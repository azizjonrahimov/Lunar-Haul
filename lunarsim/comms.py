"""Earth-link windows (``lunarsim-earth-link`` v1, research thread R-1 "Earth in sight"): reader and link queries.

The file ``data/comms/<terrain>/earth_link-v1.json`` is written by ``tools/comms/earth_link.py`` from SPICE
(Earth's topocentric direction in MOON_ME) and terrain horizon masks in Earth's wedge (5 m tile near field,
80 m polar LOLA DEM out to 300 km). This module only reads it; the engine does not use it yet (B-41).

Time axis: epochs every ``time.step_min`` minutes from ``time.start_utc``; epoch i covers [i, i + 1) steps.
Windows: the linked intervals of a series as epoch-index pairs [start, end), end exclusive, stored
delta-encoded as ``[s0, l0, g1, l1, g2, l2, ...]``: start0 = s0, end0 = s0 + l0, start1 = end0 + g1, ...

Criteria (Earth's disc against the terrain horizon h at Earth's grid bearing, seen from the antenna):
    any_part        upper limb above the horizon: elevation + apparent radius > h
    centre+0.5deg   centre at least 0.5 deg above the horizon
    centre+2deg     centre at least 2 deg above the horizon
Modes:
    dte             direct to Earth from the rover antenna (2.5 m)
    dte+mast        direct, or line of sight to the mast top at BASE (10 m) within 10 km while the mast sees Earth
Keys: points by site id ("BASE", "PAD_A@1", ...; pads by sites.json standoff key) and legs as in
lunarsim/rover/tables.legs_from_sites ("BASE->DEPOT", "PAD_A@1->BASE"); a leg is linked only when every
sample along its route is linked (teleoperation needs the link for the whole drive).

    from lunarsim.comms import EarthLink
    el = EarthLink.load("data/comms/connecting_ridge/earth_link-v1.json")
    el.linked("BASE->DEPOT", t_h=100.0, criterion="any_part")
    el.next_change("BASE->DEPOT", 100.0)       # (linked now?, hours until that changes)
    python -m lunarsim.comms data/comms/connecting_ridge/earth_link-v1.json --legs
"""
from __future__ import annotations

import json
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

EARTH_LINK_FORMAT = "lunarsim-earth-link"
EARTH_LINK_VERSION = 1
CRITERIA = ("any_part", "centre+0.5deg", "centre+2deg")
MODES = ("dte", "dte+mast")


# ---------------------------------------------------------------------------------------------------------
# run-length windows
# ---------------------------------------------------------------------------------------------------------
def runs(mask: np.ndarray) -> np.ndarray:
    """(k, 2) int array of [start, end) index pairs of the True runs of a boolean series."""
    m = np.asarray(mask, dtype=bool)
    if m.size == 0:
        return np.zeros((0, 2), dtype=np.int64)
    d = np.diff(np.concatenate([[0], m.view(np.int8), [0]]))
    return np.stack([np.flatnonzero(d == 1), np.flatnonzero(d == -1)], axis=1).astype(np.int64)


def encode_windows(w: np.ndarray) -> List[int]:
    """[s0, l0, g1, l1, ...] from (k, 2) [start, end) pairs."""
    out: List[int] = []
    prev_end = 0
    for s, e in np.asarray(w, dtype=np.int64).reshape(-1, 2):
        out += [int(s - prev_end), int(e - s)]
        prev_end = e
    return out


def decode_windows(code: Sequence[int]) -> np.ndarray:
    """(k, 2) [start, end) pairs from the delta code."""
    c = np.asarray(code, dtype=np.int64).reshape(-1, 2)
    if c.size == 0:
        return np.zeros((0, 2), dtype=np.int64)
    bounds = np.cumsum(c.reshape(-1))
    return bounds.reshape(-1, 2)


def windows_to_mask(w: np.ndarray, n: int) -> np.ndarray:
    m = np.zeros(n, dtype=bool)
    for s, e in np.asarray(w).reshape(-1, 2):
        m[s:e] = True
    return m


