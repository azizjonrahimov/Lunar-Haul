"""Vehicle and site catalogue (``lunarsim-catalog`` v1): one sourced file for the engine and the 3D models.

``lunarsim/catalog-v1.json`` is the source of truth for every vehicle number shown on screen: real
dimensions for the procedural 3D kit, plus the capacities, speeds and descent constants the engine uses.
The engine does not read it (results stay byte-identical); instead ``engine_mismatches()`` compares the two,
and ``tests/test_catalog.py`` fails if they ever drift apart.

Every number is a *quantity*: ``{"value": ..., "unit": ..., "flag": ..., "source": ...}`` with flag
Spec | Measured | Assumed | Modelled (the paper's convention). Spec and Measured need a URL in ``source``;
Assumed and Modelled may give the reasoning instead. The JSON Schema is
``schemas/catalog-v1.schema.json``; ``validate()`` is the dependency-free structural check (like formats.py).

    from lunarsim import catalog
    catalog.get("MK1")["dims"]["height_m"]["value"]   # 8.05
    catalog.value("LTV", "capacity_kg")              # 1500
    python -m lunarsim.catalog                       # validate, check the engine link, list Assumed values
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Iterator, List, Optional, Tuple

CATALOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog-v1.json")
CATALOG_FORMAT = "lunarsim-catalog"
CATALOG_VERSION = 1

FLAGS = ("Spec", "Measured", "Assumed", "Modelled")
KINDS = ("lander", "rover", "base", "reference")
PLUME_CLASSES = ("hydrolox", "methalox", "hypergolic", "none")
STATUSES = ("flown", "built", "in_development", "concept")
# dimension keys a kind may use (only those that apply are present)
DIM_KEYS = ("height_m", "diameter_m", "length_m", "width_m", "leg_count", "leg_span_m", "wheel_count",
            "wheel_d_m", "wheelbase_m", "track_m", "deck_height_m", "ground_clearance_m",
            "berm_height_m", "berm_crest_m", "berm_slope_deg", "berm_base_m", "berm_radius_m",
            "array_width_m", "array_height_m")
COUNT_KEYS = ("leg_count", "wheel_count")
QUANTITY_KEYS = ("value", "unit", "flag", "source")
# top-level quantities an entry may carry besides dims (and the lander-only descent block)
ENTRY_QUANTITIES = ("mass_kg", "capacity_kg", "max_item_kg", "speed_kmh", "night_ops", "power_kw")
GATE_KEYS = ("m_gate_kg", "prop_gate_kg", "t_max_n", "t_min_n", "isp_s")

_CACHE: Dict[str, Dict[str, Any]] = {}


def load(path: Optional[str] = None) -> Dict[str, Any]:
    """Return the catalogue document (cached per path). Raises ValueError if it does not validate."""
    p = os.path.abspath(path or CATALOG_PATH)
    if p not in _CACHE:
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        errs = validate(doc)
        if errs:
            raise ValueError(f"{p}: {len(errs)} catalogue error(s): " + "; ".join(errs[:10]))
        _CACHE[p] = doc
    return _CACHE[p]


def entries(kind: Optional[str] = None, doc: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """All entries in file order, optionally only one kind."""
    d = doc or load()
    return [e for e in d["entries"] if kind is None or e["kind"] == kind]


def get(entry_id: str, doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The entry with this id; KeyError if there is none."""
    for e in (doc or load())["entries"]:
        if e["id"] == entry_id:
            return e
    raise KeyError(f"no catalogue entry {entry_id!r}")


def quantity(entry_id: str, path: str, doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """The quantity object at a dotted path, e.g. quantity("MK1", "dims.height_m")."""
    node: Any = get(entry_id, doc)
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(f"{entry_id}: no {path!r}")
        node = node[part]
    if not _is_quantity(node):
        raise KeyError(f"{entry_id}.{path} is not a quantity")
    return node


def value(entry_id: str, path: str, doc: Optional[Dict[str, Any]] = None):
    """The bare value at a dotted path, e.g. value("LTV", "capacity_kg") -> 1500."""
    return quantity(entry_id, path, doc)["value"]


def iter_quantities(doc: Optional[Dict[str, Any]] = None) -> Iterator[Tuple[str, str, Dict[str, Any]]]:
    """Yield (entry id, dotted path, quantity) for every quantity in the catalogue, in file order."""
    def walk(node, path):
        if _is_quantity(node):
            yield path, node
        elif isinstance(node, dict):
            for k, v in node.items():
                yield from walk(v, f"{path}.{k}" if path else k)
    for e in (doc or load())["entries"]:
        for path, q in walk(e, ""):
            yield e["id"], path, q


def flagged(flag: str, doc: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str, Dict[str, Any]]]:
    """Every quantity carrying this flag, e.g. flagged("Assumed")."""
    return [(i, p, q) for i, p, q in iter_quantities(doc) if q["flag"] == flag]


