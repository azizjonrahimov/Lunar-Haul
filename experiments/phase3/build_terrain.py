"""Build the Phase-3 terrain packs (lunarsim-terrain v1) from PGDA LOLA 5 m/px site tiles.

    python experiments/phase3/build_terrain.py              # default pack(s) below
    python experiments/phase3/build_terrain.py --site Site04

Each pack is written to data/terrain/<pack>/; the source GeoTIFF is cached in data/terrain/_cache/
(git-ignored). Same code path as `lunarsim terrain build`; this file only records which tiles the
project uses. Needs the [terrain] extra (rasterio, pillow).

Source: Barker et al. 2021, PGDA LOLA 5 m/px polar DEMs, https://pgda.gsfc.nasa.gov/products/78 (NASA/GSFC).
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from lunarsim import terrain as T  # noqa: E402

# PGDA site -> pack folder. Connecting ridge is the default site (PLAN §8.4); Shackleton rim the alternative.
PACKS = {"Site01": "connecting_ridge", "Site04": "shackleton_rim"}
DEFAULT = ["Site01"]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--site", action="append", choices=sorted(PACKS), help="PGDA site(s); default Site01")
    p.add_argument("--root", default=os.path.join("data", "terrain"))
    p.add_argument("--sun-az", type=float, default=0.0)
    a = p.parse_args(argv)
    for site in a.site or DEFAULT:
        out = os.path.join(a.root, PACKS[site])
        t0 = time.time()
        src = T.download(site, os.path.join(a.root, "_cache"))
        meta = T.build_pack(src, out, site, sun_az_deg=a.sun_az)
        st = meta["stats"]
        print(f"{site} -> {out}: {meta['size_m'][0] / 1000:g} x {meta['size_m'][1] / 1000:g} km, "
              f"z {st['z_min']:.1f}..{st['z_max']:.1f} m, {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main()
