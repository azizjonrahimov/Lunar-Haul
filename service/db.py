"""SQLite storage (WAL) through the standard library sqlite3 module.

Why sqlite3 and not SQLAlchemy Core: the schema is a handful of fixed tables with plain SQL, the
service has one writer at a time (the research note reason for choosing SQLite at all), Litestream
replicates the file regardless of the driver, and the package then needs no database dependency
beyond CPython. Every statement lives in this module, so moving to Postgres later (when the service
outgrows one host) touches one file.

Connections are per thread (FastAPI runs sync endpoints in a thread pool); each connection sets
WAL, a 5 s busy timeout, foreign keys and synchronous=NORMAL (the WAL-safe setting Litestream
recommends). Writes go through `tx()` which opens BEGIN IMMEDIATE so a writer never has to retry
after reading.

Schema (PLAN 5.6), plus the additions listed in README "Departures":
  users(id, orcid, github_id, email, name, created)
  sessions(id, user_id, expires)                       -- id is sha256(session token)
  runs(id ulid, user_id, created, status, engine_version, git_sha, git_dirty, patch_sha, lock_sha,
       python, platform, scenario_sha, scenario_json, mechanism, options_json, seeds_json,
       policy_shas_json, output_sha, summary_json, parent_run_id, public, doi, cpu_s,
       + started, finished, error, replicated, worker, anon_key)
  run_events(run_id, seq, t, kind, payload_json)       -- append-only
  blobs(sha, media, bytes, path, created)              -- content-addressed, blobs/<sha[:2]>/<sha>
  quota(user_id, day, cpu_s)
  magic_links, oauth_states, login_codes               -- auth bookkeeping (additions)
"""
from __future__ import annotations

import contextlib
import json
import os
import sqlite3
import threading
from typing import Any, Dict, Iterator, List, Optional

