"""B-95: authentication, the LRIP integrity rule, W-MSR and robustness (lunarsim/atc/integrity.py), and E55 files."""
import json
import math
import os

import numpy as np
import pytest

from lunarsim.atc import integrity as I

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEY = bytes(range(16))


def test_forgery_rate_is_two_to_minus_t():
    acc = I.forgery_trial(8, 20000, np.random.default_rng(3))
    # Binomial(20000, 1/256): mean 78.1, sd 8.8
    assert 50 < acc < 110


def test_replay_and_freshness_rule():
    rx = I.Receiver(KEY, 64)
    body = b"\x01" * 13
    tag = lambda s, q: I.mac_bits(KEY, body + s.to_bytes(2, "big") + q.to_bytes(4, "big"), 64)
    assert rx.receive(5, 10, 100.0, 100.5, body, tag(5, 10))
    assert not rx.receive(5, 10, 100.0, 101.0, body, tag(5, 10)) and rx.rejected_replay == 1     # exact replay
    assert not rx.receive(5, 9, 99.0, 101.0, body, tag(5, 9))                                    # older sequence
    assert not rx.receive(5, 11, 100.0, 115.0, body, tag(5, 11)) and rx.rejected_stale == 1      # outside 10 s
    assert not rx.receive(5, 12, 100.0, 100.0, body, tag(5, 12) ^ 1) and rx.rejected_mac == 1    # bad MAC
    rx2 = I.Receiver(KEY, 64)                       # missed the original: a replay within 10 s is accepted (stale truth)
    assert rx2.receive(5, 10, 100.0, 108.0, body, tag(5, 10))


def test_k_of_n_and_detectable_error_note03_e5():
    assert I.k_of_n_false_alarm(1e-3) == pytest.approx(1.0e-8, rel=0.01)
    assert I.k_of_n_false_alarm(1e-2) == pytest.approx(9.9e-6, rel=0.01)
    chk = I.detectable_error_check(n=100000)
    assert chk["detect_prob"] == pytest.approx(0.90, abs=0.01) and chk["false_alarm"] == pytest.approx(1e-3, abs=4e-4)


def test_lrip_rule_score_counts_flags():
    from lunarsim.nn import faults as F
    X = np.zeros((1, 10, len(F.FEATURES)), np.float32)
    X[0, :, F.F_VALID] = 1
    X[0, [2, 3, 5, 6, 7], F.F_Z] = 4.0                # z^2 = 16 > 10.83
    s = I.lrip_rule_score(X, 10.83)
    assert list(s[0]) == [0, 0, 1, 2, 2, 3, 4, 4, 3, 3]          # flags among the last 5 steps
    X[0, 7, F.F_VALID] = 0                            # an invalid step never counts
    assert I.lrip_rule_score(X, 10.83)[0, 7] == 3


def test_wmsr_safety_and_robustness():
    n = 7
    full = ~np.eye(n, dtype=bool)
    rng = np.random.default_rng(0)
    x0 = rng.normal(0, 1, n)
    faulty = np.zeros(n, bool)
    faulty[0] = True
    hist, safe = I.wmsr(full, x0, faulty, F=1, steps=80)
    assert safe and hist[-1].max() - hist[-1].min() < 1e-3 * (hist[0].max() - hist[0].min())   # K7 is 3-robust
    faulty[1] = True                                   # two liars against F = 1 can drag the honest values out
    _, safe2 = I.wmsr(full, x0, faulty, F=1, steps=80)
    assert not safe2
    assert I.is_r_robust(full, 3) is True
    path = np.zeros((5, 5), bool)
    for i in range(4):
        path[i, i + 1] = path[i + 1, i] = True
    assert I.is_r_robust(path, 1) is True and I.is_r_robust(path, 2) is False
    assert I.is_r_robust(np.zeros((20, 20), bool), 1) is None          # too large to enumerate


def test_e55_outputs():
    p = os.path.join(ROOT, "results", "E55_integrity.json")
    if not os.path.isfile(p):
        pytest.skip("E55 not built")
    d = json.load(open(p))
    assert d["auth"]["forgery"]["8"]["accepted"] > 0 and d["auth"]["replay"]["0.25"]["replays_accepted"] == 0
    assert isinstance(d["h16"]["supported"], bool)
    t = d["integrity"]["sets"]["test"]["3of5@0.001"]
    assert t["fa_per_pair_day"] < d["integrity"]["sets"]["test"]["single@0.001"]["fa_per_pair_day"]


def test_replay_recent_trial_lets_through_only_missed_fresh_copies():
    """B-118 N9: replays of messages 0-60 s old; the counter and the 10 s window let through only a copy the receiver
    missed that is still inside the window, never anything else."""
    from lunarsim.atc import integrity as I
    r = I.replay_recent_trial(10, 5, 300, 0.5, 2.0, np.random.default_rng(3))
    assert r["replays"] > 400 and r["replays_with_age_le_10s"] > 0
    assert r["accepted_other"] == 0
    assert r["replays_accepted"] == r["accepted_missed_original_inside_window"] > 0
