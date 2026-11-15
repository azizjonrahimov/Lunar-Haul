"""B-117 (a), P1 S3: the full-information marketplace (O_ORACLE) with the auction's own return-to-coverage move.

    python tools/atc/b117a_oracle_rally.py run     # resumable, cached in .cache/atc/b117a.json (--max-seconds 520)
    python tools/atc/b117a_oracle_rally.py table   # -> results/B117a_oracle_rally.json (a new file)

E40 at 30 % load, block v1 (seeds 1-30, start year 2028 + seed mod 4), with the dispatch fixed point as E40 runs since
PREREG change 5 (run_phase5 --fixpoint) and E40's own regime arguments (C_AUCTION at loss LOSS = 0.10). All four cells
run on the current code with the same seeds, so every comparison is paired:
- O_ORACLE and C_AUCTION: E40's cells, repeated on the current code (compared with results/E40_runs.csv as a check);
- O + rally (unheard): O_ORACLE, and an idle robot that no radio path links to the BASE mast drives to the nearest
  site the mast sees (to BASE while the base is down): the trigger and the move of C_AUCTION's lost-link rule
  (regimes o_rally="unheard");
- O + rally (all idle): the B-75 diagnostic cell (o_rally=True: every idle robot at a site the mast does not see
  moves), repeated on the current code for comparison with results/ATC_oracle_diag.json.
Pre-declared (B-117 estimate, 13 Nov): the cells, the seeds and the comparison (urgent wait, censored mean, paired
bootstrap over seeds). Not PREREG cells. Single process.
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
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from experiments.phase5 import run_phase5 as R  # noqa: E402
from experiments.phase5.analyse_e40 import boot  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "b117a.json")
OUT = os.path.join(ROOT, "results", "B117a_oracle_rally.json")
_E40 = {lab: kw for lab, _, kw in R.REGIMES_E40}
CELLS = {"O_ORACLE": ("O_ORACLE", dict(_E40["O_ORACLE"])), "C_AUCTION": ("C_AUCTION", dict(_E40["C_AUCTION"])),
         "O + rally (unheard)": ("O_ORACLE", dict(_E40["O_ORACLE"], o_rally="unheard")),
         "O + rally (all idle)": ("O_ORACLE", dict(_E40["O_ORACLE"], o_rally=True))}
FIXPOINT = True                                           # as E40's rows (dispatch_fixpoint = 1)
KEEP = ("atc_urgent_wait_mean_cens_h", "atc_deadhead_share", "atc_rallies", "delivered_kg", "atc_urgent_within24_share")
PAIRS = (("O + rally (unheard)", "O_ORACLE"), ("C_AUCTION", "O_ORACLE"), ("C_AUCTION", "O + rally (unheard)"),
         ("O + rally (all idle)", "O_ORACLE"), ("O + rally (unheard)", "O + rally (all idle)"))


def code_fingerprint():
    import run_e50 as E5                                  # every lunarsim file an engine run uses, and run_phase5
    return E5.code_fingerprint() + ("+fixpoint" if FIXPOINT else "")


def cmd_run(max_s):
    t0, last = time.time(), 15.0
    done = json.load(open(CACHE, encoding="utf-8")) if os.path.isfile(CACHE) else {}
    fp = code_fingerprint()
    if done and done.get("_code") != fp:
        raise SystemExit(f"{CACHE} was made with other code ({done.get('_code')} != {fp}); delete it and rerun")
    done["_code"] = fp
    for lab, (reg, kw) in CELLS.items():
        c = R.cell("B117A", lab, reg, kw, load="30", block="v1")
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
            done[k]["start_year"] = int(r["start_year"]) if "start_year" in r else None
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            with open(CACHE + ".tmp", "w", encoding="utf-8") as f:
                json.dump(done, f, allow_nan=False)
            os.replace(CACHE + ".tmp", CACHE)
            print(f"  {k}: {done[k]['atc_urgent_wait_mean_cens_h']:.2f} h, {done[k]['atc_rallies']:.0f} rallies "
                  f"({last} s)", flush=True)
    print("run: done", flush=True)


def cmd_table():
    done = json.load(open(CACHE, encoding="utf-8"))
    fp = code_fingerprint()
    if done.get("_code") != fp:
        raise SystemExit(f"{CACHE} was made with other code ({done.get('_code')} != {fp}); rerun")
    missing = [f"{lab}|{s}" for lab in CELLS for s in R.V1_SEEDS if f"{lab}|{s}" not in done]
    if missing:
        raise SystemExit(f"{len(missing)} runs missing, e.g. {missing[:3]}; run first")
    import pandas as pd
    e = pd.read_csv(os.path.join(ROOT, "results", "E40_runs.csv"), float_precision="round_trip")
    e = e[(e["load"] == 30) & (e["start_year"] == 2028 + e["seed"] % 4)]
    series = {lab: {m: np.array([done[f"{lab}|{s}"][m] for s in R.V1_SEEDS]) for m in KEEP} for lab in CELLS}
    out = {"task": "B-117 (a), P1 S3: the marketplace with the auction's return-to-coverage move",
           "note": __doc__.split("\n\n")[2].strip(), "seeds": list(R.V1_SEEDS), "code": fp,
           "cells": {lab: {m: round(float(v.mean()), 4) for m, v in ser.items()} for lab, ser in series.items()},
           "pairs_urgent_wait_h": {}, "reproduces_E40_runs": {}, "b75_cells": None}
    m = "atc_urgent_wait_mean_cens_h"
    for a, b in PAIRS:
        out["pairs_urgent_wait_h"][f"{a} - {b}"] = boot(series[a][m] - series[b][m])
    for lab in ("O_ORACLE", "C_AUCTION"):                 # the HEAD repeats against E40's stored rows
        rows = e[e["label"] == lab].set_index("seed")
        diff = {k: float(np.max(np.abs(series[lab][k] - np.array([float(rows.loc[s][k]) for s in R.V1_SEEDS]))))
                for k in KEEP}
        out["reproduces_E40_runs"][lab] = {"max_abs_diff": diff, "equal": all(v == 0.0 for v in diff.values())}
    p = os.path.join(ROOT, "results", "ATC_oracle_diag.json")
    if os.path.isfile(p):
        out["b75_cells"] = json.load(open(p, encoding="utf-8"))["cells"]
    text = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with open(OUT + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(OUT + ".tmp", OUT)
    print(text)


if __name__ == "__main__":
    sys.path.insert(0, HERE)
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--max-seconds", type=float, default=520.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    cmd_run(a.max_seconds) if a.cmd == "run" else cmd_table()
