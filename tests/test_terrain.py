"""Terrain packs (lunarsim-terrain v1): build from a synthetic GeoTIFF, read back, query, place pads."""
import json, math, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("PIL")
from rasterio.transform import from_origin

from lunarsim import terrain as T

PROJ = "+proj=stere +lat_0=-90 +lat_ts=-90 +lon_0=0 +x_0=0 +y_0=0 +R=1737400 +units=m +no_defs"
X_LEFT, Y_TOP, PX, N = -19000.0, -4000.0, 5.0, 200          # same corner convention as the real Site01 tile


def write_tif(path, fn, n=N, nodata_mask=None):
    """GeoTIFF whose pixel centres carry z = fn(X, Y) in map metres (row 0 = north)."""
    cols = np.arange(n)
    X = X_LEFT + (cols + 0.5) * PX
    Y = Y_TOP - (np.arange(n) + 0.5) * PX
    XX, YY = np.meshgrid(X, Y)
    z = fn(XX, YY).astype(np.float32)
    if nodata_mask is not None:
        z[nodata_mask] = np.nan
    with rasterio.open(path, "w", driver="GTiff", width=n, height=n, count=1, dtype="float32", crs=PROJ,
                       transform=from_origin(X_LEFT, Y_TOP, PX, PX), nodata=np.nan) as ds:
        ds.write(z, 1)
    return path


def pack(tmp_path, name, fn, **kw):
    src = write_tif(str(tmp_path / f"{name}.tif"), fn, nodata_mask=kw.pop("nodata_mask", None))
    out = str(tmp_path / name)
    meta = T.build_pack(src, out, "SiteTest", **kw)
    return T.Terrain(out), meta


A, B, C = 0.10, 0.05, 1500.0                                   # plane z = A X + B Y + C


@pytest.fixture(scope="module")
def plane(tmp_path_factory):
    return pack(tmp_path_factory.mktemp("t"), "plane", lambda X, Y: A * X + B * Y + C, z_scale=0.01)


