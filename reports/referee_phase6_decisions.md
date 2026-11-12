# Referee round, Phase 6: LEAD's decisions (11 Nov 2026)

Three independent referee reports (`referee_phase6_p1.md`, `_p2.md`, `_p3.md`) each recommend major revision.
The numbers in the papers match the files (P1: 7 mismatches in 137 entries; P2: 4 in 117; P3: 3 in 898). The
problems are what the numbers are called and what is concluded from them. Every MUST FIX is accepted unless a
line below says otherwise. This file fixes the decisions that cut across papers, so the three revisions agree.

## A. Rules for the revision
1. A result that could not have come out otherwise (arithmetic on assumed inputs, a property of the rule, a
   count fixed by the design) is called a **design calculation** or a **property**, never "tested" or
   "supported". The Proved, tested, assumed tables gain a fourth status, "calculated from assumed inputs".
2. A hypothesis whose verdict depends on a reading chosen after the results is reported under every reading,
   and the verdict is "depends on the reading"; PREREG6 section 6 records it.
3. Recommendations follow only from comparisons at equal conditions. Where the conditions differ (unequal
   false-alarm rates, different fleets), the paper reports and does not recommend.
4. No pending placeholder, placeholder title or "to confirm" note may print in a paper. A result that is not in
   is named in one plain sentence in Limitations and Future work.
5. A claim about an outside source is kept only if the research notes record that the source was opened;
   otherwise it is cut or attributed as "as reported by <the source that was read>".

## B. Decisions that cross papers
1. **The lost-link release (P2 M6, P1 M9, P3 M6).** P1 and P2 state opposite rules, and releasing a silent
   vehicle's reservation is unsafe if it is dead inside the segment. One rule for all three papers: a silent
   holder's reservation is **not** released. After the timeout plus the grace period the segment is marked
   *unconfirmed*; another vehicle may enter it only at caution speed, the speed from which it can stop within
   its own perception range (P2's speed proposition), and reports what it finds. "No stuck reservation" is
   therefore withdrawn as a result; what E54 gives is the count and hours of unconfirmed segments, and the
   cost of caution-speed traversal is not priced. H14's second clause is reported as not testable as written.
2. **Hypothesis labels.** PREREG6's H9 and H10 are written H9' and H10' in all three papers (P2's notation).
3. **The position report (P3 M4, P1 M10).** The implemented POSITION carries no frame, datum, time-scale
   identifier or covariance, while the design text says every position carries them. BACKEND adds them in
   LRIP v0.2 (task B-100); until its sizes are in, the papers say what v0.1 actually serialises, that 41 B is
   the packet before link framing and coding (plus 12 B in a Proximity-1 frame), and that the traffic model
   holds 11 of the 15 message types.
4. **"Near the base" (P3 M5).** H9' clause 2 passes only under "two or more beacons in line of sight" (23 % of
   driving steps), a reading chosen after the results. BACKEND computes it under four readings on all seeds
   (B-101); the papers report all four and the verdict "depends on the reading".
5. **Reservation overlaps (P2 M2).** The overlap count is dropped as a safety measure. BACKEND reports overlap
   durations and the along-track gap at the moment of overlap (B-102); the papers state the margin's effect on
   those, or that it has none.
6. **The detector recommendation (P2 M1).** "The classical test stays in the safety path" is withdrawn. The
   papers report: on test the network finds most at equal false-alarm rates; out of distribution no detector
   keeps its false-alarm rate, so recall is not comparable; none is qualified for the safety path on this
   evidence.
7. **The clock guard (P2 M4).** Stated as observed: no conflict in 303 reservation pairs with clocks up to
   0.845 s off, the worst pair using 62 % of the guard; outside the guard proposition, which needs offsets
   within the guard.
8. **Design properties (P2 M7, P1 M12, P3 M6).** Grants lost equals the per-hop loss when the retry interval
   exceeds the grant lifetime; the 12 % same-owner share; H12's 1.06 %; H13's fleet sum; the ledger count: each
   is labelled a calculation, with the assumed input named.
9. **The radio condition (P3 M2).** The one-hop figure is reported with its basis (positions 97 % parked) and
   beside the share of driving time with a path to the base (56.6 %); BACKEND gives hops for driving vehicles
   (B-103).
10. **The two-ray law (P3 M14).** Kept as the model, with the referee's point stated: near the horizon the
    ground is not flat, and by the cited reference's method the loss is 4 to 5 dB higher (rates 1.4 to 2.4
    times lower); BACKEND checks that computation (B-104). No lunar measurement exists.
11. **Measured against estimated (P3 M1).** "0.39 MB" is a sum of estimates and "1.12 s" is the simulator's
    whole-fleet dispatch call: both are relabelled; BACKEND measures memory with tracemalloc and times one
    robot's bid computation (B-105).
12. **P1's Phase 5 claims (P1 M1 to M8, M11, M13).** Accepted as written by the referee: the primary outcome is
    wait to delivery; section 4.6's before/after numbers are redone for the primary outcome; the 99.5 % is cut
    or restated as what it is; H4 says the network was the registered model and the linear model secondary;
    H6 is reported in kilograms and in items; the seed rule's 28 unmet cells are stated; "trained by imitation"
    becomes "search from an imitation start that was not iterated"; Table 6 is recomputed on the rerun engine
    (B-106) or labelled as predating the fixes; 5,480 is stated with its 2,029 distinct E40 runs; the last
    sentence of the abstract is reworded to what was compared.
13. **P2's Phase 5 claims (P2 M5, M8 to M11).** "Hard violation" is defined as the code counts it; the ring
    deadlock rate is given per variant (0.26 % as written, 7.4 % with the unreported variant) with the right
    denominator; pad closures are 22.2 landings; the uphill case is stated as outside the no-collision
    proposition, with the slope at which the assumption fails (BACKEND runs uphill encounters, B-107); the
    bounds for types 4 to 6 are recomputed on fresh seeds (B-108).

## C. Order of work
BACKEND: B-100 to B-108 (analysis first: B-101, B-102, B-103, B-105, B-104; then B-106, B-107, B-108, B-100).
Papers: the three revision agents apply every wording and labelling fix now, from the reports and this file,
and state BACKEND-dependent items plainly as not yet available; a second short pass fills them in.
PREREG6 section 6 gains dated entries for B1, B4 and the sign test.
