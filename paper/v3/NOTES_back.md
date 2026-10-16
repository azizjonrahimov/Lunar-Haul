# Paper v3, back half: notes (Stage 1, 2026-10-15)

Written from the inputs named in the brief. No existing file was edited. Files written, all under `paper/v3/`:

| File | Content | Words (HTML) |
|---|---|---|
| `part4_results.html` | Section 6 Results: intro, 6.1 Lander controllers (E15, full), 6.2 Driving model validation (E16, full), 6.3 Landing dispersion and pad radius (E17, text from the findings, numbers as placeholders), 6.4 Pad standoff (E17, same), 6.5 Plume keep-out (E18, design + B-12c preliminary analysis, placeholders), 6.6 Autonomy and fleet size (E19, full from `table_E19.csv`), 6.7 The fitted law and pad siting (E20, design, placeholders). Tables 7-13, Figures 5-12 | ~9,600 |
| `part5_back.html` | 7 Discussion (7.1-7.5), 8 Limitations, 9 Availability and reproducibility, Appendix A (Tables A1-A4), Appendix B (`{{TABLE_VV}}` + Tables B2-B4), Appendix C (Table C1), Appendix D (Table D1 + derivation), References: the 12 version-2 entries cited in v3 ([1], [2], [3], [5], [14], [15], [16], [18], [29], [41], [43], [59], copied verbatim from `paper/part4_back.html`) and [60]-[121] | ~9,900 |
| `NOTES_back.md` | this file | |

## Placeholders: 100 occurrences, 100 distinct (98 `[[E..]]`, 2 `[[DOI..]]`)

Grep: `grep -o '\[\[[^]]*\]\]' paper/v3/part4_results.html paper/v3/part5_back.html`.

### part4_results.html (86)

