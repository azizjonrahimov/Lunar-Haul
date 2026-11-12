"""E54 (B-94, Phase 6, H14): store-and-forward and the lost-link rule against drop-and-retry.

    python tools/atc/run_e54.py run --seeds 1-30 [--max-seconds 480]     # resumable, one cache file per seed
    python tools/atc/run_e54.py build                                    # -> results/E54_dtn.json, E54_table.csv
    python tools/atc/run_e54.py ledger                                   # -> results/E54_ledger.json (lifetimes)

Per seed: the E50 scenario at 1x (p5 3eq, 30 % load, C_AUCTION, loss 0.10, roads atc, July 2028), with the engine's
events recorded: every job commit (its vehicles and time) and the end of each vehicle's last leg of the job, every
single-lane reservation. Over the month's contact plan (lunarsim/atc/dtn.py), message by message:
- TASK_AWARD from the base to each vehicle of a job at its commit (lifetime = the lease, 1 h: an award not delivered
  in time is a lost job, re-auctioned);
- RESERVE_GRANT from the base to the vehicle at the commit (lifetime 60 s by bundle, note 03 C5: else no reservation
  and the vehicle stops before the entry);
- TASK_STATE from the vehicle to the base at the end of its job (lifetime 1 h);
- one ledger bundle a day from the base to Earth (10 kB Assumed; lifetime 14 days, note 03 D "logs 14 d") through the
  BASE direct-to-Earth windows (the regimes' link file, any part of the disc) with a 14-day Earth blackout imposed
  over days 8-22 of the window (the H14 condition);
- STATUS every 10 s for the base's age of information (note 03 E7).
Protocols: drop_retry, sf (store-and-forward with custody), sf_ll (sf + the lost-link ladder); per-hop loss 0.10,
0.25, 0.40 (lunarsim.atc.messages LOSS_LEVELS). Sizes from the LRIP codec (B-93).
Stuck reservations: a reservation whose holder has no path to the base at t_out + grace (60 s) and stays unheard;
without the lost-link rule the base must keep it blocked until the holder is heard (stuck past its timeout for that
long); with the rule the holder's behaviour is defined (it finishes or never enters a single-lane segment and stops
at the next safe point), so the base releases it at its timeout: 0 stuck by construction, and the hours that would
otherwise have been blocked are reported.
H14 (PREREG6): at loss 0.25 with the 14-day blackout, sf_ll loses fewer jobs than drop_retry (paired bootstrap CI
of the difference excludes 0) and leaves no reservation stuck past its timeout.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
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

CACHE = os.path.join(ROOT, ".cache", "atc", "e54")
OUT_JSON = os.path.join(ROOT, "results", "E54_dtn.json")
OUT_CSV = os.path.join(ROOT, "results", "E54_table.csv")
PROTOCOLS = ["drop_retry", "sf", "sf_ll"]
LOSSES = [0.10, 0.25, 0.40]
BLACKOUT_DAYS = (8.0, 22.0)
LEDGER_BYTES = 10_000
B = 20000


def record(seed, t0, t1):
    """E50's perfect-position run (run_e50.record) plus the job commits and job ends."""
    import run_e50 as E5
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    sc = E5._scenario(1, t1)
    mech = G.mechanism(E5.DESIGN["regime"])
    segs = defaultdict(list)
    jobs = []

    def wrapped(sim, waiting, free, **k):
        out = mech(sim, waiting, free, **k)
        st = sim.atc
        if st is not None and not getattr(st, "_e54", False):
            st._e54 = True
            orr = st.note_reposition

            def note(v, ss, _o=orr):
                segs[v.id].extend([list(s) for s in ss])
                return _o(v, ss)
            st.note_reposition = note
        return out
    for a in ("anticipates", "supports_team", "regime", "__name__"):
        if hasattr(mech, a):
            setattr(wrapped, a, getattr(mech, a))
    sim = Simulation(sc, wrapped, seed=seed, mech_kwargs=dict(E5.DESIGN["regime_kw"]))
    start = {v.id: v.location for v in sim.vehicles}
    rl = sim.roads
    oa = rl.apply

    def apply(sim_, job, t_start):
        w = oa(sim_, job, t_start)
        ends = {}
        for v in job.vehicles:
            ss = [list(s) for s in (sim_._last_segments.get(v.id) or [])]
            segs[v.id].extend(ss)
            ends[v.id] = max((s[3] for s in ss), default=sim_.t)
        jobs.append({"t": float(sim_.t), "vehicles": [int(v.id) for v in job.vehicles], "end": ends})
        return w
    rl.apply = apply
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sim.run()
    return {"segs": dict(segs), "start": start, "res_log": [r for r in rl.res_log if r[2] > t0 and r[1] < t1],
            "branched": dict(rl.branched), "ant": {v.id: G.antenna_m(v) for v in sim.vehicles},
            "name": {s: rl.name(s) for s in sim.world.names}, "standoff": rl.standoff, "pads": sorted(rl.pads),
            "jobs": [j for j in jobs if t0 <= j["t"] < t1]}


