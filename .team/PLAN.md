# Team plan, Phase 3: learned landers and rovers inside LunarSim

Lead: LEAD session · Workers: BACKEND, FRONTEND (+ LEAD-run subagents for terrain, training, figures, paper)
Written 2026-10-15 after the Phase-3 research round. Research: `reports/Lunar landing and rover autonomy logistics.md`
(12,500 words, 326 citations) and the nine note files in `research_notes/Lunar landing and rover autonomy logistics/`.
Read the report's first section and the ranked-contribution table before starting any task.

## 0. Where we are (v2.1, done this morning)

Commits 1422413..4cc1caa: shared versioned scenario/trace formats with JSON Schemas, `lunarsim validate`,
`lunarsim serve` (stdlib local API, `--static`), the page's optional Python-engine mode, bundled sample years,
datasets regenerated in v1, README/CI updated. 130 tests pass. Baseline rule still holds: `lunarsim compare
--scenario P2-default --seeds 3` and the P2-4-vehicles seed-3 trace must stay byte-identical when the new
features are OFF (they are all opt-in Scenario fields with defaults that reproduce v2).

## 1. The scientific goal (what would be new)

NASA's 2023 and 2025 architecture papers say landing precision and pad-to-base distance drive surface
logistics "transfer time and risk" but never put a number on it; NASA KSC (2026) states "no safe standoff
distances have been defined"; the 2 km heritage exclusion was, per its author, "a number we made up". No
retrieved paper 2000-2026 quantifies how landing dispersion σ, pad standoff D, plume keep-out radius R (and
stand-down time T) and rover autonomy level change delivery delay, service level or $/kg. Learned controllers
in the space literature stop at touchdown state or tracking error; nobody has put them inside a logistics
simulation and reported logistics-level effects.

Phase 3 therefore builds and reports:

1. **A dispersion/standoff/keep-out-to-logistics law**: delay, 24 h service level and $/kg as a function of
   (σ_land, D_pad, R_keepout, T_standdown, autonomy level, fleet, demand phase). Hypothesis to test, stated
   honestly in the paper: dispersion probably acts through *pad mass and tail events* (off-pad and tip-over
   landings), not smoothly through traverse distance; keep-out and autonomy dominate the smooth part.
2. **Plume-event-aware dispatch**: keep-out as a time-varying constraint that interacts with anticipatory
   staging, lunar night and multi-owner fleets; its cost under each dispatch rule.
3. **Learned lander and rover policies as stochastic generators inside the DES**: a PPO terminal-descent
   policy (custom 3-DoF Gymnasium env parameterised from flown landers, not the toy LunarLander) gives
   per-landing miss distance, touchdown state, propellant and time-below-30 m; a behavioural-cloning driver on
   PGDA LOLA 5 m terrain gives per-leg speed, slip, energy and interventions by autonomy level and lighting.
   The DES samples both. Python and the browser run the same physics and the same weights.

What we must not claim: a predicted plume keep-out (NASA calls PSI predictions "largely qualitative"); R and T
are swept, not predicted. Every number carries a flag: Measured / Spec / Modelled / Assumed.

## 2. Architecture (data flow)

```
PGDA LOLA 5 m tile ──build_terrain──► data/terrain/<site>/ (16-bit PNG + meta JSON; 20 m web copy; 5 m crops)
                                            │                     │
   lunarsim/lander (gym env, PPO) ──export──► data/policies/lander_*.json ──┐
   lunarsim/rover  (gym env, expert, BC) ──► data/policies/rover_*.onnx     │  same files, same physics
                     └─evaluate──► data/driving/driving-v1.json (per-leg tables)│
                                                                            ▼
   lunarsim/engine.py (DES; opt-in: terrain legs, landing outcomes, plume keep-out) ──► trace v2, metrics
                                            │                                             │
   experiments/phase3/*.py (E15–E20) ──► results/, figures/ ──► paper v3                 │
                                                                                          ▼
   service/ (FastAPI + SQLite/WAL + Litestream + worker + SSE; auth; provenance; leaderboard)
                                            │
   site/ (Vite + Three.js + Observable Plot): landing, world (3D), lander lab, rover lab, simulator,
          method, paper, data, about, account, changelog  ──► GitHub Pages (app.<domain>)
```

