"""Guided stories (B-35): data/stories/<id>.json, ordered steps whose every number is sourced.

Prose (the story's title and summary; each step's title, text and visual) carries numbers only as {{r:key}}
placeholders. Each key is declared in the story's `numbers` with its source:

    {"table": "results/table_E20.csv", "where": {"term": "standoff", ...}, "column": "pct_per_unit"}
        one row of a results table (exactly one row must match; "a ± b" cells give a, or b with "part": "pm")
    {"json": "results/E20_fit.json", "path": ["siting", "impacts_per_landing_at_standoffs", "0.5"]}
    {"catalog": "LTV", "quantity": "capacity_kg"}          a catalogue quantity (its own flag and source)
    {"derive": "pct_change", "of": ["a", "b"]}            diff b - a, ratio b / a, pct_change 100 (b - a) / a

then optionally "transform" (exp_pct: 100 (e^v - 1); neg; abs), "scale", "digits", "unit", "flag", "note".

check() fails on an undeclared placeholder, a declared number nothing uses, a source that does not resolve (in a
published story; in a draft a missing results file only leaves the number pending), any digit typed into prose
(years and ALLOWED_TOKENS excepted), and highlight ids or scene samples that do not exist. resolve() returns the story
with each number's value, text, flag and source, and every prose field filled in as <field>_plain, for the site.

    python -m lunarsim.stories check                       # every data/stories/*.json
    python -m lunarsim.stories build                       # and write data/stories/resolved/<id>.json + index.json
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import hashlib
import io
import json
import math
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORIES = os.path.join("data", "stories")
RESOLVED = os.path.join(STORIES, "resolved")

PLACEHOLDER = re.compile(r"\{\{r:([A-Za-z0-9_]+)\}\}")
YEAR = re.compile(r"^(19|20)\d\d$")
ALLOWED_TOKENS = {"2D", "3D", "P1", "P2", "P3"}      # labels with digits, not quantities
DIGIT_TOKEN = re.compile(r"[A-Za-z0-9.,]*[0-9][A-Za-z0-9.,]*")
PROSE = ("title", "summary")
STEP_PROSE = ("title", "text", "visual")
FLAG_RANK = {"Spec": 0, "Measured": 1, "Modelled": 2, "Assumed": 3}   # a derived number takes its weakest input's
MINUS = "−"
PENDING_TEXT = "(pending)"
LABEL_MAX = 40                                       # a number's optional display label (B-53)


class StoryError(Exception):
    pass


class Pending(Exception):
    """The source file does not exist yet (a draft may wait for it)."""


# ---------------------------------------------------------------------------------------------------------
# prose
# ---------------------------------------------------------------------------------------------------------
def placeholders(text: str) -> List[str]:
    return PLACEHOLDER.findall(text or "")


def typed_digits(text: str) -> List[str]:
    """Digits typed into prose outside the placeholders: every token with a digit that is not a year or allowed."""
    out = []
    for tok in DIGIT_TOKEN.findall(PLACEHOLDER.sub(" ", text or "")):
        t = tok.strip(".,")
        if YEAR.match(t) or t in ALLOWED_TOKENS:
            continue
        out.append(t)
    return out


def _prose_fields(doc: Dict[str, Any]):
    for f in PROSE:
        if f in doc:
            yield f, doc[f]
    for i, st in enumerate(doc.get("steps", [])):
        for f in STEP_PROSE:
            if f in st:
                yield f"steps[{i}].{f}", st[f]


# ---------------------------------------------------------------------------------------------------------
# sources
# ---------------------------------------------------------------------------------------------------------
class Sources:
    """Reads and caches the files numbers come from (under `root`), remembering each one's sha256."""

    def __init__(self, root: str = ROOT):
        self.root = root
        self._cache: Dict[str, Any] = {}
        self.used: Dict[str, str] = {}

    def _raw(self, rel: str) -> bytes:
        p = os.path.join(self.root, rel)
        if not os.path.isfile(p):
            raise Pending(f"{rel} does not exist yet")
        with open(p, "rb") as f:
            raw = f.read()
        if raw[:2] == b"\x1f\x8b":
            self.used[rel.replace(os.sep, "/")] = hashlib.sha256(raw).hexdigest()
            return gzip.decompress(raw)
        # text: hash with LF line ends, so a CRLF working copy (git stores eol=lf) gives the same sha as CI
        raw = raw.replace(b"\r\n", b"\n")
        self.used[rel.replace(os.sep, "/")] = hashlib.sha256(raw).hexdigest()
        return raw

    def table(self, rel: str) -> List[Dict[str, str]]:
        if rel not in self._cache:
            text = self._raw(rel).decode("utf-8-sig")
            self._cache[rel] = list(csv.DictReader(io.StringIO(text)))
        return self._cache[rel]

    def json(self, rel: str) -> Any:
        if rel not in self._cache:
            self._cache[rel] = json.loads(self._raw(rel))
        return self._cache[rel]


