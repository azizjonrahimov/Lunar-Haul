"""B-117 (h), P2 S8, EXPLORATORY (a trace, not a test): why the uncoordinated road mode refers more conflicts to
Earth on Mars (94 a year, E47 rtt 20 min, no relay) than on the Moon (53, E43 2028), for the same demand.

    python tools/atc/b117h_conflict_trace.py run     # resumable, cached in .cache/atc/b117h.json (--max-seconds 500)
    python tools/atc/b117h_conflict_trace.py table   # -> results/B117h_conflict_trace.json (a new file)

The cells are E43's "uncoordinated x1" (2028 and 2038) and E47's "uncoordinated x1 mars rtt 20 no relay" and
"... rtt 20 relay", run as their experiments run them (run_phase5.run_one, dispatch fixed point), seeds 1-30. Each run
logs every conflict referred to Earth by wrapping lunarsim.atc.roads.RoadLayer._hand in this process (no lunarsim file
is changed): when it arose, when Earth's decision came, the stop of both vehicles, the vehicles and the segment. A
check: each run's conflict count equals the stored row (results/E43_runs.lead.csv, E47_runs*.csv).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, HERE, os.path.join(ROOT, "experiments", "phase5")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from experiments.phase5 import run_phase5 as R  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "b117h.json")
OUT = os.path.join(ROOT, "results", "B117h_conflict_trace.json")
CELLS = {"moon 2028": ("E43", "uncoordinated x1", 2028), "moon 2038": ("E43", "uncoordinated x1", 2038),
         "mars rtt 20 no relay": ("E47", "uncoordinated x1 mars rtt 20 no relay", 2028),
         "mars rtt 20 relay": ("E47", "uncoordinated x1 mars rtt 20 relay", 2028)}
LOG: list = []


def _install():
    from lunarsim.atc import roads
    if getattr(roads.RoadLayer._hand, "_b117h", False):
        return
    orig = roads.RoadLayer._hand

    def logged(self, sim, v, t_req, hidden, key):
        tc = max(t_req, min(x[0] for x in hidden))
        tr = self._hand_until(tc)
        vs = sim.vehicles.values() if isinstance(sim.vehicles, dict) else sim.vehicles
        busy = sum(1 for u in vs if u.busy_until > t_req)
        go = orig(self, sim, v, t_req, hidden, key)
        LOG.append({"t_req": float(t_req), "t_conflict": float(tc), "t_decision": float(tr), "stop_h": float(max(0.0, tr - tc)),
                    "go": float(go), "v": int(v.id), "owner": str(v.owner), "others": [int(x[4]) for x in hidden],
                    "key": str(key), "vehicles_busy_at_request": busy})
        return go
    logged._b117h = True
    roads.RoadLayer._hand = logged


def _cell(exp, label):
    cells = R.e43_cells() if exp == "E43" else R.e47_cells()
    return next(c for c in cells if c["tag"]["label"] == label)


def code_fingerprint():
    import hashlib
    import inspect
    import run_e50 as E5
    return E5.code_fingerprint() + "+" + hashlib.sha256(inspect.getsource(_install).encode()).hexdigest()[:8]


def cmd_run(max_s):
    _install()
    t0, last = time.time(), 20.0
    done = json.load(open(CACHE, encoding="utf-8")) if os.path.isfile(CACHE) else {}
    fp = code_fingerprint()
    if done and done.get("_code") != fp:
        raise SystemExit(f"{CACHE} was made with other code; delete it and rerun")
    done["_code"] = fp
    for name, (exp, label, year) in CELLS.items():
        c = _cell(exp, label)
        for seed in R.V1_SEEDS:
            k = f"{name}|{seed}"
            if k in done:
                continue
            if time.time() - t0 > max_s - max(60, 1.5 * last):
                print(f"run: time limit, {len(done) - 1} done; rerun", flush=True)
                return
            LOG.clear()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r = R.run_one(c, seed, year, fixpoint=True)
            last = r["run_s"]
            done[k] = {"row": {m: float(r[m]) for m in r if m.startswith("road_") and np.isscalar(r[m])
                               and isinstance(r[m], (int, float, np.integer, np.floating))},
                       "delivered_items": float(r.get("delivered_items", np.nan)), "conflicts": list(LOG)}
            with open(CACHE + ".tmp", "w", encoding="utf-8") as f:
                json.dump(done, f)
            os.replace(CACHE + ".tmp", CACHE)
            print(f"  {k}: {len(LOG)} conflicts ({last} s)", flush=True)
    print("run: done", flush=True)


def _stored(exp, label, year):
    import pandas as pd
    d = R.load_runs(exp)
    if "label" not in d:
        d["label"] = d["cell"].str.extract(r"label=([^;]+)")[0]
    return d[(d["label"] == label) & (d["start_year"] == year)].set_index("seed")


def cmd_table():
    done = json.load(open(CACHE, encoding="utf-8"))
    if done.get("_code") != code_fingerprint():
        raise SystemExit("cache made with other code; rerun")
    out = {"task": "B-117 (h), P2 S8: the Mars fleet's 94 conflicts against the Moon's 53 (EXPLORATORY: a trace)",
           "note": __doc__.split("\n\n")[1].strip(), "seeds": list(R.V1_SEEDS), "code": done["_code"], "cells": {},
           "check_counts_equal_stored_rows": {}}
    for name, (exp, label, year) in CELLS.items():
        st = _stored(exp, label, year)
        runs = [done[f"{name}|{s}"] for s in R.V1_SEEDS]
        eq = all(int(st.loc[s, "road_hand_conflicts"]) == len(r["conflicts"]) == int(r["row"]["road_hand_conflicts"])
                 for s, r in zip(R.V1_SEEDS, runs))
        out["check_counts_equal_stored_rows"][name] = eq
        cs = [c for r in runs for c in r["conflicts"]]
        stop = np.array([c["stop_h"] for c in cs])
        trav = np.mean([r["row"]["road_traversals"] for r in runs])
        # conflicts that arise while one of their own vehicles is still held by an earlier conflict's stop
        held = 0
        for r in runs:
            until = {}
            for c in sorted(r["conflicts"], key=lambda c: c["t_conflict"]):
                vs = [c["v"]] + c["others"]
                if any(until.get(x, -1.0) > c["t_conflict"] for x in vs):
                    held += 1
                for x in vs:
                    until[x] = max(until.get(x, -1.0), c["t_decision"])
        # vehicle-hours held by stops, per year (each conflict stops both vehicles until the decision)
        held_vh = float(np.mean([sum(c["stop_h"] * (1 + len(c["others"])) for c in r["conflicts"]) for r in runs]))
        # the hours in which at least one pair waits for Earth's decision, and the conflict rate inside and outside
        H, cov_h, n_in, n_out = 8760.0, 0.0, 0, 0
        for r in runs:
            iv = sorted((c["t_conflict"], min(c["t_decision"], H)) for c in r["conflicts"] if c["t_decision"] > c["t_conflict"])
            U: list = []
            for a, b in iv:
                if U and a <= U[-1][1]:
                    U[-1][1] = max(U[-1][1], b)
                else:
                    U.append([a, b])
            cov_h += sum(b - a for a, b in U)
            for c in r["conflicts"]:
                t = c["t_conflict"]
                if any(a < t < b for a, b in iv):
                    n_in += 1
                else:
                    n_out += 1
        cov_h /= len(runs)
        out["cells"][name] = {
            "conflicts_per_year": round(len(cs) / len(runs), 2),
            "traversals_per_year": round(float(trav), 1),
            "conflicts_per_1000_traversals": round(1000.0 * len(cs) / len(runs) / trav, 3),
            "stop_h_mean": round(float(stop.mean()), 2), "stop_h_median": round(float(np.median(stop)), 2),
            "stop_h_p90": round(float(np.quantile(stop, 0.9)), 2),
            "share_of_conflicts_with_a_vehicle_still_held": round(held / max(len(cs), 1), 4),
            "vehicle_hours_held_per_year": round(held_vh, 1),
            "share_of_year_with_a_pair_waiting_for_earth": round(cov_h / H, 4),
            "conflicts_per_100h_while_a_pair_waits": round(100.0 * n_in / len(runs) / max(cov_h, 1e-9), 4),
            "conflicts_per_100h_otherwise": round(100.0 * n_out / len(runs) / (H - cov_h), 4),
            "hand_wait_h_per_year": round(float(np.mean([r["row"]["road_hand_wait_h"] for r in runs])), 1),
            "other_stop_h_per_year": round(float(np.mean([r["row"]["road_other_stop_h"] for r in runs])), 1),
            "delivered_items_per_year": round(float(np.mean([r["delivered_items"] for r in runs])), 1),
            "conflicts_by_quarter": [int(sum(1 for c in cs if q * 2190 <= c["t_conflict"] < (q + 1) * 2190)) for q in range(4)],
            "segments_top5": sorted({k: sum(1 for c in cs if c["key"] == k) for k in {c["key"] for c in cs}}.items(),
                                    key=lambda kv: -kv[1])[:5]}
    text = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with open(OUT + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(OUT + ".tmp", OUT)
    print(text)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--max-seconds", type=float, default=500.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    cmd_run(a.max_seconds) if a.cmd == "run" else cmd_table()
