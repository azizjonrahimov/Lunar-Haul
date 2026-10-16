"""Rover driving physics on a terrain pack (pure numpy; ported line by line to JS).

Everything here is a plain function of (slope, speed, autonomy, RTT, lighting) so that the step-by-step
environment (env.py) and the fast leg integrator used for the driving tables (tables.py) share one model.

Constants carry flags (Measured / Spec / Modelled / Assumed) and sources from
reports/Lunar landing and rover autonomy logistics.md and research_notes/.../rover_autonomy_driving.md.

Units: metres, seconds, kg, Wh; slopes in degrees; speeds in m/s unless a name says km/h.
"""
from __future__ import annotations

import math
from typing import Dict, Tuple

import numpy as np

G_MOON = 1.62
KMH = 1.0 / 3.6                          # km/h -> m/s

LITAKER_URL = "https://ntrs.nasa.gov/api/citations/20240011392/downloads/Teleops%20IEEE%20Paper%20FY24%20FINAL.pdf"
HU_URL = "https://arxiv.org/abs/2405.11001"
LRV_URLS = ["https://www.apollojournals.org/alsj/a17/a17.clsout3.html", "https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html"]
CHEN_URL = "https://www.frontiersin.org/journals/astronomy-and-space-sciences/articles/10.3389/fspas.2026.1764826/full"

# --- vehicle --------------------------------------------------------------------------------------------
ROVER = {
    "mass_kg": 1600.0,            # Assumed: LTV-class vehicle with cargo (LTV payload >= 800 kg; NatGeo 2024)
    "wheelbase_m": 3.0,           # Assumed
    "steer_max_deg": 30.0,        # Assumed
    "steer_rate_dps": 20.0,       # Assumed
    "accel_mps2": 0.3,            # Assumed
    "slope_nominal_deg": 15.0,    # Spec: designs converge on 15 deg nominal (VIPER, Intrepid)
    "slope_hard_deg": 20.0,       # Spec: LTV / RACER / Endurance 20 deg requirement; government-reference LTV +-20 deg
}

# --- speed by autonomy level (moving speed caps on flat ground, daylight) --------------------------------
AUTONOMY_LEVELS = ("teleop", "supervised", "autonomous")
SPEED_CAP_KMH = {
    "autonomous": 9.0,            # Measured analogue: Apollo LRV moving average 8.1-9.2 km/h (vehicle limits 10-15 km/h)
    "supervised": 3.0,            # Assumed within the 0.5-3.6 km/h modelling range (no lunar demonstration)
}
SUPERVISED_STOP = {"every_m": 500.0, "stop_s": 60.0}   # Assumed: periodic human approval of the next segment

# Teleop (Earth operator, round-trip time RTT). Litaker et al. 2025 (JSC simulator, Measured):
#   speed made good incl. stops 3.24 / 2.56 / 2.03 / 1.76 km/h at RTT 0 / 4 / 6 / 8 s
#   speed without stops         3.80 / 3.55 km/h at RTT 0 / 4 s
# Model (Modelled): moving speed v_move(rtt) = 3.80 - 0.0625 rtt km/h (the two measured points, linear beyond 4 s)
# plus stop-to-confirm cadence: a stop every L(rtt) metres costing T_LOOK + 2 rtt seconds (camera pan to
# ground-truth, then confirm: one image and one command round trip). L(rtt) is solved so that a flat leg
# reproduces the four speed-made-good values exactly; it is interpolated linearly in rtt between them.
LITAKER_SMG_KMH = {0.0: 3.24, 4.0: 2.56, 6.0: 2.03, 8.0: 1.76}
TELEOP_V0_KMH, TELEOP_DV_KMH_PER_S = 3.80, (3.80 - 3.55) / 4.0
TELEOP_T_LOOK_S = 30.0            # Assumed; >95 % of navigation at 6-8 s used the 180 deg camera pan (Litaker)


def teleop_move_kmh(rtt_s: float) -> float:
    return TELEOP_V0_KMH - TELEOP_DV_KMH_PER_S * rtt_s


