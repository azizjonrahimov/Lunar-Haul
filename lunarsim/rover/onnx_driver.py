"""Run an exported rover driver (lunarsim-policy v1, kind "cnn") with onnxruntime.

    drv = OnnxDriver("data/policies/rover_bc_s0.json")      # the card; the .onnx sits next to it
    action = drv.act(obs)                                    # obs = DriveEnv observation dict

Same act(obs) interface as bc.ExpertDriver and bc.TorchDriver. Needs onnxruntime (the [ml] extra).
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict

import numpy as np


class OnnxDriver:
    def __init__(self, card_path: str, verify_sha: bool = True):
        import onnxruntime as ort
        with open(card_path, encoding="utf-8") as f:
            self.card: Dict[str, Any] = json.load(f)
        if self.card.get("format") != "lunarsim-policy" or self.card.get("kind") != "cnn":
            raise ValueError(f"{card_path}: not a lunarsim-policy cnn card")
        self.id = self.card["id"]
        self.onnx_path = os.path.join(os.path.dirname(os.path.abspath(card_path)), self.card["onnx"])
        if verify_sha and self.card.get("onnx_sha256"):
            with open(self.onnx_path, "rb") as f:
                if hashlib.sha256(f.read()).hexdigest() != self.card["onnx_sha256"]:
                    raise ValueError(f"{self.onnx_path}: sha256 does not match the card")
        self.sess = ort.InferenceSession(self.onnx_path, providers=["CPUExecutionProvider"])

    def reset(self):
        pass

    def act_batch(self, patch: np.ndarray, scalars: np.ndarray) -> np.ndarray:
        return self.sess.run(["action"], {"patch": np.asarray(patch, np.float32),
                                          "scalars": np.asarray(scalars, np.float32)})[0]

    def act(self, obs) -> np.ndarray:
        return self.act_batch(np.asarray(obs["patch"], np.float32)[None],
                              np.asarray(obs["scalars"], np.float32)[None])[0].astype(np.float32)
