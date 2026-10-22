# Referee report, round 1

**Manuscript:** "What Earth's Horizon Costs a Lunar Base: Terrain-Masked Communication Windows in South-Pole Cargo Logistics" (R-1, `paper/r1/paper.html`, preprint draft of October 2026)
**Date:** 2026-10-22
**What I checked:** the assembled paper and its five figures against `results/table_E21.csv`, `table_E21_effects.csv`, `table_E21_breakeven_delay.csv`, `table_E21_breakeven.csv`, `E21_fit.json`, `fig_E21_operator_demand.csv`, `E21_demand_by_dest.csv`, the raw `E21a/b/c` CSVs, `lunarsim/comms.py`, `lunarsim/engine.py` (delivery and delay bookkeeping), `experiments/phase4/run_phase4.py` and `analyse_e21.py`, the prior-art note, `paper/r1/NOTES.md` and `.team/reports.md` B-40 to B-43. All numbers I quote below came from those files. Where I recomputed something, I say how. Only light pandas reads and one 2,000-draw re-run of the break-even bootstrap were used; no simulation was run.

---

## 1. Summary and recommendation

**What the paper claims.**
1. It gives terrain-masked Earth-link windows for 2028–2031 at 7 sites, 10 pads and 182 routes of one Connecting Ridge layout (SPICE plus LOLA terrain out to 300 km), checked against JPL Horizons and the LOLA 60 m Earth-visibility map. The oxygen plant never sees Earth, and 101 of the 182 routes are never linked from end to end.
2. With direct-to-Earth (DTE) links only, a fleet that needs a link delivers 42 % less cargo, and 90 % of that loss is cargo bound for the oxygen plant. Extra rovers and a 10 m mast recover nothing, while any relay (p = 0.1) or full autonomy restores the lost tonnage.
3. Urgent delay falls along a long curve as relay coverage grows. A strict supervised fleet needs p ≈ 0.62 to get within twice its full-coverage delay; under the strategic policy p ≈ 0.09 is enough.
4. At p = 0.5, one extra rover is worth 0.18 of relay coverage, which prices 0.1 of coverage at 26 M$/yr. The strategic autonomy step is worth more than a rover.
5. Link windows bunch operator demand: under DTE the teleoperated fleet's peak-to-mean ratio is 36, against 15 at full relay coverage.

**Recommendation: major revision.**

The data product (Sections 3.1–3.6) is careful, well validated and new in the form given. The core result also stands: one never-linked work site makes a link-dependent fleet lose its cargo, and a relay or autonomy fixes it while rovers do not. The revision is needed for four reasons:

- **Misexplained or wrongly bounded results.** Several headline numbers are misexplained or carry intervals that are too narrow: the price interval, the "cargo still under way" explanation, the stranding spread, the cross-validation claim, and the identity of full relay with "always".
- **The throughput headline depends on the demand model.** It is mostly arithmetic on an assumed 200 t/yr feedstock flow to the one dark site, and the paper does not say so.
- **The break-even and "autonomy before rovers" are not established.** Both rest on a paired effect whose t-interval includes zero, and the conclusion names a policy (look-ahead) that stage B never tested.
- **The urgent-delay metric is censored.** Items that are never delivered drop out of it. This explains several sign reversals in the sensitivity tables that the text reads as physics.

Most of the fixes are reanalysis of data already in hand. The new runs that are needed are cheap (Section 5).

---

## 2. Errors

Each entry gives the location, what is wrong, the correct value and its source.

