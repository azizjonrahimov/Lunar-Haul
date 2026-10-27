"""B-71: calibrate and write the "p5" scenario family (lunarsim/atc/p5.py).

    python tools/atc/p5_scenarios.py plateau     # whole-fleet utilisation as demand grows (3eq, marketplace)
    python tools/atc/p5_scenarios.py calibrate   # k for each load variant (FLEX + Eagle busy 10 / 30 / 60 %)
    python tools/atc/p5_scenarios.py measure     # marketplace and inhouse at the calibrated k, 5 seeds
    python tools/atc/p5_scenarios.py write       # -> data/scenarios/p5/*.json, results/ATC_p5_load.json

Every step is single process, resumable (runs cached in .cache/atc/p5_runs.json) and stops near --max-seconds
(default 540); rerun until it says done.

Load variants (LEAD, B-71 Q6): the demand multiplier k (P2's landing rates and bulk tonnes) at which the cargo-class
vehicles (CARGO_FLEX, CARGO_EAGLE) are busy 10, 30 and 60 % of the year (mean of seeds 1-5, marketplace, 3 equal
owners, team-lift share 0.10); whole-fleet utilisation is reported next to it, because scaling demand on this fleet
levels off at about 17 % whole-fleet utilisation (only the two cargo rovers can lift most of the cargo). A 200 kg
bulk-lot variant at the 30 % level is an ASSUMED sensitivity.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lunarsim.atc import p5 as P5  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc")
RUNS = os.path.join(CACHE, "p5_runs.json")
CALIB = os.path.join(CACHE, "p5_calib.json")
OUT_DIR = os.path.join(ROOT, "data", "scenarios", "p5")
SUMMARY = os.path.join(ROOT, "results", "ATC_p5_load.json")
SEEDS = (1, 2, 3, 4, 5)
CAL_MIX, CAL_MECH, CAL_TEAM = "3eq", "marketplace", 0.10
TARGETS = {"10": (0.10, P5.BULK_LOT_KG), "30": (0.30, P5.BULK_LOT_KG), "60": (0.60, P5.BULK_LOT_KG),
           "30-lot200": (0.30, 200.0)}
TOL = 0.005                       # calibrated when the 5-seed mean is within 0.5 pp of the target
MAX_IT = 8
PLATEAU = [(1.0, SEEDS[:3]), (2.0, SEEDS[:3]), (4.0, SEEDS[:3]), (8.0, SEEDS[:3]), (11.0, SEEDS[:1]), (14.0, SEEDS[:1])]
KEEP = ("utilisation", "p5_utilisation_active", "p5_cargo_util", "delivered_kg", "backlog_kg", "stranded_kg",
        "ready_kg", "landed_kg", "jobs", "team_lifts", "p5_heavy_items", "p5_heavy_t", "p5_team_items",
        "p5_team_items_redrawn", "p5_team_items_same_owner_liftable", "p5_team_items_delivered", "p5_hopper_km",
        "p5_day_cap_h", "p5_refused_jobs", "p5_reach_kg", "p5_single_max_kg", "p5_pair_max_kg",
        "delay_prio1_mean_h")


def _key(mix, k, team, lot, mech, seed) -> str:
    return f"{mix}|{k:.6g}|{team:g}|{lot:g}|{mech}|{seed}"


def _load(path) -> Dict[str, Any]:
    return json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else {}


def _save(path, doc) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    os.replace(tmp, path)


class Runner:
    """Cached single runs with a wall-clock budget."""

    def __init__(self, max_seconds: float):
        self.t0, self.max_s = time.time(), max_seconds
        self.runs = _load(RUNS)
        self.last_s = 30.0

    def out_of_time(self) -> bool:
        return time.time() - self.t0 > self.max_s - max(30.0, 1.5 * self.last_s)

    def run(self, mix, k, team, lot, mech, seed) -> Optional[Dict[str, Any]]:
        key = _key(mix, k, team, lot, mech, seed)
        if key in self.runs:
            return self.runs[key]
        if self.out_of_time():
            return None
        from lunarsim import Simulation, dispatch
        t = time.time()
        sim = Simulation(P5.build(mix, k=k, team_lift_share=team, bulk_lot_kg=lot), getattr(dispatch, mech), seed=seed)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            s = sim.run()
        r = {k_: (float(s[k_]) if k_ in s and s[k_] is not None else None) for k_ in KEEP}
        busy: Dict[str, List[float]] = {}
        for v in sim.vehicles:
            busy.setdefault(v.cls.name, []).append(round(v.hours_busy / sim.sc.horizon_h, 4))
        r["busy_share_by_class"] = busy
        r["wall_s"] = round(time.time() - t, 1)
        self.last_s = r["wall_s"]
        self.runs[key] = r
        _save(RUNS, self.runs)
        print(f"  run {key}: cargo {r['p5_cargo_util']:.3f}, fleet {r['utilisation']:.3f} ({r['wall_s']} s)", flush=True)
        return r

    def mean(self, mix, k, team, lot, mech, metric, seeds=SEEDS) -> Optional[float]:
        vals = []
        for s in seeds:
            r = self.run(mix, k, team, lot, mech, s)
            if r is None:
                return None
            vals.append(r[metric])
        return float(np.mean(vals))


# ---------------------------------------------------------------------------------------------------------------
def step_plateau(R: Runner) -> bool:
    for k, seeds in PLATEAU:
        if R.mean(CAL_MIX, k, CAL_TEAM, P5.BULK_LOT_KG, CAL_MECH, "utilisation", seeds) is None:
            print("plateau: time limit, rerun")
            return False
    print("plateau: done")
    return True


def next_k(hist: List[Tuple[float, float]], target: float) -> float:
    """Proportional first step, then the secant on log k (clamped to a factor 3 per step)."""
    if len(hist) == 1:
        k, u = hist[0]
        return k * target / max(u, 1e-6)
    (k1, u1), (k2, u2) = hist[-2], hist[-1]
    if abs(u2 - u1) < 1e-9:
        return k2 * (1.2 if u2 < target else 0.8)
    lk = np.log(k2) + (target - u2) * (np.log(k2) - np.log(k1)) / (u2 - u1)
    return float(np.clip(np.exp(lk), k2 / 3, k2 * 3))


def step_calibrate(R: Runner) -> bool:
    cal = _load(CALIB)
    for name, (target, lot) in TARGETS.items():
        c = cal.setdefault(name, {"target": target, "bulk_lot_kg": lot, "hist": [], "k": None})
        if c["k"] is not None:
            continue
        hist = [tuple(h) for h in c["hist"]]
        k = 1.0 if not hist else round(next_k(hist, target), 3)
        while True:
            u = R.mean(CAL_MIX, k, CAL_TEAM, lot, CAL_MECH, "p5_cargo_util")
            if u is None:
                _save(CALIB, cal)
                print(f"calibrate {name}: time limit at k {k}, rerun")
                return False
            hist.append((k, u))
            c["hist"] = [list(h) for h in hist]
            print(f"calibrate {name}: k {k} -> cargo-class busy {u:.4f} (target {target})", flush=True)
            if abs(u - target) <= TOL or len(hist) >= MAX_IT:
                best = min(hist, key=lambda h: abs(h[1] - target))
                c["k"], c["cargo_util"], c["converged"] = best[0], best[1], abs(best[1] - target) <= TOL
                break
            k = round(next_k(hist, target), 3)
        _save(CALIB, cal)
    print("calibrate: done " + json.dumps({n: c["k"] for n, c in cal.items()}))
    return True


def measure_plan(cal) -> List[Tuple[str, str, float, float, str]]:
    """(load, mix, k, lot, mech): 3eq at every load, the other mixes at 30 %, the 200 kg lots at 30 %."""
    plan = []
    for load in ("10", "30", "60"):
        for mix in (["3eq", "2eq", "3uneq", "5eq"] if load == "30" else ["3eq"]):
            for mech in ("marketplace", "inhouse"):
                plan.append((load, mix, cal[load]["k"], P5.BULK_LOT_KG, mech))
    for mech in ("marketplace", "inhouse"):
        plan.append(("30-lot200", "3eq", cal["30-lot200"]["k"], 200.0, mech))
    return plan


def step_measure(R: Runner) -> bool:
    cal = _load(CALIB)
    if any(cal.get(n, {}).get("k") is None for n in TARGETS):
        raise SystemExit("calibrate first")
    for load, mix, k, lot, mech in measure_plan(cal):
        if R.mean(mix, k, CAL_TEAM, lot, mech, "utilisation") is None:
            print("measure: time limit, rerun")
            return False
    print("measure: done")
    return True


# ---------------------------------------------------------------------------------------------------------------
def _stats(R: Runner, mix, k, team, lot, mech, seeds=SEEDS) -> Dict[str, Any]:
    rs = [R.runs[_key(mix, k, team, lot, mech, s)] for s in seeds]

    def ms(m, scale=1.0):
        v = np.array([r[m] for r in rs], float) * scale
        return [round(float(v.mean()), 4), round(float(v.std(ddof=1)), 4) if len(v) > 1 else 0.0]

    team_n = sum(r["p5_team_items"] for r in rs)
    return {"seeds": list(seeds), "cargo_class_busy": ms("p5_cargo_util"), "fleet_utilisation": ms("utilisation"),
            "fleet_utilisation_active_h": ms("p5_utilisation_active"), "delivered_t": ms("delivered_kg", 1e-3),
            "backlog_t": ms("backlog_kg", 1e-3), "stranded_t": ms("stranded_kg", 1e-3),
            "heavy_lift_items": ms("p5_heavy_items"), "heavy_lift_t": ms("p5_heavy_t"),
            "team_items": ms("p5_team_items"), "team_items_delivered": ms("p5_team_items_delivered"),
            "team_items_same_owner_liftable_share": round(sum(r["p5_team_items_same_owner_liftable"] for r in rs)
                                                          / team_n, 4) if team_n else None,
            "hopper_km": ms("p5_hopper_km"), "day_cap_h": ms("p5_day_cap_h"),
            "busy_share_by_class_seed1": rs[0]["busy_share_by_class"]}


def step_write() -> Dict[str, Any]:
    R = Runner(1e9)
    cal = _load(CALIB)
    from lunarsim.config import scenario_to_dict
    from lunarsim.formats import validate_scenario
    measured: Dict[str, Dict[str, Any]] = {}
    for load, mix, k, lot, mech in measure_plan(cal):
        measured.setdefault(f"{load}|{mix}", {})[mech] = _stats(R, mix, k, CAL_TEAM, lot, mech)
    os.makedirs(OUT_DIR, exist_ok=True)
    written = []
    for mix in P5.OWNER_MIXES:
        for load in ("10", "30", "60"):
            for team in P5.TEAM_SHARES:
                written.append(_write_one(mix, load, team, P5.BULK_LOT_KG, cal, measured, None))
    written.append(_write_one("3eq", "30-lot200", CAL_TEAM, 200.0, cal, measured,
                              "ASSUMED sensitivity: 200 kg bulk lots (MAPPs can haul regolith)"))
    for p in written:
        errs = validate_scenario(json.load(open(p, encoding="utf-8")))
        if errs:
            raise SystemExit(f"{p}: {errs[:3]}")
    plateau = []
    for k, seeds in PLATEAU:
        st = _stats(R, CAL_MIX, k, CAL_TEAM, P5.BULK_LOT_KG, CAL_MECH, seeds)
        plateau.append({"k": k, **{m: st[m] for m in ("seeds", "fleet_utilisation", "fleet_utilisation_active_h",
                                                       "cargo_class_busy", "delivered_t", "backlog_t",
                                                       "busy_share_by_class_seed1")}})
    doc = {"task": "B-71", "description": __doc__.split("\n\n")[-1].strip(),
           "calibration": {"mix": CAL_MIX, "mechanism": CAL_MECH, "team_lift_share": CAL_TEAM, "seeds": list(SEEDS),
                           "tolerance": TOL, "metric": "p5_cargo_util (busy hours of CARGO_FLEX + CARGO_EAGLE / their "
                                                       "hours in the year)", "variants": cal},
           "measured": measured, "plateau": plateau,
           "files": [os.path.relpath(p, ROOT).replace(os.sep, "/") for p in written],
           "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    with open(SUMMARY, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(f"write: {len(written)} scenario files, {os.path.relpath(SUMMARY, ROOT)}")
    return doc


def _write_one(mix, load, team, lot, cal, measured, label) -> str:
    from lunarsim.config import scenario_to_dict
    c = cal[load]
    m = measured.get(f"{load}|{mix}")
    extra = {"load": {"variant": load, "target_cargo_class_busy": c["target"], "k": c["k"],
                      "calibration": f"{CAL_MECH}, {CAL_MIX}, team share {CAL_TEAM}, seeds {SEEDS[0]}-{SEEDS[-1]}",
                      **({"measured": {mech: {"cargo_class_busy": v["cargo_class_busy"][0],
                                              "fleet_utilisation": v["fleet_utilisation"][0]}
                                       for mech, v in m.items()}} if m and team == CAL_TEAM else {})}}
    if label:
        extra["label"] = label
    tt = f"T{int(round(team * 100)):02d}"
    name = f"p5-{mix}-L{load}-{tt}"
    sc = P5.build(mix, k=c["k"], team_lift_share=team, name=name, bulk_lot_kg=lot, **extra)
    path = os.path.join(OUT_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(scenario_to_dict(sc), f, indent=1)
        f.write("\n")
    return path


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/atc/p5_scenarios.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=["plateau", "calibrate", "measure", "write"])
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds + 30, exit=True)
    R = Runner(a.max_seconds)
    if a.cmd == "plateau":
        step_plateau(R)
    elif a.cmd == "calibrate":
        step_calibrate(R)
    elif a.cmd == "measure":
        step_measure(R)
    else:
        step_write()
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from terrain_assets import peak_rss_mb
    rss = peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
