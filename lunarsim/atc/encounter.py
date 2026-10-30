"""Encounter simulator (B-78, paper P2): continuous 2D kinematics at 10 Hz, many encounters at once (numpy, vectorised
over encounters), every vehicle's every step through `safety_check` (lunarsim/atc/safety.py).

An encounter is a few vehicles on a small local road geometry. Each vehicle follows a fixed path (a polyline; lanes,
single-lane segments, bays, junctions and turns are paths) with arc position s (front bumper) and speed v. Each step:
1. messages: requests, grants and releases arrive (latency MSG_LAT_S, Bernoulli loss p, none while the vehicle's link is
   down); the base computer grants a vehicle's next resource group (a single-lane segment, junction tiles, apron slots)
   in priority order (R4 / R8) when no other holder conflicts (safety.r3_pair_conflict, slot counts) and the exit node
   has a free slot (R3 exit rule); a grant that is lost is resent on the next request;
2. each vehicle's planner proposes an acceleration (nominal: cruise and stop for known lines; random fuzzer; adversarial:
   always full acceleration); the safety program accepts it or substitutes the fallback;
3. kinematics; exact closest approach between the two step ends of every vehicle pair (two discs per vehicle,
   positions linear within the step) and to every crew member;
4. hard violations (§D): contact (separation < 0); same-lane bumper gap below the static margin D0; a vehicle inside a
   closed landing zone; a moving vehicle closer to crew than R_crew,stop; two opposite-direction vehicles inside one
   single-lane segment, a vehicle inside a reserved resource without the table's grant, or more vehicles in a slot
   resource than slots. Near misses: same-lane gap < 2 d_min, time to collision < 10 s, crew closer than
   2 R_crew,stop, zone exit with less than 5 min to spare. Also: interventions, delay against free flow, deadlock
   (not finished and everyone stopped for DEADLOCK_S at the end), R1 breaches (gap below d_min while not braking).

Limits (stated in the report): commands act without actuation delay (rho enters only the margins); a vehicle is a pair
of discs; positions are interpolated linearly within a 0.1 s step for the closest approach; the learned bid policy has
no motion output, so the planners here are nominal, random and adversarial.
"""
from __future__ import annotations

import copy
import math
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from . import safety as S
from .safety import Move, safety_check

DT = 0.1                 # s, 10 Hz; spec (B-78)
VEH_L = 4.0              # m, vehicle length; A (LTV class, ~4 m)
VEH_W = 2.3              # m, width; A (same as WIDTH_SINGLE_M's vehicle width in tools/atc/roads.py)
LANE_W = 3.5             # m; A
MSG_LAT_S = 0.3          # s, one-way message latency incl. processing; A (UTM TCL4: 95 % <= 531 ms, S)
REQ_DIST_M = 80.0        # m, a vehicle requests its next resource group within this distance; A
REQ_RETRY_S = 2.0        # s, request resent if no grant arrived; A
DEADLOCK_S = 120.0       # s; A (shorter than the 10 min of §D because encounters are minutes long; stated)
CREW_R = 0.5             # m, crew member as a disc; A
WALK_MAX = 1.2           # m/s, fastest EVA walking speed, for a possible crew member behind an occluder; A
E_LAT_M = 0.3            # m, lateral deviation beyond which a vehicle is nonconforming (R9); A (R9's e_conf = 11 m is a
                         # position tolerance; lanes 3.5 m apart need a lateral one: PREREG change 6). Development
                         # baseline without this check: E_LAT_M = inf (results/E44_dev_r9.json)
R9_MARGIN_M = 0.5        # m, lateral clearance kept from an inflated volume; A
TTC_NEAR_S = 10.0        # s; §D
V_LTV = 10 / 3.6         # m/s; S (traffic_and_safety.md: LTV 10-15 km/h)
V_LTV_FAST = 15 / 3.6
V_HAUL = 4 / 3.6         # m/s; A (§B R2: HAUL 4 km/h)
A_MAX = 0.2              # m/s2 = safety.A_ACC; A
NOMINAL_DECEL = 0.3      # m/s2, comfortable braking of the nominal planner; A
T_LEAD_S = 1800.0        # s, closure notice lead before the window opens; A (R5 leaves it open; ill-posed point)
ZONE_MARGIN_S = 300.0    # s, filed exit must be this long before the window; A (§D near miss threshold 5 min)

TYPES = {
    1: "following, leader brakes at maximum (flat, 10/15/20 deg downhill)",
    2: "head-on on a single-lane segment (with/without a passing bay; a third vehicle queued behind each)",
    3: "overtaking on a two-lane stretch ending before a single-lane segment",
    4: "crossing and merging at a junction; four-way contention (tile granularity 1-4)",
    5: "cyclic wait on a ring of single-lane segments (3 or 4 vehicles, bays of 2 slots)",
    6: "landing closure: vehicle inside, filed route through, delay and wave-off",
    7: "crew crossing, emerging from occlusion, walking toward a stopped robot",
    8: "communication dropout mid-negotiation; 10-50 % message loss; partition",
    9: "nonconforming vehicle: slip, drift, dead stop inside a single-lane segment",
    10: "multi-owner speed mix (HAUL and LTV) with one adversarial planner",
    11: "pad apron contention at 2x, 4x, 8x the nominal fleet",
    12: "planner fuzzing: random and adversarial proposals on a mixed geometry",
}


# ------------------------------------------------------------------------------------------------ geometry
@dataclass
class Path:
    pts: np.ndarray                       # (P, 2) polyline

    def cum(self):
        return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(self.pts, axis=0).T))])


def lane_y(direction):
    """Right-hand traffic: +x travels at y = -LANE_W/2, -x at +LANE_W/2."""
    return -LANE_W / 2 if direction > 0 else LANE_W / 2


@dataclass
class Spec:
    """One encounter, as built by a type builder (scalars and lists; batched later)."""
    paths: List[np.ndarray]
    v_class: List[float]
    v0: List[float]
    s0: List[float]
    planner: List[int]                    # 0 nominal, 1 random, 2 adversarial
    theta: float = 0.0                    # slope along travel (downhill +), deg; same for all (local geometry)
    mu: float = S.MU_DEFAULT
    groups: List[List[dict]] = field(default_factory=list)   # per vehicle: [{res: [ids], dirs: [..], s_in, s_out, exit}]
    res_kind: List[int] = field(default_factory=list)        # 0 segment (R3), 1 slots (R10)
    res_slots: List[int] = field(default_factory=list)
    res_branched: List[bool] = field(default_factory=list)
    nodes: List[dict] = field(default_factory=list)           # [{cap, iv: {vehicle: (s_in, s_out)}}]
    loss: float = 0.0
    link_down: List[tuple] = field(default_factory=list)      # per vehicle (t0, t1) or ()
    zone: Optional[dict] = None           # {c: (x,y), r, events: [(t_close, t_reopen)], chord: per vehicle (s_in, s_out)}
    crew: List[dict] = field(default_factory=list)            # [{p0, vel, t_emerge, t_stop, occluder: per veh s or inf}]
    lead_brake: Optional[tuple] = None    # (vehicle, t): that vehicle brakes at maximum from t to a stop and stays
    fault_stop: Optional[tuple] = None    # (vehicle, t): stops dead at t (fault) and stays
    slip: Optional[tuple] = None          # (vehicle, factor): positive acceleration scaled down (late)
    drift: Optional[tuple] = None         # (vehicle, m/s): lateral drift off its path
    dwell: Optional[dict] = None          # {vehicle: (s_stop, seconds)}: stops there for that long (loading)
    priority: List[float] = field(default_factory=list)       # lower = earlier (R4/R8 key), per vehicle
    t_max: float = 600.0
    params: dict = field(default_factory=dict)
    weight: float = 1.0                   # importance-sampling weight p/q
    merges: List[tuple] = field(default_factory=list)         # [(vehicle, s_merge_start, (x, y) merge end)]
    occluders: List[tuple] = field(default_factory=list)      # [(x, y, t_until)]: a hidden crew member may be there
    exit_keep_free: bool = False          # R3 variant: a hop that does not end the trip needs 2 free slots in its bay
    stop_is_goal: bool = False            # the encounter is complete when every vehicle has stopped (type 1)
    request_rule: bool = False            # variant (PREREG change 9): no request while a hold point (a closed or
                                          # closing zone) lies before the resource


