"""3-DoF translational lander dynamics for lunar/Descent-v0 (pure numpy; ported line by line to JS).

Frame: target (pad centre) at the origin; x, y horizontal (metres), z up (altitude above the local ground
plane). The vehicle is a point mass whose single main-engine thrust acts along a body axis tilted from
vertical by two angles, as in Gaudet et al. 2018's 3-DoF formulation with a rate-limited thrust direction:

    u = (sin tx * cos ty,  sin ty,  cos tx * cos ty)          unit thrust direction
    tilt from vertical: cos(tilt) = cos tx * cos ty

State vector (float64, length 11):
    0 x, 1 y, 2 z, 3 vx, 4 vy, 5 vz   position (m) and velocity (m/s)
    6 m                               total mass (kg)
    7 tx, 8 ty                        thrust-axis angles (rad)
    9 wx, 10 wy                       their rates over the last step (rad/s)

Action (3 numbers in [-1, 1]):
    a0 throttle: thrust = t_min + (a0 + 1) / 2 * (t_max - t_min)   (the engine stays lit at its floor)
    a1, a2 commanded slew rates wx = a1 * tilt_rate_max, wy = a2 * tilt_rate_max; each angle is then
            clipped to [-tilt_max, tilt_max] (the rate actually achieved is recorded in the state).

Integration over dt with thrust and direction held after the slew (constant acceleration):
    p' = p + v dt + a dt^2 / 2,   v' = v + a dt,   m' = m - T / (Isp g0) dt
Thrust stops when the usable propellant (m - m_dry) is gone. No contact model here: the environment
detects z <= 0 and interpolates the touchdown state (touchdown()).
"""
from __future__ import annotations

import math
from typing import Tuple

import numpy as np

from .classes import G_MOON, G0, LanderClass

X, Y, Z, VX, VY, VZ, M, TX, TY, WX, WY = range(11)
STATE_SIZE = 11


def make_state(pos, vel, m, tx=0.0, ty=0.0) -> np.ndarray:
    s = np.zeros(STATE_SIZE)
    s[X:Z + 1] = pos
    s[VX:VZ + 1] = vel
    s[M] = m
    s[TX], s[TY] = tx, ty
    return s


def thrust_direction(tx: float, ty: float) -> Tuple[float, float, float]:
    return math.sin(tx) * math.cos(ty), math.sin(ty), math.cos(tx) * math.cos(ty)


def tilt_deg(tx: float, ty: float) -> float:
    """Angle between the thrust axis and local vertical, degrees."""
    c = max(-1.0, min(1.0, math.cos(tx) * math.cos(ty)))
    return math.degrees(math.acos(c))


def angles_from_direction(ux: float, uy: float, uz: float) -> Tuple[float, float]:
    """Inverse of thrust_direction for a unit vector (uz > 0)."""
    ty = math.asin(max(-1.0, min(1.0, uy)))
    tx = math.atan2(ux, uz)
    return tx, ty


def throttle_to_thrust(a0: float, cls: LanderClass, thrust_scale: float = 1.0) -> float:
    a0 = max(-1.0, min(1.0, a0))
    return thrust_scale * (cls.t_min_n + 0.5 * (a0 + 1.0) * (cls.t_max_n - cls.t_min_n))


def thrust_to_throttle(t_n: float, cls: LanderClass, thrust_scale: float = 1.0) -> float:
    """Inverse of throttle_to_thrust, clipped to [-1, 1]."""
    a0 = 2.0 * (t_n / thrust_scale - cls.t_min_n) / (cls.t_max_n - cls.t_min_n) - 1.0
    return max(-1.0, min(1.0, a0))


def step(state: np.ndarray, action, cls: LanderClass, dt: float, thrust_scale: float = 1.0,
         isp_scale: float = 1.0, m_dry: float = None) -> Tuple[np.ndarray, float]:
    """Advance one step. Returns (new_state, thrust_n actually produced). Does not modify `state`.

    thrust_scale / isp_scale are the per-episode domain-randomisation factors (1.0 = nominal);
    m_dry defaults to the class dry mass (the env passes the randomised value)."""
    s = state.copy()
    if m_dry is None:
        m_dry = cls.m_dry_kg
    a0 = max(-1.0, min(1.0, float(action[0])))
    a1 = max(-1.0, min(1.0, float(action[1])))
    a2 = max(-1.0, min(1.0, float(action[2])))

    # slew the thrust axis at the commanded rate, angles limited to +-tilt_max
    tilt_max = math.radians(cls.tilt_max_deg)
    rate_max = math.radians(cls.tilt_rate_max_dps)
    tx_new = max(-tilt_max, min(tilt_max, s[TX] + a1 * rate_max * dt))
    ty_new = max(-tilt_max, min(tilt_max, s[TY] + a2 * rate_max * dt))
    s[WX], s[WY] = (tx_new - s[TX]) / dt, (ty_new - s[TY]) / dt
    s[TX], s[TY] = tx_new, ty_new

    # thrust and mass flow
    thrust = throttle_to_thrust(a0, cls, thrust_scale)
    mdot = thrust / (cls.isp_s * isp_scale * G0)
    prop = s[M] - m_dry
    if prop <= 0.0:
        thrust, mdot = 0.0, 0.0
    elif mdot * dt > prop:                     # burn the last propellant for part of the step
        thrust *= prop / (mdot * dt)
        mdot = prop / dt

    ux, uy, uz = thrust_direction(s[TX], s[TY])
    ax = thrust * ux / s[M]
    ay = thrust * uy / s[M]
    az = thrust * uz / s[M] - G_MOON

    s[X] += s[VX] * dt + 0.5 * ax * dt * dt
    s[Y] += s[VY] * dt + 0.5 * ay * dt * dt
    s[Z] += s[VZ] * dt + 0.5 * az * dt * dt
    s[VX] += ax * dt
    s[VY] += ay * dt
    s[VZ] += az * dt
    s[M] -= mdot * dt
    return s, thrust


def touchdown(prev: np.ndarray, new: np.ndarray) -> np.ndarray:
    """State at the instant z crosses 0 between two steps, by linear interpolation of every component."""
    z0, z1 = prev[Z], new[Z]
    f = 1.0 if z0 == z1 else max(0.0, min(1.0, z0 / (z0 - z1)))
    s = prev + f * (new - prev)
    s[Z] = 0.0
    s[WX], s[WY] = new[WX], new[WY]
    return s
