# P2 placeholders (draft 0, 28 Oct 2026)

`build_p2.py` fills every `{{P2-...}}` in `part1`-`part5` and fails on any unfilled placeholder and on any nan/inf.
Since the referee round of 11 Nov 2026 no pending marker may print (decision A4 of
`reports/referee_phase6_decisions.md`): the build runs without `--allow-pending`, stops if the assembled text holds a
`[[PENDING` string, and a result that has not landed has one plain sentence in its place (see "Awaited results" at the
end). `--allow-pending` still exists for a draft when a results file of an experiment that has run is missing.
Families are written with `{m}` (fleet multiple 1, 2, 4, 8), `{y}` (start
2028, 2038), `SHARE{s}` (0, 5, 40 for the shares 0, 0.05, 0.40), `BAY{b}` (05, 2 for 0.5 and 2 km), `OWNER-{o}`
(A, B, C) and `SINGLE-KM-{lim}` (15, 10, 8 degrees); the build maps a key to its family before checking it is listed.

**What is typed and what is a placeholder.** Results of this study are always placeholders. Model inputs that a file
holds (the corridor analysis, the route length, the load factor, the horizons) are placeholders read from that file.
Rule parameters, seeds, timeouts and the 5 % pre-registered margin are typed with their provenance flag. Numbers
quoted from the literature and from our earlier papers [40-42, 44] are typed with the citation.

