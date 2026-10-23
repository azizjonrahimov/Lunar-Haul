"""B-55: results/E21_strategic_years.json (experiments/phase4/strategic_years.py) against the E21 r2 table and the
committed link files (no simulation here; the calendar and sky parts are recomputed exactly)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pandas as pd
import pytest

OUT = os.path.join(ROOT, "results", "E21_strategic_years.json")
E21 = os.path.join(ROOT, "results", "E21a_comms_autonomy_r2.csv")
pytestmark = pytest.mark.skipif(not (os.path.isfile(OUT) and os.path.isfile(E21)), reason="not generated")


@pytest.fixture(scope="module")
def doc():
    with open(OUT, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def SY():
    from experiments.phase4 import strategic_years
    return strategic_years


def test_e21_by_start_year_matches_the_table(doc):
    e = pd.read_csv(E21, float_precision="round_trip")
    e = e[(e["mix"] == "supervised_strategic") & (e["comms"] == "dte")]
    assert len(e) == 20
    for y, g in e.groupby("start_year"):
        got = doc["e21_by_start_year"][str(int(y))]
        assert got["n"] == len(g)
        assert got["delivered_t_in_year"] == pytest.approx(g["delivered_t_in_year"].mean(), abs=5e-4)
        assert got["blackout_wait_vehicle_h"] == pytest.approx(g["blackout_wait_vehicle_h"].mean(), abs=0.05)
    by = doc["e21_by_start_year"]
    assert by["2028"]["delivered_t_in_year"] < 0.5 * min(by[y]["delivered_t_in_year"] for y in ("2029", "2030", "2031"))


def test_swap_runs_agree_with_e21_and_point_at_the_year(doc):
    sw, seeds = doc["swap"], doc["generated"]["seeds"]
    assert sw["own_year_runs_reproduce_e21"] and sw["landings_identical_across_years"]
    e = pd.read_csv(E21, float_precision="round_trip")
    e = e[(e["mix"] == "supervised_strategic") & (e["comms"] == "dte")].set_index("seed")
    for s in range(seeds):
        y = int(e.loc[s, "start_year"])
        assert sw["delivered_t_in_year"][str(y)][s] == pytest.approx(e.loc[s, "delivered_t_in_year"], abs=0.051)
    assert sw["seeds_lowest_in_2028"] == seeds                                   # every seed collapses in 2028
    st = doc["stranding"]
    assert st["2028"]["stranded_rover_hours_per_run"] > st["2030"]["stranded_rover_hours_per_run"]
    assert st["2028"]["share_not_resuming_in_year"] > st["2030"]["share_not_resuming_in_year"]
    assert all(len(st[y]["stranded_fleet_share_by_month"]) == 12 for y in st)


def test_calendar_and_sky_recompute_from_the_link_files(doc, SY):
    top = [t["sample"] for t in doc["stranding_2028_top_samples"]]
    cal = SY.calendar_part(top)
    r = lambda xs: [SY._r(v, 3) for v in xs]
    assert {p: r(v) for p, v in cal["places"].items()} == doc["calendar"]["places_linked_fraction"]
    assert r(cal["route_samples"]["dark_whole_month_share"]) == doc["calendar"]["route_samples"]["dark_whole_month_share"]
    for t in doc["stranding_2028_top_samples"]:
        assert r(cal["samples"][str(t["sample"])]) == t["monthly_linked_2028_2031"]
    worst = doc["stranding_2028_top_samples"][0]
    assert max(worst["monthly_linked_2028_2031"][:12]) == 0.0                   # dark all through 2028
    assert SY.sky_part(top[:3]) == doc["sky"]
    assert doc["sky"]["samples"][str(worst["sample"])]["earth_in_its_sky_box_hours_by_year"][0] == 0