from .util import iso, now

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id         TEXT PRIMARY KEY,
  orcid      TEXT UNIQUE,
  github_id  TEXT UNIQUE,
  email      TEXT UNIQUE,
  name       TEXT,
  created    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id         TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  expires    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS runs (
  id               TEXT PRIMARY KEY,
  user_id          TEXT REFERENCES users(id) ON DELETE SET NULL,
  created          TEXT NOT NULL,
  status           TEXT NOT NULL,
  engine_version   TEXT,
  git_sha          TEXT,
  git_dirty        INTEGER,
  patch_sha        TEXT,
  lock_sha         TEXT,
  python           TEXT,
  platform         TEXT,
  scenario_sha     TEXT NOT NULL,
  scenario_json    TEXT NOT NULL,
  mechanism        TEXT NOT NULL,
  options_json     TEXT NOT NULL,
  seeds_json       TEXT NOT NULL,
  policy_shas_json TEXT,
  output_sha       TEXT,
  summary_json     TEXT,
  parent_run_id    TEXT REFERENCES runs(id),
  public           INTEGER NOT NULL DEFAULT 0,
  doi              TEXT,
  cpu_s            REAL,
  started          TEXT,
  finished         TEXT,
  error            TEXT,
  replicated       INTEGER,
  worker           TEXT,
  anon_key         TEXT
);
CREATE INDEX IF NOT EXISTS runs_status_created ON runs(status, created);
CREATE INDEX IF NOT EXISTS runs_user_created ON runs(user_id, created);
CREATE INDEX IF NOT EXISTS runs_public ON runs(public, status, created);
CREATE INDEX IF NOT EXISTS runs_parent ON runs(parent_run_id);
CREATE TABLE IF NOT EXISTS run_events (
  run_id       TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  seq          INTEGER NOT NULL,
  t            TEXT NOT NULL,
  kind         TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  PRIMARY KEY (run_id, seq)
);
CREATE TABLE IF NOT EXISTS blobs (
  sha      TEXT PRIMARY KEY,
  media    TEXT NOT NULL,
  bytes    INTEGER NOT NULL,
  path     TEXT NOT NULL,
  created  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quota (
  user_id  TEXT NOT NULL,
  day      TEXT NOT NULL,
  cpu_s    REAL NOT NULL DEFAULT 0,
  PRIMARY KEY (user_id, day)
);
CREATE TABLE IF NOT EXISTS magic_links (
  token_sha  TEXT PRIMARY KEY,
  email      TEXT NOT NULL,
  mode       TEXT NOT NULL,
  next       TEXT,
  created    REAL NOT NULL,
  expires    REAL NOT NULL,
  used       INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS oauth_states (
  state      TEXT PRIMARY KEY,
  provider   TEXT NOT NULL,
  mode       TEXT NOT NULL,
  next       TEXT,
  created    REAL NOT NULL,
  expires    REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS login_codes (
  code_sha   TEXT PRIMARY KEY,
  user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created    REAL NOT NULL,
  expires    REAL NOT NULL,
  used       INTEGER NOT NULL DEFAULT 0
);
"""

RUN_COLUMNS = ("id", "user_id", "created", "status", "engine_version", "git_sha", "git_dirty", "patch_sha",
               "lock_sha", "python", "platform", "scenario_sha", "scenario_json", "mechanism", "options_json",
               "seeds_json", "policy_shas_json", "output_sha", "summary_json", "parent_run_id", "public", "doi",
               "cpu_s", "started", "finished", "error", "replicated", "worker", "anon_key")


class Database:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self._local = threading.local()
        self._write_lock = threading.RLock()
        self.conn().executescript(SCHEMA)      # executescript manages its own transaction

    # ------------------------------------------------------------------ connections
    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, timeout=5.0, isolation_level=None, check_same_thread=False)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA synchronous=NORMAL")
            c.execute("PRAGMA foreign_keys=ON")
            c.execute("PRAGMA busy_timeout=5000")
            self._local.conn = c
        return c

    def close(self) -> None:
        c = getattr(self._local, "conn", None)
        if c is not None:
            c.close()
            self._local.conn = None

    @contextlib.contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        """One write transaction (BEGIN IMMEDIATE). Nested use inside a thread joins the outer one."""
        c = self.conn()
        with self._write_lock:
            if c.in_transaction:
                yield c
                return
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
            except BaseException:
                c.execute("ROLLBACK")
                raise
            else:
                c.execute("COMMIT")

    def one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        return self.conn().execute(sql, params).fetchone()

    def all(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        return self.conn().execute(sql, params).fetchall()

    # ------------------------------------------------------------------ users / sessions
    def get_user(self, user_id: str) -> Optional[sqlite3.Row]:
        return self.one("SELECT * FROM users WHERE id=?", (user_id,))

    def find_user(self, **by: str) -> Optional[sqlite3.Row]:
        (k, v), = by.items()
        assert k in ("orcid", "github_id", "email", "id")
        return self.one(f"SELECT * FROM users WHERE {k}=?", (v,))

    def create_user(self, user_id: str, *, orcid=None, github_id=None, email=None, name=None) -> sqlite3.Row:
        with self.tx() as c:
            c.execute("INSERT INTO users(id, orcid, github_id, email, name, created) VALUES (?,?,?,?,?,?)",
                      (user_id, orcid, github_id, email, name, iso()))
        return self.get_user(user_id)  # type: ignore[return-value]

    def update_user(self, user_id: str, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self.tx() as c:
            c.execute(f"UPDATE users SET {cols} WHERE id=?", (*fields.values(), user_id))

    def create_session(self, sid_sha: str, user_id: str, expires: float) -> None:
        with self.tx() as c:
            c.execute("INSERT INTO sessions(id, user_id, expires) VALUES (?,?,?)", (sid_sha, user_id, expires))

    def get_session(self, sid_sha: str) -> Optional[sqlite3.Row]:
        row = self.one("SELECT id, user_id, expires FROM sessions WHERE id=?", (sid_sha,))
        if row is None:
            return None
        if row["expires"] <= now():
            self.delete_session(sid_sha)
            return None
        return row

    def delete_session(self, sid_sha: str) -> None:
        with self.tx() as c:
            c.execute("DELETE FROM sessions WHERE id=?", (sid_sha,))

    def purge_expired(self) -> None:
        t = now()
        with self.tx() as c:
            c.execute("DELETE FROM sessions WHERE expires<=?", (t,))
            c.execute("DELETE FROM magic_links WHERE expires<=? OR used=1", (t,))
            c.execute("DELETE FROM oauth_states WHERE expires<=?", (t,))
            c.execute("DELETE FROM login_codes WHERE expires<=? OR used=1", (t,))

    # ------------------------------------------------------------------ runs
    def insert_run(self, row: Dict[str, Any]) -> None:
        cols = [k for k in RUN_COLUMNS if k in row]
        with self.tx() as c:
            c.execute(f"INSERT INTO runs({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
                      tuple(row[k] for k in cols))

    def get_run(self, run_id: str) -> Optional[sqlite3.Row]:
        return self.one("SELECT * FROM runs WHERE id=?", (run_id,))

    def update_run(self, run_id: str, **fields) -> None:
        if not fields:
            return
        cols = ", ".join(f"{k}=?" for k in fields)
        with self.tx() as c:
            c.execute(f"UPDATE runs SET {cols} WHERE id=?", (*fields.values(), run_id))

    def count_runs(self, where: str, params: tuple = ()) -> int:
        return int(self.one(f"SELECT COUNT(*) AS n FROM runs WHERE {where}", params)["n"])  # type: ignore[index]

    def claim_run(self, worker: str) -> Optional[sqlite3.Row]:
        """Atomically move the oldest queued run to running for this worker."""
        with self.tx() as c:
            r = c.execute("SELECT id FROM runs WHERE status='queued' ORDER BY created, id LIMIT 1").fetchone()
            if r is None:
                return None
            cur = c.execute("UPDATE runs SET status='running', started=?, worker=? WHERE id=? AND status='queued'",
                            (iso(), worker, r["id"]))
            if cur.rowcount != 1:
                return None
        return self.get_run(r["id"])

    def requeue_stale(self, older_than_s: float) -> List[str]:
        cutoff = iso(now() - older_than_s)
        rows = self.all("SELECT id FROM runs WHERE status='running' AND started<?", (cutoff,))
        ids = [r["id"] for r in rows]
        for rid in ids:
            with self.tx() as c:
                c.execute("UPDATE runs SET status='queued', started=NULL, worker=NULL WHERE id=? AND status='running'",
                          (rid,))
            self.add_event(rid, "requeued", {"reason": f"running for more than {int(older_than_s)} s"})
        return ids

    # ------------------------------------------------------------------ events (append-only)
    def add_event(self, run_id: str, kind: str, payload: Any) -> int:
        with self.tx() as c:
            r = c.execute("SELECT COALESCE(MAX(seq), 0) + 1 AS seq FROM run_events WHERE run_id=?", (run_id,)).fetchone()
            seq = int(r["seq"])
            c.execute("INSERT INTO run_events(run_id, seq, t, kind, payload_json) VALUES (?,?,?,?,?)",
                      (run_id, seq, iso(), kind, json.dumps(payload, allow_nan=False, separators=(",", ":"))))
        return seq

    def events_after(self, run_id: str, after_seq: int = 0) -> List[sqlite3.Row]:
        return self.all("SELECT seq, t, kind, payload_json FROM run_events WHERE run_id=? AND seq>? ORDER BY seq",
                        (run_id, after_seq))

    # ------------------------------------------------------------------ blobs
    def put_blob(self, data_dir: str, data: bytes, media: str, sha: str) -> Dict[str, Any]:
        """Store content-addressed under <data_dir>/blobs/<sha[:2]>/<sha>; identical bytes are written once."""
        rel = f"blobs/{sha[:2]}/{sha}"
        full = os.path.join(data_dir, "blobs", sha[:2], sha)
        existing = self.one("SELECT * FROM blobs WHERE sha=?", (sha,))
        if existing is not None and os.path.isfile(full):
            return dict(existing)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        tmp = full + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, full)
        with self.tx() as c:
            c.execute("INSERT OR REPLACE INTO blobs(sha, media, bytes, path, created) VALUES (?,?,?,?,?)",
                      (sha, media, len(data), rel, iso()))
        return dict(self.one("SELECT * FROM blobs WHERE sha=?", (sha,)))  # type: ignore[arg-type]

    def get_blob(self, sha: str) -> Optional[sqlite3.Row]:
        return self.one("SELECT * FROM blobs WHERE sha=?", (sha,))

    @staticmethod
    def blob_path(data_dir: str, row: sqlite3.Row) -> str:
        return os.path.join(data_dir, *row["path"].split("/"))

    # ------------------------------------------------------------------ quota
    def quota_used(self, key: str, day: str) -> float:
        r = self.one("SELECT cpu_s FROM quota WHERE user_id=? AND day=?", (key, day))
        return float(r["cpu_s"]) if r else 0.0

    def quota_add(self, key: str, day: str, cpu_s: float) -> float:
        with self.tx() as c:
            c.execute("INSERT INTO quota(user_id, day, cpu_s) VALUES (?,?,MAX(0, ?)) "
                      "ON CONFLICT(user_id, day) DO UPDATE SET cpu_s = MAX(0, cpu_s + ?)",
                      (key, day, cpu_s, cpu_s))
        return self.quota_used(key, day)

    # ------------------------------------------------------------------ auth bookkeeping
    def put_magic(self, token_sha: str, email: str, mode: str, next_path: Optional[str], ttl_s: float) -> None:
        t = now()
        with self.tx() as c:
            c.execute("INSERT INTO magic_links(token_sha, email, mode, next, created, expires) VALUES (?,?,?,?,?,?)",
                      (token_sha, email, mode, next_path, t, t + ttl_s))

    def consume_magic(self, token_sha: str) -> Optional[sqlite3.Row]:
        """Single use: returns the row once, and only before expiry."""
        with self.tx() as c:
            r = c.execute("SELECT * FROM magic_links WHERE token_sha=? AND used=0 AND expires>?",
                          (token_sha, now())).fetchone()
            if r is None:
                return None
            c.execute("UPDATE magic_links SET used=1 WHERE token_sha=?", (token_sha,))
        return r

    def put_state(self, state: str, provider: str, mode: str, next_path: Optional[str], ttl_s: float) -> None:
        t = now()
        with self.tx() as c:
            c.execute("INSERT INTO oauth_states(state, provider, mode, next, created, expires) VALUES (?,?,?,?,?,?)",
                      (state, provider, mode, next_path, t, t + ttl_s))

    def consume_state(self, state: str, provider: str) -> Optional[sqlite3.Row]:
        with self.tx() as c:
            r = c.execute("SELECT * FROM oauth_states WHERE state=? AND provider=? AND expires>?",
                          (state, provider, now())).fetchone()
            c.execute("DELETE FROM oauth_states WHERE state=?", (state,))
        return r

    def put_login_code(self, code_sha: str, user_id: str, ttl_s: float) -> None:
        t = now()
        with self.tx() as c:
            c.execute("INSERT INTO login_codes(code_sha, user_id, created, expires) VALUES (?,?,?,?)",
                      (code_sha, user_id, t, t + ttl_s))

    def consume_login_code(self, code_sha: str) -> Optional[sqlite3.Row]:
        with self.tx() as c:
            r = c.execute("SELECT * FROM login_codes WHERE code_sha=? AND used=0 AND expires>?",
                          (code_sha, now())).fetchone()
            if r is None:
                return None
            c.execute("UPDATE login_codes SET used=1 WHERE code_sha=?", (code_sha,))
        return r
