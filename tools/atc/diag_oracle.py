"""B-75 diagnostic: why the decentralised auction can beat the full-information marketplace (O_ORACLE).

    python tools/atc/diag_oracle.py run     # resumable, cached in .cache/atc/diag_oracle.json
    python tools/atc/diag_oracle.py table   # -> results/ATC_oracle_diag.json

E40 at 30 % load, block v1 (seeds 1-30, start year 2028 + seed mod 4), paired with E40's own O_ORACLE and
C_AUCTION rows (results/E40_runs.csv; same scenario, seeds and years). Two extra cells, not PREREG cells:
- O + rally: O_ORACLE with the auction's lost-link rally applied to every idle robot (o_rally);
- C_AUCTION loss 0: the auction on terrain radio without message loss.
Single process, --max-seconds 540.
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

CACHE = os.path.join(ROOT, ".cache", "atc", "diag_oracle.json")
OUT = os.path.join(ROOT, "results", "ATC_oracle_diag.json")
CELLS = {"O + rally": ("O_ORACLE", {"o_rally": True}), "C_AUCTION loss 0": ("C_AUCTION", {"loss": 0.0})}
KEEP = ("atc_urgent_wait_mean_cens_h", "atc_deadhead_share", "atc_rallies", "delivered_kg", "atc_urgent_within24_share")


def cmd_run(max_s):
    t0, last = time.time(), 15.0
    done = json.load(open(CACHE)) if os.path.isfile(CACHE) else {}
    for lab, (reg, kw) in CELLS.items():
        c = R.cell("DIAG", lab, reg, kw, load="30", block="v1")
        for seed in R.V1_SEEDS:
            k = f"{lab}|{seed}"
            if k in done:
                continue
            if time.time() - t0 > max_s - max(60, 1.5 * last):
                print(f"run: time limit, {len(done)} done; rerun")
                return
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = R.run_one(c, seed, None)
            last = r["run_s"]
            done[k] = {m: float(r[m]) for m in KEEP}
            os.makedirs(os.path.dirname(CACHE), exist_ok=True)
            json.dump(done, open(CACHE, "w"))
            print(f"  {k}: {done[k]['atc_urgent_wait_mean_cens_h']:.2f} h ({last} s)", flush=True)
    print("run: done")


def cmd_table():
    done = json.load(open(CACHE))
    import pandas as pd
    e = pd.read_csv(os.path.join(ROOT, "results", "E40_runs.csv"), float_precision="round_trip")   # my rows only
    e = e[(e["load"] == 30) & (e["start_year"] == 2028 + e["seed"] % 4)]
    base = {lab: e[e["label"] == lab].set_index("seed") for lab in ("O_ORACLE", "C_AUCTION")}
    vals = {lab: {s: base[lab].loc[s] for s in R.V1_SEEDS} for lab in base}
    out = {"task": "B-75 diagnostic", "note": __doc__.split("\n\n")[-1].strip(), "cells": {}, "pairs": {}}
    series = {}
    for lab in ("O_ORACLE", "C_AUCTION"):
        series[lab] = {m: np.array([float(vals[lab][s][m]) for s in R.V1_SEEDS]) for m in KEEP}
    for lab in CELLS:
        series[lab] = {m: np.array([done[f"{lab}|{s}"][m] for s in R.V1_SEEDS]) for m in KEEP}
    for lab, ser in series.items():
        out["cells"][lab] = {m: round(float(v.mean()), 4) for m, v in ser.items()}
    m = "atc_urgent_wait_mean_cens_h"
    for a, b in (("O + rally", "O_ORACLE"), ("C_AUCTION", "O_ORACLE"), ("C_AUCTION loss 0", "O_ORACLE"),
                 ("C_AUCTION", "O + rally"), ("C_AUCTION loss 0", "O + rally")):
        out["pairs"][f"{a} - {b}"] = boot(series[a][m] - series[b][m])
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    cmd_run(a.max_seconds) if a.cmd == "run" else cmd_table()
