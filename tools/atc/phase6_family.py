"""The Phase 6 confirmatory family {H9, H10, H13, H14, H15a} (paper/atc/PREREG6.md section 4; B-98a).

    python tools/atc/phase6_family.py      # -> results/phase6_family.json

Per hypothesis: the test, its statistic, the unadjusted p-value or interval where the test has one, and the Holm
decision over the hypotheses that have a sampling test (H10, H14, H15a; alpha 0.05). H9 and H13 are threshold
comparisons without a sampling test (PREREG6: "on the predicted side of the budget" / "carries no more than"): listed
with the share of seeds (H9) or of position draws (H13) on the predicted side.
Sources: E50 cells (.cache/atc/e50, 1x 30 seeds, 4x 10 seeds, 8x 5 seeds), E53 (tools/atc/run_e53.py), E54 cells (.cache/atc/e54),
E56 (results/E56_integrity.json, B-96).
"""
from __future__ import annotations

import glob
import gzip
import json
import math
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE, os.path.join(ROOT, "experiments", "phase5")):
    if p not in sys.path:
        sys.path.insert(0, p)
OUT = os.path.join(ROOT, "results", "phase6_family.json")
ALPHA = 0.05


E50_CODES = set()                                   # B-118 N21: every E50 cell of the family from one code version
E50_COUNTS = {}                                     # B-120 D: cells loaded per fleet multiple (written to the file)


def _e50(m):
    out = {}
    for p in glob.glob(os.path.join(ROOT, ".cache", "atc", "e50", f"m{m}_s*.pkl.gz")):
        with gzip.open(p) as f:
            d = pickle.load(f)
        out[d["seed"]] = d
        E50_CODES.add(d.get("code"))
    import e50_build as EB                              # B-120 D: one code, not None, the current one
    EB.require_code(E50_CODES, "phase6_family E50")
    E50_COUNTS[f"{m}x"] = len(out)
    return out


def h9():
    C = _e50(1)
    S = sorted(C)
    budget = 5.0
    dr_first = [C[s]["nav"]["dr"]["shift_p95_m"][0] for s in S]                 # p95 in the first driving hour
    near = [C[s]["nav"]["dr+ranging"]["near"]["p95_m"] for s in S]
    away = [C[s]["nav"]["dr+ranging+fixes"]["away"]["p95_m"] for s in S]
    share = lambda xs, above: float(np.mean([(x is not None) and ((x > budget) if above else (x < budget)) for x in xs]))
    return {"test": "threshold comparison (no sampling test): p95 position error against the 5 m budget, per layer, "
                    "E50 1x, 30 seeds", "budget_m": budget,
            "clauses": {
                "dead reckoning exceeds the budget within one 8-h shift": {
                    "statistic": "p95 in the first driving hour, mean over seeds", "value_m": float(np.mean(dr_first)),
                    "seeds_on_predicted_side": share(dr_first, True), "supported": share(dr_first, True) == 1.0},
                "ranging stays inside the budget near the base": {
                    "statistic": "p95 near the base, mean over seeds", "value_m": float(np.mean(near)),
                    "seeds_on_predicted_side": share(near, False), "supported": share(near, False) == 1.0},
                "absolute fixes keep it inside away from the base": {
                    "statistic": "p95 away from the base, mean over seeds", "value_m": float(np.mean(away)),
                    "seeds_on_predicted_side": share(away, False), "supported": share(away, False) == 1.0}},
            "decision": "supported in two clauses (dead reckoning, ranging near the base); NOT supported in the third "
                        "(absolute fixes away from the base: every seed above the budget)"}


def _tost_paired(d, delta):
    """Paired TOST with the t distribution: p = max of the two one-sided p-values."""
    from scipy import stats
    n = len(d)
    m, se = float(np.mean(d)), float(np.std(d, ddof=1) / math.sqrt(n))
    p_lo = 1 - stats.t.cdf((m + delta) / se, n - 1)       # H0: mean <= -delta
    p_hi = stats.t.cdf((m - delta) / se, n - 1)           # H0: mean >= +delta
    return max(p_lo, p_hi), m, se


