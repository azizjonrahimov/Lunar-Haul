"""True rover motion at 1 Hz, rebuilt from an ATC trace (format lunarsim-atc-trace v1, tools/atc/export_trace.py).

Rule (data/atc/trace_pair/index.json, "legs"): a drive or reposition leg carries edge = [edge id, f0, f1, resource];
the vehicle moves along the edge's polyline from sample index f0 x (n - 1) to f1 x (n - 1) at constant speed
(speed = piece length / piece duration); every other leg is a stop; between legs the vehicle stands where it last was.

Two additions that the trace does not hold, both stated in results/E56_README.md:
  parking slot  every vehicle has its own stand at a site (PARK_RADIUS_M from the site point, at an angle fixed by the
                vehicle id), because the trace puts every parked vehicle on the same point (range 0);
  lane offset   a moving vehicle keeps LANE_OFFSET_M to the right of the road centre line, so that two vehicles that
                pass do not drive through each other.
The offset is blended over BLEND_M around a site and smoothed with a SMOOTH_S box filter, so positions are continuous.
"""
from __future__ import annotations

import gzip
import json
import math
import os
from typing import Any, Dict, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PARK_RADIUS_M = 15.0
LANE_OFFSET_M = 2.0
BLEND_M = 30.0
SMOOTH_S = 15


def trace_path(seed: int, run: str) -> str:
    """Seed 1 is the committed trace pair; the other seeds were exported by the same tool into data/atc/integrity."""
    if seed == 1:
        return os.path.join(ROOT, "data", "atc", "trace_pair", f"{run}.json.gz")
    return os.path.join(ROOT, "data", "atc", "integrity", "traces", f"seed{seed:02d}", f"{run}.json.gz")


def load_trace(path: str) -> Dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("format") != "lunarsim-atc-trace":
        raise ValueError(f"{path}: not an ATC trace")
    return doc


def _piece(poly: np.ndarray, f0: float, f1: float) -> Tuple[np.ndarray, np.ndarray]:
    """Points of the polyline between sample indices f0 (n - 1) and f1 (n - 1), and their cumulative length."""
    n = len(poly)
    a, b = f0 * (n - 1), f1 * (n - 1)
    rev = b < a
    lo, hi = (b, a) if rev else (a, b)
    idx = [lo] + [float(i) for i in range(int(math.floor(lo)) + 1, int(math.ceil(hi))) if lo < i < hi] + [hi]
    idx = np.array(idx)
    i0 = np.clip(np.floor(idx).astype(int), 0, n - 2)
    fr = (idx - i0)[:, None]
    pts = poly[i0] * (1 - fr) + poly[i0 + 1] * fr
    if rev:
        pts = pts[::-1]
    seg = np.hypot(*np.diff(pts, axis=0).T) if len(pts) > 1 else np.zeros(0)
    return pts, np.r_[0.0, np.cumsum(seg)]


def _dilate(mask: np.ndarray, r: int) -> np.ndarray:
    """True within r steps of a True."""
    c = np.cumsum(np.r_[0, mask.astype(np.int64)])
    n = len(mask)
    lo = np.clip(np.arange(n) - r, 0, n)
    hi = np.clip(np.arange(n) + r + 1, 0, n)
    return (c[hi] - c[lo]) > 0


