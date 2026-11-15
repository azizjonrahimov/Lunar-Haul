"""E52 (B-92) route geometry. B-118 N1: each tile entry carries its own distance along the tour."""
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "atc"))
import run_e52 as E52  # noqa: E402


def test_route_tile_offsets_are_per_sample():
    """Before the fix every tile of a leg carried the leg's end distance (35 distinct offsets for 328 entries)."""
    tour, length = E52.route_tiles()
    offs = np.array([s for _, s in tour])
    assert len(np.unique(offs)) >= 0.95 * len(tour)
    assert np.all(np.diff(offs) >= 0.0)          # non-decreasing along the tour
    assert offs[0] < 1000.0                        # the first entry is near the start, not at the first leg's end
    assert offs[-1] <= length + 1e-6


def test_tour_length_unchanged_by_the_fix():
    """The tour length is the sum of the legs' sample-to-sample distances, as before the fix (16 km pack); B-120 F:
    it equals the published tour_km (results/E52_map.json), not only a plausible range."""
    import json
    _, length = E52.route_tiles()
    assert 1_000.0 < length < 200_000.0
    with open(os.path.join(ROOT, "results", "E52_map.json"), encoding="utf-8") as f:
        assert round(length / 1000.0, 2) == json.load(f)["tour_km"]
