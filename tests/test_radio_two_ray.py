"""B-89: opt-in flat-ground (two-ray) propagation in lunarsim/atc/radio.py and the E48 link revision.

Expected numbers are research note 03 (research_notes/Lunar Rover Interaction Protocol/03_comms_protocol_security.md),
section E1 (Table E1, worked examples A and B, "Check against E48") and section E3.
"""
import json
import math
import os

import numpy as np
import pytest

from lunarsim.atc import radio as RA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_note03_e1_losses_and_geometry():
    assert RA.free_space_loss_db(5000.0) == pytest.approx(114.0, abs=0.05)
    assert RA.flat_ground_loss_db(5000.0, 2.5, 2.5) == pytest.approx(132.0, abs=0.05)
    assert RA.flat_ground_loss_db(5000.0, 1.0, 1.0) == pytest.approx(148.0, abs=0.05)
    assert RA.breakpoint_m(2.5, 2.5) == pytest.approx(200.0, abs=0.5)
    for h, hor in ((0.5, 2640.0), (1.0, 3730.0), (1.5, 4570.0), (2.0, 5270.0)):     # Table E1, mutual horizon
        assert RA.mutual_horizon_m(h, h) == pytest.approx(hor, abs=10.0)
    for h, loss in ((0.5, 132.0), (1.0, 120.0), (1.5, 113.0), (2.0, 108.0)):     # Table E1, loss at 1 km
        assert RA.flat_ground_loss_db(1000.0, h, h) == pytest.approx(loss, abs=0.05)


def test_note03_e48_check_rates():
    """'LTV and cargo 6,977 -> 1,574 kbit/s; small robot 5,011 -> 18; hopper 5,989 -> 36' at 5 km."""
    for pw, h, fs, fg in ((1.0, 2.5, 6977, 1574), (0.25, 1.0, 5011, 18), (0.5, 1.0, 5989, 36)):
        b = {"tx_power_w": pw}
        assert RA.shannon_kbps(RA.free_space_loss_db(5000.0), b) == pytest.approx(fs, abs=1.0)
        assert RA.shannon_kbps(RA.flat_ground_loss_db(5000.0, h, h), b) == pytest.approx(fg, abs=0.6)


def test_note03_worked_examples_ranges():
    # example A: allowed loss 135 dB for 1 Mbit/s, 154.5 dB for 16 kbit/s
    assert RA.allowed_loss_db({"rate_bps": 1e6}) == pytest.approx(135.0, abs=1e-9)
    assert RA.allowed_loss_db() == pytest.approx(154.5, abs=0.05)
    for h, r1m in ((0.5, 1190.0), (1.0, 2370.0), (1.5, 3560.0), (2.0, 4740.0)):
        assert RA.budget_range_m(h, h, {"rate_bps": 1e6}) == pytest.approx(r1m, abs=10.0)
    assert RA.budget_range_m(2.0, 2.0) == pytest.approx(14600.0, abs=50.0)
    # example B: UHF 0.4 GHz, 0 dBi, 25 kHz, SNR 10 dB -> 2.37 km at 1 m, 4.75 km at 2 m
    ub = {"freq_hz": 4e8, "gain_dbi": 0.0, "bandwidth_hz": 25e3, "rate_bps": 25e3 * math.log2(11.0)}
    assert RA.budget_range_m(1.0, 1.0, ub) == pytest.approx(2370.0, abs=10.0)
    assert RA.budget_range_m(2.0, 2.0, ub) == pytest.approx(4750.0, abs=10.0)


def test_flat_ground_law_is_continuous_monotone_and_never_below_free_space():
    d = np.geomspace(1.0, 20000.0, 4000)
    for h1, h2, f in ((2.5, 2.5, 2.4e9), (1.0, 1.0, 2.4e9), (10.0, 1.0, 2.4e9), (2.0, 2.0, 4e8)):
        L = RA.flat_ground_loss_db(d, h1, h2, f)
        assert np.all(np.diff(L) > 0)
        assert np.all(L >= RA.free_space_loss_db(d, f) - 1e-9)
        assert np.max(np.abs(np.diff(L))) < 0.1                               # no jump at the breakpoint
        far = d > 4 * math.pi * h1 * h2 * f / RA.C_M_S
        assert np.allclose(L[far], RA.two_ray_loss_db(d[far], h1, h2))


def test_budget_range_inverts_the_loss():
    for h1, h2 in ((2.5, 2.5), (1.0, 1.0), (10.0, 1.0)):
        for b in ({}, {"rate_bps": 1e6}, {"tx_power_w": 0.25, "margin_db": 15.0}, {"rate_bps": 5e7}):
            r = float(RA.budget_range_m(h1, h2, b))
            assert RA.flat_ground_loss_db(r, h1, h2) == pytest.approx(RA.allowed_loss_db(b), abs=1e-6)


@pytest.fixture(scope="module")
def rm():
    return RA.RadioMesh()


