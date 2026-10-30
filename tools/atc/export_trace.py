"""B-80: the ATC trace pair for the site's replay ("with" vs "without" Lunar ATC), format lunarsim-atc-trace v1.

    python tools/atc/export_trace.py [--out data/atc/trace_pair] [--seed 1]

Two runs of the same scenario (p5 3eq, 30 % load, team share 0.10, landing closures, dispatch to a fixed point, start
year 2028), each simulated from 1 Jan 2028 to the end of the 2028 calendar month with the least BASE Earth visibility
(DTE, any part of the disc, the regimes' own link file), and exported for that month:
  with     C_AUCTION, message loss 0.10, terrain radio, road layer "atc"
  without  A_EARTH strict (each owner's control room on Earth), road layer "uncoordinated"
Frame: terrain/hero/sites.json (metres, BASE at [7450, 7510]) with its site ids; pads appear at their stand-off point
(where the rover works). Times: hours since 1 Jan 2028 00:00 UTC, rounded to 0.001 h. Field order: index.json "fields".
"""
from __future__ import annotations

import argparse
import calendar
import gzip
import hashlib
import json
import math
import os
import subprocess
import sys
import time
import warnings

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5")):
    if p not in sys.path:
        sys.path.insert(0, p)

FORMAT, VERSION = "lunarsim-atc-trace", 1
YEAR = 2028
COUNTERS = ("conflicts", "wasted_trips", "failed_meetings", "team_no_agreement", "parallel_winners", "claims_won",
            "claims_stale", "dropped_jobs", "status_lost")
KIND = {"conflicts": "conflict", "wasted_trips": "wasted_trip", "failed_meetings": "failed_meeting",
        "team_no_agreement": "team_no_agreement", "parallel_winners": "parallel_winner", "claims_won": "claim_won",
        "claims_stale": "claim_stale", "dropped_jobs": "dropped_job", "status_lost": "status_lost"}
FIELDS = {
    "frame": "terrain/hero/sites.json: x, y in metres (integers), BASE at [7450, 7510]; site ids as there",
    "time": "hours since 1 Jan 2028 00:00 UTC, rounded to 0.001 h",
    "fleet": "[id, owner, class, antenna_m], in id order (the order of every per-vehicle array)",
    "sites": "id -> [x_m, y_m]; pads at their stand-off point (where a rover works), as the road legs end there",
    "nodes": "radio nodes that are not vehicles: id -> [x_m, y_m, antenna_m] ('BASE' = the 10 m mast)",
    "roads": "{edges: edge id -> [[x_m, y_m], ...], res: edge id -> [resource id per point, -1 = two-lane], "
             "branched: resource id -> bool, bays: [[x_m, y_m], ...] (where a single-lane resource ends)}; edge ids "
             "are the road file's leg ids ('PAD_A@1->BASE'); no_road: edges the road file lacks (pad to pad), given as a straight line "
             "between the two sites (the engine drives them by its distance table, with no single-lane segments)",
    "legs": "vehicle id -> [[t0, t1, from, to, kind, load_kg, job, edge], ...]; kind: drive, work, wait_segment (held "
            "before a single-lane segment), wait_apron (R10 slot), hand (conflict referred to Earth; for the vehicle "
            "that goes first, a stop at the segment entry given as an edge piece with f0 = f1), reposition; edge = "
            "[edge id, f0, f1, resource] for drive and reposition (positions at sample index f x (n - 1) of the edge's "
            "polyline, linear in time; drive legs are split at every reserved segment's entry and exit, resource = its id "
            "on the piece inside it, else -1), null otherwise (from == to: the vehicle is at that site); a vehicle with "
            "no leg at a time is idle at its last 'to'",
    "jobs": "[id, t_start, t_end, vehicle ids, item ids, note, route]",
    "items": "[id, owner, mass_kg, class, priority, origin, dest, t_ready, t_picked, t_delivered, carrier, team_size]",
    "landings": "[t, lander type, pad]",
    "closures": "[t0, t1, pad, radius_km] landing keep-out windows",
    "crew": "[t0, t1, site, zone_km, v_kmh] crew walks (R6)",
    "reservations": "[resource, t_in, t_out, direction, owner, vehicle id]; resource 'apron:<pad>' for pad slots",
    "radio": "first entry [t0, links, hops_to_base, base_up] (the full state at t0); later entries [t, links_added, "
             "links_removed, hops_to_base, base_up] at each decision epoch where anything changed; links [a, b] with "
             "vehicle ids and 'BASE'; hops_to_base an array in fleet order (-1 = cut off)",
    "decisions": "[t, kind, detail]; with: award {vehicles, items, note}, conflict, wasted_trip, failed_meeting, "
                 "team_no_agreement, parallel_winner, claim_won, claim_stale, dropped_job, status_lost (detail = count "
                 "in that epoch), rally {site, vehicles, timeout_h}; without: assignment {owner, vehicles, items}, "
                 "hand_referral {vehicle, wait_h, resource}",
    "msgs": "[[t_hour, count], ...] radio transmissions per hour (with); empty when not modelled (without: Earth "
            "messages are not modelled)",
    "earth": "[[t0, t1], ...] BASE direct-to-Earth windows: every window that overlaps the run window, unclipped, plus "
             "the first one after it",
    "summary": "window totals the page recounts: urgent_items_waiting (priority-1 items ready in the window and not picked "
               "up within 24 h, or by t1), idle_robot_hours (fleet hours in the window outside every leg), "
               "messages_per_hour (sum of msgs / window hours), earth_hand_hours (hours of hand legs inside the window)",
}


