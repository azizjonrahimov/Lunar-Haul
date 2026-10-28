"""B-75: replace the rows that the auction's hash-order bug made non-reproducible, and compare old with new.

    python tools/atc/rerun_check.py drop --exp E40      # archive results/E40_runs.csv to results/archive/E40_runs.csv.prefix,
                                                         # then remove the affected rows from the live file
    (rerun with experiments/phase5/run_phase5.py run --exp E40 --cells ...; it fills exactly the missing keys)
    python tools/atc/rerun_check.py compare --exp E40    # -> results/<exp>_rerun_check.json: per cell old vs new means
                                                         #    and the paired difference (bootstrap 95 % CI)

Affected (PREREG change 4): C_AUCTION, C_LEARNED_MLP and C_LEARNED_LIN cells with message loss > 0, whose robot list was
built from a set holding the string "BASE" (iteration order by Python's per-process string hash) before the fix in
lunarsim/atc/auction.py. E40: the 10 % and 30 % cells of those regimes, block v1 (their v3 rows repeat v1 seeds 1-10
and are not used), and the C_AUCTION hopper_refuel cell. E42: every C_AUCTION cell with loss > 0.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from experiments.phase5.analyse_e40 import boot  # noqa: E402

RES = os.path.join(ROOT, "results")
ARCH = os.path.join(RES, "archive")
METRICS = ("atc_urgent_wait_mean_cens_h", "delivered_kg", "atc_urgent_wait_p95_cens_h", "atc_conflicts")


def affected(df: pd.DataFrame, exp: str) -> pd.Series:
    auc = df["regime"].isin(["C_AUCTION", "C_LEARNED_MLP", "C_LEARNED_LIN"]) & (df["loss"].astype(float) > 0)
    if exp == "E40":
        v1 = df["start_year"] == 2028 + df["seed"] % 4
        return auc & v1 & df["load"].isin([10, 30])
    return auc


def cmd_drop(exp: str) -> None:
    live = os.path.join(RES, f"{exp}_runs.csv")
    os.makedirs(ARCH, exist_ok=True)
    arch = os.path.join(ARCH, f"{exp}_runs.csv.prefix")
    if os.path.isfile(arch):
        raise SystemExit(f"{arch} exists: the rows were already archived; not overwriting it")
    shutil.copy2(live, arch)
    df = pd.read_csv(live, float_precision="round_trip", dtype=str, keep_default_na=False)   # keep every byte as is
    num = pd.read_csv(live, float_precision="round_trip")
    mask = affected(num, exp).to_numpy()
    df[~mask].to_csv(live, index=False, lineterminator="\n")
    print(f"drop: archived {os.path.relpath(arch, ROOT)}; removed {int(mask.sum())} affected rows of {len(df)} "
          f"({sorted(num.loc[mask, 'label'].unique())})")


def cmd_compare(exp: str) -> None:
    old = pd.read_csv(os.path.join(ARCH, f"{exp}_runs.csv.prefix"), float_precision="round_trip")
    new = pd.read_csv(os.path.join(RES, f"{exp}_runs.csv"), float_precision="round_trip")
    old = old[affected(old, exp)]
    new = new[new["cell"].isin(old["cell"].unique())]
    new = new[affected(new, exp)]
    k = ["cell", "seed", "start_year"]
    j = old.merge(new, on=k, suffixes=("_old", "_new"))
    out = {"exp": exp, "note": __doc__.split("\n\n")[-1].strip(), "rows_old": int(len(old)), "rows_new": int(len(new)),
           "paired": int(len(j)), "cells": {}, "flagged": []}
    for cell, g in j.groupby("cell"):
        lab = g["label_old"].iloc[0]
        load = int(g["load_old"].iloc[0])
        blk = {"label": lab, "load": load, "n": int(len(g)),
               "identical_rows": int(sum(all(a == b for a, b in zip(r[[f"{m}_old" for m in METRICS]], r[[f"{m}_new" for m in METRICS]]))
                                         for _, r in g.iterrows()))}
        for m in METRICS:
            d = (g[f"{m}_new"] - g[f"{m}_old"]).to_numpy(float)
            bb = boot(d)
            blk[m] = {"old": round(float(g[f"{m}_old"].mean()), 4), "new": round(float(g[f"{m}_new"].mean()), 4),
                      "new_minus_old": bb}
            if m == METRICS[0] and bb["ci"] and (bb["ci"][0] > 0 or bb["ci"][1] < 0):
                out["flagged"].append(f"{lab} L{load}: new - old {bb['mean']} h, CI {bb['ci']} excludes 0")
        out["cells"][f"{lab} | L{load}"] = blk
    p = os.path.join(RES, f"{exp}_rerun_check.json")
    with open(p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(json.dumps({c: (v["n"], v["identical_rows"], v[METRICS[0]]["old"], v[METRICS[0]]["new"],
                          v[METRICS[0]]["new_minus_old"]["mean"], v[METRICS[0]]["new_minus_old"]["ci"])
                      for c, v in out["cells"].items()}, indent=1))
    print("flagged:", out["flagged"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["drop", "compare"])
    ap.add_argument("--exp", default="E40", choices=["E40", "E42"])
    a = ap.parse_args()
    cmd_drop(a.exp) if a.cmd == "drop" else cmd_compare(a.exp)
