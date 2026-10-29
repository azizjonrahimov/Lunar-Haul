"""B-77: is the opt-in consolidation-WAKE dedupe (Scenario.p5["wake_dedupe"], lunarsim/dispatch.py) result-neutral?

    python tools/atc/wake_check.py gate  [--max-seconds 480]   # rerun stored rows with the flag on; every column must match
    python tools/atc/wake_check.py audit [--max-seconds 480]   # flag on + debug: each skipped WAKE is pushed anyway, marked,
                                                               # and its dispatch call must assign nothing and change no state
    -> results/ATC_wake_check.json (resumable: rows already checked are kept)

The defect: the v2 marketplace's bulk consolidation hold pushes a WAKE for every held lane on every dispatch call, all at
the lane's deadline; each WAKE re-runs dispatch, which pushes again (geometric growth, 2.37 M WAKEs in a 21-day 8x run).
The dedupe keeps one pending WAKE per (lane, oldest lot). A skipped WAKE would only have re-run dispatch at the same
instant as one that still runs, and the other events keep their relative order, so the flag is result-neutral iff such a
repeated call assigns nothing. This tool tests that on stored rows (gate) and directly (audit); it is evidence, not proof.
"""
from __future__ import annotations

import argparse
import io
import json
import math
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5")):
    if p not in sys.path:
        sys.path.insert(0, p)
import run_phase5 as R  # noqa: E402
from lunarsim import engine as E  # noqa: E402

OUT = os.path.join(ROOT, "results", "ATC_wake_check.json")
# gate: (experiment, cell index, rows) - E40 one cell per regime at 30 % (A_EARTH strict and C_AUCTION included), two E42
# cells (C_AUCTION, loss 0.1, team 0 and the last cell), the E43 1x atc and uncoordinated cells
GATE = ([("E40", i, 4) for i in (12, 14, 15, 17, 19, 20, 21, 22, 23)] + [("E42", 1, 4), ("E42", -1, 4)]
        + [("E43", 1, 5), ("E43", 2, 5)])
AUDIT = [("E43", 1, 1), ("E40", 20, 1)]
SKIP_COLS = {"run_s", "wake_dedupe", "wake_skipped"}
KEY_METRICS = ("atc_urgent_wait_mean_cens_h", "delay_mean_h", "delay_mean_bulk", "delivered_kg", "atc_calls")

_orig_init = E.Simulation.__init__
_MODE = {"on": False, "debug": False}


def _init(self, *a, **k):
    _orig_init(self, *a, **k)
    if _MODE["on"]:
        self.wake_pending = {}
        self.wake_debug = _MODE["debug"]


E.Simulation.__init__ = _init


def stored(exp: str) -> pd.DataFrame:
    return R.load_runs(exp)


def rows_for(exp: str, idx: int, n: int, df: pd.DataFrame):
    cells = R.EXPS[exp]()
    c = cells[idx]
    g = df[df["cell"] == c["key"]].sort_values(["start_year", "seed"]).head(n)
    return c, g


def as_csv_row(row: dict) -> pd.Series:
    """The row as the run files store it (written and read back the way load_runs reads them)."""
    buf = io.StringIO(pd.DataFrame([row]).to_csv(index=False, lineterminator="\n"))
    return pd.read_csv(buf, float_precision="round_trip").iloc[0]


def same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float) and math.isnan(a) and math.isnan(b):
        return True
    try:
        if pd.isna(a) and pd.isna(b):
            return True
    except (TypeError, ValueError):
        pass
    return a == b or (str(a) == str(b))


def load_out() -> dict:
    if os.path.isfile(OUT):
        return json.load(open(OUT, encoding="utf-8"))
    return {"note": __doc__.split("\n\n")[1].strip() + " " + __doc__.split("\n\n")[2].strip(),
            "gate": {}, "audit": {}}


def save_out(d: dict) -> None:
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(d, f, indent=1)
        f.write("\n")


def cmd_gate(max_s: float) -> bool:
    t0 = time.time()
    out = load_out()
    _MODE.update(on=True, debug=False)
    dfs = {}
    for exp, idx, n in GATE:
        dfs.setdefault(exp, stored(exp))
        c, g = rows_for(exp, idx, n, dfs[exp])
        for _, r in g.iterrows():
            k = f"{exp}|{c['tag']['label']}|{int(r['seed'])}|{int(r['start_year'])}"
            if k in out["gate"]:
                continue
            if time.time() - t0 > max_s - 60:
                save_out(out)
                print("gate: time limit; rerun")
                return False
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                new = run_one_flag(c, int(r["seed"]), int(r["start_year"]))
            nr = as_csv_row(new)
            cols = [x for x in r.index if x in nr.index and x not in SKIP_COLS]
            diff = [x for x in cols if not same(r[x], nr[x])]
            missing = [x for x in r.index if x not in nr.index and x not in SKIP_COLS and not pd.isna(r[x])]
            out["gate"][k] = {"columns": len(cols), "mismatched": diff[:20], "missing": missing[:20],
                              "identical": not diff and not missing, "wake_skipped": int(new.get("wake_skipped", 0)),
                              "run_s": new["run_s"], "stored_run_s": float(r["run_s"]),
                              "new_minus_stored": {m: float(nr[m]) - float(r[m]) for m in KEY_METRICS
                                                   if m in nr.index and m in r.index and not pd.isna(r[m])}}
            print(f"  {k}: {'identical' if not diff and not missing else 'MISMATCH ' + str(diff[:5] + missing[:5])}"
                  f" (skipped {new.get('wake_skipped', 0)} wakes, {new['run_s']} s)", flush=True)
            save_out(out)
    g = out["gate"].values()
    out["gate_summary"] = {"rows": len(g), "identical": sum(v["identical"] for v in g),
                           "wakes_skipped": sum(v["wake_skipped"] for v in g)}
    save_out(out)
    print("gate:", out["gate_summary"])
    return True


