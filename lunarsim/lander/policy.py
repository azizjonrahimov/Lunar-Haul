"""Numpy runtime for lunarsim-policy v1 MLP files (PLAN §5.2). No torch needed.

    pol = MlpPolicy.from_json("data/policies/lander_CLPS_baseline_s0.json")
    action = pol.act(obs)          # obs already scaled as the env produces it

Forward pass: h = obs; for each layer: h = act(W h + b) with act "tanh" or "linear"; the last layer's output
is the action mean. deterministic "mean_clipped" -> clip(mean, low, high); "argmax" -> index of the max.
W is stored as rows = outputs (w[i][j] multiplies input j for output i), matching torch.nn.Linear.weight.
The JS runtime (site/src/policy.js) must agree to 1e-6 on <id>.check.json.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List

import numpy as np

POLICY_FORMAT = "lunarsim-policy"
POLICY_VERSION = 1
_ACTS = {"tanh": np.tanh, "linear": lambda x: x, "relu": lambda x: np.maximum(x, 0.0)}


class MlpPolicy:
    def __init__(self, doc: Dict[str, Any]):
        if doc.get("format") != POLICY_FORMAT or doc.get("version") != POLICY_VERSION:
            raise ValueError(f"not a {POLICY_FORMAT} v{POLICY_VERSION} document")
        if doc.get("kind") != "mlp":
            raise ValueError(f"MlpPolicy reads kind 'mlp', got {doc.get('kind')!r}")
        self.doc = doc
        self.id = doc["id"]
        self.layers = [(np.asarray(L["w"], dtype=np.float64), np.asarray(L["b"], dtype=np.float64), L["act"])
                       for L in doc["layers"]]
        for w, b, act in self.layers:
            if act not in _ACTS:
                raise ValueError(f"unknown activation {act!r}")
            if w.shape[0] != b.shape[0]:
                raise ValueError("layer weight/bias size mismatch")
        self.act_spec = doc["act"]
        self.low = np.asarray(self.act_spec.get("low", []), dtype=np.float64)
        self.high = np.asarray(self.act_spec.get("high", []), dtype=np.float64)
        self.deterministic = doc.get("deterministic", "mean_clipped")
        self.obs_dim = self.layers[0][0].shape[1]

    @classmethod
    def from_json(cls, path: str) -> "MlpPolicy":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def forward(self, obs) -> np.ndarray:
        h = np.asarray(obs, dtype=np.float64)
        for w, b, act in self.layers:
            h = _ACTS[act](h @ w.T + b)
        return h

    def act(self, obs):
        """Deterministic action for one observation (1-D) or a batch (2-D)."""
        out = self.forward(obs)
        if self.deterministic == "argmax":
            return np.argmax(out, axis=-1)
        return np.clip(out, self.low, self.high)


def check_vectors(policy: MlpPolicy, n: int = 100, seed: int = 0) -> Dict[str, List]:
    """Random observations in [-2, 2] and this runtime's actions (the shared JS/Python test file)."""
    rng = np.random.default_rng(seed)
    obs = rng.uniform(-2.0, 2.0, size=(n, policy.obs_dim))
    act = policy.act(obs)
    return {"obs": obs.tolist(), "act": np.asarray(act).tolist()}
