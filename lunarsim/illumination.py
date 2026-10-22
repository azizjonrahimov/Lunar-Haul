"""Real sun per site and rover leg (B-44): reader of sun_link-v1.json and the engine's location-aware night rule.

Opt-in Scenario field `illumination` (None = the v2 night rule from night_fraction, byte-identical results):

    {"file":       path to a lunarsim-sun-link file (default data/illumination/connecting_ridge/sun_link-v1.json),
     "criterion":  "half" (default) | "any_part" | "full"   -- lit = half / any part / all of the solar disc visible,
     "leg_rule":   "most" (default) | "worst"               -- a leg is lit when >= 80 % of its route samples are /
                                                               when every sample is,
     "start_year": 2028-2031 (default: the comms start_year when Scenario.comms is set, else 2028),
     "start_h":    hours after 2028-01-01 00:00 UTC that engine hour 0 maps to (overrides start_year)}

The engine's night rule with the field set (vehicles that can work in the dark are unaffected except for the night
speed factor):
  - a vehicle is in the dark at a site when that site is not lit, and does not start a job or a reposition there;
  - a planned drive is caught by the dark at the first moment one of its legs (or the site where it loads/unloads) is
    not lit; it then hibernates there until that leg is lit again (the v2 rule hibernates a fixed night length);
  - dispatch rules that avoid jobs ending in the night ask whether any leg of the plan goes dark;
  - parked vehicles are woken at every moment a site becomes lit;
  - legs without a route (pad <-> pad) are lit when both end points are.
The series covers 2028-2031 hourly; engine times past its end wrap around (as the Earth-link series do).
"""
from __future__ import annotations

import bisect
import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .comms import decode_windows, year_start_h

FORMAT = "lunarsim-sun-link"
CRITERIA = ("any_part", "half", "full")
LEG_RULES = ("most", "worst")
ILLUM_KEYS = {"file", "criterion", "leg_rule", "start_year", "start_h"}
DEFAULT_FILE = os.path.join("data", "illumination", "connecting_ridge", "sun_link-v1.json")

_DOCS: Dict[str, Dict[str, Any]] = {}


def load(path: str) -> Dict[str, Any]:
    p = os.path.abspath(path)
    if p not in _DOCS:
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        if doc.get("format") != FORMAT:
            raise ValueError(f"{path}: not a {FORMAT} file")
        _DOCS[p] = doc
    return _DOCS[p]


def validate(doc: Dict[str, Any]) -> List[str]:
    """Structural check ([] = valid): header, and every point and leg rule has a window code per criterion that
    decodes to sorted windows inside the series, with a summary fraction equal to the decoded one."""
    errs: List[str] = []
    if doc.get("format") != FORMAT or doc.get("version") != 1:
        return [f"not a {FORMAT} v1 document"]
    n = int(doc["time"]["n"])

    def chk(where: str, ent: Dict[str, Any]) -> None:
        for c in CRITERIA:
            code = ent.get("lit", {}).get(c)
            if code is None:
                errs.append(f"{where}: no windows for {c}")
                continue
            w = decode_windows(code)
            if len(w) and (w[0, 0] < 0 or w[-1, 1] > n or np.any(w[:, 1] <= w[:, 0]) or np.any(w[1:, 0] <= w[:-1, 1])):
                errs.append(f"{where} {c}: windows unsorted, empty or outside the series")
                continue
            frac = float((w[:, 1] - w[:, 0]).sum()) / n if len(w) else 0.0
            if abs(frac - ent["summary"][c]["fraction"]) > 1e-4:
                errs.append(f"{where} {c}: summary fraction {ent['summary'][c]['fraction']} != {frac:.5f}")

    for k, p in doc.get("points", {}).items():
        chk(f"points.{k}", p)
    for k, leg in doc.get("legs", {}).items():
        for r in LEG_RULES:
            if r not in leg:
                errs.append(f"legs.{k}: no rule {r}")
            else:
                chk(f"legs.{k}.{r}", leg[r])
    return errs[:20]


