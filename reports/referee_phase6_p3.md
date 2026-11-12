# Referee report on P3, "The Vehicles, the Network and the Market: What Lunar ATC Puts Inside Each Vehicle and How Its Marketplace Works"

Reviewed: `paper/p3/paper.html` as built on 11 November 2026 (all sections, Tables 1 to 18, Appendix A), against the results files, the code, the two pre-registrations and the research notes. Nothing in the repository was edited. The reviewer's scripts are in the session scratchpad, not in the repository. Two parts of the review were read by assistants and spot-checked by me: the comparison of external facts with the research notes (findings marked N) and the comparison with P1 and P2 (findings marked X). Everything else, including every number in the table at the end, I opened and recomputed myself.

## Summary of the paper

The paper asks what a shared, robot-run job market at a lunar south-pole base needs inside each vehicle and under itself, and how its money works among three owners. It gives a provenance-flagged table of seven vehicle classes; a line-of-sight radio mesh on 5 m terrain with a link budget; a "bill of materials" of four software parts and a radio unit, sized by timing the authors' Python implementation on a laptop and scaling it by a CoreMark ratio of 54.8 to a GR740 (E48); a market experiment over 1,080 simulated years that prices four payment rules after one allocation and tests bid scaling and audits (E46, H5); and, in a November revision written, registered, run and reported on one day, five "layers under the market": position without GPS (E50, a replay through a matched Kalman filter), clocks (E51, a check on logged reservations), a shared map (E52, bookkeeping with assumed change rates), an interaction protocol with authentication (E53, a byte count; E55, forgery counts), and store-and-forward with a lost-link rule (E54, a message-level replay), plus eight derivations in an appendix and two checks on real data. The headline results are: the safety check takes 41.8 % of one flight core; 20 robots' traffic fits 16 kbit/s only on a base-scheduled one-hop channel; one auction round in a hundred takes 1.12 s; every owner beats working alone but owner C loses against no payments; first-price shading is not shown; ranging holds 5 m near the base (4.2 m) and terrain fixes do not away from it (15.2 m); authentication adds 52 % to the bit rate.

## Recommendation: major revision

The three reasons that carry it:

1. **The sizing claims describe the simulator, not a vehicle.** The "peak memory" is not a measurement, the "auction round on the crew rover" is the simulator's dispatch call for the whole fleet pooled over one, four and eight times the fleet, the per-class rows are one function on one set of inputs, and the link claim's one-hop condition is taken from parked vehicles while the bytes come from moving ones, which have a path to the base 56.6 % of driving time by the authors' own file (findings M1 to M4).
2. **Several "supported" verdicts either rest on an analysis choice that is not in the registration or could not have failed.** H9's second clause passes only under a definition of "near the base" (two or more beacons in line of sight, 23 % of driving steps) that the registration does not contain; under the registered words it fails. H12, H13, half of H11, half of H14 and the ledger result are arithmetic on assumed inputs (M5, M6).
3. **The text and what was built or cited disagree in places a reviewer will check first.** The position message that was serialised and counted carries none of the frame, datum, time-scale and covariance fields the paper says every position carries; the money results depend on a value of time the paper never states; a placeholder is printed in Section 5.8; the paper contradicts itself on five external facts; and several citations support claims the notes mark as unverified or not opened (M7 to M13).

The arithmetic is sound: of 898 numbers checked against the files or recomputed, three are wrong, all in typed derived text and all minor (two roundings and an off-by-one). No number that the build writes from a results file differs from that file. The problem is what the numbers are said to mean.

## First reading, before any check

What a reader takes away: (1) Lunar ATC fits a flight processor with room to spare (41.8 % of a core, 0.4 MB). (2) Twenty robots fit a 16 kbit/s channel if the base schedules it. (3) Every owner gains by joining; the smallest pays for it; the second price costs the operator five times the first. (4) Ranging holds the 5 m budget near the base; nothing holds it away from the base. (5) A cheap crystal is enough for reservations; authentication costs half again the bit rate; store-and-forward with a lost-link rule loses no job.

What I least believed, and what the check found: (a) 41.8 % of a core from Python timings times a benchmark ratio: the number reproduces, and means little (M1, S1). (b) 4.2 m near the base from 3 m ranges to four nearly collinear beacons: reproduces, under a region rule that covers 23 % of driving and is not the registered one (M5). (c) "Lost no job where drop-and-retry lost 0.33 a seed": reproduces; it is ten awards of 6,028 in a replay, against a comparator whose retry budget the authors chose (S9).

---

## MUST FIX

**M1. Section 5.1, Table 3, Table 6, Table 18, abstract, conclusion: the "peak memory" was not measured, and the "auction round on the crew rover" is not a vehicle's computation.**
*What is wrong.* (a) The paper says E48 "measures the peak memory of the on-robot part" (3.4), "Measured: peak of the on-robot part" (Table 3), "the on-robot part peaked at 0.39 MB" (5.1). `tools/atc/run_e48.py` lines 661 to 675 compute it as a sum: the bytes of a 24 h reservation-table window at the assumed layouts, plus the ledger estimate (jobs times 128 B), plus the size on disk of two policy JSON files, plus a constant 0.05 MB "working data". No memory is measured anywhere in the script (no `tracemalloc`, no resident size). The results file says so itself: `classes.LTV1.peak_memory_note` = "24 h reservation-table window + a year's ledger copy + bid policies + working data (0.05 MB)". (b) "Scaled by the same factor, an auction round on the crew rover takes 0.11 s at the median and 1.12 s at the 99th percentile". What is timed (`run_e48.py` lines 246 to 255) is the whole call `mech(sim, cand, free)`: the simulator's dispatch for every free vehicle and every waiting item, including its simulation of the message exchange. The 84,367 rounds are pooled over the six timing runs at one, four and eight times the fleet (line 658), so the 99th percentile belongs mostly to the 64-vehicle runs. No single vehicle executes that function.
*Evidence.* `results/E48_sizing.json`: `classes.*.peak_memory_mb` 0.388 with the note above; `classes.*.cpu_auction_round_ms` {median 1.975, p99 20.528, n 84367}, identical in every class row; code lines cited.
*Smallest fix.* Relabel the memory as "Estimated: bytes of the reservation table (24 h), the ledger copy and the policy files at the assumed layouts; the program, its interpreter and its stack are not counted" in 3.4, Table 3, Table 6, 5.1 and Table 18, and drop "peaked". For the round: report the time per fleet size, say that it is the simulator's dispatch call for the whole fleet, and remove "on the crew rover". Abstract and conclusion: replace "one auction round in a hundred takes 1.12 s, above the one-second decision" with "the simulator's dispatch call for the whole fleet, pooled over one to eight times the fleet and scaled, takes 1.12 s at the 99th percentile; one vehicle's share of a round was not timed".

