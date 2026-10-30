# P1 placeholders (draft 1, 28 Oct 2026)

`build_p1.py` (not written yet; R-1 pattern, `paper/r1/build_r1.py`) fills every `{{P1-...}}` in `part1`-`part5`.
It must fail on any unfilled placeholder and on any nan/inf.

**What is typed and what is a placeholder** (LEAD, 28 Oct). Results of this study are always placeholders. Inputs
that a file holds (the load factors k, the policies' feature, weight and parameter counts, the CEM settings) are
placeholders read from that file. Other model inputs (vehicle specs, seeds, loss rates, timeouts, MTBF, retry and
hop times, the 10 % / 60 % / ±2 % pre-registered thresholds) are typed with their provenance flag, as R-1 does.
Numbers quoted from the literature and from our earlier papers [40-42] are typed with the citation.

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
| P1-H1-UNDELIVERED-SHARE | share of the censored H1 gap that lies in items owners alone had not delivered by year end: 1 - delivered-only/censored paired difference | P "H1 (reported): delivered-only urgent wait" and the H1 row, v1 | % 0 dp |
| P1-H1-POOL-DIFF, P1-H1-POOL-DIFF-CI, P1-H1-POOL-SHARE | single-robot jobs pooled across owners with the pooled dispatcher: auction same-owner teams minus A_EARTH full coverage, v1, team 0.10, loss 0.10 | P "H1 dispatch part: ..."; F `hypotheses.H1.split_30.share_dispatch` | h 0 dp, CI, % 0 dp |
| P1-H1-TEAM-DIFF, P1-H1-TEAM-DIFF-CI, P1-H1-TEAM-SHARE | lifts by pairs of different owners' rovers: auction cross-owner minus auction same-owner teams | P "H1 capacity part: ..."; F `split_30.share_capacity` | h 0 dp, CI, % 0 dp |
| P1-H1-OWNER-A-DIFF, P1-H1-OWNER-B-DIFF, P1-H1-OWNER-C-DIFF | pooling's cut in mean urgent wait per owner (B relay 1.0 minus A full coverage, v1) | P "H1 (reported): owner A/B/C" | h 0 dp |
| P1-A-URGENT-RANGE-30 | min-max over A regimes, mean urgent wait | R, labels starting `A_` | "1,217 to 1,258&nbsp;h" |
| P1-A-T-RANGE-30 / P1-POOLED-T-RANGE-30 | delivered tonnes, A vs pooled regimes | R `delivered_kg`/1000 | t range |
| P1-A-BACKLOG-T-30 | year-end backlog, A full coverage (the H1 comparison's owners-alone cell) | R `backlog_kg`/1000 | t 0 dp |
| P1-BOTTOM-MAX-NAME | the regime(s) at the top of the on-Moon group at 30 % (within 0.05 h of the maximum) | R, block-one means | names |
| P1-O-URGENT-30-ALL | the marketplace's mean over the 80 matched runs of the H2 comparison (5.3) | P `H2_pooled` `b_mean` | h |
| P1-H1-60-SENTENCE | H1's registered 60 % half | P `H1` at load 60 (`mean`, CI, `n`, `p`) | composed: supported if hi < 0; outside the Holm family |
| P1-H4-60-SENTENCE | H4's registered 60 % half, linear and network | P `H4_LIN`, `H4_MLP` at load 60 | composed: cut / lengthened / includes zero |
| P1-GROUPS-60-SENTENCE | the three regime groups at 60 % | R at load 60 (block-one means for Earth-independent cells) | composed: same order, or which Earth-losing regime falls inside the on-Moon range |
| P1-A-DELIV-MINUS-O-30 | delivered-only A strict minus O | P "...delivered-only urgent wait (not tested...)" | h 0 dp |
| P1-POOLED-SPREAD-10 | max-min of pooled regimes except B strict, 10 % | R load 10 | h 1 dp |
| P1-LIN-URGENT-30 / P1-LEADER-URGENT-30 | means | R | h 1 dp |
| P1-H3A-DIFF / -PCT / -PCT-ABS / -CI90 / -N | auction minus O | P "H3a: C_AUCTION - O_ORACLE (TOST +-10 % of O)", `mean`, `share_of_b`, `lo90`/`hi90`, `n` | h, % |
| P1-LEADER-MINUS-O (+ -CI) | C_LEADER minus O, 30 % | P "C_LEADER - O_ORACLE" (row being added by BACKEND; match the exact label when it lands) | h, CI |
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
| P1-K-10 / -30 / -60 | demand factors of the three loads | `results/ATC_p5_load.json` `calibration` (or the scenario files `data/scenarios/p5/p5-3eq-L{10,30,60}-T10.json`; assert they agree) | 3 dp as stored |
| P1-N-FEATURES | inputs of the learned bid | `data/policies/atc_bid_linear_v1.json` `obs.names` length; assert equal in the MLP file | word or integer |
| P1-LIN-N-WEIGHTS | linear model's weights | linear policy file `layers` (count weights, excluding any fixed scale) | integer |
| P1-MLP-N-PARAMS | network parameters | `data/policies/atc_bid_v1.json` `layers` (sum of weights and biases; expect 1,537) | integer with comma |
| P1-MLP-HIDDEN | hidden units per layer | MLP file `layers` shapes | integer |
| P1-CEM-LIN-GENS / -LIN-POP | linear CEM generations / population | L `policies.linear.cem.generations` / `population` | integer |
| P1-CEM-MLP-GENS / -MLP-POP / -MLP-N-SEARCHED | MLP CEM generations / population / parameters searched | L `policies.mlp.cem.generations` / `population` / `parameters_searched` | integer |
| P1-CEM-N-TRAIN-SEEDS / -N-TUNE-SEEDS | seeds per candidate / per generation's selection | L `policies.*.cem.fitness` and `selection` strings list the seeds; prefer structured fields if BACKEND adds them | word |
| P1-HOPPER-O-DIFF (+ -CI) | O hopper_refuel minus O, 30 % | P hopper row (being added by BACKEND; match the exact label). BACKEND also adds C_AUCTION - O and learned - O rows; H3a keeps its own row | h, CI |
| P1-H6-ABSTRACT-CLAUSE | one clause for the abstract, 6.1 and the conclusion: team items delivered with and without cross-owner pairs at team share 0.10, and whether the commit step reduced failed meetings (same rule as P1-H6-MEETINGS-SENTENCE) | P "H6_team_items" row at team 0.10, loss 0.1; F `meetings` | sentence built in script |
| P1-MESH-LOS-25-2TO5 | LOS share 2.5-2.5 m at 2-5 km | `results/ATC_mesh.json` | % 2 dp |
| P1-MESH-MAST-MAX-KM | farthest direct mast LOS | `results/ATC_mesh.json` | km |
| P1-MESH-MAX-HOPS-5KM | max hops to mast, rovers, 5 km | `results/ATC_mesh.json` | integer |
| P1-MESH-SMALL-ISOLATED | small-robot points that never reach the mast | `results/ATC_mesh.json` | integer |
| P1-E41-RALLY-ON-URGENT / -OFF-URGENT | auction mean urgent wait, rally on (E41 base cell) / off | PENDING E41: `results/E41_runs*.csv`, cells "C_AUCTION loss 0.1" and "C_AUCTION rally off" (match labels) | h 1 dp |
| P1-E41-RALLY-ON-T / -OFF-T | auction delivered tonnes, same cells | PENDING E41, `delivered_kg`/1000 | t 0 dp |
| P1-RALLY-OFF-DEV-T / -ON-DEV-T | C_LEADER delivered t without / with the rule in the B-72 development run (development-run note only) | B-72 report: 58 t / 1,487 t. If `results/ATC_regimes_smoke.json` does not hold the rally-off run, the script reads them from a small checked-in note file rather than typing them | t 0 dp |
| P1-BOUNDS-N / -SSI-MAX / -CBBA-MIN | small-instance checks | `results/ATC_auction_bounds.json` | integer, 3 dp, % 1 dp |
| P1-CHECK-N-ROWS / -N-TESTS | regression rows and pytest count | B-7x reports (20 rows; 547 tests at B-74, rising): take from the final run log at submission | integer |
| P1-SEEDS-ADDED | sentence on the seed-adding rule | F `n_per_cell` vs 30/80 | sentence |
| P1-FIXPOINT-SENTENCE | PREREG change 5 before/after (4.6) | `results/{E40,E42,E41}_fixpoint_before_after.json` from `experiments/phase5/compare_rerun.py --exp ...` (`n_old`, `n_matched`, `primary_mean_change_h`, `primary_mean_abs_change_h`, `primary_max_abs_change_h`) | composed; pending until all three reruns have landed |
| P1-RUNTIME-RANGE / P1-PEAK-MB | run time per year, peak memory | `run_s` column of the run CSVs; peak from reports | "0.4-66&nbsp;s", MB |
| P1-TABLE-REGIMES | Table 5 | R | HTML table |
| P1-FIG-H2-YEARS | Figure 1 | P H2 rows + visibility per year | figure include |
| P1-E41-LOSS-SENTENCE / -DEPTH-SENTENCE / -RANGE-SENTENCE | Section 5.5 paragraphs | `results/table_E41_pairs.csv`, `table_E41_cells.csv`, `E41_fit.json` from `experiments/phase5/analyse_e41_pairs.py` (paired differences against each regime's loss-0 and default cells and against E40's O_ORACLE on block v1; H3b and H3c decisions; slope per point of loss; crossing loss) | composed; every direction word chosen from the interval; pending until each cell has 30 runs |
| P1-E41-DEPTH-CLAUSE | the depth-5 sentence in 5.8 | `E41_fit.json` `H3b.supported` | composed |
| P1-CHECKS-SENTENCE, P1-FAILED-CHECKS-SENTENCE, P1-PAIRING-SENTENCE | the phase-5 checks (B-79) in 3.11, 5.9 and 4.5 | `results/vv_phase5.json` rows whose `papers` holds P1; D10 rows' `detail.vrf` for the pairing | composed |
| P1-E41-REPLICATION-SENTENCE | end of 5.5 | `E41_fit.json` `replication_e40` (E41 "C_AUCTION loss 0.1" minus E40 C_AUCTION 30 % v1 on the same seeds) | composed: "reproduced every run exactly" only when the difference is exactly 0 |
| P1-H6-SHARE/MEETINGS-SENTENCE | E42 results | PENDING E42 | prose, as above |

**Typed inputs that stay typed** (with flags, as R-1): MTBF 2,000 h, repair 24 h, re-election 0.5 h, t_hand 2 h,
retry 3 min, 10 ms per hop (`lunarsim/atc/regimes.py`, `messages.py`); the vehicle table (`lunarsim/atc/vehicles-p5.json`);
2,421 mesh points. The R-1 numbers typed in the introduction (59 %, ~16-day windows, ~11-day gaps, 1.2 km) should be
checked against `paper/r1/values.json`.

**Full key list** (122 keys, generated from `part1`-`part5`; grouped rows above such as "(+ -CI)" and "/ -60" expand to these; `build_p1.py` should assert this list equals the keys it fills):

`P1-A-BACKLOG-T-30`, `P1-A-DELIV-MINUS-O-30`, `P1-A-T-RANGE-30`, `P1-A-URGENT-RANGE-30`, `P1-B-STRICT-BACKLOG-30`, `P1-B-STRICT-URGENT-10`, `P1-B-STRICT-URGENT-30`, `P1-B-STRICT-WITHIN24-30`, `P1-BOUNDS-CBBA-MIN`, `P1-BOUNDS-N`, `P1-BOUNDS-SSI-MAX`, `P1-CARGO-UTIL-30`, `P1-CEM-LIN-GENS`, `P1-CEM-LIN-POP`, `P1-CEM-MLP-GENS`, `P1-CEM-MLP-N-SEARCHED`, `P1-CEM-MLP-POP`, `P1-CEM-N-TRAIN-SEEDS`, `P1-CEM-N-TUNE-SEEDS`, `P1-CHECK-N-ROWS`, `P1-CHECK-N-TESTS`, `P1-E40-N-CELLS`, `P1-E40-N-RUNS`, `P1-E41-DEPTH-SENTENCE`, `P1-E41-LOSS-SENTENCE`, `P1-E41-N-CELLS`, `P1-E41-N-RUNS`, `P1-E41-RALLY-OFF-T`, `P1-E41-RALLY-OFF-URGENT`, `P1-E41-RALLY-ON-T`, `P1-E41-RALLY-ON-URGENT`, `P1-E41-RANGE-SENTENCE`, `P1-E42-N-CELLS`, `P1-E42-N-RUNS`, `P1-FIG-H2-YEARS`, `P1-GUARD-TONNEDAYS-PCT`, `P1-H1-UNDELIVERED-SHARE`, `P1-H1-DIFF-30`, `P1-H1-DIFF-30-CI`, `P1-H1-N-30`, `P1-H1-PHOLM`, `P1-H2-LOWVIS-YEARS`, `P1-H2-MARGIN`, `P1-H2-N`, `P1-H2-N-LOWVIS-YEARS`, `P1-H2-OLD-YARDSTICK-HALF`, `P1-H2-PHOLM`, `P1-H2-STRICT-MINUS-O`, `P1-H2-STRICT-MINUS-O-CI`, `P1-H2-STRICT-OVER-O-RATIO`, `P1-H2-YEAR-MAX`, `P1-H2-YEAR-MIN`, `P1-H3A-CI90`, `P1-H3A-DIFF`, `P1-H3A-N`, `P1-H3A-PCT`, `P1-H3A-PCT-ABS`, `P1-H4-LIN-CI-10`, `P1-H4-LIN-CI-30`, `P1-H4-LIN-DIFF-10`, `P1-H4-LIN-DIFF-30`, `P1-H4-LIN-PCT-10`, `P1-H4-LIN-PCT-30`, `P1-H4-LIN-PCT-30-ABS`, `P1-H4-LIN-PHOLM`, `P1-H4-MLP-CI-10`, `P1-H4-MLP-CI-30`, `P1-H4-MLP-DIFF-10`, `P1-H4-MLP-DIFF-30`, `P1-H4-N`, `P1-H6-MEETINGS-SENTENCE`, `P1-H6-SHARE-SENTENCE`, `P1-HOPPER-O-CI`, `P1-HOPPER-O-DIFF`, `P1-IMIT-AGREE`, `P1-IMIT-DISAGREE-30`, `P1-IMIT-DISAGREE-60`, `P1-IMIT-N-ROUNDS`, `P1-IMIT-N-ROWS`, `P1-K-10`, `P1-K-30`, `P1-K-60`, `P1-LEADER-MINUS-O`, `P1-LEADER-MINUS-O-CI`, `P1-LEADER-URGENT-30`, `P1-LIN-N-WEIGHTS`, `P1-LIN-URGENT-30`, `P1-LIN-WEIGHTS-SENTENCE`, `P1-LOAD-MAIN`, `P1-LOSS-MAIN`, `P1-MESH-LOS-25-2TO5`, `P1-MESH-MAST-MAX-KM`, `P1-MESH-MAX-HOPS-5KM`, `P1-MESH-SMALL-ISOLATED`, `P1-MLP-HIDDEN`, `P1-MLP-N-PARAMS`, `P1-N-FEATURES`, `P1-N-REGIMES`, `P1-N-RUNS-ALL`, `P1-O-BACKLOG-30`, `P1-O-URGENT-30`, `P1-O-WITHIN24-30`, `P1-OOD-N-CELLS`, `P1-OOD-N-SIG`, `P1-PEAK-MB`, `P1-PLAN-MINUS-O`, `P1-PLAN-MINUS-O-CI`, `P1-POOLED-SPREAD-10`, `P1-POOLED-T-RANGE-30`, `P1-RALLY-OFF-DEV-T`, `P1-RALLY-ON-DEV-T`, `P1-RELAY08-MINUS-O`, `P1-RELAY08-MINUS-O-CI`, `P1-RELAY08-URGENT-30`, `P1-RUNTIME-RANGE`, `P1-SEEDS-ADDED`, `P1-TABLE-OOD`, `P1-TABLE-REGIMES`, `P1-TRAIN-WALL-H`, `P1-UTIL-FLEET-30`, `P1-VIS-MAX`, `P1-VIS-MIN`

| P1-H3A-SENTENCE | table_E40_pairs.csv H3a v1-only row: tost_equivalent / CI sign | composed by build_p1.py: "it did" / "the interval was too wide to show it" / "it fell short"; never typed |
| P1-H3A-VERDICT | same row | composed sentence stating equivalence shown or not, with the direction if the CI excludes 0 |
| P1-H3A-ABSTRACT-CLAUSE | abstract: "matched the full-information marketplace" when the 95 % CI includes zero, else "was better/worse ... by X %" | composed by build_p1.py from the H3a v1 row |
| P1-H3A-INTRO-CLAUSE | introduction: the auction against the marketplace, with the 90 % interval in percent when it includes zero | composed, same row |
| P1-H4-LIGHT-CLAUSE | introduction: the light-load learning outcome ("helped there too" only if the 95 % CI excludes zero) | composed from the H4 linear row at 10 % |
| P1-REFERENCES | reference list from NOTES.md `[n]` lines (the research-note grade in parentheses is dropped) | HTML list; not a key of the 122 |

**Table markers.** `<!-- TABLE:pairs -->` (Table 7, the confirmatory family with Holm's p) sits after Table 6 in 5.6;
`<!-- TABLE:e42 -->` (Table 8, every E42 cell) ends 5.7. `build_p1.py` fails if either marker is missing.

**Key list after the 28 Oct edits:** the 122 above plus `P1-H3A-ABSTRACT-CLAUSE`, `P1-H3A-INTRO-CLAUSE`, `P1-H4-LIGHT-CLAUSE`
and `P1-REFERENCES`; `P1-H3A-PCT-ABS` is no longer used in the text (the build notes it) and may be dropped.
| P1-ID-FIX-SENTENCE | `results/id_fix_evidence.json` (`runs`, `identical`, `ids_reused_pre/post`, rows' `items`, `exp`) | composed |
| P1-CHECK-FINDINGS-SENTENCE | `results/vv_phase5.json` rows L5 (`passed`, `simulated`, `sub`) | composed |
