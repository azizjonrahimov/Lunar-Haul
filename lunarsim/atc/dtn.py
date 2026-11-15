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
  note 03 D "DTN store per rover"; a full queue, at the sender or at a relay, refuses the bundle: at creation it is
  dropped, on forwarding the hop is refused and retried after the custody timer). Time is kept per bundle within a
  step: each failed transmission costs the custody timer, a step gives a bundle only the attempts that fit before
  the step ends, and a bundle is never delivered after its lifetime (B-118 N3).
- "sf_ll": "sf" plus the lost-link ladder of note 03 C7 (T1 5 s, T2 30 s, T_hold 600 s, return at half speed to the
  last link point, T_rdv 3,600 s; note 03 D). Rule "papers" (the default; as the papers state it, corrected after
  code review on 13 Nov 2026, B-118 N6): a vehicle without a path to the base for T_hold retraces, at half speed, the
  path it drove since it lost the link, so it is linked again (direct, as at its last link point) at
  loss + T_hold + 2 x (its recorded driving time between the loss and the loss + T_hold), when that is sooner than
  its recorded isolation (it then waits there, linked, until its recorded path reconnects). The replay uses the
  recorded trajectories, so the vehicle does not stop at the next safe point as note 03 C7 says: the retrace distance
  is an upper reading of the rule. Rule "pre_review" (kept for comparison): T_hold + 2 x the driving time in the
  hour before the loss (the code before 13 Nov 2026). With either rule the base does not release the vehicle's
  reservations: at their timeout plus grace it marks the segments unconfirmed, to be entered only at caution speed
  (decision B1; no reservation stays blocked), and re-auctions its tasks when its heartbeat is lost for the lease.
  Stated limitation: the return is applied to the contact plan, not re-run in the engine (the engine's later
  dispatch does not see the vehicle's detour).

Outcomes: messages delivered, expired or censored by kind. Expired = its lifetime ended undelivered inside the window
(an award that expires = a lost job, re-auctioned after the lease). Censored (B-118 N4) = still undelivered and alive
at the window's end, or created at or after it: its fate is unknown, and it is not a loss. Also: delivery delay,
the base's age of information of each vehicle's STATUS (note 03 E7), reservations left stuck past their timeout
(holder unheard at t_out + grace 60 s, note 03 D "Reservation grace"), and Earth-bound bundles across a 14-day Earth
blackout.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
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
    "return_rule": "papers",       # B-118 N6: "papers" (default; see lost_link_plan) or "pre_review" (the old code)
}
RETURN_RULES = ("papers", "pre_review")
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
    """The contact plan under the lost-link ladder (module docstring): a vehicle isolated from the base at step k0
    regains a link to the base (direct, as at its last link point) from k0 + T_hold + 2 x D until its recorded
    isolation ends, when that is sooner. D under p["return_rule"]: "papers" (default) the recorded driving time
    between the loss and the loss + T_hold; "pre_review" the driving time in the hour before the loss. Windows are
    in seconds, converted with the plan's dt."""
    p = dict(DEFAULTS, **(p or {}))
    if p["return_rule"] not in RETURN_RULES:
        raise ValueError(f"return_rule {p['return_rule']!r} not in {RETURN_RULES}")
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
            if p["return_rule"] == "papers":                 # driven since the loss, up to the hold timer
                kh = k0 + int(math.ceil(p["t_hold_s"] / dt))
                back = (tr.ds[k0:min(kh, T), i] > 0).sum() * dt
            else:                                            # pre_review: the hour before the loss
                back = (tr.ds[max(0, k0 - int(round(3600.0 / dt))):k0, i] > 0).sum() * dt
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
    censored: bool = False         # B-118 N4: alive and undelivered at the window's end (or created after it)
    t_next: float = 0.0            # B-118 N3: earliest time of the bundle's next transmission


PROTOCOLS = ("drop_retry", "sf", "sf_ll")     # B-120 G: the protocols simulate() accepts ("sf_ll" runs as "sf")


