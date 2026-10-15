"""Export the datasets that accompany the paper into data/.

  data/parameters.csv            every model parameter with value, basis and confidence grade
  data/mission_manifest.csv      landed-mass forecast 2026-2032 (low/base/high) with base-case content
  data/cargo_classes.csv         manifest sampler classes
  data/lander_types.csv          lander classes
  data/vehicle_classes.csv       vehicle classes
  data/site_graph.json           the nine-site base graph
  data/scenarios/*.json          named scenarios (phases, fleet variants)
  data/synthetic_manifests/*.csv 30 seeded years of landings and cargo items per phase
  data/sample_traces/*.json      one replayable simulated year per phase (marketplace)
  data/capacity_ladder.csv       E12 output
  data/verification.csv          V&V table
"""
import os, sys, json, csv
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import dataclasses
import numpy as np
import pandas as pd

from lunarsim import build_default_world, Simulation, dispatch
from lunarsim.config import library, save_scenario
from lunarsim.entities import VEHICLE_CLASSES
from lunarsim.scenario import CARGO_CLASSES, LANDER_TYPES, sample_landings, sample_cargo_manifest
from experiments.scenarios import PHASES

DATA = os.path.join(ROOT, "data")
os.makedirs(DATA, exist_ok=True)

PARAMETERS = [
    ("Phase landed mass", "~4,000 / ~60,000 / ~150,000 kg; 21 / 24 / 28 landings", "NASA Moon Base Architecture User's Guide (Apr 2026) p.3", "high"),
    ("Recurring logistics", "2,000-6,000 kg per crewed mission; 2,500-10,000 kg/yr", "NASA Lunar Mobility Drivers and Needs (2024); Lunar Surface Cargo (2024)", "high"),
    ("Habitation-class elements", "12,000-15,000 kg", "NASA ACR24 white papers", "high"),
    ("Pad standoff; farthest site", ">1,000 m; up to 5,000 m", "Lunar Mobility Drivers and Needs (2024)", "high"),
    ("Slopes", "up to 20 deg; >10 deg common", "Lunar Mobility Drivers and Needs (2024)", "high"),
    ("Tortuosity factor", "1.3", "modelling choice", "assumed"),
    ("LTV cargo capacity", "800 kg full / 1,600 kg reduced performance; 1,500 kg used", "NASA ACR24; 2025 workshop slides; Astrolab FLEX 1,500-1,600 kg", "high / med"),
    ("LTV speed", "10 km/h design target; 6 km/h autonomous average used", "Moon Base guide; Astrolab CLV-1 >6 mph; Lunar Outpost Pegasus >9 mph", "med / assumed"),
    ("LTV delivered cost", "$219-220M task order + ~$234M Blue Moon MK1 delivery = $450M", "NASA release 26-046 (26 May 2026)", "high / derived"),
    ("Heavy hauler", "10,000 kg, 4 km/h, $600M, night-capable", "'high capacity mobility' gap; Starship $100k/kg published price", "assumed"),
    ("Small rover", "300 kg, 3 km/h, $60M", "Lunar Outpost HL-MAPP 250 kg / 200 kg payload / 3 m/s", "med / assumed"),
    ("Lander payloads", "CLPS 100-500 kg; MK1 2,000-3,000 kg; large 12,000-30,000 kg", "CLPS task orders 0.07-0.475 t; Blue Moon MK1 3 t; MK2 20-30 t", "high / med"),
    ("Offload delay", "6-24 h (CLPS), 12-36 h (MK1), 24-72 h (large)", "modelling choice", "assumed"),
    ("Dark share of cycle", "0.15 default (about 106 h)", "Shackleton rim 90-94% lit (LROC); 120 h darkness survival target", "med"),
    ("Night speed factor (night-capable)", "0.6", "modelling choice", "assumed"),
    ("Light-time RTT; processing", "2.6 s; +2.4 s default", "NTRS 20250000703; Mellinkoff et al. 2018", "high / med"),
    ("Teleop speed model", "3.24 / 2.56 / 2.03 / 1.76 km/h at 0 / 4 / 6 / 8 s RTT, interpolated; move-and-wait beyond 8 s", "Litaker et al., NASA TM-20240001217; Ferrell 1965", "med"),
    ("Teleop handling factor", "1 + 0.25 x RTT", "Seo, Gupta & Ham: 139% at 1.5 s, 174% at 3 s", "med"),
    ("Fan-out", "supervised 4; autonomous 20", "Olsen & Wood 2004 (1-9); mining AHS up to 30", "med"),
    ("MTBF / MTTR", "500/24 h (LTV), 400/36 h (hauler), 300/12 h (small)", "set to 92-96% availability as in autonomous mining haulage; no rover MTBF published", "assumed"),
    ("Other-duty share", "0.3 in 48 h blocks", "NASA LTV commercial-use clause; trade estimate of 25% commercial use", "low"),
    ("Energy", "350 / 900 / 120 Wh/km by class", "Apollo LRV-derived ~95 Wh/km at 700 kg, scaled", "low"),
    ("Operator cost", "$1,000 per console hour", "modelling choice; swept $200-$5,000", "assumed"),
    ("Value of time by priority", "$5,000 / $1,000 / $100 per hour", "modelling choice", "assumed"),
    ("Wear share", "0.5", "modelling choice", "assumed"),
    ("Return flow", "30% of items; 20-60% of mass; 5-30 days later", "trash and sample return are NextSTEP-2 Appendix R topics", "assumed"),
    ("Bulk flows", "P1 30 t/yr; P2 500 t/yr; P3 1,500 t/yr", "IPEx sized for 10 t regolith/day (NASA ASCEND 2024); swept 0-3,000", "assumed"),
    ("Anticipation window and margin", "48 h; arrive 1 h before first item", "modelling choice", "assumed"),
    ("Landed cost per kg", "CLPS ~$1.08M (Blue Ghost M1); MK1 ~$78k if full; Starship $100k published", "SpacePolicyOnline; NASA release 26-046; spacex.com", "high / derived / med"),
]

