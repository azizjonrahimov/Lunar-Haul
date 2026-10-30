"""Outcome-neutrality evidence for the cargo-id fix (B-79 batch 2, D8 "cargo ids unique").

    python tools/atc/check_id_fix.py run --tag pre  [--max-seconds 480]   # before the engine fix (resumable)
    python tools/atc/check_id_fix.py run --tag post [--max-seconds 480]   # after it
    python tools/atc/check_id_fix.py compare                              # -> results/id_fix_evidence.json

Runs: every E40 regime label at 30 % load and E43's three road modes at 1x (2028), seeds 1-3, a full year each,
with dispatch to a fixed point as the experiments' reruns. Each run is reduced to a content digest of every item
(owner, mass, origin, destination, ready time, class, pickup, delivery, carrier, team size), which does not use the
cargo id, plus the count of reused ids.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import warnings
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5")):
    if p not in sys.path:
        sys.path.insert(0, p)

CACHE = os.path.join(ROOT, ".cache", "atc", "id_fix")
OUT = os.path.join(ROOT, "results", "id_fix_evidence.json")
SEEDS = (1, 2, 3)


def cells():
    import run_phase5 as RP
    out = [c for c in RP.e40_cells() if c["tag"]["load"] == 30 and not c["tag"].get("hopper_refuel")]
    out += [c for c in RP.e43_cells() if c["tag"]["density"] == 1 and c["block"].startswith("y2028")
            and c["tag"]["label"] in ("none x1", "atc x1", "uncoordinated x1")]
    return out


def run_cell(c, seed):
    import numpy as np
    import run_phase5 as RP
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    from lunarsim.config import load_scenario
    if c.get("build"):
        from lunarsim.atc import p5 as P5
        b = c["build"]
        m = int(b["m"])
        sc = P5.build("3eq", k=RP.E43_K30 * m, team_lift_share=0.10)
        sc = sc.with_(fleet=list(sc.fleet) * m, n_operators=sc.n_operators * m)
        if b["horizon"]:
            sc = sc.with_(horizon_h=float(b["horizon"]))
        if b["roads"]:
            sc = sc.with_(p5=dict(sc.p5, roads=dict(b["roads"])), plume=dict(RP.E43_PLUME))
        year = 2028
    else:
        sc = load_scenario(c["scen"])
        year = RP.start_year(seed)
    sc = sc.with_(p5=dict(sc.p5, dispatch_fixpoint=True))
    kw = dict(c["kw"])
    kw["start_year"] = year
    t0 = time.time()
    sim = Simulation(sc, G.mechanism(c["regime"]), seed=seed, mech_kwargs=kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sim.run()
    rec = sorted((c_.owner, round(c_.mass_kg, 6), c_.origin, c_.dest, round(c_.t_ready, 6), c_.cls,
                  None if c_.t_picked is None else round(c_.t_picked, 6),
                  None if c_.t_delivered is None else round(c_.t_delivered, 6), c_.carrier, c_.team_size)
                 for c_ in sim.all_cargo)
    reused = sum(n - 1 for n in Counter(x.id for x in sim.all_cargo).values() if n > 1)
    return {"label": c["tag"]["label"], "exp": c["tag"]["exp"], "seed": seed, "year": year,
            "digest": hashlib.md5(json.dumps(rec, default=str).encode()).hexdigest(), "items": len(rec),
            "ids_reused": reused, "run_s": round(time.time() - t0, 1)}


def cmd_run(tag, max_s):
    t0 = time.time()
    d = os.path.join(CACHE, tag)
    os.makedirs(d, exist_ok=True)
    est = 20.0
    for c in cells():
        for s in SEEDS:
            p = os.path.join(d, hashlib.md5(f"{c['key']}|{s}".encode()).hexdigest()[:16] + ".json")
            if os.path.isfile(p):
                continue
            if time.time() - t0 + 1.5 * est > max_s:
                print("time limit; rerun", flush=True)
                return False
            r = run_cell(c, s)
            est = max(est * 0.7, r["run_s"])
            with open(p + ".tmp", "w", encoding="utf-8") as f:
                json.dump(r, f)
            os.replace(p + ".tmp", p)
            print(r["label"], s, r["run_s"], "s", r["ids_reused"], "reused", flush=True)
    print("done")
    return True


def cmd_compare():
    res = {}
    for tag in ("pre", "post"):
        d = os.path.join(CACHE, tag)
        res[tag] = {(r["label"], r["seed"]): r for r in (json.load(open(os.path.join(d, f))) for f in os.listdir(d)
                                                       if f.endswith(".json"))}
    keys = sorted(set(res["pre"]) & set(res["post"]))
    rows = [{"label": k[0], "seed": k[1], "exp": res["pre"][k]["exp"], "items": res["pre"][k]["items"],
             "ids_reused_pre": res["pre"][k]["ids_reused"], "ids_reused_post": res["post"][k]["ids_reused"],
             "identical": res["pre"][k]["digest"] == res["post"][k]["digest"]} for k in keys]
    doc = {"what": "content digest of every item (no cargo ids) before and after the cargo-id fix",
           "runs": len(rows), "identical": sum(r["identical"] for r in rows),
           "ids_reused_pre": sum(r["ids_reused_pre"] for r in rows),
           "ids_reused_post": sum(r["ids_reused_post"] for r in rows), "rows": rows}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print({k: doc[k] for k in ("runs", "identical", "ids_reused_pre", "ids_reused_post")})
    for r in rows:
        if not r["identical"]:
            print("DIFFERS", r)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "compare"])
    ap.add_argument("--tag", choices=["pre", "post"])
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 100, exit=True)
    if a.cmd == "run":
        cmd_run(a.tag, a.max_seconds)
    else:
        cmd_compare()
