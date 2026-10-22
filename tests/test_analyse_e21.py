"""E21 analysis (B-43, experiments/phase4/analyse_e21.py) on synthetic tables: paired CIs, the law fit, the
break-even inversion, operator compression and the throughput bound."""
import importlib.util, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
import pytest
from scipy import stats

_spec = importlib.util.spec_from_file_location("analyse_e21", os.path.join(ROOT, "experiments", "phase4", "analyse_e21.py"))
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.8, 0.9, 1.0]


def _row(stage, comms, p, mix, seed, policy="strict", extra=0, mast="none", **m):
    base = {"stage": stage, "comms": comms, "coverage": p if comms == "dte+relay" else np.nan, "mix": mix, "policy": policy,
            "extra_rovers": extra, "mast": mast, "pad_standoff_km": 1.0, "criterion": "any_part", "defer_wait_h": 24.0,
            "seed": seed, "n_operators": 3, "operator_hours": 438.0, "operator_peak_demand": 2.0,
            "delivered_t_in_year": 500.0, "delay_prio1_p90_h": 20.0, "delay_prio1_mean_h": 8.0, "sl24_prio1": 0.9,
            "blackout_wait_vehicle_h": 0.0}
    base.update(m)
    return base


def test_paired_ci_is_student_t_on_matched_seeds():
    rng = np.random.default_rng(0)
    ref = pd.DataFrame({"seed": range(12), "x": rng.normal(10, 2, 12)})
    d = rng.normal(3, 1, 12)
    cell = pd.DataFrame({"seed": range(12), "x": ref["x"] + d})
    cell.loc[5, "x"] = np.nan                                   # a seed without a value drops out of the pair
    extra = pd.DataFrame({"seed": [99], "x": [1e6]})            # a seed the reference lacks is ignored
    r = A.paired(ref, pd.concat([cell, extra]), "x")
    dd = np.delete(d, 5)
    h = stats.t.ppf(0.975, 10) * dd.std(ddof=1) / math.sqrt(11)
    assert r["n"] == 11 and r["diff"] == pytest.approx(dd.mean()) and r["ci_hi"] - r["diff"] == pytest.approx(h)
    assert r["rel_pct"] == pytest.approx(100 * dd.mean() / np.delete(ref["x"].to_numpy(), 5).mean())


@pytest.mark.parametrize("form,theta", [("hyperbolic", (12.0, 4.0, 0.03)), ("exponential", (15.0, 300.0, 9.0)),
                                        ("power", (18.0, 0.04, 0.9))])
def test_law_inversion_is_exact(form, theta):
    f, _ = A.FORMS[form]
    for p in (0.0, 0.25, 0.7, 1.0):
        assert A.invert(form, theta, float(f(p, *theta))) == pytest.approx(p, abs=1e-9)
    p2 = A.coverage_for(form, theta, 2.0)
    assert float(f(p2, *theta)) == pytest.approx(2.0 * float(f(1.0, *theta)), rel=1e-9) or p2 == 0.0


def _synthetic_curve(form, theta, seeds=20, noise=0.03, seed=1):
    f, _ = A.FORMS[form]
    rng = np.random.default_rng(seed)
    P = np.array(GRID)
    Y = np.array([f(P, *theta) * np.exp(rng.normal(0, noise, len(P))) for _ in range(seeds)])
    return P, Y


@pytest.mark.parametrize("form,theta,other", [("hyperbolic", (12.0, 4.0, 0.03), "exponential"),
                                              ("exponential", (15.0, 300.0, 9.0), "hyperbolic")])
def test_law_fit_recovers_parameters_and_cv_picks_the_true_form(form, theta, other):
    P, Y = _synthetic_curve(form, theta)
    th = A.fit_form(form, P, Y.mean(axis=0))
    assert th == pytest.approx(theta, rel=0.15)
    assert A.cv_rmse(form, P, Y) < A.cv_rmse(other, P, Y)
    r = A.law(P, Y, boot=40)
    assert r["form"] in (form, "power") and r["n_seeds"] == 20
    lo, hi = r["ci95"]["f1"]
    f, _ = A.FORMS[form]
    assert lo <= float(f(1.0, *theta)) * 1.02 and hi >= float(f(1.0, *theta)) * 0.98


