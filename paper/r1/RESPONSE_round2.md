# Response to the referee, round 2

Manuscript: "What Earth's Horizon Costs a Lunar Base: Terrain-Masked Communication Windows in South-Pole Cargo
Logistics" (R-1). Report answered: `paper/r1/REVIEW_round1.md` (2026-10-22). Revised text: `paper/r1/paper.html` and
`what_earths_horizon_costs_r1.pdf`, built by `paper/r1/build_r1.py` from the round-2 result files (`results/*_r2.*`).
Sections 1-4 and the appendices were revised first (see `NOTES.md`, "Changelog (parts 1-3 and this file)"); this
file covers the whole report and says where each change is. Numbers below are those of the current build; every
number in the paper is filled from the result files.

Status at writing: all round-2 stages have run. Stage A's relay coverage 0.05 (six cells, not requested by the referee) was planned but did not finish: each run is slow because rovers wait long for a link, and the background job was stopped when the machine ran low on memory. The paper states the knee as at or below 0.1 (Section 4.2).
The text is written so that it holds with or without those cells: the lowest relay level, the count of levels, the
knee, the restoration and completion shares at the lowest level and the strict-fleet curve are read from the data.

## Required changes

### Must

| # | Item | What changed, and where |
|---|---|---|
| 1 | Factual and reference errors (E1-E19, E21, E22, E25) | See the E rows below; every one is addressed. |
| 2 | Relay price interval | All 2,000 draws kept (none dropped). 0.1 of coverage = 38 M$ a year, 95 % interval 11-370 M$; the upper bound is stated as above 200 M$ and poorly determined, with the reason (Section 5.5, Table 8). Shares of draws: rover buys nothing 1.25 %, beyond full coverage 0.55 % (E3). Labelled "at coverage 0.5, for the strict fleet and this demand" in Section 5.5 and "at coverage 0.5 ... for this fleet" in the abstract, whose price reads "38 M$ (11 to over 200 M$)". Rover cost basis: Modelled in [33], operators and energy excluded (E14). |
| 3 | Reframe the throughput headline | Section 5.2 and Table 6 split the loss: bulk 499.6 → 296.3 t (−40.7 %), lander cargo 29.3 → 9.4 t (−68 % [−92, −43]), returns −75 %; the 200 t/yr feedstock haul to the never-linked plant is stated next to the 42 %, with the bound (204.2 t ready, all lost, 90 % of the gap). Stage E's local-feedstock case shows the loss would be 24.3 t (7 %). At 3 km pads under DTE no lander cargo moves and no urgent item is delivered in any seed (Section 5.7, Table 9). Abstract, Discussion paragraph 1 and Conclusions carry the split and the assumption. Figure 2 has two panels (lander, bulk). |
| 4 | Censoring in urgent delay | Every table with a 90th percentile shows the completion share next to it (Tables 6-9). Section 5.3 reports completion (strict: 96 % → 43 %) and the censored 90th percentile (median ≥ 5,727 h against 9 h). The criterion and pad results are re-read in this light (Section 5.7): the round-1 "stricter criteria improve delay at 1 km" is censoring (completion falls, censored percentile rises; no stricter criterion shortens censored delay significantly in any cell). E10: Table 9 says "none delivered" where no seed delivered an urgent item. |
| 5 | Robust delay statistics | Medians, geometric-mean ratios with t intervals on the log scale and Wilcoxon p for every main delay comparison (Sections 5.3-5.8, Tables 6 and 8); year-blocked intervals for the primary comparisons (Sections 5.2-5.5); per-start-year results (Figure 4, Section 5.4, Section 5.2 per-year text via the year-blocked intervals). The Results opening states that intervals include calendar variation over 2028-2031 and rest on four calendar draws; Section 7 repeats it. |
| 6 | Strategic versus rover | Tested: Δp(strategic) − Δp(+1 rover) = +0.05 [−0.26, 0.34], positive in 79 % of draws, not significant (Section 5.5). Stated that the Stage B strategic step has no look-ahead and that the look-ahead step was added (worth 0.17 [0.10, 0.36]). Section 5.4 shows where the strategic step helps: under DTE it recovers most urgent deliveries (completion median 43 % → 97 %, lander cargo ×3.34, censored ratio 0.12 [0.07, 0.22]); with a relay it shortens delivered-item delay (×0.18 at 0.1, ×0.51 at 0.5) but not censored delay or completion (0.1: ×0.45 [0.11, 1.86], Wilcoxon p = 0.65). The look-ahead policy does not recover the DTE loss. "Autonomy before rovers" is limited accordingly (Section 6 paragraph 3, Section 8). The stranding explanation is replaced by the 2028 calendar effect (E17). |
| 7 | Soft operator pool; full relay = always | Section 5.6 states the soft pool and reports absolute peaks and seeds over staff (teleoperated: 4.6 under DTE, 18 of 20 seeds; 5.5 at 0.1, 20 of 20; 3.4 at full, 8 of 20; reference mix never above 3). Stage A2 (hard limit) is reported against Stage A: waits 13-56 vehicle-hours a year, tonnage within 1.0 t, completion within 1.9 points, delivered-item delay up by at most 18 h (significant only at 0.3, 0.5, 0.8, by 1-6 h); reference mix identical. Full relay vs always per fleet: identical for five fleets, differs for the teleoperated fleet (p90 in 8 seeds up to 15.5 h; censored p90 in 7 up to 1,864 h; tonnage in 3 up to 2.4 t; operator waits in 18). Figure 6: absolute peaks, staffing line, A2 cells, no "always" point (E11, E12). |
| 8 | Relay sees every route point; idle fleet; LCRNS | Both conditions open Section 5 and are repeated in Section 5.2, the Discussion (paragraphs 2-3), Section 7 and Section 8 and in the abstract ("for this lightly used fleet, a relay assumed to see every route point"). Rover claims are conditioned on slack (utilisation 2.8 % always linked, 3.3 % under DTE). LCRNS comparison corrected (Section 6 paragraph 2): 80-86 % is DTE plus relay, equivalent to a relay alone at p ≈ 0.6-0.7, where the strict fleet's delay is 1.4-1.9× its full-coverage value, at or just inside the 2× target, not on the flat part; the cross-reference is Section 2.2 (E13). |
| 9 | Deferral | Section 5.7: under DTE, 12, 24, 72 h and no limit give the same completion and censored delay (ratios 0.98-1.04, every Wilcoxon p ≥ 0.13); no limit raises the delivered-item p90 (380 → 2,319 h); for the teleoperated fleet a 12 h limit costs 8.3 points of completion; at relay 0.8 a long limit shortens delivered-item p90 by 5.6 h but costs 5.2 points of completion. "Matters just as much" is gone. Section 7 states the choice and these results. |
| 10 | Unreported primary metrics; throughput break-even | Cost per landed kilogram is now a secondary output (Table 5 caption, part 3); the 24 h service share and the mean delay are no longer outputs of the paper (they stay in the result files). None is used in Section 5. The throughput break-even is one sentence (Section 5.5, Section 4.4): undefined, because throughput saturates by the lowest relay level and rovers add nothing under DTE. |

