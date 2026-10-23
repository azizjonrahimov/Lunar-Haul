# Paper R-1 ("Earth in sight"), parts 1-3: notes for the author of the back half

First written 2026-10-22; revised the same day after the referee report `paper/r1/REVIEW_round1.md` (round 1, major
revision). The changelog at the end lists every change in parts 1-3 with the review item it answers. Sources:
`research_notes/Lunar communications and visibility/earth_visibility_prior_art.md`, `.team/reports.md` (B-40 to
B-47), `lunarsim/comms.py`, `lunarsim/engine.py`, `lunarsim/phases.py`, `experiments/phase4/run_phase4.py` (working
tree, with the round-2 stages), `experiments/phase4/analyse_e21.py`, `data/comms/connecting_ridge/earth_link-v1.json`
(read with `lunarsim.comms.EarthLink`) and `earth_track-v1.json.gz`, the raw `results/E21a_comms_autonomy.csv`, and the
primary sources fetched this session (listed under "What was checked"). Only parts 1-3 and this file were edited.
Nothing was committed.

| File | Content | Prose words (tables and captions excluded) |
|---|---|---|
| `part1_front.html` | `<head>`, title, author, affiliation, abstract (result sentences as marked placeholders), keywords, Section 1 Introduction (RQ1-RQ4, three contributions, what is not claimed, roadmap) | ~2,020 (abstract ~255 with placeholders unexpanded) |
| `part2_related.html` | Section 2 Related work (2.1-2.5) and Table 1 | ~1,940 |
| `part3_methods.html` | Section 3 Data and model (3.1-3.7, Tables 2-4), Section 4 Experiment design (4.1-4.5, Table 5), Appendix A (map comparison, Table A1), Appendix B (glossary, Table B1) | ~3,600 (Section 3) + ~2,500 (Section 4) + ~350 (Appendix A) |

Section 3 is longer than before (it gained the E5, E6, E7, E23 and O8 explanations and the flag definitions moved
out of the Introduction) although Table 4 and the registration and epoch paragraphs moved to Appendix A. Section 4
gained Stages A2, D and E, the censored urgent-delay metrics, the robust paired statistics and the primary
comparisons. If it must shrink further: the Stage descriptions in 4.2 can lean more on Table 5, and the last two
paragraphs of 3.7 (identity checks) can move to Availability.

## Title

Chosen (in `<title>` and `<h1 id="r1-title">`): **What Earth's Horizon Costs a Lunar Base: Terrain-Masked
Communication Windows in South-Pole Cargo Logistics**. Unchanged in revision.

## Conventions

- Skeleton as v3: `<!DOCTYPE html>` + `<head>` only in part 1; parts 2-3 are bare fragments starting with `<h2>`.
- Classes: `.authors`, `.affil`, `.abstract` + `.kw`, `.tabcap` with `<b>Table n.</b>`, `table.small`, `td/th.num`,
  `ul.contrib`, `ol` for RQs and the primary comparisons, `.mono` (now only for SPICE kernel and routine names).
- **Style (review E26), used everywhere in parts 1-3:** percent as `&#8239;%` (narrow no-break space, U+202F);
  money as `45&nbsp;M$` (also the contract value, 4,820&nbsp;M$); stages as "Stage A", "Stage A2", "Stage B" ... "Stage E"
  (capital S, no hyphen). The back half and `build_r1.py` still write `&nbsp;%`, "Stage-A" and "Stage&nbsp;A"; see
  "For the lead" below.
- **Words, not code tokens (W4):** "any part of the disc", "centre 0.5° above the horizon", "centre 2° above the
  horizon", "DTE only", "DTE plus relay", "DTE plus mast", "supervised strict / strategic / with look-ahead",
  "teleoperated (4 s round trip)", "the reference mix", "the reference fleet of [33]", "the pooled dispatch auction of
  [33]", "Phase 2" (defined once in 4.1). No file paths or `.csv`/`.py` names in prose or tables; the experiment is
  "the experiment", not "E21". Site labels (BASE, DEPOT, POWER, CONSTR, ISRU, SCI_1, PSR, PAD_A, PAD_B) are kept as
  defined names because Figure 1 and the tables use them.
- Flags (Measured / Spec / Modelled / Assumed) are defined at the start of Section 3 and used in Sections 3-4 and the
  tables only (W7); Sections 1 and 2 carry none.
- Ids, all prefixed `r1-`: `r1-title`, `r1-abstract`, `r1-sec-intro`, `r1-sec-related`, `r1-tab-prior`, `r1-sec-data`,
  `r1-tab-sites`, `r1-tab-padlegs`, `r1-tab-rules`, `r1-sec-e21` (Section 4, kept for links), `r1-tab-stages`,
  `r1-appendices` (wrapper div), `r1-app-a`, `r1-tab-avgvisib` (now Table A1), `r1-app-b`, `r1-tab-glossary`.

### Numbering the back half must continue (changed in revision)

- Sections: 1-4 as before; Section 4 is now "Experiment design" with 4.1 Scenario and fleet, 4.2 Stages, 4.3
  Replications and calendar, **4.4 Metrics, statistics and break-evens** (old 4.4 folded into Table 5 and old 4.5),
  4.5 Compute. Section 2.2 now points to Section 4.4 for the equivalence. Sections 5-8, Availability and References
  follow, then **Appendix A and Appendix B**.
- **Tables:** 1 (prior work), 2 (sites and pads), 3 (pad legs), **4 (link rules, was 5)**, **5 (stages, was 6)**;
  appendix tables **A1** (map comparison, was 4) and **B1** (glossary). **Results tables now start at Table 6** (they
  were 7-10). `build_r1.py` writes "Table 7" to "Table 10" in its captions and part 4 cites "Table 7" to "Table 10":
  both need -1.
- **Appendices sit at the end of part 3** (as asked), between the markers `<!-- APPENDICES START ... -->` and
  `<!-- APPENDICES END -->`. In the assembled paper they would appear between Section 4 and Section 5. The build should
  cut that block and insert it after `{{R1-REFERENCES}}` (a two-line change in `build()`), or the parts can be
  reordered by hand.
- Stages: A (link regime x mix), A2 (hard operator limit), B (break-evens), C (pads, criterion, deferral), D (real
  Sun), E (sensitivity). Research questions RQ1-RQ4 unchanged in substance; RQ1, RQ2 and RQ4 were split into two
  sentences (W5) and RQ4 now asks about the hard operator limit and sensitivity.

### Limitations already stated in parts 1-3 (to repeat or update in Section 7)

Geometric link criteria, no link budget (3.4 now says "we expect a real link between the any-part and centre
criteria" with the Fresnel and station-on-disc reason, and that terrain multipath could make it worse: use the same
wording in 7, O8); parametric relay that sees every route point (Assumed), with a DRM-0 gap as a single-satellite
stand-in tested in Stage E; the slope-only route stands for every lighting case; pad-to-pad legs inferred from end
points; Stages A-C keep the fixed night share starting at hour 0 of every run (Stage D tests the real Sun; replace
"in preparation" in Section 7); no crewed local driving; uniform placement of strategic interventions and the Assumed
hazard model (Stage E sweeps x0.5 and x2); deferral limit (24 h) motivated by development runs; Stage B coverage (0.5)
fixed after Stage A (now tested at 0.2 and 0.8: fix E9 in Section 7); 20 seeds over four start years; LTV capital
450 M$ / 10 yr, Modelled in [33] (E14: use this basis and flag in 5.4 and 7, not "v3's Assumed vehicle costs"); one
site and layout; the 0.032 map difference at BASE not decomposed; the soft operator admission (Table 4) and the
teleoperated fleet's non-identity at full relay (3.7); the lightly used fleet ({{R1-UTIL-ALWAYS}}); the
never-linked candidate filter (Table 4, S18).

