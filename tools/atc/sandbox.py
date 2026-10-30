"""B-83: one full-length encounter per E44 type for the site's encounter sandbox (F-54).

    python tools/atc/sandbox.py      # -> data/atc/encounter_sandbox/T<k>_*.json.gz + index.json

Each encounter is an E44 encounter (named by batch and index in index.json), chosen to show its type's event, and
re-simulated alone to its end: once with the safety program and once with it bypassed (a = a_prop, the page's
"safety program off"). Encounters without a random fuzzer and without message loss reproduce their E44 row exactly
(checked and recorded per file); a fuzzer or a lossy radio draws from a batch-shaped random stream, so those
(type 12, type 8) are re-simulated with their own draws and carry their own outcome. Per step: t, s, v, a_prop, a,
rule (MoveVerdict.rule: 0 none, 1 R1, 2 R2, 3 stop line, 5 R5, 6 R6), modified, xy (2 decimals), crew; 'move' (the
safety_check inputs) every 20th step. Long encounters are thinned to at most MAX_STEPS stored steps (stride
recorded); the event steps are always kept.
"""
from __future__ import annotations

import glob
import gzip
import io
import json
import math
import os
import sys
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from lunarsim.atc import encounter as E, encounter_types as ET  # noqa: E402

OUT = os.path.join(ROOT, "data", "atc", "encounter_sandbox")
PARTS = os.path.join(ROOT, "results", "E44_parts")
MAX_STEPS = 1100
VIOL = ("viol_contact", "viol_gap", "viol_zone", "viol_crew", "viol_r3", "viol_slots")

# what each type's chosen encounter shows (selection rule on the E44 rows)
PICK = {
    1: ("leader brakes at maximum; followers stop behind it", lambda d: d[(d.drivable == 1) & (d.n_random == 0) & (d.finished == 1)]),
    2: ("head-on at a single-lane segment, passing bay", lambda d: d[(d.n_random == 0) & (d.finished == 1) & d.params.str.contains('"bay": true')]),
    3: ("overtaking with oncoming traffic before a single-lane segment", lambda d: d[(d.n_random == 0) & (d.finished == 1) & d.params.str.contains('"oncoming": true')]),
    4: ("four-way junction contention, tile reservations", lambda d: d[(d.n_random == 0) & (d.finished == 1) & d.params.str.contains('"n": 4')]),
    5: ("ring of single-lane segments: an R3 deadlock (one of the 386)", lambda d: d[(d.n_random == 0) & (d.deadlock == 1)]),
    6: ("landing closure: one of the four deadlocks (vehicle held at the zone line inside its crossing)", lambda d: d[(d.n_random == 0) & (d.deadlock == 1)]),
    7: ("crew emerging from behind an occluder", lambda d: d[(d.n_random == 0) & d.params.str.contains('"variant": "occluded"')]),
    8: ("message loss and a radio dropout during negotiation", lambda d: d[(d.n_random == 0) & (d.finished == 1)]),
    9: ("dead stop inside the segment: a follower loses the static margin (one of the 58)", lambda d: d[(d.n_random == 0) & (d.viol_gap > 0)]),
    10: ("speed mix with one adversarial owner", lambda d: d[(d.n_random == 0) & (d.finished == 1) & (d.n_adversarial > 0)]),
    11: ("pad apron contention, two slots", lambda d: d[(d.n_random == 0) & (d.finished == 1) & d.params.str.contains('"mult": 2')]),
    12: ("planner fuzzing: random and adversarial proposals", lambda d: d[(d.drivable == 1) & (d.n_random > 0)]),
}
EXTRA_T6 = ("landing closure: a vehicle inside the zone exits before the window", lambda d: d[(d.n_random == 0) &
            d.params.str.contains('"kind": "plain"') & d.params.str.contains('"R": 200.0') & (d.near_zone == 0)])


def _rows(k):
    return pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(PARTS, f"T{k:02d}_b*.csv.gz")))],
                     ignore_index=True)


def _spec(k, batch, idx):
    rng = np.random.default_rng([44, k, int(batch)])
    for _ in range(int(idx) + 1):
        sp = ET.build(k, rng)
    return sp


def _jsonable(x):
    if isinstance(x, dict):
        return {str(a): _jsonable(b) for a, b in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(y) for y in x]
    if isinstance(x, np.ndarray):
        return _jsonable(x.tolist())
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else round(float(x), 4)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    return x


def _spec_doc(sp):
    keys = ("paths", "v_class", "v0", "s0", "planner", "theta", "mu", "groups", "res_kind", "res_slots", "res_branched",
            "nodes", "loss", "link_down", "zone", "crew", "lead_brake", "fault_stop", "slip", "drift", "dwell",
            "priority", "t_max", "params", "weight", "merges", "occluders", "exit_keep_free", "stop_is_goal")
    return _jsonable({k: getattr(sp, k) for k in keys if hasattr(sp, k)})


