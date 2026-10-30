"""Phase 5 verification checks (B-79), from research_notes/Lunar ATC/verification_plan.md.

Every row carries the plan's labels: id (D1..), Sargent technique, NASA-STD-7009A credibility factor, kind (V =
verification, Val = validation, Cal = calibration reproduction), priority and papers. Stochastic rows follow the
plan's tolerance policy (section 2.2): the row passes when |error| <= tolerance; the 99 % batch-means interval
(20 batches) is reported, and a row whose interval misses the reference is a "bias flag" (recorded, not a
failure). `run_phase5_checks()` returns the rows; `write_json()` writes results/vv_phase5.json.

Test-only hooks (named as such, never used by production configurations): a one-item lander and fixed cargo
classes for the queueing references, one-pad landings (deterministic service), and exponential service times.
"""
from __future__ import annotations

import contextlib
import hashlib
import itertools
import json
import math
import os
import sys
import time
from dataclasses import asdict
from typing import Dict, List, Optional

import numpy as np

from .vv import Check

HOURS_PER_YEAR = 365 * 24.0


def _repo(*parts) -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), *parts)


# ------------------------------------------------------------------------------------------------ rows
def _row(cid, sub, name, reference, simulated, tolerance, unit, basis, technique, factor, kind, priority, papers,
         mode="rel", source="", ci=None, exposure=None, t0=None, tol_src=None) -> Dict:
    c = Check(name, float(reference), float(simulated), float(tolerance), unit, basis, source=source, mode=mode).finish()
    d = asdict(c)
    d.update({"id": cid, "sub": sub, "technique": technique, "factor": factor, "kind": kind, "priority": priority,
              "papers": list(papers), "ci99": [float(ci[0]), float(ci[1])] if ci is not None else None,
              "bias_flag": (None if ci is None else bool(not (ci[0] <= reference <= ci[1]))),
              "exposure": exposure, "runtime_s": round(time.time() - t0, 2) if t0 is not None else None,
              "tolerance_source": tol_src or _tol_source(cid, tolerance, unit)})
    for k in ("reference", "simulated", "rel_error", "error"):
        d[k] = float(d[k])
    return d


def _tol_source(cid, tol, unit) -> str:
    plan = "research_notes/Lunar ATC/verification_plan.md"
    if tol == 0:
        return f"{plan} section 2.2 rule 1: exact for counts and booleans"
    if tol <= 1e-9:
        return f"{plan} section 2.2 rule 1: deterministic identity, 1e-9 relative"
    return f"{plan} section 3, row {cid} (pass tolerance column)"


def _batch_means(x, nb: int = 20):
    """Mean and 99 % batch-means interval of an autocorrelated series in arrival order (Schmeiser 1982)."""
    from scipy import stats
    x = np.asarray(x, float)
    n = len(x) // nb * nb
    b = x[:n].reshape(nb, -1).mean(1)
    h = stats.t.ppf(0.995, nb - 1) * b.std(ddof=1) / math.sqrt(nb)
    return float(x.mean()), (float(b.mean() - h), float(b.mean() + h))


# ------------------------------------------------------------------------------------------------ queueing references
def erlang_c_wq(lam: float, mean_s: float, c: int) -> float:
    """M/M/c mean wait in queue (Erlang C)."""
    a = lam * mean_s
    if a >= c:
        return math.inf
    top = a ** c / math.factorial(c) * c / (c - a)
    pw = top / (sum(a ** k / math.factorial(k) for k in range(c)) + top)
    return pw / (c / mean_s - lam)


def mdc_wq(lam: float, d: float, c: int, n_max: int = 600) -> float:
    """Exact M/D/c mean wait in queue. The number in system at times t, t + D, ... is the chain
    N' = max(N - c, 0) + A, A ~ Poisson(lambda D) (Crommelin 1932: everyone in service at t has left by t + D and the
    next c in line are in service at t + D); its stationary law is the time-stationary law of N, so
    L_q = E[N] - lambda D and W_q = L_q / lambda (Little)."""
    from scipy import stats
    a = lam * d
    if a >= c:
        return math.inf
    pa = stats.poisson.pmf(np.arange(n_max + 1), a)
    P = np.zeros((n_max + 1, n_max + 1))
    for n in range(n_max + 1):
        base = max(n - c, 0)
        row = pa[: n_max + 1 - base].copy()
        row[-1] += 1.0 - row.sum()                    # truncation: the tail mass stays in the last state
        P[n, base:] = row
    A = P.T - np.eye(n_max + 1)
    A[-1, :] = 1.0
    rhs = np.zeros(n_max + 1)
    rhs[-1] = 1.0
    pi = np.linalg.solve(A, rhs)
    return (float(pi @ np.arange(n_max + 1)) - a) / lam


@contextlib.contextmanager
def _queue_hooks(classes=None, one_pad: bool = False):
    """Test-only hooks: the lander 'ONE' carries exactly one 99-100 kg item, ready 99 h after touchdown (a constant
    shift keeps arrivals Poisson); cargo classes fixed (default: one class to BASE); no return items; optionally all
    landings at the first pad."""
    import lunarsim.scenario as scn
    import lunarsim.engine as eng
    from .scenario import LanderType
    saved = (dict(scn.LANDER_TYPES), list(scn.CARGO_CLASSES), scn.RETURN_ITEM_PROB, eng.sample_landings)
    try:
        scn.LANDER_TYPES["ONE"] = LanderType("ONE", (99.0, 99.0), (99.0, 99.0), True, 100)
        scn.CARGO_CLASSES[:] = classes or [("consumables", (99.0, 100.0), {"BASE": 1.0}, 1, 1.0)]
        scn.RETURN_ITEM_PROB = 0.0
        if one_pad:
            eng.sample_landings = lambda rng, sc, pads: saved[3](rng, sc, list(pads)[:1])
        yield
    finally:
        scn.LANDER_TYPES.clear()
        scn.LANDER_TYPES.update(saved[0])
        scn.CARGO_CLASSES[:] = saved[1]
        scn.RETURN_ITEM_PROB = saved[2]
        eng.sample_landings = saved[3]


def _queue_scenario(rate_per_year: float, years: float, n_veh: int = 1):
    from .scenario import Scenario
    return Scenario(landings_per_year={"ONE": rate_per_year}, cargo_owners=["NASA"],
                    fleet=[("NASA", "LTV", "autonomous", "A")] * n_veh, night_fraction=0.0, failures=False,
                    other_duty_share=0.0, horizon_h=years * HOURS_PER_YEAR, n_operators=max(4, n_veh))


def _service_times(one_pad: bool) -> np.ndarray:
    """Job hours of one LTV from BASE: empty to the pad, load, back to BASE, unload (each pad equally likely)."""
    from . import dispatch
    from .engine import Simulation, Job
    with _queue_hooks():
        sim = Simulation(_queue_scenario(1.0, 1.0), dispatch.pooled_greedy, seed=1)
    v = sim.vehicles[0]
    from .entities import Cargo
    S = []
    for pad in (sim.world.pads[:1] if one_pad else sim.world.pads):
        v.location = "BASE"
        c = Cargo(0, "NASA", 99.5, pad, "BASE", 0.0, 0.0, 1, "A", "consumables")
        S.append(sim.job_plan(Job([v], [c], ["BASE"]), 0.0)[0])
    return np.array(S)


def _queue_run(rate_per_year, years, n_veh=1, one_pad=False, classes=None, exp_mean_h=None, mech=None, seed=21):
    """One queueing run under the test-only hooks; returns (sim, items in ready order, integral of the waiting count).
    sim.vv_service lists every started job as (start time, service hours, item id) in start order."""
    from . import dispatch
    from .engine import Simulation
    with _queue_hooks(classes, one_pad):
        sc = _queue_scenario(rate_per_year, years, n_veh)
        sim = Simulation(sc, mech or dispatch.pooled_greedy, seed=seed)
        acc = {"nq": 0.0, "t": -math.inf}
        real_adv = sim._advance_to

        def adv(t, _ra=real_adv):
            if acc["t"] == -math.inf:
                acc["t"] = t
            if t > acc["t"]:
                acc["nq"] += len(sim.waiting) * (t - acc["t"])
                acc["t"] = t
            return _ra(t)
        sim._advance_to = adv
        sim.vv_service = []
        rng = np.random.default_rng(seed + 1000)
        real_start = sim._start_job

        def start(job, _rs=real_start):
            n0 = [v.jobs for v in job.vehicles]
            _rs(job)
            if [v.jobs for v in job.vehicles] == n0:
                return
            if exp_mean_h is not None:                   # test-only: exponential service times
                end = sim.t + float(rng.exponential(exp_mean_h))
                for v in job.vehicles:
                    v.busy_until = end
                sim._push(end, "FREE", None)
            sim.vv_service.append((sim.t, max(v.busy_until for v in job.vehicles) - sim.t, job.items[0].id))
        sim._start_job = start
        sim.run()
    items = sorted((c for c in sim.all_cargo if c.t_ready <= sc.horizon_h), key=lambda c: (c.t_ready, c.id))
    return sim, items, acc["nq"]


def _waits(items, H):
    """Waits of items picked before the horizon, in ready order, plus the count still waiting at the horizon."""
    w = [c.t_picked - c.t_ready for c in items if c.t_picked is not None and c.t_picked <= H]
    return np.array(w), sum(1 for c in items if c.t_picked is None or c.t_picked > H)


# ------------------------------------------------------------------------------------------------ queue recursions
def queue_fcfs(arr, S, c: int) -> np.ndarray:
    """Waits of an FCFS c-server queue (Kiefer-Wolfowitz): customer k (arrival order) starts at max(arrival, the
    earliest server release) and takes S[k]."""
    import heapq
    free = [0.0] * c
    w = np.empty(len(S))
    for k in range(len(S)):
        f = heapq.heappop(free)
        st = arr[k] if arr[k] > f else f
        w[k] = st - arr[k]
        heapq.heappush(free, st + S[k])
    return w


def queue_priority(arr, cls, S) -> np.ndarray:
    """Waits of a one-server, non-preemptive priority queue, FCFS within class (lower class first); the k-th service
    to start takes S[k]. Customers never started keep NaN."""
    import heapq
    n = len(S)
    w = np.full(len(arr), np.nan)
    q = []
    t = 0.0
    i = k = 0
    while k < n and (q or i < len(arr)):
        if not q:
            t = max(t, arr[i])
        while i < len(arr) and arr[i] <= t:
            heapq.heappush(q, (cls[i], arr[i], i))
            i += 1
        _, a, j = heapq.heappop(q)
        w[j] = t - a
        t += S[k]
        k += 1
    return w


def _sample_path_row(cid, sub, name, eng_w, ref_w, papers, t0):
    d = float(np.max(np.abs(eng_w - ref_w))) if len(eng_w) else float("nan")
    return _row(cid, sub, name, 0.0, d, 1e-9, "h", f"{len(eng_w)} items: largest |engine wait - recursion wait| on the "
                "same arrival times and service times (the engine's own, in start order)", "comparison to other models",
                "code verification", "V", "P1", papers, mode="abs", source="Kiefer and Wolfowitz 1955 (multi-server "
                "FCFS recursion); Kleinrock 1976 (priority queue)", t0=t0, tol_src="exact up to float addition: the "
                "same floats enter both")


def _sized(simulate, ref, tol, n0=20000, n_max=4_000_000):
    """Run an independent queue in 20 batches, doubling the batch size until the 99 % half-width is at most a third
    of the tolerance (plan section 2.2 rule 3). Returns (mean, ci, n)."""
    m = n0 // 20
    while True:
        w = simulate(20 * m)
        mean, ci = _batch_means(w)
        if (ci[1] - ci[0]) / 2 <= tol / 3 * abs(ref) or 20 * m >= n_max:
            return mean, ci, len(w)
        m *= 2


# ------------------------------------------------------------------------------------------------ D1, D2
def check_d2_pk() -> List[Dict]:
    """D2: P-K mean wait and busy fraction at rho 0.3, 0.6, 0.85 (two pads: general service), and M/D/1 (one pad).
    Two steps: the engine's sample path equals an independent one-server recursion on the same inputs (exact), and
    the recursion, sized by the plan's rule, matches P-K. D1 (asymptotic form) uses the rho 0.6 engine run."""
    rows = []
    S2 = _service_times(False)
    S1 = _service_times(True)
    rng = np.random.default_rng(2)
    for rho, tol, years in ((0.3, 0.03, 10), (0.6, 0.05, 10), (0.85, 0.10, 10), ("MD1", 0.05, 10)):
        t0 = time.time()
        S = S1 if rho == "MD1" else S2
        r = 0.6 if rho == "MD1" else rho
        ES, ES2 = S.mean(), (S ** 2).mean()
        lam = r / ES
        sim, items, nq = _queue_run(lam * HOURS_PER_YEAR, years, one_pad=(rho == "MD1"))
        H = sim.sc.horizon_h
        sub = "M/D/1, rho 0.6, one pad" if rho == "MD1" else f"rho {rho}"
        sv = np.array([d for _, d, _ in sim.vv_service])
        arr = np.array([c.t_ready for c in items])
        eng_w, _ = _waits(items, H)
        rows.append(_sample_path_row("D2", sub + ": sample path", f"Engine queue = one-server recursion, {sub}",
                                     eng_w, queue_fcfs(arr, sv, 1)[:len(eng_w)], ["P1"], t0))
        wq_ref = lam * ES2 / (2 * (1 - r))
        sim_fn = lambda n: queue_fcfs(np.cumsum(rng.exponential(1 / lam, n)), rng.choice(S, n), 1)
        m, ci, n = _sized(sim_fn, wq_ref, tol)
        em, eci = _batch_means(eng_w)
        ref_name = "rho S / (2 (1 - rho))" if rho == "MD1" else "lambda E[S^2] / (2 (1 - rho))"
        rows.append(_row("D2", sub + ": W_q", f"Mean wait in queue, {sub} (Pollaczek-Khinchine {ref_name})", wq_ref, m,
                         tol, "h", f"the recursion with Poisson arrivals and the engine's service times "
                         f"({', '.join(f'{x:.3f}' for x in S)} h, equally likely), {n:,} customers in 20 batches; the "
                         f"engine run itself ({len(eng_w)} items, {years} years): {em:.4f} h, 99 % interval "
                         f"[{eci[0]:.4f}, {eci[1]:.4f}]", "analytic", "code verification", "V", "P1", ["P1"],
                         source="Pollaczek 1930; Khinchine 1932; Kleinrock, Queueing Systems Vol. 1, 1975", ci=ci, t0=t0))
        busy = sim.vehicles[0].hours_busy / H
        rows.append(_row("D2", sub + ": busy", f"Busy fraction, {sub} (lambda E[S])", r, busy, 0.01, "fraction",
                         f"engine: vehicle busy hours / horizon, {len(items)} items over {years} years", "analytic",
                         "code verification", "V", "P1", ["P1"], source="Kleinrock 1975", t0=t0))
        if rho == 0.6:
            lq = nq / H
            lam_hat = len(items) / H
            wq_all = np.array([(min(c.t_picked, H) if c.t_picked is not None else H) - c.t_ready for c in items])
            rows.append(_row("D1", "asymptotic L_q = lambda W_q", "Little's law, L_q = lambda W_q (M/G/1, rho 0.6, "
                             f"{years} years)", lam_hat * wq_all.mean(), lq, 0.02, "items",
                             "engine: time-average count of waiting items against arrival rate x mean wait (waits "
                             "censored at the horizon)", "traces", "solution verification", "V", "P1", ["P1", "P2", "P3"],
                             source="Little, Operations Research 9(3):383-387, 1961", t0=t0))
    return rows


