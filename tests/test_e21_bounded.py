"""B-57 Stage F: results/E21f_bounded_r2.csv, table_E21f_bounded_r2.csv and E21_fit_r2.json 'bounded' (analyse_e21.py
bounded) agree with each other and with Stage A (no simulation here)."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pandas as pd
import pytest

RES = os.path.join(ROOT, "results")
F = os.path.join(RES, "E21f_bounded_r2.csv")
FIT = os.path.join(RES, "E21_fit_r2.json")
TABLE = os.path.join(RES, "table_E21f_bounded_r2.csv")
pytestmark = pytest.mark.skipif(not all(os.path.isfile(p) for p in (F, FIT, TABLE)), reason="Stage F not run")


@pytest.fixture(scope="module")
def A():
    from experiments.phase4 import analyse_e21
    return analyse_e21


@pytest.fixture(scope="module")
def bounded():
    with open(FIT, encoding="utf-8") as f:
        return json.load(f)["bounded"]


def test_stage_f_is_complete_and_matches_its_design(A):
    from experiments.phase4 import run_phase4 as R
    f = A.load_stage_f(RES)
    assert len(f) == len(R.e21f_cells()) * 20 == 540 and not f.duplicated(["cell", "seed"]).any()
    assert set(f["start_year"]) == {2028, 2029, 2030, 2031}
    assert f.groupby("variant").size().eq(60).all()                 # 9 variants x 3 link regimes x 20 seeds


def test_summary_and_verdict_recompute_from_the_rows(A, bounded):
    f = A.load_stage_f(RES)
    cells = {(c["link"], c["variant"]): c for c in bounded["cells"]}
    for (p, var), g in f.groupby(["p", "variant"]):
        c = cells[(A._plabel(p), var)]
        assert c["n"] == len(g) == 20
        assert c["mean"]["delivered_t_in_year"] == pytest.approx(g["delivered_t_in_year"].mean(), rel=1e-12)
        assert c["by_year"]["2028"]["delivered_bulk_t"] == pytest.approx(
            g.loc[g["start_year"] == 2028, "delivered_bulk_t"].mean(), rel=1e-12)
    v = {x["variant"]: x for x in bounded["verdict_dte"]}
    assert v["strategic (Stage A)"]["bulk_share_of_strategic"] == pytest.approx(1.0)
    refuse = [x for k, x in v.items() if "refused" in k]
    assert refuse and all(not x["keeps_isru"] for x in refuse)      # never-linked routes refused: no ISRU haul
    assert not v["strategic, strand on never-linked"]["keeps_isru"]


def test_paired_table_against_strategic_and_look_ahead(A):
    t = pd.read_csv(TABLE)
    assert set(t["reference"]) == {"strategic", "look-ahead"} and set(t["family"]) == {"bounded", "bounded_by_year"}
    df = A.load_round(RES, "r2")
    f = A.load_stage_f(RES)
    a = df[(df["stage"] == "A") & (df["sensitivity"] == "none")]
    ref = A.select(a, p=0.0, mix="supervised_strategic")
    var = "strategic, strand on never-linked"
    cell = A.select(f, p=0.0)
    cell = cell[cell["variant"] == var]
    row = t[(t["family"] == "bounded") & (t["reference"] == "strategic") & (t["cell"] == var) & (t["p"] == 0.0)
            & (t["metric"] == "delivered_t_in_year")].iloc[0]
    assert row["diff"] == pytest.approx(A.paired(ref, cell, "delivered_t_in_year")["diff"], rel=1e-9)
    assert row["n"] == 20


def test_redraw_counts_and_never_linked_legs(A, bounded):
    df = A.load_round(RES, "r2")
    a = df[(df["stage"] == "A") & (df["sensitivity"] == "none")]
    s = A.select(a, p=0.0, mix="supervised_strategic")
    r = next(x for x in bounded["redraws"] if x["policy"] == "strategic" and x["link"] == "DTE")
    assert r["refused_per_run"] == pytest.approx(s["blackout_jobs_refused"].mean())
    assert r["refused_per_run_2028"] == pytest.approx(s.loc[s["start_year"] == 2028, "blackout_jobs_refused"].mean())
    look = next(x for x in bounded["redraws"] if x["policy"] == "look-ahead" and x["link"] == "DTE")
    assert look["refused_not_avoided_per_run"] == pytest.approx(0.0)          # look-ahead refusals are its deferrals
    nl = A.never_linked_legs()
    assert nl == bounded["never_linked_legs"]
    assert nl["main_network_legs"] == 70 and "ISRU->CONSTR" in nl["main_network_list"]
