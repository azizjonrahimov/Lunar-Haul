"""Regenerate tests/fixtures/rover_driver_parity.json: parity vectors for the JS port of the learned rover driver (F-17).

    .venv\\Scripts\\python tests\\fixtures\\make_rover_driver_parity.py [--card data/policies/rover_bc_s0.json]

One leg, fully deterministic: BASE->DEPOT on connecting_ridge, the expert's A* route for sun azimuth 90 deg, autonomous
level (no teleop lag, no RTT dependence), soil friction angle fixed at 42 deg (options["phi"], so the seed draws nothing),
seed 0, driven closed-loop by the ONNX driver in lunar/Drive-v0 (lunarsim.rover.env.DriveEnv).
  steps[0..39]  the observation (patch 3x32x32 and the 5 scalars, rounded to 1e-6) and the driver's action on that
                stored observation (onnxruntime CPU). A port that feeds the stored observation must reproduce the
                action to 1e-5.
  final         the closed-loop telemetry at the end of the leg: steps, elapsed s, path m, energy Wh, mean slip,
                interventions, stops, reached. The JS drive will drift from these (float32 vs float64, terrain
                interpolation order); FRONTEND reports the deviation and LEAD decides, as for the night-teleop drift
                in F-10. No tolerance is set here.
Needs the [terrain] and [ml] extras (onnxruntime, gymnasium).
"""
import argparse, json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np

N_STEPS = 40
LEG = ("BASE", "DEPOT")
SUN, PHI, SEED, AUTONOMY, RTT = 90.0, 42.0, 0, "autonomous", 4.0


def _r(x):
    return np.round(np.asarray(x, np.float64), 6)


def build(card: str):
    from lunarsim.terrain import Terrain
    from lunarsim.rover import physics as R
    from lunarsim.rover.env import DriveEnv, ENV_ID, PATCH, SCALAR_NAMES, DT_S
    from lunarsim.rover.expert import plan
    from lunarsim.rover.onnx_driver import OnnxDriver

    terrain = Terrain("connecting_ridge", os.path.join(ROOT, "data", "terrain"))
    with open(os.path.join(terrain.path, "sites.json"), encoding="utf-8") as f:
        pts = {s["id"]: tuple(s["xy_m"]) for s in json.load(f)["sites"]}
    route = plan(terrain, pts[LEG[0]], pts[LEG[1]], SUN)
    if route is None:
        raise SystemExit(f"no route {LEG[0]}->{LEG[1]} under the slope limit")
    drv = OnnxDriver(card)
    env = DriveEnv(terrain)

    slips = []                                   # record every slip value the env computes (mean slip in `final`)
    slip0 = R.slip
    R.slip = lambda grade, phi: slips.append(float(slip0(grade, phi))) or slip0(grade, phi)
    try:
        obs, _ = env.reset(seed=SEED, options={"waypoints": route, "autonomy": AUTONOMY, "rtt_s": RTT,
                                               "sun_az_deg": SUN, "phi": PHI})
        steps, info, k, max_dev = [], {}, 0, 0.0
        while True:
            a = drv.act(obs)
            if k < N_STEPS:
                p, s = _r(obs["patch"]), _r(obs["scalars"])
                a_stored = drv.act({"patch": p, "scalars": s})
                max_dev = max(max_dev, float(np.max(np.abs(a_stored - a))))
                steps.append({"k": k, "patch": p.tolist(), "scalars": s.tolist(), "action": _r(a_stored).tolist()})
            obs, _, term, trunc, info = env.step(a)
            k += 1
            if term or trunc:
                break
    finally:
        R.slip = slip0
    leg = info["leg"]
    return {
        "format": "lunarsim-rover-driver-parity", "version": 1, "env": ENV_ID, "policy": drv.id,
        "onnx_sha256": drv.card.get("onnx_sha256"),
        "leg": {"from": LEG[0], "to": LEG[1], "terrain": "connecting_ridge", "sun_az_deg": SUN, "phi_deg": PHI,
                "autonomy": AUTONOMY, "rtt_s": RTT, "seed": SEED, "dt_s": DT_S,
                "waypoints": _r(route).tolist()},
        "patch_shape": [3, PATCH, PATCH], "scalar_names": list(SCALAR_NAMES),
        "tolerance": {"action_given_stored_obs": 1e-5, "final": None},
        "steps": steps,
        "final": {"steps": int(env.steps), "elapsed_s": round(float(leg["time_s"]), 3),
                  "path_m": round(float(leg["distance_m"]), 3), "energy_wh": round(float(leg["energy_wh"]), 4),
                  "slip_mean": round(float(np.mean(slips)) if slips else 0.0, 6),
                  "interventions": int(leg["interventions"]), "stops": int(leg["stops"]),
                  "reached": bool(leg["reached"])},
        "note": ("steps[k].action = onnxruntime (CPU) on the stored (rounded) observation; it differs from the "
                 f"closed-loop action on the unrounded observation by at most {max_dev:.1e}. `final` is the closed-loop "
                 "Python drive; a port's closed-loop drift is reported, not asserted."),
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--card", default=os.path.join(ROOT, "data", "policies", "rover_bc_s0.json"))
    p.add_argument("--out", default=os.path.join(ROOT, "tests", "fixtures", "rover_driver_parity.json"))
    a = p.parse_args(argv)
    t0 = time.time()
    doc = build(a.card)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    print(f"wrote {a.out}: {os.path.getsize(a.out) / 1e6:.2f} MB, {len(doc['steps'])} steps stored, "
          f"final {doc['final']} in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