def summarize(w: np.ndarray, n: int, step_h: float) -> Dict[str, float]:
    """Link fraction, window count and mean length, and the unlinked gaps (series ends included)."""
    w = np.asarray(w, dtype=np.int64).reshape(-1, 2)
    on = int((w[:, 1] - w[:, 0]).sum()) if len(w) else 0
    edges = np.concatenate([[0], w.reshape(-1), [n]]).reshape(-1, 2)      # [gap start, gap end) pairs
    gaps = edges[:, 1] - edges[:, 0]
    gaps = gaps[gaps > 0]
    lens = w[:, 1] - w[:, 0] if len(w) else np.zeros(0)
    return {"fraction": round(on / n, 5), "n_windows": int(len(w)),
            "mean_window_h": round(float(lens.mean()) * step_h, 2) if len(lens) else 0.0,
            "mean_gap_h": round(float(gaps.mean()) * step_h, 2) if len(gaps) else 0.0,
            "max_gap_h": round(float(gaps.max()) * step_h, 2) if len(gaps) else 0.0}


def validate(doc: Dict[str, Any]) -> List[str]:
    """Structural check of an Earth-link document ([] = valid): header, time axis, and for every point, leg and the
    mast a window code per mode and criterion that decodes to sorted, non-overlapping windows inside the series,
    with a summary fraction equal to the decoded one."""
    errs: List[str] = []
    if doc.get("format") != EARTH_LINK_FORMAT or doc.get("version") != EARTH_LINK_VERSION:
        return [f"format/version must be {EARTH_LINK_FORMAT} v{EARTH_LINK_VERSION}"]
    try:
        n = int(doc["time"]["n"])
        step_h = float(doc["time"]["step_min"]) / 60.0
    except (KeyError, TypeError, ValueError):
        return ["time.n and time.step_min are required"]

    def check(where, code, summ):
        if not isinstance(code, list) or len(code) % 2 or any(not isinstance(v, int) or v < 0 for v in code):
            errs.append(f"{where}: window code must be an even-length list of non-negative integers")
            return
        w = decode_windows(code)
        if len(w) and (w[0, 0] < 0 or w[-1, 1] > n or np.any(w[:, 1] <= w[:, 0]) or np.any(w[1:, 0] < w[:-1, 1])):
            errs.append(f"{where}: windows must be sorted, non-empty, non-overlapping and inside [0, {n}]")
            return
        if summ is not None and abs(summarize(w, n, step_h)["fraction"] - summ.get("fraction", -1)) > 1e-5:
            errs.append(f"{where}: summary fraction does not match the windows")

    for kind in ("points", "legs"):
        for key, e in doc.get(kind, {}).items():
            if kind == "legs" and e.get("route", True) is None:
                continue
            for mode in MODES:
                for c in CRITERIA:
                    try:
                        check(f"{kind}.{key}.{mode}.{c}", e["windows"][mode][c], e["summary"][mode][c])
                    except KeyError:
                        errs.append(f"{kind}.{key}: missing windows or summary for {mode} / {c}")
    if doc.get("mast"):
        for c in CRITERIA:
            check(f"mast.{c}", doc["mast"]["windows"].get(c), doc["mast"].get("summary", {}).get(c))
    return errs


