# Response to the referee report on P3 (Phase 6 revision), 12 November 2026

Report: `reports/referee_phase6_p3.md`. Binding decisions: `reports/referee_phase6_decisions.md` (A1 to A5, B1 to B4, B8 to B11).
Only `paper/p3/` was edited. The build passes without `--allow-pending`; `paper.html` holds no `[[PENDING` string; abstract 300 words,
conclusion 250. No number that a results file holds changed. Section and table numbers are those of the built paper.

Status words: **fixed**; **fixed in part** (what is missing is named); **awaits** a task; **not done** (with the reason).
Counts: 32 fixed, 7 fixed in part, 1 awaiting tasks and new runs, 4 not done (44 findings).

Landed during the revision and reported: E50b (B-90b) and E50 at eight times the fleet. Still awaited, each with one plain sentence in the
text, a row in Table 18, an entry in Sections 6.6 and 7 and an awaited key in `PLACEHOLDERS.md`: B-100, B-101, B-103, B-104, B-105.

## MUST FIX

| # | Status | What was done | Where |
|---|---|---|---|
| M1 | Fixed in part | Memory relabelled everywhere as "estimated, not measured": a 24-hour window of the reservation table, a year's ledger copy, the two policy files as stored and 0.05 MB allowed for working data; "peaked" dropped. The round is "the simulator's dispatch call for the whole fleet, 84,367 calls pooled over one, four and eight times the fleet"; "on the crew rover" removed. Abstract and conclusion: "the simulator's whole-fleet dispatch call ... takes 1.12 s at the 99th percentile; one vehicle's share was not timed". Missing: the time per fleet size (the results file holds the pooled figure only) and real measurements: await B-105 (`E48_sizing.json`, blocks `measured_memory`, `per_robot_round`). | 3.4, Table 3, 4.2, 5.1, Table 6, 6.1, 7, Table 18, abstract, conclusion |
| M2 | Fixed in part | Claim reworded as the referee proposed: "the authenticated traffic of 20 robots, 7.86 kbit/s at the sources, would need 10.06 kbit/s of a base-scheduled channel if every robot were within one hop of the base; in the recorded month that holds for robots standing at sites, and a driving robot has a path to the base 57 % of the time". Basis stated: positions 97.4 % parked (347,669 against 9,451 steps, seed 1); a path to the base in 56.6 % of driving steps (47.7 to 62.9 % over seeds) against 93.2 % of all time (`E54_dtn.json`, `link_shares`). Report rates stated once in 3.4 (position 1 Hz, status and intent 0.1 Hz). Source load with all three at 1 Hz: 41 + 43 + 38 = 122 B/s, 19.52 kbit/s for 20 robots, above the target (a calculation, said so). E53's 2.5 m antenna for every rover stated. Missing: hops and reach over driving steps only: awaits B-103 (`E53_bitrate.json`, block `driving_hops`). | 3.3, 3.4, 4.2 (E53), 5.1, 5.2, 6.1, 7, Table 18, abstract, conclusion |
| M3 | Fixed | No marker prints. Awaited results are plain sentences (`fill_await` in the build); the build stops if `[[PENDING` or `[[CHECK` would reach the output, comments included. | 5.1, 5.2, 5.3, 5.8, 5.11; `build_p3.py` |
| M4 | Fixed | The four sentences now say "the design requires"; what v0.1 serialises is stated from the schema file: east, north (24 bits, 0.01 m), height (16 bits, 0.1 m), heading (12), speed (10), one scalar sigma (8 bits, 0.05 m), a 3-bit source code, a moving flag, 6 spare bits: 104 bits, 13 B; header: version, type, sender, one time stamp "on the site time base". No frame, datum or time-scale identifier, no covariance; v0.2 adds them (B-100, not yet done). 41 B, 52 % and 7.86 kbit/s labelled v0.1 figures before link framing and coding (plus 12 B in a Proximity-1 frame); each added byte is 0.16 kbit/s for 20 rovers. The traffic model sends 11 of the 15 types (not: task announcement, capability query, manifest, map notice). 6.3's "cost nothing" withdrawn for the identifier rule. v0.2 sizes await B-100 (`E53_bitrate.json`, block `v02`). | 3.5, 3.6, 3.7, 3.8, 5.11, 6.3, 7 |
| M5 | Fixed | Region rule stated as chosen with the experiment, not registered, covering 23.1 % of driving steps. H9' clause 2 verdict: "depends on the reading". Reported: 4.22 m under the analysis's reading; the referee's rerun of seeds 1 to 6 (attributed, read from the report by the build, its first row checked against E50): 4.21 m (23.6 %, 6 of 6), 12.9 m with one or more beacons (57.5 %, 0 of 6), 25.0 m within 1 km (67.7 %, 0 of 6), 47.1 m within 5 km (all steps, 0 of 6); sensitivity 9.6 m, 4.8 m, 5.2 m. Inside the region: 2.9 % of steps over 5 m, largest error 12 m on average and 22 m at most, own bound over budget in 31 %. Abstract: "Ranging holds ... 4.2 m where two or more base beacons are in line of sight, 23 % of driving steps, but not within a kilometre of the base (25.0 m, a referee's rerun)". All seeds under four readings: awaits B-101 (`results/E50_near_base.json`). | 4.2, 4.6, 5.8, 6.1, 7, Table 18, abstract, introduction, conclusion |
| M6 | Fixed | H12 and H13 reported as design calculations with the assumed input named (42 tiles a day in three layers of 3,969: 126 of 11,907 = 1.06 %; 20 x 49.1 B/s x 8 = 7.86 kbit/s, the same in every draw; paired differences in inverse ratio to the rate, checked). H11's ranging half: a property of the assumed 100 ns residual (30 m), true of any oscillator; the 95th percentile comes from vehicles with no path, median 92 m. H14's second clause: "not testable as written". Ledger: "11 of the 31 daily bundles", a calendar calculation; Earth in view 52.7 % of the month without the blackout and 7.9 % with it; the blackout's placement (days 8 to 22) stated as a design choice that was not varied. Table 18 gains the status "calculated from assumed inputs" (six rows). | 1, 4.1, 4.6, 5.9 to 5.12, 6.1, 7, Table 18 |
| M7 | Fixed in part | Stated in 3.9 from the scenario and the E46 design file: value of time 5,000, 1,000 and 100 USD an hour by priority; undelivered items censored at the horizon; carrier cost = half the unit cost per life hour plus operator time at 1,000 USD an hour; flag Assumed (the design file's own flag, "the scenario's specification", quoted). 5.6, from the run parts: alone, A, B and C deliver 99.3 %, 98.9 % and 1.9 % of their items (1.8 % for C with 50/35/15), and the delay cost is 81 %, 87 % and 100 % of the alone loss. Missing: the censored share in USD (the run files hold items and delay per owner only) and a sweep of the value of time (a limitation and future work). | 3.9, 5.6, 6.1, 7, Table 18 |
| M8 | Fixed | Table 4 flags: navigation service "Assumed (the providers' target; their own simulation gives 17.2 m)" with [79] for the target; dark-fix failure share "Assumed"; "(one simulation gives 6.6 %)" dropped; 2 % as "a design assumption" of [70, 71]; the crystal as "Assumed distribution over vehicles, taken from the excursion of one crystal" (uniform, one-signed). | Table 4, 3.5, 3.6 |
| M9 | Fixed | Two products, two quantities: the laser tracks behind the 5 m site models are placed to 0.1 to 0.2 m [76] (note 01, note 02); the wider polar product of 2023 states 1 m as a conservative figure [90] (note 02). E50's beacons are assumed surveyed on the site model (0.15 m, flag Assumed); the 1 m case is the referee's 4.8 m. | 3.7, Table 4, 5.8 |
| M10 | Fixed | 2.1: the carry runs "over 13.8 kB/s of inter-rover traffic on 2.4 GHz Wi-Fi". Table 1: "Yes (built for flight, not flown)". Introduction: the radio "is standardised only in part" with CCSDS 883.0-B-2 named. 2.2 and 3.3: Wi-Fi "specified for" Griffin and Peregrine; Peregrine did not reach the Moon, Griffin has not launched. 6.5: "of several makers and countries", with Griffin Mission One's two rovers of two companies named as a secondary-source fact [120]. | 1, 2.1, 2.2, 3.3, 6.5, Table 1 |
| M11 | Fixed | [104]: proved for the continuous-time rule; the discrete rule's paper not opened. [102]: NASA's words quoted; version 7 and custody attributed to an unread abstract. [51]: reworded to what the report says and to whom it attributes the remark. [30, 31], [33]: marked not re-read; the deficit result credited to Green and Laffont as the note has it. [80]: "slides list a demonstration in fiscal year 2029", with the note's caveat. Section 7's sentence replaced by a list of what rests on secondary or abstract-level reading. VDA 5050 [117] and MassRobotics [118] cited in 2.3, 3.8 and Table 5, with what the lunar case adds; "no standard" is now "no space standard". | 2.1, 2.3, 2.4, 3.5, 3.8, 6.5, 7, references |
| M12 | Fixed | 6.2: "cannot be said to agree ... only to be of the same order ... different quantities, at different sites and tower heights, and they were not matched: the verification suite's check of exactly this comparison was skipped as unfair". 3.3 likewise. | 3.3, 6.2 |
| M13 | Fixed | H9' and H10' (P2's notation) everywhere in P3, with the rule stated once in 4.1; bare H10 is only the sizing hypothesis of the first registration. | 4.1, 4.6, 5.8, 7, Table 18, section headings |
| M14 | Fixed | Proposition 1 gains the assumption "d small against the radio horizon, so that d^2/8R is small against both heights"; the worked example states that the hops of Table 7 do not meet it (bulge 1.80 m of 2.5 m at 5 km; 1.00 m at 3.73 km) and gives the referee's figures, attributed: 137.0 against 132.0 dB and 146.6 against 142.9 dB, rates about 1.4 to 2.4 times lower (about 700, 25, 49 and 3,400 kbit/s). Same in Table 7's note, Section 7 and Table 18 ("Proved (for a plane)"). The project's own check: awaits B-104 (a spherical-ground column of Table 7). | Appendix A, Table 7, 5.3, 7, Table 18 |
| M15 | Fixed | The 57 m sentence and the beacon sentence of 6.1 deleted. The proposition states "one epoch, no prior, all beacons in view"; 3.5 says the simulated layer is a sequential filter not bound by it. Example recomputed with the construction site: dilution 8.9 at 0.26 km (the worst), 1.2, 5.2, 7.0; single-epoch bounds 27 m, 3.7 m, 15 m, 21 m; E50's median 1.1 m where two or more beacons are seen. | Appendix A, 3.5, 6.1, Table 18 |

## SHOULD FIX

| # | Status | What was done | Where |
|---|---|---|---|
| S1 | Fixed | The four class timings are stated as one measurement (same function, same moves, no reservation entries in the call), their differences as timer noise; "worst class" removed; Table 6 has one robot row with the range; the hopper's "fewer rules" cell corrected; Section 7 chooses one statement (a compiled implementation would be expected faster; not measured). | 5.1, Table 3, Table 6, 7, abstract |
| S2 | Fixed | Interval given: registered 10:14, first result 17:43 on 11 Nov 2026 (commits b1e2266, 99c2a0d). Deviations listed in 4.6: the region rule, E54 as a message replay with "urgent wait" unreported, the family reduced to three, the sign test. Holm with all five counted: at most 0.005 (H15a) and 0.008 (H14), no verdict changes (recomputed by the build). Sign test stated one-sided; two-sided 0.004 and 0.008 after Holm. | 4.1, 4.5, 4.6, 5.12, 7 |
| S3 | Fixed | 4.5: H5 is outside the first registration's confirmatory family; six verdicts uncorrected; the selected maximum of twelve cell means is biased upward, which only strengthens "not supported". | 4.5 |
| S4 | Fixed | 5.7: the third clause tests superadditivity; the tariff cancels; "better named Shapley sharing"; owner C's 200 M USD transfer is 14 times the 14.7 M USD of tariff cash. 3.9 names it too. | 3.9, 5.7, Table 18 |
| S5 | Fixed | 4.2: "a covariance analysis with a matched filter ... the best any estimator could do if the model were the world"; also in Section 7. | 4.2, 7 |
| S6 | Fixed | Proposition 2: assumption of equal heights, power and gains added, with the Table 7 counterexample; Table 7's columns headed "Shannon bound". | Appendix A, Table 7 |
| S7 | Fixed | Bound stated as hash bytes in one direction, without replies and framing; one authenticated message per opened node nearly doubles the walk (28 B around 32 B); "up to 206 changed tiles (the bound is n below 206.7)", 39,560 B at n = 206. | 3.7, Appendix A |
| S8 | Fixed | (a) Table 12's two nanosecond rows marked "below the assumed transfer residual of 100 ns: not reachable"; (b) caption says the times are the closed form applied to 240 drawn clocks and that the comparison is of a formula with itself; (c) the no-guard column explained as a count of back-to-back pairs; (d) today's fleet only, larger fleets not checked. | 4.2, 5.9, Table 12, Appendix A |
| S9 | Fixed in part | (a) the retry budget stated as ours (last try 12 min after the award, from the code: five tries 180 s apart), "the size of that difference is the comparator's"; not swept (future work). (b) "counted as a lost job (hypothetically: in the recorded run every job was done)". (c) 82.1 returns a seed, about 2.6 a day, reported. (d) "the ladder's own contribution is two awards in 30 months, with a returning vehicle given a direct link". | 4.2, 5.12, Table 15, 7 |
| S10 | Fixed | 3.8: the window and the rising counter apply to the reports; a bundle is protected by its identifier, its lifetime and its originator's signature or code; said to be design, not tested, and that Proposition 7(b) covers the reports only. | 3.8 |
| S11 | Fixed | (a) "no result of this paper uses such code, because the terrain fix of E50 is a Gaussian draw"; (b) the spacecraft is below the horizon at every one of the 212 epochs (-9.26 to -0.04 degrees), so the check exercises azimuth and elevation, not the terrain mask; 6.1 narrowed. | 4.2, 5.13, 6.1, 7, Table 18 |
| S12 | Fixed | 5.11: with two liars against a rule set for one, the share of runs inside the honest range falls from 48 to 66 % without the mast to 2 to 24 % with it. | 5.11 |
| S13 | Fixed | 3.3: with 0.6 of the first Fresnel zone clear, 5.4 % at 2.4 GHz (against 9.3 %) and 1.8 % at 400 MHz; the mesh counts a grazing ray as a link; 6.3 gives the clearance side of the UHF case. | 3.3, 6.3, 7 |
| S14 | Fixed in part | Done: [16] title; "the closest we found" for the four "the one / the only" phrases; 3,908 ms for negotiation messages added; Table 1's two "Yes" cells corrected; [119], [120] secondary pages and [121] the GR740 benchmark added and named for what they are; L_G attributed to the IAU; secondary and abstract-level readings listed in Section 7. Not done: missing dates, initials and titles (the research notes do not hold them; listed in `NOTES.md`); [103]'s identifier not re-checked on the web; Table 2's "(claim)" in cells (the table prints the catalogue file's flags, which lie outside `paper/p3/`); the company post behind Eagle's night operation is in the catalogue's source string only. [81]: note 04 records it as opened; kept. | references, 2.x, 7 |
| S15 | Fixed in part | P3's side only: the lost-link rule as decision B1 states it; "the checks", not "the proof"; P1's finding restated neutrally; the clock claim about [60]'s lifts removed; [60], [61] dated "revised November 2026". The other papers' text is theirs. | 1, 3.3, 3.8, references |
| S16 | Fixed | Limitations added: the value of time and the censoring; "near the base" as 23 % of driving, with its sensitivity; the path to the base for 57 % of driving time; hidden terminals, fading and the scheduling question; the matched filter; the 2.5 m antenna and the 1 Hz rate; Python timing and the simulator's round; grazing rays and the law at the horizon; calculations that are not tests; the protocol as serialised. | 7 |
| S17 | Awaits tasks; the rest not run | Items 2, 3 and 4 await B-103, B-105 and B-104 in part. The others (sweeps of E50's inputs on all seeds, E46's value of time and best response, E54's retry budget and engine-driven returns, E52's change rates, E51 at larger fleets) need new runs and are listed in 6.6 as not run. | 6.6 |
| S18 | Not done | The paper is not split (the lead's decision). A roadmap paragraph ends the introduction, and the openings of Sections 3, 4.1, 4.2, 5, 6.1 and 8 name the two halves; Table 18 is pointed to as the shortest way in and was not moved. | 1, 3, 4, 5, 6.1, 8 |

## OPTIONAL

| # | Status | What was done |
|---|---|---|
| O1 | Fixed | 84.5 and 104.5 dB (3.3). |
| O2 | Fixed | 4.2: of the 1,080 simulated years, 780 are market runs and 300 the oracle, the owners alone and the pair coalitions. The abstract keeps "1,080 simulated years" for the word limit. |
| O3 | Not done | 199.3 jobs against 200.9 awards a seed: not explained from the files read. |
| O4 | Fixed in part | Regime codes and design-file jargon removed from the composed sentences (the auction regime, the leader regime); A_MOON removed. Task numbers of the awaited results are kept on purpose; the list of skipped checks in 5.14 is unchanged. |
| O5 | Fixed | 6.1: the first-price budget is called the gap between calibration and test seeds; the ratio "5.1 times" dropped. |
| O6 | Not done | CoreMark was not run on the laptop (a new measurement, outside this revision). |
| O7 | Fixed | 56.02 microseconds a day in 3.6 and in Proposition 3's result, with the reason. |
| O8 | Fixed | The crystal's distribution stated as uniform between 0 and 8 x 10^-7 and one-signed; the no-guard column explained. |
| O9 | Fixed | Table 6 no longer repeats columns; the pooled dispatch-call figure is in the caption. |
| O10 | Fixed | Proposition 4's example says which value is the formula's (259 days, 5.7 s) and which the table's (258 days, 5.5 s). |
| O11 | Not done | Concerns P1's text. P3 prints "at most 0.003". |

## Where this response differs from the report

- M11, [80]: the note records the JAXA slides as opened; what it could not verify is which listed year belongs to which later milestone. The citation is kept with that caveat, not cut.
- S14, [81]: note 01 says the trade report was not opened, note 04 says it was (entry M3). It is cited through note 04.
- S9(a): the comparator gives up at its fifth try, 12 minutes after the award (tries at 0, 180, ..., 720 s in `lunarsim/atc/dtn.py`), not 15.
- M14: the ratios of the rates the report lists are 1.4 to 2.3; the report's stated range, 1.4 to 2.4, is printed as the referee's.

## Second pass, part 1 (12 Nov)

Three awaited results landed (B-101, B-103, B-104); their composers are written and the build fills them from the files. The referee's own
numbers (the six-seed rerun, the three sensitivity values, the spherical-ground loss and rates) are no longer printed and the build no longer
reads the referee report. Build: passes with `--no-pdf` and without `--allow-pending`; abstract 299 words, conclusion 250; no `[[PENDING`.

| Finding | Now | What changed | Where |
|---|---|---|---|
| M5 | Closed | H9' clause 2 from `results/E50_near_base.json` (a simulation on assumed ranging errors, all seeds). Today's fleet, 30 seeds: 4.22 m where two or more beacons are in line of sight (23 % of driving steps, every seed inside); 12.5 m with one or more (57 %, no seed); 24.7 m within 1 km (67 %, no seed); 50.1 m under the registered wording, which covers every driving step (no seed). Four times the fleet, 10 seeds: 4.31, 8.64, 22.4, 32.1 m, the same pattern. The text says that under the registered wording the clause fails in every seed; verdict "depends on the reading". Sweep (six seeds): long-range ranging error 1 / 3 / 10 m gives 1.87 / 4.21 / 9.64 m under the narrow reading (inside, inside, outside in every seed) and 38.4 / 47.1 / 62.8 m under the registered wording; ultra-wideband error 0.1 / 0.3 / 0.7 m gives 4.16 / 4.21 / 4.25 m. Eight times the fleet: stated as not computed. The referee's survey-error and ultra-wideband-reach cases are dropped (not in B-101) and named as not swept. | 5.8, 6.1, 7, Table 18, abstract, introduction; 3.7 |
| M2 | Closed (antenna heights and motion-tied rate named as not run) | From `E53_bitrate.json`, `driving_split` (a calculation on drawn positions): the 1.024 hops are a figure for parked robots (54 of 6,174 robot-epochs are driving); drawn from driving steps, 20 rovers are 1.58 hops from the base (1.01 from parked steps), 93 % have a path (99 %), the busiest link carries 5.89 kbit/s (7.86), scheduled airtime 7.37 kbit/s (within the target), slotted random access 16.02 (above). The 93 % is distinguished from E54's 56.6 %. Status and intent at 1 Hz: 19.52 kbit/s at the sources, scheduled airtime 24.4 and 18.3 kbit/s, both above the target: the 1 Hz case does not hold at those rates. | 5.2, 7, Table 18 |
| M14 | Closed | From `E48_sizing.json`, `revision_b104` (a calculation with ITU-R P.526 section 3.2, checked against the text of P.526-16): at each class's longest hop 137.0 against 132.0 dB (crew and cargo rovers), 146.6 against 142.9 dB (small rover, hopper), 131.4 against 128.0 dB (mast); rates 701, 24.6, 48.9 and 3,653 kbit/s in place of 1,574, 57.9, 114 and 4,717. Table 7 has a spherical-ground column. One verdict moves: the rovers' 5 km hop no longer carries 1 Mbit/s (range at that rate 4.64 km, from 5.89 km); airtime, 16 kbit/s and the mast-reach shares do not move. The mast's figure differs from the referee's (3,653, not about 3,400: P.526 interpolates inside line of sight). | 5.3, Table 7, Appendix A (Proposition 1), 7, Table 18 |
| S17 | Items 1 (in part), 2 (in part) and 4 done | As the three rows above; still not run: the survey error and ultra-wideband reach, 1.0 m antennas and a motion-tied rate in the traffic model, and items 3, 5 to 8. | 6.6 |

Sentences that changed in the abstract: "Ranging holds the 95th percentile of position error at 4.2 m where two or more base beacons are in line of
sight, 23 % of driving steps, and fails under the registered wording, which covers all driving (50.1 m)" replaces "... but not within a kilometre
of the base (25.0 m, a referee's rerun)". No verdict word changed in the abstract or the conclusion.

Verdicts that a new number moved: the megabit verdict of the crew and cargo rovers' longest hop (true over flat ground, false over a spherical
ground); the 1 Hz link case if status and intent also go at 1 Hz (fails on every channel). Table 18 now has seven rows "calculated from assumed inputs".

Still awaited, as plain sentences: B-100 (protocol version 0.2), B-105 (measured memory, one robot's bid computation); B-102 (overlap durations)
is named in Section 7 as the companion paper's.

## Second pass, part 2 (12 Nov)

B-105 landed (`results/E48_sizing.json`, blocks `per_robot_round` and `measured_memory`); both composers are written. Build: passes with
`--no-pdf` and without `--allow-pending`; no `[[PENDING`; one key still awaited (B-100, protocol version 0.2).

| Finding | Now | What changed | Where |
|---|---|---|---|
| M1 | Closed | One robot's bid computation in an auction round (its loop over the waiting items; one 30-day month of seed 1 per fleet size; laptop, scaled by 54.8): 99th percentile 0.29 s at today's fleet (0.19 to 0.34 over the factor's range), 1.09 s at four times (0.73 to 1.28), 1.19 s at eight times (0.79 to 1.39); medians 11 to 25 ms. Verdict against the one-second decision, written from the data: within it at today's fleet, above it at four and eight times the fleet at the 99th percentile. The whole-fleet 1.12 s is kept as what it is and said to be about one robot's share. Memory measured with tracemalloc: 0.11 to 0.13 MB at peak with the parts held at once (0.14 MB with the planner's working memory added), against the 0.39 MB estimate; 0.11 MB is the learned bid policy that the default auction does not use; the other parts 0.01 to 0.03 MB. Stated: interpreter, code and numpy buffers not counted (the process holds 439 MB); a laptop measurement scaled by an assumed factor, one seed, not flight hardware. "Not timed" and "not measured" removed everywhere. | abstract, 1, 3.4, Table 3, 4.2, 5.1, Table 6 caption, 6.1, 6.4, 6.6, 7, Table 18, conclusion |
| S17 item 3 | Done in part | One robot's bid computation is timed apart from the simulator's round. The safety check in a compiled language is still not run. | 5.1, 6.6 |

Verdicts that moved: the bidding against the one-second decision. Before: unknown for one vehicle (only the pooled whole-fleet call, 1.12 s). Now:
fits at today's fleet, does not fit at four and eight times the fleet at the 99th percentile under the assumed scaling (at the low end of the factor's
range it would fit). H10 as registered has no capacity for the bidding, so its registered counts do not move; its verdict sentence now states the
bidding result. Table 18: the whole-fleet row is replaced by a tested row for one robot's bid; a tested row for measured memory is added; the
estimate row stays "calculated from assumed inputs"; the "not yet tested" row keeps only "the software on a flight-class processor, in a flight language".

Abstract (299 words): "one robot's bid takes 0.29 s (99th percentile) at today's fleet and 1.19 s at eight times it, above the one-second decision"
replaces the whole-fleet sentence. Conclusion (249 words): the same sentence. Section 6.6 names the design change that follows and is not made: a cap
on the items a robot evaluates in a round. Section 7's pointer to B-102 as the companion paper's is unchanged.

## Second pass, part 3 (12 Nov)

B-100 landed (`lunarsim/schemas/lrip-v0.2.json`, `results/E53_bitrate.json` block `lrip_v02`, `results/E53_table_v02.csv`); the composer is
written (the key name fixed from `v02`). Nothing is awaited any more. Build: passes without `--allow-pending`; no `[[PENDING`; abstract 300
words, conclusion 248; PDF rebuilt.

| Finding | Now | What changed | Where |
|---|---|---|---|
| M4 | Closed | The design text now describes what version 0.2 does, not what the design wished: the position report carries a one-sigma value and a 95 % horizontal bound (six bits that were spare; 0.05 m x 2^(code/4), coded upward; codes for "above 1.95 km" and "unknown"), still 104 bits and 41 B authenticated; frame, datum and time scale are declared per sender (6, 6 and 4 bits in a heartbeat sent at least every 10 s, and in the signed manifest) and bound to the security context: a position from a sender with no declaration under its current key epoch is refused. A covariance is not carried, and the text says so in 3.5, 3.8, 6.6 and 7. Sizes that differ: heartbeat 30 to 32 B, small-rover manifest 283 to 292 B. Rates for 20 rovers at 1 Hz, version 0.1 against 0.2: per rover 49.1 against 52.3 B/s; authentication adds 52 against 53 %; busiest link 7.86 against 8.37 kbit/s; scheduled airtime 9.82 against 10.46 kbit/s; with Proximity-1 framing (+12 B a packet) 10.87 and 13.58 kbit/s, within the target scheduled and not on slotted random access. H13's two comparisons come out the same. Table 14 has two new rows (version 0.2; version 0.2 in Proximity-1 frames). Labelled a calculation on a traffic model; the conformance vectors are said to test the codec, not a radio. The driving split and the status-and-intent case are said to be version 0.1 figures (the report gives them under v0.1 only). Every "v0.1 lacks / awaiting v0.2" sentence is gone. | 3.5, 3.6, 3.7, 3.8, Table 5, 5.11, Table 14, 6.3, 6.6, 7, Table 18, abstract, introduction, conclusion |

No verdict moved. Abstract: "Authentication adds 52 % to the bit rate; senders declare frame, datum and time scale, and reports carry a 95 %
bound, not a covariance" replaces the sentence on what version 0.1 lacked. Table 18 has eight rows "calculated from assumed inputs".

### Final tally of the 44 findings

| Status | Count | Findings |
|---|---|---|
| Fixed | 34 | M1 to M6, M8 to M15; S1 to S8, S10 to S13, S16; O1, O2, O5, O7 to O10 |
| Fixed in part | 6 | M7 (the censored part of the alone loss is given in items, not in USD; the value of time is not swept); S9 (the retry budget is stated, not swept; the lost-link return is not driven in the engine); S14 (missing dates, initials and titles are not in the research notes; one arXiv identifier not re-checked; Table 2's cells print the catalogue's flags); S15 (P3's side only); S17 (items 1, 2 and 3 in part, item 4 done; the other new experiments are listed in 6.6 as not run); O4 (task numbers and the list of skipped checks kept) |
| Not done | 4 | S18 (not split, by the lead's decision; a roadmap and explicit halves instead); O3 (199 jobs against 200.9 awards a seed, unexplained); O6 (CoreMark not run on the laptop); O11 (P1's text) |

## Second pass, part 4 (12 Nov)

1. The driving split is now given at the packet sizes of protocol version 0.2, from `results/E53_bitrate.json`, `lrip_v02.driving_split`
   (Sections 5.2, 5.11 and 7). Drawn from driving steps, 20 rovers at 1 Hz: busiest link 6.28 kbit/s (was 5.89 at v0.1 sizes); scheduled
   airtime 7.85 kbit/s, 10.19 in Proximity-1 frames (was 7.37), within the target; slotted random access 17.1, 22.2 framed (was 16.02), above
   it. With status and intent at 1 Hz: 20.03 kbit/s at the sources, 25.98 framed (was 19.52, the three reports without the heartbeat);
   scheduled airtime 25.0 and 18.8 kbit/s, 32.5 and 24.4 framed (was 24.4 and 18.3), above the target in every case. Hops (1.58) and the share
   with a path (93 %) do not depend on the version and are unchanged. The sentence that these were version 0.1 figures is gone; Section 5.11
   states that the E54 replay was not rerun with version 0.2. No verdict moved.
2. P1's learned-bid rerun: P3 quotes no learned-bid result and no 92.9 %. Its only statement, that the linear model improved on hand-built
   bids and the network did not (Section 3.4), agrees with P1's revised abstract; nothing was changed.
3. Abstract 300 words, conclusion 248. The tally of the 44 findings does not move (34 fixed, 6 fixed in part, 4 not done).

## Part 5 (13 Nov)

1. B-111 (`results/E54_dtn.json`, block `lrip_v02`): the one sentence that said the E54 replay was not rerun with version 0.2 (Section 5.11) now
   says it was repeated at version 0.2 sizes and in Proximity-1 frames with no value and no verdict changed. Section 5.12 gives the reason:
   the replay sends task awards, reservation grants and task states (92, 94 and 33 B; 104, 106 and 45 B framed), whose sizes version 0.2 does not
   change, and a size counts only against the 64 MB store, 0.37 MB at most with every message of a seed held at once. Section 7 and H14's row
   of Table 18 say the same. It is called a property of the replay's message set, not a test of version 0.2. The build checks row by row that
   the v0.2 and framed rows equal the v0.1 rows and stops if they ever differ. Future work had no such sentence and is unchanged.
2. Reference [60] carries P1's new title.
3. The tally of the 44 findings does not move (34 fixed, 6 fixed in part, 4 not done). No verdict moved.

## Part 6 (13 Nov): corrections after the code review

Source: `reports/review_phase6_code.md` and the dated entry of PREREG6 section 6. Every value is read through the build from the corrected
results file, and each earlier value from that file's `superseded_...` key. Build: passes with `--no-pdf`, without `--allow-pending`;
abstract 298 words, conclusion 249; PDF not rebuilt (memory).

Corrections after code review:
- **E52 (N1), 5.10, 6.1, Table 13.** Stale-map hits after contact at most 0.40 (hazards first) and 1.72 (oldest first), were 0.08 and 1.65; one day
  out of contact 0.78, was 0.80. Bytes, times and H12 unchanged (checked row by row).
- **E54 (N3 to N7), 4.2, 5.12, Table 15.** Age of information with the rule 9.5 s (worst vehicle 39.9 s), was 45.5 s (2.5 min); task-state
  reports 3.4 s with none lost, were 33.0 s with 2 lost; grants lost with the rule 3, were 0 (at loss 0.40: 29 and 22 in the table); returns
  87.3 a seed, were 82.1. A message still alive at the window's end is now "censored", not lost. The return rule is the one the paper states;
  the earlier rule is a variant (age of information 20.9 s). H14's first clause is unchanged under both definitions and both rules. The second
  clause: "holds by rule, not by measurement" (the file's words), beside the statement that the release rule is withdrawn (decision B1).
- **E55 (N9, N16), 5.11, Table 18.** The first replay trial (1,172 replays, none accepted) is said to draw from the whole log, with about one in
  a hundred inside the window; the new trial, labelled as added after the review: none of 589 accepted at loss 0.10, 6 of 590 at 0.25, all six
  copies a receiver had missed and inside the window. H16's exactly robust evidence: three runs, 53 on a necessary condition only.
- **E48 (N12), 5.1, 6.1, 7, Table 18, abstract, conclusion.** One robot's bid, three passes without the memory tracer: 0.21, 0.30, 0.21 s at
  today's fleet; 0.92, 0.83, 0.77 s at four times; 0.94, 0.77, 0.79 s at eight times: under one second at the central factor in every pass,
  over it only towards the top of the factor's range at four and eight times the fleet. Was 0.29, 1.09 and 1.19 s, "above" at four and eight
  times. That verdict is withdrawn wherever it stood.
- **Verification (N2, N22), 3.10, 5.14.** 36 rows bear on P3, all pass. G1 is stated with its scope: one scenario, one seed, 30 days, 144
  summary values, against a stored run of commit 0210c22; one option switched on changes 14 of them.
- **Builder (review P2).** `core_ok`, `h12`, `s_map` (and `bid_sign`) were computed and never checked: deleted.
- **E56 (N10, N11).** P3 prints no E56 recall and no false-alarm interval; H15a's adjusted p now prints as a value (0.003), not "at most".
- **E50.** Untouched, as instructed; 4.6 and 5.14 say in one sentence that the position results predate a correction and are being regenerated.

Referee finding O3 is now fixed (4.2): 200.9 awards a seed are 199.3 jobs plus 1.63 two-vehicle team jobs, one award per vehicle.
Tally of the 44 findings: 35 fixed, 6 fixed in part, 3 not done (S18, O6, O11).

## Part 7 (14 Nov): E50 regenerated after the positioning fix

Every E50-derived value is read again from the regenerated files (commit 8f58d46). Build passes with `--no-pdf`; abstract 298 words,
conclusion 249. No verdict of P3 moved: H9' first clause supported, second "depends on the reading" (fails in every seed under the registered
wording), third not supported; H10' not supported as a whole (adjusted p 0.87, was 0.93).
- 5.8: dead reckoning alone 610 m at today's fleet (was 643), 883 m at four times (was 793), 988 m at eight times (was 906); ranging where two or
  more beacons are in view 4.28 m (was 4.22); registered wording 49.1 m (was 50.1); within 1 km 25.1 m (was 24.7); sweep at 10 m ranging
  error 10.1 m (was 9.64). The near-base readings now exist at eight times the fleet (4.48, 10.2, 21.8, 30.6 m), so the three sentences saying
  they were not computed are removed. One sentence names the earlier values.
- E50b: delay +0.65 h [0.06, 1.33], 3.7 % (was +0.63 h, 3.5 %). Reversed: "no run with stop time had a violation" becomes "with stop time one run
  of 30 had a violation and without it no run, a difference whose interval includes zero, so the stop time is not shown to add or to remove
  violations" (before the fix it was the other way round, and that is said once).
- The two sentences saying E50 was being regenerated (4.6, 5.14) are replaced by statements that it was regenerated.
- P3 prints no overlap count and no margin-violation count of E50; those are the companion paper's.
The tally of the 44 findings is unchanged (35 fixed, 6 fixed in part, 3 not done).