### Should

| # | Item | What changed, and where |
|---|---|---|
| 11 | Relay levels 0.6, 0.7 | Run; Table 7 targets now fall between measured cells (strict 2×: 0.58 [0.36, 0.72]; 1.5×: 0.68 [0.58, 0.92]). Level 0.05 did not finish (see the status note); the text says the knee is at or below 0.1. |
| 12 | Stage B with look-ahead and a second coverage | Look-ahead in Stage B at DTE and 0.5; strict and strategic with 0 and 1 extra rover at 0.2 and 0.8 (Section 5.5, Table 8). One rover is not significant at 0.2 or 0.8 either; the strategic step shortens delivered-item delay at both. At 0.8 the strict cell lies above its 0.7 neighbour, so Δp there is flagged as not informative. |
| 13 | Relay gap sensitivity; DRM-0 vs RC 3.1 | Stage E (Section 5.8): 2 h and 24 h mean gaps, periodic DRM-0 (784 min) and RC 3.1 (30 h). Gap pattern moves delay (e.g. ×0.71 with 2 h gaps, ×0.57 periodic DRM-0 at 0.1) but not throughput, except RC 3.1 at 0.1 for the teleoperated fleet (−20.6 t, −3.9 %); RC 3.1 at 0.5 lowers strict completion by 5.6 points. Why the DRM-0 gap stands in: part 3 (2.2, 3.7, Table 4). Section 7 repeats the limitation. |
| 14 | Antenna height | 2.5 m tied to VIPER's mast in Section 3.3 (part 3). No other height was run (M10 not done); Section 7 says so. |
| 15 | Intervention-rate sweep | Stage E (Section 5.8): ×0.5 helps the strategic fleet (+25.6 t under DTE; censored ratio 0.34 at 0.5); ×2 changes nothing significantly; look-ahead unaffected under DTE. Section 7 notes uniform placement and possible clustering of hazards in dark terrain. |
| 16 | The law | Section 5.3: cross-validated errors almost equal (strict 0.682 / 0.687 / 0.683), in-sample factor two; no form represents the slow tail; the hyperbolic bound stated; no target read from a law. Law column removed from Tables 7 and 8; no fitted curves in Figure 3. |
| 17 | Abstract and Discussion openings; code tokens; jargon | Abstract ~240 words, validation numbers moved to the body, one number per claim, conditions stated. Each Discussion paragraph opens with a finding and its condition. Tables and prose use words (reference mix, strict, strategic, look-ahead, teleoperated; "any part", "centre 0.5° above"); no file or code tokens outside Availability; no project labels (E21, B-44) in the prose. Jargon defined in part 3 and Appendix B; Section 5 uses those terms. |
| 18 | Unverified items; references | Done in parts 1-3 (NOTES.md, "What was checked"). Parts 4-5 cite [7], [10], [14], [33] only, all in the renumbered list. |
| 19 | Figures; t intervals; primary comparisons | Figures redrawn by `make_figures_r1.py` (W11) and captions rewritten (Figures 1-6). Cell means carry Student-t intervals in every table (E20). The six primary comparisons are named in Section 4.4 and referenced by number in Sections 5.2-5.6; intervals are per comparison, not adjusted. |

