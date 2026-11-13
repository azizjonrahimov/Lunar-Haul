# Changelog

All results are simulation, replay or calculation on assumed inputs. Nothing is measured on lunar or flight hardware.

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
