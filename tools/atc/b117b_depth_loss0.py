"""B-117 (b), P1 S11: the auction's bundle depths 2 and 5 without message loss.

    python tools/atc/b117b_depth_loss0.py run     # resumable, cached in .cache/atc/b117b.json (--max-seconds 520)
    python tools/atc/b117b_depth_loss0.py table   # -> results/B117b_depth_loss0.json (a new file)

E41's design (30 % load, block v1, seeds 1-30, dispatch fixed point) has C_AUCTION at depth 2 and 5 only at loss 0.25
and 0.40, so P1 could not say how much of the depth penalty is due to loss. Two new cells, defined as E41 defines its
depth cells: C_AUCTION depth 2 loss 0 and depth 5 loss 0. Two of E41's own cells are repeated on the current code as a
check that the stored E41 rows (results/E41_runs.lead.csv) can be paired with the new ones: C_AUCTION loss 0 (depth 1)
and C_AUCTION depth 5 loss 0.25. Comparisons (paired by seed, E41's bootstrap: analyse_e41_pairs.paired): depth d
minus depth 1 at loss 0, 0.25 and 0.40, and the part due to loss, (depth d - depth 1 at loss L) - (depth d - depth 1
at loss 0). Pre-declared in the B-117 estimate (13 Nov); not PREREG cells.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from experiments.phase5 import run_phase5 as R  # noqa: E402
from experiments.phase5 import analyse_e41_pairs as P  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "b117b.json")
OUT = os.path.join(ROOT, "results", "B117b_depth_loss0.json")
NEW = {"C_AUCTION depth 2 loss 0": {"loss": 0.0, "depth": 2}, "C_AUCTION depth 5 loss 0": {"loss": 0.0, "depth": 5}}
CHECK = {"C_AUCTION loss 0": {"loss": 0.0}, "C_AUCTION depth 5 loss 0.25": {"loss": 0.25, "depth": 5}}
CELLS = dict(NEW, **CHECK)
KEEP = ("atc_urgent_wait_mean_cens_h", "atc_urgent_wait_p95_cens_h", "atc_urgent_within24_share", "delivered_kg",
        "atc_claims_stale", "atc_claims_won", "atc_wasted_trips", "atc_msgs_lost", "atc_rallies")
FIXPOINT = True


def code_fingerprint():
    import run_e50 as E5
    return E5.code_fingerprint() + "+fixpoint"


def cmd_run(max_s):
    t0, last = time.time(), 15.0
    done = json.load(open(CACHE, encoding="utf-8")) if os.path.isfile(CACHE) else {}
    fp = code_fingerprint()
    if done and done.get("_code") != fp:
        raise SystemExit(f"{CACHE} was made with other code ({done.get('_code')} != {fp}); delete it and rerun")
    done["_code"] = fp
    for lab, kw in CELLS.items():
        c = R.cell("E41", lab, "C_AUCTION", dict(kw), block="v1")
        for seed in R.V1_SEEDS:
            k = f"{lab}|{seed}"
            if k in done:
                continue
            if time.time() - t0 > max_s - max(60, 1.5 * last):
                print(f"run: time limit, {len(done) - 1} done; rerun", flush=True)
                return
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = R.run_one(c, seed, None, fixpoint=FIXPOINT)
            last = r["run_s"]
            done[k] = {m: float(r[m]) for m in KEEP}
            with open(CACHE + ".tmp", "w", encoding="utf-8") as f:
                json.dump(done, f, allow_nan=False)
            os.replace(CACHE + ".tmp", CACHE)
            print(f"  {k}: {done[k]['atc_urgent_wait_mean_cens_h']:.2f} h, stale {done[k]['atc_claims_stale']:.0f} "
                  f"({last} s)", flush=True)
    print("run: done", flush=True)


def cmd_table():
    import pandas as pd
    done = json.load(open(CACHE, encoding="utf-8"))
    fp = code_fingerprint()
    if done.get("_code") != fp:
        raise SystemExit(f"{CACHE} was made with other code ({done.get('_code')} != {fp}); rerun")
    missing = [f"{lab}|{s}" for lab in CELLS for s in R.V1_SEEDS if f"{lab}|{s}" not in done]
    if missing:
        raise SystemExit(f"{len(missing)} runs missing, e.g. {missing[:3]}; run first")
    e = P.load()
    new = {lab: pd.DataFrame([dict(seed=s, **done[f"{lab}|{s}"]) for s in R.V1_SEEDS]) for lab in CELLS}
    check = {}
    for lab in CHECK:
        st = e[e["label"] == lab].set_index("seed")
        check[lab] = {m: float(np.max(np.abs(new[lab][m].to_numpy() - np.array([float(st.loc[s, m]) for s in R.V1_SEEDS]))))
                      for m in KEEP}
    reproduced = all(v == 0.0 for c in check.values() for v in c.values())
    if not reproduced:
        raise SystemExit(f"the repeated E41 cells differ from results/E41_runs.lead.csv: {check}")
    cell = lambda lab: new[lab] if lab in NEW else e[e["label"] == lab][["seed"] + list(KEEP)]
    d1 = {"0": "C_AUCTION loss 0", "0.25": "C_AUCTION loss 0.25", "0.4": "C_AUCTION loss 0.4"}
    dd = lambda depth, L: f"C_AUCTION depth {depth} loss {L}"
    out = {"task": "B-117 (b), P1 S11: bundle depths 2 and 5 at loss 0", "note": __doc__.split("\n\n")[1].strip(),
           "seeds": list(R.V1_SEEDS), "code": fp, "repeated_E41_cells_max_abs_diff": check,
           "repeated_E41_cells_reproduce": reproduced,
           "cells": {lab: {m: round(float(cell(lab)[m].mean()), 4) for m in KEEP}
                     for lab in list(d1.values()) + [dd(k, L) for k in (2, 5) for L in ("0", "0.25", "0.4")]},
           "depth_minus_depth1": {}, "part_due_to_loss": {}}
    for i, (depth, L) in enumerate([(k, L) for k in (2, 5) for L in ("0", "0.25", "0.4")]):
        for m in (P.PRIMARY, "atc_claims_stale"):
            r = P.paired(cell(dd(depth, L)), cell(d1[L]), m, np.random.default_rng([P.SEED, 117, i]))
            out["depth_minus_depth1"].setdefault(m, {})[f"depth {depth} - depth 1, loss {L}"] = {
                k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()
                if k in ("n", "mean", "lo", "hi", "lo90", "hi90", "p", "b_mean")}
    for i, (depth, L) in enumerate([(k, L) for k in (2, 5) for L in ("0.25", "0.4")]):
        m = P.PRIMARY
        a = cell(dd(depth, L))[["seed", m]].merge(cell(d1[L])[["seed", m]], on="seed", suffixes=("", "_1"))
        b = cell(dd(depth, "0"))[["seed", m]].merge(cell(d1["0"])[["seed", m]], on="seed", suffixes=("", "_1"))
        x = pd.DataFrame({"seed": a["seed"], m: a[m] - a[m + "_1"]})
        y = pd.DataFrame({"seed": b["seed"], m: b[m] - b[m + "_1"]})
        r = P.paired(x, y, m, np.random.default_rng([P.SEED, 117, 100 + i]))
        out["part_due_to_loss"][f"depth {depth}, loss {L}"] = {
            k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()
            if k in ("n", "mean", "lo", "hi", "lo90", "hi90", "p", "b_mean")}
    out["part_due_to_loss_note"] = ("(depth d - depth 1 at loss L) - (depth d - depth 1 at loss 0), per seed; b_mean "
                                    "is the mean depth penalty at loss 0 (the part not due to loss)")
    text = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with open(OUT + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(OUT + ".tmp", OUT)
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--max-seconds", type=float, default=520.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    cmd_run(a.max_seconds) if a.cmd == "run" else cmd_table()
