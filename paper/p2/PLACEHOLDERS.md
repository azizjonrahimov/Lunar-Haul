# P2 placeholders (draft 0, 28 Oct 2026)

`build_p2.py` fills every `{{P2-...}}` in `part1`-`part5` and fails on any unfilled placeholder and on any nan/inf.
Keys whose experiment has not run (E44, E45, E47, the 8x cells of E43) are filled with a visible `[[PENDING ...]]`
marker only with `--allow-pending`. Families are written with `{m}` (fleet multiple 1, 2, 4, 8), `{y}` (start year
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
| P2-CHECKS-SENTENCE, P2-FAILED-CHECKS-SENTENCE, P2-SHARED-CHECK-LIMITATION | the verification page's phase-5 checks (B-79); `lunarsim/atc/roads.py` calling the shared `safety_check()` (B-78) | pending |
| P2-E44-N-ENCOUNTERS | B = `results/E44_bounds.json` (`tools/atc/run_e44.py summarize`): sum of `types.{k}.n_driven` | count |
| P2-E44-DESIGN-SENTENCE, P2-E44-DESIGN-SENTENCE-SHORT | B `near_miss_definition`, type 1 `n`/`n_driven`; the design n per type typed from change 6 (`E44_N`); the defect count from `results/E44_defects.json` (change 8) | composed (methods: design, bounds, weights, outcome classes, the stopped first run) |
| P2-E44-INTRO-CLAUSE, P2-E44-RESULTS-PARAGRAPH, P2-E44-DISCUSSION-CLAUSE, P2-E44-COMPARISON-CLAUSE | B `types.{k}` (`n`, `n_driven`, `n_eff`, `violations`, `violations_by_kind`, `bound`, `bonferroni_bound`, `near_misses`, `min_margin_m`, `outcomes`, `emergency_brake_rate`); `E44_defects.json` `defects_found_in_main_run` (first-run counts, re-runs after each fix, the type-9 finding) | composed; pending until all 12 types reach their designed n; checked: outcome classes sum to n, every rerun after a fix clean, the type-9 record is the dead stop |
| P2-E44-COMPUTE-SENTENCE | B `types.{k}.run_time_s`, `peak_rss_mb`; batch sizes typed from `tools/atc/run_e44.py` `BATCH` | hours; MB |
| P2-DEADLOCK-SCOPE-CLAUSE | `results/ATC_roads_rings.json` (`merge_m`; `by_share.{s}.rings`, `ring_lengths_m`, `raw_sample_cycles` for 0.05, 0.15, 0.4; BACKEND, B-78) | composed: the zero count is a property of the logistics model (unbounded bays); the ring question is undetermined from the samples; checked: counts match their length lists |
| P2-E45-N-NODES | `lunarsim/atc/modelcheck.py` `X` (the road cells) | count |
| P2-E45-DESIGN-SENTENCE, P2-E45-INTRO-CLAUSE, P2-E45-RESULTS-PARAGRAPH, P2-E45-DISCUSSION-CLAUSE, P2-E45-COMPUTE-SENTENCE | M = `results/E45_modelcheck.json` (`tools/atc/run_e45.py`): `models.{A,B,C,D}` (`states`, `transitions`, `K_max_steps_to_goal`, `seconds`, `peak_mb_traced`, the zero counts), `mutations.{R3_exit,R5_entry,R7_hold}` (`deadlock_states`, `cannot_reach_goal`, `livelock_sccs`, `deadlock_trace_length`, `violating_states`, `violation_kinds`, `counterexample_length`), `step_s`, `cell_m` | composed; checked: the four layouts and three mutations are the named ones, every layout passes, every mutation is caught. The results paragraph ends with the development counterexamples from `results/E45_development.json` (`items[].kind`; checked: the four known kinds) |
| P2-E47-DESIGN-SENTENCE, P2-E47-GEOMETRY-SENTENCE, P2-E47-INTRO-CLAUSE, P2-E47-RESULTS-PARAGRAPH, P2-E47-DISCUSSION-CLAUSE, P2-E47-LIMITATION-SENTENCE | E47 files (B-82) | pending |
| P2-H7-ABSTRACT-CLAUSE, P2-CONCLUSION-SAFETY-CLAUSE | B (types with and without violations) and M (states summed over the layouts) | composed: how many types had no violation, the type-9 exception named, the exhaustive check's verdict |
| P2-H9-ABSTRACT-CLAUSE, P2-CONCLUSION-MARS-CLAUSE | E47 | composed; pending |
| P2-REFERENCES | `NOTES.md` | numbered list |
| TABLE:E43_cells, TABLE:E43_pairs, FIG:E43_density | C, P, C | built HTML |
| TABLE:E44 | B `types.{k}` (Table 6: n, driven, effective n, violations by kind, Bonferroni bound, near misses, min margin, deadlocks, blocked by fault, emergency-brake rate) | built HTML; pending with the E44 keys |