def _pad(lst, n, val):
    return list(lst) + [val] * (n - len(lst))


class Batch:
    """N encounters of one type, padded to common sizes."""

    def __init__(self, specs: List[Spec], g=S.G_MOON):
        self.specs = specs
        N = self.N = len(specs)
        V = self.V = max(len(s.paths) for s in specs)
        P = max(max(len(p) for p in s.paths) for s in specs)
        self.g = g
        self.real = np.zeros((N, V), bool)
        self.pts = np.zeros((N, V, P, 2))
        self.cum = np.full((N, V, P), np.inf)
        self.length = np.zeros((N, V))
        for n, s in enumerate(specs):
            for i, p in enumerate(s.paths):
                p = np.asarray(p, float)
                c = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(p, axis=0).T))])
                self.pts[n, i, :len(p)] = p
                self.pts[n, i, len(p):] = p[-1]
                self.cum[n, i, :len(p)] = c
                self.cum[n, i, len(p):] = c[-1] + 1e9
                self.length[n, i] = c[-1]
                self.real[n, i] = True
        # piece directions; zero-length (padding) pieces carry the last real direction forward
        seg = np.diff(self.pts, axis=2)
        ln = np.hypot(seg[..., 0], seg[..., 1])
        u = np.where(ln[..., None] > 1e-9, seg / np.where(ln[..., None] > 1e-9, ln[..., None], 1.0), np.nan)
        u[..., 0, :] = np.where(np.isnan(u[..., 0, :]), np.array([1.0, 0.0]), u[..., 0, :])
        for k in range(1, u.shape[2]):
            u[..., k, :] = np.where(np.isnan(u[..., k, :]), u[..., k - 1, :], u[..., k, :])
        self.udir = u                                                      # (N, V, P-1, 2)
        # vehicles on the very same path (queued followers): one id per distinct polyline within an encounter
        self.path_id = np.full((N, V), -1, int)
        for n, s in enumerate(specs):
            ids = {}
            for i, pth in enumerate(s.paths):
                key = tuple(np.round(np.asarray(pth, float), 3).ravel().tolist())
                self.path_id[n, i] = ids.setdefault(key, len(ids))
        f = lambda name, default=0.0: np.array([_pad(getattr(s, name), V, default) for s in specs], float)
        self.v_class = f("v_class", 1.0)
        self.v = f("v0")
        self.s = f("s0")
        self.planner = f("planner").astype(int)
        self.theta = np.array([s.theta for s in specs])[:, None] * np.ones((1, V))
        self.mu = np.array([s.mu for s in specs])[:, None] * np.ones((1, V))
        self.prio = np.array([_pad(s.priority or list(range(len(s.paths))), V, 1e9) for s in specs], float)
        self.t_max = np.array([s.t_max for s in specs])
        # resources and groups
        R = self.R = max(1, max(len(s.res_kind) for s in specs))
        G = self.G = max(1, max((max((len(g) for g in s.groups), default=0) for s in specs)))
        T = self.T = max(1, max((max((len(x["res"]) for g in s.groups for x in g), default=1) for s in specs)))
        self.res_kind = np.array([_pad(s.res_kind, R, 0) for s in specs], int)
        self.res_slots = np.array([_pad(s.res_slots or [1] * len(s.res_kind), R, 1) for s in specs], int)
        self.res_branched = np.array([_pad(s.res_branched or [False] * len(s.res_kind), R, False) for s in specs], bool)
        self.g_res = np.full((N, V, G, T), -1, int)
        self.g_dir = np.zeros((N, V, G, T), int)
        self.g_in = np.full((N, V, G), np.inf)
        self.g_out = np.full((N, V, G), np.inf)
        self.g_exit = np.full((N, V, G), -1, int)
        self.n_groups = np.zeros((N, V), int)
        K = self.K = max(1, max(len(s.nodes) for s in specs))
        self.node_cap = np.full((N, K), 10 ** 6, int)
        self.node_in = np.full((N, V, K), np.inf)
        self.node_out = np.full((N, V, K), -np.inf)
        for n, s in enumerate(specs):
            for i, gl in enumerate(s.groups):
                self.n_groups[n, i] = len(gl)
                for gi, x in enumerate(gl):
                    self.g_res[n, i, gi, :len(x["res"])] = x["res"]
                    self.g_dir[n, i, gi, :len(x["dirs"])] = x["dirs"]
                    self.g_in[n, i, gi] = x["s_in"]
                    self.g_out[n, i, gi] = x["s_out"]
                    self.g_exit[n, i, gi] = x.get("exit", -1)
            for k, nd in enumerate(s.nodes):
                self.node_cap[n, k] = nd["cap"]
                for i, (a, b) in nd["iv"].items():
                    self.node_in[n, i, k] = a
                    self.node_out[n, i, k] = b
        # messages and links
        self.loss = np.array([s.loss for s in specs])
        self.keep_free = np.array([s.exit_keep_free for s in specs])
        self.stop_goal = np.array([s.stop_is_goal for s in specs])
        self.req_rule = np.array([s.request_rule for s in specs])
        self.down0 = np.full((N, V), np.inf)
        self.down1 = np.full((N, V), -np.inf)
        for n, s in enumerate(specs):
            for i, iv in enumerate(s.link_down):
                if iv:
                    self.down0[n, i], self.down1[n, i] = iv
        # zone
        self.has_zone = np.array([s.zone is not None for s in specs])
        Z = max(1, max((len(s.zone["events"]) for s in specs if s.zone), default=1))
        self.z_close = np.full((N, Z), np.inf)
        self.z_open = np.full((N, Z), np.inf)
        self.z_cancel = np.full((N, Z), np.inf)
        self.z_in = np.full((N, V), np.inf)
        self.z_out = np.full((N, V), np.inf)
        for n, s in enumerate(specs):
            if s.zone:
                for e, ev in enumerate(s.zone["events"]):
                    self.z_close[n, e], self.z_open[n, e] = ev[0], ev[1]
                    if len(ev) > 2:
                        self.z_cancel[n, e] = ev[2]
                for i, (a, b) in enumerate(s.zone["chord"]):
                    self.z_in[n, i], self.z_out[n, i] = a, b
        # crew
        C = self.C = max(1, max(len(s.crew) for s in specs))
        self.c_p0 = np.full((N, C, 2), 1e7)
        self.c_vel = np.zeros((N, C, 2))
        self.c_t0 = np.full((N, C), np.inf)
        self.c_t1 = np.full((N, C), np.inf)
        self.c_vis = np.full((N, C), np.inf)
        self.occl = np.full((N, V), np.inf)
        for n, s in enumerate(specs):
            for c, cr in enumerate(s.crew):
                self.c_p0[n, c] = cr["p0"]
                self.c_vel[n, c] = cr["vel"]
                self.c_t0[n, c] = cr["t_emerge"]
                self.c_t1[n, c] = cr.get("t_stop", np.inf)
                self.c_vis[n, c] = cr.get("t_visible", cr["t_emerge"])
                for i, o in enumerate(cr.get("occluder", [])):
                    self.occl[n, i] = min(self.occl[n, i], o)
        O = max(1, max(len(s.occluders) for s in specs))
        self.o_pt = np.full((N, O, 2), 1e7)
        self.o_until = np.full((N, O), -np.inf)
        self.merge_v = np.full(N, -1, int)
        self.merge_s = np.full(N, np.inf)
        self.merge_pt = np.full((N, 2), 1e7)
        for n, s in enumerate(specs):
            for o, (x, y, tu) in enumerate(s.occluders):
                self.o_pt[n, o] = (x, y)
                self.o_until[n, o] = tu
            if s.merges:
                self.merge_v[n], self.merge_s[n], self.merge_pt[n] = s.merges[0][0], s.merges[0][1], s.merges[0][2]
        # exit-node entry arc per group, and resource membership per group
        ge = np.maximum(self.g_exit, 0)
        self.g_exit_in = np.where(self.g_exit >= 0, np.take_along_axis(self.node_in, ge, 2), np.inf)
        oh = (self.g_res[..., None] == np.arange(R)) & (self.g_res[..., None] >= 0)          # (N, V, G, T, R)
        self.g_onehot = oh.any(3)                                                           # (N, V, G, R)
        self.g_resdir = (oh * self.g_dir[..., None]).sum(3)                                 # (N, V, G, R)
        # events
        self.lead_v = np.full(N, -1, int); self.lead_t = np.full(N, np.inf)
        self.fault_v = np.full(N, -1, int); self.fault_t = np.full(N, np.inf)
        self.slip_v = np.full(N, -1, int); self.slip_f = np.ones(N)
        self.drift_v = np.full(N, -1, int); self.drift_r = np.zeros(N)
        self.dwell_s = np.full((N, V), np.inf); self.dwell_d = np.zeros((N, V))
        for n, s in enumerate(specs):
            if s.lead_brake: self.lead_v[n], self.lead_t[n] = s.lead_brake
            if s.fault_stop: self.fault_v[n], self.fault_t[n] = s.fault_stop
            if s.slip: self.slip_v[n], self.slip_f[n] = s.slip
            if s.drift: self.drift_v[n], self.drift_r[n] = s.drift
            for i, (a, b) in (s.dwell or {}).items():
                self.dwell_s[n, i], self.dwell_d[n, i] = a, b

    # -------------------------------------------------------------------------------------------- geometry ops
    def pos(self, s):
        """Front-bumper position and unit heading for arc positions s (N, V)."""
        k = np.clip((self.cum[..., 1:] <= s[..., None]).sum(-1), 0, self.cum.shape[-1] - 2)
        idx = k[..., None, None]
        a = np.take_along_axis(self.pts, idx.repeat(2, -1), axis=2)[..., 0, :]
        c0 = np.take_along_axis(self.cum, k[..., None], axis=2)[..., 0]
        u = np.take_along_axis(self.udir, idx.repeat(2, -1), axis=2)[..., 0, :]
        p = a + u * np.clip(s - c0, 0, None)[..., None]
        return p, u

    def road_key(self, s):
        """Road identity at the front: the line of the current path piece (heading angle, signed offset from the
        origin). Two vehicles are on the same road, in the same direction, when both agree (PREREG change 9)."""
        k = np.clip((self.cum[..., 1:] <= s[..., None]).sum(-1), 0, self.cum.shape[-1] - 2)
        idx = k[..., None, None]
        a = np.take_along_axis(self.pts, idx.repeat(2, -1), axis=2)[..., 0, :]
        u = np.take_along_axis(self.udir, idx.repeat(2, -1), axis=2)[..., 0, :]
        return np.arctan2(u[..., 1], u[..., 0]), u[..., 0] * a[..., 1] - u[..., 1] * a[..., 0]


