"""Explicit-state model checker for the rules of the road (B-78, traffic_and_safety.md §F).

A discrete road (10 m cells): a two-lane approach, a bay of 2 slots at each end of a 4-cell single-lane segment, an
east parking cell with a junction to a 2-cell spur into a landing zone, and a crew crossing at one road cell. The planner
of every vehicle is fully nondeterministic (any proposal at any time: stay, advance one cell, ask for the segment), so a
property that holds covers any planner. Every vehicle move is decided by `safety_check` (lunarsim/atc/safety.py), the
function the logistics engine and the encounter simulator call: a move is a Move from standstill with the acceleration
A_ACC for the step time T_STEP at which a free one-cell advance just fits (x + stopping distance = one cell); the leader
gap, the distance to the next line the vehicle may not cross (segment entry without the reservation, zone entry while
closing or closed) and the distance to crew go in as metres. Reservation grants are Reserve proposals. Environment moves
(also nondeterministic): the crew walks home <-> roadside <-> road cell; the landing cycles open -> notice -> closed ->
open (closure only once the vehicles that were inside at notice have left: T_pre is assumed long enough, which E44
tests in continuous time); each vehicle's radio link drops and returns.

Checks (BFS over all interleavings; states packed into integers, interchangeable vehicles sorted; hard cap):
- safety invariants on every reachable state: two vehicles in one cell and lane (bays hold 2), opposite directions both
  inside the segment, a vehicle in the segment without the reservation, a vehicle in the zone while closed, a vehicle in
  or next to the crew's road cell;
- deadlock: a non-goal state in which no vehicle can do anything although the environment is benign (zone open, links
  up, crew at home);
- liveness: from every reachable state a goal state is reachable (backward BFS); K = the longest shortest path to goal;
- livelock: strongly connected components (Tarjan, iterative) of states that cannot reach the goal.
Mutations: remove R3's exit-slot check, R5's entry check, R7's hold (a vehicle without link enters the segment as if its
request had been granted). Each must give a counterexample (trace saved).
"""
from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional, Tuple

import numpy as np

from . import safety as S
from .safety import Move, Reserve, safety_check

CELL = 10.0                                   # m; A (§F)
VEH_L = 4.0                                   # m; as encounter.py
B_FLAT = float(S.b_guaranteed(0.0, S.MU_DEFAULT))
T_STEP = math.sqrt(CELL / (0.5 * S.A_ACC + S.A_ACC ** 2 / (2 * B_FLAT)))   # s: a free advance ends exactly one cell on
CREW_SIDE_M = 10.0                            # m, the roadside position's lateral offset; A

# cells: 0, 1 west approach; 2 bay W (2 slots); 3-6 single-lane segment; 7 bay E (2 slots); 8 road (crew crossing);
# 9 east parking and junction; 10, 11 spur into the landing zone (10 = P1, 11 = P2)
X = {c: float(c) for c in range(10)}
X[10], X[11] = 10.0, 11.0                     # along the spur, continuing east (distances only along a route matter)
SEG = (3, 4, 5, 6)
BAYS = {2: 2, 7: 2}
ZONE = (10, 11)
CREW_CELL = 8
ROUTES = {
    "W2E": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    "E2W": [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
    "PAD": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 10, 9],
}
LANE = {"W2E": 0, "E2W": 1, "PAD": 0}         # two-lane cells: eastbound lane 0, westbound lane 1
DIRS = {"W2E": 1, "E2W": -1, "PAD": 1}


def _lane(route, idx):
    """Lane of a vehicle at route index idx: shared cells (segment, spur) are lane 9."""
    c = ROUTES[route][idx]
    if c in SEG or c in ZONE:
        return 9
    if route == "PAD" and idx >= 12:          # coming back from the pad: westbound on cell 9
        return 1
    return LANE[route]


def _dir(route, idx):
    if route == "PAD" and idx >= 11:
        return -1
    return DIRS[route]


