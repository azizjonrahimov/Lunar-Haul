"""E50b (B-90b, Phase 6, H10 sensitivity): the layered scheme with and without terrain-fix stop time in the engine.

    python tools/atc/run_e50b.py run   --seeds 1-30 [--max-seconds 480]   # resumable, one cache file per seed
    python tools/atc/run_e50b.py build                                    # -> results/E50b_summary.json, E50b_runs.csv

E50 (tools/atc/run_e50.py, files unchanged and labelled "without stop time") counted the 120 s stop of each driving
terrain fix (lunarsim.atc.pnt, fix_stop_s) but did not put it into the engine, so neither the delay nor the
single-lane reservations saw it. E50b does, at fleet x1 with E50's 30 seeds and E50's scenario, per seed:
1. the perfect run (no margin; E50 stage "rec", rerun and checked against E50's cell) and the layered navigation on
   its trajectories (dr + ranging + fixes, 2028: no LANS), with each driving fix logged (pnt params log_fixes);
2. the fix table: every driving fix is matched to the drive leg it fell on (vehicle, time); per leg key, the fixes per
   traversal (traversals that start in the window) and the fixes' positions along the leg (fraction of the leg time);
3. arm "without stop time": E50's layered margin run (pos_margin from the perfect run's hourly 95 % bound, k = 1),
   rerun and checked against E50's cell; arm "with stop time": the same plus roads fix_stops (lunarsim/atc/roads.py,
   B-90b): each traversal of a leg in the window gets that leg's fixes per traversal as a running count, each stop
   120 s at the leg's observed fix positions, a stop inside a single-lane segment moved to the segment's exit;
4. per arm: its own navigation run (layered) and violations as E50 (true-time overlaps of conflicting single-lane
   windows), delay per delivery, road waiting, stops inserted.
The fix table comes from the perfect run, as E50's margin bound series does (stated). In the trajectories a stop is
spread over its leg (the engine's segments carry no mid-leg position), so the vehicle drives slower through the leg
rather than standing still: dead-reckoning error grows with distance, so the navigation run sees nearly the same
error (stated limitation).
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import math
import os
import pickle
import sys
import time
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_e50 as E5  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "e50b")
E50_CACHE = os.path.join(ROOT, ".cache", "atc", "e50")
OUT_JSON = os.path.join(ROOT, "results", "E50b_summary.json")
OUT_RUNS = os.path.join(ROOT, "results", "E50b_runs.csv")
MULT = 1
LAYERED_FIX = "dr+ranging+fixes"            # E50's source of the layered bound series (LANS share 0 in 2028)
LAYERED_NAV = E5.DESIGN["margin_sets"]["layered"]
DESIGN = {"experiment": "E50b (B-90b), Phase 6, sensitivity of H10 to terrain-fix stop time",
          "base": "E50 scenario and seeds (tools/atc/run_e50.py DESIGN), fleet x1", "stop_s": 120.0,
          "defer_in_single": True, "k_pos": E5.DESIGN["k_pos"], "bootstrap": 10000}

_FS = {"cfg": None}
_orig_scenario = E5._scenario


def _scenario(m, t1, pos_margin=None):
    sc = _orig_scenario(m, t1, pos_margin)
    if _FS["cfg"] is not None:
        sc = sc.with_(p5=dict(sc.p5, roads=dict(sc.p5["roads"], fix_stops=_FS["cfg"])))
    return sc


E5._scenario = _scenario                    # in this process only; run_e50.py is not changed


def _peak_mb():
    """Peak working set of this process (Windows GetProcessMemoryInfo; psutil is not installed)."""
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + \
                       [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                                       "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                                       "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        f = k32.K32GetProcessMemoryInfo
        f.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]   # a 64-bit handle; untyped it is truncated
        f(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return round(c.PeakWorkingSetSize / 2 ** 20, 1)
    except Exception:
        return None


def fix_table(rec, tr, fix_log, t0w, t1w):
    """Per leg key: fixes per traversal and the fixes' positions (fraction of the leg), from the perfect run."""
    names = rec["name"]
    nm = lambda s: names.get(s, s)
    drives = {}
    for vid, ss in rec["segs"].items():
        seen = set()
        lst = []
        for a, b, s0, s1, *_ in ss:
            if a == b or s1 <= s0:
                continue
            tup = (a, b, round(s0, 9), round(s1, 9))
            if tup in seen:
                continue
            seen.add(tup)
            lst.append((s0, s1, f"{nm(a)}->{nm(b)}"))
        lst.sort()
        drives[int(vid)] = lst
    trav = defaultdict(int)
    for lst in drives.values():
        for s0, s1, key in lst:
            if t0w <= s0 < t1w:
                trav[key] += 1
    frac = defaultdict(list)
    unmatched = straddle = 0
    for k, i in fix_log:
        vid, t = int(tr.ids[i]), float(tr.t_h[k])
        hit = next(((s0, s1, key) for s0, s1, key in drives.get(vid, ()) if s0 < t <= s1 + 1e-9), None)
        if hit is None:
            unmatched += 1
            continue
        s0, s1, key = hit
        if not (t0w <= s0 < t1w):
            straddle += 1
            continue
        frac[key].append(min(1.0, max(0.0, (t - s0) / (s1 - s0))))
    legs = {key: {"per_traversal": len(frac.get(key, [])) / n, "fractions": sorted(round(x, 5) for x in frac.get(key, []))}
            for key, n in trav.items() if frac.get(key)}
    return legs, {"fixes_logged": len(fix_log), "fixes_in_table": sum(len(v) for v in frac.values()),
                  "fixes_unmatched": unmatched, "fixes_on_legs_started_before_window": straddle,
                  "leg_keys": len(legs), "traversals_in_window": int(sum(trav.values()))}