### Could

| # | Item | What changed, and where |
|---|---|---|
| 20 | Busy fleet, plume, local feedstock, lower relay bound at ISRU | Plume (M13) and local feedstock (M14) run and reported (Sections 5.2, 5.8). Busy fleet (M11) and a reduced relay at the plant (M9) not run; Section 7 says so. Relay 0.05 (part of M9) did not finish. |
| 21 | Table 4 and registration to an appendix | Done in part 3 (Appendix A, Table A1); the build moves Appendices A and B after the references. |
| 22 | Link budget | Not done. Section 7 states it, gives the geometric reason the real link should fall between our criteria, and discusses LCRNS's 17-43 % DTE figures against ours. |

## Errors

| Code | What changed, and where |
|---|---|
| E1 | Section 5.3: CV errors almost equal; the factor of two is in-sample. |
| E2 | Section 5.5, Table 8, abstract: all draws kept, 2,000 draws, [11, 370] M$, upper bound poorly determined. |
| E3 | Section 5.5: 1.25 % of draws buy nothing, 0.55 % beyond full coverage; Table 8 gives both shares for every option. |
| E4 | Section 5.2 paragraph 3: 307.5 t picked up vs 306.5 t dropped off in the year; backlog 221.6 t of which 204.2 t for the plant; 4.1 t less made ready; pad B receives nothing (2.2 t always linked). "Under way" explanation removed. |
| E5 | Section 5.6 paragraph 3, per fleet, from the analysis's seed-by-seed check. |
| E6 | Part 3 (Table 2, Section 3.5). |
| E7 | Section 5.1: "windows of about three days near each monthly maximum of Earth's elevation"; no window at the science site from January to late November 2028. |
| E8 | Section 5.7 paragraph 2: censoring explains the 1 km reversal. |
| E9 | Section 7, "Choices made during the study": Stage B at 0.2 and 0.8 now tests the coverage choice. |
| E10 | Table 9 ("none delivered"; counts when fewer than 20 seeds); Section 5.7. |
| E11 | Section 5.6, Section 6 paragraph 4: absolute peaks; the teleoperated fleet's peak is the higher one. |
| E12 | Figure 6 (absolute peaks, no "always" point); caption without the unit error. |
| E13 | Section 6 paragraph 2. |
| E14 | Sections 5.5 and 7: 45 M$/yr, 450 M$ over 10 years, Modelled in [33]. |
| E15 | Table 8: Δp interval for every row, every draw kept; "beyond 1" where an option beats full coverage, with its share (strategic + 1 rover: 42 %). |
| E16 | Section 5.3: "Most of the fall happens by coverage 0.2, and a slow tail follows". |
| E17 | Section 5.4 paragraphs 2-3 and Figure 4: tonnage 113 / 508 / 536 / 543 t by start year; 41,026 rover-hours waiting in 2028 against 21,362-34,201 in other years. The referee was right that it is the calendar, and we now show how: one route sample on the regolith haul from the oxygen plant sees Earth at no hour from January 2028 to July 2029 and holds 79 % of 2028's stranded rover-hours; a swap test (demand fixed, start year varied, eight seeds) makes every seed collapse in 2028; Earth's bearing at high elevation moves with the libration pattern (results/E21_strategic_years.json, experiments/phase4/strategic_years.py). Discussion and Conclusions state the consequence for the strategic rule. |
| E18 | Section 5.4 cites the paired effects, not Table 7, for the delay claims. |
| E19 | Section 5.2: "every fleet that needs a link to drive"; strategic loses 107 t (20 %). |
| E20 | All tables: Student-t cell intervals (`table_E21_cells_r2.csv`). |
| E21 | The validation sentence left the abstract (W1); Section 3.6 and Appendix A give mean absolute 0.028, largest −0.123, two points zero in both. |
| E22 | Section 5.5 last sentence; Section 4.4. |
| E23 | Part 3; Section 5.8 reports the periodic DRM-0 and RC 3.1 cases. |
| E24 | Part 3 and NOTES.md (references renumbered and completed). |
| E25 | Abstract: "ten relay coverages from 0.1 to 1.0" (filled from the data). |
| E26 | Parts 4-5 and the build: `&#8239;%`, M$, "Stage A". |

