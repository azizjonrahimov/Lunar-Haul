# Changelog

All results are simulation, replay or calculation on assumed inputs. Nothing is measured on lunar or flight hardware.

## Four more control runs named by the referees (15 November 2026)

Control runs B-117 f, g, j1 and j3, run after the results were known and labelled as controls, not pre-registered tests. Each wrote a new results file; no existing value and no pre-registered decision changed.

### Changed text
- **Value of time (P3, f)**: E46 rerun with the value of time multiplied by 0.2, 0.5, 2 and 5 (30 seeds; factor 1 reproduces E46). H5's third clause holds at every factor in both cost splits. The efficiency loss against the oracle depends strongly on the value of time: below zero at 0.2, 13 % and 36 % at the scenario's value, 101 % and 223 % at five times. The payment rules, and with them H5's first two clauses, were not run at other values.
- **Is the error inside the bound? (P2, g)**: with ranging, a vehicle's error was inside its own 95 % bound in 97 to 98 % of driving steps, at least 96 % in every seed. With dead reckoning alone it was 96.7 % on average, 76 % in one seed. In the margin runs the bound filed from the perfect-position run covered 99.4 % of the layered run's steps, so the overlaps that remain are not explained by a bound that is too small. P2 had said they might be.
- **Ranging inputs near the base (P2, P3, j1)**: swept on 30 seeds (was 6). The number of beacons in line of sight decides: 4.28 m with two or more, 21.6 m with one, 69 m with none. A beacon survey error of 1 m holds the 5 m budget in 16 of 30 seeds, and there the bound covers 94.5 % of steps, which is not traced.
- **Clocks at four times the fleet (P2, P3, j3)**: H11's rule is met at the same resync intervals (10 s to 6 h), 10 seeds. A daily resync gives 5 conflicts in 2 of 10 seeds on the lunar time scale (1 in 1 of 30 at today's fleet).

### Known gaps
- Control run e2 (the lost-link return driven in the engine) and the fix for the lost dispatcher wake-up in the learned-bid recording run are drafted and will land separately, with a re-stamp of the E50 and E54 families after reproduction checks.

## Control runs named by the referees (15 November 2026)

Seven of the control runs the referees asked for (B-117 a, b, c, d, e1, h, j2) and a rerun of the learned-bid evaluation on the right engine. All were run after the results were known and are labelled as controls, not pre-registered tests. No pre-registered decision changed.

### Changed results and text
- **Learned bids (P1)**: the 12 November rerun of the learned-bid evaluation ran without the dispatch fixed point (PREREG change 5), which is opt-in and was never switched on for it; P1 called it the corrected engine. Rerun on the fixed point: linear minus hand -2.32 h at 30 % load (was -2.49 h) and -31.5 h at 60 % (was -30.3 h). The check that other cargo does not pay for the gain now comes out clean at 30 % load; on the engine without the fixed point it did not. The bids were trained without the fixed point and not retrained.
- **What the linear bid learned (P1)**: its whole gain over the hand rule is the slack weight. A hand rule tuned with the same search budget beat the linear bids at 30 % load and cut their lead at 60 %, where the linear bids stay ahead by 12.8 h.
- **The auction's lead (P1)**: with the auction's own return move, the marketplace matched the auction (difference +0.01 h, -0.98 to 0.96); the auction's 0.84 h point lead is the return move.
- **Auction depth (P1)**: most of the depth penalty is there without message loss; the part due to loss is significant only at depth 5 and loss 0.40.
- **Short retry budget (P2)**: 3 tries every 20 s, run on the replay, lost 6.7 % of grants at loss 0.25. P2 had given 1.6 % by arithmetic, which assumed a path at every try; the contact plan's 60 s steps put the three tries in one step.
- **Moon-Mars conflict gap (P2, exploratory)**: one road segment holds 96 to 97 % of conflicts; fewer conflicts arise while a pair waits for Earth; the higher rate per traversal on Mars is not traced.
- **Sweeps (P3)**: H14's first clause holds at 10 of 12 retry budgets; H12 holds in all 17 map settings.
- **Site**: the /results/ P1 card reads the fixed-point evaluation.

### Known gaps
- Control runs g, j1, j3, e2 and f are still running and will land separately.
- On the fixed point, the learned-bid evaluation's recording run loses a dispatcher wake-up (cause found in `lunarsim/atc/learned.py`, fix not applied); outcomes come from runs without recording, and the agreement figures come from the recording runs.

## Phase 6 corrections after a code review (14 November 2026)

A code review of the Phase 6 work found defects in the positioning model, the delay-aware safety count and the lost-link accounts. The affected experiments were rerun; the earlier values are kept in each results file under a `superseded_…` block with the reason.

