"""Scenario serialisation: Scenario <-> JSON (lunarsim-scenario v1), plus the named scenario library.

A scenario file is plain JSON so that the same inputs can be loaded by the
Python engine, the browser port and any other tool. Schema:
lunarsim/schemas/scenario-v1.schema.json. Two forms are accepted, told apart by
the ``form`` key (missing: a file with ``phase`` is compact, anything else is full).

Full form (canonical; what save_scenario writes) - every Scenario field:

    {
      "format": "lunarsim-scenario", "version": 1, "form": "full",
      "name": "P2-four-vehicles",
      "landings_per_year": {"CLPS": 4, "MK1": 3, "LARGE": 1},
      "cargo_owners": ["NASA", "NASA", "NASA", "NASA", "CoA", "CoA", "CoB", "CoC"],
      "bulk_flows": [{"origin": "CONSTR", "dest": "BASE", "tonnes_per_year": 300, "lot_kg": 1000}],
      "fleet": [["NASA", "LTV", "supervised", "A"], ["CoA", "HAUL", "supervised", "A"]],
      "night_fraction": 0.15, "n_operators": 3
    }

Compact form (what the web page exports) - a phase plus the page's controls:

    {
      "format": "lunarsim-scenario", "version": 1, "form": "compact",
      "name": "lunarsim-live", "phase": "P2", "bulk_t_per_year": 500,
      "fleet": [{"owner": "NASA", "cls": "LTV", "autonomy": "supervised", "std": "A"}],
      "night_fraction": 0.15, "rtt_s": 5.0, "n_operators": 3, "other_duty_share": 0.3,
      "mtbf_mult": 1.0, "common_standard_share": 1.0,
      "marketplace": {"bundling": true, "consolidate": true, "team_lift": true, ...}
    }

The header keys are optional on input (files written before v1 have none).

Key order never matters: in particular `landings_per_year` is drawn in the canonical lander order (CLPS, MK1,
LARGE; lunarsim.scenario.sample_landings), so reordering its keys gives the same simulated year for the same seed.
"""
from __future__ import annotations

import dataclasses
import json
import os
import warnings
from typing import Any, Dict, List, Tuple

from .scenario import Scenario, BulkFlow

SCENARIO_FORMAT = "lunarsim-scenario"
SCENARIO_VERSION = 1
HEADER_KEYS = ("format", "version", "form")
PHASE3_FIELDS = ("terrain", "pad_standoff_km", "landing_model", "plume", "autonomy_model", "comms",
                 "illumination", "p5")   # + Phase 4 comms, illumination; Phase 5 p5

COMPACT_KEYS = {"format", "version", "form", "name", "phase", "bulk_t_per_year", "fleet", "night_fraction",
                "rtt_s", "n_operators", "other_duty_share", "mtbf_mult", "common_standard_share", "marketplace"}

# compact `marketplace` flag -> keyword argument of dispatch.marketplace (and the engine, for team_lift).
# The page exports the Python names already; the short names are the PLAN §4.2 spelling. Both are accepted.
MARKETPLACE_FLAGS = {
    "bundling": "bundling", "consolidate": "consolidate", "anticipate": "anticipate",
    "backhaul": "backhaul", "priority": "priority",
    "team": "team_lift", "team_lift": "team_lift",
    "night": "night_aware", "night_aware": "night_aware",
}


def scenario_to_dict(sc: Scenario) -> Dict[str, Any]:
    """Full form v1, header first."""
    d: Dict[str, Any] = {"format": SCENARIO_FORMAT, "version": SCENARIO_VERSION, "form": "full"}
    d.update(dataclasses.asdict(sc))
    d["bulk_flows"] = [dataclasses.asdict(b) for b in sc.bulk_flows]
    d["fleet"] = [list(v) for v in sc.fleet]
    d["vot_usd_per_h"] = {str(k): v for k, v in sc.vot_usd_per_h.items()}
    for k in PHASE3_FIELDS:                 # opt-in fields are written only when set (v2 files stay unchanged)
        if d.get(k) is None:
            d.pop(k, None)
    return d


