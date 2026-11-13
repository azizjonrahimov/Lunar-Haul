"""B-105 (P3 M1; decisions B11): measure what the sizing paper calls measured.

    python tools/atc/run_b105.py run --mult 1      # one 30-day month per fleet multiple (1, 4, 8), resumable
    python tools/atc/run_b105.py run --mult 4
    python tools/atc/run_b105.py run --mult 8
    (python tools/atc/run_e48.py build then adds the blocks `measured_memory` and `per_robot_round` to E48_sizing.json)

E48's scenario (C_AUCTION, roads atc, 1 Jan 2028, seed 1; run_e48._scen), 30 days per fleet multiple.

(2) ONE robot's bid computation in one auction round: inside the marketplace each free robot computes its best
bundle over the pool (lunarsim/dispatch.py marketplace, the loop over the pool with _try_bundle and the bid
adjustment). Each _try_bundle call is timed (perf_counter) and summed per (auction round, robot); rounds are counted
at the auction's selector, which is called once per round after every robot's offer (lunarsim/atc/auction.py
_Selector). E48's cpu_auction_round_ms is the simulator's whole dispatch call for the whole fleet, pooled over the
fleet multiples; it is reported beside, relabelled.

(1) Peak memory of the on-robot part, measured with tracemalloc (bytes Python allocates; the interpreter, the code and
numpy's own buffers outside Python's allocator are not counted; a C implementation would hold the same data in less):
  - planner working memory: the peak allocated during one robot's bid computation, sampled (one robot-round in 20);
  - safety check: the peak during one safety_check call for one vehicle;
  - reservation table: a copy of the base table's entries in the next 24 h at mid-month and at month end (the window a
    robot holds), as Python objects;
  - ledger copy: the month's job records (time, vehicles, items, route), as Python objects;
  - bid policy: data/policies/atc_bid_v1.json loaded with lunarsim.atc.learned.Policy (C_AUCTION's default bids do
    not use it; the learned regimes do);
  - all of the above held at once (one tracemalloc session), the figure to compare with E48's 0.39 MB estimate.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
import time
import tracemalloc
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_e48 as E48  # noqa: E402

DAYS = 30
SAMPLE_EVERY = 20


def _peak_mb():
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + \
                       [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "a", "b", "c", "d", "e", "f")]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        f = k32.K32GetProcessMemoryInfo
        f.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        f(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return round(c.PeakWorkingSetSize / 2 ** 20, 1)
    except Exception:
        return None


def _traced(fn):
    """Peak bytes allocated while fn runs (tracemalloc), and fn's result."""
    tracemalloc.start()
    tracemalloc.reset_peak()
    base = tracemalloc.get_traced_memory()[0]
    out = fn()
    cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak - base, cur - base, out


