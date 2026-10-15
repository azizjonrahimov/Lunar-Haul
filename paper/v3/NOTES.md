# Paper v3, front half: notes for the author of the back half

Written 2026-10-15 from the sources listed in the brief plus `research_notes/Lunar landing and rover autonomy
logistics/verification_round_1.md` and two coordinator messages (the verification corrections; the new name
LunarHaul with its verbatim footnote). No existing file was edited. Files written, all under `paper/v3/`:

| File | Content | Words (HTML) |
|---|---|---|
| `part1_front.html` | `<head>`, title, authors, affiliation line, abstract (with placeholders), keywords, name footnote, Section 1 Introduction (RQ6-RQ9, three contributions, what is not claimed, roadmap) | ~2,900 |
| `part2_related.html` | Section 2 Related work (2.1-2.6) and Table 1 | ~2,500 |
| `part3_methods.html` | Section 3 Testbed (3.1-3.6, Tables 2-4, Figures 1-4), Section 4 Experiments, protocol and metrics (Table 5), Section 5 Verification (5.1-5.4, `{{v3-TABLE_E16}}`) | ~9,900 |

## Title

Chosen (used in `<title>` and `<h1>`): **Where the Lander Lands: Landing Precision, Pad Standoff, Plume Keep-Out and
Rover Autonomy Priced in Lunar Surface Logistics**. It follows the coordinator's suggestion ("Where the lander lands:
landing precision, plume keep-out and rover autonomy priced in lunar surface logistics") and adds "pad standoff",
because standoff is the central swept variable (E17, E20) and the one NASA's distance bands are about; capitalised
as the v2 title is.

Options considered:
1. Working title in the brief: "Where the lander lands: how landing precision, plume keep-out and rover autonomy price lunar surface logistics" (omits standoff; "price ... logistics" reads oddly).
2. Coordinator's: "Where the lander lands: landing precision, plume keep-out and rover autonomy priced in lunar surface logistics" (omits standoff).
3. "A Number NASA Left Blank: Landing Dispersion, Pad Standoff and Plume Keep-Out in the Cost of Moving Cargo at a Lunar Base" (hook is close to a rhetorical device; dropped).
4. "Pads, Plumes and Rovers: Learned Landers and Drivers as Stochastic Generators in a Verified Lunar Logistics Simulation" (puts the method before the finding; dropped).

## Name

The testbed is called **LunarHaul** throughout, per the coordinator. The footnote at first use (abstract, marker
`&dagger;`, paragraph `id="v3-fn-name"`) is the coordinator's text verbatim plus a citation [112] for the three
collisions: "LunarHaul was called LunarSim in versions 1 and 2 of this paper and in the archived code; the name was
changed because three unrelated projects share it [112]. The engine's Python package keeps the import name
`lunarsim`." The only other occurrence of "LunarSim" in the three files is inside that footnote. Code paths in the
text (`lunarsim/lander/classes.py`, `lunar/Descent-v0`, `lunar/Drive-v0`, format names `lunarsim-policy`,
`lunarsim-landing-outcomes`, `lunarsim-driving`) are left as they are in the repository.

Out of my scope but needed for consistency: the About page, README, `CITATION.cff`, the site header and the
v2 parts still say LunarSim; `pyproject.toml` keeps `name = "lunarsim"` per the coordinator (the import name stays).

## HTML conventions followed (from `paper/part1_front.html`, `part2_methods.html`, `style.css`, `build.py`)

- Same skeleton as v2 `part1_front.html`: `<!DOCTYPE html>` + `<head>` only in part 1; later parts are bare fragments beginning with `<h2>`.
- Classes used: `.authors`, `.affil`, `.abstract` with `.kw`, `.note`, `.mono`, `.tabcap` with `<b>Table n.</b>`, `<table>`, `<table class="small">`, `th/td class="num"`, `<figure>`, `<figure class="mid">`, `<figcaption><b>Figure n.</b>`, `ul.contrib`, `<ol>` for research questions. No `.eq`/`.algo` needed in the front half.
- Numbered citations `[n]`; v2 numbers [1]-[59] reused where the same source is meant; new sources numbered [60]-[121] (list below).
- Entities as in v2: `&ndash;`, `&deg;`, `&sigma;`, `&ldquo;`/`&rdquo;`, `&plusmn;`, `&times;`, `&sup2;`, `&#10003;`.
- Flags: `style.css` has no superscript or flag class, so every physical number carries "(Measured)", "(Spec)", "(Modelled)" or "(Assumed)" in parentheses at first appearance, as the brief said to do in that case.
- Stylesheet path is `../style.css` and figure paths are `../../figures/v3_fig0N_*.png`, on the assumption that v3 is assembled into `paper/v3/paper.html` (keeps the v2 build untouched). If `build.py` is instead pointed at `paper/` for the output, change these to `style.css` and `../figures/`.

### build.py placeholders

