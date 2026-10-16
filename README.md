# LunarHaul: lunar surface logistics testbed, marketplace mechanism, datasets and paper

LunarHaul was called LunarSim until 15 October 2026; the name changed because three unrelated projects use it. The Python package, the
command (`lunarsim`), the file formats (`lunarsim-*`) and the repository URL keep the old identifier until the next release.

[![tests](https://github.com/azizjonrahimov/lunar-logistics-research/actions/workflows/ci.yml/badge.svg)](https://github.com/azizjonrahimov/lunar-logistics-research/actions/workflows/ci.yml)
[![simulator](https://github.com/azizjonrahimov/lunar-logistics-research/actions/workflows/pages.yml/badge.svg)](https://azizjonrahimov.github.io/lunar-logistics-research/)

**Live simulator:** https://azizjonrahimov.github.io/lunar-logistics-research/
**Paper (v2, 44 pages):** [`paper/lunar_logistics_marketplace_paper_v2.pdf`](paper/lunar_logistics_marketplace_paper_v2.pdf)

## In one paragraph

NASA's Moon Base plan lands about 4 t of cargo at the lunar south pole before 2029, 60 t in 2029-2032 and 150 t
after that, in items from 10 kg instruments to 15 t habitats, while the rovers under contract carry 0.8-1.6 t.
NASA's 2026 architecture guide names "a marketplace for lunar logistics" as a goal without saying what one would do.
LunarHaul is a discrete-event model of cargo movement at a nine-site south-pole base (lander manifests, a fleet owned
by several companies, the lunar night, Earth-Moon control latency, faults, other duties, regolith and return flows)
with four dispatch rules: today's bilateral in-house contracting, pooled greedy dispatch, batched assignment, and a
pooled marketplace (sequential auction with bundling, consolidation, team lifts, night awareness and anticipatory
staging). Thirteen verification checks pass against analytic and published references; a browser port reproduces the
Python results. Main findings: pooling helps only when the fleet is fragmented (the in-house penalty follows
20/e hours in effective vehicles per owner); any pooled rule reaches a same-day service level with four vehicles at
Phase-2 demand where in-house fleets do not with eight; 1.6 t rovers can move 40% of the Phase-2 manifest, two
lifting together 55%, a 10 t hauler 88% and only 15 t of capacity all of it; a surface move costs about $300 per kg
moved or $5,000 per landed kg, a few percent of the cost of landing it.

## Try it

- **Browser:** open the [live simulator](https://azizjonrahimov.github.io/lunar-logistics-research/). Build a fleet, set the
  environment, run seeds in background workers, compare the four rules on the same seeds, replay a simulated year on
  the base map (your own run, or any trace file from the command line), run the verification checks, export CSV or
  import/export scenario JSON.
- **Command line:** `pip install -e .` then `lunarsim run --scenario P2-4-vehicles --mechanism marketplace --seeds 30`,
  `lunarsim compare --scenario P2-default`, `lunarsim verify`, `lunarsim trace --seed 3 --out year.json`,
  `lunarsim scenarios export --dir data/scenarios`, `lunarsim validate <file.json>`.
- **Both together:** `lunarsim serve` starts a local JSON API on 127.0.0.1:8765 (standard library only). In the live
  page, open Verification → Engine → Connect, and the page can run the Python reference engine on your machine:
  "Run in Python" and a live cross-implementation check. `lunarsim serve --static web/dist` serves the page as well.

## Phase 3 (version 3, October 2026): learned landers and rovers on real terrain

Version 3 puts the base on NASA's LOLA 5 m terrain of the Connecting Ridge and adds two learned models to the
logistics engine, so that a question NASA's architecture papers leave open can be answered with numbers: how landing
precision, pad-to-base distance, plume keep-out rules and rover autonomy change delivery delay and cost.

- `lunarsim/terrain.py`: terrain packs from PGDA LOLA site tiles (`lunarsim terrain build|place|info`); the nine sites
  and five landing-pad sets are in `data/terrain/connecting_ridge/sites.json`.
- `lunarsim/lander/`: a Gymnasium terminal-descent environment (`lunar/Descent-v0`, 3-DoF, SPLICE gate and touchdown
  box, altimeter dropouts), a classical ZEM/ZEV law, a PPO trainer and exporter (policies are plain JSON that run in
  Python and in the browser), and Monte Carlo outcome tables in `data/policies/`.
- `lunarsim/rover/`: a driving environment on the terrain (`lunar/Drive-v0`), slip-vs-slope in lunar gravity,
  LRV-calibrated energy, a teleoperation model calibrated to NASA JSC latency trials, a scripted expert, and per-leg
  driving tables in `data/driving/`.
- `lunarsim/phase3.py`: the engine's opt-in Scenario fields (`terrain`, `pad_standoff_km`, `landing_model`, `plume`,
  `autonomy_model`); with them unset, v2 results are reproduced byte for byte. Trace v2 records landing outcomes,
  keep-out windows and shelters.
- `site/`: the public site (Vite + three.js): landing page on the real terrain, the 3D world viewer, the lander lab,
  the rover lab, method, paper, data and about pages. `npm ci && npm run build` in `site/`.
- `experiments/phase3/`: the six experiment suites E15-E20 (`run_phase3.py`, resumable; `fit_law.py`;
  `make_figures_phase3.py`). Results are in `results/table_E15.csv` to `table_E20*.csv` and `results/E20_fit.json`,
  figures in `figures/fig20_*.png` to `fig27_*.png` with captions in `figures/phase3_captions.json`.
- What the suites found (30 seeds per cell, 62,640 simulated years in the fit): each kilometre of pad standoff raises
  the mean delay of urgent cargo by 40 % [37, 43]; each kilometre of plume keep-out radius by 12 % [10, 14]; each hour
  of post-landing stand-down by 2.3 % [1.8, 2.8]. Landing dispersion has no smooth effect (+1.6 % per e-fold of mean
  miss, interval including zero); it matters only through landings that miss the pad, which is why a 100 m pad
  absorbs the current 50 m accuracy and a 25 m pad does not. Pooled dispatch stays 46-53 % below in-house fleets.
  Two autonomous rovers do the work of six teleoperated ones at 8 s round-trip latency. The learned lander, an
  imitation clone of the classical law with DAgger on the memory-augmented observation, lands inside the touchdown
  box 89.0 % of the time against 93.8 % for the law it imitates and 63.2 % for PPO on the shaped reward, which
  prefers a slow, fuel-costly descent the reward does not penalise.
- The third version of the paper, "Where the Lander Lands: Landing Precision, Pad Standoff, Plume Keep-Out and Rover
  Autonomy Priced in Lunar Surface Logistics", is being assembled in `paper/v3/`; the research behind it is in
  `reports/Lunar landing and rover autonomy logistics.md`.

Every number in the new material carries a flag: Measured, Spec, Modelled or Assumed.

## File formats

Python and the browser exchange two JSON formats, each versioned and described by a JSON Schema in `lunarsim/schemas/`:

- **`lunarsim-scenario` v1**: a *full* form (every `Scenario` field; what `lunarsim scenarios export` writes) and a
  *compact* form (a phase plus the page's controls; what the page's "Export scenario JSON" writes). Both load in both
  places. When the page imports a full-form file, anything its controls cannot represent is listed, not dropped silently.
- **`lunarsim-trace` v1**: one simulated year (vehicles, trips with timed segments, cargo rows, nights, landings),
  written by `lunarsim trace` and by the page; the Replay tab reads either.

`lunarsim validate` checks files of either kind. The local API's endpoints (`/api/health`, `/api/scenarios`, `/api/run`,
`/api/compare`, `/api/trace`, `/api/verify`) are documented at the top of `lunarsim/server.py`.

## What is here

| Path | Contents |
|---|---|
| `lunarsim/` | The discrete-event simulator. `world.py` (nine-site base graph, Floyd-Warshall), `entities.py` (cargo, vehicle classes), `scenario.py` (demand, landers, bulk flows, environment, costs), `engine.py` (event loop, job pricing, metrics, trace export), `dispatch.py` (in-house, pooled greedy, batched Hungarian assignment, marketplace with bundling / consolidation / team lift / backhaul / night awareness / anticipatory staging, and ablation variants), `assign.py` (dependency-free Hungarian algorithm), `vv.py` (13 verification checks), `precision.py` (sequential replication to a target confidence-interval width), `phases.py` (the P1-P3 demand phases and fleet variants), `config.py` (scenario JSON, both forms, and the scenario library), `formats.py` and `schemas/` (format validators and JSON Schemas), `server.py` (the local JSON API), `cli.py` (the `lunarsim` command). |
| `tests/` | pytest suite: `test_verification.py` (the 13 verification checks plus determinism, invariants, Hungarian-vs-SciPy, team lift, trace export), `test_formats.py` (scenario and trace formats, round trips, validation), `test_server.py` (the local API). |
| `experiments/scenarios.py` | Demand phases P1 (pre-2029), P2 (2029-2032), P3 (2032+); re-exports `lunarsim/phases.py`, where the definitions live. |
| `experiments/run_all.py` | Experiment suites E1-E14; `run_e14_long.py` continues the precision run to a 1% half-width (resumable); `export_datasets.py` writes `data/`. |
| `experiments/make_figures.py` | All figures (`figures/`) and summary tables (`results/table_*.csv`), including the V&V table. |
| `web/` | The browser port of the simulator: `sim.js` (the engine, a line-by-line port of `lunarsim`), `worker.js` (runs it off the main thread), `app.js` and `index.html` (the interface), `formats.js` (reads and writes the shared trace and scenario formats), `api.js` (optional client for `lunarsim serve`), `build_web.py` (writes `web/dist/` with `ref.js`, the Python reference values for the cross-implementation check). Deployed to GitHub Pages by `.github/workflows/pages.yml`. |
| `paper/` | Paper source (`part1_front.html` ... `part4_back.html`, `style.css`), `build.py` (assembles `paper.html`, fills tables and settled numbers, prints the PDF with headless Chrome), PDFs, page previews. |
| `notes/` | Research notes compiled before modelling: methods playbook, lunar logistics literature and sourced parameters, marketplace mechanisms and simulation design, demand / supply / competitor facts. Every number carries its URL and a confidence grade. |
| `results/` | Raw per-seed results (`E*.csv`), the weight search (`E9_best.json`), precision runs (`E14_*.json`, `E14_precision_*.csv.gz`), derived tables; columns are documented in `results/README.md`. |
| `data/` | Datasets: the sourced parameter table, the 2026-2032 mission manifest, cargo / lander / vehicle classes, the site graph, scenario JSON files, 30 synthetic manifest-years per phase, replayable sample traces, the capacity ladder and the verification table (`data/README.md`). |
| `.github/workflows/` | `ci.yml` runs the tests and `lunarsim verify` on every push; `pages.yml` builds `web/dist/` and deploys the simulator to GitHub Pages. |

## Reproduce

```
py -3 -m venv .venv
.venv\Scripts\python -m pip install -e ".[full]"         # numpy, pandas, scipy, matplotlib, pymupdf, pytest
.venv\Scripts\python -m pytest tests -q                 # 117 tests (formats, server, verification)
.venv\Scripts\python experiments\run_all.py              # E1-E14, ~40 min on 10 cores; pass e1 e2 ... for a subset
.venv\Scripts\python experiments\run_e14_long.py         # optional: precision run to 1% (hours; resumable)
.venv\Scripts\python experiments\export_datasets.py      # data/ (parameters, manifests, scenarios, traces)
.venv\Scripts\python experiments\make_figures.py         # figures/*.png and results/table_*.csv (add "vv" to run the checks)
.venv\Scripts\python web\build_web.py                    # web/dist/ (index.html, app.js, sim.js, formats.js, api.js, worker.js, ref.js)
.venv\Scripts\python paper\build.py                      # paper/paper.html and the PDF (needs Chrome)
```

Seeds are 0-29 per cell (0-19 for E5, 0-7 for the E9 search, 0..n for the sequential runs). The demand stream
uses the cell seed and the operations stream the seed plus 100,003 (common random numbers). Runs are deterministic.

## Quick start in Python

```python
import sys; sys.path.insert(0, ".")
from lunarsim import run, dispatch, Simulation
from experiments.scenarios import PHASES
out = run(PHASES["P2"], dispatch.marketplace, seed=0)
print(out["delay_prio1_p90_h"], out["stranded_kg"] / out["landed_kg"], out["cost_per_kg_usd"])
sim = Simulation(PHASES["P2"], dispatch.marketplace, seed=0, mech_kwargs={"trace": True}); sim.run()
replay = sim.trace_export()   # everything the live viewer animates
```

## Verification summary

All 13 checks pass (Appendix B of the paper): kinematics and slope identities, the four NASA JSC teleoperation
speeds (exact), dark-share of time, two mass-conservation identities, the stranding rule, common random numbers,
fleet amortisation, and the M/G/1 Pollaczek-Khinchine queue (0.5% error). The browser port agrees with the
Python implementation within combined 95% CIs on all 24 Phase-2 metric cells (Verification tab of the live page).

## Caveats

Parameters marked *assumed* in Appendix A (hauler cost, bulk flows, operator cost, value of time, other-duty
share, offload delays, energy, anticipation window) are our choices and are swept in the sensitivity analysis.
Several published numbers (LTV teleoperation speeds, mining-haulage availability, LTV requirements) were only
available through secondary summaries; they are flagged in `notes/02_*.md` and `notes/03_*.md`.
