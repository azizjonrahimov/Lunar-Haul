# Response to the referee report on P1 (revision of 12 November 2026)

Report: `reports/referee_phase6_p1.md`. Binding decisions: `reports/referee_phase6_decisions.md` (A, B). Files changed:
`paper/p1/build_p1.py`, `part1` to `part5`, `dev_notes.json`, `PLACEHOLDERS.md`, `NOTES.md`, and the rebuilt
`paper.html` and `values.json`. Every new number is computed by the build from the raw run rows, the archived rows
or a results file, with a check; the new keys are listed in `PLACEHOLDERS.md` ("Referee revision").

Counts: 25 fixed, 9 fixed in part, 2 awaiting a task (B-106, B-100), 1 not done. Build: passes, abstract 299 words,
conclusion 249, no `[[PENDING` in `paper.html`. The PDF was not rebuilt (free memory 0.78 GB, below the 1.0 GB limit).

## MUST FIX

| # | Status | What was done | Where |
|---|---|---|---|
| M1 | Fixed | Verified: `regimes.py` 698-699 use `t_delivered - t_ready`. "to its delivery", "delivered within 24 h", "delivered within a day". The registration says "mean waiting time of urgent cargo" and names no end point, so there is no deviation to report; the paper says the earlier "to its pickup" was an error of the text. | 4.4, 5.3, abstract, 8 |
| M2 | Fixed | Row movements recomputed for the primary outcome from archived against current rows: E40 -0.27 h mean, 2.4 h absolute, max 153 h (plan-ahead on Earth, 60 %); E42 +0.21, 6.9, 256; E41 -0.10, 1.6, 18. All match the referee. New Table C1: H1, H2, plan ahead, relay 0.8, H3a, H4 linear, H4 network, H6 before and after, with outcome; no verdict changed (H3a -0.38 to -0.84; H4 linear -2.49 to -2.32; H2 91.3 to 89.9; H6 4.2 to 5.4 pp). | 4.6, Appendix C |
| M3 | Fixed in part | The 99.5 % is gone from the text. Each comparison is stated as itself: H1 pair, delivered only, 5.8 h (3.7 to 7.6, n 30); owners alone strict minus marketplace, delivered only, 100 h (n 80), censored 1,242 h; "do not add, so neither yields a share". "Never" replaced by "had not delivered by the end of the year"; the hours scale with the horizon; owner C alone delivers 1.6 t against 491 t pooled; the split was not varied. Not done: share of urgent items undelivered per regime in Table 5 (no such column in the run rows). `P1-H1-UNDELIVERED-SHARE` stays in `values.json` only because the site reads it. | abstract, 1, 5.2, 6.1 to 6.3, 7, 8 |
| M4 | Fixed | "H4 as registered is about the network ... with the linear model as a secondary report; for the network it is not supported." Abstract and conclusion: "The registered learned bid, a network, did not beat hand-built bids; a linear correction, registered as secondary, cut the wait by 16.5 %." Table 7 row and 4.6 say the linear row entered the Holm family after its result on these seeds was seen. "Evaluated once" replaced by "no training or selection used seeds 1-30", with the three runs named. | abstract, 1, 3.10, 4.1, 4.5, 4.6, 5.6, Table 7, Table 12, 8 |
| M5 | Fixed | Mass share (kg delivered over kg ready): +1.7 pp (1.5 to 2.0) at 0.10, +5.4 pp (3.5 to 8.5) at 0.25. Items, from the E42 rows: +11.8 a year (8.0 to 15.7) on 2,920; +80.7 (28.0 to 168.7) on 2,853. Matches the referee. "Registered on" replaced by "a cell the registration does not name; 0.10 is the design's default". | 5.7, Table 7, Table 12 |
| M6 | Fixed | The rule was not applied in any cell. Count from the rows with the paper's bootstrap: 29 of 40 (12 of 12, 10 of 15, 7 of 13), not 28; three cells sit within half a point of the threshold, so the count is 27 to 30 by method (a t interval gives 30). Paired reading: exceeded for H1, H2, H3a, H4 linear. | 4.5, 7 |
| M7 | Fixed | Verified `best_epoch: -1` and "iterations 1-4 were not run". Text: first iteration only, 37,941 rounds labelled, no correction improved held-out agreement, the loop was not run, "all of the learned policies' behaviour comes from the second stage". | 2.4, 3.10, 5.11, contribution 4 |
| M8 | Awaits B-106 | Table 6's caption, 5.6, 5.11, 4.6, Limitations and Table 12 say the values are from the evaluation of 27 October, on the engine before changes 4 and 5, and have not been rerun. "Every number" now reads "every number from E40, E41 and E42". Placeholder path `results/ATC_learned_eval_rerun.json`: the build reads `ood` and `guards` from it when it exists. | 4.6, 5.6, 5.11, 6.5, 7 |
| M9 | Fixed in part | Baseline limits (five tries, 12 of 60 minutes, assumed, not swept); 6,028 x 0.25^5 = 5.9 of 10, 62 of 85 at 0.40, 0.06 of 4 at 0.10; the return edits the contact plan while the jobs stay; 82 returns against 199 jobs and 57 % of driving time linked, not costed; the blackout bears only on the ledger. Rule rewritten as decision B1 (segment unconfirmed, caution speed). "No stuck reservation" withdrawn: 2,566 of 2,628 unconfirmed, 7,349 h, without the return; with it, not counted. H14: first clause holds against the stated baseline; second clause not testable as written. Not done: the control run without a cap. | abstract, 3.13, 4.8, 5.9, Table 11, Table 12, 7, 8 |
| M10 | Fixed; v0.2 awaits B-100 | H13 is a design calculation (fleet sum 20 x 0.393 = 7.86 kbit/s in any geometry; the note had 49 B/s, 7.9 and 65.6 kbit/s before E53). "On the air" removed everywhere; packet before link framing and coding, plus 12 B per Proximity-1 frame (63.5 B/s, 10.2 kbit/s, 12.7 scheduled, full at 25 rovers, not 32). Traffic model: 11 of 15 types (not TASK_ANNOUNCE, CAP_QUERY, CAP_MANIFEST, MAP_NOTICE). v0.1's POSITION has no frame, datum, time-scale identifier or covariance; v0.2 adds them, sizes not available. Placeholder path `lunarsim/schemas/lrip-v0.2.json`: the build stops when it appears. | abstract, 1, 3.12, 4.8, 5.8, Tables 9, 12, A2, Appendix B, 7, 8 |
| M11 | Fixed | Verified: 2,029 distinct of 2,750 (721 repeats: 650 in 13 Earth-independent cells; A_MOON 39, 61, 71 of 80; A_EARTH plan ahead 78 at 10 %). 60 rows of E41 and E42 rerun E40's auction cell: "5,480 simulated years, at most 4,699 distinct". "Pre-registered" removed. Table 5 shows distinct counts and the 79 runs with an urgent item. | abstract, 4.2, Table 4, Table 5 |
| M12 | Fixed | (a) 12 % is an input; (b) s^2(1-s) against 1-s, second part of H6 is a property of the model; (c) meeting wait = failures x timeout (checked); (d) 20 retries in the arbitrated variant; (e) verified `winners = [best]`: the best bid always wins, loss adds a parallel winner or a wasted trip. Table 12 has the statuses "calculated from assumed inputs" and "property of the model". | 3.7, 3.8, 5.7, 6.1, 6.6, 7, Table 8, Table 12 |
| M13 | Fixed | "An always-up relay equals the marketplace run for run; the auction was not distinguishable from it; only an 80 % relay was worse than the auction, by 3.8 h (2.0 to 5.7 h)." Verified -3.75 [-5.70, -2.02], n 30, unregistered, reported in 5.4. Both oxygen-plant clauses deleted. | abstract, 1, 5.4, 6.3, 8 |

