"""The loss landscape of the integrity network and the path the optimiser took through it.

    python -m lunarsim.nn.landscape [--run final_s0] [--max-seconds 520]      # resumable; run until it says done

Methods:
  random slice   Li, Xu, Taylor, Studer, Goldstein, "Visualizing the Loss Landscape of Neural Nets", NeurIPS 2018:
                 the loss at theta* + a d1 + b d2 for two random Gaussian directions with FILTER-WISE normalisation
                 (every filter of a direction is rescaled to the norm of the same filter of theta*; a filter = one
                 output channel of a convolution; bias directions are zero, as in the paper's code with ignore=biasbn);
  PCA plane      same paper, section 7: PCA of the saved weight vectors minus the final weights; the loss on a grid
                 in the plane of the first two components, the checkpoints projected onto it, the variance the two
                 components explain;
  interpolation  Goodfellow, Vinyals, Saxe, "Qualitatively characterizing neural network optimization problems",
                 ICLR 2015: the loss along the straight line from the initial to the final weights.
The loss is the training loss function (class-balanced cross-entropy over scored steps, model in evaluation mode) on
two FIXED subsets: 12 validation fault streams of each type ("val") and 12 training fault streams of each type
("train"). The loss "recorded at a checkpoint" is this same function at the saved weights.
Self-check: with high explained variance the loss at the grid node nearest a projected checkpoint must be close to
the loss recorded at that checkpoint; both gaps (projection alone, projection + grid) are reported per checkpoint.
The optimiser is Adam with a cosine learning-rate decay: "the path gradient descent took" is its path.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from . import dataset as D
from . import faults as F
from . import model as M
from . import train as T

ROOT = D.ROOT
OUT_JSON = os.path.join(D.DATA_DIR, "landscape.json")
N_GRID = 41
MARGIN = 0.2
PER_TYPE = 12
N_INTERP = 61
RANDOM_SEED = 5601


# ------------------------------------------------------------------------------------------------ geometry (pure)
def pca_plane(W: np.ndarray) -> Dict[str, np.ndarray]:
    """PCA of the checkpoints minus the last one. W [K, P]. Returns the two unit directions, the coordinates of
    every checkpoint in the plane (origin = the final weights), the explained-variance ratios and, per checkpoint,
    the share of its distance to the final weights that lies outside the plane."""
    Dm = (W - W[-1]).astype(np.float64)
    C = Dm - Dm.mean(axis=0)
    _, s, vt = np.linalg.svd(C, full_matrices=False)
    var = s ** 2
    e = vt[:2]
    xy = Dm @ e.T
    resid = np.linalg.norm(Dm - xy @ e, axis=1)
    norm = np.linalg.norm(Dm, axis=1)
    return {"e1": e[0], "e2": e[1], "xy": xy, "explained": var[:2] / var.sum(), "explained_all": var / var.sum(),
            "resid_rel": np.where(norm > 0, resid / np.maximum(norm, 1e-30), 0.0)}


def axis_through_zero(lo: float, hi: float, n: int = N_GRID, margin: float = MARGIN) -> np.ndarray:
    """At least n evenly spaced values that cover [lo, hi] with a margin and contain 0 exactly."""
    lo, hi = min(lo, 0.0), max(hi, 0.0)
    span = max(hi - lo, 1e-12)
    lo, hi = lo - margin * span, hi + margin * span
    h = (hi - lo) / (n - 1)
    i_lo, i_hi = int(math.floor(lo / h)), int(math.ceil(hi / h))
    return h * np.arange(i_lo, i_hi + 1)


def filter_normalised_direction(shapes: List[Tuple[int, ...]], theta: np.ndarray, rng: np.random.Generator
                                ) -> np.ndarray:
    """A random direction with every filter rescaled to the norm of the same filter of theta (biases: zero)."""
    out = np.zeros_like(theta, dtype=np.float64)
    i = 0
    for shp in shapes:
        n = int(np.prod(shp))
        if len(shp) > 1:
            d = rng.normal(size=shp)
            w = theta[i:i + n].reshape(shp).astype(np.float64)
            dn = np.linalg.norm(d.reshape(shp[0], -1), axis=1)
            wn = np.linalg.norm(w.reshape(shp[0], -1), axis=1)
            d = d * (wn / np.maximum(dn, 1e-12)).reshape((-1,) + (1,) * (len(shp) - 1))
            out[i:i + n] = d.ravel()
        i += n
    return out


def grid_loss(loss_fn: Callable[[np.ndarray], float], theta: np.ndarray, d1: np.ndarray, d2: np.ndarray,
              xs: np.ndarray, ys: np.ndarray, cache: Optional[str] = None, deadline: Optional[float] = None
              ) -> Optional[np.ndarray]:
    """loss_fn(theta + x d1 + y d2) on the grid, Z[iy, ix]. Saves finished rows to cache; None if out of time."""
    Z = np.full((len(ys), len(xs)), np.nan)
    if cache and os.path.isfile(cache):
        with np.load(cache) as z:
            if z["Z"].shape == Z.shape and np.allclose(z["xs"], xs) and np.allclose(z["ys"], ys):
                Z = z["Z"].copy()
    for iy, y in enumerate(ys):
        if not np.isnan(Z[iy]).any():
            continue
        if deadline is not None and time.time() > deadline:
            return None
        for ix, x in enumerate(xs):
            Z[iy, ix] = loss_fn(theta + x * d1 + y * d2)
        if cache:
            np.savez(cache, Z=Z, xs=xs, ys=ys)
    return Z


def nearest_node(xs: np.ndarray, ys: np.ndarray, Z: np.ndarray, x: float, y: float) -> float:
    return float(Z[int(np.argmin(np.abs(ys - y))), int(np.argmin(np.abs(xs - x)))])


def sig4(a: Any) -> Any:
    """Round to 4 significant digits (nested lists)."""
    if isinstance(a, (list, tuple, np.ndarray)):
        return [sig4(v) for v in a]
    v = float(a)
    return float(f"{v:.4g}") if math.isfinite(v) else None


# ------------------------------------------------------------------------------------------------ the experiment
def subsets() -> Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    out = {}
    for name, split in (("val", "val"), ("train", "train")):
        d = D.load(split)
        kinds = d["mf"][:, 0].astype(int)
        idx = np.concatenate([np.flatnonzero(kinds == k)[:PER_TYPE] for k in range(1, len(F.FAULT_TYPES) + 1)])
        out[name] = (d["Xf"][idx].copy(), d["yf"][idx].copy(), D.score_mask(d["yf"][idx], d["mf"][idx]))
        del d
    return out


def run(name: str = "final_s0", max_s: float = 520.0) -> bool:
    import torch
    torch.set_num_threads(2)
    t0 = time.time()
    deadline = t0 + max_s - 40.0
    sdir = os.path.join(T.STATE, name)
    cdir = os.path.join(T.STATE, "landscape_" + name)
    os.makedirs(cdir, exist_ok=True)
    model, done = T.load_model(name)
    with np.load(os.path.join(sdir, "trajectory.npz")) as z:
        W, ep, step = z["w"].astype(np.float64), z["epoch"], z["step"]
    theta = W[-1]
    assert np.allclose(theta, M.get_flat(model)), "the trajectory must end at the trained model"
    cw = done["class_weights"]
    sub = subsets()

    def loss(which: str) -> Callable[[np.ndarray], float]:
        X, y, m = sub[which]

        def fn(vec: np.ndarray) -> float:
            M.set_flat(model, vec)
            return T.eval_loss(model, X, y, m, cw, batch=64)
        return fn

    lv, lt = loss("val"), loss("train")
    # losses recorded at the checkpoints
    rec_path = os.path.join(cdir, "recorded.npz")
    if os.path.isfile(rec_path):
        with np.load(rec_path) as z:
            rec_v, rec_t = z["v"], z["t"]
    else:
        rec_v = np.array([lv(w) for w in W])
        rec_t = np.array([lt(w) for w in W])
        np.savez(rec_path, v=rec_v, t=rec_t)
    pca = pca_plane(W)
    xs = axis_through_zero(pca["xy"][:, 0].min(), pca["xy"][:, 0].max())
    ys = axis_through_zero(pca["xy"][:, 1].min(), pca["xy"][:, 1].max())
    Zv = grid_loss(lv, theta, pca["e1"], pca["e2"], xs, ys, os.path.join(cdir, "pca_val.npz"), deadline)
    if Zv is None:
        print("landscape: time limit in the PCA plane (validation); rerun", flush=True)
        return False
    Zt = grid_loss(lt, theta, pca["e1"], pca["e2"], xs, ys, os.path.join(cdir, "pca_train.npz"), deadline)
    if Zt is None:
        print("landscape: time limit in the PCA plane (training); rerun", flush=True)
        return False
    shapes = [tuple(p.shape) for p in model.parameters()]
    rng = np.random.default_rng(RANDOM_SEED)
    d1 = filter_normalised_direction(shapes, theta, rng)
    d2 = filter_normalised_direction(shapes, theta, rng)
    rs = np.linspace(-1.0, 1.0, N_GRID)
    Zr = grid_loss(lv, theta, d1, d2, rs, rs, os.path.join(cdir, "random_val.npz"), deadline)
    if Zr is None:
        print("landscape: time limit in the random slice; rerun", flush=True)
        return False
    if time.time() > deadline - 60.0:
        print("landscape: time limit before the interpolation; rerun", flush=True)
        return False
    ip_path = os.path.join(cdir, "interp.npz")
    alpha = np.linspace(-0.25, 1.25, N_INTERP)
    if os.path.isfile(ip_path):
        with np.load(ip_path) as z:
            iv, it, pv = z["v"], z["t"], z["p"]
    else:
        iv = np.array([lv((1 - a) * W[0] + a * theta) for a in alpha])
        it = np.array([lt((1 - a) * W[0] + a * theta) for a in alpha])
        pv = np.array([lv(theta + x * pca["e1"] + y * pca["e2"]) for x, y in pca["xy"]])    # loss at the projections
        np.savez(ip_path, v=iv, t=it, p=pv)
    M.set_flat(model, theta)
    # self-check
    near = np.array([nearest_node(xs, ys, Zv, x, y) for x, y in pca["xy"]])
    gap_proj = np.abs(pv - rec_v)
    gap_grid = np.abs(near - rec_v)
    centre = nearest_node(xs, ys, Zv, 0.0, 0.0)
    check = {"explained_variance_2": float(pca["explained"].sum()),
             "grid_centre_minus_final_loss": float(centre - rec_v[-1]),
             "projection_gap_abs": {"max": float(gap_proj.max()), "median": float(np.median(gap_proj))},
             "projection_gap_rel": {"max": float((gap_proj / rec_v).max()), "median": float(np.median(gap_proj / rec_v))},
             "nearest_node_gap_abs": {"max": float(gap_grid.max()), "median": float(np.median(gap_grid))},
             "nearest_node_gap_rel": {"max": float((gap_grid / rec_v).max()),
                                      "median": float(np.median(gap_grid / rec_v))},
             "worst_checkpoint_epoch_nearest_node": float(ep[int(np.argmax(gap_grid / rec_v))]),
             "out_of_plane_share_of_distance": {"max": float(pca["resid_rel"][:-1].max()),
                                                "median": float(np.median(pca["resid_rel"][:-1]))},
             "note": "gap = |loss on the plane - loss recorded at the checkpoint| on the validation subset; "
                     "'projection' evaluates the plane exactly at the projected point, 'nearest node' at the "
                     "closest grid node (what the page shows)"}
    from .evaluate import layer_list
    doc = {"format": "lunarsim-loss-landscape", "version": 1, "run": name, "seed": done["seed"],
           "what": "loss surface of the integrity network (E56) and the path of its training run",
           "methods": {"pca": "Li et al. 2018 (NeurIPS), section 7", "random": "Li et al. 2018, filter-wise "
                       "normalisation, biases not perturbed", "interp": "Goodfellow et al. 2015 (ICLR)"},
           "loss": {"name": "class-balanced binary cross-entropy per scored step",
                    "class_weights_neg_pos": sig4(cw), "val_subset_streams": len(sub["val"][0]),
                    "train_subset_streams": len(sub["train"][0]), "streams_per_fault_type": PER_TYPE},
           "optimiser": {"name": "Adam, cosine learning-rate decay to zero", "lr": done["config"]["lr"],
                         "batch": done["config"]["batch"], "epochs": done["config"]["epochs"]},
           "model": {"n_params": M.n_params(model), "window_steps": model.rf, "layers": layer_list(model)},
           "normalisation": {"features": list(F.FEATURES),
                             "transform": [{"fn": fn, "pre": pre, "post": post} for fn, pre, post in M.TRANSFORMS],
                             "rule": "x_norm = fn(x / pre) / post; lin = identity, slog1p = sign(x) ln(1 + |x|)"},
           "pca": {"x": sig4(xs), "y": sig4(ys), "val": sig4(Zv), "train": sig4(Zt),
                   "grid_note": "loss[iy][ix] at final weights + x[ix] e1 + y[iy] e2; (0, 0) is the final model",
                   "explained_variance": sig4(pca["explained"]), "explained_variance_sum": sig4(pca["explained"].sum()),
                   "path": [{"epoch": sig4(ep[k]), "step": int(step[k]), "x": sig4(pca["xy"][k, 0]),
                             "y": sig4(pca["xy"][k, 1]), "val_loss": sig4(rec_v[k]), "train_loss": sig4(rec_t[k]),
                             "val_loss_on_plane": sig4(pv[k]), "out_of_plane": sig4(pca["resid_rel"][k])}
                            for k in range(len(W))],
                   "self_check": {k: (sig4(v) if not isinstance(v, (dict, str)) else
                                      ({kk: sig4(vv) for kk, vv in v.items()} if isinstance(v, dict) else v))
                                  for k, v in check.items()}},
           "random": {"x": sig4(rs), "y": sig4(rs), "val": sig4(Zr), "seed": RANDOM_SEED,
                      "grid_note": "loss[iy][ix] at final weights + x[ix] d1 + y[iy] d2, filter-normalised"},
           "interp": {"alpha": sig4(alpha), "val": sig4(iv), "train": sig4(it),
                      "note": "weights = (1 - alpha) initial + alpha final"},
           "curves": {"epoch": [h["epoch"] for h in done["hist"]],
                      "train_loss_running": sig4([h["train_loss"] for h in done["hist"]]),
                      "val_loss_all_streams": sig4([h["val_loss"] for h in done["hist"]])}}
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, separators=(",", ":"))
        f.write("\n")
    np.savez(os.path.join(cdir, "all.npz"), xs=xs, ys=ys, Zv=Zv, Zt=Zt, rs=rs, Zr=Zr, alpha=alpha, iv=iv, it=it,
             xy=pca["xy"], ep=ep, rec_v=rec_v, rec_t=rec_t, pv=pv, explained=pca["explained"])
    summary = {"file": os.path.relpath(OUT_JSON, ROOT).replace("\\", "/"), "bytes": os.path.getsize(OUT_JSON),
               "run": name, "checkpoints": int(len(W)), "grid": [int(len(xs)), int(len(ys))],
               "explained_variance": [float(v) for v in pca["explained"]], **check}
    res_path = os.path.join(ROOT, "results", "E56_integrity.json")
    if os.path.isfile(res_path):
        res = json.load(open(res_path, encoding="utf-8"))
        res["landscape"] = summary
        with open(res_path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(res, f, indent=1)
            f.write("\n")
    with open(os.path.join(cdir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    print("landscape: done", json.dumps(summary), flush=True)
    return True


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="final_s0")
    ap.add_argument("--max-seconds", type=float, default=520.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 15.0, exit=True)
    sys.exit(0 if run(a.run, a.max_seconds) else 3)
