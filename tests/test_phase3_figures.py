"""Phase-3 figure generator (experiments/phase3/make_figures_phase3.py) on a synthetic tiny results set: every figure
function builds its PNG and PDF from the synthetic tables, skips cleanly when its suite is absent, falls back to the
raw CSV when the summary table is missing, and the captions JSON names every figure id."""
import itertools
import json
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
import pytest

pytest.importorskip("matplotlib")
from experiments.phase3 import fit_law as fl  # noqa: E402
from experiments.phase3 import make_figures_phase3 as mf  # noqa: E402

MISS_REF = 2.9
MECHS = ("inhouse", "marketplace")
METRIC_COLS = ["delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "delivered_share", "delay_mean_h", "cost_per_kg_usd", "energy_kwh",
               "km_total", "utilisation", "jobs", "repositions", "km_reposition", "operator_hours", "plume_standdowns", "standdown_vehicle_h",
               "landing_miss_m_mean", "offpad_landings", "failed_landings", "cargo_lost_kg", "km_offpad_extra", "interventions",
               "intervention_h", "delivered_kg", "operator_cost_musd", "fleet_cost_musd", "unmet_operator_waits"]


def _metrics(rng, base_delay, offpad=0.0, keepout=0.0, standdown=0.0, standoff=1.0, teleop=0.0):
    d = base_delay * (1 + 0.1 * offpad + 0.05 * keepout * standdown + 0.1 * (standoff - 1) + 0.2 * teleop) * rng.lognormal(0, 0.15)
    return {"delay_prio1_mean_h": d, "delay_prio1_p90_h": 2.5 * d, "sl24_prio1": float(np.clip(1 - d / 40, 0, 1)),
            "delivered_share": 0.99, "delay_mean_h": 1.3 * d, "cost_per_kg_usd": 300 + 20 * standoff + rng.normal(0, 5),
            "energy_kwh": 500 + 150 * standoff + rng.normal(0, 20), "km_total": 700 + 100 * standoff + rng.normal(0, 30),
            "utilisation": 0.05 + rng.normal(0, 0.002), "jobs": 200.0, "repositions": 5.0 + keepout, "km_reposition": 10.0,
            "operator_hours": 300 + 1500 * teleop + rng.normal(0, 20), "plume_standdowns": 10 * keepout, "standdown_vehicle_h": 8 * keepout * (1 + standdown),
            "landing_miss_m_mean": 3.0, "offpad_landings": offpad, "failed_landings": 0.0, "cargo_lost_kg": 0.0, "km_offpad_extra": 2 * offpad,
            "interventions": 150.0, "intervention_h": 12.0, "delivered_kg": 5e5, "operator_cost_musd": 0.3 + 0.01 * standoff,
            "fleet_cost_musd": 90.0, "unmet_operator_waits": 0.0}


def _e17(rng, seeds=3):
    rows = []
    for (scen, nv), (miss, label), pr, D, mech, s in itertools.product((("P2-default", 6), ("P2-2-vehicles", 2)),
                                                                        ((MISS_REF, fl.CLASSICAL_LABEL), (100.0, "NASA 50-100 m / HLS 100 m 3-sigma"), (1500.0, "IM-1")),
                                                                        (25.0, 50.0), (0.5, 1.0, 3.0), MECHS, range(seeds)):
        offpad = 0 if miss < pr else int(rng.integers(3, 9))
        tag = {"exp": "E17", "scenario": scen, "phase": "P2", "n_vehicles": nv, "miss_level_m": miss, "miss_label": label,
               "sigma_scale": miss / MISS_REF, "pad_radius_m": pr, "pad_standoff_km": D, "keepout_km": 0.0, "standdown_h": 0.0,
               "night_fraction": 0.15, "mechanism": mech, "seed": s, "landings": 8}
        rows.append({**_metrics(rng, 6.0 if mech == "marketplace" else 10.0, offpad=offpad, standoff=D), **tag})
    df = pd.DataFrame(rows)
    df["cell"] = df[["scenario", "miss_label", "pad_radius_m", "pad_standoff_km", "mechanism"]].astype(str).agg(";".join, axis=1)
    return df


