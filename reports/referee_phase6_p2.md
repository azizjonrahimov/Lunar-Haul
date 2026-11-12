# Referee report: P2, "Rules of the Road on the Moon and Mars" (build of 11 November 2026)

Independent review of `paper/p2/paper.html` against the results files, the code and the two pre-registrations.
Nothing in the paper or the code was edited. Every number below was read from the named file or recomputed
from it; `values.json` and the build's own checks were not used. Scripts ran with `.venv\Scripts\python`.

## 0. First reading, before any check

What a reader takes away:
1. The rules cost almost nothing at today's fleet (0.1 % of delay) and 42 % at eight times the fleet.
2. Keeping the reservation table on Earth instead of on the Moon multiplies delay by five.
3. The safety program is clean: no violation in eleven of twelve encounter types, an exhaustive check of 47,085 states, and the one failure (a dead stop) is explained by a proposition.
4. Without satellite navigation the rules still work: ranging holds 5 m near the base, and a margin sized from each vehicle's own bound removes reservation overlaps for almost no delay.
5. A small network detects wrong position reports sooner than a chi-square test but fails out of distribution, so the classical test is kept.

What I believed least, and what the check found:
- "Widening cut overlaps from 0.7 to 0.03 a month for under 0.05 h." Found: the baseline count is a coin flip on back-to-back windows and the delay leaves out the scheme's main cost (M2, M3).
- "The network failed out of distribution, so the classical test stays in the safety path." Found: the classical tests' out-of-distribution "recall" is coincidence with near-continuous false alarms (M1).
- "A 0.1 s guard made crystal clocks resynced every six hours safe." Found: the clocks in that cell were up to 0.845 s off; the proposition's premise does not hold there (M4).

## 1. Summary of the paper as I understand it

The paper proposes ten traffic rules (R1 to R10) for surface vehicles of several owners at a lunar base and one
"safety program" that refuses any planner proposal that breaks them. The same check function is used in three
models: an explicit-state search of a 12-node discrete model (E45), a 10 Hz encounter simulator with twelve
encounter types (E44, 274,580 driven encounters), and a year-long logistics simulation in which one-lane segments
are reserved at job commit (E43, 650 runs). The measured cost of the rules with one shared reservation table is
0.01 h per delivery at today's fleet, rising with fleet size; with per-owner tables and conflicts settled by hand
from Earth the delay is five times the baseline. A Mars variant changes gravity and the Earth link. A second
block of work, pre-registered and run on 11 November 2026, replays one recorded month to study position error
and a time margin on reservations (E50), clock error and a guard (E51), message custody and a lost-link rule
(E54), detectors of wrong position reports including a 9,529-parameter network (E56, E55), trimmed-mean agreement
(E55) and one check on spacecraft telemetry (B-97). An appendix states seven propositions and Section 8 sorts
every claim into proved, tested, assumed or untested.

## 2. Recommendation: major revision

1. Several headline results of the second block are properties of the design or comparisons the paper itself says must not be made, and the abstract and conclusion draw design advice from them (M1, M2, M3, M4, M7). The evidence does not support "the classical test stays in the safety path", "made crystal clocks safe", or a delay cost quoted without the stops the scheme needs.
2. The safety evidence is weaker than its presentation: "hard violation" is never defined and is not a breach of the rule it is described as (M5); the ring-deadlock rate pools the rule as written with an unreported variant (M8); the per-type bounds for three types are computed on the seeds used to find and fix defects (M11); assumption (vii) of the no-collision proposition fails for a conforming vehicle on an uphill grade that the base's roads contain and no encounter generates (M9); and the lost-link rule that the paper recommends is neither in the priced runs nor safe for a vehicle that is silent because it is dead (M6).
3. The manuscript is not in a submittable state: three "[[PENDING ...]]" strings in the body, a placeholder reference, a front-matter date a month before its own second pre-registration, standard methods without citations, and the closest prior work characterised from an abstract (M12).

The first block (E43, E44, E45, E47) reproduces from the raw files to the last digit and is reported with unusual
candour about what failed. That part is close to publishable after M5, M8, M9, M10, M11.

## 3. MUST FIX

**M1. Abstract, Sections 5.11, 6.1, 9: "the network failed out of distribution, so the classical test stays in the safety path" is not supported; the classical tests' out-of-distribution recall is chance.**
Evidence, `results/table_E56.csv`, set `ood`, rate `1/pair-day`, by `range_class`:

| Detector | class | false alarms per pair-day | recall, small jumps | recall, slow drifts | median delay on jumps |
|---|---|---|---|---|---|
| chi-square per step | UWB | 14.2 | 0.062 | 0.064 | 114 s |
| chi-square per step | long range | 564 | 0.862 | 0.842 | 58 s |
| CUSUM | UWB | 27.6 | 0.199 | 0.129 | 52 s |
| CUSUM | long range | 1,016 | 0.979 | 0.954 | 18 s |
| network | UWB | 3.3 | 0.210 | 0.053 | 27 s |
| network | long range | 15.8 | 0.237 | 0.145 | 60 s |

A false alarm is a 60 s bin; 1,016 per pair-day is 71 % of all minutes, 564 is 39 %. Faults last 120 to 600 s
(`lunarsim/nn/faults.py`, `EVENT_S`). A detector that alarms in 71 % of minutes "finds" nearly every fault by
coincidence, and the median delay on jumps, 0 s in distribution, becomes 18 to 60 s, which is what an alarm
unrelated to the onset gives. Where the innovation tests are not alarming continuously (UWB class) they find 6 to
20 % of the small faults, against the network's 21 % of jumps and 5 % of drifts at a quarter to an eighth of
their false-alarm rate. The sentence
in 6.1, "The innovation tests failed loudly ... still finding 40.2 % to 66.5 %", therefore reports false alarms
as detections, and uses the unequal-rate comparison that the note under Table 12 forbids. Three further facts
cut against the recommendation: (i) calibration loss was largest for the classical tests (per-step chi-square
0.68 to 479 per pair-day, a factor 700; network 0.53 to 13.8, a factor 26); (ii) with thresholds reset, every
detector finds 1 to 3 % of these faults, so nothing separates them; (iii) the rule the protocol would actually
run, three of five at 10.83, found 26 % and 25 % at 69 false alarms per pair-day (`results/E55_table.csv`), no
"louder" in recall than the network's 23 % and 11 % at 14. R9 turns every false alarm into an inflated volume and
delay; no run prices 69, 479 or 863 false alarms per pair-day, so "fails towards alarms" is not shown to be the
safe direction.
Smallest fix: delete the causal "so". Abstract: "... the network failed out of distribution, and so did every
other detector: none kept its false-alarm rate, and at a restored rate none found the small faults. We keep the
chi-square test in the safety path because its threshold follows from a stated assumption, not because it
performed better." Section 6.1: replace "still finding 40.2 % to 66.5 %" with the class split above and say that
those detections are not distinguishable from false alarms. Add the per-class rows to Table 12.

