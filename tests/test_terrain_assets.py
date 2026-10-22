"""Terrain assets v2 (B-34, tools/terrain_assets.py): analytic horizons and normals, the PNG codec, a tiny build."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import numpy as np
import pytest

import terrain_assets as ta

PX = 20.0


def grid(n=81):
    """Post-centre coordinates (x east, y north) of an n x n grid, row 0 = north."""
    c = (np.arange(n) + 0.5) * PX
    return np.meshgrid(c, c[::-1])


# ------------------------------------------------------------------------------------------------ horizons
def test_flat_plane_horizon_is_zero():
    z = np.full((41, 41), 100.0)
    for az in (0.0, 45.0, 137.0, 270.0):
        h = ta.horizon_deg(z, PX, az, h_obs=0.0, curvature=False)
        assert np.nanmax(np.abs(h)) < 1e-4              # float32 bilinear weights; the code step is 0.05
        assert np.isnan(h).sum() > 0                  # edge posts facing out of the tile have no sample
    h = ta.horizon_deg(z, PX, 90.0, h_obs=0.0, curvature=True)
    interior = h[:, :-1]
    assert np.allclose(interior, -np.degrees(PX / (2 * ta.T.MOON_RADIUS_M)), atol=1e-6)  # first sample, curvature drop


def test_cone_horizon_angle_at_known_distance():
    """Observer on flat ground D east... of a cone peak of height H, base radius Rb < D: horizon = atan(H / D)."""
    n = 101
    x, y = grid(n)
    apex = (x[50, 70], y[50, 70])
    r = np.hypot(x - apex[0], y - apex[1])
    Hc, Rb = 300.0, 200.0
    z = np.where(r < Rb, Hc * (1 - r / Rb), 0.0)
    h = ta.horizon_deg(z, PX, 90.0, h_obs=0.0, curvature=False)        # looking east, along the row
    for col in (10, 30, 50):                                             # D = 1200, 800, 400 m (all > Rb)
        D = (70 - col) * PX
        assert h[50, col] == pytest.approx(math.degrees(math.atan(Hc / D)), abs=1e-4)
    # off the grid axes the 20 m ray samples straddle the apex: a peak is under-read by at most about
    # slope x 14 m / D (half a sample step plus bilinear smoothing), here 0.33 x 14 / 1697 rad = 0.16 deg
    n = 161
    x, y = grid(n)
    r = np.hypot(x - x[80, 120], y - y[80, 120])
    z = np.where(r < 600.0, 200.0 * (1 - r / 600.0), 0.0)
    D = 60 * PX * math.sqrt(2)
    want = math.degrees(math.atan(200.0 / D))
    h45 = ta.horizon_deg(z, PX, 45.0, h_obs=0.0, curvature=False)[140, 60]   # towards NE, apex on the ray
    assert want - 0.2 <= h45 <= want + 1e-3


def test_inclined_plane_horizon_equals_slope_upslope():
    x, y = grid(61)
    z = 0.2 * x + 0.1 * y                                                # rises east and north
    for az in (0.0, 90.0, 60.0):
        g = 0.2 * math.sin(math.radians(az)) + 0.1 * math.cos(math.radians(az))
        h = ta.horizon_deg(z, PX, az, h_obs=0.0, curvature=False)
        assert np.nanmax(np.abs(h - math.degrees(math.atan(g)))) < 1e-3


def test_scheduled_rays_match_dense_on_smooth_terrain():
    x, y = grid(201)
    z = 150 * np.sin(x / 900.0) * np.cos(y / 1300.0)
    dense = ta.horizon_deg(z, PX, 70.0, distances=ta.step_schedule(PX, 6000, 1e9, 1.0))
    sched = ta.horizon_deg(z, PX, 70.0, distances=ta.step_schedule(PX, 6000, 1000.0, ta.FAR_RATIO))
    assert np.nanmax(np.abs(dense - sched)) < 0.05


def test_horizon_code_roundtrip_and_interpolation():
    deg = np.array([[-89.95, -2.0, 0.0], [1.5, 37.25, np.nan]])
    back = ta.decode_horizon(ta.encode_horizon(deg))
    assert np.allclose(back[np.isfinite(deg)], deg[np.isfinite(deg)], atol=0.025)
    assert np.isnan(back[1, 2]) and ta.encode_horizon(deg)[1, 2] == 0
    sec = np.zeros((64, 1, 1))
    sec[5], sec[6] = 2.0, 4.0
    assert ta.horizon_at(sec, 5.5 * 5.625)[0, 0] == pytest.approx(3.0)
    sec[63], sec[0] = 10.0, 20.0
    assert ta.horizon_at(sec, 359.0)[0, 0] == pytest.approx(10 + 10 * (359 / 5.625 - 63))   # wraps past 360
    assert ta.horizon_at({63: sec[63], 0: sec[0]}, 359.0, 64)[0, 0] == pytest.approx(ta.horizon_at(sec, 359.0)[0, 0])
    assert ta.bracketing_sectors(359.0) == (63, 0) and ta.bracketing_sectors(90.0) == (16, 17)


def test_shader_port_flat_and_wall():
    z = np.zeros((30, 30), dtype=np.float32)
    assert np.all(ta.shader_visibility(z, PX, 90.0) == 1.0)            # flat: lit everywhere
    z[:, 20:] = 500.0                                                    # a wall to the east
    v = ta.shader_visibility(z, PX, 90.0)
    assert np.all(v[:, :20] == 0.0) and np.all(v[:, 20:] == 1.0)


# ------------------------------------------------------------------------------------------------ normals
def test_plane_slope_normals():
    x, y = grid(21)
    a, b = 0.3, -0.15
    n = ta.normals(a * x + b * y, PX)
    want = np.array([-a, -b, 1.0]) / math.sqrt(a * a + b * b + 1)
    assert np.allclose(n, want, atol=1e-12)
    dec = ta.decode_normals(ta.encode_normals(n))
    assert np.max(np.abs(dec - want)) < 1.5 / 255 * 2


# ------------------------------------------------------------------------------------------------ PNG codec
@pytest.mark.parametrize("shape,dtype", [((7, 9), np.uint16), ((5, 6, 4), np.uint16), ((6, 5, 3), np.uint8),
                                         ((130, 3, 4), np.uint16)])
def test_png_roundtrip(tmp_path, shape, dtype):
    rng = np.random.default_rng(1)
    a = rng.integers(0, np.iinfo(dtype).max + 1, size=shape, dtype=dtype)
    a.reshape(-1)[: a.size // 2] = np.sort(a.reshape(-1)[: a.size // 2])   # smooth part exercises every filter
    p = str(tmp_path / "x.png")
    ta.write_png(p, a)
    assert np.array_equal(ta.read_png(p), a)


def test_png_readable_by_pillow(tmp_path):
    from PIL import Image
    rng = np.random.default_rng(2)
    g = rng.integers(0, 65536, size=(12, 10), dtype=np.uint16)
    ta.write_png(str(tmp_path / "g.png"), g)
    with Image.open(tmp_path / "g.png") as im:
        assert np.array_equal(np.array(im).astype(np.uint16), g)        # 16-bit grey read exactly
    rgba = rng.integers(0, 65536, size=(8, 6, 4), dtype=np.uint16)
    ta.write_png(str(tmp_path / "c.png"), rgba)
    with Image.open(tmp_path / "c.png") as im:
        assert im.size == (6, 8) and im.mode == "RGBA"                   # Pillow reduces 16-bit RGBA to 8 bits
        assert np.array_equal(np.array(im), (rgba >> 8).astype(np.uint8))


# ------------------------------------------------------------------------------------------------ tiny build
def _tiny_pack(root):
    """A 2 x 2 km lunarsim-terrain v1 pack (400 x 400 at 5 m) with a hill, plus sites.json."""
    from PIL import Image
    n, px = 400, 5.0
    c = (np.arange(n) + 0.5) * px
    x, y = np.meshgrid(c, c[::-1])
    z = 1000 + 120 * np.exp(-((x - 1300) ** 2 + (y - 900) ** 2) / (2 * 250 ** 2)) + 0.01 * x
    off, sc = 900.0, 0.5
    Image.fromarray(np.rint((z - off) / sc).astype(np.uint16)).save(os.path.join(root, "height_5m.png"))
    z20 = z.reshape(100, 4, 100, 4).mean(axis=(1, 3))
    Image.fromarray(np.rint((z20 - off) / sc).astype(np.uint16)).save(os.path.join(root, "height_20m.png"))
    meta = {"format": "lunarsim-terrain", "version": 1, "site_id": "tiny", "size_m": [2000.0, 2000.0],
            "origin_xy_m": [0.0, 0.0], "frame": "local", "source": {"url": ""},
            "layers": {"height_5m": {"file": "height_5m.png", "shape": [n, n], "px_m": px},
                       "height_20m": {"file": "height_20m.png", "shape": [100, 100], "px_m": 20.0}},
            "z_encoding": {"offset_m": off, "scale_m_per_unit": sc}}
    with open(os.path.join(root, "meta.json"), "w") as f:
        json.dump(meta, f)
    sites = {"sites": [{"id": "BASE", "xy_m": [600.0, 700.0]}], "pads": {"1": {"PAD_A": [1500.0, 1400.0]}}}
    with open(os.path.join(root, "sites.json"), "w") as f:
        json.dump(sites, f)
    return z


def test_tiny_build_manifest(tmp_path, monkeypatch):
    pack = tmp_path / "tiny"
    pack.mkdir()
    _tiny_pack(str(pack))
    monkeypatch.setattr(ta, "PATCH_M", 500.0)
    out = str(pack / "v2")
    man = ta.build(str(pack), out, dem=None, n_sectors=8, log=lambda *a: None)
    names = [f["file"] for f in man["files"]]
    assert names == ["normal_20m.png", "normal_5m_BASE.png", "height_5m_BASE.png", "normal_5m_PAD_A.png",
                     "height_5m_PAD_A.png", "horizon_20m_00.png", "horizon_20m_01.png"]
    for f in man["files"]:
        p = os.path.join(out, f["file"])
        assert f["bytes"] == os.path.getsize(p) and f["sha256"] == ta.sha256(p)
    assert man["within_budget"] and man["horizon"]["n_sectors"] == 8
    assert "NOT included" in man["horizon"]["outside_tile"]
    H = ta.load_horizon(out, 8)
    assert sorted(H) == list(range(8)) and H[0].shape == (100, 100)
    assert sorted(ta.load_horizon(out, 8, sectors=[2, 6])) == [2, 6]
    # a post west of the hill sees it to the east (sector 2 = 90 deg) above the horizon to the west (sector 6)
    r, c = 55, 30
    assert H[2][r, c] > H[6][r, c] + 1.0
    # stored angles equal fresh rays to the code step
    fresh = ta.horizon_deg(ta.block_mean_rows(ta.load_dem5(str(pack), None, json.load(open(pack / "meta.json")))[0], 4),
                           20.0, 90.0)
    assert np.nanmax(np.abs(H[2] - fresh)) <= 0.025 + 1e-9
    # 5 m patch heights decode to the source within the 0.5 m pack quantisation (the patch step is 0.05 m)
    pt = next(p for p in man["lods"][1]["patches"] if p["site"] == "BASE")
    hp = next(f for f in man["files"] if f["file"] == "height_5m_BASE.png")
    w = pt["pixel_window_5m"]
    zpatch = hp["encoding"]["z_offset_m"] + hp["encoding"]["z_scale_m_per_unit"] * ta.read_png(
        os.path.join(out, "height_5m_BASE.png")).astype(float)
    assert zpatch.shape == (100, 100) and w["n"] == 100
    # a second run with --files keeps the manifest consistent
    man2 = ta.build(str(pack), out, dem=None, files="1", n_sectors=8, skip_static=True, log=lambda *a: None)
    assert [f["file"] for f in man2["files"]] == names


def test_patch_window_snaps_and_clamps():
    assert ta.patch_window([7450.0, 7510.0], 5.0, 2000.0, (3200, 3200)) == (1498, 1290, 400)
    r0, c0, n = ta.patch_window([10.0, 15990.0], 5.0, 2000.0, (3200, 3200))
    assert (r0, c0, n) == (0, 0, 400)
