"""R-1 "Earth in sight" data pipeline (B-40): Earth-link windows at our sites and along our rover routes.

    python tools/comms/earth_link.py ephem                 # SPICE: Earth seen from BASE, 2028-2031, 10 min
    python tools/comms/earth_link.py routes [--legs 0-59]  # expert A* route per leg (chunks; cached)
    python tools/comms/earth_link.py points                # sites, pads, mast, route samples every 100 m
    python tools/comms/earth_link.py dem                   # windowed read of the 80 m polar DEM in Earth's wedge
    python tools/comms/earth_link.py masks --part 0 --parts 3   # horizon masks in Earth's wedge (chunks)
    python tools/comms/earth_link.py link                  # link states, windows -> earth_link-v1.json
    python tools/comms/earth_link.py horizons              # cross-check one month at BASE against JPL Horizons
    python tools/comms/earth_link.py avgvisib              # compare with the PDS average Earth-visibility map
    python tools/comms/earth_link.py track                 # hourly Earth track at BASE -> earth_track-v1.json.gz
    python tools/comms/earth_link.py points2               # B-52: + samples on every lighting route (routes-v1)
    python tools/comms/earth_link.py masks2 --part 0 --parts 3  # horizon masks of the new samples (chunks)
    python tools/comms/earth_link.py series2 --part 0 --parts 3 # their hourly windows (chunks)
    python tools/comms/earth_link.py samples2              # -> earth_link-v2-samples.json.gz (v1 file + lit routes)
                                                           #    and -lite.json.gz (any_part only, for the site)
    python tools/comms/earth_link.py ties                  # engine vs routes-v1 night routes -> results/E21_route_ties.json

Intermediate files (kernels, DEM window, routes, masks; ~100 MB) live in ``.cache/comms/`` (git-ignored); the
output ``data/comms/connecting_ridge/earth_link-v1.json`` (format: lunarsim/comms.py) is < 1 MB.

Geometry and conventions:
- Positions: the pack's polar stereographic map (south pole, lon0 = 0, true scale at the pole, R = 1,737.4 km,
  the LOLA MOON_ME sphere). A map point (X, Y) is the unit vector (4RY, 4RX, rho^2 - 4R^2) / (rho^2 + 4R^2),
  i.e. lon = atan2(X, Y), lat = -90 deg + 2 atan(rho / 2R); heights are above the 1,737.4 km sphere.
- Earth: SPICE spkcpo/azlcpo, observer BASE fixed on the Moon, MOON_ME (= MOON_ME_DE440_ME421, the DE421 mean-Earth
  frame of the LOLA products), aberration 'LT+S' (airless apparent direction), 10-min epochs 2028-01-01 00:00 UTC
  to 2031-12-31 23:50 UTC. Other points: the same Earth vector shifted by the point's offset from BASE (exact
  translation; light-time differences are < 1e-7 s), then azimuth/elevation in the point's own local frame.
  Earth's apparent radius = asin(6,378.1366 km / range) (equatorial radius, pck00011).
- Grid bearing = local azimuth (clockwise from local north) + east longitude: the conformal map preserves
  angles, and local north points away from the pole along the meridian.
- Horizon mask: for grid bearings b0 - 12 ... b0 + 12 deg in 0.1 deg steps (b0 = middle of Earth's bearing range
  at BASE), the largest elevation of the terrain seen from the antenna, computed exactly on the sphere
  (asin of the up-component of the unit line of sight; curvature included), along a straight map ray:
  5 m tile (float GeoTIFF) out to 8 km, 80 m LDEM_80S_80MPP_ADJ (PGDA product 90) from 8 to 300 km (and where
  the tile ends earlier). Antenna 2.5 m (rover, at sites, pads and route samples), 10 m (mast at BASE).
- Route samples: the expert A* route of each leg (lunarsim.rover.expert.plan with no lighting term: the
  slope-only route, as costly as the night route), resampled every 100 m and snapped to 20 m post centres
  (dedupes shared corridors); the leg's end points are the site positions themselves. The engine uses these.
  B-52 (points2 ... samples2) adds the same samples along every route of data/driving/routes-v1.json, the five
  lightings; its night route (plan(..., NIGHT): every cost scaled by the shadow factor) is equally long but A*
  breaks the ties between equal-cost paths differently, so on many legs it runs elsewhere.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from lunarsim import comms as C  # noqa: E402

R_MOON_M = 1_737_400.0            # Spec: LOLA reference sphere (PGDA products 78/90; MOON radii in pck00011)
R_EARTH_KM = 6378.1366            # Spec: Earth equatorial radius, pck00011.tpc
START_UTC = "2028-01-01 00:00"
N_DAYS = 1461                     # 2028-01-01 .. 2031-12-31
STEP_MIN = 10
ANT_ROVER_M = 2.5                 # Assumed (B-40): rover antenna height
ANT_MAST_M = 10.0                 # Assumed (B-40): mast at BASE
MAST_RANGE_KM = 10.0              # Assumed (B-40): mast relay range
WEDGE_HALF_DEG = 12.0
WEDGE_STEP_DEG = 0.1
NEAR_MAX_M = 8000.0
FAR_MAX_M = 300000.0
ROUTE_STEP_M = 100.0
SAMPLE_STEP_MIN = 60              # time step of the per-sample windows (earth_link-v1-samples.json)
MARGIN_DEG = {"any_part": None, "centre+0.5deg": 0.5, "centre+2deg": 2.0}
CACHE = os.path.join(ROOT, ".cache", "comms")
KDIR = os.path.join(CACHE, "kernels")
NAIF = "https://naif.jpl.nasa.gov/pub/naif/generic_kernels/"
KERNELS = [("naif0012.tls", "lsk/naif0012.tls"), ("pck00011.tpc", "pck/pck00011.tpc"),
           ("de440s.bsp", "spk/planets/de440s.bsp"), ("moon_pa_de440_200625.bpc", "pck/moon_pa_de440_200625.bpc"),
           ("moon_de440_250416.tf", "fk/satellites/moon_de440_250416.tf")]
FAR_URL = "https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/LDEM_80S_80MPP_ADJ.TIF"
HORIZONS_URL = "https://ssd.jpl.nasa.gov/api/horizons.api"
AVGVISIB_URL = "http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.IMG"
AVGVISIB = {"lines": 5058, "samples": 5058, "scale": 0.00004, "px_m": 60.0, "offset_px": 2528.5}   # its .LBL
HORIZONS_SITE = (222.761, -89.439, 1.958)        # east lon deg, lat deg, km above 1737.4 km (the note's request)
PACK = os.path.join(ROOT, "data", "terrain", "connecting_ridge")
OUT = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1.json")


# ---------------------------------------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------------------------------------
def stereo_unit(X, Y, R: float = R_MOON_M) -> np.ndarray:
    """Unit position vectors (..., 3) in MOON_ME of south polar stereographic map points (metres)."""
    X, Y = np.asarray(X, dtype=np.float64), np.asarray(Y, dtype=np.float64)
    rho2 = X * X + Y * Y
    d = 4 * R * R + rho2
    return np.stack([4 * R * Y / d, 4 * R * X / d, -(4 * R * R - rho2) / d], axis=-1)


def latlon_deg(X, Y, R: float = R_MOON_M) -> Tuple[np.ndarray, np.ndarray]:
    X, Y = np.asarray(X, dtype=np.float64), np.asarray(Y, dtype=np.float64)
    lat = -90.0 + np.degrees(2 * np.arctan(np.hypot(X, Y) / (2 * R)))
    return lat, np.degrees(np.arctan2(X, Y)) % 360.0


def enu(lat_deg: float, lon_deg: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    la, lo = math.radians(lat_deg), math.radians(lon_deg)
    east = np.array([-math.sin(lo), math.cos(lo), 0.0])
    north = np.array([-math.sin(la) * math.cos(lo), -math.sin(la) * math.sin(lo), math.cos(la)])
    up = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)])
    return east, north, up


def wrap180(a):
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


class GridSampler:
    """Bilinear samples of a north-up grid (row 0 = north) in map metres; NaN outside the posts or in no-data."""

    def __init__(self, z: np.ndarray, x_west: float, y_north: float, px: float):
        self.z = np.asarray(z, dtype=np.float32)
        self.x0, self.y0, self.px = float(x_west), float(y_north), float(px)

    def __call__(self, X, Y) -> np.ndarray:
        rows, cols = self.z.shape
        u = (np.asarray(X) - self.x0) / self.px - 0.5
        v = (self.y0 - np.asarray(Y)) / self.px - 0.5
        ok = (u >= 0) & (u <= cols - 1) & (v >= 0) & (v <= rows - 1)
        i0 = np.clip(np.floor(u).astype(np.int64), 0, cols - 2)
        j0 = np.clip(np.floor(v).astype(np.int64), 0, rows - 2)
        fu, fv = u - i0, v - j0
        z = self.z
        out = ((z[j0, i0] * (1 - fu) + z[j0, i0 + 1] * fu) * (1 - fv)
               + (z[j0 + 1, i0] * (1 - fu) + z[j0 + 1, i0 + 1] * fu) * fv)
        return np.where(ok, out, np.nan)


def ray_distances(near_max: float = NEAR_MAX_M, far_max: float = FAR_MAX_M) -> np.ndarray:
    """5 m steps to 1 km, then 0.5 % longer steps (>= 5 m) to near_max, then >= 80 m (0.5 %) to far_max."""
    d, out = 5.0, []
    while d <= far_max + 1e-6:
        out.append(d)
        if d < 1000.0:
            d += 5.0
        elif d < near_max:
            d = max(d * 1.005, d + 5.0)
        else:
            d = max(d * 1.005, d + 80.0)
    return np.array(out)


def horizon_wedge(obs_X, obs_Y, obs_z, h_ant, bearings_deg, near, far=None, distances=None,
                  near_max: float = NEAR_MAX_M, R: float = R_MOON_M) -> np.ndarray:
    """Horizon elevation (deg) per observer (N) and grid bearing (M): max over the ray of the exact elevation of
    the terrain on the sphere seen from h_ant above the observer. `near`/`far` are samplers (map X, Y) -> height;
    `near` is used to near_max and falls back to `far` where it has no data. NaN where no terrain was sampled."""
    oX, oY = np.asarray(obs_X, float), np.asarray(obs_Y, float)
    b = np.radians(np.asarray(bearings_deg, float))
    sb, cb = np.sin(b)[None, :], np.cos(b)[None, :]
    Uo = stereo_unit(oX, oY, R)                                               # (N, 3)
    O = Uo * (R + np.asarray(obs_z, float) + np.asarray(h_ant, float))[:, None]
    best = np.full((len(oX), len(b)), -np.inf)
    for d in (ray_distances(near_max) if distances is None else distances):
        Xs, Ys = oX[:, None] + d * sb, oY[:, None] + d * cb
        if d <= near_max:
            z = near(Xs, Ys)
            if far is not None:
                miss = np.isnan(z)
                if miss.any():
                    z[miss] = far(Xs[miss], Ys[miss])
        elif far is not None:
            z = far(Xs, Ys)
        else:
            break
        if np.all(np.isnan(z)):
            continue
        T = stereo_unit(Xs, Ys, R) * (R + z)[..., None]
        v = T - O[:, None, :]
        s = np.einsum("nmk,nk->nm", v, Uo) / np.linalg.norm(v, axis=-1)
        np.fmax(best, s, out=best)                                            # NaN samples are ignored
    out = np.degrees(np.arcsin(np.clip(best, -1, 1)))
    out[~np.isfinite(best)] = np.nan
    return out


def earth_topo(E_base_km: np.ndarray, P_base_km: np.ndarray, P_km: np.ndarray, lat: float, lon: float):
    """Earth's local azimuth, elevation, grid bearing and apparent radius (deg) from a point, per epoch."""
    E = E_base_km - (P_km - P_base_km)[None, :]
    rng = np.linalg.norm(E, axis=1)
    east, north, up = enu(lat, lon)
    az = np.degrees(np.arctan2(E @ east, E @ north)) % 360.0
    el = np.degrees(np.arcsin(E @ up / rng))
    rad = np.degrees(np.arcsin(R_EARTH_KM / rng))
    return az, el, wrap180(az + lon), rad


