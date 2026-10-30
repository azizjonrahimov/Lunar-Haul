"""The 12 encounter types of traffic_and_safety.md §C as random builders for lunarsim/atc/encounter.py (B-78).

`build(k, rng)` returns one Spec with randomised parameters (recorded in Spec.params). Planners per vehicle: nominal 40 %,
random fuzzer 30 %, adversarial 30 % (type 12: random/adversarial only). Importance sampling (types 6, 7, 9): the hard
parameter is drawn from a proposal q that oversamples the critical region; Spec.weight = p/q (reported, and the
bounds use the effective sample size).
"""
from __future__ import annotations

import math
from typing import List

import numpy as np

from . import safety as S
from .encounter import (LANE_W, T_LEAD_S, V_HAUL, V_LTV, V_LTV_FAST, VEH_L, VEH_W, Spec)

Y = LANE_W / 2
TAPER = 10.0                 # m, lane to single-lane taper length; A
PLANNER_P = (0.4, 0.3, 0.3)  # nominal, random, adversarial; A (test design)


def _cum(pts):
    pts = np.asarray(pts, float)
    return np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(pts, axis=0).T))])


def _planners(rng, n, fuzz_only=False):
    p = (0.0, 0.5, 0.5) if fuzz_only else PLANNER_P
    return list(rng.choice(3, size=n, p=p))


def _mu(rng):
    return float(rng.choice([0.3, 0.45, 0.6]))


def _arc_of_x(pts, x, after=0):
    """Arc position where a polyline first reaches abscissa x (monotone in x after vertex `after`)."""
    pts = np.asarray(pts, float)
    c = _cum(pts)
    for k in range(after, len(pts) - 1):
        a, b = pts[k], pts[k + 1]
        if (a[0] - x) * (b[0] - x) <= 0 and a[0] != b[0]:
            f = (x - a[0]) / (b[0] - a[0])
            return float(c[k] + f * (c[k + 1] - c[k]))
    raise ValueError("x not on path")


# ------------------------------------------------------------------------------------------------ 1 following
def t1(rng):
    theta = float(rng.choice([0.0, 10.0, 15.0, 20.0]))
    mu = _mu(rng)
    nv = int(rng.choice([2, 3]))
    vcl = float(rng.choice([V_LTV, V_LTV_FAST]))
    vmax = float(S.v_max_r2(theta, mu, 1e4, vcl))
    drivable = vmax > 0.05
    v0 = vmax * rng.uniform(0.6, 1.0) if drivable else 0.0
    b = float(S.b_guaranteed(theta, mu))
    pts = [(0.0, -Y), (700.0, -Y)]
    s, sl = [], 250.0
    for i in range(nv):
        s.append(sl)
        gap = float(S.rss_dmin(v0, v0, b)) + rng.uniform(0, 30) if drivable else 30.0
        sl = sl - VEH_L - gap
    tb = rng.uniform(2, 30)
    return Spec(paths=[pts] * nv, v_class=[vmax if drivable else vcl] * nv, v0=[v0] * nv, s0=s,
                planner=[0] + _planners(rng, nv - 1), theta=theta, mu=mu, lead_brake=(0, tb),
                priority=list(range(nv)), t_max=(tb + 90 if drivable else 0.2), stop_is_goal=True,
                params={"theta": theta, "mu": mu, "n": nv, "v0": v0, "drivable": drivable})