- Reused: `{E3_GAIN}` in the abstract (v2 recap). `build.py` already fills it from `results/E3_thickness.csv`.
- New: `{{v3-TABLE_E16}}` in Section 5.2 (after the model-level checks paragraph). `build.py` needs a `table_e16()` that reads `results/table_E16.csv` (produced by `experiments/phase3/run_phase3.py e16`) and renders a `.tabcap` + `<table class="small">` with the speed-vs-RTT check (sim km/h, JSC km/h, error %, tolerance) and the PSR round-trip energy check (sim kWh, Chen band scaled by mass, inside/outside). Caption text suggestion: "Table 6. Driving-table checks (E16): speed made good against the JSC measurements on the longest flat leg, and the base-to-crater round-trip energy against Chen et al. scaled by mass."
- Not used in the front half but the back half may want: `{{TABLE_VV}}` (extend to the 13 + 1 identity + 13 Phase-3 engine tests), `{INH_MEAN}` etc. for the condensed v2 results in 6.1.
- Assembly order proposed: `v3/part1_front.html`, `v3/part2_related.html`, `v3/part3_methods.html`, `v3/part4_results.html`, `v3/part5_back.html`.

### ids (all prefixed `v3-`)

`v3-title`, `v3-abstract`, `v3-fn-name`, `v3-sec-intro`, `v3-sec-related`, `v3-tab-families`, `v3-sec-testbed`,
`v3-tab-sites`, `v3-fig-terrain`, `v3-tab-classes`, `v3-tab-reward`, `v3-fig-descent`, `v3-fig-rover`,
`v3-fig-dataflow`, `v3-sec-experiments`, `v3-tab-suites`, `v3-sec-verification`.

### Numbering the back half must continue

- Sections: 6 Results (6.1 version-2 findings condensed, incl. the effect of the terrain geometry and the 134 Wh/km energy model on the v2 cells; 6.2 E15 lander Monte Carlo incl. the BC/DAgger-vs-PPO finding and the mapping of sigma_scale to the 50 m target, the 100 m requirement and the demonstrated misses; 6.3 E16 driving tables; 6.4 E17 dispersion x standoff; 6.5 E18 keep-out; 6.6 E19 autonomy x fleet; 6.7 E20 the law and pad siting), 7 Discussion and limitations, 8 Availability. The front half cross-references "Section 6.1", "Section 6.2", "Section 5.4" (compute), "Section 7", "Appendix A" (parameters with flags), "Appendix D" (the lunar ballistic range/time-of-flight table from `verification_round_1.md` section 4(d), Modelled). Appendices B (verification table) and C (STRESS checklist) are assumed to keep their v2 letters.
- Tables: 1 families (part 2), 2 sites and pads, 3 lander classes, 4 reward terms, 5 suites (part 3); `{{v3-TABLE_E16}}` should be Table 6; results tables from Table 7.
- Figures: 1 terrain and sites, 2 data flow, 3 descent environment, 4 rover environment (all referenced in part 3; files `figures/v3_fig01_terrain.png`, `v3_fig02_dataflow.png`, `v3_fig03_descent.png`, `v3_fig04_rover.png` do **not exist yet** and must be produced by `experiments/make_figures.py` or a v3 figure script). Figure 2 is placed at the end of Section 3.6 and Figure 3 at the end of 3.3, Figure 4 at the end of 3.4, Figure 1 after Table 2. Results figures from Figure 5.
- Research questions: RQ6-RQ9 (v2 had RQ1-RQ5).
- Equations: none numbered in the front half; v2's Equation (1) and Algorithm 1 are referred to as v2's.

## Every placeholder (25 occurrences, 23 distinct), with what the results must supply

All are of the form `[[Exx: description]]`. Grep: `grep -o '\[\[E[^]]*\]\]' paper/v3/*.html`.

### part1_front.html (14, all in the abstract, line 15)