def _t(x):
    return None if x is None else round(float(x), 3)


def _m(p):
    return [int(round(float(p[0]))), int(round(float(p[1])))]


def _changes_dte(year=YEAR, horizon=400 * 24.0):
    from lunarsim.atc import regimes as G
    from lunarsim.comms import _Windows, file_year_start_h
    el = G._earth_link(G.LINK_V1 if year <= 2031 else G.LINK_V3)
    dte = _Windows(el, "BASE", "any_part", "dte", file_year_start_h(el.doc["time"]["start_utc"], el.horizon_h, year))
    return G._changes(dte, horizon)


def _intervals(ch):
    """Up intervals [(a, b)] from a change list [(t, up)] (the state before the first change is its opposite)."""
    out, up, last = [], (not ch[0][1]) if ch else False, 0.0
    for t, u in ch:
        if up:
            out.append((last, t))
        last, up = t, u
    if up:
        out.append((last, math.inf))
    return out


def dark_month(year: int = YEAR):
    iv = _intervals(_changes_dte(year))
    best, t = None, 0.0
    for m in range(1, 13):
        a, b = t, t + calendar.monthrange(year, m)[1] * 24.0
        up = sum(max(0.0, min(e, b) - max(s, a)) for s, e in iv)
        if best is None or up / (b - a) < best[3]:
            best = (m, a, b, up / (b - a))
        t = b
    return best, iv


RUNS = {
    "with": {"regime": "C_AUCTION", "kw": {"loss": 0.10}, "roads": "atc",
             "label": "Lunar ATC: robots auction pooled jobs over the mesh; road layer atc (shared reservations)"},
    "without": {"regime": "A_EARTH", "kw": {"fallback": "strict", "own_teams": True, "team_lift": True},
                "roads": "uncoordinated",
                "label": "status quo: each owner's control room on Earth assigns its own robots while Earth is in view; "
                         "uncoordinated roads (conflicts settled by hand through Earth)"},
}


def _scenario(name, t1):
    import run_phase5 as RP
    from lunarsim.atc import p5 as P5
    spec = RUNS[name]
    sc = P5.build("3eq", k=RP.E43_K30, team_lift_share=0.10)
    return sc.with_(horizon_h=t1, plume=dict(RP.E43_PLUME),
                    p5=dict(sc.p5, dispatch_fixpoint=True,
                            roads={"mode": spec["roads"], "single_share": RP.SINGLE_SHARE, "bay_km": 1.0}))