def _body(b, s, lat):
    """Body centre and the two disc centres, placed on the path behind the front (at s - L/2 and s - L/2 +- off), with
    the vehicle's lateral offset: at a corner the body trails along the path instead of swinging off it."""
    off = (VEH_L - VEH_W) / 2
    out = []
    for d in (VEH_L / 2, VEH_L / 2 - off, VEH_L / 2 + off):
        q, uq = b.pos(s - d)
        out.append(q + np.stack([-uq[..., 1], uq[..., 0]], -1) * lat[..., None])
    return out[0], out[1], out[2]


def _closest(p0, p1, q0, q1):
    """Minimum distance between two points moving linearly from p0->p1 and q0->q1 over the step (arrays ..., 2)."""
    d0 = p0 - q0
    dv = (p1 - p0) - (q1 - q0)
    a = (dv * dv).sum(-1)
    t = np.where(a > 1e-12, np.clip(-(d0 * dv).sum(-1) / np.where(a > 1e-12, a, 1.0), 0.0, 1.0), 0.0)
    d = d0 + dv * t[..., None]
    return np.hypot(d[..., 0], d[..., 1])


@dataclass
class Outcome:
    min_sep: np.ndarray
    min_gap_same: np.ndarray
    viol_contact: np.ndarray
    viol_gap: np.ndarray
    viol_zone: np.ndarray
    viol_crew: np.ndarray
    viol_r3: np.ndarray
    viol_slots: np.ndarray
    r1_breach: np.ndarray
    near_gap: np.ndarray
    near_ttc: np.ndarray
    near_crew: np.ndarray
    near_zone: np.ndarray
    min_crew: np.ndarray
    interventions: np.ndarray
    proposals: np.ndarray
    no_safe: np.ndarray
    deadlock: np.ndarray
    blocked_by_fault: np.ndarray
    finished: np.ndarray
    delay_s: np.ndarray
    t_end: np.ndarray
    steps: np.ndarray


