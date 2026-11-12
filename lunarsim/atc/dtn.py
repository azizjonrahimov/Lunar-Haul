"""Store-and-forward, custody and the lost-link rule on the radio mesh (B-94, problems 4 and 6, experiment E54).

A message-level simulation over a recorded month (the engine's trajectories and events; tools/atc/run_e54.py), at
the contact plan's resolution (one step = the trajectory grid, 60 s). Research note 03: sections Q3, C5, C7, D, E7.

Contact plan. Nodes: the vehicles and the base computer's 10 m mast. A link exists in a step when the two are in DEM
line of sight within the radio range (B-70 mesh; lunarsim.atc.pnt.LOS); the plan is "predicted" in the sense of
note 03 Q3 (scheduled links from known routes): every protocol may use the current step's links.

Protocols (per message; per-hop loss p, independent per transmission, as lunarsim/atc/messages.py):
- "drop_retry": end to end. At its creation and then every `retry_s` (180 s, the engines' RETRY_H) the sender tries
  once along the current shortest path: delivered if every hop gets through, else dropped and tried again; at most
  `max_tries` (5, Assumed) tries and never after the message's lifetime. No storage on the way.
- "sf" (store-and-forward with custody, BPv7 + custody signalling [RFC9171, LNIS5]): hop by hop. The node holding the
  bundle sends it to the next node on the current shortest path; a lost transmission is repeated after the custody
  timer (10 s surface, note 03 D) while the link lasts; with no path it waits in the node's queue (byte limit 64 MB,
  note 03 D "DTN store per rover"; a full queue drops the newest); it expires at its lifetime.
- "sf_ll": "sf" plus the lost-link ladder of note 03 C7 (T1 5 s, T2 30 s, T_hold 600 s, return at half speed to the
  last link point, T_rdv 3,600 s; note 03 D). Effects modelled: a vehicle without a path to the base for T_hold
  retraces to its last link point, so its isolation ends after T_hold + 2 x (driving time since it lost the link)
  when that is sooner than its recorded isolation (it then waits there, linked, until its recorded path reconnects);
  the base releases the vehicle's reservations at their timeout (stuck reservations end) and re-auctions its tasks
  when its heartbeat is lost for the lease. Stated limitation: the return is applied to the contact plan, not re-run
  in the engine (the engine's later dispatch does not see the vehicle's detour).

Outcomes: messages delivered / expired by kind (an award that expires = a lost job, re-auctioned after the lease),
delivery delay, the base's age of information of each vehicle's STATUS (note 03 E7), reservations left stuck past
their timeout (holder unheard at t_out + grace 60 s, note 03 D "Reservation grace"), and Earth-bound bundles across a
14-day Earth blackout.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

DEFAULTS = {
    "custody_timer_s": 10.0,       # note 03 D "Custody retransmission timer, surface" 10 s (Assumed, 3-60)
    "retry_s": 180.0,              # regimes.RETRY_H (0.05 h)
    "max_tries": 5,                # Assumed: drop-and-retry gives up after 5 tries
    "queue_bytes": 64e6,           # note 03 D "DTN store per rover" 64 MB (Assumed, 8-512)
    "hop_latency_s": 0.010,        # lunarsim.atc.messages.HOP_LATENCY_S
    "t_hold_s": 600.0,             # note 03 D "Lost link: T_hold" (Project R7)
    "t_rdv_s": 3600.0,             # note 03 D "Lost link: T_rdv" (auction timeout)
    "return_speed_factor": 0.5,    # note 03 C7 RETURN: half speed
    "grace_s": 60.0,               # note 03 D "Reservation grace (late)" 60 s (Project R9)
    "lease_s": 3600.0,             # an awarded task returns to the pool after the lease (Project 1 h, note 03 C7)
    "status_period_s": 10.0,       # STATUS 0.1 Hz (note 03 C2)
}
BASE = -1                          # node id of the base mast in messages


def contact_plan(tr, los, base_idx: int, mast_h: float = 10.0) -> np.ndarray:
    """(T, n + 1, n + 1) bool adjacency per step; node n is the base mast."""
    T, N = tr.idx.shape
    A = np.zeros((T, N + 1, N + 1), bool)
    for k in range(T):
        ix = tr.idx[k]
        for i in range(N):
            A[k, i, N] = A[k, N, i] = bool(los.mast[float(tr.ant[i])][ix[i]]) or int(ix[i]) == base_idx
            for j in range(i + 1, N):
                if los.mat[(float(tr.ant[i]), float(tr.ant[j]))][ix[i], ix[j]]:
                    A[k, i, j] = A[k, j, i] = True
    return A


def hops_to(A_k: np.ndarray, dst: int) -> np.ndarray:
    """BFS hop counts to dst in one step's adjacency (-1 unreachable)."""
    n = A_k.shape[0]
    h = np.full(n, -1)
    h[dst] = 0
    fr = [dst]
    while fr:
        nx = []
        for u in fr:
            for w in np.nonzero(A_k[u])[0]:
                if h[w] < 0:
                    h[w] = h[u] + 1
                    nx.append(w)
        fr = nx
    return h


