"""Scene packages (B-31, lunarsim/scene.py): determinism, reproduction of the trace, continuity, the samples."""
import collections, hashlib, json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

from lunarsim import scene as S
from lunarsim.formats import load_schema

TRACE = os.path.join(ROOT, "data", "sample_traces", "P2_marketplace_seed3_v2.json")
SCENES = os.path.join(ROOT, "data", "scenes")
ROUTES = os.path.join(ROOT, "data", "driving", "routes-v1.json")
needs = pytest.mark.skipif(not (os.path.isfile(TRACE) and os.path.isfile(ROUTES)), reason="sample trace or routes missing")


def _digest(folder):
    return {f: hashlib.sha256(open(os.path.join(folder, f), "rb").read()).hexdigest() for f in sorted(os.listdir(folder))}


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    trace = json.load(open(TRACE, encoding="utf-8"))
    a = str(tmp_path_factory.mktemp("a"))
    b = str(tmp_path_factory.mktemp("b"))
    S.build(trace, a)
    S.build(json.loads(json.dumps(trace)), b)
    return trace, a, b


def test_rdp_light_and_trajectory_helpers():
    line = np.column_stack([np.linspace(0, 100, 11), np.zeros(11), np.zeros(11)])
    assert S.rdp(line, 0.5) == [0, 10]
    bent = line.copy()
    bent[5, 1] = 3.0
    assert 5 in S.rdp(bent, 0.5)
    nights = [[100.0, 200.0]]
    assert S.light_key(150.0, nights) == "night" and S.light_key(0.0, nights) == "0"
    assert S.light_key(S.LUNAR_CYCLE_H / 4, []) == "90"
    doc = {"pilots": [{"cls": "CLPS", "pilot": "classical", "episodes": [
        {"pick": "p10", "seed": 1, "miss_m": 0.8}, {"pick": "p50", "seed": 2, "miss_m": 2.0},
        {"pick": "first_failure", "seed": 3, "miss_m": 0.3}]}]}
    assert S._nearest_trajectory(doc, "CLPS", 1.9, True)["seed"] == 2
    assert S._nearest_trajectory(doc, "CLPS", 1.9, False)["pick"] == "first_failure"
    assert S._nearest_trajectory(doc, "MK1", 1.0, True) is None


@needs
def test_deterministic_package(built):
    _, a, b = built
    assert _digest(a) == _digest(b)


@needs
def test_replay_reproduces_the_trace(built):
    trace, a, _ = built
    pkg = S.read(a)
    got = S.replay_counts(pkg)
    cols = {c: i for i, c in enumerate(trace["cargo_columns"])}
    delivered = round(sum(r[cols["mass_kg"]] for r in trace["cargo"] if r[cols["t_delivered"]] is not None), 3)
    assert got["delivered_kg"] == delivered                                  # the trace's cargo table, exactly
    assert abs(got["delivered_kg"] - trace["summary"]["delivered_kg"]) <= 0.05 * len(pkg["index"]["deliveries"])
    assert got["trips"] == sum(1 for j in trace["jobs"] if j["kind"] != "reposition") == trace["summary"]["jobs"]
    assert got["landings"] == len(trace["landings"])


@needs
def test_timelines_are_continuous_and_on_routes(built):
    trace, a, _ = built
    pkg = S.read(a)
    idx, seg = pkg["index"], pkg["segments"]
    c = {k: i for i, k in enumerate(idx["segment_columns"])}
    H = idx["horizon_h"]
    for v in idx["vehicles"]:
        m = seg[seg[:, c["veh"]] == v["id"]]
        m = m[np.argsort(m[:, c["t0"]], kind="stable")]
        assert m[0, c["t0"]] == 0 and m[-1, c["t1"]] == pytest.approx(H)
        assert np.max(np.abs(m[1:, c["t0"]] - m[:-1, c["t1"]])) < 1e-3          # float32 times
        jump = np.hypot(m[1:, c["x0"]] - m[:-1, c["x1"]], m[1:, c["y0"]] - m[:-1, c["y1"]])
        assert jump.max() < 0.05
    # a drive starts at its origin site and ends at its destination (job 0's legs)
    job = trace["jobs"][0]
    a_site, b_site, t0, t1, _ = job["segments"][2]
    x, y, _, state = S.position(pkg, job["veh"], t0 + 1e-4)
    assert math.hypot(x - idx["sites"][a_site][0], y - idx["sites"][a_site][1]) < 1.0 and state == "driving"
    x, y, _, _ = S.position(pkg, job["veh"], t1 - 1e-4)
    assert math.hypot(x - idx["sites"][b_site][0], y - idx["sites"][b_site][1]) < 2.0
    # every segment lies inside its chunk
    for ch in idx["chunks"]:
        raw = open(os.path.join(a, ch["file"]), "rb").read()
        sg = np.frombuffer(raw, dtype="<f4", count=ch["segments"]["rows"] * ch["segments"]["cols"]).reshape(-1, len(c))
        assert sg[:, c["t0"]].min() >= ch["t0"] - 1e-3 and sg[:, c["t1"]].max() <= ch["t1"] + 1e-3
    states = collections.Counter(idx["states"][int(s)] for s in seg[:, c["state"]])
    assert states["driving"] > 0 and states["loading"] > 0 and states["parked_night"] > 0