def run_one_flag(c, seed, year):
    return R.run_one(c, seed, year)


def _snap(sim):
    def simple(d):
        return {k: v for k, v in d.items() if isinstance(v, (int, float, str, bool, type(None)))}
    veh = [simple(vars(v)) for v in sim.vehicles]
    ev = sorted((t, kind) for t, _, kind, _ in sim.events if kind != "WAKE")
    s = {"vehicles": veh, "waiting": [id(c) for c in sim.waiting], "pending": len(sim.pending),
         "metrics": simple(vars(sim.metrics)), "rng": [str(sim.rng.bit_generator.state), str(sim.rng_ops.bit_generator.state)],
         "events": ev, "op_jobs": list(getattr(sim, "op_jobs", [])), "t": sim.t}
    if getattr(sim, "atc", None) is not None:       # the regime's counters, less the per-call ones (they count calls)
        s["atc"] = {k: v for k, v in sim.atc.m.items() if k not in ("calls", "gated_calls")}
    return s


def cmd_audit(max_s: float) -> None:
    out = load_out()
    _MODE.update(on=True, debug=True)
    dfs = {}
    for exp, idx, n in AUDIT:
        dfs.setdefault(exp, stored(exp))
        c, g = rows_for(exp, idx, n, dfs[exp])
        r = g.iloc[0]
        k = f"{exp}|{c['tag']['label']}|{int(r['seed'])}|{int(r['start_year'])}"
        if k in out["audit"]:
            continue
        last = {"payload": None}
        real_pop = E.heapq.heappop

        class _HQ:
            heappush = staticmethod(E.heapq.heappush)

            @staticmethod
            def heappop(h):
                item = real_pop(h)
                last["payload"] = item[3]
                return item

        stats = {"dup_calls": 0, "violations": 0, "examples": []}
        real_dispatch = E.Simulation._dispatch

        def audited(self):
            if last["payload"] != "dup":
                return real_dispatch(self)
            stats["dup_calls"] += 1
            a = _snap(self)
            n0 = self._seq
            real_dispatch(self)
            b = _snap(self)
            if a != b:
                stats["violations"] += 1
                keys = [x for x in a if a[x] != b[x]]
                if keys != ["atc"]:
                    stats["non_atc"] = stats.get("non_atc", 0) + 1
                ak = sorted(x for x in set(a.get("atc", {})) | set(b.get("atc", {}))
                            if a.get("atc", {}).get(x) != b.get("atc", {}).get(x))
                stats.setdefault("atc_keys", {})
                for x in ak:
                    stats["atc_keys"][x] = stats["atc_keys"].get(x, 0) + 1
                if len(stats["examples"]) < 3:
                    stats["examples"].append({"t": self.t, "keys": keys, "pushed": self._seq - n0,
                                              "atc": {x: [a.get("atc", {}).get(x), b.get("atc", {}).get(x)] for x in ak}})

        E.heapq = _HQ
        E.Simulation._dispatch = audited
        try:
            t0 = time.time()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                new = R.run_one(c, int(r["seed"]), int(r["start_year"]))
        finally:
            E.heapq = __import__("heapq")
            E.Simulation._dispatch = real_dispatch
        nr = as_csv_row(new)
        cols = [x for x in r.index if x in nr.index and x not in SKIP_COLS]
        diff = [x for x in cols if not same(r[x], nr[x])]
        out["audit"][k] = {"dup_calls_audited": stats["dup_calls"], "violations": stats["violations"],
                           "violations_outside_atc_counters": stats.get("non_atc", 0),
                           "atc_counters_changed": stats.get("atc_keys", {}),
                           "examples": stats["examples"], "wake_skipped_counted": int(new.get("wake_skipped", 0)),
                           "row_matches_stored": not diff, "mismatched": diff[:20], "run_s": round(time.time() - t0, 1)}
        print(f"  audit {k}: {stats['dup_calls']} duplicate calls, {stats['violations']} changed state; "
              f"row {'matches' if not diff else 'MISMATCH ' + str(diff[:5])}", flush=True)
        save_out(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gate", "audit"])
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    if a.cmd == "gate":
        cmd_gate(a.max_seconds)
    else:
        cmd_audit(a.max_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
