"""Where dispatch decisions are made (B-72): each regime wraps an existing allocator (lunarsim.dispatch).

    mech = regimes.mechanism("B_EARTH")          # an engine mechanism; its settings come as mech_kwargs
    Simulation(sc, mech, seed=s, mech_kwargs={"fallback": "plan_ahead", "start_year": 2038}).run()

Regimes
- O_ORACLE      the pooled marketplace with perfect, instant information (the v2 marketplace as is).
- B_EARTH       one pooled dispatcher on Earth (marketplace, or inner="central_assign"); it decides only while BASE,
                the gateway, is linked to Earth (R-1 link windows, any_part; v1 for 2028-2031, v3 after). With
                `coverage` p a relay is OR'd in (R-1's parametric relay; B_EARTH_RELAY is B_EARTH with p set).
- A_EARTH       each owner's control room on Earth assigns only its own vehicles to its own cargo (dispatch.inhouse),
                only while Earth is in view. Cross-owner conflicts at a pad apron are settled by hand: the newcomer
                waits t_hand hours, possible only while Earth is in view. No cross-owner team lifts.
- A_MOON        each owner alone, decided on the Moon by its own robots: the owner's robots that hear each other
                over the owner's own mesh (its robots only, multi-hop) decide; robots outside that partition act on
                their last instructions. Cross-owner apron conflicts still go by hand through Earth (t_hand).
- C_LEADER      pooled; an elected leader on the Moon (the base computer on the BASE mast; when it fails, after a
                re-election delay, the robot that reaches the most robots) runs the marketplace for the robots it
                reaches through the mesh (B-70 radio, multi-hop through robots and the mast). Robots outside its
                partition act on their last instructions. Status and assignment messages go through
                lunarsim.atc.messages (loss per hop); a robot whose status or assignment is lost waits for the next
                epoch (a retry wake RETRY_H later).
Lost-link procedure (Assumed; robots in practice carry one): an idle robot that does not hear its decider drives
to a rally point and waits there: for C_LEADER the nearest site (by travel time) that sees the BASE mast at its
antenna height, for A_MOON BASE (the owners' meeting point; an owner's partition that includes a robot at BASE is
its main one). Without it a robot that ends a delivery at a radio-shadowed site (ISRU, SCI_1, PSR, PAD_B on the
Connecting Ridge) is never reached again. `rally` False switches it off.
Earth fallbacks (A_EARTH, B_EARTH): `strict` (no new assignment while dark) or `plan_ahead`: when a blackout starts,
the control room's upload is used: a queue per vehicle of the items waiting at loss of signal (greedy, least
planned hours first), then a standing rule for the items it published for the blackout (landings and bulk lots;
oldest first, nearest vehicle, one item per trip; dispatch._greedy). Return items, created on the Moon, wait for
Earth.

Positions: at each decision epoch every vehicle's position is a route-sample index (B-70's point index),
interpolated along its committed plan's legs (earth_link-v1-samples legs); idle vehicles sit at their site.

Assumed constants: antenna 2.5 m on rovers, 1.0 m on MAPP-class robots and hoppers, 10 m on the BASE mast (B-70);
radio range and margin from lunarsim.atc.radio (provisional); base computer MTBF 2,000 h, repair 24 h, re-election
30 min (CADRE wakes about every 30 min); t_hand 2 h (sweep 0.5-8); retry epoch RETRY_H.
"""
from __future__ import annotations

import gzip
import json
import math
import os
from bisect import bisect_right
from collections import deque
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LINK_V1 = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1.json")
LINK_V3 = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v3.json")
SAMPLES_V1 = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1-samples.json.gz")