def _e18(rng, seeds=3):
    rows = []
    for (scen, nv), nf, D, mech, (R, T), s in itertools.product((("P2-default", 6), ("P2-2-vehicles", 2)), (0.15, 0.0), (1.0, 3.0), MECHS,
                                                                 ((0.0, 0.0), (0.5, 0.5), (0.5, 2.0), (2.0, 0.5), (2.0, 2.0)), range(seeds)):
        tag = {"exp": "E18", "scenario": scen, "phase": "P2", "n_vehicles": nv, "night_fraction": nf, "pad_standoff_km": D, "sigma_scale": 1.0,
               "keepout_km": R, "standdown_h": T, "mechanism": mech, "seed": s}
        rows.append({**_metrics(rng, 6.0 if mech == "marketplace" else 10.0, keepout=R, standdown=T, standoff=D), **tag})
    df = pd.DataFrame(rows)
    df["cell"] = df[["scenario", "night_fraction", "pad_standoff_km", "keepout_km", "standdown_h", "mechanism"]].astype(str).agg(";".join, axis=1)
    return df


def _e19(rng, seeds=3):
    rows = []
    for n, (aut, rtt), mech, s in itertools.product((2, 4), (("teleop", 4.0), ("teleop", 6.0), ("teleop", 8.0), ("supervised", 5.0), ("autonomous", 5.0)), MECHS, range(seeds)):
        tag = {"exp": "E19", "scenario": f"P2-{n}-vehicles", "phase": "P2", "n_vehicles": n, "autonomy": aut, "rtt_s": rtt, "pad_standoff_km": 1.0,
               "sigma_scale": 1.0, "mechanism": mech, "seed": s}
        rows.append({**_metrics(rng, (6.0 if mech == "marketplace" else 10.0) * 4 / n, teleop=(rtt / 4 if aut == "teleop" else 0.0)), **tag})
    df = pd.DataFrame(rows)
    df["cell"] = df[["scenario", "autonomy", "rtt_s", "mechanism"]].astype(str).agg(";".join, axis=1)
    return df


def _outcomes(rng, policy, cls, controller, n, pass_p, sigma):
    eps = []
    for i in range(n):
        ok = bool(rng.random() < pass_p)
        r = rng.normal(0, sigma, 2) if rng.random() > 0.05 else rng.normal(0, 25 * sigma, 2)
        eps.append({"cls": cls, "seed": 100000 + i, "miss_m": [float(r[0]), float(r[1])], "v_td": [0.01, 0.02, -1.0 if ok else -3.0],
                    "tilt_deg": 0.4, "ok": ok, "touchdown_ok": ok, "failure_kind": None if ok else str(rng.choice(["velocity", "sensor", "timeout"])),
                    "prop_used_kg": float(rng.normal(90, 10)), "t_below_30m_s": float(rng.normal(24, 3)), "t_flight_s": 120.0})
    return {"format": "lunarsim-landing-outcomes", "version": 1, "policy": policy, "controller": controller, "cls": cls, "n": n,
            "seed0": 100000, "sensor": True, "summary": {"n": n}, "episodes": eps}