def arm(seed, t0, t1, series, fs_cfg):
    _FS["cfg"] = fs_cfg
    try:
        recm = E5.record(MULT, seed, t0, t1, pos_margin={"k": DESIGN["k_pos"], "bound_m": series})
    finally:
        _FS["cfg"] = None
    trm = E5.trajectories(recm, t0, t1)
    resm = E5.nav(trm, recm, LAYERED_NAV, seed, store=True)
    rd = recm["road"]
    out = {"delay_mean_h": recm["delay_mean_h"], "delivered": recm["delivered"],
           "urgent_delay_mean_h": recm["urgent_delay_mean_h"], "urgent_delivered": recm["urgent_delivered"],
           "road_wait_h": rd["road_wait_h"], "road_conflicts": rd["road_conflicts"],
           "engine_fix_stops": int(rd.get("road_fix_stops", 0)), "engine_fix_stop_h": float(rd.get("road_fix_stop_h", 0.0)),
           "nav_fix_stop_h": resm.counts["fix_stop_h"], "nav_fixes_driving": resm.counts["fixes_driving"],
           "reservations": len(recm["res_log"]),
           "margin_h_mean": float(np.mean([r[3] for r in recm["res_log"]])) if recm["res_log"] else 0.0,
           "violations": E5.violations(recm, trm, resm, t0, t1), "run_s": round(recm["run_s"], 1)}
    del recm, trm, resm
    return out


def run_seed(seed):
    from lunarsim.atc import pnt as PN
    t_s = time.time()
    code = E5.code_fingerprint()                                  # B-120 D: the cell carries its code version
    month, t0, t1, share = E5._window()
    rec = E5.record(MULT, seed, t0, t1)
    tr = E5.trajectories(rec, t0, t1)
    bi, bxy = E5.beacons(rec)
    res = PN.simulate(tr, PN.LAYER_SETS[LAYERED_FIX], seed, params={"year": E5.YEAR, "log_fixes": True},
                      los=E5._geo()["los"], beacon_idx=bi, beacon_xy=bxy, mast_idx=E5._geo()["ids"]["BASE"],
                      store_errors=True)
    series = E5.bound_series(tr, res, t0)
    legs, tstats = fix_table(rec, tr, res.counts["fix_log"], t0, t1)
    out = {"seed": seed, "mult": MULT, "window": [t0, t1], "month": month,
           "perfect": {k: rec[k] for k in ("delay_mean_h", "delivered", "urgent_delay_mean_h", "urgent_delivered")},
           "perfect_road_wait_h": rec["road"]["road_wait_h"], "perfect_fixes_driving": res.counts["fixes_driving"],
           "perfect_fix_stop_h": res.counts["fix_stop_h"], "table": tstats,
           "table_legs": {k: {"per_traversal": v["per_traversal"], "n_fixes": len(v["fractions"])} for k, v in legs.items()}}
    # share of the observed fix positions inside a single-lane segment of their leg (the ones the engine defers)
    from lunarsim.atc import roads as RD
    single = RD.single_lane_set(RD.DEFAULTS["single_share"] if "single_share" not in E5._scenario(MULT, t1).p5["roads"]
                                else E5._scenario(MULT, t1).p5["roads"]["single_share"])
    _, _, seglegs = RD.build_segments(single, E5._scenario(MULT, t1).p5["roads"]["bay_km"])
    inside = sum(1 for key, v in legs.items() for g in v["fractions"]
                 if any(f_in <= g <= f_out for _, f_in, f_out, _d in seglegs.get(key, ())))
    out["table"]["fixes_inside_single_lane"] = int(inside)
    del res, tr, rec
    fs_cfg = {"stop_s": DESIGN["stop_s"], "t_from_h": t0, "defer_in_single": DESIGN["defer_in_single"], "legs": legs}
    out["without_stop_time"] = arm(seed, t0, t1, series, None)
    out["with_stop_time"] = arm(seed, t0, t1, series, fs_cfg)
    # reproduction of E50's cell (perfect run and the layered margin run)
    p50 = os.path.join(E50_CACHE, f"m{MULT}_s{seed}.pkl.gz")
    if os.path.isfile(p50):
        with gzip.open(p50) as f:
            c = pickle.load(f)
        ml = c["margin"]["layered"]
        w = out["without_stop_time"]
        out["e50_reproduced"] = {
            "perfect_delay": c["perfect"]["delay_mean_h"] == out["perfect"]["delay_mean_h"],
            "margin_delay": ml["delay_mean_h"] == w["delay_mean_h"], "margin_road_wait": ml["road_wait_h"] == w["road_wait_h"],
            "margin_violations": ml["violations"]["violations"] == w["violations"]["violations"],
            "fixes_driving": c["nav"][LAYERED_FIX]["counts"]["fixes_driving"] == out["perfect_fixes_driving"]}
    out["seed_s"] = round(time.time() - t_s, 1)
    out["peak_mb"] = _peak_mb()
    out["code"] = code
    return out


