"""Real sun at every site and rover leg (B-44): hourly sunlit fraction of the solar disc, 2028-2031, and the sunlit
windows the engine's night rule reads (opt-in scenario field `illumination`).

    python tools/illumination/sun_link.py ephem                 # SPICE Sun vector from BASE, hourly (.cache/illum)
    python tools/illumination/sun_link.py dem                   # LOLA 80 m DEM, +-260 km around the tile
    python tools/illumination/sun_link.py masks --part 0 --parts 10 [--max-seconds 540]   # full-circle horizons
    python tools/illumination/sun_link.py link                  # -> data/illumination/connecting_ridge/sun_link-v1.json
    python tools/illumination/sun_link.py avgvisib              # check against the PGDA average-illumination map

Method (shared with tools/comms/earth_link.py, whose functions it imports):
  Sun      SPICE spkcpo("SUN", et, MOON_ME, observer BASE, LT+S) with naif0012, pck00011, de440s and the Moon frame
           kernels, hourly from 2028-01-01 00:00 UTC; each point's local azimuth and elevation from its own
           east-north-up frame; apparent radius asin(R_sun / range), R_sun = 695,700 km (IAU 2015 B3 nominal).
  horizon  the exact elevation of the terrain on the sphere, seen from the point, every 0.5 deg of grid bearing
           over the full circle, from the 5 m tile out to 8 km and LOLA LDEM_80S_80MPP_ADJ (80 m) out to 250 km
           (beyond that the Moon's curvature drops any terrain more than 18 km below the local horizontal, so it
           cannot block a Sun that stands at most ~1.6 deg high); linear in bearing between samples.
  disc     visible fraction of the solar disc with the horizon locally straight across it:
           f = 1 - (acos(x) - x sqrt(1 - x^2)) / pi, x = (elevation - horizon) / radius clipped to [-1, 1].
  points   every engine site and pad (each pad standoff) and every 100 m route sample of the 182 rover legs
           (tools/comms points), at 2.5 m above the ground (Assumed: a rover's solar panels / mast; the comms
           antenna height); BASE also at 0 m, 2 m and 10 m for the checks.
  windows  per point and per leg, the hours a criterion holds: any_part (f > 0), half (f >= 0.5), full (f >= 0.999).
           Legs carry two rules: "worst" (lit only when every route sample is) and "most" (lit when at least 80 % of
           the samples are; Assumed: a rover crosses short shadows on its battery). The engine's default night
           rule is "half": below half the solar disc a solar-powered rover is dark (Assumed).
"""
from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import math
import os
import sys
import time
import urllib.request
from typing import Dict, List, Optional

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "comms"))
import earth_link as E  # noqa: E402
from lunarsim.comms import encode_windows, runs, summarize  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "illum")
OUT = os.path.join(ROOT, "data", "illumination", "connecting_ridge", "sun_link-v1.json")
R_SUN_KM = 695_700.0               # Spec: IAU 2015 Resolution B3 nominal solar radius
N_HOURS = E.N_DAYS * 24            # 35,064
BEARING_STEP_DEG = 0.5
FAR_MAX_M = 250_000.0
WINDOW_HALF_M = 260_000.0
CRITERIA = {"any_part": 0.0, "half": 0.5, "full": 0.999}       # lit when f > 0 / f >= 0.5 / f >= 0.999
CRITERIA_TEXT = {"any_part": "some of the solar disc above the local horizon (f > 0)",
                 "half": "at least half of the solar disc above the local horizon (f >= 0.5)",
                 "full": "the whole solar disc above the local horizon (f >= 0.999)"}
DEFAULT_CRITERION = "half"
MOST_SHARE = 0.8                   # leg rule "most": lit when >= 80 % of its samples are (Assumed: short shadows on battery)
LEG_RULES = {"worst": "every route sample of the leg lit (its worst sample)",
             "most": "at least 80 % of the leg's route samples lit (a rover crosses short shadows on its battery)"}
H_PANEL_M = 2.5
CHECK_HEIGHTS = {"BASE_0m": 0.0, "BASE_2m": 2.0, "BASE_10m": 10.0}
GLASER = {"2m": 92.27, "10m": 95.65, "dark_days": [3, 5],
          "source": "Gläser et al. (Connecting Ridge, average illumination at 2 m and 10 m above ground; 3-5 days of "
                    "continuous darkness), as cited in research_notes/Lunar communications and visibility/"
                    "earth_visibility_prior_art.md"}
