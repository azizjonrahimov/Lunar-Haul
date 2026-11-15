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
| M7 | fixed; the extra baseline was run later (part 11), and the 1.6 % below is corrected there | Labelled a calculation (decision B8): the lost share equals the per-hop loss (0.095, 0.256, 0.399, checked) because the retry interval (180 s) exceeds a grant's lifetime (60 s), both assumed; three tries would lose 0.25^3 = 1.6 % by arithmetic. "Custody is therefore part of the traffic rules" and "give grants custody" removed; the text says the replay does not show custody to be needed. A drop-and-retry row with a retry inside the lifetime needs a new run: listed in 6.5. | 3.11, 5.12, 6.1, 6.3, 9, Table 14 |
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
| S8 | part | 5.4 and 6.1: 37.2 h of wait per conflict against 2 h of staff time, t_hand not swept, no local fallback. 5.1 says two vehicles do most of the driving. Not done: the Mars fleet's 94 against 53 conflicts is still untraced (needs engine analysis; traced in part, see part 11); the 95 % figure is from `.cache`, not a results file, so no number is printed. | 5.1, 5.4, 6.1, Table 14 |
| S9 | fixed | 3.4, 6.1, 6.4 and 7 state the oracle dispatcher (checked: every E43 row has `regime` O_ORACLE), windows computed at commit and kept exactly, no travel-time uncertainty, no lost-link procedure, 56.6 % contact; 7 says E50 covers position error and not timing error. | 1, 3.4, 6.1, 6.4, 7 |
| S10 | fixed | (i) Table 6 and 7 gain "finished" and "incomplete"; 22 %, 36 %, 10 % in the text. (ii) 3.5: the 0.5 m/s2 brake is below g sin 20 deg = 0.55 m/s2. (iii) 58 of 3,316 dead-stop encounters (1.7 %). | 3.5, 5.6, Tables 6, 7 |
| S11 | fixed, except one reference | P1: "illustrates ... does not test the formula". P2: new paragraph on the constant-speed premise (6.5 s from rest for 4.2 m against a 1.0 s margin; the stop line; v is the leg's mean speed in `roads.py`). P3: "holds its speed through a reaction delay"; R2 against R1; the NASA figure "validates nothing". P4: (iii) and the dead vehicle; uphill (M9). P6: outside the headline case. P7: no-delay assumption added; "18 %" replaced by 10 % (16 % with the mast) for cells where F covers the faulty rovers. Not done: LeBlanc et al. 2013 not read (listed in NOTES.md). | 1, 6.1, A.1 to A.7 |
| S12 | part | 2.6 limits the novelty statement to the works read and names the fields not searched (single-track signalling, mine haulage, AGV zones, RNP, vehicular misbehaviour detection, RAIM, delay-robust path finding); Table 1 says so. Not done: none of these sources is in the research notes as opened, so none is cited (decision A5). | 2.6, 2.7, NOTES.md |
| S13 | fixed in P2 | H9', H10' used throughout and explained in the roadmap; H9 without a prime is always Mars. The lost-link rule is now the one of decision B1. P1's title for P3 is outside this paper. | 1, 4.1 |
| S14 | fixed (part 12) | 7 says what the Phase 6 verification rows do not check. Bound coverage per seed is now in a results file (`results/E50_coverage_sweep.json`, B-117 g, a control run after the results): 7, Table 9's note and Table 14 give it. | 7, Table 9, Table 14 |
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
| M9 (B-107, `results/E45_uphill.json`) | closed | "By calculation" is replaced by the simulated result. A.4: 64 cells of 2,000 encounters, followers at the rule's limit, with and without a 1 s actuation lag. R1 as it was: no contact anywhere; gaps inside the 5 m margin on the Moon when following with the lag from 14 deg (14 of 2,000 at 15 deg, 335 at 17.2 deg, smallest 4.15 m), never in the lunar convoy; at Mars gravity with the lag from 6.5 deg (following) and 8.5 deg (convoy), down to 0.72 m, and at 15 deg and above without the lag. Slope term: none when following; 71 and 62 of 2,000 in the Mars convoy with the lag, at most 0.14 m inside (smallest 4.86 m), not explained and not patched (the first explanation, one step more of earlier commands than R1 allows, was wrong: see part 10). R1 in Table 2 is stated with the slope term as the proposed rule; the text says the twelve types were run without it, on the flat and downhill, where it is inactive (checked). The calculation (3.0 m on the route maximum) stays as the worst case of the formulas. | abstract, Table 2, 3.5, 6.1, 6.4, 7, 9, A.4, Table 14 |

Updated tally (37 findings): fixed 28, fixed in part 7 (M12, S5, S8, S12, S14, S16, O3), awaiting a BACKEND task 0, not
done 2 (O2, O8).

## Second pass, part 3 (12-13 Nov)

Wording only; no finding changes status (tally stays: fixed 28, part 7, awaiting 0, not done 2).
- Uphill remainder now in the abstract and the conclusion: the slope term removed the shortfall when following; a Mars
  convoy with a 1 s lag kept shortfalls of at most 0.14 m (`results/E45_uphill.json`, through `uphill_sim`).
- Ring deadlock in the conclusion with both rates and denominators: 13 of 1,892 (0.7 %) under the rule as written, 373
  of 1,963 (19.0 %) with a variant. The numbers are read from `results/E44_parts` and `E44_bins.csv` (main run), not
  from `E44_fresh_seeds.json`, which holds only the pooled deadlock counts. The abstract has no room for the rate.
- The Artemis Accords closing sentence of the conclusion stays cut. The source itself was opened (the research note
  `traffic_and_safety.md` lists the signed Accords among the primary texts read, grade High, and records that they give
  policy without operating rules), so decision A5 would allow it; it stays out for the 250-word limit.
- To make room, the Mars sentence left the conclusion and lost its first half in the abstract.
- Reference [44] carries P1's new title (commit 52e7fd7): "Working Together Without Earth: Job Sharing, Team Lifts,
  Learned Bidding and a Message Protocol for Lunar Robots of Different Owners" (`paper/p2/NOTES.md` line 50, which the
  build reads); PDF rebuilt.

