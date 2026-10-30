"""E47 (B-82): the Mars part of P2 (exploratory H9).

    python tools/atc/run_e47.py design                    # -> data/scenarios/E47-design.json (before any row)
    python tools/atc/run_e47.py encounters [--max-seconds 480]   # E44's 12 types with Mars gravity -> results/E47_parts/
    python experiments/phase5/run_phase5.py run --exp E47 --fixpoint --max-seconds 480   # road coordination, Mars link
    python tools/atc/run_e47.py analyse                   # -> results/E47_encounters.csv, E47_bounds.json, E47_bins.csv,
                                                          #    results/E47_fit.json (H9 numbers)

Encounters: the same builders, rules, safety_check and seeds as E44 ((44, type, batch): Mars encounter (k, b, i) is
the Moon encounter (k, b, i) with g = 3.71 m/s2 in the braking, slope and drivability terms), 2,000 per type and
12,000 for types 1 and 7. The vehicles are the lunar ones (service braking 0.5 m/s2, B_MAX 0.8 m/s2): a downhill slope
steeper than asin(0.5 / 3.71) = 7.7 deg cannot be held by the service brake, so R2 forbids driving it (type 1 counts
those draws as not driven). Road coordination: E43's cells at 1x with a Mars Earth link (lunarsim/atc/roads.py
MARS_DEFAULTS) on the Connecting Ridge road geometry as the controlled case.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE, os.path.join(ROOT, "experiments", "phase5")):
    if p not in sys.path:
        sys.path.insert(0, p)
import run_e44 as R  # noqa: E402
from lunarsim.atc import encounter_types as ET, safety as S  # noqa: E402
from lunarsim.atc.roads import MARS_DEFAULTS  # noqa: E402

DESIGN = os.path.join(ROOT, "data", "scenarios", "E47-design.json")
FIT = os.path.join(ROOT, "results", "E47_fit.json")
N_MARS = {k: 2_000 for k in range(1, 13)}
N_MARS.update({1: 12_000, 7: 12_000})
VIOL = R.VIOL


def configure():
    R.PARTS = os.path.join(ROOT, "results", "E47_parts")
    R.OUT_CSV = os.path.join(ROOT, "results", "E47_encounters.csv")
    R.OUT_BOUNDS = os.path.join(ROOT, "results", "E47_bounds.json")
    R.OUT_BINS = os.path.join(ROOT, "results", "E47_bins.csv")
    R.GRAVITY = S.G_MARS
    R.DEFECTS_FILE = None
    R.N_TARGET = dict(N_MARS)
    ET.G_BUILD = S.G_MARS
    # batch-time estimates: start from E44's per-type batch times, so a chunk never starts a batch it cannot finish
    tf = os.path.join(R.PARTS, "timing.json")
    t44 = os.path.join(ROOT, "results", "E44_parts", "timing.json")
    if os.path.isfile(t44):
        tim = json.load(open(tf)) if os.path.isfile(tf) else {}
        for k, v in json.load(open(t44)).items():
            if k not in tim and k.isdigit():
                tim[k] = {"seconds": v.get("seconds", 60.0), "batch": v.get("batch"), "seeded_from_e44": True}
        os.makedirs(R.PARTS, exist_ok=True)
        json.dump(tim, open(tf, "w"), indent=1)


def cmd_design():
    th = math.degrees(math.asin(S.B_MIN_FLAT / S.G_MARS))
    doc = {"experiment": "E47 (B-82), the Mars part of P2, exploratory H9",
           "hypothesis_H9": "the same rules keep zero violations under Mars gravity and braking; the delay cost of the "
                            "rules is similar to the Moon's; Earth-dependent coordination loses more on Mars than on "
                            "the Moon because of 6-44 min round trips and conjunction blackouts (PREREG change 1)",
           "encounters": {"types": list(range(1, 13)), "n_per_type": N_MARS, "seeds": "(44, type, batch) as E44: paired "
                          "with the Moon encounters of the same type, batch and index", "batch_sizes": R.BATCH,
                          "gravity_m_s2": {"value": S.G_MARS, "flag": "Spec"},
                          "vehicles": {"service_braking_m_s2": S.B_MIN_FLAT, "max_braking_m_s2": S.B_MAX,
                                       "flag": "Assumed: the lunar vehicles, unchanged",
                                       "steepest_holdable_downhill_deg": round(th, 2)},
                          "friction_mu": {"values": [0.3, 0.45, 0.6], "flag": "Assumed: as on the Moon (Low)"},
                          "everything_else": "E44 unchanged (rules, safety_check, builders, outcome classes, bound rule)"},
           "road_coordination": {"cells": "E43 atc and uncoordinated at 1x, pooled dispatch, 30 % load, one year, seeds "
                                          "1-30; atc is Earth-independent (its runs must equal E43's atc x1)",
                                 "geometry": "Connecting Ridge roads, as the controlled case",
                                 "rtt_min": {"values": [6, 20, 44], "flag": "Spec (light time 3-22 min each way)"},
                                 "relay": {"values": ["none (base)", "one areostationary relay (variant: continuous "
                                                      "contact outside conjunction and storms)"], "flag": "Assumed"},
                                 "mars_link": {k: v for k, v in MARS_DEFAULTS.items() if k not in ("rtt_min", "relay")},
                                 "mars_link_flags": {"sol_h": "Spec", "dte_fraction": "Assumed", "conjunction_start_d":
                                                     "Assumed (fixed date)", "conjunction_days": "Spec/Assumed",
                                                     "storms": "Assumed (dust storms as comms-loss bursts)"},
                                 "t_hand_h": {"value": 2.0, "flag": "Assumed: staff time as E43; the round trip is "
                                                                    "added on Mars"},
                                 "moon_baseline": "results/E43_runs.lead.csv (uncoordinated x1 2028 and 2038, atc x1)"},
           "second_geometry": {"done": False,
                               "why_not": "the terrain code reads PGDA LOLA polar-stereographic tiles with the lunar "
                                          "radius; a HiRISE DTM (PDS IMG/GeoTIFF, equirectangular, ~1 m/px, hundreds of "
                                          "MB per tile) needs a new reader and projection, and a Jezero base needs its own "
                                          "sites, pads and route network before E43-style runs can use it; together more "
                                          "than a day, so the controlled case only"},
           "outputs": ["results/E47_encounters.csv", "results/E47_bounds.json", "results/E47_bins.csv",
                       "results/E47_runs.csv", "results/E47_fit.json"]}
    os.makedirs(os.path.dirname(DESIGN), exist_ok=True)
    with open(DESIGN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print("design:", os.path.relpath(DESIGN, ROOT))


def _boot(x, n=20000, seed=7):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) < 2:
        return {"mean": float(x.mean()) if len(x) else None, "ci": None, "n": int(len(x))}
    rng = np.random.default_rng(seed)
    m = rng.choice(x, (n, len(x))).mean(1)
    return {"mean": round(float(x.mean()), 4), "ci": [round(float(np.quantile(m, 0.025)), 4),
                                                      round(float(np.quantile(m, 0.975)), 4)], "n": int(len(x))}


def cmd_analyse():
    configure()
    R.cmd_summarize()
    bounds = json.load(open(R.OUT_BOUNDS, encoding="utf-8"))
    bounds["experiment"] = "E47 (Mars): E44's 12 types with g = 3.71 m/s2, lunar vehicles; exploratory (H9)"
    with open(R.OUT_BOUNDS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(bounds, f, indent=1, default=float)
        f.write("\n")
    mars = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(R.PARTS, "T*_b*.csv.gz")))], ignore_index=True)
    moon = pd.concat([pd.read_csv(f) for f in sorted(glob.glob(os.path.join(ROOT, "results", "E44_parts", "T*_b*.csv.gz")))],
                     ignore_index=True)
    key = ["type", "batch", "idx"]
    pair = mars.merge(moon, on=key, suffixes=("_mars", "_moon"))
    enc = {}
    for k in range(1, 13):
        p = pair[pair.type == k]
        both = p[(p.drivable_mars == 1) & (p.drivable_moon == 1)]
        vm = both[[f + "_mars" for f in VIOL]].max(axis=1) > 0
        vl = both[[f + "_moon" for f in VIOL]].max(axis=1) > 0
        nom = both[(both.n_nominal_mars == both.n_vehicles_mars) & (both.finished_mars == 1) & (both.finished_moon == 1)]
        tb = bounds["types"][str(k)]
        enc[k] = {"n": tb["n"], "violations_mars": tb["violations"], "violations_by_kind_mars": tb["violations_by_kind"],
                  "deadlocks_mars": tb["outcomes"]["deadlock"], "bound_mars": tb["bound"],
                  "not_driven_mars": tb["outcomes"]["not_driven"],
                  "not_driven_moon_same_encounters": int((p.drivable_moon == 0).sum()),
                  "paired_driven_both": int(len(both)), "violations_moon_same_encounters": int(vl.sum()),
                  "violations_mars_same_encounters": int(vm.sum()),
                  "delay_s_nominal": {"moon": _boot(nom["delay_s_moon"]), "mars": _boot(nom["delay_s_mars"]),
                                      "mars_minus_moon": _boot(nom["delay_s_mars"] - nom["delay_s_moon"])}}
    allnom = pair[(pair.drivable_mars == 1) & (pair.drivable_moon == 1) & (pair.n_nominal_mars == pair.n_vehicles_mars)
                  & (pair.finished_mars == 1) & (pair.finished_moon == 1)]
    dm, dl = allnom["delay_s_mars"].mean(), allnom["delay_s_moon"].mean()
    # road coordination
    import run_phase5 as P
    e47 = P.load_runs("E47")
    e43 = P.load_runs("E43")
    road = {}
    atc_m = e47[e47.label == "atc x1 mars"].set_index("seed")
    atc_l = e43[(e43.label == "atc x1") & (e43.start_year == 2028)].set_index("seed")
    common = atc_m.index.intersection(atc_l.index)
    road["atc_mars_equals_moon"] = bool(len(common) and np.allclose(atc_m.loc[common, "delay_mean_h"],
                                                                 atc_l.loc[common, "delay_mean_h"]))
    for metric in ("delay_mean_h", "atc_urgent_wait_mean_cens_h"):
        blk = {}
        for y in (2028, 2038):
            u = e43[(e43.label == "uncoordinated x1") & (e43.start_year == y)].set_index("seed")
            s_ = u.index.intersection(atc_l.index)
            blk[f"moon_{y}"] = {"uncoordinated_minus_atc": _boot(u.loc[s_, metric] - atc_l.loc[s_, metric]),
                                "atc_mean": round(float(atc_l.loc[s_, metric].mean()), 3)}
        for relay in (False, True):
            for rtt in P.E47_RTT_MIN:
                lab = f"uncoordinated x1 mars rtt {rtt:g} {'relay' if relay else 'no relay'}"
                u = e47[e47.label == lab].set_index("seed")
                if u.empty:
                    continue
                s_ = u.index.intersection(atc_m.index)
                blk[f"mars_rtt{rtt:g}_{'relay' if relay else 'norelay'}"] = {
                    "uncoordinated_minus_atc": _boot(u.loc[s_, metric] - atc_m.loc[s_, metric]),
                    "hand_conflicts_mean": round(float(u.loc[s_, "road_hand_conflicts"].mean()), 2),
                    "hand_wait_h_mean": round(float(u.loc[s_, "road_hand_wait_h"].mean()), 1)}
        road[metric] = blk
    d = road["delay_mean_h"]
    m20 = d.get("mars_rtt20_norelay", {}).get("uncoordinated_minus_atc", {}).get("mean")
    l28 = d["moon_2028"]["uncoordinated_minus_atc"]["mean"]
    l38 = d["moon_2038"]["uncoordinated_minus_atc"]["mean"]
    v_mars_ex9 = sum(enc[k]["violations_mars"] for k in enc if k != 9)
    fit = {"experiment": "E47 (B-82, Mars, exploratory H9)", "design": os.path.relpath(DESIGN, ROOT).replace("\\", "/"),
           "encounters": enc, "road_coordination": road,
           "headline": {
               "violations_mars_all_types": sum(enc[k]["violations_mars"] for k in enc),
               "violations_mars_excluding_type9": v_mars_ex9,
               "type9_dead_stop_violations_mars": enc[9]["violations_mars"],
               "type9_dead_stop_violations_moon_same_encounters": enc[9]["violations_moon_same_encounters"],
               "deadlocks_mars": {k: enc[k]["deadlocks_mars"] for k in enc if enc[k]["deadlocks_mars"]},
               "type1_not_driven_share_mars": round(enc[1]["not_driven_mars"] / enc[1]["n"], 3),
               "type1_not_driven_share_moon": round(enc[1]["not_driven_moon_same_encounters"] / enc[1]["n"], 3),
               "steepest_holdable_downhill_deg_mars": round(math.degrees(math.asin(S.B_MIN_FLAT / S.G_MARS)), 1),
               "rule_delay_nominal_mars_over_moon": round(float(dm / dl), 3) if dl else None,
               "rule_delay_nominal_s": {"mars": round(float(dm), 1), "moon": round(float(dl), 1), "n": int(len(allnom))},
               "uncoordinated_penalty_delay_h": {"mars_rtt20_norelay": m20, "moon_2028": l28, "moon_2038": l38,
                                                 "mars_over_moon_2028": round(m20 / l28, 3) if m20 and l28 else None},
               "atc_mars_equals_moon": road["atc_mars_equals_moon"]},
           "second_geometry": json.load(open(DESIGN, encoding="utf-8"))["second_geometry"]}
    with open(FIT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(fit, f, indent=1, default=float)
        f.write("\n")
    print(json.dumps(fit["headline"], indent=1, default=float))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["design", "encounters", "analyse"])
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 120, exit=True)
    if a.cmd == "design":
        cmd_design()
    elif a.cmd == "encounters":
        configure()
        R.cmd_run(list(range(1, 13)), None, a.max_seconds)
    else:
        cmd_analyse()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
