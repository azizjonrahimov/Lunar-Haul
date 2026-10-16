# Referee review, round 1: "Where the Lander Lands" (v3, paper/v3/paper.html)

Checked against results/table_E15–E20*.csv, E20_fit.json, data/policies/outcomes_*.json and the policy cards, driving-v1.json, sites.json, figures/phase3_captions.json and the figure PNGs.

## Summary verdict

1. The numbers are in unusually good order: of roughly 400 result values in the Abstract, Sections 6–8 and Tables 7–13 that I recomputed, all but the handful in Section 1 agree to the printed precision, and none of the slips changes a conclusion.
2. Must: the dispersion "hypothesis test" is a property of the engine's rules, not a finding, and the fit does not confirm it (C1, C2).
3. Must: the headline law slopes are evaluated at utilisation u = 0, outside the data (0.02–0.08); at the loads run, the stand-down and keep-out terms are near zero or negative, as Section 6.5 reports, so the Abstract contradicts itself (C3).
4. Must: Section 6.5's "only two Phase-3 marketplace cells exclude zero" at 3 km is wrong (131 of 600 cells; 16 Phase-3 marketplace) (N1).
5. Must: Figure 2's image file does not exist; Figure 10's caption describes a panel the figure does not contain; two Zenodo DOI placeholders remain (S1–S3).
6. Should: the Abstract (about 1,000 words) overstates three ranges; "two autonomous ≈ six teleoperated" reverses in-house and has no paired interval; three Table 7 rows are not from released tables although the caption says so; the $5,525 figure has no table behind it.
7. Should: Limitations must name the marketplace staging rule changed after the first E18 results, and the damage-cost floor that guarantees "never at 0.5–1 km".
8. May: rounding slips, figure ordering, voice tics.
9. Voice: no em-dashes, stock openers or filler vocabulary; the prose is a researcher's. What still reads as generated is a few repeated devices (Section 3).
10. Keep the honest passages listed at the end of Section 3.

## 1. Numbers

Verified: all of Tables 7–13; 6.4 (40 standoff cells, concavity 0.52/0.31/0.10/0.12, ratios 0.42/0.61/0.65/0.52, km and kWh); 6.3 (off-pad shares, dCL ranges, exclude-zero counts 2/2/1/4/6); 6.5 (941/240/19; bins 41/132/49/18; radius and stand-down averages; stand-down hours); 6.6; 6.7 (every coefficient, R² 0.478, residual SD 0.587, per-rule fits); siting (75.1/19.0/5.9; 27/3/6; Table 13 totals); 6.1 against the outcome JSONs (p90 horizontal speed 1.39 vs 0.15 m/s, tilt 4.5 vs 1.6°, no_eta −5.5 to −17.3 m/s, hover-v1 return +43) and the cards (round box rates, label inconsistency, 655/714 s, 2,007,040 steps, 9,685 s). Exceptions:

