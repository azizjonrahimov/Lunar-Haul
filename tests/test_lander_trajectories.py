"""Descent trajectories for the 3D lab (B-33, lunarsim/lander/trajectories.py): selection, recording, parity."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

pytest.importorskip("gymnasium")
from lunarsim.lander import trajectories as T
from lunarsim.lander import physics as P
from lunarsim.formats import load_schema

DATA = os.path.join(ROOT, "data", "policies", "trajectories-v1.json")


def test_quaternion_takes_z_to_the_thrust_direction():
    rng = np.random.default_rng(0)
    for _ in range(200):
        tx, ty = rng.uniform(-0.8, 0.8, 2)
        u = np.array(P.thrust_direction(tx, ty))
        q = T.quaternion_from_direction(u)
        assert abs(np.linalg.norm(q) - 1) < 1e-12
        assert np.allclose(T.rotate(q, [0, 0, 1]), u, atol=1e-12)
    assert T.quaternion_from_direction([0, 0, 1]) == [1.0, 0.0, 0.0, 0.0]


def test_selection_percentiles_ties_and_first_failure():
    def ep(seed, miss, kind=None):
        return {"seed": seed, "miss_m": [miss, 0.0], "failure_kind": kind, "ok": kind is None}
    eps = [ep(10 + i, float(i)) for i in range(11)] + [ep(5, 99.0, "timeout"), ep(30, 5.0), ep(31, 7.0, "velocity")]
    picks = {p["pick"]: p for p in T.select_episodes(eps)}
    ground_miss = sorted([float(i) for i in range(11)] + [5.0, 7.0])
    assert picks["p50"]["target_miss_m"] == pytest.approx(np.percentile(ground_miss, 50))
    assert picks["p50"]["seed"] == 15                         # miss 5.0 at seeds 15 and 30: the lower seed
    assert picks["p10"]["seed"] == 11 and picks["p90"]["seed"] in (19, 20)
    assert picks["first_failure"]["seed"] == 5                 # the timeout (not part of the percentiles)
    assert "first_failure" not in {p["pick"] for p in T.select_episodes([ep(1, 1.0), ep(2, 2.0)])}


@pytest.fixture(scope="module")
def classical_episode():
    controller, obs_v, variant, _ = T.controller_for("law", "classical", None)
    return T.record_episode("CLPS", controller, obs_v, variant, 100483), (controller, obs_v, variant)


def test_recording_10hz_sampling_and_reward_split(classical_episode):
    rec, _ = classical_episode
    t = np.array(rec["t"])
    assert np.allclose(np.diff(t[:-1]), 0.1) and 0 < t[-1] - t[-2] <= 0.1 + 1e-9
    assert len(rec["pos"]) == len(t) and rec["n_steps"] == len(rec["steps"]["throttle"])
    pos, vel = np.asarray(rec["pos"]), np.asarray(rec["vel"])
    # within a step the acceleration is constant: the mid-step sample sits on that parabola
    a = (vel[2] - vel[0]) / 0.2
    assert np.allclose(pos[1], pos[0] + vel[0] * 0.1 + 0.5 * a * 0.01, atol=1e-9)
    assert rec["outcome"]["ok"] and abs(pos[-1][2]) < 1e-9                # ends on the ground
    s = rec["steps"]
    total = sum(s["track"]) + sum(s["effort"]) + sum(s["low_alt"]) + sum(s["terminal"]) + rec["eta"] * rec["n_steps"]
    assert total == pytest.approx(rec["score"], abs=1e-6)           # (each step was checked to 1e-9 while recording)
    assert s["terminal"][-1] > 0 and all(x == 0 for x in s["terminal"][:-1])
    th = np.asarray(s["throttle"])
    assert th.min() >= 0.2 - 1e-9 and th.max() <= 1.0 + 1e-9        # CLPS floor 1000 N of 5000 N
    assert s["prop_kg"][-1] < s["prop_kg"][0]


def test_parity_replay_reproduces_compact_positions(classical_episode):
    rec, (controller, obs_v, variant) = classical_episode
    c = T.compact(rec)
    again = T.record_episode("CLPS", controller, obs_v, variant, rec["seed"])
    assert np.max(np.abs(np.asarray(again["pos"]) - np.asarray(c["pos_m"]))) < 1e-6
    doc = {"format": T.TRAJ_FORMAT, "version": 1, "pilots": [{"cls": "CLPS", "pilot": "classical", "episodes": [c]}]}
    assert T.validate(doc) == []
    bad = json.loads(json.dumps(doc))
    bad["pilots"][0]["episodes"][0]["throttle"].append(0.5)
    bad["pilots"][0]["episodes"][0]["reward"]["score"] += 50.0
    errs = T.validate(bad)
    assert any("throttle length" in e for e in errs) and any("sum to the score" in e for e in errs)


def test_policy_pilot_records():
    controller, obs_v, variant, prov = T.controller_for("policy", "lander_CLPS_bc_v3_s0", "lander_CLPS_bc_v3_s0.json")
    assert obs_v == 3 and variant == "baseline" and prov["policy"] == "lander_CLPS_bc_v3_s0"
    rec = T.record_episode("CLPS", controller, obs_v, variant, 100471)
    assert rec["n_steps"] > 100
    _, _, v_hover, _ = T.controller_for("policy", "lander_CLPS_hover_bonus_v1_s0", "lander_CLPS_hover_bonus_v1_s0.json")
    assert v_hover == "hover_bonus"


@pytest.mark.skipif(not os.path.isfile(DATA), reason="trajectories-v1.json not generated")
def test_committed_file_validates_and_replays():
    assert os.path.getsize(DATA) <= 3 * 1024 * 1024
    with open(DATA, encoding="utf-8") as f:
        doc = json.load(f)
    assert T.validate(doc) == []
    combos = {(p["cls"], p["pilot"]) for p in doc["pilots"]}
    assert len(combos) == 9 and ("CLPS", "lander_CLPS_hover_bonus_v1_s0") in combos
    assert all(e["matches_monte_carlo"] for p in doc["pilots"] for e in p["episodes"])
    assert doc["plume"]["CLPS"]["f33_onset_altitude_m"]["value"] == 15.0
    jsonschema = pytest.importorskip("jsonschema", reason="jsonschema not installed")
    jsonschema.validate(doc, load_schema("trajectories-v1"))


@pytest.mark.skipif(not os.path.isfile(DATA), reason="trajectories-v1.json not generated")
def test_committed_file_parity_two_episodes():
    assert T.check(DATA, max_episodes=2, log=lambda *a: None) < 1e-6
