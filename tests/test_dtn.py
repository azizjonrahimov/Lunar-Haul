"""B-94: store-and-forward, custody, the lost-link plan and age of information (lunarsim/atc/dtn.py)."""
import json
import os

import numpy as np
import pytest

from lunarsim.atc import dtn as DT
from lunarsim.atc.dtn import BASE, Msg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def chain(T, link_steps):
    """Two vehicles and the base mast (node 2): vehicle 0 - vehicle 1 - base, the 1-base link only in link_steps."""
    A = np.zeros((T, 3, 3), bool)
    A[:, 0, 1] = A[:, 1, 0] = True
    for k in link_steps:
        A[k, 1, 2] = A[k, 2, 1] = True
    return A


def test_store_and_forward_waits_for_the_contact():
    A = chain(100, range(50, 100))                      # the base appears at step 50
    m = [Msg(0, "award", BASE, 0, 0.0, 92, 3600.0)]
    sf = DT.simulate(A, m, "sf", 0.0, np.random.default_rng(0), 60.0)[0]
    assert sf.t_done is not None and 50 * 60.0 <= sf.t_done < 51 * 60.0
    dr = DT.simulate(A, m, "drop_retry", 0.0, np.random.default_rng(0), 60.0)[0]
    assert dr.t_done is None and dr.expired                # 5 tries 3 min apart, all before the contact


def test_custody_survives_loss_drop_retry_does_not():
    A = chain(200, range(200))                           # always linked, two hops
    msgs = [Msg(i, "award", BASE, 0, i * 30.0, 92, 3600.0) for i in range(200)]
    sf = DT.simulate(A, msgs, "sf", 0.4, np.random.default_rng(1), 60.0)
    dr = DT.simulate(A, msgs, "drop_retry", 0.4, np.random.default_rng(1), 60.0)
    assert sum(x.t_done is None for x in sf) == 0
    lost = sum(x.t_done is None for x in dr)
    # drop_retry loses a message only if all 5 two-hop tries fail: (1 - 0.6^2)^5 = 0.107
    assert 0.04 < lost / len(dr) < 0.2
    assert np.mean([x.t_done - x.t0 for x in sf]) < np.mean([x.t_done - x.t0 for x in dr if x.t_done is not None])


def test_lifetime_and_earth_link():
    A = chain(100, range(100))
    m = [Msg(0, "ledger_earth", BASE, -2, 0.0, 10_000, 600.0)]
    off = DT.simulate(A, m, "sf", 0.0, np.random.default_rng(0), 60.0, earth_up=lambda k: False)[0]
    assert off.expired and off.t_done is None
    on = DT.simulate(A, m, "sf", 0.0, np.random.default_rng(0), 60.0, earth_up=lambda k: k >= 5)[0]
    assert on.t_done is not None and on.t_done >= 5 * 60.0


def test_age_of_information_matches_note03_e7():
    """One hop, update every 10 s, no path loss: mean age about T/2 + step bias; with loss p per hop and no retry the
    age grows as note 03 E7 says (mean age rises with 1/q)."""
    A = chain(2000, range(2000))
    a0 = DT.age_of_information(A, 0.0, "drop_retry", np.random.default_rng(0), 60.0)
    a4 = DT.age_of_information(A, 0.4, "drop_retry", np.random.default_rng(0), 60.0)
    s4 = DT.age_of_information(A, 0.4, "sf", np.random.default_rng(0), 60.0)
    assert a4[1] > a0[1] and s4[1] < a4[1]
    # B-118 N5: every 10 s update arrives: the age is a sawtooth from 0 to 10 s, mean 5 s (was floored at dt/2 = 30 s)
    assert a0[1] == pytest.approx(5.0, abs=0.01)


def test_age_of_information_no_path_grows():
    A = chain(100, range(50))                            # linked for 50 steps, then never
    a = DT.age_of_information(A, 0.0, "sf", np.random.default_rng(0), 60.0)
    # first half: 5 s; second half: the age grows linearly from 0 to 3,000 s, mean 1,500 s -> overall about 752.5 s
    assert a[1] == pytest.approx(0.5 * 5.0 + 0.5 * 1500.0, rel=0.01)


class _Tr:
    def __init__(self, T, n):
        self.dt_s = 60.0
        self.ds = np.zeros((T, n))


def _isolated_chain(T=200):
    A = chain(T, list(range(0, 20)) + list(range(150, T)))
    A[:, 0, 2] = A[:, 2, 0] = False
    return A