def _cell(s: str, part: str) -> float:
    s = (s or "").strip()
    if "±" in s:
        a, b = s.split("±", 1)
        s = a if part == "value" else b
    elif part == "pm":
        raise StoryError(f"cell {s!r} has no ± part")
    try:
        return float(s.strip())
    except ValueError:
        raise StoryError(f"cell {s!r} is not a number") from None


def _matches(row: Dict[str, str], where: Dict[str, Any]) -> bool:
    for k, v in where.items():
        if k not in row:
            return False
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            try:
                if not math.isclose(float(row[k]), float(v), rel_tol=0, abs_tol=1e-12):
                    return False
            except ValueError:
                return False
        elif row[k] != str(v):
            return False
    return True


def _raw_number(key: str, spec: Dict[str, Any], src: Sources, numbers: Dict[str, Any],
                done: Dict[str, Dict[str, Any]], stack: Tuple[str, ...]) -> Tuple[float, str, str]:
    """(value before transform and scale, source text, flag)"""
    if "table" in spec:
        rows = src.table(spec["table"])
        where = spec.get("where", {})
        hit = [r for r in rows if _matches(r, where)]
        sel = ", ".join(f"{k} = {v}" for k, v in where.items()) or "the only row"
        if len(hit) != 1:
            raise StoryError(f"{spec['table']}: {len(hit)} rows match {sel} (need exactly one)")
        col = spec["column"]
        if col not in hit[0]:
            raise StoryError(f"{spec['table']} has no column {col}")
        part = spec.get("part", "value")
        return (_cell(hit[0][col], part), f"{spec['table']}, row {sel}, column {col}" + (" (± part)" if part == "pm" else ""),
                spec.get("flag", "Modelled"))
    if "json" in spec:
        v: Any = src.json(spec["json"])
        for p in spec["path"]:
            try:
                v = v[p]
            except (KeyError, IndexError, TypeError):
                raise StoryError(f"{spec['json']}: no {'/'.join(map(str, spec['path']))}") from None
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            raise StoryError(f"{spec['json']}: {'/'.join(map(str, spec['path']))} is not a number")
        return float(v), f"{spec['json']}: {'/'.join(map(str, spec['path']))}", spec.get("flag", "Modelled")
    if "catalog" in spec:
        from . import catalog
        rel = "lunarsim/" + os.path.basename(catalog.CATALOG_PATH)
        doc = src.json(rel)
        ent = next((e for e in doc["entries"] if e["id"] == spec["catalog"]), None)
        if ent is None:
            raise StoryError(f"catalogue has no entry {spec['catalog']}")
        q: Any = ent
        for p in spec["quantity"].split("."):
            q = q.get(p) if isinstance(q, dict) else None
        if not (isinstance(q, dict) and isinstance(q.get("value"), (int, float)) and not isinstance(q.get("value"), bool)):
            raise StoryError(f"catalogue {spec['catalog']} has no numeric quantity {spec['quantity']}")
        return float(q["value"]), f"{rel} {spec['catalog']}.{spec['quantity']}: {q.get('source', '')}", \
            spec.get("flag", q.get("flag", "Modelled"))
    if "derive" in spec:
        a_key, b_key = spec["of"]
        vals = []
        for k in (a_key, b_key):
            if k not in numbers:
                raise StoryError(f"derives from undeclared number {k}")
            r = _resolve_one(k, numbers, src, done, stack)
            vals.append(r)
        a, b = vals[0]["value"], vals[1]["value"]
        op = spec["derive"]
        if op == "diff":
            v = b - a
        elif op in ("ratio", "pct_change"):
            if a == 0:
                raise StoryError(f"{op} of {a_key} = 0")
            v = b / a if op == "ratio" else 100.0 * (b - a) / a
        else:
            raise StoryError(f"unknown derive {op}")
        flag = spec.get("flag") or max((x["flag"] for x in vals), key=lambda f: FLAG_RANK.get(f, 2))
        na, nb = (f"“{r['label']}”" if r.get("label") else k for k, r in zip((a_key, b_key), vals))
        how = {"diff": f"{nb} minus {na}", "ratio": f"{nb} divided by {na}",
               "pct_change": f"percentage change from {na} to {nb}"}[op]
        return v, f"{how} (from the unrounded values)", flag
    raise StoryError("a number needs one of table, json, catalog, derive")


