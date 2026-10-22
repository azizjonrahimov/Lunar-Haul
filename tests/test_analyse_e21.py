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


def test_check_rounds(tmp_path):
    """Round-2 rows must equal their round-1 twins in every round-1 column; a difference is reported."""
    r1 = pd.DataFrame({"cell": ["a", "a", "b"], "seed": [0, 1, 0], "x": [0.1 + 0.2, 2.0, np.nan], "run_s": [1, 2, 3]})
    r2 = r1.copy()
    r2["run_s"] = [9, 9, 9]
    r2["new_metric"] = 1.0
    r2 = pd.concat([r2, pd.DataFrame({"cell": ["c"], "seed": [0], "x": [5.0], "run_s": [1], "new_metric": [0.0]})])
    r1.to_csv(tmp_path / "E21a_comms_autonomy.csv", index=False)
    r2.to_csv(tmp_path / "E21a_comms_autonomy_r2.csv", index=False)
    res = A.check_rounds(str(tmp_path))["E21a_comms_autonomy.csv"]
    assert res["pairs"] == 3 and res["differing"] == {}                 # 0.30000000000000004 round-trips exactly
    r2.loc[1, "x"] = 2.0000000001
    r2.to_csv(tmp_path / "E21a_comms_autonomy_r2.csv", index=False)
    assert A.check_rounds(str(tmp_path))["E21a_comms_autonomy.csv"]["differing"] == {"x": 1}


# ---- round 2 (B-49) ----
def test_robust_stats():
    ref = pd.Series([10.0, 20.0, 40.0, 80.0])
    cell = ref * 2.0
    r = A.robust_stats(ref, cell)
    assert r["gm_ratio"] == pytest.approx(2.0) and r["gm_ratio_lo"] == pytest.approx(2.0)
    assert r["ref_median"] == 30.0 and r["median_diff"] == 30.0 and r["n_increase"] == 4
    assert r["wilcoxon_p"] == pytest.approx(stats.wilcoxon([10.0, 20.0, 40.0, 80.0]).pvalue)
    z = A.robust_stats(pd.Series([0.0, 1.0]), pd.Series([1.0, 2.0]))
    assert math.isnan(z["gm_ratio"])                                    # a zero: no log-ratio


def test_order_statistic_quantile_keeps_infinities():
    x = np.array([1.0, 2.0, 3.0, np.inf, np.inf])
    assert A._q(x, 0.975) == np.inf and A._q(x, 0.025) == 1.0 and A._q(np.array([np.nan]), 0.5) != A._q(x, 0.5)


def test_breakeven_r2_keeps_all_draws():
    df, curve = _breakeven_df()
    t, worth = A.breakeven_r2(df, boot=50)
    pe = dict(zip(t["option"], t["p_equiv"]))
    assert pe["+1 rover"] == pytest.approx(0.7) and math.isinf(pe["strategic step + 1 rover"])
    assert "p_equiv_law" not in t                                       # referee S5
    row = t[t.option == "strategic step + 1 rover"].iloc[0]
    assert row["share_beyond_full_coverage"] == 1.0 and row["ci95_hi_beyond_full_coverage"]
    assert worth["price_musd_per_0.1_coverage"] == pytest.approx(0.1 * A.ltv_musd_per_year() / 0.2)
    assert worth["price_ci95"][0] == pytest.approx(worth["price_ci95"][1])            # no seed noise in this curve
    assert worth["strategic_minus_rover"]["point"] == pytest.approx(0.2) and worth["strategic_minus_rover"]["share_positive"] == 1.0
    assert worth["share_draws_rover_buys_nothing"] == 0.0


def _year_df():
    rows = []
    for s in range(8):
        yr = 2028 + s % 4
        for comms, p in (("always", None), ("dte", 0.0)):
            v = 500.0 if comms == "always" else (100.0 if yr == 2028 else 400.0)
            rows.append(_row("A", comms, p, "supervised_strategic", s, delivered_t_in_year=v, start_year=yr))
    return A.prepare(pd.DataFrame(rows))


