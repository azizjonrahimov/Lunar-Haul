"""B-91: vehicle clocks and time transfer (lunarsim/atc/clocks.py) and the E51 files."""
import json
import math
import os

import numpy as np
import pytest

from lunarsim.atc import clocks as CK

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_relativistic_rate_and_light_time():
    """Note 01 E4: +56.02 us/day (6.4844e-10), i.e. 16.8 km of light-time a day; E5: 1 ns = 0.2998 m."""
    assert CK.RATE_MOON_MINUS_EARTH * 86400 * 1e6 == pytest.approx(56.02, abs=0.01)
    assert CK.RATE_MOON_MINUS_EARTH * 86400 * CK.C_M_S == pytest.approx(16.8e3, rel=0.01)
    assert CK.C_M_S * 1e-9 == pytest.approx(0.2998, abs=1e-4)


def test_holdover_matches_note01_e6_table():
    """Note 01 E6 'Holdover' table (y0 alone): crystal 1e-6 -> 1 us in 1 s, 0.1 s in 27.8 h; 2e-7 -> 10 ms in 13.9 h;
    CSAC 3e-10 -> 1 us in 56 min; rubidium 1e-12 -> 10 ns in 2.8 h."""
    assert CK.holdover_s(1e-6, 1e-6) == pytest.approx(1.0)
    assert CK.holdover_s(0.1, 1e-6) / 3600 == pytest.approx(27.8, abs=0.1)
    assert CK.holdover_s(10e-3, 2e-7) / 3600 == pytest.approx(13.9, abs=0.1)
    assert CK.holdover_s(1e-6, 3e-10) / 60 == pytest.approx(55.6, abs=0.5)
    assert CK.holdover_s(10e-9, 1e-12) / 3600 == pytest.approx(2.8, abs=0.05)
    # ageing shortens the time; a perfect clock never runs out
    assert CK.holdover_s(10e-3, 3e-10, CK.ageing_rate("csac")) < CK.holdover_s(10e-3, 3e-10)
    assert math.isinf(CK.holdover_s(1e-3, 0.0))


def test_clock_model_resync_and_free_run():
    y, A = np.array([5e-7, 5e-7]), np.zeros(2)
    att = np.array([True] * 10)
    clk = CK.Clocks(y, A, 0.0, 600.0, lambda i: att if i == 0 else np.zeros(10, bool), 10,
                    np.random.default_rng(0), tt_sigma_s=0.0)
    assert clk.x(0, 3000.0)[0] == pytest.approx(0.0)                       # just resynced at 3000 s
    assert clk.x(0, 3300.0)[0] == pytest.approx(5e-7 * 300.0)
    assert clk.x(1, 3300.0)[0] == pytest.approx(5e-7 * 3300.0)             # never in contact: free-running
    ys, As = CK.draw(1000, "crystal", np.random.default_rng(1))
    assert ys.min() >= 0 and ys.max() <= 8e-7 and not As.any()
    ye, _ = CK.draw(1000, "crystal", np.random.default_rng(1), earth_scale=True)
    assert np.allclose(ye - ys, CK.RATE_MOON_MINUS_EARTH)


def test_e51_outputs():
    path = os.path.join(ROOT, "results", "E51_clocks.json")
    if not os.path.isfile(path):
        pytest.skip("E51 not built")
    d = json.load(open(path))
    assert len(d["seeds"]) == 30
    perfect = d["rows"][0]
    assert perfect["class"] == "perfect" and perfect["one_way_m_p95"] == 0 and perfect["conflicts_guard_0.1"] == 0
    cr = {r["interval_s"]: r for r in d["rows"] if r["class"] == "crystal" and r["scale"] == "lunar"}
    assert cr[10]["max_abs_clock_s"] <= cr["never"]["max_abs_clock_s"]
    assert isinstance(d["h11"]["supported"], bool)