def lost_link_plan(A: np.ndarray, tr, p: Optional[dict] = None) -> Tuple[np.ndarray, Dict[str, float]]:
    """The contact plan under the lost-link ladder (module docstring): a vehicle isolated from the base for longer
    than T_hold + 2 x its driving time since the last link regains a link to the base (direct, as at its last link
    point) from then until its recorded isolation ends."""
    p = dict(DEFAULTS, **(p or {}))
    T, n1, _ = A.shape
    N = n1 - 1
    dt = tr.dt_s
    A2 = A.copy()
    linked = np.zeros((T, N), bool)
    for k in range(T):
        linked[k] = hops_to(A[k], N)[:N] >= 0
    stats = {"returns": 0, "isolation_h_saved": 0.0}
    for i in range(N):
        k = 0
        while k < T:
            if linked[k, i]:
                k += 1
                continue
            k0 = k
            while k < T and not linked[k, i]:
                k += 1
            k1 = k                                           # isolated over [k0, k1)
            drive_back = 0.0
            j = k0 - 1
            back = (tr.ds[max(0, k0 - 60):k0, i] > 0).sum() * dt   # driving in the hour before the loss (bounded)
            ret = p["t_hold_s"] + back / p["return_speed_factor"]
            kr = k0 + int(math.ceil(ret / dt))
            if kr < k1:
                A2[kr:k1, i, N] = A2[kr:k1, N, i] = True
                stats["returns"] += 1
                stats["isolation_h_saved"] += (k1 - kr) * dt / 3600.0
    return A2, stats


@dataclass
class Msg:
    mid: int
    kind: str
    src: int                       # vehicle index or BASE
    dst: int
    t0: float                      # creation (s from the window start)
    size: int
    life_s: float
    at: int = 0                    # current holder (node index; resolved at run time)
    tries: int = 0
    t_done: Optional[float] = None
    expired: bool = False


