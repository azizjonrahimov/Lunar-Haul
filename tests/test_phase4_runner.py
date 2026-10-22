"""E21 runner (B-42, experiments/phase4/run_phase4.py): cells, a 2 x 2 smoke run, resumability, knee and break-even."""
import math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
import pytest

from experiments.phase4 import run_phase4 as R

LINK = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1.json")


def test_cell_lists():
    a, b, c = R.e21a_cells(), R.e21b_cells(0.8), R.e21c_cells()
    assert (len(a), len(b), len(c)) == (60, 32, 36)
    for cells in (a, b, c):
        keys = [R.e21_key(t, mn) for (t, _, mn, _, _) in cells]
        assert len(set(keys)) == len(keys)
    mixes = {t["mix"]: t["policy"] for (t, *_) in a}
    assert mixes["supervised_strategic+avoid"] == "strategic+avoid" and mixes["default"] == "strict"
    t, sc = R.scenario("teleop_4s", "dte+relay", 0.9)
    assert t["rtt_s"] == pytest.approx(4.0) and all(v[2] == "teleop" for v in sc.fleet)
    assert sc.comms["relay"]["coverage"] == 0.9 and sc.terrain == "connecting_ridge" and sc.pad_standoff_km == "1"
    t, sc = R.scenario("supervised_strict", "dte", extra=3, mast=R.MASTS[1])
    assert len(sc.fleet) == 9 and sc.n_operators == 4 and sc.comms["mast"]["height_m"] == 10.0
    assert [R.start_year(s) for s in range(6)] == [2028, 2029, 2030, 2031, 2028, 2029]
    defers = sorted({t["defer_wait_h"] for (t, *_) in c})
    assert defers == [12.0, 24.0, 72.0, math.inf]


@pytest.mark.skipif(not os.path.isfile(LINK), reason="earth_link-v1.json not generated")
def test_smoke_two_cells_two_seeds_and_resume(tmp_path, capsys):
    res = str(tmp_path)
    cells = R.e21a_cells()
    idx = [i for i, (t, *_) in enumerate(cells) if t["comms"] == "dte" and t["mix"] in ("default", "autonomous")]
    spec = f"{idx[0]}-{idx[1]}"
    assert idx[1] == idx[0] + 4                                   # mixes run in MIXES order within a comms level
    sub = [cells[idx[0]], cells[idx[1]]]
    df = R.run_stage("E21a_comms_autonomy", sub, seeds=2, workers=1, results=res)
    assert len(df) == 4 and set(df["start_year"]) == {2028, 2029}
    for col in ("cell", "seed", "stage", "comms", "mix", "policy", "defer_wait_h", "blackout_wait_vehicle_h",
                "operator_peak_demand", "linked_share_by_leg_mean", "delivered_t_in_year", "run_s"):
        assert col in df.columns, col
    assert (df[df["mix"] == "autonomous"]["blackout_wait_vehicle_h"] == 0).all()
    again = R.run_stage("E21a_comms_autonomy", sub, seeds=2, workers=1, results=res)
    assert len(again) == 4 and "0 to run" in capsys.readouterr().out
    t = R.write_tables(res)
    assert len(t) == 2 and (t["n_seeds"] == 2).all()
    for m in ("delivered_t_in_year", "delay_prio1_p90_h", "cost_per_landed_kg_usd", "blackout_wait_vehicle_h",
              "operator_peak_demand"):
        assert m in t.columns and m + "_ci95" in t.columns
    assert os.path.isfile(os.path.join(res, "table_E21.csv"))
    with pytest.raises(SystemExit):
        R.parse_cells("40-41", 36)
    assert R.parse_cells(spec, 36) == [idx[0], idx[0] + 1, idx[0] + 2, idx[0] + 3, idx[1]]


def _synthetic_table():
    rows = []
    curve = {0.0: 300.0, 0.5: 420.0, 0.8: 495.0, 0.9: 505.0, 1.0: 515.0}
    for p, v in curve.items():
        rows.append({"stage": "A", "comms": "dte" if p == 0 else "dte+relay", "coverage": np.nan if p == 0 else p,
                     "mix": "supervised_strict", "delivered_t_in_year": v})
    rows.append({"stage": "A", "comms": "always", "coverage": np.nan, "mix": "supervised_strict", "delivered_t_in_year": 515.0})
    rows.append({"stage": "A", "comms": "dte", "coverage": np.nan, "mix": "supervised_strategic", "delivered_t_in_year": 330.0})
    rows.append({"stage": "A", "comms": "dte", "coverage": np.nan, "mix": "autonomous", "delivered_t_in_year": 515.0})
    for n, v in ((0, 300.0), (1, 360.0), (2, 410.0), (3, 450.0)):
        rows.append({"stage": "B", "comms": "dte", "mast": "none", "policy": "strict", "extra_rovers": n,
                     "delivered_t_in_year": v})
    rows.append({"stage": "B", "comms": "dte", "mast": "BASE 10 m", "policy": "strict", "extra_rovers": 0,
                 "delivered_t_in_year": 310.0})
    return pd.DataFrame(rows)


def test_knee_and_breakeven_on_a_synthetic_table():
    t = _synthetic_table()
    assert R.knee_coverage(t) == 0.8                              # 495 >= 0.95 x 515 = 489.25; 420 is not
    be = R.breakeven_table(t).set_index("option")
    one_ltv = be.attrs["rover_musd_per_yr"] if hasattr(be, "attrs") else None
    assert be.loc["relay coverage 0.5", "gain_vs_dte"] == pytest.approx(120.0)
    assert be.loc["relay coverage 0.5", "extra_rovers_equiv"] == pytest.approx(2.0 + 10.0 / 40.0)  # 410 + 10 of 40
    assert be.loc["+1 supervised LTV", "relay_coverage_equiv"] == pytest.approx(0.25)            # 60 of 120 per 0.5
    assert be.loc["autonomy step: supervised strict -> strategic", "extra_rovers_equiv"] == pytest.approx(0.5)
    assert math.isnan(be.loc["relay coverage 1", "extra_rovers_equiv"])                           # beyond +3 rovers
    assert be.loc["BASE mast 10 m", "gain_vs_dte"] == pytest.approx(10.0)
    rover = R.VEHICLE_CLASSES["LTV"].unit_cost_musd / R.VEHICLE_CLASSES["LTV"].life_years
    assert be.loc["relay coverage 0.5", "relay_price_musd_per_yr_equiv"] == pytest.approx(2.25 * rover)
