"""B-61 (tools/comms/parking.py): parking points for a helper that sees both Earth and the held rover.
Helpers on synthetic data; the committed data/comms/connecting_ridge/parking-v1.json and results/E21_parking.json
against their inputs (no simulation, no masks)."""
import gzip, json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "comms"))
import numpy as np
import pandas as pd
import pytest

import parking as P  # noqa: E402
from lunarsim import comms as C  # noqa: E402

OUT = P.OUT
SUMMARY = P.SUMMARY
need_out = pytest.mark.skipif(not (os.path.isfile(OUT) and os.path.isfile(SUMMARY)), reason="B-61 outputs not built")


@pytest.fixture(scope="module")
def terrain():
    from lunarsim.terrain import Terrain
    return Terrain(P.EL.PACK)


@pytest.fixture(scope="module")
def sdoc():
    return P._load_samples()


@pytest.fixture(scope="module")
def doc():
    with open(OUT, encoding="utf-8") as f:
        return json.load(f)


def test_waits_from_windows_equal_waits_from_masks():
    rng = np.random.default_rng(0)
    n = 500
    for _ in range(20):
        m = rng.random(n) < rng.uniform(0.02, 0.6)
        m[: rng.integers(0, 50)] = bool(rng.integers(0, 2))
        W = P.wait_until_linked(m)
        hours = rng.integers(0, n, size=200)
        assert np.array_equal(P.waits_at(C.runs(m), hours, n), W[hours])
    assert P.wait_until_linked(np.array([False, True, False, False]))[2:].tolist() == [3.0, 2.0]   # wraps after the end
    assert np.isinf(P.waits_at(np.zeros((0, 2), dtype=int), np.array([0, 3]), 4)).all()


def test_batch_clearance_is_terrain_los_clearance(terrain, sdoc):
    xy = np.array([s["xy_m"] for s in sdoc["samples"]])
    rng = np.random.default_rng(1)
    i, j = rng.integers(0, len(xy), size=40), rng.integers(0, len(xy), size=40)
    got = P.los_batch(terrain, xy[i], xy[j])
    want = [terrain.los_clearance_m(tuple(xy[a]), tuple(xy[b]), h_a=2.5, h_b=2.5) for a, b in zip(i, j)]
    assert got.tolist() == want                                              # same arithmetic, bit for bit


def test_route_network_is_connected_and_keeps_leg_lengths(sdoc):
    from scipy.sparse.csgraph import connected_components
    with open(P.LINK_V1, encoding="utf-8") as f:
        link = json.load(f)
    G, xy = P.network(sdoc, link)
    assert connected_components(G, directed=False)[0] == 1
    leg = "BASE->DEPOT"
    ids = sdoc["legs"][leg]
    along = sum(G[min(a, b), max(a, b)] for a, b in zip(ids[:-1], ids[1:]))
    assert along == pytest.approx(link["legs"][leg]["length_m"], rel=1e-9)


@need_out
def test_parking_file_matches_its_inputs(doc, sdoc):
    assert doc["samples_file"]["sha256"] == P.EL.sha256(P.SAMPLES_V1)
    for rel, sha in doc["inputs"].items():                    # the committed inputs (caches may be absent here)
        if rel.startswith(("data/", "results/")):
            assert P.EL.sha256(os.path.join(ROOT, rel)) == sha, rel
    n = doc["time"]["n"]
    assert n == sdoc["time"]["n"]
    never = {i for i, s in enumerate(sdoc["samples"]) if not sdoc["series"][s["w"][0]]}
    assert doc["set_h"]["never_linked"] == len(never) and {int(s) for s in doc["samples"]} >= never | {188}
    assert doc["no_working_point"] == []


@need_out
def test_ranking_and_coverage_are_consistent(doc, sdoc):
    n = doc["time"]["n"]
    pts = doc["points"]
    for s, r in doc["samples"].items():
        top = r["top"]
        keys = [(-t["share"][1], -t["share"][2], -t["dark_share"][2], t["drive_km"]) for t in top]
        assert keys == sorted(keys), s
        assert top[0]["share"] == r["coverage"]["best"]
        for m, v in r["coverage"].items():
            assert v == sorted(v), (s, m)                                    # within 0 <= 24 <= 168 h
            assert all(a <= b + 1e-12 for a, b in zip(v, r["coverage"]["all"])), (s, m)
        lk = C.windows_to_mask(C.decode_windows(sdoc["series"][sdoc["samples"][int(s)]["w"][0]]), n)
        assert r["dark_hours"]["n"] == int((~lk).sum()) and r["never_linked"] == (not lk.any())
        assert r["basis"] == "calls" or r["n_basis"] == r["dark_hours"]["n"]
    for p in pts:
        if p["kind"] == "route":
            w = C.decode_windows(sdoc["series"][sdoc["samples"][p["sample"]]["w"][0]])
        else:
            w = C.decode_windows(p["windows"])
            assert len(w) == 0 or (w[0, 0] >= 0 and w[-1, 1] <= n)
        frac = float((w[:, 1] - w[:, 0]).sum()) / n if len(w) else 0.0
        assert p["link_fraction"] == round(frac, 5)


@need_out
def test_best_points_see_the_sample_and_grid_points_are_reached(doc, sdoc, terrain):
    from lunarsim.rover.expert import plan
    xy = np.array([s["xy_m"] for s in sdoc["samples"]])
    pts = doc["points"]
    for s in ("188", "4", "189", "230"):
        t = doc["samples"][s]["top"][0]
        p = pts[t["point"]]
        c = terrain.los_clearance_m(tuple(p["xy_m"]), tuple(xy[int(s)]), h_a=2.5, h_b=2.5)
        assert c > 0 and round(c, 3) == t["clear_m"]
        assert t["dist_m"] == round(math.hypot(*(np.array(p["xy_m"]) - xy[int(s)])), 1)
    grid = [p for p in pts if p["kind"] == "grid"][:3]
    for p in grid:
        poly = plan(terrain, tuple(xy[p["near_sample"]]), tuple(p["xy_m"]), None)
        assert poly is not None and round(float(np.hypot(*np.diff(poly, axis=0).T).sum()), 1) == p["access_m"]


@need_out
def test_summary_tally_matches_stage_g2():
    with open(SUMMARY, encoding="utf-8") as f:
        sm = json.load(f)
    g2 = pd.read_csv(os.path.join(ROOT, "results", "E21g2_rescue_any_r2.csv"), float_precision="round_trip")
    for h in P.TALLY_H:
        rescues = int(g2.loc[g2["rescue_h"] == h, "blackout_rescues_never_linked"].sum())
        assert sm["tally"]["cells"][f"{h:g}"]["capped_waits"] == rescues
        assert sm["help_delay"]["call"][f"{h:g}"]["all"]["n"] == rescues
        u = sm["uncovered_calls"][f"{h:g}|all"]
        assert u["calls"] == rescues
        allv = sm["help_delay"]["call"][f"{h:g}"]["all"]["all"]
        assert u["uncovered_share"] == pytest.approx(1 - allv[2], abs=2e-5)
    assert sm["parking_file"]["sha256"] == P.EL.sha256(OUT)
