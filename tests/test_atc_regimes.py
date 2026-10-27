"""B-72: decision regimes, messages and positions (lunarsim/atc/regimes.py, messages.py); the degenerate checks."""
import math, os, sys, warnings
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim import Simulation, dispatch
from lunarsim.atc import regimes as G
from lunarsim.atc.messages import Channel
from lunarsim.config import load_scenario

SCEN = os.path.join(ROOT, "data", "scenarios", "p5", "p5-3eq-L10-T10.json")


def sim_run(mech, kw=None, seed=2, scen=SCEN):
    sc = load_scenario(scen)
    sim = Simulation(sc, mech, seed=seed, mech_kwargs=dict(kw or {}, trace=True))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        s = sim.run()
    return sim, s


def same_run(a, b):
    sa, ra = a
    sb, rb = b
    assert sa.trace == sb.trace                                   # identical event trace
    for k, v in ra.items():                                       # and identical engine summary
        if k.startswith("atc_") or k not in rb:                   # the regime's own columns
            continue
        assert rb[k] == v or (isinstance(v, float) and math.isnan(v) and math.isnan(rb[k])), k


# ---------------------------------------------------------------------------------------- degenerate checks
def test_b_earth_full_coverage_equals_pooled_marketplace():
    same_run(sim_run(dispatch.marketplace), sim_run(G.mechanism("B_EARTH"), {"coverage": 1.0}))


def test_a_earth_full_coverage_no_hand_delay_equals_inhouse():
    same_run(sim_run(dispatch.inhouse), sim_run(G.mechanism("A_EARTH"), {"coverage": 1.0, "t_hand": 0.0}))


def test_c_leader_perfect_radio_equals_oracle():
    o = sim_run(G.mechanism("O_ORACLE"))
    same_run(sim_run(dispatch.marketplace), o)
    same_run(o, sim_run(G.mechanism("C_LEADER"), {"radio": "perfect", "base_mtbf_h": math.inf}))


# ---------------------------------------------------------------------------------------- Earth gating
@pytest.mark.parametrize("year", [2028, 2038])
def test_b_earth_strict_assigns_only_while_base_is_linked(year):
    sim, s = sim_run(G.mechanism("B_EARTH"), {"start_year": year})
    st = sim.atc
    jobs = [r for r in sim.trace if r["kind"] != "reposition"]
    assert jobs and all(st.earth.next_change(r["t0"])[0] for r in jobs)
    assert 0.3 < s["atc_decider_down_share"] < 0.6
    assert s["atc_blackouts"] == len(st.aos) > 5


def test_plan_ahead_works_in_the_dark_and_relay_shortens_the_dark():
    sim, s = sim_run(G.mechanism("B_EARTH"), {"fallback": "plan_ahead"})
    dark = [r for r in sim.trace if r["kind"] in ("queue", "standing")]
    assert dark and not any(sim.atc.earth.next_change(r["t0"])[0] for r in dark)
    _, r = sim_run(G.mechanism("B_EARTH_RELAY"), {"coverage": 0.8})
    assert r["atc_decider_down_share"] < 0.5 * s["atc_decider_down_share"]


def test_a_earth_settles_cross_owner_apron_conflicts_by_hand():
    _, s = sim_run(G.mechanism("A_EARTH"), {"t_hand": 2.0}, scen=SCEN.replace("L10", "L30"))
    assert s["team_lifts"] == 0
    assert s["atc_hand_conflicts"] > 0 and s["atc_hand_wait_h"] >= 2.0 * s["atc_hand_conflicts"] - 1e-9


# ---------------------------------------------------------------------------------------- messages
def test_bernoulli_and_burst_loss_rates():
    ch = Channel(0.25, "bernoulli", rng=np.random.default_rng(1))
    ok = sum(ch.send(1)[0] for _ in range(40000))
    assert abs(1 - ok / 40000 - 0.25) < 0.01
    assert ch.send(3)[1] in (0.0, pytest.approx(0.03))                    # 10 ms a hop
    b = Channel(0.25, "burst", rng=np.random.default_rng(2))
    res = np.array([b.send(1)[0] for _ in range(200000)])
    assert abs(1 - res.mean() - 0.25) < 0.02
    runs = np.diff(np.flatnonzero(np.diff(np.r_[1, res.astype(int), 1]) != 0))[::2]   # lengths of loss runs
    assert 8 < runs.mean() < 12                                           # mean burst ~10 messages
    assert Channel(0.4).send(0) == (True, 0.0)


# ---------------------------------------------------------------------------------------- positions and leader
def test_positions_follow_the_committed_legs():
    sim, _ = sim_run(G.mechanism("C_LEADER"))
    st = sim.atc
    v = sim.vehicles[1]
    segs = [["BASE", "ISRU", 10.0, 12.0, 0.0], ["ISRU", "ISRU", 12.0, 13.0, 0.0]]
    st.plans[v.id] = segs
    ids = st.leg_ids("BASE", "ISRU")
    assert st.position(v, 10.0) == ids[0] and st.position(v, 11.99) == ids[-1]
    assert st.position(v, 11.0) in ids and st.position(v, 12.5) == st.site_index("ISRU")


def test_leader_failures_and_rally():
    sim, s = sim_run(G.mechanism("C_LEADER"), {"base_mtbf_h": 300.0})
    st = sim.atc
    assert s["atc_base_failures"] == len(st.base_down) > 10
    assert s["atc_decider_down_share"] == pytest.approx(sum(min(0.5, b - a) for a, b in st.base_down) / st.H)
    a, b = st.base_down[0]
    assert st.leader_state(a + 0.1) == "none" and st.leader_state(a + 0.6) == "robot" and st.leader_state(b + 1e-6) == "base"
    assert "ISRU" not in st.covered_sites(sim, 2.5) and "DEPOT" in st.covered_sites(sim, 2.5)
    assert s["atc_rallies"] > 0
    _, off = sim_run(G.mechanism("C_LEADER"), {"rally": False})
    assert off["delivered_kg"] < 0.5 * s["delivered_kg"]                  # without the lost-link rule robots strand


def test_backlog_is_recorded_at_every_blackout_end():
    sim, s = sim_run(G.mechanism("O_ORACLE"))
    assert len(sim.atc.backlog_at_aos) == len(sim.atc.aos) and s["atc_backlog_end_blackout_t_max"] >= 0


def test_unknown_regime_and_bad_settings():
    with pytest.raises(ValueError):
        G.mechanism("Z_NONE")
    with pytest.raises(ValueError):
        sim_run(G.mechanism("B_EARTH_RELAY"), {})                          # needs a coverage
