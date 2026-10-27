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
