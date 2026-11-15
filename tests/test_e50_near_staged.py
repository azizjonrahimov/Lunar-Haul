"""B-118 (8x): the staged near_base path (one step per process) gives the same cell as run_cell. Tiny case: the
engine run, the trajectories, the masks and pnt.simulate are replaced by small deterministic stand-ins, so the test
checks the staging and assembly, not the physics (which both paths share)."""
import os
import sys
import types

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "atc"))


def _fakes(monkeypatch, N, tmp_path):
    from lunarsim.atc import pnt as PN
    E5 = N.E5
    T, V = 40, 3
    monkeypatch.setattr(E5, "_window", lambda: (0, 0.0, 1.0, 0.5))
    monkeypatch.setattr(E5, "record", lambda m, s, t0, t1, pos_margin=None: {"delay_mean_h": 1.5 + s, "name": ["a", "b", "c"]})
    ds = (np.arange(T * V).reshape(T, V) % 3 > 0).astype(float)
    monkeypatch.setattr(E5, "trajectories", lambda rec, t0, t1: types.SimpleNamespace(ds=ds))
    monkeypatch.setattr(E5, "beacons", lambda rec: ([0], [[0.0, 0.0]]))
    monkeypatch.setattr(E5, "_geo", lambda: {"los": None, "ids": {"BASE": 0}})
    monkeypatch.setattr(E5, "code_fingerprint", lambda: "tiny")
    monkeypatch.setattr(E5, "CACHE", str(tmp_path / "no_e50"))
    k = np.arange(T * V).reshape(T, V)
    monkeypatch.setattr(N, "masks", lambda tr, rec: {r: (k % (i + 2) == 0) for i, r in enumerate(N.READINGS)})

    def simulate(tr, layers, seed, params=None, **kw):
        base = seed + len(layers) + sum(float(v) for v in (params or {}).values())
        return types.SimpleNamespace(err=np.abs(np.sin((k + 1) * (1.0 + 0.1 * base))) * 10.0)
    monkeypatch.setattr(PN, "simulate", simulate)
    monkeypatch.setattr(N, "CACHE", str(tmp_path / "near"))
    os.makedirs(N.CACHE, exist_ok=True)


def test_staged_cell_equals_run_cell(monkeypatch, tmp_path):
    import json
    import run_e50_near as N
    _fakes(monkeypatch, N, tmp_path)
    for mult, seed in ((1, 3), (8, 2)):                # with the sweep (1x seed 3) and without (8x)
        direct = N.run_cell(mult, seed)
        for _ in range(len(N._stage_names(mult, seed)) + 1):
            N.cmd_stage(mult, [seed])
        staged = json.load(open(os.path.join(N.CACHE, f"m{mult}_s{seed}.json")))
        assert staged["code"] == "tiny" and staged["staged"] is True
        assert not os.path.isdir(N._stage_dir(mult, seed))   # B-120 D: the steps are removed once in the cell
        assert direct["code"] == "tiny"                       # B-120 D: run_cell stamps its code too
        skip = {"cell_s", "peak_mb", "code", "staged"}
        direct = json.loads(json.dumps(direct))
        assert {k: v for k, v in staged.items() if k not in skip} == {k: v for k, v in direct.items() if k not in skip}
        assert ("sweep" in staged) == (mult == 1)


def test_assembly_refuses_mixed_code(monkeypatch, tmp_path):
    import pytest
    import run_e50_near as N
    _fakes(monkeypatch, N, tmp_path)
    names = N._stage_names(8, 1)
    for _ in range(len(names) - 1):
        N.cmd_stage(8, [1])
    monkeypatch.setattr(N.E5, "code_fingerprint", lambda: "other")
    N.cmd_stage(8, [1])                                # the last step, made with other code
    with pytest.raises(SystemExit):
        N.cmd_stage(8, [1])
