"""B-70 (Lunar ATC): robot-to-robot radio visibility on the Connecting Ridge (data product).

    python tools/atc/mesh.py pairs --part i --parts N   # terrain profiles of a share of the point pairs (cached in
                                                        # .cache/atc/, resumable: rerun a part until it says done)
    python tools/atc/mesh.py build                      # -> data/atc/connecting_ridge/mesh-v1.json.gz (+ .sha256),
                                                        #    results/ATC_mesh.json

Each step is single process with --max-seconds 540 (default).

Points: the route samples of the engine's samples file (earth_link-v1-samples, 2,421 samples). Samples 0-16 are the
sites and the pads (their `id`), so every site and pad point is a sample and a point index is a sample index. The base
computer is BASE (sample 0) with its antenna on the 10 m mast.

For every pair of points within MAX_D_M and each antenna height combination, from the terrain profile (5 m stations,
bilinear 5 m heights, Moon curvature as the chord bulge s (L - s) / 2R; the arithmetic of Terrain.los_clearance_m and
tools/comms/parking.los_batch):
- the straight-line distance d;
- the terrain clearance of the ray, min over the inner stations of (ray height - ground), m; line of sight when it is
  > margin (Terrain.line_of_sight: > 0), stored at 0 m and at a 1 m margin;
- the first-Fresnel-zone clearance ratio at the worst point, min over the inner stations of clearance / r_F1 with
  r_F1 = sqrt(lambda s (L - s) / L), at 2.4 GHz and 400 MHz.
Pairs (i < j): combinations (h_i, h_j) = (2.5, 2.5), (2.5, 1.0), (1.0, 2.5), (1.0, 1.0), so 2.5-1.0 is kept in both
orientations. BASE mast pairs (BASE, j): (10, 2.5) and (10, 1.0). A pair with no inner station (d <= 5 m, including
the two coincident samples) has clearance min(h_i, h_j) (los_clearance_m; for d = 0 it returns h_a, made symmetric
here) and an unlimited Fresnel ratio.
"""
from __future__ import annotations

import argparse
import base64
import gzip
import hashlib
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p_ in (ROOT, os.path.join(ROOT, "tools", "comms")):
    if p_ not in sys.path:
        sys.path.insert(0, p_)

import earth_link as EL  # noqa: E402
from lunarsim.terrain import MOON_RADIUS_M, _bilinear  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc")
OUT = os.path.join(ROOT, "data", "atc", "connecting_ridge", "mesh-v1.json.gz")
SUMMARY = os.path.join(ROOT, "results", "ATC_mesh.json")
SAMPLES_V1 = EL.SAMPLES_V1

ANT_ROVER_M = EL.ANT_ROVER_M      # Assumed (B-40), Spec (B-70 task): rover antenna 2.5 m
ANT_SMALL_M = 1.0                 # Spec (B-70 task): small robot antenna 1.0 m
ANT_MAST_M = EL.ANT_MAST_M        # Assumed (B-40), Spec (B-70 task): base computer antenna on the 10 m mast at BASE
COMBOS = ((ANT_ROVER_M, ANT_ROVER_M), (ANT_ROVER_M, ANT_SMALL_M), (ANT_SMALL_M, ANT_ROVER_M), (ANT_SMALL_M, ANT_SMALL_M))
MAST_COMBOS = ((ANT_MAST_M, ANT_ROVER_M), (ANT_MAST_M, ANT_SMALL_M))
MAX_D_M = 10000.0                 # Spec (B-70 task): every pair within 10 km
STEP_M = 5.0                      # as Terrain.los_clearance_m (5 m stations on the 5 m grid)
MARGINS_M = (0.0, 1.0)            # Spec (B-70 task): line of sight at 0 m and at a 1 m clearance margin
C_LIGHT = 299_792_458.0           # Spec: speed of light, m/s
FREQS_HZ = (2.4e9, 400e6)         # Spec (B-70 task): first Fresnel zone at 2.4 GHz and 400 MHz
BANDS_KM = ((0.0, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 5.0), (5.0, 10.0))   # Spec (B-70 task)
RANGES_KM = (1.0, 2.0, 5.0, 10.0)                                          # Spec (B-70 task)
ISOLATION_KM = 2.0                                                          # Spec (B-70 task)
FRESNEL_REPORT = 0.6              # Assumed: the usual 60 % first-zone clearance, reported next to plain LOS
CHUNK = 2_000_000                 # inner stations per numpy batch (~300 MB of temporaries)
BASE_INDEX = 0