1. `[[E17-E19: total simulated years]]` — sum of completed cells x replications across E17, E18, E19 (design: 280 + 1,008 + 40 cells x 30 = 39,840; state what actually ran).
2. `[[E17: paired difference in mean urgent delay, 5 km against 1 km, Phase-2 default fleet, marketplace]]` — from `table_E17.csv` paired columns (seed bootstrap 95% CI).
3. `[[E17: paired difference in cost per kg moved, 5 km against 1 km, with and without an energy price]]` — `cost_per_kg_usd` and `cost_per_kg_with_energy_usd_<p>` paired differences.
4. `[[E17: whether delay depends smoothly on sigma or through off-pad and failed landings, and the sigma at which the effect appears]]` — the hypothesis test of PLAN section 1 item 1; use `offpad_landings`, `failed_landings`, `km_offpad_extra` against sigma_scale.
5. `[[E18: paired difference in mean urgent delay, R 1 km and T 2 h against no keep-out, Phase-3 default fleet]]`.
6. `[[E18: stand-down vehicle-hours per year, same cell]]` — `standdown_vehicle_h`.
7. `[[E18: interaction with night and with fleet size, one clause]]` — night 0.15 vs 0, P2-default vs P2-4 vs P3.
8. `[[E19: vehicles needed to match the supervised fleet's service level]]` — teleop 8 s fleet size whose `sl24_prio1` reaches the supervised fleet's.
9. `[[E20: R-squared of the pooled fit on log mean urgent delay]]` — `E20_fit.json` pooled `log_delay_prio1_mean_h` r2.
10. `[[E20: the sign and size of the leading terms, one clause]]` — the coefficients on D, R, T, ln sigma and their interactions with u, with bootstrap CIs.
11. `[[E15: PPO baseline box rate]]` — `outcomes_lander_CLPS_baseline_s0.json` pass rate (development: 43.6% over 500; 40.5% over 200).
12. `[[E15: BC box rate before DAgger]]` — from the `bc_warmstart` run record (development: 74% over 100 episodes).
13. `[[E15: box rate of the DAgger policy]]` — the exported DAgger policy's outcome table (does not exist yet; LEAD's run was in progress at 14:22).
14. `[[E15: classical box rate]]` — `outcomes_classical_CLPS.json` (development: 93.8% over 500; MK1 93.0%, LARGE 97.0%).

### part3_methods.html (11)

