"""B-117 (f) reduced, P3 M7/S17: E46's value of time swept, for H5 clause 3 only.

    python tools/atc/b117f_e46_vot.py run      # resumable (--max-seconds 500); parts in .cache/atc/e46_vot/x<level>/
    python tools/atc/b117f_e46_vot.py table    # -> results/E46_vot_sweep.json (a new file)

E46 (tools/atc/run_e46.py) prices delay with one value of time (Scenario.vot_usd_per_h: priority 1 5,000, 2 1,000, 3
100 USD/h). Here the whole table is scaled by x0.2, x0.5, x2 and x5 (levels fixed in the B-117 estimate, 13 Nov,
before any row). The scaled values enter both the dispatch (the bids' value-of-time term, dispatch._bid) and the
shippers' delay cost, so each level needs new physical runs. Reduced design (no deviations, so H5 clause 3 only):
per split (3eq, 3uneq) and seed (1-30), the pooled market, the three two-owner coalitions, owners alone (A_MOON) and
the marketplace (O_ORACLE, for the efficiency loss), each exactly as run_e46.run_one runs them (dispatch fixed point,
loss 0, start year 2028, private costs eps by seed). Clause 3 as run_e46.cmd_analyse computes it: for every owner in
every coalition, the Shapley payoff in the coalition minus its value alone (v(S) = -(true carrier costs + delay costs
of S's cargo) in S's own run), bootstrap over seeds (run_e46._boot); supported iff the smallest upper bound >= 0.
Check: the x1 level is E46's own parts (results/E46_parts); one pooled x1 run per split is repeated and must equal its
stored part, and clause 3 recomputed from the stored parts must equal results/E46_fit.json.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import run_e46 as E  # noqa: E402

LEVELS = (0.2, 0.5, 2.0, 5.0)
CACHE = os.path.join(ROOT, ".cache", "atc", "e46_vot")
OUT = os.path.join(ROOT, "results", "E46_vot_sweep.json")
KINDS = [("pooled", None), ("pair", ("A", "B")), ("pair", ("A", "C")), ("pair", ("B", "C")), ("alone", None),
         ("oracle", None)]
_ORIG_SCENARIO = E.scenario
STOP_MB = 350          # LEAD (15 Nov): stop a chunk, keeping its finished runs, when free memory falls below this


def _free_mb():
    """Free physical memory in MB (Windows; a large number elsewhere, so the check never stops a run there)."""
    try:
        import ctypes

        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong)] + \
                       [(n, ctypes.c_ulonglong) for n in ("tp", "ap", "tpf", "apf", "tv", "av", "aev")]
        m = MS()
        m.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return m.ap / 2 ** 20
    except Exception:
        return 1e9


def _scaled(level):
    def scenario(split, members=None):
        sc = _ORIG_SCENARIO(split, members)
        return sc.with_(vot_usd_per_h={p: float(v) * level for p, v in sc.vot_usd_per_h.items()})
    return scenario


def _path(level, split, seed, kind, members):
    tag = "pair_" + "".join(members) if kind == "pair" else kind
    return os.path.join(CACHE, f"x{level:g}", f"{split}_s{seed:03d}_{tag}.json.gz")


def code():
    import run_e50 as E5
    return E5.code_fingerprint()


def cmd_run(max_s):
    t0, est = time.time(), 10.0
    fp = code()
    # check first: one pooled x1 run per split equals its stored part
    for split in E.DESIGN_DOC["splits"]:
        p = os.path.join(CACHE, f"check_x1_{split}.json")
        if os.path.isfile(p):
            continue
        E.scenario = _ORIG_SCENARIO
        r = E.run_one(split, 1, "pooled")
        stored = json.load(gzip.open(E._name(split, 1, "pooled", None, 1.0, None), "rt"))
        same = {k: r[k] == stored[k] for k in ("owners", "jobs", "delivered_share")}
        os.makedirs(CACHE, exist_ok=True)
        json.dump({"code": fp, "equal": same}, open(p, "w"))
        print(f"check x1 {split} seed 1 pooled: {same}", flush=True)
        if not all(same.values()):
            raise SystemExit("the x1 pooled run differs from E46's stored part; stopping")
    n = 0
    for level in LEVELS:
        E.scenario = _scaled(level)
        for split in E.DESIGN_DOC["splits"]:
            for seed in E.DESIGN_DOC["seeds"]:
                for kind, members in KINDS:
                    p = _path(level, split, seed, kind, members)
                    if os.path.isfile(p):
                        continue
                    if _free_mb() < STOP_MB:
                        print(f"run: free memory below {STOP_MB} MB after {n} new runs; stopped", flush=True)
                        E.scenario = _ORIG_SCENARIO
                        return False
                    if time.time() - t0 + 2.0 * est > max_s:
                        print(f"run: time limit after {n} new runs; rerun", flush=True)
                        E.scenario = _ORIG_SCENARIO
                        return False
                    r = E.run_one(split, seed, kind, None, 1.0, members)
                    r["vot_level"], r["code"] = level, fp
                    os.makedirs(os.path.dirname(p), exist_ok=True)
                    with gzip.open(p + ".tmp", "wt", encoding="utf-8") as f:
                        json.dump(r, f, separators=(",", ":"))
                    os.replace(p + ".tmp", p)
                    est = max(est * 0.5, r["run_s"]) if n else r["run_s"]
                    n += 1
    E.scenario = _ORIG_SCENARIO
    print(f"run: done ({n} new runs)", flush=True)
    return True


def clause3(load):
    """H5 clause 3 per split from runs load(split, seed, kind, members) (run_e46.cmd_analyse's computation)."""
    out = {}
    for split in E.DESIGN_DOC["splits"]:
        rows, effs = [], []
        V = {}
        for s in E.DESIGN_DOC["seeds"]:
            alone = load(split, s, "alone", None)
            v = {frozenset(): 0.0}
            for o in E.OWNERS:
                v[frozenset([o])] = E.owner_value(alone, o)
            for pr in itertools.combinations(E.OWNERS, 2):
                v[frozenset(pr)] = E.coalition_value(load(split, s, "pair", pr), pr)
            pooled = load(split, s, "pooled", None)
            v[frozenset(E.OWNERS)] = E.coalition_value(pooled, E.OWNERS)
            V[s] = v
            orc = load(split, s, "oracle", None)
            if orc is not None:
                vo = E.coalition_value(orc, E.OWNERS)
                effs.append(100.0 * (vo - v[frozenset(E.OWNERS)]) / abs(vo))    # system cost above the oracle's, %
        for coal in [c for r in (2, 3) for c in itertools.combinations(E.OWNERS, r)]:
            for o in coal:
                d = []
                for s, v in V.items():
                    sub = {frozenset(S): v[frozenset(S)] for r in range(len(coal) + 1) for S in itertools.combinations(coal, r)}
                    d.append(E.shapley(sub, coal)[o] - v[frozenset([o])])
                rows.append({"coalition": "".join(coal), "owner": o, **E._boot(d)})
        ups = [r["hi"] for r in rows if r["hi"] is not None]
        los = [r["lo"] for r in rows if r["lo"] is not None]
        out[split] = {"supported": bool(ups) and min(ups) >= 0, "min_upper": min(ups), "min_lower": min(los),
                      "all_lower_bounds_above_0": min(los) > 0,
                      "grand_coalition_value_usd_mean": float(np.mean([v[frozenset(E.OWNERS)] for v in V.values()])),
                      "efficiency_loss_vs_oracle_pct_mean": float(np.mean(effs)) if effs else None, "rows": rows}
    return out


def cmd_table():
    fp = code()
    checks = {sp: json.load(open(os.path.join(CACHE, f"check_x1_{sp}.json"))) for sp in E.DESIGN_DOC["splits"]}
    if not all(all(c["equal"].values()) and c["code"] == fp for c in checks.values()):
        raise SystemExit(f"x1 check failed or made with other code: {checks}")

    def stored(split, seed, kind, members):
        p = E._name(split, seed, kind, None, 1.0, members)
        return json.load(gzip.open(p, "rt")) if os.path.isfile(p) else None
    x1 = clause3(stored)
    fit = json.load(open(os.path.join(ROOT, "results", "E46_fit.json"), encoding="utf-8"))
    rep = {sp: abs(x1[sp]["min_upper"] - fit["H5"][sp]["clause3"]["min_upper"]) < 1e-6
           and abs(x1[sp]["min_lower"] - fit["H5"][sp]["clause3"]["min_lower"]) < 1e-6 for sp in x1}
    if not all(rep.values()):
        raise SystemExit(f"clause 3 recomputed from E46's parts differs from E46_fit.json: {rep}")
    out = {"task": "B-117 (f) reduced: E46's value of time swept, H5 clause 3", "note": __doc__.split("\n\n")[1].strip(),
           "code": fp, "levels": [1.0] + list(LEVELS),
           "vot_usd_per_h_x1": {"1": 5000.0, "2": 1000.0, "3": 100.0},
           "check": {"x1_pooled_seed1_equals_stored_part": {sp: checks[sp]["equal"] for sp in checks},
                     "x1_clause3_reproduces_E46_fit": rep},
           "clause3": {"x1": x1}}
    for level in LEVELS:
        def load(split, seed, kind, members, _l=level):
            p = _path(_l, split, seed, kind, members)
            if not os.path.isfile(p):
                raise SystemExit(f"missing {p}; run first")
            r = json.load(gzip.open(p, "rt"))
            if r["code"] != fp:
                raise SystemExit(f"{p} made with other code; rerun")
            return r
        out["clause3"][f"x{level:g}"] = clause3(load)
    out["supported_at_every_level"] = all(v[sp]["supported"] for v in out["clause3"].values() for sp in v)
    text = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with open(OUT + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(OUT + ".tmp", OUT)
    for lev, v in out["clause3"].items():
        print(lev, {sp: (x["supported"], round(x["min_lower"] / 1e6, 2), round(x["min_upper"] / 1e6, 2),
                         round(x["efficiency_loss_vs_oracle_pct_mean"], 2) if x["efficiency_loss_vs_oracle_pct_mean"] is not None else None)
                    for sp, x in v.items()})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "table"])
    ap.add_argument("--max-seconds", type=float, default=500.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 120, exit=True)
    cmd_run(a.max_seconds) if a.cmd == "run" else cmd_table()