## Second pass, part 4 (13 Nov)

No finding changes status (tally stays: fixed 28, part 7, awaiting 0, not done 2). M11 stays closed; its row above says
the request rule "was rerun on that one encounter only", which is now out of date:
- The request-rule variant was run on all 10,000 fresh type-6 encounters (B-112, `results/E44_fresh_seeds.json` key
  `request_rule_fresh_6`). Sections 5.6, 6.1, 7 and Table 14 now say so, with every value read through the build: no
  violation against one; no encounter that finished under the rule as written fails; 3,781 finished under either rule;
  nine of the ten deadlocks and the violating encounter end incomplete (6,218, 62 %, against 6,208); paired delay
  change -0.035 s [-0.104, +0.0001]; bound 6.5e-4 (1.2e-3 Bonferroni) against the weighted 1.0e-3 (1.7e-3).
- The variant stays exploratory: it was chosen after seeing the violation, its bound is not a registered result, and
  the type-6 verdict (fails on fresh seeds under the rule as written) is unchanged. Each place says this.
- New build checks in `fresh_facts` (`paper/p2/build_p2.py`): the build stops if the variant has a violation, if the
  pairing counts are not 9 deadlocks and 1 violation to incomplete, if any finished encounter fails under the variant,
  or if the file's rule-as-written block is not the fresh-seed run of type 6.
- Limitations gains one sentence (B-113, `results/E44_defects.json` key `b113_stale_deadlock_flag`): the stored
  encounter files of types 2, 3, 4, 8, 9, 10 and 12 carried a deadlock flag from before the classifier fix in rows with
  a random fuzzer; no reported value reads those rows. The type list is read from the file. The files have since been
  regenerated (B-115, key `b113_stale_deadlock_flag.outcome`): 40 batches, 70,000 rows; the flag goes from 1 to 0 in
  14,071 rows, all with a random fuzzer, and from 0 to 1 in none; no other column differs and the rebuilt bounds,
  encounter and bin files are unchanged in every value. The sentence now says this, from the file (part 10).
- Abstract and conclusion unchanged (neither stated the one-encounter fact). New placeholder `P2-REQRULE-LIMITATION`.

## Parts 8 and 9 (13-14 Nov): corrections after the code review

These follow `reports/review_phase6_code.md`, not the referee report, so the referee tally does not move (fixed 28,
part 7, awaiting 0, not done 2). Every value below is read through the build from the regenerated files; the earlier
value is named once in the paper where listed. No verdict moved: H10 is still not supported as a whole and its
equivalence clause holds.

