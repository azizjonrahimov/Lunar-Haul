# FRONTEND inbox

Read `.team/PLAN.md` first (ownership in §4, site contract in §5.7). Do not run git add/commit. Report in
`.team/reports.md` when done, with the real clock time.

## Done: F-1…F-4 (v2.1) · F-5 site skeleton + hero (5e7f117) · F-6 3D world viewer (15c8f86)
## Decision (PLAN §2): the browser engine (web/sim.js) stays at v2; the world viewer reads Python v2 traces and
## browser v1 traces. F-10 does not port the Phase-3 engine features.

# ── Phase 3 (PLAN.md §1, §2, §5.7) ──────────────────────────────────────────────────────────────────────
Ownership: site/** and web/** (engine in web/sim.js frozen except exportTrace()/worker block).

## F-7 [DONE] Lander lab
Goal: `/lab/lander`: port `lunarsim/lander/physics.py` to `site/src/lander/physics.js` line by line (actions are
throttle + two tilt-rate commands; 15 observations scaled by `obs_scale(cls)`: see `lunarsim/lander/env.py`,
`classes.py`); load a policy JSON through `site/src/policy.js` (MLP forward pass; must match `<id>.check.json` to
1e-6 and show the check result on the page); run episodes in the browser with the trained policy: side view of the
descent over the terrain, live telemetry (T+, altitude, vertical and horizontal speed, throttle, propellant, miss
distance) and a large score counter in the spirit of the reference reel (red while negative, green once the SPLICE
box is met); a "reward rules" panel with sliders for the shaping terms that re-scores the last episode; a "hover
hack" button loading the hover_bonus policy (LEAD trains it; until then disable the button with a note); a Monte
Carlo panel plotting miss-distance scatter and the touchdown-box pass rate from `outcomes_<id>.json` (Observable
Plot, CI bands, CSV download). Lander classes selectable; every constant shown with its flag and source.
Policy files in `data/policies/`: `lander_CLPS_baseline_s0.json` + `.check.json` (the first trained policy; its
Monte Carlo pass rate is about 60 %, the classical law's 94 %: show both honestly, side by side), and the outcome
tables `outcomes_classical_{CLPS,MK1,LARGE}.json` and `outcomes_lander_CLPS_baseline_s0.json` (LEAD commits them as
they finish). Better policies will replace the file under the same id scheme; read the card's `training` record for
the numbers you display.
Files: site/src/lander/**, site/src/policy.js, site/lab/lander/index.html
Done when: a deterministic JS episode equals Python's trajectory for the same seed within 1e-6 (ask BACKEND for a
fixture in reports.md: initial state + action sequence + states); 60 fps; numbers traceable.
Due: Oct 16 12:00

## Queued
- F-8 Rover lab: port `lunarsim/rover/physics.py`, run the ONNX driver with onnxruntime-web (after B-13), a
  teleop-latency slider, autonomy % and interventions/km, lighting toggle, drive-it-yourself mode with latency.
- F-9 Accounts, saved runs, replicate badge, leaderboard against service v2 (PLAN §5.6); nothing gated for viewers.
- F-10 Verification page (Python-vs-JS checks for policy, physics, driving tables), the three simulator fixes
  (negative rect width, favicon, tooltip name), polish, performance tiers, Pages deploy of `site/dist`.

## Notes from LEAD for F-7 / F-8 (visual language of the two reference reels, seen today)
- Reel 1 (rocket): a cinematic 3D scene with ONE big live number (SCORE, red while negative, green once positive),
  cut with hand-drawn "whiteboard" explainers: a film strip of attempts (#1, #500, #3,000) with reward arrows, and a
  score-vs-attempt curve. For F-7: the score counter, and a sketch-style strip of episodes next to the learning curve.
- Reel 2 (driving): the camera frame shown as a GRID OF NUMBERS ("a picture is numbers"), a strip of frames feeding a
  DATASET box, a small network diagram over the road, "ONE NUMBER −15°" on a steering wheel, then the guess drawn on
  the road as the car "steers by itself". For F-8: show the 32×32 heightmap patch as a number grid that updates as the
  rover drives, the network's two outputs on a wheel + throttle dial, and the predicted path drawn on the terrain.
- Keep the research tone: these are explanatory devices, drawn in the site's own palette and type, not cartoon assets.
- New bundled sample: `data/sample_traces/P2_marketplace_seed3_v2.json` (full year, all Phase-3 features on); please
  add it to the World page's sample list and replace the test fixture option.

## F-8 [DONE] Rover lab (expert driver now; learned driver when B-13 lands)
Goal: `/lab/rover`: port `lunarsim/rover/physics.py` (bicycle model, autonomy speed caps, Hu slip table, energy model,
lighting penalties, teleop command delay + stop-to-confirm cadence) and `lunarsim/rover/expert.py` (A* on the 20 m
slope/lighting cost grid + pure pursuit at 5 m) to `site/src/rover/`, line by line, using `site/src/terrain.js` for
heights, slopes and shadows (the rover env's observation is the body-aligned 32×32 patch of relative height, slope and
roughness plus the scalars: see `lunarsim/rover/env.py`). Page: pick a leg (any ordered pair of the nine sites, pads
from the standoff selector), autonomy level (teleop at 0/4/6/8 s RTT, supervised, autonomous), lighting (sun azimuth
0/90/180/270 or night); "Drive" runs the leg in the browser and plays it on the terrain (plan view + a 3D or profile
view, your call) with live telemetry: speed made good, slip, grade, energy used, interventions, elapsed time, and
the reel-style explainer: the 32×32 patch shown as a grid of numbers updating as the rover moves, the controller's two
outputs (steer rate, throttle) on a wheel + throttle dial, the planned path drawn ahead. Compare against the table:
load `data/driving/driving-v1.json` and show the table's mean/p90 for the same leg/level/lighting beside the live
result (they come from the same physics; the live run uses one seed). A "drive it yourself" mode: arrow keys with the
chosen RTT delaying your commands (teaching what latency does), autonomy % computed with intervention cost = RTT +
recovery. Hook for B-13: a controller interface `{act(obs) -> [steer, throttle]}`; the expert implements it now; the
ONNX driver (onnxruntime-web, lazy-loaded only when chosen) plugs in later. Every constant with flag and source.
Files: site/src/rover/**, site/lab/rover/index.html, site/scripts/prepare-data.mjs (stage driving-v1.json or a slice)
Done when: a flat-leg teleop drive reproduces 3.24/2.56/2.03/1.76 km/h at 0/4/6/8 s within 2 %; BASE→PSR energy is
within 5 % of the table mean for the same seed convention (or you explain the difference); no console errors;
Lighthouse 100/100 kept.
Due: Oct 16 18:00

## F-7b [DONE] (small, do before or alongside F-8) Lander lab: env reward v2 and the new parity fixture
B-10b changed `lunarsim/lander/env.py` to reward v2 (ENV_VERSION 2): kappa 50, crash penalty −5 per m/s outside the
box, and the velocity-tracking term multiplied by `near = 1 + 3·max(0, 1 − z/30)`. Observations and dynamics are
unchanged. Update `site/src/lander/env.js` rewards and the reward-rule sliders/presets to v2, show the env version on
the page, and re-run parity against `tests/fixtures/lander_parity.json` (629 kB: physics steps incl. propellant
run-out, target_velocity samples, deterministic episodes per class). Also: `<id>.check.json` now stores the float64
numpy-runtime actions as `act` (match to 1e-6) and SB3's float32 actions as `sb3_act` (tolerance 1e-4); adjust
`checkPolicy`. Report the parity numbers.
Due: Oct 16 11:00

## F-10 [DONE] Verification page, simulator fixes, polish, deploy readiness
Goal: `/verification`: (1) the existing checks moved in: the 13 engine checks and the Python-vs-browser cross-check
(reuse the simulator's worker code; embed or link the simulator's Verification tab if embedding is heavy); (2) new
Phase-3 checks run in the page: policy check vectors for every published policy (`<id>.check.json`, float64 `act`
to 1e-6), lander parity against `tests/fixtures/lander_parity.json` (physics steps, target_velocity, deterministic
episodes per class), rover parity (flat-leg speeds vs the JSC values; BASE->PSR autonomous integrator vs table;
the known night-teleop trig drift listed as a documented difference with its magnitude), terrain decoding vs
meta.json stats (z range), shadow grid checksum; each check shows reference, computed, tolerance, pass/fail, and
the page shows a summary badge "N of M checks pass" like the simulator does; (3) the three simulator fixes from F-5
(negative rect width, favicon, tooltip accessible name); (4) polish: consistent headers across pages, the footer
credit line everywhere, phone-width check on every page, theme-switch test, `prefers-reduced-motion` behaviour
described on the About page; (5) deploy readiness: `npm run build` with `SITE_BASE=/lunar-logistics-research/`
produces working absolute links on every page (test with `npx vite preview --base`), the 404 page, and a short
`site/README.md` (dev, build, data staging, where each page's data comes from).
Files: site/**, web/** (the three fixes only)
Done when: /verification lists every check with its numbers and passes; Lighthouse 100/100 accessibility and best
practices on all pages; the prefixed build serves correctly.
Due: Oct 16 14:00 (after F-7b)

## Decision 14:42 (LEAD): the project is renamed LunarHaul
"LunarSim" collides with PUTvision's 2023 rover simulator, Element Robotics' commercial product and a 1999 Dundee
lander-vision simulator (verification_round_1.md, "Name candidates"). New project name: LunarHaul ("LunarHaul: a
verified testbed for lunar surface logistics"). Rules: (1) site titles, headers, footer, page copy and the paper use
LunarHaul from now on; "formerly LunarSim" once on the About page and in the paper's footnote. (2) Code identifiers,
the Python package `lunarsim`, file formats (`lunarsim-trace` etc.), CLI and URLs stay unchanged until a single rename
task at the release milestone (LEAD, all sessions idle). (3) Do not touch pyproject/package names yourselves.

## F-11 [DONE] (after F-10 is committed) Apply the LunarHaul name to the site and the simulator page
Exactly as you proposed: titles, meta descriptions, header brand ("LunarHaul · lunar surface logistics"), footer,
landing copy, h1/intro text, site/README.md, "formerly LunarSim" once on About; the simulator page title too
("LunarHaul simulator" or similar; web/index.html, title and header text only). Unchanged: identifiers, formats,
localStorage keys, URLs, paths. Also on About: drop "or focus" (flags stay mouse/screen-reader only).
Then F-9 (accounts UI) against the service that now exists: `service/README.md` has the API table and the local
run commands (`python -m service --port 8800` + `python -m service worker`); CSRF header `X-Requested-With:
lunarsim`; bearer mode for the github.io origin (`mode=bearer` login → `#login_code` → `POST /v2/auth/token`).
Due: F-11 Oct 16 10:00; F-9 Oct 16 18:00

## F-12 [DONE] (small) Browser engine: landing draw order independent of key order
B-12b made Python draw landings in LANDER_TYPES order (CLPS, MK1, LARGE) regardless of the scenario's key order.
`web/sim.js scheduleDemand` iterates `sc.landings` in insertion order. Make it iterate the fixed order
['CLPS','MK1','LARGE'] (skipping absent types), which leaves the page's own PHASES results unchanged (check: the
Verification page's 24-cell cross-check and the engine checks must still pass) and makes imported files with
reordered keys match Python. This is an exception to the frozen-engine rule, specified by LEAD.
Files: web/sim.js (that loop only), site/verify refs if needed
Due: Oct 16 10:00

## F-13 [DONE] Rover lab follows the new slip model (B-11b, committed)
`lunarsim/rover/physics.py` now has `SLIP_CURVES` (three digitised Hu et al. 2024 curves by soil friction angle
phi 37.8 / 42.0 / 47.8 deg, 0-30 deg in 5 deg steps), `slip(grade, phi)` linear in slope and phi (clipped), the flat
reference `FLAT_SLIP_REF` = slip(0, 42) = 0.04 used by the speed caps and the energy calibration (rolling coefficient
now 0.178), dig-in counted once per contiguous stretch, and phi drawn per episode in `env.py` (`options["phi"]` fixes
it; tables draw per run). Port these to `site/src/rover/physics.js` / `env.js`, add a soil selector to the rover lab
(phi 37.8 / 42 / 47.8 / sampled) with the flag Modelled and the source, re-run your parity checks (flat-leg speeds
must be unchanged; BASE->PSR autonomous energy per phi against Python), and update the Verification page's rover
rows once LEAD commits the regenerated `site/verify/refs.json` and `data/driving/driving-v1.json` (coming within the
hour). Files: site/src/rover/**, site/lab/rover/index.html, site/src/verify/** (rover rows).
Due: Oct 16 12:00

## F-14 [DONE] Results page and the simulator footer
Goal: `/results`: a page that renders the Phase-3 figures from `figures/fig20_*.png` … `fig27_*.png` with the
captions in `figures/phase3_captions.json` (status produced/skipped/stale shown as a small note; skipped figures
show their reason), the E15 and E16 summary tables from `results/table_E15.csv` and `table_E16.csv` (rendered at
build time; flags and n stated), and links to the raw CSVs. Also the v2 figures (`figures/fig01…fig19`) in a
collapsed "Version 2 results" section with their existing captions from the v2 paper if easy to obtain, else
titles only. prepare-data.mjs stages the PNGs; PDFs link to the repository. Add "Results" to the nav after
"World". Also rename the simulator footer line in web/index.html to "LunarHaul (engine: lunarsim) · Roatify
Research · MIT licence · …". The figures on disk are preliminary and will be regenerated by LEAD after the final
runs (same file names); the page must not hard-code numbers.
Files: site/results/index.html (new), site/src/results/** (new), site/scripts/prepare-data.mjs, site/lib/pages.mjs
(nav), web/index.html (footer only)
Done when: the page builds with whatever figures exist; Lighthouse 100/100; prefixed build works.
Due: Oct 16 14:00

## F-15 [DONE] Pipeline diagram for the Method page and the paper
Goal: one inline SVG (hand-authored, responsive, both themes, no text as paths) showing how the three models feed the
logistics engine: PGDA LOLA tile → terrain pack → (a) lander env → classical law / imitation + DAgger / PPO →
outcome tables; (b) rover env → expert / learned driver → driving tables; (c) plume module (R, T swept) → engine
(dispatch rules) → metrics → experiments E15-E20 → law; with the "Python ⇄ browser, one physics" cross-check marked.
Place it on /method (after the first section) with a caption and a text equivalent (an ordered list) for screen
readers; also export it as `figures/v3_fig02_pipeline.svg` + a 200-dpi PNG via a small script in site/scripts/ (the
paper's Figure 2 placeholder expects that path; see paper/v3/NOTES.md "Figures"). Style: the site's type and Tol
palette, hairline arrows, no icons from stock sets.
Files: site/src/components/pipeline.svg (or inline in content rendering), site/content/method.md hook, site/scripts/,
figures/v3_fig02_pipeline.{svg,png}
Due: Oct 16 16:00

## Note for the lander lab (apply with F-16 or now if idle): policy ids after today's retraining
- Best learned lander: `lander_CLPS_bcml_s0` (imitation + DAgger from the memoryless classical law; 81.2 %): make it the
  default "trained policy"; show `lander_CLPS_bc_s0` (58.2 %) and `lander_CLPS_baseline_s0` (PPO, reward v2, 63.2 %) as
  the comparison. The hover-hack button should load `lander_CLPS_hover_bonus_v1_s0` (reward v1: hovers, 5 % landings,
  positive score), with the v2 `lander_CLPS_hover_bonus_s0` (51 %) available in the list. Cards carry env_version.

## F-16a [DONE] (small) Lander lab policy defaults per the note above (bcml default; hover demo = hover_bonus_v1).
Files: site/src/lander/lab.js. Due: Oct 16 10:00.

## LEAD 18:20: MEMORY. 0.3 GB free of 7.9 GB. The final E17/E18 suites (3 workers) have priority until they finish
(LEAD will say when). Until then: run only single test files, no full `pytest tests`, no training or smoke runs > 1
minute, and prefer reading/writing code to running it. LEAD stopped the rover-driver training to make room.

## F-16 [DONE] Lander lab and verification: observation v3 (B-10e, committed)
Port `alt_history_step` and the obs v3 construction to `site/src/lander/env.js` (`obsVersion` 2|3; names, scales 30/2/30/30,
offsets 0, taken before the new reading shifts the history; "held" = dropout hold below 30 m with the sensor on; no
new random draws), infer the version from a card's `obs.names`, and run v3 policies when LEAD commits
`lander_CLPS_bc_v3_s0.json` (after the suites). Verification page: add the `alt_history` and `episodes_v3` fixture
checks (tests/fixtures/lander_parity.json, env_version 3). Keep v2 cards working. Report parity numbers.
Files: site/src/lander/{env,lab}.js, site/src/policy.js, site/src/verify/checks.worker.js
Due: Oct 16 12:00

## F-18 [DONE] Landing page and Method/Paper copy with the results
Rewrite the landing page's three sections and headline numbers around the Phase-3 findings (numbers from
`.team/reports.md` entries "first final-data findings", "findings from E16 and E19", "learned-lander ladder", "fit and
siting on the near-complete data"; the E18/E20 values may shift in the last decimal after the final fit, so read them
from `results/table_E20.csv` / `E20_fit.json` at build time where you can and label them Modelled with n). Headline
trio proposal: urgent delay +40 % per km of pad standoff [37, 43]; a keep-out radius costs +12 %/km and a stand-down
+2.3 %/h; the best learned lander lands 89.0 % vs the classical law's 93.8 %. "What is new" states the three
contributions as results, not aims; "Try it" points to World, the labs, Results and Verification. Update
`site/content/paper.md` to say the v3 draft exists (title "Where the Lander Lands…", in preparation, figures on
/results) and `site/content/method.md` where it still speaks in the future tense. Keep the voice plain.
Files: site/index.html (copy), site/lib/pages.mjs (headline sources), site/content/{paper,method}.md
Due: Oct 16 12:00

## F-19 [REVIEW] (<= 1 h) Site rebuild on the final results; headline and results-page numbers checked against the tables
Goal: the final Phase-3 results are committed (77b53cc: `results/table_E15.csv` … `table_E20*.csv`, `E20_fit.json`,
figures fig20-fig27 and `figures/phase3_captions.json`, all rebuilt at 02:36 on the complete E18). Rebuild the site
(`npm run build` with `SITE_BASE=/lunar-logistics-research/`) and check, page by page, that every number read at build
time (F-18) matches the tables: landing-page headline figures, Method, Paper (`standoff_pct` etc.), Results (every table,
caption and figure file), and the verification page still at its full pass count. Expected values from `table_E20.csv`
(pooled, log delay): standoff +39.7 % per km [36.6, 43.4]; keep-out +12.1 % [10.4, 13.8]; stand-down +2.3 % per h
[1.8, 2.8]; log miss +1.6 % [-0.4, +3.9]; mechanisms -46.6 / -46.1 / -53.2 % vs in-house. If a number is formatted
from a different column or rounded inconsistently with the paper (one decimal for percentages, integers for hours
over 10), fix the formatter, not the copy. No console errors; Lighthouse 100/100 kept; `vite preview --base` links work.
Files: site/** (no changes to web/**)
Done when: the rebuilt site shows the final numbers everywhere, with the list of pages and values checked in the report.
Due: Oct 16 04:30 (written 02:44)

## F-17 [DONE] Learned rover driver in the rover lab
Goal: a "Learned driver (rover_bc_s0)" option in the rover lab's controller selector, next to the scripted expert, through the
existing `{name, act(obs, env)}` interface (`site/src/rover/lab.js` "B-13 hook"). The driver is the ONNX export of B-13:
`data/policies/rover_bc_s0.onnx` + card `rover_bc_s0.json` (lunarsim-policy v1, kind "cnn": inputs "patch" [N,3,32,32] float32
and "scalars" [N,5] float32, output "action" [N,2] in [-1, 1]; the card carries the input spec, the normalisation, the
training record, the onnx sha256) + `rover_bc_s0.check.json` (onnxruntime outputs for stored inputs; match to 1e-5, show the
check on the page and on /verification like the lander policies). Runtime: onnxruntime-web (WASM, from the npm package
`onnxruntime-web`, pinned; lazy-loaded only when the learned driver is chosen; never on page load; keep Lighthouse 100).
The observation the env.js already builds (body-aligned 32x32 patch of relative height / slope / roughness + the five scalars,
`lunarsim/rover/env.py`) must be fed in exactly the Python order and normalisation of the card; verify on the check vectors
first, then on one leg: the browser drive of BASE->DEPOT (autonomous, sun 90) must reproduce the Python `lunarsim.rover.bc`
drive of the same leg and seed to the tolerance LEAD states with the commit (LEAD will add a fixture
`tests/fixtures/rover_driver_parity.json`: obs sequence + actions + final telemetry).
Page: the explainer (number grid, wheel + throttle dial, predicted path) now shows the NETWORK's outputs; beside the live
telemetry show the measured values from `data/driving/driving-v1-learned.json` (interventions/km and time ratio per leg and
lighting, produced by `lunarsim.rover.tables --driver`) against the expert's `driving-v1.json` for the same leg. A sentence on
the page says what the learned driver is (an imitation of the scripted expert from 20 legs with two DAgger rounds capped at 20,000 samples each) and that the
suites in the paper use the expert's tables, not this driver. Flags and sources on every constant.
Files: site/src/rover/**, site/lab/rover/index.html, site/verification/** (the two new checks), site/package.json (the dependency),
site/scripts/prepare-data.mjs (stage the .onnx, both cards and driving-v1-learned.json).
Done when: check vectors pass at 1e-5 in the page and on /verification; the BASE->DEPOT parity fixture passes; the learned
option loads in under 2 s on a warm cache and does nothing until chosen; no console errors; Lighthouse 100/100 on /lab/rover.
Due: 4 h after the commit lands.

## F-20 [DONE] (<= 1.5 h) Site copy for the re-fitted law; the v3 paper on the Paper page
Goal: the law was re-fitted with the utilisation covariate centred (commit 533589f; results/table_E20.csv now has a
`util_center` column, 0.0462 pooled). The main effects are now the effects at the typical fleet load, and they changed:
standoff +35.0 % per km [32.6, 37.6] (was 39.7); keep-out -0.5 % per km [-1.5, +0.8] and stand-down -0.8 % per hour
[-1.1, -0.3] (both were positive; now "no measurable cost at the simulated loads of 2-8 % utilisation, growing only at
lighter loads"); landing dispersion +8.2 % per e-fold of mean miss [6.2, 10.5] (was "no smooth effect"), acting only
through landings that miss the pad. The formatters read the same rows, so the numbers update on rebuild, but the COPY
around them is now wrong: (1) landing-page headline: keep the standoff item, add "at the typical fleet load; the relation
is concave: about 0.52 per km below 1 km, 0.10-0.19 per km beyond 2 km" to its context; replace the keep-out/stand-down
item by "A plume keep-out radius and a stand-down add no measurable delay at these loads" with the two values and
intervals in the context line and the sentence "the fleets, at 2-8 % utilisation, absorb the evacuations; a cost appears
only in the lightest-loaded night cells at 2-3 km radii"; add a third item for dispersion (+8.2 % per e-fold; "through
landings off the pad; a 100 m pad absorbs today's 50 m accuracy, a 25 m pad does not"). (2) "What is new", Method and
Paper copy: same corrections wherever the old numbers or the "no smooth effect" sentence appear (grep for "12.1",
"2.3 %", "smooth", "keep-out"). (3) Results page: the law table/figure (fig27) is rebuilt; the caption JSON is current.
(4) Paper page: when LEAD commits paper/v3/where_the_lander_lands_v3.pdf (this morning), link it as "Version 3 (draft,
October 2026, PDF)" with the page count, keep "A draft; not yet posted with a DOI", and update the Cite block to version
3.0.0 with the v3 title; until then leave the paper link part and do the rest.
Files: site/content/*.md, site/lib/pages.mjs (copy only), site/lab/** untouched.
Done when: no page shows +39.7, +12.1 or +2.3 as the law; the rebuilt site passes the F-19 checks; report the sentences
you changed. Due: Oct 16 06:00 (written 03:37)

## F-21 [DONE] Port the env's intervention resume (v2) to the rover lab
Goal: B-18 found that env version 1 re-intervened on every step when the planned route crossed a hazard cell (slope or roughness
above R.INTERVENTION limits), which produced thousands of interventions per drive; version 2 (`lunarsim/rover/env.py`, `_hazard()`
and the resume loop in the intervention handler, `HAZARD_CLEAR_M = 25.0`) resumes at the first route point past the hazard that is
clear of both limits and more than 25 m from the hazard cell's centre, adds the skipped route distance to `dist_m`, and counts ONE
intervention per hazard. Port that logic line by line to `site/src/rover/env.js`, show "env v2" where the lab shows the env version,
and re-run the rover parity rows on /verification/ (the BASE->DEPOT fixture has 0 interventions, so it must stay identical; add one
documented check on a leg with a hazard: PSR->PAD_A at 3 km, night, autonomous, expert: interventions count and distance vs Python,
values from BACKEND's B-18 report: PSR->PAD_A@3 night, expert autonomous: 1 intervention on cell (333, 368), rtt 4 s; and the flat-route unit case in tests/test_rover.py: one rough cell on a 1.2 km route = exactly 1 intervention, distance 1,200 m within 2 %). Also: the card's `evaluation` block is now credible (recomputed under env v2 by B-18): quote its four rows in the lab's "learned driver" section (reached, km driven vs route km, elapsed h, interventions per km, autonomy %) with the card's `evaluation_note` definitions, and the plain interpretation (finishes every drive, rarely needs an intervention, but 1.77x the distance and 3.5x the expert's time at the autonomous level). Then add the learned-vs-expert column from `data/driving/driving-v1-learned.json` when it exists.
Files: site/src/rover/env.js, site/src/rover/lab.js, site/src/verify/checks.worker.js, site/scripts/prepare-data.mjs.
Done when: the parity rows pass, the hazard-leg check matches Python's intervention count, no console errors, Lighthouse 100 kept.
Due: 2 h after the commit lands (written 09:55)

---

# PHASE 4 (from 22 Oct 2026): read `.team/PLAN-phase4-design.md` (your steps F-30…F-40; ownership in its §9) and `research_notes/LunarHaul 3D interactive design/design_research.md` first.

## F-30 [DONE 08:16, accepted] (<= 4 h) Design system v2: the "instrument" theme and the shared UI components
Goal: the look of every Phase 4 3D page (plan §3, §5 F-30). Reading pages keep today's light theme and dark toggle.
Owner decisions: dark "instrument" theme on 3D pages; keep Source Sans 3 for reading text; add **Sora** (display) and
**JetBrains Mono** (all numbers, tabular), both OFL, self-hosted unmodified from npm (Fontsource packages); check the
OFL text for a Reserved Font Name and report. You may A/B Sora against Space Grotesk on the demo page and say which
reads better at 12–14 px.
Files: `site/src/styles/tokens.css` (+ an instrument scope, e.g. `.instrument` on <body>), new `site/src/ui/*`, new
page `site/design/index.html` (+ the `vite.config.js` PAGES entry; `noindex`, not in the nav), `site/package.json`.
Tokens: near-black blue background; glass panels at ≥ 0.85 opacity wherever small text sits on them (research §3.3:
the reference's translucent panels fail AA over sunlit regolith); 1 px light border; radius 16–18 px; ink and muted
pass 4.5:1; "faint" only for ≥ 24 px text or decoration; cool cyan (data, guidance) and warm amber (thrust, heat)
accents; Tol bright for categories; focus ring ≥ 3:1; 24 px minimum targets.
Components (vanilla JS, no framework; keyboard support and ARIA on each): segmented pill control (radiogroup, arrow
keys), stat chip (label, value, unit, flag + source via the existing `components/num.js`), narrative card (title,
text, step dots, polite live region with final text only), callout label (a DOM API the 3D stage will position:
dot + leader + pill), scene-switcher chips, timeline (range + event ticks), loading door (real byte progress,
Enter button, skip link), big animated counter (sign colours, tabular digits, instant under
prefers-reduced-motion), glass panel, tooltip.
The /design/ page shows every component in the instrument and the reading theme, and a live contrast table (computed
from the CSS variables, pass/fail per pair) over three backgrounds: black, mid grey, sunlit-regolith grey.
Done when: every contrast pair in use passes AA; a keyboard-only walkthrough works; Lighthouse accessibility 100 on
/design/; no console errors; existing pages unchanged (spot-check /, /world/, both labs).

## F-31 [DONE, accepted] (<= 6 h) The shared 3D stage (`site/src/stage/`) and one demo scene with the full pipeline
Goal: plan §5 F-31. Every later 3D page builds on this; M1 is reviewed on the demo scene.
API sketch (adapt it, report the final one): `createStage({canvas, preset: 'exhibit' | 'onsite', tier, sun: {az, el}})`
→ `{scene, camera, renderer, director, labels, cutaway, explode, setTier, setToneMapping, renderOnce, dispose}`.
- Renderer: three r186 `WebGLRenderer` (decision: no WebGPU this phase), `stencil: true`, reversed depth buffer when
  supported (capability check), colour management on; tone mapping switchable Neutral / ACES / AgX for an A/B.
- Lighting presets: exhibit (RoomEnvironment PMREM, soft studio key) and onsite (black sky, one sun at az/el, el
  default 1.5°, dim lunar environment, Earth as a 1.9° disc placeholder near the horizon).
- Post-processing by tier (detect-gpu with the existing self-hosted benchmarks): tier 1 = render + output + FXAA or
  SMAA; tier 2 = + AO (try r186 GTAO and N8AO (npm, MIT); measure both) + bloom on emissive parts; tier 3 = all +
  SMAA. An adaptive pixel-ratio monitor holding a frame-time target; render-on-demand when nothing moves.
- Camera director on `camera-controls` (npm, MIT): named shots, smooth `setLookAt` moves, orbit limits, instant cuts
  under prefers-reduced-motion; one pause button stops all motion.
- Labels: F-30 callouts anchored to 3D points, hidden when occluded, simple overlap avoidance.
- Cutaway helper: clipping plane(s) with solid stencil caps (three example `webgl_clipping_stencil`), optional
  wedge; exploded-view helper (named parts, explode axes, 0–1 animation).
- Hover/pick outline (OutlinePass on tier ≥ 2, emissive tint fallback); WebGL context-loss recovery; `dispose()`.
- Demo page `site/design/stage/` (noindex): a procedural test object (a tank with a feed line and a bell nozzle,
  named parts) with Whole / Cutaway / Exploded, both presets, callouts, a tier switcher, the tone-mapping A/B and an
  on-screen frame-time readout (ms, p50 and p95 over 5 s).
Done when: the demo runs at tiers 1–3; the report gives measured frame times per tier on this RTX 3050 laptop at the
default view (target: tier 2 p95 ≤ 16.7 ms) and which AO you chose and why; reduced motion respected; no console
errors; /world/ and the labs unchanged. Stop the dev server and close heavy tabs when done.

# M2 (vehicles and effects): start after F-31 is reported. Read plan §5 F-32/F-33 and research §1.4, §1.7, §2.1–2.2.

## F-32 [DONE, accepted] (after F-31; <= 8 h, may report in two parts a/b) The procedural vehicle kit and the `/vehicles/` exhibit page
Goal: the first page in the reference reel's pattern, for our own fleet (plan §5 F-32). Everything at true scale from
`lunarsim/catalog-v1.json` (your copy in `site/public/catalog/`); no glTF downloads.
**F-32a the kit** (`site/src/stage/models/` or `site/src/models/`, your call): one generator per catalogue id —
`CLPS` (Nova-C-like: hexagonal body, 6 legs, top-deck solar panel, one bell), `MK1` (8.05 m × 3.08 m cylinder,
4 representative legs, BE-7 bell, side solar panels), `LARGE` (52 × 9 m HLS-like: no flaps, a solar band, an
airlock and an elevator from the deck to the ground, 6 representative legs, mid-body landing thrusters), `LTV`
(CLV-1/FLEX-like: 4 large wheels with chevron treads, deck, crab-steer pivots, solar panel, small robotic arm),
`HAUL` (the concept: low flat-bed, 6 wheels of 1.5 m, pallet interface, radiators, headlights, no solar mast),
`MICRO` (VIPER-scale, 4 wheels of 0.5 m with grousers, mast with lights), base elements `habitat`, `pad` (with berm),
`solar_tower`, `comms_mast`, `cargo_pallet` (instanced). Rules: real dimensions from `dims.*.value` (metres); named
parts with an explode axis each; closed meshes (caps work in Cutaway); materials from the catalogue's material map
(gold and silver MLI with a crinkle normal map generated in code, white paint, aluminium, dark solar cells,
regolith dust on the lower 30–50 cm); three levels of detail (full, simplified, today's constant-size icon for the
far view); triangle budget per vehicle at full detail ≤ 60k (report the counts); one `buildVehicle(id, {lod})`
entry point. Representative parts carry `userData.representative = true` so the page can say so.
**F-32b the page** `site/vehicles/index.html` (+ nav entry "Vehicles", `<body class="instrument">`): the Exhibit
lighting preset; scene chips Landers · Rovers · Base, then one chip per vehicle; View [Whole | Cutaway | Exploded];
Follow [Propellant | Power | Cargo] (animated flow along feed lines, cables or the load path); a narrative card per
vehicle × mode (plain words, numbers from the catalogue through `{{…}}`-style lookups, never typed in HTML); stat
chips (e.g. "Carries 1.5 t · 6 km/h · parks in the dark", each with its flag and source); callouts for 4–6 parts;
a component tree and a properties panel (OpenRocket-style, collapsible on phones); a scale reference toggle (an
astronaut silhouette 1.8 m and the Apollo LRV); the loading door; a DOM mirror (part list, current numbers) for
screen readers; the "representative model" label wherever `representative` is true.
Done when: every catalogue vehicle renders at its catalogue size (report: measured bounding boxes vs catalogue);
Cutaway shows solid caps; Exploded separates parts cleanly; tier 1 holds ≥ 30 fps and tier 2 p95 ≤ 16.7 ms on
this laptop at the default view (report numbers); keyboard and reduced motion work; Lighthouse accessibility
≥ 95 and performance ≥ 85 (desktop); no console errors; 390 px layout works.

## F-33 [DONE, accepted] (after F-32; <= 6 h) Lunar light and effects; /world/ terrain on the horizon map
Goal: plan §5 F-33 and the B-34 finding (the horizon map is more accurate than today's shader off-axis).
1. **/world/ terrain lighting from `data/terrain/connecting_ridge/v2/`** (copy via `prepare-data.mjs`): sample the
   16 RGBA16 horizon textures (manifest for encoding; frame note: normal (nx, ny, nz) → scene (nx, nz, −ny)) so the
   sun can sit at any azimuth instantly (no re-bake), with a soft edge for the 0.53° solar disc; use `normal_20m`
   and the 5 m patches near BASE and PAD_A. Keep the current shader as the fallback if textures fail to load.
