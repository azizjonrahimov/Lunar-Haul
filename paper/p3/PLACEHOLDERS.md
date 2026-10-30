# P3 placeholders (draft 0, 29 Oct 2026)

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

**Abbreviations.** CAT = the catalogue; SCN = the scenario; M = `results/ATC_mesh.json`; REG = `regimes.DEFAULTS`;
E46 = the three E46 files; E48 = `results/E48_sizing.json`; PR = `paper/atc/PREREG.md`.

| Key | Source | Format |
|---|---|---|
| P3-N-CLASSES, P3-N-CLASSES-FLEET, P3-N-FLEET, P3-N-OWNERS | CAT `classes` count; SCN `fleet` (distinct classes, vehicles, owners) | words |
| P3-K30 | SCN `p5.k` | 3 decimals |
| P3-CLV1-PAYLOAD-KG, P3-CLV1-RANGE-KM | CAT `LTV1_CLV1.params.capacity_kg`, `range_km_per_charge` (checked equal to Pegasus's payload) | kg; km |
| P3-CAP-MAX-SINGLE-KG, P3-CAP-MAX-PAIR-KG, P3-CAP-FLEET-SUM-KG | CAT `capacity_kg` over the fleet's classes: the largest, the two largest with `can_team_lift`, the sum over the fleet's vehicles | kg |
| P3-N-COALITION-RUNS | 2 to the power of the number of owners (SCN) | word |
| P3-MESH-N-POINTS | M `n_points` | count |
| P3-MESH-LOS-25-0TO05, P3-MESH-LOS-25-2TO5, P3-MESH-LOS-10-2TO5 | M `los_by_distance_band` `2.5-2.5` `0-0.5 km`, `2-5 km`, `1.0-1.0` `2-5 km`, `los_0m` (checked: falls with distance and height) | % |
| P3-MESH-MAST-DIRECT-SHARE, P3-MESH-MAST-DIRECT-MAX-KM | M `mast_direct.rover_2.5m`: (n_points &minus; `n_no_direct_los`) / n_points; the last distance band whose `within_km.n` grows (checked against the band share; checked 10-30 %) | %; km |
| P3-MESH-COMPONENTS-2KM, P3-MESH-REACH-1HOP, P3-MESH-REACH-2HOPS, P3-MESH-MAX-HOPS-5KM, P3-MESH-MEDIAN-HOPS-5KM | M `connectivity.rover_2.5m` at 2 km and at the radio range (`reach_base_share`, `max_hops`, `median_hops`; checked: one component, nobody never reaches) | word; %; words |
| P3-MESH-SMALL-ISOLATED, P3-MESH-SMALL-MAX-HOPS | M `isolated.small_1.0m.n`; `connectivity.small_1.0m` at the range, `max_hops` | words |
| P3-RADIO-RANGE-KM | `radio.DEFAULT_D_MAX_M` (checked: one of M's ranges) | km |
| P3-HOP-LATENCY-MS, P3-MEAN-BURST | `messages.HOP_LATENCY_S`, `MEAN_BURST` | ms; count |
| P3-BASE-MTBF-H, P3-BASE-REPAIR-H, P3-REELECT-MIN | REG `base_mtbf_h`, `base_repair_h`, `reelect_h` x 60 | h; h; min |
| P3-TIMEOUT-H | `auction.TIMEOUT_H` | h |
| P3-LIN-N-WEIGHTS, P3-MLP-N-PARAMS | as build_p1.py: the linear policy's `layers[0].w` length (checked: one weight per observation name) and the sum of `w` and `b` sizes over the network's `layers` (`data/policies/atc_bid_linear_v1.json`, `atc_bid_v1.json`) | count |
| P3-CHANGES-SENTENCE | PR: `### Change N` headings after change 1 that name E46, E48, H5, H10 or first-price | composed |
| P3-CHECKS-SENTENCE, P3-FAILED-CHECKS-SENTENCE | the verification page's phase-5 checks (B-79 batch 3) | pending |
| P3-E48-DESIGN-SENTENCE, P3-E48-COMPUTE-SENTENCE | E48 `runs` | composed; pending |
| P3-E48-RESULTS-CPU, P3-E48-RESULTS-MESSAGES, P3-E48-RESULTS-LINK, P3-E48-RESULTS-FAILOVER | E48 `classes`, `messages`, `ledger_mb_per_year`, `failover`, `flight`, `laptop` | composed paragraphs; pending; checked: no job assigned twice |
| P3-H10-VERDICT-SENTENCE | E48: scaled p99 safety-check time x factor x `safety_hz` as a share of one core at the worst class; scaled peak memory against `flight.memory_mb`; `bytes_per_robot_hour."1"` x `robots` x 8 / 3600 against `link_kbps_20_robots` | composed: "holds on every count" / "does not hold on every count (...)" from the data |
| P3-E48-ABSTRACT-CLAUSE, P3-E48-INTRO-CLAUSE, P3-E48-DISCUSSION-CLAUSE, P3-E48-COMPARISON-CLAUSE, P3-E48-CONCLUSION-CLAUSE, P3-E48-LIMITATION-SENTENCE | the same scaled values; "fits" / "does not fit" from the data; the comparison with the 13.8 kB/s convoy controller of [25] | composed; pending |
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
| P3-REFERENCES | `NOTES.md` | numbered list |
| TABLE:vehicles | CAT and SCN (built: value and flag per cell) | built HTML |
| TABLE:E48_sizing, TABLE:E48_link | E48 `classes`, `flight`, `laptop` | built HTML; pending |
| TABLE:E46_rules, TABLE:E46_owners | E46 cells (`profit_{A,B,C}_musd`, `operator_budget_musd`, `efficiency_loss_pct`, `settled_earth_musd`, `open_end_musd`, `ir_violations`); E46 pairs (coalition minus alone rows) | built HTML |
