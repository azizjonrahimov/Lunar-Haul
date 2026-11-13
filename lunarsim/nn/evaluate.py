"""E56 evaluation: every detector at the same false-alarm rates, event level, with bootstrap intervals.

    python -m lunarsim.nn.evaluate [--on val]      # --on val = a rehearsal that never opens the test sets
                                                   # exit code 3 = time limit; run it again, it resumes (scores of
                                                   # every detector are saved per data set in .cache/nn/)

Thresholds: for every detector (and every seed of the network) the threshold for 1 false alarm per pair-day and for
1 per pair-hour is set on the VALIDATION fault-free blocks (baselines.calibrate). Nothing is set on test data.
Then, on the test set and on the out-of-distribution set:
  false alarms per pair-day on the fault-free blocks (stratum-weighted to the natural mix), and per hour of blocks in
    which somebody drives;
  event recall (an event is found if a step inside it is above threshold), per fault type and overall;
  event precision, which depends on how often faults happen, so it is given for a stated fault rate:
    precision_at_1_fault_per_pair_day = recall / (recall + false alarms per pair-day on the fault-free blocks)
    (per fault type: as if every fault were of that type); and, as measured on the fault streams themselves,
    found events / (found events + false-alarm bins before the faults), where a fault follows 1 to 6.7 clean minutes;
  detection delay of the found events (median, p90), and the paired delay difference network - baseline on the events
    both found;
  window-level ROC AUC and PR AUC on the scored steps of the fault streams (every 5th step);
  the event numbers again per ranging class (the class in use for most of the event: UWB or the long-range radio).
Network numbers are the mean over the training seeds with the standard deviation over seeds; 95 % intervals are a
bootstrap over events (1,000 resamples; the same resample for every seed).
Also: inference time per window, parameter count, bytes; the policy file data/policies/integrity_net_v1.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from . import baselines as B
from . import dataset as D
from . import faults as F
from . import model as M
from . import train as T

ROOT = D.ROOT
RESULT = os.path.join(ROOT, "results", "E56_integrity.json")
TABLE = os.path.join(ROOT, "results", "table_E56.csv")
POLICY = os.path.join(ROOT, "data", "policies", "integrity_net_v1.json")
POLICY_CHECK = os.path.join(ROOT, "data", "policies", "integrity_net_v1.check.json")
EVAL_CACHE = os.path.join(T.STATE, "eval_arrays.npz")
BASELINES = os.path.join(T.STATE, "baselines.json")
FINAL_SEEDS = (0, 1, 2, 3, 4)
DETECTORS = ("chi2_step", "chi2_window", "cusum", "logreg", "net")
LABEL = {"chi2_step": "chi-square, per step", "chi2_window": "chi-square, windowed", "cusum": "CUSUM",
         "logreg": "logistic regression", "net": "network"}
N_BOOT = 1000
AUC_STRIDE = 5
TYPES = F.FAULT_TYPES + ("all",)


def final_name(seed: int) -> str:
    return f"final_s{seed}"


def baseline_scorers() -> Dict[str, Callable[[np.ndarray], np.ndarray]]:
    doc = json.load(open(BASELINES, encoding="utf-8"))
    lr = B.LogReg.from_doc(doc["logreg"])
    w, k, ref = int(doc["chi2_window_W"]), float(doc["cusum_k"]), int(doc["cusum_ref"])
    return {"chi2_step": B.chi2_step, "chi2_window": lambda X: B.chi2_window(X, w),
            "cusum": lambda X: B.cusum(X, k, ref), "logreg": lr.score}


def pr_auc(score: np.ndarray, label: np.ndarray) -> float:
    """Average precision."""
    order = np.argsort(-score, kind="stable")
    y = label[order] > 0
    tp = np.cumsum(y)
    prec = tp / np.arange(1, len(y) + 1)
    return float(prec[y].sum() / max(y.sum(), 1))


def roc_curve(score: np.ndarray, label: np.ndarray, n: int = 200) -> Tuple[np.ndarray, np.ndarray]:
    order = np.argsort(-score, kind="stable")
    y = label[order] > 0
    tpr = np.r_[0.0, np.cumsum(y) / max(y.sum(), 1)]
    fpr = np.r_[0.0, np.cumsum(~y) / max((~y).sum(), 1)]
    grid = np.unique(np.r_[np.logspace(-5, 0, n), 0.0])
    return grid, np.interp(grid, fpr, tpr)


def _ci(samples: np.ndarray) -> List[float]:
    s = samples[np.isfinite(samples)]
    if not len(s):
        return [float("nan"), float("nan")]
    return [float(np.percentile(s, 2.5)), float(np.percentile(s, 97.5))]


def _stat(per_seed: np.ndarray, boot: np.ndarray) -> Dict[str, Any]:
    """per_seed [S]; boot [B] (already the mean over seeds per resample)."""
    return {"mean": float(np.nanmean(per_seed)) if np.isfinite(per_seed).any() else float("nan"),
            "sd_seeds": float(np.nanstd(per_seed)) if len(per_seed) > 1 and np.isfinite(per_seed).any() else 0.0,
            "ci95": _ci(boot)}


def _nanq(a: np.ndarray, q: float, axis: int) -> np.ndarray:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanpercentile(a, q, axis=axis)


def _mean0(a: np.ndarray) -> np.ndarray:
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return np.nanmean(a, axis=0)


def event_block(found: np.ndarray, delay: np.ndarray, fp: np.ndarray, kinds: np.ndarray,
                rng: np.random.Generator, keep: Optional[np.ndarray] = None,
                fa_day: Optional[np.ndarray] = None) -> Dict[str, Any]:
    """found, delay, fp: [S, N] over seeds and fault streams. Per fault type and overall (keep = a subset)."""
    out: Dict[str, Any] = {}
    keep = np.ones(len(kinds), bool) if keep is None else keep
    for k, name in list(enumerate(F.FAULT_TYPES, 1)) + [(0, "all")]:
        sel = np.flatnonzero((kinds == k) & keep) if k else np.flatnonzero((kinds > 0) & keep)
        if not len(sel):
            continue
        f, d, p = found[:, sel], delay[:, sel], fp[:, sel]
        idx = rng.integers(0, len(sel), (N_BOOT, len(sel)))
        fb, db, pb = f[:, idx], d[:, idx], p[:, idx]                     # [S, B, n]
        prec = f.sum(1) / np.maximum(f.sum(1) + p.sum(1), 1)
        prec_b = fb.sum(2) / np.maximum(fb.sum(2) + pb.sum(2), 1)
        rec = f.mean(1)
        out[name] = {"n_events": int(len(sel)),
                     "recall": _stat(rec, fb.mean(2).mean(0)),
                     "precision_at_1_fault_per_pair_day": (float(np.mean(rec / np.maximum(rec + fa_day, 1e-12)))
                                                           if fa_day is not None else None),
                     "precision_on_fault_streams": _stat(prec, prec_b.mean(0)),
                     "delay_median_s": _stat(_nanq(d, 50, 1), _mean0(_nanq(db, 50, 2))),
                     "delay_p90_s": _stat(_nanq(d, 90, 1), _mean0(_nanq(db, 90, 2)))}
    return out


def paired_delay(d_net: np.ndarray, d_base: np.ndarray, kinds: np.ndarray, rng: np.random.Generator
                 ) -> Dict[str, Any]:
    """Median of (network delay - baseline delay) over the events both found; d_net [S, N], d_base [N]."""
    out = {}
    for k, name in list(enumerate(F.FAULT_TYPES, 1)) + [(0, "all")]:
        sel = np.flatnonzero(kinds == k) if k else np.flatnonzero(kinds > 0)
        diff = d_net[:, sel] - d_base[None, sel]                         # nan where either missed
        idx = rng.integers(0, len(sel), (N_BOOT, len(sel)))
        out[name] = {"n_both_mean": float(np.isfinite(diff).sum(1).mean()),
                     "median_diff_s": _stat(_nanq(diff, 50, 1), _mean0(_nanq(diff[:, idx], 50, 2)))}
    return out


def compare(found_net: np.ndarray, d_net: np.ndarray, found_base: np.ndarray, d_base: np.ndarray,
            sel: np.ndarray, rng: np.random.Generator) -> Dict[str, Any]:
    """Network against one baseline on the events sel (PREREG6, H15). found_net, d_net [S, N]; base [N].

    delay_median_diff_s   median delay of the network's found events minus the baseline's (each over its own found
                          events; network: mean over seeds), bootstrap over events: 95 % and 90 % intervals;
    paired_diff_s         median of (network delay - baseline delay) over the events both found;
    censored_diff_s       the same difference of medians with a missed event counted as a delay of 600 s (the longest
                          fault), so that finding fewer faults cannot shorten the median;
    recall_diff           network recall minus baseline recall."""
    fn, dn, fb, db = found_net[:, sel], d_net[:, sel], found_base[sel], d_base[sel]
    idx = rng.integers(0, len(sel), (N_BOOT, len(sel)))

    def med(a, axis):
        return _nanq(a, 50, axis)

    miss_s = float(F.EVENT_S[1])                                 # B-119 C13: the longest fault, from faults.EVENT_S
    cn, cb = np.where(np.isnan(dn), miss_s, dn), np.where(np.isnan(db), miss_s, db)
    out = {}
    for key, point, boot in (
            ("delay_median_diff_s", med(dn, 1).mean() - med(db, 0), _mean0(med(dn[:, idx], 2)) - med(db[idx], 1)),
            ("paired_diff_s", np.nanmean(med(dn - db[None], 1)), _mean0(med((dn - db[None])[:, idx], 2))),
            ("censored_diff_s", np.median(cn, axis=1).mean() - np.median(cb),
             np.median(cn[:, idx], axis=2).mean(0) - np.median(cb[idx], axis=1)),
            ("recall_diff", fn.mean() - fb.mean(), fn[:, idx].mean(2).mean(0) - fb[idx].mean(1))):
        b = boot[np.isfinite(boot)]
        out[key] = {"value": float(point), "ci95": _ci(boot),
                    "ci90": [float(np.percentile(b, 5)), float(np.percentile(b, 95))] if len(b) else [None, None],
                    # B-118 N8: the resample counts a bootstrap p is computed from
                    "boot_n": int(len(b)), "boot_at_or_above_0": int((b >= 0).sum()),
                    "boot_at_or_below_0": int((b <= 0).sum())}
    out["delay_median_s"] = {"net": float(med(dn, 1).mean()), "base": float(med(db, 0))}
    out["recall"] = {"net": float(fn.mean()), "base": float(fb.mean())}
    out["n_events"] = int(len(sel))
    return out


def h15_block(arr: Dict[str, Any], kinds: np.ndarray) -> Dict[str, Any]:
    """The comparisons PREREG6 names for H15, at 1 false alarm per pair-day."""
    out: Dict[str, Any] = {}
    for base in ("chi2_step", "cusum", "logreg"):
        out[base] = {}
        for k, name in enumerate(F.FAULT_TYPES, 1):
            rng = np.random.default_rng([D.MASTER_SEED, 15, k])
            out[base][name] = compare(arr["found__net__day"], arr["delay__net__day"], arr[f"found__{base}__day"][0],
                                      arr[f"delay__{base}__day"][0], np.flatnonzero(kinds == k), rng)
    return out


def evaluate_set(scores_f: Dict[str, np.ndarray], meta: np.ndarray, y: np.ndarray, scores_n: Dict[str, np.ndarray],
                 mn: np.ndarray, thr: Dict[str, Dict[str, np.ndarray]], seed: int = 0
                 ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """scores_*[det] = [S, N, T]; thr[det][rate] = [S]. Returns (results, arrays for the figures)."""
    kinds = meta[:, 0].astype(int)
    cls_f = meta[:, D.META.index("cls")].astype(int)
    cls_n = mn[:, D.META.index("cls")].astype(int)
    wn = mn[:, D.META.index("weight")]
    active = mn[:, D.META.index("ctx")] == 1
    res: Dict[str, Any] = {}
    arr: Dict[str, Any] = {}
    mask = D.score_mask(y, meta)
    sub = mask.copy()
    sub[:, np.arange(sub.shape[1]) % AUC_STRIDE != 0] = False
    for det in DETECTORS:
        sf, sn = scores_f[det], scores_n[det]
        S = len(sf)
        res[det] = {}
        bms = [B.bin_max(sn[s]) for s in range(S)]
        for rate in B.RATES:
            rng = np.random.default_rng([D.MASTER_SEED, 11, seed])           # the same resamples for every detector
            fd = [B.detect(sf[s], meta, float(thr[det][rate][s])) for s in range(S)]
            found = np.array([q[0] for q in fd])
            delay = np.array([q[1] for q in fd])
            fp = np.array([q[2] for q in fd])
            fa = np.array([B.fa_per_day(bms[s], wn, float(thr[det][rate][s])) for s in range(S)])
            idx = rng.integers(0, len(wn), (N_BOOT, len(wn)))
            fa_b = np.array([[B.fa_per_day(bms[s][i], wn[i], float(thr[det][rate][s])) for i in idx[:200]]
                             for s in range(S)]).mean(0)
            act_h = active.sum() * bms[0].shape[1] * B.BIN_S / 3600.0
            fa_act = np.array([(bms[s][active] > thr[det][rate][s]).sum() / max(act_h, 1e-9) for s in range(S)])
            sta_h = (~active).sum() * bms[0].shape[1] * B.BIN_S / 3600.0
            fa_sta = np.array([(bms[s][~active] > thr[det][rate][s]).sum() / max(sta_h, 1e-9) for s in range(S)])
            res[det][rate] = {"threshold": [float(t) for t in thr[det][rate]],
                              "fa_per_pair_day": _stat(fa, fa_b),
                              "fa_per_hour_in_blocks_with_driving": float(fa_act.mean()),
                              "fa_per_hour_in_blocks_without_driving": float(fa_sta.mean()),
                              "fa_per_pair_day_by_class": {
                                  c: float(np.mean([B.fa_per_day(bms[s][cls_n == ci], wn[cls_n == ci],
                                                                 float(thr[det][rate][s])) for s in range(S)]))
                                  for ci, c in enumerate(D.CLASSES) if (cls_n == ci).any()},
                              "events": event_block(found, delay, fp, kinds, rng, None, fa),
                              "events_by_class": {c: event_block(found, delay, fp, kinds, rng, cls_f == ci)
                                                  for ci, c in enumerate(D.CLASSES)}}
            arr[f"found__{det}__{rate}"] = found
            arr[f"delay__{det}__{rate}"] = delay
        auc = {name: {"roc": [], "pr": []} for name in TYPES}
        for s in range(S):
            for k, name in list(enumerate(F.FAULT_TYPES, 1)) + [(0, "all")]:
                rows = (kinds == k) if k else (kinds >= 0)
                m = sub & rows[:, None]
                auc[name]["roc"].append(T.auc_roc(sf[s][m], y[m]))
                auc[name]["pr"].append(pr_auc(sf[s][m], y[m]))
        res[det]["window_auc"] = {name: {"roc_auc": float(np.mean(v["roc"])), "pr_auc": float(np.mean(v["pr"])),
                                         "roc_auc_sd_seeds": float(np.std(v["roc"]))} for name, v in auc.items()}
        fpr, tpr = roc_curve(sf[0][sub], y[sub])
        arr[f"roc_fpr__{det}"], arr[f"roc_tpr__{det}"] = fpr, tpr
    res["paired_delay_net_minus"] = {}
    for base in ("chi2_step", "cusum", "logreg"):
        res["paired_delay_net_minus"][base] = {}
        for rate in B.RATES:
            rng = np.random.default_rng([D.MASTER_SEED, 12, seed])
            res["paired_delay_net_minus"][base][rate] = paired_delay(
                arr[f"delay__net__{rate}"], arr[f"delay__{base}__{rate}"][0], kinds, rng)
    arr["kinds"] = kinds
    arr["cls"] = cls_f
    res["h15_net_against"] = h15_block(arr, kinds)
    return res, arr


def time_inference(model, n: int = 2000) -> Dict[str, Any]:
    """Seconds per window on this CPU: the torch model with one thread, and the numpy reference runtime."""
    import torch
    n_threads = torch.get_num_threads()                          # B-119 C13: restored afterwards, not set to 2
    torch.set_num_threads(1)
    rng = np.random.default_rng(0)
    x = torch.from_numpy(rng.normal(size=(1, model.rf, len(F.FEATURES))).astype(np.float32))
    model.eval()
    ts = []
    with torch.no_grad():
        for _ in range(200):
            model(x)
        for _ in range(n):
            t = time.perf_counter()
            model(x)
            ts.append(time.perf_counter() - t)
    pol = M.Policy(doc=M.to_doc(model, "timing"))
    xn = x.numpy()[0]
    tn = []
    for _ in range(300):
        t = time.perf_counter()
        pol(xn)
        tn.append(time.perf_counter() - t)
    torch.set_num_threads(n_threads)
    import platform
    return {"window_steps": model.rf, "torch_1thread_ms": {"median": float(np.median(ts) * 1e3),
                                                           "p99": float(np.percentile(ts, 99) * 1e3), "n": n},
            "numpy_reference_ms": {"median": float(np.median(tn) * 1e3), "p99": float(np.percentile(tn, 99) * 1e3),
                                   "n": 300},
            "cpu": platform.processor(), "torch": torch.__version__,
            "note": "one whole window recomputed per report (no reuse of the previous window's activations)"}


def sizes(model) -> Dict[str, Any]:
    n = M.n_params(model)
    n_ch = sum(len(c.bias) for c in model.convs) + 1
    return {"n_params": n, "float32_bytes": 4 * n, "float16_bytes": 2 * n,
            "int8_bytes_estimate": n + 4 * n_ch + 4 * (len(model.convs) + 1),
            "int8_note": "one byte per weight, a 32-bit bias per output channel and one 32-bit scale per layer; an "
                         "estimate, the int8 network was not built or tested"}


def layer_list(model) -> List[Dict[str, Any]]:
    out = []
    for i, (conv, d) in enumerate(zip(model.convs, model.dilations)):
        out.append({"name": f"conv{i + 1}", "type": "conv1d", "in": conv.in_channels, "out": conv.out_channels,
                    "kernel": conv.kernel_size[0], "dilation": d, "act": "relu",
                    "residual": bool(model.residual and i > 0), "params": conv.weight.numel() + conv.bias.numel(),
                    "weight_shape": list(conv.weight.shape)})
    out.append({"name": "head", "type": "conv1d", "in": model.head.in_channels, "out": 1, "kernel": 1, "dilation": 1,
                "act": "linear (sigmoid gives the probability)", "residual": False,
                "params": model.head.weight.numel() + model.head.bias.numel(),
                "weight_shape": list(model.head.weight.shape)})
    return out


def export_policy(model, done: Dict[str, Any], thr: Dict[str, float], va: Dict[str, np.ndarray],
                  extra: Dict[str, Any]) -> Dict[str, Any]:
    """data/policies/integrity_net_v1.json and its .check.json (windows from VALIDATION streams)."""
    doc = M.to_doc(model, "integrity_net_v1", {
        "thresholds": {"logit_for_1_false_alarm_per_pair_day": thr["day"],
                       "logit_for_1_false_alarm_per_pair_hour": thr["hour"],
                       "note": "set on validation fault-free blocks; a false alarm is a 60 s bin with an alarm"},
        "training": {"task": "B-96 / E56", "seed": done["seed"], "config": done["config"],
                     "loss": "class-balanced binary cross-entropy per step", "class_weights": done["class_weights"],
                     "val_loss": done["val_loss"], **extra}})
    with open(POLICY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, separators=(",", ":"))
        f.write("\n")
    pol = M.Policy(POLICY)
    kinds = va["mf"][:, 0].astype(int)
    obs, what = [], []
    for k, name in enumerate(F.FAULT_TYPES, 1):
        i = int(np.flatnonzero(kinds == k)[0])
        onset, end = int(va["mf"][i, D.META.index("onset")]), int(va["mf"][i, D.META.index("end")])
        for tag, t in (("before the fault", onset - 5), ("in the fault", min(end - 1, onset + 90))):
            w = va["Xf"][i, t - pol.window + 1:t + 1]
            obs.append([[float(f"{float(v):.7g}") for v in row] for row in w])
            what.append(f"{name}: {tag} (validation stream {i}, window ends at step {t})")
    exp = [float(pol(np.array(o))) for o in obs]
    chk = {"format": "lunarsim-policy-check", "version": 1, "policy": "integrity_net_v1", "tolerance": 1e-6,
           "note": "each obs is one window [window_steps][10] of raw features, oldest step first; expected is the "
                   "logit of the float64 reference runtime lunarsim.nn.model.Policy on the policy file",
           "what": what, "obs": obs, "expected": exp}
    with open(POLICY_CHECK, "w", encoding="utf-8", newline="\n") as f:
        json.dump(chk, f, separators=(",", ":"))
        f.write("\n")
    return {"policy_bytes": os.path.getsize(POLICY), "check_bytes": os.path.getsize(POLICY_CHECK),
            "check_windows": len(obs)}


def write_table(res: Dict[str, Any]) -> None:
    cols = ["set", "range_class", "detector", "rate", "fault", "n_events", "recall", "recall_ci_lo", "recall_ci_hi",
            "recall_sd_seeds", "precision_at_1_fault_per_pair_day", "precision_on_fault_streams",
            "delay_median_s", "delay_median_ci_lo", "delay_median_ci_hi",
            "delay_p90_s", "fa_per_pair_day", "window_roc_auc", "window_pr_auc"]
    with open(TABLE, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for sname in ("test", "ood", "ood_recalibrated"):
            if sname not in res:
                continue
            for det in DETECTORS:
                for rate in B.RATES:
                    blk = res[sname][det][rate]
                    for cname in ("all",) + D.CLASSES:
                        evs = blk["events"] if cname == "all" else blk["events_by_class"][cname]
                        fa = (blk["fa_per_pair_day"]["mean"] if cname == "all"
                              else blk["fa_per_pair_day_by_class"].get(cname, float("nan")))
                        for ft in TYPES:
                            e = evs.get(ft)
                            if e is None:
                                continue
                            a = res[sname][det]["window_auc"][ft]
                            w.writerow([sname, cname, det, "1/pair-" + rate, ft, e["n_events"],
                                        round(e["recall"]["mean"], 4), round(e["recall"]["ci95"][0], 4),
                                        round(e["recall"]["ci95"][1], 4), round(e["recall"]["sd_seeds"], 4),
                                        (round(e["precision_at_1_fault_per_pair_day"], 4)
                                         if e["precision_at_1_fault_per_pair_day"] is not None else ""),
                                        round(e["precision_on_fault_streams"]["mean"], 4),
                                        round(e["delay_median_s"]["mean"], 1),
                                        round(e["delay_median_s"]["ci95"][0], 1),
                                        round(e["delay_median_s"]["ci95"][1], 1),
                                        round(e["delay_p90_s"]["mean"], 1), round(fa, 3),
                                        round(a["roc_auc"], 4) if cname == "all" else "",
                                        round(a["pr_auc"], 4) if cname == "all" else ""])


def scores_fingerprint(names: List[str]) -> str:
    """B-118 N21: what a cached score array depends on: the model checkpoints named, the scoring code (baselines,
    model, faults), the baselines' fitted parameters and the dataset's hash."""
    import glob as _g
    import hashlib
    h = hashlib.sha256(D.dataset_sha256().encode())
    files = [os.path.join(os.path.dirname(os.path.abspath(__file__)), f) for f in ("baselines.py", "model.py", "faults.py")]
    files += [BASELINES] + sorted(p for n in names for p in _g.glob(os.path.join(T.STATE, n, "*")) if os.path.isfile(p))
    for p in files:
        h.update(os.path.basename(p).encode())
        with open(p, "rb") as f:
            h.update(f.read().replace(b"\r\n", b"\n") if p.endswith(".py") else f.read())
    return h.hexdigest()[:16]


def main(on: str = "test", force: bool = False, runs: Optional[List[str]] = None, max_s: float = 530.0) -> None:
    t0 = time.time()
    rehearsal = on == "val"
    result_path = RESULT if not rehearsal else os.path.join(T.STATE, "rehearsal_val.json")
    prev = json.load(open(RESULT, encoding="utf-8")) if os.path.isfile(RESULT) else {}
    if not rehearsal and prev.get("test_evaluated") and not force:
        raise SystemExit("the test set was already evaluated (results/E56_integrity.json); --force re-runs the same "
                         "frozen models and thresholds")
    scorers = baseline_scorers()
    models, dones = [], []
    if runs and not rehearsal:
        raise SystemExit("--runs is for the validation rehearsal only")
    for name in (runs or [final_name(s) for s in FINAL_SEEDS]):
        m, d = T.load_model(name)
        models.append(m)
        dones.append(d)
    va = D.load("val")
    wv = va["mn"][:, D.META.index("weight")]

    tag = "rehearsal" if rehearsal else "final"

    fp = scores_fingerprint(runs or [final_name(s) for s in FINAL_SEEDS])

    def all_scores(X: np.ndarray, what: str) -> Dict[str, np.ndarray]:
        """Scores of every detector on one array; saved, so that a run that stops at the time limit resumes."""
        path = os.path.join(T.STATE, f"scores_{tag}_{what}.npz")
        if os.path.isfile(path) and not rehearsal:
            with np.load(path) as z:
                got = {k: z[k] for k in z.files}
            code = str(got.pop("_code")) if "_code" in got else None    # B-118 N21
            if code is None:
                print(f"  {what}: scores cached before B-118 carry no fingerprint; used as they are", flush=True)
            elif code != fp:
                raise SystemExit(f"{path} was made with other models or code ({code} != {fp}); delete it and rescore")
            return got
        if time.time() - t0 > max_s - 200.0 and not rehearsal:
            raise SystemExit(3)
        out = {k: fn(X)[None] for k, fn in scorers.items()}
        out["net"] = np.array([M.score_streams(m, X) for m in models])
        if not rehearsal:
            np.savez(path, _code=np.array(fp), **out)
        print(f"  scored {what} ({time.time() - t0:.0f} s)", flush=True)
        return out

    sv = all_scores(va["Xn"], "val_ff")
    thr = {det: {rate: np.array([B.calibrate(B.bin_max(sv[det][s]), wv, per_day) for s in range(len(sv[det]))])
                 for rate, per_day in B.RATES.items()} for det in DETECTORS}
    val_fa = {det: {rate: float(np.mean([B.fa_per_day(B.bin_max(sv[det][s]), wv, thr[det][rate][s])
                                         for s in range(len(sv[det]))])) for rate in B.RATES} for det in DETECTORS}
    del sv
    res: Dict[str, Any] = {}
    arrays: Dict[str, Any] = {}
    for sname in (("val",) if rehearsal else ("test", "ood")):
        d = D.load(sname)
        sf, sn = all_scores(d["Xf"], sname + "_fault"), all_scores(d["Xn"], sname + "_ff")
        if time.time() - t0 > max_s - 150.0 and not rehearsal:
            raise SystemExit(3)
        r, a = evaluate_set(sf, d["mf"], d["yf"], sn, d["mn"], thr)
        key = "test" if rehearsal else sname
        res[key] = r
        arrays.update({f"{key}__{k}": v for k, v in a.items()})
        res[key]["natural_active_share"] = float(d["pop"][2:].sum() / d["pop"].sum())
        res[key]["natural_uwb_share"] = float(d["pop"][[0, 2]].sum() / d["pop"].sum())
        res[key]["fault_free_pair_days_represented"] = B.pair_days(B.bin_max(sn["chi2_step"][0]),
                                                                   d["mn"][:, D.META.index("weight")])
        res[key]["fault_free_block_hours"] = float(len(d["mn"]) * D.FF_T / 3600.0)
        if sname == "ood":
            # thresholds reset on one half of the OOD fault-free blocks, false alarms counted on the other half
            half = np.arange(len(d["mn"])) % 2 == 0
            wn = d["mn"][:, D.META.index("weight")]
            thr2 = {det: {rate: np.array([B.calibrate(B.bin_max(sn[det][s][half]), wn[half], per_day)
                                          for s in range(len(sn[det]))]) for rate, per_day in B.RATES.items()}
                    for det in DETECTORS}
            r2, a2 = evaluate_set(sf, d["mf"], d["yf"], {k: v[:, ~half] for k, v in sn.items()}, d["mn"][~half], thr2)
            res["ood_recalibrated"] = r2
            arrays.update({f"ood_recalibrated__{k}": v for k, v in a2.items()})
        del sf, sn, d
        print(f"{sname}: evaluated ({time.time() - t0:.0f} s)", flush=True)
    rep, rdone = models[0], dones[0]
    man = json.load(open(D.MANIFEST, encoding="utf-8"))
    pdoc = json.load(open(F.PARAMS_FILE, encoding="utf-8"))
    bdoc = json.load(open(BASELINES, encoding="utf-8"))
    out = {
        "experiment": "E56", "task": "B-96", "what": "is another rover's position report wrong? a small network "
        "against chi-square, CUSUM and logistic regression at the same false-alarm rates",
        "PROVISIONAL": pdoc["status"] == "PROVISIONAL", "params_status": pdoc["status"],
        "params_note": pdoc["status_note"], "params": {k: v["value"] for k, v in pdoc["params"].items()},
        "params_not_in_note_01": pdoc.get("not_in_note_01", []),
        "params_source": {k: v["source"] for k, v in pdoc["params"].items()},
        "ood_setting": pdoc["ood"], "simulated_data": True, "test_evaluated": not rehearsal,
        "dataset_sha256": D.dataset_sha256(), "dataset": {k: {kk: vv for kk, vv in v.items() if "sha" not in kk}
                                                          for k, v in man["splits"].items()},
        "false_alarm_definition": "a 60 s bin of fault-free stream with at least one step above threshold; rates are "
                                  "weighted to the natural share of blocks with and without driving",
        "rates": {"day": "1 false alarm per pair-day", "hour": "1 false alarm per pair-hour"},
        "config": rdone["config"], "seeds": list(FINAL_SEEDS),
        "model": {"architecture": layer_list(rep), "window_s": rep.rf, **sizes(rep),
                  "val_loss_by_seed": [d["val_loss"] for d in dones],
                  "train_wall_s_by_seed": [d["wall_s"] for d in dones]},
        "baselines": {"chi2_window_W": bdoc["chi2_window_W"], "cusum_k": bdoc["cusum_k"], "cusum_ref_s": bdoc["cusum_ref"],
                      "logreg_features": len(bdoc["logreg"]["w"]), "logreg_windows": bdoc["logreg"]["windows"],
                      "tuning_on_validation": bdoc["tuning"], "rule": bdoc["rule"]},
        "thresholds_from_validation": {det: {rate: [float(t) for t in thr[det][rate]] for rate in B.RATES}
                                       for det in DETECTORS},
        "validation_fa_per_pair_day_at_threshold": val_fa,
        "timing": time_inference(rep),
        **res,
    }
    if not rehearsal:
        out["policy_file"] = export_policy(rep, rdone, {r: float(thr["net"][r][0]) for r in B.RATES}, va,
                                           {"dataset_sha256": out["dataset_sha256"],
                                            "PROVISIONAL": out["PROVISIONAL"]})
        if "landscape" in prev:
            out["landscape"] = prev["landscape"]
        np.savez(EVAL_CACHE, **arrays)
        write_table(out)
    out["wall_s"] = round(time.time() - t0, 1)
    with open(result_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    for sname in res:
        print(sname)
        for det in DETECTORS:
            e = res[sname][det]["day"]
            print(f"  {det:12s} FA/day {e['fa_per_pair_day']['mean']:.2f} | " + " | ".join(
                f"{ft} {e['events'][ft]['recall']['mean']:.2f}/{e['events'][ft]['delay_median_s']['mean']:.0f}s"
                for ft in TYPES if ft in e["events"]))
    print("->", result_path, out["wall_s"], "s")


def resample_counts(write: bool = True) -> Dict[str, Any]:
    """B-118 N8: the bootstrap resample counts behind H15's comparisons (h15_block at 1 false alarm per pair-day),
    reproduced from the saved event arrays (EVAL_CACHE) with the same random streams as the published evaluation, and
    checked against the stored intervals. Written to results/E56_integrity.json under a new top-level key; every other
    key is left as it is. A one-sided bootstrap p for 'network shorter' is (at_or_above_0 + 1) / (boot_n + 1)."""
    doc = json.load(open(RESULT, encoding="utf-8"))
    out: Dict[str, Any] = {"note": resample_counts.__doc__.split("\n\n")[0].replace("\n    ", " "), "sets": {}}
    with np.load(EVAL_CACHE) as z:
        for sname in ("test", "ood", "ood_recalibrated"):
            if f"{sname}__kinds" not in z.files or sname not in doc:
                continue
            arr = {k[len(sname) + 2:]: z[k] for k in z.files if k.startswith(sname + "__")}
            blk = h15_block(arr, arr["kinds"])
            stored = doc[sname]["h15_net_against"]
            cnt: Dict[str, Any] = {}
            for base, by in blk.items():
                for ft, r in by.items():
                    for key, v in r.items():
                        if isinstance(v, dict) and "boot_n" in v:
                            s = stored[base][ft][key]
                            cnt[f"{base}|{ft}|{key}"] = {
                                "boot_n": v["boot_n"], "at_or_above_0": v["boot_at_or_above_0"],
                                "at_or_below_0": v["boot_at_or_below_0"],
                                "reproduces_stored_interval": bool(np.allclose(v["ci95"], s["ci95"], equal_nan=True)
                                                                   and np.allclose(v["ci90"], s["ci90"], equal_nan=True))}
            out["sets"][sname] = cnt
    if write:
        doc["h15_resample_counts_b118"] = out
        with open(RESULT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")
    return out


def onset_and_fa_addendum(write: bool = True, sets=("test", "ood")) -> Dict[str, Any]:
    """B-118 N10 and N11, from the saved scores (.cache/nn/scores_final_*.npz) and the stored validation thresholds;
    nothing is retrained or recalibrated, and every existing key of results/E56_integrity.json is left as it is.
    N10: beside each recall (test and out-of-distribution sets, both rates, per fault type and overall), the share of
    events with an alarm already on at the step before onset (baselines.onset_context), and the recall on the events
    with no alarm in the 60 s before onset. N11: the false-alarm interval on all 1,000 resamples (the published one
    used the first 200), with the same resample indices. Every recomputed recall and 200-resample interval is checked
    against the stored value first."""
    doc = json.load(open(RESULT, encoding="utf-8"))
    thr = doc["thresholds_from_validation"]
    out: Dict[str, Any] = {"note": onset_and_fa_addendum.__doc__.replace("\n    ", " "), "sets": {}}
    for sname in sets:
        with np.load(D.cache_path(sname)) as z:
            mf, mn = z["mf"], z["mn"]
        kinds = mf[:, 0].astype(int)
        wn = mn[:, D.META.index("weight")]
        blk: Dict[str, Any] = {}
        for det in DETECTORS:
            with np.load(os.path.join(T.STATE, f"scores_final_{sname}_fault.npz")) as z:
                sf = z[det]
            blk[det] = {}
            for rate in B.RATES:
                S = len(sf)
                res = [B.detect(sf[s], mf, float(thr[det][rate][s])) for s in range(S)]
                ctx = [B.onset_context(sf[s], mf, float(thr[det][rate][s])) for s in range(S)]
                stored = doc[sname][det][rate]["events"]
                ev = {}
                for k, name in list(enumerate(F.FAULT_TYPES, 1)) + [(0, "all")]:
                    sel = (kinds == k) if k else (kinds > 0)
                    rec = float(np.mean([res[s][0][sel].mean() for s in range(S)]))
                    on = float(np.mean([ctx[s][0][sel].mean() for s in range(S)]))
                    q = [ctx[s][1] & sel for s in range(S)]
                    rq = [res[s][0][q[s]].mean() for s in range(S) if q[s].any()]
                    ev[name] = {"recall": rec, "recall_reproduces_stored": bool(abs(rec - stored[name]["recall"]["mean"]) < 1e-9),
                                "share_alarm_on_at_onset": on, "recall_quiet_60s_before": float(np.mean(rq)) if rq else None,
                                "events_quiet_60s_before_mean": float(np.mean([q[s].sum() for s in range(S)])),
                                "events": int(sel.sum())}
                    ev[name]["share_alarm_in_60s_before"] = 1.0 - ev[name]["events_quiet_60s_before_mean"] / ev[name]["events"]
                blk[det][rate] = {"events": ev}
            del sf
            with np.load(os.path.join(T.STATE, f"scores_final_{sname}_ff.npz")) as z:
                sn = z[det]
            bms = [B.bin_max(sn[s]) for s in range(len(sn))]
            del sn
            for rate in B.RATES:
                S = len(bms)
                rng = np.random.default_rng([D.MASTER_SEED, 11, 0])          # evaluate_set's stream, seed 0
                idx = rng.integers(0, len(wn), (N_BOOT, len(wn)))
                per = np.array([[B.fa_per_day(bms[s][i], wn[i], float(thr[det][rate][s])) for i in idx]
                                for s in range(S)])                         # [S, 1000]
                b200, b1000 = per[:, :200].mean(0), per.mean(0)
                st = doc[sname][det][rate]["fa_per_pair_day"]["ci95"]
                blk[det][rate]["fa_per_pair_day_ci95_1000"] = _ci(b1000)
                blk[det][rate]["fa_ci95_200_reproduces_stored"] = bool(np.allclose(_ci(b200), st, equal_nan=True))
            print(f"{sname} {det} done", flush=True)
        out["sets"][sname] = blk
    if write:
        doc["onset_context_and_fa_interval_b118"] = out
        with open(RESULT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, indent=1)
            f.write("\n")
    return out


if __name__ == "__main__":
    if "--onset-fa" in sys.argv:
        r = onset_and_fa_addendum()
        bad = [(s, d, rt, ft) for s, b in r["sets"].items() for d, x in b.items() for rt, y in x.items()
               for ft, e in y["events"].items() if not e["recall_reproduces_stored"]]
        bad += [(s, d, rt, "fa") for s, b in r["sets"].items() for d, x in b.items() for rt, y in x.items()
                if not y["fa_ci95_200_reproduces_stored"]]
        print("not reproduced:", bad)
        raise SystemExit(0)
    if "--resample-counts" in sys.argv:
        r = resample_counts()
        print({s: sum(not v["reproduces_stored_interval"] for v in c.values()) for s, c in r["sets"].items()},
              "comparisons not reproduced")
        raise SystemExit(0)
    ap = argparse.ArgumentParser()
    ap.add_argument("--on", default="test", choices=("test", "val"))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--runs", default="", help="rehearsal only: comma-separated run names instead of the finals")
    ap.add_argument("--max-seconds", type=float, default=530.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    main(a.on, a.force, [r for r in a.runs.split(",") if r] or None, a.max_seconds)
