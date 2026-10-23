"""B-59 Stage G: results/E21g_rescue_r2.csv, table_E21g_rescue_r2.csv and E21_fit_r2.json 'rescue' (analyse_e21.py
rescue); the break-even crossing on synthetic numbers; the pool diagnostic of 'bounded' (no simulation here)."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pandas as pd
import pytest

RES = os.path.join(ROOT, "results")
G = os.path.join(RES, "E21g_rescue_r2.csv")
FIT = os.path.join(RES, "E21_fit_r2.json")


@pytest.fixture(scope="module")
def A():
    from experiments.phase4 import analyse_e21
    return analyse_e21


def test_crossing_is_linear_in_log1p(A):
    lv = [0, 24, 72, 168, 720]
    assert A.crossing_h(lv, [5, 4, 3, 2, 1]) == math.inf                    # stays above: beyond the range
    assert A.crossing_h(lv, [0, 1, 1, 1, 1]) == -math.inf                   # at or below 0 at the first level
    h = A.crossing_h(lv, [3, 2, 1, -1, -2])                                  # between 72 and 168, halfway in log1p
    assert h == pytest.approx(math.expm1(0.5 * (math.log1p(72) + math.log1p(168))))
    assert A.crossing_h(lv, [3, 2, 0, -1, 2]) == pytest.approx(72.0)         # the first crossing counts


@pytest.mark.skipif(not (os.path.isfile(G) and os.path.isfile(FIT)), reason="Stage G not run")
def test_rescue_summary_and_breakeven_recompute(A):
    from experiments.phase4 import run_phase4 as R
    g = A.load_stage_g(RES)
    assert len(g) == len(R.e21g_cells()) * 20 == 100 and not g.duplicated(["cell", "seed"]).any()
    with open(FIT, encoding="utf-8") as f:
        doc = json.load(f)["rescue"]
    lv = {x["rescue_h"]: x for x in doc["levels"]}
    for h, cell in g.groupby("rescue_h"):
        assert lv[h]["mean"]["delivered_t_in_year"] == pytest.approx(cell["delivered_t_in_year"].mean(), rel=1e-12)
        assert lv[h]["rescues_per_run"] == pytest.approx(cell["blackout_rescues_never_linked"].mean())
    assert lv[0.0]["rescue_vehicle_h_per_run"] == 0.0 and lv[720.0]["rescue_vehicle_h_per_run"] > lv[24.0]["rescue_vehicle_h_per_run"]
    df = A.load_round(RES, "r2")
    a = df[(df["stage"] == "A") & (df["sensitivity"] == "none")]
    strict = A.select(a, p=0.0, mix="supervised_strict")
    for m, b in doc["breakeven_vs_strict"].items():
        d = [(g[g["rescue_h"] == h].set_index("seed")[m] - strict.set_index("seed")[m]).mean() for h in b["levels_h"]]
        assert np.allclose(d, b["mean_diff_by_level"], rtol=1e-12, atol=1e-12)
        pt = A.crossing_h(b["levels_h"], d)
        want = "beyond 720 h" if pt == math.inf else "below 0 h" if pt == -math.inf else round(pt, 1)
        assert b["breakeven_h"] == want and b["draws"] == 2000
        assert 0.0 <= b["share_beyond_range"] + b["share_below_range"] <= 1.0
    t = pd.read_csv(os.path.join(RES, "table_E21g_rescue_r2.csv"))
    assert set(t["reference"]) == {"strategic", "strict", "look-ahead"} and set(t["family"]) == {"rescue", "rescue_by_year"}


@pytest.mark.skipif(not os.path.isfile(FIT), reason="no fit file")
def test_pool_diagnostic_for_strict_and_look_ahead():
    with open(FIT, encoding="utf-8") as f:
        ps = json.load(f).get("bounded", {}).get("pool_starvation")
    if not ps or "strict" not in ps:
        pytest.skip("bounded --diagnose not run")
    assert set(ps["filter_before_cap"]) == {"rule", "strict", "look-ahead"}
    for key in ("strict", "look_ahead"):
        assert [r["start_year"] for r in ps[key]] == [2028, 2029, 2030, 2031]
        for r in ps[key]:
            assert 0.0 <= r["blocked_share_of_slots"] <= r["blocked_share_of_pool"] <= 1.0 and r["samples"] > 100