def _e16_table():
    jsc = {0.0: 3.24, 4.0: 2.56, 6.0: 2.03, 8.0: 1.76}
    rows = []
    for aut, base in (("teleop", 3.28), ("supervised", 2.73), ("autonomous", 9.0)):
        for rtt in (0.0, 4.0, 6.0, 8.0):
            v = base * (jsc[rtt] / jsc[0.0] if aut == "teleop" else 1.0)
            rows.append({"check": "speed_made_good_vs_rtt_flat", "leg": "synthetic flat 2 km", "lighting": "none", "autonomy": aut, "rtt_s": rtt,
                         "length_m": 2000.0, "max_slope_deg": 0.0, "sim_kmh": v, "sim_kmh_mean_runs": v * 0.99, "sim_ratio_to_rtt0": v / base,
                         "ref_kmh": jsc[rtt] if aut == "teleop" else np.nan, "ref_ratio_to_rtt0": jsc[rtt] / jsc[0.0] if aut == "teleop" else np.nan,
                         "rel_err": v / jsc[rtt] - 1 if aut == "teleop" else np.nan, "interventions_lambda": 0.1, "stops": 10,
                         "note": "sim_kmh is the deterministic made-good with whole stops, sim_kmh_mean_runs the mean over 400 runs"})
    for rtt in (0.0, 4.0, 6.0, 8.0):
        rows.append({"check": "speed_made_good_vs_rtt_real_leg", "leg": "CONSTR->DEPOT", "lighting": "270", "autonomy": "teleop", "rtt_s": rtt,
                     "length_m": 662.3, "max_slope_deg": 5.8, "sim_kmh": 0.94 * 3.28 * jsc[rtt] / jsc[0.0], "ref_kmh": jsc[rtt], "note": "context"})
    for aut in ("teleop", "supervised", "autonomous"):
        for per in ("day", "night"):
            rows.append({"check": "psr_round_trip_energy", "leg": "BASE->PSR + PSR->BASE", "lighting": per, "autonomy": aut, "rtt_s": 4.0, "length_m": 8949.0,
                         "sim_kwh": 1.6 if per == "day" else 1.57, "ref_kwh_lo": 1.28, "ref_kwh_hi": 14.08, "in_band": True, "rover_mass_kg": 1600.0, "note": "Chen"})
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def synth(tmp_path_factory):
    """A tiny complete results set: raw suites, their fit_law tables, the E20 fit and siting tables, policies, table_E16."""
    root = tmp_path_factory.mktemp("phase3fig")
    res, out, pol = root / "results", root / "figures", root / "policies"
    for d in (res, out, pol):
        d.mkdir()
    rng = np.random.default_rng(7)
    for name, cls, ctrl, n, p, sig in (("classical_CLPS", "CLPS", "classical ZEM/ZEV", 40, 0.9, 2.0), ("lander_CLPS_x_s0", "CLPS", "policy", 30, 0.5, 4.0),
                                       ("classical_MK1", "MK1", "classical ZEM/ZEV", 20, 0.95, 2.0)):
        with open(pol / f"outcomes_{name}.json", "w", encoding="utf-8") as f:
            json.dump(_outcomes(rng, name, cls, ctrl, n, p, sig), f)
    with open(pol / "lander_CLPS_x_s0.json", "w", encoding="utf-8") as f:
        json.dump({"format": "lunarsim-policy", "id": "lander_CLPS_x_s0", "training": {"reward_variant": "baseline", "steps": 1000}}, f)
    _e16_table().to_csv(res / "table_E16.csv", index=False)
    e17, e18, e19 = _e17(rng), _e18(rng), _e19(rng)
    e17.to_csv(res / "E17_dispersion_standoff.csv", index=False)
    e18.to_csv(res / "E18_plume.csv", index=False)
    e19.to_csv(res / "E19_autonomy_fleet.csv", index=False)
    fl.table_e17(e17, B=20).to_csv(res / "table_E17.csv", index=False)
    fl.table_e18(e18, B=20).to_csv(res / "table_E18.csv", index=False)
    fl.table_e19(e19, B=20).to_csv(res / "table_E19.csv", index=False)
    both = pd.concat([e17, e18], ignore_index=True, sort=False)
    fit, table = fl.fit_law(both, B=10)
    fit["inputs"] = {"E17": str(res / "E17_dispersion_standoff.csv"), "E18": str(res / "E18_plume.csv"), "rows": int(len(both)), "seeds": 3}
    sit = fl.siting_table(e17, sites_path=str(root / "no_sites.json"), landings_per_year={"P2-default": 8.0, "P2-2-vehicles": 8.0})
    sit.to_csv(res / "table_E20_siting.csv", index=False)
    mins = fl.siting_minimum(sit)
    mins.to_csv(res / "table_E20_siting_min.csv", index=False)
    fit["siting"] = {"share_of_minima_by_standoff": fl.siting_summary(mins).to_dict("records")}
    table.to_csv(res / "table_E20.csv", index=False)
    with open(res / "E20_fit.json", "w", encoding="utf-8") as f:
        json.dump(fit, f)
    return {"res": str(res), "out": str(out), "policies": str(pol)}


def _png_width_in(path):
    import matplotlib.image as mimage
    return mimage.imread(path).shape[1] / 200.0


@pytest.mark.parametrize("fid", mf.FIG_IDS)
def test_each_figure_builds_from_synthetic_results(synth, fid):
    fn = dict(mf.FIGURES)[fid]
    info = fn(**synth)
    assert set(info) >= {"caption", "n", "ci", "flags", "files"}
    assert "n = " in info["caption"]                                   # n per cell (or the absence of replication) is stated
    for ext in ("png", "pdf"):
        p = os.path.join(synth["out"], f"{fid}.{ext}")
        assert os.path.exists(p) and os.path.getsize(p) > 1000, p
    assert _png_width_in(os.path.join(synth["out"], f"{fid}.png")) <= mf.MAX_WIDTH_IN * 1.05


