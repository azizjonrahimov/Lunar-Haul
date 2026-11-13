"""The classical detectors the network is compared with, and the false-alarm calibration every detector shares.

Detectors (each returns a score per step, higher = more suspicious; input X [N, T, 10] in the order faults.FEATURES):
  chi2_step     z^2 of the normalised range innovation, one step at a time;
  chi2_window   the mean of z^2 over the last W steps;
  cusum         two-sided CUSUM on z with reference value k: g+ = max(0, g+ + z - k), g- = max(0, g- - z - k),
                score max(g+, g-); it starts at zero with the stream (the warm-up is not scored) and is never reset,
                so its false alarms can be counted for any threshold from one pass. Variant ref > 0: z is first
                centred on its own mean over the steps t - 2 ref .. t - ref;
  LogReg        logistic regression on hand-made statistics of the last 16 and 128 steps (hand_features()): of
                z (|mean|, rms, spread, peak, slope, largest step), of the reported speed (mean, peak, spread), the
                shares of valid and of degraded-link steps, the claimed uncertainties and their change, A's fix
                age, the ranging class and the range.
W, k and the CUSUM variant are chosen on validation data; the logistic regression is fitted on training data.

Alarms and false alarms (one definition for every detector, the network included):
  an alarm is a step with score > threshold; a FALSE ALARM is a 60 s bin of fault-free stream with at least one alarm
  (so one disturbance that keeps a detector above threshold for 3 minutes costs 3 false alarms). The count is
  monotone in the threshold, so calibrate() finds the threshold for a target rate exactly, on fault-free VALIDATION
  blocks, with the stratum weights of dataset.finish() (natural mix of blocks with and without driving).
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

from . import faults as F
from .dataset import PRE

BIN_S = 60
RATES = {"day": 1.0, "hour": 24.0}          # target false alarms per pair-day: 1 per pair-day, 1 per pair-hour
LR_WINDOWS = (16, 128)


# ------------------------------------------------------------------------------------------------ calibration
def bin_max(score: np.ndarray, pre: int = PRE) -> np.ndarray:
    """Maximum score in each 60 s bin of the scored part: [N, T] -> [N, (T - pre) / 60]."""
    s = score[:, pre:]
    n, t = s.shape
    return s[:, :t - t % BIN_S].reshape(n, -1, BIN_S).max(axis=2)


def pair_days(bmax: np.ndarray, weight: np.ndarray) -> float:
    return float((weight * bmax.shape[1] * BIN_S).sum() / 86400.0)


def fa_per_day(bmax: np.ndarray, weight: np.ndarray, thr: float) -> float:
    """Weighted false alarms per pair-day at a threshold."""
    return float(((bmax > thr).sum(axis=1) * weight).sum() / pair_days(bmax, weight))


def calibrate(bmax: np.ndarray, weight: np.ndarray, rate_per_day: float) -> float:
    """The lowest threshold whose weighted false-alarm rate on these fault-free blocks is <= rate_per_day."""
    v = bmax.ravel().astype(np.float64)
    w = np.repeat(weight, bmax.shape[1])
    order = np.argsort(-v, kind="stable")
    v, w = v[order], w[order]
    allowed = rate_per_day * pair_days(bmax, weight)
    cw = np.cumsum(w)
    k = int(np.searchsorted(cw, allowed * (1 + 1e-12), side="right"))      # the k highest bins may alarm
    while k < len(v) and k > 0 and v[k] == v[k - 1]:                       # ties cannot be split: alarm fewer
        k -= 1
    return float(v[k]) if k < len(v) else float(v[-1] - 1.0)


# ------------------------------------------------------------------------------------------------ rolling helpers
def _roll_sum(x: np.ndarray, w: int) -> np.ndarray:
    """Sum over the last w steps (causal, zero before the start), along axis 1."""
    c = np.cumsum(x, axis=1, dtype=np.float64)
    out = c.copy()
    out[:, w:] -= c[:, :-w]
    return out


def _roll_max(x: np.ndarray, w: int) -> np.ndarray:
    """Causal rolling maximum by doubling (exact; O(log w) passes)."""
    out = x.copy()
    span = 1
    while span < w:
        step = min(span, w - span)
        shifted = np.full_like(out, -np.inf)
        shifted[:, step:] = out[:, :-step]
        out = np.maximum(out, shifted)
        span += step
    return out


# ------------------------------------------------------------------------------------------------ detectors
def chi2_step(X: np.ndarray) -> np.ndarray:
    return (X[..., F.F_Z] ** 2 * X[..., F.F_VALID]).astype(np.float32)


def chi2_window(X: np.ndarray, w: int) -> np.ndarray:
    return (_roll_sum(X[..., F.F_Z] ** 2 * X[..., F.F_VALID], w) / w).astype(np.float32)


def cusum(X: np.ndarray, k: float, ref: int = 0) -> np.ndarray:
    """Two-sided CUSUM on z. ref = 0: on z itself. ref > 0: on z minus its mean over the steps t - 2 ref .. t - ref
    (a lagged reference level, because the honest innovation is not zero-mean: navigation errors bias it)."""
    z = (X[..., F.F_Z] * X[..., F.F_VALID]).astype(np.float64)
    v = X[..., F.F_VALID] > 0
    if ref > 0:
        s, c = _roll_sum(z, ref), _roll_sum(v.astype(np.float64), ref)
        level = np.zeros_like(z)
        level[:, ref:] = (s / np.maximum(c, 1.0))[:, :-ref]
        z = (z - level) * v
    n, t = z.shape
    gp = np.zeros(n)
    gm = np.zeros(n)
    out = np.zeros((n, t), np.float32)
    for i in range(t):
        vi = v[:, i]
        gp = np.where(vi, np.maximum(0.0, gp + z[:, i] - k), gp)
        gm = np.where(vi, np.maximum(0.0, gm - z[:, i] - k), gm)
        out[:, i] = np.maximum(gp, gm)
    return out


def hand_features(X: np.ndarray) -> np.ndarray:
    """Hand-made window statistics for the logistic regression: [N, T, 10] -> [N, T, n_features]."""
    v = X[..., F.F_VALID].astype(np.float64)
    z = X[..., F.F_Z].astype(np.float64) * v
    sp = X[..., F.F_SPEED].astype(np.float64)
    lq = X[..., F.F_LQ].astype(np.float64)
    dz = np.abs(np.diff(z, axis=1, prepend=z[:, :1]))
    lsb = np.log(np.maximum(X[..., F.F_SIGB].astype(np.float64), 0.1))
    cols = []
    t = np.arange(z.shape[1], dtype=np.float64)[None, :]
    for w in LR_WINDOWS:
        m1 = _roll_sum(z, w) / w
        m2 = _roll_sum(z * z, w) / w
        # least-squares slope of z over the window, times the window length (the change across it)
        st = _roll_sum(z * t, w) / w
        tm = t - (w - 1) / 2.0
        slope = (st - m1 * tm) / ((w * w - 1) / 12.0) * w
        ms = _roll_sum(sp, w) / w
        ms2 = _roll_sum(sp * sp, w) / w
        cols += [np.abs(m1), np.log1p(np.sqrt(m2)), np.sqrt(np.maximum(m2 - m1 * m1, 0.0)),
                 np.log1p(np.sqrt(_roll_max(z * z, w))), np.log1p(np.abs(slope)),
                 np.log1p(_roll_max(dz, w)), ms, np.log1p(_roll_max(sp, w)),
                 np.sqrt(np.maximum(ms2 - ms * ms, 0.0)), _roll_sum(v, w) / w, _roll_sum(lq, w) / w]
    d16 = np.zeros_like(lsb)
    d16[:, 16:] = lsb[:, 16:] - lsb[:, :-16]
    cols += [lsb * v, np.log(np.maximum(X[..., F.F_SIGA].astype(np.float64), 0.1)),
             np.log1p(X[..., F.F_FIXAGE].astype(np.float64) / 60.0), np.abs(d16) * v,
             X[..., F.F_CLASS].astype(np.float64), np.log1p(X[..., F.F_RANGE].astype(np.float64) / 100.0)]
    return np.stack(cols, axis=2).astype(np.float32)


class LogReg:
    """Class-balanced logistic regression on hand_features (fitted with L-BFGS in torch; plain numpy to score)."""

    def __init__(self, mean=None, std=None, w=None, b=0.0):
        self.mean, self.std, self.w, self.b = mean, std, w, b

    def fit(self, X: np.ndarray, y: np.ndarray, mask: np.ndarray, stride: int = 8, l2: float = 1e-4,
            seed: int = 0) -> "LogReg":
        import torch
        torch.manual_seed(seed)
        feats, labs = [], []
        for i in range(0, len(X), 256):
            f = hand_features(X[i:i + 256])
            m = mask[i:i + 256].copy()
            m[:, np.arange(m.shape[1]) % stride != 0] = False
            feats.append(f[m])
            labs.append(y[i:i + 256][m])
        f = np.concatenate(feats).astype(np.float64)
        t = np.concatenate(labs).astype(np.float64)
        self.mean, self.std = f.mean(axis=0), f.std(axis=0) + 1e-6
        A = torch.tensor((f - self.mean) / self.std)
        tt = torch.tensor(t)
        pos = float(t.mean())
        wt = torch.where(tt > 0.5, 0.5 / pos, 0.5 / (1.0 - pos))
        w = torch.zeros(A.shape[1], dtype=torch.float64, requires_grad=True)
        b = torch.zeros(1, dtype=torch.float64, requires_grad=True)
        opt = torch.optim.LBFGS([w, b], max_iter=200, tolerance_grad=1e-9, line_search_fn="strong_wolfe")

        def closure():
            opt.zero_grad()
            loss = (torch.nn.functional.binary_cross_entropy_with_logits(A @ w + b, tt, reduction="none") * wt).mean()
            loss = loss + l2 * (w * w).sum()
            loss.backward()
            return loss

        opt.step(closure)
        self.w, self.b = w.detach().numpy().copy(), float(b.detach())
        self.n_rows, self.pos_share = len(t), pos
        return self

    def score(self, X: np.ndarray) -> np.ndarray:
        out = np.zeros(X.shape[:2], np.float32)
        for i in range(0, len(X), 128):
            f = hand_features(X[i:i + 128]).astype(np.float64)
            out[i:i + 128] = ((f - self.mean) / self.std) @ self.w + self.b
        return out

    def to_doc(self) -> Dict[str, Any]:
        return {"windows": list(LR_WINDOWS), "mean": self.mean.tolist(), "std": self.std.tolist(),
                "w": self.w.tolist(), "b": self.b}

    @classmethod
    def from_doc(cls, d: Dict[str, Any]) -> "LogReg":
        return cls(np.array(d["mean"]), np.array(d["std"]), np.array(d["w"]), float(d["b"]))


# ------------------------------------------------------------------------------------------------ event scoring
def onset_context(score: np.ndarray, meta: np.ndarray, thr: float, quiet_s: int = 60
                  ) -> Tuple[np.ndarray, np.ndarray]:
    """B-118 N10, on fault streams (onset >= 0): (alarm_on_at_onset [N], quiet_before [N]). alarm_on_at_onset: the
    score is above thr at the step just before the onset, so detect() counts the event found at once whatever the
    fault does. quiet_before: no step above thr in the quiet_s steps (1 s each) before the onset. detect() is
    unchanged; this says how much of a recall comes from alarms that were already on."""
    from .dataset import META
    onset = meta[:, META.index("onset")].astype(int)
    al = score > thr
    on = np.zeros(len(onset), bool)
    quiet = np.zeros(len(onset), bool)
    for i, o in enumerate(onset):
        if o < 1:
            continue
        on[i] = bool(al[i, o - 1])
        quiet[i] = not al[i, max(0, o - quiet_s):o].any()
    return on, quiet


def detect(score: np.ndarray, meta: np.ndarray, thr: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """On fault streams: (found [N] bool, delay in s [N] (nan if missed), false-alarm bins before the fault [N]).

    An event is found if any step inside it has score > thr; the delay is the first such step minus the onset.
    False-alarm bins are 60 s bins of the scored part that end before the fault begins (all bins of a fault-free
    stream). Bins after the fault are not counted: a detector with memory is still reacting to the fault there."""
    from .dataset import META
    onset = meta[:, META.index("onset")].astype(int)
    end = meta[:, META.index("end")].astype(int)
    n, t = score.shape
    found = np.zeros(n, bool)
    delay = np.full(n, np.nan)
    fp = np.zeros(n, int)
    al = score > thr
    nb = (t - PRE) // BIN_S
    for i in range(n):
        if onset[i] >= 0:
            hit = np.flatnonzero(al[i, onset[i]:end[i]])
            if len(hit):
                found[i] = True
                delay[i] = float(hit[0])
        for b in range(nb):
            lo, hi = PRE + b * BIN_S, PRE + (b + 1) * BIN_S
            if onset[i] >= 0 and hi > onset[i]:
                continue
            fp[i] += bool(al[i, lo:hi].any())
    return found, delay, fp
