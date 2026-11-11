"""The integrity dataset: deterministic builder, splits and loader (documented in data/atc/integrity/README.md).

    python -m lunarsim.nn.dataset --split train|val|test|ood|all [--max-seconds 520]

Split by what we generalise to, twice over:
  simulator seed (one seed = one simulated month, both runs "with" and "without" of that seed):
      train 1-6, val 7-9, test 10-13, ood 14-17;
  vehicle pair (unordered pair {i, j}, by |i - j|): train {1, 4, 5}, val {2, 6}, test and ood {3, 7}.
So no pair-month, no seed and no pair is in two splits (test and ood share the pair group, not the seeds).

Streams (1 Hz; every stream starts with PRE unscored warm-up steps). A window is "active" if A or B drives in it
and "static" if nobody does; its ranging class is "uwb" if at least half of its in-range steps are within the UWB
range, else "long" (the long-range base radio):
  fault streams      PRE + 1200 s, exactly one fault of 120-600 s; 70 % active windows (driving for at least 60 s,
                     in range at least half the time), 30 % static (in range all the time), each half uwb, half long
                     where the trace has enough of both; frozen-report faults only where B drives (the report is
                     not wrong while B stands);
  fault-free design  (train only) the same kinds of window without a fault;
  fault-free natural (val, test, ood) PRE + 3600 s blocks for false-alarm rates, the same number from each of the
                     four strata (active or static) x (uwb or long), each block carrying the weight that restores the
                     natural share of its stratum in that split (a stratified estimate of the rate per pair-day of
                     natural operation; blocks in which the pair is never in radio range are not pair time).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import faults as F
from . import tracks as TR

ROOT = TR.ROOT
DATA_DIR = os.path.join(ROOT, "data", "atc", "integrity")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
MANIFEST = os.path.join(DATA_DIR, "manifest.json")
MASTER_SEED = 56
SPLIT_SEEDS = {"train": (1, 2, 3, 4, 5, 6), "val": (7, 8, 9), "test": (10, 11, 12, 13), "ood": (14, 15, 16, 17)}
SPLIT_ID = {"train": 0, "val": 1, "test": 2, "ood": 3}
PAIR_DIFFS = {"train": (1, 4, 5), "val": (2, 6), "test": (3, 7), "ood": (3, 7)}
RUNS = ("with", "without")
PRE = 256                      # warm-up steps at the start of every stream (never scored, never trained on)
FAULT_T = 1200                 # scored length of a fault stream
FF_T = 3600                    # scored length of a natural fault-free block
ACTIVE_SHARE = 0.7
# per trace: fault streams per type, fault-free design streams (train), natural fault-free blocks per stratum
QUOTA = {"train": {"fault": 60, "ff_design": 84, "ff_natural": 0},
         "val": {"fault": 34, "ff_design": 0, "ff_natural": 25},
         "test": {"fault": 50, "ff_design": 0, "ff_natural": 19},
         "ood": {"fault": 50, "ff_design": 0, "ff_natural": 19}}
META = ("kind", "ctx", "seed", "run", "a", "b", "start", "onset", "end", "mag", "dir", "weight", "cls", "uwb_share")
CLASSES = ("uwb", "long")      # meta column cls: 0 = UWB, 1 = long-range base radio
ONSET_LEAD = (60, 400)         # the fault starts this many scored seconds into the stream (uniform)


def pairs_of(split: str, n_vehicles: int = 8) -> List[Tuple[int, int]]:
    """Ordered pairs (observer A, sender B) of a split."""
    out = []
    for i in range(n_vehicles):
        for j in range(n_vehicles):
            if i != j and abs(i - j) in PAIR_DIFFS[split]:
                out.append((i, j))
    return out


def _rng(*key: int) -> np.random.Generator:
    return np.random.default_rng(np.random.SeedSequence([MASTER_SEED, *[int(k) for k in key]]))


def _windows(n_total: int, length: int) -> np.ndarray:
    """Start indices of the non-overlapping windows of a month."""
    return np.arange(F.LEAD, n_total - length, length)


def _win_sum(c: np.ndarray, starts: np.ndarray, length: int) -> np.ndarray:
    return c[starts + length] - c[starts]


def _plan(n: int, frozen: bool) -> List[Tuple[int, int]]:
    """(ctx, cls) of the n fault streams of one type in one trace."""
    n_act = n if frozen else int(round(ACTIVE_SHARE * n))
    out = [(1, i % 2) for i in range(n_act)] + [(0, i % 2) for i in range(n - n_act)]
    return out


def build_trace(split: str, seed: int, run: str, quota: Optional[Dict[str, int]] = None,
                t_limit_s: Optional[int] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """All streams of one trace of a split. Returns arrays Xf, yf, mf (fault + design fault-free streams) and
    Xn, mn (natural fault-free blocks) plus the population counts of the four natural strata."""
    quota = quota or QUOTA[split]
    ood = split == "ood"
    p = F.true_params(params or F.load_params(), ood)
    sid, rid = SPLIT_ID[split], RUNS.index(run)
    tr = TR.vehicle_tracks(TR.load_trace(TR.trace_path(seed, run)), t_limit_s or 0)
    xy, moving, ant = tr["xy"], tr["moving"], tr["antenna_m"]
    V, T = moving.shape
    nav = [F.nav_error(xy[v], moving[v], p, _rng(1, seed, rid, v, int(ood))) for v in range(V)]
    prs = pairs_of(split, V)
    Lf, Ln = PRE + FAULT_T, PRE + FF_T
    sf, sn = _windows(T, Lf), _windows(T, Ln)
    cand_f: List[Tuple[int, ...]] = []      # (a, b, start, ctx, b_active, cls)
    cand_n: List[Tuple[int, ...]] = []      # (a, b, start, stratum = 2 ctx + cls)
    cache: Dict[Tuple[int, int], Any] = {}
    limit = {}
    for a, b in prs:
        key = (min(a, b), max(a, b))
        limit[(a, b)] = F.range_limit_m(ant[a], ant[b], p)
        if key not in cache:
            d = np.hypot(xy[a, :, 0] - xy[b, :, 0], xy[a, :, 1] - xy[b, :, 1])
            cache[key] = (np.r_[0, np.cumsum(d <= limit[(a, b)])], np.r_[0, np.cumsum(d <= p["uwb_range_max_m"])])
        c_in, c_uwb = cache[key]
        c_any = np.r_[0, np.cumsum(moving[a] | moving[b])]
        c_b = np.r_[0, np.cumsum(moving[b])]
        n_in, mv, mvb = _win_sum(c_in, sf, Lf), _win_sum(c_any, sf, Lf), _win_sum(c_b, sf, Lf)
        cls = (_win_sum(c_uwb, sf, Lf) < 0.5 * np.maximum(n_in, 1)).astype(int)
        act = (mv >= 60) & (n_in >= 0.5 * Lf)
        sta = (mv == 0) & (n_in >= Lf)
        for i in np.flatnonzero(act | sta):
            cand_f.append((a, b, int(sf[i]), int(act[i]), int(mvb[i] >= 60 and act[i]), int(cls[i])))
        n_in, mv = _win_sum(c_in, sn, Ln), _win_sum(c_any, sn, Ln)
        cls = (_win_sum(c_uwb, sn, Ln) < 0.5 * np.maximum(n_in, 1)).astype(int)
        for i in np.flatnonzero(n_in > 0):
            cand_n.append((a, b, int(sn[i]), 2 * int(mv[i] > 0) + int(cls[i])))
    cf = np.array(cand_f, np.int64).reshape(-1, 6)
    cn = np.array(cand_n, np.int64).reshape(-1, 4)
    sel = _rng(2, sid, seed, rid)
    cf = cf[sel.permutation(len(cf))]
    cn = cn[sel.permutation(len(cn))]
    used = np.zeros(len(cf), bool)
    counter = [0]

    def stream(a: int, b: int, start: int, length: int, fault=None):
        sl = slice(start - F.LEAD, start + length)
        counter[0] += 1
        return F.pair_stream(xy[a][sl], xy[b][sl], nav[a][0][sl], nav[b][0][sl], nav[a][1][sl], nav[b][1][sl],
                             nav[a][2][sl], p, _rng(3, sid, seed, rid, counter[0]), fault, limit[(a, b)])

    def take(ctx: int, need_b: bool, cls: int) -> Optional[int]:
        ok = (~used) & (cf[:, 3] == ctx) & ((cf[:, 4] == 1) | (not need_b))
        for c in (cls, 1 - cls):                        # the other class if this one has run out
            idx = np.flatnonzero(ok & (cf[:, 5] == c))
            if len(idx):
                used[idx[0]] = True
                return int(idx[0])
        return None

    def dists(a: int, b: int, start: int, length: int) -> np.ndarray:
        return np.hypot(*(xy[b][start:start + length].astype(np.float64)
                          - xy[a][start:start + length].astype(np.float64)).T)

    Xf, yf, mf = [], [], []
    for kind, name in enumerate(F.FAULT_TYPES, start=1):
        for ctx, cls in _plan(quota["fault"], name == "frozen"):
            done = False
            while not done:
                ci = take(ctx, name == "frozen", cls)
                if ci is None:
                    break
                a, b, start = int(cf[ci, 0]), int(cf[ci, 1]), int(cf[ci, 2])
                d = dists(a, b, start, Lf)
                inr = d <= limit[(a, b)]
                pb = xy[b][start:start + Lf].astype(np.float64)
                er = _rng(4, sid, seed, rid, ci)
                for _try in range(20):
                    onset = PRE + int(er.integers(*ONSET_LEAD))
                    end = onset + int(er.integers(F.EVENT_S[0], F.EVENT_S[1] + 1))
                    if not inr[onset] or inr[onset:end].mean() < 0.5:
                        continue
                    if name == "frozen":
                        if not moving[b][start + onset]:
                            continue
                        if np.hypot(*(pb[onset:end] - pb[onset]).T).max() < F.FROZEN_MIN_MOVE_M:
                            continue
                    mag, direction = F.sample_fault(name, er, ood)
                    X, y, _ = stream(a, b, start, Lf, (name, onset, end, mag, direction))
                    ev = inr[onset:end]
                    share = float((d[onset:end][ev] <= p["uwb_range_max_m"]).mean())
                    Xf.append(X)
                    yf.append(y)
                    mf.append((kind, ctx, seed, rid, a, b, start, onset, end, mag, direction, 1.0,
                               int(share < 0.5), share))
                    done = True
                    break
    for ctx, cls in _plan(quota["ff_design"], False):
        ci = take(ctx, False, cls)
        if ci is None:
            continue
        a, b, start = int(cf[ci, 0]), int(cf[ci, 1]), int(cf[ci, 2])
        X, y, _ = stream(a, b, start, Lf)
        d = dists(a, b, start, Lf)
        inr = d <= limit[(a, b)]
        share = float((d[inr] <= p["uwb_range_max_m"]).mean())
        Xf.append(X)
        yf.append(y)
        mf.append((0, ctx, seed, rid, a, b, start, -1, -1, 0.0, 0.0, 1.0, int(share < 0.5), share))
    Xn, mn = [], []
    pop = [int((cn[:, 3] == s).sum()) for s in range(4)] if len(cn) else [0, 0, 0, 0]
    for stratum in range(4):
        idx = np.flatnonzero(cn[:, 3] == stratum)[:quota["ff_natural"]] if len(cn) else []
        for ci in idx:
            a, b, start = int(cn[ci, 0]), int(cn[ci, 1]), int(cn[ci, 2])
            X, _, _ = stream(a, b, start, Ln)
            d = dists(a, b, start, Ln)
            inr = d <= limit[(a, b)]
            share = float((d[inr] <= p["uwb_range_max_m"]).mean())
            Xn.append(X)
            mn.append((0, stratum // 2, seed, rid, a, b, start, -1, -1, 0.0, 0.0, 1.0, stratum % 2, share))
    nf = len(F.FEATURES)
    return {"Xf": np.array(Xf, np.float32).reshape(-1, Lf, nf), "yf": np.array(yf, np.uint8).reshape(-1, Lf),
            "mf": np.array(mf, np.float64).reshape(-1, len(META)),
            "Xn": np.array(Xn, np.float32).reshape(-1, Ln, nf), "mn": np.array(mn, np.float64).reshape(-1, len(META)),
            "pop": np.array(pop, np.float64)}


def stratum_of(meta: np.ndarray) -> np.ndarray:
    return (2 * meta[:, META.index("ctx")] + meta[:, META.index("cls")]).astype(int)


def finish(parts: List[Dict[str, Any]]) -> Dict[str, np.ndarray]:
    """Join the traces of a split and set the natural-mix weights of the fault-free blocks."""
    out = {k: np.concatenate([q[k] for q in parts]) for k in ("Xf", "yf", "mf", "Xn", "mn")}
    pop = np.sum([q["pop"] for q in parts], axis=0).astype(float)
    mn = out["mn"]
    if len(mn) and pop.sum() > 0:
        st = stratum_of(mn)
        present = np.array([(st == s).any() for s in range(4)])
        share = pop * present / (pop * present).sum()           # a stratum with no sampled block cannot be weighted
        for s in range(4):
            if present[s]:
                mn[st == s, META.index("weight")] = share[s] / ((st == s).sum() / len(mn))
    out["pop"] = pop
    return out


def score_mask(y: np.ndarray, meta: np.ndarray) -> np.ndarray:
    """Steps that are scored and trained on: not the warm-up, not the guard after a fault ends."""
    m = np.ones(y.shape, bool)
    m[:, :PRE] = False
    end = meta[:, META.index("end")].astype(int)
    for i in np.flatnonzero(end >= 0):
        m[i, end[i]:end[i] + F.GUARD_S] = False
    return m


def _sha(a: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()


def digest(d: Dict[str, np.ndarray]) -> Dict[str, Any]:
    mf, mn = d["mf"], d["mn"]
    cls = mf[:, META.index("cls")].astype(int)
    stn = stratum_of(mn) if len(mn) else np.zeros(0, int)
    names = ("static_uwb", "static_long", "active_uwb", "active_long")
    return {"fault_streams": int((mf[:, 0] > 0).sum()),
            "fault_streams_by_type": {n: int((mf[:, 0] == k).sum()) for k, n in enumerate(F.FAULT_TYPES, 1)},
            "fault_streams_by_type_and_class": {n: {c: int(((mf[:, 0] == k) & (cls == ci)).sum())
                                                    for ci, c in enumerate(CLASSES)}
                                                for k, n in enumerate(F.FAULT_TYPES, 1)},
            "fault_free_design_streams": int((mf[:, 0] == 0).sum()),
            "fault_free_natural_blocks": int(len(mn)),
            "natural_blocks_by_stratum": {n: int((stn == s).sum()) for s, n in enumerate(names)},
            "natural_population_blocks": {n: float(d["pop"][s]) for s, n in enumerate(names)},
            "natural_active_share": float(d["pop"][2:].sum() / max(d["pop"].sum(), 1.0)),
            "natural_uwb_share": float(d["pop"][[0, 2]].sum() / max(d["pop"].sum(), 1.0)),
            "shape_Xf": list(d["Xf"].shape), "shape_Xn": list(d["Xn"].shape),
            "sha256": {k: _sha(d[k]) for k in ("Xf", "yf", "mf", "Xn", "mn")}}


def cache_path(split: str) -> str:
    return os.path.join(CACHE_DIR, f"{split}.npz")


def build_split(split: str, max_s: float = 520.0) -> bool:
    """Build one split trace by trace (each trace is saved, so a stopped run resumes), then join and digest."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    t0, last = time.time(), 30.0
    parts = []
    for seed in SPLIT_SEEDS[split]:
        for run in RUNS:
            part = os.path.join(CACHE_DIR, f"part_{split}_{seed:02d}_{run}.npz")
            if not os.path.isfile(part):
                if time.time() - t0 > max_s - 2.0 * last - 30.0:
                    print(f"{split}: time limit; rerun to continue", flush=True)
                    return False
                t = time.time()
                q = build_trace(split, seed, run)
                np.savez(part, **{k: np.asarray(v) for k, v in q.items()})
                last = time.time() - t
                print(f"  {split} seed {seed} {run}: {len(q['Xf'])} streams, {len(q['Xn'])} blocks, pop {q['pop']} "
                      f"({last:.0f} s)", flush=True)
            with np.load(part) as z:
                parts.append({k: z[k] for k in z.files})
    d = finish(parts)
    np.savez(cache_path(split), **d)
    man = json.load(open(MANIFEST, encoding="utf-8")) if os.path.isfile(MANIFEST) else {}
    pdoc = json.load(open(F.PARAMS_FILE, encoding="utf-8"))
    man.update({"format": "lunarsim-integrity-manifest", "version": 1, "master_seed": MASTER_SEED,
                "features": list(F.FEATURES), "meta_columns": list(META), "pre_s": PRE, "guard_s": F.GUARD_S,
                "numpy": np.__version__, "params_status": pdoc["status"],
                "params_sha256": hashlib.sha256(open(F.PARAMS_FILE, "rb").read()).hexdigest()})
    man.setdefault("splits", {})[split] = {
        "seeds": list(SPLIT_SEEDS[split]), "pair_abs_id_difference": list(PAIR_DIFFS[split]),
        "ordered_pairs": len(pairs_of(split)),
        "traces_sha256": {f"seed{s:02d}/{r}": hashlib.sha256(open(TR.trace_path(s, r), "rb").read()).hexdigest()
                          for s in SPLIT_SEEDS[split] for r in RUNS}, **digest(d)}
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as f:
        json.dump(man, f, indent=1)
        f.write("\n")
    for seed in SPLIT_SEEDS[split]:
        for run in RUNS:
            os.remove(os.path.join(CACHE_DIR, f"part_{split}_{seed:02d}_{run}.npz"))
    print(f"{split}: done, {json.dumps({k: v for k, v in man['splits'][split].items() if 'sha' not in k})}", flush=True)
    return True


def load(split: str) -> Dict[str, np.ndarray]:
    """A built split: Xf, yf, mf, Xn, mn, pop (build it first: python -m lunarsim.nn.dataset --split ...)."""
    path = cache_path(split)
    if not os.path.isfile(path):
        raise SystemExit(f"{path} is missing; run: python -m lunarsim.nn.dataset --split {split}")
    with np.load(path) as z:
        return {k: z[k] for k in z.files}


def dataset_sha256() -> str:
    """One hash for the whole dataset: over the manifest's per-split array hashes, in split order."""
    man = json.load(open(MANIFEST, encoding="utf-8"))
    h = hashlib.sha256()
    for split in ("train", "val", "test", "ood"):
        for k in ("Xf", "yf", "mf", "Xn", "mn"):
            h.update(man["splits"][split]["sha256"][k].encode())
    return h.hexdigest()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="all")
    ap.add_argument("--max-seconds", type=float, default=520.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 20.0, exit=True)
    t_start = time.time()
    for s in (("train", "val", "test", "ood") if a.split == "all" else (a.split,)):
        if not build_split(s, a.max_seconds - (time.time() - t_start)):
            sys.exit(3)