def teleop_stop_s(rtt_s: float) -> float:
    return TELEOP_T_LOOK_S + 2.0 * rtt_s


def _cadence_point(rtt: float, smg_kmh: float) -> float:
    overhead_s_per_m = 3.6 / smg_kmh - 3.6 / teleop_move_kmh(rtt)     # s per metre spent stopped
    return teleop_stop_s(rtt) / overhead_s_per_m


TELEOP_CADENCE_M = {rtt: _cadence_point(rtt, v) for rtt, v in LITAKER_SMG_KMH.items()}


def teleop_cadence_m(rtt_s: float) -> float:
    """Distance between stop-to-confirm halts (m), piecewise linear in RTT through the calibration points."""
    xs = sorted(TELEOP_CADENCE_M)
    if rtt_s <= xs[0]:
        return TELEOP_CADENCE_M[xs[0]]
    for a, b in zip(xs[:-1], xs[1:]):
        if rtt_s <= b:
            f = (rtt_s - a) / (b - a)
            return TELEOP_CADENCE_M[a] + f * (TELEOP_CADENCE_M[b] - TELEOP_CADENCE_M[a])
    return TELEOP_CADENCE_M[xs[-1]]


def speed_cap_mps(autonomy: str, rtt_s: float = 0.0) -> float:
    """Wheel-speed cap (m/s) such that the *ground* speed on flat ground in daylight, after the flat-ground slip,
    equals the measured/assumed moving speed (Litaker's and Apollo's speeds are ground speeds)."""
    if autonomy == "teleop":
        ground_kmh = teleop_move_kmh(rtt_s)
    elif autonomy in SPEED_CAP_KMH:
        ground_kmh = SPEED_CAP_KMH[autonomy]
    else:
        raise ValueError(f"unknown autonomy level {autonomy!r}")
    return ground_kmh * KMH / (1.0 - FLAT_SLIP_REF)


def stop_plan(autonomy: str, rtt_s: float = 0.0) -> Tuple[float, float]:
    """(stop every m, seconds per stop); (inf, 0) when the level does not stop."""
    if autonomy == "teleop":
        return teleop_cadence_m(rtt_s), teleop_stop_s(rtt_s)
    if autonomy == "supervised":
        return SUPERVISED_STOP["every_m"], SUPERVISED_STOP["stop_s"]
    return math.inf, 0.0


# --- slope: speed factor and slip --------------------------------------------------------------------------
# Slip vs slope along the heading (uphill positive): Hu et al. 2024 (Chrono CRM, validated against NASA GRC SLOPE-lab
# tests), Figs 7 and 13, 440 kg VIPER-class rover in LUNAR gravity on GRC-3 simulant, digitised in
# research_notes/.../verification_round_1.md section 5. One curve per soil friction angle phi (Modelled):
#   phi 47.8 deg (dense, rho 1839): 0.01 0.03 0.08 0.18 0.35 0.76 0.88  at 0/5/10/15/20/25/30 deg
#   phi 42.0 deg (medium, 1734):    0.04 0.13 0.30 0.67 0.86 0.92 0.96
#   phi 37.8 deg (loose, 1627):     0.12 0.32 0.74 0.88 0.93 0.95 0.97
# slip() interpolates linearly in slope and in phi (clipped to the digitised range). The driving tables sample phi
# uniformly in [37.8, 47.8] per run (rover.tables), the env per episode; calibrations use the median curve phi 42.
# (The light MGRU3 rover on Earth slips far less, e.g. 0.10 at 10 deg on phi 42: Earth tests are optimistic.)
HU_URL = "https://arxiv.org/abs/2405.11001"
SLIP_TABLE_DEG = np.array([0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0])
SLIP_PHI_DEG = np.array([37.8, 42.0, 47.8])
SLIP_CURVES = np.array([[0.12, 0.32, 0.74, 0.88, 0.93, 0.95, 0.97],      # phi 37.8
                        [0.04, 0.13, 0.30, 0.67, 0.86, 0.92, 0.96],      # phi 42.0
                        [0.01, 0.03, 0.08, 0.18, 0.35, 0.76, 0.88]])     # phi 47.8
