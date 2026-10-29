# Pre-registration: Lunar ATC experiments (P-A, P-B, P-C)

Written 27 October 2026, before any Phase 5 experiment was run (git history dates this file). Changes after the
first main-run row exists are listed at the end with the date and the reason; the original text stays.

## 1. Questions
- **P-A.** Does the gain from pooling vehicles of several owners survive when dispatch decisions move from Earth
  onto the robots, which hear one another only over terrain-limited radio and lose messages?
- **P-B.** Do rules of the road, enforced by a safety check on every vehicle, prevent every violation whatever the
  planner proposes, and what delay do they cost?
- **P-C.** Under which payment rules can no owner gain by misreporting costs, and is every owner at least as well
  off as working alone?

## 2. Conditions
Decision regimes: A_EARTH (strict, plan_ahead), A_MOON, B_EARTH (strict, plan_ahead), B_EARTH_RELAY (0.8, 1.0),
C_LEADER, C_AUCTION, C_LEARNED, O_ORACLE, as defined in `.team/inbox-backend.md` B-72 to B-74. "Without the
network" means A_EARTH and B_EARTH; "with the network" means C_LEADER, C_AUCTION and C_LEARNED.

## 3. Primary outcome and secondary outcomes
- Primary: mean waiting time of urgent cargo (h), per run year.
- Secondary: 95th-percentile urgent wait; share of urgent items delivered within 24 h; tonnes delivered per year;
  deadhead share; messages per robot-hour; failed team-lift meetings; per-owner profit; operator budget; for P-B,
  violations, near misses, minimum separation, deadlocks and delay per delivery.

## 4. Hypotheses and decision rules
Each paired comparison uses common random numbers (same seed across regimes), 30 seeds per cell unless stated,
the paired mean difference with a percentile bootstrap 95 % CI (20,000 resamples), and Holm's correction across
the confirmatory family {H1, H2, H3a, H4, H6} at 30 % load. A claim of "no practical difference" needs a TOST
with margin ±10 % of the oracle's mean.

- **H1 (sharing).** At 30 % and 60 % load, B regimes with full Earth coverage cut the primary outcome versus A
  regimes with full coverage. Supported if the CI excludes zero in the predicted direction.
- **H2 (availability), confirmatory.** B_EARTH strict is worse than O_ORACLE by at least half of the A-vs-O
  pooling gap in start years whose BASE Earth visibility is below 60 %. plan_ahead recovers part; relay 0.8
  recovers most (within 10 % of O by TOST).
- **H3a (decentralisation).** At message loss <= 0.10 with terrain radio, C_AUCTION is within 10 % of O_ORACLE
  (TOST). **H3b (exploratory).** At loss 0.25-0.40, bundle depth 5 is worse than depth 1. **H3c (exploratory).**
  C_LEADER matches C_AUCTION unless the mesh partitions.
- **H4 (learning).** At 30-60 % load, C_LEARNED beats C_AUCTION on held-out seeds 1-30 by a CI that excludes
  zero; at 10 % load the difference is within ±2 % (TOST). Also reported: the linear model on the same features,
  and every out-of-distribution test, whichever way they come out.
- **H5 (incentives, P-C).** First-price bids let at least one owner gain by shading; per-item second price
  reduces the largest gain; posted price with Shapley sharing leaves no owner worse off than alone in any tested
  coalition. The operator's budget is reported, not assumed balanced.
- **H6 (team lifts).** Allowing cross-owner pairs raises the share of items delivered; at loss >= 0.25 failed
  meetings rise without a commit-and-timeout step.
- **H7 (safety, P-B).** Zero violations in each of 12 encounter types (10^5 encounters per type); each rule
  removed in the model checker produces a counterexample. Reported bound per type: 1 - 0.05^(1/n).
- **H8 (cost of safety, P-B).** At today's fleet density the rules add less than 5 % to the delay per delivery;
  at 4-8x density the cost rises. Exploratory beyond that statement.