def test_lost_link_plan_pre_review_rule():
    """The rule before 13 Nov 2026, kept as a named variant: driving in the hour BEFORE the loss."""
    A = _isolated_chain()
    tr = _Tr(200, 2)
    tr.ds[10:20, 1] = 50.0                                # vehicle 1 drove 10 min before losing the link
    A2, st = DT.lost_link_plan(A, tr, {"return_rule": "pre_review"})
    # both lose the base at step 20 (vehicle 0 only ever reached it through vehicle 1). Vehicle 1: T_hold 600 s
    # (10 steps) + 2 x 600 s (20 steps) -> step 50; vehicle 0 did not drive: T_hold alone -> step 30
    assert not A2[49, 1, 2] and A2[50, 1, 2] and A2[149, 1, 2]
    assert not A2[29, 0, 2] and A2[30, 0, 2] and st["returns"] == 2
    assert (DT.base_hops(A)[20:150, 1] < 0).all()


def test_lost_link_plan_papers_rule():
    """B-118 N6 (default): retrace at half speed what was driven SINCE the loss, up to the hold timer."""
    A = _isolated_chain()
    tr = _Tr(200, 2)
    tr.ds[10:20, 1] = 50.0                                # 10 min of driving before the loss: no longer counts
    tr.ds[20:25, 1] = 50.0                                # 5 min of driving after the loss
    A2, st = DT.lost_link_plan(A, tr)
    # vehicle 1: 600 s hold + 2 x 300 s = 1,200 s = 20 steps -> step 40 (the pre-review rule gives step 50)
    assert not A2[39, 1, 2] and A2[40, 1, 2] and A2[149, 1, 2]
    assert not A2[29, 0, 2] and A2[30, 0, 2] and st["returns"] == 2
    A3, _ = DT.lost_link_plan(A, tr, {"return_rule": "pre_review"})
    assert not A3[49, 1, 2] and A3[50, 1, 2]
    tr.ds[20:60, 1] = 50.0                                # driving beyond the hold timer does not count
    A4, _ = DT.lost_link_plan(A, tr)
    assert not A4[49, 1, 2] and A4[50, 1, 2]              # 600 + 2 x 600 s = 30 steps -> step 50
    with pytest.raises(ValueError):
        DT.lost_link_plan(A, tr, {"return_rule": "other"})


def test_never_delivered_after_the_lifetime():
    """B-118 N3: a step gives a bundle only the attempts that fit, and nothing is delivered after its lifetime."""
    A = chain(20, range(20))
    # created just after a step starts: before the fix the next step gave them six more tries whatever time was left
    msgs = [Msg(i, "grant", BASE, 0, 5.0 + (i % 5), 92, 60.0) for i in range(2000)]
    res = DT.simulate(A, msgs, "sf", 0.7, np.random.default_rng(3), 60.0)
    done = [m for m in res if m.t_done is not None]
    assert done and all(m.t_done <= m.t0 + m.life_s + 1e-9 for m in done)
    assert all(m.expired for m in res if m.t_done is None)
    dr = DT.simulate(A, msgs, "drop_retry", 0.7, np.random.default_rng(3), 60.0, {"retry_s": 20.0})
    assert all(m.t_done <= m.t0 + m.life_s + 1e-9 for m in dr if m.t_done is not None)


def test_delivery_recorded_in_the_step_it_happens():
    A = chain(10, range(10))
    m = DT.simulate(A, [Msg(0, "award", BASE, 0, 0.0, 92, 3600.0)], "sf", 0.0, np.random.default_rng(0), 60.0)[0]
    assert m.t_done == pytest.approx(0.02)               # two hops of 10 ms
    # with loss, an arrival on a step's last attempt keeps its own time (before: stamped at the next step's start)
    msgs = [Msg(i, "award", BASE, 0, 0.0, 92, 3600.0) for i in range(2000)]
    res = DT.simulate(chain(200, range(200)), msgs, "sf", 0.8, np.random.default_rng(5), 60.0)
    assert not any(m.t_done is not None and m.t_done % 60.0 == 0.0 for m in res)


def test_window_end_is_not_expiry():
    """B-118 N4: a bundle alive and undelivered at the window's end is censored, not lost; so is one created after."""
    A = chain(10, [])                                    # never a path to vehicle 0
    msgs = [Msg(0, "award", BASE, 0, 0.0, 92, 3600.0), Msg(1, "award", BASE, 0, 700.0, 92, 3600.0),
            Msg(2, "grant", BASE, 0, 0.0, 92, 60.0)]
    for proto in ("sf", "drop_retry"):
        r = DT.simulate(A, msgs, proto, 0.0, np.random.default_rng(0), 60.0)
        assert r[0].censored and not r[0].expired and r[0].t_done is None
        assert r[1].censored and not r[1].expired
        assert r[2].expired and not r[2].censored         # its lifetime ended inside the window


