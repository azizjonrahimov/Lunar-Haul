"""B-77: roads and rules of the road (tools/atc/roads.py, lunarsim/atc/roads.py)."""
import json, math, os, sys, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim import Simulation
from lunarsim.atc import p5 as P5, regimes as G
from lunarsim.atc import roads as RD

CORRIDOR = os.path.join(ROOT, "results", "ATC_roads_corridor.json")
PLUME = {"keepout_km": 1.0, "standdown_h": 0.75, "shelter": "auto"}


def make(roads=None, fleet=None, k=0.857, seed=2, horizon=None):
    sc = P5.build("3eq", k=k, team_lift_share=0.10).with_(plume=PLUME)
    if fleet is not None:
        sc = sc.with_(fleet=fleet)
    if horizon:
        sc = sc.with_(horizon_h=horizon)
    if roads is not None:
        sc = sc.with_(p5=dict(sc.p5, roads=roads))
    return Simulation(sc, G.mechanism("O_ORACLE"), seed=seed, mech_kwargs={"start_year": 2028, "trace": True})


def run(sim):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        return sim.run()


def test_corridor_finding_file():
    if not os.path.isfile(CORRIDOR):
        pytest.skip("roads not built")
    d = json.load(open(CORRIDOR, encoding="utf-8"))
    assert d["samples"] == 2421 and d["criterion"]["width_single_m"] == 10.0
    assert d["single_lane_km_at_20deg"] == 0.0 and d["by_slope_limit_deg"]["20"]["single_lane_share"] == 0.0
    sh = [d["by_slope_limit_deg"][k]["single_lane_share"] for k in ("20", "15", "12", "10", "8")]
    assert sh == sorted(sh) and "ASSUMED" in d["e43_choice"]


def test_single_lane_ranking_and_bays():
    n0, n15, n40 = (RD.single_lane_set(s) for s in (0.0, 0.15, 0.40))
    assert not n0.any() and n15.sum() == round(0.15 * len(n15))
    assert np.all(n40[n15])                                       # nested: the narrowest places first
    roads, _ = RD._load()
    assert not n40[roads["junctions"]].any()                      # sites and pads are junctions
    r05, _, _ = RD.build_segments(n15, 0.5)
    r2, _, _ = RD.build_segments(n15, 2.0)
    assert r05.max() > r2.max()                                   # more bays, more (shorter) segments


def test_single_vehicle_sees_no_added_delay_from_the_road_layer():
    fleet = [("A", "CARGO_FLEX", "supervised", "A")]
    off = make(None, fleet=fleet)
    on = make({"mode": "atc", "single_share": 0.40, "eva": {"per_week": 0}}, fleet=fleet)
    a, b = run(off), run(on)
    assert b["road_wait_h"] == b["road_apron_wait_h"] == b["road_hand_wait_h"] == 0.0 and b["road_traversals"] > 0
    assert off.trace == on.trace
    assert all(b[k] == v for k, v in a.items() if not (isinstance(v, float) and math.isnan(v)))


def _layer(mode, seed=2):
    sim = make({"mode": mode, "single_share": 0.15, "eva": {"per_week": 0}}, horizon=10.0, seed=seed)
    run(sim)
    return sim, sim.roads


def _leg_with_traversal(rl):
    for key, tr in rl.legs.items():
        a, b = key.split("->")
        if tr and "@" not in a and "@" not in b:
            return a, b, tr[0]
    raise AssertionError("no leg with a single-lane traversal")


def _job(sim, v, a, b, t0, t1):
    from lunarsim.engine import Job
    sim._last_segments = {v.id: [[a, b, t0, t1, 0.0]]}
    return Job([v], [], [b])


@pytest.mark.parametrize("mode", ["atc", "uncoordinated"])
def test_head_on_conflict(mode):
    sim, rl = _layer(mode)
    a, b, (res, f_in, f_out, d) = _leg_with_traversal(rl)
    v1 = next(v for v in sim.vehicles if v.owner == "A")
    v2 = next(v for v in sim.vehicles if v.owner == "B")
    rl.table = {}
    assert rl.apply(sim, _job(sim, v1, a, b, 100.0, 110.0), 100.0) == 0.0          # first one: free road
    seg1 = rl.table[res][0]
    # the other direction, reaching the same segment at the same moment: a conflict
    g_in = next(f for r, f, _, _ in rl.legs[f"{b}->{a}"] if r == res)
    t0r = seg1[0] - 10.0 * g_in
    extra = rl.apply(sim, _job(sim, v2, b, a, t0r, t0r + 10.0), t0r)
    if mode == "atc":
        assert rl.m["conflicts"] == 1 and extra > 0 and rl.m["hand_conflicts"] == 0
        t_in2 = rl.table[res][-1][0]
        assert t_in2 >= seg1[1] - 1e-9                                            # waits until the segment is free
    else:
        assert rl.m["hand_conflicts"] == 1 and extra >= rl.cfg["t_hand"] - 1e-9  # settled by hand from Earth
        assert rl.m["other_stop_h"] > 0
    # same owner: always known, a wait not a hand conflict
    rl.table, rl.m["hand_conflicts"], rl.m["conflicts"] = {}, 0, 0
    v3 = [v for v in sim.vehicles if v.owner == "A"][1]
    rl.apply(sim, _job(sim, v1, a, b, 200.0, 210.0), 200.0)
    t0r = rl.table[res][0][0] - 10.0 * g_in
    assert rl.apply(sim, _job(sim, v3, b, a, t0r, t0r + 10.0), t0r) > 0 and rl.m["hand_conflicts"] == 0
    # same direction may follow
    rl.table, rl.m["conflicts"] = {}, 0
    rl.apply(sim, _job(sim, v1, a, b, 300.0, 310.0), 300.0)
    if not any(rl.branched.get(r) for r, _, _, _ in rl.legs[f"{a}->{b}"]):    # branched segments are exclusive
        assert rl.apply(sim, _job(sim, v3, a, b, 300.0, 310.0), 300.0) == 0.0


def test_apron_slots_and_eva():
    sim, rl = _layer("atc")
    pad = sorted(rl.pads)[0]
    vs = sim.vehicles[:3]
    rl.table = {}
    for v in vs[:2]:
        sim._last_segments = {v.id: [[pad, pad, 50.0, 51.0, 0.0]]}
        from lunarsim.engine import Job
        assert rl.apply(sim, Job([v], [], [pad]), 50.0) == 0.0
    sim._last_segments = {vs[2].id: [[pad, pad, 50.0, 51.0, 0.0]]}
    from lunarsim.engine import Job
    assert rl.apply(sim, Job([vs[2]], [], [pad]), 50.0) == pytest.approx(1.0)       # third vehicle: waits a slot
    rl.eva = [(100.0, 106.0)]
    assert rl._eva_extra("DEPOT", "BASE", 99.0, 101.0) == pytest.approx(0.05)       # 50 m at 1 km/h
    assert rl._eva_extra("DEPOT", "BASE", 99.0, 107.0) == 0.0
