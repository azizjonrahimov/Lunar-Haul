"""B-20: memory-bounded DAgger in lunarsim.rover.bc (per-round reservoir cap, early stop on failing rollouts,
float16 dataset with per-batch float32, memory printout). The smoke run uses the real terrain pack and is skipped
without it or without the [ml] extras."""
import json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

pytest.importorskip("gymnasium")
torch = pytest.importorskip("torch")
from lunarsim.rover import bc as BC  # noqa: E402


def test_reservoir_is_bounded_and_uniform():
    rng = np.random.default_rng(0)
    counts = np.zeros(100)
    for _ in range(2000):
        r = BC.Reservoir(10, rng)
        for i in range(100):
            r.add(i)
        assert len(r.items) == 10 and r.seen == 100
        counts[[it[0] for it in r.items]] += 1
    p = counts / counts.sum()
    assert np.allclose(p, 0.01, atol=0.004)          # every stream position kept with probability cap / n
    small = BC.Reservoir(10, rng)
    for i in range(4):
        small.add(i, -i)
    assert small.items == [(0, 0), (1, -1), (2, -2), (3, -3)]   # below the cap: everything, in order


def test_process_memory_is_reported():
    m = BC.process_memory_mb()
    assert set(m) == {"rss_mb", "peak_rss_mb", "private_mb"}
    assert m["rss_mb"] is not None and m["rss_mb"] > 10


def test_train_keeps_the_dataset_float16():
    rng = np.random.default_rng(1)
    data = {"patch": rng.normal(size=(40, 3, 32, 32)).astype(np.float16),
            "scalars": rng.normal(size=(40, 5)).astype(np.float32),
            "act": rng.uniform(-1, 1, (40, 2)).astype(np.float32)}
    before = data["patch"].copy()
    r = BC.train(BC.make_model(), data, epochs=2, batch=16, seed=0)
    assert r["steps"] == 6 and np.isfinite(r["mse"])
    assert data["patch"].dtype == np.float16 and np.array_equal(data["patch"], before)


@pytest.fixture
def pack(monkeypatch):
    if not os.path.exists(os.path.join(ROOT, "data", "terrain", "connecting_ridge", "sites.json")):
        pytest.skip("terrain pack connecting_ridge not present")
    pytest.importorskip("onnxruntime")
    monkeypatch.chdir(ROOT)
    return "connecting_ridge"


def test_dagger_smoke_bounded(pack, tmp_path, capsys):
    """--legs 2 --max-steps 200: every 200-step rollout ends short of the goal, so the DAgger round stops after
    its first 5 runs; the cap keeps 30 of the ~125 recorded samples."""
    r = BC.run(pack, "rover_smoke", n_legs=2, stride=8, dagger=1, epochs=1, dagger_epochs=1, eval_legs=1,
               max_steps=200, out_dir=str(tmp_path / "pol"), run_root=str(tmp_path / "runs"), dagger_steps_cap=30)
    out = capsys.readouterr().out
    hist = r["card"]["training"]["history"]
    assert [h["round"] for h in hist] == [0, 1]
    ro = hist[1]["rollout"]
    assert ro["stopped_early"] and ro["runs"] == 5 and ro["failed"] == 5 and ro["planned_runs"] == 10
    assert ro["recorded"] > 30 and ro["kept"] == 30
    assert hist[1]["samples"] == hist[0]["samples"] + 30
    for h in hist:
        assert h["dataset_mb"] > 0 and h["rss_mb"] > 0
    assert "round 0: dataset" in out and "round 1: dataset" in out and "working set" in out
    assert "(round stopped early)" in out
    assert r["card"]["training"]["dagger_steps_cap"] == 30
    with open(tmp_path / "pol" / "rover_smoke.json", encoding="utf-8") as f:
        assert json.load(f)["kind"] == "cnn"
    print(out)
