"""B-107: R1's slope term and the uphill options are opt-in; on Mars uphill at the rule's limit the rule as is lets the
gap fall inside D0 and the slope term does not (lunarsim/atc/safety.py Move.b_front; encounter.py options)."""
import os
import sys
import warnings

import numpy as np

from lunarsim.atc import encounter as E, encounter_types as ET, safety as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "atc"))


def test_b_front_none_is_b_max():
    rng = np.random.default_rng(0)
    n = 200
    kw = dict(v=rng.uniform(0, 4, n), a_prop=rng.uniform(-1, 0.2, n), dt=0.1, theta=rng.uniform(-15, 15, n), mu=0.45,
              v_class=4.2, sight=1e4, gap_lead=rng.uniform(0, 40, n), v_lead=rng.uniform(0, 4, n), d_stop=np.inf,
              d_crew=np.inf)
    a = S.safety_check(None, S.Move(**kw))
    b = S.safety_check(None, S.Move(**kw, b_front=S.B_MAX))
    assert np.array_equal(a.a, b.a) and np.array_equal(a.rule, b.rule)


def test_mars_uphill_slope_term():
    import run_e45_uphill as U
    g = S.G_MARS
    ET.G_BUILD = g
    try:
        rng = np.random.default_rng([4507, 9, 9, 150, 0])
        specs = [U.build(rng, 15.0, "following", g, 1.0) for _ in range(40)]
        below = {}
        for rule in (False, True):
            for sp in specs:
                sp.r1_slope_term = rule
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                oc, _ = E.run_batch(E.Batch(specs, g=g), np.random.default_rng(1))
            below[rule] = int((np.asarray(oc.min_gap_same) < S.D0_M - 1e-6).sum())
        assert below[False] > 0 and below[True] == 0
    finally:
        ET.G_BUILD = S.G_MOON
