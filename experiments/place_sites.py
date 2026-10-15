"""Place the nine LunarSim sites on a terrain pack and write data/terrain/<site>/sites.json.

LEAD tool (Phase 3). The layout keeps the v2 world's relative geometry (world.py: pads > 1 km from the base,
farthest work site ~5 km) but every site is moved to the flattest nearby cell that satisfies its kind:
  BASE/DEPOT/POWER/CONSTR/ISRU  pad-scale slope (mean plane over a 100 m disk) <= 5 deg
  SCI_1                          <= 8 deg (a rim site)
  PSR                            in cast shadow at all four reference sun azimuths (permanent-shadow proxy)
Pads come from lunarsim.terrain.place_pads at each standoff D (km): PAD_A = best illumination, PAD_B = the next
candidate at least 400 m away. All numbers are derived from the LOLA 5 m DEM (Measured terrain, Assumed layout).

    .venv\\Scripts\\python experiments\\place_sites.py --site connecting_ridge --base 7450,7510
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lunarsim.terrain import Terrain, place_pads, plane_slope_deg, resolve_pack  # noqa: E402

# nominal offsets from BASE in km, from lunarsim/world.py (BASE at (1.4, 1.0))
NOMINAL = {
    "DEPOT": (-0.3, -0.3, "depot", 5.0),
    "POWER": (0.5, 0.6, "power", 5.0),
    "CONSTR": (-0.4, 0.5, "construction", 5.0),
    "ISRU": (1.2, -0.1, "isru", 5.0),
    "SCI_1": (1.8, 1.3, "science", 8.0),
    "PSR": (3.2, 2.0, "psr", 12.0),
}
STANDOFFS = (0.5, 1.0, 2.0, 3.0, 5.0)
SEARCH_M = {"PSR": 2500.0}
DEFAULT_SEARCH_M = 400.0
MIN_SEP_M = 300.0


def rotate(dx, dy, phi_deg):
    c, s = math.cos(math.radians(phi_deg)), math.sin(math.radians(phi_deg))
    return dx * c - dy * s, dx * s + dy * c


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--site", default="connecting_ridge")
    p.add_argument("--base", default="7450,7510")
    p.add_argument("--out", default=None)
    a = p.parse_args(argv)
    t = Terrain(a.site)
    base = tuple(float(v) for v in a.base.split(","))
    px = t.px20
    rows, cols = t.z20.shape
    splane = plane_slope_deg(t.z20, px, max(1, int(round(100.0 / px))))      # row 0 = south
    illum = t.illumination_proxy()
    shadow_all = np.ones_like(t.z20, dtype=bool)
    for az in (0, 90, 180, 270):
        shadow_all &= t.shadow_grid(az)
    yy, xx = np.mgrid[0:rows, 0:cols]
    cx, cy = (xx + 0.5) * px, (yy + 0.5) * px
    margin = 150.0

    # orientation: rotate the nominal layout to the flattest fit (PSR excluded)
    best = None
    for phi in range(0, 360, 15):
        score, ok = 0.0, True
        for sid, (dx, dy, kind, _) in NOMINAL.items():
            if sid == "PSR":
                continue
            rx, ry = rotate(dx * 1000, dy * 1000, phi)
            x, y = base[0] + rx, base[1] + ry
            if not (margin < x < t.size_m[0] - margin and margin < y < t.size_m[1] - margin):
                ok = False
                break
            j, i = t.cell(x, y)
            score += float(splane[j, i])
        if ok and (best is None or score < best[0]):
            best = (score, phi)
    phi = best[1]

    sites = [{"id": "BASE", "xy_m": [round(base[0], 1), round(base[1], 1)], "kind": "base"}]
    for sid, (dx, dy, kind, smax) in NOMINAL.items():
        rx, ry = rotate(dx * 1000, dy * 1000, phi)
        nx, ny = base[0] + rx, base[1] + ry
        R = SEARCH_M.get(sid, DEFAULT_SEARCH_M)
        d = np.hypot(cx - nx, cy - ny)
        cand = (d <= R) & (cx > margin) & (cx < t.size_m[0] - margin) & (cy > margin) & (cy < t.size_m[1] - margin)
        for s in sites:  # sites stay at least MIN_SEP_M apart so no leg degenerates
            cand &= np.hypot(cx - s["xy_m"][0], cy - s["xy_m"][1]) >= MIN_SEP_M
        if sid == "PSR":
            cand &= shadow_all
        cand &= splane <= smax
        idx = np.flatnonzero(cand)
        if len(idx) == 0:  # relax: nearest cell of the kind regardless of slope
            cand = (d <= 2 * R) & (shadow_all if sid == "PSR" else True)
            idx = np.flatnonzero(cand)
        # score: slope first (quantised to 1 deg), then distance to the nominal spot
        sc = np.round(splane.ravel()[idx]) * 1000.0 + d.ravel()[idx]
        k = idx[int(np.argmin(sc))]
        x, y = float(cx.ravel()[k]), float(cy.ravel()[k])
        sites.append({"id": sid, "xy_m": [round(x, 1), round(y, 1)], "kind": kind})
    for s in sites:
        x, y = s["xy_m"]
        j, i = t.cell(x, y)
        s["z_m"] = round(float(t.height(x, y)), 1)
        s["slope_plane_deg"] = round(float(splane[j, i]), 2)
        s["illum_proxy"] = round(float(illum[j, i]), 4)
        s["shadow_all_az"] = bool(shadow_all[j, i])
        if s["id"] != "BASE":
            s["dist_base_km"] = round(math.hypot(x - base[0], y - base[1]) / 1000.0, 3)
            s["los_to_base"] = "clear" if t.line_of_sight((x, y), base) else "blocked"
        if s["kind"] == "psr":
            s["night_dark"] = True

    pads, pad_details = {}, {}
    for D in STANDOFFS:
        c = place_pads(t, base, D, illum=illum, n=8, min_sep_m=400.0)
        if len(c) < 2:
            c = place_pads(t, base, D, illum=illum, n=8, min_sep_m=400.0, max_slope_deg=8.0)
        key = f"{D:g}"
        pa, pb = c[0], c[1]
        pads[key] = {"PAD_A": pa["xy_m"], "PAD_B": pb["xy_m"]}
        pad_details[key] = {"PAD_A": pa, "PAD_B": pb}

    out = {
        "format": "lunarsim-sites", "version": 1, "terrain": t.site_id,
        "base_xy_m": [round(base[0], 1), round(base[1], 1)], "layout_rotation_deg": phi,
        "rules": {"pad_scale_slope": "mean plane over 100 m disk", "psr": "cast shadow at sun az 0/90/180/270, el 1.5 deg",
                  "pads": "place_pads: best illumination, PAD_B >= 400 m from PAD_A", "flag": "Assumed layout on Measured terrain"},
        "sites": sites, "pads": pads, "pad_details": pad_details,
    }
    path = a.out or os.path.join(resolve_pack(a.site), "sites.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"rotation {phi} deg; wrote {path}")
    for s in sites:
        print(f"  {s['id']:7s} {s['xy_m']}  z {s['z_m']:7.1f}  slope {s['slope_plane_deg']:4.1f}  "
              f"shadow_all {s['shadow_all_az']}  {s.get('dist_base_km', 0):.2f} km  {s.get('los_to_base', '')}")
    for key, d in pad_details.items():
        for pid in ("PAD_A", "PAD_B"):
            q = d[pid]
            print(f"  D={key:>3} {pid} {q['xy_m']} slope {q['slope_plane_deg']} illum {q['illum']} los {q['los_to_base']}")


if __name__ == "__main__":
    main()