def link_state(el, rad, horizon) -> Dict[str, np.ndarray]:
    """Boolean series per criterion; NaN horizon (no terrain) means an open sky (smooth sphere beyond)."""
    h = np.where(np.isnan(horizon), -90.0, horizon)
    out = {}
    for c, m in MARGIN_DEG.items():
        out[c] = (el + rad > h) if m is None else (el > h + m)
    return out


# ---------------------------------------------------------------------------------------------------------
# files and provenance
# ---------------------------------------------------------------------------------------------------------
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def peak_rss_mb() -> Optional[float]:
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from terrain_assets import peak_rss_mb as p
    return p()


def _rel(p: str) -> str:
    try:
        return os.path.relpath(p, ROOT).replace("\\", "/")
    except ValueError:
        return p.replace("\\", "/")


def fetch_kernels() -> List[Dict[str, str]]:
    os.makedirs(KDIR, exist_ok=True)
    out = []
    for name, rel in KERNELS:
        p = os.path.join(KDIR, name)
        if not os.path.isfile(p) or os.path.getsize(p) == 0:
            urllib.request.urlretrieve(NAIF + rel, p)
        out.append({"file": name, "url": NAIF + rel, "sha256": sha256(p)})
    return out


def furnsh_all():
    import spiceypy as sp
    sp.kclear()
    for name, _ in KERNELS:
        sp.furnsh(os.path.join(KDIR, name))
    return sp