## Every placeholder in parts 1-3 (29 occurrences, 28 distinct)

Grep: `grep -o "{{R1-[^}]*}}" paper/r1/part[123]*.html`. Round-2 sources are the `_r2` files written by
`run_phase4.py --round r2` and the round-2 `analyse_e21.py fit` (`results/table_E21_r2.csv`,
`table_E21_breakeven_r2.csv`, and, if the analysis writes them with the same suffix, `table_E21_effects_r2.csv`,
`table_E21_breakeven_delay_r2.csv`, `E21_fit_r2.json`, `fig_E21_operator_demand_r2.csv`). "Default" = mix `default`
(the reference mix). Stage A rows have `stage=A, criterion=any_part, pad_standoff_km=1, defer_wait_h=24, mast=none,
extra_rovers=0, sensitivity=none`. Report every number as mean with its 95&#8239;% interval.

### Already filled by `build_r1.py` (switch its inputs to the `_r2` files)

| Placeholder | Where | Content and source |
|---|---|---|
| `{{R1-T-DTE}}`, `{{R1-T-ALWAYS}}` | abstract | delivered t/yr inside the year, DTE only and always, default; `table_E21_r2.csv` `delivered_t_in_year` |
| `{{R1-T-LOSS-PCT}}` | abstract | paired change in %, default, `table_E21_effects_r2.csv` family `dte_vs_always`; format `&minus;42&#8239;% [&minus;44, &minus;41]` |
| `{{R1-RELAY01-RESTORE-PCT}}` | abstract | (T(0.1) - T(DTE)) / (T(always) - T(DTE)), default |
| `{{R1-DP-ONE-LTV}}` | abstract | Δp of one extra rover at p = 0.5, strict fleet, with CI; `E21_fit_r2.json` `breakeven_delay` |
| `{{R1-MUSD-PER-01}}` | abstract | price per 0.1 coverage with the corrected CI (all draws kept, >= 2,000 draws; E2). If the upper bound is unstable write "11 M$ to above 200 M$" or similar; the abstract sentence has no room for more |
| `{{R1-COMPUTE-H}}`, `{{R1-COMPUTE-A-MIN}}`, `{{R1-COMPUTE-B-MIN}}`, `{{R1-COMPUTE-C-MIN}}` | 4.5 | sum of `run_s` over the `_r2` raw files / 3600 or / 60, per stage |

`{{R1-A-KNEE-P}}` no longer appears in parts 1-3: Section 4.2 now states the first run's knee as the literal
"p = 0.1" (round-1 `values.json`), because a round-2 table with p = 0.05 could give a different knee. Part 4 still
uses the placeholder.

### New placeholders (the build must add them)