CLEAR_UNIT_M = 0.1                # clear_dm = ceil(10 c) - 1: c > m  <=>  clear_dm >= 10 m (exact for whole dm)
FRESNEL_UNIT = 0.01               # fresnel = clip(floor(100 r) + 1, 0, 255): r >= k / 100 <=> fresnel >= k + 1


# ---------------------------------------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------------------------------------
class GridTerrain:
    """A synthetic height grid with Terrain.height's interface (cell-centred, row 0 = south, bilinear)."""

    def __init__(self, z_south_up: np.ndarray, px_m: float):
        self.z, self.px = np.asarray(z_south_up, dtype=np.float64), float(px_m)

    def height(self, x, y):
        return _bilinear(self.z, self.px, x, y)


def wavelengths() -> Tuple[float, ...]:
    return tuple(C_LIGHT / f for f in FREQS_HZ)


def pair_profiles(terrain, P: np.ndarray, I: np.ndarray, J: np.ndarray, combos: Sequence[Tuple[float, float]],
                  step_m: float = STEP_M, radius_m: float = MOON_RADIUS_M, z_points: Optional[np.ndarray] = None,
                  chunk: int = CHUNK) -> Tuple[np.ndarray, np.ndarray]:
    """(clearance m, Fresnel ratio at FREQS_HZ[0]) of shape (len(combos), len(I)) for the pairs (P[I[k]], P[J[k]]),
    heights (h at I, h at J) per combo. Stations as Terrain.profile (np.linspace(0, L, ceil(L / step) + 1)); the
    ends' ground from terrain.height at the points; radius_m = inf drops the curvature term."""
    P = np.asarray(P, dtype=np.float64)
    I, J = np.asarray(I, dtype=np.int64), np.asarray(J, dtype=np.int64)
    zP = terrain.height(P[:, 0], P[:, 1]) if z_points is None else np.asarray(z_points, dtype=np.float64)
    lam = C_LIGHT / FREQS_HZ[0]
    K, nc = len(I), len(combos)
    clear, ratio = np.empty((nc, K)), np.empty((nc, K))
    dx, dy = P[J, 0] - P[I, 0], P[J, 1] - P[I, 1]
    L = np.hypot(dx, dy)
    n = np.maximum(1, np.ceil(L / step_m)).astype(np.int64)
    m = n - 1                                                   # inner stations
    none = m == 0
    for c, (ha, hb) in enumerate(combos):
        clear[c, none], ratio[c, none] = min(ha, hb), np.inf
    cm = np.cumsum(m)
    k0 = 0
    while k0 < K:
        base = cm[k0 - 1] if k0 else 0
        k1 = max(k0 + 1, int(np.searchsorted(cm, base + chunk, side="right")))
        k1 = min(k1, K)
        sel = np.arange(k0, k1)[~none[k0:k1]]
        if len(sel):
            mc = m[sel]
            off = np.concatenate([[0], np.cumsum(mc)[:-1]])
            rep = np.repeat(np.arange(len(sel)), mc)
            j = np.arange(int(mc.sum()), dtype=np.int64) - off[rep] + 1
            Lr = L[sel][rep]
            s = j * (L[sel] / n[sel])[rep]
            f = s / Lr
            z = terrain.height(P[I[sel], 0][rep] + f * dx[sel][rep], P[I[sel], 1][rep] + f * dy[sel][rep])
            za = zP[I[sel]][rep]
            g = z - (za + (zP[J[sel]][rep] - za) * f)           # ground above the ground chord
            del z, za
            if math.isfinite(radius_m):
                g += s * (Lr - s) / (2 * radius_m)
            rf = np.sqrt(lam * s * (Lr - s) / Lr)
            del j, s, Lr
            for c, (ha, hb) in enumerate(combos):
                cl = ha + (hb - ha) * f - g
                clear[c, sel] = np.minimum.reduceat(cl, off)
                cl /= rf
                ratio[c, sel] = np.minimum.reduceat(cl, off)
            del f, g, rf, cl, rep
        k0 = k1
    return clear, ratio


