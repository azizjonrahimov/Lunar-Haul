"""Rover driving model: physics calibrations (always), terrain-based env / expert / tables (need [terrain] + [ml])."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim.rover import physics as R


# ---------------------------------------------------------------------------
# physics (pure numpy)
# ---------------------------------------------------------------------------
def test_slip_curves_hu2024():
    g = np.linspace(0, 30, 61)
    for phi in (37.8, 40.0, 42.0, 45.0, 47.8):
        assert np.all(np.diff(R.slip(g, phi)) >= 0)                                 # monotone in slope
    for gg in (0, 5, 10, 15, 20, 25, 30):
        assert R.slip(gg, 37.8) >= R.slip(gg, 42.0) >= R.slip(gg, 47.8)              # looser soil slips more
    # the digitised points (Hu et al. 2024 Figs 7/13, 440 kg, lunar gravity)
    assert [R.slip(x, 42.0) for x in (0, 5, 10, 15, 20, 25, 30)] == pytest.approx([0.04, 0.13, 0.30, 0.67, 0.86, 0.92, 0.96])
    assert R.slip(15.0, 47.8) == pytest.approx(0.18) and R.slip(10.0, 37.8) == pytest.approx(0.74)
    assert R.slip(10.0, 39.9) == pytest.approx(0.5 * (0.74 + 0.30), abs=1e-9)        # linear in phi
    assert R.slip(30.0, 47.8) > R.DIG_IN_SLIP and R.slip(20.0, 42.0) > R.DIG_IN_SLIP  # dig-in
    assert R.slip(-10.0, 42.0) == R.slip(0.0, 42.0) == R.FLAT_SLIP_REF                # downhill = flat value
    assert R.slip(5.0, 30.0) == R.slip(5.0, 37.8)                                     # phi clipped to the data


def test_energy_calibration():
    assert R.energy_wh(1000.0, 0.0, R.slip(0.0), mass_kg=700.0) == pytest.approx(58.5)   # LRV 57-60 Wh/km
    assert R.C_RR_EFF == pytest.approx(0.178, abs=0.001)
    flat = R.energy_wh(1000.0, 0.0, R.slip(0.0))
    assert flat == pytest.approx(58.5 * R.ROVER["mass_kg"] / 700.0)
    assert R.energy_wh(1000.0, 10.0, R.slip(10.0)) > 2 * flat
    assert R.energy_wh(1000.0, -10.0, R.slip(-10.0)) < flat                    # no grade work downhill


def test_teleop_cadence_reproduces_jsc_on_paper():
    for rtt, smg in R.LITAKER_SMG_KMH.items():
        every, stop_s = R.stop_plan("teleop", rtt)
        ground = R.speed_cap_mps("teleop", rtt) * (1.0 - R.slip(0.0))
        t = 1000.0 / ground + 1000.0 / every * stop_s
        assert 3.6 * 1000.0 / t == pytest.approx(smg, rel=1e-9)
    assert R.stop_plan("autonomous") == (math.inf, 0.0)
    assert R.speed_cap_mps("teleop", 4.0) < R.speed_cap_mps("teleop", 0.0)


def test_slope_and_lighting_factors():
    assert R.slope_speed_factor(5) == 1.0 and R.slope_speed_factor(15) == 0.5 and R.slope_speed_factor(21) == 0.0
    assert R.lighting_factor(0.0, 0.0, False) == pytest.approx(math.cos(math.radians(25)))     # up-sun tacking
    assert R.lighting_factor(180.0, 0.0, False) == 1.0
    assert R.lighting_factor(180.0, 0.0, True) == R.SHADOW_SPEED_FACTOR
    assert R.lighting_factor(90.0, R.NIGHT, True) == R.SHADOW_SPEED_FACTOR


# ---------------------------------------------------------------------------
# terrain-based parts
# ---------------------------------------------------------------------------
rasterio = pytest.importorskip("rasterio")
pytest.importorskip("PIL")
from rasterio.transform import from_origin  # noqa: E402
from lunarsim import terrain as T  # noqa: E402
from lunarsim.rover import expert as X, tables as TB  # noqa: E402

PROJ = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
N, PX = 600, 5.0          # 3 km tile


def make_pack(tmp, name, fn, z_scale=0.01):
    cols = np.arange(N)
    XX, YY = np.meshgrid((cols + 0.5) * PX, N * PX - (cols + 0.5) * PX)     # local coordinates, row 0 = north
    z = fn(XX, YY).astype(np.float32)
    src = str(tmp / f"{name}.tif")
    with rasterio.open(src, "w", driver="GTiff", width=N, height=N, count=1, dtype="float32", crs=PROJ,
                       transform=from_origin(0.0, N * PX, PX, PX)) as ds:
        ds.write(z, 1)
    out = str(tmp / name)
    T.build_pack(src, out, "SiteTest", z_scale=z_scale)
    return T.Terrain(out)


@pytest.fixture(scope="module")
def flat(tmp_path_factory):
    return make_pack(tmp_path_factory.mktemp("rv"), "flat", lambda x, y: 0.0 * x + 100.0)


@pytest.fixture(scope="module")
def ramp(tmp_path_factory):                      # 8 deg ramp rising towards +x
    return make_pack(tmp_path_factory.mktemp("rv"), "ramp", lambda x, y: x * math.tan(math.radians(8.0)))


def test_roughness_is_detrended(ramp):
    assert float(np.max(ramp.roughness20())) < 0.02        # a plane has no roughness, however steep


def test_fast_integrator_flat_leg_matches_jsc(flat):
    route = np.array([[200.0, 1500.0], [2800.0, 1500.0]])
    prof = TB.leg_profile(flat, route, None)
    for rtt, smg in R.LITAKER_SMG_KMH.items():
        r = TB.drive_profile(prof, "teleop", rtt, None, np.random.default_rng(0), 400, phi_deg=R.PHI_REF)
        det = prof["length_m"] / (r["t_move_s"] + r["stops"] * R.teleop_stop_s(rtt)) * 3.6
        assert det == pytest.approx(smg, rel=0.02), (rtt, det, smg)     # whole stops only: floor(length / L)


gym = pytest.importorskip("gymnasium")
from lunarsim.rover.env import DriveEnv, drive_expert, SCALAR_NAMES  # noqa: E402


@pytest.mark.parametrize("rtt", [0.0, 4.0, 6.0, 8.0])
def test_env_teleop_flat_leg_within_5_percent_of_jsc(flat, rtt):
    env = DriveEnv(flat, autonomy="teleop", rtt_s=rtt, sun_az_deg=None)
    leg = drive_expert(env, {"waypoints": [[200.0, 1500.0], [2800.0, 1500.0]], "autonomy": "teleop", "rtt_s": rtt,
                             "sun_az_deg": None, "phi": R.PHI_REF})
    assert leg["reached"] and leg["interventions"] == 0
    smg = leg["distance_m"] / leg["time_s"] * 3.6
    assert smg == pytest.approx(R.LITAKER_SMG_KMH[rtt], rel=0.05), (rtt, smg)


def test_env_contract(flat):
    from gymnasium.utils.env_checker import check_env
    env = DriveEnv(flat, autonomy="supervised", sun_az_deg=90.0, random_leg_m=500.0)
    check_env(env, skip_render_check=True)
    obs, _ = env.reset(seed=1)
    assert obs["patch"].shape == (3, 32, 32) and obs["scalars"].shape == (len(SCALAR_NAMES),)
    o2, _ = env.reset(seed=1)
    assert np.array_equal(obs["patch"], o2["patch"])
    _, r, term, trunc, info = env.step(env.action_space.sample())
    assert isinstance(r, float) and not term


def test_expert_reaches_waypoints_on_a_ramp(ramp):
    a, b = (300.0, 300.0), (2700.0, 2600.0)
    route = X.plan(ramp, a, b, 0.0)
    assert route is not None
    s = ramp.leg_stats(a, b)
    assert s["climb_m"] > 300
    env = DriveEnv(ramp, autonomy="autonomous", sun_az_deg=0.0)
    leg = drive_expert(env, {"waypoints": route, "autonomy": "autonomous", "sun_az_deg": 0.0})
    assert leg["reached"] and leg["interventions"] == 0
    assert leg["energy_wh"] > R.energy_wh(np.hypot(2400, 2300), 0.0, R.slip(0.0))     # climbing costs more
    # downhill is cheaper than uphill
    back = drive_expert(env, {"waypoints": route[::-1], "autonomy": "autonomous", "sun_az_deg": 0.0})
    assert back["reached"] and back["energy_wh"] < leg["energy_wh"]


def test_astar_avoids_impassable_wall(tmp_path):
    def wall(x, y):                               # a 40 m high, 50 m wide ridge across the middle with a gap at y > 2400
        return np.where((x > 1400) & (x < 1450) & (y < 2400), 40.0, 0.0)
    t = make_pack(tmp_path, "wall", wall)
    route = X.plan(t, (500.0, 500.0), (2500.0, 500.0), None)
    assert route is not None and route[:, 1].max() > 2350          # detours through the gap
    assert np.max(t.slope(*X.densify(route, 5.0).T)) <= R.ROVER["slope_hard_deg"] + 1


def test_tables_document(flat):
    sites = {"sites": [{"id": "BASE", "xy_m": [1500.0, 1500.0]}, {"id": "DEPOT", "xy_m": [2500.0, 1500.0]}],
             "pads": {"1": {"PAD_A": [1500.0, 2500.0], "PAD_B": [2500.0, 1500.0]}}}
    legs = dict((n, (a, b)) for n, a, b in TB.legs_from_sites(sites))
    assert {"BASE->DEPOT", "DEPOT->BASE", "PAD_A@1->BASE", "BASE->PAD_A@1", "PAD_B@1->DEPOT"} <= set(legs)
    doc = TB.build(flat, sites, seeds=5, lighting=(90.0, R.NIGHT), rtts=(0.0, 4.0))
    assert doc["format"] == "lunarsim-driving" and doc["version"] == 1
    assert {"leg": "PAD_B@1->DEPOT", "reason": "coincident end points"} in doc["skipped"]
    e = doc["legs"]["BASE->DEPOT"]["autonomy"]["teleop"]["rtt_s"]["4"]["lighting"]["90"]
    assert e["time_h"]["dist"] == "lognormal" and e["interventions"]["dist"] == "poisson"
    night = doc["legs"]["BASE->DEPOT"]["autonomy"]["teleop"]["rtt_s"]["4"]["lighting"]["night"]
    assert night["time_h"]["mean"] > e["time_h"]["mean"]           # night driving is slower
    auto = doc["legs"]["BASE->DEPOT"]["autonomy"]["autonomous"]["rtt_s"]["4"]["lighting"]["90"]
    assert auto["time_h"]["mean"] < e["time_h"]["mean"]
    json.dumps(doc)


# ---------------------------------------------------------------------------
# B-13: behaviour-cloned driver (dataset, training smoke, ONNX round trip, OnnxDriver)
# ---------------------------------------------------------------------------
torch = pytest.importorskip("torch")
from lunarsim.rover import bc as BC  # noqa: E402


@pytest.fixture(scope="module")
def flat_data(flat):
    legs = [("A->B", (300.0, 1500.0), (900.0, 1500.0))]
    return BC.collect(flat, legs, lambda env, ex: ex, stride=5, lighting=(90.0,), seed=0)


def test_bc_dataset_shapes(flat_data):
    d = flat_data
    n = len(d["act"])
    assert n > 20
    assert d["patch"].shape == (n, 3, 32, 32) and d["patch"].dtype == np.float16
    assert d["scalars"].shape == (n, len(SCALAR_NAMES)) and d["act"].shape == (n, 2)
    assert np.all(np.abs(d["act"]) <= 1.0) and d["legs"][0]["reached"]


def test_bc_training_smoke_and_onnx_round_trip(flat, flat_data, tmp_path):
    pytest.importorskip("onnxruntime")
    model = BC.make_model()
    with torch.no_grad():
        before = float(torch.nn.functional.mse_loss(
            model(torch.as_tensor(flat_data["patch"].astype(np.float32)), torch.as_tensor(flat_data["scalars"])),
            torch.as_tensor(flat_data["act"])))
    r = BC.train(model, flat_data, epochs=1000, batch=64, max_steps=200, device="cpu")
    assert r["steps"] == 200 and r["mse"] < before
    card = BC.write_card(model, "rover_test", str(tmp_path), {"algo": "test"}, {})
    assert card["kind"] == "cnn" and card["opset"] == 17 and card["runtime"]["torch_onnx_max_abs_err"] <= 1e-5
    chk = json.load(open(tmp_path / "rover_test.check.json", encoding="utf-8"))
    from lunarsim.rover.onnx_driver import OnnxDriver
    drv = OnnxDriver(str(tmp_path / "rover_test.json"))
    got = drv.act_batch(np.array(chk["patch"], np.float32), np.array(chk["scalars"], np.float32))
    assert np.max(np.abs(got - np.array(chk["action"]))) < 1e-6
    with torch.no_grad():
        ref = model(torch.as_tensor(np.array(chk["patch"], np.float32)), torch.as_tensor(np.array(chk["scalars"], np.float32))).numpy()
    assert np.max(np.abs(got - ref)) < 1e-5
    # the cloned driver drives a flat leg through the onnx runtime
    env = DriveEnv(flat, autonomy="autonomous", sun_az_deg=90.0)
    _, leg = BC.drive(env, [[300.0, 1500.0], [900.0, 1500.0]], 90.0, drv, None, 1, max_steps=600, record=False)
    assert leg["distance_m"] > 100.0
    bad = dict(card, onnx_sha256="0" * 64)
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256"):
        OnnxDriver(str(tmp_path / "bad.json"))


def test_expert_driver_interface_and_evaluation(flat):
    legs = [("A->B", (300.0, 1500.0), (900.0, 1500.0))]
    ev = BC.evaluate_driver(flat, legs, lambda env: BC.ExpertDriver(env), autonomies=("autonomous",), lighting=(90.0,))
    a = ev["autonomous"]
    assert a["reached"] == a["runs"] == 1 and a["interventions"] == 0 and a["autonomy_pct"] == pytest.approx(100.0)


def test_phi_is_sampled_per_run_and_slows_loose_soil(ramp):
    route = X.plan(ramp, (300.0, 1500.0), (2700.0, 1500.0), None)              # 8 deg uphill all the way
    prof = TB.leg_profile(ramp, route, None)
    loose = TB.drive_profile(prof, "autonomous", 4.0, None, np.random.default_rng(0), 5, phi_deg=37.8)
    dense = TB.drive_profile(prof, "autonomous", 4.0, None, np.random.default_rng(0), 5, phi_deg=47.8)
    assert loose["t_move_s"] > 1.5 * dense["t_move_s"]                       # slip 0.57 vs 0.06 at 8 deg
    mixed = TB.drive_profile(prof, "autonomous", 4.0, None, np.random.default_rng(1), 200)
    assert 37.8 <= mixed["phi_deg"].min() and mixed["phi_deg"].max() <= 47.8 and mixed["phi_deg"].std() > 2
