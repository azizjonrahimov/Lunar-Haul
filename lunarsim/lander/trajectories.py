"""Descent trajectories for the 3D landing lab (B-33; format ``lunarsim-trajectories`` v1).

    python -m lunarsim.lander.trajectories                     # -> data/policies/trajectories-v1.json
    python -m lunarsim.lander.trajectories --check             # replay every exported episode and compare

For each lander class x pilot, episodes are picked from the existing 500-episode Monte Carlo (outcomes_<name>.json,
seeds EVAL_SEED0 + i, the same dispersed initial conditions for every pilot): the episodes whose |miss| is nearest
the 10th, 50th and 90th percentile of |miss| over the episodes that reached the ground (not "timeout" / "lost"; all
episodes when none did; ties go to the lower seed), and the first failure (lowest seed with ok = false). Each is
replayed in lunar/Descent-v0 (the current env, ENV_VERSION) from its seed with the pilot, and recorded:

- positions and velocities at 10 Hz (t = 0, 0.1, ... and the end instant): exact within each 0.2 s guidance step,
  where the model holds thrust and direction constant (p = p0 + v0 h + a h^2 / 2);
- per guidance step k (the interval [0.2 (k-1), 0.2 k]; the model slews the thrust axis at the start of the step):
  throttle = thrust / maximum thrust (0-1; the engine floor is t_min / t_max), thrust direction (unit vector),
  attitude quaternion [w, x, y, z] (the rotation taking body +z to the thrust direction, no roll), propellant left
  (kg, at the end of the step), the altimeter reading the pilot saw (m, sensor model: noise, bias, dropouts) and the
  reward terms of that step (track, effort, low_alt, terminal; plus the constant eta per step) so the lab's SCORE
  counter ticks from real data: reward = track + effort + eta + low_alt + terminal (checked to 1e-9 per step);
- the outcome record (the env's own, compared with the Monte Carlo file's record).

Frame: the pad frame of physics.py (pad centre at the origin; x, y horizontal; z up = altitude above the local
ground plane; metres, seconds, kg). In the three.js world (X east, Y up, Z south) a pad-frame vector (x, y, z) maps to
(x, z, -y) if the pad frame's x is drawn east. The approach azimuth is random per seed.

Rewards are scored with the current env's reward (ENV_VERSION) under the pilot's reward variant: "baseline" for the
laws and the baseline-trained policies, "hover_bonus" for the hover-bonus policy (the reward-hacking demo: eta 0.3
per step pays more for hovering than a landing does).

Plume and surface: the keep-out model (lunarsim/phase3.py PlumeModel) works with a keep-out radius and a stand-down
time per landing and has no dust-onset altitude; the file says so per class and gives the research note's ~15 m
onset for CLPS-class thrusters (Blue Ghost / SCALPSS) for F-33.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np

from . import physics as P
from .classes import CLASSES, G_MOON, SPLICE_URL, TOUCHDOWN

TRAJ_FORMAT = "lunarsim-trajectories"
TRAJ_VERSION = 1
POLICY_DIR = os.path.join("data", "policies")
OUT = os.path.join(POLICY_DIR, "trajectories-v1.json")
POS_DECIMALS = 6           # 1e-6 m: the parity test compares replays to the stored positions at < 1e-6 m
VEL_DECIMALS = 4
DIR_DECIMALS = 5
TERM_DECIMALS = 5
PICKS = (("p10", 10.0), ("p50", 50.0), ("p90", 90.0))
SCALPSS_URL = "https://www.nasa.gov/general/nasa-cameras-on-blue-ghost-capture-first-of-its-kind-moon-landing-footage/"

# (class, pilot id, kind, outcomes name, policy card) in file order
PILOTS = [
    ("CLPS", "classical", "law", "classical_CLPS", None),
    ("CLPS", "memoryless", "law", "memoryless_CLPS", None),
    ("CLPS", "lander_CLPS_bc_v3_s0", "policy", "lander_CLPS_bc_v3_s0", "lander_CLPS_bc_v3_s0.json"),
    ("CLPS", "lander_CLPS_baseline_s0", "policy", "lander_CLPS_baseline_s0", "lander_CLPS_baseline_s0.json"),
    ("CLPS", "lander_CLPS_hover_bonus_v1_s0", "policy", "lander_CLPS_hover_bonus_v1_s0", "lander_CLPS_hover_bonus_v1_s0.json"),
    ("MK1", "classical", "law", "classical_MK1", None),
    ("MK1", "memoryless", "law", "memoryless_MK1", None),
    ("LARGE", "classical", "law", "classical_LARGE", None),
    ("LARGE", "memoryless", "law", "memoryless_LARGE", None),
]
PILOT_LABELS = {"classical": "classical ZEM/ZEV law (filtered)", "memoryless": "memoryless classical law (B-10d)",
                "lander_CLPS_bc_v3_s0": "learned: imitation + DAgger, observation v3",
                "lander_CLPS_baseline_s0": "learned: PPO, baseline reward",
                "lander_CLPS_hover_bonus_v1_s0": "learned: PPO, hover-bonus reward (reward-hacking demo)"}


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def quaternion_from_direction(u) -> List[float]:
    """[w, x, y, z] of the rotation taking +z to the unit vector u (no roll)."""
    ux, uy, uz = (float(v) for v in u)
    w = math.sqrt(max(0.0, (1.0 + uz) / 2.0))
    if w < 1e-12:                                   # u = -z: half turn about x
        return [0.0, 1.0, 0.0, 0.0]
    return [w, -uy / (2.0 * w), ux / (2.0 * w), 0.0]   # vector part (z x u) / (2 cos(theta / 2)), z x u = (-uy, ux, 0)


def rotate(q, v) -> np.ndarray:
    """Rotate v by the unit quaternion q = [w, x, y, z]."""
    w, x, y, z = q
    qv = np.array([x, y, z])
    v = np.asarray(v, float)
    return v + 2.0 * np.cross(qv, np.cross(qv, v) + w * v)


def controller_for(kind: str, pilot: str, card: Optional[str], policy_dir: str = POLICY_DIR):
    """(controller(obs, env) -> action, obs_version, reward variant, provenance)."""
    from . import evaluate as EV
    from .env import obs_version_of
    if kind == "law":
        fn = EV.classical_action if pilot == "classical" else EV.memoryless_action
        return (lambda obs, env: fn(env)), 2, "baseline", {"controller": PILOT_LABELS[pilot]}
    from .policy import MlpPolicy
    path = os.path.join(policy_dir, card)
    pol = MlpPolicy.from_json(path)
    variant = (pol.doc.get("training") or {}).get("reward_variant") or "baseline"
    return ((lambda obs, env: pol.act(obs)), obs_version_of(pol.doc["obs"]["names"]), variant,
            {"controller": PILOT_LABELS.get(pilot, pilot), "policy": pol.id, "policy_sha256": _sha(path)})


def select_episodes(episodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The p10 / p50 / p90 |miss| episodes among those that reached the ground, and the first failure."""
    ground = [e for e in episodes if e["failure_kind"] not in ("timeout", "lost")] or list(episodes)
    miss = np.array([math.hypot(*e["miss_m"]) for e in ground])
    seeds = np.array([e["seed"] for e in ground])
    out = []
    for label, q in PICKS:
        target = float(np.percentile(miss, q))
        order = np.lexsort((seeds, np.abs(miss - target)))
        e = ground[int(order[0])]
        out.append({"pick": label, "seed": int(e["seed"]), "target_miss_m": target})
    fails = sorted((e for e in episodes if not e["ok"]), key=lambda e: e["seed"])
    if fails:
        out.append({"pick": "first_failure", "seed": int(fails[0]["seed"]), "target_miss_m": None})
    return out