## 5. Seeds, exclusions and stopping
Training seeds 1000+, tuning 2000+, evaluation 1-30 (P-A); no evaluation seed is used for training or tuning.
No run is excluded after the fact. A run that crashes is fixed and rerun with the same seed, and the crash is
reported. If CIs at 30 seeds are wider than ±10 % of the mean, seeds are added in blocks of 10 up to 60, with the
rule written before looking at differences (the v2 sequential rule on the primary outcome's half-width only).

## 6. What would count against us
If H2 fails (an Earth-only dispatcher keeps most of the gain), the case for an on-Moon network rests only on
latency-bound decisions and team lifts, and the paper says so. If H3a fails, decentralised dispatch costs more
than it saves at the loss rates tested, and the paper reports at what loss it breaks even. If H4 fails, the
learned bids are described as no better than hand-built bids.

## Changes after the first main-run row
(none yet)

### Change 1, 27 Oct 2026 (before any main run): papers regrouped by the owner
The owner set the three papers: P1 job sharing, team-ups and direct communication with learned matching
(hypotheses H1-H4, H6 unchanged); P2 traffic rules and safety layers on the Moon and Mars (H7, H8 unchanged; a Mars
part is added as exploratory, H9 below); P3 the real vehicles, the radio network, what Lunar ATC puts inside each
vehicle and how its market works (H5 unchanged and moved here; H10 below, exploratory).
- **H9 (Mars, exploratory).** The same rules keep zero violations under Mars gravity and braking; the delay cost
  of the rules is similar to the Moon's; Earth-dependent coordination loses more on Mars than on the Moon because
  of 6-44 min round trips and conjunction blackouts.
- **H10 (sizing, exploratory).** The safety check, the bidding and the radio traffic of Lunar ATC fit a
  flight-class computer (reported as measured CPU time, memory and bytes per robot-hour, scaled to a reference
  radiation-tolerant processor with a stated factor) and a 16 kbit/s-class link for 20 robots.

### Change 2, 27 Oct 2026 (before any main run; after a 5-seed smoke run, disclosed): H2's yardstick
What we saw: B-72's smoke table (`results/ATC_regimes_smoke.json`, 5 seeds, 2028 and 2038, 30 % load). It showed
that the A-vs-O gap in censored urgent wait (~1,250 h) is almost all cargo that owners working alone can never
move (owner C's fleet cannot lift it and owners alone get no team lifts). So "half the A-vs-O gap" measures fleet
capacity, not Earth availability, and H2 as written could not test what it was meant to test. We saw the smoke
numbers before writing this change; the revision is stated so that it does not depend on them.
- **H2 (revised), confirmatory.** Availability is measured inside the pooled fleet, where capacity is equal:
  B_EARTH strict versus O_ORACLE (identical to B_EARTH at coverage 1.0, checked by a degenerate test). Supported if
  the paired difference in the primary outcome excludes zero and its lower CI bound exceeds 10 % of O's mean (the
  same margin as our TOST rule), in each start year whose BASE visibility is below 60 %, and in the pooled years.
  Secondary, as before: plan_ahead recovers part; relay 0.8 within 10 % of O by TOST.
- Reported but not tested: the original yardstick, and the delivered-only version of the A-vs-O gap, with a note
  that delivered-only waits are conditioned on delivery and so differ in which items they contain.
- H1 is unchanged; the smoke run suggests most of the sharing gain at this fleet is capacity (team lifts across
  owners), which the paper will separate from dispatch quality using E42.

### Change 3, 27 Oct 2026 (after B-74's evaluation on seeds 1-30, before any E40 run): which learned policy E40 uses
What we saw: B-74 (`results/ATC_learned_eval.json`). The MLP (imitation, then CEM on its output weights) is no better
than the hand-built bids; the linear correction (13 weights, CEM) cuts the primary outcome by 16.8 % at 30 % load and
42 % at 60 %, and by 10.6 % at 10 % load, so H4's "within +-2 % at 10 % load" part fails. H4 is reported exactly so:
not supported for the MLP (the pre-registered C_LEARNED), supported for the linear model at 30-60 % load.
- Because we have now seen both policies on seeds 1-30, E40 does not pick one: it runs both, as C_LEARNED_MLP and
  C_LEARNED_LIN, in every cell where C_LEARNED appears, and the paper reports both. No new training or tuning of
  either policy happens after this point (no distillation of the linear policy into the MLP for E40).
- Any headline about learned bids in P1 names the linear model and says it was the secondary model in this plan.

### Change 4, 28 Oct 2026 (before the final E40/E42 analysis): two defects found in the runs, and how they are handled
1. Pseudo-replication. In the p5 runs, a regime that never waits for Earth (O, B_EARTH_RELAY 1.0, A_EARTH full
   coverage, C_LEADER, C_AUCTION, both learned regimes) gives the same run for a seed whatever the start year, so
   its v3 block repeats seeds 1-10 five times. Every comparison between two such regimes therefore uses the v1
   block only (n = 30, the design written above). Comparisons involving an Earth-dependent regime (H2,
   plan_ahead, relay 0.8, A_EARTH with Earth windows, A_MOON) use both blocks, as planned. The 60 % cells of the
   Earth-independent regimes are run on v1 only. The interim statement in commit 197a574 that the on-Moon auction
   beats the full-information marketplace by 8.7 % came from this defect. On v1 the difference is
   -0.38 h [-1.99, 1.16], and that statement is withdrawn.
2. Run-to-run nondeterminism. The auction ordered robots by Python's per-process string hash, so the random
   draws under message loss differed between processes. Each such run is still a valid draw, but not
   bit-reproducible. The order is now sorted. The affected rows (C_AUCTION and the learned regimes at loss > 0 in
   E40, and C_AUCTION at loss > 0 in E42) are rerun with the fix and replace the old rows. The old rows are kept
   in results/archive/ and compared with the new ones in the B-75 report. B-73's smoke run and B-74's evaluation
   were made before the fix and are reported as statistically valid but not bit-exact.

### Issue 5, 28 Oct 2026 (found after the E40/E42 analysis and the P1 draft; decision pending): duplicate wake-ups
What we saw (B-77, `results/ATC_wake_check.json`, `tools/atc/wake_check.py`). The v2 marketplace's bulk
consolidation hold pushes a WAKE event for every held lane at that lane's deadline on every dispatch call, so N calls
give N wake-ups, each of which re-runs dispatch and pushes again (2.37 M WAKEs in a 21-day run at 8x the fleet; one
E41 run at 1x took 10,916 s). A dedupe that keeps one pending WAKE per lane and deadline was built as an opt-in flag
and tested against stored rows, on the claim that a repeated call at the same instant assigns nothing.
- The claim is false. With the flag on, 0 of 54 stored rows reproduce. Earth-dependent regimes and O_ORACLE change
  only in per-call counters or by <= 0.001 h; the on-Moon regimes (C_*) and E43 move. Mean / max |delta| of the
  primary outcome over 4-5 seeds per cell: C_LEADER -5.8 / 17.0 h, C_AUCTION -1.8 / 7.0, C_LEARNED_MLP +0.9 / 3.6,
  C_LEARNED_LIN +2.1 / 8.5, E43 atc 1x +0.2 / 1.1, E43 uncoordinated 1x -4.6 / 23.1.
- A direct audit (duplicates pushed anyway and every call checked) found that a few duplicate calls start a job
  (1 of 44,315 in an E43 run; 3 of 83,370 in an E40 C_AUCTION run) and most change the auction's per-call counters.
  Reading (hypothesis): duplicates fire a float-noise later, after a time-dependent condition has flipped (an operator
  freed, a window opened), so they act as accidental extra wake-ups that the design never specified.
- Consequence: the stored rows are reproducible with the flag off, but the on-Moon regimes' numbers depend on how many
  accidental wake-ups the hold generated, which differs by regime. H3a and H4 (P1) and H8 (P2) are affected in
  principle; the direction of the shift on 4-5 seeds (auction and leader improve, learned bids worsen) would narrow
  H4's linear-model gain. No result is withdrawn yet; the P1 draft is not final until this is settled.
- Options, written before the decision: (a) keep the stored rows, disclose the artefact as a limitation, run E41 and
  the rest as they are (about ten more multi-hour storm runs expected); (b) fix the hold properly (every state change
  that can enable a job schedules its own wake-up, then one WAKE per lane and deadline), verify on the audit that no
  duplicate call ever assigns, rerun every affected cell (E40 C regimes, E42, E41, E43 atc and uncoordinated), and
  report the before/after as change 5; (c) as (b) but keep the old rows in the paper alongside the new ones.
  LEAD recommends (b): the artefact is a dispatcher polling pattern no design specified, and results should not
  depend on it. The owner decides; E41 is paused meanwhile (132 of 1,560 runs, kept in
  results/E41_runs.lead.csv until the decision).
- Diagnostic (B-77 follow-up, 28 Oct 2026, scratch data only, no results files changed). The "missing wake-up"
  reading above is rejected: every duplicate call that started a job came 0.0 h after the previous call, with no
  state change between them. The gap is that one dispatch call is greedy and does not reach a fixed point (for
  example the hold's capacity reference is recomputed over the vehicles still free, so a second call at the same
  instant releases what the first held). A proper fix was built behind the opt-in flag p5["dispatch_fixpoint"]:
  one pending consolidation WAKE per lane and oldest lot, and after any call that changed state, dispatch again at
  the same instant until a call changes nothing (cap 64, never reached). Audit with duplicates pushed anyway: 0 of
  41,307 duplicate calls assign anything in an E43 run, 0 of 31,782 in an E40 C_AUCTION run.
  Effect on the primary outcome (urgent wait), mean / max |delta| over 4-5 seeds per cell, fix minus stored:
  C_LEADER +0.8 / 6.6 h, C_AUCTION +0.3 / 5.3, C_LEARNED_MLP +0.8 / 2.6, C_LEARNED_LIN -0.2 / 3.5, E43 atc 1x
  +0.6 / 7.7, E43 uncoordinated 1x -11.0 / 32.6 (against an effect of about +46 h). The fix also moves
  Earth-dependent regimes and O_ORACLE on single seeds (B_EARTH strict at 60 % +21.2 h on one seed; O_ORACLE +0.4
  / 2.7), so a rerun cannot be limited to the on-Moon regimes; A_EARTH strict is unchanged. Runs with the fix are
  faster (5-7 s against 11-80 s) and the 8x cells of E43 fit a chunk at 60 days. Rerun estimate with the fix,
  single process: E40 all regimes about 2,780 runs, 8.5 h; E42 1,170 runs, 2 h; E41 1,560 runs, 3 h; E43 all cells
  including 8x at 60 days, 650 runs, 1.6 h; about 15 h in all. Old rows stay reproducible with the flag off.
  LEAD's recommendation stands: option (b), the fix as the dispatcher's defined behaviour, every affected block
  rerun, the before/after reported as change 5, and the old rows archived. Decision: pending the owner.

### Change 5, 28 Oct 2026 (after the E40/E42 analysis and the P1 draft; the owner's decision on issue 5): dispatch runs to a fixed point
The owner chose option (b). The dispatcher's defined behaviour is now: one pending consolidation wake-up per lane
and oldest lot, and after any dispatch call that changed state, dispatch again at the same instant until a call
changes nothing (flag p5["dispatch_fixpoint"], recorded in every row as dispatch_fixpoint = 1 with the fix's
counters). The accidental extra wake-ups of the old hold are gone; the audit found no duplicate call that assigns.
- Every block affected is rerun with the flag: E40 (all regimes and loads, both blocks), E42, E41 and E43 (all
  cells, the 8x cells at the original 60 days). Hypotheses, comparisons, seeds, blocks and decision rules are
  unchanged. No cell is dropped and no seed is added.
- The old rows are archived as results/archive/*pre-fixpoint-2026-10-28.csv and stay reproducible with the flag
  off. The B-75 analysis and the P1 draft 2 numbers are those of the old rows; after the rerun both are rebuilt
  from the new rows and the before/after of every tested comparison is reported in the papers (Section 4.6 of
  each) whichever way it comes out. The interim E43 numbers in P2 draft 0 are likewise superseded.
- Written before any rerun row existed.

### Change 6, 29 Oct 2026 (after E45 and the development runs of the encounter simulator; before any E44 main row): R9 gains a lateral conformance test; E44's sample size
Found by the exhaustive check and the development runs of B-78, written before the first main E44 encounter.
- **R9 (conformance) gains a lateral test.** A vehicle more than e_lat = 0.3 m (Assumed) off its filed path is
  nonconforming, and its occupied volume is its broadcast position inflated by that deviation. Every vehicle's safety
  check tests its path ahead, as driven, against the inflated volumes of nonconforming neighbours, and a nonconforming
  vehicle tests its own track against all neighbours. A conflict within 60 m is a stop line placed before it, net of
  the approaching vehicle's travel while braking. The position tolerance e_conf = 11 m stays for along-track lateness;
  it cannot catch a 1.75 m drift into a 3.5 m lane. Why: the shield of R1-R10 as first implemented tested only filed
  intents, so a drifting vehicle (encounter type 9) could touch a conforming neighbour. Development counts on 300
  type-9 encounters (results/E44_dev_r9.json): 31 encounters with a contact before the fix, 0 after; under the earlier
  per-second drift model 122 before. Reported in P2 as found and fixed during development.
- **Drift model.** Lateral drift grows per metre driven, not per second (a stopped vehicle does not slide); changed
  together with the fix. A stall behind a nonconforming vehicle is classified blocked_by_fault, not a deadlock.
- **R4's tie-break** is defined as the order in which the base computer queued the requests (its FIFO), not the
  filing clock; the logistics model already serves reservations in commit order, so E43 is unchanged. Wording only.
- **E44 sample size: 10^4 encounters per type (120,000), not 10^5.** Why: the simulator's throughput after batch
  compaction is 0.4-22 h per 10^5 encounters by type (type 11, sixteen vehicles, 21.8 h), 55 h in all on the shared
  8 GB machine; 10^4 per type takes about 5.5 h. Types 1 and 7 are cheap and run 10^5. The reported bound per type
  stays 1 - 0.05^(1/n) with zero violations (3.0e-4 at 10^4, 3.0e-5 at 10^5), and the Bonferroni bound at
  alpha/12 (5.5e-4 at 10^4) is reported beside it; with x > 0 violations the Clopper-Pearson upper bound. H7's
  decision rule (zero violations in every type) is unchanged. The weaker bound is a cost of compute, disclosed.
- **Importance sampling** on types 6 (the inside vehicle's exit distance: 70 % of draws in the far 40 %), 7 (crew
  emergence time: 80 % in the 40 s before the robot arrives) and 9 (dead-stop time: 80 % while inside the segment),
  with weights p/q reported and the bound computed on n_eff = (sum w)^2 / sum w^2.
- **Type 1 draws whose slope and friction cannot hold the vehicle** (about 26 % of draws) are not driven and are
  counted apart, not as violations and not in n.
- **Deadlocks** are counted only in encounters without the random fuzzer (a fuzzed planner may stop forever by
  construction).
- **R3 on rings.** The exit-bay rule is not deadlock-free on a ring of single-lane segments with finite bays (about
  1 % of three- and four-vehicle ring encounters in development, all nominal planners; a "keep one slot free" variant
  is worse). R3 is not amended. The ring frequency is reported with E44, the logistics model's zero deadlock count is
  reported as a property of that model (unbounded bays, one job at a time) and not of the rule, and whether the base
  has a physical single-lane ring is reported as undetermined from the route samples
  (results/ATC_roads_rings.json: 1 candidate ring at the default share after merging samples within 40 m).
- **E44 outcome classes (added 29 Oct, still before any main row).** Every encounter is classified into exactly one
  of not_driven, violation, blocked_by_fault, deadlock, finished, incomplete, with that precedence; incomplete means
  the encounter ended at its time limit, or was quiet by design (an idling fuzzer, a robot told to stay stopped, a
  vehicle held at a closed zone), with no violation, fault or deadlock. Deadlock is judged only where no fuzzer runs;
  a stalled fuzzer encounter is incomplete. An emergency-brake event (the shield finds no candidate that satisfies
  every rule and applies full braking) is an event, not an outcome, reported as a per-type rate beside the classes.
  Counts are reported unweighted; rates and bounds use the importance weights where sampled.

### Change 7, 29 Oct 2026 (before any E46 or E48 row; recorded while drafting P3 draft 0): H5's design and rules
What we saw: nothing from E46 or E48 (neither has run). The P3 draft found that B-76 REVISED (27 Oct) dropped the
first-price rule with the dropped manipulations, which would leave H5's first two clauses untestable, and that H5
carries no numeric decision rule. Decisions, all before the first E46 row:
- E46 keeps a first-price cell beside per-item second price and posted price with Shapley sharing, so that H5 is
  tested as registered. The manipulation test (bid scaling k in {0.8, 0.9, 1.1, 1.25}, one owner at a time) runs
  under first price and second price; posted price has no bid to scale.
- Decision rules for H5 (paired by seed, percentile bootstrap, 20,000 resamples). Clause 1 (first price invites
  shading): supported if, under first price, the largest gain in an owner's annual profit over bidding truthfully
  across the tested k has a 95 % CI above zero. Clause 2 (second price reduces it): supported if the largest such
  gain under per-item second price is smaller than under first price with the 95 % CI of the paired difference
  excluding zero. Clause 3 (posted price with Shapley sharing leaves no owner worse off than alone): supported if,
  for every owner in every tested coalition, the 95 % CI of (profit in the coalition - profit alone) does not lie
  entirely below zero; the point estimates are reported either way. The operator's budget (payments in minus
  payouts) is reported per rule as a mean with its interval, not tested.
- The individual-rationality baseline "alone" is the owners-alone regime decided on the Moon (A_MOON), on the
  same seeds, so that the comparison does not carry the Earth-availability effect of P1's H2. Coalitions are every
  non-empty subset of the three owners (7, plus the grand coalition's split), as the Shapley computation needs.
- Parameters not fixed by B-76 REVISED (the posted price per tonne-km and how Earth sets it, the owners' private
  cost distributions, the audit penalty multiple m) are set by BACKEND in data/scenarios/E46-design.json before the
  first row and read by P3 from that file; they are design inputs, not results.
- E48: the lander carries a Lunar ATC radio unit and the landing-announcement part only (no planner, no safety
  program), as the site's vehicle table shows; B-81 measures the on-robot part on the driving and flying classes.
  The MTBF levels, the reference flight processor and its benchmark, and the per-class frequency and transmit
  power are set in data/scenarios/E48-design.json before the first measurement and are flagged Assumed.

### Change 8, 29 Oct 2026 (after types 1-10 and 9 of the 25 type-11 batches of the E44 main run; before the E44 rerun): two simulator defects, one genuine finding, the main run restarted
What we saw: an interim summary of the paused main run showed violations in four encounter types (T4 37, T5 3,
T6 82, T9 58; every other type 0). BACKEND traced every violating encounter to one of three causes.
- **Defect, body geometry at corners (T4, T5; reaching T11 and T12 through T4).** The vehicle body was drawn
  backwards from the front disc along the front's current heading. Past a sharp corner the body swung sideways
  into the oncoming lane and registered false contacts. Fix: the body follows the path, with discs placed at
  s - L/2 +/- off along the centreline. The ten T4 and three T5 violating encounters are clean after the fix,
  with the fuzzer disabled. Run time rises by about 38 %.
- **Defect, T6 builder.** The random straight roads through the zone crossed with no junction control, so the
  contacts occurred at unmanaged crossings and not under R5 as the type intended. Fix: an R10 junction tile at
  every crossing, half-length (W + 1 m)/sin(angle) + 2 m. The five re-run encounters are clean.
- **Genuine finding, T9 dead stop (58 gap-below-D0 and 7 contacts; unchanged by both fixes).** A fault stops a
  vehicle instantly, while R1's d_min assumes the leader brakes at most at B_MAX = 0.8 m/s^2. A same-direction
  follower inside a single-lane segment therefore loses its margin. This is a limit of RSS-style separation
  against instantaneous stops and is reported as a result of E44, not corrected. A dead-stop margin variant is
  noted as future work and is not run.
Decisions: the parts of the paused run are archived as development output in results/archive/E44_parts_pre-body-fix/
with the counts above recorded as found and fixed; the main run is restarted for all 12 types at the same n
with both fixes; the type-11 batch size drops from 400 to 300 encounters so that each chunk stays inside the
480 s limit (sample size unchanged); the encounter fixtures are regenerated and tests/test_safety.py must pass
before the first rerun row. No outcome class, bound, rule or sample size of change 6 is altered.
