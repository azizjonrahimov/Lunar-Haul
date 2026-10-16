"""Phase-3 models the engine uses when the opt-in Scenario fields are set (PLAN §5.3-§5.5).

    terrain          site positions from data/terrain/<site>/sites.json (pads per standoff)
    autonomy_model   leg time / energy / interventions sampled from driving tables (lunarsim-driving v1)
    landing_model    per-landing outcome sampled from a Monte Carlo table (lunarsim-landing-outcomes v1)
    plume            keep-out windows around each landing, shelters, staging at the boundary

With every field None the engine never builds any of these and runs the v2 code unchanged.

Mapping between the DES and the tables (Modelled; stated in the paper):
- the driving tables describe a 1.6 t LTV-class rover; leg time for another vehicle class is scaled by the
  class's nominal speed relative to LTV, divided by the class's empty-speed multiplier when empty and by the team
  speed multiplier for team lifts; leg energy is scaled by the class's Wh/km relative to the table rover's flat
  134 Wh/km and by the v2 load factor (1 + 0.6 load / capacity);
- lighting bin from the simulated sun: azimuth = 360 (t mod synodic month) / synodic month in grid degrees,
  nearest of 0/90/180/270, "night" whenever the scenario's night is on;
- RTT bin: the table RTT nearest to the scenario's round-trip time (ties go to the lower value).
"""
from __future__ import annotations

import json
import math
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from .scenario import LUNAR_CYCLE_H

DEFAULT_TERRAIN_ROOT = os.path.join("data", "terrain")
DEFAULT_DRIVING = os.path.join("data", "driving", "driving-v1.json")
DEFAULT_POLICY_DIR = os.path.join("data", "policies")
REF_CLASS = "LTV"
OFFPAD_SPEED_FACTOR = 0.5        # Assumed: speed over unprepared terrain between an off-pad lander and the pad
OFFPAD_ENERGY_FACTOR = 2.0       # Assumed: energy per km over the same rough ground
INTERVENTION_RECOVERY_S = 300.0  # as lunarsim.rover.physics.INTERVENTION["recovery_s"] (Assumed)
LIGHT_BINS = (0.0, 90.0, 180.0, 270.0)
_JSON_CACHE: Dict[str, Any] = {}      # read-only documents shared by every Simulation in the process
_TERRAIN_CACHE: Dict[str, Any] = {}
_LOS_CACHE: Dict[Tuple[str, str, str, str], bool] = {}


def _load_json(path: str):
    key = os.path.abspath(path)
    st = os.stat(key)
    ck = (key, st.st_mtime_ns, st.st_size)
    if ck not in _JSON_CACHE:
        with open(key, encoding="utf-8") as f:
            _JSON_CACHE[ck] = json.load(f)
    return _JSON_CACHE[ck]


def _find(path: str) -> str:
    """Resolve a data path relative to the working directory or the repository root."""
    if os.path.exists(path):
        return path
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    alt = os.path.join(here, path)
    return alt if os.path.exists(alt) else path


# ---------------------------------------------------------------------------------------------------------
class SiteMap:
    """World site name -> position (km, local frame of the terrain pack or the v2 world graph)."""

    def __init__(self, world, terrain: Optional[str], standoff: Optional[str], root: str = DEFAULT_TERRAIN_ROOT):
        self.terrain_id = terrain
        self.standoff = str(standoff) if standoff is not None else "1"
        self.xy_km: Dict[str, Tuple[float, float]] = {}
        self.los_blocked: Dict[Tuple[str, str], bool] = {}
        self._terrain = None
        if terrain:
            path = _find(os.path.join(root, terrain, "sites.json"))
            doc = _load_json(path)
            self.sites_doc = doc
            for s in doc["sites"]:
                self.xy_km[s["id"]] = (s["xy_m"][0] / 1000.0, s["xy_m"][1] / 1000.0)
            pads = doc.get("pads", {})
            if self.standoff not in pads:
                raise ValueError(f"pad_standoff_km {self.standoff!r} not in {terrain} sites.json pads {sorted(pads)}")
            for pid, xy in pads[self.standoff].items():
                self.xy_km[pid] = (xy[0] / 1000.0, xy[1] / 1000.0)
            self.root = root
        else:
            self.sites_doc = None
            for name, s in world.sites.items():
                self.xy_km[name] = (s.x_km, s.y_km)
        missing = [n for n in world.names if n not in self.xy_km]
        if missing:
            raise ValueError(f"terrain {terrain} sites.json lacks world sites {missing}")

    def dist_km(self, a: str, b: str) -> float:
        (xa, ya), (xb, yb) = self.xy_km[a], self.xy_km[b]
        return math.hypot(xa - xb, ya - yb)

    def line_of_sight_blocked(self, a: str, b: str) -> Optional[bool]:
        """True if the terrain blocks the line of sight between two sites (10 m source height at a, 2 m at b);
        None without terrain."""
        if not self.terrain_id:
            return None
        key = (self.terrain_id, self.standoff, a, b)
        if key not in _LOS_CACHE:
            tkey = os.path.abspath(os.path.join(_find(self.root), self.terrain_id))
            if tkey not in _TERRAIN_CACHE:
                from .terrain import Terrain
                _TERRAIN_CACHE[tkey] = Terrain(self.terrain_id, _find(self.root))
            pa = [1000.0 * v for v in self.xy_km[a]]
            pb = [1000.0 * v for v in self.xy_km[b]]
            _LOS_CACHE[key] = _TERRAIN_CACHE[tkey].los_clearance_m(pa, pb, h_a=10.0, h_b=2.0) <= 0
        return _LOS_CACHE[key]