def check_d1_sample_path() -> List[Dict]:
    """D1: Little's law in sample-path form on a full library run: the engine's own waiting integral
    (tonne_days_waiting, accumulated at every event) against the item records, and the count form from a hook."""
    from .config import library
    from .engine import Simulation
    from . import dispatch
    from .scenario import HOURS_PER_DAY
    rows = []
    for name, mech in (("P2-default", dispatch.marketplace), ("P2-default", dispatch.pooled_greedy)):
        t0 = time.time()
        sc = library()[name]
        sim = Simulation(sc, mech, seed=1)
        acc = {"nq": 0.0, "t": -math.inf}               # from the first event: an item may be ready before t = 0
        real_adv = sim._advance_to

        def adv(t, _ra=real_adv, _s=sim, _a=acc):
            if _a["t"] == -math.inf:
                _a["t"] = t
            if t > _a["t"]:
                _a["nq"] += len(_s.waiting) * (t - _a["t"])
                _a["t"] = t
            return _ra(t)
        sim._advance_to = adv
        out = sim.run()
        H = sc.horizon_h
        seen = [c for c in sim.all_cargo if c.t_ready <= H]
        ref_t = sum(c.mass_kg / 1000.0 * ((min(c.t_picked, H) if c.t_picked is not None else H) - c.t_ready)
                    / HOURS_PER_DAY for c in seen if not c.stranded)
        ref_n = sum((min(c.t_picked, H) if c.t_picked is not None else H) - c.t_ready for c in seen)
        mname = mech.__name__
        rows.append(_row("D1", f"sample path, tonne-days, {mname}", f"Little's law, sample path: engine waiting "
                         f"tonne-days = item records ({name}, {mname}, seed 1)", ref_t, out["tonne_days_waiting"], 1e-9,
                         "t-days", f"sum over {len(seen)} items (stranded excluded, as the engine) of mass x "
                         "(min(pickup, T) - ready)", "traces", "code verification", "V", "P1", ["P1", "P2", "P3"],
                         source="Little 1961; Little, Operations Research 59(3):536-549, 2011", t0=t0))
        rows.append(_row("D1", f"sample path, items, {mname}", f"Little's law, sample path: integral of the waiting "
                         f"count = sum of waits ({name}, {mname}, seed 1)", ref_n, acc["nq"], 1e-9, "item-h",
                         "integral of len(waiting) over event intervals from the first event (one item is ready "
                         "before t = 0) against sum over items of (min(pickup, T) - ready)", "traces", "code verification", "V", "P1", ["P1", "P2", "P3"],
                         source="Little 1961, 2011", t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ D3, D4
def check_d3_multi() -> List[Dict]:
    """D3: c vehicles. Engine sample path = the FCFS c-server recursion on the same inputs (exact); the recursion,
    sized by the plan's rule, against Erlang C (exponential service) and the exact M/D/c mean."""
    rows = []
    rng = np.random.default_rng(3)
    mean_s, rho = 2.0, 0.6
    S = float(_service_times(True)[0])
    for kind, c in (("M", 2), ("M", 3), ("M", 4), ("D", 2), ("D", 3)):
        t0 = time.time()
        s_mean = mean_s if kind == "M" else S
        lam = c * rho / s_mean
        years = 3
        sim, items, _ = _queue_run(lam * HOURS_PER_YEAR, years, n_veh=c, one_pad=(kind == "D"),
                                   exp_mean_h=(mean_s if kind == "M" else None), seed=30 + c)
        eng_w, _ = _waits(items, sim.sc.horizon_h)
        sv = np.array([d for _, d, _ in sim.vv_service])
        arr = np.array([x.t_ready for x in items])
        sub = f"M/{kind}/{c}"
        what = "exponential service (test-only hook)" if kind == "M" else "deterministic service, one pad"
        rows.append(_sample_path_row("D3", sub + ": sample path", f"Engine queue = FCFS {c}-server recursion, {what}",
                                     eng_w, queue_fcfs(arr, sv, c)[:len(eng_w)], ["P1"], t0))
        if kind == "M":
            ref = erlang_c_wq(lam, mean_s, c)
            fn = lambda n: queue_fcfs(np.cumsum(rng.exponential(1 / lam, n)), rng.exponential(mean_s, n), c)
            name, src = f"Mean wait, {c} vehicles, exponential service (Erlang C)", "Erlang 1917; Tijms 2003"
        else:
            ref = mdc_wq(lam, S, c)
            fn = lambda n: queue_fcfs(np.cumsum(rng.exponential(1 / lam, n)), np.full(n, S), c)
            name = f"Mean wait, {c} vehicles, deterministic service (exact M/D/c, Crommelin chain)"
            src = "Crommelin 1932; Franx, Operations Research Letters 29(5):221-229, 2001"
        m, ci, n = _sized(fn, ref, 0.05)
        em, eci = _batch_means(eng_w)
        rows.append(_row("D3", sub + ": W_q", name, ref, m, 0.05, "h", f"rho {rho} per vehicle, E[S] {s_mean:.3f} h; the "
                         f"recursion, {n:,} customers in 20 batches; the engine run itself ({len(eng_w)} items, {years} "
                         f"years): {em:.4f} h [{eci[0]:.4f}, {eci[1]:.4f}]", "analytic", "code verification", "V", "P1",
                         ["P1"], source=src, ci=ci, t0=t0))
    return rows


def check_d4_cobham() -> List[Dict]:
    """D4: two priority classes, one vehicle, non-preemptive priority, FCFS within class (dispatch._greedy with
    priority=True, the rule the check is valid for). Engine = priority recursion on the same inputs (exact); the
    recursion, sized, against Cobham."""
    from . import dispatch
    t0 = time.time()
    rng = np.random.default_rng(4)
    S = _service_times(False)
    ES, ES2 = S.mean(), (S ** 2).mean()
    share1, rho = 0.3, 0.7
    lam = rho / ES
    classes = [("consumables", (99.0, 100.0), {"BASE": 1.0}, 1, share1),
               ("science", (99.0, 100.0), {"BASE": 1.0}, 2, 1.0 - share1)]
    mech = lambda sim, w, f, **kw: dispatch._greedy(sim, w, f, pooled=True, priority=True)
    years = 10
    sim, items, _ = _queue_run(lam * HOURS_PER_YEAR, years, classes=classes, mech=mech, seed=51)
    H = sim.sc.horizon_h
    arr = np.array([c.t_ready for c in items])
    cls = np.array([c.priority for c in items])
    sv = np.array([d for _, d, _ in sim.vv_service])
    rec = queue_priority(arr, cls, sv)
    done = np.array([c.t_picked is not None and c.t_picked <= H for c in items])
    eng = np.array([(c.t_picked - c.t_ready) if d else np.nan for c, d in zip(items, done)])
    rows = [_sample_path_row("D4", "sample path", "Engine queue = non-preemptive priority recursion", eng[done],
                             rec[done], ["P1"], t0)]
    W0 = lam * ES2 / 2
    s1 = share1 * rho
    ref = {1: W0 / (1 - s1), 2: W0 / ((1 - s1) * (1 - rho))}
    for k in (1, 2):
        def fn(n, k=k):
            a = np.cumsum(rng.exponential(1 / lam, n))
            cl = np.where(rng.random(n) < share1, 1, 2)
            w = queue_priority(a, cl, rng.choice(S, n))
            return w[cl == k]
        m, ci, n = _sized(fn, ref[k], 0.05)
        em, eci = _batch_means(eng[done & (cls == k)])
        rows.append(_row("D4", f"class {k}", f"Mean wait, priority class {k} of 2 (Cobham)", ref[k], m, 0.05, "h",
                         f"one vehicle, rho {rho}, class-1 share {share1}; the recursion, {n:,} class-{k} customers in "
                         f"20 batches; the engine run itself: {em:.4f} h [{eci[0]:.4f}, {eci[1]:.4f}]; rule: strict "
                         "priority, FCFS within class (dispatch._greedy priority=True)", "analytic",
                         "code verification", "V", "P2", ["P1"],
                         source="Cobham, Operations Research 2(1):70-76, 1954", ci=ci, t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ D5
def check_d5_extremes() -> List[Dict]:
    from . import dispatch
    from .engine import Simulation
    from .scenario import Scenario
    from .entities import VEHICLE_CLASSES
    rows = []
    t0 = time.time()
    sc = Scenario(landings_per_year={"CLPS": 0, "MK1": 0, "LARGE": 0})
    out = Simulation(sc, dispatch.marketplace, seed=1).run()
    bad = [k for k in ("delivered_kg", "km_total", "energy_kwh", "jobs") if out[k] != 0]
    fleet = sum(VEHICLE_CLASSES[c].unit_cost_musd / VEHICLE_CLASSES[c].life_years for _, c, _, _ in sc.fleet)
    rows.append(_row("D5", "zero landings", "Zero landings: nothing delivered, driven or used", 0.0, float(len(bad)), 0.0,
                     "nonzero fields", f"delivered_kg, km_total, energy_kwh, jobs all 0 (nonzero: {bad or 'none'})",
                     "extreme condition", "code verification", "V", "P1", ["P1", "P2", "P3"], mode="abs",
                     source="Sargent 2013", t0=t0))
    rows.append(_row("D5", "zero landings: fleet cost", "Zero landings: fleet cost unchanged", fleet,
                     out["fleet_cost_musd"], 1e-9, "$M", "sum of unit cost / life", "extreme condition",
                     "code verification", "V", "P1", ["P1", "P2", "P3"], source="Sargent 2013", t0=t0))
    t0 = time.time()
    sc = Scenario(fleet=[])
    out = Simulation(sc, dispatch.marketplace, seed=1).run()
    rows.append(_row("D5", "zero vehicles", "Zero vehicles: the backlog is all ready mass, no crash", out["ready_kg"],
                     out["backlog_kg"] + out["stranded_kg"], 1e-9, "kg",
                     f"backlog + stranded = ready ({out['ready_kg']:.0f} kg); delivered {out['delivered_kg']:.0f} kg",
                     "extreme condition", "code verification", "V", "P1", ["P1", "P2", "P3"], source="Sargent 2013",
                     t0=t0))
    t0 = time.time()
    S = _service_times(False)
    lam = 1.5 / S.mean()
    years = 2
    pts = []
    from . import dispatch as D

    def mech(sim, w, f, **kw):
        pts.append((sim.t, len(sim.waiting)))
        return D.pooled_greedy(sim, w, f, **kw)
    sim, items, _ = _queue_run(lam * HOURS_PER_YEAR, years, mech=mech, seed=61)
    P = np.array(pts)
    half = P[:, 0] > sim.sc.horizon_h / 4
    slope = float(np.polyfit(P[half, 0], P[half, 1], 1)[0])
    ref = lam - 1.0 / S.mean()
    rows.append(_row("D5", "overload rho 1.5", "Overload rho 1.5: backlog grows at lambda - 1/E[S]", ref, slope, 0.02,
                     "items/h", f"least-squares slope of the waiting count over the last 3/4 of {years} years "
                     f"({len(P)} dispatch calls)", "extreme condition", "code verification", "V", "P1",
                     ["P1", "P2", "P3"], source="Sargent 2013", t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ D9
def check_d9_hungarian(n_inst: int = 1000) -> Dict:
    from .assign import min_cost_assignment
    t0 = time.time()
    rng = np.random.default_rng(9)
    worst, n_bad = 0.0, 0
    perms = {}
    for k in range(n_inst):
        r = 1 + k % 8
        c = int(rng.integers(max(1, r - 2), 9))
        C = rng.uniform(0, 100, (r, c))
        rows_, cols_ = min_cost_assignment(C)
        got = float(C[rows_, cols_].sum())
        if len(rows_) != min(r, c) or len(set(rows_)) != len(rows_) or len(set(cols_)) != len(cols_):
            n_bad += 1
            continue
        key = (r, c)
        if key not in perms:
            if r <= c:
                perms[key] = np.array(list(itertools.permutations(range(c), r)), dtype=np.int64)
            else:
                perms[key] = np.array(list(itertools.permutations(range(r), c)), dtype=np.int64)
        p = perms[key]
        best = float((C[np.arange(r)[None, :], p].sum(1) if r <= c else C[p, np.arange(c)[None, :]].sum(1)).min())
        e = abs(got - best) / max(best, 1e-12)
        worst = max(worst, e)
        n_bad += e > 1e-9
    return _row("D9", "1,000 instances", "Central assignment equals brute force (n <= 8)", 0.0, float(n_bad), 0.0,
                "instances", f"{n_inst} random cost matrices, 1-8 rows x 1-8 columns (square and rectangular); "
                f"largest relative cost gap {worst:.2e}", "comparison to other models", "code verification", "V", "P1",
                ["P1"], mode="abs", source="Kuhn 1955; Munkres 1957; lunarsim/assign.py", t0=t0)


# ------------------------------------------------------------------------------------------------ E3
def check_e3_energy() -> List[Dict]:
    from .rover import physics as R
    t0 = time.time()
    g, crr, s = 1.62, 0.178, 0.04
    rows = []
    cases = [("flat, 700 kg", 700.0, 0.0, "Cal"), ("flat, 1,600 kg", 1600.0, 0.0, "V"),
             ("10 deg uphill, 1,600 kg", 1600.0, 10.0, "V"), ("10 deg downhill, 1,600 kg", 1600.0, -10.0, "V")]
    for sub, m, gr, kind in cases:
        th = math.radians(gr)
        hand = (crr * m * g * math.cos(th) + max(0.0, m * g * math.sin(th)) / 0.7) * 1000.0 / (1 - s) / 3600.0
        sim = float(R.energy_wh(1000.0, gr, R.FLAT_SLIP_REF, mass_kg=m))
        rows.append(_row("E3", sub, f"Traction energy per km, {sub} (hand calculation)", hand, sim, 0.005, "Wh/km",
                         f"E = (C_rr m g cos + max(0, m g sin) / 0.7) d / (1 - s), C_rr 0.178, s 0.04 (engine slip "
                         f"{R.FLAT_SLIP_REF:.4f}, C_rr_eff {R.C_RR_EFF:.5f})" + (
                             "; calibration reproduction: C_rr_eff is fitted to the LRV's 58.5 Wh/km" if kind == "Cal"
                             else ""), "analytic", "code verification", kind, "P1", ["P3"],
                         source="v3 Section 3.4 energy model; Apollo LRV 57-60 Wh/km", t0=t0))
    flat = float(R.energy_wh(1000.0, 0.0, R.FLAT_SLIP_REF, mass_kg=700.0))
    rows.append(_row("E3", "LRV range", "Flat 700 kg energy inside the LRV's measured 57-60 Wh/km", 58.5, flat, 1.5,
                     "Wh/km", "Apollo 15/17 LRV 1.58-1.67 Ah/km at 36 V (band 57-60 = 58.5 +/- 1.5)",
                     "historical data", "referent validation", "Cal", "P1", ["P3"], mode="abs",
                     source="Apollo LRV data as cited in v3 [41]", t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ R1
def check_r1_horizon() -> List[Dict]:
    """R1: the mesh builder's line-of-sight routine (tools/atc/mesh.py pair_profiles) on a bald Moon (flat local
    terrain, curvature term on) against the smooth-sphere horizon sqrt(2Rh1) + sqrt(2Rh2)."""
    t0 = time.time()
    sys.path.insert(0, _repo("tools", "atc"))
    try:
        import mesh as MESH
    finally:
        sys.path.pop(0)
    from .terrain import MOON_RADIUS_M as R

    class Bald:
        @staticmethod
        def height(x, y):
            return np.zeros(np.broadcast(np.asarray(x), np.asarray(y)).shape)
    d = np.arange(50.0, 14000.0, 1.0)
    P = np.concatenate([[[0.0, 0.0]], np.stack([d, np.zeros_like(d)], 1)])
    I = np.zeros(len(d), np.int64)
    J = np.arange(1, len(d) + 1, dtype=np.int64)
    combos = ((2.5, 2.5), (2.5, 10.0), (10.0, 10.0))
    clear, _ = MESH.pair_profiles(Bald(), P, I, J, combos, radius_m=R)
    rows = []
    for k, (ha, hb) in enumerate(combos):
        ref = math.sqrt(2 * R * ha) + math.sqrt(2 * R * hb)
        vis = clear[k] > 0
        edge = float(d[vis].max()) if vis.any() else 0.0
        far = np.abs(d - ref) > 5.0
        wrong = int(np.sum(vis[far] != (d[far] < ref)))
        sub = f"{ha:g} m to {hb:g} m"
        rows.append(_row("R1", sub + ": edge", f"Smooth-sphere radio horizon, antennas {sub}", ref, edge, 5.0, "m",
                         f"largest visible distance on a bald Moon (1 m spacing, R {R / 1000:.1f} km); misclassified "
                         f"points more than 5 m from the edge: {wrong}", "analytic", "code verification", "V", "P1",
                         ["P2", "P3"], mode="abs", source="spherical geometry; Archinal et al. 2018 (R)", t0=t0))
        rows.append(_row("R1", sub + ": classification", f"Line of sight classified exactly away from the edge, {sub}",
                         0.0, float(wrong), 0.0, "points", f"{int(far.sum())} distances 50-14,000 m more than 5 m "
                         "from the edge", "analytic", "code verification", "V", "P1", ["P2", "P3"], mode="abs",
                         source="spherical geometry", t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ D6
def _run_digest(sim, out) -> str:
    rec = [(c.id, c.owner, round(c.mass_kg, 9), c.origin, c.dest, c.t_ready, c.t_picked, c.t_delivered, c.carrier)
           for c in sorted(sim.all_cargo, key=lambda c: c.id)]
    summ = {k: (round(v, 9) if isinstance(v, float) else v) for k, v in sorted(out.items()) if np.isscalar(v)}
    return hashlib.md5(json.dumps([rec, summ], default=str).encode()).hexdigest()


def check_d6_one_owner() -> List[Dict]:
    from . import dispatch
    from .engine import Simulation
    from .scenario import Scenario
    rows = []
    base = Scenario(landings_per_year={"CLPS": 12, "MK1": 6, "LARGE": 1})
    sc = base.with_(cargo_owners=["NASA"], fleet=[("NASA",) + tuple(f[1:]) for f in base.fleet])
    for seed in (1, 2, 3):
        t0 = time.time()
        d = []
        for mech in (dispatch.inhouse, dispatch.pooled_greedy):
            sim = Simulation(sc, mech, seed=seed)
            d.append(_run_digest(sim, sim.run()))
        rows.append(_row("D6", f"seed {seed}", f"One owner: in-house dispatch equals pooled greedy (seed {seed})", 1.0,
                         float(d[0] == d[1]), 0.0, "match", f"md5 of every item record and the summary: "
                         f"{d[0][:12]} vs {d[1][:12]} (default fleet, 12 CLPS + 6 MK1 + 1 LARGE landings a year, all vehicles and "
                         f"cargo owned by NASA, {len(sim.all_cargo)} items)",
                         "degenerate tests", "code verification", "V", "P1", ["P1"], mode="abs",
                         source="Sargent 2013", t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ D7
@contextlib.contextmanager
def _time_scaled(k: float):
    """Test-only: every duration x k (vehicle speeds / k, load and unload x k, charging power / k, lander offload
    window, item offload stagger and return lag x k, the lunar cycle x k)."""
    import dataclasses
    import lunarsim.scenario as scn
    import lunarsim.engine as eng
    from .entities import VEHICLE_CLASSES
    saved = (dict(VEHICLE_CLASSES), dict(scn.LANDER_TYPES), scn.ITEM_STAGGER_H, scn.RETURN_LAG_H, scn.LUNAR_CYCLE_H,
             eng.LUNAR_CYCLE_H)
    try:
        for n, v in saved[0].items():
            VEHICLE_CLASSES[n] = dataclasses.replace(v, speed_kmh=v.speed_kmh / k, load_h=v.load_h * k,
                                                     unload_h=v.unload_h * k, charge_kw=v.charge_kw / k)
        for n, lt in saved[1].items():
            scn.LANDER_TYPES[n] = dataclasses.replace(lt, offload_h=(lt.offload_h[0] * k, lt.offload_h[1] * k))
        scn.ITEM_STAGGER_H = saved[2] * k
        scn.RETURN_LAG_H = (saved[3][0] * k, saved[3][1] * k)
        scn.LUNAR_CYCLE_H = eng.LUNAR_CYCLE_H = saved[4] * k
        yield
    finally:
        VEHICLE_CLASSES.clear()
        VEHICLE_CLASSES.update(saved[0])
        scn.LANDER_TYPES.clear()
        scn.LANDER_TYPES.update(saved[1])
        scn.ITEM_STAGGER_H, scn.RETURN_LAG_H, scn.LUNAR_CYCLE_H, eng.LUNAR_CYCLE_H = saved[2:]


def check_d7_time_scale(k: float = 2.0) -> List[Dict]:
    from . import dispatch
    from .engine import Simulation
    from .scenario import Scenario
    rows = []
    for sub, night in (("no night", 0.0), ("night 15 %", 0.15)):
        t0 = time.time()
        base = Scenario(night_fraction=night, failures=False, other_duty_share=0.0, horizon_h=2 * HOURS_PER_YEAR,
                        landings_per_year={"CLPS": 12, "MK1": 6, "LARGE": 1})
        sims = []
        for kk in (1.0, k):
            sc = base.with_(horizon_h=base.horizon_h * kk,
                            landings_per_year={n: r / kk for n, r in base.landings_per_year.items()})
            with _time_scaled(kk):
                sim = Simulation(sc, dispatch.pooled_greedy, seed=7)
                out = sim.run()
            sims.append((sim, out))
        (s1, o1), (s2, o2) = sims
        a = {c.id: c for c in s1.all_cargo}
        b = {c.id: c for c in s2.all_cargo}
        worst = 0.0 if set(a) == set(b) else math.inf
        for i in set(a) & set(b):
            for f in ("t_ready", "t_picked", "t_delivered"):
                x, y = getattr(a[i], f), getattr(b[i], f)
                if (x is None) != (y is None):
                    worst = math.inf
                elif x is not None:
                    worst = max(worst, abs(k * x - y) / max(abs(k * x), 1e-9))
        same = [f for f in ("delivered_items", "delivered_kg", "jobs", "km_total") if abs(o1[f] - o2[f]) > 1e-9 * max(1, abs(o1[f]))]
        rows.append(_row("D7", sub, f"Time-scale invariance x{k:g}, {sub}: every item time x {k:g}", 0.0, worst, 1e-9,
                         "rel", f"{len(a)} items, largest relative error of ready, pickup and delivery times against "
                         f"x{k:g}; counts, kg, jobs and km unchanged: {'yes' if not same else 'no: ' + ', '.join(same)}"
                         " (pooled greedy, faults and duties off, seed 7)", "metamorphic testing", "code verification",
                         "V", "P2", ["P1", "P2", "P3"], mode="abs", source="Chen et al. 2018; Segura et al. 2016",
                         t0=t0, tol_src="research_notes/Lunar ATC/verification_plan.md section 3, row D7: 1e-9 relative"))
    return rows


# ------------------------------------------------------------------------------------------------ D8
def _invariant_run(sim) -> Dict:
    """Run with assertion hooks: clock order, no event in the past, no vehicle in two overlapping jobs, team members
    share the job interval, carried mass within capacity; then item time order."""
    v_ = {"clock": 0, "past": 0, "overlap": 0, "team": 0, "capacity": 0, "order": 0}
    last = {"t": -math.inf}
    real_adv, real_push, real_start = sim._advance_to, sim._push, sim._start_job

    def adv(t, _ra=real_adv):
        if t < last["t"] - 1e-9:
            v_["clock"] += 1
        last["t"] = max(last["t"], t)
        return _ra(t)

    def push(t, kind, payload, _rp=real_push):
        if t < sim.t - 1e-9:
            v_["past"] += 1
        return _rp(t, kind, payload)
    jobs = {}

    def start(job, _rs=real_start):
        n0 = [v.jobs for v in job.vehicles]
        _rs(job)
        if [v.jobs for v in job.vehicles] == n0:
            return
        ends = [v.busy_until for v in job.vehicles]
        if max(ends) - min(ends) > 1e-9:
            v_["team"] += 1
        cap = sum(v.cls.capacity_kg for v in job.vehicles)
        for load in (job.items, job.backhaul):
            if sum(c.mass_kg for c in load) > cap + 1e-6:
                v_["capacity"] += 1
        for v in job.vehicles:
            jobs.setdefault(v.id, []).append((sim.t, v.busy_until))
    sim._advance_to, sim._push, sim._start_job = adv, push, start
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sim.run()
    n_jobs = 0
    for iv in jobs.values():
        iv.sort()
        n_jobs += len(iv)
        v_["overlap"] += sum(1 for (s0, e0), (s1, e1) in zip(iv[:-1], iv[1:]) if s1 < e0 - 1e-9)
    for c in sim.all_cargo:
        if c.t_picked is not None and (c.t_picked < c.t_ready - 1e-9 or
                                       (c.t_delivered is not None and c.t_delivered < c.t_picked - 1e-9)):
            v_["order"] += 1
    v_["jobs"] = n_jobs
    return v_


def check_d8_invariants() -> List[Dict]:
    from . import dispatch
    from .engine import Simulation
    from .config import library
    t0 = time.time()
    tot = {}
    n_runs = 0
    runs = [(library()[n], m, s) for n in ("P1-default", "P2-default", "P3-default")
            for m in (dispatch.inhouse, dispatch.pooled_greedy, dispatch.central_assign, dispatch.marketplace)
            for s in (0, 1)]
    for sc, mech, seed in runs:
        r = _invariant_run(Simulation(sc, mech, seed=seed))
        n_runs += 1
        for k, v in r.items():
            tot[k] = tot.get(k, 0) + v
    p5 = 0
    for regime, sim in _p5_sims(("O_ORACLE", "A_MOON", "C_AUCTION", "C_LEADER"), seeds=(1,), days=120):
        r = _invariant_run(sim)
        n_runs += 1
        p5 += 1
        for k, v in r.items():
            tot[k] = tot.get(k, 0) + v
    n_jobs = tot.pop("jobs")
    bad = sum(tot.values())
    up = 1 - 0.05 ** (1 / n_runs)
    return [_row("D8", "all invariants", "Trace invariants: clock order, no event in the past, no vehicle in two jobs, "
                 "team interval, capacity, item time order", 0.0, float(bad), 0.0, "violations",
                 f"{n_runs} runs ({n_runs - p5} library: P1/P2/P3-default x 4 job rules x 2 seeds; {p5} ATC regimes on "
                 f"the p5 3eq scenario, 120 days), {n_jobs:,} jobs; violations by kind: "
                 + ", ".join(f"{k} {v}" for k, v in tot.items()), "traces", "code verification", "V", "P1",
                 ["P1", "P2", "P3"], mode="abs", source="Balci 1998 (assertion checking); Sargent 2013 (traces)",
                 exposure={"n": n_runs, "unit": "runs", "upper95": up, "jobs": n_jobs}, t0=t0)]


# ------------------------------------------------------------------------------------------------ D10
def _p5_sims(regimes, seeds=(1,), days=None, split="3eq"):
    """Simulations (not yet run) of ATC regimes on the p5 scenario as the experiments build them."""
    for p in (_repo(), _repo("experiments", "phase5")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import run_phase5 as RP
    from .engine import Simulation
    from .atc import regimes as G
    from .atc import p5 as P5
    kws = {lab: kw for lab, _, kw in RP.REGIMES_E40}
    for seed in seeds:
        for regime in regimes:
            sc = P5.build(split, k=RP.E43_K30, team_lift_share=0.10)
            if days:
                sc = sc.with_(horizon_h=days * 24.0)
            kw = dict(kws.get(regime, kws.get(regime + " 0.8", {})))
            kw["start_year"] = 2028
            name = regime.split()[0]
            yield regime, Simulation(sc, G.mechanism(name), seed=seed, mech_kwargs=kw)


def check_d10_crn() -> List[Dict]:
    import pandas as pd
    import warnings
    rows = []
    t0 = time.time()
    regs = ("O_ORACLE", "A_EARTH strict", "A_MOON", "B_EARTH strict", "B_EARTH_RELAY 0.8", "C_LEADER", "C_AUCTION",
            "C_LEARNED_MLP")
    mani = {}
    for regime, sim in _p5_sims(regs, seeds=(11,), days=90):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            sim.run()
        mani[regime] = tuple((c.id, c.owner, round(c.mass_kg, 9), c.origin, c.dest, c.t_landed, c.t_ready, c.priority)
                             for c in sorted(sim.all_cargo, key=lambda c: c.id) if c.cls != "return")
    ref = mani["O_ORACLE"]
    diff = [r for r, m in mani.items() if m != ref]
    rows.append(_row("D10", "manifest", "Same landed manifest for every ATC regime (seed 11)", 0.0, float(len(diff)), 0.0,
                     "regimes differing", f"{len(regs)} regimes on the p5 3eq scenario, 90 days, {len(ref)} items "
                     f"(return items excluded: they follow deliveries); differing: {diff or 'none'}",
                     "internal validity", "results robustness", "V", "P1", ["P1", "P2"], mode="abs",
                     source="Law 2015 ch. 11; extends check 11", t0=t0))
    d = pd.read_csv(_repo("results", "E40_runs.csv"))
    d["owners"] = d["cell"].str.extract(r"owners=(\w+)")
    d = d[(d["owners"] == "3eq") & (d["load"].astype(str) == "10")]
    key = ["seed", "start_year"]                       # the CRN unit: a seed in a start year
    t0 = time.time()
    dem = d.groupby(key + ["label"])[["landed_kg", "landings"]].mean().reset_index()
    ref_dem = dem[dem["label"] == "O_ORACLE"].set_index(key)
    n_pairs = n_bad = 0
    for lab in sorted(set(dem["label"]) - {"O_ORACLE"}):
        x = dem[dem["label"] == lab].set_index(key)
        common = x.index.intersection(ref_dem.index)
        n_pairs += len(common)
        n_bad += int(((x.loc[common, "landed_kg"] - ref_dem.loc[common, "landed_kg"]).abs() > 1e-6).sum()
                     + (x.loc[common, "landings"] != ref_dem.loc[common, "landings"]).sum())
    rows.append(_row("D10", "E40 demand identical", "Common demand in the experiment itself: every regime's E40 run has "
                     "O_ORACLE's landed mass and landings (same seed and start year)", 0.0, float(n_bad), 0.0,
                     "differing pairs", f"{n_pairs} regime pairs at 10 % load, 3eq; the demand stream (landings, "
                     "manifests) is common. The operations stream (per-job driving interventions and fault redraws, "
                     "engine rng_ops) is shared in draw order and desynchronises once allocations differ (seed 11: draw "
                     "18, about the sixth job, for every regime, the C regimes included)", "internal validity",
                     "results robustness", "V", "P1", ["P1", "P2"], mode="abs", source="Law 2015 ch. 11", t0=t0))
    base = d[d["label"] == "O_ORACLE"].groupby(key)["delay_mean_h"].mean()
    for lab in sorted(set(d["label"]) - {"O_ORACLE"}):
        t0 = time.time()
        x = d[d["label"] == lab].groupby(key)["delay_mean_h"].mean()
        s = sorted(set(x.index) & set(base.index))
        if len(s) < 4:
            continue
        a, b = x.loc[s].to_numpy(), base.loc[s].to_numpy()
        r = float(np.corrcoef(a, b)[0, 1])
        if r > 1 - 1e-12:                               # identical outputs (the regime reduces to the reference)
            lo = hi = 1.0
        else:
            z, se = math.atanh(r), 1 / math.sqrt(len(s) - 3)
            lo, hi = math.tanh(z - 1.96 * se), math.tanh(z + 1.96 * se)
        vrf = float(np.var(a - b, ddof=1) / (np.var(a, ddof=1) + np.var(b, ddof=1)))
        row = _row("D10", f"pairing {lab}", f"CRN pairing reduces variance against O_ORACLE (correlation's 95 % CI "
                         f"above zero): {lab} (E40, 10 % load, 3eq)",
                         1.0, float(lo > 0 and vrf < 1), 0.0, "pass", f"seeds shared: the exact demand check passes "
                         f"({n_pairs} regime pairs, {n_bad} differing in landed mass or landings; row 'E40 demand "
                         f"identical'). {len(s)} paired runs (seed, start year), mean delay per delivery: "
                         f"correlation {r:.3f} (95 % CI {lo:.3f} to {hi:.3f}), variance-reduction factor "
                         f"Var(X - Y) / (Var X + Var Y) = {vrf:.3f}; passes when the CI excludes 0 and the factor < 1 (pairing "
                         "effectiveness, not stream integrity: see the demand rows)",
                         "internal validity", "results robustness", "V", "P1", ["P1", "P2"], mode="abs",
                         source="Law 2015 ch. 11 (common random numbers)", t0=t0,
                         tol_src="research_notes/Lunar ATC/verification_plan.md section 3, row D10")
        row["detail"] = {"corr": r, "corr_lo": lo, "corr_hi": hi, "vrf": vrf, "n": len(s)}
        rows.append(row)
    return rows


# ------------------------------------------------------------------------------------------------ D11
def check_d11_inputs(years: int = 400) -> List[Dict]:
    """D11: the input generators against their specification: yearly landing counts Poisson (chi-squared), gaps
    exponential (KS), item masses uniform per class (KS, on items whose acceptance cannot depend on their own mass),
    destination shares per class (chi-squared). Holm across the family at alpha 0.01."""
    from scipy import stats
    import lunarsim.scenario as scn
    from .scenario import Scenario, sample_landings, sample_cargo_manifest, HOURS_PER_DAY
    t0 = time.time()
    rng = np.random.default_rng(11)
    rates = {"CLPS": 4.0, "MK1": 2.0, "LARGE": 1.0}
    sc = Scenario(landings_per_year=rates, horizon_h=years * 365 * HOURS_PER_DAY)
    pads = ["PAD_A", "PAD_B"]
    sched = sample_landings(rng, sc, pads)
    tests = []
    for name, rate in rates.items():
        t = np.array([x[0] for x in sched if x[1].name == name])
        counts = np.bincount((t // (365 * HOURS_PER_DAY)).astype(int), minlength=years)[:years]
        kmax = int(stats.poisson.ppf(0.999, rate))
        obs = np.array([np.sum(counts == k) for k in range(kmax)] + [np.sum(counts >= kmax)], float)
        exp = np.array([stats.poisson.pmf(k, rate) for k in range(kmax)] + [stats.poisson.sf(kmax - 1, rate)]) * years
        while len(exp) > 2 and exp[-1] < 5:            # pool the tail until every expected count is at least 5
            exp[-2] += exp[-1]; obs[-2] += obs[-1]; exp, obs = exp[:-1], obs[:-1]
        while len(exp) > 2 and exp[0] < 5:
            exp[1] += exp[0]; obs[1] += obs[0]; exp, obs = exp[1:], obs[1:]
        p = stats.chisquare(obs, exp).pvalue
        tests.append((f"{name} yearly counts Poisson({rate:g})", p, f"chi-squared over {years} years"))
        gaps = np.diff(t)
        p = stats.kstest(gaps, "expon", args=(0, 365 * HOURS_PER_DAY / rate)).pvalue
        tests.append((f"{name} gaps exponential", p, f"KS on {len(gaps)} gaps"))
    masses = {lab: [] for lab, *_ in scn.CARGO_CLASSES}
    dests = {lab: [] for lab, *_ in scn.CARGO_CLASSES}
    cid = 0
    for t_land, lt, pad in sched:                       # destinations: the real landers
        items, cid = sample_cargo_manifest(rng, lt, ["NASA"], pads, t_land, 0.5, cid, pad=pad)
        for c in items:
            if c.cls != "consumables" or c.dest in ("BASE", "DEPOT"):
                dests[c.cls].append(c.dest)
    # masses: a test-only 100 t lander, so that most items are drawn where no draw of any class can be replaced by a
    # fill crate (cumulative mass + the largest possible item below the payload); those items are unbiased draws
    from .scenario import LanderType
    big = LanderType("VV_BIG", (100000.0, 100000.0), (6.0, 24.0), True, 15000.0)
    h_any = max(min(x[1][1], big.max_item_kg) for x in scn.CARGO_CLASSES)
    for j in range(60):
        items, cid = sample_cargo_manifest(rng, big, ["NASA"], pads, 0.0, 0.5, cid, pad=pads[0])
        before = 0.0
        for c in items:
            lo, hi = next(x for x in scn.CARGO_CLASSES if x[0] == c.cls)[1]
            if before + h_any < big.payload_kg[0]:
                masses[c.cls].append((c.mass_kg, lo, min(hi, big.max_item_kg)))
            before += c.mass_kg
    for lab, lst in masses.items():
        for hi2 in sorted({x[2] for x in lst}):
            m = np.array([x[0] for x in lst if x[2] == hi2])
            lo = next(x for x in scn.CARGO_CLASSES if x[0] == lab)[1][0]
            if len(m) < 50:
                continue
            p = stats.kstest(m, "uniform", args=(lo, hi2 - lo)).pvalue
            tests.append((f"{lab} mass U({lo:g}, {hi2:g})", p, f"KS on {len(m)} items"))
    for lab, dw, in [(x[0], x[2]) for x in scn.CARGO_CLASSES]:
        obs = np.array([dests[lab].count(k) for k in dw], float)
        if obs.sum() < 50:
            continue
        exp = np.array(list(dw.values())) / sum(dw.values()) * obs.sum()
        p = stats.chisquare(obs, exp).pvalue
        tests.append((f"{lab} destinations", p, f"chi-squared on {int(obs.sum())} items"))
    # Holm at alpha 0.01
    order = sorted(range(len(tests)), key=lambda i: tests[i][1])
    m = len(tests)
    reject = [False] * m
    for rank, i in enumerate(order):
        if tests[i][1] <= 0.01 / (m - rank):
            reject[i] = True
        else:
            break
    rows = []
    for (name, p, how), rj in zip(tests, reject):
        rows.append(_row("D11", name, f"Input distribution: {name}", 0.0, float(rj), 0.0, "rejected",
                         f"{how}; p = {p:.4f}; Holm across {m} tests at alpha 0.01", "historical data", "input pedigree",
                         "Val", "P2", ["P1"], mode="abs", source="Law 2015 ch. 6", t0=t0,
                         tol_src="research_notes/Lunar ATC/verification_plan.md section 2.2 rule 4: alpha 0.01, Holm"))
    return rows


# ================================================================================================ batch 2 (B-79)
# auction and team lifts (A), radio and messages (R), regimes (X6), learned policy (L)

def _p5_sim(regime: str, kw: Dict, seed: int = 1, days: float = 90.0, split: str = "3eq", mutate=None):
    """One ATC simulation (not yet run) on the p5 scenario as the experiments build it, with explicit settings."""
    for p in (_repo(), _repo("experiments", "phase5")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import run_phase5 as RP
    from .engine import Simulation
    from .atc import regimes as G
    from .atc import p5 as P5
    sc = P5.build(split, k=RP.E43_K30, team_lift_share=0.10)
    if days:
        sc = sc.with_(horizon_h=days * 24.0)
    if mutate is not None:
        sc = mutate(sc)
    k = dict(kw)
    k.setdefault("start_year", 2028)
    return Simulation(sc, G.mechanism(regime), seed=seed, mech_kwargs=k)


def _items_digest(sim) -> str:
    rec = [(c.id, c.owner, round(c.mass_kg, 9), c.origin, c.dest, c.t_ready, c.t_picked, c.t_delivered, c.carrier,
            c.team_size) for c in sorted(sim.all_cargo, key=lambda c: c.id)]
    return hashlib.md5(json.dumps(rec, default=str).encode()).hexdigest()


def _run_quiet(sim):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return sim.run()


PERFECT = {"loss": 0.0, "radio": "perfect", "base_mtbf_h": 1e15}


def check_a2_degenerate() -> List[Dict]:
    """A2: with perfect communication (no loss, every robot hears every other, the base computer never fails) the
    decentralised auction gives the centralised marketplace's awards (O_ORACLE)."""
    rows = []
    for seed in (1, 2, 3):
        t0 = time.time()
        d = {}
        for reg, kw in (("O_ORACLE", {}), ("C_AUCTION", dict(PERFECT))):
            sim = _p5_sim(reg, kw, seed=seed)
            _run_quiet(sim)
            d[reg] = (_items_digest(sim), len(sim.all_cargo))
        rows.append(_row("A2", f"seed {seed}", f"Decentralised auction = centralised marketplace under perfect "
                         f"communication (seed {seed})", 1.0, float(d["O_ORACLE"][0] == d["C_AUCTION"][0]), 0.0, "match",
                         f"md5 of every item record (pickup, delivery, carrier, team size), p5 3eq, 90 days, "
                         f"{d['O_ORACLE'][1]} items: {d['O_ORACLE'][0][:12]} vs {d['C_AUCTION'][0][:12]}; C_AUCTION with "
                         "loss 0, radio 'perfect', base computer MTBF 1e15 h", "degenerate tests", "code verification",
                         "V", "P1", ["P1"], mode="abs", source="design identity (lunarsim/atc/auction.py)", t0=t0))
    return rows


def check_a6_metamorphic() -> List[Dict]:
    """A6: (a) relabelling the owners, (b) multiplying every bid by k > 0, (d) one robot: the auction's awards are
    unchanged (a, b) or equal the marketplace's for that robot (d)."""
    from . import dispatch as D
    rows = []
    t0 = time.time()
    perm = {"A": "B", "B": "C", "C": "A"}

    def relabel(sc):
        from .scenario import BulkFlow
        import dataclasses
        return sc.with_(fleet=[(perm.get(f[0], f[0]),) + tuple(f[1:]) for f in sc.fleet],
                        cargo_owners=[perm.get(o, o) for o in sc.cargo_owners],
                        bulk_flows=[dataclasses.replace(b, owner=perm.get(b.owner, b.owner)) for b in sc.bulk_flows])
    out = {}
    for tag, mut in (("base", None), ("relabelled", relabel)):
        sim = _p5_sim("C_AUCTION", {"loss": 0.10}, seed=4, mutate=mut)
        _run_quiet(sim)
        out[tag] = [(c.id, c.t_picked, c.t_delivered, c.carrier, c.team_size, perm.get(c.owner, c.owner) if tag == "base"
                     else c.owner) for c in sorted(sim.all_cargo, key=lambda c: c.id)]
    same = out["base"] == out["relabelled"]
    rows.append(_row("A6", "owner relabelling", "Auction awards unchanged when owners are relabelled (A->B->C->A)", 1.0,
                     float(same), 0.0, "match", f"C_AUCTION, loss 0.10, terrain radio, seed 4, 90 days, "
                     f"{len(out['base'])} items: every item's pickup, delivery, carrier and team size, owners mapped",
                     "metamorphic testing", "code verification", "V", "P1", ["P1"], mode="abs",
                     source="Burkard, Dell'Amico and Martello 2009; Chen et al. 2018", t0=t0))
    t0 = time.time()
    real = D._bid
    dig = {}
    try:
        for k in (1.0, 3.7):
            D._bid = (lambda *a, _k=k, **kw: _k * real(*a, **kw))
            for reg, kw in (("C_AUCTION", {"loss": 0.10}), ("O_ORACLE", {})):
                sim = _p5_sim(reg, kw, seed=5)
                _run_quiet(sim)
                dig[(k, reg)] = _items_digest(sim)
    finally:
        D._bid = real
    for reg in ("C_AUCTION", "O_ORACLE"):
        rows.append(_row("A6", f"bid scaling, {reg}", f"Awards unchanged when every bid is multiplied by 3.7 ({reg})",
                         1.0, float(dig[(1.0, reg)] == dig[(3.7, reg)]), 0.0, "match",
                         f"md5 of item records, seed 5, 90 days (test-only: dispatch._bid x 3.7): "
                         f"{dig[(1.0, reg)][:12]} vs {dig[(3.7, reg)][:12]}", "metamorphic testing", "code verification",
                         "V", "P1", ["P1"], mode="abs", source="Chen et al. 2018 (scale invariance of argmin)", t0=t0))
    t0 = time.time()
    one = lambda sc: sc.with_(fleet=[next(f for f in sc.fleet if f[1] == "CARGO_FLEX")])
    d1 = {}
    for reg, kw in (("O_ORACLE", {}), ("C_AUCTION", dict(PERFECT))):
        sim = _p5_sim(reg, kw, seed=6, mutate=one)
        _run_quiet(sim)
        d1[reg] = _items_digest(sim)
    rows.append(_row("A6", "one robot", "One robot: the auction's awards equal the marketplace's", 1.0,
                     float(d1["O_ORACLE"] == d1["C_AUCTION"]), 0.0, "match", f"owner A's CARGO_FLEX alone (the p5 fleet's largest carrier), "
                     f"perfect communication, seed 6, 90 days: {d1['O_ORACLE'][:12]} vs {d1['C_AUCTION'][:12]}",
                     "degenerate tests", "code verification", "V", "P1", ["P1"], mode="abs", source="Chen et al. 2018",
                     t0=t0))
    return rows


def _job_log(sim):
    """Hook: every started job as (start, end, vehicle ids, owners, item ids, item mass, capacities, revenue shares,
    price)."""
    log = []
    real = sim._start_job

    def start(job, _rs=real):
        n0 = [v.jobs for v in job.vehicles]
        r0 = [v.revenue_musd for v in job.vehicles]
        _rs(job)
        if [v.jobs for v in job.vehicles] == n0:
            return
        log.append({"t": sim.t, "ends": [v.busy_until for v in job.vehicles], "vids": [v.id for v in job.vehicles],
                    "owners": [v.owner for v in job.vehicles], "items": [c.id for c in job.items + job.backhaul],
                    "objs": [id(c) for c in job.items + job.backhaul],
                    "mass": sum(c.mass_kg for c in job.items), "caps": [v.cls.capacity_kg for v in job.vehicles],
                    "shares": [(v.revenue_musd - a) * 1e6 for v, a in zip(job.vehicles, r0)]})
    sim._start_job = start
    return log


def check_a7_no_double() -> List[Dict]:
    """A7 (as the auction implements it): under message loss and partitions, no item is ever carried by two jobs;
    duplicates the auction believes it won end as wasted trips or conflicts settled by the CBBA rule."""
    t0 = time.time()
    cells = [("C_AUCTION", {"loss": 0.10}), ("C_AUCTION", {"loss": 0.40}), ("C_AUCTION", {"loss": 0.25, "loss_model": "burst"}),
             ("C_AUCTION", {"loss": 0.25, "depth": 5}), ("C_LEADER", {"loss": 0.40})]
    dup = jobs = wasted = conflicts = runs = 0
    for reg, kw in cells:
        for seed in (1, 2):
            sim = _p5_sim(reg, kw, seed=seed)
            log = _job_log(sim)
            out = _run_quiet(sim)
            objs = [i for j in log for i in j["objs"]]            # by object: cargo ids can repeat (row D8 ids)
            dup += len(objs) - len(set(objs))
            jobs += len(log)
            runs += 1
            wasted += int(out.get("atc_wasted_trips", 0) or 0)
            conflicts += int(out.get("atc_conflicts", 0) or 0)
    return [_row("A7", "no item carried twice", "Under loss and partitions no item is carried by two jobs", 0.0,
                 float(dup), 0.0, "items", f"{runs} runs (C_AUCTION loss 0.10 / 0.40 / burst 0.25 / depth 5 at 0.25; "
                 f"C_LEADER loss 0.40; seeds 1-2, 90 days), {jobs:,} jobs; duplicates the robots believed they won: "
                 f"{wasted} wasted trips, {conflicts} conflicts settled by the CBBA rule (summary counters)",
                 "event validity", "code verification", "V", "P1", ["P1", "P2"], mode="abs",
                 source="Johnson et al. 2011 (ACBBA); Choi et al. 2009", exposure={"n": runs, "unit": "runs",
                 "upper95": 1 - 0.05 ** (1 / runs), "jobs": jobs}, t0=t0)]


def check_d8_ids() -> List[Dict]:
    """D8 (added, B-79 batch 2): every cargo item has its own id (the engine reused ids until 7247b8e)."""
    from collections import Counter
    t0 = time.time()
    reused = items = runs = 0
    for reg, kw in (("O_ORACLE", {}), ("C_AUCTION", {"loss": 0.10})):
        for seed in (1, 2):
            sim = _p5_sim(reg, kw, seed=seed, days=365)
            _run_quiet(sim)
            cnt = Counter(c.id for c in sim.all_cargo)
            reused += sum(n - 1 for n in cnt.values() if n > 1)
            items += len(sim.all_cargo)
            runs += 1
    return [_row("D8", "cargo ids unique", "Every cargo item has its own id", 0.0, float(reused), 0.0, "ids reused",
                 f"{runs} one-year p5 runs (O_ORACLE, C_AUCTION; seeds 1-2), {items:,} items. Found failing on a46353b; "
                 "fixed in 7247b8e; outcome-neutral on 48 of 48 reruns (results/id_fix_evidence.json; PREREG change "
                 "10). The defect: manifests used Simulation._cid as the next free id while return items and bulk lots "
                 "advanced it before use, so the next landing reused an id (12-18 of about 2,970 items a year)",
                 "traces", "code verification", "V", "P1", ["P1", "P2", "P3"], mode="abs",
                 source="Balci 1998 (assertion checking)", t0=t0)]


def check_a9_team_lifts() -> List[Dict]:
    """A9: a team forms only when the members' capacities cover the item; members share the job interval; the price
    is split equally and the shares sum to it; team scope 'same_owner' pairs one owner's robots only."""
    t0 = time.time()
    cells = [({"loss": 0.0}, "any"), ({"loss": 0.25}, "any"), ({"loss": 0.25, "commit": False}, "any"),
             ({"loss": 0.10, "team_scope": "same_owner"}, "same_owner")]
    v = {"capacity": 0, "interval": 0, "split": 0, "scope": 0}
    teams = runs = 0
    cross = 0
    for kw, scope in cells:
        for seed in (1, 2):
            sim = _p5_sim("C_AUCTION", kw, seed=seed, days=180)
            log = _job_log(sim)
            _run_quiet(sim)
            runs += 1
            for j in log:
                if len(j["vids"]) < 2:
                    continue
                teams += 1
                cross += len(set(j["owners"])) > 1
                v["capacity"] += j["mass"] > sum(j["caps"]) + 1e-6
                v["interval"] += max(j["ends"]) - min(j["ends"]) > 1e-9
                tot = sum(j["shares"])
                v["split"] += max(j["shares"]) - min(j["shares"]) > 1e-6 * max(1.0, abs(tot))
                v["scope"] += scope == "same_owner" and len(set(j["owners"])) > 1
    bad = sum(v.values())
    return [_row("A9", "team lifts", "Team lifts: capacity covers the item, shared interval, equal price split, scope "
                 "respected", 0.0, float(bad), 0.0, "violations", f"{runs} runs (C_AUCTION, team share 0.10; loss 0 / "
                 f"0.25 / 0.25 without commit / scope same_owner at 0.10; seeds 1-2, 180 days), {teams} team jobs "
                 f"({cross} cross-owner); by kind: " + ", ".join(f"{k} {x}" for k, x in v.items()),
                 "traces", "code verification", "V", "P1", ["P1"], mode="abs",
                 source="Gerkey and Mataric, IJRR 23(9):939-954, 2004", exposure={"n": teams, "unit": "team jobs",
                 "upper95": 1 - 0.05 ** (1 / max(teams, 1))}, t0=t0)]


def check_a_not_applicable() -> List[Dict]:
    why = ("C_AUCTION is a sequential single-item auction (marketplace bids) that borrows only CBBA's conflict rule "
           "(lunarsim/atc/auction.py); ")
    out = []
    for cid, name, w in (("A1", "Single-item epsilon-auction within n epsilon of the optimum",
                          "the code has no epsilon-auction; central assignment's optimality is D9"),
                         ("A3", "CBBA convergence within N_t x D rounds and agreement",
                          "the CBBA bound does not apply; the auction's own round limit and its agreement (no item "
                          "carried twice) are A2 and A7"),
                         ("A4", "CBBA score at least half the optimum", "the 50 % guarantee is CBBA's; not claimed"),
                         ("A5", "Learned score has diminishing marginal gain", "DMG is the condition of CBBA's "
                          "guarantees, which the papers do not claim; the learned correction adds to a bundle bid")):
        r = _row(cid, "not applicable", name, float("nan"), float("nan"), 0.0, "", why + w, "analytic",
                 "code verification", "V", "P1", ["P1"], mode="abs", source="Choi, Brunet and How 2009")
        r["skipped"] = "not applicable: " + w
        r["passed"] = False
        out.append(r)
    return out


# ------------------------------------------------------------------------------------------------ radio and messages
def check_r2_reciprocity(n_pairs: int = 3000) -> List[Dict]:
    """R2: the mesh builder's clearance of a -> b with heights (h_a, h_b) equals b -> a with (h_b, h_a), on the real
    terrain, for a random sample of the file's pairs; and the recomputation reproduces the stored file."""
    t0 = time.time()
    sys.path.insert(0, _repo("tools", "atc"))
    try:
        import mesh as MESH
    finally:
        sys.path.pop(0)
    from .terrain import Terrain
    from .atc.radio import RadioMesh
    m = RadioMesh()
    rng = np.random.default_rng(22)
    near = np.flatnonzero(m.d <= 5000.0)
    k = rng.choice(near, n_pairs, replace=False)
    I, J = m.I[k], m.J[k]
    t = Terrain(MESH.EL.PACK)
    combos = m.combos
    fw, _ = MESH.pair_profiles(t, m.xy, I, J, combos)
    bw, _ = MESH.pair_profiles(t, m.xy, J, I, [(b, a) for a, b in combos])
    asym = int(np.sum(MESH.encode_clear(fw) != MESH.encode_clear(bw)))
    stored = m.clear_dm[:, k]
    repro = int(np.sum(MESH.encode_clear(fw) != stored))
    base = (f"{n_pairs} random pairs within 5 km of mesh-v1 ({m.n} points), 4 height combinations, clearance encoded "
            "as the file does (0.1 m)")
    return [_row("R2", "reciprocity", "Radio reciprocity: a hears b iff b hears a (clearance a->b = b->a)", 0.0,
                 float(asym), 0.0, "pair-combos", base + "; terrain profiles recomputed both ways", "metamorphic testing",
                 "code verification", "V", "P1", ["P2", "P3"], mode="abs", source="geometry", t0=t0),
            _row("R2", "file reproduces", "The mesh file's clearances reproduce from the terrain", 0.0, float(repro), 0.0,
                 "pair-combos", base + "; recomputed against the stored file", "comparison to other models",
                 "solution verification", "V", "P1", ["P2", "P3"], mode="abs", source="tools/atc/mesh.py", t0=t0)]


def check_r7_graph() -> List[Dict]:
    """R7: mesh diameter by BFS (radio.hops) equals Floyd-Warshall; component count equals union-find; with no loss a
    broadcast reaches every node within D x hop latency."""
    from scipy.sparse.csgraph import floyd_warshall, connected_components
    from .atc.radio import RadioMesh
    from .atc.messages import Channel, HOP_LATENCY_S
    rows = []
    m = RadioMesh()
    rng = np.random.default_rng(7)
    for sub, h, dmax in (("2.5 m, 5 km", 2.5, 5000.0), ("1.0 m, 3 km", 1.0, 3000.0)):
        t0 = time.time()
        sel = np.sort(rng.choice(m.n, 600, replace=False))
        sel = np.union1d(sel, [m.base])
        G = m.graph(h, d_max_m=dmax)[sel][:, sel]
        fw = floyd_warshall(G, directed=False, unweighted=True)
        # BFS from every node with radio.hops' method (scipy shortest_path, unweighted) on the same subgraph
        from scipy.sparse.csgraph import shortest_path
        bfs = shortest_path(G, directed=False, unweighted=True, method="D")
        diff = int(np.sum(~((fw == bfs) | (np.isinf(fw) & np.isinf(bfs)))))
        fin = np.isfinite(fw)
        D_fw = int(fw[fin].max())
        # union-find over the links
        par = list(range(len(sel)))

        def find(x):
            while par[x] != x:
                par[x] = par[par[x]]
                x = par[x]
            return x
        Gc = G.tocoo()
        for a, b in zip(Gc.row, Gc.col):
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                par[ra] = rb
        n_uf = len({find(x) for x in range(len(sel))})
        n_cc = connected_components(G, directed=False)[0]
        rows.append(_row("R7", sub + ": shortest paths", f"Mesh hop counts: BFS equals Floyd-Warshall ({sub})", 0.0,
                         float(diff), 0.0, "pairs", f"{len(sel)} mesh points (600 random + BASE), antenna {h} m, d_max "
                         f"{dmax / 1000:g} km, BASE with its mast; diameter of the largest component {D_fw} hops",
                         "comparison to other models", "code verification", "V", "P1", ["P2", "P3"], mode="abs",
                         source="Floyd 1962; scipy.sparse.csgraph", t0=t0))
        rows.append(_row("R7", sub + ": components", f"Mesh components: scipy equals union-find ({sub})", float(n_uf),
                         float(n_cc), 0.0, "components", f"same subgraph; {n_cc} components", "comparison to other models",
                         "code verification", "V", "P1", ["P2", "P3"], mode="abs", source="Tarjan 1975 (union-find)",
                         t0=t0))
        ch = Channel(0.0)
        b = int(np.searchsorted(sel, m.base))
        hops = fw[b][np.isfinite(fw[b])].astype(int)
        lat = max(ch.send(int(x))[1] for x in hops)
        ecc = int(hops.max())
        rows.append(_row("R7", sub + ": broadcast latency", f"No-loss broadcast from BASE reaches its component within "
                         f"eccentricity x hop latency ({sub})", ecc * HOP_LATENCY_S, lat, 1e-9, "s",
                         f"{len(hops)} reachable points, eccentricity {ecc} hops, hop latency {HOP_LATENCY_S * 1000:g} ms "
                         "(lunarsim.atc.messages)", "analytic", "code verification", "V", "P1", ["P2", "P3"],
                         source="lunarsim/atc/messages.py", t0=t0))
    return rows


def check_r9_messages(n: int = 200000) -> List[Dict]:
    """R9 (added to the plan: the message model): Bernoulli delivery over h hops = (1 - p)^h; the Gilbert-Elliott
    chain's stationary loss = p and mean loss burst = MEAN_BURST; messages = delivered + lost."""
    from scipy import stats
    from .atc.messages import Channel, MEAN_BURST
    rows = []
    for p, h in ((0.10, 1), (0.10, 3), (0.40, 2)):
        t0 = time.time()
        ch = Channel(p, rng=np.random.default_rng(int(100 * p) + h))
        ok = sum(ch.send(h)[0] for _ in range(n))
        ref = (1 - p) ** h
        tol = 4.0 * math.sqrt(ref * (1 - ref) / n) / ref
        rows.append(_row("R9", f"bernoulli p {p:g}, {h} hops", f"Message delivery, Bernoulli loss {p:g} over {h} hop(s) "
                         "= (1 - p)^h", ref, ok / n, tol, "share", f"{n:,} messages; messages = delivered + lost: "
                         f"{ch.messages == ok + ch.lost}", "analytic", "code verification", "V", "P1", ["P1", "P2"],
                         source="lunarsim/atc/messages.py", t0=t0,
                         tol_src="4 binomial standard errors (a correct model fails with probability 6e-5)"))
    t0 = time.time()
    p = 0.25
    ch = Channel(p, model="burst", rng=np.random.default_rng(9))
    lost = np.array([not ch.send(1)[0] for _ in range(n)])
    share = float(lost.mean())
    edges = np.flatnonzero(np.diff(np.concatenate([[0], lost.astype(int), [0]])))
    runs = edges[1::2] - edges[::2]
    nb = 20
    b = lost[: n // nb * nb].reshape(nb, -1).mean(1)
    hw = stats.t.ppf(0.995, nb - 1) * b.std(ddof=1) / math.sqrt(nb)
    rows.append(_row("R9", "burst: stationary loss", f"Burst (Gilbert-Elliott) loss: stationary share = {p:g}", p, share,
                     0.05, "share", f"{n:,} one-hop messages; 99 % batch-means interval +/- {hw:.4f}", "analytic",
                     "code verification", "V", "P1", ["P1", "P2"], source="Gilbert 1960; Elliott 1963", ci=(share - hw,
                     share + hw), t0=t0, tol_src="5 % relative; the interval's half-width is about a third of it"))
    rows.append(_row("R9", "burst: mean run", f"Burst loss: mean run of lost messages = {MEAN_BURST:g}", MEAN_BURST,
                     float(runs.mean()), 0.05, "messages", f"{len(runs):,} loss runs", "analytic", "code verification",
                     "V", "P1", ["P1", "P2"], source="Gilbert 1960; lunarsim.atc.messages MEAN_BURST", t0=t0,
                     tol_src="5 % relative (standard error about 1 % at this many runs)"))
    return rows


# ------------------------------------------------------------------------------------------------ regimes
def check_x6_earth_independent() -> List[Dict]:
    """X6 (added: the regimes' design claim behind PREREG change 4): a regime that never waits for Earth gives the
    same run whatever the start year; an Earth-dependent one does not (the control). Full relay coverage equals
    O_ORACLE."""
    for p in (_repo(), _repo("experiments", "phase5")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import run_phase5 as RP
    kws = {lab: (reg, kw) for lab, reg, kw in RP.REGIMES_E40}
    rows = []
    for lab in ("O_ORACLE", "B_EARTH_RELAY 1.0", "C_LEADER", "C_AUCTION", "C_LEARNED_MLP", "C_LEARNED_LIN",
                "A_EARTH strict"):
        t0 = time.time()
        reg, kw = kws[lab]
        d = []
        for y in (2028, 2038):
            sim = _p5_sim(reg, dict(kw, start_year=y), seed=3)
            _run_quiet(sim)
            d.append(_items_digest(sim))
        indep = lab in RP.EARTH_INDEPENDENT
        rows.append(_row("X6", f"start year, {lab}", f"{'Earth-independent' if indep else 'Earth-dependent (control)'} "
                         f"regime {lab}: {'same' if indep else 'different'} run in 2028 and 2038", 1.0,
                         float((d[0] == d[1]) == indep), 0.0, "pass", f"md5 of item records, seed 3, 90 days: "
                         f"{d[0][:12]} vs {d[1][:12]}; listed in run_phase5.EARTH_INDEPENDENT: {indep}",
                         "degenerate tests", "code verification", "V", "P1", ["P1", "P2"], mode="abs",
                         source="PREREG change 4 (paper/atc/PREREG.md)", t0=t0))
    t0 = time.time()
    d = []
    for reg, kw in (("O_ORACLE", {}), kws["B_EARTH_RELAY 1.0"]):
        sim = _p5_sim(reg, dict(kw), seed=3)
        _run_quiet(sim)
        d.append(_items_digest(sim))
    rows.append(_row("X6", "full relay = oracle", "B_EARTH_RELAY with full coverage equals O_ORACLE", 1.0,
                     float(d[0] == d[1]), 0.0, "match", f"md5 of item records, seed 3, 90 days: {d[0][:12]} vs "
                     f"{d[1][:12]}", "degenerate tests", "code verification", "V", "P1", ["P1", "P2"], mode="abs",
                     source="regimes.py: B_EARTH decides only while linked; coverage 1.0 links always", t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ learned policy
def check_l_policy() -> List[Dict]:
    from .atc.learned import Policy
    rows = []
    for pid in ("atc_bid_v1", "atc_bid_linear_v1"):
        t0 = time.time()
        pol = Policy(_repo("data", "policies", pid + ".json"))
        chk = json.load(open(_repo("data", "policies", pid + ".check.json"), encoding="utf-8"))
        got = pol(np.array(chk["obs"], float))
        want = np.array(chk["act"], float).ravel()
        d = float(np.max(np.abs(got - want)))
        rows.append(_row("L4", pid, f"Policy runtime reproduces its stored check vectors ({pid})", 0.0, d,
                         float(chk.get("tolerance", 1e-9)), "h", f"{len(want)} vectors in data/policies/{pid}.check.json; "
                         "the browser's parity against the same file is FRONTEND's test (site/src/atc/bid.js)",
                         "comparison to other models", "code verification", "V", "P1", ["P1"], mode="abs",
                         source="lunarsim.atc.learned.Policy", t0=t0,
                         tol_src=f"the check file's own tolerance ({chk.get('tolerance')})"))
    t0 = time.time()
    sys.path.insert(0, _repo("tools", "atc"))
    try:
        import train_bid as TB
    finally:
        sys.path.pop(0)
    train = set(TB.TRAIN_SEEDS) | set(TB.TUNE_SEEDS) | set(TB.CEM_FIT_SEEDS) | set(TB.CEM_TUNE_SEEDS)
    inter = sorted(train & set(TB.EVAL_SEEDS))
    rows.append(_row("L1", "seed sets disjoint", "Held-out evaluation seeds are disjoint from training and tuning seeds",
                     0.0, float(len(inter)), 0.0, "seeds", f"training {min(TB.TRAIN_SEEDS)}-{max(TB.TRAIN_SEEDS)}, tuning "
                     f"{min(TB.TUNE_SEEDS)}-{max(TB.TUNE_SEEDS)}, CEM {list(TB.CEM_FIT_SEEDS)} / {list(TB.CEM_TUNE_SEEDS)}; "
                     f"evaluation {min(TB.EVAL_SEEDS)}-{max(TB.EVAL_SEEDS)} (tools/atc/train_bid.py); shared: "
                     f"{inter or 'none'}", "internal validity", "input pedigree", "V", "P1", ["P1"], mode="abs",
                     source="Ross, Gordon and Bagnell 2011 (DAgger)", t0=t0))
    ev = json.load(open(_repo("results", "ATC_learned_eval.json"), encoding="utf-8"))["eval"]["30"]
    r = _row("L1", "teacher agreement", "Agreement with the teacher (O_ORACLE) on held-out rounds", float("nan"),
             float(ev["mlp"]["heldout_agreement"]), 0.0, "share",
             f"held-out top-1 agreement (results/ATC_learned_eval.json, 30 % load): hand bids "
             f"{ev['hand']['heldout_agreement']} ({ev['hand']['heldout_groups']:,} rounds), MLP "
             f"{ev['mlp']['heldout_agreement']}, linear {ev['linear']['heldout_agreement']}",
             "comparison to other models", "referent validation", "Val", "P1", ["P1"], mode="abs",
             source="Ross et al. 2011; Wilson 1927")
    r["skipped"] = ("no preregistered agreement threshold (PREREG H4 tests outcomes, not agreement); the numbers are "
                    "reported in basis")
    rows.append(r)
    r = _row("L2", "not applicable", "Outcome equivalence with the teacher (TOST)", float("nan"), float("nan"), 0.0, "",
             "the policy is not a distilled copy of the teacher: after imitation it is tuned by CEM to beat it, and its "
             "outcome against C_AUCTION is H4 itself (E40)", "internal validity", "referent validation", "Val", "P1",
             ["P1"], mode="abs", source="PREREG H4")
    r["skipped"] = "not applicable: the learned policy is tuned to differ from its teacher; H4 tests the outcome"
    rows.append(r)
    t0 = time.time()
    import tempfile
    doc = json.load(open(_repo("data", "policies", "atc_bid_v1.json"), encoding="utf-8"))
    last = doc["layers"][-1]
    last["w"] = np.zeros_like(np.array(last["w"], float)).tolist()
    last["b"] = np.zeros_like(np.array(last["b"], float)).tolist()
    with tempfile.TemporaryDirectory() as td:
        pth = os.path.join(td, "zero.json")
        with open(pth, "w", encoding="utf-8") as f:
            json.dump(doc, f)
        d = {}
        for reg, kw in (("C_AUCTION", {"loss": 0.10}), ("C_LEARNED_MLP", {"loss": 0.10, "policy": pth})):
            sim = _p5_sim(reg, kw, seed=7)
            _run_quiet(sim)
            d[reg] = _items_digest(sim)
    rows.append(_row("L6", "zero correction", "A learned policy with zero correction reproduces the hand-bid auction",
                     1.0, float(d["C_AUCTION"] == d["C_LEARNED_MLP"]), 0.0, "match", f"atc_bid_v1 with its output layer "
                     f"zeroed (g = 0) in C_LEARNED_MLP vs C_AUCTION, loss 0.10, seed 7, 90 days: "
                     f"{d['C_AUCTION'][:12]} vs {d['C_LEARNED_MLP'][:12]}", "degenerate tests", "code verification", "V",
                     "P1", ["P1"], mode="abs", source="design identity (lunarsim/atc/learned.py)", t0=t0))
    return rows


def run_phase5_batch2() -> List[Dict]:
    rows: List[Dict] = []
    for f in (check_a2_degenerate, check_a6_metamorphic, check_a7_no_double, check_d8_ids, check_a9_team_lifts,
              check_a_not_applicable, check_r2_reciprocity, check_r7_graph, check_r9_messages,
              check_x6_earth_independent, check_l_policy):
        rows += f()
    return rows


# ================================================================================================ batch 3 (B-79)
# P3's payment and timing checks (LEAD's list for P3 Section 3.6)

def _tool(name):
    for p in (_repo("tools", "atc"), _repo(), _repo("experiments", "phase5")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import importlib
    return importlib.import_module(name)


def _e46_runs():
    import glob
    import gzip
    M = _tool("run_e46")
    runs = {}
    for f in sorted(glob.glob(os.path.join(M.PARTS, "*.json.gz"))):
        tag = os.path.basename(f).split("_", 2)[2].replace(".json.gz", "")
        if tag in ("pooled", "alone", "pair_AB", "pair_AC", "pair_BC") or tag.startswith("dev_"):
            r = json.load(gzip.open(f, "rt"))
            runs[(r["split"], r["seed"], tag)] = r
    design = json.load(open(M.DESIGN, encoding="utf-8"))
    return M, runs, design


def check_a8_payments() -> List[Dict]:
    """A8 for P3: (c) Shapley payoffs sum to the grand coalition's value on every seed; (d) asks scaled by k = 1.0
    reproduce the honest payments exactly; (e) the audit charges nothing at q = 0 and m x |misreport| on every job
    at q = 1. All on the stored E46 runs with run_e46's own payment code."""
    t0 = time.time()
    M, runs, design = _e46_runs()
    T = design["posted_price"]["values_usd_per_tkm"]
    m = float(design["audit_penalty_multiple"]["value"])
    rows = []
    worst, n = 0.0, 0
    for (split, seed, tag), base in runs.items():
        if tag != "pooled" or (split, seed, "alone") not in runs:
            continue
        v = {frozenset(): 0.0}
        for o in M.OWNERS:
            v[frozenset([o])] = M.owner_value(runs[(split, seed, "alone")], o)
        for pr in itertools.combinations(M.OWNERS, 2):
            v[frozenset(pr)] = M.coalition_value(runs[(split, seed, "pair_" + "".join(pr))], pr)
        v[frozenset(M.OWNERS)] = M.coalition_value(base, M.OWNERS)
        phi = M.shapley(v, M.OWNERS)
        worst = max(worst, abs(sum(phi.values()) - v[frozenset(M.OWNERS)]) / abs(v[frozenset(M.OWNERS)]))
        n += 1
    rows.append(_row("A8", "(c) Shapley efficiency", "The Shapley payoffs sum to the grand coalition's value on every seed", 0.0,
                     worst, 1e-9, "rel", f"{n} seed-splits of E46 (30 seeds x 3eq, 3uneq); coalition values from the "
                     "stored runs (alone: A_MOON; pairs; grand: the pooled market); largest relative gap",
                     "analytic", "code verification", "V", "P2", ["P3"], mode="abs",
                     source="Shapley 1953 (efficiency); tools/atc/run_e46.py", t0=t0))
    t0 = time.time()
    worst, n = 0.0, 0
    for (split, seed, tag), base in runs.items():
        if tag != "pooled":
            continue
        for rule in ("first", "second", "posted", "none"):
            ref = M.money(base, rule, T[split])
            for o in M.OWNERS:
                got = M.money(base, rule, T[split], dev_owner=o, k=1.0)
                for key in ("profit", "cash", "fines"):
                    for oo in M.OWNERS:
                        worst = max(worst, abs(got[key][oo] - ref[key][oo]))
                worst = max(worst, abs(got["budget"] - ref["budget"]))
                n += 1
    rows.append(_row("A8", "(d) k = 1, payments", "Asks scaled by k = 1.0 reproduce the honest payments exactly", 0.0,
                     worst, 1e-9, "USD", f"{n} cases (60 pooled runs x 4 rules x 3 owners): largest |difference| over "
                     "every owner's profit, cash flow, fine and the operator's budget", "degenerate tests",
                     "code verification", "V", "P1", ["P3"], mode="abs", source="tools/atc/run_e46.py money()", t0=t0,
                     tol_src="1e-9 USD absolute (the same arithmetic on the same floats)"))
    t0 = time.time()
    a = M.run_one("3eq", 1, "pooled")
    b = M.run_one("3eq", 1, "dev", "A", 1.0)
    same = json.dumps(a["jobs"]) == json.dumps(b["jobs"]) and a["owners"] == b["owners"]
    rows.append(_row("A8", "(d) k = 1, physical run", "Asks scaled by k = 1.0 reproduce the honest payments exactly: the physical run with a deviating owner at k = 1.0 equals the honest run", 1.0,
                     float(same), 0.0, "match", f"E46 3eq seed 1: owner A's asks x 1.0 against the pooled run; every job "
                     f"(time, carriers, cost, items, alternatives) and every owner's delay and deliveries; "
                     f"{len(a['jobs'])} jobs", "degenerate tests", "code verification", "V", "P1", ["P3"], mode="abs",
                     source="lunarsim/atc/auction.py bid_mult hook", t0=t0))
    t0 = time.time()
    f0 = f1 = 0.0
    n = 0
    for (split, seed, tag), r in runs.items():
        if not tag.startswith("dev_"):
            continue
        _, o, k = tag.split("_")
        k = float(k)
        for rule in ("first", "second"):
            z = M.money(r, rule, T[split], dev_owner=o, k=k, q=0.0, m=m)
            f0 = max(f0, max(abs(x) for x in z["fines"].values()))
            one = M.money(r, rule, T[split], dev_owner=o, k=k, q=1.0, m=m)
            mis = {oo: 0.0 for oo in M.OWNERS}
            for j in r["jobs"]:
                share = j["cost"] / len(j["carriers"])
                for c in j["carriers"]:
                    ask = share * r["eps"][c] * (k if c == o else 1.0)
                    mis[c] += abs(ask - share * r["eps"][c])
            f1 = max(f1, max(abs(one["fines"][oo] - m * mis[oo]) / max(1.0, m * mis[oo]) for oo in M.OWNERS))
            n += 1
    rows.append(_row("A8", "(e) audit q = 0", "The audit at q = 0 charges nothing and at q = 1 charges m times every misreport: q = 0", 0.0, f0, 0.0, "USD",
                     f"{n} deviation runs x rules (first, second): largest fine at q = 0", "degenerate tests",
                     "code verification", "V", "P1", ["P3"], mode="abs", source="tools/atc/run_e46.py money()", t0=t0))
    rows.append(_row("A8", "(e) audit q = 1", "The audit at q = 0 charges nothing and at q = 1 charges m times every misreport: q = 1", 0.0, f1, 1e-9, "rel",
                     f"{n} deviation runs x rules: each owner's fine against m = {m:g} times the sum over its jobs of "
                     "|ask - true cost|, recomputed from the job log; largest relative gap", "analytic",
                     "code verification", "V", "P1", ["P3"], mode="abs", source="tools/atc/run_e46.py money()", t0=t0))
    return rows


def check_x7_timing() -> List[Dict]:
    """X7 (added, for P3): E48's round timer (a wrapper that reads perf_counter around each dispatch call, as in
    tools/atc/run_e48.py) leaves the run bit-identical: every pushed event (time, kind) and every item record."""
    from .engine import Simulation
    from .atc import regimes as G
    t0 = time.time()
    E = _tool("run_e48")
    sc = E._scen(1, 60)
    out = []
    for timed in (False, True):
        mech = G.mechanism("C_AUCTION")
        call = mech
        if timed:
            rounds = []

            def call(sim, cand, free, _m=mech, **kw):
                t1 = time.perf_counter()
                r = _m(sim, cand, free, **kw)
                rounds.append(time.perf_counter() - t1)
                return r
            for a in ("anticipates", "supports_team", "regime", "__name__"):
                if hasattr(mech, a):
                    setattr(call, a, getattr(mech, a))
        sim = Simulation(sc, call, seed=1, mech_kwargs={"start_year": 2028, "loss": 0.10})
        ev = []
        real = sim._push

        def push(t, kind, payload, _rp=real, _ev=ev):
            _ev.append((float(t), kind))
            return _rp(t, kind, payload)
        sim._push = push
        _run_quiet(sim)
        out.append((hashlib.md5(json.dumps(ev).encode()).hexdigest(), _items_digest(sim), len(ev)))
    return [_row("X7", "(f) E48 timer", "The E48 timers leave a run's event trace bit-identical to a run with timing off", 1.0,
                 float(out[0][:2] == out[1][:2]), 0.0, "match", f"C_AUCTION + road layer (E48's 1x scenario), 60 days, "
                 f"seed 1, loss 0.10: {out[0][2]:,} events; md5 of the event list {out[0][0][:12]} vs {out[1][0][:12]}, "
                 f"of the item records {out[0][1][:12]} vs {out[1][1][:12]}", "degenerate tests", "code verification",
                 "V", "P1", ["P3"], mode="abs", source="tools/atc/run_e48.py", t0=t0)]


def check_a8_market_identities() -> List[Dict]:
    """A8 for P3: (a) with every bid multiplier at 1 the market run reproduces the pooled auction; (b) the one-owner
    market's money flows."""
    from .engine import Simulation
    from .atc import regimes as G
    M = _tool("run_e46")
    rows = []
    t0 = time.time()
    same, n = 0, 0
    for split, seed in (("3eq", 1), ("3eq", 2), ("3uneq", 1)):
        d = []
        for mult in (None, {o: 1.0 for o in M.OWNERS}):
            kw = {"loss": 0.0, "start_year": 2028}
            if mult is not None:
                kw["bid_mult"] = mult
            sim = Simulation(M.scenario(split), G.mechanism("C_AUCTION"), seed=seed, mech_kwargs=kw)
            _run_quiet(sim)
            d.append(_items_digest(sim))
        same += d[0] == d[1]
        n += 1
    rows.append(_row("A8", "(a) multiplier 1", "With every bid multiplier at 1, the market run reproduces the pooled "
                     "auction exactly", float(n), float(same), 0.0, "runs identical", f"E46's scenario (p5, 30 % load, "
                     "fixpoint), C_AUCTION, loss 0, with bid_mult {A: 1, B: 1, C: 1} against no hook; 3eq seeds 1-2 and "
                     "3uneq seed 1, a year each; md5 of every item record (the hook is outcome-neutral when off)",
                     "degenerate tests", "code verification", "V", "P1", ["P3"], mode="abs",
                     source="lunarsim/atc/auction.py bid_mult hook", t0=t0))
    t0 = time.time()
    real = M.scenario

    def one_owner(split, members=None, _r=real):
        sc = _r(split, members)
        return sc.with_(fleet=[("A",) + tuple(f[1:]) for f in sc.fleet], cargo_owners=["A"] * len(sc.cargo_owners),
                        bulk_flows=[__import__("dataclasses").replace(b, owner="A") for b in sc.bulk_flows])
    M.scenario = one_owner
    try:
        run = M.run_one("3eq", 1, "pooled")
    finally:
        M.scenario = real
    T = json.load(open(M.DESIGN, encoding="utf-8"))["posted_price"]["values_usd_per_tkm"]["3eq"]
    viol = 0
    lines = []
    for rule in ("none", "first", "second", "posted"):
        x = M.money(run, rule, T)
        others = abs(x["cash"]["B"]) + abs(x["cash"]["C"])
        earth = abs(x["cash"]["A"] + x["budget"])
        ident = abs(x["budget"] - (x["receipts"] - x["payouts"] + x["fines_total"]))
        zero = abs(x["budget"]) if rule in ("none", "posted") else 0.0
        viol += (others > 1e-6) + (earth > 1e-6) + (ident > 1e-6) + (zero > 1e-6)
        lines.append(f"{rule}: budget {x['budget'] / 1e6:+.3f} M (receipts {x['receipts'] / 1e6:.3f} - payouts "
                     f"{x['payouts'] / 1e6:.3f})")
    rows.append(_row("A8", "(b) one owner", "With one owner there are no payments between owners under any rule; the "
                     "operator's budget is zero under no payments and the posted price, and under first and second price "
                     "it equals the tariff receipts less the payouts, all of it between that owner and Earth", 0.0,
                     float(viol), 0.0, "violations", f"E46 3eq seed 1 with every vehicle and every item owned by A "
                     f"({len(run['jobs'])} jobs); per rule: the other owners' cash 0, A's cash = - budget, budget = "
                     f"receipts - payouts + fines, budget 0 under none and posted. " + "; ".join(lines),
                     "degenerate tests", "code verification", "V", "P1", ["P3"], mode="abs",
                     source="tools/atc/run_e46.py money()", t0=t0, tol_src="1e-6 USD absolute on each identity"))
    return rows


def check_a8_no_double_assignment() -> List[Dict]:
    """(g) for P3: across base-computer failures and recoveries (C_LEADER, E48's failover settings) and across mesh
    partitions (C_AUCTION, terrain radio), no cargo item is ever assigned to two jobs."""
    t0 = time.time()
    E = _tool("run_e48")
    fo = E.DESIGN_DOC["failover"]
    dup = jobs = merges = runs = 0
    out_share = []
    cells = [("C_LEADER", {"loss": 0.10, "base_mtbf_h": 500.0, "base_repair_h": fo["repair_h"],
                           "reelect_h": fo["reelect_h"]}, s) for s in (1, 2)]
    cells += [("C_AUCTION", {"loss": 0.10}, s) for s in (1, 2)] + [("C_AUCTION", {"loss": 0.40}, 3)]
    for reg, kw, seed in cells:
        sim = _p5_sim(reg, kw, seed=seed, days=365)
        log = _job_log(sim)
        out = _run_quiet(sim)
        objs = [i for j in log for i in j["objs"]]
        dup += len(objs) - len(set(objs))
        jobs += len(log)
        runs += 1
        if reg == "C_LEADER":
            merges += len(sim.atc.base_down)
        else:
            out_share.append(float(out.get("atc_robots_out_share", 0.0) or 0.0))
    return [_row("A8", "(g) no job twice", "Across base-computer failures and recoveries and across mesh partitions, no "
                 "cargo item is ever assigned to two jobs (the ledger itself is sized, not simulated)", 0.0, float(dup),
                 0.0, "items", f"{runs} one-year runs: C_LEADER at base MTBF 500 h, repair {fo['repair_h']:g} h, "
                 f"re-election {fo['reelect_h']:g} h, loss 0.10, seeds 1-2 ({merges} base failures and recoveries); "
                 f"C_AUCTION with terrain radio at loss 0.10 (seeds 1-2) and 0.40 (seed 3), mean share of robots outside "
                 f"the mast's component {np.mean(out_share):.3f}; {jobs:,} jobs, items keyed by object", "event validity",
                 "code verification", "V", "P1", ["P3"], mode="abs", source="tools/atc/run_e48.py (failover)",
                 exposure={"n": jobs, "unit": "jobs", "upper95": 1 - 0.05 ** (1 / max(jobs, 1))}, t0=t0)]


def run_phase5_batch3() -> List[Dict]:
    rows: List[Dict] = []
    for f in (check_a8_market_identities, check_a8_payments, check_a8_no_double_assignment, check_x7_timing):
        rows += f()
    return rows


# ================================================================================================ batch 3 part 2 (B-79)
# safety layer (S), traffic (T), replay (V)

def _e44_types():
    return json.load(open(_repo("results", "E44_bounds.json"), encoding="utf-8"))["types"]


def check_s1_separation() -> List[Dict]:
    """S1: (a) the encounter simulator's closest approach between 10 Hz steps (encounter._closest, two points moving
    linearly) against an independent bounded minimisation; (b) zero contacts and separation violations in E44's
    nominal encounter types, with the exposure and the 95 % bound; (c) type 9 (non-conforming vehicles) reported."""
    from scipy.optimize import minimize_scalar
    from .atc.encounter import _closest
    rows = []
    t0 = time.time()
    rng = np.random.default_rng(1)
    n = 20000
    p0, p1, q0, q1 = (rng.uniform(-20, 20, (n, 2)) for _ in range(4))
    got = _closest(p0, p1, q0, q1)
    worst = 0.0
    for k in range(0, n, 10):                       # 2,000 independent minimisations
        f = lambda t: float(np.hypot(*((p0[k] + (p1[k] - p0[k]) * t) - (q0[k] + (q1[k] - q0[k]) * t))))
        r = minimize_scalar(f, bounds=(0.0, 1.0), method="bounded", options={"xatol": 1e-12})
        ref = min(r.fun, f(0.0), f(1.0))
        worst = max(worst, abs(got[k] - ref))
    rows.append(_row("S1", "(a) closest approach", "Closest approach between 10 Hz steps is exact (continuous time, "
                     "not sampled)", 0.0, worst, 1e-6, "m", "encounter._closest on 2,000 random pairs of linear moves "
                     "(+/- 20 m) against scipy's bounded minimisation (xatol 1e-12) with both end points; largest "
                     "|difference|", "comparison to other models", "code verification", "V", "P1", ["P2"], mode="abs",
                     source="closest-point-of-approach geometry; lunarsim/atc/encounter.py", t0=t0,
                     tol_src="1e-6 m (the minimiser's own tolerance, well below a disc radius)"))
    t0 = time.time()
    ty = _e44_types()
    nom = {k: v for k, v in ty.items() if k != "9"}
    viol = sum(int(v["violations"]) for v in nom.values())
    n_eff = sum(float(v["n_eff"]) for v in nom.values())
    rows.append(_row("S1", "(b) nominal types", "Zero separation violations in every nominal encounter type (E44)", 0.0,
                     float(viol), 0.0, "violations", f"E44 types {', '.join(sorted(nom, key=int))}: contacts, gap below "
                     f"the RSS minimum, zone, crew, R3 and slot violations, evaluated in continuous time between steps; "
                     f"{n_eff:,.0f} driven encounters (n_eff)", "traces", "code verification", "V", "P1", ["P2"],
                     mode="abs", source="results/E44_bounds.json; Hanley and Lippman-Hand 1983",
                     exposure={"n": n_eff, "unit": "driven encounters", "upper95": 1 - 0.05 ** (1 / n_eff)}, t0=t0))
    t9 = ty["9"]
    rows.append(_row("S1", "(c) type 9, non-conforming", "Zero separation violations with non-conforming vehicles "
                     "(type 9: slip, drift, dead stop)", 0.0, float(t9["violations"]), 0.0, "violations",
                     f"E44 type 9, {t9['n_eff']:,.0f} driven encounters: by kind {t9['violations_by_kind']}. A vehicle that "
                     "stops dead brakes harder than the leader braking R1 assumes (B_MAX), so R1's guarantee does not "
                     "cover it; the P2 paper reports this as a finding", "traces", "code verification", "V", "P1",
                     ["P2"], mode="abs", source="results/E44_bounds.json", exposure={"n": float(t9["n_eff"]),
                     "unit": "driven encounters", "upper95": None}, t0=t0))
    return rows


def _move(**kw):
    from .atc.safety import Move
    base = dict(v=np.array([1.0]), a_prop=np.array([0.0]), dt=0.1, theta=np.array([0.0]), mu=np.array([0.3]),
                v_class=np.array([2.8]), sight=np.array([1e6]), gap_lead=np.array([np.inf]), v_lead=np.array([0.0]),
                d_stop=np.array([np.inf]), d_crew=np.array([np.inf]))
    base.update(kw)
    return Move(**base)


def check_s2_injection(n: int = 1000) -> List[Dict]:
    """S2: unsafe proposals injected into safety_check, 1,000 per class; every one must be refused (a reservation
    verdict not ok, or a move replaced by a safe candidate)."""
    from .atc import safety as S
    rows = []
    rng = np.random.default_rng(2)
    t0 = time.time()
    caught = {}
    # R3: an overlapping reservation in the opposite direction (any overlap on a branched segment)
    c = 0
    for _ in range(n):
        a = rng.uniform(0, 100)
        b = a + rng.uniform(0.01, 2)
        branched = bool(rng.random() < 0.5)
        d0 = int(rng.choice([-1, 1]))
        d1 = d0 if branched else -d0
        dur = rng.uniform(0.01, 2)
        ti = rng.uniform(a - dur + 1e-6, b - 1e-6)           # the request overlaps the holder's window
        table = {"seg": [(a, b, d0, "B", 1)]}
        v = S.safety_check(table, S.Reserve("seg", ti, ti + dur, 2, "A", d=d1, branched=branched))
        c += not v.ok
    caught["R3 reservation conflict"] = c
    # R10: a slot request while every slot is held
    c = 0
    for _ in range(n):
        slots = int(rng.integers(1, 4))
        entries = [(0.0, 10.0, 0, "B", 10 + i) for i in range(slots)]
        ti = rng.uniform(0, 9.9)
        v = S.safety_check({"pad": entries}, S.Reserve("pad", ti, ti + rng.uniform(0.01, 5), 1, "A", kind="slots",
                                                       slots=slots))
        c += not v.ok
    caught["R10 slots full"] = c
    # R1: closer than the RSS minimum to the leader, proposing to accelerate
    c = 0
    for _ in range(n):
        vr, vl = rng.uniform(0.5, 2.8), rng.uniform(0.0, 2.8)
        b = float(S.b_guaranteed(0.0, 0.3))
        gap = rng.uniform(0.05, 0.9) * float(S.rss_dmin(vr, vl, b))
        m = _move(v=np.array([vr]), a_prop=np.array([rng.uniform(0.01, 0.2)]), gap_lead=np.array([gap]),
                  v_lead=np.array([vl]))
        r = S.safety_check(None, m)
        c += bool(r.modified[0]) and r.a[0] < 0
    caught["R1 inside the RSS gap"] = c
    # R2: at or above the admissible speed, proposing to accelerate (slopes friction can hold: b > 0)
    th_hold = math.degrees(math.atan(0.3)) - 0.5
    c = 0
    for _ in range(n):
        th = rng.uniform(0, th_hold)
        vmax = float(S.v_max_r2(th, 0.3, 1e6, 2.8))
        m = _move(v=np.array([vmax + rng.uniform(0.0, 0.5)]), a_prop=np.array([rng.uniform(0.01, 0.2)]),
                  theta=np.array([th]))
        r = S.safety_check(None, m)
        c += bool(r.modified[0]) and r.a[0] <= 0
    caught["R2 over the speed limit"] = c
    # beyond the invariant: on slopes friction cannot hold (b < 0, v_max = 0) no action is safe; the shield must say so
    c = 0
    for _ in range(n):
        th = rng.uniform(th_hold + 1.0, 25)
        m = _move(v=np.array([rng.uniform(0.0, 0.5)]), a_prop=np.array([rng.uniform(-0.2, 0.2)]), theta=np.array([th]))
        r = S.safety_check(None, m)
        c += bool(r.no_safe_action[0])
    caught["unholdable slope flagged"] = c
    # stop line (R3 / R5 / R10 entry without a confirmed reservation): too close to stop if it accelerates
    c = 0
    for _ in range(n):
        v0 = rng.uniform(0.5, 2.8)
        b = float(S.b_guaranteed(0.0, 0.3))
        d = float(S.stop_distance(v0, b)) + rng.uniform(0.0, 0.05)
        m = _move(v=np.array([v0]), a_prop=np.array([rng.uniform(0.05, 0.2)]), d_stop=np.array([d]))
        r = S.safety_check(None, m)
        c += bool(r.modified[0])
    caught["stop line"] = c
    # R6: inside the crew keep-out distance while moving, proposing to accelerate
    c = 0
    for _ in range(n):
        v0 = rng.uniform(0.5, 2.8)
        b = float(S.b_guaranteed(0.0, 0.3))
        d = rng.uniform(0.1, 0.95) * float(S.r_crew_stop(v0, b))
        m = _move(v=np.array([v0]), a_prop=np.array([rng.uniform(0.01, 0.2)]), d_crew=np.array([d]))
        r = S.safety_check(None, m)
        c += bool(r.modified[0]) and r.a[0] < 0
    caught["R6 crew keep-out"] = c
    # R5: inside a closing landing zone, proposing to slow down with the way out clear
    c = 0
    for _ in range(n):
        v0 = rng.uniform(0.3, 2.0)
        m = _move(v=np.array([v0]), a_prop=np.array([-rng.uniform(0.05, 0.3)]), must_exit=np.array([True]))
        r = S.safety_check(None, m)
        c += bool(r.modified[0]) and r.a[0] >= 0
    caught["R5 must exit"] = c
    for k, cnt in caught.items():
        rows.append(_row("S2", k, f"Injected unsafe proposals refused: {k}", float(n), float(cnt), 0.0, "refused",
                         f"{n} injections; a miss is an accepted unsafe proposal (miss-rate bound 3/N = {3 / n:.3f})"
                         + (". Beyond the invariant (R2 forbids these slopes): the shield's kinematics take a stopped "
                            "vehicle to stay stopped, so a near-standstill vehicle braking on a slope friction cannot "
                            "hold is accepted instead of flagged" if k == "unholdable slope flagged" else ""),
                         "fault injection (mutation testing)", "code verification", "V", "P1", ["P2"], mode="abs",
                         source="DeMillo, Lipton and Sayward 1978; lunarsim/atc/safety.py",
                         exposure={"n": n, "unit": "injections", "upper95": 1 - 0.05 ** (1 / n)}, t0=t0))
    return rows


def check_s3_minimal(n: int = 10000) -> List[Dict]:
    """S3: a proposal that is already safe passes unchanged (random free-road states, accelerations that keep the
    speed within its limit); the intervention rate in the encounters is reported from E44."""
    from .atc import safety as S
    t0 = time.time()
    rng = np.random.default_rng(3)
    th = rng.uniform(0, 8, n)
    vmax = S.v_max_r2(th, 0.3, 1e6, 2.8)
    v = rng.uniform(0, 1, n) * vmax * 0.8
    b = S.b_guaranteed(th, 0.3)
    lo = np.maximum(-b * 0.9, -v / 0.1)
    hi = np.minimum(0.2, (vmax - v) / 0.1)
    a = lo + (hi - lo) * rng.random(n)
    m = _move(v=v, a_prop=a, theta=th, mu=np.full(n, 0.3), v_class=np.full(n, 2.8), sight=np.full(n, 1e6),
              gap_lead=np.full(n, np.inf), v_lead=np.zeros(n), d_stop=np.full(n, np.inf), d_crew=np.full(n, np.inf))
    r = S.safety_check(None, m)
    changed = int(np.sum(r.modified))
    ty = _e44_types()
    rates = ", ".join(f"T{k} {v['intervention_rate']:.3f}" for k, v in sorted(ty.items(), key=lambda x: int(x[0])))
    return [_row("S3", "safe passes unchanged", "A proposal that is already safe passes unchanged", 0.0, float(changed),
                 0.0, "modified", f"{n:,} free-road states (slope 0-8 deg, speed below 80 % of its limit, acceleration "
                 f"keeping it below the limit, no leader, line or crew); intervention rate per E44 type (share of "
                 f"proposals the shield changed): {rates}", "analytic", "code verification", "V", "P1", ["P2"],
                 mode="abs", source="Alshiekh et al. 2018 (shielding); Ames et al. 2019", t0=t0)]


def _road_harness(branched=True):
    """The engine's RoadLayer.apply on one single-lane resource 'X->Y' (direction +1) / 'Y->X' (-1), driven without a
    simulation: a vehicle's job is one traversal, committed in call order (as jobs commit in the engine)."""
    from .atc.roads import RoadLayer, DEFAULTS as RD

    class _Sim:
        def __init__(self):
            self._last_segments = {}
            self.vehicles = []

    class _V:
        def __init__(self, i):
            self.id, self.owner = i, "A"

    class _Job:
        def __init__(self, v):
            self.vehicles = [v]
    rl = object.__new__(RoadLayer)
    rl.cfg = dict(RD, eva=dict(RD["eva"], per_week=0))
    rl.table, rl.wait_by_owner, rl.pads, rl.eva = {}, {}, set(), []
    rl.standoff = "1"
    rl.branched = {0: bool(branched)}
    rl.legs = {"X->Y": [(0, 0.0, 1.0, 1)], "Y->X": [(0, 0.0, 1.0, -1)]}
    rl.m = {"wait_h": 0.0, "apron_wait_h": 0.0, "eva_slow_h": 0.0, "conflicts": 0, "hand_conflicts": 0,
            "hand_wait_h": 0.0, "other_stop_h": 0.0, "r7_fallbacks": 0, "jobs": 0, "traversals": 0, "deadlocks": 0}
    sim = _Sim()

    def traverse(vid, t, tau, d=1, prune=True):
        if prune:                                     # entries that ended can never conflict again
            rl.table[0] = [e for e in rl.table.get(0, []) if e[1] > t]
        a, b = ("X", "Y") if d > 0 else ("Y", "X")
        sim._last_segments[vid] = [[a, b, t, t + tau, 1.0]]
        return rl.apply(sim, _Job(_V(vid)), t)
    return traverse, rl


def check_t1_single_lane() -> List[Dict]:
    """T1: one single-lane segment, single occupancy, Poisson arrivals, deterministic traversal tau: the engine's
    reservation commit (RoadLayer.apply) equals the Lindley recursion on the same arrivals (exact), and its mean wait
    matches M/D/1 at rho 0.3, 0.6, 0.85 (sized by the plan's rule)."""
    rows = []
    tau = 0.1
    for rho, tol in ((0.3, 0.03), (0.6, 0.05), (0.85, 0.10)):
        t0 = time.time()
        lam = rho / tau
        rng = np.random.default_rng(int(rho * 100))
        traverse, rl = _road_harness()
        ref = lam * tau * tau / (2 * (1 - rho))
        m_ = 2000
        waits = []
        t = 0.0
        while True:
            arr = t + np.cumsum(rng.exponential(1 / lam, 20 * m_))
            for i, a in enumerate(arr):
                waits.append(traverse(len(waits), float(a), tau))
            t = float(arr[-1])
            w = np.array(waits)
            mean, ci = _batch_means(w)
            if (ci[1] - ci[0]) / 2 <= tol / 3 * ref or len(w) >= 2_000_000:
                break
            m_ = len(w) // 20
        # sample path: Lindley on the same arrivals
        rng2 = np.random.default_rng(int(rho * 100))
        arr_all = []
        tt, mm = 0.0, 2000
        while len(arr_all) < len(w):
            a2 = tt + np.cumsum(rng2.exponential(1 / lam, 20 * mm))
            arr_all.extend(a2.tolist())
            tt = float(a2[-1])
            mm = len(arr_all) // 20
        lind = queue_fcfs(np.array(arr_all[:len(w)]), np.full(len(w), tau), 1)
        d = float(np.max(np.abs(lind - w)))
        rows.append(_row("T1", f"rho {rho}: sample path", f"Single-lane segment = Lindley recursion, rho {rho}", 0.0, d,
                         1e-9, "h", f"{len(w):,} traversals through RoadLayer.apply (R3 via safety_check, branched "
                         "segment: single occupancy) against the Lindley recursion on the same arrival times",
                         "comparison to other models", "code verification", "V", "P1", ["P2"], mode="abs",
                         source="Lindley 1952", t0=t0, tol_src="exact up to float addition"))
        rows.append(_row("T1", f"rho {rho}: W_q", f"Single-lane segment mean wait, rho {rho} (M/D/1: lambda tau^2 / "
                         "(2 (1 - rho)))", ref, mean, tol, "h", f"tau {tau} h, lambda {lam:g}/h, {len(w):,} traversals "
                         "in 20 batches", "analytic", "code verification", "V", "P1", ["P2"], source="Kleinrock 1975",
                         ci=ci, t0=t0))
    return rows


def check_t2_deterministic() -> List[Dict]:
    """T2: (a) n vehicles at once on a single-lane segment: waits 0, tau, ..., mean (n - 1) tau / 2; (b) strictly
    alternating directions, saturated: throughput 1 / tau (the model has no clearance time between directions);
    (c) same direction on an unbranched segment: following is allowed, so nobody waits (spacing is R1's job)."""
    rows = []
    tau = 0.25
    t0 = time.time()
    worst = 0.0
    for n in (2, 5, 10, 50):
        traverse, _ = _road_harness()
        w = [traverse(i, 0.0, tau, prune=False) for i in range(n)]
        worst = max(worst, abs(np.mean(w) - (n - 1) * tau / 2) / ((n - 1) * tau / 2))
    rows.append(_row("T2", "(a) n at once", "n vehicles at once: mean wait (n - 1) tau / 2", 0.0, worst, 1e-9, "rel",
                     "n = 2, 5, 10, 50 at t = 0, tau 0.25 h, single occupancy; largest relative error", "analytic",
                     "code verification", "V", "P1", ["P2"], mode="abs", source="elementary queueing", t0=t0))
    t0 = time.time()
    traverse, _ = _road_harness(branched=True)
    n = 200
    ends = []
    for i in range(n):                                # arrivals in sequence (1e-6 h apart): strict alternation
        t_a = i * 1e-6
        w = traverse(i, t_a, tau, d=1 if i % 2 == 0 else -1, prune=False)
        ends.append(t_a + w + tau)
    thr = n / max(ends)
    rows.append(_row("T2", "(b) alternating", "Strictly alternating directions, saturated, single occupancy: "
                     "throughput 1 / tau", 1 / tau,
                     thr, 1e-9, "per h", f"{n} vehicles arriving in sequence (1e-6 h apart) with alternating directions on a "
                     "single-occupancy (branched) segment; the model has no clearance time s between directions (s = 0). "
                     "On an unbranched segment alternation is not strict: R3 lets a later vehicle join an earlier "
                     "same-direction window (a platoon; T2 (c)), so directions batch and throughput exceeds 1 / tau", "analytic", "code verification",
                     "V", "P1", ["P2"], source="elementary queueing", t0=t0))
    t0 = time.time()
    traverse, _ = _road_harness(branched=False)
    w = [traverse(i, 0.0, tau, d=1, prune=False) for i in range(50)]
    rows.append(_row("T2", "(c) same direction", "Same direction on an unbranched segment: no reservation wait "
                     "(following is allowed; spacing is R1's job)", 0.0, float(max(w)), 0.0, "h", "50 vehicles at t = 0, "
                     "same direction", "analytic", "code verification", "V", "P1", ["P2"], mode="abs",
                     source="lunarsim/atc/safety.py r3_pair_conflict", t0=t0))
    return rows


def _roads_sim(mode, seed=1, days=120, year=2028, plume=True):
    for p in (_repo(), _repo("experiments", "phase5")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import run_phase5 as RP

    def mut(sc):
        rd = {"mode": mode, "single_share": RP.SINGLE_SHARE, "bay_km": 1.0}
        sc = sc.with_(p5=dict(sc.p5, roads=rd, dispatch_fixpoint=True))
        return sc.with_(plume=dict(RP.E43_PLUME)) if plume else sc
    return _p5_sim("O_ORACLE", {"start_year": year}, seed=seed, days=days, mutate=mut)


def check_t5_s5_s6_s7_roads() -> List[Dict]:
    """On E43-style runs (road layer + landing closures, O_ORACLE): T5 the reservation table holds no conflicting
    overlap and no apron over its slots, and a lone vehicle gets no road delay; S5 every reservation wait points to an
    earlier booking (the wait-for graph is acyclic) and is finite; S6 the 'atc' mode is Earth-independent and never
    refers a conflict to Earth; S7 no vehicle is at a pad, or within the keep-out radius of it on a road leg, during a
    landing window."""
    from .atc.safety import r3_pair_conflict
    rows = []
    t0 = time.time()
    audit = {"overlap": 0, "apron": 0}
    s5 = {"edges": 0, "phantom": 0, "max_wait_h": {"atc": 0.0, "uncoordinated": 0.0}, "nonfinite": 0}
    s7 = {"pad": 0, "approach": 0, "visits": 0, "windows": 0}
    runs = 0
    for mode in ("atc", "uncoordinated"):
        for seed in (1, 2):
            sim = _roads_sim(mode, seed=seed)

            def hook(sim_):
                rl = sim_.roads
                orig = rl._conflicts

                def conf(res, t_in, t_out, d, v, mine_only, _o=orig, _rl=rl):
                    out = _o(res, t_in, t_out, d, v, mine_only)
                    have = set(_rl.table.get(res, ()))
                    for x in out:
                        s5["edges"] += 1
                        if x not in have or x[4] == v.id:  # a wait must be for another vehicle's existing booking
                            s5["phantom"] += 1
                    return out
                rl._conflicts = conf
                orig_apply = rl.apply

                def apply(sim__, job, t_start, _a=orig_apply, _mode=mode):
                    w = _a(sim__, job, t_start)
                    s5["max_wait_h"][_mode] = max(s5["max_wait_h"][_mode], w)
                    s5["nonfinite"] += not math.isfinite(w)
                    return w
                rl.apply = apply
            segs_log = []
            real_start = sim._start_job

            def start(job, _rs=real_start, _sim=sim):
                if getattr(_sim, "roads", None) is not None and not getattr(_sim, "_vv_hooked", False):
                    hook(_sim)
                    _sim._vv_hooked = True
                n0 = [v.jobs for v in job.vehicles]
                _rs(job)
                if [v.jobs for v in job.vehicles] != n0:
                    for v in job.vehicles:
                        segs_log.append(list(_sim._last_segments.get(v.id) or []))
            sim._start_job = start
            out = _run_quiet(sim)
            runs += 1
            rl = sim.roads
            for res, lst in rl.table.items():
                if isinstance(res, tuple) and res[0] == "apron":
                    ev = sorted([(a, 1) for a, b, *_ in lst] + [(b, -1) for a, b, *_ in lst])
                    occ = 0
                    for _, dlt in ev:
                        occ += dlt
                        audit["apron"] += occ > int(rl.cfg["apron_slots"])
                    continue
                br = rl.branched.get(res, False)
                srt = sorted(lst)
                for i in range(len(srt)):
                    for j in range(i + 1, len(srt)):
                        if srt[j][0] >= srt[i][1]:
                            break
                        if srt[i][4] != srt[j][4] and bool(r3_pair_conflict(srt[i][2], srt[j][2], br)):
                            audit["overlap"] += 1
            # S7: pad intervals and the approach / departure inside the keep-out radius
            pl = sim.plume
            R = float(pl.R)
            s7["windows"] += len(pl.windows)
            for segs in segs_log:
                for a, b, t_a, t_b, _ in segs:
                    if a == b and a in sim.world.pads and t_b > t_a:
                        s7["visits"] += 1
                        if pl.overlapping(a, t_a, t_b) is not None:
                            s7["pad"] += 1
                    elif a != b:
                        L = max(sim.world.distance_km(a, b), 1e-9)
                        f = min(1.0, R / L)
                        for site, lo, hi in ((b, t_b - f * (t_b - t_a), t_b), (a, t_a, t_a + f * (t_b - t_a))):
                            if site in sim.world.pads and hi > lo and pl.overlapping(site, lo, hi) is not None:
                                s7["approach"] += 1
    rows.append(_row("T5", "(b) reservation table", "No two conflicting reservations of a segment overlap, and no apron "
                     "holds more than its slots", 0.0, float(audit["overlap"] + audit["apron"]), 0.0, "violations",
                     f"{runs} runs (O_ORACLE + road layer, atc and uncoordinated, seeds 1-2, 120 days, landing "
                     f"closures): conflicting overlaps {audit['overlap']}, apron over slots {audit['apron']}", "traces",
                     "code verification", "V", "P1", ["P2"], mode="abs", source="lunarsim/atc/roads.py", t0=t0))
    rows.append(_row("S5", "road layer wait-for", "Every reservation wait is for another vehicle's existing booking "
                     "(bookings are committed in order, so the wait-for graph is acyclic) and ends", 0.0,
                     float(s5["phantom"] + s5["nonfinite"]), 0.0, "violations",
                     f"same {runs} runs: {s5['edges']:,} wait edges, {s5['phantom']} not for another vehicle's booking in "
                     f"the table, {s5['nonfinite']} unbounded waits; longest wait {s5['max_wait_h']['atc']:.2f} h in atc "
                     f"mode and {s5['max_wait_h']['uncoordinated']:.2f} h uncoordinated (hand-resolution waits for Earth "
                     "contact through blackouts; T_max is not stated in the plan, so the maxima are reported). Deadlocks "
                     "in the encounter layer are a separate row",
                     "traces", "code verification", "V", "P1", ["P2"], mode="abs",
                     source="Coffman, Elphick and Shoshani 1971", t0=t0))
    rows.append(_row("S7", "landing keep-out", "No vehicle at a pad, or within the keep-out radius of it on a road leg, "
                     "during a landing window", 0.0, float(s7["pad"] + s7["approach"]), 0.0, "violations",
                     f"same {runs} runs, {s7['windows']} keep-out windows (R {R:g} km, +/- the stand-down): {s7['visits']:,} "
                     f"pad visits, {s7['pad']} inside a window; road legs inside the radius during a window: "
                     f"{s7['approach']} (a vehicle is taken to be within R on the last / first R km of a leg into / out "
                     "of the pad, at the leg's mean speed)", "traces", "code verification", "V", "P1", ["P2", "P3"],
                     mode="abs", source="v3 engine tests; lunarsim/phase3.py PlumeModel", t0=t0))
    t0 = time.time()
    one = lambda sc: sc.with_(fleet=[next(f for f in sc.fleet if f[1] == "CARGO_FLEX")])
    for p in (_repo(), _repo("experiments", "phase5")):
        if p not in sys.path:
            sys.path.insert(0, p)
    import run_phase5 as RP

    def mut1(sc):
        sc = one(sc)
        return sc.with_(p5=dict(sc.p5, roads={"mode": "atc", "single_share": RP.SINGLE_SHARE, "bay_km": 1.0,
                                             "eva": {"per_week": 0}}, dispatch_fixpoint=True))
    sim = _p5_sim("O_ORACLE", {}, seed=1, days=120, mutate=mut1)
    out = _run_quiet(sim)
    delay = out.get("road_wait_h", 0) + out.get("road_apron_wait_h", 0) + out.get("road_hand_wait_h", 0)
    rows.append(_row("T5", "(a) free flow", "A lone vehicle gets no delay from the road layer", 0.0, float(delay), 0.0,
                     "h", f"one CARGO_FLEX, road layer atc (no crew walks), 120 days, {int(out.get('road_traversals', 0))} "
                     "single-lane traversals: segment, apron and hand waits summed", "degenerate tests",
                     "code verification", "V", "P1", ["P2"], mode="abs", source="lunarsim/atc/roads.py", t0=t0))
    r = _row("T5", "(c) node conservation", "Vehicles in = out + present at every node", float("nan"), float("nan"), 0.0,
             "", "the engine has no node occupancy: vehicles are on legs or at sites, and capacity at sites is the "
             "apron slot rule (row T5 (b))", "traces", "code verification", "V", "P1", ["P2"], mode="abs",
             source="lunarsim/atc/roads.py")
    r["skipped"] = "not applicable: no node occupancy in the engine; site capacity is the apron slot rule (T5 (b))"
    rows.append(r)
    t0 = time.time()
    d = {}
    for mode in ("atc", "uncoordinated"):
        for y in (2028, 2038):
            sim = _roads_sim(mode, seed=3, days=90, year=y)
            o = _run_quiet(sim)
            d[(mode, y)] = (_items_digest(sim), o.get("road_hand_conflicts", 0))
    rows.append(_row("S6", "atc Earth-independent", "Road mode 'atc' decides without Earth: same run in 2028 and 2038, "
                     "no conflict referred to Earth", 1.0, float(d[("atc", 2028)][0] == d[("atc", 2038)][0] and
                                                             d[("atc", 2028)][1] == 0 and d[("atc", 2038)][1] == 0),
                     0.0, "pass", f"seed 3, 90 days, landing closures on: md5 of item records {d[('atc', 2028)][0][:12]} "
                     f"vs {d[('atc', 2038)][0][:12]}, hand referrals {d[('atc', 2028)][1]:g} / {d[('atc', 2038)][1]:g}; "
                     f"control 'uncoordinated': {d[('uncoordinated', 2028)][0][:12]} vs "
                     f"{d[('uncoordinated', 2038)][0][:12]}, hand referrals {d[('uncoordinated', 2028)][1]:g} / "
                     f"{d[('uncoordinated', 2038)][1]:g}", "metamorphic testing", "code verification", "V", "P1", ["P2"],
                     mode="abs", source="design identity (lunarsim/atc/roads.py)", t0=t0))
    return rows


def check_s5_encounters() -> List[Dict]:
    """S5 in the encounter layer, from E44: zero deadlocks (cycles of vehicles waiting for one another)."""
    t0 = time.time()
    ty = _e44_types()
    dl = {k: int(v["outcomes"].get("deadlock", 0)) for k, v in ty.items()}
    n = sum(float(v["n_eff"]) for v in ty.values())
    return [_row("S5", "encounter deadlocks", "Zero deadlocks in the encounter layer (E44)", 0.0, float(sum(dl.values())),
                 0.0, "encounters", f"E44, {n:,.0f} driven encounters; deadlocks by type: "
                 + ", ".join(f"T{k} {x}" for k, x in sorted(dl.items(), key=lambda z: int(z[0])) if x)
                 + ". Type 5 is a ring of single-lane reservations (R3) and type 6 a junction at a zone line, the "
                 "genuine mechanisms PREREG change 9 records; the P2 paper reports them", "traces", "code verification",
                 "V", "P1", ["P2"], mode="abs", source="results/E44_bounds.json; PREREG change 9", t0=t0)]


def _trace_files():
    import gzip
    d = _repo("data", "atc", "trace_pair")
    idx = json.load(open(os.path.join(d, "index.json"), encoding="utf-8"))
    docs = {n: json.load(gzip.open(os.path.join(d, r["file"]), "rt")) for n, r in idx["runs"].items()}
    return d, idx, docs


def check_v_replay() -> List[Dict]:
    """V1: the ATC trace pair (data/atc/trace_pair, B-80) against a fresh engine run without export hooks; the index's
    sizes and hashes. V2: positions: a vehicle never jumps between legs, every edge starts and ends at its sites, and
    every piece of road on a single-lane segment lies inside that vehicle's own reservation."""
    from .engine import Simulation
    from .atc import regimes as G
    rows = []
    if not os.path.isfile(_repo("data", "atc", "trace_pair", "index.json")):
        for cid in ("V1", "V2"):
            r = _row(cid, "not yet possible", "ATC trace replay", float("nan"), float("nan"), 0.0, "", "no trace pair",
                     "traces", "code verification", "V", "P1", ["P1", "P2"], mode="abs", source="B-80")
            r["skipped"] = "no data/atc/trace_pair (run tools/atc/export_trace.py)"
            rows.append(r)
        return rows
    t0 = time.time()
    d, idx, docs = _trace_files()
    bad = 0
    for n, r in idx["runs"].items():
        p = os.path.join(d, r["file"])
        bad += os.path.getsize(p) != r["bytes"]
        bad += hashlib.sha256(open(p, "rb").read()).hexdigest() != r["sha256"]
    rows.append(_row("V1", "index", "The trace index's sizes and hashes match its files", 0.0, float(bad), 0.0,
                     "mismatches", f"{len(idx['runs'])} files in data/atc/trace_pair, commit {str(idx.get('commit'))[:10]}",
                     "traces", "code verification", "V", "P1", ["P1", "P2"], mode="abs", source="tools/atc/export_trace.py",
                     t0=t0))
    E = _tool("export_trace")
    t0w, t1w = idx["window"]["t0_h"], idx["window"]["t1_h"]
    _t = E._t
    for name, tr in docs.items():
        t0 = time.time()
        spec = E.RUNS[name]
        sim = Simulation(E._scenario(name, t1w), G.mechanism(spec["regime"]), seed=int(idx["seed"]),
                         mech_kwargs=dict(spec["kw"], start_year=E.YEAR))
        _run_quiet(sim)
        items = [[c.id, c.owner, round(c.mass_kg, 1), c.cls, c.priority, c.origin, c.dest, _t(c.t_ready),
                  _t(c.t_picked), _t(c.t_delivered), c.carrier, c.team_size] for c in sorted(sim.all_cargo, key=lambda c: c.id)
                 if c.t_ready <= t1w and (c.t_delivered is None or c.t_delivered >= t0w)]
        res = sorted([[f"apron:{k[1]}" if isinstance(k, tuple) else int(k), _t(a), _t(b), int(dd), o, int(v)]
                      for k, lst in sim.roads.table.items() for a, b, dd, o, v in lst if b > t0w and a < t1w],
                     key=lambda x: (x[1], str(x[0])))
        lands = [[_t(t), lt.name, pad] for t, lt, pad in sim.landing_schedule if t0w <= t <= t1w]
        clos = [[_t(a), _t(b), pad, float(sim.plume.R)] for a, b, pad in sim.plume.windows if b >= t0w and a <= t1w]
        e = sim.roads.cfg["eva"]
        crew = [[_t(a), _t(b), "BASE", float(e["zone_km"]), float(e["v_crew_kmh"])] for a, b in sim.roads.eva
                if b >= t0w and a <= t1w]
        mism = {"items": items != tr["items"], "reservations": res != tr["reservations"],
                "landings": lands != tr["landings"], "closures": clos != tr["closures"], "crew": crew != tr["crew"]}
        dk = {}
        for x in tr["decisions"]:
            dk[x[1]] = dk.get(x[1], 0) + 1
        rows.append(_row("V1", f"{name}: engine", f"The '{name}' trace equals a fresh engine run ({tr['regime']})", 0.0,
                         float(sum(mism.values())), 0.0, "blocks differing", f"fresh run without export hooks, same "
                         f"scenario, seed and horizon; compared: {len(items)} items, {len(res)} reservations, "
                         f"{len(lands)} landings, {len(clos)} closures, {len(crew)} crew walks (differing: "
                         f"{[k for k, v in mism.items() if v] or 'none'}). Trace counts: {len(tr['jobs'])} jobs, "
                         f"{len(tr['radio'])} radio entries, decisions {dk}", "traces", "code verification", "V", "P1",
                         ["P1", "P2"], mode="abs", source="tools/atc/export_trace.py; extends B-31", t0=t0))
    t0 = time.time()
    v = {"jump": 0, "edge_ends": 0, "outside_reservation": 0, "fractions": 0, "start": 0, "pieces_on_segments": 0}
    for name, tr in docs.items():
        resv = {}
        for rname, a, b, dd, o, vid in tr["reservations"]:
            resv.setdefault((str(rname), vid), []).append((a, b))
        def start_at(l):
            e = l[7]
            return (l[2],) if e is None or e[1] == 0.0 else (e[0], e[1])

        def end_at(l):
            e = l[7]
            return (l[2],) if e is None else ((l[3],) if e[2] == 1.0 else (e[0], e[2]))
        for f in tr["fleet"]:                                 # start: a known site, and where the first leg begins
            first = tr["legs"].get(str(f[0]))
            v["start"] += (len(f) < 5 or f[4] not in tr["sites"] or (bool(first) and first[0][2] != f[4]))
        for vid, legs in tr["legs"].items():
            prev = None
            for leg in legs:
                t_a, t_b, fr, to, kind, load, job, edge = leg
                if prev is not None and end_at(prev) != start_at(leg):      # where one leg ends the next begins
                    v["jump"] += 1
                if edge is not None:
                    key, f0, f1, res = edge
                    poly = tr["roads"]["edges"][key]
                    if (f0 == 0.0 and poly[0] != tr["sites"][fr]) or (f1 == 1.0 and poly[-1] != tr["sites"][to]):
                        v["edge_ends"] += 1
                    if not (0.0 <= f0 <= f1 <= 1.0):
                        v["fractions"] += 1
                    if res >= 0:
                        v["pieces_on_segments"] += 1
                        win = resv.get((str(res), int(vid)), [])
                        if not any(abs(a - t_a) <= 0.0015 and abs(b - t_b) <= 0.0015 for a, b in win):
                            v["outside_reservation"] += 1
                prev = leg
    n_on = v.pop("pieces_on_segments")
    rows.append(_row("V2", "positions", "Vehicle positions in the trace: every vehicle has a start site, no jumps "
                     "(each leg starts where the last ended, at a site or at the same fraction of the same edge), edges "
                     "end at their sites, every single-lane piece inside the vehicle's own reservation", 0.0, float(sum(v.values())), 0.0,
                     "violations", f"both traces; {n_on} pieces on single-lane segments; violations by kind: "
                     + ", ".join(f"{k} {x}" for k, x in v.items()) + "; times compared at the files' 0.001 h rounding",
                     "traces", "code verification", "V", "P1", ["P1", "P2"], mode="abs",
                     source="tools/atc/export_trace.py; lunarsim/atc/roads.py", t0=t0))
    return rows


def run_phase5_tranche3() -> List[Dict]:
    rows: List[Dict] = []
    for f in (check_r3_knife_edge, check_r4_link_budget, check_s4_invariance, check_t3_capacity, check_e4_charging,
              check_l5_monotone, check_x_not_possible, check_tranche3_skipped):
        rows += f()
    return rows


def run_phase5_batch3b() -> List[Dict]:
    rows: List[Dict] = []
    for f in (check_s1_separation, check_s2_injection, check_s3_minimal, check_s5_encounters, check_t1_single_lane,
              check_t2_deterministic, check_t5_s5_s6_s7_roads, check_v_replay):
        rows += f()
    return rows


# ================================================================================================ tranche 3 (B-79)
def check_r3_knife_edge() -> List[Dict]:
    """R3: a single ridge of known height between two antennas, through the mesh builder's line-of-sight routine:
    blocked iff the ridge top is above the chord; the first-Fresnel clearance ratio against r1 = sqrt(lambda d1 d2 /
    (d1 + d2)). The model computes clearance and the Fresnel ratio, not a diffraction loss J(nu)."""
    t0 = time.time()
    MESH = _tool("mesh")
    L, xm, half = 2000.0, 1000.0, 10.0
    lam = MESH.C_LIGHT / MESH.FREQS_HZ[0]
    Hs = np.round(np.arange(0.0, 6.0, 0.01), 6)
    wrong, worst, n = 0, 0.0, 0
    for ha, hb in ((2.5, 2.5), (2.5, 1.0), (1.0, 2.5), (10.0, 2.5)):
        for H in Hs:
            class Ridge:
                @staticmethod
                def height(x, y, _H=H):
                    return np.where(np.abs(np.asarray(x) - xm) <= half + 1e-9, _H, 0.0) + 0.0 * np.asarray(y)
            P = np.array([[0.0, 0.0], [L, 0.0]])
            clear, ratio = MESH.pair_profiles(Ridge(), P, np.array([0]), np.array([1]), [(ha, hb)], radius_m=math.inf)
            s = np.arange(1, int(math.ceil(L / MESH.STEP_M))) * (L / math.ceil(L / MESH.STEP_M))
            ground = np.where(np.abs(s - xm) <= half + 1e-9, H, 0.0)
            chord = ha + (hb - ha) * s / L
            cl = chord - ground
            r1 = np.sqrt(lam * s * (L - s) / L)
            blocked_ref = bool(cl.min() <= 0)
            wrong += blocked_ref != bool(clear[0, 0] <= 0)
            worst = max(worst, abs(float(ratio[0, 0]) - float((cl / r1).min())) / max(1e-12, abs(float((cl / r1).min()))))
            n += 1
    return [_row("R3", "knife edge: blocking", "A single ridge blocks the link iff its top is above the chord", 0.0,
                 float(wrong), 0.0, "cases", f"{n} cases: a 20 m wide ridge 0-6 m high (1 cm steps) midway on a 2 km flat "
                 "path, antennas 2.5/2.5, 2.5/1.0, 1.0/2.5 and mast 10/2.5 m, through tools/atc/mesh.py pair_profiles",
                 "analytic", "code verification", "V", "P2", ["P3"], mode="abs", source="ITU-R P.526 (single knife "
                 "edge); geometry", t0=t0),
            _row("R3", "knife edge: Fresnel ratio", "First-Fresnel clearance ratio at the worst point equals clearance / "
                 "sqrt(lambda d1 d2 / (d1 + d2))", 0.0, worst, 1e-9, "rel", f"same {n} cases at {MESH.FREQS_HZ[0] / 1e9:g} "
                 "GHz; largest relative difference. The model has no diffraction loss J(nu): a link needs clearance (and, "
                 "when asked, a Fresnel ratio), so J(nu) is not checked", "analytic", "code verification", "V", "P2",
                 ["P3"], mode="abs", source="ITU-R P.526", t0=t0)]


def check_r4_link_budget() -> List[Dict]:
    """R4: E48's link budget per class recomputed from its design file (arithmetic), its constants against the exact
    ones, and the Shannon bound."""
    t0 = time.time()
    rd = json.load(open(_repo("data", "scenarios", "E48-design.json"), encoding="utf-8"))["radio"]
    res = json.load(open(_repo("results", "E48_sizing.json"), encoding="utf-8"))["classes"]
    c, kB = 299792458.0, 1.380649e-23
    worst_arith, worst_const, worst_rate, over = 0.0, 0.0, 0.0, 0
    lines = []
    for cls, r in res.items():
        f = rd["freq_ghz"][cls] * 1e9
        pt = 10 * math.log10(rd["tx_power_w"][cls] * 1000.0)
        fspl48 = 20 * math.log10(rd["worst_hop_m"]) + 20 * math.log10(f) - 147.55
        noise48 = -174 + 10 * math.log10(rd["bandwidth_mhz"] * 1e6) + rd["noise_figure_db"]
        snr48 = pt + 2 * rd["antenna_gain_dbi"] - fspl48 - noise48 - rd["implementation_margin_db"]
        rate48 = rd["bandwidth_mhz"] * 1e3 * math.log2(1 + 10 ** (snr48 / 10))
        worst_arith = max(worst_arith, abs(rate48 - r["link"]["worst_hop_kbps"]))
        fspl = 20 * math.log10(4 * math.pi * rd["worst_hop_m"] * f / c)
        n0 = 10 * math.log10(kB * 290.0 * 1000.0)
        noise = n0 + 10 * math.log10(rd["bandwidth_mhz"] * 1e6) + rd["noise_figure_db"]
        snr = pt + 2 * rd["antenna_gain_dbi"] - fspl - noise - rd["implementation_margin_db"]
        rate = rd["bandwidth_mhz"] * 1e3 * math.log2(1 + 10 ** (snr / 10))
        worst_const = max(worst_const, abs(snr - snr48))
        worst_rate = max(worst_rate, abs(rate - rate48) / rate48)
        cap = rd["bandwidth_mhz"] * 1e3 * math.log2(1 + 10 ** ((snr48 + rd["implementation_margin_db"]) / 10))
        over += r["link"]["worst_hop_kbps"] > cap + 1e-9
        lines.append(f"{cls} {r['link']['worst_hop_kbps']:.1f} kbit/s")
    return [_row("R4", "arithmetic", "E48's link budget reproduces from its design file", 0.0, worst_arith, 0.05,
                 "kbit/s", "per class: P_t + 2 G - FSPL - (kTB + NF) - margin, rate = B log2(1 + SNR), with E48's own "
                 "constants; stored rates are rounded to 0.1 kbit/s: " + ", ".join(lines), "analytic",
                 "code verification", "V", "P2", ["P3"], mode="abs", source="Friis 1946; Shannon 1948; tools/atc/run_e48.py",
                 t0=t0, tol_src="half the stored rounding (0.1 kbit/s)"),
            _row("R4", "constants", "E48's rounded constants against the exact ones (FSPL 20 log10(4 pi d f / c), kT at "
                 "290 K)", 0.0, worst_const, 0.05, "dB", f"E48 uses -147.55 dB for 20 log10(4 pi / c) (exact "
                 f"{20 * math.log10(4 * math.pi / c):.4f}) and -174 dBm/Hz for kT (exact {10 * math.log10(kB * 290 * 1000):.3f}); "
                 f"largest SNR difference {worst_const:.4f} dB, rate difference {100 * worst_rate:.3f} %", "analytic",
                 "code verification", "V", "P2", ["P3"], mode="abs", source="CODATA 2018 (k, c)", t0=t0,
                 tol_src="half of E48's 0.1 dB SNR reporting precision"),
            _row("R4", "Shannon bound", "No link carries more than B log2(1 + SNR)", 0.0, float(over), 0.0, "classes",
                 f"{len(res)} classes; the stored rate against the capacity at the SNR before the implementation margin",
                 "analytic", "code verification", "V", "P2", ["P3"], mode="abs", source="Shannon 1948", t0=t0)]


def check_e4_charging() -> List[Dict]:
    """E4: charge time = energy short / charging power (the engine has no charging efficiency: eta = 1), and idle
    recharge = power x time up to capacity. The engine has no solar model, so the solar row is skipped."""
    from . import dispatch
    from .engine import Simulation, Job
    from .scenario import Scenario
    from .entities import Cargo
    rows = []
    t0 = time.time()
    worst = 0.0
    for frac in (0.0, 0.25, 0.6):
        sc = Scenario(night_fraction=0.0, failures=False, other_duty_share=0.0)
        sim = Simulation(sc, dispatch.pooled_greedy, seed=1)
        v = sim.vehicles[0]
        c = Cargo(10 ** 6, "NASA", 100.0, sim.world.pads[0], "BASE", 0.0, 0.0, 1, "A", "consumables")
        job = Job([v], [c], ["BASE"])
        dur, km, km_e, e_wh, _ = sim.job_plan(job, 0.0)
        v.battery_wh = frac * e_wh
        sim.waiting.append(c)
        sim.all_cargo.append(c)
        sim._start_job(job)
        ref = dur + (e_wh - frac * e_wh) / (v.cls.charge_kw * 1000.0)
        worst = max(worst, abs((v.busy_until - 0.0) - ref) / ref)
    rows.append(_row("E4", "charge time", "Charge time before a trip = energy short / charging power", 0.0, worst, 1e-9,
                     "rel", "first vehicle of the default fleet, a pad-to-BASE job needing e_wh with the pack at 0, 25 and "
                     "60 % of it: busy time = planned hours + (e_wh - pack) / (charge_kw x 1000); the engine has no "
                     "charging efficiency (eta = 1)", "analytic", "code verification", "V", "P2", ["P1", "P3"], mode="abs",
                     source="lunarsim/engine.py", t0=t0))
    t0 = time.time()
    sim = Simulation(Scenario(night_fraction=0.0, failures=False, other_duty_share=0.0), dispatch.pooled_greedy, seed=1)
    worst = 0.0
    for v in sim.vehicles:
        v.battery_wh = 0.1 * v.cls.battery_wh
        v.busy_until = 0.0
    dt = 3.0
    sim._advance_to(dt)
    for v in sim.vehicles:
        ref = min(v.cls.battery_wh, 0.1 * v.cls.battery_wh + v.cls.charge_kw * 1000.0 * dt)
        worst = max(worst, abs(v.battery_wh - ref) / ref)
    rows.append(_row("E4", "idle recharge", "Idle recharge = charging power x time, up to capacity", 0.0, worst, 1e-9,
                     "rel", f"every vehicle of the default fleet idle for {dt:g} h from 10 % of its pack", "analytic",
                     "code verification", "V", "P2", ["P1", "P3"], mode="abs", source="lunarsim/engine.py", t0=t0))
    r = _row("E4", "solar input", "Daily solar energy = eta A S cos i over the illumination file", float("nan"),
             float("nan"), 0.0, "", "the engine has no solar power model (vehicles recharge at a fixed power when idle)",
             "analytic", "code verification", "V", "P2", ["P1", "P3"], mode="abs", source="Kopp and Lean 2011")
    r["skipped"] = "not applicable: no solar power model in the engine"
    rows.append(r)
    return rows


def check_s4_invariance() -> List[Dict]:
    """S4: (a) the bounded model checker (E45) proves the rule set on its instances and catches every mutation;
    (b) closed-loop forward invariance by exhaustive grid: from every state with the RSS gap, a follower whose planner
    always asks for full acceleration, under the shield, never touches a leader that brakes at up to B_MAX."""
    from .atc import safety as S
    rows = []
    t0 = time.time()
    mc = json.load(open(_repo("results", "E45_modelcheck.json"), encoding="utf-8"))
    n_models = len(mc.get("models", {}))
    n_mut = len(mc.get("mutations", {}))
    ok = bool(mc.get("all_models_pass")) and bool(mc.get("all_mutations_caught"))
    rows.append(_row("S4", "(a) model checker", "The bounded model checker proves the rules on its instances and catches "
                     "every mutation (E45)", 1.0, float(ok), 0.0, "pass", f"results/E45_modelcheck.json: {n_models} "
                     f"models (all pass: {mc.get('all_models_pass')}), {n_mut} mutations (all caught: "
                     f"{mc.get('all_mutations_caught')}); step {mc.get('step_s')} s, cell {mc.get('cell_m')} m",
                     "formal (bounded model checking)", "code verification", "V", "P1", ["P2"], mode="abs",
                     source="Lamport 2002; lunarsim/atc/modelcheck.py", t0=t0))
    t0 = time.time()
    dt, steps = 0.1, 1500
    coll, n_states, min_gap = 0, 0, math.inf
    rng = np.random.default_rng(4)
    for theta in (0.0, 5.0, 10.0):
        b = float(S.b_guaranteed(theta, 0.3))
        vmax = float(S.v_max_r2(theta, 0.3, 1e6, 2.8))
        vr0, vl0, k = np.meshgrid(np.linspace(0, vmax, 25), np.linspace(0, vmax, 25), np.linspace(1.0, 3.0, 9),
                                  indexing="ij")
        vr, vl = vr0.ravel(), vl0.ravel()
        gap = S.rss_dmin(vr, vl, b) * k.ravel()
        N = len(vr)
        n_states += N
        brake_at = rng.uniform(0, 60, N)                # the leader cruises, then brakes at B_MAX to a stop
        t = 0.0
        for _ in range(steps):
            al = np.where(t >= brake_at, -S.B_MAX, rng.uniform(-S.B_MAX, 0.05, N))
            m = _move(v=vr, a_prop=np.full(N, 0.2), theta=np.full(N, theta), mu=np.full(N, 0.3),
                      v_class=np.full(N, 2.8), sight=np.full(N, 1e6), gap_lead=gap, v_lead=vl,
                      d_stop=np.full(N, np.inf), d_crew=np.full(N, np.inf))
            a = S.safety_check(None, m).a
            vr1, xr = S._after_step(vr, a, dt)
            vl1, xl = S._after_step(vl, al, dt)
            gap = gap - xr + xl
            vr, vl = vr1, vl1
            t += dt
            min_gap = min(min_gap, float(gap.min()))
            coll += int(np.sum(gap <= 0))
    rows.append(_row("S4", "(b) closed loop", "Forward invariance: from every state with the RSS gap, an always-"
                     "accelerating planner under the shield never touches its leader", 0.0, float(coll), 0.0,
                     "contacts", f"{n_states:,} initial states (follower and leader speeds on a 25 x 25 grid up to the R2 "
                     f"limit, gap 1-3 x the RSS minimum, slopes 0 / 5 / 10 deg, mu 0.3) x {steps} steps of {dt} s; "
                     f"leader cruises with random braking up to B_MAX, then brakes at B_MAX to a stop; smallest gap "
                     f"{min_gap:.3f} m", "formal (exhaustive grid)", "code verification", "V", "P2", ["P2"], mode="abs",
                     source="Ames et al. 2019 (forward invariance); Shalev-Shwartz et al. 2017 (RSS)", t0=t0))
    return rows


def check_x_not_possible() -> List[Dict]:
    out = []
    for cid, name, why in (("X2", "Python against the browser engine on the ATC cells",
                            "not possible: the browser has no ATC engine (web/sim.js is the frozen v2/v3 engine); the "
                            "browser's ATC safety program is checked against the E44 fixtures by FRONTEND's tests"),
                           ("X5", "Face validity review by outside reviewers",
                            "not a computation: it needs reviewers outside the team watching replays (the owner's call)")):
        r = _row(cid, "not possible", name, float("nan"), float("nan"), 0.0, "", why, "comparison to other models",
                 "results robustness", "V" if cid == "X2" else "Val", "P2", ["P1", "P2", "P3"], mode="abs",
                 source="verification_plan.md")
        r["skipped"] = why
        out.append(r)
    return out


def check_t3_capacity() -> List[Dict]:
    """T3: saturation flow of a following lane. A platoon starts packed at standstill and every planner asks for full
    acceleration, so only the safety program limits the gaps; at the R2 speed v the flow past a line far downstream is
    v / (L_veh + d_min(v, v)), d_min the RSS minimum gap (with its static margin)."""
    from .atc import encounter as E
    from .atc import safety as S
    t0 = time.time()
    nv, X = 12, 2500.0
    theta, mu, vcl = 0.0, 0.3, 2.8
    b = float(S.b_guaranteed(theta, mu))
    v = float(S.v_max_r2(theta, mu, 1e4, vcl))
    y = E.lane_y(1)
    pts = np.array([(0.0, y), (4000.0, y)])
    s0, s = [], 300.0
    for i in range(nv):
        s0.append(s)
        s -= E.VEH_L + float(S.rss_dmin(0.0, 0.0, b)) + 0.01
    t_end = (X + 300.0) / v + 40.0 * nv + 200.0
    sp = E.Spec(paths=[pts] * nv, v_class=[v] * nv, v0=[0.0] * nv, s0=s0, planner=[2] * nv, theta=theta, mu=mu,
                priority=list(range(nv)), t_max=t_end, params={"t3": True})
    bt = E.Batch([sp])
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        oc, tr = E.run_batch(bt, np.random.default_rng(3), record=[0])
    steps = tr[0]
    ts = np.array([st["t"] for st in steps])
    ss = np.array([st["s"] for st in steps])                # (steps, nv)
    cross = []
    for k in range(nv):
        j = np.flatnonzero(ss[:, k] >= X)
        if len(j) == 0:
            break
        j = int(j[0])
        f = (X - ss[j - 1, k]) / (ss[j, k] - ss[j - 1, k])  # linear within the 0.1 s step
        cross.append(ts[j - 1] + f * (ts[j] - ts[j - 1]))
    cross = np.array(cross)
    hw = np.diff(cross)[2:]                                  # skip the first gaps (the platoon still forming)
    q = 1.0 / float(hw.mean()) if len(hw) else float("nan")
    ref = v / (E.VEH_L + float(S.rss_dmin(v, v, b)))
    vl1, xl1 = S._after_step(np.array([v]), np.array([-S.B_MAX]), E.DT)
    g_eq = float(S.rss_dmin(v, vl1[0], b)) + v * E.DT - float(xl1[0])     # the shield's equilibrium at 10 Hz
    disc = _row("T3", "saturation flow, 10 Hz shield", "Saturation flow of a following lane with the shield's one-step "
                "look-ahead = v / (L_veh + d_min(v, v - B_MAX dt) + v dt - x_lead(dt))", 3600.0 * v / (E.VEH_L + g_eq),
                q * 3600.0, 0.01, "veh/h", f"same run; each 0.1 s step the shield assumes the leader brakes at B_MAX "
                f"within the step, so the steady gap is {g_eq:.3f} m, not d_min(v, v) = {float(S.rss_dmin(v, v, b)):.3f} m",
                "analytic", "code verification", "V", "P2", ["P2"], source="lunarsim/atc/safety.py _ok (R1)", t0=t0)
    return [disc, _row("T3", "saturation flow", "Saturation flow of a following lane = v / (L_veh + d_min)", ref * 3600.0,
                 q * 3600.0, 0.01, "veh/h", f"{nv} vehicles from standstill, every planner at full acceleration "
                 f"(adversarial), flat, mu {mu}: v = {v:.3f} m/s (R2), L_veh {E.VEH_L} m, d_min(v, v) "
                 f"{float(S.rss_dmin(v, v, b)):.2f} m; flow from the last {len(hw)} headways past s = {X:g} m "
                 f"({len(cross)} vehicles crossed); violations in the run {int(oc.viol_contact[0] + oc.viol_gap[0])}. "
                 "The continuous formula overstates the model's capacity by the shield's one-step look-ahead (row "
                 "'saturation flow, 10 Hz shield' matches); a property of the 10 Hz shield, not a defect",
                 "analytic", "code verification", "V", "P2", ["P2"], source="Daganzo 1997", t0=t0)]


def check_l5_monotone(n: int = 10000) -> List[Dict]:
    """L5: the learned correction never makes a robot bid less for a longer approach or a heavier bundle, or more for a
    fuller battery: bid' = bid - urgency x g, so g must not rise with approach_h or mass_frac and not fall with battery
    (finite differences on random probes inside the check vectors' feature ranges)."""
    from .atc.learned import Policy, FEATURES
    from .scenario import Scenario
    sc0 = Scenario()
    # the base bid rises with approach time by at least the smallest value of time (and the carrier's cost, ignored
    # here): the correction may rise by up to that over the urgency weight per approach hour without lowering the bid
    slack_per_h = min(sc0.vot_usd_per_h.values()) / sc0.urgency_usd_per_h
    rows = []
    for pid in ("atc_bid_v1", "atc_bid_linear_v1"):
        t0 = time.time()
        pol = Policy(_repo("data", "policies", pid + ".json"))
        chk = json.load(open(_repo("data", "policies", pid + ".check.json"), encoding="utf-8"))
        obs = np.array(chk["obs"], float)
        lo, hi = obs.min(0), obs.max(0)
        rng = np.random.default_rng(5)
        X = lo + (hi - lo) * rng.random((n, len(FEATURES)))
        viol, lines = 0, []
        for feat, sign in (("approach_h", +1), ("mass_frac", +1), ("battery", -1)):
            j = list(FEATURES).index(feat)
            d = max(1e-3, 0.01 * (hi[j] - lo[j]))
            X2 = X.copy()
            X2[:, j] += d
            dg = pol(X2) - pol(X)
            allow = slack_per_h * d if feat == "approach_h" else 0.0
            bad = int(np.sum(sign * dg > allow + 1e-12))  # the total bid falls with approach or mass, or rises with SOC
            viol += bad
            lines.append(f"{feat} {bad}")
        share = viol / (3 * n)
        rows.append(_row("L5", pid, f"Learned bid monotone in approach, mass and battery ({pid})", 0.0, share, 0.01,
                         "share", f"{n:,} probes x 3 features inside the check vectors' ranges; bid' = bid - urgency x g, the "
                         f"base bid rising with approach time by at least the smallest value of time (slack {slack_per_h:g} "
                         "of g per approach hour) and not depending on mass or battery; violations by feature: "
                         + ", ".join(lines) + ". A property of the trained policy (tuned by CEM on urgent wait), not of the "
                         "code", "metamorphic testing", "referent validation", "Val", "P2", ["P1"],
                         mode="abs", source="Chen et al. 2018", t0=t0,
                         tol_src="research_notes/Lunar ATC/verification_plan.md section 3, row L5: <= 1 % of probes"))
    return rows


def check_tranche3_skipped() -> List[Dict]:
    out = []
    for cid, name, why in (
            ("R6", "Relay orbit period and visible fraction against SPICE",
             "not applicable: the relay is modelled as a coverage share (B_EARTH_RELAY coverage p), not an orbit"),
            ("R8", "Face validity of DTE coverage against published values",
             "skipped by the ten-minute rule: the published values use other criteria and antenna heights, so a fair "
             "comparison needs the prior-art note's criteria matched case by case"),
            ("L3", "Calibration of predicted against realised costs",
             "skipped by the ten-minute rule: the policy outputs a bid correction, not a cost or ETA prediction, so a "
             "calibration target would have to be defined first"),
            ("V3", "Positions between events on the route and on the ground in the 3D scene",
             "FRONTEND's: the scene's interpolation and the wheel height above the DEM live in the browser"),
            ("V4", "Sun, Earth and link lines drawn in the scene",
             "FRONTEND's: the drawn directions and link lines live in the browser"),
            ("T4", "Jackson network of single-lane segments",
             "skipped by the ten-minute rule: it needs exponential traversal and Markov routing through a new test hook "
             "in the road layer")):
        r = _row(cid, "skipped", name, float("nan"), float("nan"), 0.0, "", why, "analytic", "code verification", "V",
                 "P3", ["P1", "P2", "P3"], mode="abs", source="verification_plan.md")
        r["skipped"] = why
        out.append(r)
    return out


# ------------------------------------------------------------------------------------------------ run and write
def run_phase5_checks(batches=(1, 2, 3)) -> List[Dict]:
    rows: List[Dict] = []
    if 1 not in batches:
        return (run_phase5_batch2() if 2 in batches else rows) + (run_phase5_batch3() + run_phase5_batch3b() if 3 in batches else [])
    for f in (check_d1_sample_path, check_d2_pk, check_d3_multi, check_d4_cobham, check_d5_extremes,
              check_d6_one_owner, check_d7_time_scale, check_d8_invariants, check_d9_hungarian, check_d10_crn,
              check_d11_inputs, check_r1_horizon, check_e3_energy):
        r = f()
        rows += r if isinstance(r, list) else [r]
    if 2 in batches:
        rows += run_phase5_batch2()
    if 3 in batches:
        rows += run_phase5_batch3() + run_phase5_batch3b() + run_phase5_tranche3()
    return rows


def _finite(x):
    if isinstance(x, float) and not math.isfinite(x):
        return None
    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_finite(v) for v in x]
    if isinstance(x, (np.floating, np.integer)):
        return _finite(x.item())
    return x


def write_json(rows: List[Dict], path: Optional[str] = None) -> str:
    import subprocess
    path = path or _repo("results", "vv_phase5.json")
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=_repo(), capture_output=True, text=True,
                                timeout=20).stdout.strip() or None
    except Exception:
        commit = None
    ran = [r for r in rows if not r["skipped"]]
    doc = {"version": 1, "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "commit": commit,
           "summary": {"rows": len(rows), "passed": sum(r["passed"] for r in ran),
                       "failed": sum(not r["passed"] for r in ran), "skipped": len(rows) - len(ran),
                       "bias_flags": sum(1 for r in ran if r.get("bias_flag"))},
           "rows": _finite(rows)}
    keys = [(r["id"], r["sub"]) for r in rows]
    if len(set(keys)) != len(keys):
        raise ValueError("id + sub must be unique")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, allow_nan=False)
        f.write("\n")
    return path


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(1500, exit=True)
    t = time.time()
    rows = run_phase5_checks()
    p = write_json(rows)
    for r in rows:
        print(("PASS" if r["passed"] else "FAIL") + (" bias" if r.get("bias_flag") else ""), r["id"], r["sub"],
              f"ref={r['reference']:.6g} sim={r['simulated']:.6g} err={r['error']:.3g}")
    print(os.path.relpath(p, _repo()), f"{len(rows)} rows, {time.time() - t:.0f} s")
