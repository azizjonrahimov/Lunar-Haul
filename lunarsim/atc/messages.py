"""Robot-to-robot message delivery (B-72): per-hop loss, multi-hop relay, latency and a message counter.

A message travelling h hops (through any robot or the base mast) is delivered when every hop gets through. Each hop
is one transmission and is lost independently with probability `loss` ("bernoulli"), or by a Gilbert-Elliott chain
over the sequence of transmissions ("burst": a good state that loses nothing and a bad state that loses
everything, mean bad run `mean_burst` transmissions, stationary loss `loss`). A lost message is not retried within
the same decision epoch (`retries` = 0); it is sent again at the next one.

Constants (Assumed, B-72 task): hop latency 10 ms (Wi-Fi / LTE practice); mean burst 10 messages.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

HOP_LATENCY_S = 0.010            # Assumed (B-72 task; research note Table A: ~10 ms surface hop)
MEAN_BURST = 10.0                # Assumed (B-72 task): mean length of a loss burst, in messages
LOSS_LEVELS = (0.0, 0.10, 0.25, 0.40)


class Channel:
    def __init__(self, loss: float = 0.0, model: str = "bernoulli", mean_burst: float = MEAN_BURST,
                 retries: int = 0, rng: Optional[np.random.Generator] = None):
        if not 0.0 <= loss < 1.0:
            raise ValueError("message loss must be in [0, 1)")
        if model not in ("bernoulli", "burst"):
            raise ValueError("message model must be 'bernoulli' or 'burst'")
        self.loss, self.model, self.retries = float(loss), model, int(retries)
        self.rng = rng if rng is not None else np.random.default_rng(0)
        # Gilbert-Elliott: P(bad -> good) = 1 / mean_burst; P(good -> bad) from the stationary bad share = loss
        self.p_bg = 1.0 / float(mean_burst)
        self.p_gb = self.loss * self.p_bg / (1.0 - self.loss) if self.loss > 0 else 0.0
        self.bad = False
        self.sent = 0                 # transmissions (hops x attempts)
        self.messages = 0
        self.lost = 0
        self.latency_s = 0.0

    def _hop_ok(self) -> bool:
        self.sent += 1
        if self.loss <= 0.0:
            return True
        if self.model == "bernoulli":
            return bool(self.rng.random() >= self.loss)
        self.bad = (self.rng.random() >= self.p_bg) if self.bad else (self.rng.random() < self.p_gb)
        return not self.bad

    def send(self, hops: int) -> Tuple[bool, float]:
        """Deliver one message over `hops` hops (0 = local, always delivered). Returns (delivered, latency s)."""
        self.messages += 1
        if hops <= 0:
            return True, 0.0
        for _ in range(self.retries + 1):
            ok = True
            for _h in range(int(hops)):
                if not self._hop_ok():
                    ok = False
                    break
            if ok:
                lat = hops * HOP_LATENCY_S
                self.latency_s += lat
                return True, lat
        self.lost += 1
        return False, 0.0