def test_lifetime_ending_in_the_last_step_is_expired():
    """B-120 B: a bundle held with no path through the final step, whose lifetime ended inside the window, is expired
    (before, store-and-forward called it censored while drop_retry called it expired); a deadline at the window's end
    itself is expired too; one later than the end is censored. Same for both protocols."""
    A = chain(2, [])                                     # 2 steps of 60 s, never a path to vehicle 0
    for proto in ("sf", "drop_retry"):
        for life, expired in ((90.0, True), (120.0, True), (600.0, False)):    # 600 s: drop_retry's next try (180 s)
            if proto == "drop_retry" and life == 600.0:                      # is still inside the lifetime
                assert DT.DEFAULTS["retry_s"] < life
            m = DT.simulate(A, [Msg(0, "award", BASE, 0, 0.0, 92, life)], proto, 0.0, np.random.default_rng(0), 60.0)[0]
            assert m.t_done is None and m.expired is expired and m.censored is (not expired), (proto, life)
    m = DT.simulate(A, [Msg(0, "award", BASE, 0, 0.0, 92, 121.0)], "sf", 0.0, np.random.default_rng(0), 60.0)[0]
    assert m.censored and not m.expired                  # one second past the end: not known
    # an Earth-bound bundle at the base with the Earth link down to the end (E54's ledgers)
    A = chain(3, range(3))
    for life, expired in ((180.0, True), (240.0, False)):
        m = DT.simulate(A, [Msg(0, "ledger_earth", BASE, -2, 0.0, 10_000, life)], "sf", 0.0,
                        np.random.default_rng(0), 60.0, earth_up=lambda k: False)[0]
        assert m.expired is expired and m.censored is (not expired)


def test_full_base_store_refuses_an_earth_bound_bundle():
    """B-120 G: the base holds an Earth-bound bundle until the Earth link, so a full base store refuses custody like
    a full relay (before, the base store was unbounded for Earth-bound bundles)."""
    A = chain(40, range(40))
    held = Msg(0, "ledger_earth", BASE, -2, 0.0, 80, 7200.0)          # fills the base store (100 B) until Earth is up
    x = Msg(1, "ledger_earth", 1, -2, 0.0, 50, 7200.0)                # from vehicle 1, one hop to the base
    up = lambda k: k >= 20
    r = DT.simulate(A, [held, x], "sf", 0.0, np.random.default_rng(0), 60.0, {"queue_bytes": 100}, earth_up=up)
    hl = DT.DEFAULTS["hop_latency_s"]
    assert r[0].t_done == pytest.approx(20 * 60.0 + hl)
    assert r[1].t_done == pytest.approx(20 * 60.0 + 2 * hl)   # refused at the full base until the held bundle left
    r2 = DT.simulate(A, [held, x], "sf", 0.0, np.random.default_rng(0), 60.0, earth_up=up)
    assert r2[1].t_done == pytest.approx(20 * 60.0 + hl)     # default 64 MB store: at the base already, one hop


def test_simulate_refuses_an_unknown_protocol():
    """B-120 G: before, any string but "drop_retry" ran as store-and-forward."""
    A = chain(2, [0, 1])
    msgs = [Msg(0, "award", BASE, 0, 0.0, 92, 600.0)]
    with pytest.raises(ValueError):
        DT.simulate(A, msgs, "drop-retry", 0.0, np.random.default_rng(0), 60.0)
    a = DT.simulate(A, msgs, "sf", 0.0, np.random.default_rng(0), 60.0)[0]
    b = DT.simulate(A, msgs, "sf_ll", 0.0, np.random.default_rng(0), 60.0)[0]
    assert a.t_done == b.t_done is not None


def test_e54_fingerprint_ignores_docstrings_and_comments():
    """B-120 C: the E54 fingerprint hashes code, not docstrings, comments or layout."""
    import sys
    sys.path.insert(0, os.path.join(ROOT, "tools", "atc"))
    import run_e54 as R
    a = 'def f(x):\n    """doc"""\n    return x + 1  # note\n'
    b = 'def f(x):\n    """another doc"""\n\n    return (x + 1)\n'
    c = 'def f(x):\n    """doc"""\n    return x + 2\n'
    assert R._ast_digest(a) == R._ast_digest(b) != R._ast_digest(c)
    assert R._ast_digest('"""module doc"""\nimport os\n') == R._ast_digest("import os  # c\n")


