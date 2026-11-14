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


def test_mixed_actuation_delays_are_refused():
    """B-118 N23: the command buffer has one length per batch, so a batch mixing actuation delays is refused (before,
    every lagged row got the batch's longest delay)."""
    import pytest
    import run_e45_uphill as U
    g = S.G_MOON
    rng = np.random.default_rng([4507, 1, 1, 50, 0])
    specs = [U.build(rng, 5.0, "following", g, d) for d in (S.RHO_S, S.RHO_S, 2 * S.RHO_S)]
    with pytest.raises(ValueError):
        E.Batch(specs, g=g)
    same = [U.build(rng, 5.0, "following", g, S.RHO_S) for _ in range(3)] + [U.build(rng, 5.0, "following", g, 0.0)]
    E.Batch(same, g=g)                                   # one positive delay (and zero) is fine


def _breaches(delay_s, brakes=True, steps=60):
    """A follower whose gap is below rss_dmin from step 0 on; it commands full braking at entry (or never), and acts on
    its command delay_s later through a command buffer like run_batch's (zeros before the first command)."""
    bg = 0.5
    L = int(round(delay_s / E.DT))
    buf, ptr = np.zeros(max(L, 1)), 0
    below_s, n = np.full(1, -1.0), 0
    for _ in range(steps):
        a = -bg if brakes else 0.0
        if L:
            a_ph = buf[ptr]
            buf[ptr] = a
            ptr = (ptr + 1) % L
        else:
            a_ph = a
        r1b, below_s = E.r1_breach_delayed(np.ones(1, bool), below_s, np.full(1, a_ph), bg)
        n += int(r1b[0])
    return n


def test_delayed_breach_allows_the_response_time():
    """B-118 N23 (b): with an actuation delay the breach allows R1's response time RHO_S, not the delay."""
    assert _breaches(S.RHO_S) == 0                           # brakes at entry, acts after RHO_S: compliant
    assert _breaches(2 * S.RHO_S) > 0                        # acts after 2 RHO_S: counted for the excess
    assert _breaches(2 * S.RHO_S) == int(round(S.RHO_S / E.DT)) - 1
    assert _breaches(S.RHO_S, brakes=False) > 0              # never brakes: counted after RHO_S
    assert _breaches(S.RHO_S, brakes=False) == 60 - int(round(S.RHO_S / E.DT)) - 1
