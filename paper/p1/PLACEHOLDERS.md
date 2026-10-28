# P1 placeholders (draft 1, 28 Oct 2026)

`build_p1.py` (not written yet; R-1 pattern, `paper/r1/build_r1.py`) fills every `{{P1-...}}` in `part1`-`part4`.
It must fail on any unfilled placeholder and on any nan/inf. 104 distinct keys.

**What is typed and what is a placeholder.** Results of this study are always placeholders. Model inputs
(vehicle specs, seeds, loss rates, timeouts, MTBF, the 10 % / 60 % / ±2 % pre-registered thresholds, CEM
population sizes) are typed with their provenance flag, as R-1 did. Numbers quoted from the literature and from our
earlier papers [40-42] are typed with the citation. If LEAD wants inputs drawn from files too, the candidates are
listed at the end.

**Abbreviations.** P = `results/table_E40_pairs.csv` (row = `comparison` + `load`; columns `mean`, `lo`, `hi`,
`lo90`, `hi90`, `n`, `b_mean`, `share_of_b`, `threshold_10pct_of_O`). R = `results/table_E40_regimes.csv` (row =
`load` + `label`). F = `results/E40_fit.json`. L = `results/ATC_learned_eval.json`.

**Formats.** h = hours, 1 decimal, with "&nbsp;h"; signed differences use `num(..., sign=True)` with the R-1 minus
sign; CI = "a to b&nbsp;h" with 1 decimal; % = 1 decimal with "&#8239;%"; t = tonnes, integer with thousands comma;
counts = integer. "ABS" keys print the absolute value (the sentence carries the direction).

