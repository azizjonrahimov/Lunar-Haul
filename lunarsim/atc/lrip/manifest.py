"""LRIP capability manifest (B-93; research note 03 C3): JSON for humans, compact CBOR on the wire, and the matcher
`can_do(task, manifest)` the auction uses to filter bidders.

Compact form (note C3 rules): every key and every enumerated string replaced by its index in the schema's
manifest_registry (indices are never reused); decimals as fixed-point integers x 100 (registry decimal_keys);
version strings "M.m" as M * 256 + m (registry version_keys); unknown keys and strings stay as text, so a reader
skips what it does not know. The owner signs the compact bytes (CAP_MANIFEST is a signed message).
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from . import cbor
from .codec import ROOT, schema

EXAMPLES = os.path.join(ROOT, "data", "atc", "lrip")
MANIFEST_SCHEMA = os.path.join(ROOT, "lunarsim", "schemas", "lrip-manifest-v0.1.schema.json")
MANIFEST_SCHEMA_V02 = os.path.join(ROOT, "lunarsim", "schemas", "lrip-manifest-v0.2.schema.json")


def _reg():
    r = schema()["manifest_registry"]
    if "_k" not in r:
        r["_k"] = {k: i for i, k in enumerate(r["keys"])}
        r["_s"] = {s: i for i, s in enumerate(r["strings"])}
        r["_dec"] = set(r["decimal_keys"])
        r["_ver"] = set(r["version_keys"])
    return r


def _ver_int(s: str) -> int:
    a, b = str(s).split(".")
    return int(a) * 256 + int(b)


def _enc(x: Any, key: Optional[str], r) -> Any:
    if isinstance(x, dict):
        return {r["_k"].get(k, k): _enc(v, k, r) for k, v in x.items()}
    if isinstance(x, list):
        return [_enc(v, key, r) for v in x]
    if isinstance(x, bool) or x is None:
        return x
    if key in r["_ver"] and isinstance(x, str):
        return _ver_int(x)
    if isinstance(x, str):
        # B-119 C9: only the keys the decoder maps back carry registry indices; any other string stays text
        return r["_s"].get(x, x) if key in _STRING_KEYS else x
    if key in r["_dec"]:
        return int(round(float(x) * 100))
    if isinstance(x, float):
        if not x.is_integer():
            raise ValueError(f"manifest: decimal value for key {key!r} not in decimal_keys")
        return int(x)
    return x


def _dec(x: Any, key: Optional[str], r) -> Any:
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            name = r["keys"][k] if isinstance(k, int) and k < len(r["keys"]) else k
            out[name] = _dec(v, name, r)
        return out
    if isinstance(x, list):
        return [_dec(v, key, r) for v in x]
    if isinstance(x, bool) or x is None:
        return x
    if key in r["_ver"] and isinstance(x, int):
        return f"{x // 256}.{x % 256}"
    if key in r["_dec"] and isinstance(x, int):
        return x / 100.0
    if isinstance(x, int) and key in _STRING_KEYS:
        return r["strings"][x] if x < len(r["strings"]) else x
    return x


# keys whose values are enumerated strings (or lists of them) in the registry
_STRING_KEYS = {"class", "band", "std", "sources", "type", "pub", "sub", "name", "interface", "bands", "policy"}


def encode(manifest: Dict[str, Any]) -> bytes:
    """Compact CBOR bytes of a manifest."""
    return cbor.dumps(_enc(manifest, None, _reg()))


def decode(data: bytes) -> Dict[str, Any]:
    return _dec(cbor.loads(data), None, _reg())


def minified_json(manifest: Dict[str, Any]) -> bytes:
    return json.dumps(manifest, separators=(",", ":")).encode()


def example(name: str, version: str = "0.1") -> Dict[str, Any]:
    """'small_rover' or 'hopper' (note 03 C3); version "0.2" (B-100) adds nav.frame, nav.datum and nav.time_scale, the
    sender's declaration of the reference of its positions and time stamps (data/atc/lrip/v0.2/)."""
    d = EXAMPLES if version == "0.1" else os.path.join(EXAMPLES, "v" + version)
    with open(os.path.join(d, f"manifest-{name}.json"), encoding="utf-8") as f:
        return json.load(f)


def _major_minor(v: str):
    a, b = str(v).split(".")
    return int(a), int(b)


def can_do(task: Dict[str, Any], manifest: Optional[Dict[str, Any]]) -> bool:
    """Does the vehicle offer the task's capability? task = {"capability": name, "ver": "M.m", "params": {key: value
    or list}}. The manifest must list the capability with the same major version and a minor version at least the
    task's; each task parameter must fall inside the manifest's {"max": ...} / {"min": ...} bounds, and a list
    parameter must be a subset of the manifest's list. A manifest without the parameter cannot do the task. Unknown
    capabilities and parameters in the manifest are ignored (note 03 C3)."""
    if manifest is None:
        return False
    tmaj, tmin = _major_minor(task.get("ver", "1.0"))
    for cap in manifest.get("capabilities", []):
        if cap.get("name") != task["capability"]:
            continue
        cmaj, cmin = _major_minor(cap.get("ver", "1.0"))
        if cmaj != tmaj or cmin < tmin:
            continue
        ok = True
        for k, v in (task.get("params") or {}).items():
            spec = (cap.get("params") or {}).get(k)
            if spec is None:
                ok = False
                break
            if isinstance(v, (list, tuple)):
                if not isinstance(spec, list) or not set(v) <= set(spec):
                    ok = False
                    break
                continue
            if isinstance(spec, dict):
                if "max" in spec and float(v) > float(spec["max"]) + 1e-9:
                    ok = False
                if "min" in spec and float(v) < float(spec["min"]) - 1e-9:
                    ok = False
            elif spec != v:
                ok = False
            if not ok:
                break
        if ok:
            return True
    return False


def from_vehicle_class(vid: int, owner: str, cls) -> Dict[str, Any]:
    """A manifest generated from the engine's vehicle class (catalogue): carrying vehicles offer transport.carry up
    to their capacity (hoppers transport.hop); used by the auction's opt-in capability filter."""
    name = cls.name
    hop = name.startswith("HOPPER")
    cap = {"name": "transport.hop" if hop else "transport.carry", "ver": "1.0",
           "params": {"mass_kg": {"max": float(cls.capacity_kg)}}}
    return {"lrip": "0.1", "rev": 1, "vehicle": {"id": int(vid), "owner": str(owner), "model": name,
                                                  "class": "hopper" if hop else "cargo_rover"},
            "capabilities": [cap]}


def task_for_bundle(v, bundle) -> Dict[str, Any]:
    """The capability a bundle of cargo asks of vehicle v: carrying (or hopping) the bundle's total mass."""
    hop = v.cls.name.startswith("HOPPER")
    return {"capability": "transport.hop" if hop else "transport.carry", "ver": "1.0",
            "params": {"mass_kg": float(sum(c.mass_kg for c in bundle))}}
