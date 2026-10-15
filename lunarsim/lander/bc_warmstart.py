"""Behaviour-cloning warm start for the descent PPO policy from the classical ZEM/ZEV law (B-10b).

    python -m lunarsim.lander.bc_warmstart --cls CLPS --episodes 2000 --out runs/bc/bc_CLPS.zip
    python -m lunarsim.lander.train --cls CLPS --init-from-bc runs/bc/bc_CLPS.zip --hyper-set finetune --steps 300000

1. Roll out the classical controller (evaluate.classical_action, the same law the paper compares against) in
   DescentEnv with dispersion, domain randomisation and the sensor model on; record the env's observations, the
   controller's actions in the env's own action space (throttle + tilt-rate commands) and the rewards.
2. Build an SB3 PPO model with the target architecture and fit (a) the actor's action mean to the classical actions
   (MSE, clipped to [-1, 1]) and (b) the value head to the discounted Monte Carlo returns of those episodes, so the
   first PPO updates do not start from an untrained critic. The log-std is set low (init_log_std) for fine-tuning.
3. Save the model zip; train.py --init-from-bc loads it and continues with PPO.

The classical law keeps a little filter state (velocity smoothing, command low-pass) that the MLP cannot see; the
clone therefore approximates it from the current observation only. The BC-only pass rate is reported so the
fine-tuning gain is visible.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, Optional, Tuple

import numpy as np


def collect(cls: str, episodes: int, seed0: int = 2_000_000, variant: str = "baseline",
            gamma: float = 0.995) -> Dict[str, np.ndarray]:
    """(obs, act, ret, ok) arrays from classical-controller episodes. ret = discounted return-to-go per step."""
    from .env import DescentEnv
    from .evaluate import classical_action
    env = DescentEnv(cls=cls, variant=variant)
    O, A, R = [], [], []
    ok = 0
    for i in range(episodes):
        obs, _ = env.reset(seed=seed0 + i)
        done, rews = False, []
        info = {}
        while not done:
            a = classical_action(env)
            O.append(obs)
            A.append(np.clip(a, -1, 1))
            obs, r, te, tr, info = env.step(a)
            rews.append(r)
            done = te or tr
        g, rets = 0.0, []
        for r in reversed(rews):
            g = r + gamma * g
            rets.append(g)
        R.extend(reversed(rets))
        ok += info["outcome"]["touchdown_ok"]
    return {"obs": np.asarray(O, np.float32), "act": np.asarray(A, np.float32), "ret": np.asarray(R, np.float32),
            "box_rate": ok / max(episodes, 1)}


def dagger_round(model, cls: str, episodes: int, seed0: int, variant: str = "baseline", gamma: float = 0.995,
                 beta: float = 0.0) -> Dict[str, np.ndarray]:
    """One DAgger round: roll out the current policy (with probability beta the expert acts instead), label every
    visited state with the classical law's action (its filters follow the same estimates) and return the data."""
    from .env import DescentEnv
    from .evaluate import classical_action
    env = DescentEnv(cls=cls, variant=variant)
    rng = np.random.default_rng(seed0)
    O, A, R = [], [], []
    ok = 0
    for i in range(episodes):
        obs, _ = env.reset(seed=seed0 + i)
        done, rews, info = False, [], {}
        while not done:
            expert = np.clip(classical_action(env), -1, 1)
            O.append(obs)
            A.append(expert)
            act = expert if rng.random() < beta else model.predict(obs, deterministic=True)[0]
            obs, r, te, tr, info = env.step(act)
            rews.append(r)
            done = te or tr
        g, rets = 0.0, []
        for r in reversed(rews):
            g = r + gamma * g
            rets.append(g)
        R.extend(reversed(rets))
        ok += info["outcome"]["touchdown_ok"]
    return {"obs": np.asarray(O, np.float32), "act": np.asarray(A, np.float32), "ret": np.asarray(R, np.float32),
            "box_rate": ok / max(episodes, 1)}


def _merge(a: Dict[str, np.ndarray], b: Dict[str, np.ndarray]) -> Dict[str, np.ndarray]:
    return {k: np.concatenate([a[k], b[k]]) for k in ("obs", "act", "ret")}


def fit(model, data: Dict[str, np.ndarray], epochs: int = 30, batch: int = 1024, lr: float = 1e-3,
        seed: int = 0, init_log_std: float = -1.5, verbose: bool = True) -> Dict[str, float]:
    """Supervised fit of the SB3 actor mean and critic. Returns final losses."""
    import torch
    torch.manual_seed(seed)
    pol = model.policy
    dev = pol.device
    obs = torch.as_tensor(data["obs"], device=dev)
    act = torch.as_tensor(data["act"], device=dev)
    ret = torch.as_tensor(data["ret"], device=dev).unsqueeze(1)
    actor = list(pol.mlp_extractor.policy_net.parameters()) + list(pol.action_net.parameters())
    critic = list(pol.mlp_extractor.value_net.parameters()) + list(pol.value_net.parameters())
    opt_a = torch.optim.Adam(actor, lr=lr)
    opt_c = torch.optim.Adam(critic, lr=lr)
    n = len(obs)
    g = torch.Generator().manual_seed(seed)
    la = lc = float("nan")
    for ep in range(epochs):
        perm = torch.randperm(n, generator=g)
        tot_a = tot_c = 0.0
        for k in range(0, n, batch):
            idx = perm[k:k + batch]
            feats = pol.extract_features(obs[idx])
            lat_pi, lat_vf = pol.mlp_extractor(feats)
            loss_a = torch.nn.functional.mse_loss(pol.action_net(lat_pi), act[idx])
            loss_c = torch.nn.functional.mse_loss(pol.value_net(lat_vf), ret[idx])
            opt_a.zero_grad()
            loss_a.backward(retain_graph=True)
            opt_a.step()
            opt_c.zero_grad()
            loss_c.backward()
            opt_c.step()
            tot_a += loss_a.item() * len(idx)
            tot_c += loss_c.item() * len(idx)
        la, lc = tot_a / n, tot_c / n
        if verbose and (ep % 5 == 0 or ep == epochs - 1):
            print(f"  epoch {ep:3d}  actor MSE {la:.5f}  critic MSE {lc:.3f}", flush=True)
    with torch.no_grad():
        pol.log_std.fill_(init_log_std)
    return {"actor_mse": la, "critic_mse": lc}