### Changed results
- **Position without GPS (E50)** was regenerated at 1x (30 seeds), 4x (10) and 8x (5) the fleet after a fix to the positioning model. Every H9, H10, H14 and H15a decision is as it was; H10 as a whole is still not supported. Dead-reckoning error p95 is 610 / 883 / 988 m (was 643 / 793 / 906 m). With the layered margin the violation count rises with the fleet: 0, 2.3 and 3.6 a month.
- **Uphill keep-distance (E45)**: with a 1 s actuation delay the R1 breach is now counted against the delayed command. The rate is 0 in all 16 delay cells under both rules (five were 0.05 % to 15 %). With the slope term, a gap up to 0.14 m inside the margin remains in two Mars cells; its cause is not known.
- **Lost link (E54)**: an Earth ledger whose 14-day life ends exactly when the 31-day window ends is counted expired, not censored: 300 expired and 390 censored (was 270 and 420); 690 undelivered either way. Awards, grants, reports, age of information and H14 did not move.
- **Stored encounter parts (E44)** whose deadlock flag was stale were regenerated (40 batches, 70,000 rows): 14,071 rows with a random fuzzer go from set to unset, none the other way, and no published value changes.

### Fixed
- Stored cells of E50, E45 and E54 carry a fingerprint of the code that produced them, and the builds refuse a missing, mixed or old one.
- The detector evaluation no longer drops two stored blocks on a rerun and refuses unstamped score caches.
- The LRIP codec reports every decode fault as its own error type and refuses a NaN or infinite clock.
- The G1 regression comparison is exact (0 of 144 values differ; one scenario, one seed, 30 days).
- CI: the detector-network job fails when a test fails, not only when one is skipped.
- Site: results files are read through one helper that stops the build on a missing file or block; `/network/` follows the system colour scheme; pages state the corrected values and name the earlier ones with their cause.
- Papers P1, P2 and P3 follow the corrected results, and several sentences that had no check behind them are now tied to the results files or reworded.

### Known gaps
- Control runs named by the referees (B-117) are still not run.
- Open follow-ups from the review are listed in `reports/review_phase6_code.md`, section O.
- The pre-registration file gained a dated correction log; no bar in it was changed.

## Phase 6: the Lunar Rover Interaction Protocol (deployed 13 November 2026, `b96361e`)

### Added
- **Position without GPS** (`lunarsim/atc/pnt.py`, E50): dead reckoning, terrain fixes and ranging as layers, with the position error carried into the keep-distance margin. Runs at 1x, 4x and 8x the fleet.
- **Clocks** (E51): a per-vehicle clock model and the reservation guard it needs.
- **Shared map and coordinates** (E52): one frame and datum, and how fast map changes spread.
- **LRIP, the message protocol** (`lunarsim/atc/lrip/`, E53): 15 message types with a bit-packed codec and conformance vectors. Version 0.2 declares frame, datum and time scale in HELLO and carries a position uncertainty code.
- **Lost link** (E54): store-and-forward with custody. A silent vehicle's reservation is not released; the segment is marked unconfirmed.
- **Integrity and consensus** (E55) and a **wrong-position detector** (E56): a 9,529-parameter network with its loss landscape.
- **Real-data checks** (B-97): spacecraft telemetry (SMAP, MSL) and Artemis II optical navigation, shown for what they are.
- **Site**: `/protocol/` and `/network/` pages, a Phase 6 block on `/verification/` (54 checks), and the `/results/`, `/atc/` and `/paper/` pages reading results files at build time.
- **Papers**: P1, P2 and P3 revised with Phase 6 and then again after an internal referee round (three reports, each "major revision"). P1 has a new title: "Working Together Without Earth: Job Sharing, Team Lifts, Learned Bidding and a Message Protocol for Lunar Robots of Different Owners".

### Changed after the referee round
- Results that could not have come out otherwise are called design calculations or properties, not tests.
- "Near the base" is reported under every reading; the verdict depends on the reading.
- The count of reservation overlaps is no longer used as a safety measure.
- The keep-distance rule gained a slope term for uphill driving.
- The learned-bid evaluation was rerun on the corrected engine. The linear model's gain holds; the check that it is free for other cargo at 30 % load does not come out clean.
- Encounter types 4, 5 and 6 were rerun on fresh seeds: one zone violation in 10,000 type-6 encounters under the rule as written. A request-rule variant removes it but is exploratory.
- "Measured" memory and timing in the sizing paper are now measured (one seed, on a laptop, scaled by an assumed factor).

### Fixed
- CI on `main`, red since 30 October: the `cryptography` dependency was missing from the `full` extra, three recorded file hashes were of CRLF copies, two tests needed files or packages CI does not have, and four experiment design records were validated as scenarios.

### Known gaps
- Lighthouse was not measured for this release, and the light theme was checked on 5 pages only.
- Several control runs named by the referees were not run; each paper lists them under Limitations.
- The repository was renamed `Lunar-Haul`. Schema identifiers and the older papers (v2, v3) still carry the old name; GitHub redirects it.