def _run(sp, shield):
    b = E.Batch([sp])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        oc, tr = E.run_batch(b, np.random.default_rng(1), record=[0], shield=shield)
    nv = len(sp.paths)
    steps = tr[0]
    events = {i for i, st in enumerate(steps) if any(st["modified"][:nv])}
    stride = max(1, math.ceil(len(steps) / MAX_STEPS))
    keep = sorted(set(range(0, len(steps), stride)) | set(sorted(events)[:150]) | {len(steps) - 1})
    out = []
    for i in keep:
        st = steps[i]
        row = {"t": st["t"], "s": [round(x, 3) for x in st["s"][:nv]], "v": [round(x, 3) for x in st["v"][:nv]],
               "a_prop": [round(x, 4) for x in st["a_prop"][:nv]], "a": [round(x, 4) for x in st["a"][:nv]],
               "rule": st["rule"][:nv], "modified": [bool(x) for x in st["modified"][:nv]],
               "xy": [[round(c, 2) for c in p] for p in st["xy"][:nv]],
               "crew": [None if c is None else [round(c[0], 2), round(c[1], 2)] for c in st["crew"]]}
        if i % 20 == 0:
            row["move"] = _jsonable({k: (v[:nv] if isinstance(v, list) else v) for k, v in st["move"].items()})
        out.append(row)
    outcome = {"min_sep_m": _jsonable(oc.min_sep[0]), "min_crew_m": _jsonable(oc.min_crew[0]),
               "violations_by_kind": {f: int(getattr(oc, f)[0] > 0) for f in VIOL},
               "deadlock": bool(oc.deadlock[0]), "blocked_by_fault": bool(oc.blocked_by_fault[0]),
               "finished": bool(oc.finished[0]), "delay_s": _jsonable(oc.delay_s[0]), "t_end": _jsonable(oc.t_end[0]),
               "steps_total": len(steps), "stride": stride}
    return out, outcome


def main():
    os.makedirs(OUT, exist_ok=True)
    plan = [(k, *PICK[k]) for k in range(1, 13)] + [(6, *EXTRA_T6)]
    index = []
    for q, (k, what, sel) in enumerate(plan):
        d = _rows(k)
        cand = sel(d)
        if cand.empty:
            print(f"T{k}: no candidate for '{what}'")
            continue
        r = cand.iloc[0]
        sp = _spec(k, r.batch, r.idx)
        on, oc_on = _run(sp, True)
        off, oc_off = _run(sp, False)
        e44 = {"min_sep_m": _jsonable(r.min_sep), "violations_by_kind": {f: int(r[f]) for f in VIOL},
               "deadlock": int(r.deadlock), "finished": int(r.finished), "delay_s": _jsonable(r.delay_s)}
        same = (oc_on["violations_by_kind"] == e44["violations_by_kind"] and bool(e44["deadlock"]) == oc_on["deadlock"]
                and bool(e44["finished"]) == oc_on["finished"]
                and (e44["min_sep_m"] is None or oc_on["min_sep_m"] is None or abs(e44["min_sep_m"] - oc_on["min_sep_m"]) < 1e-3))
        doc = {"type": k, "title": E.TYPES[k], "shows": what, "e44": {"batch": int(r.batch), "idx": int(r.idx), "row": e44},
               "reproduces_e44_row": bool(same),
               "note": ("re-simulated alone; a random fuzzer or message loss draws its own random numbers here, so the "
                        "outcome is this run's" if not same else "identical to the E44 row"),
               "dt": E.DT, "vehicle": {"length": E.VEH_L, "width": E.VEH_W}, "spec": _spec_doc(sp),
               "rule_codes": {"0": "none", "1": "R1 keep distance", "2": "R2 speed", "3": "stop line (R3/R5/R10)",
                              "5": "R5 must exit", "6": "R6 crew"},
               "shield_on": {"outcome": oc_on, "steps": on}, "shield_off": {"outcome": oc_off, "steps": off}}
        name = f"T{k:02d}_{q:02d}.json.gz"
        with io.TextIOWrapper(gzip.GzipFile(os.path.join(OUT, name), "wb", mtime=0), encoding="utf-8") as f:
            json.dump(doc, f, separators=(",", ":"))
        size = os.path.getsize(os.path.join(OUT, name))
        index.append({"file": name, "type": k, "shows": what, "e44_batch": int(r.batch), "e44_idx": int(r.idx),
                      "reproduces_e44_row": bool(same), "steps_total": oc_on["steps_total"], "stride": oc_on["stride"],
                      "kb_gz": round(size / 1024, 1), "shield_on": {x: oc_on[x] for x in ("deadlock", "finished")},
                      "shield_off_violations": oc_off["violations_by_kind"]})
        print(f"T{k} {name}: {what} | e44 b{int(r.batch)} i{int(r.idx)} same={same} steps {oc_on['steps_total']} "
              f"stride {oc_on['stride']} {size / 1024:.0f} kB | off-violations {oc_off['violations_by_kind']}", flush=True)
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump({"note": __doc__.split("\n\n")[1].strip(), "encounters": index}, f, indent=1)
        f.write("\n")


if __name__ == "__main__":
    main()