def reward_terms(env, s_new: np.ndarray, thrust: float, out: Optional[Dict[str, Any]], td: Optional[np.ndarray],
                 lost: bool) -> Dict[str, float]:
    """The env's reward of one step split into terms (same expressions as DescentEnv.step)."""
    from .env import SENSOR, TOUCHDOWN as TD, target_velocity
    rw, c = env.rw, env.cls
    z = s_new[P.Z]
    tf = thrust / (c.t_max_n * env.thrust_scale)
    vt = target_velocity(s_new[P.X:P.Z + 1], s_new[P.VX:P.VZ + 1])
    near = 1.0 + rw["near_gain"] * max(0.0, 1.0 - z / SENSOR["low_alt_m"])
    track = rw["alpha"] * near * float(np.linalg.norm(s_new[P.VX:P.VZ + 1] - vt))
    effort = rw["beta"] * tf
    low = 0.0
    if z < SENSOR["low_alt_m"]:
        low += rw["delta"] * max(0.0, P.tilt_deg(s_new[P.TX], s_new[P.TY]) - TD["tilt_max_deg"]) / 6.0
        low += rw["zeta"] * math.degrees(math.hypot(s_new[P.WX], s_new[P.WY]))
        low += rw["low_time"] + (rw["low_thrust"] * tf * tf if z < 10.0 else 0.0)
    terminal = 0.0
    if out is not None and td is not None:
        if out["touchdown_ok"]:
            terminal = rw["kappa"] * (0.5 + 0.5 * math.exp(-math.hypot(*out["miss_m"]) / 10.0))
        else:
            vh, vz = math.hypot(td[P.VX], td[P.VY]), abs(td[P.VZ])
            terminal = rw["crash"] * (max(0.0, vz - TD["vz_max_mps"]) + max(0.0, vh - TD["vh_max_mps"]))
    elif lost:
        terminal = rw["lost"]
    return {"track": track, "effort": effort, "low_alt": low, "terminal": terminal}


