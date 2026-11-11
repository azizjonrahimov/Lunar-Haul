"""Fault definitions for position reports, and the honest disturbances that are not faults.

Setting: observer A hears B's position reports at 1 Hz and measures the range to B. Everything A uses is built here:
  nav_error()   a vehicle's own navigation error: collapses to fix_sigma_m at an absolute fix (taken at every stop and
                at Poisson points along the distance driven), then grows with the dead-reckoned displacement (a scale-factor error
                and a heading error drawn once per fix interval, each 1-sigma dr_error_frac). The uncertainty the
                vehicle CLAIMS is sqrt(fix_sigma^2 + (dr_error_frac_nominal x distance driven since the fix)^2).
  FAULTS        the five named faults (import these: FAULTS["drift"].lo, sample_fault(), inject()).
  pair_stream() one stream of what A knows about B: the ten per-step features, the label and the in-range flag.
Ranging has two classes (note 01, section D): UWB two-way ranging up to uwb_range_max_m, and long-range two-way
ranging over the base radio from there to the radio line of sight; the class in use is one of A's inputs.

Honest disturbances in fault-free data: B stopping and starting (from the simulator), A's and B's error growing and
collapsing at a fix (a fix moves the report by metres at once: an honest jump, announced by the claimed uncertainty),
range and report dropouts beyond the radio line of sight, a change of ranging class at the UWB limit, and positive
blocked-path range bias in bursts.
Faults act on B's reported position only; B's claimed uncertainty stays as if nothing had happened.
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS_FILE = os.path.join(HERE, "pnt_params.json")

FEATURES = ("z", "range_m", "rep_speed_mps", "rep_dheading_rad", "rep_sigma_m", "own_sigma_m", "lq_degraded",
            "own_fix_age_s", "range_valid", "range_class_long")
F_Z, F_RANGE, F_SPEED, F_DHEAD, F_SIGB, F_SIGA, F_LQ, F_FIXAGE, F_VALID, F_CLASS = range(10)
MOON_RADIUS_M = 1737.4e3
SPEED_BASE_S = 5          # reported speed = displacement of the reports over this many seconds
HEAD_BASE_S = 10          # heading change between two consecutive displacements of this length
HEAD_GATE_M = 3.0         # ... only when both displacements exceed this
LEAD = 2 * HEAD_BASE_S    # extra steps before a stream so the derived features exist at its first step
GUARD_S = 128             # after a fault ends, steps that are neither scored nor trained on


def load_params(path: Optional[str] = None) -> Dict[str, Any]:
    with open(path or PARAMS_FILE, encoding="utf-8") as f:
        doc = json.load(f)
    p = {k: v["value"] for k, v in doc["params"].items()}
    p["_status"] = doc["status"]
    p["_ood"] = doc["ood"]
    return p


def true_params(p: Dict[str, Any], ood: bool) -> Dict[str, Any]:
    """What the world does (differs from what A's filter assumes only in the out-of-distribution set)."""
    q = dict(p)
    mult = p["_ood"]["range_noise_mult"] if ood else 1.0
    q["uwb_range_noise_true_m"] = p["uwb_range_noise_m"] * mult
    q["long_range_noise_true_m"] = p["long_range_noise_m"] * mult
    q["dr_error_frac_true"] = p["_ood"]["dr_error_frac_true"] if ood else p["dr_error_frac"]
    return q


# ------------------------------------------------------------------------------------------------ fault definitions
@dataclass(frozen=True)
class FaultDef:
    name: str
    label: str
    unit: str
    lo: float            # training / in-distribution magnitude range
    hi: float
    ood_lo: float        # out-of-distribution magnitude range (equal to lo, hi where the task names none)
    ood_hi: float
    log_uniform: bool
    what: str


FAULTS: Dict[str, FaultDef] = {
    "jump": FaultDef("jump", "jump", "m", 5.0, 50.0, 2.0, 5.0, False,
                     "a step offset in a random direction, held until the fault ends"),
    "drift": FaultDef("drift", "slow drift", "m/s", 0.01, 0.5, 0.005, 0.01, True,
                      "an offset that grows linearly from zero in a random direction"),
    "frozen": FaultDef("frozen", "frozen report", "-", 0.0, 0.0, 0.0, 0.0, False,
                       "the reported navigation solution stops updating while B moves (report noise goes on)"),
    "frame": FaultDef("frame", "frame error", "m", 300.0, 1000.0, 300.0, 1000.0, False,
                      "a constant offset, as when the principal-axis frame is used for the mean-Earth frame"),
    "noise": FaultDef("noise", "noise inflation", "x", 3.0, 10.0, 3.0, 10.0, False,
                      "the report noise is multiplied; the claimed uncertainty is not"),
}
FAULT_TYPES = tuple(FAULTS)                     # order = type id 1..5 (0 = fault-free)
EVENT_S = (120, 600)                            # fault length in seconds, uniform
FROZEN_MIN_MOVE_M = 10.0                        # a frozen report is a fault only if B moves at least this far


def sample_fault(name: str, rng: np.random.Generator, ood: bool = False) -> Tuple[float, float]:
    """(magnitude, direction in rad) for a named fault."""
    f = FAULTS[name]
    lo, hi = (f.ood_lo, f.ood_hi) if ood else (f.lo, f.hi)
    if hi <= lo:
        mag = lo
    elif f.log_uniform:
        mag = float(math.exp(rng.uniform(math.log(lo), math.log(hi))))
    else:
        mag = float(rng.uniform(lo, hi))
    return mag, float(rng.uniform(0.0, 2.0 * math.pi))


def inject(name: str, nav_xy: np.ndarray, noise_xy: np.ndarray, onset: int, end: int, mag: float,
           direction: float) -> np.ndarray:
    """B's reported positions [T, 2] with the named fault active on steps onset <= t < end.

    nav_xy = B's navigation solution (true position + navigation error); noise_xy = the white report noise."""
    rep = nav_xy + noise_xy
    u = np.array([math.cos(direction), math.sin(direction)])
    t = np.arange(end - onset)
    if name == "jump" or name == "frame":
        rep[onset:end] += mag * u
    elif name == "drift":
        rep[onset:end] += (mag * (t + 1.0))[:, None] * u
    elif name == "frozen":
        rep[onset:end] = nav_xy[onset] + noise_xy[onset:end]
    elif name == "noise":
        rep[onset:end] = nav_xy[onset:end] + mag * noise_xy[onset:end]
    else:
        raise ValueError(name)
    return rep


# ------------------------------------------------------------------------------------------------ navigation error
def nav_error(xy: np.ndarray, moving: np.ndarray, p: Dict[str, Any], rng: np.random.Generator
              ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(error [T, 2], claimed 1-sigma per axis [T], seconds since the last fix [T]) for one vehicle's month."""
    T = len(xy)
    stop = np.flatnonzero(moving[:-1] & ~moving[1:]) + 1                    # a fix at every stop
    x64 = xy.astype(np.float64)
    step = np.hypot(*np.diff(x64, axis=0, prepend=x64[:1]).T)
    cum = np.cumsum(step)
    n_rand = int(rng.poisson(cum[-1] / p["fix_spacing_m"]))               # fixes while driving, Poisson in distance
    rand = np.searchsorted(cum, rng.uniform(0.0, cum[-1], n_rand)) if n_rand else np.zeros(0, np.int64)
    fix = np.unique(np.clip(np.r_[0, stop, rand], 0, T - 1)).astype(np.int64)
    n = len(fix)
    e0 = rng.normal(0.0, p["fix_sigma_m"], (n, 2))
    sc = rng.normal(0.0, p["dr_error_frac_true"], n)                        # scale-factor error
    ps = rng.normal(0.0, p["dr_error_frac_true"], n)                        # heading error, rad
    k = np.searchsorted(fix, np.arange(T), side="right") - 1                # fix interval of each step
    d = x64 - x64[fix][k]
    err = e0[k] + np.stack([sc[k] * d[:, 0] - ps[k] * d[:, 1], ps[k] * d[:, 0] + sc[k] * d[:, 1]], axis=1)
    dist = cum - cum[fix][k]
    sigma = np.sqrt(p["fix_sigma_m"] ** 2 + (p["dr_error_frac"] * dist) ** 2)
    age = (np.arange(T) - fix[k]).astype(np.float32)
    return err.astype(np.float32), sigma.astype(np.float32), age


def range_limit_m(h_a: float, h_b: float, p: Dict[str, Any]) -> float:
    """Radio line of sight between two antennas on a smooth Moon, capped at long_range_cap_m."""
    return min(float(p["long_range_cap_m"]),
               math.sqrt(2.0 * MOON_RADIUS_M * h_a) + math.sqrt(2.0 * MOON_RADIUS_M * h_b))


# ------------------------------------------------------------------------------------------------ one stream
def pair_stream(pa: np.ndarray, pb: np.ndarray, ea: np.ndarray, eb: np.ndarray, sa: np.ndarray, sb: np.ndarray,
                age_a: np.ndarray, p: Dict[str, Any], rng: np.random.Generator,
                fault: Optional[Tuple[str, int, int, float, float]] = None, limit_m: Optional[float] = None
                ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """What A knows about B on one stream.

    Inputs are slices of the month arrays that start LEAD steps before the stream: true positions pa, pb [LEAD + T, 2],
    navigation errors ea, eb, claimed sigmas sa, sb and A's fix age. fault = (name, onset, end, magnitude, direction)
    with onset and end counted from the stream's first step, or None. limit_m = the pair's radio line of sight.
    Ranging class per step: UWB up to uwb_range_max_m, the long-range base radio beyond it, nothing beyond limit_m.
    Returns (features [T, 10] float32 in the order FEATURES, label [T] uint8, in_range [T] bool)."""
    n = len(pa)
    pa = pa.astype(np.float64)
    pb = pb.astype(np.float64)
    dist = np.hypot(pb[:, 0] - pa[:, 0], pb[:, 1] - pa[:, 1])
    valid = dist <= (p["long_range_cap_m"] if limit_m is None else limit_m)
    long = dist > p["uwb_range_max_m"]
    # range measurement: white noise of the class in use, positive blocked-path bias in bursts, a link-quality flag
    nlos = np.zeros(n)
    for _ in range(int(rng.poisson(p["nlos_rate_per_h"] * n / 3600.0))):
        s = int(rng.integers(0, n))
        L = int(rng.uniform(*p["nlos_burst_s"]))
        nlos[s:s + L] = p["nlos_bias_m"]
    rho = dist + rng.normal(0.0, 1.0, n) * np.where(long, p["long_range_noise_true_m"],
                                                    p["uwb_range_noise_true_m"]) + nlos
    u = rng.random(n)
    lq = np.where(nlos > 0, u < p["lq_detect_prob"], u < p["lq_false_prob"])
    # B's reports
    nav_b = pb + eb
    noise = rng.normal(0.0, p["report_noise_m"], (n, 2))
    label = np.zeros(n, np.uint8)
    if fault is None:
        rep = nav_b + noise
    else:
        name, onset, end, mag, direction = fault
        rep = inject(name, nav_b, noise, onset + LEAD, end + LEAD, mag, direction)
        label[onset + LEAD:end + LEAD] = 1
    sig_b = np.sqrt(sb.astype(np.float64) ** 2 + p["report_noise_m"] ** 2)       # what B claims
    # A's side: own estimate, predicted range, normalised innovation
    est_a = pa + ea
    pred = np.hypot(rep[:, 0] - est_a[:, 0], rep[:, 1] - est_a[:, 1])
    S = (np.where(long, p["long_range_noise_m"], p["uwb_range_noise_m"]) ** 2 + sa.astype(np.float64) ** 2
         + sig_b ** 2)
    z = (rho - pred) / np.sqrt(S)
    # reported speed and heading change, from the reports A heard
    k = SPEED_BASE_S
    dsp = np.zeros((n, 2))
    dsp[k:] = rep[k:] - rep[:-k]
    ok_sp = np.zeros(n, bool)
    ok_sp[k:] = valid[k:] & valid[:-k]
    speed = np.where(ok_sp, np.hypot(dsp[:, 0], dsp[:, 1]) / k, 0.0)
    h = HEAD_BASE_S
    d1 = np.zeros((n, 2))
    d0 = np.zeros((n, 2))
    d1[2 * h:] = rep[2 * h:] - rep[h:-h]
    d0[2 * h:] = rep[h:-h] - rep[:-2 * h]
    ok_h = np.zeros(n, bool)
    ok_h[2 * h:] = valid[2 * h:] & valid[h:-h] & valid[:-2 * h]
    n1, n0 = np.hypot(d1[:, 0], d1[:, 1]), np.hypot(d0[:, 0], d0[:, 1])
    ang = np.arctan2(d0[:, 0] * d1[:, 1] - d0[:, 1] * d1[:, 0], d0[:, 0] * d1[:, 0] + d0[:, 1] * d1[:, 1])
    dhead = np.where(ok_h & (n1 > HEAD_GATE_M) & (n0 > HEAD_GATE_M), ang, 0.0)
    X = np.zeros((n, len(FEATURES)), np.float32)
    v = valid.astype(np.float64)
    X[:, F_Z] = z * v
    X[:, F_RANGE] = rho * v
    X[:, F_SPEED] = speed
    X[:, F_DHEAD] = dhead
    X[:, F_SIGB] = sig_b * v
    X[:, F_SIGA] = sa
    X[:, F_LQ] = lq * v
    X[:, F_FIXAGE] = age_a
    X[:, F_VALID] = v
    X[:, F_CLASS] = long * v
    return X[LEAD:], label[LEAD:], valid[LEAD:]
