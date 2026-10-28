"""Analysis of E40 (and E41, E42) for paper P1 (B-75): paired differences, bootstrap CIs, PREREG decision rules.

    python experiments/phase5/analyse_e40.py        # -> results/table_E40_regimes.csv, results/table_E40_pairs.csv,
                                                    #    results/E40_fit.json (works on whatever rows exist; prints n)

Primary outcome (PREREG): mean urgent wait (atc_urgent_wait_mean_cens_h: censored at year end, lost cargo excluded).
Pairs: the same seed and start year in two cells (common random numbers). Paired mean difference with a percentile
bootstrap 95 % CI (20,000 resamples, seed 40); a two-sided bootstrap p-value for Holm's correction across the
confirmatory family at 30 % load; TOST for "no practical difference": the 90 % bootstrap CI inside +-margin.

Blocks. A run is in block v1 iff start_year == 2028 + seed mod 4 (seeds 1-30, the PREREG design); otherwise v3
(start years 2032-2044 x seeds 1-10). The p5 scenarios carry no engine Earth-link rule, so a regime that never waits
for Earth (EARTH_INDEPENDENT) gives the same run for a seed whatever the start year: its v3 runs repeat v1 seeds 1-10.
A comparison between two such regimes therefore uses block v1 only (n = 30); the all-runs row is reported, flagged
pseudo-replicated. Comparisons with an Earth-dependent regime use every run.

Decision rules (paper/atc/PREREG.md with changes 2 and 3):
- H1: B_EARTH_RELAY 1.0 (pooled, full Earth coverage) cuts the primary outcome vs A_EARTH full coverage (owners alone,
  own teams), at 30 % and 60 %: the CI excludes 0 below. Reported, not tested: the delivered-only difference and the
  split by cargo owner (owners A and B, who have cargo rovers, vs owner C, who has none).
- H2 (change 2): B_EARTH strict vs O_ORACLE: the lower CI bound exceeds 10 % of O's mean in each start year with BASE
  visibility below 60 % and pooled; plan_ahead and relay 0.8 reported; the original yardstick and the delivered-only
  option reported, not tested.
- H3a: C_AUCTION within +-10 % of O_ORACLE at loss 0.10, 30 % (TOST); "not supported as stated" if the 90 % CI leaves
  the band, with the direction.
- H4 (change 3): C_LEARNED_MLP and C_LEARNED_LIN each vs C_AUCTION: CI below 0 at 30 % and 60 %; at 10 % within +-2 %
  of C_AUCTION's mean (TOST).
- H6 (E42): cross-owner pairs raise the share of mass delivered (C_AUCTION, loss 0.10, team share 0.25, cross-owner
  vs same owner): CI above 0. Failed meetings at loss >= 0.25 with commit, without, and arbitrated are reported.
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
EARTH_INDEPENDENT = R.EARTH_INDEPENDENT
REPORT = [M, "atc_urgent_wait_mean_h", "atc_urgent_wait_p95_cens_h", "atc_urgent_within24_share", "delivered_kg",
          "atc_deadhead_share", "p5_cargo_util", "utilisation", "atc_decider_down_share", "atc_msgs_per_robot_h",
          "atc_backlog_end_blackout_t_mean", "atc_starved_items", "atc_robots_out_share", "team_lifts",
          "p5_team_items_delivered", "p5_team_items", "backlog_kg", "stranded_kg", "atc_failed_meetings",
          "atc_team_no_agreement", "atc_meeting_wait_h", "atc_own_team_jobs", "atc_arbitrated", "ready_kg"]


def boot(d: np.ndarray, seed: int = 40, level: float = 0.95) -> Dict[str, Any]:
    d = np.asarray(d, float)
    d = d[np.isfinite(d)]
    n = len(d)
    if n < 2:
        return {"n": n, "mean": round(float(d.mean()), 4) if n else None, "ci": None, "ci90": None, "p": None}
    rng = np.random.default_rng(seed)
    means = d[rng.integers(0, n, (B, n))].mean(1)
    a = (1 - level) / 2
    p = 2 * min((means <= 0).mean(), (means >= 0).mean())
    return {"n": n, "mean": round(float(d.mean()), 4),
            "ci": [round(float(np.quantile(means, a)), 4), round(float(np.quantile(means, 1 - a)), 4)],
            "ci90": [round(float(np.quantile(means, 0.05)), 4), round(float(np.quantile(means, 0.95)), 4)],
            "p": round(float(min(1.0, max(p, 1.0 / B))), 6)}


def _sel(df, q):
    s = df
    for k, v in q.items():
        s = s[s[k] == v]
    return s


def add_block(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["run_block"] = np.where(df["start_year"] == 2028 + df["seed"] % 4, "v1", "v3")
    return df


def paired(df, a, b, metric=M, years=None, block=None):
    sa, sb = _sel(df, a), _sel(df, b)
    if years is not None:
        sa, sb = sa[sa["start_year"].isin(years)], sb[sb["start_year"].isin(years)]
    if block is not None:
        sa, sb = sa[sa["run_block"] == block], sb[sb["run_block"] == block]
    if metric not in sa or metric not in sb:
        return np.zeros(0), sa.iloc[:0]
    j = sa[KEYS + [metric]].merge(sb[KEYS + [metric]], on=KEYS, suffixes=("_a", "_b"))
    return (j[f"{metric}_a"] - j[f"{metric}_b"]).to_numpy(float), j


class Pairs:
    """Pair rows (all runs and v1 only) for table_E40_pairs.csv; `valid` = the version decisions use."""

    def __init__(self, df):
        self.df, self.rows = df, []

    def add(self, name, load, a, b, metric=M, years=None, scale=1.0) -> Dict[str, Any]:
        la, lb = a.get("label"), b.get("label")
        indep = la in EARTH_INDEPENDENT and lb in EARTH_INDEPENDENT
        out = {}
        for blk in (None, "v1"):
            d, _ = paired(self.df, dict(a, load=load), dict(b, load=load), metric, years, blk)
            bb = boot(d * scale)
            base = _sel(self.df, dict(b, load=load))
            if years is not None:
                base = base[base["start_year"].isin(years)]
            if blk:
                base = base[base["run_block"] == blk]
            bm = float(base[metric].mean() * scale) if metric in base and len(base) else float("nan")
            row = {"comparison": name, "load": load, "metric": metric, "block": blk or "all",
                   "pseudo_replicated": bool(indep and blk is None), "valid": bool(blk == "v1" if indep else blk is None),
                   "n": bb["n"], "mean": bb["mean"], "lo": bb["ci"][0] if bb["ci"] else None,
                   "hi": bb["ci"][1] if bb["ci"] else None, "lo90": bb["ci90"][0] if bb["ci90"] else None,
                   "hi90": bb["ci90"][1] if bb["ci90"] else None, "p": bb["p"], "b_mean": round(bm, 4),
                   "share_of_b": round(bb["mean"] / bm, 4) if bb["mean"] is not None and bm else None}
            self.rows.append(row)
            out[blk or "all"] = row
        out["valid"] = out["v1"] if indep else out["all"]
        return out


def regimes_table(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (load, label), g in df.groupby(["load", "label"]):
        r = {"load": int(load), "label": label, "n": len(g), "n_v1": int((g["run_block"] == "v1").sum()),
             "earth_independent": label in EARTH_INDEPENDENT}
        for k in REPORT:
            if k in g:
                r[k] = round(float(g[k].astype(float).mean()), 4)
        rows.append(r)
    return pd.DataFrame(rows)


def merge_backfill(df: pd.DataFrame) -> pd.DataFrame:
    """Per-owner columns of rows that ran before they existed, from results/E40_owner_backfill.csv (tools/atc/
    backfill_owner.py reran each row and checked every other column bit for bit)."""
    p = os.path.join(RES, "E40_owner_backfill.csv")
    if not os.path.isfile(p):
        return df
    bf = pd.read_csv(p, float_precision="round_trip")
    cols = [c for c in bf.columns if c.startswith("own_") and c != "own_teams"]
    m = df.merge(bf[KEYS + ["cell"] + cols], on=["cell"] + KEYS, how="left", suffixes=("", "_bf"))
    for c in cols:
        if c in df:
            m[c] = m[c].where(m[c].notna(), m[f"{c}_bf"])
        else:
            m[c] = m[f"{c}_bf"]
        m = m.drop(columns=f"{c}_bf")
    return m


def visibility_by_year(df: pd.DataFrame) -> Dict[int, float]:
    s = _sel(df, {"label": "B_EARTH strict"})
    return {int(y): round(float(1 - g["atc_decider_down_share"].mean()), 4) for y, g in s.groupby("start_year")}


def main() -> Dict[str, Any]:
    t0 = time.time()
    df = R.load_runs("E40")
    if df.empty:
        raise SystemExit("no E40 rows")
    df = merge_backfill(df)
    df = add_block(df)
    n = df.groupby(["load", "label", "run_block"]).size()
    print("E40 rows per cell (load, label, block):")
    print(n.unstack(fill_value=0).to_string())
    regimes_table(df).to_csv(os.path.join(RES, "table_E40_regimes.csv"), index=False, lineterminator="\n")
    fit: Dict[str, Any] = {"task": "B-75", "n_rows": int(len(df)),
                           "n_per_cell": {f"{l}|{lab}|{b}": int(v) for (l, lab, b), v in n.items()},
                           "metric": M, "bootstrap": B, "earth_independent": sorted(EARTH_INDEPENDENT),
                           "hypotheses": {}, "notes": []}
    P = Pairs(df)
    H = fit["hypotheses"]
    loads = sorted(int(x) for x in df["load"].unique())

    # every regime minus O (and the hopper sensitivity), at every load
    for L in loads:
        for lab in sorted(df[df["load"] == L]["label"].unique()):
            if lab != "O_ORACLE":
                P.add(f"{lab} - O_ORACLE", L, {"label": lab}, {"label": "O_ORACLE"})
    P.add("C_AUCTION hopper_refuel - C_AUCTION", 30, {"label": "C_AUCTION hopper_refuel"}, {"label": "C_AUCTION"})

    # H1 and its reported splits
    h1 = {}
    for L in (30, 60):
        r = P.add("H1: B_EARTH_RELAY 1.0 - A_EARTH full coverage", L, {"label": "B_EARTH_RELAY 1.0"},
                  {"label": "A_EARTH full coverage"})
        dl = P.add("H1 (reported): delivered-only urgent wait", L, {"label": "B_EARTH_RELAY 1.0"},
                   {"label": "A_EARTH full coverage"}, metric="atc_urgent_wait_mean_h")
        split = {}
        for o in ("A", "B", "C"):
            col = f"own_{o}_urgent_wait_cens_h"
            split[o] = P.add(f"H1 (reported): owner {o}", L, {"label": "B_EARTH_RELAY 1.0"},
                             {"label": "A_EARTH full coverage"}, metric=col)["valid"]
        v = r["valid"]
        h1[str(L)] = {"test": v, "delivered_only": dl["valid"], "by_owner": split,
                      "supported": (v["hi"] is not None and v["hi"] < 0) if v["n"] > 1 else None}
    H["H1"] = h1

    # H2
    vis = visibility_by_year(df)
    low = sorted(y for y, v in vis.items() if v < 0.60)
    h2 = {}
    for L in (30, 60):
        per = {}
        for y in low:
            r = P.add(f"H2: B_EARTH strict - O_ORACLE, {y}", L, {"label": "B_EARTH strict"}, {"label": "O_ORACLE"},
                      years=[y])["valid"]
            om = _sel(df, {"load": L, "label": "O_ORACLE", "start_year": y})[M].mean()
            r = dict(r, threshold=round(0.1 * float(om), 4) if np.isfinite(om) else None)
            r["passes"] = bool(r["lo"] is not None and r["threshold"] is not None and r["lo"] > r["threshold"])
            per[str(y)] = r
        pooled = P.add("H2: B_EARTH strict - O_ORACLE, pooled years", L, {"label": "B_EARTH strict"}, {"label": "O_ORACLE"})["valid"]
        om = _sel(df, {"load": L, "label": "O_ORACLE"})[M].mean()
        pooled = dict(pooled, threshold=round(0.1 * float(om), 4) if np.isfinite(om) else None)
        pooled["passes"] = bool(pooled["lo"] is not None and pooled["threshold"] is not None and pooled["lo"] > pooled["threshold"])
        extra = {}
        for lab in ("B_EARTH plan_ahead", "B_EARTH_RELAY 0.8"):
            rr = P.add(f"H2 (reported): {lab} - O_ORACLE", L, {"label": lab}, {"label": "O_ORACLE"})["valid"]
            if rr["n"] > 1:
                m10 = 0.1 * rr["b_mean"]
                rr = dict(rr, margin=round(m10, 4),
                          within_10pct_tost=bool(-m10 < rr["lo90"] and rr["hi90"] < m10),
                          direction="worse than O" if rr["lo"] > 0 else ("better than O" if rr["hi"] < 0 else "unclear"))
            extra[lab] = rr
        ao = P.add("H2 (not tested): A_EARTH strict - O_ORACLE (original yardstick)", L, {"label": "A_EARTH strict"},
                   {"label": "O_ORACLE"})["valid"]
        aod = P.add("H2 (not tested): A_EARTH strict - O_ORACLE, delivered-only (conditions on delivery)", L,
                    {"label": "A_EARTH strict"}, {"label": "O_ORACLE"}, metric="atc_urgent_wait_mean_h")["valid"]
        h2[str(L)] = {"low_visibility_years": low, "visibility": vis, "per_year": per, "pooled": pooled,
                      "plan_ahead_and_relay_0.8": extra,
                      "original_yardstick_half_A_minus_O": round(0.5 * ao["mean"], 4) if ao["mean"] is not None else None,
                      "delivered_only_A_minus_O": aod["mean"],
                      "supported": bool(pooled["passes"] and per and all(r["passes"] for r in per.values()))
                      if pooled["n"] > 1 else None}
    H["H2"] = h2

    # H3a
    r = P.add("H3a: C_AUCTION - O_ORACLE (TOST +-10 % of O)", 30, {"label": "C_AUCTION"}, {"label": "O_ORACLE"})["valid"]
    if r["n"] > 1:
        marg = 0.1 * r["b_mean"]
        eq = bool(-marg < r["lo90"] and r["hi90"] < marg)
        r = dict(r, margin=round(marg, 4), tost_equivalent=eq,
                 verdict="supported" if eq else "not supported as stated",
                 direction="better than O" if r["hi90"] < 0 else ("worse than O" if r["lo90"] > 0 else "both sides"))
    H["H3a"] = r

    # H4
    h4 = {}
    for pol in ("C_LEARNED_MLP", "C_LEARNED_LIN"):
        per = {}
        for L in (10, 30, 60):
            rr = P.add(f"H4: {pol} - C_AUCTION", L, {"label": pol}, {"label": "C_AUCTION"})["valid"]
            if rr["n"] > 1:
                if L == 10:
                    m2 = 0.02 * rr["b_mean"]
                    rr = dict(rr, margin=round(m2, 4), tost_equivalent=bool(-m2 < rr["lo90"] and rr["hi90"] < m2))
                else:
                    rr = dict(rr, beats_hand=bool(rr["hi"] < 0))
            per[str(L)] = rr
        h4[pol] = per
    H["H4"] = h4

    # E41 and E42 summaries; H6
    for exp in ("E41", "E42"):
        de = R.load_runs(exp)
        if de.empty:
            continue
        de = add_block(de)
        cols = [k for k in REPORT if k in de]
        summ = {lab: {"n": int(len(x)), **{k: round(float(x[k].mean()), 4) for k in cols}}
                for lab, x in de.groupby("label")}
        fit[exp] = {"n_rows": int(len(de)), "cells": summ}
    if "E42" in fit:
        de = add_block(R.load_runs("E42"))
        de["delivered_share"] = de["delivered_kg"] / de["ready_kg"]
        de["team_items_delivered_share"] = de["p5_team_items_delivered"] / de["p5_team_items"].replace(0, np.nan)
        P42 = Pairs(de)
        h6 = {}
        for team in ("10", "25"):
            for loss in ("0.1", "0.25", "0.4"):
                a = {"label": f"C_AUCTION team {team} any loss {loss}"}
                b = {"label": f"C_AUCTION team {team} same_owner loss {loss}"}
                h6[f"team {team} loss {loss}"] = {
                    "delivered_share": P42.add(f"H6: cross-owner - same owner, team {team}, loss {loss}", 30, a, b,
                                               metric="delivered_share")["valid"],
                    "team_items_delivered_share": P42.add(f"H6 (reported): team items, team {team}, loss {loss}", 30, a, b,
                                                          metric="team_items_delivered_share")["valid"]}
        cap = {team: P42.add(f"H1 split (E42): C_AUCTION same owner - A_EARTH own teams, team {team}, loss 0.1", 30,
                             {"label": f"C_AUCTION team {team} same_owner loss 0.1"},
                             {"label": f"A_EARTH strict own teams team {team}"})["valid"] for team in ("00", "10", "25")}
        meet = {}
        for loss in ("0.1", "0.25", "0.4"):
            for lab in (f"C_AUCTION team 25 any loss {loss}", f"C_AUCTION team 25 any loss {loss} no commit",
                        f"C_AUCTION team 25 any loss {loss} arbitrated (exploratory)",
                        f"C_AUCTION team 25 any loss {loss} timeout 0.5", f"C_AUCTION team 25 any loss {loss} timeout 2"):
                x = de[de["label"] == lab]
                if len(x):
                    meet[lab] = {"n": int(len(x)), **{k: round(float(x[k].mean()), 4) for k in
                                 ("atc_failed_meetings", "atc_team_no_agreement", "atc_meeting_wait_h", "team_lifts",
                                  "p5_team_items_delivered", M) if k in x}}
        main6 = h6["team 25 loss 0.1"]["delivered_share"]
        H["H6"] = {"test": main6, "supported": bool(main6["lo"] is not None and main6["lo"] > 0),
                   "grid": h6, "capacity_split_same_owner_pool_vs_alone": cap, "meetings": meet}
        # H1 split (LEAD, B-75): full Earth coverage, block v1, team share 0.10, loss 0.10; pairs by seed and year
        a_full = df[(df["load"] == 30) & (df["label"] == "A_EARTH full coverage") & (df["run_block"] == "v1")]
        same = de[(de["label"] == "C_AUCTION team 10 same_owner loss 0.1") & (de["run_block"] == "v1")]
        cross = de[(de["label"] == "C_AUCTION team 10 any loss 0.1") & (de["run_block"] == "v1")]
        tot_rows = df[(df["load"] == 30) & (df["label"] == "B_EARTH_RELAY 1.0") & (df["run_block"] == "v1")]
        jd = same[KEYS + [M]].merge(a_full[KEYS + [M]], on=KEYS, suffixes=("_p", "_a"))
        jc = cross[KEYS + [M]].merge(same[KEYS + [M]], on=KEYS, suffixes=("_x", "_s"))
        jt = tot_rows[KEYS + [M]].merge(a_full[KEYS + [M]], on=KEYS, suffixes=("_b", "_a"))
        disp, capd, tot = (jd[f"{M}_p"] - jd[f"{M}_a"]), (jc[f"{M}_x"] - jc[f"{M}_s"]), (jt[f"{M}_b"] - jt[f"{M}_a"])
        note = ("pooled side = the on-Moon auction (C_AUCTION, loss 0.10; E42 has no B regime), so the dispatch part "
                "includes any auction-vs-marketplace difference (the v1 C_AUCTION - O_ORACLE row is not "
                "distinguishable from 0); A side = E40 cell 38 (A_EARTH full coverage, own teams), paired by seed")
        split = {}
        for name, d in (("H1 dispatch part: C_AUCTION same-owner teams - A_EARTH full coverage", disp),
                        ("H1 capacity part: C_AUCTION cross-owner - C_AUCTION same-owner teams", capd),
                        ("H1 total (E40): B_EARTH_RELAY 1.0 - A_EARTH full coverage", tot)):
            bb = boot(d.to_numpy(float))
            split[name] = bb
        sum_parts = (split["H1 dispatch part: C_AUCTION same-owner teams - A_EARTH full coverage"]["mean"] or 0) + \
                    (split["H1 capacity part: C_AUCTION cross-owner - C_AUCTION same-owner teams"]["mean"] or 0)
        for name, bb in split.items():
            share = round(bb["mean"] / sum_parts, 4) if sum_parts and "part" in name else None
            P.rows.append({"comparison": name, "load": 30, "metric": M, "block": "v1", "pseudo_replicated": False,
                           "valid": True, "n": bb["n"], "mean": bb["mean"], "lo": bb["ci"][0] if bb["ci"] else None,
                           "hi": bb["ci"][1] if bb["ci"] else None, "lo90": bb["ci90"][0] if bb["ci90"] else None,
                           "hi90": bb["ci90"][1] if bb["ci90"] else None, "p": bb["p"], "b_mean": None,
                           "share_of_b": share, "note": note})
        H["H1"]["split_30"] = {"parts": split, "sum_of_parts": round(sum_parts, 4), "note": note,
                               "share_dispatch": round(split["H1 dispatch part: C_AUCTION same-owner teams - A_EARTH full coverage"]["mean"] / sum_parts, 4) if sum_parts else None,
                               "share_capacity": round(split["H1 capacity part: C_AUCTION cross-owner - C_AUCTION same-owner teams"]["mean"] / sum_parts, 4) if sum_parts else None}
        fit["pairs_E42"] = P42.rows
    # Holm across the confirmatory family at 30 % (H3a is an equivalence claim, outside it)
    fam = {"H1": h1["30"]["test"]["p"], "H2": h2["30"]["pooled"]["p"],
           "H4_MLP": h4["C_LEARNED_MLP"]["30"]["p"], "H4_LIN": h4["C_LEARNED_LIN"]["30"]["p"],
           "H6": H.get("H6", {}).get("test", {}).get("p")}
    ps = sorted((v, k) for k, v in fam.items() if v is not None)
    holm, run_max = {}, 0.0
    for i, (p, k) in enumerate(ps):
        run_max = max(run_max, min(1.0, (len(ps) - i) * p))
        holm[k] = round(run_max, 6)
    fit["holm_30pct"] = {"raw_p": fam, "adjusted_p": holm,
                         "note": "two-sided bootstrap p; a small p supports a hypothesis only in its predicted "
                                 "direction (check the sign of each row's mean)"}
    fit["notes"] += ["cells 38-39 (A_EARTH full coverage) were added to the runner before any of their rows ran; "
                     "they are the yardstick PREREG H1 names (LEAD, 27 Oct)",
                     "block v1 = start_year == 2028 + seed mod 4; Earth-independent regimes repeat v1 seeds 1-10 in "
                     "block v3, so comparisons between two of them use v1 only (pseudo_replicated rows flagged)"]
    pd.DataFrame(P.rows + fit.get("pairs_E42", [])).to_csv(os.path.join(RES, "table_E40_pairs.csv"), index=False,
                                                          lineterminator="\n")
    fit.pop("pairs_E42", None)
    fit["wall_s"] = round(time.time() - t0, 1)
    with open(os.path.join(RES, "E40_fit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(fit, f, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
        f.write("\n")
    return fit


if __name__ == "__main__":
    f = main()
    H = f["hypotheses"]
    short = lambda r: (r.get("mean"), r.get("lo"), r.get("hi"), r.get("n"))
    print(json.dumps({
        "H1": {L: {"test": short(x["test"]), "delivered_only": short(x["delivered_only"]),
                   "by_owner": {o: short(v) for o, v in x["by_owner"].items()}, "supported": x["supported"]}
               for L, x in H["H1"].items() if L != "split_30"},
        "H1_split": {k: (v["mean"], v["ci"]) for k, v in H["H1"].get("split_30", {}).get("parts", {}).items()},
        "H2": {L: {"pooled": short(x["pooled"]) + (x["pooled"].get("threshold"),), "supported": x["supported"],
                   "plan/relay": {k: short(v) + (v.get("direction"),) for k, v in x["plan_ahead_and_relay_0.8"].items()}}
               for L, x in H["H2"].items()},
        "H3a": (short(H["H3a"]), H["H3a"].get("lo90"), H["H3a"].get("hi90"), H["H3a"].get("verdict"), H["H3a"].get("direction")),
        "H4": {p: {L: short(r) for L, r in v.items()} for p, v in H["H4"].items()},
        "H6": {"test": short(H["H6"]["test"]), "supported": H["H6"]["supported"],
               "capacity_split": {t: short(v) for t, v in H["H6"]["capacity_split_same_owner_pool_vs_alone"].items()}} if "H6" in H else None,
        "holm": f["holm_30pct"]["adjusted_p"]}, indent=1, default=str))