def record_episode(cls: str, controller: Callable, obs_version: int, variant: str, seed: int) -> Dict[str, Any]:
    """Replay one episode and record it (see the module docstring)."""
    from .env import DescentEnv
    env = DescentEnv(cls=cls, variant=variant, sensor=True, obs_version=obs_version)
    obs, _ = env.reset(seed=seed)
    dt = env.dt
    states = [env.state.copy()]                    # step boundaries
    mids: List[Tuple[np.ndarray, np.ndarray]] = []  # (pos, vel) at mid-step, when the step lasted that long
    steps = {"throttle": [], "dir": [], "quat": [], "prop_kg": [], "alt_meas_m": [], "track": [], "effort": [],
             "low_alt": [], "terminal": []}
    total = 0.0
    info: Dict[str, Any] = {}
    done = False
    end_frac = 1.0
    while not done:
        s0 = env.state.copy()
        a = controller(obs, env)
        full, thrust = P.step(s0, a, env.cls, dt, env.thrust_scale, env.isp_scale, env.m_dry)
        obs, r, term, trunc, info = env.step(a)
        done = term or trunc
        s1 = env.state.copy()
        acc = (full[P.VX:P.VZ + 1] - s0[P.VX:P.VZ + 1]) / dt
        h = dt / 2.0
        td_state = s1 if (term and "outcome" in info and info["outcome"]["landed_tilt_deg"] is not None) else None
        if td_state is not None:                    # touchdown inside the step: the fraction it lasted
            z0, z1 = s0[P.Z], full[P.Z]
            end_frac = 1.0 if z0 == z1 else max(0.0, min(1.0, z0 / (z0 - z1)))
        if td_state is None or end_frac > 0.5:
            mids.append((s0[P.X:P.Z + 1] + s0[P.VX:P.VZ + 1] * h + 0.5 * acc * h * h, s0[P.VX:P.VZ + 1] + acc * h))
        states.append(s1)
        u = P.thrust_direction(full[P.TX], full[P.TY])
        steps["throttle"].append(thrust / (env.cls.t_max_n * env.thrust_scale))
        steps["dir"].append(list(u))
        steps["quat"].append(quaternion_from_direction(u))
        steps["prop_kg"].append(max(0.0, s1[P.M] - env.m_dry))
        steps["alt_meas_m"].append(float(env.last_est[0][2]))
        lost = term and td_state is None                # the env ends an airborne episode early only as "lost"
        terms = reward_terms(env, full, thrust, info.get("outcome") if td_state is not None else None, td_state, lost)
        s_terms = terms["track"] + terms["effort"] + env.rw["eta"] + terms["low_alt"] + terms["terminal"]
        if abs(s_terms - r) > 1e-9:
            raise AssertionError(f"reward split {s_terms} != env reward {r} at step {len(states) - 1} (seed {seed})")
        for k in ("track", "effort", "low_alt", "terminal"):
            steps[k].append(terms[k])
        total += r
    n_steps = len(states) - 1
    t_end = (n_steps - 1 + end_frac) * dt if end_frac < 1.0 else n_steps * dt
    # 10 Hz positions: boundaries and mid-steps interleaved, then the end instant
    pos, vel, t = [], [], []
    for k in range(n_steps):
        pos.append(states[k][P.X:P.Z + 1])
        vel.append(states[k][P.VX:P.VZ + 1])
        t.append(k * dt)
        if k < len(mids):
            pos.append(mids[k][0])
            vel.append(mids[k][1])
            t.append(k * dt + dt / 2.0)
    pos.append(states[-1][P.X:P.Z + 1])
    vel.append(states[-1][P.VX:P.VZ + 1])
    t.append(t_end)
    return {"seed": int(seed), "t_end_s": round(t_end, 6), "n_steps": n_steps,
            "t": t, "pos": pos, "vel": vel, "steps": steps, "eta": env.rw["eta"], "score": total,
            "outcome": info["outcome"], "m0_kg": float(env.m0), "m_dry_kg": float(env.m_dry),
            "thrust_scale": float(env.thrust_scale), "slope_deg": float(env.slope_deg)}


