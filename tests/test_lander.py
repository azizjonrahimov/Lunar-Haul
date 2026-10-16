"""Learned lander: physics (always), environment / policy export / PPO smoke run (need the [ml] extra)."""
import json, math, os, sys, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim.lander import physics as P
from lunarsim.lander.classes import CLASSES, CLPS, G_MOON, G0, TIPOVER_DEG
from lunarsim.lander.policy import MlpPolicy


# ---------------------------------------------------------------------------
# physics (pure numpy)
# ---------------------------------------------------------------------------
def test_free_fall_is_exact():
    s = P.make_state([10.0, -5.0, 400.0], [3.0, -1.0, -15.0], CLPS.m_dry_kg)   # no propellant: no thrust
    dt, t = 0.2, 0.0
    for _ in range(50):
        s, thrust = P.step(s, [1.0, 0.0, 0.0], CLPS, dt)
        t += dt
        assert thrust == 0.0
    assert s[P.Z] == pytest.approx(400.0 - 15.0 * t - 0.5 * G_MOON * t * t, abs=1e-9)
    assert s[P.VZ] == pytest.approx(-15.0 - G_MOON * t, abs=1e-12)
    assert (s[P.X], s[P.Y]) == pytest.approx((10.0 + 3.0 * t, -5.0 - t), abs=1e-9)
    assert s[P.M] == CLPS.m_dry_kg


def test_hover_and_mass_flow():
    m = CLPS.m_gate_kg
    s = P.make_state([0, 0, 100.0], [0, 0, 0], m)
    a0 = P.thrust_to_throttle(m * G_MOON, CLPS)
    assert P.throttle_to_thrust(a0, CLPS) == pytest.approx(m * G_MOON)
    s1, thrust = P.step(s, [a0, 0.0, 0.0], CLPS, 0.2)
    assert thrust == pytest.approx(m * G_MOON)
    assert s1[P.VZ] == pytest.approx(0.0, abs=1e-12) and s1[P.Z] == pytest.approx(100.0, abs=1e-12)
    assert m - s1[P.M] == pytest.approx(m * G_MOON / (CLPS.isp_s * G0) * 0.2)
    # mass keeps dropping at constant thrust, so the vehicle starts to climb
    for _ in range(100):
        s1, _ = P.step(s1, [a0, 0.0, 0.0], CLPS, 0.2)
    assert s1[P.VZ] > 0


def test_throttle_floor_and_last_propellant():
    assert P.throttle_to_thrust(-1.0, CLPS) == CLPS.t_min_n and P.throttle_to_thrust(1.0, CLPS) == CLPS.t_max_n
    s = P.make_state([0, 0, 50.0], [0, 0, 0], CLPS.m_dry_kg + 0.1)               # 0.1 kg left
    s1, thrust = P.step(s, [1.0, 0, 0], CLPS, 0.2)
    assert s1[P.M] == pytest.approx(CLPS.m_dry_kg) and 0 < thrust < CLPS.t_max_n


def test_rate_limited_slew_and_tilt_limit():
    s = P.make_state([0, 0, 50.0], [0, 0, 0], CLPS.m_gate_kg)
    wmax, tmax = math.radians(CLPS.tilt_rate_max_dps), math.radians(CLPS.tilt_max_deg)
    s1, _ = P.step(s, [0.0, 1.0, -0.5], CLPS, 0.2)
    assert s1[P.TX] == pytest.approx(wmax * 0.2) and s1[P.TY] == pytest.approx(-0.5 * wmax * 0.2)
    assert s1[P.WX] == pytest.approx(wmax) and s1[P.WY] == pytest.approx(-0.5 * wmax)
    for _ in range(200):
        s1, _ = P.step(s1, [0.0, 1.0, 0.0], CLPS, 0.2)
    assert s1[P.TX] == pytest.approx(tmax) and s1[P.WX] == 0.0
    ux, uy, uz = P.thrust_direction(s1[P.TX], s1[P.TY])
    assert math.hypot(ux, math.hypot(uy, uz)) == pytest.approx(1.0)
    assert P.tilt_deg(s1[P.TX], 0.0) == pytest.approx(CLPS.tilt_max_deg)
    tx, ty = P.angles_from_direction(*P.thrust_direction(0.3, -0.2))
    assert (tx, ty) == pytest.approx((0.3, -0.2))


