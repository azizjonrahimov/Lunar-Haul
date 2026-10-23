"""B-64: the joined link windows (tools/comms/later_years.py join) and results/E21_edge_check_r2.json."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "comms"))
import numpy as np
import pytest

import later_years as LY  # noqa: E402

OUT = os.path.join(ROOT, "results", "E21_edge_check_r2.json")


def test_join_windows_merges_at_the_seam():
    w1 = np.array([[2, 5], [8, 10]])
    assert LY.join_windows(w1, 10, np.array([[0, 3], [6, 7]])).tolist() == [[2, 5], [8, 13], [16, 17]]
    assert LY.join_windows(w1, 10, np.array([[1, 3]])).tolist() == [[2, 5], [8, 10], [11, 13]]
    assert LY.join_windows(np.zeros((0, 2), int), 10, np.array([[0, 2]])).tolist() == [[10, 12]]
    assert LY.join_windows(w1, 10, np.zeros((0, 2), int)).tolist() == w1.tolist()


@pytest.mark.skipif(not os.path.isfile(OUT), reason="edge check not run")
def test_edge_check_report_is_consistent():
    from experiments.phase4 import run_phase4 as R
    d = json.load(open(OUT, encoding="utf-8"))
    late = [s for s in range(20) if R.start_year(s) == 2031]
    for lab, b in d["cells"].items():
        assert set(b["rows_with_any_change"]) <= set(late), lab          # only the 2031 start years move
        for m, mb in b["metrics"].items():
            for y in ("2028", "2029", "2030"):
                assert mb["by_start_year"][y]["mean_diff"] == 0.0, (lab, m, y)
            o = mb["overall"]
            assert o["joined_mean"] - o["committed_mean"] == pytest.approx(o["mean_diff"], abs=1e-9)
    pv = d["paper_values"]
    assert pv["n_moved"] == len(pv["moved"]) and pv["base_equals_committed_values_json"] == pv["n_values"]
    assert d["verdict"].startswith("yes" if pv["n_moved"] else "no")