2. **Engine glow and landing dust** (stage module `effects/`): a faint near-nozzle glow by `plume_class` (hydrolox
   almost none, methalox and hypergolic faint), no shock diamonds; a deterministic dust sheet (seeded particles on
   ballistic paths, g = 1.62 m/s², no drag, launched at 1–3°, starting below an onset height that scales with
   thrust, ~15 m for CLPS-class), an obscuration layer that peaks in the last seconds and vanishes at engine
   cut-off, and a scour decal left on the terrain. Particle budget by tier (≈ 2k / 10k / 30k).
3. **Long shadows and night**: a tight shadow camera on the focused vehicle (shadows ≈ 38× height at 1.5°), the
   terrain shader samples that shadow map; headlight cones for rovers at night; wheel dust behind moving rovers.
4. **Sky**: black; Earth as a 1.9° disc placed by a simple ephemeris for now (R-1 will supply the real series)
   and hidden when below the horizon map; stars off at sunlit exposure (an "exposure" toggle may show them).
Done when: a /design/stage/ "effects" scene shows each effect with the tier switch and frame times; /world/ uses
the horizon map (side-by-side screenshots old vs new at sun azimuth 30°, where the old shader is weakest);
determinism: the same seed gives the same dust frames; reduced motion pauses particles; no console errors.

