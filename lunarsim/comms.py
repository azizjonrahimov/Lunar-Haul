"""Earth-link windows (``lunarsim-earth-link`` v1, research thread R-1 "Earth in sight"): reader and link queries.

The file ``data/comms/<terrain>/earth_link-v1.json`` is written by ``tools/comms/earth_link.py`` from SPICE
(Earth's topocentric direction in MOON_ME) and terrain horizon masks in Earth's wedge (5 m tile near field,
80 m polar LOLA DEM out to 300 km). This module reads it (EarthLink) and holds the engine's opt-in model of the
Scenario field ``comms`` (CommsModel, B-41; rules below).

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
from bisect import bisect_right
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

EARTH_LINK_FORMAT = "lunarsim-earth-link"
EARTH_LINK_VERSION = 1
EARTH_LINK_SAMPLES_FORMAT = "lunarsim-earth-link-samples"   # per route sample windows (earth_link-v1-samples.json)
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
        self._lists: Dict[Tuple[str, str, str], Tuple[List[int], List[int]]] = {}

    @classmethod
    def load(cls, path: str, samples: bool = False) -> "EarthLink":
        """Read the file; samples=True also reads the per-sample file it names (same folder)."""
        import os
        with open(path, encoding="utf-8") as f:
            el = cls(json.load(f))
        if samples:
            el.load_samples(os.path.join(os.path.dirname(os.path.abspath(path)), el.doc["samples_file"]["file"]))
        return el

    # ---- per route sample (earth_link-v1-samples.json.gz: hourly direct windows) --------------------------
    def load_samples(self, path: str) -> None:
        import gzip
        with open(path, "rb") as f:
            raw = f.read()
        doc = json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)
        if doc.get("format") != EARTH_LINK_SAMPLES_FORMAT:
            raise ValueError(f"{path}: not a {EARTH_LINK_SAMPLES_FORMAT} document")
        self.samples = doc
        self._s_step_h = float(doc["time"]["step_min"]) / 60.0
        self._s_cache: Dict[int, np.ndarray] = {}

    def leg_samples(self, leg: str) -> List[int]:
        """Sample indices of a leg in route order (end points included)."""
        return self.samples["legs"][leg]

    def _series(self, sid: int) -> np.ndarray:
        if sid not in self._s_cache:
            self._s_cache[sid] = decode_windows(self.samples["series"][sid])
        return self._s_cache[sid]

    def sample_wait_h(self, sample: int, t_h: float, criterion: str = "any_part", mode: str = "dte",
                      wrap: bool = False) -> float:
        """Hours from t until the sample is linked (0 if it is linked now; inf if never again in the series).
        Sample series are hourly; in mode dte+mast the sample is also linked while it sees the mast and the mast is
        linked (the mast's own 10-min series)."""
        s = self.samples["samples"][sample]
        w = self._series(s["w"][CRITERIA.index(criterion)])
        n_s = int(self.samples["time"]["n"])
        x = t_h / self._s_step_h
        if wrap:
            x %= n_s
        elif not 0 <= x < n_s:
            raise ValueError(f"t = {t_h} h outside the sample series")
        i = int(math.floor(x + 1e-9))
        j = int(np.searchsorted(w[:, 0], i, side="right")) - 1
        if j >= 0 and i < w[j, 1]:
            return 0.0
        best = (w[j + 1, 0] - x) * self._s_step_h if j + 1 < len(w) else math.inf
        if mode == "dte+mast" and s.get("mast_los"):
            up, dt = self.next_change("mast", (x * self._s_step_h) % self.horizon_h if wrap else x * self._s_step_h,
                                      criterion, "dte", wrap)
            best = 0.0 if up else min(best, dt)
        return max(0.0, best)

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
            wins = e["windows"] if key == "mast" else e["windows"][mode]   # the mast has direct windows only
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
        """(linked at t, hours from t until the state changes); inf if it never changes again (with wrap=True the
        series repeats, so only a series with no window at all never changes)."""
        ck = (key, criterion, mode)
        lists = self._lists.get(ck)
        if lists is None:
            w = self.windows(key, criterion, mode)
            lists = self._lists[ck] = (w[:, 0].tolist(), w[:, 1].tolist())
        starts, ends = lists
        x = t_h / self.step_h
        if wrap:
            x %= self.n
        elif not 0 <= x < self.n:
            raise ValueError(f"t = {t_h} h outside the series (0 to {self.horizon_h} h); pass wrap=True to repeat it")
        i = int(x + 1e-9)
        j = bisect_right(starts, i) - 1
        if j >= 0 and i < ends[j]:
            return True, (ends[j] - x) * self.step_h
        if j + 1 < len(starts):
            return False, (starts[j + 1] - x) * self.step_h
        if wrap and starts:
            return False, (self.n - x + starts[0]) * self.step_h
        return False, math.inf

    def summary(self, key: str, criterion: str = "any_part", mode: str = "dte") -> Dict[str, float]:
        return summarize(self.windows(key, criterion, mode), self.n, self.step_h)


# ---------------------------------------------------------------------------------------------------------
# engine model (B-41): the opt-in Scenario field `comms`
# ---------------------------------------------------------------------------------------------------------
# Scenario.comms (None = off; the engine never builds this model and runs unchanged):
#   mode               "always" (no link rule: results identical to comms=None) | "dte" | "dte+relay"
#   criterion          one of CRITERIA (default "any_part")
#   link_series        path to earth_link-v1.json (default DEFAULT_LINK_SERIES; its samples file is read too)
#   relay              {"coverage": p in [0, 1], "gap_model": "parametric", "mean_gap_h": g} for dte+relay
#   mast               {"site": "BASE", "height_m": 10, "range_km": 10} or None (the mast the link file was built for)
#   supervised_policy  "strict" (default) | "strategic"
#   start_year         2028-2031 (the series year engine hour 0 maps to; default 2028), or start_h (hours from
#                      2028-01-01 00:00 UTC); engine times past the series end wrap around it
#   defer_wait_h       a job whose planned blackout wait exceeds this is not committed now (the rover stays free
#                      and dispatch wakes up when the link returns); default DEFAULT_DEFER_WAIT_H; null = commit
#                      whatever the wait (the rover parks with the job until the link comes)
# Rules (Modelled; R-1 note "Experiment design in our engine"):
#   teleop             starts a drive or a load/unload only while the leg (every 100 m route sample) or the site is
#                      linked; if the link drops mid-way the rover parks and resumes at the next link-up
#   supervised strict  as teleop
#   supervised         drives without a link, but each intervention (driving tables' count per leg, or
#     strategic        HAZARD_SUPERVISED_PER_KM without tables) sits at a uniformly drawn route sample and waits for
#                      that sample's next link-up (hourly sample series); planning does not foresee these waits
#   autonomous         unaffected
#   relay              dte+relay: an alternating up/gap process independent of DTE, availability p, exponential gaps
#                      of mean g (default DEFAULT_RELAY_GAP_H), from its own random stream; a point is linked when
#                      DTE or the relay is up (the relay is taken to see every route point)
#   operators          demand counts only while the vehicle's current leg or site is linked: the admission check
#                      at job start sees only the demand linked at that moment, so link-ups can bunch demand;
#                      operator_peak_demand is the largest hourly mean of concurrent linked demand
#   legs missing       pad <-> pad has no route in the link file: linked when both end points are linked
# Random streams of their own (seed-derived), so the demand and operations streams are untouched.
import os as _os

COMMS_MODES = ("always", "dte", "dte+relay")
SUPERVISED_POLICIES = ("strict", "strategic")
COMMS_KEYS = {"mode", "criterion", "link_series", "relay", "mast", "supervised_policy", "start_year", "start_h",
              "defer_wait_h"}
DEFAULT_LINK_SERIES = _os.path.join("data", "comms", "connecting_ridge", "earth_link-v1.json")
SERIES_YEARS = (2028, 2029, 2030, 2031)
# Modelled: one LCRNS reference relay sees the south pole 324 of every 784 min (DRM-0), i.e. a 460 min gap per orbit;
# Esper et al., NTRS 20250003321, https://ntrs.nasa.gov/api/citations/20250003321/downloads/LCRNS_Esper_257.pdf
DEFAULT_RELAY_GAP_H = 460.0 / 60.0
# Assumed: interventions per km for supervised driving when no driving table is set (lunarsim.rover.tables HAZARD_PER_KM)
HAZARD_SUPERVISED_PER_KM = 0.10
# Assumed: operators do not reserve a rover for a job that must wait more than a day for its link; DTE windows are
# predictable from the ephemeris, so the job is planned for the next link-up instead
DEFAULT_DEFER_WAIT_H = 24.0
_EPS = 1e-9


def year_start_h(year: int) -> float:
    """Hours from 2028-01-01 00:00 to 1 January of `year` (2028-2031)."""
    if year not in SERIES_YEARS:
        raise ValueError(f"comms start_year must be one of {SERIES_YEARS}")
    days = {2028: 0, 2029: 366, 2030: 731, 2031: 1096}[year]
    return 24.0 * days


class _Series:
    """A link state in engine hours: next_change(t) -> (up at t, hours until the state changes; inf = never)."""

    def next_change(self, t: float) -> Tuple[bool, float]:
        raise NotImplementedError

    def wait(self, t: float) -> float:
        up, dt = self.next_change(t)
        return 0.0 if up else dt

    def up_until(self, t: float) -> float:
        up, dt = self.next_change(t)
        return t + dt if up else t


class _Windows(_Series):
    def __init__(self, el: "EarthLink", key: str, criterion: str, mode: str, start_h: float):
        self.el, self.key, self.c, self.m, self.t0 = el, key, criterion, mode, start_h
        self._memo: Dict[float, Tuple[bool, float]] = {}

    def next_change(self, t):
        r = self._memo.get(t)
        if r is None:
            if len(self._memo) > 50000:
                self._memo.clear()
            r = self._memo[t] = self.el.next_change(self.key, (self.t0 + t) % self.el.horizon_h, self.c, self.m,
                                                    wrap=True)
        return r


class _Intervals(_Series):
    """Up during sorted disjoint [start, end) intervals (engine hours); down otherwise."""

    def __init__(self, iv: np.ndarray):
        self.iv = iv

    def next_change(self, t):
        iv = self.iv
        j = int(np.searchsorted(iv[:, 0], t, side="right")) - 1 if len(iv) else -1
        if j >= 0 and t < iv[j, 1]:
            return True, float(iv[j, 1] - t)
        return False, (float(iv[j + 1, 0] - t) if j + 1 < len(iv) else math.inf)


class _Or(_Series):
    def __init__(self, a: _Series, b: _Series):
        self.a, self.b = a, b

    def next_change(self, t):
        ua, da = self.a.next_change(t)
        ub, db = self.b.next_change(t)
        if not (ua or ub):
            return False, min(da, db)
        e = t
        for _ in range(100000):                       # the up run ends when both are down
            ua, da = self.a.next_change(e)
            ub, db = self.b.next_change(e)
            ne = max(e + da if ua else e, e + db if ub else e)
            if ne <= e + _EPS or not math.isfinite(ne):
                return True, (ne - t if not math.isfinite(ne) else e - t)
            e = ne
        return True, e - t


class _And(_Series):
    def __init__(self, a: _Series, b: _Series):
        self.a, self.b = a, b

    def next_change(self, t):
        ua, da = self.a.next_change(t)
        ub, db = self.b.next_change(t)
        if ua and ub:
            return True, min(da, db)
        e = t
        for _ in range(100000):                       # wait until both are up at the same time
            ua, da = self.a.next_change(e)
            ub, db = self.b.next_change(e)
            if ua and ub:
                return False, e - t
            step = max(0.0 if ua else da, 0.0 if ub else db)
            if not math.isfinite(step):
                return False, math.inf
            e += step
        return False, math.inf


class CommsModel:
    """The engine's view of Earth links (see the block comment above). Built only when Scenario.comms is set."""

    def __init__(self, cfg: Dict[str, Any], standoff: str, seed: int, horizon_h: float, pads: Sequence[str],
                 find=None):
        unknown = set(cfg) - COMMS_KEYS
        if unknown:
            raise ValueError(f"unknown comms keys {sorted(unknown)}; known: {sorted(COMMS_KEYS)}")
        self.mode = cfg.get("mode", "dte")
        if self.mode not in COMMS_MODES:
            raise ValueError(f"comms mode {self.mode!r} not in {COMMS_MODES}")
        self.criterion = cfg.get("criterion", "any_part")
        if self.criterion not in CRITERIA:
            raise ValueError(f"comms criterion {self.criterion!r} not in {CRITERIA}")
        self.policy = cfg.get("supervised_policy", "strict")
        if self.policy not in SUPERVISED_POLICIES:
            raise ValueError(f"comms supervised_policy {self.policy!r} not in {SUPERVISED_POLICIES}")
        self.start_h = float(cfg["start_h"]) if "start_h" in cfg else year_start_h(int(cfg.get("start_year", 2028)))
        dw = cfg.get("defer_wait_h", DEFAULT_DEFER_WAIT_H)
        self.defer_wait_h = math.inf if dw is None else float(dw)
        self.wakes: set = set()
        self.jobs_deferred = 0
        self.standoff, self.pads, self.horizon_h = str(standoff), set(pads), float(horizon_h)
        self.active = self.mode != "always"
        self.mast = cfg.get("mast")
        self.link_mode = "dte+mast" if self.mast else "dte"
        self.el: Optional[EarthLink] = None
        self.relay: Optional[_Intervals] = None
        self.rng_iv = np.random.default_rng([int(seed), 41, 1])          # intervention positions
        # metrics
        self.wait_h = {"teleop": 0.0, "supervised": 0.0, "autonomous": 0.0}
        self.jobs_delayed = 0
        self.jobs_refused = 0
        self.missing_legs: set = set()
        self.waits: List[list] = []                                       # [veh, t0, t1, where, kind] for the trace
        self.hour_demand = np.zeros(int(math.ceil(horizon_h)) + 2)
        self.op_segs: List[Tuple[float, float, float]] = []               # linked operator demand (active mode)
        self.leg_uses: Dict[str, int] = {}
        self.linked_share_by_leg: Dict[str, float] = {}
        self._series: Dict[Any, _Series] = {}
        self._last: Dict[int, Dict[str, Any]] = {}
        self._km_of = None
        self._never: Dict[Tuple[str, str], bool] = {}
        self.delivered_in_horizon_kg = 0.0
        if not self.active:
            return
        path = cfg.get("link_series") or DEFAULT_LINK_SERIES
        path = find(path) if find else path
        self.el = EarthLink.load(path, samples=True)
        if self.mast:
            fm = self.el.doc.get("mast") or {}
            want = (fm.get("site"), float(fm.get("height_m", -1)), float(fm.get("range_km", -1)))
            got = (self.mast.get("site", "BASE"), float(self.mast.get("height_m", 10.0)), float(self.mast.get("range_km", 10.0)))
            if got != want:
                raise ValueError(f"comms mast {got} differs from the mast the link file was built for {want}")
        if self.mode == "dte+relay":
            r = cfg.get("relay") or {}
            if r.get("gap_model", "parametric") != "parametric":
                raise ValueError("only relay gap_model 'parametric' is implemented")
            p = float(r.get("coverage", 0.8))
            g = float(r.get("mean_gap_h", DEFAULT_RELAY_GAP_H))
            if not 0.0 <= p <= 1.0 or g <= 0:
                raise ValueError("relay coverage must be in [0, 1] and mean_gap_h > 0")
            self.relay = _Intervals(self._relay_intervals(p, g, np.random.default_rng([int(seed), 41, 2])))

    # ---- link series -------------------------------------------------------------------------------------
    def _relay_intervals(self, p: float, g: float, rng) -> np.ndarray:
        if p >= 1.0:
            return np.array([[0.0, math.inf]])
        if p <= 0.0:
            return np.zeros((0, 2))
        up_mean = g * p / (1.0 - p)
        t, up, out = 0.0, bool(rng.random() < p), []
        end = self.horizon_h + 10 * (up_mean + g)
        while t < end:
            d = float(rng.exponential(up_mean if up else g))
            if up:
                out.append([t, t + d])
            t += d
            up = not up
        return np.array(out) if out else np.zeros((0, 2))

    def name(self, site: str) -> str:
        return f"{site}@{self.standoff}" if site in self.pads else site

    def series(self, a: str, b: Optional[str] = None) -> _Series:
        """Link of a leg a -> b (every route sample), or of a site when b is None or b == a."""
        k = (a, b if b != a else None)
        if k not in self._series:
            if k[1] is None:
                s: _Series = _Windows(self.el, self.name(a), self.criterion, self.link_mode, self.start_h)
            else:
                key = f"{self.name(a)}->{self.name(b)}"
                if key in self.el.doc["legs"] and self.el.doc["legs"][key].get("route", True) is not None:
                    s = _Windows(self.el, key, self.criterion, self.link_mode, self.start_h)
                else:
                    self.missing_legs.add(key)
                    s = _And(self.series(a), self.series(b))
            if self.relay is not None:
                s = _Or(s, self.relay)
            self._series[k] = s
        return self._series[k]

    def _sample_wait(self, a: str, b: str, u: float, t: float) -> float:
        """Wait (h) at engine time t for the route sample at fraction u of leg a -> b (relay counts)."""
        key = f"{self.name(a)}->{self.name(b)}"
        try:
            ids = self.el.leg_samples(key)
        except KeyError:
            return self.series(a, b).wait(t)
        sid = ids[min(len(ids) - 1, int(u * len(ids)))]
        w = self.el.sample_wait_h(sid, (self.start_h + t) % self.el.horizon_h, self.criterion, self.link_mode, wrap=True)
        if self.relay is not None and w > 0:
            w = min(w, self.relay.wait(t))
        return w

    def needs_link(self, autonomy: str) -> bool:
        return autonomy == "teleop" or (autonomy == "supervised" and self.policy == "strict")

    # ---- job timelines ------------------------------------------------------------------------------------
    def plan(self, sim, job, t_start: float, realize: bool):
        """sim._job_plan with the link rules applied to every vehicle's segment list; inf duration if a needed
        link never comes (the job cannot be done)."""
        sim._last_segk = {}
        dur, km, km_empty, e_wh, night = sim._job_plan(job, t_start, realize)
        segk = sim._last_segk
        dur_max = 0.0
        any_wait = False
        self._last = {}
        for v in job.vehicles:
            segs = sim._last_segments.get(v.id, [])
            new, waits = self._apply(v, segs, segk.get(v.id), realize)
            if new is None:
                self._last = {}
                return math.inf, km, km_empty, e_wh, night
            planned = sum(w[2] - w[1] for w in waits if w[4] != "intervention")
            if planned > self.defer_wait_h + _EPS:            # not now: plan it for the next link-up
                self.wakes.add(round(min(w[2] for w in waits if w[4] != "intervention"), 4))
                self._last = {}
                if realize:
                    self.jobs_deferred += 1
                return math.inf, km, km_empty, e_wh, night
            sim._last_segments[v.id] = new
            self._last[v.id] = {"waits": waits}
            any_wait = any_wait or bool(waits)
            end = new[-1][3] if new else t_start
            dur_max = max(dur_max, end - t_start)
        return (dur_max if any_wait else dur), km, km_empty, e_wh, night

    def pop_wakes(self, now: float) -> List[float]:
        """Future link-up times at which a deferred job becomes possible (the engine adds WAKE events)."""
        out = sorted(t for t in self.wakes if t > now + _EPS and t < self.horizon_h)
        self._woken = getattr(self, "_woken", set())
        out = [t for t in out if t not in self._woken]
        self._woken.update(out)
        self.wakes.clear()
        return out

    def _apply(self, v, segs, ks, realize):
        need = self.needs_link(v.autonomy)
        strategic = v.autonomy == "supervised" and self.policy == "strategic"
        if not (need or (strategic and realize)):
            return segs, []
        out, waits, shift = [], [], 0.0
        for idx, (a, b, t0, t1, load) in enumerate(segs):
            t0, t1 = t0 + shift, t1 + shift
            dur = t1 - t0
            if dur <= _EPS:
                out.append([a, b, t0, t1, load])
                continue
            if need:
                s = self.series(a, b)
                where = a if a == b else f"{a}->{b}"
                up, dt = s.next_change(t0)
                n_waits = len(waits)
                if not up:                                        # park at a until the link comes up
                    if not math.isfinite(dt):
                        return None, waits
                    out.append([a, a, t0, t0 + dt, load])
                    waits.append([v.id, t0, t0 + dt, where, "start"])
                    t0 += dt
                    up, dt = s.next_change(t0)
                t, rem = t0, dur
                for _ in range(100000):
                    if up:
                        d = min(rem, dt)
                        t += d
                        rem -= d
                        if rem <= _EPS:
                            break
                    else:                                         # the link dropped: park, resume at link-up
                        if not math.isfinite(dt):
                            return None, waits
                        dt = max(dt, _EPS)
                        waits.append([v.id, t, t + dt, where, "midway"])
                        t += dt
                    up, dt = s.next_change(t)
                if len(waits) == n_waits:
                    t = t1                          # no wait in this segment: keep the planned end exactly
                out.append([a, b, t0, t, load])
                shift += (t - t1)
            else:                                                 # strategic: interventions wait at their sample
                if a == b:
                    k = 0
                elif ks is not None and idx < len(ks):            # the driving table's draw for this leg
                    k = int(ks[idx])
                else:                                             # no driving table: draw from the hazard rate
                    km = self._km_of(a, b) if self._km_of else 0.0
                    k = int(self.rng_iv.poisson(HAZARD_SUPERVISED_PER_KM * km))
                extra = 0.0
                if a != b and k > 0:
                    for u in np.sort(self.rng_iv.random(k)):
                        ti = t0 + u * dur + extra
                        w = self._sample_wait(a, b, float(u), ti)
                        if not math.isfinite(w):
                            return None, waits
                        if w > _EPS:
                            waits.append([v.id, ti, ti + w, f"{a}->{b}", "intervention"])
                            extra += w
                out.append([a, b, t0, t1 + extra, load])
                shift += extra
        return out, waits

    def reposition(self, v, a: str, b: str, t0: float, h: float):
        """An empty drive a -> b under the link rule: (segments, waits) or None when the link never comes."""
        return self._apply(v, [[a, b, t0, t0 + h, 0.0]], None, True)

    def book_waits(self, v, waits) -> None:
        """Count waits inside the simulated horizon (the trace keeps them whole)."""
        for w in waits:
            self.wait_h[v.autonomy] = self.wait_h.get(v.autonomy, 0.0) + max(0.0, min(w[2], self.horizon_h) - max(w[1], 0.0))
            self.waits.append([round(x, 4) if isinstance(x, float) else x for x in w])

    def filter_candidates(self, sim, candidates):
        """When every vehicle needs a link, drop items whose delivery leg is never linked at all (no vehicle could
        ever take them; keeps the mechanisms from re-proposing them at every event)."""
        if any(v.alive and not self.needs_link(v.autonomy) for v in sim.vehicles):
            return candidates
        out = []
        for c in candidates:
            k = (c.origin, c.dest)
            if k not in self._never:
                self._never[k] = not math.isfinite(self.series(c.origin, c.dest).wait(0.0))
            if not self._never[k]:
                out.append(c)
        return out

    def note_deliveries(self, items) -> None:
        for c in items:
            if c.t_delivered is not None and c.t_delivered <= self.horizon_h:
                self.delivered_in_horizon_kg += c.mass_kg

    def set_leg_km(self, km_of) -> None:
        """Leg lengths (km) for the strategic hazard draw when there is no driving table."""
        self._km_of = km_of

    # ---- operators, commits, metrics ----------------------------------------------------------------------
    def demand_at(self, t: float) -> float:
        self.op_segs = [s for s in self.op_segs if s[1] > t + _EPS]
        return sum(d for s0, s1, d in self.op_segs if s0 <= t + _EPS)

    def next_demand_drop(self, t: float) -> Optional[float]:
        ends = [s1 for s0, s1, d in self.op_segs if s0 <= t + _EPS < s1]
        return min(ends) if ends else None

    def _log_demand(self, t0: float, t1: float, d: float) -> float:
        """Add demand d over [t0, t1) to the hourly bins; returns demand-hours."""
        if t1 <= t0 or d <= 0:
            return 0.0
        h0, h1 = int(math.floor(t0)), int(math.floor(min(t1, self.horizon_h + 1)))
        for h in range(max(h0, 0), min(h1, len(self.hour_demand) - 1) + 1):
            ov = min(t1, h + 1.0) - max(t0, float(h))
            if ov > 0:
                self.hour_demand[h] += d * ov
        return d * (t1 - t0)

    def log_job_passive(self, t0: float, t1: float, demand: float) -> None:
        """Mode 'always': record operator demand over the whole job (nothing else changes)."""
        self._log_demand(t0, t1, demand)

    def commit(self, sim, job, t0: float, t_end: float) -> float:
        """Book the committed job's waits, linked operator demand and leg use; returns linked demand-hours."""
        delayed = False
        dh = 0.0
        for v in job.vehicles:
            rec = self._last.get(v.id, {"waits": []})
            self.book_waits(v, rec["waits"])
            delayed = delayed or bool(rec["waits"])
            dem = sim.operator_demand(v)
            segs = sim._last_segments.get(v.id, [])
            in_wait = [(w[1], w[2]) for w in rec["waits"] if w[4] in ("start", "midway")]
            for a, b, s0, s1, _ in segs:
                if s1 - s0 <= _EPS or (a == b and any(abs(s0 - w0) < 1e-9 and abs(s1 - w1) < 1e-9 for w0, w1 in in_wait)):
                    continue
                if a != b:
                    key = f"{self.name(a)}->{self.name(b)}"
                    self.leg_uses[key] = self.leg_uses.get(key, 0) + 1
                s = self.series(a, b)
                t = s0
                for _ in range(100000):                           # linked parts of the segment only
                    if t >= s1 - _EPS:
                        break
                    up, dt = s.next_change(t)
                    e = min(s1, t + dt)
                    if up and not any(w0 <= t < w1 for w0, w1 in in_wait):
                        self.op_segs.append((t, e, dem))
                        dh += self._log_demand(t, e, dem)
                    t = e if e > t + _EPS else s1
        if delayed:
            self.jobs_delayed += 1
        return dh

    def finalise(self) -> None:
        """Linked share over the simulated horizon for every leg a job drove."""
        if not self.active:
            return
        for key in self.leg_uses:
            a, b = key.split("->")
            base = lambda s: s.split("@")[0]
            s = self.series(base(a), base(b))
            t, on = 0.0, 0.0
            for _ in range(100000):
                if t >= self.horizon_h - _EPS:
                    break
                up, dt = s.next_change(t)
                e = min(self.horizon_h, t + dt)
                if up:
                    on += e - t
                t = e if e > t + _EPS else self.horizon_h
            self.linked_share_by_leg[key] = on / self.horizon_h

    def summary(self) -> Dict[str, float]:
        uses = sum(self.leg_uses.values())
        share = (sum(self.linked_share_by_leg.get(k, 0.0) * n for k, n in self.leg_uses.items()) / uses
                 if uses and self.linked_share_by_leg else (1.0 if not self.active else float("nan")))
        return {
            "blackout_wait_vehicle_h": sum(self.wait_h.values()),
            "blackout_wait_teleop_h": self.wait_h.get("teleop", 0.0),
            "blackout_wait_supervised_h": self.wait_h.get("supervised", 0.0),
            "blackout_wait_autonomous_h": self.wait_h.get("autonomous", 0.0),
            "blackout_jobs_delayed": self.jobs_delayed,
            "blackout_jobs_refused": self.jobs_refused,
            "blackout_jobs_deferred": self.jobs_deferred,
            "operator_peak_demand": float(self.hour_demand.max()),
            "delivered_kg_in_horizon": self.delivered_in_horizon_kg,
            "linked_share_by_leg_mean": share,
        }


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