MANIFEST = [
    (2026, 0.0, 0.5, 0.7, "Griffin-1 with the FLIP rover (~0.5 t)"),
    (2027, 0.2, 0.8, 3.5, "Blue Moon MK1 Pathfinder, IM-4, Draper CP-12, VIPER on a second MK1"),
    (2028, 1.0, 4.5, 12, "Two LTV deliveries on MK1 with co-manifested cargo; Artemis IV crew logistics; MoonFall drones"),
    (2029, 1.5, 6, 15, "Recurring logistics begins (NASA: 2,500-10,000 kg/yr); Eagle rover on Starship; IM-5"),
    (2030, 3, 20, 35, "Fission Surface Power unit (<=15 t) plus recurring logistics"),
    (2031, 3, 12, 30, "Recurring logistics; ESA Argonaut (1.5 t); ISRU pilot elements"),
    (2032, 5, 25, 45, "JAXA pressurised rover (12-15 t class); recurring logistics up to 8 t per mission"),
]


def main():
    pd.DataFrame(PARAMETERS, columns=["parameter", "value_used", "basis", "confidence"]).to_csv(os.path.join(DATA, "parameters.csv"), index=False)
    pd.DataFrame(MANIFEST, columns=["year", "low_t", "base_t", "high_t", "base_case_content"]).to_csv(os.path.join(DATA, "mission_manifest.csv"), index=False)
    pd.DataFrame([{"label": c[0], "mass_min_kg": c[1][0], "mass_max_kg": c[1][1], "destination_weights": json.dumps(c[2]), "priority": c[3], "item_share": c[4]}
                  for c in CARGO_CLASSES]).to_csv(os.path.join(DATA, "cargo_classes.csv"), index=False)
    pd.DataFrame([{"name": lt.name, "payload_min_kg": lt.payload_kg[0], "payload_max_kg": lt.payload_kg[1], "offload_min_h": lt.offload_h[0],
                   "offload_max_h": lt.offload_h[1], "max_item_kg": lt.max_item_kg} for lt in LANDER_TYPES.values()]).to_csv(os.path.join(DATA, "lander_types.csv"), index=False)
    pd.DataFrame([dataclasses.asdict(v) for v in VEHICLE_CLASSES.values()]).to_csv(os.path.join(DATA, "vehicle_classes.csv"), index=False)
    json.dump(build_default_world().to_dict(), open(os.path.join(DATA, "site_graph.json"), "w"), indent=1)
    for k, sc in library().items():
        save_scenario(sc.with_(name=k), os.path.join(DATA, "scenarios", f"{k}.json"))
    # synthetic manifests
    os.makedirs(os.path.join(DATA, "synthetic_manifests"), exist_ok=True)
    world = build_default_world()
    for ph, sc in PHASES.items():
        rows = []
        for seed in range(30):
            rng = np.random.default_rng(seed)
            cid = 0
            for t, lt, pad in sample_landings(rng, sc, world.pads):
                items, cid = sample_cargo_manifest(rng, lt, sc.cargo_owners, world.pads, t, 1.0, cid, pad=pad)
                for c in items:
                    rows.append({"seed": seed, "landing_time_h": round(t, 3), "lander": lt.name, "pad": pad, "item_id": c.id, "owner": c.owner,
                                 "mass_kg": round(c.mass_kg, 1), "dest": c.dest, "ready_time_h": round(c.t_ready, 3), "priority": c.priority,
                                 "class": c.cls, "return_mass_kg": round(c.return_mass_kg, 1), "return_lag_h": round(c.return_lag_h, 1)})
        pd.DataFrame(rows).to_csv(os.path.join(DATA, "synthetic_manifests", f"{ph}_30_years.csv"), index=False)
        print(ph, len(rows), "items over 30 years")
    # sample traces
    os.makedirs(os.path.join(DATA, "sample_traces"), exist_ok=True)
    for ph, sc in PHASES.items():
        sim = Simulation(sc, dispatch.marketplace, seed=3, mech_kwargs={"trace": True})
        sim.run()
        json.dump(sim.trace_export(), open(os.path.join(DATA, "sample_traces", f"{ph}_marketplace_seed3.json"), "w"))
    for src, dst in (("table_E12.csv", "capacity_ladder.csv"), ("table_vv.csv", "verification.csv"), ("table_E13.csv", "fragmentation_law_cells.csv"),
                     ("table_E11.csv", "anticipation_paired.csv"), ("table_cost_context.csv", "cost_context.csv")):
        p = os.path.join(ROOT, "results", src)
        if os.path.exists(p):
            pd.read_csv(p).to_csv(os.path.join(DATA, dst), index=False)
    readme = """# Datasets

All files are produced by `experiments/export_datasets.py` from the simulator and the paper's sources.

| File | Contents |
|---|---|
| `parameters.csv` | Every model parameter with the value used, its basis (source) and a confidence grade (high / med / low / assumed). |
| `mission_manifest.csv` | Landed payload mass at the lunar south pole by year, 2026-2032, low / base / high, with the base-case content. |
| `cargo_classes.csv`, `lander_types.csv`, `vehicle_classes.csv` | The demand and fleet models exactly as the code uses them. |
| `site_graph.json` | The nine-site base graph (coordinates in km, edges with slope class and path length). |
| `scenarios/*.json` | Named scenarios: the three phases and the Phase-2 fleet-size variants, in the `lunarsim-scenario` v1 format (full form; schema `lunarsim/schemas/scenario-v1.schema.json`). Load with `lunarsim.config.load_scenario`, pass to `lunarsim run --scenario <file>`, or import on the live page. |
| `synthetic_manifests/P*_30_years.csv` | 30 seeded years of landings and cargo items per phase: one row per item with mass, class, priority, pad, destination, release time and return flow. |
| `sample_traces/*.json` | One replayable simulated year per phase (marketplace, seed 3) in the `lunarsim-trace` v1 format (schema `lunarsim/schemas/trace-v1.schema.json`): every vehicle movement, every item, nights and landings. Load them in the live simulator's Replay tab. Check any file with `lunarsim validate <file>`. |
| `capacity_ladder.csv` | Share of landed mass movable by a vehicle or team of a given capacity, by phase (300 manifest-years each). |
| `fragmentation_law_cells.csv` | The 90 in-house / marketplace cells behind the fragmentation law. |
| `anticipation_paired.csv` | Paired differences with and without anticipatory staging. |
| `verification.csv` | The thirteen verification checks with references, simulated values and errors. |
| `cost_context.csv` | Landed cost per kilogram on three vehicles against the simulated cost of a surface move. |

Raw per-seed experiment outputs (one row per simulated year) are in `../results/E*.csv`; column names match the
metric names in `lunarsim/engine.py` (`Metrics.summary`).
"""
    open(os.path.join(DATA, "README.md"), "w", encoding="utf-8").write(readme)
    print("datasets exported to", DATA)


if __name__ == "__main__":
    main()