def test_touchdown_interpolation():
    prev = P.make_state([0, 0, 0.4], [1.0, 0, -2.0], 1000)
    new = P.make_state([0.2, 0, -0.4], [1.0, 0, -2.0], 999)
    td = P.touchdown(prev, new)
    assert td[P.Z] == 0.0 and td[P.X] == pytest.approx(0.1) and td[P.M] == pytest.approx(999.5)


def test_classes_flagged():
    for c in CLASSES.values():
        assert c.t_min_n < c.t_max_n and c.prop_gate_kg < c.m_gate_kg
        assert c.hover_tw > 1.0                                   # all classes can hover at the gate
        for k in ("m_gate_kg", "t_max_n", "t_min_n", "isp_s"):
            assert c.flags[k] in ("Measured", "Spec", "Modelled", "Assumed")
    mk1 = CLASSES["MK1"]
    assert mk1.t_min_n == 8900.0 and mk1.flags["t_min_n"] == "Spec"
    assert "2,000 lbf" in mk1.sources["t_min_n"] and "be7-engine-testing" in mk1.sources["t_min_n"]
    assert CLASSES["LARGE"].hover_tw == pytest.approx(1.5)


# ---------------------------------------------------------------------------
# policy runtime (numpy only)
# ---------------------------------------------------------------------------
def tiny_doc(det="mean_clipped"):
    return {"format": "lunarsim-policy", "version": 1, "kind": "mlp", "id": "tiny", "env": "x", "env_version": 1,
            "obs": {"names": ["a", "b"], "scale": [1, 1], "offset": [0, 0]},
            "act": {"kind": "box", "names": ["u"], "low": [-1.0], "high": [1.0]},
            "layers": [{"w": [[1.0, -2.0], [0.5, 0.5]], "b": [0.1, 0.0], "act": "tanh"},
                       {"w": [[2.0, 3.0]], "b": [-0.5], "act": "linear"}], "deterministic": det}


def test_mlp_forward_by_hand(tmp_path):
    p = tmp_path / "tiny.json"
    p.write_text(json.dumps(tiny_doc()), encoding="utf-8")
    pol = MlpPolicy.from_json(str(p))
    o = np.array([0.3, -0.4])
    h = np.tanh(np.array([[1.0, -2.0], [0.5, 0.5]]) @ o + [0.1, 0.0])
    mean = 2.0 * h[0] + 3.0 * h[1] - 0.5
    assert pol.act(o)[0] == pytest.approx(np.clip(mean, -1, 1), abs=1e-15)
    assert pol.act(np.array([[5.0, -5.0]]))[0][0] == 1.0          # clipped
    with pytest.raises(ValueError):
        MlpPolicy({**tiny_doc(), "format": "other"})


# ---------------------------------------------------------------------------
# environment, export, training (need the [ml] extra)
# ---------------------------------------------------------------------------
gym = pytest.importorskip("gymnasium")
from lunarsim.lander.env import DescentEnv, classify, OBS_NAMES, REWARD_VARIANTS  # noqa: E402
from lunarsim.lander import evaluate as E  # noqa: E402


def test_env_registered_and_check_env():
    sb3_checker = pytest.importorskip("stable_baselines3.common.env_checker")
    env = gym.make("lunar/Descent-v0").unwrapped
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sb3_checker.check_env(env, warn=True)
    from gymnasium.utils.env_checker import check_env
    check_env(DescentEnv(cls="MK1", variant="plume_aware"), skip_render_check=True)
    assert env.observation_space.shape == (len(OBS_NAMES),) and env.action_space.shape == (3,)


def test_reset_is_seeded_and_outcome_record():
    env = DescentEnv()
    o1, _ = env.reset(seed=7)
    o2, _ = env.reset(seed=7)
    assert np.array_equal(o1, o2)
    o3, _ = env.reset(seed=8)
    assert not np.array_equal(o1, o3)
    done, info = False, {}
    while not done:
        _, r, te, tr, info = env.step(np.zeros(3, np.float32))
        done = te or tr
    out = info["outcome"]
    for k in ("miss_m", "v_td", "tilt_deg", "prop_used_kg", "t_below_30m_s", "ok", "failure_kind"):
        assert k in out
    assert len(out["miss_m"]) == 2 and len(out["v_td"]) == 3 and out["prop_used_kg"] > 0


