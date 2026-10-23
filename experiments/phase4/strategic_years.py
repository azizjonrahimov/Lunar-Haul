"""Why strategic driving under direct links collapses in 2028 (B-55; paper R-1, referee E17).

    python experiments/phase4/strategic_years.py [--seeds 8] [--max-seconds 540]
        -> results/E21_strategic_years.json, results/E21_strategic_years_monthly.csv

E21 stage A, all-supervised fleet, strategic policy, direct links only (the r2 cell). The link-series year enters
the engine only through Scenario.comms.start_year; the demand (landings, manifests) comes from the seed. So the
test is a swap: every seed 0..S-1 runs with every start year 2028-2031 (S x 4 runs, single process, ~1 s each).
Per run it records the stranding events: intervention waits longer than STRAND_H (the strategic rule: each
intervention of the driving table's draw sits at a uniformly drawn route sample of the leg and waits for that
sample's next link-up in the hourly sample series, which repeats after 2031), with the rover, the hour, the
length, the leg and the route sample, and whether the wait ends inside the simulated year. The calendar part reads
the link files: monthly linked fraction at the sites, the pads and the stranding samples, the share of all route
samples dark for a whole month, 2028-2031, and where Earth stands (seen from BASE) when the worst samples see it. Consistency: each seed at its own E21 year reproduces its row of
results/E21a_comms_autonomy_r2.csv; the file also stores the E21 means by start year.
"""
from __future__ import annotations

import argparse
import calendar
import faulthandler
import gzip
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from experiments.phase4 import run_phase4 as R  # noqa: E402
from lunarsim import Simulation  # noqa: E402
from lunarsim import comms as C  # noqa: E402

OUT = os.path.join(ROOT, "results", "E21_strategic_years.json")
OUT_CSV = os.path.join(ROOT, "results", "E21_strategic_years_monthly.csv")
E21_CSV = os.path.join(ROOT, "results", "E21a_comms_autonomy_r2.csv")
LINK = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1.json")
SAMPLES = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1-samples.json.gz")
TRACK = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_track-v1.json.gz")
YEARS = (2028, 2029, 2030, 2031)
STRAND_H = 24.0
PLACES = ("BASE", "DEPOT", "CONSTR", "POWER", "SCI_1", "ISRU", "PSR", "PAD_A@1", "PAD_B@1")
TOP_SAMPLES = 10


def _r(x, d=3):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), d)


def month_edges_h(year: int) -> List[float]:
    """Engine hours (0 = 1 January of the start year) of the first hour of each calendar month, plus the year end."""
    e, h = [], 0
    for m in range(1, 13):
        e.append(h)
        h += 24 * calendar.monthrange(year, m)[1]
    return e + [h]


def series_month_edges(step_h: float) -> List[int]:
    """Epoch indices of every month start 2028-01 .. 2031-12 (and the end) in a series starting 2028-01-01."""
    out, h = [], 0
    for y in YEARS:
        for m in range(1, 13):
            out.append(int(round(h / step_h)))
            h += 24 * calendar.monthrange(y, m)[1]
    return out + [int(round(h / step_h))]


def cell():
    tag, sc, mn, mf, kw = next(c for c in R.e21a_cells("r2") if c[0]["mix"] == "supervised_strategic"
                               and c[0]["comms"] == "dte")
    return tag, sc, mf, kw


