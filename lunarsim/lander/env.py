"""Gymnasium environment lunar/Descent-v0: terminal descent from the SPLICE gate to touchdown.

Physics in physics.py (3-DoF point mass, rate-limited thrust axis). This module adds the episode: initial
dispersion around the gate, domain randomisation, the navigation/altimeter sensor model, the observation
vector, the touchdown classification and the reward variants. Constants below carry flags.

Observation (15 floats): obs_i = (raw_i - OBS_OFFSET_i) / OBS_SCALE_i, clipped to [-10, 10]; raw features
are *estimates* (sensor model applied). Action (3 floats in [-1, 1]): throttle, tilt-rate commands (physics.py).

Outcome record in `info["outcome"]` at the end of every episode (PLAN §5.3, plus a few diagnostic fields):
    {miss_m:[dx,dy], v_td:[vx,vy,vz], tilt_deg, rate_dps, landed_tilt_deg, slope_deg, prop_used_kg,
     t_below_30m_s, t_flight_s, ok, touchdown_ok, failure_kind}
failure_kind: None | "velocity" | "tilt" | "offpad" | "sensor" | "timeout" | "lost"
("timeout" and "lost" extend the PLAN list: episode cap reached in the air; left the 3 km box).
"""
from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np

from . import physics as P
from .classes import CLASSES, G_MOON, GATE, TIPOVER_DEG, TOUCHDOWN, LanderClass

try:
    import gymnasium as gym
    from gymnasium import spaces
    _Base = gym.Env
except ImportError:  # physics/policy stay usable without the [ml] extra
    gym, spaces, _Base = None, None, object

ENV_ID = "lunar/Descent-v0"
ENV_VERSION = 1            # bump when dynamics, observation or outcome definitions change

DT_S = 0.2                 # guidance step (Gaudet et al. 2018 update every 0.2 s), Modelled
MAX_STEPS = 750            # 150 s episode cap, Assumed (gate-to-touchdown ~60-90 s nominal)
LOST_RANGE_M = 3000.0      # horizontal distance or altitude beyond which the episode ends as "lost", Assumed

# initial dispersion around the SPLICE gate (1-sigma unless stated), all Assumed
DISP = {"downrange_m": 25.0, "crossrange_m": 25.0, "altitude_m": 20.0, "vh_mps": 2.0, "vcross_mps": 1.0,
        "vz_mps": 1.0, "tilt0_deg": (10.0, 30.0)}    # initial braking tilt drawn uniformly in this range
# domain randomisation (uniform ranges), Assumed (Gaudet et al. used mass +-5 %)
DR = {"dry_mass": (0.95, 1.05), "prop": (0.90, 1.10), "thrust": (0.95, 1.05), "isp": (0.97, 1.03),
      "sensor_noise": (0.5, 2.0)}
# sensor model, scaled per episode by DR["sensor_noise"]
SENSOR = {
    "nav_bias_m": 1.5,         # per-episode horizontal navigation bias per axis, Assumed (Lugo et al. 2020: final nav
                               # position error < 4 m with TRN: https://ntrs.nasa.gov/api/citations/20205003002/downloads/nav.pdf)
    "nav_noise_m": 0.5,        # per-step horizontal noise, Assumed
    "vel_noise_mps": 0.05,     # velocimeter noise, Spec range 1.7-10 cm/s (SPLICE PL&HA requirements)
    "alt_noise_hi_m": 0.2,     # altimeter noise above the low-altitude regime, Assumed
    "low_alt_m": 30.0,         # below this the altimeter degrades (IM-2, ispace M1/M2 failure regime), Modelled
    "alt_bias_low_m": 1.0,     # per-episode altimeter bias below 30 m (sigma), Assumed
    "alt_noise_low_m": 0.5,    # per-step altimeter noise below 30 m, Assumed
    "alt_dropout_p": 0.05,     # per-step probability that the altimeter holds its last value below 30 m, Assumed
}
# landed tilt = local slope + K_VH * v_h + K_VZ * max(0, |v_z| - vz_max): Assumed coefficients, chosen so that a
# SPLICE-box landing on a 5 deg slope stays below 12 deg and the IM-1 case (12 deg slope, 0.9 m/s lateral, 2.7 m/s
# vertical) tips over.
K_VH_DEG_PER_MPS = 3.0
K_VZ_DEG_PER_MPS = 1.0
SITE_SLOPE_DEG = (0.0, 5.0)   # local slope under the lander, uniform, Assumed (prepared pad .. good natural site)