def test_classify_touchdown_box():
    def st(vx=0.0, vz=-1.0, tx=0.0, wx=0.0, x=0.0):
        s = P.make_state([x, 0, 0], [vx, 0, vz], 1000.0, tx, 0.0)
        s[P.WX] = wx
        return s
    assert classify(st(), 2.0, 50, False)["ok"]
    assert classify(st(vz=-2.5), 0, 50, False)["failure_kind"] == "velocity"
    assert classify(st(vx=1.2), 0, 50, False)["failure_kind"] == "velocity"
    assert classify(st(tx=math.radians(7)), 0, 50, False)["failure_kind"] == "tilt"
    assert classify(st(wx=math.radians(3)), 0, 50, False)["failure_kind"] == "tilt"
    assert classify(st(x=60.0), 0, 50, False)["failure_kind"] == "offpad"
    assert classify(st(vz=-2.5), 0, 50, True)["failure_kind"] == "sensor"
    assert classify(st(vz=-9.0), 0, 50, True)["failure_kind"] == "velocity"        # not a near miss
    im1 = classify(st(vx=0.9, vz=-2.7), 12.0, 50, False)                             # IM-1: tips over
    assert im1["landed_tilt_deg"] > TIPOVER_DEG and not im1["ok"]
    assert classify(st(vx=0.9, vz=-1.9), 5.0, 50, False)["landed_tilt_deg"] < TIPOVER_DEG


def test_reward_variants_differ():
    assert set(REWARD_VARIANTS) == {"baseline", "no_eta", "hover_bonus", "fuel_heavy", "plume_aware"}
    assert REWARD_VARIANTS["no_eta"]["eta"] == 0 and REWARD_VARIANTS["hover_bonus"]["eta"] > REWARD_VARIANTS["baseline"]["eta"]
    a = np.array([-0.2, 0.0, 0.0], np.float32)          # same open-loop episode under every variant
    totals = {}
    for v in REWARD_VARIANTS:
        env = DescentEnv(variant=v)
        env.reset(seed=3)
        done, tot = False, 0.0
        while not done:
            _, r, te, tr, _ = env.step(a)
            tot += r
            done = te or tr
        totals[v] = tot
    assert len({round(t, 9) for t in totals.values()}) == len(totals)


def test_classical_baseline_lands(tmp_path):
    env = DescentEnv(cls="CLPS")
    recs = E.run_episodes(env, lambda o, e: E.classical_action(e), 40, seed0=100_000)
    s = E.summarise(recs)
    assert s["pass_rate"] >= 0.85
    assert s["components"]["miss_r_m"]["mean"] < 10
    path = E.write_outcomes(recs, str(tmp_path), "classical_CLPS", {"policy": "classical", "cls": "CLPS"})
    doc = json.load(open(path, encoding="utf-8"))
    assert doc["format"] == "lunarsim-landing-outcomes" and len(doc["episodes"]) == 40
    assert doc["summary"]["components"]["prop_used_kg"]["n"] == 40
    assert os.path.exists(os.path.join(tmp_path, "outcomes_classical_CLPS.csv"))


def test_policy_json_round_trip_equals_sb3(tmp_path):
    sb3 = pytest.importorskip("stable_baselines3")
    from lunarsim.lander import export
    from lunarsim.lander.env import ACT_NAMES, ENV_ID, ENV_VERSION, OBS_OFFSET, obs_scale
    model = sb3.PPO("MlpPolicy", DescentEnv(), seed=0, device="cpu", policy_kwargs={"log_std_init": -0.5})
    out = tmp_path / "lander_test.json"
    doc = export.write(model, str(out), env_id=ENV_ID, env_version=ENV_VERSION, obs_names=OBS_NAMES,
                       obs_scale=obs_scale(CLPS).tolist(), obs_offset=OBS_OFFSET.tolist(), act_names=ACT_NAMES)
    chk = json.load(open(tmp_path / "lander_test.check.json", encoding="utf-8"))
    pol = MlpPolicy.from_json(str(out))
    assert len(chk["obs"]) == 100 and doc["deterministic"] == "mean_clipped"
    assert np.max(np.abs(pol.act(np.array(chk["obs"])) - np.array(chk["act"]))) < 1e-12   # reference vectors
    sb3_act, _ = model.predict(np.array(chk["obs"], np.float32), deterministic=True)
    assert np.max(np.abs(pol.act(np.array(chk["obs"])) - sb3_act)) < 1e-5               # float32 round-off
    # discrete action space -> argmax
    dmodel = sb3.PPO("MlpPolicy", "CartPole-v1", seed=0, device="cpu")
    ddoc = export.write(dmodel, str(tmp_path / "cartpole.json"), env_id="CartPole-v1", env_version=1,
                        obs_names=["x", "v", "th", "w"])
    dchk = json.load(open(tmp_path / "cartpole.check.json", encoding="utf-8"))
    assert ddoc["deterministic"] == "argmax"
    assert list(MlpPolicy(ddoc).act(np.array(dchk["obs"]))) == [int(a) for a in dchk["act"]]


