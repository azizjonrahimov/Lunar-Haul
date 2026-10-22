"""Dispatch mechanisms.

Each mechanism has the signature
    mechanism(sim, waiting: List[Cargo], free: List[Vehicle], **kw) -> List[Job]
and may only use information available at sim.t.

Mechanisms
----------
inhouse          Status quo: each cargo owner is served by one contracted carrier.
                 Oldest item first, nearest feasible vehicle, one item per trip.
pooled_greedy    All vehicles in one pool, otherwise identical to inhouse.
central_assign   One-shot optimal assignment of free vehicles to waiting items
                 (Hungarian algorithm on travel-time cost), one item per trip.
marketplace      Pooled sequential single-item auction with bundling by insertion,
                 priority-aware ordering, team lift for oversize items, backhaul
                 of return cargo and night-aware acceptance. Flags turn each
                 component off for ablations.
"""
from __future__ import annotations

import math

from typing import Dict, List, Optional, Tuple
import itertools

import numpy as np

from .assign import min_cost_assignment
from .engine import Job, Simulation, TEAM_SETUP_H
from .entities import Cargo, Vehicle


def _feasible_single(v: Vehicle, c: Cargo) -> bool:
    return v.compatible(c) and c.mass_kg <= v.cls.capacity_kg


def _approach_h(sim: Simulation, v: Vehicle, c: Cargo) -> float:
    return sim.travel_h(v, v.location, c.origin, False, False, sim.t)


def _single_job_hours(sim: Simulation, v: Vehicle, c: Cargo) -> float:
    job = Job([v], [c], [c.dest])
    return sim.job_plan(job, sim.t)[0]


def _comms_blocked(sim: Simulation, v: Vehicle, c: Cargo) -> bool:
    """Phase 4: with the Earth-link rule on, a vehicle that needs the link cannot take a job whose link never comes."""
    cm = getattr(sim, "comms", None)
    if cm is None or not cm.active or not cm.needs_link(v.autonomy):
        return False
    return not math.isfinite(_single_job_hours(sim, v, c))


# ----------------------------------------------------------------------------
# Baselines
# ----------------------------------------------------------------------------

def _greedy(sim: Simulation, waiting: List[Cargo], free: List[Vehicle], pooled: bool,
            priority: bool = False) -> List[Job]:
    jobs = []
    used = set()
    order = sorted(waiting, key=lambda c: ((c.priority if priority else 0), c.t_ready))
    for c in order:
        best, best_h = None, None
        for v in free:
            if v.id in used or not _feasible_single(v, c):
                continue
            if not pooled and sim.carrier_of.get(c.owner, c.owner) != v.owner:
                continue
            if _comms_blocked(sim, v, c):
                continue
            h = _approach_h(sim, v, c)
            if best is None or h < best_h:
                best, best_h = v, h
        if best is not None:
            used.add(best.id)
            jobs.append(Job([best], [c], [c.dest], note="greedy"))
    return jobs


def inhouse(sim, waiting, free, **kw):
    return _greedy(sim, waiting, free, pooled=False)


def pooled_greedy(sim, waiting, free, **kw):
    return _greedy(sim, waiting, free, pooled=True)


def central_assign(sim, waiting, free, **kw):
    """Hungarian assignment minimising total job hours, one item per vehicle."""
    items = [c for c in waiting]
    if not items or not free:
        return []
    BIG = 1e6
    cost = np.full((len(free), len(items)), BIG)
    for i, v in enumerate(free):
        for j, c in enumerate(items):
            if _feasible_single(v, c):
                # weight waiting age lightly so starved items are not ignored forever
                age = sim.t - c.t_ready
                h = _single_job_hours(sim, v, c)
                if math.isfinite(h):            # Phase 4 comms: inf = the link never comes (stays BIG)
                    cost[i, j] = h - 0.05 * age
    rows, cols = min_cost_assignment(cost)
    jobs = []
    for i, j in zip(rows, cols):
        if cost[i, j] < BIG / 2:
            jobs.append(Job([free[i]], [items[j]], [items[j].dest], note="hungarian"))
    return jobs


# ----------------------------------------------------------------------------
# Marketplace: pooled SSI auction with bundling, team lift, backhaul, night-aware
# ----------------------------------------------------------------------------

PRIORITY_WEIGHT_H = {1: 6.0, 2: 2.0, 3: 0.0}   # hours of "urgency credit" per priority class
AGE_WEIGHT = 0.08                               # hours of credit per hour waited