def encode_clear(c: np.ndarray) -> np.ndarray:
    """int16 decimetres, ceil(10 c) - 1: line of sight at margin m (whole dm) is clear_dm >= round(10 m)."""
    return np.clip(np.ceil(np.asarray(c) * 10.0) - 1, -32768, 32767).astype(np.int16)


def encode_fresnel(r: np.ndarray) -> np.ndarray:
    """uint8 hundredths, floor(100 r) + 1 clipped to 0..255: r >= k / 100 is fresnel >= k + 1 (0 <= k <= 254)."""
    r = np.asarray(r, dtype=np.float64)
    q = np.floor(np.where(np.isfinite(r), r, 1e9) * 100.0) + 1
    return np.clip(q, 0, 255).astype(np.uint8)


def fresnel_pair(ratio_ref: np.ndarray) -> np.ndarray:
    """Encoded ratios at both FREQS_HZ from the ratio at FREQS_HZ[0] (r_F1 scales with sqrt(lambda))."""
    lam = wavelengths()
    return np.stack([encode_fresnel(ratio_ref * math.sqrt(lam[0] / l)) for l in lam], axis=-2)


# ---------------------------------------------------------------------------------------------------------
# inputs
# ---------------------------------------------------------------------------------------------------------
def load_samples() -> Dict[str, Any]:
    with open(SAMPLES_V1, "rb") as f:
        return json.loads(gzip.decompress(f.read()))


def points(sdoc: Dict[str, Any]) -> np.ndarray:
    P = np.array([s["xy_m"] for s in sdoc["samples"]], dtype=np.float64)
    if sdoc["samples"][BASE_INDEX].get("id") != "BASE":
        raise SystemExit("sample 0 of the samples file is not BASE")
    return P