def test_year_table_and_blocked_interval():
    df = _year_df()
    y = A.year_table(df, ["delivered_t_in_year"])
    dte = y[(y.comms == "dte") & (y.mix == "supervised_strategic")]
    assert dte[dte.start_year == 2028]["flag"].iloc[0] and not dte[dte.start_year == 2029]["flag"].iloc[0]
    a = df[df.stage == "A"]
    b = A.year_blocked(A.select(a, comms="always", mix="supervised_strategic"),
                       A.select(a, p=0.0, mix="supervised_strategic"), "delivered_t_in_year")
    assert b["years"] == 4 and b["diff"] == pytest.approx(-175.0) and b["by_year"][2028] == -400.0
    assert b["ci_hi"] - b["ci_lo"] == pytest.approx(2 * stats.t.ppf(0.975, 3) * np.std([-400, -100, -100, -100], ddof=1) / 2)


def test_full_relay_check_and_cell_table():
    rows = []
    for s in range(4):
        for mix, bump in (("default", 0.0), ("teleop_4s", 1.0 if s == 2 else 0.0)):
            rows.append(_row("A", "always", None, mix, s, delay_prio1_p90_h=20.0))
            rows.append(_row("A", "dte+relay", 1.0, mix, s, delay_prio1_p90_h=20.0 + bump))
    df = A.prepare(pd.DataFrame(rows))
    chk = A.full_relay_vs_always(df, ["delay_prio1_p90_h"])
    assert chk["default"]["identical"] and not chk["teleop_4s"]["identical"]
    assert chk["teleop_4s"]["metrics"]["delay_prio1_p90_h"] == {"seeds_differing": 1, "max_abs_diff": 1.0}
    df["sensitivity"] = "none"
    ct = A.cell_table(df, ["delay_prio1_p90_h"])
    tele = ct[(ct.mix == "teleop_4s") & (ct.comms == "dte+relay")].iloc[0]
    v = np.array([20.0, 20.0, 21.0, 20.0])
    assert tele["delay_prio1_p90_h_ci95_t"] == pytest.approx(stats.t.ppf(0.975, 3) * v.std(ddof=1) / 2)
    assert tele["delay_prio1_p90_h_median"] == 20.0 and tele["n_seeds"] == 4


def test_split_summary():
    rows = []
    for s in range(4):
        for comms, p, bulk, landed in (("always", None, 500e3, 29e3), ("dte", 0.0, 300e3, 9.5e3)):
            rows.append(_row("A", comms, p, "supervised_strict", s, delivered_t_in_year=(bulk + landed + 800) / 1000,
                             delivered_bulk_kg_in_horizon=bulk, delivered_landed_kg_in_horizon=landed))
        r = _row("C", "dte", 0.0, "default", s, delivered_bulk_kg_in_horizon=296e3, delivered_landed_kg_in_horizon=0.0,
                 delivered_t_in_year=296.0)
        r["pad_standoff_km"] = 3.0
        rows.append(r)
    tmp = pd.DataFrame(rows)
    tmp["sensitivity"] = "none"
    df = A.prepare(tmp)
    for k in ("bulk", "landed"):
        df[f"delivered_{k}_t"] = df[f"delivered_{k}_kg_in_horizon"] / 1000.0
    df["delivered_return_t"] = df["delivered_t_in_year"] - df["delivered_bulk_t"] - df["delivered_landed_t"]
    sp = A.split_summary(df)
    assert {"origin": "CONSTR", "dest": "ISRU", "t_per_year": 200} in sp["bulk_flows_P2"]
    d = sp["dte_vs_always"]["supervised_strict"]
    assert d["delivered_landed_t"]["diff"] == pytest.approx(-19.5) and d["delivered_bulk_t"]["diff"] == pytest.approx(-200.0)
    assert d["delivered_return_t"]["diff"] == pytest.approx(0.0, abs=1e-9)
    assert sp["pads_3km_dte"]["default/any_part"] == {"landed_t_mean": 0.0, "seeds_with_landed_cargo": 0, "n_seeds": 4}