## SHOULD FIX

| # | Status | What was done | Where |
|---|---|---|---|
| S1 | Fixed | Four departures listed; "one-sided p = 0.002; two-sided 0.004", Holm 0.004 and 0.008; the sign test was added after the results. H10' is no longer provisional: the family file now holds the 8x cells. | 4.5, 4.6, 4.8, 5.9 |
| S2 | Fixed | "As revised in change 2 after a five-seed development run"; the first yardstick "would not have been met"; year-clustered interval 77.2 to 102.3 h; per-year tests on 7 to 10 runs; the false sentence on the pooled interval removed. | 1, 4.5, 5.3, Table 12 |
| S3 | Fixed in part | Stated: 809 returns a year, 11 with a perfect radio, 15.2 h, 0.3 h above the marketplace. Not done: the marketplace with the same move (needs 30 runs). | 5.4, 6.1, 7 |
| S4 | Fixed | No bound in cost, with the counterexample (M against 2); toy score named; the Fisher, Nemhauser and Wolsey sentence deleted (not opened). | 2.1, 3.11, Appendix B, Table 12 |
| S5 | Fixed | Heartbeat 1 s (the protocol's): 4.5 s detection, 0.78 false marks a day, k = 5, 8, 12. With the lease: 112.8 min, about 1.9 h, 29 times less than Earth's 53.8 h; 52.9 min after a sighting. "One rover watching one"; the design-note sentence deleted. | 3.13, Appendix B |
| S6 | Fixed | Proposition 5: inputs chosen to match the ratios, a consistency check. Proposition 6: definitional for six of eight fields; 13 B is this layout's size. Names kept, with a sentence saying both are counts. "Each with a number" replaced. | 3.13, Appendix B, contributions |
| S7 | Fixed | "A grant was generated for every award" (6,028 against 2,628 reservations); the stopping sentence deleted; grant loss labelled a consequence of two settings; ledger given as 31 bundles. | 4.8, 5.9, Table 11 |
| S8 | Fixed | Urgent = crew consumables, with the five cargo classes; 15, 52 and 122 items a run (ranges 0 to 31, 21 to 102, 61 to 184). Given in the text, not as a Table 5 column. | 3.1, 4.4 |
| S9 | Fixed | "Wrote the layer down, implemented its encoding and counted its bytes"; what exists and what does not; the unseen-class case "was not run". | 1, 3.12 |
| S10 | Fixed in part | (a) [32] dropped from citations; [13], [14], [15], [18], [22], [23], [33] cited as read in abstract; (b) CADRE "reported in hardware tests [72]"; (c) reworded; (f) [43] corrected, "cite by tag" removed; 48 B "by our count". Not done: (d), (e) and the missing reference fields need sources opened and recorded in the notes. | 2, Table 1, 6.2, NOTES.md |
| S11 | Fixed in part | Says the design cannot attribute the penalty to loss (stale claims 85 and 86, 313 and 314); the claims sentence reworded. Not done: the two loss-free cells. | 3.7, 5.5 |
| S12 | Fixed in part | Both sentences softened to "13 weights, which we have not interpreted"; search not converged stated. Not done: ablation and tuned baseline. | 5.6, 6.2, 6.3 |
| S13 | Fixed in part | (b) H9', H10'; (c) "at most 0.003"; (d) follows B1; (f) the two checks told apart. Not done: (a) P3's 10.06 at 1.024 hops is not quoted; (e) which paper reports E53 and E54 is the lead's decision. | 4.8, 5.9, 3.12 |
| S14 | Fixed in part | Limitations added: ownership split and horizon, auction model, reference without the return move, no channel capacity, base computer, no vehicle failure, baseline transport, E53 sampling. Experiments not run; listed as future work. | 6.5, 7 |
| S15 | Fixed | 658 tests collected on 11 November (547 passed at B-74; not rerun in full); statement now names `dev_notes.json` and typed inputs. Journal policy not checked. | 3.11, AI statement, dev_notes.json |
| S16 | Fixed in part | (a) 6.4 is one sentence; (b) the check list is the six failures and a count; (c) most terms defined or replaced; (d) Tables 7 and 8 in words; (f) fixed, PDF pending memory. Not done: (e) new figures; (g) only the bid rule and cargo classes were added. | 3, 5.11, 6.4, Tables 7, 8 |

## OPTIONAL

| # | Status | What was done | Where |
|---|---|---|---|
| O1 | Fixed | Auction against relay 0.8: 3.8 h shorter (2.0 to 5.7); against plan ahead: 8.2 h (5.0 to 11.7). | 5.4 |
| O2 | Not done | Percentile bootstrap kept for the per-year tests; the 7 to 10 runs are stated. | 5.3 |
| O3 | Fixed | "Different quantities ... set side by side and not compared". | 5.5 |
| O4 | Fixed | "rho(AT + IT)/IT, which is rho(AT/IT + 1)". | Appendix B |
| O5 | Fixed | 10 % load, mean delay per delivery, 80 rows with repeats. | 4.5 |
| O6 | Fixed | Owner C is invented; its rover class is owner B's company's product. | 3.2 |
| O7 | Fixed | The broadband vectors carry the 8 B code; the 16 B code has no vector. | 3.12 |
| O8 | Fixed | The slogan and the "order of value" sentence are deleted. | 8 |

## Where the recomputation differs from the report or the task

- M6: 29 cells, not 28, with the paper's own bootstrap (seed 40); 30 with a t interval. Three cells are at 10.0 %.
- M12(e): "never a worse assignment" is too strong. A parallel winner takes a load that a later round might have
  given to another robot (`auction.py` 246-260). The paper says loss cannot keep the best bid from winning.
- M10: v0.1's POSITION does carry one uncertainty value (`sigma_h`, horizontal one-sigma); what it lacks is a
  covariance, and frame, datum and time-scale identifiers.
- M1: the registration does not say pickup, so no deviation exists.
- S1: H10' is no longer pending 8x in `phase6_family.json` (file of 12 November).

## For others

- The site's /paper/ page still reads `P1-H1-UNDELIVERED-SHARE` (99.5 %) from `values.json`.
- `compare_rerun.py` still calls `delay_mean_h` the primary outcome in its JSON.

## Second pass, part 1 (12 Nov)

| Item | Status | What was done | Where |
|---|---|---|---|
| `P1-RELAY08-SHARE` | Done | New key, "80 %", read from the `coverage` column of the cell `B_EARTH_RELAY 0.8` in `results/E40_runs*.csv` (the build stops if the cell has more than one coverage value). Used in all 11 places where the text said 80 % of that relay, and in the two composed regime names. | abstract, 1, 5.1, 5.3, 5.4, 5.11, 6.1, 6.3, 8; `values.json` |
| B-103 (`E53_bitrate.json` `driving_split`) | Done | New `P1-E53-DRIVING-SENTENCE`, labelled a calculation: 2.6 % of the sampled vehicle-steps are driving steps; on those, 1.58 hops, 93 % with a path, busiest link 5.9 kbit/s (7.4 scheduled), against 1.01 hops, 99 % and 7.9 kbit/s parked; 57 % of driving time linked in E54's month; with STATUS and INTENT at 1 Hz the sources offer 19.52 kbit/s, above the 16 kbit/s budget, so H13's first clause holds only at the assumed report rates. The earlier pointer sentence is replaced. | 5.8, 7 |
| B-104 (`E48_sizing.json` `revision_b104`) | Done | New `P1-LINKLAW-SENTENCE`, labelled a calculation outside the runs: rover to rover at 5 km, 1,574 kbit/s flat ground against 701 kbit/s with the Moon's curvature (5 dB more loss). P1's runs use no link law. | 5.8, 7 |
| B-101 (`E50_near_base.json`) | Nothing to change | P1 names H9' only as reported in the companion paper [45] and states no clause or verdict of it. | 4.8 |
| Landed files | Checked | The build does not read `E50_near_base.json` or `E44_fresh_seeds.json`; its only stop on a landed file is `lunarsim/schemas/lrip-v0.2.json` (B-100, still awaited). It passes with the updated `phase6_family.json` and `E53_table.csv`. | `build_p1.py` |
| B-106, B-100 | Still awaited | Left as plain sentences with their placeholder paths. | 5.6, 6.5, 7 |

Build: abstract 299 words, conclusion 249, 288 values, 0 pending, no `[[PENDING` in `paper.html`. PDF not rebuilt.
