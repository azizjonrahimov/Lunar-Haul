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
    assert a0[1] == pytest.approx(30.0, abs=1.0)        # half a step: the step-resolution bias, the same everywhere


def test_lost_link_plan_shortens_isolation():
    T = 200
    A = chain(T, list(range(0, 20)) + list(range(150, T)))
    A[:, 0, 2] = A[:, 2, 0] = False

    class Tr:
        dt_s = 60.0
        ds = np.zeros((T, 2))
    Tr.ds[10:20, 1] = 50.0                                # vehicle 1 drove 10 min before losing the link
    A2, st = DT.lost_link_plan(A, Tr)
    # both vehicles lose the base at step 20 (vehicle 0 only ever reached it through vehicle 1). Vehicle 1 drove 10 min
    # before: T_hold 600 s (10 steps) + 2 x 600 s back at half speed (20 steps) -> its own link at step 50; vehicle 0
    # did not drive: T_hold alone -> step 30
    assert not A2[49, 1, 2] and A2[50, 1, 2] and A2[149, 1, 2]
    assert not A2[29, 0, 2] and A2[30, 0, 2] and st["returns"] == 2
    assert (DT.base_hops(A)[20:150, 1] < 0).all()


def test_e54_outputs():
    p = os.path.join(ROOT, "results", "E54_dtn.json")
    if not os.path.isfile(p):
        pytest.skip("E54 not built")
    d = json.load(open(p))
    assert isinstance(d["h14"]["supported"], bool) and d["h14"]["stuck_reservations_sf_ll"] == 0
