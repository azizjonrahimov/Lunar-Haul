"""Verification and validation checks for LunarSim.

Each check compares a simulator output with an independent reference: an
analytic formula, a published data point, or a conservation identity. A check
passes when the relative error is within its tolerance (1% unless the reference
itself is less precise). `run_all_checks()` returns a list of dicts that the
test-suite, the paper and the live viewer all use.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from typing import Callable, Dict, List

import numpy as np

from .engine import Simulation, Job, teleop_speed_kmh
from .entities import VEHICLE_CLASSES
from .scenario import Scenario, LUNAR_CYCLE_H, HOURS_PER_DAY, BulkFlow
from .world import build_default_world


@dataclass
class Check:
    name: str
    reference: float
    simulated: float
    tolerance: float      # relative tolerance (mode "rel") or absolute, in `unit` (mode "abs")
    unit: str
    basis: str
    passed: bool = False
    rel_error: float = float("nan")
    source: str = ""      # where the reference comes from (Phase 4 rows)
    mode: str = "rel"
    error: float = float("nan")     # the error the tolerance applies to (relative or absolute)
    skipped: str = ""     # non-empty: the check could not run here, and why (not a failure)

    def finish(self):
        self.rel_error = abs(self.simulated - self.reference) / max(abs(self.reference), 1e-12)
        self.error = abs(self.simulated - self.reference) if self.mode == "abs" else self.rel_error
        self.passed = bool(self.error <= self.tolerance)
        return self


# ---------------------------------------------------------------------------
# 1. Kinematics: travel time along a known path equals slope-weighted distance / speed
# ---------------------------------------------------------------------------
def check_travel_time() -> Check:
    w = build_default_world()
    sc = Scenario(fleet=[("A", "LTV", "autonomous", "A")], other_duty_share=0.0, failures=False,
                  landings_per_year={"CLPS": 0, "MK1": 0, "LARGE": 0})
    sim = Simulation(sc, lambda *a, **k: [], seed=0)
    v = sim.vehicles[0]
    # PAD_A -> BASE goes PAD_A - DEPOT - BASE, both flat edges
    d = w.distance_km("PAD_A", "BASE")
    ref = d / v.cls.speed_kmh  # flat, loaded, autonomous
    sim_h = sim.travel_h(v, "PAD_A", "BASE", loaded=True, team=False, t=0.0)
    return Check("Travel time on a flat two-edge path", ref, sim_h, 1e-9, "h",
                 "distance / speed; path PAD_A-DEPOT-BASE, both edges flat").finish()


def check_slope_penalty() -> Check:
    w = build_default_world()
    sc = Scenario(fleet=[("A", "LTV", "autonomous", "A")], other_duty_share=0.0, failures=False,
                  landings_per_year={"CLPS": 0, "MK1": 0, "LARGE": 0})
    sim = Simulation(sc, lambda *a, **k: [], seed=0)
    v = sim.vehicles[0]
    # SCI_1 -> PSR is a single steep edge: time = dist / (0.5 * speed)
    d = w.distance_km("SCI_1", "PSR")
    ref = d / (0.5 * v.cls.speed_kmh)
    return Check("Steep-edge travel time doubles", ref, sim.travel_h(v, "SCI_1", "PSR", True, False, 0.0),
                 1e-9, "h", "slope class 'steep' halves speed").finish()


# ---------------------------------------------------------------------------
# 2. Teleoperation model reproduces the NASA JSC trial speeds it was fitted to
# ---------------------------------------------------------------------------
def check_teleop_fit() -> List[Check]:
    data = {0.0: 3.24, 4.0: 2.56, 6.0: 2.03, 8.0: 1.76}   # km/h at RTT s (Litaker et al., TM-20240001217)
    out = []
    for rtt, v_obs in data.items():
        v_model = teleop_speed_kmh(rtt)
        out.append(Check(f"Teleoperated speed at {rtt:.0f} s RTT", v_obs, v_model, 0.01, "km/h",
                         "NASA JSC LTV teleoperation trial average speed").finish())
    return out


# ---------------------------------------------------------------------------
# 3. Night model: dark fraction of simulated time equals the parameter
# ---------------------------------------------------------------------------
def check_night_fraction() -> Check:
    sc = Scenario(night_fraction=0.15, landings_per_year={"CLPS": 0, "MK1": 0, "LARGE": 0})
    sim = Simulation(sc, lambda *a, **k: [], seed=0)
    ts = np.linspace(0, 10 * LUNAR_CYCLE_H, 200_001)
    dark = np.mean([sim.is_night(t) for t in ts])
    return Check("Dark share of time", 0.15, float(dark), 0.005, "fraction",
                 "night_fraction parameter; sampled over 10 cycles").finish()


# ---------------------------------------------------------------------------
# 4. Mass conservation: landed + bulk = delivered + stranded + backlog + pending
# ---------------------------------------------------------------------------
def check_mass_conservation(mechanism: Callable, seed: int = 3) -> Check:
    from .scenario import Scenario
    sc = Scenario(name="vv", landings_per_year={"CLPS": 4, "MK1": 3, "LARGE": 1},
                  fleet=[("NASA", "LTV", "supervised", "A"), ("CoA", "LTV", "supervised", "A"),
                         ("CoA", "HAUL", "supervised", "A"), ("CoB", "MICRO", "teleop", "A")],
                  bulk_flows=[BulkFlow("CONSTR", "BASE", 300, lot_kg=1000)], n_operators=3)
    sim = Simulation(sc, mechanism, seed=seed)
    sim.run()
    m = sim.metrics
    ready_total = m.ready_kg
    accounted = m.delivered_kg + m.stranded_kg + m.backlog_kg
    return Check(f"Mass conservation ({getattr(mechanism, '__name__', 'mech')})", ready_total, accounted, 1e-9, "kg",
                 "ready mass = delivered + stranded + backlog at horizon").finish()


# ---------------------------------------------------------------------------
# 5. Stranding rule: an item heavier than the best team is never moved
# ---------------------------------------------------------------------------
def check_stranding_rule() -> Check:
    from . import dispatch
    sc = Scenario(landings_per_year={"CLPS": 0, "MK1": 0, "LARGE": 6},
                  fleet=[("NASA", "LTV", "autonomous", "A"), ("NASA", "LTV", "autonomous", "A")],
                  other_duty_share=0.0, failures=False)
    sim = Simulation(sc, dispatch.marketplace, seed=5)
    sim.run()
    heavy = [c for c in sim.all_cargo if c.mass_kg > 3000 and c.cls != "return"]
    moved = sum(1 for c in heavy if c.t_delivered is not None)
    return Check("Items above team capacity (2 x 1,500 kg) never delivered", 0.0, float(moved), 0.0, "items",
                 f"{len(heavy)} items heavier than 3,000 kg in six large landings").finish()


# ---------------------------------------------------------------------------
# 6. Common random numbers: identical demand across mechanisms for one seed
# ---------------------------------------------------------------------------
def check_common_random_numbers() -> Check:
    from . import dispatch
    sc = Scenario(landings_per_year={"CLPS": 4, "MK1": 3, "LARGE": 1},
                  fleet=[("NASA", "LTV", "supervised", "A"), ("CoA", "HAUL", "supervised", "A")])
    sigs = []
    for mech in (dispatch.inhouse, dispatch.pooled_greedy, dispatch.central_assign, dispatch.marketplace):
        sim = Simulation(sc, mech, seed=11)
        sim.run()
        land = [(round(c.t_landed, 6), round(c.mass_kg, 6), c.dest) for c in sim.all_cargo if c.cls not in ("return", "bulk")]
        sigs.append(tuple(sorted(land)))
    same = float(all(s == sigs[0] for s in sigs))
    return Check("Same landed manifest for every mechanism (seed 11)", 1.0, same, 0.0, "bool",
                 "demand drawn from a stream separate from operations").finish()


# ---------------------------------------------------------------------------
# 7. Queueing: single vehicle, Poisson single-item arrivals -> M/G/1 (Pollaczek-Khinchine)
# ---------------------------------------------------------------------------
def check_mg1_queue(n_years: int = 20) -> Check:
    """One autonomous LTV, no night, no faults, no duties; items arrive one per
    landing (CLPS payload fixed by making the manifest a single 100 kg crate) at a
    Poisson rate; destination fixed. The mean wait in queue should follow
    W_q = lambda * E[S^2] / (2 (1 - rho)) where S is the job duration."""
    from . import dispatch
    from .scenario import LANDER_TYPES, LanderType, CARGO_CLASSES
    import lunarsim.scenario as scn
    # a dedicated tiny lander whose manifest is exactly one crate
    saved_lt = dict(LANDER_TYPES)
    saved_classes = list(CARGO_CLASSES)
    try:
        LANDER_TYPES["ONE"] = LanderType("ONE", (99.0, 99.0), (0.0, 0.0), True, 100)
        scn.CARGO_CLASSES[:] = [("consumables", (99.0, 100.0), {"BASE": 1.0}, 1, 1.0)]
        saved_ret = scn.RETURN_ITEM_PROB
        scn.RETURN_ITEM_PROB = 0.0
        rate_per_year = 900.0
        sc = Scenario(landings_per_year={"ONE": rate_per_year}, cargo_owners=["NASA"],
                      fleet=[("NASA", "LTV", "autonomous", "A")], night_fraction=0.0, failures=False,
                      other_duty_share=0.0, horizon_h=n_years * 365 * HOURS_PER_DAY, n_operators=4)
        sim = Simulation(sc, dispatch.pooled_greedy, seed=21)
        sim.run()
        # service time: vehicle at BASE after the first job; each job = BASE->pad empty + load + pad->BASE + unload
        v = sim.vehicles[0]
        w = sim.world
        pads = w.pads
        # average over the two pads (equally likely)
        S = []
        for pad in pads:
            job = Job([v], [sim.all_cargo[0]], ["BASE"])
            v.location = "BASE"
            sim.all_cargo[0].origin = pad
            S.append(sim.job_plan(job, 0.0)[0])
        S = np.array(S)
        lam = rate_per_year / (365 * HOURS_PER_DAY)
        ES, ES2 = S.mean(), (S ** 2).mean()
        rho = lam * ES
        Wq_ref = lam * ES2 / (2 * (1 - rho))
        # simulated wait in queue = pickup time - ready time; pickup happens when a vehicle is assigned
        waits = np.array([c.t_picked - c.t_ready for c in sim.all_cargo if c.t_picked is not None and c.cls != "return"])
        # ignore the first 2% as warm-up (negligible here) and the return items (none: return share applies but origin not pad? keep filter)
        Wq_sim = float(waits.mean())
        return Check("M/G/1 mean queue wait (Pollaczek-Khinchine)", Wq_ref, Wq_sim, 0.05, "h",
                     f"rho={rho:.3f}, lambda={lam*24:.2f}/day, E[S]={ES:.2f} h, n={len(waits)} items over {n_years} years").finish()
    finally:
        LANDER_TYPES.clear()
        LANDER_TYPES.update(saved_lt)
        scn.CARGO_CLASSES[:] = saved_classes
        scn.RETURN_ITEM_PROB = saved_ret


# ---------------------------------------------------------------------------
# 8. Fleet cost identity
# ---------------------------------------------------------------------------
def check_fleet_cost() -> Check:
    from . import dispatch
    sc = Scenario(fleet=[("NASA", "LTV", "supervised", "A"), ("CoA", "HAUL", "supervised", "A"), ("CoB", "MICRO", "teleop", "A")],
                  landings_per_year={"CLPS": 1, "MK1": 0, "LARGE": 0})
    sim = Simulation(sc, dispatch.pooled_greedy, seed=1)
    out = sim.run()
    ref = sum(VEHICLE_CLASSES[c].unit_cost_musd / VEHICLE_CLASSES[c].life_years for _, c, _, _ in sc.fleet)
    return Check("Annual fleet amortisation", ref, out["fleet_cost_musd"], 1e-9, "$M",
                 "sum of unit cost / calendar life over the fleet").finish()


def run_all_checks() -> List[Dict]:
    from . import dispatch
    checks: List[Check] = [check_travel_time(), check_slope_penalty()]
    checks += check_teleop_fit()
    checks += [check_night_fraction(), check_mass_conservation(dispatch.marketplace),
               check_mass_conservation(dispatch.pooled_greedy), check_stranding_rule(),
               check_common_random_numbers(), check_fleet_cost(), check_mg1_queue()]
    return [asdict(c) for c in checks]


# ---------------------------------------------------------------------------
# Phase 4 data checks (B-39): the new data files against the code that made them and independent references
# ---------------------------------------------------------------------------
def _repo(*parts) -> str:
    import os
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), *parts)


def _skip(name: str, unit: str, basis: str, source: str, why: str) -> Check:
    return Check(name, float("nan"), float("nan"), 0.0, unit, basis, False, float("nan"), source, "abs", float("nan"), why)


def check_catalogue_engine() -> Check:
    """B-30: the catalogue's capacities, speeds, night operation, payloads and descent constants equal the engine's."""
    from . import catalog
    from .lander.classes import CLASSES
    from .scenario import LANDER_TYPES
    n = 3 * len(VEHICLE_CLASSES) + len(LANDER_TYPES) * 2 + len(CLASSES) * 2 * len(catalog.GATE_KEYS)
    mism = catalog.engine_mismatches()
    return Check("Catalogue values equal the engine constants", float(n), float(n - len(mism)), 0.0, "values",
                 "lunarsim/catalog-v1.json vs entities.VEHICLE_CLASSES, scenario.LANDER_TYPES, lander/classes.py "
                 "(values and flags)", source="lunarsim/catalog.py engine_mismatches()", mode="abs").finish()


def check_scene_reproduces_trace() -> List[Check]:
    """B-31: a scene package of the P2 v2 sample trace reproduces its trips, landings and delivered kg."""
    import json, os, tempfile
    from . import scene as SCN
    trace_path = _repo("data", "sample_traces", "P2_marketplace_seed3_v2.json")
    src = "data/sample_traces/P2_marketplace_seed3_v2.json -> lunarsim/scene.py build/read"
    if not (os.path.isfile(trace_path) and os.path.isfile(_repo("data", "driving", "routes-v1.json"))):
        return [_skip("Scene package reproduces the trace", "", "", src, "sample trace or routes-v1.json missing")]
    with open(trace_path, encoding="utf-8") as f:
        trace = json.load(f)
    with tempfile.TemporaryDirectory() as d:
        SCN.build(trace, d)
        got = SCN.replay_counts(SCN.read(d))
    ci = {c: i for i, c in enumerate(trace["cargo_columns"])}
    kg = round(sum(r[ci["mass_kg"]] for r in trace["cargo"] if r[ci["t_delivered"]] is not None), 3)
    trips = sum(1 for j in trace["jobs"] if j["kind"] != "reposition")
    return [Check("Scene package: trips equal the trace's", float(trips), float(got["trips"]), 0.0, "trips",
                  "job records in the trace (repositions excluded) vs distinct jobs in the package", source=src, mode="abs").finish(),
            Check("Scene package: landings equal the trace's", float(len(trace["landings"])), float(got["landings"]), 0.0,
                  "landings", "landing events", source=src, mode="abs").finish(),
            Check("Scene package: delivered kg equals the trace's", kg, got["delivered_kg"], 0.0, "kg",
                  "sum of delivered masses in the trace's cargo table (0.1 kg) vs the package's deliveries", source=src,
                  mode="abs").finish()]


def check_trajectory_replay() -> Check:
    """B-33: an exported descent episode replays in the Python env to < 1e-6 m."""
    import json, os
    import numpy as np
    path = _repo("data", "policies", "trajectories-v1.json")
    src = "data/policies/trajectories-v1.json (CLPS, classical law, p50 episode) -> lunar/Descent-v0"
    name = "Descent trajectory replays to the stored positions"
    if not os.path.isfile(path):
        return _skip(name, "m", "", src, "trajectories-v1.json missing")
    try:
        from .lander import trajectories as TJ
        controller, obs_v, variant, _ = TJ.controller_for("law", "classical", None)
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        ep = next(e for p in doc["pilots"] if p["cls"] == "CLPS" and p["pilot"] == "classical"
                  for e in p["episodes"] if e["pick"] == "p50")
        rec = TJ.record_episode("CLPS", controller, obs_v, variant, ep["seed"])
    except ImportError as e:
        return _skip(name, "m", "", src, f"needs the [ml] extra ({e.name or e})")
    d = float(np.max(np.abs(np.asarray(rec["pos"]) - np.asarray(ep["pos_m"]))))
    return Check(name, 0.0, d, 1e-6, "m", f"seed {ep['seed']}: max |position difference| over "
                 f"{len(ep['pos_m'])} samples (stored to 1e-6 m)", source=src, mode="abs").finish()


def check_ephemeris_horizons() -> List[Check]:
    """B-40: the stored Earth track at BASE (SPICE) agrees with an independent JPL Horizons month."""
    import gzip, json, os
    import numpy as np
    hpath = _repo("data", "comms", "connecting_ridge", "horizons_2028-01_base.json")
    tpath = _repo("data", "comms", "connecting_ridge", "earth_track-v1.json.gz")
    src = "data/comms/connecting_ridge/horizons_2028-01_base.json (JPL Horizons API) vs earth_track-v1.json.gz (SPICE)"
    if not (os.path.isfile(hpath) and os.path.isfile(tpath)):
        return [_skip("Earth elevation at BASE vs JPL Horizons", "deg", "", src, "Horizons month or Earth track missing")]
    with open(hpath, encoding="utf-8") as f:
        hz = json.load(f)
    with open(tpath, "rb") as f:
        tr = json.loads(gzip.decompress(f.read()))
    n = len(hz["rows"])
    el_h = np.array([r[2] for r in hz["rows"]])
    az_h = np.array([r[1] for r in hz["rows"]])
    el_t = np.asarray(tr["elevation_cdeg"][:n]) / 100.0                  # both start 2028-01-01 00:00 UTC, hourly
    az_t = (np.asarray(tr["grid_bearing_cdeg"][:n]) / 100.0 - tr["lon_deg"]) % 360.0
    d_el = float(np.max(np.abs(el_t - el_h)))
    d_az = float(np.max(np.abs((az_t - az_h + 180.0) % 360.0 - 180.0)))
    basis = (f"max over {n} hours of January 2028; the track is stored in centidegrees and BASE sits within ~30 m of "
             "the Horizons site coordinates")
    return [Check("Earth elevation at BASE vs JPL Horizons", 0.0, d_el, 0.01, "deg", basis, source=src, mode="abs").finish(),
            Check("Earth azimuth at BASE vs JPL Horizons", 0.0, d_az, 0.01, "deg", basis, source=src, mode="abs").finish()]


def check_comms_always_baseline() -> Check:
    """B-41: with comms mode 'always' the engine reproduces the baseline (canonical md5 of compare P2-default x 3)."""
    import hashlib, io
    import pandas as pd
    from .config import library
    from .engine import run
    from .cli import _mechanism
    want = "739e9ba72c1563f4ae508ebc1dfd9938"
    sc = library()["P2-default"].with_(comms={"mode": "always"})
    rows = []
    for name in ("inhouse", "pooled_greedy", "central_assign", "marketplace"):     # as `lunarsim compare`
        fn, kw = _mechanism(name)
        for s in range(3):
            r = run(sc, fn, seed=s, **kw)
            r["mechanism"] = name
            rows.append(r)
    buf = io.StringIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    df = pd.read_csv(io.StringIO(buf.getvalue()), float_precision="round_trip")
    from .comms import SUMMARY_PREFIXES
    drop = [c for c in df.columns if c.startswith(SUMMARY_PREFIXES)
            or c in ("delivered_nonbulk_kg", "cost_per_landed_kg_usd")]
    md5 = hashlib.md5(df.drop(columns=drop).to_csv(index=False, lineterminator=chr(10)).encode()).hexdigest()
    return Check("Earth-link rule 'always' reproduces the baseline", 1.0, float(md5 == want), 0.0, "match",
                 f"canonical md5 of compare P2-default x 3 seeds x 4 job rules: {md5[:12]} vs {want[:12]}",
                 source="tests/test_phase3_engine.py BASELINE_V2_CANONICAL_MD5", mode="abs").finish()


def run_phase4_checks() -> List[Dict]:
    checks: List[Check] = [check_catalogue_engine()]
    checks += check_scene_reproduces_trace()
    checks.append(check_trajectory_replay())
    checks += check_ephemeris_horizons()
    checks.append(check_comms_always_baseline())
    return [asdict(c) for c in checks]


if __name__ == "__main__":
    for c in run_all_checks():
        flag = "PASS" if c["passed"] else "FAIL"
        print(f"{flag}  {c['name']:60s} ref={c['reference']:.4g} sim={c['simulated']:.4g} err={100*c['rel_error']:.3f}%  tol={100*c['tolerance']:.1f}%")
