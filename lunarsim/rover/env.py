"""Gymnasium environment lunar/Drive-v0: drive a waypoint route on a terrain pack (PLAN §5.4).

Observation (Dict):
    patch    float32 (3, 32, 32): body-aligned grid ahead of and around the rover, 5 m spacing, rows = forward
             (row 0 nearest, 8 rows behind ... 23 ahead), columns = left..right. Channels: height relative to
             the rover / 10 m, slope / 20 deg, roughness (5 m height std per 20 m cell) / 1 m.
    scalars  float32 (5,): speed / v_cap, heading error to the pursuit point / pi, distance to the next
             waypoint / 100 m (clipped at 10), relative sun azimuth / 180 deg (0 at night), shadow flag.
Action: Box(-1, 1, (2,)): steer-rate command, throttle (fraction of the speed cap).
Time step 1 s. Teleop: actions take effect after the round-trip time (command queue), and the rover halts
for stop-to-confirm every L(rtt) metres (physics.stop_plan). Interventions (corridor exit, slope above the
hard limit, stall, roughness above the collision proxy) cost RTT + recovery time and put the rover back on
the route, stopped, at the closest point, or (version 2) at the first route point past it that is clear of the
roughness and slope limits and, when the rover stands on a hazard, more than HAZARD_CLEAR_M from that 20 m cell's
centre: the operator takes the rover across a hazard the route runs through or cuts past, so one hazard is one
intervention (as in the driving tables). Version 1 re-intervened on every step there (thousands per
drive). info["leg"] at the end: time_s, energy_wh, interventions, distance_m, stops, reached.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any, Dict, Optional

import numpy as np

from . import physics as R
from .expert import PurePursuit, densify

try:
    import gymnasium as gym
    from gymnasium import spaces
    _Base = gym.Env
except ImportError:
    gym, spaces, _Base = None, None, object

ENV_ID = "lunar/Drive-v0"
ENV_VERSION = 2          # 2: an intervention carries the rover past a hazard on the route (B-18)
HAZARD_CLEAR_M = 25.0    # resume at the first route point this far from the hazard's 20 m cell centre (> half diagonal)
DT_S = 1.0
PATCH = 32
PATCH_RES_M = 5.0
PATCH_BEHIND = 8
SCALAR_NAMES = ["speed_frac", "heading_err", "dist_wp", "sun_rel", "shadow"]


class DriveEnv(_Base):
    """options for reset(): waypoints (list of [x, y] local metres; required unless random_leg_m),
    autonomy ("teleop" | "supervised" | "autonomous"), rtt_s, sun_az_deg (float | "night" | None)."""

    metadata = {"render_modes": []}

    def __init__(self, terrain, autonomy: str = "autonomous", rtt_s: float = 4.0, sun_az_deg=0.0,
                 random_leg_m: float = 600.0, max_slope_start_deg: float = 8.0):
        if spaces is None:
            raise ImportError("DriveEnv needs gymnasium (pip install the [ml] extra)")
        self.t = terrain
        self.defaults = {"autonomy": autonomy, "rtt_s": rtt_s, "sun_az_deg": sun_az_deg}
        self.random_leg_m, self.max_slope_start = random_leg_m, max_slope_start_deg
        self.observation_space = spaces.Dict({
            "patch": spaces.Box(-10.0, 10.0, shape=(3, PATCH, PATCH), dtype=np.float32),
            "scalars": spaces.Box(-10.0, 10.0, shape=(len(SCALAR_NAMES),), dtype=np.float32)})
        self.action_space = spaces.Box(-1.0, 1.0, shape=(2,), dtype=np.float32)
        fwd = (np.arange(PATCH) - PATCH_BEHIND) * PATCH_RES_M
        lat = (np.arange(PATCH) - PATCH / 2 + 0.5) * PATCH_RES_M
        self._F, self._L = np.meshgrid(fwd, lat, indexing="ij")

    # -- episode -------------------------------------------------------------------------------------------
    def _random_route(self, rng):
        sl = self.t.slope20
        rows, cols = sl.shape
        for _ in range(1000):
            j, i = rng.integers(10, rows - 10), rng.integers(10, cols - 10)
            if sl[j, i] > self.max_slope_start:
                continue
            a = np.array([(i + 0.5) * self.t.px20, (j + 0.5) * self.t.px20])
            ang = rng.uniform(0, 2 * math.pi)
            b = a + self.random_leg_m * np.array([math.sin(ang), math.cos(ang)])
            if not self.t.contains(*b) or self.t.slope(*b) > self.max_slope_start:
                continue
            route = densify(np.array([a, b]), 50.0)
            if np.max(self.t.slope(route[:, 0], route[:, 1])) < R.ROVER["slope_nominal_deg"]:
                return route
        raise RuntimeError("no gentle random route found on this terrain")

    def reset(self, *, seed: Optional[int] = None, options: Optional[dict] = None):
        super().reset(seed=seed)
        o = {**self.defaults, **(options or {})}
        self.autonomy, self.rtt = o["autonomy"], float(o["rtt_s"])
        if self.autonomy not in R.AUTONOMY_LEVELS:
            raise ValueError(f"unknown autonomy level {self.autonomy!r}")
        self.sun = o["sun_az_deg"]
        # soil friction angle for the slip curve (Hu et al. 2024): fixed via options["phi"], else drawn per episode
        self.phi = float(o["phi"]) if o.get("phi") is not None else float(self.np_random.uniform(*R.PHI_RANGE))
        wps = o.get("waypoints")
        self.route = np.asarray(wps, float) if wps is not None else self._random_route(self.np_random)
        self.pp = PurePursuit(self.route)
        p0, p1 = self.route[0], self.route[1]
        psi = math.atan2(p1[0] - p0[0], p1[1] - p0[1]) % (2 * math.pi)
        self.state = {"x": float(p0[0]), "y": float(p0[1]), "psi": psi, "v": 0.0, "delta": 0.0}
        self.shadow = None if self.sun is None else (
            np.ones_like(self.t.slope20, bool) if self.sun == R.NIGHT else self.t.shadow_grid(float(self.sun)))
        self.rough = self.t.roughness20()
        self.v_cap0 = R.speed_cap_mps(self.autonomy, self.rtt)
        self.every_m, self.stop_s = R.stop_plan(self.autonomy, self.rtt)
        lag = int(round(self.rtt / DT_S)) if self.autonomy == "teleop" else 0
        self.queue = deque([np.zeros(2, np.float32)] * lag)
        self.time_s = self.energy_wh = self.dist_m = 0.0
        self.since_stop = 0.0
        self.stops = self.interventions = 0
        self.stall_s = 0.0
        self.steps = 0
        L = float(self.pp.s[-1])
        self.max_steps = int(min(50_000, 10 + 6 * L / max(self.v_cap0 * 0.25, 0.05)))
        return self._obs(), {}

    # -- terrain queries --------------------------------------------------------------------------------------
    def _in_shadow(self, x, y) -> bool:
        if self.shadow is None:
            return False
        j, i = self.t.cell(x, y)
        return bool(self.shadow[j, i])

    def _v_cap(self, x, y, psi) -> float:
        heading = math.degrees(psi)
        f = float(R.slope_speed_factor(self.t.slope(x, y)))
        f *= float(R.lighting_factor(heading, self.sun, self._in_shadow(x, y)))
        return self.v_cap0 * f

    def _obs(self):
        s = self.state
        sp, cp = math.sin(s["psi"]), math.cos(s["psi"])
        X = s["x"] + self._F * sp + self._L * cp            # forward along the heading, lateral to the right
        Y = s["y"] + self._F * cp - self._L * sp
        z0 = float(self.t.height(s["x"], s["y"]))
        rel = (self.t.height(X, Y) - z0) / 10.0
        slo = self.t.slope(X, Y) / 20.0
        j, i = self.t.cell(X, Y)
        rough = self.rough[j, i] / 1.0
        patch = np.clip(np.stack([rel, slo, rough]), -10, 10).astype(np.float32)
        k = self.pp.closest(s["x"], s["y"])
        tgt = self.pp.path[min(len(self.pp.path) - 1, k + int(self.pp.lookahead))]
        bearing = math.atan2(tgt[0] - s["x"], tgt[1] - s["y"])
        herr = (bearing - s["psi"] + math.pi) % (2 * math.pi) - math.pi
        dist_wp = math.hypot(*(self.route[-1] - (s["x"], s["y"])))
        if self.sun is None or self.sun == R.NIGHT:
            sun_rel = 0.0
        else:
            sun_rel = ((float(self.sun) - math.degrees(s["psi"]) + 180) % 360 - 180) / 180.0
        cap = max(self._v_cap(s["x"], s["y"], s["psi"]), 1e-6)
        scal = np.array([s["v"] / cap, herr / math.pi, min(dist_wp / 100.0, 10.0), sun_rel,
                         float(self._in_shadow(s["x"], s["y"]))], dtype=np.float32)
        return {"patch": patch, "scalars": np.clip(scal, -10, 10)}

    # -- dynamics -------------------------------------------------------------------------------------------
    def _hazard(self, x, y) -> bool:
        """A point the rover cannot stand on without an intervention: slope or roughness above the limits."""
        j, i = self.t.cell(x, y)
        return bool(self.t.slope(x, y) > R.INTERVENTION["slope_deg"] or self.rough[j, i] > R.INTERVENTION["roughness_m"])

    def _intervene(self):
        self.interventions += 1
        self.time_s += R.intervention_cost_s(self.rtt)
        x, y = self.state["x"], self.state["y"]
        k = self.pp.closest(x, y)
        k0, last = k, len(self.pp.path) - 1
        # a hazard under the rover: resume past the 20 m cell it lies in (pursuit would cut back into it otherwise)
        c = None
        if self._hazard(x, y):
            j, i = self.t.cell(x, y)
            c = ((int(i) + 0.5) * self.t.px20, (int(j) + 0.5) * self.t.px20)
        while k < last and (self._hazard(*self.pp.path[k]) or
                            (c is not None and math.hypot(self.pp.path[k][0] - c[0], self.pp.path[k][1] - c[1]) < HAZARD_CLEAR_M)):
            k += 1
        self.dist_m += float(self.pp.s[k] - self.pp.s[k0])          # the operator drives it across
        p = self.pp.path[k]
        q = self.pp.path[min(last, k + 5)]
        psi = math.atan2(q[0] - p[0], q[1] - p[1]) % (2 * math.pi) if np.any(q != p) else self.state["psi"]
        self.state.update(x=float(p[0]), y=float(p[1]), psi=psi, v=0.0, delta=0.0)
        self.stall_s = 0.0

    def step(self, action):
        a = np.clip(np.asarray(action, dtype=np.float32), -1, 1)
        if self.queue.maxlen is not None or len(self.queue):
            self.queue.append(a)
            a = self.queue.popleft()
        s = self.state
        cap = self._v_cap(s["x"], s["y"], s["psi"])
        s = R.step(s, float(a[0]), float(a[1]), cap, DT_S)
        z_a = float(self.t.height(s["x"], s["y"]))
        # along-track grade over the next metre of travel at the current heading
        z_b = float(self.t.height(s["x"] + math.sin(s["psi"]), s["y"] + math.cos(s["psi"])))
        grade = math.degrees(math.atan(z_b - z_a))
        sl = float(R.slip(grade, self.phi))
        gv = s["v"] * (1.0 - sl)
        before = self.pp.s[self.pp.closest(s["x"], s["y"])]
        s = R.advance(s, gv, DT_S)
        self.state = s
        ds = gv * DT_S
        self.dist_m += ds
        self.since_stop += ds
        self.energy_wh += float(R.energy_wh(ds, grade, sl))
        self.time_s += DT_S
        self.steps += 1
        if self.since_stop >= self.every_m:             # stop-to-confirm / approval halt
            self.time_s += self.stop_s
            self.stops += 1
            self.since_stop = 0.0
        self.stall_s = self.stall_s + DT_S if (a[1] > 0.1 and gv < 0.05) or sl >= R.DIG_IN_SLIP else 0.0
        k = self.pp.closest(s["x"], s["y"])
        xte = math.hypot(*(self.pp.path[k] - (s["x"], s["y"])))
        j, i = self.t.cell(s["x"], s["y"])
        if (xte > R.INTERVENTION["corridor_m"] or self.t.slope(s["x"], s["y"]) > R.INTERVENTION["slope_deg"]
                or self.stall_s >= R.INTERVENTION["stall_s"] or self.rough[j, i] > R.INTERVENTION["roughness_m"]):
            self._intervene()
        progress = self.pp.s[self.pp.closest(self.state["x"], self.state["y"])] - before
        reward = progress / 10.0 - 0.001
        reached = self.pp.done(self.state["x"], self.state["y"])
        truncated = not reached and self.steps >= self.max_steps
        info: Dict[str, Any] = {}
        if reached or truncated:
            info["leg"] = {"time_s": self.time_s, "energy_wh": self.energy_wh, "interventions": self.interventions,
                           "distance_m": self.dist_m, "stops": self.stops, "reached": bool(reached),
                           "autonomy": self.autonomy, "rtt_s": self.rtt, "sun_az_deg": self.sun}
        return self._obs(), float(reward), bool(reached), bool(truncated), info


def drive_expert(env: DriveEnv, options: Dict[str, Any], seed: int = 0) -> Dict[str, Any]:
    """Run the pure-pursuit expert through one episode; returns info["leg"]."""
    env.reset(seed=seed, options=options)
    pp = PurePursuit(env.route)
    while True:
        cap = env._v_cap(env.state["x"], env.state["y"], env.state["psi"])
        _, _, term, trunc, info = env.step(np.array(pp.action(env.state, cap), dtype=np.float32))
        if term or trunc:
            return info["leg"]
