"""B-75: the Phase-5 runner's cells and run files (experiments/phase5/run_phase5.py)."""
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pandas as pd
import pytest

from experiments.phase5 import run_phase5 as R


def test_cells_and_blocks():
    e40 = R.e40_cells()
    assert len(e40) == 40 and len({c["key"] for c in e40}) == 40
    l60 = e40[24:36]
    assert [c["tag"]["load"] for c in l60] == [60] * 12
    assert [c["tag"]["label"] for c in l60] == [lab for lab, _, _ in R.REGIMES_E40]
    assert len(R.blocks("both")) == 80 and len(R.blocks("v1")) == 30
    assert {c["regime"] for c in e40} >= {"C_LEARNED_MLP", "C_LEARNED_LIN", "O_ORACLE"}
    assert all(c["kw"].get("own_teams") for c in e40 if c["regime"].startswith("A_"))
    for f in (R.e41_cells, R.e42_cells):
        cs = f()
        assert len({c["key"] for c in cs}) == len(cs)


def test_existing_rows_keep_their_cell_keys():
    """PREREG change 4: only the unrun 60 % cells of the Earth-independent regimes run block v1 only; every row already
    in results/E40_runs*.csv still belongs to a current cell (same key)."""
    e40 = R.e40_cells()
    keys = {c["key"] for c in e40}
    l60 = {c["tag"]["label"]: c["block"] for c in e40 if c["tag"]["load"] == 60}
    assert {lab for lab, b in l60.items() if b == "v1"} == {lab for lab in l60 if lab in R.EARTH_INDEPENDENT}
    assert all(c["block"] == "both" for c in e40 if c["tag"]["load"] in (10,) or
               (c["tag"]["load"] == 30 and "hopper" not in c["tag"]["label"]))
    df = R.load_runs("E40")
    if df.empty:
        pytest.skip("no E40 rows")
    assert set(df["cell"].astype(str)) <= keys


def test_run_files_union_and_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "RESULTS", str(tmp_path))
    row = lambda cell, seed, extra=None: dict({"cell": cell, "seed": seed, "start_year": 2028 + seed % 4, "x": 1.0}, **(extra or {}))
    R._append("EX", row("a", 1))
    R._append("EX", row("b", 1), part="L60")
    R._append("EX", row("b", 2, {"y": 3.0}), part="L60")          # a new column: the file is rewritten with the union
    assert sorted(os.listdir(tmp_path)) == ["EX_runs.L60.csv", "EX_runs.csv"]
    df = R.load_runs("EX")
    assert len(df) == 3 and R._done("EX") == {("a", 1, 2029), ("b", 1, 2029), ("b", 2, 2030)}
    assert pd.isna(df.loc[df["cell"] == "a", "y"]).all()
    R._append("EX", row("b", 1), part="other")                     # the same key in another file
    with pytest.raises(ValueError):
        R.load_runs("EX")
    with pytest.raises(ValueError):
        R._done("EX")