def test_full_relay_refuses_custody():
    """C11: a relay whose store is full does not take the bundle; it moves on when the store frees."""
    T = 60
    A = np.zeros((T, 4, 4), bool)                        # v0, v1, v2, base (3)
    A[:, 3, 1] = A[:, 1, 3] = True
    A[:, 1, 0] = A[:, 0, 1] = True
    A[30:, 1, 2] = A[30:, 2, 1] = True                   # v1 - v2 only from step 30
    x = Msg(0, "task_state", 1, 2, 0.0, 92, 7200.0)      # waits at v1 until step 30
    y = Msg(1, "award", BASE, 0, 1.0, 92, 7200.0)        # base -> v1 -> v0
    r = DT.simulate(A, [x, y], "sf", 0.0, np.random.default_rng(0), 60.0, {"queue_bytes": 100})
    assert r[0].t_done == pytest.approx(30 * 60.0 + 0.01)
    assert r[1].t_done >= 30 * 60.0                      # refused by the full relay until x left
    r2 = DT.simulate(A, [x, y], "sf", 0.0, np.random.default_rng(0), 60.0)
    assert r2[1].t_done < 60.0                           # with the default 64 MB store it passes at once


def test_e54_outputs():
    p = os.path.join(ROOT, "results", "E54_dtn.json")
    if not os.path.isfile(p):
        pytest.skip("E54 not built")
    d = json.load(open(p))
    # B-119: the verdict recomputed from the file (paired CI below 0, and no reservation stuck under sf_ll, which
    # holds by rule); the per-seed means agree with the table's award losses at loss 0.25
    h = d["h14"]
    assert h["supported"] is bool(h["difference_sf_ll_minus_drop_retry"]["ci"][1] < 0 and h["stuck_reservations_sf_ll"] == 0)
    rows = {(r["loss"], r["protocol"]): r for r in d["rows"]}
    n = len(d["seeds"])
    assert abs(rows[(0.25, "drop_retry")]["award_lost"] / n - h["lost_jobs_drop_retry_per_seed"]["mean"]) < 1e-9
    assert abs(rows[(0.25, "sf_ll")]["award_lost"] / n - h["lost_jobs_sf_ll_per_seed"]["mean"]) < 1e-9
    assert rows[(0.25, "sf_ll")]["stuck_reservations"] == h["stuck_reservations_sf_ll"] == 0


# B-119 T: the six custody cells the state-machines reviewer found untested (drop_retry x expire; sf x expire;
# drop_retry to EARTH x deliver / expire / drop; sf to EARTH x drop). EARTH-bound messages leave from the base.
def test_cell_drop_retry_expires():
    A = chain(30, [])                                    # never a path to vehicle 0
    m = DT.simulate(A, [Msg(0, "grant", BASE, 0, 0.0, 92, 600.0)], "drop_retry", 0.0, np.random.default_rng(0), 60.0)[0]
    assert m.expired and not m.censored and m.t_done is None and m.tries == 4      # tries at 0, 180, 360, 540 s


def test_cell_sf_expires():
    A = chain(30, [])
    m = DT.simulate(A, [Msg(0, "award", BASE, 0, 0.0, 92, 600.0)], "sf", 0.0, np.random.default_rng(0), 60.0)[0]
    assert m.expired and not m.censored and m.t_done is None


def test_cell_drop_retry_to_earth_delivers():
    A = chain(10, range(10))
    m = DT.simulate(A, [Msg(0, "ledger_earth", BASE, -2, 30.0, 10_000, 3600.0)], "drop_retry", 0.0,
                    np.random.default_rng(0), 60.0, earth_up=lambda k: True)[0]
    assert m.t_done == pytest.approx(30.0 + 0.01) and m.tries == 1   # one hop: the Earth link from the base


def test_cell_drop_retry_to_earth_expires():
    A = chain(30, range(30))
    m = DT.simulate(A, [Msg(0, "ledger_earth", BASE, -2, 0.0, 10_000, 600.0)], "drop_retry", 0.0,
                    np.random.default_rng(0), 60.0, earth_up=lambda k: False)[0]
    assert m.expired and m.t_done is None and not m.censored


def test_cell_drop_retry_to_earth_drops_then_gives_up():
    A = chain(30, range(30))
    m = DT.simulate(A, [Msg(0, "ledger_earth", BASE, -2, 0.0, 10_000, 1700.0)], "drop_retry", 0.999,
                    np.random.default_rng(1), 60.0, earth_up=lambda k: True)[0]
    assert m.tries == DT.DEFAULTS["max_tries"] and m.expired and m.t_done is None    # every try dropped