# ------------------------------------------------------------------------------------------------ 2 head-on (and 8, 9)
def _headon(rng, bay=None, queued=None, nv_side=None):
    L = rng.uniform(50, 300)
    bay = rng.random() < 0.5 if bay is None else bay
    queued = (rng.random() < 0.5, rng.random() < 0.5) if queued is None else queued
    A = rng.uniform(30, 150)
    B = rng.uniform(30, 150)
    m = L / 2
    west = [(-A - 260, -Y), (-TAPER, -Y), (0.0, 0.0)]
    if bay:
        west += [(m - 8, 0.0), (m - 3, LANE_W), (m + 3, LANE_W), (m + 8, 0.0)]
    west += [(L, 0.0), (L + TAPER, -Y), (L + B + 60, -Y)]
    east = [(L + B + 260, Y), (L + TAPER, Y), (L, 0.0), (0.0, 0.0), (-TAPER, Y), (-A - 60, Y)]
    paths, s0, groups, v_class, nodes_iv = [], [], [], [], {}
    res_kind, res_slots = ([0, 0], [1, 1]) if bay else ([0], [1])
    cw = _cum(west)
    ce = _cum(east)
    wi = {"in": float(cw[1]), "out": float(cw[-2])}
    ei = {"in": float(ce[1]), "out": float(ce[4])}
    vehicles = []
    for side, q in (("W", queued[0]), ("E", queued[1])):
        k = 1 + int(q) if nv_side is None else nv_side
        for j in range(k):
            vehicles.append((side, j))
    nodes = []
    if bay:
        nodes = [{"cap": 1, "iv": {}}]
    lead = {"W": float(cw[1]) - rng.uniform(20, 120), "E": float(ce[1]) - rng.uniform(20, 120)}
    b0 = float(S.b_guaranteed(0.0, 0.3))
    for idx, (side, j) in enumerate(vehicles):
        s_front = lead[side]
        lead[side] = s_front - VEH_L - float(S.rss_dmin(V_LTV, V_LTV, b0)) - rng.uniform(2, 15)
        vc = V_LTV
        if side == "W":
            pts = west
            if bay:
                c = cw
                g0 = {"res": [0], "dirs": [1], "s_in": float(c[1]), "s_out": float(c[4]), "exit": 0}
                g1 = {"res": [1], "dirs": [1], "s_in": float(c[5]), "s_out": float(c[8])}
                groups.append([g0, g1])
                nodes[0]["iv"][idx] = (float(c[4]), float(c[5]) + VEH_L)
            else:
                groups.append([{"res": [0], "dirs": [1], "s_in": wi["in"], "s_out": wi["out"]}])
        else:
            pts = east
            if bay:   # no bay on this side's path: the whole segment as one group
                groups.append([{"res": [1, 0], "dirs": [-1, -1], "s_in": float(ce[1]), "s_out": float(ce[4])}])
            else:
                groups.append([{"res": [0], "dirs": [-1], "s_in": ei["in"], "s_out": ei["out"]}])
        paths.append(pts)
        s0.append(s_front)
        v_class.append(vc)
    nv = len(paths)
    return dict(paths=paths, s0=s0, groups=groups, v_class=v_class, res_kind=res_kind, res_slots=res_slots,
                nodes=nodes, nv=nv, L=L, bay=bay, queued=queued)


def t2(rng):
    h = _headon(rng)
    nv = h["nv"]
    return Spec(paths=h["paths"], v_class=h["v_class"], v0=[V_LTV] * nv, s0=h["s0"], planner=_planners(rng, nv),
                mu=_mu(rng), groups=h["groups"], res_kind=h["res_kind"], res_slots=h["res_slots"], nodes=h["nodes"],
                priority=list(rng.permutation(nv)), t_max=600.0,
                params={"L": h["L"], "bay": h["bay"], "queued": int(sum(h["queued"])), "n": nv})


