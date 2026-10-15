"""Run the full experiment suite and save one CSV per experiment in results/.

Usage:  python experiments/run_all.py [exp_name ...]
Each cell is replicated over N_SEEDS seeds with common random numbers (the demand
sample path for seed s is identical across mechanisms and most factor levels).
"""
import os, sys, time, itertools, warnings, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
warnings.filterwarnings("ignore")
from multiprocessing import Pool
import numpy as np
import pandas as pd

from lunarsim import run, dispatch, Scenario, BulkFlow
from experiments.scenarios import PHASES, OWNERS

N_SEEDS = 30
RESULTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
os.makedirs(RESULTS, exist_ok=True)

MECHS = {
    "inhouse": (dispatch.inhouse, {}),
    "pooled_greedy": (dispatch.pooled_greedy, {}),
    "central_assign": (dispatch.central_assign, {"batch_h": 1.0}),
    "marketplace": (dispatch.marketplace, {}),
}
ABLATIONS = {
    "marketplace": (dispatch.marketplace, {}),
    "no_bundling": (dispatch.marketplace_no_bundling, {}),
    "no_consolidate": (dispatch.marketplace_no_consolidate, {}),
    "no_team_lift": (dispatch.marketplace_no_team, {}),
    "no_backhaul": (dispatch.marketplace_no_backhaul, {}),
    "no_night_aware": (dispatch.marketplace_no_night, {}),
    "no_priority": (dispatch.marketplace_no_priority, {}),
    "no_anticipate": (dispatch.marketplace_no_anticipate, {}),
}

LTV = lambda o, a="supervised", s="A": (o, "LTV", a, s)
HAUL = lambda o, a="supervised", s="A": (o, "HAUL", a, s)
MICRO = lambda o, a="teleop", s="A": (o, "MICRO", a, s)


def _job(args):
    tag, sc, mech_name, mech, kw, seed = args
    out = run(sc, mech, seed=seed, **kw)
    out.update(tag)
    out["mechanism"] = mech_name
    return out


def run_cells(name, cells, seeds=N_SEEDS, procs=None):
    """cells: list of (tag_dict, scenario, mech_name, mech_fn, mech_kwargs)."""
    path = os.path.join(RESULTS, f"{name}.csv")
    jobs = [(tag, sc, mn, mf, kw, s) for (tag, sc, mn, mf, kw) in cells for s in range(seeds)]
    t0 = time.time()
    with Pool(procs or max(1, os.cpu_count() - 2)) as pool:
        rows = pool.map(_job, jobs, chunksize=4)
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
    print(f"[{name}] {len(jobs)} runs in {time.time()-t0:.0f}s -> {path}")
    return df


# ---------------------------------------------------------------------------
# E1: phases x mechanisms (+ an unconstrained-fleet bound)
# ---------------------------------------------------------------------------
def e1():
    cells = []
    for ph, sc in PHASES.items():
        for mn, (mf, kw) in MECHS.items():
            cells.append(({"exp": "E1", "phase": ph}, sc, mn, mf, kw))
        # bound: a very large autonomous fleet with no other duties and no faults
        big = sc.with_(fleet=[LTV("NASA", "autonomous")] * 12 + [HAUL("NASA", "autonomous")] * 4,
                       other_duty_share=0.0, failures=False, n_operators=8)
        cells.append(({"exp": "E1", "phase": ph}, big, "unconstrained_bound", dispatch.marketplace, {}))
    return run_cells("E1_phases", cells)


# ---------------------------------------------------------------------------
# E2: fleet-size sweep at Phase-2 demand (minimum fleet for a service level)
# ---------------------------------------------------------------------------
from lunarsim.phases import FLEETS  # noqa: E402  (Phase-2 fleet-size variants; shared with lunarsim.config.library)