| Placeholder | Where | Content | Source and expected value |
|---|---|---|---|
| `{{R1-N-YEARS}}` | abstract, Table 5 | simulated years in all stages | number of rows over the six `_r2` raw files; **expected 4,920** (246 cells x 20) from the runner's cell lists |
| `{{R1-N-CELLS}}` | Table 5 | cells in all stages | **expected 246** |
| `{{R1-CELLS-A}}` | Table 5 | Stage A cells | `len(e21a_cells("r2"))`; **expected 78** (13 link levels x 6 mixes) |
| `{{R1-CELLS-A2}}` | Table 5 | Stage A2 cells | `len(e21a2_cells())`; **expected 12** |
| `{{R1-CELLS-B}}` | Table 5 | Stage B cells | `len(e21b_cells(0.5, "r2"))`; **expected 56** (48 + 8) |
| `{{R1-CELLS-C}}` | Table 5 | Stage C cells | **expected 36** |
| `{{R1-CELLS-D}}` | Table 5 | Stage D cells | `len(e21d_cells())`; **expected 32** |
| `{{R1-CELLS-E}}` | Table 5 | Stage E cells | `len(e21e_cells())`; **expected 32** (16 relay gap + 8 interventions + 2 plume + 6 local feedstock) |
| `{{R1-N-DUP-YEARS}}` | Table 5 caption | years that repeat a Stage A cell | Stage B +0 rovers, no mast: 3 policies at DTE, 3 at p = 0.5, 2 at p = 0.2, 2 at p = 0.8 = 10 cells; Stage C base cells = 3; **expected 13 x 20 = 260**. (Stage D's fixed-night cells also repeat 5 of their 20 seeds from Stage A, 40 runs; mention if you count them.) Write as "260" |
| `{{R1-N-EFFECTS}}` | 4.4 | number of paired effects computed | rows of `table_E21_effects_r2.csv` (round 1: 810 per the review; 708 in B-43 before Stage C finished) |
| `{{R1-BOOT-DRAWS}}` | 4.4 | bootstrap draws | the round-2 `analyse_e21.py` setting; the review requires >= 2,000 (S4). Write "2,000" |
| `{{R1-UTIL-ALWAYS}}` | 4.1 | utilisation of the reference fleet with Earth always in view | `table_E21_r2.csv` `utilisation`, Stage A, always, default; round 1: 0.0285, so "2.8&#8239;%" (DTE: 3.4&#8239;%) |
| `{{R1-COMPUTE-A2-MIN}}`, `{{R1-COMPUTE-D-MIN}}`, `{{R1-COMPUTE-E-MIN}}` | 4.5 | stage minutes | sum of `run_s` in `E21a2_operators_r2.csv`, `E21d_sun_r2.csv` (or `E21d_sun.csv` if D is not rerun), `E21e_sensitivity_r2.csv`, / 60 |
| `{{R1-T-LANDED-LOSS-PCT}}` | abstract | paired change in lander cargo (non-bulk, non-return) delivered in the year, DTE vs always, default | `table_E21_effects_r2.csv` metric `delivered_landed_kg_in_horizon` (or compute from the raw `_r2` A rows); round 1 had the strict fleet at 29.3 t to 9.4 t (about -68&#8239;%) from `delivered_nonbulk_kg` |
| `{{R1-P1-COMPLETION-DTE}}` | abstract | completion share of priority-1 items, DTE only, default | `table_E21_r2.csv` `prio1_completion_share`, as a percentage with CI |
| `{{R1-ABS-OPERATORS}}` | abstract | **a whole sentence, at most ~15 words**, on operator demand: absolute peak and seeds over the 3 on duty for the teleoperated fleet under DTE only, and what the hard limit costs | Stage A2 effects (`strict_vs_lenient` family) and `fig_E21_operator_demand_r2.csv` (`peak_mean`, `seeds_over_staffing`). Replaces the peak/mean ratio sentence (O6) |

Removed from the abstract (still used in parts 4-5, so the build keeps them): `{{R1-LOSS-SHARE-ISRU}}`,
`{{R1-P90-ALWAYS}}`, `{{R1-P90-DTE}}`, `{{R1-ROVER-GAIN-T}}`, `{{R1-MAST-GAIN-T}}`, `{{R1-PTM-DTE}}`, `{{R1-PTM-FULL}}`.
The uncensored p90 should not be the headline delay any more (S1); if a delay number is wanted in the abstract use the
censored p90 with its "≥" mark.

### Abstract: what the lead still has to do

The result sentences sit between `<!-- RESULT SENTENCES ... -->` and `<!-- END RESULT SENTENCES -->`. They assume the
round-1 directions (a large DTE loss that is mostly the plant's regolith; relay 0.1 restores nearly all; rovers and
mast restore none; a positive Δp) and carry the referee's conditions: the feedstock assumption and the lander split
(O1), "assumed to see every route point" (O2, S12), "lightly used fleet" (O3), "at coverage 0.5, strict" (O5). The
text outside the block is ~170 words; with placeholders expanded the block must stay near 80 words for W1 (<= 250).

## Numbers written in parts 1-3 and where they come from

All data and validation numbers are measured and written in: site and pad table (B-40), leg counts 101/182 and
138/182 (B-40), Horizons 1.0e-6 / 5.5e-7 deg / 0.0006" over 4,465 epochs, map comparison mean -0.004, mean |Δ|
0.028, largest -0.123, 15 of 17 within 0.05, two points zero in both (`provenance.avgvisib_check`), BASE 0.471 /
0.503 / 0.593 / 0.384 / 0.597, horizon +2.9 / -1.26 deg, 18.6-yr 0.580, years 0.546-0.626, windows 16.0 / 14.1 /
12.1 d (B-40).

Computed this session (light reads, no simulation):
- **Censored gaps (E6, E7), `EarthLink.windows()` on `earth_link-v1.json`, any part, DTE:** SCI_1 first window at
  day 330.4 (26 Nov 2028), 42 windows, mean 70.7 h, largest gap between windows 622.5 h, mean between 582.2 h;
  13-14 windows a year from 2029. PSR 54 windows, mean 79.9 h, first on 3 Jan 2028. PAD_A@2 first window day 358.1
  (24 Dec 2028), then a 2,579 h gap to 11 Apr 2029, then monthly; mean between 631.3 h. PAD_B@3 first window day
  493.2 (8 May 2029), largest gap between windows 633.8 h, mean between 579.7 h. The summary's `max_gap_h` and
  `mean_gap_h` include the stretches before the first and after the last window.
- **Windows at the elevation maxima (E7):** with the hourly Earth track at BASE, every window of SCI_1, PSR, PAD_A@2
  and PAD_B@3 is centred within 16 h of the local monthly maximum of Earth's elevation (median offset 2-5 h), and
  Earth's centre is at least 5.0 deg above the horizontal throughout them; the monthly maxima are 5.82-6.23 deg.
- **Pad legs at 3 and 5 km:** 55 of 56 never linked; the exception, PSR->PAD_A@5, is linked 8.0&#8239;% (0.0798).
- **Lunar obliquity (unverified item 4):** with SPICE and the DE440 kernels of Section 3.2, the angle between the
  MOON_ME pole and the ecliptic pole over 2028-2031 is 1.540 deg on average (1.506-1.581 deg with physical
  librations), and the Sun's elevation at the pole (from the Moon's centre) stays within -1.56 to +1.59 deg. At BASE
  the Sun swings -2.1 to +2.1 deg (B-44).
- **E5, raw `E21a_comms_autonomy.csv`, always against relay 1.0 per seed:** teleop_4s differs in 8 of 20 seeds in
  urgent p90 (max 15.47 h) and by up to 2,444 kg delivered; mean `unmet_operator_waits` 11.4 (always) against 32.4
  (relay 1.0). The other five mixes are identical in p90, delivered mass and unmet waits.
- **E10:** round-1 `table_E21.csv` Stage C at 3 km pads: `n_valid` = 0 for every DTE cell (default and teleop, all
  three criteria); 20 for the relay 0.8 cells.
- **Phase 2 (W4), `lunarsim/phases.py`:** landings CLPS 4, MK1 3, LARGE 1 a year; bulk CONSTR->BASE 300 t/yr and
  CONSTR->ISRU 200 t/yr in 1 t lots; fleet NASA LTV x2, CoA LTV and HAUL (supervised), CoB MICRO and CoC LTV (teleop);
  3 operators. Matches `web/sim.js` PHASES.P2.
- **Unit tests:** `^def test_` in `test_comms_data.py` 11, `test_comms_engine.py` 14, `test_operators_strict.py` 5,
  `test_illumination.py` 9 = 39 ("Thirty-nine unit test functions" in 3.7).
- **The law bound (S5):** with `fit_form`'s bounds (`a, b >= 0`, `c >= 1e-4`; power `g` in [0, 20]) the hyperbolic
  2x target is at most (1 - c)/2, and the power form's is too when g <= 1 (round-1 fits: default g = 0.91, strategic
  g = 0.39). Written in 4.4.

## References (numbered by first citation across all five parts)

[1] S. Bryant. "Lunar Pole Illumination and Communications Maps Computed from Goldstone Solar System Radar Elevation Data." *The Interplanetary Network Progress Report* 42-176, Jet Propulsion Laboratory, 15 February 2009. https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.pdf

[2] D. De Rosa, B. Bussey, J. T. Cahill, T. Lutz, I. A. Crawford, T. Hackwill, S. van Gasselt, G. Neukum, L. Witte, A. McGovern, P. M. Grindrod, J. D. Carpenter. "Characterisation of potential landing sites for the European Space Agency's Lunar Lander project." *Planetary and Space Science* 74(1):224-246, 2012. doi:10.1016/j.pss.2012.08.002

[3] M. C. Scardelletti, M. R. Gasper, R. C. Reinhart, M. J. Zemba, J. L. Rock, S. R. Oleson, E. R. Turnbull. "Lunar Surface Network Relay Terminal: A Lunar Communications Platform." 40th International Communications Satellite Systems Conference (ICSSC), Bradford, UK, 23-26 October 2023. NTRS 20230013361. https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf

[4] W. W. Jun, T. Tanaka, P. Carter, R. L. Anderson, S. Bhamidipati, K.-M. Cheung. "A Rapid, Low-Cost Path to Lunar Communication and Navigation with a Lunar Surface Station." 2025 IEEE Aerospace Conference, Big Sky, MT, 2025. doi:10.1109/AERO63441.2025.11068684. https://www-robotics.jpl.nasa.gov/media/documents/A_Rapid_Low-Cost_Path_to_Lunar_Communication_and_Navigation.pdf

[5] H. L. Litaker, Z. Q. Li, K. H. Beaton, J. F. Lewis. *Lunar Terrain Vehicle (LTV) Remote Teleoperation Studies Under Four Lunar Communication Latencies*. NASA/TM-20240001217, January 2024. https://ntrs.nasa.gov/citations/20240001217 ; follow-up paper NTRS 20240011392, 2025, https://ntrs.nasa.gov/citations/20240011392

[6] M. Shirley, E. Balaban. "An Overview of Mission Planning for the VIPER Rover." SpaceOps 2022 Mission Planning Workshop, 2 June 2022. https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf

[7] N. Otten, D. Wettergreen, W. Whittaker. "Strategic Autonomy for Reducing Risk of Sun-Synchronous Lunar Polar Exploration." *Field and Service Robotics* (FSR 2017), Springer, 2018. https://www.ri.cmu.edu/app/uploads/2018/01/FSR_2017_Otten_66.pdf ; N. Otten, *Planning for Sun-Synchronous Lunar Polar Roving*, PhD thesis, Carnegie Mellon University, 2018, https://www.ri.cmu.edu/app/uploads/2018/01/thesis_otten.pdf

[8] A. Dwyer Cianciolo. "Artemis Human Landing System Update." NASA LaRC/ARC EDL Summer Seminar Series, August 2024. NTRS 20240009596. https://ntrs.nasa.gov/api/citations/20240009596/downloads/ArtemisHLSUpdate_2024.pdf

[9] T. George, M. A. Rubio, S. J. Lawrence, P. Curell. "Artemis III Site Selection Update: Downselection From Thirteen to Nine Candidate Regions." Lunar and Planetary Science Conference, The Woodlands, TX, March 2026. NTRS 20250011660. https://ntrs.nasa.gov/citations/20250011660

[10] J. Esper, G. Heckler, J. Verville, G. Ryden. "NASA's Lunar Communications Relay and Navigation Systems (LCRNS)." 18th International Conference on Space Operations (SpaceOps 2025), Montreal, 26-30 May 2025. NTRS 20250003321. https://ntrs.nasa.gov/api/citations/20250003321/downloads/LCRNS_Esper_257.pdf

[11] NASA. "NASA Selects Lunar Relay Contractor for Near Space Network Services." News release, 17 September 2024. https://www.nasa.gov/news-release/nasa-selects-lunar-relay-contractor-for-near-space-network-services

[12] E. Mazarico, G. A. Neumann, D. E. Smith, M. T. Zuber, M. H. Torrence. "Illumination conditions of the lunar polar regions using LOLA topography." *Icarus* 211:1066-1081, 2011. doi:10.1016/j.icarus.2010.10.030. LOLA average Earth-visibility maps: PGDA product 69, https://pgda.gsfc.nasa.gov/products/69

[13] H. Inoue, S. Adachi. "Spatio-Temporal Path Planning for Lunar Polar Exploration with Robustness against Schedule Delay." *Transactions of the Japan Society for Aeronautical and Space Sciences* 64(6):304-311, 2021. doi:10.2322/tjsass.64.304

[14] A. Rahimov. *Where the Lander Lands: Landing Precision, Pad Standoff, Plume Keep-Out and Rover Autonomy Priced in Lunar Surface Logistics*. Preprint, version 3, October 2026. DOI to be assigned on deposit.

[15] P. Gläser, F. Scholten, D. De Rosa, R. M. Figuera, J. Oberst, E. Mazarico, G. Neumann, M. S. Robinson. "Illumination conditions at the lunar south pole using high resolution Digital Terrain Models from LOLA." *Icarus* 243:79-90, 2014. doi:10.1016/j.icarus.2014.08.013

[16] E. Peña-Asensio, Á.-S. Neira-Acosta, J. M. Sánchez-Lozano. "Evaluating potential landing sites for the Artemis III mission using a multi-criteria decision making approach." arXiv:2406.19863, 2024 (accepted in *Acta Astronautica*). https://arxiv.org/abs/2406.19863

[17] H. Wang, H. Guo, X. Lu, G. Liu, H. Ye. "Lunar Terrain-Driven Earth Visibility Analysis for South Polar Moon-Based Observations." *IEEE Geoscience and Remote Sensing Letters* 22:1-5, 2025. doi:10.1109/LGRS.2025.3571520

[18] G. Ryden, M. Volle. *NASA Lunar Communications Relay and Navigation Systems (LCRNS) Reference Constellation 3.1*. NASA white paper, 2025. NTRS 20250002698. https://ntrs.nasa.gov/citations/20250002698

[19] UNOOSA International Committee on GNSS, Working Group B, Lunar PNT meeting, June 2024 (LCRNS service schedule slides). https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_01_02.pdf

[20] NASA. "Moon Base Phases." Web page, last updated 8 October 2026 (IM-3 and Altus-1, the first satellite of Intuitive Machines' lunar relay network). https://www.nasa.gov/moonbase-phases/

[21] ESA. "The Moon where no satnav has gone before." https://www.esa.int/Applications/Navigation/The_Moon_where_no_satnav_has_gone_before ; SSTL. "ESA signs further order for commercial lunar relay services from SSTL," 2023. https://sstl.co.uk/media-hub/latest-news/2023/esa-signs-further-order-for-commercial-lunar-relay-services-from-sstl

[22] ESA. "ESA's Moonlight programme: pioneering the path for lunar exploration." https://esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration

[23] NASA. "VIPER: Lunar Operations." NASA Science web page. https://science.nasa.gov/mission/viper/lunar-operations/

[24] D. Gaines et al. "Productivity Challenges for Mars Rover Operations." JPL D-97908, 2016 (same title as the ICAPS 2016 workshop paper). https://ai.jpl.nasa.gov/public/documents/papers/gaines-report-roverProductivity.pdf

[25] E. L. Gralla, S. Shull, O. L. de Weck. "A modeling framework for interplanetary supply chains." AIAA SPACE 2006; S. A. Shull, *Integrated Modeling and Simulation of Lunar Exploration Campaign Logistics*, S.M. thesis, MIT, 2007. https://dspace.mit.edu/handle/1721.1/39711

[26] T. Ishimatsu, O. L. de Weck, J. A. Hoffman, Y. Ohkami, R. Shishko. "Generalized multicommodity network flow model for the Earth-Moon-Mars logistics system." *Journal of Spacecraft and Rockets* 53(1):25-38, 2016. https://dspace.mit.edu/handle/1721.1/110236

[27] K. Ho. *Dynamic Network Modeling for Spaceflight Logistics with Time-Expanded Networks*, PhD thesis, MIT, 2015; B. B. Jagannatha, K. Ho, "Event-driven network model for space mission optimization," *Journal of Spacecraft and Rockets* 57(3), 2020. https://arxiv.org/abs/1904.09364

[28] K. Ho et al. "Space logistics: a review." 2024. https://arxiv.org/abs/2306.01107

[29] R. Vera, A. Berea, W. G. Kennedy. "Lunar base agent-based modeling: A benchmark for simulating crewed space missions." *PLOS One* 21(5):e0348882, 2026. doi:10.1371/journal.pone.0348882

[30] Z. Wang. "Agent Mars: Multi-Agent Simulation for Multi-Planetary Life Exploration and Settlement." arXiv:2602.13291, 2026. https://arxiv.org/abs/2602.13291

[31] A. Krawciw, L. Antonyshyn, S. Lilge, N. Olmedo, F. Rehmatullah, M. Desjardins-Goulet, P. Toupin, T. D. Barfoot. "Sharing the load: autonomous multi-rover cargo transport." arXiv:2510.18766, 2025. https://arxiv.org/abs/2510.18766

[32] A. Krawciw, N. Olmedo, F. Rehmatullah, M. Desjardins-Goulet, P. Toupin, T. D. Barfoot. "Lunar Rover Cargo Transport: Mission Concept and Field Test." arXiv:2601.03371, 2026. https://arxiv.org/abs/2601.03371

[33] A. Rahimov. *Who Hauls the Habitat? A Verified Simulation Testbed, a Pooled Dispatch Marketplace and a Reference Design for Lunar Surface Logistics*. Preprint, version 2, October 2026.

[34] M. K. Barker, E. Mazarico, G. A. Neumann, D. E. Smith, M. T. Zuber, J. W. Head. "Improved LOLA elevation maps for south pole landing sites: Error estimates and their impact on illumination conditions." *Planetary and Space Science* 203:105119, 2021. doi:10.1016/j.pss.2020.105119; PGDA product 78 (Site01, 5 m), https://pgda.gsfc.nasa.gov/products/78

[35] C. H. Acton. "Ancillary data services of NASA's Navigation and Ancillary Information Facility." *Planetary and Space Science* 44(1):65-70, 1996. doi:10.1016/0032-0633(95)00107-7; NAIF generic kernels, https://naif.jpl.nasa.gov/pub/naif/generic_kernels/ ; azlcpo_c, https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/azlcpo_c.html

[36] A. M. Annex et al. "SpiceyPy: a Pythonic Wrapper for the SPICE Toolkit." *Journal of Open Source Software* 5(46):2050, 2020. doi:10.21105/joss.02050

[37] R. S. Park, W. M. Folkner, J. G. Williams, D. H. Boggs. "The JPL Planetary and Lunar Ephemerides DE440 and DE441." *The Astronomical Journal* 161:105, 2021. doi:10.3847/1538-3881/abd414

[38] M. K. Barker, E. Mazarico, G. A. Neumann, D. E. Smith, M. T. Zuber, J. W. Head, X. Sun. "A New View of the Lunar South Pole from the Lunar Orbiter Laser Altimeter (LOLA)." *The Planetary Science Journal* 4:183, 2023. doi:10.3847/PSJ/acf3e1; PGDA product 90, https://pgda.gsfc.nasa.gov/products/90 ; data doi:10.60903/gsfcpgda-lola-spole

[39] JPL Solar System Dynamics. Horizons API. https://ssd-api.jpl.nasa.gov/doc/horizons.html ; the request used is recorded in the provenance of the link file (Availability).

[40] R. Hoover. "NASA VIPER Robotic Moon Rover Team Raises Its Mighty Mast." NASA, 1 April 2024. https://www.nasa.gov/general/nasa-viper-robotic-moon-rover-team-raises-its-mighty-mast/

[41] LOLA Science Team. AVGVISIB_85S_060M_201608_EARTH (image and PDS label; product created 15 September 2016), LRO LOLA GDR illumination extras. http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.LBL

## Renumbering and its effect on parts 4-5

- Order of first citation across all five parts (E24): parts 1-2 already cited [1]-[33] in order. In Section 3.2 the
  old [36]-[38] were cited before the old [35]; the new citation of the VIPER mast (S14) falls in 3.3, before the map
  label. Mapping old -> new: **[35] -> [38], [36] -> [35], [37] -> [36], [38] -> [37], [40] -> [41]; new [40]**
  (VIPER mast); [1]-[34] and [39] unchanged.
- **Parts 4 and 5 need no change:** they cite only [7], [10] and [14] (part 5); part 4 cites no reference. [33] also
  keeps its number if the lead cites it.
- Contents changed without renumbering: [2] (author list completed, pages), [4] (full title, venue, DOI), [5] (TM
  number and date; internal pointer removed), [17] (authors, pages, DOI), [20] (Wikipedia replaced by NASA's Moon Base
  Phases page), [29], [30], [32] (full authors and titles), [34] (authors, DOI), [35] (DOI). Every "(v3 [n])"
  pointer is gone.

## What was checked this session, and what could not be

Checked against the primary record (fetched or downloaded): the 60 m AVGVISIB label (START 2009-07-13, STOP
2013-07-18, computed from LDEM_85S_060M; no averaging period stated); the PGDA 69 page ("averaged over hourly
timesteps spanning 18.6 years"; "may be very slightly optimistic for radio link studies"); Jun et al. [4] full text
(station "positioned at the Connecting Ridge"; "would benefit significantly with a <10 km surface-to-surface link";
"many billions in USD over decades"; IEEE Aerospace 2025, DOI); Litaker et al. [5] full text ("Testing assumed
continuous high-bandwidth communication between the LTV and the remote operator"; LTV-SYS-071 "6 km (threshold), 8 km
(goal) in one 24-hour period when operated remotely"; delays 0, 4, 6 and 8 s); Acton 1996 [35] (Crossref and NAIF);
De Rosa [2], Barker 2021 [34], Wang [17], Vera [29] (Crossref); [30]-[32] (arXiv API); NASA Moon Base Phases page
[20] (Altus-1 launches with IM-3; no date); VIPER mast article [40] (mast tip about 2.5 m above the wheel rims; low-
and high-gain antennas to the DSN); lunar obliquity computed from DE440 (above).

Fixed or softened in the text:
- **"18.6 years" of the map:** now attributed to the PGDA product page for the maps in general; Appendix A says the
  60 m label gives only 2009-2013 (probably the altimetry period) and that we did not find the 60 m map's averaging
  period. "Epoch is not one of them" became "unlikely to be one of them". Our own 18.6-year BASE value (0.580, B-40)
  stays.
- **Jun et al.'s station:** confirmed "at the Connecting Ridge"; kept.
- **LTV quotes:** "flawless high-bandwidth comms" was not verbatim; replaced by the verbatim "continuous high-bandwidth
  communication between the LTV and the remote operator"; "6 km per 24 h" replaced by the requirement as written.
- **Sun's elevation:** "within about 1.5 deg [14]" replaced by our SPICE/DE440 computation (tilt 1.54 deg; Sun within
  1.6 deg at the pole, 2.1 deg at BASE), cited to [35, 37].
- **Acton 1996:** confirmed with DOI.
- **"terrain behind the map predates the 2021 and 2023 models":** now supported by the label (LDEM_85S_060M).
- **IM-3 date:** the "first part of 2027" claim had only a Wikipedia source and no NASA page gives a date; removed.

Still not verified (unchanged from round 1 unless noted):
- [24] Gaines 2016: title from search results.
- [21] Lunar Pathfinder: frequency plan and launch date conflict across sources; the paper states only its orbit and
  purpose.
- [23] VIPER operations page: Medium in the research note (6-10 s latency, two weeks a month out of view).
- [5] follow-up NTRS 20240011392: title not re-read.
- LCRNS "Spudis Ridge Peak" identity and why Malapert is only 43&#8239;% in [10].
- Bryant's ±6.87 / ±8.16 deg (the PDF text shows "+"; the paper rounds to ±6.9 / ±8.2).
- X-band wavelength 3.6 cm (Assumed, 8.4 GHz); relay hop <= 0.065 s and apolune ~19,150 km derived from [18].
- [29] "four astronauts and two rovers", [30] the landing-slot scenario among 93 agents, and [32] the 5 s each-way
  delay come from the full texts read for the research note `novelty_prior_art.md`, not re-read this session.
- The 2.5 m antenna is now tied to VIPER's mast height [40]; no LTV-class antenna height was found.
- The 10-year rover life and 450 M$ delivered cost (`lunarsim/entities.py`: 219-220 M$ task order + ~234 M$ MK1
  delivery), Modelled in [33]; primary sources are in [33]'s parameter table, not re-checked.

## For the lead (back half and build)

1. **Build script (`build_r1.py`):** read the `_r2` files; add the new placeholders above; write percent as
   `&#8239;%` and stage names as "Stage A" (E26); change the result-table captions from Table 7-10 to Table 6-9; move
   the appendix block after the references; relabel `MIX_LABEL["default"]` "Phase-2 mix (reference)" to "Reference
   mix" and write criteria in words in `table_stagec` (W4).
2. **Cell intervals (E20):** Section 4.4 now says cell means carry Student-t intervals on 19 df (t = 2.093).
   `experiments/phase3/fit_law.py` line 120 still uses `1.96 * sd / sqrt(n)`; the round-2 tables must use t, or the
   text must change back.
3. **Bootstrap (E2, S4):** Section 4.4 says every draw is kept, >= 2,000 draws, shares of Δp <= 0 and of "beyond full
   coverage" reported, and a paired bootstrap of Δp(strategic) - Δp(+1 rover). `analyse_e21.py breakeven()` drops
   non-finite and non-positive draws in round 1; check the round-2 analysis does what the text says.
4. **Robust statistics (S2):** Section 4.4 promises the geometric-mean ratio with a t interval on the log scale, a
   Wilcoxon signed-rank test and medians for the main delay comparisons. Report them for primary comparisons 2, 4,
   5 and 6 at least.
5. **Primary comparisons (S16):** Section 4.4 names six (DTE vs always: mass with the bulk/lander split; DTE vs
   always: completion and censored p90; the strict fleet's 2x coverage target; strategic vs strict at p = 0.1 and
   0.5; one rover and the strategic step as Δp at p = 0.5 and their difference; hard vs soft operator limit for the
   teleoperated fleet). Change the list if the results section leads with different ones.
6. **Per-start-year reporting (S3, M3):** Section 4.3 promises key cells per start year.
7. **E10:** Section 4.3 promises that a mean over fewer than 20 seeds is reported with its count.
8. **Section 4.4, break-evens in throughput (E22):** one sentence says the break-even is undefined because throughput
   "saturates by relay coverage 0.1 and extra rovers add nothing at DTE only". Re-check with the 0.05 level.
9. **Availability (part 5, W4):** put the canonical md5 of the always-linked reference comparison
   (739e9ba72c1563f4ae508ebc1dfd9938), "byte-identical", the file names (`earth_link-v1.json`, the samples file,
   `E21*_r2.csv`, `table_E21_r2.csv`, ...) and the code paths there; Section 3 now says "Availability gives the
   checksum".
10. **Part 5 items that touch my wording:** §8 "verified cargo simulation" -> "checked against analytic and earlier
    results" (O12, as in the Introduction); §7 "a real link budget would sit between our criteria" -> "we expect ...
    because ..." (O8, see 3.4); §7 "Night is not the real Sun ... in preparation" -> Stage D; §7 "Choices made during
    the study ... (Table 10)" -> Stage B at p = 0.2 and 0.8 tests the coverage choice (E9); §7 and §5.4 rover cost ->
    "Modelled in [33]" (E14); §6 LCRNS comparison -> combined vs relay-alone coverage, "Section 2.2" (E13).
11. **Part 4 items that touch my wording:** §5.1 "only in the weeks of largest libration" -> "for about three days
    near each monthly maximum of Earth's elevation; SCI_1 not at all from January to late November 2028" (E7); the
    Table 2 reference stays; "Phase-2 mix", "v3", "Stage-A" -> "reference mix", "[14]", "Stage A" (W4, E26).

## Changelog (parts 1-3 and this file), by review item

**Errors**
- **E5** (3.7): the identity of full relay with "always linked" is now stated for the tested reference comparison
  and for five of the six fleets; a new paragraph explains why the teleoperated fleet differs (soft admission; 8 of 20
  seeds, up to 15.5 h and 2.4 t; 32.4 against 11.4 operator waits) with numbers checked in the raw CSV. 4.4 says
  operator comparisons use full relay as the reference and why.
- **E6** (3.5, Table 2): the largest gaps of SCI_1, pad A at 2 km and pad B at 3 km are marked as stretches before
  the first window, cut off at the series start; the caption says gaps include the series-end stretches; the
  footnote gives the mean and largest gaps between windows (582/623, 631/2,579, 580/634 h).
- **E7** (3.5): "rare moments of peak libration" replaced by "about three days near the monthly maxima of Earth's
  elevation", with window counts and means; SCI_1 has no window until 26 November 2028; PSR has one window a month
  through the series. Pad A at 2 km and pad B at 3 km described the same way.
- **E9** (4.2): the Stage B coverage choice is now tested at p = 0.2 and 0.8; the methods say so (the "Table 10"
  sentence itself is in part 5, see "For the lead" 10).
- **E10** (4.3): "the tables give the count" replaced by a rule (means over fewer than 20 seeds carry their count),
  and 4.4 explains that the uncensored p90 is undefined at 3 km pads under DTE (n_valid = 0 in all 20 seeds), which is
  why the censored measure is used.
- **E14** (4.4): one basis for the rover cost: 45 M$/yr = 450 M$ delivered over 10 years, Modelled in [33].
- **E20** (4.4, Appendix B): cell means carry Student-t intervals on 19 df (t = 2.09), not 1.96 standard errors.
- **E21** (abstract): broken sentence rewritten; reports mean absolute difference 0.028, largest -0.123, 17 points,
  two zero in both. 3.6 and Appendix A give the same numbers.
- **E22** (4.4): the throughput break-even paragraph reduced to one sentence (undefined: throughput saturates by
  p = 0.1 and rovers add nothing).
- **E23** (2.2, 3.7, Table 4): why the DRM-0 gap stands in (the only per-pass figure found), that it is a
  single-satellite stand-in, and that Stage E tests 2 h, 24 h and periodic gaps with the DRM-0 and RC 3.1 periods.
- **E24** (references): renumbered by first citation across all parts; internal pointers removed; [17], [20], [29],
  [30], [32] completed or replaced; [2], [4], [5], [34], [35] completed.
- **E25** (abstract): "eleven relay coverages from 0.05 to 1.0".
- **E26** (parts 1-3): `&#8239;%` everywhere; "M$" for all money (4,820 M$, 450 M$, 45 M$); "Stage A" ... "Stage E"
  and "Stage A2" in one spelling.
- **Unverified statements under the E-table:** all five checked; see "What was checked" (map period softened, Jun
  confirmed, LTV quotes corrected to verbatim, Sun elevation from SPICE/DE440 with the 1.54 deg tilt, Acton confirmed).

**Overclaims**
- **O1, O2, O3, O5** (abstract result block, 1, 4.1): the feedstock assumption (500 of ~530 t ready is bulk; 200 t/yr to
  the never-linked site), the lander split, "assumed to see every route point", the lightly used fleet and "at
  coverage 0.5, strict" are written into the abstract placeholders and Section 4.1; the Introduction's "not claimed"
  paragraph adds the lightly used fleet.
- **O8** (3.4): "the centre criteria bracket that loss" replaced by "we expect a real link to fall between ... but
  terrain multipath could make it worse", with the reason (station anywhere on the disc; Fresnel radii; 0.5 deg clears
  the first zone beyond about 0.5 km).
- **O10** (3.6): "at our crest points".
- **O12** (abstract, contribution 2, 3.7): "verified" removed; "checked against analytic and earlier results" with a
  definition in 3.7 (regression identity plus analytic tests; not validated against operations).
- **O13** (abstract): "We found no published analysis of what these gaps cost a cargo fleet."

**Statistics**
- **S1** (3.7, 4.4): booking at pickup, completion share and censored p90 with the "≥" rule defined.
- **S2** (4.4): geometric-mean ratio, Wilcoxon signed-rank, medians for the main delay comparisons.
- **S3** (4.3): intervals include calendar variation over four start years; key cells per start year.
- **S4, E2, E3** (4.4): bootstrap draws as a placeholder (>= 2,000), every draw kept, shares of Δp <= 0 and beyond
  full coverage reported, paired bootstrap of the strategic step against one rover.
- **S5** (4.4): the law is descriptive; cross-validation barely separates the forms; the hyperbolic (and power with
  g <= 1) form cannot place the 2x target above (1 - c)/2.
- **S6** (4.4): targets below the lowest level are reported as "at most"; the envelope hides non-monotone cells and
  we say where.
- **S8** (4.2): the second and third Stage B coverages.
- **S10** (3.7): the fixed night starts at hour 0 of every run whatever the start year; Stage D uses the real Sun.
- **S11** (Table 4, 3.7, 4.2): soft and hard operator limits as separate rows; Stage A2.
- **S12** (abstract block, 1, Table 4): the relay sees every route point.
- **S13** (3.7, Table 4): exponential vs near-periodic gaps; Stage E.
- **S14** (3.3): 2.5 m tied to VIPER's mast [40]; antenna height matters at crests (0.384 vs 0.593 at BASE) and not at
  the oxygen plant.
- **S15** (Table 4, 4.2): Stage E sweeps the intervention rate x0.5 and x2.
- **S16** (4.4): six primary comparisons named; intervals per comparison, not adjusted.
- **S17** (Table 5 caption): cost per landed kilogram demoted to a secondary output.
- **S18** (4.1, 4.3, Table 5): the operator count rises at +2 and +3 rovers; shared cells are a check, counted
  separately; the never-linked filter stays in Table 4.

**Writing**
- **W1** (abstract): cut to ~170 words outside the result block; one number per claim.
- **W3** (1): "fails badly" -> "does not hold" with the numbers; "almost never linked" -> 55 of 56 pad legs.
- **W4** (all): code tokens and project labels replaced (see Conventions); Phase 2 defined once in 4.1 from
  `lunarsim/phases.py`; md5 and "byte-identical" moved out (to Availability, part 5).
- **W5** (1, 2.2, 3.4, 3.7): RQ1, RQ2, RQ4, the contract sentence, the mast-mode sentence and the identity
  paragraph split; the throughput break-even paragraph removed (E22). The abstract's list of factors shortened.
- **W7** (1, 2): flags removed from the Introduction and Related work; their definition moved to the start of
  Section 3.
- **W8** (3.6, 4.4, appendices): Table 4 (now A1) and the registration and epoch paragraphs moved to Appendix A;
  old 4.4 (metrics) folded into Table 5 ("Main outputs" column and the caption's secondary outputs).
- **W9, W10** (1-3, Appendix B): jargon defined at first use where short (libration, discrete-event, SPICE, LOLA,
  Fresnel zone, X-band, apolune, frozen orbit, DRM-0, 3GPP, LEGS, DSN, PGDA, CLPS-class, MK1-class, common random
  numbers, cell, stage, mix, knee, pooled dispatch auction, bootstrap, cross-validation) and in the glossary
  (Table B1), which also covers the paired difference, Student-t interval, interventions per km, priority-1,
  deferral, look-ahead, completion share, censored delay, geometric-mean ratio and Wilcoxon test.

## Changelog, round 2: back half (parts 4-5), abstract result sentences and build (2026-10-22)

Written after all round-2 runs except Stage A's relay 0.05 cells, and after the round-2 `analyse_e21.py fit`. The
reply to the referee, item by item, is `paper/r1/RESPONSE_round2.md`. Nothing was committed.

**What changed**
- `part4_results.html` (Section 5) rewritten: 5.1 map; 5.2 throughput split (bulk / lander / returns), the feedstock
  bound, what the rest of the gap is (E4), relay restoration with its two conditions, rovers and mast; 5.3 completion
  share, censored 90th percentile (medians, geometric-mean ratios, Wilcoxon, year-blocked), relay curve, coverage
  targets (Table 7), law descriptive only; 5.4 strategic and look-ahead policies, the 2028 calendar (Figure 4);
  5.5 Stage B with all draws kept, the price, the strategic-minus-rover difference, p = 0.2 and 0.8; 5.6 operator
  demand as absolute peaks and seeds over staff, Stage A2, full relay against always (E5); 5.7 pads x comms,
  criterion re-read with censoring, deferral (Table 9); 5.8 Stage D (real Sun) and Stage E against their twins.
- `part5_back.html`: Discussion openings rewritten as findings with conditions (W2); Limitations updated (Stage D
  result, Stage E, A2, censoring, calendar, never-linked filter, untested busy fleet / antenna height / relay masks);
  Conclusions with conditions; Availability as a list with file names, md5 and "byte for byte" (W4).
- `part1_front.html`: abstract shortened (~240 words; the map-validation numbers moved out, W1) and its result
  sentences rewritten; the relay-level count and range are placeholders.
- **Results tables are 6-9** (6 DTE vs always by fleet; 7 coverage targets; 8 break-evens; 9 Stage C). **Figures
  are numbered by first mention**: Figure 4 is `r1_fig6_years.png`, Figure 5 `r1_fig4_breakeven.png`, Figure 6
  `r1_fig5_operators.png` (Figures 1-3 unchanged). Renaming the PNGs to match would be tidier; the captions in
  part 4 are the record.
- `build_r1.py` rewritten for the `_r2` files: Student-t cell intervals from `table_E21_cells_r2.csv`; medians,
  geometric-mean ratios and Wilcoxon p from `table_E21_effects_r2.csv`; year-blocked intervals from
  `E21_fit_r2.json`; the appendices are moved after the references; the build fails on an unfilled placeholder and
  on nan/inf in any value or in the assembled text, and asserts the data facts the wording depends on (for example
  the 2028 calendar effect, the reference mix's identity under the hard limit, the strict 0.8 cell above 0.7, no
  urgent item at 3 km pads, 72 h = no limit at relay 0.8). It prints a WARNING if a relay level restores less than
  95 % of the lost tonnage (then reword "Any relay restores" in 5.2, Discussion paragraph 2, the Conclusions and the
  abstract).
- **Computed in the build, not by the analysis** (light, ~15 s): Stage D paired effects (real Sun against fixed
  night, pairs by start year and seed, from `E21d_sun_r2.csv`); the local-feedstock DTE-vs-always loss (from
  `E21e_sensitivity_r2.csv`); the model-free break-evens for the look-ahead step and the mast at p = 0.5 and for one
  rover and the strategic step at p = 0.2 and 0.8, with the analysis's own bootstrap (`analyse_e21` functions,
  seed 1, 2,000 draws, every draw kept). The p = 0.5 rows are recomputed and asserted equal to `E21_fit_r2.json`.
  The analysis could own these later.
- Sunlit shares (Stage D) are read from `data/illumination/connecting_ridge/sun_link-v1.json`.

**Placeholders.** Removed: `R1-ABS-OPERATORS`, `R1-ISRU-BOUND-T`, `R1-LOST-ISRU-T`, `R1-LOSS-SHARE-ISRU`,
`R1-P90-ALWAYS`, `R1-P90-DTE`, `R1-PADS-05-GAIN`, `R1-PADS-3-LOSS`, `R1-PTM-DTE`, `R1-PTM-FULL`,
`R1-RELAY01-RESTORE-PCT`, `R1-T-LANDED-LOSS-PCT`, `R1-T-STRATEGIC-DTE`, `R1-WAIT-STRATEGIC-DTE`,
`R1-WAIT-STRICT-DTE`. Redefined: `R1-T-DTE` / `R1-T-ALWAYS` / `R1-T-LOSS-PCT` / `R1-P1-COMPLETION-DTE` are now the
supervised-strict fleet (the analysis's primary row; the reference mix differs by under 1 %), and
`R1-OP-PEAK-TELEOP-DTE` is the absolute peak, not the peak/mean ratio. About 220 were added, in groups:
counts and compute (`R1-N-*`, `R1-CELLS-*`, `R1-COMPUTE-*`, `R1-UTIL-*`, `R1-BOOT-DRAWS`, `R1-LAW-BOOT`,
`R1-A-RELAY-COUNT`, `R1-P-LOW`), 5.1 (`R1-FRAC-*`), 5.2 (`R1-T-*`, `R1-BULK-*`, `R1-LANDED-*`, `R1-BOUND-T`,
`R1-LOST-NEVER-T`, `R1-LOSS-SHARE-NEVER`, `R1-LOCAL-*`, `R1-PICKED/DROPPED/BACKLOG-DTE`, `R1-READY-GAP`,
`R1-RESTORE-*`, `R1-KNEE-REMARK`), 5.3 (`R1-COMP-*`, `R1-CP90-*`, `R1-STRICT-CP90-CURVE`, `R1-REL05-*`,
`R1-P-2X-*`, `R1-P-15X-STRICT`, `R1-NONMONO`, `R1-CV-STRICT`, `R1-INS-STRICT`), 5.4 (`R1-STRAT-*`, `R1-AVOID-*`,
`R1-WAIT-*`), 5.5 (`R1-B-*`, `R1-DP-*`, `R1-SHARE-*`, `R1-MUSD-PER-01-ABS`, `R1-PRICE-UPPER-NOTE`), 5.6
(`R1-OP-*`, `R1-A2-*`, `R1-FR-*`), 5.7 (`R1-C-*`, `R1-CRIT-*`, `R1-DEFER*`, `R1-NODEFER-*`), 5.8 (`R1-SUN-*`,
`R1-D-*`, `R1-E-*`), Discussion (`R1-LCRNS-RATIO`). `paper/r1/values.json` lists every filled value.

**When Stage A's relay 0.05 cells land** (re-run `analyse_e21.py fit --round r2`, then this build): the abstract,
Sections 5.2, 5.3, 6 and 8 and Table 5 switch to "eleven relay coverages from 0.05", the lowest level, its
restoration and completion shares, the knee, the strict curve phrase and the "≤ lowest level" targets by
themselves. Check by hand: (1) the WARNING above; (2) whether the strategic and look-ahead 2x targets are still
below the lowest level (Table 7, Section 5.3); (3) that the price and Δp rows still match `E21_fit_r2.json` (the
build asserts it); (4) Section 5.2's sentence "a relay that is up a few hours at a time opens every route" (the
mean up period at 0.05 is 0.40 h).

**Open points for the lead.** (a) Part 3's list of six primary comparisons (4.4) and the analysis's
`primary_comparisons` (E21_fit_r2.json) differ in detail; the text follows part 3 and reports the analysis's six
rows within it. (b) Table 7's target intervals come from the law bootstrap, 400 draws (stated in its caption and
in Section 7), not 2,000. (c) Part 3 already says "eleven coverage levels"; until the 0.05 cells land Table 5 reads
72 Stage A cells. (d) One extra rover's Δp interval excludes zero while its paired tests do not; the text says so.
(e) The real Sun lengthens urgent delay about fivefold at p = 0.5 (Stage D); the coverage targets and the price
are for the fixed night share, and the text says so.

### 22 Oct 2026, evening (LEAD): the relay 0.05 cells are dropped from round 2
Stage A's six relay-0.05 cells (cells 60-65) did not finish: no run completed inside a 540 s chunk, and the background
job (2 workers, long limit) was stopped by the host when the 8 GB machine ran low on memory, with no row written.
The referee did not ask for 0.05 (Should 11 asks for 0.6 and 0.7, both run). Part 3 now says ten coverage levels
and that the throughput knee lies at or below 0.1; RESPONSE_round2.md says the same. The notes above about "when
the 0.05 cells land" no longer apply unless the owner asks for the runs (they need a quiet machine and, likely,
per-run row writes). Also added this evening: the route tie-break limitation (Section 7, from
results/E21_route_ties.json, B-52b). Still open: the 2028 mechanism of the strategic fleet (B-55) for Section 5.4.

