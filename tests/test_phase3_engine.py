"""Phase-3 DES integration (B-12): opt-in terrain legs, landing outcomes, plume keep-out, trace v2.

Synthetic outcome and driving tables (written in fixtures) keep the expectations exact; the site positions and
line-of-sight checks use the committed terrain pack data/terrain/connecting_ridge.
"""
import hashlib, json, math, os, sys, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

pytest.importorskip("PIL")
if not os.path.exists(os.path.join(ROOT, "data", "terrain", "connecting_ridge", "sites.json")):
    pytest.skip("terrain pack connecting_ridge not present", allow_module_level=True)

from lunarsim import dispatch, run, Simulation
from lunarsim.config import library, scenario_to_dict, scenario_from_dict
from lunarsim.formats import validate_trace, validate_scenario, load_schema
from lunarsim.phase3 import DrivingModel, SiteMap
from lunarsim.world import build_default_world

warnings.filterwarnings("ignore", category=RuntimeWarning)
BASELINE_MD5 = "ebb9e0dea68005cddf4ab4d2bda1bfdd"          # lunarsim compare --scenario P2-default --seeds 3


@pytest.fixture(autouse=True)
def in_root(monkeypatch):
    monkeypatch.chdir(ROOT)


def outcomes_table(path, cls, miss=(1.0, -1.0), kind=None, n=20):
    eps = [{"seed": i, "cls": cls, "miss_m": list(miss), "v_td": [0, 0, -1], "tilt_deg": 1.0, "rate_dps": 0.1,
            "landed_tilt_deg": 2.0, "slope_deg": 1.0, "prop_used_kg": 50.0, "t_below_30m_s": 20.0, "t_flight_s": 80.0,
            "touchdown_ok": kind is None, "ok": kind is None, "failure_kind": kind} for i in range(n)]
    with open(os.path.join(path, f"outcomes_{cls}.json"), "w", encoding="utf-8") as f:
        json.dump({"format": "lunarsim-landing-outcomes", "version": 1, "episodes": eps}, f)


def landing_dir(tmp_path_factory, name, **kw):
    d = tmp_path_factory.mktemp(name)
    for cls in ("CLPS", "MK1", "LARGE"):
        outcomes_table(str(d), cls, **kw)
    return str(d)


@pytest.fixture(scope="module")
def lm_ok(tmp_path_factory):
    return landing_dir(tmp_path_factory, "ok")


@pytest.fixture(scope="module")
def lm_offpad(tmp_path_factory):
    return landing_dir(tmp_path_factory, "off", miss=(300.0, 400.0))         # 500 m: off any 50 m pad


@pytest.fixture(scope="module")
def lm_failed(tmp_path_factory):
    return landing_dir(tmp_path_factory, "fail", kind="velocity")


@pytest.fixture(scope="module")
def driving(tmp_path_factory):
    """A lunarsim-driving table for every ordered pair of world sites at the 1 km standoff: 3 km/h made good
    over the straight-line distance x 1.3, 150 Wh/km, 0.1 interventions per km."""
    sm = SiteMap(build_default_world(), "connecting_ridge", "1")
    names = list(sm.xy_km)
    legs = {}
    for a in names:
        for b in names:
            if a == b:
                continue
            km = 1.3 * sm.dist_km(a, b)
            ent = {"time_h": {"mu": math.log(km / 3.0), "sigma": 0.1, "dist": "lognormal"},
                   "energy_kwh": {"mu": math.log(0.15 * km), "sigma": 0.05, "dist": "lognormal"},
                   "interventions": {"lambda": 0.1 * km, "dist": "poisson"}, "stops": 0}
            by_rtt = {r: {"lighting": {"90": ent, "night": ent}} for r in ("0", "4", "6", "8")}
            nm = lambda s: f"{s}@1" if s.startswith("PAD") else s
            legs[f"{nm(a)}->{nm(b)}"] = {"route": {"90": {"length_m": 1000 * km}, "night": {"length_m": 1000 * km}},
                                         "autonomy": {au: {"rtt_s": by_rtt} for au in ("teleop", "supervised", "autonomous")}}
    p = tmp_path_factory.mktemp("drv") / "driving.json"
    p.write_text(json.dumps({"format": "lunarsim-driving", "version": 1, "rtt_s": ["0", "4", "6", "8"],
                             "model": {"mass_kg": 1600.0, "c_rr_eff": 0.1764}, "legs": legs}), encoding="utf-8")
    return str(p)


def p2(**kw):
    return library()["P2-default"].with_(**kw)


def summary(sc, seed=1, mech=dispatch.marketplace):
    return run(sc, mech, seed=seed)