def run_trace(name: str, seed: int, t0: float, t1: float, earth_iv):
    import numpy as np
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    spec = RUNS[name]
    sc = _scenario(name, t1)
    mech = G.mechanism(spec["regime"])
    kw = dict(spec["kw"], start_year=YEAR)
    rec = {"jobs": [], "legs": {}, "radio": [], "decisions": [], "hand": [], "msgs": {}, "shifts": []}
    radio_prev = {"state": None, "t": None}
    last_m, last_sent = {}, [0]

    def radio_state(sim, st, t):
        alive = sorted(sim.vehicles, key=lambda v: v.id)
        nodes = st._robot_nodes(sim, t, [v for v in alive if getattr(v, "alive", True)])
        up = st.base_up(t)
        if up:
            nodes = nodes + [("BASE", st.site_index("BASE"), G.ANT_MAST_M)]
        adj = st._graph(nodes)
        hops = st._bfs(adj, "BASE") if up else {}
        links = sorted({tuple(sorted((a, b), key=str)) for a in adj for b in adj[a]}, key=str)
        return (tuple(links), tuple(hops.get(v.id, -1) for v in alive), bool(up))

    def wrapped(sim, waiting, free, **k):
        st = sim.atc
        if st is not None and not getattr(st, "_vv_rally", False):
            st._vv_rally = True
            orr = st._rally

            def rally(sim_, v, sites, _o=orr, _st=st):
                n0 = _st.m["rallies"]
                _o(sim_, v, sites)
                if _st.m["rallies"] > n0 and t0 <= sim_.t <= t1:
                    rec["decisions"].append([_t(sim_.t), "rally", {"site": v.repos_target, "vehicles": [v.id],
                                                                   "timeout_h": float(_st.cfg["timeout_h"])}])
            st._rally = rally
        jobs = mech(sim, waiting, free, **k)
        st = sim.atc
        t = sim.t
        if st is None:
            return jobs
        for c in COUNTERS:
            n = int(st.m.get(c, 0))
            d = n - last_m.get(c, 0)
            if d > 0 and t0 <= t <= t1:
                rec["decisions"].append([_t(t), KIND[c], d])
            last_m[c] = n
        sent = int(getattr(st.channel, "sent", 0))
        if t0 <= t <= t1 and st.regime.startswith("C_"):
            h = int(math.floor(t))
            rec["msgs"][h] = rec["msgs"].get(h, 0) + sent - last_sent[0]
        last_sent[0] = sent
        s = radio_state(sim, st, t)
        if t < t0:
            radio_prev["state"] = s
        elif t <= t1:
            if not rec["radio"]:
                first = radio_prev["state"] or s
                rec["radio"].append([_t(t0), [list(x) for x in first[0]], list(first[1]), first[2]])
                radio_prev["state"] = first
            if s != radio_prev["state"]:
                old, new = set(radio_prev["state"][0]), set(s[0])
                rec["radio"].append([_t(t), [list(x) for x in sorted(new - old, key=str)],
                                     [list(x) for x in sorted(old - new, key=str)], list(s[1]), s[2]])
                radio_prev["state"] = s
        return jobs
    for a in ("anticipates", "supports_team", "regime", "__name__"):
        if hasattr(mech, a):
            setattr(wrapped, a, getattr(mech, a))
    sim = Simulation(sc, wrapped, seed=seed, mech_kwargs=kw)

    def label(orig, new, hand_times):
        """Kinds of the road layer's output segments: originals are drive / work; inserted holds are waits or hand."""
        out, i = [], 0
        for s in new:
            a, b = s[0], s[1]
            if a != b:
                out.append((s, "drive"))
                i += 1
                continue
            if i < len(orig) and orig[i][0] == orig[i][1] == a and abs((s[3] - s[2]) - (orig[i][3] - orig[i][2])) < 1e-6:
                out.append((s, "work"))
                i += 1
                continue
            nxt = orig[i] if i < len(orig) else None
            k = "wait_apron" if nxt is not None and nxt[0] == nxt[1] else "wait_segment"
            if any(abs((s[3] - s[2]) - w) < 1e-6 for w in hand_times):   # the hold lasts exactly the hand wait
                k = "hand"
            out.append((s, k))
        return out
    job_id = [0]
    real_start = sim._start_job
    hooked = [False]

    def hook_roads():
        rl, st = sim.roads, sim.atc
        oh, oa = rl._hand, rl.apply

        def hand(sim_, v, t_req, hidden, key):
            before = list(rl.table.get(key, []))
            go = oh(sim_, v, t_req, hidden, key)
            # the other vehicle stops too: the engine shifts its reservation and busy time, not its leg plan; the
            # trace follows the reservation (a hand stop at the entry, the rest of that job later by the stop)
            for old, new in zip(before, rl.table.get(key, [])):
                if new[0] != old[0] and new[4] != v.id:
                    rec["shifts"].append((int(new[4]), float(old[0]), float(new[0] - old[0])))
            rec["hand"].append((v.id, t_req, go))
            if t0 <= t_req <= t1:
                rec["decisions"].append([_t(t_req), "hand_referral", {"vehicle": v.id, "wait_h": _t(go - t_req),
                                                                        "resource": str(key)}])
            return go

        def apply(sim_, job, t_start):
            orig = {v.id: [list(s) for s in (sim_._last_segments.get(v.id) or [])] for v in job.vehicles}
            n_hand = len(rec["hand"])
            w = oa(sim_, job, t_start)
            hv = {}
            for vid, tr, go in rec["hand"][n_hand:]:
                hv.setdefault(vid, []).append(go - tr)
            sim_._vv_kinds = {v.id: label(orig[v.id], sim_._last_segments.get(v.id) or [], hv.get(v.id, []))
                              for v in job.vehicles}
            return w
        rl._hand, rl.apply = hand, apply
        onr = st.note_reposition

        def note_rep(v, segs):
            for a, b, ta, tb, load in segs:
                if tb > t0 and ta < t1:
                    rec["legs"].setdefault(v.id, []).append(("reposition", a, b, ta, tb, load, None))
            return onr(v, segs)
        st.note_reposition = note_rep

    def start(job):
        if not hooked[0] and getattr(sim, "roads", None) is not None and sim.atc is not None:
            hook_roads()
            hooked[0] = True
        n0 = [v.jobs for v in job.vehicles]
        sim._vv_kinds = None
        real_start(job)
        if [v.jobs for v in job.vehicles] == n0:
            return
        job_id[0] += 1
        jid = job_id[0]
        t_end = max(v.busy_until for v in job.vehicles)
        if t_end >= t0 and sim.t <= t1:
            rec["jobs"].append([jid, _t(sim.t), _t(t_end), [v.id for v in job.vehicles],
                                [c.id for c in job.items + job.backhaul], job.note, list(job.route)])
            if sim.atc.regime.startswith("A_"):
                rec["decisions"].append([_t(sim.t), "assignment", {"owner": job.vehicles[0].owner,
                                                                   "vehicles": [v.id for v in job.vehicles],
                                                                   "items": [c.id for c in job.items]}])
            else:
                rec["decisions"].append([_t(sim.t), "award", {"vehicles": [v.id for v in job.vehicles],
                                                              "items": [c.id for c in job.items], "note": job.note}])
        kd = getattr(sim, "_vv_kinds", None) or {}
        for v in job.vehicles:
            segs = kd.get(v.id) or [(s, "work" if s[0] == s[1] else "drive") for s in (sim._last_segments.get(v.id) or [])]
            for (a, b, ta, tb, load), k in segs:
                if tb > t0 and ta < t1:
                    rec["legs"].setdefault(v.id, []).append((k, a, b, ta, tb, load, jid))
    sim._start_job = start
    t_run = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = sim.run()
    st, rl = sim.atc, sim.roads
    from lunarsim.atc.regimes import _samples, antenna_m
    sd = _samples()
    sxy = np.array([s["xy_m"] for s in sd["doc"]["samples"]], float)
    # legs, with drive legs split at the reserved segments' entries and exits
    edges_used, legs = set(), {}
    for vid, lst in rec["legs"].items():
        rows = []
        for k, a, b, ta, tb, load, jid in sorted(lst, key=lambda x: (x[3], x[4])):
            if a == b:
                rows.append([ta, tb, a, b, k, round(float(load), 1), jid, None])
                continue
            key = f"{rl.name(a)}->{rl.name(b)}"
            edges_used.add(key)
            cuts = [(0.0, 1.0, -1)]
            if k == "drive":
                trav = sorted(rl.legs.get(key, ()), key=lambda x: x[1])
                cuts, f = [], 0.0
                for res, f_in, f_out, _d in trav:
                    if f_in > f:
                        cuts.append((f, f_in, -1))
                    cuts.append((f_in, f_out, int(res)))
                    f = f_out
                if f < 1.0:
                    cuts.append((f, 1.0, -1))
            dur = tb - ta
            for f0, f1, res in cuts:
                rows.append([ta + f0 * dur, ta + f1 * dur, a, b, k, round(float(load), 1), jid,
                             [key, round(f0, 6), round(f1, 6), res]])
        for svid, t_old, stop in rec["shifts"]:
            if svid != vid or not (t0 <= t_old < t1):         # legs exist only inside the window
                continue
            hit = next((i for i, r in enumerate(rows) if abs(r[0] - t_old) < 1e-6 and r[4] in ("drive", "work")), None)
            if hit is None:
                rec.setdefault("unmatched_shifts", []).append((svid, t_old, stop))
                continue
            r = rows[hit]
            stay = None if r[7] is None else [r[7][0], r[7][1], r[7][1], -1]
            for q in rows:
                if q[6] == r[6] and q[0] >= t_old - 1e-9:
                    q[0] += stop
                    q[1] += stop
            rows.insert(hit, [t_old, t_old + stop, r[2], r[3], "hand", r[5], r[6], stay])
        legs[str(vid)] = [[_t(r[0]), _t(r[1])] + r[2:] for r in rows]
    # roads: the edges used, their resource per point, bays
    roads = {"edges": {}, "res": {}, "branched": {}, "bays": [], "no_road": []}
    bays = set()
    by_name = {}
    for vid_, rows_ in legs.items():
        for r_ in rows_:
            if r_[7] is not None:
                by_name[r_[7][0]] = (r_[2], r_[3])
    for key in sorted(edges_used):
        ids = sd["doc"]["legs"].get(key, [])
        if not ids:                                   # the road file has no leg here (pad to pad): a straight line
            a_, b_ = by_name[key]
            roads["edges"][key] = [_m(sxy[st.site_index(a_)]), _m(sxy[st.site_index(b_)])]
            roads["res"][key] = [-1, -1]
            roads["no_road"].append(key)
            continue
        roads["edges"][key] = [_m(sxy[i]) for i in ids]
        r = [int(rl.res_of[i]) for i in ids]
        roads["res"][key] = r
        for j in range(1, len(r)):
            if r[j] != r[j - 1]:
                bays.add(tuple(_m(sxy[ids[j] if r[j] >= 0 else ids[j - 1]])))
        for x in set(r):
            if x >= 0:
                roads["branched"][str(x)] = bool(rl.branched.get(x, False))
    roads["bays"] = [list(b) for b in sorted(bays)]
    names = sorted(set([v.location for v in sim.vehicles] + list(sim.world.pads) + [c.origin for c in sim.all_cargo]
                       + [c.dest for c in sim.all_cargo] + ["BASE"]))
    sites = {}
    for nme in names:
        try:
            sites[nme] = _m(sxy[st.site_index(nme)])
        except Exception:
            pass
    reservations = []
    for res, lst in rl.table.items():
        for ta, tb, d, owner, vid in lst:
            if tb > t0 and ta < t1:
                reservations.append([f"apron:{res[1]}" if isinstance(res, tuple) else int(res), _t(ta), _t(tb), int(d),
                                     owner, int(vid)])
    reservations.sort(key=lambda r: (r[1], str(r[0])))
    items = [[c.id, c.owner, round(c.mass_kg, 1), c.cls, c.priority, c.origin, c.dest, _t(c.t_ready), _t(c.t_picked),
              _t(c.t_delivered), c.carrier, c.team_size] for c in sorted(sim.all_cargo, key=lambda c: c.id)
             if c.t_ready <= t1 and (c.t_delivered is None or c.t_delivered >= t0)]
    e = rl.cfg["eva"]
    earth, after = [], None
    for a, b in earth_iv:
        if b > t0 and a < t1:
            earth.append([_t(a), _t(b) if math.isfinite(b) else None])
        elif a >= t1 and after is None:
            after = [_t(a), _t(b) if math.isfinite(b) else None]
    if after:
        earth.append(after)
    msgs = [[h, n] for h, n in sorted(rec["msgs"].items())]
    # window totals, computed from the exported events as the page recounts them
    W = t1 - t0
    urgent = sum(1 for it in items if it[4] == 1 and t0 <= it[7] <= t1 and
                 ((it[8] if it[8] is not None else t1) - it[7] > 24.0 or (it[8] is None and t1 - it[7] > 24.0)))
    busy = 0.0
    for vid, rows in legs.items():
        iv = sorted((max(r[0], t0), min(r[1], t1)) for r in rows if r[1] > t0 and r[0] < t1)
        cur = None
        for a, b in iv:
            if cur is None or a > cur[1]:
                if cur:
                    busy += cur[1] - cur[0]
                cur = [a, b]
            else:
                cur[1] = max(cur[1], b)
        if cur:
            busy += cur[1] - cur[0]
    hand_h = sum(min(r[1], t1) - max(r[0], t0) for rows in legs.values() for r in rows if r[4] == "hand"
                 and r[1] > t0 and r[0] < t1)
    summary = {"urgent_items_waiting": int(urgent), "idle_robot_hours": round(len(sim.vehicles) * W - busy, 3),
               "messages_per_hour": round(sum(n for _, n in msgs) / W, 3), "earth_hand_hours": round(hand_h, 3)}
    doc = {"format": FORMAT, "version": VERSION, "name": name, "label": spec["label"], "seed": seed,
           "regime": spec["regime"], "settings": dict(spec["kw"], roads=spec["roads"], start_year=YEAR,
                                                      scenario="p5 3eq, 30 % load, team share 0.10, landing closures, "
                                                               "fixpoint"),
           "window_h": [_t(t0), _t(t1)], "run_h": [0.0, _t(t1)], "summary": summary,
           "fleet": [[v.id, v.owner, v.cls.name, antenna_m(v)] for v in sorted(sim.vehicles, key=lambda v: v.id)],
           "sites": sites, "nodes": {"BASE": _m(sxy[st.site_index("BASE")]) + [G.ANT_MAST_M]}, "roads": roads,
           "legs": legs, "jobs": rec["jobs"], "items": items,
           "landings": [[_t(t), lt.name, pad] for t, lt, pad in sim.landing_schedule if t0 <= t <= t1],
           "closures": [[_t(a), _t(b), pad, float(sim.plume.R)] for a, b, pad in sim.plume.windows if b >= t0 and a <= t1],
           "crew": [[_t(a), _t(b), "BASE", float(e["zone_km"]), float(e["v_crew_kmh"])] for a, b in rl.eva
                    if b >= t0 and a <= t1],
           "reservations": reservations, "radio": rec["radio"], "decisions": rec["decisions"], "msgs": msgs,
           "earth": earth}
    if rec.get("unmatched_shifts"):
        raise RuntimeError(f"hand stops not placed in the legs: {rec['unmatched_shifts']}")
    return doc, sim, out


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                              timeout=20).stdout.strip() or None
    except Exception:
        return None


