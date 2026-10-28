"""C_AUCTION (B-73): a decentralised sequential single-item auction over the robot mesh, and cross-owner team lifts.

Each decision epoch:
- Mesh components: robots (B-70 radio, positions as in regimes.py) and the BASE mast while the base computer is up
  (it fails as in C_LEADER, but nothing waits for a leader). A component knows every waiting item if it holds the
  mast (the base computer has the manifests), otherwise only the items at sites where one of its robots stands.
- In each component the robots run the marketplace's auction (Otte et al.: sequential single-item rounds with the
  previous winners rebroadcast every round): every free robot bids its best bundle (the marketplace's marginal
  insertion cost, dispatch._try_bundle); each bid is flooded to the others (message loss per hop,
  lunarsim.atc.messages). A robot that missed the best bid and sees its own as the best it heard believes it won:
  if its items do not overlap the true winner's it is a parallel winner; if they do, the conflict is settled by the
  CBBA rule (better bid, then lower id) when the winner's rebroadcast reaches it in one of the remaining rounds;
  otherwise it drives to the pad for nothing (a wasted trip, counted). Round limit: max(N_items, N_robots) x mesh
  diameter (N_items x diameter as specified, raised to N_robots so that a perfect mesh never cuts the auction short).
- Bundle depth d (CBBA-lite): after the immediate round a robot keeps bidding for up to d - 1 future jobs from the
  end of its plan; won future jobs are claims, hidden from the robots of its component and started when it is
  free, if their items are still waiting (else dropped as stale).
- Team lifts (marketplace step 1) need both robots to agree: with `commit` (two-phase commit) the proposer sends a
  proposal, the partner says yes, the proposer commits; a lost proposal or yes means no team this epoch; a lost
  commit means the partner never comes: the proposer drives to the pad, waits `timeout_h` and gives up (a failed
  meeting; the item returns to the pool). Without `commit` the proposer goes on the proposal alone and fails the
  same way when it is lost. `team_scope` "same_owner" pairs only robots of one owner.
- Lost-link procedure as in regimes.py: a free robot in a component without the mast rallies to a site that sees it.
With perfect radio, no loss, depth 1 and no base failures this is exactly the pooled marketplace (tested).

The small-instance checks (bounds_check) compare SSI with the Hungarian optimum (min total cost, one item per robot)
and CBBA-lite (greedy marginal score, bundles up to depth) with the brute-force optimum score.
"""
from __future__ import annotations

import copy
import itertools
import math
from collections import deque
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

TIMEOUT_H = 1.0                  # Assumed (B-73 task): rendezvous timeout, sweep 0.5-2 h
RETRY_H = 0.05                   # as regimes.RETRY_H: the base computer resends a lost decision 3 min later


# ------------------------------------------------------------------------------------------------- engine side
def _components(st, sim, t):
    from .regimes import ANT_MAST_M
    alive = [v for v in sim.vehicles if v.alive]
    nodes = st._robot_nodes(sim, t, alive)
    if st.base_up(t):
        nodes = nodes + [("BASE", st.site_index("BASE"), ANT_MAST_M)]
    adj = st._graph(nodes)
    comps, seen = [], set()
    for k, _, _ in nodes:
        if k in seen:
            continue
        h = st._bfs(adj, k)
        seen |= set(h)
        comps.append(set(h))
    return adj, comps, {k: p for k, p, _ in nodes}


class _Hops:
    def __init__(self, st, adj):
        self.st, self.adj, self.c = st, adj, {}

    def __call__(self, a, b) -> int:
        if a == b:
            return 0
        if a not in self.c:
            self.c[a] = self.st._bfs(self.adj, a)
        return self.c[a].get(b, 10 ** 6)

    def diameter(self, comp) -> int:
        return max((self(a, b) for a in comp for b in comp), default=0)


