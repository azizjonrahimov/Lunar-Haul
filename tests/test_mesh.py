"""B-70: robot-to-robot radio visibility (tools/atc/mesh.py, lunarsim/atc/radio.py, data/atc/.../mesh-v1.json.gz)."""
import hashlib, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "atc"))
import numpy as np
import pytest

import mesh as M  # noqa: E402
from lunarsim.terrain import MOON_RADIUS_M  # noqa: E402

R = MOON_RADIUS_M
FILE = M.OUT
PX = 5.0


def line_grid(z_of_x, length_m=12000.0):
    """3 rows x length/5 columns; the points sit on the middle row (y = 7.5 m)."""
    x = (np.arange(int(length_m / PX)) + 0.5) * PX
    return M.GridTerrain(np.tile(z_of_x(x), (3, 1)), PX)


def clearance(t, d, ha, hb, radius_m, x0=100.0):
    P = np.array([[x0, 7.5], [x0 + d, 7.5]])
    cl, _ = M.pair_profiles(t, P, [0], [1], [(ha, hb)], radius_m=radius_m)
    return cl[0, 0]


def horizon(t, ha, hb, radius_m):
    lo, hi = 100.0, 11000.0
    while hi - lo > 0.5:
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if clearance(t, mid, ha, hb, radius_m) > 0 else (lo, mid)
    return lo


@pytest.mark.parametrize("ha,hb", [(2.5, 2.5), (2.5, 1.0), (1.0, 10.0)])
def test_smooth_sphere_reproduces_the_horizon_formula(ha, hb):
    want = math.sqrt(2 * R * ha) + math.sqrt(2 * R * hb)            # 5.89 km for 2.5 m at both ends
    xc = 3000.0
    sphere = line_grid(lambda x: -(x - xc) ** 2 / (R + np.sqrt(R * R - (x - xc) ** 2)))   # the sphere in a tangent frame
    assert abs(horizon(sphere, ha, hb, math.inf) - want) <= PX                            # curvature from the DEM
    assert abs(horizon(line_grid(lambda x: 0 * x), ha, hb, R) - want) <= PX               # curvature as the chord bulge
    if (ha, hb) == (2.5, 2.5):
        assert abs(want - 5894.7) < 0.5


def test_flat_dem_gives_los_for_every_pair():
    t = M.GridTerrain(np.full((400, 400), 123.0), PX)
    rng = np.random.default_rng(0)
    P = rng.uniform(10, 1990, size=(30, 2))
    I, J = np.triu_indices(len(P), 1)
    for radius in (math.inf, R):
        cl, ra = M.pair_profiles(t, P, I, J, M.COMBOS, radius_m=radius)
        assert (cl > 0).all() and (ra > 0).all()


def test_ridge_blocks_the_pair_across_it():
    t = line_grid(lambda x: np.where((x > 500) & (x < 520), 30.0, 0.0), 2000.0)
    P = np.array([[100.0, 7.5], [900.0, 7.5], [600.0, 7.5]])
    cl, _ = M.pair_profiles(t, P, [0, 2], [1, 1], M.COMBOS + M.MAST_COMBOS)
    assert (cl[:, 0] < -15).all()                  # across the 30 m ridge, even from the 10 m mast
    assert (cl[:, 1] > 0).all()                    # both on the same side


def test_encodings_are_exact_at_thresholds():
    c = np.array([-0.05, 0.0, 1e-9, 0.1, 0.95, 1.0, 1.0000001, 3.2])
    q = M.encode_clear(c)
    assert ((q >= 0) == (c > 0)).all() and ((q >= 10) == (c > 1.0)).all()
    r = np.array([-0.3, -0.001, 0.0, 0.59, 0.5999, 0.6, 0.61, 2.6, np.inf])
    f = M.encode_fresnel(r)
    assert ((f >= 61) == (r >= 0.6)).all() and ((f >= 1) == (r >= 0)).all() and f[-1] == 255


@pytest.fixture(scope="module")
def rm():
    if not os.path.isfile(FILE):
        pytest.skip("mesh file not built")
    from lunarsim.atc.radio import RadioMesh
    return RadioMesh(FILE)


def test_file_sha256_matches():
    if not os.path.isfile(FILE):
        pytest.skip("mesh file not built")
    want = open(FILE + ".sha256", encoding="utf-8").read().split()[0]
    assert hashlib.sha256(open(FILE, "rb").read()).hexdigest() == want


def test_links_are_symmetric(rm):
    rng = np.random.default_rng(1)
    for _ in range(400):
        a, b = (int(x) for x in rng.integers(0, rm.n, 2))
        for ha, hb in ((2.5, 2.5), (2.5, 1.0), (1.0, 1.0)):
            for kw in ({}, {"margin_m": 1.0}, {"fresnel_min": 0.6, "freq_hz": 400e6}, {"d_max_m": 10000.0}):
                assert rm.link(a, b, ha, hb, **kw) == rm.link(b, a, hb, ha, **kw)
        if a != rm.base:
            assert rm.link(rm.base, a, 10.0, 2.5) == rm.link(a, rm.base, 2.5, 10.0)
    G = rm.graph(2.5, d_max_m=2000.0)
    assert (G != G.T).nnz == 0
    nb = rm.neighbours(100, 1.0, d_max_m=5000.0)
    assert all(100 in rm.neighbours(int(k), 1.0, d_max_m=5000.0) for k in nb[:20])


def test_file_agrees_with_terrain_los(rm):
    from lunarsim.terrain import Terrain
    t = Terrain(M.EL.PACK)
    rng = np.random.default_rng(2)
    for _ in range(60):
        a, b = (int(x) for x in rng.integers(1, rm.n, 2))
        if a == b:
            continue
        for ha, hb in ((2.5, 1.0), (1.0, 1.0)):
            c = t.los_clearance_m(tuple(rm.xy[a]), tuple(rm.xy[b]), h_a=ha, h_b=hb)
            if abs(c) > 1e-6 and abs(c - 1.0) > 1e-6:
                assert rm.link(a, b, ha, hb, d_max_m=1e5) == (c > 0)
                assert rm.link(a, b, ha, hb, d_max_m=1e5, margin_m=1.0) == (c > 1.0)
        c = t.los_clearance_m(tuple(rm.xy[0]), tuple(rm.xy[a]), h_a=10.0, h_b=2.5)
        if abs(c) > 1e-6:
            assert rm.link(0, a, 10.0, 2.5, d_max_m=1e5) == (c > 0)


def test_hops_and_range(rm):
    h = rm.hops(rm.base, 2.5, d_max_m=5000.0)
    assert h[rm.base] == 0
    one = np.where(h == 1)[0]
    assert all(rm.link(rm.base, int(k), 10.0, 2.5) for k in one[:50])
    assert not rm.link(0, 1, 2.5, 2.5, d_max_m=float(rm.d[0]) - 1e-6)
    with pytest.raises(ValueError):
        rm.link(5, 6, 10.0, 2.5)                    # the mast stands only at BASE
    with pytest.raises(ValueError):
        rm.link(5, 6, 2.5, 2.5, margin_m=0.25)      # the file resolves 0.1 m
