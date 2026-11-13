"""Integrity, authentication and consensus (B-95, problem 7, experiment E55); research note 03 sections C6, C8, E4, E5,
E6. The position-report faults and streams are B-96's (lunarsim/nn/faults.py, imported, not copied), so E55 and E56
score the same events.

(1) Message authentication (note 03 E4): AES-CMAC truncated to t bits and an anti-replay rule per sender and key:
    accept iff the MAC verifies, the sequence number exceeds the highest accepted one, and |t_valid - now| <= 10 s.
(2) Position-report integrity, the LRIP rule of note 03 C8 as written: flag a neighbour's report when the normalised
    innovation d2 = z^2 exceeds gamma (10.83 for one range at alpha = 1e-3; E5), declare the neighbour suspect when
    3 of the last 5 tests are flagged. On B-96's streams the per-step z is lunarsim.nn.faults.pair_stream's.
(3) Consensus (note 03 E6): W-MSR with parameter F on the radio mesh; the robustness of the graph checked exactly by
    enumerating disjoint subset pairs (small fleets) and the necessary degree condition (any size).
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

FRESHNESS_S = 10.0                       # note 03 D "Anti-replay: freshness window" 10 s
GAMMA = {1: {1e-2: 6.63, 1e-3: 10.83, 1e-4: 15.14, 1e-5: 19.51},
         2: {1e-2: 9.21, 1e-3: 13.82, 1e-4: 18.42, 1e-5: 23.03}}   # note 03 E5 table (chi-square quantiles)
K_OF_N = (3, 5)                          # note 03 C8 persistence


# ------------------------------------------------------------------------------------------------ (1) authentication
def mac_bits(key: bytes, data: bytes, t_bits: int) -> int:
    from .lrip.codec import cmac
    full = int.from_bytes(cmac(key, data, 16), "big")
    return full >> (128 - t_bits)


@dataclass
class Receiver:
    key: bytes
    t_bits: int
    s_max: Dict[int, int] = field(default_factory=dict)
    accepted: int = 0
    rejected_mac: int = 0
    rejected_replay: int = 0
    rejected_stale: int = 0

    def receive(self, sender: int, seq: int, t_valid: float, now: float, body: bytes, tag: int) -> bool:
        if mac_bits(self.key, body + sender.to_bytes(2, "big") + seq.to_bytes(4, "big"), self.t_bits) != tag:
            self.rejected_mac += 1
            return False
        if seq <= self.s_max.get(sender, -1):
            self.rejected_replay += 1
            return False
        if abs(t_valid - now) > FRESHNESS_S:
            self.rejected_stale += 1
            return False
        self.s_max[sender] = seq
        self.accepted += 1
        return True


def forgery_trial(t_bits: int, attempts: int, rng: np.random.Generator, key: bytes = bytes(range(16))) -> int:
    """Accepted forgeries out of `attempts` random tags on fresh, never-seen sequence numbers (each forgery uses a new
    sequence number, so only the MAC can stop it)."""
    rx = Receiver(key, t_bits)
    ok = 0
    for a in range(attempts):
        body = bytes(rng.integers(0, 256, 13, dtype=np.uint8))
        tag = int(rng.integers(0, 1 << t_bits))
        ok += rx.receive(7, a, 0.0, 0.0, body, tag)
    return ok


def replay_trial(n_senders: int, n_receivers: int, seconds: int, loss: float, replay_rate_hz: float,
                 rng: np.random.Generator, t_bits: int = 64, key: bytes = bytes(range(16))) -> Dict[str, int]:
    """Senders broadcast at 1 Hz; each copy reaches each receiver with probability 1 - loss; an attacker records
    everything and, replay_rate_hz times a second, replays a random EARLIER message of the whole recorded log (so
    usually minutes old) to a random receiver, stamped as arriving 0-60 s after the replay event (the receiver's state
    is the one at the event). B-118 N9: because the message is drawn from the whole log, only about 1 % of replays
    fall inside the 10 s freshness window, so few acceptances are possible by design; replay_recent_trial is the
    harder test. Returns accepted replays, of which to a receiver that had missed the original."""
    rxs = [Receiver(key, t_bits) for _ in range(n_receivers)]
    log: List[Tuple[int, int, float, bytes, int]] = []
    heard: set = set()
    out = {"replays": 0, "replays_accepted": 0, "accepted_missed_original": 0}
    events = []
    for t in range(seconds):
        for s in range(n_senders):
            events.append((float(t) + rng.random() * 0.5, "send", s, t))
    for _ in range(int(rng.poisson(replay_rate_hz * seconds))):
        events.append((rng.uniform(0, seconds), "replay", 0, 0))
    events.sort()
    for now, kind, s, seq in events:
        if kind == "send":
            body = bytes(rng.integers(0, 256, 13, dtype=np.uint8))
            tag = mac_bits(key, body + s.to_bytes(2, "big") + seq.to_bytes(4, "big"), t_bits)
            log.append((s, seq, now, body, tag))
            for r, rx in enumerate(rxs):
                if rng.random() >= loss:
                    rx.receive(s, seq, now, now, body, tag)
                    heard.add((r, s, seq))
        elif log:
            s2, seq2, tv, body, tag = log[int(rng.integers(0, len(log)))]
            r = int(rng.integers(0, n_receivers))
            out["replays"] += 1
            if rxs[r].receive(s2, seq2, tv, now + rng.uniform(0, 60), body, tag):
                out["replays_accepted"] += 1
                out["accepted_missed_original"] += int((r, s2, seq2) not in heard)
    return out


def replay_recent_trial(n_senders: int, n_receivers: int, seconds: int, loss: float, replay_rate_hz: float,
                        rng: np.random.Generator, t_bits: int = 64, key: bytes = bytes(range(16)),
                        max_age_s: float = 60.0) -> Dict[str, int]:
    """B-118 N9 (added after the code review of 13 Nov 2026): as replay_trial, but each replay is a message sent in the
    last max_age_s (60 s) before the replay, delivered at the replay's time, so its age is 0 to 60 s. Accepted
    replays are split into those the rule is meant to let through (the receiver missed the original and the copy is
    inside the 10 s freshness window: a true but late state) and the rest (which would be a defect)."""
    rxs = [Receiver(key, t_bits) for _ in range(n_receivers)]
    log: List[Tuple[int, int, float, bytes, int]] = []
    heard: set = set()
    out = {"replays": 0, "replays_with_age_le_10s": 0, "replays_accepted": 0,
           "accepted_missed_original_inside_window": 0, "accepted_other": 0}
    events = []
    for t in range(seconds):
        for s in range(n_senders):
            events.append((float(t) + rng.random() * 0.5, "send", s, t))
    for _ in range(int(rng.poisson(replay_rate_hz * seconds))):
        events.append((rng.uniform(0, seconds), "replay", 0, 0))
    events.sort()
    lo = 0                                                    # first log entry sent within max_age_s of now
    for now, kind, s, seq in events:
        if kind == "send":
            body = bytes(rng.integers(0, 256, 13, dtype=np.uint8))
            tag = mac_bits(key, body + s.to_bytes(2, "big") + seq.to_bytes(4, "big"), t_bits)
            log.append((s, seq, now, body, tag))
            for r, rx in enumerate(rxs):
                if rng.random() >= loss:
                    rx.receive(s, seq, now, now, body, tag)
                    heard.add((r, s, seq))
            continue
        while lo < len(log) and log[lo][2] < now - max_age_s:
            lo += 1
        if lo >= len(log):
            continue
        s2, seq2, tv, body, tag = log[int(rng.integers(lo, len(log)))]
        r = int(rng.integers(0, n_receivers))
        out["replays"] += 1
        out["replays_with_age_le_10s"] += int(now - tv <= FRESHNESS_S)
        if rxs[r].receive(s2, seq2, tv, now, body, tag):
            out["replays_accepted"] += 1
            if (r, s2, seq2) not in heard and now - tv <= FRESHNESS_S:
                out["accepted_missed_original_inside_window"] += 1
            else:
                out["accepted_other"] += 1
    return out


# ------------------------------------------------------------------------------------------------ (2) the LRIP rule
def lrip_rule_score(X: np.ndarray, gamma: float, k: int = K_OF_N[0], n: int = K_OF_N[1]) -> np.ndarray:
    """Per step: the number of flagged tests among the last n (z^2 > gamma on valid steps). Suspect when >= k, so the
    alarm threshold on this score is k - 0.5 (B-96's detect / calibrate take scores and thresholds)."""
    from ..nn import faults as F
    flag = ((X[..., F.F_Z] ** 2 > gamma) & (X[..., F.F_VALID] > 0)).astype(np.float32)
    c = np.cumsum(flag, axis=1)
    out = c.copy()
    out[:, n:] -= c[:, :-n]
    return out


def detectable_error_check(m: int = 1, alpha: float = 1e-3, p_detect: float = 0.9, n: int = 200000,
                           seed: int = 0) -> Dict[str, float]:
    """Monte Carlo of note 03 E5: for one Gaussian test with m = 1 the bias that is caught with probability p_detect
    is (z_{1-alpha/2} + z_{p_detect}) sigma = (3.29 + 1.28) sigma = 4.57 sigma (two-sided, since d2 = v^2)."""
    # B-119 C12: the bias follows alpha and p_detect (before: a literal 4.57). Exact for any m: the bias (in sigmas,
    # along one axis) whose noncentral chi-square exceeds gamma with probability p_detect; for m = 1 this is close to
    # z_{1-alpha/2} + z_{p_detect} (4.57 at alpha 1e-3, p 0.9; the two-sided form adds the far tail).
    from scipy import optimize, stats
    rng = np.random.default_rng(seed)
    g = GAMMA[m][alpha] if alpha in GAMMA.get(m, {}) else float(stats.chi2.ppf(1 - alpha, m))
    b = float(optimize.brentq(lambda x: stats.ncx2.sf(g, m, x * x) - p_detect, 1e-6, 50.0))
    v = rng.normal(0.0, 1.0, (n, m))
    v[:, 0] += b
    d2 = (v * v).sum(axis=1)
    return {"bias_sigma": b, "bias_sigma_first_order": float(stats.norm.ppf(1 - alpha / 2) + stats.norm.ppf(p_detect)),
            "detect_prob": float((d2 > g).mean()),
            "false_alarm": float((rng.normal(0, 1, (n, m)) ** 2).sum(axis=1).__gt__(g).mean())}


def k_of_n_false_alarm(alpha: float, k: int = 3, n: int = 5) -> float:
    """Note 03 E5: sum over i >= k of C(n, i) alpha^i (1 - alpha)^(n - i)."""
    return float(sum(math.comb(n, i) * alpha ** i * (1 - alpha) ** (n - i) for i in range(k, n + 1)))


# ------------------------------------------------------------------------------------------------ (3) consensus
def wmsr(adj: np.ndarray, x0: np.ndarray, faulty: np.ndarray, F: int, steps: int = 100, attack: str = "polarise",
         L: float = 50.0) -> Tuple[np.ndarray, bool]:
    """W-MSR (note 03 E6): every normal node removes the F largest neighbour values above its own and the F smallest
    below (fewer if fewer), then averages the rest with its own (equal weights). Faulty nodes send attack values:
    "polarise" sends +L to neighbours above the honest median and -L to those below; "constant" sends +L to all.
    Returns (history of normal values [steps + 1, n_normal], whether every normal value stayed inside the initial range
    of the normal values at every step)."""
    n = len(x0)
    x = x0.astype(float).copy()
    normal = ~faulty
    lo, hi = x[normal].min(), x[normal].max()
    hist = [x[normal].copy()]
    safe = True
    for _ in range(steps):
        med = np.median(x[normal])
        new = x.copy()
        for i in np.nonzero(normal)[0]:
            nb = np.nonzero(adj[i])[0]
            vals = []
            for j in nb:
                if faulty[j]:
                    vals.append(L if (attack == "constant" or x[i] >= med) else -L)
                else:
                    vals.append(x[j])
            vals = np.array(vals, float)
            above = np.sort(vals[vals > x[i]])
            below = np.sort(vals[vals < x[i]])
            same = vals[vals == x[i]]
            keep = np.concatenate([above[:max(0, len(above) - F)], below[min(F, len(below)):], same])
            new[i] = (x[i] + keep.sum()) / (1 + len(keep))
        x = new
        if (x[normal] < lo - 1e-9).any() or (x[normal] > hi + 1e-9).any():
            safe = False
        hist.append(x[normal].copy())
    return np.array(hist), safe


def r_reachable(adj: np.ndarray, S: Sequence[int], r: int) -> bool:
    Sset = set(S)
    out = np.ones(adj.shape[0], bool)
    out[list(Sset)] = False
    return any(int(adj[i][out].sum()) >= r for i in Sset)


def is_r_robust(adj: np.ndarray, r: int, max_n: int = 12) -> Optional[bool]:
    """Exact: for every pair of nonempty disjoint subsets S1, S2, at least one is r-reachable (LeBlanc et al. 2012,
    Definition 7). None when the graph has more than max_n nodes (3^n pairs)."""
    n = adj.shape[0]
    if n > max_n:
        return None
    for lab in itertools.product((0, 1, 2), repeat=n):          # 0: neither, 1: S1, 2: S2
        if 1 not in lab or 2 not in lab:
            continue
        if lab.index(1) > lab.index(2):                          # (S1, S2) and (S2, S1) are the same pair
            continue
        S1 = [i for i, v in enumerate(lab) if v == 1]
        S2 = [i for i, v in enumerate(lab) if v == 2]
        if not (r_reachable(adj, S1, r) or r_reachable(adj, S2, r)):
            return False
    return True