def run_batch(b: Batch, rng: np.random.Generator, record: Optional[List[int]] = None, shield: bool = True) -> tuple:
    """Simulate a batch; returns (Outcome, traces for the encounters listed in `record`)."""
    N, V, R, G, T, K, C = b.N, b.V, b.R, b.G, b.T, b.K, b.C
    real = b.real
    s, v = b.s.copy(), b.v.copy()
    t = 0.0
    # reservation state
    hold_t = np.zeros((N, V, R), bool)       # table side
    hold_dir = np.zeros((N, V, R), int)
    held_v = np.zeros((N, V, G), bool)       # vehicle side (confirmed grants)
    next_g = np.zeros((N, V), int)
    req_arr = np.full((N, V), np.inf)        # when the pending request reaches the base
    req_g = np.full((N, V), -1, int)
    req_sent = np.full((N, V), -np.inf)
    base_g = np.full((N, V), -1, int)          # the base's queue: the group each vehicle has asked for (or -1)
    base_filed = np.full((N, V), np.inf)
    base_resend = np.zeros((N, V), bool)
    grant_arr = np.full((N, V), np.inf)
    grant_g = np.full((N, V), -1, int)
    rel_arr = np.full((N, V, G), np.inf)     # release of a group reaches the base
    granted_g = np.zeros((N, V, G), bool)    # table granted (exit-node slot reserved until arrival)
    done = ~real.copy()
    stopped_since = np.zeros((N, V))
    dwell_until = np.full((N, V), -np.inf)
    dwell_used = np.zeros((N, V), bool)
    faulted = np.zeros((N, V), bool)
    lat = np.zeros((N, V))                   # lateral drift offset
    out = {k: np.zeros(N) for k in ("viol_contact", "viol_gap", "viol_zone", "viol_crew", "viol_r3", "viol_slots",
                                     "r1_breach", "near_gap", "near_ttc", "near_crew", "near_zone", "interventions",
                                     "proposals", "no_safe")}
    min_sep = np.full(N, np.inf)
    min_gap = np.full(N, np.inf)
    min_crew = np.full(N, np.inf)
    t_done = np.full((N, V), np.inf)
    t_free = np.where(real, (b.length - b.s) / np.maximum(b.v_class, 1e-3), 0.0)
    active = np.ones(N, bool)
    t_end = np.zeros(N)
    steps = np.zeros(N)
    traces = {n: [] for n in (record or [])}
    vi = np.arange(V)
    off = (VEH_L - VEH_W) / 2                # disc centres at +-off from the body centre
    dl_flag = np.zeros(N, bool)
    bf_flag = np.zeros(N, bool)
    last_change = np.zeros(N)                # last movement, grant, release or finish in the encounter
    zone_hold_before = np.zeros((N, V), bool)  # previous step: a no-entry zone boundary lies before the next group

    def link_up(tt):
        return ~((b.down0 <= tt) & (tt < b.down1))

    # compaction: once half the batch has ended, finished encounters leave the arrays (results kept in full-size copies)
    N0 = N
    idx_map = np.arange(N)
    full = {"out": {k: x.copy() for k, x in out.items()}, "min_sep": min_sep.copy(), "min_gap": min_gap.copy(),
            "min_crew": min_crew.copy(), "dl": dl_flag.copy(), "bf": bf_flag.copy(), "done": done.copy(),
            "t_done": t_done.copy(), "t_free": t_free.copy(), "real": real.copy(), "faulted": faulted.copy(),
            "t_end": t_end.copy(), "steps": steps.copy()}

    def _store(rows):
        g_ = idx_map[rows]
        for k_, x_ in out.items():
            full["out"][k_][g_] = x_[rows]
        for k_, x_ in (("min_sep", min_sep), ("min_gap", min_gap), ("min_crew", min_crew), ("dl", dl_flag),
                       ("bf", bf_flag), ("done", done), ("t_done", t_done), ("t_free", t_free), ("real", real),
                       ("faulted", faulted), ("t_end", t_end), ("steps", steps)):
            full[k_][g_] = x_[rows]

    while active.any():
        if not record and N > 64 and active.sum() < 0.5 * N:
            keep = np.flatnonzero(active)
            _store(np.flatnonzero(~active))
            nb = copy.copy(b)
            for k_, x_ in vars(b).items():
                if isinstance(x_, np.ndarray) and x_.ndim >= 1 and x_.shape[0] == N:
                    setattr(nb, k_, x_[keep])
            nb.N = len(keep)
            nb.specs = [b.specs[q] for q in keep]
            b = nb
            (s, v, hold_t, hold_dir, held_v, next_g, req_arr, req_g, req_sent, base_g, base_filed, base_resend,
             grant_arr, grant_g, rel_arr, granted_g, done, stopped_since, dwell_until, dwell_used, faulted, lat,
             min_sep, min_gap, min_crew, t_done, t_free, active, t_end, steps, dl_flag, bf_flag, last_change,
             zone_hold_before) = (
                x_[keep] for x_ in (s, v, hold_t, hold_dir, held_v, next_g, req_arr, req_g, req_sent, base_g,
                                    base_filed, base_resend, grant_arr, grant_g, rel_arr, granted_g, done,
                                    stopped_since, dwell_until, dwell_used, faulted, lat, min_sep, min_gap, min_crew,
                                    t_done, t_free, active, t_end, steps, dl_flag, bf_flag, last_change,
                                    zone_hold_before))
            out = {k_: x_[keep] for k_, x_ in out.items()}
            idx_map = idx_map[keep]
            N = len(keep)
            real = b.real
        t += DT
        up = link_up(t)
        # ---------------------------------------------------------------- 1. messages
        # vehicle side: request the next group when near and nothing pending
        # the first group ahead that the vehicle does not hold yet (requests and stop lines look past held groups)
        gidx = np.arange(G)[None, None, :]
        unheld = (gidx >= next_g[..., None]) & (gidx < b.n_groups[..., None]) & ~held_v
        has_next = unheld.any(-1)
        gi = np.where(has_next, unheld.argmax(-1), np.minimum(next_g, G - 1))
        g_in_next = np.take_along_axis(b.g_in, gi[..., None], 2)[..., 0]
        held_next = np.take_along_axis(held_v, gi[..., None], 2)[..., 0]
        want = has_next & ~held_next & ~done & (g_in_next - s <= REQ_DIST_M) & active[:, None] & ~faulted
        want &= ~(b.req_rule[:, None] & zone_hold_before)
        send = want & ((req_g != gi) | (t - req_sent >= REQ_RETRY_S)) & up
        lost = rng.random((N, V)) < b.loss[:, None]
        req_g = np.where(send, gi, req_g)
        req_sent = np.where(send, t, req_sent)
        req_arr = np.where(send, np.where(lost, np.inf, t + MSG_LAT_S), req_arr)
        # base: a request that arrives joins the queue (kept until granted; a lost grant is resent when the vehicle
        # asks again); every step the queue is served in order of first filing, then nearer the entry, then R4 key
        newly = req_arr <= t + 1e-9
        if newly.any():
            changed = newly & (base_g != req_g)
            base_filed = np.where(changed, t, base_filed)
            base_g = np.where(newly, req_g, base_g)
            base_resend = base_resend | newly
            req_arr = np.where(newly, np.inf, req_arr)
        arrived = (base_g >= 0) & ~done
        if arrived.any():
            # exit-node occupancy: vehicles physically inside a node + granted, not yet arrived
            in_node = (b.node_in <= s[..., None]) & (s[..., None] - VEH_L < b.node_out) & ~done[..., None]
            occ = in_node.sum(1)                                   # (N, K): physically inside
            pend = granted_g & (b.g_exit >= 0) & (s[..., None] < b.g_exit_in)              # granted, not yet arrived
            if pend.any():
                np.add.at(occ, (np.nonzero(pend)[0], b.g_exit[pend]), 1)
            # order: nearer its entry first (queue order on an approach; R4 'earlier filed' refined: a grant to a
            # vehicle queued behind another that is waiting for the same resource would deadlock), then the R4 key
            dist_in = np.where(arrived, np.round(np.take_along_axis(b.g_in, np.maximum(base_g, 0)[..., None], 2)[..., 0]
                                                 - s, 1), np.inf)
            order = np.lexsort((b.prio, dist_in, np.where(arrived, base_filed, np.inf)), axis=1)
            for i in order.T:                                       # vehicle index per rank, vectorised over N
                n_ok = arrived[np.arange(N), i]
                if not n_ok.any():
                    continue
                g = base_g[np.arange(N), i]
                gq = np.maximum(g, 0)
                rs = b.g_res[np.arange(N), i, gq]                  # (N, T)
                ds = b.g_dir[np.arange(N), i, gq]
                ok = n_ok.copy()
                already = granted_g[np.arange(N), i, gq]
                for tt in range(T):
                    r = rs[:, tt]
                    valid = r >= 0
                    rr = np.maximum(r, 0)
                    others = hold_t[np.arange(N), :, rr].copy()    # (N, V)
                    others[np.arange(N), i] = False
                    kind = b.res_kind[np.arange(N), rr]
                    od = hold_dir[np.arange(N), :, rr]
                    conf = (others & S.r3_pair_conflict(od, ds[:, tt][:, None], b.res_branched[np.arange(N), rr][:, None])).any(1)
                    slots_full = others.sum(1) >= b.res_slots[np.arange(N), rr]
                    bad = np.where(kind == 0, conf, slots_full)
                    ok &= ~(valid & bad)
                ex = b.g_exit[np.arange(N), i, gq]
                exq = np.maximum(ex, 0)
                i_in_ex = in_node[np.arange(N), i, exq]
                not_last = gq < b.n_groups[np.arange(N), i] - 1
                need = 1 + (b.keep_free & not_last).astype(int)
                ex_full = (occ[np.arange(N), exq] - i_in_ex) > b.node_cap[np.arange(N), exq] - need
                ok &= ~((ex >= 0) & ex_full & ~already)
                newg = ok & ~already
                if newg.any():
                    for tt in range(T):
                        r = rs[:, tt]
                        sel = newg & (r >= 0)
                        hold_t[np.arange(N)[sel], i[sel], r[sel]] = True
                        hold_dir[np.arange(N)[sel], i[sel], r[sel]] = ds[sel, tt]
                    granted_g[np.arange(N)[newg], i[newg], gq[newg]] = True
                    sel = newg & (ex >= 0)
                    occ[np.arange(N)[sel], ex[sel]] += 1
                # send a grant for a new grant, or again when the vehicle asked again for one it already has
                give = n_ok & (newg | (already & base_resend[np.arange(N), i]))
                lostg = rng.random(N) < b.loss
                gl = give & ~lostg & up[np.arange(N), i]
                grant_arr[np.arange(N)[gl], i[gl]] = t + MSG_LAT_S
                grant_g[np.arange(N)[gl], i[gl]] = g[gl]
                base_resend[np.arange(N)[n_ok], i[n_ok]] = False
                served = n_ok & (newg | already)                   # leaves the queue (asks again if the grant is lost)
                base_g[np.arange(N)[served], i[served]] = -1
        # vehicle side: grants arrive
        ga = (grant_arr <= t + 1e-9) & up
        last_change = np.where(ga.any(1), t, last_change)
        if ga.any():
            nn, ii = np.nonzero(ga)
            held_v[nn, ii, grant_g[nn, ii]] = True
            grant_arr[nn, ii] = np.inf
        # base: releases arrive
        ra = rel_arr <= t + 1e-9
        last_change = np.where(ra.any((1, 2)), t, last_change)
        if ra.any():
            nn, ii, gg = np.nonzero(ra)
            for tt in range(T):
                r = b.g_res[nn, ii, gg, tt]
                sel = r >= 0
                hold_t[nn[sel], ii[sel], r[sel]] = False
            granted_g[nn, ii, gg] = False
            rel_arr[nn, ii, gg] = np.inf
            base_g[nn, ii] = np.where(base_g[nn, ii] == gg, -1, base_g[nn, ii])
            # a resource also covered by another granted group of the same vehicle stays held (shared node tiles)
            keep = (granted_g[nn, ii, :, None] & b.g_onehot[nn, ii]).any(1)                  # (m, R)
            hold_t[nn, ii] |= keep
            kd = (granted_g[nn, ii, :, None] * b.g_resdir[nn, ii]).sum(1)
            hold_dir[nn, ii] = np.where(keep, np.sign(kd), hold_dir[nn, ii])
        # ---------------------------------------------------------------- 2. situation of each vehicle
        p, u = b.pos(s)
        nrm = np.stack([-u[..., 1], u[..., 0]], -1)
        p = p + nrm * lat[..., None]
        ctr, disc_f0, disc_b0 = _body(b, s, lat)          # the body follows the path behind the front (corners)
        # leader on the same lane: ahead within 30 deg heading and 1.5 m laterally
        dp = ctr[:, None, :, :] - ctr[:, :, None, :]               # (N, i, j, 2): j relative to i
        lon = (dp * u[:, :, None, :]).sum(-1)
        latd = np.abs((dp * nrm[:, :, None, :]).sum(-1))
        same = (u[:, :, None, :] * u[:, None, :, :]).sum(-1) > math.cos(math.radians(30))
        cand = same & (lon > 0) & (latd < 1.5) & ~done[:, None, :] & ~done[:, :, None]
        cand &= ~np.eye(V, dtype=bool)[None]
        gapm = np.where(cand, lon - VEH_L, np.inf)
        jl = gapm.argmin(-1)
        gap_lead = np.take_along_axis(gapm, jl[..., None], -1)[..., 0]
        v_lead = np.where(np.isfinite(gap_lead), np.take_along_axis(v, jl, 1), 0.0)
        # stop lines: next group not held (vehicle side); closed or closing zone not cleared for entry
        d_stop = np.where(has_next & ~held_next & ~done, g_in_next - s, np.inf)
        valid_e = t < b.z_cancel
        zc = np.where((b.z_close >= t - 1e-9) & valid_e, b.z_close, np.inf).min(1)  # next closure start
        cur_closed = ((b.z_close <= t) & (t < b.z_open) & valid_e).any(1)
        win_close = np.where(cur_closed, t, zc)                                   # closure in force or next one
        notice = b.has_zone & (win_close - t <= T_LEAD_S)
        inside = (s > b.z_in) & (s - VEH_L < b.z_out)
        before = s <= b.z_in
        eta_exit = t + (b.z_out + VEH_L - s) / np.maximum(b.v_class, 1e-3)
        no_entry = notice[:, None] & before & (eta_exit > win_close[:, None] - ZONE_MARGIN_S)
        zone_hold_before = no_entry & (b.z_in < g_in_next)
        d_stop = np.minimum(d_stop, np.where(no_entry, b.z_in - s, np.inf))
        must_exit = notice[:, None] & inside & ~done
        # merging back after overtaking: keep clear of a same-direction vehicle near the merge point (COLREGs 13)
        mrow = b.merge_v >= 0
        if mrow.any():
            mv_i = np.maximum(b.merge_v, 0)
            rel = ((b.merge_pt[:, None, :] - ctr) * u).sum(-1)                         # merge point ahead of j by rel
            latm = np.abs(((b.merge_pt[:, None, :] - ctr) * nrm).sum(-1))
            same_h = (u * u[np.arange(N), mv_i][:, None, :]).sum(-1) > 0.86
            near = (rel > -(VEH_L + S.D0_M)) & (rel < S.rss_dmin(v, 0.0, S.b_guaranteed(b.theta, b.mu, b.g)) + 2 * VEH_L)
            gate = (near & (latm < 2.0) & same_h & ~done & (vi[None] != mv_i[:, None])).any(1) & mrow
            sm = s[np.arange(N), mv_i]
            gate &= sm < b.merge_s
            d_stop[np.arange(N)[gate], mv_i[gate]] = np.minimum(d_stop[np.arange(N)[gate], mv_i[gate]],
                                                                (b.merge_s - sm)[gate])
        # R9 conformance (PREREG change 6): a vehicle more than E_LAT_M off its filed path is nonconforming; its occupied
        # volume is inflated by its deviation. Every vehicle tests its path ahead, as it is being driven, against the
        # inflated volumes of nonconforming neighbours, and a nonconforming vehicle tests its own track against
        # everyone; a conflict is a stop line before it (the approaching vehicle's speed counted while braking)
        dev = np.abs(lat)
        noncon = (dev > E_LAT_M) & ~done & real
        if noncon.any():
            bgr = np.maximum(S.b_guaranteed(b.theta, b.mu, b.g), 1e-3)
            infl = np.where(noncon, dev, 0.0)
            pair = (noncon[:, :, None] | noncon[:, None, :]) & ~np.eye(V, dtype=bool)[None]
            pair &= ~done[:, :, None] & ~done[:, None, :] & real[:, :, None] & real[:, None, :]
            vjc = np.maximum(0.0, -((u[:, None, :, :] * v[:, None, :, None]) * u[:, :, None, :]).sum(-1))  # (N,i,j)
            d_obs = np.full((N, V), np.inf)
            discs_j = [disc_f0, disc_b0]
            for kk in range(1, 13):
                pk, uk = b.pos(s + 5.0 * kk)
                pk = pk + np.stack([-uk[..., 1], uk[..., 0]], -1) * lat[..., None]
                near = np.zeros((N, V, V), bool)
                for dj in discs_j:
                    dd = pk[:, :, None, :] - dj[:, None, :, :]
                    near |= np.hypot(dd[..., 0], dd[..., 1]) - infl[:, None, :] < VEH_W + R9_MARGIN_M
                hit = near & pair
                if hit.any():
                    cand = 5.0 * (kk - 1) - S.D0_M - vjc * (v / bgr + DT)[..., None]
                    d_obs = np.minimum(d_obs, np.where(hit, cand, np.inf).min(-1))
            d_stop = np.minimum(d_stop, d_obs)
        # crew
        cpos = b.c_p0 + b.c_vel * np.clip(np.minimum(t, b.c_t1) - b.c_t0, 0, None)[..., None]
        cvis = t >= b.c_vis                                                       # (N, C)
        dc = ctr[:, :, None, :] - cpos[:, None, :, :]                             # (N, V, C, 2)
        dcn = np.hypot(dc[..., 0], dc[..., 1]) - (VEH_L / 2 + CREW_R)
        ahead = (-(dc * u[:, :, None, :]).sum(-1)) > -VEH_L
        bgw = S.b_guaranteed(b.theta, b.mu, b.g)
        dcn = dcn - WALK_MAX * (v / np.maximum(bgw, 1e-3) + DT)[..., None]
        d_crew_any = np.where(cvis[:, None, :], dcn, np.inf).min(-1)
        d_crew = np.where(cvis[:, None, :] & ahead, dcn, np.inf).min(-1)
        # a crew member may be hidden behind an occluder until it is known clear: a virtual crew member there, who may
        # walk toward the vehicle while it brakes
        if np.isfinite(b.o_until).any():
            bg0 = S.b_guaranteed(b.theta, b.mu, b.g)
            do = ctr[:, :, None, :] - b.o_pt[:, None, :, :]
            don = np.hypot(do[..., 0], do[..., 1]) - (VEH_L / 2 + CREW_R)
            don = don - WALK_MAX * (v / np.maximum(bg0, 1e-3) + S.RHO_S)[..., None]
            o_ahead = (-(do * u[:, :, None, :]).sum(-1)) > -VEH_L
            act = (t < b.o_until)[:, None, :]
            d_crew_any = np.minimum(d_crew_any, np.where(act, don, np.inf).min(-1))
            d_crew = np.minimum(d_crew, np.where(act & o_ahead, don, np.inf).min(-1))
        sight = np.full((N, V), 1e4)
        # ---------------------------------------------------------------- 3. planner and safety program
        bg = S.b_guaranteed(b.theta, b.mu, b.g)
        rnd = rng.uniform(-S.B_MAX, A_MAX, (N, V))
        need = np.minimum(np.minimum(gap_lead - S.rss_dmin(v, v_lead, bg), d_stop), d_crew - S.R_CREW_MARGIN_M)
        nominal = np.where(need < S.stop_distance(v, NOMINAL_DECEL) + 2.0, -NOMINAL_DECEL,
                           np.clip((b.v_class - v) / 2.0, -NOMINAL_DECEL, A_MAX))
        a_prop = np.select([b.planner == 0, b.planner == 1], [nominal, rnd], A_MAX)
        # scripted behaviours (leader braking, dwell, fault) are planner proposals too: they go through the check
        lb = (vi[None] == b.lead_v[:, None]) & (t >= b.lead_t[:, None])
        a_prop = np.where(lb, -S.B_MAX, a_prop)
        dwell_hit = (s >= b.dwell_s - 2.5) & ~dwell_used & np.isfinite(b.dwell_s)
        dwell_until = np.where(dwell_hit & (v <= S.MOVING_MS), t + b.dwell_d, dwell_until)
        dwell_used |= dwell_hit & (v <= S.MOVING_MS)
        stop_for_dwell = (np.isfinite(b.dwell_s) & ~dwell_used & (b.dwell_s - s <= S.stop_distance(v, NOMINAL_DECEL) + 1.0)) | (t < dwell_until)
        a_prop = np.where(stop_for_dwell, np.where(v > 0, -NOMINAL_DECEL, 0.0), a_prop)
        mv = Move(v=v, a_prop=a_prop, dt=DT, theta=b.theta, mu=b.mu, v_class=b.v_class, sight=sight,
                  gap_lead=gap_lead, v_lead=v_lead, d_stop=d_stop, d_crew=d_crew, must_exit=must_exit,
                  a_max=A_MAX, g=b.g)
        mv.d_crew_any = d_crew_any
        ver = safety_check(None, mv)
        v_in = v
        a = ver.a if shield else np.minimum(np.asarray(a_prop, float), A_MAX)   # shield=False: sandbox "safety off"
        live = real & ~done & active[:, None]
        out["proposals"] += live.sum(1)
        out["interventions"] += (ver.modified & live).sum(1)
        out["no_safe"] += (ver.no_safe_action & live).sum(1)
        # physics: faults and slip act on the vehicle, not the command
        fault_now = (vi[None] == b.fault_v[:, None]) & (t >= b.fault_t[:, None])
        faulted |= fault_now
        a_act = np.where((vi[None] == b.slip_v[:, None]) & (a > 0), a * b.slip_f[:, None], a)
        th = np.radians(b.theta)
        b_phys = b.mu * b.g * np.cos(th) - b.g * np.sin(th)                   # friction limit of braking (physics)
        a_act = np.maximum(a_act, -b_phys)
        v_new = np.maximum(v + a_act * DT, 0.0)
        with np.errstate(divide="ignore", invalid="ignore"):
            tst = np.where(a_act < 0, np.minimum(DT, v / np.where(a_act < 0, -a_act, 1.0)), DT)
        ds_ = np.maximum(v * tst + 0.5 * a_act * tst * tst, 0.0)
        ds_ = np.where(faulted | done | ~active[:, None], 0.0, ds_)
        v_new = np.where(faulted | done, 0.0, v_new)
        r1b = np.isfinite(gap_lead) & (gap_lead < S.rss_dmin(v, v_lead, bg)) & (a > -bg + 1e-9) & live
        out["r1_breach"] += r1b.any(1)
        s_new = s + ds_
        # drift grows with distance driven (a stopped vehicle does not slide sideways): drift_r m/s at class speed
        lat = lat + np.where(vi[None] == b.drift_v[:, None], b.drift_r[:, None] / np.maximum(b.v_class, 1e-3), 0.0) * ds_
        # ---------------------------------------------------------------- 4. closest approach and violations
        p1, u1 = b.pos(s_new)
        nrm1 = np.stack([-u1[..., 1], u1[..., 0]], -1)
        p1 = p1 + nrm1 * lat[..., None]
        c1, disc_f1, disc_b1 = _body(b, s_new, lat)
        discs0 = np.stack([disc_f0, disc_b0], 2)                               # (N, V, 2, 2)
        discs1 = np.stack([disc_f1, disc_b1], 2)
        ii, jj = np.triu_indices(V, 1)
        if len(ii):
            dmin = np.full((N, len(ii)), np.inf)
            for a_ in range(2):
                for b_ in range(2):
                    dmin = np.minimum(dmin, _closest(discs0[:, ii, a_], discs1[:, ii, a_], discs0[:, jj, b_], discs1[:, jj, b_]))
            pair_live = ~done[:, ii] & ~done[:, jj] & real[:, ii] & real[:, jj]
            sep = np.where(pair_live, dmin - VEH_W, np.inf)
            msep = sep.min(1)
            min_sep = np.minimum(min_sep, np.where(active, msep, np.inf))
            out["viol_contact"] += (msep < 0) & active
            ttc = np.where(np.isfinite(gap_lead) & (v > v_lead), gap_lead / np.maximum(v - v_lead, 1e-6), np.inf)
            out["near_ttc"] += ((ttc < TTC_NEAR_S) & live).any(1)
        # the D0 violation and the near-miss gap count only same-road, same-direction pairs (PREREG change 9: the
        # shield's 30 deg leader test also catches vehicles on two roads crossing at a shallow angle)
        ang_k, off_k = b.road_key(s)
        ang_l = np.take_along_axis(ang_k, jl, 1)
        off_l = np.take_along_axis(off_k, jl, 1)
        dang = np.abs((ang_k - ang_l + np.pi) % (2 * np.pi) - np.pi)
        same_road = ((dang < 1e-3) & (np.abs(off_k - off_l) < 0.05)) | (b.path_id == np.take_along_axis(b.path_id, jl, 1))
        gl_now = np.where(live & same_road, gap_lead, np.inf)
        min_gap = np.minimum(min_gap, gl_now.min(1))
        out["viol_gap"] += (gl_now < S.D0_M - 1e-6).any(1)
        out["near_gap"] += (gl_now < 2 * S.rss_dmin(v, v_lead, bg)).any(1)
        # zone: any part of a vehicle inside the zone while closed
        closed_now = ((b.z_close <= t) & (t < b.z_open) & valid_e).any(1)
        inside1 = (s_new > b.z_in) & (s_new - VEH_L < b.z_out) & live
        out["viol_zone"] += closed_now & inside1.any(1)
        just_out = inside & ~inside1 & notice[:, None] & (s_new - VEH_L >= b.z_out)
        out["near_zone"] += (just_out & ((win_close[:, None] - t) < ZONE_MARGIN_S)).any(1)
        # crew: moving within R_crew,stop (closest approach in the step)
        cp1 = b.c_p0 + b.c_vel * np.clip(np.minimum(t + DT, b.c_t1) - b.c_t0, 0, None)[..., None]
        dcc = np.full((N, V), np.inf)
        for a_ in range(2):
            for c in range(C):
                dd = _closest(discs0[:, :, a_], discs1[:, :, a_], cpos[:, None, c], cp1[:, None, c]) - (VEH_W / 2 + CREW_R)
                dcc = np.minimum(dcc, np.where(cvis[:, None, c], dd, np.inf))
        moving = (v > S.MOVING_MS) | (v_new > S.MOVING_MS)
        rstop = S.r_crew_stop(np.maximum(v, v_new), bg)
        out["viol_crew"] += ((dcc < rstop - S.R_CREW_MARGIN_M + 1e-6) & moving & live).any(1) | ((dcc < 0) & live).any(1)
        out["near_crew"] += ((dcc < 2 * rstop) & moving & live).any(1)
        min_crew = np.minimum(min_crew, np.where(live, dcc, np.inf).min(1))
        # R3 / R10 occupancy: physically inside a resource of a group
        occ_in = (b.g_in + 0.01 < s_new[..., None]) & (s_new[..., None] - VEH_L < b.g_out) & live[..., None]   # (N, V, G)
        if occ_in.any():
            # without the table's grant
            out["viol_r3"] += (occ_in & ~granted_g).any((1, 2))
            # opposite directions inside one segment / over-full slots
            inr = (occ_in[..., None] & b.g_onehot).any(2)                          # (N, V, R)
            dirr = (occ_in[..., None] * b.g_resdir).sum(2)
            cnt = inr.sum(1)                                                        # (N, R)
            seg = b.res_kind == 0
            opp = (inr & (dirr > 0)).any(1) & (inr & (dirr < 0)).any(1)
            br = b.res_branched & (cnt > 1)
            out["viol_r3"] += (seg & (opp | br)).any(1)
            out["viol_slots"] += (~seg & (cnt > b.res_slots)).any(1)
        # releases: rear past the group's end
        fin_now = (s_new >= b.length - 0.01) & real
        rel = held_v & (((s_new[..., None] - VEH_L >= b.g_out) & np.isfinite(b.g_out)) | fin_now[..., None])
        if rel.any():
            nn, ii2, gg = np.nonzero(rel)
            held_v[nn, ii2, gg] = False
            lostr = rng.random(len(nn)) < b.loss[nn]
            upr = up[nn, ii2]
            # a release is resent every REQ_RETRY_S until it arrives (Dresner); modelled as arrival after the
            # number of tries a geometric draw gives
            tries = np.where(upr, rng.geometric(1 - np.minimum(b.loss[nn], 0.999)), 1)
            rel_arr[nn, ii2, gg] = t + MSG_LAT_S + (tries - 1) * REQ_RETRY_S + np.where(upr, 0.0, b.down1[nn, ii2] - t).clip(0)
            next_g[nn, ii2] = np.maximum(next_g[nn, ii2], gg + 1)
        # ---------------------------------------------------------------- 5. bookkeeping
        s, v = s_new, v_new
        fin = (s >= b.length - 0.01) & ~done & real
        # type 1: once the leader has stopped, a vehicle at rest has completed the encounter
        lead_stopped = v[np.arange(N), np.maximum(b.lead_v, 0)] <= S.MOVING_MS
        fin |= (b.stop_goal[:, None] & (v <= S.MOVING_MS) & (t > b.lead_t[:, None]) & ~done & real
                & lead_stopped[:, None])
        moving_any = ((v > S.MOVING_MS) & ~done & real).any(1)
        last_change = np.where(fin.any(1) | moving_any | (rel_arr < np.inf).any((1, 2)) | (grant_arr < np.inf).any(1),
                               t, last_change)
        t_done = np.where(fin, t, t_done)
        done |= fin
        stopped_since = np.where((v <= S.MOVING_MS) & ~done, stopped_since + DT, 0.0)
        for n in traces:
            if active[n]:
                traces[n].append({"t": round(t, 3), "s": s[n].tolist(), "v": v[n].tolist(), "a_prop": a_prop[n].tolist(),
                                  "a": a[n].tolist(), "modified": ver.modified[n].tolist(),
                                  "rule": ver.rule[n].tolist(),
                                  "xy": np.round(c1[n], 4).tolist(), "lat": lat[n].tolist(),
                                  "crew": [cp1[n, c].tolist() if cvis[n, c] else None for c in range(C)],
                                  "d_stop": np.where(np.isfinite(d_stop[n]), d_stop[n], -1).round(3).tolist(),
                                  "held": held_v[n].astype(int).tolist(), "granted": granted_g[n].astype(int).tolist(),
                                  "inside": occ_in[n].astype(int).tolist(), "next_g": next_g[n].tolist(),
                                  "move": {k_: np.asarray(x_)[n].tolist() if np.ndim(x_) == 2 else x_ for k_, x_ in
                                           (("v", v_in), ("a_prop", a_prop), ("theta", b.theta), ("mu", b.mu),
                                            ("v_class", b.v_class), ("sight", sight), ("gap_lead", gap_lead),
                                            ("v_lead", v_lead), ("d_stop", d_stop), ("d_crew", d_crew),
                                            ("d_crew_any", d_crew_any), ("must_exit", must_exit.astype(int)))}})
        steps += active
        all_done = done.all(1)
        dwelling = t < dwell_until
        quiet_zone = ~(np.isfinite(b.z_cancel) & (b.z_cancel > t)).any(1)
        # held at a closed or closing zone: the zone line is the binding stop line (change 9 correction: the old test
        # counted only vehicles within ~1 m of the line, so a vehicle that stopped 2 m short looked deadlocked)
        zone_line = no_entry & (b.z_in - s <= d_stop + 0.5)
        held = zone_line & quiet_zone[:, None]
        dead = (stopped_since >= DEADLOCK_S) | done | faulted | (dwelling & (v <= S.MOVING_MS)) | (held & (v <= S.MOVING_MS))
        timeout = t >= b.t_max
        stuck = dead.all(1) & ~all_done & (t - last_change >= DEADLOCK_S)
        ending = active & (all_done | timeout | stuck)
        # a deadlock: the encounter stalls with a vehicle waiting for a grant (not for a fault, dwell or closure)
        # waiting for a grant: the entry of the group it has not been granted is the binding stop line, within request
        # distance (a group far beyond another hold point is not what the vehicle waits for)
        grant_line = has_next & ~held_next & (g_in_next - s <= d_stop + 0.5) & (g_in_next - s < REQ_DIST_M)
        waiting_grant = ~done & ~faulted & ~dwelling & ~held & (stopped_since >= DEADLOCK_S) & grant_line
        fault_like = faulted.any(1) | ((np.abs(lat) > E_LAT_M) & ~done & real).any(1)   # incl. R9 nonconforming
        dl_now = ending & stuck & waiting_grant.any(1) & ~fault_like
        bf_now = ending & stuck & fault_like & ~all_done
        dl_flag = np.where(ending, dl_now, dl_flag)
        bf_flag = np.where(ending, bf_now, bf_flag)
        t_end = np.where(ending, t, t_end)
        active &= ~ending
    _store(np.arange(N))
    fo = full["out"]
    real_f, done_f, faulted_f = full["real"], full["done"], full["faulted"]
    delay = np.where(np.isfinite(full["t_done"]) & real_f, full["t_done"] - full["t_free"], np.nan)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        dmean = np.nanmean(np.where(real_f & ~faulted_f, delay, np.nan), axis=1)
    oc = Outcome(min_sep=full["min_sep"], min_gap_same=full["min_gap"], viol_contact=fo["viol_contact"],
                 viol_gap=fo["viol_gap"], viol_zone=fo["viol_zone"], viol_crew=fo["viol_crew"], viol_r3=fo["viol_r3"],
                 viol_slots=fo["viol_slots"], r1_breach=fo["r1_breach"], near_gap=fo["near_gap"],
                 near_ttc=fo["near_ttc"], near_crew=fo["near_crew"], near_zone=fo["near_zone"],
                 min_crew=full["min_crew"], interventions=fo["interventions"], proposals=fo["proposals"],
                 no_safe=fo["no_safe"], deadlock=full["dl"], blocked_by_fault=full["bf"], finished=done_f.all(1),
                 delay_s=dmean, t_end=full["t_end"], steps=full["steps"])
    return oc, traces
