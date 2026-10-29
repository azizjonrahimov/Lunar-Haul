"""E43 (B-77): rules of the road at logistics resolution -> results/E43_summary.json.

Per cell: means of the delivery and road metrics. Paired by seed (same seed, same start year): atc - none (what the rules
cost when one shared table resolves conflicts) and uncoordinated - atc (what coordinating the table is worth), per fleet
density and, for uncoordinated, per start year; bootstrap 95 % CI as in analyse_e40. The single-lane share is ASSUMED
(results/ATC_roads_corridor.json); the 8x cells were not run (data/scenarios/p5/E43-design.json).
"""
from __future__ import annotations

import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import run_phase5 as R  # noqa: E402
from analyse_e40 import boot  # noqa: E402

METRICS = ("atc_urgent_wait_mean_cens_h", "delay_mean_h", "delivered_share", "road_wait_h", "road_conflicts",
           "road_hand_conflicts", "road_hand_wait_h", "road_other_stop_h", "road_eva_slow_h", "road_apron_wait_h")
OUT = os.path.join(ROOT, "results", "E43_summary.json")


def main() -> None:
    df = R.load_runs("E43")
    cells = R.e43_cells()
    out = {"note": __doc__.split("\n\n")[1].strip(), "single_share_flag": R.SINGLE_SHARE_FLAG, "cells": {},
           "paired": {}, "not_run": []}
    for c in cells:
        g = df[df["cell"] == c["key"]]
        n_exp = len(R.blocks(c["block"]))
        lab = f"{c['tag']['label']} | {c['block']}"
        if g.empty:
            out["not_run"].append(lab)
            continue
        out["cells"][lab] = {"n": int(len(g)), "n_planned": n_exp,
                             "horizon_days": float(g["horizon_days"].iloc[0]),
                             **{m: round(float(g[m].mean()), 4) for m in METRICS if m in g}}
    key = ["seed", "start_year"]

    def pair(a_lab, b_lab, name):
        a = df[df["label"] == a_lab]
        b = df[df["label"] == b_lab]
        if a.empty or b.empty:
            return
        for y in sorted(set(a["start_year"]) & set(b["start_year"])):
            j = a[a.start_year == y].merge(b[b.start_year == y], on=key, suffixes=("_a", "_b"))
            if j.empty:
                continue
            out["paired"][f"{name} | {y}"] = {"n": int(len(j)), **{
                m: boot((j[f"{m}_a"] - j[f"{m}_b"]).to_numpy(float)) for m in METRICS[:3]}}

    def pair_seed(a_lab, b_lab, y, name):
        """b is Earth-independent (atc): its 2028 run is its run in any start year, so pair by seed only."""
        a = df[(df["label"] == a_lab) & (df["start_year"] == y)]
        b = df[df["label"] == b_lab]
        j = a.merge(b, on="seed", suffixes=("_a", "_b"))
        if len(j):
            out["paired"][f"{name} | {y} (atc run is year-independent)"] = {"n": int(len(j)), **{
                m: boot((j[f"{m}_a"] - j[f"{m}_b"]).to_numpy(float)) for m in METRICS[:3]}}

    for m in (1, 2, 4):
        pair_seed(f"uncoordinated x{m}", f"atc x{m}", 2038, f"uncoordinated - atc x{m}")
        pair(f"atc x{m}", f"none x{m}", f"atc - none x{m}")
        pair(f"uncoordinated x{m}", f"atc x{m}", f"uncoordinated - atc x{m}")
    for s in ("share 0", "share 0.05", "share 0.4", "bay 0.5", "bay 2"):
        pair(f"uncoordinated x1 {s}", f"atc x1 {s}", f"uncoordinated - atc x1 {s}")
        pair(f"atc x1 {s}", "none x1", f"atc - none x1 {s}")
    pair("atc x1 r7", "atc x1", "atc r7 strict - atc x1")
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    for k, v in out["paired"].items():
        u = v["atc_urgent_wait_mean_cens_h"]
        print(f"{k:42s} n {v['n']:3d}  urgent {u['mean']:+8.2f} {u['ci']}  delay {v['delay_mean_h']['mean']:+7.2f}")
    print("not run:", out["not_run"])


if __name__ == "__main__":
    main()
