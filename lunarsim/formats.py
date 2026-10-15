"""Interchange formats shared by the Python engine and the browser port.

The JSON Schemas in ``lunarsim/schemas/`` are the documentation; the functions here
are small dependency-free structural validators that return a list of problems
(empty list = valid), so callers can report every error at once.

    lunarsim-trace v1      validate_trace(d)      schemas/trace-v1.schema.json
    lunarsim-scenario v1   validate_scenario(d)   schemas/scenario-v1.schema.json
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Tuple

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas")

TRACE_FORMAT = "lunarsim-trace"
TRACE_VERSION = 1
TRACE_CARGO_COLUMNS = ["id", "owner", "mass_kg", "origin", "dest", "t_ready", "t_picked",
                       "t_delivered", "priority", "cls", "stranded"]

# expected type per known cargo column: "int", "num", "str", "num?" (number or null), "flag" (0/1)
_CARGO_TYPES = {"id": "int", "owner": "str", "mass_kg": "num", "origin": "str", "dest": "str",
                "t_ready": "num", "t_picked": "num?", "t_delivered": "num?", "priority": "int",
                "cls": "str", "stranded": "flag", "t_landed": "num?"}


def load_schema(name: str) -> Dict[str, Any]:
    """Return a bundled schema, e.g. load_schema("trace-v1")."""
    with open(os.path.join(SCHEMA_DIR, f"{name}.schema.json"), encoding="utf-8") as f:
        return json.load(f)


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _check(kind: str, x) -> bool:
    if kind == "int":
        return _is_int(x)
    if kind == "num":
        return _is_num(x)
    if kind == "num?":
        return x is None or _is_num(x)
    if kind == "str":
        return isinstance(x, str)
    if kind == "flag":
        return _is_int(x) and x in (0, 1)
    return True


def _tuple(errs: List[str], where: str, row, kinds: List[str]) -> None:
    if not isinstance(row, list) or len(row) != len(kinds):
        errs.append(f"{where}: expected a list of {len(kinds)}, got {row!r}"[:200])
        return
    for i, (k, x) in enumerate(zip(kinds, row)):
        if not _check(k, x):
            errs.append(f"{where}[{i}]: expected {k}, got {x!r}"[:200])


def validate_trace(d: Any, max_errors: int = 50) -> List[str]:
    """Structural check of a lunarsim-trace v1 document. Returns a list of problems.

    A document without a ``format`` key is a legacy Python trace and is checked as v1.
    """
    errs: List[str] = []
    if not isinstance(d, dict):
        return ["trace: expected a JSON object"]
    if "format" in d and d["format"] != TRACE_FORMAT:
        errs.append(f"format: expected '{TRACE_FORMAT}', got {d['format']!r}")
    if "version" in d and d["version"] != TRACE_VERSION:
        errs.append(f"version: unsupported version {d['version']!r} (this reader knows {TRACE_VERSION})")
    if "engine" in d and d["engine"] not in ("python", "js"):
        errs.append(f"engine: expected 'python' or 'js', got {d['engine']!r}")
    for k in ("scenario", "mechanism"):
        if k in d and not isinstance(d[k], str):
            errs.append(f"{k}: expected string")
    if "seed" in d and not _is_int(d["seed"]):
        errs.append("seed: expected integer")
    for k in ("horizon_h", "nights", "landings", "vehicles", "jobs", "cargo"):
        if k not in d:
            errs.append(f"missing required key '{k}'")
    if errs:
        return errs
    if not _is_num(d["horizon_h"]) or d["horizon_h"] <= 0:
        errs.append("horizon_h: expected a positive number")

    if "world" in d:
        w = d["world"]
        if not isinstance(w, dict) or not isinstance(w.get("sites"), list) or not isinstance(w.get("edges"), list):
            errs.append("world: expected an object with 'sites' and 'edges' lists")
        else:
            for i, s in enumerate(w["sites"]):
                if not (isinstance(s, dict) and isinstance(s.get("name"), str) and _is_num(s.get("x")) and _is_num(s.get("y"))):
                    errs.append(f"world.sites[{i}]: expected {{name, x, y}}")
            for i, e in enumerate(w["edges"]):
                if not (isinstance(e, dict) and isinstance(e.get("a"), str) and isinstance(e.get("b"), str) and _is_num(e.get("dist"))):
                    errs.append(f"world.edges[{i}]: expected {{a, b, dist}}")

    for name, kinds in (("nights", ["num", "num"]), ("landings", ["num", "str", "str"])):
        if not isinstance(d[name], list):
            errs.append(f"{name}: expected a list")
            continue
        for i, row in enumerate(d[name]):
            _tuple(errs, f"{name}[{i}]", row, kinds)

    if not isinstance(d["vehicles"], list):
        errs.append("vehicles: expected a list")
    else:
        for i, v in enumerate(d["vehicles"]):
            if not isinstance(v, dict):
                errs.append(f"vehicles[{i}]: expected an object")
                continue
            for k, kind in (("id", "int"), ("owner", "str"), ("cls", "str"), ("capacity", "num")):
                if not _check(kind, v.get(k)):
                    errs.append(f"vehicles[{i}].{k}: expected {kind}, got {v.get(k)!r}")
            if "night_ops" in v and not isinstance(v["night_ops"], bool):
                errs.append(f"vehicles[{i}].night_ops: expected boolean")

    if not isinstance(d["jobs"], list):
        errs.append("jobs: expected a list")
    else:
        for i, j in enumerate(d["jobs"]):
            if len(errs) >= max_errors:
                break
            where = f"jobs[{i}]"
            if not isinstance(j, dict):
                errs.append(f"{where}: expected an object")
                continue
            for k, kind in (("kind", "str"), ("veh", "int"), ("t0", "num"), ("t1", "num")):
                if not _check(kind, j.get(k)):
                    errs.append(f"{where}.{k}: expected {kind}, got {j.get(k)!r}")
            if "team" in j and not (isinstance(j["team"], list) and all(_is_int(x) for x in j["team"])):
                errs.append(f"{where}.team: expected a list of integers")
            if not isinstance(j.get("segments"), list):
                errs.append(f"{where}.segments: expected a list")
            else:
                for s, seg in enumerate(j["segments"]):
                    _tuple(errs, f"{where}.segments[{s}]", seg, ["str", "str", "num", "num", "num"])
            if "items" in j:
                if not isinstance(j["items"], list):
                    errs.append(f"{where}.items: expected a list")
                else:
                    for s, it in enumerate(j["items"]):
                        _tuple(errs, f"{where}.items[{s}]", it, ["int", "num", "int", "str", "str"])

    cols = d.get("cargo_columns", TRACE_CARGO_COLUMNS)
    if not (isinstance(cols, list) and all(isinstance(c, str) for c in cols)):
        errs.append("cargo_columns: expected a list of strings")
    elif len(set(cols)) != len(cols):
        errs.append("cargo_columns: duplicate column names")
    elif cols[:len(TRACE_CARGO_COLUMNS)] != TRACE_CARGO_COLUMNS:
        errs.append(f"cargo_columns: must start with the v1 columns {TRACE_CARGO_COLUMNS}")
    elif not isinstance(d["cargo"], list):
        errs.append("cargo: expected a list")
    else:
        kinds = [_CARGO_TYPES.get(c, "any") for c in cols]
        for i, row in enumerate(d["cargo"]):
            if len(errs) >= max_errors:
                break
            _tuple(errs, f"cargo[{i}]", row, kinds)

    if "summary" in d:
        sm = d["summary"]
        if not isinstance(sm, dict):
            errs.append("summary: expected an object")
        else:
            for k, v in sm.items():
                if not (v is None or _is_num(v)):
                    errs.append(f"summary.{k}: expected number or null, got {v!r}")
    return errs[:max_errors]


# ---------------------------------------------------------------------------
# lunarsim-scenario v1
# ---------------------------------------------------------------------------
_CLASSES = ("LTV", "HAUL", "MICRO")
_AUTONOMY = ("teleop", "supervised", "autonomous")


def _fleet_errors(errs: List[str], fleet) -> None:
    if not isinstance(fleet, list):
        errs.append("fleet: expected a list")
        return
    for i, v in enumerate(fleet):
        if isinstance(v, dict):
            extra = set(v) - {"owner", "cls", "autonomy", "std"}
            if extra:
                errs.append(f"fleet[{i}]: unknown keys {sorted(extra)}")
            owner, cls, aut, std = v.get("owner"), v.get("cls"), v.get("autonomy", "supervised"), v.get("std", "A")
        elif isinstance(v, list) and len(v) in (3, 4):
            owner, cls, aut = v[:3]
            std = v[3] if len(v) == 4 else "A"
        else:
            errs.append(f"fleet[{i}]: expected [owner, cls, autonomy, std] or {{owner, cls, autonomy, std}}")
            continue
        if not isinstance(owner, str):
            errs.append(f"fleet[{i}].owner: expected string")
        if cls not in _CLASSES:
            errs.append(f"fleet[{i}].cls: expected one of {_CLASSES}, got {cls!r}")
        if aut not in _AUTONOMY:
            errs.append(f"fleet[{i}].autonomy: expected one of {_AUTONOMY}, got {aut!r}")
        if not isinstance(std, str):
            errs.append(f"fleet[{i}].std: expected string")


def _range(errs: List[str], d: Dict[str, Any], k: str, lo=None, hi=None, integer=False) -> None:
    if k not in d:
        return
    x = d[k]
    if not (_is_int(x) if integer else _is_num(x)):
        errs.append(f"{k}: expected {'integer' if integer else 'number'}, got {x!r}")
    elif (lo is not None and x < lo) or (hi is not None and x > hi):
        errs.append(f"{k}: {x} outside [{lo}, {hi}]")


def validate_scenario(d: Any) -> List[str]:
    """Structural check of a lunarsim-scenario v1 document (either form). Returns a list of problems.

    Beyond types and ranges it runs the real loader (lunarsim.config.scenario_from_dict_ex), so
    anything Python would refuse to load is reported too.
    """
    from .config import SCENARIO_FORMAT, SCENARIO_VERSION, COMPACT_KEYS, MARKETPLACE_FLAGS, scenario_form, scenario_from_dict_ex
    import dataclasses
    from .scenario import Scenario
    if not isinstance(d, dict):
        return ["scenario: expected a JSON object"]
    errs: List[str] = []
    if "format" in d and d["format"] != SCENARIO_FORMAT:
        errs.append(f"format: expected '{SCENARIO_FORMAT}', got {d['format']!r}")
    if "version" in d and d["version"] != SCENARIO_VERSION:
        errs.append(f"version: unsupported version {d['version']!r} (this reader knows {SCENARIO_VERSION})")
    try:
        form = scenario_form(d)
    except ValueError as e:
        return errs + [str(e)]
    if "name" in d and not isinstance(d["name"], str):
        errs.append("name: expected string")
    if "fleet" in d:
        _fleet_errors(errs, d["fleet"])
    for k in ("night_fraction", "other_duty_share", "common_standard_share"):
        _range(errs, d, k, 0, 1)
    _range(errs, d, "n_operators", 0, None, integer=True)
    _range(errs, d, "mtbf_mult", 0, None)
    if form == "compact":
        unknown = set(d) - COMPACT_KEYS
        if unknown:
            errs.append(f"unknown compact-form fields: {sorted(unknown)}")
        if d.get("phase") not in ("P1", "P2", "P3"):
            errs.append(f"phase: expected P1, P2 or P3, got {d.get('phase')!r}")
        _range(errs, d, "bulk_t_per_year", 0, None)
        _range(errs, d, "rtt_s", 0, None)
        mp = d.get("marketplace", {})
        if not isinstance(mp, dict):
            errs.append("marketplace: expected an object")
        else:
            for k, v in mp.items():
                if k not in MARKETPLACE_FLAGS:
                    errs.append(f"marketplace.{k}: no such option (known: {sorted(MARKETPLACE_FLAGS)})")
                elif not isinstance(v, bool):
                    errs.append(f"marketplace.{k}: expected boolean")
    else:
        known = {f.name for f in dataclasses.fields(Scenario)} | {"format", "version", "form"}
        unknown = set(d) - known
        if unknown:
            errs.append(f"unknown scenario fields: {sorted(unknown)}")
        _range(errs, d, "horizon_h", 0, None)
        for k in ("one_way_latency_s", "ground_delay_s"):
            _range(errs, d, k, 0, None)
        if "landings_per_year" in d and not (isinstance(d["landings_per_year"], dict)
                                             and all(_is_num(v) for v in d["landings_per_year"].values())):
            errs.append("landings_per_year: expected an object of numbers")
        bf = d.get("bulk_flows", [])
        if not isinstance(bf, list):
            errs.append("bulk_flows: expected a list")
        else:
            for i, b in enumerate(bf):
                if not (isinstance(b, dict) and isinstance(b.get("origin"), str) and isinstance(b.get("dest"), str)
                        and _is_num(b.get("tonnes_per_year"))):
                    errs.append(f"bulk_flows[{i}]: expected {{origin, dest, tonnes_per_year, ...}}")
    if not errs:
        try:
            import warnings
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                scenario_from_dict_ex(d)
        except Exception as e:  # anything the loader refuses
            errs.append(f"does not load: {type(e).__name__}: {e}")
    return errs


# ---------------------------------------------------------------------------
# files of either kind (lunarsim validate)
# ---------------------------------------------------------------------------
def detect_kind(d: Any) -> str:
    """'trace' or 'scenario': by the `format` key, else a legacy file with `jobs` and `cargo` is a trace."""
    from .config import SCENARIO_FORMAT
    if isinstance(d, dict) and "format" in d:
        if d["format"] == TRACE_FORMAT:
            return "trace"
        if d["format"] == SCENARIO_FORMAT:
            return "scenario"
        raise ValueError(f"unknown format {d['format']!r} (expected '{TRACE_FORMAT}' or '{SCENARIO_FORMAT}')")
    return "trace" if isinstance(d, dict) and "jobs" in d and "cargo" in d else "scenario"


def validate_file(path: str) -> Tuple[str, bool, List[str]]:
    """(kind, legacy, errors) for a trace or scenario JSON file. kind is '?' if it cannot be read."""
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
        return "?", False, [f"cannot read JSON: {e}"]
    try:
        kind = detect_kind(d)
    except ValueError as e:
        return "?", False, [str(e)]
    legacy = "format" not in d
    errs = validate_trace(d) if kind == "trace" else validate_scenario(d)
    return kind, legacy, errs
