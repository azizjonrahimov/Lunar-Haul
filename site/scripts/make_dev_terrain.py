"""Stand-in terrain pack for site development until LEAD commits data/terrain/connecting_ridge (B-9).

Reads the cached PGDA LOLA 5 m DEM, averages it down to 1000 x 1000 (16 m posts for the 16 km tile) and writes
a uint16 PNG plus a meta.json in the lunarsim-terrain v1 shape (PLAN 5.1) into site/.terrain-dev/ (git-ignored).
The site reads only height_20m.png and meta.json, so this is a drop-in for the real pack.

Usage (repo root): .venv\\Scripts\\python site\\scripts\\make_dev_terrain.py
"""
import json, os, sys, time
import numpy as np
import rasterio
from rasterio.enums import Resampling
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SRC = os.path.join(ROOT, "data", "terrain", "_cache", "Site01_final_adj_5mpp_surf.tif")
OUT = os.path.join(ROOT, "site", ".terrain-dev")
N = 1000
SCALE = 0.05  # m per unit: 65535 units cover 3.3 km of relief


def main():
    if not os.path.exists(SRC):
        sys.exit(f"no DEM at {SRC}")
    with rasterio.open(SRC) as d:
        z = d.read(1, out_shape=(N, N), resampling=Resampling.average).astype(np.float64)
        b = d.bounds
    if np.isnan(z).any():  # fill the odd hole with the mean so the mesh has no spikes
        z[np.isnan(z)] = np.nanmean(z)
    offset = float(np.floor(z.min()))
    u = np.clip(np.round((z - offset) / SCALE), 0, 65535).astype(np.uint16)
    os.makedirs(OUT, exist_ok=True)
    Image.fromarray(u).save(os.path.join(OUT, "height_20m.png"))
    post = (b.right - b.left) / N
    gy, gx = np.gradient(z, post)
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    meta = {
        "format": "lunarsim-terrain", "version": 1, "site_id": "dev_site01", "name": "Site01 (development stand-in)",
        "dev_standin": True,
        "source": {"product": "PGDA LOLA 5mpp Site01", "url": "https://pgda.gsfc.nasa.gov/products/90",
                   "citation": "Barker et al. (2021), Planetary and Space Science 203, 105119",
                   "credit": "NASA Goddard PGDA / LOLA"},
        "crs": "Moon south polar stereographic (LOLA)",
        "origin_xy_m": [b.left, b.bottom], "size_m": [b.right - b.left, b.top - b.bottom],
        "layers": {"height_20m": {"file": "height_20m.png", "shape": [N, N], "post_m": post,
                                  "row0": "north", "dtype": "uint16"}},
        "z_encoding": {"offset_m": offset, "scale_m_per_unit": SCALE},
        "stats": {"z_min": float(z.min()), "z_max": float(z.max()),
                  "slope_p50": float(np.percentile(slope, 50)), "slope_p90": float(np.percentile(slope, 90))},
        "generated": {"tool": "site/scripts/make_dev_terrain.py", "commit": None, "time": time.strftime("%Y-%m-%dT%H:%M:%S")},
    }
    json.dump(meta, open(os.path.join(OUT, "meta.json"), "w"), indent=2)
    print("wrote", OUT, f"z {meta['stats']['z_min']:.0f}..{meta['stats']['z_max']:.0f} m, post {post:.1f} m")


if __name__ == "__main__":
    main()
