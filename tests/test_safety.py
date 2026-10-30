"""B-78: the safety program (lunarsim/atc/safety.py), the encounter simulator and the model checker."""
import math, os, sys, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim.atc import safety as S
from lunarsim.atc.safety import Move, Reserve, safety_check


def test_rss_numbers_match_traffic_and_safety_note():
    b = S.B_MIN_FLAT
    assert float(S.rss_dmin(10 / 3.6, 10 / 3.6, b)) == pytest.approx(6.9 + 5, abs=0.05)
    assert float(S.rss_dmin(15 / 3.6, 15 / 3.6, b)) == pytest.approx(12.5 + 5, abs=0.05)
    assert float(S.rss_dmin(15 / 3.6, 15 / 3.6, b, rho=3.0)) == pytest.approx(25.3 + 5, abs=0.1)
    assert float(S.b_guaranteed(20.0, 0.3)) < 0 and float(S.v_max_r2(20.0, 0.3, 1e4, 4.0)) == 0.0
    assert float(S.v_max_r2(15.0, 0.6, 1e4, 10.0)) <= math.sqrt(2 * float(S.b_guaranteed(15.0, 0.6)) * 15.0) + 1e-9


def test_reserve_r3_and_r10():
    table = {"seg": [(0.0, 10.0, 1, "A", 1)], ("apron", "P"): [(0.0, 5.0, 0, "A", 1), (1.0, 6.0, 0, "B", 2)]}
    assert not safety_check(table, Reserve("seg", 5, 8, 3, "B", d=-1)).ok              # head-on overlap
    assert safety_check(table, Reserve("seg", 5, 8, 3, "B", d=1)).ok                   # same direction follows
    assert not safety_check(table, Reserve("seg", 5, 8, 3, "B", d=1, branched=True)).ok
    assert safety_check(table, Reserve("seg", 5, 8, 3, "B", d=-1, mine_only=True)).ok  # uncoordinated view
    v = safety_check(table, Reserve(("apron", "P"), 2, 3, 3, "C", kind="slots", slots=2))
    assert not v.ok and v.until == 5.0
    assert safety_check(table, Reserve(("apron", "P"), 2, 3, 3, "C", kind="slots", slots=3)).ok


def _mv(**kw):
    base = dict(v=np.array([2.0]), a_prop=np.array([0.2]), dt=0.1, theta=np.array([0.0]), mu=np.array([0.45]),
                v_class=np.array([2.78]), sight=np.array([1e4]), gap_lead=np.array([np.inf]), v_lead=np.array([0.0]),
                d_stop=np.array([np.inf]), d_crew=np.array([np.inf]))
    base.update(kw)
    return Move(**base)


def test_move_shield():
    assert safety_check(None, _mv()).a[0] == pytest.approx(0.2)                        # free road: accepted
    v = safety_check(None, _mv(d_stop=np.array([4.1])))                               # cannot stop: brake
    assert v.modified[0] and v.a[0] < 0
    v = safety_check(None, _mv(gap_lead=np.array([8.0]), v_lead=np.array([0.0])))      # below d_min: proper response
    assert v.a[0] <= -float(S.b_guaranteed(0.0, 0.45)) + 1e-9
    v = safety_check(None, _mv(v=np.array([0.0]), d_crew=np.array([8.0])))             # crew close: stay stopped
    assert v.a[0] <= 0
    v = safety_check(None, _mv(v=np.array([0.0]), a_prop=np.array([0.0]), must_exit=np.array([True])))
    assert v.a[0] > 0                                                                  # R5: may not idle in a closing zone


def test_encounters_nominal_clean_and_reproducible():
    from lunarsim.atc import encounter as E, encounter_types as ET
    for k in (2, 5, 7):
        rng = np.random.default_rng(77 + k)
        specs = [ET.build(k, rng) for _ in range(6)]
        for sp in specs:
            sp.planner = [0] * len(sp.paths)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            oc, _ = E.run_batch(E.Batch(specs), np.random.default_rng(k))
            oc2, _ = E.run_batch(E.Batch(specs), np.random.default_rng(k))
        viol = sum(getattr(oc, f) for f in ("viol_contact", "viol_gap", "viol_zone", "viol_crew", "viol_r3", "viol_slots"))
        assert (viol == 0).all(), k
        assert np.array_equal(oc.t_end, oc2.t_end) and np.array_equal(oc.interventions, oc2.interventions)


def test_adversarial_planner_cannot_break_the_rules_head_on():
    from lunarsim.atc import encounter as E, encounter_types as ET
    rng = np.random.default_rng(5)
    specs = [ET.build(2, rng) for _ in range(10)]
    for sp in specs:
        sp.planner = [2] * len(sp.paths)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        oc, _ = E.run_batch(E.Batch(specs), np.random.default_rng(5))
    assert (oc.viol_contact == 0).all() and (oc.viol_r3 == 0).all() and (oc.interventions > 0).any()


def test_model_checker_and_mutations():
    from lunarsim.atc import modelcheck as M
    r = M.check(M.Model(["PAD", "E2W"]))
    assert r["violating_states"] == 0 and r["deadlock_states"] == 0 and r["cannot_reach_goal"] == 0
    r = M.check(M.Model(["W2E", "E2W", "E2W"], landing=False, links=False, symmetric=((1, 2),)))
    assert r["violating_states"] == 0 and r["cannot_reach_goal"] == 0
    assert M.check(M.Model(["W2E", "E2W", "E2W"], landing=False, links=False, symmetric=((1, 2),),
                           mutation="R3_exit"))["cannot_reach_goal"] > 0
    assert M.check(M.Model(["PAD", "E2W"], mutation="R5_entry"))["violating_states"] > 0
    assert M.check(M.Model(["PAD", "E2W"], mutation="R7_hold"))["violating_states"] > 0


def test_fixture_parity_python():
    """data/atc/encounter_fixtures: safety_check on each step's stored inputs reproduces the stored output (the JS port
    is checked against the same files with the tolerance in index.json)."""
    import glob, gzip, json
    fx = sorted(glob.glob(os.path.join(ROOT, "data", "atc", "encounter_fixtures", "E44_fixture_*.json.gz")))
    if not fx:
        pytest.skip("fixtures not built")
    tol = json.load(open(os.path.join(ROOT, "data", "atc", "encounter_fixtures", "index.json")))["tolerance"]
    f = lambda x: np.array([np.inf if y is None else y for y in x], float)
    for p in fx[:6]:
        doc = json.load(gzip.open(p, "rt"))
        for st in doc["steps"][::25]:
            m = st["move"]
            mv = Move(v=f(m["v"]), a_prop=f(m["a_prop"]), dt=doc["dt"], theta=f(m["theta"]), mu=f(m["mu"]),
                      v_class=f(m["v_class"]), sight=f(m["sight"]), gap_lead=f(m["gap_lead"]), v_lead=f(m["v_lead"]),
                      d_stop=f(m["d_stop"]), d_crew=f(m["d_crew"]), must_exit=np.array(m["must_exit"], bool),
                      a_max=0.2, d_crew_any=f(m["d_crew_any"]))
            a = safety_check(None, mv).a
            assert np.allclose(a, f(st["a"]), atol=max(tol["a"], 1e-6)), p