Rule "two engines, one physics": every model that runs in the browser (lander policy runtime, rover env,
driving tables) has a Python reference and a cross-check in the Verification page, as today.
Decision (Oct 15, after B-12): the browser logistics engine (`web/sim.js`) stays at v2; the Phase-3 engine
features (terrain legs, landing outcomes, plume keep-out) run in Python only, and the 3D world viewer replays
Python v2 traces (plus browser v1 traces). The labs port the lander and rover *physics*, not the DES.

## 3. Milestones

| # | Milestone | Target | Main tasks |
|---|---|---|---|
| M5 | Foundations: terrain pack + site coordinates; lander env + policy runtime; site skeleton with design system; hero 3D terrain | Oct 15 evening | B-9, B-10, F-5 |
| M6 | Rover env + scripted expert + driving tables v0; DES integration (landing outcomes, plume, terrain legs) + trace v2; 3D world viewer replaying trace v2 | Oct 16 | B-11, B-12, F-6 |
| M7 | Trained policies: PPO lander (per class, reward-shaping variants incl. the hover/hacking demo), BC driver + DAgger; Monte Carlo evaluations vs classical law and vs Litaker/Chen anchors; lander lab + rover lab pages | Oct 17 | B-13, LEAD training runs, F-7, F-8 |
| M8 | Experiments E15–E20, law fit, precision runs; service v2 (auth, runs, SSE, provenance, leaderboard); accounts UI | Oct 18–19 | B-14, B-15, F-9, LEAD |
| M9 | Figures, paper v3 (natural voice, flagged numbers), README, data/DOI packaging, verification page extended | Oct 20–22 | LEAD + subagents, F-10 |
| M10 | Deploy: Pages (site), service on VPS (owner decision), Zenodo release; push | Oct 22–23 | LEAD |

Dates assume continuous worker sessions; each task carries its own due time in the inboxes.

## 4. File ownership (Phase 3)

| Owner | May edit |
|---|---|
| **BACKEND** | `lunarsim/**` (engine changes only behind opt-in Scenario fields; v2 results must stay byte-identical with them off), `lunarsim/lander/**`, `lunarsim/rover/**`, `lunarsim/terrain.py`, `service/**` (new FastAPI app), `experiments/phase3/**` (new), `tests/**`, `pyproject.toml` optional-dependency groups `[ml]`, `[service]`, `[terrain]` only (report the exact lines; LEAD applies) |
| **FRONTEND** | `site/**` (new Vite project), `web/**` (existing simulator; `web/sim.js` engine still frozen except `exportTrace()`/worker block and a new optional `terrainLegs` hook that LEAD will spec with B-12) |
| **LEAD** | `data/**` (terrain packs, site coordinates, policies, driving tables: generated with BACKEND tools, committed by LEAD), `results/**`, `figures/**`, `paper/**`, `notes/**`, `research_notes/**`, `reports/**`, `README.md`, `.github/**`, `CITATION.cff`, `.team/PLAN.md`, `.team/inbox-*.md` |
| Shared, append-only | `.team/reports.md` |

Workers never run git add/commit/push. LEAD commits per task after review. Real clock times in reports.

## 5. Contracts

### 5.1 Terrain pack — `lunarsim-terrain` v1 (B-9)

Folder `data/terrain/<site_id>/` with (settled by B-9; sizes come from the file, never hard-coded):
- `meta.json`: `{format:"lunarsim-terrain", version:1, site_id, name, source:{product:"PGDA LOLA 5mpp Site01", url, citation, credit}, crs:"+proj=stere +lat_0=-90 +lat_ts=-90 +R=1737400", origin_xy_m:[x0,y0] (map lower-left corner, pixel edge), size_m:[16000,16000] for Site01, layers:{name:{shape, px_m}}, z_encoding:{offset_m, scale_m_per_unit}, stats:{z_min,z_max,slope_p50,slope_p90}, generated:{tool,commit,time}}`
- `height_5m.png` (uint16, 3200² for Site01, z = offset + scale·value), `height_20m.png` (800²), `slope_20m.png`
  (uint8, degrees, computed on the 5 m float grid then block-meaned), `hillshade_20m.png`, optional `illum_240m.png`.
- Conventions: local metres x = X − origin_x, y = Y − origin_y; PNG row 0 = max y; pixel centre (r,c) =
  ((c+½)·px, (rows−r−½)·px); bilinear on centres, clamped; azimuth 0 = +y, 90 = +x, clockwise; shadows and
  line of sight use the Moon's curvature (R 1737.4 km); outside the tile is open terrain. Pad-scale slope is the
  tilt of the mean plane over a 100 m disk (`--slope-stat plane`), because the literal "every 20 m cell ≤5°"
  rule leaves 0.24% of this tile.