| Key | Meaning | Source | Format |
|---|---|---|---|
| P1-LOAD-MAIN | the middle load | constant of the design, "30&#8239;%" from R load values | % 0 dp |
| P1-LOSS-MAIN | message loss of the on-Moon regimes in E40 | `run_phase5.LOSS` | 0.10 |
| P1-N-REGIMES | regimes in E40 incl. owners-alone full coverage | count of distinct R `label` without " hopper_refuel" | word if < 20 |
| P1-N-RUNS-ALL | simulated years in E40+E41+E42 (main runs only) | rows of `results/E4[012]_runs*.csv` | integer |
| P1-E40-N-CELLS / -N-RUNS | E40 cells / runs | `run_phase5.py list --exp E40`; rows of `E40_runs*.csv` | integer |
| P1-E41-N-CELLS / -N-RUNS | same for E41 | PENDING E41 | integer |
| P1-E42-N-CELLS / -N-RUNS | same for E42 | PENDING E42 | integer |
| P1-UTIL-FLEET-30 | whole-fleet utilisation, marketplace, 30 % | R `30`/`O_ORACLE`, `utilisation` | % 1 dp |
| P1-CARGO-UTIL-30 | FLEX+Eagle busy share, marketplace, 30 % | R `30`/`O_ORACLE`, `p5_cargo_util` | % 0 dp |
| P1-VIS-MIN / -MAX | base Earth visibility over the simulated start years | earth_link v1/v3 BASE any_part per start year (2028-2031, 2032, 2035, 2038, 2041, 2044) | % 1 dp |
| P1-H2-N-LOWVIS-YEARS | start years with visibility < 60 % | count of P rows "H2: ..., <year>" | word |
| P1-H2-LOWVIS-YEARS | their list | same rows | "2029, 2031, ..." |
| P1-H2-STRICT-MINUS-O (+ -CI) | B strict minus O, pooled years | P "H2: B_EARTH strict - O_ORACLE, pooled years", 30 | h, CI |
| P1-H2-STRICT-OVER-O-RATIO | B strict mean / O mean, 30 % | R `B_EARTH strict` / `O_ORACLE`, `atc_urgent_wait_mean_cens_h` | 1 dp |
| P1-H2-N | n of that row | P `n` | integer |
| P1-H2-MARGIN | 10 % of O's mean | P `threshold_10pct_of_O` (pooled row) | h 1 dp |
| P1-H2-YEAR-MIN / -MAX | smallest / largest per-year mean difference | P H2 per-year rows, `mean` | h 0 dp |
| P1-H2-PHOLM | Holm-adjusted p | F `holm_30pct.adjusted_p.H2` | "&lt; 0.001" style |
| P1-H2-OLD-YARDSTICK-HALF | half of A strict minus O | P "A_EARTH strict - O_ORACLE (original H2 yardstick, not tested)" `mean`/2 | h 0 dp |
| P1-B-STRICT-URGENT-30 / -10 | B strict mean urgent wait | R | h 1 dp |
| P1-O-URGENT-30 | marketplace mean urgent wait | R | h 1 dp |
| P1-PLAN-MINUS-O (+ -CI) | plan_ahead minus O, 30 % | P "B_EARTH plan_ahead - O_ORACLE" | h, CI |
| P1-RELAY08-MINUS-O (+ -CI) | relay 0.8 minus O, 30 % | P "B_EARTH_RELAY 0.8 - O_ORACLE" | h, CI |
| P1-RELAY08-URGENT-30 | relay 0.8 mean | R | h 1 dp |
| P1-B-STRICT-BACKLOG-30 / P1-O-BACKLOG-30 | backlog at end of a blackout | R `atc_backlog_end_blackout_t_mean` | t 1 dp |
| P1-O-WITHIN24-30 / P1-B-STRICT-WITHIN24-30 | share of urgent items within 24 h | R `atc_urgent_within24_share` | % 0 dp |
| P1-H1-DIFF-30 (+ -CI, -N-30) | B relay 1.0 minus A full coverage, 30 % | P "H1: B_EARTH_RELAY 1.0 - A_EARTH full coverage", 30 | h 0 dp, CI |
| P1-H1-PHOLM | Holm p | F `holm_30pct.adjusted_p.H1` | p |
| P1-H1-CAPACITY-SHARE | share of the H1 gap due to capacity | PENDING E42 own-teams cells; definition to agree with BACKEND (item 3 of LEAD's 197a574 message) | % 0 dp |
| P1-A-URGENT-RANGE-30 | min-max over A regimes, mean urgent wait | R, labels starting `A_` | "1,217 to 1,258&nbsp;h" |
| P1-A-T-RANGE-30 / P1-POOLED-T-RANGE-30 | delivered tonnes, A vs pooled regimes | R `delivered_kg`/1000 | t range |
| P1-A-BACKLOG-T-30 | year-end backlog, A strict | R `backlog_kg`/1000 | t 0 dp |
| P1-A-DELIV-MINUS-O-30 | delivered-only A strict minus O | P "...delivered-only urgent wait (not tested...)" | h 0 dp |
| P1-POOLED-SPREAD-10 | max-min of pooled regimes except B strict, 10 % | R load 10 | h 1 dp |
| P1-LIN-URGENT-30 / P1-LEADER-URGENT-30 | means | R | h 1 dp |
| P1-H3A-DIFF / -PCT / -PCT-ABS / -CI90 / -N | auction minus O | P "H3a: C_AUCTION - O_ORACLE (TOST +-10 % of O)", `mean`, `share_of_b`, `lo90`/`hi90`, `n` | h, % |
| P1-LEADER-MINUS-O (+ -CI) | C_LEADER minus O | NOT IN P YET: ask BACKEND to add the row (value +0.45 [-0.29, 1.14] was quoted in the message) | h, CI |
| P1-H4-LIN-DIFF-30/-10, -PCT-30/-10, -PCT-30-ABS, -CI-30/-10 | LIN minus auction | P "H4: C_LEARNED_LIN - C_AUCTION" 30 and 10 | h, %, CI |
| P1-H4-MLP-DIFF-30/-10, -CI-30/-10 | MLP minus auction | P "H4: C_LEARNED_MLP - C_AUCTION" | h, CI |
| P1-H4-N | n | P `n` | integer |
| P1-H4-LIN-PHOLM | Holm p | F `holm_30pct.adjusted_p.H4_lin` (key name to check) | p |
| P1-GUARD-TONNEDAYS-PCT | tonne-days change, linear vs hand, 60 % guard | L `guards.60.tonne_days_waiting` (linear/hand - 1) | % 0 dp |
| P1-OOD-N-CELLS / -N-SIG | OOD cells run / CI excluding 0 | L `ood` | word |
| P1-TABLE-OOD | Table 6 | L `ood` | HTML table |
| P1-LIN-WEIGHTS-SENTENCE | plain-language weights | `data/policies/atc_bid_linear_v1.json` | sentence built in script |
| P1-IMIT-AGREE | hand agrees with oracle, held out | L `imitation.hand_agreement_val` | % 1 dp |
| P1-IMIT-DISAGREE-30 / -60 | "318 of 318" / "404 of 404" | L `imitation.finding` or the policy files' training record (structured field to add) | "n of n" |
| P1-IMIT-N-ROUNDS / -N-ROWS | groups / rows collected | L `imitation.groups` / `rows` | integer |
| P1-TRAIN-WALL-H | CEM wall time, both models | L `policies.*.cem.wall_s` sum /3600 | h 1 dp |
| P1-HOPPER-O-DIFF (+ -CI) | O hopper_refuel minus O | NOT IN P YET (quoted +0.40 [-0.35, 1.19]); ask BACKEND for the row | h, CI |
| P1-MESH-LOS-25-2TO5 | LOS share 2.5-2.5 m at 2-5 km | `results/ATC_mesh.json` | % 2 dp |
| P1-MESH-MAST-MAX-KM | farthest direct mast LOS | `results/ATC_mesh.json` | km |
| P1-MESH-MAX-HOPS-5KM | max hops to mast, rovers, 5 km | `results/ATC_mesh.json` | integer |
| P1-MESH-SMALL-ISOLATED | small-robot points that never reach the mast | `results/ATC_mesh.json` | integer |
| P1-RALLY-OFF-SMOKE-T / -ON-SMOKE-T | C_LEADER delivered t, rally off / on (development run) | B-72 report quotes 58 t / 1,487 t; check whether `results/ATC_regimes_smoke.json` holds the rally-off run, else replace with the E41 rally-off cell | t |
| P1-BOUNDS-N / -SSI-MAX / -CBBA-MIN | small-instance checks | `results/ATC_auction_bounds.json` | integer, 3 dp, % 1 dp |
| P1-CHECK-N-ROWS / -N-TESTS | regression rows and pytest count | B-7x reports (20 rows; 547 tests at B-74, rising): take from the final run log at submission | integer |
| P1-SEEDS-ADDED | sentence on the seed-adding rule | F `n_per_cell` vs 30/80 | sentence |
| P1-RUNTIME-RANGE / P1-PEAK-MB | run time per year, peak memory | `run_s` column of the run CSVs; peak from reports | "0.4-66&nbsp;s", MB |
| P1-TABLE-REGIMES | Table 5 | R | HTML table |
| P1-FIG-H2-YEARS | Figure 1 | P H2 rows + visibility per year | figure include |
| P1-E41-LOSS/DEPTH/RANGE-SENTENCE | E41 results | PENDING E41 | prose, to be rewritten by hand with placeholders |
| P1-H6-SHARE/MEETINGS-SENTENCE | E42 results | PENDING E42 | prose, as above |

**Typed inputs that could become placeholders** (if LEAD wants them file-driven): k = 0.857 / 2.806 / 6.22 (scenario
files); vehicle table (`lunarsim/atc/vehicles-p5.json`); 1,537 parameters and 13 weights (policy files); CEM
population and generations (L `policies.*.cem`); MTBF 2,000 h, repair 24 h, re-election 0.5 h, t_hand 2 h, retry
3 min, 10 ms per hop (`lunarsim/atc/regimes.py` and `messages.py` defaults); 2,421 mesh points (`ATC_mesh.json`).
The R-1 numbers typed in the introduction (59 %, ~16-day windows, ~11-day gaps, 1.2 km) should be checked against
`paper/r1/values.json`.
