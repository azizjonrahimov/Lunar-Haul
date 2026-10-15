"""Driving tables v0 (lunarsim-driving v1): the scripted expert over every ordered site pair (PLAN §5.4).

    python -m lunarsim.rover.tables --site connecting_ridge --seeds 20 --out data/driving/driving-v1.json

For every ordered pair of sites in data/terrain/<site>/sites.json (plus every pad position set: legs
"PAD_A@2->BASE" etc.) and every lighting case (sun azimuth 0, 90, 180, 270 deg, night), the expert's A* route
is planned once (routes do not depend on the autonomy level: every level's cap scales the cost grid
uniformly). The route is then driven by the fast leg integrator below for each autonomy level x RTT
{0, 4, 6, 8} s x N seeds, and lognormal fits (time, energy) and a Poisson rate (interventions) are stored.

Fast leg integrator (same physics functions as env.py, along the route at 5 m resolution):
    v      = v_cap(autonomy, RTT) * slope_speed_factor(slope) * lighting_factor(heading, sun, shadow) * u_leg
    ground = v * (1 - slip(grade));  t_move = sum(ds / ground);  E = sum(energy_wh(ds, grade, slip))
    stops  = floor(length / L) * t_stop  (teleop cadence / supervised approvals)
    interventions ~ Poisson(sum over segments of hazard * ds), each costing RTT + recovery
u_leg ~ lognormal(0, SPEED_SIGMA) per run is the run-to-run variability. Interventions use an Assumed hazard
(no interventions-per-km data exists for lunar rovers; B-13 replaces it with the learned driver's measured
rate). tests/test_rover.py checks the integrator against the step-by-step env on a flat leg.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from . import physics as R
from .expert import densify, plan

DRIVING_FORMAT = "lunarsim-driving"
RTTS = (0.0, 4.0, 6.0, 8.0)
LIGHTING = (0.0, 90.0, 180.0, 270.0, R.NIGHT)
SPEED_SIGMA = 0.10              # Assumed run-to-run variability of speed made good (lognormal sigma)
# intervention hazard per km (Assumed): base rate by autonomy + terrain terms
HAZARD_PER_KM = {"teleop": 0.05, "supervised": 0.10, "autonomous": 0.20}
HAZARD_SLOPE_PER_KM = 1.0       # extra per km driven on slopes above the nominal 15 deg
HAZARD_ROUGH_PER_KM = 1.0       # extra per km over cells rougher than half the collision proxy
HAZARD_SHADOW_MULT = 2.0        # hazard multiplier in shadow / at night (contrast; JSC lighting study)


def leg_profile(terrain, route: np.ndarray, sun_az_deg) -> Dict[str, np.ndarray]:
    """Per-segment quantities along a route densified to 5 m."""
    p = densify(np.asarray(route, float), 5.0)
    d = np.diff(p, axis=0)
    ds = np.hypot(d[:, 0], d[:, 1])
    mid = 0.5 * (p[1:] + p[:-1])
    z = terrain.height(p[:, 0], p[:, 1])
    grade = np.degrees(np.arctan2(np.diff(z), np.maximum(ds, 1e-9)))
    heading = np.degrees(np.arctan2(d[:, 0], d[:, 1])) % 360
    slope = terrain.slope(mid[:, 0], mid[:, 1])
    j, i = terrain.cell(mid[:, 0], mid[:, 1])
    if sun_az_deg is None:
        shadow = np.zeros(len(ds), bool)
    elif sun_az_deg == R.NIGHT:
        shadow = np.ones(len(ds), bool)
    else:
        shadow = terrain.shadow_grid(float(sun_az_deg))[j, i]
    rough = terrain.roughness20()[j, i]
    return {"ds": ds, "grade": grade, "heading": heading, "slope": slope, "shadow": shadow, "rough": rough,
            "length_m": float(ds.sum())}


def drive_profile(prof: Dict[str, np.ndarray], autonomy: str, rtt_s: float, sun_az_deg, rng: np.random.Generator,
                  n: int) -> Dict[str, np.ndarray]:
    """n stochastic runs of the leg. Returns arrays time_s, energy_wh, interventions (length n)."""
    ds, grade, slope = prof["ds"], prof["grade"], prof["slope"]
    sl = R.slip(grade)
    f = R.slope_speed_factor(slope) * R.lighting_factor(prof["heading"], sun_az_deg, prof["shadow"])
    v = R.speed_cap_mps(autonomy, rtt_s) * f * (1.0 - sl)
    blocked = (v <= 0) | (sl >= R.DIG_IN_SLIP)
    v = np.where(blocked, np.nan, v)
    t_det = float(np.nansum(ds / v))                      # blocked segments are covered by interventions
    every, stop_s = R.stop_plan(autonomy, rtt_s)
    stops = math.floor(prof["length_m"] / every) if math.isfinite(every) else 0
    e = float(np.sum(R.energy_wh(ds, grade, np.minimum(sl, 0.95))))
    km = ds / 1000.0
    haz = (HAZARD_PER_KM[autonomy] + HAZARD_SLOPE_PER_KM * (slope > R.ROVER["slope_nominal_deg"])
           + HAZARD_ROUGH_PER_KM * (prof["rough"] > 0.5 * R.INTERVENTION["roughness_m"]))
    haz = haz * np.where(prof["shadow"], HAZARD_SHADOW_MULT, 1.0)
    lam = float(np.sum(haz * km)) + float(np.sum(blocked))
    u = np.exp(rng.normal(0.0, SPEED_SIGMA, n))
    k = rng.poisson(lam, n)
    time_s = t_det / u + stops * stop_s + k * R.intervention_cost_s(rtt_s)
    energy = e * (1.0 + 0.05 * k)                         # Assumed: each intervention adds 5 % of the leg energy
    return {"time_s": time_s, "energy_wh": energy, "interventions": k.astype(float), "lambda": lam,
            "stops": stops, "t_move_s": t_det}


def _lognormal(x: np.ndarray) -> Dict[str, Any]:
    lx = np.log(np.maximum(x, 1e-12))
    return {"mu": float(lx.mean()), "sigma": float(lx.std(ddof=1)) if len(x) > 1 else 0.0, "dist": "lognormal",
            "mean": float(x.mean()), "p90": float(np.percentile(x, 90))}


def leg_table(terrain, a, b, autonomies, rtts, lighting, seeds: int, rng) -> Optional[Dict[str, Any]]:
    out: Dict[str, Any] = {"autonomy": {}, "route": {}}
    profs = {}
    for sun in lighting:
        route = plan(terrain, a, b, sun)
        if route is None:
            return None
        key = "night" if sun == R.NIGHT else f"{sun:g}"
        profs[key] = (sun, leg_profile(terrain, route, sun))
        p = profs[key][1]
        out["route"][key] = {"length_m": round(p["length_m"], 1),
                             "climb_m": round(float(np.sum(np.maximum(0, np.diff(terrain.height(*densify(route, 5.0).T))))), 1),
                             "max_slope_deg": round(float(p["slope"].max()), 1),
                             "shadow_fraction": round(float(p["shadow"].mean()), 3), "waypoints": len(route)}
    for au in autonomies:
        by_rtt = {}
        for rtt in rtts:
            by_light = {}
            for key, (sun, p) in profs.items():
                r = drive_profile(p, au, rtt, sun, rng, seeds)
                by_light[key] = {"time_h": _lognormal(r["time_s"] / 3600.0),
                                 "energy_kwh": _lognormal(r["energy_wh"] / 1000.0),
                                 "interventions": {"lambda": float(r["interventions"].mean()), "dist": "poisson"},
                                 "stops": int(r["stops"])}
            by_rtt[f"{rtt:g}"] = {"lighting": by_light}
        out["autonomy"][au] = {"rtt_s": by_rtt}
    return out


def legs_from_sites(sites: Dict[str, Any]) -> List[Tuple[str, Tuple[float, float], Tuple[float, float]]]:
    pts = {s["id"]: tuple(s["xy_m"]) for s in sites.get("sites", [])}
    legs = [(f"{a}->{b}", pts[a], pts[b]) for a in pts for b in pts if a != b]
    for D, pads in (sites.get("pads") or {}).items():
        items = pads.items() if isinstance(pads, dict) else ((p["id"], p["xy_m"]) for p in pads)
        for pid, xy in items:
            for b, q in pts.items():
                if b == pid:
                    continue
                legs.append((f"{pid}@{D}->{b}", tuple(xy), q))
                legs.append((f"{b}->{pid}@{D}", q, tuple(xy)))
    return legs


def build(terrain, sites: Dict[str, Any], seeds: int = 20, seed: int = 0, lighting=LIGHTING, rtts=RTTS,
          autonomies=R.AUTONOMY_LEVELS, policy: str = "expert-astar-purepursuit", progress: bool = False) -> Dict[str, Any]:
    rng = np.random.default_rng(seed)
    legs, skipped = {}, []
    todo = legs_from_sites(sites)
    t0 = time.time()
    for n, (name, a, b) in enumerate(todo, 1):
        if math.hypot(a[0] - b[0], a[1] - b[1]) < 1.0:
            skipped.append({"leg": name, "reason": "coincident end points"})
            continue
        tab = leg_table(terrain, a, b, autonomies, rtts, lighting, seeds, rng)
        if tab is None:
            skipped.append({"leg": name, "reason": "no route under the slope limit"})
        else:
            legs[name] = tab
        if progress and (n % 20 == 0 or n == len(todo)):
            print(f"  {n}/{len(todo)} legs ({time.time() - t0:.0f} s)", flush=True)
    return {
        "format": DRIVING_FORMAT, "version": 1, "terrain": terrain.site_id, "policy": policy, "seeds": seeds,
        "seed": seed, "rtt_s": [f"{r:g}" for r in rtts],
        "lighting": ["night" if s == R.NIGHT else f"{s:g}" for s in lighting],
        "units": {"time_h": "hours, lognormal over runs (mu, sigma of ln)", "energy_kwh": "traction kWh, lognormal",
                  "interventions": "Poisson rate per traverse"},
        "model": {"speed_cap_kmh": {**R.SPEED_CAP_KMH, "teleop": {f"{r:g}": round(R.teleop_move_kmh(r), 4) for r in rtts}},
                  "teleop_cadence_m": {f"{r:g}": round(R.teleop_cadence_m(r), 1) for r in rtts},
                  "teleop_stop_s": {f"{r:g}": R.teleop_stop_s(r) for r in rtts}, "supervised_stop": R.SUPERVISED_STOP,
                  "c_rr_eff": R.C_RR_EFF, "drive_eff": R.DRIVE_EFF, "mass_kg": R.ROVER["mass_kg"],
                  "speed_sigma": SPEED_SIGMA, "hazard_per_km": HAZARD_PER_KM, "intervention": R.INTERVENTION,
                  "flags": "see lunarsim/rover/physics.py; hazard model Assumed (no lunar interventions/km data)"},
        "skipped": skipped,
        "generated": {"tool": "lunarsim.rover.tables", "time": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat(),
                      "wallclock_s": round(time.time() - t0, 1)},
        "legs": legs,
    }


def main(argv=None):
    from ..terrain import Terrain
    p = argparse.ArgumentParser(description="driving tables v0 from the scripted expert")
    p.add_argument("--site", default="connecting_ridge")
    p.add_argument("--root", default=os.path.join("data", "terrain"))
    p.add_argument("--sites", default=None, help="sites.json (default: the pack's own)")
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default=os.path.join("data", "driving", "driving-v1.json"))
    a = p.parse_args(argv)
    t = Terrain(a.site, a.root)
    path = a.sites or os.path.join(t.path, "sites.json")
    if not os.path.exists(path):
        raise SystemExit(f"{path} not found: choose sites with `lunarsim terrain place` and write sites.json first")
    with open(path, encoding="utf-8") as f:
        sites = json.load(f)
    doc = build(t, sites, a.seeds, a.seed, progress=True)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f)
    print(f"wrote {a.out}: {len(doc['legs'])} legs ({len(doc['skipped'])} skipped) in {doc['generated']['wallclock_s']} s, "
          f"{os.path.getsize(a.out) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