def all_pairs(P: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Every (i < j) within MAX_D_M, ordered by i then j."""
    I, J = np.triu_indices(len(P), k=1)
    d = np.hypot(*(P[J] - P[I]).T)
    keep = d <= MAX_D_M
    return I[keep].astype(np.int64), J[keep].astype(np.int64)


def part_bounds(P: np.ndarray, I: np.ndarray, J: np.ndarray, parts: int) -> List[Tuple[int, int]]:
    """Pair ranges with about equal numbers of profile stations."""
    w = np.maximum(1, np.ceil(np.hypot(*(P[J] - P[I]).T) / STEP_M))
    cw = np.cumsum(w)
    cuts = [0] + [int(np.searchsorted(cw, cw[-1] * p / parts, side="right")) for p in range(1, parts)] + [len(I)]
    return list(zip(cuts[:-1], cuts[1:]))


def part_path(part: int, parts: int) -> str:
    return os.path.join(CACHE, f"mesh_pairs_{part}of{parts}.npz")


# ---------------------------------------------------------------------------------------------------------
# step 1: pairs
# ---------------------------------------------------------------------------------------------------------
def step_pairs(part: int = 0, parts: int = 1, max_seconds: float = 540.0, log=print) -> bool:
    """Profiles of pair range `part` of `parts`; saves progress about every minute; True when the part is done."""
    from lunarsim.terrain import Terrain
    t0 = time.time()
    os.makedirs(CACHE, exist_ok=True)
    P = points(load_samples())
    I, J = all_pairs(P)
    a, b = part_bounds(P, I, J, parts)[part]
    path = part_path(part, parts)
    if os.path.isfile(path):
        z = np.load(path)
        st = {k: z[k] for k in z.files}
        if int(st["range"][0]) != a or int(st["range"][1]) != b:
            raise SystemExit(f"{path}: cached for another pair range; delete it")
    else:
        st = {"range": np.array([a, b]), "next": np.array(a),
              "clear_dm": np.zeros((len(COMBOS), b - a), np.int16),
              "fresnel": np.zeros((len(COMBOS), len(FREQS_HZ), b - a), np.uint8)}
    k = int(st["next"])
    if k >= b:
        log(f"pairs part {part}/{parts}: done ({b - a} pairs)")
        return True
    t = Terrain(EL.PACK)
    zP = t.height(P[:, 0], P[:, 1])
    last = time.time()
    blk = 20000
    while k < b:
        if time.time() - t0 > max_seconds - 45:
            break
        e = min(b, k + blk)
        cl, ra = pair_profiles(t, P, I[k:e], J[k:e], COMBOS, z_points=zP)
        st["clear_dm"][:, k - a:e - a] = encode_clear(cl)
        st["fresnel"][:, :, k - a:e - a] = fresnel_pair(ra)
        k = e
        st["next"] = np.array(k)
        if time.time() - last > 60 or k >= b:
            np.savez(path, **st)
            last = time.time()
    np.savez(path, **st)
    done = k >= b
    log(f"pairs part {part}/{parts}: {k - a}/{b - a} pairs ({time.time() - t0:.0f} s this call)"
        + ("" if done else "; time limit, rerun this part"))
    return done


# ---------------------------------------------------------------------------------------------------------
# step 2: build
# ---------------------------------------------------------------------------------------------------------
def _b64(a: np.ndarray, shuffle: bool = False) -> Dict[str, Any]:
    """An array as little-endian base64; shuffle stores byte 0 of every element, then byte 1, ... (compresses
    better; lunarsim.atc.radio.unb64 reverses it)."""
    a = np.ascontiguousarray(a)
    raw = a.view(np.uint8).reshape(-1, a.dtype.itemsize).T.tobytes() if shuffle else a.tobytes()
    out = {"dtype": a.dtype.str, "shape": list(a.shape), "b64": base64.b64encode(raw).decode("ascii")}
    if shuffle:
        out["shuffle"] = True
    return out


def load_parts() -> Tuple[np.ndarray, np.ndarray, int]:
    import glob
    found = sorted(glob.glob(os.path.join(CACHE, "mesh_pairs_*of*.npz")))
    if not found:
        raise SystemExit("no pair parts in the cache; run `pairs` first")
    parts = {int(os.path.basename(f).split("of")[1].split(".")[0]) for f in found}
    if len(parts) != 1:
        raise SystemExit(f"pair parts of different splits in the cache ({sorted(parts)}); delete the stale ones")
    N = parts.pop()
    zs = []
    for p in range(N):
        path = part_path(p, N)
        if not os.path.isfile(path):
            raise SystemExit(f"part {p}/{N} missing; run `pairs --part {p} --parts {N}`")
        z = np.load(path)
        if int(z["next"]) < int(z["range"][1]):
            raise SystemExit(f"part {p}/{N} incomplete; rerun it")
        zs.append((int(z["range"][0]), z["clear_dm"], z["fresnel"]))
    zs.sort(key=lambda r: r[0])
    return np.concatenate([r[1] for r in zs], axis=1), np.concatenate([r[2] for r in zs], axis=2), N


def clear_deltas(clear_dm: np.ndarray) -> np.ndarray:
    dlt = clear_dm[1:].astype(np.int32) - clear_dm[0].astype(np.int32)
    if dlt.min() < -128 or dlt.max() > 127:
        raise SystemExit(f"clearance deltas {dlt.min()}..{dlt.max()} do not fit int8")
    return dlt.astype(np.int8)


def los_bits(clear_dm: np.ndarray) -> np.ndarray:
    """uint8: bit 2c = LOS at 0 m for combo c, bit 2c + 1 = LOS at 1 m."""
    out = np.zeros(clear_dm.shape[1], np.uint8)
    for c in range(clear_dm.shape[0]):
        for b_, m in enumerate(MARGINS_M):
            out |= ((clear_dm[c] >= round(m / CLEAR_UNIT_M)).astype(np.uint8) << (2 * c + b_))
    return out


def step_build(max_seconds: float = 540.0, log=print) -> Dict[str, Any]:
    from lunarsim.terrain import Terrain
    t0 = time.time()
    sdoc = load_samples()
    P = points(sdoc)
    I, J = all_pairs(P)
    clear_dm, fres, nparts = load_parts()
    if clear_dm.shape[1] != len(I):
        raise SystemExit(f"parts hold {clear_dm.shape[1]} pairs, expected {len(I)}")
    t = Terrain(EL.PACK)
    zP = t.height(P[:, 0], P[:, 1])
    # BASE mast pairs
    Jm = np.arange(1, len(P), dtype=np.int64)
    Im = np.zeros_like(Jm)
    cl_m, ra_m = pair_profiles(t, P, Im, Jm, MAST_COMBOS, z_points=zP)
    mast_clear = encode_clear(cl_m)
    mast_fres = fresnel_pair(ra_m)
    log(f"build: {len(I)} pairs from {nparts} parts, {len(Jm)} mast pairs ({time.time() - t0:.0f} s)")
    checks = cross_checks(t, P, zP, I, J, clear_dm, Jm, cl_m, sdoc)
    log(f"build: checks {json.dumps(checks)}")
    lam = wavelengths()
    doc = {
        "format": "lunarsim-mesh", "version": 1, "terrain": sdoc["terrain"],
        "description": ("Robot-to-robot radio visibility between the route samples of the engine's samples file (writer "
                        "tools/atc/mesh.py, B-70). Point k is sample k (samples 0-16 are the sites and pads); BASE (point "
                        "0) also carries the base computer's antenna on the mast. pairs: every (i < j) within max_d_m, "
                        "ordered by i then j; per antenna combination (h at i, h at j): terrain clearance of the ray and "
                        "the first-Fresnel-zone clearance ratio at the worst point, encoded (see encoding). mast: (BASE "
                        "mast, j) for every other point."),
        "samples_file": {"file": EL._rel(SAMPLES_V1), "sha256": EL.sha256(SAMPLES_V1), "n_samples": len(P)},
        "inputs": {"terrain_height_5m": EL.sha256(os.path.join(EL.PACK, t.meta["layers"]["height_5m"]["file"]))},
        "points": {"n": len(P), "xy_m": [[float(x), float(y)] for x, y in P],
                   "ids": {s["id"]: k for k, s in enumerate(sdoc["samples"]) if s.get("id")},
                   "base": BASE_INDEX},
        "antenna_m": {"rover": ANT_ROVER_M, "small": ANT_SMALL_M, "mast": ANT_MAST_M,
                      "flag": "Spec (B-70 task); rover and mast Assumed in B-40"},
        "rules": {"max_d_m": MAX_D_M, "step_m": STEP_M, "radius_m": MOON_RADIUS_M, "margins_m": list(MARGINS_M),
                  "freqs_hz": list(FREQS_HZ), "wavelengths_m": [round(l, 9) for l in lam],
                  "clearance": "min over the inner stations of the ray height above ground (Moon curvature as the chord "
                               "bulge s (L - s) / 2R); Terrain.los_clearance_m",
                  "los": "clearance > margin (Terrain.line_of_sight)",
                  "fresnel": "min over the inner stations of clearance / sqrt(lambda s (L - s) / L)",
                  "no_inner_station": "d <= step_m: clearance min(h_i, h_j), Fresnel ratio unlimited (255)"},
        "encoding": {"clear_dm": "int16, ceil(10 c) - 1 for clearance c in m: LOS at margin m (whole dm) <=> "
                                 "clear_dm >= 10 m; c lies in (clear_dm / 10, (clear_dm + 1) / 10]",
                     "fresnel": "uint8, clip(floor(100 r) + 1, 0, 255) for ratio r: r >= k / 100 <=> fresnel >= k + 1 "
                                "(0 <= k <= 254); 0 means r < 0; axis 1 follows rules.freqs_hz",
                     "los": "uint8 bit field: bit 2c = LOS at 0 m for combo c, bit 2c + 1 = LOS at 1 m",
                     "clear_dm0": "pairs: clear_dm of combo 0",
                     "clear_dm_delta": "pairs: int8 (combos - 1, n), clear_dm of combo c minus clear_dm of combo 0 "
                                       "(exact; the combos differ by at most the antenna height difference)",
                     "distance": "straight-line distance between points.xy_m (not stored)",
                     "arrays": "little-endian bytes, base64; shape as given; with shuffle the bytes are stored by "
                               "plane (byte 0 of every element, then byte 1, ...)"},
        "pairs": {"n": len(I), "combos": [list(c) for c in COMBOS],
                  "i": _b64(I.astype("<u2")), "j": _b64(J.astype("<u2")),
                  "clear_dm0": _b64(clear_dm[0].astype("<i2"), shuffle=True), "clear_dm_delta": _b64(clear_deltas(clear_dm)),
                  "fresnel": _b64(fres), "los": _b64(los_bits(clear_dm))},
        "mast": {"n": len(Jm), "point": BASE_INDEX, "combos": [list(c) for c in MAST_COMBOS],
                 "j": _b64(Jm.astype("<u2")), "clear_dm": _b64(mast_clear.astype("<i2")), "fresnel": _b64(mast_fres), "los": _b64(los_bits(mast_clear))},
        "checks": checks,
        "generated": {"tool": "tools/atc/mesh.py", "commit": EL._git_sha(),
                      "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    raw = json.dumps(doc, separators=(",", ":")).encode("utf-8")
    with open(OUT, "wb") as f:
        f.write(gzip.compress(raw, 9, mtime=0))
    sha = EL.sha256(OUT)
    with open(OUT + ".sha256", "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{sha}  {os.path.basename(OUT)}\n")
    log(f"build: {EL._rel(OUT)} {os.path.getsize(OUT) / 1e6:.1f} MB (json {len(raw) / 1e6:.1f} MB), sha256 {sha[:12]}")
    summ = summary(doc, sha, time.time() - t0)
    with open(SUMMARY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(summ, f, indent=1)
        f.write("\n")
    log(f"build: {EL._rel(SUMMARY)} ({time.time() - t0:.0f} s)")
    return summ


def cross_checks(t, P, zP, I, J, clear_dm, Jm, cl_m, sdoc, n: int = 300, seed: int = 70) -> Dict[str, Any]:
    """Random pairs against Terrain.los_clearance_m; the mast pairs against the samples file's mast_los."""
    rng = np.random.default_rng(seed)
    pick = rng.choice(len(I), size=min(n, len(I)), replace=False)
    worst, bad = 0.0, 0
    for k in pick:
        for c, (ha, hb) in enumerate(COMBOS):
            ref = t.los_clearance_m(tuple(P[I[k]]), tuple(P[J[k]]), h_a=ha, h_b=hb)
            q = int(clear_dm[c, k])
            if not (q / 10.0 - 1e-6 < ref <= (q + 1) / 10.0 + 1e-6):
                bad += 1
            worst = max(worst, abs(ref - (q + 0.5) / 10.0))
    ml = np.array([bool(s.get("mast_los")) for s in sdoc["samples"]])[Jm]
    dm = np.hypot(*(P[Jm] - P[0]).T)
    ours = (cl_m[0] >= 0) & (dm <= EL.MAST_RANGE_KM * 1000)          # the samples file's rule: >= 0 within 10 km
    return {"terrain_los_clearance_m": {"pairs": len(pick), "combos": len(COMBOS), "outside_encoded_interval": bad,
                                        "max_abs_m_vs_interval_mid": round(worst, 4)},
            "samples_mast_los": {"points": int(len(Jm)), "agree": int((ml == ours).sum()),
                                 "rule": "clearance (2.5 m, 10 m mast) >= 0 within 10 km, as earth_link.sees_mast"}}


# ---------------------------------------------------------------------------------------------------------
# summary
# ---------------------------------------------------------------------------------------------------------
def _share(x: np.ndarray) -> Optional[float]:
    return round(float(x.mean()), 4) if len(x) else None


def summary(doc: Dict[str, Any], sha: str, runtime_s: float) -> Dict[str, Any]:
    from lunarsim.atc.radio import RadioMesh
    rm = RadioMesh(doc=doc)
    N = rm.n
    I, J, d = rm.I, rm.J, rm.d
    md = rm.mast_d
    pos = d > 0
    k_dup = int((~pos).sum())
    out: Dict[str, Any] = {
        "task": "B-70", "file": EL._rel(OUT), "sha256": sha, "n_points": N, "n_pairs": int(len(I)),
        "coincident_pairs": k_dup,
        "note": ("Shares by distance band count pairs with d > 0 (coincident pairs left out); 2.5-1.0 counts both "
                 "orientations (each unordered pair twice); 2.5-10 and 1.0-10 are the BASE mast to every other point. "
                 "LOS = clearance > margin; Fresnel = first-zone ratio >= 0.6 at the worst point (Assumed threshold, "
                 "reported only)."),
        "los_by_distance_band": {}, "connectivity": {}, "isolated": {}, "mast_direct": {},
    }
    bands = [f"{lo:g}-{hi:g} km" for lo, hi in BANDS_KM]

    def band_of(dd):
        return [((dd > lo * 1000) | ((lo == 0) & (dd > 0))) & (dd <= hi * 1000) for lo, hi in BANDS_KM]

    def row(clear_dm, fres, dd):
        r = {}
        for name, msk in zip(bands, band_of(dd)):
            cd, fr = clear_dm[msk], fres[:, msk]
            r[name] = {"n": int(msk.sum()), "los_0m": _share(cd >= 0), "los_1m": _share(cd >= 10),
                       "fresnel_0.6_2.4GHz": _share(fr[0] >= 61), "fresnel_0.6_400MHz": _share(fr[1] >= 61)}
        return r

    C, F = rm.clear_dm, rm.fresnel
    out["los_by_distance_band"]["2.5-2.5"] = row(C[0], F[0], d)
    out["los_by_distance_band"]["2.5-1.0"] = row(np.concatenate([C[1], C[2]]), np.concatenate([F[1], F[2]], axis=1),
                                                 np.concatenate([d, d]))
    out["los_by_distance_band"]["1.0-1.0"] = row(C[3], F[3], d)
    out["los_by_distance_band"]["2.5-10"] = row(rm.mast_clear_dm[0], rm.mast_fresnel[0], md)
    out["los_by_distance_band"]["1.0-10"] = row(rm.mast_clear_dm[1], rm.mast_fresnel[1], md)

    from scipy.sparse.csgraph import connected_components
    for h, lab in ((ANT_ROVER_M, "rover_2.5m"), (ANT_SMALL_M, "small_1.0m")):
        conn = {}
        for R in RANGES_KM:
            G = rm.graph(h, d_max_m=R * 1000, margin_m=0.0)
            ncomp, labels = connected_components(G, directed=False)
            sizes = np.bincount(labels)
            hops = rm.hops(BASE_INDEX, h, d_max_m=R * 1000, margin_m=0.0)
            o = hops[1:]
            conn[f"{R:g} km"] = {
                "components": int(ncomp), "largest_component": int(sizes.max()),
                "base_component": int(sizes[labels[BASE_INDEX]]),
                "singletons": int((sizes == 1).sum()),
                "reach_base_share": {"1 hop": _share(o == 1), "2 hops": _share(o == 2), "3+ hops": _share(o >= 3),
                                     "never": _share(o < 0)},
                "max_hops": int(o.max()) if (o > 0).any() else None,
                "median_hops": float(np.median(o[o > 0])) if (o > 0).any() else None}
        out["connectivity"][lab] = conn
        nb = rm.neighbour_counts(h, d_max_m=ISOLATION_KM * 1000, margin_m=0.0)
        iso = np.where(nb == 0)[0]
        out["isolated"][lab] = {"rule": f"no other point with LOS (0 m) within {ISOLATION_KM:g} km (d > 0), the BASE mast "
                                        "counting as a neighbour", "n": int(len(iso)), "samples": iso.tolist(),
                                "xy_m": [doc["points"]["xy_m"][k] for k in iso]}
        mc = rm.mast_clear_dm[0 if h == ANT_ROVER_M else 1]
        md_los = mc >= 0
        out["mast_direct"][lab] = {
            "within_km": {f"{R:g} km": {"n": int((md_los & (md <= R * 1000)).sum()),
                                        "share_of_points": _share(md_los & (md <= R * 1000)),
                                        "share_of_points_within_range": _share(md_los[md <= R * 1000])}
                          for R in RANGES_KM},
            "no_direct_los_within_2km": rm.mast_j[~md_los & (md <= ISOLATION_KM * 1000)].tolist(),
            "n_no_direct_los": int((~md_los).sum())}
    out["checks"] = doc["checks"]
    out["runtime_s_build"] = round(runtime_s, 1)
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/atc/mesh.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pairs")
    p.add_argument("--part", type=int, default=0)
    p.add_argument("--parts", type=int, default=1)
    sub.add_parser("build")
    for sp_ in sub.choices.values():
        sp_.add_argument("--max-seconds", type=float, default=540.0,
                         help="stop this process after so many seconds (Windows: `timeout` only kills the venv launcher)")
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    if a.cmd == "pairs":
        step_pairs(a.part, a.parts, a.max_seconds)
    elif a.cmd == "build":
        step_build(a.max_seconds)
    rss = EL.peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