def test_mono_inverse():
    P = [0.0, 0.5, 1.0]
    m = [100.0, 10.0, 1.0]
    assert A.mono_inverse(P, m, 10.0) == pytest.approx(0.5)
    assert A.mono_inverse(P, m, math.sqrt(10.0)) == pytest.approx(0.75)          # log-linear between grid points
    assert A.mono_inverse(P, m, 200.0) == 0.0 and math.isinf(A.mono_inverse(P, m, 0.5))
    assert A.mono_inverse([0.0, 0.5, 1.0], [100.0, 5.0, 8.0], 5.0) == pytest.approx(0.5)   # envelope of a bump


def _breakeven_df(seeds=20):
    """Strict curve 100 e^(-3p) exactly (log-linear, so interpolation is exact); stage B options at known p."""
    curve = lambda p: 100.0 * math.exp(-3.0 * p)
    rows = []
    for s in range(seeds):
        for p in GRID:
            rows.append(_row("A", "dte" if p == 0 else "dte+relay", p, "supervised_strict", s, delay_prio1_p90_h=curve(p)))
        for pol, extra, p_like in (("strict", 0, 0.5), ("strict", 1, 0.7), ("strict", 2, 0.75), ("strict", 3, 0.6),
                                   ("strategic", 0, 0.9), ("strategic", 1, 1.3)):
            rows.append(_row("B", "dte+relay", 0.5, "supervised_strict", s, policy=pol, extra=extra,
                             delay_prio1_p90_h=curve(p_like)))
    return A.prepare(pd.DataFrame(rows)), curve


def test_breakeven_inverts_the_strict_curve():
    df, curve = _breakeven_df()
    t, worth = A.breakeven(df, "exponential", boot=30)
    pe = dict(zip(t["option"], t["p_equiv"]))
    assert pe["+1 rover"] == pytest.approx(0.7) and pe["+2 rovers"] == pytest.approx(0.75)
    assert pe["+3 rovers"] == pytest.approx(0.6) and pe["strategic step"] == pytest.approx(0.9)
    assert math.isinf(pe["strategic step + 1 rover"])                            # beats full coverage
    assert t.loc[t.option == "strategic step + 1 rover", "share_beyond_full_coverage"].iloc[0] == 1.0
    assert worth["base"]["p90"] == pytest.approx(curve(0.5)) == pytest.approx(worth["base"]["cell_pb"])
    assert worth["delta_p_one_ltv"] == pytest.approx(0.2)
    assert worth["musd_per_year_per_0.1_coverage"] == pytest.approx(0.1 * A.ltv_musd_per_year() / 0.2)
    law = dict(zip(t["option"], t["p_equiv_law"]))
    assert law["+1 rover"] == pytest.approx(0.7, abs=0.02)                      # the exponential law is exact here


def test_effects_families():
    rows = []
    for s in range(6):
        for mix in ("supervised_strict", "supervised_strategic", "supervised_strategic+avoid"):
            rows.append(_row("A", "always", None, mix, s))
            rows.append(_row("A", "dte", 0.0, mix, s, delivered_t_in_year=300.0 + s))
            rows.append(_row("A", "dte+relay", 0.5, mix, s, delivered_t_in_year=530.0))
        for extra in (0, 1):
            for mast in ("none", "BASE 10 m"):
                rows.append(_row("B", "dte", 0.0, "supervised_strict", s, extra=extra, mast=mast,
                                 delivered_t_in_year=300.0 + 2 * extra))
    e = A.effects(A.prepare(pd.DataFrame(rows)))
    d = e[(e.family == "dte_vs_always") & (e.mix == "supervised_strict") & (e.metric == "delivered_t_in_year")].iloc[0]
    assert d["diff"] == pytest.approx(-197.5) and d["n"] == 6 and d["ci_excludes_0"]
    r = e[(e.family == "rovers_vs_0") & (e.metric == "delivered_t_in_year")].iloc[0]
    assert r["diff"] == pytest.approx(2.0) and r["cell"] == "+1 rovers"
    assert set(e.family) == {"dte_vs_always", "relay_vs_always", "policy_vs_strict", "rovers_vs_0", "mast_vs_none"}