def scenario_form(d: Dict[str, Any]) -> str:
    """'full' or 'compact' (explicit `form` key, else: has `phase` => compact)."""
    form = d.get("form")
    if form is None:
        return "compact" if "phase" in d else "full"
    if form not in ("full", "compact"):
        raise ValueError(f"unknown scenario form {form!r} (expected 'full' or 'compact')")
    return form


def _check_header(d: Dict[str, Any]) -> None:
    if "format" in d and d["format"] != SCENARIO_FORMAT:
        raise ValueError(f"not a scenario file: format is {d['format']!r}, expected '{SCENARIO_FORMAT}'")
    if "version" in d and d["version"] != SCENARIO_VERSION:
        raise ValueError(f"unsupported scenario version {d['version']!r} (this reader knows {SCENARIO_VERSION})")


def _fleet_entry(v) -> Tuple[str, str, str, str]:
    if isinstance(v, dict):
        return (v["owner"], v["cls"], v.get("autonomy", "supervised"), v.get("std", "A"))
    v = list(v)
    return tuple(v if len(v) >= 4 else v + ["A"])  # type: ignore[return-value]


def scenario_from_dict(d: Dict[str, Any]) -> Scenario:
    """Scenario from either form. Compact `marketplace` flags are dropped here; use
    scenario_from_dict_ex to get them as mechanism kwargs."""
    return scenario_from_dict_ex(d)[0]


def scenario_from_dict_ex(d: Dict[str, Any]) -> Tuple[Scenario, Dict[str, Any]]:
    """(Scenario, marketplace mechanism kwargs) from a full- or compact-form dict."""
    _check_header(d)
    if scenario_form(d) == "compact":
        return _from_compact(d)
    d = {k: v for k, v in d.items() if k not in HEADER_KEYS}
    d["bulk_flows"] = [BulkFlow(**b) if isinstance(b, dict) else BulkFlow(*b) for b in d.get("bulk_flows", [])]
    d["fleet"] = [_fleet_entry(v) for v in d.get("fleet", [])]
    if "vot_usd_per_h" in d:
        d["vot_usd_per_h"] = {int(k): float(v) for k, v in d["vot_usd_per_h"].items()}
    known = {f.name for f in dataclasses.fields(Scenario)}
    unknown = set(d) - known
    if unknown:
        raise ValueError(f"unknown scenario fields: {sorted(unknown)}")
    return Scenario(**d), {}


def _phases() -> Dict[str, Scenario]:
    from .phases import PHASES
    return PHASES


def split_rtt(rtt_s: float, ground_delay_s: float = 2.4) -> Tuple[float, float]:
    """(one_way_latency_s, ground_delay_s) such that the engine's
    ``2 * one_way_latency_s + ground_delay_s`` equals ``rtt_s`` bit for bit.

    The page has one control, the round trip ``rtt`` in seconds, which web/sim.js uses
    directly (``sc.rtt`` in speedMult/handlingMult). Python keeps the two parts and
    sums them in Simulation.__init__. Rule: keep the phase's ground delay (2.4 s) and
    put the rest in the light time, ``one_way = (rtt - 2.4) / 2``; if rtt < 2.4 s the
    ground delay is 0 and ``one_way = rtt / 2``. Where floating point makes
    ``2*one_way + 2.4`` miss rtt by one ulp (e.g. 6.8 s), ground_delay_s is set to
    ``rtt - 2*one_way`` instead (it differs from 2.4 by < 1e-15 s), so both engines
    see the identical rtt.
    """
    rtt_s = float(rtt_s)
    if rtt_s < ground_delay_s:
        return rtt_s / 2, 0.0
    ow = (rtt_s - ground_delay_s) / 2
    if 2 * ow + ground_delay_s != rtt_s:
        ground_delay_s = rtt_s - 2 * ow
    return ow, ground_delay_s


