"""CI gates (B-38): per-page download budgets on the built site, and schema validation of every data file.

    python tools/ci/budgets.py pages --dist site/dist                 # after `npm run build` in site/
    python tools/ci/budgets.py pages --dist site/dist --propose       # print budgets 25 % above today's sizes
    python tools/ci/budgets.py schemas                                # every data file that has a JSON Schema

pages: for each built page (site/dist/**/index.html, 404.html) the initial JavaScript and CSS are the files its HTML
loads (module scripts, modulepreload links, stylesheets: what Vite emits for the page's static imports; lazy chunks
such as the 3D stage load later and are not counted), measured gzip-compressed (GitHub Pages serves gzip). The data a
page fetches at load is declared per page in tools/ci/budgets.json (globs under dist; listed from the page code and
prepare-data.mjs outputs) and measured the same way. Classic scripts (<script src> without type="module", e.g. the
simulator's engine files copied in by site/scripts/copy-simulator.mjs) count with the page's JS. Chunks a page loads
later by dynamic import are declared per page as "lazy" (globs of the entry chunks; their static imports are followed,
minus the files the page already loaded) and reported and budgeted separately (lazy_gzip_kb). The site total is
checked against the Pages limit. Thresholds:
tools/ci/budgets.json; a page without its own entry uses "defaults". Exit 1 on any violation or missing file.

schemas: validates with jsonschema (Draft 2020-12) and, where a format has one, its Python validator too:
catalog, routes, trajectories, scene indexes and gallery, earth link, stories, scenario files and sample traces (v1 or v2 by
version).
"""
from __future__ import annotations

import argparse
import fnmatch
import glob
import gzip
import json
import math
import os
import re
import sys
from html.parser import HTMLParser
from typing import Any, Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
BUDGETS = os.path.join(ROOT, "tools", "ci", "budgets.json")