# ---------------------------------------------------------------------------------------------------------
# structural validation (no jsonschema dependency; returns every problem at once)

def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _is_quantity(x) -> bool:
    return isinstance(x, dict) and "value" in x and "flag" in x


def _has_url(s: str) -> bool:
    return "http://" in s or "https://" in s


def _check_quantity(errs: List[str], where: str, q, *, count: bool = False, boolean: bool = False) -> None:
    if not isinstance(q, dict):
        errs.append(f"{where}: expected a quantity object {{value, unit, flag, source}}, got {q!r}"[:200])
        return
    missing = [k for k in QUANTITY_KEYS if k not in q]
    if missing:
        errs.append(f"{where}: quantity missing {missing}")
        return
    extra = sorted(set(q) - set(QUANTITY_KEYS) - {"note"})
    if extra:
        errs.append(f"{where}: unknown quantity keys {extra}")
    v = q["value"]
    if boolean:
        if not isinstance(v, bool):
            errs.append(f"{where}: value must be true/false, got {v!r}")
    elif count:
        if not (isinstance(v, int) and not isinstance(v, bool) and v >= 0):
            errs.append(f"{where}: value must be a non-negative integer, got {v!r}")
    elif not (_is_num(v) and v >= 0):
        errs.append(f"{where}: value must be a non-negative number, got {v!r}")
    if not isinstance(q["unit"], str):
        errs.append(f"{where}: unit must be a string")
    if q["flag"] not in FLAGS:
        errs.append(f"{where}: flag {q['flag']!r} not in {FLAGS}")
    src = q["source"]
    if not (isinstance(src, str) and src.strip()):
        errs.append(f"{where}: source must be a non-empty string")
    elif q["flag"] in ("Spec", "Measured") and not _has_url(src):
        errs.append(f"{where}: a {q['flag']} value needs a URL in its source")


def _bare_numbers(errs: List[str], where: str, node) -> None:
    """Any number outside a quantity object is unsourced."""
    if _is_quantity(node):
        return
    if _is_num(node):
        errs.append(f"{where}: bare number {node!r} (every number must be a quantity with flag and source)")
    elif isinstance(node, dict):
        for k, v in node.items():
            _bare_numbers(errs, f"{where}.{k}", v)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            _bare_numbers(errs, f"{where}[{i}]", v)


