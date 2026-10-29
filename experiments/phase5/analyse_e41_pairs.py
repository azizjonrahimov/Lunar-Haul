"""Paired analysis of E41 for paper P1 (LEAD): the tables build_p1.py reads for Section 5.5 (message loss, bundle
depth, radio range, the lost-link rule and a second mast) and the H3b / H3c decisions.

    python experiments/phase5/analyse_e41_pairs.py   # -> results/table_E41_cells.csv, results/table_E41_pairs.csv,
                                                      #    results/E41_fit.json (works on whatever rows exist; prints n)

Design (run_phase5.e41_cells; block v1, seeds 1-30, 30 % load). One factor at a time around the four on-Moon
regimes (C_LEADER, C_AUCTION, C_LEARNED_MLP, C_LEARNED_LIN):
  loss 0, 0.10, 0.25, 0.40 and bursty 0.25 (all four regimes);
  bundle depth 2 and 5 at loss 0.25 and 0.40 (not the leader, which does not bundle);
  radio range 2 km, 10 km and perfect at loss 0.10 (all four);
  the lost-link rule off and a second mast at pad B at loss 0.10 (all four).
The default cell of each regime is "<regime> loss 0.1" (the E40 configuration of that regime at 30 %).

Pairs: the same seed in two cells (common random numbers). Block v1 pairs with the E40 v1 rows of O_ORACLE at 30 %
(the full-information marketplace), which never wait for Earth and so share the seed's year. Paired mean difference
with a percentile bootstrap 95 % CI (20,000 resamples, seed 41), the 90 % CI for one-sided rules, and the ratio to
the baseline's mean with its own bootstrap CI. The primary outcome is the censored mean urgent wait (as in E40).

Decision rules (PREREG, both exploratory). H3b: at loss 0.25-0.40 bundle depth 5 is worse than depth 1: supported
if the 95 % CI of (depth 5 - depth 1) on the primary outcome lies above zero at both losses for the auction. H3c:
C_LEADER matches C_AUCTION unless the mesh partitions: "matches" in a cell if the 90 % CI of (leader - auction) /
mean(auction) lies within +-10 % (TOST at the H3a margin); the partition cells are range 2 km and the lost-link rule
off (the share of robots out of the mast's part of the network is reported for every cell).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "results")
sys.path.insert(0, ROOT)
from experiments.phase5 import run_phase5 as RP  # noqa: E402

PRIMARY = "atc_urgent_wait_mean_cens_h"
METRICS = [PRIMARY, "atc_urgent_wait_mean_h", "atc_urgent_wait_p95_cens_h", "atc_urgent_within24_share",
           "atc_urgent_items", "delivered_kg", "delivered_items", "delay_mean_h", "atc_claims_stale", "atc_claims_won",
           "atc_wasted_trips", "atc_parallel_winners", "atc_conflicts", "atc_msgs_lost", "atc_msgs_per_robot_h",
           "atc_robots_out_share", "atc_rallies", "atc_status_lost", "atc_decider_down_share", "atc_base_failures",
           "operator_hours", "run_s"]
SEC = (PRIMARY, "atc_urgent_wait_p95_cens_h", "atc_urgent_within24_share", "delivered_kg", "delivered_items",
       "atc_claims_stale", "atc_wasted_trips", "atc_robots_out_share", "atc_rallies")
REGIMES = [lab for lab, _ in RP.C_FOUR]
DEPTH_REGIMES = [lab for lab, _ in RP.C_FOUR[1:]]
LOSSES = ("0", "0.1", "0.25", "0.4")
DEFAULT = "loss 0.1"
N_BOOT, SEED, MARGIN_H3C = 20000, 41, 0.10
LABEL_RE = re.compile(r"^(?P<regime>C_[A-Z_]+) (?P<rest>.+)$")


def factor_of(label: str) -> Dict[str, str]:
    m = LABEL_RE.match(label)
    if not m:
        raise ValueError(f"unexpected E41 label {label!r}")
    rest = m.group("rest")
    if rest.startswith("depth"):
        _, depth, _, loss = rest.split()
        return {"regime": m.group("regime"), "factor": "depth", "level": depth, "loss": loss}
    if rest.startswith("burst"):
        return {"regime": m.group("regime"), "factor": "burst", "level": rest.split()[1], "loss": rest.split()[1]}
    if rest.startswith("loss"):
        return {"regime": m.group("regime"), "factor": "loss", "level": rest.split()[1], "loss": rest.split()[1]}
    if rest.startswith("range"):
        return {"regime": m.group("regime"), "factor": "range", "level": rest[len("range "):], "loss": "0.1"}
    if rest == "rally off":
        return {"regime": m.group("regime"), "factor": "rally", "level": "off", "loss": "0.1"}
    if rest.startswith("mast2"):
        return {"regime": m.group("regime"), "factor": "mast2", "level": rest.split()[1], "loss": "0.1"}
    raise ValueError(f"unexpected E41 label {label!r}")


def load() -> pd.DataFrame:
    d = RP.load_runs("E41")
    if d.empty:
        raise SystemExit("no E41 run files")
    if "label" not in d:
        d["label"] = d["cell"].str.extract(r"label=([^;]+)")[0]
    v1 = d["start_year"] == 2028 + d["seed"] % 4
    if not v1.all():
        raise SystemExit(f"{int((~v1).sum())} E41 rows are not block v1 (start year 2028 + seed mod 4)")
    return d


def load_oracle() -> pd.DataFrame:
    """E40's O_ORACLE at 30 % on block v1: the full-information marketplace, paired by seed."""
    d = RP.load_runs("E40")
    if d.empty:
        return d
    if "label" not in d:
        d["label"] = d["cell"].str.extract(r"label=([^;]+)")[0]
    o = d[(d["label"] == "O_ORACLE") & (d["load"] == 30) & (d["start_year"] == 2028 + d["seed"] % 4)]
    return o