Code-review findings touching P2:
- N2 (options-off row): the verification paragraph gives the check with its scope; 56 rows, commit `bbbd8f5`
  (`results/vv_phase6.json`).
- N8 (H15a's p), N10 and N11 (detector recall and false-alarm intervals): recalls are on quiet events (CUSUM 84.2 ->
  69.3 %, per-step chi-square 79.2 -> 73.2 %, network 66.0 -> 65.1 %), false-alarm intervals on 1,000 resamples.
  Table 12 has a note, not new columns: the quiet-event recalls exist only for the test and out-of-distribution blocks.
- N14, N15 (position model, E50): all E50 text and Tables 9 and 10 follow `results/E50_summary.json`,
  `E50_overlaps.json`, `E50b_summary.json` and `phase6_family.json` at 1x, 4x and 8x. Dead-reckoning p95 643 -> 610 m;
  ranging overall 50.1 -> 49.1 m; overlaps without a margin 1.87 -> 1.43 a seed (median 334 -> 548 s); with the margin
  none at 1x (was 1 in 30 under each), 0.3 and 2.3 at 4x, 0.0 and 3.6 at 8x; layered gap at 4x -0.87 h [-2.00, -0.01]
  -> -0.49 h [-1.36, 0.05]; H10 p 0.93 / 0.77 -> 0.87 / 0.66; E50b +0.63 h -> +0.65 h [0.06, 1.33]. Abstract: 50 m ->
  49 m, 0.63 h -> 0.65 h.
- N23 (actuation-delay buffer): Appendix A.4 defines the delay-aware R1 breach count and names the earlier rates (none
  of the 32 cells with the lag has a breach; counted on the command at once, five had 0.05 % to 15 %). Amended in
  part 10.
- The E54 paragraph carries the regenerated message age (9.5 s; earlier 45 s, worst 149 s). Amended in part 10.

Sentences reversed or removed:
- "The same overlap count for every layer set at four times the fleet": dead reckoning alone now has 84 a month against
  67 to 68 for the three sets with ranging.
- "No overlap occurred in any seed with the stops": 1 of 30 seeds with, 0 without; the paper now says overlaps say
  nothing either way.
- "The eight-times cells were not analysed" and the provisional sentence in `part5_back.html`: removed; the 8x readings
  and overlaps are in the text.

Proposition 1 illustration (two steps):
- Part 9 first printed 81 m after one driving hour, 244 m after five, 240 m after eight, and said the level stretch was
  not traced.
- BACKEND then traced it (reading only): the curve bins cumulative driving hours since the window start
  (`tools/atc/run_e50.py`, `shift_curve`) and few vehicles drive that long, so the points beyond the fourth hour rest on
  a few vehicles a seed. The paper now says the level stretch is within that noise and that the error still grows: 0.62 km
  beyond eight driving hours (0.65 km before the fix), and a rise in every hour at 4x and 8x (344 m and 470 m after
  eight). The curve values are read from `errors.<m>.dr.shift_p95_m_mean_over_seeds`. The file does not hold the number
  of vehicles in each hour or the seed-to-seed spread, so the paper states those in words, without numbers.
- New build checks (`paper/p2/phase6.py`, `prop1`): the curve has eight hourly bins and one beyond; the bin beyond is
  more than twice any hourly value; at 4x and 8x every hour is above the one before.

Builder: eight defects fixed in `paper/p2/build_p2.py` (no typed-in fallback values); the R1 breach pin covers four
lines of `lunarsim/atc/encounter.py`.

Not done: the position-error percentiles in the errors paragraph and the cells of Tables 9 and 10 do not name their
earlier values one by one; the limitations sentence points to `superseded_2026-11-13_b118_n15`.

## Part 10 (14 Nov): second correction pass (review fixes B-115 and B-120, E54 rerun)

HTML only (`build_p2.py --no-pdf`, all checks pass, abstract 300 words, conclusion 250); the PDF is not rebuilt. Every
value is read from the results files through build checks. Everything is simulation.

- E54 ledger split (`results/E54_dtn.json`, code `c3c3b2880e33888c`). The E54 paragraph (5.12) ends with a second
  correction note: of 930 daily Earth ledgers, 690 undelivered under custody at every loss rate; 300 expired and 390
  still alive at the window's end (32.3 %), where the file first gave 270 and 420 (29.0 %). Cause: one ledger a seed
  whose 14-day lifetime ended exactly at the end of the window is now counted expired, not censored. The paper had
  printed none of these counts. Checks (`phase6.py`, `results_paragraph`): the file holds exactly the two superseded
  blocks and each is read by its key; apart from the three ledger fields of the store-and-forward rows every field of
  every row equals the `superseded_2026-11-14_b120_b` block; H14 and its variants are equal; the main table and the
  three size sets agree; the move is one ledger a seed and the undelivered total is unchanged.
