"""B-107 (P2 M9): uphill encounters. R1's no-collision proposition assumes the leader brakes no harder than
B_MAX = 0.8 m/s2; a conforming vehicle going uphill brakes at its service braking plus the slope, 0.5 + g sin(theta),
which is above B_MAX beyond 10.7 deg on the Moon (g 1.62) and 4.6 deg on Mars (g 3.71).

    python tools/atc/run_e45_uphill.py run [--max-seconds 480]    # resumable, one file per cell
    python tools/atc/run_e45_uphill.py build                      # -> results/E45_uphill.json, results/E45_uphill.csv

Encounters: E44's type 1 (following, the leader brakes to a stop; lunarsim/atc/encounter_types.py t1) with the slope
fixed uphill and the followers at the rule's limit: every vehicle at class speed, each follower 0-2 m beyond R1's
d_min and driven by E44's adversarial planner (it asks for full acceleration, so the safety check holds it at the
limit; E44's nominal planner keeps a cushion of v^2/0.6 + 2 m and never reaches d_min), in two geometries: "following" (a two-lane road, as type 1) and "one_lane" (the same convoy holding one
single-lane reservation, R3, same direction); Moon and Mars; slopes 5, 10, 15, 17.2 deg. In every cell the braking
leader brakes at its real capability, max(B_MAX, b_guaranteed(theta)) (Spec.lead_brake_physical), and every vehicle
goes through the one safety_check as it is ("as_is") or with the slope term in R1 ("slope_term": R1 assumes that
leader braking, Move.b_front = max(B_MAX, b_guaranteed(theta))), on the same encounters (paired). Opt-in; E44's types
and seeds are untouched (seed roots 4507 builder / 4508 run, never used). Each cell runs without and with a follower actuation lag equal to R1's response time RHO_S = 1 s
(Spec.actuation_delay_s; E44's vehicles act within one 0.1 s step, faster than the proposition assumes, so the margin
it reserves for the response is not spent without the lag). A slope sweep (0 to 17 deg, 0.5 deg steps, 500
encounters, as_is, with the lag) gives the slope at which the smallest same-lane gap falls inside the 5 m static margin D0.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from lunarsim.atc import encounter as E, encounter_types as ET, safety as S  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "e45_uphill")
OUT_JSON = os.path.join(ROOT, "results", "E45_uphill.json")
OUT_CSV = os.path.join(ROOT, "results", "E45_uphill.csv")
PLANETS = {"moon": S.G_MOON, "mars": S.G_MARS}
SLOPES = [5.0, 10.0, 15.0, 17.2]
GEOMS = ["following", "one_lane"]
RULES = ["as_is", "slope_term"]
DELAYS = [0.0, S.RHO_S]                         # 0 = E44 (the check acts within one 0.1 s step); RHO_S = R1's own response time as a lag
N_CELL = 2000
SWEEP = [x / 2 for x in range(0, 35)]          # 0 to 17 deg
N_SWEEP = 500
VIOL = ("viol_contact", "viol_gap", "viol_zone", "viol_crew", "viol_r3", "viol_slots")


def build(rng, slope, geom, g, delay=0.0):
    """E44 type 1 (t1) with theta = -slope (uphill) and the leader braking at its real capability."""
    theta = -float(slope)
    mu = ET._mu(rng)
    nv = int(rng.choice([2, 3]))
    vcl = float(rng.choice([E.V_LTV, E.V_LTV_FAST]))
    vmax = float(S.v_max_r2(theta, mu, 1e4, vcl, g=g))
    drivable = vmax > 0.05
    v0 = vmax if drivable else 0.0               # steady state at class speed (E44 t1: 0.6-1.0 x vmax)
    b = float(S.b_guaranteed(theta, mu, g))
    pts = [(0.0, -ET.Y), (700.0, -ET.Y)]
    s, sl = [], 250.0
    for i in range(nv):
        s.append(sl)
        gap = float(S.rss_dmin(v0, v0, b)) + rng.uniform(0, 2) if drivable else 30.0   # at the rule's limit (t1: 0-30 m)
        sl = sl - E.VEH_L - gap
    tb = rng.uniform(2, 30)
    kw = {}
    if geom == "one_lane":                       # the convoy enters one single-lane segment (R3, same direction) as
        s_in = 260.0                             # type 9 does: it starts before the segment and is granted on approach;
        if drivable:                             # the leader brakes after the last vehicle is inside
            tb += (s_in + 5.0 - s[-1]) / max(v0, 0.1)
        kw = dict(groups=[[{"res": [0], "dirs": [1], "s_in": s_in, "s_out": 700.0}] for _ in range(nv)],
                  res_kind=[0], res_slots=[1], res_branched=[False])
    return E.Spec(paths=[pts] * nv, v_class=[vmax if drivable else vcl] * nv, v0=[v0] * nv, s0=s,
                  planner=[0] + [2] * (nv - 1), theta=theta, mu=mu, lead_brake=(0, tb),
                  priority=list(range(nv)), t_max=(tb + 90 if drivable else 0.2), stop_is_goal=True,
                  lead_brake_physical=True, actuation_delay_s=float(delay),
                  params={"theta": theta, "mu": mu, "n": nv, "v0": v0, "drivable": drivable, "b_lead": max(S.B_MAX, b)},
                  **kw)


def run_cell(planet, geom, slope, n, tag, rules=RULES, delay=0.0):
    g = PLANETS[planet]
    pi, gi = list(PLANETS).index(planet), GEOMS.index(geom)
    rng = np.random.default_rng([4507, pi, gi, int(round(slope * 10)), 0 if tag == "cell" else 1])
    ET.G_BUILD = g
    specs = [build(rng, slope, geom, g, delay) for _ in range(n)]
    drive = [sp for sp in specs if sp.params["drivable"]]
    out = {"planet": planet, "geom": geom, "slope_deg": slope, "delay_s": float(delay), "n": n, "n_driven": len(drive), "g": g,
           "b_lead_mean": float(np.mean([sp.params["b_lead"] for sp in drive])) if drive else None, "rules": {}}
    for rule in rules:
        for sp in drive:
            sp.r1_slope_term = rule == "slope_term"
        if not drive:
            out["rules"][rule] = None
            continue
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            oc, _ = E.run_batch(E.Batch(drive, g=g), np.random.default_rng([4508, pi, gi, int(round(slope * 10))]))
        gap = np.asarray(oc.min_gap_same, float)
        gapf = gap[np.isfinite(gap)]
        nominal = np.array([all(p == 0 for p in sp.planner) for sp in drive])
        out["rules"][rule] = {
            "violations": int(sum(int(np.any([getattr(oc, f)[i] > 0 for f in VIOL])) for i in range(len(drive)))),
            "by_kind": {f: int((np.asarray(getattr(oc, f)) > 0).sum()) for f in VIOL},
            "min_gap_m": float(gapf.min()) if len(gapf) else None,
            "min_gap_p01_m": float(np.quantile(gapf, 0.01)) if len(gapf) else None,
            "min_gap_median_m": float(np.median(gapf)) if len(gapf) else None,
            "gap_below_d0": int((gapf < S.D0_M).sum()), "contacts": int((np.asarray(oc.viol_contact) > 0).sum()),
            "r1_breach_rate": float((np.asarray(oc.r1_breach) > 0).mean()),
            "emergency_brake_rate": float((np.asarray(oc.no_safe) > 0).mean()),
            "nominal_only_violations": int(sum(int(np.any([getattr(oc, f)[i] > 0 for f in VIOL])) for i in np.nonzero(nominal)[0])),
            "nominal_only_n": int(nominal.sum())}
    ET.G_BUILD = S.G_MOON
    return out


def _cells():
    for planet in PLANETS:
        for geom in GEOMS:
            for slope in SLOPES:
                for delay in DELAYS:
                    yield ("cell", planet, geom, slope, delay)
    for planet in PLANETS:
        for geom in GEOMS:
            for slope in SWEEP:
                yield ("sweep", planet, geom, slope, S.RHO_S)


def _path(tag, planet, geom, slope, delay):
    return os.path.join(CACHE, f"{tag}_{planet}_{geom}_{slope:g}_d{delay:g}.json")


def cmd_run(max_s):
    os.makedirs(CACHE, exist_ok=True)
    t0 = time.time()
    est = {"cell": 60.0, "sweep": 10.0}
    for tag, planet, geom, slope, delay in _cells():
        p = _path(tag, planet, geom, slope, delay)
        if os.path.isfile(p):
            continue
        if time.time() - t0 + 1.4 * est[tag] > max_s:
            print(f"stop before {tag} {planet} {geom} {slope} d{delay:g}: time budget", flush=True)
            return
        ts = time.time()
        out = run_cell(planet, geom, slope, N_CELL if tag == "cell" else N_SWEEP, tag,
                       RULES if tag == "cell" else ["as_is"], delay)
        est[tag] = max(est[tag] * 0.5, time.time() - ts)
        json.dump(out, open(p + ".tmp", "w"))
        os.replace(p + ".tmp", p)
        r = out["rules"].get("as_is") or {}
        print(f"{tag} {planet} {geom} {slope:g} d{delay:g}: {time.time() - ts:.0f} s, viol {r.get('violations')}, min gap "
              f"{r.get('min_gap_m')}" + (f", slope_term viol {out['rules']['slope_term']['violations']} min gap "
                                        f"{out['rules']['slope_term']['min_gap_m']}" if tag == "cell" and out["rules"].get("slope_term") else ""),
              flush=True)
    print("all cells done", flush=True)


def cmd_build():
    cells = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(CACHE, "cell_*.json")))]
    sweep = [json.load(open(p)) for p in sorted(glob.glob(os.path.join(CACHE, "sweep_*.json")))]
    rows = []
    for c in cells:
        for rule, r in c["rules"].items():
            if r is None:
                continue
            rows.append({"planet": c["planet"], "geom": c["geom"], "slope_deg": c["slope_deg"], "delay_s": c["delay_s"], "rule": rule,
                         "n_driven": c["n_driven"], "b_lead_mean": round(c["b_lead_mean"], 4), "violations": r["violations"],
                         "contacts": r["contacts"], "gap_below_d0": r["gap_below_d0"], "min_gap_m": r["min_gap_m"],
                         "min_gap_p01_m": r["min_gap_p01_m"], "r1_breach_rate": r["r1_breach_rate"],
                         "nominal_only_violations": r["nominal_only_violations"]})
    thr = {}
    for planet in PLANETS:
        for geom in GEOMS:
            pts = sorted(((s["slope_deg"], s["rules"]["as_is"]["min_gap_m"]) for s in sweep
                          if s["planet"] == planet and s["geom"] == geom and s["rules"].get("as_is")), key=lambda x: x[0])
            first = next((sl for sl, gp in pts if gp is not None and gp < S.D0_M), None)
            thr[f"{planet}:{geom}"] = {"first_slope_with_gap_below_d0_deg": first,
                                       "theory_b_lead_exceeds_b_max_deg": round(math.degrees(math.asin((S.B_MAX - S.B_MIN_FLAT) / PLANETS[planet])), 2),
                                       "sweep": [[sl, gp] for sl, gp in pts]}
    doc = {"task": "B-107 (P2 M9)", "note": __doc__.strip().split("\n\n")[1].replace("\n", " "),
           "d0_m": S.D0_M, "b_max": S.B_MAX, "b_min_flat": S.B_MIN_FLAT, "n_per_cell": N_CELL, "n_per_sweep_point": N_SWEEP,
           "cells": rows, "threshold": thr}
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, allow_nan=False)
        f.write("\n")
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)
    print(json.dumps({k: (v["first_slope_with_gap_below_d0_deg"], v["theory_b_lead_exceeds_b_max_deg"]) for k, v in thr.items()}))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "build"])
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        cmd_run(a.max_seconds)
    else:
        cmd_build()


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(560, exit=True)
    main()