# ------------------------------------------------------------------------------------------------ 3 overtaking
def t3(rng):
    xs = 0.0
    gap = rng.uniform(15, 50)
    xa = xs + rng.uniform(5, 30)
    xb = xa + rng.uniform(60, 140)
    X0 = xb + 15 + rng.uniform(40, 150)
    Ls = rng.uniform(50, 200)
    end = X0 + Ls + 200
    slow = [(-50.0, -Y), (X0 - TAPER, -Y), (X0, 0.0), (X0 + Ls, 0.0), (X0 + Ls + TAPER, -Y), (end, -Y)]
    fast = [(-50.0 - gap - VEH_L, -Y), (xa, -Y), (xa + 15, Y), (xb, Y), (xb + 15, -Y), (X0 - TAPER, -Y), (X0, 0.0),
            (X0 + Ls, 0.0), (X0 + Ls + TAPER, -Y), (end, -Y)]
    onc = rng.random() < 0.6
    paths = [slow, fast]
    cs, cf = _cum(slow), _cum(fast)
    groups = [[{"res": [1], "dirs": [1], "s_in": float(cs[1]), "s_out": float(cs[4])}],
              [{"res": [0], "dirs": [1], "s_in": float(cf[1]), "s_out": float(cf[4])},
               {"res": [1], "dirs": [1], "s_in": float(cf[5]), "s_out": float(cf[8])}]]
    s0 = [50.0 + xs, 50.0]
    v0 = [V_HAUL, V_LTV]
    vcl = [V_HAUL, V_LTV]
    if onc:
        o = [(end, Y), (X0 + Ls + TAPER, Y), (X0 + Ls, 0.0), (X0, 0.0), (X0 - TAPER, Y), (-100.0, Y)]
        co = _cum(o)
        a_ov = _arc_of_x(o, xb + 15 + VEH_L, after=4)
        b_ov = _arc_of_x(o, xa - VEH_L, after=4)
        groups.append([{"res": [1], "dirs": [-1], "s_in": float(co[1]), "s_out": float(co[4])},
                       {"res": [0], "dirs": [-1], "s_in": a_ov, "s_out": b_ov}])
        paths.append(o)
        s0.append(rng.uniform(0, float(co[1]) - 30.0))          # outside the segment, able to stop before it
        v0.append(V_LTV)
        vcl.append(V_LTV)
    nv = len(paths)
    sp = Spec(paths=paths, v_class=vcl, v0=v0, s0=s0, planner=_planners(rng, nv), mu=_mu(rng), groups=groups,
              res_kind=[0, 0], res_slots=[1, 1], priority=list(rng.permutation(nv)), t_max=600.0,
              params={"oncoming": onc, "overtake_m": xb - xa, "Lseg": Ls, "n": nv})
    sp.merges = [(1, float(cf[3]) - 1.0, (xb + 15, -Y))]      # the overtaking vehicle keeps clear when merging back
    return sp


# ------------------------------------------------------------------------------------------------ 4 junction
def _arm_path(arm, move):
    """Approach on arm (E, W, N, S), straight / left / right, through a junction box [-8, 8]^2 (right-hand traffic)."""
    D = 200.0
    inbound = {"W": ((-D, -Y), (-8, -Y)), "E": ((D, Y), (8, Y)), "S": ((Y, -D), (Y, -8)), "N": ((-Y, D), (-Y, 8))}
    outbound = {"E": ((8, -Y), (D, -Y)), "W": ((-8, Y), (-D, Y)), "N": ((Y, 8), (Y, D)), "S": ((-Y, -8), (-Y, -D))}
    heading = {"W": "E", "E": "W", "S": "N", "N": "S"}[arm]     # straight continues to the opposite side
    left = {"W": "N", "E": "S", "S": "W", "N": "E"}[arm]
    right = {"W": "S", "E": "N", "S": "E", "N": "W"}[arm]
    to = {"straight": heading, "left": left, "right": right}[move]
    a0, a1 = inbound[arm]
    b0, b1 = outbound[to]
    if move == "straight":
        mid = []
    elif move == "left":
        mid = [(0.5 * (a1[0] + b0[0]) + 0.0, 0.5 * (a1[1] + b0[1]))]
    else:
        mid = [(0.6 * a1[0] + 0.4 * b0[0], 0.6 * a1[1] + 0.4 * b0[1])]
    return [a0, a1] + mid + [b0, b1]


def _tiles_on_path(pts, gq, box=8.0, step=0.25):
    pts = np.asarray(pts, float)
    c = _cum(pts)
    ss = np.arange(0, c[-1], step)
    xy = np.array([np.interp(ss, c, pts[:, 0]), np.interp(ss, c, pts[:, 1])]).T
    size = 2 * box / gq
    tiles, s_in, s_out = set(), math.inf, -math.inf
    m = VEH_W / 2 + 0.3
    for sv, (x, y) in zip(ss, xy):
        for tx in range(gq):
            for ty in range(gq):
                x0, y0 = -box + tx * size, -box + ty * size
                if x0 - m <= x <= x0 + size + m and y0 - m <= y <= y0 + size + m:
                    tiles.add(tx * gq + ty)
                    s_in = min(s_in, sv)
                    s_out = max(s_out, sv)
    return sorted(tiles), s_in, s_out


