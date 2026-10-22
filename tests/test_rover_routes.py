"""Planned rover routes for the 3D views (B-32, lunarsim/rover/routes.py): A*, resampling, time fractions, the file."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim.rover import routes as RT
from lunarsim.rover.expert import astar
from lunarsim.formats import load_schema

DATA = os.path.join(ROOT, "data", "driving", "routes-v1.json")
DRIVING = os.path.join(ROOT, "data", "driving", "driving-v1.json")


def test_astar_is_straight_on_flat_ground():
    cost = np.ones((60, 60))
    path = astar(cost, (10, 5), (10, 45), 20.0)
    assert [r for r, _ in path] == [10] * len(path) and len(path) == 41
    diag = astar(cost, (5, 5), (35, 35), 20.0)
    assert all(r == c for r, c in diag) and len(diag) == 31


def test_resample_keeps_corners_and_spacing():
    poly = np.array([[0, 0], [0, 40], [0, 95], [60, 95], [60, 95], [90, 125]], float)  # collinear point, duplicate
    assert RT.corner_indices(poly) == [0, 2, 3, 4]                       # indices after dropping the repeat
    v = RT.resample(poly, 10.0)
    seg = np.hypot(*np.diff(v, axis=0).T)
    assert seg.max() <= 10.0 + 1e-9 and seg.min() > 0
    for corner in ([0, 0], [0, 95], [60, 95], [90, 125]):
        assert np.min(np.hypot(*(v - corner).T)) < 1e-9
    assert seg.sum() == pytest.approx(95 + 60 + math.hypot(30, 30))       # the length is unchanged


def test_time_fractions_follow_the_speed_model():
    n = 40
    prof = {"ds": np.full(n, 5.0), "grade": np.zeros(n), "slope": np.zeros(n), "heading": np.zeros(n),
            "shadow": np.zeros(n, bool)}
    s = np.linspace(0, 200, 21)
    f = RT.time_fractions(prof, None, s)
    assert f[0] == 0 and f[-1] == pytest.approx(1.0) and np.all(np.diff(f) >= 0)
    assert np.allclose(f, s / 200.0)                                      # uniform speed: f = s / L
    prof["slope"] = np.where(np.arange(n) < n // 2, 0.0, 12.0)            # slower (still passable) second half
    f2 = RT.time_fractions(prof, None, np.array([0.0, 100.0, 200.0]))
    assert f2[1] < 0.5 and f2[2] == pytest.approx(1.0)
    prof["shadow"] = np.ones(n, bool)
    f3 = RT.time_fractions(prof, "night", np.array([0.0, 100.0, 200.0]))
    assert f3[2] == pytest.approx(1.0)


def test_encode_decode_round_trip():
    rng = np.random.default_rng(1)
    pts = np.cumsum(rng.uniform(-7, 7, (50, 2)), axis=0) + 5000
    seg = np.hypot(*np.diff(pts, axis=0).T)
    rec = {"x": pts[:, 0], "y": pts[:, 1], "z": rng.uniform(1500, 1900, 50),
           "s": np.concatenate([[0], np.cumsum(seg)]), "f": np.linspace(0, 1, 50) ** 1.3}
    g = RT.decode_geom(RT.encode_geom(rec))
    assert np.max(np.abs(g["x"] - rec["x"])) <= 0.05 + 1e-9 and np.max(np.abs(g["z"] - rec["z"])) <= 0.05 + 1e-9
    assert abs(g["s"][-1] - rec["s"][-1]) < 49 * 0.05 * math.sqrt(2)     # per-segment rounding, at most
    df = RT.encode_f(rec["f"])
    f = RT.decode_f(df)
    assert sum(df) == 10000 and min(df) >= 0 and np.max(np.abs(f - rec["f"])) <= 5e-5 + 1e-12


@pytest.mark.skipif(not os.path.isfile(DATA), reason="routes-v1.json not generated")
def test_committed_routes_file():
    assert os.path.getsize(DATA) <= 4 * 1024 * 1024
    with open(DATA, encoding="utf-8") as f:
        doc = json.load(f)
    assert RT.validate(doc) == []
    with open(DRIVING, encoding="utf-8") as f:
        table = json.load(f)
    assert set(doc["legs"]) == set(table["legs"]) and len(doc["legs"]) == 182
    n = 0
    for leg, ls in doc["legs"].items():
        assert set(ls) == {"0", "90", "180", "270", "night"}
        for key, e in ls.items():
            assert e is not None
            assert abs(e["length_m"] - table["legs"][leg]["route"][key]["length_m"]) <= 0.06
            g = RT.decode_geom(doc["geoms"][e["geom"]])
            assert abs(g["s"][-1] - e["length_m"]) < 0.1
            n += 1
    assert n == 910 and doc["checks"]["max_abs_length_diff_vs_table_m"] <= 0.06
    # pads at every standoff are present
    assert {"PAD_A@0.5->BASE", "BASE->PAD_B@5", "PAD_A@3->ISRU"} <= set(doc["legs"])
    jsonschema = pytest.importorskip("jsonschema", reason="jsonschema not installed")
    jsonschema.validate(doc, load_schema("routes-v1"))
