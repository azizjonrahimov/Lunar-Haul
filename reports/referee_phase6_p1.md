# Referee report on P1, "Working Together Without Earth" (revision of 11 November 2026)

Reviewed: `paper/p1/paper.html` (all sections and both appendices), against `results/`, `lunarsim/`, `tools/atc/`,
`paper/atc/PREREG.md`, `paper/atc/PREREG6.md`, the research notes and the companion papers P2 and P3.
All recomputation was done from the raw rows and JSON files with my own scripts; `values.json` and the build's
checks were not used. Bootstrap intervals are mine (20,000 resamples, different random stream), so they differ
from the paper's in the last digit.

## 1. Summary of the paper

The paper simulates one year of cargo movement at a lunar south-pole base with eight vehicles in six classes
split among three owners, and compares thirteen ways of deciding who carries what: owners alone, a pooled
dispatcher on Earth that works only while Earth is in view (with plan-ahead and relay variants), and three
on-Moon schemes (a base computer as leader, an auction among the robots, the auction with learned bid
corrections), against a full-information marketplace. Its main results are paired differences in the mean
wait of urgent cargo over 30 seeds (80 where the regime depends on Earth): pooling against owners alone,
the cost of an Earth-bound dispatcher, the on-Moon auction against the marketplace, learned against
hand-built bids, and cross-owner team lifts. The November revision adds a message protocol (LRIP v0.1, a
schema and a codec), a byte count of its traffic on a geometric mesh (E53), a message-level replay of one
recorded month under three transports (E54), six propositions and a table that sorts every claim into
proved, tested, assumed or not tested.

First reading, written before any check. What a reader takes away: (1) almost all of the gain from pooling
is cargo owners alone cannot move; (2) a dispatcher on Earth that stops at blackouts costs about 90 h of
urgent wait; (3) an auction on the Moon is as good as a full-information dispatcher; (4) a 13-weight linear
bid correction gains 16.5 %; (5) the protocol fits a 16 kbit/s radio and store-and-forward with a lost-link
rule loses no jobs. What I believed least: the 99.5 % figure, the two protocol hypotheses reported as
"supported", and the size of the learned gain. The checks below bear on all three.

## 2. Recommendation: major revision

1. Several "supported" verdicts are not what the registered rules give, or are consequences of how the
   experiment was built: H4 for a model the registration names as secondary, H13 whose answer the design note
   had already computed, H14 whose first clause turns on an unswept retry cap in the baseline and whose
   second clause is true by construction, H6 tested on a different quantity from the one named, and a
   registered seed rule that was not applied in 28 of 40 cells while the paper admits to one comparison.
2. Headline quantities are defined or labelled wrongly: the primary outcome (the text says wait to pickup,
   the code measures to delivery), the 99.5 % share (built from two different comparisons and not a
   decomposition), the before-and-after numbers of the engine fix (a different metric from the one named),
   "5,480 simulated years" (721 are exact repeats), and "bytes on the air" (packets before framing and coding).
3. The protocol part claims more than was done. The codec exists and its sizes are right; the protocol does
   not run in the engine, the replay credits the lost-link rule with contact while the vehicle keeps to its
   recorded job, a training method is named that was not run (DAgger), and Table 6 and the guard runs come
   from the engine before two defects were fixed although the paper says every number is from the rerun.

The core E40 to E42 numbers reproduce from the raw rows. The problems are in what the numbers are called
and what is concluded from them, which is why this is not a rejection.

## 3. Propositions: verdicts

| Prop. | Verdict | Gap or note |
|---|---|---|
| 1 (one auction round) | Correct. Proof checked line by line; the charging argument holds. No counterexample in 4,000 random monotone submodular instances (lowest greedy/optimum: (a) 0.600, (b) 0.671, (c) 0.685) nor in 60,000 structured coverage instances for (c) (lowest 0.546). | Applicability gap. For the paper's cost auction the guarantee is in "value below a ceiling C" and depends on the free constant C; in cost the round can be arbitrarily worse than the optimum (costs c(1,a)=0, c(1,b)=c(2,a)=1, c(2,b)=M: greedy pays M, the optimum 2). Diminishing gain is not verified for the engine's bid. The 200-instance check uses a toy score on a 10 x 10 square (`ATC_auction_bounds.json`, "model"), not the engine's bids. See S4. |
| 2 (bit rate) | Correct (a counting identity). Worked numbers reproduce: 49.1 B/s, 7.86, 9.82, 21.4, 19.6 kbit/s; (1 - 1/20)^19 = 0.377. | L is counted in Space Packet bytes. Link framing, coding and bundle overhead are outside it (M10). |
| 3 (age of a relayed report) | Correct. All 12 cells of Table B1 reproduce; a simulation of the model gives 1.893 s against 1.900 s (p = 0.25, k = 3) and the tail (1 - q)^m to three decimals. | Part (a) is called "the engine's model", but Section 3.5 gives the engine a retry after 3 minutes. No experiment of the paper uses k > 1 for reports (E53 does not relay them); the table is illustrative. |
| 4 (hand-over) | Correct as formulas. 45 s, 0.08 and 53 false marks a day, k = 4, 7, 10, 53.6 min, 53.8 h and the ratio 60 all reproduce (Monte Carlo for (b) and (d) agrees). | The worked example contradicts the protocol of Section 3.13 and Table A2 in two places (heartbeat period, and re-auction before the second timeout or the lease). See S5. Not tested, as the paper says. |
| 5 (operators) | Correct (one line). Table B2 reproduces. | Circular as evidence: the inputs were "chosen so that the result sits near published ratios". It cannot serve as one of the "three reasons, each with a number" in Section 3.13. See S6. |
| 6 (size of a position report) | Correct arithmetic (97.4 bits, 98, 13 B, 41 B). | Not a lower bound in any useful sense: for six of the eight fields the "number of values" is 2^bits because the range was set by the bit width. See S6. |

## 4. Findings

### MUST FIX

**M1. The primary outcome is defined wrongly (Sections 4.4, 5.3).**
The text says the wait runs "from the moment the item is ready to its pickup". The code measures to delivery:
`lunarsim/atc/regimes.py` lines 698-699 use `c.t_delivered - c.t_ready`, and the engine keeps a separate
`t_picked` (`lunarsim/engine.py` 1163, 1175) that the outcome does not use. The same slip is in "the share
of urgent items picked up within 24 h" (4.4) and "picked up within a day" (5.3); Table 5's caption says
"delivered within a day", which is what the code computes.
Fix: "from the moment the item is ready to its delivery" and "delivered within 24 h" throughout.

**M2. The before-and-after numbers of the engine fix are for another metric (Section 4.6).**
The paper says "the primary outcome moved by -0.01 h on average and 1.3 h in absolute value, at most 105 h"
(E40), "-0.02, 0.3, at most 6 h" (E42), "+0.04, 0.3, at most 3 h" (E41). `E40_fixpoint_before_after.json`
has `"primary": "delay_mean_h"`, the mean delay per delivery of all cargo. For the paper's primary outcome
(`atc_urgent_wait_mean_cens_h`), matching the archived rows to the current ones by cell, seed and start year:
E40 -0.27 h on average, 2.41 h in absolute value, at most 153 h (B_EARTH plan_ahead, 60 %, seed 4, 2028);
E42 +0.21, 6.9, at most 256 h; E41 -0.10, 1.55, at most 18 h. The fix moved the primary outcome five to
twenty times more than the text says.
Change 5 of the pre-registration also promised "the before/after of every tested comparison ... in the papers
(Section 4.6 of each)". The paper gives row movements only. From the archive: H3a -0.38 [-1.98, 1.17] before,
-0.84 [-2.94, 0.95] after; H4 linear -2.49 before, -2.32 after; H2 91.3 before, 89.9 after; relay 0.8 3.08
before, 2.55 after. No verdict changes.
Fix: replace the three triples with the urgent-wait values and add a five-row before/after table of the
tested comparisons.