- [must] N1. 6.5 "At the 3 km standoff … every cell is within ±1.5 h and only two Phase-3 marketplace cells exclude zero": table_E18 has 131 of 600 D = 3 km keep-out cells excluding zero, 16 of them Phase-3 marketplace (4 with the night on). Max |Δ| is 1.50 h.
- [should] N2. Abstract "it reaches +1.02 h [+0.27, +1.68] to +2.85 h … only at IM-1's 1,500 m" vs 6.3 "+0.62 h [−0.90, +1.77] to +2.85 h": the Abstract drops the two cells whose intervals include zero. Say "in the six of eight cells that exclude zero".
- [should] N3. Abstract "it stays under an hour up to IM-2's 300 m": at 300 m the P2-2 marketplace cell is +1.05 h [−0.17, +2.96] (Table 8). "Below 300 m".
- [may] N4. Abstract "the delay by at most half an hour" (pad radius): dR50 reaches −0.54 h (P2-4 in-house, 100 m pad). "About half an hour".
- [may] N5. 6.5 "costs more vehicle-hours than the 6 h window … in every fleet and rule": P2-4 in-house at 3 km is 77.4 vs 77.7. "All but one".
- [may] N6. 6.5 "+1.56 h [+0.05, +3.13]" names no cell (P2-4 in-house, 3 km, 0.1 h); "+1.86 h [+0.64, +3.22] (… two-minute and six-minute)" quotes the two-minute CI for both (six-minute is [+0.52, +3.33]).
- [may] N7. 6.6 "($176–$694)": table minimum is $174.5. 7.1 "2,400–3,300 console hours" vs 6.6 "2,381–3,323". 5.2 "timeouts (2–3%)": 2.2/3.2/1.0%. 3.4 "about five minutes" vs 5.4 "276 s" vs card 279 s.
- [may] N8. 6.1 "ran at 60–70 s per 100,000 steps otherwise, which the 314 and 464 s … confirm": the card's curve gives 52–56 s per 100k after the stall; the variants ran at 62 and 91.
- [should] N9. Section 6 "$5,525 [4,460, 7,281]": no file under results/ holds this quantity or its bootstrap (the raw CSVs carry landed_kg but no cost per landed kg; the value traces to .team/reports.md). Add a derived table or script.
- [should] N10. Table 7 caption "from the released outcome tables": the memoryless expert (94.8%), the round-0 clone (87.2%) and the PPO reward-v1 row (43.6%, with full failure counts and statistics) are not in table_E15 or data/policies, and two of the three are in the Abstract. Release them or label the rows unreleased.
- [should] N11. 3.3 and 6.1 "Cloning the filtered law reached 75% … 69, 60, 51 and 43%": the lander_CLPS_bc_s0 card records 1,000 episodes, 30 epochs and four rounds of 400, not the 800/25/2×300 recipe of the Methods, and says the record was reconstructed after the run crashed. State both.
- Every quoted interval contains its point estimate; every value quoted twice agrees except N2–N3 and N7.

## 2. Claims