# ---------------------------------------------------------------------------------------------------------
class DrivingModel:
    """Leg lookups in a lunarsim-driving v1 table. Pads are looked up as '<PAD>@<standoff>'."""

    def __init__(self, path_or_name: str, standoff: str, vehicle_classes):
        path = DEFAULT_DRIVING if path_or_name in ("driving-v1", None) else path_or_name
        self.doc = _load_json(_find(path))
        if self.doc.get("format") != "lunarsim-driving":
            raise ValueError(f"{path}: not a lunarsim-driving table")
        self.legs = self.doc["legs"]
        self.standoff = standoff
        self.rtts = sorted(float(r) for r in self.doc.get("rtt_s", ["0", "4", "6", "8"]))
        ref = vehicle_classes[REF_CLASS]
        self.ref_speed = ref.speed_kmh
        mass = self.doc.get("model", {}).get("mass_kg", 1600.0)
        crr = self.doc.get("model", {}).get("c_rr_eff", 0.1764)
        self.table_wh_per_km = crr * mass * 1.62 / 3.6 / 0.95       # flat-ground Wh/km of the table rover
        self._cache: Dict[Tuple, Dict[str, Any]] = {}

    def _name(self, site: str, pads) -> str:
        return f"{site}@{self.standoff}" if site in pads else site

    def rtt_bin(self, rtt_s: float) -> str:
        best = min(self.rtts, key=lambda r: (abs(r - rtt_s), r))
        return f"{best:g}"

    @staticmethod
    def light_bin(t_h: float, night: bool) -> str:
        if night:
            return "night"
        az = 360.0 * (t_h % LUNAR_CYCLE_H) / LUNAR_CYCLE_H
        best = min(LIGHT_BINS, key=lambda b: min(abs(az - b), 360.0 - abs(az - b)))
        return f"{best:g}"

    def entry(self, a: str, b: str, pads, autonomy: str, rtt: str, light: str) -> Optional[Dict[str, Any]]:
        key = (a, b, autonomy, rtt, light)
        if key in self._cache:
            return self._cache[key]
        leg = self.legs.get(f"{self._name(a, pads)}->{self._name(b, pads)}")
        out = None
        if leg is not None:
            by_rtt = leg["autonomy"][autonomy]["rtt_s"]
            r = rtt if rtt in by_rtt else min(by_rtt, key=lambda k: abs(float(k) - float(rtt)))
            lights = by_rtt[r]["lighting"]
            lk = light if light in lights else ("night" if light == "night" and "night" in lights else next(iter(lights)))
            e = lights[lk]
            route = leg["route"].get(lk) or next(iter(leg["route"].values()))
            t, en = e["time_h"], e["energy_kwh"]
            out = {"mu_t": t["mu"], "s_t": t["sigma"], "mean_h": math.exp(t["mu"] + 0.5 * t["sigma"] ** 2),
                   "mu_e": en["mu"], "s_e": en["sigma"], "mean_kwh": math.exp(en["mu"] + 0.5 * en["sigma"] ** 2),
                   "lam": e["interventions"]["lambda"], "km": route["length_m"] / 1000.0}
        self._cache[key] = out
        return out