def deterministic_box_rate(model, cls: str, n: int, seed0: int = 10_000_000) -> Tuple[float, Dict[str, int]]:
    from .env import DescentEnv
    env = DescentEnv(cls=cls)
    ok, kinds = 0, {}
    for i in range(n):
        obs, _ = env.reset(seed=seed0 + i)
        done, info = False, {}
        while not done:
            a, _ = model.predict(obs, deterministic=True)
            obs, _, te, tr, info = env.step(a)
            done = te or tr
        ok += info["outcome"]["touchdown_ok"]
        k = info["outcome"]["failure_kind"] or "none"
        kinds[k] = kinds.get(k, 0) + 1
    return ok / n, kinds


def build_bc(cls: str, episodes: int, out: str, net=(128, 128), epochs: int = 30, seed: int = 0,
             eval_n: int = 100, init_log_std: float = -1.5, verbose: bool = True, dagger: int = 0,
             dagger_episodes: int = 500, dagger_epochs: int = 15) -> Dict[str, Any]:
    import torch
    from stable_baselines3 import PPO
    from .env import DescentEnv
    torch.set_num_threads(1)
    t0 = time.time()
    data = collect(cls, episodes)
    t_collect = time.time() - t0
    if verbose:
        print(f"collected {len(data['obs'])} steps from {episodes} classical episodes in {t_collect:.0f} s "
              f"(classical box rate {100 * data['box_rate']:.1f} %)", flush=True)
    model = PPO("MlpPolicy", DescentEnv(cls=cls), seed=seed, device="cpu",
                policy_kwargs={"net_arch": list(net), "log_std_init": init_log_std})
    losses = fit(model, data, epochs=epochs, seed=seed, init_log_std=init_log_std, verbose=verbose)
    rounds = []
    if eval_n:
        box0, kinds0 = deterministic_box_rate(model, cls, eval_n)
        rounds.append({"round": 0, "samples": int(len(data["obs"])), "box_rate": box0, "failures": kinds0})
        if verbose:
            print(f"  round 0 (BC): box {100 * box0:.1f} % {kinds0}", flush=True)
    for k in range(1, dagger + 1):
        new = dagger_round(model, cls, dagger_episodes, seed0=3_000_000 + 100_000 * k)
        data = _merge(data, new)
        losses = fit(model, data, epochs=dagger_epochs, seed=seed + k, init_log_std=init_log_std, verbose=False)
        box_k, kinds_k = deterministic_box_rate(model, cls, eval_n) if eval_n else (None, {})
        rounds.append({"round": k, "samples": int(len(data["obs"])), "rollout_box_rate": new["box_rate"],
                       "box_rate": box_k, "failures": kinds_k, **losses})
        if verbose:
            print(f"  round {k} (DAgger): {len(data['obs'])} samples, box {100 * (box_k or 0):.1f} % {kinds_k}", flush=True)
    box, kinds = (rounds[-1]["box_rate"], rounds[-1]["failures"]) if rounds else (None, {})
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    model.save(out)
    rec = {"cls": cls, "episodes": episodes, "steps": int(len(data["obs"])), "net": list(net), "epochs": epochs,
           "seed": seed, "init_log_std": init_log_std, "classical_box_rate": data["box_rate"], **losses,
           "bc_box_rate": box, "bc_failures": kinds, "dagger_rounds": rounds, "wallclock_s": round(time.time() - t0, 1),
           "path": out}
    with open(os.path.splitext(out)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=2)
    return rec


def main(argv=None):
    from .classes import CLASSES
    p = argparse.ArgumentParser(description="behaviour-cloning warm start from the classical descent law")
    p.add_argument("--cls", default="CLPS", choices=sorted(CLASSES))
    p.add_argument("--episodes", type=int, default=2000)
    p.add_argument("--epochs", type=int, default=30)
    p.add_argument("--net", default="128,128")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--eval-n", type=int, default=100)
    p.add_argument("--dagger", type=int, default=0, help="DAgger rounds after behaviour cloning")
    p.add_argument("--dagger-episodes", type=int, default=500)
    p.add_argument("--out", default=os.path.join("runs", "bc", "bc_CLPS.zip"))
    a = p.parse_args(argv)
    r = build_bc(a.cls, a.episodes, a.out, net=tuple(int(x) for x in a.net.split(",")), epochs=a.epochs,
                 seed=a.seed, eval_n=a.eval_n, dagger=a.dagger, dagger_episodes=a.dagger_episodes)
    print(f"BC policy: deterministic box rate {r['bc_box_rate']} ({r['bc_failures']}); wrote {a.out}")


if __name__ == "__main__":
    main()