## Overclaims

| Code | What changed, and where |
|---|---|
| O1 | Section 5.2, Table 6, abstract, Section 6 paragraph 1, Section 8. |
| O2 | Section 5 opening, Section 5.2, Section 6 paragraph 2, Sections 7-8, abstract. |
| O3 | Sections 5.2 and 5.5 condition rover claims on slack; one rover not significant at 0.2, 0.5, 0.8; Section 7: no busy fleet tested. |
| O4 | Sections 5.4-5.5, Section 6 paragraph 3, Section 8 (see Must 6). |
| O5 | Abstract and Section 5.5 label the price; Section 6 adds that a relay serves many users and that operators and energy are excluded. |
| O6 | Section 5.6 and Figure 6: absolute peaks; why the ratio misleads (mean demand 0.22 → 0.13). The untested "does not depend on that rule" is replaced by the Stage A2 result. |
| O7 | Section 5.7 paragraph 3 (see Must 9). |
| O8 | Section 7 "Geometry, not radio": "we expect", with the reason. |
| O9 | Section 6 paragraph 1 opens with the measured statement (one site, 90 % of the lost tonnage). |
| O10 | Part 3 (Section 3.6). |
| O11 | Section 8: findings and recommendations each carry their conditions. |
| O12 | Section 8: "checked against analytic and earlier results"; Availability says "checks". |
| O13 | Abstract keeps "We found no published analysis". |
| O14 | Section 5.2 (E4), Section 5.4 (E17, calendar not chance), Section 5.5 (operators cannot bind; one/two/three rovers within noise). |

## Statistics and method

| Code | What changed, and where |
|---|---|
| S1 | Sections 4.4 (part 3), 5.3, 5.7; completion beside every p90 (Tables 6-9). |
| S2 | Medians, geometric-mean ratios, Wilcoxon throughout Section 5. |
| S3 | Section 5 opening; year-blocked intervals; Figure 4; Section 7. |
| S4 | 2,000 draws, all kept (Section 5.5, Table 8). The coverage targets keep the analysis's 400-draw law bootstrap, stated in Table 7 and Section 7. |
| S5 | Section 5.3 (see Should 16). |
| S6 | Table 7: "≤ 0.1" where the target lies below the lowest relay level; Section 5.3 names the non-monotone cells (strict 0.7 → 0.8, reference mix 0.8 → 0.9). |
| S7 | Section 5.7 (see Must 9). |
| S8 | Stage B at 0.2 and 0.8 (Section 5.5, Table 8). |
| S9 | Stage E plume case (Section 5.8): no measurable change. |
| S10 | Stage D (Section 5.8): the real Sun leaves throughput and DTE cells unchanged but lengthens urgent delay at relay 0.5 about fivefold (delivered-item ratio 5.41 [4.21, 6.95], censored 4.90 [3.00, 8.01]). Section 6 and Section 7 qualify the coverage targets and the price accordingly. |
| S11 | Section 5.6 and Stage A2 (see Must 7). |
| S12 | See Must 8. |
| S13 | See Should 13. |
| S14 | See Should 14. |
| S15 | See Should 15. |
| S16 | Section 5 opening; primary comparisons numbered. |
| S17 | See Must 10. |
| S18 | Section 5.5 (three or four operators on duty); Table 5 counts the 260 duplicated years (part 3); Section 7 keeps the never-linked filter. |