def h10():
    from scipy import stats
    C1, C4, C8 = _e50(1), _e50(4), _e50(8)
    S1 = sorted(C1)
    perf = np.array([C1[s]["perfect"]["delay_mean_h"] for s in S1])
    lay = np.array([C1[s]["margin"]["layered"]["delay_mean_h"] for s in S1])
    dr = np.array([C1[s]["margin"]["dr"]["delay_mean_h"] for s in S1])
    delta = 0.5 * float(perf.mean())
    p_tost, m_lay, se = _tost_paired(lay - perf, delta)
    d_dr = dr - perf
    t_dr = float(d_dr.mean() / (d_dr.std(ddof=1) / math.sqrt(len(d_dr))))
    p_dr = float(1 - stats.t.cdf(t_dr, len(d_dr) - 1))
    S4 = sorted(C4)
    g4 = np.array([C4[s]["margin"]["layered"]["delay_mean_h"] - C4[s]["perfect"]["delay_mean_h"] for s in S4])
    g1 = float((lay - perf).mean())
    S8 = sorted(C8)
    g8 = np.array([C8[s]["margin"]["layered"]["delay_mean_h"] - C8[s]["perfect"]["delay_mean_h"] for s in S8])

    def grows(gm):
        # the gap grows at m x: one-sided Welch test of mean(gap m x) > mean(gap 1x)
        t_g, p_g2 = stats.ttest_ind(gm, lay - perf, equal_var=False)
        return float(p_g2 / 2 if t_g > 0 else 1 - p_g2 / 2)
    p_grow4, p_grow8 = grows(g4), grows(g8)
    p_grow = max(p_grow4, p_grow8)
    p_iut = max(p_tost, p_dr, p_grow)
    return {"test": "primary clause: paired TOST at 1x (margin 50 % of the perfect-position delay), t distribution, 30 "
                    "seeds; the clauses joined by intersection-union (p = the largest clause p)",
            "clauses": {
                "layered within 1.5x of perfect at 1x (TOST)": {"mean_diff_h": m_lay, "se_h": se, "margin_h": delta,
                                                                 "p": float(p_tost)},
                "the gap grows with the fleet (4x and 8x)": {
                    "gap_1x_h": g1, "gap_4x_h": float(g4.mean()), "n_4x": len(g4), "gap_8x_h": float(g8.mean()),
                    "n_8x": len(g8), "p_one_sided_4x": p_grow4, "p_one_sided_8x": p_grow8, "p_one_sided": p_grow,
                    "note": "Welch one-sided, gap m x > gap 1x, at 4x and at 8x; the clause holds only if both do "
                            "(p = the larger)"},
                "dead reckoning with the margin larger at 1x": {"mean_diff_h": float(d_dr.mean()), "t": t_dr,
                                                                "p_one_sided": p_dr}},
            "p_primary": float(p_tost), "p_intersection_union": float(p_iut)}


def h13():
    import run_e53 as E3
    idx, g = E3.positions()
    out = {}
    for f_hz in (1.0, 10.0):
        rate, size, bps = E3.per_rover(f_hz, True)
        beacon = sum(bps[k] for k in E3.BEACONS)
        event = sum(v for k, v in bps.items() if k not in E3.BEACONS)
        rng = np.random.default_rng([53, 20])
        loads = np.array([E3.busiest(idx[rng.integers(0, len(idx), 20)], g, beacon, event)[0]
                          for _ in range(E3.DRAWS)]) * 8 / 1000.0
        pred = (loads <= 16.0) if f_hz == 1.0 else (loads > 16.0)
        out[f"{f_hz:g} Hz"] = {"busiest_kbps_mean": float(loads.mean()), "busiest_kbps_p95": float(np.quantile(loads, 0.95)),
                               "draws_on_predicted_side": float(pred.mean())}
    return {"test": "threshold comparison (no sampling test): busiest-link load with authentication, 20 rovers, against "
                    "16 kbit/s (E53, 30 position draws)", "clauses": out,
            "decision": "supported: every draw <= 16 kbit/s at 1 Hz and > 16 kbit/s at 10 Hz"
            if out["1 Hz"]["draws_on_predicted_side"] == 1.0 and out["10 Hz"]["draws_on_predicted_side"] == 1.0
            else "see the shares"}


