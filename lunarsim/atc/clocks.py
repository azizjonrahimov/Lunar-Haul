"""Vehicle clocks and time transfer (B-91, problem 3, experiment E51).

Research note 01 (`research_notes/Lunar Rover Interaction Protocol/01_positioning_and_time.md`), sections B6, B7, D,
E4-E6; source tags as in the note.

Model. Each vehicle's clock error against the base time scale (the base computer's rubidium-class time server, the
reference here) is, since its last successful two-way time transfer at t_s,

    x(t) = r + y (t - t_s) + 1/2 A (t - t_s)^2          (note E6 "Holdover"; the random part is below these terms)

r: the residual of the transfer, normal with sigma 100 ns (note D "Time-transfer accuracy, two-way over a surface
   link", A; bounded by [NIST-TT], [CSAC], [G8271]);
y: the clock's fractional frequency error, constant over the window per vehicle (the transfer corrects the offset, not
   the frequency: conservative):
   - crystal (TCXO): uniform 0 to 8 x 10^-7, the range LuGRE's crystal moved through on the lunar surface with
     temperature [LUGRE26] MOON (note D: 4 x 10^-7 default, sweep 2 x 10^-7 to 10^-6);
   - chip-scale atomic clock (CSAC): normal, sigma 3 x 10^-10 (temperature term [CSAC]);
A: linear ageing: CSAC 9 x 10^-10 per month [CSAC] (the sign drawn per vehicle); crystal 0 (its temperature term
   dominates);
plus, in the "earth_scale" variant, the Moon-minus-Earth rate +6.4844 x 10^-10 (56.02 us/day; note E4 [ASH24, KK24,
TUR25]) for a vehicle whose clock counts Earth seconds while the base counts lunar seconds.

A transfer succeeds only when the vehicle has a radio path to the base mast at that moment (lunarsim.atc.pnt.LOS, the
B-70 mesh), so a vehicle out of reach free-runs until it is heard again.

Effects (note E5, E6):
- one-way ranging error to a base-clock beacon: c x |x| (1 ns = 0.2998 m);
- two-way single-sided ranging error between two vehicles: c x T_reply x |y_a - y_b| / 2 (T_reply 1 ms);
- a time-stamped position read by another node: v x |x_a - x_b|;
- a road reservation stamped in the vehicle's own clock is truly at stamp - x: two conflicting reservations whose
  true windows come closer than allowed by the guard are a conflict caused by clock error alone.
"""
from __future__ import annotations

import math
from typing import Dict, Optional, Sequence

import numpy as np

C_M_S = 299792458.0
RATE_MOON_MINUS_EARTH = 6.4844e-10       # note 01 E4 (CALC): +56.025 us/day; 56.0199(12) [ASH24]
MONTH_S = 30.0 * 86400.0
CLASSES: Dict[str, Dict[str, float]] = {
    "crystal": {"y_lo": 0.0, "y_hi": 8e-7, "ageing_per_month": 0.0},       # [LUGRE26] MOON; note D
    "csac": {"y_sigma": 3e-10, "ageing_per_month": 9e-10},                  # [CSAC] data sheet (not space-rated)
    "rubidium": {"y_sigma": 1e-12, "ageing_per_month": 0.0},               # [INTEROP25]; base reference class
}
TT_SIGMA_S = 100e-9                      # note 01 D, A
T_REPLY_S = 1e-3                         # note 01 E5 example
GUARD_S = 0.1                            # note 01 B7: road-segment reservation, needed clock agreement 0.1 s
# note 01 B7 "Timing accuracy needed": budget (s) per use
USES: Dict[str, float] = {
    "one-way ranging, 1 m": 1.0 / C_M_S,
    "one-way ranging to a base clock, 10 m": 10.0 / C_M_S,
    "TDMA slots, 5G NR class (1.5 us)": 1.5e-6,
    "TDMA slots, relaxed mesh (30 us)": 30e-6,
    "logging and auction time stamps (1 ms)": 1e-3,
    "time-stamped position report (10 ms)": 10e-3,
    "road-segment reservation (0.1 s)": 0.1,
}


def draw(n: int, cls: str, rng: np.random.Generator, earth_scale: bool = False):
    """Per-vehicle frequency error y and ageing A (per second)."""
    c = CLASSES[cls]
    if "y_hi" in c:
        y = rng.uniform(c["y_lo"], c["y_hi"], n)
    else:
        y = rng.normal(0.0, c["y_sigma"], n)
    A = rng.choice([-1.0, 1.0], n) * ageing_rate(cls)          # change of y per second, sign per vehicle
    if earth_scale:
        y = y + RATE_MOON_MINUS_EARTH
    return y, A


def ageing_rate(cls: str) -> float:
    """|A| in 1/s: the change of y per second (ageing per month / seconds per month)."""
    return CLASSES[cls]["ageing_per_month"] / MONTH_S


class Clocks:
    """Clock errors of n vehicles over a window: sync attempts every `interval_s` from t0 (seconds), successful where
    `contact(k)` (k: attempt index) says so for that vehicle; query x(t) by vehicle and time."""

    def __init__(self, y: np.ndarray, A: np.ndarray, t0_s: float, interval_s: Optional[float], contact, n_att: int,
                 rng: np.random.Generator, tt_sigma_s: float = TT_SIGMA_S):
        self.y, self.A = np.asarray(y, float), np.asarray(A, float)
        n = len(self.y)
        self.t_sync, self.r = [], []
        for i in range(n):
            ts = [t0_s]
            if interval_s is not None:
                ok = np.nonzero(contact(i))[0]
                ts += list(t0_s + (ok + 1) * interval_s)
            ts = np.asarray(ts, float)
            self.t_sync.append(ts)
            self.r.append(rng.normal(0.0, tt_sigma_s, len(ts)))

    def x(self, i: int, t_s) -> np.ndarray:
        t = np.atleast_1d(np.asarray(t_s, float))
        ts = self.t_sync[i]
        k = np.clip(np.searchsorted(ts, t, side="right") - 1, 0, len(ts) - 1)
        dt = t - ts[k]
        return self.r[i][k] + self.y[i] * dt + 0.5 * self.A[i] * dt * dt


def holdover_s(budget_s: float, y: float, A: float = 0.0, r: float = 0.0) -> float:
    """Time for |r + y t + A t^2 / 2| to reach budget (y, A >= 0 taken as magnitudes; inf if never)."""
    y, A = abs(y), abs(A)
    rem = budget_s - abs(r)
    if rem <= 0:
        return 0.0
    if A == 0.0:
        return math.inf if y == 0.0 else rem / y
    return (-y + math.sqrt(y * y + 2.0 * A * rem)) / A