def _r(x, d):
    return [round(float(v), d) for v in x]


def compact(ep: Dict[str, Any]) -> Dict[str, Any]:
    """Columnar, rounded JSON record of one episode (10 Hz positions are t = 0, 0.1, ... plus the end instant)."""
    s = ep["steps"]
    return {
        "seed": ep["seed"], "t_end_s": ep["t_end_s"], "n_steps": ep["n_steps"], "n_samples": len(ep["pos"]),
        "pos_m": [_r(p, POS_DECIMALS) for p in ep["pos"]],
        "vel_mps": [_r(v, VEL_DECIMALS) for v in ep["vel"]],
        "throttle": _r(s["throttle"], 4), "thrust_dir": [_r(u, DIR_DECIMALS) for u in s["dir"]],
        "quat_wxyz": [_r(q, DIR_DECIMALS) for q in s["quat"]], "prop_kg": _r(s["prop_kg"], 2),
        "alt_meas_m": _r(s["alt_meas_m"], 3),
        "reward": {"eta_per_step": ep["eta"], "track": _r(s["track"], TERM_DECIMALS),
                   "effort": _r(s["effort"], TERM_DECIMALS), "low_alt": _r(s["low_alt"], TERM_DECIMALS),
                   "terminal": _r(s["terminal"], TERM_DECIMALS), "score": round(ep["score"], 6)},
        "outcome": ep["outcome"],
        "episode": {"m0_kg": round(ep["m0_kg"], 3), "m_dry_kg": round(ep["m_dry_kg"], 3),
                    "thrust_scale": round(ep["thrust_scale"], 6), "site_slope_deg": round(ep["slope_deg"], 4)},
    }


def ensure_outcomes(name: str, cls: str, law: str, policy_dir: str, log=print) -> str:
    """The Monte Carlo file; for a missing memoryless law it is computed (500 episodes, EVAL_SEED0)."""
    path = os.path.join(policy_dir, f"outcomes_{name}.json")
    if not os.path.isfile(path):
        from .evaluate import evaluate, EVAL_SEED0
        log(f"{name}: no Monte Carlo file; running 500 episodes ({law}, {cls})")
        evaluate(None, cls, 500, EVAL_SEED0, True, policy_dir, name=name, law=law)
    return path


def plume_block(cls: str) -> Dict[str, Any]:
    c = CLASSES[cls]
    out = {"t_max_n": c.t_max_n, "t_min_n": c.t_min_n, "m_gate_kg": c.m_gate_kg,
           "keepout_model": "lunarsim/phase3.py PlumeModel: a keep-out radius R and a stand-down time T around each "
                            "landing (scenario parameters, the same for every class); it has no dust-onset altitude",
           "dust_onset_altitude_m": None}
    if cls == "CLPS":
        out["f33_onset_altitude_m"] = {"value": 15.0, "flag": "Measured",
                                       "source": "Blue Ghost M1 (SCALPSS): reaction-control plumes start acting on the "
                                                 f"surface at ~15 m: {SCALPSS_URL}"}
    else:
        out["f33_onset_altitude_m"] = {"value": None, "flag": "Assumed",
                                       "source": "no published onset for this class; design_research.md §1.4 scales the "
                                                 "onset with thrust (F-33 decides)"}
    return out