**M2. Abstract, Section 5.9, Table 10, Table 14: "cut true-time overlaps from 0.7 to 0.03 a month" compares a count that is fixed by construction, and its size is never reported.**
Evidence: `tools/atc/run_e50.py`, `violations()`: a waiting vehicle's nominal window starts exactly where the
conflicting one ends, each end is shifted by (along-track error)/(speed), and any positive overlap counts. With
zero gap a pair overlaps whenever the two shifts have the unfavourable order, about half the time, whatever the
size of the error. `results/E50_errors.csv` confirms it: at four times the fleet the count is 71.5, 69.0, 67.7
and 69.2 a month for 95th-percentile errors of 793 m, 32 m, 10.6 m and 5.8 m. The count measures how many
back-to-back conflicting pairs the month had, not a hazard that shrinks with better navigation. The overlap
durations without the margin are not in any results file; with the margin they are 8 to 23 s
(`results/E50_runs.csv`, `overlap_s`). The "test" of Proposition 2 is also circular: the simulation moves each
window by error/speed, which is the proposition's own premise, so E50 can only show how often the filed bound was
exceeded, not whether widening by k x bound / speed keeps real vehicles apart.
Smallest fix: report the distribution of overlap durations (s) and of the implied distances (m) with and without
the margin; say in the text and in Table 10 that without a margin every back-to-back pair overlaps with
probability about one half by construction; reword the abstract: "Reservations filed back to back overlap in true
time whenever positions are in error (0.7 pairs a month at today's fleet); a margin of 39 s at each end, sized
from the vehicle's own bound, left 1 overlap in 30 months." In Table 14 change "Proved; tested" for Proposition 2
to "Proved; the exceedance rate of the bound measured".

**M3. Abstract, Sections 5.9, 6.1, 9: the delay cost "under 0.05 h ... fix stops not counted" leaves out the larger part of the cost and should not be a headline number.**
Evidence: `results/E50_errors.csv`: 37.27 h of terrain-fix stops a month at today's fleet. `.cache/atc/e50`
(30 cells): 162.8 vehicle-hours of driving a month, so the stops are 23 % of driving time. 249.9 deliveries a
month (`results/E50_runs.csv`), so the stops alone are 0.15 h per delivery before any queueing, three times the
"under 0.05 h" ceiling and 20 times the reported +0.007 h. The follow-up run is in progress in `.cache/atc/e50b`
(not a results file; 9 of 30 seeds when read): with the stops in the engine the delay per delivery is +0.61 h on
average (per seed +0.67, +0.85, +0.13, +1.56, +0.66, +1.33, +0.00, -0.92, +1.19). The same cache shows that
24.5 % of the fixes that produce the reported 12.6 m and 15.2 m were taken while stopped inside a one-lane
segment (`table.fixes_inside_single_lane`), which R3 forbids and E50's reservation windows do not cover; E50b
moves those stops to the segment exit, so the position error inside segments will be larger than Table 9 shows.
Smallest fix: remove the delay figure from the abstract and the conclusion until E50b is in, or write "the
widened windows themselves added 0.007 h per delivery; the terrain-fix stops the scheme depends on, 37 h a month
or 23 % of the fleet's driving time, are not in that figure". State in 5.9 that a quarter of the fixes were taken
inside one-lane segments.

**M4. Abstract: "A 0.1 s guard made crystal clocks resynced every six hours safe for reservations."**
Evidence, `results/E51_table.csv`, crystal, lunar scale, 21,600 s: `max_abs_clock_s` 0.845, more than eight times
the guard; `conflicts_guard_0.1` 0 of 303 pairs; `worst_close_s` 0.123 against the 0.2 s that two guards give. At
one day the same cell has one conflict. Proposition 6 needs every clock within g of the base scale; no crystal
cell with the 0.1 s guard meets that (largest error 0.328 s even at a 10 s resync). The 51 cells in which the
premise held (A.6) are 42 atomic-clock cells and 9 crystal cells with the 1 s guard, on both time scales. So the
headline case is outside the proposition, rests on zero events in 303 pairs (a 95 % upper bound of 1 % per pair),
and used 62 % of the guard in its worst pair. The appendix says this; the abstract and Table 14 ("no conflict in
any cell that meets the premise", next to the H11 row) do not.
Smallest fix, abstract: "With a 0.1 s guard, crystal clocks resynced every six hours caused no reservation
conflict in 303 conflicting pairs over 30 simulated months, although clocks out of radio reach were up to 0.85 s
off; the guarantee (Proposition 6) needs every clock within the guard." Also explain the "No guard" column of
Table 11: the atomic clock, 3.6 ms off at worst, shows 22 to 25 conflicts where the crystal at a 10 s resync shows
1, because with zero stamped gap any clock difference of the wrong sign counts. As printed it reads as a result.

**M5. Sections 1, 3.5, 5.6, 5.8, A.4, Tables 6, 7, 14: "hard violation" is never defined, and "below the required gap" misdescribes it.**
Evidence: `lunarsim/atc/encounter.py` lines 14 to 19 and 720: `viol_gap` is a same-road bumper gap below the
static margin D0 = 5 m, not below R1's gap d_min; breaches of d_min while not braking are a separate counter,
`r1_breach_rate`, 0.0 in every type (`results/E44_bounds.json`). The crew violation is a moving vehicle inside
(stopping distance), that is R_crew,stop minus its 10 m margin (line 738). The paper defines a near miss
(Section 3.5) but not the violation, and says "closed below the required gap in 58 of 10,000" (1, 5.6, 5.8, 6.1,
A.4). A reader will take "required gap" as R1's 6.9 m + d_0.
Smallest fix: add to 3.5: "A hard violation is one of: contact; a same-road gap below the static margin d_0 = 5 m;
any part of a vehicle inside a closed zone; a moving vehicle closer to crew than its stopping distance; two
opposing vehicles inside one one-lane segment, a vehicle inside a reserved resource without a grant, or more
vehicles in a slot resource than slots. Gaps below R1's d_min while the follower is not braking are counted
separately and were zero in every type." Replace "below the required gap" by "inside the 5 m static margin"
everywhere.

**M6. Sections 3.11, 5.12, 6.1, 6.3, 9, Table 14: the lost-link rule is recommended but is absent from every priced run, its cost is unreported, and releasing a silent vehicle's reservation is unsafe when the vehicle is silent because it failed.**
Evidence: (a) `results/E54_dtn.json`: `lost_link_returns_per_seed` 82.1 against `jobs_per_seed` 199.3;
`link_shares.linked_share_driving_time` 0.566; `lost_link_isolation_h_saved_per_seed` 335.6 h against 162.8 h of
driving a month. Under the rule as specified (no contact for 600 s, retrace at half speed to the last link point,
wait there) the replay has 82 returns a month against 199 jobs and credits 336 vehicle-hours a month as spent
waiting, linked, at the return point; the fleet drives 163 h a month. `lunarsim/atc/dtn.py` applies the return to
the contact plan only; the recorded job still completes. None of these three numbers is in the paper. The
vehicles recorded for E50 drive 43 % of their driving time out of contact and never turn back, and E43's default
mode has no link test on the road at all, so the 0.1 % and every E50 number are for a fleet that does not follow
Section 3.11.
The strict reading of R7, the nearest thing priced, cost +49 h per delivery. (b) Section 5.12 says the "no
reservation stuck" clause "holds by construction ... the rule defines what a silent holder does, so the base may
release the reservation at its timeout". That assumes a silent vehicle is healthy and compliant. A vehicle that
is silent because a fault stopped it inside the segment (type 9 with its radio down) is still there when the
base releases, and the next opposing vehicle is granted the segment. (c) Companion paper P1 states the opposite
rule and cites this paper for it: "The dead vehicle's road reservation is not released: its last reserved stretch
stays closed until the vehicle is seen or towed, so that safety never rests on the failure detector being right
[45]" (`paper/p1/paper.html`, Section 3).
Smallest fix: report the 82 returns, the 56.6 % and the 336 h; say in 5.12, 6.4 and 7 that no logistics run
contains the lost-link ladder and that its delay cost is unknown and, from the strict-R7 cell, probably large;
change the rule or its claim: either the base releases only after the vehicle is heard or seen clear (then "no
reservation stuck" is false and the 7,349 h stand), or state the assumption "a silent vehicle is not a failed
vehicle" in Table 14 and in Proposition 4 (iii). Make P1 and P2 say the same thing.

**M7. Section 5.12, 6.1, 6.3, 9: "drop and retry lost 26 % of grants" is fixed by two assumed parameters, not measured.**
Evidence: `lunarsim/atc/dtn.py` DEFAULTS: `retry_s` 180; Section 3.11: a grant lives 60 s. A grant therefore gets
exactly one transmission, and `results/E54_table.csv` shows the lost share equal to the per-hop loss at every
level: 0.0946 at 0.10, 0.2560 at 0.25, 0.3986 at 0.40, with a mean delay of 0.01 s. Three tries inside the
lifetime would lose 1.6 % at a loss of 0.25. "Custody is therefore part of the traffic rules" and the practice
advice "give grants custody" rest on a baseline that cannot retry.
Smallest fix: label the 26 % as "the per-hop loss, because the retry interval (180 s, Assumed) is longer than a
grant's lifetime (60 s, Assumed)"; add a drop-and-retry row whose retry interval fits inside the lifetime.

**M8. Abstract, Sections 5.6, 5.8, 6.1, 9, Tables 6, 7, 14: the ring-deadlock rate "3.9 %" pools R3 as written with an unreported variant of R3.**
Evidence: `lunarsim/atc/encounter_types.py` `t5`: `keep = rng.random() < 0.5`; `encounter.py` line 121:
"exit_keep_free: R3 variant: a hop that does not end the trip needs 2 free slots in its bay".
`results/E44_bins.csv`, type 5: keep_free False 0 of 2,505 (K = 3) and 13 of 2,477 (K = 4), together 13 of 4,982,
0.26 %; keep_free True 106 of 2,421 and 267 of 2,597, together 373 of 5,018, 7.4 %. Mars
(`results/E47_bins.csv`): 2 of 979 against 68 of 1,021. The variant is not in Table 2 or anywhere in the paper;
PREREG change 6 mentions it as "worse" and says R3 is not amended. Separately, deadlock is judged only where no
random fuzzer runs, so 10,000 is not the denominator: among all-nominal encounters it is 76 of 939 (8.1 %), among
all-adversarial 43 of 535 (8.0 %) (`results/E44_encounters.csv`), both variants pooled.
Smallest fix: report the two rule variants separately with their judged denominators. Abstract: "A ring of
one-lane segments deadlocked in 0.3 % of its encounters under the exit-bay rule as written (13 of 4,982) and in
7.4 % under a keep-one-slot-free variant."

**M9. Appendix A.4, Sections 5.6, 6.1, Table 14: assumption (vii) of Proposition 4 fails for a conforming vehicle on an uphill grade, under the paper's own braking model, and no encounter is driven uphill.**
Evidence: `safety.py` `b_guaranteed`: b = min(0.5, mu g cos(theta)) - g sin(theta), theta > 0 downhill. Uphill
the full-braking candidate of the shield is 0.5 + g sin|theta|, which exceeds b_max = 0.8 m/s2 above 10.7 deg on
the Moon and above 4.6 deg on Mars. The steepest route slope is 17.2 deg (`results/ATC_roads_corridor.json`).
Recomputed with the formulas of A.4 at 15 km/h, follower at exactly d_min: leader braking at 0.98 m/s2 on
17.2 deg uphill, final gap 3.0 m; at Mars gravity on 15 to 20 deg uphill, 0.15 to 0.25 m. The lunar case is
inside the 5 m static margin, which is this paper's own hard violation, with no fault and no rule broken. The
type-1 builder draws theta from {0, 10, 15, 20} downhill only, and every other type runs on the flat (`theta`
defaults to 0), so the simulator could not have found it. The statement "The simulator's one failure is where the
derivation says it should be" and the Table 14 entry "Proved; tested" hold only for flat and downhill following.
The proposition also assumes without saying so that the follower knows the true gap and the leader's speed;
with the 15 m position error of Section 5.9 and the widened gap never exercised (Section 7), (b) is not covered
by (iv).
Smallest fix: make b_max slope-dependent (the leader's own 0.5 + g sin|theta|, or the friction limit) or state
(vii) as "no harder than b_max, which on this model fails on uphill grades above 10.7 deg (Moon)"; add uphill
following to type 1; add assumption (viii) "the follower measures the gap and the leader's speed without error,
or the error is inside d_0"; say in 3.5 and 7 that types 2 to 11 are flat.

**M10. Section 5.1: "Landings closed a pad 29 times a year."**
Evidence: `results/E43_runs.lead.csv`, cell `atc x1`: `landings` 22.2 a year; `plume_standdowns` 28.9. The
second is what the build writes (`build_p2.py` line 404), and `lunarsim/engine.py` lines 880 and 1064 increment
it once per vehicle evacuated and once per job held, not per closure.
Smallest fix: "The base saw 22 landings a year; their closures held a job or sent a vehicle to shelter 29
times."

**M11. Sections 3.5, 5.6, Table 6: the 95 % bounds for types 4, 5 and 6 are computed on the seeds on which the defects were found and fixed.**
Evidence: PREREG changes 8 and 9 and Section 5.6: the first main run showed 37, 3 and 82 violations in types 4, 5
and 6; the body geometry and the type-6 builder were corrected, the same-lane test of the gap metric was narrowed
after ten type-6 encounters had counted as violations, and all types were rerun "at the same n" on the same seeds
(type 9 "reproduced exactly"). A bound of the form 1 - 0.05^(1/n) needs a sample that played no part in fixing
the code or the metric. The paper discloses every step but still prints the bounds as 95 % bounds.
Smallest fix: rerun types 4, 5 and 6 once on fresh seeds with the frozen code and report those bounds, or mark
the three bounds in Table 6 "after correction on the same seeds; not a confirmatory bound" and drop the joint
"95 % over the twelve types".

**M12. Manuscript state.**
- Three "[[PENDING ...]]" strings are in the body (Section 5.9, twice for E50 at eight times and once for E50b). Either finish the runs or take the clauses out; "no claim rests on them" is not true of the abstract's delay figure (M3).
- Front matter: "Preprint, October 2026". The second pre-registration is dated 11 November 2026 and its results the same day (`git log`); P1 and P3 already say "revised November 2026".
- Reference [45]: "Companion paper P3 ... Title to be fixed." P3 has a title. [43] and [59]: "Cite by repository tag when tagged."
- The chi-square innovation test, CUSUM, covariance intersection, the temporal convolutional network, two-way time transfer and the W-MSR rule are used without a citation (`paper/p2/NOTES.md` says so on purpose, "because the notes ... name no opened source"). A journal will not accept that.
- [3] (Kim, Li, Wang, GLEX-2025) is the closest prior work in Table 1 and the basis given for R4 and R8, and is described as "without numbers" and "qualitatively"; `research_notes/Lunar ATC/traffic_and_safety.md` records that "the GLEX 2025 full paper ... [was] not available". The same note says the text of EU 2021/664 [10] "could not be fetched; wording is from EASA extracts and snippets", yet Section 2.2 quotes it, and that the normative text of ASTM F3548 [25] was not available.
- [16], [37], [38] carry a description in place of a title; [60] to [65], [71], [72], [79] lack authors' initials, venue or pages; [82] cites a data release without its paper (Hundman et al., KDD 2018), which the text admits was not opened.
Smallest fix: complete or remove each; describe [3] only from what was read ("its abstract proposes ...") and read the paper before submission.

**M13. Abstract and Section 9, sentences that go beyond what was measured.** (The body is usually careful; the abstract is not.)

| Sentence | What was measured | Rewording that stays inside it |
|---|---|---|
| "On Mars the rules behaved as on the Moon, and referral to Earth cost about one-sixth as much." | No sloped encounter was driven; on the flat the braking term is the same within 0.014 m/s2, so the driven encounters repeat the lunar ones (11 of 11 type-9 violations identical). The one-sixth follows from an assumed Earth window of half of every sol on the lunar road network. | "With Mars gravity on the same roads the flat encounters repeated the lunar ones and no sloped encounter could be driven, because the lunar brakes hold no downhill above 7.7 deg. With Earth assumed in view for half of every sol, referral to Earth cost about one-sixth of its lunar cost." |
| "We checked them ... and then with position error, clock error and wrong position reports." | The encounters and the exhaustive check were not rerun with position error (Table 14, "Not yet tested"); the later experiments are replays of one recorded month. | "... and, in replays of one recorded month, measured what position error, clock error, lost messages and wrong position reports do to the reservations." |
| "At today's fleet the rules added 0.1 % to delay per delivery" | +0.014 h, interval [-0.17, 0.22]; 13 of 30 seeds positive; an oracle dispatcher (`regime=O_ORACLE` in every E43 cell); reservations filed for the whole job at commit and kept to the second; no lost-link behaviour; the default reading of R7. | "... the rules added no measurable delay (0.1 %, upper bound 1.4 %) when every reservation is filed with the job; if a vehicle may file only where the base hears it, delay rose fourfold." |
| "referring every conflict to Earth raised it 5.1-fold" | True for t_hand = 2 h (Assumed, not swept) and the polar Earth windows; 37 h of the wait per conflict is the window gap, 2 h the staff time. | Add "with two hours of staff time per conflict (assumed) and the base's Earth windows". |
| Section 6.1, "The second number is the one we would put in front of a policymaker." | As above; the mode also has no local fallback at all. | Delete, or add the two assumptions. |
| Section 6.3, "Proposition 3 puts a number on what the uncoordinated mode already showed in delay" | The uncoordinated mode has no teleoperated driving in it. | Delete "what the uncoordinated mode already showed in delay". |
| Table 14, "Dead-reckoning error passes any fixed margin m within a distance m/sigma" | Proposition 1 says the standard deviation reaches m. | "The standard deviation of dead-reckoning error reaches m within m/sigma." |
| Table 14, "Non-overlapping reservations and the gap rule give no collision" | (a) covers opposing vehicles in one one-lane segment, (b) rear-end contact; junctions, crew, merging and lateral contact are outside it. | "... give no head-on meeting inside a one-lane segment and no rear-end contact." |
| Section 5.7, "H7's second clause, a counterexample for each removed rule, holds." | Three rule clauses were removed (R3 exit, R5 entry, R7 hold). The registered text is "each rule removed". R6 and R10 are in the discrete model and were not mutated. | "... holds for the three clauses removed; R6 and R10 were not mutated." |

## 4. SHOULD FIX

**S1. H9', second clause: "near the base" is an analysis choice made after the registration, and the result is close to the line.** PREREG6 says "within radio range of the base beacons". The rule used, "radio line of sight of at least 2 of the 4 beacons", first appears in `tools/atc/run_e50.py`, committed at 17:43 on 11 November together with the E50 results (PREREG6: 10:14 the same day). With ranging the overall 95th percentile is 50.1 m; near the base it is 4.22 m, seed maximum 4.64 m, against 5 m. Give the result for at least 1, 2, 3 and 4 beacons in view, say when the rule was fixed, and list it in 4.6. The same applies to the hourly-maximum bound and to a filter change made after the first E50 cell (`lunarsim/atc/pnt.py` line 67: parked vehicles range once, "over-confidence; seen as NEES 6.8 against 2 in the first E50 cell"), which 4.6 does not list.

**S2. PREREG6 section 2 says "A parameter without an opened source is ASSUMED and swept."** Section 7 says "Only their nominal values were run ... nothing else was swept." That is a deviation from the registration and should be listed in 4.6 as one.

**S3. The Holm family.** PREREG6 gives decision rules by interval, not p values, so all three p values are constructions made after the results (a paired t-based TOST, an exact one-sided sign test, a bootstrap bound with 1,000 resamples where the general rule is 20,000). Say so in 4.5, state that the sign test is one-sided (two-sided p = 0.0039), and add the adjusted values with the registered family size of five (H15a at most 0.005, H14 0.008), which do not change the verdicts. H8 is not in the first registration's confirmatory family {H1, H2, H3a, H4, H6}; "confirmatory" in 4.1 is this paper's label and should be called that.

**S4. H10'.** (i) A margin of 50 % of the perfect-position delay (8.87 h) is 1,300 times the effect and larger than the between-seed standard deviation (5.9 h); passing it says nothing. It is the registered rule, so keep the verdict, but report the smallest margin that would pass: the 90 % upper end is 0.015 h, 0.09 % of the delay. (ii) Third clause: the dead-reckoning margin was costlier in 24 of 30 seeds (Wilcoxon signed-rank p = 0.003, my computation from `results/E50_runs.csv`), while the registered interval on the mean includes zero. "Could not be told from zero" (6.1) is true of the mean only. (iii) At four times the fleet the perfect-position delay has a standard deviation of 12.9 h over 10 seeds (4.0 to 46.8 h); a "gain" of -0.87 h whose interval excludes zero shows that 10 seeds do not resolve this comparison. "Both failed because position error cost less than we had predicted" is not established; "the experiment could not resolve either" is.

**S5. False-alarm rates rest on a handful of events, and one of them is quoted to two digits.** Test fault-free data: 575 one-hour blocks, drawn equally from four strata and weighted back; the stratum "parked, long range" is 70 % of natural time and has 152 blocks (`results/E56_integrity.json`, `dataset.test`). One alarm-minute there adds 0.11 per pair-day. The protocol rule's 0.098 per pair-day is therefore a handful of alarm-minutes in 575 hours (four, if they fall in the two middle strata) and none in that stratum; zero in 152 hours allows up to 0.33 per pair-day from it at 95 %. Give the count and an interval, and drop "113 times". Give the intervals for all detectors, not only the network (README: per-step chi-square 0.18 to 1.42, windowed 0.03 to 3.70). The appendix's "check of the assumption" (threshold 19.1 against 19.2) is one crossing point: at 10.83 the single test gave 53 alarm-minutes a day against 84 for independent Gaussian innovations, and at 15.14 it gave 4.8 against 8.6 (`results/E55_table.csv`), so the innovations are not Gaussian with the claimed variance, as the README says in words ("the honest innovation is not zero-mean").

**S6. E56 description.** (i) Pairs are split by |id difference| ({1,4,5}, {2,6}, {3,7}); every vehicle is in all three sets. Say "no pair and no month is shared; every vehicle is". (ii) Section 3.12 says A has "the errors of Section 3.9"; the E56 model is 2 % of distance with a fix every 100 m and at every stop, no filter, no terrain (`results/E56_README.md`, section 2 and 10). (iii) The median delay is over each detector's own found faults; quote the common-found figure the README already has, -23.2 s [-26.8, -19.9]. (iv) H15 (b) is given as a 90 % interval [1.0, 1.6] in the text; `results/table_E56.csv` carries the same two numbers in its interval columns without a level. State which it is.

**S7. The real-telemetry check (Section 5.11, Table 13) does not show what the text says without three qualifications.** (i) The detectors are not E56's: window 16 and CUSUM k = 0.5 uncentred (`tools/atc/run_b97.py` line 92) against 5 and k = 3 centred. (ii) The gain on SMAP comes with 9 to 13 times the false-alarm runs (18 and 26 against 2), so it is not at one false-alarm rate. (iii) The "z-score" and "chi-square, per step" columns are the same detector on one channel and print identical numbers. On the first difference, the residual closest to an innovation, accumulation gains nothing. The check, if it argues anything, argues against the per-step test the paper keeps. The 14 channels per spacecraft are the first in alphabetical order, chosen by download size.

**S8. The uncoordinated mode.** t_hand was not swept; 37.2 h of wait per conflict against 2 h of staff time means the result is the Earth-window gap. The Mars fleet referred 94 conflicts against 53 "and we have not traced the cause"; a reviewer will not accept an untraced factor of 1.8 in the quantity that drives the comparison. Two vehicles do 95 % of the driving (seed 1 of E50: 9,018 of 9,451 driving steps, `.cache/atc/e50/trace_m1_s1.pkl.gz`), and owners A and B carry nearly all of the bay wait (19.1 and 4.9 h against 0.4 h for C); say in 5.1 that "today's fleet" on the roads is two vehicles.

**S9. Conditions of the 0.1 %.** State in 3.4 and 6.4 that E43 uses the oracle dispatcher with instant, lossless assignment; that windows are computed at commit for every later leg and kept exactly; that no travel-time uncertainty exists in the model; and that E54's contact plan has vehicles in contact for 56.6 % of driving time. E50 covers position error only, not timing error, which is the larger term for windows filed hours ahead.

**S10. E44 reporting.** (i) Table 6 omits the finished and incomplete outcomes: 22 % of driven type-1 encounters finished, 36 % of type 2, 10 % of type 11 (`results/E44_encounters.csv`); a reader cannot tell how often a rule was exercised. Add the columns. (ii) The 0.5 m/s2 service brake cannot hold the 20 deg slope that the reference vehicle is specified for (g sin 20 deg = 0.554), which is why 25 % of type-1 draws are not driven; an assumed parameter contradicts a sourced one. Say so or size the brake. (iii) Type 9: 58 of 3,316 dead-stop encounters (1.7 %, unweighted) is the rate a reader wants; "58 of 10,000" is diluted by the slip and drift bins.

**S11. Propositions, one by one.**
- P1: correct. Statement and numbers reproduce. Table 14 misstates it (M13). E50's 85 m and 308 m illustrate it; they do not test the formula.
- P2: correct as stated, with a gap. The premise "so that it is truly at each end within beta/v of the time it believes" holds only if the vehicle moves at v across the stretch of length beta at each end. A vehicle that starts from rest at the bay (every waiting vehicle) at 0.2 m/s2 needs sqrt(2 beta / a) to cover beta: 6.5 s for beta = 4.2 m against a margin of 1.0 s at 15 km/h. A waiting vehicle with error beta may stand beta inside the segment mouth for the whole wait; a time margin does nothing for that, a stop line set back by beta does. Opposite signs of the two errors are covered by the proof. In the code v is the mean speed of the whole leg (`roads.py` line 465). State the constant-speed premise and add the set-back.
- P3: correct. It assumes constant speed through the reaction time while R1 assumes acceleration a_acc through it; say which R2 uses. "NASA's simulator study measured 2.03 km/h ... inside these caps" validates nothing.
- P4: (a) correct but close to definitional: (iii) assumes what a safety proof should show, and a dead vehicle breaks (iii) as well as (vii). (b) correct under (vi) and (vii); (vii) fails uphill (M9).
- P5: correct. Numbers reproduce (10.83, 13.82, 4.57, 5.62, 9.4 m, 13.0 m, 1.0e-8, 0.991, 19.2). Applicability is poor, which the appendix says; see S5.
- P6: correct. Not applicable to the headline case (M4).
- P7 (a): correct; add "values heard at a step are the senders' values at that step" (no delay). (b) is quoted from a report on a continuous-time rule; the discrete-time theorem is LeBlanc et al., IEEE JSAC 2013, which the notes mark "paywalled and was not opened". Read it and cite it. "Converged in at most 18 %" (abstract, 6.1) comes from the cell with two faulty rovers and F = 1, where the rule is unsafe; where F covers the faulty rovers the maximum is 10 % (`results/E55_integrity.json`, `consensus.cells`).

**S12. Related work and novelty.** The closest deployed systems for one-lane roads with passing places are not discussed: single-track railway signalling (token block, passing loops), autonomous haulage in open-pit and underground mines (permission-based single-lane ramps with passing bays), and zone-controlled AGV systems with deadlock avoidance. For margins sized by navigation performance: required navigation performance and containment in aviation, the conformance volumes of ASTM F3548, and the buffers in Dresner and Stone, which the paper cites for something else. For wrong position reports: misbehaviour detection in vehicular networks (plausibility checks against ranging, learned detectors, public datasets) and receiver autonomous integrity monitoring with protection levels. For execution under timing uncertainty: k-robust and delay-probability multi-agent path finding. With these absent, "We found no work that puts position error, clock error or a wrong report into a traffic rule and measures what the rule then costs" (2.6) and the fifth contribution are not justified as written. Table 1 has no row newer than 2021 except the authors' own and a conference abstract.

**S13. Consistency across the three papers.** Numbers quoted in more than one paper agree (4.2 m, 15.2 m, 7.54 m, 0.33 lost jobs a seed, 88 reservations a seed, Holm 0.004, 0.003, 0.93). Labels do not: P2 writes H9 for Mars and H9', H10' for the second registration; P3 writes H9 for positioning and H10 for flight-computer sizing, and in its Holm sentence uses H10 for the margin hypothesis; P1 explains P2's primes in passing. A reader of all three meets H9 with two meanings and H10 with two. Prefix the second registration's labels in all three. P1 cites P3 under a slightly different title from P3's own. The reservation of a silent vehicle is handled in opposite ways in P1 and P2 (M6).

**S14. Verification of the Phase 6 models.** The 10 rows tagged to this paper check chi-square quantiles, a Monte Carlo of the formulas, one trimmed-mean case and that the options switch off. None checks the positioning filter, the clock model, the contact plan or the overlap counter against anything. The one quantity Proposition 2 depends on, how often the error is inside the vehicle's own bound, is not reported; I computed it for seed 1 at today's fleet from the cached trace: 97.1 % of driving steps inside the 95 % bound, 99.75 % inside the hourly maximum used for filing. That is fine and should be in Table 9 for all seeds.

**S15. Section 3.6 against the final checker.** 3.6 lists "none in a crew cell or next to it" as an invariant on every reachable state; 5.7 says that formulation was a checker defect and R6 is now checked on the vehicle's motion. Correct 3.6.

**S16. Limitations that are missing or understated, and controls a reviewer will ask for.**
Missing: no travel-time uncertainty in any reservation; the lost-link ladder absent from the logistics runs; all Phase 6 experiments on one month (July 2028); the bound a vehicle files with comes from a different run's trajectory, so residual overlaps may be an artefact of that and "the remainder is outside the 95 % bound" (Table 14) is not shown; errors sampled on a 60 s grid; crystal frequency error drawn one-sided from 0 to 8e-7, which halves the spread of clock differences against a symmetric draw; the out-of-distribution set is one arbitrary shift.
Controls: E50b finished and E50 rerun with fixes deferred out of segments; the lost-link ladder inside the engine; a sweep of t_hand and one local fallback rule for the uncoordinated mode; uphill following and sloped versions of types 2, 4 and 7; type 9 with the full-stopping-distance gap; fresh-seed rerun of types 4, 5 and 6; detectors compared at matched realised false-alarm rates with two observers; the cost in delay of R9 at 0.1, 1 and 70 false alarms per pair-day; a sensitivity of the H9' verdict to the beacon rule.

## 5. OPTIONAL

**O1. One paper or two.** Sections 3.9 to 3.12, 5.9 to 5.12, half of 6 and 7 and five of seven propositions are a second paper: different pre-registration, different regime (auction, not oracle), one month instead of a year, replays instead of runs, and a detector study that shares nothing with the rules but R9. The title and the first three research questions cover only the first. Splitting would let the first paper go out after M5, M8 to M11, and give the second the room to finish E50b and the engine run of the lost-link rule.

**O2. Figures.** Three plots and fourteen tables. There is no map of the road network with its one-lane segments and bays, no drawing of an encounter type, no diagram of a reservation with its margin and guard. Table 5 (39 rows) belongs in a supplement with five rows kept.

**O3. Readability.** Section 5.6 spends more words on the three reruns than on the result, and 5.13 prints eight verification row names verbatim ("D10 pairing A_EARTH plan_ahead (CRN pairing reduces variance against O_ORACLE ...)"). Move both to an appendix. Terms used before or without definition: ATC mode, pair-day, effective n, layer set, b_AB, the auction of [44], B-97, change 9, phase 5, "the navigation service as in 2028".

**O4. H11 is true before any run** (1 ns of clock error is 0.3 m; one-way ranging is not used by the system). Say so in one line and drop it from the abstract-level claims.

**O5. Section 5.8:** "differs between the bodies by at most 0.01 m/s2" is 0.014 at friction 0.3 (0.5 against 0.486).

**O6. Section 6.1:** "with dead reckoning alone it is 25 min and cost 2.1 h per delivery at four times the fleet" pairs the margin at today's fleet (0.414 h) with the cost at four times (where the margin is 0.450 h, 27 min).

**O7. E50's perfect-position delay (17.7 h) against E43's baseline (15.5 h):** one sentence on why they differ (month, regime) would save the reader a search.

**O8. Competing interest.** The statement is adequate. Given that the code, the runs, the text and the reference list were produced by an assistant, name who checked the references against the publishers' records, and when.

## 6. Checked numbers

Source files are under `results/` unless a path is given. "Recomputed" means from raw rows by my own script
(bootstrap with my own seed, so interval ends can differ in the second decimal). Rows 1 to 16 are every number
in the abstract and the conclusion.

| # | Claim | Paper | File value | Source | Verdict |
|---|---|---|---|---|---|
| 1 | Driven encounters | 274,580 | 274,580 | E44_encounters.csv, outcome not `not_driven` | match |
| 2 | Logistics runs | 650 | 650 | E43_runs.lead.csv rows | match |
| 3 | Types without a violation | 11 of 12 | 11 (type 9: 58) | E44_encounters.csv | match |
| 4 | Ring deadlocks | 3.9 % | 386 of 10,000 | E44_encounters.csv, type 5 | match; pooled over two rule variants (M8) |
| 5 | Cost of the rules, x1 | 0.1 % | 0.0143 h / 15.532 h = 0.092 % | E43_runs.lead.csv, recomputed | match |
| 6 | Referral to Earth | 5.1-fold | 79.063 / 15.532 = 5.09 | same | match |
| 7 | Mars referral cost | about one-sixth | 11.12 / 63.52 = 0.175 | E47_runs.csv, E43 | match |
| 8 | Ranging near the base | inside 5 m | 4.216 m | E50_errors.csv, dr+ranging, near | match |
| 9 | Terrain fixes away | 15 m | 15.234 m | E50_errors.csv, dr+ranging+fixes, away | match |
| 10 | Overlaps a month | 0.7 to 0.03 | 21/30 = 0.70; 1/30 = 0.033 | E50_errors.csv, E50_runs.csv | match |
| 11 | Delay of the margin | under 0.05 h | +0.0066 h, upper end 0.017 | E50_runs.csv, recomputed | match as worded; excludes stops (M3) |
| 12 | Crystal, 6 h, guard 0.1 s | safe | 0 of 303; max clock error 0.845 s | E51_table.csv | count matches; "safe" not supported (M4) |
| 13 | Network size | 9,529 | 9,529 | E56_integrity.json, model.n_params | match |
| 14 | Drift found sooner | 24 s | 109.0 - 84.9 = 24.1 | table_E56.csv | match |
| 15 | Drifts missed by every detector | at least 37 % | best recall 0.630 | table_E56.csv, test, 1/pair-day | match |
| 16 | Fixes away, multiple of margin | three times | 15.23 / 5 = 3.05 | E50_errors.csv | match |
| 17 | Delay, atc x1 / none x1 | 15.5 / 15.5 h | 15.546 / 15.532 | E43_runs.lead.csv | match |
| 18 | Delay, uncoordinated 2028 / 2038 | 79.1 / 98.5 h | 79.063 / 98.478 | same | match |
| 19 | Bay wait, conflicts, traversals, x1 | 24 h, 73, 1,843 | 24.13, 72.87, 1,842.7 | same | match |
| 20 | Apron wait, crew-speed hours | 0.5 h, 10.0 h | 0.475, 10.03 | same | match |
| 21 | Pad closures a year | 29 | landings 22.2; plume_standdowns 28.9 counts held jobs and evacuations | same; engine.py 880, 1064 | **mismatch** (M10) |
| 22 | Bay wait by owner | 19.1, 4.9, 0.4 h | 19.14, 4.92, 0.41 | same | match |
| 23 | Deadlocks in E43 | 0 in 650 | 0 | same | match |
| 24 | H8 difference and interval | +0.01 [-0.17, 0.22] | 0.0143 [-0.173, 0.219] | recomputed | match |
| 25 | H8 upper bound of the ratio | 1.4 % | 1.41 % (file 1.42 %) | recomputed; table_E43_pairs.csv | match |
| 26 | p90, items, urgent wait, operator hours | +0.07, -1.8, -0.41, +7.4 | 0.074, -1.8, -0.412, 7.44 | recomputed | match |
| 27 | x2 cost | +0.29 [0.21, 0.39], 3.7 %, 4.9 % | 0.295 [0.205, 0.391], 3.69 %, 4.90 % | recomputed | match |
| 28 | x4 cost | +0.40, 7.9 %, 10.2 % | 0.398, 7.94 %, 10.1 % | recomputed | match |
| 29 | x8 cost | +1.56 [1.17, 1.92], 41.7 %, 53.9 % | 1.558 [1.17, 1.92], 41.7 %, 54.0 % | recomputed | match |
| 30 | x2 conflicts and bay wait | 847, 288 h | 846.5, 287.5 | E43_runs.lead.csv | match |
| 31 | Uncoordinated minus none | +63.5 [58.4, 68.7]; +82.9 [76.0, 89.7] | 63.53 [58.4, 68.8]; 82.95 [75.9, 89.7] | recomputed | match |
| 32 | Ratios to baseline | 6.3; 8.1, 10.3; 12.6, 12.8; 20.2, 18.1 | 6.34; 8.11, 10.29; 12.57, 12.81; 20.24, 18.10 | recomputed | match |
| 33 | Earth conflicts, wait, other vehicle | 53, 1,969 h, 1,961 h | 52.9, 1,969.0, 1,960.8 | E43_runs.lead.csv | match |
| 34 | 2038 conflicts and wait | 45, 2,527 h | 44.63, 2,526.7 | same | match |
| 35 | Strict R7 | +49.1 [43.8, 54.8]; 725; 37; 1,551 h | 49.14 [43.8, 54.8]; 724.97; 37.47; 1,551.4 | recomputed | match |
| 36 | Share 0.4 | 96.8 km; +0.28 [-0.03, 0.58]; 43 h | 96.8; 0.276 [-0.03, 0.58]; 42.5 | recomputed | match |
| 37 | Bays every 0.5 km | +0.06; 4,834 traversals | 0.063; 4,834.2 | recomputed | match |
| 38 | One-lane road at default share | 36.3 of 242 km | 36.3; 242.1 | E43 runs; ATC_roads_corridor.json | match |
| 39 | Corridor analysis | 2,421; 17; 0.4 km; 36.5 km (15.1 %); 96.5 km; 101 m; 17.2 deg | same values | ATC_roads_corridor.json | match |
| 40 | Not driven | 24,743 and 677 | 24,743 and 677 | E44_encounters.csv | match |
| 41 | Bonferroni bounds, types 1 and 6 | 7.3e-5, 1.2e-3 | 7.28e-5, 1.21e-3 | recomputed from n_eff | match |
| 42 | Effective n, types 6, 7, 9, 12 | 4,545; 47,148; 6,115; 7,231 | 4,545.0; 47,148.2; 6,114.6; 7,231.0 | recomputed from weights | match |
| 43 | Type 9 violations | 58 (7 contact, 58 "below the required gap") | 58 (7 `viol_contact`, 58 `viol_gap` = gap below D0) | E44_bounds.json; encounter.py 720 | counts match; **definition mismatch** (M5) |
| 44 | Type 9 limits | 8.1e-3; 9.2e-3 at 0.61 % | 8.12e-3; 9.18e-3 at 0.605 % | recomputed (Clopper-Pearson) | match |
| 45 | Near misses | 121,468 (44 %) | 121,468 (44.2 %) | E44_bounds.json | match |
| 46 | Smallest clearance without violation | 1.1 m | 1.052 m (type 6) | E44_bounds.json | match |
| 47 | Deadlocks, types 5 and 6; blocked by fault | 386; 4; 4,137 | 386; 4; 4,137 | E44_encounters.csv | match |
| 48 | Emergency brake, type 7 | 52.7 % | 0.5269 | E44_bounds.json | match |
| 49 | Reachable states, transitions, largest | 47,085; 272,899; 36,912 | 4,356+1,092+4,725+36,912; 272,899; 36,912 | E45_modelcheck.json | match |
| 50 | Longest shortest path | 41 steps of 8.5 s | 41; 8.452 s | E45_modelcheck.json | match |
| 51 | Mutations | R3: 2, 39, 13, 12; R5: 384, 14; R7: 198 (138, 96), 5 | same | E45_modelcheck.json | match |
| 52 | Mars type 9 | 11 of 2,000, the same eleven, no contact | 11; 11 of 11 violate on the Moon; min margin 0.226 m | E47 and E44 encounters merged | match |
| 53 | Mars bounds | 2.7e-3 (1.5e-3); 1.2e-2 (9.1e-3) | 2.74e-3 (1.50e-3); 1.15e-2 (9.09e-3) | recomputed | match |
| 54 | Mars ring and closure deadlocks | 70; 2 | 70; 2 | E47_encounters.csv | match |
| 55 | Type 1 not driven, Mars and Moon | 8,961 (74.7 %); 3,019 (25.2 %) | 8,961; 3,019 | E47, E44 merged | match |
| 56 | Holdable downhill | 7.7 deg; 16.7 to 18.0 deg | 7.74; 16.70 and 17.98 | computed from safety.py | match |
| 57 | Flat braking difference | at most 0.01 m/s2 | 0.014 (0.500 against 0.486 at friction 0.3) | computed from safety.py | **mismatch**, minor (O5) |
| 58 | Mars uncoordinated minus ATC | 10.4, 11.1, 10.8; relay 8.2, 8.7, 6.4 h | 10.36, 11.12, 10.79; 8.22, 8.68, 6.37 | E47_runs.csv, recomputed | match |
| 59 | Mars conflicts and wait; hours per conflict | 94; 772 h; 8.2; Moon 37.2 | 94.0; 772; 8.21; 37.2 | E47_runs.csv, E43 | match |
| 60 | Share of ATC delay; of Moon cost | 0.72; 0.18 | 0.715; 0.175 | recomputed | match |
| 61 | Mars ATC runs equal lunar | on every seed | largest difference 0.0 | E47_runs.csv against E43 | match |
| 62 | Dead reckoning p95; first hour | 643 m [563, 728]; 85 m | 643.2 [563, 729]; 85.2 | E50_summary.json; phase6_family.json | match |
| 63 | With ranging | 50.1; 4.22 [4.12, 4.31]; 57.1 m | 50.10; 4.216; 57.08 | E50_errors.csv | match |
| 64 | With fixes | 12.6; 3.50; 15.2 [14.5, 16.0]; 49 % | 12.63; 3.495; 15.23; 0.490 | E50_errors.csv | match |
| 65 | Navigation service 2030, away | 7.54 m | 7.545 | E50_errors.csv | match |
| 66 | Fix stops | 37.3 h; 169 h | 37.27; 168.7 | E50_errors.csv | match |
| 67 | x4: near with ranging; away with fixes | 4.31; 12.2 [11.6, 12.9] | 4.305; 12.24 | E50_errors.csv | match |
| 68 | Seeds on the predicted side | all, all, none | 30 of 30 below 5 m (max 4.64); 0 of 30 (min 11.45) | E50_errors.csv | match |
| 69 | Overlaps without margin | 1.87; 0.57 to 0.77 | 56/30; 17/30, 21/30, 23/30 | E50_errors.csv | match |
| 70 | Margin size | 0.41 h; 0.011 h (39 s) | 0.4145; 0.01076 (38.8 s) | E50_summary.json | match |
| 71 | Perfect-position delay | 17.73 [15.82, 19.93] | 17.731 | E50_runs.csv | match |
| 72 | Margin minus perfect | +0.007 [0.000, 0.017]; +0.12 [-0.08, 0.31] | 0.0066 [0.0002, 0.017]; 0.117 [-0.08, 0.31] | recomputed | match |
| 73 | Road waiting | 2.47, 2.49, 7.57 h | 2.473, 2.488, 7.574 | E50_summary.json | match |
| 74 | x4 block | 68 to 72; 0.0, 0.9; 12.80; +2.08; -0.87; 310.2, 314.7, 605.2 | 67.7 to 71.5; 0, 0.9; 12.80; 2.082; -0.868; same | E50 files, recomputed | match |
| 75 | H10' figures | 8.87 h; 1.0004; p 0.93, 0.13; Holm 0.93 | 8.866; 1.00037; 0.932, 0.128; 0.932 | phase6_family.json; t test recomputed | match |
| 76 | Discussion: dead-reckoning margin at x4 | 25 min | 0.450 h = 27 min at x4 (25 min is x1) | E50_summary.json | **mismatch**, minor (O6) |
| 77 | Pairs checked; resync failures | 303; 6.8 % | 303; 0.0683 | E51_table.csv | match |
| 78 | Crystal conflicts, guard 0.1 s | 0 to 6 h; 1 at a day; 15 never | same | E51_table.csv | match |
| 79 | No guard | crystal 1 to 26; atomic 22 to 25; 3.6 ms | same; 0.00361 s | E51_table.csv | match |
| 80 | Largest crystal error | 0.33 s at 10 s; 2.14 s never | 0.328; 2.141 | E51_table.csv | match |
| 81 | One-way ranging | 975, 1,787 km; 1.61, 3.23, 42.4 km | 975.3, 1,787.1; 1.610, 3.229, 42.35 | E51_table.csv | match |
| 82 | Two-way ranging | 0.084 m; 0.11 mm | 0.0837; 0.000112 | E51_table.csv | match |
| 83 | Variants | 1.5 to 7.1 times; 5.19 against 1.63 km; 24 % | 1.50 to 7.13; 5.190, 1.626; 1.237 | E51b_table.csv, recomputed | match |
| 84 | Realised false alarms, test | 0.53 [0.29, 0.82]; 0.68; 1.26; 1.35; 2.03 | 0.531 [0.286, 0.825]; 0.678; 1.256; 1.346; 2.025 | table_E56.csv; E55_integrity.json | match |
| 85 | Recall over all faults | 90, 86, 77, 71, 70 % | 0.903, 0.861, 0.774, 0.713, 0.703 | table_E56.csv | match |
| 86 | Noise, jumps | 100.0 against 35.5; 92.0 against 69.8; 95.5 | 1.000, 0.355; 0.9195, 0.6975; 0.955 | table_E56.csv | match |
| 87 | Drift delays | 85, 81, 78, 109 s | 84.9, 81.0, 78.5, 109.0 | table_E56.csv | match |
| 88 | One per pair-hour | 95 %, 78 %; 94 %, 73 % | 0.953, 0.775; 0.939, 0.728 | table_E56.csv | match |
| 89 | Out of distribution | 22.6 %, 11.3 %; 66.5, 66.5; 13.8 (26 times); 18.3; 199 to 863 | 0.226, 0.113; 0.665, 0.665; 13.84 (26.0); 18.26; 199.0 to 863.4 | table_E56.csv | match |
| 90 | Thresholds reset | 1 to 3 %; 0.7 to 1.9 | 0.010 to 0.034; 0.74 to 1.89 | table_E56.csv | match |
| 91 | Jump delay, network | 1.2 s [1.0, 1.6] | 1.2 [1.0, 1.6] | table_E56.csv | match (interval level, S6) |
| 92 | Protocol rule, test | 0.10; 67.7 % (73.5, 61.8, 8.5); single test 53 | 0.098; 0.677 (0.735, 0.618, 0.085); 53.3 | E55_table.csv | match |
| 93 | Protocol rule, out of distribution | 69; 26 %, 25 %; 1,128 | 69.0; 0.263, 0.248; 1,128 | E55_table.csv | match |
| 94 | "113 times 0.0009 a day" | 113 | 0.0979 / 0.000863 = 113 | recomputed | match |
| 95 | Monte Carlo of Proposition 5 | 0.899 at 0.98e-3 | 0.89939; 0.000985 | E55_integrity.json | match |
| 96 | Telemetry check | 28 channels, 38 events; MSL 13, 13 against 10; SMAP 12, 16 against 2; 0.38 to 0.46; first difference 10, 10, 10 and 7, 5, 7 | same | B97_realdata.json | match |
| 97 | Agreement safety | 30 cells, 1,500 runs; 48 to 66 %; 70 to 92 % | same | E55_integrity.json, consensus.cells | match |
| 98 | Agreement reached | 0 to 18 %; at most 10 % with no faulty rover | 0 to 0.18 (the 0.18 is at f = 2, F = 1); 0.10 | same | match; attribution (S11) |
| 99 | Hears 2F+1 others | 0 to 30 %; none spread | 0 to 0.30; 0 | same | match |
| 100 | Base mast | 58 to 96 % against 0 to 10 %; 0 to 16 %; at most 8 %; 2 to 24 % against 48 to 66 %; 6 % against 50 % | same | same, consensus_with_base_mast | match |
| 101 | Robust meshes | 12 of 800 | 12 of 800 | same | match |
| 102 | Grants and awards; lost | 6,028; 1,543 (26 %); 2 (0.03 %); 9 %, 40 % | 6,028; 1,543 (0.256); 2; 0.0946, 0.3986 | E54_table.csv | match |
| 103 | Lost jobs; sign test | 0.33 [0.17, 0.53]; 9, 0, 21; p 0.002; 0.004 | 0.333 [0.167, 0.533]; 9, 0, 21; 0.00195; 0.0039 | E54_dtn.json; phase6_family.json; recomputed | match |
| 104 | Blocked reservations | 2,566 of 2,628; 7,349 h | 2,566; 87.6 x 30 = 2,628; 7,349.2 | E54_table.csv, E54_dtn.json | match |
| 105 | Age of information | 45 s (149 s); 88 min (31 h) | 45.5 (148.9); 5,287 s (111,296 s) | E54_table.csv | match |
| 106 | Phase 5 checks | 98; 97 and 1; technique counts; 8 failed, 81 passed, 9 not run | 98; 97, 1; same; passed 81, not passed 17 | vv_phase5.json | match |
| 107 | Phase 6 checks | 10, all pass; 6 analytic, 4 Monte Carlo | same | vv_phase6.json | match |
| 108 | Dispatch fix, before and after | -0.13 h; 3.8 h; 43 h; 69 %; 14 to 8 s; 394 to 32 s | -0.133; 3.846; 43.07; 0.687; 13.5 to 8.0; 393.6 to 31.6 | E43_fixpoint_before_after.json | match |
| 109 | A.1 worked numbers | 250, 50 m; 128, 26 m; 60, 225 s; 0.17 %; 2.6 % | 250, 50; 127.6, 25.5; 60, 225; 0.175 %; 2.62 % | recomputed | match |
| 110 | A.1, E50 | 85 m after one hour, 308 m after eight | 85.2; 307.8 | phase6_family.json; .cache/atc/e50 | match |
| 111 | A.3 worked numbers | 14.4, 8.6, 9.7, 4.9, 17.0, 9.3 km/h; 0.73 | 14.40, 8.59, 9.73, 4.89, 16.99, 9.27; 0.729 | recomputed | match |
| 112 | Table 2 and A.4 | 6.9 m, 12.5 m; 2.83 m/s (10.2 km/h); 5.9 m; 23.3 m | 6.92, 12.48; 2.828 (10.18); 5.85; 23.33 | recomputed from safety.py formulas | match |
| 113 | A.5 worked numbers | 10.83, 3.29, 13.82; 4.57, 5.62; 2.84, 9.4, 13.0 m; 1.0e-8; 0.991 | 10.828, 3.2905, 13.816; 4.572, 5.617; 2.844, 9.36, 13.00; 9.985e-9; 0.9914 | recomputed | match |
| 114 | A.5, thresholds | 19.2 from the law; 19.1 on validation | 19.23; 19.106 | recomputed; E56_integrity.json | match |
| 115 | A.6 | 36.5 h; 36.7 h; 51 cells; 18 microseconds | 36.55; 36.71; 26 + 25 = 51; 1.84e-5 s | E51_clocks.json holdover; E51_table.csv | match |
| 116 | E56 split | 28, 16, 12 ordered pairs; 3,600, 1,020, 2,000 streams; 600, 575 hours | same | E56_integrity.json, dataset | match |
| 117 | Test fault-free pair-days | 24 | 23.96 | E56_integrity.json | match |

117 rows checked (most rows hold several numbers). 4 mismatches: row 21 (wrong quantity), row 43 (the count is
right, the thing counted is not what the text says), rows 57 and 76 (minor).

## 7. What I could not check, and why

- No simulation was rerun. E44, E47 and E43 were checked from their per-encounter and per-run files; the encounter kinematics and the engine were read, not re-executed.
- E56 and E55: the per-event scores are not in `results/`, only the aggregated tables, so recalls, delays and their bootstrap intervals were compared with `table_E56.csv` and `E55_table.csv`, not recomputed from events. The count of false-alarm bins behind 0.098 per pair-day is inferred from the stratum weights.
- E51, E54, E55 agreement: per-seed data are in `.cache/` only; the summary tables were checked for internal consistency and the sign test recomputed from its counts.
- The durations of the overlaps without a margin (M2) are not stored anywhere I could find.
- The Earth-visibility shares (61.5 %, 54.7 %) appear only in `values.json`; the telemetry totals (82 channels, 105 anomalies) were not traced.
- Bound coverage (S14) and the dead-reckoning value after eight hours come from `.cache/atc/e50`, which is not under version control; the E50b figures in M3 are from an unfinished run and will change.
- No external source was opened. Statements about references rest on the research notes' own "opened" and "UNVERIFIED" marks and on `paper/p2/NOTES.md`; the prior work named in S12 is from my knowledge of those fields and should be checked by the authors.
- The PDF was not inspected; figures were judged from the three inline SVG elements, not rendered.
- P1 and P3 were searched for what they share with P2, not refereed.
