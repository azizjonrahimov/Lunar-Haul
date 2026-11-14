"""E50 build (B-90): cell caches of tools/atc/run_e50.py -> results/E50_errors.csv, E50_runs.csv, E50_summary.json,
E50_trace.json. Called by `python tools/atc/run_e50.py build`.

Statistics (paper/atc/PREREG6.md, PREREG.md general rules): per cell (fleet multiple, seed) one value per outcome; over
seeds, means with percentile bootstrap 95 % CIs (20,000 resamples); paired differences on common seeds; TOST at 90 %
for "within".
H9 (per layer set and region): supported for dead reckoning if the p95 error exceeds the 5 m budget within one 8-hour
shift of driving (the first driving hour whose p95, over seeds, is above the budget is <= 8); for ranging if the p95
error near the base (in view of >= 2 beacons) is inside the budget; for absolute fixes if the p95 error away from the
base is inside the budget. "On the predicted side" = the bootstrap CI of the mean p95 over seeds lies on that side.
H10: at 1x, delay per delivery with the layered margin minus perfect position, TOST with margin 50 % of the perfect
delay (supported if the 90 % CI lies inside the margin); the gap at 4x and 8x vs 1x (reported); dead reckoning with
the margin minus perfect: CI excluding zero.
"""
from __future__ import annotations

import csv
import glob
import gzip
import json
import math
import os
import pickle

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(ROOT, ".cache", "atc", "e50")
B = 20000
SUPERSEDED_KEY = "superseded_2026-11-13_b118_n15"
SUPERSEDED_REASON = ("B-118 N14/N15 (positioning fix in lunarsim/atc/pnt.py: a ranging or fix update at a vehicle's "
                     "arrival step, and the reservation count): the values below were made with the code before the "
                     "fix and are kept as they were; the file's other values come from the regenerated cells")


def keep_superseded(path, doc, design_multiples=None, built_multiples=None):
    """B-118 N15: carry the previous file's values into doc under SUPERSEDED_KEY (once: a later rebuild keeps the key
    it finds, so the pre-fix values are never overwritten by a partial rebuild), carry any older superseded_* keys,
    and list the design's fleet multiples not yet rerun (their pre-fix values stay only under SUPERSEDED_KEY)."""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            old = json.load(f)
        for k, v in old.items():
            if k.startswith("superseded_"):
                doc.setdefault(k, v)
        if SUPERSEDED_KEY not in doc:
            doc[SUPERSEDED_KEY] = {"reason": SUPERSEDED_REASON, "superseded_on": "2026-11-13",
                                   **{k: v for k, v in old.items() if not k.startswith("superseded_")}}
    if design_multiples is not None:
        built = {int(m) for m in (built_multiples or [])}
        doc["multiples_not_rerun_yet"] = [m for m in design_multiples if m not in built]
    return doc


def _load(p):
    with gzip.open(p, "rb") as f:
        return pickle.load(f)


def boot_mean(x, seed=0, level=0.95):
    x = np.asarray([v for v in x if v is not None and np.isfinite(v)], float)
    if len(x) == 0:
        return {"n": 0, "mean": None, "ci": [None, None]}
    if len(x) == 1:
        return {"n": 1, "mean": float(x[0]), "ci": [None, None]}
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), (B, len(x)))].mean(axis=1)
    a = (1 - level) / 2
    return {"n": int(len(x)), "mean": float(x.mean()), "ci": [float(np.quantile(m, a)), float(np.quantile(m, 1 - a))]}


def cells():
    out = {}
    for p in sorted(glob.glob(os.path.join(CACHE, "m*_s*.pkl.gz"))):
        d = _load(p)
        out[(int(d["mult"]), int(d["seed"]))] = d
    codes = {d.get("code") for d in out.values()}               # B-118 N21: never mix cells made with other code
    if len(codes) > 1:
        raise SystemExit(f"E50 cells made with different code: {sorted(codes, key=str)}; rerun the stale cells")
    return out


