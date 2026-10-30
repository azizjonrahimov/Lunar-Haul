"""Roads and rules of the road inside the logistics engine (B-77, paper P2 at logistics resolution).

Scenario.p5["roads"] (opt-in) = {mode, single_share, bay_km, apron_slots, t_hand, eva, start_year}. At every job
commit (after the plume hold) the road layer walks each vehicle's planned legs over the route samples
(earth_link-v1-samples legs, 100 m apart) and applies, in time order:
- R3 single-lane segments with exclusive reservations: the single-lane samples (single_share of the route samples,
  ASSUMED: the 5 m DEM shows no corridor narrower than 10 m at the 15-20 deg limits, so the narrowest places at
  10 deg are marked first; data/atc/connecting_ridge/roads-v1.json, results/ATC_roads_narrow.json) form physical
  segments (consecutive along any leg), split by passing bays every bay_km. A vehicle enters a (sub)segment only with
  the whole segment reserved for its traversal window; a reservation in the opposite direction that overlaps is a
  conflict (vehicles in the same direction may follow). Reservations end at a bay or junction, so the exit-bay rule
  holds by construction and no vehicle waits inside a segment; the reservation table is filled one job at a time,
  so circular waits (deadlock) cannot arise.
- R4 / R8 priority among requests of the same dispatch call: urgent cargo, then loaded before empty, then the earlier
  filed request, then the lower vehicle id (owner identity never matters); earlier commits keep their reservations.
- R10 pad apron slots: at most apron_slots vehicles load or unload at a pad at once.
- R6 crew zones: an EVA schedule (Assumed: 2 a week, 6 h, at the habitat, BASE); a leg that starts or ends at BASE
  inside an EVA crosses the slow zone (R_crew,slow 50 m) at v_crew = 1 km/h.
- R5 landing closures: the engine's plume model (Scenario.plume keepout_km / standdown_h), unchanged.
- Modes: "atc": one shared reservation table; a conflict means waiting at the bay until the segment is free (granted
  in milliseconds when linked). A robot that cannot reach the base computer when it files (its position not seen by
  the BASE mast; R7) cannot have an unconfirmed reservation assumed: its conflict goes to Earth like an uncoordinated
  one. By default (r7 False) the reservation travels with the job assignment, which reached the robot, so every robot
  files at commit; r7 True files only from the start site or the first route sample the BASE mast sees. "uncoordinated": each owner sees only its own vehicles' reservations; a conflict with another owner's vehicle
  stops both at the conflict time until it is settled by hand from Earth (t_hand, only while BASE sees Earth).
  The other vehicle's stop extends its busy time; its already recorded deliveries are not moved (stated limitation).
"""
from __future__ import annotations

import gzip
import json
import math
import os
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .safety import Reserve, safety_check

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROADS_FILE = os.path.join(ROOT, "data", "atc", "connecting_ridge", "roads-v1.json")
SAMPLES_FILE = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1-samples.json.gz")
DEFAULTS = {"r7": False, "mode": "atc", "single_share": 0.15, "bay_km": 1.0, "apron_slots": 2, "t_hand": 2.0,
            "eva": {"per_week": 2, "duration_h": 6.0, "first_h": 30.0, "zone_km": 0.05, "v_crew_kmh": 1.0},
            "start_year": None, "planet": "moon", "mars": None}
# Mars (B-82, E47): Earth contact for hand-resolution of an uncoordinated conflict. Flags: S = Spec, A = Assumed.
MARS_DEFAULTS = {
    "rtt_min": 20.0,                  # one of 6, 20, 44 min; S (light time 3-22 min each way)
    "relay": False,                   # base: direct to Earth only; variant: one areostationary relay (continuous); A
    "sol_h": 24.6597,                 # S (mean solar day)
    "dte_fraction": 0.5,              # share of each sol with Earth above the horizon at the base; A
    "conjunction_start_d": 200.0,     # day of the year the solar-conjunction blackout starts; A (fixed date)
    "conjunction_days": 14.0,         # S/A (~2 weeks of no contact per conjunction; B-82 spec: ~14 days a year)
    "storms": [[90.0, 5.0], [270.0, 5.0]],   # [start day, days] dust storms as comms-loss bursts; A (B-82 spec)
}
SINGLE_SHARE_FLAG = ("ASSUMED: the 5 m DEM cannot see boulders, crater rims, shadows or graded one-lane roads; "
                     "the narrowest places at a 10 deg slope limit are marked first")