def test_cell_sf_to_earth_drops_and_retransmits():
    A = chain(30, range(30))
    msgs = [Msg(i, "ledger_earth", BASE, -2, 0.0, 10_000, 1700.0) for i in range(200)]
    res = DT.simulate(A, msgs, "sf", 0.7, np.random.default_rng(2), 60.0, earth_up=lambda k: True)
    done = [m.t_done for m in res if m.t_done is not None]
    assert len(done) == 200                                   # custody retransmits until it gets through
    assert sum(t >= DT.DEFAULTS["custody_timer_s"] for t in done) > 100   # most were dropped at least once first
    assert all(round((t - DT.DEFAULTS["hop_latency_s"]) / DT.DEFAULTS["custody_timer_s"], 6).is_integer() for t in done)


# B-120 G: the state-machines reviewer's untested cells (.gstack/tmp/state-machines.50bfcda2244a.md)
def test_cell_earth_bound_censored_when_alive_at_the_end():
    """drop_retry:earth and sf:earth x censor: Earth link down to the end, lifetime past the end."""
    for proto in ("drop_retry", "sf"):
        m = DT.simulate(chain(3, range(3)), [Msg(0, "ledger_earth", BASE, -2, 0.0, 10_000, 3600.0)], proto, 0.0,
                        np.random.default_rng(0), 60.0, earth_up=lambda k: False)[0]
        assert m.censored and not m.expired and m.t_done is None, proto


def test_cell_sf_ll_deliver_hold_drop_expire_censor():
    """simulate on a lost_link_plan output (E54's sf_ll cells run protocol "sf" on that plan): vehicle 0 loses the
    base at step 20 and the rule relinks it at step 30 (T_hold alone: it did not drive); the recorded plan relinks
    it only at step 150."""
    A = _isolated_chain()
    A2, _ = DT.lost_link_plan(A, _Tr(200, 2))
    m = [Msg(0, "award", BASE, 0, 25 * 60.0, 92, 3600.0)]
    assert DT.simulate(A, m, "sf", 0.0, np.random.default_rng(0), 60.0)[0].expired       # isolated until step 150
    r = DT.simulate(A2, m, "sf_ll", 0.0, np.random.default_rng(0), 60.0)[0]
    assert r.t_done == pytest.approx(30 * 60.0 + DT.DEFAULTS["hop_latency_s"])          # deliver, held until 1,800 s
    many = [Msg(i, "award", BASE, 0, 25 * 60.0, 92, 3600.0) for i in range(100)]
    res = DT.simulate(A2, many, "sf_ll", 0.4, np.random.default_rng(1), 60.0)            # drop: custody retransmits
    assert all(x.t_done is not None and x.t_done >= 30 * 60.0 for x in res)
    assert any(x.t_done > 30 * 60.0 + DT.DEFAULTS["custody_timer_s"] for x in res)
    g = DT.simulate(A2, [Msg(0, "grant", BASE, 0, 21 * 60.0, 92, 60.0)], "sf_ll", 0.0,
                    np.random.default_rng(0), 60.0)[0]
    assert g.expired and not g.censored and g.t_done is None                             # expire before the return
    c = DT.simulate(A2[:25], [Msg(0, "award", BASE, 0, 21 * 60.0, 92, 3600.0)], "sf_ll", 0.0,
                    np.random.default_rng(0), 60.0)[0]
    assert c.censored and not c.expired and c.t_done is None                             # window ends first


def test_cell_full_store_drops_the_newest_at_creation():
    A = chain(100, range(50, 100))
    msgs = [Msg(0, "award", BASE, 0, 0.0, 92, 7200.0), Msg(1, "award", BASE, 0, 1.0, 92, 7200.0)]
    r = DT.simulate(A, msgs, "sf", 0.0, np.random.default_rng(0), 60.0, {"queue_bytes": 100})
    assert r[0].t_done is not None and r[1].expired and not r[1].censored and r[1].t_done is None
    dr = DT.simulate(chain(100, range(100)), msgs, "drop_retry", 0.0, np.random.default_rng(0), 60.0,
                     {"queue_bytes": 100})
    assert all(m.t_done is not None for m in dr)                                         # drop_retry has no store


def test_cell_short_isolation_has_no_return():
    """papers and pre_review x reconnect before the return: an isolation shorter than T_hold changes nothing."""
    A = chain(200, list(range(0, 20)) + list(range(28, 200)))     # isolated for 8 steps < T_hold (10 steps)
    A[:, 0, 2] = A[:, 2, 0] = False
    for rule in DT.RETURN_RULES:
        A2, st = DT.lost_link_plan(A, _Tr(200, 2), {"return_rule": rule})
        assert (A2 == A).all() and st["returns"] == 0 and st["isolation_h_saved"] == 0.0, rule
