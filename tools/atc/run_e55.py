"""E55 (B-95, Phase 6, H15 baseline and H16): authentication, the LRIP integrity rule, and consensus with liars.

    python tools/atc/run_e55.py auth          # -> .cache/atc/e55/auth.json        (about a minute)
    python tools/atc/run_e55.py integrity     # -> .cache/atc/e55/integrity.json   (loads B-96's splits one at a time)
    python tools/atc/run_e55.py consensus     # -> .cache/atc/e55/consensus.json
    python tools/atc/run_e55.py build         # -> results/E55_integrity.json, results/E55_table.csv

(1) Forgeries with t = 8 and 16 bit truncated AES-CMAC (measured acceptance against 2^-t); 64 and 128 bits by the
    formula (note 03 E4). Replays with the counter and the 10 s freshness rule: 20 senders at 1 Hz, 10 receivers,
    loss 0.10 / 0.25, 10 minutes, a replay a second: a random earlier message of the whole recorded log (usually
    minutes old), stamped 0 to 60 s after the replay event. Added after the code review of 13 Nov 2026 (B-118 N9,
    key "replay_recent"): the same set-up with each replay drawn from the messages sent in the last 60 s, so its age
    is 0 to 60 s; accepted replays split into "missed the original, inside the 10 s window" and the rest.
(2) The LRIP rule of note 03 C8 as written (z^2 > gamma, 3 of the last 5 flagged) on B-96's validation, test and
    out-of-distribution streams (data/atc/integrity/cache, lunarsim.nn.dataset.load; the same faults as E56), at alpha
    1e-2 / 1e-3 / 1e-4 with the theoretical gamma (no threshold tuned on any data), and the single test at the same
    gamma; event recall per fault type, median delay, false alarms per pair-day (B-96's lunarsim.nn.baselines.detect /
    fa_per_day, stratum-weighted as in E56). E56's validation-calibrated chi-square and network at 1 false alarm per
    pair-day are quoted beside them.
(3) W-MSR (note 03 E6): N rovers in {5, 8, 12, 20, 40} at positions drawn from the 1x fleet's trajectories ("fleet")
    or uniform over the route samples ("spread"), links by DEM line of sight (B-70 mesh, 2.5 m antennas); honest
    values = a beacon coordinate estimate N(0, 1 m); f in {0, 1, 2} faulty rovers sending polarising values (+-50 m);
    W-MSR with F = 1 and F = f; 60 synchronous steps; 50 runs a cell. Safety = every honest value stays inside the
    initial honest range at every step; agreement = the final honest range below 1 % of the initial one. Robustness:
    exact (2F+1)- and (F+1)-robustness for N <= 8, the degree condition (every honest node hears >= 2F + 1) for all.
H16 (PREREG6): with f faulty rovers the trimmed-mean rule keeps the agreed value inside the honest range whenever the
mesh is (2f+1)-robust, in every run; when it is not, at least one run leaves the range.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import pickle
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
CACHE = os.path.join(ROOT, ".cache", "atc", "e55")
OUT_JSON = os.path.join(ROOT, "results", "E55_integrity.json")
OUT_CSV = os.path.join(ROOT, "results", "E55_table.csv")
ALPHAS = [1e-2, 1e-3, 1e-4]


def _save(name, obj):
    os.makedirs(CACHE, exist_ok=True)
    with open(os.path.join(CACHE, name + ".json"), "w") as f:
        json.dump(obj, f, indent=1)


def _load(name):
    with open(os.path.join(CACHE, name + ".json")) as f:
        return json.load(f)


def cmd_auth():
    from lunarsim.atc import integrity as I
    out = {"forgery": {}, "replay": {}}
    for t_bits, n in ((8, 100_000), (16, 1_000_000)):
        t = time.time()
        acc = I.forgery_trial(t_bits, n, np.random.default_rng([55, t_bits]))
        out["forgery"][str(t_bits)] = {"attempts": n, "accepted": acc, "rate": acc / n, "bound_2^-t": 2.0 ** -t_bits,
                                       "expected": n * 2.0 ** -t_bits, "s": round(time.time() - t, 1)}
    for t_bits in (64, 128):
        q = 10 * 3.156e7                                        # ten attempts a second for a year
        out["forgery"][str(t_bits)] = {"per_attempt": 2.0 ** -t_bits, "year_at_10_per_s_union_bound": q * 2.0 ** -t_bits,
                                       "note": "formula (note 03 E4); not measurable by trial"}
    for loss in (0.10, 0.25):
        out["replay"][str(loss)] = I.replay_trial(20, 10, 600, loss, 1.0, np.random.default_rng([55, int(loss * 100)]))
    _save("auth", out)
    print(json.dumps(out, indent=1))


def cmd_replay_recent():
    """B-118 N9: the replay trial with replays of messages sent in the last 60 s (integrity.replay_recent_trial)."""
    from lunarsim.atc import integrity as I
    out = {"added": "after the code review of 13 Nov 2026 (B-118 N9)",
           "setup": "20 senders at 1 Hz, 10 receivers, 600 s, a replay a second of a message sent in the last 60 s "
                    "(age 0 to 60 s), counter and 10 s freshness rule, 64-bit tags", "loss": {}}
    for loss in (0.10, 0.25):
        out["loss"][str(loss)] = I.replay_recent_trial(20, 10, 600, loss, 1.0, np.random.default_rng([55, 9, int(loss * 100)]))
    _save("replay_recent", out)
    print(json.dumps(out, indent=1))


def cmd_integrity():
    from lunarsim.atc import integrity as I
    from lunarsim.nn import baselines as B, dataset as D, faults as F
    out = {"rule": "LRIP note 03 C8: z^2 > gamma, suspect at 3 of the last 5", "sets": {}}
    ti = D.META.index("kind")
    w_i = D.META.index("weight")
    for split in ("val", "test", "ood"):
        t = time.time()
        d = D.load(split)
        kinds = d["mf"][:, ti].astype(int)
        w = d["mn"][:, w_i]
        res = {}
        for alpha in ALPHAS:
            g = I.GAMMA[1][alpha]
            for rule, (sf, sn, thr) in {
                "3of5": (I.lrip_rule_score(d["Xf"], g), I.lrip_rule_score(d["Xn"], g), 2.5),
                "single": (B.chi2_step(d["Xf"]), B.chi2_step(d["Xn"]), g)}.items():
                fa = B.fa_per_day(B.bin_max(sn), w, thr)
                found, delay, fp = B.detect(sf, d["mf"], thr)
                per = {}
                for k, name in enumerate(F.FAULT_TYPES, start=1):
                    sel = kinds == k
                    if sel.any():
                        per[name] = {"events": int(sel.sum()), "recall": float(found[sel].mean()),
                                     "median_delay_s": float(np.nanmedian(delay[sel & found])) if (sel & found).any() else None}
                fsel = kinds > 0
                per["all"] = {"events": int(fsel.sum()), "recall": float(found[fsel].mean()),
                              "median_delay_s": float(np.nanmedian(delay[fsel & found])) if (fsel & found).any() else None}
                prec = per["all"]["recall"] / (per["all"]["recall"] + fa) if (per["all"]["recall"] + fa) > 0 else None
                res[f"{rule}@{alpha:g}"] = {"gamma": g, "fa_per_pair_day": fa, "per_type": per,
                                            "precision_at_1_fault_per_pair_day": prec}
                del sf, sn
        out["sets"][split] = res
        out["sets"][split]["_s"] = round(time.time() - t, 1)
        del d
        print(split, {k: (round(v["fa_per_pair_day"], 2), round(v["per_type"]["all"]["recall"], 3))
                      for k, v in res.items() if not k.startswith("_")}, flush=True)
    e56 = json.load(open(os.path.join(ROOT, "results", "E56_integrity.json")))
    out["e56_reference"] = {s: {det: e56[s][det]["day"] for det in ("chi2_step", "cusum", "net") if det in e56[s]}
                            for s in ("test", "ood")}
    out["detectable_error_check"] = I.detectable_error_check()
    out["k_of_n_false_alarm"] = {f"{a:g}": I.k_of_n_false_alarm(a) for a in ALPHAS}
    _save("integrity", out)


def _positions(geometry):
    import run_e50 as E5
    g = E5._geo()
    if geometry == "spread":
        return np.arange(len(g["xy"])), g
    tr = pickle.load(gzip.open(os.path.join(ROOT, ".cache", "atc", "e50", "trace_m1_s1.pkl.gz")))
    xy = np.asarray(tr["xy"], float).reshape(-1, 2)[::7]
    sxy = g["xy"]
    idx = np.empty(len(xy), int)
    for k in range(0, len(xy), 4096):
        dd = ((xy[k:k + 4096, None, :] - sxy[None, :, :]) ** 2).sum(axis=2)
        idx[k:k + 4096] = dd.argmin(axis=1)
    return idx, g


def cmd_consensus(runs=50, mast_variant=False):
    """mast_variant (LEAD, 11 Nov): the base computer on the 10 m BASE mast joins as one more honest node, linked to
    every rover in its DEM line of sight (B-70 mesh mast table)."""
    from lunarsim.atc import integrity as I
    out = {"cells": []}
    t0 = time.time()
    for geometry in ("fleet", "spread"):
        pool, g = _positions(geometry)
        M = g["los"].mat[(2.5, 2.5)]
        mast_vis = g["los"].mast[2.5]
        for N in (5, 8, 12, 20, 40):
            for f in (0, 1, 2):
                for F in sorted({1, max(f, 1)}):
                    rng = np.random.default_rng([55, N, f, F, geometry == "spread"])
                    safe, agree, rob, rob_f1, deg_ok, conn = [], [], [], [], [], []
                    for _ in range(runs):
                        idx = pool[rng.integers(0, len(pool), N)]
                        adj = M[np.ix_(idx, idx)].copy()
                        np.fill_diagonal(adj, False)
                        faulty = np.zeros(N, bool)
                        faulty[rng.choice(N, f, replace=False)] = True
                        x0 = rng.normal(0.0, 1.0, N)
                        if mast_variant:                       # node N = the mast (honest)
                            a2 = np.zeros((N + 1, N + 1), bool)
                            a2[:N, :N] = adj
                            a2[:N, N] = a2[N, :N] = mast_vis[idx]
                            adj = a2
                            faulty = np.r_[faulty, False]
                            x0 = np.r_[x0, rng.normal(0.0, 1.0)]
                        hist, ok = I.wmsr(adj, x0, faulty, F, steps=60)
                        r0 = hist[0].max() - hist[0].min()
                        safe.append(ok)
                        agree.append(bool(hist[-1].max() - hist[-1].min() < 0.01 * max(r0, 1e-12)))
                        honest_deg = adj[~faulty].sum(axis=1)
                        deg_ok.append(bool((honest_deg >= 2 * F + 1).all()))
                        rob.append(I.is_r_robust(adj, 2 * F + 1, max_n=8))
                        rob_f1.append(I.is_r_robust(adj, F + 1, max_n=8))
                        # connected?
                        seen, st = {0}, [0]
                        while st:
                            u = st.pop()
                            for v in np.nonzero(adj[u])[0]:
                                if v not in seen:
                                    seen.add(int(v))
                                    st.append(int(v))
                        conn.append(len(seen) == len(adj))
                    exact = [r for r in rob if r is not None]
                    cell = {"geometry": geometry, "mast": bool(mast_variant), "N": N, "f": f, "F": F, "runs": runs,
                            "safe_share": float(np.mean(safe)), "agreement_share": float(np.mean(agree)),
                            "degree_condition_share": float(np.mean(deg_ok)), "connected_share": float(np.mean(conn)),
                            "robust_2F1_share": float(np.mean(exact)) if exact else None,
                            "robust_F1_share": float(np.mean([r for r in rob_f1 if r is not None])) if exact else None}
                    # H16 split: safety among robust / non-robust graphs (exact where N <= 8, else the degree condition)
                    key = rob if exact else deg_ok
                    rs = [s for s, k in zip(safe, key) if k]
                    nrs = [s for s, k in zip(safe, key) if not k]
                    cell["safe_when_robust"] = float(np.mean(rs)) if rs else None
                    cell["safe_when_not_robust"] = float(np.mean(nrs)) if nrs else None
                    cell["runs_robust"] = len(rs)
                    cell["robust_basis"] = "exact (2F+1)-robust" if exact else "degree >= 2F+1 (necessary only)"
                    out["cells"].append(cell)
                    print(geometry, N, f, F, {k: cell[k] for k in ("safe_share", "agreement_share", "robust_2F1_share",
                                                                    "degree_condition_share", "safe_when_not_robust")},
                          round(time.time() - t0), "s", flush=True)
    _save("consensus_mast" if mast_variant else "consensus", out)


def cmd_build():
    auth, integ, cons = _load("auth"), _load("integrity"), _load("consensus")
    cons_m = _load("consensus_mast") if os.path.isfile(os.path.join(CACHE, "consensus_mast.json")) else {"cells": []}
    rows = []
    for split, res in integ["sets"].items():
        for key, r in res.items():
            if key.startswith("_"):
                continue
            row = {"part": "integrity", "set": split, "detector": key, "gamma": r["gamma"],
                   "fa_per_pair_day": round(r["fa_per_pair_day"], 3)}
            for t, v in r["per_type"].items():
                row[f"recall_{t}"] = round(v["recall"], 3)
                row[f"delay_s_{t}"] = v["median_delay_s"]
            rows.append(row)
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    crow = []
    for c in cons["cells"] + cons_m["cells"]:
        crow.append({"part": "consensus", **dict({"mast": False}, **c)})
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in keys})
    with open(OUT_CSV.replace(".csv", "_consensus.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(crow[0]))
        w.writeheader()
        w.writerows(crow)
    # H16
    robust_cells = [c for c in cons["cells"] if c["f"] >= 1 and c["F"] == c["f"] and c["runs_robust"]]
    unsafe_robust = [c for c in robust_cells if c["safe_when_robust"] is not None and c["safe_when_robust"] < 1.0]
    nonrobust = [c for c in cons["cells"] if c["f"] >= 1 and c["F"] == c["f"] and c["safe_when_not_robust"] is not None]
    left = [c for c in nonrobust if c["safe_when_not_robust"] < 1.0]
    over = [c for c in cons["cells"] if c["f"] > c["F"]]
    h16 = {"rule": "F = f: every run on a (2f+1)-robust mesh stays inside the honest range; on a non-robust mesh at least "
                   "one run leaves it",
           "robust_cells_all_safe": not unsafe_robust,
           "nonrobust_cells_with_a_run_leaving_the_range": len(left), "nonrobust_cells": len(nonrobust),
           "cells_with_more_liars_than_F": [{k: c[k] for k in ("geometry", "N", "f", "F", "safe_share")} for c in over]}
    h16["supported"] = bool(h16["robust_cells_all_safe"] and len(left) > 0)

    def _ev(cells):
        return {"cells": len(cells), "runs_robust": int(sum(c["runs_robust"] for c in cells)),
                "runs_robust_all_safe": all(c["safe_when_robust"] == 1.0 for c in cells if c["runs_robust"]),
                "runs_not_robust": int(sum(c["runs"] - c["runs_robust"] for c in cells))}
    ff = [c for c in cons["cells"] if c["f"] >= 1 and c["F"] == c["f"]]
    h16["robust_evidence_by_basis"] = {      # B-118 N16: the exact cells reported apart
        "exact_2F1_robust_N_le_8": _ev([c for c in ff if c["robust_basis"].startswith("exact")]),
        "degree_condition_only_N_gt_8": _ev([c for c in ff if not c["robust_basis"].startswith("exact")]),
        "note": "the split behind robust_cells_all_safe: exact (2F+1)-robustness is computed for N <= 8 only; above, "
                "'robust' means every honest node hears >= 2F + 1, a necessary condition, so those runs are not shown "
                "to be on robust meshes. The exactly robust evidence is the runs_robust of the first block."}
    doc = {"experiment": "E55 (B-95), Phase 6, H15 baseline and H16", "note": __doc__.split("\n\n")[1].strip(),
           "auth": auth, "integrity": integ, "consensus": cons, "consensus_with_base_mast": cons_m, "h16": h16}
    doc["replay_trial_description"] = (       # B-118 N9: what auth.replay counts, said plainly
        "auth.replay: 20 senders at 1 Hz, 10 receivers, 600 s, loss 0.10 / 0.25; once a second the attacker replays a "
        "random EARLIER message drawn from the whole recorded log (so usually minutes old), stamped 0 to 60 s after the "
        "replay event. Only about 1 % of these replays fall inside the 10 s freshness window, so '0 accepted' says "
        "little about the window. replay_recent (added after the code review of 13 Nov 2026) replays messages sent in "
        "the last 60 s (age 0 to 60 s) and splits the accepted replays.")
    if os.path.isfile(os.path.join(CACHE, "replay_recent.json")):    # B-118 N9, added after the code review
        doc["replay_recent"] = _load("replay_recent")
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, default=lambda x: None)
        f.write("\n")
    print(json.dumps(h16, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["auth", "replay_recent", "integrity", "consensus", "consensus_mast", "build"])
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    {"auth": cmd_auth, "replay_recent": cmd_replay_recent, "integrity": cmd_integrity, "consensus": cmd_consensus,
     "consensus_mast": lambda: cmd_consensus(mast_variant=True), "build": cmd_build}[a.cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
