"""LunarSim service v2 (PLAN §5.6): FastAPI + SQLite (WAL) + DB-polling worker + SSE.

    python -m service --port 8800        the HTTP API (uvicorn)
    python -m service worker             the run executor (polls the same SQLite file)

The stdlib local API (``lunarsim serve``) is unchanged and stays for local use; this package
is the hosted, multi-user service with sign-in, saved runs, provenance and replication.
"""
__version__ = "0.1.0"