def dispatch(st, sim, waiting, free, inner_kw) -> List[Any]:
    from .. import dispatch as D
    from ..engine import Job
    t = sim.t
    c = st.cfg
    chan = st.channel
    adj, comps, pos = _components(st, sim, t)
    hops = _Hops(st, adj)
    jobs: List[Any] = []
    taken: set = set()
    started: set = set()
    wset = {id(x): x for x in waiting}
    # 1. claims from earlier epochs (depth > 1)
    for v in free:
        q = st.claims.get(v.id) or []
        while q:
            items, route = q.pop(0)
            if all(id(x) in wset and id(x) not in taken for x in items) and sum(x.mass_kg for x in items) <= v.cls.capacity_kg:
                jobs.append(Job([v], list(items), list(route), note="claim"))
                taken |= {id(x) for x in items}
                started.add(v.id)
                st.m["claims_run"] += 1
                break
            st.m["claims_stale"] += 1
    claimed_by = {id(x): vid for vid, q in st.claims.items() for items, _ in q for x in items}
    # 2. the auction, component by component
    for comp in sorted(comps, key=lambda s: min((k for k in s if k != "BASE"), default=10 ** 6)):
        fc = [v for v in free if v.id in comp and v.id not in started]
        if not fc:
            continue
        if "BASE" in comp:
            known = [x for x in waiting if id(x) not in taken]
        else:
            sites = {pos[k] for k in comp}
            known = [x for x in waiting if id(x) not in taken and st.site_index(x.origin) in sites]
            for v in fc:
                st._rally(sim, v, st.covered_sites(sim, _ant(v)) if st.base_up(t) else ["BASE"])
        known = [x for x in known if claimed_by.get(id(x)) is None or claimed_by[id(x)] not in comp]
        st.m["robots_seen"] += len(fc)
        st.m["robots_out_sum"] += sum(1 for v in fc if "BASE" not in comp)
        if not known:
            continue
        robots = [k for k in comp if k != "BASE"]
        limit = max(len(known), len(fc)) * max(1, hops.diameter(comp))
        sel = _Selector(st, hops, robots, limit)
        adj_fn, flush = _learned_hooks(st, sim, waiting, free, inner_kw, adj, comps, sel)
        jc = D.marketplace(sim, known, fc, selector=sel, team_hook=_team_hook(st, sim, hops), round_limit=limit,
                           bid_adjust=adj_fn, **inner_kw)
        flush()
        busy_now = {v.id for j in jc for v in j.vehicles}
        for v, pad in sel.wasted:
            if v.id not in busy_now and v.repos_target is None:
                sim.schedule_reposition(v, pad, t)
                st.m["wasted_trips"] += 1
        for j in jc:
            taken |= {id(x) for x in j.items + j.backhaul}
        jobs += jc
        if int(c["depth"]) > 1:
            _future_rounds(st, sim, [x for x in known if id(x) not in taken], comp, jc, hops, robots, inner_kw)
            claimed_by = {id(x): vid for vid, q in st.claims.items() for items, _ in q for x in items}
    return jobs


def _learned_hooks(st, sim, waiting, free, inner_kw, adj, comps, sel):
    """(bid_adjust, flush) for C_LEARNED (the policy's correction) and DAgger collection (oracle labels)."""
    if st.policy is None and st.collector is None:
        return None, (lambda: None)
    from .learned import features, next_landings, oracle_assignment
    base = next((cp for cp in comps if "BASE" in cp), set())
    ctx = {"base_comp": base, "degree": {k: len(v) for k, v in adj.items()}, "claims": st.claims,
           "next_landing": next_landings(sim)}
    urg = float(sim.sc.urgency_usd_per_h)
    teacher = None
    if st.collector is not None:
        key = ("teacher", sim.t, getattr(sim, "_dispatch_serial", 0))
        if getattr(st, "_teacher_key", None) != key:
            st._teacher, st._teacher_key = oracle_assignment(sim, waiting, free, inner_kw), key
        teacher = st._teacher
    buf: Dict[Tuple[int, int], List[Any]] = {}

    def adjust(sim, v, bundle, route, bid):
        x = features(sim, v, bundle, route, ctx)
        if teacher is not None:
            buf.setdefault((sel.round, v.id), []).append((x, -bid / urg, id(bundle[0]) in teacher.get(v.id, ())))
        if st.policy is None:
            return bid
        return bid - urg * float(st.policy(x))

    def flush():
        if teacher is None:
            return
        for rows in buf.values():
            pos = [i for i, r in enumerate(rows) if r[2]]
            if not pos:
                continue
            tgt = max(pos, key=lambda i: rows[i][1])               # the best-scoring oracle item (lowest hand bid)
            st.collector.add_group([r[0] for r in rows], [r[1] for r in rows], [int(i == tgt) for i in range(len(rows))])
        buf.clear()
    return adjust, flush