def run(m, trace=True):
    """trace False (B-118 N12): the timing pass, with no tracemalloc anywhere in the month; trace True: the memory
    pass (planner sampling and the component peaks); its timings are kept only to measure tracemalloc's effect."""
    from lunarsim import Simulation, dispatch as D
    from lunarsim.atc import auction as AU, regimes as G, safety as S
    import run_phase5 as R
    sc = E48._scen(m, DAYS)
    state = {"round": 0, "per": {}, "n_calls": 0, "planner_peak": [], "sampling": False}
    orig_try = D._try_bundle

    def timed_try(sim, v, *a, **k):
        key = (state["round"], v.id)
        state["n_calls"] += 1
        sample = trace and (state["round"] % SAMPLE_EVERY == 0)
        if sample:
            tracemalloc.start()
            tracemalloc.reset_peak()
            b0 = tracemalloc.get_traced_memory()[0]
        t0 = time.perf_counter()
        out = orig_try(sim, v, *a, **k)
        dt = time.perf_counter() - t0
        if sample:
            state["planner_peak"].append(tracemalloc.get_traced_memory()[1] - b0)
            tracemalloc.stop()
        state["per"][key] = state["per"].get(key, 0.0) + dt
        return out
    D._try_bundle = timed_try
    orig_call = AU._Selector.__call__

    def sel_call(self, sim, offers):
        state.setdefault("pool_robots", []).append(len(offers))
        state["round"] += 1
        return orig_call(self, sim, offers)
    AU._Selector.__call__ = sel_call
    ledger = []
    mech = G.mechanism("C_AUCTION")
    hold = {}

    def mech_with_snap(s_, waiting, free, **kw):
        snap_mid()                                         # mid-month snapshot of the base's reservation table
        return mech(s_, waiting, free, **kw)
    for a_ in ("anticipates", "supports_team", "regime", "__name__"):
        if hasattr(mech, a_):
            setattr(mech_with_snap, a_, getattr(mech, a_))
    sim = Simulation(sc, mech_with_snap, seed=1, mech_kwargs={"start_year": 2028, "loss": R.LOSS})
    real_start = sim._start_job

    def start(job, _rs=real_start):
        n0 = len(sim.waiting)
        _rs(job)
        if len(sim.waiting) < n0:
            ledger.append((round(float(sim.t), 4), tuple(int(v.id) for v in job.vehicles),
                           tuple(id(c) % 10 ** 9 for c in job.items + job.backhaul),
                           tuple(round(float(c.mass_kg), 2) for c in job.items + job.backhaul), tuple(job.route)))
    sim._start_job = start
    mid = {}
    H = sc.horizon_h

    def snap_mid(sim_=sim):
        if not mid and sim.t >= H / 2:
            tab = sim.roads.table if sim.roads is not None else {}
            mid["win"] = {k: [e for e in v if e[1] >= sim.t and e[0] <= sim.t + 24.0] for k, v in tab.items()}
    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sim.run()
    run_s = time.time() - t0
    D._try_bundle = orig_try
    AU._Selector.__call__ = orig_call
    per = np.array(list(state["per"].values())) * 1000.0
    tab = sim.roads.table if sim.roads is not None else {}
    end_win = {k: [e for e in v if e[1] >= H - 24.0 and e[0] <= H] for k, v in tab.items()}
    win = max((mid.get("win") or {}, end_win), key=lambda w: sum(len(x) for x in w.values()))
    n_win = sum(len(x) for x in win.values())
    # memory, component by component (tracemalloc), then all at once
    tab_peak, tab_held, tab_copy = _traced(lambda: copy.deepcopy(win))
    led_peak, led_held, led_copy = _traced(lambda: copy.deepcopy(ledger))
    from lunarsim.atc.learned import Policy
    pol_peak, pol_held, pol = _traced(lambda: Policy(os.path.join(ROOT, "data", "policies", "atc_bid_v1.json")))
    one = dict(v=np.array([2.5]), a_prop=np.array([0.2]), dt=0.1, theta=np.array([5.0]), mu=0.45, v_class=np.array([2.78]),
               sight=np.array([1e4]), gap_lead=np.array([30.0]), v_lead=np.array([2.0]), d_stop=np.array([np.inf]),
               d_crew=np.array([np.inf]))
    S.safety_check(None, S.Move(**one))                         # warm up imports
    sc_peak, _, _ = _traced(lambda: S.safety_check(None, S.Move(**one)))
    pp = np.array(state["planner_peak"], float)
    planner_p99 = float(np.quantile(pp, 0.99)) if len(pp) else 0.0

    def all_at_once():
        hold = [copy.deepcopy(win), copy.deepcopy(ledger),
                Policy(os.path.join(ROOT, "data", "policies", "atc_bid_v1.json"))]
        S.safety_check(None, S.Move(**one))
        return len(hold)
    all_peak, all_held, _ = _traced(all_at_once)
    MB = 1e6
    return {"mult": m, "days": DAYS, "seed": 1, "robots": len(sim.vehicles), "run_s": round(run_s, 1),
            "process_peak_working_set_mb": _peak_mb(),
            "per_robot_round": {"n": int(len(per)), "median_ms": float(np.median(per)), "p99_ms": float(np.quantile(per, 0.99)),
                                "max_ms": float(per.max()), "rounds": int(state["round"]),
                                "try_bundle_calls": int(state["n_calls"]),
                                "robots_per_round_mean": float(np.mean(state.get("pool_robots", [0])))},
            "memory_mb": {"planner_working_peak_p99": planner_p99 / MB, "planner_working_peak_max": float(pp.max()) / MB if len(pp) else 0.0,
                          "planner_samples": int(len(pp)),
                          "safety_check_peak": sc_peak / MB,
                          "reservation_window_24h": {"entries": int(n_win), "resources": int(sum(1 for x in win.values() if x)),
                                                     "held": tab_held / MB, "peak": tab_peak / MB},
                          "ledger_month": {"entries": len(ledger), "held": led_held / MB, "peak": led_peak / MB},
                          "bid_policy": {"held": pol_held / MB, "peak": pol_peak / MB},
                          "all_at_once_peak": all_peak / MB, "all_at_once_held": all_held / MB,
                          "all_at_once_plus_planner_p99": all_peak / MB + planner_p99 / MB}}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "timing"])
    ap.add_argument("--mult", type=int, required=True)
    ap.add_argument("--passes", type=int, default=3)
    a = ap.parse_args(argv)
    res = json.load(open(E48._cache("b105"))) if os.path.isfile(E48._cache("b105")) else {}
    if a.cmd == "timing":                            # B-118 N12: repeated timing passes (no tracemalloc), same month
        r = res[str(a.mult)]
        tp = r.setdefault("timing_passes", [r["per_robot_round"]])
        while len(tp) < a.passes:
            t = run(a.mult, trace=False)
            if any(t["per_robot_round"][k] != r["per_robot_round"][k] for k in ("n", "rounds", "try_bundle_calls")):
                raise SystemExit("timing pass is not the same run")
            tp.append(dict(t["per_robot_round"], timed_without_tracemalloc=True))
            E48._save("b105", res)
            print(a.mult, len(tp), round(tp[-1]["median_ms"], 3), round(tp[-1]["p99_ms"], 2), flush=True)
        return
    tm = run(a.mult, trace=False)                    # B-118 N12: timing and tracing in separate passes
    out = run(a.mult, trace=True)
    out["per_robot_round_traced_pass"] = out["per_robot_round"]
    out["per_robot_round"] = dict(tm["per_robot_round"], timed_without_tracemalloc=True)
    out["run_s_timing_pass"] = tm["run_s"]
    out["passes_same_run"] = all(tm["per_robot_round"][k] == out["per_robot_round_traced_pass"][k]
                                 for k in ("n", "rounds", "try_bundle_calls", "robots_per_round_mean"))
    res[str(a.mult)] = out
    E48._save("b105", res)
    print(json.dumps({k: out[k] for k in ("mult", "robots", "run_s", "process_peak_working_set_mb", "per_robot_round")}),
          json.dumps(out["memory_mb"]))


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(560, exit=True)
    main()
