# Paper R-1 ("Earth in sight"), parts 1-3: notes for the author of the back half

Written 2026-10-22. Sources: `research_notes/Lunar communications and visibility/earth_visibility_prior_art.md`,
`.team/reports.md` (B-40, B-41, B-42 DONE), `lunarsim/comms.py`, `tools/comms/earth_link.py`,
`experiments/phase4/run_phase4.py`, `experiments/phase4/analyse_e21.py` (docstring only), `.team/PLAN-phase4-design.md` §10,
`data/comms/connecting_ridge/earth_link-v1.json` (provenance block and a light count of legs, see below), and the v3
parts for style. No existing file was edited. Nothing was committed.

| File | Content | Prose words (tables excluded) |
|---|---|---|
| `part1_front.html` | `<head>` (`../style.css`), title, author, affiliation, abstract (12 placeholders), keywords, Section 1 Introduction (RQ1-RQ4, three contributions, what is not claimed and the flags, roadmap) | ~1,930 (abstract ~340, intro ~1,590) |
| `part2_related.html` | Section 2 Related work (2.1-2.5) and Table 1 | ~1,810 |
| `part3_methods.html` | Section 3 Data and model (3.1-3.7, Tables 2-5), Section 4 Experiment E21 (4.1-4.6, Table 6; 5 placeholders) | ~4,590 |

The methods part is over the ~3,000 target because the brief asks for the site table, the legs headline, the full
validation and the engine rules. If it must shrink: move Table 4 and the registration/epoch paragraphs of 3.6 to an
appendix, and fold 4.4 (metrics) into Table 6.

## Title

Chosen (in `<title>` and `<h1 id="r1-title">`): **What Earth's Horizon Costs a Lunar Base: Terrain-Masked
Communication Windows in South-Pole Cargo Logistics**. It is the owner's example, it names the cost (the paper's
question) before the method, and it matches the guided story already titled "What Earth's horizon costs (E21)".