def fmt(v: float, digits: int = 1, unit: str = "") -> str:
    s = f"{abs(v):,.{digits}f}"
    if v < 0 and float(s.replace(",", "")) != 0:
        s = MINUS + s
    return f"{s} {unit}".rstrip() if unit else s


def _resolve_one(key: str, numbers: Dict[str, Any], src: Sources, done: Dict[str, Dict[str, Any]],
                 stack: Tuple[str, ...] = ()) -> Dict[str, Any]:
    if key in done:
        if "error" in done[key]:
            raise StoryError(f"input {key}: {done[key]['error']}")
        if "pending" in done[key]:
            raise Pending(f"input {key}: {done[key]['pending']}")
        return done[key]
    if key in stack:
        raise StoryError(f"derive cycle through {key}")
    spec = numbers[key]
    v, source, flag = _raw_number(key, spec, src, numbers, done, stack + (key,))
    t = spec.get("transform")
    if t == "exp_pct":
        v = 100.0 * math.expm1(v)
    elif t == "neg":
        v = -v
    elif t == "abs":
        v = abs(v)
    elif t:
        raise StoryError(f"unknown transform {t}")
    v *= spec.get("scale", 1.0)
    if not math.isfinite(v):
        raise StoryError("value is not finite")
    v = float(f"{v:.12g}")          # 12 significant digits: platform libm last-bit noise stays out of the files
    if t:
        source += "; " + {"exp_pct": "as a percentage, 100 (e^v - 1)", "neg": "sign reversed", "abs": "absolute value"}[t]
    if spec.get("scale", 1.0) != 1.0:
        source += f"; x {spec['scale']:g}"
    if spec.get("note"):
        source += f"; {spec['note']}"
    out = {"value": v, "text": fmt(v, int(spec.get("digits", 1)), spec.get("unit", "")), "unit": spec.get("unit", ""),
           "flag": flag, "source": source}
    if spec.get("label"):
        out["label"] = spec["label"]
    done[key] = out
    return out


def resolve_numbers(doc: Dict[str, Any], src: Sources) -> Dict[str, Dict[str, Any]]:
    numbers = doc.get("numbers", {})
    done: Dict[str, Dict[str, Any]] = {}
    for k in numbers:
        if k in done:
            continue
        try:
            _resolve_one(k, numbers, src, done)
        except Pending as e:
            done[k] = {"pending": str(e)}
        except StoryError as e:
            done[k] = {"error": str(e)}
    for k, spec in numbers.items():                     # pending numbers keep their label too
        if spec.get("label") and "label" not in done[k]:
            done[k] = {**done[k], "label": spec["label"]}
    return {k: done[k] for k in numbers}


