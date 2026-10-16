"""Phase-3 experiment runners (B-15): cell construction, the Pool job function, resumable CSVs, the law fit on
synthetic data, the pad-siting terms, and the E15 / E16 tables from the committed data files. No real multiprocessing."""
import itertools, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
import pytest

from experiments.phase3 import run_phase3 as rp
from experiments.phase3 import fit_law as fl

HAVE_DATA = (os.path.exists(os.path.join(ROOT, "data", "terrain", "connecting_ridge", "sites.json"))
             and os.path.exists(rp.DRIVING)
             and all(os.path.exists(os.path.join(rp.POLICIES, f"outcomes_classical_{c}.json")) for c in ("CLPS", "MK1", "LARGE")))
needs_data = pytest.mark.skipif(not HAVE_DATA, reason="terrain pack, driving table or classical outcome tables not present")


@pytest.fixture(autouse=True)
def in_root(monkeypatch):
    monkeypatch.chdir(ROOT)


# ---------------------------------------------------------------------------------------------- cells
def _keys(cells):
    return [rp.cell_key(t, mn) for (t, sc, mn, mf, kw) in cells]


def test_e17_cells():
    cells = rp.e17_cells()
    assert len(cells) == 7 * 3 * 5 * 2 * 4 == 840
    assert len(set(_keys(cells))) == len(cells)
    tags = pd.DataFrame([t for (t, *_) in cells])
    assert list(dict.fromkeys(tags["miss_label"])) == [fl.CLASSICAL_LABEL, "SLIM pre-divert", "ADD Rev C target",
                                                        "NASA 50-100 m / HLS 100 m 3-sigma", "Blue Ghost M1", "IM-2", "IM-1"]
    assert sorted(tags["miss_level_m"].unique())[1:] == [10.0, 50.0, 100.0, 118.0, 300.0, 1500.0]
    assert sorted(tags["pad_radius_m"].unique()) == [25.0, 50.0, 100.0]
    assert sorted(tags["pad_standoff_km"].unique()) == [0.5, 1.0, 2.0, 3.0, 5.0]
    assert set(tags["scenario"]) == {"P2-default", "P2-4-vehicles", "P2-2-vehicles", "P3-default"}
    assert set(tags["n_vehicles"]) == {6, 4, 2, 9}
    ref = rp.MISS_REF_M
    assert 2.0 < ref < 4.0
    for (t, sc, mn, mf, kw) in cells:
        assert sc.terrain == "connecting_ridge" and sc.autonomy_model == "driving-v1" and sc.plume is None
        assert sc.pad_standoff_km == rp.standoff_key(t["pad_standoff_km"])
        sig = 1.0 if t["miss_label"] == fl.CLASSICAL_LABEL else t["miss_level_m"] / ref
        assert t["sigma_scale"] == sig and (t["miss_label"] != fl.CLASSICAL_LABEL or t["miss_level_m"] == ref)
        assert sc.landing_model == {"policy": "classical", "sigma_scale": sig, "pad_radius_m": t["pad_radius_m"], "failure_policy": "lose"}
        assert mn in ("inhouse", "marketplace")
        if t["scenario"] == "P2-2-vehicles":
            assert len(sc.fleet) == 2 and sc.n_operators == 2


def test_e18_cells():
    cells = rp.e18_cells()
    assert len(cells) == 3 * 2 * 2 * 4 * (1 + 5 * 5) == 1248
    assert len(set(_keys(cells))) == len(cells)
    tags = pd.DataFrame([t for (t, *_) in cells])
    assert (tags[["keepout_km", "standdown_h"]].eq(0.0).all(axis=1)).sum() == 48          # the no-plume cells
    assert set(tags["night_fraction"]) == {0.15, 0.0} and set(tags["pad_standoff_km"]) == {1.0, 3.0}
    assert set(mn for (_, _, mn, *_) in cells) == {"inhouse", "pooled_greedy", "central_assign", "marketplace"}
    for (t, sc, mn, mf, kw) in cells:
        if t["keepout_km"] == 0.0:
            assert sc.plume is None
        else:
            assert sc.plume == {"keepout_km": t["keepout_km"], "standdown_h": t["standdown_h"], "shelter": "auto"}
        assert sc.night_fraction == t["night_fraction"] and sc.landing_model["sigma_scale"] == 1.0 and sc.landing_model["pad_radius_m"] == 50.0
        assert kw == ({"batch_h": 1.0} if mn == "central_assign" else {})


