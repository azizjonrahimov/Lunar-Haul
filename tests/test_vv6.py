"""B-98: every Phase 6 verification row passes, and the results file has the format the verification page reads."""
import json
import os

import pytest

from lunarsim import vv6

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_all_phase6_rows_pass():
    rows = vv6.run_phase6_checks()
    failed = [(r["id"], r["sub"], r["reference"], r["simulated"]) for r in rows if not r["passed"]]
    assert not failed
    keys = [(r["id"], r["sub"]) for r in rows]
    assert len(keys) == len(set(keys))
    assert {r["id"][0] for r in rows} == {"P", "M", "C", "G"}
    assert all(r["tolerance_source"] and "note" in r["tolerance_source"].lower() or r["id"].startswith("G")
               for r in rows)


def test_results_file():
    p = os.path.join(ROOT, "results", "vv_phase6.json")
    if not os.path.isfile(p):
        pytest.skip("not built")
    d = json.load(open(p))
    assert d["version"] == 1 and d["summary"]["rows"] == len(d["rows"]) and d["summary"]["failed"] == 0