# ---------------------------------------------------------------------------------------------------------
# references: highlight ids and scene samples
# ---------------------------------------------------------------------------------------------------------
def _known_ids(root: str) -> Tuple[set, List[str]]:
    ids, errs = set(), []
    p = os.path.join(root, "data", "site_graph.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            ids |= {s["name"] for s in json.load(f)["sites"]}
    else:
        errs.append("data/site_graph.json missing: highlight ids cannot be checked")
    p = os.path.join(root, "lunarsim", "catalog-v1.json")
    if os.path.isfile(p):
        with open(p, encoding="utf-8") as f:
            ids |= {e["id"] for e in json.load(f)["entries"]}
    return ids, errs


def check_scene(ref: str, root: str) -> Optional[str]:
    """None when the scene sample exists: world:<scene package or gallery id>, lander:<cls>/<pilot>/<pick>,
    rover:<leg key, e.g. BASE->DEPOT>."""
    kind, _, name = ref.partition(":")
    if kind == "world":
        if os.path.isfile(os.path.join(root, "data", "scenes", name, "scene.json")):
            return None
        g = os.path.join(root, "data", "scenes", "gallery.json")
        if os.path.isfile(g):
            with open(g, encoding="utf-8") as f:
                if any(s.get("id") == name for s in json.load(f).get("scenes", [])):
                    return None
        return f"no scene package data/scenes/{name}"
    if kind == "lander":
        p = os.path.join(root, "data", "policies", "trajectories-v1.json")
        if not os.path.isfile(p):
            return "data/policies/trajectories-v1.json missing"
        try:
            cls, pilot, pick = name.split("/")
        except ValueError:
            return f"lander scene {name!r} is not <cls>/<pilot>/<pick>"
        with open(p, encoding="utf-8") as f:
            doc = json.load(f)
        ok = any(pl["cls"] == cls and pl["pilot"] == pilot and any(e["pick"] == pick for e in pl["episodes"])
                 for pl in doc["pilots"])
        return None if ok else f"trajectories-v1.json has no episode {name}"
    if kind == "rover":
        p = os.path.join(root, "data", "driving", "routes-v1.json")
        if not os.path.isfile(p):
            return "data/driving/routes-v1.json missing"
        with open(p, encoding="utf-8") as f:
            legs = json.load(f)["legs"]
        return None if name in legs else f"routes-v1.json has no leg {name}"
    return f"unknown scene kind {kind!r}"


# ---------------------------------------------------------------------------------------------------------
# check and resolve
# ---------------------------------------------------------------------------------------------------------
def _schema_errors(doc: Dict[str, Any]) -> List[str]:
    try:
        import jsonschema
    except ImportError:
        return []
    from .formats import load_schema
    v = jsonschema.Draft202012Validator(load_schema("story-v1"))
    return [f"schema: {'/'.join(map(str, e.path)) or '(root)'}: {e.message[:160]}" for e in v.iter_errors(doc)]


def check(doc: Dict[str, Any], root: str = ROOT, refs: bool = True,
          resolved: Optional[Dict[str, Dict[str, Any]]] = None) -> Tuple[List[str], List[str]]:
    """(errors, pending numbers) for one story."""
    errs = _schema_errors(doc)
    numbers = doc.get("numbers", {})
    if resolved is None:
        resolved = resolve_numbers(doc, Sources(root))
    used = set()
    for where, text in _prose_fields(doc):
        for k in placeholders(text):
            used.add(k)
            if k not in numbers:
                errs.append(f"{where}: placeholder {{{{r:{k}}}}} is not declared in numbers")
        for t in typed_digits(text):
            errs.append(f"{where}: typed number {t!r} (use a {{{{r:key}}}} placeholder)")
    for i, st in enumerate(doc.get("steps", [])):
        for k in st.get("chips", []):
            used.add(k)
            if k not in numbers:
                errs.append(f"steps[{i}].chips: {k} is not declared in numbers")
    for k, spec in numbers.items():
        if "derive" in spec:
            used |= set(spec.get("of", []))
        lab = spec.get("label")
        if lab is not None:
            if not isinstance(lab, str) or not 0 < len(lab) <= LABEL_MAX:
                errs.append(f"numbers.{k}.label: must be 1-{LABEL_MAX} characters")
            for t in typed_digits(lab if isinstance(lab, str) else ""):
                errs.append(f"numbers.{k}.label: typed number {t!r}")
    for k in numbers:
        if k not in used:
            errs.append(f"numbers.{k}: declared but not used")
    pending = []
    for k, r in resolved.items():
        if "error" in r:
            errs.append(f"numbers.{k}: {r['error']}")
        elif "pending" in r:
            if doc.get("status") == "published":
                errs.append(f"numbers.{k}: unresolved in a published story: {r['pending']}")
            pending.append(k)
    ids = [s.get("id") for s in doc.get("steps", [])]
    for d in sorted({x for x in ids if ids.count(x) > 1}):
        errs.append(f"step id {d} is repeated")
    if refs:
        known, rerrs = _known_ids(root)
        errs += rerrs
        for i, st in enumerate(doc.get("steps", [])):
            for h in st.get("highlight", []):
                if known and h not in known:
                    errs.append(f"steps[{i}].highlight: unknown id {h}")
        scenes = [("scene", doc["scene"])] if doc.get("scene") else []
        scenes += [(f"steps[{i}].scene", st["scene"]) for i, st in enumerate(doc.get("steps", [])) if st.get("scene")]
        for where, ref in scenes:
            e = check_scene(ref, root)
            if e:
                errs.append(f"{where}: {e}")
    return errs, pending


def _fill(text: str, resolved: Dict[str, Dict[str, Any]]) -> str:
    return PLACEHOLDER.sub(lambda m: resolved.get(m.group(1), {}).get("text", PENDING_TEXT), text)


def resolve(doc: Dict[str, Any], root: str = ROOT) -> Dict[str, Any]:
    """The story for the site: numbers with value/text/flag/source (or pending), prose with <field>_plain."""
    src = Sources(root)
    nums = resolve_numbers(doc, src)
    out = {"format": "lunarsim-story-resolved", "version": 1}
    for k, v in doc.items():
        if k in ("format", "version", "numbers", "steps"):
            continue
        out[k] = v
        if k in PROSE:
            out[k + "_plain"] = _fill(v, nums)
    out["numbers"] = nums
    steps = []
    for st in doc["steps"]:
        s = dict(st)
        for f in STEP_PROSE:
            if f in st:
                s[f + "_plain"] = _fill(st[f], nums)
        steps.append(s)
    out["steps"] = steps
    out["pending"] = [k for k, r in nums.items() if "pending" in r]
    out["sources"] = dict(sorted(src.used.items()))
    return out


def load(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def story_files(root: str = ROOT) -> List[str]:
    return sorted(glob.glob(os.path.join(root, STORIES, "*.json")))


def check_all(root: str = ROOT) -> Tuple[Dict[str, Tuple[List[str], List[str]]], Dict[str, Dict[str, Any]]]:
    results, built = {}, {}
    for p in story_files(root):
        doc = load(p)
        stem = os.path.splitext(os.path.basename(p))[0]
        res = resolve(doc, root)
        errs, pend = check(doc, root, resolved=res["numbers"])
        if doc.get("id") != stem:
            errs.append(f"id {doc.get('id')!r} differs from the file name {stem!r}")
        results[stem] = (errs, pend)
        built[stem] = res
    return results, built


def _dump(doc: Any) -> bytes:
    return (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")


def build(root: str = ROOT, out: Optional[str] = None) -> Tuple[Dict[str, Tuple[List[str], List[str]]], Dict[str, bytes]]:
    """Check every story; the resolved files (path -> bytes) for the stories without errors."""
    results, built = check_all(root)
    files = {}
    index = []
    for stem, res in built.items():
        if results[stem][0]:
            continue
        files[f"{stem}.json"] = _dump(res)
        index.append({"id": stem, "title": res["title"], "status": res["status"], "steps": len(res["steps"]),
                      "pending": len(res["pending"]), "file": f"{stem}.json"})
    files["index.json"] = _dump({"format": "lunarsim-stories-index", "version": 1, "stories": index})
    if out:
        os.makedirs(out, exist_ok=True)
        for name, b in files.items():
            with open(os.path.join(out, name), "wb") as f:
                f.write(b)
    return results, files


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Check guided stories and write their resolved files.")
    ap.add_argument("cmd", choices=["check", "build"])
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--out", default=None, help=f"build: output folder (default {RESOLVED})")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")      # a Windows console cannot print every sign
    out = (a.out or os.path.join(a.root, RESOLVED)) if a.cmd == "build" else None
    results, files = build(a.root, out)
    n_err = 0
    for stem, (errs, pend) in results.items():
        n_err += len(errs)
        print(f"{'OK ' if not errs else 'ERR'} {stem}" + (f"  ({len(pend)} pending: {', '.join(pend)})" if pend else ""))
        for e in errs:
            print(f"    {e}")
    if out:
        print(f"wrote {len(files)} files to {out}" + ("" if not n_err else " (stories with errors left out)"))
    print(f"stories: {len(results)}, {n_err} problem(s)")
    return 0 if n_err == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