def t4(rng):
    gq = int(rng.choice([1, 2, 3, 4]))
    nv = int(rng.choice([2, 3, 4]))
    arms = list(rng.permutation(["W", "E", "S", "N"])[:nv])
    paths, groups, s0 = [], [], []
    for arm in arms:
        mv = str(rng.choice(["straight", "left", "right"], p=[0.5, 0.25, 0.25]))
        pts = _arm_path(arm, mv)
        tiles, a, b = _tiles_on_path(pts, gq)
        paths.append(pts)
        groups.append([{"res": tiles, "dirs": [0] * len(tiles), "s_in": a, "s_out": b}])
        s0.append(rng.uniform(80, 180))
    return Spec(paths=paths, v_class=[V_LTV] * nv, v0=[V_LTV] * nv, s0=s0, planner=_planners(rng, nv), mu=_mu(rng),
                groups=groups, res_kind=[1] * gq * gq, res_slots=[1] * gq * gq, priority=list(rng.permutation(nv)),
                t_max=400.0, params={"tiles": gq, "n": nv})


# ------------------------------------------------------------------------------------------------ 5 cyclic wait
def t5(rng):
    """A ring of K single-lane segments (chords) between bays at the nodes. A bay holds 2 vehicles in pockets off the
    road (one radial spoke per vehicle, 8 + 5 i m out); the node point itself is a junction tile. A hop reserves its
    segment and both end tiles (R3, R10) and needs a free slot in the arrival bay (exit rule)."""
    K = int(rng.choice([3, 4]))
    keep = rng.random() < 0.5
    R = rng.uniform(80, 150)
    ang = np.arange(K) * 2 * np.pi / K
    P = np.stack([R * np.cos(ang), R * np.sin(ang)], 1)
    out_dir = P / np.linalg.norm(P, axis=1, keepdims=True)
    nodes = [{"cap": 2, "iv": {}} for _ in range(K)]
    paths, groups, s0 = [], [], []
    starts = list(rng.permutation(K))[: int(rng.integers(2, K + 1))]
    SPOKE = 10.0

    def rot(vec, deg):
        c_, s_ = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        return np.array([c_ * vec[0] - s_ * vec[1], s_ * vec[0] + c_ * vec[1]])

    for i, st in enumerate(starts):
        th = (-60.0, -20.0, 20.0, 60.0)[i]                    # this vehicle's pocket direction at every bay
        d = int(rng.choice([1, -1]))
        hops = int(rng.integers(1, 4))
        seq = [(st + d * h) % K for h in range(hops + 1)]
        k0 = seq[0]
        pts = [P[k0] + rot(out_dir[k0], th) * (SPOKE + VEH_L), P[k0] + rot(out_dir[k0], th) * SPOKE, P[k0]]
        idx_P, idx_go = [2], [1]
        for h, k in enumerate(seq[1:], start=1):
            idx_P.append(len(pts))
            if h < hops:                                      # teardrop through the pocket, no reversing
                pts += [P[k], P[k] + rot(out_dir[k], th - 8) * (SPOKE + 1), P[k] + rot(out_dir[k], th + 8) * (SPOKE + 1),
                        P[k]]
                idx_go.append(len(pts) - 2)
            else:
                pts += [P[k], P[k] + rot(out_dir[k], th) * SPOKE]
        pts = np.array(pts)
        c = _cum(pts)
        gl = []
        for h in range(hops):
            a_, b2 = seq[h], seq[h + 1]
            seg = a_ if d == 1 else b2
            dr = 1 if d == 1 else -1
            s_in = float(c[idx_go[h]]) + (0.5 if h == 0 else 0.0)
            s_out = float(c[idx_P[h + 1]]) + 6.0
            gl.append({"res": [seg, K + a_, K + b2], "dirs": [dr, 0, 0], "s_in": s_in, "s_out": s_out, "exit": b2})
        nodes[k0]["iv"][i] = (0.0, float(c[idx_P[0]]) + VEH_L)
        for h in range(1, hops + 1):
            k = seq[h]
            j = idx_P[h]
            end = float(c[j + 3]) + VEH_L if h < hops else float(c[-1]) + 1.0
            nodes[k]["iv"][i] = (float(c[j]), end)
        paths.append(pts)
        groups.append(gl)
        s0.append(VEH_L)                                     # front at the pocket end, facing the node
    nv = len(paths)
    return Spec(paths=paths, v_class=[V_LTV] * nv, v0=[0.0] * nv, s0=s0, planner=_planners(rng, nv), mu=_mu(rng),
                groups=groups, res_kind=[0] * K + [1] * K, res_slots=[1] * (2 * K), nodes=nodes,
                priority=list(rng.permutation(nv)), t_max=900.0, exit_keep_free=bool(keep),
                params={"K": K, "n": nv, "keep_free": bool(keep)})