### 22 Oct 2026, late (LEAD): the 2028 mechanism (B-55) and the plume's waits
Section 5.4: the round-1/agent explanation (science site without a window) is replaced by the measured mechanism from
results/E21_strategic_years.json (one dark route sample on ISRU->CONSTR, Jan 2028 - Jul 2029, 79 % of 2028's stranded
rover-hours; swap test; Earth's bearing at high elevation by year). New placeholders R1-SY-*; the build asserts the
facts the wording uses (first link after 2028, ISRU->CONSTR the top leg, every swap seed lowest in 2028, 2028's high
Earth outside the sample's bearing window). Section 5.8: the plume keep-out raises DTE waits for Earth 977 -> 2,786
rover-hours (ratio 2.43 [1.91, 3.08], E21e), with tonnage and urgent delay unchanged (R1-E-PLUME-DTE-WAIT). Discussion
and Conclusions: the strategic rule's risk and the untested middle rule.

### DONE (22 Oct, LEAD; was OPEN): the strategic policy's asymmetry, stated and measured (Stage F, B-57)
Table 4 and the never-linked-jobs rule together make plain `strategic` clairvoyant about never-linked samples only:
an intervention drawn on a never-linked sample makes the job infinite, so dispatch avoids it or refuses it at start
and the draw is repeated, while a draw on a long-dark (finite) sample is accepted and waited out. The first is what
lets strategic serve the oxygen plant (bulk 396 t under DTE); the second is what makes 2028 collapse. B-57 (Stage F)
measures it: a no-clairvoyance `never_linked: strand` variant, refusal counts by start year, and the legs that hold
never-linked samples; plus the bounded-wait rule in two variants. Sections 5.4, 6, 7 and 8 and the abstract's
strategic sentence must be revisited with those results (state the asymmetry in Section 7 in any case).
Done 22 Oct: Stage F (results/E21f_bounded_r2.csv, table_E21f_bounded_r2.csv, E21_fit_r2.json["bounded"]) is in
the paper as R1-F-* placeholders (build asserts: no re-draws with a relay; strand = strategic with a relay; the
stranding fleet below strict; refuse variants keep no ISRU haul and avoid 2028, re-draw variants the reverse; pool
full of CONSTR->ISRU at the last moment). Text: abstract strategic sentence, Table 4 strategic row, Section 4.2 Stage F
paragraph, Table 5 row F, compute paragraph (Stage F ran with two workers: summed run times), Section 5.4 (free
second chance paragraph, bounded-rule paragraph, relay independence), Figure 4 caption, Section 5.8 (intervention
rate "with its free re-draw"), Discussion paragraph 3, Limitations (two features of the rule; the auction pool),
Conclusions (third finding; planning point on reaching a stopped rover), RESPONSE_round2.md.
Done 22 Oct (later): B-59 Stage G (results/E21g_rescue_r2.csv, table_E21g_rescue_r2.csv, E21_fit_r2.json["rescue"])
as R1-G-* placeholders (asserts: help <= 168 h indistinguishable from the re-draw in tonnage and censored delay; help
at 720 h = strict tonnage but more urgent completion; completion break-even beyond 720 h in every draw; 2028 still
collapses). The framing is now rescue time: within a week = free re-draw, a month = strict tonnage but the urgent gain
kept, none = 42 t. Limitations: the strict/look-ahead pools never fill (R1-F-POOL-STRICT).