def test_e19_cells():
    cells = rp.e19_cells()
    assert len(cells) == 4 * 5 * 2 == 40
    assert len(set(_keys(cells))) == len(cells)
    for (t, sc, mn, mf, kw) in cells:
        assert len(sc.fleet) == t["n_vehicles"] and sc.n_operators == max(2, t["n_vehicles"] // 2)
        assert {v[2] for v in sc.fleet} == {t["autonomy"]}
        assert 2 * sc.one_way_latency_s + sc.ground_delay_s == t["rtt_s"]          # split_rtt is exact
        if t["autonomy"] == "teleop":
            assert t["rtt_s"] in (4.0, 6.0, 8.0)
        else:
            assert t["rtt_s"] == 5.0                                                # the phase default
        assert sc.pad_standoff_km == "1" and sc.landing_model["policy"] == "classical"


def test_standoff_key_matches_cli():
    from lunarsim.cli import _with_phase3
    import argparse
    for d in (0.5, 1, 1.0, 2, 3, 5):
        a = argparse.Namespace(terrain=None, pad_standoff=d, landing_model=None, plume=None, autonomy=None)
        assert rp.standoff_key(d) == _with_phase3(rp.LIB["P2-default"], a).pad_standoff_km


# ---------------------------------------------------------------------------------------------- the job
@needs_data
def test_job_runs_one_e17_and_one_e18_cell():
    c17 = next(c for c in rp.e17_cells() if c[0]["scenario"] == "P2-2-vehicles" and c[0]["miss_label"] == "IM-1"
               and c[0]["pad_radius_m"] == 25.0 and c[0]["pad_standoff_km"] == 5.0 and c[2] == "inhouse")
    row = rp._job((*c17, 0))
    assert row["seed"] == 0 and row["mechanism"] == "inhouse" and row["cell"] == rp.cell_key(c17[0], "inhouse")
    for k in ("delay_prio1_mean_h", "cost_per_kg_usd", "energy_kwh", "landing_miss_m_mean", "offpad_landings", "interventions",
              "plume_standdowns", "landings"):
        assert k in row
    assert row["miss_level_m"] == 1500.0 and row["pad_standoff_km"] == 5.0 and row["plume_standdowns"] == 0
    assert row["landings"] > 0 and 0 < row["offpad_landings"] <= row["landings"] and row["landing_miss_m_mean"] > 100.0
    c18 = next(c for c in rp.e18_cells() if c[0]["scenario"] == "P2-4-vehicles" and c[0]["keepout_km"] == 3.0
               and c[0]["standdown_h"] == 6.0 and c[0]["night_fraction"] == 0.0 and c[0]["pad_standoff_km"] == 1.0 and c[2] == "inhouse")
    row = rp._job((*c18, 0))
    assert row["keepout_km"] == 3.0 and row["standdown_h"] == 6.0 and row["plume_standdowns"] > 0 and row["standdown_vehicle_h"] > 0


# ---------------------------------------------------------------------------------------------- resumable CSV
def test_pending_jobs_and_append(tmp_path):
    cells = rp.e19_cells()[:3]
    path = str(tmp_path / "x.csv")
    jobs, n_done = rp.pending_jobs(path, cells, 2)
    assert n_done == 0 and len(jobs) == 6
    rows = [dict(a=1.0, b=2.0, seed=s, cell=rp.cell_key(cells[0][0], cells[0][2])) for s in (0, 1)]
    rp.append_rows(path, rows)
    rp.append_rows(path, [dict(a=3.0, b=4.0, seed=0, cell=rp.cell_key(cells[1][0], cells[1][2]))])
    jobs, n_done = rp.pending_jobs(path, cells, 2)
    assert n_done == 3 and len(jobs) == 3
    assert {(rp.cell_key(t, mn), s) for (t, sc, mn, mf, kw, s) in jobs} == {(rp.cell_key(cells[1][0], cells[1][2]), 1),
                                                                             (rp.cell_key(cells[2][0], cells[2][2]), 0),
                                                                             (rp.cell_key(cells[2][0], cells[2][2]), 1)}
    rp.append_rows(path, [dict(a=5.0, b=6.0, c=7.0, seed=1, cell="new")])         # a new column rewrites the file
    df = pd.read_csv(path)
    assert list(df.columns) == ["a", "b", "seed", "cell", "c"] and len(df) == 4 and df["c"].notna().sum() == 1


# ---------------------------------------------------------------------------------------------- the fit
MISS_REF = 2.9


def _synthetic(seeds=8, noise=0.01, rng_seed=1):
    rng = np.random.default_rng(rng_seed)
    util = {("A", "inhouse"): 0.05, ("A", "marketplace"): 0.04, ("B", "inhouse"): 0.2, ("B", "marketplace"): 0.15}
    rows = []
    for (scen, mech), u in util.items():
        for miss, pr, D, R, T in itertools.product((MISS_REF, 33.0, 300.0), (25.0, 50.0, 100.0), (0.5, 1.0, 3.0), (0.0, 1.0, 2.0), (0.0, 0.5, 2.0)):
            if (R == 0) != (T == 0) or (R > 0 and pr != 50.0) or (R > 0 and miss != MISS_REF):
                continue
            for s in range(seeds):
                offpad = 0 if miss < pr else int(rng.integers(1, 9))
                rows.append(dict(scenario=scen, phase="P2", n_vehicles=4, mechanism=mech, night_fraction=0.15, miss_level_m=miss,
                                 miss_label=fl.CLASSICAL_LABEL if miss == MISS_REF else f"m{miss:g}", sigma_scale=miss / MISS_REF, pad_radius_m=pr,
                                 pad_standoff_km=D, keepout_km=R, standdown_h=T, seed=s, utilisation=u + rng.normal(0, 1e-3),
                                 landings=8, offpad_landings=offpad, delivered_kg=1000.0, energy_kwh=100.0, cost_per_kg_usd=1.0,
                                 delay_prio1_p90_h=1.0, km_total=1.0, km_offpad_extra=0.0))
    df = pd.DataFrame(rows)
    truth = {"const": 1.0, "log_miss": 0.3, "standoff": 0.2, "keepout": 0.5, "standdown": 0.1, "util": 4.0, "offpad_share": 0.6,
             "pad_radius_m": -0.001, "log_miss:standoff": 0.05, "keepout:standdown": 0.07, "keepout:util": 1.5, "standdown:util": 0.8,
             "standoff:util": 2.0, "log_miss:util": -0.5, "mech_marketplace": -0.4}
    X, names = fl.design(df, miss_ref_m=MISS_REF)
    beta = np.array([truth.get(n, 0.0) for n in names])
    y = X @ beta + rng.normal(0, noise, len(df))
    return df, X, names, y, truth


def test_design_columns():
    df, X, names, y, truth = _synthetic(seeds=2)
    assert names == fl.TERMS + ["mech_marketplace", "mech_pooled_greedy", "mech_central_assign"]
    col = dict(zip(names, X.T))
    assert np.allclose(col["log_miss"], np.log(df["miss_level_m"]))
    assert np.allclose(col["offpad_share"], df["offpad_landings"] / df["landings"])
    assert np.allclose(col["pad_radius_m"], df["pad_radius_m"]) and np.allclose(col["standoff"], df["pad_standoff_km"])
    # rows without miss_level_m / landings fall back to sigma_scale x reference and to 0 off-pad share
    d2 = df.drop(columns=["miss_level_m", "landings", "offpad_landings"])
    X2, n2 = fl.design(d2, miss_ref_m=MISS_REF)
    assert np.allclose(X2[:, n2.index("log_miss")], np.log(df["sigma_scale"] * MISS_REF)) and (X2[:, n2.index("offpad_share")] == 0).all()


def test_fit_recovers_known_coefficients():
    df, X, names, y, truth = _synthetic()
    f = fl.fit_ols(X, y, df["seed"].to_numpy(), B=300)
    assert [names[j] for j in f["dropped"]] == ["night_fraction", "mech_pooled_greedy", "mech_central_assign"]
    assert f["r2"] > 0.999 and f["n_seeds"] == 8
    for j, c, lo, hi in zip(f["keep"], f["coef"], f["lo"], f["hi"]):
        t = truth.get(names[j], 0.0)
        assert abs(c - t) < 0.02, names[j]
        assert lo - 0.02 <= t <= hi + 0.02, names[j]
        assert lo <= c <= hi


def test_fit_law_tables_and_json_shape():
    df, X, names, y, truth = _synthetic(seeds=4)
    df["delay_prio1_mean_h"] = np.exp(y)
    df["sl24_prio1"] = 0.5
    fit, table = fl.fit_law(df, B=50)
    assert set(fit) == {"design", "pooled", "by_mechanism"} and set(fit["by_mechanism"]) == {"inhouse", "marketplace"}
    assert "log_delay_prio1_mean_h" in fit["pooled"] and "cost_per_kg_with_energy_usd_2000" in fit["pooled"]
    c = fit["pooled"]["log_delay_prio1_mean_h"]["coef"]
    assert abs(c["standoff"]["coef"] - 0.2) < 0.03 and abs(c["log_miss"]["coef"] - 0.3) < 0.03 and abs(c["offpad_share"]["coef"] - 0.6) < 0.05
    assert {"response", "subset", "term", "coef", "ci_lo", "ci_hi", "n", "n_seeds", "r2", "pct_per_unit"} <= set(table.columns)
    assert (table[table["subset"] == "pooled"].groupby("response").size() > 10).all()
    assert fit["design"]["regressors"] == names                                     # the design statement names every regressor


def test_paired_and_energy_cost():
    rows = []
    for D in (0.5, 1.0, 3.0):
        for s in range(5):
            rows.append(dict(scenario="A", phase="P2", n_vehicles=4, mechanism="inhouse", miss_level_m=2.9, miss_label=fl.CLASSICAL_LABEL, sigma_scale=1.0,
                             pad_radius_m=50.0, pad_standoff_km=D, seed=s, delay_prio1_mean_h=D * 2.0 + s, delay_prio1_p90_h=1.0, sl24_prio1=0.5,
                             cost_per_kg_usd=100.0, energy_kwh=50.0 * D, delivered_kg=1000.0, km_total=1.0, offpad_landings=0, km_offpad_extra=0.0, landings=8))
    df = pd.DataFrame(rows)
    df.loc[(df["pad_standoff_km"] == 3.0) & (df["seed"] == 4), "delay_prio1_mean_h"] = np.nan   # one missing year
    t = fl.paired(df, fl.E17_FACTORS, ["delay_prio1_mean_h", "energy_kwh"], {"pad_standoff_km": 1.0}, B=200)
    assert len(t) == 2 and set(t["pad_standoff_km"]) == {0.5, 3.0}            # the reference cell itself is not listed
    r = t.set_index("pad_standoff_km")
    assert math.isclose(r.loc[3.0, "d_delay_prio1_mean_h"], 4.0) and math.isclose(r.loc[0.5, "d_delay_prio1_mean_h"], -1.0)
    assert math.isclose(r.loc[3.0, "d_energy_kwh"], 100.0) and r.loc[3.0, "n_common"] == 5
    assert r.loc[3.0, "d_delay_prio1_mean_h_lo"] <= 4.0 <= r.loc[3.0, "d_delay_prio1_mean_h_hi"]
    e = fl.add_energy_cost(df)
    assert math.isclose(e.loc[0, "cost_per_kg_with_energy_usd_2000"], 100.0 + 2000 * 25.0 / 1000.0)
    assert (e["cost_per_kg_with_energy_usd_0"] == e["cost_per_kg_usd"]).all()
    tab = fl.table_e17(df, B=50)
    assert len(tab) == 3 and {"dD1_delay_prio1_mean_h", "cost_per_kg_with_energy_usd_2000_ci95", "offpad_share"} <= set(tab.columns)
    assert tab["dD1_delay_prio1_mean_h"].isna().sum() == 1                         # NaN for the reference row
    assert "dCL_delay_prio1_mean_h" not in tab.columns                             # only the classical level present: nothing to pair


# ---------------------------------------------------------------------------------------------- pad siting
def test_impacts_per_landing():
    assert math.isclose(fl.impacts_per_landing(1.0), 8.0) and math.isclose(fl.impacts_per_landing(5.0), 0.37) and math.isclose(fl.impacts_per_landing(10.0), 0.10)
    slope = (math.log(0.37) - math.log(8.0)) / 4.0
    assert math.isclose(fl.impacts_per_landing(0.5), math.exp(math.log(8.0) - 0.5 * slope))      # extrapolated with the 1-5 km slope
    assert math.isclose(fl.impacts_per_landing(3.0), math.exp(math.log(8.0) + 2.0 * slope))      # log-linear between the anchors
    vals = fl.impacts_per_landing(np.array([0.5, 1.0, 2.0, 3.0, 5.0, 10.0]))
    assert (np.diff(vals) < 0).all() and vals[0] > 8.0


@needs_data
def test_pad_los_from_sites_json():
    assert fl.pad_los_blocked(0.5) is False and fl.pad_los_blocked(1.0) is False
    assert fl.pad_los_blocked(2.0) and fl.pad_los_blocked(3.0) and fl.pad_los_blocked(5.0)
    assert fl.pad_los_blocked(7.0) is None


def test_siting_table_minimum(tmp_path):
    rows = []
    for D in (0.5, 1.0, 2.0, 5.0):
        for s in range(3):
            rows.append(dict(scenario="P2-default", phase="P2", n_vehicles=6, mechanism="marketplace", miss_level_m=2.9, miss_label=fl.CLASSICAL_LABEL,
                             sigma_scale=1.0, pad_radius_m=50.0, pad_standoff_km=D, seed=s, operator_cost_musd=0.05 + 0.01 * D, energy_kwh=400.0 * D,
                             delivered_kg=30000.0, fleet_cost_musd=14.0, cargo_lost_kg=0.0, offpad_landings=0, km_total=700.0 * D, delay_prio1_mean_h=5.0 + D))
    df = pd.DataFrame(rows)
    sites = tmp_path / "sites.json"
    sites.write_text('{"pad_details": {"0.5": {"PAD_A": {"los_to_base": "clear"}}, "1": {"PAD_A": {"los_to_base": "clear"}}, '
                     '"2": {"PAD_A": {"los_to_base": "blocked"}}, "5": {"PAD_A": {"los_to_base": "blocked"}}}}', encoding="utf-8")
    sit = fl.siting_table(df, sites_path=str(sites), landings_per_year={"P2-default": 8.0})
    assert len(sit) == 4 * len(fl.ENERGY_PRICES) * len(fl.PAD_COST_MUSD) * len(fl.DAMAGE_MUSD_PER_IMPACT)
    r = sit[(sit["energy_price_usd_per_kwh"] == 2000) & (sit["pad_case_usd_per_kg_transport"] == "100K") & (sit["damage_musd_per_impact"] == 1.0)].set_index("pad_standoff_km")
    assert math.isclose(r.loc[2.0, "hauling_musd"], 0.07 + 2000 * 800.0 / 1e6) and math.isclose(r.loc[2.0, "pad_musd_per_year"], 22.9)
    assert r.loc[2.0, "shield"] == 0.1 and r.loc[1.0, "shield"] == 1.0 and bool(r.loc[2.0, "pad_a_los_blocked"]) is True
    assert math.isclose(r.loc[1.0, "damage_musd"], 8.0 * 8.0 * 1.0 * 1.0) and math.isclose(r.loc[5.0, "damage_musd"], 8.0 * 0.37 * 0.1 * 1.0)
    assert math.isclose(r.loc[2.0, "total_musd"], r.loc[2.0, "hauling_musd"] + 22.9 + r.loc[2.0, "damage_musd"])
    assert r["min_cost"].sum() == 1
    mins = fl.siting_minimum(sit)
    assert len(mins) == len(fl.ENERGY_PRICES) * len(fl.PAD_COST_MUSD) * len(fl.DAMAGE_MUSD_PER_IMPACT)
    by_dc = mins.groupby("damage_musd_per_impact")["pad_standoff_km"].unique()
    assert set(by_dc[10.0]) == {5.0}                                                # heavy damage pushes the pad out
    no_damage = fl.siting_table(df, sites_path=str(sites), landings_per_year={"P2-default": 8.0}, damage_costs=(0.0,))
    assert (fl.siting_minimum(no_damage)["pad_standoff_km"] == 0.5).all()           # without damage, hauling alone: nearest pad
    summ = fl.siting_summary(mins)
    assert {"energy_price_usd_per_kwh", "damage_musd_per_impact"} <= set(summ.columns) and np.allclose(summ.filter(like="share_min_at").sum(axis=1), 1.0)


# ---------------------------------------------------------------------------------------------- E15 / E16 from the committed files
@needs_data
def test_e15_table_from_committed_outcomes(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "RESULTS", str(tmp_path))
    t = rp.e15()
    assert os.path.exists(tmp_path / "table_E15.csv")
    cl = t[t["kind"] == "classical"].set_index("cls")
    assert {"CLPS", "MK1", "LARGE"} <= set(cl.index)
    assert math.isclose(cl.loc["CLPS", "miss_mean_m"], rp.MISS_REF_M, rel_tol=1e-6)      # the E17 miss reference is this table's mean
    assert ((t["pass_rate"] >= 0) & (t["pass_rate"] <= 1)).all() and (t["n"] > 0).all()
    fails = t[[f"fail_{k}" for k in rp.FAIL_KINDS]].sum(axis=1)
    assert (fails <= t["n"]).all()
    assert (t["miss_p90_m"] >= t["miss_p50_m"]).all() and (t["miss_max_m"] >= t["miss_p90_m"]).all()
    learned = t[t["kind"] == "learned"]
    for _, r in learned.iterrows():
        assert r["vs"] == f"classical_{r['cls']}"
        assert math.isclose(r["d_pass_rate"], r["pass_rate"] - cl.loc[r["cls"], "pass_rate"])
        assert r["d_pass_rate_ci95"] > 0


def test_e16_flat_leg_rows_match_jsc():
    pytest.importorskip("PIL")
    rows = pd.DataFrame(rp.e16_flat_rows())
    tel = rows[rows["autonomy"] == "teleop"].set_index("rtt_s")
    assert list(tel.index) == [0.0, 4.0, 6.0, 8.0] and (tel["max_slope_deg"] == 0).all()
    for rtt, jsc in rp.JSC_TELEOP_KMH.items():
        assert tel.loc[rtt, "sim_kmh"] == pytest.approx(jsc, rel=0.02), rtt           # as tests/test_rover.py: whole stops only
        assert tel.loc[rtt, "sim_kmh_mean_runs"] == pytest.approx(jsc, rel=0.05)
    assert (tel["sim_kmh"].diff().dropna() < 0).all() and set(rows["autonomy"]) == {"teleop", "supervised", "autonomous"}


@needs_data
def test_e16_table_from_committed_driving_table(tmp_path, monkeypatch):
    monkeypatch.setattr(rp, "RESULTS", str(tmp_path))
    t = rp.e16()
    raw = pd.read_csv(tmp_path / "E16_driving_validation.csv")
    assert {"leg", "autonomy", "rtt_s", "lighting", "speed_made_good_kmh", "energy_kwh_mean", "interventions_lambda"} <= set(raw.columns)
    assert raw["leg"].nunique() > 100 and (raw["speed_made_good_kmh"] > 0).all()
    flat = t[(t["check"] == "speed_made_good_vs_rtt_flat") & (t["autonomy"] == "teleop")].set_index("rtt_s")
    assert list(flat.index) == [0.0, 4.0, 6.0, 8.0] and (flat["rel_err"].abs() < 0.02).all()
    sp = t[(t["check"] == "speed_made_good_vs_rtt_real_leg") & (t["autonomy"] == "teleop")].set_index("rtt_s")
    assert list(sp.index) == [0.0, 4.0, 6.0, 8.0]
    assert [round(v, 2) for v in sp["ref_kmh"]] == [3.24, 2.56, 2.03, 1.76]
    assert sp["leg"].nunique() == 1 and (sp["length_m"] >= rp.MIN_FLAT_LEG_M).all() and (sp["max_slope_deg"] > 0).all()
    assert (sp["sim_kmh"].diff().dropna() < 0).all()                              # slower with more latency
    assert (sp["rel_err"].abs() < 0.25).all()
    en = t[t["check"] == "psr_round_trip_energy"]
    assert set(en["autonomy"].dropna()) == {"teleop", "supervised", "autonomous"} and set(en["lighting"]) == {"day", "night"}
    assert np.allclose(en["ref_kwh_lo"], 0.4 * en["rover_mass_kg"] / 500.0) and (en["sim_kwh"] > 0).all()
    assert en["note"].str.contains("Chen").all()