# ------------------------------------------------------------------------------------------------ 6 landing closure
def t6(rng):
    R = float(rng.choice([200.0, 500.0, 1000.0]))
    nv = int(rng.choice([2, 3]))
    paths, chords, s0, vcl = [], [], [], []
    w = 1.0
    for i in range(nv):
        ang = rng.uniform(0, 2 * np.pi)
        off = rng.uniform(-0.8, 0.8) * R
        u = np.array([math.cos(ang), math.sin(ang)])
        nrm = np.array([-u[1], u[0]])
        half = math.sqrt(R * R - off * off)
        D = R + 400
        pts = [nrm * off - u * D, nrm * off + u * D]
        z_in, z_out = D - half, D + half
        cls = V_HAUL if rng.random() < 0.3 else V_LTV
        if i == 0:                                            # the vehicle inside: IS on its remaining exit distance
            q_far = rng.random() < 0.7
            frac = rng.uniform(0.6, 1.0) if q_far else rng.uniform(0.0, 1.0)
            dens_q = 0.7 * (frac >= 0.6) / 0.4 + 0.3
            w = 1.0 / dens_q
            s_front = z_in + VEH_L + frac * (2 * half - VEH_L)
            s_front = z_out - (s_front - z_in) + VEH_L        # frac = 1 -> just entered (longest exit)
        else:
            s_front = rng.uniform(0, z_in - 50)
        paths.append(pts)
        chords.append((z_in, z_out))
        s0.append(float(s_front))
        vcl.append(cls)
    ev = [(T_LEAD_S, T_LEAD_S + 2700.0)]
    kind = str(rng.choice(["plain", "delay", "waveoff"], p=[0.5, 0.25, 0.25]))
    t_max = T_LEAD_S + 60
    if kind == "delay":
        dt_ = rng.uniform(300, 1800)
        ev = [(T_LEAD_S + dt_, T_LEAD_S + dt_ + 2700.0)]
        t_max += dt_
    elif kind == "waveoff":
        tw = rng.uniform(T_LEAD_S - 900, T_LEAD_S + 600)
        ev = [(T_LEAD_S, T_LEAD_S + 2700.0, tw), (tw + T_LEAD_S, tw + T_LEAD_S + 2700.0)]
        t_max = tw + T_LEAD_S + 60
    zone = {"c": (0.0, 0.0), "r": R, "events": ev, "chord": chords}
    groups, res_kind, s0 = _crossing_tiles(paths, s0, vcl)
    sp = Spec(paths=paths, v_class=vcl, v0=vcl, s0=s0, planner=_planners(rng, nv), mu=_mu(rng), zone=zone,
              groups=groups, res_kind=res_kind, res_slots=[1] * len(res_kind),
              priority=list(range(nv)), t_max=t_max, weight=w,
              params={"R": R, "kind": kind, "inside_cls": "HAUL" if vcl[0] == V_HAUL else "LTV", "n": nv,
                      "exit_s": (chords[0][1] + VEH_L - s0[0]) / vcl[0]})
    return sp