# reward variants (Gaudet-style; coefficients Modelled after Gaudet et al. 2018 Table 5 / 2019 meta-RL, rescaled)
# crash: gated terminal penalty per m/s outside the velocity box (Gaudet et al. terminate attitude violations with
# gamma = -100; without a crash cost the shaping makes an early crash a local optimum). no_eta keeps pure Gaudet
# shaping (no eta, no crash cost) to show that pathology.
# zeta: attitude-rate penalty per deg/s below 30 m (the 2 deg/s touchdown limit; a stochastic policy otherwise
# arrives slewing). eta = 0.01 as Gaudet et al.: with a larger eta, hovering out the episode pays more than landing.
_BASE = {"alpha": -0.05, "beta": -0.05, "delta": -0.05, "zeta": -0.01, "eta": 0.01, "kappa": 10.0, "lost": -10.0,
         "crash": -1.0, "low_time": 0.0, "low_thrust": 0.0}
REWARD_VARIANTS: Dict[str, Dict[str, float]] = {
    "baseline":    dict(_BASE),
    "no_eta":      {**_BASE, "eta": 0.0, "crash": 0.0},
    "hover_bonus": {**_BASE, "eta": 0.3},
    "fuel_heavy":  {**_BASE, "beta": -0.5},
    "plume_aware": {**_BASE, "low_time": -0.02, "low_thrust": -0.1},
}
# velocity field (Gaudet et al. 2019 meta-RL: v_o, tau1 = 20 s above 15 m, tau2 = 100 s below), Modelled
VF = {"v0_mps": 20.0, "hover_alt_m": 15.0, "tau_hi_s": 20.0, "tau_lo_s": 100.0, "vz_hi_mps": -2.0, "vz_lo_mps": -1.0}

OBS_NAMES = ["x", "y", "h", "vx", "vy", "vz", "ex", "ey", "ez", "tx", "ty", "wx", "wy", "prop_frac", "tw_max"]
ACT_NAMES = ["throttle", "tilt_rate_x_cmd", "tilt_rate_y_cmd"]


def obs_scale(cls: LanderClass) -> np.ndarray:
    tm, wm = math.radians(cls.tilt_max_deg), math.radians(cls.tilt_rate_max_dps)
    return np.array([500, 500, 500, 30, 30, 15, 10, 10, 10, tm, tm, wm, wm, 1, 3], dtype=np.float64)


OBS_OFFSET = np.zeros(len(OBS_NAMES))


def target_velocity(pos, vel) -> np.ndarray:
    """Gaudet-style velocity field: towards a hover point 15 m above the target, then down at 1 m/s.
    v_targ = -v0 * r/|r| * (1 - exp(-t_go/tau)) + (0, 0, vz_off), t_go = |r| / |v - (0,0,vz_off)|."""
    pos = np.asarray(pos, float)
    vel = np.asarray(vel, float)
    if pos[2] > VF["hover_alt_m"]:
        r = pos - np.array([0.0, 0.0, VF["hover_alt_m"]])
        off, tau = VF["vz_hi_mps"], VF["tau_hi_s"]
    else:
        r = pos.copy()
        off, tau = VF["vz_lo_mps"], VF["tau_lo_s"]
    off_v = np.array([0.0, 0.0, off])
    rn = float(np.linalg.norm(r))
    if rn < 1e-6:
        return off_v
    t_go = rn / max(float(np.linalg.norm(vel - off_v)), 1e-3)
    return -VF["v0_mps"] * r / rn * (1.0 - math.exp(-t_go / tau)) + off_v