def marketplace_kwargs(flags: Dict[str, Any]) -> Dict[str, Any]:
    """Compact `marketplace` flags -> dispatch.marketplace kwargs (see MARKETPLACE_FLAGS).
    Flags with no Python equivalent are dropped with a warning."""
    out: Dict[str, Any] = {}
    unknown = []
    for k, v in (flags or {}).items():
        if k in MARKETPLACE_FLAGS:
            out[MARKETPLACE_FLAGS[k]] = bool(v)
        else:
            unknown.append(k)
    if unknown:
        warnings.warn(f"marketplace flags with no Python equivalent ignored: {sorted(unknown)}")
    return out


def _from_compact(d: Dict[str, Any]) -> Tuple[Scenario, Dict[str, Any]]:
    """Expand the page's compact form exactly as web/sim.js makeScenario() does:

    - start from lunarsim.phases.PHASES[phase] (landings, cargo owners, bulk routes,
      fleet, n_operators); missing controls keep the phase value;
    - bulk_t_per_year B: every phase flow gets tonnes_per_year * (B / max(1e-9, sum of phase
      tonnes)), owner NASA, the phase lot size and priority; B == 0 means no bulk flows;
    - rtt_s -> (one_way_latency_s, ground_delay_s) via split_rtt();
    - night_fraction, n_operators, other_duty_share, mtbf_mult, common_standard_share copy
      across; everything makeScenario fixes (horizon 8760 h, night speed 0.6, fan-out 4,
      duty block 48 h, costs, VOT) equals the Scenario defaults the phases use.
    """
    unknown = set(d) - COMPACT_KEYS
    if unknown:
        raise ValueError(f"unknown scenario fields: {sorted(unknown)}")
    phases = _phases()
    phase = d.get("phase")
    if phase not in phases:
        raise ValueError(f"unknown phase {phase!r}. Known: {', '.join(phases)}")
    base = phases[phase]
    kw: Dict[str, Any] = {"name": d.get("name", phase)}
    if "bulk_t_per_year" in d:
        total = sum(b.tonnes_per_year for b in base.bulk_flows)
        bulk_t = float(d["bulk_t_per_year"])
        scale = bulk_t / max(1e-9, total)
        kw["bulk_flows"] = [BulkFlow(b.origin, b.dest, b.tonnes_per_year * scale, lot_kg=b.lot_kg,
                                     owner="NASA", priority=b.priority) for b in base.bulk_flows] if bulk_t > 0 else []
    if "fleet" in d:
        kw["fleet"] = [_fleet_entry(v) for v in d["fleet"]]
    if "rtt_s" in d:
        kw["one_way_latency_s"], kw["ground_delay_s"] = split_rtt(d["rtt_s"], base.ground_delay_s)
    for k in ("night_fraction", "other_duty_share", "mtbf_mult", "common_standard_share"):
        if k in d:
            kw[k] = float(d[k])
    if "n_operators" in d:
        kw["n_operators"] = int(d["n_operators"])
    return base.with_(**kw), marketplace_kwargs(d.get("marketplace", {}))


def save_scenario(sc: Scenario, path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scenario_to_dict(sc), f, indent=2)


def load_scenario(path: str) -> Scenario:
    return load_scenario_ex(path)[0]


def load_scenario_ex(path: str) -> Tuple[Scenario, Dict[str, Any]]:
    """(Scenario, mechanism kwargs). The kwargs are the compact form's `marketplace`
    flags translated by marketplace_kwargs(); {} for full-form files."""
    with open(path, encoding="utf-8") as f:
        return scenario_from_dict_ex(json.load(f))


def library() -> Dict[str, Scenario]:
    """Named scenarios used in the paper (phases and the fleet-size variants)."""
    from .phases import PHASES, FLEETS
    out: Dict[str, Scenario] = {}
    for ph, sc in PHASES.items():
        out[f"{ph}-default"] = sc
    for n, fleet in FLEETS.items():
        out[f"P2-{n}-vehicles"] = PHASES["P2"].with_(name=f"P2-{n}-vehicles", fleet=fleet, n_operators=max(2, n // 2))
    return out