def e2():
    base = PHASES["P2"]
    cells = []
    for n, fleet in FLEETS.items():
        sc = base.with_(fleet=fleet, n_operators=max(2, n // 2))
        for mn, (mf, kw) in MECHS.items():
            cells.append(({"exp": "E2", "n_vehicles": n}, sc, mn, mf, kw))
    return run_cells("E2_fleet_size", cells)


# ---------------------------------------------------------------------------
# E3: market thickness - number of companies sharing a fixed fleet
# ---------------------------------------------------------------------------
def e3():
    base = PHASES["P2"]
    cells = []
    for n_comp in (1, 2, 3, 4, 6):
        comps = [f"Co{i}" for i in range(n_comp)]
        fleet = [LTV(comps[i % n_comp]) for i in range(6)]
        fleet[3] = HAUL(comps[3 % n_comp])
        owners = [comps[i % n_comp] for i in range(8)]
        for duty in (0.0, 0.3, 0.6):
            sc = base.with_(fleet=fleet, cargo_owners=owners, other_duty_share=duty, n_operators=3)
            for mn in ("inhouse", "marketplace"):
                mf, kw = MECHS[mn]
                cells.append(({"exp": "E3", "n_companies": n_comp, "other_duty": duty}, sc, mn, mf, kw))
    return run_cells("E3_thickness", cells)


# ---------------------------------------------------------------------------
# E4: heavy cargo - the capability gap
# ---------------------------------------------------------------------------
def e4():
    cells = []
    fleets = {
        "LTVs only": [LTV("NASA"), LTV("NASA"), LTV("CoA"), LTV("CoB")],
        "LTVs + 1 hauler": [LTV("NASA"), LTV("NASA"), LTV("CoA"), HAUL("CoB")],
        "LTVs + 2 haulers": [LTV("NASA"), LTV("CoA"), HAUL("CoA"), HAUL("CoB")],
    }
    for ph in ("P2", "P3"):
        for fname, fleet in fleets.items():
            sc = PHASES[ph].with_(fleet=fleet, n_operators=3)
            for mn in ("pooled_greedy", "marketplace"):
                mf, kw = MECHS[mn]
                cells.append(({"exp": "E4", "phase": ph, "fleet": fname}, sc, mn, mf, kw))
            cells.append(({"exp": "E4", "phase": ph, "fleet": fname}, sc, "marketplace_no_team",
                          dispatch.marketplace_no_team, {}))
    return run_cells("E4_heavy_cargo", cells)


# ---------------------------------------------------------------------------
# E5: autonomy level, latency and operator pool
# ---------------------------------------------------------------------------
def e5():
    base = PHASES["P2"]
    cells = []
    fleet_tpl = [("NASA", "LTV"), ("NASA", "LTV"), ("CoA", "LTV"), ("CoA", "HAUL"), ("CoB", "MICRO")]
    for autonomy in ("teleop", "supervised", "autonomous"):
        fleet = [(o, c, autonomy, "A") for o, c in fleet_tpl]
        for rtt_extra in (0.0, 2.4, 5.4, 13.4, 600.0, 1320.0):   # total RTT = 2.6 + extra
            for n_ops in (1, 2, 4):
                sc = base.with_(fleet=fleet, ground_delay_s=rtt_extra, n_operators=n_ops)
                mf, kw = MECHS["marketplace"]
                cells.append(({"exp": "E5", "autonomy": autonomy, "rtt_s": 2.6 + rtt_extra,
                               "n_operators": n_ops}, sc, "marketplace", mf, kw))
    return run_cells("E5_autonomy_latency", cells, seeds=20)


# ---------------------------------------------------------------------------
# E6: cargo interface standards
# ---------------------------------------------------------------------------
def e6():
    base = PHASES["P2"]
    cells = []
    # half the fleet accepts only the common standard A; the other half accepts A and B
    fleet = [LTV("NASA", s="A"), LTV("NASA", s="A|B"), LTV("CoA", s="A"), HAUL("CoA", s="A|B"), MICRO("CoB", s="A")]
    for share in (0.5, 0.75, 0.9, 1.0):
        sc = base.with_(fleet=fleet, common_standard_share=share, n_operators=3)
        for mn in ("inhouse", "pooled_greedy", "marketplace"):
            mf, kw = MECHS[mn]
            cells.append(({"exp": "E6", "common_share": share}, sc, mn, mf, kw))
    return run_cells("E6_standards", cells)


# ---------------------------------------------------------------------------
# E7: environment robustness - night, reliability, bulk flows
# ---------------------------------------------------------------------------
def e7():
    base = PHASES["P2"].with_(fleet=FLEETS[5], n_operators=3)
    cells = []
    for nf in (0.1, 0.15, 0.3, 0.5):
        for mn in ("pooled_greedy", "marketplace"):
            mf, kw = MECHS[mn]
            cells.append(({"exp": "E7", "factor": "night_fraction", "level": nf}, base.with_(night_fraction=nf), mn, mf, kw))
    for mm in (0.25, 0.5, 1.0, 2.0):
        for mn in ("pooled_greedy", "marketplace"):
            mf, kw = MECHS[mn]
            cells.append(({"exp": "E7", "factor": "mtbf_mult", "level": mm}, base.with_(mtbf_mult=mm), mn, mf, kw))
    for bt in (0, 500, 1500, 3000):
        flows = [] if bt == 0 else [BulkFlow("CONSTR", "BASE", bt * 0.6, lot_kg=1000), BulkFlow("CONSTR", "ISRU", bt * 0.4, lot_kg=1000)]
        for mn in ("pooled_greedy", "marketplace"):
            mf, kw = MECHS[mn]
            cells.append(({"exp": "E7", "factor": "bulk_t_per_year", "level": bt}, base.with_(bulk_flows=flows), mn, mf, kw))
    return run_cells("E7_environment", cells)


# ---------------------------------------------------------------------------
# E8: ablations and batching window
# ---------------------------------------------------------------------------
def e8():
    cells = []
    for ph, fleet in (("P2", FLEETS[4]), ("P3", FLEETS[6])):
        sc = PHASES[ph].with_(fleet=fleet, n_operators=3)
        for an, (mf, kw) in ABLATIONS.items():
            cells.append(({"exp": "E8", "phase": ph, "variant": an, "batch_h": 0.0}, sc, an, mf, kw))
        for b in (0.5, 1.0, 2.0, 6.0):
            cells.append(({"exp": "E8", "phase": ph, "variant": "marketplace", "batch_h": b}, sc,
                          f"marketplace_b{b}", dispatch.marketplace, {"batch_h": b}))
    return run_cells("E8_ablations", cells)


# ---------------------------------------------------------------------------
# E9: tuned auction weights - search on P2, test on P1 and P3
# ---------------------------------------------------------------------------
def e9():
    rng = np.random.default_rng(7)
    train = PHASES["P2"].with_(fleet=FLEETS[4], n_operators=3)
    cells = []
    configs = [{"w_p1": 6.0, "w_p2": 2.0, "w_age": 0.08, "fill": 0.7, "max_wait": 24.0}]  # hand-set
    for i in range(40):
        configs.append({"w_p1": float(rng.uniform(0, 30)), "w_p2": float(rng.uniform(0, 10)),
                        "w_age": float(rng.uniform(0, 0.5)), "fill": float(rng.uniform(0.3, 0.95)),
                        "max_wait": float(rng.uniform(4, 72))})
    for i, cfg in enumerate(configs):
        tag = {"exp": "E9", "stage": "search", "config": i}
        tag.update(cfg)
        cells.append((tag, train, "marketplace", dispatch.marketplace, cfg))
    df = run_cells("E9_search", cells, seeds=8)
    # objective: urgent-cargo 90th percentile delay, with cost as tie-breaker
    g = df.groupby("config").agg(p90=("delay_prio1_p90_h", "mean"), cost=("cost_per_kg_usd", "mean"),
                                 sl=("sl24_prio1", "mean")).reset_index()
    g["score"] = g["p90"] + 1e-4 * g["cost"]
    best = int(g.sort_values("score").iloc[0]["config"])
    json.dump({"best_config": best, "params": configs[best], "table": g.to_dict("records")},
              open(os.path.join(RESULTS, "E9_best.json"), "w"), indent=1)
    cells = []
    for ph, fleet in (("P1", FLEETS[3]), ("P2", FLEETS[4]), ("P3", FLEETS[6])):
        sc = PHASES[ph].with_(fleet=fleet, n_operators=3)
        for label, cfg in (("hand-set", configs[0]), ("tuned", configs[best])):
            tag = {"exp": "E9", "stage": "test", "phase": ph, "weights": label}
            cells.append((tag, sc, "marketplace", dispatch.marketplace, cfg))
    return run_cells("E9_test", cells)


# ---------------------------------------------------------------------------
# E10: economics sensitivity (tornado) around the Phase-2 marketplace cell
# ---------------------------------------------------------------------------
def e10():
    from lunarsim.entities import VEHICLE_CLASSES
    base = PHASES["P2"].with_(fleet=FLEETS[4], n_operators=3)
    cells = [({"exp": "E10", "factor": "base", "level": "base"}, base, "marketplace", dispatch.marketplace, {})]
    # demand
    for lab, mult in (("low", 0.5), ("high", 1.5)):
        lp = {k: v * mult for k, v in base.landings_per_year.items()}
        cells.append(({"exp": "E10", "factor": "demand", "level": lab}, base.with_(landings_per_year=lp), "marketplace", dispatch.marketplace, {}))
    for lab, v in (("low", 200.0), ("high", 5000.0)):
        cells.append(({"exp": "E10", "factor": "operator_cost", "level": lab}, base.with_(operator_cost_per_h=v), "marketplace", dispatch.marketplace, {}))
    for lab, v in (("low", 0.0), ("high", 0.6)):
        cells.append(({"exp": "E10", "factor": "other_duty", "level": lab}, base.with_(other_duty_share=v), "marketplace", dispatch.marketplace, {}))
    for lab, v in (("low", 0.1), ("high", 0.3)):
        cells.append(({"exp": "E10", "factor": "night_fraction", "level": lab}, base.with_(night_fraction=v), "marketplace", dispatch.marketplace, {}))
    for lab, v in (("low", 0.5), ("high", 2.0)):
        cells.append(({"exp": "E10", "factor": "mtbf", "level": lab}, base.with_(mtbf_mult=v), "marketplace", dispatch.marketplace, {}))
    df = run_cells("E10_tornado_sim", cells)
    return df


EXPS = {"e1": e1, "e2": e2, "e3": e3, "e4": e4, "e5": e5, "e6": e6, "e7": e7, "e8": e8, "e9": e9, "e10": e10}



# ---------------------------------------------------------------------------
# E11: anticipatory staging using the published landing schedule
# ---------------------------------------------------------------------------
def e11():
    cells = []
    for ph, fleet in (("P1", FLEETS[3]), ("P2", FLEETS[4]), ("P3", FLEETS[6])):
        sc = PHASES[ph].with_(fleet=fleet, n_operators=3)
        for mn, mf in (("marketplace", dispatch.marketplace), ("marketplace_no_anticipate", dispatch.marketplace_no_anticipate)):
            cells.append(({"exp": "E11", "phase": ph, "n_vehicles": len(fleet)}, sc, mn, mf, {}))
    for n in (2, 3):
        sc = PHASES["P2"].with_(fleet=FLEETS[n], n_operators=2)
        for mn, mf in (("marketplace", dispatch.marketplace), ("marketplace_no_anticipate", dispatch.marketplace_no_anticipate)):
            cells.append(({"exp": "E11", "phase": "P2", "n_vehicles": n}, sc, mn, mf, {}))
    return run_cells("E11_anticipation", cells)


# ---------------------------------------------------------------------------
# E12: capacity ladder - share of landed mass movable by a vehicle (or team) of capacity C
# ---------------------------------------------------------------------------
def e12():
    from lunarsim.scenario import sample_landings, sample_cargo_manifest
    from lunarsim import build_default_world
    world = build_default_world()
    grid = [300, 500, 800, 1000, 1500, 1600, 2000, 2500, 3000, 4000, 4500, 5000, 6000, 8000, 10000, 12000, 13000, 15000, 20000, 30000]
    rows = []
    for ph, sc in PHASES.items():
        masses = []
        for seed in range(300):
            rng = np.random.default_rng(seed)
            cid = 0
            for t, lt, pad in sample_landings(rng, sc, world.pads):
                items, cid = sample_cargo_manifest(rng, lt, sc.cargo_owners, world.pads, t, 1.0, cid, pad=pad)
                masses += [c.mass_kg for c in items]
        masses = np.array(masses)
        for C in grid:
            rows.append({"exp": "E12", "phase": ph, "capacity_kg": C, "movable_mass_share": float(masses[masses <= C].sum() / masses.sum()),
                         "movable_item_share": float((masses <= C).mean()), "n_items": len(masses)})
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(RESULTS, "E12_capacity_ladder.csv"), index=False)
    print("[E12_capacity_ladder] ->", os.path.join(RESULTS, "E12_capacity_ladder.csv"))
    return df


# ---------------------------------------------------------------------------
# E13: fragmentation law - does in-house service depend only on effective vehicles per owner?
# ---------------------------------------------------------------------------
def e13():
    base = PHASES["P2"]
    cells = []
    for N in (4, 6, 8):
        for k in (1, 2, 3, 4, 6, 8):
            if k > N:
                continue
            comps = [f"Co{i}" for i in range(k)]
            fleet = [LTV(comps[i % k]) for i in range(N)]
            owners = [comps[i % k] for i in range(8)]
            flows = [BulkFlow("CONSTR", "BASE", 300, lot_kg=1000, owner=comps[0]), BulkFlow("CONSTR", "ISRU", 200, lot_kg=1000, owner=comps[-1])]
            for duty in (0.0, 0.3, 0.6):
                sc = base.with_(fleet=fleet, cargo_owners=owners, other_duty_share=duty, n_operators=max(2, N // 2), bulk_flows=flows)
                for mn in ("inhouse", "marketplace"):
                    mf, kw = MECHS[mn]
                    cells.append(({"exp": "E13", "N": N, "k": k, "other_duty": duty, "eff_per_owner": N * (1 - duty) / k}, sc, mn, mf, kw))
    return run_cells("E13_fragmentation_law", cells)


# ---------------------------------------------------------------------------
# E14: sequential replication to 99% confidence, 1% relative half-width
# ---------------------------------------------------------------------------
def e14():
    from lunarsim.precision import run_until_precise
    sc = PHASES["P2"]
    out = {}
    for mn, (mf, kw) in MECHS.items():
        res, df = run_until_precise(sc, mf, {"delay_prio1_mean_h": 0.01, "sl24_prio1": 0.01, "delivered_share": 0.01,
                                              "cost_per_kg_usd": 0.01, "delay_prio1_p90_h": 0.05},
                                    confidence=0.99, block=100, n_min=30, n_max=4000, mech_kwargs=kw, verbose=False)
        out[mn] = {m: {"n": r.n, "mean": r.mean, "half_width": r.half_width, "rel_half_width": r.rel_half_width,
                       "target": r.target_rel, "reached": r.reached, "history": r.history} for m, r in res.items()}
        df["mechanism"] = mn
        df.to_csv(os.path.join(RESULTS, f"E14_precision_{mn}.csv"), index=False)
        print(f"[E14] {mn}: n={res['delay_prio1_mean_h'].n} " + " ".join(f"{m}={r.rel_half_width:.4f}" for m, r in res.items()))
    json.dump(out, open(os.path.join(RESULTS, "E14_precision.json"), "w"), indent=1)
    return out


EXPS.update({"e11": e11, "e12": e12, "e13": e13, "e14": e14})


if __name__ == "__main__":
    names = sys.argv[1:] or list(EXPS)
    for n in names:
        EXPS[n]()