Section 6 intro (1)
1. `[[E17: reference-cell P2-default marketplace mean urgent delay with 95% CI]]` (beside build.py's `{MKT_MEAN}`, the settled v2 value)

6.3 Dispersion and pad radius (17)
2. `[[E17: failed landings and cargo lost per year in the reference cell]]`
3. `[[E17: off-pad share at the 50 m level for the 25, 50 and 100 m pads, with CIs]]`
4. `[[E17: off-pad shares at the 100 and 118 m levels for the three pads]]`
5. `[[E17: off-pad shares at 300 and 1,500 m]]`
6. `[[E17: off-pad share at the 10 m level, 50 m pad]]`
7. `[[E17: dCL paired differences in mean urgent delay by level, 50 m pad, 1 km standoff, four fleets and two rules, with bootstrap CIs]]`
8. `[[E17: dCL on the same-day service level by level]]`
9. `[[E17: dCL on cost per kg by level, without and with the 2,000 $/kWh energy price]]`
10. `[[E17: off-pad extra km per year by level, P2-default marketplace]]`
11. `[[E17: dR50 paired differences, 25 and 100 m pads against the 50 m pad, mean urgent delay at the 50 and 118 m levels]]`
12.-18. Table 8, one placeholder per row (classical, 10, 50, 100, 118, 300, 1,500 m): off-pad shares at 25/50/100 m; dCL mean urgent delay for P2-default marketplace, P2-2 in-house, P3-default marketplace with CIs; off-pad km/yr (P2-default marketplace). Columns `offpad_share`, `dCL_delay_prio1_mean_h[_lo/_hi]`, `km_offpad_extra` of `table_E17.csv`.

6.4 Pad standoff (14)
19. `[[E17: mean urgent delay at 0.5 and 5 km for the eight fleet-rule combinations, with CIs]]`
20. `[[E17: dD1 paired differences at 2, 3 and 5 km by fleet and rule, mean urgent delay, with CIs]]`
21. `[[E17: dD1 at 0.5 km by fleet and rule]]`
22. `[[E17: dD1 on the same-day service level at 5 km by fleet and rule]]`
23. `[[E17: km_total and energy at 0.5, 1, 3 and 5 km, P3-default, both rules]]`
24. `[[E17: ratio of marketplace to in-house dD1 at 5 km, by fleet]]`
25. `[[E17: cost per kg at 0.5 and 5 km, P2-default marketplace, no energy price]]`
26. `[[E17: dD1 cost per kg with energy at 2,000 $/kWh, 5 km against 1 km, by fleet and rule]]`
27. `[[E17: route length from pad A to the base at each standoff, from the driving tables]]` (from `driving-v1.json`, not from E17; may be dropped)
28.-32. Table 9, one per row (0.5, 1, 2, 3, 5 km): delays with CIs for P2-2 in-house, P2-default marketplace, P3-default marketplace; dD1 with CIs; km and energy (P3-default marketplace); cost per kg at p = 0 and p = 2,000 (P2-default marketplace).

6.5 Plume keep-out (20)
33. `[[E18: cells and seeds completed, of 37,440 simulated years]]`
34. `[[E18: dNP mean urgent delay, R 1 km, T 2 h, P3-default, marketplace, with CI]]`
35. `[[E18: dNP, R 1 km, T 2 h, P2-default and P2-4, in-house and marketplace, with CIs]]`
36. `[[E18: stand-down vehicle-hours per year, R 1 km, T 2 h, each fleet]]`
37. `[[E18: plume stand-downs and repositions per year, same cells]]`
38. `[[E18: night 0.15 against 0, same cells]]`
39. `[[E18: the R x T cells whose bootstrap interval excludes zero, by fleet and rule]]`
40. `[[E18: dNP at R 3 km, T 6 h, all fleets and rules]]`
41. `[[E18: dNP at T 0.033 h, R 1 km, P3-default, both rules]]`
42. `[[E18: dNP at T 6 h, R 1 km, P3-default, both rules]]`
43.-51. Table 10, one per row: (R, T) = (1, 0.033), (1, 0.1), (1, 0.5), (1, 2), (1, 6), (0.2, 2), (3, 2), (3, 6) at the 1 km standoff and (1, 2) at the 3 km standoff: dNP mean urgent delay with CIs for P2-default marketplace, P2-4 in-house, P3-default marketplace, P3-default in-house; `standdown_vehicle_h` and `plume_standdowns` (P3-default marketplace). Night 0.15.
52. Figure 9 caption: `[[E18: seeds per cell in the final figure; the figure on file is preliminary]]`

6.7 Law and siting (34)
53. `[[E20: pooled R-squared on log mean urgent delay, n rows and seeds]]`
54. `[[E20: residual SD, pooled log delay]]`
55. `[[E20: coefficient on standoff D with CI, as % per km]]`
56. `[[E20: coefficient on ln miss with CI, as % per e-fold of miss]]`
57. `[[E20: coefficient on the off-pad share with CI]]`
58. `[[E20: coefficients on R and T and on R x T, with CIs]]`
59. `[[E20: coefficient on u and on the D x u, R x u and T x u interactions, with CIs]]`
60. `[[E20: the marketplace dummy with CI]]`
61. `[[E20: R-squared on sl24, pooled]]`
62. `[[E20: R-squared on cost per kg without and with energy prices]]`
63. `[[E20: per-mechanism R-squared and the D coefficient for in-house and marketplace, with CIs]]`
64.-75. Table 12, one per row: const; ln miss; off-pad share; pad radius; standoff; keep-out; stand-down; utilisation; night fraction; the six interactions; the mechanism dummies; the n / seeds / R2 / residual SD / dropped-constant line. Three responses each (`log_delay_prio1_mean_h`, `sl24_prio1`, `cost_per_kg_with_energy_usd_2000`) from `table_E20.csv` (`subset == pooled`).
76. Figure 11 caption: `[[E20: n years and seeds, pooled R-squared, in the final figure; the figure on file is from the E17 rows only]]`
77. `[[E20: hauling cost per year at 0.5, 1, 2, 3 and 5 km, reference cell, p = 0 and 2,000]]`
78. `[[E20: damage term at 0.5, 1, 2, 3 and 5 km for the 1 M$ per impact case, reference cell]]`
79. `[[E20: minimum-cost standoff of the reference cell by energy price, damage cost and value of time]]`
80. `[[E20: share of minima at 0.5, 1, 2, 3 and 5 km by energy price, damage cost and value of time, from table_E20_siting_shares]]`
81.-85. Table 13, one per row (0.5, 1, 2, 3, 5 km): hauling M$/yr at p 0 and 2,000; pad M$/yr (three cases: 13.0 / 22.9 / 54.8, which do not depend on the data); damage M$/yr at 0.1 / 1 / 10 M$ per impact; delay valuation at 100 and 1,000 $/item-h; total. From `table_E20_siting.csv.gz` for the reference cell (P2-default, marketplace, classical level, 50 m pad).
86. `[[E20: shares of minima by standoff for the 36 (energy price, damage cost, value of time) combinations, condensed]]` (`table_E20_siting_shares.csv`)

### part5_back.html (14)

7.1 (9)
1. `[[E20: coefficient on standoff as % per km, pooled, with CI]]`
2. `[[E17: the 0.5 to 5 km difference by fleet and rule, from Table 9]]`
3. `[[E20: minimum-cost standoff range across cost cases, from Table 13]]`
4. `[[E17: off-pad shares at the 50 m level, three pads]]`
5. `[[E17: dCL at 50 and 300 m, Table 8]]`
6. `[[E17: off-pad share at 10 m, 50 m pad]]`
7. `[[E18: dNP for R 1 km, T 2 h by fleet and rule]]`
8. `[[E18: dNP at T 0.033 h]]`
9. `[[E18: dNP at T 6 h]]`

8 Limitations (2)
10. `[[E17: P3-default utilisation in the reference cell]]`
11. `[[E20: pooled R-squared]]`

9 Availability (2) and References (1)
12. `[[DOI: Zenodo record for version 3, to be minted at submission]]` (not an E placeholder)
13. `[[E17-E19: wall-clock of the three suites with three workers]]` (from the runner's log; not in any table)
14. `[[DOI: Zenodo record of version 2]]` in reference [113] (not an E placeholder)

Also present: build.py placeholders `{MKT_MEAN}` (Section 6 intro) and `{{TABLE_VV}}` (Appendix B). Both exist in `build.py`; the v3 build needs a parts list `v3/part1_front.html` ... `v3/part5_back.html`, an output path (`paper/v3/paper.html`, matching the `../style.css` and `../../figures/` paths used by every part), the `table_e16()` for part3's `{{v3-TABLE_E16}}`, and the existing `{E3_GAIN}` and settled-number fills.

## Numbering used

- Sections: 6 Results (6.1 Lander controllers; 6.2 Driving model validation; 6.3 Landing dispersion and pad radius; 6.4 Pad standoff; 6.5 Plume keep-out; 6.6 Autonomy and fleet size; 6.7 The fitted law and pad siting), 7 Discussion (7.1-7.5), 8 Limitations, 9 Availability and reproducibility, Appendices A (parameters), B (verification), C (unverified items), D (ballistics), References. This follows the brief and **not** the front half's cross-references; see "Front-half edits needed" below.
- Tables: 7 controllers (E15); 8 dispersion (E17); 9 standoff (E17); 10 keep-out (E18); 11 autonomy x fleet (E19); 12 law coefficients (E20); 13 siting (E20); A1 terrain, A2 lander, A3 rover, A4 plume / engine mapping / E20 costs; B1 = `{{TABLE_VV}}` (v2's 13 checks), B2 identity + 14 Phase-3 engine tests, B3 model-level checks, B4 Python-browser parity; C1 unverified items; D1 ballistic table. Table 6 is part3's `{{v3-TABLE_E16}}`.
- Figures: 5 = `fig20_lander_mc`, 6 = `fig21_driving_validation`, 7 = `fig22_dispersion_standoff`, 8 = `fig23_standoff`, 9 = `fig24_plume`, 10 = `fig25_autonomy_fleet`, 11 = `fig27_law`, 12 = `fig26_siting` (law before siting, as in the text). Paths `../../figures/fig2N_*.png`.
- ids: `v3-sec-results`, `v3-tab-controllers`, `v3-fig-lander-mc`, `v3-fig-driving-validation`, `v3-tab-dispersion`, `v3-fig-dispersion`, `v3-tab-standoff`, `v3-fig-standoff`, `v3-tab-keepout`, `v3-fig-plume`, `v3-tab-autonomy`, `v3-fig-autonomy`, `v3-tab-law`, `v3-fig-law`, `v3-tab-siting`, `v3-fig-siting`, `v3-sec-discussion`, `v3-sec-limitations`, `v3-sec-availability`, `v3-app-params`, `v3-app-verification`, `v3-app-unverified`, `v3-app-ballistics`, `v3-refs`.
- Reference [110] (Chang'e-4) is listed but cited nowhere in v3 (NOTES.md called it optional); drop it or cite it.

## Front-half edits needed for consistency (not made; the brief forbade editing other files)

1. Section numbers. part1 roadmap paragraph: "Section 6 reports results: the version-2 findings condensed, then ..." (there is no condensed-v2 subsection; the Section 6 intro covers it in one paragraph), "Section 7 discusses ... and their limitations" (limitations are now Section 8), "Section 8 gives availability" (now 9), "Appendices give ... the verification table and the reporting checklist" (Appendix C is now the unverified-items table; there is no STRESS checklist). part2 2.3 "Section 6.2" -> 6.1. part3: "Section 6.1 reports the effect of the geometry change on the version-2 cells" (3.2 and 3.4) -> "the Section 6 introduction"; "Section 6.2" (3.3 twice, 3.6, 4.1 and 5.2) -> 6.1; the learned-driver placeholder's "6.3" -> 6.2.
2. E17 design (part3 4.1, Table 5, NOTES contradiction 8): the suite sweeps seven implied-mean-miss levels (2.9 classical, 10, 50, 100, 118, 300, 1,500 m; sigma_scale 1, 3.4, 17.2, 34.5, 40.7, 103, 517) x pad radius {25, 50, 100 m} x standoff x 4 scenarios x 2 rules = 840 cells, 25,200 years (complete), not sigma_scale {0.25 .. 20} and 280 cells.
3. E18 design (part3 3.5, 4.1, Table 5; NOTES contradiction 7): five stand-downs {0.033, 0.1, 0.5, 2, 6 h}, 1,248 cells, 37,440 years by design; `E18_plume.csv` had 30,450 rows (81%) at drafting.
4. Total simulated years by design (abstract placeholder 1): 25,200 + 37,440 + 1,200 = 63,840, not 39,840. State what ran.
5. E20 design (part3 4.2): the fit uses ln(implied mean miss) not ln sigma_scale, and adds `offpad_share` and `pad_radius_m` as regressors; the siting table adds a plume-damage term (Wittal impacts x LOS shield x cost per impact) and a delay valuation (items x mean delay x value of time) to hauling + pad cost. Part 3 should say so or defer to 6.7.
6. Imitation recipe (part3 3.3 "Imitation with DAgger", placeholder 15): the released clone (`lander_CLPS_bc_v3_s0`) imitates the **memoryless** rewrite of the law, under observation version 3, with 800 expert episodes (266,923 samples), 25 epochs, **2** DAgger rounds of 300 episodes; part3's "2,000 episodes (~700,000 samples), 30 epochs, [[rounds]] of 400" describes the first clone of the filtered law. The paragraph's closing sentence ("the residual gap between clone and law is informative about how much of the law's performance is memory") should be rewritten: the finding is that the filtered law cannot be cloned at all by a memoryless learner (Section 6.1).
7. Observation version 3 (part3 3.3 "Sensor model" says the observation has fifteen components): add the four altimeter-history inputs and ENV_VERSION 3.
8. Learned driver (part3 3.4, placeholder 17): not trained; E17-E19 use the scripted expert's tables; cut the paragraph to a design statement.
9. Placeholder 16 (episodes per controller): 500. Placeholder 18: no learned-policy table was run through E17; "only through E15". Placeholder 19: no precision runs were made. Placeholder 20: 3.262 / 2.570 / 2.031 / 1.764 km/h (+0.66 / +0.38 / +0.07 / +0.20%). Placeholder 21: 1.77 kWh (autonomous, daylight route of 8.95 km; the row's sun azimuth is the 0 deg route, not 90 deg; night route 8.57 km, 1.89 kWh). Placeholder 22: PPO baseline 2,007,040 steps in 9,685 s wall-clock (stalled between 250 k and 500 k steps; 60-70 s per 100 k steps otherwise; hover v2 314 s, no_eta 464 s for 507,904 steps); BC+DAgger obs v3 655 s and obs v2 714 s on one process; each 500-episode Monte Carlo 14-29 s. Placeholder 23: E17 840 x 30 complete, E19 40 x 30 complete, E18 1,248 x 30 in progress at drafting; wall-clock unknown to me.
10. Abstract placeholders 11-14: PPO 63.2% (reward v2; 43.6% under v1); BC before DAgger 87.2% on 500 episodes (obs v3; 91% in the 100-episode round evaluation); DAgger clone 89.0%; classical 93.8%. Placeholder 8 (E19): no teleoperated fleet of up to eight vehicles at 8 s reaches the six-vehicle supervised fleet's same-day service level under either rule (marketplace 0.900 +/- 0.047 at eight against 0.936 +/- 0.037; in-house 0.805 against 0.834); at 4 s eight vehicles do under the marketplace (0.935). Two autonomous vehicles deliver urgent cargo about as fast as six teleoperated at 8 s.
11. part3 5.2 "the base-to-crater round trip (8.6 km by route)": the E16 check row is the 8.95 km daylight route (sun 0 deg); 8.57 km is the sun-90 deg and night route.
12. part3 3.4 effective rolling coefficient 0.176 -> 0.178 (B-11b, after the slip curves; `physics.py`). Appendix A uses 0.178.
13. part3 Table 4 caption says "environment version 2"; the environment is now version 3 (observation only; reward unchanged). Fine as is if "reward of version 2" is meant.

## Contradictions and inconsistencies in the inputs (none resolved silently)

1. **E17 and E18 designs** differ between part3 / NOTES.md and `run_phase3.py` / `table_E17.csv` (items 2-4 above). The back half follows the runner and the tables and says so in the Section 6 intro.
2. **E20 fit on file is preliminary.** `results/E20_fit.json` records `inputs.E18: None` and 8,000 rows, so it was fitted on a partial E17 alone; `table_E20.csv`, `fig27_law.png` (17:41) and `fig26_siting.png` (19:09, from the final E17) will change when E18 is in. The text says so; Stage 2 replaces.
3. **Committed PPO policies are env version 2**, not 1 (NOTES contradiction 18 is out of date): the cards of `lander_CLPS_baseline_s0`, `hover_bonus_s0`, `no_eta_s0` record `env_version: 2`, git 9d5eec4, retrained (`.team/reports.md` F-16a). The reward-v1 numbers (43.6% box, 182 sensor failures) survive only in `.team/reports.md` (LEAD 13:49, ladder 19:16) and in the superseded `lander_CLPS_hover_bonus_v1_s0`; the miss / propellant / time-below-30 m values of the v1 baseline row in Table 7 (5.73 / 7.55 / 99.9 m; 59.8 kg; 8.5 s; -2.18 m/s; paired -50.2 +/- 4.8) come from the earlier `results/table_E15.csv`, which was overwritten during this session. Keep the row labelled "superseded; development evaluation" or drop it.
4. **Memoryless law and round-0 clone have no released outcome tables.** Their box rates (94.8%, 87.2% on 500 episodes) are from B-10d and the LEAD ladder; Table 7 marks them "development evaluation, table not released". If the tables are released, fill the row.
5. **Real-leg slowdown**: LEAD 19:29 says the flattest real leg runs "2-6 % slower"; `table_E16.csv` gives -4.7 to -7.2% (rel_err -0.071, -0.068, -0.072, -0.047). The text uses the table.
6. **Night energy**: `table_E16.csv` has autonomous night (1.894 kWh) above day (1.766) but teleoperated night (1.765) below day (1.842); B-12c's route-length explanation (night route 8,567 m is the shortest; per-metre energy equal within 2%) is given, with the per-run speed factor left implicit. Section 6.2 reports the numbers as they are.
7. **PSR route length** 8.6 km (part3) vs 8.95 km (E16 day row) vs 8.57 km (night and sun-90) (item 11 above).
8. **C_rr,eff** 0.176 (part3) vs 0.178 (`physics.py` after B-11b).
9. **Figures on file.** `phase3_captions.json` marks fig20-25 and fig27 "not built in this run" (only fig26 was built last). PNG timestamps: fig20, fig21, fig25 at 17:44 (fig20 therefore predates the obs-v3 clone of 19:12 and fig25 may predate the final E19 data); fig24 and fig27 at 17:41 (preliminary E18 / E17-only fit); fig22 and fig23 at 18:59-19:02 (final E17). Rebuild all eight in Stage 2 with `make_figures_phase3.py` and re-check the captions' "PRELIMINARY" clauses.
10. **v2 Appendix A LRV energy** "~95 Wh/km at 700 kg" vs the measured 57-60 Wh/km (NOTES contradiction 11): addressed in the Appendix A preamble.
11. **Section numbering** between the brief and the front half (item 1 above).
12. **Appendix C letter**: the front half's Section 1 says the appendices give "the reporting checklist"; the brief makes Appendix C the unverified-items table. No STRESS checklist is included.
13. **Interventions in E19** fall with teleoperation latency (autonomous ~510/yr, teleop 8 s ~428/yr) although the base hazard is higher for autonomy: the terrain terms (1/km on steep and rough cells) dominate and the slower teleoperated fleet drives the same kilometres; the text says the counts are "nearly independent of the level". Not a contradiction, but worth a check in `tables.py` if the reader asks.
14. **n_operators** in E19 is max(2, n/2): 2, 2, 3, 4 operators for 2, 4, 6, 8 vehicles; stated in Table 11's caption.

## Stage 2 checklist

1. `run_phase3.py e18` to completion; `fit_law.py` (refits E20 on E17 + E18, rewrites `table_E17.csv`, `table_E18.csv`, `table_E20*.csv`, `E20_fit.json`); `make_figures_phase3.py` (all eight figures; check `phase3_captions.json` statuses and the PRELIMINARY clauses).
2. Replace the 98 `[[E..]]` placeholders above from: `table_E17.csv` (columns `offpad_share`, `dCL_*`, `dD1_*`, `dR50_*`, `km_offpad_extra`, `failed_landings`, `cargo_lost_kg`, `km_total`, `energy_kwh`, `cost_per_kg_usd`, `cost_per_kg_with_energy_usd_2000`, `utilisation`), `table_E18.csv` (`dNP_*`, `standdown_vehicle_h`, `plume_standdowns`, `repositions`), `table_E20.csv` (pooled and per-mechanism rows), `E20_fit.json` (`pooled.*.r2`, `residual_sd`, `dropped_constant`, `siting.*`), `table_E20_siting_min.csv` / `table_E20_siting_shares.csv`, and the raw CSV row counts for completeness and the runner's log for wall-clock.
3. Re-read the Section 6 intro, 6.3, 6.4, 6.5 and 6.7 prose against the final numbers: the findings sentences ("+4 h to +18 h", "about 65 / 30 / 2%", "+0.1-0.5 h", "roughly halves") are LEAD's approximate readings of the final E17 and must be checked against the table, and the E18 sentences describe the preliminary analysis and must be reconciled with the final signs.
4. Rebuild Table 7 if the memoryless-law or round-0 outcome tables are released; otherwise leave the "not released" marks.
5. Decide reference [110] (uncited) and the two DOI placeholders.
