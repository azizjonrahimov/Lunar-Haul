# Data

All files are in the repository under `data/` and `results/`, produced by scripts that are also in the
repository. Formats are versioned and each has a JSON Schema; `lunarsim validate <file>` checks any of them.

## Datasets (`data/`)

| File | Contents |
|---|---|
| `parameters.csv` | Every model parameter with the value used, its basis (source) and a confidence grade. |
| `mission_manifest.csv` | Landed payload mass at the lunar south pole by year, 2026–2032, low / base / high, with the base-case content. |
| `cargo_classes.csv`, `lander_types.csv`, `vehicle_classes.csv` | The demand and fleet models exactly as the code uses them. |
| `site_graph.json` | The nine-site base graph of the v2 study (coordinates in km, edges with slope class and path length). |
| `scenarios/*.json` | Named scenarios in the `lunarsim-scenario` v1 format: the three demand phases and the Phase-2 fleet-size variants. Load with the command line or import them on the Simulator page. |
| `synthetic_manifests/P*_30_years.csv` | 30 seeded years of landings and cargo items per phase, one row per item. |
| `sample_traces/*.json` | One replayable simulated year per phase (marketplace, seed 3) in the `lunarsim-trace` format. The World page plays them. |
| `terrain/connecting_ridge/` | The terrain pack: 16 × 16 km of the Connecting Ridge from the LOLA 5 m DEM as 16-bit height maps (5 m and 20 m), slope, hillshade, metadata with citation, and `sites.json` with the nine sites and the landing-pad sets at 0.5, 1, 2, 3 and 5 km from the base. |
| `driving/driving-v1.json` | Per-leg driving tables on that terrain: time, energy and interventions for every ordered pair of sites, by autonomy level, control latency and lighting. |
| `policies/` | Trained landing policies (`lunarsim-policy` v1, plain JSON weights that run in Python and in the browser) with their training records and Monte Carlo outcome tables. |
| `capacity_ladder.csv`, `fragmentation_law_cells.csv`, `anticipation_paired.csv`, `verification.csv`, `cost_context.csv` | The derived tables behind the v2 paper's figures. |

## Results (`results/`)

Raw per-seed experiment outputs, one row per simulated year, one CSV per suite (E1–E14 from the v2 study;
E15–E20 from the current phase), and the summary tables `table_*.csv` used by the paper and by this site.
Column names are documented in `results/README.md`.

## Formats

- `lunarsim-scenario` v1: a full form (every scenario field) and a compact form (a demand phase plus the page's
  controls). Both load in Python and in the browser.
- `lunarsim-trace` v1/v2: one simulated year: vehicles, trips with timed segments, cargo rows, nights, landings;
  v2 adds landing outcomes, plume keep-out windows and shelters.
- `lunarsim-terrain` v1, `lunarsim-driving` v1, `lunarsim-policy` v1: the terrain pack, the driving tables and
  the policy weights described above.

Schemas live in `lunarsim/schemas/`.

## Reproducing

```
pip install -e ".[full,terrain,ml]"
python -m pytest tests -q
python experiments/run_all.py            # v2 suites E1–E14
python experiments/phase3/run_phase3.py  # current suites E15–E20
python experiments/export_datasets.py
python experiments/make_figures.py
```

Seeds are fixed and documented in every results file; runs are deterministic. The World and Simulator pages
state which engine produced what you see.

## Citing

See the Paper page and `CITATION.cff`. Data produced by the project is released under CC BY 4.0; NASA data keep
their own terms (public, credit NASA/GSFC).