def _crossing_tiles(paths, s0, v0=None):
    """Junction control (R10) where two straight roads cross: one tile per crossing, reserved from where the front
    reaches the crossing zone to where the rear has cleared it (half-length W / sin(angle) + 2 m). Overlapping
    crossings on one road form one group. A start inside a crossing zone is moved just past it."""
    n = len(paths)
    iv = [[] for _ in range(n)]
    rid = 0
    for i in range(n):
        for j in range(i + 1, n):
            p0, p1 = np.asarray(paths[i][0], float), np.asarray(paths[i][-1], float)
            q0, q1 = np.asarray(paths[j][0], float), np.asarray(paths[j][-1], float)
            d1, d2 = p1 - p0, q1 - q0
            den = d1[0] * d2[1] - d1[1] * d2[0]
            if abs(den) < 1e-9:
                continue
            w0 = q0 - p0
            ti = (w0[0] * d2[1] - w0[1] * d2[0]) / den
            tj = (w0[0] * d1[1] - w0[1] * d1[0]) / den
            if not (0 < ti < 1 and 0 < tj < 1):
                continue
            sin_a = abs(den) / (np.linalg.norm(d1) * np.linalg.norm(d2))
            half = min((VEH_W + 1.0) / max(sin_a, 0.01) + 2.0, 1000.0)   # exact for shallow crossings too
            for k, t in ((i, ti), (j, tj)):
                arc = t * float(np.linalg.norm(np.asarray(paths[k][-1], float) - np.asarray(paths[k][0], float)))
                iv[k].append([arc - half, arc + half, [rid]])
            rid += 1
    groups = []
    s0 = list(s0)
    for k in range(n):
        merged = []
        for a, b, r in sorted(iv[k]):
            if merged and a <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], b)
                merged[-1][2] = merged[-1][2] + r
            else:
                merged.append([a, b, list(r)])
        # start state (PREREG change 9): never inside a crossing zone and never within stopping distance + 20 m of
        # one; a start that would be is moved just past that zone, and the check repeats for the next zone
        clear = float(S.stop_distance(v0[k], S.b_guaranteed(0.0, 0.3))) + 20.0 if v0 is not None else 0.0
        moved = True
        while moved:
            moved = False
            for a, b, _ in merged:
                if a - clear < s0[k] < b + VEH_L:
                    s0[k] = b + VEH_L + 1.0
                    moved = True
        groups.append([{"res": r, "dirs": [0] * len(r), "s_in": a, "s_out": b} for a, b, r in merged
                       if b + VEH_L >= s0[k]])
    return groups, [1] * rid, s0


# ------------------------------------------------------------------------------------------------ 7 crew
def t7(rng):
    variant = str(rng.choice(["crossing", "occluded", "toward"]))
    vcl = float(rng.choice([V_LTV, V_LTV_FAST]))
    xc = rng.uniform(80, 250)
    pts = [(0.0, -Y), (xc + 300, -Y)]
    s0 = 10.0
    walk = rng.uniform(0.5, 1.2)
    b = float(S.b_guaranteed(0.0, 0.45))
    w = 1.0
    dwell = None
    occl = math.inf
    if variant == "toward":                                   # robot stopped (loading) at xc; crew walks to it
        dwell = {0: (xc, 1e5)}
        stop_at = rng.uniform(2, 15)
        p0 = (xc + 60, -Y)
        vel = (-walk, 0.0)
        t_e = rng.uniform(0, 150)
        t_stop = t_e + (60 - VEH_L / 2 - stop_at) / walk
        crew = [{"p0": p0, "vel": vel, "t_emerge": t_e, "t_stop": t_stop, "occluder": [occl]}]
    else:
        side = rng.choice([-1, 1])
        y0 = -Y + side * (rng.uniform(4, 12) if variant == "crossing" else rng.uniform(6, 30))
        vel = (0.0, -side * walk)
        t_arrive = (xc - s0) / vcl                            # when the robot would reach xc at full speed
        crit = (t_arrive - 40, t_arrive)                      # emergence while the robot is close: oversampled
        if rng.random() < 0.8:
            t_e = rng.uniform(*crit)
        else:
            t_e = rng.uniform(0, t_arrive + 30)
        lo, hi = 0.0, t_arrive + 30
        p = 1.0 / (hi - lo)
        q = 0.2 / (hi - lo) + (0.8 / 40.0 if crit[0] <= t_e <= crit[1] else 0.0)
        w = p / q
        t_e = max(t_e, 0.0)
        # crossing: visible standing beside the road from the start, walks across at t_e; occluded: hidden behind a
        # boulder (the map knows it, an EVA is under way) until t_e, then walks across
        crew = [{"p0": (xc, y0), "vel": vel, "t_emerge": t_e, "t_stop": math.inf,
                 "t_visible": 0.0 if variant == "crossing" else t_e}]
        occluders = [(xc, y0, t_e)] if variant == "occluded" else []
        return Spec(paths=[pts], v_class=[vcl], v0=[vcl], s0=[s0], planner=_planners(rng, 1), mu=0.45, crew=crew,
                    occluders=occluders, t_max=(xc + 300) / vcl + 900, weight=w, priority=[0],
                    params={"variant": variant, "v_class": vcl, "walk": walk, "lateral_m": abs(y0 + Y)})
    return Spec(paths=[pts], v_class=[vcl], v0=[vcl], s0=[s0], planner=_planners(rng, 1), mu=0.45, crew=crew,
                dwell=dwell, t_max=(xc + 300) / vcl + 200, weight=w, priority=[0],
                params={"variant": variant, "v_class": vcl, "walk": walk})


