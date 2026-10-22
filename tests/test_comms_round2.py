"""Round 2 (B-48): outcome metrics (completion, censored urgent delay, bulk / landed kg), the periodic relay, the
intervention scale, and the round-2 cell sets."""
import json, math, os, sys
from types import SimpleNamespace
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim import Simulation
from lunarsim.comms import CommsModel
from experiments.phase4 import run_phase4 as R

H = 8760.0


def _model(**cfg):
    return CommsModel({"mode": "dte", **cfg}, "1", 0, H, ["PAD_A", "PAD_B"])


def _c(ready, done, prio=1, cls="consumables", kg=100.0):
    return SimpleNamespace(t_ready=ready, t_delivered=done, priority=prio, cls=cls, mass_kg=kg)


def test_censored_equals_uncensored_when_all_delivered():
    cargo = [_c(100.0 * i, 100.0 * i + w) for i, w in enumerate(range(1, 21))]
    m = _model().outcome_metrics(cargo)
    waits = np.arange(1, 21, dtype=float)
    assert m["prio1_completion_share"] == 1.0 and m["delay_prio1_p90_censored_is_bound"] == 0.0
    assert m["delay_prio1_p90_censored_h"] == pytest.approx(np.percentile(waits, 90))
    assert m["delay_prio1_mean_censored_h"] == pytest.approx(waits.mean())


def test_censoring_and_bound_flag():
    base = [_c(100.0 * i, 100.0 * i + w) for i, w in enumerate(range(1, 21))]
    # one item never delivered, ready early: censored wait H - 50 sits at the top, outside the p90's order statistics
    m = _model().outcome_metrics(base + [_c(50.0, None)])
    assert m["prio1_completion_share"] == pytest.approx(20 / 21)
    assert m["delay_prio1_p90_censored_is_bound"] == 0.0
    assert m["delay_prio1_p90_censored_h"] == pytest.approx(np.percentile(list(range(1, 21)) + [H - 50.0], 90))
    # ready near the end and not delivered: a short censored wait below the p90 -> the p90 is only a lower bound
    m = _model().outcome_metrics(base + [_c(H - 2.0, None)])
    assert m["delay_prio1_p90_censored_is_bound"] == 1.0
    # delivered after the year counts as censored at the year's end
    m = _model().outcome_metrics([_c(H - 10.0, H + 5.0)])
    assert m["prio1_completion_share"] == 0.0 and m["delay_prio1_p90_censored_h"] == pytest.approx(10.0)
    # completion < 90 %: always a bound
    m = _model().outcome_metrics(base[:5] + [_c(10.0 * i, None) for i in range(3)])
    assert m["prio1_completion_share"] < 0.9 and m["delay_prio1_p90_censored_is_bound"] == 1.0


def test_bulk_and_landed_split():
    cargo = [_c(1.0, 5.0, 3, "bulk", 1000.0), _c(2.0, None, 3, "bulk", 1000.0), _c(3.0, 9.0, 2, "equipment", 500.0),
             _c(4.0, 9.0, 2, "return", 50.0), _c(H + 1.0, None, 1, "consumables", 70.0)]       # ready after the year: out
    m = _model().outcome_metrics(cargo)
    assert m["completion_share_bulk"] == 0.5 and m["completion_share_landed"] == 1.0
    assert m["delivered_bulk_kg_in_horizon"] == 1000.0 and m["delivered_landed_kg_in_horizon"] == 500.0
    assert math.isnan(m["prio1_completion_share"])


def _run(sc, seed=0):
    fn, kw = R.MECHS[R.MECH]
    return Simulation(sc.with_(comms=dict(sc.comms, start_year=2028)), fn, seed=seed, mech_kwargs=dict(kw)).run()


def test_engine_never_linked_destination_and_always():
    """DTE: ISRU never sees Earth, so its bulk feedstock is never completed; Earth always in view: all completed and
    the censored urgent delay equals the engine's (no urgent item is pending at the year's end)."""
    _, dte = R.scenario("supervised_strict", "dte")
    r = _run(dte)
    assert r["completion_share_bulk"] < 0.7 and r["delivered_bulk_kg_in_horizon"] <= 300e3 + 1e-6
    assert r["delay_prio1_p90_censored_h"] >= r["delay_prio1_p90_h"]
    parts = r["delivered_bulk_kg_in_horizon"] + r["delivered_landed_kg_in_horizon"]
    assert parts <= r["delivered_kg_in_horizon"] + 1e-6           # the rest is return cargo
    _, alw = R.scenario("supervised_strict", "always")
    a = _run(alw)
    assert a["prio1_completion_share"] == 1.0 and a["delay_prio1_p90_censored_is_bound"] == 0.0
    assert a["delay_prio1_p90_censored_h"] == pytest.approx(a["delay_prio1_p90_h"], rel=1e-9)


def test_periodic_relay():
    m = CommsModel({"mode": "dte+relay", "relay": {"coverage": 0.25, "gap_model": "periodic", "period_h": 30.0}},
                   "1", 3, H, ["PAD_A", "PAD_B"])
    iv = m.relay.iv
    assert np.allclose(iv[:, 1] - iv[:, 0], 7.5) and np.allclose(np.diff(iv[:, 0]), 30.0)
    up = sum(min(e, H) - max(s, 0.0) for s, e in iv if e > 0 and s < H)
    assert up / H == pytest.approx(0.25, abs=0.005)
    with pytest.raises(ValueError):
        CommsModel({"mode": "dte+relay", "relay": {"coverage": 0.5, "gap_model": "lunar"}}, "1", 0, H, [])


def test_intervention_scale():
    _, sc = R.scenario("supervised_strategic", "dte+relay", 0.5)
    a = _run(sc)
    b = _run(sc.with_(comms=dict(sc.comms, intervention_scale=1.0)))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    fn, kw = R.MECHS[R.MECH]
    sim = Simulation(sc.with_(comms=dict(sc.comms, start_year=2028, intervention_scale=0.0)), fn, seed=0, mech_kwargs=dict(kw))
    sim.run()
    assert not [w for w in sim.comms.waits if w[4] == "intervention"]
    with pytest.raises(ValueError):
        _model(intervention_scale=-1.0)


def test_round2_cell_sets():
    key = lambda cs: {R.e21_key(t, m) for t, _, m, *_ in cs}
    assert R.sfx("r1") == "" and R.sfx("r2") == "_r2"
    a1, a2 = R.e21a_cells("r1"), R.e21a_cells("r2")
    assert len(a1) == 60 and len(a2) == 78 and key(a1) <= key(a2)
    b1, b2 = R.e21b_cells(0.5, "r1"), R.e21b_cells(0.5, "r2")
    assert len(b1) == 32 and len(b2) == 56 and key(b1) <= key(b2)
    e = R.e21e_cells()
    assert len(e) == 32 and len(key(e)) == 32 and all(t["stage"] == "E" and t["sensitivity"] for t, *_ in e)
    loc = [sc for t, sc, *_ in e if t["sensitivity"] == "isru_local_feedstock"]
    assert loc and all(not any(b.dest == "ISRU" for b in sc.bulk_flows) for sc in loc)
