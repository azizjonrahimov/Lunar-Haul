"""B-97: the limb fit on a synthetic partly lit disc, the alarm-run counting, and the downloads manifest."""
import json
import math
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools", "atc"))
import run_b97 as B97  # noqa: E402


def test_limb_fit_ignores_the_terminator():
    """A disc of radius 80 px lit on one side (the terminator an ellipse of half-width 30 px): the RANSAC fit must
    return the limb circle, not the terminator."""
    H, W = 400, 500
    yy, xx = np.mgrid[0:H, 0:W]
    cx, cy, r = 260.3, 190.7, 80.0
    inside = (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r
    lit = inside & (((xx - cx) / 30.0) ** 2 + ((yy - cy) / r) ** 2 >= 1.0) & (xx > cx - 1)   # gibbous on the right
    img = np.where(lit, 200, 3).astype(np.uint8)
    fx, fy, fr, share, nb, thr = B97.fit_limb(img, np.random.default_rng(0))
    assert abs(fr - r) < 1.0 and math.hypot(fx - cx, fy - cy) < 1.0
    assert 0.2 < share < 0.95


def test_alarm_runs():
    a = np.array([0, 1, 1, 0, 0, 1, 0, 1, 1, 1], bool)
    assert B97._events(a) == [(1, 3), (5, 6), (7, 10)]


def test_manifest():
    p = os.path.join(ROOT, "results", "B97_downloads.json")
    if not os.path.isfile(p):
        pytest.skip("B-97 manifest not written")
    d = json.load(open(p))
    assert d["total_bytes"] < d["limit_bytes"] == 200_000_000
    assert all(f["url"] and len(f["sha256"]) == 64 for f in d["files"])
    assert d["sources"]["telemanom (SMAP / MSL)"]["is_mirror"] is True
    mirrored = [f for f in d["files"] if "telemanom/train" in f["file"] or "telemanom/test" in f["file"]]
    assert mirrored and all(f["mirror"] for f in mirrored)
