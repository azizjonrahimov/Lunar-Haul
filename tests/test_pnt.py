"""B-90: positioning layer (lunarsim/atc/pnt.py), the opt-in margins in safety.py and roads.py, and the E50 files."""
import json
import math
import os

import numpy as np
import pytest

from lunarsim.atc import pnt as PN
from lunarsim.atc import safety as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def straight(T=120, N=400, v=1.0, dt=60.0, cls=PN.FIRM, arrive_every=None, lit=True):
    """N vehicles driving straight east at v m/s, one leg each (no ranging geometry needed)."""
    ds = np.full((T, N), v * dt, np.float32)
    head = np.zeros((T, N, 2), np.float32)
    head[..., 0] = 1.0
    arrive = np.zeros((T, N), bool)
    leg = np.zeros((T, N), np.int32)
    if arrive_every:
        arrive[arrive_every::arrive_every] = True
    return PN.Trajectories(t_h=np.arange(T) * dt / 3600.0, xy=np.zeros((T, N, 2), np.float32),
                           idx=np.zeros((T, N), np.int32), ds=ds, head=head, leg=leg,
                           cls=np.full((T, N), cls, np.int8), lit=np.full((T, N), lit), arrive=arrive,
                           ids=np.arange(N), ant=np.full(N, 2.5), dt_s=dt)


def nees(res):
    e = res.e.astype(float)
    P = res.P.astype(float) + 1e-9 * np.eye(2)
    return np.einsum("tni,tnij,tnj->tn", e, np.linalg.inv(P), e)


def test_dead_reckoning_grows_as_percent_of_distance():
    """Note 01 D: 1-sigma horizontal error = k x distance (bias per leg; the star-tracker heading term is 0.17 %)."""
    tr = straight()
    res = PN.simulate(tr, ("dr",), seed=1, store_errors=True)
    d = np.cumsum(tr.ds[:, 0])
    rms = np.sqrt((res.err.astype(float) ** 2).mean(axis=1))
    k = PN.DEFAULTS["dr_firm"]
    assert rms[-1] / d[-1] == pytest.approx(math.hypot(k, math.radians(0.1)), rel=0.1)
    loose = PN.simulate(straight(cls=PN.LOOSE), ("dr",), seed=1)
    assert np.sqrt((loose.err[-1].astype(float) ** 2).mean()) / d[-1] == pytest.approx(PN.DEFAULTS["dr_loose"], rel=0.1)


def test_filter_is_consistent_and_fixes_bound_the_error():
    tr = straight(arrive_every=20)
    res = PN.simulate(tr, ("dr", "fixes"), seed=2, store_errors=True)
    assert 1.5 < nees(res)[5:].mean() < 2.5                     # chi-square, 2 degrees of freedom
    dr = PN.simulate(tr, ("dr",), seed=2)
    assert res.err[-1].mean() < 0.1 * dr.err[-1].mean()
    assert res.counts["fixes"] > 0 and res.counts["fix_stop_h"] > 0


def test_common_random_numbers_and_perfect():
    tr = straight(T=30, N=20)
    a = PN.simulate(tr, ("dr",), seed=3)
    b = PN.simulate(tr, ("dr", "lans"), seed=3, params={"year": 2028})      # LANS share 0 in 2028: identical
    assert np.array_equal(a.err, b.err)
    p = PN.simulate(tr, (), seed=3)
    assert not p.err.any() and not p.b95.any()


def test_lans_share_by_year_and_slip():
    assert PN.lans_share(2028) == 0.0 and PN.lans_share(2029) == 0.4 and PN.lans_share(2035) == 0.8
    assert PN.lans_share(2030, {"lans_slip_years": 1}) == 0.4
    assert PN.lans_share(2020) == 0.0


def test_covariance_intersection_never_grows_the_trace():
    rng = np.random.default_rng(0)
    for _ in range(200):
        A = rng.normal(size=(4, 4))
        P = A @ A.T + 0.1 * np.eye(4)
        u = rng.normal(size=2)
        u /= np.linalg.norm(u)
        z1, P1 = PN._ci_update(np.zeros(4), P, u, 0.0, float(rng.uniform(0.01, 100.0)))
        assert P1[0, 0] + P1[1, 1] <= P[0, 0] + P[1, 1] + 1e-9
    P = np.diag([4.0, 4.0, 0.5, 0.5])
    for _ in range(500):                                          # the same range again and again stays bounded
        _, P = PN._ci_update(np.zeros(4), P, np.array([1.0, 0.0]), 0.0, 9.0)
    assert P[1, 1] <= 4.0 + 1e-9


def test_bound95_and_pair_bound():
    P = np.diag([1.0, 1.0])
    assert PN.bound95(P) == pytest.approx(PN.R95)
    assert PN.pair_bound95(P, P) == pytest.approx(PN.R95 * math.sqrt(2))
    # 95 % of 2D Gaussian samples fall inside the bound
    x = np.random.default_rng(1).normal(size=(200000, 2))
    assert (np.hypot(*x.T) <= PN.R95).mean() == pytest.approx(0.95, abs=0.003)