- [must] C1. "Dispersion acts through off-pad landings only, not smoothly through distance" (Abstract; 6.3 "The first finding is mechanical"; 7.2 "the hypothesis test that came with it"). A miss inside the pad adds nothing and a miss outside adds exactly 2 × miss (3.6, Assumed); the smooth branch of RQ6 was never implemented, so the design could not have found it. 6.3 admits this and 7.2 then lists it as a tested hypothesis. Reframe the findings as (i) the off-pad share as a function of miss and pad radius and (ii) the small delay cost per off-pad landing at these loads; drop "hypothesis test".
- [must] C2. 6.3 "the fitted law of Section 6.7 confirms it: the coefficient on the logarithm of the mean miss is indistinguishable from zero": the off-pad-share coefficient is also indistinguishable from zero (+0.025 [−0.097, +0.139]) and ln miss × u is large (+1.37 [+1.14, +1.58]). The fit confirms neither channel; it moves the dispersion effect into the load interaction.
- [must] C3. The law's headline slopes (Abstract; 6.7 "Distance is what costs"; 7.1) are "at the fit's origin", u = 0, while u spans 0.021–0.077. With T × u = −0.66 the stand-down effect is ≈ 0 at u = 0.035 and −1.5%/h at the Phase-3 marketplace's 0.057, consistent with 6.5 ("the short windows cost more") and inconsistent with the Abstract's "+2.3% per hour"; the radius term goes from +12.1%/km to −3.3%/km (6.7 says so). The Abstract states "indistinguishable from zero" for a 1 km keep-out and "+12.1% per kilometre" in one sentence without reconciling them. Centre u at its mean or report slopes at the reference-cell loads.
- [should] C4. Standoff +40%/km (Abstract): 6.7 and 7.1 carry the concavity caveat (0.52/km below 1 km, 0.10–0.12/km beyond 2 km); the Abstract does not. Add it or quote the cell range (+4.10 to +18.39 h at 5 km). A referee will ask why a concave response was fitted linear in D (ln D or a knot at 2 km).
- [should] C5. "Two autonomous vehicles deliver urgent cargo about as fast as six teleoperated" (Abstract, 6.6, 7.1): true under the marketplace (13.3 vs 14.6 h), reversed in-house (23.2 vs 21.0 h), both inside ±4–5 h intervals, no paired difference although the cells share seeds. Qualify as marketplace-only and give the paired interval.
- [should] C6. "No teleoperated fleet … matches the same-day service level of six supervised ones (90.0 ± 4.7% against 93.6 ± 3.7%)": the intervals overlap by most of their width. Give a paired difference or soften to "lies below".
- [should] C7. 6.6: the marketplace autonomous fleet is slower with six vehicles (5.4 h) than four (4.3 h), and the four-vehicle fleet books more console hours (3,323) than six or eight; Figure 10 shows both. The fleets differ in composition (the six-vehicle fleet carries the hauler and micro-rover), so the "exchange rate" is partly composition. Say what the fleets are and comment.
- [should] C8. "Never at 0.5–1 km" (Abstract, 6.7, 7.1): with 8 impacts at 1 km, shield 1 and the sweep's floor of $0.1 M per impact, damage at 1 km is ≥ $6.4 M/yr against $0.5 M/yr of hauling, so no swept assumption could put the minimum at 1 km; about $10 k per impact would. State that "never" is a consequence of the sweep's lower bound, in Limitations too.
- [should] C9. 6.5 "the staging rule now sends the vehicle to the nearest site outside R": the marketplace's keep-out cost is reported after a rule change motivated by a penalty seen in these same cells; the other three rules did not get one. 6.5 is candid; 7.3 and Section 8 should name it.
- [should] C10. 7.4 "withhold it and no amount of DAgger helps", "observation sufficiency, not algorithm": generalised from one expert, one class and four rounds. Keep the observation, drop the universals.
- [may] C11. Untested causal sentences: 6.4 "for the version-2 reason that a pooled vehicle is usually closer"; 6.5 "because a window and the dark can coincide"; 6.5 "after a two-minute window the evacuated vehicle is still driving to the shelter" (the channel ablation covered one cell). Mark as explanations.
- [may] C12. The lander ladder 93.8/94.8/89.0/63.2 mixes environment versions 1/3/2; the paper's argument that shared seeds make this harmless belongs in Table 7's header.
- Novelty: nothing in Section 2 contradicts 7.2; the research notes (plume_ejecta_base_layout.md "No published study optimises pad-to-base distance", novelty_prior_art.md) support the claim as bounded in 2.6. The PPO comparison and the untrained driver are framed honestly (7.3, 8).

## 3. Voice

No em-dashes (0), no "notably/importantly/overall/in summary", none of the listed filler words in the author's prose (the three "robust/paradigm/critical" hits are inside quotations), no rhetorical questions beyond RQ6–RQ9. The remaining tells are structural:

- [should] V1. Counted openers, eleven: 3.1 "Three things about the version-2 engine matter"; 3.3 "Two things in this design were forced"; 3.3 "Four failures during development shaped"; 3.4 "Three caveats stand"; 5.2 "Four checks compare"; 6.4 "Two features of the terrain shape"; 6.5 "Two modelling questions came out of that"; 6.5 "The final tables say four things"; 6.7 "Two cautions on reading"; 7.2 "Four things in this version"; 7.5 "Five things, in order". Keep three; elsewhere start with the first item ("The demand and operations streams are separate…"; "A class-dependent keep-out radius would change most…").
- [should] V2. Verdict one-liners and "X, not Y" constructions (39 of ", not "): 1 "Nobody has priced the alternatives." / "The reason is structural."; 6.5 "The exclusion itself is nearly free; the radius decides." / "What the keep-out does cost is driving."; 6.6 "The service level tells the fleet-sizing story." / "The operator bill is the other half."; 6.7 "Distance is what costs." / "The shield at 2 km does the work." / "The pattern is simple to state."; 7.1 "turns out to be a pad question before it is a logistics question"; 7.4 "The PPO lesson is older and plainer." Delete "The pattern is simple to state." and "The reason is structural."; fold the rest into the sentence that follows ("The keep-out's measurable cost is driving: in the Phase-3 fleet…").
- [should] V3. 7.1 restates Section 6 with the same intervals (six CIs from Table 10 verbatim; Table 9 repeated). Cut 7.1 to interpretation and cite the tables.
- [may] V4. Same reveal twice: 6.2 "That looked like a bug, and it is not." and 6.5 "which looked like an error and is the return drive". Keep one.
- [may] V5. 1 "We are explicit about what we do not claim." Start at "We do not predict plume ejecta".
- [may] V6. 6.3 "The first finding is mechanical, and we state it first because everything else follows from it:" → "The first finding is mechanical:".
- [may] V7. "which is why" (6), "That is why" (2), "therefore" (21), "stated rule/reasons/level" (11): thin by half.
- [may] V8. 6.1 "Those are the marks of a policy that has found the edge of the box" → "The policy has found the edge of the box and the cheapest way over it."
- [may] V9. 1 "Section 2 reviews … Section 9 gives availability": the roadmap paragraph can go.