**M3. The 99.5 % figure (abstract, Sections 1, 5.2, 6.1, 6.3, 8).**
(a) The sentence in 5.2 joins two comparisons. "Owners alone with strict fallback wait 100 h longer" on
delivered items is A_EARTH strict against the marketplace (114.9 - 15.0 = 99.8 h, n = 80). The 99.5 % is
computed in `build_p1.py` (lines 606-612) from another pair, owners alone with full coverage against the
relay that is always up: 1 - 5.77/1232.4 (`table_E40_pairs.csv`, rows "H1 (reported): delivered-only urgent
wait", v1, and "H1"). With the figures of the sentence itself the share is 1 - 99.8/1241.6 = 92.0 %.
(b) One minus the ratio of the delivered-only difference to the censored difference is not a share of a gap.
The two differences are means over different item sets, as the paper itself notes; they do not add.
(c) "Never deliver" is "had not delivered by the end of the simulated year". The size of the gap (1,232 h,
and 2,575 h for owner C) is set by the horizon: an undelivered urgent item contributes the time from its
arrival to day 365, about half a year on average. A two-year run would roughly double it.
(d) The result follows from the inputs. Owner C is given a third of the cargo and no vehicle that can lift
most of it (in the owners-alone runs it delivers about 5 t a year, `own_C_delivered_t`), and team items are
drawn at 2,000 to 2,800 kg where the only same-owner pair lifts 2,080 kg.
Fix: delete the percentage. Proposed wording for the abstract: "In this fleet, where one owner has no cargo
rover, the gain from sharing is cargo that owners alone had not delivered by the end of the year: on the
items both deliver, owners alone with Earth always in view waited 5.8 h longer." Report the share of urgent
items undelivered at year end per regime in Table 5, say in 5.2 that the hour figures of H1 scale with the
one-year horizon, and state in Section 7 that the ownership split was not varied in E40 to E42.

**M4. H4: the verdict, the sentence about the registration, and the abstract (Sections 5.6, 4.5, Table 7,
Table 12, abstract, Section 8).**
(a) Section 5.6 says "H4 as registered names the learned policy without saying which model". The
registration says which: H4 is about C_LEARNED, with "also reported: the linear model on the same features",
and change 3 calls the network "the pre-registered C_LEARNED". (b) Change 3 also commits the paper: "Any
headline about learned bids in P1 names the linear model and says it was the secondary model in this plan."
The abstract and the conclusion name the linear model and do not say it was secondary. (c) The linear model
entered the Holm family (Table 7, adjusted p = 0.017) after its result on the evaluation seeds 1 to 30 was
known (change 3 is dated "after B-74's evaluation on seeds 1-30"; `ATC_learned_eval.json` has -2.39 h,
16.8 %, on those seeds). Section 4.6 reports the decision to run both models; it does not say the
confirmatory test of the linear model was added then. (d) "Evaluated once on held-out seeds" (contribution
4, Section 3.10): the E40 values are the third run of the frozen policies on seeds 1 to 30 (B-74, E40 before
the fix, E40 after). No selection used those seeds, which is the claim that can be made.
Fix: (a) "H4 as registered is about the network, with the linear model as a secondary report; for the
network it is not supported." (b) Abstract: "A linear bid correction, registered as the secondary model, cut
the wait by 16.5 %; the registered network did not." (c) Mark the H4-linear row of Table 7 "added to the
family after its result on these seeds was seen". (d) "No training or selection used seeds 1 to 30."

**M5. H6 is tested on mass and described as items (Section 5.7, Table 7, Table 12).**
"The share of all items delivered" rose "by 1.7 percentage points" and "5.4 percentage points (3.5 to 8.5)".
The metric in `table_E40_pairs.csv` rows 159-180 is `delivered_share`, which `lunarsim/engine.py` line 143
defines as `delivered_kg / ready_kg`. It is a share of mass. In items the effect at team share 0.25 is +80.7
items a year [28.1, 168.7] of about 2,930, that is 2.7 points; at team share 0.10 it is +11.8 items
[8.1, 15.7]. Both intervals exclude zero, so the verdict stands. Also, "registered on the share of all items
at team share 0.25" is not in `PREREG.md`: H6 names no team share, and the design default is 0.10.
Fix: "the share of ready cargo mass delivered"; give the item counts beside it; replace "registered on" with
"tested at team share 0.25, a cell the registration does not name; at the default 0.10 the difference is 1.7
points (1.5 to 2.0)".

**M6. The registered seed rule was not applied anywhere, not only for H3a (Sections 4.5, 7).**
`PREREG.md` section 5: "If CIs at 30 seeds are wider than +-10 % of the mean, seeds are added in blocks of 10
up to 60 ... (on the primary outcome's half-width only)". From `E40_runs.csv`, the 95 % half-width of the
cell mean exceeds 10 % of the mean in 28 of 40 cells, including every 30-run cell at 10 % and 30 % load
(marketplace at 30 %: 2.51 h on 14.93 h, 16.8 %; auction 14.6 %; linear 14.2 %; marketplace at 10 %:
29.0 %). Under the paper's own reading (half-width of the paired difference against 10 % of the reference
mean) H1 (163 h against 125 h) and H4 linear (1.65 h against 1.41 h) also exceed, besides H3a.
Fix: "The rule was not applied: no seeds were added in any cell, although the half-width exceeded 10 % of
the mean in 28 of the 40 E40 cells. Every interval is therefore from the fixed design of 30 seeds." Carry it
into Section 7 in place of the H3a-only paragraph.

**M7. DAgger was not run (Sections 2.4, 3.10, contribution 4).**
"We use DAgger first" and "the first stage imitated the full-information marketplace by dataset aggregation
[24]". `ATC_learned_eval.json` (`imitation.finding`, `best_epoch: -1`) and `.team/reports.md` line 6431 say
"DAgger iterations 1-4 would add nothing, so they were not run". What ran is iteration 0: rollouts of the
hand-built bids labelled by the marketplace, with no model update kept and no aggregation. "Trained by
imitation and by search" (contribution 4) is therefore search only.
Fix: "We labelled 37,941 rounds of the hand-built auction with the marketplace's choice (the first iteration
of dataset aggregation [24]). No correction improved held-out agreement over the hand-built bids, so the
aggregation loop was not run and imitation left both models at zero correction. All of the learned policies'
behaviour comes from the search stage."

**M8. Table 6, the guard runs and the imitation statistics come from the engine before the fixes
(Sections 5.6, 5.11, 4.6).**
Section 4.6: "every number in this paper is from the rerun rows". `results/ATC_learned_eval.json` is dated
27 October 20:16 and has one commit (c90676f, 27 October), before change 4 (the hash-order fix, 28 October)
and change 5 (the fixed-point dispatcher). It is the source of Table 6 (two and five owners, loss 0.25 and
0.40, 10 % load, year 2038), of "tonne-days ... -15 %" and "tonnes delivered did not change" (the guard
runs), and of 92.9 %, 318 of 318 and 404 of 404. `PREREG.md` change 4 says of this file "statistically valid
but not bit-exact".
Fix: rerun the six out-of-range cells and the guard runs on the current engine (60 + 40 run-years), or add
to the caption of Table 6 and to the guard sentence "from the engine before changes 4 and 5", and correct
the sentence in 4.6 to "every number from E40, E41 and E42".

