"""R-1 Earth-link data (B-40): geometry, horizon masks, link windows and the reader (lunarsim/comms.py)."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "comms"))
import numpy as np
import pytest

import earth_link as E
from lunarsim import comms as C

R = E.R_MOON_M
DATA = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1.json")


# ------------------------------------------------------------------------------------------------ geometry
def test_stereo_unit_matches_lat_lon_and_the_note():
    X, Y = np.array([-11550.0, 3000.0, 0.0]), np.array([-12490.0, -250000.0, 1.0])
    lat, lon = E.latlon_deg(X, Y)
    la, lo = np.radians(lat), np.radians(lon)
    want = np.stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)], axis=-1)
    assert np.allclose(E.stereo_unit(X, Y), want, atol=1e-12)
    assert lat[0] == pytest.approx(-89.439, abs=5e-4) and lon[0] == pytest.approx(222.761, abs=5e-3)   # BASE


def test_grid_bearing_is_local_azimuth_plus_longitude():
    """A short step along map +y (grid bearing 0) seen from a point near the pole has local azimuth -lon."""
    X, Y = -11550.0, -12490.0
    lat, lon = (float(v) for v in E.latlon_deg(X, Y))
    for b in (0.0, 7.0, -11.0):
        P = E.stereo_unit(X, Y) * R
        Q = E.stereo_unit(X + 50 * math.sin(math.radians(b)), Y + 50 * math.cos(math.radians(b))) * R
        east, north, up = E.enu(lat, lon)
        az = math.degrees(math.atan2((Q - P) @ east, (Q - P) @ north))
        assert float(E.wrap180(az + lon)) == pytest.approx(b, abs=0.02)


# ------------------------------------------------------------------------------------------------ horizons
def test_flat_sphere_horizon_is_the_dip():
    flat = lambda X, Y: np.zeros(np.shape(X))
    h = np.array([2.5, 10.0, 1957.6])
    m = E.horizon_wedge([-11550.0] * 3, [-12490.0] * 3, [0.0] * 3, h, [-5.0, 0.0, 5.0], flat, flat)
    want = -np.degrees(np.arccos(R / (R + h)))
    assert np.allclose(m, want[:, None], atol=2e-3)


def test_wall_blocks_the_wedge_and_the_link():
    """A 300 m wall 5 km out along grid bearing 0: horizon = its exact elevation; Earth below it never links."""
    X0, Y0, D, Hw = -11550.0, -12490.0, 5000.0, 300.0
    wall = lambda X, Y: np.where((np.asarray(Y) > Y0 + D) & (np.asarray(Y) < Y0 + D + 400), Hw, 0.0)
    m = E.horizon_wedge([X0], [Y0], [0.0], [2.5], [-3.0, 0.0, 3.0], wall, wall)[0]
    O = E.stereo_unit(X0, Y0) * (R + 2.5)
    T = E.stereo_unit(X0, Y0 + D) * (R + Hw)                        # the near face is the highest elevation
    want = math.degrees(math.asin((T - O) @ E.stereo_unit(X0, Y0) / np.linalg.norm(T - O)))
    assert m[1] == pytest.approx(want, abs=0.02) and want > 3.0
    el = np.array([want - 1.0, want - 0.6, want + 0.1, want + 3.0])
    s = E.link_state(el, np.full(4, 0.5), np.full(4, m[1]))
    assert s["any_part"].tolist() == [False, False, True, True]
    assert s["centre+0.5deg"].tolist() == [False, False, False, True]
    assert s["centre+2deg"].tolist() == [False, False, False, True]


def test_sinusoidal_earth_over_flat_sphere_gives_analytic_windows():
    """el(t) = A sin(2 pi t / T) against a constant horizon: windows start and end at the analytic crossings."""
    n, T, A, r = 20000, 2000, 6.5, 0.95
    t = np.arange(n)
    el = A * np.sin(2 * np.pi * t / T)
    h = np.full(n, -0.097)                                          # the 2.5 m dip
    s = E.link_state(el, np.full(n, r), h)
    for c, thr in (("any_part", h[0] - r), ("centre+0.5deg", h[0] + 0.5), ("centre+2deg", h[0] + 2.0)):
        w = C.runs(s[c])
        a = math.asin(thr / A) * T / (2 * math.pi)                 # first upward crossing (before t = 0 if thr < 0)
        starts = (a + T * np.arange(-1, n // T + 1)) % n
        ends = (T / 2 - a + T * np.arange(-1, n // T + 1)) % n
        for s0, e0 in w:
            if s0 > 0:
                assert np.min(np.abs(starts - s0)) <= 1.0
            if e0 < n:
                assert np.min(np.abs(ends - e0)) <= 1.0
        assert s[c].mean() == pytest.approx(0.5 - math.asin(thr / A) / math.pi, abs=2e-3)
    const = E.link_state(np.full(10, 3.0), np.full(10, r), np.full(10, 1.0))
    assert const["any_part"].all() and const["centre+0.5deg"].all() and not const["centre+2deg"].any()


# ------------------------------------------------------------------------------------------------ windows and reader
def test_runs_encode_decode_roundtrip():
    rng = np.random.default_rng(3)
    for _ in range(20):
        m = rng.random(500) < rng.uniform(0.05, 0.95)
        w = C.runs(m)
        assert np.array_equal(C.windows_to_mask(C.decode_windows(C.encode_windows(w)), 500), m)
    assert C.runs(np.zeros(5, bool)).shape == (0, 2) and C.encode_windows(C.runs(np.zeros(5, bool))) == []
    assert C.runs(np.ones(4, bool)).tolist() == [[0, 4]]


def _tiny_doc():
    m = np.zeros(144, dtype=bool)
    m[10:40] = True
    m[100:130] = True
    win = C.encode_windows(C.runs(m))
    summ = C.summarize(C.runs(m), 144, 1 / 6)
    series = {mode: {c: win for c in C.CRITERIA} for mode in C.MODES}
    sums = {mode: {c: summ for c in C.CRITERIA} for mode in C.MODES}
    return {"format": C.EARTH_LINK_FORMAT, "version": 1, "time": {"start_utc": "2028-01-01 00:00", "step_min": 10, "n": 144},
            "points": {"BASE": {"windows": series, "summary": sums}},
            "legs": {"BASE->DEPOT": {"windows": series, "summary": sums}}, "mast": None}


def test_reader_queries_on_a_hand_made_series():
    doc = _tiny_doc()
    assert C.validate(doc) == []
    el = C.EarthLink(doc)
    assert not el.linked("BASE->DEPOT", 1.0)                       # epoch 6
    assert el.linked("BASE->DEPOT", 10 / 6)                         # epoch 10 starts the window
    assert not el.linked("BASE->DEPOT", 40 / 6)                     # end is exclusive
    assert el.next_change("BASE->DEPOT", 2.0) == (True, pytest.approx((40 - 12) / 6))
    assert el.next_change("BASE->DEPOT", 7.0) == (False, pytest.approx((100 - 42) / 6))
    assert el.next_change("BASE->DEPOT", 22.0) == (False, math.inf)
    assert el.linked("BASE", 24.0 + 2.0, wrap=True)                # wraps past the 24 h series
    with pytest.raises(ValueError):
        el.linked("BASE", 30.0)
    s = el.summary("BASE")
    assert s["fraction"] == pytest.approx(60 / 144, abs=1e-5) and s["n_windows"] == 2
    assert s["max_gap_h"] == pytest.approx(60 / 6)                  # 40 -> 100
    with pytest.raises(KeyError):
        el.windows("NOPE")


def test_validate_catches_bad_windows():
    doc = _tiny_doc()
    doc["legs"]["BASE->DEPOT"]["windows"]["dte"]["any_part"] = [10, 30, 0, 5]   # zero gap -> overlapping/adjacent
    doc["points"]["BASE"]["windows"]["dte"]["centre+2deg"] = [100, 50]          # runs past n
    errs = C.validate(doc)
    assert any("legs.BASE->DEPOT.dte.any_part" in e for e in errs)
    assert any("points.BASE.dte.centre+2deg" in e for e in errs)


# ------------------------------------------------------------------------------------------------ SPICE and the data file
def test_earth_topo_equals_azlcpo():
    if not os.path.isfile(os.path.join(E.KDIR, "de440s.bsp")):
        pytest.skip("SPICE kernels not in .cache/comms (run tools/comms/earth_link.py ephem)")
    sp = E.furnsh_all()
    X, Y, z = -11550.0, -12490.0, 1957.6
    lat, lon = (float(v) for v in E.latlon_deg(X, Y))
    P = E.stereo_unit(X, Y) * (R + z) / 1000
    ets = sp.str2et("2029-06-01 00:00 UTC") + 3600.0 * np.arange(0, 700, 37)
    Eb = np.array([sp.spkcpo("EARTH", float(et), "MOON_ME", "OBSERVER", "LT+S", P, "MOON", "MOON_ME")[0][:3] for et in ets])
    az, el, brg, rad = E.earth_topo(Eb, P, P, lat, lon)
    for k, et in enumerate(ets):
        st, _ = sp.azlcpo("ELLIPSOID", "EARTH", float(et), "LT+S", False, True, P, "MOON", "MOON_ME")
        assert abs(float(E.wrap180(math.degrees(st[1]) - az[k]))) < 1e-9
        assert abs(math.degrees(st[2]) - el[k]) < 1e-9
    assert np.all(np.abs(brg) < 12.0)                               # inside the mask wedge


def test_committed_earth_link_file():
    if not os.path.isfile(DATA):
        pytest.skip("earth_link-v1.json not generated")
    assert os.path.getsize(DATA) < 1024 * 1024
    with open(DATA, encoding="utf-8") as f:
        doc = json.load(f)
    assert C.validate(doc) == []
    el = C.EarthLink(doc)
    assert el.n == 1461 * 144 and el.step_h == pytest.approx(1 / 6)
    assert el.summary("ISRU")["fraction"] == 0.0                      # never sees Earth (PDS map: 0)
    assert 0.45 <= el.summary("BASE")["fraction"] <= 0.65
    assert set(doc["points"]) >= {"BASE", "DEPOT", "POWER", "CONSTR", "ISRU", "SCI_1", "PSR", "PAD_A@1", "PAD_B@1"}
    assert len(doc["legs"]) == 182
    sha = open(DATA + ".sha256").read().split()[0]
    assert sha == E.sha256(DATA)


def test_samples_file_agrees_with_the_leg_windows():
    """Hourly per-sample series (conservative): when every sample of a leg is linked for an hour, the leg is too."""
    if not os.path.isfile(DATA):
        pytest.skip("earth_link-v1.json not generated")
    el = C.EarthLink.load(DATA, samples=True)
    with open(DATA + ".sha256") as f:
        assert f.read().split()[0] == E.sha256(DATA)
    assert el.doc["samples_file"]["sha256"] == E.sha256(os.path.join(os.path.dirname(DATA), el.doc["samples_file"]["file"]))
    rng = np.random.default_rng(0)
    checked = 0
    for leg in ("BASE->DEPOT", "POWER->CONSTR", "PAD_A@1->BASE", "BASE->PSR"):
        ids = el.leg_samples(leg)
        assert len(ids) == el.doc["legs"][leg]["n_samples"]
        for t in rng.uniform(0, el.horizon_h - 2, 40):
            h = math.floor(t)
            if all(el.sample_wait_h(i, h) == 0.0 for i in ids):
                assert el.linked(leg, h + 0.5)
                checked += 1
    assert checked > 10
    assert el.sample_wait_h(el.leg_samples("BASE->ISRU")[-1], 10.0) == math.inf     # ISRU never sees Earth


# ------------------------------------------------------------------------------------------------ B-52 lighting routes
SAMPLES_V2 = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v2-samples.json.gz")
LITE_V2 = SAMPLES_V2.replace(".json.gz", "-lite.json.gz")


def _gz(path):
    import gzip
    with open(path, "rb") as f:
        return json.loads(gzip.decompress(f.read()))


def test_route_ids_snap_dedupe_and_keep_the_sites():
    cells = {}

    def add(cx, cy):
        return cells.setdefault((cx, cy), 100 + len(cells))

    poly = np.array([[5.0, 5.0], [5.0, 405.0], [255.0, 405.0]])     # 650 m, one corner
    ids = E.route_ids(poly, 0, 1, add)
    assert ids[0] == 0 and ids[-1] == 1 and len(ids) == 8          # 7 steps of ~93 m: 6 interior samples
    assert all(a != b for a, b in zip(ids, ids[1:]))
    assert all(cx % 20 == 10 and cy % 20 == 10 for cx, cy in cells)
    assert E.cell_of(0.0, 19.999) == (10.0, 10.0) and E.cell_of(-0.1, 20.0) == (-10.0, 30.0)
    assert E.route_ids(np.array([[5.0, 5.0], [5.0, 6.0]]), 0, 1, add) == [0, 1]


def test_validate_samples_catches_bad_routes():
    doc = {"format": C.EARTH_LINK_SAMPLES_FORMAT, "version": 2, "time": {"n": 10}, "criteria": ["any_part"],
           "lighting": ["0", "night"], "series": [[0, 4], [2, 3]],
           "samples": [{"xy_m": [0, 0], "id": "A", "mast_los": True, "w": [0]},
                       {"xy_m": [10, 10], "id": None, "mast_los": False, "w": [1]},
                       {"xy_m": [20, 20], "id": "B", "mast_los": False, "w": [0]}],
           "legs": {"A->B": [0, 1, 2]}, "routes": {"A->B": {"0": [0, 2], "night": [0, 1, 2]}}}
    assert C.validate_samples(doc) == []
    bad = json.loads(json.dumps(doc))
    bad["routes"]["A->B"]["0"] = [1, 2]
    assert any("from sample A" in e for e in C.validate_samples(bad))
    bad = json.loads(json.dumps(doc))
    bad["routes"]["A->B"].pop("night")
    assert any("one list per lighting" in e for e in C.validate_samples(bad))
    bad = json.loads(json.dumps(doc))
    bad["series"][1] = [8, 5]
    assert any("series[1]" in e for e in C.validate_samples(bad))
    bad = json.loads(json.dumps(doc))
    bad["samples"][1]["w"] = [7]
    assert any("samples[1].w" in e for e in C.validate_samples(bad))


def test_samples_v2_extends_v1_unchanged():
    """v2 = the v1 samples file as a prefix (the engine's ids, series and leg lists) + the lighting routes."""
    if not os.path.isfile(SAMPLES_V2):
        pytest.skip("earth_link-v2-samples.json.gz not generated")
    v1_path = os.path.join(os.path.dirname(SAMPLES_V2), "earth_link-v1-samples.json.gz")
    v1, v2 = _gz(v1_path), _gz(SAMPLES_V2)
    assert C.validate_samples(v2) == []
    assert v2["v1_prefix"]["sha256"] == E.sha256(v1_path)
    n1, s1 = len(v1["samples"]), len(v1["series"])
    assert v2["samples"][:n1] == v1["samples"] and v2["series"][:s1] == v1["series"]
    assert v2["legs"] == v1["legs"] and v2["time"] == v1["time"] and v2["criteria"] == v1["criteria"]
    assert v2["lighting"] == ["0", "90", "180", "270", "night"]
    assert all(all(per[L] for L in v2["lighting"]) for per in v2["routes"].values())
    assert set(v2["night_legs_off_v1"]) == {k for k, per in v2["routes"].items() if per["night"] != v2["legs"][k]}
    lite = _gz(LITE_V2)
    assert C.validate_samples(lite) == [] and lite["criteria"] == ["any_part"]
    assert lite["routes"] == v2["routes"] and lite["legs"] == v2["legs"]
    for i in range(0, len(v2["samples"]), 97):
        assert lite["series"][lite["samples"][i]["w"][0]] == v2["series"][v2["samples"][i]["w"][0]]


def test_samples_v2_lie_on_the_routes_v1_routes():
    """Interior samples sit on the 20 m cell centre nearest the routes-v1 route (<= 10 sqrt 2 m off it)."""
    if not os.path.isfile(SAMPLES_V2):
        pytest.skip("earth_link-v2-samples.json.gz not generated")
    from lunarsim.rover.routes import decode_geom
    v2 = _gz(SAMPLES_V2)
    rpath = os.path.join(ROOT, v2["routes_file"]["file"])
    rdoc = json.load(open(rpath, encoding="utf-8"))
    assert v2["routes_file"]["sha256"] == E.sha256(rpath)            # rebuild samples2 after routes-v1 changes
    for leg in ("BASE->PSR", "PSR->BASE", "BASE->POWER", "PAD_A@1->DEPOT", "SCI_1->ISRU"):
        for L in v2["lighting"]:
            g = decode_geom(rdoc["geoms"][rdoc["legs"][leg][L]["geom"]])
            A = np.stack([g["x"][:-1], g["y"][:-1]], 1)
            AB = np.stack([np.diff(g["x"]), np.diff(g["y"])], 1)
            L2 = np.maximum((AB ** 2).sum(1), 1e-12)
            ids = v2["routes"][leg][L]
            a, b = leg.split("->")
            assert v2["samples"][ids[0]]["id"] == a and v2["samples"][ids[-1]]["id"] == b
            for i in ids[1:-1]:
                p = np.asarray(v2["samples"][i]["xy_m"], float)
                t = np.clip(((p - A) * AB).sum(1) / L2, 0.0, 1.0)
                assert np.hypot(*(A + t[:, None] * AB - p).T).min() <= 10 * math.sqrt(2) + 0.1, (leg, L, i)
            assert v2["lengths_m"][leg][L] == pytest.approx(g["s"][-1], abs=0.1)


def test_route_ties_summary_matches_the_data():
    """results/E21_route_ties.json (earth_link.py ties): the link-share part is recomputed from the committed v2
    samples (integer hour counts); the geometry needs the git-ignored B-40 routes, so it is checked for consistency."""
    path = os.path.join(ROOT, "results", "E21_route_ties.json")
    if not (os.path.isfile(path) and os.path.isfile(SAMPLES_V2)):
        pytest.skip("E21_route_ties.json or the v2 samples not generated")
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    v2 = _gz(SAMPLES_V2)
    assert doc["sources"]["samples_v2"]["sha256"] == E.sha256(SAMPLES_V2)
    assert doc["sources"]["routes_v1"]["sha256"] == E.sha256(os.path.join(ROOT, "data", "driving", "routes-v1.json"))
    assert doc["linked_share"] == E.route_tie_linked(v2)
    g, n = doc["geometry"], doc["legs_compared"]
    assert n == len(v2["legs"]) == 182
    assert 0 <= g["legs_differing_gt_20m"] <= g["legs_differing_gt_2m"] <= n
    assert g["legs_differing_gt_20m"] <= doc["sample_lists_differing"] == len(v2["night_legs_off_v1"])
    assert g["max_leg"] in v2["night_legs_off_v1"] and g["max_m"] > 20.0
    with open(DATA, encoding="utf-8") as f:
        el = json.load(f)
    worst = max(abs(el["legs"][k]["length_m"] - v2["lengths_m"][k]["night"]) for k in v2["legs"]
                if el["legs"][k].get("length_m") is not None)                      # both rounded to 0.1 m
    assert worst <= 0.15 and doc["length"]["max_abs_diff_m"] <= worst + 0.05