## Missing analyses

| Code | Status |
|---|---|
| M1 | 0.6 and 0.7 done; 0.05 did not finish (Section 4.2). |
| M2 | Done (Table 6, Figure 2, Section 5.2). |
| M3 | Done (year-blocked intervals, Figure 4). |
| M4 | Done (completion share, censored p90). |
| M5 | Done (all draws, 2,000; paired strategic-minus-rover; log-ratio and Wilcoxon effects). |
| M6 | Done (look-ahead in Stage B; 0.2 and 0.8). |
| M7 | Done (Stage A2). |
| M8 | Done (Stage E relay cases). |
| M9 | Partly: relay 0.05 did not finish; no reduced availability at the plant. |
| M10 | Not done. |
| M11 | Not done. |
| M12 | Done (Stage E). |
| M13 | Done (Stage E). |
| M14 | Done (Stage E). |

## Writing

| Code | What changed, and where |
|---|---|
| W1 | Abstract ~240 words, conditions on the relay and price claims. |
| W2 | Discussion openings are findings with conditions. |
| W3 | "goes a long way", "largest single number", "puts a number on it", "the practical points are three", "about a quarter" and the vague comparatives are gone; numbers instead. |
| W4 | Words for mixes, policies and criteria in prose and tables; code paths, file names, md5 and "byte for byte" only in Availability. |
| W5 | Throughput break-even paragraph reduced to one sentence. |
| W6 | Promissory sentences replaced by the Stage A2 and Stage D results. |
| W7, W8, W10 | Parts 1-3. |
| W9 | Terms used in Section 5 (censored delay, completion share, geometric-mean ratio, Wilcoxon, look-ahead) are defined in Section 4.4 and Appendix B. |
| W11 | Figures redrawn; captions rewritten (Figure 1 says which direction is drawn; Figure 3 log-scale t intervals and no law; Figure 5 paired differences with intervals; Figure 6 absolute peaks against staff). |

## Things the revision found that the report did not anticipate

- The real Sun (Stage D) lengthens urgent delay at relay coverage 0.5 about fivefold while leaving throughput
  unchanged; the coverage targets and the price are therefore for the fixed night share (Sections 5.8, 6, 7).
- One extra rover's equivalent coverage (0.12 [0.01, 0.42]) has a bootstrap interval that excludes zero although its
  paired tests do not (t interval −19.6 to 1.4 h; Wilcoxon p = 0.23), and on the censored measure its point estimate
  goes the other way (ratio 1.52 [0.46, 5.02]). The text reports the value as weakly determined.
- With a relay, the strategic step's benefit is in the delay of delivered items, not in completion or censored delay.
- **The strategic rule's free second chance (new Stage F, Section 5.4).** Checking the rule after round 1, we found
  that it treats two kinds of dark point differently. An intervention drawn on a route sample that never sees Earth
  in 2028–2031 makes the job impossible, so dispatch refuses it and draws again later at no cost (138 times a run
  under DTE). A long but finite wait is accepted and waited out. On 28 of the 70 main-network legs, every leg to or
  from the oxygen plant among them, the first behaviour is what lets the strategic fleet haul feedstock. Stage F
  brackets it. If the rover is instead held where it stopped until the year ends, the strategic fleet delivers 42 t a
  year, 265 t less than the strict fleet. A bounded rule (the "middle rule" the round-1 Discussion proposed, at four
  bounds from 24 to 720 h) either refuses those routes and matches the look-ahead (307–309 t, no oxygen-plant haul),
  or leaves them to the re-draw and still collapses in 2028, now because deferred items fill the 40-item auction pool.
  The abstract, Sections 5.4, 6 and 8, Table 4 and Table 5 are revised, and Section 7 states both features of the rule
  and the pool limit. The relay results are unaffected: with a relay no point is never linked.
