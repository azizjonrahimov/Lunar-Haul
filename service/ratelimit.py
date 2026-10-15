"""In-memory token buckets per (route group, client). One process, no Redis: the research note's
"slowapi with the memory backend" tier. Returns the seconds to wait when a bucket is empty so the
API can answer 429 with Retry-After. Buckets idle for an hour are pruned.
"""
from __future__ import annotations

import math
import threading
import time
from typing import Dict, Optional, Tuple

from .util import parse_rate


class RateLimiter:
    def __init__(self, rules: Dict[str, str]):
        self.rules: Dict[str, Tuple[int, float]] = {k: parse_rate(v) for k, v in rules.items()}
        if "default" not in self.rules:
            self.rules["default"] = (240, 60.0)
        self._buckets: Dict[Tuple[str, str], Tuple[float, float]] = {}   # (group, client) -> (tokens, updated)
        self._lock = threading.Lock()
        self._last_prune = time.monotonic()

    def rule(self, group: str) -> Tuple[int, float]:
        return self.rules.get(group, self.rules["default"])

    def check(self, group: str, client: str, cost: float = 1.0) -> Optional[int]:
        """Consume one token; None when allowed, else whole seconds until a token is available."""
        n, period = self.rule(group)
        rate = n / period                      # tokens per second
        now = time.monotonic()
        with self._lock:
            tokens, updated = self._buckets.get((group, client), (float(n), now))
            tokens = min(float(n), tokens + (now - updated) * rate)
            if tokens >= cost:
                self._buckets[(group, client)] = (tokens - cost, now)
                retry = None
            else:
                self._buckets[(group, client)] = (tokens, now)
                retry = max(1, int(math.ceil((cost - tokens) / rate)))
            if now - self._last_prune > 300:
                self._prune(now)
        return retry

    def _prune(self, now: float) -> None:
        self._last_prune = now
        for key, (_, updated) in list(self._buckets.items()):
            if now - updated > 3600:
                del self._buckets[key]

    def describe(self) -> Dict[str, str]:
        return {k: f"{n}/{int(p)}s" for k, (n, p) in sorted(self.rules.items())}