def _bid(sim: Simulation, v: Vehicle, bundle: List[Cargo], route: List[str], priority: bool,
         w: Optional[dict] = None) -> float:
    """Marginal-cost bid in USD for serving the bundle (vehicle operating hours at the
    vehicle's per-hour price plus operator time), minus an urgency credit that lets
    urgent or long-waiting items win vehicles earlier."""
    job = Job([v], bundle, route)
    hours = sim.job_plan(job, sim.t)[0]
    cost = sim.job_cost_usd(job, hours)
    # generalised cost: carrier's variable cost plus the shippers' value of delivery time
    tot = cost
    w = w or {}
    vot_scale = w.get("vot_scale", 1.0)
    for c in bundle:
        idx = route.index(c.dest)
        frac = (idx + 1) / len(route)
        tot += vot_scale * sim.sc.vot_usd_per_h.get(c.priority, 100.0) * hours * frac
    if priority:
        pw = {1: w.get("w_p1", PRIORITY_WEIGHT_H[1]), 2: w.get("w_p2", PRIORITY_WEIGHT_H[2]), 3: 0.0}
        aw = w.get("w_age", AGE_WEIGHT)
        for c in bundle:
            tot -= (pw[c.priority] + aw * (sim.t - c.t_ready)) * sim.sc.urgency_usd_per_h
    return tot


def _best_route(sim: Simulation, origin: str, dests: List[str]) -> List[str]:
    """Shortest visiting order for up to 4 distinct destinations (brute force)."""
    uniq = list(dict.fromkeys(dests))
    if len(uniq) <= 1:
        return uniq
    best, best_len = None, None
    for perm in itertools.permutations(uniq):
        L = sim.world.equiv_flat_km(origin, perm[0])
        for a, b in zip(perm[:-1], perm[1:]):
            L += sim.world.equiv_flat_km(a, b)
        if best is None or L < best_len:
            best, best_len = list(perm), L
    return best


def _try_bundle(sim: Simulation, v: Vehicle, seed_item: Cargo, pool: List[Cargo],
                max_items: int, priority: bool, w: Optional[dict] = None) -> Tuple[List[Cargo], List[str], float]:
    """Insertion heuristic: starting from one item, add waiting items at the same
    pad while capacity allows and the marginal hours per added item stay small."""
    bundle = [seed_item]
    route = [seed_item.dest]
    base_hours = sim.job_plan(Job([v], bundle, route), sim.t)[0]
    cands = [c for c in pool if c is not seed_item and c.origin == seed_item.origin
             and v.compatible(c)]
    cands.sort(key=lambda c: (c.dest != seed_item.dest, c.priority, c.t_ready))
    for c in cands:
        if len(bundle) >= max_items:
            break
        if sum(x.mass_kg for x in bundle) + c.mass_kg > v.cls.capacity_kg:
            continue
        new_route = _best_route(sim, seed_item.origin, route + [c.dest])
        if len(new_route) > 4:
            continue
        new_hours = sim.job_plan(Job([v], bundle + [c], new_route), sim.t)[0]
        # accept if the detour is cheaper than a separate trip would be
        separate = _single_job_hours(sim, v, c)
        if new_hours - base_hours < 0.8 * separate:
            bundle.append(c)
            route = new_route
            base_hours = new_hours
    bid = _bid(sim, v, bundle, route, priority, w)
    return bundle, route, bid


def _night_ok(sim: Simulation, v: Vehicle, job: Job) -> bool:
    if v.cls.night_ops:
        return True
    dur = sim.job_plan(job, sim.t)[0]
    return sim.t + dur <= sim.next_night_start(sim.t)


def _team_for(sim: Simulation, c: Cargo, free: List[Vehicle], used: set) -> Optional[List[Vehicle]]:
    cands = [v for v in free if v.id not in used and v.cls.can_team_lift and v.compatible(c)]
    cands.sort(key=lambda v: -v.cls.capacity_kg)
    for k in (2, 3):
        for combo in itertools.combinations(cands, k):
            if sum(v.cls.capacity_kg for v in combo) >= c.mass_kg:
                return list(combo)
    return None


MAX_POOL = 40                # auction considers at most this many waiting items (oldest/most urgent first)
CONSOLIDATE_FILL = 0.7       # dispatch deferrable bulk lots once a vehicle is this full...
CONSOLIDATE_MAX_WAIT_H = 24  # ...or once the oldest lot has waited this long


