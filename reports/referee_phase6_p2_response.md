# Response to the referee report on P2 (`reports/referee_phase6_p2.md`), 11-12 November 2026

Revision made under `reports/referee_phase6_decisions.md` (sections A and B). Files changed: `paper/p2/build_p2.py`,
`phase6.py`, `part1` to `part5`, `NOTES.md`, `PLACEHOLDERS.md`; `paper.html` and `values.json` rebuilt. The build now
runs without `--allow-pending`, stops if a `[[PENDING` string or a note to the authors would print, and `paper.html`
holds no such string. Every number below is written by the build from a results file or from `lunarsim/atc/safety.py`,
with a check. Two results landed during the revision and are in: E50b (`results/E50b_summary.json`, commit 35ae43e)
and E50 at eight times the fleet (`results/E50_summary.json`, 12 Nov 09:09).

Status words: **fixed**; **part** (fixed in part); **awaits** (a BACKEND task; one plain sentence stands in the text
and the build stops when the file appears, see `PLACEHOLDERS.md`, "Awaited results"); **not done**.

## MUST FIX

| # | Status | What was done | Where |
|---|---|---|---|
| M1 | fixed | The recommendation is withdrawn (decision B6). Abstract: "none kept its false-alarm rate with noisier sensors, so none qualifies for the safety path". 5.11 (d) gives the split by ranging class from `table_E56.csv`: CUSUM long range 1,016 false alarms per pair-day = 71 % of fault-free minutes, 98 % "found", median delay 18 s against 0 s on test; short range 28 per pair-day, 20 % and 13 %; network 21 % and 5 % at 3.3. Calibration loss: per-step chi-square x700, network x26. "Failed loudly ... still finding 40.2 % to 66.5 %" deleted; 6.1 says the detections cannot be told from false alarms and that no run prices R9's false alarms. Table 12 gains ten rows by class. "Keep the classical test" removed from 6.1 and 9. | abstract, 1, 5.11, Table 12, 6.1, 9, Table 14 |
| M2 | part; awaits B-102 | The overlap count is no longer a safety result (decision B5). 3.9 and 5.9 state that without a margin a back-to-back pair overlaps about half the time by construction (4x: 68 to 72 a month for errors from 793 m to 5.8 m), and that the count with the margin is the exceedance of the filed bound, not a test of Proposition 2 (circular). Durations with the margin: 8 to 241 s per run with an overlap (`E50_runs.csv`, all fleet sizes). Removed from the abstract and conclusion. Table 14: "Proved; the exceedance of the filed bound counted, not a test", plus a row "calculated: a property of the count". Durations and gaps without the margin: not computed, awaits `results/E50_overlaps.json`. | 3.9, 5.9, Table 10 note, 6.1, Table 14 |
| M3 | fixed | E50b is in. Abstract: "terrain fixes left 15 m elsewhere, and their stops, not the reservation margins, set the cost: 0.63 h per delivery (3.5 %, a lower bound)". 5.9: 18.37 h against 17.74 h, +0.63 h [0.02, 1.29], 22 seeds higher, 8 lower, paired t p 0.07, ratio to perfect 1.036, exploratory, lower bound (71 % of the stop time inserted). Stops are 37.3 h a month = 23 % of the 163 h of driving (`E50_errors.csv` `n_steps`); by arithmetic 0.15 h per delivery (250 deliveries); 25 % of fixes fell inside one-lane segments (`E50b_summary.json`). "Under 0.05 h" removed everywhere. | abstract, 1, 5.9, 6.1, 7, 9, Table 14 |
| M4 | fixed | Stated as observed (decision B7). Abstract: "A 0.1 s guard left no conflict in 303 reservation pairs with crystal clocks up to 0.84 s off, outside the guarantee." 5.10: no crystal cell meets Proposition 6's premise; worst pair closed 0.123 s of 0.2 s (62 %); 95 % upper bound 1.0 % per pair. The "No guard" column is explained as a count of signs. A.6: the 51 premise cells are 42 atomic and 9 crystal with the 1 s guard. H11 reported as an observation (its second condition could not fail: 1 ns = 0.3 m). | abstract, 1, 5.10, Table 11 note, 6.1, A.6, Table 14 |
| M5 | fixed | 3.5 defines the hard violation as `encounter.py` counts it, each clause checked against its source line: contact; same-road, same-direction gap below d0 = 5 m; any part of a vehicle in a closed zone; a moving vehicle inside its stopping distance of crew (R_stop less 10 m) or touching crew; opposing vehicles in one segment, a resource without a grant, slots over-full. "Below the required gap" replaced by "inside the 5 m static margin" everywhere. R1 breaches reported apart, but not as the referee states them (see "Referee findings not accepted"). | 3.5, 5.6, 5.8, 6.1, A.4, Tables 6, 7, 14 |
| M6 | fixed (rule and claims); cost not priced | Rule rewritten as decision B1: a silent holder's reservation is not released; after timeout plus grace the segment is marked unconfirmed and entered only at caution speed (Proposition 3: 6.4 km/h for 10 m of perception, 12.3 km/h for 20 m, class limit from 27 m). "No stuck reservation" withdrawn; H14's second clause "not testable as written". Reported: 2,566 of 2,628 reservations unconfirmed (7,349 h), 82 returns a seed against 199 jobs, radio path in 56.6 % of driving time, 336 h credited. Stated in 3.4, 5.12, 6.1, 6.4, 7 that no logistics run contains the ladder and that its cost is unknown and probably large (strict R7: +49 h). Table 2's R7 says the encounter and discrete models ran the rule as first written. | Table 2, 3.4, 3.11, 5.12, 6.1, 6.3, 7, A.3, A.4, Table 14 |
| M7 | fixed; the extra baseline not run | Labelled a calculation (decision B8): the lost share equals the per-hop loss (0.095, 0.256, 0.399, checked) because the retry interval (180 s) exceeds a grant's lifetime (60 s), both assumed; three tries would lose 0.25^3 = 1.6 % by arithmetic. "Custody is therefore part of the traffic rules" and "give grants custody" removed; the text says the replay does not show custody to be needed. A drop-and-retry row with a retry inside the lifetime needs a new run: listed in 6.5. | 3.11, 5.12, 6.1, 6.3, 9, Table 14 |
| M8 | fixed | Per variant, from `E44_bins.csv` and `results/E44_parts`: R3 as written 13 of 1,892 judged encounters (0.7 %; 0.26 % of 4,982 driven); keep-one-slot-free variant 373 of 1,963 (19.0 %; 7.4 % of 5,018); all-nominal 76 of 939. Mars: 2 of 368 and 68 of 395. The variant is described in 5.6. Abstract: "A one-lane ring deadlocked in 0.7 % of encounters under the rule as written." | abstract, 5.6, 5.8, 6.1, Tables 6, 7, 14 |
| M9 | part; awaits B-107 | A.4 states that (vii) fails for a conforming leader uphill: full braking exceeds b_max above 10.7 deg (Moon) and 4.6 deg (Mars), 11.5 deg at friction 0.3 on the Moon; on the 17.2 deg route maximum the final gap at 15 km/h is 3.0 m (Moon) and 0.2 m (Mars), all recomputed from `safety.py`. Proposition 4 is headed "for the flat and for downhill grades"; assumption (viii) added (the follower knows gap and speed). 3.5 and 7 say types 2 to 11 are flat and no encounter is uphill. Uphill encounters and the slope term in the rule: awaits `results/E45_uphill.json`. | abstract, 3.5, 5.6 (via 6.1), 6.1, 7, A.4, Table 14 |
| M10 | fixed | "The base saw 22 landings a year; their closures held a job or sent a vehicle to shelter 29 times". | 5.1 |
| M11 | part; awaits B-108 | The bounds of types 4, 5 and 6 are labelled as computed on the seeds used to find and fix defects (dagger in Tables 6 and 7, sentences in 1, 3.5, 5.6, 7, Table 14); "jointly at 95 % over the twelve types" removed from the introduction. Fresh-seed bounds: awaits `results/E44_fresh_seeds.json` (file name to confirm with BACKEND). | 1, 3.5, 5.6, Tables 6, 7, 14 |
| M12 | part | No pending string prints. Date line: "Preprint, October 2026, revised November 2026". [45] carries P3's title (checked against `paper/p3/part1_front.html`); [43], [59] no longer print "Cite by repository tag". [3], [10], [25], [58] are attributed to what was read (abstract; EASA's Easy Access Rules; published scope; a vendor's summary). [16], [37], [38] have titles from the research notes. Standard methods: named without citation, listed in `NOTES.md` as references to be added by the authors (the notes record no opened source). Not done: initials, venue and pages of [60] to [65], [71], [72], [79], and the paper behind [82]; the notes hold no more. | front matter, 1, 2, Table 1, Table 2, NOTES.md |
| M13 | fixed | All nine rows. Mars: "At Mars gravity only flat encounters could be driven; with Earth assumed in view half of every sol, referral cost one-sixth of its lunar cost." Method sentence: "one-month replays with position error, clock error, lost messages and wrong position reports". 0.1 %: "no measurable delay (0.1 %, upper bound 1.4 %) when reservations are filed with the job"; the strict-R7 figure (4.2-fold) is in the introduction. 5.1-fold: "at an assumed two staff hours each". 6.1 "policymaker" sentence replaced by the two assumptions. 6.3: the clause on the uncoordinated mode deleted. Table 14: Proposition 1 and 4 claims reworded as proposed. 5.7: "holds for the three rule clauses that were removed ...; R6 and R10 ... were not mutated, so the clause is met in part". | abstract, 1, 5.7, 6.1, 6.3, 9, Table 14 |