AVGVISIB_URL = "http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608.IMG"


def _p(*a) -> str:
    return os.path.join(CACHE, *a)


def disc_fraction(el, h, rad) -> np.ndarray:
    """Visible fraction of a disc of angular radius rad (deg) whose centre is at elevation el, horizon at h."""
    x = np.clip((np.asarray(el) - np.asarray(h)) / np.asarray(rad), -1.0, 1.0)
    return 1.0 - (np.arccos(x) - x * np.sqrt(1.0 - x * x)) / math.pi


def sun_topo(S_base_km, P_base_km, P_km, lat, lon):
    """Sun's grid bearing, elevation and apparent radius (deg) from a point, per epoch."""
    S = S_base_km - (P_km - P_base_km)[None, :]
    rng = np.linalg.norm(S, axis=1)
    east, north, up = E.enu(lat, lon)
    az = np.degrees(np.arctan2(S @ east, S @ north)) % 360.0
    el = np.degrees(np.arcsin(S @ up / rng))
    return E.wrap180(az + lon) % 360.0, el, np.degrees(np.arcsin(R_SUN_KM / rng))


def bearings() -> np.ndarray:
    return np.round(np.arange(0.0, 360.0, BEARING_STEP_DEG), 4)


def horizon_at(mask_row: np.ndarray, brg: np.ndarray) -> np.ndarray:
    b = bearings()
    m = np.where(np.isfinite(mask_row), mask_row, -90.0)
    return np.interp(np.asarray(brg) % 360.0, np.append(b, 360.0), np.append(m, m[0]))


# ---------------------------------------------------------------------------------------------------------
def step_ephem(log=print) -> Dict:
    t0 = time.time()
    os.makedirs(CACHE, exist_ok=True)
    kern = E.fetch_kernels()
    sp = E.furnsh_all()
    base = np.load(E.ephem_path())                       # BASE position from the Earth-link run (same point)
    P_base = base["P_base_km"]
    lat, lon = (float(x) for x in base["base_latlon"])
    et0 = sp.str2et(E.START_UTC + " UTC")
    ets = et0 + 3600.0 * np.arange(N_HOURS)
    S = np.empty((N_HOURS, 3))
    for i, et in enumerate(ets):
        st, _ = sp.spkcpo("SUN", float(et), "MOON_ME", "OBSERVER", "LT+S", P_base, "MOON", "MOON_ME")
        S[i] = st[:3]
    brg, el, rad = sun_topo(S, P_base, P_base, lat, lon)
    az_local = (brg - lon) % 360.0
    d_az, d_el = [], []
    for i in range(0, N_HOURS, 97):                      # SPICE's own az/el must agree with ours
        st, _ = sp.azlcpo("ELLIPSOID", "SUN", float(ets[i]), "LT+S", False, True, P_base, "MOON", "MOON_ME")
        d_az.append(abs(E.wrap180(math.degrees(st[1]) - az_local[i])))
        d_el.append(abs(math.degrees(st[2]) - el[i]))
    np.savez(_p("sun_ephem.npz"), et=ets, S_base_km=S, P_base_km=P_base)
    info = {"n": N_HOURS, "step_h": 1, "start_utc": E.START_UTC, "el_range_deg": [float(el.min()), float(el.max())],
            "radius_range_deg": [float(rad.min()), float(rad.max())],
            "azlcpo_check": {"epochs": len(d_az), "max_abs_az_deg": float(max(d_az)), "max_abs_el_deg": float(max(d_el))},
            "kernels": kern, "seconds": round(time.time() - t0, 1)}
    json.dump(info, open(_p("sun_ephem.json"), "w"), indent=1)
    log(f"ephem: {N_HOURS} hours, Sun elevation at BASE {el.min():.2f} to {el.max():.2f} deg, radius "
        f"{rad.min():.4f}-{rad.max():.4f} deg; azlcpo max |d az| {max(d_az):.1e}, |d el| {max(d_el):.1e} deg "
        f"({time.time() - t0:.0f} s)")
    return info


