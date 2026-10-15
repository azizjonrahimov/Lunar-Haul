"""PPO training for lunar/Descent-v0 (and the LunarLander-v3 toolchain warm-up). Needs the [ml] extra.

    python -m lunarsim.lander.train --cls CLPS --variant baseline --steps 300000 --seed 0
    python -m lunarsim.lander.train --env LunarLander-v3 --steps 1000000          # tutorial warm-up

Descent runs write data/policies/lander_<cls>_<variant>_s<seed>.json (+ .check.json) with the training record,
and keep the SB3 zip, a learning curve (curve.csv: steps, mean return, touchdown-box rate, pass rate over
deterministic evaluation episodes) and TensorBoard logs in runs/lander/<id>/. The warm-up writes only to
runs/lunarlander/<id>/ and prints the 20-episode deterministic mean the tutorial claim refers to.

Hyperparameters start from RL-Zoo's LunarLander PPO settings (n_steps 1024, gamma 0.999, gae_lambda 0.98,
n_epochs 4, ent_coef 0.01, batch 64, 16 envs) and are adapted for the descent env (8 envs, batch 256,
10 epochs, gamma 0.999 as RL-Zoo, no entropy bonus, initial log-std -0.5); see HYPER_DESCENT below.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import platform
import subprocess
import time
from typing import Any, Dict, Optional

import numpy as np

CURRICULUM = 0.3   # share of training resets starting in the terminal phase (evaluation always starts at the gate)
HYPER_DESCENT: Dict[str, Any] = {"n_envs": 8, "n_steps": 1024, "batch_size": 256, "n_epochs": 10, "gamma": 0.999,
                                 "gae_lambda": 0.98, "learning_rate": 3e-4, "clip_range": 0.2, "ent_coef": 0.0,
                                 "vf_coef": 0.5, "max_grad_norm": 0.5,
                                 "policy_kwargs": {"net_arch": [64, 64], "log_std_init": -0.5},
                                 "normalize_reward": True}
# named hyperparameter sets (--hyper-set); learning_rate "linear:<x>" decays linearly from x to 0
HYPER_SETS: Dict[str, Dict[str, Any]] = {
    "default": HYPER_DESCENT,
    "b10b": {"n_envs": 8, "n_steps": 2048, "batch_size": 256, "n_epochs": 10, "gamma": 0.995, "gae_lambda": 0.98,
             "learning_rate": "linear:1e-4", "clip_range": 0.2, "ent_coef": 0.0, "vf_coef": 0.5, "max_grad_norm": 0.5,
             "policy_kwargs": {"net_arch": [128, 128], "log_std_init": -0.5}, "normalize_reward": True},
    # fine-tuning a behaviour-cloned policy: small, decaying steps; no reward normalisation so the BC-fitted
    # critic (raw discounted returns, gamma 0.995) stays valid
    "finetune": {"n_envs": 8, "n_steps": 2048, "batch_size": 256, "n_epochs": 10, "gamma": 0.995, "gae_lambda": 0.98,
                 "learning_rate": "linear:1e-4", "clip_range": 0.1, "ent_coef": 0.0, "vf_coef": 0.5, "max_grad_norm": 0.5,
                 "policy_kwargs": {"net_arch": [128, 128], "log_std_init": -1.5}, "normalize_reward": False},
}
HYPER_LUNARLANDER: Dict[str, Any] = {"n_envs": 16, "n_steps": 1024, "batch_size": 64, "n_epochs": 4, "gamma": 0.999,
                                     "gae_lambda": 0.98, "ent_coef": 0.01}   # RL-Zoo ppo.yml, LunarLander-v3


def git_sha() -> Optional[str]:
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=here, capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "lunarsim"], cwd=here, capture_output=True,
                               text=True, timeout=10).stdout.strip()
        return (sha + ("-dirty" if dirty else "")) or None
    except (OSError, subprocess.SubprocessError):
        return None


def _make_eval_fn(cls: str, variant: str, n: int, seed0: int):
    """Deterministic evaluation on fixed seeds (not the training seeds)."""
    from .env import DescentEnv
    env = DescentEnv(cls=cls, variant=variant)

    def run(model) -> Dict[str, float]:
        rets, box, ok = [], 0, 0
        for i in range(n):
            obs, _ = env.reset(seed=seed0 + i)
            done, total, info = False, 0.0, {}
            while not done:
                act, _ = model.predict(obs, deterministic=True)
                obs, r, term, trunc, info = env.step(act)
                total += r
                done = term or trunc
            rets.append(total)
            box += info["outcome"]["touchdown_ok"]
            ok += info["outcome"]["ok"]
        return {"mean_return": float(np.mean(rets)), "box_rate": box / n, "pass_rate": ok / n}
    return run


def train_descent(cls: str, variant: str, steps: int, seed: int, out_dir: str, run_root: str,
                  eval_every: int = 50_000, eval_n: int = 100, n_envs: Optional[int] = None,
                  subproc: bool = True, verbose: int = 0, hyper: Optional[Dict[str, Any]] = None,
                  curriculum: float = CURRICULUM, hyper_set: str = "default",
                  init_from_bc: Optional[str] = None) -> Dict[str, Any]:
    import stable_baselines3 as sb3
    import torch
    from stable_baselines3 import PPO
    from stable_baselines3.common.callbacks import BaseCallback
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv, VecNormalize
    from . import export
    from .classes import CLASSES
    from .env import ACT_NAMES, ENV_ID, ENV_VERSION, OBS_NAMES, OBS_OFFSET, DescentEnv, obs_scale

    if hyper is None:
        if hyper_set not in HYPER_SETS:
            raise ValueError(f"unknown hyper set {hyper_set!r}; known: {', '.join(HYPER_SETS)}")
        hyper = HYPER_SETS[hyper_set]
    hp = json.loads(json.dumps(hyper))       # deep copy; stays JSON for the training record
    if n_envs:
        hp["n_envs"] = n_envs
    pid = f"lander_{cls}_{variant}_s{seed}"
    run_dir = os.path.join(run_root, pid)
    os.makedirs(run_dir, exist_ok=True)
    torch.set_num_threads(1)
    vec = make_vec_env(DescentEnv, n_envs=hp["n_envs"], seed=seed,
                       env_kwargs={"cls": cls, "variant": variant, "curriculum": curriculum},
                       vec_env_cls=SubprocVecEnv if subproc and hp["n_envs"] > 1 else DummyVecEnv)
    if hp.get("normalize_reward"):          # rewards only: the exported policy sees the env's own observations
        vec = VecNormalize(vec, norm_obs=False, norm_reward=True, gamma=hp["gamma"])
    kw = {k: v for k, v in hp.items() if k not in ("n_envs", "normalize_reward")}
    lr = kw.get("learning_rate")
    if isinstance(lr, str) and lr.startswith("linear:"):
        lr0 = float(lr.split(":", 1)[1])
        # SB3's progress_remaining = 1 - steps / total goes NEGATIVE in the last rollout when n_envs * n_steps does not
        # divide the budget (e.g. 311,296 of 300,000): an unclamped linear schedule then makes the final update a
        # gradient *ascent* step (B-10c: a 50 % checkpoint evaluated at 3 % after it). Clamp at 0.
        kw["learning_rate"] = lambda progress_remaining: lr0 * max(progress_remaining, 0.0)
    try:
        import tensorboard  # noqa: F401
        tb = os.path.join(run_dir, "tb")
    except ImportError:
        tb = None
    model = PPO("MlpPolicy", vec, seed=seed, verbose=verbose, device="cpu", tensorboard_log=tb, **kw)
    init_rec = None
    if init_from_bc:                       # copy the behaviour-cloned actor/critic (same architecture required)
        bc = PPO.load(init_from_bc, device="cpu")
        model.policy.load_state_dict(bc.policy.state_dict())
        side = os.path.splitext(init_from_bc)[0] + ".json"
        init_rec = {"kind": "bc", "path": init_from_bc}
        if os.path.exists(side):
            with open(side, encoding="utf-8") as f:
                init_rec["bc"] = json.load(f)
    evaluate = _make_eval_fn(cls, variant, eval_n, seed0=10_000_000)
    curve = []
    t_start = time.time()

    class Curve(BaseCallback):
        def __init__(self):
            super().__init__()
            self.next = eval_every

        def _on_step(self) -> bool:
            if self.num_timesteps >= self.next:
                self.next += eval_every
                r = evaluate(self.model)
                r.update(steps=int(self.num_timesteps), wallclock_s=round(time.time() - t_start, 1))
                curve.append(r)
                if verbose >= 0:
                    print(f"  {r['steps']:>9d} steps  return {r['mean_return']:8.2f}  box {100 * r['box_rate']:5.1f} %  "
                          f"pass {100 * r['pass_rate']:5.1f} %  ({r['wallclock_s']:.0f} s)", flush=True)
            return True

    model.learn(total_timesteps=steps, callback=Curve(), progress_bar=False)
    wall = time.time() - t_start
    final = evaluate(model)
    final.update(steps=int(model.num_timesteps), wallclock_s=round(wall, 1))
    if not curve or curve[-1]["steps"] != final["steps"]:
        curve.append(final)
    vec.close()
    model.save(os.path.join(run_dir, "model.zip"))
    with open(os.path.join(run_dir, "curve.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["steps", "wallclock_s", "mean_return", "box_rate", "pass_rate"])
        w.writeheader()
        w.writerows(curve)
    training = {"algo": "PPO", "sb3_version": sb3.__version__, "torch_version": torch.__version__,
                "hyper_set": hyper_set if hyper is None or hyper is HYPER_SETS.get(hyper_set) else "custom",
                "init": init_rec or {"kind": "random"},
                "steps": int(model.num_timesteps), "seed": seed, "hyperparams": hp, "reward_variant": variant,
                "cls": cls, "curriculum": curriculum, "wallclock_s": round(wall, 1), "s_per_100k_steps": round(wall / model.num_timesteps * 1e5, 1),
                "git_sha": git_sha(), "python": platform.python_version(), "platform": platform.platform(),
                "end_of_training_eval": {**final, "episodes": eval_n, "seed0": 10_000_000,
                                         "how": "SB3 model.predict on the training seed set (curve's last point)"},
                "curve": curve}
    card = {"title": f"PPO terminal-descent policy, {cls}, reward variant '{variant}'",
            "intended_use": "stochastic generator of landing outcomes for the LunarSim DES; not flight software",
            "env": f"{ENV_ID} v{ENV_VERSION}: 3-DoF point mass, rate-limited thrust axis, SPLICE gate dispersion, "
                   "domain randomisation, altimeter degradation below 30 m",
            "limitations": "3-DoF (no rotational dynamics beyond a slew-rate limit); flat ground plane with a sampled "
                           "local slope; sensor model Assumed; lander constants partly Assumed (see classes.py flags)"}
    out_json = os.path.join(out_dir, f"{pid}.json")
    doc = export.write(model, out_json, env_id=ENV_ID, env_version=ENV_VERSION, obs_names=OBS_NAMES,
                       obs_scale=obs_scale(CLASSES[cls]).tolist(), obs_offset=OBS_OFFSET.tolist(),
                       act_names=ACT_NAMES, training=training, card=card)
    # the card's final_eval is the quantity evaluate.py reports: the exported numpy policy, evaluate()'s default
    # seeds, the same env construction (sensor on, dispersion on)
    from .evaluate import evaluate as mc_evaluate, EVAL_SEED0
    summ = mc_evaluate(out_json, cls, eval_n, seed0=EVAL_SEED0)
    doc["training"]["final_eval"] = {"episodes": eval_n, "seed0": EVAL_SEED0, "pass_rate": summ["pass_rate"],
                                     "box_rate": summ["touchdown_box_rate"], "failure_counts": summ["failure_counts"],
                                     "how": "lunarsim.lander.evaluate on the exported JSON policy"}
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    return {"policy": out_json, "run_dir": run_dir, "final": final, "final_eval": doc["training"]["final_eval"],
            "wallclock_s": wall, "doc": doc}


def train_lunarlander(steps: int, seed: int, run_root: str, n_eval: int = 20, verbose: int = 0,
                      subproc: bool = True) -> Dict[str, Any]:
    import gymnasium as gym
    from stable_baselines3 import PPO
    from stable_baselines3.common.env_util import make_vec_env
    from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
    from stable_baselines3.common.evaluation import evaluate_policy
    import torch
    torch.set_num_threads(1)
    hp = dict(HYPER_LUNARLANDER)
    run_dir = os.path.join(run_root, f"lunarlander_s{seed}")
    os.makedirs(run_dir, exist_ok=True)
    vec = make_vec_env("LunarLander-v3", n_envs=hp.pop("n_envs"), seed=seed,
                       vec_env_cls=SubprocVecEnv if subproc else DummyVecEnv)
    model = PPO("MlpPolicy", vec, seed=seed, verbose=verbose, device="cpu", **hp)
    t0 = time.time()
    model.learn(total_timesteps=steps)
    wall = time.time() - t0
    vec.close()
    eval_env = gym.make("LunarLander-v3")
    eval_env.reset(seed=seed + 12345)
    mean, std = evaluate_policy(model, eval_env, n_eval_episodes=n_eval, deterministic=True)
    model.save(os.path.join(run_dir, "model.zip"))
    res = {"env": "LunarLander-v3", "steps": steps, "seed": seed, "mean_reward": float(mean), "std_reward": float(std),
           "n_eval": n_eval, "wallclock_s": round(wall, 1), "solved": bool(mean >= 200), "hyperparams": HYPER_LUNARLANDER,
           "subproc": subproc}
    with open(os.path.join(run_dir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    return res


def main(argv=None):
    from .classes import CLASSES
    from .env import REWARD_VARIANTS
    p = argparse.ArgumentParser(description="PPO training for lunar/Descent-v0 or the LunarLander-v3 warm-up")
    p.add_argument("--env", default="lunar/Descent-v0", choices=["lunar/Descent-v0", "LunarLander-v3"])
    p.add_argument("--cls", default="CLPS", choices=sorted(CLASSES))
    p.add_argument("--variant", default="baseline", choices=sorted(REWARD_VARIANTS))
    p.add_argument("--steps", type=int, default=300_000)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--n-envs", type=int, default=None)
    p.add_argument("--eval-every", type=int, default=50_000)
    p.add_argument("--eval-n", type=int, default=100)
    p.add_argument("--curriculum", type=float, default=CURRICULUM)
    p.add_argument("--hyper-set", default="default", choices=sorted(HYPER_SETS))
    p.add_argument("--init-from-bc", default=None, help="SB3 zip from lunarsim.lander.bc_warmstart")
    p.add_argument("--no-subproc", action="store_true",
                   help="run all envs in this process (DummyVecEnv): slower, but no worker processes / far less memory")
    p.add_argument("--out-dir", default=os.path.join("data", "policies"))
    p.add_argument("--run-root", default="runs")
    p.add_argument("--verbose", type=int, default=0)
    a = p.parse_args(argv)
    if a.env == "LunarLander-v3":
        r = train_lunarlander(a.steps, a.seed, os.path.join(a.run_root, "lunarlander"), verbose=a.verbose,
                              subproc=not a.no_subproc)
        print(f"LunarLander-v3: {a.steps} steps in {r['wallclock_s']:.0f} s; deterministic mean over {r['n_eval']} "
              f"episodes {r['mean_reward']:.1f} +- {r['std_reward']:.1f} ({'solved' if r['solved'] else 'NOT solved'})")
        return
    print(f"training {a.cls} / {a.variant} / seed {a.seed} for {a.steps} steps", flush=True)
    r = train_descent(a.cls, a.variant, a.steps, a.seed, a.out_dir, os.path.join(a.run_root, "lander"),
                      eval_every=a.eval_every, eval_n=a.eval_n, n_envs=a.n_envs, verbose=a.verbose,
                      curriculum=a.curriculum, subproc=not a.no_subproc, hyper_set=a.hyper_set,
                      init_from_bc=a.init_from_bc)
    f, fe = r["final"], r["final_eval"]
    print(f"done in {r['wallclock_s']:.0f} s ({r['doc']['training']['s_per_100k_steps']} s / 100k steps): end-of-training "
          f"return {f['mean_return']:.2f}, box {100 * f['box_rate']:.1f} %; card final_eval (evaluate.py, "
          f"{fe['episodes']} episodes): box {100 * fe['box_rate']:.1f} %, pass {100 * fe['pass_rate']:.1f} %")
    print(f"wrote {r['policy']} and {r['run_dir']}")


if __name__ == "__main__":
    main()