def earth_up_fn(t0h, t1h, dt_s):
    """BASE direct-to-Earth per step (the regimes' 2028 link file), with the 14-day blackout imposed."""
    import export_trace as XT
    iv = XT._intervals(XT._changes_dte(2028))
    T = int(round((t1h - t0h) * 3600.0 / dt_s))
    up = np.zeros(T, bool)
    th = t0h + np.arange(T) * dt_s / 3600.0
    for a, b in iv:
        up |= (th >= a) & (th < b)
    day = (th - t0h) / 24.0
    up &= ~((day >= BLACKOUT_DAYS[0]) & (day < BLACKOUT_DAYS[1]))
    return up


def messages(rec, t0h, t1h, N, vid_col):
    from lunarsim.atc.dtn import BASE, Msg
    from lunarsim.atc.lrip import codec as C
    sz = {k: v["default"] for k, v in C.size_table().items()}
    out, mid = [], 0
    for j in rec["jobs"]:
        t = (j["t"] - t0h) * 3600.0
        for vid in j["vehicles"]:
            n = vid_col[vid]
            out.append(Msg(mid, "award", BASE, n, t, sz["TASK_AWARD"], 3600.0)); mid += 1
            out.append(Msg(mid, "grant", BASE, n, t, sz["RESERVE_GRANT"], 60.0)); mid += 1
            te = (j["end"].get(str(vid), j["end"].get(vid, j["t"])) - t0h) * 3600.0
            if te < (t1h - t0h) * 3600.0:
                out.append(Msg(mid, "task_state", n, BASE, te, sz["TASK_STATE"], 3600.0)); mid += 1
    for d in range(int((t1h - t0h) // 24)):
        out.append(Msg(mid, "ledger_earth", BASE, -2, d * 86400.0, LEDGER_BYTES, 14 * 86400.0)); mid += 1
    return out


def stuck_reservations(rec, A, tr, t0h, vid_col, grace_s):
    """(count stuck past timeout, blocked hours) without the lost-link rule: holder unheard at t_out + grace."""
    from lunarsim.atc.dtn import hops_to
    T = A.shape[0]
    N = A.shape[1] - 1
    linked = None
    n_stuck, hours = 0, 0.0
    cache = {}
    for res_id, a, b, mh, d, vid, key, f_in, f_out in rec["res_log"]:
        k = int((b - t0h) * 3600.0 / tr.dt_s + grace_s / tr.dt_s)
        if k >= T:
            continue
        n = vid_col[int(vid)]
        if k not in cache:
            cache[k] = hops_to(A[k], N)
        if cache[k][n] >= 0:
            continue
        n_stuck += 1
        kk = k
        while kk < T:
            if kk not in cache:
                cache[kk] = hops_to(A[kk], N)
            if cache[kk][n] >= 0:
                break
            kk += 1
        hours += (kk - k) * tr.dt_s / 3600.0
    return n_stuck, hours


def run_seed(seed):
    import run_e50 as E5
    from lunarsim.atc import dtn as DT
    month, t0h, t1h, share = E5._window()
    t = time.time()
    rec = record(seed, t0h, t1h)
    tr = E5.trajectories(rec, t0h, t1h)
    g = E5._geo()
    A = DT.contact_plan(tr, g["los"], g["ids"]["BASE"])
    A_ll, ll_stats = DT.lost_link_plan(A, tr)
    hb = {"A": DT.base_hops(A), "A_ll": DT.base_hops(A_ll)}
    N = A.shape[1] - 1
    vid_col = {int(v): n for n, v in enumerate(tr.ids)}
    eu = earth_up_fn(t0h, t1h, tr.dt_s)
    msgs = messages(rec, t0h, t1h, N, vid_col)
    out = {"seed": seed, "n_vehicles": N, "jobs": len(rec["jobs"]), "messages": len(msgs),
           "earth_up_share": float(eu.mean()), "lost_link": ll_stats, "cells": []}
    n_st, h_st = stuck_reservations(rec, A, tr, t0h, vid_col, DT.DEFAULTS["grace_s"])
    out["reservations"] = len(rec["res_log"])
    for loss in LOSSES:
        for proto in PROTOCOLS:
            plan = A_ll if proto == "sf_ll" else A
            rng = np.random.default_rng([seed, 94, int(loss * 100), PROTOCOLS.index(proto)])
            res = DT.simulate(plan, msgs, "drop_retry" if proto == "drop_retry" else "sf", loss, rng, tr.dt_s,
                              earth_up=lambda k: bool(eu[min(k, len(eu) - 1)]))
            by = defaultdict(lambda: {"n": 0, "lost": 0, "delay": []})
            for m in res:
                b = by[m.kind]
                b["n"] += 1
                if m.t_done is None:
                    b["lost"] += 1
                else:
                    b["delay"].append(m.t_done - m.t0)
            aoi = DT.age_of_information(plan, loss, "drop_retry" if proto == "drop_retry" else "sf",
                                        np.random.default_rng([seed, 94, 7, int(loss * 100)]), tr.dt_s,
                                        hb=hb["A_ll" if proto == "sf_ll" else "A"])
            row = {"loss": loss, "protocol": proto,
                   "kinds": {k: {"n": v["n"], "lost": v["lost"],
                                 "delay_mean_s": float(np.mean(v["delay"])) if v["delay"] else None,
                                 "delay_p95_s": float(np.quantile(v["delay"], 0.95)) if v["delay"] else None}
                             for k, v in by.items()},
                   "aoi_mean_s": float(np.mean(aoi)), "aoi_max_vehicle_s": float(np.max(aoi)),
                   "stuck_reservations": 0 if proto == "sf_ll" else n_st,
                   "stuck_hours": 0.0 if proto == "sf_ll" else h_st,
                   "blocked_hours_released_by_rule": h_st if proto == "sf_ll" else 0.0}
            out["cells"].append(row)
    out["run_s"] = round(time.time() - t, 1)
    return out


def cmd_run(seeds, max_s):
    t0 = time.time()
    os.makedirs(CACHE, exist_ok=True)
    for s in seeds:
        p = os.path.join(CACHE, f"s{s}.json")
        if os.path.isfile(p):
            continue
        if time.time() - t0 > max_s * 0.55:
            print(f"stop before seed {s}: time budget", flush=True)
            return
        o = run_seed(s)
        json.dump(o, open(p + ".tmp", "w"), allow_nan=True)
        os.replace(p + ".tmp", p)
        print(f"s{s} done in {o['run_s']} s", flush=True)
    print("all requested seeds done", flush=True)


def _boot(x, seed=0):
    x = np.asarray(x, float)
    rng = np.random.default_rng(seed)
    m = x[rng.integers(0, len(x), (B, len(x)))].mean(axis=1)
    return {"n": int(len(x)), "mean": float(x.mean()), "ci": [float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]}


def build():
    files = sorted(glob.glob(os.path.join(CACHE, "s*.json")), key=lambda p: int(os.path.basename(p)[1:-5]))
    S = [json.load(open(p)) for p in files]
    if not S:
        raise SystemExit("no E54 seeds")
    kinds = ["award", "grant", "task_state", "ledger_earth"]
    rows = []
    cell = {}
    for loss in LOSSES:
        for proto in PROTOCOLS:
            rs = [next(c for c in s["cells"] if c["loss"] == loss and c["protocol"] == proto) for s in S]
            cell[(loss, proto)] = rs
            row = {"loss": loss, "protocol": proto, "seeds": len(rs)}
            for k in kinds:
                n = sum(r["kinds"].get(k, {}).get("n", 0) for r in rs)
                lost = sum(r["kinds"].get(k, {}).get("lost", 0) for r in rs)
                d = [r["kinds"][k]["delay_mean_s"] for r in rs if r["kinds"].get(k, {}).get("delay_mean_s") is not None]
                d95 = [r["kinds"][k]["delay_p95_s"] for r in rs if r["kinds"].get(k, {}).get("delay_p95_s") is not None]
                row[f"{k}_n"] = n
                row[f"{k}_lost"] = lost
                row[f"{k}_lost_share"] = round(lost / n, 5) if n else ""
                row[f"{k}_delay_mean_s"] = round(float(np.mean(d)), 3) if d else ""
                row[f"{k}_delay_p95_s"] = round(float(np.mean(d95)), 3) if d95 else ""
            row["aoi_mean_s"] = round(float(np.mean([r["aoi_mean_s"] for r in rs])), 2)
            row["aoi_worst_vehicle_s"] = round(float(np.max([r["aoi_max_vehicle_s"] for r in rs])), 1)
            row["stuck_reservations"] = int(sum(r["stuck_reservations"] for r in rs))
            row["stuck_hours"] = round(float(sum(r["stuck_hours"] for r in rs)), 2)
            rows.append(row)
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lost = lambda r: r["kinds"].get("award", {}).get("lost", 0)
    dr, ll = cell[(0.25, "drop_retry")], cell[(0.25, "sf_ll")]
    diff = [lost(b) - lost(a) for a, b in zip(dr, ll)]
    h14 = {"rule": "loss 0.25, 14-day Earth blackout: lost jobs (expired awards) sf_ll minus drop_retry, paired bootstrap "
                   "CI excludes 0 below; and no reservation stuck past its timeout under sf_ll",
           "lost_jobs_drop_retry_per_seed": _boot([lost(a) for a in dr], 1),
           "lost_jobs_sf_ll_per_seed": _boot([lost(b) for b in ll], 2),
           "difference_sf_ll_minus_drop_retry": _boot(diff, 3),
           "stuck_reservations_sf_ll": int(sum(r["stuck_reservations"] for r in ll)),
           "stuck_reservations_drop_retry": int(sum(r["stuck_reservations"] for r in dr))}
    d = h14["difference_sf_ll_minus_drop_retry"]
    h14["supported"] = bool(d["ci"][1] < 0 and h14["stuck_reservations_sf_ll"] == 0)
    doc = {"experiment": "E54 (B-94), Phase 6, H14 (paper/atc/PREREG6.md)", "note": __doc__.split("\n\n")[1].strip(),
           "seeds": [s["seed"] for s in S], "jobs_per_seed": float(np.mean([s["jobs"] for s in S])),
           "earth_up_share": float(np.mean([s["earth_up_share"] for s in S])),
           "reservations_per_seed": float(np.mean([s["reservations"] for s in S])),
           "lost_link_returns_per_seed": float(np.mean([s["lost_link"]["returns"] for s in S])),
           "lost_link_isolation_h_saved_per_seed": float(np.mean([s["lost_link"]["isolation_h_saved"] for s in S])),
           "rows": rows, "h14": h14, "parameters": __import__("lunarsim.atc.dtn", fromlist=["DEFAULTS"]).DEFAULTS,
           "blackout_days": BLACKOUT_DAYS, "ledger_bytes": LEDGER_BYTES}
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(json.dumps(h14, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "build", "ledger"])
    ap.add_argument("--seeds", default="1-30")
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    if a.cmd == "run":
        lo, hi = (a.seeds.split("-") + [a.seeds])[:2]
        cmd_run(list(range(int(lo), int(hi) + 1)), a.max_seconds)
    elif a.cmd == "ledger":
        ledger()
    else:
        build()
    return 0




# ------------------------------------------------------------------------------------------------ ledger variants
def ledger(seeds=range(1, 31)):
    """B-94 addendum (LEAD, 11 Nov): the daily Earth-ledger bundle with lifetimes 14 d (note 03 D), 30 d, and the
    longest Earth-down interval (blackout + the direct-to-Earth gap around it) + 1 day. Base -> Earth only, so no
    vehicle contact plan is needed: simulated over 61 days from the window start so every bundle created in the
    31-day window either arrives or truly expires. -> results/E54_ledger.json"""
    import run_e50 as E5
    from lunarsim.atc import dtn as DT
    from lunarsim.atc.dtn import BASE, Msg
    month, t0h, t1h, share = E5._window()
    dt = 60.0
    span_h = 61 * 24.0
    eu = earth_up_fn(t0h, t0h + span_h, dt)
    down, run, gap = ~eu, 0, 0
    for x in down:
        run = run + 1 if x else 0
        gap = max(gap, run)
    gap_s = gap * dt
    lifetimes = {"14 d (note 03 D)": 14 * 86400.0, "30 d": 30 * 86400.0,
                 f"longest Earth-down {gap_s / 86400.0:.2f} d + 1 d": gap_s + 86400.0}
    A = np.zeros((len(eu), 1, 1), bool)
    days = int((t1h - t0h) // 24)
    out = {"longest_earth_down_d": gap_s / 86400.0, "earth_up_share_61d": float(eu.mean()), "rows": []}
    for lname, life in lifetimes.items():
        for loss in LOSSES:
            for proto in ("drop_retry", "sf"):
                deliv, lost, delay = [], [], []
                for s in seeds:
                    msgs = [Msg(d, "ledger_earth", BASE, -2, d * 86400.0, LEDGER_BYTES, life) for d in range(days)]
                    res = DT.simulate(A, msgs, proto, loss, np.random.default_rng([s, 94, 11, int(loss * 100)]), dt,
                                      earth_up=lambda k: bool(eu[min(k, len(eu) - 1)]))
                    deliv.append(sum(m.t_done is not None for m in res))
                    lost.append(sum(m.t_done is None for m in res))
                    delay += [(m.t_done - m.t0) / 86400.0 for m in res if m.t_done is not None]
                out["rows"].append({"lifetime": lname, "lifetime_d": round(life / 86400.0, 2), "loss": loss,
                                    "protocol": proto, "bundles": days * len(list(seeds)),
                                    "delivered": int(sum(deliv)), "lost": int(sum(lost)),
                                    "lost_share": round(sum(lost) / (days * len(list(seeds))), 4),
                                    "delay_mean_d": round(float(np.mean(delay)), 2) if delay else None,
                                    "delay_max_d": round(float(np.max(delay)), 2) if delay else None})
    with open(os.path.join(ROOT, "results", "E54_ledger.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    return out


if __name__ == "__main__":
    raise SystemExit(main())