15. line 74 `[[E15: number of DAgger rounds]]` — the recipe was 4 rounds of 400 episodes; state the number actually used for the exported policy.
16. line 80, 84, 140 `[[E15: episodes per controller and class]]` (three occurrences: Monte Carlo paragraph, Figure 3 caption, Table 5) — PLAN says 5,000; committed tables have 500. Use one number everywhere.
17. line 104 `[[E16: which driver produced the driving tables used in E17-E19: the scripted expert, or the learned driver; and the learned driver's measured interventions per km against the Assumed hazard]]` — B-13 (learned rover driver, ONNX) is not built; `driving-v1.json` is the scripted expert's. If the paper ships with the expert tables, say so here and in 6.3 and cut the "learned driver" paragraph down to a design statement.
18. line 135 `[[E17: whether a learned-policy outcome table was also run through the standoff sweep, and in which cells]]` — `run_phase3.py` E17 uses `landing="classical"`; if no learned-policy cell is run, replace with "only through E15".
19. line 149 `[[E17: whether precision runs to a 1% half-width were made for the headline cells, and their n]]` — PLAN section 6 "precision runs for the headline cells as in E14"; not in `run_phase3.py`.
20. line 162 `[[E16: speed made good at 0, 4, 6 and 8 s from the committed tables against the JSC values]]` — `table_E16.csv` check `speed_made_good_vs_rtt`.
21. line 162 `[[E16: round-trip energy base to PSR and back, autonomous, sun 90, from the committed tables]]` — `table_E16.csv` check `psr_round_trip_energy` (B-11's 3.15 kWh was on a draft sites.json with an 11.4 km round trip; the committed route is 4.28 km each way).
22. line 170 `[[E15: training and evaluation wall-clock and hardware for the DAgger clone, the PPO policies and the Monte Carlo]]` — from the policy cards' `training.wallclock_s` and the bc_warmstart record.
23. line 170 `[[E17-E19: suites run, cells completed, replications and wall-clock]]` — from the resumable CSVs' row counts.

Numbers in the front half that are **not** placeholders but come from development runs and should be re-checked
when the final tables exist: the teleop reproduction 3.243/2.576/2.056/1.769 km/h (+0.1/+0.6/+1.3/+0.5%) and the
abstract's "within 1.3%" (current `physics.py`; see contradiction 5 below); the classical law's 93.8/93.0/97.0% at
n = 500 (labelled "development runs" in 5.2); the PPO pathology figures (median |vz| 1.90, vh p90 1.52, 60 vs 89 kg,
8.6 vs 23 s; labelled "development evaluations over 200 episodes"); the LunarLander-v3 warm-up 246.9 +/- 21.2 in
1,368 s (`results/E15_lunarlander_v3_warmup.json`); per-seed wall-clock 0.196 / 0.326 s; the parity numbers of 5.3
(from F-7, F-7b, F-8 in `.team/reports.md`); the MD5 `ebb9e0dea68005cddf4ab4d2bda1bfdd`.

## Assumptions I made

1. Section numbering continues v2's: 1 Introduction, 2 Related work, 3 Testbed, 4 Experiments/protocol/metrics, 5 Verification, 6 Results, 7 Discussion, 8 Availability (PLAN section 7 outline; v2 had the mechanisms as Section 4 and results as 6, so 6 is kept for results).
2. The "nine sites" are the seven base sites plus the two pads, as in v2 and `sites.json`.
3. The reference standoff is 1 km (`SiteMap` default `"1"`; `fit_law._util_reference` uses standoff 1).
4. The learned lander is the BC + DAgger clone of the ZEM/ZEV law (LEAD decision 14:22), with PPO as the comparison; the draft says so in the abstract, 1, 2.3, 3.3 and the contributions. If the DAgger policy does not reach a usable box rate, the contribution-3 wording ("imitation ... did better") still holds on the development numbers (74% vs 40-60%) but the abstract's placeholders will carry the final rates.
5. The rover slip model is described as the coordinator instructed (digitised Hu et al. curves by friction angle, phi sampled per cell in [37.8, 47.8] deg), not as `physics.py` currently implements it (single table). See contradiction 5.
6. The 60 t LARGE class, the 9,000 kg MK1 gate mass and the 440 s MK1 Isp are stated as Assumed with the verification note's 6-11 t band as justification.
7. The E17 sigma sweep is described as a scaling of the classical table's miss vector; mapping to physical dispersion (50 m target, 100 m 3-sigma, demonstrated misses) is left to 6.2 because the table's own miss distribution is needed.
8. "Appendix D" is assumed for the ballistic table; change the letter if the back half orders appendices differently.
9. E16's "longest flat leg of at least 500 m" follows `run_phase3.MIN_FLAT_LEG_M = 500`.
10. The abstract recaps v2 in one sentence per finding using v2's own numbers ($300/kg, 40/88/100%, four vs eight vehicles) plus `{E3_GAIN}`; it does not use the settled E14 numbers.
11. Compute hardware: "8 GB laptop with a four-core CPU" is inferred from `.team/reports.md` (8 GB total, memory kills) and `run_phase3.WORKERS = 3` ("8 GB machine shared"); the 12-core desktop is v2's. Confirm.

## Contradictions and inconsistencies between the sources (none resolved silently)

1. **RL vs imitation for the lander.** The report (section "Flown landers bound the descent model") and PLAN section 1 item 3 say the learned lander must be RL, citing Holt, Origer & Izzo 2025 (BC collapses under stochastic ICs). B-10b found the opposite in this environment: BC of the classical law 74% box vs PPO 40-60%, and PPO fine-tuning lowered the box rate while raising the return; LEAD decided "learned lander = BC + DAgger, PPO stays as the comparison". The draft presents the literature's prediction (2.3) and the contrary finding (contributions; 3.3) and defers the numbers to E15. A likely reconciliation (Holt cloned open-loop optimal trajectories; we clone a closed-loop feedback law under the same noise) is offered in 2.3 as a direction, not asserted.
2. **Tile size.** PLAN section 5.1 says 20 x 20 km / 4000^2; `meta.json` and B-9 say 16 x 16 km / 3200^2 (the PGDA Site01 GeoTIFF as delivered); the report says PGDA fields are 20 x 20 km. The draft uses 16 km. PLAN was not updated (B-9 asked for it).
3. **Line of sight at 0.5 and 1 km.** `site/content/method.md` says "at 0.5 and 1 km the pad has a clear line of sight to the base"; `sites.json` says PAD_A is clear and PAD_B blocked at both standoffs. The draft states the per-pad truth (Table 2, 3.2). method.md should be corrected.
4. **MK1 thrust and throttle floor.** `classes.py` has `t_max_n = 44000` and flags the 8.9 kN floor "Spec (conflicting)" (8.9 vs 4.4 kN); `verification_round_1.md` resolves it: Blue Origin's own release says 10,000 lbf (44.5 kN) "throttling down to 2,000 lbf" (8.9 kN), the 1,000 lbf figure is unsourced and should be dropped, and MK1 hovers on one engine (the report's "3 t-class lander cannot hover" conflated payload with landed mass). The draft says Spec for both and notes "the environment uses 44.0 kN". `classes.py` should be updated (t_max 44,480 N, floor flag "Spec", source the Dec 2020 release) and the policies/outcome tables for MK1 regenerated if the number changes.
5. **Slip model.** `lunarsim/rover/physics.py` uses one slip table (5/8/15/22/35/55/85% at 0-30 deg) read from the report's text anchors, and `data/driving/driving-v1.json` was built from it; `verification_round_1.md` section 5 and the coordinator specify friction-angle curves (20% slip near 7-8 deg on medium soil, dig-in near 18-19 deg). The draft describes the friction-angle model. Consequences: `physics.slip`, `speed_cap_mps` (which divides by the flat-ground slip `SLIP_TABLE[0]` to turn ground speeds into wheel-speed caps; with phi-dependent slip the flat-ground slip is 0.01-0.12), `C_RR_EFF` (calibrated with the 0.05 flat-ground slip; the 0.176 and 134 Wh/km figures move slightly), the driving tables, the E16 checks and the JS port (`site/src/rover/physics.js`) must all be regenerated before E16-E19 are final. The teleop reproduction numbers and "within 1.3%" in the abstract are from the current model and must be re-verified.
6. **thrust^2.5 attribution.** The research notes attributed the ejecta-mass scaling to Lane & Metzger 2015; the verification note shows that paper argues linear erosion-vs-thrust and that the scaling is in Metzger's later abstracts and Metzger & Mantovani 2023. The draft cites [96] for the scaling and [117] for the 2,594 kg erosion estimate and the linearity argument. The report's own text ("Metzger et al. 2019; Metzger & Mantovani 2023") was already right; only the notes were wrong.
7. **Stand-down levels.** The verification note recommends sweeping T over 1-5 min (the ballistic floor is ~90 s); `run_phase3.STANDDOWNS = (0.1, 0.5, 2.0, 6.0)` h. The draft describes the 0.1-6 h sweep with the ballistic floor stated and the longer values labelled operational conservatism (Assumed). Consider adding a 2-minute level (0.033 h) to E18 so the floor itself is a cell.
8. **E17 sigma levels.** PLAN section 6 lists "sigma_scale in {0.25...10} union {req 100 m 3-sigma, demonstrated set}"; `run_phase3.SIGMAS = (0.25, 0.5, 1, 2, 5, 10, 20)` has no explicit requirement or demonstrated levels. The draft describes the seven levels and defers the mapping to 6.2 (placeholder 7 above and Section 3.6 text).
9. **E15 design.** PLAN section 6 says 5,000 episodes and a comparison "vs a classical closed-loop law ... and an open-loop optimum"; committed tables have n = 500 and no open-loop optimum exists in the code. The draft says "We do not include an open-loop fuel optimum in this version" and leaves n as a placeholder.
10. **Energy anchor geometry.** B-11's Chen comparison (3.15 kWh, 11.4 km round trip) was on a draft `sites.json`; the committed route is 4.28 km each way. The report's table says Chen's paths are 12-50 km; B-11 says 24-100 km round trips (consistent if one-way vs round trip); the draft says "24-100 km round trips". E16 supplies the number.
11. **LRV energy figure.** v2 Appendix A says "LRV-derived ~95 Wh/km at 700 kg" and v2 Section 3.4 uses 350 Wh/km for the LTV class; the report and `physics.py` use the measured 1.58-1.67 Ah/km at 36 V = 57-60 Wh/km (58.5 used) and get 134 Wh/km for 1.6 t. The draft states the v2 value (350) and the change; the 95 vs 58.5 discrepancy with v2's appendix must be addressed in the back half (Appendix A) and in 6.1.
12. **Site distances vs v2.** v2 Section 3.2 has pads at 1.7 and 2.1 km, base sites 0.6-2 km, science ~3 km, PSR ~5 km; the terrain layout has CONSTR 0.26, DEPOT 0.40, POWER 0.73, ISRU 1.16, SCI_1 2.14, PSR 3.96 km. Stated in 3.2; 6.1 should report the effect on v2 cells.
13. **The "reduction in distance" quote.** The report attributes "a reduction in distance means a reduction in transfer time and risk" jointly to NASA 2023 (LPI M2M-ACR2023 Safe Precise Lunar Landings PDF) and NASA 2025 (iparch10 logistics/mobility/cargo paper); `verification_round_1.md` fetched a different copy of the 2023 paper (NTRS 20230016301) and quotes other sentences from it. The draft cites [60, 61]. Confirm which document carries the exact sentence before publication.
14. **ADD wording.** The report's gaps table said "ADD Rev B objective LI-5 'defined radius'"; the verification note shows the "defined radius" wording is characteristic/need CN-T-401 L, LI-5 is the objective, Rev B says "TBD" and Rev C (Dec 2025) says "50m landing accuracy for FE segment ... within 25m ... <10 minute". The draft follows the verification note and says NASA does not state whether 50 m is 1-sigma, 3-sigma or a hard radius.
15. **Grogan & de Weck 2012.** Report: unread, might pre-empt pad-slot pricing. Verification: a federation framework with bilateral negotiated exchanges and exogenous prices, no auction, no pads. The draft cites it [116] as precedent for multi-owner space-economy simulation only.
16. **Aerospace 12(12):1115.** Report: unread, might define an intervention-rate metric. Verification: per-task success statistics with N trials; the only per-distance metric is Waymo's incidents per million miles. Cited [120] as the certification counterpart.
17. **Name.** The brief said to keep "LunarSim" with the About page's qualifier; the About page has no qualifier (PLAN section 8 item 3 left it as an owner decision); the verification note found three collisions; the coordinator then fixed the name as LunarHaul with a verbatim footnote. The draft follows the coordinator.
18. **Reward version of committed policies.** The three committed PPO policies (`lander_CLPS_{baseline,hover_bonus,no_eta}_s0`) were trained under env version 1 (kappa 10); the draft's Table 4 is env version 2 (kappa 50, crash -5, near gain 3). E15 must say which version each controller's table was evaluated under; the browser already scores by the card's `env_version`.
19. **Supervised autonomy.** The PLAN says supervised speed is "within the 0.5-3.6 km/h range"; the model's 3.0 km/h cap plus 60 s every 500 m gives 2.74 km/h, close to teleop at 4 s. The draft flags this as following from Assumed values, not data (3.4).
20. **Operators in E19.** `run_phase3.e19_cells` uses `n_operators = max(2, n // 2)`; v2's E5 used 1, 2 and 4 operators. Not a contradiction, stated in Table 5.
21. **Report vs classes.py on CLPS Isp.** The inbox for B-10 suggested Spec; B-10 and `classes.py` flag 311 s Assumed (Apollo DPS stand-in). The draft says Assumed.
22. **Verification note vs report on SCALPSS.** Both agree: still unpublished. The draft quotes the +/-20 mm / 60-80 mm result as Measured [111].

