"""Phase 4 data checks in `lunarsim verify` (B-39): each row passes (or is skipped with a reason), and the format."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pytest

from lunarsim import vv

ROW_KEYS = {"name", "reference", "simulated", "error", "tolerance", "unit", "basis", "source", "mode", "passed", "skipped"}


@pytest.fixture(scope="module")
def rows():
    return vv.run_phase4_checks()


def test_phase4_rows_pass_or_skip_with_reason(rows):
    names = [r["name"] for r in rows]
    assert len(rows) == 8 and len(set(names)) == 8
    for r in rows:
        assert ROW_KEYS <= set(r), r["name"]
        assert r["source"], r["name"]
        if r["skipped"]:
            assert not r["passed"]
            continue
        assert r["passed"], f"{r['name']}: ref {r['reference']} sim {r['simulated']} err {r['error']} tol {r['tolerance']}"
        assert r["basis"] and math.isfinite(r["error"])


def test_check_modes_and_skip():
    c = vv.Check("x", 0.0, 4e-7, 1e-6, "m", "b", mode="abs").finish()
    assert c.passed and c.error == pytest.approx(4e-7)
    c = vv.Check("x", 0.0, 2e-6, 1e-6, "m", "b", mode="abs").finish()
    assert not c.passed
    c = vv.Check("x", 100.0, 100.5, 0.01, "kg", "b").finish()
    assert c.passed and c.error == pytest.approx(0.005)
    s = vv._skip("y", "m", "b", "src", "needs the [ml] extra")
    assert s.skipped and not s.passed


def test_catalogue_check_detects_drift(monkeypatch):
    from lunarsim import catalog
    monkeypatch.setattr(catalog, "engine_mismatches", lambda doc=None: ["LTV.capacity_kg: catalogue 800 != engine 1500"])
    c = vv.check_catalogue_engine()
    assert not c.passed and c.reference - c.simulated == 1


def test_cli_verify_json(tmp_path, capsys):
    from lunarsim.cli import main
    out = tmp_path / "v.json"
    with pytest.raises(SystemExit) as e:
        main(["verify", "--json", str(out)])
    assert e.value.code == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["format"] == "lunarsim-verification" and len(doc["phase4"]) == 8 and doc["checks"]
    text = capsys.readouterr().out
    assert "Catalogue values equal the engine constants" in text and "checks passed" in text