# ---------------------------------------------------------------------------------------------------------
# reader
# ---------------------------------------------------------------------------------------------------------
class EarthLink:
    """Read-only access to a lunarsim-earth-link v1 document. Times are hours since time.start_utc."""

    def __init__(self, doc: Dict[str, Any]):
        if doc.get("format") != EARTH_LINK_FORMAT or doc.get("version") != EARTH_LINK_VERSION:
            raise ValueError(f"not a {EARTH_LINK_FORMAT} v{EARTH_LINK_VERSION} document")
        self.doc = doc
        self.n = int(doc["time"]["n"])
        self.step_h = float(doc["time"]["step_min"]) / 60.0
        self.horizon_h = self.n * self.step_h
        self._cache: Dict[Tuple[str, str, str], np.ndarray] = {}

    @classmethod
    def load(cls, path: str) -> "EarthLink":
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f))

    def points(self) -> List[str]:
        return list(self.doc["points"])

    def legs(self) -> List[str]:
        return list(self.doc["legs"])

    def _entry(self, key: str) -> Dict[str, Any]:
        if key in self.doc["legs"]:
            return self.doc["legs"][key]
        if key in self.doc["points"]:
            return self.doc["points"][key]
        if key == "mast" and self.doc.get("mast"):
            return self.doc["mast"]
        raise KeyError(f"no point or leg {key!r}")

    def windows(self, key: str, criterion: str = "any_part", mode: str = "dte") -> np.ndarray:
        """(k, 2) epoch-index [start, end) pairs when `key` is linked."""
        if criterion not in CRITERIA or mode not in MODES:
            raise ValueError(f"criterion in {CRITERIA}, mode in {MODES}")
        ck = (key, criterion, mode)
        if ck not in self._cache:
            e = self._entry(key)
            wins = e["windows"] if key == "mast" else e["windows"][mode]
            self._cache[ck] = decode_windows(wins[criterion])
        return self._cache[ck]

    def _index(self, t_h: float, wrap: bool) -> int:
        i = int(math.floor(t_h / self.step_h + 1e-9))
        if wrap:
            return i % self.n
        if not 0 <= i < self.n:
            raise ValueError(f"t = {t_h} h outside the series (0 to {self.horizon_h} h); pass wrap=True to repeat it")
        return i

    def linked(self, key: str, t_h: float, criterion: str = "any_part", mode: str = "dte", wrap: bool = False) -> bool:
        w = self.windows(key, criterion, mode)
        i = self._index(t_h, wrap)
        j = int(np.searchsorted(w[:, 0], i, side="right")) - 1
        return bool(j >= 0 and i < w[j, 1])

    def next_change(self, key: str, t_h: float, criterion: str = "any_part", mode: str = "dte",
                    wrap: bool = False) -> Tuple[bool, float]:
        """(linked at t, hours from t until the state changes); inf if it never changes again in the series."""
        w = self.windows(key, criterion, mode)
        i = self._index(t_h, wrap)
        frac = t_h / self.step_h - math.floor(t_h / self.step_h + 1e-9)
        j = int(np.searchsorted(w[:, 0], i, side="right")) - 1
        if j >= 0 and i < w[j, 1]:
            return True, (w[j, 1] - i - frac) * self.step_h
        nxt = w[j + 1, 0] if j + 1 < len(w) else None
        return False, ((nxt - i - frac) * self.step_h if nxt is not None else math.inf)

    def summary(self, key: str, criterion: str = "any_part", mode: str = "dte") -> Dict[str, float]:
        return summarize(self.windows(key, criterion, mode), self.n, self.step_h)


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m lunarsim.comms", description="Summarise an Earth-link file.")
    ap.add_argument("path", nargs="?", default="data/comms/connecting_ridge/earth_link-v1.json")
    ap.add_argument("--mode", default="dte", choices=MODES)
    ap.add_argument("--legs", action="store_true", help="also print every leg")
    a = ap.parse_args(argv)
    el = EarthLink.load(a.path)
    keys = el.points() + (el.legs() if a.legs else [])
    print(f"{'key':22s} " + " ".join(f"{c:>34s}" for c in CRITERIA))
    print(f"{'':22s} " + " ".join(f"{'frac  win_d  gap_h  max_gap_h':>34s}" for _ in CRITERIA))
    for k in keys:
        cells = []
        for c in CRITERIA:
            s = el.summary(k, c, a.mode)
            cells.append(f"{s['fraction']:6.3f} {s['mean_window_h'] / 24:6.2f} {s['mean_gap_h']:6.1f} {s['max_gap_h']:10.1f}")
        print(f"{k:22s} " + " ".join(f"{x:>34s}" for x in cells))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