def step_dem(log=print) -> Dict:
    """The LOLA 80 m DEM (the file fetched once by the Earth-link run) within +-260 km of the tile centre."""
    import rasterio
    from rasterio.windows import from_bounds
    os.makedirs(CACHE, exist_ok=True)
    meta, _ = E.load_pack()
    x0, y0 = meta["origin_xy_m"]
    W, H = meta["size_m"]
    cx, cy = x0 + W / 2, y0 + H / 2
    local = os.path.join(E.CACHE, os.path.basename(E.FAR_URL))
    if not os.path.isfile(local):
        raise SystemExit(f"{local} missing: fetch it once (curl -C - -o <file> {E.FAR_URL})")
    t0 = time.time()
    with rasterio.open(local) as ds:
        L, B, R_, T = ds.bounds
        xmin, ymin = max(cx - WINDOW_HALF_M, L), max(cy - WINDOW_HALF_M, B)
        xmax, ymax = min(cx + WINDOW_HALF_M, R_), min(cy + WINDOW_HALF_M, T)
        win = from_bounds(xmin, ymin, xmax, ymax, ds.transform).round_offsets().round_lengths()
        z = ds.read(1, window=win, out_dtype="float32")
        tr = ds.window_transform(win)
    px = float(tr.a)
    np.savez(_p("ldem_80m_full.npz"), z=z, x_west=tr.c, y_north=tr.f, px=px)
    info = {"file": os.path.basename(local), "file_sha256": E.sha256(local), "window_px": [int(win.col_off), int(win.row_off),
            int(win.width), int(win.height)], "window_bounds_m": [float(tr.c), float(tr.f - px * z.shape[0]),
            float(tr.c + px * z.shape[1]), float(tr.f)], "nan_share": float(np.isnan(z).mean()), "seconds": round(time.time() - t0, 1)}
    json.dump(info, open(_p("dem.json"), "w"), indent=1)
    log(f"dem: {z.shape[1]} x {z.shape[0]} px ({z.nbytes / 2**20:.0f} MB), bounds {info['window_bounds_m']}")
    return info


def far_sampler() -> E.GridSampler:
    d = np.load(_p("ldem_80m_full.npz"))
    return E.GridSampler(d["z"], float(d["x_west"]), float(d["y_north"]), float(d["px"]))


def points() -> List[Dict]:
    """The Earth-link points (sites, pads, route samples, mast) at panel height, then the BASE check heights."""
    doc = json.load(open(os.path.join(E.CACHE, "points.json")))
    pts = [dict(p, h_obs=H_PANEL_M if p["kind"] != "mast" else p["h_ant"]) for p in doc["points"]]
    b = next(p for p in pts if p["id"] == "BASE")
    for k, h in CHECK_HEIGHTS.items():
        pts.append(dict(b, id=k, kind="check", h_obs=h))
    return pts


def step_masks(part: int, parts: int, batch: int = 120, log=print) -> None:
    meta, _ = E.load_pack()
    near, _ = E.near_sampler(meta)
    far = far_sampler()
    x0, y0 = meta["origin_xy_m"]
    pts = points()
    b = bearings()
    dist = E.ray_distances(E.NEAR_MAX_M, FAR_MAX_M)
    idx = np.array_split(np.arange(len(pts)), parts)[part]
    out = np.full((len(idx), len(b)), np.nan, dtype=np.float32)
    t0 = time.time()
    for k in range(0, len(idx), batch):
        P = [pts[i] for i in idx[k:k + batch]]
        out[k:k + len(P)] = E.horizon_wedge(np.array([p["x"] + x0 for p in P]), np.array([p["y"] + y0 for p in P]),
                                            np.array([p["z"] for p in P]), np.array([p["h_obs"] for p in P]),
                                            b, near, far, distances=dist)
        log(f"masks part {part}/{parts}: {k + len(P)}/{len(idx)} points ({time.time() - t0:.0f} s)")
    np.savez(_p(f"masks_{part:02d}of{parts:02d}.npz"), idx=idx, mask=out, bearings=b)


def load_masks(n: int) -> np.ndarray:
    files = sorted(f for f in os.listdir(CACHE) if f.startswith("masks_") and f.endswith(".npz"))
    parts = {int(f.split("of")[1][:2]) for f in files}
    if len(parts) != 1:
        raise SystemExit(f"mask files from different --parts runs or none: {files}")
    M = np.full((n, len(bearings())), np.nan, dtype=np.float32)
    for f in files:
        d = np.load(_p(f))
        M[d["idx"]] = d["mask"]
    missing = ~np.isfinite(M).any(axis=1)
    if missing.any():
        raise SystemExit(f"{missing.sum()} points have no mask; run the missing --part chunks")
    return M