def _seeds(s):
    lo, hi = (s.split("-") + [s])[:2]
    return list(range(int(lo), int(hi) + 1))


def cmd_run(seeds, max_s):
    os.makedirs(CACHE, exist_ok=True)
    t0 = time.time()
    last = 0.0
    for s in seeds:
        p = os.path.join(CACHE, f"m{MULT}_s{s}.json")
        if os.path.isfile(p):
            continue
        if time.time() - t0 + max(last, 60.0) * 1.3 > max_s:
            print(f"stop before seed {s}: time budget", flush=True)
            return
        ts = time.time()
        out = run_seed(s)
        with open(p + ".tmp", "w") as f:
            json.dump(out, f)
        os.replace(p + ".tmp", p)
        last = time.time() - ts
        w, ws = out["without_stop_time"], out["with_stop_time"]
        print(f"s{s}: {last:.0f} s, delay {w['delay_mean_h']:.3f} -> {ws['delay_mean_h']:.3f} h, stops "
              f"{ws['engine_fix_stops']}, viol {w['violations']['violations']} -> {ws['violations']['violations']}, "
              f"repro {all(out.get('e50_reproduced', {}).values())}, peak {out['peak_mb']} MB", flush=True)
    print("all requested seeds done", flush=True)


def _boot(d, B, rng):
    d = np.asarray(d, float)
    m = d[rng.integers(0, len(d), (B, len(d)))].mean(axis=1)
    return [float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def cmd_build():
    from scipy import stats
    S = sorted((json.load(open(p)) for p in glob.glob(os.path.join(CACHE, f"m{MULT}_s*.json"))), key=lambda x: x["seed"])
    if not S:
        raise SystemExit("no E50b cells")
    import e50_build as EB
    code = EB.require_code((x.get("code") for x in S), "E50b")              # B-120 D
    rng = np.random.default_rng([50, 2])
    B = DESIGN["bootstrap"]
    get = lambda armk, f: np.array([f(s[armk]) for s in S], float)
    perf = np.array([s["perfect"]["delay_mean_h"] for s in S])
    rows, metrics = [], {}
    for name, f in (("delay_mean_h", lambda a: a["delay_mean_h"]), ("urgent_delay_mean_h", lambda a: a["urgent_delay_mean_h"]),
                    ("road_wait_h", lambda a: a["road_wait_h"]), ("violations", lambda a: a["violations"]["violations"]),
                    ("overlap_s", lambda a: a["violations"]["overlap_s"]), ("delivered", lambda a: a["delivered"])):
        a, b = get("without_stop_time", f), get("with_stop_time", f)
        ok = np.isfinite(a) & np.isfinite(b)                 # urgent delay: seeds with no urgent delivery drop out
        a, b = a[ok], b[ok]
        d = b - a
        t = stats.ttest_rel(b, a) if np.std(d) > 0 else None
        metrics[name] = {"without_stop_time": float(a.mean()), "with_stop_time": float(b.mean()),
                         "diff_mean": float(d.mean()), "diff_ci95_bootstrap": _boot(d, B, rng),
                         "paired_t_p": float(t.pvalue) if t is not None else None,
                         "seeds_higher": int((d > 0).sum()), "seeds_lower": int((d < 0).sum()), "n_seeds": int(ok.sum())}
    # H10's primary clause re-checked with stop time (exploratory sensitivity, not in the confirmatory family)
    lay_s = get("with_stop_time", lambda a: a["delay_mean_h"])
    delta = 0.5 * float(perf.mean())
    dd = lay_s - perf
    n = len(dd)
    se = float(dd.std(ddof=1) / math.sqrt(n))
    p_tost = max(1 - stats.t.cdf((dd.mean() + delta) / se, n - 1), stats.t.cdf((dd.mean() - delta) / se, n - 1))
    for s in S:
        w, ws = s["without_stop_time"], s["with_stop_time"]
        rows.append({"seed": s["seed"], "perfect_delay_h": s["perfect"]["delay_mean_h"],
                     "delay_h_without": w["delay_mean_h"], "delay_h_with": ws["delay_mean_h"],
                     "road_wait_h_without": w["road_wait_h"], "road_wait_h_with": ws["road_wait_h"],
                     "violations_without": w["violations"]["violations"], "violations_with": ws["violations"]["violations"],
                     "engine_fix_stops": ws["engine_fix_stops"], "engine_fix_stop_h": round(ws["engine_fix_stop_h"], 3),
                     "perfect_fix_stop_h": round(s["perfect_fix_stop_h"], 3),
                     "fixes_inside_single_lane": s["table"]["fixes_inside_single_lane"],
                     "fixes_in_table": s["table"]["fixes_in_table"], "e50_reproduced": all(s.get("e50_reproduced", {}).values()),
                     "peak_mb": s["peak_mb"]})
    with open(OUT_RUNS, "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0]))
        wr.writeheader()
        wr.writerows(rows)
    tab = [s["table"] for s in S]
    doc = {"design": DESIGN, "code": code, "note": __doc__.strip().split("\n\n")[1].replace("\n", " "), "seeds": [s["seed"] for s in S],
           "labels": {"without_stop_time": "E50's layered margin run (results/E50_*: 'without stop time')",
                      "with_stop_time": "the same with the terrain-fix stops in the engine (roads fix_stops)"},
           "metrics": metrics,
           "stops": {"engine_fix_stops_mean": float(np.mean([s["with_stop_time"]["engine_fix_stops"] for s in S])),
                     "engine_fix_stop_h_mean": float(np.mean([s["with_stop_time"]["engine_fix_stop_h"] for s in S])),
                     "perfect_run_fix_stop_h_mean": float(np.mean([s["perfect_fix_stop_h"] for s in S])),
                     "nav_fix_stop_h_with_stop_time_mean": float(np.mean([s["with_stop_time"]["nav_fix_stop_h"] for s in S])),
                     "fixes_in_table_share": float(np.sum([t["fixes_in_table"] for t in tab]) / max(1, np.sum([t["fixes_logged"] for t in tab]))),
                     "fixes_inside_single_lane_share": float(np.sum([t["fixes_inside_single_lane"] for t in tab]) / max(1, np.sum([t["fixes_in_table"] for t in tab]))),
                     "fixes_unmatched": int(np.sum([t["fixes_unmatched"] for t in tab])),
                     "fixes_on_legs_started_before_window": int(np.sum([t["fixes_on_legs_started_before_window"] for t in tab]))},
           "h10_primary_with_stop_time": {"note": "exploratory sensitivity, not part of the confirmatory family: paired "
                                                  "TOST of layered-with-stop-time minus perfect at 1x, margin 50 % of the "
                                                  "perfect delay", "mean_diff_h": float(dd.mean()), "se_h": se,
                                          "margin_h": delta, "p": float(p_tost),
                                          "ratio_to_perfect": float(lay_s.mean() / perf.mean())},
           "e50_reproduced_all_seeds": all(all(s.get("e50_reproduced", {}).values()) and s.get("e50_reproduced") for s in S),
           "peak_mb_max": max((s["peak_mb"] or 0) for s in S), "seed_s_mean": float(np.mean([s["seed_s"] for s in S]))}
    import e50_build as EB
    EB.keep_superseded(OUT_JSON, doc)
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(json.dumps({k: {kk: (round(vv, 4) if isinstance(vv, float) else vv) for kk, vv in v.items()}
                      for k, v in metrics.items()}, indent=1))
    print(json.dumps(doc["stops"], indent=1), json.dumps(doc["h10_primary_with_stop_time"]), doc["e50_reproduced_all_seeds"])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "build"])
    ap.add_argument("--seeds", default="1-30")
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        cmd_run(_seeds(a.seeds), a.max_seconds)
    else:
        cmd_build()


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(560, exit=True)
    main()
