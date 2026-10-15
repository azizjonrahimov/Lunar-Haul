"""Scripted expert driver: A* route on a slope + lighting cost grid (20 m), pure-pursuit follower (5 m lookahead).

The A* cost of moving between neighbouring 20 m cells is the *time* to drive it at the autonomy level's speed
cap, slowed by the slope factor and the lighting factor (physics.py), with cells steeper than the hard slope
limit impassable. The heuristic (straight-line distance at the flat-ground cap) is admissible because every
factor is <= 1. The search is limited to the bounding box of start and goal plus a margin, widened if no
route is found.
"""
from __future__ import annotations

import heapq
import math
from typing import List, Optional, Sequence, Tuple

import numpy as np

from . import physics as R

SQRT2 = math.sqrt(2.0)
_NEIGH = [(-1, -1, SQRT2), (-1, 0, 1.0), (-1, 1, SQRT2), (0, -1, 1.0), (0, 1, 1.0), (1, -1, SQRT2), (1, 0, 1.0), (1, 1, SQRT2)]


def cost_grid(terrain, sun_az_deg=None) -> np.ndarray:
    """Seconds per metre to cross each 20 m cell at the nominal flat-ground speed of 1 m/s, before the
    direction-dependent up-sun term: 1 / (slope factor * shadow factor); inf where impassable.
    sun_az_deg None = no lighting term; "night" = everything in shadow."""
    f = R.slope_speed_factor(terrain.slope20)
    if sun_az_deg == R.NIGHT:
        f = f * R.SHADOW_SPEED_FACTOR
    elif sun_az_deg is not None:
        f = np.where(terrain.shadow_grid(float(sun_az_deg)), f * R.SHADOW_SPEED_FACTOR, f)
    with np.errstate(divide="ignore"):
        return np.where(f > 0, 1.0 / np.maximum(f, 1e-12), np.inf)


def astar(cost: np.ndarray, start: Tuple[int, int], goal: Tuple[int, int], px: float, sun_az_deg=None,
          margin_cells: int = 150) -> Optional[List[Tuple[int, int]]]:
    """8-connected A* over cells (row from south, column). Edge cost = px * step length * mean of the two cells'
    cost, times 1/cos(tack) when the move heads up-sun. Returns the cell path or None."""
    rows, cols = cost.shape
    for margin in (margin_cells, margin_cells * 3, max(rows, cols)):
        r0 = max(0, min(start[0], goal[0]) - margin)
        r1 = min(rows, max(start[0], goal[0]) + margin + 1)
        c0 = max(0, min(start[1], goal[1]) - margin)
        c1 = min(cols, max(start[1], goal[1]) + margin + 1)
        path = _astar_box(cost, start, goal, px, sun_az_deg, r0, r1, c0, c1)
        if path is not None or (r0 == 0 and c0 == 0 and r1 == rows and c1 == cols):
            return path
    return None