**M9. E54 and H14: the first clause depends on the baseline's retry cap, and the replay puts a vehicle in two
places (abstract, Sections 4.8, 5.9, 6.1, 8, Table 12).**
(a) Drop-and-retry gives up after 5 tries 180 s apart, 12 minutes into a 60-minute lease, while
store-and-forward repeats every 10 s for the whole lease (`lunarsim/atc/dtn.py` DEFAULTS: `max_tries: 5`
"Assumed", `retry_s: 180`, `custody_timer_s: 10`). Paths are one hop (mean 1.01 to 1.03), so custody at
relays plays almost no part. Five independent losses in a row have probability p^5, and 6,028 x 0.25^5 = 5.9
of the 10 lost awards at loss 0.25; at 0.40 the same count is 62 of the 85 lost; at 0.10 it is 0.06 of 4.
The remaining four or so are vehicles with no path, of which store-and-forward itself loses 2. The result is
mostly "five tries in twelve minutes against 360 tries in an hour". Neither parameter was swept.
(b) The lost-link rule is applied by editing the contact plan: after 600 s plus the drive back,
`lost_link_plan` gives the vehicle a direct link to the base until its recorded isolation ends, while the
awards, grants and end-of-job reports stay at the recorded times of a vehicle that drove on. The vehicle is
at its last link point for the radio and on its job for the logistics. The 45 s age, the 33 s report delay
and the zero lost jobs all come from that. The cost side is not counted: 82 returns a seed against 199 jobs,
and vehicles have no path to the base for 43 % of driving time (`E54_dtn.json`,
`link_shares.linked_share_driving_time` = 0.566). The ladder of Section 3.13, read literally (stop at the
next safe point when the link is lost, hold 600 s, retrace), would interrupt every drive through those
stretches. The paper says the engine "does not see the detour"; it does not say the vehicle's own job is the
thing left out.
(c) The 14-day Earth blackout cannot affect the first clause: `earth_up` gates only messages addressed to
Earth, and awards, grants, reports and status go between base and vehicle.
(d) The second clause is `0 if proto == "sf_ll"` in `run_e54.py`. The paper says so.
Fix: abstract and conclusion: "In a message-level replay of one month, drop-and-retry capped at five tries
lost 10 of 6,028 awards at 25 % loss; store-and-forward that retries for the whole lease lost 2, and none
when unheard vehicles were assumed to return to their last link point." In 5.9 and Table 12: "H14's first
clause holds against this baseline; its second clause is a property of the rule and is not a test." Add the
p^5 arithmetic. State in 4.8 that the blackout bears only on the ledger, and that the replay counts the
rule's gain in contact and not its cost in interrupted jobs. A control run with drop-and-retry at a 10 s
period and no cap would settle (a) in a few minutes of computing.

**M10. H13 and "bytes on the air" (abstract, Sections 1, 3.12, 5.8, 8, Tables 9, 12, A2).**
(a) The outcome was known before the registration. Research note 03, which `PREREG6.md` section 2 names as
its parameter source, already has "41 + 4.3 + 3.8 = 49 B/s per robot ... or 7.9 kbit/s for 20 robots" and a
table with 65.6 kbit/s at 10 Hz; the note was committed 35 minutes after the registration (02e9674, 10:50,
against b1e2266, 10:14, both 11 November). E53 reproduces that arithmetic with the codec's sizes.
(b) The first clause cannot fail in any geometry. Reports are not relayed, so no node can hear more than the
fleet's sum, 20 x 0.3928 = 7.857 kbit/s, which is the reported 95th percentile to four digits. "Each clause
held in every one of the 30 draws" carries no information for the first clause.
(c) "41 B on the air" is the Space Packet with its security fields (6 + 8 + 13 + 6 + 8). The paper's own
Table A1 puts Proximity-1 or USLP frames underneath, and note 03 says "Add 12 bytes per message inside a
Proximity-1 frame (3-byte sync marker, 5-byte header, 4-byte CRC) ... or 48 bytes inside a BPv7 bundle".
Neither is counted, nor is channel coding. With Proximity-1 framing a rover offers 63.5 B/s; 20 rovers
offer 10.2 kbit/s and need 12.7 kbit/s scheduled. It still fits, and the limit drops from 32 rovers to 25.
(d) "The full message set fits" (Table 12) and "15 message types fit a 16 kbit/s channel" (Section 8): the
traffic model of `run_e53.py` holds 11 message types (`per_rover_at_1hz`); TASK_ANNOUNCE, CAP_QUERY,
CAP_MANIFEST and MAP_NOTICE are not in it. The paper's own Section 5.8 shows it does not fit on random
access (21.4 kbit/s) or with one relay hop (19.6). P3's abstract states this limit; P1's does not.
Fix: rename the column "packet size (B), before link framing and coding" and drop "on the air" everywhere.
In 5.8: "H13's first clause is arithmetic on the sizes and rates and holds in any geometry; the design note
had computed 7.9 and 65.6 kbit/s before E53 ran. E53 confirms it with the codec's sizes and adds the mesh."
Conclusion: "the periodic reports and task and road messages of 20 rovers offer 7.9 kbit/s at one position
report a second, which fits a 16 kbit/s channel only if the base schedules it and reports travel one hop."
Table 12: "Counted" in place of "Tested ... Supported".

**M11. "5,480 pre-registered simulated years" (abstract, Table 4, Table 5).**
`E40_runs.csv` has 2,750 rows and 2,029 distinct runs: 721 rows repeat another row of the same cell exactly
(same seed, identical outcomes). The Earth-independent regimes account for 650 (13 cells x 50), which the
paper discloses in 4.6 and then counts in the abstract and in Table 4. The other 71 are A_MOON (39 distinct
of 80 at 10 % load, 61 at 30 %, 71 at 60 %) and A_EARTH plan_ahead at 10 % (78), which Table 5 lists with 80
runs and no dagger. The paper withdrew an earlier claim because repeats had been counted as independent
runs. "Pre-registered" is also too wide: `PREREG.md` registers hypotheses and rules, not the cell lists of
E41 and E42.
E41 and E42 add further deliberate repeats of the E40 auction cell (E41's default and 10 km cells, E42's
team-share 0.10 cell), so 4,759 is an upper count of distinct runs.
Fix: "at most 4,759 distinct simulated years (5,480 rows, of which at least 721 repeat a run exactly)". Mark
A_MOON in Table 5 with its distinct count.

**M12. Results that are properties of the design are reported as findings.**
(a) "From 12 % to 93 %" (abstract, 5.7): the 12 % is an input. `p5_team_items_same_owner_liftable` is 1.53
of 12.37 team items (12.4 %) at team share 0.10 and 3.17 of 28.43 (11.1 %) at 0.25; the same-owner auction
delivers 1.50 and 2.97. The share a single owner can lift is fixed by the assumed mass range and the one
same-owner pair of 2,080 kg.
(b) H6's second part (5.7): in `_team_hook` (`lunarsim/atc/auction.py`) the commit variant fails a meeting
only when the proposal and the answer arrive and the commit is lost; the variant without commit fails when
the single proposal is lost. With per-message success s these are s^2(1 - s) and (1 - s). "Failed meetings
rise without a commit step" is that inequality. No message is ever sent twice in either variant.
(c) "The timeout sets the waiting without buying fewer failures" (5.7): meeting wait equals failed meetings
times the timeout in every row of Table 8 (12.93 x 0.5 = 6.47; 13.83 x 2 = 27.67). A partner that missed the
commit never comes, so no timeout could reduce failures in this model.
(d) "The exploratory variant ... had no failed meetings": the base retries each vehicle `timeout/0.05 h` = 20
times; the commit variant retries nothing. The comparison is of retry budgets.
(e) The auction under loss (3.7, 5.4, 6.1): `_Selector.__call__` starts with `winners = [best]`. The best
bid in a component wins whatever is lost; loss can add parallel winners and wasted trips and nothing else,
and the component that holds the mast knows every waiting item from the base computer. The engine does not
execute an auction message by message. The closeness of the auction to the marketplace is partly built in.
(f) H1 (see M3 d).
Fix: one sentence each. For (a): "Of the team items, 12 % are within the one same-owner pair's capacity by
construction; cross-owner pairs delivered 93 %." For (b) to (d): "In this model a lost message is never
repeated inside a handshake, so ... follows from the message count and is not an independent measurement."
For (e), in Section 7: "The auction is modelled at the level of rounds: the best bid always wins, and a lost
bid costs a parallel winner or a wasted trip, never a worse assignment. A message-level implementation could
do worse." Table 12 needs a fifth status, "follows from the model", for these rows.