ANTICIPATE_WINDOW_H = 48.0    # look this far ahead in the published landing schedule
ANTICIPATE_MARGIN_H = 1.0     # arrive at the pad this long before the first item is ready


def _anticipate(sim: Simulation, free: List[Vehicle], used: set, pool: List[Cargo]) -> None:
    """Anticipatory staging. Landings are published in advance; when a landing is
    due within the window and no vehicle is at (or heading to) its pad, send the
    nearest idle, compatible vehicle so that it arrives just before offloading
    finishes. Repositioning never pre-empts waiting cargo: only vehicles that the
    auction left idle are used, and only outside the night for vehicles that
    cannot work in the dark."""
    for t_land, lt, pad in sim.upcoming_landings(ANTICIPATE_WINDOW_H):
        staged = any((v.location == pad and v.busy_until <= sim.t) or v.repos_target == pad
                     or getattr(v, "staged_for", None) == pad for v in sim.vehicles)   # staged_for: Phase-3 shelter staging
        if staged:
            continue
        t_first = t_land + lt.offload_h[0]
        cands = [v for v in free if v.id not in used and v.repos_target is None and v.location != pad]
        if not cands:
            continue
        v = min(cands, key=lambda u: sim.travel_h(u, u.location, pad, False, False, sim.t))
        h = sim.travel_h(v, v.location, pad, False, False, sim.t)
        depart = max(sim.t, t_first - ANTICIPATE_MARGIN_H - h)
        # never stage a vehicle that would be caught by the night on the way
        if not v.cls.night_ops and depart + h > sim.next_night_start(depart):
            continue
        sim.schedule_reposition(v, pad, depart)
        used.add(v.id)


def marketplace(sim, waiting, free, bundling=True, team_lift=True, backhaul=True,
                night_aware=True, priority=True, consolidate=True, anticipate=True, max_items=10,
                batch_h=0.0, w_p1=None, w_p2=None, w_age=None, fill=None, max_wait=None,
                vot_scale=None, **kw):
    jobs: List[Job] = []
    used = set()
    pool = list(waiting)
    w = {k: v for k, v in (("w_p1", w_p1), ("w_p2", w_p2), ("w_age", w_age), ("vot_scale", vot_scale))
         if v is not None}
    fill = CONSOLIDATE_FILL if fill is None else fill
    max_wait = CONSOLIDATE_MAX_WAIT_H if max_wait is None else max_wait
    if consolidate and bundling:
        # Hold back deferrable bulk lots until there is a full load or they are old.
        bulk = [c for c in pool if c.cls == "bulk" and c.priority >= 3]
        if bulk:
            oldest_wait = sim.t - min(c.t_ready for c in bulk)
            by_lane = {}
            for c in bulk:
                by_lane.setdefault((c.origin, c.dest), []).append(c)
            cap_ref = max((v.cls.capacity_kg for v in free if any(_feasible_single(v, c) for c in bulk)), default=0)
            for lane, lots in by_lane.items():
                mass = sum(c.mass_kg for c in lots)
                age = sim.t - min(c.t_ready for c in lots)
                if cap_ref > 0 and mass < fill * cap_ref and age < max_wait:
                    for c in lots:
                        pool.remove(c)
                    # wake the dispatcher when the oldest lot reaches the maximum wait
                    sim._push(sim.t + (max_wait - age) + 1e-6, "WAKE", None)
    # 1. oversize items first (they need teams, and teams need several free vehicles)
    if team_lift:
        single_max = max((v.cls.capacity_kg for v in free), default=0)
        oversize = [c for c in pool if c.mass_kg > single_max]
        oversize.sort(key=lambda c: (c.priority, c.t_ready))
        for c in oversize:
            team = _team_for(sim, c, free, used)
            if team is None:
                continue
            job = Job(team, [c], [c.dest], note="team")
            if night_aware and not all(_night_ok(sim, v, job) for v in team):
                continue
            for v in team:
                used.add(v.id)
            jobs.append(job)
            pool.remove(c)
    # 2. sequential single-item auction with bundling. To keep each dispatch call
    #    polynomial under heavy backlogs, only the MAX_POOL most urgent / oldest
    #    items are auctioned in one call; the rest wait for the next event.
    if len(pool) > MAX_POOL:
        pool.sort(key=lambda c: (c.priority, c.t_ready))
        pool = pool[:MAX_POOL]
    while True:
        vehicles = [v for v in free if v.id not in used]
        if not vehicles or not pool:
            break
        best = None  # (bid, v, bundle, route)
        for v in vehicles:
            for c in pool:
                if not _feasible_single(v, c):
                    continue
                if bundling:
                    bundle, route, bid = _try_bundle(sim, v, c, pool, max_items, priority, w)
                else:
                    bundle, route = [c], [c.dest]
                    bid = _bid(sim, v, bundle, route, priority, w)
                if not math.isfinite(bid):         # Phase 4 comms: a needed Earth link never comes
                    continue
                if best is None or bid < best[0]:
                    best = (bid, v, bundle, route)
        if best is None:
            break
        bid, v, bundle, route = best
        job = Job([v], bundle, route, note="auction")
        if night_aware and not _night_ok(sim, v, job):
            # try to shrink the bundle to finish before dark; else leave the vehicle idle
            used.add(v.id)
            continue
        # 3. backhaul: return cargo waiting at the last stop that fits on this vehicle
        if backhaul:
            last = route[-1]
            ret = [c for c in pool if c.origin == last and c not in bundle and v.compatible(c)
                   and c.dest in sim.world.pads]
            ret.sort(key=lambda c: c.t_ready)
            bh, m = [], 0.0
            for c in ret:
                if m + c.mass_kg <= v.cls.capacity_kg:
                    bh.append(c)
                    m += c.mass_kg
            if bh:
                # all backhaul items must go to the same pad in this simple version
                pad = bh[0].dest
                bh = [c for c in bh if c.dest == pad]
                job.backhaul = bh
        used.add(v.id)
        jobs.append(job)
        for c in bundle + job.backhaul:
            pool.remove(c)
    # 4. anticipatory staging with whatever is still idle
    if anticipate:
        _anticipate(sim, free, used, pool)
    return jobs


