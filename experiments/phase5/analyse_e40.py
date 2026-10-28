"""Analysis of E40 (and E41, E42) for paper P1 (B-75): paired differences, bootstrap CIs, PREREG decision rules.

    python experiments/phase5/analyse_e40.py        # -> results/table_E40_regimes.csv, results/table_E40_pairs.csv,
                                                    #    results/E40_fit.json (works on whatever rows exist; prints n)

Primary outcome (PREREG): mean urgent wait (atc_urgent_wait_mean_cens_h: censored at year end, lost cargo excluded).
Pairs: the same seed and start year in two cells (common random numbers). Paired mean difference with a percentile
bootstrap 95 % CI (20,000 resamples, seed 40); a two-sided bootstrap p-value (twice the smaller share of resampled
means on either side of 0) for Holm's correction across the confirmatory family {H1, H2, H3a, H4, H6} at 30 % load;
TOST for "no practical difference" claims: the 90 % bootstrap CI inside +-margin.
Decision rules (paper/atc/PREREG.md with changes 2 and 3):
- H1: B_EARTH_RELAY 1.0 (pooled, full Earth coverage) cuts the primary outcome vs A_EARTH full coverage (owners
  alone, own teams), at 30 % and 60 %: the CI excludes 0 below.
- H2 (change 2): B_EARTH strict vs O_ORACLE: the lower CI bound of the paired difference exceeds 10 % of O's mean, in
  each start year whose BASE Earth visibility is below 60 % and pooled over the years; plan_ahead and relay 0.8
  reported; the original yardstick (half of the A-vs-O gap) and the delivered-only option reported, not tested.
- H3a: C_AUCTION within +-10 % of O_ORACLE at loss 0.10, 30 % (TOST).
- H4 (change 3): C_LEARNED_MLP and C_LEARNED_LIN each vs C_AUCTION: CI below 0 at 30 % and 60 %; at 10 % within
  +-2 % of C_AUCTION's mean (TOST).
- H6 (E42): cross-owner pairs raise the share of items delivered (C_AUCTION, team share 0.25, loss 0.10, cross-owner
  vs same owner): CI above 0; failed meetings at loss >= 0.25 with and without the commit step reported.
Utilisation is reported both ways (p5_cargo_util and whole-fleet utilisation; LEAD, B-71).
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from experiments.phase5 import run_phase5 as R  # noqa: E402

RES = os.path.join(ROOT, "results")
M = "atc_urgent_wait_mean_cens_h"
B = 20000
KEYS = ["seed", "start_year"]
REPORT = [M, "atc_urgent_wait_mean_h", "atc_urgent_wait_p95_cens_h", "atc_urgent_within24_share", "delivered_kg",
          "atc_deadhead_share", "p5_cargo_util", "utilisation", "atc_decider_down_share", "atc_msgs_per_robot_h",
          "atc_backlog_end_blackout_t_mean", "atc_starved_items", "atc_robots_out_share", "team_lifts",
          "p5_team_items_delivered", "p5_team_items", "backlog_kg", "stranded_kg"]


def boot(d: np.ndarray, seed: int = 40, level: float = 0.95) -> Dict[str, Any]:
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 2:
        return {"n": n, "mean": float(d.mean()) if n else None, "ci": None, "p": None}
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, n, (B, n))].mean(1)
    a = (1 - level) / 2
    p = 2 * min((means <= 0).mean(), (means >= 0).mean())
    return {"n": n, "mean": round(float(d.mean()), 4),
            "ci": [round(float(np.quantile(means, a)), 4), round(float(np.quantile(means, 1 - a)), 4)],
            "ci90": [round(float(np.quantile(means, 0.05)), 4), round(float(np.quantile(means, 0.95)), 4)],
            "p": round(float(min(1.0, max(p, 1.0 / B))), 6)}


def paired(df: pd.DataFrame, a: Dict[str, Any], b: Dict[str, Any], metric: str = M, years=None) -> Tuple[np.ndarray, pd.DataFrame]:
    """Differences a - b on the same (seed, start year); a, b select rows by column values."""
    sa = _sel(df, a)
    sb = _sel(df, b)
    if years is not None:
        sa, sb = sa[sa["start_year"].isin(years)], sb[sb["start_year"].isin(years)]
    j = sa[KEYS + [metric]].merge(sb[KEYS + [metric]], on=KEYS, suffixes=("_a", "_b"))
    return (j[f"{metric}_a"] - j[f"{metric}_b"]).to_numpy(float), j


def _sel(df, q):
    s = df
    for k, v in q.items():
        s = s[s[k] == v]
    return s


def regimes_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (load, label), g in df.groupby(["load", "label"]):
        r = {"load": int(load), "label": label, "n": len(g), "n_v1": int((g["block"] != "v3").sum() if "block" in g else 0)}
        for k in REPORT:
            if k in g:
                v = g[k].astype(float)
                r[k] = round(float(v.mean()), 4)
        o = _sel(df, {"load": load, "label": "O_ORACLE"})
        if len(o) and label != "O_ORACLE":
            d, _ = paired(df, {"load": load, "label": label}, {"load": load, "label": "O_ORACLE"})
            bb = boot(d)
            r.update({"minus_O_mean": bb["mean"], "minus_O_lo": bb["ci"][0] if bb["ci"] else None,
                      "minus_O_hi": bb["ci"][1] if bb["ci"] else None, "minus_O_n": bb["n"]})
        rows.append(r)
    return pd.DataFrame(rows)


def visibility_by_year(df: pd.DataFrame) -> Dict[int, float]:
    s = _sel(df, {"label": "B_EARTH strict"})
    return {int(y): round(float(1 - g["atc_decider_down_share"].mean()), 4) for y, g in s.groupby("start_year")}


def main() -> Dict[str, Any]:
    t0 = time.time()
    df = R.load_runs("E40")
    if df.empty:
        raise SystemExit("no E40 rows")
    df = df.copy()
    n = df.groupby(["load", "label"]).size()
    print("E40 rows per cell (load, label):")
    print(n.to_string())
    tab = regimes_table(df)
    tab.to_csv(os.path.join(RES, "table_E40_regimes.csv"), index=False, lineterminator="\n")
    fit: Dict[str, Any] = {"task": "B-75", "n_rows": int(len(df)), "n_per_cell": {f"{l}|{lab}": int(v) for (l, lab), v in n.items()},
                           "metric": M, "bootstrap": B, "hypotheses": {}, "notes": []}
    pairs_rows = []

    def add_pair(name, load, a, b, metric=M, years=None, rel_to=None):
        d, j = paired(df, dict(a, load=load), dict(b, load=load), metric, years)
        bb = boot(d)
        base = _sel(df, dict(b, load=load))
        if years is not None:
            base = base[base["start_year"].isin(years)]
        bm = float(base[metric].mean()) if len(base) else float("nan")
        row = {"comparison": name, "load": load, "metric": metric, **{k: bb[k] for k in ("n", "mean", "p")},
               "lo": bb["ci"][0] if bb["ci"] else None, "hi": bb["ci"][1] if bb["ci"] else None,
               "lo90": bb["ci90"][0] if bb.get("ci90") else None, "hi90": bb["ci90"][1] if bb.get("ci90") else None,
               "b_mean": round(bm, 4), "share_of_b": round(bb["mean"] / bm, 4) if bb["mean"] is not None and bm else None}
        pairs_rows.append(row)
        return row

    H = fit["hypotheses"]
    # H1
    h1 = {str(L): add_pair("H1: B_EARTH_RELAY 1.0 - A_EARTH full coverage", L, {"label": "B_EARTH_RELAY 1.0"},
                           {"label": "A_EARTH full coverage"}) for L in (30, 60)}
    H["H1"] = {"rows": h1, "supported": {L: (r["hi"] is not None and r["hi"] < 0) for L, r in h1.items() if r["n"] > 1}}
    # H2
    vis = visibility_by_year(df)
    low = sorted(y for y, v in vis.items() if v < 0.60)
    h2 = {}
    for L in (30, 60):
        o_mean = _sel(df, {"load": L, "label": "O_ORACLE"})[M].mean()
        per = {}
        for y in low:
            r = add_pair(f"H2: B_EARTH strict - O_ORACLE, {y}", L, {"label": "B_EARTH strict"}, {"label": "O_ORACLE"},
                         years=[y])
            om = _sel(df, {"load": L, "label": "O_ORACLE", "start_year": y})[M].mean()
            r["threshold_10pct_of_O"] = round(0.1 * float(om), 4)
            r["passes"] = r["lo"] is not None and r["lo"] > 0.1 * om
            per[str(y)] = r
        pooled = add_pair("H2: B_EARTH strict - O_ORACLE, pooled years", L, {"label": "B_EARTH strict"}, {"label": "O_ORACLE"})
        pooled["threshold_10pct_of_O"] = round(0.1 * float(o_mean), 4) if np.isfinite(o_mean) else None
        pooled["passes"] = pooled["lo"] is not None and pooled["lo"] > 0.1 * o_mean
        extra = {lab: add_pair(f"{lab} - O_ORACLE", L, {"label": lab}, {"label": "O_ORACLE"})
                 for lab in ("B_EARTH plan_ahead", "B_EARTH_RELAY 0.8")}
        ao = add_pair("A_EARTH strict - O_ORACLE (original H2 yardstick, not tested)", L, {"label": "A_EARTH strict"}, {"label": "O_ORACLE"})
        ao_del = add_pair("A_EARTH strict - O_ORACLE, delivered-only urgent wait (not tested; conditions on delivery)", L,
                          {"label": "A_EARTH strict"}, {"label": "O_ORACLE"}, metric="atc_urgent_wait_mean_h")
        h2[str(L)] = {"low_visibility_years": low, "visibility": vis, "per_year": per, "pooled": pooled,
                      "plan_ahead_and_relay": extra,
                      "original_yardstick_half_A_minus_O": round(0.5 * ao["mean"], 4) if ao["mean"] is not None else None,
                      "delivered_only_A_minus_O": ao_del["mean"],
                      "supported": bool(pooled["passes"] and all(r["passes"] for r in per.values()))}
    H["H2"] = h2
    # H3a
    r = add_pair("H3a: C_AUCTION - O_ORACLE (TOST +-10 % of O)", 30, {"label": "C_AUCTION"}, {"label": "O_ORACLE"})
    marg = 0.1 * r["b_mean"]
    r["margin"] = round(marg, 4)
    r["tost_equivalent"] = r["lo90"] is not None and -marg < r["lo90"] and r["hi90"] < marg
    H["H3a"] = r
    # H4
    h4 = {}
    for pol in ("C_LEARNED_MLP", "C_LEARNED_LIN"):
        per = {}
        for L in (10, 30, 60):
            rr = add_pair(f"H4: {pol} - C_AUCTION", L, {"label": pol}, {"label": "C_AUCTION"})
            if L == 10:
                m2 = 0.02 * rr["b_mean"]
                rr["margin"] = round(m2, 4)
                rr["tost_equivalent"] = rr["lo90"] is not None and -m2 < rr["lo90"] and rr["hi90"] < m2
            else:
                rr["beats_hand"] = rr["hi"] is not None and rr["hi"] < 0
            per[str(L)] = rr
        h4[pol] = per
    H["H4"] = h4
    # H6 (E42) and E41 summaries, when present
    for exp in ("E41", "E42"):
        try:
            de = R.load_runs(exp)
        except ValueError as e:
            raise SystemExit(str(e))
        if de.empty:
            continue
        g = de.groupby("label")
        summ = {lab: {"n": int(len(x)), **{k: round(float(x[k].mean()), 4) for k in REPORT + ["atc_failed_meetings",
                "atc_team_no_agreement", "atc_meeting_wait_h", "atc_conflicts", "atc_wasted_trips", "atc_arbitrated",
                "atc_own_team_jobs", "delivered_kg"] if k in x}} for lab, x in g}
        fit[exp] = {"n_rows": int(len(de)), "cells": summ}
    if "E42" in fit:
        de = R.load_runs("E42")
        de = de.assign(load=30)
        d, j = paired(de, {"label": "C_AUCTION team 25 any loss 0.1"}, {"label": "C_AUCTION team 25 same_owner loss 0.1"},
                      metric="delivered_kg")
        H["H6"] = {"delivered_t_cross_minus_same_owner": boot(d / 1000.0)}
    # Holm across the confirmatory family at 30 %
    fam = {"H1": h1.get("30", {}).get("p"), "H2": h2["30"]["pooled"]["p"], "H3a": None,
           "H4_lin": h4["C_LEARNED_LIN"]["30"]["p"], "H4_mlp": h4["C_LEARNED_MLP"]["30"]["p"],
           "H6": H.get("H6", {}).get("delivered_t_cross_minus_same_owner", {}).get("p")}
    ps = sorted((v, k) for k, v in fam.items() if v is not None)
    holm, run_max = {}, 0.0
    for i, (p, k) in enumerate(ps):
        run_max = max(run_max, min(1.0, (len(ps) - i) * p))
        holm[k] = round(run_max, 6)
    fit["holm_30pct"] = {"raw_p": fam, "adjusted_p": holm,
                         "note": "H3a is an equivalence claim (TOST), outside the Holm-adjusted difference tests"}
    fit["notes"].append("cells 38-39 (A_EARTH full coverage) were added to the runner before any of their rows ran; "
                        "they are the yardstick PREREG H1 names (LEAD, 27 Oct)")
    pd.DataFrame(pairs_rows).to_csv(os.path.join(RES, "table_E40_pairs.csv"), index=False, lineterminator="\n")
    fit["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(RES, "E40_fit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(fit, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
        f.write("\n")
    return fit


if __name__ == "__main__":
    f = main()
    H = f["hypotheses"]
    print(json.dumps({"H1": {k: (v["mean"], v["lo"], v["hi"], v["n"]) for k, v in H["H1"]["rows"].items()},
                      "H2_pooled": {L: (x["pooled"]["mean"], x["pooled"]["lo"], x["pooled"]["threshold_10pct_of_O"], x["supported"]) for L, x in H["H2"].items()},
                      "H3a": (H["H3a"]["mean"], H["H3a"]["lo90"], H["H3a"]["hi90"], H["H3a"]["margin"], H["H3a"]["tost_equivalent"]),
                      "H4": {p: {L: (r["mean"], r["lo"], r["hi"], r["n"]) for L, r in v.items()} for p, v in H["H4"].items()},
                      "holm": f["holm_30pct"]["adjusted_p"]}, indent=1, default=str))