# ---------------------------------------------------------------------------------------------------------
# runs
# ---------------------------------------------------------------------------------------------------------
def run_one(seed: int, year: int) -> Dict[str, Any]:
    _, sc, mech, kw = cell()
    sc = sc.with_(comms=dict(sc.comms, start_year=year))
    sim = Simulation(sc, mech, seed=seed, mech_kwargs=dict(kw))
    cm = sim.comms
    log: Dict[tuple, int] = {}
    orig = cm._sample_wait

    def logged(a, b, u, t):                                  # remember which route sample each wait sits at
        w = orig(a, b, u, t)
        ids = cm.el.leg_samples(f"{cm.name(a)}->{cm.name(b)}")
        log[(f"{a}->{b}", round(float(t), 4))] = ids[min(len(ids) - 1, int(u * len(ids)))]
        return w

    cm._sample_wait = logged
    out = sim.run()
    H = float(sc.horizon_h)
    rovers = [v.id for v in sim.vehicles]
    events = []
    for veh, t0, t1, where, kind in cm.waits:
        if kind == "intervention" and t1 - t0 > STRAND_H:
            events.append({"rover": veh, "t0_h": t0, "t1_h": t1, "wait_h": t1 - t0, "leg": where,
                           "sample": log.get((where, round(float(t0), 4))), "resumes_in_year": t1 <= H})
    edges = month_edges_h(year)
    stranded = []
    for m in range(12):
        lo, hi = edges[m], min(edges[m + 1], H)
        s = sum(max(0.0, min(e["t1_h"], hi) - max(e["t0_h"], lo)) for e in events)
        stranded.append(s / (len(rovers) * (hi - lo)) if hi > lo else float("nan"))
    first = {}
    for e in sorted(events, key=lambda e: e["t0_h"]):
        first.setdefault(e["rover"], e["t0_h"])
    items = [c for c in sim.all_cargo if c.t_ready <= H]
    land_m = np.histogram([t for t, _, _ in sim.landing_schedule], bins=edges)[0]
    item_m = np.histogram([c.t_ready for c in items], bins=edges)[0]
    landings_key = tuple((round(t, 6), lt.name, pad) for t, lt, pad in sim.landing_schedule)
    items_key = tuple(sorted((round(c.t_landed, 6), c.dest, c.priority, round(c.mass_kg, 3)) for c in items))
    return {"seed": seed, "year": year, "delivered_t_in_year": out.get("delivered_kg_in_horizon", float("nan")) / 1000.0,
            "blackout_wait_vehicle_h": out.get("blackout_wait_vehicle_h"), "delay_prio1_mean_h": out.get("delay_prio1_mean_h"),
            "n_rovers": len(rovers), "events": events, "stranded_share_by_month": stranded, "first_strand_h": first,
            "landings_by_month": land_m.tolist(), "items_by_month": item_m.tolist(),
            "items_by_dest": dict(Counter(c.dest for c in items)), "items_kg": sum(c.mass_kg for c in items),
            "landings_key": landings_key, "items_key": items_key}


# ---------------------------------------------------------------------------------------------------------
# calendar from the link files
# ---------------------------------------------------------------------------------------------------------
def monthly_fraction(mask: np.ndarray, edges: List[int]) -> List[float]:
    return [float(mask[a:b].mean()) for a, b in zip(edges[:-1], edges[1:])]


def sky_part(samples_of_interest: List[int]) -> Dict[str, Any]:
    """Where Earth stands (seen from BASE, earth_track-v1) when each sample is linked, and how many hours per year
    Earth stands in that part of the sky (bearing and elevation at least the 5th percentile of the linked hours)."""
    t = json.loads(gzip.decompress(open(TRACK, "rb").read()))
    el = np.array(t["elevation_cdeg"]) / 100.0
    brg = np.array(t["grid_bearing_cdeg"]) / 100.0
    s = json.loads(gzip.decompress(open(SAMPLES, "rb").read()))
    yr = series_month_edges(1.0)[::12]
    per_year = lambda m: [int(m[a:b].sum()) for a, b in zip(yr[:-1], yr[1:])]
    out = {"earth_at_base": {str(y): {"max_elevation_deg": _r(el[a:b].max(), 2),
                                      "share_above_horizon_plane": _r((el[a:b] > 0).mean(), 3),
                                      "bearing_range_when_above_5.5deg": [_r(brg[a:b][el[a:b] > 5.5].min(), 1),
                                                                          _r(brg[a:b][el[a:b] > 5.5].max(), 1)]}
                             for y, a, b in zip(YEARS, yr[:-1], yr[1:])}, "samples": {}}
    for i in samples_of_interest:
        m = C.windows_to_mask(C.decode_windows(s["series"][s["samples"][i]["w"][0]]), len(el))
        if not m.any():
            continue
        box = (brg >= np.percentile(brg[m], 5)) & (el >= np.percentile(el[m], 5))
        out["samples"][str(i)] = {"bearing_deg_when_linked": [_r(brg[m].min(), 1), _r(float(np.median(brg[m])), 1), _r(brg[m].max(), 1)],
                                  "elevation_deg_when_linked": [_r(el[m].min(), 2), _r(el[m].max(), 2)],
                                  "linked_hours_by_year": per_year(m), "earth_in_its_sky_box_hours_by_year": per_year(box)}
    return out


