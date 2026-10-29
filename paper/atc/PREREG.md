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