def simulate(A: np.ndarray, msgs: Sequence[Msg], protocol: str, loss: float, rng: np.random.Generator,
             dt_s: float, p: Optional[dict] = None, earth_up=None) -> List[Msg]:
    """Deliver the messages over the contact plan A (T, n + 1, n + 1). Node n is the base mast; a message to "EARTH"
    (dst = -2) needs the base and earth_up(k) for its last hop. Returns the messages with t_done, expired or censored
    set: t_done = delivered (at or before t0 + life_s); expired = undelivered and with no attempt left that could
    deliver it: its lifetime ended inside the window (t0 + life_s <= T dt_s, the end itself included, B-120 B), or
    it is out of tries (drop_retry), or its next attempt falls after its lifetime (drop_retry: the next try
    t0 + tries retry_s > t0 + life_s; store-and-forward: the next transmission or custody retransmission, or the
    arrival of the last hop, at or after t0 + life_s), or it was dropped by a full store at creation. The rule on the
    next attempt is applied in every step, the last one included, so a bundle whose lifetime ends after the window's
    end but before its next attempt (at most one retry_s or custody_timer_s after the end) is expired, not
    censored (B-121: stated here as the code has it; no code change). censored = undelivered, still alive at the
    window's end (t0 + life_s > T dt_s) and with an attempt still possible inside its lifetime, or created at or
    after the end: its outcome is not known. protocol: "drop_retry", or "sf" (store-and-forward with custody; "sf_ll", the
    same model run on a lost_link_plan output, is accepted as a name for it); anything else is refused (B-120 G:
    before, every string but "drop_retry" ran as sf). Stores (store-and-forward): every node holds at most
    queue_bytes; a full store drops a new bundle at creation, and a full relay refuses custody until it has room;
    the base counts as a relay for an Earth-bound bundle, which it stores until the Earth link (B-120 G: before, the
    base took every Earth-bound bundle whatever its store held); a bundle for the base itself is delivered at once."""
    if protocol not in PROTOCOLS:
        raise ValueError(f"unknown protocol {protocol!r}; expected one of {PROTOCOLS}")
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
            deadline = m.t0 + m.life_s
            if t_lo >= deadline:
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
                if m.tries >= p["max_tries"] or t_try > deadline:
                    m.expired = True                          # out of tries, or the next try is past the lifetime
                    continue
                if t_try >= t_hi:
                    still.append(i)
                    continue
                m.tries += 1
                h = hops(k, dst_node)[m.at]
                ok = h >= 0 and (m.dst != -2 or earth_up(k))
                if ok:
                    hh = int(h) + (1 if m.dst == -2 else 0)
                    if rng.random() < q ** hh:
                        t_arr = max(t_try, t_lo) + hh * p["hop_latency_s"]
                        if t_arr <= deadline:
                            m.t_done = t_arr
                            continue
                still.append(i)
                continue
            # store-and-forward: hop by hop, custody retransmissions every custody_timer_s, with the bundle's own
            # clock (B-118 N3): only the attempts that start inside this step and inside the lifetime
            t_now = max(m.t0, t_lo, m.t_next)
            while m.t_done is None and t_now < t_hi and t_now < deadline:
                if m.at == dst_node:
                    if m.dst == -2:
                        if not earth_up(k):
                            break
                        if rng.random() < q:
                            t_arr = t_now + p["hop_latency_s"]
                            if t_arr <= deadline:
                                m.t_done = t_arr
                                q_bytes[m.at] -= m.size
                            else:
                                t_now = t_arr
                        else:
                            t_now += p["custody_timer_s"]
                        continue
                    m.t_done = t_now
                    q_bytes[m.at] -= m.size
                    break
                hd = hops(k, dst_node)
                if hd[m.at] < 0:
                    break                                     # no path now: hold the bundle
                cand = [w for w in np.nonzero(A[k, m.at])[0] if hd[w] == hd[m.at] - 1]
                w = min(cand)
                # C11: a full relay refuses custody; try again later. The base takes custody of an Earth-bound
                # bundle and stores it until the Earth link, so its store is bounded too (B-120 G: before, unbounded)
                if (w != dst_node or m.dst == -2) and q_bytes[w] + m.size > p["queue_bytes"]:
                    t_now += p["custody_timer_s"]
                    continue
                if rng.random() < q:
                    q_bytes[m.at] -= m.size
                    q_bytes[w] += m.size
                    m.at = int(w)
                    t_now += p["hop_latency_s"]
                    if m.at == dst_node and m.dst != -2:      # arrival is recorded now, not in the next step
                        if t_now <= deadline:
                            m.t_done = t_now
                            q_bytes[m.at] -= m.size
                        break
                else:
                    t_now += p["custody_timer_s"]
            m.t_next = t_now
            if m.t_done is None:
                if t_now >= deadline:                         # lifetime over inside the window
                    m.expired = True
                    q_bytes[m.at] -= m.size
                    continue
                still.append(i)
        active = still
    t_end = T * dt_s
    for i in active:                                          # B-118 N4: alive at the window's end: censored
        m = out[i]
        if m.t_done is None and not m.expired:
            if m.t0 + m.life_s <= t_end:                      # B-120 B: its whole lifetime was inside the window
                m.expired = True                              # (deadline at t_end included): the outcome is known
                if protocol != "drop_retry":
                    q_bytes[m.at] -= m.size
            else:
                m.censored = True
    for m in out:                                             # created at or after the window's end: censored
        if m.t_done is None and not m.expired and m.t0 >= t_end:
            m.censored = True
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
    per = p["status_period_s"]
    for k in range(T):
        h = hb[k]
        ps = np.where(h >= 0, q1 ** np.maximum(h, 0), 0.0)
        got = rng.random((n_up, N)) < ps[None, :]
        # B-118 N5: the exact integral of the age t - last(t) over the step, with last(t) moving to each update's
        # generation time when it arrives (arrival = generation: hop latency 10 ms is neglected). Before, the step's
        # newest update was applied first, which floored the age at dt/2 = 30 s whatever the status period.
        cur = k * dt_s
        for j in range(n_up):
            g = k * dt_s + (j + 1) * per
            acc += 0.5 * ((g - last) ** 2 - (cur - last) ** 2)
            last = np.where(got[j], g, last)
            cur = g
        t_end = (k + 1) * dt_s
        if t_end > cur:
            acc += 0.5 * ((t_end - last) ** 2 - (cur - last) ** 2)
    return acc / (T * dt_s)