Keep, because a referee reads them as honesty: 4.2 (the five-seed pilot that reversed sign); 5.3 and Table B4 (the documented browser divergence); 6.2 "the check tests the implementation, not the model" and "They are not validated, because nothing exists to validate them against"; 6.5's first paragraph; 6.1 "what a modest budget buys, and what it does not"; the Section 6 correction of version 2's $5,000; 3.4 "this follows from the Assumed supervised values, not from data"; 7.3; Section 8; Appendix C; the Acknowledgements.

## 4. Structure and apparatus

- [must] S1. paper.html references ../../figures/v3_fig02_dataflow.png; the directory holds v3_fig02_pipeline.png/.svg. Figure 2 renders blank. (v3_fig01/03/04 exist.)
- [must] S2. Figure 10 caption "mean urgent delay and same-day service level": fig25_autonomy_fleet.png plots delay and operator console hours (phase3_captions.json agrees with the figure).
- [must] S3. Placeholders: 9 "[[DOI: Zenodo record for version 3 …]]" and [113] "[[DOI: Zenodo record of version 2]]".
- [should] S4. No Conclusions section; Section 8 is Limitations and the Abstract carries the conclusions at about 1,000 words. Cut the Abstract to 300–400 words and add a half-page Conclusions before Limitations.
- [should] S5. Figure 2 is first cited in 3.6, after Figures 3 and 4; Table A3 is cited before A2 in the Appendix A preamble.
- [should] S6. [110] (Chang'e-4) is uncited; the flown record in Section 1 omits Chang'e-4, so cite it there or drop it. All other 73 entries are cited; the apparent citations of [4], [6], [7], [8], [12] are the cost intervals "[4,460, 7,281]" etc., not references.
- [should] S7. Reproducibility: the classical law's filter constants and PD gains ("Its gains are Assumed", 3.3) are not given; the bc_s0 recipe differs from the Methods (N11); NumPy version absent (SB3, Gymnasium, PyTorch, Python given). Seeds, cell counts, bootstrap and Monte Carlo seeds are all stated.
- [should] S8. Limitations names R² 0.48, the single site, the untrained driver, the swept plume rule and the PPO reward. It omits: the u = 0 extrapolation (C3); the by-construction dispersion channel (C1); the post-hoc staging rule (C9); the damage-cost floor (C8); that E17–E19 use the classical law's tables only (in 4.1, not here); that Wittal's 10 t curve is applied to 2 t and 60 t landings alike.
- [may] S9. References without a locator: [87] (no URL), [106] (no venue), [112] (unverified, stated). [91] cites research_notes inside a reference; move to Appendix C.
- [may] S10. Flags are consistent; gravity 1.62 (3.3) vs 1.622 (Appendix D) is acknowledged. Cross-references all resolve. Captions of Figures 5–9, 11, 12 match the figures and captions JSON; Figure 9's cells spot-checked against Table 10 agree.

## Counts

[must] 7 · [should] 20 · [may] 15