- Uphill remainder (A.4, 6.1, 7, Table 14). "One 0.1 s step more of its earlier commands than R1's response time
  allows" was wrong for these cells and is removed. The text now states what `lunarsim/atc/encounter.py` does: a
  follower applies the command it gave 1 s earlier (a queue of ten 0.1 s steps), so braking commanded when the gap
  goes below R1's distance takes effect at the response time; the check decides each step from the current speed and
  gap and is not given the queued commands. The remainder (at most 0.14 m) is stated as not explained and not patched.
  With the slope term the remainder occurs only in rows with the lag (71 and 62 of 2,000, Mars convoy, 15 and
  17.2 deg), none without it (checked from the file). One candidate cause, a one-step detection latency, was refuted
  by BACKEND in a scratch check that is in no results file; the paper prints nothing from it.
  The breach count's definition gains "time below taken at the end of the step" (B-120 A). BACKEND reran the 16 delay
  cells (32 rows, each cell under both rules) on the corrected counter: every value equal, breach rate 0 in all 32.
  The text says so, and the build checks the file's `delay_cells_code_note` and that `delay_cells_code` equals
  `run_e45_uphill.code_fingerprint()` on the current code (the fingerprint is not typed). The pin of the breach lines now covers five
  lines (the counter line added); three new checks tie the lag-model sentences to the source.
- E44 stored files: see the amended bullet in part 7. New checks on the `outcome` record (types, totals, no flag from 0
  to 1, no other column, published files unchanged).
- Age of the base's knowledge: "as young as it can be" removed. The text gives 9.5 s against the floor of 5 s (half
  the 10 s reporting period): 4.5 s above it, 1.9 times. Check: between the floor and one period at every loss rate.
- Prose now tied to checks: the overlap counts with a margin by fleet size ("no trend" was wrong for the layered
  margin: 0.0, 2.3, 3.6 a month at 1x, 4x, 8x, intervals at 4x and 8x overlapping; no direction under the
  dead-reckoning margin); "no verdict moved" for the near-base readings (same number of seeds inside the budget under
  each of the five readings before and after); the typed "fourth hour" in the Proposition 1 illustration is removed.
- Typed run times removed: E50's "1.5, 11 and 42 minutes" a cell (no results file holds them) and the "nine minutes"
  and "five minutes" limits in 4.7. The run times that remain are read from files.