**M13. Two closing claims have no support in the paper (abstract, Section 6.3).**
(a) "Dispatch on the Moon then beats a relay to Earth" (abstract). The relay that is always up is identical
to the marketplace run for run, and the auction's difference from it is -0.84 h, 90 % interval -2.6 to 0.7.
Only the 80 % relay is beaten, and by a comparison the paper never reports: auction minus relay 0.8, paired
on the 30 seeds of block one, -3.75 h [-5.69, -2.00] (my computation from `E40_runs.csv`; not registered).
(b) "The robots' auction keeps working at the oxygen plant, which no relay reaches" (6.3; the introduction
has "the relay does not reach the oxygen plant either"). Section 3.9 says a robot finishing at the oxygen
plant "can end up where no other robot and no mast hears it" and must drive to a rally point; and the relay
is modelled as link time at the base with a coverage share, with no geometry at all.
Fix: (a) "dispatch on the Moon then did better than an 80 % relay (3.8 h, 2.0 to 5.7, an unregistered
comparison) and was not distinguishable from a relay that is always up", and report the comparison in 5.4.
(b) Delete both clauses.

### SHOULD FIX

**S1. Changes to both confirmatory families are not marked as changes (Sections 4.1, 4.5, 4.8, 5.9).**
`PREREG.md`: Holm across {H1, H2, H3a, H4, H6}. Paper: {H1, H2, H4 linear, H4 network, H6}, with H3a "tested
separately". `PREREG6.md`: {H9, H10, H13, H14, H15a}. Paper: Holm over three. The sign test for H14 is not
registered (P3 says it "was added for that purpose"; P1 does not). Its p = 0.002 is one-sided (0.5^9 =
0.00195); every other p in the paper is two-sided. Two-sided it is 0.0039 and Holm gives 0.008. H10's
adjusted p of 0.93 is quoted as final while `phase6_family.json` says "pending: E50 at 8x ... will be added".
None of this changes a verdict.
Fix: list the four deviations in 4.6 as changes made after results; print "one-sided" beside 0.002 or use
0.004 and 0.008; mark H10 "provisional".

**S2. H2 (Sections 1, 5.3, Table 12).**
"Passed the pre-registered test" should read "the test as revised in change 2, after a five-seed development
run of the same cells". As first registered (at least half the gap between owners alone and the marketplace,
621 h) H2 fails at 89.9 h; 5.3 says "we report it as registered but do not test it", which hides that. The
pooled interval treats 80 pairs as independent although nine start years carry most of the variance (the
paper's own pairing check gives 0.99) and seeds 1 to 10 appear six times each. Resampling whole start years
gives [77.4, 102.3] in place of [81.8, 98.7]; resampling seeds gives [82.5, 98.1]. The sentence "the pooled
interval includes the variation between years" is not true of a bootstrap over pairs. The per-year tests
rest on 7 to 10 runs each.
Fix: the wording above, "the original yardstick would not have been met", and the year-clustered interval.

**S3. H3a is confounded by the lost-link rule (Sections 5.4, 5.5, 6.1, 7).**
The on-Moon regimes send idle unheard robots back to a site the mast sees, 809 times a year; the marketplace
has no such move. Where the radio reaches every robot the rallies fall to 11 a year and the auction's wait is
15.25 h, 0.31 h above the marketplace and 1.15 h [-0.17, 2.67] above its own default cell
(`E41_runs.lead.csv`, "C_AUCTION range perfect"). The negative point estimate against the marketplace is
therefore more likely repositioning than decentralised decision quality. Section 7 calls the rule a cost
"part of every on-Moon result"; the data point the other way.
Fix: say so in 5.4, and run the marketplace with the same return-to-coverage move as a control (30 runs).

**S4. Proposition 1 is presented as a guarantee for the auction (contribution 6, Sections 2.1, 3.11, Table 12).**
See the verdict table. Fix: in Table 12 and the contribution list, "a bound on one greedy round in value
below a ceiling; it gives no bound on cost or waiting, where a greedy round can be arbitrarily worse than the
optimum", and say that the 200 instances use a toy score. Add the reference for Fisher, Nemhauser and Wolsey
or delete the sentence; it is named in the text and absent from the list.

**S5. Proposition 4's worked example disagrees with the protocol (Appendix B, Section 3.13).**
(a) Heartbeat: 10 s here; Table A2 and E53 send HELLO at 1 Hz whenever nothing else was sent. At 1 Hz and
k = 5 detection takes 4.5 s and false marks are ten times as frequent (0.78 a day per watcher at loss 0.10,
so k = 5, 8 and 12 are needed for fewer than one a day at loss 0.10, 0.25, 0.40). (b) The example re-auctions
45 s after the last heartbeat. Section 3.13 marks a vehicle failed only "after a second, longer timeout or a
sighting", returns a silent vehicle's job "when the lease ends", and E54 uses a 1 h lease. With the lease
the hand-over is about 1 h 54 min and the ratio to Earth's 53.8 h is 28, not 60. (c) "A pair of live rovers
raises 0.08 false marks a day" is one rover watching one other. (d) The sentence about "the design note
behind this section" and (k + 1/2) cannot be followed without that note.
Fix: one heartbeat period throughout; add the second timeout to the example ("54 min" in 3.13 becomes about
1.9 h); delete (d).

**S6. Propositions 5 and 6 (Appendix B, Section 3.13, abstract of contributions).**
Proposition 6: "cannot be shorter than 13 B" holds only for ranges that were set by the bit widths (+-83.9
km in 0.01 m steps is 2^24 values by definition; likewise h, speed and sigma_h). Only heading and nav_src
have a count that is not a power of two. A 1 cm position step sits beside a 5 cm step for its own
uncertainty and navigation errors of metres (P3). Proposition 5's inputs were picked to land near published
ratios.
Fix: call both "remarks" or "counts"; say "five propositions and two counts" or similar; in 3.13 replace
"each with a number" by "the third is a model with assumed inputs".

**S7. E54's grants are not the recorded reservations (Sections 4.8, 5.9, Table 11).**
`messages()` in `run_e54.py` creates one RESERVE_GRANT per vehicle per job at the job's commit: 6,028
grants, the same count as the awards. The recorded single-lane reservations number 2,628. "The messages are
those of the recorded run" and "each lost grant is a vehicle that stops before a single-lane segment" do not
hold: more than half the grants belong to jobs with no single-lane reservation. Grants lost by
drop-and-retry at "about the per-hop loss rate itself" is one try on one hop, by the 60 s lifetime and the
180 s retry period; the paper says this, and it should be labelled as a consequence of those two settings.
The ledger's 930 bundles are 31 bundles replayed for 30 seeds on which they do not depend.
Fix: "a grant was generated for every award"; delete the stopping sentence or count the 2,628; give the
ledger as 31 bundles.

**S8. Size and makeup of the primary outcome are not stated (Sections 4.4, 5.1).**
A run has about 53 urgent items at 30 % load (21 to 102), about 15 at 10 % (as few as 0; one A_EARTH strict
run has none, so that cell's mean is over 79 runs, not the 80 printed) and about 122 at 60 %
(`atc_urgent_items`). Nowhere does the paper define "urgent" or give these counts. The light-load results
(H4's second part, the 7.9 h spread) rest on means of 15 items.
Fix: define urgent cargo in 3.1 and add the item counts to 4.4 and to Table 5.

**S9. "Implemented" and "measured" (abstract, Section 1, contribution 5, 3.12).**
What exists: a schema, a bit-packed and a CBOR codec with AES-CMAC and Ed25519 (`lunarsim/atc/lrip`, 645
lines), a manifest matcher, 45 vectors, nine fast tests that pass. What does not: any exchange of LRIP
messages between simulated vehicles, the request and response timeouts, heartbeat and epoch handling, the
ladder's first steps. The capability-filter check reproduces (my rerun: 128 of 128 values identical, 364
items; 5 items with no manifests) and is a no-op by design, as the paper says; "it matters when a vehicle
joins whose class the dispatcher has never seen" is untested.
Fix: "we wrote the layer down, implemented its encoding and counted its bytes"; "byte counts" for
"measured"; "it is meant for a vehicle whose class the dispatcher has never seen; that case was not run".

**S10. Related work and references.**
(a) Cited as support but not opened, by the paper's own `NOTES.md`: [32] (paywalled; cited for CADRE's
design in 2.6 and Table 1); [18] abstract only, yet described as "its robots are cooperative and its links
perfect" and given a full row of dashes in Table 1; [33] abstract only, likewise in Table 1; [13], [14],
[15] abstract or snippet, cited for hardness results; [22], [23] abstract. [24], [29], [46], [47], [51] are
flagged "title to confirm". An absence cannot be read from an abstract.
(b) Table 1 gives CADRE a dash for message loss. The paper itself says CADRE's design choice was made "to
keep messages few on lossy surface links", and note 04 records packet loss from motor interference in
CADRE's tests. Mark it "in hardware tests".
(c) Section 6.2 sets "our leader regime" beside CADRE and concludes that "the two on-Moon designs did not
differ". The leader regime is the marketplace on a base computer with a 0.5 h election; it is not CADRE's
planner. Reword so that the two designs compared are named as ours.
(d) Named and uncited: Fisher, Nemhauser and Wolsey 1978; Sargent's techniques; the Two Generals problem;
the Gilbert-Elliott channel; the cross-entropy method; the Hungarian method; the contract-net protocol
(Smith 1980 is the primary source, not the FIPA specification); slotted ALOHA; CFDP (Table A2).
(e) Prior art the notes themselves say must be read before a novelty claim on multi-owner fleets: Grogan and
de Weck 2012 (`multi_owner_allocation.md`, section 8). Not cited. Also listed there and not cited: Rantanen
et al. 2018 on CBBA in a lossy network, Schnell et al. 2023.
(f) Missing fields: no or partial initials in [18], [19], [20], [33], [34], [50], [69], [71], [72], [73],
[75], [76], [77], [81];
"et al." in [3], [9], [17], [23], [31], [32], [35], [36], [48], [80]; no year in [63], [65], [66], [68], [70]; no
access date for web items [49], [64] to [67], [78], [79]; no identifier or URL for the author's preprints
[40] to [42]; [43] reads "cite by repository tag when tagged" and "changes 1-5 apply to this paper" while
Section 5.11 relies on change 10. "About 48 B of overhead per bundle [60]" is the authors' computation, not
a figure in RFC 9171.
(g) [78] and [79] are a trade-body news item and a web digest. They carry Table B2's anchors. The entries
say so; a journal will still ask for the primary sources.

**S11. Bundle depth and loss are not separated (Section 5.5).**
There is no cell with depth 2 or 5 at loss 0. Stale claims are the same at loss 0.25 and 0.40 (84.6 and
85.7 at depth 2; 312.6 and 313.9 at depth 5), which suggests the penalty comes from bundling on this demand
and not from loss. H3b as registered is supported; the comparison with Lott and Honary's finding (best depth
falls under loss) cannot be made. "Claims are hidden from robots in the same part of the network" (3.7)
reads as an error for a reader without the code.
Fix: add the two loss-free cells (60 runs) or say the design cannot attribute the penalty to loss.

