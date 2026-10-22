"""Strict operator capacity in the linked modes (B-45, comms.operators_strict)."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim import Simulation
from lunarsim.comms import CommsModel, _Intervals
from experiments.phase4 import run_phase4 as R


def _model(**cfg):
    return CommsModel({"mode": "dte", **cfg}, "1", 0, 8760.0, ["PAD_A", "PAD_B"])


def test_op_series_from_bookings():
    m = _model(operators_strict=True)
    m.op_segs = [(10.0, 20.0, 1.0), (15.0, 30.0, 1.0), (40.0, 50.0, 0.5)]
    s = m._op_series(2.0, 1.0, [(25.0, 35.0, 1.0)], 0.0)      # room for 1.0 while booked <= 1.0
    assert s.next_change(5.0)[0] and not s.next_change(16.0)[0] and not s.next_change(27.0)[0]
    assert s.next_change(32.0)[0] and s.next_change(45.0)[0]
    up, dt = s.next_change(16.0)
    assert dt == pytest.approx(4.0)                            # two bookings 15-20 and 25-30 (one with the extra)
    assert s.next_change(22.0)[0] and s.next_change(22.0)[1] == pytest.approx(3.0)
    assert m._op_series(2.0, 0.5, [], 0.0).next_change(16.0)[0] is False
    assert m._op_series(3.0, 1.0, [], 0.0).next_change(16.0)[0] is True


def test_linked_parts_skip_waits():
    m = _model(operators_strict=True)
    m.series = lambda a, b=None: _Intervals(np.array([[0.0, 1e9]]))          # always linked
    segs = [["A", "A", 0.0, 2.0, 0], ["A", "B", 2.0, 10.0, 0]]
    waits = [[0, 0.0, 2.0, "A", "start"], [0, 4.0, 5.0, "A->B", "operator"]]
    assert m._linked_parts(segs, waits, 1.0) == [(2.0, 4.0, 1.0), (5.0, 10.0, 1.0)]


def test_split_op_waits():
    m = _model(operators_strict=True)
    m.series = lambda a, b=None: _Intervals(np.array([[3.0, 1e9]]))          # link comes up at 3 h
    out = m._split_op_waits([[0, 1.0, 6.0, "A->B", "midway"], [0, 7.0, 8.0, "A->B", "intervention"]])
    assert [w[4] for w in out] == ["midway", "operator", "intervention"]
    assert out[0][1:3] == [1.0, 3.0] and out[1][1:3] == [3.0, 6.0]


def _run(sc, seed=0):
    fn, kw = R.MECHS[R.MECH]
    sim = Simulation(sc.with_(comms=dict(sc.comms, start_year=2028)), fn, seed=seed, mech_kwargs=dict(kw))
    return sim.run()


def test_off_is_unchanged():
    _, sc = R.scenario("default", "dte+relay", 0.5)
    a = _run(sc)
    b = _run(sc.with_(comms=dict(sc.comms, operators_strict=False)))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True) and "operator_wait_vehicle_h" not in a


def test_strict_caps_the_peak():
    """An all-teleop fleet with one operator and a half-time relay: without the rule the linked demand peaks above
    one operator; with it the peak is <= 1 and the vehicles wait for the operator instead."""
    _, sc = R.scenario("teleop_4s", "dte+relay", 0.5)
    sc = sc.with_(n_operators=1)
    lenient = _run(sc)
    strict = _run(sc.with_(comms=dict(sc.comms, operators_strict=True)))
    assert lenient["operator_peak_demand"] > 1.0 + 1e-6
    assert strict["operator_peak_demand"] <= 1.0 + 1e-9
    assert strict["operator_wait_vehicle_h"] > 0 and strict["operator_waits"] > 0
    assert strict["delivered_kg"] > 0
