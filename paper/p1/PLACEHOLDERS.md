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

## Phase 6 additions (11 Nov 2026): the protocol, E53, E54, the propositions and the proved / tested / assumed table

Filled by `phase6_values`, `phase6_e53`, `phase6_e54`, `phase6_props` and `phase6_proved` in `build_p1.py`.

**Abbreviations.** SCH = `lunarsim/schemas/lrip-v0.1.json`. COD = `lunarsim/atc/lrip/codec.py` (`size_table()`,
`decode`) and `manifest.py` (`encode`, `can_do`). MAN = `data/atc/lrip/manifest-{small_rover,hopper}.json`. VEC =
`data/atc/lrip/conformance-v0.1.json`. E53 = `results/E53_bitrate.json` and `results/E53_table.csv` (row = `geometry`
+ `auth` + `position_hz` + `rovers`). E54 = `results/E54_dtn.json` (row = `loss` + `protocol`; `h14`; `parameters`).
E54L = `results/E54_ledger.json` (61 days; the ledger columns of the main E54 table are cut off by its 31-day window
and are never quoted). BND = `results/ATC_auction_bounds.json`. DEV = `paper/p1/dev_notes.json` (`prop4_inputs`,
`prop5_inputs`, `capability_filter_check`, each with its source).

**Formats.** kbit/s with 3 significant figures unless stated; B = bytes, integer; s = seconds. Every "SENTENCE" and
"CLAUSE" key is composed in the script, with its direction words (inside / above, fits / does not fit, supported /
not supported, excludes / includes zero) chosen from the data. E54 keys go through `fill()`: a missing
`E54_dtn.json` or `E54_ledger.json` gives a visible `[[PENDING E54]]` marker with `--allow-pending`.

**Data checks added (each stops the build when it fails).** The schema's header fields fill their bytes; E53 used
the codec's packet sizes; every message's fields fill whole bytes; a secured packet is content + 28 B; the signed
messages are exactly the three responses; an all-stop or landing-closure ALERT is signed; the schema has four
versioning rules and reads an unknown alert type as a hazard and an unknown mode as a fault; the manifest sizes
recomputed here equal E53's; owner and model as text explain part of the gap to the design note's estimate; the
matching rule accepts and refuses the example tasks as the text says; the conformance file holds every message three
times and our codec decodes every vector; the capability filter changed no summary value; E53 covers 5 to 80 rovers
at 0.1, 1 and 10 Hz; the per-rover load is the same in every row and is the sum over message types; events add less
than a thousandth; H13's verdict in the file follows its rule on the fleet-geometry rows; the airtime values equal
the file's; in the fleet geometry the busiest link carries the fleet sum; spread out it carries about half, reach
grows with fleet size and the mesh is cut before the channel fills at 20 rovers; E54's blackout lasts 14 days and
drop-and-retry's retry is longer than a grant's lifetime; H14's verdict follows its rule and the per-seed lost jobs
add up to the table's counts; the results file sets stuck reservations to zero under the rule; drop-and-retry loses
grants at about the per-hop loss rate and custody under 1 %; the transport does not change the base's age of
information and the rule cuts it; the ledger's loss under drop-and-retry does not depend on the lifetime, and a
lifetime longer than the longest Earth-down stretch loses none; at depth 1 no small instance fell below half the
optimum and at greater depth none below a third; the 2 x 2 example gives 1 + epsilon against 2; Proposition 3's mean
age and 99.9 % bound hold in a seeded simulation of its model; Proposition 4's transfer time is the engine's
coupling time and waiting for Earth costs more than ten times the hand-over; the fan-out grows with the autonomy
level; the position report's fields add up to 104 bits, the codec counts 13 B and 41 B, the golden packets have
those sizes, and 12 B hold fewer bits than the fields need; the engine's base-computer constants are those the text
types.