def _intersect(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    out, i, j = [], 0, 0
    while i < len(a) and j < len(b):
        s, e = max(a[i, 0], b[j, 0]), min(a[i, 1], b[j, 1])
        if e > s:
            out.append((s, e))
        if a[i, 1] < b[j, 1]:
            i += 1
        else:
            j += 1
    return np.array(out, dtype=np.int64).reshape(-1, 2)


class Illumination:
    """The engine's sunlit windows (engine hours) per site and leg. Built only when Scenario.illumination is set."""

    def __init__(self, cfg: Dict[str, Any], standoff: str, horizon_h: float, pads: Sequence[str],
                 comms_start_year: Optional[int] = None, find=None):
        unknown = set(cfg) - ILLUM_KEYS
        if unknown:
            raise ValueError(f"unknown illumination keys {sorted(unknown)}; known: {sorted(ILLUM_KEYS)}")
        self.criterion = cfg.get("criterion", "half")
        if self.criterion not in CRITERIA:
            raise ValueError(f"illumination criterion {self.criterion!r} not in {CRITERIA}")
        self.leg_rule = cfg.get("leg_rule", "most")
        if self.leg_rule not in LEG_RULES:
            raise ValueError(f"illumination leg_rule {self.leg_rule!r} not in {LEG_RULES}")
        if "start_h" in cfg:
            self.t0 = float(cfg["start_h"])
        else:
            self.t0 = year_start_h(int(cfg.get("start_year", comms_start_year or 2028)))
        path = cfg.get("file") or DEFAULT_FILE
        if find is not None and not os.path.isabs(path) and not os.path.exists(path):
            path = find(path)
        self.doc = load(path)
        self.n = int(self.doc["time"]["n"])
        self.standoff, self.pads, self.horizon_h = str(standoff), set(pads), float(horizon_h)
        self._w: Dict[Tuple[str, Optional[str]], Tuple[List[float], List[float]]] = {}
        self.missing_legs: set = set()

    # ---- windows ----
    def name(self, site: str) -> str:
        return f"{site}@{self.standoff}" if site in self.pads else site

    def _raw(self, a: str, b: Optional[str]) -> np.ndarray:
        """Lit hour windows [start, end) of a site (b None) or a leg, in series hours."""
        if b is None or b == a:
            p = self.doc["points"].get(self.name(a))
            if p is None:
                raise KeyError(f"illumination: no point {self.name(a)} in the sun-link file")
            return decode_windows(p["lit"][self.criterion])
        legs = self.doc["legs"]
        for k in (f"{self.name(a)}->{self.name(b)}", f"{self.name(b)}->{self.name(a)}"):
            if k in legs:
                return decode_windows(legs[k][self.leg_rule]["lit"][self.criterion])
        self.missing_legs.add(f"{self.name(a)}->{self.name(b)}")
        return _intersect(self._raw(a, None), self._raw(b, None))

    def _windows(self, a: str, b: Optional[str] = None) -> Tuple[List[float], List[float]]:
        """Lit windows in engine hours over two series lengths (so a horizon past the series end wraps)."""
        k = (a, None if b == a else b)
        if k not in self._w:
            w = self._raw(a, k[1]).astype(float)
            ws = np.concatenate([w, w + self.n]) - self.t0
            self._w[k] = (ws[:, 0].tolist(), ws[:, 1].tolist())
        return self._w[k]

    def lit(self, t: float, a: str, b: Optional[str] = None) -> bool:
        s, e = self._windows(a, b)
        i = bisect.bisect_right(s, t) - 1
        return i >= 0 and t < e[i]

    def dark(self, t: float, a: str, b: Optional[str] = None) -> bool:
        return not self.lit(t, a, b)

    def next_dark(self, t: float, a: str, b: Optional[str] = None) -> float:
        """t if dark at t, else the end of the lit window holding t (inf if it never ends)."""
        s, e = self._windows(a, b)
        i = bisect.bisect_right(s, t) - 1
        if i >= 0 and t < e[i]:
            return e[i]
        return t

    def light_after(self, t: float, a: str, b: Optional[str] = None) -> float:
        """t if lit at t, else the start of the next lit window (inf if none)."""
        s, e = self._windows(a, b)
        i = bisect.bisect_right(s, t) - 1
        if i >= 0 and t < e[i]:
            return t
        return s[i + 1] if i + 1 < len(s) else float("inf")

    def first_dark(self, segs: Sequence[Sequence[Any]]) -> Optional[Tuple[float, float]]:
        """(time the plan is caught by the dark, time that place is lit again) along planned segments
        [a, b, t0, t1, ...] (a == b: a stop at site a), or None when the plan stays lit."""
        for seg in segs:
            a, b, s0, s1 = seg[0], seg[1], float(seg[2]), float(seg[3])
            if s1 <= s0 + 1e-9:
                continue
            bb = None if a == b else b
            td = self.next_dark(s0, a, bb)
            if td < s1 - 1e-9:
                return td, self.light_after(td, a, bb)
        return None

    def light_returns(self, sites: Sequence[str], horizon_h: float) -> List[float]:
        """Every engine time in (0, horizon) at which one of the sites becomes lit (wake-ups for parked vehicles)."""
        out = set()
        for site in sites:
            s, _ = self._windows(site)
            out.update(x for x in s if 0.0 < x < horizon_h)
        return sorted(out)

    def dark_windows(self, site: str, horizon_h: float) -> List[List[float]]:
        """Dark windows of a site clipped to [0, horizon] (the trace's 'nights')."""
        s, e = self._windows(site)
        out, prev = [], -float("inf")
        for a, b in list(zip(s, e)) + [(float("inf"), float("inf"))]:
            lo, hi = max(prev, 0.0), min(a, horizon_h)
            if hi > lo:
                out.append([lo, hi])
            prev = b
        return out
