"""The integrity network: a small causal 1D convolutional network over the last W seconds of what A knows about B.

Input per step (faults.FEATURES, raw units), squashed by fixed transforms (TRANSFORMS; no fitted statistics):
    x_norm = fn(x / pre) / post,  fn = lin (identity) or slog1p (sign(x) log(1 + |x|)).
Network: a stack of dilated convolutions (kernel k, dilations d1..dn, ReLU, a residual connection from the second
layer on), then a 1 x 1 convolution to one logit: the fault probability at the window's end is sigmoid(logit).
Receptive field W = 1 + (k - 1) (d1 + ... + dn) steps = seconds at 1 Hz. No normalisation layers, no dropout at
inference: the flight computer runs n convolutions and one dot product per report.

Two runtimes with the same numbers:
  IntegrityNet (torch)   training, and streaming over long recordings (left zero padding = "no history yet");
  Policy (numpy float64) the reference for a re-implementation: one window [W, 10] -> one logit. Its JSON file
                         (to_doc / Policy) follows data/policies/atc_bid_linear_v1.json: format "lunarsim-policy".
A GRU variant (GruNet) exists for the model search only; it has no JSON codec.
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from . import faults as F

ENV = "lunar/integrity-v1"
TRANSFORMS = (            # (fn, pre, post) per feature, in the order faults.FEATURES
    ("slog1p", 1.0, 3.0),        # z
    ("slog1p", 100.0, 4.0),      # range_m
    ("slog1p", 1.0, 2.0),        # rep_speed_mps
    ("lin", math.pi, 1.0),       # rep_dheading_rad
    ("slog1p", 1.0, 3.0),        # rep_sigma_m
    ("slog1p", 1.0, 3.0),        # own_sigma_m
    ("lin", 1.0, 1.0),           # lq_degraded
    ("slog1p", 60.0, 6.0),       # own_fix_age_s
    ("lin", 1.0, 1.0),           # range_valid
    ("lin", 1.0, 1.0),           # range_class_long
)


def transform_np(x: np.ndarray) -> np.ndarray:
    out = np.empty(x.shape, np.float64)
    for j, (fn, pre, post) in enumerate(TRANSFORMS):
        v = x[..., j].astype(np.float64) / pre
        out[..., j] = (np.sign(v) * np.log1p(np.abs(v)) if fn == "slog1p" else v) / post
    return out


def receptive_field(kernel: int, dilations: Sequence[int]) -> int:
    return 1 + (kernel - 1) * int(sum(dilations))


def _torch():
    import torch
    return torch


def make_model(cfg: Dict[str, Any]):
    """cfg: {"arch": "tcn", "channels", "kernel", "dilations", "residual"} or {"arch": "gru", "hidden"}."""
    torch = _torch()
    nn = torch.nn
    n_in = len(F.FEATURES)

    class _Base(nn.Module):
        def __init__(self):
            super().__init__()
            self.register_buffer("pre", torch.tensor([t[1] for t in TRANSFORMS], dtype=torch.float32))
            self.register_buffer("post", torch.tensor([t[2] for t in TRANSFORMS], dtype=torch.float32))
            self.register_buffer("is_log", torch.tensor([t[0] == "slog1p" for t in TRANSFORMS]))

        def squash(self, x):
            v = x / self.pre
            return torch.where(self.is_log, torch.sign(v) * torch.log1p(torch.abs(v)), v) / self.post

    class IntegrityNet(_Base):
        def __init__(self):
            super().__init__()
            self.cfg = dict(cfg)
            c, k = int(cfg["channels"]), int(cfg["kernel"])
            self.dilations = [int(d) for d in cfg["dilations"]]
            self.kernel = k
            self.residual = bool(cfg.get("residual", True))
            self.convs = nn.ModuleList([nn.Conv1d(n_in if i == 0 else c, c, k, dilation=d)
                                        for i, d in enumerate(self.dilations)])
            self.head = nn.Conv1d(c, 1, 1)
            self.rf = receptive_field(k, self.dilations)

        def forward(self, x):
            """x [N, T, 10] raw features -> logits [N, T] (causal: step t sees steps t - W + 1 .. t)."""
            h = self.squash(x).transpose(1, 2)
            for i, (conv, d) in enumerate(zip(self.convs, self.dilations)):
                y = torch.relu(conv(nn.functional.pad(h, ((self.kernel - 1) * d, 0))))
                h = h + y if (self.residual and i > 0) else y
            return self.head(h)[:, 0, :]

    class GruNet(_Base):
        def __init__(self):
            super().__init__()
            self.cfg = dict(cfg)
            self.gru = nn.GRU(n_in, int(cfg["hidden"]), batch_first=True)
            self.head = nn.Linear(int(cfg["hidden"]), 1)
            self.rf = 1

        def forward(self, x):
            h, _ = self.gru(self.squash(x))
            return self.head(h)[..., 0]

    return GruNet() if cfg.get("arch") == "gru" else IntegrityNet()


def n_params(model) -> int:
    return int(sum(p.numel() for p in model.parameters()))


def score_streams(model, X: np.ndarray, batch: int = 64) -> np.ndarray:
    """Logits for whole streams [N, T, 10] -> [N, T] float32 (streaming form, no gradient)."""
    torch = _torch()
    model.eval()
    out = np.zeros(X.shape[:2], np.float32)
    with torch.no_grad():
        for i in range(0, len(X), batch):
            out[i:i + batch] = model(torch.from_numpy(X[i:i + batch])).numpy()
    return out


# ------------------------------------------------------------------------------------------------ JSON codec
def _r(a: np.ndarray) -> list:
    """Float32 values written with 9 significant digits (round-trips float32 exactly)."""
    return json.loads(json.dumps(np.asarray(a, np.float64).tolist()), parse_float=lambda s: float(f"{float(s):.9g}"))


def to_doc(model, policy_id: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if model.cfg.get("arch", "tcn") != "tcn":
        raise ValueError("only the convolutional network has a JSON codec")
    layers: List[Dict[str, Any]] = []
    for i, (conv, d) in enumerate(zip(model.convs, model.dilations)):
        layers.append({"type": "conv1d", "w": _r(conv.weight.detach().numpy()), "b": _r(conv.bias.detach().numpy()),
                       "dilation": d, "act": "relu", "residual": bool(model.residual and i > 0)})
    layers.append({"type": "conv1d", "w": _r(model.head.weight.detach().numpy()),
                   "b": _r(model.head.bias.detach().numpy()), "dilation": 1, "act": "linear", "residual": False})
    doc = {"format": "lunarsim-policy", "version": 1, "kind": "tcn", "id": policy_id, "env": ENV,
           "obs": {"names": list(F.FEATURES), "window_steps": model.rf, "rate_hz": 1.0,
                   "transform": [{"fn": fn, "pre": pre, "post": post} for fn, pre, post in TRANSFORMS],
                   "note": "one window = the last window_steps reports, oldest first, each row in the order of names; "
                           "x_norm = fn(x / pre) / post with fn lin (identity) or slog1p (sign(x) ln(1 + |x|)); "
                           "when range_valid is 0 the features z, range_m, rep_sigma_m, lq_degraded and range_class_long are 0"},
           "act": {"names": ["fault_logit"],
                   "note": "probability that B's reports are faulty at the window's last step = 1 / (1 + exp(-logit)); "
                           "alarm when logit > threshold (thresholds below)"},
           "layers": layers,
           "layer_note": "w[out][in][tap]; valid convolution, tap j reads step t + j * dilation; a residual layer adds "
                         "its input at the same (latest) steps to its ReLU output; the last layer gives the logit",
           "n_params": n_params(model)}
    doc.update(extra or {})
    return doc


class Policy:
    """Float64 numpy runtime of an integrity policy file: one window -> one logit."""

    def __init__(self, path: Optional[str] = None, doc: Optional[Dict[str, Any]] = None):
        if doc is None:
            with open(path, encoding="utf-8") as f:
                doc = json.load(f)
        if doc.get("format") != "lunarsim-policy" or doc.get("env") != ENV:
            raise ValueError("not an integrity policy")
        if list(doc["obs"]["names"]) != list(F.FEATURES):
            raise ValueError("policy features differ from lunarsim.nn.faults.FEATURES")
        self.doc = doc
        self.window = int(doc["obs"]["window_steps"])
        self.tf = [(t["fn"], float(t["pre"]), float(t["post"])) for t in doc["obs"]["transform"]]
        self.layers = [(np.array(L["w"], float), np.array(L["b"], float), int(L["dilation"]), L["act"],
                        bool(L["residual"])) for L in doc["layers"]]

    def squash(self, x: np.ndarray) -> np.ndarray:
        out = np.empty(x.shape, np.float64)
        for j, (fn, pre, post) in enumerate(self.tf):
            v = np.asarray(x[..., j], np.float64) / pre
            out[..., j] = (np.sign(v) * np.log1p(np.abs(v)) if fn == "slog1p" else v) / post
        return out

    def __call__(self, window: np.ndarray) -> np.ndarray:
        """Logit for one window [W, 10] or many [n, W, 10] (raw features, oldest step first)."""
        x = np.asarray(window, np.float64)
        single = x.ndim == 2
        h = self.squash(np.atleast_3d(x) if not single else x[None])[:, -self.window:, :].transpose(0, 2, 1)
        for w, b, d, act, res in self.layers:
            k = w.shape[2]
            t_out = h.shape[2] - (k - 1) * d
            y = np.zeros((h.shape[0], w.shape[0], t_out))
            for j in range(k):
                y += np.einsum("oi,nit->not", w[:, :, j], h[:, :, j * d:j * d + t_out])
            y += b[None, :, None]
            if act == "relu":
                y = np.maximum(y, 0.0)
            elif act != "linear":
                raise ValueError(act)
            h = h[:, :, -t_out:] + y if res else y
        out = h[:, 0, -1]
        return out[0] if single else out


def from_doc(doc: Dict[str, Any]):
    """A torch IntegrityNet with the weights of a policy document."""
    torch = _torch()
    convs = doc["layers"][:-1]
    cfg = {"arch": "tcn", "channels": len(convs[0]["b"]), "kernel": len(convs[0]["w"][0][0]),
           "dilations": [L["dilation"] for L in convs], "residual": any(L["residual"] for L in convs)}
    m = make_model(cfg)
    with torch.no_grad():
        for conv, L in zip(m.convs, convs):
            conv.weight.copy_(torch.tensor(L["w"], dtype=torch.float32))
            conv.bias.copy_(torch.tensor(L["b"], dtype=torch.float32))
        m.head.weight.copy_(torch.tensor(doc["layers"][-1]["w"], dtype=torch.float32))
        m.head.bias.copy_(torch.tensor(doc["layers"][-1]["b"], dtype=torch.float32))
    return m


# ------------------------------------------------------------------------------------------------ flat weights
def get_flat(model) -> np.ndarray:
    return np.concatenate([p.detach().numpy().ravel() for p in model.parameters()]).astype(np.float32)


def set_flat(model, vec: np.ndarray) -> None:
    torch = _torch()
    i = 0
    with torch.no_grad():
        for p in model.parameters():
            n = p.numel()
            p.copy_(torch.from_numpy(np.asarray(vec[i:i + n], np.float32).reshape(tuple(p.shape))))
            i += n
