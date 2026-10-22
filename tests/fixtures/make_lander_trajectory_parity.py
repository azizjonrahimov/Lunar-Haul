"""Regenerate tests/fixtures/lander_trajectory_parity.json: two exported descent episodes at full float64 precision
for the JS replay test (B-46; site/tests/lander-trajectories.test.mjs asserts < 1e-6 m against it).

    .venv\\Scripts\\python tests\\fixtures\\make_lander_trajectory_parity.py

The episodes are the CLPS classical law and the CLPS network (lander_CLPS_bc_v3_s0) at their p50 picks in
data/policies/trajectories-v1.json, replayed exactly as lunarsim/lander/trajectories.py records them
(DescentEnv(cls, variant, sensor=True, obs_version).reset(seed), randomised). Per episode: the domain-randomisation
draws the physics needs (thrust_scale, isp_scale, m_dry), dt, the initial state; per step the raw action [a0, a1, a2]
the pilot returned (before the physics' own clipping), the navigation estimate it saw (pos, vel: env.last_est, the
sensor readings behind the observation) and the env state after the step. The last step of a landing is the
touchdown state (physics.touchdown(prev, physics.step(prev, a)) - flag "touchdown"). State layout: physics.STATE
(x, y, z, vx, vy, vz, m, tx, ty, wx, wy). Floats are Python repr (shortest round-trip), so JSON.parse gives the
same float64.
"""
import dataclasses, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

from lunarsim.lander import physics as P
from lunarsim.lander import trajectories as TJ
from lunarsim.lander.classes import CLASSES, G_MOON, TOUCHDOWN
from lunarsim.lander.env import DescentEnv, ENV_VERSION

OUT = os.path.join(ROOT, "tests", "fixtures", "lander_trajectory_parity.json")
EPISODES = [("CLPS", "classical", "p50"), ("CLPS", "lander_CLPS_bc_v3_s0", "p50")]


def episode(doc, cls, pilot, pick):
    entry = next(p for p in doc["pilots"] if p["cls"] == cls and p["pilot"] == pilot)
    ep = next(e for e in entry["episodes"] if e["pick"] == pick)
    kind = "law" if pilot in ("classical", "memoryless") else "policy"
    controller, obs_v, variant, prov = TJ.controller_for(kind, pilot, None if kind == "law" else pilot + ".json")
    env = DescentEnv(cls=cls, variant=variant, sensor=True, obs_version=obs_v)
    obs, _ = env.reset(seed=ep["seed"])
    out = {"cls": cls, "pilot": pilot, "pick": pick, "seed": ep["seed"], "obs_version": obs_v, "reward_variant": variant,
           "provenance": prov, "dt": env.dt, "thrust_scale": float(env.thrust_scale), "isp_scale": float(env.isp_scale),
           "m_dry": float(env.m_dry), "state0": [float(x) for x in env.state], "steps": []}
    done, info = False, {}
    while not done:
        est_pos, est_vel = env.last_est
        a = controller(obs, env)
        obs, r, term, trunc, info = env.step(a)
        done = term or trunc
        rec = {"action": [float(x) for x in a], "est_pos": [float(x) for x in est_pos],
               "est_vel": [float(x) for x in est_vel], "state": [float(x) for x in env.state]}
        if term and "outcome" in info and info["outcome"].get("landed_tilt_deg") is not None:
            rec["touchdown"] = True
        out["steps"].append(rec)
    out["n_steps"] = len(out["steps"])
    out["outcome"] = {k: v for k, v in info.get("outcome", {}).items() if isinstance(v, (int, float, str, bool, list, type(None)))}
    if out["n_steps"] != ep["n_steps"]:
        raise SystemExit(f"{cls} {pilot} {pick}: {out['n_steps']} steps, the export has {ep['n_steps']}")
    return out


def main():
    with open(os.path.join(ROOT, "data", "policies", "trajectories-v1.json"), encoding="utf-8") as f:
        doc = json.load(f)
    fx = {"format": "lunarsim-lander-trajectory-parity", "version": 1, "env_version": ENV_VERSION,
          "description": __doc__.split("\n\n", 2)[2].strip(),
          "state_layout": ["x", "y", "z", "vx", "vy", "vz", "m", "tx", "ty", "wx", "wy"],
          "constants": {"g_moon": G_MOON, "touchdown": TOUCHDOWN,
                        "classes": {c: dataclasses.asdict(CLASSES[c]) for c in sorted({e[0] for e in EPISODES})}},
          "episodes": [episode(doc, *e) for e in EPISODES]}
    if len(fx["state_layout"]) != P.STATE_SIZE:
        raise SystemExit("state layout out of date")
    b = (json.dumps(fx, indent=None, separators=(",", ":")) + "\n").encode("utf-8")
    open(OUT, "wb").write(b)
    print(f"wrote {OUT}: {[e['n_steps'] for e in fx['episodes']]} steps, {len(b) / 1024:.0f} kB")


if __name__ == "__main__":
    main()
