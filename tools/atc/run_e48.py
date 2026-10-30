"""E48 (B-81, P3, exploratory H10): what Lunar ATC puts inside each vehicle, measured on our implementation.

    python tools/atc/run_e48.py design      # -> data/scenarios/E48-design.json (before the first measurement)
    python tools/atc/run_e48.py measure [--max-seconds 480]   # resumable steps -> .cache/atc/e48/*.json
    python tools/atc/run_e48.py build       # -> results/E48_sizing.json (schema: paper/p3/PLACEHOLDERS.md)

Measured on this laptop (Python + numpy, single core): CPU time per safety_check call (the Move check every vehicle runs
at 10 Hz; the base computer's Reserve check for BASE) and per auction round (one C_AUCTION dispatch call: what the
deciding computer runs), the on-robot data (reservation-table copy, ledger copy, bid policy), messages per robot-hour
and the ledger per year from runs at 1x, 4x and 8x the fleet (C_AUCTION with the road layer, dispatch to a fixed
point), and failover from C_LEADER runs over an MTBF sweep with a check that no cargo item is ever assigned twice.
Derived: flight-processor times (laptop time x factor), link budgets per class on B-70's mesh geometry. The lander
carries the radio unit and the landing-announcement part only (PREREG change 7): it is not a class here.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import pickle
import statistics
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5")):
    if p not in sys.path:
        sys.path.insert(0, p)

DESIGN = os.path.join(ROOT, "data", "scenarios", "E48-design.json")
CACHE = os.path.join(ROOT, ".cache", "atc", "e48")
OUT = os.path.join(ROOT, "results", "E48_sizing.json")
CLASSES = ("LTV1", "CARGO", "SMALL", "HOPPER", "BASE")

DESIGN_DOC = {
    "experiment": "E48 (B-81), P3, exploratory H10",
    "H10": "the safety check, the bidding and the radio traffic of Lunar ATC fit a flight-class computer (measured CPU "
           "time, memory and bytes per robot-hour, scaled to a reference radiation-tolerant processor with a stated "
           "factor) and a 16 kbit/s-class link for 20 robots (PREREG change 1)",
    "classes": {"LTV1": ["LTV1_CLV1", "LTV1_PEGASUS"], "CARGO": ["CARGO_FLEX", "CARGO_EAGLE"], "SMALL": ["MAPP_SMALL"],
                "HOPPER": ["HOPPER_MOONFALL", "HOPPER_MICRONOVA"],
                "BASE": "the base computer at the habitat (reservation table, auction, ledger)",
                "lander": "radio unit and landing-announcement part only (PREREG change 7); not sized here"},
    "laptop": {"processor": "Intel Core i5-10500H (6 cores, 2.5 GHz base, 4.5 GHz turbo)",
               "benchmark": 27000.0, "benchmark_name": "CoreMark per core",
               "benchmark_note": "Assumed: 4.5 GHz turbo (Intel spec) x 6.0 CoreMark/MHz (typical for this core "
                                 "generation; no published CoreMark for this chip found), range 4-7 CoreMark/MHz"},
    "flight": {"processor": "Frontgrade Gaisler GR740 (rad-hard quad-core LEON4FT, 250 MHz)",
               "benchmark": 492.5, "benchmark_name": "CoreMark per core",
               "source": "Cobham Gaisler, GR740 benchmark results, ESA DSP Day 2016: 1.97 CoreMark/MHz/core x 250 MHz; "
                         "https://indico.esa.int/event/102/contributions/62/ ; product brief: "
                         "https://download.gaisler.com/products/gr740/doc/Product%20Brief_GR740_20230908_rev1.pdf",
               "memory_mb": 256, "memory_flag": "Assumed: SDRAM of a typical GR740 single-board computer",
               "factor": round(27000.0 / 492.5, 1),
               "factor_range": [round(4.0 * 4500 / 492.5, 1), round(7.0 * 4500 / 492.5, 1)],
               "factor_note": "laptop CoreMark per core / flight CoreMark per core; the measured times are Python + "
                              "numpy, a flight implementation in C would be faster, so the scaled times are an upper "
                              "bound in that respect (Assumed)"},
    "targets": {"robots": 20, "safety_hz": 10, "link_kbps_20_robots": 16, "bytes_per_s_per_robot": 100,
                "market_mb_per_day": 1, "flag": "Assumed: the proposal's estimates (B-81 task)"},
    "radio": {"freq_ghz": {"LTV1": 2.4, "CARGO": 2.4, "SMALL": 2.4, "HOPPER": 2.4, "BASE": 2.4},
              "tx_power_w": {"LTV1": 1.0, "CARGO": 1.0, "SMALL": 0.25, "HOPPER": 0.5, "BASE": 5.0},
              "antenna_gain_dbi": 3.0, "bandwidth_mhz": 1.0, "noise_figure_db": 5.0, "implementation_margin_db": 10.0,
              "worst_hop_m": 5000.0, "flag": "Assumed (frequency as B-70's provisional 2.4 GHz; powers per class; "
                                            "worst hop = the mesh's 5 km range)"},
    "power_w": {"LTV1": 12.0, "CARGO": 12.0, "SMALL": 6.0, "HOPPER": 8.0, "BASE": 25.0,
                "flag": "Assumed: a GR740-class board (~4-5 W) plus the radio at the stated transmit power and duty; "
                        "BASE adds the mast radio and storage"},
    "messages": {"bytes": {"status": 48, "reservation_request": 32, "grant": 32, "release": 16, "bid": 40,
                           "award": 32, "claim": 32, "landing_announcement": 64, "ledger_entry": 128},
                 "status_hz": 1.0, "flag": "Assumed byte layouts (ids, times, positions as 32-bit values, headers 8 B); "
                                           "status at 1 Hz per R9"},
    "failover": {"mtbf_levels_h": [500.0, 2000.0, 8000.0], "repair_h": 24.0, "reelect_h": 0.5, "seeds": [1, 2, 3, 4, 5],
                 "regime": "C_LEADER, message loss 0.1, 30 % load, 1x, one year", "flag": "Assumed (B-72 defaults; sweep)"},
    "runs": {"multiples": [1, 4, 8], "horizon_days": {"1": 365, "4": 90, "8": 60}, "seeds": [1, 2],
             "regime": "C_AUCTION, message loss 0.1, roads atc (15 % single-lane), dispatch to a fixed point"},
}


def cmd_design():
    os.makedirs(os.path.dirname(DESIGN), exist_ok=True)
    with open(DESIGN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(DESIGN_DOC, f, indent=1)
        f.write("\n")
    print("design:", os.path.relpath(DESIGN, ROOT))


def _cache(name):
    return os.path.join(CACHE, name + ".json")


def _save(name, obj):
    os.makedirs(CACHE, exist_ok=True)
    json.dump(obj, open(_cache(name), "w"), indent=1)


def _scen(m, horizon_days, regime_roads=True):
    import run_phase5 as R
    from lunarsim.atc import p5 as P5
    sc = P5.build("3eq", k=R.E43_K30 * m, team_lift_share=0.10)
    sc = sc.with_(fleet=list(sc.fleet) * m, n_operators=sc.n_operators * m, horizon_h=float(horizon_days) * 24.0)
    p5 = dict(sc.p5, dispatch_fixpoint=True)
    if regime_roads:
        p5["roads"] = {"mode": "atc", "single_share": R.SINGLE_SHARE, "bay_km": 1.0}
        sc = sc.with_(plume=dict(R.E43_PLUME))
    return sc.with_(p5=p5)


def step_safety():
    """CPU time per safety_check call (Move, one vehicle) with inputs drawn from the E44 fixtures, per class speed;
    BASE: the Reserve check against a reservation list of realistic length (from the 1x run)."""
    from lunarsim.atc import safety as S
    import glob
    moves = []
    for p in sorted(glob.glob(os.path.join(ROOT, "data", "atc", "encounter_fixtures", "E44_fixture_*.json.gz"))):
        doc = json.load(gzip.open(p, "rt"))
        for st in doc["steps"]:
            m = st["move"]
            for i in range(len(m["v"])):
                moves.append({k: (np.inf if v[i] is None else v[i]) if isinstance(v, list) else v for k, v in m.items()})
    rng = np.random.default_rng(48)
    vc = json.load(open(os.path.join(ROOT, "lunarsim", "atc", "vehicles-p5.json"), encoding="utf-8"))["classes"]
    speeds = {g: max(vc[n]["params"]["speed_kmh"]["value"] for n in names) / 3.6        # fastest of the class
              for g, names in DESIGN_DOC["classes"].items() if isinstance(names, list)}
    out = {}
    for cls, vc in speeds.items():
        ts = []
        for j in rng.integers(0, len(moves), 20000):
            mv = moves[int(j)]
            arg = S.Move(v=np.array(mv["v"]), a_prop=np.array(mv["a_prop"]), dt=0.1, theta=np.array(mv["theta"]),
                         mu=np.array(mv["mu"]), v_class=np.array(vc), sight=np.array(mv["sight"]),
                         gap_lead=np.array(mv["gap_lead"]), v_lead=np.array(mv["v_lead"]),
                         d_stop=np.array(mv["d_stop"]), d_crew=np.array(mv["d_crew"]),
                         must_exit=np.array(bool(mv["must_exit"])), a_max=0.2, d_crew_any=np.array(mv["d_crew_any"]))
            t0 = time.perf_counter_ns()
            S.safety_check(None, arg)
            ts.append((time.perf_counter_ns() - t0) / 1000.0)
        out[cls] = {"median": round(statistics.median(ts), 2), "p99": round(float(np.quantile(ts, 0.99)), 2),
                    "n": len(ts)}
    # BASE: Reserve against a list of entries like the busiest resource of a 1x year
    table = json.load(open(_cache("runs"))).get("busiest_resource_entries", 200) if os.path.isfile(_cache("runs")) else 200
    entries = [(float(i), float(i) + 0.5, 1 if i % 2 else -1, "A" if i % 3 else "B", i) for i in range(int(table))]
    ts = []
    for j in range(20000):
        t0 = time.perf_counter_ns()
        S.safety_check(entries, S.Reserve("r", float(j % 400), float(j % 400) + 0.3, 99999, "C", d=1))
        ts.append((time.perf_counter_ns() - t0) / 1000.0)
    out["BASE"] = {"median": round(statistics.median(ts), 2), "p99": round(float(np.quantile(ts, 0.99)), 2), "n": len(ts),
                   "check": "Reserve", "entries": int(table)}
    _save("safety", out)
    print("safety:", {k: (v["median"], v["p99"]) for k, v in out.items()})


def step_safety_batch():
    """One safety_check call over 20 vehicles at once (arrays of 20): what a base or leader computer checking every
    robot pays per robot, compared with 20 single calls."""
    from lunarsim.atc import safety as S
    rng = np.random.default_rng(49)
    ts = []
    for _ in range(5000):
        n = 20
        arg = S.Move(v=rng.uniform(0, 2.8, n), a_prop=rng.uniform(-0.8, 0.2, n), dt=0.1, theta=np.zeros(n),
                     mu=np.full(n, 0.45), v_class=np.full(n, 2.42), sight=np.full(n, 1e4),
                     gap_lead=rng.uniform(5, 80, n), v_lead=rng.uniform(0, 2.8, n), d_stop=rng.uniform(1, 200, n),
                     d_crew=np.full(n, np.inf), must_exit=np.zeros(n, bool), a_max=0.2, d_crew_any=np.full(n, np.inf))
        t0 = time.perf_counter_ns()
        S.safety_check(None, arg)
        ts.append((time.perf_counter_ns() - t0) / 1000.0)
    out = {"robots": 20, "median_us": round(statistics.median(ts), 2), "p99_us": round(float(np.quantile(ts, 0.99)), 2),
           "n": len(ts), "per_robot_p99_us": round(float(np.quantile(ts, 0.99)) / 20, 2)}
    _save("safety_batch", out)
    print("safety batch:", out)


def step_runs(max_s):
    """C_AUCTION + roads atc at 1x (365 d), 4x (90 d), 8x (60 d), seeds 1-2: auction-round time, messages, ledger,
    the reservation table and its 24 h window."""
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    import run_phase5 as R
    res = json.load(open(_cache("runs"))) if os.path.isfile(_cache("runs")) else {"rows": {}}
    t_start = time.time()
    for m in DESIGN_DOC["runs"]["multiples"]:
        for seed in DESIGN_DOC["runs"]["seeds"]:
            key = f"{m}:{seed}"
            if key in res["rows"]:
                continue
            if time.time() - t_start > max_s * 0.5:
                print("runs: time limit; rerun")
                _save("runs", res)
                return False
            sc = _scen(m, DESIGN_DOC["runs"]["horizon_days"][str(m)])
            mech = G.mechanism("C_AUCTION")
            rounds = []

            def timed(sim, cand, free, **kw):
                t0 = time.perf_counter()
                out = mech(sim, cand, free, **kw)
                rounds.append(time.perf_counter() - t0)
                return out
            for a in ("anticipates", "supports_team", "regime", "__name__"):
                if hasattr(mech, a):
                    setattr(timed, a, getattr(mech, a))
            sim = Simulation(sc, timed, seed=seed, mech_kwargs={"start_year": 2028, "loss": R.LOSS})
            jobs = [0]
            real_start = sim._start_job

            def start(job, _rs=real_start):
                n0 = len(sim.waiting)
                _rs(job)
                if len(sim.waiting) < n0:
                    jobs[0] += 1
            sim._start_job = start
            t0 = time.time()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                s = sim.run()
            run_s = time.time() - t0
            H = sc.horizon_h
            robots = len(sim.vehicles)
            tab = sim.roads.table if sim.roads is not None else {}
            busiest = max((len(v) for v in tab.values()), default=0)
            win = {k: [e for e in v if e[1] >= H - 24.0 and e[0] <= H + 24.0] for k, v in tab.items()}
            res["rows"][key] = {"multiple": m, "seed": seed, "robots": robots, "horizon_h": H, "run_s": round(run_s, 1),
                                "rounds_ms": [round(1000 * x, 3) for x in rounds if x > 0][:20000],
                                "msgs_per_robot_h_auction": float(s.get("atc_msgs_per_robot_h", float("nan"))),
                                "road_traversals": float(s.get("road_traversals", 0.0)),
                                "road_jobs": float(s.get("road_jobs", 0.0)), "jobs_started": jobs[0],
                                "landings": len(sim.landing_schedule),
                                "table_bytes": len(pickle.dumps(tab)), "table_24h_bytes": len(pickle.dumps(win)),
                                "busiest_resource_entries": busiest}
            res["busiest_resource_entries"] = max(res.get("busiest_resource_entries", 0), busiest)
            _save("runs", res)
            print(f"runs {key}: {run_s:.0f} s, rounds {len(rounds)}, jobs {jobs[0]}", flush=True)
    print("runs: done")
    return True


def step_failover(max_s):
    """C_LEADER (loss 0.1) at 1x over a year per MTBF level and seed: base down share, time without a decider, the
    number of base recoveries (state merges) and cargo items assigned more than once (must be 0)."""
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    import run_phase5 as R
    res = json.load(open(_cache("failover"))) if os.path.isfile(_cache("failover")) else {}
    t_start = time.time()
    fo = DESIGN_DOC["failover"]
    for mtbf in fo["mtbf_levels_h"]:
        for seed in fo["seeds"]:
            key = f"{mtbf:g}:{seed}"
            if key in res:
                continue
            if time.time() - t_start > max_s * 0.8:
                print("failover: time limit; rerun")
                _save("failover", res)
                return False
            sc = _scen(1, 365, regime_roads=False)
            sim = Simulation(sc, G.mechanism("C_LEADER"), seed=seed,
                             mech_kwargs={"start_year": 2028, "loss": R.LOSS, "base_mtbf_h": mtbf,
                                          "base_repair_h": fo["repair_h"], "reelect_h": fo["reelect_h"]})
            seen, twice = set(), [0]
            real_start = sim._start_job

            def start(job, _rs=real_start):
                n0 = len(sim.waiting)
                ids = [id(c) for c in job.items + job.backhaul]
                _rs(job)
                if len(sim.waiting) < n0:
                    for i in ids:
                        if i in seen:
                            twice[0] += 1
                        seen.add(i)
            sim._start_job = start
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                s = sim.run()
            atc = sim.atc
            H = sc.horizon_h
            r = float(fo["reelect_h"])
            no_leader = sum(min(b, H, a + r) - a for a, b in atc.base_down) / H if atc is not None else 0.0
            res[key] = {"down_share": float(s.get("atc_decider_down_share", float("nan"))),
                        "base_down_share": sum(min(b, H) - a for a, b in atc.base_down if a < H) / H,
                        "no_leader_share": no_leader, "merges": len(atc.base_down),
                        "jobs_assigned_twice": twice[0], "items_assigned": len(seen)}
            _save("failover", res)
            print(f"failover {key}: {res[key]}", flush=True)
    print("failover: done")
    return True


def step_links():
    """Per class: free-space link budget at the worst (5 km) hop, Shannon rate with an implementation margin, latency
    for a 1 s decision, and the share of route samples in direct view of the BASE mast (B-70 mesh) for the class's
    antenna height."""
    from lunarsim.atc import regimes as G
    from lunarsim.atc.radio import DEFAULT_D_MAX_M
    rd = DESIGN_DOC["radio"]
    rm = G._mesh()
    seen = {}
    for h, c in ((2.5, 0), (1.0, 1)):
        ok = (rm.mast_clear_dm[c] >= 0) & (rm.mast_d <= DEFAULT_D_MAX_M)
        seen[h] = set(rm.mast_j[ok].tolist()) | {rm.base}
    n_samples = len(G._samples()["ids"]) if isinstance(G._samples().get("ids"), dict) else None
    from lunarsim.atc import roads as RD
    _, sdoc = RD._load()
    total = len(sdoc["samples"])
    ant = {"LTV1": G.ANT_ROVER_M, "CARGO": G.ANT_ROVER_M, "SMALL": G.ANT_SMALL_M, "HOPPER": G.ANT_SMALL_M,
           "BASE": G.ANT_MAST_M}
    safety = json.load(open(_cache("safety")))
    out = {}
    for cls in CLASSES:
        f = rd["freq_ghz"][cls] * 1e9
        pt_dbm = 10 * math.log10(rd["tx_power_w"][cls] * 1000.0)
        fspl = 20 * math.log10(rd["worst_hop_m"]) + 20 * math.log10(f) - 147.55
        pr = pt_dbm + 2 * rd["antenna_gain_dbi"] - fspl
        noise = -174 + 10 * math.log10(rd["bandwidth_mhz"] * 1e6) + rd["noise_figure_db"]
        snr_db = pr - noise - rd["implementation_margin_db"]
        rate_kbps = rd["bandwidth_mhz"] * 1e3 * math.log2(1 + 10 ** (snr_db / 10))
        hops = 1 if cls == "BASE" else 3
        tx_ms = 100 * 8 / max(rate_kbps, 1e-6)
        proc_ms = safety.get(cls, safety["LTV1"])["p99"] / 1000.0 * DESIGN_DOC["flight"]["factor"]
        latency = hops * (10.0 + tx_ms) + proc_ms
        h = ant[cls]
        share = 1.0 if cls == "BASE" else len(seen[2.5 if h >= 2.5 else 1.0]) / total
        out[cls] = {"antenna_m": h, "freq_ghz": rd["freq_ghz"][cls], "tx_power_w": rd["tx_power_w"][cls],
                    "worst_hop_kbps": round(rate_kbps, 1), "snr_db_worst_hop": round(snr_db, 1),
                    "latency_budget_ms": round(latency, 1), "latency_hops": hops,
                    "reachable_share": round(share, 3),
                    "reachable_note": "share of route samples in direct view of the BASE mast within 5 km (B-70 mesh)"
                                      if cls != "BASE" else "the mast itself"}
    _save("links", out)
    print("links:", {k: (v["worst_hop_kbps"], v["reachable_share"]) for k, v in out.items()})


def cmd_measure(max_s):
    t0 = time.time()
    if not os.path.isfile(_cache("runs")) or not json.load(open(_cache("runs"))).get("done"):
        if not step_runs(max_s):
            return
        r = json.load(open(_cache("runs")))
        r["done"] = True
        _save("runs", r)
    if not os.path.isfile(_cache("safety")):
        step_safety()
    if not os.path.isfile(_cache("links")):
        step_links()
    if not os.path.isfile(_cache("safety_batch")):
        step_safety_batch()
    if time.time() - t0 > max_s * 0.6:
        print("measure: rerun for failover")
        return
    step_failover(max_s - (time.time() - t0))


def cmd_build():
    d = DESIGN_DOC
    runs = json.load(open(_cache("runs")))["rows"]
    safety = json.load(open(_cache("safety")))
    links = json.load(open(_cache("links")))
    fo = json.load(open(_cache("failover")))
    mb = d["messages"]["bytes"]
    msgs, bph, ledger = {}, {}, {}
    per_type = {}
    for m in d["runs"]["multiples"]:
        rows = [r for r in runs.values() if r["multiple"] == m]
        rh = [r["robots"] * r["horizon_h"] for r in rows]
        auction = float(np.mean([r["msgs_per_robot_h_auction"] for r in rows]))
        trav = float(np.mean([r["road_traversals"] / (r["robots"] * r["horizon_h"]) for r in rows]))
        land = float(np.mean([r["landings"] / r["horizon_h"] for r in rows]))
        jobs_y = float(np.mean([r["jobs_started"] / r["horizon_h"] * 8766.0 for r in rows]))
        rates = {"status": d["messages"]["status_hz"] * 3600.0, "reservation_request": trav, "grant": trav,
                 "release": trav, "auction (bid, award, claim)": auction, "landing_announcement": land}
        per_type[str(m)] = {k: round(v, 3) for k, v in rates.items()}
        msgs[str(m)] = round(sum(rates.values()), 1)
        auction_bytes = auction * (mb["bid"] + mb["award"] + mb["claim"]) / 3.0
        bph[str(m)] = round(rates["status"] * mb["status"] + trav * (mb["reservation_request"] + mb["grant"]
                            + mb["release"]) + auction_bytes + land * mb["landing_announcement"], 1)
        ledger[str(m)] = round(jobs_y * mb["ledger_entry"] / 1e6, 3)
    rounds = [x for r in runs.values() for x in r["rounds_ms"]]
    rnd = {"median": round(statistics.median(rounds), 3), "p99": round(float(np.quantile(rounds, 0.99)), 3),
           "n": len(rounds)}
    # on-robot data: 24 h reservation-table window, ledger copy for a year, bid policy, safety constants
    one = [r for r in runs.values() if r["multiple"] == 1]
    tab24 = max(r["table_24h_bytes"] for r in one) / 1e6
    pol = sum(os.path.getsize(os.path.join(ROOT, "data", "policies", f)) for f in ("atc_bid_linear_v1.json",
                                                                                    "atc_bid_v1.json")) / 1e6
    led1 = ledger["1"]
    classes = {}
    for cls in CLASSES:
        mem = tab24 + led1 + (pol if cls != "BASE" else pol) + 0.05
        if cls == "BASE":
            mem = max(r["table_bytes"] for r in one) / 1e6 + led1 + pol + 0.05
        classes[cls] = {"cpu_safety_check_us": safety[cls], "cpu_auction_round_ms": rnd,
                        "peak_memory_mb": round(mem, 3),
                        "peak_memory_note": ("24 h reservation-table window + a year's ledger copy + bid policies + "
                                             "working data (0.05 MB)") if cls != "BASE" else
                                            "the full year's reservation table + ledger + policies + working data",
                        "power_w": {"value": d["power_w"][cls], "flag": "Assumed"},
                        "link": links[cls]}
    by = {}
    for lvl in d["failover"]["mtbf_levels_h"]:
        rows = [v for k, v in fo.items() if k.split(":")[0] == f"{lvl:g}"]
        by[f"{lvl:g}"] = {"down_share": round(float(np.mean([r["base_down_share"] for r in rows])), 4),
                          "no_leader_share": round(float(np.mean([r["no_leader_share"] for r in rows])), 5),
                          "reelect_s": d["failover"]["reelect_h"] * 3600.0,
                          "merges": round(float(np.mean([r["merges"] for r in rows])), 2),
                          "jobs_assigned_twice": int(sum(r["jobs_assigned_twice"] for r in rows)),
                          "items_assigned": int(sum(r["items_assigned"] for r in rows)), "seeds": len(rows)}
    run_s = [r["run_s"] for r in runs.values()]
    out = {"experiment": "E48 (B-81, P3, exploratory H10)", "design": "data/scenarios/E48-design.json",
           "note": __doc__.split("\n\n")[1].strip(),
           "laptop": {k: d["laptop"][k] for k in ("processor", "benchmark", "benchmark_name")},
           "flight": {k: d["flight"][k] for k in ("processor", "benchmark", "factor", "factor_range", "memory_mb", "source")},
           "targets": {k: v for k, v in d["targets"].items() if k != "flag"},
           "classes": classes,
           "messages": {"bytes_per_type": mb, "per_robot_hour": msgs, "per_robot_hour_by_type": per_type,
                        "bytes_per_robot_hour": bph},
           "ledger_mb_per_year": ledger,
           "failover": {"mtbf_levels_h": d["failover"]["mtbf_levels_h"], "by_mtbf": by},
           "runs": {"n": len(runs) + len(fo), "multiples": d["runs"]["multiples"],
                    "run_s_mean": round(float(np.mean(run_s)), 1),
                    "cpu_h": round((sum(run_s) + 0.0) / 3600.0, 3)}}
    # H10 numbers (as P3's build composes them)
    worst = max(CLASSES[:-1], key=lambda c: classes[c]["cpu_safety_check_us"]["p99"])
    p99 = classes[worst]["cpu_safety_check_us"]["p99"]
    share = p99 * 1e-6 * d["flight"]["factor"] * d["targets"]["safety_hz"]
    batch = json.load(open(_cache("safety_batch")))
    out["cpu_safety_check_batch20_us"] = batch
    out["h10"] = {"worst_class_safety": worst, "safety_core_share_flight_per_robot_10hz": round(share, 4),
                  "safety_core_share_note": "on board: p99 laptop time of one call x factor x 10 Hz, as a share of one "
                                            "flight core (each robot checks only itself); measured in Python + numpy, "
                                            "so an upper bound for a C implementation",
                  "safety_core_share_flight_base_20_robots_batched": round(batch["p99_us"] * 1e-6 * d["flight"]["factor"]
                                                                           * d["targets"]["safety_hz"], 4),
                  "peak_memory_mb_max_robot": max(classes[c]["peak_memory_mb"] for c in CLASSES[:-1]),
                  "link_kbps_needed_20_robots": round(bph["1"] * 20 * 8 / 3600.0 / 1000.0, 2),
                  "market_mb_per_day": round(per_type["1"]["auction (bid, award, claim)"] * 24.0 * 20
                                             * (mb["bid"] + mb["award"] + mb["claim"]) / 3.0 / 1e6, 4)}
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1, default=float)
        f.write("\n")
    print(json.dumps(out["h10"], indent=1), json.dumps(out["messages"]["per_robot_hour"]), json.dumps(ledger))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["design", "measure", "build"])
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 100, exit=True)
    {"design": cmd_design, "measure": lambda: cmd_measure(a.max_seconds), "build": cmd_build}[a.cmd]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
