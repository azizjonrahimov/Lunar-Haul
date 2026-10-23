"""Opt-in Earth-link rules in the engine (B-41, Scenario.comms): identity when off, each rule on a hand-made series."""
import copy, gzip, hashlib, json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim import comms as C, dispatch
from lunarsim.config import library, scenario_to_dict, scenario_from_dict
from lunarsim.engine import Simulation, run
from lunarsim.entities import Vehicle, VEHICLE_CLASSES
from lunarsim.formats import validate_trace, load_schema

SITES = ["PAD_A@1", "PAD_B@1", "DEPOT", "BASE", "POWER", "CONSTR", "ISRU", "SCI_1", "PSR"]
N = 4 * 8760 * 6                      # 10-min epochs covering four years (the reader wraps past the end)
REAL = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1.json")


def _windows(spec_h, n=N, step_h=1 / 6):
    """[start_h, end_h) pairs -> delta code at 10-min epochs."""
    m = np.zeros(n, dtype=bool)
    for a, b in spec_h:
        m[int(round(a / step_h)):int(round(b / step_h))] = True
    return C.encode_windows(C.runs(m))


def write_series(tmp, leg_windows=None, point_windows=None, default="always", sample_windows=None):
    """A hand-made earth_link-v1.json (+ samples) for the default world's sites and every directed leg."""
    always = _windows([(0, N / 6)])
    never = []
    dflt = always if default == "always" else never
    entry = lambda w: {"windows": {m: {c: w for c in C.CRITERIA} for m in C.MODES},
                       "summary": {m: {c: C.summarize(C.decode_windows(w), N, 1 / 6) for c in C.CRITERIA} for m in C.MODES}}
    points = {s: entry((point_windows or {}).get(s, dflt)) for s in SITES}
    legs = {f"{a}->{b}": entry((leg_windows or {}).get(f"{a}->{b}", dflt)) for a in SITES for b in SITES if a != b}
    samples, series, slegs = [], [], {}
    for name in legs:                               # three samples per leg, hourly series
        ids = []
        for k in range(3):
            w = (sample_windows or {}).get(name, legs[name]["windows"]["dte"]["any_part"])
            wh = C.encode_windows(C.runs(C.windows_to_mask(C.decode_windows(w), N)[: N - N % 6].reshape(-1, 6).all(axis=1)))
            series.append(wh)
            samples.append({"xy_m": [0, 0], "id": None, "mast_los": False, "w": [len(series) - 1] * 3})
            ids.append(len(samples) - 1)
        slegs[name] = ids
    sdoc = {"format": C.EARTH_LINK_SAMPLES_FORMAT, "version": 1, "terrain": "test",
            "time": {"start_utc": "2028-01-01 00:00", "step_min": 60, "n": N // 6}, "criteria": list(C.CRITERIA),
            "samples": samples, "series": series, "legs": slegs}
    with open(os.path.join(tmp, "s.json.gz"), "wb") as f:
        f.write(gzip.compress(json.dumps(sdoc).encode(), mtime=0))
    doc = {"format": C.EARTH_LINK_FORMAT, "version": 1, "time": {"start_utc": "2028-01-01 00:00", "step_min": 10, "n": N},
           "points": points, "legs": legs, "mast": None, "samples_file": {"file": "s.json.gz"}}
    path = os.path.join(tmp, "link.json")
    with open(path, "w") as f:
        json.dump(doc, f)
    return path


def small(**kw):
    sc = library()["P2-default"].with_(horizon_h=2000.0, other_duty_share=0.0, failures=False)
    return sc.with_(**kw)


from lunarsim.comms import SUMMARY_PREFIXES as V2_SKIP     # every column the comms model adds


def v2_part(r):
    return {k: v for k, v in r.items() if not k.startswith(V2_SKIP)}


def same(a, b):
    assert set(a) == set(b)
    for k in a:
        x, y = a[k], b[k]
        assert (isinstance(x, float) and isinstance(y, float) and math.isnan(x) and math.isnan(y)) or x == y, k


# ------------------------------------------------------------------------------------------------ identity
@pytest.mark.parametrize("mech", [dispatch.marketplace, dispatch.pooled_greedy, dispatch.central_assign])
def test_off_always_and_full_relay_are_identical(mech):
    base = run(small(), mech, seed=1)
    for comms in ({"mode": "always"}, {"mode": "dte+relay", "relay": {"coverage": 1.0}, "link_series": REAL}):
        if comms["mode"] != "always" and not os.path.isfile(REAL):
            continue
        r = run(small(comms=comms), mech, seed=1)
        same(v2_part(r), base)
        assert r["blackout_wait_vehicle_h"] == 0 and r["blackout_jobs_refused"] == 0


def test_always_reproduces_the_baseline_md5(tmp_path):
    from lunarsim.cli import main
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    from test_phase3_engine import v2_canonical_md5, BASELINE_V2_CANONICAL_MD5
    import pandas as pd
    out = tmp_path / "c.csv"
    main(["compare", "--scenario", "P2-default", "--seeds", "3", "--out", str(out), "--comms", "always"])
    df = pd.read_csv(out, float_precision="round_trip")
    df = df.drop(columns=[c for c in df.columns if c.startswith(V2_SKIP) or c in ("delivered_nonbulk_kg", "cost_per_landed_kg_usd")])
    assert hashlib.md5(df.to_csv(index=False, lineterminator=chr(10)).encode()).hexdigest() == BASELINE_V2_CANONICAL_MD5


# ------------------------------------------------------------------------------------------------ rules (unit)
def model(tmp, policy="strict", **series_kw):
    path = write_series(str(tmp), **series_kw)
    return C.CommsModel({"mode": "dte", "link_series": path, "supervised_policy": policy}, "1", 7, 2000.0,
                        ["PAD_A", "PAD_B"])


def veh(autonomy):
    return Vehicle(0, "NASA", VEHICLE_CLASSES["LTV"], "DEPOT", {"A"}, autonomy)


def test_teleop_waits_at_start_and_parks_midway(tmp_path):
    cm = model(tmp_path, leg_windows={"DEPOT->BASE": _windows([(10, 12), (30, 100)])})
    segs = [["DEPOT", "BASE", 5.0, 9.0, 0.0], ["BASE", "BASE", 9.0, 10.0, 0.0]]
    out, waits = cm._apply(veh("teleop"), copy.deepcopy(segs), None, True)
    # parks at DEPOT 5 -> 10, drives 10 -> 12 (2 of 4 h), parks 12 -> 30, drives 30 -> 32; then unloads 32 -> 33
    assert out[0] == ["DEPOT", "DEPOT", 5.0, 10.0, 0.0]
    assert out[1][:4] == ["DEPOT", "BASE", 10.0, pytest.approx(32.0)]
    assert out[2][2:4] == [pytest.approx(32.0), pytest.approx(33.0)]
    assert [(w[4], round(w[1], 3), round(w[2], 3)) for w in waits] == [("start", 5.0, 10.0), ("midway", 12.0, 30.0)]
    strict, _ = cm._apply(veh("supervised"), copy.deepcopy(segs), None, True)
    assert strict == out                                            # supervised-strict follows the teleop rule
    auto, w_auto = cm._apply(veh("autonomous"), copy.deepcopy(segs), None, True)
    assert auto == segs and w_auto == []                            # autonomous is unaffected


def test_never_linked_leg_is_infeasible(tmp_path):
    cm = model(tmp_path, leg_windows={"DEPOT->ISRU": []})
    out, _ = cm._apply(veh("teleop"), [["DEPOT", "ISRU", 1.0, 2.0, 0.0]], None, True)
    assert out is None


def test_strategic_interventions_wait_at_their_sample(tmp_path):
    cm = model(tmp_path, policy="strategic", leg_windows={"DEPOT->BASE": []},     # the leg itself: never linked
               sample_windows={"DEPOT->BASE": _windows([(100, N / 6)])})          # its samples: from hour 100
    segs = [["DEPOT", "BASE", 10.0, 14.0, 0.0], ["BASE", "BASE", 14.0, 15.0, 0.0]]
    plan, w = cm._apply(veh("supervised"), copy.deepcopy(segs), [2, 0], False)
    assert plan == segs and w == []                                 # planning foresees nothing
    u = np.sort(np.random.default_rng([7, 41, 1]).random(2))
    out, waits = cm._apply(veh("supervised"), copy.deepcopy(segs), [2, 0], True)
    t_first = 10.0 + u[0] * 4.0                                     # first intervention waits until hour 100,
    assert waits[0][4] == "intervention" and waits[0][1] == pytest.approx(t_first)   # the second is then linked
    assert len(waits) == 1 and out[0][3] == pytest.approx(14.0 + (100.0 - t_first))
    assert out[1][2] == pytest.approx(out[0][3])
    assert cm._apply(veh("teleop"), copy.deepcopy(segs), [2, 0], True)[0] is None   # teleop needs the whole leg


def test_operator_demand_counts_only_while_linked(tmp_path):
    path = write_series(str(tmp_path), leg_windows={"DEPOT->BASE": _windows([(10, 12), (30, 100)])})
    sc = small(fleet=[("NASA", "LTV", "teleop", "A")], comms={"mode": "dte", "link_series": path})
    sim = Simulation(sc, dispatch.marketplace, seed=0)
    v = sim.vehicles[0]
    from lunarsim.engine import Job
    sim._last_segments = {v.id: [["DEPOT", "BASE", 5.0, 9.0, 0.0]]}
    out, waits = sim.comms._apply(v, sim._last_segments[v.id], None, True)
    sim._last_segments[v.id] = out
    sim.comms._last = {v.id: {"waits": waits}}
    dh = sim.comms.commit(sim, Job([v], [], ["BASE"]), 5.0, 32.0)
    assert dh == pytest.approx(4.0)                                 # 2 h + 2 h of linked driving, demand 1
    assert sim.comms.demand_at(7.0) == 0.0 and sim.comms.demand_at(11.0) == 1.0
    assert sim.comms.demand_at(20.0) == 0.0 and sim.comms.demand_at(31.0) == 1.0
    assert sim.comms.wait_h["teleop"] == pytest.approx(5.0 + 18.0)
    assert sim.comms.hour_demand.max() == pytest.approx(1.0)


def test_relay_fills_blackouts_with_the_given_availability(tmp_path):
    path = write_series(str(tmp_path), default="never")
    cm = C.CommsModel({"mode": "dte+relay", "link_series": path, "relay": {"coverage": 0.8, "mean_gap_h": 7.67}},
                      "1", 3, 20000.0, ["PAD_A", "PAD_B"])
    iv = cm.relay.iv
    up = np.clip(iv[:, 1], 0, 20000) - np.clip(iv[:, 0], 0, 20000)
    assert up.sum() / 20000 == pytest.approx(0.8, abs=0.03)
    gaps = iv[1:, 0] - iv[:-1, 1]
    assert gaps.mean() == pytest.approx(7.67, rel=0.15)
    s = cm.series("DEPOT", "BASE")                                  # DTE never: the link is the relay alone
    t_up = float(iv[0, 0]) + 0.01
    assert s.next_change(t_up)[0] is True


# ------------------------------------------------------------------------------------------------ engine level
def test_half_linked_series_delays_teleop_and_logs(tmp_path):
    w = _windows([(k * 500, k * 500 + 250) for k in range(80)])     # every leg and site linked half the time
    path = write_series(str(tmp_path), leg_windows={f"{a}->{b}": w for a in SITES for b in SITES if a != b},
                        point_windows={s: w for s in SITES})
    fleet = [("NASA", "LTV", "teleop", "A"), ("NASA", "LTV", "teleop", "A")]
    base = run(small(fleet=fleet), dispatch.marketplace, seed=2)
    r = run(small(fleet=fleet, comms={"mode": "dte", "link_series": path}), dispatch.marketplace, seed=2)
    assert r["blackout_wait_teleop_h"] > 0 and r["blackout_jobs_delayed"] > 0
    assert r["blackout_wait_supervised_h"] == 0 and r["blackout_jobs_refused"] == 0
    assert r["delay_mean_h"] > base["delay_mean_h"]
    assert r["linked_share_by_leg_mean"] == pytest.approx(0.5, abs=0.02)
    assert r["operator_hours"] < base["operator_hours"] * 1.5


def test_never_linked_destinations_are_not_served_by_link_needing_fleets(tmp_path):
    never_isru = {f"{a}->ISRU": [] for a in SITES if a != "ISRU"}
    path = write_series(str(tmp_path), leg_windows=never_isru)
    fleet = [("NASA", "LTV", "teleop", "A")]
    sim = Simulation(small(fleet=fleet, comms={"mode": "dte", "link_series": path}), dispatch.marketplace, seed=0)
    sim.run()
    assert all(c.t_delivered is None for c in sim.all_cargo if c.dest == "ISRU")
    assert any(c.t_delivered is not None for c in sim.all_cargo if c.dest != "ISRU")
    sim2 = Simulation(small(fleet=fleet + [("NASA", "LTV", "autonomous", "A")],
                            comms={"mode": "dte", "link_series": path}), dispatch.marketplace, seed=0)
    sim2.run()
    assert any(c.t_delivered is not None for c in sim2.all_cargo if c.dest == "ISRU")   # the autonomous rover can


def test_trace_v2_records_the_waits(tmp_path):
    w = _windows([(k * 400, k * 400 + 300) for k in range(100)])
    path = write_series(str(tmp_path), leg_windows={f"{a}->{b}": w for a in SITES for b in SITES if a != b})
    sc = small(fleet=[("NASA", "LTV", "teleop", "A")], terrain="connecting_ridge",
               comms={"mode": "dte", "link_series": path})
    sim = Simulation(sc, dispatch.marketplace, seed=0, mech_kwargs={"trace": True})
    sim.run()
    tr = json.loads(json.dumps(sim.trace_export()))
    assert tr["version"] == 2 and validate_trace(tr) == []
    assert tr["comms"]["mode"] == "dte" and tr["comms_waits"]
    assert all(len(x) == 5 and x[4] in ("start", "midway", "intervention") for x in tr["comms_waits"])
    plain = Simulation(sc.with_(comms=None), dispatch.marketplace, seed=0, mech_kwargs={"trace": True})
    plain.run()
    assert "comms" not in plain.trace_export()


# ------------------------------------------------------------------------------------------------ configuration
def test_config_validation_and_scenario_round_trip(tmp_path):
    path = write_series(str(tmp_path))
    with pytest.raises(ValueError, match="unknown comms keys"):
        Simulation(small(comms={"mode": "dte", "colour": 1}), dispatch.marketplace, seed=0)
    with pytest.raises(ValueError, match="mode"):
        Simulation(small(comms={"mode": "laser"}), dispatch.marketplace, seed=0)
    with pytest.raises(ValueError, match="start_year"):
        Simulation(small(comms={"mode": "dte", "start_year": 2035, "link_series": path}), dispatch.marketplace, seed=0)
    with pytest.raises(ValueError, match="mast"):
        Simulation(small(comms={"mode": "dte", "mast": {"site": "BASE", "height_m": 10}, "link_series": path}),
                   dispatch.marketplace, seed=0)
    assert C.year_start_h(2031) == 24 * 1096
    sc = small(comms={"mode": "dte+relay", "relay": {"coverage": 0.5}, "start_year": 2030})
    d = scenario_to_dict(sc)
    assert d["comms"]["relay"]["coverage"] == 0.5 and "comms" not in scenario_to_dict(small())
    assert scenario_from_dict(d).comms == sc.comms
    full = load_schema("scenario-v1")["$defs"]["full"]["properties"]
    assert "comms" in full


@pytest.mark.skipif(not os.path.isfile(REAL), reason="earth_link-v1.json not generated")
def test_real_series_start_year_and_mast():
    r28 = run(small(comms={"mode": "dte", "start_year": 2028}), dispatch.marketplace, seed=0)
    r31 = run(small(comms={"mode": "dte", "start_year": 2031}), dispatch.marketplace, seed=0)
    assert r28["delivered_kg"] != r31["delivered_kg"] or r28["blackout_wait_vehicle_h"] != r31["blackout_wait_vehicle_h"]
    m = run(small(comms={"mode": "dte", "mast": {"site": "BASE", "height_m": 10, "range_km": 10}}), dispatch.marketplace, seed=0)
    assert m["blackout_wait_vehicle_h"] <= r28["blackout_wait_vehicle_h"] + 1e-9 or m["delivered_kg"] >= r28["delivered_kg"]


def test_strategic_avoid_looks_ahead_and_defers(tmp_path):
    """strategic+avoid: a route whose sample would make an intervention wait > defer_wait_h at passing time is not
    taken now (a wake-up is set at the link-up); a never-linked sample means never; plain strategic takes both."""
    path = write_series(str(tmp_path), leg_windows={"DEPOT->BASE": [], "DEPOT->ISRU": []},
                        sample_windows={"DEPOT->BASE": _windows([(100, N / 6)]), "DEPOT->ISRU": []})
    sc = small(fleet=[("NASA", "LTV", "supervised", "A")],
               comms={"mode": "dte", "link_series": path, "supervised_policy": "strategic+avoid"})
    sim = Simulation(sc, dispatch.marketplace, seed=0)
    cm = sim.comms
    assert cm.restricted("supervised") and not cm.needs_link("supervised")
    assert cm.route_worst_wait([["DEPOT", "BASE", 10.0, 14.0, 0.0]]) == pytest.approx(90.0)   # first sample at t = 10
    assert cm.route_worst_wait([["DEPOT", "BASE", 120.0, 124.0, 0.0]]) == 0.0
    assert cm.route_worst_wait([["DEPOT", "ISRU", 120.0, 124.0, 0.0]]) == math.inf
    assert not cm.could_serve("supervised", "DEPOT", "ISRU") and cm.could_serve("supervised", "DEPOT", "BASE")
    assert math.isinf(cm.leg_worst_expected_wait("DEPOT", "ISRU"))
    cm2 = C.CommsModel({"mode": "dte", "link_series": path, "supervised_policy": "strategic"}, "1", 0, 2000.0, ["PAD_A", "PAD_B"])
    assert not cm2.restricted("supervised")


def test_strategic_avoid_engine_run_waits_less_than_strategic():
    if not os.path.isfile(REAL):
        pytest.skip("earth_link-v1.json not generated")
    sup = [(o, c, "supervised", s) for (o, c, _, s) in library()["P2-default"].fleet]
    sc = small(fleet=sup, terrain="connecting_ridge", pad_standoff_km="1", autonomy_model="driving-v1")
    plain = run(sc.with_(comms={"mode": "dte", "supervised_policy": "strategic"}), dispatch.marketplace, seed=1)
    avoid = run(sc.with_(comms={"mode": "dte", "supervised_policy": "strategic+avoid"}), dispatch.marketplace, seed=1)
    assert avoid["blackout_wait_supervised_h"] < plain["blackout_wait_supervised_h"]
    assert "blackout_jobs_avoided" in avoid


# ------------------------------------------------------------------------------------------------ B-57 bounded rule
def _bound_sim(tmp_path, **comms):
    path = write_series(str(tmp_path), leg_windows={"DEPOT->BASE": [], "DEPOT->ISRU": []},
                        sample_windows={"DEPOT->BASE": _windows([(100, N / 6)]), "DEPOT->ISRU": []})
    sc = small(fleet=[("NASA", "LTV", "supervised", "A")], comms={"mode": "dte", "link_series": path, **comms})
    return Simulation(sc, dispatch.marketplace, seed=0).comms


def test_strategic_bound_limits_and_never_linked_handling(tmp_path):
    """bound 0 refuses what is not linked at the pass and every never-linked route (look-ahead-like); a bound of 90 h
    takes DEPOT->BASE at t = 10 (first sample waits 90 h) and a bound below that defers it; bound null = strategic;
    bound_never 'strategic' leaves never-linked samples out of the check and keeps their routes servable."""
    seg = lambda a, b, t: [[a, b, t, t + 4.0, 0.0]]
    for bound, base_ok in ((0.0, False), (89.0, False), (91.0, True)):
        cm = _bound_sim(tmp_path, supervised_policy="strategic+bound", bound_h=bound)
        assert cm.avoids("supervised") and cm.restricted("supervised")
        assert bool(cm.route_worst_wait(seg("DEPOT", "BASE", 10.0)) <= cm._look_limit()) == base_ok
        assert cm.route_worst_wait(seg("DEPOT", "ISRU", 120.0)) == math.inf
        assert not cm.could_serve("supervised", "DEPOT", "ISRU")
    look = _bound_sim(tmp_path, supervised_policy="strategic+avoid")
    b24 = _bound_sim(tmp_path, supervised_policy="strategic+bound", bound_h=24.0)
    for s in (seg("DEPOT", "BASE", 10.0), seg("DEPOT", "BASE", 120.0), seg("DEPOT", "ISRU", 120.0)):
        assert b24.route_worst_wait(s) == look.route_worst_wait(s) and b24._look_limit() == look.defer_wait_h
    inf = _bound_sim(tmp_path, supervised_policy="strategic+bound", bound_h=None)
    assert not inf.avoids("supervised") and not inf.restricted("supervised") and inf.could_serve("supervised", "DEPOT", "ISRU")
    sk = _bound_sim(tmp_path, supervised_policy="strategic+bound", bound_h=24.0, bound_never="strategic")
    assert sk.route_worst_wait(seg("DEPOT", "ISRU", 120.0)) == 0.0                     # never-linked samples skipped
    assert sk.route_worst_wait(seg("DEPOT", "BASE", 10.0)) == pytest.approx(90.0)       # finite forecasts still count
    assert sk.could_serve("supervised", "DEPOT", "ISRU")
    with pytest.raises(ValueError):
        _bound_sim(tmp_path, supervised_policy="strategic", bound_h=24.0)
    with pytest.raises(ValueError):
        _bound_sim(tmp_path, supervised_policy="strategic+bound", bound_never="maybe")
    with pytest.raises(ValueError):
        _bound_sim(tmp_path, supervised_policy="strict", never_linked="strand")


def test_never_linked_redraw_or_strand(tmp_path):
    """An intervention drawn on a never-linked sample: 'redraw' (default) makes the job impossible (refused, tried
    again later); 'strand' keeps the rover there until the end of the year."""
    segs = [["DEPOT", "ISRU", 10.0, 14.0, 0.0]]
    redraw = _bound_sim(tmp_path, supervised_policy="strategic")
    assert redraw._apply(veh("supervised"), copy.deepcopy(segs), [1], True)[0] is None
    strand = _bound_sim(tmp_path, supervised_policy="strategic", never_linked="strand")
    out, waits = strand._apply(veh("supervised"), copy.deepcopy(segs), [1], True)
    assert out is not None and len(waits) == 1 and waits[0][2] == pytest.approx(strand.horizon_h + 1.0)
    assert out[0][3] > strand.horizon_h and strand.never_strandings == 1
    assert "blackout_strandings_never_linked" in strand.summary(None) and "blackout_strandings_never_linked" not in redraw.summary(None)