def paired(a: pd.DataFrame, b: pd.DataFrame, metric: str, rng: np.random.Generator) -> Dict[str, Any]:
    """a - b on the same seeds; b is the baseline."""
    m = a[["seed", metric]].merge(b[["seed", metric]], on="seed", suffixes=("_a", "_b")).dropna()
    n = len(m)
    out: Dict[str, Any] = {"n": n}
    if n == 0:
        return dict(out, mean=np.nan, lo=np.nan, hi=np.nan, lo90=np.nan, hi90=np.nan, p=np.nan, b_mean=np.nan,
                    share_of_b=np.nan, ratio_lo=np.nan, ratio_hi=np.nan, ratio_lo90=np.nan, ratio_hi90=np.nan)
    x, y = m[f"{metric}_a"].to_numpy(float), m[f"{metric}_b"].to_numpy(float)
    d = x - y
    idx = rng.integers(0, n, size=(N_BOOT, n))
    bd = d[idx].mean(axis=1)
    by = y[idx].mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        br = np.where(by != 0, bd / by, np.nan)
    q = lambda v, p: float(np.nanpercentile(v, p))
    p = float(2 * min((bd <= 0).mean(), (bd >= 0).mean()))
    return dict(out, mean=float(d.mean()), lo=q(bd, 2.5), hi=q(bd, 97.5), lo90=q(bd, 5), hi90=q(bd, 95),
                p=max(p, 1.0 / N_BOOT), b_mean=float(y.mean()),
                share_of_b=float(d.mean() / y.mean()) if y.mean() != 0 else np.nan,
                ratio_lo=q(br, 2.5), ratio_hi=q(br, 97.5), ratio_lo90=q(br, 5), ratio_hi90=q(br, 95))