def _ant(v):
    from .regimes import antenna_m
    return antenna_m(v)


class _Selector:
    """Winners of one auction round under message loss (see the module docstring)."""

    def __init__(self, st, hops, robots, limit):
        self.st, self.hops, self.robots, self.limit = st, hops, robots, limit
        self.round = 0
        self.wasted: List[Tuple[Any, str]] = []

    def __call__(self, sim, offers):
        self.round += 1
        chan = self.st.channel
        best = offers[0]
        for o in offers[1:]:
            if o[0] < best[0]:
                best = o
        heard: Dict[int, set] = {}
        for o in offers:                                       # every bid flooded to the other robots
            r = o[1].id
            for s in self.robots:
                if s != r and chan.send(self.hops(r, s))[0]:
                    heard.setdefault(s, set()).add(r)
        winners, claimed = [best], {id(x) for x in best[2]}
        bids = {o[1].id: o for o in offers}
        left = max(0, self.limit - self.round)
        for o in offers:
            v = o[1]
            if o is best or best[1].id in heard.get(v.id, set()):
                continue
            mine = [bids[r] for r in heard.get(v.id, set()) if r in bids] + [o]
            if min(mine, key=lambda z: (z[0], z[1].id)) is not o:
                continue                                       # it heard a better bid than its own
            items = {id(x) for x in o[2]}
            if not (items & claimed):
                winners.append(o)                              # a parallel winner
                claimed |= items
                self.st.m["parallel_winners"] += 1
                continue
            self.st.m["conflicts"] += 1                        # CBBA: the winner's rebroadcast settles it
            if any(chan.send(self.hops(best[1].id, v.id))[0] for _ in range(left)):
                continue
            self.wasted.append((v, o[2][0].origin))
        return winners


def _team_hook(st, sim, hops):
    def hook(sim, job):
        a, b = job.vehicles[0], job.vehicles[1]
        h = hops(a.id, b.id)
        chan, c = st.channel, st.cfg
        if c.get("arbitrate") and hops("BASE", a.id) < 10 ** 6 and hops("BASE", b.id) < 10 ** 6:
            st.m["arbitrated"] = st.m.get("arbitrated", 0) + 1          # exploratory: one decision, a lease
            k = max(1, int(float(c["timeout_h"]) / RETRY_H))
            got = [any(chan.send(hops("BASE", v.id))[0] for _ in range(k)) for v in (a, b)]
            if all(got):
                return True, set()
            if not any(got):
                st.m["team_no_agreement"] += 1
                return False, set()
            return _failed_meeting(st, sim, a if got[0] else b, job.items[0].origin)
        if c["commit"]:
            if not (chan.send(h)[0] and chan.send(h)[0]):     # proposal, yes
                st.m["team_no_agreement"] += 1
                return False, set()
            if chan.send(h)[0]:                                # commit
                return True, set()
        elif chan.send(h)[0]:                                  # one-shot proposal heard
            return True, set()
        return _failed_meeting(st, sim, a, job.items[0].origin)
    return hook


def _failed_meeting(st, sim, v, pad):
    """The proposer drives to the pad, waits the rendezvous timeout and gives up; the item returns to the pool."""
    st.m["failed_meetings"] += 1
    if v.location != pad and not sim._reposition(v, pad):
        return False, {v.id}
    wait = float(st.cfg["timeout_h"])
    v.busy_until = max(v.busy_until, sim.t) + wait
    st.m["meeting_wait_h"] += wait
    sim._push(v.busy_until, "FREE", None)
    return False, {v.id}


def _plan_end(st, sim, v, jobs_now) -> Tuple[str, float]:
    """(site, hour) where v's commitments end: the claims queue, else this epoch's job, else its committed plan."""
    from ..engine import Job
    q = st.claims.get(v.id) or []
    if q:
        return q[-1][1][-1], st.claim_end.get(v.id, sim.t)
    for j in jobs_now:
        if v in j.vehicles:
            dur = sim.job_plan(j, sim.t)[0]
            return (j.backhaul[0].dest if j.backhaul else j.route[-1]), sim.t + dur
    return v.location, max(sim.t, v.busy_until)