REGIMES = ("O_ORACLE", "B_EARTH", "B_EARTH_RELAY", "A_EARTH", "A_MOON", "C_LEADER")
A_REGIMES = ("A_EARTH", "A_MOON")
EARTH_REGIMES = ("A_EARTH", "B_EARTH", "B_EARTH_RELAY")
DEFAULTS: Dict[str, Any] = {
    "fallback": "strict",            # A_EARTH / B_EARTH while Earth is out of view: strict | plan_ahead
    "coverage": None,                # relay coverage OR'd with BASE's direct link (None = direct only)
    "start_year": 2028,
    "t_hand": 2.0,                   # Assumed (B-72 task): hours to settle a cross-owner conflict by hand, sweep 0.5-8
    "inner": "marketplace",          # B_EARTH alternative: central_assign
    "radio": "terrain",              # terrain (B-70 mesh) | perfect
    "d_max_m": None,                 # None = lunarsim.atc.radio's provisional default
    "margin_m": None,
    "loss": 0.0,                     # per-hop message loss
    "loss_model": "bernoulli",       # bernoulli | burst
    "base_mtbf_h": 2000.0,           # Assumed (B-72 task): base computer MTBF, sweep
    "base_repair_h": 24.0,           # Assumed (B-72 task)
    "reelect_h": 0.5,                # Assumed (B-72 task; CADRE wakes about every 30 min)
    "rally": True,                   # Assumed: lost-link procedure (drive to a rally point when unheard)
}
REGIME_KEYS = set(DEFAULTS)
RETRY_H = 0.05                       # Assumed: a robot whose message was lost is reconsidered 3 min later
URGENT_TARGET_H = 24.0               # PREREG: share of urgent items delivered within 24 h
SMALL_ANTENNA_PREFIXES = ("MAPP", "HOPPER", "MICRO")
ANT_ROVER_M, ANT_SMALL_M, ANT_MAST_M = 2.5, 1.0, 10.0

_EL_CACHE: Dict[str, Any] = {}
_SAMPLES: Dict[str, Any] = {}
_MESH: Dict[str, Any] = {}


def mechanism(regime: str, inner: str = "marketplace"):
    """An engine mechanism for `regime` (settings as mech_kwargs, see DEFAULTS)."""
    if regime not in REGIMES:
        raise ValueError(f"unknown regime {regime!r}; known {REGIMES}")
    pooled_inner = "inhouse" if regime in A_REGIMES else inner

    def mech(sim, waiting, free, **kw):
        st = getattr(sim, "atc", None)
        if st is None:
            st = sim.atc = ATCState(sim, regime, kw)
        return st.dispatch(sim, waiting, free, kw)

    mech.__name__ = f"atc_{regime}"
    mech.supports_team = pooled_inner == "marketplace"
    mech.anticipates = pooled_inner == "marketplace"
    mech.regime = regime
    return mech


def _inner_fn(name: str):
    from .. import dispatch
    return getattr(dispatch, name)


def _earth_link(path: str):
    from ..comms import EarthLink
    if path not in _EL_CACHE:
        _EL_CACHE[path] = EarthLink.load(path)
    return _EL_CACHE[path]


def _samples() -> Dict[str, Any]:
    if "doc" not in _SAMPLES:
        with open(SAMPLES_V1, "rb") as f:
            d = json.loads(gzip.decompress(f.read()))
        _SAMPLES["doc"] = d
        _SAMPLES["ids"] = {s["id"]: k for k, s in enumerate(d["samples"]) if s.get("id")}
    return _SAMPLES


def _mesh():
    if "rm" not in _MESH:
        from .radio import RadioMesh
        _MESH["rm"] = RadioMesh()
    return _MESH["rm"]


def antenna_m(v) -> float:
    return ANT_SMALL_M if v.cls.name.startswith(SMALL_ANTENNA_PREFIXES) else ANT_ROVER_M


def _changes(series, horizon: float) -> List[Tuple[float, bool]]:
    """(time, up after it) at every state change of a link series within [0, horizon]."""
    out, t = [], 0.0
    up, dt = series.next_change(0.0)
    out.append((0.0, up))
    while math.isfinite(dt) and t + dt <= horizon:
        t += dt
        up, dt = series.next_change(t)
        out.append((t, up))
    return out