def fractions(pts, M, log=print) -> np.ndarray:
    """(points, hours) float32 visible disc fraction."""
    meta, _ = E.load_pack()
    x0, y0 = meta["origin_xy_m"]
    e = np.load(_p("sun_ephem.npz"))
    S, P_base = e["S_base_km"], e["P_base_km"]
    F = np.empty((len(pts), N_HOURS), dtype=np.float32)
    t0 = time.time()
    for i, p in enumerate(pts):
        X, Y = p["x"] + x0, p["y"] + y0
        lat, lon = E.latlon_deg(X, Y)
        P = E.stereo_unit(X, Y) * (E.R_MOON_M + p["z"] + p["h_obs"]) / 1000.0
        brg, el, rad = sun_topo(S, P_base, P, float(lat), float(lon))
        F[i] = disc_fraction(el, horizon_at(M[i], brg), rad)
        if (i + 1) % 500 == 0:
            log(f"  fractions {i + 1}/{len(pts)} ({time.time() - t0:.0f} s)")
    return F


def _lit(f: np.ndarray, c: str) -> np.ndarray:
    return f > 0 if c == "any_part" else f >= CRITERIA[c]


def _entry(f_rows: np.ndarray, rule: str = "worst") -> Dict:
    """Windows and summary of a point (one row) or a leg: rule "worst" = every sample lit (the minimum over the
    samples), "most" = at least MOST_SHARE of the samples lit."""
    out = {"lit": {}, "summary": {}}
    for c in CRITERIA:
        if f_rows.ndim == 1:
            lit = _lit(f_rows, c)
        elif rule == "worst":
            lit = _lit(f_rows.min(axis=0), c)
        else:
            lit = _lit(f_rows, c).mean(axis=0) >= MOST_SHARE - 1e-9
        w = runs(lit)
        out["lit"][c] = encode_windows(w)
        out["summary"][c] = summarize(w, N_HOURS, 1.0)
    f = f_rows if f_rows.ndim == 1 else (f_rows.min(axis=0) if rule == "worst" else f_rows.mean(axis=0))
    out["summary"]["mean_disc_fraction"] = round(float(f.mean()), 5)
    return out


def step_link(out: str = OUT, log=print) -> Dict:
    t0 = time.time()
    pts = points()
    M = load_masks(len(pts))
    F = fractions(pts, M, log)
    pdoc = json.load(open(os.path.join(E.CACHE, "points.json")))
    names = {p["id"]: i for i, p in enumerate(pts)}
    doc_pts = {}
    for i, p in enumerate(pts):
        if p["kind"] in ("site", "pad", "check"):
            doc_pts[p["id"]] = {"xy_m": [p["x"], p["y"]], "z_m": p["z"], "h_m": p["h_obs"], **_entry(F[i])}
    legs = {k: {"worst": _entry(F[np.asarray(ix)], "worst"), "most": _entry(F[np.asarray(ix)], "most"),
                "samples": len(ix)} for k, ix in pdoc["legs"].items()}
    base = doc_pts["BASE"]["summary"]
    checks = {"glaser": {**GLASER, "ours_mean_disc_pct": {k: round(100 * doc_pts[f"BASE_{k}"]["summary"]["mean_disc_fraction"], 2)
                                                          for k in ("2m", "10m")},
                         "ours_any_part_pct": {k: round(100 * doc_pts[f"BASE_{k}"]["summary"]["any_part"]["fraction"], 2)
                                               for k in ("2m", "10m")},
                         "ours_longest_dark_days_half": round(base["half"]["max_gap_h"] / 24.0, 1)},
              "ephem": json.load(open(_p("sun_ephem.json")))["azlcpo_check"]}
    route = [i for i, p in enumerate(pts) if p["kind"] not in ("check", "mast")]
    md = F[route].mean(axis=1)
    ib = route[int(np.argmax(md))]
    checks["glaser"]["best_point_2p5m"] = {"id": pts[ib]["id"], "xy_m": [pts[ib]["x"], pts[ib]["y"]],
                                           "mean_disc_pct": round(100 * float(md.max()), 2),
                                           "note": "the best-lit site or route sample of the pack at 2.5 m; Gläser's "
                                                   "figure is the ridge's best point"}
    meta, _ = E.load_pack()
    doc = {"format": "lunarsim-sun-link", "version": 1, "terrain": "connecting_ridge",
           "description": "Sunlit windows at the sites, pads and rover legs of the Connecting Ridge pack, hourly "
                          "2028-2031 (writer tools/illumination/sun_link.py; reader lunarsim/illumination.py). "
                          "Windows: [s0, l0, g1, l1, ...] hour indices, start0 = s0, end0 = start0 + l0 (exclusive), "
                          "start1 = end0 + g1; hour i covers [i, i + 1) from time.start_utc.",
           "time": {"start_utc": E.START_UTC, "step_min": 60, "n": N_HOURS},
           "criteria": CRITERIA_TEXT, "default_criterion": DEFAULT_CRITERION, "leg_rules": LEG_RULES,
           "observer_height_m": H_PANEL_M, "sun_radius_km": R_SUN_KM,
           "points": doc_pts, "legs": legs, "checks": checks,
           "provenance": {"tool": "tools/illumination/sun_link.py", "git_sha": E._git_sha(),
                          "dem_near": "5 m tile of the terrain pack (LOLA 5 m, PGDA 78)", "dem_far": json.load(open(_p("dem.json"))),
                          "horizon": {"bearing_step_deg": BEARING_STEP_DEG, "near_max_m": E.NEAR_MAX_M, "far_max_m": FAR_MAX_M},
                          "ephemeris": "SPICE spkcpo SUN from BASE, LT+S, MOON_ME (kernels as tools/comms)",
                          "flags": "Sun position Spec (SPICE); terrain Measured (LOLA); observer height 2.5 m Assumed; "
                                   "night = below half the disc Assumed"},
           "generated": {"seconds": round(time.time() - t0, 1)}}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    b = (json.dumps(doc, separators=(",", ":")) + "\n").encode("utf-8")
    open(out, "wb").write(b)
    np.savez_compressed(_p("fractions_sites.npz"), **{p["id"]: F[i] for i, p in enumerate(pts)
                                                     if p["kind"] in ("site", "pad", "check")})
    log(f"link: wrote {os.path.relpath(out, ROOT)} ({len(b) / 2**20:.2f} MB): {len(doc_pts)} points, {len(legs)} legs; "
        f"BASE lit (half) {base['half']['fraction']:.3f}, mean disc {base['mean_disc_fraction']:.3f}, longest dark "
        f"{base['half']['max_gap_h'] / 24:.1f} d; Glaser et al. 2 m {GLASER['2m']} % vs ours "
        f"{checks['glaser']['ours_mean_disc_pct']['2m']} % (mean disc) ({time.time() - t0:.0f} s)")
    return doc