def test_round_trip_meta(plane):
    t, meta = plane
    assert (meta["format"], meta["version"]) == ("lunarsim-terrain", 1)
    assert meta["origin_xy_m"] == [X_LEFT, Y_TOP - N * PX]
    assert meta["size_m"] == [N * PX, N * PX]
    assert meta["layers"]["height_5m"]["shape"] == [N, N] and meta["layers"]["height_20m"]["shape"] == [N // 4, N // 4]
    assert meta["z_encoding"]["offset_m"] == math.floor(meta["stats"]["z_min"])
    assert meta["source"]["credit"] == "NASA/GSFC" and "products/78" in meta["source"]["citation"]
    for L in meta["layers"].values():
        assert os.path.exists(os.path.join(t.path, L["file"]))
    with open(os.path.join(t.path, "meta.json"), encoding="utf-8") as f:
        assert json.load(f) == meta
    assert t.slope20.shape == (N // 4, N // 4)


def test_bilinear_height_on_a_plane(plane):
    t, _ = plane
    x0, y0 = t.meta["origin_xy_m"]
    rng = np.random.default_rng(0)
    xs, ys = rng.uniform(2.5, N * PX - 2.5, 500), rng.uniform(2.5, N * PX - 2.5, 500)
    exact = A * (xs + x0) + B * (ys + y0) + C
    assert np.max(np.abs(t.height(xs, ys) - exact)) <= 0.006     # bilinear is exact on a plane; 0.01 m quantisation
    # pixel centres and the north/south orientation
    assert abs(t.height(2.5, N * PX - 2.5) - (A * (X_LEFT + 2.5) + B * (Y_TOP - 2.5) + C)) <= 0.006


def test_slope_of_a_plane(plane):
    t, meta = plane
    expect = math.degrees(math.atan(math.hypot(A, B)))          # 6.38 deg
    xs = np.linspace(100, 900, 9)
    assert np.all(np.abs(t.slope(xs, xs) - expect) <= 0.51)     # uint8 degrees
    assert abs(meta["stats"]["slope_p50"] - expect) < 1e-3


def test_leg_stats_on_a_ramp(tmp_path):
    t, _ = pack(tmp_path, "ramp", lambda X, Y: 0.2 * (X - X_LEFT), z_scale=0.01)   # rises 0.2 m/m towards +x
    s = t.leg_stats((100, 500), (900, 500))
    assert s["length_m"] == pytest.approx(800)
    assert s["climb_m"] == pytest.approx(160, abs=0.05) and s["descent_m"] == pytest.approx(0, abs=0.05)
    assert s["length_3d_m"] == pytest.approx(800 * math.hypot(1, 0.2), rel=1e-4)
    assert s["max_grade_deg"] == pytest.approx(math.degrees(math.atan(0.2)), abs=0.05)
    assert s["slope_hist"][2] == pytest.approx(1.0)               # 11.3 deg: all in 10-15
    assert sum(s["slope_hist"]) == pytest.approx(1.0)
    back = t.leg_stats((900, 500), (100, 500))
    assert back["descent_m"] == pytest.approx(160, abs=0.05) and back["climb_m"] == pytest.approx(0, abs=0.05)
    p = t.profile((0, 0), (300, 400), step_m=5)
    assert p["s"][-1] == pytest.approx(500) and len(p["s"]) == 101


def wall(X, Y):
    """Flat at 0 m except a 300 m high east-west wall 100 m wide across y_local 600..700."""
    y = Y - (Y_TOP - N * PX)
    return np.where((y > 600) & (y < 700), 300.0, 0.0)


def test_shadow_and_line_of_sight(tmp_path):
    t, _ = pack(tmp_path, "wall", wall, z_scale=0.1)
    south, north = (500, 300), (500, 900)
    assert bool(t.shadowed(*south, sun_az_deg=0.0)[0])          # sun beyond the wall to +y: in shadow
    assert not bool(t.shadowed(*south, sun_az_deg=180.0)[0])    # sun behind the point: lit
    assert not bool(t.shadowed(*north, sun_az_deg=0.0)[0])
    assert t.shadow_fraction((100, 300), (900, 300), 0.0) == pytest.approx(1.0)
    assert t.shadow_fraction((100, 300), (900, 300), 180.0) == pytest.approx(0.0)
    assert not t.line_of_sight(south, north)
    assert t.line_of_sight((100, 300), (900, 300))
    assert t.los_clearance_m(south, north) < -200


def test_place_respects_slope_limit(tmp_path):
    def half(X, Y):                                              # flat for x_local < 500, 20 deg slope beyond
        x = X - X_LEFT
        return np.where(x < 500, 0.0, (x - 500) * math.tan(math.radians(20)))
    t, _ = pack(tmp_path, "half", half, z_scale=0.1)
    for stat in ("plane", "max"):
        c = T.place_pads(t, (300, 500), 0.35, max_slope_deg=5.0, radius_m=100, n=20, min_sep_m=60, slope_stat=stat)
        assert c, stat
        for p in c:
            assert p["xy_m"][0] < 500
            assert (p["slope_plane_deg"] if stat == "plane" else p["slope_max_deg"]) <= 5.0
            assert abs(p["dist_km"] - 0.35) <= 0.35 * 0.05 + 0.02
            assert p["los_to_base"] in ("clear", "blocked")
        assert all(math.hypot(a["xy_m"][0] - b["xy_m"][0], a["xy_m"][1] - b["xy_m"][1]) >= 60
                   for i, a in enumerate(c) for b in c[i + 1:])
    with pytest.raises(ValueError):
        T.place_pads(t, (300, 500), 0.35, slope_stat="mean")


def test_nodata_is_filled(tmp_path):
    mask = np.zeros((N, N), bool)
    mask[50:60, 70:90] = True
    t, meta = pack(tmp_path, "holes", lambda X, Y: A * X + B * Y + C, z_scale=0.01, nodata_mask=mask)
    assert meta["stats"]["nodata_filled"] == 200
    x0, y0 = t.meta["origin_xy_m"]
    x, y = 80 * PX, (N - 55) * PX                                # inside the former hole
    assert abs(t.height(x, y) - (A * (x + x0) + B * (y + y0) + C)) < 0.5


def test_uint16_overflow_is_reported(tmp_path):
    src = write_tif(str(tmp_path / "tall.tif"), lambda X, Y: (X - X_LEFT) * 100.0)   # ~100 km relief
    with pytest.raises(ValueError, match="does not fit uint16"):
        T.build_pack(src, str(tmp_path / "tall"), "SiteTest")


def test_cli_build_info_place(tmp_path, capsys):
    from lunarsim.cli import main
    src = write_tif(str(tmp_path / "p.tif"), lambda X, Y: A * 0.2 * X + C)          # 1.1 deg: everywhere a pad
    out = tmp_path / "packs" / "tiny"
    main(["terrain", "build", "--site", "SiteTest", "--src", src, "--out", str(out)])
    assert "height_5m.png" in capsys.readouterr().out
    main(["terrain", "info", "--site", str(out)])
    assert "tiny: SiteTest" in capsys.readouterr().out
    main(["terrain", "place", "--site", "tiny", "--root", str(tmp_path / "packs"), "--standoff", "0.3",
          "--base", "500,500", "--n", "3", "--json"])
    d = json.loads(capsys.readouterr().out)
    assert len(d["candidates"]) == 3 and d["criteria"]["slope_stat"] == "plane"
    with pytest.raises(SystemExit, match="outside the tile"):
        main(["terrain", "place", "--site", str(out), "--base", "5000,5000"])


def test_missing_pack():
    with pytest.raises(FileNotFoundError):
        T.Terrain("no_such_pack", root=ROOT)