@lru_cache(maxsize=None)
def move_ok(gap_cells: float, stop_cells: float, crew_m: float, crew_any_m: float, must_exit: bool) -> bool:
    """Is a one-cell advance accepted by safety_check? (gap / stop distances in cells from this cell's centre; crew in m)"""
    gap = gap_cells * CELL - VEH_L if math.isfinite(gap_cells) else math.inf
    d_stop = (stop_cells - 0.5) * CELL if math.isfinite(stop_cells) else math.inf
    m = Move(v=np.array(0.0), a_prop=np.array(S.A_ACC), dt=T_STEP, theta=np.array(0.0), mu=np.array(S.MU_DEFAULT),
             v_class=np.array(10 / 3.6), sight=np.array(1e4), gap_lead=np.array(gap), v_lead=np.array(0.0),
             d_stop=np.array(d_stop), d_crew=np.array(crew_m), must_exit=np.array(must_exit),
             a_max=S.A_ACC, d_crew_any=np.array(crew_any_m))
    ver = safety_check(None, m)
    return bool(np.all(ver.a >= S.A_ACC - 1e-12))      # accepted as proposed (a full advance)


@dataclass
class Model:
    routes: List[str]
    landing: bool = True
    crew: bool = True
    links: bool = True
    mutation: Optional[str] = None            # None, "R3_exit", "R5_entry", "R7_hold"
    symmetric: Tuple[Tuple[int, ...], ...] = ()   # groups of interchangeable vehicles (same route)
    cap: int = 3_000_000

    # state: (positions tuple, held tuple, crew, phase, must_exit mask, links mask)
    # crew: 0 home, 1 roadside, 2 on the road cell; phase: 0 open, 1 notice, 2 closed
    def init(self):
        n = len(self.routes)
        return (tuple(0 for _ in range(n)), tuple(0 for _ in range(n)), 0, 0, 0, (1 << n) - 1)

    def goal(self, st) -> bool:
        return all(p == len(ROUTES[r]) - 1 for p, r in zip(st[0], self.routes))

    def canon(self, st):
        if not self.symmetric:
            return st
        pos, held, crew, ph, mex, links = st
        pos, held = list(pos), list(held)
        lk = [(links >> i) & 1 for i in range(len(pos))]
        mx = [(mex >> i) & 1 for i in range(len(pos))]
        for grp in self.symmetric:
            items = sorted((pos[i], held[i], lk[i], mx[i]) for i in grp)
            for i, it in zip(grp, items):
                pos[i], held[i], lk[i], mx[i] = it
        return (tuple(pos), tuple(held), crew, ph,
                sum(b << i for i, b in enumerate(mx)), sum(b << i for i, b in enumerate(lk)))

    def pack(self, st) -> int:
        pos, held, crew, ph, mex, links = st
        x = 0
        for p, h in zip(pos, held):
            x = (x << 5) | (p << 1) | h
        return (((((x << 2) | crew) << 2 | ph) << 3 | mex) << 3) | links

    # ---------------------------------------------------------------------------------------------- helpers
    def cell(self, i, st):
        return ROUTES[self.routes[i]][st[0][i]]

    def in_zone(self, i, st):
        return self.cell(i, st) in ZONE

    def seg_holders(self, st, excl):
        out = []
        for j, r in enumerate(self.routes):
            if j != excl and st[1][j]:
                out.append((0.0, math.inf, _dir(r, st[0][j]), "o", j))
        return out

    def bay_count(self, st, bay):
        n = sum(1 for j in range(len(self.routes)) if self.cell(j, st) == bay)
        # vehicles holding the segment and heading into this bay (granted, not yet arrived)
        for j, r in enumerate(self.routes):
            if st[1][j] and self.cell(j, st) not in (bay,):
                exit_bay = 7 if _dir(r, st[0][j]) > 0 else 2
                if exit_bay == bay and self.cell(j, st) in SEG + (2, 7) and self.cell(j, st) != exit_bay:
                    n += 1
        return n

    def violations(self, st) -> List[str]:
        out = []
        occ = {}
        for i, r in enumerate(self.routes):
            c = self.cell(i, st)
            key = (c, 0 if c in BAYS else _lane(r, st[0][i]))
            occ.setdefault(key, []).append(i)
        for (c, ln), vs in occ.items():
            parked = [v for v in vs if c in (0, 9) and st[0][v] in (0, len(ROUTES[self.routes[v]]) - 1)]
            if len(vs) - len(parked) > BAYS.get(c, 1) - (1 if parked and len(vs) > len(parked) else 0) and len(vs) > len(parked):
                out.append(f"two vehicles in cell {c}")
        dirs_in = {_dir(self.routes[i], st[0][i]) for i in range(len(self.routes)) if self.cell(i, st) in SEG}
        if len(dirs_in) > 1:
            out.append("opposite directions in the segment")
        for i in range(len(self.routes)):
            if self.cell(i, st) in SEG and not st[1][i]:
                out.append(f"vehicle {i} in the segment without the reservation")
            if self.landing and st[3] == 2 and self.in_zone(i, st):
                out.append(f"vehicle {i} in the zone while closed")
        return out

    def edge_violations(self, kind, who, st, nx) -> List[str]:
        """R6 is about the vehicle's motion: a vehicle moving into or next to the crew's road cell."""
        if kind == "move" and self.crew and st[2] == 2:
            c = ROUTES[self.routes[who]][nx[0][who]]
            if c not in ZONE and abs(X[c] - X[CREW_CELL]) <= 1:
                return [f"vehicle {who} moved next to crew on the road"]
        return []

    # ---------------------------------------------------------------------------------------------- vehicle moves
    def _move_allowed(self, i, st, forced_exit=False):
        r = self.routes[i]
        idx = st[0][i]
        route = ROUTES[r]
        if idx >= len(route) - 1:
            return False
        nxt = route[idx + 1]
        lane_next = _lane(r, idx + 1)
        # occupancy of the next cell (bays: 2 slots)
        here = [j for j in range(len(self.routes)) if j != i and self.cell(j, st) == nxt
                and (nxt in BAYS or _lane(self.routes[j], st[0][j]) == lane_next)]   # a bay's slots serve both lanes
        start_or_end = lambda j: st[0][j] in (0, len(ROUTES[self.routes[j]]) - 1) and self.cell(j, st) in (0, 9)
        here = [j for j in here if not start_or_end(j)]
        if nxt in BAYS:                       # a bay's slots: vehicles in it plus slots reserved by segment holders
            arriving_mine = st[1][i] and (7 if _dir(r, idx) > 0 else 2) == nxt
            if self.bay_count(st, nxt) - (1 if arriving_mine else 0) >= BAYS[nxt]:
                return False
        elif len(here) >= 1:
            return False
        # leader gap (cells, same lane and direction, ahead on this route)
        gap = math.inf
        for j, rj in enumerate(self.routes):
            if j == i or start_or_end(j) and self.cell(j, st) in (0, 9):
                continue
            if _dir(rj, st[0][j]) != _dir(r, idx):
                continue
            for k in range(idx + 1, len(route)):
                if route[k] == self.cell(j, st) and _lane(r, k) == _lane(rj, st[0][j]) and route[k] not in BAYS:
                    gap = min(gap, k - idx)
                    break
        # stop lines: the segment without a held reservation; the zone while closing / closed
        stop = math.inf
        for k in range(idx + 1, len(route)):
            c = route[k]
            if c in SEG and not st[1][i] and not (self.mutation == "R7_hold" and not (st[5] >> i) & 1):
                if route[idx] not in SEG:
                    stop = min(stop, k - idx)
                break
        if self.landing and st[3] in (1, 2) and self.mutation != "R5_entry":
            for k in range(idx + 1, len(route)):
                if route[k] in ZONE and route[idx] not in ZONE:
                    stop = min(stop, k - idx)
                    break
        # crew: distance along the direction of travel (ahead only) and in any direction (slow zone)
        crew_m = crew_any = math.inf
        if self.crew and st[2] in (1, 2):
            lat = 0.0 if st[2] == 2 else CREW_SIDE_M
            dx = (X[CREW_CELL] - X[route[idx]]) * CELL
            heading = 1.0 if X[nxt] >= X[route[idx]] else -1.0
            crew_any = math.hypot(dx, lat) - (VEH_L / 2 + 0.5)
            if dx * heading >= 0:
                crew_m = crew_any
        return move_ok(float(gap), float(stop), round(crew_m, 6), round(crew_any, 6), bool(forced_exit))

    def _apply_move(self, i, st):
        pos, held, crew, ph, mex, links = st
        pos = list(pos)
        held = list(held)
        pos[i] += 1
        c = ROUTES[self.routes[i]][pos[i]]
        if c not in SEG and held[i]:
            held[i] = 0                       # left the segment into the exit bay: released
        mex2 = mex & ~(1 << i) if c not in ZONE else mex
        return (tuple(pos), tuple(held), crew, ph, mex2, links)

    def _request(self, i, st):
        """Grant of the segment (R3 via safety_check Reserve; exit-slot rule unless mutated); None if not granted."""
        r = self.routes[i]
        idx = st[0][i]
        route = ROUTES[r]
        if st[1][i] or idx >= len(route) - 1 or route[idx + 1] not in SEG:
            return None
        if self.links and not (st[5] >> i) & 1:
            return None                       # R7: no link, no new reservation
        d = _dir(r, idx)
        v = safety_check(self.seg_holders(st, i), Reserve("SEG", 0.0, math.inf, i, "o", d=d, kind="segment"))
        if not v.ok:
            return None
        exit_bay = 7 if d > 0 else 2
        if self.mutation != "R3_exit" and self.bay_count(st, exit_bay) >= BAYS[exit_bay]:
            return None
        held = list(st[1])
        held[i] = 1
        return (st[0], tuple(held)) + st[2:]

    def successors(self, st):
        out = []
        n = len(self.routes)
        for i in range(n):
            forced = self.landing and st[3] == 1 and (st[4] >> i) & 1 and self.in_zone(i, st)
            if self._move_allowed(i, st, forced_exit=forced):
                out.append(("move", i, self._apply_move(i, st)))
                if self.mutation == "R7_hold" and not (st[5] >> i) & 1:
                    pass
            g = self._request(i, st)
            if g is not None:
                out.append(("grant", i, g))
            # R7 mutation: a vehicle without link at the stop line enters as if granted
            if self.mutation == "R7_hold" and self.links and not (st[5] >> i) & 1 and not st[1][i]:
                idx = st[0][i]
                route = ROUTES[self.routes[i]]
                if idx < len(route) - 1 and route[idx + 1] in SEG and route[idx] not in SEG:
                    held = list(st[1])
                    held[i] = 1
                    out.append(("assume", i, (st[0], tuple(held)) + st[2:]))
        pos, held, crew, ph, mex, links = st
        if self.crew:
            occ8 = any(self.cell(j, st) == CREW_CELL for j in range(n))
            for c2 in {0: (1,), 1: (0, 2), 2: (1,)}[crew]:
                if c2 == 2 and occ8:
                    continue
                out.append(("crew", c2, (pos, held, c2, ph, mex, links)))
        if self.landing:
            if ph == 0:
                inside = sum(1 << j for j in range(n) if self.in_zone(j, st))
                out.append(("notice", 0, (pos, held, crew, 1, inside, links)))
            elif ph == 1 and mex == 0:
                out.append(("close", 0, (pos, held, crew, 2, 0, links)))
            elif ph == 2:
                out.append(("open", 0, (pos, held, crew, 0, 0, links)))
        if self.links:
            for i in range(n):
                out.append(("link", i, (pos, held, crew, ph, mex, links ^ (1 << i))))
        return out

    def vehicle_can_act(self, st):
        return any(k in ("move", "grant", "assume") for k, _, _ in self.successors(st))


