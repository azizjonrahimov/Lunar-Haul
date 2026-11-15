"""B-117 (g) and (j1) at 1x: E50's bound coverage per seed, and the navigation input sweeps on all 30 seeds.

    python tools/atc/b117gj1_e50_cov.py run --seeds 1-30    # resumable, one file per seed (.cache/atc/b117gj1)
    python tools/atc/b117gj1_e50_cov.py table               # -> results/E50_coverage_sweep.json (a new file)

Per seed (E50 at 1x, the July 2028 window; E50's own functions: run_e50.record, trajectories, nav, bound_series):
(g) bound coverage: the share of driving vehicle-steps whose position error |e| is inside the vehicle's 95 % bound,
    for each layer set (dr, dr+ranging, dr+ranging+fixes; LANS as in 2030), against (i) the bound of the same step and
    (ii) the bound as filed with the margin (bound_series: the hourly maximum, same run), near the base (2+ beacons in
    line of sight, E50's region rule) and away. Then the cross-run question P2 leaves open: in E50's two margin runs
    (k = 1; "dr" and "layered" = dr+ranging+fixes+lans in 2028), the margin run's own error against the bound it filed
    with, which comes from the perfect run (hourly maximum), and against its own bound.
(j1) input sweeps on dr+ranging (2028), one input at a time from the defaults, over the ranges of note 01 D:
    long-range ranging sigma 1 and 10 m (default 3), UWB sigma 0.1 and 0.7 m (0.3), beacon survey sigma 0.05, 0.5
    and 1.0 m (0.15), UWB reach 50 and 300 m (100). Per point: p95 error and coverage, split by distance from the
    BASE mast (< 1 km, 1-5 km, > 5 km) and by beacons in line of sight (0, 1, 2+).
Checks per seed: the perfect run's delay equals E50's cached cell, the dr+ranging near p95 equals it (as
run_e50_near), and each margin run's delay equals the cached margin block. Pre-declared in the B-117 estimate (13 Nov;
the sweep ranges are note 01 D's). Earlier: run_e50_near's sweep on seeds 1-6 (uwb and long-range sigma only).
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import pickle
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import run_e50 as E5  # noqa: E402
import run_e50_near as NB  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "b117gj1")
OUT = os.path.join(ROOT, "results", "E50_coverage_sweep.json")
SETS = {"dr": ("dr", 2028), "dr+ranging": ("dr+ranging", 2028), "dr+ranging+fixes": ("dr+ranging+fixes", 2028),
        "lans@2030": ("dr+ranging+fixes+lans", 2030)}
SWEEP = [("radio_sigma_m", 1.0), ("radio_sigma_m", 10.0), ("uwb_sigma_m", 0.1), ("uwb_sigma_m", 0.7),
         ("beacon_sigma_m", 0.05), ("beacon_sigma_m", 0.5), ("beacon_sigma_m", 1.0),
         ("uwb_range_m", 50.0), ("uwb_range_m", 300.0)]
DIST = {"<1 km": (0.0, 1000.0), "1-5 km": (1000.0, 5000.0), ">5 km": (5000.0, np.inf)}


def _nav(tr, rec, ls, seed, year, extra=None):
    from lunarsim.atc import pnt as PN
    bi, bxy = E5.beacons(rec)
    return PN.simulate(tr, PN.LAYER_SETS[ls], seed, params=dict({"year": year}, **(extra or {})), los=E5._geo()["los"],
                       beacon_idx=bi, beacon_xy=bxy, mast_idx=E5._geo()["ids"]["BASE"], store_errors=False)


def _filed(tr, series):
    """(T, N) the bound filed for each vehicle-step: bound_series' value for the step's hour (0 before the window)."""
    out = np.zeros(tr.idx.shape)
    for n, vid in enumerate(tr.ids):
        s = np.array(series[str(int(vid))], float)
        k = np.searchsorted(s[:, 0], tr.t_h, side="right") - 1
        out[:, n] = s[np.clip(k, 0, len(s) - 1), 1]
    return out


def _cov(err, b, m):
    return {"n": int(m.sum()), "share_inside": float((err[m] <= b[m]).mean()) if m.any() else None}


def _p95(err, m):
    return float(np.quantile(err[m], 0.95)) if m.any() else None


def run_seed(seed):
    t_s = time.time()
    code = E5.code_fingerprint()
    month, t0, t1, share = E5._window()
    rec = E5.record(1, seed, t0, t1)
    tr = E5.trajectories(rec, t0, t1)
    mv = tr.ds > 0
    M = NB.masks(tr, rec)
    near = M["a"]
    g = E5._geo()
    bxy0 = g["xy"][g["ids"]["BASE"]]
    d_base = np.hypot(tr.xy[..., 0] - bxy0[0], tr.xy[..., 1] - bxy0[1])
    cls_d = {k: (d_base >= lo) & (d_base < hi) & mv for k, (lo, hi) in DIST.items()}
    cls_b = {"0": ~M["b"] & mv, "1": M["b"] & ~M["a"] & mv, "2+": M["a"] & mv}
    out = {"seed": seed, "code": code, "perfect_delay_mean_h": rec["delay_mean_h"], "driving_steps": int(mv.sum()),
           "share_by_distance": {k: float(m.sum() / mv.sum()) for k, m in cls_d.items()},
           "share_by_beacons": {k: float(m.sum() / mv.sum()) for k, m in cls_b.items()}, "coverage": {}, "sweep": [],
           "margin": {}}
    series = {}
    for name, (ls, year) in SETS.items():
        res = _nav(tr, rec, ls, seed, year)
        filed = _filed(tr, E5.bound_series(tr, res, t0))
        out["coverage"][name] = {
            "own_bound": {"all": _cov(res.err, res.b95, mv), "near": _cov(res.err, res.b95, mv & near),
                          "away": _cov(res.err, res.b95, mv & ~near)},
            "filed_bound_same_run": {"all": _cov(res.err, filed, mv), "near": _cov(res.err, filed, mv & near),
                                     "away": _cov(res.err, filed, mv & ~near)},
            "p95_m": {"all": _p95(res.err, mv), "near": _p95(res.err, mv & near)}}
        if name == "dr+ranging":
            out["dr_ranging_default"] = {"by_distance": {k: {"p95_m": _p95(res.err, m), **_cov(res.err, res.b95, m)}
                                                         for k, m in cls_d.items()},
                                         "by_beacons": {k: {"p95_m": _p95(res.err, m), **_cov(res.err, res.b95, m)}
                                                        for k, m in cls_b.items()}}
        series[name] = E5.bound_series(tr, res, t0)
        del res
    for par, val in SWEEP:
        res = _nav(tr, rec, "dr+ranging", seed, 2028, {par: val})
        out["sweep"].append({"param": par, "value": val, "p95_m": {"all": _p95(res.err, mv), "near": _p95(res.err, mv & near)},
                             "by_distance": {k: {"p95_m": _p95(res.err, m), **_cov(res.err, res.b95, m)} for k, m in cls_d.items()},
                             "by_beacons": {k: {"p95_m": _p95(res.err, m), **_cov(res.err, res.b95, m)} for k, m in cls_b.items()}})
        del res
    # E50's margin runs: dr with dr's series; layered = dr+ranging+fixes+lans in 2028 (no LANS fix then: the
    # dr+ranging+fixes series, as stage_nav uses)
    for lab, ls in E5.DESIGN["margin_sets"].items():
        ser = series["dr"] if ls == "dr" else series["dr+ranging+fixes"]
        recm = E5.record(1, seed, t0, t1, pos_margin={"k": E5.DESIGN["k_pos"], "bound_m": ser})
        trm = E5.trajectories(recm, t0, t1)
        mvm = trm.ds > 0
        nearm = E5.near_mask(trm, recm)
        resm = _nav(trm, recm, ls, seed, E5.YEAR)
        filedm = _filed(trm, ser)
        out["margin"][lab] = {"layer_set": ls, "delay_mean_h": recm["delay_mean_h"],
                              "filed_bound_from_perfect_run": {"all": _cov(resm.err, filedm, mvm),
                                                               "near": _cov(resm.err, filedm, mvm & nearm),
                                                               "away": _cov(resm.err, filedm, mvm & ~nearm)},
                              "own_bound": {"all": _cov(resm.err, resm.b95, mvm), "near": _cov(resm.err, resm.b95, mvm & nearm)}}
        del resm
    p50 = os.path.join(E5.CACHE, f"m1_s{seed}.pkl.gz")
    with gzip.open(p50) as f:
        c = pickle.load(f)
    out["e50_reproduced"] = {
        "perfect_delay": c["perfect"]["delay_mean_h"] == rec["delay_mean_h"],
        "ranging_near_p95": abs(c["nav"]["dr+ranging"]["near"]["p95_m"] - out["coverage"]["dr+ranging"]["p95_m"]["near"]) < 1e-4,
        "margin_delay": {lab: c["margin"][lab]["delay_mean_h"] == out["margin"][lab]["delay_mean_h"] for lab in out["margin"]}}
    out["e50_cell_code"] = c.get("code")
    out["seed_s"] = round(time.time() - t_s, 1)
    out["peak_mb"] = NB._peak_mb()
    return out


def cmd_run(seeds, max_s):
    t0, last = time.time(), 200.0
    os.makedirs(CACHE, exist_ok=True)
    for s in seeds:
        p = os.path.join(CACHE, f"s{s}.json")
        if os.path.isfile(p):
            continue
        if time.time() - t0 + 1.25 * last > max_s:
            print(f"stop before seed {s}: time budget", flush=True)
            return
        ts = time.time()
        o = run_seed(s)
        last = time.time() - ts
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(o, f, allow_nan=False)
        os.replace(p + ".tmp", p)
        print(f"s{s} done in {last:.0f} s, peak {o['peak_mb']} MB, reproduced {o['e50_reproduced']}", flush=True)
    print("all requested seeds done", flush=True)


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return round(float(np.mean(xs)), 4) if xs else None


def cmd_table():
    files = sorted(glob.glob(os.path.join(CACHE, "s[0-9]*.json")), key=lambda p: int(os.path.basename(p)[1:-5]))
    S = [json.load(open(p, encoding="utf-8")) for p in files]
    fp = E5.code_fingerprint()
    if sorted({s["code"] for s in S}) != [fp]:
        raise SystemExit(f"cells with other code: {sorted({s['code'] for s in S})} (current {fp}); rerun")
    bad = [s["seed"] for s in S if not (s["e50_reproduced"]["perfect_delay"] and s["e50_reproduced"]["ranging_near_p95"]
                                        and all(s["e50_reproduced"]["margin_delay"].values()))]
    if bad:
        raise SystemExit(f"seeds not reproducing E50's cells: {bad}")
    out = {"task": "B-117 (g) and (j1) at 1x: bound coverage per seed, and E50's navigation input sweeps on 30 seeds",
           "note": __doc__.split("\n\n")[1].strip(), "seeds": [s["seed"] for s in S], "code": fp,
           "e50_cells_reproduced": True, "coverage": {}, "margin_runs": {}, "sweep": {}, "per_seed": {}}
    for name in SETS:
        out["coverage"][name] = {
            kind: {reg: {"share_inside_mean": _mean([s["coverage"][name][kind][reg]["share_inside"] for s in S]),
                         "share_inside_min_seed": round(min(s["coverage"][name][kind][reg]["share_inside"] for s in S
                                                            if s["coverage"][name][kind][reg]["share_inside"] is not None), 4)}
                   for reg in ("all", "near", "away")}
            for kind in ("own_bound", "filed_bound_same_run")}
        out["per_seed"][name] = {str(s["seed"]): round(s["coverage"][name]["own_bound"]["all"]["share_inside"], 4) for s in S}
    for lab in E5.DESIGN["margin_sets"]:
        out["margin_runs"][lab] = {
            "filed_bound_from_perfect_run": {reg: {"share_inside_mean": _mean([s["margin"][lab]["filed_bound_from_perfect_run"][reg]["share_inside"] for s in S]),
                                                   "share_inside_min_seed": round(min(s["margin"][lab]["filed_bound_from_perfect_run"][reg]["share_inside"]
                                                                                      for s in S if s["margin"][lab]["filed_bound_from_perfect_run"][reg]["share_inside"] is not None), 4)}
                                             for reg in ("all", "near", "away")},
            "own_bound": {reg: _mean([s["margin"][lab]["own_bound"][reg]["share_inside"] for s in S]) for reg in ("all", "near")}}
        out["per_seed"][f"margin {lab} filed"] = {str(s["seed"]): round(s["margin"][lab]["filed_bound_from_perfect_run"]["all"]["share_inside"], 4) for s in S}
    pts = [("default", None)] + [(p, v) for p, v in SWEEP]
    for p, v in pts:
        rows = [s["dr_ranging_default"] for s in S] if p == "default" else \
            [next(x for x in s["sweep"] if x["param"] == p and x["value"] == v) for s in S]
        key = "default (radio 3 m, uwb 0.3 m, beacon 0.15 m, uwb reach 100 m)" if p == "default" else f"{p} = {v:g}"
        out["sweep"][key] = {
            "by_distance": {k: {"p95_m_mean": _mean([r["by_distance"][k]["p95_m"] for r in rows]),
                                "seeds_p95_within_5m": sum(1 for r in rows if r["by_distance"][k]["p95_m"] is not None and r["by_distance"][k]["p95_m"] <= 5.0),
                                "coverage_mean": _mean([r["by_distance"][k]["share_inside"] for r in rows])} for k in DIST},
            "by_beacons": {k: {"p95_m_mean": _mean([r["by_beacons"][k]["p95_m"] for r in rows]),
                               "seeds_p95_within_5m": sum(1 for r in rows if r["by_beacons"][k]["p95_m"] is not None and r["by_beacons"][k]["p95_m"] <= 5.0),
                               "coverage_mean": _mean([r["by_beacons"][k]["share_inside"] for r in rows])} for k in ("0", "1", "2+")}}
        if p != "default":
            out["sweep"][key]["near_p95_m_mean"] = _mean([r["p95_m"]["near"] for r in rows])
    out["sweep"]["default (radio 3 m, uwb 0.3 m, beacon 0.15 m, uwb reach 100 m)"]["near_p95_m_mean"] = \
        _mean([s["coverage"]["dr+ranging"]["p95_m"]["near"] for s in S])
    out["peak_mb_max"] = max(s["peak_mb"] or 0 for s in S)
    out["run_s_total"] = round(sum(s["seed_s"] for s in S), 1)
    text = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with open(OUT + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(OUT + ".tmp", OUT)
    print(json.dumps({k: out[k] for k in ("coverage", "margin_runs")}, indent=1)[:5000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--seeds", default="1-30")
    ap.add_argument("--max-seconds", type=float, default=500.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 120, exit=True)
    if a.cmd == "run":
        lo, hi = (a.seeds.split("-") + [a.seeds])[:2]
        cmd_run(list(range(int(lo), int(hi) + 1)), a.max_seconds)
    else:
        cmd_table()