**S12. The linear policy is neither explained nor benchmarked against a tuned rule (Sections 5.6, 6.2, 6.3).**
The weights disfavour older items (age, -1.10) and robots with more charge (-1.39) and favour longer jobs
(+1.93). The policy fails the monotonicity check in 67 % of probes (5.11). The search stopped while still
improving (`selected_generation: 5` of 6) after 60 candidates on four seeds. "The linear weights say what
the hand-built bid misses" and "13 weights an operator can read" are not supported by an analysis of the
weights. The paper concedes the baseline was never tuned.
Fix: an ablation (zero each weight in turn on the 30 seeds), and the same search applied to the hand-built
rule's own parameters; or soften both sentences to "13 weights, which we have not interpreted".

**S13. Consistency with P2 and P3.**
(a) Same claim, different numbers: scheduled channel for 20 rovers 9.82 kbit/s in P1 (h = 1), 10.06 in P3
(h = 1.024); random access 21.4 against 21.87. P3's abstract adds "only on a base-scheduled, one-hop
channel"; P1's has no such limit. (b) "H10" means sizing in P1 Section 4.1 and the margin hypothesis in 4.8
and 5.9; P2 writes the latter H10'. Use H9' and H10' in P1. (c) H15a: "adjusted p = 0.003" in P1, "at most
0.003" in P2 and P3; the file gives an upper bound. (d) P2 says H14 was "supported in full"; P1 says one
clause is by construction. (e) E53, E54, H13 and H14 are reported as results in P1 and P3, and E54 and H14
in P2 as well. A journal will treat that as redundant publication; one paper should report, the others cite.
(f) P1 quotes 128 summary values (45 days, seed 3, a test); P2 and P3 quote 144 (30 days, seed 2,
`vv_phase6.json` row G1). Different checks; say which.

**S14. Limitations that are missing or understated (Sections 6.4, 7).**
The ownership split and the equal thirds of cargo (M3). One year from an empty base, so every regime is in a
start-up transient and censoring sets the size of H1. The auction model (M12 e). The reference lacks the
rally move (S3). The engine has no channel capacity: messages are counted and never queue or collide, so
E53's limit never feeds back into E40 to E42. The base computer holds every manifest and is the default
leader; "among the robots" overstates how distributed the on-Moon regimes are. No vehicle fails. The baseline
transport's parameters (M9). E53's fleet geometry draws 5 to 80 rovers from the trajectories of eight
vehicles, which mostly sit near the base, so "the busiest link hears the whole fleet" is a feature of that
sampling. The 0.5 h election was not rerun at 10 s although the paper says the value "is slow".
Experiments a reviewer will ask for: the three controls named in M9, S3 and S11; an ownership split in which
every owner can lift its own cargo; the leader regime at a 10 s election; one rover failure; a second site
or at least a second mast position chosen before looking.

**S15. The AI-use statement is not accurate (Use of AI tools; Section 3.11; 4.7).**
"Every number in the paper is written by the build script from the results files ... no number was typed."
`paper/p1/dev_notes.json` describes itself as "numbers quoted in P1 that no results file holds", with three
entries marked "to update at submission": 547 tests (656 are collected today; I did not run them all), 20
rerun rows, 360 MB. It also holds 58 t and 1,487 t (a development run), the capability-filter counts and the
inputs of Propositions 4 and 5.
Fix: update the three entries, and write "from the results files and a short file of development-run values
listed in the repository". Check the statement against the target journal's current policy on generative
tools; as written it attributes drafting and the running of experiments to the tools.