# ------------------------------------------------------------------------------------------------ 8 comms
def t8(rng):
    h = _headon(rng, bay=False)
    nv = h["nv"]
    loss = float(rng.uniform(0.1, 0.5))
    k = int(rng.integers(nv))
    t0 = rng.uniform(0, 60)
    down = [()] * nv
    down[k] = (t0, t0 + rng.uniform(5, 120))
    return Spec(paths=h["paths"], v_class=h["v_class"], v0=[V_LTV] * nv, s0=h["s0"], planner=_planners(rng, nv),
                mu=_mu(rng), groups=h["groups"], res_kind=h["res_kind"], res_slots=h["res_slots"], nodes=h["nodes"],
                loss=loss, link_down=down, priority=list(rng.permutation(nv)), t_max=900.0,
                params={"loss": loss, "down_s": down[k][1] - down[k][0], "n": nv})


# ------------------------------------------------------------------------------------------------ 9 nonconforming
def t9(rng):
    kind = str(rng.choice(["slip", "drift", "dead"]))
    h = _headon(rng, bay=False, queued=(rng.random() < 0.5, False))
    nv = h["nv"]
    sp = Spec(paths=h["paths"], v_class=h["v_class"], v0=[V_LTV] * nv, s0=h["s0"], planner=_planners(rng, nv),
              mu=_mu(rng), groups=h["groups"], res_kind=h["res_kind"], res_slots=h["res_slots"],
              priority=list(rng.permutation(nv)), t_max=600.0, params={"kind": kind, "n": nv})
    if kind == "slip":
        sp.slip = (0, float(rng.uniform(0.1, 0.5)))
    elif kind == "drift":
        sp.drift = (0, float(rng.uniform(0.005, 0.03)) * rng.choice([-1, 1]))
    else:   # dead stop, oversampled while inside the segment: arrival at the segment ~ (s_in - s0) / v
        g = h["groups"][0][0]
        t_in = (g["s_in"] - h["s0"][0]) / V_LTV
        t_out = (g["s_out"] - h["s0"][0]) / V_LTV
        if rng.random() < 0.8:
            tf = rng.uniform(t_in, t_out + 2)
        else:
            tf = rng.uniform(0, t_out + 60)
        p = 1 / (t_out + 60)
        q = 0.2 / (t_out + 60) + (0.8 / (t_out + 2 - t_in) if t_in <= tf <= t_out + 2 else 0.0)
        sp.weight = p / q
        sp.fault_stop = (0, float(tf))
    return sp