def check(model: Model, max_seconds: float = 400.0) -> Dict:
    t0 = time.time()
    s0 = model.canon(model.init())
    ids: Dict[int, int] = {model.pack(s0): 0}
    states = [s0]
    parent = [(-1, None)]
    src, dst = [], []
    first_viol = None
    n_viol = 0
    viol_kinds: Dict[str, int] = {}
    q = deque([0])
    aborted = None
    while q:
        u = q.popleft()
        st = states[u]
        vs = model.violations(st)
        if vs:
            n_viol += 1
            for v_ in vs:
                k_ = v_.split(" ", 2)[-1] if v_.startswith("vehicle") else v_
                viol_kinds[k_] = viol_kinds.get(k_, 0) + 1
            if first_viol is None:
                first_viol = u
            continue                                  # do not expand past a violation
        for kind, who, nx in model.successors(st):
            ev = model.edge_violations(kind, who, st, nx)
            if ev:
                n_viol += 1
                for v_ in ev:
                    viol_kinds["moved next to crew"] = viol_kinds.get("moved next to crew", 0) + 1
                if first_viol is None:
                    first_viol = u
                    res_edge = (kind, who)
                continue
            nx = model.canon(nx)
            key = model.pack(nx)
            v = ids.get(key)
            if v is None:
                v = len(states)
                ids[key] = v
                states.append(nx)
                parent.append((u, (kind, who)))
                q.append(v)
                if len(states) > model.cap:
                    aborted = f"state cap {model.cap} reached"
                    break
            src.append(u)
            dst.append(v)
        if aborted or time.time() - t0 > max_seconds:
            aborted = aborted or f"time limit {max_seconds} s"
            break
    n = len(states)
    res = {"states": n, "transitions": len(src), "violating_states": n_viol, "violation_kinds": viol_kinds,
           "aborted": aborted, "seconds_bfs": round(time.time() - t0, 1)}
    if first_viol is not None:
        res["counterexample"] = _trace(states, parent, first_viol, model)
    if aborted:
        return res
    # deadlock: non-goal, benign environment, no vehicle can act
    dead = []
    for u, st in enumerate(states):
        if model.goal(st) or model.violations(st):
            continue
        if st[3] == 0 and st[2] == 0 and (not model.links or st[5] == (1 << len(model.routes)) - 1):
            if not model.vehicle_can_act(st):
                dead.append(u)
    res["deadlock_states"] = len(dead)
    if dead and "counterexample" not in res:
        res["deadlock_trace"] = _trace(states, parent, dead[0], model)
    # liveness: backward BFS from goal states over all transitions
    S_ = np.array(src, dtype=np.int64)
    D_ = np.array(dst, dtype=np.int64)
    order = np.argsort(D_, kind="stable")
    Ds, Ss = D_[order], S_[order]
    start = np.searchsorted(Ds, np.arange(n))
    end = np.searchsorted(Ds, np.arange(n), side="right")
    dist = np.full(n, -1, dtype=np.int64)
    goals = [u for u, st in enumerate(states) if model.goal(st)]
    dq = deque(goals)
    for g in goals:
        dist[g] = 0
    while dq:
        v = dq.popleft()
        for k in range(start[v], end[v]):
            u = Ss[k]
            if dist[u] < 0:
                dist[u] = dist[v] + 1
                dq.append(u)
    viol_mask = np.array([bool(model.violations(st)) for st in states])
    bad = np.flatnonzero((dist < 0) & ~viol_mask)
    res["goal_states"] = len(goals)
    res["cannot_reach_goal"] = int(len(bad))
    res["K_max_steps_to_goal"] = int(dist[dist >= 0].max()) if (dist >= 0).any() else None
    if len(bad) and "counterexample" not in res and "deadlock_trace" not in res:
        res["liveness_trace"] = _trace(states, parent, int(bad[0]), model)
    # livelock: SCCs among states that cannot reach the goal, with at least one vehicle move inside
    res["livelock_sccs"] = _livelock(bad, S_, D_, n) if len(bad) else 0
    res["seconds_total"] = round(time.time() - t0, 1)
    return res


