"""Positioning layer of the Lunar Rover Interaction Protocol (B-90, problem 1, experiment E50).

Each vehicle carries a true position (the engine's, interpolated along the route samples) and an estimated one; this
module simulates the estimation error e = estimate - truth and the vehicle's own covariance P along a recorded
trajectory, layer by layer (research note 01, `research_notes/Lunar Rover Interaction Protocol/01_positioning_and_time.md`:
parameters from its section D, maths from its section E; source tags as in the note):

(a) dead reckoning ("dr"): error grows with distance driven, as a bias per drive leg (the quoted "percent of distance"
    is bias-dominated, note E1) with a drift by terrain class: 2 % firm level ground with visual odometry and a star
    tracker [MAIM07] EARTH, [DAF23, ATHA24] REQ; 10 % on loose soil or slopes above 10 deg [HELM06] EARTH; 3 % in shadow
    with lamps (A; upper end [DAI26] SIM). Heading: a star tracker leaves a bounded heading error of 0.1 deg (A;
    [DAF23]); the gyro-only variant integrates a 3 deg/h bias [MAIM07] MARS (note E1 case (a)).
(b) cooperative ranging ("ranging"): two-way ranges to the base beacons (surveyed, map geolocation 0.15 m [BARK21]) and
    to other vehicles inside radio line of sight (the DEM mesh of B-70): UWB 0.3 m within 100 m [PLANS18, NUCH24] EARTH /
    A; two-way ranging over the base radio 3 m beyond that, up to the mesh's 5 km (A). Beacons: an EKF update with the
    beacon's covariance added along the line of sight (note E2, Cramer-Rao); other vehicles: covariance intersection
    (note E2, "the default rule for mixed fleets"), because repeated mutual ranging correlates the errors.
(c) absolute fixes ("fixes"): terrain matching against the orbital map at opportunities every 100 m sunlit, 500 m in
    shadow (A, [DAF23]), 1.7 m 1-sigma sunlit [DAF23] REQ, 3 m in the dark with a 0.3 failure probability [ATHA24];
    a fix while driving costs a 120 s stop (A, [NASH26]) and is taken only when the vehicle's 95 % bound exceeds the
    trigger; a vehicle that arrives at a site takes one there at no extra cost (it is stopped anyway).
(d) LANS ("lans"): 10 m (95 %) horizontal with the map height when 3 or more satellites are in view [INTEROP25] SIM,
    [LDN25, ML24] REQ; availability by year 0 (2026-2028), 0.4 (2029), 0.6 (2030), 0.8 (2031-32) [GRAM24, ML24, ESA24,
    MUR26], modelled as one window per Earth day of that share (A), with an optional schedule slip.

Outputs per vehicle per step: |e| (m) and the 95 % bound of the vehicle's own covariance (radius containing 95 % of a
2D Gaussian with the larger eigenvalue on both axes: 2.4477 sigma_max). The filter is linear in the errors (note E2);
the bias of each drive leg is a filter state, so ranges and fixes also estimate it (simulate()'s docstring).

Nothing here runs inside the engine: E50 (tools/atc/run_e50.py) records a run's trajectories and runs this module on
them. The engine's coupling is the opt-in reservation margin of lunarsim/atc/roads.py and the Move margin of
lunarsim/atc/safety.py.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

R95 = math.sqrt(-2.0 * math.log(0.05))      # 2.4477: radius of 95 % for a circular 2D Gaussian, in sigmas

# ------------------------------------------------------------------------------------------------ parameters (note 01 D)
DEFAULTS: Dict[str, Any] = {
    # (a) dead reckoning, 1-sigma horizontal error as a share of distance driven
    "dr_firm": 0.02,             # [MAIM07] EARTH; [DAF23, ATHA24] REQ (VO + star tracker, firm level ground); sweep 1-2.5 %
    "dr_loose": 0.10,            # [HELM06] EARTH; slip from existing notes (loose soil or slope > 10 deg, no VO); 5-30 %
    "dr_shadow": 0.03,           # A; upper end [DAI26] SIM 6.6 % (shadow, VO with lamps); 2-7 %
    "slope_loose_deg": 10.0,     # note 01 D row "slope above 10 deg"
    "heading": "star_tracker",   # star_tracker | gyro
    "heading_sigma_deg": 0.1,    # A; "small fraction of a degree" [DAF23] (star tracker, bounded); 0.01-0.5
    "gyro_drift_deg_h": 3.0,     # [MAIM07] MARS; [LRV73] REQ (gyro only); 1-5
    # (b) ranging
    "uwb_sigma_m": 0.3,          # [PLANS18, NUCH24] EARTH; 0.1-0.7
    "uwb_range_m": 100.0,        # A; no lunar value is public; 50-300
    "radio_sigma_m": 3.0,        # A; long-range two-way ranging over the base radio; 1-10
    "radio_range_m": 5000.0,     # the mesh's radio range (lunarsim.atc.radio DEFAULT_D_MAX_M, provisional)
    "beacon_sigma_m": 0.15,      # [BARK21] map horizontal geolocation error (beacons surveyed on the map)
    "beacons": ["BASE", "DEPOT", "POWER", "PAD_A"],   # A: 4 beacons (note D "Number of base beacons" 4, sweep 2-8);
                                 # the 10 m mast at BASE, 2.5 m at the others; the landing pad as a lander beacon
    "range_interval_s": 60.0,    # A: one ranging epoch a minute
    "max_peers": 4,              # A: ranges to at most this many other vehicles per epoch (nearest in view)
    "peer_fusion": "ci",         # ci (covariance intersection) | ekf (independence assumed: over-confident)
    # a parked vehicle ranges once after it stops, not again until it moves: its geometry, the beacons' survey errors
    # and its neighbours' errors do not change while it stands, so repeating the same ranges would be counted as new
    # information (over-confidence; seen as NEES 6.8 against 2 in the first E50 cell)
    # (c) absolute terrain fixes
    "fix_sigma_lit_m": 1.7,      # [DAF23] REQ (5 m at 3-sigma); 0.4-3
    "fix_sigma_dark_m": 3.0,     # [ATHA24] SIM/EARTH; 2-5
    "fix_fail_dark": 0.3,        # [ATHA24]; A; 0.1-0.5
    "fix_spacing_lit_m": 100.0,  # A; craters of 5 m and more detected at 15-40 m [DAF23]; 50-500
    "fix_spacing_dark_m": 500.0,  # A; only 10-20 m craters are mapped in shadow [DAF23]; 200-2000
    "fix_stop_s": 120.0,         # A; [NASH26]; 30-600
    "fix_trigger_m": 2.5,        # A: take a driving fix when the 95 % bound exceeds half the 5 m separation budget
    "dark_fixes": True,          # note D rows "in the dark"; False = no fixes in shadow (the B-90 task's wording)
    "fix_at_stops": True,        # a vehicle arriving at a site takes a fix there (no extra stop)
    "map_sigma_m": 0.15,         # [BARK21]: added to every map-referenced fix
    # (d) LANS
    "lans_95_m": 10.0,           # [INTEROP25] SIM (17.2 m); [LDN25, ML24] REQ; 5-20
    "lans_availability": {2026: 0.0, 2027: 0.0, 2028: 0.0, 2029: 0.4, 2030: 0.6, 2031: 0.8, 2032: 0.8},
                                 # [GRAM24] (two AFS by mid-2028; IOC-C 40 %), [ML24, ESA24] (Moonlight 15 of 24 h),
                                 # [MUR26] (LNSS); 2028 sweep 0-0.2
    "lans_slip_years": 0,        # A; 0-3 (one milestone slipped >= 6 months in 2026)
    "lans_interval_s": 60.0,     # A
    "year": 2028,
    # budget
    "budget_m": 5.0,             # separation budget: the static margin D0_M of rule R1 (lunarsim/atc/safety.py)
}
LAYERS = ("dr", "ranging", "fixes", "lans")
LAYER_SETS: Dict[str, Tuple[str, ...]] = {
    "perfect": (),
    "dr": ("dr",),
    "dr+ranging": ("dr", "ranging"),
    "dr+ranging+fixes": ("dr", "ranging", "fixes"),
    "dr+ranging+fixes+lans": ("dr", "ranging", "fixes", "lans"),
}
FIRM, LOOSE, SHADOW = 0, 1, 2


def bound95(P: np.ndarray) -> np.ndarray:
    """95 % radius of N(0, P) bounded by the larger eigenvalue on both axes (P: (..., 2, 2))."""
    a, b, d = P[..., 0, 0], P[..., 0, 1], P[..., 1, 1]
    lam = 0.5 * (a + d) + np.sqrt(np.maximum(0.25 * (a - d) ** 2 + b * b, 0.0))
    return R95 * np.sqrt(np.maximum(lam, 0.0))


def pair_bound95(P_a: np.ndarray, P_b: np.ndarray) -> np.ndarray:
    """95 % bound of the relative position of two vehicles with independent errors (P_a + P_b)."""
    return bound95(np.asarray(P_a) + np.asarray(P_b))


def lans_share(year: int, p: Optional[Dict[str, Any]] = None) -> float:
    p = dict(DEFAULTS, **(p or {}))
    y = int(year) - int(p["lans_slip_years"])
    av = {int(k): float(v) for k, v in p["lans_availability"].items()}
    if y < min(av):
        return 0.0
    return av[min(max(av), y)]


# ------------------------------------------------------------------------------------------------ trajectories
@dataclass
class Trajectories:
    """True motion on a time grid: t_h (T,), xy (T, N, 2), idx (T, N) nearest route sample, ds (T, N) metres driven in
    the step ending at t, head (T, N, 2) unit direction of motion, leg (T, N) drive-leg counter (changes at a new
    leg), cls (T, N) terrain class (FIRM / LOOSE / SHADOW), lit (T, N), arrive (T, N) the vehicle stopped at a site in
    this step; ids (N,) vehicle ids, ant (N,) antenna heights (m)."""
    t_h: np.ndarray
    xy: np.ndarray
    idx: np.ndarray
    ds: np.ndarray
    head: np.ndarray
    leg: np.ndarray
    cls: np.ndarray
    lit: np.ndarray
    arrive: np.ndarray
    ids: np.ndarray
    ant: np.ndarray
    dt_s: float

    @classmethod
    def from_segments(cls_, segs: Dict[int, List[Sequence[Any]]], start: Dict[int, str], t0_h: float, t1_h: float,
                      dt_s: float, ant: Dict[int, float], name, sample_xy: np.ndarray, site_index: Dict[str, int],
                      legs: Dict[str, List[int]], slope_deg: np.ndarray, lit_fn=None,
                      slope_loose_deg: float = DEFAULTS["slope_loose_deg"]) -> "Trajectories":
        """segs: vehicle id -> [[a, b, t0_h, t1_h, load], ...] (the engine's segments after the road layer; a == b is a
        stop at a); start: vehicle id -> site at t0_h when no segment covers it; name(site) -> the leg-file name
        (pads at their stand-off); lit_fn(t_h, a, b) -> bool (None = always lit)."""
        t = np.arange(t0_h, t1_h, dt_s / 3600.0)
        ids = np.array(sorted(segs.keys() | start.keys()), dtype=np.int64)
        T, N = len(t), len(ids)
        xy = np.zeros((T, N, 2), np.float32)
        idx = np.zeros((T, N), np.int32)
        ds = np.zeros((T, N), np.float32)
        head = np.zeros((T, N, 2), np.float32)
        leg = np.full((T, N), -1, np.int32)
        cl = np.zeros((T, N), np.int8)
        lit = np.ones((T, N), bool)
        arrive = np.zeros((T, N), bool)
        lit_memo: Dict[Tuple[str, str, int], bool] = {}

        def is_lit(tt, a, b):
            if lit_fn is None:
                return True
            k = (a, b, int(math.floor(tt)))
            if k not in lit_memo:
                lit_memo[k] = bool(lit_fn(float(k[2]), a, b))
            return lit_memo[k]

        def lit_steps(kk, a, b):
            """Lit flag per grid step (the sun-link series is hourly: one lookup per hour)."""
            hrs = np.floor(t[kk]).astype(np.int64)
            u, inv = np.unique(hrs, return_inverse=True)
            return np.array([is_lit(float(h), a, b) for h in u], bool)[inv]
        n_leg = 0
        for n, vid in enumerate(ids):
            lst = sorted((list(s) for s in segs.get(int(vid), [])), key=lambda s: (s[2], s[3]))
            here = start.get(int(vid), lst[0][0] if lst else None)
            cur = site_index[here] if here is not None else 0
            xy[:, n] = sample_xy[cur]
            idx[:, n] = cur
            for a, b, ta, tb, _ in lst:
                if tb <= t0_h or ta >= t1_h or tb <= ta:
                    if tb <= t0_h:                               # ended before the window: the vehicle stands at b
                        cur = site_index[b]
                        xy[:, n] = sample_xy[cur]
                        idx[:, n] = cur
                    continue
                k0, k1 = np.searchsorted(t, [ta, tb], side="left")
                if a == b:
                    s_i = site_index[a]
                    xy[k0:, n] = sample_xy[s_i]
                    idx[k0:, n] = s_i
                    kk = np.arange(k0, min(k1, T))
                    if len(kk):
                        lit[kk, n] = lit_steps(kk, a, a)
                    continue
                ids_leg = legs.get(f"{name(a)}->{name(b)}") or [site_index[a], site_index[b]]
                P = sample_xy[ids_leg].astype(np.float64)
                seg_len = np.hypot(*np.diff(P, axis=0).T)
                cum = np.concatenate([[0.0], np.cumsum(seg_len)])
                L = cum[-1]
                kk = np.arange(k0, min(k1, T))
                f = np.clip((t[kk] - ta) / (tb - ta), 0.0, 1.0)
                s = f * L
                px = np.interp(s, cum, P[:, 0])
                py = np.interp(s, cum, P[:, 1])
                xy[kk, n, 0], xy[kk, n, 1] = px, py
                j = np.clip(np.searchsorted(cum, s, side="right") - 1, 0, len(ids_leg) - 2) if len(ids_leg) > 1 else np.zeros(len(kk), int)
                near = np.where(s - cum[j] > 0.5 * seg_len[j] if len(seg_len) else False, j + 1, j)
                idx[kk, n] = np.asarray(ids_leg)[near]
                # distance in each step: from the previous grid point (or the leg start) to this one
                s_prev = np.concatenate([[max(0.0, (t[k0 - 1] - ta) / (tb - ta) * L) if k0 > 0 and t[k0 - 1] > ta else 0.0],
                                         s[:-1]]) if len(kk) else s
                ds[kk, n] = s - s_prev
                dirs = np.diff(P, axis=0) / np.maximum(seg_len, 1e-9)[:, None]
                head[kk, n] = dirs[j]
                leg[kk, n] = n_leg
                n_leg += 1
                if len(kk):
                    lt = lit_steps(kk, a, b)
                    lit[kk, n] = lt
                    cl[kk, n] = np.where(slope_deg[idx[kk, n]] > slope_loose_deg, LOOSE, np.where(lt, FIRM, SHADOW))
                end = site_index[b]
                if k1 < T:
                    xy[k1:, n] = sample_xy[end]
                    idx[k1:, n] = end
                    ds[k1, n] += max(0.0, L - (s[-1] if len(kk) else 0.0))
                    arrive[k1, n] = True
        return cls_(t, xy, idx, ds, head, leg, cl, lit, arrive, ids, np.array([ant[int(v)] for v in ids], float), dt_s)


# ------------------------------------------------------------------------------------------------ line of sight
class LOS:
    """Dense line-of-sight lookups on the mesh-v1 file (lunarsim.atc.radio): vehicle-vehicle by antenna heights, and
    beacon-vehicle (BASE beacon on the 10 m mast)."""

    def __init__(self, rm, d_max_m: float):
        n = rm.n
        self.n = n
        self.mat: Dict[Tuple[float, float], np.ndarray] = {}
        ok_d = rm.d <= d_max_m
        for c, (hi, hj) in enumerate(rm.combos):
            m = np.zeros((n, n), bool)
            ok = (rm.clear_dm[c] >= 0) & ok_d
            m[rm.I[ok], rm.J[ok]] = True
            self.mat[(hi, hj)] = m
        for (hi, hj), m in list(self.mat.items()):
            self.mat[(hi, hj)] = m | self.mat[(hj, hi)].T
        for m in self.mat.values():
            np.fill_diagonal(m, True)
        self.mast = {}
        for c, (_, h) in enumerate(rm.mast_combos):
            v = np.zeros(n, bool)
            ok = (rm.mast_clear_dm[c] >= 0) & (rm.mast_d <= d_max_m)
            v[rm.mast_j[ok]] = True
            v[rm.base] = True
            self.mast[h] = v
        self.base = rm.base

    def ok(self, i_idx: int, h_i: float, j_idx: np.ndarray, h_j: np.ndarray) -> np.ndarray:
        out = np.zeros(len(j_idx), bool)
        for h in np.unique(h_j):
            sel = h_j == h
            out[sel] = self.mat[(float(h_i), float(h))][i_idx, j_idx[sel]]
        return out


# ------------------------------------------------------------------------------------------------ the filter
def _scalar_update(z, P, h, y, R):
    """Range update on the error state z = [e (2), f (2)] with H = [u, 0]: the innovation is -u.e + y (y: the
    neighbour's or beacon's error along u plus the range noise)."""
    Ph = P[:, :2] @ h
    S = float(h @ Ph[:2]) + R
    K = Ph / S
    z1 = z + K * (-(h @ z[:2]) + y)
    P1 = P - np.outer(K, Ph)
    return z1, 0.5 * (P1 + P1.T)


def _ci_update(z, P, h, y, R, w_grid=np.linspace(0.05, 0.95, 19)):
    """Covariance intersection with a scalar range whose error correlates with the prior: prior P / w, noise R / (1 - w),
    w chosen to minimise the trace of the position block (note 01 E2). With a single range CI inflates the prior across
    the line of sight (P / w there), so "no update" (w = 1) is always a candidate: the trace never grows, and repeated
    ranging to the same neighbour cannot inflate P without bound."""
    best = (P[0, 0] + P[1, 1], None, P)
    for w in w_grid:
        Pw, Rw = P / w, R / (1.0 - w)
        Ph = Pw[:, :2] @ h
        S = float(h @ Ph[:2]) + Rw
        K = Ph / S
        P1 = Pw - np.outer(K, Ph)
        tr = P1[0, 0] + P1[1, 1]
        if tr < best[0]:
            best = (tr, K, P1)
    _, K, P1 = best
    if K is None:
        return z, P
    return z + K * (-(h @ z[:2]) + y), 0.5 * (P1 + P1.T)


@dataclass
class NavResult:
    layers: Tuple[str, ...]
    err: np.ndarray          # (T, N) |e| in m
    b95: np.ndarray          # (T, N) 95 % bound of the vehicle's position covariance, m
    e: Optional[np.ndarray]  # (T, N, 2) error vectors (store_errors)
    P: Optional[np.ndarray]  # (T, N, 2, 2) position covariances (store_errors)
    counts: Dict[str, float]


def simulate(tr: Trajectories, layers: Sequence[str], seed: int, params: Optional[Dict[str, Any]] = None,
             los: Optional[LOS] = None, beacon_idx: Optional[Sequence[int]] = None,
             beacon_xy: Optional[np.ndarray] = None, mast_idx: int = 0, store_errors: bool = False) -> NavResult:
    """Run the layers over the trajectories. Random streams per layer (seed, 90, k) so every layer set sees the same
    dead-reckoning draws (common random numbers).

    Filter state per vehicle (errors, estimate minus truth): z = [e, f], e the position error (m), f the error of the
    vehicle's estimate of its dead-reckoning bias on the current leg (the drift direction per unit of k x distance,
    1/2 per axis at the leg start, so that |bias| has an rms of 1 and the drift an rms of k x distance, note 01 D).
    Driving a step of length ds on a terrain class with drift k: e <- e - k ds f, plus the heading term psi ds n_perp
    (star tracker: bounded psi [DAF23]; gyro: psi grows at the gyro bias [MAIM07]) as process noise. A new leg draws a
    new bias (f reset, its covariance 1/2 I, no correlation with e). Ranges and fixes update z through its correlation
    with e, so they also estimate the bias (the note's E2 table treats drift intervals as independent; estimating the
    bias is the better filter it mentions)."""
    p = dict(DEFAULTS, **(params or {}))
    layers = tuple(layers)
    for x in layers:
        if x not in LAYERS:
            raise ValueError(f"unknown layer {x}")
    T, N = tr.ds.shape
    dt = tr.dt_s
    err = np.zeros((T, N), np.float32)
    b95 = np.zeros((T, N), np.float32)
    E = np.zeros((T, N, 2), np.float32) if store_errors else None
    PP = np.zeros((T, N, 2, 2), np.float32) if store_errors else None
    counts = {"range_updates": 0, "beacon_updates": 0, "peer_updates": 0, "fixes": 0, "fixes_driving": 0,
              "fix_stop_h": 0.0, "fixes_failed": 0, "lans_updates": 0}
    if "dr" not in layers:
        return NavResult(layers, err, b95, E, PP, counts)
    r_dr = np.random.default_rng([int(seed), 90, 1])
    r_rg = np.random.default_rng([int(seed), 90, 2])
    r_fx = np.random.default_rng([int(seed), 90, 3])
    r_ln = np.random.default_rng([int(seed), 90, 4])
    k_cls = np.array([p["dr_firm"], p["dr_loose"], p["dr_shadow"]])
    sig_psi = math.radians(p["heading_sigma_deg"])
    gyro = p["heading"] == "gyro"
    sig_b = math.radians(p["gyro_drift_deg_h"]) / 3600.0
    z = np.zeros((N, 4))
    P = np.zeros((N, 4, 4))
    psi = np.zeros(N)
    gb = np.zeros(N)
    t_leg = np.zeros(N)
    cur_leg = np.full(N, -1)
    need_range = np.zeros(N, bool)    # moved since its last ranging epoch
    since_opp = np.zeros(N)
    I2 = np.eye(2)
    H2 = np.hstack([I2, np.zeros((2, 2))])
    use_rg, use_fx, use_ln = "ranging" in layers, "fixes" in layers, "lans" in layers
    k_rg = max(1, int(round(p["range_interval_s"] / dt)))
    k_ln = max(1, int(round(p["lans_interval_s"] / dt)))
    share = lans_share(int(p["year"]), p) if use_ln else 0.0
    sig_lans = p["lans_95_m"] / R95
    bidx = np.asarray(beacon_idx if beacon_idx is not None else [], np.int64)
    bvar = p["beacon_sigma_m"] ** 2
    bxy = np.asarray(beacon_xy if beacon_xy is not None else np.zeros((0, 2)), float)
    if len(bxy) != len(bidx):
        raise ValueError("beacon_idx and beacon_xy differ in length")
    # each beacon's surveyed position is off the truth by a fixed map geolocation error (per axis), drawn once per seed
    eb = np.random.default_rng([int(seed), 90, 5]).normal(0.0, p["beacon_sigma_m"], (len(bidx), 2))
    sig_lit = math.hypot(p["fix_sigma_lit_m"], p["map_sigma_m"])
    sig_dark = math.hypot(p["fix_sigma_dark_m"], p["map_sigma_m"])
    fuse_peer = _ci_update if p["peer_fusion"] == "ci" else _scalar_update

    def pos_update(i, sig, rng):
        """A 2D position fix (terrain match or LANS) with per-axis sigma."""
        S = P[i][:2, :2] + sig * sig * I2
        K = P[i][:, :2] @ np.linalg.inv(S)
        z[i] = z[i] + K @ (-z[i, :2] + rng.normal(0.0, sig, 2))
        P1 = P[i] - K @ H2 @ P[i]
        P[i] = 0.5 * (P1 + P1.T)

    for k in range(T):
        ds = tr.ds[k]
        mv = ds > 0
        need_range |= mv
        # ---- (a) dead reckoning
        if mv.any():
            new = mv & (tr.leg[k] != cur_leg)
            for i in np.nonzero(new)[0]:
                cur_leg[i] = tr.leg[k, i]
                z[i, 2:] = -r_dr.normal(0.0, math.sqrt(0.5), 2)      # f = estimate (0) - true unit bias
                P[i, 2:, :] = 0.0
                P[i, :, 2:] = 0.0
                P[i, 2, 2] = P[i, 3, 3] = 0.5
                psi[i] = r_dr.normal(0.0, sig_psi)
                gb[i] = r_dr.normal(0.0, sig_b)
                t_leg[i] = 0.0
            a = k_cls[tr.cls[k]] * np.where(mv, ds, 0.0)
            h = tr.head[k].astype(np.float64)
            nperp = np.stack([-h[:, 1], h[:, 0]], axis=1)
            if gyro:
                t_leg[mv] += dt
                psi_now = psi + gb * t_leg
                s_psi = np.sqrt(sig_psi ** 2 + (sig_b * t_leg) ** 2)
            else:
                psi_now = psi
                s_psi = np.full(N, sig_psi)
            dd = np.where(mv, ds, 0.0)
            z[:, :2] += -a[:, None] * z[:, 2:] + (psi_now * dd)[:, None] * nperp
            Pef, Pff = P[:, :2, 2:].copy(), P[:, 2:, 2:]
            A = a[:, None, None]
            P[:, :2, :2] += -A * (Pef + np.transpose(Pef, (0, 2, 1))) + A * A * Pff \
                + ((s_psi * dd) ** 2)[:, None, None] * I2
            P[:, :2, 2:] = Pef - A * Pff
            P[:, 2:, :2] = np.transpose(P[:, :2, 2:], (0, 2, 1))
        # ---- (c) absolute fixes
        if use_fx:
            sp = np.where(tr.lit[k], p["fix_spacing_lit_m"], p["fix_spacing_dark_m"])
            since_opp += np.where(mv, ds, 0.0)
            opp = mv & (since_opp >= sp)
            since_opp[opp] = 0.0
            stop_fix = tr.arrive[k] if p["fix_at_stops"] else np.zeros(N, bool)
            if opp.any() or stop_fix.any():
                bb = bound95(P[:, :2, :2])
                for i in np.nonzero(opp | stop_fix)[0]:
                    driving = bool(opp[i]) and not bool(stop_fix[i])
                    if driving and bb[i] <= p["fix_trigger_m"]:
                        continue
                    dark = not tr.lit[k, i]
                    if dark and not p["dark_fixes"]:
                        continue
                    if driving:
                        counts["fixes_driving"] += 1
                        counts["fix_stop_h"] += p["fix_stop_s"] / 3600.0
                    if dark and r_fx.random() < p["fix_fail_dark"]:
                        counts["fixes_failed"] += 1
                        continue
                    counts["fixes"] += 1
                    pos_update(i, sig_dark if dark else sig_lit, r_fx)
        # ---- (d) LANS
        if use_ln and share > 0 and k % k_ln == 0:
            ph = (tr.t_h[k] % 24.0) / 24.0
            if ph < share:                                            # every vehicle at once
                S = P[:, :2, :2] + sig_lans * sig_lans * I2
                K = P[:, :, :2] @ np.linalg.inv(S)
                z += np.einsum("nij,nj->ni", K, -z[:, :2] + r_ln.normal(0.0, sig_lans, (N, 2)))
                P = P - K @ P[:, :2, :]
                P = 0.5 * (P + np.transpose(P, (0, 2, 1)))
                counts["lans_updates"] += N
        # ---- (b) ranging
        if use_rg and k % k_rg == 0:
            act = np.nonzero(need_range)[0]
            need_range[:] = mv
            xy = tr.xy[k].astype(np.float64)
            ix = tr.idx[k]
            for i in act:
                if len(bidx):                                         # beacons in view (EKF)
                    vis = np.array([los.mast[tr.ant[i]][ix[i]] if b == mast_idx else
                                    los.mat[(2.5, float(tr.ant[i]))][b, ix[i]] for b in bidx])
                    for b_i in np.nonzero(vis)[0]:
                        dvec = xy[i] - bxy[b_i]
                        d = math.hypot(*dvec)
                        if d < 1.0 or d > p["radio_range_m"]:
                            continue
                        u = dvec / d
                        sig = p["uwb_sigma_m"] if d <= p["uwb_range_m"] else p["radio_sigma_m"]
                        y = float(u @ eb[b_i]) + r_rg.normal(0.0, sig)
                        z[i], P[i] = _scalar_update(z[i], P[i], u, y, sig * sig + bvar)
                        counts["beacon_updates"] += 1
                dv = xy - xy[i]                                       # other vehicles in view, nearest first
                dist = np.hypot(dv[:, 0], dv[:, 1])
                cand = np.nonzero((dist >= 1.0) & (dist <= p["radio_range_m"]))[0]
                if len(cand):
                    cand = cand[los.ok(int(ix[i]), float(tr.ant[i]), ix[cand], tr.ant[cand])]
                    cand = cand[np.argsort(dist[cand])][: int(p["max_peers"])]
                for j in cand:
                    d = dist[j]
                    u = (xy[i] - xy[j]) / d
                    sig = p["uwb_sigma_m"] if d <= p["uwb_range_m"] else p["radio_sigma_m"]
                    R = sig * sig + float(u @ P[j, :2, :2] @ u)
                    y = float(u @ z[j, :2]) + r_rg.normal(0.0, sig)
                    z[i], P[i] = fuse_peer(z[i], P[i], u, y, R)
                    counts["peer_updates"] += 1
            counts["range_updates"] = counts["beacon_updates"] + counts["peer_updates"]
        err[k] = np.hypot(z[:, 0], z[:, 1])
        b95[k] = bound95(P[:, :2, :2])
        if store_errors:
            E[k] = z[:, :2]
            PP[k] = P[:, :2, :2]
    return NavResult(layers, err, b95, E, PP, counts)


# ------------------------------------------------------------------------------------------------ summaries
def error_summary(res: NavResult, tr: Trajectories, budget_m: float = DEFAULTS["budget_m"],
                  mask: Optional[np.ndarray] = None) -> Dict[str, float]:
    """Median / p95 / max of |e| over vehicle-steps (moving steps by default), and the share of moving time whose 95 %
    bound exceeds the separation budget."""
    m = (tr.ds > 0) if mask is None else mask
    if not m.any():
        return {"n": 0}
    x = res.err[m].astype(np.float64)
    b = res.b95[m].astype(np.float64)
    return {"n": int(m.sum()), "median_m": float(np.median(x)), "p95_m": float(np.quantile(x, 0.95)),
            "max_m": float(x.max()), "b95_median_m": float(np.median(b)), "b95_p95_m": float(np.quantile(b, 0.95)),
            "share_b95_over_budget": float((b > budget_m).mean()), "share_err_over_budget": float((x > budget_m).mean())}
