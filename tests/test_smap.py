"""B-92: coordinates (lunarsim/atc/geo.py), the shared map (lunarsim/atc/smap.py) and the E52 files."""
import json
import math
import os

import numpy as np
import pytest

from lunarsim.atc import geo as G
from lunarsim.atc import smap as S

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_tile_centre_and_round_trips():
    lat, lon = G.site_to_latlon(8000.0, 8000.0)            # note 02 E1: tile centre 89.4632 S, 222.5104 E
    assert float(lat) == pytest.approx(-89.4632, abs=1e-4) and float(lon) == pytest.approx(222.5104, abs=1e-4)
    rng = np.random.default_rng(0)
    d = G.base_datum()
    assert np.allclose(d.Q @ d.Q.T, np.eye(3), atol=1e-12)
    for _ in range(200):
        la, lo, h = -89.0 - rng.random(), rng.uniform(0, 360), rng.uniform(-500, 2000)
        enu = d.me_to_enu(la, lo, h)
        la2, lo2, h2 = d.enu_to_me(enu)
        p_back = G.latlon_to_cart(float(la2), float(lo2), float(h2))
        assert np.linalg.norm(p_back - G.latlon_to_cart(la, lo, h)) < 1e-6
        X, Y = G.latlon_to_grid(la, lo)
        la3, lo3 = G.grid_to_latlon(X, Y)
        assert float(la3) == pytest.approx(la, abs=1e-9) and (float(lo3) - lo + 180) % 360 - 180 == pytest.approx(0, abs=1e-9)


def test_enu_basis_matches_note02_e1():
    Q = G.enu_basis(-89.4632, 222.5104)
    assert np.allclose(Q[0], [0.6757, -0.7372, 0.0], atol=1e-4)
    assert np.allclose(Q[1], [-0.7371, -0.6757, 0.0094], atol=1e-4)
    assert np.allclose(Q[2], [-0.0069, -0.0063, -1.0000], atol=1e-4)


def test_pa_versus_me_shift_matches_spice_values():
    """Note 02 E1 (SPICE pxform): 662.86 m at the pole, 659.22 m at the tile centre, 875.23 m at (0, 0); at the tile
    centre east -444.3, north +487.0, up -0.125 m when ME numbers are read as PA."""
    norm = lambda la, lo: float(np.linalg.norm(G.frame_mixup_shift(la, lo)))
    assert norm(-90.0, 0.0) == pytest.approx(662.86, abs=0.05)
    assert norm(-89.4632, 222.5104) == pytest.approx(659.22, abs=0.05)
    assert norm(0.0, 0.0) == pytest.approx(875.23, abs=0.05)
    e, n, u = G.frame_mixup_shift(-89.4632, 222.5104)
    assert e == pytest.approx(-444.3, abs=0.3) and n == pytest.approx(487.0, abs=0.3) and u == pytest.approx(-0.125, abs=0.01)


def test_stereographic_scale_note02_e2():
    """k - 1 = tan^2(d / 2R): 207 ppm at 50 km from the pole; rho - d = 3.45 m."""
    d = 50000.0
    c = d / G.R_MOON
    rho = 2 * G.R_MOON * math.tan(c / 2)
    assert (G.grid_scale(rho, 0.0) - 1.0) * 1e6 == pytest.approx(207, abs=1)
    assert rho - d == pytest.approx(3.45, abs=0.01)