class ATCState:
    """Per-run regime state (sim.atc); the engine calls on_advance, note_job, note_reposition and summary."""

    def __init__(self, sim, regime: str, kw: Dict[str, Any]):
        from .messages import Channel
        self.regime = regime
        c = dict(DEFAULTS)
        c.update({k: v for k, v in kw.items() if k in REGIME_KEYS})
        if regime == "B_EARTH_RELAY" and c["coverage"] is None:
            raise ValueError("B_EARTH_RELAY needs a relay coverage")
        if c["fallback"] not in ("strict", "plan_ahead"):
            raise ValueError("fallback must be 'strict' or 'plan_ahead'")
        self.cfg = c
        self.H = float(sim.sc.horizon_h)
        self.standoff = str(sim.sc.pad_standoff_km) if sim.sc.pad_standoff_km is not None else "1"
        self.pads = set(sim.world.pads)
        # Earth: BASE's direct link (the blackout yardstick for every regime) and the decision link
        from ..comms import _Windows, _Or, _Intervals, CommsModel, DEFAULT_RELAY_GAP_H, file_year_start_h
        y = int(c["start_year"])
        el = _earth_link(LINK_V1 if y <= 2031 else LINK_V3)
        t0 = file_year_start_h(el.doc["time"]["start_utc"], el.horizon_h, y)
        self.dte = _Windows(el, "BASE", "any_part", "dte", t0)
        self.earth = self.dte
        if c["coverage"] is not None:
            class _H:
                horizon_h = self.H
            iv = CommsModel._relay_intervals(_H(), float(c["coverage"]), DEFAULT_RELAY_GAP_H,
                                             np.random.default_rng([int(sim.seed), 41, 2]))
            self.earth = _Or(self.dte, _Intervals(iv))
        dte_ch = _changes(self.dte, self.H)
        self.aos = [t for t, up in dte_ch if up and t > 0]                 # ends of BASE's direct blackouts
        self._aos_i = 0
        self.backlog_at_aos: List[float] = []
        self.earth_ch = _changes(self.earth, self.H) if regime in EARTH_REGIMES else []
        self._earth_t = [t for t, _ in self.earth_ch]
        # base computer (C_LEADER): failure intervals from its own stream
        self.base_down: List[Tuple[float, float]] = []
        if regime == "C_LEADER" and math.isfinite(float(c["base_mtbf_h"])):
            rng = np.random.default_rng([int(sim.seed), 72, 1])
            t = 0.0
            while True:
                t += float(rng.exponential(float(c["base_mtbf_h"])))
                if t >= self.H:
                    break
                self.base_down.append((t, t + float(c["base_repair_h"])))
                t += float(c["base_repair_h"])
        self.channel = Channel(float(c["loss"]), c["loss_model"],
                               rng=np.random.default_rng([int(sim.seed), 72, 2]))
        rk = {}
        if c["d_max_m"] is not None:
            rk["d_max_m"] = float(c["d_max_m"])
        if c["margin_m"] is not None:
            rk["margin_m"] = float(c["margin_m"])
        self.radio_kw = rk
        # bookkeeping
        self.plans: Dict[int, List[list]] = {}
        self.bookings: Dict[str, List[Tuple[float, float, str]]] = {}
        self.locks: Dict[int, float] = {}
        self.cleared: set = set()
        self.queue: Dict[int, List[Any]] = {}
        self.queue_for: Optional[float] = None
        self._covered: Dict[float, List[str]] = {}
        self._retry_at = -1.0
        self.m = {"rallies": 0, "calls": 0, "gated_calls": 0, "blocked_calls": 0, "queue_jobs": 0, "standing_jobs": 0,
                  "hand_conflicts": 0, "hand_wait_h": 0.0, "robots_out_sum": 0.0, "robots_seen": 0,
                  "dropped_jobs": 0, "status_lost": 0}
        # wake-ups: dispatch resumes when the decision maker comes back
        wakes = []
        if regime in EARTH_REGIMES:
            wakes += [t for t, up in self.earth_ch if up and t > sim.t]
        for a, b in self.base_down:
            wakes += [a + float(c["reelect_h"]), b]
        for t in sorted(set(wakes)):
            if sim.t < t < self.H:
                sim._push(t + 1e-6, "WAKE", None)

    # ------------------------------------------------------------------------------------------- engine hooks
    def on_advance(self, sim, t_old: float, t_new: float) -> None:
        """The waiting set is constant on (t_old, t_new): record the backlog at blackout ends inside it."""
        while self._aos_i < len(self.aos) and self.aos[self._aos_i] <= t_new:
            if self.aos[self._aos_i] > t_old or t_old == 0.0:
                self.backlog_at_aos.append(sum(c.mass_kg for c in sim.waiting if not c.stranded) / 1000.0)
            self._aos_i += 1

    def note_job(self, sim, job, t_end: float) -> None:
        for v in job.vehicles:
            segs = [list(s) for s in (sim._last_segments.get(v.id) or [])]
            if segs and segs[-1][3] < t_end:
                segs.append([segs[-1][1], segs[-1][1], segs[-1][3], t_end, 0.0])
            self.plans[v.id] = segs
            for a, b, t0, t1, _ in segs:
                if a == b and a in self.pads:
                    self.bookings.setdefault(a, []).append((t0, t1, v.owner))
                    break

    def note_reposition(self, v, segs) -> None:
        self.plans[v.id] = [list(s) for s in segs]

    # ------------------------------------------------------------------------------------------- positions
    def site_index(self, site: str) -> int:
        name = f"{site}@{self.standoff}" if site in self.pads else site
        return _samples()["ids"][name]

    def leg_ids(self, a: str, b: str) -> List[int]:
        na = f"{a}@{self.standoff}" if a in self.pads else a
        nb = f"{b}@{self.standoff}" if b in self.pads else b
        return _samples()["doc"]["legs"].get(f"{na}->{nb}", [])

    def position(self, v, t: float) -> int:
        segs = self.plans.get(v.id)
        if segs and segs[0][2] <= t < segs[-1][3]:
            for a, b, t0, t1, _ in segs:
                if t0 <= t < t1:
                    if a == b:
                        return self.site_index(a)
                    ids = self.leg_ids(a, b)
                    f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
                    if not ids:
                        return self.site_index(a if f < 0.5 else b)
                    return ids[min(len(ids) - 1, int(f * len(ids)))]
            return self.site_index(segs[-1][1])
        return self.site_index(v.location)

    # ------------------------------------------------------------------------------------------- mesh
    def _graph(self, nodes: List[Tuple[Any, int, float]]) -> Dict[Any, List[Any]]:
        """Adjacency of (key, point, antenna height) nodes under the radio model."""
        adj: Dict[Any, List[Any]] = {k: [] for k, _, _ in nodes}
        perfect = self.cfg["radio"] == "perfect"
        rm = None if perfect else _mesh()
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                (ka, pa, ha), (kb, pb, hb) = nodes[i], nodes[j]
                if perfect or rm.link(pa, pb, ha, hb, **self.radio_kw):
                    adj[ka].append(kb)
                    adj[kb].append(ka)
        return adj

    @staticmethod
    def _bfs(adj, src) -> Dict[Any, int]:
        hops, q = {src: 0}, deque([src])
        while q:
            u = q.popleft()
            for w in adj[u]:
                if w not in hops:
                    hops[w] = hops[u] + 1
                    q.append(w)
        return hops

    def base_up(self, t: float) -> bool:
        return not any(a <= t < b for a, b in self.base_down)

    def leader_state(self, t: float) -> str:
        """'base', 'robot' (a robot leads after re-election) or 'none' (election under way)."""
        for a, b in self.base_down:
            if a <= t < b:
                return "robot" if t >= a + float(self.cfg["reelect_h"]) else "none"
        return "base"

    # ------------------------------------------------------------------------------------------- dispatch
    def dispatch(self, sim, waiting, free, kw) -> List[Any]:
        t = sim.t
        self.m["calls"] += 1
        inner_kw = {k: v for k, v in kw.items() if k not in REGIME_KEYS}
        r = self.regime
        if r == "O_ORACLE":
            return _inner_fn("marketplace")(sim, waiting, free, **inner_kw)
        if r in ("B_EARTH", "B_EARTH_RELAY"):
            if self.earth.next_change(t)[0]:
                return _inner_fn(self.cfg["inner"])(sim, waiting, free, **inner_kw)
            return self._dark(sim, waiting, free, pooled=True)
        if r == "A_EARTH":
            waiting = self._unlocked(waiting, t)
            if self.earth.next_change(t)[0]:
                jobs = _inner_fn("inhouse")(sim, waiting, free)
            else:
                jobs = self._dark(sim, waiting, free, pooled=False)
            return self._hand(sim, jobs, t)
        if r == "A_MOON":
            waiting = self._unlocked(waiting, t)
            ok = self._owner_partitions(sim, free, t)
            jobs = _inner_fn("inhouse")(sim, waiting, ok) if ok else []
            jobs = self._deliver(sim, jobs, t)
            return self._hand(sim, jobs, t)
        if r == "C_LEADER":
            ok = self._leader_partition(sim, free, t)
            if ok is None:
                self.m["gated_calls"] += 1
                return []
            jobs = _inner_fn("marketplace")(sim, waiting, ok, **inner_kw) if ok else []
            return self._deliver(sim, jobs, t)
        raise AssertionError(r)

    def _unlocked(self, waiting, t):
        return [c for c in waiting if self.locks.get(id(c), -1.0) <= t]

    # ---- Earth fallbacks
    def _dark(self, sim, waiting, free, pooled: bool) -> List[Any]:
        self.m["gated_calls"] += 1
        if self.cfg["fallback"] == "strict":
            if waiting and free:
                self.m["blocked_calls"] += 1
            return []
        from .. import dispatch as D
        from ..engine import Job
        t = sim.t
        t_los = self._earth_t[bisect_right(self._earth_t, t) - 1] if self._earth_t else 0.0
        if self.queue_for != t_los:
            self._build_queue(sim, [c for c in waiting if c.t_ready <= t_los and c.cls != "return"], pooled, t_los)
        p5 = getattr(sim, "p5", None)
        cand = {id(c): c for c in waiting if c.cls != "return"}           # published for the blackout
        jobs, used, taken = [], set(), set()
        for v in free:
            q = self.queue.get(v.id, [])
            while q and id(q[0]) not in cand:
                q.pop(0)
            for c in list(q):
                if id(c) in cand and id(c) not in taken and D._feasible_single(v, c):
                    q.remove(c)
                    jobs.append(Job([v], [c], [c.dest], note="queue"))
                    used.add(v.id)
                    taken.add(id(c))
                    self.m["queue_jobs"] += 1
                    break
        rest = [v for v in free if v.id not in used]
        left = [c for c in cand.values() if id(c) not in taken]
        if rest and left:
            more = D._greedy(sim, left, rest, pooled=pooled)
            for j in more:
                j.note = "standing"
            self.m["standing_jobs"] += len(more)
            jobs += more
        return jobs

    def _build_queue(self, sim, items, pooled: bool, t_los: float) -> None:
        """The upload: items waiting at loss of signal, each to the feasible vehicle with the least planned hours."""
        from .. import dispatch as D
        p5 = getattr(sim, "p5", None)
        vs = [v for v in sim.vehicles if v.alive and not (p5 is not None and p5.limited(v))]
        load = {v.id: max(0.0, v.busy_until - sim.t) for v in vs}
        self.queue = {v.id: [] for v in vs}
        for c in sorted(items, key=lambda c: (c.priority, c.t_ready)):
            best, bh = None, math.inf
            for v in vs:
                if not D._feasible_single(v, c):
                    continue
                if not pooled and sim.carrier_of.get(c.owner, c.owner) != v.owner:
                    continue
                h = load[v.id] + D._single_job_hours(sim, v, c)
                if h < bh:
                    best, bh = v, h
            if best is not None and math.isfinite(bh):
                self.queue[best.id].append(c)
                load[best.id] = bh
        self.queue_for = t_los

    # ---- hand resolution of cross-owner conflicts (A regimes)
    def _hand(self, sim, jobs, t) -> List[Any]:
        if not jobs:
            return jobs
        keep = []
        tentative: Dict[str, List[Tuple[float, float, str]]] = {}
        for job in jobs:
            pad = job.items[0].origin if job.items else None
            v0 = job.vehicles[0]
            key = (v0.id, tuple(id(c) for c in job.items))
            win = None
            if pad in self.pads and key not in self.cleared:
                sim.job_plan(job, t)
                for a, b, t0, t1, _ in sim._last_segments.get(v0.id) or []:
                    if a == b == pad:
                        win = (t0, t1)
                        break
            clash = False
            if win is not None:
                for t0, t1, owner in self.bookings.get(pad, []) + tentative.get(pad, []):
                    if owner != v0.owner and t1 > t and t0 < win[1] and win[0] < t1:
                        clash = True
                        break
            if not clash:
                keep.append(job)
                if win is not None:
                    tentative.setdefault(pad, []).append((win[0], win[1], v0.owner))
                continue
            up, dt = self.earth.next_change(t) if self.regime == "A_EARTH" else self.dte.next_change(t)
            t_res = t + (0.0 if up else dt) + float(self.cfg["t_hand"])
            if t_res <= t + 1e-12:
                keep.append(job)
                continue
            self.m["hand_conflicts"] += 1
            self.m["hand_wait_h"] += t_res - t
            self.cleared.add(key)
            for v in job.vehicles:
                v.busy_until = max(v.busy_until, t_res)
            for c in job.items:
                self.locks[id(c)] = t_res
            if math.isfinite(t_res) and t_res < self.H:
                sim._push(t_res, "FREE", None)
        return keep

    # ---- on-Moon decisions
    def _robot_nodes(self, sim, t, vehicles) -> List[Tuple[Any, int, float]]:
        return [(v.id, self.position(v, t), antenna_m(v)) for v in vehicles]

    def _owner_partitions(self, sim, free, t) -> List[Any]:
        """Free robots in their owner's main partition (own robots only); messages to the owner's lead robot."""
        alive = [v for v in sim.vehicles if v.alive]
        ok = []
        for o in sorted({v.owner for v in alive}):
            mine = [v for v in alive if v.owner == o]
            adj = self._graph(self._robot_nodes(sim, t, mine))
            comps, seen = [], set()
            for v in mine:
                if v.id in seen:
                    continue
                h = self._bfs(adj, v.id)
                seen |= set(h)
                comps.append(sorted(h))
            at_base = {v.id for v in mine if self.position(v, t) == self.site_index("BASE")}
            main = max(comps, key=lambda c: (bool(at_base & set(c)), len(c), -c[0]))
            hops = self._bfs(adj, main[0])
            f = [v for v in free if v.owner == o]
            self.m["robots_seen"] += len(f)
            self.m["robots_out_sum"] += sum(1 for v in f if v.id not in hops)
            for v in f:
                if v.id in hops:
                    if self.channel.send(hops[v.id])[0]:
                        ok.append(v)
                    else:
                        self.m["status_lost"] += 1
                else:
                    self._rally(sim, v, ["BASE"])
            self._hops = getattr(self, "_hops", {})
            self._hops.update(hops)
        return ok

    def _leader_partition(self, sim, free, t) -> Optional[List[Any]]:
        state = self.leader_state(t)
        if state == "none":
            return None
        alive = [v for v in sim.vehicles if v.alive]
        nodes = self._robot_nodes(sim, t, alive)
        if state == "base":
            nodes = nodes + [("BASE", self.site_index("BASE"), ANT_MAST_M)]
        adj = self._graph(nodes)
        if state == "base":
            hops = self._bfs(adj, "BASE")
        else:
            best = None
            for v in sorted(alive, key=lambda v: v.id):
                h = self._bfs(adj, v.id)
                if best is None or len(h) > len(best):
                    best = h
            hops = best or {}
        self._hops = hops
        self.m["robots_seen"] += len(free)
        self.m["robots_out_sum"] += sum(1 for v in free if v.id not in hops)
        ok = []
        for v in free:
            if v.id not in hops:
                self._rally(sim, v, self.covered_sites(sim, antenna_m(v)) if state == "base" else ["BASE"])
                continue
            if self.channel.send(hops[v.id])[0]:
                ok.append(v)
            else:
                self.m["status_lost"] += 1
        if len(ok) < sum(1 for v in free if v.id in hops):
            self._retry(sim)
        return ok

    def covered_sites(self, sim, h: float) -> List[str]:
        """Sites from which an antenna h m up sees the BASE mast (plus BASE itself)."""
        if h not in self._covered:
            rm = _mesh() if self.cfg["radio"] != "perfect" else None
            b = self.site_index("BASE")
            self._covered[h] = [x for x in sim.world.names
                                if x == "BASE" or rm is None or rm.link(b, self.site_index(x), ANT_MAST_M, h, **self.radio_kw)]
        return self._covered[h]

    def _rally(self, sim, v, sites: Sequence[str]) -> None:
        """Lost-link procedure: an idle robot nobody hears drives to the nearest rally site."""
        if not self.cfg["rally"] or v.repos_target is not None or v.location in sites:
            return
        dest = min(sites, key=lambda x: sim.travel_h(v, v.location, x, False, False, sim.t))
        sim.schedule_reposition(v, dest, sim.t)
        self.m["rallies"] += 1

    def _deliver(self, sim, jobs, t) -> List[Any]:
        """Assignment messages: a job starts only if every vehicle of it hears its assignment."""
        hops = getattr(self, "_hops", {})
        out = []
        for j in jobs:
            if all(self.channel.send(hops.get(v.id, 0))[0] for v in j.vehicles):
                out.append(j)
            else:
                self.m["dropped_jobs"] += 1
        if len(out) < len(jobs):
            self._retry(sim)
        return out

    def _retry(self, sim) -> None:
        """One pending retry epoch at a time (a lost message is sent again RETRY_H later)."""
        t = sim.t + RETRY_H
        if t < self.H and not (sim.t < self._retry_at <= t):
            sim._push(t, "WAKE", None)
            self._retry_at = t

    # ------------------------------------------------------------------------------------------- summary
    def _down_share(self) -> float:
        """Share of the year the regime's decision maker could not assign (Earth out of view; no leader)."""
        if self.regime in EARTH_REGIMES:
            down, ch = 0.0, self.earth_ch + [(self.H, True)]
            for (t0, up), (t1, _) in zip(ch[:-1], ch[1:]):
                if not up:
                    down += min(t1, self.H) - t0
            return down / self.H
        if self.regime == "C_LEADER":
            r = float(self.cfg["reelect_h"])
            return sum(min(b, self.H, a + r) - a for a, b in self.base_down) / self.H
        return 0.0

    def summary(self, sim) -> Dict[str, float]:
        H = self.H
        urg = [c for c in sim.all_cargo if c.priority == 1 and c.t_ready < H and not getattr(c, "lost", False)]
        waits = np.array([(c.t_delivered - c.t_ready) for c in urg if c.t_delivered is not None])
        cens = np.array([(c.t_delivered - c.t_ready) if c.t_delivered is not None else H - c.t_ready for c in urg])
        m = sim.metrics
        nveh = max(1, len(sim.vehicles))
        bl = np.array(self.backlog_at_aos) if self.backlog_at_aos else np.array([np.nan])
        return {
            "atc_regime": REGIMES.index(self.regime),
            "atc_decider_down_share": self._down_share(),
            "atc_calls": self.m["calls"], "atc_gated_calls": self.m["gated_calls"],
            "atc_blocked_calls": self.m["blocked_calls"],
            "atc_queue_jobs": self.m["queue_jobs"], "atc_standing_jobs": self.m["standing_jobs"],
            "atc_hand_conflicts": self.m["hand_conflicts"], "atc_hand_wait_h": self.m["hand_wait_h"],
            "atc_robots_out_share": self.m["robots_out_sum"] / max(1, self.m["robots_seen"]),
            "atc_status_lost": self.m["status_lost"], "atc_dropped_jobs": self.m["dropped_jobs"],
            "atc_msgs_per_robot_h": self.channel.sent / (nveh * H),
            "atc_msgs_lost": self.channel.lost, "atc_msg_latency_s_mean": self.channel.latency_s / max(1, self.channel.messages - self.channel.lost),
            "atc_base_failures": len(self.base_down), "atc_rallies": self.m["rallies"],
            "atc_urgent_items": len(urg),
            "atc_urgent_wait_mean_h": float(waits.mean()) if len(waits) else float("nan"),
            "atc_urgent_wait_mean_cens_h": float(cens.mean()) if len(cens) else float("nan"),
            "atc_urgent_wait_p95_cens_h": float(np.percentile(cens, 95)) if len(cens) else float("nan"),
            "atc_urgent_within24_share": float(np.mean([c.t_delivered is not None and c.t_delivered - c.t_ready
                                                        <= URGENT_TARGET_H for c in urg])) if urg else float("nan"),
            "atc_deadhead_share": m.km_empty / m.km_total if m.km_total > 0 else float("nan"),
            "atc_blackouts": len(self.backlog_at_aos),
            "atc_backlog_end_blackout_t_mean": float(np.nanmean(bl)),
            "atc_backlog_end_blackout_t_max": float(np.nanmax(bl)),
        }
