"""Phase 5 vehicle classes (B-71): the sourced table lunarsim/atc/vehicles-p5.json as engine VehicleClass objects.

lunarsim.entities.VEHICLE_CLASSES and lunarsim/catalog-v1.json are unchanged; the engine resolves a fleet class id
there first and here second (lunarsim.entities.vehicle_class). The extra fields default to "no limit", so a class
without them behaves like any v2 class:
- mass_kg: vehicle mass (team-lift rule "krawciw", energy);
- flies: straight-line hops between sites at speed_kmh, no driving tables, no roads (hoppers);
- km_budget: total km before the vehicle retires (hoppers: propellant);
- active_h: hours after deployment (t = 0) before the vehicle retires (hoppers: days of hopping);
- km_per_day: driving budget per 24 h when remotely operated (Phase-1 LTVs: 6 km/day).
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..entities import VehicleClass

TABLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vehicles-p5.json")
ENGINE_KEYS = ("capacity_kg", "speed_kmh", "empty_speed_mult", "energy_wh_per_km", "battery_wh", "charge_kw",
               "night_ops", "can_team_lift", "unit_cost_musd", "life_hours", "mtbf_h", "mttr_h", "load_h",
               "unload_h", "life_years")


@dataclass
class AtcVehicleClass(VehicleClass):
    mass_kg: float = 0.0
    flies: bool = False
    km_budget: float = math.inf
    active_h: float = math.inf
    km_per_day: float = math.inf


_cache: Dict[str, Any] = {}


def load_table(path: Optional[str] = None) -> Dict[str, Any]:
    p = path or TABLE
    if p not in _cache:
        with open(p, encoding="utf-8") as f:
            _cache[p] = json.load(f)
    return _cache[p]


def build(cid: str, overrides: Optional[Dict[str, Any]] = None, doc: Optional[Dict[str, Any]] = None) -> AtcVehicleClass:
    """The class `cid` from the table, with parameter overrides (sweeps) applied by name."""
    d = doc or load_table()
    P = {k: q["value"] for k, q in d["classes"][cid]["params"].items()}
    P.update(overrides or {})
    kw = {k: (bool(P[k]) if k in ("night_ops", "can_team_lift") else float(P[k])) for k in ENGINE_KEYS}
    return AtcVehicleClass(cid, **kw, mass_kg=float(P.get("mass_kg", 0.0)),
                           flies=bool(d["classes"][cid].get("flies", False)),
                           km_budget=float(P.get("km_budget", math.inf)),
                           active_h=float(P["active_days"]) * 24.0 if "active_days" in P else math.inf,
                           km_per_day=float(P.get("km_per_day", math.inf)))


def p5_classes(doc: Optional[Dict[str, Any]] = None) -> Dict[str, AtcVehicleClass]:
    d = doc or load_table()
    return {cid: build(cid, doc=d) for cid in d["classes"]}


P5_CLASSES = p5_classes()


def validate(doc: Optional[Dict[str, Any]] = None) -> List[str]:
    """Every parameter a quantity with a flag, a confidence and a source; Assumed values carry a sweep where the
    task asks (unknown battery kWh); the modelled energy and battery follow their rules."""
    d = doc or load_table()
    errs: List[str] = []
    rule = d["rules"]["energy_wh_per_km"]["value"]
    for cid, c in d["classes"].items():
        P = c["params"]
        for k in ENGINE_KEYS:
            if k not in P:
                errs.append(f"{cid}: missing {k}")
        for k, q in P.items():
            for f in ("value", "unit", "flag", "confidence", "source"):
                if f not in q:
                    errs.append(f"{cid}.{k}: missing {f}")
            if q.get("flag") not in ("Spec", "Modelled", "Assumed", "Measured"):
                errs.append(f"{cid}.{k}: bad flag {q.get('flag')!r}")
            if not str(q.get("source", "")).strip():
                errs.append(f"{cid}.{k}: empty source")
            if q.get("flag") == "Assumed" and q.get("confidence") != "-":
                errs.append(f"{cid}.{k}: an Assumed value has confidence '-'")
            if "sweep" in q and not (q["sweep"][0] <= q["value"] <= q["sweep"][1]):
                errs.append(f"{cid}.{k}: value outside its sweep")
        if P["energy_wh_per_km"]["flag"] == "Modelled" and P["energy_wh_per_km"]["value"] > 0:
            want = rule * P["mass_kg"]["value"]
            if abs(P["energy_wh_per_km"]["value"] - want) > 0.06:
                errs.append(f"{cid}.energy_wh_per_km: {P['energy_wh_per_km']['value']} != traction rule {want:.2f}")
        if "range_km_per_charge" in P:
            want = P["range_km_per_charge"]["value"] * P["energy_wh_per_km"]["value"]
            if abs(P["battery_wh"]["value"] - want) > 1.0:
                errs.append(f"{cid}.battery_wh: {P['battery_wh']['value']} != range x energy {want:.0f}")
            if "sweep" not in P["battery_wh"]:
                errs.append(f"{cid}.battery_wh: an unknown battery needs a sweep")
    return errs