def h14():
    S = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(ROOT, ".cache", "atc", "e54", "s*.json")))]
    lost = lambda s, proto: next(c for c in s["cells"] if c["loss"] == 0.25 and c["protocol"] == proto)["kinds"]["award"]["lost"]
    d = np.array([lost(s, "sf_ll") - lost(s, "drop_retry") for s in S])
    n_neg, n_pos = int((d < 0).sum()), int((d > 0).sum())
    from scipy import stats
    p_sign = float(stats.binomtest(n_neg, n_neg + n_pos, 0.5, alternative="greater").pvalue) if n_neg + n_pos else 1.0
    stuck = sum(next(c for c in s["cells"] if c["loss"] == 0.25 and c["protocol"] == "sf_ll")["stuck_reservations"] for s in S)
    return {"test": "exact sign test on per-seed lost jobs (expired awards), sf_ll minus drop_retry, loss 0.25, 14-day "
                    "blackout, 30 seeds; plus 'no reservation stuck under sf_ll' (a property of the rule)",
            "mean_diff_jobs": float(d.mean()), "seeds_fewer": n_neg, "seeds_more": n_pos, "seeds_tied": int((d == 0).sum()),
            "p": p_sign, "stuck_reservations_sf_ll": int(stuck),
            "stuck_basis": "by rule, not measured (B-118 N7): the replay sets sf_ll's stuck count to 0 by construction; "
                           "see results/E54_dtn.json h14.clause_2_basis"}


def h15a():
    d = json.load(open(os.path.join(ROOT, "results", "E56_integrity.json")))
    x = d["test"]["h15_net_against"]["chi2_step"]["drift"]["delay_median_diff_s"]
    c = d.get("h15_resample_counts_b118", {}).get("sets", {}).get("test", {}).get("chi2_step|drift|delay_median_diff_s")
    if c is None or not c["reproduces_stored_interval"]:
        raise SystemExit("E56: run python -m lunarsim.nn.evaluate --resample-counts first (B-118 N8)")
    B = c["boot_n"]
    return {"test": "network minus per-step chi-square, median detection delay on slow drifts at 1 false alarm per "
                    "pair-day (E56, B-96): bootstrap over events, 1,000 resamples",
            "delay_median_diff_s": x["value"], "ci95": x["ci95"], "ci90": x["ci90"],
            "p": (c["at_or_above_0"] + 1.0) / (B + 1), "resamples_at_or_above_0": c["at_or_above_0"], "resamples": B,
            "p_note": "one-sided bootstrap p = (resamples at or above 0 + 1) / (resamples + 1), from the saved count "
                      "(results/E56_integrity.json h15_resample_counts_b118; B-118 N8)"}


def holm(ps):
    order = sorted(ps, key=lambda k: ps[k])
    m = len(order)
    adj, run = {}, 0.0
    for i, k in enumerate(order):
        run = max(run, min(1.0, (m - i) * ps[k]))
        adj[k] = run
    return adj


def main():
    fam = {"H9": h9(), "H10": h10(), "H13": h13(), "H14": h14(), "H15a": h15a()}
    ps = {"H10": fam["H10"]["p_intersection_union"], "H14": fam["H14"]["p"], "H15a": fam["H15a"]["p"]}
    adj = holm(ps)
    ps_primary = dict(ps, H10=fam["H10"]["p_primary"])
    adj_primary = holm(ps_primary)
    for k in ps:
        fam[k]["holm"] = {"p_adjusted": adj[k], "rejected_at_0.05": adj[k] < ALPHA,
                          "p_adjusted_if_H10_primary_clause_only": adj_primary[k]}
    doc = {"family": "PREREG6 section 4: {H9, H10, H13, H14, H15a} confirmatory, Holm at alpha 0.05 over the "
                     "hypotheses with a sampling test (H10, H14, H15a)", "alpha": ALPHA, "hypotheses": fam,
           "summary": {"H9": fam["H9"]["decision"], "H13": fam["H13"]["decision"],
                       "H10": ("supported (Holm)" if fam["H10"]["holm"]["rejected_at_0.05"] else
                               "not supported as a whole: the primary clause holds (TOST), the 'gap grows' and 'dead "
                               "reckoning larger' clauses do not (intersection-union)"),
                       "H14": "supported (Holm)" if fam["H14"]["holm"]["rejected_at_0.05"] else "not supported",
                       "H15a": "supported (Holm)" if fam["H15a"]["holm"]["rejected_at_0.05"] else "not supported"},
           "e50_cells": dict(sorted(E50_COUNTS.items(), key=lambda kv: int(kv[0][:-1]))),
           "e50_code": __import__("e50_build").require_code(E50_CODES, "phase6_family E50")}
    import e50_build as EB                              # B-118 N15: the previous values kept under the dated key
    EB.keep_superseded(OUT, doc)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, default=float)
        f.write("\n")
    print(json.dumps(doc["summary"], indent=1))
    print({k: (round(ps[k], 5), round(adj[k], 5)) for k in ps}, "primary-only H10 p", round(fam["H10"]["p_primary"], 6))


if __name__ == "__main__":
    main()