# ---------------------------------------------------------------------------
def test_all_off_is_byte_identical_to_v2(tmp_path):
    from lunarsim.cli import main
    out = tmp_path / "c.csv"
    main(["compare", "--scenario", "P2-default", "--seeds", "3", "--out", str(out)])
    assert hashlib.md5(out.read_bytes()).hexdigest() == BASELINE_MD5
    sc = library()["P2-default"]
    assert all(getattr(sc, k) is None for k in ("terrain", "pad_standoff_km", "landing_model", "plume", "autonomy_model"))
    assert "terrain" not in scenario_to_dict(sc)                        # saved v2 scenarios unchanged
    assert "plume_standdowns" not in summary(sc)
    sim = Simulation(library()["P2-4-vehicles"], dispatch.marketplace, seed=3, mech_kwargs={"trace": True})
    sim.run()
    assert sim.trace_export()["version"] == 1


@pytest.mark.parametrize("feature", ["terrain", "landing", "plume", "autonomy"])
def test_each_feature_changes_results_deterministically(feature, lm_offpad, driving):
    kw = {"terrain": {"terrain": "connecting_ridge", "pad_standoff_km": "2"},
          "landing": {"landing_model": {"policy": "{cls}", "dir": lm_offpad}},
          "plume": {"plume": {"keepout_km": 3.0, "standdown_h": 6.0}},
          "autonomy": {"terrain": "connecting_ridge", "pad_standoff_km": "1", "autonomy_model": driving}}[feature]
    sc = p2(**kw)
    a, b = summary(sc), summary(sc)
    assert a == b or all((x == y) or (x != x and y != y) for x, y in zip(a.values(), b.values()))
    base = summary(p2())
    assert "plume_standdowns" in a
    changed = [k for k in base if k in a and base[k] == base[k] and a[k] != base[k]]
    if feature == "terrain":                    # site positions alone do not change v2 travel (graph distances)
        assert a["jobs"] == base["jobs"]
    else:
        assert changed, feature


def test_keepout_blocks_pad_jobs_inside_windows(driving):
    sc = library()["P2-4-vehicles"].with_(terrain="connecting_ridge", pad_standoff_km="1",
                                          plume={"keepout_km": 1.0, "standdown_h": 6.0})
    sim = Simulation(sc, dispatch.marketplace, seed=0, mech_kwargs={"trace": True})
    s = sim.run()
    tr = sim.trace_export()
    wins = tr["plume_windows"]
    assert wins and s["plume_standdowns"] > 0 and s["standdown_vehicle_h"] > 0
    pads = set(sim.world.pads)
    for job in tr["jobs"]:
        for a, b, t0, t1, _ in job["segments"]:
            if a == b:
                continue                          # holds and handling at one place
            for site, tt in ((a, t0), (b, t1)):   # leaving or reaching a pad
                if site in pads:
                    assert not any(w[2] == site and w[0] + 1e-6 < tt < w[1] - 1e-6 for w in wins), (job["kind"], site, tt)
    assert tr["shelters"] and all(sh["site"] not in pads for sh in tr["shelters"])


def test_offpad_landing_adds_distance(lm_ok, lm_offpad):
    on = summary(p2(landing_model={"policy": "{cls}", "dir": lm_ok}))
    off = summary(p2(landing_model={"policy": "{cls}", "dir": lm_offpad}))
    assert on["offpad_landings"] == 0 and on["km_offpad_extra"] == 0
    assert off["offpad_landings"] > 0 and off["km_offpad_extra"] > 0
    assert off["km_total"] > on["km_total"]
    assert off["landing_miss_m_mean"] == pytest.approx(500.0) and on["landing_miss_m_mean"] == pytest.approx(math.sqrt(2))
    sig = summary(p2(landing_model={"policy": "{cls}", "dir": lm_ok, "sigma_scale": 100.0}))   # 141 m > 50 m pad
    assert sig["offpad_landings"] > 0


def test_lost_cargo_is_accounted(lm_failed, lm_ok):
    s = summary(p2(landing_model={"policy": "{cls}", "dir": lm_failed}))
    assert s["failed_landings"] > 0
    assert s["cargo_lost_kg"] == pytest.approx(s["landed_kg"])         # every landing failed, all cargo lost
    assert s["ready_kg"] == pytest.approx(s["bulk_kg"])                 # only surface flows remain to move
    rec = summary(p2(landing_model={"policy": "{cls}", "dir": lm_failed, "failure_policy": {"recover_h": 48}}))
    ok = summary(p2(landing_model={"policy": "{cls}", "dir": lm_ok}))
    assert rec["cargo_lost_kg"] == 0 and rec["failed_landings"] == s["failed_landings"]
    assert rec["delay_prio1_mean_h"] > ok["delay_prio1_mean_h"]         # recovery delays every item
    assert ok["prop_residual_kg_mean"] > 0


