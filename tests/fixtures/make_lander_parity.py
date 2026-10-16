"""Regenerate tests/fixtures/lander_parity.json: deterministic vectors for the JS port of the lander (F-7).

    .venv\\Scripts\\python tests\\fixtures\\make_lander_parity.py

numpy's PCG64 and Gymnasium seeding cannot be reproduced in JS, so everything here is deterministic:
  physics          per class: an initial state, dt, the domain-randomisation factors, 200 actions (clipping at +-1,
                   tilt saturation, propellant run-out) and the state + thrust returned by physics.step after each.
  target_velocity  ~20 (pos, vel) -> v_targ samples covering both altitude branches and r ~ 0.
  episodes         per class: DescentEnv(cls, variant="baseline", randomize=False, sensor=False).reset(seed=0), then
                   the policy (data/policies/lander_CLPS_baseline_s0.json) acting until the end; per step obs (float32
                   as the env returns it), action, reward, state, terminated, truncated; the final outcome record.
                   MK1 and LARGE also use the CLPS policy (the network is class-agnostic; its observation scaling
                   uses the class's own tilt limits), so their episodes test the env, not a good landing.
Floats are written with repr precision (17 significant digits).
"""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np

from lunarsim.lander import physics as P
from lunarsim.lander.classes import CLASSES
from lunarsim.lander.env import DescentEnv, ENV_VERSION, OBS_NAMES_V3, alt_history_step, obs_scale, target_velocity
from lunarsim.lander.policy import MlpPolicy

POLICY = os.path.join(ROOT, "data", "policies", "lander_CLPS_baseline_s0.json")


def physics_case(cls_name: str):
    c = CLASSES[cls_name]
    rng = np.random.default_rng(42)
    m_dry = c.m_dry_kg * 0.98
    prop = 125 * 0.2 * 1.03 * c.t_max_n / (c.isp_s * 0.98 * 9.80665)   # 125 steps of full thrust: runs out near step 190
    state = P.make_state([-180.0, 40.0, 300.0], [25.0, -3.0, -12.0], m_dry + prop, 0.2, -0.1)
    acts = []
    for k in range(200):
        if k < 40:
            a = [1.0, 1.0, -1.0]                        # full throttle, saturate the tilt towards the limit
        elif k < 60:
            a = [1.7, -2.5, 0.4]                        # out-of-range commands: must be clipped to +-1
        elif k < 160:
            a = list(rng.uniform(-1.2, 1.2, 3))
        else:
            a = [1.0, 0.0, 0.0]                         # burn out the remaining propellant
        acts.append([float(x) for x in a])
    s, states, thrusts = state.copy(), [], []
    for a in acts:
        s, thr = P.step(s, a, c, 0.2, thrust_scale=1.03, isp_scale=0.98, m_dry=m_dry)
        states.append(s.tolist())
        thrusts.append(float(thr))
    return {"cls": cls_name, "dt": 0.2, "thrust_scale": 1.03, "isp_scale": 0.98, "m_dry": m_dry,
            "state0": state.tolist(), "actions": acts, "states": states, "thrust": thrusts,
            "note": "propellant is exhausted before the last step (thrust 0 at the end)"}


def target_cases():
    rng = np.random.default_rng(7)
    out = []
    pts = [([0.0, 0.0, 15.0], [0.0, 0.0, -2.0]), ([0.0, 0.0, 0.0], [0.0, 0.0, -1.0]), ([1e-9, 0.0, 15.0], [0.0, 0.0, 0.0])]
    for _ in range(9):
        pts.append((list(rng.uniform([-300, -300, 16], [300, 300, 500])), list(rng.uniform(-30, 30, 3))))
    for _ in range(8):
        pts.append((list(rng.uniform([-20, -20, 0], [20, 20, 15])), list(rng.uniform(-3, 3, 3))))
    for pos, vel in pts:
        out.append({"pos": [float(x) for x in pos], "vel": [float(x) for x in vel],
                    "v_targ": [float(x) for x in target_velocity(pos, vel)]})
    return out


def episode(cls_name: str, pol: MlpPolicy):
    env = DescentEnv(cls=cls_name, variant="baseline", randomize=False, sensor=False)
    obs, _ = env.reset(seed=0)
    steps = [{"obs": [float(x) for x in obs], "state": env.state.tolist()}]
    done, info = False, {}
    while not done:
        a = [float(x) for x in pol.act(obs)]
        obs, r, te, tr, info = env.step(np.asarray(a, np.float32))
        steps.append({"action": a, "obs": [float(x) for x in obs], "reward": float(r), "state": env.state.tolist(),
                      "terminated": bool(te), "truncated": bool(tr)})
        done = te or tr
    return {"cls": cls_name, "variant": "baseline", "randomize": False, "sensor": False, "seed": 0,
            "policy": pol.id, "initial": steps[0], "steps": steps[1:], "outcome": info["outcome"],
            "note": "action = pol.act(obs) in float64 from the float32 obs, passed to env.step as float32"}


def alt_history_cases():
    """Readings with dropout holds for alt_history_step (obs v3): per step the reading, the held flag, the time
    and the four features."""
    seq = [(30.5, False), (29.8, False), (29.8, True), (29.8, True), (28.1, False), (27.4, False), (27.4, True),
           (25.9, False), (25.2, False), (25.2, True), (25.2, True), (25.2, True), (22.0, False)]
    hist, out = None, []
    for k, (h, held) in enumerate(seq):
        t = 0.2 * k
        hist, f = alt_history_step(hist, h, held, t)
        out.append({"h": h, "held": held, "t": t, "features": [float(x) for x in f]})
    return out


def episode_v3(cls_name: str):
    """obs v3 composition: sensor off (no holds), fixed actions, until the end."""
    env = DescentEnv(cls=cls_name, variant="baseline", randomize=False, sensor=False, obs_version=3)
    obs, _ = env.reset(seed=0)
    steps = [{"obs": [float(x) for x in obs]}]
    a = [0.15, 0.0, 0.0]
    done, info = False, {}
    while not done:
        obs, r, te, tr, info = env.step(np.asarray(a, np.float32))
        steps.append({"action": a, "obs": [float(x) for x in obs], "reward": float(r), "terminated": bool(te),
                      "truncated": bool(tr)})
        done = te or tr
    return {"cls": cls_name, "obs_version": 3, "obs_names": OBS_NAMES_V3,
            "obs_scale": obs_scale(CLASSES[cls_name], 3).tolist(), "steps": steps, "outcome": info["outcome"]}


def main():
    pol = MlpPolicy.from_json(POLICY)
    doc = {"format": "lunarsim-lander-parity", "version": 1, "env_version": ENV_VERSION, "policy": pol.id,
           "tolerance": 1e-6, "physics": [physics_case(c) for c in ("CLPS", "MK1", "LARGE")],
           "target_velocity": target_cases(), "episodes": [episode(c, pol) for c in ("CLPS", "MK1", "LARGE")],
           "alt_history": alt_history_cases(), "episodes_v3": [episode_v3("CLPS")]}
    out = os.path.join(ROOT, "tests", "fixtures", "lander_parity.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    e = doc["episodes"]
    print(f"wrote {out}: {os.path.getsize(out) / 1e3:.0f} kB; episode lengths {[len(x['steps']) for x in e]}, "
          f"outcomes {[x['outcome']['failure_kind'] for x in e]}")


if __name__ == "__main__":
    main()
