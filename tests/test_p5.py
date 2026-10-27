"""B-71: real vehicle classes, hoppers, owners and the "p5" scenario family (lunarsim/atc/vehicles.py, p5.py)."""
import glob, json, math, os, sys, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pytest

from lunarsim import Simulation, catalog, dispatch
from lunarsim.atc import p5 as P5, vehicles as V
from lunarsim.config import load_scenario, scenario_from_dict
from lunarsim.entities import VEHICLE_CLASSES
from lunarsim.formats import validate_scenario

P5_DIR = os.path.join(ROOT, "data", "scenarios", "p5")


def run(sc, mech="marketplace", seed=1):
    sim = Simulation(sc, getattr(dispatch, mech), seed=seed)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return sim, sim.run()


def test_classes_load_and_validate():
    assert V.validate() == []
    assert set(V.P5_CLASSES) == {"LTV1_CLV1", "LTV1_PEGASUS", "CARGO_FLEX", "CARGO_EAGLE", "MAPP_SMALL",
                                 "HOPPER_MOONFALL", "HOPPER_MICRONOVA"}
    clv = V.P5_CLASSES["LTV1_CLV1"]
    assert clv.capacity_kg == 80 and clv.km_per_day == 6
    assert clv.battery_wh == pytest.approx(10 * clv.energy_wh_per_km, abs=1)        # 10 km per charge binds
    hop = V.P5_CLASSES["HOPPER_MOONFALL"]
    assert hop.flies and hop.km_budget == 50 and hop.active_h == 14 * 24
    assert V.build("CARGO_EAGLE", {"capacity_kg": 1600}).capacity_kg == 1600        # sweeps by name


def test_old_classes_and_catalogue_untouched():
    assert list(VEHICLE_CLASSES) == ["LTV", "HAUL", "MICRO"]
    assert catalog.engine_mismatches() == []
    assert catalog.validate(catalog.load()) == []


def test_p5_files_validate_and_cover_the_family():
    files = sorted(glob.glob(os.path.join(P5_DIR, "*.json")))
    assert len(files) == 37                                    # 4 owner mixes x 3 loads x 3 team shares + lot 200
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        assert validate_scenario(d) == [], f
        assert d["p5"]["load"]["k"] > 0
    sc = load_scenario(os.path.join(P5_DIR, "p5-3uneq-L30-T10.json"))
    assert sorted(set(sc.cargo_owners)) == ["A", "B", "C"]
    assert [sc.cargo_owners.count(o) for o in "ABC"] == [30, 21, 9]                 # 50 / 35 / 15


@pytest.mark.parametrize("mech", ["marketplace", "inhouse"])
def test_p5_year_runs_and_conserves_mass(mech):
    sc = load_scenario(os.path.join(P5_DIR, "p5-3eq-L10-T25.json"))
    sim, s = run(sc, mech, seed=2)
    assert s["delivered_kg"] > 0 and s["p5_reach_kg"] == 2800 and s["p5_single_max_kg"] == 2000
    m = sim.metrics
    assert m.ready_kg == pytest.approx(m.delivered_kg + m.stranded_kg + m.backlog_kg, rel=1e-12)
    assert all(c.mass_kg <= sim.p5.reach for c in sim.all_cargo)
    assert all(c.mass_kg > sim.p5.reach for c in sim.p5.heavy)
    assert not any(c in sim.all_cargo or c.t_delivered is not None for c in sim.p5.heavy)  # never offered
    assert s["p5_heavy_t"] == pytest.approx(sum(c.mass_kg for c in sim.p5.heavy) / 1000)
    if mech == "inhouse":
        assert s["team_lifts"] == 0 and s["p5_team_items_delivered"] == 0             # owners alone: no team lifts


