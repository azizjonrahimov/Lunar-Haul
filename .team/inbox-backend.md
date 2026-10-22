# BACKEND inbox

Read `.team/PLAN.md` first (ownership in §4, contracts in §5). Do not run git add/commit. Report in `.team/reports.md`
when done, with the real clock time (`date +%H:%M`). Run tests with `.venv\Scripts\python -m pytest tests -q`.
Memory: 8 GB machine, three sessions. No multi-process training; smoke runs ≤300k steps in one process (`--no-subproc`).
LEAD runs the long jobs in the background and commits data/.

## Done: B-1…B-8 (v2.1) · B-9 terrain (b2ef8b4) · B-10 lander (40891db) · B-11 rover (876285a) · B-12 engine
## integration + trace v2 (9b258c3)

# ── Phase 3 (PLAN.md §1-§6; research report in reports/) ───────────────────────────────────────────────
Ownership: lunarsim/**, lunarsim/lander/**, lunarsim/rover/**, lunarsim/terrain.py, service/**, experiments/phase3/**,
tests/**. Every physical constant carries a flag (Measured / Spec / Modelled / Assumed) and a source URL.

## B-10b [DONE] Lander policy: close the gap to the classical law
Facts: LEAD's 2M-step run (CLPS, baseline reward, seed 0, 8 DummyVecEnv envs, 20 min) ends at **box/pass 57-60 %**,
training return flat at ≈ −60 from 0.9M steps on. The classical ZEM/ZEV law passes 93.8 % under the same dispersion.
Artifacts (do not delete): `runs/lander_CLPS_baseline_s0/` (model.zip, tb, curve) and `data/policies/lander_CLPS_
baseline_s0.json`. The site's lander lab will show whatever the Monte Carlo says, so the number must be real.
Steps:
1. Diagnose with the saved model: 200 deterministic episodes; classify failures (velocity / tilt / sensor / timeout /
   lost); distributions of |miss|, vz, vh, tilt at contact; is it hovering, landing hard, drifting, or timing out?
2. Try, each as a ≤300k-step single-process smoke run, in this order, and keep what helps:
   (a) behaviour-cloning warm start from the classical controller: collect ≈2,000 episodes of (obs, action) from the
       ZEM/ZEV law expressed in the env's own action space (throttle + tilt-rate commands), fit the SB3 policy's action
       mean by supervised regression (`bc_warmstart.py`), then PPO fine-tune with lr 1e-4 and clip 0.1;
   (b) curriculum: 60 % near-ground starts for the first half of training, then the gate;
   (c) reward: velocity-field weight rising near the ground, terminal bonus +50, continuous crash penalty;
   (d) PPO: n_steps 2048, batch 256, lr 1e-4 with linear decay, ent_coef 0.0, gamma 0.995, net [128,128].
3. Deliver `train.py --init-from-bc <path>` and `--hyper-set <name>`, `lunarsim/lander/bc_warmstart.py`, and update
   the policy card fields (`training.init`, `training.hyper_set`). Tests for the new code paths (fast).
4. Report the best box rate reached in smoke runs with its curve; LEAD runs the final 2-3M-step trainings for the
   three classes and the reward variants.
Files: lunarsim/lander/{train,bc_warmstart,evaluate}.py, tests/test_lander.py
Done when: a documented recipe reaches ≥90 % box rate within ~1M steps in your smoke test, or the best achieved is
reported with evidence and the remaining gap explained.
Due: 17:30

## B-15 [DONE by LEAD agent, b704d1b + 209087d + dc587cb] Experiment runners E15-E20 (PLAN §6)
Goal: `experiments/phase3/run_phase3.py` with suites as functions (pattern of `experiments/run_all.py`: cells,
multiprocessing Pool, resumable CSV per suite in `results/`, 30 seeds per cell, the same seed convention), plus
`experiments/phase3/fit_law.py` that fits the dispersion/standoff/keep-out law (log-linear with interactions, CIs by
seed bootstrap) and writes `results/table_E17.csv`, `table_E18.csv`, `table_E20.csv` and `E20_fit.json`.
Suites: E15 lander Monte Carlo summary table from the outcome files (classical and learned policies, per class and
variant; n, pass rate, |miss| mean/p90, propellant, t<30 m; the classical-vs-learned comparison columns);
E16 driving-table validation table (flat-leg speed vs RTT vs JSC; PSR round trip energy vs Chen band);
E17 dispersion × standoff: `landing_model` sigma_scale ∈ {0.25, 0.5, 1, 2, 5, 10} plus "req100" (resample so the
3σ miss is 100 m) × pad_standoff_km ∈ {0.5, 1, 2, 3, 5} × mechanism ∈ {inhouse, marketplace} × phase ∈ {P2, P3},
autonomy_model driving-v1 at the scenario RTT, no plume;
E18 plume: keepout_km ∈ {0.2, 0.5, 1, 2, 3} × standdown_h ∈ {0.1, 0.5, 2, 6} × mechanism (4) × night on/off, P2,
standoff 1 and 3;
E19 autonomy × fleet: vehicle autonomy level sets {all teleop at 4/6/8 s, supervised, autonomous} × fleet size
{2, 4, 6, 8} (the P2 fleet variants), marketplace and inhouse;
E20 pad siting: hauling cost from E17 plus pad construction cost (Metzger & Autry 2022: $130 M / $229 M / $548 M
at $10K / $100K / $300K per kg, flag Spec) amortised over 10 years, vs standoff and dispersion; the minimum and the
law fit with bootstrap CIs.
Done when: `python experiments/phase3/run_phase3.py e15 e16` runs end to end; `e17 e18 e19 e20` run on 2 seeds in
a smoke mode (`--seeds 2`) in under 10 min; the fit script produces the tables from the smoke CSVs; tests cover cell
construction and the fit on synthetic data. LEAD runs the full suites.
Due: Oct 16 14:00 (after B-10b)

## Queued
- B-13 BC driver: PilotNet-style CNN on heightmap patches (torch cu126), DAgger relabelling against the expert, ONNX
  export + model card, autonomy % with RTT-based intervention cost, interventions/km; driving tables regenerated with
  the learned driver (LEAD runs the long training).
- B-14 Service v2 (PLAN §5.6): FastAPI + SQLite WAL + worker + SSE + Authlib (ORCID, GitHub, magic link) +
  provenance run records + replicate endpoint + leaderboard; Dockerfile, Caddyfile, Litestream config, deploy README.
- Small: `lunarsim validate` prints "trace v1" for a version-2 trace; print the real version.

## B-15 addendum (from LEAD's pilot, see reports.md)
- Report paired differences on common seeds (vs the no-plume cell for E18, vs standoff 1 km for E17) with bootstrap CIs; raw means have ±2.5 h CIs at 30 seeds.
- E17 and E18 cells: add phase P3 and the P2 fleets of 2 and 4 vehicles (`lunarsim.phases.FLEETS`), where utilisation is high; at P2 with six vehicles utilisation is 0.03 and keep-out is nearly free.
- Cost: add `cost_per_kg_with_energy_usd` = cost_per_kg_usd + energy_price × energy_kwh / delivered_kg with energy_price swept over {0, 500, 2000, 5000} $/kWh (Assumed; cite nothing, label it), in the fit script, not in the engine.

## Reassignment 13:59 (LEAD): B-15 (experiment runners) and B-14 (service v2) are being built by LEAD-run agents in
## parallel. BACKEND: do not start them. After B-10b, go to B-13 (BC driver). The `validate` version label fix stays yours.

## B-10b: accepted as PARTLY DONE at 14:22; committed. LEAD runs the DAgger recipe now. Decision: the paper's
## "learned lander" is imitation + DAgger from the classical law; PPO is the comparison, with its reward-misalignment
## failure explained.

## B-8b [DONE] (10 min, first) tests/test_formats.py must accept a v2 file among the bundled sample traces
LEAD committed `data/sample_traces/P2_marketplace_seed3_v2.json` (trace v2, full year). Four tests now fail:
`test_sample_traces_are_v1[...v2.json]`, `test_legacy_traces_accepted[...v2.json]`, `test_validate_cli_bundled_files`
(expects 12 files / v1 labels), `test_validate_cli_legacy_copies`. Make them version-aware: v1 samples keep their
checks, v2 samples are validated as v2 and are not stripped into legacy copies; the CLI test counts files rather than
assuming 12 and accepts "trace v2". Files: tests/test_formats.py. Done when the full suite is green.
Due: 15:00

## B-10c [DONE] (<= 1 h) The end-of-training evaluation printed 3 % after a fine-tune whose checkpoints evaluated at 50-74 %
Find the cause (evaluation env version vs training env, VecNormalize or policy state at save time, seed set,
deterministic flag) and fix it so the number in the policy card (training.final_eval) is the same quantity that
evaluate.py computes. Add a test that trains 5k steps, saves, reloads and compares the two evaluations on 20 episodes.
Files: lunarsim/lander/train.py, lunarsim/lander/evaluate.py, tests/test_lander.py
Due: 16:00

## B-13 [DONE] BC driver for the rover (after B-10c)
Goal: PLAN section 5.4. lunarsim/rover/bc.py: dataset from the scripted expert on lunar/Drive-v0 over all legs and
lighting cases (observation = 32x32x3 patch + scalars; labels = expert steer-rate and throttle), PilotNet-style CNN
in torch (cu126 wheel; fall back to CPU if CUDA is unavailable and say which), DAgger relabelling (>= 3 rounds),
export to ONNX (opset 17) + data/policies/rover_<id>.json card (input spec, normalisation, training record), an
OnnxDriver implementing the same act(obs) interface as the expert, evaluation = interventions/km and autonomy %
with intervention cost RTT + recovery, per autonomy level, against the expert; tables.py --driver <id> to regenerate
the driving tables with the learned driver. Keep datasets small (<= 2 GB on disk; uint8/float16 npz under runs/).
Tests: dataset shapes, a 200-step smoke training on CPU, ONNX export round trip equals torch to 1e-5, OnnxDriver
drives a flat leg. LEAD runs the long training.
Files: lunarsim/rover/bc.py, lunarsim/rover/onnx_driver.py, lunarsim/rover/tables.py (driver option), tests/test_rover.py
Due: Oct 16 16:00

## B-11b [DONE] (before B-13) Rover slip from the digitised Hu et al. 2024 curves; MK1 throttle floor
Verification round 1 (research_notes/.../verification_round_1.md, section 5) digitised Hu et al. Fig. 7/13: 440 kg
VIPER-class in lunar gravity on GRC-3, slip at 0/5/10/15/20/25/30 deg by soil friction angle: phi 47.8: 0.01/0.03/
0.08/0.18/0.35/0.76/0.88; phi 42.0: 0.04/0.13/0.30/0.67/0.86/0.92/0.96; phi 37.8: 0.12/0.32/0.74/0.88/0.93/0.95/0.97.
Replace the current slip table in lunarsim/rover/physics.py with these three curves (flag Modelled, cite the figure),
interpolate in slope and in friction angle, and sample phi per leg (or per cell) uniformly in [37.8, 47.8] deg from
the ops stream (document the choice; the median curve is phi 42). Keep the 80 % dig-in rule. Expose phi as a
Scenario/tables parameter so E16 can report the three curves. Re-run the teleop calibration test (it is on flat
ground, so it should not move) and the PSR round-trip energy. LEAD regenerates driving-v1.json afterwards.
Also lunarsim/lander/classes.py: MK1 throttle floor = 8.9 kN is now Spec (Blue Origin, Dec 4 2020 release: "throttling
down to 2,000 lbf"); drop the 4.4 kN / 10 % variant and the "conflicting" wording; landed mass stays Assumed (bound
5.1-11.5 t; a single BE-7 can hover it in every case).
Files: lunarsim/rover/physics.py, lunarsim/rover/tables.py, lunarsim/lander/classes.py, tests/test_rover.py
Due: Oct 16 11:00

## Decision 14:42 (LEAD): the project is renamed LunarHaul
"LunarSim" collides with PUTvision's 2023 rover simulator, Element Robotics' commercial product and a 1999 Dundee
lander-vision simulator (verification_round_1.md, "Name candidates"). New project name: LunarHaul ("LunarHaul: a
verified testbed for lunar surface logistics"). Rules: (1) site titles, headers, footer, page copy and the paper use
LunarHaul from now on; "formerly LunarSim" once on the About page and in the paper's footnote. (2) Code identifiers,
the Python package `lunarsim`, file formats (`lunarsim-trace` etc.), CLI and URLs stay unchanged until a single rename
task at the release milestone (LEAD, all sessions idle). (3) Do not touch pyproject/package names yourselves.

## B-12b [DONE] (30 min, before B-11b) Landing schedule must not depend on dict order
The service's provenance work found that `sample_landings` (lunarsim/scenario.py:172) iterates `sc.landings_per_year`
in insertion order, so `{"CLPS":4,"MK1":3,"LARGE":1}` and the same mapping with sorted keys produce different years
(P2-default seed 0: prio-1 delay 2.55 h vs 3.08 h). Make the draw order fixed and canonical: iterate in
`LANDER_TYPES` declaration order (CLPS, MK1, LARGE), which equals the phases' insertion order, so every committed
result stays byte-identical (the compare md5 test must still pass) while any key order in a scenario file gives the
same year. Add a test: a scenario with reversed keys equals the original seed for seed. Note the rule in the
scenario-format docstring (config.py). Tell LEAD so the service can switch to fully sorted canonical JSON.
Files: lunarsim/scenario.py, lunarsim/config.py docstring, tests/test_formats.py or test_phase3_engine.py
Due: Oct 16 10:00

## B-10d [DONE] (after B-12b and B-11b) Why DAgger degrades the clone, and an observation the clone can use
LEAD's run of your recipe (`bc_warmstart --cls CLPS --episodes 1000 --dagger 4 --dagger-episodes 400`): classical
93.6 %; BC round 0 **75.0 %**; DAgger rounds 69 / 60 / 51 / 43 % (sensor failures rise 16 → 37, tilt 4 → 17). The
run then crashed writing its JSON record: `KeyError: 'box_rate'` in the summary dict (data["box_rate"]); the zip was
saved (runs/bc/bc_CLPS.zip; exported by LEAD as data/policies/lander_CLPS_bc_s0.json).
Steps: (1) fix the KeyError. (2) Test the hypothesis that the classical law's labels are not a function of the
observation (its filtered velocity / held thrust direction): measure label inconsistency in the aggregated set
(variance of the expert action conditioned on near-identical observations) per round. (3) Make the policy able to
use what the expert knows, choosing one: (a) an observation-consistent expert (a memoryless version of the classical
law that acts on the current noisy observation only; report its own box rate), or (b) observation augmentation:
append last-valid altitude, its age, and a two-step history of the altitude channel (obs 15 → 19 values; bump
env_version to 3; obs_scale updated; FRONTEND must port it, so document the exact new names/scales). (4) Rerun BC +
2 DAgger rounds with the fix; report box rates per round. Target: ≥ 85 % if (b); report honestly otherwise.
Files: lunarsim/lander/{bc_warmstart,env,evaluate,export}.py, tests/test_lander.py
Due: Oct 16 15:00

## B-12c [DONE] (after B-10d) Two effects in the preliminary Phase-3 results that need an explanation or a fix
1. E18, in-house, P2-4-vehicles, night 15 %, keep-out 1 km: the paired delay difference vs no plume is **negative**
   (−1.1 to −1.4 h, bootstrap CI excluding 0) at several stand-down levels: a keep-out that reduces urgent delay.
   Hypothesis: evacuating idle vehicles from inside R to the shelter acts as accidental staging for an in-house fleet
   that otherwise parks at the pad; or the hold/re-plan loop re-dispatches better. Reproduce on 10 seeds
   (`run_phase3.py` cells or the CLI), trace one year, and say which mechanism it is. If it is a modelling choice
   (where evacuated vehicles go), make it explicit and defensible (e.g. evacuate to the nearest shelter, then return
   to the pre-evacuation site after the window) and report the effect size with and without the return. If it is a
   genuine effect, document it for the paper.
2. E16: for some legs the night energy is below the day energy (teleop BASE<->PSR 1.77 kWh night vs 1.84 day).
   Check whether it is the A* lighting cost (day routes tack around up-sun headings, so they are longer) and report
   the day/night route lengths; if energy per metre falls at night, that is a bug.
Also: `e15_rows` in experiments/phase3/run_phase3.py (LEAD's) uses os.path.relpath and fails across drives; LEAD fixes.
Files: lunarsim/phase3.py, lunarsim/engine.py (only if a fix is needed), tests/test_phase3_engine.py
Due: Oct 16 18:00

## B-11c [QUEUED until LEAD says the final runs are done] Up-sun rule tie on exact 45-degree headings
`d <= UP_SUN_HALF_ANGLE_DEG` sits exactly on the A* diagonal heading for cardinal sun azimuths, so the factor flips on
the last bit of the heading (platform libm). Replace with a smooth or tie-safe rule (e.g. a cosine-shaped penalty, or
`<` with headings snapped to 1e-9 deg before the comparison) in physics.py and the A* cost, document it, and tell
LEAD so the tables, refs and E16 can be regenerated together.

## B-10e [DONE] (go for (b)) Observation v3 for the lander clone, after the cheap option
Step 1 (cheap, stays at env v2): weight terminal-phase samples (h < 30 m) 3x in the BC loss with the memoryless
expert; rerun BC + 2 DAgger; report the 500-episode box rate. Step 2 (if < 90 %): observation v3 = the 15 values plus
last-valid altitude estimate, its age (s), and the two previous altitude readings (obs 19; ENV_VERSION 3; obs_scale
extended; document names/scales/offsets exactly, FRONTEND ports them in F-15); regenerate tests/fixtures/
lander_parity.json and the export check layout; rerun BC + DAgger with the memoryless expert; report. Keep v2 policies
loadable (the runtime reads obs names from the card; the env must accept `obs_version` so old cards still run).
Files: lunarsim/lander/{env,bc_warmstart,export,evaluate,policy}.py, tests/test_lander.py, tests/fixtures/*
Due: Oct 16 14:00

## B-10e addendum: policy cards for imitation policies
`lunarsim.lander.export` on a BC zip leaves `training` empty (FRONTEND had to infer class/variant from the id).
Fill it from the BC record next to the zip (runs/bc/<name>.json): algo "BC" or "BC+DAgger", expert (classical /
memoryless), episodes, samples per round, box rate per round, inconsistency per round, epochs, net, seed, env_version,
wallclock, git sha; `cls` and `reward_variant` ("baseline": the clone is scored with the baseline reward) explicit.
Re-export `lander_CLPS_bc_s0` and `lander_CLPS_bcml_s0` from their zips (runs/bc/bc_CLPS.zip, bc_CLPS_ml.zip) and
tell LEAD; the weights must not change (the check vectors must still pass).

## LEAD 18:20: MEMORY. 0.3 GB free of 7.9 GB. The final E17/E18 suites (3 workers) have priority until they finish
(LEAD will say when). Until then: run only single test files, no full `pytest tests`, no training or smoke runs > 1
minute, and prefer reading/writing code to running it. LEAD stopped the rover-driver training to make room.

## B-10f [DONE] (small) Policy cards for imitation policies: the addendum under B-10e (fill `training` from the BC record on export; re-export bc, bcml, and later bc_v3 without changing weights). Due: Oct 16 11:00.
## B-11c is still queued until LEAD says the suites are done.

## B-16 [DONE] Exact cost per landed kilogram
`Metrics.summary` gains `delivered_nonbulk_kg` (delivered mass of non-bulk, non-return cargo) and
`cost_per_landed_kg_usd` = 1e6 x (fleet + operator cost) / delivered_nonbulk_kg. Existing columns and values stay
byte-identical; the identity test compares the v2 column set (update it to select those columns). The web engine
(`web/sim.js`) computes `cost_per_landed_kg_usd` as 1e6 x cost / (delivered - bulk released); tell FRONTEND the exact
definition so F-17 can align it. results/README.md wording to LEAD.
Files: lunarsim/engine.py, tests/test_phase3_engine.py or test_verification.py

## B-12d [DONE] Two keep-out oddities in the final E18 (fig24)
1. For greedy / batched / marketplace at 3 km keep-out, a 2 h stand-down costs more stand-down vehicle-hours than 6 h
   (76 vs 70 h/yr). Check the shelter/return logic: a shorter window may trigger more evacuation-return cycles; say
   whether that is the mechanism and whether it is defensible.
2. Marketplace, P2 4 vehicles, night, keep-out 0.2/0.5 km (smaller than the 1 km standoff) shows +0.9 h delay (CI
   excluding 0) only at the 6 h stand-down. Explain (staged vehicles caught by the hold?).
Files: lunarsim/phase3.py, tests. Report in reports.md; no engine change without LEAD's go.

## Release 20:29 (LEAD): the suites are effectively done (E18 at 1,237/1,248 cells; the last cells wait for the owner's
## memory go-ahead). B-16 (exact cost per landed kg; additive column) and B-12d (investigation only) are OPEN now.
## B-11c (up-sun tie) is DEFERRED past version 3: it would force regenerating the tables and rerunning E16-E19; the
## paper documents it as a known numerical fragility. Keep runs short (single process, minutes).

## B-12e [DONE] (small, ≤ 1 h) Keep-out metric split and the staging target
1. Metrics: keep `standdown_vehicle_h` (total) and add `standdown_hold_h` (jobs held at the boundary) and
   `standdown_drive_h` (evacuation + return drives); additive columns, v2 columns byte-identical.
2. Staging: when marketplace anticipatory staging targets a pad with an upcoming window, stage at the nearest site
   outside R to that pad (the boundary; at R = 0.2-0.5 km with a 1 km standoff that is DEPOT or the other pad), and
   fall back to the shelter only when no site outside R is nearer than the shelter. Document the rule in phase3.py and
   the PLAN wording; add a test that R < standoff leaves the paired delay vs no-plume within noise.
3. Report the effect on the P2-4-vehicles marketplace night cells (R 0.2/0.5 km, T 6 h) with 10 seeds.
Files: lunarsim/phase3.py, lunarsim/engine.py (metrics), lunarsim/schemas (if the trace carries the split), tests/test_phase3_engine.py
Due: Oct 16 09:00

## B-17 [REVIEW] (small, <= 45 min) Version 3.0.0 in the package and a LunarHaul banner on `lunarsim serve`
Goal: `lunarsim/__init__.py` `__version__ = "3.0.0"` (LEAD bumps `pyproject.toml` and `CITATION.cff` in the same commit;
check nothing else hard-codes 2.0.0 in `lunarsim/**`, `service/**`, `tests/**`). `lunarsim serve` prints one banner line on
start: `LunarHaul (lunarsim 3.0.0) local API on http://127.0.0.1:<port> ...` and `lunarsim --version` prints `lunarsim 3.0.0
(LunarHaul)`. No other behaviour change; the baseline md5 must stay `ebb9e0dea68005cddf4ab4d2bda1bfdd`.
Do NOT run the full test suite yet (LEAD is training the rover driver; memory): run only `tests/test_cli.py` or the
single file that covers `serve`/`--version`, single process. Report the exact lines printed.
Files: lunarsim/__init__.py, lunarsim/cli.py, lunarsim/server.py (banner only), tests/** (one test for --version if cheap)
Done when: `lunarsim --version` and the serve banner print as above; the single test file passes; report in reports.md with clock times.
Due: Oct 16 04:00 (written 02:44)

## B-18 ADDENDUM 09:08 (do this FIRST, before the tables): the card's evaluation block is not credible as it stands
`data/policies/rover_bc_s0.json` -> evaluation (6 legs x 5 lighting, rtt_s 4.0 for every level): EXPERT autonomous 430.8
interventions/km, autonomy 0.70 %, 107 km in "3,924 h"; expert supervised 366/km; LEARNED autonomous 122.7/km, autonomy 3.15 %,
175 km in "1,868 h"; 29/30 reached in every row. The fast integrator (tables.py) and the Figure-4 step drive (BASE->PSR, teleop 4 s:
4.74 km in 2.18 h, 48 stops, 0 interventions) give sane numbers, so the step-by-step evaluation in bc.py (drive()/evaluate) is
reporting something else: a units slip (seconds or steps labelled hours), "interventions" counting stop-to-confirm or slip events
per step, the autonomous level driven with the teleop cadence (rtt 4.0 applied to every level), drives running to the 50,000-step
cap after "reached", or a combination. Diagnose with one leg (BASE->DEPOT, sun 90, phi 42, seed 0): drive the expert through
bc.drive() and through the F-8 path, print steps, sim time, km, stops, interventions by kind, and reconcile. Fix the reporting (or
the evaluation setup) in bc.py and tables.measure_driver if they share it; then re-evaluate the SAVED ONNX (no retraining; load
rover_bc_s0.onnx through onnx_driver) on the same 6 legs with a sane per-drive step limit, and rewrite only the card's
`evaluation` block (keep onnx_sha256 and training as they are; add `evaluation_note` saying it was recomputed and why). Only
then produce driving-v1-learned.json. If the learned driver's true rate is still hundreds per km, that is the result; do not tune.
Report the reconciled numbers for expert and learned with their definitions. Single process; keep the eval under 10 min per
foreground command (fewer legs or a step limit) or ask LEAD to run it outside Claude Code.

## B-18 [DONE] (the driver is committed) Learned-driver tables, parity fixture, full suite
Goal: (1) `python -m lunarsim.rover.tables --driver data/policies/rover_bc_s0.json --out data/driving/driving-v1-learned.json`
(single process; the expert's `driving-v1.json` is NOT touched: the suites and the paper use it). Report the learned driver's
interventions/km and time-ratio distribution over legs and lighting cases, and the legs it did not finish (kept at the expert
model by the tool). (2) A parity fixture for F-17: `tests/fixtures/rover_driver_parity.json` for BASE->DEPOT, autonomous,
sun 90, phi 42, seed 0, driven by the ONNX driver in `lunar/Drive-v0`: the first 40 steps' observations (patch as float32 lists
rounded to 1e-6, scalars) with the driver's actions, plus the final telemetry (steps, elapsed s, path m, energy Wh, slip
mean, interventions). Keep it under 1.5 MB. Document the tolerances in the file (actions 1e-5 given stored obs; final
telemetry: FRONTEND reports the deviation of its closed-loop drive and LEAD decides, like the night-teleop drift in F-10).
(3) `tests/test_rover_driver.py`: the check vectors in `rover_bc_s0.check.json` reproduce with onnxruntime to 1e-5; the fixture
reproduces (skip both cleanly when onnxruntime is absent). (4) THEN the full suite, single process:
`.venv\Scripts\python -m pytest -q -x -p no:cacheprovider` — report the exact counts, time and any failure verbatim.
Files: data/driving/driving-v1-learned.json, tests/fixtures/rover_driver_parity.json, tests/test_rover_driver.py, lunarsim/rover/tables.py
only if the --driver path needs a fix.
Done when: the learned table, the fixture and the test exist; the full suite passes (or every failure is listed with its cause).
Due: 3 h after the commit lands (written 02:52)

## B-19 [REVIEW] (<= 2 h, single process) Released tables behind two paper numbers: cost per landed kilogram, and the memoryless-law outcomes
Goal: the referee review of the paper (paper/v3/REVIEW_round1.md, "Numbers") found two results quoted from reports rather than from
released files. (1) Cost per landed kilogram: write `experiments/phase3/cost_per_landed_kg.py` (you may add this one file in the
LEAD-owned folder) that runs the P2 and P3 baseline scenarios (the phases of `lunarsim/phases.py`) for the four mechanisms with
the fleets used in B-16 (P2 four vehicles; P3 as in B-16), 30 seeds, single process, and writes `results/table_cost_landed_kg.csv`
with, per (phase, fleet, mechanism): delivered_nonbulk_kg mean, cost mean, the exact ratio-of-means cost_per_landed_kg_usd and its
seed-bootstrap 95 % interval (N_BOOT as in fit_law.py), plus the v2-approximation column for the record. It must reproduce the
B-16 numbers ($5,525 [4,460, 7,281] P2 four-vehicle marketplace; $10,019 [8,067, 12,756] in-house; P3 $5,630 [4,883, 6,655] and
$7,199 [6,182, 8,612]); if a number differs, say why (seeds, fleet) rather than tuning. Runtime estimate first; if above 40 min,
report and wait. (2) The memoryless classical law's outcomes: `python -m lunarsim.lander.evaluate` (or the B-10d path) for
CLPS, 500 episodes from EVAL_SEED0, written as data/policies/outcomes_memoryless_CLPS.{csv,json} in the same format as
outcomes_classical_CLPS, so Table 7's 94.8 % row has a released file; add the row to results/table_E15.csv only if
run_phase3.py e15 picks it up automatically (do not hand-edit result files; if e15 needs a one-line registration of the
controller, make it and re-run `run_phase3.py e15`). The round-0 clone (87.2 %) and the reward-v1 PPO (43.6 %) rows have no saved
policy: say so in the report; LEAD will have the paper mark them as development runs.
Files: experiments/phase3/cost_per_landed_kg.py, results/table_cost_landed_kg.csv, data/policies/outcomes_memoryless_CLPS.*,
lunarsim/lander/evaluate.py or experiments/phase3/run_phase3.py (registration only), results/table_E15.csv (regenerated only).
Done when: both files exist with the numbers above reproduced (or the difference explained); report with clock times.
Due: Oct 16 06:00 (written 03:31)

## B-20 [REVIEW] (<= 1.5 h) Memory-bounded DAgger in lunarsim/rover/bc.py
Goal: two runs of `python -m lunarsim.rover.bc` were stopped for memory on this 8 GB machine: 60 legs reached a 4.5 GB working set;
20 legs (`--legs 20 --stride 8 --dagger 2 --epochs 10`) went from ~9,400 base samples to 119,900 after ONE DAgger round
(rollouts are recorded at every step while the base data uses the stride; 186,029 rollout interventions) and passed 2.7 GB in
round 2. Make the trainer bounded: (1) record DAgger rollouts with the same stride as the base data (`--stride`), and add
`--dagger-steps-cap N` (per-round cap on recorded rollout samples, reservoir-subsampled, default 20,000); (2) keep the
aggregated dataset in float16 on disk/in RAM and convert to float32 per mini-batch in the training loop (no whole-dataset
float32 tensor); (3) print the dataset size and the process RSS (psutil if present, else os-level) at the end of every round;
(4) stop a DAgger round early when the learned policy's rollout fails to reach the goal on more than 50 % of legs (record it,
keep the expert labels of what was collected). Base behaviour with `--dagger 0` must be unchanged (same samples, same model
given the same seed). A smoke test in tests/test_rover_bc.py (if it exists; else add one) with `--legs 2 --max-steps 200`.
Do NOT run a full training (memory; LEAD runs it). Report the expected working set for `--legs 20 --stride 8 --dagger 2`.
Files: lunarsim/rover/bc.py, tests/test_rover_bc.py (or the existing rover test file).
Done when: the smoke test passes single-process; the report gives the RSS printout from the smoke run and the estimate.
Due: Oct 16 07:00 (written 04:11)

---

# PHASE 4 (from 22 Oct 2026): read `.team/PLAN-phase4-design.md` first (your steps B-30…B-39; ownership in its §9)

## B-30 [DONE 08:05] (<= 3 h) Vehicle and site catalogue: one sourced file for the engine and the 3D models
Goal: a single catalogue every 3D model and every on-screen vehicle number comes from (plan §4 B-30).
Files (new): `lunarsim/catalog.py` (load + validate + `get(id)`), `lunarsim/catalog-v1.json` (package data; the source
of truth), `lunarsim/schemas/catalog-v1.schema.json`, `tests/test_catalog.py`.
Content: entries for landers `CLPS`, `MK1`, `LARGE`; rovers `LTV`, `HAUL`, `MICRO`; base elements `habitat`, `pad`
(with berm), `solar_tower`, `comms_mast`, `cargo_pallet`; scale references `apollo_lrv`, `nova_c`, `griffin`,
`viper`. Each entry: `id`, `kind` (lander | rover | base | reference), `reference_vehicle` (name + URL),
`representative` (true when the shape is not published), `dims` (height_m, diameter_m or length/width, leg_count,
leg_span_m, wheel_count, wheel_d_m, wheelbase_m, track_m, deck_height_m: only those that apply), `capacity_kg`,
`speed_kmh`, `night_ops`, `propellant` + `plume_class` (hydrolox | methalox | hypergolic | none), `materials`
(tags: mli_gold, mli_silver, white_paint, aluminium, solar_cell, radiator, regolith_dust) and for EVERY number
`{value, unit, flag: Spec | Measured | Assumed | Modelled, source: URL or reasoning}`.
Starting values and sources: `research_notes/LunarHaul 3D interactive design/design_research.md` §2.1–2.2 (Nova-C 3.9 m,
MK1 8.05 × 3.08 m, HLS 52 × 9 m, CLV-1/FLEX deployed ~4 × 2.3 × 2.6 m, VIPER 1.7 × 1.7 × 2.5 m with 0.5 m wheels,
LRV 3.1 m frame / 2.3 m wheelbase / 0.818 m wheels, HAUL = ATHLETE-like concept with `representative: true`).
Where the research says a value is unknown (MK1 and HLS legs), give an Assumed value with the reasoning.
Engine link WITHOUT changing results: do not rewire the engine. Instead `tests/test_catalog.py` asserts that
`capacity_kg`, `speed_kmh` and `night_ops` of LTV/HAUL/MICRO equal the `lunarsim.entities` VehicleClass values, and
that the lander gate masses and thrusts equal `lunarsim/lander/classes.py`, so the two can never drift.
Done when: the schema test, the equality tests and the fast suite pass; the baseline md5 is unchanged; the report
lists every value flagged Assumed and gives the catalogue path for FRONTEND (they copy it in `prepare-data.mjs`).

## B-34 [DONE 08:30] (<= 4 h, foreground chunks) Terrain assets v2: normals, horizon maps, levels of detail
Goal: 3D pages get terrain that lights correctly for ANY sun position instantly, plus the geometry the
Earth-visibility research (plan §10, R-1) needs. Today `site/src/world/scene.js` ray-marches sun visibility on the
GPU each time the sun moves; a precomputed horizon map replaces that and also answers "is Earth above the local
horizon here?".
Files (new): `tools/terrain_assets.py`, `tests/test_terrain_assets.py`. Output folder (LEAD commits):
`data/terrain/connecting_ridge/v2/`.
From `data/terrain/connecting_ridge/height_5m.png` (+ `meta.json` for scale and offset):
1. `normal_20m.png` (RGB8, up = +z) and 5 m normal maps only for two 2 × 2 km patches centred on BASE and PAD_A
   (coordinates in `sites.json`).
2. Horizon map: horizon elevation angle (degrees, 0.05° steps, uint16) for 64 azimuth sectors at 20 m posts,
   ray-marched over the tile. State clearly that terrain outside the 16 km tile is NOT included (R-1 extends it).
   Pack it the way a three.js texture upload handles best (e.g. 16 RGBA16 PNGs, or one binary file + JSON index)
   and say why. Validate against the existing sun-visibility shader logic for 4 sun azimuths (report agreement;
   target > 99 % of posts).
3. LODs: the existing 20 m grid + the 5 m patches above; `manifest.json` with every file's shape, encoding, size and
   sha256.
Budget: ≤ 30 MB on disk. Memory: process in row blocks, report peak RSS; each run under `timeout 540`.
Tests: synthetic DEMs with analytic answers (flat plane → horizon 0°; a cone → known horizon angle at a known
distance; a plane slope → known normals).
Done when: tests pass; the 4-azimuth agreement numbers are in the report; files listed with sizes.

## B-40 [IN PROGRESS] (after B-34; <= 5 h, foreground chunks) R-1 data: Earth-link windows at our sites and along our routes
Goal: the data behind research thread R-1 "Earth in sight" (plan §10). Read first:
`research_notes/Lunar communications and visibility/earth_visibility_prior_art.md`, sections "Site facts",
Q4 and "Minimal data pipeline". The prior-art verdict: site visibility percentages are published; the coupling to
fleet logistics is not. Our sites ISRU and SCI_1 never see Earth on the PDS 60 m map; BASE 0.50.
Files (new): `tools/comms/` (pipeline scripts), `lunarsim/comms.py` (reader + link queries only in this task),
`tests/test_comms_data.py`. Output (LEAD commits): `data/comms/connecting_ridge/earth_link-v1.json` (< 1 MB) with
sha256 and provenance. Kernels and DEM downloads go to an ignored cache folder (`.cache/comms/`), not the repo.
`spiceypy` 8.3 is installed in .venv (pyproject extra `[comms]`); rasterio is there for windowed COG reads.
1. Ephemeris: SPICE (`de440s.bsp`, `moon_pa_de440_200625.bpc`, `moon_de440_250416.tf`, `pck00011.tpc`,
   `naif0012.tls` from NAIF generic_kernels) and `spiceypy.azlcpo` in MOON_ME: Earth's topocentric azimuth,
   elevation and apparent radius, every 10 min, 2028-01-01 to 2031-12-31, for the 9 sites, both pad sets used by
   the engine (standoffs in `sites.json`) and route samples every 100 m along each leg's expert route (run the
   existing A* planner in `lunarsim/rover` per leg; no driving simulation). Cross-check one month at BASE against the
   JPL Horizons API with the exact parameters in the note (report the max difference).
2. Horizon masks only in Earth's wedge (grid bearing ±12° around the mean Earth direction, 0.1° steps): near field
   ≤ 8 km from the cached 5 m DEM, 8–300 km from windowed reads of PGDA `LDEM_80S_80MPP_ADJ.TIF`, spherical
   curvature R = 1,737.4 km, antenna height 2.5 m (rover), 10 m (mast at BASE).
3. Link state per point and time under three criteria (`any_part`, `centre+0.5deg`, `centre+2deg`): run-length
   windows per point; per leg, linked only when every sample is linked. A 10 m BASE mast option: a point is linked
   if it has line of sight to the mast top within 10 km and the mast sees Earth.
Checks (in the report): BASE any-part fraction vs the PDS AVGVISIB map value 0.50 (±0.05; explain any epoch or
criterion difference); typical window lengths ~13–14 d; ISRU and SCI_1 ≈ 0; the Horizons cross-check.
Memory: chunk by point groups; report peak RSS; every run under `timeout 540`.
Done when: tests pass (synthetic: flat sphere, Earth at fixed elevation → analytic windows; a wall → blocked
wedge); the JSON validates; the report tables per site and per leg (link fraction, mean and max gap) under each
criterion.

## B-41 [OPEN] (after B-40; <= 5 h) R-1 engine: opt-in `comms` scenario field (results byte-identical when off)
Goal: the engine can run with Earth-link windows (design: the note's "Experiment design in our engine").
Scenario field `comms` (default None): `mode` always | dte | dte+relay; `relay` {coverage 0–1, gap_model
"parametric", mean_gap_h}; `mast` {site, height_m, range_km} or None; `link_series` (path to earth_link-v1.json);
`criterion`. Rules: teleop may start a leg or a load/unload only when the leg is linked; if the link drops mid-leg
the rover parks and resumes at the next link-up (log the wait); supervised has two policies, `strict` (no driving
without a link) and `strategic` (drives planned legs without a link, but each intervention, drawn from the
driving tables' interventions/km, waits for the link); operator demand counts only while linked (log peak
concurrent demand per hour); autonomous unaffected. New metrics: `blackout_wait_vehicle_h` (by autonomy level),
`blackout_jobs_delayed`, `operator_peak_demand`, `linked_share_by_leg`. Same rule in the trace (v2 events) so the
3D world can show "waiting for Earth".
Done when: `comms=None` and `comms.mode=always` both reproduce the baseline md5 (use the new constant
739e9ba7…); unit tests for each rule on a tiny scenario with a hand-made link series; one smoke run of P2 with
`mode=dte` for 2 seeds reported (delays and the new metrics), single process. Do NOT run the suite (LEAD runs E21).

## B-42 [OPEN] (after B-41, before B-33; <= 3 h) R-1 suite runner E21 "Earth in sight" (LEAD runs the suite)
Goal: the experiment that tests H1–H6 of the R-1 note (plan §10). File (new): `experiments/phase4/run_phase4.py`
following `experiments/phase3/run_phase3.py` conventions (cells × seeds with common random numbers, resumable raw
CSV keyed by `cell` and `seed`, summary table, `--seeds`, `--workers` default 1, plus `--cells a-b` so LEAD can run
foreground chunks), and `tests/test_phase4_runner.py` (smoke: 2 cells × 2 seeds).
Calendar: each replication is one simulated year starting on 1 Jan of 2028 + (seed mod 4), so the link series'
~347-day ripple (H6) is sampled; the start year is a column.
Stage A (`e21a`): comms {always, dte, dte+relay p = 0.5, 0.8, 0.9, 1.0} × autonomy mix {all teleop (4 s), the
phase's default mix, all supervised-strict, all supervised-strategic, all autonomous} × 20 seeds; P2, the 6-vehicle
default fleet, marketplace, pads at 1 km, terrain legs and driving tables on (as in E19), criterion `any_part`.
Stage B (`e21b`, reads the Stage A table): at the knee of the coverage → throughput curve, extra rovers +0…3 ×
base mast {none, 10 m} × the two supervised policies; the break-even table: relay coverage ≡ one autonomy step ≡ N
extra rovers ≡ mast, also as a break-even relay price per year using the fleet capital costs already in the engine.
Stage C (`e21c`): pads {0.5, 1, 3 km} × criterion {any_part, centre+0.5deg, centre+2deg} at three Stage A cells.
Columns: everything the engine reports, plus the B-41 metrics (`blackout_wait_vehicle_h` by autonomy level,
`blackout_jobs_delayed`, `operator_peak_demand`, `linked_share_by_leg` summarised), `start_year`, the factor
columns. Summary `results/table_E21.csv`: mean and 95 % CI per cell for delivered t/yr, urgent p90 delay, $/kg,
blackout wait, operator peak.
Done when: the smoke test passes single-process; the report gives the expected runtime per seed for P2 with comms
on (measured on 2 seeds) and the total for Stage A, and the peak RSS.

## B-33 [OPEN] (after B-41; <= 3 h) Descent trajectories for the 3D landing lab
Goal: F-34 replays real descents at true scale (plan §4 B-33). Files: new `lunarsim/lander/trajectories.py` (or an
`--export-trajectories` mode in `evaluate.py`), `tests/test_lander_trajectories.py`. Output (LEAD commits):
`data/policies/trajectories-v1.json` (+ schema), budget ≤ 3 MB.
For each class (CLPS, MK1, LARGE) × pilot (classical law, memoryless law, and for CLPS also `lander_CLPS_bc_v3_s0`,
`lander_CLPS_baseline_s0` (PPO) and the hover-bonus v1 policy as the reward-hacking demo), pick episodes from the
existing 500-episode Monte Carlo seeds: the median miss, p10 and p90 miss, and the first failure if any (say which
seed and why). Record at 10 Hz: t, position (m, pad frame), velocity, attitude quaternion, throttle (0–1),
thrust direction, propellant left, altitude, the reward terms per step (so the lab's SCORE counter can tick from
real data), and the outcome block; plus per class the plume-surface numbers the keep-out model uses (onset
altitude for dust if the model has one; otherwise state that F-33 uses the research note's ~15 m CLPS onset).
Parity: replaying one exported episode through the JS env (`site/src/lander/env.js`) or the Python env from the
same seed reproduces positions to < 1e-6 m (test in Python; FRONTEND checks the JS side).
Done when: the file validates, parity passes, the report lists the chosen seeds per class × pilot with their miss
and outcome.