**Abbreviations.** C = `results/table_E43_cells.csv` (row = `label` + `start_year`; cell means of every metric).
P = `results/table_E43_pairs.csv` (row = `comparison` + `metric`; `mean`, `lo`, `hi`, `lo90`, `hi90`, `n`, `b_mean`,
`share_of_b`, `ratio_lo`, `ratio_hi`, `ratio_hi95`). F = `results/E43_fit.json` (H8 per density, deadlocks, owner
waits, run times, design). K = `results/ATC_roads_corridor.json`. D = `data/scenarios/p5/E43-design.json`.
Comparisons are named in `LABELS` of the build script; the analysis is `experiments/phase5/analyse_e43_pairs.py` (BACKEND's `analyse_e43.py` writes the report summary).

| Key | Source | Format |
|---|---|---|
| P2-N-RUNS-E43, P2-N-CELLS-E43 | raw run files, F | count |
| P2-K30 | D `load_multiplier_30pct` | 3 decimals |
| P2-HORIZON-X{m}-D | run_phase5 `E43_DENSITY` (checked against F `horizons_days`) | integer days |
| P2-N-SAMPLES, P2-ROUTE-KM, P2-N-JUNCTIONS | K `samples`, `route_km_unique`, `junctions_excluded` | count; km |
| P2-MEDIAN-WIDTH-20, P2-SLOPE-MAX | K `by_slope_limit_deg.20.median_width_m`, `slope_at_sample_percentiles_deg.1.0` | m; degrees |
| P2-SINGLE-KM-{lim}, P2-SINGLE-SHARE-10 | K `by_slope_limit_deg.{lim}.single_lane_km_unique`, `.10.single_lane_share` | km; % |
| P2-SHARE-MAX-PCT | the largest `single_share` among E43 rows | % |
| P2-SINGLE-KM-DEFAULT, P2-SHARE40-SINGLE-KM | C `road_single_km` of `atc x1` and `atc x1 share 0.4` | km |
| P2-ATC-X{m}-TRAVERSALS, P2-ATC-X{m}-CONFLICTS, P2-ATC-X{m}-BAY-WAIT-H, P2-ATC-X{m}-APRON-WAIT-H, P2-ATC-X{m}-EVA-SLOW-H, P2-ATC-X{m}-STANDDOWNS | C row `atc x{m}` | count; hours |
| P2-ATC-X1-CONFLICTS-PER-WEEK | C `road_conflicts` of `atc x1` / 52 | 1 decimal |
| P2-ATC-X1-LANDINGS | `results/E43_runs.lead.csv` `landings`, mean over the 30 runs of `atc x1` (the referee's M10: `plume_standdowns`, which the text had called pad closures, counts jobs held and vehicles sent to shelter); checked: the same rows give C's `plume_standdowns`, and every E43 run has `regime` O_ORACLE | count |
| P2-R7-ATC-FOLD | (C `delay_mean_h` of `atc x1` + P `atc x1 r7 - atc x1` mean) / C `delay_mean_h` of `atc x1` | ratio, 1 decimal (abstract: delay under the strict reading of R7 as a multiple of the default) |
| P2-UNC-X1-WAIT-PER-CONFLICT-H | C `road_hand_wait_h` / `road_hand_conflicts` of `uncoordinated x1`, 2028 | hours per referred conflict (5.4, 6.1: the Earth-window gap, not the staff time, sets the cost) |
| P2-OWNER-{o}-BAY-WAIT-X{m}, P2-OWNER-BAY-WAIT-ORDER-CLAUSE | F `owner_bay_wait_h_atc.{m}` (only x1 is used in the text) | hours; composed: which owner waited most and least |
| P2-DEADLOCKS-TOTAL | F `deadlocks_total_by_density` summed | word (checked = 0 for the "no deadlock" sentences) |
| P2-DEADLOCKS-TOTAL-N | F `deadlocks_total_by_density` summed | the same count with digits, for the parenthesis in 5.1 |
| P2-VIS-2028 | 4.2 | share of hours with Earth in view at the base in start year 2028, E40_fit.json hypotheses.H2.30.visibility |
| P2-VIS-2038 | 4.2 | the same for 2038 |
| P2-NONE-X{m}-DELAY, P2-H8-X{m}-DELAY | C `delay_mean_h` of `none x{m}`, `atc x{m}` | hours, 1 decimal |
| P2-H8-X{m}-DIFF, P2-H8-X{m}-DIFF-CI, P2-H8-X{m}-PCT, P2-H8-X{m}-UPPER | P `H8: atc - none, x{m}` on `delay_mean_h`: `mean`, [lo, hi], `share_of_b`, `ratio_hi95` | hours with sign; %; % |
| P2-H8-X1-P90-DIFF, P2-H8-X1-ITEMS-DIFF, P2-H8-X1-URGENT-DIFF, P2-H8-X1-OPERATOR-DIFF, P2-X1-ITEMS | P same comparison on `delay_p90_h`, `delivered_items`, `atc_urgent_wait_mean_cens_h`, `operator_hours`; C `delivered_items` of `none x1` | signed, with CI |
| P2-H8-VERDICT-SENTENCE | F `H8.1.supported` | composed: supported / not supported, with the margin |
| P2-H8-X8-CLAUSE, P2-H8-X8-SENTENCE, P2-H8-X8-DISCUSSION-CLAUSE, P2-UNC-X8-SENTENCE, P2-X8-STATUS-SENTENCE | F `H8.8`, D `design_changes`, run counts | composed; pending while 8x has no rows |
| P2-UNC-X{m}-DELAY-{y}, P2-UNC-X{m}-DIFF-{y}, P2-UNC-X{m}-DIFF-CI-{y}, P2-UNC-X{m}-RATIO-{y} | C `uncoordinated x{m}` at year y; P `uncoordinated - none, x{m}, {y}` (`mean`, CI, 1 + `share_of_b`) | hours; ratio 1 decimal |
| P2-UNC-X{m}-HAND-CONFLICTS-{y}, P2-UNC-X{m}-HAND-WAIT-H-{y}, P2-UNC-X{m}-OTHER-STOP-H-{y} | C `road_hand_conflicts`, `road_hand_wait_h`, `road_other_stop_h` | count; hours |
| P2-UNC-X1-RATIO, P2-UNC-X1-HAND-WAIT-H, P2-UNC-X1-DELAY | the 2028 values above (abstract) | as above |
| P2-UNC-VS-ATC-X{m}-DIFF-{y} | P `uncoordinated - atc, x{m}, {y}` `mean` with CI (only x1 is used in the text) | hours with sign |
| P2-SHARE{s}-ATC-DIFF, P2-SHARE{s}-UNC-DIFF, P2-SHARE{s}-UNC-RATIO | P `atc x1 share {s} - none x1`, `uncoordinated x1 share {s} - none x1` | hours with sign; ratio |
| P2-SHARE40-ATC-DIFF-CI, P2-SHARE40-ATC-PCT, P2-SHARE40-ATC-PCT-ABS, P2-SHARE40-ATC-BAY-WAIT-H, P2-SHARE0-UNC-HAND-CONFLICTS | P `atc x1 share 0.4 - none x1` (CI, `share_of_b`, `ratio_hi95`); C rows | CI; %; hours; count |
| P2-BAY{b}-ATC-VS-ATC-DIFF, P2-BAY05-ATC-VS-ATC-DIFF-CI, P2-BAY05-ATC-TRAVERSALS | P `atc x1 bay {b} - atc x1`; C `road_traversals` of `atc x1 bay 0.5` | hours; count |
| P2-R7-ATC-DIFF, P2-R7-ATC-DIFF-CI, P2-R7-HAND-CONFLICTS, P2-R7-HAND-WAIT-H, P2-R7-UNLINKED-JOBS | P `atc x1 r7 - atc x1`; C `atc x1 r7` | hours; counts |
| P2-RUN-S-X{m}, P2-RUN-S-X8-CLAUSE, P2-E43-CPU-H | F `run_s_mean_by_label` (mean over the three modes at that multiple), raw `run_s` sum | seconds; hours |
| P2-N-CHANGES-WORD, P2-X8-HORIZON-SENTENCE | D `design_changes` (three dated entries; the run times are parsed from their `why`) | composed |
| P2-WAKE-SENTENCE | `results/E43_fixpoint_before_after.json` from `experiments/phase5/compare_rerun.py --exp E43` (rows matched, mean and max change of `delay_mean_h`, share moved > 0.1 h, run times) | composed; pending until the comparison is as new as the run files |
| P2-INCOMPLETE-CELLS-SENTENCE, P2-R7-N-CLAUSE | run counts per (label, year) against the design blocks; P `atc x1 r7 - atc x1` `n` | composed: "Every cell ran all its seeds." or the short cells with their counts |
| P2-CHECKS-SENTENCE, P2-FAILED-CHECKS-SENTENCE | `results/vv_phase5.json` rows whose `papers` holds P2: counts by `kind` and `technique`, `commit`; outcomes from `passed`, `skipped`, `bias_flag`, `error`/`rel_error` against `tolerance`; the summary is recounted from the rows and every passed flag recomputed | composed; pending until B-79 lands |
| P2-PAIRING-SENTENCE | `results/vv_phase5.json` D10 row `E40 demand identical` (passed, pairs from basis) | composed |
| P2-SHARED-CHECK-LIMITATION | `lunarsim/atc/roads.py` calling the shared `safety_check()` (B-78) | composed |
| P2-E44-N-ENCOUNTERS | B = `results/E44_bounds.json` (`tools/atc/run_e44.py summarize`): sum of `types.{k}.n_driven` | count |
| P2-E44-DESIGN-SENTENCE, P2-E44-DESIGN-SENTENCE-SHORT | B `near_miss_definition`, type 1 `n`/`n_driven`; the design n per type typed from change 6 (`E44_N`); the defect count from `results/E44_defects.json` (change 8) | composed (methods: design, bounds, weights, outcome classes, the stopped first run) |
| P2-E44-INTRO-CLAUSE, P2-E44-RESULTS-PARAGRAPH, P2-E44-DISCUSSION-CLAUSE, P2-E44-COMPARISON-CLAUSE | B `types.{k}` (`n`, `n_driven`, `n_eff`, `violations`, `violations_by_kind`, `bound`, `bonferroni_bound`, `near_misses`, `min_margin_m`, `outcomes`, `emergency_brake_rate`); `E44_defects.json` `defects_found_in_main_run` (first-run counts, re-runs after each fix, the type-9 finding) | composed; pending until all 12 types reach their designed n; checked: outcome classes sum to n, every rerun after a fix clean, the type-9 record is the dead stop |
| P2-E44-COMPUTE-SENTENCE | B `types.{k}.run_time_s`, `peak_rss_mb`; batch sizes typed from `tools/atc/run_e44.py` `BATCH` | hours; MB |
| P2-DEADLOCK-SCOPE-CLAUSE | `results/ATC_roads_rings.json` (`merge_m`; `by_share.{s}.rings`, `ring_lengths_m`, `raw_sample_cycles` for 0.05, 0.15, 0.4; BACKEND, B-78) | composed: the zero count is a property of the logistics model (unbounded bays); the ring question is undetermined from the samples; checked: counts match their length lists |
| P2-E45-N-NODES | `lunarsim/atc/modelcheck.py` `X` (the road cells) | count |
| P2-E45-DESIGN-SENTENCE, P2-E45-INTRO-CLAUSE, P2-E45-RESULTS-PARAGRAPH, P2-E45-DISCUSSION-CLAUSE, P2-E45-COMPUTE-SENTENCE | M = `results/E45_modelcheck.json` (`tools/atc/run_e45.py`): `models.{A,B,C,D}` (`states`, `transitions`, `K_max_steps_to_goal`, `seconds`, `peak_mb_traced`, the zero counts), `mutations.{R3_exit,R5_entry,R7_hold}` (`deadlock_states`, `cannot_reach_goal`, `livelock_sccs`, `deadlock_trace_length`, `violating_states`, `violation_kinds`, `counterexample_length`), `step_s`, `cell_m` | composed; checked: the four layouts and three mutations are the named ones, every layout passes, every mutation is caught. The results paragraph ends with the development counterexamples from `results/E45_development.json` (`items[].kind`; checked: the four known kinds) |
| P2-E47-DESIGN-SENTENCE, P2-E47-GEOMETRY-SENTENCE, P2-E47-INTRO-CLAUSE, P2-E47-RESULTS-PARAGRAPH, P2-E47-DISCUSSION-CLAUSE, P2-E47-LIMITATION-SENTENCE | results/E47_fit.json, E47_bounds.json, E47_bins.csv, E47_runs.csv, data/scenarios/E47-design.json, E44_bounds.json (the lunar twins), table_E43_pairs.csv (the Moon comparison) | composed; every direction checked (H9 verdicts, the brake limit from the design, the Mars-over-Moon ratio, the per-conflict wait) |
| P2-H7-ABSTRACT-CLAUSE, P2-CONCLUSION-SAFETY-CLAUSE | B (types with and without violations) and M (states summed over the layouts) | composed: how many types had no violation, the type-9 exception named, the exhaustive check's verdict |
| P2-H9-ABSTRACT-CLAUSE, P2-CONCLUSION-MARS-CLAUSE | E47 (as above) | composed; the "times less" word is the rounded reciprocal of the Mars-over-Moon ratio, checked within 0.5 |
| P2-REFERENCES | `NOTES.md` | numbered list |
| TABLE:E43_cells, TABLE:E43_pairs, FIG:E43_density | C, P, C | built HTML |
| TABLE:E44 | B `types.{k}` (Table 6: n, driven, effective n, violations by kind, Bonferroni bound, near misses, min margin, deadlocks, blocked by fault, emergency-brake rate) | built HTML; pending with the E44 keys |
| TABLE:E47, TABLE:E47_link | results/E47_bounds.json `types.{k}` (Table 7, E44's columns at Mars gravity); results/E47_fit.json `road_coordination.delay_mean_h`, table_E43_pairs.csv (the Moon rows, so one quantity has one interval) and table_E43_cells.csv (Table 8: uncoordinated minus ATC by round trip and relay, its share of the ATC delay, conflicts referred and Earth wait) | built HTML; pending with the E47 keys |
| P2-ID-FIX-SENTENCE | `results/id_fix_evidence.json` (`runs`, `identical`, `ids_reused_pre/post`, rows' `items`, `exp`) | composed |
| P2-CHECK-FINDINGS-SENTENCE, P2-SHIELD-SLOPE-SENTENCE | `results/vv_phase5.json` rows S1 (c) type 9, S5 encounter deadlocks, S2 unholdable slope flagged (`passed`, `simulated`, `reference`, `unit`) | composed |

## Phase 6 (11 Nov 2026): position, clocks, lost link, integrity, propositions, Table 13

Filled by `paper/p2/phase6.py`, which `build_p2.py` calls at the end of `values()`. Same rules: numbers from files,
outcome-dependent wording composed with the direction chosen from the data, a `check()` behind every fixed phrase.
"H9'" and "H10'" are H9 and H10 of `paper/atc/PREREG6.md`; H9 and H10 without a prime stay those of `PREREG.md`.
Pending now: E50 at eight times the fleet and E50b. No longer used in the text but still filled: P2-H7-ABSTRACT-CLAUSE,
P2-CONCLUSION-SAFETY-CLAUSE and P2-CONCLUSION-MARS-CLAUSE (their short forms replace them, for the word limits);
P2-E50-X8-CLAUSE is used inside P2-E50-H10-SENTENCE. Abbreviations: S50 = `results/E50_summary.json`
(`errors.{mult}.{layer set}.{all,near,away}`, `violations`, `delay`, `h9`, `h10`, `design`, `seeds`); S51 =
`results/E51_clocks.json` (`rows` by class, scale and interval; `constants`; `holdover`; `h11`); S51b =
`results/E51b_clocks.json`; S54 = `results/E54_dtn.json` (`rows` by loss and protocol; `h14`; `parameters`); S55 =
`results/E55_integrity.json` (`integrity.sets.{val,test,ood}`, `consensus.cells`, `consensus_with_base_mast.cells`,
`h16`); S56 = `results/E56_integrity.json` (`test`, `ood`, `ood_recalibrated` by detector and rate; `dataset`;
`model`; `thresholds_from_validation`). PN = `lunarsim/atc/pnt.py` `DEFAULTS`; SF = `lunarsim/atc/safety.py` constants.

| Key | Source | Format |
|---|---|---|
| P2-E50-MODEL-SENTENCE, P2-E50-BUDGET | PN (drifts, ranging, fixes, navigation-service availability, `R95`); SF `D0_M` | composed (the four layers and the filter); m |
| P2-E50-DESIGN-SENTENCE | S50 `design`, `seeds`; cell run times and the 8x seed count typed from PREREG6 section 6 | composed; says whether 8x has finished |
| P2-E50-ERRORS-PARAGRAPH | S50 `errors` (p95 with CI, near and away, share of steps with the bound over budget, fix stops, hourly p95 of dead reckoning) at 1x and 4x | composed; checked: each layer lowers the p95, ranging holds the budget near the base only, fixes do not hold it away |
| P2-E50-H9-SENTENCE | S50 `h9.1`, `h9.4`, the 2030 variant | composed: verdict per clause of H9' as registered |
| P2-E50-MARGIN-PARAGRAPH | S50 `violations`, `delay` at 1x and 4x | composed |
| P2-E50-H10-SENTENCE | S50 `h10`, `delay` | composed: verdict per clause of H10'; the 4x reading ("no measurable cost", not a gain) is chosen from the sign, the interval and the road waiting; holds P2-E50-X8-CLAUSE |
| P2-E50-X8-CLAUSE, P2-E50-X8-SENTENCE | S50 `errors.8`, `delay.8`, `h10.gap_by_mult.8` | composed when the 8x seeds are in the file; until then the clause is empty and the sentence is "The eight-times cells of E50 have not finished." (awaited, see below) |
| P2-E50B-SENTENCE | `results/E50b_summary.json` (B-90b, landed 11 Nov 20:35): `metrics.delay_mean_h` (two arms, difference, bootstrap interval, paired t p, seeds higher and lower), `metrics.road_wait_h`, `metrics.violations`, `stops` (`engine_fix_stop_h_mean`, `perfect_run_fix_stop_h_mean`, `fixes_inside_single_lane_share`), `h10_primary_with_stop_time` (`ratio_to_perfect`, `note`), `design`, `seeds`, `e50_reproduced_all_seeds`; deliveries a month from `results/E50_runs.csv` | composed; checked: E50's seeds at 1x, the arm without stops reproduces E50's layered cell, the stop time of the position run is E50's, the file calls the comparison exploratory, the delay rose, road waiting did not change, the inserted stop time is a part of the position run's (a lower bound) |
| P2-PROP2-NUMBERS | S50 (the 95th percentile near the base with ranging as the bound), SF `A_ACC`; `lunarsim/atc/roads.py` (the speed in the margin is the leg's mean speed) | composed: the constant-speed premise of Proposition 2, a vehicle starting from rest, the stop line |
| P2-P6-AWAITED-LIMITATION, P2-P6-AWAITED-FUTURE | `build_p2.py` `AWAITED` and S50 (whether 8x is in the file) | composed: the list of analyses asked for by the referee round that have not been run (Sections 5.13, 7 and 6.5) |
| P2-E50-STOP-CLAUSE | S50 `errors.1.dr+ranging+fixes.fix_stop_h_per_month`; `h10.note` | hours a month; checked: the file says the stops are not in the delay |
| P2-E51-MODEL-SENTENCE, P2-E51-DESIGN-SENTENCE | S51 `constants`, `design` | composed |
| P2-E51-RESULTS-PARAGRAPH | S51 `rows` (lunar scale): conflicts by guard, largest error, one-way and two-way ranging error, failed resyncs | composed; the guard-sweep wording per guard is derived from the rows; checked: conflicts at every interval without a guard, none for the atomic clock with any guard |
| P2-E51-H11-SENTENCE | S51 `h11` (recomputed from the crystal rows) | composed |
| P2-E51-VARIANTS-SENTENCE | S51b `rows` (steering; mixed time scales) | composed; checked: steering helps the crystal at every interval and hurts the atomic clock at 1 min |
| P2-E54-MODEL-SENTENCE, P2-E54-DESIGN-SENTENCE | S54 `parameters`, `rows`, `blackout_days`, `seeds` | composed |
| P2-E54-RESULTS-PARAGRAPH | S54 `rows` at loss 0.25 (and 0.10, 0.40 for grants), `h14`, `reservations_per_seed` | composed; checked: custody cuts grant loss more than a hundredfold; the zero of stuck reservations under the rule is by construction (the runner sets it), stated as such |
| P2-E56-DATA-SENTENCE | `lunarsim/nn/faults.py` `FAULTS` (sizes in and out of distribution); S56 `dataset`, `ood_setting` | composed; checked: no seed and no pair in two splits |
| P2-E56-MODEL-SENTENCE | S56 `baselines`, `model`, `config`, `timing`; `results/E56_runs.csv` (the search rows) | composed; checked: parameter count is the sum over layers, the wider network's gain is under the search margin |
| P2-E56-DESIGN-SENTENCE, P2-E56-PAIR-DAYS | S56 `validation_fa_per_pair_day_at_threshold`, `false_alarm_definition`, `seeds`, `test.fault_free_pair_days_represented` | composed; count |
| P2-E56-RESULTS-PARAGRAPH | S56 `test` (recall, delay, realised false alarms; `h15_net_against.logreg` and `.cusum`; the per-hour rate) | composed; checked: order of overall recall, the network below the regression on jumps, every detector under 70 % on slow drifts |
| P2-E56-H15-PARAGRAPH | S56 `test.h15_net_against.chi2_step` and `.cusum`, `ood`, `ood_recalibrated` | composed: (a) to (d) as registered, each verdict from its interval |
| P2-E55-DESIGN-SENTENCE, P2-E55-RULE-PARAGRAPH | S55 `integrity` (the 3-of-5 rule and the single test at alpha 0.001; `k_of_n_false_alarm`; `detectable_error_check`); S56 for the two reference detectors | composed; checked: the single test's rate is within what independent Gaussian tests at 1 Hz give, the rule's rate is far above the independent-test value |
| P2-E55-H16-PARAGRAPH, P2-E55-MAST-SENTENCE | S55 `consensus.cells`, `consensus_with_base_mast.cells`, `h16` | composed: H16 not supported as written, the restatement exploratory; the mast variant by connected and agreement shares |
| P2-PROP1-NUMBERS | PN, SF; S50 hourly p95 of dead reckoning | composed: Proposition 1's distances and times |
| P2-PROP3-NUMBERS | SF (`G_MOON`, `MU_DEFAULT`, `B_MIN_FLAT`, `RHO_S`, `v_max_r2`); the measured teleoperation speed typed from [78] | composed; checked: the formula equals `v_max_r2`, the worked cell of note 04 E.3 is reproduced |
| P2-PROP4-NUMBERS | SF (`rss_dmin`, `B_MAX`, `D0_M`); `results/E44_bounds.json` type 9 | composed; checked: Table 2's gap at 15 km/h is reproduced, only type 9 has violations |
| P2-PROP5-NUMBERS | computed quantiles; S56 `thresholds_from_validation.chi2_step.day`, `ood`; S55 the rule's rate | composed; checked: note 03 E5's thresholds reproduced, the validation threshold within 5 % of the law's value |
| P2-PROP6-NUMBERS | S51 `constants`, `holdover`, `rows` | composed; checked: every cell whose largest clock error is within the guard has zero conflicts |
| P2-PROP7-NUMBERS | S55 `consensus.cells` | composed |
| P2-H7-ABSTRACT-SHORT, P2-CONCLUSION-SAFETY-SHORT | `results/E44_bounds.json`, `results/E45_modelcheck.json` | composed (shorter forms of the H7 clauses, for the word limits) |
| P2-P6-ABSTRACT-CLAUSE, P2-P6-INTRO-PARAGRAPH, P2-P6-CONCLUSION-CLAUSE | S50, S51, S55, S56 | composed; every direction checked in `facts()` |
| P2-P6-DISCUSSION-POSITION, P2-P6-DISCUSSION-TIME | S50, S51, S54, S55, S56; PN | composed: the reading of H10' and the recommendation on the detectors follow the verdicts |
| P2-P6-FAILED-SENTENCE | the verdicts above | composed: what failed, what the runs did not resolve, what is reported as an observation (H11) and what is withdrawn (H14, second clause) |
| TABLE:E50_errors, TABLE:E50_margin, FIG:E50_layers | S50 (Tables 9 and 10, Figure 2: inline SVG) | built HTML |
| TABLE:E51 | S51 `rows`, lunar scale (Table 11) | built HTML |
| TABLE:E56, FIG:E56_recall | S56 and the rule's rows from S55 (Table 12, Figure 3: inline SVG) | built HTML |
| P2-B97-PARAGRAPH, TABLE:B97 | `results/B97_realdata.json` `telemetry.rows` (spacecraft, residual, detector: `events`, `found`, `fp_runs`, `precision`, `channels`), `threshold_rule`; `results/B97_downloads.json` (the mirror's `checks_passed`) | composed and built HTML (Table 13); checked: the label file is byte-identical, thresholds from training data only, both accumulating detectors find more than the per-step test on the level residual |
| P2-FAMILY-STATS-SENTENCE, P2-FAMILY-H9-SENTENCE, P2-FAMILY-H10-SENTENCE, P2-FAMILY-H14-SENTENCE, P2-FAMILY-H15A-SENTENCE, P2-FAMILY-LIMITATION | `results/phase6_family.json` (`hypotheses.{H9,H10,H14,H15a}`: clause p values, `p_intersection_union`, `holm.p_adjusted`, seeds on the predicted side, sign-test counts; `alpha`; `pending`) | composed; checked: the Holm-adjusted values are recomputed from the unadjusted ones, H10's joined p is its largest clause p, and the file's differences equal those of E50, E54 and E56 |
| P2-CHECKS6-SENTENCE, P2-CHECKS6-OUTCOME | `results/vv_phase6.json` rows whose `papers` holds P2 (`technique`, `kind`, `passed`, `skipped`; the G1 `options off` row's `simulated` and `basis`), `commit`, `summary` (recounted) | composed |
| TABLE:PTA | every file above (Table 14: proved, tested, calculated from assumed inputs, observed, assumed, not yet tested; statuses read from the verdicts) | built HTML |

## Awaited results (referee round of 11 Nov 2026; decision A4)

`reports/referee_phase6_p2.md` asked for analyses that only BACKEND can run. None may print as a pending marker. Each
has an entry in `AWAITED` of `build_p2.py`: the results file, the task, the one plain sentence that stands where the
result will go, and the phrase for the list in Sections 5.13, 6.5 and 7. `awaited(name)` returns the sentence while the
file is absent. **When the file appears the build stops** and names the entry, so that the paper cannot say "not run"
beside a results file that exists; the pass that fills it writes a function that composes the sentence from the file,
with data checks, calls it where `awaited(name)` is called now, and removes the entry.

| Entry | Results file | Task | Where `awaited()` is called | What the sentence must then say |
|---|---|---|---|---|
| `overlaps` | `results/E50_overlaps.json` | B-102 | `phase6.py` `margin_paragraph` (5.9); also Table 10's note, Table 14's Proposition 2 row, 6.1 | the distribution of overlap durations (s) and of the along-track gap (m) when the second vehicle enters, with and without the margin; whether the margin changes them or only the count (decision B5) |
| `uphill` | `results/E45_uphill.json` | B-107 | `phase6.py` `prop4` (A.4); also 5.6, 6.1 (`e44_discussion_clause`), Table 14 | violations and smallest gaps on uphill grades of 5, 10, 15 and 17.2 degrees, Moon and Mars, with the rule as it is and with a slope term in the required gap |
| `fresh_seeds` | `results/E44_fresh_seeds.json` (the name is this paper's; B-108 says only "keep both in the file", so check it against BACKEND's report) | B-108 | `build_p2.py` `e44_results_paragraph` (5.6); also Table 6's dagger note, 3.5, Table 14 | the bounds of types 4, 5 and 6 on seeds never used, beside the present ones; then the dagger and "not confirmatory" go |
| `near_base` | `results/E50_near_base.json` | B-101 | `phase6.py` `h9_sentence` (5.9); also Table 9's note, Table 14, 6.1 | the 95th percentile with ranging under the four readings (two or more beacons in line of sight; one or more; within 1 km of the mast; within its radio range), the share of driving steps each covers, the side of the budget per seed; the verdict stays "depends on the reading" (decision B4) |
| E50 at eight times the fleet | `results/E50_summary.json` (`errors.8`, `delay.8`, `h10.gap_by_mult.8`) | BACKEND's 8x loop | `phase6.py` `x8_clause`, `x8_sentence` (they compose themselves when the keys appear) | as the functions say |
| E50b | `results/E50b_summary.json` | B-90b | landed; `phase6.py` `e50b_sentence` | filled |

Not in `AWAITED` because no task exists for them; the text says each is not run and Sections 6.5 and 7 list them: a
drop-and-retry baseline whose retry interval fits inside a grant's lifetime (M7); the lost-link ladder and
caution-speed entry inside the logistics model (M6); how often the position error is inside the vehicle's own bound,
per seed (S14; the referee read 97.1 % for one seed from `.cache`, which is not a results file); a sweep of the
hand-resolution time (S8); detectors at matched realised false-alarm rates with two observers, and the delay cost of
R9's false alarms (M1, S16).
