# Changelog

The format follows Keep a Changelog. Versions are the engine's version in `pyproject.toml`.

## Unreleased (3.0.0, in progress)

### Added
- Terrain packs from NASA's LOLA 5 m south-polar DEMs; the nine-site base placed on the Connecting Ridge.
- A lander terminal-descent environment with a classical guidance baseline and a reinforcement-learning policy;
  per-landing miss distance, touchdown state and propellant feed the logistics engine.
- A rover driving environment on real terrain with a scripted expert and a learned driver; per-leg time, energy
  and interventions by autonomy level, control latency and lighting.
- Plume keep-out windows and shelters around landings in the dispatch rules.
- This site: 3D world viewer, lander and rover labs, method, paper and data pages.

### Changed (22 October 2026)
- The site moved to `/Lunar-Haul/` with the repository rename; the build now takes its base path from GitHub Pages.
- Plain-language labels in the simulator and the labs: scenario, fleet, environment and job-rule names say what
  they do, with a short hint under each setting. The paper's names (in-house, pooled greedy, batched assignment)
  are given in the Method tab. Nothing in the engines changed.

## 2.1.0 — 2026-10-15

### Added
- Versioned, schema-checked scenario and trace formats shared by Python and the browser.
- `lunarsim validate` for both formats; `lunarsim serve`, a local JSON API over the reference engine, with an
  optional "Python engine" mode in the live page and a live Python-vs-browser cross-check.
- Replay of any trace file and one-click sample years in the simulator.
- The demand phases moved into the package so scenario files work outside a repository checkout.

### Changed
- Datasets regenerated in the v1 formats (header keys only; all values unchanged).

## 2.0.0 — 2026-10-06

### Added
- The verified lunar surface logistics testbed, released under the project's former name LunarSim (nine-site base,
  multi-owner fleet, lunar night, Earth–Moon latency, faults), four dispatch rules including the pooled marketplace,
  thirteen verification checks.
- Experiments E1–E14, the datasets, the figures, the browser port with a cross-implementation check, and the
  44-page paper.
