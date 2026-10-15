"""Small helpers shared by the service modules: ULIDs, canonical JSON, hashing, clock."""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import secrets
import time
from typing import Any

_B32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"   # Crockford, as the ULID spec


def ulid(ms: int | None = None) -> str:
    """A 26-character ULID: 48-bit millisecond timestamp + 80 random bits, Crockford base32."""
    t = int(time.time() * 1000) if ms is None else int(ms)
    value = (t << 80) | int.from_bytes(os.urandom(10), "big")
    out = []
    for _ in range(26):
        out.append(_B32[value & 31])
        value >>= 5
    return "".join(reversed(out))


def is_ulid(s: Any) -> bool:
    return isinstance(s, str) and len(s) == 26 and all(c in _B32 for c in s)


def _canon(x: Any, ordered_keys: tuple, keep: bool = False) -> Any:
    if isinstance(x, dict):
        items = list(x.items()) if keep else sorted(x.items(), key=lambda kv: str(kv[0]))
        return {str(k): _canon(v, ordered_keys, keep or k in ordered_keys) for k, v in items}
    if isinstance(x, (list, tuple)):
        return [_canon(v, ordered_keys, keep) for v in x]
    return x


def canonical_json(obj: Any, ordered_keys: tuple = ()) -> bytes:
    """Canonical JSON bytes for hashing: sorted keys, no whitespace, UTF-8, no NaN/inf.

    Floats use Python's repr (the shortest string that round-trips, identical on every
    CPython >= 3.1 platform), ints stay ints; callers pass values through
    lunarsim.server.clean() first so numpy scalars and NaN never reach the encoder.

    `ordered_keys`: names of mappings whose key order is *semantic* and must survive. The engine
    iterates Scenario.landings_per_year in dict order when it draws the landing schedule, so
    sorting that mapping would change the random draw sequence and the results; its insertion
    order is therefore part of the scenario's identity and is kept as written."""
    return json.dumps(_canon(obj, tuple(ordered_keys)), sort_keys=False, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def new_token(nbytes: int = 32) -> str:
    """URL-safe random token, 256 bits by default (session ids, magic links, login codes)."""
    return secrets.token_urlsafe(nbytes)


def now() -> float:
    return time.time()


def iso(ts: float | None = None) -> str:
    """UTC ISO-8601 with a Z suffix, second precision."""
    d = _dt.datetime.fromtimestamp(now() if ts is None else ts, _dt.timezone.utc)
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def day_key(ts: float | None = None) -> str:
    """The quota day: UTC calendar date."""
    d = _dt.datetime.fromtimestamp(now() if ts is None else ts, _dt.timezone.utc)
    return d.strftime("%Y-%m-%d")


def seconds_to_next_utc_day(ts: float | None = None) -> int:
    t = now() if ts is None else ts
    d = _dt.datetime.fromtimestamp(t, _dt.timezone.utc)
    nxt = (d + _dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((nxt - d).total_seconds()) + 1)


def parse_rate(spec: str) -> tuple[int, float]:
    """'5/minute' | '60/hour' | '10/second' | '100/day' | '3/30s' -> (count, period seconds)."""
    n, _, per = spec.partition("/")
    n = int(n)
    per = per.strip().lower()
    table = {"second": 1.0, "sec": 1.0, "s": 1.0, "minute": 60.0, "min": 60.0, "m": 60.0,
             "hour": 3600.0, "h": 3600.0, "day": 86400.0, "d": 86400.0}
    if per in table:
        return n, table[per]
    for suffix, mult in (("s", 1.0), ("m", 60.0), ("h", 3600.0), ("d", 86400.0)):
        if per.endswith(suffix) and per[:-1].isdigit():
            return n, int(per[:-1]) * mult
    raise ValueError(f"bad rate spec {spec!r} (expected e.g. '5/minute')")
