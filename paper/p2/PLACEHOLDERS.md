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
| P2-N-CHANGES-WORD, P2-X8-HORIZON-SENTENCE, P2-WAKE-SENTENCE | D `design_changes`; the B-77 report | composed; pending until the hold decision (PREREG issue 5) |
| P2-CHECKS-SENTENCE, P2-FAILED-CHECKS-SENTENCE, P2-SHARED-CHECK-LIMITATION | the verification page's phase-5 checks (B-79); `lunarsim/atc/roads.py` calling the shared `safety_check()` (B-78) | pending |
| P2-E44-N-ENCOUNTERS, P2-E44-DESIGN-SENTENCE, P2-E44-DESIGN-SENTENCE-SHORT, P2-E44-INTRO-CLAUSE, P2-E44-RESULTS-PARAGRAPH, P2-E44-DISCUSSION-CLAUSE, P2-E44-COMPARISON-CLAUSE, P2-E44-COMPUTE-SENTENCE | `results/E44_encounters.csv`, `E44_bounds.json` (B-78) | pending |
| P2-E45-N-NODES, P2-E45-DESIGN-SENTENCE, P2-E45-INTRO-CLAUSE, P2-E45-RESULTS-PARAGRAPH, P2-E45-DISCUSSION-CLAUSE, P2-E45-COMPUTE-SENTENCE | `results/E45_modelcheck.json` (B-78) | pending |
| P2-E47-DESIGN-SENTENCE, P2-E47-GEOMETRY-SENTENCE, P2-E47-INTRO-CLAUSE, P2-E47-RESULTS-PARAGRAPH, P2-E47-DISCUSSION-CLAUSE, P2-E47-LIMITATION-SENTENCE | E47 files (B-82) | pending |
| P2-H7-ABSTRACT-CLAUSE, P2-H9-ABSTRACT-CLAUSE, P2-CONCLUSION-SAFETY-CLAUSE, P2-CONCLUSION-MARS-CLAUSE | E44/E45 and E47 | composed; pending |
| P2-REFERENCES | `NOTES.md` | numbered list |
| TABLE:E43_cells, TABLE:E43_pairs, TABLE:E44, FIG:E43_density | C, P, E44, C | built HTML |