def test_operator_compression_against_full_relay():
    rows = []
    for s in range(5):
        rows.append(_row("A", "always", None, "teleop_4s", s, operator_peak_demand=3.0))
        rows.append(_row("A", "dte+relay", 1.0, "teleop_4s", s, operator_peak_demand=3.0))
        rows.append(_row("A", "dte+relay", 0.1, "teleop_4s", s, operator_peak_demand=5.0 + 0.1 * s))
    o = A.operator_demand(A.prepare(pd.DataFrame(rows)), mixes=("teleop_4s",))
    low = o[o.p == 0.1].iloc[0]
    assert low["over_staffing"] and low["seeds_over_staffing"] == 5
    assert low["peak_minus_full_relay"] == pytest.approx(2.2)
    assert low["peak_to_mean"] == pytest.approx((5.2) / (438.0 / 8760.0))
    assert not o[o.p == 1.0].iloc[0]["over_staffing"]


def test_throughput_bound():
    cols = ["id", "owner", "mass_kg", "origin", "dest", "t_ready", "t_picked", "t_delivered", "priority", "cls", "stranded", "lost"]
    cargo = [[1, "N", 1000, "CONSTR", "ISRU", 10.0, None, 20.0, 3, "bulk", 0, 0],
             [2, "N", 500, "PAD_A", "BASE", 5.0, None, 9000.0, 1, "x", 0, 0],         # delivered after the year
             [3, "N", 200, "PAD_A", "BASE", 9000.0, None, None, 1, "x", 0, 0]]        # ready after the year
    d = A.demand_by_dest(cargo, cols)
    assert d["ISRU"] == {"ready_kg": 1000.0, "delivered_kg": 1000.0} and d["BASE"] == {"ready_kg": 500.0, "delivered_kg": 0.0}
    dem = pd.DataFrame([{"seed": s, "run": run, "dest": dest, "ready_kg": rk, "delivered_kg": dk}
                        for s in range(4)
                        for run, dest, rk, dk in (("always", "ISRU", 200e3, 200e3), ("always", "BASE", 300e3, 300e3),
                                                  ("dte", "ISRU", 200e3, 0.0), ("dte", "BASE", 300e3, 290e3 - 1e3 * s))])
    tb = A.throughput_bound(dem, ["ISRU"])
    assert tb["bound_ready_t"]["mean"] == pytest.approx(200.0) and tb["lost_at_never_linked_t"]["mean"] == pytest.approx(200.0)
    assert tb["gap_t"]["mean"] == pytest.approx(211.5) and tb["gap_elsewhere_t"]["mean"] == pytest.approx(11.5)
    assert tb["dte_delivered_to_never_linked_t"]["mean"] == 0.0


def test_strict_operator_family_and_demand():
    """Stage A2 (strict operators) is paired with its Stage A twin; lenient cells count no operator waits."""
    rows = []
    for s in range(5):
        for p in (0.5, 1.0):
            rows.append(_row("A", "dte+relay", p, "teleop_4s", s, operator_peak_demand=5.0 if p == 0.5 else 3.4,
                             delay_prio1_p90_h=40.0))
            rows.append(_row("A2", "dte+relay", p, "teleop_4s", s, operator_peak_demand=3.0,
                             delay_prio1_p90_h=41.0 + s, operator_wait_vehicle_h=10.0 * (p == 0.5)))
        rows.append(_row("A", "always", None, "teleop_4s", s, operator_peak_demand=3.0))
    df = A.prepare(pd.DataFrame(rows))
    assert (df.loc[df.stage == "A", "operator_wait_vehicle_h"] == 0).all()
    e = A.effects(df)
    st = e[e.family == "strict_vs_lenient"]
    pk = st[(st.metric == "operator_peak_demand") & (st.p == 0.5)].iloc[0]
    assert pk["diff"] == pytest.approx(-2.0) and pk["n"] == 5
    w = st[(st.metric == "operator_wait_vehicle_h") & (st.p == 0.5)].iloc[0]
    assert w["diff"] == pytest.approx(10.0)
    d = st[(st.metric == "delay_prio1_p90_h") & (st.p == 0.5)].iloc[0]
    assert d["diff"] == pytest.approx(3.0)
    o = A.operator_demand(df, mixes=("teleop_4s",))
    assert set(o["operators"]) == {"lenient", "strict"}
    assert not o[o.operators == "strict"]["over_staffing"].any()