def test_team_share_redraw_keeps_every_other_draw():
    sc = P5.build("3eq", k=0.857, team_lift_share=0.0)
    a, _ = run(sc, seed=4)
    b, _ = run(sc.with_(p5=dict(sc.p5, team_lift_share=0.25)), seed=4)
    ka = [(c.id, c.owner, c.origin, c.dest, c.priority, c.cls, round(c.t_ready, 9)) for c in a.all_cargo if c.cls != "return"]
    kb = [(c.id, c.owner, c.origin, c.dest, c.priority, c.cls, round(c.t_ready, 9)) for c in b.all_cargo if c.cls != "return"]
    assert ka == kb
    assert [c.id for c in a.p5.heavy] == [c.id for c in b.p5.heavy]
    la = [c for c in a.all_cargo if c.cls not in ("bulk", "return")]     # ids can repeat across bulk and lander
    lb = [c for c in b.all_cargo if c.cls not in ("bulk", "return")]     # items (engine), so pair by position
    moved = [cb for ca, cb in zip(la, lb) if cb.mass_kg != ca.mass_kg]
    assert len(moved) == b.p5.redrawn > 0
    assert all(2000 < c.mass_kg <= 2800 for c in moved)


def test_same_owner_pairs_and_rules():
    sim, s = run(P5.build("3eq", k=0.5, team_lift_share=0.25), seed=1)
    assert sim.p5.same_owner_pair_max == {"A": 2080.0, "B": 880.0}          # FLEX + CLV-1; Eagle + Pegasus
    kr, _ = run(P5.build("3eq", k=0.5, team_lift_share=0.25, team_rule="krawciw"), seed=1)
    assert kr.p5.pair_max == pytest.approx(0.3 * (1600 + 1500)) and kr.p5.reach == 2000   # no pair beats FLEX alone
    assert kr.p5.redrawn == 0


def test_hopper_flies_straight_and_respects_budget_and_window():
    sc = P5.build("3eq", k=0.857)
    sim = Simulation(sc, dispatch.marketplace, seed=1)
    hop = next(v for v in sim.vehicles if v.cls.name == "HOPPER_MOONFALL")
    a, b = "BASE", "PSR"
    km = sim._fly_km(a, b)
    assert sim.travel_h(hop, a, b, True, False, 0.0) == pytest.approx(km / 20.0)
    assert sim._p3_leg(hop, a, b, True, False, 0.0, False) == (pytest.approx(km / 20.0), 0.0, km, 0)
    from lunarsim.engine import Job
    assert sim.p5.job_ok(Job([hop], [], [b]), 0.0, 1.0, 49.0)
    assert not sim.p5.job_ok(Job([hop], [], [b]), 0.0, 1.0, 51.0)                 # beyond 50 km
    assert not sim.p5.job_ok(Job([hop], [], [b]), 330.0, 10.0, 1.0)              # ends after 14 days
    sim.p5.note_km(hop, 50.0, 5.0)
    assert not hop.alive and sim.p5.retired_at[hop.id] == 5.0
    _, s = run(sc, seed=1)
    assert s["p5_hoppers_retired"] == 2 and s["p5_hopper_km"] <= 2 * 50 + 1e-9
    r = Simulation(sc.with_(p5=dict(sc.p5, hopper_refuel=True)), dispatch.marketplace, seed=1)
    h2 = next(v for v in r.vehicles if v.cls.name == "HOPPER_MOONFALL")
    r.p5.note_km(h2, 50.0, 5.0)
    assert h2.alive and r.p5.km_left(h2, 5.0) == 0 and r.p5.km_left(h2, 5.0 + 29.53 * 24) == 50


def test_daily_km_budget():
    sim = Simulation(P5.build("3eq", k=0.857), dispatch.marketplace, seed=1)
    clv = next(v for v in sim.vehicles if v.cls.name == "LTV1_CLV1")
    from lunarsim.engine import Job
    j = Job([clv], [], ["BASE"])
    assert sim.p5.day_cap_delay(j, 9.0, 0.0) == pytest.approx(12.0)              # 3 km over 6 km/day
    assert sim.p5.day_cap_delay(j, 6.0, 0.0) == pytest.approx(24.0)              # bucket empty
    assert sim.p5.day_cap_delay(j, 3.0, 48.0) == 0.0                             # refilled after a day


def test_old_scenarios_ignore_p5():
    from lunarsim.config import library, scenario_to_dict
    d = scenario_to_dict(library()["P2-default"])
    assert "p5" not in d
    assert scenario_from_dict(d).p5 is None