def main() -> None:
    t0 = time.time()
    d = load()
    oracle = load_oracle()
    rng = np.random.default_rng(SEED)
    print(f"E41: {len(d)} rows, {d['label'].nunique()} labels; oracle rows {len(oracle)}")

    rows = []
    for label, g in d.groupby("label", sort=False):
        row = {"label": label, **factor_of(label), "n": len(g),
               "seeds": ",".join(str(s) for s in sorted(g["seed"].astype(int)))}
        for mtr in METRICS:
            row[mtr] = float(g[mtr].mean()) if mtr in g and g[mtr].notna().any() else np.nan
        rows.append(row)
    cells = pd.DataFrame(rows).sort_values(["factor", "regime", "level", "loss"]).reset_index(drop=True)
    cells.to_csv(os.path.join(RES, "table_E41_cells.csv"), index=False)

    def sub(label: str) -> pd.DataFrame:
        return d[d["label"] == label]

    pairs: List[Dict[str, Any]] = []

    def add(comparison: str, a: pd.DataFrame, b: pd.DataFrame, metrics=(PRIMARY,), **tags) -> Optional[Dict[str, Any]]:
        first = None
        for mtr in metrics:
            if mtr not in a or mtr not in b:
                continue
            r = paired(a, b, mtr, rng)
            pairs.append(dict(comparison=comparison, metric=mtr, **tags, **r))
            if mtr == PRIMARY:
                first = r
                if r["n"]:
                    print(f"  {comparison:52s} n={r['n']:3d} {r['mean']:+9.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}] "
                          f"ratio {r['share_of_b']:+.3f}")
        return first

    # loss: each regime against its own loss-0 cell, bursty against steady 0.25, every loss cell against the marketplace
    slope: Dict[str, Any] = {}
    crossing: Dict[str, Any] = {}
    for reg in REGIMES:
        base0 = sub(f"{reg} loss 0")
        for L in LOSSES[1:]:
            add(f"{reg} loss {L} - {reg} loss 0", sub(f"{reg} loss {L}"), base0, SEC, regime=reg, factor="loss", level=L)
        add(f"{reg} burst 0.25 - {reg} loss 0.25", sub(f"{reg} burst 0.25"), sub(f"{reg} loss 0.25"), SEC,
            regime=reg, factor="burst", level="0.25")
        if len(oracle):
            cr = None
            for L in LOSSES:
                r = add(f"{reg} loss {L} - O_ORACLE", sub(f"{reg} loss {L}"), oracle, SEC, regime=reg, factor="loss",
                        level=L)
                if cr is None and r and r["n"] and r["lo90"] > 0:
                    cr = L
            crossing[reg] = cr      # the smallest loss at which the regime is above the marketplace (90 % CI above 0)
        m0, m4 = cells[cells["label"] == f"{reg} loss 0"], cells[cells["label"] == f"{reg} loss 0.4"]
        if len(m0) and len(m4) and m0[PRIMARY].iloc[0] > 0 and int(m0["n"].iloc[0]) == 30 and int(m4["n"].iloc[0]) == 30:
            y0, y4 = float(m0[PRIMARY].iloc[0]), float(m4[PRIMARY].iloc[0])
            slope[reg] = {"wait_0_h": y0, "wait_40_h": y4, "pct_of_loss0_per_point": 100.0 * (y4 - y0) / y0 / 40.0}

    # bundle depth: depth 2 and 5 against depth 1 (the loss cell) at the same loss; H3b for the auction
    h3b: Dict[str, Any] = {"cells": {}, "supported": None}
    for reg in DEPTH_REGIMES:
        for depth in ("2", "5"):
            for L in ("0.25", "0.4"):
                r = add(f"{reg} depth {depth} loss {L} - {reg} loss {L}", sub(f"{reg} depth {depth} loss {L}"),
                        sub(f"{reg} loss {L}"), SEC, regime=reg, factor="depth", level=depth, loss=L)
                if r and r["n"]:
                    h3b["cells"][f"{reg} depth {depth} loss {L}"] = {"n": r["n"], "mean": r["mean"], "lo": r["lo"],
                                                                     "hi": r["hi"], "worse": bool(r["lo"] > 0),
                                                                     "better": bool(r["hi"] < 0)}
    auc5 = [h3b["cells"].get(f"C_AUCTION depth 5 loss {L}") for L in ("0.25", "0.4")]
    if all(c and c["n"] == 30 for c in auc5):
        h3b["supported"] = bool(all(c["worse"] for c in auc5))
        h3b["test"] = {f"loss {L}": c for L, c in zip(("0.25", "0.4"), auc5)}

    # radio range, the lost-link rule and the second mast against the regime's default cell
    for reg in REGIMES:
        base = sub(f"{reg} {DEFAULT}")
        for rng_lab in ("2 km", "10 km", "perfect"):
            add(f"{reg} range {rng_lab} - {reg} {DEFAULT}", sub(f"{reg} range {rng_lab}"), base, SEC, regime=reg,
                factor="range", level=rng_lab)
        add(f"{reg} rally off - {reg} {DEFAULT}", sub(f"{reg} rally off"), base, SEC, regime=reg, factor="rally",
            level="off")
        add(f"{reg} mast2 PAD_B - {reg} {DEFAULT}", sub(f"{reg} mast2 PAD_B"), base, SEC, regime=reg, factor="mast2",
            level="PAD_B")

    # H3c: the leader against the auction in every cell both ran
    h3c: Dict[str, Any] = {"margin": MARGIN_H3C, "cells": {}}
    for cond in [f"loss {L}" for L in LOSSES] + ["burst 0.25", "range 2 km", "range 10 km", "range perfect",
                                                  "rally off", "mast2 PAD_B"]:
        r = add(f"H3c: C_LEADER - C_AUCTION, {cond}", sub(f"C_LEADER {cond}"), sub(f"C_AUCTION {cond}"), SEC,
                regime="C_LEADER", factor="h3c", level=cond)
        if r and r["n"]:
            out = {o: float(sub(f"{reg} {cond}")["atc_robots_out_share"].mean()) for o, reg in
                   (("leader", "C_LEADER"), ("auction", "C_AUCTION")) if "atc_robots_out_share" in d}
            h3c["cells"][cond] = {"n": r["n"], "mean": r["mean"], "lo": r["lo"], "hi": r["hi"],
                                  "ratio_lo90": r["ratio_lo90"], "ratio_hi90": r["ratio_hi90"],
                                  "matches": bool(r["ratio_lo90"] > -MARGIN_H3C and r["ratio_hi90"] < MARGIN_H3C),
                                  "robots_out_share": out}
    # the replication check: E41's default auction cell is E40's C_AUCTION at 30 % on the same seeds
    e40 = RP.load_runs("E40")
    if not e40.empty:
        if "label" not in e40:
            e40["label"] = e40["cell"].str.extract(r"label=([^;]+)")[0]
        a40 = e40[(e40["label"] == "C_AUCTION") & (e40["load"] == 30) & (e40["start_year"] == 2028 + e40["seed"] % 4)]
        add("replication: C_AUCTION loss 0.1 (E41) - C_AUCTION 30 % v1 (E40)", sub("C_AUCTION loss 0.1"), a40,
            (PRIMARY, "delivered_kg"), regime="C_AUCTION", factor="replication", level="E40")
    pd.DataFrame(pairs).to_csv(os.path.join(RES, "table_E41_pairs.csv"), index=False)

    rep = next((p for p in pairs if p["factor"] == "replication" and p["metric"] == PRIMARY), None)
    counts = {lab: int(n) for lab, n in d.groupby("label", sort=False).size().items()}
    fit = {"n_rows": int(len(d)), "n_cells_designed": len(RP.e41_cells()), "labels": counts, "primary": PRIMARY,
           "n_boot": N_BOOT, "seed": SEED, "default_cell": DEFAULT, "oracle_rows": int(len(oracle)),
           "H3b": h3b, "H3c": h3c, "slope_per_point_of_loss": slope, "crossing_loss_vs_oracle": crossing,
           "replication_e40": {k: rep[k] for k in ("n", "mean", "lo", "hi")} if rep else None,
           "run_s_mean_by_label": {lab: float(v) for lab, v in d.groupby("label", sort=False)["run_s"].mean().items()},
           "elapsed_s": round(time.time() - t0, 1)}
    with open(os.path.join(RES, "E41_fit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(fit, f, indent=1)
        f.write("\n")
    print(json.dumps({"H3b": h3b.get("supported"), "H3c": {k: v["matches"] for k, v in h3c["cells"].items()},
                      "slope": slope, "crossing": crossing, "replication": fit["replication_e40"]}, indent=1))


if __name__ == "__main__":
    main()