| Key | Meaning | Source | Format |
|---|---|---|---|
| P1-LRIP-N-MSG | number of message types | SCH `messages` | integer |
| P1-LRIP-SPP-B, P1-LRIP-HDR-B, P1-LRIP-SEC-B | Space Packet header, LRIP header, security header | SCH `framing.*.bytes` | B |
| P1-LRIP-MAC-B, P1-LRIP-MAC16-B, P1-LRIP-SIG-B | authentication code (narrow-band, broadband), signature | SCH `framing.trailer` | B |
| P1-LRIP-OVERHEAD-B, P1-LRIP-OVERHEAD-SIG-B | fixed overhead with the 8 B code / with a signature | sums of the above | B |
| P1-LRIP-HOP-LIMIT | relay hop limit | typed design input (note 03 C1), set in the script | integer |
| P1-LRIP-BUNDLE-B | Bundle Protocol overhead per bundle | SCH `framing.bundle_overhead_bytes` | B |
| P1-LRIP-PATTERN-SENTENCE | which messages are published, requests, responses | SCH `messages[].pattern` | composed |
| P1-LRIP-AWARD-B, P1-LRIP-GRANT-B, P1-LRIP-ALERT-SIGNED-B | signed award, signed grant, signed alert on the air | COD `size_table()` | B |
| P1-TABLE-LRIP-MSG | Table A2, the message catalogue | SCH + COD `size_table(283)` | HTML table |
| P1-LRIP-MANIFEST-EXAMPLE | the small-rover manifest, four blocks abbreviated | MAN | HTML listing; not written to values.json |
| P1-LRIP-MANIFEST-SIZE-SENTENCE | JSON, compact and on-air sizes; the note's estimate; the reason | MAN through COD; E53 `manifest_bytes` (`note03_compact`); the same encoder with owner and model as numbers | composed |
| P1-LRIP-CANDO-SENTENCE | the matching rule on example tasks | COD `can_do` on MAN | composed; outcomes checked |
| P1-LRIP-CAPFILTER-SENTENCE | the auction's filter with catalogue manifests | DEV `capability_filter_check` | composed |
| P1-LRIP-N-VECTORS, P1-LRIP-VECTORS-SENTENCE | golden packets, by profile and authentication | VEC `vectors` | integer; composed |
| P1-LRIP-INTRO-SENTENCE, P1-LRIP-ABSTRACT-SENTENCE, P1-LRIP-CONCLUSION-SENTENCE | H13's two loads against the budget, for 1, the abstract and 8 | E53 fleet rows, 20 rovers, auth on | composed |
| P1-E53-DRAWS | draws of rover positions per fleet size | E53 `draws` | integer |
| P1-E53-NB-KBPS, P1-E53-BB-KBPS | narrow-band and broadband channel rates | E53 `channels_kbps` | kbit/s 0 dp |
| P1-E53-ETA-SCHED, P1-E53-ETA-ALOHA | channel efficiencies used | E53 `eta` | 0.8; 2 dp |
| P1-E53-PER-ROVER-1HZ, P1-E53-PER-ROVER-1HZ-BPS, P1-E53-PER-ROVER-01HZ, P1-E53-PER-ROVER-10HZ | load per rover, auth on | E53 `per_rover_kbps` | kbit/s; B/s 1 dp |
| P1-E53-H13-SENTENCE | H13 as pre-registered, with the verdict | E53 `h13` and the fleet rows | composed |
| P1-E53-AUTH-SENTENCE | the same link without authentication | E53 fleet rows, auth off | composed |
| P1-E53-AIRTIME-SENTENCE | load as airtime, scheduled, random access, relayed once | E53 `h13`, `eta` | composed |
| P1-E53-NMAX-SENTENCE | fleet at which the scheduled 16 kbit/s channel is full | floor(eta x channel / per-rover load); fleet rows | composed |
| P1-E53-10HZ-SENTENCE | five rovers at 10 Hz; the broadband channel at 80 | E53 fleet rows | composed |
| P1-E53-SPREAD-SENTENCE | the spread geometry: share of the fleet sum, hops, reach | E53 spread rows, auth on | composed |
| P1-TABLE-E53-FLEET, P1-TABLE-E53-SPREAD | Tables 9 and 10 | E53 table | HTML tables |
| P1-E54-DESIGN-SENTENCE, P1-E54-LEDGER-DESIGN | E54's methods paragraph; the ledger replay | E54 `seeds`, `jobs_per_seed`, `reservations_per_seed`, `parameters`, `blackout_days`, `ledger_bytes`; E54L lifetimes | composed |
| P1-LRIP-LADDER-SENTENCE | the example manifest's lost-link times, checked against E54's | MAN `lost_link`; E54 `parameters` | composed |
| P1-E54-HOLD-S, P1-E54-RDV-H | hold time and time at the last link point in the lost-link ladder | E54 `parameters.t_hold_s`, `t_rdv_s` | s; h |
| P1-E54-H14-SENTENCE | lost jobs per seed, the paired difference, H14's first clause | E54 `h14`, rows at loss 0.25 | composed |
| P1-E54-STUCK-SENTENCE | H14's second clause (by construction), the blocked hours avoided, the verdict | E54 `h14`, rows at loss 0.25 | composed |
| P1-P6-FAMILY-SENTENCE, P1-E54-HOLM-SENTENCE, P1-E53-DRAWS-SENTENCE | the Phase 6 confirmatory family: which hypotheses Holm covers (4.8); H14's sign test and Holm p, with H10 and H15a (5.9); H13's draws on the predicted side (5.8) | `results/phase6_family.json` (`hypotheses.*.holm`, `H14.seeds_*`, `H13.clauses.*.draws_on_predicted_side`, `summary`), checked against E54 `h14` and the E53 rows | composed; pending if the file is missing |
| P1-E54-GRANTS-SENTENCE | grants lost by transport and loss | E54 rows | composed |
| P1-E54-AOI-SENTENCE, P1-E54-AOI-CLAUSE | the base's age of information; end-of-job reports | E54 rows at loss 0.25; `lost_link_*` | composed |
| P1-E54-LEDGER-SENTENCE | the Earth-bound ledger over 61 days | E54L | composed |
| P1-E54-ABSTRACT-CLAUSE | lost jobs with and without, for the abstract, 1 and 8 | E54 `h14` | composed |
| P1-TABLE-E54 | Table 11 | E54 rows | HTML table |
| P1-H6-SHORT-CLAUSE | team items delivered with and without cross-owner pairs (abstract) | P "H6 (reported): team items" team 0.10, loss 0.1 | composed |
| P1-BOUNDS-CBBA-MIN-D1, P1-BOUNDS-CBBA-MIN-DEEP, P1-BOUNDS-CBBA-DEPTHS | lowest share of the optimum at depth 1 and at the deeper depths; those depths | BND `cbba_lite_vs_optimum` | % 1 dp; list |
| P1-PROP2-ALOHA-N20, P1-PROP2-ALOHA-LIMIT, P1-PROP2-EXAMPLE-SENTENCE | (1 - 1/N)^(N-1) at N = 20; 1/e; Proposition 2 with E53's numbers | computed; E53 | 3 dp; composed |
| P1-TABLE-PROP3, P1-PROP3-EXAMPLE-SENTENCE, P1-PROP3-E54-SENTENCE | Table B1 and its reading; the link to E54 | Proposition 3's formulas with `lunarsim.atc.messages.HOP_LATENCY_S` and `LOSS_LEVELS`; E54 rows | HTML table; composed |
| P1-PROP4-EXAMPLE-SENTENCE, P1-PROP4-EARTH-SENTENCE, P1-PROP4-TOTAL-MIN, P1-PROP4-EARTH-H | Proposition 4 evaluated | DEV `prop4_inputs`; `lunarsim.engine.TEAM_SETUP_H` checked | composed; min 0 dp; h 0 dp |
| P1-TABLE-PROP5 | Table B2 | DEV `prop5_inputs` | HTML table |
| P1-TABLE-PROP6, P1-PROP6-BITS, P1-PROP6-NEED-BITS, P1-PROP6-JOINT-BITS, P1-PROP6-SPARE-BITS | Table B3; bits used, needed field by field, needed jointly, spare | SCH `messages[POSITION].fields`, `enums.nav_src` | HTML table; integers; 1 dp |
| P1-PROP6-CONTENT-B, P1-PROP6-SECURED-B, P1-PROP6-MAC16-B, P1-PROP6-UNSEC-B, P1-PROP6-CBOR-B | position report: content, with the 8 B code, with the 16 B code, unsecured, the golden CBOR packet | COD `size_table()`; VEC | B |
| P1-LEADER-N-FAIL-YEAR, P1-LEADER-ELECTION-H-YEAR | base-computer failures and hours of election a year under the engine's constants | `lunarsim.atc.regimes.DEFAULTS` (`base_mtbf_h`, `base_repair_h`, `reelect_h`) | 1 dp; h 1 dp |
| P1-TABLE-PROVED | Table 12, proved / tested / assumed | P, F, BND, E53, E54, DEV; verdict words from the data | HTML table (the site reads it from paper.html by its heading) |

