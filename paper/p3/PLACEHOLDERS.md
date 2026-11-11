# P3 placeholders (draft 3 after referee round 2, 30 Oct 2026; E48 link and traffic correction of 11 Nov 2026)

`build_p3.py` fills every `{{P3-...}}` in `part1`-`part5` and fails on any unfilled placeholder and on any nan/inf.
Keys whose experiment has not run (E46, E48, the B-79 checks) are filled with a visible `[[PENDING ...]]` marker only
with `--allow-pending`. There are no key families in P3: every key is listed below by name.

**What is typed and what is a placeholder.** Results of this study are always placeholders. Model inputs that a file
holds are placeholders read from that file: the vehicle catalogue (`lunarsim/atc/vehicles-p5.json`, Table 2 and the
capacity plateau), the scenario's fleet and load factor (`data/scenarios/p5/p5-3eq-L30-T10.json`), the mesh summary
(`results/ATC_mesh.json`), the Assumed defaults of the code (`lunarsim/atc/regimes.py` DEFAULTS, `messages.py`,
`radio.py`, `auction.py`), the learned policies' sizes (`data/policies/*.json`) and the dated changes of
`paper/atc/PREREG.md`. Numbers quoted from the literature (Sections 1, 2, 3.2 for the landers, 3.3 for the link
physics) are typed with the citation and, where the research note grades them, its confidence. Facts the notes do
not hold are `[[CHECK: ...]]` in the text, counted by the build and listed in NOTES.md.

**Proposed experiment files (not yet promised by BACKEND).** B-81 names `results/E48_sizing.json`. B-76 REVISED names
no file; the build reads `results/E46_cells.csv` (one row per cell: `label`, `rule` in none / second / posted (and
`first` if a first-price cell is added), `split` in 3eq / 3uneq, `k`, `q`, `n`, and the metrics below),
`results/E46_pairs.csv` (`comparison`, `metric`, `n`, `mean`, `lo`, `hi`, `b_mean`, `share_of_b`) and
`results/E46_fit.json` (`n_rows`, `n_cells`, `run_s_mean`, `cpu_h`, `design` {`owners`, `splits`, `rules`, `k_levels`,
`q_levels`, `seeds`}, `H5` {per split: `clause1` {`tested`, `supported`, `gain`, `lo`, `hi`}, `clause2` {`tested`, `supported`, `diff_mean`, `diff_lo`, `diff_hi`}, `clause3` {`tested`, `supported`, `min_upper`, `min_lower`}; the build recomputes `supported` from the intervals by the rules of change 7},
`max_gain` {rule: {`owner`, `k`, `gain`, `lo`, `hi`, `system_cost_h`, `lo_cost`, `hi_cost`}}, `audits` {rule: {"0", "5",
"20": {`recovered_share`, `net_gain`}}}, `short_cells` [{`label`, `have`, `n`}]). The E48 schema the build expects:
`laptop` {`processor`, `benchmark`, `benchmark_name`}; `flight` {`processor`, `benchmark`, `factor`, `factor_range`,
`memory_mb`, `source`}; `targets` {`robots`: 20, `safety_hz`: 10, `link_kbps_20_robots`: 16, `bytes_per_s_per_robot`: 100,
`market_mb_per_day`: 1}; `classes` {LTV1, CARGO, SMALL, HOPPER, BASE: {`cpu_safety_check_us` {`median`, `p99`, `n`},
`cpu_auction_round_ms` {`median`, `p99`, `n`}, `peak_memory_mb`, `power_w` {`value`, `flag`}, `link` {`antenna_m`,
`freq_ghz`, `tx_power_w`, `worst_hop_kbps`, `latency_budget_ms`, `reachable_share`}}}; `messages` {`bytes_per_type`
{type: bytes}, `per_robot_hour` {"1", "4", "8"}, `bytes_per_robot_hour` {"1", "4", "8"}}; `ledger_mb_per_year` {"1",
"4", "8"}; `failover` {`mtbf_levels_h` [...], `by_mtbf` {level: {`down_share`, `no_leader_share`, `reelect_s`, `merges`,
`jobs_assigned_twice`}}}; `runs` {`n`, `multiples`, `run_s_mean`, `cpu_h`}. A file that exists but lacks a field makes
that key pending with the field named.