def main(out_dir: str, seed: int):
    (month, t0, t1, share), iv = dark_month()
    os.makedirs(out_dir, exist_ok=True)
    idx = {"format": FORMAT, "version": VERSION, "commit": _commit(), "seed": seed, "year": YEAR,
           "frame": {"source": "terrain/hero/sites.json", "units": "m", "base_xy_m": [7450, 7510]},
           "window": {"month": month, "name": calendar.month_name[month], "t0_h": t0, "t1_h": t1,
                      "base_dte_share": round(share, 4),
                      "rule": "the 2028 calendar month with the least BASE direct-to-Earth visibility"},
           "time": "hours since 1 Jan 2028 00:00 UTC", "runs": {}, "fields": FIELDS}
    for name in ("with", "without"):
        t_run = time.time()
        doc, _, _ = run_trace(name, seed, t0, t1, iv)
        raw = json.dumps(doc, separators=(",", ":"), allow_nan=False).encode()
        path = os.path.join(out_dir, f"{name}.json.gz")
        with open(path, "wb") as f:
            with gzip.GzipFile(fileobj=f, mode="wb", mtime=0, compresslevel=9) as g:
                g.write(raw)
        idx["runs"][name] = {"file": f"{name}.json.gz", "label": doc["label"], "regime": doc["regime"],
                             "settings": doc["settings"], "bytes": os.path.getsize(path), "bytes_json": len(raw),
                             "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(), "summary": doc["summary"],
                             "counts": {k: len(doc[k]) for k in ("jobs", "items", "landings", "closures", "crew",
                                                                  "reservations", "radio", "decisions", "msgs",
                                                                  "earth")}}
        print(name, idx["runs"][name]["bytes"], "B gz,", len(raw), "B json,", idx["runs"][name]["counts"],
              doc["summary"], round(time.time() - t_run, 1), "s", flush=True)
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(idx, f, indent=1)
        f.write("\n")
    print("window", idx["window"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "atc", "trace_pair"))
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(580, exit=True)
    main(a.out, a.seed)