**M2. Sections 3.3, 4.2, 5.2, 5.11, abstract, conclusion: the one-hop, base-scheduled condition of the link claim is established on parked vehicles; the traffic is that of moving ones.**
*What is wrong.* The claim is that 20 robots' authenticated traffic needs 10.06 kbit/s "at the measured mean of 1.024 hops". (a) The 1.024 is taken over the robots' positions at 1,029 decision epochs of one seed, not over driving time. E53's "fleet geometry" draws positions from seed 1's trajectories with "every vehicle-step equally likely" (`tools/atc/run_e53.py` line 12); 97.4 % of vehicle-steps in that month are parked (`results/E50_errors.csv`, seed 1: 347,669 parked steps, 9,451 driving). (b) The traffic is 99.99 % position and status reports, sent at 1 Hz because a vehicle moves (the schema's own default is "1 Hz moving, 0.1 Hz parked", `lunarsim/schemas/lrip-v0.1.json`). (c) While driving, a vehicle has a radio path to the base 56.6 % of the time (range over seeds 47.7 to 62.9 %), against 93.2 % over all time: `results/E54_dtn.json`, `link_shares.linked_share_driving_time`. The paper reports the 93.2 % side (as "6.8 % of the attempts find none" and "5.6 % of the robot-epochs") and never the 56.6 %. A base cannot give a slot to, or hear a one-hop report from, a vehicle with no path to it. (d) Section 3.4 says "Status and intent are broadcast at 1 Hz for conformance [61]"; the counted traffic has status and intent at 0.1 Hz. With all three at 1 Hz the load is 41 + 43 + 38 = 122 B/s, 19.5 kbit/s for 20 robots at the sources, above the target before any airtime factor (X). (e) E53 gives every rover a 2.5 m antenna; half the fleet has 1.0 m.
*Smallest fix.* Report the 56.6 % beside the 93.2 % in 3.3 and 5.2. Recompute the hop count and the reach over driving steps only. State the report rates once and make 3.4 agree with them. Reword the claim: "the authenticated traffic of 20 robots, 7.86 kbit/s at the sources, would need 10.06 kbit/s of a base-scheduled channel if every robot were within one hop of the base; in the recorded month that holds for robots standing at sites, and a driving robot has a path to the base 57 % of the time".

**M3. Section 5.8, built text: a placeholder is printed.**
"[[PENDING E50b (B-90b): the delay with the fix stops in the engine]] [[PENDING E50 at 8x]]" stands in the body of Section 5.8 (`paper.html` line 407; it is text, not a comment). Remove it from the built paper; the sentence in 5.14 already says what is not run.

**M4. Sections 3.5, 3.6, 3.7, 3.8, 5.11, 6.3: the position report that was serialised and counted does not carry what the paper says every position carries.**
*What is wrong.* The paper states: "A position report carries the frame, the time scale, a covariance and the layers that contributed" (3.5); "Every time stamp in a Lunar ATC message names its time scale" (3.6); "every position in every message carries a frame identifier and a datum identifier; a receiver rejects a position without them" (3.7); and lists these in 6.3 as rules that "cost nothing to adopt". The implemented POSITION message (`lunarsim/schemas/lrip-v0.1.json`, id 1, 104 bits) has: east, north, height, heading, speed, one scalar `sigma_h`, one `nav_src` enumeration, a moving flag and spare bits. The 8-byte protocol header has version, type, sender and `t_valid` "on the site time base". There is no frame identifier, no datum identifier, no time-scale identifier and no covariance anywhere in the packet, nor in the example manifest (`data/atc/lrip/manifest-small_rover.json`). Research note 03 says it in one line: "Frame and datum are defined in the positioning note; here only the encoding"; notes 01 and 02 require the fields. The 41 B, the 49.1 B/s, the 52 % and the 7.86 kbit/s are all computed from the message without them.
*Smallest fix.* Either add the fields and recount (each byte added to POSITION adds 0.16 kbit/s for 20 rovers at the sources; three identifiers and a 2 by 2 covariance are at least 6 B, about 1 kbit/s), or change the four sentences to say where the identifiers travel (for example once, in the manifest or a site configuration message) and that the report carries one scalar uncertainty. As written, the design rule the paper calls Layer 0 is not in the protocol it measured.

**M5. Sections 4.1, 5.8, abstract, introduction, Table 18: H9's second clause is "supported" under a region rule that is not registered; under the registered wording it fails.**
*What is wrong.* The registration (`paper/atc/PREREG6.md`, H9) says: with ranging the error "stays inside the budget within radio range of the base beacons". E50 implements "near the base" as "the vehicle's route sample is in radio line of sight of at least 2 of the 4 beacons" (`tools/atc/run_e50.py`, `DESIGN.region_rule`). That rule is in neither the registration nor its dated changes, which do record the budget and the seed counts. It covers 23.1 % of driving steps (`results/E50_errors.csv`: 2,255 of 9,770 steps a seed); the paper gives the rule and never the share.
*Evidence, my reruns.* I ran `lunarsim/atc/pnt.py` on the recorded month for seeds 1 to 6 with the paper's parameters and the paper's code, changing only the mask (script in the session scratchpad; seed 1 reproduces the file's 54.5819, 4.1811 and 13.2878 m exactly). 95th percentile with ranging, mean over the six seeds:

| Region | Share of driving steps | p95 with ranging (m) | Seeds under 5 m |
|---|---|---|---|
| Two or more beacons in line of sight (the paper) | 23.6 % | 4.21 | 6 of 6 |
| One or more beacons in line of sight | 57.5 % | 12.9 | 0 of 6 |
| Within 1 km of the base | 67.7 % | 25.0 | 0 of 6 |
| Within 5 km of the base (the mesh's radio range) | 100 % | 47.1 | 0 of 6 |

The clause is also not robust to the one assumed input that drives it. The note gives 1 to 10 m for a range over the base radio and the model takes 3 m: at 10 m the paper's own region gives 9.6 m (0 of 6 seeds inside). A beacon survey error of 1 m in place of 0.15 m (see M9) gives 4.8 m (4 of 6 seeds inside), up from 4.2; an ultra-wideband reach of 50 m in place of 100 m gives 5.2 m (2 of 6 seeds inside).
Inside the paper's own region the abstract's "keeps position within the 5 m budget" is a 95th percentile: 2.9 % of those steps exceed 5 m, the largest error is 12 m on average and up to 22 m, and the vehicle's own 95 % bound, which is what a rule can act on, exceeds 5 m in 31 % of them (`E50_summary.json`, `errors.1.dr+ranging.near`; `E50_errors.csv`, `share_err_over_budget`). The paper reports only the 76 % for all steps.
*Smallest fix.* Record the region rule as a choice made with the experiment, not registered; give the share; report the clause under the registered words as well. Abstract: "where two or more of the four base beacons are in line of sight, 23 % of driving steps, ranging holds the 95th percentile of the position error at 4.2 m; within a kilometre of the base it does not (25.0 m)".

**M6. Sections 1, 4.1, 5.9 to 5.12, 6.1, Table 18: five results are reported as tested hypotheses or as counts over 30 seeds, and are arithmetic on assumed inputs.**
- *H12, "1.06 % of a full resend".* 42 tiles a day are assumed to change in each of three layers of 3,969 tiles: 126 / 11,907 = 1.058 %. The result is the assumption. The second clause, hazards first is current sooner "at every link rate", cannot fail: a subset sent first is always finished first, and the paired differences at 10, 16, 100 and 1,000 kbit/s are in exact inverse ratio to the rate (1,833.3, 1,145.8, 183.3, 18.3 s; `E52_map.json`, `h12.paired_24h`).
- *H13.* The busiest-link load is 20 × 49.105 B/s × 8 = 7.857 kbit/s; "it holds in every draw" because every draw has the same sum. It is the product that E48 already reported. Its verdict uses the comparison (load against target) that change 11 of the first registration replaced the same day with airtime; as airtime on random access it fails (21.36).
- *H11, second half.* "Its clock error still adds more to one-way ranging than the ranging radio's own noise of 0.3 m" is true of any oscillator, a perfect one included: the assumed transfer residual of 100 ns is 30 m. The 975 km at the 95th percentile comes from vehicles with no path to the base, which could not range to it either; the median at a 10 s resync is 92 m (`E51_clocks.json`, `rows[1].one_way_m_median`).
- *H14, second half* is by construction, which the paper says.
- *The ledger.* "330 of 930 daily ledger bundles (35 %)" is 11 of 31 bundles, the same 11 in each of the 30 seeds and at each loss (`E54_ledger.json`: every 14-day store-and-forward row has `lost` 330). It is a calendar fact: a 14-day lifetime is shorter than a 24.8-day gap. The gap is the imposed 14-day blackout laid over the month's own gaps: Earth is in view 52.7 % of that month without the blackout (`E48_sizing.json`, `e40_month.base_dte_share`) and 7.9 % with it (`E54_dtn.json`, `earth_up_share`). Where in the month the blackout is placed decides the number, and the paper does not say how days 8 to 22 were chosen.
*Smallest fix.* Report these as computed consequences of the stated inputs, without "supported" and without seed counts: for example "with 42 route tiles assumed to change a day in each layer, the changed tiles are 1.06 % of the map, so a sync of changed tiles is 1.06 % of a full resend"; "11 of the 31 daily bundles of the month".

**M7. Sections 3.9, 5.5, 5.6, Tables 8 and 9: the money parameters are never stated.**
*What is wrong.* Every profit, budget, Shapley value and transfer is in USD, and the paper says three times that the alone baseline is "dominated by its cargo's delay cost at its own value of time". The value of time is nowhere in the paper. It is in the code: 5,000, 1,000 and 100 USD an hour by priority, with undelivered items censored at the horizon; the operator costs 1,000 USD an hour; wear is half the unit cost per life hour (`tools/atc/run_e46.py` lines 73 to 83, 205 to 212). With these, carrier costs are 47.5 M USD a year and owner C alone loses 723 M USD: the Shapley values, the 804 M USD "pooling gain" and the 200 M USD transfer are delay priced at an assumed hourly rate, and the paper does not say how much of that delay is cargo never delivered and censored at the year's end.
*Smallest fix.* State the rates, the censoring rule and their flag (Assumed) in 3.9, and say in 5.6 what share of each owner's alone loss is censored undelivered cargo. A sweep of the value of time belongs in the limitations with the private-cost spread.

**M8. Table 4 and Section 3.5: provenance flags are stronger than the sources.**
- Navigation service: Table 4 flags "10 m (95 %)" as "Simulation by the providers (accuracy)". The simulation gives 17.2 m; 10 m is a target. `pnt.py` line 80 says so ("[INTEROP25] SIM (17.2 m); [LDN25, ML24] REQ"), Section 3.5 flags the same number Assumed, and Section 7 says it "is better than the 17.2 m". The reference for the target is not in the list (N).
- Terrain fix in the dark, "30 % of attempts failing", flagged "simulation and field tests": the code and note flag it Assumed (`pnt.py` line 71); the note's one data point is another quantity (N).
- "3 % in shadow … (one simulation gives 6.6 %)": the note does not say that traverse was in shadow, and 6.6 % is the note's own division (N).
- "The lunar crater-matching work takes 2 % as its requirement … (Spec)": the note records "typically < 2 %" as a design assumption of that work (N).
- Crystal: a single receiver's excursion as it warmed (0 to 8 × 10⁻⁷) is used as the distribution of constant offsets across vehicles. That is a modelling choice and should be flagged as one, not as "Measured on the Moon".
*Smallest fix.* Set the flags to what the notes hold: "Assumed (the providers' target; their simulation gives 17.2 m)", "Assumed" for the failure share, drop the parenthesis on 6.6 %, "design assumption of [70]" for the 2 %.

**M9. Table 4 against Section 3.7: one quantity, two values, both "Measured" from the same reference.**
Table 4: beacons "each surveyed to 0.15 m … Measured (the map's geolocation error after track adjustment) [76]". Section 3.7: the map's position is "good to about 1 m after track adjustment [76, 90] (Measured)". Note 01 holds 0.15 m and note 02 holds about 1 m, for different products (N). The 0.15 m is a model input of E50 (`pnt.py`, `beacon_sigma_m`); see M5 for what 1 m does. Say which product the base's beacons are surveyed on and use one value.

**M10. Internal contradictions on external facts.**
- Section 2.1: the two-rover carry "does not describe the inter-rover link [25]". Sections 3.4 and 6.2: "the one measured inter-rover coordination load on record … used 13.8 kB/s [25]". The note that read the paper has 13.83 kB/s on 2.4 GHz Wi-Fi (N). Delete the first.
- Table 1: CADRE "Flight or field hardware: Yes (flight)". Section 6.5: "It is built and tested, not flown." Change the cell to "Yes (built for flight)".
- Introduction: "The radio that would connect them is not standardised either." Section 3.8: CCSDS 883.0-B-2 "fixes Wi-Fi 6 and LTE Release 12 for the surface radio", so the earlier statement "is true of LunaNet 1.0 and no longer of CCSDS". Correct the introduction rather than retract it 200 lines later.
- Section 2.2: "Lander-to-payload Wi-Fi at 2.4 GHz is flown on Griffin and Peregrine [18]"; Section 3.3: "the Wi-Fi-class radio the Griffin lander flies". Reference [18] is a 2021 user's guide; the notes record that Peregrine did not reach the Moon and that Griffin has not launched (N). Write "is specified for".
- Section 6.5: Chang'e 8 "is the first planned mission on which robots of several makers share a site". The same note lists Griffin Mission One with two rovers of two companies on one lander, and its own sentence reads "of several makers and countries" (N).

**M11. Citations that support claims the notes mark as unverified, not opened or differently attributed.**
- [104], Section 3.8, "tolerates one false value only if it hears at least three others": note 03 says the cited report proves the continuous-time protocol and the discrete rule's paper "was not opened: UNVERIFIED".
- [102], Section 3.8, CAPSTONE ran Bundle Protocol version 7 "with custody transfer": the NASA release says only "the latest DTN protocols"; version 7 and custody come from an abstract of a paper the note says was not read and the paper does not cite.
- [51], Sections 2.1 and 6.5, "the number at which NASA's own policy analysis expected central coordination to become necessary": the note records it as a remark by "a major partner" that coordination "may become necessary".
- [33] and [30, 31], Section 2.4: marked "Low (not re-read)"; the deficit result is credited in the note to a paper that is not cited.
- [80], "JAXA plans a demonstration satellite for 2029": listed in note 01 under what could not be verified.
- Section 7: "Some statuses rest on secondary sources … each is named as such where it is used." It is not true: the hoppers' figures in the introduction, Blue Moon's 3 t and about ten related-work items rest on press, abstracts or secondary statements without saying so (N, list in S14).
- Section 3.8: "What no standard defines is what two rovers of different owners say to each other", and the introduction's "no standard says". Note 03 records that the message set follows VDA 5050 version 3.0.0 and the MassRobotics interoperability standard, topic for topic. Neither is cited. The novelty of the message set cannot be claimed while its two models are left out.
*Smallest fix.* Cite what was read for what it says; move the rest to "as reported in"; cite VDA 5050 and MassRobotics in 2.3 and 3.8 and say what the lunar case adds.

**M12. Section 6.2 and Section 3.3: "The mesh itself agrees with NASA's viewsheds."**
The 23.3 % is a share of route sample points along the roads of the Connecting Ridge within 5 km of a 10 m mast. The 10.6 to 23.7 % is a share of the area of a 20 by 20 km region at the Malapert massif for a 4 m tower. The suite's own check of exactly this comparison, R8, was skipped because "the published values use other criteria and antenna heights, so a fair comparison needs the prior-art note's criteria matched case by case" (Section 5.14). The paper cannot decline the comparison as unfair in 5.14 and report its outcome as agreement in 6.2. Reword: "is of the same order as the area shares of [16], which are for another site, another quantity and another tower height; the two were not matched."

**M13. Sections 4.1 and 7: the bare label H10 means two hypotheses in adjacent sentences.**
Section 4.1 sets the rule "in this paper H5 and H10 are the hypotheses of [59]" and two sentences later writes "The confirmatory family of [67] is H9, H10, H13, H14 and H15a … H10 is not supported as a whole (adjusted p = 0.93)". A reader will take the paper's own sizing hypothesis to be "not supported, p = 0.93". P2 writes H9′ and H10′ for the second registration's hypotheses and keeps H9 for Mars (X); P3's bare H9 is therefore P2's H9′. Use P2's primes in all three papers.

**M14. Appendix A, Proposition 1 as applied in Table 7, Proposition 2 and Section 7: the flat-ground law is evaluated where the paper's own horizon says the ground is not flat, and is not conservative there.**
*What is wrong.* Parts (a) and (b) assume flat ground; part (c) puts the horizon of two 2.5 m antennas at 5.89 km and of two 1.0 m antennas at 3.73 km. Table 7 then evaluates the flat-ground law at 5 km for the first pair, where the bulge of the sphere at mid-path is 1.80 m of the antennas' 2.5 m, and at exactly 3.73 km for the second, where it equals the antenna height. The statement "from the breakpoint outward the law is therefore optimistic by at most 0.36 dB" is true against the flat two-ray model and is not a bound on anything in Table 7.
*Evidence.* With the smooth-sphere method of the paper's own reference [20] (ITU-R P.526, sections 3.1 and 3.2, R = 1,737.4 km, 2.4 GHz) I get 23.0 dB above free space at 5 km for 2.5 m antennas (137.0 dB against the paper's 132.0) and 35.1 dB at 3.73 km for 1.0 m antennas (146.6 against 142.9). The rates of Table 7 become about 700 instead of 1,574 kbit/s for the rovers, 25 instead of 57.9 for the small rover, 49 instead of 113.5 for the hopper and 3,400 instead of 4,717 for the mast (first-term formula there). These are my computations with a standard method, not measurements; no verdict changes, and every Table 7 rate is about 1.4 to 2.4 times too high by the paper's own cited method. The first version's error was of the same kind.
*Smallest fix.* Add to the assumptions "d small against the horizon, so that d²/8R is small against both heights"; say in the worked example and in Table 7's caption that the hops used do not meet it; give the spherical value beside the flat one, or evaluate at hops that do. Table 18's "Proved" row is about a model on a plane and should say so.

**M15. Appendix A, Proposition 8, Sections 3.5 and 6.1: the proposition is right and is applied to the wrong quantity, with a selective example.**
- "E50's ranging layer left 57 m at the 95th percentile away from the base, a figure of the size these bounds allow." "Away from the base" is defined as fewer than two beacons in line of sight. The bound assumes all four in view. It says nothing about that region.
- Section 6.1: "The beacons are part of it too: the four of E50 lie nearly on one line … one beacon on a distant rise would change the bound more than a better ranging radio." The clause that failed is the one where at most one beacon is seen; collinearity is not its cause, and the sentence is offered next to a disclaimer that the reading "is the model's construction and not a finding".
- The bound is for one epoch of ranges with no prior. E50 is a sequential filter with a dead-reckoning prior and is not bound by it: at the oxygen plant the bound is 3.7 m one sigma, and E50's median error where two or more beacons are seen is 1.1 m. Section 3.5's "Proposition 8 gives the bound that beacon geometry puts on layer 2" is wrong for the layer as simulated.
- The worked example lists three sites with dilutions 1.2, 5.2 and 7.0, rising with distance. I reproduce them (1.24, 5.16, 7.03 with the pad beacon at its 1 km stand-off). The construction site, 0.26 km from the base and on the beacon line, has 8.9 by the same formula and is left out.
*Smallest fix.* Delete the 57 m sentence and the beacon sentence of 6.1; state that the bound is for a single epoch; add the construction site to the example.

---

## SHOULD FIX

**S1. Section 5.1, Table 6, abstract: the per-class rows and "the worst class".**
The four class rows time the same function, `safety_check(None, Move)`, on the same 20,000 moves drawn from the encounter fixtures; only the class speed differs (`run_e48.py` lines 181 to 194). The medians (577.0 to 583.4 µs) and 99th percentiles (693 to 763 µs) differ by timer noise. "Worst on the crew rover" and the abstract's "the worst class's safety check" name noise. Table 3 says the hopper runs "fewer rules"; that is not what was timed. The state argument is `None`: no reservation entries and no heard broadcasts are in the timed call. The 580 µs is what a Python function on numpy scalars costs; it says little about the rules. The results file calls the scaled share "an upper bound for a C implementation"; Section 7 says a flight implementation "could differ … in either direction". Choose one, say that the rows are one measurement, and report one row.

**S2. Section 4.1, 4.6, front matter: what "pre-registered" covers for the revision.**
The second registration was committed at 10:14 on 11 November 2026 and the first result at 17:43 the same day (`git log` on `paper/atc/PREREG6.md` and on the results files). That is a registration, and the paper should give the interval. Deviations that are not in its dated changes: the region rule of H9 (M5); E54 run as a message-level replay although the registration lists "urgent wait" among its outcomes and speaks of engine experiments, with that outcome unreported; the family reduced from five hypotheses to three; the sign test. The paper discloses the last two in 4.6 but says the Holm step follows "the rule of [67]"; the registration says only "{H9, H10, H13, H14, H15a} are confirmatory (Holm)". With all five counted the adjusted values are 0.005 for H15a and 0.008 for H14, so nothing changes; say so. The sign test is one-sided (p = 0.5⁹ = 0.00195, `phase6_family.json`); the paper does not say so. Two-sided it is 0.0039 and 0.0078 after Holm.

**S3. Sections 4.1, 4.5, 5.7: H5's status and its tests.**
H5 is outside the first registration's confirmatory family, {H1, H2, H3a, H4, H6} (`PREREG.md` section 4). The paper's reason for no correction, that H5 "is a single hypothesis with three clauses", is not the registered one. Six verdicts (three clauses, two splits) are given without correction. Clause 1 takes the largest of twelve cell means (three owners, four factors) and then bootstraps that cell: the interval of a selected maximum is biased upward, which here only strengthens "not supported". Say both.

**S4. Sections 3.9, 5.6, 5.7: H5's third clause tests superadditivity, not a payment rule.**
Under the posted price the quantity compared with alone is the owner's Shapley value, and the transfer is defined as Shapley value less cash, so the tariff cancels from every owner's payoff. A Shapley value is at least the stand-alone value whenever the coalition values are superadditive. The clause therefore asks whether pooling vehicles is superadditive in the simulator, which the companion paper already reports. Name the rule "Shapley sharing" and say the posted price sets the cash that flows before the transfer and nothing else; the transfers (200 M USD) are about 14 times the tariff cash (14.7 M USD).

**S5. Sections 4.2, 5.8, 7: E50 is a covariance analysis with a matched filter.**
`pnt.py` draws errors from the same linear-Gaussian model the filter assumes, with the leg bias as a filter state, no outlier, no non-line-of-sight range bias, no wrong fix accepted as good, and beacon survey errors treated in the filter as white. The reported error is the best any estimator could do if the model were the world. Say so in 4.2 in one sentence; the limitation on the "probability of a wrong fix that is declared good" covers one of these.

**S6. Appendix A, Proposition 2.**
"The rate at the longest hop of a route is a lower bound on the rate of every hop of it" holds only if every hop has the same antenna heights, power and gains. Counterexample from Table 7: a route with a 5 km rover-to-rover hop (1,574 kbit/s) and a 3.7 km small-rover hop (57.9 kbit/s). Add the assumption. Table 7's "rate" is the Shannon bound of a 1 MHz channel after a 10 dB margin; head the columns "Shannon bound".

**S7. Appendix A, Proposition 6; Section 5.10.**
The bound h(1 + 4nD) counts hash bytes in one direction. `smap.py` (`tree_walk_bytes`) counts the same. Not counted: the replies that say which children differ, and the paper's own 28 B per message (or 48 to 108 B per bundle). One opened node per message nearly doubles the walk. State the bound as "hash bytes" or add the framing. "The tree is the smaller as long as fewer than 206 tiles changed" should read "up to 206" (the bound is n < 206.7; at n = 206 the tree costs 39,560 B against 39,690).

**S8. Appendix A, Proposition 4 and Table 12; Section 5.9.**
(a) Table 12's first two rows give holdover times for budgets of 3.34 ns and 33.4 ns. The model's own transfer residual is 100 ns: the clock is outside both budgets at the instant of synchronisation. The formula sets the residual to zero (`run_e51.py` line 303, "r = 0") and the table inherits it. Mark both rows "not reachable with the assumed transfer". (b) The "simulated" column is the same closed form applied to 240 drawn clocks; "the build checks the two against each other" compares a formula with itself. (c) The "no guard" column counts a conflict whenever the later vehicle's clock error exceeds the earlier one's at a pair with zero nominal gap (`run_e51.py` line 119, `close > 2 × guard`). It counts back-to-back reservation pairs, about 26, and the sign of a difference; it is why the better clock shows 22 to 25 "conflicts" and the crystal at a 10 s resync shows 1. Drop the column or explain it. (d) The whole experiment rests on 303 pairs in 30 seeds at today's fleet; say that the four- and eight-times fleets, where reservations are frequent, were not checked.

**S9. Sections 4.2, 5.12: E54.**
(a) The comparator is the authors': five tries 180 s apart give up after 15 minutes against an award that lives an hour. Ten lost awards of 6,028 is what that budget produces; the registration does not fix it. Sweep it or say that the difference is the comparator's retry budget. (b) "A lost award is a lost job" is hypothetical: in the recorded run every job was done. (c) `E54_dtn.json` holds 82.1 lost-link returns a seed (`lost_link_returns_per_seed`), about 2.7 a day for eight vehicles, each a retrace at half speed that the replay does not drive and no delay figure contains. The paper does not report the count. (d) Custody alone lost 2 awards and the rule 0: the rule's contribution to the registered outcome is two awards in 30 months, with a returning vehicle given a direct link.

**S10. Section 3.8: the freshness window and store-and-forward do not fit together as written.**
"A receiver accepts a message only if … its counter is above the highest it has accepted from that sender under that key, and its time stamp is within 10 s of the receiver's clock." The next paragraph has awards living an hour, ledger bundles 14 days, and a custodian that retransmits after 10 s. As stated, every bundle delivered after 10 s is rejected, and a held award that arrives after a newer message from the base fails the counter test. The custodian cannot restamp an award the base signed. Say which messages the window and the monotonic counter apply to (the reports), and what protects a bundle (its own identifier, its lifetime and the signature). Proposition 7(b) is correct for the reports and silent on this.

**S11. Sections 5.13, 6.1, Table 18: what the real-data checks check.**
(a) No result of this paper uses code that turns an image into a position: the terrain fix of E50 is a Gaussian draw. "It tests the camera model, the frames and the kernels that position-from-image code rests on" should say that no such code is used here. The paper is otherwise careful to say the limb fit says nothing about a rover, and it does not imply otherwise. (b) In the Earth-link check the spacecraft is below the horizon at all 212 epochs (elevation −9.26° to −0.04°, `B97_realdata.json`, `geometry.orion_visible_share` 0.0). It checks the azimuth and elevation transformation against the toolkit the code is built on, to 6 × 10⁻¹⁴ degrees; it does not exercise the terrain mask that makes the Earth windows. Section 6.1's "the geometry code under the Earth windows agrees with the reference toolkit" should be narrowed to that.

**S12. Section 5.11: the agreement variant with the base mast.**
The paper quotes the cells with "no more faulty rovers than the rule is set for". In the same file, with two liars against a rule set for one, adding the mast lowers the share of runs that stay inside the honest range from 48 to 66 % to 2 to 24 % (`E55_integrity.json`, `consensus_with_base_mast.cells`, f = 2, F = 1). A well-connected node spreads a false value. One clause, since the paper's conclusion is to compute the estimate at the base.

**S13. Sections 3.3, 6.3: the mesh's sensitivity that the file holds and the paper omits.**
`results/ATC_mesh.json` has, beside line of sight at zero clearance, the share of pairs with 0.6 of the first Fresnel zone clear: at 2 to 5 km for rover antennas, 5.4 % at 2.4 GHz against 9.3 % with bare line of sight, and 1.8 % at 400 MHz. The mesh counts a grazing ray as a link, where the paper's own knife-edge figure is 6 dB. Report the 5.4 %. Section 6.3's case for a lunar UHF band gives the diffraction side only; the clearance side is in the file.

**S14. References and attributions (N).**
- [16]: the note's title is "Lunar Surface Network Relay Terminal: A Lunar Communications Platform"; the paper has "Lunar Surface Relay."
- [103]: arXiv 2610.34554 dated 19 October 2026 would be the 34,554th submission of the month on its 19th day; check the identifier.
- The GR740 benchmark (492.5 CoreMark per core, "ESA DSP Day 2016") is the base of the 54.8 and has no reference entry and no research note; it lives in a string in `run_e48.py`.
- Sources used and not listed: the target accuracy of the navigation service; the company post behind Eagle's night operation; the page behind "the first satellite is to ride with the IM-3 lander".
- [81]: note 01 says it was not opened, note 04 says it was.
- Proposition 3 attributes L_G to [23]; it is the IAU's defining constant.
- No date or year: [2], [3], [10], [13], [14], [20], [22], [63], [64], [86], [99], [100], [116]. No authors or initials: [24], [41], [53], [69] to [72], [74], [81] to [84], [103], [104]. Composite entries with untitled parts: [7], [11], [17], [21], [35]. The authors' own notes still list eleven entries as needing a publisher check.
- Rested on secondary or abstract-level reading without saying so: [7] in the introduction, [11], [29], [32], [34], [35] (the 20 to 30 % was read in [36]), [38], [41], [47], [53].
- "The one …" appears where the notes say "the closest found": the one mechanism-design study of self-interested robots, the one two-rover carry, the one measured inter-rover load, the only measured latency. The notes list counter-examples for the first three.
- Section 2.3 quotes 189 ms and 531 ms from [66]; the same sentence of the note has 3,908 ms for negotiation messages, the kind closest to an auction.
- Table 2: "Spec (High)" covers company claims (FLEX 2,000 kg; the small rover's 250 kg, 200 kg and 10.8 km/h) and bounds are printed as values ("about 2,000 lb", "more than", "up to"). The values equal the catalogue; add "(claim)" in the cells as the note has it.
- Table 1: "Yes" for measured radio traffic in the drone-traffic row (server messages) and for payments in the ride-hailing row (a fleet-size model) is not what those studies hold.

**S15. Consistency with P1 and P2 (X).**
- The lost-link ladder is stated three ways. P3: no first threshold, 10 min unheard, then a meeting point, "then parks with a beacon", others keep the space blocked "until it is heard", the base releases "60 s after its timeout". P1: 30 s, then 600 s, a meeting point after 1 h, blocked "until its timeout". P2: 5 s and 30 s, 10 min, "waits in a safe state", no meeting point. P3's design text ("until it is heard") contradicts its own E54 rule. `E54_dtn.json` says the base releases "at its timeout"; the 60 s is the grace period in the definition of a stuck reservation.
- P3 Section 1: "the proof that the safety program keeps them" is the subject of P2. P2 reports violations in one encounter type and deadlocks on a ring; P3's own Table 16 calls it "the open case of [61]". Write "the checks".
- P3 Section 1: P1 "found that it keeps the gain … through every blackout". P1's abstract says the equivalence test could not show it.
- P3 Section 3.3: a 1 ppm oscillator's drift is something "the cooperative lifts of [60] cannot tolerate". P1 states no clock requirement; its lift is a commit with a one-hour timeout.
- P1's abstract and claims table still say the message set fits "inside a 16 kbit/s budget" without the condition P3 now attaches.
- Section 5.11's "10 % to 26 %" and P2's "0 % to 30 %" for the same share are different subsets of the same cells; neither says which.
- The sign test is disclosed as added after the results only in P3.
- Reference lists: P1 gives P3's title as "…Inside Each Lunar Vehicle…"; P2 has "Title to be fixed"; P3 cites both companions as "Preprint, October 2026" although they report November experiments; "[59]" is the first registration in P3 and the second in P2.
- Agreeing, checked: every shared traffic, mesh, message-size, E50, E51, E54, E55 and Holm number, the load factor 2.806, the fleet and its ownership, the base computer's parameters.

**S16. Section 7, limitations that are missing or understated.**
- The value of time and the censoring of undelivered cargo (M7).
- That "near the base" is 23 % of driving, and the sensitivity of that clause (M5).
- That a driving vehicle has a path to the base 57 % of the time (M2).
- Hidden terminals, fading, and whether a base that sees 23 % of route points can schedule a channel at all.
- That E50's filter is matched to its truth model (S5).
- That E53 gives every rover a 2.5 m antenna and a 1 Hz rate whether it moves or not.
- That the sizing is of Python with numpy, and that the timed round is the simulator's.
- Understated: "The radio is a model" does not say that the mesh counts grazing rays (S13) or that the law is used at the horizon (M14).

**S17. Experiments a reviewer will ask for.**
1. E50 split by distance from the base and by number of beacons in view, with the ranging error, beacon survey error and ultra-wideband reach swept over the note's ranges (the six-seed run of M5 took seven minutes).
2. Hop count, reach and airtime over driving steps only, with 1.0 m antennas for owner C, and the report rate tied to motion.
3. The safety check in C on the laptop, to bound the language factor, before any scaling; and one vehicle's bid computation timed apart from the simulator's round.
4. The link budget with a spherical-ground or diffraction term at the hops used, and a comparison with the coverage atlas [103] the paper already cites.
5. E46 with the value of time and the private-cost spread swept; a best response rather than four fixed factors; five owners.
6. E54 with the comparator's retry budget swept and with the lost-link return driven in the engine, so that its 82 returns a seed appear in the delay.
7. E52 with the change rates swept; without that it has one free parameter and one result.
8. E51's conflict check at four and eight times the fleet.

**S18. Presentation: this is two papers.**
The built text is about 40,000 words, 18 tables, 116 references and eight propositions, on two unrelated questions. Split at the revision's own seam.
- *Paper A, "The vehicles and the market":* Sections 2.1, 2.4, 3.1, 3.2, 3.9, E46 and H5, 5.5 to 5.7, the market part of the discussion, and Section 6.5 as a short outlook. This is a complete mechanism-design study once M7 is fixed.
- *Paper B, "What each vehicle carries and the layers under it":* Sections 3.3 to 3.8, E48 and E50 to E55, Appendix A, Table 18.
- Tables 16 and 17 (a validation plan and a list of organisations to ask) are a proposal, correctly framed as one ("None of these organisations has been approached, and none endorses this work"), and belong in a supplement of either. The market section quotes no market size for the product and says why; that is right.
As it stands a reader has no path: the abstract carries more than a dozen numbers from six experiments, the introduction's results paragraph is about 380 words of verdicts, and Sections 4.1 and 4.6 are two paragraphs each of 370 to 560 words. Table 18 is the best page of the paper and should come first, after the abstract.

---

## OPTIONAL

**O1.** Section 3.3: free-space loss at 400 MHz is 84.5 dB at 1 km and 104.5 dB at 10 km; "85 and 105" rounds up.
**O2.** Abstract: "priced four payment rules over 1,080 simulated years". 780 of the years are market runs; 300 are the oracle, the owners alone and the pair coalitions.
**O3.** Section 4.2 (E54): "199 jobs … a seed" beside 6,028 awards (200.9 a seed); "88 single-lane reservations" is 87.6. Explain the first.
**O4.** Terms that need the repository: C_LEADER, C_AUCTION, A_MOON, "dispatch to a fixed point", "roads atc (15 % single-lane)", "B-72 defaults", "task B-97", "B-90b", "the lead", "the ten-minute rule", "FRONTEND's". Section 5.14's list of skipped checks is a log, not prose.
**O5.** Section 5.5: "Under first price … the carriers are paid their true costs" makes the first-price budget a calibration gap, as Section 7 says; Section 6.1 still reports it as "a deficit under first price (2.50 M USD …)" and a ratio "5.1 times". Drop the ratio.
**O6.** Section 4.2: the laptop's benchmark is assumed (6.0 CoreMark/MHz at turbo clock). Run CoreMark on the laptop; it takes a minute and removes the range 36.5 to 64.0.
**O7.** Proposition 3 quotes the rate to 0.001 µs a day; a kilometre of site height moves it by 0.0016 and the eccentricity term it names is 0.11 periodic. Quote 56.02, as the text of 3.6 does.
**O8.** Section 3.6: say that the crystal's distribution is uniform between 0 and 8 × 10⁻⁷ and one-signed; it is why the crystal's "no guard" count differs from the atomic clock's.
**O9.** Table 6 repeats two identical columns in five rows; give them once in the caption.
**O10.** Proposition 4's example gives 259 days and 5.7 s; Table 12 gives 258 days and 5.5 s for the same clock. Both are in the file (the formula at the 95th-percentile frequency error, and the fifth percentile over drawn clocks); say which is which in the example.
**O11.** `phase6_family.json` gives H15a's adjusted p as an upper bound, 0.003; P1 prints it as an equality (X).

---

## The eight propositions, one line each

| Proposition | Verdict | Gap |
|---|---|---|
| 1. Flat-ground loss, horizon | Correct with a gap | The statement is right for a plane and every worked number reproduces. Applied at hops where d²/8R is 0.7 to 1.0 of the antenna height; there it is 4 to 5 dB optimistic by the paper's own reference [20] (M14). "Flat ground" on a ridge is an assumption the paper flags as such; the claim "a model" is kept in Sections 7 and 8 and lost in Table 7's bare "rate". |
| 2. Rate of a hop | Correct with a gap | Monotone in distance only for equal heights, power and gains on every hop (S6). Numbers reproduce. |
| 3. Lunar clock rate | Correct | Each term and the sum reproduce (60.2147, 2.7128, 1.4769, 56.025 µs a day; 6.4844 × 10⁻¹⁰; 16.8 km a day; 58.7 without the Moon's potential). The constant in `clocks.py` is the same. |
| 4. Range from clock, holdover | Correct with a gap | (a), (b), (c) follow and reproduce. Part (c) sets the residual to zero while the model assumes 100 ns, which voids the nanosecond rows of Table 12 (S8). |
| 5. Wrong lunar frame | Correct | 0.02886°, 875.2 m, 662.9 m and 659.2 m reproduce from the three kernel angles in either rotation order; second-order term 0.44 m. |
| 6. Hash-tree bytes | Correct with a gap | Counts hashes one way; no replies, no framing (S7). 8,072 B, 39,690 B reproduce; threshold is 206.7, not "fewer than 206". |
| 7. Forgery and replay | Correct | 5.4 × 10⁻²⁰, 1.7 × 10⁻¹¹, 0.07, 391, 15.3, 136 years reproduce; 11 observed against 15.3 expected has probability 0.17 of being that low. Says nothing about a shared site key held by an insider, which the paper states, nor about bundles (S10). |
| 8. Beacon dilution | Correct, misapplied | Algebra checks, including (ii) and the (4d² + b²)/(4bd) form. Applied to a region and an estimator it does not cover; example omits the worst site (M15). |

I tried a counterexample to each. They are: for 1, the paper's own Table 7 hops; for 2, a mixed-class route; for 4, the 100 ns residual; for 6, one node per authenticated message; for 8, the construction site. For 3, 5 and 7 I found none within the stated assumptions.

---

## Checked numbers

All values opened in the file named and, where derived, recomputed. "✓" = equal at the paper's rounding. Sources are under `results/` unless a path is given. Rows that hold several values count each value.

| # | Claim (where) | Paper | File or computation | Source | Verdict |
|---|---|---|---|---|---|
| 1 | Scaling factor (abstract) | 54.8 | 27,000 / 492.5 = 54.82 | E48_sizing `flight.factor` | ✓ |
| 2 | Factor range | 36.5 to 64.0 | 18,000 / 492.5, 31,500 / 492.5 | `flight.factor_range` | ✓ |
| 3 | Safety check share (abstract) | 41.8 % | 763.3 µs × 54.8 × 10 Hz = 0.4183 | `h10.safety_core_share_flight_per_robot_10hz` | ✓ (see S1) |
| 4 | Scheduled airtime (abstract) | 10.06 | 7.857 × 1.024 / 0.8 | `airtime.rows` (secured, measured hops) | ✓ |
| 5 | Random access (abstract) | 21.87 | 7.857 × 1.024 / 0.3679 | same | ✓ |
| 6 | Two hops (abstract) | 19.64 | 7.857 × 2 / 0.8 | same | ✓ |
| 7 | Auction round, 99th pct scaled (abstract, conclusion) | 1.12 s | 20.528 ms × 54.8 = 1.125 s | `classes.*.cpu_auction_round_ms` | ✓ (see M1) |
| 8 | Simulated years (abstract, conclusion) | 1,080 | 1,080 | E46_fit `n_rows` | ✓ |
| 9 | Largest first-price gain (abstract, conclusion) | 7.7 M USD | 7.730 | E46_fit `H5.3eq.clause1.gain` | ✓ |
| 10 | Its interval | [−1.46, 18.53] | −1.463, 18.532 | same | ✓ |
| 11 | Near the base with ranging (abstract) | 4.2 m | 4.2156 | E50_summary `errors.1.dr+ranging.near.p95_m` | ✓ |
| 12 | Away with fixes (abstract) | 15.2 m | 15.234 | `errors.1.dr+ranging+fixes.away` | ✓ |
| 13 | Authentication overhead (abstract, conclusion) | 52 % | 392.8 / 258.4 = 1.520 | E53_bitrate `per_rover_at_1hz` | ✓ |
| 14 | Capacity plateau (conclusion) | 2,800 kg | 2,000 + 800 | `lunarsim/atc/vehicles-p5.json` | ✓ |
| 15 | Budgets: first, second price, equal | −2.50, −12.71 | −2.504, −12.710 | E46_fit `budget` | ✓ |
| 16 | Their intervals | [−4.78, −0.22], [−14.36, −11.11] | −4.784, −0.215; −14.358, −11.105 | same | ✓ |
| 17 | Budgets, 50/35/15 | −2.76, −13.07 | −2.762, −13.068 | same | ✓ |
| 18 | Owner C against no payments, six cells | all below zero | −14.7, −6.5, −14.5, −6.2, −214.4, −84.6 with intervals below zero | E46_fit `vs_none` | ✓ |
| 19 | Safety check median / p99, four classes | 583.4/763.3, 578.2/731.1, 579.9/738.8, 577.0/693.4 | same | E48 `classes.*.cpu_safety_check_us` | ✓ (8 values) |
| 20 | Base reservation check | 136.2 / 190.8 | 136.2 / 190.81 | `classes.BASE` | ✓ |
| 21 | Auction round, rounds | 1.98 / 20.5 ms, 84,367 | 1.975 / 20.528, 84,367 | same | ✓ |
| 22 | On-robot memory | 0.39 MB | 0.388 (a sum, not a measurement) | `peak_memory_mb`, `peak_memory_note` | ✓ value; label wrong (M1) |
| 23 | Messages, bytes per robot-hour, 1x/4x/8x | 3,600.3 / 172,812; 3,604.2 / 172,945; 3,613.9 / 173,280 | same | `messages` | ✓ (6) |
| 24 | Per robot, 20 robots, unauthenticated | 48.0 B/s, 7.68 kbit/s | 172,811.6 / 3,600; × 160 | computed | ✓ |
| 25 | Authenticated: messages, bytes | 4,320.4; 176,779; 211,341 | same | `messages.secured` | ✓ (3) |
| 26 | Authenticated: per robot, 20 robots | 49.1 B/s; 7.86; 9.39 kbit/s | 49.105; 7.857; 9.393 | computed | ✓ (3) |
| 27 | Assumed byte layouts (9 types) | 48, 32, 32, 16, 40, 32, 32, 64, 128 | same | `messages.bytes_per_type` | ✓ (9) |
| 28 | Authenticated sizes, 8-byte code (10 types) | 41, 43, 38, 35, 94, 31, 37, 92, 33, 42 | same | `messages.secured.bytes_per_type.mac8`; E53 `sizes` | ✓ (10) |
| 29 | Ledger growth | 0.3, 1.4, 2.7 MB a year | 0.299, 1.351, 2.706 | `ledger_mb_per_year` | ✓ (3) |
| 30 | Market messages | 0.005 MB a day; 0.34 per robot-hour | 0.0049; 0.343 | `h10`, `per_robot_hour_by_type` | ✓ (2) |
| 31 | Hop histogram, no path | 5,686; 140; 5.6 %; 1.024 | 5,686; 140; 0.0564; 1.0240 | `revision.two_ray_in_the_mesh.e40_month` | ✓ (4) |
| 32 | One hop, scheduled / random | 9.82; 21.36 | 9.82; 21.36 | `airtime.rows`; E53 `h13` | ✓ (2) |
| 33 | Table 7 rates, flat ground | 1,574; 57.9; 113.5; 4,717 | 1,573.6; 57.9; 113.5; 4,716.9; recomputed 1,573.6, 57.86, 113.49, 4,716.9 | `classes.*.link` | ✓ (4) |
| 34 | Table 7 free-space rates | 6,976; 5,010; 5,988; 9,289 | 6,976.4; 5,010.4; 5,987.8; 9,289.1 | `link_free_space_upper_bound` | ✓ (4) |
| 35 | Table 7 latencies | 73, 72, 112, 89, 21 ms | 73.4, 71.6, 112.0, 89.1, 20.6; recomputed | `latency_budget_ms` | ✓ (5) |
| 36 | Mast in reach | 23.3 %, 19.1 % | 0.233, 0.191 | `reachable_share` | ✓ (2) |
| 37 | Uplink from a small rover | 1,180 kbit/s | 1,179.5 | `classes.BASE.link` | ✓ |
| 38 | Rates if visible at 5 km; ratios | 18.1, 36.0; 277, 166 times | 18.13, 36.04; 276.8, 166.3 | computed | ✓ (4) |
| 39 | Failover, three levels | 4.21/0.09/15.4; 1.10/0.02/4.0; 0.38/0.01/1.4 | 0.0421/0.00088/15.4; 0.011/0.00023/4.0; 0.0038/0.00008/1.4 | `failover.by_mtbf` | ✓ (9) |
| 40 | Runs, time | 21; 63 s; 0.1 h | 21; 62.8; 0.105 | `runs` | ✓ (3) |
| 41 | Mesh points, line-of-sight shares | 2,421; 50.5 %; 9.3 %; 6.3 % | 2,421; 0.5054; 0.0931; 0.0629 | ATC_mesh `los_by_distance_band` | ✓ (4) |
| 42 | Mast sees; two hops; most hops; median | 23.3 %; 58.1 %; 4; 2 | 0.2331; 0.5814; 4; 2.0 | `connectivity.rover_2.5m.5 km` | ✓ (4) |
| 43 | Isolated small-robot points, hops | 4; up to 5 | 4; 5 | `isolated`, `connectivity.small_1.0m` | ✓ (2) |
| 44 | Horizon check removes; 15 dB shares | 6.9 %; 94.2 %; 99.1 % | 1 − 0.9313; 0.9419; 0.9906 | E48 `revision.two_ray_in_the_mesh.mesh_pairs` | ✓ (3) |
| 45 | Tariffs | 19,828.85; 19,908.58 | same | E46_fit `tariff_usd_per_tkm` | ✓ (2) |
| 46 | Efficiency loss | 12.7 %, 35.9 % | 12.666, 35.88 | E46_cells.csv | ✓ (2) |
| 47 | Table 8 profits (8 rows × 3 owners) | as printed | as printed to 0.1 | E46_cells.csv, truthful rows | ✓ (24) |
| 48 | Table 8 settled, open | 16.1, 10.1, 20.9, 12.8, 14.7, 6.7; ≤ 0.01 | 16.11, 10.12, 20.88, 12.77, 14.73, 6.73; ≤ 0.009 | E46_cells.csv | ✓ (7) |
| 49 | Receipts, carrier cost | 45.0; 47.5 M USD | 44.996; 47.500 | E46_fit `budget.first.3eq` | ✓ (2) |
| 50 | Second-price shares | 16/84/64 %; 15/85/63 % | 0.155/0.845/0.637; 0.153/0.847/0.633 | `second_price` | ✓ (6) |
| 51 | Shapley transfers with intervals | +112 [96, 129]; +88 [76, 100]; −200 [−224, −176]; +34 [22, 46]; +44 [29, 62]; −78 [−94, −62] | same to rounding | `transfers` | ✓ (18) |
| 52 | Settled with transfers | 214.4 [190.9, 238.4]; 90.3 [77.1, 105.7] | same | `settled_with_transfers` | ✓ (6) |
| 53 | Table 9, 18 rows: difference and interval | as printed | as printed | `H5.*.clause3.rows` | ✓ (54) |
| 54 | Alone profits (derived) | −106.7, −118.7, −723.4; −141.9, −119.0, −313.0 | consistent with Table 8 less Table 9 (e.g. −251.7 − 471.7 = −723.4) | computed | ✓ (6) |
| 55 | Against no payments, 18 cells with intervals | as printed | as printed | `vs_none` | ✓ (54) |
| 56 | Largest gains, second price and 50/35/15 | 6.91 [−2.30, 17.71]; 5.23 [−9.72, 19.31]; 2.89 [−12.05, 16.97] | same | `max_gain` | ✓ (9) |
| 57 | Delay and system cost of the deviation | −5,500 h [−16,272, 3,704]; −15.07; −72 h [−11,323, 11,596]; +2.65 | same | `max_gain.*.system_cost_*` | ✓ (8) |
| 58 | Audits: recovered, net (8 cells) | 5 %/7.34; 20 %/6.18; 15 %/4.43; 61 %/2.03; 6 %/6.53; 22 %/5.37; 28 %/2.09; 111 %/−0.31 | same | `audits` | ✓ (16) |
| 59 | Clause 2 differences | −0.82 [−0.93, −0.70]; −2.33 [−2.51, −2.13] | same | `H5.*.clause2` | ✓ (6) |
| 60 | Cash part, post hoc | 2.57 [2.43, 2.73]; 5.40 [5.01, 5.80]; 1.75; 3.05 | same | `exploratory.allocation_fixed_gain` | ✓ (8) |
| 61 | Delay term mean, s.d., ratio | +5.16, −0.17; 29, 41; 7.6 | 5.157, −0.171; 28.6, 41.1; 41.09 / 5.40 = 7.61 | `exploratory.reallocation_term` | ✓ (5) |
| 62 | Pooling gain and shares (6.1) | 804; 7/8/85 %; 21/20/59 %; 438 | 803.7; 6.5/8.1/85.4; 21.4/19.9/58.7; 437.8 | computed from Tables 8, 9 | ✓ (8) |
| 63 | Deficit ratio | 5.1 times | 12.71 / 2.50 = 5.08 | computed | ✓ |
| 64 | E50 today's fleet, 95th pct, four layer sets × three regions with intervals | Table 10 and 5.8 | as printed | E50_summary `errors.1` | ✓ (20) |
| 65 | E50 four times, same | Table 10 and 5.8 | as printed | `errors.4` | ✓ (20) |
| 66 | Medians, both fleets | 293, 3.87, 1.70, 1.30; 325, 3.41, 1.74, 1.29 | same | same | ✓ (8) |
| 67 | First and eighth driving hour | 85, 308; 99, 346 | 85.2, 307.8; 99.0, 346.0 | `shift_p95_m_mean_over_seeds` | ✓ (4) |
| 68 | Own bound over budget | 100/76/42/21 %; 100/76/45/23 % | same | `share_b95_over_budget` | ✓ (8) |
| 69 | Fix stops | 37.3 [35.5, 39.1]; 168.7 [163.7, 174.0]; 33.1; 150.4 | same | `fix_stop_h_per_month` | ✓ (8) |
| 70 | Seeds on the predicted side | 30, 30, 0 | 30 of 30 under 5 m (largest 4.64); 0 of 30 (smallest 11.4) | E50_errors.csv | ✓ (3) |
| 71 | Table 11, 14 rows × 7 values | as printed | as printed | E51_clocks `rows` | ✓ (98) |
| 72 | Pairs; failed attempts; median at 10 s | 303; 6.8 %; 92 m | 303; 0.0683; 92.1 | same | ✓ (3) |
| 73 | Table 12, 14 holdover times | as printed | as printed | `holdover.*.p5_over_vehicles_s` | ✓ (14) (see S8) |
| 74 | Steering factors | 1.5 to 7.1; 2.6 to 7.3; 5.19 against 1.63 km; 2.4 × 10⁻⁹ | 1.50 to 7.13; 2.63 to 7.26; 5.190, 1.626; √2 × 100 ns / 60 s | E51b_clocks `rows` | ✓ (7) |
| 75 | Mixed scales | 18 to 24 %; 42.7 against 34.5 km | 17.5 to 23.7 %; 42.72, 34.54 | same | ✓ (4) |
| 76 | E52 at one day | 126 versions; 1.97 MB; 1.06 %; 4,351 B; 120,760 B | 126.5; 1,965,482; 0.01059; 4,351; 120,760 | E52_table.csv | ✓ (5) |
| 77 | Times at 16 kbit/s | 57.6 s; 20.1 min; 21 times; 20.5 min | 57.64; 1,203.45; 20.9; 1,228.4 | same | ✓ (4) |
| 78 | Bytes by outage | 78 kB; 489 kB; 2.74; 2.81 MB | 77,636; 489,342; 2,737,099; 2,808,331 | same | ✓ (4) |
| 79 | Stale-map hits | 0.02, 0.80, 13.8; at most 0.08 and 1.65 | 0.017, 0.80, 13.78; 0.083, 1.65 | same | ✓ (5) |
| 80 | Paired means | 30.6 min, 19.1 min, 3.1 min, 18.3 s | 1,833.3, 1,145.8, 183.3, 18.3 s | E52_map `h12.paired_24h` | ✓ (4) |
| 81 | Table 13, 6 rows | as printed | as printed (16 and 100 kbit/s rows) | E52_table.csv | ✓ (48) |
| 82 | Full resend; tiles; route tiles | 185.5 MB; 3,969; 60 | 185,534,244; 63²; 60 | E52_map | ✓ (3) |
| 83 | Tile sizes | 2,048; 11,796; 32,768 B | 256² × 0.25 / 8; × 1.44 / 8; × 4 / 8 | computed; E52_map `layers` | ✓ (3) |
| 84 | 42 tiles: hazards, three layers | 86.0 kB; 1.96 MB | 86.0; 1.958 | computed | ✓ (2) |
| 85 | Table 14, fleet and spread, authenticated, 1 Hz | 1.96, 3.93, 7.86, 15.71, 31.25; 1.57, 2.75, 4.54, 8.68, 16.32 | same | E53_bitrate `rows` | ✓ (10) |
| 86 | Per rover; without authentication; 10 Hz | 0.393; 32.3 B/s; 5.17; 66.9; 44.0; 16.7 | 0.3928; 32.3; 5.17; 66.897; 44.05; 16.72 | same | ✓ (6) |
| 87 | Reach and hops | 30/43/62/83/93 %; 1.1 to 2.2; 1.01 to 1.03; 97 to 99 %; 58 % | 0.30/0.43/0.62/0.83/0.93; 1.14 to 2.16; 1.01 to 1.03; 0.97 to 0.99; 4.538 / 7.857 | same | ✓ (11) |
| 88 | Manifest; position without and with wide code | 1,200; 283; 27; 49 B | same | E53 `manifest_bytes`, `sizes` | ✓ (4) |
| 89 | Awards lost | 10, 4, 85 of 6,028; 2; 0 | same | E54_dtn `rows` | ✓ (6) |
| 90 | Award delay | 61.5, 3.3, 3.3 s | 61.55, 3.31, 3.33 | same | ✓ (3) |
| 91 | Grants lost; task states | 1,543 (25.6 %); 6,022; 1,946, 82, 2; 9.0 min; 33.0 s | 1,543 (0.256); 6,022; 1,946, 82, 2; 542.7 s; 33.0 | same | ✓ (8) |
| 92 | Age of information | 88.1 min; 30.9 h; 45.5 s; 2.5 min | 5,287 s; 111,296 s; 45.49; 148.9 | same | ✓ (4) |
| 93 | Stuck reservations, hours | 2,566; 7,349 | 2,566; 7,349.2 | same | ✓ (2) |
| 94 | Lost jobs a seed, difference | 0.33 [0.17, 0.53]; −0.33 [−0.53, −0.17] | same | `h14` | ✓ (6) |
| 95 | Sign test | 9, 0, 21; p = 0.002; 0.004 | 9, 0, 21; 0.5⁹ = 0.00195 (one-sided); 0.0039 | phase6_family `H14` | ✓ (5) |
| 96 | Family: H15a, H10 | at most 0.003; 0.93 | 0.002997 (bound); 0.932 | phase6_family | ✓ (2) |
| 97 | Ledger | 24.8 days; 330 of 930 (35 %); 25.8 days; 10.8; 24.8; 94 % | 24.81; 330/930; 25.81; 10.84; 24.81; 870/930 | E54_ledger | ✓ (7) (see M6) |
| 98 | Table 15, remaining cells | as printed | as printed | E54_dtn `rows` | ✓ (30) |
| 99 | Jobs and reservations a seed | 199; 88 | 199.3; 87.6 | E54_dtn | ✓ (2); 6,028 / 30 = 200.9 unexplained |
| 100 | Forgeries | 395 of 100,000; 391; 11 of 1,000,000; 15.3 | same | E55_integrity `auth.forgery` | ✓ (4) |
| 101 | Replays | 1,172 = 574 + 598; none accepted | same | `auth.replay` | ✓ (4) |
| 102 | Hears three others | 10 to 26 %; 0 % | 0.10 to 0.26 (F = 1, at most one liar); 0.0 | `consensus.cells` | ✓ (3) |
| 103 | With the mast | 58 to 96 %; 0 to 10 %; 0 to 16 % | 0.58 to 0.96; 0.0 to 0.10; 0.0 to 0.16 | `consensus_with_base_mast.cells` | ✓ (6) |
| 104 | Artemis frames | 6; 1 saturated; 5 usable; 4 with attitude; 2 Earth | same | B97_realdata `artemis2.images` | ✓ (5) |
| 105 | Range, direction, radius, angle | 0.25 to 1.29 %; 0.08 to 0.16°; 0.8 to 1.3 px; 0.08 to 0.11° | 0.248 to 1.293 %; 0.082 to 0.162°; 0.81 to 1.32; 0.079 to 0.112 | same | ✓ (8) |
| 106 | Moon frames at 79,000 km | 408 to 661 km; 110 to 230 km | 408.0, 660.6; 79,300 × tan(0.08° to 0.16°) = 111 to 224 | same; computed | ✓ (4) |
| 107 | Ranges; focal length | 79,000 to 186,000 km; 7,312 px | 79,297 to 186,160; 7,312.4 | same | ✓ (3) |
| 108 | Earth-link check | 212; 6 × 10⁻¹⁴°; 77.4 m | 212; 5.7 × 10⁻¹⁴; 77.43 | `geometry` | ✓ (3) |
| 109 | Revision's checks | 35; 32 analytic, 3 Monte Carlo; 144; all pass | 35; 32, 3; 144; 54 of 54 pass | vv_phase6 | ✓ (5) |
| 110 | Phase-5 checks | 9 rows; 50; 47/1/2; 27/8/7/4/3/1; 9 not run | same | vv_phase5 (`papers` contains P3) | ✓ (13) |
| 111 | Compute | 7 s; 2.1 h | 7.1; 2.129 | E46_fit | ✓ (2) |
| 112 | Fleet sums | 3,380 kg; 0.3 of pair mass | 80+80+2,000+800+400+20; 475 / 1,600 = 0.297 | catalogue; computed | ✓ (2) |
| 113 | Convoy comparison | 287 and 281 times | 13,800 / 48.0; / 49.1 | computed | ✓ (2) |
| 114 | Prop. 1 example | 0.1249 m; 114.0 dB; 200.1 m; 628.8 m; 132.0 dB; 5.89 km; 32.0 m; 100.6 m; 148.0 dB; 3.73 km; 0.36 dB; 6 dB | all reproduce | script; `radio.py` | ✓ (12) |
| 115 | Horizons, Fresnel, breakpoint (3.3) | 2.95, 1.86, 5.89, 8.84, 7.76 km; 5.6 m, 13.7 m; 128 m | 2.947, 1.864, 5.895, 8.842, 7.759; 5.59, 13.69; 128.1 | computed | ✓ (8) |
| 116 | Free-space loss (3.3) | 100, 120 dB; 85, 105 dB | 100.05, 120.05; **84.49, 104.49** | computed | 2 ✓; **2 mismatch (rounding, O1)** |
| 117 | Prop. 2 example | −109 dBm; 30.0 dBm; +3.0 dB; 1,574; 24.0 dBm; −19.0 dB; 18.1 | all reproduce | script | ✓ (7) |
| 118 | Prop. 3 example | 0.012151; 1.0497 × 10⁶; 60.2147; 2.7128; 1.4769; 56.025; 6.4844 × 10⁻¹⁰; 16.8 km; 58.7 | all reproduce | script; `clocks.py` | ✓ (9) |
| 119 | Prop. 4 example | 0.2998 m; 7.6 × 10⁻⁷; 36.5 h; 4.4 ms; 5.9 × 10⁻¹⁰; 3.5 × 10⁻¹⁶; 259 d; 5.7 s; 0.12 m; 0.084 m | reproduce (259 d and 5.7 s from the unrounded 5.88 × 10⁻¹⁰, 3.47 × 10⁻¹⁶) | script; E51 `holdover.*.analytic_y95_s` | ✓ (10) |
| 120 | Drift at 1 ppm | 86 ms a day | 86.4 | computed | ✓ |
| 121 | Prop. 5 example | 0.02886°; 875.2; 662.9; 659.2 m; under half a metre | 0.028863; 875.23; 662.86; 659.23; 0.44 | script | ✓ (5) |
| 122 | Prop. 6 example | D = 6; 8,072; 39,690; "below 206"; 4,880 for 180 | 6; 8,072; 39,690; **n < 206.7**; 4,880, 180.0 | script; E52 | 5 ✓; **1 off by one (S7)** |
| 123 | Prop. 7 example | 5.4 × 10⁻²⁰; 3.2 × 10⁸; 1.7 × 10⁻¹¹; 0.07; 136 years | all reproduce | script | ✓ (5) |
| 124 | Prop. 8 example | span 1.37 km; 1.0; 1.2, 5.2, 7.0; 1.2, 2.1, 4.0 km; 3.7, 15, 21 m | 1,372 m; 1.0; 1.24, 5.16, 7.03; 1.16, 2.14, 3.96; 3.7, 15.5, 21.1 | site coordinates from the mesh samples | ✓ (11) |
| 125 | Beacon survey against map position | 0.15 m (Table 4); about 1 m (3.7) | `pnt.py` uses 0.15; notes hold both | internal | **inconsistent (M9)** |
| 126 | Base releases a silent vehicle's reservation | "60 s after its timeout" | "at its timeout"; 60 s is `grace_s` in the stuck definition | E54_dtn `stuck_definition`, `parameters` | **ambiguous (S15)** |

Count: 898 numbers in rows 1 to 124 (rows 125 and 126 are not counted as numbers). Rows 1 to 18 are every number of the abstract and the conclusion (30 values); rows 19 to 111 are the methods tables and the results sections (786 values); rows 112 to 124 are derived quantities of Section 3 and every worked number of Appendix A (82 values). **Mismatches: 3**, all minor and all in typed derived text: the two free-space values at 400 MHz (row 116) and the tile threshold (row 122). No number that the build writes from a results file differs from that file. One pair of values is internally inconsistent (row 125) and one parameter is stated ambiguously (row 126).

---

## What I could not check, and why

1. **Any external source.** I opened no paper, standard, press release or web page. Findings marked N say what the research notes record, not whether the notes are right. Facts dated 2026 (contract awards, launch slips, mission status) are checked only against the notes.
2. **The engine runs behind E46, E48 and the recorded month.** I reran one month for six seeds through `run_e50.record` to reproduce E50 (it does, exactly) and reran nothing else. The 1,080 years of E46 and the timing runs of E48 are taken from their files.
3. **The serialisation and the cryptography.** I read the schema and the size table; I did not run the codec or the 45 conformance vectors.
4. **Whether the first registration's git history supports its dates.** I checked the dates of `PREREG6.md` and of the revision's results; I did not audit `PREREG.md`'s history commit by commit.
5. **The PDF.** I read the HTML. Whether the placeholder of M3 and the table layouts are the same in `vehicles_network_market_p3.pdf` I did not check. Figures were not inspected.
6. **P2's working copy.** `paper/p2/paper.html` had uncommitted changes when read; the comparison is with the file on disk.
7. **Table 13's three columns not at 16 or 100 kbit/s, and Table 14's unauthenticated and 0.1 Hz rows**, were spot-checked, not read cell by cell.
8. **The working copy of two code files.** `lunarsim/atc/pnt.py` and `lunarsim/atc/roads.py` had uncommitted changes from other work in progress (the E50b logging) when I read and ran them. My rerun of seed 1 through that copy reproduces the committed E50 values to four decimals, so the changes do not move E50; I did not diff them line by line.
9. **The spherical-ground figures of M14** are my computation with the formulae of ITU-R P.526 as I know them, not a run of a reference implementation; treat them as the size of the effect.