# ------------------------------------------------------------------------------------------------ 10 speed mix
def t10(rng):
    X0 = rng.uniform(150, 300)
    Ls = rng.uniform(50, 200)
    end = X0 + Ls + 200
    lane = [(-150.0, -Y), (X0 - TAPER, -Y), (X0, 0.0), (X0 + Ls, 0.0), (X0 + Ls + TAPER, -Y), (end, -Y)]
    c = _cum(lane)
    k = int(rng.integers(2, 5))
    paths, s0, vcl, groups, planner = [], [], [], [], []
    sfront = 150.0 + rng.uniform(0, 50)
    adv_owner = int(rng.integers(2))
    for i in range(k):
        cls = V_HAUL if rng.random() < 0.5 else V_LTV
        paths.append(lane)
        s0.append(sfront)
        sfront -= VEH_L + rng.uniform(12, 40)
        vcl.append(cls)
        groups.append([{"res": [0], "dirs": [1], "s_in": float(c[1]), "s_out": float(c[4])}])
        owner = i % 2
        planner.append(2 if owner == adv_owner else int(rng.choice(3, p=PLANNER_P)))
    if rng.random() < 0.6:
        o = [(end, Y), (X0 + Ls + TAPER, Y), (X0 + Ls, 0.0), (X0, 0.0), (X0 - TAPER, Y), (-200.0, Y)]
        co = _cum(o)
        paths.append(o)
        s0.append(rng.uniform(0, 150))
        vcl.append(V_LTV)
        groups.append([{"res": [0], "dirs": [-1], "s_in": float(co[1]), "s_out": float(co[4])}])
        planner.append(int(rng.choice(3, p=PLANNER_P)))
    nv = len(paths)
    return Spec(paths=paths, v_class=vcl, v0=vcl, s0=[max(x, 1.0) for x in s0], planner=planner, mu=_mu(rng),
                groups=groups, res_kind=[0], res_slots=[1], priority=list(rng.permutation(nv)), t_max=900.0,
                params={"n": nv, "haul": sum(v == V_HAUL for v in vcl)})


# ------------------------------------------------------------------------------------------------ 11 apron
def t11(rng):
    mult = int(rng.choice([2, 4, 8]))
    nv = 2 * mult
    paths, groups, s0, dwell = [], [], [], {}
    count = {"W": 0, "E": 0}
    for i in range(nv):
        side = "W" if i % 2 == 0 else "E"
        sg = -1 if side == "W" else 1
        yin = -Y if side == "W" else Y
        pts = [(sg * 160.0, yin), (sg * 22.0, yin), (sg * 8.0, 0.0), (sg * 22.0, -yin), (sg * 160.0, -yin)]
        c = _cum(pts)
        j = count[side]
        count[side] += 1
        groups.append([{"res": [0 if side == "W" else 1], "dirs": [0], "s_in": float(c[1]) - 2.0,
                        "s_out": float(c[3]) + 2.0}])
        s0.append(float(c[1]) - 20.0 - j * (VEH_L + 12.0) - rng.uniform(0, 5))
        dwell[i] = (float(c[2]), float(rng.uniform(10, 40)))
        paths.append(pts)
    return Spec(paths=paths, v_class=[V_LTV] * nv, v0=[0.0] * nv, s0=s0,
                planner=_planners(rng, nv), mu=_mu(rng), groups=groups, res_kind=[1, 1], res_slots=[1, 1],
                dwell=dwell, priority=list(rng.permutation(nv)), t_max=150.0 + 70.0 * mult,
                params={"mult": mult, "n": nv})


# ------------------------------------------------------------------------------------------------ 12 fuzzing
def t12(rng):
    base = int(rng.choice([1, 2, 4, 7]))
    sp = BUILDERS[base](rng)
    sp.planner = _planners(rng, len(sp.paths), fuzz_only=True)
    sp.params = dict(sp.params, base_type=base)
    return sp


BUILDERS = {1: t1, 2: t2, 3: t3, 4: t4, 5: t5, 6: t6, 7: t7, 8: t8, 9: t9, 10: t10, 11: t11, 12: t12}


def build(k: int, rng: np.random.Generator) -> Spec:
    return BUILDERS[k](rng)
