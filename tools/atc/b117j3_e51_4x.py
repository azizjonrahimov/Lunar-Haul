"""B-117 (j3), P3 S17: E51 (clock quality, H11) at 4x fleet, 10 seeds.

    python tools/atc/b117j3_e51_4x.py run --seeds 1-10   # resumable, one file per seed (.cache/atc/e51_m4)
    python tools/atc/b117j3_e51_4x.py table              # -> results/E51_clocks_m4.json, E51_table_m4.csv,
                                                         #    E51b_clocks_m4.json, E51b_table_m4.csv (new files)

E51 (tools/atc/run_e51.py) ran at 1x (8 vehicles, 30 seeds). Here the same code and design (run_e51.run_seed and
run_e51.build) with E50's 4x fleet (32 vehicles; run_e50.record with fleet multiple 4, as E50's own 4x cells), seeds
1-10 (E50's 4x seeds). The only change is the multiple passed to run_e50.record; each seed file is stamped with E50's
code fingerprint, and its perfect run's delay is checked against E50's cached 4x cell. run_e51's own output files are
not touched (build writes to the _m4 paths). Pre-declared in the B-117 estimate (13 Nov).
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import pickle
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import run_e50 as E5  # noqa: E402
import run_e51 as E51  # noqa: E402

MULT = 4
CACHE = os.path.join(ROOT, ".cache", "atc", "e51_m4")


def _paths():
    E51.CACHE = CACHE
    for k in ("OUT_JSON", "OUT_CSV", "OUT_JSON_B", "OUT_CSV_B"):
        p = getattr(E51, k)
        setattr(E51, k, p.replace(".json", "_m4.json").replace(".csv", "_m4.csv"))


def run_seed(seed):
    orig = E5.record
    seen = {}

    def rec4(m, s, t0, t1, **kw):
        r = orig(MULT, s, t0, t1, **kw)
        seen["delay"] = r["delay_mean_h"]
        return r
    E5.record = rec4
    try:
        o = E51.run_seed(seed)
    finally:
        E5.record = orig
    o["mult"] = MULT
    o["code"] = E5.code_fingerprint()
    p50 = os.path.join(E5.CACHE, f"m{MULT}_s{seed}.pkl.gz")
    with gzip.open(p50) as f:
        c = pickle.load(f)
    o["e50_reproduced"] = {"perfect_delay": c["perfect"]["delay_mean_h"] == seen["delay"], "e50_cell_code": c.get("code")}
    return o


def cmd_run(seeds, max_s):
    t0, last = time.time(), 300.0
    os.makedirs(CACHE, exist_ok=True)
    for s in seeds:
        p = os.path.join(CACHE, f"s{s}.json")
        if os.path.isfile(p):
            continue
        if time.time() - t0 + 1.25 * last > max_s:
            print(f"stop before seed {s}: time budget", flush=True)
            return
        ts = time.time()
        o = run_seed(s)
        last = time.time() - ts
        with open(p + ".tmp", "w", encoding="utf-8") as f:
            json.dump(o, f, allow_nan=True)
        os.replace(p + ".tmp", p)
        print(f"s{s} done in {last:.0f} s, reproduced {o['e50_reproduced']}", flush=True)
    print("all requested seeds done", flush=True)


def cmd_table():
    S = [json.load(open(p, encoding="utf-8")) for p in glob.glob(os.path.join(CACHE, "s[0-9]*.json"))]
    fp = E5.code_fingerprint()
    if sorted({s["code"] for s in S}) != [fp]:
        raise SystemExit(f"seed files with other code {sorted({s['code'] for s in S})} (current {fp}); rerun")
    bad = [s["seed"] for s in S if not s["e50_reproduced"]["perfect_delay"]]
    if bad:
        raise SystemExit(f"seeds whose perfect run differs from E50's 4x cell: {bad}")
    _paths()
    E51.build()
    d = json.load(open(E51.OUT_JSON, encoding="utf-8"))
    d["mult"] = MULT
    d["code"] = fp
    d["note_b117j3"] = (__doc__.split("\n\n")[1].strip() + " Perfect runs reproduce E50's 4x cells (delay equal) in "
                        f"all {len(S)} seeds.")
    with open(E51.OUT_JSON + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(d, indent=1, allow_nan=False, default=lambda x: None) + "\n")
    os.replace(E51.OUT_JSON + ".tmp", E51.OUT_JSON)
    print("->", E51.OUT_JSON, "H11 at 4x:", d["h11"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--seeds", default="1-10")
    ap.add_argument("--max-seconds", type=float, default=500.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 300, exit=True)
    if a.cmd == "run":
        lo, hi = (a.seeds.split("-") + [a.seeds])[:2]
        cmd_run(list(range(int(lo), int(hi) + 1)), a.max_seconds)
    else:
        cmd_table()