## What the results and back sections will need

- `results/table_E15.csv`, `table_E16.csv`, `table_E17.csv`, `table_E18.csv`, `table_E19.csv`, `table_E20.csv`, `table_E20_siting.csv`, `E20_fit.json` exist in `results/` (untracked at the time of writing) but I did not read their numbers, per the brief; every number from them is a placeholder above.
- The DAgger policy JSON and its outcome table (`data/policies/lander_CLPS_dagger_s0.json`, `outcomes_lander_CLPS_dagger_s0.json`) do not exist yet; nor do MK1/LARGE learned policies (only CLPS was trained).
- The learned rover driver (B-13, ONNX) does not exist; decide whether 3.4's "learned driver" paragraph stays as a method or moves to future work (placeholder 17).
- Figures `v3_fig01`-`v3_fig04` must be generated (descriptions in the captions).
- `build.py`: add `table_e16()`, a v3 parts list and output path; keep the `{E3_GAIN}` fill.
- Appendix A must add every v3 parameter with its flag (the values are in 3.2-3.5; sources in `classes.py`, `env.py`, `rover/physics.py`, `rover/tables.py`, `phase3.py`, `terrain.py`).
- Appendix B: the 13 v2 checks + the identity check (MD5) + the 13 Phase-3 engine tests (`tests/test_phase3_engine.py`) + the model-level checks of 5.2 + the parity table of 5.3.
- Appendix D: the lunar ballistic range/time-of-flight table (verification note section 4(d); Modelled, our computation; g 1.622 m/s^2, R 1,737.4 km, flat and spherical Moon).
- Discussion must cover: PSI uncertainty and why R is swept; no interventions/km data; Earth-test optimism and the VIPER-class limits of the slip data (1.6 t rover outside the data; VIPER grew to 520 kg); one site/tile/layout; 3-DoF; the name change; the still-open items (MK1 dry mass and Isp; SCALPSS erosion; Dundee 1999 paper details; Element Robotics trademark; Lane & Metzger 2012 venue).
- Availability: Zenodo DOI, policies, terrain pack, driving tables, run records (PLAN section 7).