def test_ppo_smoke_run_improves():
    """20k PPO steps raise the mean return of training episodes (last quarter vs first quarter).
    CPU, one torch thread and fixed seeds make the run deterministic (seed 2: about -170 -> -120)."""
    sb3 = pytest.importorskip("stable_baselines3")
    import torch
    torch.set_num_threads(1)
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.env_util import make_vec_env
    vec = make_vec_env(DescentEnv, n_envs=4, seed=2, env_kwargs={"curriculum": 0.3})
    model = sb3.PPO("MlpPolicy", vec, seed=2, device="cpu", n_steps=512, batch_size=256, n_epochs=10, gamma=0.999,
                    gae_lambda=0.98, policy_kwargs={"net_arch": [64, 64], "log_std_init": -0.5})
    rets = []

    class Returns(BaseCallback):
        def _on_step(self):
            rets.extend(i["episode"]["r"] for i in self.locals["infos"] if "episode" in i)
            return True
    model.learn(total_timesteps=20_000, callback=Returns())
    vec.close()
    q = len(rets) // 4
    assert q >= 20
    assert np.mean(rets[-q:]) > np.mean(rets[:q]) + 10, (np.mean(rets[:q]), np.mean(rets[-q:]))


# ---------------------------------------------------------------------------
# B-10b: behaviour-cloning warm start, hyper sets, the JS parity fixture
# ---------------------------------------------------------------------------
def test_bc_collect_and_fit_small(tmp_path):
    pytest.importorskip("stable_baselines3")
    from lunarsim.lander import bc_warmstart as BC
    data = BC.collect("CLPS", 3, seed0=5)
    assert data["obs"].shape[1] == len(OBS_NAMES) and data["act"].shape == (len(data["obs"]), 3)
    assert np.all(np.abs(data["act"]) <= 1.0) and len(data["ret"]) == len(data["obs"])
    from stable_baselines3 import PPO
    model = PPO("MlpPolicy", DescentEnv(), seed=0, device="cpu", policy_kwargs={"net_arch": [16, 16]})
    before = BC.fit(model, data, epochs=1, verbose=False)["actor_mse"]
    after = BC.fit(model, data, epochs=10, verbose=False)["actor_mse"]
    assert after < before
    assert float(model.policy.log_std.mean()) == pytest.approx(-1.5)


def test_hyper_sets_and_init_from_bc(tmp_path):
    sb3 = pytest.importorskip("stable_baselines3")
    from lunarsim.lander import train as T
    assert {"default", "b10b", "finetune"} <= set(T.HYPER_SETS)
    assert T.HYPER_SETS["finetune"]["clip_range"] == 0.1 and T.HYPER_SETS["finetune"]["normalize_reward"] is False
    bc = sb3.PPO("MlpPolicy", DescentEnv(), seed=1, device="cpu", policy_kwargs={"net_arch": [128, 128]})
    path = str(tmp_path / "bc.zip")
    bc.save(path)
    hp = dict(T.HYPER_SETS["finetune"], n_envs=1, n_steps=256, batch_size=128, n_epochs=1, learning_rate=0.0)
    r = T.train_descent("CLPS", "baseline", 256, 0, str(tmp_path / "pol"), str(tmp_path / "runs"), eval_every=10**9,
                        eval_n=1, subproc=False, hyper=hp, init_from_bc=path, curriculum=0.0)
    tr = r["doc"]["training"]
    assert tr["init"]["kind"] == "bc" and tr["hyper_set"] == "custom"
    # learning rate 0: the exported actor equals the BC actor
    w_bc = bc.policy.mlp_extractor.policy_net[0].weight.detach().double().numpy()
    assert np.allclose(np.array(r["doc"]["layers"][0]["w"]), w_bc, atol=1e-12)