| # | Location | What is wrong | Correct value | Source |
|---|---|---|---|---|
| E1 | §5.3, para 1 | "Hyperbolic and power laws fit the cells about twice as well as an exponential one (cross-validated over seeds)". | The cross-validated RMSEs are almost equal: strict 0.708 / 0.708 / 0.712 (hyperbolic / power / exponential); default 0.653 / 0.653 / 0.660; teleop 0.727 / 0.727 / 0.730. The factor of two is **in-sample** RMSE (strict 0.12 against 0.25). The form choice by CV is therefore arbitrary (differences under 2 %). | `E21_fit.json` `laws.*.delay_prio1_p90_h.cv_rmse_log` and `insample_rmse_log`; B-43 §2 says "in-sample" |
| E2 | Abstract; §5.4, para 2 | The price "26 M$ [11, 139]" per 0.1 coverage per year. The interval was computed after **discarding** every bootstrap draw in which one rover bought nothing (Δp ≤ 0) or beat full coverage (Δp = ∞). That is 2.5 % of the draws, both tails. | The interval must keep those draws (Δp ≤ 0 gives an unbounded price; Δp = ∞ gives a price near 0). The paper's own Δp interval [0.019, 0.41] implies an upper bound of about 4.5 / 0.019 ≈ 240 M$. My re-run with 2,000 draws gives [11, 225] when the draws are dropped and **[11, 355]** when they are kept. The upper bound is unstable and should be reported as "above 200 M$, poorly bounded". NOTES item 11 asked for exactly this ("if > 0 the upper CI bound is unbounded; say so"). | `analyse_e21.py` `breakeven()`: `per01 = [... if np.isfinite(x) and x > 0]`; `E21_fit.json` `share_draws_one_ltv_not_positive` = 0.025; `delta_p_one_ltv_ci95` |
| E3 | §5.4, para 2 | "in 2.5 % of the bootstrap draws one rover bought no delay at all". | Of that 2.5 %, half (1.25 %, `share_beyond_full_coverage`) are draws where one rover was worth **more than full coverage**. Only about 1.25 % bought nothing. | `table_E21_breakeven_delay.csv` row "+1 rover": `share_beyond_full_coverage` = 0.0125 |
| E4 | §5.2, para 2 | "The remaining 21.5 ± 7.7 t is cargo for linked sites that is still under way at the end of the year, because rovers wait for Earth on their way to it." | Almost none of it is under way. Under DTE (strict fleet), 307.5 t was picked up against 306.5 t delivered in the year, so about 1 t was in transit. About 17 t was **never picked up** (backlog 221.6 t minus 204.2 t for ISRU). About 4 t of return cargo was never generated (ready mass 529.8 t against 534.0 t under "always"). One destination in the list, pad B (2.2 t), is linked only 28.6 % of the time and its legs less. | Raw `E21a_comms_autonomy.csv`: `delivered_kg` (booked at pickup, `engine.py` l. 1039–1050), `delivered_t_in_year`, `backlog_kg`, `ready_kg`; `E21_fit.json` `throughput.delivered_t_by_dest` |
| E5 | §4.5 "Operator demand…"; §3.7 last para; Fig. 5 | "relay coverage 1.0, whose operations equal those of the always-linked cell". | False for the teleoperated fleet, which is the fleet used for the burst headline. The urgent p90 differs in 8 of 20 seeds (by up to 15.5 h), delivered mass differs by up to 2.4 t, and unmet operator waits are 32.4 against 11.4. The other five mixes are identical. The cause is the admission rule (§3.7, Table 5). The §3.7 statement holds for the P2-default comparison it was tested on; the general claim in §4.5 and in B-43 ("equals 'always' exactly in every throughput and delay metric") does not. | Raw `E21a`: `teleop_4s` always against dte+relay 1.0, per seed; column `unmet_operator_waits` |
| E6 | Table 2 caption ("Gaps are the intervals between windows"); §3.5 ("gaps of up to 7,929 h (330 days)") | For SCI_1, PAD_A at 2 km and PAD_B at 3 km, the "max gap" is the dark stretch from the **start of the series**: the first window opens on day 330.4, 358.1 and 493.2 respectively. It is censored at 1 January 2028, so it is not an interval between two windows. After it, these points are linked about 3 days every month (largest gap between windows about 26 days for SCI_1). | State that the value is censored at the series start and give the largest gap between windows separately. | `earth_link-v1.json` read with `EarthLink.windows()`; `summary()` `max_gap_h` |
| E7 | §3.5 ("at rare moments of peak libration"); §5.1 ("only in the weeks of largest libration") | SCI_1 has 42 windows (mean 70.7 h) from late November 2028 on. PSR has 54, one per month through the whole series (mean 80 h). These are monthly windows of about 3 days, not rare moments and not weeks. | "for about three days near each monthly maximum of Earth's elevation; SCI_1 not at all from January to late November 2028". | as E6 |
| E8 | §5.7, para 1 | "Urgent delay depends on it more, as expected from shorter windows." | Holds only at 0.5 km pads (default fleet: +21 h [8, 34] for centre+0.5°, +82 h [44, 120] for centre+2°). At 1 km pads the stricter criteria give **lower** mean p90: default 380 → 235 → 305 h, teleop 662 → 228 → 318 h; paired effects −145 [−433, 143] and −75 [−366, 217] (default). The likely cause is censoring (S1): more never-linked legs remove more urgent items from the statistic. | `table_E21_effects.csv` family `criterion_vs_any_part` |
| E9 | §7, "Choices made during the study" | "Both are reported with their alternatives (Table 10)." | Table 10 reports alternatives to the deferral limit only. No alternative to the stage B coverage (p = 0.5) is reported anywhere. | Table 10; Table 6 |
| E10 | §4.3, last sentence | "the tables give the count" (of seeds with a finite urgent delay). | No table gives it. Table 10's 3 km rows show "–" without explanation; `n_valid` = 0 there, meaning no urgent item was delivered in any of the 20 seeds. | `table_E21.csv` `n_valid` |
| E11 | §6, "Operations planning…" | "with teleoperation the bunching is strongest". | Figure 5 shows the opposite for the metric used: the Phase-2 mix's peak/mean ratio is higher (83 under DTE, 42 at full relay) than the teleoperated fleet's (36 and 15). In absolute peak the teleoperated fleet is higher (4.6 against 2.1). Say which. | `fig_E21_operator_demand.csv` |
| E12 | Figure 5 caption and plot | The caption gives the y-axis unit as "(operators)", but a ratio is dimensionless. The plot includes an "always" point, although §4.5 says "always" books demand differently and must not be the comparison point. | Remove the unit; drop the "always" point or mark it as not comparable. | `analyse_e21.py` `operator_demand()` docstring |
| E13 | §6, para 2 | "NASA's LCRNS reference numbers (one relay 80–86 % a year [10], Section 2) fall on the flat part of our curve". | 80–86 % is DTE **plus** relay. §3.7 itself converts it to a relay-alone p of about 0.6–0.7. There the strict fleet's p90 is about 30–35 h, roughly twice the full-coverage value, which is right at the paper's own 2× threshold (p = 0.62). That is not the flat part. The cross-reference should be Section 2.2. | §3.7, last para; Table 8; `table_E21.csv` |
| E14 | §4.5 against §5.4 and §7 | The rover cost is "Modelled in [33]" in §4.5 but "v3's Assumed vehicle costs" in §5.4 and §7. | One basis and one flag. NOTES gives it as the `entities.py` comment, Modelled in v2 [33]. | `paper/r1/NOTES.md`, last bullet |
| E15 | Table 9, row "strategic step + 1 rover" | "0.98 [0.69, 0.99]": 44 % of the draws were beyond full coverage and were dropped before the interval was taken. The "Coverage gained" column has no intervals; +3 rovers is +0.03 [−0.12, 0.29]. | "≥ 0.69; beyond full coverage in 44 % of draws". Add Δp intervals for every row. | `table_E21_breakeven_delay.csv`: `share_beyond_full_coverage` = 0.4425; `delta_p_ci95_lo/hi` |
| E16 | §5.3, para 1 | "Coverage brings it down steadily rather than at a knee". | The strict p90 falls 446 → 136 → 60 h between p = 0 and 0.2 (−87 %), then 60 → 17 h over 0.2–1.0. That is a knee near 0.2 followed by a slow tail, which is what §4.5 itself says ("the slow decline between p = 0.2 and 1"). | `E21_fit.json` `laws.supervised_strict.delay_prio1_p90_h.cell_mean` |
| E17 | §5.5, para 1 | "The spread between seeds is large, because one hazard drawn on a rarely linked stretch can hold a rover for most of the year." | The spread in strategic DTE tonnage is the **start year**. All five 2028 replications deliver 56–183 t (mean 113 t); the other fifteen deliver 492–574 t (2029: 508, 2030: 536, 2031: 543). In 2028, SCI_1 has no link until day 330 and PAD_A at 2 km none until day 358 (E6). The supervised wait itself is not very spread (29,927 ± 3,794 h). | Raw `E21a` grouped by `start_year`; link file |
| E18 | §5.5, para 1, last sentence | "(Table 8)" is cited for "both well ahead of the strict policy in urgent delay". | Table 8 gives coverage targets, not delays. The evidence is Figure 3 / `table_E21.csv` (p = 0.1: 27.5 and 33.7 h against 135.6 h). | — |
| E19 | §5.2, para 1; §8 | "Every fleet that needs a person for some of its driving loses about the same amount" and "a fleet that needs operators on Earth delivers about 42 % less". | The strategic fleet also needs a person (for interventions) and loses 107 t (−20 %), not 225 t. Say "every fleet that needs a link to drive". | Table 7 |
| E20 | §4.5, para 1 | Cell intervals are "1.96 standard errors" while the effects use Student-t on 19 degrees of freedom. | Use t for both. The cell intervals are about 6 % too narrow. | `experiments/phase3/fit_law.py` `cell_means` |
| E21 | Abstract, sentence 6 | "and computed the published map's way our fractions match the 60 m LOLA Earth-visibility map to −0.004 on average over 17 points". The syntax is broken, and the signed mean hides the scatter. | Report the mean absolute difference 0.028 and the largest, −0.123; note that 2 of the 17 points are 0 = 0. | Table 4 |
| E22 | §4.5, "Break-evens in throughput" | The method is described in full, but its results are never reported, and they are degenerate. The relay equivalent of p = 0.9 is 0.105; +2 rovers is "0.09 rover-equivalents"; +3 rovers gives a relay price of 0. | Say that the throughput break-even is undefined because throughput saturates at p = 0.1 and rovers add nothing. Drop the paragraph or reduce it to that one sentence. | `table_E21_breakeven.csv` |
| E23 | §2.2 against Table 5 | The relay gap is taken from DRM-0 (one satellite, 784-min orbit, 460-min gap), while §2.2 describes the Reference Constellation 3.1 orbit (period about 30 h). | Say why the DRM-0 gap stands for the RC 3.1 constellation, or derive the gap from RC 3.1. | [10], [18]; `comms.py` `DEFAULT_RELAY_GAP_H` |
| E24 | References | [35] is first cited after [36]–[38] (§3.2), so the list is not in order of first citation. Several entries carry internal pointers such as "(v3 reference [29])" and "(v3 [14])". [17] has no authors. [20] cites Wikipedia for a NASA schedule statement. [29], [30] and [32] are incomplete (no titles or full author lists). | Renumber; remove the internal pointers; complete or replace these entries. | `paper/r1/NOTES.md` "What I could not verify" |
| E25 | Abstract | "a relay of coverage 0.1–1.0" | The grid has no levels at 0.6 and 0.7. Say "eight levels from 0.1 to 1.0", or add the missing levels (M1). | Table 6 |
| E26 | Units and formats throughout | "M$" and "$45 million"; "59%" and "42 %" in the same abstract; "centre+0.5deg" in Table 10 against "centre +0.5°" elsewhere; "Stage A", "stage A" and "Stage-A". | Pick one style for each. | — |

