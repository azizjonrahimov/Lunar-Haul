"""E45 (B-78): exhaustive check of the rules of the road on the discrete model (lunarsim/atc/modelcheck.py).

    python tools/atc/run_e45.py        # -> results/E45_modelcheck.json, results/E45_traces/*.json

Models: A (pad visit + oncoming vehicle; landing, crew, links), B (three vehicles on the line, two interchangeable;
crew), C (A's pad visit with two oncoming vehicles; landing, crew), D (C with radio links: the largest). Mutations
(each must give a counterexample): R3 without the exit-slot check (on B), R5 without the entry check (on A), R7 without
the hold (on A). Run time and peak memory (tracemalloc) per model.
"""
from __future__ import annotations

import json
import os
import sys
import time
import tracemalloc

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from lunarsim.atc import modelcheck as M  # noqa: E402

OUT = os.path.join(ROOT, "results", "E45_modelcheck.json")
TRACES = os.path.join(ROOT, "results", "E45_traces")

MODELS = {
    "A_pad_and_oncoming": dict(routes=["PAD", "E2W"]),
    "B_three_on_line": dict(routes=["W2E", "E2W", "E2W"], landing=False, links=False, symmetric=((1, 2),)),
    "C_pad_two_oncoming": dict(routes=["PAD", "E2W", "E2W"], links=False, symmetric=((1, 2),)),
    "D_pad_two_oncoming_links": dict(routes=["PAD", "E2W", "E2W"], symmetric=((1, 2),)),
}
MUTATIONS = {
    "R3_exit": ("B_three_on_line", "deadlock or liveness failure: a vehicle in the segment with its exit bay full"),
    "R5_entry": ("A_pad_and_oncoming", "safety: a vehicle in the landing zone while closed"),
    "R7_hold": ("A_pad_and_oncoming", "safety: a vehicle in the segment without a confirmed reservation"),
}


def run(name, kw, mutation=None):
    tracemalloc.start()
    t0 = time.time()
    r = M.check(M.Model(mutation=mutation, **kw), max_seconds=420)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    r["peak_mb_traced"] = round(peak / 2 ** 20, 1)
    r["seconds"] = round(time.time() - t0, 2)
    traces = {k: r.pop(k) for k in ("counterexample", "deadlock_trace", "liveness_trace") if k in r}
    if traces:
        os.makedirs(TRACES, exist_ok=True)
        tag = f"{name}{'_' + mutation if mutation else ''}"
        for k, tr in traces.items():
            p = os.path.join(TRACES, f"{tag}_{k}.json")
            with open(p, "w", encoding="utf-8", newline="\n") as f:
                json.dump(tr, f, indent=1)
                f.write("\n")
            r[k + "_file"] = os.path.relpath(p, ROOT).replace("\\", "/")
            r[k + "_length"] = len(tr)
    return r


def main():
    out = {"note": __doc__.split("\n\n")[1].strip(), "step_s": round(M.T_STEP, 3), "cell_m": M.CELL,
           "models": {}, "mutations": {}}
    for name, kw in MODELS.items():
        r = run(name, kw)
        r["passes"] = (r["violating_states"] == 0 and r.get("deadlock_states", 1) == 0
                       and r.get("cannot_reach_goal", 1) == 0 and r.get("livelock_sccs", 1) == 0 and not r["aborted"])
        out["models"][name] = r
        print(name, {k: r[k] for k in ("states", "violating_states", "deadlock_states", "cannot_reach_goal",
                                       "K_max_steps_to_goal", "livelock_sccs", "seconds", "peak_mb_traced", "passes")
                     if k in r}, flush=True)
    for mut, (name, expect) in MUTATIONS.items():
        r = run(name, MODELS[name], mutation=mut)
        found = r["violating_states"] > 0 or r.get("deadlock_states", 0) > 0 or r.get("cannot_reach_goal", 0) > 0
        r["counterexample_found"] = bool(found)
        r["expected"] = expect
        out["mutations"][mut] = dict(model=name, **r)
        print("mutation", mut, "found" if found else "NOT FOUND", {k: r[k] for k in ("states", "violating_states",
              "deadlock_states", "cannot_reach_goal") if k in r}, flush=True)
    out["all_models_pass"] = all(m["passes"] for m in out["models"].values())
    out["all_mutations_caught"] = all(m["counterexample_found"] for m in out["mutations"].values())
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print("all models pass:", out["all_models_pass"], "| all mutations caught:", out["all_mutations_caught"])


if __name__ == "__main__":
    main()
