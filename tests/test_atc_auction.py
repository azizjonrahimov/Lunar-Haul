"""B-73: the decentralised auction and cross-owner team lifts (lunarsim/atc/auction.py)."""
import json, math, os, sys, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim import Simulation, dispatch
from lunarsim.atc import auction as A, regimes as G
from lunarsim.config import load_scenario

L10 = os.path.join(ROOT, "data", "scenarios", "p5", "p5-3eq-L10-T25.json")
BOUNDS = os.path.join(ROOT, "results", "ATC_auction_bounds.json")


def sim_run(mech, kw=None, seed=2, scen=L10):
    sim = Simulation(load_scenario(scen), mech, seed=seed, mech_kwargs=dict(kw or {}, trace=True))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        s = sim.run()
    return sim, s


def test_perfect_links_depth_one_equal_the_pooled_marketplace():
    a, ra = sim_run(dispatch.marketplace)
    b, rb = sim_run(G.mechanism("C_AUCTION"), {"radio": "perfect", "base_mtbf_h": math.inf, "depth": 1, "loss": 0.0})
    assert a.trace == b.trace
    assert all(rb[k] == v for k, v in ra.items() if not (isinstance(v, float) and math.isnan(v)))


def test_lossy_deep_auction_never_assigns_an_item_twice():
    sim, s = sim_run(G.mechanism("C_AUCTION"), {"loss": 0.4, "depth": 5})
    assert s["atc_conflicts"] > 0 and s["atc_claims_won"] > 0
    picked = [c for c in sim.all_cargo if c.t_picked is not None]
    assert len({id(c) for c in picked}) == len(picked)                    # each item started once
    assert sim.metrics.ready_kg == pytest.approx(sim.metrics.delivered_kg + sim.metrics.stranded_kg
                                                 + sim.metrics.backlog_kg, rel=1e-12)


def test_team_lifts_commit_timeout_and_scope():
    _, s = sim_run(G.mechanism("C_AUCTION"), {"loss": 0.4, "commit": False, "timeout_h": 1.5})
    assert s["atc_failed_meetings"] > 0
    assert s["atc_meeting_wait_h"] == pytest.approx(1.5 * s["atc_failed_meetings"])
    assert s["atc_team_no_agreement"] == 0                                 # nothing to agree on without commit
    _, c = sim_run(G.mechanism("C_AUCTION"), {"loss": 0.4, "commit": True})
    assert c["atc_team_no_agreement"] > 0
    sim, _ = sim_run(G.mechanism("C_AUCTION"), {"team_scope": "same_owner"})
    owner = {v.id: v.owner for v in sim.vehicles}
    teams = [r for r in sim.trace if r["kind"] == "team"]
    assert all(len({owner[i] for i in r["team"]}) == 1 for r in teams)
    sim2, _ = sim_run(G.mechanism("C_AUCTION"))
    assert any(len({owner[i] for i in r["team"]}) == 2 for r in sim2.trace if r["kind"] == "team")


def test_small_instance_algorithms():
    pairs, tot = A.ssi_assign(np.array([[1.0, 2.0], [1.5, 10.0]]))
    assert pairs == [(0, 0), (1, 1)] and tot == 11.0                      # greedy, not the optimum (3.5)
    R = np.array([[0.0, 0.0], [10.0, 10.0]])
    I = np.array([[1.0, 0.0], [2.0, 0.0], [9.0, 10.0]])
    b, s = A.cbba_lite(R, I, depth=2, reward=12.0)
    assert sorted(b[0]) == [0, 1] and b[1] == [2] and all(len(x) <= 2 for x in b.values())
    assert s == pytest.approx(A.optimum_score(R, I, 2, 12.0))


def test_bounds_on_random_instances():
    r = A.bounds_check(40, seed=5)
    assert r["items_assigned_twice"] == 0
    assert r["cbba_lite_vs_optimum"]["1"]["score_share_min"] >= 0.5        # greedy matching: 1/2 guaranteed
    if os.path.isfile(BOUNDS):
        d = json.load(open(BOUNDS, encoding="utf-8"))
        assert d["instances"] == 200 and d["items_assigned_twice"] == 0
        assert d["ssi_vs_hungarian"]["ratio_max"] <= 2.0 and not d["ssi_vs_hungarian"]["above_factor_2"]