def test_lander_parity_fixture_is_current():
    path = os.path.join(ROOT, "tests", "fixtures", "lander_parity.json")
    pol_path = os.path.join(ROOT, "data", "policies", "lander_CLPS_baseline_s0.json")
    if not (os.path.exists(path) and os.path.exists(pol_path)):
        pytest.skip("fixture or policy not present")
    doc = json.load(open(path, encoding="utf-8"))
    from lunarsim.lander.env import target_velocity, ENV_VERSION
    assert doc["env_version"] == ENV_VERSION
    for case in doc["physics"]:
        c = CLASSES[case["cls"]]
        s = np.array(case["state0"])
        for a, want, thr in zip(case["actions"], case["states"], case["thrust"]):
            s, t = P.step(s, a, c, case["dt"], case["thrust_scale"], case["isp_scale"], case["m_dry"])
            assert np.max(np.abs(s - want)) < 1e-9 and abs(t - thr) < 1e-9
        assert case["thrust"][-1] == 0.0
    for tv in doc["target_velocity"]:
        assert np.allclose(target_velocity(tv["pos"], tv["vel"]), tv["v_targ"], atol=1e-12)
    pol = MlpPolicy.from_json(pol_path)
    for ep in doc["episodes"]:
        env = DescentEnv(cls=ep["cls"], variant="baseline", randomize=False, sensor=False)
        obs, _ = env.reset(seed=0)
        assert np.allclose(obs, ep["initial"]["obs"], atol=1e-7)
        for st in ep["steps"]:
            a = pol.act(obs)
            assert np.allclose(a, st["action"], atol=1e-9)
            obs, r, te, tr, info = env.step(np.asarray(st["action"], np.float32))
            assert np.allclose(obs, st["obs"], atol=1e-6) and abs(r - st["reward"]) < 1e-9
            assert (te, tr) == (st["terminated"], st["truncated"])
        assert info["outcome"]["failure_kind"] == ep["outcome"]["failure_kind"]
    from lunarsim.lander.env import alt_history_step
    hist = None
    for c in doc["alt_history"]:
        hist, f = alt_history_step(hist, c["h"], c["held"], c["t"])
        assert np.allclose(f, c["features"], atol=1e-12)
    for ep in doc["episodes_v3"]:
        env = DescentEnv(cls=ep["cls"], variant="baseline", randomize=False, sensor=False, obs_version=3)
        obs, _ = env.reset(seed=0)
        assert len(obs) == 19 and np.allclose(obs, ep["steps"][0]["obs"], atol=1e-7)
        for st in ep["steps"][1:]:
            obs, r, te, tr, _ = env.step(np.asarray(st["action"], np.float32))
            assert np.allclose(obs, st["obs"], atol=1e-6) and abs(r - st["reward"]) < 1e-9


# ---------------------------------------------------------------------------
# B-10c: the card's final evaluation is the evaluate.py quantity; the lr schedule never goes negative
# ---------------------------------------------------------------------------
def test_final_eval_matches_evaluate_and_reloaded_model(tmp_path):
    sb3 = pytest.importorskip("stable_baselines3")
    from lunarsim.lander import train as T
    from lunarsim.lander.evaluate import evaluate as mc, run_episodes, EVAL_SEED0
    hp = dict(T.HYPER_SETS["finetune"], n_envs=2, n_steps=1536, batch_size=256, n_epochs=2)   # 2 x 1536 x 2 > 5000
    r = T.train_descent("CLPS", "baseline", 5000, 0, str(tmp_path / "pol"), str(tmp_path / "runs"),
                        eval_every=10**9, eval_n=20, subproc=False, hyper=hp, curriculum=0.0)
    card = r["doc"]["training"]["final_eval"]
    again = mc(r["policy"], "CLPS", 20, seed0=EVAL_SEED0)
    assert card["box_rate"] == again["touchdown_box_rate"] and card["failure_counts"] == again["failure_counts"]
    model = sb3.PPO.load(os.path.join(r["run_dir"], "model.zip"), device="cpu")
    recs = run_episodes(DescentEnv(cls="CLPS"), lambda o, e: model.predict(o, deterministic=True)[0], 20, EVAL_SEED0)
    assert sum(x["touchdown_ok"] for x in recs) / 20 == pytest.approx(card["box_rate"], abs=0.05)   # float32 vs float64
    stored = json.load(open(r["policy"], encoding="utf-8"))
    assert stored["training"]["final_eval"] == card                                                # rewritten into the file


