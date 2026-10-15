"""Runners.

    python -m service [serve] [--host 127.0.0.1] [--port 8800] [--reload]     the API (uvicorn)
    python -m service worker [--once]                                          the run executor
    python -m service version                                                  provenance as the API reports it
"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from .settings import Settings


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="python -m service", description="LunarSim service v2")
    sub = p.add_subparsers(dest="cmd")
    sv = sub.add_parser("serve", help="run the HTTP API with uvicorn (default)")
    sv.add_argument("--host", default="127.0.0.1")
    sv.add_argument("--port", type=int, default=8800)
    sv.add_argument("--reload", action="store_true", help="development auto-reload")
    sv.add_argument("--workers", type=int, default=1)
    wk = sub.add_parser("worker", help="poll the database and execute queued runs")
    wk.add_argument("--once", action="store_true", help="execute at most one run and exit (0 = ran one, 3 = queue empty)")
    sub.add_parser("version", help="print provenance and settings (no secrets)")
    # allow `python -m service --port 8800` without the word serve
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        argv = ["serve", *argv]
    a = p.parse_args(argv)
    settings = Settings.from_env()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if a.cmd == "worker":
        from .worker import Worker
        w = Worker(settings)
        if a.once:
            sys.exit(0 if w.run_once() else 3)
        w.run_forever()
        return
    if a.cmd == "version":
        from . import provenance
        prov = provenance.collect(settings.repo_root)
        print(json.dumps({"provenance": provenance.as_dict(prov), "settings": settings.public_dict()}, indent=2))
        return
    import uvicorn
    if a.reload:
        uvicorn.run("service.app:create_app", factory=True, host=a.host, port=a.port, reload=True)
    else:
        from .app import create_app
        uvicorn.run(create_app(settings), host=a.host, port=a.port, workers=1, proxy_headers=settings.trust_proxy,
                    forwarded_allow_ips="127.0.0.1" if settings.trust_proxy else None)


if __name__ == "__main__":
    main()
