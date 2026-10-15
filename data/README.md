# Datasets

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