def calendar_part(samples_of_interest: List[int]) -> Dict[str, Any]:
    el = C.EarthLink.load(LINK, samples=True)
    n10 = el.n
    e10 = series_month_edges(el.step_h)
    places = {}
    for p in PLACES:
        w = C.decode_windows(el.doc["points"][p]["windows"]["dte"]["any_part"])
        places[p] = monthly_fraction(C.windows_to_mask(w, n10), e10)
    s = el.samples
    nh = int(s["time"]["n"])
    eh = series_month_edges(1.0)
    used = sorted({i for ids in s["legs"].values() for i in ids})
    masks = {i: C.windows_to_mask(C.decode_windows(s["series"][s["samples"][i]["w"][0]]), nh) for i in used}
    frac = np.array([monthly_fraction(masks[i], eh) for i in used])            # samples x 48 months
    linked_ever = np.array([masks[i].any() for i in used])
    top = {str(i): monthly_fraction(masks[i], eh) for i in samples_of_interest}
    return {"places": places, "samples": top,
            "route_samples": {"n": len(used), "never_linked": int((~linked_ever).sum()),
                              "dark_whole_month_share": (frac[linked_ever] == 0).mean(axis=0).tolist(),
                              "mean_linked_fraction": frac[linked_ever].mean(axis=0).tolist()},
            "xy": {str(i): s["samples"][i]["xy_m"] for i in samples_of_interest}}


