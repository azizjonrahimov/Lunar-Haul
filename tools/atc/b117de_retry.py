"""B-117 (d) and (e1), P2 M7 and P3 S9/S17: E54's drop-and-retry with other retry budgets.

    python tools/atc/b117de_retry.py run --seeds 1-30   # resumable, one cache file per seed (.cache/atc/e54_retry)
    python tools/atc/b117de_retry.py table              # -> results/E54_retry_budget.json (a new file)

E54 (tools/atc/run_e54.py) ran drop-and-retry with one budget, a try every 180 s and at most 5 tries (dtn.DEFAULTS
retry_s, max_tries; our choice, not the registration's). Here the same replay (the seed's engine run, contact plan,
messages and random stream as run_e54: rng [seed, 94, loss x 100, 0]) with tries {1, 3, 5, 10} x retry interval
{20, 60, 180 s} at loss 0.10, 0.25 and 0.40, 30 seeds. (d) is 3 tries every 20 s, all inside a grant's 60 s lifetime.
The published budget (5, 180 s) is one of the twelve and must reproduce E54's drop_retry cells exactly (a check; the
table refuses otherwise). Every budget runs on the same random stream (common random numbers). Age of information is
not recomputed (it uses STATUS beacons, not the retry budget). H14's comparison is repeated per budget: lost jobs
(expired awards) sf_ll minus drop_retry at loss 0.25, paired by seed against E54's cached sf_ll cells (run_e54's
bootstrap, _boot). Pre-declared in the B-117 estimate (13 Nov).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import run_e54 as E4  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "e54_retry")
OUT = os.path.join(ROOT, "results", "E54_retry_budget.json")
TRIES = (1, 3, 5, 10)
RETRY_S = (20.0, 60.0, 180.0)
PUBLISHED = (5, 180.0)
KINDS = ("award", "grant", "task_state", "ledger_earth")


def code():
    """E54's fingerprint plus this file's own replay (AST, no docstrings)."""
    import hashlib
    import inspect
    own = "".join(E4._ast_digest(inspect.getsource(f)) for f in (prepare, replay_seed))
    return E4.code_fingerprint() + "+" + hashlib.sha256(own.encode()).hexdigest()[:12]


def prepare(seed):
    """run_e54.prepare without the lost-link plans and the stuck count (not used by drop_retry)."""
    import run_e50 as E5
    from lunarsim.atc import dtn as DT
    month, t0h, t1h, share = E5._window()
    rec = E4.record(seed, t0h, t1h)
    tr = E5.trajectories(rec, t0h, t1h)
    g = E5._geo()
    A = DT.contact_plan(tr, g["los"], g["ids"]["BASE"])
    return {"rec": rec, "tr": tr, "t0h": t0h, "t1h": t1h, "N": A.shape[1] - 1,
            "vid_col": {int(v): n for n, v in enumerate(tr.ids)}, "A": A, "eu": E4.earth_up_fn(t0h, t1h, tr.dt_s)}


def replay_seed(seed, ctx):
    from lunarsim.atc import dtn as DT
    msgs = E4.messages(ctx["rec"], ctx["t0h"], ctx["t1h"], ctx["N"], ctx["vid_col"])
    eu = ctx["eu"]
    cells = []
    for loss in E4.LOSSES:
        for tries in TRIES:
            for retry_s in RETRY_S:
                rng = np.random.default_rng([seed, 94, int(loss * 100), 0])     # run_e54's drop_retry stream
                res = DT.simulate(ctx["A"], msgs, "drop_retry", loss, rng, ctx["tr"].dt_s,
                                  {"max_tries": tries, "retry_s": retry_s},
                                  earth_up=lambda k: bool(eu[min(k, len(eu) - 1)]))
                by = defaultdict(lambda: {"n": 0, "lost": 0, "censored": 0, "delay": []})
                for m in res:
                    b = by[m.kind]
                    b["n"] += 1
                    if m.t_done is None:
                        b["censored" if m.censored else "lost"] += 1
                    else:
                        b["delay"].append(m.t_done - m.t0)
                cells.append({"loss": loss, "max_tries": tries, "retry_s": retry_s,
                              "kinds": {k: {"n": v["n"], "lost": v["lost"], "censored": v["censored"],
                                            "delay_mean_s": float(np.mean(v["delay"])) if v["delay"] else None}
                                        for k, v in by.items()}})
    return cells


def cmd_run(seeds, max_s):
    t0, last = time.time(), 90.0
    os.makedirs(CACHE, exist_ok=True)
    fp = code()
    for s in seeds:
        p = os.path.join(CACHE, f"s{s}.json")
        if os.path.isfile(p):
            continue
        if time.time() - t0 + 1.3 * last > max_s:
            print(f"stop before seed {s}: time budget", flush=True)
            return
        ts = time.time()
        cells = replay_seed(s, prepare(s))
        last = time.time() - ts
        E4._write_cache(p, {"seed": s, "code": fp, "cells": cells, "run_s": round(last, 1)})
        print(f"s{s} done in {last:.0f} s", flush=True)
    print("all requested seeds done", flush=True)


def cmd_table():
    fp = code()
    files = sorted(glob.glob(os.path.join(CACHE, "s[0-9]*.json")), key=lambda p: int(os.path.basename(p)[1:-5]))
    R = [json.load(open(p, encoding="utf-8")) for p in files]
    bad = sorted({r["code"] for r in R} - {fp})
    if bad:
        raise SystemExit(f"retry cache made with other code {bad} (current {fp}); rerun")
    S = E4._load_cache(os.path.join(E4.CACHE, "s[0-9]*.json"))                 # E54's cells, current code only
    seeds = [r["seed"] for r in R]
    if seeds != [s["seed"] for s in S]:
        raise SystemExit(f"retry seeds {seeds} != E54 seeds {[s['seed'] for s in S]}")
    cell = lambda r, loss, t, rs: next(c for c in r["cells"] if c["loss"] == loss and c["max_tries"] == t
                                       and c["retry_s"] == rs)
    e54 = lambda s, loss, proto: next(c for c in s["cells"] if c["loss"] == loss and c["protocol"] == proto)
    # check: the published budget reproduces E54's drop_retry cells (n, lost, censored per kind)
    mism = []
    for r, s in zip(R, S):
        for loss in E4.LOSSES:
            a, b = cell(r, loss, *PUBLISHED)["kinds"], e54(s, loss, "drop_retry")["kinds"]
            for k in KINDS:
                if k in a or k in b:
                    x = {f: a.get(k, {}).get(f) for f in ("n", "lost", "censored", "delay_mean_s")}
                    y = {f: b.get(k, {}).get(f) for f in ("n", "lost", "censored", "delay_mean_s")}
                    if x != y:
                        mism.append((r["seed"], loss, k, x, y))
    if mism:
        raise SystemExit(f"the published budget does not reproduce E54's drop_retry cells: {mism[:3]}")
    rows = []
    for loss in E4.LOSSES:
        for t in TRIES:
            for rs in RETRY_S:
                cs = [cell(r, loss, t, rs) for r in R]
                row = {"loss": loss, "max_tries": t, "retry_s": rs, "seeds": len(cs),
                       "gives_up_after_s": (t - 1) * rs, "published_budget": (t, rs) == PUBLISHED}
                for k in KINDS:
                    g = lambda f: sum(c["kinds"].get(k, {}).get(f, 0) for c in cs)
                    n = g("n")
                    row[f"{k}_n"], row[f"{k}_lost"], row[f"{k}_censored"] = n, g("lost"), g("censored")
                    row[f"{k}_lost_share"] = round(g("lost") / n, 5) if n else None
                rows.append(row)
    h14 = {}
    for i, (t, rs) in enumerate([(t, rs) for t in TRIES for rs in RETRY_S]):
        dr = [cell(r, 0.25, t, rs)["kinds"].get("award", {}).get("lost", 0) for r in R]
        ll = [e54(s, 0.25, "sf_ll")["kinds"].get("award", {}).get("lost", 0) for s in S]
        d = E4._boot([b - a for a, b in zip(dr, ll)], 3)
        h14[f"{t} tries, {rs:g} s"] = {"lost_jobs_drop_retry_per_seed": E4._boot(dr, 1)["mean"],
                                      "lost_jobs_sf_ll_per_seed": E4._boot(ll, 2)["mean"],
                                      "difference_sf_ll_minus_drop_retry": d,
                                      "clause_1_ci_below_0": bool(d["ci"][1] < 0)}
    out = {"task": "B-117 (d) and (e1): E54 drop-and-retry at twelve retry budgets",
           "note": __doc__.split("\n\n")[1].strip(), "seeds": seeds, "code": fp, "e54_code": S[0]["code"],
           "published_budget": {"max_tries": PUBLISHED[0], "retry_s": PUBLISHED[1],
                                "reproduces_E54_drop_retry_cells": True},
           "d_three_tries_inside_grant_lifetime": {"max_tries": 3, "retry_s": 20.0,
                                                   "rows": [r for r in rows if r["max_tries"] == 3 and r["retry_s"] == 20.0]},
           "rows": rows, "h14_by_budget_loss_0.25": h14,
           "run_s_total": round(sum(r["run_s"] for r in R), 1)}
    text = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with open(OUT + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(OUT + ".tmp", OUT)
    print(json.dumps({k: v for k, v in out.items() if k not in ("rows",)}, indent=1)[:4000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--seeds", default="1-30")
    ap.add_argument("--max-seconds", type=float, default=500.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    if a.cmd == "run":
        lo, hi = (a.seeds.split("-") + [a.seeds])[:2]
        cmd_run(list(range(int(lo), int(hi) + 1)), a.max_seconds)
    else:
        cmd_table()