def build(policy_dir: str = POLICY_DIR, out: str = OUT, log=print) -> Dict[str, Any]:
    from .env import ENV_ID, ENV_VERSION
    t0 = time.time()
    entries = []
    for cls, pilot, kind, oname, card in PILOTS:
        opath = ensure_outcomes(oname, cls, "classical" if pilot == "classical" else "memoryless", policy_dir, log) \
            if kind == "law" else os.path.join(policy_dir, f"outcomes_{oname}.json")
        with open(opath, encoding="utf-8") as f:
            mc = json.load(f)
        by_seed = {e["seed"]: e for e in mc["episodes"]}
        controller, obs_v, variant, prov = controller_for(kind, pilot, card, policy_dir)
        eps = []
        for pick in select_episodes(mc["episodes"]):
            rec = record_episode(cls, controller, obs_v, variant, pick["seed"])
            ref = by_seed[pick["seed"]]
            got = rec["outcome"]
            same = (got["failure_kind"] == ref["failure_kind"] and got["ok"] == ref["ok"]
                    and abs(math.hypot(*got["miss_m"]) - math.hypot(*ref["miss_m"])) < 1e-6)
            c = compact(rec)
            c.update({"pick": pick["pick"], "target_miss_m": pick["target_miss_m"],
                      "miss_m": round(math.hypot(*got["miss_m"]), 4), "matches_monte_carlo": bool(same)})
            eps.append(c)
            log(f"{cls:5s} {pilot:30s} {pick['pick']:13s} seed {pick['seed']}  |miss| {c['miss_m']:8.2f} m  "
                f"{got['failure_kind'] or 'ok':9s} t {rec['t_end_s']:6.1f} s  score {rec['score']:8.2f}"
                + ("" if same else "  (differs from the Monte Carlo record)"))
        entries.append({"cls": cls, "pilot": pilot, "label": PILOT_LABELS.get(pilot, pilot), "reward_variant": variant,
                        "obs_version": obs_v, "monte_carlo": {"file": os.path.basename(opath), "sha256": _sha(opath),
                                                              "n": mc.get("n", len(mc["episodes"])),
                                                              "seed0": mc.get("seed0"),
                                                              "env_version": mc.get("env_version"),
                                                              "pass_rate": mc["summary"]["pass_rate"]},
                        **prov, "episodes": eps})
    doc = {
        "format": TRAJ_FORMAT, "version": TRAJ_VERSION, "env": ENV_ID, "env_version": ENV_VERSION,
        "description": __doc__.split("\n\n")[1].strip(),
        "frame": "pad frame: pad centre at the origin, x and y horizontal, z up (altitude above the local ground "
                 "plane); metres, seconds, kilograms",
        "sampling": {"guidance_step_s": 0.2, "position_rate_hz": 10,
                     "pos_m / vel_mps": "t = 0, 0.1, 0.2, ... then t_end_s (the touchdown instant or the end of the "
                                        "episode); exact within each guidance step (constant acceleration)",
                     "per step k": "throttle, thrust_dir, quat_wxyz, prop_kg (end of the step), alt_meas_m (the "
                                   "altimeter reading the pilot saw after the step), reward terms: all for the interval "
                                   "[0.2 (k - 1), 0.2 k]"},
        "fields": {"throttle": "thrust / maximum thrust (0-1)",
                   "quat_wxyz": "rotation taking body +z to the thrust direction (no roll)",
                   "reward": "per-step terms; step reward = track + effort + eta_per_step + low_alt + terminal; "
                             "score = their sum over the episode (the current env's reward under the pilot's variant)",
                   "outcome": "the env's touchdown record (lunarsim/lander/env.py)",
                   "matches_monte_carlo": "the replay's outcome equals the Monte Carlo file's record for that seed"},
        "selection": "p10 / p50 / p90: the episode whose |miss| is nearest that percentile of |miss| over the Monte "
                     "Carlo episodes that reached the ground (all episodes if none did; ties to the lower seed); "
                     "first_failure: the lowest seed with ok = false",
        "touchdown_box": {k: v for k, v in TOUCHDOWN.items() if k != "source"}, "touchdown_source": SPLICE_URL,
        "plume": {cls: plume_block(cls) for cls in CLASSES},
        "pilots": entries,
        "generated": {"tool": "lunarsim/lander/trajectories.py", "seconds": round(time.time() - t0, 1)},
    }
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    log(f"wrote {out}: {os.path.getsize(out) / 2**20:.2f} MB, {sum(len(e['episodes']) for e in entries)} episodes "
        f"in {time.time() - t0:.0f} s")
    return doc