def build():
    import run_e50 as R
    D = R.DESIGN
    C = cells()
    if not C:
        raise SystemExit("no E50 cells in .cache/atc/e50")
    sets = list(D["layer_sets"]) + ["lans@2030"]
    regions = ("all", "near", "away", "parked")
    # ---------------------------------------------------------------- per-cell tables
    err_rows, run_rows = [], []
    for (m, s), d in sorted(C.items()):
        for ls in sets:
            v = d["nav"][ls]
            for rg in regions:
                e = v[rg]
                err_rows.append({"mult": m, "seed": s, "layer_set": ls, "region": rg, "n_steps": e.get("n", 0),
                                 **{k: (round(e[k], 4) if k in e else "") for k in
                                    ("median_m", "p95_m", "max_m", "b95_median_m", "b95_p95_m",
                                     "share_b95_over_budget", "share_err_over_budget")},
                                 "fixes": v["counts"]["fixes"], "fix_stop_h": round(v["counts"]["fix_stop_h"], 3),
                                 "range_updates": v["counts"]["range_updates"],
                                 "violations_no_margin": v["violations_no_margin"]["violations"]})
        run_rows.append({"mult": m, "seed": s, "variant": "perfect", "layer_set": "", "delay_mean_h": d["perfect"]["delay_mean_h"],
                         "delivered": d["perfect"]["delivered"], "urgent_delay_mean_h": d["perfect"]["urgent_delay_mean_h"],
                         "road_wait_h": d["perfect"]["road_wait_h"], "reservations": d["perfect"]["reservations"],
                         "margin_h_mean": 0.0, "violations": 0, "overlap_s": 0.0, "fix_stop_h": 0.0})
        for lab, v in d["margin"].items():
            run_rows.append({"mult": m, "seed": s, "variant": f"margin_{lab}", "layer_set": v["layer_set"],
                             "delay_mean_h": v["delay_mean_h"], "delivered": v["delivered"],
                             "urgent_delay_mean_h": v["urgent_delay_mean_h"], "road_wait_h": v["road_wait_h"],
                             "reservations": v["reservations"], "margin_h_mean": v["margin_h_mean"],
                             "violations": v["violations"]["violations"], "overlap_s": v["violations"]["overlap_s"],
                             "fix_stop_h": v.get("fix_stop_h", 0.0)})
    for path, rows in ((R.OUT_ERR, err_rows), (R.OUT_RUNS, run_rows)):
        with open(path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            for r in rows:
                w.writerow({k: (round(v, 6) if isinstance(v, float) and math.isfinite(v) else v) for k, v in r.items()})
    # ---------------------------------------------------------------- summary
    mults = sorted({m for m, _ in C})
    summ = {"experiment": D["experiment"], "design": {k: v for k, v in D.items() if k != "experiment"},
            "seeds": {str(m): sorted(s for mm, s in C if mm == m) for m in mults}, "errors": {}, "violations": {},
            "delay": {}, "h9": {}, "h10": {}}
    budget = D["budget_m"]
    for m in mults:
        S = sorted(s for mm, s in C if mm == m)
        em = {}
        for ls in sets:
            em[ls] = {}
            for rg in regions:
                vals = [C[(m, s)]["nav"][ls][rg] for s in S]
                em[ls][rg] = {k: boot_mean([v.get(k) for v in vals], seed=1) for k in
                              ("median_m", "p95_m", "max_m", "share_b95_over_budget")}
            sh = np.array([[np.nan if x is None else x for x in C[(m, s)]["nav"][ls]["shift_p95_m"]] for s in S], float)
            em[ls]["shift_p95_m_mean_over_seeds"] = [None if np.all(np.isnan(c)) else round(float(np.nanmean(c)), 3)
                                                     for c in sh.T]
            em[ls]["fix_stop_h_per_month"] = boot_mean([C[(m, s)]["nav"][ls]["counts"]["fix_stop_h"] for s in S], seed=2)
        summ["errors"][str(m)] = em
        summ["violations"][str(m)] = {
            "no_margin": {ls: boot_mean([C[(m, s)]["nav"][ls]["violations_no_margin"]["violations"] for s in S], seed=3)
                          for ls in sets},
            "with_margin": {lab: boot_mean([C[(m, s)]["margin"][lab]["violations"]["violations"] for s in S], seed=4)
                            for lab in D["margin_sets"]}}
        perf = np.array([C[(m, s)]["perfect"]["delay_mean_h"] for s in S], float)
        dl = {"perfect": boot_mean(perf, seed=5)}
        for lab in D["margin_sets"]:
            x = np.array([C[(m, s)]["margin"][lab]["delay_mean_h"] for s in S], float)
            dl[f"margin_{lab}"] = boot_mean(x, seed=6)
            dl[f"margin_{lab}_minus_perfect"] = boot_mean(x - perf, seed=7)
            dl[f"margin_{lab}_minus_perfect_90"] = boot_mean(x - perf, seed=7, level=0.90)
            dl[f"margin_{lab}_road_wait_h"] = boot_mean([C[(m, s)]["margin"][lab]["road_wait_h"] for s in S], seed=8)
            dl[f"margin_{lab}_margin_h_mean"] = boot_mean([C[(m, s)]["margin"][lab]["margin_h_mean"] for s in S], seed=9)
        dl["perfect_road_wait_h"] = boot_mean([C[(m, s)]["perfect"]["road_wait_h"] for s in S], seed=8)
        summ["delay"][str(m)] = dl
    # ---------------------------------------------------------------- H9
    for m in mults:
        em = summ["errors"][str(m)]
        dr_sh = em["dr"]["shift_p95_m_mean_over_seeds"]
        first = next((h + 1 for h, v in enumerate(dr_sh[:-1]) if v is not None and v > budget), None)
        rng_near = em["dr+ranging"]["near"]["p95_m"]
        fx_away = em["dr+ranging+fixes"]["away"]["p95_m"]

        def side(b, below):
            if b["ci"][0] is None:
                return None
            return bool(b["ci"][1] < budget) if below else bool(b["ci"][0] > budget)
        summ["h9"][str(m)] = {
            "budget_m": budget,
            "dr_first_driving_hour_p95_over_budget": first,
            "dr_supported": bool(first is not None and first <= D["shift_h"]),
            "ranging_near_p95_m": rng_near, "ranging_near_supported": side(rng_near, True),
            "fixes_away_p95_m": fx_away, "fixes_away_supported": side(fx_away, True),
            "rule": "dr: first driving hour (since the window start) whose p95 over seeds exceeds the budget is <= 8; "
                    "ranging / fixes: the 95 % CI of the mean p95 over seeds lies below the budget"}
    # ---------------------------------------------------------------- H10
    if 1 in mults:
        d1 = summ["delay"]["1"]
        p = d1["perfect"]["mean"]
        ci90 = d1["margin_layered_minus_perfect_90"]["ci"]
        tost = None if ci90[0] is None else bool(-0.5 * p < ci90[0] and ci90[1] < 0.5 * p)
        dr_ci = d1["margin_dr_minus_perfect"]["ci"]
        summ["h10"] = {
            "perfect_delay_1x_h": p, "tost_margin_h": 0.5 * p,
            "layered_minus_perfect_1x_90ci": ci90, "layered_within_supported": tost,
            "ratio_layered_over_perfect_1x": (d1["margin_layered"]["mean"] / p) if p else None,
            "dr_minus_perfect_1x_95ci": dr_ci,
            "dr_larger_supported": None if dr_ci[0] is None else bool(dr_ci[0] > 0),
            "gap_by_mult": {str(m): summ["delay"][str(m)]["margin_layered_minus_perfect"] for m in mults},
            "note": "the layered scheme's terrain-fix stops (fix_stop_h) are not in the engine's delay; they are "
                    "reported per month in errors.<mult>.<set>.fix_stop_h_per_month"}
    keep_superseded(R.OUT_JSON, summ, D["multiples"], mults)
    with open(R.OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summ, f, indent=1, allow_nan=False, default=lambda x: None)
        f.write("\n")
    # ---------------------------------------------------------------- site trace (1x, seed 1)
    tp = os.path.join(CACHE, "trace_m1_s1.pkl.gz")
    if os.path.isfile(tp):
        tr = _load(tp)
        drive = (np.asarray(tr["ds"]) > 0).sum(axis=0)
        pick = [int(i) for i in np.argsort(-drive)[:2]]
        t_h = np.asarray(tr["t_h"])
        per = 30                                    # 30 min bins (60 s steps)
        nb = len(t_h) // per
        doc = {"format": "lunarsim-e50-trace", "version": 1, "experiment": "E50 (B-90)", "mult": 1, "seed": 1,
               "t0_h": float(t_h[0]), "bin_min": per * float(R.DESIGN["dt_s"]) / 60.0, "budget_m": budget,
               "fields": "per vehicle: xy_m [[x, y], ...] at each bin start; per layer set: err_m and b95_m, the "
                         "maximum over each bin, 0.1 m",
               "vehicles": {}}
        for n in pick:
            vid = int(tr["ids"][n])
            xy = np.asarray(tr["xy"])[:nb * per:per, n]
            v = {"xy_m": [[int(round(a)), int(round(b))] for a, b in xy], "drive_h": round(float(drive[n]) / 60.0, 2),
                 "sets": {}}
            for ls, (err, b95) in tr["sets"].items():
                e = np.asarray(err)[:nb * per, n].reshape(nb, per).max(axis=1)
                b = np.asarray(b95)[:nb * per, n].reshape(nb, per).max(axis=1)
                v["sets"][ls] = {"err_m": [round(float(x), 1) for x in e], "b95_m": [round(float(x), 1) for x in b]}
            doc["vehicles"][str(vid)] = v
        with open(R.OUT_TRACE, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f, separators=(",", ":"))
            f.write("\n")
    print(json.dumps({"cells": len(C), "h9": summ["h9"], "h10": summ["h10"]}, indent=1, default=str))
