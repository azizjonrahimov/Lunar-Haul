"""Full-precision lander trajectory fixture (B-46): replays exactly in Python, and matches the exported episodes."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim.lander import physics as P
from lunarsim.lander.classes import CLASSES

FX = os.path.join(ROOT, "tests", "fixtures", "lander_trajectory_parity.json")


@pytest.fixture(scope="module")
def fx():
    with open(FX, encoding="utf-8") as f:
        return json.load(f)


def test_fixture_shape(fx):
    assert fx["format"] == "lunarsim-lander-trajectory-parity" and len(fx["episodes"]) == 2
    assert {(e["cls"], e["pilot"], e["pick"]) for e in fx["episodes"]} == {("CLPS", "classical", "p50"),
                                                                          ("CLPS", "lander_CLPS_bc_v3_s0", "p50")}
    for e in fx["episodes"]:
        assert len(e["state0"]) == P.STATE_SIZE and len(e["steps"]) == e["n_steps"]
        assert all(len(s["action"]) == 3 and len(s["state"]) == P.STATE_SIZE for s in e["steps"])
        assert e["steps"][-1].get("touchdown") is True


def test_physics_replay_is_exact(fx):
    """physics.step chained from state0 with the recorded actions (physics.touchdown on the landing step) gives every
    recorded state bit for bit: what the JS port must reproduce."""
    for e in fx["episodes"]:
        c = CLASSES[e["cls"]]
        s = np.array(e["state0"])
        for k, st in enumerate(e["steps"]):
            new, _ = P.step(s, st["action"], c, e["dt"], e["thrust_scale"], e["isp_scale"], e["m_dry"])
            if st.get("touchdown"):
                new = P.touchdown(s, new)
            assert np.array_equal(new, np.array(st["state"])), (e["pilot"], k)
            s = new


def test_env_replay_is_exact(fx):
    pytest.importorskip("gymnasium")
    from lunarsim.lander.env import DescentEnv
    for e in fx["episodes"]:
        env = DescentEnv(cls=e["cls"], variant=e["reward_variant"], sensor=True, obs_version=e["obs_version"])
        env.reset(seed=e["seed"])
        assert np.array_equal(env.state, np.array(e["state0"]))
        assert (env.thrust_scale, env.isp_scale, env.m_dry) == (e["thrust_scale"], e["isp_scale"], e["m_dry"])
        for k, st in enumerate(e["steps"]):
            assert np.array_equal(np.array(env.last_est[0]), np.array(st["est_pos"])), (e["pilot"], k)
            env.step(st["action"])
            assert np.array_equal(env.state, np.array(st["state"])), (e["pilot"], k)


def test_matches_the_exported_episodes(fx):
    """The export (trajectories-v1.json) stores positions to 1e-6 m at step boundaries and mid-steps."""
    with open(os.path.join(ROOT, "data", "policies", "trajectories-v1.json"), encoding="utf-8") as f:
        doc = json.load(f)
    for e in fx["episodes"]:
        pil = next(p for p in doc["pilots"] if p["cls"] == e["cls"] and p["pilot"] == e["pilot"])
        ep = next(x for x in pil["episodes"] if x["pick"] == e["pick"])
        pos = np.asarray(ep["pos_m"])
        t = np.asarray(ep["t_s"]) if "t_s" in ep else None
        states = [e["state0"]] + [s["state"] for s in e["steps"][:-1]]
        bnd = np.array([s[:3] for s in states])
        if t is not None:
            idx = [int(np.argmin(np.abs(t - k * e["dt"]))) for k in range(len(states))]
            d = float(np.max(np.abs(pos[idx] - bnd)))
        else:
            d = float(np.max(np.abs(pos[0:2 * len(states):2] - bnd)))
        assert d < 1e-6 + 1e-9, (e["pilot"], d)