def test_linear_schedule_is_clamped_at_zero():
    pytest.importorskip("stable_baselines3")
    from lunarsim.lander import train as T
    hp = dict(T.HYPER_SETS["finetune"])
    lr0 = float(hp["learning_rate"].split(":")[1])
    # reproduce the schedule train_descent builds
    kw_lr = (lambda progress_remaining: lr0 * max(progress_remaining, 0.0))
    assert kw_lr(1.0) == lr0 and kw_lr(0.0) == 0.0 and kw_lr(-0.04) == 0.0
    import inspect
    assert "max(progress_remaining, 0.0)" in inspect.getsource(T.train_descent)


# ---------------------------------------------------------------------------
# B-10d: observation-consistent expert, label inconsistency, DAgger record
# ---------------------------------------------------------------------------
def test_memoryless_law_is_a_function_of_the_observation_and_lands():
    env = DescentEnv(cls="CLPS")
    env.reset(seed=3)
    for _ in range(40):
        env.step(E.memoryless_action(env))
    a1 = E.memoryless_action(env)
    a2 = E.memoryless_action(env)                     # no internal state: calling again changes nothing
    assert np.array_equal(a1, a2)
    s = E.summarise(E.run_episodes(DescentEnv(cls="CLPS"), lambda o, e: E.memoryless_action(e), 30, 100_000))
    assert s["touchdown_box_rate"] >= 0.85


def test_label_inconsistency_metric():
    from lunarsim.lander.bc_warmstart import label_inconsistency
    rng = np.random.default_rng(0)
    obs = rng.normal(size=(3000, 4)).astype(np.float32)
    det = {"obs": obs, "act": np.tanh(obs[:, :3])}                                  # a function of obs
    rnd = {"obs": obs, "act": rng.uniform(-1, 1, (3000, 3)).astype(np.float32)}     # unrelated to obs
    assert label_inconsistency(det, n_query=200)["ratio_mean"] < 0.1
    assert label_inconsistency(rnd, n_query=200)["ratio_mean"] > 0.8


def test_bc_record_survives_dagger_rounds(tmp_path):
    pytest.importorskip("stable_baselines3")
    from lunarsim.lander import bc_warmstart as BC
    rec = BC.build_bc("CLPS", 3, str(tmp_path / "bc.zip"), net=(16, 16), epochs=1, eval_n=2, verbose=False,
                      dagger=1, dagger_episodes=2, dagger_epochs=1)
    assert rec["expert"] == "memoryless" and len(rec["dagger_rounds"]) == 2 and "classical_box_rate" in rec
    assert json.load(open(tmp_path / "bc.json", encoding="utf-8"))["dagger_rounds"][1]["round"] == 1


def test_obs_v3_extends_v2_without_changing_it():
    from lunarsim.lander.env import OBS_NAMES_V3, OBS_NAMES, obs_version_of
    a, b = DescentEnv(), DescentEnv(obs_version=3)
    oa, _ = a.reset(seed=11)
    ob, _ = b.reset(seed=11)
    assert len(oa) == 15 and len(ob) == 19 and np.array_equal(oa, ob[:15])
    for _ in range(400):
        act = np.array([0.1, 0.05, -0.02], np.float32)
        ra, rb = a.step(act), b.step(act)
        assert np.array_equal(ra[0], rb[0][:15]) and ra[1] == rb[1]
        if ra[2] or ra[3]:
            break
    assert obs_version_of(OBS_NAMES) == 2 and obs_version_of(OBS_NAMES_V3) == 3
    with pytest.raises(ValueError):
        DescentEnv(obs_version=4)


def test_export_card_from_bc_record():
    from lunarsim.lander.export import training_from_bc_record
    rec = {"cls": "MK1", "expert": "memoryless", "episodes": 10, "epochs": 2, "net": [16, 16], "seed": 0,
           "classical_box_rate": 0.9, "env_version": 3, "git_sha": "abc", "wallclock_s": 1.0, "obs_version": 3,
           "dagger_rounds": [{"round": 0, "samples": 100, "box_rate": 0.5, "label_inconsistency": 0.3},
                             {"round": 1, "samples": 150, "box_rate": 0.6, "label_inconsistency": 0.2}]}
    t = training_from_bc_record(rec)
    assert t["algo"] == "BC+DAgger" and t["expert"] == "memoryless" and t["cls"] == "MK1"
    assert t["reward_variant"] == "baseline" and t["obs_version"] == 3 and t["git_sha"] == "abc"
    assert [r["box_rate"] for r in t["rounds"]] == [0.5, 0.6] and t["rounds"][1]["samples"] == 150
    assert training_from_bc_record({**rec, "dagger_rounds": rec["dagger_rounds"][:1]})["algo"] == "BC"
