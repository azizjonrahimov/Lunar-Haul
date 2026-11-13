"""Training of the integrity network (CPU, two threads, resumable, every run logged).

fit(name, cfg, seed) trains one configuration and appends one row to results/E56_runs.csv:
  loss        class-balanced binary cross-entropy per step (weights 0.5 / share of each class among the scored
              training steps), over the scored steps only (not the warm-up, not the guard after a fault);
  batches     cfg["batch"] random crops of cfg["crop"] steps from the training streams, the first W - 1 steps of a
              crop unscored (the network has no history there); Adam, cosine learning-rate decay to zero;
  model       the weights after the LAST epoch (no early stopping, so the saved trajectory ends at the model);
  validation  after every epoch the loss on all validation fault streams; at the end the event recall on validation
              faults at thresholds set on validation fault-free blocks (model choice only; never the test set).
State lives in .cache/nn/<name>/ (checkpoint after every epoch): a run that stops at --max-seconds resumes.
With trajectory=True the full weight vector is saved at the start, at a few steps of the first epoch and after every
epoch (for lunarsim.nn.landscape).
"""
from __future__ import annotations

import csv
import json
import math
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np

from . import baselines as B
from . import dataset as D
from . import faults as F
from . import model as M

ROOT = D.ROOT
STATE = os.path.join(ROOT, ".cache", "nn")
RUNS_CSV = os.path.join(ROOT, "results", "E56_runs.csv")
RUN_COLS = ("iter", "name", "stage", "seed", "config", "n_params", "window_s", "epochs", "train_loss", "val_loss",
            "val_recall_day_macro", "val_recall_hour_macro", "val_recall_day_by_type", "val_median_delay_day_s",
            "val_auc_roc", "wall_s", "note")
DEFAULT = {"arch": "tcn", "channels": 24, "kernel": 3, "dilations": [1, 2, 4, 8, 16, 32], "residual": True,
           "lr": 3e-3, "wd": 0.0, "epochs": 10, "batch": 32, "crop": 728}
FIRST_EPOCH_STEPS = (1, 2, 4, 8, 16, 32, 64)


def _torch():
    import torch
    torch.set_num_threads(2)
    return torch


def class_weights(y: np.ndarray, mask: np.ndarray) -> List[float]:
    pos = float(y[mask].mean())
    return [0.5 / (1.0 - pos), 0.5 / pos]


def weighted_bce(logits, y, mask, cw):
    """Class-balanced cross-entropy over the masked steps (torch tensors; y, mask as float)."""
    torch = _torch()
    w = (cw[0] + (cw[1] - cw[0]) * y) * mask
    loss = torch.nn.functional.binary_cross_entropy_with_logits(logits, y, reduction="none")
    return (loss * w).sum() / mask.sum().clamp(min=1.0)


def eval_loss(model, X: np.ndarray, y: np.ndarray, mask: np.ndarray, cw, batch: int = 64) -> float:
    """The loss as one number over a fixed set of streams (sum over steps / number of scored steps)."""
    torch = _torch()
    model.eval()
    tot, cnt = 0.0, 0.0
    with torch.no_grad():
        for i in range(0, len(X), batch):
            yy = torch.from_numpy(y[i:i + batch].astype(np.float32))
            mm = torch.from_numpy(mask[i:i + batch].astype(np.float32))
            n = float(mm.sum())
            if n > 0:
                tot += float(weighted_bce(model(torch.from_numpy(X[i:i + batch])), yy, mm, cw)) * n
                cnt += n
    return tot / max(cnt, 1.0)


def auc_roc(score: np.ndarray, label: np.ndarray) -> float:
    """Area under the ROC curve by ranks (ties get the mean rank)."""
    from scipy.stats import rankdata
    r = rankdata(score)
    n1 = float(label.sum())
    n0 = float(len(label) - n1)
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((r[label > 0].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0))


def val_events(score_f: np.ndarray, meta: np.ndarray, score_n: np.ndarray, weight_n: np.ndarray) -> Dict[str, Any]:
    """Event recall and delay on fault streams at thresholds calibrated on fault-free blocks."""
    bm = B.bin_max(score_n)
    out: Dict[str, Any] = {}
    kinds = meta[:, 0].astype(int)
    for rate, per_day in B.RATES.items():
        thr = B.calibrate(bm, weight_n, per_day)
        found, delay, _ = B.detect(score_f, meta, thr)
        by = {n: float(found[kinds == k].mean()) for k, n in enumerate(F.FAULT_TYPES, 1) if (kinds == k).any()}
        out[rate] = {"thr": thr, "recall_by_type": by, "recall_macro": float(np.mean(list(by.values()))),
                     "median_delay_s": float(np.nanmedian(delay)) if found.any() else float("nan")}
    return out