# M3/M4 frontend (queued 22 Oct 12:35). Order: F-34, F-36, F-35, F-37. Data now committed: trajectories-v1 (B-33),
# routes-v1 (B-32), scene packages + earth_track (B-31), earth_link (B-40).

## F-34 [DONE, accepted] (after F-33; <= 6 h) Lander lab in 3D: "The last 500 metres"
Plan §5 F-34. Upgrade `/lab/lander/` to an instrument page on the shared stage (on-site preset), keeping the 2D side
view as tier 0 and as the accessible mirror. Replay `data/policies/trajectories-v1.json` episodes at true scale over
the terrain at PAD_A (5 m patch from B-34): the catalogue lander model, attitude from the quaternion, the F-33
engine glow and dust sheet (onset per the file), touchdown box drawn in 3D, the 500-landing scatter from the
outcomes tables on the pad. Controls: Pilot [Network | Classical | Memoryless | PPO | Hover hack] (only what exists
per class), Lander [Small | Medium | Large], View [Chase | Side | Pad camera], Show [Guidance | Thrust | Sensors]
(velocity-field arrows, thrust vector, altimeter beam with dropouts), phase chips Approach / Hover / Touchdown, the
big SCORE counter driven by the per-step reward terms (red/green with sign; the hover-hack episode shows the clock
running out), and a chalkboard card (KaTeX rendered at build time: thrust, gravity, the reward sum) for reward
shaping, linking to the existing reward-rules section. JS parity: replay one exported episode through
`site/src/lander/env.js` from its seed and compare positions with `pos_m` (< 1e-6 m; add as a `site/tests/*.mjs`
node test for B-38's CI hook). Done when: every pilot × class in the file plays; parity test passes; tiers;
reduced motion; Lighthouse ≥ 85 performance desktop; no console errors.

## F-36 [DONE, accepted] (after F-34; <= 8 h, may report in parts) World v2: the flagship (plan §5 F-36)
`/world/` on the shared stage, instrument theme, reading the B-31 scene packages (write the JS reader
`site/src/world/scene-data.js`; the five samples in `data/scenes/` and the run-queue path `runs/<id>/scene/`):
loading door → fly-in; scene chips Overview · Pads & keep-out · Rover legs · Base · Night; true-scale / icon toggle;
rovers on their routes (f-interpolation per the schema) with states shown (parked at night, stand-down,
"waiting for Earth" from the comms sample); landers descending along the nearest B-33 trajectory with glow, dust
and keep-out rings; pallets stacking at sites from the hourly waiting series; Earth at its real elevation from the
hourly series, hidden by the horizon map, with a "comms" chip (direct / relay only / none) when the sample has
comms; timeline with event ticks (landings, nightfall, strandings, Earth set/rise); stat chips (delivered, waiting,
trips, urgent 90 % wait so far); a narrative card for the current event; Follow [Cargo | Rovers | Landers | Night];
a split view comparing two samples on the same seed (e.g. P2 always vs P2 DTE-only). Keep the 2D plan view as
tier 0. Done when: all five samples play a full year; `?run=<id>` loads a run-queue scene; position checks against
the Python reader (`lunarsim.scene.position`) at 20 random times (node test); tiers, reduced motion, keyboard,
Lighthouse ≥ 85 desktop.

## F-36d [DONE, accepted] (next, before F-35; <= 3 h) World v2 polish: make the flagship read like the reels
LEAD's browser review of F-36 (22 Oct 14:40), P2 scene: the data, controls and chips work; the look is not there yet.
1. **Routes:** today every planned route (all lighting variants) is drawn bright cyan, so the network reads as
   spaghetti and hides the terrain. Draw each leg once as a thin, low-contrast line (night route), brighten only the
   legs in use now (and fade them back), and colour by state when Follow/Earth-link is on.
2. **Scene chips must move the camera and the story:** "Pads & keep-out" should frame the pads with their keep-out
   rings (and play to the next landing), "Rover legs" a busy leg at rover scale, "Base" the base cluster, "Night" a
   site in the dark with headlights; the narrative card rewrites itself per chip (today it stays on "0 driving").
3. **Show the rovers:** at overview distance the icons are hard to find; make them larger, brighter, with a short
   trail, and make "True scale" obviously true scale.
4. **First frame:** Enter should open on a lit, framed view with something happening (a landing or a convoy), not an
   idle moment; pick the start time from the package's events.
Check in the browser at 1440 and 390 px; frame times per tier; no console errors.

## F-35 [DONE, accepted] (after F-36; <= 5 h) Rover lab in 3D (plan §5 F-35)
`/lab/rover/` on the stage: drive the chosen leg on the terrain along the B-32 route for the chosen lighting, chase
and cockpit cameras, a "ghost" rover where your delayed command will take effect, the low-sun glare cone and long
shadows, slip indicator, interventions as 3D markers with callouts, expert vs neural-network race on the same leg,
Earth visibility along the route (from earth_link samples: where on the leg a teleoperated rover would lose the
link). 2D plan view stays as tier 0 and mirror.

## F-35d [DONE, accepted] (after F-37 if F-37 is under way, else before; <= 2 h) Rover lab 3D polish (LEAD browser review 22 Oct)
1. Open on a sunlit stretch of the leg (today the first frame is in terrain shadow); pick the start from the leg's
   lighting so the rover and ground are lit, then let the drive reach the shadow.
2. The flat cyan disc and yellow ring around the rover are too heavy: make the glare cone and command marker subtle
   (thin outline, low alpha), the ring only when it means something.
3. Earth-link posts must not spear the rover: shorter, offset to the route side, fading near the camera.
4. Close-up craters look stamped and repetitive: vary size, rotation and depth, lower the density near the camera.
5. Label the Earth-link posts as computed for the leg's night route (BACKEND adds per-lighting samples later).
Check at 1440 and 390 px; no console errors.

## F-37 [DONE, accepted] (after F-35; <= 5 h) Simulator v3 on the design system (plan §5 F-37)
The `/simulator/` page rebuilt on the site's design system (glass panels, segmented controls, the plain labels of
22 Oct kept word for word unless clearer), engine files `web/sim.js` and `web/worker.js` untouched; results as stat
chips and Observable Plot charts; Compare as four answer-style cards (one per job rule, the SpaceX-reel pattern);
"Watch this year in 3D" opens /world/ with the run; the v2 page stays reachable at `/simulator/v2/` for one release.

