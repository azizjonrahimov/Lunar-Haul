"""Monte Carlo evaluation of descent controllers -> landing-outcome tables the DES samples (PLAN §5.3).

    python -m lunarsim.lander.evaluate --policy data/policies/lander_CLPS_baseline_s0.json --n 500
    python -m lunarsim.lander.evaluate --classical --cls CLPS --n 500

Writes <out-dir>/outcomes_<name>.json (format lunarsim-landing-outcomes v1: per-episode records + summary
with mean/std/min/max of every touchdown component, propellant, time below 30 m, pass rate) and a CSV of the
episodes. Both controllers see the same dispersed initial conditions (episode i uses seed seed0 + i) and the
same sensor model.

Classical baseline (the paper's comparison): ZEM/ZEV feedback guidance (Ebrahimi et al. 2008 form,
a = 6 ZEM / t_go^2 - 2 ZEV / t_go) to a point 10 m above the target at -1 m/s, then a vertical
terminal phase holding -1 m/s with horizontal PD nulling (the SPLICE terminal-descent profile: "a vertical
descent ... from 30 m altitude to touchdown, at a velocity of 1 m/s downward"). t_go is re-estimated every
step from the vertical channel, t_go = 2 (h - 10) / (max(-vz, 0.5) + 1). The velocity estimate is smoothed
and the terminal-phase thrust direction is low-pass filtered (sensor noise otherwise drives the attitude
rate past the 2 deg/s touchdown limit), and held constant below 3 m. Gains are Assumed.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from . import physics as P
from .classes import CLASSES, G_MOON

OUT_FORMAT = "lunarsim-landing-outcomes"
COMPONENTS = ["miss_r_m", "miss_x_m", "miss_y_m", "vx_td", "vy_td", "vz_td", "vh_td", "tilt_deg", "rate_dps",
              "landed_tilt_deg", "prop_used_kg", "t_below_30m_s", "t_flight_s"]

# classical-law constants (Assumed)
ZEM_AIM_ALT_M = 10.0
ZEM_AIM_VZ = -1.0
TERM_VZ = -1.0
K_VZ = 1.0          # 1/s, vertical speed loop
K_PH = 0.05         # 1/s^2, horizontal position loop
K_VH = 0.6          # 1/s, horizontal velocity loop
EST_ALPHA = 0.3     # exponential smoothing of the velocity estimate (per 0.2 s step)
CMD_ALPHA = 0.25    # first-order filter on the thrust-direction command in the terminal phase
HOLD_ALT_M = 3.0    # below this the thrust direction is held (attitude-hold for touchdown)


def classical_action(env) -> np.ndarray:
    """ZEM/ZEV + vertical terminal phase, computed from the env's *estimated* state (same sensors as the policy).
    Keeps a little filter state on the env object (reset when env.steps == 0)."""
    (pos, vel), s, c = env.last_est, env.state, env.cls
    if env.steps == 0 or getattr(env, "_cl", None) is None:
        env._cl = {"vel": np.array(vel, float), "u": None}
    mem = env._cl
    mem["vel"] = (1 - EST_ALPHA) * mem["vel"] + EST_ALPHA * np.asarray(vel, float)
    vel = mem["vel"]
    m = s[P.M]
    g = np.array([0.0, 0.0, -G_MOON])
    h = pos[2]
    terminal = h <= ZEM_AIM_ALT_M + 5.0
    if not terminal:
        rf = np.array([0.0, 0.0, ZEM_AIM_ALT_M])
        vf = np.array([0.0, 0.0, ZEM_AIM_VZ])
        tgo = max(3.0, 2.0 * (h - ZEM_AIM_ALT_M) / (max(-vel[2], 0.5) + abs(ZEM_AIM_VZ)))
        zem = rf - (pos + vel * tgo + 0.5 * g * tgo * tgo)
        zev = vf - (vel + g * tgo)
        a = 6.0 * zem / (tgo * tgo) - 2.0 * zev / tgo
    else:
        a = np.array([-K_PH * pos[0] - K_VH * vel[0], -K_PH * pos[1] - K_VH * vel[1], G_MOON + K_VZ * (TERM_VZ - vel[2])])
    F = m * a
    F[2] = max(F[2], 1e-3 * m)                      # the engine cannot push down
    tmax = math.radians(c.tilt_max_deg)
    fh = math.hypot(F[0], F[1])
    if fh > F[2] * math.tan(tmax):                  # respect the tilt limit, keep the vertical component
        k = F[2] * math.tan(tmax) / fh
        F[0] *= k
        F[1] *= k
    T = float(np.linalg.norm(F))
    u = F / T
    if terminal and mem["u"] is not None:
        if h < HOLD_ALT_M:
            u = mem["u"]
        else:
            u = (1 - CMD_ALPHA) * mem["u"] + CMD_ALPHA * u
            u /= np.linalg.norm(u)
    mem["u"] = u
    tx, ty = P.angles_from_direction(*u)
    wmax = math.radians(c.tilt_rate_max_dps)                  # angle target -> rate command for one step
    rx = max(-1.0, min(1.0, (tx - s[P.TX]) / (env.dt * wmax)))
    ry = max(-1.0, min(1.0, (ty - s[P.TY]) / (env.dt * wmax)))
    return np.array([P.thrust_to_throttle(T, c), rx, ry], dtype=np.float32)


def run_episodes(env, controller: Callable, n: int, seed0: int = 0) -> List[Dict[str, Any]]:
    """controller(obs, env) -> action. Returns the outcome record of every episode."""
    out = []
    for i in range(n):
        obs, _ = env.reset(seed=seed0 + i)
        info: Dict[str, Any] = {}
        done = False
        while not done:
            obs, _, term, trunc, info = env.step(controller(obs, env))
            done = term or trunc
        rec = dict(info["outcome"])
        rec["seed"] = seed0 + i
        out.append(rec)
    return out


def _flat(r: Dict[str, Any]) -> Dict[str, Any]:
    mx, my = r["miss_m"]
    vx, vy, vz = r["v_td"]
    return {"miss_r_m": math.hypot(mx, my), "miss_x_m": mx, "miss_y_m": my, "vx_td": vx, "vy_td": vy, "vz_td": vz,
            "vh_td": math.hypot(vx, vy), "tilt_deg": r["tilt_deg"], "rate_dps": r["rate_dps"],
            "landed_tilt_deg": r["landed_tilt_deg"], "prop_used_kg": r["prop_used_kg"],
            "t_below_30m_s": r["t_below_30m_s"], "t_flight_s": r["t_flight_s"]}


def summarise(recs: List[Dict[str, Any]]) -> Dict[str, Any]:
    n = len(recs)
    kinds: Dict[str, int] = {}
    for r in recs:
        k = r["failure_kind"] or "none"
        kinds[k] = kinds.get(k, 0) + 1
    flat = [_flat(r) for r in recs]
    comp = {}
    for c in COMPONENTS:
        v = np.array([f[c] for f in flat if f[c] is not None], dtype=float)
        comp[c] = ({"mean": float(v.mean()), "std": float(v.std(ddof=1)) if len(v) > 1 else 0.0,
                    "min": float(v.min()), "max": float(v.max()), "p50": float(np.percentile(v, 50)),
                    "p90": float(np.percentile(v, 90)), "n": int(len(v))} if len(v) else None)
    ok = sum(r["ok"] for r in recs)
    td = sum(r["touchdown_ok"] for r in recs)
    return {"n": n, "pass_rate": ok / n if n else None, "touchdown_box_rate": td / n if n else None,
            "failure_counts": kinds, "components": comp}


def write_outcomes(recs, out_dir: str, name: str, meta: Dict[str, Any]) -> str:
    os.makedirs(out_dir, exist_ok=True)
    doc = {"format": OUT_FORMAT, "version": 1, **meta, "summary": summarise(recs),
           "fields": "miss_m [dx,dy] m; v_td [vx,vy,vz] m/s; tilt_deg/rate_dps at contact; landed_tilt_deg; "
                     "prop_used_kg; t_below_30m_s; ok; failure_kind",
           "episodes": recs}
    path = os.path.join(out_dir, f"outcomes_{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    with open(os.path.join(out_dir, f"outcomes_{name}.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["seed", "cls", "ok", "touchdown_ok", "failure_kind"] + COMPONENTS)
        for r in recs:
            fl = _flat(r)
            w.writerow([r["seed"], r["cls"], int(r["ok"]), int(r["touchdown_ok"]), r["failure_kind"] or ""] +
                       ["" if fl[c] is None else f"{fl[c]:.6g}" for c in COMPONENTS])
    return path


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


EVAL_SEED0 = 100_000           # first Monte Carlo episode seed (training uses other seeds)


def evaluate(policy_path: Optional[str], cls: str, n: int, seed0: int = EVAL_SEED0, sensor: bool = True,
             out_dir: Optional[str] = None, name: Optional[str] = None) -> Dict[str, Any]:
    """Run the Monte Carlo; write the table if out_dir. Returns the summary (plus the path)."""
    from .env import DescentEnv, ENV_ID, ENV_VERSION
    from .policy import MlpPolicy
    env = DescentEnv(cls=cls, sensor=sensor)
    if policy_path:
        pol = MlpPolicy.from_json(policy_path)
        controller = lambda obs, e: pol.act(obs)
        name = name or pol.id
        meta = {"policy": pol.id, "policy_sha256": _sha(policy_path), "controller": "policy"}
    else:
        controller = lambda obs, e: classical_action(e)
        name = name or f"classical_{cls}"
        meta = {"policy": name, "policy_sha256": None, "controller": "classical ZEM/ZEV + vertical terminal phase"}
    t0 = time.time()
    recs = run_episodes(env, controller, n, seed0)
    meta.update({"env": ENV_ID, "env_version": ENV_VERSION, "cls": cls, "n": n, "seed0": seed0, "sensor": sensor,
                 "wallclock_s": round(time.time() - t0, 2)})
    summ = summarise(recs)
    if out_dir:
        summ["path"] = write_outcomes(recs, out_dir, name, meta)
    return summ


def main(argv=None):
    p = argparse.ArgumentParser(description="Monte Carlo landing outcomes for a policy or the classical law")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--policy", help="lunarsim-policy v1 JSON")
    g.add_argument("--classical", action="store_true")
    p.add_argument("--cls", default="CLPS", choices=sorted(CLASSES))
    p.add_argument("--n", type=int, default=500)
    p.add_argument("--seed0", type=int, default=EVAL_SEED0, help="first episode seed (training uses other seeds)")
    p.add_argument("--no-sensor", action="store_true")
    p.add_argument("--out-dir", default=os.path.join("data", "policies"))
    a = p.parse_args(argv)
    s = evaluate(a.policy, a.cls, a.n, a.seed0, not a.no_sensor, a.out_dir)
    c = s["components"]
    print(f"{a.n} episodes: pass {100 * s['pass_rate']:.1f} %, touchdown box {100 * s['touchdown_box_rate']:.1f} %, "
          f"failures {s['failure_counts']}")
    for k in ("miss_r_m", "vz_td", "vh_td", "tilt_deg", "prop_used_kg", "t_below_30m_s"):
        if c[k]:
            print(f"  {k:15s} mean {c[k]['mean']:8.3f}  std {c[k]['std']:7.3f}  min {c[k]['min']:8.3f}  max {c[k]['max']:8.3f}")
    print(f"wrote {s.get('path')}")


if __name__ == "__main__":
    main()