def step_avgvisib(log=print) -> Dict:
    """The PGDA/PDS average solar illumination map (Mazarico et al. 2011 method; mean visible fraction of the solar
    disc at the surface, 60 m pixels) at our sites, against our surface-level BASE and our 2.5 m points."""
    lbl_url = AVGVISIB_URL.replace(".IMG", ".LBL")
    lbl = urllib.request.urlopen(lbl_url, timeout=60).read().decode("latin-1")

    def key(k):
        for line in lbl.splitlines():
            if line.strip().startswith(k):
                return line.split("=", 1)[1].strip().split()[0].strip('"')
        raise KeyError(k)

    lines, samples = int(key("LINES")), int(key("LINE_SAMPLES"))
    scale = float(key("SCALING_FACTOR"))
    px_m = float(key("MAP_SCALE")) * (1000.0 if "KM" in lbl.split("MAP_SCALE", 1)[1].split("\n")[0].upper() else 1.0)
    off = float(key("LINE_PROJECTION_OFFSET"))
    meta, sites = E.load_pack()
    x0, y0 = meta["origin_xy_m"]
    W, H = meta["size_m"]
    j0 = int(math.floor(off - (y0 + H) / px_m)) - 2
    j1 = int(math.ceil(off - y0 / px_m)) + 2
    rec = samples * 2
    raw = _p(f"avgvisib_sun_rows_{j0}_{j1}.bin")
    if not os.path.isfile(raw):
        req = urllib.request.Request(AVGVISIB_URL, headers={"Range": f"bytes={j0 * rec}-{(j1 + 1) * rec - 1}"})
        with urllib.request.urlopen(req, timeout=300) as r:
            open(raw, "wb").write(r.read())
    vis = np.fromfile(raw, dtype="<i2").reshape(-1, samples).astype(np.float64) * scale
    # our pipeline the map's way: surface level, the 5 m tile averaged to the map's 60 m pixels, at the centre of the
    # map pixel holding each point (as tools/comms/earth_link.py step_avgvisib did for the Earth map)
    near5, _ = E.near_sampler(meta)
    z5, px5 = near5.z, near5.px
    k = int(round(px_m / px5))
    oc = int(round(((math.ceil(x0 / px_m) * px_m) - x0) / px5))
    orow = int(round(((y0 + H) - math.floor((y0 + H) / px_m) * px_m) / px5))
    sub = z5[orow:, oc:]
    r_, c_ = (sub.shape[0] // k) * k, (sub.shape[1] // k) * k
    near60 = E.GridSampler(sub[:r_, :c_].reshape(r_ // k, k, c_ // k, k).mean(axis=(1, 3)),
                           x0 + oc * px5, y0 + H - orow * px5, px_m)
    far = far_sampler()
    e = np.load(_p("sun_ephem.npz"))
    S, P_base = e["S_base_km"], e["P_base_km"]
    dist = E.ray_distances(E.NEAR_MAX_M, FAR_MAX_M)
    doc = json.load(open(OUT))
    rows = []
    for key_, p in doc["points"].items():
        X, Y = p["xy_m"][0] + x0, p["xy_m"][1] + y0
        i, j = int(round(X / px_m + off)), int(round(off - Y / px_m))
        nb = vis[j - j0 - 1:j - j0 + 2, i - 1:i + 2]
        cx, cy = (i - off) * px_m, (off - j) * px_m
        zc = float(near60(np.array([cx]), np.array([cy]))[0])
        m = E.horizon_wedge([cx], [cy], [zc], [0.0], bearings(), near60, far, distances=dist)[0]
        lat, lon = E.latlon_deg(cx, cy)
        brg, el, rad = sun_topo(S, P_base, E.stereo_unit(cx, cy) * (E.R_MOON_M + zc) / 1000.0, float(lat), float(lon))
        mapway = float(disc_fraction(el, horizon_at(m, brg), rad).mean())
        rows.append({"point": key_, "h_m": p["h_m"], "map": round(float(vis[j - j0, i]), 3),
                     "map_3x3": [round(float(nb.min()), 3), round(float(nb.max()), 3)],
                     "ours_map_way": round(mapway, 3), "ours_mean_disc": p["summary"]["mean_disc_fraction"]})
        log(f"{key_:10s} map {rows[-1]['map']:.3f} (3x3 {nb.min():.3f}-{nb.max():.3f})  ours, map's way {mapway:.3f}  "
            f"ours at {p['h_m']:.1f} m on the 5 m tile {rows[-1]['ours_mean_disc']:.3f}")
    uniq = {(r["map"], r["ours_map_way"]) for r in rows if r["point"] not in CHECK_HEIGHTS}
    dm = np.array([b - a for a, b in uniq])
    res = {"map": AVGVISIB_URL, "label": {"lines": lines, "samples": samples, "scale": scale, "px_m": px_m, "offset_px": off},
           "rows": rows, "map_way_minus_map": {"mean": round(float(dm.mean()), 4), "mean_abs": round(float(np.abs(dm).mean()), 4),
                                               "max_abs": round(float(np.abs(dm).max()), 4),
                                               "within_0p05": int((np.abs(dm) <= 0.05).sum()), "n": int(len(dm))},
           "note": "the map: mean visible solar-disc fraction at the surface (LDEM 60 m) over its own period (label); "
                   "ours: 2028-2031 hourly; the map's way = surface level on the 5 m tile averaged to 60 m"}
    json.dump(res, open(_p("avgvisib_check.json"), "w"), indent=1)
    doc["checks"]["avgvisib"] = {k2: res[k2] for k2 in ("map", "map_way_minus_map", "note")}
    doc["checks"]["avgvisib"]["rows"] = [r for r in rows if r["point"] in ("BASE", "DEPOT", "POWER", "CONSTR", "ISRU",
                                                                            "SCI_1", "PSR", "PAD_A@1", "PAD_B@1")]
    open(OUT, "wb").write((json.dumps(doc, separators=(",", ":")) + "\n").encode("utf-8"))
    log(f"map way minus map: mean {dm.mean():+.3f}, mean |d| {np.abs(dm).mean():.3f}, max |d| {np.abs(dm).max():.3f}; "
        f"{res['map_way_minus_map']['within_0p05']}/{len(dm)} within 0.05")
    return res


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["ephem", "dem", "masks", "link", "avgvisib"])
    ap.add_argument("--part", type=int, default=0)
    ap.add_argument("--parts", type=int, default=1)
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    if a.step == "ephem":
        step_ephem()
    elif a.step == "dem":
        step_dem()
    elif a.step == "masks":
        step_masks(a.part, a.parts)
    elif a.step == "link":
        step_link()
    else:
        step_avgvisib()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