# M5 (stories, landing page, quality). Order: F-38, F-39, F-40. Queued 22 Oct 15:45.

## F-38 [REVIEW] (<= 5 h) Guided stories (explorable explanations), plan §5 F-38
Data: `data/stories/resolved/*.json` (+ `index.json`), format in `lunarsim/schemas/story-v1.schema.json` (B-35).
Published stories only (four: pads distance, sharing rovers, learned landing, Earth's horizon). New page `/stories/`
(list) and `/stories/<id>/` (one page per story, or one page with ?s=<id>): each step drives the matching 3D stage
(world scenes from the gallery, the lander lab's episodes, rover legs), switches modes, moves the camera to the named
shot (map the B-35 shot and mode names to your stage; tell LEAD if any name should change in the data), shows the
step's text with every number as a stat chip carrying its flag and source (the resolved file has value, text,
unit, flag, source per number), Next / Back and a step bar, keyboard, a text-only twin of every step (the `visual`
field), reduced motion = cuts. Nav: "Stories" after World. Lighthouse ≥ 85 performance desktop; no console errors.

## F-39 [REVIEW] (<= 2 h) Landing page hero, plan §5 F-39
The home page opens with the loading door and a slow cinematic orbit of the base under the low sun (on-site preset,
the gallery's P2 scene, landers and rovers moving), three big counters from the results (sourced: simulated years
in the law fit, cost per landed kg at the marketplace, and the Earth's-horizon headline from the published story's
numbers), and entry chips to World, Vehicles, Labs, Simulator and Stories. Keep LCP ≤ 2.5 s on mobile: the hero
3D starts after first paint and only on capable tiers; tier 0 shows a still image.

## F-40 [IN PROGRESS] (<= 4 h, then continuous) Quality pass, plan §5 F-40, plus the notes collected in reviews
- Measure tiers in a FOREGROUND window (frame interval at display rate) on every 3D page; record numbers.
- Lander lab: frame the Approach phase with the ground in view (no black first frame).
- Rover lab: the stretched brown streak pattern on the ground near the camera (chase view, first frame).
- World: verify the Earth-link scenes show "waiting for Earth" clearly; the urgent chip's live value.
- Simulator: "Full 3D replay on GitHub" button opening the run-queue issue form prefilled from the settings (URL
  query parameters keyed by the form's field ids); keep "trace replay of this run" for /world/trace/.
- /verification/: show the Phase 4 rows from `data/verification/verification-v1.json` → `phase4[]`.
- Light-theme Tol yellow/cyan/grey marks below 3:1 on white (from F-30): fix or add outlines.
- Stories: draw `highlight` (e.g. ISRU in the Earth story) and the route colour for no link; declutter vehicle labels
  in story views (show only the vehicles a step talks about); after B-53 use the data's `label` field.
- Keyboard, screen-reader mirror, reduced motion, contrast on every page; Lighthouse table for every page;
  a screenshot set (desktop + 390 px) committed under `site/design/shots/` is NOT wanted — keep them out of git.

## F-41 [IN PROGRESS] (<= 4 h) "Earth's sky, year by year": an explorable for R-1's 2028 finding (light reading page)
The finding (B-55, paper §5.4): one 100 m route point on the regolith haul ISRU->CONSTR sees Earth at no hour from
Jan 2028 to Jul 2029; strategic rovers stopped there wait, and in 2028 the fleet is captured (113 t vs ~530 t in
2029-31). The cause is where Earth stands when it is high: west of grid north in 2028, east of it in 2030.
New page `/research/earth-sky/` (chalkboard explainer style, light theme, Plot/SVG, no 3D needed):
1. **Earth's track in the sky from the base**, grid bearing (x) vs elevation (y), one curve per year 2028-2031
   (`data/comms/connecting_ridge/earth_track-v1.json.gz`: elevation_cdeg, grid_bearing_cdeg, hourly), a year
   picker and a month scrubber; overlay the terrain horizon at BASE and at the dark sample (B-58 exports them).
2. **The dark spot's calendar**: monthly link fraction 2028-2031 for the dark sample, BASE, ISRU, CONSTR and the
   ISRU->CONSTR leg (`results/E21_strategic_years.json` → stranding_2028_top_samples[0].monthly_linked_2028_2031,
   calendar.places_linked_fraction; `results/E21_strategic_years_monthly.csv`).
3. **The fleet captured**: stranded fleet share by month, 2028 against 2030 (stranding.<year>.stranded_fleet_share_by_month),
   and tonnage by start year (e21_by_start_year).
Every number a stat chip with flag and source (Modelled; SPICE + LOLA), text twin for each chart, keyboard, 390 px.
Link it from the Earth story's step 7 (a "Why 2028?" link; tell LEAD the URL so the story data can carry it) and
from /research/ or Results. NOTE: the strategic policy's results are being re-examined (B-57); show the geometry
and the stranding as measured, and do not add claims about which policy is best. Budget entry for the page.

## F-41 part 2 [REVIEW] (<= 1.5 h) B-58's skylines and the haul road on /research/earth-sky/; the rule's result (queued 22 Oct 21:55)
- **Data:** stage `data/comms/connecting_ridge/horizons_dark_sample.json` (keys in BACKEND's B-58 report) and the
  `bounded` block of `results/E21_fit_r2.json` (only what the page shows) in prepare-data; budget data entry.
- **Figure 1:** draw the skylines at BASE and at the dark spot over Earth's path (same grid-bearing convention).
  Earth is in view at the dark spot when its path rises above that skyline (5.9-8.6° against a ~6.2° peak); make
  that the caption and keep or drop the dashed patch as you judge clearer. Table twin: skyline at the highest point's
  bearing, per year.
- **Figure 2:** add the haul road ISRU->CONSTR row: `all_samples_that_ever_link` ("its points that ever see Earth");
  say in the caption that its point at the oxygen plant never does, so the whole road is never linked at once.
- **Replace the note under section 3** (no task IDs on public pages) with the result, numbers from the staged data:
  "The strategic rule has a second chance the model gives for free: when help would be needed at a point that never
  sees Earth, the job is drawn again. Without that second chance (the rover waits there for the rest of the year), the
  strategic fleet delivers 42 t a year (30 to 58 t by start year)." Add a fourth chip for it. A rescue-time result
  follows from BACKEND (B-59); leave room for one more sentence.
- Small (F-40 list): task IDs such as "(B-36)" in visible source text on /world/ chips: replace with the file name.

## F-42 [REVIEW] (<= 45 min) /research/earth-sky/ section 3: help for any long wait fixes 2028 (B-60) (queued 22 Oct 22:45)
B-60 (`results/E21_fit_r2.json` -> `rescue_any`, same layout as `rescue`): when help comes for ANY strategic rover held
longer than the rescue time, not only at points that never see Earth, 2028 recovers. Help within a week (168 h): 507 t
in 2028, 516 t a year over all start years (always linked: about 532 t); help after a month: 302 t in 2028.
- Replace "None of this changes 2028: ..." with two sentences, numbers from the data: help only at points that never
  see Earth leaves 2028 as it is (the dark spot sees Earth again in July 2029, so a rover stopped there waits it out:
  86-208 t); help for any rover held longer than a week fixes it (507 t in 2028; 516 t a year, close to the 532 t with
  Earth always in view).
- Say the cost: help would be needed about 148 times a year at 168 h (`rescue_any.levels[168].rescues_per_run`), and
  the helper's own time is not counted.
- One chip: "Help for any long wait, 2028 sky" (507 t). Stage `rescue_any` into rescue.json (only what is shown).

## F-43 [REVIEW] (<= 60 min) /research/earth-sky/: a real helper, Earth's cycle, and the years ahead (B-61/62/63)
Three new results are committed (paper 598bc15). The page's section 3 still says "help within a week (helper's time
not counted)". Update it, and add a short section 4. Every number comes from staged data with its flag and source;
no task IDs on the page; same light/dark, 390 px and budget checks as F-42.
1. **Section 3, result text and chips** (replace the help-within-a-week sentences; keep the strand / never-linked
   sentences):
   - `results/E21_fit_r2.json` -> `helper.cells[label = "dedicated k=1, 24 h"]`: one helper rover, called once a rover
     has been held a day, keeps the fleet within 5 % of always-linked tonnage in every start year (523 t a year; worst
     year 97 % of always-linked). It spends most of its working time parked, waiting for its own view of Earth
     (`helper.busy_split_share.parked_waiting_for_earth`, ~95 %). One more hauling rover adds under 1 t
     (`helper.references`, "strict + 1 rover" minus "strict"). Called after a week instead, 2029 falls to 85 %.
   - `results/E21_parking.json` -> `uncovered_calls["0|all"]`: a parking spot in sight of the stuck rover exists
     everywhere, but ~29 % of calls still wait over a week, because Earth is below every nearby horizon for days at a
     time (Earth's monthly cycle). One sentence; it is the page's own subject.
   - Chips: replace "Help within a week" with "One helper, called after a day" (523 t); keep "No help" (42 t); keep
     or drop the others as space allows (max four).
2. **New section 4, "The years ahead"** (one figure + table twin + two sentences):
   - Bars: the dark spot's (#188) linked hours per year, 2028-2050 (`results/E21_later_years.json` ->
     `dark_sample_188.linked_h_by_year`), with its dark spells over 180 days shaded (`dark_spells_188_over_180_days`;
     the last one is censored at the end of 2050; the first began Nov 2025, before the chart).
   - A second small panel or overlay: tonnes a year by start year for strict, strategic (no help) and the one-helper
     fleet: 2028-2031 from `results/E21_strategic_years.json` / the Stage A and Stage H rows you already stage, 2032-2046
     from `E21_fit_r2.json` -> `later_years.by_policy_year` (`mean_t`; five seeds each, say so; 2028-2031 have 20).
     If mixing seed counts on one axis looks misleading, draw 2032-2046 only and say 2028-2031 are in section 3.
   - Text: the dark spells recur about every six years (`period_188.annual`: 5.95 years, 95 % 5.79-6.11), each 3.6-4.0
     years long; without help the fleet collapses in 9 of the 15 start years 2032-2046; with one helper called after a
     day it stays within 5 % of always-linked in every year.
3. **Data:** prepare-data stages only what the page shows into `research/earth-sky/` (extend rescue.json or a new
   `years.json`); add the new files to the page's source list. Budget: data stays under the page's 100 KB.
Files you own as usual; report with the file list. LEAD updates the Earth story separately.
