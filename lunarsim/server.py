"""Local JSON API over the reference engine (standard library only).

    lunarsim serve --port 8765          (or: python -m lunarsim.server --port 8765)

Binds 127.0.0.1 only. JSON in and out, CORS open (Access-Control-Allow-Origin: *) so the
static page can call it. Errors are HTTP 4xx/5xx with {"error": "message"}. NaN is sent as null.

    GET  /api/health              {"ok": true, "version": "2.0.0", "engine": "python"}
    GET  /api/scenarios           {"scenarios": [{"name", "fleet_size", "landings_per_year"}]}
    GET  /api/scenarios/{name}    lunarsim-scenario v1, full form
    POST /api/run                 {"scenario": name|{scenario v1}, "mechanism", "seeds": [..], "opts": {..}}
                                  -> {"runs": [row, ...], "ms"}
    POST /api/compare             {"scenario", "seeds", "opts"} -> {"runs": {mechanism: [row, ...]}, "ms"}
    POST /api/trace               {"scenario", "mechanism", "seed"} -> lunarsim-trace v1
    GET  /api/verify              {"checks": [...], "passed": n, "total": n}

With --static DIR (e.g. web/dist) every other GET path serves that folder's files ("/" ->
index.html), so the page and the API share one origin. Paths that resolve outside DIR are
refused. Chrome's Private Network Access preflight (an https page such as the GitHub Pages
site calling http://127.0.0.1) is answered with Access-Control-Allow-Private-Network: true.

A scenario object may be either form (lunarsim.config); a compact form's `marketplace` flags
are used for the marketplace mechanisms, and `opts` (same keys) override them. Scenario names
are looked up in the named library only; file paths are not accepted over HTTP.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import posixpath
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Tuple
from urllib.parse import unquote, urlsplit

log = logging.getLogger("lunarsim.server")

HOST = "127.0.0.1"
MAX_SEEDS = 100
MAX_BODY = 1 << 20          # 1 MiB of JSON is far more than any scenario needs
COMPARE_MECHANISMS = ("inhouse", "pooled_greedy", "central_assign", "marketplace")
STATIC_TYPES = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json", ".css": "text/css; charset=utf-8", ".csv": "text/csv; charset=utf-8",
    ".txt": "text/plain; charset=utf-8", ".md": "text/markdown; charset=utf-8",
    ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".gif": "image/gif", ".ico": "image/x-icon", ".webp": "image/webp", ".pdf": "application/pdf",
    ".wasm": "application/wasm", ".woff2": "font/woff2", ".woff": "font/woff", ".map": "application/json",
}


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


# ---------------------------------------------------------------------------
# helpers shared by the endpoints
# ---------------------------------------------------------------------------
_lib_lock = threading.Lock()
_lib_cache: Dict[str, Any] = {}


def _library():
    with _lib_lock:
        if not _lib_cache:
            from .config import library
            _lib_cache.update(library())
        return _lib_cache


def clean(x: Any) -> Any:
    """JSON-safe copy: NaN/inf -> None, numpy scalars -> Python numbers, tuples -> lists."""
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, bool) or x is None or isinstance(x, str):
        return x
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    try:  # numpy scalar
        import numpy as np
        if isinstance(x, np.bool_):
            return bool(x)
        if isinstance(x, np.integer):
            return int(x)
        if isinstance(x, np.floating):
            return clean(float(x))
    except ImportError:  # pragma: no cover
        pass
    return x


def _scenario(spec: Any) -> Tuple[Any, Dict[str, Any]]:
    """(Scenario, marketplace kwargs from a compact form) from a library name or a scenario object."""
    from .config import scenario_from_dict_ex
    from .formats import validate_scenario
    if isinstance(spec, str):
        lib = _library()
        if spec not in lib:
            raise ApiError(400, f"unknown scenario '{spec}'. Known: {', '.join(sorted(lib))}")
        return lib[spec], {}
    if isinstance(spec, dict):
        errs = validate_scenario(spec)
        if errs:
            raise ApiError(400, "invalid scenario: " + "; ".join(errs[:10]))
        try:
            return scenario_from_dict_ex(spec)
        except (ValueError, TypeError, KeyError) as e:
            raise ApiError(400, f"invalid scenario: {e}")
    raise ApiError(400, "'scenario' must be a scenario name or a lunarsim-scenario object")


def _mechanism(name: Any):
    from .cli import _mechanism as cli_mechanism   # same lookup and central_assign batch_h as the CLI
    if not isinstance(name, str):
        raise ApiError(400, "'mechanism' must be a string")
    try:
        return cli_mechanism(name)
    except SystemExit as e:
        raise ApiError(400, str(e))


def _opts(opts: Any) -> Dict[str, Any]:
    from .config import MARKETPLACE_FLAGS, marketplace_kwargs
    if opts is None:
        return {}
    if not isinstance(opts, dict):
        raise ApiError(400, "'opts' must be an object")
    bad = [k for k in opts if k not in MARKETPLACE_FLAGS]
    if bad:
        raise ApiError(400, f"unknown opts {sorted(bad)}. Known: {', '.join(sorted(MARKETPLACE_FLAGS))}")
    if any(not isinstance(v, bool) for v in opts.values()):
        raise ApiError(400, "'opts' values must be true or false")
    return marketplace_kwargs(opts)


def _mech_kwargs(name: str, base: Dict[str, Any], file_kw: Dict[str, Any], opts: Dict[str, Any]) -> Dict[str, Any]:
    if name.startswith("marketplace"):
        return {**base, **file_kw, **opts}
    return dict(base)


def _seed(x: Any, what: str = "seed") -> int:
    if not isinstance(x, int) or isinstance(x, bool) or x < 0:
        raise ApiError(400, f"'{what}' must be a non-negative integer")
    return x


def _seeds(x: Any) -> List[int]:
    if x is None:
        return [0]
    if not isinstance(x, list) or not x:
        raise ApiError(400, "'seeds' must be a non-empty list of integers")
    if len(x) > MAX_SEEDS:
        raise ApiError(400, f"at most {MAX_SEEDS} seeds per request (got {len(x)})")
    return [_seed(s, "seeds[]") for s in x]


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
def api_health(_body=None):
    from . import __version__
    return {"ok": True, "version": __version__, "engine": "python"}


def api_scenarios(_body=None):
    return {"scenarios": [{"name": k, "fleet_size": len(sc.fleet), "landings_per_year": sc.landings_per_year}
                          for k, sc in _library().items()]}


def api_scenario(name: str):
    from .config import scenario_to_dict
    lib = _library()
    if name not in lib:
        raise ApiError(404, f"unknown scenario '{name}'. Known: {', '.join(sorted(lib))}")
    return scenario_to_dict(lib[name].with_(name=name))


def api_run(body: Dict[str, Any]):
    from .engine import run
    sc, file_kw = _scenario(body.get("scenario", "P2-default"))
    name = body.get("mechanism", "marketplace")
    fn, kw = _mechanism(name)
    kw = _mech_kwargs(name, kw, file_kw, _opts(body.get("opts")))
    seeds = _seeds(body.get("seeds"))
    t0 = time.perf_counter()
    runs = [run(sc, fn, seed=s, **kw) for s in seeds]
    return {"runs": runs, "ms": round(1000 * (time.perf_counter() - t0))}


def api_compare(body: Dict[str, Any]):
    from .engine import run
    sc, file_kw = _scenario(body.get("scenario", "P2-default"))
    opts = _opts(body.get("opts"))
    seeds = _seeds(body.get("seeds"))
    t0 = time.perf_counter()
    out = {}
    for name in COMPARE_MECHANISMS:
        fn, kw = _mechanism(name)
        kw = _mech_kwargs(name, kw, file_kw, opts)
        out[name] = [run(sc, fn, seed=s, **kw) for s in seeds]
    return {"runs": out, "ms": round(1000 * (time.perf_counter() - t0))}


def api_trace(body: Dict[str, Any]):
    from .engine import Simulation
    sc, file_kw = _scenario(body.get("scenario", "P2-4-vehicles"))
    name = body.get("mechanism", "marketplace")
    fn, kw = _mechanism(name)
    kw = dict(_mech_kwargs(name, kw, file_kw, _opts(body.get("opts"))), trace=True)
    sim = Simulation(sc, fn, seed=_seed(body.get("seed", 3)), mech_kwargs=kw)
    sim.run()
    return sim.trace_export(mechanism=name)


def api_verify(_body=None):
    from . import vv
    checks = vv.run_all_checks()
    return {"checks": checks, "passed": sum(bool(c["passed"]) for c in checks), "total": len(checks)}


GET_ROUTES = {"/api/health": api_health, "/api/scenarios": api_scenarios, "/api/verify": api_verify}
POST_ROUTES = {"/api/run": api_run, "/api/compare": api_compare, "/api/trace": api_trace}


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------
class Handler(BaseHTTPRequestHandler):
    server_version = "lunarsim"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # route the stdlib's access log through logging
        log.info("%s %s", self.address_string(), fmt % args)

    def _send(self, status: int, payload: Any = None) -> None:
        body = b"" if payload is None else json.dumps(clean(payload), allow_nan=False).encode("utf-8")
        self._send_bytes(status, body, "application/json" if payload is not None else None)

    def _send_bytes(self, status: int, body: bytes, content_type: Any = None, extra: Any = None) -> None:
        self.send_response(status)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "600")
        if (self.headers.get("Access-Control-Request-Private-Network") or "").lower() == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")   # Chrome PNA preflight
        if content_type:
            self.send_header("Content-Type", content_type)
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _static(self, path: str) -> None:
        """Serve a file under server.static_dir, refusing anything that resolves outside it."""
        root = self.server.static_dir
        rel = unquote(path).replace("\\", "/")
        parts = [p for p in rel.split("/") if p not in ("", ".")]
        if ".." in parts or any(":" in p or "\x00" in p for p in parts):
            raise ApiError(403, "path outside the static folder")
        full = os.path.realpath(os.path.join(root, *parts))
        if os.path.commonpath([root, full]) != root:
            raise ApiError(403, "path outside the static folder")
        if os.path.isdir(full):
            full = os.path.join(full, "index.html")
        if not os.path.isfile(full):
            raise ApiError(404, f"no file {path}")
        with open(full, "rb") as f:
            body = f.read()
        ctype = STATIC_TYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        self._send_bytes(200, body, ctype, {"Cache-Control": "no-cache"})

    def _dispatch(self, method: str) -> None:
        try:
            path = urlsplit(self.path).path.rstrip("/") or "/"
            if method == "GET":
                if path in GET_ROUTES:
                    return self._send(200, GET_ROUTES[path]())
                if path.startswith("/api/scenarios/"):
                    return self._send(200, api_scenario(unquote(path[len("/api/scenarios/"):])))
                if path in POST_ROUTES:
                    raise ApiError(405, f"{path} needs POST")
                if self.server.static_dir and not (path + "/").startswith("/api/"):
                    return self._static(urlsplit(self.path).path)
            else:
                if path in POST_ROUTES:
                    return self._send(200, POST_ROUTES[path](self._body()))
                if path in GET_ROUTES or path.startswith("/api/scenarios/"):
                    raise ApiError(405, f"{path} needs GET")
            raise ApiError(404, f"no endpoint {method} {path}")
        except ApiError as e:
            self._send(e.status, {"error": str(e)})
        except Exception as e:  # engine failure: report, keep serving
            log.exception("error handling %s %s", method, self.path)
            self._send(500, {"error": f"{type(e).__name__}: {e}"})

    def _body(self) -> Dict[str, Any]:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "bad Content-Length")
        if n > MAX_BODY:
            raise ApiError(413, f"request body over {MAX_BODY} bytes")
        raw = self.rfile.read(n) if n else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            raise ApiError(400, f"request body is not valid JSON: {e}")
        if not isinstance(body, dict):
            raise ApiError(400, "request body must be a JSON object")
        return body

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_OPTIONS(self):  # CORS preflight
        self._send(204)


def make_server(port: int = 8765, static_dir: Any = None) -> ThreadingHTTPServer:
    """A ThreadingHTTPServer on 127.0.0.1:port (port 0 picks a free one; see .server_address).
    With static_dir, non-API GET paths serve files from that folder."""
    if static_dir is not None:
        static_dir = os.path.realpath(static_dir)
        if not os.path.isdir(static_dir):
            raise ValueError(f"--static: no such folder {static_dir}")
    srv = ThreadingHTTPServer((HOST, port), Handler)
    srv.daemon_threads = True
    srv.static_dir = static_dir
    return srv


def serve(port: int = 8765, static_dir: Any = None) -> None:
    srv = make_server(port, static_dir)
    host, port = srv.server_address[:2]
    print(f"lunarsim API on http://{host}:{port}/api/health  (Ctrl+C to stop)", flush=True)
    if static_dir:
        print(f"serving {srv.static_dir} at http://{host}:{port}/", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    p = argparse.ArgumentParser(prog="lunarsim serve", description="local JSON API over the reference engine")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--static", default=None, metavar="DIR", help="also serve this folder at / (e.g. web/dist)")
    a = p.parse_args(argv)
    serve(a.port, a.static)


if __name__ == "__main__":
    main()
