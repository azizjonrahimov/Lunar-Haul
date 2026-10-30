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


# ------------------------------------------------------------------------------------------------ batch 2
def test_batch2_fast_checks_pass():
    rows = V.check_r9_messages(20000) + V.check_r7_graph()
    rows += [r for r in V.check_l_policy() if not r["skipped"]]
    bad = [(r["id"], r["sub"], r["basis"]) for r in rows if not r["passed"]]
    assert not bad


def test_not_applicable_rows_are_skips_not_failures(tmp_path):
    rows = V.check_a_not_applicable()
    assert all(r["skipped"].startswith("not applicable") and not r["passed"] for r in rows)
    doc = json.loads(open(V.write_json(rows, str(tmp_path / "na.json")), encoding="utf-8").read())
    assert doc["summary"]["failed"] == 0 and doc["summary"]["skipped"] == len(rows)


def test_cargo_ids_unique_after_fix():
    from collections import Counter
    sim = V._p5_sim("O_ORACLE", {}, seed=1, days=120)
    V._run_quiet(sim)
    cnt = Counter(c.id for c in sim.all_cargo)
    assert len(sim.all_cargo) > 500 and max(cnt.values()) == 1


# ------------------------------------------------------------------------------------------------ batch 3 (P3)
def test_audit_and_k1_identities_on_one_run():
    import gzip
    M = V._tool("run_e46")
    T = json.load(open(M.DESIGN, encoding="utf-8"))["posted_price"]["values_usd_per_tkm"]["3eq"]
    base = json.load(gzip.open(M._name("3eq", 1, "pooled", None, 1.0, None), "rt"))
    dev = json.load(gzip.open(M._name("3eq", 1, "dev", "B", 1.25, None), "rt"))
    for rule in ("first", "second", "posted", "none"):
        assert M.money(base, rule, T, dev_owner="A", k=1.0) == M.money(base, rule, T)
    assert all(v == 0 for v in M.money(dev, "first", T, dev_owner="B", k=1.25, q=0.0)["fines"].values())
    one = M.money(dev, "first", T, dev_owner="B", k=1.25, q=1.0, m=3.0)["fines"]["B"]
    mis = sum(abs(0.25 * j["cost"] / len(j["carriers"]) * dev["eps"]["B"]) for j in dev["jobs"] for c in j["carriers"]
              if c == "B")
    assert one == pytest.approx(3.0 * mis, rel=1e-12)


def test_x7_timer_is_bit_identical():
    rows = V.check_x7_timing()
    assert rows[0]["passed"]


# ------------------------------------------------------------------------------------------------ batch 3 part 2
def test_safety_injection_and_minimal_interference():
    rows = V.check_s2_injection(200) + V.check_s3_minimal(2000)
    bad = [(r["sub"], r["simulated"]) for r in rows if not r["passed"] and r["sub"] != "unholdable slope flagged"]
    assert not bad


def test_single_lane_harness_matches_lindley_and_deterministic_cases():
    traverse, _ = V._road_harness()
    rng = np.random.default_rng(0)
    arr = np.cumsum(rng.exponential(1 / 6.0, 3000))
    w = np.array([traverse(i, float(a), 0.1) for i, a in enumerate(arr)])
    assert np.max(np.abs(w - V.queue_fcfs(arr, np.full(len(arr), 0.1), 1))) <= 1e-9
    assert all(r["passed"] for r in V.check_t2_deterministic())


def test_closest_approach_row():
    assert V.check_s1_separation()[0]["passed"]


# ------------------------------------------------------------------------------------------------ B-80 trace pair
def test_trace_pair_index_and_positions():
    import os
    if not os.path.isfile(os.path.join(V._repo(), "data", "atc", "trace_pair", "index.json")):
        pytest.skip("no trace pair")
    d, idx, docs = V._trace_files()
    assert set(docs) == {"with", "without"}
    for n, r in idx["runs"].items():
        assert os.path.getsize(os.path.join(d, r["file"])) == r["bytes"] <= 400_000
        t = docs[n]
        assert t["radio"][0][0] == idx["window"]["t0_h"] and len(t["radio"][0]) == 4
        assert all(len(e[3]) == len(t["fleet"]) for e in t["radio"][1:])
        assert set(t["summary"]) == {"urgent_items_waiting", "idle_robot_hours", "messages_per_hour", "earth_hand_hours"}