def validate(doc) -> List[str]:
    """Structural check of a catalogue document; [] means valid."""
    errs: List[str] = []
    if not isinstance(doc, dict):
        return ["catalogue must be a JSON object"]
    if doc.get("format") != CATALOG_FORMAT:
        errs.append(f"format must be {CATALOG_FORMAT!r}")
    if doc.get("version") != CATALOG_VERSION:
        errs.append(f"version must be {CATALOG_VERSION}")
    materials = doc.get("materials")
    if not isinstance(materials, dict) or not materials:
        errs.append("materials must be a non-empty object (tag -> appearance)")
        materials = {}
    for tag, m in materials.items():
        w = f"materials.{tag}"
        if not isinstance(m, dict) or not isinstance(m.get("description"), str):
            errs.append(f"{w}: needs a description")
            continue
        for k in ("base_color_linear", "metalness", "roughness"):
            if k not in m:
                errs.append(f"{w}: missing {k}")
        if "base_color_linear" in m:
            q = m["base_color_linear"]
            if not (isinstance(q, dict) and isinstance(q.get("value"), list) and len(q["value"]) == 3
                    and all(_is_num(c) and 0 <= c <= 1 for c in q["value"])):
                errs.append(f"{w}.base_color_linear: value must be [r, g, b] in 0..1")
            elif q.get("flag") not in FLAGS or not str(q.get("source", "")).strip() or "unit" not in q:
                errs.append(f"{w}.base_color_linear: needs unit, flag and source")
        for k in ("metalness", "roughness"):
            if k in m:
                _check_quantity(errs, f"{w}.{k}", m[k])
                if _is_quantity(m[k]) and _is_num(m[k]["value"]) and m[k]["value"] > 1:
                    errs.append(f"{w}.{k}: value must be in 0..1")
    ents = doc.get("entries")
    if not isinstance(ents, list) or not ents:
        return errs + ["entries must be a non-empty list"]
    seen = set()
    for i, e in enumerate(ents):
        where = f"entries[{i}]"
        if not isinstance(e, dict):
            errs.append(f"{where}: must be an object")
            continue
        eid = e.get("id")
        if not (isinstance(eid, str) and eid):
            errs.append(f"{where}: id must be a non-empty string")
        elif eid in seen:
            errs.append(f"{where}: duplicate id {eid!r}")
        else:
            seen.add(eid)
            where = f"{eid}"
        kind = e.get("kind")
        if kind not in KINDS:
            errs.append(f"{where}: kind {kind!r} not in {KINDS}")
        if not isinstance(e.get("name"), str):
            errs.append(f"{where}: name must be a string")
        ref = e.get("reference_vehicle")
        if not (isinstance(ref, dict) and isinstance(ref.get("name"), str) and _has_url(str(ref.get("url", "")))):
            errs.append(f"{where}: reference_vehicle needs a name and a URL")
        elif ref.get("status") not in STATUSES:
            errs.append(f"{where}: reference_vehicle.status {ref.get('status')!r} not in {STATUSES}")
        if not isinstance(e.get("representative"), bool):
            errs.append(f"{where}: representative must be true/false")
        if e.get("plume_class") not in PLUME_CLASSES:
            errs.append(f"{where}: plume_class {e.get('plume_class')!r} not in {PLUME_CLASSES}")
        if not isinstance(e.get("propellant"), str):
            errs.append(f"{where}: propellant must be a string ('none' for unpowered/electric)")
        if kind in ("lander",) and e.get("plume_class") == "none":
            errs.append(f"{where}: a lander needs a plume_class")
        mats = e.get("materials")
        if not (isinstance(mats, list) and mats and all(isinstance(m, str) for m in mats)):
            errs.append(f"{where}: materials must be a non-empty list of tags")
        else:
            unknown = [m for m in mats if m not in materials]
            if unknown:
                errs.append(f"{where}: unknown material tags {unknown}")
        dims = e.get("dims")
        if not isinstance(dims, dict) or not dims:
            errs.append(f"{where}: dims must be a non-empty object")
        else:
            for k, q in dims.items():
                if k not in DIM_KEYS:
                    errs.append(f"{where}: unknown dims key {k!r}")
                    continue
                _check_quantity(errs, f"{where}.dims.{k}", q, count=k in COUNT_KEYS)
        for k in ENTRY_QUANTITIES:
            if k in e:
                _check_quantity(errs, f"{where}.{k}", e[k], boolean=(k == "night_ops"))
        if kind == "lander":
            gate = e.get("gate")
            if not isinstance(gate, dict):
                errs.append(f"{where}: a lander needs a gate block {GATE_KEYS}")
            else:
                for k in GATE_KEYS:
                    if k not in gate:
                        errs.append(f"{where}: gate missing {k}")
                    else:
                        _check_quantity(errs, f"{where}.gate.{k}", gate[k])
            for k in ("capacity_kg", "max_item_kg"):
                if k not in e:
                    errs.append(f"{where}: a lander needs {k}")
        if kind == "rover":
            for k in ("capacity_kg", "speed_kmh", "night_ops"):
                if k not in e:
                    errs.append(f"{where}: a rover needs {k}")
        if "engine_class" in e and not isinstance(e["engine_class"], str):
            errs.append(f"{where}: engine_class must be a string")
        known = {"id", "kind", "name", "reference_vehicle", "representative", "representative_note",
                 "engine_class", "dims", "propellant", "plume_class", "materials", "gate", "notes"}
        unknown = sorted(set(e) - known - set(ENTRY_QUANTITIES))
        if unknown:
            errs.append(f"{where}: unknown keys {unknown}")
        _bare_numbers(errs, where, {k: v for k, v in e.items() if k != "reference_vehicle"})
    return errs


