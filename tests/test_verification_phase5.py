"""B-79 batch 1: the Phase 5 verification checks (lunarsim/vv5.py). The long queueing checks run in
`python -m lunarsim.vv5`, which writes results/vv_phase5.json; here the references, the recursions and the fast
checks, plus the JSON writer's contract."""
import json
import math

import numpy as np
import pytest

from lunarsim import vv5 as V


def test_mdc_reduces_to_md1_and_erlang_c_to_mm1():
    assert V.mdc_wq(0.3, 2.0, 1) == pytest.approx(0.6 * 2.0 / (2 * 0.4), rel=1e-8)
    assert V.erlang_c_wq(0.3, 2.0, 1) == pytest.approx(0.6 * 2.0 / 0.4, rel=1e-12)
    assert V.mdc_wq(0.6, 2.0, 2) < V.erlang_c_wq(0.6, 2.0, 2)       # deterministic service waits less


def test_fcfs_recursion_by_hand():
    w = V.queue_fcfs(np.array([0.0, 0.5, 1.0, 1.2]), np.array([2.0, 2.0, 2.0, 2.0]), 2)
    assert w.tolist() == pytest.approx([0.0, 0.0, 1.0, 1.3])


def test_priority_recursion_serves_class_one_first():
    w = V.queue_priority(np.array([0.0, 0.1, 0.2]), np.array([2, 2, 1]), np.array([1.0, 1.0, 1.0]))
    assert w.tolist() == pytest.approx([0.0, 1.9, 0.8])            # item 3 (class 1) overtakes item 2


def test_fast_checks_pass():
    rows = [V.check_d9_hungarian(200)] + V.check_e3_energy() + V.check_r1_horizon() + V.check_d6_one_owner() \
        + V.check_d7_time_scale() + V.check_d11_inputs(200)
    bad = [(r["id"], r["sub"], r["basis"]) for r in rows if not r["passed"]]
    assert not bad
    keys = {"id", "sub", "technique", "factor", "kind", "priority", "papers", "ci99", "bias_flag", "exposure",
            "runtime_s", "tolerance_source", "name", "reference", "simulated", "tolerance", "mode", "unit", "error",
            "rel_error", "passed", "skipped", "basis", "source"}
    assert all(keys <= set(r) for r in rows)


def test_empty_fleet_does_not_crash():
    from lunarsim import dispatch
    from lunarsim.engine import Simulation
    from lunarsim.scenario import Scenario
    out = Simulation(Scenario(fleet=[]), dispatch.marketplace, seed=1).run()
    assert out["delivered_kg"] == 0 and out["backlog_kg"] + out["stranded_kg"] == pytest.approx(out["ready_kg"])


def test_engine_queue_equals_recursion_short():
    S = V._service_times(False)
    sim, items, _ = V._queue_run(0.6 / S.mean() * V.HOURS_PER_YEAR, 0.5)
    w, _ = V._waits(items, sim.sc.horizon_h)
    sv = np.array([d for _, d, _ in sim.vv_service])
    ref = V.queue_fcfs(np.array([c.t_ready for c in items]), sv, 1)[:len(w)]
    assert len(w) > 500 and np.max(np.abs(w - ref)) <= 1e-9


def test_write_json_nulls_and_unique(tmp_path):
    rows = [V._row("X0", "a", "nan row", 1.0, float("nan"), 0.1, "u", "b", "t", "f", "V", "P1", ["P1"]),
            V._row("X0", "b", "ok row", 1.0, 1.0, 0.1, "u", "b", "t", "f", "V", "P1", ["P1"])]
    rows[0]["skipped"] = "test"
    p = V.write_json(rows, str(tmp_path / "vv.json"))
    doc = json.loads(open(p, encoding="utf-8").read())
    assert doc["rows"][0]["simulated"] is None and doc["summary"] == {"rows": 2, "passed": 1, "failed": 0,
                                                                     "skipped": 1, "bias_flags": 0}
    assert "commit" in doc
    with pytest.raises(ValueError):
        V.write_json(rows + [rows[1]], str(tmp_path / "dup.json"))
