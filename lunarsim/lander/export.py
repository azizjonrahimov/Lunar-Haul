"""Export a Stable-Baselines3 PPO MlpPolicy to lunarsim-policy v1 JSON (PLAN §5.2).

    python -m lunarsim.lander.export model.zip --out data/policies/lander_CLPS_baseline_s0.json

Writes <id>.json (weights + obs/act spec + training record + card) and <id>.check.json: 100 random
observations with the float64 numpy runtime's actions (the reference both runtimes must reproduce to 1e-6),
plus SB3's own float32 actions; the export fails if SB3 and the numpy runtime differ by more than 1e-4
(float32 round-off grows with the network width).
"""
from __future__ import annotations

import argparse
import json
import os
from typing import Any, Dict, List, Optional

import numpy as np

from .policy import POLICY_FORMAT, POLICY_VERSION, MlpPolicy


def _linear_layers(seq) -> List[Any]:
    import torch.nn as nn
    return [m for m in seq if isinstance(m, nn.Linear)]


def _act_name(seq) -> str:
    import torch.nn as nn
    for m in seq:
        if isinstance(m, nn.Tanh):
            return "tanh"
        if isinstance(m, nn.ReLU):
            return "relu"
    return "linear"


def policy_doc(model, policy_id: str, env_id: str, env_version: Any, obs_names: List[str],
               obs_scale: Optional[List[float]] = None, obs_offset: Optional[List[float]] = None,
               act_names: Optional[List[str]] = None, training: Optional[Dict[str, Any]] = None,
               card: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """lunarsim-policy v1 document from an SB3 PPO model with an MlpPolicy actor."""
    from gymnasium import spaces
    pol = model.policy
    if not getattr(pol, "share_features_extractor", True) and type(pol.pi_features_extractor).__name__ != "FlattenExtractor":
        raise ValueError("only the default Flatten features extractor is supported")
    hidden = _linear_layers(pol.mlp_extractor.policy_net)
    act = _act_name(pol.mlp_extractor.policy_net)
    layers = [{"w": L.weight.detach().cpu().double().numpy().tolist(),
               "b": L.bias.detach().cpu().double().numpy().tolist(), "act": act} for L in hidden]
    head = pol.action_net
    layers.append({"w": head.weight.detach().cpu().double().numpy().tolist(),
                   "b": head.bias.detach().cpu().double().numpy().tolist(), "act": "linear"})
    space = model.action_space
    n_obs = int(np.prod(model.observation_space.shape))
    if isinstance(space, spaces.Box):
        act_spec = {"kind": "box", "names": act_names or [f"a{i}" for i in range(space.shape[0])],
                    "low": space.low.astype(float).tolist(), "high": space.high.astype(float).tolist()}
        det = "mean_clipped"
    elif isinstance(space, spaces.Discrete):
        act_spec = {"kind": "discrete", "names": act_names or [f"a{i}" for i in range(int(space.n))], "n": int(space.n)}
        det = "argmax"
    else:
        raise ValueError(f"unsupported action space {space}")
    return {
        "format": POLICY_FORMAT, "version": POLICY_VERSION, "kind": "mlp", "id": policy_id,
        "env": env_id, "env_version": env_version,
        "obs": {"names": obs_names, "scale": list(obs_scale) if obs_scale is not None else [1.0] * n_obs,
                "offset": list(obs_offset) if obs_offset is not None else [0.0] * n_obs,
                "note": "obs = clip((raw - offset) / scale, -10, 10) as the env computes it; the policy sees obs"},
        "act": act_spec, "layers": layers, "deterministic": det,
        "training": training or {}, "card": card or {},
    }


SB3_TOLERANCE = 1e-4


def check_doc(model, policy_id: str, obs_dim: int, n: int = 100, seed: int = 0, runtime=None) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    obs = rng.uniform(-2.0, 2.0, size=(n, obs_dim)).astype(np.float32)
    sb3_act, _ = model.predict(obs, deterministic=True)
    act = runtime.act(obs.astype(np.float64)) if runtime is not None else sb3_act
    return {"format": "lunarsim-policy-check", "version": 1, "policy": policy_id,
            "tolerance": 1e-6, "obs": obs.astype(float).tolist(), "act": np.asarray(act).astype(float).tolist(),
            "sb3_act": np.asarray(sb3_act).astype(float).tolist(), "sb3_tolerance": SB3_TOLERANCE,
            "note": "act = float64 numpy runtime (lunarsim.lander.policy) on obs; runtimes must match it to 1e-6. "
                    "sb3_act = Stable-Baselines3 model.predict(obs, deterministic=True) in float32."}


def write(model, out_json: str, **kw) -> Dict[str, Any]:
    """Write <id>.json and <id>.check.json next to it; verify the numpy runtime against SB3. Returns the doc."""
    policy_id = kw.pop("policy_id", None) or os.path.splitext(os.path.basename(out_json))[0]
    doc = policy_doc(model, policy_id, **kw)
    rt = MlpPolicy(doc)
    chk = check_doc(model, policy_id, int(np.prod(model.observation_space.shape)), runtime=rt)
    got = np.asarray(chk["act"], dtype=float)
    err = float(np.max(np.abs(got - np.asarray(chk["sb3_act"], dtype=float)))) if got.size else 0.0
    if err > SB3_TOLERANCE:
        raise AssertionError(f"numpy runtime disagrees with SB3 by {err:g} (> {SB3_TOLERANCE})")
    doc["card"].setdefault("runtime_check_max_abs_err", err)
    os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    with open(os.path.splitext(out_json)[0] + ".check.json", "w", encoding="utf-8") as f:
        json.dump(chk, f)
    return doc


def main(argv=None):
    from stable_baselines3 import PPO
    from .env import ENV_ID, ENV_VERSION, OBS_NAMES, ACT_NAMES, OBS_OFFSET, obs_scale
    from .classes import CLASSES
    p = argparse.ArgumentParser(description="export an SB3 PPO lander model to lunarsim-policy v1 JSON")
    p.add_argument("model")
    p.add_argument("--out", required=True)
    p.add_argument("--cls", default="CLPS", choices=sorted(CLASSES))
    a = p.parse_args(argv)
    model = PPO.load(a.model, device="cpu")
    doc = write(model, a.out, env_id=ENV_ID, env_version=ENV_VERSION, obs_names=OBS_NAMES,
                obs_scale=obs_scale(CLASSES[a.cls]).tolist(), obs_offset=OBS_OFFSET.tolist(), act_names=ACT_NAMES)
    print(f"wrote {a.out} ({len(doc['layers'])} layers); runtime check max |err| {doc['card']['runtime_check_max_abs_err']:.2e}")


if __name__ == "__main__":
    main()