def test_safety_move_margin_is_opt_in():
    kw = dict(v=np.array([1.0, 1.0]), a_prop=np.array([0.2, 0.2]), dt=0.1, theta=0.0, mu=0.45, v_class=2.0,
              sight=np.inf, gap_lead=np.array([9.0, 9.0]), v_lead=np.array([1.0, 1.0]), d_stop=np.inf, d_crew=np.inf)
    base = S.safety_check(None, S.Move(**kw))
    zero = S.safety_check(None, S.Move(**kw, pos_bound=0.0))
    assert np.array_equal(base.a, zero.a) and np.array_equal(base.rule, zero.rule)
    wide = S.safety_check(None, S.Move(**kw, pos_bound=np.array([0.0, 10.0])))
    assert wide.a[0] == base.a[0] and wide.a[1] < base.a[1] and wide.rule[1] == 1
    assert S.reservation_margin_h(5.0, 1.0) == pytest.approx(5.0 / 3600.0)      # note 01 E6: 5 m at 1 m/s = 5 s


def test_e50_outputs():
    path = os.path.join(ROOT, "results", "E50_summary.json")
    if not os.path.isfile(path):
        pytest.skip("E50 not built")
    d = json.load(open(path))
    assert len(d["seeds"]["1"]) == 30
    e1 = d["errors"]["1"]
    p95 = [e1[s]["all"]["p95_m"]["mean"] for s in ("dr", "dr+ranging", "dr+ranging+fixes", "lans@2030")]
    assert p95 == sorted(p95, reverse=True)                     # each layer removes error
    assert d["h9"]["1"]["dr_supported"] is True
    tr = json.load(open(os.path.join(ROOT, "results", "E50_trace.json")))
    assert tr["format"] == "lunarsim-e50-trace" and len(tr["vehicles"]) == 2


def test_arrival_step_belongs_to_its_leg():
    """B-118 N15 (and N14's exits): the partial distance driven in the arrival step keeps the leg's heading, class and
    leg index; before, it had a zero heading and leg -1, so the filter redrew the leg's bias and E50's timing shift
    of a reservation ending in that step was 0."""
    sample_xy = np.array([[0.0, 0.0], [50.0, 0.0], [100.0, 0.0]])
    tr = PN.Trajectories.from_segments({1: [["A", "B", 0.005, 0.02, 0]]}, {1: "A"}, 0.0, 0.05, 60.0, {1: 2.5},
                                       lambda s: s, sample_xy, {"A": 0, "B": 2}, {"A->B": [0, 1, 2]}, np.zeros(3))
    k_drive, k_arr = 1, 2
    assert tr.ds[k_drive, 0] > 0 and tr.ds[k_arr, 0] > 0 and tr.arrive[k_arr, 0]
    assert abs(tr.ds[k_drive, 0] + tr.ds[k_arr, 0] - 100.0) < 1e-3
    assert tr.head[k_arr, 0].tolist() == [1.0, 0.0]
    assert tr.leg[k_arr, 0] == tr.leg[k_drive, 0] >= 0
    assert tr.cls[k_arr, 0] == tr.cls[k_drive, 0]


class _OpenSky:
    """A line-of-sight stub: everything sees everything (one route sample, index 0)."""
    def __init__(self, n=1):
        self.mast = {2.5: np.ones(n, bool)}
        self.mat = {(2.5, 2.5): np.ones((n, n), bool)}

    def ok(self, i_idx, h_i, j_idx, h_j):
        return np.ones(len(j_idx), bool)


def test_ranging_lowers_the_error_and_counts_updates():
    """The review's pnt test: ranging to a beacon (and peers) lowers the dead-reckoning error, and the update counts
    add up (range_updates = beacon_updates + peer_updates)."""
    tr = straight(T=60, N=40)
    tr.xy[:] = np.stack([np.linspace(150.0, 450.0, 40), np.full(40, 80.0)], axis=1)[None]
    los = _OpenSky()
    dr = PN.simulate(tr, ("dr",), seed=4)
    rg = PN.simulate(tr, ("dr", "ranging"), seed=4, los=los, beacon_idx=[0], beacon_xy=np.array([[0.0, 0.0]]))
    assert rg.counts["beacon_updates"] > 0 and rg.counts["peer_updates"] > 0
    assert rg.counts["range_updates"] == rg.counts["beacon_updates"] + rg.counts["peer_updates"]
    assert np.median(rg.err[-1]) < 0.5 * np.median(dr.err[-1])


def test_lans_with_a_nonzero_share():
    """LANS in 2030 (share 0.6): updates happen and the error falls below dead reckoning alone; in 2028 it does nothing."""
    tr = straight(T=24 * 60 // 60 * 2, N=30)
    dr = PN.simulate(tr, ("dr",), seed=5)
    ln = PN.simulate(tr, ("dr", "lans"), seed=5, params={"year": 2030})
    assert ln.counts["lans_updates"] > 0 and np.median(ln.err[-1]) < 0.5 * np.median(dr.err[-1])
    assert PN.simulate(tr, ("dr", "lans"), seed=5, params={"year": 2028}).counts["lans_updates"] == 0