# convenience wrappers for ablations
def marketplace_no_bundling(sim, w, f, **kw):
    kw.pop("bundling", None)
    return marketplace(sim, w, f, bundling=False, **kw)


def marketplace_no_team(sim, w, f, **kw):
    kw.pop("team_lift", None)
    return marketplace(sim, w, f, team_lift=False, **kw)


def marketplace_no_backhaul(sim, w, f, **kw):
    kw.pop("backhaul", None)
    return marketplace(sim, w, f, backhaul=False, **kw)


def marketplace_no_night(sim, w, f, **kw):
    kw.pop("night_aware", None)
    return marketplace(sim, w, f, night_aware=False, **kw)


def marketplace_no_priority(sim, w, f, **kw):
    kw.pop("priority", None)
    return marketplace(sim, w, f, priority=False, **kw)


def marketplace_no_consolidate(sim, w, f, **kw):
    kw.pop("consolidate", None)
    return marketplace(sim, w, f, consolidate=False, **kw)


def marketplace_no_anticipate(sim, w, f, **kw):
    kw.pop("anticipate", None)
    return marketplace(sim, w, f, anticipate=False, **kw)


MECHANISMS = {
    "inhouse": inhouse,
    "pooled_greedy": pooled_greedy,
    "central_assign": central_assign,
    "marketplace": marketplace,
    "marketplace_no_bundling": marketplace_no_bundling,
    "marketplace_no_team": marketplace_no_team,
    "marketplace_no_backhaul": marketplace_no_backhaul,
    "marketplace_no_night": marketplace_no_night,
    "marketplace_no_priority": marketplace_no_priority,
    "marketplace_no_consolidate": marketplace_no_consolidate,
    "marketplace_no_anticipate": marketplace_no_anticipate,
}

marketplace.supports_team = True
marketplace_no_bundling.supports_team = True
marketplace_no_backhaul.supports_team = True
marketplace_no_night.supports_team = True
marketplace_no_priority.supports_team = True
marketplace_no_team.supports_team = False
marketplace_no_consolidate.supports_team = True
marketplace_no_anticipate.supports_team = True
for _f in (marketplace, marketplace_no_bundling, marketplace_no_backhaul, marketplace_no_night,
           marketplace_no_priority, marketplace_no_team, marketplace_no_consolidate):
    _f.anticipates = True
marketplace_no_anticipate.anticipates = False
