# Changelog

All results are simulation, replay or calculation on assumed inputs. Nothing is measured on lunar or flight hardware.

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
