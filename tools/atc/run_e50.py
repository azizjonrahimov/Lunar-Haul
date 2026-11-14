"""E50 (B-90, Phase 6, H9 and H10): what position error costs the rules of the road.

    python tools/atc/run_e50.py time  [--mult 1] [--seed 1]                    # one cell, timed
    python tools/atc/run_e50.py run   --mult 1 --seeds 1-30 [--max-seconds 480]  # resumable, one cell per (mult, seed)
    python tools/atc/run_e50.py build                                          # -> results/E50_*.{csv,json}

Scenario (PREREG6 section 2): p5 3eq, 30 % load, team share 0.10, landing closures, dispatch to a fixed point, C_AUCTION
with message loss 0.10, road layer "atc", fleet x 1 / 4 / 8 (each owner's fleet repeated), simulated from 1 Jan 2028
to the end of the window: the 2028 month with the least BASE direct-to-Earth visibility (July; tools/atc/export_trace.py
dark_month), as B-80's trace pair.

Per (fleet multiple, seed), one cell:
1. "perfect" run (no position margin), with every single-lane reservation logged; its trajectories (the engine's
   segments after the road layer) on a 60 s grid.
2. lunarsim.atc.pnt on those trajectories for each layer set (dr; + ranging; + absolute fixes; + LANS in 2028, and in
   2030 as a variant): position error |e| and the 95 % bound per vehicle and step.
3. Violations without the margin: each reserved single-lane window shifted to its true time (along-track error /
   speed at entry and exit, note 01 E6); two windows of different vehicles on one resource that conflict under R3
   (opposite directions, or any on a branched segment) and overlap in true time are a violation.
4. For the margin sets (dr alone; the layered scheme available in 2028 = dr + ranging + fixes): a run with each
   reservation widened by k x the vehicle's 95 % bound / speed at both ends (bound series: the hourly maximum of the
   perfect run's bound for that vehicle; zero before the window), its own navigation run, violations with the margin,
   and delay per delivery against the perfect run.
Outcomes are over the window (vehicle-steps while driving for errors; items delivered in the window for delay).
Errors start at zero at the window start (every vehicle surveyed then: Assumed).
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import pickle
import sys
import time
import warnings
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

CACHE = os.path.join(ROOT, ".cache", "atc", "e50")
OUT_JSON = os.path.join(ROOT, "results", "E50_summary.json")
OUT_ERR = os.path.join(ROOT, "results", "E50_errors.csv")
OUT_RUNS = os.path.join(ROOT, "results", "E50_runs.csv")
OUT_TRACE = os.path.join(ROOT, "results", "E50_trace.json")
YEAR = 2028
DESIGN = {
    "experiment": "E50 (B-90), Phase 6, H9 and H10 (paper/atc/PREREG6.md)",
    "regime": "C_AUCTION", "regime_kw": {"loss": 0.10, "start_year": YEAR}, "roads": "atc",
    "multiples": [1, 4, 8], "dt_s": 60.0, "k_pos": 1.0,
    "layer_sets": ["dr", "dr+ranging", "dr+ranging+fixes", "dr+ranging+fixes+lans"],
    "lans_variant_year": 2030,
    "margin_sets": {"dr": "dr", "layered": "dr+ranging+fixes+lans"},
    "budget_m": 5.0,
    "region_rule": "near base = the vehicle's route sample is in radio line of sight of at least 2 of the 4 beacons",
    "shift_h": 8.0,
}


# ------------------------------------------------------------------------------------------------ engine runs
def _window():
    import export_trace as XT
    (month, t0, t1, share), _ = XT.dark_month(YEAR)
    return month, t0, t1, share


def _scenario(m, t1, pos_margin=None):
    import run_phase5 as RP
    from lunarsim.atc import p5 as P5
    sc = P5.build("3eq", k=RP.E43_K30 * m, team_lift_share=0.10)
    roads = {"mode": DESIGN["roads"], "single_share": RP.SINGLE_SHARE, "bay_km": 1.0, "log_reservations": True}
    if pos_margin is not None:
        roads["pos_margin"] = pos_margin
    return sc.with_(fleet=list(sc.fleet) * m, n_operators=sc.n_operators * m, horizon_h=t1, plume=dict(RP.E43_PLUME),
                    p5=dict(sc.p5, dispatch_fixpoint=True, roads=roads))


def record(m, seed, t0, t1, pos_margin=None):
    """One engine run; returns the segments, start sites, reservation log, deliveries in the window and road summary."""
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    sc = _scenario(m, t1, pos_margin)
    mech = G.mechanism(DESIGN["regime"])
    segs = defaultdict(list)

    def wrapped(sim, waiting, free, **k):
        jobs = mech(sim, waiting, free, **k)
        st = sim.atc
        if st is not None and not getattr(st, "_e50", False):
            st._e50 = True
            orr = st.note_reposition

            def note(v, ss, _o=orr):
                segs[v.id].extend([list(s) for s in ss])
                return _o(v, ss)
            st.note_reposition = note
        return jobs
    for a in ("anticipates", "supports_team", "regime", "__name__"):
        if hasattr(mech, a):
            setattr(wrapped, a, getattr(mech, a))
    sim = Simulation(sc, wrapped, seed=seed, mech_kwargs=dict(DESIGN["regime_kw"]))
    start = {v.id: v.location for v in sim.vehicles}
    rl = sim.roads
    oa = rl.apply

    def apply(sim_, job, t_start):
        w = oa(sim_, job, t_start)
        for v in job.vehicles:
            segs[v.id].extend([list(s) for s in (sim_._last_segments.get(v.id) or [])])
        return w
    rl.apply = apply
    t_run = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sim.run()
    run_s = time.time() - t_run
    dl = [c for c in sim.all_cargo if c.t_delivered is not None and t0 <= c.t_delivered < t1]
    delays = np.array([c.t_delivered - c.t_ready for c in dl], float)
    urg = np.array([c.t_delivered - c.t_ready for c in dl if c.priority == 1], float)
    log = [r for r in rl.res_log if r[2] > t0 and r[1] < t1]
    return {"segs": dict(segs), "start": start, "res_log": log, "branched": dict(rl.branched),
            "ant": {v.id: G.antenna_m(v) for v in sim.vehicles}, "name": {s: rl.name(s) for s in sim.world.names},
            "delay_mean_h": float(delays.mean()) if len(delays) else float("nan"), "delivered": int(len(delays)),
            "urgent_delay_mean_h": float(urg.mean()) if len(urg) else float("nan"), "urgent_delivered": int(len(urg)),
            "road": rl.summary(), "run_s": run_s, "standoff": rl.standoff, "pads": sorted(rl.pads)}


# ------------------------------------------------------------------------------------------------ navigation
_GEO = {}


def _geo():
    """Samples, slopes, mesh line of sight (lazy, shared)."""
    if not _GEO:
        from lunarsim.atc import pnt as PN
        from lunarsim.atc import regimes as G
        sd = G._samples()
        _GEO["xy"] = np.array([s["xy_m"] for s in sd["doc"]["samples"]], float)
        _GEO["ids"] = sd["ids"]
        _GEO["legs"] = sd["doc"]["legs"]
        rd = json.load(open(os.path.join(ROOT, "data", "atc", "connecting_ridge", "roads-v1.json")))
        _GEO["slope"] = np.array(rd["slope_at_sample_deg"], float)
        _GEO["los"] = PN.LOS(G._mesh(), PN.DEFAULTS["radio_range_m"])
    return _GEO


def trajectories(rec, t0, t1):
    from lunarsim.atc import pnt as PN
    from lunarsim.illumination import Illumination
    g = _geo()
    names = rec["name"]
    il = Illumination({"start_year": YEAR}, rec["standoff"], t1, rec["pads"])
    site_index = {s: g["ids"][names[s]] for s in names}
    return PN.Trajectories.from_segments(rec["segs"], rec["start"], t0, t1, DESIGN["dt_s"], rec["ant"],
                                         lambda s: names.get(s, s), g["xy"], site_index, g["legs"], g["slope"],
                                         lit_fn=lambda t, a, b: il.lit(t, a, None if a == b else b))


def beacons(rec):
    from lunarsim.atc import pnt as PN
    g = _geo()
    names = rec["name"]
    idx = [g["ids"][names.get(b, b)] for b in PN.DEFAULTS["beacons"]]
    return idx, g["xy"][idx]


def nav(tr, rec, layer_set, seed, year=YEAR, store=False):
    from lunarsim.atc import pnt as PN
    bi, bxy = beacons(rec)
    return PN.simulate(tr, PN.LAYER_SETS[layer_set], seed, params={"year": year}, los=_geo()["los"], beacon_idx=bi,
                       beacon_xy=bxy, mast_idx=_geo()["ids"]["BASE"], store_errors=store)


def near_mask(tr, rec):
    """Vehicle-steps whose route sample sees >= 2 beacons (DESIGN region_rule)."""
    g = _geo()
    los = g["los"]
    bi, _ = beacons(rec)
    cnt = np.zeros(tr.idx.shape, int)
    for b in bi:
        for h in np.unique(tr.ant):
            sel = tr.ant == h
            if b == g["ids"]["BASE"]:
                cnt[:, sel] += los.mast[float(h)][tr.idx[:, sel]]
            else:
                cnt[:, sel] += los.mat[(2.5, float(h))][b, tr.idx[:, sel]]
    return cnt >= 2


def shift_curve(tr, res, shift_h):
    """p95 of |e| by driving hours since the window start (1 h bins up to shift_h, then one bin beyond)."""
    drv = np.cumsum(tr.ds > 0, axis=0) * tr.dt_s / 3600.0
    mv = tr.ds > 0
    out = []
    for h in range(int(shift_h)):
        m = mv & (drv > h) & (drv <= h + 1)
        out.append(float(np.quantile(res.err[m], 0.95)) if m.any() else None)
    m = mv & (drv > shift_h)
    out.append(float(np.quantile(res.err[m], 0.95)) if m.any() else None)
    return out


def violations(rec, tr, res, t0, t1):
    """True-time overlaps of conflicting single-lane reservations (module docstring, step 3)."""
    from lunarsim.atc.safety import r3_pair_conflict
    g = _geo()
    vid_col = {int(v): n for n, v in enumerate(tr.ids)}
    by_res = defaultdict(list)
    for res_id, a, b, mh, d, vid, key, f_in, f_out in rec["res_log"]:
        if b <= t0 or a >= t1:
            continue
        ids = g["legs"].get(key) or []
        if len(ids) < 2 or b <= a:
            continue
        P = g["xy"][ids]
        L = float(np.hypot(*np.diff(P, axis=0).T).sum())
        v_ms = (f_out - f_in) * L / ((b - a) * 3600.0)
        if v_ms <= 0:
            continue
        n = vid_col[int(vid)]
        sh = []
        seg = np.diff(P, axis=0)
        cum = np.concatenate([[0.0], np.cumsum(np.hypot(*seg.T))])
        for tt, f in ((a, f_in), (b, f_out)):
            k = int(np.clip(round((tt - tr.t_h[0]) * 3600.0 / tr.dt_s), 0, len(tr.t_h) - 1))
            hd = tr.head[k, n].astype(np.float64)
            if not hd.any():
                # B-118 N14: the time rounds to a step outside the leg (zero heading): use the reserved segment's own
                # direction at that point of the leg, so the along-track error still shifts the window
                j = int(np.clip(np.searchsorted(cum, f * L, side="right") - 1, 0, len(seg) - 1))
                hd = seg[j] / max(float(np.hypot(*seg[j])), 1e-9)
            e_al = float(res.e[k, n] @ hd) if res.e is not None else 0.0
            sh.append(e_al / v_ms / 3600.0)
        by_res[res_id].append((a + sh[0], b + sh[1], d, int(vid)))
    n_viol, overlap_s, pairs = 0, 0.0, 0
    for res_id, w in by_res.items():
        br = g_branched(rec, res_id)
        w.sort()
        for i in range(len(w)):
            for j in range(i + 1, len(w)):
                if w[j][0] >= w[i][1]:
                    break
                if w[i][3] == w[j][3]:
                    continue
                pairs += 1
                if r3_pair_conflict(w[i][2], w[j][2], br):
                    n_viol += 1
                    overlap_s += (min(w[i][1], w[j][1]) - w[j][0]) * 3600.0
    return {"violations": n_viol, "overlap_s": overlap_s, "same_dir_overlaps": pairs - n_viol,
            "reservations": sum(len(w) for w in by_res.values())}


def g_branched(rec, res_id):
    return bool(rec["branched"].get(res_id, False))


def bound_series(tr, res, t0):
    """Per vehicle: hourly maximum of the 95 % bound as [[t_h, bound], ...], with 0 before the window."""
    per_h = int(round(3600.0 / tr.dt_s))
    T = (len(tr.t_h) // per_h) * per_h
    hb = res.b95[:T].reshape(-1, per_h, len(tr.ids)).max(axis=1)
    out = {}
    for n, vid in enumerate(tr.ids):
        out[str(int(vid))] = [[0.0, 0.0]] + [[float(t0 + h), round(float(hb[h, n]), 3)] for h in range(hb.shape[0])]
    return out


# ------------------------------------------------------------------------------------------------ one cell
def _cache(m, seed):
    return os.path.join(CACHE, f"m{m}_s{seed}.pkl.gz")


def _stage_dir(m, seed):
    return os.path.join(CACHE, f"m{m}_s{seed}")


def _stage_path(m, seed, stage):
    return os.path.join(_stage_dir(m, seed), stage + ".pkl.gz")


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with gzip.open(tmp, "wb") as f:
        pickle.dump(obj, f)
    os.replace(tmp, path)


def _load(path):
    with gzip.open(path, "rb") as f:
        return pickle.load(f)


STAGES = ["rec", "nav"] + [f"{x}_{lab}" for lab in DESIGN["margin_sets"] for x in ("mrec", "mnav")]


def stage_rec(m, seed, keep_trace=False):
    month, t0, t1, share = _window()
    return record(m, seed, t0, t1)


def stage_nav(m, seed, keep_trace=False):
    """Navigation runs on the perfect run's trajectories, the perfect run's outcomes, and the margin bound series."""
    from lunarsim.atc import pnt as PN
    month, t0, t1, share = _window()
    rec = _load(_stage_path(m, seed, "rec"))
    out = {"mult": m, "seed": seed, "window": [t0, t1], "month": month, "nav": {}, "timing": {}}
    out["timing"]["perfect_run_s"] = round(rec["run_s"], 1)
    out["perfect"] = {k: rec[k] for k in ("delay_mean_h", "delivered", "urgent_delay_mean_h", "urgent_delivered")}
    out["perfect"]["road_wait_h"] = rec["road"]["road_wait_h"]
    out["perfect"]["reservations"] = len(rec["res_log"])
    out["n_vehicles"] = len(rec["ant"])
    t = time.time()
    tr = trajectories(rec, t0, t1)
    near = near_mask(tr, rec)
    mv = tr.ds > 0
    out["timing"]["trajectories_s"] = round(time.time() - t, 1)
    out["drive_h"] = float(mv.sum() * tr.dt_s / 3600.0)
    out["near_share_driving"] = float((near & mv).sum() / max(1, mv.sum()))
    trace, series = {}, {}
    from lunarsim.atc.pnt import lans_share
    for ls in list(DESIGN["layer_sets"]) + ["lans@2030"]:
        t = time.time()
        name = "dr+ranging+fixes+lans" if ls == "lans@2030" else ls
        year = DESIGN["lans_variant_year"] if ls == "lans@2030" else YEAR
        if name == "dr+ranging+fixes+lans" and lans_share(year) == 0.0 and "dr+ranging+fixes" in out["nav"]:
            # no LANS fix exists in this year: the set is the previous one exactly (same random streams)
            out["nav"][ls] = dict(out["nav"]["dr+ranging+fixes"], same_as="dr+ranging+fixes (LANS share 0)", nav_s=0.0)
            if ls in DESIGN["margin_sets"].values():
                series[ls] = series_prev
            if keep_trace:
                trace[ls] = trace["dr+ranging+fixes"]
            continue
        res = nav(tr, rec, name, seed, year=year, store=True)
        o = {"all": PN.error_summary(res, tr, DESIGN["budget_m"]),
             "near": PN.error_summary(res, tr, DESIGN["budget_m"], mv & near),
             "away": PN.error_summary(res, tr, DESIGN["budget_m"], mv & ~near),
             "parked": PN.error_summary(res, tr, DESIGN["budget_m"], ~mv),
             "shift_p95_m": shift_curve(tr, res, DESIGN["shift_h"]),
             "counts": res.counts, "violations_no_margin": violations(rec, tr, res, t0, t1)}
        o["nav_s"] = round(time.time() - t, 1)
        out["nav"][ls] = o
        series_prev = bound_series(tr, res, t0)
        if ls in DESIGN["margin_sets"].values():
            series[ls] = series_prev
        if keep_trace:
            trace[ls] = (res.err.copy(), res.b95.copy())
        del res
    out["_series"] = series
    if keep_trace:
        out["_trace"] = {"t_h": tr.t_h, "ids": tr.ids, "xy": tr.xy, "ds": tr.ds, "near": near, "sets": trace}
    return out


def stage_mrec(m, seed, lab):
    month, t0, t1, share = _window()
    navd = _load(_stage_path(m, seed, "nav"))
    ls = DESIGN["margin_sets"][lab]
    return record(m, seed, t0, t1, pos_margin={"k": DESIGN["k_pos"], "bound_m": navd["_series"][ls]})


def stage_mnav(m, seed, lab):
    from lunarsim.atc import pnt as PN
    month, t0, t1, share = _window()
    recm = _load(_stage_path(m, seed, f"mrec_{lab}"))
    ls = DESIGN["margin_sets"][lab]
    t = time.time()
    trm = trajectories(recm, t0, t1)
    resm = nav(trm, recm, ls, seed, store=True)
    return {"layer_set": ls, "delay_mean_h": recm["delay_mean_h"], "delivered": recm["delivered"],
            "urgent_delay_mean_h": recm["urgent_delay_mean_h"], "urgent_delivered": recm["urgent_delivered"],
            "road_wait_h": recm["road"]["road_wait_h"], "reservations": len(recm["res_log"]),
            "margin_h_mean": float(np.mean([r[3] for r in recm["res_log"]])) if recm["res_log"] else 0.0,
            "violations": violations(recm, trm, resm, t0, t1), "fix_stop_h": resm.counts["fix_stop_h"],
            "errors": PN.error_summary(resm, trm, DESIGN["budget_m"]), "run_s": round(recm["run_s"], 1),
            "nav_s": round(time.time() - t, 1)}


FP_EXCLUDE = ("lunarsim/atc/lrip/", "lunarsim/nn/", "lunarsim/vv", "lunarsim/server.py", "lunarsim/cli.py",
              "lunarsim/formats.py", "lunarsim/atc/integrity.py", "lunarsim/atc/dtn.py", "lunarsim/atc/smap.py",
              "lunarsim/atc/clocks.py", "lunarsim/atc/modelcheck.py", "lunarsim/atc/encounter")


def code_fingerprint():
    """B-118 N21: a fingerprint of the code an E50 cell comes from: every .py file of lunarsim except the parts an E50
    run does not use (FP_EXCLUDE: the codec, the network, the verification rows, the CLI, and the modules of other
    experiments), plus this runner, export_trace.py and experiments/phase5/run_phase5.py. Every stage of a cell and
    every cell of a build must carry the same one."""
    import glob as _g
    import hashlib
    files = sorted(p.replace(os.sep, "/") for p in _g.glob(os.path.join(ROOT, "lunarsim", "**", "*.py"), recursive=True))
    files = [p for p in files if not any(x in p[len(ROOT.replace(os.sep, "/")) + 1:] for x in FP_EXCLUDE)]
    files += [os.path.join(HERE, "run_e50.py"), os.path.join(HERE, "export_trace.py"),
              os.path.join(ROOT, "experiments", "phase5", "run_phase5.py")]
    h = hashlib.sha256()
    for p in files:
        h.update(os.path.relpath(p, ROOT).replace(os.sep, "/").encode())
        with open(p, "rb") as f:
            h.update(f.read().replace(b"\r\n", b"\n"))
    return h.hexdigest()[:16]


def run_stage(m, seed, stage, keep_trace=False):
    t = time.time()
    fp = code_fingerprint()                                       # B-118 N21: taken when the stage starts
    if stage == "rec":
        obj = stage_rec(m, seed)
    elif stage == "nav":
        obj = stage_nav(m, seed, keep_trace)
    elif stage.startswith("mrec_"):
        obj = stage_mrec(m, seed, stage[5:])
    else:
        obj = stage_mnav(m, seed, stage[5:])
    _dump(_stage_path(m, seed, stage), obj)
    with open(_stage_path(m, seed, stage) + ".code", "w") as f:
        f.write(fp)
    return round(time.time() - t, 1)


def assemble(m, seed):
    """All stages done: write the cell file (small) and drop the large stage files."""
    fps = set()
    for st in STAGES:                                             # B-118 N21: one code fingerprint for the cell
        p = _stage_path(m, seed, st) + ".code"
        fps.add(open(p).read().strip() if os.path.isfile(p) else None)
    if len(fps) != 1 or None in fps:
        raise SystemExit(f"m{m} s{seed}: stages made with different code ({sorted(fps, key=str)}); rerun the cell")
    navd = _load(_stage_path(m, seed, "nav"))
    out = {k: v for k, v in navd.items() if not k.startswith("_")}
    out["margin"] = {lab: _load(_stage_path(m, seed, f"mnav_{lab}")) for lab in DESIGN["margin_sets"]}
    out["code"] = fps.pop()
    try:
        import subprocess
        out["rerun_commit"] = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                             text=True, timeout=20).stdout.strip() or None
    except Exception:
        out["rerun_commit"] = None
    if "_trace" in navd:
        _dump(os.path.join(CACHE, f"trace_m{m}_s{seed}.pkl.gz"), navd["_trace"])
    _dump(_cache(m, seed), out)
    for st in STAGES:
        for p in (_stage_path(m, seed, st), _stage_path(m, seed, st) + ".code"):
            try:
                os.remove(p)
            except OSError:
                pass
    try:
        os.rmdir(_stage_dir(m, seed))
    except OSError:
        pass
    return out


def next_stage(m, seed):
    for st in STAGES:
        if not os.path.isfile(_stage_path(m, seed, st)):
            return st
    return None


def run_cell(m, seed, keep_trace=False):
    """Every remaining stage of one cell, then assemble (used by `time`)."""
    t0 = time.time()
    timing = {}
    while True:
        st = next_stage(m, seed)
        if st is None:
            break
        timing[st] = run_stage(m, seed, st, keep_trace)
    out = assemble(m, seed)
    out["timing"].update({f"stage_{k}_s": v for k, v in timing.items()})
    out["timing"]["cell_s"] = round(time.time() - t0, 1)
    return out


def _seeds(s):
    if "-" in s:
        a, b = s.split("-")
        return list(range(int(a), int(b) + 1))
    return [int(x) for x in s.split(",")]


def cmd_time(m, seed):
    o = run_cell(m, seed)
    print(json.dumps(o["timing"]), "drive_h", round(o["drive_h"], 1))
    for ls, v in o["nav"].items():
        a = v["all"]
        print(f"{ls:24s} med {a.get('median_m', 0):7.2f} p95 {a.get('p95_m', 0):8.2f} max {a.get('max_m', 0):8.1f} "
              f"over {a.get('share_b95_over_budget', 0):.3f} viol {v['violations_no_margin']['violations']} "
              f"fixes {v['counts']['fixes']} nav {v['nav_s']} s")
    for lab, v in o["margin"].items():
        print(lab, {k: v[k] for k in ("delay_mean_h", "road_wait_h", "margin_h_mean", "run_s")}, v["violations"])
    print("perfect", o["perfect"])


def cmd_run(m, seeds, max_s, start_limit=None):
    """Resumable: runs the next missing stage of the first unfinished seed, then more stages while under a third of
    the budget, or under --start-limit seconds (an 8x engine run alone takes most of a chunk)."""
    lim = max_s / 3.0 if start_limit is None else float(start_limit)
    t_start = time.time()
    first = True
    for s in seeds:
        if os.path.isfile(_cache(m, s)):
            continue
        while True:
            st = next_stage(m, s)
            if st is None:
                assemble(m, s)
                print(f"m{m} s{s} assembled", flush=True)
                break
            if not first and time.time() - t_start > lim:
                print(f"stop before m{m} s{s} {st}: time budget", flush=True)
                return
            dt = run_stage(m, s, st, keep_trace=(m == 1 and s == 1))
            first = False
            print(f"m{m} s{s} {st} {dt} s", flush=True)
    print(f"m{m}: all requested seeds done", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["time", "run", "build"])
    ap.add_argument("--mult", type=int, default=1)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--seeds", default="1")
    ap.add_argument("--max-seconds", type=float, default=480.0)
    ap.add_argument("--start-limit", type=float, default=None, help="start no new stage after this many seconds")
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    if a.cmd == "time":
        cmd_time(a.mult, a.seed)
    elif a.cmd == "run":
        cmd_run(a.mult, _seeds(a.seeds), a.max_seconds, a.start_limit)
    else:
        import e50_build
        e50_build.build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