def _future_rounds(st, sim, pool, comp, jobs_now, hops, robots, inner_kw) -> None:
    """Claims for up to depth - 1 future jobs per robot (bids from the end of its commitments)."""
    from .. import dispatch as D
    from ..engine import Job
    depth = int(st.cfg["depth"])
    vs = [v for v in sim.vehicles if v.alive and v.id in comp and not (getattr(sim, "p5", None) is not None and sim.p5.limited(v))]
    pool = list(pool)
    sel = _Selector(st, hops, robots, max(1, len(pool)) * max(1, hops.diameter(comp)))
    t_now = sim.t
    for _ in range(sel.limit):
        offers = []
        for v in vs:
            if len(st.claims.get(v.id) or []) >= depth - 1 or not pool:
                continue
            loc, t_end = _plan_end(st, sim, v, jobs_now)
            sh = copy.copy(v)
            sh.id, sh.location, sh.load = -1 - v.id, loc, []
            mine = None
            sim.t = max(t_now, t_end)
            try:
                for x in pool:
                    if not D._feasible_single(sh, x):
                        continue
                    bundle, route, bid = D._try_bundle(sim, sh, x, pool, inner_kw.get("max_items", 10), True)
                    if math.isfinite(bid) and (mine is None or bid < mine[0]):
                        mine = (bid, v, bundle, route, sim.t + sim.job_plan(Job([sh], bundle, route), sim.t)[0])
            finally:
                sim.t = t_now
            if mine is not None:
                offers.append(mine)
        if not offers:
            break
        for bid, v, bundle, route, end in _winners(sel, sim, offers):
            if any(x not in pool for x in bundle):
                continue
            st.claims.setdefault(v.id, []).append((list(bundle), list(route)))
            st.claim_end[v.id] = end
            st.m["claims_won"] += 1
            for x in bundle:
                pool.remove(x)


def _winners(sel, sim, offers):
    w = sel(sim, [o[:4] for o in offers])
    by = {o[1].id: o for o in offers}
    return [by[x[1].id] for x in w]


# ------------------------------------------------------------------------------------------------- small instances
def ssi_assign(cost: np.ndarray) -> Tuple[List[Tuple[int, int]], float]:
    """Sequential single-item auction (one item per robot): the cheapest remaining (robot, item) pair each round."""
    C = np.array(cost, float)
    pairs, tot = [], 0.0
    R, I = set(range(C.shape[0])), set(range(C.shape[1]))
    while R and I:
        i, j = min(((i, j) for i in R for j in I), key=lambda p: (C[p], p))
        pairs.append((i, j))
        tot += C[i, j]
        R.discard(i)
        I.discard(j)
    return pairs, tot


def _route_score(start, pts, reward: float) -> float:
    """Score of visiting pts in order from start: sum over items of max(0, reward - distance travelled to it)."""
    d, cur, s = 0.0, start, 0.0
    for p in pts:
        d += float(np.hypot(*(p - cur)))
        cur = p
        s += max(0.0, reward - d)
    return s


def _best_insert(start, bundle_pts, p, reward):
    best = None
    for k in range(len(bundle_pts) + 1):
        trial = bundle_pts[:k] + [p] + bundle_pts[k:]
        s = _route_score(start, trial, reward)
        if best is None or s > best[0]:
            best = (s, k)
    return best


def cbba_lite(robots: np.ndarray, items: np.ndarray, depth: int, reward: float) -> Tuple[Dict[int, List[int]], float]:
    """Greedy bundle building (CBBA's bundle phase with full information): repeatedly add the (robot, item) with the
    largest marginal score (best insertion position), each robot at most `depth` items."""
    bundles: Dict[int, List[int]] = {i: [] for i in range(len(robots))}
    free_items = set(range(len(items)))
    while free_items:
        best = None
        for i in bundles:
            if len(bundles[i]) >= depth:
                continue
            pts = [items[j] for j in bundles[i]]
            base = _route_score(robots[i], pts, reward)
            for j in sorted(free_items):
                s, k = _best_insert(robots[i], pts, items[j], reward)
                gain = s - base
                if gain > 1e-12 and (best is None or gain > best[0] + 1e-12):
                    best = (gain, i, j, k)
        if best is None:
            break
        _, i, j, k = best
        bundles[i].insert(k, j)
        free_items.discard(j)
    return bundles, sum(_route_score(robots[i], [items[j] for j in b], reward) for i, b in bundles.items())