**E48 schema additions of 11 Nov 2026 (B-89, PREREG change 11).** The build now also reads, per class, `link` {`peer_antenna_m`, `law`,
`worst_hop_m`, `loss_db_worst_hop`, `mutual_horizon_m`, `beyond_horizon_at_worst_hop`, `worst_hop_kbps_if_visible`, `longest_hop_m`,
`longest_hop_kbps`, `latency_hops`, `reachable_share_free_space`, `reachable_note`; BASE: `uplink_from_small_kbps_at_worst_hop`} and
`link_free_space_upper_bound` {`worst_hop_kbps`, `law`}; `messages.secured` {`bytes_per_type` {`mac8`, `mac16`, `map`, `header`},
`per_robot_hour`, `bytes_per_robot_hour` {multiple: {`mac8`, `mac16`}}}; `airtime` {`robots`, `channel_kbps`, `rows` [{`sizes`, `hops`,
`access`, `eta`, `channel_kbps_needed`, `fits_16_kbps`}], `mean_hops_to_base`}; `h10` {`link_kbps_needed_20_robots`,
`link_kbps_needed_20_robots_secured_mac8`, `_mac16`, `carries_20_robots_1hz_on_16_kbps` {`scheduled`, `slotted_aloha`, `hops`}};
`revision` {`date`, `two_ray_in_the_mesh.e40_month` {`epochs`, `scenario`, `variants.default` {`hop_histogram`,
`robot_epochs_cut_off_share`, `robot_epochs_with_base_up`}}}; and from
`data/scenarios/E48-design.json` `radio` {`antenna_gain_dbi`, `bandwidth_mhz`, `noise_figure_db`, `implementation_margin_db`, `worst_hop_m`}.
The link is no longer one yes or no in the build: the processor and the memory keep "fits" / "does not fit", and the link's wording is
chosen from three airtime rows (scheduled at the measured hops, slotted random access at the measured hops, scheduled at two hops).
Checks added with these keys: "beyond the horizon" = worst hop > mutual horizon = sqrt(2 R h1) + sqrt(2 R h2), and a zero rate only
there; the loss at the worst hop equals 40 log d - 20 log(h1 h2) beyond 4 pi h1 h2 / lambda; free space is an upper bound on every
class's rate; the mast-reach share is equal under both laws and its note names line of sight, 5 km, 16 kbit/s and a 10 dB margin; the
secured load = bytes per robot-hour x robots x 8 / 3600 and equals the h10 block; every airtime row = load x hops / eta and its fits
flag agrees with the target; the mean hop count equals the month's hop histogram and is below 1.1 (the "one hop" wording), with the
same verdict at exactly one hop; the small classes' free-space rate is more than 100 times their flat-ground rate (Section 7). The
mesh-link survival shares of `revision.two_ray_in_the_mesh.mesh_pairs` are not quoted anywhere in P3; one check reads them (for a class
beyond its horizon, `by_class.*.16k_m10_smooth_horizon.survive_share` < `16k_m10.survive_share`) to cover the note of Table 6 that on the
terrain a pair can be in line of sight beyond the smooth-Moon horizon.

**Abbreviations.** CAT = the catalogue; SCN = the scenario; M = `results/ATC_mesh.json`; REG = `regimes.DEFAULTS`;
E46 = the three E46 files; E48 = `results/E48_sizing.json`; PR = `paper/atc/PREREG.md`.