- `sites.json`: the nine LunarSim sites placed on this terrain: `{sites:[{id:"BASE", xy_m:[...], kind, slope_deg, illum}], pads:{"0.5":[...],"1":[...],"2":[...],"3":[...],"5":[...]}, corridors:[...]}`
  where `pads[D]` gives PAD_A/PAD_B positions at standoff D km from BASE along terrain-feasible corridors
  (LEAD chooses; B-9 provides the tool `lunarsim terrain place --site ... --standoff 2` that proposes candidates
  by slope ≤5°, illumination, line-of-sight to BASE blocked/unblocked flag).
- Readers: Python `lunarsim.terrain.Terrain(site_id)` with `height(x,y)`, `slope(x,y)`, `profile(a,b,step)`,
  `leg_stats(a,b)` (length, climb, max slope, slope histogram, shadow fraction for a sun azimuth), and JS
  `site/src/terrain.js` reading the same PNG/JSON.

### 5.2 Policy weights — `lunarsim-policy` v1 (B-10, B-13)

- MLP (lander): `{format:"lunarsim-policy", version:1, kind:"mlp", id, env:"lunar/Descent-v0", env_version,
  obs:{names:[...], scale:[...], offset:[...]}, act:{kind:"box"|"discrete", names, low, high},
  layers:[{w:[[...]], b:[...], act:"tanh"}, ..., {w, b, act:"linear"}], deterministic:"mean_clipped"|"argmax",
  training:{algo:"PPO", sb3_version, steps, seed, hyperparams, reward_variant, wallclock_s, git_sha}, card:{...}}`
  Forward pass: Python `lunarsim.lander.policy.MlpPolicy.act(obs)` (numpy) and JS `site/src/policy.js`
  must agree to 1e-6 on a shared test vector file `data/policies/<id>.check.json`.
- CNN (rover): `<id>.onnx` (opset 17) + `<id>.json` card with input spec (patch size, channels, scalars,
  normalisation), output spec, training record; runtime Python `onnxruntime`, browser `onnxruntime-web`.

### 5.3 Lander environment and landing outcomes (B-10, B-12)

Env `lunar/Descent-v0` (Gymnasium): 3-DoF translational point mass (x, y, z, vx, vy, vz) plus thrust
direction with rate limits (Gaudet 2018 formulation), mass flow by Isp, gravity 1.62 m/s². Classes
(constants in `lunarsim/lander/classes.py`, each value flagged):
`CLPS` (≈2,000 kg at gate, 5 kN max, floor 20%, Isp 311), `MK1` (gate mass Assumed ≈9,000 kg, 44 kN max,
floor 8.9 kN, Isp 440 Assumed), `LARGE` (parametric 60 t, hover T/W 1.5, floor 25%). Initial state drawn
around the SPLICE gate (500 m slant, −15 m/s vertical, 30 m/s horizontal) with dispersion; terminal success
box (SPLICE): vz ≤ 2.0 m/s, horizontal ≤ 1.0 m/s, tilt ≤ 6°, rate ≤ 2°/s; landed tilt from local slope +
arrival state; failure if tilt > 12° or velocity box violated. Sensor model: altitude noise/bias/dropout
below 30 m (the documented failure regime). Reward (Gaudet-style, variants switchable): velocity-field
tracking, effort, attitude penalty, +η per step, gated terminal bonus; variants `no_eta` (early-crash
pathology), `hover_bonus` (reward hacking demo), `fuel_heavy`, `plume_aware` (penalise time below 30 m and
high thrust near ground). Episode cap, `check_env` clean.

Settled by B-10: actions are throttle plus two tilt-*rate* commands (the tilt angles are state); observations are
15 values scaled by `env.obs_scale(cls)`; CLPS Isp 311 s is Assumed (Apollo DPS stand-in), MK1's 8.9 kN floor is
flagged conflicting; LARGE starts from a longer gate (400 m, 25 m/s, Assumed).
Per-landing outcome record (what the DES samples): `{miss_m:[dx,dy], v_td:[vx,vy,vz], tilt_deg, prop_used_kg,
t_below_30m_s, ok:bool, failure_kind:null|"velocity"|"tilt"|"offpad"|"sensor"|"timeout"|"lost"}`. DES landing model
(Scenario `landing_model`, default None = v2 behaviour): sample an outcome for the lander class from
`data/policies/outcomes_<policy>.json` (empirical table from the Monte Carlo, with `sigma_scale` to sweep);
offset → cargo released at pad + miss (if |miss| > pad radius: off-pad, rover legs extended over terrain
with the rough-terrain speed factor); failure → cargo loss or recovery delay per `failure_policy`.