@needs
def test_hourly_waiting_and_sun(built):
    trace, a, _ = built
    pkg = S.read(a)
    idx, hr = pkg["index"], pkg["hourly"]
    assert hr.shape == (int(idx["horizon_h"]), len(idx["hourly_columns"]))
    sites = list(idx["sites"])
    cols = {c: i for i, c in enumerate(trace["cargo_columns"])}
    h = 1200
    want = sum(1 for r in trace["cargo"] if r[cols["origin"]] == "PAD_A" and r[cols["t_ready"]] <= h
               and (r[cols["t_picked"]] is None or r[cols["t_picked"]] > h))
    assert hr[h, idx["hourly_columns"].index("waiting_n_PAD_A")] == want
    assert hr[h, 0] == pytest.approx(S.sun_az_deg(h), abs=1e-3)
    if idx["earth"]["source"]:
        el = hr[:, idx["hourly_columns"].index("earth_el_deg")]
        assert -8.5 < el.min() < -6 and 5.5 < el.max() < 7.5                  # Earth's swing at the pole


@pytest.mark.skipif(not os.path.isdir(SCENES), reason="sample scenes not generated")
def test_committed_samples():
    import gzip
    for name in ("P1", "P2", "P3", "P2V2", "P2-comms-dte"):
        folder = os.path.join(SCENES, name)
        assert S.gz_size(folder) <= 2 * 1024 * 1024
        pkg = S.read(folder)
        idx = pkg["index"]
        for ch in idx["chunks"]:
            assert hashlib.sha256(open(os.path.join(folder, ch["file"]), "rb").read()).hexdigest() == ch["sha256"]
        got = S.replay_counts(pkg)
        assert got["trips"] == idx["checks"]["trips"] == idx["checks"]["trips_summary"]
        assert got["delivered_kg"] == idx["checks"]["delivered_kg_cargo_table"]
        assert got["landings"] == idx["checks"]["landings"]
        jsonschema = None
        try:
            import jsonschema
        except ImportError:
            pass
        if jsonschema:
            jsonschema.validate(idx, load_schema("scene-v1"))
    dte = S.read(os.path.join(SCENES, "P2-comms-dte"))
    c = {k: i for i, k in enumerate(dte["index"]["segment_columns"])}
    states = {dte["index"]["states"][int(s)] for s in dte["segments"][:, c["state"]]}
    assert "waiting_for_earth" in states and dte["index"]["comms"]["mode"] == "dte" and dte["index"]["comms_waits"]


def test_trajectory_mapping_uses_outcomes():
    """B-47: a good landing never shows a failed episode (the classical first failure has the smallest |miss|); a failed
    landing shows a failure of its own kind when the file has one."""
    ep = lambda pick, seed, miss, ok, kind=None: {"pick": pick, "seed": seed, "miss_m": miss,
                                                  "outcome": {"ok": ok, "failure_kind": kind}}
    doc = {"pilots": [{"cls": "CLPS", "pilot": "classical", "episodes": [
        ep("p10", 1, 0.8, True), ep("p50", 2, 2.0, True), ep("p90", 3, 4.5, True),
        ep("first_failure", 4, 0.3, False, "timeout"), ep("failure_velocity", 5, 6.0, False, "velocity")]}]}
    assert S._nearest_trajectory(doc, "CLPS", 0.3, True)["pick"] == "p10"
    assert S._nearest_trajectory(doc, "CLPS", 9.0, None)["pick"] == "p90"          # unjudged = treated as good
    assert S._nearest_trajectory(doc, "CLPS", 0.1, False, "velocity")["pick"] == "failure_velocity"
    assert S._nearest_trajectory(doc, "CLPS", 5.5, False, "tilt")["pick"] == "failure_velocity"   # nearest failure
    assert S._nearest_trajectory(doc, "CLPS", None, False, "lost")["pick"] == "first_failure"
    assert S._nearest_trajectory(doc, "CLPS", None, True) is None


@needs
def test_delivery_priority_and_wait(built):
    trace, a, _ = built
    idx = S.read(a)["index"]
    assert idx["delivery_columns"] == ["t_h", "site", "mass_kg", "priority", "wait_h"]
    ci = {c: i for i, c in enumerate(trace["cargo_columns"])}
    rows = sorted((r for r in trace["cargo"] if r[ci["t_delivered"]] is not None),
                  key=lambda r: (r[ci["t_delivered"]], r[ci["id"]]))
    assert len(rows) == len(idx["deliveries"])
    for d, r in zip(idx["deliveries"], rows):
        assert len(d) == 5 and d[3] == r[ci["priority"]] and d[3] in (1, 2, 3)
        assert d[4] == pytest.approx(r[ci["t_delivered"]] - r[ci["t_ready"]], abs=1e-4) and d[4] >= -1e-9


@needs
def test_committed_packages_landings_and_deliveries():
    gal = json.load(open(os.path.join(SCENES, "gallery.json"), encoding="utf-8"))
    for s in gal["scenes"]:
        idx = S.read(os.path.join(SCENES, s["package"]))["index"]
        assert idx.get("delivery_columns") == ["t_h", "site", "mass_kg", "priority", "wait_h"], s["package"]
        assert all(len(d) == 5 for d in idx["deliveries"])
        for L in idx["landings"]:
            if L["trajectory"] is not None and L["ok"] is not False:
                assert L["trajectory"]["pick"] != "first_failure", (s["package"], L)