PHI_RANGE = (37.8, 47.8)        # sampled uniformly (Assumed: no site-specific soil data for the south-pole sites)
PHI_REF = 42.0                  # median curve, used by the flat-ground calibrations
SLIP_TABLE = SLIP_CURVES[1]     # the phi-42 curve (kept for callers of the old name)
DIG_IN_SLIP = 0.80              # Hu et al.: "slip values above 80% place the rover in a situation that increases
                                # the propensity for dig-in"


def slip(grade_deg, phi_deg=PHI_REF):
    """Longitudinal slip for the slope along the direction of travel (uphill > 0) and soil friction angle phi.
    Downhill (and flat) travel uses the curve's flat-ground value; beyond 30 deg the 30 deg value."""
    g = np.clip(np.asarray(grade_deg, dtype=float), 0.0, SLIP_TABLE_DEG[-1])
    phi = np.clip(np.asarray(phi_deg, dtype=float), SLIP_PHI_DEG[0], SLIP_PHI_DEG[-1])
    s = [np.interp(g, SLIP_TABLE_DEG, c) for c in SLIP_CURVES]          # per phi curve
    lo = np.where(phi <= SLIP_PHI_DEG[1], 0, 1)
    p0, p1 = SLIP_PHI_DEG[lo], SLIP_PHI_DEG[lo + 1]
    w = (phi - p0) / (p1 - p0)
    a = np.where(lo == 0, s[0], s[1])
    b = np.where(lo == 0, s[1], s[2])
    out = (1.0 - w) * a + w * b
    return out if np.ndim(out) else float(out)


FLAT_SLIP_REF = slip(0.0, PHI_REF)     # 0.04


def slope_speed_factor(slope_deg):
    """Speed multiplier for the local terrain slope (any direction): 1 up to 10 deg, 0.5 at 15 deg (nominal
    limit), 0.25 at 20 deg (hard limit), 0 beyond. Assumed (slower driving on slopes; JSC crews drove the
    7 and 15 deg scenarios slowly)."""
    return np.interp(np.asarray(slope_deg, dtype=float), [0, 10, 15, 20, 20.001], [1.0, 1.0, 0.5, 0.25, 0.0])


# --- lighting ------------------------------------------------------------------------------------------------
# JSC lighting study (Litaker / Bell; sun 1-2 deg): drivers up-sun tacked +-20-30 deg; entering shadow with lit
# terrain in view made artificial lights useless; shadowed slopes "very difficult" to judge -> slower driving.
UP_SUN_HALF_ANGLE_DEG = 45.0     # Assumed: "up-sun" = heading within 45 deg of the sun azimuth
UP_SUN_TACK_DEG = 25.0           # Measured range 20-30 deg; tacking lengthens the path by 1 / cos(25 deg) = 1.10
SHADOW_SPEED_FACTOR = 0.5        # Assumed: driving in shadow (or at night) on headlights
NIGHT = "night"


def lighting_factor(heading_deg, sun_az_deg, in_shadow):
    """Speed-made-good multiplier from lighting: up-sun tacking and shadow/night slow-down."""
    h = np.asarray(heading_deg, dtype=float)
    shade = np.asarray(in_shadow, dtype=bool)
    f = np.where(shade, SHADOW_SPEED_FACTOR, 1.0)
    if sun_az_deg is not None and sun_az_deg != NIGHT:
        d = np.abs((h - float(sun_az_deg) + 180.0) % 360.0 - 180.0)
        up = (d <= UP_SUN_HALF_ANGLE_DEG) & ~shade
        f = np.where(up, f * math.cos(math.radians(UP_SUN_TACK_DEG)), f)
    return f if f.ndim else float(f)