| Key | Source | Format |
|---|---|---|
| P3-N-CLASSES, P3-N-CLASSES-FLEET, P3-N-FLEET, P3-N-OWNERS | CAT `classes` count; SCN `fleet` (distinct classes, vehicles, owners) | words |
| P3-K30 | SCN `p5.k` | 3 decimals |
| P3-CLV1-PAYLOAD-KG, P3-CLV1-RANGE-KM | CAT `LTV1_CLV1.params.capacity_kg`, `range_km_per_charge` (checked equal to Pegasus's payload) | kg; km |
| P3-CAP-MAX-SINGLE-KG, P3-CAP-MAX-PAIR-KG, P3-CAP-FLEET-SUM-KG | CAT `capacity_kg` over the fleet's classes: the largest, the two largest with `can_team_lift`, the sum over the fleet's vehicles | kg |
| P3-N-COALITION-RUNS | removed from the text in draft 2 (the coalition sentence of 3.5 now states the seven coalitions and five runs per seed in words); the lead removes it from the build | &ndash; |
| P3-MESH-N-POINTS | M `n_points` | count |
| P3-MESH-LOS-25-0TO05, P3-MESH-LOS-25-2TO5, P3-MESH-LOS-10-2TO5 | M `los_by_distance_band` `2.5-2.5` `0-0.5 km`, `2-5 km`, `1.0-1.0` `2-5 km`, `los_0m` (checked: falls with distance and height) | % |
| P3-MESH-MAST-DIRECT-SHARE, P3-MESH-MAST-DIRECT-MAX-KM | M `mast_direct.rover_2.5m`: (n_points &minus; `n_no_direct_los`) / n_points; the last distance band whose `within_km.n` grows (checked against the band share; checked 10-30 %) | %; km |
| P3-MESH-COMPONENTS-2KM, P3-MESH-REACH-1HOP, P3-MESH-REACH-2HOPS, P3-MESH-MAX-HOPS-5KM, P3-MESH-MEDIAN-HOPS-5KM | M `connectivity.rover_2.5m` at 2 km and at the radio range (`reach_base_share`, `max_hops`, `median_hops`; checked: one component, nobody never reaches) | word; %; words |
| P3-MESH-SMALL-ISOLATED, P3-MESH-SMALL-MAX-HOPS | M `isolated.small_1.0m.n`; `connectivity.small_1.0m` at the range, `max_hops` | words |
| P3-RADIO-RANGE-KM | `radio.DEFAULT_D_MAX_M` (checked: one of M's ranges) | km |
| P3-HOP-LATENCY-MS, P3-MEAN-BURST | `messages.HOP_LATENCY_S`, `MEAN_BURST` | ms; count |
| P3-BASE-MTBF-H, P3-BASE-REPAIR-H | REG `base_mtbf_h`, `base_repair_h` | h; h |
| P3-REELECT-MIN | no longer in the text since draft 3 (referee round 2, finding 24: the re-election delay is 0.5 h everywhere else, so 3.4 and Table 3 type 0.5&nbsp;h, Assumed, the value of REG `reelect_h` and of `E48-design.json` `failover.reelect_h`); the lead removes the key from the build or keeps it unused | &ndash; |
| P3-TIMEOUT-H | `auction.TIMEOUT_H` | h |
| P3-LIN-N-WEIGHTS, P3-MLP-N-PARAMS | as build_p1.py: the linear policy's `layers[0].w` length (checked: one weight per observation name) and the sum of `w` and `b` sizes over the network's `layers` (`data/policies/atc_bid_linear_v1.json`, `atc_bid_v1.json`) | count |
| P3-CHANGES-SENTENCE | PR: `### Change N` headings after change 1 that name E46, E48, H5, H10 or first-price; since draft 2 the "none" case must be empty, because 4.6 types the closing sentence "No other choice was made after looking at data." | composed |
| P3-CHECKS-SENTENCE, P3-FAILED-CHECKS-SENTENCE | `results/vv_phase5.json` rows whose `papers` holds P3: counts by `kind` and `technique`, `commit`; outcomes from `passed`, `skipped`, `bias_flag`, `error`/`rel_error` against `tolerance`; the summary is recounted from the rows and every passed flag recomputed | composed; pending until a B-79 batch tags P3 |
| P3-E48-DESIGN-SENTENCE, P3-E48-COMPUTE-SENTENCE | E48 `runs` | composed; pending |
| P3-E48-RESULTS-CPU, P3-E48-RESULTS-MESSAGES, P3-E48-RESULTS-LINK, P3-E48-RESULTS-FAILOVER | E48 `classes`, `messages`, `ledger_mb_per_year`, `failover`, `flight`, `laptop`; since 11 Nov P3-E48-RESULTS-LINK reads `classes.*.link` (`worst_hop_kbps`, or for a class with `beyond_horizon_at_worst_hop` the words "beyond the ... horizon" with `mutual_horizon_m` and `longest_hop_kbps`; `latency_budget_ms`, `latency_hops`, `reachable_share`) and `classes.*.link_free_space_upper_bound.worst_hop_kbps`, and P3-E48-RESULTS-MESSAGES states the unsecured load "at the sources" without a verdict against the link target | composed paragraphs; checked: no job assigned twice; a zero rate is never printed |
| P3-H10-VERDICT-SENTENCE | E48: scaled p99 safety-check time x factor x `safety_hz` as a share of one core at the worst class; scaled peak memory against `flight.memory_mb`; `h10.market_mb_per_day` against `targets.market_mb_per_day`; since 11 Nov the link is `messages.secured.bytes_per_robot_hour."1".mac8` x `robots` x 8 / 3600 (the load at the sources) and the three `airtime.rows` for it (scheduled and slotted at the measured hops, scheduled at two hops; `channel_kbps_needed` against `targets.link_kbps_20_robots`), with `h10.carries_20_robots_1hz_on_16_kbps.hops` | composed: "holds on every count" / "holds for the processor, the memory and the market's messages, and for the link only when the base schedules the channel and the reports travel one hop" / "does not hold on every count (...)", and "within" / "above" per case, from the data |
| P3-E48-ABSTRACT-CLAUSE, P3-E48-INTRO-CLAUSE, P3-E48-DISCUSSION-CLAUSE, P3-E48-COMPARISON-CLAUSE, P3-E48-CONCLUSION-CLAUSE, P3-E48-LIMITATION-SENTENCE | the same scaled values; "fits" / "does not fit" from the data for the processor and the memory; since 11 Nov the link claim is the qualified one of P3-H10-VERDICT-SENTENCE (the same three `airtime.rows`; the abstract and the long form print the three rates, the conclusion the condition only); the comparison with the 13.8 kB/s convoy controller of [25], at `messages.bytes_per_robot_hour."1"` and at `messages.secured.bytes_per_robot_hour."1".mac8` | composed |
| P3-E48-STATUS-SENTENCE | E48: the fields of Section 4.2 that are missing from the file | composed |
| P3-E46-N-RUNS, P3-E46-DESIGN-SENTENCE, P3-E46-COMPUTE-SENTENCE | E46 fit `n_rows`, `n_cells`, `design`, `run_s_mean`, `cpu_h` | count; composed; pending |
| P3-E46-RESULTS-RULES | E46 cells per rule and split (k = 1, q = 0): `efficiency_loss_pct`, `operator_budget_musd` (surplus / deficit from the sign), `settled_earth_musd`, `open_end_musd`; checked: one allocation (efficiency loss equal across rules; the rule-minus-rule pairs on `delay_h` and `delivered` exactly zero; budget zero under none and posted) | composed |
| P3-E46-RESULTS-IR | E46 cells `ir_violations` (honest cells and all cells); pairs `coalition {S} - alone, owner {o} ({split})` on `profit_usd` (`b_mean` = alone profit); fit `H5.{split}.clause3.rows` | composed |
| P3-E46-RESULTS-MANIP, P3-E46-RESULTS-AUDITS | E46 fit `max_gain.{rule}.{split}` (owner, k, gain with CI, `system_cost_h` with CI, `system_cost_usd`); `audits.{rule}.{split}.{q}` (`recovered_share`, `net_gain`) | composed |
| P3-H5-VERDICT-SENTENCE, P3-H5-ABSTRACT-CLAUSE, P3-H5-INTRO-CLAUSE | E46 fit `H5.clause1..3` (`tested`, `supported`, and the intervals `lo`, `diff_mean`/`diff_hi`, `min_upper`/`min_lower`) against the rules of Section 4.1, with `supported` checked against the intervals | composed: supported / not supported / not tested, from the data |
| P3-E46-ABSTRACT-CLAUSE, P3-E46-INTRO-CLAUSE, P3-E46-DISCUSSION-CLAUSE, P3-E46-COMPARISON-CLAUSE, P3-E46-IMPLICATION-CLAUSE, P3-E46-CONCLUSION-CLAUSE | the rules with zero IR violations in both splits; the budget's sign per rule; the largest gain; the audits' net gain at 20 %; the smallest owner (C, 3uneq, posted) against Kondor [39] | composed; pending |
| P3-E46-STATUS-SENTENCE | E46 fit `short_cells` | composed |
| P3-E46-POSTHOC-SENTENCE | E46 fit `exploratory.allocation_fixed_gain.{rule}.{split}` (`gain`, `lo`, `hi`) and `exploratory.reallocation_term.{split}` (`mean`, `sd`); made after the runs, labelled so in the text | composed; pending until BACKEND adds the block |
| P3-E46-TARIFF-SENTENCE | E46 fit `tariff_usd_per_tkm.{split}`, `audit_penalty_multiple` (copies of the design file) | composed |
| P3-E46-RESERVE-SENTENCE (5.5, right after P3-E46-RESULTS-RULES; moved out of 3.5 in draft 3, referee round 2 finding 5, so that 3.5 keeps only the rule's definition) | E46 run parts (`results/E46_parts/`, each job's `alts`): the share of jobs with at least one competing free vehicle at the dispatch instant and the share priced by the tariff reserve, per split | composed |
| P3-E46-SURPLUS-SENTENCE (6.1, right after P3-E46-TRANSFERS-CLAUSE and before the typed mirror-image sentence) | E46 cells: the none-rule profits per owner and split; the pairs' alone means (`b_mean` of the coalition-minus-alone rows); fit `H5.{split}.clause3.rows` for ABC (each owner's Shapley payoff) and the transfers: the pooling gain over alone per split, each owner's share of it under no payments and under the Shapley sharing, and the transfer as the difference between the two shares; direction from the data (draft 3: owner C's share is the largest under the Shapley sharing and larger still under no payments) | composed; direction from the data |
| P3-E46-LOSS-SENTENCE (4.2, E46 paragraph; since draft 3 the only full statement of the perfect radio, 3.3 keeping one short mention) | `data/scenarios/E46-design.json` `message_loss.value` and `.flag` | composed; design input |
| P3-E46-BUDGET-SENTENCE (5.5, after P3-E46-RESULTS-RULES) | E46 cells `operator_budget_musd` per rule and split with a bootstrap interval over seeds; the first-price budget stated as tariff receipts less true carrier cost | composed |
| P3-E46-TRANSFERS-SENTENCE (5.5, after P3-E46-BUDGET-SENTENCE) | E46 fit `H5.{split}.clause3.rows` and the posted-price cells: each owner's Shapley payoff less its posted-price cash, per split, and the settlement on Earth including the transfers | composed |
| P3-E46-VS-NONE-SENTENCE (5.6, after P3-E46-RESULTS-IR) | E46 cells: each owner's profit under first, second and posted price minus its profit under none, paired by seed, with intervals (needs per-seed profits from the run parts or a new pairs row `rule - none, owner {o} ({split})`) | composed |
| P3-H5-POWER-CLAUSE (5.7, after P3-H5-VERDICT-SENTENCE) | E46 fit `exploratory.allocation_fixed_gain.first.{split}` (`gain`, `lo`, `hi`), labelled post hoc; states that the registered measure includes the deviator's own delay | composed |
| P3-E46-TRANSFERS-CLAUSE (6.1) | as P3-E46-TRANSFERS-SENTENCE: the transfer amounts per split, one clause | composed |
| P3-E46-VS-NONE-CLAUSE (6.1) | as P3-E46-VS-NONE-SENTENCE: whether any owner is worse off under a paid rule than under none, one clause | composed; direction from the data |
| P3-H5-POWER-ABSTRACT-CLAUSE (abstract, after P3-H5-ABSTRACT-CLAUSE), P3-H5-POWER-CONCLUSION-CLAUSE (conclusion, after P3-E46-CONCLUSION-CLAUSE) | as P3-H5-POWER-CLAUSE, one short clause each (about 20 words; the abstract's typed part is 171 words and the conclusion's 126) | composed |
| P3-E48-REFERENCE-SENTENCE (4.2, E48 paragraph) | `data/scenarios/E48-design.json` `flight.processor`, `flight.benchmark`, `flight.source`, `laptop.processor`, `laptop.benchmark`, `laptop.benchmark_note`, `flight.factor`, `flight.factor_range` | composed; design input, Assumed |
| P3-E48-MTBF-SENTENCE (4.2, E48 paragraph; since draft 3 the only statement of the repair time and the re-election delay in that paragraph, the typed duplicates having been removed) | `data/scenarios/E48-design.json` `failover.mtbf_levels_h`, `failover.repair_h`, `failover.reelect_h`, `failover.seeds`, `failover.regime` | composed; design input, Assumed |
| P3-E48-HORIZONS-SENTENCE (4.2, E48 paragraph; since draft 3 the only statement of the horizons and the extrapolation, the typed duplicate having been removed) | `data/scenarios/E48-design.json` `runs.horizon_days` per multiple and `runs.seeds` | composed; design input |
| P3-E48-TRAFFIC-NOTE (5.2, after the bytes-per-robot-hour sentence) | E48 `messages.per_robot_hour` and `bytes_per_robot_hour` per multiple against the status rate (`status_hz` x 3600) and the status bytes: the share of messages and of bytes that is the heartbeat | composed |
| P3-E48-ROUND-SENTENCE (5.1, after P3-H10-VERDICT-SENTENCE) | E48 `classes.BASE.cpu_auction_round_ms` (`median`, `p99`) x `flight.factor` against a one-second decision; what the scaled round does to H10 | composed; direction from the data |
| P3-OWN-CHECKS-SENTENCE (3.6) | `results/vv_phase5.json` rows of the seven market and sizing checks (none rule equals the pooled regime; one owner has no payments and a zero budget; Shapley payoffs sum to the grand coalition's value; k = 1 reproduces honest payments; the audit at q = 0 charges nothing and at q = 1 charges m times every misreport; the E48 timers leave the event trace bit-identical; the ledger after a merge holds no job twice), once B-79 batch 3 lands | composed; pending |
| P3-REFERENCES | `NOTES.md` | numbered list |
| TABLE:vehicles | CAT and SCN (built: value and flag per cell) | built HTML |
| TABLE:E48_sizing, TABLE:E48_link | E48 `classes`, `flight`, `laptop`; since 11 Nov Table 6 reads `classes.*.link` (`antenna_m`, `freq_ghz`, `tx_power_w`, `mutual_horizon_m`, `worst_hop_kbps` or the words "beyond the horizon" from `beyond_horizon_at_worst_hop`, `longest_hop_kbps` at `longest_hop_m`, `latency_budget_ms`, `reachable_share`; BASE `uplink_from_small_kbps_at_worst_hop` in the table note) and `classes.*.link_free_space_upper_bound.worst_hop_kbps` (the upper-bound column) | built HTML |
| TABLE:E46_rules, TABLE:E46_owners | E46 cells (`profit_{A,B,C}_musd`, `operator_budget_musd`, `efficiency_loss_pct`, `settled_earth_musd`, `open_end_musd`, `ir_violations`); E46 pairs (coalition minus alone rows) | built HTML |
| P3-ID-FIX-SENTENCE | `results/id_fix_evidence.json` (`runs`, `identical`, `ids_reused_pre/post`, rows' `items`, `exp`) | composed |
| P3-E48-SECURED-LAYOUT-SENTENCE (3.4, the radio unit) | E48 `messages.secured.bytes_per_type.header` (`space_packet`, `lrip`, `security_header`, `mac` [narrow, wide], `signature`) and `.map` (checked: position at 1 Hz with status and intent at 0.1 Hz replace the 1 Hz status message; the landing announcement is sent once plus three repeats; grant and award are the signed types; the ledger entry is not on the air; the wider code adds its bytes to every type but the two signed ones) | composed; design input, Design |
| P3-E48-AIRTIME-METHOD-SENTENCE (4.2, E48 paragraph) | E48 `airtime.robots`, the `eta` of the scheduled and the slotted `airtime.rows` (checked: the access strings name a 20 % guard and 1/e), `revision.two_ray_in_the_mesh.e40_month.epochs` and `.scenario` (checked: C_AUCTION, 30 % load, loss 0.10, seed 1, the month with the least direct-to-Earth visibility at BASE) | composed; design input, Assumed |
| P3-E48-LINK-LAW-SENTENCE (4.2, E48 paragraph) | E48 `classes.*.link` (`worst_hop_m`, `peer_antenna_m`, `law`, `loss_db_worst_hop`, `mutual_horizon_m`) and `data/scenarios/E48-design.json` `radio` (`bandwidth_mhz`, `antenna_gain_dbi`, `noise_figure_db`, `implementation_margin_db`, `worst_hop_m`); the law's source is [21] as note 03 of the LRIP research notes cites it (Q2, E1) and the horizon rule [63] | composed; checked: the loss at the worst hop equals the two-ray formula, the horizon equals sqrt(2 R h1) + sqrt(2 R h2) |
| P3-E48-RESULTS-AIRTIME (5.2, second paragraph) | E48 `messages.secured.bytes_per_type.mac8` and `.mac16`, `messages.secured.per_robot_hour."1"`, `messages.secured.bytes_per_robot_hour."1"` (`mac8`, `mac16`), `targets.robots`, `targets.bytes_per_s_per_robot`, `targets.link_kbps_20_robots`, `h10.carries_20_robots_1hz_on_16_kbps.hops`, `revision.two_ray_in_the_mesh.e40_month.variants.default` (`hop_histogram`, `robot_epochs_cut_off_share`, `robot_epochs_with_base_up`), M `connectivity.rover_2.5m` `median_hops` at the radio range (checked: above the month's mean), and four `airtime.rows` (secured MAC 8 B: scheduled at the measured hops, slotted at the measured hops, scheduled at one hop, scheduled at two hops; `channel_kbps_needed`, `fits_16_kbps`) | composed; "within" / "above" the target per row from the data |
| P3-E48-REVISION-DATE (4.1, 4.6, 5.8, 7) | E48 `revision.date` | day month year |
| P3-E48-CORRECTION-SENTENCE (7, "The link budget was corrected once") | E48 `classes.*.link_free_space_upper_bound.worst_hop_kbps` (the first version's rates) against `classes.*.link` (`worst_hop_kbps`, `worst_hop_kbps_if_visible`, `mutual_horizon_m`, `beyond_horizon_at_worst_hop`, `antenna_m`, `worst_hop_m`) | composed; checked: the classes beyond the horizon are the two with the lowest antennas and their free-space rate is more than 100 times the flat-ground rate (the typed "more than two orders of magnitude"); the other classes' rates fell |