def test_driving_tables_drive_legs(driving):
    sc = p2(terrain="connecting_ridge", pad_standoff_km="1", autonomy_model=driving)
    s = summary(sc)
    assert s["interventions"] > 0 and s["intervention_h"] > 0
    assert s["intervention_h"] == pytest.approx(s["interventions"] * (5.0 + 300.0) / 3600.0)   # RTT 5 s + recovery
    dm = DrivingModel(driving, "1", __import__("lunarsim.entities", fromlist=["VEHICLE_CLASSES"]).VEHICLE_CLASSES)
    assert dm.rtt_bin(5.0) == "4" and dm.rtt_bin(7.1) == "8" and dm.rtt_bin(0.4) == "0"
    assert DrivingModel.light_bin(0.0, False) == "0" and DrivingModel.light_bin(0.0, True) == "night"


def test_trace_v2_from_a_run_validates(lm_ok, driving):
    sc = library()["P2-4-vehicles"].with_(horizon_h=2500.0, terrain="connecting_ridge", pad_standoff_km="1",
                                          landing_model={"policy": "{cls}", "dir": lm_ok},
                                          plume={"keepout_km": 1.0, "standdown_h": 2.0}, autonomy_model=driving)
    sim = Simulation(sc, dispatch.marketplace, seed=0, mech_kwargs={"trace": True})
    sim.run()
    tr = json.loads(json.dumps(sim.trace_export()))
    assert tr["version"] == 2 and validate_trace(tr) == []
    assert tr["terrain"] == "connecting_ridge" and len(tr["landings"]) == 5
    assert all({"t", "type", "pad", "xy_m", "miss_m", "ok"} <= set(L) for L in tr["landings"])
    assert all("interventions" in j and "energy_kwh" in j for j in tr["jobs"] if j["kind"] != "reposition")
    assert tr["cargo_columns"][-1] == "lost" and all(len(r) == 12 for r in tr["cargo"])
    broken = json.loads(json.dumps(tr))
    broken["landings"][0] = [1.0, "CLPS", "PAD_A"]                       # v1 row inside a v2 trace
    assert validate_trace(broken)


def test_committed_trace_v2_fixture():
    p = os.path.join(ROOT, "tests", "fixtures", "trace_v2_sample.json")
    with open(p, encoding="utf-8") as f:
        tr = json.load(f)
    assert tr["version"] == 2 and validate_trace(tr) == []
    assert len(tr["landings"]) >= 3 and tr["plume_windows"] and tr["shelters"]
    try:
        import jsonschema
    except ImportError:
        return
    jsonschema.Draft202012Validator(load_schema("trace-v2")).validate(tr)


def test_scenario_json_carries_phase3_fields(lm_ok):
    sc = p2(terrain="connecting_ridge", pad_standoff_km="2", landing_model={"policy": "classical", "sigma_scale": 2.0},
            plume={"keepout_km": 1.0, "standdown_h": 0.5, "shelter": "auto"}, autonomy_model="driving-v1")
    d = json.loads(json.dumps(scenario_to_dict(sc)))
    assert validate_scenario(d) == [] and scenario_from_dict(d) == sc
    bad = dict(d, plume={"keepout_km": 1.0})                              # standdown_h missing
    try:
        import jsonschema
        assert list(jsonschema.Draft202012Validator(load_schema("scenario-v1")).iter_errors(bad))
    except ImportError:
        pass


def test_cli_flags_build_the_scenario(tmp_path, lm_ok, capsys):
    from lunarsim.cli import main
    out = tmp_path / "r.csv"
    main(["run", "--scenario", "P2-default", "--seeds", "1", "--out", str(out), "--terrain", "connecting_ridge",
          "--pad-standoff", "2", "--landing-model", "{cls}", "--policy-dir", lm_ok, "--plume", "1,0.5",
          "--failure-policy", "recover:24"])
    import pandas as pd
    row = pd.read_csv(out).iloc[0]
    assert "plume_standdowns" in row and row["landing_miss_m_mean"] == pytest.approx(math.sqrt(2))
    with pytest.raises(SystemExit):
        main(["run", "--scenario", "P2-default", "--seeds", "1", "--plume", "1"])
    with pytest.raises(ValueError, match="pad_standoff_km"):
        summary(p2(terrain="connecting_ridge", pad_standoff_km="7"))