# ---------------------------------------------------------------------------------------------------------
class LandingModel:
    """Samples per-landing outcomes from lunarsim-landing-outcomes v1 tables, one per lander class.

    spec: {policy: "classical" | "<id with {cls}>" | {cls: id}, sigma_scale, pad_radius_m, failure_policy, dir}"""

    def __init__(self, spec: Dict[str, Any]):
        self.spec = dict(spec)
        self.sigma_scale = float(spec.get("sigma_scale", 1.0))
        self.pad_radius_m = float(spec.get("pad_radius_m", 50.0))
        fp = spec.get("failure_policy", "lose")
        if fp != "lose" and not (isinstance(fp, dict) and "recover_h" in fp):
            raise ValueError("landing_model.failure_policy must be 'lose' or {'recover_h': hours}")
        self.failure_policy = fp
        self.dir = spec.get("dir", DEFAULT_POLICY_DIR)
        self.policy = spec.get("policy", "classical")
        self._tables: Dict[str, List[Dict[str, Any]]] = {}

    def _file(self, cls: str) -> str:
        p = self.policy
        if isinstance(p, dict):
            pid = p[cls]
        elif p == "classical":
            pid = f"classical_{cls}"
        else:
            pid = p.format(cls=cls)
        return _find(os.path.join(self.dir, f"outcomes_{pid}.json"))

    def episodes(self, cls: str) -> List[Dict[str, Any]]:
        if cls not in self._tables:
            path = self._file(cls)
            doc = _load_json(path)
            if doc.get("format") != "lunarsim-landing-outcomes":
                raise ValueError(f"{path}: not a landing-outcomes table")
            self._tables[cls] = doc["episodes"]
        return self._tables[cls]

    def sample(self, cls: str, rng: np.random.Generator) -> Dict[str, Any]:
        eps = self.episodes(cls)
        rec = eps[int(rng.integers(len(eps)))]
        mx, my = (self.sigma_scale * float(v) for v in rec["miss_m"])
        miss = math.hypot(mx, my)
        kind = rec.get("failure_kind")
        failed = kind in ("velocity", "tilt", "sensor", "timeout", "lost")
        offpad = (not failed) and miss > self.pad_radius_m
        return {"miss_m": [mx, my], "miss_r_m": miss, "tilt_deg": rec.get("tilt_deg"),
                "prop_residual_kg": None, "prop_used_kg": rec.get("prop_used_kg"),
                "ok": (not failed) and not offpad, "failed": failed, "offpad": offpad,
                "failure_kind": kind if failed else ("offpad" if offpad else None)}


# ---------------------------------------------------------------------------------------------------------
class PlumeModel:
    """Keep-out windows [t_land - T, t_land + T] at each landing's pad, radius R; shelters per pad."""

    def __init__(self, spec: Dict[str, Any], sites: SiteMap, world):
        self.R = float(spec["keepout_km"])
        self.T = float(spec["standdown_h"])
        # B-12c: after the window an evacuated vehicle that is still idle at the shelter drives back to where it
        # was (default). With return_after False it stays at the shelter, which acts as unplanned staging.
        self.return_after = bool(spec.get("return_after", True))
        self.evacuated: Dict[str, List[Tuple[int, str]]] = {}      # pad -> [(vehicle id, pre-evacuation site)]
        self.windows: List[Tuple[float, float, str]] = []
        self.sites, self.world = sites, world
        self._shelter: Dict[str, str] = {}
        self._staging: Dict[str, Optional[str]] = {}

    def add(self, t_land: float, pad: str):
        self.windows.append((t_land - self.T, t_land + self.T, pad))

    def active(self, pad: str, t: float) -> Optional[Tuple[float, float, str]]:
        for w in self.windows:
            if w[2] == pad and w[0] <= t < w[1]:
                return w
        return None

    def overlapping(self, pad: str, t0: float, t1: float) -> Optional[Tuple[float, float, str]]:
        """The earliest window at the pad that overlaps [t0, t1]."""
        best = None
        for w in self.windows:
            if w[2] == pad and w[0] < t1 and t0 < w[1] and (best is None or w[0] < best[0]):
                best = w
        return best

    def upcoming(self, pad: str, t: float, within_h: float) -> bool:
        return any(w[2] == pad and t - 1e-9 <= w[1] and w[0] <= t + within_h for w in self.windows)

    def inside(self, site: str, pad: str) -> bool:
        return self.sites.dist_km(site, pad) < self.R

    def staging_site(self, pad: str) -> Optional[str]:
        """Where marketplace anticipatory staging waits for a landing at a pad with an upcoming window (B-12e): the
        nearest site outside the keep-out radius R, i.e. the keep-out boundary. The shelter is itself outside R, so
        it is used only when it is the nearest such site. (Staging at the shelter regardless, as before, sent the
        staged vehicle far away when R was small and added ~0.9 h of urgent delay at R 0.2-0.5 km, T 6 h.)"""
        if pad not in self._staging:
            outside = [s for s in self.world.names if s != pad and not self.inside(s, pad)]
            self._staging[pad] = min(outside, key=lambda s: self.sites.dist_km(s, pad)) if outside else None
        return self._staging[pad]

    def shelter(self, pad: str) -> Optional[str]:
        """Nearest site outside R whose line of sight to the pad is blocked by terrain; else the nearest outside R."""
        if pad not in self._shelter:
            outside = [s for s in self.world.names if s != pad and not self.inside(s, pad)]
            outside.sort(key=lambda s: self.sites.dist_km(s, pad))
            blocked = [s for s in outside if self.sites.line_of_sight_blocked(pad, s)]
            self._shelter[pad] = (blocked or outside or [None])[0]
        return self._shelter[pad]