# ---------------------------------------------------------------------------------------------------------
# pages
# ---------------------------------------------------------------------------------------------------------
class _Refs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.js: List[str] = []
        self.css: List[str] = []
        self.classic: List[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "script" and a.get("type") == "module" and a.get("src"):
            self.js.append(a["src"])
        elif tag == "script" and a.get("src") and a.get("type") in (None, "", "text/javascript", "application/javascript"):
            self.classic.append(a["src"])
        elif tag == "link" and a.get("href"):
            rel = (a.get("rel") or "").lower()
            if rel == "modulepreload":
                self.js.append(a["href"])
            elif rel == "stylesheet":
                self.css.append(a["href"])


def _local(href: str, dist: str, page_dir: str) -> str:
    """A built file for an href (absolute with any base prefix, or relative to the page)."""
    href = href.split("?")[0].split("#")[0]
    if re.match(r"^[a-z]+://", href):
        return ""
    if "/assets/" in href or href.startswith("assets/"):
        return os.path.join(dist, "assets", href.split("assets/", 1)[1])
    if href.startswith("/"):
        p = os.path.join(dist, href.lstrip("/"))
        parts = href.lstrip("/").split("/", 1)
        if not os.path.exists(p) and len(parts) == 2 and os.path.exists(os.path.join(dist, parts[1])):
            return os.path.join(dist, parts[1])               # a site base prefix (e.g. /Lunar-Haul/) on a "/" build
        return p
    return os.path.normpath(os.path.join(page_dir, href))


_IMPORT = re.compile(r"""(?:\bfrom\s*|\bimport\s*)["'](\./[^"']+\.js)["']""")


def static_closure(entries: List[str]) -> List[str]:
    """The entry chunks and every chunk they import statically (relative ./x.js imports of Vite's output)."""
    seen, todo = set(), list(entries)
    while todo:
        f = os.path.normpath(todo.pop())
        if f in seen or not os.path.isfile(f):
            continue
        seen.add(f)
        with open(f, encoding="utf-8", errors="replace") as fh:
            for rel in _IMPORT.findall(fh.read()):
                todo.append(os.path.join(os.path.dirname(f), rel))
    return sorted(seen)


def gz(path: str) -> int:
    with open(path, "rb") as f:
        return len(gzip.compress(f.read(), 6))


def pages(dist: str) -> List[str]:
    out = sorted(os.path.relpath(p, dist).replace(os.sep, "/") for p in glob.glob(os.path.join(dist, "**", "index.html"), recursive=True))
    if os.path.isfile(os.path.join(dist, "404.html")):
        out.append("404.html")
    return out


def measure(dist: str, budgets: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for page in pages(dist):
        p = _Refs()
        with open(os.path.join(dist, page), encoding="utf-8") as f:
            p.feed(f.read())
        page_dir = os.path.dirname(os.path.join(dist, page))
        missing = []
        js_files = sorted({_local(h, dist, page_dir) for h in p.js + p.classic} - {""})
        css_files = sorted({_local(h, dist, page_dir) for h in p.css} - {""})
        js = sum(gz(f) for f in js_files if os.path.isfile(f))
        css = sum(gz(f) for f in css_files if os.path.isfile(f))
        missing += [os.path.relpath(f, dist) for f in js_files + css_files if not os.path.isfile(f)]
        spec = {**budgets.get("defaults", {}), **budgets.get("pages", {}).get(page, {})}
        data_files = []
        for pattern in spec.get("data", []):
            hits = sorted(glob.glob(os.path.join(dist, pattern)))
            if not hits:
                missing.append(pattern)
            data_files += hits
        data = sum(gz(f) for f in sorted(set(data_files)))
        lazy_entries = []
        for pattern in spec.get("lazy", []):
            hits = sorted(glob.glob(os.path.join(dist, pattern)))
            if not hits:
                missing.append(pattern)
            lazy_entries += hits
        initial = {os.path.normpath(f) for f in js_files}
        lazy_files = [f for f in static_closure(lazy_entries) if f not in initial]
        lazy = sum(gz(f) for f in lazy_files)
        rows.append({"page": page, "js_gzip_kb": js / 1024, "css_gzip_kb": css / 1024, "data_gzip_kb": data / 1024,
                     "lazy_gzip_kb": lazy / 1024, "n_js": len(js_files), "n_classic": len(set(p.classic)),
                     "n_lazy": len(lazy_files), "n_data": len(set(data_files)), "missing": missing, "spec": spec})
    return rows


def check_pages(dist: str, budgets: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    rows = measure(dist, budgets)
    errs = []
    for r in rows:
        s = r["spec"]
        for k in ("js_gzip_kb", "css_gzip_kb", "data_gzip_kb", "lazy_gzip_kb"):
            if k in s and r[k] > s[k] + 1e-9:
                errs.append(f"{r['page']}: {k} {r[k]:.1f} > budget {s[k]}")
        for m in r["missing"]:
            errs.append(f"{r['page']}: missing {m}")
    known = set(budgets.get("pages", {}))
    for page in known - {r["page"] for r in rows}:
        errs.append(f"budgets.json lists {page}, which the build does not have")
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(dist) for f in fs) / 2**20
    lim = budgets.get("site_total_mb")
    if lim and total > lim:
        errs.append(f"site total {total:.0f} MB > {lim} MB")
    rows.append({"page": "(site total)", "total_mb": total, "spec": {"site_total_mb": lim}})
    return rows, errs


def propose(rows: List[Dict[str, Any]], margin: float = 1.25) -> Dict[str, Any]:
    up = lambda x: int(math.ceil(max(x, 1.0) * margin / 5.0) * 5)
    out = {}
    for r in rows:
        if r["page"].startswith("("):
            continue
        out[r["page"]] = {"js_gzip_kb": up(r["js_gzip_kb"]), "css_gzip_kb": up(r["css_gzip_kb"])}
        if r["spec"].get("data"):
            out[r["page"]].update(data=r["spec"]["data"], data_gzip_kb=up(r["data_gzip_kb"]))
        if r["spec"].get("lazy"):
            out[r["page"]].update(lazy=r["spec"]["lazy"], lazy_gzip_kb=up(r["lazy_gzip_kb"]))
    return out


# ---------------------------------------------------------------------------------------------------------
# schemas
# ---------------------------------------------------------------------------------------------------------
def _load(path: str):
    with open(path, "rb") as f:
        raw = f.read()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def schema_targets(root: str = ROOT) -> List[Tuple[str, str]]:
    """(data file, schema name) for every committed data file that has a schema."""
    j = lambda *p: os.path.join(root, *p)
    t = [(j("lunarsim", "catalog-v1.json"), "catalog-v1"),
         (j("data", "driving", "routes-v1.json"), "routes-v1"),
         (j("data", "policies", "trajectories-v1.json"), "trajectories-v1"),
         (j("data", "comms", "connecting_ridge", "earth_link-v1.json"), "earth-link-v1"),
         (j("data", "illumination", "connecting_ridge", "sun_link-v1.json"), "sun-link-v1")]
    t += [(p, "scene-v1") for p in sorted(glob.glob(j("data", "scenes", "*", "scene.json")))]
    t += [(p, "scenario-v1") for p in sorted(glob.glob(j("data", "scenarios", "*.json")))]
    t += [(j("data", "scenes", "gallery.json"), "scene-gallery-v1")]
    t += [(p, "story-v1") for p in sorted(glob.glob(j("data", "stories", "*.json")))]
    for p in sorted(glob.glob(j("data", "sample_traces", "*.json"))):
        t.append((p, "trace-v2" if _load(p).get("version") == 2 else "trace-v1"))
    return [(p, s) for p, s in t if os.path.isfile(p)]


def _python_validator(schema: str):
    if schema == "catalog-v1":
        from lunarsim.catalog import validate
        return validate
    if schema == "routes-v1":
        from lunarsim.rover.routes import validate
        return validate
    if schema == "trajectories-v1":
        from lunarsim.lander.trajectories import validate
        return validate
    if schema == "earth-link-v1":
        from lunarsim.comms import validate
        return validate
    if schema == "sun-link-v1":
        from lunarsim.illumination import validate
        return validate
    if schema.startswith("trace-"):
        from lunarsim.formats import validate_trace
        return validate_trace
    if schema == "story-v1":
        from lunarsim.stories import check
        return lambda doc: check(doc)[0]
    if schema == "scenario-v1":
        from lunarsim.formats import validate_scenario
        return validate_scenario
    return None


def check_schemas(root: str = ROOT) -> Tuple[List[Tuple[str, str, int]], List[str]]:
    import jsonschema
    from lunarsim.formats import load_schema
    errs, done = [], []
    cache: Dict[str, Any] = {}
    for path, name in schema_targets(root):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        if name not in cache:
            sch = load_schema(name)
            jsonschema.Draft202012Validator.check_schema(sch)
            cache[name] = jsonschema.Draft202012Validator(sch)
        doc = _load(path)
        n = 0
        for e in cache[name].iter_errors(doc):
            n += 1
            if n <= 3:
                errs.append(f"{rel} [{name}]: {'/'.join(map(str, e.path))}: {e.message[:160]}")
        pv = _python_validator(name)
        if pv is not None:
            for e in (pv(doc) or [])[:3]:
                errs.append(f"{rel} [{name}, Python validator]: {e}")
                n += 1
        done.append((rel, name, n))
    return done, errs


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pages")
    p.add_argument("--dist", default=os.path.join(ROOT, "site", "dist"))
    p.add_argument("--budgets", default=BUDGETS)
    p.add_argument("--propose", action="store_true")
    sub.add_parser("schemas")
    a = ap.parse_args(argv)
    if a.cmd == "pages":
        with open(a.budgets, encoding="utf-8") as f:
            budgets = json.load(f)
        rows, errs = check_pages(a.dist, budgets)
        print(f"{'page':28s} {'JS gz kB':>9s} {'CSS gz kB':>9s} {'data gz kB':>10s} {'lazy gz kB':>10s}   "
              f"budgets (JS / CSS / data / lazy)")
        for r in rows:
            if r["page"].startswith("("):
                print(f"{r['page']:28s} {r['total_mb']:.1f} MB (limit {r['spec']['site_total_mb']} MB)")
                continue
            s = r["spec"]
            print(f"{r['page']:28s} {r['js_gzip_kb']:9.1f} {r['css_gzip_kb']:9.1f} {r['data_gzip_kb']:10.1f} "
                  f"{r['lazy_gzip_kb']:10.1f}   {s.get('js_gzip_kb', '-')} / {s.get('css_gzip_kb', '-')} / "
                  f"{s.get('data_gzip_kb', '-')} / {s.get('lazy_gzip_kb', '-')}")
        if a.propose:
            print(json.dumps(propose(rows), indent=1))
        for e in errs:
            print("BUDGET", e)
        print("pages: OK" if not errs else f"pages: {len(errs)} problem(s)")
        return 0 if not errs else 1
    done, errs = check_schemas()
    for rel, name, n in done:
        print(f"{'OK ' if n == 0 else 'ERR'} {rel}  [{name}]")
    for e in errs:
        print("SCHEMA", e)
    print(f"schemas: {len(done)} files, {len(errs)} problem(s)")
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