Not verified by the build: that few vehicles drive more than a few hours (BACKEND's trace). The cause of the uphill
remainder is unknown.

## Part 11 (14 Nov): two control runs (B-117 d, e1 and h)

HTML only (`build_p2.py --no-pdf`, all checks pass, abstract 300 words, conclusion 250). Everything is simulation.
Tally unchanged: M7 was already counted fixed and its missing baseline is now run; S8 stays "part" (the hand-resolution
time is still not swept, and part of the conflict gap is still untraced). Fixed 28, part 7, awaiting 0, not done 2.

- M7, correction (`results/E54_retry_budget.json`, `tools/atc/b117de_retry.py`). The paper printed "three tries inside
  the lifetime would by arithmetic lose 0.25^3, 1.6 %" (5.12, 6.5, Table 14; 3.11 did not print it). The run gives
  6.7 % (406 of 6,028 grants) at a loss of 0.25, 0.9 % at 0.10 and 16.8 % at 0.40. Cause of the error: the arithmetic
  assumed a radio path at every try and independent failures; the three tries span 40 s and the contact plan has 60 s
  steps, so a vehicle without a path mostly has none at any of them. Five and ten tries every 20 s lose 6.7 % too.
  The 1.6 % stays only as the independent-tries figure, labelled as not the result, and 5.12 records that an earlier
  version gave it. "The replay does not show that custody is needed" is removed: retry inside the lifetime 6.7 %,
  custody 0.03 %. The published budget (5 tries every 180 s) reproduces E54's drop-and-retry cells: the file's flag,
  and the build compares n, lost, censored and lost share of all four message kinds at the three loss rates, and the
  H14 difference.
- H14 (control e1, same file): 5.12 now says the first clause is supported at the retry budget chosen, and that over
  the twelve budgets the interval excluded zero at ten; with ten tries every 20 or 60 s drop and retry lost 0.07 jobs
  a seed and the interval reached zero. Labelled exploratory.
- S8 (`results/B117h_conflict_trace.json`, exploratory, not pre-registered). "We have not traced the cause" is
  replaced in 6.1 by the trace: 120 runs with counts equal to the stored rows; one segment holds 96 % (Moon) and 97 %
  (Mars) of the conflicts; lunar cells (waits 37 and 56 h) 53 and 45 conflicts a year, Mars cells (5 and 8 h) 92 and
  94; 0.009 against 0.77 conflicts per 100 h while a pair waits; a wait in force 22 % of the lunar year against 8.5 %
  on Mars; the count ratio 1.78 = 1.18 (time without a waiting pair) x 1.51 (rate in that time); 51.5 against 32.1
  conflicts per 1,000 traversals. The cause of the higher rate is stated as not traced.
- Limitations and future work: "a drop-and-retry baseline whose retry fits inside a grant's lifetime" removed from the
  list in 6.5; 6.4's "custody or a retry inside its lifetime" now says custody, since retries inside the lifetime
  still lost grants.
- New build checks: `phase6.py` `retry()` (ten checks), `build_p2.py` `conflict_trace()` (nine checks).

Differences from the task as given, from the files: "97 % on one segment" is 96 to 97 % by cell; "conflicts fall as the
wait grows" does not hold between the two Mars cells (92.1 at 5.4 h, 94.0 at 8.0 h), so the text says so; "about a
third of the gap" is not a number in the file (the factors give 28 % of the log ratio), so the factors are printed;
the 1.5 is the rate per 100 h outside waits, and per traversal the ratio is 1.6.

## Part 12 (15 Nov): three control runs (B-117 g, j1, j3)

HTML only (`build_p2.py --no-pdf`). Everything is simulation; all three are control runs made after the results and
not pre-registered, and the text says so. Every value is read from the files through build checks.

Tally: S14 moves from part to fixed (bound coverage per seed is now in a results file). Fixed 29, part 6 (M12, S5,
S8, S12, S16, O3), awaiting 0, not done 2 (O2, O8).

- g (`results/E50_coverage_sweep.json`), Section 7: "an overlap that remains with the margin may therefore come from
  that mismatch ..., and how often the error is inside the vehicle's own bound is not in the results files" is
  replaced. Now: in the margin runs the bound filed from the perfect run covers 99.4 % of the layered run's driving
  steps (lowest seed 95.0 %) and 96.2 % of the dead-reckoning run's (lowest 75.7 %), against 97.4 % and 96.0 % for
  each run's own bound, so the remaining overlaps are not explained by a bound that is too small. With ranging the own
  bound covers 97.0 to 98.4 % on average and at least 95.5 % in every seed; dead reckoning 96.7 % but 76.1 % in one
  seed. Table 9's note gives the four layer sets; Table 14's Proposition 2 row replaces "whether each remaining
  overlap is an error outside a correctly computed bound is not shown". "How often each vehicle's error is inside its
  own bound" is removed from future work.
- j1 (same file): P2 printed no 6-seed sweep, so no value or table changes. 5.9 gains the sweep (four ranging inputs
  one at a time, 30 seeds): at the defaults 4.28 m with two or more beacons, 21.6 m with one, 69.1 m with none; by
  distance 25.1 m within 1 km and 75.4 m from 1 to 5 km; no point brings one beacon or none within 5 m (best 12.9 m);
  with two or more the budget fails in some seeds only at long-range error 10 m (0 of 30), reach 50 m (8), survey
  error 1 m (16) and 0.5 m (29). Section 7's "nothing else was swept", 4.6's deviation sentence and Table 14's
  parameters row now name the sweep.
- j3 (`results/E51_clocks_m4.json`): 5.10's H11 sentence and Table 14's H11 row gain 4x: rule met at the same
  intervals (10 s to 6 h), 10 seeds, 4.5 times the reservations a seed; daily resync 5 conflicts in 2 of 10 seeds
  (lunar scale; 1 in 1 of 30 at 1x) and 6 in 4 of 10 (Earth scale; none at 1x); never resynced 365 against 15. The
  E51b file at 4x is not used (P2's variants sentence is at 1x).
