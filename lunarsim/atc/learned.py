"""C_LEARNED (B-74): a small learned correction to the auction's hand-built bids.

score = -bid / urgency_usd_per_h + g(features);  the robot bids  bid' = bid - urgency_usd_per_h * g(features)
g is an MLP 12-32-32-1 (tanh; ~1.5k parameters) or, as the honest baseline, a linear model on the same features.
Training (tools/atc/train_bid.py): first imitation of O_ORACLE (DAgger): at every auction round each robot's
candidate seed items are labelled with the item the oracle (the full-information pooled marketplace on the same
state) gives that robot. That reproduces the hand-built bids by construction (O_ORACLE is the same bid rule with full
information; every disagreement is an item another robot wins), so the correction is then fitted on the objective
itself with the cross-entropy method (mean urgent wait, common random numbers, selection on tuning seeds).

Features (only what the robot can know locally; FEATURES, with the units the policy file scales):
  job_h        planned hours of the bundle job (its marginal insertion cost in time)
  age_d        days since the seed item became ready
  prio         seed item's priority - 2 (urgent -1, normal 0, deferrable +1)
  mass_frac    bundle mass / the robot's capacity
  approach_h   hours to drive empty to the item's pad
  battery      battery state of charge (0..1)
  dark_or_low  hours until the robot's next dark period or until its battery would run out driving (whichever
               comes first) / 336, capped at 1 (anticipation the greedy bid ignores; LEAD, B-74)
  link_base    1 if the robot is in the BASE mast's mesh component
  heard        robots it hears directly / 8
  queue        claims it holds / 5
  bundle_n     items in the bundle / 10 (replaces "team partner needed": team lifts are not bid singly here)
  slack_d      (target - age - job_h) / 24 h, targets 24 / 168 / 720 h by priority (PREREG 24 h for urgent)
  landing      hours until the next published landing at the item's pad or the robot's site / 336, capped at 1
               (anticipation the greedy bid ignores; LEAD, B-74)
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

FEATURES = ("job_h", "age_d", "prio", "mass_frac", "approach_h", "battery", "dark_or_low", "link_base", "heard",
            "queue", "bundle_n", "slack_d", "landing")
SCALE = (3.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 10.0, 1.0)   # fixed feature scales (CEM policies)
TARGET_H = {1: 24.0, 2: 168.0, 3: 720.0}
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_POLICY = os.path.join(ROOT, "data", "policies", "atc_bid_v1.json")


def features(sim, v, bundle, route, ctx: Dict[str, Any]) -> np.ndarray:
    from ..dispatch import _plan_hours
    t = sim.t
    c = bundle[0]
    job_h = _plan_hours(sim, v, bundle, route)
    age_h = max(0.0, t - c.t_ready)
    prio = min(x.priority for x in bundle)
    dark = math.inf if v.cls.night_ops else max(0.0, sim.next_dark(t, v.location) - t)
    rate = v.cls.energy_wh_per_km * v.cls.speed_kmh                # Wh per driving hour (flat, empty)
    low = v.battery_wh / rate if rate > 0 else math.inf
    dark_or_low = min(1.0, min(dark, low) / 336.0)
    nl = ctx.get("next_landing", {})
    landing = min(1.0, max(0.0, min(nl.get(c.origin, math.inf), nl.get(v.location, math.inf)) - t) / 336.0)
    return np.array([
        job_h if math.isfinite(job_h) else 1e3,
        age_h / 24.0,
        prio - 2.0,
        sum(x.mass_kg for x in bundle) / max(v.cls.capacity_kg, 1e-9),
        sim.travel_h(v, v.location, c.origin, False, False, t),
        v.battery_wh / max(v.cls.battery_wh, 1e-9),
        dark_or_low,
        1.0 if v.id in ctx.get("base_comp", ()) else 0.0,
        ctx.get("degree", {}).get(v.id, 0) / 8.0,
        len(ctx.get("claims", {}).get(v.id) or []) / 5.0,
        len(bundle) / 10.0,
        (TARGET_H[prio] - age_h - (job_h if math.isfinite(job_h) else 1e3)) / 24.0,
        landing,
    ], dtype=np.float64)


def next_landings(sim) -> dict:
    """Next published landing time per pad after now."""
    out = {}
    for tl, _, pad in sim.landing_schedule:
        if tl > sim.t and tl < out.get(pad, math.inf):
            out[pad] = tl
    return out


class Policy:
    """Float64 numpy runtime of an atc_bid policy file (kind mlp or linear)."""

    def __init__(self, path: Optional[str] = None, doc: Optional[Dict[str, Any]] = None):
        if doc is None:
            with open(path or DEFAULT_POLICY, encoding="utf-8") as f:
                doc = json.load(f)
        if doc.get("format") != "lunarsim-policy" or doc.get("env") != "lunar/ATC-bid-v1":
            raise ValueError("not an ATC bid policy")
        if list(doc["obs"]["names"]) != list(FEATURES):
            raise ValueError("policy features differ from lunarsim.atc.learned.FEATURES")
        self.doc = doc
        self.offset = np.array(doc["obs"]["offset"], float)
        self.scale = np.array(doc["obs"]["scale"], float)
        self.layers = [(np.array(L["w"], float), np.array(L["b"], float), L["act"]) for L in doc["layers"]]

    def __call__(self, x: np.ndarray) -> np.ndarray:
        """g(features) for one row (12,) or many (n, 12)."""
        h = (np.atleast_2d(np.asarray(x, float)) - self.offset) / self.scale
        for w, b, act in self.layers:
            h = h @ w.T + b
            if act == "tanh":
                h = np.tanh(h)
            elif act != "linear":
                raise ValueError(act)
        out = h[:, 0]
        return out if np.ndim(x) == 2 else out[0]


def oracle_assignment(sim, waiting, free, inner_kw) -> Dict[int, set]:
    """The teacher: what the full-information pooled marketplace would give each free robot now (no side effects:
    no staging, no wake-ups)."""
    from .. import dispatch as D
    push = sim._push
    sim._push = lambda *a, **k: None
    try:
        kw = dict(inner_kw)
        kw["anticipate"] = False
        jobs = D.marketplace(sim, list(waiting), list(free), **kw)
    finally:
        sim._push = push
    out: Dict[int, set] = {}
    for j in jobs:
        if len(j.vehicles) == 1:
            out[j.vehicles[0].id] = {id(x) for x in j.items}
    return out


class Collector:
    """Rows for DAgger: (group, features, hand score, label) at every auction round."""

    def __init__(self):
        self.X: List[np.ndarray] = []
        self.s: List[float] = []
        self.y: List[int] = []
        self.g: List[int] = []
        self.next_group = 0

    def add_group(self, rows: Sequence[np.ndarray], hand: Sequence[float], labels: Sequence[int]) -> None:
        if not rows or sum(labels) != 1:
            return
        gid = self.next_group
        self.next_group += 1
        for x, s, y in zip(rows, hand, labels):
            self.X.append(x)
            self.s.append(s)
            self.y.append(y)
            self.g.append(gid)

    def arrays(self):
        if not self.X:
            return np.zeros((0, len(FEATURES))), np.zeros(0), np.zeros(0, int), np.zeros(0, int)
        return np.array(self.X), np.array(self.s), np.array(self.y, int), np.array(self.g, int)