## Reference numbers used in the front half (for the back half's reference list)

v2 numbers reused with v2's entries: [1] Moon Base Architecture User's Guide 2026; [2] Lunar Mobility Drivers and Needs 2024; [3] Lunar Surface Cargo 2024; [5] Goodliff 2025 workshop; [14] SpaceNet (Gralla, Shull, de Weck); [15] Ishimatsu et al. 2016; [16] Ho 2015 / Jagannatha & Ho 2020; [18] Krawciw et al. 2025 "Sharing the load"; [29] Litaker et al. LTV teleoperation (NASA TM-20240001217; NTRS 20240011392); [41] NSSDC Apollo LRV; [59] Hoad, Robinson & Davies 2010.

New entries (cite text and URL to be formatted as v2's `.refs` paragraphs):

- [60] NASA. *Safe and Precise Landing at Lunar Sites*, Moon to Mars Architecture Concept Review 2023 white paper. NTRS 20230016301, https://ntrs.nasa.gov/api/citations/20230016301/downloads/Safe%20and%20Precise%20Landing%20at%20Lunar%20Sites.pdf ; also https://www.nasa.gov/wp-content/uploads/2024/01/safe-and-precise-landing-at-lunar-sites.pdf and https://www.lpi.usra.edu/lunar/strategies/resources/M2M-ACR2023_SafePreciseLunarLandings.pdf (confirm which copy carries the "reduction in distance" sentence).
- [61] NASA. *Logistics, Mobility and Cargo*, Moon to Mars architecture white paper, February 2025. https://www.nasa.gov/wp-content/uploads/2025/02/iparch10-wp-logistics-mobility-cargo.pdf
- [62] N. Gelino et al. (NASA KSC). Lunar Innovation Park site plan, 2026, NTRS 20260002816; M. Hilburger, N. Gelino, Lunar Innovation Park storyboard, NTRS 20260002824.
- [63] KUNC/NPR, "How do you preserve history on the Moon?", 21 Feb 2019 (P. Metzger quoted). https://www.kunc.org/npr-news/2019-02-21/how-do-you-preserve-history-on-the-moon
- [64] NASA. *Recommendations to Space-Faring Entities: How to Protect and Preserve the Historic and Scientific Value of U.S. Government Lunar Artifacts*, Rev A, 2011. https://www.nasa.gov/pdf/617743main_NASA-USG_LUNAR_HISTORIC_SITES_RevA-508.pdf
- [65] K. Ho et al. Space logistics review, 2024. arXiv:2306.01107.
- [66] P. T. Metzger, G. Autry. Lunar landing pad cost optimisation, 2022. arXiv:2205.00378.
- [67] Anderson, Saxena, Metzger. Crater umbrella zones, 2026. PMC13263143; https://www.nature.com/articles/s44453-026-00045-w
- [68] A. Krawciw et al. Autonomous cargo rover field test, 2026. arXiv:2601.03371.
- [69] Vera et al. Mesa lunar base benchmark, *PLOS ONE* 2026, doi:10.1371/journal.pone.0348882.
- [70] Wang. Agent Mars, 2026. arXiv:2602.13291.
- [71] B. Gaudet, R. Linares, R. Furfaro. Deep RL for six-degree-of-freedom planetary landing, 2018. arXiv:1810.08719.
- [72] B. Gaudet, R. Linares, R. Furfaro. Adaptive guidance via meta-RL, 2019. arXiv:1904.09865.
- [73] Chiu et al. Traversability from Perseverance logs, 2026. arXiv:2609.24952.
- [74] Orsula et al. RL waypoint following in a lunar analogue lab, 2025. arXiv:2508.11503.
- [75] Bouton et al. Cost of transport on sand slopes, 2026. arXiv:2606.06790.
- [76] RL dispatcher in DES: *Buildings* 16(11):2274, 2026, doi:10.3390/buildings16112274; taxi dispatch, arXiv:2307.07508.
- [77] Takubo, Chen, Ho. Hierarchical RL for space campaign design, 2022. arXiv:2103.08981.
- [78] Holt, Origer, Izzo. Behavioural cloning vs RL for landing, 2025. arXiv:2507.19535.
- [79] Izzo et al. Review of optimal control and learning for spacecraft guidance, 2023. arXiv:2305.13078.
- [80] Furfaro et al. 2020. arXiv:2003.02182.
- [81] NASA SPLICE. *Precision Landing and Hazard Avoidance requirements/ground rules*, 2020. NTRS 20200002415.
- [82] NASA. HLS requirements (HLS-R-0322), NTRS 20200001606; HLS Statement of Work, https://www.nasa.gov/wp-content/uploads/2023/01/80MSFC20C0034-P00010_Att_J-01_SOW_RIF_TAGGED.pdf
- [83] Lugo et al. Lunar lander navigation study, 2020. NTRS 20205003002.
- [84] Karlgaard et al. IM-1 trajectory reconstruction, 2025. NTRS 20250007036.
- [85] JAXA. SLIM press briefing, 26 Dec 2024, https://www.isas.jaxa.jp/en/topics/files/SLIM-press-briefing-20241226.pdf ; JAXA release 25 Jan 2024.
- [86] Tackett et al. Blue Ghost Mission 1 landing, LPSC 2026, https://www.hou.usra.edu/meetings/lpsc2026/pdf/1958.pdf ; Moon Monday #216.
- [87] Spaceflight Now, 14 May 2025, IM-2 landing causes.
- [88] F. V. Bennett. *Apollo Experience Report: Mission Planning for Lunar Module Descent and Ascent*, NASA TM X-58040, 1970.
- [89] Wittal et al. Lander plume ejecta impacts vs distance, 2020, NTRS 20205003590; NASA OTPS, *Lunar Landing and Operations Policy Analysis*, 2022.
- [90] Gelino et al. In-situ pad construction with regolith and thermoset polymers, ASCE Earth and Space 2022. NTRS 20220000334.
- [91] Hu et al. Physics-based simulation for extraterrestrial terramechanics, 2024. arXiv:2405.11001 (Figs 7, 13 digitised in `verification_round_1.md`); Unjhawala et al. 2025, arXiv:2507.05643.
- [92] Chen et al. LOLA-based terramechanics for PSR round trips, *Frontiers in Astronomy and Space Sciences* 2026, doi:10.3389/fspas.2026.1764826.
- [93] Bojarski et al. End to end learning for self-driving cars (PilotNet), 2016. arXiv:1604.07316.
- [94] Litaker et al. LTV lighting study, 2025. NTRS 20240011393.
- [95] M. K. Barker et al. LOLA 5 m/px polar DEMs, *Planetary and Space Science* 203:105119, 2021; PGDA product 78, https://pgda.gsfc.nasa.gov/products/78
- [96] Metzger et al. "Lander Plume Effects at Outpost on Shackleton Crater Rim", SSERVI ESF 2019, https://www.lpi.usra.edu/exploration/publications/MetzgerEtAl_SSERVI%20ESF2019_LanderPlumeEjecta.pdf ; Metzger, GLEX 2021 (velocity classes); Metzger & Mantovani 2023, arXiv:2305.12234 (thrust^2.5 scaling, "likely an overestimate").
- [97] Korzun, Chambers. NASA PSI poster, IPPW 2023, NTRS 20230011539; Metzger 2024 erosion theory, arXiv:2403.18583.
- [98] Ebrahimi, Bahrami, Roshanian. Optimal sliding-mode guidance with ZEM/ZEV, *Acta Astronautica* 62, 2008.
- [99] Ross, Gordon, Bagnell. DAgger, AISTATS 2011.
- [100] Schulman et al. Proximal policy optimization, 2017. arXiv:1707.06347.
- [101] Raffin et al. Stable-Baselines3, *JMLR* 22, 2021; Towers et al. Gymnasium, 2024, arXiv:2407.17032.
- [102] R. Mueller (LSIC). Lunar landing and launch pads deck, 2020, NTRS 20205009125 (pad requirements; ALHAT 12 deg; Apollo 15 at 11 deg); Rogers 1972, NTRS 19720018253.
- [103] NASA VIPER lunar operations page, https://science.nasa.gov/mission/viper/lunar-operations/ ; Bluethmann 2024, NTRS 20240013903.
- [104] LSIC. *The Path to an Enduring Lunar Presence*. https://lsic.jhuapl.edu/Resources/files/The%20Path%20to%20an%20Enduring%20Lunar%20Presence.pdf
- [105] Immer et al. 2008, NTRS 20130012063; Metzger, Immer, Lane 2009/2021, arXiv:2104.06248 (Apollo 12 / Surveyor III).
- [106] Angelova et al. Learning slip behaviour, JPL 2006.
- [107] Yutu-2 slip: Jilin Univ. paper, https://cjournal.hep.com.cn/1671-5497/CN/PDF/10.13229/j.cnki.jdxbgxb.20211193 ; *Nature Geoscience* ESM, doi:10.1038/s41561-022-00905-6.
- [108] NASA. Apollo 11 LM touchdown dynamics V&V for HLS, 2026. NTRS 20260001760.
- [109] ispace. Hakuto-R Mission 1 landing results, 26 May 2023; SpaceNews, laser rangefinder problems blamed for the Mission 2 crash, 2025.
- [110] Liu et al. Chang'e-4 landing, 2019, PMC6760200 (not cited in the front half; optional).
- [111] Tyrrell, Weisberger, Fahringer, Danehy. SCALPSS 1.1 post-landing terrain, AIAA SciTech 2026, NTRS 20250010922; SCALPSS poster Aug 2026, NTRS 20260007363.
- [112] Pieczynski, Ptak, Kraft, Drapikowski. "LunarSim: Lunar Rover Simulator Focused on High Visual Fidelity and ROS 2 Integration", *Applied Sciences* 13(22):12401, 2023, doi:10.3390/app132212401; Element Robotics "LunarSim" digital-twin platform (FutureFive, 11 July 2025); University of Dundee "LunarSim", IEEE Information Visualization 1999 (title and authors unverified).
- [113] A. Rahimov. *Who Hauls the Habitat? A Verified Simulation Testbed, a Pooled Dispatch Marketplace and a Reference Design for Lunar Surface Logistics*, preprint version 2, October 2026 (this paper's version 2; add the Zenodo DOI).
- [114] NASA. *Moon to Mars Architecture Definition Document*, ESDMD-001 Rev B.1, 2024/2025. NTRS 20240015571.
- [115] NASA. *Moon to Mars Architecture Definition Document*, Revision C, NASA/TM-20250010956, December 2025 (gap 1101; DN-017 L, DN-018 L).
- [116] P. T. Grogan, O. L. de Weck. "Federated Simulation and Gaming Framework for a Decentralized Space-Based Resource Economy", ASCE Earth and Space 2012, pp. 1468-1477, doi:10.1061/9780784412190.156; http://hdl.handle.net/1721.1/84055
- [117] J. E. Lane, P. T. Metzger. "Estimation of Apollo lunar dust transport using optical extinction measurements", *Acta Geophysica* 63(2):568-599, 2015, arXiv:1503.00154.
- [118] J. E. Lane, P. T. Metzger. Ballistics model for particles propelled by a vertically impinging jet, NASA KSC-2010-164, NTRS 20100031187; Lane, Metzger, Carlson, "Lunar dust particles blown by lander engine exhaust", Earth & Space 2010, arXiv:2104.06332.
- [119] Blue Origin. "BE-7 Engine Testing Further Demonstrates Capability to Land on the Moon", 4 Dec 2020 (10,000 lbf, "throttling down to 2,000 lbf"); Blue Moon Mark 1 page (3 t, 100 m accuracy), Wayback snapshots cited in `verification_round_1.md`.
- [120] Dickinson et al. "A Method for Lunar Surface Autonomy Certification", *Aerospace* 12(12):1115, 2025, doi:10.3390/aerospace12121115.
- [121] Astrobotic. *Peregrine and Griffin Payload User's Guide*, January 2022 (100 m x 100 m ellipse). https://www.astrobotic.com/wp-content/uploads/2022/01/PUGLanders_011222.pdf
