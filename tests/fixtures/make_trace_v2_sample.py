"""Regenerate tests/fixtures/trace_v2_sample.json (lunarsim-trace v2 sample for FRONTEND's world viewer, F-6).

    .venv\\Scripts\\python tests\\fixtures\\make_trace_v2_sample.py

A short real run (P2-4-vehicles, first 2,500 h, seed 0 = 5 landings of all three classes, marketplace) with all four Phase-3 features on:
terrain connecting_ridge, pads at the 1 km standoff, the classical ZEM/ZEV landing-outcome tables (200 Monte Carlo
episodes per class), plume keep-out 1 km / 2 h, and a driving table for the 1 km pad set (expert, 2 lighting cases,
RTT 0/4/6/8, 10 seeds). Needs the [terrain] and [ml] extras; takes a few minutes. The intermediate tables go to a
temporary folder; only the trace is kept.
"""
import json, os, sys, tempfile, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from lunarsim import dispatch, Simulation
from lunarsim.config import library
from lunarsim.formats import validate_trace
from lunarsim.lander.evaluate import evaluate
from lunarsim.rover import tables as TB, physics as R
from lunarsim.terrain import Terrain


def main():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="lunarsim_v2fixture_")
    for cls in ("CLPS", "MK1", "LARGE"):
        evaluate(None, cls, 200, out_dir=tmp)
    terrain = Terrain("connecting_ridge")
    sites = json.load(open(os.path.join(terrain.path, "sites.json"), encoding="utf-8"))
    sites = {"sites": sites["sites"], "pads": {"1": sites["pads"]["1"]}}
    doc = TB.build(terrain, sites, seeds=10, lighting=(90.0, R.NIGHT))
    drive = os.path.join(tmp, "driving-fixture.json")
    json.dump(doc, open(drive, "w", encoding="utf-8"))
    sc = library()["P2-4-vehicles"].with_(
        horizon_h=2500.0, terrain="connecting_ridge", pad_standoff_km="1",
        landing_model={"policy": "classical", "dir": tmp, "sigma_scale": 1.0, "pad_radius_m": 50.0, "failure_policy": "lose"},
        plume={"keepout_km": 1.0, "standdown_h": 2.0, "shelter": "auto"}, autonomy_model=drive)
    sim = Simulation(sc, dispatch.marketplace, seed=0, mech_kwargs={"trace": True})
    sim.run()
    tr = sim.trace_export(mechanism="marketplace")
    tr["fixture_note"] = ("Small sample for viewer development: 2,500 h of P2-4-vehicles with every Phase-3 feature on; "
                          "the driving table here covers only the 1 km pad set and two lighting cases.")
    errs = validate_trace(tr)
    assert not errs, errs
    out = os.path.join(ROOT, "tests", "fixtures", "trace_v2_sample.json")
    json.dump(tr, open(out, "w", encoding="utf-8"), separators=(",", ":"))
    print(f"wrote {out}: {os.path.getsize(out) / 1e3:.0f} kB, {len(tr['jobs'])} jobs, {len(tr['landings'])} landings, "
          f"{len(tr['plume_windows'])} windows in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