Options considered:
1. What Earth's Horizon Costs a Lunar Base: Terrain-Masked Communication Windows in South-Pole Cargo Logistics (chosen).
2. Earth in Sight: Terrain-Masked Direct-to-Earth Windows, Relay Coverage and Rover Autonomy in South-Pole Cargo Logistics (the thread's name; more complete, less direct).
3. Waiting for Earth: Link Windows Along Real Routes and the Relay, Autonomy and Rover Break-Even at a Lunar South-Pole Base (names the break-even, but long and the hook is weaker).

## Conventions

- Skeleton as v3: `<!DOCTYPE html>` + `<head>` only in part 1 (no closing `</body>`, as v3 part 1); parts 2-3 are bare fragments starting with `<h2>`.
- Classes: `.authors`, `.affil`, `.abstract` + `.kw`, `.tabcap` with `<b>Table n.</b>`, `table.small`, `td/th.num`, `ul.contrib`, `ol` for RQs, `.mono`. No figures yet.
- Flags as v3 (Measured / Spec / Modelled / Assumed), in parentheses at first use. Our link fractions are Modelled.
- Ids, all prefixed `r1-`: `r1-title`, `r1-abstract`, `r1-sec-intro`, `r1-sec-related`, `r1-tab-prior`, `r1-sec-data`, `r1-tab-sites`, `r1-tab-padlegs`, `r1-tab-avgvisib`, `r1-tab-rules`, `r1-sec-e21`, `r1-tab-stages`.
- Affiliation links use the URLs in the brief (`github.com/azizjonrahimov/Lunar-Haul`, `azizjonrahimov.github.io/Lunar-Haul/`). v3 used `.../lunar-logistics-research`; check which one resolves before release.
- `paper/build.py` does not know about `paper/r1/` yet. Proposed assembly: `r1/part1_front.html`, `r1/part2_related.html`, `r1/part3_methods.html`, `r1/part4_results.html`, `r1/part5_back.html` into `paper/r1/paper.html`; placeholders are `{{R1-...}}` (not v3's `[[...]]`), so the build needs a filler or they are replaced by hand.

### Numbering the back half must continue

- Sections promised in the roadmap: **5 Results, 6 Discussion, 7 Limitations, 8 Conclusions**, then Availability and References. Section 4.5 refers to the relay price as an equivalence ("Section 4.5"); Section 2.2 is referred to for "no public price".
- Tables used: 1 (prior work), 2 (sites and pads), 3 (pad legs by standoff), 4 (map validation), 5 (link rules), 6 (E21 stages). Results tables start at **Table 7**.
- Figures: none yet. Suggested: Fig. 1 map of sites and legs coloured by link fraction with Earth's 16 deg wedge (from `earth_link-v1.json`); Fig. 2 Earth's elevation at BASE against the horizon over one month with the windows shaded (the hourly track `earth_track-v1.json.gz`); Fig. 3 urgent p90 against relay coverage per mix with the fitted law (`fig_E21_delay_coverage.csv`); Fig. 4 peak against mean linked operator demand (`fig_E21_operator_demand.csv`).
- Research questions RQ1-RQ4 (numbered for this paper, not continuing v3's RQ6-RQ9). Hypotheses H1-H6 of the research note are not named in parts 1-3; the results can map to them (H1 throughput and urgent wait under DTE; H2 supervised policies; H3 the saturating coverage curve; H4 dead zones and the mast; H5 operator compression; H6 untestable in E21 because the night is not the real Sun, see limitations).

### Limitations already flagged in parts 1-3 (to repeat in Section 7)

Geometric link criteria, no link budget, no Fresnel loss, no ground-station scheduling; parametric relay that sees
every route point (Assumed); the slope-only route stands for every lighting case; pad-to-pad legs inferred from end
points; night not phased with the real Sun (H6 not tested); no crewed local driving; uniform placement of strategic
interventions; intervention rates from v3's Assumed hazard; the deferral limit (24 h) motivated by development runs;
stage B coverage (0.5) fixed after stage A; 20 seeds; LTV capital $450 M / 10 yr; one site and layout; the 0.032 map
difference at BASE not decomposed.

## Every placeholder (17 occurrences, 17 distinct)

Grep: `grep -o "{{R1-[^}]*}}" paper/r1/*.html`. "Default" = mix `default` (the P2 reference fleet). Stage A rows of
`results/table_E21.csv` have `stage=A, criterion=any_part, pad_standoff_km=1, defer_wait_h=24, mast=none,
extra_rovers=0`. Report every number as mean with its 95 % CI.

### part1_front.html (abstract)

| # | Placeholder | Content | Source |
|---|---|---|---|
| 1 | `{{R1-T-DTE}}` | delivered t/yr inside the year, DTE only, default mix | `table_E21.csv`: stage A, comms=dte, mix=default, `delivered_t_in_year` (+ `_ci95`) |
| 2 | `{{R1-T-ALWAYS}}` | same, link always up | `table_E21.csv`: comms=always, mix=default |
| 3 | `{{R1-T-LOSS-PCT}}` | paired loss in %, e.g. "-42 % [-44, -40]" | `table_E21_effects.csv`: family=dte_vs_always, mix=default, metric=delivered_t_in_year: `rel_pct`; CI = `ci_lo`, `ci_hi` divided by `ref_mean` |
| 4 | `{{R1-LOSS-SHARE-ISRU}}` | share of the DTE loss that was cargo for ISRU (never linked) | `E21_fit.json` `throughput.lost_at_never_linked_t.mean / throughput.gap_t.mean`. **Check the mix:** the throughput block is built from the supervised-strict runs; if it cannot be computed for the default mix, switch items 1-3 and 5-7 to mix=supervised_strict (the guided story already uses that row) and say "an all-supervised fleet" in the abstract |
| 5 | `{{R1-P90-ALWAYS}}` | urgent p90 delay (h), always, default | `table_E21.csv` `delay_prio1_p90_h` |
| 6 | `{{R1-P90-DTE}}` | urgent p90 delay (h), DTE only, default | `table_E21.csv` `delay_prio1_p90_h` |
| 7 | `{{R1-RELAY01-RESTORE-PCT}}` | (T(relay 0.1) - T(dte)) / (T(always) - T(dte)) in %, default | `table_E21.csv` `delivered_t_in_year`, stage A, comms dte+relay coverage 0.1 vs dte vs always. Cross-check with `table_E21_breakeven.csv` row "relay coverage 0.1" (supervised strict) |
| 8 | `{{R1-ROVER-GAIN-T}}` | t/yr gained by +1 supervised LTV at DTE (strict, no mast) | `table_E21_breakeven.csv` option "+1 supervised LTV", `gain_vs_dte`; CI from `table_E21_effects.csv` family=rovers_vs_0, stage B, p=0, extra_rovers=1, policy=strict, mast=none |
| 9 | `{{R1-MAST-GAIN-T}}` | t/yr gained by the BASE 10 m mast at DTE (strict, +0) | `table_E21_breakeven.csv` option "BASE mast 10 m", `gain_vs_dte`; CI from `table_E21_effects.csv` family=mast_vs_none |
| 10 | `{{R1-DP-ONE-LTV}}` | relay coverage one extra rover is worth in urgent p90 at p = 0.5, e.g. "0.18 [0.02, 0.41]" | `E21_fit.json` `breakeven_delay.delta_p_one_ltv` and `delta_p_one_ltv_ci95`; same as `table_E21_breakeven_delay.csv` row "+1 rover": `delta_p`, `delta_p_ci95_lo/hi` |
| 11 | `{{R1-MUSD-PER-01}}` | break-even relay price, M$/yr per 0.1 coverage, with CI | `E21_fit.json` `breakeven_delay["musd_per_year_per_0.1_coverage"]` and `_ci95`. Also report `share_draws_one_ltv_not_positive` (if > 0 the upper CI bound is unbounded; say so) |
| 12 | `{{R1-OP-PEAK-TELEOP-DTE}}` | peak linked operator demand, teleop 4 s, DTE only (mean and CI; add max and seeds over staffing) | `fig_E21_operator_demand.csv` (or `E21_fit.json` `operators`): mix=teleop_4s, comms=dte: `peak_mean`, `peak_ci95`, `peak_max`, `seeds_over_staffing` of `n_seeds`; staff = `n_operators` (3) |

### part3_methods.html

| # | Placeholder | Content | Source |
|---|---|---|---|
| 13 | `{{R1-A-KNEE-P}}` | the stage A throughput knee: smallest p with mean supervised-strict `delivered_t_in_year` >= 0.95 x the p = 1 value, written "p = 0.1" | `run_phase4.knee_coverage(table_E21.csv)`, printed by the `e21b` stage; the code comment in `run_phase4.py` (LEAD 22 Oct) says 0.1 |
| 14 | `{{R1-COMPUTE-H}}` | total wall-clock hours of E21 | sum of `run_s` over `results/E21a_comms_autonomy.csv`, `E21b_breakeven.csv`, `E21c_pads_criterion.csv` / 3600 (excludes start-up overhead; or LEAD's run log) |
| 15 | `{{R1-COMPUTE-A-MIN}}` | stage A minutes | sum of `run_s` in `E21a_comms_autonomy.csv` / 60 |
| 16 | `{{R1-COMPUTE-B-MIN}}` | stage B minutes | sum of `run_s` in `E21b_breakeven.csv` / 60 |
| 17 | `{{R1-COMPUTE-C-MIN}}` | stage C minutes | sum of `run_s` in `E21c_pads_criterion.csv` / 60 |

Sentences whose wording assumes a direction seen in the current tables (re-read when the numbers are filled):
abstract "a relay in view 10 % of the time restores ... of the lost cargo" (assumes a gain), "one extra supervised
rover is worth ... of relay coverage" (assumes Δp > 0; 2.5 % of bootstrap draws were not positive in the current
`E21_fit.json`), and Section 4.2 "that knee was the lowest level tested". Section 4.5's "no smooth form fits the slow
decline between p = 0.2 and 1 well enough to invert there" is taken from the `analyse_e21.py` docstring.

`E21_fit.json` currently says `n_rows: 2480`; the three raw CSVs hold 1,200 + 640 + 720 = 2,560 rows (the design count
written in the paper). The fit file probably predates the end of stage C: rerun `analyse_e21.py fit` before filling.

## Numbers written in parts 1-3 and where they come from

All data and validation numbers are already measured and written in: site and pad table (B-40 table), leg counts
101/182 and 138/182 (B-40), Horizons 1.0e-6 / 5.5e-7 deg / 0.0006" over 4,465 epochs, map comparison -0.004 / 0.028 /
15 of 17, BASE 0.471 / 0.503 / 0.593 / 0.384 / 0.597, horizon +2.9 / -1.26 deg, 18.6-yr 0.580, years 0.546-0.626,
windows 16.0 / 14.1 / 12.1 d (B-40 and the `avgvisib_check` and `horizons_check` blocks of `earth_link-v1.json`).
Computed here (light read of the committed link file with `lunarsim.comms.EarthLink.summary`): in the E21 network
(7 sites + the two 1 km pads, 70 directed legs) 28 legs never linked under any_part, 50 under both centre criteria;
mean leg fraction 0.174 (0.195 with the mast); 13 of 42 site-to-site legs never linked. Unit-test count (25 functions,
one parametrised over three dispatch rules) by `grep -c "^def test_"`.

## References (numbered by first appearance in parts 1-3)

[1] S. Bryant. "Lunar Pole Illumination and Communications Maps Computed from Goldstone Solar System Radar Elevation Data." *The Interplanetary Network Progress Report* 42-176, Jet Propulsion Laboratory, 15 February 2009. https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.pdf

[2] D. De Rosa, B. Bussey, J. T. Cahill, T. Lutz, I. Crawford, T. Hackwill, S. van Gasselt, G. Neukum, L. Witte, A. McGovern, J. D. Carpenter. "Characterisation of potential landing sites for the European Space Agency's Lunar Lander project." *Planetary and Space Science* 74, 2012. doi:10.1016/j.pss.2012.08.002; https://arxiv.org/abs/1208.5587

[3] M. C. Scardelletti, M. R. Gasper, R. C. Reinhart, M. J. Zemba, J. L. Rock, S. R. Oleson, E. R. Turnbull. "Lunar Surface Network Relay Terminal: A Lunar Communications Platform." 40th International Communications Satellite Systems Conference (ICSSC), Bradford, UK, 23-26 October 2023. NTRS 20230013361. https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf

[4] W. W. Jun, T. Tanaka, P. Carter, R. L. Anderson, S. Bhamidipati, K.-M. Cheung. "A Rapid, Low-Cost Path to Lunar Communication and Navigation." IEEE Aerospace Conference, Big Sky, MT, 2025 (JPL-hosted version). https://www-robotics.jpl.nasa.gov/media/documents/A_Rapid_Low-Cost_Path_to_Lunar_Communication_and_Navigation.pdf

[5] H. L. Litaker, Z. Q. Li, K. H. Beaton, J. F. Lewis. *Lunar Terrain Vehicle (LTV) Remote Teleoperation Studies Under Four Lunar Communication Latencies*. NASA TM-20240001217, 2024; follow-up NTRS 20240011392, 2025. https://ntrs.nasa.gov/citations/20240001217 ; https://ntrs.nasa.gov/citations/20240011392 (v3 reference [29])

[6] M. Shirley, E. Balaban. "An Overview of Mission Planning for the VIPER Rover." SpaceOps 2022 Mission Planning Workshop, 2 June 2022. https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf

[7] N. Otten, D. Wettergreen, W. Whittaker. "Strategic Autonomy for Reducing Risk of Sun-Synchronous Lunar Polar Exploration." *Field and Service Robotics* (FSR 2017), Springer, 2018. https://www.ri.cmu.edu/app/uploads/2018/01/FSR_2017_Otten_66.pdf ; N. Otten, *Planning for Sun-Synchronous Lunar Polar Roving*, PhD thesis, Carnegie Mellon University, 2018, https://www.ri.cmu.edu/app/uploads/2018/01/thesis_otten.pdf

[8] A. Dwyer Cianciolo. "Artemis Human Landing System Update." NASA LaRC/ARC EDL Summer Seminar Series, August 2024. NTRS 20240009596. https://ntrs.nasa.gov/api/citations/20240009596/downloads/ArtemisHLSUpdate_2024.pdf

[9] T. George, M. A. Rubio, S. J. Lawrence, P. Curell. "Artemis III Site Selection Update: Downselection From Thirteen to Nine Candidate Regions." Lunar and Planetary Science Conference, The Woodlands, TX, March 2026. NTRS 20250011660. https://ntrs.nasa.gov/citations/20250011660

[10] J. Esper, G. Heckler, J. Verville, G. Ryden. "NASA's Lunar Communications Relay and Navigation Systems (LCRNS)." 18th International Conference on Space Operations (SpaceOps 2025), Montreal, 26-30 May 2025. NTRS 20250003321. https://ntrs.nasa.gov/api/citations/20250003321/downloads/LCRNS_Esper_257.pdf

[11] NASA. "NASA Selects Lunar Relay Contractor for Near Space Network Services." News release, 17 September 2024. https://www.nasa.gov/news-release/nasa-selects-lunar-relay-contractor-for-near-space-network-services

[12] E. Mazarico, G. A. Neumann, D. E. Smith, M. T. Zuber, M. H. Torrence. "Illumination conditions of the lunar polar regions using LOLA topography." *Icarus* 211:1066-1081, 2011. doi:10.1016/j.icarus.2010.10.030. LOLA average Earth-visibility maps: PGDA product 69, https://pgda.gsfc.nasa.gov/products/69

[13] H. Inoue, S. Adachi. "Spatio-Temporal Path Planning for Lunar Polar Exploration with Robustness against Schedule Delay." *Transactions of the Japan Society for Aeronautical and Space Sciences* 64(6):304-311, 2021. doi:10.2322/tjsass.64.304

[14] A. Rahimov. *Where the Lander Lands: Landing Precision, Pad Standoff, Plume Keep-Out and Rover Autonomy Priced in Lunar Surface Logistics*. Preprint, version 3, October 2026. (Our previous paper; DOI to be assigned on deposit.)

[15] P. Gläser, F. Scholten, D. De Rosa, R. M. Figuera, J. Oberst, E. Mazarico, G. Neumann, M. S. Robinson. "Illumination conditions at the lunar south pole using high resolution Digital Terrain Models from LOLA." *Icarus* 243:79-90, 2014. doi:10.1016/j.icarus.2014.08.013; https://elib.dlr.de/94240

[16] E. Peña-Asensio, Á.-S. Neira-Acosta, J. M. Sánchez-Lozano. "Evaluating potential landing sites for the Artemis III mission using a multi-criteria decision making approach." arXiv:2406.19863, 2024 (accepted in *Acta Astronautica*). https://arxiv.org/abs/2406.19863

[17] "Lunar Terrain-Driven Earth Visibility Analysis for South Polar Moon-Based Observations." *IEEE Geoscience and Remote Sensing Letters* 22, 2025. ADS 2025IGRSL..22L1520W. https://ui.adsabs.harvard.edu/abs/2025IGRSL..22L1520W/abstract (authors not verified; abstract only)

[18] G. Ryden, M. Volle. *NASA Lunar Communications Relay and Navigation Systems (LCRNS) Reference Constellation 3.1*. NASA white paper, 2025. NTRS 20250002698. https://ntrs.nasa.gov/citations/20250002698

[19] UNOOSA International Committee on GNSS, Working Group B, Lunar PNT meeting, June 2024 (LCRNS service schedule slides). https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_01_02.pdf

[20] Wikipedia. "IM-3" (revision of 15 October 2026). https://en.wikipedia.org/wiki/IM-3

[21] ESA. "The Moon where no satnav has gone before." https://www.esa.int/Applications/Navigation/The_Moon_where_no_satnav_has_gone_before ; SSTL. "ESA signs further order for commercial lunar relay services from SSTL," 2023. https://sstl.co.uk/media-hub/latest-news/2023/esa-signs-further-order-for-commercial-lunar-relay-services-from-sstl

[22] ESA. "ESA's Moonlight programme: pioneering the path for lunar exploration." https://esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration

[23] NASA. "VIPER: Lunar Operations." https://science.nasa.gov/mission/viper/lunar-operations/ (v3 reference [103])

[24] D. Gaines et al. "Productivity Challenges for Mars Rover Operations." JPL D-97908, 2016 (same title as the ICAPS 2016 workshop paper). https://ai.jpl.nasa.gov/public/documents/papers/gaines-report-roverProductivity.pdf

[25] E. L. Gralla, S. Shull, O. L. de Weck. "A modeling framework for interplanetary supply chains." AIAA SPACE 2006; S. A. Shull, *Integrated Modeling and Simulation of Lunar Exploration Campaign Logistics*, S.M. thesis, MIT, 2007. https://dspace.mit.edu/handle/1721.1/39711 (v3 [14])

[26] T. Ishimatsu, O. L. de Weck, J. A. Hoffman, Y. Ohkami, R. Shishko. "Generalized multicommodity network flow model for the Earth-Moon-Mars logistics system." *Journal of Spacecraft and Rockets* 53(1):25-38, 2016. https://dspace.mit.edu/handle/1721.1/110236 (v3 [15])

[27] K. Ho. *Dynamic Network Modeling for Spaceflight Logistics with Time-Expanded Networks*, PhD thesis, MIT, 2015; B. B. Jagannatha, K. Ho, "Event-driven network model for space mission optimization," *Journal of Spacecraft and Rockets* 57(3), 2020. https://arxiv.org/abs/1904.09364 (v3 [16])

[28] K. Ho et al. "Space logistics: a review." 2024. https://arxiv.org/abs/2306.01107 (v3 [65])

[29] Vera et al. "A Mesa agent-based benchmark of a lunar base." *PLOS ONE*, 2026. https://doi.org/10.1371/journal.pone.0348882 (v3 [69])

[30] Wang. "Agent Mars." 2026. https://arxiv.org/abs/2602.13291 (v3 [70])

[31] A. Krawciw, L. Antonyshyn, S. Lilge, N. Olmedo, F. Rehmatullah, M. Desjardins-Goulet, P. Toupin, T. D. Barfoot. "Sharing the load: autonomous multi-rover cargo transport." arXiv:2510.18766, 2025. https://arxiv.org/abs/2510.18766 (v3 [18])

[32] A. Krawciw et al. Autonomous cargo rover field test, 2026. https://arxiv.org/abs/2601.03371 (v3 [68])

[33] A. Rahimov. *Who Hauls the Habitat? A Verified Simulation Testbed, a Pooled Dispatch Marketplace and a Reference Design for Lunar Surface Logistics*. Preprint, version 2, October 2026. (v3 [113])

[34] M. K. Barker et al. "Improved LOLA elevation maps for south pole landing sites: error estimates and their impact on illumination conditions." *Planetary and Space Science* 203:105119, 2021; PGDA product 78 (Site01, 5 m). https://pgda.gsfc.nasa.gov/products/78 (v3 [95])

[35] M. K. Barker, E. Mazarico, G. A. Neumann, D. E. Smith, M. T. Zuber, J. W. Head, X. Sun. "A New View of the Lunar South Pole from the Lunar Orbiter Laser Altimeter (LOLA)." *The Planetary Science Journal* 4:183, 2023. doi:10.3847/PSJ/acf3e1; PGDA product 90, https://pgda.gsfc.nasa.gov/products/90 ; data doi:10.60903/gsfcpgda-lola-spole

[36] C. H. Acton. "Ancillary data services of NASA's Navigation and Ancillary Information Facility." *Planetary and Space Science* 44(1):65-70, 1996; NAIF generic kernels, https://naif.jpl.nasa.gov/pub/naif/generic_kernels/ ; `azlcpo_c`, https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/azlcpo_c.html

[37] A. M. Annex et al. "SpiceyPy: a Pythonic Wrapper for the SPICE Toolkit." *Journal of Open Source Software* 5(46):2050, 2020. doi:10.21105/joss.02050

[38] R. S. Park, W. M. Folkner, J. G. Williams, D. H. Boggs. "The JPL Planetary and Lunar Ephemerides DE440 and DE441." *The Astronomical Journal* 161:105, 2021. doi:10.3847/1538-3881/abd414

[39] JPL Solar System Dynamics. Horizons API. https://ssd-api.jpl.nasa.gov/doc/horizons.html ; request used: see `provenance.horizons_check.url` in `data/comms/connecting_ridge/earth_link-v1.json`

[40] LOLA team. `AVGVISIB_85S_060M_201608_EARTH` (IMG and label), LRO LOLA GDR illumination extras. http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.LBL

## What I could not verify (or verified only partly)

Checked this session by fetching the record or a search result: titles and authors of [1], [2], [3], [4] (as
submitted; acceptance not confirmed), [6], [7], [8], [9], [10], [12], [13], [15], [16], [18], [35], [37], [38], and the
PGDA 69 and 90 page statements. Not checked:

- **[36] Acton 1996**: title, volume and pages from memory.
- **[2] De Rosa**: volume 74 from the research note; page range not confirmed.
- **[17] IEEE GRSL 2025**: authors unknown (ADS returned 405; a web search found no record); content from the abstract snippet in the research note only.
- **[24] Gaines 2016**: title from search results, Medium.
- **[20], [21]**: IM-3 date from Wikipedia (Medium); Lunar Pathfinder's frequency plan and launch date conflict across sources, so the paper states only its orbit and purpose.
- **[23] VIPER operations page**: Medium in the research note.
- **[5] LTV "6 km per 24 h when operated remotely"** and "flawless high-bandwidth comms": from the repo's earlier note, not re-read this session.
- **Jun et al. [4] station location**: the search summary says Connecting Ridge; the research note says "a ridge near de Gerlache". The paper says "on the Connecting Ridge"; confirm in the PDF (it exceeded the fetch limit).
- **LCRNS "Spudis Ridge Peak"** identity and why Malapert is only 43 % in [10] (unresolved; the paper says the figure probably includes unstated constraints).
- **18.6 years** for the AVGVISIB map comes from the PGDA 69 page; the B-40 provenance notes the label's START/STOP fields as 2009-2013 (probably the LOLA data period). Check the `.LBL` before print.
- **"the terrain behind the map predates the 2021 and 2023 models we use"** is an inference from the map's 2016 release date, not a statement from its label.
- **Sun within ~1.5 deg of the horizon at the pole** is cited to v3 [14], which flagged it Assumed there; a primary source (lunar obliquity 1.54 deg) would be better.
- **Bryant's ±6.87 deg / ±8.16 deg**: the extracted PDF text shows "+", probably a lost "±" (research note); the paper rounds to ±6.9 / ±8.2 deg.
- **X-band wavelength 3.6 cm** for the Fresnel radius is our assumption (8.4 GHz); the 6 m and 19 m radii follow from it (research note, Computed).
- **Relay hop <= 0.065 s** and apolune ~19,150 km are derived in the research note from [18], not stated in [18].
- **LTV $450 M** delivered cost: `lunarsim/entities.py` comment (task order $219-220 M + MK1 delivery ~$234 M), labelled Modelled in v2; the primary sources are in v2's parameter table, not re-checked.