def test_build_writes_captions_for_every_figure(synth):
    caps = mf.build(res=synth["res"], out=synth["out"], policies=synth["policies"])
    path = os.path.join(synth["out"], mf.CAPTIONS_FILE)
    assert os.path.exists(path)
    with open(path, encoding="utf-8") as f:
        saved = json.load(f)
    assert list(saved) == mf.FIG_IDS and set(caps) == set(mf.FIG_IDS)
    for fid, c in saved.items():
        assert c["status"] == "produced", (fid, c)
        assert "95 %" in c["caption"] or "none" in c["ci"], fid          # the CI convention is stated
        assert any(w in c["caption"] for w in ("Measured", "Spec", "Modelled", "Assumed")), fid   # a flag is stated
        assert c["files"] == [f"{fid}.png", f"{fid}.pdf"]


def test_only_selection_keeps_other_entries(synth):
    mf.build(res=synth["res"], out=synth["out"], policies=synth["policies"])
    caps = mf.build(only=["22"], res=synth["res"], out=synth["out"], policies=synth["policies"])
    assert caps["fig22_dispersion_standoff"]["status"] == "produced"
    assert caps["fig27_law"]["status"] == "produced"                       # kept from the previous run
    assert mf.select(["fig22", "fig27_law", "25"]) == ["fig22_dispersion_standoff", "fig27_law", "fig25_autonomy_fleet"]
    with pytest.raises(SystemExit):
        mf.select(["fig99"])


def test_missing_suites_are_skipped_not_crashed(tmp_path):
    res, out = tmp_path / "empty", tmp_path / "figs"
    res.mkdir()
    for fid, fn in mf.FIGURES:
        with pytest.raises(mf.Skip):
            fn(res=str(res), out=str(out), policies=str(tmp_path / "nopol"))
    caps = mf.build(res=str(res), out=str(out), policies=str(tmp_path / "nopol"))
    assert set(caps) == set(mf.FIG_IDS) and all(c["status"] == "skipped" and c["reason"] for c in caps.values())
    assert os.path.exists(out / mf.CAPTIONS_FILE) and not list(out.glob("*.png"))


def test_table_fallback_from_raw_csv(synth, tmp_path):
    res = tmp_path / "raw_only"
    shutil.copytree(synth["res"], res)
    for t in ("table_E17.csv", "table_E18.csv", "table_E19.csv"):
        os.remove(res / t)
    out = tmp_path / "figs"
    for fid in ("fig23_standoff", "fig24_plume", "fig25_autonomy_fleet"):
        info = dict(mf.FIGURES)[fid](res=str(res), out=str(out))
        assert os.path.exists(out / f"{fid}.png")
        assert "n = 3 seeds" in info["n"]


def test_missing_columns_skip_with_reason(synth, tmp_path):
    res = tmp_path / "nocols"
    shutil.copytree(synth["res"], res)
    t = pd.read_csv(res / "table_E17.csv")
    t.drop(columns=[c for c in t.columns if c.startswith("dCL_")]).to_csv(res / "table_E17.csv", index=False)
    with pytest.raises(mf.Skip, match="dCL"):
        mf.fig22_dispersion_standoff(res=str(res), out=str(tmp_path / "f"))
    pd.read_csv(res / "table_E16.csv").query("check != 'speed_made_good_vs_rtt_flat'").to_csv(res / "table_E16.csv", index=False)
    with pytest.raises(mf.Skip, match="speed_made_good_vs_rtt_flat"):
        mf.fig21_driving_validation(res=str(res), out=str(tmp_path / "f"))


def test_helpers():
    lo, hi = mf.wilson(469, 500)
    assert 0.91 < lo < 0.938 < hi < 0.96
    assert mf.wilson(0, 300)[0] == 0.0 and mf.wilson(0, 0) == (pytest.approx(np.nan, nan_ok=True), pytest.approx(np.nan, nan_ok=True))
    assert mf.n_text([2, 2, 2]) == "n = 2 seeds per cell"
    assert mf.n_text([2, 30, 30]) == "n = 2-30 seeds per cell (median 30)"
    assert mf.ordered_colors(3) == [mf.BATLOW[0], mf.BATLOW[3], mf.BATLOW[6]] and len(mf.ordered_colors(5)) == 5
    assert mf.scen_label("P3-default", 9) == "P3, 9 vehicles"
    assert mf.nearest([0.5, 1.0, 3.0], 1.2) == 1.0