def vehicle_tracks(doc: Dict[str, Any], t_limit_s: int = 0) -> Dict[str, Any]:
    """1 Hz positions over the trace window (or over its first t_limit_s seconds).

    Returns {"xy": float32 [V, T, 2] (metres, minus the BASE point), "moving": bool [V, T], "ids": [...], "t0_h", "T"}.
    """
    t0_h, t1_h = doc["window_h"]
    T = int(round((t1_h - t0_h) * 3600.0))
    if t_limit_s:
        T = min(T, int(t_limit_s))
    sites = {k: np.array(v, float) for k, v in doc["sites"].items()}
    site_names = sorted(sites)
    site_xy = np.array([sites[s] for s in site_names])
    origin = sites["BASE"]
    edges = {k: np.array(v, float) for k, v in doc["roads"]["edges"].items()}
    fleet = doc["fleet"]
    V = len(fleet)
    xy = np.zeros((V, T, 2), np.float32)
    moving = np.zeros((V, T), bool)
    for vi, (vid, _owner, _cls, _ant, start) in enumerate(fleet):
        base = np.full((T, 2), np.nan)
        base[0] = sites[start]
        for t0, t1, frm, to, _kind, _load, _job, edge in doc["legs"].get(str(vid), []):
            k0 = max(0, int(math.ceil((t0 - t0_h) * 3600.0 - 1e-6)))
            k1 = min(T - 1, int(math.floor((t1 - t0_h) * 3600.0 + 1e-6)))
            if k1 < k0:
                continue
            if edge is None:
                if frm == to:
                    base[k0] = sites[frm]
                continue
            pts, cum = _piece(edges[edge[0]], float(edge[1]), float(edge[2]))
            if cum[-1] <= 0.0 or t1 <= t0:
                base[k0] = pts[0]
                continue
            k = np.arange(k0, k1 + 1)
            s = np.clip(((k / 3600.0 + t0_h) - t0) / (t1 - t0), 0.0, 1.0) * cum[-1]
            base[k, 0] = np.interp(s, cum, pts[:, 0])
            base[k, 1] = np.interp(s, cum, pts[:, 1])
            moving[vi, k0:k1 + 1] = True
        have = ~np.isnan(base[:, 0])
        last = np.maximum.accumulate(np.where(have, np.arange(T), 0))
        base = base[last]                                            # stand where it last was
        step = np.diff(base, axis=0, prepend=base[:1])
        sp = np.hypot(step[:, 0], step[:, 1])
        mv = sp > 1e-6
        moving[vi] &= mv | np.r_[mv[1:], False]
        # The offset only changes near motion: work on those steps (plus step 0) and hold it elsewhere.
        near = _dilate(mv, 2 * SMOOTH_S)
        near[0] = True
        K = np.flatnonzero(near)
        bK, stK, spK, mvK = base[K], step[K], sp[K], mv[K]
        hx = np.where(mvK, stK[:, 0] / np.maximum(spK, 1e-9), np.nan)          # heading, held through stops
        hy = np.where(mvK, stK[:, 1] / np.maximum(spK, 1e-9), np.nan)
        hl = np.maximum.accumulate(np.where(mvK, np.arange(len(K)), 0))
        hx, hy = np.nan_to_num(hx[hl]), np.nan_to_num(hy[hl])
        lane = LANE_OFFSET_M * np.stack([hy, -hx], axis=1)                     # right-hand side of the road
        ang = 2.0 * math.pi * (int(vid) % 8) / 8.0 + 0.7 * np.arange(len(site_names))
        slot = PARK_RADIUS_M * np.stack([np.cos(ang), np.sin(ang)], axis=1)    # [sites, 2]
        off = np.zeros((len(K), 2))
        wmax = np.zeros(len(K))
        for si in range(len(site_names)):
            d = np.hypot(bK[:, 0] - site_xy[si, 0], bK[:, 1] - site_xy[si, 1])
            w = np.clip(1.0 - d / BLEND_M, 0.0, 1.0)
            off += w[:, None] * slot[si]
            wmax = np.maximum(wmax, w)
        off += (1.0 - wmax)[:, None] * lane
        ker = np.ones(SMOOTH_S) / SMOOTH_S
        sm = np.stack([np.convolve(np.pad(off[:, j], (SMOOTH_S // 2, SMOOTH_S // 2), mode="edge"), ker, "valid")
                       for j in (0, 1)], axis=1)
        inner = _dilate(mv, SMOOTH_S)[K]                # smoothing is exact here; outside it the offset is constant
        off = np.where(inner[:, None], sm, off)
        pos = np.cumsum(near) - 1                       # index into K of the latest worked step
        xy[vi] = (base + off[pos] - origin).astype(np.float32)
    return {"xy": xy, "moving": moving, "ids": [f[0] for f in fleet],
            "antenna_m": [float(f[3]) for f in fleet], "t0_h": t0_h, "T": T,
            "seed": doc.get("seed"), "run": doc.get("name")}