# ---------------------------------------------------------------------------------------------------------
# the engine link: the catalogue must agree with the constants the engine actually runs on

def engine_mismatches(doc: Optional[Dict[str, Any]] = None) -> List[str]:
    """Differences between the catalogue and the engine constants ([] = in agreement).

    Rovers: capacity_kg, speed_kmh, night_ops vs lunarsim.entities.VEHICLE_CLASSES.
    Landers: capacity_kg / max_item_kg vs lunarsim.scenario.LANDER_TYPES (upper payload bound, largest item),
    and the gate block (values and flags) vs lunarsim.lander.classes.CLASSES.
    """
    from .entities import VEHICLE_CLASSES
    from .scenario import LANDER_TYPES
    from .lander.classes import CLASSES

    d = doc or load()
    out: List[str] = []

    def cmp(where, cat, eng):
        if cat != eng:
            out.append(f"{where}: catalogue {cat!r} != engine {eng!r}")

    for e in entries("rover", d):
        cls = e.get("engine_class", e["id"])
        if cls not in VEHICLE_CLASSES:
            out.append(f"{e['id']}: engine class {cls!r} not in VEHICLE_CLASSES")
            continue
        vc = VEHICLE_CLASSES[cls]
        cmp(f"{e['id']}.capacity_kg", e["capacity_kg"]["value"], vc.capacity_kg)
        cmp(f"{e['id']}.speed_kmh", e["speed_kmh"]["value"], vc.speed_kmh)
        cmp(f"{e['id']}.night_ops", e["night_ops"]["value"], vc.night_ops)
    for e in entries("lander", d):
        cls = e.get("engine_class", e["id"])
        if cls not in LANDER_TYPES or cls not in CLASSES:
            out.append(f"{e['id']}: engine class {cls!r} missing from LANDER_TYPES or lander.classes")
            continue
        lt, lc = LANDER_TYPES[cls], CLASSES[cls]
        cmp(f"{e['id']}.capacity_kg", e["capacity_kg"]["value"], lt.payload_kg[1])
        cmp(f"{e['id']}.max_item_kg", e["max_item_kg"]["value"], lt.max_item_kg)
        for k in GATE_KEYS:
            cmp(f"{e['id']}.gate.{k}", e["gate"][k]["value"], getattr(lc, k))
            cmp(f"{e['id']}.gate.{k}.flag", e["gate"][k]["flag"], lc.flags.get(k))
    for cls in VEHICLE_CLASSES:
        if not any(e.get("engine_class", e["id"]) == cls for e in entries("rover", d)):
            out.append(f"engine rover class {cls!r} has no catalogue entry")
    for cls in LANDER_TYPES:
        if not any(e.get("engine_class", e["id"]) == cls for e in entries("lander", d)):
            out.append(f"engine lander class {cls!r} has no catalogue entry")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m lunarsim.catalog",
                                 description="Validate the vehicle catalogue, check it against the engine, list flags.")
    ap.add_argument("--path", default=None, help="catalogue file (default: the bundled catalog-v1.json)")
    ap.add_argument("--flag", default="Assumed", choices=FLAGS, help="list the quantities with this flag")
    a = ap.parse_args(argv)
    with open(a.path or CATALOG_PATH, encoding="utf-8") as f:
        doc = json.load(f)
    errs = validate(doc)
    for m in errs:
        print("ERROR", m)
    if errs:
        return 1
    mism = engine_mismatches(doc)
    for m in mism:
        print("ENGINE", m)
    counts = {fl: len(flagged(fl, doc)) for fl in FLAGS}
    n = sum(counts.values())
    print(f"{CATALOG_FORMAT} v{doc['version']}: {len(doc['entries'])} entries, {n} quantities "
          + ", ".join(f"{fl} {c}" for fl, c in counts.items())
          + f"; engine link {'OK' if not mism else 'MISMATCH'}")
    print(f"-- {a.flag} --")
    for i, p, q in flagged(a.flag, doc):
        print(f"{i}.{p} = {q['value']} {q['unit']}: {q['source']}")
    return 1 if mism else 0


if __name__ == "__main__":
    raise SystemExit(main())