def optimum_score(robots, items, depth, reward) -> float:
    """Brute force: every item to a robot or to nobody, at most `depth` per robot, each bundle in its best order."""
    nR, nI = len(robots), len(items)
    best_by_set: Dict[Tuple[int, frozenset], float] = {}

    def bundle_best(i, js):
        key = (i, js)
        if key not in best_by_set:
            best_by_set[key] = max((_route_score(robots[i], [items[j] for j in perm], reward)
                                    for perm in itertools.permutations(sorted(js))), default=0.0)
        return best_by_set[key]

    best = 0.0
    for assign in itertools.product(range(nR + 1), repeat=nI):
        groups = {i: frozenset(j for j in range(nI) if assign[j] == i) for i in range(nR)}
        if any(len(g) > depth for g in groups.values()):
            continue
        best = max(best, sum(bundle_best(i, g) for i, g in groups.items()))
    return best


def bounds_check(n: int = 200, seed: int = 73) -> Dict[str, Any]:
    """SSI vs Hungarian (factor 2) and CBBA-lite vs the optimum (50 %), on n random small instances."""
    from ..assign import min_cost_assignment
    rng = np.random.default_rng(seed)
    ssi_ratio, ssi_fail, cb, cb_fail = [], [], {1: [], 2: [], 3: []}, {1: [], 2: [], 3: []}
    dup = 0
    for k in range(n):
        nR, nI = int(rng.integers(2, 6)), int(rng.integers(2, 6))
        R = rng.uniform(0, 10, (nR, 2))
        I = rng.uniform(0, 10, (nI, 2))
        D = rng.uniform(0, 10, (nI, 2))
        cost = np.hypot(*(R[:, None, :] - I[None, :, :]).transpose(2, 0, 1)) + np.hypot(*(I - D).T)[None, :]
        pairs, tot = ssi_assign(cost)
        rows, cols = min_cost_assignment(cost)
        opt = float(cost[rows, cols].sum())
        r = tot / opt if opt > 0 else 1.0
        ssi_ratio.append(r)
        if r > 2.0 + 1e-9:
            ssi_fail.append({"instance": k, "ratio": round(r, 4), "robots": nR, "items": nI})
        dup += len(pairs) - len({j for _, j in pairs})
        for d in cb:
            nIs = min(nI, 5)
            b, s = cbba_lite(R, I[:nIs], d, reward=12.0)
            o = optimum_score(R, I[:nIs], d, reward=12.0)
            q = s / o if o > 0 else 1.0
            cb[d].append(q)
            if q < 0.5 - 1e-9:
                cb_fail[d].append({"instance": k, "score_share": round(q, 4), "robots": nR, "items": nIs})
            assigned = [j for v in b.values() for j in v]
            dup += len(assigned) - len(set(assigned))
    sr = np.array(ssi_ratio)
    return {"instances": n, "seed": seed,
            "ssi_vs_hungarian": {"ratio_mean": round(float(sr.mean()), 4), "ratio_max": round(float(sr.max()), 4),
                                 "share_optimal": round(float(np.mean(sr <= 1 + 1e-9)), 4),
                                 "above_factor_2": ssi_fail},
            "cbba_lite_vs_optimum": {str(d): {"score_share_mean": round(float(np.mean(v)), 4),
                                              "score_share_min": round(float(np.min(v)), 4),
                                              "below_half": cb_fail[d]} for d, v in cb.items()},
            "items_assigned_twice": dup,
            "model": "positions uniform in a 10 x 10 square; SSI cost = robot->item + item->destination, one item per "
                     "robot; CBBA-lite score = sum over a robot's items of max(0, 12 - distance travelled to it)"}