def test_default_is_unchanged_and_two_ray_only_removes_links(rm):
    for h in (2.5, 1.0):
        base = rm.pair_links(h)
        assert np.array_equal(base, rm.pair_links(h, propagation=None))
        tr = rm.pair_links(h, propagation="two_ray")
        assert not np.any(tr & ~base)
        # a budget that closes at any range leaves exactly the horizon cut
        big = rm.pair_links(h, propagation="two_ray", budget={"tx_power_w": 1e9}, horizon=True)
        hor = base & (rm.d <= RA.mutual_horizon_m(h, h))
        hor[rm.I == rm.base] = base[rm.I == rm.base] & (rm.d[rm.I == rm.base] <= RA.mutual_horizon_m(rm.mast_h, h))
        assert np.array_equal(big, hor)
    # pairwise link() agrees with the vectorised pair_links on a sample of pairs
    tr = rm.pair_links(1.0, base_mast=False, propagation="two_ray")
    for k in np.linspace(0, len(rm.I) - 1, 400).astype(int):
        assert rm.link(int(rm.I[k]), int(rm.J[k]), 1.0, 1.0, propagation="two_ray") == bool(tr[k])
    with pytest.raises(ValueError):
        rm.link(1, 2, propagation="free_space")


def test_horizon_option_and_margin_sweep(rm):
    """LEAD's B-89 answer 1: on the DEM mesh the smooth horizon is off by default (the clearance carries the
    curvature); more link margin only ever removes links (3, 10, 15 dB)."""
    base = rm.pair_links(1.0)
    huge = {"tx_power_w": 1e9}
    assert np.array_equal(rm.pair_links(1.0, propagation="two_ray", budget=huge), base)          # horizon off
    on = rm.pair_links(1.0, propagation="two_ray", budget=huge, horizon=True)
    far = base & (rm.d > RA.mutual_horizon_m(1.0, 1.0)) & (rm.I != rm.base)
    assert far.any() and not np.any(on & far)       # DEM-visible pairs beyond the smooth horizon exist; horizon cuts them
    prev = None
    for m in (3.0, 10.0, 15.0):
        ok = rm.pair_links(1.0, propagation="two_ray", budget={"tx_power_w": 0.25, "margin_db": m})
        assert not np.any(ok & ~base)
        if prev is not None:
            assert not np.any(ok & ~prev)
        prev = ok
    assert prev.sum() < base.sum()                   # at 15 dB and 0.25 W some 1 m links no longer close 16 kbit/s


def test_e48_revision_block():
    path = os.path.join(ROOT, "results", "E48_sizing.json")
    doc = json.load(open(path))
    rv = doc["revision"]
    assert rv["task"] == "B-89"
    for cls, row in rv["old_new_per_class"].items():
        assert row["worst_hop_kbps"] == [doc["classes"][cls]["link_free_space_upper_bound"]["worst_hop_kbps"],
                                         doc["classes"][cls]["link"]["worst_hop_kbps"]]
    assert doc["classes"]["SMALL"]["link"]["beyond_horizon_at_worst_hop"] is True
    assert doc["classes"]["LTV1"]["link"]["worst_hop_kbps"] == pytest.approx(1574, abs=1)
    # note 03 E3: 49.1 B/s per robot -> 7.86 kbit/s (MAC 8 B), 9.39 kbit/s (MAC 16 B) for 20 robots, one hop
    assert doc["h10"]["link_kbps_needed_20_robots_secured_mac8"] == pytest.approx(7.86, abs=0.02)
    assert doc["h10"]["link_kbps_needed_20_robots_secured_mac16"] == pytest.approx(9.39, abs=0.02)
    assert doc["h10"]["link_kbps_needed_20_robots"] == 7.68                      # B-81 value kept


def test_spherical_ground_p526():
    """B-104: ITU-R P.526 sections 3.1.1 / 3.2 over the smooth Moon reproduce the referee's values (P3 M14), agree
    with the flat-ground law where the bulge is negligible, and equal free space below the breakpoint."""
    from lunarsim.atc import radio as RA
    assert abs(RA.spherical_loss_db(5000.0, 2.5, 2.5) - 137.0) < 0.05         # two rovers, 5 km
    assert abs(RA.spherical_loss_db(3728.6, 1.0, 1.0) - 146.6) < 0.05         # two 1 m antennas at their horizon
    assert abs(RA.spherical_loss_db(1000.0, 2.5, 2.5) - float(RA.flat_ground_loss_db(1000.0, 2.5, 2.5))) < 0.1
    assert abs(RA.spherical_loss_db(150.0, 2.5, 2.5) - float(RA.free_space_loss_db(150.0))) < 1e-9
    d = [2000.0, 4000.0, 6000.0, 8000.0]
    L = [RA.spherical_loss_db(x, 2.5, 2.5) for x in d]
    assert all(b > a for a, b in zip(L, L[1:]))                               # monotone in distance