**Typed inputs that stay typed in the Phase 6 text** (model inputs and literature values, each with its citation or
flag): the 60 s lifetime of a reservation grant and the 60 s contact-plan step of E54; CADRE's figures (10 s, 25 of
30 minutes, under 10 kg, 1 Mbit/s) [71, 72]; the teleoperation speeds [75] and VIPER's figures [76]; the supervision
ratios [78, 79]; DDS's 20 B header and 30 s announcements [68]; MQTT-SN's 2 or 4 B header [70]; MAVLink's 13 B
signature [66]; the guard share 0.2 of Proposition 2 (E53's eta = 0.8).

**Keys filled but not used in the text** (kept in `values.json` for the site): `P1-E53-H13-1HZ`, `P1-E53-H13-10HZ`,
`P1-E53-H13-VERDICT`, `P1-E53-NMAX-SCHED`, `P1-E53-AIR-SCHED`, `P1-E53-AIR-ALOHA`, `P1-E54-H14-VERDICT`,
`P1-LRIP-MANIFEST-CBOR-SMALL`, `P1-LRIP-MANIFEST-CBOR-HOPPER`, `P1-PROP5-RHO`; and `P1-BOUNDS-CBBA-MIN` (the minimum
over all depths, replaced in Section 3.11 by the per-depth keys).

## Referee revision (12 Nov 2026): reports/referee_phase6_p1.md and reports/referee_phase6_decisions.md

New sources. RAW = the raw run rows, read in full by `R.full(exp)` (`results/E4x_runs*.csv`), and ARCH = the rows
archived before PREREG change 5, read by `R.arch(exp)` (`results/archive/<exp>_runs*.pre-fixpoint-*.csv`). Paired
differences from them use `analyse_e40.paired` and `analyse_e40.boot` (the pairs table's own pairing and bootstrap,
20,000 resamples, seed 40), through `raw_pair`. DEV gains `learned_eval`, `lrip_v02`, `h13_design_note` and
`regression_check.pytest_collected`.

**Inputs that await a task (decision A4: no pending marker prints).**
- Task B-106 (rerun of Table 6's six cells and the guard runs on the current engine). Placeholder path:
  `results/ATC_learned_eval_rerun.json` (DEV `learned_eval.rerun_file`), with the structure of
  `ATC_learned_eval.json` (`ood`, `guards`). When it exists the build reads `ood` and `guards` from it and
  `P1-LEARNED-EVAL-LABEL`, `P1-LEARNED-EVAL-SENTENCE` and Table 6's caption change by themselves. Then also edit the
  typed sentences that say "have not been rerun": part4 5.11 ("figures from the first evaluation"), part5 6.5 and the
  Limitations entry "Table 6 and the guard runs predate the engine fixes".
- Task B-100 (LRIP v0.2: frame, time-scale identifier and covariance in POSITION). Placeholder path:
  `lunarsim/schemas/lrip-v0.2.json` (DEV `lrip_v02.schema_file`). When it exists the build STOPS with a message: fill
  `P1-LRIP-V02-SENTENCE` and the position-report sizes from it, and edit part5 6.5 and the Limitations entry "The
  protocol is counted and replayed".

**Data checks added (each stops the build).** The after side of Table C1 equals `table_E40_pairs.csv`; an
Earth-independent cell repeats exactly its 50 block-two runs; no row of E41 or E42 repeats another of its cell;
E41's default cell and E42's cell at team share 0.10 and loss 0.10 repeat E40's auction cell run for run; the H2
pairs rebuilt from RAW are the table's; H2 clears its margin under the year-clustered interval; the auction waits
less than the 80 % relay and than plan-ahead and is not distinguishable from the always-up relay, which equals the
marketplace run for run; alone, owner C delivers under 2 % of what it delivers pooled; the seed rule is read on every
E40 cell; the H6 rows are on `delivered_share`; same-owner pairs deliver about as many team items as fit the one
same-owner pair; meeting wait equals failed meetings times the timeout; a longer timeout buys no fewer failures;
H13's value is the fleet sum and the design note's figures agree with E53's; v0.1's POSITION has the nine named
fields and none for frame, datum, time scale or covariance; the replay generates a grant per award, more than twice
the recorded reservations; drop-and-retry gives up before the lease ends; five losses in a row account for more than
half of the baseline's lost awards at loss 0.25 and 0.40 and never for more than all; the sign-test p in the family
file is the one-sided exact p and Holm recomputed here reproduces the file's other two adjusted p; the heartbeat of
Proposition 4 is the schema's HELLO rate; the small instances use a toy score on a square.

| Key | Meaning | Source | Format |
|---|---|---|---|
| P1-FIXPOINT-SENTENCE (recomposed) | change 5: movement of the PRIMARY outcome (censored mean urgent wait) per experiment, and the before/after of H3a, H4 linear, H2, H6 | RAW against ARCH matched by cell, seed, start year | composed; "No verdict changed" only if the outcome column of Table C1 is equal before and after in every row |
| P1-TABLE-FIXPOINT | Table C1 (Appendix C): every tested comparison before and after change 5 | RAW, ARCH | HTML table |
| P1-N-RUNS-DISTINCT-MAX, P1-N-RUNS-REPEATS, P1-E40-N-DISTINCT, P1-RUNS-SENTENCE | rows against distinct runs. A row repeats another of its cell when seed and ten outcome columns (`OUTCOMES`) are equal to nine decimals; plus the 60 rows of E41 and E42 that rerun E40's auction cell | RAW | integers; composed |
| P1-H1-DELIV-DIFF, P1-H1-DELIV-DIFF-CI | delivered-only difference of the H1 pair itself (owners alone, full coverage, minus relay 1.0, block one) | P "H1 (reported): delivered-only urgent wait", v1 | h 1 dp; CI |
| P1-A-DELIV-MINUS-O-CI, P1-A-DELIV-N, P1-A-CENS-MINUS-O-30 | the other comparison (owners alone strict minus the marketplace): delivered-only interval, n, and its censored difference | P "H2 (not tested)" rows | CI 0 dp; integer; h 0 dp |
| P1-OWNER-C-ALONE-T, P1-OWNER-C-POOLED-T | tonnes of owner C's cargo delivered alone (full coverage) and pooled (relay 1.0), block one, 30 % | RAW `own_C_delivered_t` | t |
| P1-RELAY08-MINUS-O-CI (now the 95 % interval), P1-RELAY08-MINUS-O-CI90 | relay 0.8 minus marketplace | P `lo`/`hi`; `lo90`/`hi90` | CI |
| P1-H2-YEARCLUSTER-CI, P1-H2-N-YEARS, P1-H2-N-PER-YEAR, P1-H2-OLD-YARDSTICK-MET | H2's interval when whole start years are resampled (20,000 resamples, seed 40); start years; runs per year; whether the first-registered yardstick would have been met | RAW; F | CI; word; range; phrase chosen from data |
| P1-AUCTION-MINUS-RELAY08, P1-AUCTION-MINUS-RELAY08-CI, P1-AUCTION-MINUS-PLAN, P1-AUCTION-MINUS-PLAN-CI, P1-AUCTION-DIRECT-N | unregistered direct comparisons on block one, printed as how much shorter the auction's wait is | RAW via `raw_pair` | h 1 dp; CI; n |
| P1-H3A-RALLY-SENTENCE | the lost-link return as a confound of H3a | E41 cells and pairs ("C_AUCTION range perfect") | composed |
| P1-SEEDS-ADDED (recomposed), P1-SEEDS-N-OVER, P1-SEEDS-N-CELLS | the registered seed rule read on every E40 cell (bootstrap half-width of the cell mean over 10 % of the mean; valid runs) and on the confirmatory paired differences | RAW; P | composed; integers |
| P1-URGENT-ITEMS-SENTENCE | urgent items per run by load | RAW `atc_urgent_items` | composed |
| P1-CHECK-N-TESTS-NOW, P1-CHECK-TESTS-DATE | tests collected at this revision, and when | DEV `regression_check` | integer; date |
| P1-LEARNED-EVAL-LABEL, P1-LEARNED-EVAL-SENTENCE | where Table 6 and the guard runs come from | DEV `learned_eval`; the rerun file if present | composed |
| P1-H6-SHARE-SENTENCE, P1-H6-MEETINGS-SENTENCE, P1-H6-SHORT-CLAUSE, P1-H6-ABSTRACT-CLAUSE (recomposed) | H6 in kilograms and in items; the same-owner share as an input; the meeting results that follow from the handshake | P; RAW E42 (`delivered_items`, `p5_team_items*`); `lunarsim.atc.auction` (`TIMEOUT_H`, `RETRY_H`) | composed |
| P1-LRIP-V02-SENTENCE | what v0.1's POSITION serialises and lacks | SCH; DEV `lrip_v02` | composed |
| P1-LRIP-FRAME-B, P1-E53-FRAMING-SENTENCE | Proximity-1 framing per message and the loads with it | SCH `framing.proximity1_frame_bytes`; E53 `per_rover_at_1hz` | B; composed |
| P1-E53-N-TYPES, P1-E53-TYPES-SENTENCE | message types in E53's traffic model | E53 `per_rover_at_1hz` against SCH | integer; composed |
| P1-E53-H13-SENTENCE, P1-E53-DRAWS-SENTENCE, P1-LRIP-INTRO/ABSTRACT/CONCLUSION-SENTENCE (recomposed) | H13 as a design calculation | E53; DEV `h13_design_note` | composed |
| P1-E54-SHORT-CLAUSE | the abstract's and conclusion's E54 clause (the counts of P1-E54-ABSTRACT-CLAUSE in fewer words) | E54 rows at loss 0.25 | composed |
| P1-E54-COST-SENTENCE | what the replay leaves out of the lost-link return | E54 `lost_link_returns_per_seed`, `jobs_per_seed`, `link_shares` | composed |
| P1-E54-DESIGN/H14/STUCK/GRANTS/HOLM-SENTENCE, P1-E54-ABSTRACT-CLAUSE, P1-E54-AOI-CLAUSE, P1-TABLE-E54, P1-P6-FAMILY-SENTENCE (recomposed) | E54 with the baseline's limits, the p^5 arithmetic, the unconfirmed segments (decision B1), the one-sided p | E54; `phase6_family.json` | composed |
| P1-PROP4-TOTAL-H (replaces P1-PROP4-TOTAL-MIN) | hand-over on the Moon with the lease | DEV `prop4_inputs`; E54 `parameters.lease_s` | h 1 dp |
| P1-PROP6-DEFINITIONAL-SENTENCE | which fields' value counts are set by their bit width | SCH | composed |

**Withdrawn from the text, still filled for the site:** `P1-H1-UNDELIVERED-SHARE` (the 99.5 %; referee M3). The
site's /paper/ page reads it from `values.json`; remove the key here once the site no longer does.

## Second pass, part 1 (12 Nov 2026)

| Key | Meaning | Source | Format |
|---|---|---|---|
| P1-RELAY08-SHARE | availability of the relay case the text calls the 80 % relay (the site reads it) | `coverage` of the cell `B_EARTH_RELAY 0.8` in `results/E40_runs*.csv` (run_phase5's cell definition) | % 0 dp |
| P1-E53-DRIVING-SENTENCE | task B-103: the load calculation on driving steps only, and with STATUS and INTENT at 1 Hz | E53 `driving_split` | composed; "above / inside the budget" chosen from data; labelled a calculation |
| P1-LINKLAW-SENTENCE | task B-104: rover-to-rover rate at the worst hop, flat ground against curved Moon | `results/E48_sizing.json` `revision_b104.per_class.LTV1.worst_hop` | composed; labelled a calculation |

## Second pass, part 2 (12 Nov 2026): LRIP v0.2 (task B-100, landed)

The paper now describes v0.2. `P6` reads `lunarsim/schemas/lrip-v0.2.json`, `data/atc/lrip/conformance-v0.2.json`,
`data/atc/lrip/v0.2/manifest-*.json`, the key `lrip_v02` of `results/E53_bitrate.json` and the rows with
`framing == "lrip"` of `results/E53_table_v02.csv`; every E53 key, Tables 9, 10, A2 and B3 and Propositions 2 and 6
are filled from them. The v0.1 file and table stay loaded (`e53_v01`, `t53_v01`) for what was computed with v0.1
sizes: the design note's figures, `phase6_family.json`'s H13 values and the driving split of B-103; E54 also ran with
v0.1 sizes. The build no longer stops on the v0.2 schema; the earlier note under "Inputs that await a task" for
B-100 is superseded. Only B-106 is still awaited.

`P1-LRIP-V02-SENTENCE` (recomposed): what the v0.2 position report carries, the declaration in HELLO and the
manifest, the refusal rule, v0.1 bit-exact, no covariance. Checks added: only HELLO changes size from v0.1 to v0.2;
the codec at minor version 1 gives E53's v0.1 sizes; the 95 % code takes the six bits that were spare; HELLO's last
three fields are frame, datum and time scale since minor 2; E53's v0.2 traffic sends HELLO once per declaration
interval; the schema states the declaration rule and five versioning rules; the framed loads equal the file's
framing row; the traffic model's types are those the v0.2 block lists; H13 is on the same side with v0.2 sizes.

## Final pass, part 3 (12 Nov 2026): the learned-bid rerun (B-106) and the v0.2 driving split (B-110)

RR = `results/ATC_learned_eval_rerun.json` (rerun of 12 Nov 2026 on the corrected engine: `eval`, 30 seeds at 30 and
60 % load; `guards`, 10 seeds; `dates`; `rerun_note`). The build now requires it. `guards` and `eval` are read from
RR. `ood` is read from RR when it is a table (a dict); until then Table 6 prints the `ood` of the 27 Oct file with a
plain label, and `P1-OOD-LABEL-SENTENCE` says so; nothing needs editing when the table lands. The imitation
statistics (`P1-IMIT-*`) stay from `results/ATC_learned_eval.json`: they are a training record, not rerun. H4's
numbers (`P1-H4-*`) stay from E40's pairs table, the registered confirmatory test; RR's `eval` is reported beside it.

| Key | Meaning | Source | Format |
|---|---|---|---|
| P1-LEARNED-EVAL-SENTENCE (recomposed), P1-LEARNED-EVAL-LABEL | the rerun stated once, with the linear and network differences at 30 and 60 % | RR `eval.*.{linear,mlp}.vs_hand_h`, `vs_hand_share`, `dates.rerun`; DEV `learned_eval.file_date` | composed |
| P1-GUARD-TONNEDAYS-PCT | tonne-days change at 60 % in the guard runs | RR `guards.60.tonne_days_waiting` | % 0 dp |
| P1-GUARD-30-SENTENCE, P1-GUARD-30-CLAUSE | the guard runs at 30 %: urgent wait, bulk delay, all-cargo delay; every direction word chosen from the interval | RR `guards.30.*.linear_minus_hand` | composed |
| P1-IMIT-RERUN-SENTENCE | the 92.9 % is a training record; agreement with the marketplace on the evaluation seeds in the rerun | RR `eval.30.*.heldout_agreement`, `imitation.rerun_status` | composed; % 2 dp |
| P1-OOD-LABEL-SENTENCE | whether Table 6's cells were rerun | RR `ood` (table or not) | composed |
| P1-E53-DRIVING-SENTENCE (recomposed) | driving steps and the 1 Hz status and intent case with v0.2 sizes, with and without Proximity-1 frames | E53 `lrip_v02.driving_split` (B-110); the E54 link share from `driving_split.e54_link_shares_30_seeds` | composed |

## Part 4 (12 Nov 2026): the out-of-range cells rerun

RR `ood` is now a table and Table 6 reads it. `P1-OOD-SENTENCE` (new, composed): the five out-of-range cells, how
many intervals exclude zero (counted, with each cell's difference and interval), the cells whose interval includes
zero, the sixth cell ("year 2038") kept out of the count, and the statement that the 27 Oct file mixed engine
states. `P1-OOD-N-CELLS` and `P1-OOD-N-SIG` now count without "year 2038". The build STOPS if the "year 2038" cell
ever differs from the guard runs at 30 % load (`guards.30.atc_urgent_wait_mean_cens_h`: both means, the difference,
its interval and n), because the text says it repeats them.