_CACHE: Dict[str, Any] = {}


def _load():
    if "roads" not in _CACHE:
        with open(ROADS_FILE, encoding="utf-8") as f:
            _CACHE["roads"] = json.load(f)
        with open(SAMPLES_FILE, "rb") as f:
            _CACHE["samples"] = json.loads(gzip.decompress(f.read()))
    return _CACHE["roads"], _CACHE["samples"]


def single_lane_set(share: float) -> np.ndarray:
    """The first round(share x samples) route samples by corridor width at 10 deg (then 8 deg, then id); never a
    junction (site or pad)."""
    roads, sdoc = _load()
    n = len(sdoc["samples"])
    w10, w8 = np.array(roads["width_m"]["10"]), np.array(roads["width_m"]["8"])
    junc = set(roads["junctions"])
    order = sorted((i for i in range(n) if i not in junc), key=lambda i: (w10[i], w8[i], i))
    k = int(round(float(share) * n))
    mask = np.zeros(n, bool)
    mask[order[:k]] = True
    return mask


def build_segments(single: np.ndarray, bay_km: float) -> Tuple[np.ndarray, Dict[int, bool], Dict[str, list]]:
    """(resource id per sample or -1, branched per segment, per-leg traversals [(res, f_in, f_out, dir)])."""
    _, sdoc = _load()
    xy = np.array([s["xy_m"] for s in sdoc["samples"]], float)
    adj: Dict[int, set] = {}
    for ids in sdoc["legs"].values():
        for a, b in zip(ids[:-1], ids[1:]):
            if single[a] and single[b] and a != b:
                adj.setdefault(a, set()).add(b)
                adj.setdefault(b, set()).add(a)
    seg = np.full(len(xy), -1, int)
    pos = np.zeros(len(xy))
    branched: Dict[int, bool] = {}

    def bfs(src, comp):
        dist, dq = {src: 0.0}, deque([src])
        while dq:
            u = dq.popleft()
            for w in adj.get(u, ()):
                if w not in dist:
                    dist[w] = dist[u] + float(np.hypot(*(xy[w] - xy[u])))
                    dq.append(w)
        return dist

    nseg = 0
    for i in np.flatnonzero(single):
        if seg[i] >= 0:
            continue
        d0 = bfs(int(i), None)
        end = min(d0, key=lambda u: (-d0[u], u))
        dd = bfs(end, None)
        for u, d in dd.items():
            seg[u] = nseg
            pos[u] = d
        branched[nseg] = any(len(adj.get(u, ())) > 2 for u in dd)
        nseg += 1
    bay_m = max(1.0, float(bay_km) * 1000.0)
    res = np.full(len(xy), -1, int)
    rid: Dict[Tuple[int, int], int] = {}
    for u in np.flatnonzero(seg >= 0):
        key = (int(seg[u]), int(pos[u] // bay_m))
        res[u] = rid.setdefault(key, len(rid))
    res_branched = {r: branched[k[0]] for k, r in rid.items()}
    # direction of a traversal: the leg's heading against the resource's axis (its lowest- to highest-position sample;
    # for a one-sample resource, the first heading seen), so a one-sample traversal still has a direction
    members: Dict[int, List[int]] = {}
    for u in np.flatnonzero(res >= 0):
        members.setdefault(int(res[u]), []).append(int(u))
    axis: Dict[int, np.ndarray] = {}
    for r, us in members.items():
        if len(us) > 1:
            lo, hi = min(us, key=lambda u: pos[u]), max(us, key=lambda u: pos[u])
            axis[r] = xy[hi] - xy[lo]
    legs: Dict[str, list] = {}
    for leg in sorted(sdoc["legs"]):
        ids = sdoc["legs"][leg]
        out, n = [], len(ids)
        k = 0
        while k < n:
            r = res[ids[k]]
            if r < 0:
                k += 1
                continue
            j = k
            while j + 1 < n and res[ids[j + 1]] == r:
                j += 1
            f_in, f_out = (k / (n - 1), (j + 1) / (n - 1)) if n > 1 else (0.0, 1.0)
            heading = xy[ids[min(j + 1, n - 1)]] - xy[ids[max(k - 1, 0)]]
            ax = axis.setdefault(int(r), heading)
            d = 1 if float(np.dot(heading, ax)) >= 0 else -1
            out.append((int(r), f_in, min(1.0, f_out), d))
            k = j + 1
        legs[leg] = out
    return res, res_branched, legs


class RoadLayer:
    def __init__(self, sim):
        c = dict(DEFAULTS)
        c.update(sim.sc.p5.get("roads") or {})
        eva = dict(DEFAULTS["eva"])
        eva.update(c.get("eva") or {})
        c["eva"] = eva
        if c["mode"] not in ("atc", "uncoordinated"):
            raise ValueError("roads mode must be 'atc' or 'uncoordinated'")
        self.cfg = c
        self.sim = sim
        self.standoff = str(sim.sc.pad_standoff_km) if sim.sc.pad_standoff_km is not None else "1"
        self.pads = set(sim.world.pads)
        self.single = single_lane_set(c["single_share"])
        self.res_of, self.branched, self.legs = build_segments(self.single, c["bay_km"])
        self.table: Dict[Any, List[Tuple[float, float, int, str, int]]] = {}
        self.m = {"wait_h": 0.0, "apron_wait_h": 0.0, "eva_slow_h": 0.0, "conflicts": 0, "hand_conflicts": 0,
                  "hand_wait_h": 0.0, "other_stop_h": 0.0, "r7_fallbacks": 0, "jobs": 0, "traversals": 0,
                  "deadlocks": 0}
        self.wait_by_owner: Dict[str, float] = {}
        H = float(sim.sc.horizon_h)
        e = c["eva"]
        step = 168.0 / max(1e-9, float(e["per_week"]))
        self.eva = [(t, t + float(e["duration_h"])) for t in np.arange(float(e["first_h"]), H, step)] if e["per_week"] else []
        if c["planet"] == "mars":
            m = dict(MARS_DEFAULTS)
            m.update(c.get("mars") or {})
            c["mars"] = m
            self.dte = None
        else:
            y = c["start_year"] if c["start_year"] is not None else int(sim.mech_kwargs.get("start_year", 2028))
            from .regimes import LINK_V1, LINK_V3, _earth_link
            from ..comms import _Windows, file_year_start_h
            el = _earth_link(LINK_V1 if y <= 2031 else LINK_V3)
            self.dte = _Windows(el, "BASE", "any_part", "dte", file_year_start_h(el.doc["time"]["start_utc"], el.horizon_h, int(y)))
        self._covered = None
        self._cover_memo: Dict[Tuple[str, float], float] = {}
        self._mast_seen = None

    # --------------------------------------------------------------------------------------------- helpers
    def name(self, site: str) -> str:
        return f"{site}@{self.standoff}" if site in self.pads else site

    def priority_key(self, job):
        """R4 / R8 within a dispatch call: urgent cargo first, loaded before empty, earlier filed, lower vehicle id."""
        items = job.items + job.backhaul
        prio = min((c.priority for c in items), default=9)
        ready = min((c.t_ready for c in items), default=math.inf)
        return (prio, 0 if items else 1, ready, min(v.id for v in job.vehicles))

    def _linked(self, v) -> bool:
        """R7: can the robot reach the base computer when it files? (its site seen by the BASE mast)"""
        if self._covered is None:
            from .regimes import _mesh, _samples, ANT_MAST_M, antenna_m
            rm = _mesh()
            ids = _samples()["ids"]
            self._covered = {}
            for h in (1.0, 2.5):
                self._covered[h] = {s for s in self.sim.world.names
                                    if s == "BASE" or rm.link(0, ids[self.name(s)], ANT_MAST_M, h)}
        from .regimes import antenna_m
        return v.location in self._covered[antenna_m(v)]

    def _leg_cover(self, key: str, v) -> float:
        """Leg fraction of the first route sample whose position sees the BASE mast (R7 filing point); inf if none."""
        from .regimes import antenna_m
        h = antenna_m(v)
        k = (key, h)
        if k not in self._cover_memo:
            if self._mast_seen is None:
                from .radio import DEFAULT_D_MAX_M
                from .regimes import _mesh
                rm = _mesh()
                self._mast_seen = {}
                for hh, c in ((2.5, 0), (1.0, 1)):
                    ok = (rm.mast_clear_dm[c] >= 0) & (rm.mast_d <= DEFAULT_D_MAX_M)
                    self._mast_seen[hh] = set(rm.mast_j[ok].tolist()) | {rm.base}
            _, sdoc = _load()
            ids = sdoc["legs"].get(key, [])
            seen = self._mast_seen[h]
            f = next((i / (len(ids) - 1) if len(ids) > 1 else 0.0 for i, sid in enumerate(ids) if sid in seen), math.inf)
            self._cover_memo[k] = f
        return self._cover_memo[k]

    def _hand_until(self, t: float) -> float:
        if self.dte is None:                                   # Mars: contact, then staff time and the round trip
            m = self.cfg["mars"]
            return self._mars_next_contact(t) + float(self.cfg["t_hand"]) + float(m["rtt_min"]) / 60.0
        up, dt = self.dte.next_change(t)
        return t + (0.0 if up else dt) + float(self.cfg["t_hand"])

    def _mars_next_contact(self, t: float) -> float:
        """First time >= t with Earth contact from the Mars base: not in the conjunction blackout or a dust storm, and
        (without relay) Earth above the horizon (the first dte_fraction of each sol)."""
        m = self.cfg["mars"]
        blocks = [(float(m["conjunction_start_d"]) * 24.0, float(m["conjunction_days"]) * 24.0)]
        blocks += [(float(a) * 24.0, float(d) * 24.0) for a, d in m["storms"]]
        sol = float(m["sol_h"])
        for _ in range(1000):
            moved = False
            for a, d in blocks:
                yr = 8766.0
                tt = t % yr
                if a <= tt < a + d:                            # repeats every year
                    t += a + d - tt
                    moved = True
            if not m["relay"]:
                ph = t % sol
                if ph >= sol * float(m["dte_fraction"]):
                    t += sol - ph
                    moved = True
            if not moved:
                return t
        return t

    def _eva_extra(self, a: str, b: str, t0: float, t1: float) -> float:
        e = self.cfg["eva"]
        if "BASE" not in (a, b) or a == b:
            return 0.0
        tb = t0 if a == "BASE" else t1
        if any(s <= tb < s2 for s, s2 in self.eva):
            return float(e["zone_km"]) / float(e["v_crew_kmh"])
        return 0.0

    def _conflicts(self, res, t_in, t_out, d, v, mine_only: bool):
        """R3 via the safety program (lunarsim/atc/safety.py, the single source of truth)."""
        return safety_check(self.table, Reserve(res, t_in, t_out, v.id, v.owner, d=d, kind="segment",
                                                branched=self.branched.get(res, False), mine_only=mine_only)).conflicts

    def _apron_conflicts(self, pad, t_in, t_out, v, mine_only: bool):
        """R10 via the safety program."""
        return safety_check(self.table, Reserve(("apron", pad), t_in, t_out, v.id, v.owner, kind="slots",
                                                slots=int(self.cfg["apron_slots"]), mine_only=mine_only)).conflicts

    # --------------------------------------------------------------------------------------------- commit
    def _hand(self, sim, v, t_req: float, hidden, key) -> float:
        """A conflict nobody planned for: both stop at the conflict, Earth settles it (t_hand, while BASE sees
        Earth); the vehicle already holding the reservation goes first. Returns when this vehicle may go."""
        self.m["hand_conflicts"] += 1
        tc = max(t_req, min(x[0] for x in hidden))
        tr = self._hand_until(tc)
        stop = max(0.0, tr - tc)
        go = t_req
        table = self.table.get(key, [])
        for x in hidden:                                  # the other vehicle stops too, then goes first
            u = sim.vehicles[x[4]]
            u.busy_until = max(u.busy_until, x[1] + stop)
            sim._push(u.busy_until, "FREE", None)
            self.m["other_stop_h"] += stop
            self.wait_by_owner[u.owner] = self.wait_by_owner.get(u.owner, 0.0) + stop
            if x in table:
                table[table.index(x)] = (x[0] + stop, x[1] + stop) + tuple(x[2:])
            go = max(go, x[1] + stop)
        go = max(go, tr)
        self.m["hand_wait_h"] += go - t_req
        self.wait_by_owner[v.owner] = self.wait_by_owner.get(v.owner, 0.0) + go - t_req
        return go

    def apply(self, sim, job, t_start: float) -> float:
        """Extra hours for the job under the road rules; reserves its traversals; updates sim._last_segments."""
        self.m["jobs"] += 1
        atc = self.cfg["mode"] == "atc"
        worst = 0.0
        for v in job.vehicles:
            segs = sim._last_segments.get(v.id) or []
            shift = 0.0
            new_segs: List[list] = []
            linked = (self._linked(v) if self.cfg["r7"] else True) if atc else False   # R7 variant: filing needs the mast
            sees_all = atc and linked
            if atc and not linked:
                self.m["r7_unlinked_jobs"] = self.m.get("r7_unlinked_jobs", 0) + 1
            for a, b, t0, t1, load in segs:
                t0s, t1s = t0 + shift, t1 + shift
                if a == b:
                    if a in self.pads and t1 > t0:                       # R10 apron slot while loading / unloading
                        key = ("apron", a)
                        while True:
                            occ = self._apron_conflicts(a, t0s, t1s, v, mine_only=not sees_all)
                            if occ:                                      # known: wait for the first slot to free
                                w = min(x[1] for x in occ) - t0s
                                self.m["apron_wait_h"] += w
                            else:
                                hid = self._apron_conflicts(a, t0s, t1s, v, mine_only=False)
                                if not hid:
                                    break
                                if atc:
                                    self.m["r7_fallbacks"] += 1
                                full = [x for x in self.table[key] if x[4] in {h[3] for h in hid}]
                                w = self._hand(sim, v, t0s, [x for x in full if x[0] < t1s and x[1] > t0s][:1], key) - t0s
                            new_segs.append([a, a, t0s, t0s + w, 0.0])
                            shift += w
                            t0s, t1s = t0s + w, t1s + w
                        self.table.setdefault(key, []).append((t0s, t1s, 0, v.owner, v.id))
                    new_segs.append([a, b, t0s, t1s, load])
                    continue
                ev = self._eva_extra(a, b, t0s, t1s)                     # R6 crew zone at BASE
                if ev > 0:
                    self.m["eva_slow_h"] += ev
                    t1s += ev
                    shift += ev
                dur = t1s - t0s
                key = f"{self.name(a)}->{self.name(b)}"
                cov = self._leg_cover(key, v) if atc and not linked else None
                for res, f_in, f_out, d in self.legs.get(key, ()):        # R3 single-lane segments
                    self.m["traversals"] += 1
                    if cov is not None and cov <= f_in:                   # passes a covered point before entering
                        linked = sees_all = True
                    while True:
                        t_in, t_out = t0s + f_in * dur, t0s + f_out * dur
                        known = self._conflicts(res, t_in, t_out, d, v, mine_only=not sees_all)
                        if known:                                         # wait at the bay before the segment
                            self.m["conflicts"] += 1
                            w = max(x[1] for x in known) - t_in
                            self.m["wait_h"] += w
                            self.wait_by_owner[v.owner] = self.wait_by_owner.get(v.owner, 0.0) + w
                        else:
                            hidden = self._conflicts(res, t_in, t_out, d, v, mine_only=False)
                            if not hidden:
                                break
                            if atc:
                                self.m["r7_fallbacks"] += 1          # unlinked: no reservation assumed (R7)
                            w = self._hand(sim, v, t_in, hidden, res) - t_in
                        new_segs.append([a, a, t0s, t0s + w, load])
                        shift += w
                        t0s, t1s = t0s + w, t1s + w
                    self.table.setdefault(res, []).append((t_in, t_out, d, v.owner, v.id))
                new_segs.append([a, b, t0s, t1s, load])
                if atc and not linked and self._leg_cover(key, v) <= 1.0:   # heard the base somewhere on this leg
                    linked = sees_all = True
            sim._last_segments[v.id] = new_segs
            worst = max(worst, shift)
        return worst

    def summary(self) -> Dict[str, float]:
        out = {f"road_{k}": float(v) for k, v in self.m.items()}
        out.update({"road_single_share": float(self.cfg["single_share"]), "road_bay_km": float(self.cfg["bay_km"]),
                    "road_single_km": float(self.single.sum()) * 0.1,
                    "road_resources": int(self.res_of.max() + 1) if (self.res_of >= 0).any() else 0})
        for o, w in sorted(self.wait_by_owner.items()):
            out[f"road_wait_h_owner_{o}"] = w
        return out
