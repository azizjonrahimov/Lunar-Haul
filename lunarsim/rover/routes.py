"""Planned rover routes for the 3D views (B-32; format ``lunarsim-routes`` v1).

    python -m lunarsim.rover.routes --site connecting_ridge      # -> data/driving/routes-v1.json

For every directed leg of the driving tables (data/driving/driving-v1.json; the pads at every standoff) and every
lighting case (sun azimuth 0, 90, 180, 270 deg, night) this is the expert's PLANNED route: the same cost grid and
A* the tables use (lunarsim.rover.expert.plan), no driving simulation. Each route is resampled so that no two
vertices are more than MAX_SPACING_M apart, keeping every corner of the A* polyline (each corner-to-corner segment is
split into equal parts), and carries:
    z      terrain height from the 5 m grid (Terrain.height; the vehicle's own height is added by the viewer)
    s      cumulative distance along the route (m)
    f      cumulative time fraction (0 at the start, 1 at the end) from the expert's speed model along the route:
           slope factor x lighting factor (shadow, up-sun) x (1 - slip at the median soil, phi 42 deg), as the
           fast integrator in tables.py; the table's expected leg time T is spread as t(vertex) = f * T
The `length_m` of each route is checked against the table's route.length_m (same polyline, densified to 5 m).

Encoding (columnar, integer, delta; gzip-friendly): positions in decimetres, f in 1e-4. A geometry is stored once
and shared by the lighting cases that plan the same route:
    geoms[g] = {"n": vertices, "x0", "y0", "z0", "dx", "dy", "dz"}   x_k = (x0 + sum dx[:k]) / 10  (m), same for
               y, z; dx, dy, dz have n - 1 entries; s_k = sum of the horizontal segment lengths of the decoded
               vertices up to k (computed by the reader; decode_geom)
    legs[leg][lighting] = {"geom": g, "df": [...], "length_m", "table_length_m"}   f_k = sum df[:k] / 1e4
Coordinates: the terrain pack's local frame (x east, y north, metres from the tile's south-west corner).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import physics as R
from .expert import plan
from .tables import LIGHTING, leg_profile, legs_from_sites

ROUTES_FORMAT = "lunarsim-routes"
ROUTES_VERSION = 1
MAX_SPACING_M = 10.0
XY_SCALE = 10.0            # decimetres
F_SCALE = 1e4
DRIVING = os.path.join("data", "driving", "driving-v1.json")
OUT = os.path.join("data", "driving", "routes-v1.json")


def light_key(sun) -> str:
    return "night" if sun == R.NIGHT else f"{float(sun):g}"


def dedupe(poly: np.ndarray, tol: float = 1e-9) -> np.ndarray:
    """Drop consecutive repeated vertices."""
    p = np.asarray(poly, float)
    keep = [0] + [k for k in range(1, len(p)) if math.hypot(*(p[k] - p[k - 1])) > tol]
    return p[keep]


def corner_indices(poly: np.ndarray, tol: float = 1e-9) -> List[int]:
    """End points and every vertex where the direction changes (indices into the polyline without repeats)."""
    p = dedupe(poly, tol)
    keep = [0]
    for k in range(1, len(p) - 1):
        a, b = p[k] - p[k - 1], p[k + 1] - p[k]
        la, lb = math.hypot(*a), math.hypot(*b)
        if la < tol or lb < tol:
            continue
        cross = (a[0] * b[1] - a[1] * b[0]) / (la * lb)
        dot = (a[0] * b[0] + a[1] * b[1]) / (la * lb)
        if abs(cross) > tol or dot < 0:
            keep.append(k)
    keep.append(len(p) - 1)
    return keep


def resample(poly: np.ndarray, max_spacing: float = MAX_SPACING_M) -> np.ndarray:
    """Corners kept; each corner-to-corner segment split into ceil(L / max_spacing) equal parts."""
    p = dedupe(poly)
    idx = corner_indices(p)
    out = [p[idx[0]]]
    for i0, i1 in zip(idx[:-1], idx[1:]):
        a, b = p[i0], p[i1]
        L = math.hypot(*(b - a))
        if L <= 1e-9:
            continue
        n = max(1, int(math.ceil(L / max_spacing - 1e-9)))
        for k in range(1, n + 1):
            out.append(a + (b - a) * k / n)
    return np.asarray(out)


def time_fractions(prof: Dict[str, np.ndarray], sun, s_query: np.ndarray, phi_deg: float = R.PHI_REF) -> np.ndarray:
    """Cumulative time fraction at distances s_query from the 5 m leg profile (tables.leg_profile)."""
    ds = prof["ds"]
    sl = R.slip(prof["grade"], phi_deg)
    f = R.slope_speed_factor(prof["slope"]) * R.lighting_factor(prof["heading"], sun, prof["shadow"]) * (1.0 - sl)
    blocked = (f <= 0) | (sl >= R.DIG_IN_SLIP)        # not driven in the integrator (an intervention instead)
    with np.errstate(divide="ignore", invalid="ignore"):
        dt = np.where(blocked, 0.0, ds / np.where(blocked, 1.0, f))
    s = np.concatenate([[0.0], np.cumsum(ds)])
    t = np.concatenate([[0.0], np.cumsum(dt)])
    total = t[-1]
    if total <= 0:
        frac = s / max(s[-1], 1e-12)
    else:
        frac = t / total
    return np.interp(np.clip(s_query, 0, s[-1]), s, frac)


def route_record(terrain, a, b, sun) -> Optional[Dict[str, Any]]:
    """Planned route of one leg and lighting: vertices x, y, z, s, f (metres; f in [0, 1])."""
    poly = plan(terrain, a, b, sun)
    if poly is None:
        return None
    prof = leg_profile(terrain, poly, sun)
    v = resample(poly)
    seg = np.hypot(*np.diff(v, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    z = terrain.height(v[:, 0], v[:, 1])
    f = time_fractions(prof, sun, s)
    f[0], f[-1] = 0.0, 1.0
    return {"x": v[:, 0], "y": v[:, 1], "z": np.asarray(z, float), "s": s, "f": f, "length_m": float(s[-1]),
            "profile_length_m": prof["length_m"]}


def _ints(x, scale) -> np.ndarray:
    return np.rint(np.asarray(x, float) * scale).astype(np.int64)


def encode_geom(rec) -> Dict[str, Any]:
    x, y, z = (_ints(rec[k], XY_SCALE) for k in ("x", "y", "z"))
    return {"n": int(len(x)), "x0": int(x[0]), "y0": int(y[0]), "z0": int(z[0]),
            "dx": np.diff(x).tolist(), "dy": np.diff(y).tolist(), "dz": np.diff(z).tolist()}


def decode_geom(g) -> Dict[str, np.ndarray]:
    def col(v0, d):
        return (v0 + np.concatenate([[0], np.cumsum(np.asarray(d, dtype=np.int64))])) / XY_SCALE
    x, y = col(g["x0"], g["dx"]), col(g["y0"], g["dy"])
    s = np.concatenate([[0.0], np.cumsum(np.hypot(np.diff(x), np.diff(y)))])
    return {"x": x, "y": y, "z": col(g["z0"], g["dz"]), "s": s}


def decode_f(df) -> np.ndarray:
    return np.concatenate([[0], np.cumsum(np.asarray(df, dtype=np.int64))]) / F_SCALE


def encode_f(f) -> List[int]:
    q = _ints(f, F_SCALE)
    q[-1] = int(F_SCALE)
    q = np.maximum.accumulate(q)                     # monotone after rounding
    return np.diff(q).tolist()


def build(site: str = "connecting_ridge", driving: str = DRIVING, out: str = OUT, legs_sel=None, log=print) -> Dict:
    from ..terrain import Terrain
    t0 = time.time()
    terrain = Terrain(site)
    with open(os.path.join(terrain.path, "sites.json"), encoding="utf-8") as f:
        sites = json.load(f)
    with open(driving, encoding="utf-8") as f:
        table = json.load(f)
    legs = [l for l in legs_from_sites(sites) if l[0] in table["legs"]]
    missing = sorted(set(table["legs"]) - {l[0] for l in legs})
    if missing:
        raise ValueError(f"legs of {driving} without positions in sites.json: {missing[:5]}")
    if legs_sel is not None:
        legs = [legs[i] for i in legs_sel]
    geoms: List[Dict[str, Any]] = []
    gix: Dict[str, int] = {}
    out_legs: Dict[str, Dict[str, Any]] = {}
    diffs = []
    n_vert = 0
    for name, a, b in legs:
        rec_leg = {}
        for sun in LIGHTING:
            key = light_key(sun)
            r = route_record(terrain, a, b, sun)
            tab = table["legs"][name]["route"].get(key, {}).get("length_m")
            if r is None:
                rec_leg[key] = None
                continue
            g = encode_geom(r)
            h = hashlib.sha1(json.dumps(g, separators=(",", ":")).encode()).hexdigest()
            if h not in gix:
                gix[h] = len(geoms)
                geoms.append(g)
                n_vert += g["n"]
            entry = {"geom": gix[h], "df": encode_f(r["f"]), "length_m": round(r["length_m"], 2),
                     "table_length_m": tab}
            if tab is not None:
                diffs.append(abs(r["length_m"] - tab))
            rec_leg[key] = entry
        out_legs[name] = rec_leg
        log(f"{name:24s} {', '.join(f'{k}: {v['length_m']:.0f} m' if v else f'{k}: -' for k, v in rec_leg.items())}")
    doc = {
        "format": ROUTES_FORMAT, "version": ROUTES_VERSION, "terrain": site,
        "description": __doc__.split("\n\n")[1].strip(),
        "frame": "terrain pack local frame: x east, y north, metres from the tile's south-west corner; z = LOLA height (m)",
        "encoding": {"xy_z_s_unit_m": 1.0 / XY_SCALE, "f_unit": 1.0 / F_SCALE,
                     "geom": "x_k = (x0 + sum(dx[:k])) / 10; y, z the same; n vertices; s_k = sum of the "
                             "horizontal segment lengths of the decoded vertices up to k",
                     "f": "f_k = sum(df[:k]) / 1e4 (0 at the start, 1 at the end)"},
        "max_spacing_m": MAX_SPACING_M, "lighting": [light_key(s) for s in LIGHTING],
        "driving_table": {"file": os.path.basename(driving), "sha256": hashlib.sha256(open(driving, "rb").read()).hexdigest()},
        "speed_model": "time per 5 m segment = ds / (slope_speed_factor * lighting_factor * (1 - slip(grade, phi 42 deg))); "
                       "blocked segments (dig-in) take no time, as in tables.drive_profile",
        "geoms": geoms, "legs": out_legs,
        "checks": {"n_legs": len(out_legs), "n_routes": sum(v is not None for l in out_legs.values() for v in l.values()),
                   "n_geoms": len(geoms), "n_vertices": n_vert,
                   "max_abs_length_diff_vs_table_m": round(max(diffs), 3) if diffs else None},
        "generated": {"tool": "lunarsim/rover/routes.py", "seconds": round(time.time() - t0, 1)},
    }
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(doc, f, separators=(",", ":"))
        log(f"wrote {out}: {os.path.getsize(out) / 2**20:.2f} MB; {doc['checks']}")
    return doc


def validate(doc) -> List[str]:
    """Structural check ([] = valid)."""
    errs = []
    if doc.get("format") != ROUTES_FORMAT or doc.get("version") != ROUTES_VERSION:
        return [f"format/version must be {ROUTES_FORMAT} v{ROUTES_VERSION}"]
    geoms = doc["geoms"]
    for i, g in enumerate(geoms):
        if not all(len(g[k]) == g["n"] - 1 for k in ("dx", "dy", "dz")):
            errs.append(f"geom {i}: delta lengths != n - 1")
            continue
        seg = np.hypot(np.asarray(g["dx"]), np.asarray(g["dy"])) / XY_SCALE
        if seg.max(initial=0) > doc.get("max_spacing_m", MAX_SPACING_M) + 0.15:
            errs.append(f"geom {i}: spacing above max_spacing_m")
    for leg, ls in doc["legs"].items():
        for key, e in ls.items():
            if e is None:
                continue
            g = geoms[e["geom"]] if 0 <= e["geom"] < len(geoms) else None
            if g is None:
                errs.append(f"{leg}/{key}: bad geom index")
                continue
            if len(e["df"]) != g["n"] - 1 or min(e["df"], default=0) < 0 or sum(e["df"]) != int(F_SCALE):
                errs.append(f"{leg}/{key}: df must have n - 1 non-negative entries summing to 1e4")
    return errs


def main(argv=None):
    ap = argparse.ArgumentParser(description="Planned rover routes for the 3D views (lunarsim-routes v1)")
    ap.add_argument("--site", default="connecting_ridge")
    ap.add_argument("--driving", default=DRIVING)
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    doc = build(a.site, a.driving, a.out, log=lambda s: None)
    print(f"wrote {a.out}: {os.path.getsize(a.out) / 2**20:.2f} MB; {doc['checks']}; {doc['generated']['seconds']} s")
    try:
        from .bc import process_memory_mb
        print("memory", process_memory_mb())
    except Exception:
        pass


if __name__ == "__main__":
    main()