def classify(td: np.ndarray, slope_deg: float, pad_radius_m: float, sensor_fault: bool) -> Dict[str, Any]:
    """Touchdown record from the interpolated contact state."""
    vh = math.hypot(td[P.VX], td[P.VY])
    vz = td[P.VZ]
    tilt = P.tilt_deg(td[P.TX], td[P.TY])
    rate = math.degrees(math.hypot(td[P.WX], td[P.WY]))
    landed = slope_deg + K_VH_DEG_PER_MPS * vh + K_VZ_DEG_PER_MPS * max(0.0, abs(vz) - TOUCHDOWN["vz_max_mps"])
    miss = math.hypot(td[P.X], td[P.Y])
    vel_ok = abs(vz) <= TOUCHDOWN["vz_max_mps"] and vh <= TOUCHDOWN["vh_max_mps"]
    att_ok = tilt <= TOUCHDOWN["tilt_max_deg"] and rate <= TOUCHDOWN["rate_max_dps"]
    if not vel_ok:
        kind = "velocity"
    elif not att_ok or landed > TIPOVER_DEG:
        kind = "tilt"
    elif miss > pad_radius_m:
        kind = "offpad"
    else:
        kind = None
    # attribution rule (Modelled): a near-miss (|vz| within 2x the limit) while the altimeter was wrong by > 1 m or
    # holding a dropped-out value is counted as a sensor failure, the IM-2 / ispace pattern
    if kind in ("velocity", "tilt") and sensor_fault and abs(vz) <= 2 * TOUCHDOWN["vz_max_mps"]:
        kind = "sensor"
    return {"miss_m": [float(td[P.X]), float(td[P.Y])], "v_td": [float(td[P.VX]), float(td[P.VY]), float(vz)],
            "tilt_deg": tilt, "rate_dps": rate, "landed_tilt_deg": landed, "slope_deg": slope_deg,
            "touchdown_ok": bool(vel_ok and att_ok and landed <= TIPOVER_DEG), "ok": kind is None,
            "failure_kind": kind}


