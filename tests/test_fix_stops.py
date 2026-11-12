"""B-90b: the opt-in terrain-fix stops of the road layer (lunarsim/atc/roads.py fix_stops)."""
import numpy as np

from lunarsim.atc.roads import RoadLayer


def _layer(per_traversal, fractions, segs, t_from=10.0):
    rl = RoadLayer.__new__(RoadLayer)                    # no engine needed for the placement rule
    rl.legs = {"A->B": segs}
    rl._fs = {"stop_h": 120.0 / 3600.0, "t_from": t_from, "defer": True,
              "legs": {"A->B": (per_traversal, np.sort(np.asarray(fractions, float)))}}
    rl._fs_acc = {}
    return rl


def test_running_count_and_window():
    rl = _layer(1.5, [0.2, 0.6], [])
    assert rl._fix_stops("A->B", 5.0) == []              # before t_from: no stops, count not advanced
    n = [len(rl._fix_stops("A->B", 11.0)) for _ in range(4)]
    assert n == [1, 2, 1, 2] and sum(n) == 6             # 4 traversals x 1.5 = 6 stops, deterministic
    assert rl._fix_stops("C->D", 11.0) == []             # a leg without fixes


def test_stop_inside_single_lane_moves_to_exit():
    rl = _layer(1.0, [0.5], [(0, 0.4, 0.7, 1), (1, 0.7, 0.8, 0)])   # two adjacent single-lane segments
    (g,) = rl._fix_stops("A->B", 11.0)
    assert 0.8 < g < 0.8 + 1e-6                          # past both exits, not inside either