def _astar_box(cost, start, goal, px, sun_az_deg, r0, r1, c0, c1):
    if not (np.isfinite(cost[start]) and np.isfinite(cost[goal])):
        return None
    tack = None
    if sun_az_deg is not None and sun_az_deg != R.NIGHT:
        tack = 1.0 / math.cos(math.radians(R.UP_SUN_TACK_DEG))
        up = []
        for dr, dc, _ in _NEIGH:
            hd = math.degrees(math.atan2(dc, dr)) % 360       # +row = +y (north), +col = +x (east)
            d = abs((hd - float(sun_az_deg) + 180) % 360 - 180)
            up.append(d <= R.UP_SUN_HALF_ANGLE_DEG)
    W = c1 - c0
    gr, gc = goal
    best = {}
    came = {}
    s_key = (start[0] - r0) * W + (start[1] - c0)
    best[s_key] = 0.0
    h0 = px * math.hypot(start[0] - gr, start[1] - gc)
    heap = [(h0, 0.0, start[0], start[1])]
    while heap:
        f, g, r, c = heapq.heappop(heap)
        key = (r - r0) * W + (c - c0)
        if g > best.get(key, math.inf):
            continue
        if (r, c) == goal:
            path = [(r, c)]
            while key in came:
                key = came[key]
                path.append((key // W + r0, key % W + c0))
            return path[::-1]
        cr = cost[r, c]
        for k, (dr, dc, step) in enumerate(_NEIGH):
            nr, nc = r + dr, c + dc
            if nr < r0 or nr >= r1 or nc < c0 or nc >= c1:
                continue
            cn = cost[nr, nc]
            if not math.isfinite(cn):
                continue
            w = px * step * 0.5 * (cr + cn)
            if tack is not None and up[k]:
                w *= tack
            ng = g + w
            nkey = (nr - r0) * W + (nc - c0)
            if ng < best.get(nkey, math.inf):
                best[nkey] = ng
                came[nkey] = key
                heapq.heappush(heap, (ng + px * math.hypot(nr - gr, nc - gc), ng, nr, nc))
    return None


def plan(terrain, a: Sequence[float], b: Sequence[float], sun_az_deg=None) -> Optional[np.ndarray]:
    """Route from a to b (local metres) as an (n, 2) polyline of 20 m cell centres with the exact end points."""
    cost = cost_grid(terrain, sun_az_deg)
    ja, ia = terrain.cell(a[0], a[1])
    jb, ib = terrain.cell(b[0], b[1])
    cells = astar(cost, (int(ja), int(ia)), (int(jb), int(ib)), terrain.px20, sun_az_deg)
    if cells is None:
        return None
    pts = np.array([[(c + 0.5) * terrain.px20, (r + 0.5) * terrain.px20] for r, c in cells], dtype=float)
    pts[0], pts[-1] = a, b
    return pts


def densify(poly: np.ndarray, step_m: float = 5.0) -> np.ndarray:
    """Resample a polyline at (about) step_m spacing, keeping the end points."""
    out = [poly[0]]
    for p, q in zip(poly[:-1], poly[1:]):
        L = float(np.hypot(*(q - p)))
        n = max(1, int(math.ceil(L / step_m)))
        for k in range(1, n + 1):
            out.append(p + (q - p) * k / n)
    return np.asarray(out)


class PurePursuit:
    """Pure-pursuit path follower: steer towards the path point `lookahead_m` ahead of the closest point."""

    def __init__(self, path: np.ndarray, lookahead_m: float = 5.0):
        self.path = densify(np.asarray(path, float), 1.0)
        self.s = np.concatenate([[0.0], np.cumsum(np.hypot(*np.diff(self.path, axis=0).T))])
        self.lookahead = lookahead_m
        self.k = 0                              # index of the closest point found so far (monotone)

    def closest(self, x: float, y: float, window: int = 200) -> int:
        lo, hi = self.k, min(len(self.path), self.k + window)
        d = np.hypot(self.path[lo:hi, 0] - x, self.path[lo:hi, 1] - y)
        self.k = lo + int(np.argmin(d))
        return self.k

    def action(self, state, v_cap: float) -> Tuple[float, float]:
        """(steer-rate command, throttle) in [-1, 1] for the env's action space."""
        k = self.closest(state["x"], state["y"])
        target_s = self.s[k] + self.lookahead
        j = min(len(self.path) - 1, int(np.searchsorted(self.s, target_s)))
        tx, ty = self.path[j]
        bearing = math.atan2(tx - state["x"], ty - state["y"])          # map azimuth
        alpha = (bearing - state["psi"] + math.pi) % (2 * math.pi) - math.pi
        ld = max(1.0, math.hypot(tx - state["x"], ty - state["y"]))
        delta_cmd = math.atan2(2.0 * R.ROVER["wheelbase_m"] * math.sin(alpha), ld)
        dmax = math.radians(R.ROVER["steer_max_deg"])
        delta_cmd = max(-dmax, min(dmax, delta_cmd))
        rate = (delta_cmd - state["delta"]) / math.radians(R.ROVER["steer_rate_dps"])   # per 1 s step
        throttle = 1.0 if abs(alpha) < math.radians(45) else 0.3
        return max(-1.0, min(1.0, rate)), throttle

    def done(self, x: float, y: float, tol_m: float = 10.0) -> bool:
        return math.hypot(*(self.path[-1] - (x, y))) <= tol_m