class DescentEnv(_Base):
    """lunar/Descent-v0. Options: cls ("CLPS" | "MK1" | "LARGE"), variant (REWARD_VARIANTS key),
    randomize (domain randomisation + dispersion), sensor (sensor model on), pad_radius_m (off-pad threshold;
    default SPLICE 50 m delivery radius), site_slope_deg (uniform range)."""

    metadata = {"render_modes": []}

    def __init__(self, cls: str = "CLPS", variant: str = "baseline", randomize: bool = True, sensor: bool = True,
                 pad_radius_m: float = TOUCHDOWN["delivery_radius_m"], site_slope_deg=SITE_SLOPE_DEG,
                 max_steps: int = MAX_STEPS, dt: float = DT_S, curriculum: float = 0.0):
        if spaces is None:
            raise ImportError("DescentEnv needs gymnasium (pip install the [ml] extra)")
        if cls not in CLASSES:
            raise ValueError(f"unknown lander class {cls!r}; known: {', '.join(CLASSES)}")
        if variant not in REWARD_VARIANTS:
            raise ValueError(f"unknown reward variant {variant!r}; known: {', '.join(REWARD_VARIANTS)}")
        self.cls_name, self.cls = cls, CLASSES[cls]
        self.variant, self.rw = variant, REWARD_VARIANTS[variant]
        self.randomize, self.sensor_on = randomize, sensor
        self.pad_radius_m, self.site_slope_deg = pad_radius_m, tuple(site_slope_deg)
        self.max_steps, self.dt = max_steps, dt
        self.curriculum = curriculum   # training only: share of resets that start in the terminal phase
        self.scale = obs_scale(self.cls)
        self.observation_space = spaces.Box(-10.0, 10.0, shape=(len(OBS_NAMES),), dtype=np.float32)
        self.action_space = spaces.Box(-1.0, 1.0, shape=(3,), dtype=np.float32)
        self.state = None

    # -- episode setup ---------------------------------------------------------
    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        rng = self.np_random
        c = self.cls
        u = (lambda lo_hi: rng.uniform(*lo_hi)) if self.randomize else (lambda lo_hi: 1.0)
        n = (lambda s: rng.normal(0.0, s)) if self.randomize else (lambda s: 0.0)
        self.m_dry = c.m_dry_kg * u(DR["dry_mass"])
        prop = c.prop_gate_kg * u(DR["prop"])
        self.thrust_scale, self.isp_scale = u(DR["thrust"]), u(DR["isp"])
        self.noise = u(DR["sensor_noise"]) if self.sensor_on else 0.0

        psi = rng.uniform(0.0, 2 * math.pi) if self.randomize else 0.0      # approach azimuth
        e = np.array([math.cos(psi), math.sin(psi)])                          # direction of travel
        nrm = np.array([-e[1], e[0]])
        gate = {**GATE, **c.gate_overrides}
        down = gate["downrange_m"] + n(DISP["downrange_m"])
        pos_h = -down * e + n(DISP["crossrange_m"]) * nrm
        z = gate["altitude_m"] + n(DISP["altitude_m"])
        v_h = (gate["vh_mps"] + n(DISP["vh_mps"])) * e + n(DISP["vcross_mps"]) * nrm
        vz = gate["vz_mps"] + n(DISP["vz_mps"])
        tilt0 = math.radians(rng.uniform(*DISP["tilt0_deg"]) if self.randomize else 20.0)
        ux, uy, uz = -math.sin(tilt0) * e[0], -math.sin(tilt0) * e[1], math.cos(tilt0)   # braking: thrust against travel
        tx, ty = P.angles_from_direction(ux, uy, uz)
        if self.curriculum > 0 and rng.random() < self.curriculum:
            # terminal-phase start (training curriculum): 5-100 m up, near the target, slow, nearly upright
            pos_h = rng.normal(0.0, 15.0, 2)
            z = rng.uniform(5.0, 100.0)
            v_h = rng.normal(0.0, 1.5, 2)
            vz = -rng.uniform(0.5, 5.0)
            tx, ty = rng.normal(0.0, math.radians(3.0), 2)
        self.state = P.make_state([pos_h[0], pos_h[1], z], [v_h[0], v_h[1], vz], self.m_dry + prop, tx, ty)
        self.m0 = self.state[P.M]

        lo, hi = self.site_slope_deg
        self.slope_deg = rng.uniform(lo, hi) if self.randomize else lo
        s = self.noise
        self.nav_bias = np.array([n(SENSOR["nav_bias_m"] * s), n(SENSOR["nav_bias_m"] * s)]) if s else np.zeros(2)
        self.alt_bias = n(SENSOR["alt_bias_low_m"] * s) if s else 0.0
        self.alt_hold = None
        self.dropouts_recent = 0
        self.last_alt_err = 0.0
        self.steps = 0
        self.t_below_30 = 0.0
        self.thrust_n = P.throttle_to_thrust(0.0, c, self.thrust_scale)
        return self._obs(), {}

    # -- sensing ---------------------------------------------------------------
    def _measure(self):
        s, rng, k = self.state, self.np_random, self.noise
        x = s[P.X] + self.nav_bias[0] + (rng.normal(0, SENSOR["nav_noise_m"] * k) if k else 0.0)
        y = s[P.Y] + self.nav_bias[1] + (rng.normal(0, SENSOR["nav_noise_m"] * k) if k else 0.0)
        v = s[P.VX:P.VZ + 1] + (rng.normal(0, SENSOR["vel_noise_mps"] * k, 3) if k else 0.0)
        z = s[P.Z]
        if not k:
            h = z
        elif z >= SENSOR["low_alt_m"]:
            h = z + rng.normal(0, SENSOR["alt_noise_hi_m"] * k)
            self.alt_hold = h
        else:
            if self.alt_hold is not None and rng.random() < SENSOR["alt_dropout_p"]:
                h = self.alt_hold                  # dropout: altimeter repeats its last value
                self.dropouts_recent = 10          # remembered for 2 s (sensor attribution)
            else:
                h = z + self.alt_bias + rng.normal(0, SENSOR["alt_noise_low_m"] * k)
                self.alt_hold = h
        self.dropouts_recent = max(0, self.dropouts_recent - 1)
        self.last_alt_err = h - z
        return np.array([x, y, h]), np.asarray(v, float)

    def _obs(self):
        pos, vel = self._measure()
        e = vel - target_velocity(pos, vel)
        s = self.state
        prop_frac = max(0.0, s[P.M] - self.m_dry) / max(self.cls.prop_gate_kg, 1e-9)
        tw = self.cls.t_max_n / (s[P.M] * G_MOON)
        raw = np.array([pos[0], pos[1], pos[2], vel[0], vel[1], vel[2], e[0], e[1], e[2], s[P.TX], s[P.TY],
                        s[P.WX], s[P.WY], prop_frac, tw])
        self.last_est = (pos, vel)
        return np.clip((raw - OBS_OFFSET) / self.scale, -10, 10).astype(np.float32)

    # -- dynamics ----------------------------------------------------------------
    def step(self, action):
        rw, c = self.rw, self.cls
        prev = self.state
        new, thrust = P.step(prev, action, c, self.dt, self.thrust_scale, self.isp_scale, self.m_dry)
        self.thrust_n = thrust
        self.steps += 1
        z = new[P.Z]
        if 0 < z < SENSOR["low_alt_m"] or (z <= 0 < prev[P.Z] < SENSOR["low_alt_m"]):
            self.t_below_30 += self.dt
        tf = thrust / (c.t_max_n * self.thrust_scale)

        # shaping on the true state
        vt = target_velocity(new[P.X:P.Z + 1], new[P.VX:P.VZ + 1])
        reward = rw["alpha"] * float(np.linalg.norm(new[P.VX:P.VZ + 1] - vt)) + rw["beta"] * tf + rw["eta"]
        if z < SENSOR["low_alt_m"]:
            reward += rw["delta"] * max(0.0, P.tilt_deg(new[P.TX], new[P.TY]) - TOUCHDOWN["tilt_max_deg"]) / 6.0
            reward += rw["zeta"] * math.degrees(math.hypot(new[P.WX], new[P.WY]))
            reward += rw["low_time"] + (rw["low_thrust"] * tf * tf if z < 10.0 else 0.0)

        terminated = truncated = False
        info: Dict[str, Any] = {}
        if z <= 0.0:
            td = P.touchdown(prev, new)
            self.state = td
            out = classify(td, self.slope_deg, self.pad_radius_m,
                           sensor_fault=self.noise > 0 and (abs(self.last_alt_err) > 1.0 or self.dropouts_recent > 0))
            if out["touchdown_ok"]:
                miss = math.hypot(*out["miss_m"])
                reward += rw["kappa"] * (0.5 + 0.5 * math.exp(-miss / 10.0))
            else:
                vh, vz = math.hypot(td[P.VX], td[P.VY]), abs(td[P.VZ])
                reward += rw["crash"] * (max(0.0, vz - TOUCHDOWN["vz_max_mps"]) + max(0.0, vh - TOUCHDOWN["vh_max_mps"]))
            terminated = True
            info["outcome"] = self._finish(out)
            return self._obs(), float(reward), terminated, truncated, info
        self.state = new
        if math.hypot(new[P.X], new[P.Y]) > LOST_RANGE_M or z > LOST_RANGE_M:
            reward += rw["lost"]
            terminated = True
            info["outcome"] = self._finish(self._airborne("lost"))
        elif self.steps >= self.max_steps:
            truncated = True
            info["outcome"] = self._finish(self._airborne("timeout"))
        return self._obs(), float(reward), terminated, truncated, info

    def _airborne(self, kind: str) -> Dict[str, Any]:
        s = self.state
        return {"miss_m": [float(s[P.X]), float(s[P.Y])], "v_td": [float(s[P.VX]), float(s[P.VY]), float(s[P.VZ])],
                "tilt_deg": P.tilt_deg(s[P.TX], s[P.TY]), "rate_dps": math.degrees(math.hypot(s[P.WX], s[P.WY])),
                "landed_tilt_deg": None, "slope_deg": self.slope_deg, "touchdown_ok": False, "ok": False,
                "failure_kind": kind}

    def _finish(self, out: Dict[str, Any]) -> Dict[str, Any]:
        out["prop_used_kg"] = float(self.m0 - self.state[P.M])
        out["t_below_30m_s"] = float(self.t_below_30)
        out["t_flight_s"] = float(self.steps * self.dt)
        out["cls"] = self.cls_name
        return out