def load_pack(pack: str = PACK):
    with open(os.path.join(pack, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(pack, "sites.json"), encoding="utf-8") as f:
        sites = json.load(f)
    return meta, sites


def site_points(sites: Dict) -> Dict[str, Tuple[float, float, str]]:
    """Every engine site (and pad per standoff key) -> (x, y, kind) in local metres."""
    pts = {s["id"]: (float(s["xy_m"][0]), float(s["xy_m"][1]), "site") for s in sites["sites"]}
    for D, pads in (sites.get("pads") or {}).items():
        for pid, xy in pads.items():
            pts[f"{pid}@{D}"] = (float(xy[0]), float(xy[1]), "pad")
    return pts


def near_sampler(meta: Dict) -> Tuple[GridSampler, Dict]:
    """The 5 m tile from the float GeoTIFF (cached by `lunarsim terrain build`), else the pack PNG."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import terrain_assets as ta
    dem = ta.default_dem(meta)
    z, src = ta.load_dem5(PACK, dem, meta)
    x0, y0 = meta["origin_xy_m"]
    return GridSampler(z, x0, y0 + meta["size_m"][1], meta["layers"]["height_5m"]["px_m"]), src


def ephem_path() -> str:
    return os.path.join(CACHE, "ephem.npz")


# ---------------------------------------------------------------------------------------------------------
# pipeline steps
# ---------------------------------------------------------------------------------------------------------
def step_ephem(log=print) -> Dict:
    t0 = time.time()
    kern = fetch_kernels()
    sp = furnsh_all()
    meta, sites = load_pack()
    bx, by = sites["base_xy_m"]
    X, Y = bx + meta["origin_xy_m"][0], by + meta["origin_xy_m"][1]
    near, _ = near_sampler(meta)
    zb = float(near(np.array([X]), np.array([Y]))[0])
    P_base = stereo_unit(X, Y) * (R_MOON_M + zb) / 1000.0                     # km, BASE on the ground
    lat, lon = latlon_deg(X, Y)
    n = N_DAYS * 24 * 60 // STEP_MIN
    et0 = sp.str2et(START_UTC + " UTC")
    ets = et0 + 60.0 * STEP_MIN * np.arange(n)
    E = np.empty((n, 3))
    for i, et in enumerate(ets):
        st, _ = sp.spkcpo("EARTH", float(et), "MOON_ME", "OBSERVER", "LT+S", P_base, "MOON", "MOON_ME")
        E[i] = st[:3]
    az, el, brg, rad = earth_topo(E, P_base, P_base, float(lat), float(lon))
    # azlcpo check (every 97th epoch): the az/el conversion here must equal SPICE's own
    idx = np.arange(0, n, 97)
    d_az, d_el = [], []
    for i in idx:
        st, _ = sp.azlcpo("ELLIPSOID", "EARTH", float(ets[i]), "LT+S", False, True, P_base, "MOON", "MOON_ME")
        d_az.append(abs(wrap180(math.degrees(st[1]) - az[i])))
        d_el.append(abs(math.degrees(st[2]) - el[i]))
    chk = {"epochs": int(len(idx)), "max_abs_az_deg": float(max(d_az)), "max_abs_el_deg": float(max(d_el))}
    np.savez(ephem_path(), et=ets, E_base_km=E, P_base_km=P_base, base_xy_map=np.array([X, Y]), base_z_m=zb,
             base_latlon=np.array([float(lat), float(lon)]))
    lo, hi = float(brg.min()), float(brg.max())
    info = {"n": int(n), "base_lat_lon": [float(lat), float(lon)], "base_z_m": zb, "bearing_range_deg": [lo, hi],
            "el_range_deg": [float(el.min()), float(el.max())], "azlcpo_check": chk, "kernels": kern,
            "seconds": round(time.time() - t0, 1)}
    with open(os.path.join(CACHE, "ephem.json"), "w") as f:
        json.dump(info, f, indent=1)
    log(f"ephem: {n} epochs, BASE lat {float(lat):.4f} lon {float(lon):.3f}, Earth grid bearing {lo:.2f} to {hi:.2f} deg, "
        f"elevation {el.min():.2f} to {el.max():.2f} deg; azlcpo check max |d az| {chk['max_abs_az_deg']:.2e}, "
        f"|d el| {chk['max_abs_el_deg']:.2e} deg ({time.time() - t0:.0f} s)")
    return info


def wedge_bearings() -> Tuple[np.ndarray, float]:
    with open(os.path.join(CACHE, "ephem.json")) as f:
        lo, hi = json.load(f)["bearing_range_deg"]
    b0 = round(0.5 * (lo + hi), 1)
    n = int(round(2 * WEDGE_HALF_DEG / WEDGE_STEP_DEG)) + 1
    return np.round(b0 - WEDGE_HALF_DEG + WEDGE_STEP_DEG * np.arange(n), 4), b0


def step_routes(legs_spec: Optional[str] = None, log=print) -> None:
    from lunarsim.terrain import Terrain
    from lunarsim.rover.expert import plan
    from lunarsim.rover.tables import legs_from_sites
    meta, sites = load_pack()
    t = Terrain(PACK)
    legs = legs_from_sites(sites)
    sel = range(len(legs))
    if legs_spec:
        a, _, b = legs_spec.partition("-")
        sel = range(int(a), min(len(legs), int(b or a) + 1))
    path = os.path.join(CACHE, "routes.json")
    done = json.load(open(path)) if os.path.isfile(path) else {}
    t0 = time.time()
    for i in sel:
        name, a, b = legs[i]
        if name in done:
            continue
        poly = plan(t, a, b, None)
        done[name] = None if poly is None else np.round(poly, 2).tolist()
        with open(path, "w") as f:
            json.dump(done, f)
    log(f"routes: {len(done)}/{len(legs)} legs planned ({time.time() - t0:.0f} s this run)")


def resample(poly: np.ndarray, step: float) -> np.ndarray:
    seg = np.hypot(*np.diff(poly, axis=0).T)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    L = s[-1]
    n = max(1, int(math.ceil(L / step)))
    q = np.linspace(0.0, L, n + 1)
    return np.stack([np.interp(q, s, poly[:, 0]), np.interp(q, s, poly[:, 1])], axis=1)


def cell_of(x: float, y: float) -> Tuple[float, float]:
    """Centre of the 20 m post cell that holds (x, y): route samples snap here (dedupes shared corridors)."""
    return (math.floor(x / 20.0) + 0.5) * 20.0, (math.floor(y / 20.0) + 0.5) * 20.0


def step_points(log=print) -> Dict:
    """Unique observation points: sites, pads, the mast, and route samples snapped to 20 m post centres."""
    from lunarsim.rover.tables import legs_from_sites
    meta, sites = load_pack()
    routes = json.load(open(os.path.join(CACHE, "routes.json")))
    legs = legs_from_sites(sites)
    missing = [n for n, _, _ in legs if n not in routes]
    if missing:
        raise SystemExit(f"{len(missing)} legs have no route yet; run `routes` first")
    near, _ = near_sampler(meta)
    x0, y0 = meta["origin_xy_m"]
    pts: List[Dict[str, Any]] = []
    index: Dict[Any, int] = {}

    def add(key, x, y, kind, h):
        if key in index:
            return index[key]
        z = float(near(np.array([x + x0]), np.array([y + y0]))[0])
        index[key] = len(pts)
        pts.append({"id": key if isinstance(key, str) else None, "x": round(x, 2), "y": round(y, 2), "z": round(z, 3),
                    "h_ant": h, "kind": kind})
        return index[key]

    named = site_points(sites)
    for k, (x, y, kind) in named.items():
        add(k, x, y, kind, ANT_ROVER_M)
    bx, by = sites["base_xy_m"]
    add("BASE_MAST", float(bx), float(by), "mast", ANT_MAST_M)
    xy_to_name = {(round(x, 2), round(y, 2)): k for k, (x, y, _) in named.items()}
    leg_pts: Dict[str, List[int]] = {}
    lengths: Dict[str, float] = {}
    for name, a, b in legs:
        poly = routes[name]
        if poly is None:
            leg_pts[name] = []
            continue
        poly = np.asarray(poly)
        lengths[name] = float(np.hypot(*np.diff(poly, axis=0).T).sum())
        smp = resample(poly, ROUTE_STEP_M)
        ids = []
        for j, (x, y) in enumerate(smp):
            if j in (0, len(smp) - 1):
                ids.append(index[xy_to_name[(round(float(x), 2), round(float(y), 2))]])
            else:
                cx, cy = cell_of(x, y)
                ids.append(add(("cell", cx, cy), cx, cy, "route", ANT_ROVER_M))
        leg_pts[name] = [k for j, k in enumerate(ids) if j == 0 or k != ids[j - 1]]   # route order
    doc = {"points": pts, "legs": leg_pts, "lengths_m": lengths}
    with open(os.path.join(CACHE, "points.json"), "w") as f:
        json.dump(doc, f)
    n_route = sum(p["kind"] == "route" for p in pts)
    log(f"points: {len(pts)} ({len(named)} sites and pads, 1 mast, {n_route} route cells); "
        f"{sum(len(v) for v in leg_pts.values())} leg samples over {len(leg_pts)} legs; "
        f"{sum(v is None for v in routes.values())} legs without a route")
    return doc


def far_window_path() -> str:
    return os.path.join(CACHE, "ldem_80s_80m_window.npz")


def step_dem(log=print) -> Dict:
    """Read the part of LDEM_80S_80MPP_ADJ that every ray can reach (Earth's wedge, out to 300 km)."""
    import rasterio
    from rasterio.windows import from_bounds
    meta, _ = load_pack()
    bearings, b0 = wedge_bearings()
    x0, y0 = meta["origin_xy_m"]
    W, H = meta["size_m"]
    corners = np.array([[x0, y0], [x0 + W, y0], [x0, y0 + H], [x0 + W, y0 + H]])
    b = np.radians([bearings[0], bearings[-1]] + ([0.0] if bearings[0] < 0 < bearings[-1] else []))
    ends = np.concatenate([corners + FAR_MAX_M * np.stack([np.sin(bb), np.cos(bb)])[None, :] for bb in b])
    allp = np.concatenate([corners, ends])
    pad = 160.0
    xmin, ymin = allp.min(axis=0) - pad
    xmax, ymax = allp.max(axis=0) + pad
    t0 = time.time()
    local = os.path.join(CACHE, os.path.basename(FAR_URL))
    # the whole 181 MB file is fetched once (curl -C - resumes): the PGDA server sends ~0.4 MB/s and GDAL's small
    # /vsicurl/ range requests made a windowed remote read take over an hour
    src_path = local if os.path.isfile(local) else "/vsicurl/" + FAR_URL
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".TIF,.tif"):
        with rasterio.open(src_path) as ds:
            L, B, R_, T = ds.bounds
            xmin, ymin, xmax, ymax = max(xmin, L), max(ymin, B), min(xmax, R_), min(ymax, T)
            win = from_bounds(xmin, ymin, xmax, ymax, ds.transform).round_offsets().round_lengths()
            z = ds.read(1, window=win, out_dtype="float32")
            tr = ds.window_transform(win)
            px = ds.res[0]
            size = (ds.width, ds.height)
    np.savez(far_window_path(), z=z, x_west=tr.c, y_north=tr.f, px=px, url=FAR_URL,
             window=np.array([win.col_off, win.row_off, win.width, win.height]))
    info = {"url": FAR_URL, "product": "PGDA product 90 (Barker et al. 2023, PSJ 4:183), LDEM_80S_80MPP_ADJ",
            "doi": "10.60903/gsfcpgda-lola-spole", "full_size_px": list(size),
            "window_px": [int(win.col_off), int(win.row_off), int(win.width), int(win.height)],
            "window_bounds_m": [float(tr.c), float(tr.f - px * z.shape[0]), float(tr.c + px * z.shape[1]), float(tr.f)],
            "sha256_window_float32": hashlib.sha256(z.tobytes()).hexdigest(), "seconds": round(time.time() - t0, 1),
            "file_sha256": sha256(local) if src_path == local else None,
            "nan_share": float(np.isnan(z).mean())}
    # datum check: the 80 m DEM against the 5 m tile at the tile's 20 m posts
    near, _ = near_sampler(meta)
    far = GridSampler(z, tr.c, tr.f, px)
    c = (np.arange(40, 800, 40) + 0.5) * 20.0
    gx, gy = np.meshgrid(c + x0, c + y0)
    dz = (far(gx, gy) - near(gx, gy)).ravel()
    dz = dz[np.isfinite(dz)]
    info["datum_check_far_minus_near_m"] = {"mean": float(dz.mean()), "rms": float(np.sqrt((dz ** 2).mean())),
                                            "p95_abs": float(np.percentile(np.abs(dz), 95)), "n": int(dz.size)}
    with open(os.path.join(CACHE, "dem.json"), "w") as f:
        json.dump(info, f, indent=1)
    log(f"dem: window {z.shape[1]} x {z.shape[0]} px ({z.nbytes / 2**20:.0f} MB) in {time.time() - t0:.0f} s; "
        f"far - near: mean {dz.mean():+.2f} m, rms {info['datum_check_far_minus_near_m']['rms']:.2f} m")
    return info


def far_sampler() -> GridSampler:
    d = np.load(far_window_path())
    return GridSampler(d["z"], float(d["x_west"]), float(d["y_north"]), float(d["px"]))


def step_masks(part: int = 0, parts: int = 1, batch: int = 250, log=print) -> None:
    meta, _ = load_pack()
    doc = json.load(open(os.path.join(CACHE, "points.json")))
    pts = doc["points"]
    bearings, b0 = wedge_bearings()
    near, _ = near_sampler(meta)
    far = far_sampler()
    x0, y0 = meta["origin_xy_m"]
    idx = np.array_split(np.arange(len(pts)), parts)[part]
    out = np.full((len(idx), len(bearings)), np.nan, dtype=np.float32)
    t0 = time.time()
    for k in range(0, len(idx), batch):
        sl = idx[k:k + batch]
        P = [pts[i] for i in sl]
        out[k:k + len(sl)] = horizon_wedge(np.array([p["x"] + x0 for p in P]), np.array([p["y"] + y0 for p in P]),
                                           np.array([p["z"] for p in P]), np.array([p["h_ant"] for p in P]),
                                           bearings, near, far)
        log(f"masks part {part}/{parts}: {k + len(sl)}/{len(idx)} points ({time.time() - t0:.0f} s)")
    np.savez(os.path.join(CACHE, f"masks_{part:02d}of{parts:02d}.npz"), idx=idx, mask=out, bearings=bearings)


def load_masks() -> Tuple[np.ndarray, np.ndarray]:
    doc = json.load(open(os.path.join(CACHE, "points.json")))
    n = len(doc["points"])
    files = sorted(f for f in os.listdir(CACHE) if f.startswith("masks_") and f.endswith(".npz"))
    if not files:
        raise SystemExit("no masks yet; run `masks` first")
    parts = {int(f.split("of")[1][:2]) for f in files}
    if len(parts) != 1:
        raise SystemExit(f"mask files from different --parts runs: {files}; delete the stale ones")
    M = None
    bearings = None
    for f in files:
        d = np.load(os.path.join(CACHE, f))
        if M is None:
            bearings = d["bearings"]
            M = np.full((n, len(bearings)), np.nan, dtype=np.float32)
        M[d["idx"]] = d["mask"]
    have = np.isfinite(M).any(axis=1)
    if not have.all():
        raise SystemExit(f"{(~have).sum()} points have no mask; run the missing --part chunks")
    return M, bearings


def point_link(p: Dict, mask_row: np.ndarray, E: np.ndarray, P_base: np.ndarray, x0: float, y0: float,
               bearings: np.ndarray, label: Any = "") -> Dict[str, np.ndarray]:
    """10-min direct link states of one observation point (its antenna on the terrain) for every criterion."""
    X, Y = p["x"] + x0, p["y"] + y0
    lat, lon = latlon_deg(X, Y)
    P = stereo_unit(X, Y) * (R_MOON_M + p["z"] + p["h_ant"]) / 1000.0
    _, el, brg, rad = earth_topo(E, P_base, P, float(lat), float(lon))
    if brg.min() < bearings[0] or brg.max() > bearings[-1]:
        raise ValueError(f"point {label}: Earth bearing {brg.min():.2f}..{brg.max():.2f} leaves the mask wedge")
    return link_state(el, rad, np.interp(brg, bearings, mask_row))


def sees_mast(terrain, p: Dict, bx: float, by: float) -> bool:
    """Line of sight from a 2.5 m antenna at p to the 10 m mast at BASE, within the mast's range."""
    d_km = math.hypot(p["x"] - bx, p["y"] - by) / 1000.0
    if d_km > MAST_RANGE_KM:
        return False
    return d_km < 0.01 or terrain.los_clearance_m((p["x"], p["y"]), (bx, by), h_a=ANT_ROVER_M, h_b=ANT_MAST_M) >= 0


def step_link(out: str = OUT, log=print) -> Dict:
    from lunarsim.terrain import Terrain
    t0 = time.time()
    meta, sites = load_pack()
    pdoc = json.load(open(os.path.join(CACHE, "points.json")))
    pts, leg_pts = pdoc["points"], pdoc["legs"]
    M, bearings = load_masks()
    e = np.load(ephem_path())
    E, P_base = e["E_base_km"], e["P_base_km"]
    n = len(E)
    step_h = STEP_MIN / 60.0
    x0, y0 = meta["origin_xy_m"]
    terrain = Terrain(PACK)
    bx, by = sites["base_xy_m"]

    def series(i):
        return point_link(pts[i], M[i], E, P_base, x0, y0, bearings, i)

    mast_i = next(i for i, p in enumerate(pts) if p["id"] == "BASE_MAST")
    mast = series(mast_i)
    los = np.zeros(len(pts), dtype=bool)
    dist = np.zeros(len(pts))
    for i, p in enumerate(pts):
        dist[i] = math.hypot(p["x"] - bx, p["y"] - by) / 1000.0
        if i != mast_i:
            los[i] = sees_mast(terrain, p, bx, by)
    enc = lambda m: C.encode_windows(C.runs(m))

    def pack(direct, with_mast):
        return ({"dte": {c: enc(direct[c]) for c in C.CRITERIA}, "dte+mast": {c: enc(with_mast[c]) for c in C.CRITERIA}},
                {"dte": {c: C.summarize(C.runs(direct[c]), n, step_h) for c in C.CRITERIA},
                 "dte+mast": {c: C.summarize(C.runs(with_mast[c]), n, step_h) for c in C.CRITERIA}})

    points_out = {}
    for i, p in enumerate(pts):
        if p["kind"] not in ("site", "pad"):
            continue
        s = series(i)
        sm = {c: s[c] | (los[i] & mast[c]) for c in C.CRITERIA}
        w, summ = pack(s, sm)
        lat, lon = latlon_deg(p["x"] + x0, p["y"] + y0)
        points_out[p["id"]] = {"kind": p["kind"], "xy_m": [p["x"], p["y"]], "z_m": p["z"],
                               "lat_deg": round(float(lat), 5), "lon_deg": round(float(lon), 4),
                               "antenna_m": p["h_ant"], "mast_los": bool(los[i]), "dist_mast_km": round(dist[i], 3),
                               "horizon_at_mean_bearing_deg": round(float(np.interp(0.5 * (bearings[0] + bearings[-1]),
                                                                                    bearings, M[i])), 3),
                               "windows": w, "summary": summ}
    # every route sample once: direct windows per criterion (the mast mode is derived from these, mast_los and the
    # mast's windows, here and in the engine)
    pt_win: Dict[int, Dict[str, List[int]]] = {}
    pt_hour: Dict[int, Dict[str, List[int]]] = {}
    k_h = SAMPLE_STEP_MIN // STEP_MIN
    for i in sorted({k for ids in leg_pts.values() for k in ids}):
        s = series(i)
        pt_win[i] = {c: enc(s[c]) for c in C.CRITERIA}
        # hourly sample series: an hour counts as linked only when all of its 10-min epochs are (conservative)
        pt_hour[i] = {c: enc(s[c][: n - n % k_h].reshape(-1, k_h).all(axis=1)) for c in C.CRITERIA}
    mask_of = lambda code: C.windows_to_mask(C.decode_windows(code), n)
    legs_out = {}
    for name, ids in leg_pts.items():
        if not ids:
            legs_out[name] = {"route": None}
            continue
        acc = {c: np.ones(n, dtype=bool) for c in C.CRITERIA}
        accm = {c: np.ones(n, dtype=bool) for c in C.CRITERIA}
        for i in ids:
            for c in C.CRITERIA:
                m_ = mask_of(pt_win[i][c])
                acc[c] &= m_
                accm[c] &= m_ | (los[i] & mast[c])
        w, summ = pack(acc, accm)
        legs_out[name] = {"length_m": round(pdoc["lengths_m"][name], 1), "n_samples": len(ids),
                          "mast_los_share": round(float(los[ids].mean()), 3), "windows": w, "summary": summ}
    # per-sample windows (for interventions that wait for the link at their own position): deduplicated series
    series_ix: Dict[Tuple[int, ...], int] = {}
    series_list: List[List[int]] = []

    def sid(code):
        key = tuple(code)
        if key not in series_ix:
            series_ix[key] = len(series_list)
            series_list.append(code)
        return series_ix[key]

    used = sorted(pt_win)
    new_ix = {i: k for k, i in enumerate(used)}
    samples_doc = {
        "format": C.EARTH_LINK_SAMPLES_FORMAT, "version": C.EARTH_LINK_VERSION, "terrain": meta["site_id"],
        "time": {"start_utc": START_UTC, "step_min": SAMPLE_STEP_MIN, "n": int(n // k_h)},
        "criteria": list(C.CRITERIA),
        "samples": [{"xy_m": [pts[i]["x"], pts[i]["y"]], "id": pts[i]["id"], "mast_los": bool(los[i]),
                     "w": [sid(pt_hour[i][c]) for c in C.CRITERIA]} for i in used],
        "series": series_list,
        "legs": {name: [new_ix[i] for i in ids] for name, ids in leg_pts.items()},
        "note": "sample windows are direct (dte), hourly: an hour is linked only when all six 10-min epochs are; with the mast a sample is also linked when mast_los and the mast "
                "(earth_link-v1.json 'mast') is linked; legs list their samples in route order, end points included",
    }
    samples_path = os.path.join(os.path.dirname(out), "earth_link-v1-samples.json.gz")
    ephem = json.load(open(os.path.join(CACHE, "ephem.json")))
    dem = json.load(open(os.path.join(CACHE, "dem.json")))
    hz = os.path.join(CACHE, "horizons_check.json")
    av = os.path.join(CACHE, "avgvisib_check.json")
    _, nsrc = near_sampler(meta)
    doc = {
        "format": C.EARTH_LINK_FORMAT, "version": C.EARTH_LINK_VERSION, "terrain": meta["site_id"],
        "time": {"start_utc": START_UTC, "step_min": STEP_MIN, "n": int(n), "scale": "UTC",
                 "end_utc_exclusive": "2032-01-01 00:00"},
        "criteria": {"any_part": "elevation + apparent radius > horizon (upper limb visible)",
                     "centre+0.5deg": "elevation > horizon + 0.5 deg", "centre+2deg": "elevation > horizon + 2 deg"},
        "modes": {"dte": f"direct to Earth from a {ANT_ROVER_M} m rover antenna",
                  "dte+mast": f"direct, or line of sight to a {ANT_MAST_M} m mast at BASE within {MAST_RANGE_KM} km "
                              "while the mast sees Earth (same criterion)"},
        "windows_encoding": "[s0, l0, g1, l1, ...] epoch indices: start0 = s0, end0 = start0 + l0 (exclusive), "
                            "start1 = end0 + g1, ...",
        "antenna_m": {"rover": ANT_ROVER_M, "mast": ANT_MAST_M, "flag": "Assumed (B-40 task)"},
        "mast": {"site": "BASE", "height_m": ANT_MAST_M, "range_km": MAST_RANGE_KM,
                 "windows": {c: enc(mast[c]) for c in C.CRITERIA},
                 "summary": {c: C.summarize(C.runs(mast[c]), n, step_h) for c in C.CRITERIA}},
        "earth": {"grid_bearing_range_deg_at_BASE": ephem["bearing_range_deg"],
                  "elevation_range_deg_at_BASE": ephem["el_range_deg"],
                  "mask_wedge_deg": [float(bearings[0]), float(bearings[-1]), WEDGE_STEP_DEG]},
        "points": points_out, "legs": legs_out,
        "provenance": {
            "kernels": ephem["kernels"], "frame": "MOON_ME (= MOON_ME_DE440_ME421)", "aberration": "LT+S",
            "spice_conversion_check": ephem["azlcpo_check"],
            "near_dem": nsrc, "far_dem": {k: v for k, v in dem.items() if k != "seconds"},
            "routes": "lunarsim.rover.expert.plan(terrain, a, b, sun_az_deg=None) per leg of "
                      "lunarsim.rover.tables.legs_from_sites; samples every 100 m snapped to 20 m post centres",
            "mast_los": "lunarsim.terrain.Terrain.los_clearance_m(point, BASE, h_a=2.5, h_b=10) >= 0 within 10 km",
            "horizons_check": json.load(open(hz)) if os.path.isfile(hz) else None,
            "avgvisib_check": json.load(open(av)) if os.path.isfile(av) else None,
            "earth_radius_km": R_EARTH_KM, "moon_radius_m": R_MOON_M,
            "outside_80S": "terrain beyond the 80 deg S DEM edge (303 km from the pole) is not included",
        },
        "generated": {"tool": "tools/comms/earth_link.py", "commit": _git_sha(),
                      "time": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()},
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    import gzip
    with open(samples_path, "wb") as f:                       # deterministic gzip (no name, mtime 0)
        f.write(gzip.compress(json.dumps(samples_doc, separators=(",", ":")).encode("utf-8"), 9, mtime=0))
    doc["samples_file"] = {"file": os.path.basename(samples_path), "sha256": sha256(samples_path),
                           "n_samples": len(used), "n_series": len(series_list)}
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    with open(out + ".sha256", "w") as f:
        f.write(f"{sha256(out)}  {os.path.basename(out)}\n")
    rss = peak_rss_mb()
    log(f"samples: {len(used)} samples, {len(series_list)} distinct series -> {_rel(samples_path)} "
        f"({os.path.getsize(samples_path) / 1024:.0f} KB)")
    log(f"link: {len(points_out)} points, {len(legs_out)} legs -> {_rel(out)} ({os.path.getsize(out) / 1024:.0f} KB) "
        f"in {time.time() - t0:.0f} s" + (f"; peak RSS {rss:.0f} MB" if rss else ""))
    return doc


# ---------------------------------------------------------------------------------------------------------
# B-52: samples along every lighting route of routes-v1.json -> earth_link-v2-samples.json.gz
# ---------------------------------------------------------------------------------------------------------
ROUTES_V1 = os.path.join(ROOT, "data", "driving", "routes-v1.json")
LIGHTS = ("0", "90", "180", "270", "night")
SAMPLES_V1 = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1-samples.json.gz")
SAMPLES_V2 = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v2-samples.json.gz")


def route_ids(poly: np.ndarray, a_id: int, b_id: int, add) -> List[int]:
    """Point ids of one route in route order: samples every ROUTE_STEP_M, the end points the leg's sites, the
    others snapped to 20 m cells (add(cx, cy) -> id); consecutive repeats dropped (the rule of step_points)."""
    smp = resample(np.asarray(poly, float), ROUTE_STEP_M)
    ids = [a_id if j == 0 else b_id if j == len(smp) - 1 else add(*cell_of(x, y)) for j, (x, y) in enumerate(smp)]
    return [k for j, k in enumerate(ids) if j == 0 or k != ids[j - 1]]


def step_points2(routes_file: str = ROUTES_V1, log=print) -> Dict:
    """The v1 points (indices kept) plus the new 20 m cells of the routes of routes-v1.json; per leg and lighting
    the point ids in route order. The night case follows routes-v1's night route too: it is as long as the B-40
    route (plan(..., None)) the engine uses, but A* breaks the ties between equal-cost paths differently when every
    cost is scaled by the shadow factor (plan(..., NIGHT)), so on many legs it runs elsewhere; those legs are listed."""
    from lunarsim.rover.routes import decode_geom
    meta, _ = load_pack()
    v1 = json.load(open(os.path.join(CACHE, "points.json")))
    rdoc = json.load(open(routes_file))
    near, _ = near_sampler(meta)
    x0, y0 = meta["origin_xy_m"]
    pts = [dict(p) for p in v1["points"]]
    index = {(p["id"] if p["id"] is not None else ("cell", p["x"], p["y"])): i for i, p in enumerate(pts)}

    def add(cx, cy):
        key = ("cell", cx, cy)
        if key not in index:
            z = float(near(np.array([cx + x0]), np.array([cy + y0]))[0])
            index[key] = len(pts)
            pts.append({"id": None, "x": round(cx, 2), "y": round(cy, 2), "z": round(z, 3), "h_ant": ANT_ROVER_M,
                        "kind": "route"})
        return index[key]

    routes: Dict[str, Dict[str, List[int]]] = {}
    lengths: Dict[str, Dict[str, float]] = {}
    night_diff: List[str] = []
    for leg, per in rdoc["legs"].items():
        a, b = leg.split("->")
        routes[leg], lengths[leg] = {}, {}
        for L in LIGHTS:
            e = per.get(L)
            ids = []
            if e is not None:
                g = decode_geom(rdoc["geoms"][e["geom"]])
                ids = route_ids(np.stack([g["x"], g["y"]], axis=1), index[a], index[b], add)
                lengths[leg][L] = round(float(g["s"][-1]), 1)
            if L == "night" and ids != v1["legs"].get(leg, []):
                night_diff.append(leg)
            routes[leg][L] = ids
    n_new = len(pts) - len(v1["points"])
    doc = {"n_v1": len(v1["points"]), "points": pts, "routes": routes, "lengths_m": lengths,
           "routes_file": {"file": os.path.relpath(routes_file, ROOT).replace(os.sep, "/"), "sha256": sha256(routes_file)},
           "night_legs_off_v1": night_diff}
    with open(os.path.join(CACHE, "points2.json"), "w") as f:
        json.dump(doc, f)
    n_routes = sum(bool(v) for per in routes.values() for v in per.values())
    log(f"points2: {len(pts)} points ({n_new} new cells); {n_routes} routes over {len(routes)} legs; "
        f"the routes-v1 night samples differ from the engine's v1 list on {len(night_diff)} legs")
    return doc


def step_masks2(part: int = 0, parts: int = 1, batch: int = 250, log=print) -> None:
    """Horizon masks of the new points of points2.json only (the v1 points keep their masks_*.npz)."""
    meta, _ = load_pack()
    doc = json.load(open(os.path.join(CACHE, "points2.json")))
    pts, n1 = doc["points"], doc["n_v1"]
    bearings, _ = wedge_bearings()
    near, _ = near_sampler(meta)
    far = far_sampler()
    x0, y0 = meta["origin_xy_m"]
    idx = np.array_split(np.arange(n1, len(pts)), parts)[part]
    out = np.full((len(idx), len(bearings)), np.nan, dtype=np.float32)
    t0 = time.time()
    for k in range(0, len(idx), batch):
        sl = idx[k:k + batch]
        P = [pts[i] for i in sl]
        out[k:k + len(sl)] = horizon_wedge(np.array([p["x"] + x0 for p in P]), np.array([p["y"] + y0 for p in P]),
                                           np.array([p["z"] for p in P]), np.array([p["h_ant"] for p in P]),
                                           bearings, near, far)
        log(f"masks2 part {part}/{parts}: {k + len(sl)}/{len(idx)} points ({time.time() - t0:.0f} s)")
    np.savez(os.path.join(CACHE, f"masks2_{part:02d}of{parts:02d}.npz"), idx=idx, mask=out, bearings=bearings)


def load_masks2() -> Tuple[np.ndarray, np.ndarray]:
    doc = json.load(open(os.path.join(CACHE, "points2.json")))
    M1, bearings = load_masks()
    n1, n = doc["n_v1"], len(doc["points"])
    if len(M1) != n1:
        raise SystemExit("points.json changed since points2; rerun points2")
    M = np.full((n, len(bearings)), np.nan, dtype=np.float32)
    M[:n1] = M1
    files = sorted(f for f in os.listdir(CACHE) if f.startswith("masks2_") and f.endswith(".npz"))
    if len({int(f.split("of")[1][:2]) for f in files}) > 1:
        raise SystemExit(f"masks2 files from different --parts runs: {files}; delete the stale ones")
    for f in files:
        d = np.load(os.path.join(CACHE, f))
        if not np.array_equal(d["bearings"], bearings):
            raise SystemExit(f"{f}: mask bearings differ from the v1 masks")
        M[d["idx"]] = d["mask"]
    miss = ~np.isfinite(M).any(axis=1)
    if miss.any():
        raise SystemExit(f"{int(miss.sum())} points have no mask; run the missing `masks2 --part` chunks")
    return M, bearings


def _v2_used(doc: Dict, v1s: Dict) -> Tuple[List[int], List[int]]:
    """(v1 point ids of the v1 samples in v1 sample order, new point ids in sorted order) of points2.json."""
    v1_pts = json.load(open(os.path.join(CACHE, "points.json")))
    used_v1 = sorted({k for ids in v1_pts["legs"].values() for k in ids})
    if len(used_v1) != len(v1s["samples"]):
        raise SystemExit("the v1 samples file does not match points.json")
    have = set(used_v1)
    new = sorted({k for per in doc["routes"].values() for ids in per.values() for k in ids} - have)
    return used_v1, new


def step_series2(part: int = 0, parts: int = 1, log=print) -> None:
    """Hourly direct windows (and mast line of sight) of the new samples, one chunk of them (cached)."""
    import gzip
    from lunarsim.terrain import Terrain
    t0 = time.time()
    meta, sites = load_pack()
    doc = json.load(open(os.path.join(CACHE, "points2.json")))
    v1s = json.loads(gzip.decompress(open(SAMPLES_V1, "rb").read()))
    _, new = _v2_used(doc, v1s)
    sel = np.array_split(np.array(new, dtype=int), parts)[part]
    M, bearings = load_masks2()
    e = np.load(ephem_path())
    E, P_base = e["E_base_km"], e["P_base_km"]
    n, k_h = len(E), SAMPLE_STEP_MIN // STEP_MIN
    x0, y0 = meta["origin_xy_m"]
    terrain = Terrain(PACK)
    bx, by = sites["base_xy_m"]
    out = {}
    for j, i in enumerate(sel.tolist()):
        p = doc["points"][i]
        s = point_link(p, M[i], E, P_base, x0, y0, bearings, i)
        out[str(i)] = {"mast_los": sees_mast(terrain, p, bx, by),
                       "w": [C.encode_windows(C.runs(s[c][: n - n % k_h].reshape(-1, k_h).all(axis=1)))
                             for c in C.CRITERIA]}
        if (j + 1) % 250 == 0:
            log(f"series2 part {part}/{parts}: {j + 1}/{len(sel)} samples ({time.time() - t0:.0f} s)")
    with open(os.path.join(CACHE, f"series2_{part:02d}of{parts:02d}.json"), "w") as f:
        json.dump(out, f)
    log(f"series2 part {part}/{parts}: {len(sel)} samples in {time.time() - t0:.0f} s")


def step_samples2(out: str = SAMPLES_V2, recheck: int = 40, log=print) -> Dict:
    """Assemble earth_link-v2-samples.json.gz: the v1 samples file unchanged as a prefix (samples, series, legs),
    the new samples appended, and per leg and lighting the sample ids of its route. `recheck` v1 samples are
    recomputed and must reproduce their v1 series exactly."""
    import gzip
    from lunarsim.terrain import Terrain
    t0 = time.time()
    meta, sites = load_pack()
    doc = json.load(open(os.path.join(CACHE, "points2.json")))
    v1s = json.loads(gzip.decompress(open(SAMPLES_V1, "rb").read()))
    used_v1, new = _v2_used(doc, v1s)
    got: Dict[str, Any] = {}
    files = sorted(f for f in os.listdir(CACHE) if f.startswith("series2_") and f.endswith(".json"))
    if len({int(f.split("of")[1][:2]) for f in files}) > 1:
        raise SystemExit(f"series2 files from different --parts runs: {files}; delete the stale ones")
    for f in files:
        got.update(json.load(open(os.path.join(CACHE, f))))
    miss = [i for i in new if str(i) not in got]
    if miss:
        raise SystemExit(f"{len(miss)} new samples have no series; run the missing `series2 --part` chunks")
    # determinism check: a few v1 samples recomputed with the same code reproduce their v1 hourly series
    pts = doc["points"]
    if recheck:
        M, bearings = load_masks2()
        e = np.load(ephem_path())
        E, P_base = e["E_base_km"], e["P_base_km"]
        n, k_h = len(E), SAMPLE_STEP_MIN // STEP_MIN
        x0, y0 = meta["origin_xy_m"]
        terrain = Terrain(PACK)
        bx, by = sites["base_xy_m"]
        rng = np.random.default_rng(52)
        for j in sorted(rng.choice(len(used_v1), size=min(recheck, len(used_v1)), replace=False).tolist()):
            i, rec = used_v1[j], v1s["samples"][j]
            s = point_link(pts[i], M[i], E, P_base, x0, y0, bearings, i)
            w = [C.encode_windows(C.runs(s[c][: n - n % k_h].reshape(-1, k_h).all(axis=1))) for c in C.CRITERIA]
            if w != [v1s["series"][k] for k in rec["w"]] or sees_mast(terrain, pts[i], bx, by) != rec["mast_los"]:
                raise SystemExit(f"v1 sample {j} (point {i}) does not reproduce its v1 series")
        log(f"samples2: {min(recheck, len(used_v1))} v1 samples recomputed, identical")
    series_list = [list(c) for c in v1s["series"]]
    series_ix = {tuple(c): k for k, c in reversed(list(enumerate(series_list)))}

    def sid(code):
        key = tuple(code)
        if key not in series_ix:
            series_ix[key] = len(series_list)
            series_list.append(list(code))
        return series_ix[key]

    samples = [dict(s) for s in v1s["samples"]]
    for i in new:
        r = got[str(i)]
        samples.append({"xy_m": [pts[i]["x"], pts[i]["y"]], "id": pts[i]["id"], "mast_los": bool(r["mast_los"]),
                        "w": [sid(c) for c in r["w"]]})
    new_ix = {i: k for k, i in enumerate(used_v1 + new)}
    routes = {leg: {L: [new_ix[i] for i in per[L]] for L in LIGHTS} for leg, per in doc["routes"].items()}
    sdoc = {
        "format": C.EARTH_LINK_SAMPLES_FORMAT, "version": 2, "terrain": meta["site_id"],
        "time": v1s["time"], "criteria": v1s["criteria"],
        "lighting": list(LIGHTS),
        "samples": samples, "series": series_list,
        "legs": v1s["legs"],
        "routes": routes,
        "lengths_m": doc["lengths_m"],
        "v1_prefix": {"file": os.path.basename(SAMPLES_V1), "sha256": sha256(SAMPLES_V1),
                      "n_samples": len(v1s["samples"]), "n_series": len(v1s["series"])},
        "routes_file": doc["routes_file"],
        "night_legs_off_v1": doc["night_legs_off_v1"],
        "note": "version 2 = the v1 samples file (samples, series and legs unchanged, so v1 sample ids stay valid) plus "
                "the samples of every route of routes-v1.json (B-32): routes[leg][lighting] lists sample ids in route "
                "order, end points included ([] when the leg has no route in that lighting). legs[leg] is the "
                "engine's list (B-40 route, plan(..., None)); routes[leg]['night'] follows routes-v1's night route "
                "(plan(..., NIGHT)), equally long but a different tie between equal-cost paths on the legs in "
                "night_legs_off_v1. Samples every 100 m along the route, snapped to 20 m post centres; windows direct "
                "(dte), hourly, an hour linked only when all six 10-min epochs are; mast_los as in v1. The engine "
                "reads the v1 file.",
        "generated": {"tool": "tools/comms/earth_link.py points2 / masks2 / series2 / samples2"},
    }
    lite_out = out.replace(".json.gz", "-lite.json.gz")
    for path, d in ((out, sdoc), (lite_out, lite_samples(sdoc))):
        with open(path, "wb") as f:                           # deterministic gzip (no name, mtime 0)
            f.write(gzip.compress(json.dumps(d, separators=(",", ":")).encode("utf-8"), 9, mtime=0))
    log(f"samples2: {len(samples)} samples ({len(new)} new), {len(series_list)} distinct series "
        f"({len(series_list) - len(v1s['series'])} new) -> {_rel(out)} ({os.path.getsize(out) / 1024:.0f} KB), "
        f"lite {_rel(lite_out)} ({os.path.getsize(lite_out) / 1024:.0f} KB) in {time.time() - t0:.0f} s")
    return sdoc


def lite_samples(sdoc: Dict) -> Dict:
    """The site's copy: the first criterion (any_part) only; sample ids, legs and routes unchanged."""
    used = sorted({s["w"][0] for s in sdoc["samples"]})
    remap = {k: j for j, k in enumerate(used)}
    lite = dict(sdoc, criteria=sdoc["criteria"][:1], series=[sdoc["series"][k] for k in used],
                samples=[dict(s, w=[remap[s["w"][0]]]) for s in sdoc["samples"]])
    lite["variant"] = "lite: criterion any_part only (series re-indexed; sample ids, legs and routes as in the full file)"
    lite.pop("v1_prefix")
    return lite


TIES_OUT = os.path.join(ROOT, "results", "E21_route_ties.json")


def leg_linked_hours(sdoc: Dict, ids: Sequence[int], crit: int = 0) -> int:
    """Hours of the sample series in which every listed sample is linked (direct, criterion index crit)."""
    n = int(sdoc["time"]["n"])
    m = np.ones(n, dtype=bool)
    for i in ids:
        m &= C.windows_to_mask(C.decode_windows(sdoc["series"][sdoc["samples"][i]["w"][crit]]), n)
    return int(m.sum())


def route_tie_linked(sdoc: Dict) -> Dict[str, Any]:
    """Engine night lists (legs) against the routes-v1 night lists: share of hours with every sample linked
    (any_part), per leg; differences in percentage points. Integer counts, so the same on every machine."""
    n = int(sdoc["time"]["n"])
    rows = []
    for leg, ids in sdoc["legs"].items():
        alt = sdoc["routes"][leg]["night"]
        if not ids or not alt:
            continue
        a, b = leg_linked_hours(sdoc, ids), leg_linked_hours(sdoc, alt)
        rows.append((abs(a - b), leg, a, b))
    rows.sort(key=lambda r: (-r[0], r[1]))
    d_pp = np.array([100.0 * r[0] / n for r in rows])
    top = rows[0]
    return {"definition": "share of the hours 2028-2031 in which every 100 m route sample of the leg sees Earth "
                          "(direct, any part of the disc, hourly samples of earth_link-v2-samples.json.gz)",
            "legs": len(rows), "max_abs_diff_pp": round(float(d_pp.max()), 2), "max_leg": top[1],
            "max_leg_share_engine": round(top[2] / n, 4), "max_leg_share_routes_v1": round(top[3] / n, 4),
            "median_abs_diff_pp": round(float(np.median(d_pp)), 2),
            "legs_gt_1pp": int((d_pp > 1.0).sum()), "legs_gt_5pp": int((d_pp > 5.0).sum())}


def step_ties(out: str = TIES_OUT, log=print) -> Dict:
    """E21_route_ties.json: the engine's night routes (B-40, plan(..., None)) against the routes-v1 night routes
    (plan(..., NIGHT)) - geometry, length and the leg link share - for the paper's limitation sentence."""
    import gzip
    from scipy.spatial import cKDTree
    from lunarsim.rover.routes import decode_geom
    old = json.load(open(os.path.join(CACHE, "routes.json")))
    rdoc = json.load(open(ROUTES_V1))
    sdoc = json.loads(gzip.decompress(open(SAMPLES_V2, "rb").read()))
    hd, dl = {}, {}
    for leg, per in rdoc["legs"].items():
        e = per.get("night")
        if e is None or old.get(leg) is None:
            continue
        g = decode_geom(rdoc["geoms"][e["geom"]])
        P, Q = np.asarray(old[leg], float), np.stack([g["x"], g["y"]], axis=1)
        Pd, Qd = resample(P, 1.0), resample(Q, 1.0)
        hd[leg] = float(max(cKDTree(Qd).query(Pd)[0].max(), cKDTree(Pd).query(Qd)[0].max()))
        dl[leg] = abs(float(np.hypot(*np.diff(P, axis=0).T).sum()) - float(g["s"][-1]))
    h = np.array(list(hd.values()))
    h_leg = max(hd, key=lambda k: (hd[k], k))
    l_leg = max(dl, key=lambda k: (dl[k], k))
    off = set(sdoc["night_legs_off_v1"])
    doc = {
        "description": "E21's rover routes for the Earth link (B-40: lunarsim.rover.expert.plan(terrain, a, b, None), the "
                       "slope-only route) against the night routes of the driving tables and data/driving/routes-v1.json "
                       "(plan(..., 'night')). Both are optimal and equally long; they differ in which of several "
                       "equal-cost paths A* returns.",
        "cause": "the night cost grid multiplies every cell cost by 1/SHADOW_SPEED_FACTOR while the A* heuristic "
                 "(straight-line distance x 1 s/m) stays unscaled, so the search breaks ties between equal-cost paths "
                 "differently",
        "legs_compared": len(hd),
        "geometry": {"metric": "symmetric Hausdorff distance (m) between the two polylines, each resampled at 1 m",
                     "legs_differing_gt_2m": int((h > 2.0).sum()), "legs_differing_gt_20m": int((h > 20.0).sum()),
                     "max_m": round(float(h.max()), 1), "max_leg": h_leg, "median_m": round(float(np.median(h)), 1)},
        "length": {"max_abs_diff_m": round(max(dl.values()), 3), "max_leg": l_leg,
                   "note": "routes-v1 stores positions in decimetres"},
        "linked_share": route_tie_linked(sdoc),
        "sample_lists_differing": len(off),
        "sources": {"engine_routes": ".cache/comms/routes.json (tools/comms/earth_link.py routes; git-ignored)",
                    "routes_v1": {"file": "data/driving/routes-v1.json", "sha256": sha256(ROUTES_V1)},
                    "samples_v2": {"file": "data/comms/connecting_ridge/earth_link-v2-samples.json.gz",
                                   "sha256": sha256(SAMPLES_V2)}},
        "generated": {"tool": "tools/comms/earth_link.py ties"},
    }
    if doc["geometry"]["legs_differing_gt_20m"] > len(off) or h_leg not in off:
        raise SystemExit("geometry and sample lists disagree; check the inputs")
    with open(out, "wb") as f:
        f.write((json.dumps(doc, indent=1) + "\n").encode("utf-8"))
    ls = doc["linked_share"]
    log(f"ties: {len(hd)} legs; geometry > 20 m on {doc['geometry']['legs_differing_gt_20m']} (max "
        f"{doc['geometry']['max_m']} m, {h_leg}); length diff max {doc['length']['max_abs_diff_m']} m; linked share "
        f"max {ls['max_abs_diff_pp']} pp ({ls['max_leg']}), > 1 pp {ls['legs_gt_1pp']}, > 5 pp {ls['legs_gt_5pp']} "
        f"-> {_rel(out)}")
    return doc


def _git_sha() -> Optional[str]:
    from lunarsim.terrain import _git_sha as g
    return g()


def step_horizons(log=print) -> Dict:
    """One month at the note's site coordinates against the JPL Horizons API (same parameters as the note)."""
    q = {"format": "text", "COMMAND": "'399'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'", "EPHEM_TYPE": "'OBSERVER'",
         "CENTER": "'coord@301'", "COORD_TYPE": "'GEODETIC'",
         "SITE_COORD": "'%.3f,%.3f,%.3f'" % HORIZONS_SITE, "START_TIME": "'2028-01-01'", "STOP_TIME": "'2028-02-01'",
         "STEP_SIZE": "'10m'", "QUANTITIES": "'4,13,14'", "APPARENT": "'AIRLESS'", "ANG_FORMAT": "'DEG'",
         "CSV_FORMAT": "'YES'"}
    url = HORIZONS_URL + "?" + urllib.parse.urlencode(q, safe="',@")
    raw_path = os.path.join(CACHE, "horizons_2028-01.txt")
    if not os.path.isfile(raw_path):
        with urllib.request.urlopen(url, timeout=120) as r:
            open(raw_path, "wb").write(r.read())
    txt = open(raw_path, encoding="utf-8", errors="replace").read()
    lines = txt.splitlines()
    i0 = lines.index("$$SOE")
    i1 = lines.index("$$EOE")
    header = [h.strip() for h in lines[i0 - 2].split(",")]
    col = {h: k for k, h in enumerate(header)}
    rows = [[c.strip() for c in ln.split(",")] for ln in lines[i0 + 1:i1]]
    az_k = next(k for h, k in col.items() if h.startswith("Azi"))
    el_k = next(k for h, k in col.items() if h.startswith("Elev"))
    di_k = next(k for h, k in col.items() if h.startswith("Ang-diam"))
    t_k = col[next(h for h in col if h.startswith("Date"))]
    sp = furnsh_all()
    lon, lat, alt = HORIZONS_SITE
    la, lo = math.radians(lat), math.radians(lon)
    P = np.array([math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la)]) * (R_MOON_M / 1000 + alt)
    d_az, d_el, d_di = [], [], []
    for r in rows:
        et = sp.str2et(r[t_k].replace("A.D. ", "") + " UTC")
        st, _ = sp.azlcpo("ELLIPSOID", "EARTH", et, "LT+S", False, True, P, "MOON", "MOON_ME")
        d_az.append(abs(float(wrap180(math.degrees(st[1]) - float(r[az_k])))))
        d_el.append(abs(math.degrees(st[2]) - float(r[el_k])))
        d_di.append(abs(2 * math.degrees(math.asin(R_EARTH_KM / st[0])) * 3600 - float(r[di_k])))
    res = {"site": {"east_lon_deg": lon, "lat_deg": lat, "alt_km": alt}, "span": "2028-01-01 to 2028-02-01, 10 min",
           "n": len(rows), "max_abs_az_deg": max(d_az), "max_abs_el_deg": max(d_el),
           "max_abs_diameter_arcsec": max(d_di), "url": url,
           "horizons_header": [ln.strip() for ln in lines[:i0] if "Center pole" in ln or "Target body" in ln
                               or "Center radii" in ln][:3]}
    with open(os.path.join(CACHE, "horizons_check.json"), "w") as f:
        json.dump(res, f, indent=1)
    log(f"horizons: {len(rows)} epochs; max |d az| {res['max_abs_az_deg']:.4f} deg, |d el| {res['max_abs_el_deg']:.4f} "
        f"deg, |d diameter| {res['max_abs_diameter_arcsec']:.2f} arcsec")
    return res


def step_avgvisib(log=print) -> Dict:
    """Compare with the PDS average Earth-visibility map (Mazarico et al.; any part of the disc, surface level,
    LDEM_85S_060M). Two ways: our sites as computed (2.5 m antenna, 5 m tile), and our pipeline run the map's way
    (surface level, the 5 m tile averaged to the map's 60 m pixels, at the centre of the map pixel holding each site).
    Map pixels: 0-based pixel centre (i, j) at x = (i - 2528.5) * 60 m, y = (2528.5 - j) * 60 m (the image is centred
    on the pole; the label's offsets are pixel-centre coordinates)."""
    meta, sites = load_pack()
    x0, y0 = meta["origin_xy_m"]
    W, H = meta["size_m"]
    A = AVGVISIB
    rec = A["samples"] * 2
    j0 = int(math.floor(A["offset_px"] - (y0 + H) / A["px_m"])) - 2
    j1 = int(math.ceil(A["offset_px"] - y0 / A["px_m"])) + 2
    raw = os.path.join(CACHE, f"avgvisib_rows_{j0}_{j1}.bin")
    if not os.path.isfile(raw):
        req = urllib.request.Request(AVGVISIB_URL, headers={"Range": f"bytes={j0 * rec}-{(j1 + 1) * rec - 1}"})
        with urllib.request.urlopen(req, timeout=180) as r:
            open(raw, "wb").write(r.read())
    vis = np.fromfile(raw, dtype="<i2").reshape(-1, A["samples"]).astype(np.float64) * A["scale"]
    # the 5 m tile averaged to the map's 60 m pixels (pixel edges at multiples of 60 m from the pole)
    near5, _ = near_sampler(meta)
    z5 = near5.z
    px5 = near5.px
    k = int(round(A["px_m"] / px5))
    oc = int(round(((math.ceil(x0 / A["px_m"]) * A["px_m"]) - x0) / px5))
    orow = int(round(((y0 + H) - math.floor((y0 + H) / A["px_m"]) * A["px_m"]) / px5))
    sub = z5[orow:, oc:]
    r, c = (sub.shape[0] // k) * k, (sub.shape[1] // k) * k
    z60 = sub[:r, :c].reshape(r // k, k, c // k, k).mean(axis=(1, 3))
    near60 = GridSampler(z60, x0 + oc * px5, y0 + H - orow * px5, A["px_m"])
    far = far_sampler()
    bearings, _ = wedge_bearings()
    e = np.load(ephem_path())
    E, P_base = e["E_base_km"], e["P_base_km"]
    d = json.load(open(OUT))
    rows = []
    for key, pnt in d["points"].items():
        X, Y = pnt["xy_m"][0] + x0, pnt["xy_m"][1] + y0
        i = int(round(X / A["px_m"] + A["offset_px"]))
        j = int(round(A["offset_px"] - Y / A["px_m"]))
        mval = float(vis[j - j0, i])
        nb = vis[j - j0 - 1:j - j0 + 2, i - 1:i + 2]
        cx, cy = (i - A["offset_px"]) * A["px_m"], (A["offset_px"] - j) * A["px_m"]
        zc = float(near60(np.array([cx]), np.array([cy]))[0])
        m = horizon_wedge([cx], [cy], [zc], [0.0], bearings, near60, far)[0]
        lat, lon = latlon_deg(cx, cy)
        P = stereo_unit(cx, cy) * (R_MOON_M + zc) / 1000.0
        _, el, brg, rad = earth_topo(E, P_base, P, float(lat), float(lon))
        ours60 = float(np.mean(el + rad > np.interp(brg, bearings, np.nan_to_num(m, nan=-90.0))))
        rows.append({"point": key, "map": round(mval, 3), "map_3x3": [round(float(nb.min()), 3), round(float(nb.max()), 3)],
                     "ours_map_way": round(ours60, 3), "ours_2p5m_5m": pnt["summary"]["dte"]["any_part"]["fraction"]})
        log(f"{key:10s} map {mval:.3f} (3x3 {nb.min():.3f}-{nb.max():.3f})  ours, map's way {ours60:.3f}  "
            f"ours, 2.5 m antenna on the 5 m tile {rows[-1]['ours_2p5m_5m']:.3f}")
    dm = np.array([r["ours_map_way"] - r["map"] for r in rows])
    res = {"map": AVGVISIB_URL, "criterion": "any part of the disc, surface level", "rows": rows,
           "map_way_minus_map": {"mean": round(float(dm.mean()), 4), "mean_abs": round(float(np.abs(dm).mean()), 4),
                                 "max_abs": round(float(np.abs(dm).max()), 4),
                                 "within_0p05": int((np.abs(dm) <= 0.05).sum()), "n": len(rows)},
           "epochs": "ours 2028-2031 at 10 min; the map averages its own period (label START/STOP 2009-2013)"}
    with open(os.path.join(CACHE, "avgvisib_check.json"), "w") as f:
        json.dump(res, f, indent=1)
    log(f"map way minus map: mean {dm.mean():+.3f}, mean |d| {np.abs(dm).mean():.3f}, max |d| {np.abs(dm).max():.3f}; "
        f"{res['map_way_minus_map']['within_0p05']}/{len(rows)} within 0.05")
    return res


TRACK_OUT = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_track-v1.json.gz")


def step_track(out: str = TRACK_OUT, log=print) -> Dict:
    """Hourly Earth elevation, apparent radius and grid bearing at BASE (ground level), 2028-2031, for the 3D world
    (the Earth disc, scene packages). Integers in centidegrees; deterministic gzip."""
    import gzip
    e = np.load(ephem_path())
    E, P_base = e["E_base_km"], e["P_base_km"]
    lat, lon = (float(v) for v in e["base_latlon"])
    k = 60 // STEP_MIN
    _, el, brg, rad = earth_topo(E[::k], P_base, P_base, lat, lon)
    cd = lambda a: np.rint(np.asarray(a) * 100.0).astype(int).tolist()
    doc = {"format": "lunarsim-earth-track", "version": 1, "site": "BASE", "lat_deg": round(lat, 5), "lon_deg": round(lon, 4),
           "time": {"start_utc": START_UTC, "step_h": 1, "n": int(len(el))},
           "units": "centidegrees (value / 100 = degrees)",
           "elevation_cdeg": cd(el), "radius_cdeg": cd(rad), "grid_bearing_cdeg": cd(brg),
           "note": "Earth's centre seen from BASE at ground level (no antenna height, no terrain): elevation above the "
                   "local horizontal, apparent radius, grid bearing (0 = +y, 90 = +x); SPICE, MOON_ME, LT+S "
                   "(tools/comms/earth_link.py ephem)",
           "kernels": json.load(open(os.path.join(CACHE, "ephem.json")))["kernels"]}
    with open(out, "wb") as f:
        f.write(gzip.compress(json.dumps(doc, separators=(",", ":")).encode("utf-8"), 9, mtime=0))
    log(f"track: {len(el)} hours -> {_rel(out)} ({os.path.getsize(out) / 1024:.0f} KB)")
    return doc


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/comms/earth_link.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ephem")
    p = sub.add_parser("routes")
    p.add_argument("--legs", default=None, help="leg index range, e.g. 0-59 (order of legs_from_sites)")
    sub.add_parser("points")
    sub.add_parser("dem")
    p = sub.add_parser("masks")
    p.add_argument("--part", type=int, default=0)
    p.add_argument("--parts", type=int, default=1)
    p = sub.add_parser("link")
    p.add_argument("--out", default=OUT)
    sub.add_parser("horizons")
    sub.add_parser("avgvisib")
    sub.add_parser("track")
    sub.add_parser("points2")
    for name in ("masks2", "series2"):
        p = sub.add_parser(name)
        p.add_argument("--part", type=int, default=0)
        p.add_argument("--parts", type=int, default=1)
    p = sub.add_parser("samples2")
    p.add_argument("--recheck", type=int, default=40, help="v1 samples to recompute as a determinism check")
    sub.add_parser("ties")
    for sp_ in sub.choices.values():
        sp_.add_argument("--max-seconds", type=float, default=540.0,
                         help="stop this process after so many seconds (Windows: `timeout` only kills the venv launcher)")
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    os.makedirs(CACHE, exist_ok=True)
    if a.cmd == "ephem":
        step_ephem()
    elif a.cmd == "routes":
        step_routes(a.legs)
    elif a.cmd == "points":
        step_points()
    elif a.cmd == "dem":
        step_dem()
    elif a.cmd == "masks":
        step_masks(a.part, a.parts)
    elif a.cmd == "link":
        step_link(a.out)
    elif a.cmd == "horizons":
        step_horizons()
    elif a.cmd == "avgvisib":
        step_avgvisib()
    elif a.cmd == "track":
        step_track()
    elif a.cmd == "points2":
        step_points2()
    elif a.cmd == "masks2":
        step_masks2(a.part, a.parts)
    elif a.cmd == "series2":
        step_series2(a.part, a.parts)
    elif a.cmd == "samples2":
        step_samples2(recheck=a.recheck)
    elif a.cmd == "ties":
        step_ties()
    rss = peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