**S16. Presentation.**
(a) Two sections are called Limitations (6.4 and 7). Fold 6.4 into one sentence that points to 7.
(b) Section 5.11 contains a 500-word run of internal check identifiers ("X2 not possible ... FRONTEND's
tests", "the ten-minute rule", "the owner's call", "LEAD"). Move it to a supplementary table and keep the
six failures.
(c) Not understandable without the repository: "the owner of the study" (4.6, in a paper about owners);
"block v1" (Table 7); "3eq"; "today's fleet"; "guard runs"; "the design note" (3.12, Appendix B); "lease"
and "ledger" before they are introduced (4.8); "apron"; "epoch"; "CFDP"; TASK_BID "encrypted" (Table A2,
with no encryption described anywhere); "bundle" for both a set of jobs and a DTN unit; the manifest key
`t_hold_s: 30` beside a hold of 600 s in the text.
(d) Tables 5 and 8 print internal labels ("C_AUCTION team 25 any loss 0.4 arbitrated (exploratory)").
Table 7 repeats "H1:" in two columns and mixes hours and percentage points.
(e) One figure in the paper. A site map with the mast's coverage and a plot of the main comparison are the
least a reader needs.
(f) Small errors: "(Section 3.5)" at the end of the L5 sentence in 5.11 should be 3.10. "2.6 h (1.7 to 3.4
h)" for the relay is the 90 % interval, printed beside 95 % intervals without its level (95 %: 1.5 to 3.6).
"104.9 h against 15.0 h" (5.3) beside 14.9 h in Table 5, and "from 81 %" beside 82 %: the first of each
pair is the mean over 80 rows that repeat seeds 1 to 10 six times. "13.8 KB/s" beside kbit/s elsewhere. The
PDF in `paper/p1` is seven minutes older than `paper.html`.
(g) The model is described by difference from three unpublished preprints of the author ("everything ...
not described here is unchanged"). The bid rule, the urgency weight, the cargo classes and the demand
process must be stated in this paper, in a paragraph or an appendix.

### OPTIONAL

**O1.** Report the direct paired comparisons a reader looks for: auction against relay 0.8 (-3.75 h,
[-5.69, -2.00]) and against plan-ahead (-8.15 h, [-11.8, -5.0]), both n = 30, block one, unregistered.

**O2.** Percentile bootstrap with 7 to 10 runs (the per-year tests of H2) undercovers. The effects are large
enough that it does not matter here; a t interval or BCa would remove the question.

**O3.** The slope comparison with Lott and Honary in 5.5 sets per cent of cargo wait beside per cent of
makespan. Say they are different quantities or drop the comparison.

**O4.** Proposition 5: (AT + IT)/IT equals AT/IT + 1 exactly, so "close to their fan-out when requests are
rare" can be an equality with the offset stated. I did not open [77] to see which form it uses.

**O5.** The pairing check quoted in 4.5 (variance factors 0.00 to 0.99) was made at 10 % load on mean delay
per delivery, over 80 rows that include the repeats. Say so, or redo it on the primary outcome at 30 %.

**O6.** "Three companies": owner C is invented and is given "MAPP class" rovers, a product of the company
that is owner B. A sentence in 3.2 would prevent the question.

**O7.** The broadband vectors use the 8 B code although Table A1 gives 16 B for broadband.

**O8.** The closing line ("What it needs most is permission") is a slogan resting on M3. A journal reviewer
will ask for it to go.

## 5. Checked numbers

Verdict "match" means the paper's value equals mine from the named file within rounding or bootstrap noise.

| # | Claim | Paper | File value | Source | Verdict |
|---|---|---|---|---|---|
| 1 | Decision regimes | 13 | 13 (15 labels less two refuelling variants) | `E40_runs.csv`, `label` | match |
| 2 | Simulated years | 5,480 | 5,480 rows; E40 holds 2,029 distinct runs in 2,750 rows | E40, E41, E42 run files | match on rows; at least 721 repeats (M11) |
| 3 | Strict Earth dispatcher minus marketplace | 89.9 h | 89.85 | E40, B_EARTH strict - O_ORACLE, n = 80 | match |
| 4 | Plan ahead leaves | 7.3 h | 7.26 | E40, B_EARTH plan_ahead - O_ORACLE | match |
| 5 | Auction against marketplace | within 0.8 h | -0.84 | E40, C_AUCTION - O_ORACLE, block one, n = 30 | match |
| 6 | Linear bids cut the wait | 16.5 % | 2.32 / 14.09 = 16.5 % | E40, C_LEARNED_LIN - C_AUCTION | match |
| 7 | Team items delivered | 12 % to 93 % | 11.6 % to 93.4 % | E42, team 10, loss 0.1 | match (12 % is an input, M12) |
| 8 | Share of the gap never delivered | 99.5 % | 1 - 5.77/1232.4 = 99.53 % from the full-coverage pair; 92.0 % from the strict-fallback figures of the same sentence | `table_E40_pairs.csv` rows 81, 116 | MISMATCH (M3) |
| 9 | Message types | 15 | 15 | `E53_bitrate.json`, `sizes` | match |
| 10 | Authenticated position report | 41 B | 41 | `sizes.POSITION.mac8`; golden packet | match |
| 11 | 20 rovers at 1 Hz | 7.9 kbit/s | 7.857 | `E53_bitrate.json`, `h13` | match |
| 12 | Budget | 16 kbit/s | 16.0 | `channels_kbps` | match |
| 13 | 20 rovers at 10 Hz | 66.9 kbit/s | 66.897 | `h13` | match |
| 14 | Drop-and-retry lost jobs | 0.33 a seed | 10 / 30 = 0.333 | `E54_dtn.json`, `h14` | match |
| 15 | Store-and-forward with rule lost | none | 0 | `E54_table.csv` | match |
| 16 | Propositions | six | six | paper | match |
| 17 | Strict against uninterrupted | 7.0 times | 104.89 / 15.03 = 6.98 | E40 | match |
| 18 | Start years below 60 % visibility | six | 2029, 2031, 2032, 2038, 2041, 2044 (0.547 to 0.599) | `E40_fit.json`, `visibility` | match |
| 19 | Auction difference in per cent | -5.6 % | -0.838 / 14.932 = -5.61 % | E40 | match |
| 20 | Its 90 % interval | -17 % to +5 % | -17.4 % to +4.9 % | E40 | match |
| 21 | Split of the gap | 68 % / 32 % | 844.4 and 388.9 of 1,233.3: 68.5 % / 31.5 % | E42 and E40 | match |
| 22 | Base's age of information | 88 min / 45 s | 5,287 s / 45.49 s | `E54_table.csv`, `aoi_mean_s` | match |
| 23 | Light-load gain interval | -0.1 to 2.2 h | -0.15 to 2.23 | E40, 10 % | match |
| 24 | Mesh points | 2,421 | 2,421 | `ATC_mesh.json` | match |
| 25 | Line of sight at 2 to 5 km | 9.31 % | 0.0931 | `ATC_mesh.json` | match |
| 26 | Hops to the mast at 5 km | at most 4 | 4 | `connectivity` | match |
| 27 | Points cut off for small robots | four | 4 | `isolated` | match |
| 28 | Visibility range | 54.7 to 62.6 % | 0.5467 to 0.6258 | `E40_fit.json` | match |
| 29 | Auction against Hungarian, worst ratio | 1.255 | 1.2549 | `ATC_auction_bounds.json` | match |
| 30 | CBBA-like lowest share | 85.1 %, 85.3 % | 0.8513, 0.8531 | same | match |
| 31 | Phase-5 checks for P1 | 121 (100 + 21) | 121 (100 V, 21 Val) | `vv_phase5.json` | match |
| 32 | Checks by technique | 33, 16, 16, 16, 15, 13, 7, 4, 1 | same | `vv_phase5.json` | match |
| 33 | Network parameters | 1,537 | 13x32+32 + 32x32+32 + 32+1 = 1,537 | policy file | match |
| 34 | Imitation rounds and rows | 37,941; 624,640 | same | `ATC_learned_eval.json` | match |
| 35 | Search sizes | 6 x 10; 5 x 12 on 32 weights | same | `policies.*.cem` | match |
| 36 | Overhead | 28 B; 84 B signed | 41 - 13; 92 - 8 | `sizes` | match |
| 37 | Award, grant, signed alert | 92, 94, 98 B | 92, 94, 98 | `sizes` | match |
| 38 | Manifest sizes | 1,200 / 1,210; 283 / 280; 367; 247 / 251 | same | `manifest_bytes`, `CAP_MANIFEST` | match |
| 39 | Golden packets | 45 (12 + 3, 15, 15) | 45 (N mac8 12, N signed 3, N none 15, B 15) | `conformance-v0.1.json` | match |
| 40 | Capability filter | 128 of 128; below 10 % without manifests | 128 of 128; 5 of 364 items (1.4 %) | my rerun of the test's three runs | match |
| 41 | Elections a year | 4.3; 2.2 h | 8,760 / 2,024 = 4.33; 2.16 h (E41 mean failures 4.23) | computed; E41 | match |
| 42 | Test suite | 547 tests | 656 collected | `pytest --collect-only tests` | MISMATCH (stale) |
| 43 | E40 runs and cells | 2,750; 40 | 2,750; 40 | E40 | match |
| 44 | E41 runs and cells | 1,560; 52 | 1,560; 52 | E41 | match |
| 45 | E42 runs and cells | 1,170; 39 | 1,170; 39 | E42 | match |
| 46 | Variance factors from pairing | 0.00 to 0.52; 0.90 to 0.99 | 0.000 to 0.520; 0.901 to 0.993 | `vv_phase5.json`, D10 | match (10 % load, another metric) |
| 47 | Regime pairs with equal demand | 880 | 880 | D10 | match |
| 48 | H3a half-width against 10 % of the mean | 1.64 h; 1.49 h | 1.64 to 1.67; 1.493 | E40 | match |
| 49 | Archived rows | 4,052 | 2,750 + 1,170 + 132 | `results/archive` | match |
| 50 | E40, primary outcome moved by | -0.01; 1.3; at most 105 h | -0.27; 2.41; 153 h (the quoted values are `delay_mean_h`) | archive against current rows | MISMATCH (M2) |
| 51 | E42, the same | -0.02; 0.3; at most 6 h | +0.21; 6.9; 256 h | same | MISMATCH (M2) |
| 52 | E41, the same | +0.04; 0.3; at most 3 h | -0.10; 1.55; 18 h | same | MISMATCH (M2) |
| 53 | Longest run | 71 s | 71.0 | `E40_fixpoint_before_after.json` | match |
| 54 | Training time | 1.8 h | (3,433 + 3,182) s = 1.84 h | `policies.*.cem.wall_s` | match |
| 55 | Jobs and reservations a seed | 199; 88 | 199.3; 87.6 | `E54_dtn.json` | match |
| 56 | Owners alone at 30 % | 1,217 to 1,257 h | 1,217.1 to 1,256.6 | E40 | match |
| 57 | Earth-losing pooled regimes | 17.6 to 104.9 h | 17.59 to 104.89 | E40 | match |
| 58 | Bottom group | 11.8 to 14.9 h | 11.77 to 14.93 | E40, block one | match |
| 59 | Tonnes delivered | 1,454 to 1,471; 943 to 956 | 1,454.4 to 1,471.5; 943.3 to 955.7 | E40 | match |
| 60 | Cargo rovers and fleet busy | 30 %; 7.6 % | 0.295; 0.076 | E40, O_ORACLE | match |
| 61 | Light-load spread; strict | 7.9 h; 75.3 h | 18.77 - 10.87 = 7.90; 75.33 | E40 | match |
| 62 | Table 5, marketplace at 30 % | 14.9; 66; 82 %; 1,469 | 14.93; 66.0; 0.817; 1,469.4 | E40 | match |
| 63 | Table 5, linear at 60 % | 45.2; 212; 73 % | 45.22; 212.3; 0.728 | E40 | match |
| 64 | Table 5, strict at 60 % | 483.9; 1,500; 22 %; 2,180; 1,083 | 483.86; 1,500.1; 0.222; 2,179.6; 1,083.1 | E40 | match |
| 65 | Table 5, A_EARTH strict at 10 %, runs | 80 | 79 with a value (one run has no urgent item) | E40 | MISMATCH (minor) |
| 66 | H1 at 30 % | 1,232 h [1,076, 1,401] | 1,232.4 [1,075, 1,400] | E40 | match |
| 67 | H1 at 60 % | 1,077 h [984, 1,175] | 1,077.3 [985, 1,174] | E40 | match |
| 68 | Backlog of owners alone | 513 t | 512.7 | E40 | match |
| 69 | Delivered-only gap, strict | 100 h | 114.86 - 15.03 = 99.8 | E40, `atc_urgent_wait_mean_h` | match |
| 70 | Two parts of the gap | 844 [732, 955]; 389 [301, 483] | 844.4 [734, 956]; 388.9 [299, 483] | E42 and E40 | match |
| 71 | Gain by owner | 404; 631; 2,575 h | 404.3; 630.9; 2,574.8 | E40, `own_*_urgent_wait_cens_h` | match |
| 72 | H2 interval | 81.8 to 98.7 | 81.6 to 98.5 | E40 | match |
| 73 | Means behind H2 | 104.9 against 15.0 | 104.89; 15.03 (80 rows; 14.93 on the 30 distinct runs) | E40 | match |
| 74 | Year means of the difference | 74 to 113 h | 74.0 (2029) to 113.0 (2031) | E40 | match |
| 75 | Backlog at the end of a blackout | 47.8; 2.3 t | 47.76; 2.25 | E40 | match |
| 76 | Within a day | 81 % to 39 % | 0.807 to 0.389 | E40, 80 rows | match |
| 77 | Plan-ahead interval | 5.2 to 9.4 | 5.25 to 9.38 | E40 | match |
| 78 | Relay 0.8 | 2.6 h (1.7 to 3.4) | 2.55; 95 % 1.55 to 3.57; 90 % 1.70 to 3.40 | E40 | match to the 90 % interval; level not printed |
| 79 | Original yardstick | 621 h | 1,241.6 / 2 = 620.8 | `table_E40_pairs.csv` row 116 | match |
| 80 | Leader against marketplace | 0.26 h (-1.8 to 1.2) | -0.26 [-1.81, 1.18] | E40 | match |
| 81 | Loss-free waits | 14.6; 14.3; 13.8; 10.8 | 14.55; 14.30; 13.82; 10.76 | E41 | match |
| 82 | Linear below marketplace at loss 0 | 4.2 h (2.7 to 5.7) | 4.17 [2.71, 5.75] | E41 and E40 | match |
| 83 | Added by loss 0.40 | 1.0; 3.9; 3.7; 4.3 h | 1.05; 3.86; 3.73; 4.32 | E41 | match |
| 84 | Slopes per point of loss | 0.18; 0.67; 0.67; 1.00 % | 0.180; 0.675; 0.674; 1.005 | E41 | match |
| 85 | Bursty against steady, cut by | 1.4 (0.4 to 2.4); 1.2 (0.4 to 2.2) | 1.36 [0.42, 2.36]; 1.22 [0.34, 2.16] | E41 | match |
| 86 | Depth 5 and depth 2 | +6.0, +10.0; +3.7, +5.0 | 6.03, 10.04; 3.74, 5.03 | E41 | match |
| 87 | Stale claims | 314 a year | 313.9 | E41 | match |
| 88 | Range 2 km, 10 km, unlimited | -0.1; 0; +1.2 (-0.2 to 2.7) | -0.06; 0.00; 1.15 [-0.17, 2.67] | E41 | match |
| 89 | Rule off | +3,267.5 h; 5.1 % to 83.1 %; 809 | 3,267.5; 0.051 to 0.831; 808.7 | E41 | match |
| 90 | Second mast | +1.5 h (0.1 to 3.2); 5.0 % | 1.51 [0.05, 3.20]; 0.050 | E41 | match |
| 91 | Leader against auction | 2.6 h at loss 0.40; 871.6 h rule off | 2.56 [0.70, 4.52]; 871.6 | E41 | match |
| 92 | E41 default cell equals E40's | exactly | largest difference 0.0 over 30 seeds | E41, E40 | match |
| 93 | H4 linear, 30 % | 2.3 h [0.6, 3.9]; p 0.009; Holm 0.017 | 2.32 [0.64, 3.95]; 0.0087; 0.0174 | E40; `E40_fit.json` | match |
| 94 | H4 linear, 10 % | 0.9 h, 7.9 % | 0.94; 7.9 % | E40 | match |
| 95 | H4 linear, 60 % | 31.5 h [25.2, 38.2] | 31.46 [25.1, 38.0] | E40 | match |
| 96 | Network at 30, 10, 60 % | -0.25; -1.06; -1.3 h | -0.25 [-1.65, 1.09]; -1.06 [-2.96, 0.38]; -1.34 [-6.0, 3.0] | E40 | match |
| 97 | Largest weights | +1.93, +1.28, +1.04; -1.96, -1.41, -1.39 | 1.929, 1.283, 1.040; -1.956, -1.411, -1.388 | `atc_bid_linear_v1.json` | match |
| 98 | Tonne-days in the guard runs | -15 % | -1,055.6 / 6,837.4 = -15.4 % | `ATC_learned_eval.json` | match (engine before the fixes, M8) |
| 99 | Table 6, six rows | as printed | same | `ATC_learned_eval.json`, `ood` | match (engine before the fixes, M8) |
| 100 | Team items, paired | 82 points [78, 86]; 86 [83, 88] | 81.8 [77.7, 85.6]; 85.5 [82.9, 88.0] | E42 | match |
| 101 | "Share of all items" | +1.7; +5.4 points [3.5, 8.5] | mass share +1.7; +5.4 [3.5, 8.5]; items +80.7 of about 2,930 | E42, `delivered_share` | MISMATCH (mass, not items; M5) |
| 102 | Failed meetings | 4.0; 12.1; 25.2; without commit 15.2; 35.4 | 3.97; 12.10; 25.20; 15.23; 35.40 | E42 | match |
| 103 | Commit step cut failures by | 3.1 (0.6 to 5.8); 10.2 (4.5 to 16.0) | 3.13 [0.57, 5.67]; 10.2 [4.6, 15.9] | E42 | match |
| 104 | Its cost in wait | 1.8 h (0.1 to 3.6); 9.1 h (6.8 to 11.5) | 1.85 [0.07, 3.63]; 9.14 [6.75, 11.48] | E42 | match |
| 105 | Meeting wait by timeout | 6.5; 12.1; 27.7 h | 6.47; 12.10; 27.67 | E42 | match |
| 106 | Table 8, all 39 rows | as printed | same | E42 | match |
| 107 | Load per rover | 0.393 (49.1 B/s); 0.266; 3.34 kbit/s | 0.3928; 0.2656; 3.3448 | `E53_table.csv` | match |
| 108 | Mean over draws | 7.48 | 7.477 | E53 | match |
| 109 | Without authentication | 5.17; 44.0; +52 % | 5.168; 44.048; 1.520 | E53 | match |
| 110 | Channel needed | 9.82; 21.4; 19.6 kbit/s | 9.821; 21.358; 19.64 | E53, `h13`; computed | match |
| 111 | Hops and reach | 1.01 to 1.03; 97 to 99 % | 1.007 to 1.031; 0.968 to 0.987 | E53 | match |
| 112 | Full at; 40 rovers | 32 rovers; 15.7 and 19.6 | 32.6; 15.714 and 19.64 | E53; computed | match |
| 113 | 5 rovers at 10 Hz; 80 at 10 Hz | 16.7; 266 and 333 | 16.724; 266.08 and 332.6 | E53 | match |
| 114 | Table 9, all 36 cells | as printed | same | `E53_table.csv`, fleet rows | match |
| 115 | Table 10, all 30 cells | as printed | same | spread rows | match |
| 116 | Spread geometry shares | 42 to 49 %; 52 to 80 %; 4.54 | 41.5 to 48.7 %; 51.9 to 80.0 %; 4.538 | E53 | match |
| 117 | Awards lost by drop-and-retry | 10 of 6,028; 0.17 to 0.53 | same | `E54_table.csv`; `h14` | match |
| 118 | Unconfirmed releases | 2,566 of 2,628; 7,349 h; 245 h a seed | 2,566; 87.6 x 30 = 2,628; 7,349.2; 245.0 | E54 | match |
| 119 | Sign test | 9, 0, 21; p = 0.002 | 9, 0, 21; 0.5^9 = 0.00195 one-sided (0.0039 two-sided) | `phase6_family.json` | match; one-sided, not stated (S1) |
| 120 | Holm in the second family | 0.004; 0.003; 0.93 | 0.0039; at most 0.0030; 0.932 (8x pending) | `phase6_family.json` | match |
| 121 | Grants lost by drop-and-retry | 9.5; 25.6; 39.9 % | 9.46; 25.60; 39.86 % | E54 | match |
| 122 | Ages | 5,287 s; 31 h; 45 s; 149 s | 5,287.0; 111,296 s = 30.9 h; 45.49; 148.9 | E54 | match |
| 123 | Returns; isolation removed | 82; 336 vehicle-hours | 82.13; 335.6 | `E54_dtn.json` | match |
| 124 | End-of-job reports | 32 %; 1.4 %; 543 s; 33 s | 32.3 %; 1.36 %; 542.7; 33.0 | E54 | match |
| 125 | Ledger | 61 days; 24.8 days; 94 %; 35 %; none | 61; 24.81; 93.55 %; 35.48 %; 0 | `E54_ledger.json` | match |
| 126 | Table 11, nine rows | as printed | same | `E54_table.csv` | match |
| 127 | Hopper refuelling | -0.61 h (-2.1 to 0.4) | -0.61 [-2.13, 0.41] | E40 | match |
| 128 | Agreement with the marketplace | 92.9 %; 318 of 318; 404 of 404 | 0.92881; same | `ATC_learned_eval.json` | match |
| 129 | Phase-5 outcomes | 6 failed; 100 passed; 15 not run; 1 bias flag | same | `vv_phase5.json` | match |
| 130 | Monotonicity failures | 32 %; 67 % | 0.3186; 0.6667 | `vv_phase5.json`, L5 | match |
| 131 | Cargo-id fix | 48 runs; 670 to 0 | 48; 670; 0 | `id_fix_evidence.json` | match |
| 132 | Slotted access efficiency | 0.377; 0.368 | 0.3774; 0.3679 | computed | match |
| 133 | Table B1, 12 cells | as printed | same; simulation 1.893 against 1.900 | computed | match |
| 134 | Proposition 4, detection and false marks | 45 s, 50 s; 0.08, 53; k = 4, 7, 10 | 45, 50; 0.078, 53.1; 4, 7, 10 | computed | match |
| 135 | Hand-over; wait for Earth; ratio | 53.6 min; 53.8 h; 60 | 53.58; 53.78; 60.2 | computed | match |
| 136 | Table B2, 5 rows | as printed | same | computed | match |
| 137 | Proposition 6 | 97.4 bits; 98; 13 B; 41, 49, 27 B | 97.40; 98; 13; 41, 49, 27 | computed; `sizes` | match |

137 entries checked (several stand for whole tables); 7 mismatches (rows 8, 42, 50, 51, 52, 65, 101). Three
further entries match the file and need a label or a qualifier (rows 2, 78, 119).

## 6. What I could not check, and why

- The full test suite. 656 tests are collected; I ran the nine fast protocol tests (all pass) and the
  capability-filter runs, not the rest, for time.
- Anything quoted from the author's earlier preprints [40] to [42] (59 % visibility, windows of 16 days and
  gaps of 11, the oxygen plant at 1.2 km, the driving tables, the bid rule). They were not in scope and
  have no results file here.
- The cited sources themselves. I did not fetch them; I relied on the research notes' record of what was
  opened. S10 lists where that record says a source was not read.
- Development-run values that exist only in `dev_notes.json` and the team log: 20 rerun rows with no
  difference, 360 MB of memory, 58 t against 1,487 t without and with the lost-link rule.
- The trace-identity claims of Section 3.11 (pooled dispatcher with coverage 1.0, leader and auction with
  perfect links against the marketplace). The summaries agree in the E40 rows (relay 1.0 equals the
  marketplace run for run); I did not compare event traces.
- The load multipliers 0.857 and 6.220 (2.806 appears in the code and the tests) and the manifest sizes of
  257 and 259 B with registry numbers in place of names (computed inside the build).
- Figure 1 and the PDF. I read the HTML as text; the figure's data (year means and intervals) reproduce,
  its drawing was not inspected, and the PDF is older than the HTML.
- Whether [77] states fan-out as AT/IT or AT/IT + 1 (O4), and what the target journal's current rule on
  generative tools allows (S15).
- The live site and the public repository named under Data and code availability.