def test_tree_walk_bound_and_sync_order():
    base, copy = S.TileMap(), S.TileMap()
    rng = np.random.default_rng(1)
    tiles = {(int(rng.integers(0, 63)), int(rng.integers(0, 63))) for _ in range(42)}
    for i, t in enumerate(sorted(tiles)):
        for layer in ("hazard", "traversability", "elevation1"):
            base.bump(layer, t, float(i))
    n = len(tiles)
    D = S.quadtree_depth(S.tiles_per_side("hazard"))
    b, ch = S.tree_walk_bytes(base, copy, "hazard")
    assert set(ch) == tiles and b <= S.HASH_B * (1 + 4 * n * D)          # note 02 E4 bound (8,072 B at n = 42)
    assert S.HASH_B * (1 + 4 * 42 * 6) == 8072
    assert S.flat_manifest_bytes("hazard") == 63 * 63 * 10
    route = sorted(tiles)[:5]
    ov, items = S.sync_plan(base, copy, route, "hazards_first")
    kinds = [it[0] for it in items]
    assert kinds[:5] == ["hazard_route"] * 5 and kinds.index("traversability") > max(i for i, k in enumerate(kinds) if k.startswith("hazard"))
    th, ta = S.time_hazards_current(ov, items, 16000.0, 0.2)
    ov2, items2 = S.sync_plan(base, copy, route, "oldest_first")
    th2, ta2 = S.time_hazards_current(ov2, items2, 16000.0, 0.2)
    assert th < th2 and ta == pytest.approx(ta2)
    assert S.tree_walk_bytes(base, base.copy(), "hazard") == (S.HASH_B, [])   # equal maps: one root hash


def test_contribution_rule():
    a = S.Authority()
    assert a.submit(S.Contribution("A", (1, 1), 3.0, 0.2), 0.0).startswith("rejected: position")
    assert a.submit(S.Contribution("A", (1, 1), 1.0, 1.5), 0.0).startswith("rejected: height")
    assert a.submit(S.Contribution("A", (1, 1), 1.0, 0.2, frame_ok=False), 0.0).startswith("rejected: frame")
    assert a.submit(S.Contribution("A", (1, 1), 1.0, 0.2), 1.0) == "accepted: provisional"
    assert a.submit(S.Contribution("A", (1, 1), 1.0, 0.2), 2.0) == "accepted: provisional"     # same owner, same pass
    assert a.submit(S.Contribution("B", (1, 1), 1.0, 0.2), 3.0) == "accepted: confirmed"
    assert S.Authority.growth_radius_m(1.5) == pytest.approx(4.5)
    assert a.map.v["hazard"][(1, 1)] == 3 and len(a.log) == 6


def test_confirmed_tile_is_not_provisional():
    """B-119 C10: a valid report on an already-confirmed tile is logged as such, not as provisional; and the same owner
    on another pass confirms (the review's two smap tests)."""
    a = S.Authority()
    a.submit(S.Contribution("A", (2, 2), 1.0, 0.2, pass_id=1), 1.0)
    assert a.submit(S.Contribution("A", (2, 2), 1.0, 0.2, pass_id=2), 2.0) == "accepted: confirmed"   # other pass
    assert a.submit(S.Contribution("C", (2, 2), 1.0, 0.2), 3.0) == "accepted: already confirmed"
    assert a.log[-1][2] == "accepted: already confirmed" and (2, 2) in a.confirmed


def test_e52_outputs():
    p = os.path.join(ROOT, "results", "E52_map.json")
    if not os.path.isfile(p):
        pytest.skip("E52 not run")
    d = json.load(open(p))
    # B-119: the verdict recomputed from the rows (after 24 h: hazards-first bytes < 10 % of a full resend at
    # 100 kbit/s, and the hazard layer current sooner than oldest-first at every link rate)
    R = {(r["out_h"], r["order"], r["rate_kbps"]): r for r in d["rows"]}
    share = R[(24, "hazards_first", 100)]["share_of_full_resend"]
    rates = sorted({r["rate_kbps"] for r in d["rows"]})
    sooner = all(R[(24, "hazards_first", k)]["t_hazards_current_s"] < R[(24, "oldest_first", k)]["t_hazards_current_s"]
                 for k in rates)
    assert d["h12"]["supported"] is bool(share < 0.10 and sooner)
    rows = {(r["out_h"], r["order"], r["rate_kbps"]): r for r in d["rows"]}
    assert rows[(24, "hazards_first", 16)]["t_hazards_current_s"] < rows[(24, "oldest_first", 16)]["t_hazards_current_s"]
    assert rows[(1, "hazards_first", 100)]["bytes_mean"] <= rows[(336, "hazards_first", 100)]["bytes_mean"]
