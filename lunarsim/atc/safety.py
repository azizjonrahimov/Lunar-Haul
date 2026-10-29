"""The safety program of Lunar ATC (B-78): the one place where the rules of the road are decided.

`safety_check(state, proposal)` is the single source of truth for the logistics engine (lunarsim/atc/roads.py calls it
at job commit for R3 and R10), the encounter simulator (lunarsim/atc/encounter.py, every vehicle at 10 Hz) and the
model checker (lunarsim/atc/modelcheck.py, every vehicle move). Two kinds of proposal:

- Reserve(...): may this vehicle hold this resource (single-lane segment, junction tile, pad apron) for this time window?
  Decided on the reservation entries the caller can see: the shared table (atc) or only the vehicle's owner's entries
  (uncoordinated; R7 for a vehicle that cannot reach the base computer). A reservation that is not confirmed is never
  assumed (Dresner's rule): the caller passes only confirmed entries. Verdict: ok, or the conflicting entries and the
  time the resource frees (the fallback is to hold before the entry).
- Move(...): numpy arrays, one element per vehicle (any shape): the planner's proposed acceleration for the next step,
  with the vehicle's kinematic situation. Accepted only if, after the step, every rule below still holds with the
  vehicle braking at its guaranteed deceleration; otherwise the first safe candidate (no acceleration, then full
  braking) is substituted (Simplex / post-posed shield). Verdict: accepted acceleration, a mask of modified proposals,
  and a mask of vehicles for which no candidate satisfies the rules (should never be set when the invariant holds).

Rules (research_notes/Lunar ATC/traffic_and_safety.md, table B; flags: S = Spec/sourced, M = Modelled/derived,
A = Assumed):
- R1 keep distance (same direction): RSS minimum gap d_min(v_rear, v_front) with response time RHO_S, the follower's
  maximum acceleration A_ACC, its guaranteed braking (slope- and friction-limited) and the leader's maximum braking
  B_MAX, plus static margin D0_M. Below d_min the only accepted action is the proper response (braking).
- R2 speed: v <= class limit, v <= the speed whose reaction + stopping distance fits the clear sight distance, and on
  downhill slopes over 10 deg the speed that stops within 15 m. Where friction cannot hold the slope, v_max = 0.
- R3 single-lane segments: exclusive reservation for the whole segment and window (opposite directions conflict; any
  overlap conflicts on a branched segment) and a free slot at the exit (bay, junction, parking). Without a confirmed
  reservation the vehicle must be able to stop before the entry.
- R5 landing closure: a stop line at the zone boundary while the zone is closed or closing; a vehicle inside a closing
  zone must keep moving to the exit (the shield never lets it stop there unless R1 or R6 forces it).
- R6 crew: never closer than R_crew,stop = stopping distance + 10 m to a crew member while moving; within 50 m, at most
  1 km/h.
- R7 comms loss: no new reservations (the caller's view holds only confirmed entries); held ones stay valid.
- R10 pads, chargers, junction tiles: slots, at most `slots` holders at once.
- R4 / R8 (priority) order the requests before they reach this function; they never make an unsafe action safe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np

# ------------------------------------------------------------------------------------------------ constants
G_MOON = 1.62          # m/s2, S (lunar surface gravity)
G_MARS = 3.71          # m/s2, S (B-82)
RHO_S = 1.0            # s, response time; A (RSS default; sweep 0.5, 1, 3; traffic_and_safety.md R1)
A_ACC = 0.2            # m/s2, follower's max acceleration during the response time; A (R1)
B_MIN_FLAT = 0.5       # m/s2, guaranteed service braking on the flat; A (R1), reduced by g sin(theta) downhill
B_MAX = 0.8            # m/s2, leader's max braking (worst case for the follower); A (R1)
D0_M = 5.0             # m, static margin; A (R1)
MU_DEFAULT = 0.45      # regolith braking friction; A, Low confidence (sweep 0.3, 0.45, 0.6; traffic_and_safety.md §5)
STEEP_DEG = 10.0       # deg; downhill steeper than this is capped at a 15 m stop; A (R2)
STEEP_STOP_M = 15.0    # m; A (R2)
R_CREW_SLOW_M = 50.0   # m; A (R6)
R_CREW_MARGIN_M = 10.0  # m, R_crew,stop = stopping distance + this; A (R6)
V_CREW_MS = 1.0 / 3.6  # m/s (1 km/h); A (R6; ISO 3691-4 0.3 m/s analogue, Low)
MOVING_MS = 0.05       # m/s; below this a vehicle counts as stopped (metrics only); A


# ------------------------------------------------------------------------------------------------ kinematics
def b_guaranteed(theta_deg, mu=MU_DEFAULT, g=G_MOON):
    """Guaranteed deceleration (m/s2): service braking, friction-limited, minus the downhill component. theta > 0 is
    downhill. Can be <= 0 (the vehicle cannot stop on that slope)."""
    th = np.radians(theta_deg)
    return np.minimum(B_MIN_FLAT, mu * g * np.cos(th)) - g * np.sin(th)


def stop_distance(v, b):
    """v^2 / 2b; inf where b <= 0 and v > 0."""
    v = np.asarray(v, float)
    b = np.asarray(b, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        d = np.where(b > 0, v * v / (2.0 * np.where(b > 0, b, 1.0)), np.where(v > 0, np.inf, 0.0))
    return d


def rss_dmin(v_rear, v_front, b_rear, rho=RHO_S, a_acc=A_ACC, b_front=B_MAX, d0=D0_M):
    """RSS safe longitudinal gap (bumper to bumper, m) for the same direction, plus the static margin."""
    v_rear = np.asarray(v_rear, float)
    v_front = np.asarray(v_front, float)
    vr = v_rear + rho * a_acc
    d = v_rear * rho + 0.5 * a_acc * rho * rho + stop_distance(vr, b_rear) - v_front * v_front / (2.0 * b_front)
    return np.maximum(d, 0.0) + d0


def v_max_r2(theta_deg, mu, sight_m, v_class, rho=RHO_S, g=G_MOON):
    """R2: the highest admissible speed (m/s)."""
    b = b_guaranteed(theta_deg, mu, g)
    s = np.maximum(np.asarray(sight_m, float), 0.0)
    bp = np.where(b > 0, b, 1.0)
    v_sight = np.where(b > 0, bp * (-rho + np.sqrt(rho * rho + 2.0 * s / bp)), 0.0)
    v_steep = np.where(np.asarray(theta_deg) > STEEP_DEG, np.sqrt(2.0 * bp * STEEP_STOP_M), np.inf)
    return np.where(b > 0, np.minimum(np.minimum(v_class, v_sight), v_steep), 0.0)


def r_crew_stop(v, b):
    """R6: the keep-out radius around crew for a vehicle at speed v (m)."""
    return stop_distance(v, b) + R_CREW_MARGIN_M


# ------------------------------------------------------------------------------------------------ reservations
def r3_pair_conflict(d_existing, d_request, branched):
    """R3 on one overlapping pair of reservations: opposite directions conflict; on a branched segment any overlap does."""
    return (np.asarray(d_existing) != np.asarray(d_request)) | np.asarray(branched, bool)


@dataclass
class Reserve:
    resource: Any
    t_in: float
    t_out: float
    vid: int
    owner: str
    d: int = 0                      # direction along the resource's axis (+1 / -1); 0 for slots
    kind: str = "segment"           # "segment" (R3) or "slots" (R10: pad apron, charger, junction tile)
    branched: bool = False
    slots: int = 1
    mine_only: bool = False         # the caller's view: only this owner's entries (uncoordinated, or R7 unlinked)


@dataclass
class ReserveVerdict:
    ok: bool
    conflicts: List[tuple] = field(default_factory=list)
    until: float = -np.inf          # when the last conflicting holder frees the resource (hold before the entry)


@dataclass
class Move:
    """Arrays (any common shape), one element per vehicle. Distances in m, speeds m/s, accelerations m/s2."""
    v: Any
    a_prop: Any
    dt: float
    theta: Any                       # slope along travel, deg (downhill > 0)
    mu: Any
    v_class: Any
    sight: Any                       # clear sight distance ahead (occluders already applied)
    gap_lead: Any                    # bumper gap to the leader on the same lane (inf if none)
    v_lead: Any
    d_stop: Any                      # distance to the next line it may not cross (R3 / R5 / R10 entry without a
                                     # confirmed reservation, closed zone); inf if none
    d_crew: Any                      # distance to the nearest crew member ahead or beside the path (inf if none)
    must_exit: Any = False           # inside a closing landing zone (R5): keep moving to the exit
    a_max: Any = 0.2                 # the vehicle's acceleration capability (m/s2)
    g: float = G_MOON


@dataclass
class MoveVerdict:
    a: np.ndarray
    modified: np.ndarray
    no_safe_action: np.ndarray
    rule: np.ndarray                 # first violated rule of the proposal: 0 none, 1 R1, 2 R2, 3 stop line, 6 R6, 5 R5


def _reserve(state, p: Reserve) -> ReserveVerdict:
    entries = state.get(p.resource, ()) if hasattr(state, "get") else state
    if p.kind == "slots":
        occ = [(a, b, o, vid) for (a, b, _, o, vid) in entries
               if vid != p.vid and a < p.t_out and b > p.t_in and (not p.mine_only or o == p.owner)]
        if len(occ) >= int(p.slots):
            return ReserveVerdict(False, occ, min(x[1] for x in occ))
        return ReserveVerdict(True)
    out = []
    for (a, b, dd, owner, vid) in entries:
        if vid == p.vid or b <= p.t_in or a >= p.t_out:
            continue
        if p.mine_only and owner != p.owner:
            continue
        if r3_pair_conflict(dd, p.d, p.branched):
            out.append((a, b, dd, owner, vid))
    if out:
        return ReserveVerdict(False, out, max(x[1] for x in out))
    return ReserveVerdict(True)


def _after_step(v, a, dt):
    """Speed after the step and distance covered (no reversing: a vehicle that would stop mid-step stays stopped)."""
    v1 = np.maximum(v + a * dt, 0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        t_stop = np.where(a < 0, np.minimum(dt, v / np.where(a < 0, -a, 1.0)), dt)
    x1 = v * t_stop + 0.5 * a * t_stop * t_stop
    return v1, np.maximum(x1, 0.0)


def _ok(m: Move, a, b, vmax):
    """Rule check of acceleration a: returns (ok mask, first violated rule code)."""
    v1, x1 = _after_step(m.v, a, m.dt)
    rule = np.zeros(np.shape(v1), int)
    # R2: admissible speed after the step
    r2 = v1 <= vmax + 1e-9
    # R1: gap after the step against the leader braking at B_MAX throughout, unless this is the proper response
    vl1, xl1 = _after_step(m.v_lead, -B_MAX, m.dt)
    gap1 = m.gap_lead - x1 + xl1
    r1 = (gap1 >= rss_dmin(v1, vl1, b)) | (a <= -b + 1e-9)
    r1 &= gap1 > 0
    # stop line (R3 / R5 / R10 without a confirmed reservation): still able to stop before it
    rs = x1 + stop_distance(v1, b) <= m.d_stop + 1e-9
    # R6: crew keep-out while moving, and the crew slow zone
    dc1 = m.d_crew - x1
    r6 = ((dc1 >= r_crew_stop(v1, b)) | (v1 <= MOVING_MS)) & ((m.d_crew > R_CREW_SLOW_M) | (v1 <= V_CREW_MS + 1e-9))
    ok = r2 & r1 & rs & r6
    rule = np.where(~r6, 6, np.where(~r1, 1, np.where(~rs, 3, np.where(~r2, 2, 0))))
    return ok, rule


def _move(state, m: Move) -> MoveVerdict:
    b = b_guaranteed(m.theta, m.mu, m.g)
    vmax = v_max_r2(m.theta, m.mu, m.sight, m.v_class, g=m.g)
    a_prop = np.minimum(np.asarray(m.a_prop, float), m.a_max)
    must = np.broadcast_to(np.asarray(m.must_exit, bool), np.shape(a_prop))
    # R5: inside a closing zone the planner may not choose to slow down (the exit candidate is full acceleration)
    a_first = np.where(must, np.maximum(a_prop, np.minimum(m.a_max, (vmax - m.v) / m.dt)), a_prop)
    ok0, rule0 = _ok(m, a_first, b, vmax)
    rule0 = np.where(must & (a_prop < a_first), np.where(rule0 == 0, 5, rule0), rule0)
    a = np.where(ok0, a_first, np.nan)
    for cand in (np.minimum(a_first, 0.0), np.maximum(-b, -B_MAX * 4)):      # no acceleration, then full braking
        okc, _ = _ok(m, cand, b, vmax)
        a = np.where(np.isnan(a) & okc, cand, a)
    none = np.isnan(a)
    a = np.where(none, np.maximum(-b, -B_MAX * 4), a)
    return MoveVerdict(a=a, modified=(a != a_prop), no_safe_action=none, rule=rule0)


def safety_check(state, proposal):
    """The safety program: Reserve -> ReserveVerdict (state: the visible reservation entries of that resource, or a
    dict resource -> entries); Move -> MoveVerdict (state unused: the Move carries the vehicle's situation)."""
    if isinstance(proposal, Reserve):
        return _reserve(state, proposal)
    if isinstance(proposal, Move):
        return _move(state, proposal)
    raise TypeError(f"unknown proposal {type(proposal).__name__}")