# ---------------------------------------------------------------------------------------------------------
def build(seeds: int = 8, log=print) -> Dict[str, Any]:
    t0 = time.time()
    runs = []
    for s in range(seeds):
        for y in YEARS:
            runs.append(run_one(s, y))
        log(f"  seed {s}: " + ", ".join(f"{r['year']} {r['delivered_t_in_year']:.0f} t" for r in runs[-4:])
            + f" ({time.time() - t0:.0f} s)")
    by = lambda y: [r for r in runs if r["year"] == y]
    # 1. swap: demand fixed by the seed, only the year changes
    landings_same = all(len({r["landings_key"] for r in runs if r["seed"] == s}) == 1 for s in range(seeds))
    items_same = all(len({r["items_key"] for r in runs if r["seed"] == s}) == 1 for s in range(seeds))
    delivered = {str(y): [_r(r["delivered_t_in_year"], 1) for r in sorted(by(y), key=lambda r: r["seed"])] for y in YEARS}
    # E21 consistency: each seed at its own year reproduces its r2 row
    e21 = pd.read_csv(E21_CSV, float_precision="round_trip")
    e21 = e21[(e21["mix"] == "supervised_strategic") & (e21["comms"] == "dte")]
    own = []
    for s in range(seeds):
        row = e21[e21["seed"] == s].iloc[0]
        r = next(r for r in runs if r["seed"] == s and r["year"] == int(row["start_year"]))
        own.append(abs(r["delivered_t_in_year"] - float(row["delivered_t_in_year"])) < 1e-9
                   and abs(r["blackout_wait_vehicle_h"] - float(row["blackout_wait_vehicle_h"])) < 1e-6)
    e21_by_year = {str(int(y)): {"n": int(len(g)), "delivered_t_in_year": _r(g["delivered_t_in_year"].mean(), 3),
                                 "blackout_wait_vehicle_h": _r(g["blackout_wait_vehicle_h"].mean(), 1),
                                 "delay_prio1_mean_h": _r(g["delay_prio1_mean_h"].mean(), 1)}
                   for y, g in e21.groupby("start_year")}
    # 2. stranding events
    strand = {}
    sample_hours: Dict[int, float] = defaultdict(float)
    leg_hours: Dict[str, float] = defaultdict(float)
    leg_year: Dict[str, Dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for y in YEARS:
        rs = by(y)
        ev = [e for r in rs for e in r["events"]]
        H = 8760.0
        for e in ev:
            leg_year[e["leg"]][y] += (min(e["t1_h"], H) - e["t0_h"]) / len(rs)
            if y == 2028 and e["sample"] is not None:
                sample_hours[e["sample"]] += min(e["t1_h"], H) - e["t0_h"]
                leg_hours[e["leg"]] += min(e["t1_h"], H) - e["t0_h"]
        firsts = [h for r in rs for h in r["first_strand_h"].values()]
        never = [e for e in ev if not e["resumes_in_year"]]
        stranded_rovers = [len(r["first_strand_h"]) for r in rs]
        months = np.nanmean(np.array([r["stranded_share_by_month"] for r in rs]), axis=0)
        strand[str(y)] = {
            "runs": len(rs), "events_gt_24h_per_run": _r(len(ev) / len(rs), 2),
            "stranded_rover_hours_per_run": _r(sum(min(e["t1_h"], H) - e["t0_h"] for e in ev) / len(rs), 0),
            "share_not_resuming_in_year": _r(len(never) / len(ev) if ev else float("nan"), 3),
            "median_wait_h": _r(float(np.median([e["wait_h"] for e in ev])) if ev else None, 0),
            "rovers_stranded_at_least_once_mean": _r(float(np.mean(stranded_rovers)), 2),
            "first_strand_h_median": _r(float(np.median(firsts)) if firsts else None, 0),
            "first_strand_h_by_seed": {str(r["seed"]): sorted(_r(h, 0) for h in r["first_strand_h"].values()) for r in rs},
            "stranded_fleet_share_by_month": [_r(v, 3) for v in months],
            "delivered_t_in_year_mean": _r(float(np.mean([r["delivered_t_in_year"] for r in rs])), 1),
        }
    top = [i for i, _ in sorted(sample_hours.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_SAMPLES]]
    cal = calendar_part(top)
    # 3. demand by month (seeds averaged; identical across years for a seed by construction, checked)
    dem = {str(y): {"landings_by_month": np.mean([r["landings_by_month"] for r in by(y)], axis=0).round(2).tolist(),
                    "items_by_month": np.mean([r["items_by_month"] for r in by(y)], axis=0).round(2).tolist(),
                    "items_kg_mean": _r(float(np.mean([r["items_kg"] for r in by(y)])), 0)} for y in YEARS}
    # E21's own year assignment (seed mod 4): do the 2028 seeds have different demand? (from the swap runs)
    own_runs = [r for r in runs if r["year"] == 2028 + r["seed"] % 4]
    dem_e21 = {str(y): {"seeds": [r["seed"] for r in own_runs if r["year"] == y],
                        "landings_mean": _r(float(np.mean([sum(r["landings_by_month"]) for r in own_runs if r["year"] == y])), 2),
                        "items_mean": _r(float(np.mean([sum(r["items_by_month"]) for r in own_runs if r["year"] == y])), 1)}
               for y in YEARS}
    months_2028 = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    dark = np.array(cal["route_samples"]["dark_whole_month_share"]).reshape(4, 12)
    doc = {
        "description": "Why the E21 cell 'all supervised, strategic, direct links only' delivers far less when the link "
                       "series starts in 2028 (experiments/phase4/strategic_years.py, B-55).",
        "cell": {"stage": "A", "mix": "supervised_strategic", "comms": "dte", "criterion": "any_part",
                 "rule": "each intervention (driving table's count per leg) sits at a uniformly drawn route sample "
                         "of the leg and waits there for that sample's next link-up (hourly direct series, repeating "
                         "after 2031); planning does not foresee these waits (lunarsim/comms.py)",
                 "stranding": f"an intervention wait longer than {STRAND_H:g} h"},
        "e21_by_start_year": e21_by_year,
        "swap": {"design": f"seeds 0-{seeds - 1} x start years 2028-2031: the demand is fixed by the seed, only the "
                           "link-series year changes",
                 "landings_identical_across_years": landings_same,
                 "manifests_identical_across_years": items_same,
                 "manifests_note": "landing times, lander types and pads are drawn before the run; each lander's "
                                   "manifest is drawn when it lands, from the engine's one random stream, which the run "
                                   "also uses, so with a different link year the manifests differ in detail but come "
                                   "from the same distribution",
                 "delivered_t_in_year": delivered,
                 "delivered_t_in_year_mean": {y: _r(float(np.mean(v)), 1) for y, v in delivered.items()},
                 "seeds_lowest_in_2028": int(sum(min(range(4), key=lambda k: delivered[str(YEARS[k])][s]) == 0
                                                 for s in range(seeds))),
                 "own_year_runs_reproduce_e21": all(own)},
        "stranding": strand,
        "stranding_2028_top_samples": [{"sample": i, "xy_m": cal["xy"][str(i)], "stranded_rover_hours": _r(sample_hours[i], 0),
                                        "monthly_linked_2028_2031": [_r(v, 3) for v in cal["samples"][str(i)]]}
                                       for i in top],
        "stranding_2028_top_legs": [{"leg": k, "stranded_rover_hours": _r(v, 0)}
                                    for k, v in sorted(leg_hours.items(), key=lambda kv: (-kv[1], kv[0]))[:10]],
        "stranded_rover_hours_per_run_by_leg": {k: {str(y): _r(leg_year[k].get(y, 0.0), 0) for y in YEARS}
                                                for k in sorted(leg_year, key=lambda k: -sum(leg_year[k].values()))[:8]},
        "sky": sky_part(top[:3]),
        "calendar": {"months": [f"{y}-{m:02d}" for y in YEARS for m in range(1, 13)],
                     "places_linked_fraction": {p: [_r(v, 3) for v in f] for p, f in cal["places"].items()},
                     "route_samples": {"n": cal["route_samples"]["n"], "never_linked": cal["route_samples"]["never_linked"],
                                       "dark_whole_month_share": [_r(v, 3) for v in cal["route_samples"]["dark_whole_month_share"]],
                                       "mean_linked_fraction": [_r(v, 3) for v in cal["route_samples"]["mean_linked_fraction"]]},
                     "dark_whole_month_share_jan_apr": {str(y): _r(float(dark[k, :4].mean()), 3) for k, y in enumerate(YEARS)}},
        "demand_by_year_swap": dem,
        "demand_by_e21_year": dem_e21,
        "month_names": months_2028,
        "generated": {"tool": "experiments/phase4/strategic_years.py", "seeds": seeds,
                      "link_file": "data/comms/connecting_ridge/earth_link-v1.json (+ its samples file)"},
    }
    rows = []
    for k, ym in enumerate(doc["calendar"]["months"]):
        y, m = int(ym[:4]), int(ym[5:])
        row = {"month": ym, "year": y, "m": m,
               "route_samples_dark_share": doc["calendar"]["route_samples"]["dark_whole_month_share"][k],
               "route_samples_linked_mean": doc["calendar"]["route_samples"]["mean_linked_fraction"][k],
               "stranded_fleet_share_if_start_this_year": strand[str(y)]["stranded_fleet_share_by_month"][m - 1],
               "landings_mean": dem[str(y)]["landings_by_month"][m - 1]}
        row.update({f"linked_{p}": doc["calendar"]["places_linked_fraction"][p][k] for p in PLACES})
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT_CSV, index=False, lineterminator="\n")
    with open(OUT, "wb") as f:
        f.write((json.dumps(doc, indent=1) + "\n").encode("utf-8"))
    log(f"wrote {os.path.relpath(OUT, ROOT)} and {os.path.relpath(OUT_CSV, ROOT)} in {time.time() - t0:.0f} s")
    return doc


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    if a.max_seconds > 0:
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    build(a.seeds)


if __name__ == "__main__":
    main()