### 5.4 Rover environment and driving tables (B-11, B-13)

Env `lunar/Drive-v0`: 2.5-D on the terrain pack; pose (x, y, ψ), speed; obs = body-aligned 32×32 patch
(relative height, slope, roughness) + scalars (speed, heading error, distance to waypoint, sun azimuth
relative, shadow flag); actions steer-rate, throttle in [−1,1]; kinematic bicycle; speed cap by autonomy
level (teleop curve calibrated to Litaker: 3.24/2.56/2.03/1.76 km/h at 0/4/6/8 s RTT), slope cap 15° nominal
/ 20° hard, slip from the Hu et al. 2024 lunar-g curve (≈5-10% at 0-5°, 20% at 10-15°, dig-in >80% near 30°),
energy = rolling + grade + slip losses calibrated to LRV 57-60 Wh/km at ~700 kg (flag Assumed for 1.6 t),
lighting penalties from the JSC study (up-sun tacking ±20-30°, shadow entry slow-down). Expert: A* on a
slope/lighting cost grid + pure pursuit. Teleop model: command delay RTT plus stop-to-confirm cadence.
Intervention: policy leaves corridor, exceeds slope, stalls, or collides → count; cost = RTT + recovery time
(not Nvidia's 6 s). Autonomy levels: `teleop`, `supervised`, `autonomous`.

Driving tables `data/driving/driving-v1.json`: `{format:"lunarsim-driving", version:1, terrain:site_id, policy,
legs:{"A->B":{autonomy:{teleop:{rtt_s:{"4":{time_h:{mu,sigma,dist:"lognormal"}, energy_kwh:{...},
interventions:{lambda}}}}, ...}, lighting:{...}}}}` for every ordered site pair and pad position set.
The DES (Scenario `autonomy_model:"driving-v1"`) samples leg time/energy/interventions from these instead of
the slope-class multipliers. Validation targets before use: 12% speed loss at 4 s RTT; 0.4-4.4 kWh PSR round
trips (Chen 2026, scaled to our mass).

### 5.5 Plume keep-out and trace v2 (B-12)

Scenario `plume: {keepout_km: R, standdown_h: T, shelter_sites:[...], applies_to:["CLPS","MK1","LARGE"]}`.
During [t_land − T, t_land + T]: no job may start or end at the pad; vehicles within R of the pad are
re-routed to the nearest shelter site (line-of-sight blocked flag from the terrain) and their current job is
suspended; evacuated vehicles return to their pre-evacuation site after the window (`plume.return_after`, default
on); anticipatory staging for a pad with an upcoming window waits at the nearest site outside R from that pad (the
keep-out boundary; the shelter only when it is that nearest site). Metrics: `standdown_vehicle_h` =
`standdown_hold_h` (jobs held) + `standdown_drive_h` (evacuation and return drives). Metrics added: `plume_standdowns`,
`standdown_vehicle_h`, `landing_miss_m_mean`, `offpad_landings`, `failed_landings`, `cargo_lost_kg`,
`km_offpad_extra`, `interventions`, `intervention_h`, `prop_residual_kg_mean`.
Trace v2 (`version:2`, readers accept v1): `landings` rows become objects `{t, type, pad, xy_m, miss_m,
tilt_deg, ok, descent:[[t,x,y,z,vx,vy,vz,throttle], ...] (1 Hz, optional)}`, new `plume_windows:[[t0,t1,pad,R]]`,
`shelters:[...]`, vehicles gain `autonomy_level`, jobs gain `interventions`, `energy_kwh`; `terrain:site_id`.

### 5.6 Service API v2 (B-14) — FastAPI, SQLite WAL, worker, SSE

Base `/v2`. JSON; errors `{error, code}`; cookies `HttpOnly; Secure; SameSite=Lax` (needs app./api.<domain>);
fallback bearer token for the github.io origin. Rate limits per route (429 + Retry-After); CPU-minute
budget per account per day enforced at enqueue; Turnstile on sign-up (owner decision).
| Endpoint | Purpose |
|---|---|
| `GET /v2/health`, `GET /v2/version` | liveness; engine version, git sha, policies loaded |
| `GET /v2/auth/{orcid|github}/start` → redirect; `GET /v2/auth/{p}/callback`; `POST /v2/auth/magic` {email}; `GET /v2/auth/magic/{token}`; `POST /v2/logout`; `GET /v2/me` | sign-in (Authlib), sessions table |
| `POST /v2/runs` {scenario v1, mechanism, seeds[], options{landing_model, plume, autonomy_model}, public} → {run_id, status} | enqueue; stores provenance (engine semver, git sha, dirty, patch sha, lockfile sha, python/platform, scenario sha, policy shas, seeds per stream) |
| `GET /v2/runs/{id}`; `GET /v2/runs/{id}/events` (SSE: queued/running/progress/done/failed); `GET /v2/runs/{id}/trace` (blob, content-addressed); `GET /v2/runs/{id}/summary` | results |
| `POST /v2/runs/{id}/replicate` → new run with identical inputs; result compares output sha → `replicated:true|false` | machine-checkable replication badge |
| `GET /v2/runs?public=1&metric=&scenario=&limit=`; `POST /v2/runs/{id}/publish` | gallery/leaderboard (only `git_dirty=false` runs on tagged releases rank) |
| `GET /v2/policies`, `GET /v2/policies/{id}`; `GET /v2/terrain`, `GET /v2/terrain/{id}` | model cards, weights, terrain meta |
DB (SQLite, WAL): `users(id, orcid, github_id, email, name, created)`, `sessions(id, user_id, expires)`,
`runs(id ulid, user_id, created, status, engine_version, git_sha, git_dirty, patch_sha, lock_sha, python,
platform, scenario_sha, scenario_json, mechanism, options_json, seeds_json, policy_shas_json, output_sha,
summary_json, parent_run_id, public, doi, cpu_s)`, `run_events(run_id, seq, t, kind, payload_json)` append-only,
`blobs(sha, media, bytes, path, created)` content-addressed `blobs/<sha[:2]>/<sha>`, `quota(user_id, day,
cpu_s)`. Litestream config to S3-compatible storage; Dockerfile; Caddyfile; `service/README.md` with deploy
steps for Hetzner CX23 (owner decision). The stdlib `lunarsim serve` stays for local use.

### 5.7 Site (F-5…F-10) — Vite + Three.js + Observable Plot, static on GitHub Pages

Pages: `/` (landing: real-terrain 3D hero with the polar sun, three honest headline numbers from results,
what-this-is, links), `/world` (3D base on LOLA terrain: time scrubber, landers descending along policy
trajectories, plume keep-out rings and stand-downs, rovers on real legs, night, telemetry rail with
numbers over time; loads trace v2 from a run, a sample, or a file), `/lab/lander` (the descent env in
the browser with the trained policy: live score counter, throttle/altitude/velocity telemetry, reward
sliders → re-score an episode, the hover-hacking demo, Monte Carlo dispersion plot from results),
`/lab/rover` (drive a real leg: BC policy vs expert vs you with latency; autonomy %, interventions/km,
energy; lighting toggle), `/simulator` (existing app, moved under the site), `/method`, `/paper`, `/data`,
`/about`, `/account` (sign-in, saved runs, replicate badge, leaderboard), `/changelog`, `/verification`.
Design: Distill-like measures (16 px → 1.06 rem, line-height 1.7, ink rgba(0,0,0,.8), hairlines .1), one OFL
sans (Source Sans 3, self-hosted, renamed if subset) + tabular monospace for telemetry; Tol Bright / Okabe-Ito
categorical, Crameri batlow for elevation; light and dark themes; WCAG 2.2.2/2.3.3 (pause control,
`prefers-reduced-motion` tiering); canvas mirrored by a DOM telemetry table and a 2D plan view (also the
Tier-0 fallback via `detect-gpu`); pixel budget ~5.2 MP; 30 fps floor. No stock space art; images are NASA
(credited, no insignia) or our own renders; vehicles are labelled "representative" parametric models.
Every figure: SVG/PNG/CSV download; every number traceable to a logged variable with units and its flag.

## 6. Experiments (LEAD runs; BACKEND writes runners in `experiments/phase3/`)

| Suite | Content | Validation anchor |
|---|---|---|
| E15 lander MC | per class × reward variant × sensor model: 5,000 episodes; miss, touchdown box, propellant, t<30 m; vs a classical closed-loop law (ZEM/ZEV or Apollo polynomial) and an open-loop optimum | Gaudet-style protocol; SLIM/Blue Ghost/IM demonstrated misses as plausibility band |
| E16 driving tables | all legs × autonomy × RTT × lighting; interventions/km | Litaker −12% at 4 s; Chen 0.4-4.4 kWh |
| E17 dispersion × standoff | σ_scale ∈ {0.25…10} ∪ {req 100 m 3σ, demonstrated set} × D ∈ {0.5,1,2,3,5} km × mechanism × phase | NASA bands >50 m, >1,000 m, ≤5,000 m |
| E18 plume keep-out | R ∈ {0.2,0.5,1,2,3} km × T ∈ {0.1,0.5,2,6} h × mechanism × night | Wittal impacts-vs-distance ordering |
| E19 autonomy × fleet | teleop(4,6,8 s)/supervised/autonomous × fleet size | LTV-SYS-071 6-8 km/day |
| E20 pad siting | hauling cost + pad cost (Metzger & Autry) vs D under dispersion; the law fit with CIs | — |
Precision runs for the headline cells as in E14.

## 7. Paper v3

Outline: Introduction (what NASA leaves blank, quoted) · Related work (four disconnected traditions) ·
Testbed (DES recap, terrain, learned lander, learned driver, plume module; every parameter flagged) ·
Verification (13 checks + new: policy MC vs classical law; speed-vs-latency reproduction; energy anchor;
Python-vs-browser agreement) · Results E1-E14 condensed, E15-E20 new, the law · Discussion and limitations
(PSI uncertainty, no interventions/km data, Earth-test optimism, name collision, unverified items table) ·
Availability (Zenodo DOI, policies, terrain, run records). Voice: plain, specific, first person plural
where natural, no hype; figures regenerated by `experiments/make_figures.py` with checked numbers;
captions state n, CI and flag.

## 8. Decisions needed from the owner (not blocking M5-M7)

1. Hosting and domain for the service and sign-in (Hetzner CX23 ≈ €4.49/month + a domain; cookies need
   app.<domain>/api.<domain>). Fallback: public static site without accounts, API local-only.
2. OAuth registrations: ORCID Public API client (owner's ORCID), GitHub OAuth app; email sender for magic links.
3. Project name: DECIDED Oct 15 — renamed **LunarHaul** (three collisions found: PUTvision 2023, Element Robotics
   product, Dundee 1999). Brand now; package/format identifiers renamed in one task at release. Owner actions:
   register `lunarhaul` on PyPI and npm, rename the GitHub repository (old URL redirects), trademark clearance.
4. Terrain site: default Connecting Ridge (PGDA Site01), alternative Shackleton rim (Site04).
5. Zenodo account for DOIs on release.

## 8b. Release checklist (LEAD; from the paper draft's contradiction list and the reviews)

- [x] Tables, refs, E16/E17/E19 full, E18 1,237/1,248 cells, E20 on that, figures, paper back half drafted (Oct 15 20:40).
      Remaining: last 11 E18 cells + final e20 + figure refresh (owner go-ahead after the memory stop), paper stage 2.
- [x] PPO policies retrained under reward v2 (n = 500 Monte Carlo; the 2,000-episode rerun is optional, CIs are already ±4 %).
- [x] Final learned lander `lander_CLPS_bc_v3_s0` (89.0 %) with Monte Carlo and the E15 table.
- [x] Rename pass: README, CITATION.cff (title, version 3.0.0, date), pyproject description, `lunarsim serve`
      banner text; package/format identifiers stay until the dedicated rename task; the simulator footer.
- [x] Verify which NASA document carries the exact "reduction in distance" sentence; reconcile v2 Appendix A's
      LRV 95 Wh/km with the measured 57–60 Wh/km (state both and the source of each).
- [ ] Owner actions: register `lunarhaul` on PyPI/npm, rename the GitHub repository, hosting + domain for the
      service, OAuth registrations, Zenodo DOI.

## 9. Process (unchanged)

Tasks in the inboxes as `## B-n [OPEN|IN PROGRESS|REVIEW|DONE|REWORK]`; workers change only their own
status tags; reports appended to `.team/reports.md` with real clock times; LEAD reviews (diff, tests,
baseline identity, page in a browser), commits per task, assigns the next.
