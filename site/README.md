# LunarSim site

The public site: a Vite multi-page app (vanilla JS modules, three.js, Observable Plot) built to static files for
GitHub Pages. The existing simulator (`web/`) is copied in under `/simulator/` at build time.

## Develop

```sh
cd site
npm ci
npm run dev          # http://localhost:5173/  (also serves /simulator/ from web/dist)
```

`npm run dev` and `npm run build` first run `scripts/prepare-data.mjs`, which stages the run-time data into
`public/` (git-ignored). `/simulator/` in dev needs `python web/build_web.py` to have been run once.

## Build

```sh
npm run build                                          # site/dist, base "/"
SITE_BASE=/lunar-logistics-research/ npm run build     # the GitHub Pages build (CI)
npx vite preview --base /lunar-logistics-research/     # serve a prefixed build locally
```

The build runs prepare-data, then `vite build`, then `scripts/copy-simulator.mjs` (runs `web/build_web.py` with
`$PYTHON` or the repo's `.venv`, and copies `web/dist` to `dist/simulator/`). Every internal link, asset and data
URL is prefixed with `SITE_BASE`. On Git Bash for Windows set `MSYS_NO_PATHCONV=1`, or the shell rewrites the base
into a Windows path.

## Where each page's data comes from

| Page | Source files (repo) | Staged as |
|---|---|---|
| `/` hero | `data/terrain/connecting_ridge/{height_20m.png, meta.json}` (fallback: `site/.terrain-dev/` from `scripts/make_dev_terrain.py`) | `public/terrain/hero/` |
| `/` numbers and figure | `results/table_main.csv` (read at build time by `lib/pages.mjs`) | inlined in the HTML |
| `/world` | `data/sample_traces/*.json`, `tests/fixtures/trace_v2_sample.json`, `data/site_graph.json`, `data/terrain/connecting_ridge/sites.json`; the simulator's last run via `localStorage` | `public/world/`, `public/terrain/hero/` |
| `/lab/lander` | `data/policies/{lander_*.json, *.check.json, outcomes_*.json}` | `public/lab/policies/` (+ `index.json`) |
| `/lab/rover` | `data/terrain/connecting_ridge/{height_5m.png, slope_20m.png}`, `data/driving/driving-v1.json` (split per leg); daylight shadow grids precomputed with `src/rover/terrain.js` | `public/lab/rover/`, `public/terrain/hero/` |
| `/verification` | the simulator's worker, `tests/fixtures/lander_parity.json`, `site/verify/refs.json` (Python reference numbers from `scripts/make_verify_refs.py`) | `public/verify/` |
| `/method`, `/paper`, `/data`, `/about`, `/changelog` | `site/content/*.md` (rendered at build time) | inlined |
| GPU tiering | detect-gpu's benchmark tables (self-hosted, no third-party request) | `public/detect-gpu/` |

Re-run `.venv\Scripts\python site\scripts\make_verify_refs.py` (repo root) after the terrain pack, the rover model
or the driving table changes, and commit `site/verify/refs.json`.

## Code map

- `lib/pages.mjs`: build-time header, footer, icons (Lucide), markdown, headline numbers, figures.
- `src/main.js`, `src/styles/`: shared page script and the design system (`tokens.css`, `base.css`).
- `src/components/num.js` (every number with unit, flag and source), `src/components/figure.js` (SVG/PNG/CSV).
- `src/terrain.js`: lunarsim-terrain reader with a 16-/8-bit PNG decoder.
- `src/world/`: trace reader (v1 + v2), layout, state, 3D scene, 2D plan view.
- `src/lander/`, `src/policy.js`: line-by-line ports of `lunarsim/lander/` and the policy runtime.
- `src/rover/`: line-by-line ports of `lunarsim/rover/` and the terrain queries it uses.
- `src/verify/`: the verification page and its worker.

The ports follow the Python code line by line, including its numeric conventions (floor modulo, half-even
rounding, float32 casts, `np.interp` order). `/verification` checks them against Python on every load.