def append_run(row: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(RUNS_CSV), exist_ok=True)
    new = not os.path.isfile(RUNS_CSV)
    with open(RUNS_CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RUN_COLS, lineterminator="\n")
        if new:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in RUN_COLS})


def fit(name: str, cfg: Dict[str, Any], seed: int, max_s: float = 520.0, trajectory: bool = False,
        stage: str = "search", it: Any = "", note: str = "", data: Optional[Dict[str, Any]] = None,
        log: bool = True) -> Optional[Dict[str, Any]]:
    """Train (or resume) one run. Returns its summary, or None if the time ran out (call again to continue)."""
    torch = _torch()
    t_start = time.time()
    cfg = {**DEFAULT, **cfg}
    sdir = os.path.join(STATE, name)
    os.makedirs(sdir, exist_ok=True)
    done_path = os.path.join(sdir, "done.json")
    if os.path.isfile(done_path):
        return json.load(open(done_path, encoding="utf-8"))
    tr = data["train"] if data else D.load("train")
    va = data["val"] if data else D.load("val")
    Xt, yt = tr["Xf"], tr["yf"]
    mt = D.score_mask(yt, tr["mf"])
    Xv, yv = va["Xf"], va["yf"]
    mv = D.score_mask(yv, va["mf"])
    cw = class_weights(yt, mt)
    torch.manual_seed(seed)
    model = M.make_model(cfg)
    opt = torch.optim.Adam(model.parameters(), lr=cfg["lr"], weight_decay=cfg["wd"])
    n, T = yt.shape
    crop = int(cfg["crop"]) if cfg.get("crop") else T
    steps_per_epoch = int(math.ceil(n / cfg["batch"]))
    total_steps = steps_per_epoch * int(cfg["epochs"])
    st = {"epoch": 0, "hist": [], "wall": 0.0}
    traj: Dict[str, list] = {"w": [], "epoch": [], "step": []}
    ck = os.path.join(sdir, "ckpt.pt")
    if os.path.isfile(ck):
        # B-119 C13: weights_only=True (tensors and plain Python only; see the save below). A checkpoint written
        # before 13 Nov 2026 held numpy arrays and cannot be resumed this way: train that run again.
        z = torch.load(ck, weights_only=True)
        model.load_state_dict(z["model"])
        opt.load_state_dict(z["opt"])
        st = z["st"]
        traj = {"w": [w.numpy() for w in z["traj"]["w"]], "epoch": list(z["traj"]["epoch"]),
                "step": list(z["traj"]["step"])}
    elif trajectory:
        traj["w"].append(M.get_flat(model)); traj["epoch"].append(0.0); traj["step"].append(0)
    ep_time = 60.0
    while st["epoch"] < cfg["epochs"]:
        if time.time() - t_start > max_s - 1.3 * ep_time - 45.0:
            print(f"{name}: time limit at epoch {st['epoch']}; rerun to continue", flush=True)
            return None
        t_ep = time.time()
        ep = st["epoch"]
        rng = np.random.default_rng([D.MASTER_SEED, 7, seed, ep])
        order = rng.permutation(n)
        model.train()
        tot, cnt = 0.0, 0
        for bi in range(steps_per_epoch):
            idx = np.sort(order[bi * cfg["batch"]:(bi + 1) * cfg["batch"]])
            s0 = int(rng.integers(0, T - crop + 1))
            xb = torch.from_numpy(Xt[idx, s0:s0 + crop])
            yb = torch.from_numpy(yt[idx, s0:s0 + crop].astype(np.float32))
            mb = mt[idx, s0:s0 + crop].copy()
            mb[:, :max(model.rf - 1, 0) if cfg.get("arch") != "gru" else 64] = False
            mb = torch.from_numpy(mb.astype(np.float32))
            gstep = ep * steps_per_epoch + bi
            for g in opt.param_groups:
                g["lr"] = cfg["lr"] * 0.5 * (1.0 + math.cos(math.pi * gstep / total_steps))
            opt.zero_grad()
            loss = weighted_bce(model(xb), yb, mb, cw)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
            tot += float(loss.detach()); cnt += 1
            if trajectory and ep == 0 and (bi + 1) in FIRST_EPOCH_STEPS and bi + 1 < steps_per_epoch:
                traj["w"].append(M.get_flat(model)); traj["epoch"].append((bi + 1) / steps_per_epoch)
                traj["step"].append(bi + 1)
        vl = eval_loss(model, Xv, yv, mv, cw)
        st["epoch"] = ep + 1
        st["hist"].append({"epoch": ep + 1, "train_loss": tot / cnt, "val_loss": vl})
        if trajectory:
            traj["w"].append(M.get_flat(model)); traj["epoch"].append(float(ep + 1))
            traj["step"].append((ep + 1) * steps_per_epoch)
        ep_time = time.time() - t_ep
        st["wall"] += ep_time
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                    "st": json.loads(json.dumps(st, default=float)),
                    "traj": {"w": [torch.from_numpy(np.asarray(w)) for w in traj["w"]],
                             "epoch": [float(x) for x in traj["epoch"]], "step": [int(x) for x in traj["step"]]}}, ck)
        print(f"  {name} epoch {ep + 1}/{cfg['epochs']}: train {tot / cnt:.4f} val {vl:.4f} ({ep_time:.0f} s)",
              flush=True)
    if time.time() - t_start > max_s - 60.0:
        print(f"{name}: time limit before the final validation; rerun", flush=True)
        return None
    t_ev = time.time()
    sf = M.score_streams(model, Xv)
    sn = M.score_streams(model, va["Xn"])
    ev = val_events(sf, va["mf"], sn, va["mn"][:, D.META.index("weight")])
    sub = mv.copy()
    sub[:, np.arange(sub.shape[1]) % 10 != 0] = False
    auc = auc_roc(sf[sub], yv[sub])
    st["wall"] += time.time() - t_ev
    torch.save(model.state_dict(), os.path.join(sdir, "model.pt"))
    if trajectory:
        np.savez(os.path.join(sdir, "trajectory.npz"), w=np.array(traj["w"], np.float32),
                 epoch=np.array(traj["epoch"]), step=np.array(traj["step"]))
    out = {"name": name, "stage": stage, "iter": it, "seed": seed, "config": cfg, "n_params": M.n_params(model),
           "window_s": model.rf, "epochs": cfg["epochs"], "hist": st["hist"], "class_weights": cw,
           "train_loss": st["hist"][-1]["train_loss"], "val_loss": st["hist"][-1]["val_loss"], "val_events": ev,
           "val_auc_roc": auc, "wall_s": round(st["wall"], 1), "note": note}
    with open(done_path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    if log:
        append_run({"iter": it, "name": name, "stage": stage, "seed": seed,
                    "config": json.dumps(cfg, separators=(",", ":")), "n_params": out["n_params"],
                    "window_s": out["window_s"], "epochs": cfg["epochs"], "train_loss": round(out["train_loss"], 5),
                    "val_loss": round(out["val_loss"], 5),
                    "val_recall_day_macro": round(ev["day"]["recall_macro"], 4),
                    "val_recall_hour_macro": round(ev["hour"]["recall_macro"], 4),
                    "val_recall_day_by_type": json.dumps({k: round(v, 3) for k, v in
                                                          ev["day"]["recall_by_type"].items()}, separators=(",", ":")),
                    "val_median_delay_day_s": ev["day"]["median_delay_s"], "val_auc_roc": round(auc, 5),
                    "wall_s": out["wall_s"], "note": note})
    print(f"{name}: val loss {out['val_loss']:.4f}, recall@1/day {ev['day']['recall_macro']:.3f} "
          f"{ev['day']['recall_by_type']}, recall@1/hour {ev['hour']['recall_macro']:.3f}, AUC {auc:.4f}, "
          f"{out['n_params']} parameters, {out['wall_s']} s", flush=True)
    return out


def load_model(name: str):
    """The trained torch model of a finished run."""
    torch = _torch()
    sdir = os.path.join(STATE, name)
    done = json.load(open(os.path.join(sdir, "done.json"), encoding="utf-8"))
    m = M.make_model(done["config"])
    m.load_state_dict(torch.load(os.path.join(sdir, "model.pt"), weights_only=True))
    m.eval()
    return m, done