def _livelock(bad, S_, D_, n) -> int:
    badset = np.zeros(n, bool)
    badset[bad] = True
    keep = badset[S_] & badset[D_] & (S_ != D_)
    s, d = S_[keep], D_[keep]
    adj: Dict[int, List[int]] = {}
    for a, b in zip(s.tolist(), d.tolist()):
        adj.setdefault(a, []).append(b)
    index, low, on, stack, count, idx = {}, {}, set(), [], 0, 0
    for root in bad.tolist():
        if root in index:
            continue
        work = [(root, 0)]
        while work:
            v, pi = work[-1]
            if pi == 0:
                index[v] = low[v] = idx
                idx += 1
                stack.append(v)
                on.add(v)
            nbrs = adj.get(v, [])
            if pi < len(nbrs):
                work[-1] = (v, pi + 1)
                w = nbrs[pi]
                if w not in index:
                    work.append((w, 0))
                elif w in on:
                    low[v] = min(low[v], index[w])
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[v])
            if low[v] == index[v]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == v:
                        break
                if len(comp) > 1:
                    count += 1
    return count


def _trace(states, parent, u, model):
    path = []
    while u >= 0:
        p, act = parent[u]
        st = states[u]
        path.append({"action": act, "cells": [model.cell(i, st) for i in range(len(model.routes))],
                     "held": list(st[1]), "crew": st[2], "phase": st[3], "links": st[5],
                     "violations": model.violations(st)})
        u = p
    return list(reversed(path))