# --- energy -------------------------------------------------------------------------------------------------
# Apollo LRV (Measured): 1.58 Ah/km (A17) and 1.67 Ah/km (A15) at 36 V = 57-60 Wh/km for ~700 kg (210 kg vehicle +
# 490 kg payload incl. crew), flat-to-moderate terrain at ~9 km/h. Calibration: on flat ground with the flat-ground
# slip, E = C_RR_EFF m g / (1 - slip) per metre = 58.5 Wh/km at 700 kg gives the implied effective rolling
# coefficient (rolling resistance + drivetrain losses) below. Applying it to a 1.6 t cargo rover is Assumed.
LRV_WH_PER_KM, LRV_MASS_KG = 58.5, 700.0
C_RR_EFF = LRV_WH_PER_KM * 3.6 * (1.0 - FLAT_SLIP_REF) / (LRV_MASS_KG * G_MOON)     # ~0.178 (Modelled; phi 42 flat slip)
DRIVE_EFF = 0.7                  # Assumed: motor + gear efficiency for the grade term
HOTEL_W = 0.0                    # avionics/comms power while driving, not included (stated in the tables)


def energy_wh(ds_m, grade_deg, slip_ratio, mass_kg: float = ROVER["mass_kg"]):
    """Traction energy (Wh) for ds metres at the given along-track grade and slip: (rolling + grade) work at the
    wheels divided by (1 - slip) (wheels turn further than the ground made good). Downhill grade work is not
    recovered (no regeneration)."""
    th = np.radians(np.asarray(grade_deg, dtype=float))
    f_roll = C_RR_EFF * mass_kg * G_MOON * np.cos(th)
    f_grade = np.maximum(0.0, mass_kg * G_MOON * np.sin(th)) / DRIVE_EFF
    return (f_roll + f_grade) * np.asarray(ds_m, dtype=float) / (1.0 - np.asarray(slip_ratio, dtype=float)) / 3600.0


# --- interventions ------------------------------------------------------------------------------------------
INTERVENTION = {
    "corridor_m": 25.0,           # Assumed: leaving 25 m either side of the planned path
    "slope_deg": ROVER["slope_hard_deg"],
    "stall_s": 30.0,              # Assumed: no progress for 30 s with throttle applied (or slip above dig-in)
    "roughness_m": 0.5,           # Assumed collision proxy: local height residual std over the footprint
    "recovery_s": 300.0,          # Assumed: operator recovery time after an intervention (cost = RTT + recovery)
}


def intervention_cost_s(rtt_s: float) -> float:
    return rtt_s + INTERVENTION["recovery_s"]


def step(state: Dict[str, float], steer_rate_cmd: float, throttle_cmd: float, v_cap: float, dt: float):
    """Kinematic bicycle, one step. state: x, y, psi (rad, map azimuth: 0 = +y, 90 deg = +x), v (m/s), delta (rad).
    v_cap: speed cap after slope and lighting factors; the rover accelerates towards throttle_cmd * v_cap.
    Ground speed made good = v * (1 - slip) is applied by the caller via `ground_factor`."""
    s = dict(state)
    dmax = math.radians(ROVER["steer_max_deg"])
    s["delta"] = max(-dmax, min(dmax, s["delta"] + max(-1.0, min(1.0, steer_rate_cmd)) * math.radians(ROVER["steer_rate_dps"]) * dt))
    v_target = max(0.0, min(1.0, throttle_cmd)) * v_cap
    dv = max(-ROVER["accel_mps2"] * dt, min(ROVER["accel_mps2"] * dt, v_target - s["v"]))
    s["v"] = max(0.0, s["v"] + dv)
    return s


def advance(state: Dict[str, float], ground_v: float, dt: float) -> Dict[str, float]:
    """Move along the heading at the ground speed, turning with the bicycle model."""
    s = dict(state)
    s["psi"] = (s["psi"] + ground_v / ROVER["wheelbase_m"] * math.tan(s["delta"]) * dt) % (2 * math.pi)
    s["x"] += ground_v * math.sin(s["psi"]) * dt
    s["y"] += ground_v * math.cos(s["psi"]) * dt
    return s
