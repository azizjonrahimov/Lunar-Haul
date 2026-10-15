"""Reference numbers for the site's /verification page, computed by the Python reference code (lunarsim).

The page recomputes each quantity with the browser port and compares. Output: site/verify/refs.json (committed;
re-run after the terrain pack, the rover model or the driving table changes).

Usage (repo root): .venv\\Scripts\\python site\\scripts\\make_verify_refs.py
"""
import json, os, sys, tempfile, time, pathlib, subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from lunarsim import terrain as T                      # noqa: E402
from lunarsim.rover import physics as R, expert as X, tables as TB   # noqa: E402
from lunarsim.rover.env import DriveEnv, drive_expert  # noqa: E402

SITE_ID = "connecting_ridge"
OUT = os.path.join(ROOT, "site", "verify", "refs.json")


def fnv1a(b: bytes) -> int:
    h = 0x811C9DC5
    for x in b:
        h = ((h ^ x) * 0x01000193) & 0xFFFFFFFF
    return h


def main():
    t = T.Terrain(SITE_ID)
    refs = {"generated": {"tool": "site/scripts/make_verify_refs.py", "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
                          "commit": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()},
            "terrain": {"site_id": SITE_ID, "z5_min": float(t.z5.min()), "z5_max": float(t.z5.max()),
                        "meta_z_min": t.meta["stats"]["z_min"], "meta_z_max": t.meta["stats"]["z_max"],
                        "scale_m_per_unit": t.meta["z_encoding"]["scale_m_per_unit"]},
            "shadow": {}, "rover": {}}
    for az in (0.0, 90.0, 180.0, 270.0):           # row 0 = south, one byte per cell, as the JS port stores it
        g = t.shadow_grid(az).astype(np.uint8)
        refs["shadow"][f"{az:g}"] = {"shadowed_cells": int(g.sum()), "cells": int(g.size), "fnv1a": fnv1a(g.tobytes())}

    # flat-leg teleop speeds made good (the step env + expert, on the flat pack tests/test_rover.py builds)
    import rasterio
    from rasterio.transform import from_origin
    N, PX = 600, 5.0
    proj = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
    tmp = pathlib.Path(tempfile.mkdtemp())
    with rasterio.open(str(tmp / "flat.tif"), "w", driver="GTiff", width=N, height=N, count=1, dtype="float32", crs=proj,
                       transform=from_origin(0.0, N * PX, PX, PX)) as ds:
        ds.write(np.full((N, N), 100.0, np.float32), 1)
    T.build_pack(str(tmp / "flat.tif"), str(tmp / "flat"), "SiteTest", z_scale=0.01)
    flat = T.Terrain(str(tmp / "flat"))
    route = [[200.0, 1500.0], [2800.0, 1500.0]]
    refs["rover"]["flat_leg"] = {"route": route, "meta": flat.meta, "smg_kmh": {}}
    for rtt in (0.0, 4.0, 6.0, 8.0):
        leg = drive_expert(DriveEnv(flat, autonomy="teleop", rtt_s=rtt, sun_az_deg=None),
                           {"waypoints": route, "autonomy": "teleop", "rtt_s": rtt, "sun_az_deg": None})
        refs["rover"]["flat_leg"]["smg_kmh"][f"{rtt:g}"] = leg["distance_m"] / leg["time_s"] * 3.6

    # BASE -> PSR, sun 90 deg: route, integrator and the autonomous step drive
    sites = {s["id"]: s["xy_m"] for s in t.sites()["sites"]}
    rt = X.plan(t, sites["BASE"], sites["PSR"], 90.0)
    prof = TB.leg_profile(t, rt, 90.0)
    r = TB.drive_profile(prof, "autonomous", 0.0, 90.0, np.random.default_rng(0), 4)
    leg = drive_expert(DriveEnv(t, autonomy="autonomous", rtt_s=0.0, sun_az_deg=90.0),
                       {"waypoints": rt.tolist(), "autonomy": "autonomous", "rtt_s": 0.0, "sun_az_deg": 90.0})
    refs["rover"]["base_psr_sun90"] = {"route_points": len(rt), "length_m": prof["length_m"], "integrator_energy_wh": float(r["energy_wh"][0]),
                                       "integrator_t_move_s": r["t_move_s"], "drive_autonomous": leg}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(refs, open(OUT, "w"), indent=1, default=float)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