**Unverified statements that must be checked before submission** (the NOTES already flag these; the paper prints them as fact):
- the "18.6 years" of the AVGVISIB map (the label's START/STOP fields read 2009–2013);
- Jun et al.'s station "on the Connecting Ridge";
- the LTV quotes "flawless high-bandwidth comms" and "6 km per 24 h";
- the Sun "within about 1.5°" of the horizon, which is cited to [14], where it is flagged Assumed (use the 1.54° lunar obliquity and a primary source);
- the Acton 1996 bibliographic details.

---

## 3. Overclaims and unsupported statements

**O1. The −42 % headline rests on a demand assumption, and the paper presents it as a fleet result.**
- Of the 534 t/yr made ready, 500 t is two bulk regolith flows (`bulk_kg` = 500,000 in every run), and 200 t/yr of that is hauled from CONSTR to the one site that never sees Earth.
- So the headline is close to arithmetic: 204 / 532 ≈ 38 %. If the plant dug its own feedstock, as many ISRU concepts assume, the loss would be about 25 t out of about 330 t, roughly 8 % (M14 would measure it).
- The result that does not depend on that choice is the cargo that arrives by lander. Non-bulk deliveries fall from 29.3 t to 9.4–9.8 t, **about two-thirds lost** (`delivered_nonbulk_kg`: always 29,282 kg against DTE 9,400 kg, strict fleet).
- At 3 km pads under DTE, *no* lander cargo moves at all: every pad leg is dark (Table 3), the 296 t delivered is CONSTR→BASE regolith, and no urgent item is delivered in any seed.
- The abstract and §8 should report the cargo-class split and state the feedstock assumption next to the 42 %.

**O2. "Any relay restores the cargo" / "a relay in view 10 % of the time restores 99 %" depends on three conditions the abstract does not state.**
- The relay is assumed to see every route point (Assumed), including ISRU, which sits in a hollow 139 m below BASE (`sites.json` z = 1,818.5 m against 1,957.6 m).
- Throughput is a one-year sum with no deadline.
- The fleet is almost idle: utilisation 2.8 % (default, always linked) and 3.3 % (strict, DTE).

Under those conditions any nonzero access is enough. Say so wherever the claim appears (abstract, §5.2, §6, §8).

**O3. "So the loss is not a shortage of rovers" and "rovers are not [substitutes]" hold for a fleet that is idle 97 % of the time.**
- Extra rovers cannot add throughput to such a fleet.
- In delay, the one test where a rover could matter (p = 0.5, strict) gives a paired effect of −9.1 h [−19.6, +1.4], which does not exclude zero.
- The claim should be conditioned on fleet slack. A busy-fleet case would test it (M11).

**O4. "The strategic step … is worth more than a rover" (§5.4, §6) and "buy autonomy before rovers when links are scarce, provided the rovers look ahead" (§8) are not supported as written.**
- (a) The difference was not tested. Δp is 0.29 [0.20, 0.41] for the strategic step against 0.18 [0.02, 0.41] for one rover. In a paired bootstrap on the same draws (my re-run, 2,000 draws) the difference is positive in 79 % of draws, 95 % interval [−0.15, +0.32].
- (b) Stage B tested the plain strategic policy, not strategic+avoid, so "provided the rovers look ahead" names a policy that was not in the comparison.
- (c) Where links are scarcest (DTE only), the look-ahead policy delivers the same tonnage as strict (+0.4 t [−0.1, 0.9]) and its p90 is not better (+256 h [−86, 598]). The plain strategic policy delivers more but strands rovers for about 30,000 h a year and collapses in 2028 (E17).

So the advice holds, at most, "once some relay coverage exists". Rewrite §6 para 3 and §8 accordingly.

**O5. The relay price is local and its interval is understated.**
It is valid only at p = 0.5, for the strict fleet and this demand. The interval must be corrected (E2), and the rover cost leaves out operators and energy. The abstract states the price without "at relay coverage 0.5". Add that qualifier, and in the Discussion say that a relay serves many users while the rover purchase serves one base.

**O6. The operator-burst claim (abstract, §5.6, Figure 5 title "Weak links bunch operator demand") rests on a ratio whose denominator halves.**
- Teleoperated fleet: mean linked demand falls from 0.223 to 0.127 operators while the peak rises from 3.37 to 4.6. Most of the 15 → 36 change in the ratio is the lower mean, because less work is done.
- Phase-2 mix: the peak does not change at all (2.12 against 2.13, −0.02 [−0.30, 0.27]); the 42 → 83 ratio is entirely the lower mean.
- The largest absolute peak for teleop is at p = 0.1 (5.5 operators, over the 3 on duty in 20 of 20 seeds), not under DTE.
- "The bunching itself does not depend on that rule" (§5.6) is untested: a hard limit would spread admissions out.

Report absolute peaks, seeds over staff, and the share of linked hours with demand above the staff.

**O7. "The deferral limit matters just as much" (§5.5) overstates the result.**
The 380 → 2,319 h change has a paired interval of +1,939 h [−184, +4,062], which includes zero. At DTE, the 12, 24 and 72 h limits are indistinguishable. At relay 0.8, removing the limit *lowers* urgent delay (−5.6 h [−11.0, −0.2]). Say what the data show: no limit is risky under DTE, and a short limit costs a little delay when coverage is high.

**O8. "A real link budget would sit between our criteria" (§7) is untested.**
At 0–6° elevation over a ridge, terrain multipath and a small rover antenna could make a real link worse than centre+2°. Write "we expect…" and give the reason (the Fresnel radii of §3.4).

**O9.** "Where a site is matters as much as how it is served" (§6) is a comparison the paper does not make. Replace it with the measured statement: one site explains 90 % of the throughput loss in this layout.

**O10.** "A surface-level map therefore understates what a rover antenna sees at a crest" (§3.6) is shown at BASE and a few crest points on one DEM. Say "at our crest points".

**O11. The Conclusions generalise from one case to "base planners".**
The evidence is one layout, one demand phase that is 94 % bulk, one six-rover fleet at about 3 % utilisation, plume off, a 10 km mast range (Assumed) and four calendar years. Keep the recommendations, and state each one's condition.

**O12.** "Verified" engine (abstract, contribution 2). Here verification means regression identity with earlier versions, not validation against operations. Planetary-ops readers will read "verified" as "validated". Define the term or replace it.

**O13. Novelty is consistent with the prior-art verdict** ("partly covered; the specific coupling looks new, Medium confidence"), and §2.5 hedges it correctly. The abstract states the gap flatly ("what the gaps cost a cargo fleet is not [published]"). Add "we found no…". Contribution 1, "We found no published dataset that gives windows along routes", is acceptable: VIPER and Otten computed them but did not publish them.

**O14. Causal language without evidence:**
- "because rovers wait for Earth on their way to it" (E4);
- "because one hazard drawn on a rarely linked stretch" (E17);
- "probably because operator demand grows with the fleet (the peak … rises from 1.3 to 1.6 operators)" (§5.4). With 4 operators on duty for 9 vehicles, a peak of 1.6 cannot bind. The +1 / +2 / +3 differences are also not significant (paired −9.1 [−19.6, 1.4], −9.1 [−18.5, 0.3], −1.9 [−10.3, 6.5]), so "a third gives most of the gain back" is probably noise. Say so.

---

## 4. Statistics and method

Each item is marked **[text]** (must be addressed in the manuscript), **[run]** (needs an analysis or run, see Section 5) or **[ok]** (an acceptable limitation if stated as below).

**S1. Censoring of urgent delay [text + run].**
- The engine books a delivery, and its delay, at **pickup** (`engine.py` l. 1039–1050, `_record_delivery`).
- So the urgent p90 includes items dropped off after the year ends but excludes every item never picked up: ISRU-bound urgent items under DTE, and every lander item at 3 km pads (`n_valid` = 0).
- Throughput counts only drop-offs inside the year. The two metrics use different inclusion rules.
- Consequences: stricter criteria at 1 km "improve" delay (E8); the share of urgent items within 24 h is lower at p = 0.1 (0.42, default) than under DTE (0.55); and DTE delays understate the cost.

Report, for every cell, the share of ready priority-1 items delivered within the year. Either treat undelivered items as censored at the year end (a censored p90) or show the p90 only alongside the completion share.

**S2. Heavy tails in p90 [text + run].**
- Per-seed DTE p90 for the default fleet ranges from 2 h to 3,054 h. The mean is 380 h, the median 284 h, and the mean without the largest seed 239 h.
- Student-t intervals on raw hours misbehave here. The teleop DTE effect is +633 h [−25, 1,291] even though 19 of 20 seeds increase.
- Use paired log-ratios (a geometric-mean ratio with a t-interval on the log scale) or a Wilcoxon / sign test for the main delay effects, and report medians beside means.

**S3. The calendar is a block, not noise [text + run].**
- The 20 seeds are 4 start years × 5 replications, and differences between years are large and deterministic: strict DTE p90 is 407 / 225 / 161 / 989 h for 2028–2031; strategic DTE tonnage is 113 / 508 / 536 / 543 t.
- Intervals that treat seeds as independent mix the calendar with the stochastic spread, and they rest on only four calendar draws.
- Report the key cells per start year, and either block on year or say plainly that the intervals include calendar variation over 2028–2031 only.

**S4. Bootstrap [text].**
- 400 draws leaves 10 draws in each 2.5 % tail. That is thin for the price bound, which moves from 139 to 225 M$ between 400 and 2,000 draws.
- Dropping non-finite draws biases intervals (E2, E15). Fix the price interval, and raise the draw count to at least 2,000; the analysis takes minutes.

**S5. The delay law [text].**
- The CV differences between forms are under 2 % (E1), so the choice of form is arbitrary.
- The law-based coverages are also bounded by the functional form. With a ≥ 0 and c > 0 (the bounds in `fit_form`), the hyperbolic form cannot give p(2×) above (1 − c)/2 < 0.5 or p(1.5×) above (2 − c)/3 < 0.67. The power law with g ≤ 1 behaves the same way. The reported law values (strict 0.44 [0.29, 0.49] and 0.61 [0.46, 0.66]) sit on those bounds.
- In Figure 3 the strategic power law (g = 0.39, c ≈ 0) gives 42 h and 32 h at p = 0.1 and 0.2, where the cells are 27.5 h and 23.0 h, and then passes below the cells at 0.3–0.5 (27 / 24 / 22 h against 31 / 27 / 27 h). The fit is set by the DTE point.
- The law is descriptive at best. Say that the chosen family cannot represent the slow tail; drop the "Law-based" column of Table 9 or fit p > 0 only; and remove the strategic curves or refit them.

**S6. Model-free inversion [ok if fixed].**
The method is sound and better than the law. But the headline p(2×) = 0.62, p(1.5×) = 0.81 and every stage B equivalent (0.53–0.79) are interpolated across the empty 0.5–0.8 interval; add 0.6 and 0.7 (M1). For the strategic fleets, the 0.09 / 0.10 targets are interpolated between the DTE cell (where the policy strands rovers) and p = 0.1. Report them as "≤ 0.1, the lowest level tested". The non-increasing envelope hides real non-monotonicity (default p90 is 20.9 h at 0.8 and 26.2 h at 0.9); mention it.

**S7. Deferral rule chosen during development [text; ok otherwise].**
The disclosure is good (§3.7, §7). The text must add that the effect changes sign with coverage (O7) and that 12, 24 and 72 h are indistinguishable under DTE.

**S8. Stage B coverage chosen after stage A [ok, with qualifier].**
The disclosure is adequate. Because the price headline depends on p = 0.5, label it "at p = 0.5" everywhere. A second stage B coverage (M6) would turn a disclosed choice into a tested one.

**S9. Plume off [ok].** It is stated in §5 and §7. One paired check with the v3 keep-out on (M13) would show whether stand-downs inside short link windows interact.

**S10. Fixed night share [text; ok otherwise].**
§1 and §7 say E21 does not test the Sun–Earth overlap. The text should add that the engine's night starts at hour 0 of *every* run, whatever the start year. Its overlap with the real Earth windows is therefore arbitrary and differs between years, which contributes to the calendar variance of S3. B-44's real-Sun option exists; stage D should use it.

**S11. Operator admission rule [text, and run if possible].**
- The admission check sees only demand linked at that moment, so the pool is soft. For the teleop mix the hourly peak is 4.6 operators under DTE (above the 3 on duty in 18 of 20 seeds) and 5.0–5.5 at p ≤ 0.5 (20 of 20 seeds); unmet operator waits rise from 11 to 36–110.
- So the teleop rows of Tables 7–8, its curve in Figure 3 and Figure 5 are optimistic, and the "full relay = always" identity fails for that mix (E5).
- The supervised and default results are unaffected: the default fleet's mean peak is at most 2.8 and no seed exceeds 3 operators, and the stage B fleet peaks at 1.6 against 3–4.
- The text must say this. A rerun of the teleop cells with B-45's hard limit is cheap (M7).

**S12. The relay sees every route point [text].**
This assumption is load-bearing for "any relay restores 99 %", because the site it rescues is in a hollow. State it in the abstract and §8, not only in §1 and §7. Bound it cheaply with p = 0.02 / 0.05, or with a relay availability at ISRU reduced by half (M9).

**S13. The relay process [text + run].**
- The process is exponential up/down, independent of DTE, with a gap taken from DRM-0. Independence is reasonable for an orbit's phase, but the real gap is close to periodic, and exponential gaps give occasional 20 h+ outages.
- At p = 0.1 the mean up period, 0.85 h, is shorter than many teleop drives, so the shape of the low-coverage curve is set by the assumed gap mean as much as by coverage.
- Reconcile DRM-0 with RC 3.1 (E23), and add a gap sensitivity (M8).

**S14. The 2.5 m antenna [text; run is cheap].**
- Justify 2.5 m with a vehicle source; none is cited.
- At BASE the fraction is 0.384 at 0 m against 0.593 at 2.5 m, so window lengths at crest points and pads depend strongly on antenna height.
- The ISRU = 0 headline is robust: 0 on the map, at 0 m and at 2.5 m.
- Say both, and give one other height (M10).

**S15. Intervention rate and uniform placement [text; run is cheap].**
The strategic results hinge on the Assumed hazard model (0.10 per km without tables) and on placing interventions uniformly. Hazards are likely to cluster in the same hollows and slopes that are dark, which would make strategic driving worse. Say so, and sweep the rate ×0.5 and ×2 (M12).

**S16. Multiplicity [text].**
`table_E21_effects.csv` holds 810 effects. Name the 5–6 primary comparisons and say that the intervals are per comparison and not adjusted.

**S17. Primary metrics not reported [text].**
§4.4 lists cost per landed kg, the 24 h service share and mean delay as primary, and none appears in §5. Cost per landed kg is non-monotone in coverage (default 16.4k $/kg at p = 0.1, 31.0k at p = 0.5, 16.6k at p = 1.0), which needs either an explanation or demotion to secondary.

**S18. Small confounds [text].**
- The operator count rises with the fleet: max(3, ⌊n/2⌋) adds an operator at +2 and +3 rovers. It does not bind (peaks ≤ 1.6) but should be stated.
- Stage B shares four cells with stage A (strict and strategic, +0 rovers, no mast, at DTE and p = 0.5) and stage C shares three, so the 2,560 years include 140 duplicate years. These are useful as a check (the stage B base equals the stage A cell exactly); say so rather than counting them as independent.
- The never-linked filter is an engine choice that the throughput result depends on: without it the run starved at 63 t (B-41). Table 5 lists it; keep it in the limitations.

---

## 5. Missing analyses (all cheap)

Run times are taken from §4.6 and B-42: DTE cells about 6 s per run, relay cells 1–2 s, stage B about 3 s, the analysis about 2 min. Everything runs single-process at under 300 MB.

| # | Analysis | Why | Cost |
|---|---|---|---|
| M1 | Relay levels 0.6 and 0.7 (and 0.05) in stage A, all six mixes | The headline 0.62 / 0.81 and every stage B equivalent fall in the empty 0.5–0.8 gap | 18 cells × 20 = 360 runs, about 10 min |
| M2 | Throughput split into bulk regolith and lander cargo, by destination, for every mix and regime | O1: the general result is the two-thirds loss of lander cargo | Analysis only (`delivered_nonbulk_kg` exists), minutes |
| M3 | Key cells per start year; year-blocked intervals | S3, E17 | Analysis only, seconds |
| M4 | Completion share of urgent items, and a censored p90 | S1 | Add one summary column and rerun the analysis, or reuse B-43's traced reruns; under 15 min |
| M5 | Price interval with all draws, 2,000 draws; paired bootstrap of Δp(strategic) − Δp(+1 rover); log-ratio and Wilcoxon effects for the main delay comparisons | E2, O4, S2 | Seconds to 2 min (my re-run took under a minute) |
| M6 | Stage B with strategic+avoid at p = 0.5 and DTE; stage B (strict and strategic, +0 and +1 rover) at p = 0.2 and 0.8 | O4 (the look-ahead claim), S8 (is the rover worth the same elsewhere?) | About 16 cells × 20 = 320 runs, 15–20 min |
| M7 | Teleop stage A rerun with B-45's hard operator limit | S11, O6, E5 | 10 cells × 20 = 200 runs, about 10 min |
| M8 | Relay gap 2 h and 24 h, and a periodic gap (DRM-0 and RC 3.1 orbits), at p = 0.1 and 0.5, strict and teleop | S13, E23 | 240 runs, about 8 min (the periodic gap needs a few lines in `_relay_intervals`) |
| M9 | p = 0.02 / 0.05, or relay availability at ISRU reduced by half | S12, O2 | 120–240 runs, about 5 min |
| M10 | Antenna height 1.5 m and 3.5 m for the windows; rerun the DTE default and strict cells | S14 | Pipeline masks + link about 9 min per height (B-40 timings), plus about 5 min of runs |
| M11 | A busy fleet (for example twice the landing cadence, or three rovers) for rovers against relay at p = 0.5 | O3 | About 8 cells × 20 = 160 runs, about 8 min |
| M12 | Intervention rate ×0.5 and ×2 for strategic and strategic+avoid at DTE and p = 0.5 | S15 | 8 cells × 20 = 160 runs, about 8 min |
| M13 | Plume keep-out on, at DTE default and p = 0.5 strict | S9 | 40 runs, about 3 min |
| M14 | ISRU with local feedstock (no CONSTR→ISRU haul) at DTE and always, three mixes | Shows how much of the 42 % is the demand model | 120 runs, about 5 min |

M1, M2, M3, M4, M5 and M7 are the ones I would require. Together they take well under an hour of machine time.

---

## 6. Writing

On the whole the prose is plain and concrete, better than most papers in this area. The problems are concentrated in the abstract, the Discussion and the code vocabulary.

**W1. The abstract** runs about 340 words with about 30 numbers. Cut it to 250 words or fewer, with one number per claim, and move the validation numbers (Horizons, map agreement) to the body. Fix the broken sentence (E21). Add the conditions on the relay claim (O2) and the price claim (O5).

**W2. The Discussion opens each paragraph with a slogan.**
- "Where a site is matters as much as how it is served."
- "A little relay coverage goes a long way for throughput, and a long way is needed for urgent delay."
- "Autonomy and relays are substitutes, and rovers are not."
- "Operations planning has to expect bursts."

These read as taglines, and three of them overclaim (O3, O4, O9). Open each paragraph with the finding and its condition instead. For example: "In this layout, one site that never sees Earth accounts for 90 % of the lost tonnage."

**W3. Phrases to replace:**
- "fails badly" (§1) → give the number;
- "goes a long way" → give the number;
- "The largest single number in this paper" → drop;
- "puts a number on it" → "gives it a value for a fleet";
- "the practical points are three" → "three points follow";
- "Within those limits three things hold" → just list them;
- "about a quarter" (§5.4, actually 22.6 %) → "by 9 h, about a fifth";
- "comes close to full coverage", "nearly equal", "well ahead", "hardly depends", "almost never linked" → give the numbers.

**W4. Code and project vocabulary in the prose and tables.**
- Code tokens: any_part, centre+0.5deg, dte+relay, dte+mast, teleop 4 s, strategic+avoid. Use words in prose and tables ("any part of the disc", "centre 0.5° above the horizon", "DTE plus relay").
- Project labels: "Phase-2", "Phase-2 mix", "v2", "v3", "version-3 code", "E21". Use "[14]" and "[33]", and define "Phase 2" once as the reference demand of [33]: four CLPS-class, three MK1-class and one large landing a year, plus 500 t/yr of regolith haul.
- The canonical md5 hash and "byte-identical" belong in Availability, not in §3.7.

**W5. Long sentences to split:**
- RQ1 (45 words);
- the contract sentence in §2.2;
- the identity sentence at the end of §3.7;
- the mast-mode sentence in §3.4;
- the list of factors in the abstract;
- the "Break-evens in throughput" paragraph, which should go (E22).

**W6. Promissory sentences.** "A version with a hard operator limit is in preparation" (§5.6) and "which is in preparation" (§7): replace each with the result (M7) or a plain limitation.

**W7. Flags in the Introduction.** Tagging every number in §1 as (Modelled) or (Spec) interrupts the reading. Keep the flags in the tables and at first use in Sections 3–4.

**W8. Length.** §3 is about 4,600 words of prose (NOTES). Follow the NOTES suggestion: move Table 4 and the registration and epoch paragraphs of §3.6 to an appendix, and fold §4.4 into Table 6.

**W9. Jargon a planetary-operations reader will not know without a definition:**
- common random numbers;
- paired difference;
- Student-t interval;
- bootstrap resample;
- five-fold cross-validated RMSE of log delay;
- non-increasing envelope;
- knee (defined only in §4.2);
- marketplace rule (say "the pooled dispatch auction of [33]");
- discrete-event;
- cell, mix and stage;
- interventions per km and the hazard model;
- priority-1;
- deferral;
- look-ahead.

**W10. Terms an operations-research reader will not know:** LOLA (never expanded), SPICE, libration, grazing / Fresnel zone, X-band, apolune, frozen orbit, DRM-0, 3GPP, DSN (in §2.3), LEGS, CLPS-class, MK1-class, PGDA. Expand each at first use, or add a short glossary.

**W11. Figures.**
- Fig. 1: the black shadow region hides about half of the map, and dark-purple routes on black are unreadable. Use elevation shading. The two directions of a leg are drawn over each other; say which one is shown.
- Fig. 3: the strategic curves misfit the cells, above them at p = 0.1–0.2 and below them at 0.3–0.5 (S5), and symmetric ±1.96 SE bars on a log axis reach down to 5 h. Use log-scale or bootstrap bars, and offset the markers.
- Fig. 4: the reference bar ("strict, as is") has no interval, and the equivalence labels have none either. A panel of paired differences would show that +1 rover is not significant.
- Fig. 5: see E12 and O6. Plot absolute peaks against the staffing line.

---

## 7. Required changes, in priority order

### Must

1. **Fix the factual and reference errors:** E1–E19, E21, E22 and E25. The ones that change what a reader believes are E1, E2, E4, E5, E8, E11, E13, E15 and E17.
2. **Correct the relay price interval** (all draws, at least 2,000; say the upper bound is poorly determined, above 200 M$). Label the price "at p = 0.5, strict fleet" in the abstract and §5.4 (E2, E3, O5, S4).
3. **Reframe the throughput headline.** Report the bulk / lander split (lander cargo about −67 %) and the 200 t/yr feedstock assumption next to the 42 %. Say that at 3 km pads no lander cargo moves under DTE (O1, M2).
4. **Deal with censoring in urgent delay.** Report the completion share of priority-1 items in every table that shows p90, and re-read the criterion and pad results in its light (S1, E8, E10, M4).
5. **Make the delay statistics robust.** Use log-ratio or rank-based paired effects for the main delay claims, give medians, show results per start year, and say that intervals include calendar variation over four years (S2, S3, M3, M5).
6. **Rewrite the strategic-versus-rover conclusion.** Test the difference (M5), state that the stage B "strategic step" had no look-ahead, and limit "autonomy before rovers" to the coverage range where it was shown (O4). Replace the stranding explanation with the 2028 calendar effect (E17).
7. **State the soft operator pool and its effect on the teleop results;** fix the "full relay = always" claim. Replace the peak/mean ratio with absolute peaks and seeds over staff, or rerun the teleop cells with the hard limit (S11, O6, E5, E11, E12, M7).
8. **Put the assumption that the relay sees every route point,** and the near-idle fleet, next to every "any relay restores" and "rovers do not help" claim. Fix the LCRNS comparison (combined against relay-alone coverage) (O2, O3, S12, E13).
9. **Report what the deferral data show** (no effect from 12 to 72 h under DTE; a small cost at high coverage), and drop "matters just as much" (O7, S7).
10. **Report or demote the unreported primary metrics,** and drop or shorten the degenerate throughput break-even (S17, E22).

### Should

11. Add relay levels 0.6 and 0.7 (M1).
12. Run stage B with strategic+avoid, and at a second coverage (M6).
13. Add the relay-gap sensitivity and reconcile DRM-0 with RC 3.1 (M8, E23, S13).
14. Justify the 2.5 m antenna and test one other height (M10, S14).
15. Run the intervention-rate sweep (M12, S15).
16. Revise the law: say the family cannot fit the tail, drop the law-based column and the misfit curves (S5).
17. Rewrite the abstract and the Discussion openings (W1–W3). Remove code tokens and project labels (W4). Define the jargon (W9, W10).
18. Verify the items listed under the E-table (map period, Jun et al. location, LTV quotes, Sun elevation source). Complete the references (E24).
19. Fix the figures (W11). Use t intervals for cell means (E20). Name the primary comparisons (S16).

### Could

20. Test a busy fleet (M11), the plume keep-out on (M13), ISRU with local feedstock (M14), and a lower relay bound at ISRU (M9).
21. Move §3.6's Table 4 and the registration detail to an appendix (W8).
22. Add an order-of-magnitude DTE link budget for a 2.5 m rover antenna at 0–6° elevation to an 18 m LEGS dish, to show that teleoperation over DTE is plausible at all at these elevations. LCRNS's 17–43 % DTE figures against our 52–59 % at BASE suggest their definition includes more than geometry; discuss this.
