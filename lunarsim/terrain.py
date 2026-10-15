"""Terrain packs (lunarsim-terrain v1): build from a PGDA LOLA 5 m/px site tile, read, and query.

A pack is a folder ``data/terrain/<site_id>/``:

    meta.json          format, source + citation, CRS, origin, size, layers, z encoding, stats, provenance
    height_5m.png      uint16, z = offset_m + scale_m_per_unit * value, row 0 = north edge (max y)
    height_20m.png     same encoding, 4x4 block mean of the float 5 m grid
    slope_20m.png      uint8 degrees: slope computed on the float 5 m grid, then 4x4 block mean
    hillshade_20m.png  uint8, 255 * (n . s) / hillshade_scale, cast shadows included (sun elevation 1.5 deg)
    sites.json         (chosen by LEAD with `lunarsim terrain place`) LunarSim sites and pad sets

Coordinates. Map frame = the GeoTIFF's south polar stereographic X/Y in metres (MOON_ME, DE421).
Local frame used everywhere else: x = X - x0, y = Y - y0 where (x0, y0) = ``origin_xy_m`` is the map
position of the tile's lower-left corner (min X, min Y; pixel edge, not centre). Pixel (row r from
the top, column c) has its centre at x = (c + 0.5) * px, y = (rows - r - 0.5) * px.

Azimuths are map azimuths: 0 deg = +y (grid north of the stereographic map), 90 deg = +x, clockwise.
At the pole "north" has no geographic meaning; this is a grid convention, stated so the JS reader
(site/src/terrain.js) can follow it line by line.

Constants (flags as in the project's parameter tables):
- LOLA 5 m/px site DEM: Measured (Barker et al. 2021; ~90 % of 5 m pixels interpolated;
  median RMS Z error 0.30-0.50 m, slope error 1.5-2.5 deg). https://pgda.gsfc.nasa.gov/products/78
- MOON_RADIUS_M = 1737.4 km: Spec (IAU mean radius; PGDA illumination products use 1737.4 km).
  https://pgda.gsfc.nasa.gov/products/69
- SUN_ELEVATION_DEG = 1.5: Assumed (typical sun elevation at the south-pole sites is a few degrees or less;
  the PGDA 45 deg hillshade is "a shading aid, not a lighting ground truth"). https://pgda.gsfc.nasa.gov/products/90/
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import subprocess
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

TERRAIN_FORMAT = "lunarsim-terrain"
TERRAIN_VERSION = 1
MOON_RADIUS_M = 1_737_400.0          # Spec, see module docstring
SUN_ELEVATION_DEG = 1.5              # Assumed
PGDA_URL = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/{site}/{site}_final_adj_5mpp_surf.tif"
CITATION = ("Barker et al. 2021, PGDA LOLA 5 m/px polar DEMs, https://pgda.gsfc.nasa.gov/products/78 "
            "(Barker, M. K. et al., Planetary and Space Science 203, 105119, doi:10.1016/j.pss.2020.105119)")
CREDIT = "NASA/GSFC"
SITE_NAMES = {"Site01": "Connecting ridge", "Site04": "Shackleton rim", "Site07": "Peak near Shackleton",
              "Site11": "de Gerlache rim", "Site23": "Malapert massif", "Site20v2": "Leibnitz beta plateau"}
SLOPE_BINS_DEG = (0, 5, 10, 15, 20)  # leg_stats histogram: 0-5, 5-10, 10-15, 15-20, >20
DEFAULT_ROOT = os.path.join("data", "terrain")


# ---------------------------------------------------------------------------
# grid maths (pure numpy; the JS port follows these functions)
# ---------------------------------------------------------------------------
def slope_deg(z: np.ndarray, px: float) -> np.ndarray:
    """Slope in degrees by central differences (one-sided at the edges), z row 0 = north."""
    dz_drow, dz_dcol = np.gradient(z, px)
    return np.degrees(np.arctan(np.hypot(dz_dcol, dz_drow)))


def block_mean(a: np.ndarray, k: int) -> np.ndarray:
    """k x k block mean; the array is trimmed to a multiple of k first."""
    r, c = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    return a[:r, :c].reshape(r // k, k, c // k, k).mean(axis=(1, 3))


def sun_vector(az_deg: float, el_deg: float) -> Tuple[float, float, float]:
    """Unit vector towards the sun in the local frame (x, y, up); az 0 = +y, 90 = +x."""
    az, el = math.radians(az_deg), math.radians(el_deg)
    return math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el)


def cast_shadow(z_north_up: np.ndarray, px: float, az_deg: float, el_deg: float,
                max_dist_m: float = 20_000.0) -> np.ndarray:
    """Boolean grid, True where the sun (a point at az/el) is below the local terrain horizon.

    Horizon ray-march: from every cell, step towards the sun one cell length at a time and compare the
    terrain (lowered by the Moon's curvature, d^2 / 2R) with the sun ray z0 + d tan(el). Cells whose ray
    leaves the tile are lit beyond the edge (no terrain outside the tile is known)."""
    z = z_north_up
    rows, cols = z.shape
    sx, sy, _ = sun_vector(az_deg, el_deg)
    h = math.hypot(sx, sy)
    dx, dy = sx / h, sy / h                       # unit step towards the sun in the local frame
    tan_el = math.tan(math.radians(el_deg))
    shadow = np.zeros(z.shape, dtype=bool)
    n = int(max_dist_m / px)
    for k in range(1, n + 1):
        d = k * px
        oc = int(round(k * dx))                   # column offset (+x)
        orow = -int(round(k * dy))                # row offset (+y is up, rows grow southwards)
        if abs(oc) >= cols or abs(orow) >= rows:
            break
        r0, r1 = max(0, -orow), min(rows, rows - orow)
        c0, c1 = max(0, -oc), min(cols, cols - oc)
        src = z[r0 + orow:r1 + orow, c0 + oc:c1 + oc] - d * d / (2 * MOON_RADIUS_M)
        shadow[r0:r1, c0:c1] |= src > z[r0:r1, c0:c1] + d * tan_el
    return shadow


def hillshade(z_north_up: np.ndarray, px: float, az_deg: float, el_deg: float = SUN_ELEVATION_DEG,
              shadows: bool = True) -> np.ndarray:
    """n . s in [0, 1] (Lambertian incidence), 0 in cast shadow if `shadows`."""
    dz_drow, dz_dcol = np.gradient(z_north_up, px)
    dz_dx, dz_dy = dz_dcol, -dz_drow              # rows grow southwards
    sx, sy, sz = sun_vector(az_deg, el_deg)
    shade = (-dz_dx * sx - dz_dy * sy + sz) / np.sqrt(dz_dx ** 2 + dz_dy ** 2 + 1.0)
    shade = np.clip(shade, 0.0, 1.0)
    if shadows:
        shade[cast_shadow(z_north_up, px, az_deg, el_deg)] = 0.0
    return shade


def disk_mean(a: np.ndarray, radius_px: int) -> np.ndarray:
    """Mean over a disk of the given radius (in cells) around each cell; edges use the cells inside."""
    out = np.zeros_like(a, dtype=np.float64)
    cnt = np.zeros_like(a, dtype=np.float64)
    rows, cols = a.shape
    for di in range(-radius_px, radius_px + 1):
        for dj in range(-radius_px, radius_px + 1):
            if di * di + dj * dj > radius_px * radius_px:
                continue
            r0, r1 = max(0, -di), min(rows, rows - di)
            c0, c1 = max(0, -dj), min(cols, cols - dj)
            out[r0:r1, c0:c1] += a[r0 + di:r1 + di, c0 + dj:c1 + dj]
            cnt[r0:r1, c0:c1] += 1
    return out / cnt


def plane_slope_deg(z: np.ndarray, px: float, radius_px: int) -> np.ndarray:
    """Pad-scale tilt: slope of the mean height gradient over a disk (= slope of the least-squares plane
    for evenly sampled cells), in degrees."""
    dz_drow, dz_dcol = np.gradient(z, px)
    return np.degrees(np.arctan(np.hypot(disk_mean(dz_dcol, radius_px), disk_mean(dz_drow, radius_px))))


def disk_max(a: np.ndarray, radius_px: int) -> np.ndarray:
    """Maximum over a disk of the given radius (in cells) around each cell; edges use the cells inside."""
    out = a.copy()
    rows, cols = a.shape
    for di in range(-radius_px, radius_px + 1):
        for dj in range(-radius_px, radius_px + 1):
            if (di == 0 and dj == 0) or di * di + dj * dj > radius_px * radius_px:
                continue
            r0, r1 = max(0, -di), min(rows, rows - di)
            c0, c1 = max(0, -dj), min(cols, cols - dj)
            np.maximum(out[r0:r1, c0:c1], a[r0 + di:r1 + di, c0 + dj:c1 + dj], out=out[r0:r1, c0:c1])
    return out


# ---------------------------------------------------------------------------
# building a pack
# ---------------------------------------------------------------------------
def _git_sha() -> Optional[str]:
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=here, capture_output=True, text=True,
                              timeout=10).stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def download(site: str, cache_dir: str, url: Optional[str] = None) -> str:
    """Fetch the PGDA site DEM into cache_dir (skipped if already there). Returns the local path."""
    import urllib.request
    url = url or PGDA_URL.format(site=site)
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, os.path.basename(url))
    if os.path.exists(path):
        return path
    tmp = path + ".part"
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, path)
    return path


def read_geotiff(path: str) -> Tuple[np.ndarray, Dict[str, Any]]:
    """(z float64, row 0 = north, NaN for no-data; georef dict) from a north-up GeoTIFF."""
    import rasterio
    with rasterio.open(path) as ds:
        z = ds.read(1).astype(np.float64)
        t = ds.transform
        if abs(t.b) > 1e-12 or abs(t.d) > 1e-12:
            raise ValueError(f"{path}: rotated GeoTIFFs are not supported")
        if abs(abs(t.a) - abs(t.e)) > 1e-9:
            raise ValueError(f"{path}: non-square pixels ({t.a} x {t.e})")
        if ds.nodata is not None:
            z[z == ds.nodata] = np.nan
        crs = ds.crs.to_wkt() if ds.crs else None
        proj4 = ds.crs.to_proj4() if ds.crs else None
    if t.e > 0:                                   # south-up file: flip to north-up
        z = z[::-1]
        y_bottom = t.f
    else:
        y_bottom = t.f + t.e * z.shape[0]
    if t.a < 0:
        z = z[:, ::-1]
        x_left = t.c + t.a * z.shape[1]
    else:
        x_left = t.c
    z[~np.isfinite(z)] = np.nan
    return z, {"px_m": abs(t.a), "origin_xy_m": [float(x_left), float(y_bottom)], "crs_wkt": crs, "proj4": proj4}


def _fill_nan(z: np.ndarray) -> int:
    """Fill NaNs in place by repeated 4-neighbour averaging. Returns how many cells were filled."""
    bad = ~np.isfinite(z)
    n = int(bad.sum())
    if n == 0:
        return 0
    if n == z.size:
        raise ValueError("DEM has no valid cells")
    while bad.any():
        p = np.pad(z, 1, constant_values=np.nan)
        nb = np.stack([p[:-2, 1:-1], p[2:, 1:-1], p[1:-1, :-2], p[1:-1, 2:]])
        cnt = np.isfinite(nb).sum(axis=0)
        s = np.nansum(nb, axis=0)
        fill = bad & (cnt > 0)
        z[fill] = s[fill] / cnt[fill]
        bad &= ~fill
    return n


def _png(path: str, a: np.ndarray, bits: int) -> None:
    from PIL import Image
    if bits == 16:
        Image.fromarray(a.astype(np.uint16)).save(path, optimize=True)
    else:
        Image.fromarray(a.astype(np.uint8), mode="L").save(path, optimize=True)


def encode_height(z: np.ndarray, offset_m: float, scale: float) -> np.ndarray:
    v = np.rint((z - offset_m) / scale)
    if v.max() > 65535:
        raise ValueError(f"relief {z.max() - offset_m:.0f} m does not fit uint16 at {scale} m/unit; raise --z-scale")
    return np.clip(v, 0, 65535).astype(np.uint16)


def build_pack(src_tif: str, out_dir: str, site: str, name: Optional[str] = None, sun_az_deg: float = 0.0,
               z_scale: float = 0.5, url: Optional[str] = None, coarse: int = 4) -> Dict[str, Any]:
    """Write a lunarsim-terrain v1 pack from a 5 m GeoTIFF. Returns meta."""
    z, geo = read_geotiff(src_tif)
    filled = _fill_nan(z)
    px = geo["px_m"]
    rows, cols = z.shape
    offset = float(math.floor(np.min(z)))
    os.makedirs(out_dir, exist_ok=True)

    slope5 = slope_deg(z, px)
    z20 = block_mean(z, coarse)
    slope20 = block_mean(slope5, coarse)
    px20 = px * coarse
    shade = hillshade(z20, px20, sun_az_deg, SUN_ELEVATION_DEG)
    shade_scale = float(max(np.percentile(shade[shade > 0], 99), 1e-6)) if (shade > 0).any() else 1.0

    _png(os.path.join(out_dir, "height_5m.png"), encode_height(z, offset, z_scale), 16)
    _png(os.path.join(out_dir, "height_20m.png"), encode_height(z20, offset, z_scale), 16)
    _png(os.path.join(out_dir, "slope_20m.png"), np.clip(np.rint(slope20), 0, 255), 8)
    _png(os.path.join(out_dir, "hillshade_20m.png"), np.clip(np.rint(255 * shade / shade_scale), 0, 255), 8)

    def layer(file, shape, cell, kind, **kw):
        d = {"file": file, "shape": [int(shape[0]), int(shape[1])], "px_m": cell, "kind": kind}
        d.update(kw)
        return d

    meta = {
        "format": TERRAIN_FORMAT, "version": TERRAIN_VERSION, "site_id": os.path.basename(os.path.normpath(out_dir)),
        "name": name or SITE_NAMES.get(site, site),
        "source": {"product": f"PGDA LOLA 5mpp {site}", "url": url or PGDA_URL.format(site=site),
                   "citation": CITATION, "credit": CREDIT, "flag": "Measured"},
        "crs": "Moon south polar stereographic (LOLA)", "proj4": geo["proj4"], "crs_wkt": geo["crs_wkt"],
        "origin_xy_m": geo["origin_xy_m"],
        "size_m": [cols * px, rows * px],
        "frame": ("local x = X - origin_x, y = Y - origin_y (metres); PNG row 0 = max y; "
                  "azimuth 0 = +y, 90 = +x (grid convention)"),
        "layers": {
            "height_5m": layer("height_5m.png", z.shape, px, "height", dtype="uint16"),
            "height_20m": layer("height_20m.png", z20.shape, px20, "height", dtype="uint16",
                                note=f"{coarse}x{coarse} block mean of the float 5 m grid"),
            "slope_20m": layer("slope_20m.png", slope20.shape, px20, "slope_deg", dtype="uint8",
                               note=f"slope on the float 5 m grid (central differences), {coarse}x{coarse} block mean, rounded"),
            "hillshade_20m": layer("hillshade_20m.png", z20.shape, px20, "hillshade", dtype="uint8",
                                   sun_az_deg=sun_az_deg, sun_el_deg=SUN_ELEVATION_DEG, hillshade_scale=shade_scale,
                                   note="value = 255 * min(1, (n . s) / hillshade_scale); cast shadows set to 0; "
                                        "Moon curvature included"),
        },
        "z_encoding": {"offset_m": offset, "scale_m_per_unit": z_scale},
        "stats": {"z_min": float(np.min(z)), "z_max": float(np.max(z)),
                  "slope_p50": float(np.percentile(slope5, 50)), "slope_p90": float(np.percentile(slope5, 90)),
                  "nodata_filled": filled},
        "generated": {"tool": "lunarsim terrain build", "commit": _git_sha(),
                      "time": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()},
    }
    with open(os.path.join(out_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


# ---------------------------------------------------------------------------
# reading and querying a pack
# ---------------------------------------------------------------------------
def _read_png(path: str) -> np.ndarray:
    from PIL import Image
    with Image.open(path) as im:
        return np.array(im)


def _bilinear(grid_south_up: np.ndarray, px: float, x, y):
    """Bilinear sample of a cell-centred grid stored with row 0 = south (min y). Clamped at the edges."""
    g = grid_south_up
    rows, cols = g.shape
    u = np.clip(np.asarray(x, dtype=np.float64) / px - 0.5, 0, cols - 1)
    v = np.clip(np.asarray(y, dtype=np.float64) / px - 0.5, 0, rows - 1)
    i0 = np.minimum(np.floor(u).astype(np.int64), cols - 2) if cols > 1 else np.zeros_like(u, dtype=np.int64)
    j0 = np.minimum(np.floor(v).astype(np.int64), rows - 2) if rows > 1 else np.zeros_like(v, dtype=np.int64)
    fu, fv = u - i0, v - j0
    i1, j1 = np.minimum(i0 + 1, cols - 1), np.minimum(j0 + 1, rows - 1)
    return ((g[j0, i0] * (1 - fu) + g[j0, i1] * fu) * (1 - fv)
            + (g[j1, i0] * (1 - fu) + g[j1, i1] * fu) * fv)


def resolve_pack(site: str, root: str = DEFAULT_ROOT) -> str:
    """A pack folder from a path or a site id under root."""
    if os.path.isfile(os.path.join(site, "meta.json")):
        return site
    p = os.path.join(root, site)
    if os.path.isfile(os.path.join(p, "meta.json")):
        return p
    raise FileNotFoundError(f"no terrain pack '{site}' (looked for {site}/meta.json and {p}/meta.json)")


class Terrain:
    """Read-only access to a lunarsim-terrain v1 pack. All positions are local metres (see module doc)."""

    def __init__(self, site_id: str, root: str = DEFAULT_ROOT):
        self.path = resolve_pack(site_id, root)
        with open(os.path.join(self.path, "meta.json"), encoding="utf-8") as f:
            self.meta = json.load(f)
        if self.meta.get("format") != TERRAIN_FORMAT or self.meta.get("version") != TERRAIN_VERSION:
            raise ValueError(f"{self.path}: not a {TERRAIN_FORMAT} v{TERRAIN_VERSION} pack")
        L, enc = self.meta["layers"], self.meta["z_encoding"]
        self.site_id = self.meta["site_id"]
        self.size_m = tuple(self.meta["size_m"])
        self.px5 = L["height_5m"]["px_m"]
        self.px20 = L["height_20m"]["px_m"]
        off, sc = enc["offset_m"], enc["scale_m_per_unit"]
        self.z5 = (off + sc * _read_png(os.path.join(self.path, L["height_5m"]["file"])).astype(np.float64))[::-1]
        self.z20 = (off + sc * _read_png(os.path.join(self.path, L["height_20m"]["file"])).astype(np.float64))[::-1]
        self.slope20 = _read_png(os.path.join(self.path, L["slope_20m"]["file"])).astype(np.float64)[::-1]
        self._sites = None

    # point queries ---------------------------------------------------------
    def height(self, x, y):
        """Surface height (m, LOLA datum) by bilinear interpolation of the 5 m grid."""
        return _bilinear(self.z5, self.px5, x, y)

    def slope(self, x, y):
        """Terrain slope (deg) by bilinear interpolation of slope_20m (computed on the float 5 m grid;
        the 5 m height PNG is quantised to scale_m_per_unit, too coarse to differentiate)."""
        return _bilinear(self.slope20, self.px20, x, y)

    def contains(self, x, y) -> bool:
        return 0 <= x <= self.size_m[0] and 0 <= y <= self.size_m[1]

    def to_local(self, X, Y):
        x0, y0 = self.meta["origin_xy_m"]
        return X - x0, Y - y0

    def to_map(self, x, y):
        x0, y0 = self.meta["origin_xy_m"]
        return x + x0, y + y0

    # paths -----------------------------------------------------------------
    def profile(self, a: Sequence[float], b: Sequence[float], step_m: float = 5.0) -> Dict[str, np.ndarray]:
        """Samples along the straight segment a -> b: s (m from a), x, y, z, slope_deg."""
        a, b = np.asarray(a, float), np.asarray(b, float)
        L = float(np.hypot(*(b - a)))
        n = max(1, int(math.ceil(L / step_m)))
        s = np.linspace(0.0, L, n + 1)
        f = s / L if L > 0 else np.zeros_like(s)
        x, y = a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1])
        return {"s": s, "x": x, "y": y, "z": self.height(x, y), "slope_deg": self.slope(x, y)}

    def leg_stats(self, a, b, step_m: float = 5.0, sun_az_deg: Optional[float] = None,
                  sun_el_deg: float = SUN_ELEVATION_DEG) -> Dict[str, Any]:
        """Straight-leg statistics. slope_hist = share of the leg length in terrain-slope bins
        0-5, 5-10, 10-15, 15-20, >20 deg (fractions summing to 1). max_grade_deg is the steepest
        along-track grade between samples; max_slope_deg the steepest terrain slope crossed."""
        p = self.profile(a, b, step_m)
        dz = np.diff(p["z"])
        ds = np.diff(p["s"])
        mid_slope = 0.5 * (p["slope_deg"][1:] + p["slope_deg"][:-1])
        edges = list(SLOPE_BINS_DEG) + [np.inf]
        L = float(p["s"][-1])
        hist = [float(ds[(mid_slope >= lo) & (mid_slope < hi)].sum() / L) if L > 0 else 0.0
                for lo, hi in zip(edges[:-1], edges[1:])]
        out = {
            "length_m": L,
            "length_3d_m": float(np.sum(np.hypot(ds, dz))),
            "climb_m": float(dz[dz > 0].sum()),
            "descent_m": float(-dz[dz < 0].sum()),
            "max_slope_deg": float(p["slope_deg"].max()),
            "max_grade_deg": float(np.degrees(np.arctan(np.max(np.abs(dz) / ds)))) if len(ds) else 0.0,
            "slope_hist": hist,
            "slope_bins_deg": ["0-5", "5-10", "10-15", "15-20", ">20"],
        }
        if sun_az_deg is not None:
            out["shadow_fraction"] = self.shadow_fraction(a, b, sun_az_deg, sun_el_deg)
        return out

    def shadowed(self, x, y, sun_az_deg: float, sun_el_deg: float = SUN_ELEVATION_DEG,
                 max_dist_m: float = 20_000.0) -> np.ndarray:
        """True where the sun is below the terrain horizon (ray-march at the 20 m cell size, Moon curvature
        included). Terrain beyond the tile edge is unknown and treated as open."""
        x = np.atleast_1d(np.asarray(x, float))
        y = np.atleast_1d(np.asarray(y, float))
        z0 = _bilinear(self.z20, self.px20, x, y)
        sx, sy, _ = sun_vector(sun_az_deg, sun_el_deg)
        h = math.hypot(sx, sy)
        dx, dy = sx / h, sy / h
        tan_el = math.tan(math.radians(sun_el_deg))
        shade = np.zeros(x.shape, bool)
        alive = np.ones(x.shape, bool)
        for k in range(1, int(max_dist_m / self.px20) + 1):
            d = k * self.px20
            xs, ys = x + d * dx, y + d * dy
            alive &= (xs >= 0) & (xs <= self.size_m[0]) & (ys >= 0) & (ys <= self.size_m[1])
            if not alive.any():
                break
            zt = _bilinear(self.z20, self.px20, xs, ys) - d * d / (2 * MOON_RADIUS_M)
            shade |= alive & (zt > z0 + d * tan_el)
        return shade

    def shadow_fraction(self, a, b, sun_az_deg: float, sun_el_deg: float = SUN_ELEVATION_DEG) -> float:
        """Share of the leg (samples every 20 m) in cast shadow for the given sun azimuth."""
        p = self.profile(a, b, self.px20)
        return float(self.shadowed(p["x"], p["y"], sun_az_deg, sun_el_deg).mean())

    def los_clearance_m(self, a, b, h_a: float = 2.0, h_b: float = 2.0, step_m: float = 5.0) -> float:
        """Smallest height of the sight line above the terrain between a and b (observers h_a, h_b metres
        above ground; Moon curvature included as the chord bulge s (L - s) / 2R). Negative = blocked."""
        p = self.profile(a, b, step_m)
        s, z = p["s"], p["z"]
        L = s[-1]
        if L <= 0:
            return float(h_a)
        za, zb = z[0] + h_a, z[-1] + h_b
        line = za + (zb - za) * s / L
        bulge = s * (L - s) / (2 * MOON_RADIUS_M)
        inner = slice(1, -1)
        if len(s) <= 2:
            return float(min(h_a, h_b))
        return float(np.min(line[inner] - (z[inner] + bulge[inner])))

    def line_of_sight(self, a, b, h_a: float = 2.0, h_b: float = 2.0) -> bool:
        """True if a and b see each other (both observers h metres above ground)."""
        return self.los_clearance_m(a, b, h_a, h_b) > 0

    # whole-grid layers -----------------------------------------------------
    def illumination_proxy(self, azimuths: Iterable[float] = (0, 90, 180, 270),
                           el_deg: float = SUN_ELEVATION_DEG) -> np.ndarray:
        """Mean hillshade (n . s, cast shadows) over the given sun azimuths on the 20 m grid, row 0 = south.
        A stand-in until the PGDA average-visibility raster is added to the pack."""
        z_north = self.z20[::-1]
        acc = np.zeros_like(z_north)
        azs = list(azimuths)
        for az in azs:
            acc += hillshade(z_north, self.px20, az, el_deg)
        return (acc / len(azs))[::-1]

    def roughness20(self) -> np.ndarray:
        """Roughness proxy per 20 m cell (m), row 0 = south: std of the 5 m heights in the cell about their
        least-squares plane (the slope itself removed). The 5 m PNG is quantised to scale_m_per_unit, so values
        near scale/sqrt(12) (0.14 m at 0.5 m/unit) are quantisation noise. Cached."""
        if getattr(self, "_rough", None) is None:
            k = int(round(self.px20 / self.px5))
            r, c = (self.z5.shape[0] // k) * k, (self.z5.shape[1] // k) * k
            b = self.z5[:r, :c].reshape(r // k, k, c // k, k)                  # (rows, k, cols, k)
            u = (np.arange(k) - (k - 1) / 2.0)
            U = u[None, :, None, None]                                         # along rows (y)
            V = u[None, None, None, :]                                         # along columns (x)
            mean = b.mean(axis=(1, 3), keepdims=True)
            su2 = float((u * u).sum() * k)
            gy = (b * U).sum(axis=(1, 3), keepdims=True) / su2
            gx = (b * V).sum(axis=(1, 3), keepdims=True) / su2
            self._rough = (b - (mean + gy * U + gx * V)).std(axis=(1, 3))
        return self._rough

    def shadow_grid(self, sun_az_deg: float, sun_el_deg: float = SUN_ELEVATION_DEG) -> np.ndarray:
        """Cast-shadow mask on the 20 m grid (row 0 = south) for one sun azimuth. Cached per azimuth."""
        cache = self.__dict__.setdefault("_shadow_cache", {})
        key = (round(float(sun_az_deg), 3), round(float(sun_el_deg), 3))
        if key not in cache:
            cache[key] = cast_shadow(self.z20[::-1], self.px20, sun_az_deg, sun_el_deg)[::-1]
        return cache[key]

    def cell(self, x, y):
        """(row from south, column) of the 20 m cell containing (x, y), clamped to the grid."""
        rows, cols = self.z20.shape
        j = np.clip((np.asarray(y, float) / self.px20).astype(np.int64), 0, rows - 1)
        i = np.clip((np.asarray(x, float) / self.px20).astype(np.int64), 0, cols - 1)
        return j, i

    def sites(self) -> Optional[Dict[str, Any]]:
        if self._sites is None:
            p = os.path.join(self.path, "sites.json")
            if os.path.exists(p):
                with open(p, encoding="utf-8") as f:
                    self._sites = json.load(f)
        return self._sites


# ---------------------------------------------------------------------------
# pad placement
# ---------------------------------------------------------------------------
def place_pads(t: Terrain, base_xy: Sequence[float], standoff_km: float, max_slope_deg: float = 5.0,
               radius_m: float = 100.0, band_frac: float = 0.05, n: int = 10, min_sep_m: float = 300.0,
               illum: Optional[np.ndarray] = None, slope_stat: str = "plane") -> List[Dict[str, Any]]:
    """Pad candidates at standoff_km (+- band_frac) from base_xy, ranked by the illumination proxy and
    greedily thinned to min_sep_m apart. Slope test over a radius_m disk, by `slope_stat`:
    "plane" (default) = tilt of the mean surface over the disk (pad-scale slope); "max" = steepest
    20 m cell in the disk (strict; 5 m LOLA slope noise of 1.5-2.5 deg RMS inflates it).
    Both values are reported. Each candidate reports line of sight to BASE (blocked = natural plume shield)."""
    if slope_stat not in ("plane", "max"):
        raise ValueError("slope_stat must be 'plane' or 'max'")
    D = standoff_km * 1000.0
    px = t.px20
    rows, cols = t.slope20.shape
    yy, xx = np.mgrid[0:rows, 0:cols]
    cx, cy = (xx + 0.5) * px, (yy + 0.5) * px
    dist = np.hypot(cx - base_xy[0], cy - base_xy[1])
    band = max(band_frac * D, px)
    rad = max(1, int(round(radius_m / px)))
    smax = disk_max(t.slope20, rad)
    splane = plane_slope_deg(t.z20, px, rad)
    test = splane if slope_stat == "plane" else smax
    inside = (xx >= rad) & (xx < cols - rad) & (yy >= rad) & (yy < rows - rad)   # whole disk on the tile
    ok = (np.abs(dist - D) <= band) & (test <= max_slope_deg) & inside
    if illum is None:
        illum = t.illumination_proxy()
    idx = np.flatnonzero(ok)
    order = idx[np.argsort(-illum.ravel()[idx], kind="stable")]
    picked: List[Dict[str, Any]] = []
    for k in order:
        x, y = float(cx.ravel()[k]), float(cy.ravel()[k])
        if any(math.hypot(x - p["xy_m"][0], y - p["xy_m"][1]) < min_sep_m for p in picked):
            continue
        clear = t.los_clearance_m((x, y), base_xy, h_a=10.0, h_b=2.0)   # 10 m: plume/ejecta source height, Assumed
        picked.append({
            "xy_m": [round(x, 1), round(y, 1)],
            "dist_km": round(float(dist.ravel()[k]) / 1000.0, 3),
            "bearing_deg": round(math.degrees(math.atan2(x - base_xy[0], y - base_xy[1])) % 360, 1),
            "slope_plane_deg": round(float(splane.ravel()[k]), 2),
            "slope_max_deg": round(float(smax.ravel()[k]), 2),
            "illum": round(float(illum.ravel()[k]), 4),
            "z_m": round(float(t.height(x, y)), 1),
            "los_to_base": "clear" if clear > 0 else "blocked",
            "los_clearance_m": round(clear, 1),
        })
        if len(picked) >= n:
            break
    return picked