def simulate(A: np.ndarray, msgs: Sequence[Msg], protocol: str, loss: float, rng: np.random.Generator,
             dt_s: float, p: Optional[dict] = None, earth_up=None) -> List[Msg]:
    """Deliver the messages over the contact plan A (T, n + 1, n + 1). Node n is the base mast; a message to "EARTH"
    (dst = -2) needs the base and earth_up(k) for its last hop. Returns the messages with t_done / expired set."""
    p = dict(DEFAULTS, **(p or {}))
    T, n1, _ = A.shape
    N = n1 - 1
    node = lambda x: N if x == BASE else x
    out = [Msg(m.mid, m.kind, m.src, m.dst, m.t0, m.size, m.life_s, node(m.src)) for m in msgs]
    order = sorted(range(len(out)), key=lambda i: out[i].t0)
    active: List[int] = []
    q_bytes = np.zeros(n1)
    nxt = 0
    hop_cache: Dict[Tuple[int, int], np.ndarray] = {}

    def hops(k, dst):
        key = (k, dst)
        if key not in hop_cache:
            hop_cache[key] = hops_to(A[k], dst)
        return hop_cache[key]
    per_step = max(1, int(round(dt_s / p["custody_timer_s"])))
    q = 1.0 - loss
    for k in range(T):
        t_lo, t_hi = k * dt_s, (k + 1) * dt_s
        while nxt < len(order) and out[order[nxt]].t0 < t_hi:
            i = order[nxt]
            m = out[i]
            if protocol != "drop_retry" and q_bytes[m.at] + m.size > p["queue_bytes"]:
                m.expired = True                              # full store: the newest is dropped
            else:
                active.append(i)
                if protocol != "drop_retry":
                    q_bytes[m.at] += m.size
            nxt += 1
        if k % 60 == 0 and len(hop_cache) > 4096:
            hop_cache.clear()
        still = []
        for i in active:
            m = out[i]
            if m.t_done is not None:
                continue
            if t_lo >= m.t0 + m.life_s:
                m.expired = True
                if protocol != "drop_retry":
                    q_bytes[m.at] -= m.size
                continue
            if m.dst == -2:                                   # Earth-bound: base first, then the Earth link
                dst_node = N
            else:
                dst_node = node(m.dst)
            if protocol == "drop_retry":
                t_try = m.t0 + m.tries * p["retry_s"]
                if t_try >= t_hi or m.tries >= p["max_tries"]:
                    if m.tries >= p["max_tries"]:
                        m.expired = True
                        continue
                    still.append(i)
                    continue
                m.tries += 1
                h = hops(k, dst_node)[m.at]
                ok = h >= 0 and (m.dst != -2 or earth_up(k))
                if ok:
                    hh = int(h) + (1 if m.dst == -2 else 0)
                    if rng.random() < q ** hh:
                        m.t_done = max(t_try, t_lo) + hh * p["hop_latency_s"]
                        continue
                still.append(i)
                continue
            # store-and-forward: hop by hop within the step, custody retransmissions every custody_timer_s
            attempts = per_step
            t_now = max(m.t0, t_lo)
            while attempts > 0 and m.t_done is None:
                if m.at == dst_node:
                    if m.dst == -2:
                        if not earth_up(k):
                            break
                        if rng.random() < q:
                            m.t_done = t_now + p["hop_latency_s"]
                            q_bytes[m.at] -= m.size
                        else:
                            t_now += p["custody_timer_s"]
                        attempts -= 1
                        continue
                    m.t_done = t_now
                    q_bytes[m.at] -= m.size
                    break
                hd = hops(k, dst_node)
                if hd[m.at] < 0:
                    break                                     # no path now: hold the bundle
                cand = [w for w in np.nonzero(A[k, m.at])[0] if hd[w] == hd[m.at] - 1]
                w = min(cand)
                attempts -= 1
                if rng.random() < q:
                    q_bytes[m.at] -= m.size
                    q_bytes[w] += m.size
                    m.at = int(w)
                    t_now += p["hop_latency_s"]
                else:
                    t_now += p["custody_timer_s"]
            if m.t_done is None:
                still.append(i)
        active = still
    for i in active:
        m = out[i]
        if m.t_done is None:
            m.expired = True
    return out


def base_hops(A: np.ndarray) -> np.ndarray:
    """(T, n) hop counts of every vehicle to the base mast per step (-1 unreachable)."""
    T, n1, _ = A.shape
    return np.stack([hops_to(A[k], n1 - 1)[:n1 - 1] for k in range(T)])


def age_of_information(A: np.ndarray, loss: float, protocol: str, rng: np.random.Generator, dt_s: float,
                       p: Optional[dict] = None, hb: Optional[np.ndarray] = None) -> np.ndarray:
    """Per vehicle: time-average age (s) of its newest STATUS at the base (note 03 E7). Each step the vehicle sends
    dt / status_period updates; with a path of h hops an update arrives with probability (1 - loss)^h ("drop_retry":
    beacons are never queued nor retried) or, store-and-forward, (1 - loss^m)^h with m custody attempts per hop in
    the step (only the newest matters: a stored old update does not lower the age). No path: no update. hb: the
    precomputed base_hops(A)."""
    p = dict(DEFAULTS, **(p or {}))
    T, n1, _ = A.shape
    N = n1 - 1
    hb = base_hops(A) if hb is None else hb
    n_up = max(1, int(round(dt_s / p["status_period_s"])))
    m_att = max(1, int(round(dt_s / p["custody_timer_s"])))
    q1 = (1.0 - loss) if protocol == "drop_retry" else (1.0 - loss ** m_att)
    last = np.zeros(N)                                        # generation time of the newest update at the base
    acc = np.zeros(N)
    for k in range(T):
        h = hb[k]
        ps = np.where(h >= 0, q1 ** np.maximum(h, 0), 0.0)
        got = rng.random((n_up, N)) < ps[None, :]
        anyg = got.any(axis=0)
        if anyg.any():
            j = n_up - 1 - np.argmax(got[::-1], axis=0)       # the newest update that got through
            last = np.where(anyg, k * dt_s + (j + 1) * p["status_period_s"], last)
        # the age over the step, from the newest generation time known at its start (a slight upward bias, the same
        # for every protocol)
        a0 = np.maximum(k * dt_s - last, 0.0)
        acc += a0 * dt_s + 0.5 * dt_s * dt_s
    return acc / (T * dt_s)