def validate(doc: Dict[str, Any]) -> List[str]:
    """Structural check ([] = valid): header, per episode consistent array lengths, unit vectors, terms vs score."""
    errs: List[str] = []
    if doc.get("format") != TRAJ_FORMAT or doc.get("version") != TRAJ_VERSION:
        return [f"format/version must be {TRAJ_FORMAT} v{TRAJ_VERSION}"]
    for p in doc.get("pilots", []):
        if p.get("cls") not in CLASSES:
            errs.append(f"unknown class {p.get('cls')!r}")
        for e in p.get("episodes", []):
            w = f"{p.get('cls')}/{p.get('pilot')}/{e.get('pick')}"
            n, k = e["n_samples"], e["n_steps"]
            if len(e["pos_m"]) != n or len(e["vel_mps"]) != n:
                errs.append(f"{w}: pos/vel length != n_samples")
            if not (k + 1 <= n <= 2 * k + 1):
                errs.append(f"{w}: n_samples {n} inconsistent with {k} steps")
            for key in ("throttle", "thrust_dir", "quat_wxyz", "prop_kg", "alt_meas_m"):
                if len(e[key]) != k:
                    errs.append(f"{w}: {key} length != n_steps")
            for key in ("track", "effort", "low_alt", "terminal"):
                if len(e["reward"][key]) != k:
                    errs.append(f"{w}: reward.{key} length != n_steps")
            u = np.asarray(e["thrust_dir"], float)
            if len(u) and np.max(np.abs(np.linalg.norm(u, axis=1) - 1.0)) > 1e-4:
                errs.append(f"{w}: thrust_dir not unit vectors")
            q = np.asarray(e["quat_wxyz"], float)
            if len(q) and np.max(np.abs(np.linalg.norm(q, axis=1) - 1.0)) > 1e-4:
                errs.append(f"{w}: quaternions not unit")
            th = np.asarray(e["throttle"], float)
            if len(th) and (th.min() < -1e-9 or th.max() > 1.0 + 1e-6):
                errs.append(f"{w}: throttle outside 0-1")
            rr = e["reward"]
            s = sum(sum(rr[key]) for key in ("track", "effort", "low_alt", "terminal")) + rr["eta_per_step"] * k
            if abs(s - rr["score"]) > 1e-3 * max(1.0, k):
                errs.append(f"{w}: reward terms do not sum to the score")
            if e["pos_m"][-1][2] < -1e-6:
                errs.append(f"{w}: ends below the ground")
    return errs


def check(path: str = OUT, policy_dir: str = POLICY_DIR, max_episodes: Optional[int] = None, log=print) -> float:
    """Replay exported episodes in the Python env; returns the largest position difference (m)."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    worst = 0.0
    n = 0
    for p in doc["pilots"]:
        kind = "law" if p["pilot"] in ("classical", "memoryless") else "policy"
        card = None if kind == "law" else f"{p['pilot']}.json"
        controller, obs_v, variant, _ = controller_for(kind, p["pilot"], card, policy_dir)
        for e in p["episodes"]:
            rec = record_episode(p["cls"], controller, obs_v, variant, e["seed"])
            d = float(np.max(np.abs(np.asarray(rec["pos"]) - np.asarray(e["pos_m"]))))
            worst = max(worst, d)
            n += 1
            if max_episodes and n >= max_episodes:
                return worst
    log(f"replayed {n} episodes: max |position difference| {worst:.2e} m")
    return worst


def main(argv=None):
    ap = argparse.ArgumentParser(description="Export descent trajectories for the 3D landing lab")
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--policy-dir", default=POLICY_DIR)
    ap.add_argument("--check", action="store_true", help="replay the exported file and report the parity")
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    if a.check:
        with open(a.out, encoding="utf-8") as f:
            errs = validate(json.load(f))
        print("validate:", "OK" if not errs else errs[:5])
        check(a.out, a.policy_dir)
    else:
        build(a.policy_dir, a.out)


if __name__ == "__main__":
    main()
