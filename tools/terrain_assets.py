"""Terrain assets v2 (B-34): normal maps, horizon maps and levels of detail from a lunarsim-terrain v1 pack.

    python tools/terrain_assets.py build --pack data/terrain/connecting_ridge --out data/terrain/connecting_ridge/v2
    python tools/terrain_assets.py build ... --files 0-7        # horizon files 0-7 only (foreground chunks)
    python tools/terrain_assets.py validate --pack ... --out ...  # 4-azimuth agreement with the world shader

Output folder (``manifest.json`` lists every file with shape, encoding, size and sha256):

    normal_20m.png              RGB8 normals at the 20 m posts of height_20m.png (800 x 800)
    normal_5m_<SITE>.png        RGB8 normals, 2 x 2 km patch centred on BASE and on PAD_A (400 x 400)
    height_5m_<SITE>.png        uint16 heights for the same patches, 0.05 m per unit (finer than the pack's 0.5 m)
    horizon_20m_<jj>.png        RGBA16 horizon elevation angles; file jj holds sectors 4jj..4jj+3 in R, G, B, A
    manifest.json

Frames and conventions (those of lunarsim/terrain.py, so the JS reader follows them line by line):
- local x = east from the tile's west edge, y = north from its south edge, metres; PNG row 0 = north edge.
- Normals: unit vector (nx, ny, nz) in (x east, y north, z up), stored as round((n + 1) / 2 * 255). In the
  three.js world frame of site/src/world/scene.js (X east, Y up, Z south) the normal is (nx, nz, -ny).
- Azimuth: grid convention, 0 deg = +y, 90 deg = +x, clockwise. Horizon sector k (k = 0..63) is the ray at
  azimuth k * 360 / 64 = k * 5.625 deg (sector centre). For any azimuth a: f = a / 5.625, k0 = floor(f) mod 64,
  k1 = (k0 + 1) mod 64, h = lerp(H[k0], H[k1], f - floor(f)).
- Horizon angle = max over the ray of atan((z(d) - d^2 / 2R - z0 - h_obs) / d): the elevation of the local
  terrain horizon seen from h_obs = 1 m above the post (the world shader's eye height), Moon curvature included
  (R = 1737.4 km, as lunarsim.terrain). Stored as uint16 code = round((angle_deg + 90) / 0.05): angle =
  0.05 * code - 90. Code 0 = no terrain inside the tile in that direction (the post sits on the edge).
- **Terrain outside the 16 km tile is NOT included.** A ray stops at the tile edge, so posts near an edge
  under-estimate the horizon in outward directions (the distance to the edge along azimuth a follows from the
  post position). R-1 (Earth in sight) extends the horizon beyond the tile.

Why 16 RGBA16 PNGs for 64 sectors: (1) four times fewer requests than 64 single-channel files (GitHub Pages
sends max-age=600, so every file pays a revalidation); (2) one RGBA texel holds four adjacent azimuths, so the
bracketing pair for a sun or Earth azimuth is in the same texture three times out of four; (3) the samples stay
exact 16-bit values through the site's own PNG reader (site/src/terrain.js; canvas decoding drops to 8 bits),
then upload as a DataTexture (or a 16-layer DataArrayTexture) with linear filtering after conversion to
half floats; (4) deflate keeps it small and Pages serves image/png as is. KTX2 is not used: the data are
precise scalars, not colour, and no KTX tooling is installed.

Heights come from the float LOLA GeoTIFF when it is present (``--dem``; the pack's height_5m.png is quantised to
0.5 m, too coarse to differentiate at 5 m) and from the pack PNG otherwise; the manifest records which, with its
sha256. Memory: the 5 m grid is read as float32 and reduced in row blocks; the 20 m work arrays are 2.5 MB.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import math
import os
import struct
import sys
import time
import zlib
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from lunarsim import terrain as T  # noqa: E402

ASSETS_FORMAT = "lunarsim-terrain-assets"
ASSETS_VERSION = 1
N_SECTORS = 64
SECTORS_PER_FILE = 4
H_OBS_M = 1.0                 # eye height of the world shader (site/src/world/scene.js visFrag: h0 = height + 1.0)
ANGLE_STEP_DEG = 0.05
ANGLE_OFFSET_DEG = 90.0
PATCH_M = 2000.0
PATCH_SITES = ("BASE", "PAD_A")
PATCH_STANDOFF = "1"          # sites.json pad set used by the world page by default (site/src/world/layout.js)
PATCH_Z_SCALE = 0.05          # m per unit for the 5 m height patches
DENSE_M = 4000.0              # ray steps every post out to this distance ...
FAR_RATIO = 1.005             # ... then each step 0.5 % longer than the last
BUDGET_BYTES = 30 * 1024 * 1024
SUN_EL_DEG = 1.5              # as site/src/world/scene.js
SUN_RADIUS_DEG = 0.267
VALIDATION_AZ = (0.0, 90.0, 180.0, 270.0)       # the PSR rule's azimuths (sites.json), exact sectors
VALIDATION_AZ_OFF = (30.0, 120.0, 210.0, 300.0)  # between sectors: tests the interpolation


# ---------------------------------------------------------------------------------------------------------
# PNG codec (16-bit multi-channel PNGs; Pillow cannot write them). Same byte layout the site's reader expects.
# ---------------------------------------------------------------------------------------------------------
_PNG_SIG = b"\x89PNG\r\n\x1a\n"
_CTYPE = {1: 0, 2: 4, 3: 2, 4: 6}        # channels -> PNG colour type (grey, grey+alpha, RGB, RGBA)


def _chunk(kind: bytes, body: bytes) -> bytes:
    return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)


def _filter_block(x: np.ndarray, prev: np.ndarray, bpp: int) -> np.ndarray:
    """Filter rows (int16 array, one row per line) with the per-row best of PNG filters 0-4."""
    a = np.zeros_like(x)
    a[:, bpp:] = x[:, :-bpp]
    b = np.vstack([prev[None, :], x[:-1]])
    c = np.zeros_like(x)
    c[:, bpp:] = b[:, :-bpp]
    p = a + b - c
    pa, pb, pc = np.abs(p - a), np.abs(p - b), np.abs(p - c)
    paeth = np.where((pa <= pb) & (pa <= pc), a, np.where(pb <= pc, b, c))
    cands = np.stack([x, x - a, x - b, x - ((a + b) >> 1), x - paeth]) & 255     # (5, rows, stride)
    signed = np.minimum(cands, 256 - cands)
    best = signed.sum(axis=2).argmin(axis=0)                                     # min-sum-of-abs heuristic
    rows = np.arange(x.shape[0])
    out = np.empty((x.shape[0], x.shape[1] + 1), dtype=np.uint8)
    out[:, 0] = best
    out[:, 1:] = cands[best, rows]
    return out


def write_png(path: str, a: np.ndarray, level: int = 9) -> None:
    """Write a uint8 or uint16 array (rows, cols) or (rows, cols, channels) as a PNG (big-endian samples)."""
    a = np.asarray(a)
    if a.ndim == 2:
        a = a[:, :, None]
    rows, cols, ch = a.shape
    if a.dtype == np.uint16:
        depth, raw = 16, a.astype(">u2").view(np.uint8).reshape(rows, cols * ch * 2)
    elif a.dtype == np.uint8:
        depth, raw = 8, np.ascontiguousarray(a).reshape(rows, cols * ch)
    else:
        raise TypeError(f"write_png needs uint8 or uint16, got {a.dtype}")
    bpp = ch * depth // 8
    comp = zlib.compressobj(level)
    parts = []
    prev = np.zeros(raw.shape[1], dtype=np.int16)
    for r0 in range(0, rows, 128):                                               # row blocks bound the memory
        x = raw[r0:r0 + 128].astype(np.int16)
        parts.append(comp.compress(_filter_block(x, prev, bpp).tobytes()))
        prev = x[-1]
    parts.append(comp.flush())
    ihdr = struct.pack(">IIBBBBB", cols, rows, depth, _CTYPE[ch], 0, 0, 0)
    with open(path, "wb") as f:
        f.write(_PNG_SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", b"".join(parts)) + _chunk(b"IEND", b""))


def read_png(path: str) -> np.ndarray:
    """Read a non-interlaced 8/16-bit grey, grey+alpha, RGB or RGBA PNG exactly. 2-D for one channel."""
    with open(path, "rb") as f:
        b = f.read()
    if b[:8] != _PNG_SIG:
        raise ValueError(f"{path}: not a PNG")
    off, idat, hdr = 8, [], None
    while off < len(b):
        n = struct.unpack(">I", b[off:off + 4])[0]
        kind, body = b[off + 4:off + 8], b[off + 8:off + 8 + n]
        if kind == b"IHDR":
            hdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat.append(body)
        elif kind == b"IEND":
            break
        off += 12 + n
    cols, rows, depth, ctype, _, _, interlace = hdr
    ch = {0: 1, 4: 2, 2: 3, 6: 4}[ctype]
    if interlace or depth not in (8, 16):
        raise ValueError(f"{path}: unsupported PNG (depth {depth}, interlace {interlace})")
    bpp = ch * depth // 8
    stride = cols * bpp
    raw = np.frombuffer(zlib.decompress(b"".join(idat)), dtype=np.uint8).reshape(rows, stride + 1)
    out = np.empty((rows, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.int32)
    for y in range(rows):
        ft, row = raw[y, 0], raw[y, 1:].astype(np.int32)
        if ft == 0:
            cur = row
        elif ft == 1:
            cur = np.cumsum(row.reshape(cols, bpp), axis=0).reshape(-1) & 255
        elif ft == 2:
            cur = (row + prev) & 255
        elif ft in (3, 4):                                   # sequential within the row: plain Python ints
            r, pv, c = row.tolist(), prev.tolist(), [0] * stride
            if ft == 3:
                for i in range(stride):
                    c[i] = (r[i] + (((c[i - bpp] if i >= bpp else 0) + pv[i]) >> 1)) & 255
            else:
                for i in range(stride):
                    a, cc = (c[i - bpp], pv[i - bpp]) if i >= bpp else (0, 0)
                    b = pv[i]
                    p = a + b - cc
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - cc)
                    c[i] = (r[i] + (a if pa <= pb and pa <= pc else (b if pb <= pc else cc))) & 255
            cur = np.array(c, dtype=np.int32)
        else:
            raise ValueError(f"{path}: bad PNG filter {ft} on row {y}")
        out[y] = cur
        prev = cur
    if depth == 16:
        a = out.view(">u2").astype(np.uint16).reshape(rows, cols, ch)
    else:
        a = out.reshape(rows, cols, ch)
    return a[:, :, 0] if ch == 1 else a


# ---------------------------------------------------------------------------------------------------------
# grid maths
# ---------------------------------------------------------------------------------------------------------
def normals(z_north_up: np.ndarray, px: float) -> np.ndarray:
    """Unit normals (rows, cols, 3) in (x east, y north, z up) by central differences (one-sided at edges)."""
    dz_drow, dz_dcol = np.gradient(np.asarray(z_north_up, dtype=np.float64), px)
    gx, gy = dz_dcol, -dz_drow                                   # rows grow southwards
    inv = 1.0 / np.sqrt(gx * gx + gy * gy + 1.0)
    return np.stack([-gx * inv, -gy * inv, inv], axis=-1)


def encode_normals(n: np.ndarray) -> np.ndarray:
    return np.clip(np.rint((n + 1.0) * 0.5 * 255.0), 0, 255).astype(np.uint8)


def decode_normals(rgb: np.ndarray) -> np.ndarray:
    n = rgb.astype(np.float64) / 255.0 * 2.0 - 1.0
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def step_schedule(px: float, max_d: float, dense_m: float = DENSE_M, ratio: float = FAR_RATIO) -> np.ndarray:
    """Ray sample distances (m): every post out to dense_m, then geometric steps (never shorter than px)."""
    d, out = px, []
    while d <= max_d + 1e-9:
        out.append(d)
        d = d + px if (d < dense_m or ratio <= 1.0) else max(d * ratio, d + px)
    return np.array(out)


def _snap(v: float) -> float:
    r = round(v)
    return float(r) if abs(v - r) < 1e-9 else v


def horizon_tan(z_north_up: np.ndarray, px: float, az_deg: float, h_obs: float = H_OBS_M,
                curvature: bool = True, distances: Optional[np.ndarray] = None) -> np.ndarray:
    """Max tan(elevation) of the terrain along azimuth az from every post (-inf where no sample in the tile).

    Bilinear samples of the post grid at horizontal distance d along the ray; the fractional offset is the same
    for every post at a given d, so each step is four shifted slices with scalar weights."""
    z = np.asarray(z_north_up, dtype=np.float32)
    rows, cols = z.shape
    if distances is None:
        distances = step_schedule(px, math.hypot(rows, cols) * px)
    a = math.radians(az_deg)
    sa, ca = math.sin(a), math.cos(a)
    z0 = z + np.float32(h_obs)
    best = np.full(z.shape, -np.inf, dtype=np.float32)
    for d in distances:
        fx, fy = _snap(d * sa / px), _snap(-d * ca / px)            # +col = east, +row = south
        ix, iy = math.floor(fx), math.floor(fy)
        wx, wy = fx - ix, fy - iy
        ex, ey = (1 if wx > 0 else 0), (1 if wy > 0 else 0)
        r0, r1 = max(0, -iy), min(rows, rows - iy - ey)
        c0, c1 = max(0, -ix), min(cols, cols - ix - ex)
        if r0 >= r1 or c0 >= c1:
            break                                                    # offsets only grow: nothing left
        s = z[r0 + iy:r1 + iy, c0 + ix:c1 + ix] * np.float32((1 - wx) * (1 - wy))
        if ex:
            s += z[r0 + iy:r1 + iy, c0 + ix + 1:c1 + ix + 1] * np.float32(wx * (1 - wy))
        if ey:
            s += z[r0 + iy + 1:r1 + iy + 1, c0 + ix:c1 + ix] * np.float32((1 - wx) * wy)
        if ex and ey:
            s += z[r0 + iy + 1:r1 + iy + 1, c0 + ix + 1:c1 + ix + 1] * np.float32(wx * wy)
        s -= z0[r0:r1, c0:c1]
        if curvature:
            s -= np.float32(d * d / (2.0 * T.MOON_RADIUS_M))
        s *= np.float32(1.0 / d)
        np.maximum(best[r0:r1, c0:c1], s, out=best[r0:r1, c0:c1])
    return best


def horizon_deg(z_north_up, px, az_deg, **kw) -> np.ndarray:
    """Horizon elevation angle (deg) along azimuth az; NaN where the tile has no terrain in that direction."""
    t = horizon_tan(z_north_up, px, az_deg, **kw)
    out = np.degrees(np.arctan(t.astype(np.float64)))
    out[~np.isfinite(t)] = np.nan
    return out


def encode_horizon(deg: np.ndarray) -> np.ndarray:
    code = np.rint((np.asarray(deg, dtype=np.float64) + ANGLE_OFFSET_DEG) / ANGLE_STEP_DEG)
    code = np.where(np.isfinite(code), np.clip(code, 1, 65535), 0)
    return code.astype(np.uint16)


def decode_horizon(code: np.ndarray) -> np.ndarray:
    deg = code.astype(np.float64) * ANGLE_STEP_DEG - ANGLE_OFFSET_DEG
    deg[code == 0] = np.nan
    return deg


def sector_azimuth(k: int, n: int = N_SECTORS) -> float:
    return k * 360.0 / n


def horizon_at(sectors, az_deg: float, n: Optional[int] = None) -> np.ndarray:
    """Interpolated horizon (deg) at any azimuth from decoded sectors: an array (n, rows, cols) or a dict
    {sector: (rows, cols)} with n given; NaN-safe (NaN = no terrain = open)."""
    n = n or len(sectors)
    f = (az_deg % 360.0) / (360.0 / n)
    k0 = int(math.floor(f)) % n
    k1, t = (k0 + 1) % n, f - math.floor(f)
    h0 = np.nan_to_num(sectors[k0], nan=-ANGLE_OFFSET_DEG)
    h1 = np.nan_to_num(sectors[k1], nan=-ANGLE_OFFSET_DEG)
    return h0 * (1 - t) + h1 * t


def smoothstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def shader_visibility(z_north_up: np.ndarray, post: float, az_deg: float, el_deg: float = SUN_EL_DEG,
                      sun_radius_deg: float = SUN_RADIUS_DEG) -> np.ndarray:
    """Port of the world page's sun-visibility pass (site/src/world/scene.js visFrag), in float32 like the GPU:
    eye 1 m above the post, 110 nearest-texel samples at d = post * 1.07^i, no Moon curvature, max atan,
    smoothstep over the solar disc. Returns visibility in [0, 1]."""
    z = np.asarray(z_north_up, dtype=np.float32)
    rows, cols = z.shape
    a = math.radians(az_deg)
    dc, dr = np.float32(math.sin(a)), np.float32(-math.cos(a))
    h0 = z + np.float32(1.0)
    max_ang = np.full(z.shape, -1.0, dtype=np.float32)
    d = np.float32(post)
    for _ in range(110):
        oc = int(math.floor(np.float32(0.5) + dc * (d / np.float32(post))))
        orr = int(math.floor(np.float32(0.5) + dr * (d / np.float32(post))))
        r0, r1 = max(0, -orr), min(rows, rows - orr)
        c0, c1 = max(0, -oc), min(cols, cols - oc)
        if r0 < r1 and c0 < c1:
            hh = z[r0 + orr:r1 + orr, c0 + oc:c1 + oc]
            ang = np.arctan2(hh - h0[r0:r1, c0:c1], d)
            np.maximum(max_ang[r0:r1, c0:c1], ang, out=max_ang[r0:r1, c0:c1])
        d = np.float32(d * np.float32(1.07))
    rad = math.radians(sun_radius_deg)
    return smoothstep(-rad, rad, math.radians(el_deg) - max_ang.astype(np.float64))


# ---------------------------------------------------------------------------------------------------------
# inputs, files, provenance
# ---------------------------------------------------------------------------------------------------------
def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def peak_rss_mb() -> Optional[float]:
    """Peak resident set of this process in MB (Windows: PeakWorkingSetSize; POSIX: ru_maxrss)."""
    try:
        import resource
        v = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return v / (1 << 20) if sys.platform == "darwin" else v / 1024.0
    except ImportError:
        pass
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        m = PMC()
        m.cb = ctypes.sizeof(PMC)
        if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(m), m.cb):
            return m.PeakWorkingSetSize / (1 << 20)
    except Exception:
        pass
    return None


def _rel(path: str) -> str:
    """Repository-relative path with forward slashes (absolute when on another drive)."""
    try:
        return os.path.relpath(path, ROOT).replace("\\", "/")
    except ValueError:
        return os.path.abspath(path).replace("\\", "/")


def default_dem(meta: Dict) -> Optional[str]:
    url = meta.get("source", {}).get("url", "")
    p = os.path.join(ROOT, "data", "terrain", "_cache", os.path.basename(url)) if url else ""
    return p if p and os.path.isfile(p) else None


def load_dem5(pack: str, dem: Optional[str], meta: Dict) -> Tuple[np.ndarray, Dict]:
    """The 5 m height grid (float32, row 0 = north) and a provenance record. Prefers the float GeoTIFF."""
    L, enc = meta["layers"]["height_5m"], meta["z_encoding"]
    if dem:
        import rasterio
        with rasterio.open(dem) as ds:
            t = ds.transform
            z = ds.read(1, out_dtype="float32")
            nodata = ds.nodata
        if abs(t.b) > 1e-12 or abs(t.d) > 1e-12 or t.a <= 0 or t.e >= 0:
            raise ValueError(f"{dem}: expected a north-up, unrotated GeoTIFF")
        origin = [float(t.c), float(t.f + t.e * z.shape[0])]
        if origin != [float(v) for v in meta["origin_xy_m"]] or list(z.shape) != list(L["shape"]) \
                or abs(t.a - L["px_m"]) > 1e-9:
            raise ValueError(f"{dem}: extent {origin} {z.shape} does not match the pack {meta['origin_xy_m']} {L['shape']}")
        if nodata is not None and np.any(z == nodata) or not np.all(np.isfinite(z)):
            raise ValueError(f"{dem}: has no-data cells; rebuild the pack (it fills them) and use its PNG")
        return z, {"kind": "geotiff (float)", "file": _rel(dem),
                   "sha256": sha256(dem), "flag": "Measured", "note": "the PGDA LOLA tile the pack was built from"}
    png = os.path.join(pack, L["file"])
    z = (enc["offset_m"] + enc["scale_m_per_unit"] * T._read_png(png).astype(np.float32)).astype(np.float32)
    return z, {"kind": "pack png (quantised)", "file": _rel(png),
               "sha256": sha256(png), "flag": "Measured",
               "note": f"quantised to {enc['scale_m_per_unit']} m; 5 m normals will be noisy"}


def block_mean_rows(z: np.ndarray, k: int, block: int = 64) -> np.ndarray:
    """k x k block mean computed over row blocks (bounded temporaries), float32 result."""
    r, c = (z.shape[0] // k) * k, (z.shape[1] // k) * k
    out = np.empty((r // k, c // k), dtype=np.float32)
    for i in range(0, r // k, block):
        j = min(r // k, i + block)
        out[i:j] = z[i * k:j * k, :c].reshape(j - i, k, c // k, k).mean(axis=(1, 3), dtype=np.float64)
    return out


def patch_window(xy: Sequence[float], px: float, size_m: float, grid_shape: Tuple[int, int]) -> Tuple[int, int, int]:
    """(row0, col0, n) of a size_m square of px cells centred on xy, snapped to the grid and kept inside it."""
    rows, cols = grid_shape
    n = int(round(size_m / px))
    c0 = int(round(xy[0] / px - n / 2))
    r0 = int(round((rows * px - xy[1]) / px - n / 2))                 # row 0 = north edge
    c0, r0 = min(max(c0, 0), cols - n), min(max(r0, 0), rows - n)
    return r0, c0, n


def patch_sites(pack: str) -> List[Tuple[str, List[float]]]:
    with open(os.path.join(pack, "sites.json"), encoding="utf-8") as f:
        s = json.load(f)
    pos = {x["id"]: x["xy_m"] for x in s["sites"]}
    pos.update(s.get("pads", {}).get(PATCH_STANDOFF, {}))
    return [(k, pos[k]) for k in PATCH_SITES if k in pos]


def parse_files(spec: Optional[str], n_files: int) -> List[int]:
    if not spec:
        return list(range(n_files))
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out.extend(range(int(a), int(b or a) + 1))
    bad = [j for j in out if not 0 <= j < n_files]
    if bad:
        raise ValueError(f"horizon files {bad} out of range 0-{n_files - 1}")
    return sorted(set(out))


def horizon_file(j: int) -> str:
    return f"horizon_20m_{j:02d}.png"


# ---------------------------------------------------------------------------------------------------------
# build, validate, manifest
# ---------------------------------------------------------------------------------------------------------
def build(pack: str, out: str, dem: Optional[str] = "auto", files: Optional[str] = None, n_sectors: int = N_SECTORS,
          skip_static: bool = False, dense_m: float = DENSE_M, far_ratio: float = FAR_RATIO, log=print) -> Dict:
    t0 = time.time()
    with open(os.path.join(pack, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    if n_sectors % SECTORS_PER_FILE:
        raise ValueError(f"n_sectors must be a multiple of {SECTORS_PER_FILE}")
    os.makedirs(out, exist_ok=True)
    if dem == "auto":
        dem = default_dem(meta)
    z5, src = load_dem5(pack, dem, meta)
    px5 = float(meta["layers"]["height_5m"]["px_m"])
    k = int(round(meta["layers"]["height_20m"]["px_m"] / px5))
    z20 = block_mean_rows(z5, k)
    px20 = px5 * k
    log(f"heights from {src['kind']} {src['file']}; 20 m grid {z20.shape}")

    if not skip_static:
        write_png(os.path.join(out, "normal_20m.png"), encode_normals(normals(z20, px20)))
        for site, xy in patch_sites(pack):
            r0, c0, n = patch_window(xy, px5, PATCH_M, z5.shape)
            lo_r, lo_c = max(r0 - 1, 0), max(c0 - 1, 0)                 # one-cell margin: central differences inside
            hi_r, hi_c = min(r0 + n + 1, z5.shape[0]), min(c0 + n + 1, z5.shape[1])
            nn = normals(z5[lo_r:hi_r, lo_c:hi_c], px5)[r0 - lo_r:r0 - lo_r + n, c0 - lo_c:c0 - lo_c + n]
            write_png(os.path.join(out, f"normal_5m_{site}.png"), encode_normals(nn))
            zp = z5[r0:r0 + n, c0:c0 + n].astype(np.float64)
            off = math.floor(float(zp.min()))
            code = np.rint((zp - off) / PATCH_Z_SCALE)
            if code.max() > 65535:
                raise ValueError(f"{site}: patch relief too large for {PATCH_Z_SCALE} m/unit")
            write_png(os.path.join(out, f"height_5m_{site}.png"), code.astype(np.uint16))
            with open(os.path.join(out, f"patch_{site}.json"), "w", encoding="utf-8") as f:
                json.dump({"site": site, "row0": r0, "col0": c0, "n": n, "px_m": px5, "z_offset_m": off,
                           "z_scale_m_per_unit": PATCH_Z_SCALE}, f)
            log(f"patch {site}: rows {r0}-{r0 + n - 1}, cols {c0}-{c0 + n - 1} (5 m), z offset {off} m")

    n_files = n_sectors // SECTORS_PER_FILE
    dist = step_schedule(px20, math.hypot(*z20.shape) * px20, dense_m, far_ratio)
    for j in parse_files(files, n_files):
        t1 = time.time()
        planes = []
        for s in range(SECTORS_PER_FILE):
            kk = j * SECTORS_PER_FILE + s
            planes.append(encode_horizon(horizon_deg(z20, px20, sector_azimuth(kk, n_sectors), distances=dist)))
        write_png(os.path.join(out, horizon_file(j)), np.stack(planes, axis=-1))
        log(f"{horizon_file(j)}: sectors {j * SECTORS_PER_FILE}-{j * SECTORS_PER_FILE + 3} "
            f"({time.time() - t1:.1f} s, {len(dist)} steps per ray)")
    params = {"n_sectors": n_sectors, "h_obs_m": H_OBS_M, "dense_m": dense_m, "far_ratio": far_ratio,
              "steps_per_ray": int(len(dist)), "curvature": True}
    man = write_manifest(pack, out, meta, src, params, n_sectors)
    rss = peak_rss_mb()
    log(f"done in {time.time() - t0:.1f} s; peak RSS {rss:.0f} MB" if rss else f"done in {time.time() - t0:.1f} s")
    return man


def load_horizon(out: str, n_sectors: int = N_SECTORS, sectors: Optional[Iterable[int]] = None) -> Dict[int, np.ndarray]:
    """Horizon sectors decoded to degrees, {sector: (rows, cols) float32}; all of them unless `sectors` is given
    (only the files holding those sectors are read)."""
    want = set(range(n_sectors)) if sectors is None else {k % n_sectors for k in sectors}
    out_d: Dict[int, np.ndarray] = {}
    for j in sorted({k // SECTORS_PER_FILE for k in want}):
        a = read_png(os.path.join(out, horizon_file(j)))
        for s in range(SECTORS_PER_FILE):
            if j * SECTORS_PER_FILE + s in want:
                out_d[j * SECTORS_PER_FILE + s] = decode_horizon(a[:, :, s]).astype(np.float32)
    return out_d


def bracketing_sectors(az_deg: float, n: int = N_SECTORS) -> Tuple[int, int]:
    k0 = int(math.floor((az_deg % 360.0) / (360.0 / n))) % n
    return k0, (k0 + 1) % n


def validate(pack: str, out: str, dem: Optional[str] = "auto", log=print) -> Dict:
    """Agreement of the horizon map with the world page's sun-visibility shader (ported), lit vs shadowed at the
    20 m posts, sun at 1.5 deg, for 4 sector azimuths and 4 in-between azimuths. Also isolates the causes:
    the same comparison with curvature off, and the dense-vs-scheduled ray difference for one azimuth."""
    with open(os.path.join(out, "manifest.json"), encoding="utf-8") as f:
        man = json.load(f)
    with open(os.path.join(pack, "meta.json"), encoding="utf-8") as f:
        meta = json.load(f)
    n = man["horizon"]["n_sectors"]
    need = [k for az in VALIDATION_AZ + VALIDATION_AZ_OFF for k in bracketing_sectors(az, n)]
    H = load_horizon(out, n, need + [n // 4])
    L, enc = meta["layers"]["height_20m"], meta["z_encoding"]
    z20png = (enc["offset_m"] + enc["scale_m_per_unit"]
              * T._read_png(os.path.join(pack, L["file"])).astype(np.float64)).astype(np.float32)
    px20 = float(L["px_m"])
    if dem == "auto":
        dem = default_dem(meta)
    z5, _ = load_dem5(pack, dem, meta)
    z20 = block_mean_rows(z5, int(round(px20 / meta["layers"]["height_5m"]["px_m"])))
    del z5
    el = SUN_EL_DEG
    rows = []
    for az in VALIDATION_AZ + VALIDATION_AZ_OFF:
        vis_s = shader_visibility(z20png, px20, az, el)
        h = horizon_at(H, az, n)
        lit_h, lit_s = h < el, vis_s > 0.5
        rad = math.radians(SUN_RADIUS_DEG)
        vis_h = smoothstep(-rad, rad, np.radians(el - h))
        row = {"az_deg": az, "sector": az in VALIDATION_AZ, "agree_lit": float(np.mean(lit_h == lit_s)),
               "lit_share_map": float(lit_h.mean()), "lit_share_shader": float(lit_s.mean()),
               "map_lit_shader_dark": float(np.mean(lit_h & ~lit_s)),
               "map_dark_shader_lit": float(np.mean(~lit_h & lit_s)),
               "mean_abs_vis_diff": float(np.mean(np.abs(vis_h - vis_s)))}
        exact = np.nan_to_num(horizon_deg(z20, px20, az), nan=-ANGLE_OFFSET_DEG) < el     # a fresh ray at this azimuth
        row["agree_map_vs_exact_ray"] = float(np.mean(lit_h == exact))
        row["agree_shader_vs_exact_ray"] = float(np.mean(lit_s == exact))
        if az in VALIDATION_AZ:          # cause isolation, exact sectors only (fresh rays, not the stored file)
            h_nc = horizon_deg(z20png, px20, az, curvature=False)
            row["agree_lit_no_curvature_same_heights"] = float(np.mean((np.nan_to_num(h_nc, nan=-90) < el) == lit_s))
        rows.append(row)
        log(f"az {az:5.1f}: map vs shader {100 * row['agree_lit']:.2f} %; vs an exact ray: map "
            f"{100 * row['agree_map_vs_exact_ray']:.2f} %, shader {100 * row['agree_shader_vs_exact_ray']:.2f} % "
            f"(lit: map {100 * row['lit_share_map']:.1f} %, shader {100 * row['lit_share_shader']:.1f} %)"
            + (f"; no-curvature same heights {100 * row['agree_lit_no_curvature_same_heights']:.2f} %"
               if "agree_lit_no_curvature_same_heights" in row else ""))
    dense = horizon_deg(z20, px20, 90.0, distances=step_schedule(px20, math.hypot(*z20.shape) * px20, 1e9, 1.0))
    sched = horizon_deg(z20, px20, 90.0)
    dd = np.abs(dense - sched)[np.isfinite(dense)]
    sched_err = {"az_deg": 90.0, "max_abs_deg": float(dd.max()), "p999_abs_deg": float(np.percentile(dd, 99.9)),
                 "share_over_0p05_deg": float(np.mean(dd > ANGLE_STEP_DEG))}
    log(f"dense vs scheduled rays (az 90): max {sched_err['max_abs_deg']:.3f} deg, p99.9 {sched_err['p999_abs_deg']:.3f} deg")
    stored = H[n // 4]                                   # sector at azimuth 90
    if stored is not None:
        q = np.abs(np.nan_to_num(stored, nan=0) - np.nan_to_num(sched, nan=0))
        sched_err["stored_vs_fresh_max_abs_deg"] = float(q.max())
        log(f"stored sector {n // 4} vs fresh rays: max {q.max():.3f} deg (quantisation 0.025 deg)")
    v = {"sun_el_deg": el, "sun_radius_deg": SUN_RADIUS_DEG, "reference": "port of site/src/world/scene.js visFrag "
         "on height_20m.png (eye +1 m, 110 nearest samples at x1.07 steps, no curvature)", "rows": rows,
         "min_agree_sector_az": min(r["agree_lit"] for r in rows if r["sector"]),
         "min_agree_off_sector_az": min(r["agree_lit"] for r in rows if not r["sector"]),
         "min_agree_map_vs_exact_ray": min(r["agree_map_vs_exact_ray"] for r in rows),
         "min_agree_shader_vs_exact_ray": min(r["agree_shader_vs_exact_ray"] for r in rows),
         "exact_ray": "a fresh ray-march at the test azimuth (same heights, curvature and step schedule as the map, "
                      "no interpolation, no quantisation)",
         "schedule_check": sched_err, "time": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()}
    man["validation"] = v
    with open(os.path.join(out, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    rss = peak_rss_mb()
    if rss:
        log(f"peak RSS {rss:.0f} MB")
    return v


def _entry(out: str, name: str, role: str, shape, encoding: Dict, **kw) -> Dict:
    p = os.path.join(out, name)
    d = {"file": name, "role": role, "shape": list(shape), "encoding": encoding, "bytes": os.path.getsize(p),
         "sha256": sha256(p)}
    d.update(kw)
    return d


def write_manifest(pack: str, out: str, meta: Dict, src: Dict, params: Dict, n_sectors: int) -> Dict:
    rows, cols = meta["layers"]["height_20m"]["shape"]
    px20 = float(meta["layers"]["height_20m"]["px_m"])
    size = meta["size_m"]
    nrm = {"type": "RGB8", "value": "round((n + 1) / 2 * 255)", "frame": "x east, y north, z up (unit normal)"}
    files = []
    if os.path.isfile(os.path.join(out, "normal_20m.png")):
        files.append(_entry(out, "normal_20m.png", "normals", [rows, cols, 3], nrm, px_m=px20,
                            bounds_m=[0.0, 0.0, size[0], size[1]], note="central differences on the 20 m block mean"))
    patches = []
    for site, _ in patch_sites(pack):
        pj = os.path.join(out, f"patch_{site}.json")
        if not os.path.isfile(pj):
            continue
        with open(pj, encoding="utf-8") as f:
            p = json.load(f)
        px5, n = p["px_m"], p["n"]
        x0, y1 = p["col0"] * px5, size[1] - p["row0"] * px5
        bounds = [x0, y1 - n * px5, x0 + n * px5, y1]
        files.append(_entry(out, f"normal_5m_{site}.png", "normals", [n, n, 3], nrm, px_m=px5, bounds_m=bounds,
                            site=site, note="central differences on the 5 m grid"))
        files.append(_entry(out, f"height_5m_{site}.png", "height", [n, n],
                            {"type": "uint16 grey", "value": "z_m = z_offset_m + z_scale_m_per_unit * v",
                             "z_offset_m": p["z_offset_m"], "z_scale_m_per_unit": p["z_scale_m_per_unit"]},
                            px_m=px5, bounds_m=bounds, site=site, note="LOD 2: 5 m posts (pixel centres)"))
        patches.append({"site": site, "bounds_m": bounds, "pixel_window_5m": {"row0": p["row0"], "col0": p["col0"],
                                                                           "n": n}})
    hz = {"type": "RGBA16 (16-bit per channel, big-endian PNG samples)",
          "value": f"angle_deg = {ANGLE_STEP_DEG} * v - {ANGLE_OFFSET_DEG:g}; v = 0 means no terrain in the tile",
          "channels": "file jj: R, G, B, A = sectors 4jj, 4jj+1, 4jj+2, 4jj+3"}
    nfiles = n_sectors // SECTORS_PER_FILE
    for j in range(nfiles):
        if os.path.isfile(os.path.join(out, horizon_file(j))):
            files.append(_entry(out, horizon_file(j), "horizon", [rows, cols, SECTORS_PER_FILE], hz, px_m=px20,
                                bounds_m=[0.0, 0.0, size[0], size[1]],
                                sectors=list(range(j * SECTORS_PER_FILE, (j + 1) * SECTORS_PER_FILE))))
    total = sum(f["bytes"] for f in files)
    base20 = os.path.join(pack, meta["layers"]["height_20m"]["file"])
    man = {
        "format": ASSETS_FORMAT, "version": ASSETS_VERSION, "terrain": meta["site_id"],
        "pack": {"meta_sha256": sha256(os.path.join(pack, "meta.json")),
                 "frame": meta["frame"], "size_m": size, "origin_xy_m": meta["origin_xy_m"]},
        "heights_from": src,
        "lods": [
            {"level": 1, "px_m": px20, "file": "../" + meta["layers"]["height_20m"]["file"], "sha256": sha256(base20),
             "note": "existing pack layer (z encoding in ../meta.json); not duplicated"},
            {"level": 2, "px_m": float(meta["layers"]["height_5m"]["px_m"]),
             "files": [f"height_5m_{p['site']}.png" for p in patches], "patches": patches,
             "note": f"{PATCH_M / 1000:g} x {PATCH_M / 1000:g} km around BASE and PAD_A (sites.json pad set "
                     f"'{PATCH_STANDOFF}', the world page's default)"},
        ],
        "horizon": {"n_sectors": n_sectors, "sector_az_deg": f"k * {360.0 / n_sectors:g} (sector centre; grid azimuth, "
                    "0 = +y, 90 = +x)", "interpolation": "linear between the two nearest sectors",
                    "angle_step_deg": ANGLE_STEP_DEG, "observer_height_m": H_OBS_M,
                    "moon_radius_m": T.MOON_RADIUS_M, "posts": "20 m post centres of height_20m (row 0 = north)",
                    "outside_tile": "NOT included: rays stop at the 16 km tile edge (R-1 extends this)",
                    "flag": "Modelled (ray-marched from Measured LOLA heights)", "params": params},
        "files": files,
        "total_bytes": total, "budget_bytes": BUDGET_BYTES, "within_budget": total <= BUDGET_BYTES,
        "generated": {"tool": "tools/terrain_assets.py", "commit": T._git_sha(),
                      "time": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()},
    }
    old = os.path.join(out, "manifest.json")
    if os.path.isfile(old):                     # keep an earlier validation if the files it checked are unchanged
        with open(old, encoding="utf-8") as f:
            prev = json.load(f)
        same = {f["file"]: f["sha256"] for f in prev.get("files", [])} == {f["file"]: f["sha256"] for f in files}
        if same and "validation" in prev:
            man["validation"] = prev["validation"]
    with open(old, "w", encoding="utf-8") as f:
        json.dump(man, f, indent=1)
    return man


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/terrain_assets.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "validate"):
        p = sub.add_parser(name)
        p.add_argument("--pack", default=os.path.join("data", "terrain", "connecting_ridge"))
        p.add_argument("--out", default=None, help="output folder (default: <pack>/v2)")
        p.add_argument("--dem", default="auto", help="float GeoTIFF of the tile ('auto': data/terrain/_cache if "
                                                     "present; 'none': use the pack's height_5m.png)")
        if name == "build":
            p.add_argument("--files", default=None, help="horizon files to compute, e.g. 0-7 or 3,5 (default: all)")
            p.add_argument("--skip-static", action="store_true", help="do not rewrite the normal maps and patches")
    a = ap.parse_args(argv)
    out = a.out or os.path.join(a.pack, "v2")
    dem = None if a.dem == "none" else a.dem
    if a.cmd == "build":
        man = build(a.pack, out, dem, a.files, skip_static=a.skip_static)
        for f in man["files"]:
            print(f"  {f['file']:24s} {f['bytes'] / 1024:9.1f} KB")
        print(f"  total {man['total_bytes'] / 2**20:.2f} MB (budget {BUDGET_BYTES / 2**20:.0f} MB)")
    else:
        v = validate(a.pack, out, dem)
        print(f"minimum agreement with the shader: {100 * v['min_agree_sector_az']:.2f} % at sector azimuths, "
              f"{100 * v['min_agree_off_sector_az']:.2f} % between sectors; with an exact ray: map "
              f"{100 * v['min_agree_map_vs_exact_ray']:.2f} %, shader {100 * v['min_agree_shader_vs_exact_ray']:.2f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