## SHOULD FIX

| # | Status | What was done | Where |
|---|---|---|---|
| S1 | part; awaits B-101 | H9' clause 2: "the verdict depends on the reading". The reading used (two or more of four beacons in line of sight) covers 23 % of driving steps, was written with the results, gives 4.22 m (largest seed 4.63 m) against 50.1 m over all driving. 4.6 lists the beacon rule, the hourly-maximum bound and the filter change. The other readings: awaits `results/E50_near_base.json`. | abstract, 1, 4.6, 5.9, Table 9 note, 6.1, Table 14 |
| S2 | fixed | 4.6 and 7 state that running nominal values only departs from PREREG6 section 2. | 4.6, 7, Table 14 |
| S3 | fixed | 4.5: the p values are constructions after the results; the sign test is one-sided (two-sided 0.0039); over the registered family of five the adjusted values are at most 0.005 (H15a) and 0.008 (H14). 4.1: "confirmatory" for H8 is this paper's label. | 4.1, 4.5, 5.12 |
| S4 | fixed | (i) the smallest margin that passes is 0.015 h, 0.09 % of the delay; the registered margin exceeds the between-seed SD (5.9 h). (ii) dead-reckoning margin costlier in 24 of 30 seeds, Wilcoxon p 0.003 (post hoc, said so). (iii) 4x perfect-position delay SD 12.9 h (4.0 to 46.8 h): "not resolved"; 8x now in (-0.25 h [-0.83, 0.26], 5 seeds). 6.1: "the experiment resolved neither". | 5.9, 6.1, Table 14 |
| S5 | part | Intervals for all five detectors on test; the weight of one alarm-minute in the heaviest stratum (0.11 per pair-day; no alarm in 152 h allows 0.33); "113 times" dropped; single test 53 against 84 minutes at 10.83 and 4.8 against 8.6 at 15.14, so the innovations are not Gaussian with the claimed variance; A.5 calls 19.1 against 19.2 one crossing point. Not done: the count of alarm-minutes behind 0.098 and its interval are not in any results file. | 5.11, A.5, Table 14 |
| S6 | fixed | (i) "every vehicle is in all three". (ii) 3.12 now gives E56's own model (2 % of distance, fix to 1.7 m at stops and every 100 m, no filter, no terrain). (iii) common-found difference -23.2 s [-26.8, -19.9]. (iv) the interval of H15 (b) is stated as 90 %. | 3.12, 5.11, Table 12 note |
| S7 | fixed | The three qualifications are in 5.11 and under Table 13: settings differ from E56's (window 16 against 5, k 0.5 uncentred against 3 centred); SMAP gain with 18 and 26 false-alarm runs against 2; the z-score and per-step columns are one detector; channels are the first 14 by file listing. "The check supports no choice of detector." | 5.11, Table 13, Table 14 |
| S8 | part | 5.4 and 6.1: 37.2 h of wait per conflict against 2 h of staff time, t_hand not swept, no local fallback. 5.1 says two vehicles do most of the driving. Not done: the Mars fleet's 94 against 53 conflicts is still untraced (needs engine analysis); the 95 % figure is from `.cache`, not a results file, so no number is printed. | 5.1, 5.4, 6.1, Table 14 |
| S9 | fixed | 3.4, 6.1, 6.4 and 7 state the oracle dispatcher (checked: every E43 row has `regime` O_ORACLE), windows computed at commit and kept exactly, no travel-time uncertainty, no lost-link procedure, 56.6 % contact; 7 says E50 covers position error and not timing error. | 1, 3.4, 6.1, 6.4, 7 |
| S10 | fixed | (i) Table 6 and 7 gain "finished" and "incomplete"; 22 %, 36 %, 10 % in the text. (ii) 3.5: the 0.5 m/s2 brake is below g sin 20 deg = 0.55 m/s2. (iii) 58 of 3,316 dead-stop encounters (1.7 %). | 3.5, 5.6, Tables 6, 7 |
| S11 | fixed, except one reference | P1: "illustrates ... does not test the formula". P2: new paragraph on the constant-speed premise (6.5 s from rest for 4.2 m against a 1.0 s margin; the stop line; v is the leg's mean speed in `roads.py`). P3: "holds its speed through a reaction delay"; R2 against R1; the NASA figure "validates nothing". P4: (iii) and the dead vehicle; uphill (M9). P6: outside the headline case. P7: no-delay assumption added; "18 %" replaced by 10 % (16 % with the mast) for cells where F covers the faulty rovers. Not done: LeBlanc et al. 2013 not read (listed in NOTES.md). | 1, 6.1, A.1 to A.7 |
| S12 | part | 2.6 limits the novelty statement to the works read and names the fields not searched (single-track signalling, mine haulage, AGV zones, RNP, vehicular misbehaviour detection, RAIM, delay-robust path finding); Table 1 says so. Not done: none of these sources is in the research notes as opened, so none is cited (decision A5). | 2.6, 2.7, NOTES.md |
| S13 | fixed in P2 | H9', H10' used throughout and explained in the roadmap; H9 without a prime is always Mars. The lost-link rule is now the one of decision B1. P1's title for P3 is outside this paper. | 1, 4.1 |
| S14 | part | 7 says what the Phase 6 verification rows do not check. Not done: bound coverage per seed is not in a results file (the referee's 97.1 % is from `.cache`). | 7 |
| S15 | fixed | 3.6: R6 is checked on each move, not as a state invariant. | 3.6 |
| S16 | part | Limitations added: no travel-time uncertainty; no lost-link ladder in the logistics runs; one month; the bound comes from another run, so the remainder is not shown to be outside a correct bound; 60 s sampling; one-sided crystal draw; one out-of-distribution shift. The controls are listed in 6.5; none was run here. | 6.4, 6.5, 7 |

## OPTIONAL

| # | Status | What was done | Where |
|---|---|---|---|
| O1 | fixed (not split, as instructed) | A roadmap paragraph ends the introduction: which sections, experiments and hypotheses belong to each body of work. | 1 |
| O2 | not done | No new figure or map; needs drawing work outside this pass. | |
| O3 | part | "Pair-day" defined; "B-97" removed from Table 14. The long lists in 5.6 and 5.13 stay. | 4.2, Table 14 |
| O4 | fixed | H11's second condition is called a calculation that could not have failed; H11 is out of the abstract-level claims. | 5.10, Table 14 |
| O5 | fixed | 0.014 m/s2, at the lowest friction value. | 5.8 |
| O6 | fixed | "25 min at today's fleet, where its cost of 0.12 h was not resolved, and 27 min at four times the fleet, where it cost 2.1 h". | 6.1 |
| O7 | fixed | One sentence: one month under the auction against a year under the oracle. | 5.9 |
| O8 | not done | Who checked the references, and when, is for the author to state. | |

## Referee findings not accepted as written

- **M5, last sentence of the proposed text** ("Gaps below R1's d_min while the follower is not braking are counted
  separately and were zero in every type"; the report cites `r1_breach_rate` 0.0 in every type). `results/E44_bounds.json`
  holds `r1_breach_rate` 0.0003 for types 3 and 10 and 0.001 for type 6; the part files store the flag per encounter.
  The paper says: 3 of 10,000 encounters in types 3 and 10, 10 of 10,000 in type 6, none in the other nine.
- **M8, denominators.** The report gives 13 of 4,982 (0.26 %) and 373 of 5,018 (7.4 %), which are over all driven
  encounters, while noting that deadlock is judged only without a random fuzzer. `results/E44_parts` holds the planner
  mix per encounter: among judged encounters the rates are 13 of 1,892 (0.7 %) and 373 of 1,963 (19.0 %). The paper
  gives both; the abstract uses the judged rate.
- **M3 and M12, E50b and the 8x cells "not in".** Both landed during the revision and are reported from their files.
  The report's provisional +0.61 h from 9 seeds became +0.63 h [0.02, 1.29] on 30.

## Counts

37 findings. Fixed: 24 (M1, M3, M4, M5, M6, M7, M8, M10, M13; S2, S3, S4, S6, S7, S9, S10, S11, S13, S15; O1, O4,
O5, O6, O7). Fixed in part: 7 (M12, S5, S8, S12, S14, S16, O3). Fixed in part and awaiting a BACKEND task: 4 (M2:
B-102; M9: B-107; M11: B-108; S1: B-101). Not done: 2 (O2, O8).

## Second pass, part 1 (12 Nov)

Two BACKEND results landed and are composed from their files (simulation in both cases), with data checks; both are
out of `AWAITED`. Build: `build_p2.py --no-pdf` passes, abstract 299 words, conclusion 250, 0 pending, no "PENDING" in
`paper.html`. E50 at eight times the fleet had already landed and is in (first pass).

| Finding | Status now | What was done | Where |
|---|---|---|---|
| M11 (B-108, `results/E44_fresh_seeds.json`) | closed | Types 4, 5, 6 rerun on seeds never used, 10,000 each; both seed sets in Table 6 with the reason. Types 4 and 5: no violation, bound 3.0e-4 (5.5e-4 Bonferroni) as before; ring 361 deadlocks against 386. Type 6: one hard violation in 10,000 (a vehicle inside the closed zone, no contact; replayed: hold-and-wait between R5 and R3). Quoted for type 6: the weighted limit 1.0e-3 (1.7e-3 Bonferroni); one sentence says why the unweighted 4.7e-4 is not comparable (it counts all driven encounters and falls below the zero-violation bound on the effective n). The request rule of change 9 was rerun on that one encounter only (clean); "nothing is claimed for it" on the other 9,999. Every "no violation in eleven types" is now "ten of twelve" or "in the main run". | abstract, 1, 3.5, 5.6, Table 6, 5.8, 6.1, 7, 9, Table 14 |
| S1 (B-101, `results/E50_near_base.json`) | closed | H9' clause 2 under readings (a) to (e), ranging set, 1x: (a) 23 % of driving, 4.22 m, 30 of 30 seeds inside; (b) 57 %, 12.5 m, none; (c) 67 %, 24.7 m, none; (d) = (e) the registered wording, all driving, 50.1 m, none. 4x: 4.31 m under (a) in every seed, 32.1 m under the registered wording in none; 8x not run under the readings. Verdict "depends on the reading", and the text says the clause fails in every seed under the registered wording. | abstract, 1, 5.9, 5.13, 6.1, 9, Table 14 |
| M8, M5 (BACKEND's confirmation) | agree | The paper's 13 of 1,892 (0.7 %) and 373 of 1,963 (19.0 %), and R1 breaches of 3, 3 and 10 in 10,000 for types 3, 10 and 6, equal BACKEND's values; the build now checks the three rates. | 5.6 |

Still awaited, as plain sentences: B-102 (`results/E50_overlaps.json`, M2) and B-107 (`results/E45_uphill.json`, M9).
Updated tally: fixed 26, fixed in part 7, awaiting a BACKEND task 2 (M2, M9), not done 2.

## Second pass, part 2 (12 Nov)

B-102 and B-107 landed and are composed from their files with data checks; `AWAITED` is now empty. Kind of evidence:
simulation in both cases (B-102 is an analysis of the E50 runs; B-107 new encounter runs).

| Finding | Status now | What was done | Where |
|---|---|---|---|
| M2 (B-102, `results/E50_overlaps.json`) | closed | 5.9: windows filed back to back overlap in 43 % to 52 % of cases at 4x (134 such pairs a seed) for all four layer sets, 40 % to 60 % at 1x (42 pairs in 30 seeds); pairs filed apart at most 4 %: the count measures back-to-back pairs. Duration follows navigation (4x medians 417 s, 15 s, 6.7 s, 3.8 s). No overlap, with or without the margin, brought two vehicles within 5 m or within R1's gap; the first vehicle was about 440 m ahead at entry; 99 % are same-direction pairs on branched segments. The margin lowers the count and changes neither the gap at entry (441 m) nor the nature of an overlap. 8x: "were not analysed". The count stays out of the safety results. | 5.9, 6.1, Table 14 |
| M9 (B-107, `results/E45_uphill.json`) | closed | "By calculation" is replaced by the simulated result. A.4: 64 cells of 2,000 encounters, followers at the rule's limit, with and without a 1 s actuation lag. R1 as it was: no contact anywhere; gaps inside the 5 m margin on the Moon when following with the lag from 14 deg (14 of 2,000 at 15 deg, 335 at 17.2 deg, smallest 4.15 m), never in the lunar convoy; at Mars gravity with the lag from 6.5 deg (following) and 8.5 deg (convoy), down to 0.72 m, and at 15 deg and above without the lag. Slope term: none when following; 71 and 62 of 2,000 in the Mars convoy with the lag, at most 0.14 m inside (smallest 4.86 m), traced to the lag model, not patched. R1 in Table 2 is stated with the slope term as the proposed rule; the text says the twelve types were run without it, on the flat and downhill, where it is inactive (checked). The calculation (3.0 m on the route maximum) stays as the worst case of the formulas. | abstract, Table 2, 3.5, 6.1, 6.4, 7, 9, A.4, Table 14 |

Updated tally (37 findings): fixed 28, fixed in part 7 (M12, S5, S8, S12, S14, S16, O3), awaiting a BACKEND task 0, not
done 2 (O2, O8).
