# Earth in sight (R-1) and long shadows (R-2): prior art, data sources and a research design (current to 2026-10-22)

Grades: **High** = primary source read (full text, official page, data label or a live API response); **Medium** = abstract, search snippet, secondary report or partly read source; **Low** = untraceable, inconsistent or absence-of-evidence. **Computed** = arithmetic or a small data read done for this note (the data source is linked; method in the bullet). No code was edited and nothing heavy was run.

---

## Summary and novelty verdicts

**R-1 "Earth in sight": partly covered. The specific coupling looks new (Medium confidence).**
- Already published:
  - Earth-visibility percentages at south-pole sites: Bryant 2009, De Rosa et al. 2012, and the LOLA "average Earth visibility" maps (Mazarico method).
  - Statements that Earth is hidden for about 14 days each month.
  - LCRNS yearly coverage figures: direct-to-Earth (DTE) only 17–43 %, one relay 80–86 %, more relays 100 %.
  - Single-rover traverse planning that times drives around DTE "radio shadows": VIPER (Shirley & Balaban 2022), Otten et al. 2017 "strategic autonomy", Robust-STP3R 2021.
- Not found in about 35 searches and 25 full-text reads:
  - Any model that takes terrain-masked DTE windows along real routes, turns them into availability for a teleoperated or supervised rover *fleet*, and outputs cargo throughput, delivery delay and cost.
  - Any break-even between a relay, an autonomy upgrade and extra rovers.
- The closest papers are VIPER (DSN shadow/dropout events counted in Monte Carlo traverse tests), Otten 2017 (autonomy as the fix for blackouts) and Esper 2025 (relay coverage). None of them is about logistics.

**R-2 "long shadows": partly covered, and probably not worth a paper.**
- Mutual shading of tower arrays at the south pole is already studied: Halbach et al. ICES 2020/2021 and Ross et al. 2023 (Acta Astronautica).
- No source on lander shadows falling on arrays or routes was found. A simple calculation shows the effect is small (Computed):
  - A lander's *full* shadow (umbra) ends about 107 × its width from the vehicle, because the Sun is 0.53° wide. For a Starship HLS (9 m wide) that is about 0.97 km; for the MK1 class about 0.33 km.
  - Beyond that, the "2 km HLS shadow" is only partial shade (penumbra).
  - The shadow sweeps sideways at about 9 m/h at 1 km, so a fixed array 1 km away loses about 2 h of sun per lunar day (about 0.3 %).
  - The plume keep-out we already apply (≥ 1 km) is longer than every umbra except HLS.
- Recommendation: keep R-2 as a visual (F-33) and a one-line siting rule, not a research result.

**New data point found while checking (Computed, Medium):**
- Source: the public PDS/PGDA LOLA Earth-visibility map, 60 m/px, averaged over 18.6 years; "visible" means any part of the Earth's disc. Values at our sites:

| Site | Earth visible (fraction of time) |
|---|---|
| BASE | 0.50 |
| POWER | 0.57 |
| CONSTR | 0.52 |
| DEPOT | 0.37 |
| PSR | 0.11 |
| ISRU | 0.00 |
| SCI_1 | 0.00 |
| Pads | 0.06–0.58 |

- So two of our work sites never see Earth. Teleoperating there is impossible without a relay or a mast at the base. This makes R-1 concrete for our layout.

**Recommended data sources:**
- Ephemeris: NAIF SPICE through spiceypy, using `azlcpo` in the MOON_ME frame. Kernels: `de440s.bsp` 31 MB, `moon_pa_de440_200625.bpc` 12 MB, `moon_de440_250416.tf`, `pck00011.tpc`, `naif0012.tls`.
- Cross-check: the JPL Horizons API with `CENTER='coord@301'`. Verified by a live call in this note.
- Near-field horizon (≤ 8 km): our cached Site01 5 m DEM.
- Far-field horizon (8–300 km): PGDA product 90, `LDEM_80S_80MPP_ADJ.TIF` (181 MB cloud-optimised GeoTIFF). Only Earth's narrow azimuth wedge needs to be read, a few MB in windowed reads.
- Validation: `AVGVISIB_85S_060M_201608_EARTH` (51 MB, PDS/PGDA).

---

## Site facts for our terrain pack (Connecting Ridge, LOLA PGDA Site01)

- **Where the base is.** BASE = 89.439°S, 222.761°E (137.239°W), 1,957.6 m above the 1,737.4 km sphere. Converted from `data/terrain/connecting_ridge/sites.json` (base_xy 7450, 7510) plus `meta.json` (origin −19000, −20000; polar stereographic, R = 1,737,400 m) with rasterio.
  - Converted site positions:

| Site | Latitude | Longitude |
|---|---|---|
| DEPOT | 89.426°S | 222.9°E |
| POWER | 89.463°S | 222.9°E |
| CONSTR | 89.447°S | 222.8°E |
| ISRU | 89.464°S | 219.8°E |
| SCI_1 | 89.507°S | 220.6°E |
| PSR | 89.551°S | 215.1°E |
| DEM centre | 89.463°S | 222.5°E |

  - Source: our own files, via the PGDA Site01 product page — https://pgda.gsfc.nasa.gov/products/78 — **Computed / High**.
- **Earlier studies looked at the same spot.**
  - ESA's Lunar Lander region of interest "Connecting Ridge CR1" is at 89.4679°S, 137.411°W (grid −10.92, −11.88 km), 0.9 km from our BASE.
  - Bryant's (2009) radar-DEM peak "B1" is at grid −12.40, −13.68 km, 1.5 km away. That grid comes from a different DEM, so the match is approximate.
  - Sources: [De Rosa et al. 2012, Table 2](https://arxiv.org/abs/1208.5587); [Bryant 2009](https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.html) — **High** (positions) / **Computed** (distances).
- **Where Earth appears in our sky.** Live JPL Horizons call for the BASE site, Jan 2027, daily steps:
  - Earth's azimuth runs from 129.6° to 144.6°, measured clockwise from local north.
  - In our grid that is a bearing of about −8° to +8°, i.e. toward +y, the 0° meridian and Malapert.
  - Earth's elevation runs from −7.42° to +6.12°.
  - Earth's apparent diameter is 6,469–7,366″ (1.80°–2.05°).
  - So Earth's direction stays inside a wedge about 16° wide. A horizon mask is needed only in that wedge, not all 360°.
  - Source: [JPL Horizons API](https://ssd.jpl.nasa.gov/api/horizons.api) (request in §Q4) — **High** (API output) / **Computed** (grid bearing = local azimuth + 222.76° − 360°).
- **The ridge sees past the geometric horizon.** BASE is 1.96 km above the reference sphere, so over a smooth sphere its horizon dips 2.7° below horizontal.
  - Horizons flags Earth's upper limb as above the smooth horizon from about 9 to 25 Jan 2027: about 17 of 27 days, or about 60 %, against the textbook 50 %.
  - The terrain-masked map gives 0.50, so real terrain removes roughly 10 percentage points at BASE.
  - The time spans and criteria differ, so this is indicative only.
  - Sources: [Horizons output](https://ssd.jpl.nasa.gov/api/horizons.api); [AVGVISIB label](http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.LBL) — **Computed / Medium**.
- **Malapert may clip the bottom of Earth's swing.** Malapert peak (De Rosa MP1, grid −4.48, 121.8 km) lies at a bearing of about 3° from BASE, about 134 km away, inside Earth's wedge.
  - With Bryant's radar peak height of about 4.2 km, its top sits about −1.3° below BASE's horizontal.
  - Earth could therefore be hidden by Malapert between about −2.7° and −1.3°.
  - The heights come from different DEMs. This is the reason to fetch far-field terrain to about 200–300 km.
  - Sources: [De Rosa 2012](https://arxiv.org/abs/1208.5587); [Bryant 2009 Table 2](https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.pdf) — **Computed / Low**.

---

## Q1. Prior art on Earth visibility and DTE windows at the south pole (with terrain)

**What has been measured: long-run fractions at named sites and window lengths of about 14 days.** Nobody publishes the windows along rover routes, or the timing of windows relative to operations.

- **Why Earth comes and goes.** Earth wanders ±6.87° in latitude and ±8.16° in longitude in the lunar sky (the extracted PDF text shows "+", probably a lost "±"). So DTE from a polar base is possible only about half of each sidereal month (27.3 d). — [Bryant 2009, IPN PR 42-176](https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.pdf) — **High**
- **Bryant 2009 (JPL; 40 m radar DEM).**
  - Method: horizon masks for the area within 100 km of the pole, integrated over Earth's motion box, multi-year averages 2009–2028.
  - The best base site has 92 % solar and 51 % DTE availability.
  - Fine-resolution Earth visibility (any part / half / whole disc):

| Site | Any part | Half disc | Whole disc |
|---|---|---|---|
| B1 (connecting-ridge peak) | 65.2 % | 58.2 % | 51.3 % |
| A1–A4 (Shackleton rim) | 62–64 % | | |
| Malapert | 100 % | | |
| Leibnitz β | 100 % | | |

  - "The best visibility to some part of the Earth is around 65 percent"; "continuous polar lunar base coverage requires some kind of Earth relay". A radio reflector on Malapert was suggested.
  - No outage durations are given.
  - Source: [PDF](https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.pdf) — **High**
  - A 2010 SpaceOps version quotes "about 50 %" — [NTRS 20150008843](https://ntrs.nasa.gov/citations/20150008843) — **Medium** (snippet)
- **De Rosa et al. 2012 (ESA Lunar Lander; LOLA; JPL Horizons ephemeris; horizons out to 150 km, 720 azimuths).**
  - "The Earth centre follows a pattern of approximately ±6.5° in elevation every month, constrained to approximately ±8° in azimuth."
  - DTE windows follow "a regular pattern of ~14 days", and up to about 19 days near 85°S (Leibnitz β plateau).
  - At none of the regions (including Connecting Ridge CR1) does elevated terrain toward Earth cause "a significant decrease".
  - A 2° minimum elevation constraint costs "maximum 5 %" of availability.
  - The 14-day windows "demand a relatively high level of autonomy".
  - Source: [arXiv 1208.5587](https://arxiv.org/abs/1208.5587) (PSS 74, 2012) — **High**
- **LOLA "average Earth visibility" maps (method of Mazarico et al. 2011).**
  - Hourly steps over 18.6 years. "The Earth is considered visible if any part of its disc is not obscured."
  - South-pole versions: 65°S at 240 m, 75°S at 120 m, 85°S at 60 m (2016 release).
  - Sources: [PGDA product 69](https://pgda.gsfc.nasa.gov/products/69); [PDS label](http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.LBL) — **High**
  - The 2011 Icarus abstract itself covers only solar illumination — [NTRS 20120010094](https://ntrs.nasa.gov/citations/20120010094) — **High**
- **Our sites on that map (Computed, Medium).** Method:
  - Read the needed rows of `AVGVISIB_85S_060M_201608_EARTH.IMG` (int16, ×0.00004, 5058², 60 m, MOON_ME DE421) by HTTP range request.
  - Pixel index = 2529.5 + X/60 for the column and 2529.5 − Y/60 for the row.
  - Registration check: over our 16 km tile, the map correlates +0.39 with our DEM height; with the x-axis flipped it gives −0.24.
  - Values at the site pixel (maximum within a 5×5 window, i.e. ±150 m, in brackets):

| Site | Value | 5×5 max |
|---|---|---|
| BASE | 0.503 | 0.58 |
| POWER | 0.572 | |
| CONSTR | 0.522 | |
| DEPOT | 0.370 | |
| PSR | 0.113 | |
| ISRU | 0.000 | 0.00 |
| SCI_1 | 0.000 | 0.53 |
| PAD_A 0.5 km | 0.58 | |
| PAD_B 0.5 km | 0.35 | |
| PAD_A 1 km | 0.50 | |
| PAD_B 1 km | 0.26 | |
| PAD_A 2 km | 0.06 | |
| PAD_B 2 km | 0.41 | |
| PAD_A 3 km | 0.12 | |

  - Bryant's B1 grid point lands on a 0 pixel, which suggests his radar-DEM grid is offset from LOLA.
  - Caveats: these are surface-level values with no antenna height, an optimistic "any part of disc" criterion, and averages only (no time series).
  - Source: [IMG directory](http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/)
- **PSRs can still see Earth.** Earth climbs to about +6.8° while the Sun stays within about ±1.5°. So permanently shadowed ground can still have DTE windows; our PSR site is about 11 %.
  - Sources: [Bryant 2009](https://ipnpr.jpl.nasa.gov/progress_report/42-176/176C.pdf); [AVGVISIB map](http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/) — **Computed / Medium**
- **Artemis III.**
  - Landing requirement 4 is "Direct with Earth (DWE) communication; assume no comm relay is available".
  - Areas with Earth visibility below 25 % are screened out — [Dwyer Cianciolo 2024, HLS update](https://ntrs.nasa.gov/api/citations/20240009596/downloads/ArtemisHLSUpdate_2024.pdf) — **High**
  - The 2026 update: "If Artemis III employs a Direct-to-Earth (DTE) communication architecture, regions with greater Earth visibility are preferred". Constraints are evaluated "on a calendar basis", and individual regions give "limited viable opportunities" — [George et al., LPSC 2026, NTRS 20250011660](https://ntrs.nasa.gov/citations/20250011660) — **High**
  - No per-region DTE percentages are published.
- **Multi-criteria study of Artemis III sites.** It scores DTE from the 240 m Earth-visibility maps. Its top point "maintains direct communication with Earth for one-third of the time". Connecting Ridge (Site01) is not in its top 20 — [Peña-Asensio et al. 2024, arXiv 2406.19863](https://arxiv.org/abs/2406.19863) — **Medium**
- **IEEE GRSL 2025.** "Lunar Terrain-Driven Earth Visibility Analysis for South Polar Moon-Based Observations" uses LOLA over 80–90°S. Terrain obstruction cuts Earth visibility "by up to 80 %" on crater rims and at high latitude, so the smooth-sphere approximation fails there — [ADS 2025IGRSL..22L1520W](https://ui.adsabs.harvard.edu/abs/2025IGRSL..22L1520W/abstract) — **Medium** (abstract snippet only; full text not read)
- **Gläser et al.** Connecting Ridge gets 92.27 % sunlight at 2 m and 95.65 % at 10 m, with 3–5 days of continuous darkness. Illumination only; no Earth numbers in the abstracts.
  - Sources: [Icarus 243, 2014](https://elib.dlr.de/94240); [EPSC 2014](https://elib.dlr.de/94242); [PSS 2018](https://elib.dlr.de/119091) — **Medium**
- **NASA Glenn and JPL comms papers.**
  - "During the time Earth is not visible from the lunar south pole (nominally for 14 days every month), both Gateway and LCRNS can provide orbital relay service" — [Scardelletti et al., ICSSC 2023](https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf) — **High**
  - "Earth sets under the lunar horizon for two week intervals resulting in around a 50% availability for LOS access to Earth" — [Jun et al., IEEE Aerospace 2025 (JPL)](https://www-robotics.jpl.nasa.gov/media/documents/A_Rapid_Low-Cost_Path_to_Lunar_Communication_and_Navigation.pdf) — **High**
- **LCRNS figure.**
  - "DTE communications dramatically limits landing site availability, with 43% best case and 17% worse case coverage availability" (yearly average, 10-year line-of-sight simulation to Earth's centre).
  - Worst case is "Spudis Ridge Peak", best case "Mount Malapert Peak".
  - Source: [Esper et al., SpaceOps 2025](https://ntrs.nasa.gov/api/citations/20250003321/downloads/LCRNS_Esper_257.pdf) — **High** (quote) / **Low** (interpretation)
  - "Spudis Ridge" is not an IAU name I could confirm. If it means the Shackleton–de Gerlache ridge, NASA's own worst case would be our site. Malapert at 43 % conflicts with Bryant's 100 %, so the figure probably includes other constraints (ground stations or a link margin); this needs the full figure.
- **Visualisation.** Earth "bobs up and down, never veering far from 0° longitude" — [NASA SVS 5228](https://svs.gsfc.nasa.gov/5228) — **High**

## Q2. Prior art linking comms availability to surface operations throughput

**Verdict: partly covered. The coupling "terrain-masked DTE windows → teleop/supervised fleet availability → cargo delay and cost, versus relay or autonomy investment" was not found.**

What exists, closest first:

- **VIPER mission planning (NASA Ames).** Shirley & Balaban, June 2022 — [slides](https://www.nasa.gov/wp-content/uploads/2022/05/overview_of_mission_planning_for_the_viper_rover.pdf) — **High**
  - "Similar radio shadows are cast from a line-of-site radio link to ground stations"; "Sun and radio shadows move at speeds similar to VIPER's average speed"; "Traverses must be timed to avoid moving shadows".
  - DTE is one of four site-selection requirements. "Safe Havens" are places with ≤ 50 h of shadow while Earth is below the horizon.
  - Traverse planning is a cost-constrained travelling-salesman problem whose budget is "the time Earth is above the horizon at the site".
  - Monte-Carlo stress tests (SHERPA) model "DSN connection availability" and report DSN shadow and dropout counts and hours.
  - This is the closest prior art for "DTE windows → rover productivity". It covers one science rover and science stations, with no fleet, no cargo, and no relay or autonomy cost trade.
  - VIPER operations: 6–10 s latency, 24/7 operations, Earth out of view two weeks per month — [NASA VIPER lunar operations](https://science.nasa.gov/mission/viper/lunar-operations/) — **Medium** (from our repo note `rover_autonomy_driving.md`)
- **Otten, Wettergreen & Whittaker 2017, "Strategic Autonomy for Reducing Risk of Sun-Synchronous Lunar Polar Exploration" (FSR).**
  - Requiring continuous Earth communication while driving forces rovers to "dwell motionless near the day–night terminator for weeks".
  - They propose "preplanned, short, slow, autonomous drives without communication".
  - They note blackouts are "common at local depressions and on non-Earth-facing slopes" and "not conducive to highly supervised autonomy or teleoperation".
  - This is the closest prior art for the autonomy-upgrade branch: one rover, mission duration as the metric, no cost.
  - Sources: [PDF](https://www.ri.cmu.edu/app/uploads/2018/01/FSR_2017_Otten_66.pdf) — **High**; [thesis 2018](https://www.ri.cmu.edu/app/uploads/2018/01/thesis_otten.pdf) — **Medium** (abstract)
- **Robust-STP3R (Trans. JSASS 64(6), 2021).** Spatio-temporal path planning with time-varying illumination and Earth visibility, robust to schedule delay; one rover — [J-STAGE](https://www.jstage.jst.go.jp/browse/tjsass/64/0/_contents/-char/en) — **Medium** (listing)
  - Lamarre et al. 2024 (solar-powered PSR rover, Cabeus) models illumination but not comms — [arXiv 2401.08558](https://arxiv.org/abs/2401.08558) — **Medium**
- **LCRNS (Esper et al. 2025).** The relay case is framed as landing-site availability and astronaut safety: DTE 17–43 % → one relay 80–86 % → DTE plus two relays 100 %. No surface-throughput metric — [PDF](https://ntrs.nasa.gov/api/citations/20250003321/downloads/LCRNS_Esper_257.pdf) — **High**
  - The NASA contract release says, without relays, "landing opportunities would be significantly limited" — [NASA, 17 Sep 2024](https://www.nasa.gov/news-release/nasa-selects-lunar-relay-contractor-for-near-space-network-services) — **High**
- **Surface relay concepts.**
  - NASA Glenn's Lunar Surface Relay: a 10 m boom, 3GPP coverage "out to 10 km, depending on local terrain", Wi-Fi about 300 m, mobile versions driven by waypoints "similar to ... VIPER" — [Scardelletti et al. 2023](https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf) — **High**
  - JPL: a single surface station on a ridge near de Gerlache; "a rover ... would benefit significantly with a <10 km ... link" — [Jun et al. 2025](https://www-robotics.jpl.nasa.gov/media/documents/A_Rapid_Low-Cost_Path_to_Lunar_Communication_and_Navigation.pdf) — **High**
  - Intuitive Machines' RACER LTV is described as able to serve "as a communications base station" — [IM LTV page](https://intuitivemachines.com/ltv) — **Medium** (snippet)
- **LTV teleoperation evidence assumes the link is always there.**
  - The JSC latency trials assumed "flawless high-bandwidth comms"; the SRD requires 6 km per 24 h when "operated remotely" — [Litaker et al. 2025](https://ntrs.nasa.gov/citations/20240011392) — **High** (from our repo note)
  - Lunar Outpost's Lunar Voyage 1 rover was run with "268 commands with a total lander network provided downlink of only 6 Mb" — [Lunar Outpost](https://www.lunaroutpost.com/post/lunar-voyage-1-update) — **Medium**
- **Analogues, not lunar logistics.**
  - Mars: productivity is shaped by relay-pass timing (the "decisional pass"; 3–5 relay windows per sol), and "non-sun-synchronous relay orbiters" may make it worse — [Gaines et al. 2016, JPL D-97908](https://ai.jpl.nasa.gov/public/documents/papers/gaines-report-roverProductivity.pdf) — **High**
  - DRATS 2009 dual-rover field test: keeping comms took 14 % of crew time per day in one operations mode, versus 5 % and 2 % in others — [Acta Astronautica 2012](https://www.sciencedirect.com/science/article/abs/pii/S0094576512000574) — **Medium** (snippet)
  - An event-scheduler simulation of lander–orbiter–Earth messages, not throughput — [ResearchGate](https://www.researchgate.net/publication/228411230_A_MATLAB_based_Distributed_Real-time_Simulation_of_Lander-Orbiter-Earth_Communication_for_Lunar_Missions) — **Low**
- **No cost-per-link-hour study exists.** A targeted search found none comparing relay cost with rover uptime or autonomy — [search summary; e.g. IEEE Spectrum](https://spectrum.ieee.org/lunar-communications) — **Low** (absence of evidence; ScienceDirect and IEEE paywalls limited coverage)
- **Earlier repo prior-art map.** It found no lunar logistics simulation with comms windows; LunarHaul's own latency penalty (Litaker table) is the only fleet-level comms effect — [repo note](../Lunar%20landing%20and%20rover%20autonomy%20logistics/novelty_prior_art.md) — **Medium**

**Closest papers to position against:** Shirley & Balaban 2022 (VIPER), Otten et al. 2017, Esper et al. 2025, Bryant 2009, De Rosa et al. 2012.

## Q3. R-2: lander shadows and tower shading

**Verdict:** tower-on-tower shading is already done. Lander-on-array and lander-on-route shading was not found, but the expected effect is small. **Partly covered; low value.**

- **Halbach et al., ICES-2020-385 "Solar Array Configurations for the Moon Village" (Shackleton rim).**
  - Panels occlude each other at ±1.5° sun.
  - Enlarging the ground area to 3× the minimum diameter raises mean exposure by up to 66 %; the specific arrangement matters little.
  - Follow-up ICES 2021: variable panel elevations — [TTU](https://ttu-ir.tdl.org/items/a42dcf27-baec-4f72-a790-10d859ada702)
  - Source: [TTU repository](https://ttu-ir.tdl.org/items/4b4c413c-d8ee-4540-8f97-c13c91f4532a) — **Medium** (abstract)
- **Ross, Ruppert, Gläser & Elvis 2023 (Acta Astronautica 211:616).** "Overshadowing of highly illuminated areas by towers placed in sunward locations limits the total power." Up to about 55 MW at > 70 % illumination for towers ≤ 20 m (preprint numbers).
  - Sources: [arXiv 2102.11766](https://arxiv.org/abs/2102.11766); [ADS](https://ui.adsabs.harvard.edu/abs/2023AcAau.211..616R/abstract) — **Medium**
- **Towers in programmes and products.**
  - VSAT masts up to 10 m — [NTRS 20220013210](https://ntrs.nasa.gov/citations/20220013210)
  - A relocatable 10 kW array with a 10 m elevation requirement — [NASA TM-20210011743](https://ntrs.nasa.gov/api/citations/20210011743/downloads/NASA-TM-20210011743.pdf)
  - Blue Origin "Power Tower", 20 m, > 10 kW, sun 44–100 % of the time by season — [eeNews](https://www.eenewseurope.com/en/blue-origin-power-tower-lunar-surface-power/)
  - Tower heights of 10/50/100 m for microgrids near Shackleton — [IEEE Access 2023](https://ui.adsabs.harvard.edu/abs/2023IEEEA..11.8701S/abstract)
  - Mutual shading included in a south-pole PV potential study — [Energy 2025](https://ideas.repec.org/a/eee/energy/v335y2025ics0360544225035649.html)
  - All **Medium**.
- **Site plans.** The KSC Lunar Innovation Park layout is designed around "VSAT geometry" and plume geometry, but not lander shadows — [Gelino 2026, NTRS 20260002816](https://ntrs.nasa.gov/api/citations/20260002816/downloads/329%20-%20Site%20Plan%20and%20Bulk%20Presentation.pdf) — **Medium** (from our repo note `plume_ejecta_base_layout.md`)
- **Driving.** A rover's own long shadow forced up- and down-sun tacking, and shadow transitions slowed drivers. This is about vehicle and terrain shadows, not a lander's — [Litaker et al. 2025, lighting study](https://ntrs.nasa.gov/citations/20240011393) — **High** (from our repo note)
- **Lander shadows on arrays or routes.** No source found in three searches — **Low** (absence)
- **Size of the effect (Computed; inputs from [design_research.md](../LunarHaul%203D%20interactive%20design/design_research.md)).**
  - Geometric shadow at 1.5° sun: 38.2 × height. HLS: 52 m × 38.2 ≈ 1.99 km.
  - Umbra length ≈ width / tan(0.533°) ≈ 107 × width: HLS 9 m → 0.97 km; MK1 3.08 m → 0.33 km; CLPS 1.6–2 m → 0.17–0.21 km.
  - At the HLS shadow tip (2 km) a 9 m body covers about 59 % of the Sun's disc, so the tip is dimmed, not dark.
  - The shadow rotates at 0.508°/h, i.e. about 8.9 m/h sideways at 1 km. A point 1 km away is in the HLS umbra or penumbra for about 2 h once per lunar day (about 0.3 % of time).
  - A crossing rover is in it for seconds. Pads that respect our ≥ 1 km plume keep-out therefore cast negligible shade, except HLS on arrays within about 1 km of the Sun–pad line.
- **Possible crossover with R-1 (Computed / Low).**
  - A 9 m HLS 1 km away spans 0.5° of azimuth, against Earth's 1.9° disc, so it can only partly block the optical line to Earth.
  - At X-band the first Fresnel zone at 1 km is about 6 m, so radio diffraction loss is plausible.
  - Siting rule worth keeping: keep pads out of the base's Earth wedge (grid bearing about −10° to +10°) within about 2 km.
  - All current pad positions in `sites.json` are at least 17° off that bearing (the nearest is PAD_A at 0.5 km), so they are already outside it.

## Q4. Data we would need (access, size, licence)

### (a) Earth's azimuth and elevation from a lunar surface site

- **JPL Horizons API: verified by a live call on 2026-10-22.**
  - Request: `https://ssd.jpl.nasa.gov/api/horizons.api?format=text&COMMAND='399'&OBJ_DATA='NO'&MAKE_EPHEM='YES'&EPHEM_TYPE='OBSERVER'&CENTER='coord@301'&COORD_TYPE='GEODETIC'&SITE_COORD='222.761,-89.439,1.958'&START_TIME='2028-01-01'&STOP_TIME='2028-02-01'&STEP_SIZE='10m'&QUANTITIES='4,13,14'&APPARENT='AIRLESS'&ANG_FORMAT='DEG'&CSV_FORMAT='YES'`
  - `SITE_COORD` is east longitude (deg), latitude (deg), altitude (km) above the 1,737.4 km sphere.
  - Quantity 4 = airless apparent azimuth (clockwise from north) and elevation; 13 = Earth's angular diameter; 14 = sub-observer point.
  - The response header reports: Earth from DE441, "Center pole/equ: MEAN_ME (high precision)", centre radii 1737.4 km. The Moon frame is "Lunar mean Earth (DE421)", the same as LOLA products. "The lunar PA frame is not currently available in Horizons"; the high-precision lunar pole holds for 1550–2650.
  - The `i` flag marks Earth's upper limb above the smooth apparent horizon, which includes the site-altitude dip. This is inferred from the output: 9 Jan was flagged with the centre at −3.0°, i.e. upper limb at −2.05°, above the −2.7° dip.
  - Chunk requests by month (about 4,500 lines at 10 min). The API doc states no rate limit or licence.
  - Sources: [API doc](https://ssd-api.jpl.nasa.gov/doc/horizons.html); [manual](https://ssd.jpl.nasa.gov/horizons/manual.html) — **High**
- **SPICE through spiceypy (recommended; offline, reproducible, cheap).**
  - Kernels (sizes from the NAIF listings):

| Kernel | Size |
|---|---|
| `spk/planets/de440s.bsp` (1849–2150) | 31 MB |
| `spk/planets/de440.bsp` (alternative) | 114 MB |
| `pck/moon_pa_de440_200625.bpc` | 12 MB |
| `fk/satellites/moon_de440_250416.tf` (defines the Moon ME and PA frames; check the exact ME alias name in the kernel) | 19 KB |
| `pck/pck00011.tpc` | 128 KB |
| `lsk/naif0012.tls` | 5 KB |

  - Call: `spiceypy.azlcpo('ELLIPSOID', 'EARTH', et, 'LT+S', False, True, obspos_km_MOON_ME, 'MOON', 'MOON_ME')` returns the state in range/azimuth/elevation plus light time.
  - `azccw=False` gives azimuth clockwise; `elplsz=True` gives elevation positive toward +Z.
  - The frame must be "body-fixed, body-centered" on the observer's centre.
  - Sources: [NAIF generic kernels](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/) — **High** (listing); [azlcpo_c](https://naif.jpl.nasa.gov/pub/naif/toolkit_docs/C/cspice/azlcpo_c.html) — **High**; [spiceypy docs](https://spiceypy.readthedocs.io/en/main/documentation.html) — **High**; [SpiceyPy, MIT licence](https://github.com/AndrewAnnex/SpiceyPy) — **High**
  - Use MOON_ME, not MOON_PA, to match the LOLA DEMs (MOON_ME of DE421): [PGDA 90](https://pgda.gsfc.nasa.gov/products/90) — **High**
  - Our sites span about 4 km, which shifts Earth's elevation by up to about 0.13° between sites. So compute per site, or per route sample, not once for BASE — **Computed**

### (b) Larger-area LOLA polar DEMs for horizon masks out to about 300 km

- **Why 200–300 km (Computed).** The 80°S edge is 303 km from the pole.
  - A feature 3 km above BASE stays above BASE's −2.7° dip horizon only out to about 210 km: d ≤ R(θ + √(θ² + 2Δh/R)) with θ = 0.047 rad.
  - So 80°S coverage is enough. The smooth-sphere dip means far terrain matters for elevated sites.
- **PGDA product 90 (Barker et al. 2023, PSJ 4:183).** Cloud-optimised GeoTIFFs, south polar stereographic, MOON_ME (DE421). Base URL `https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/`.

| File | Size |
|---|---|
| `LDEM_80S_80MPP_ADJ.TIF` (**recommended far field**) | 181 MB |
| `LDEM_80S_40MPP_ADJ.TIF` | 685 MB |
| `LDEM_80S_20MPP_ADJ.TIF` | 2.6 GB |
| `LDEM_83S_10MPP_ADJ.TIF` | 4.8 GB |
| `LDEM_75S_30MPP_ADJ.TIF` | 2.7 GB |

  - Error maps (`_ERR`) and effective-resolution maps (`_EFFRES`) are also provided.
  - Data DOI 10.60903/gsfcpgda-lola-spole. Usage: "Please cite this paper"; no licence is named.
  - Because they are COGs, GDAL `/vsicurl/` windowed reads can fetch only Earth's wedge: about 30 km × 300 km at 80 m ≈ 375 × 3,750 px ≈ 6 MB float32.
  - Source: [PGDA 90](https://pgda.gsfc.nasa.gov/products/90) — **High** (listing) / **Computed** (window size)
- **PGDA product 81:** `ldem_87s_5mpp.tif`, 3.3 GB, a 5 m mosaic of 87–90°S (Barker et al. 2021). Only needed if routes leave our 16 km tile — [PGDA 81](https://pgda.gsfc.nasa.gov/products/81) — **High**
- **PGDA product 78:** our cached `Site01_final_adj_5mpp_surf.tif` (41 MB), the near field ≤ 8 km — [PGDA 78](https://pgda.gsfc.nasa.gov/products/78) — **High**
- **Older PDS GDR polar files** (2017 IMG): `ldem_80s_80m.img` 116 MB, `ldem_80s_40m.img` 462 MB, `ldem_80s_20m.img` 1.85 GB, `ldem_85s_10m.img` 1.84 GB, `ldem_875s_5m.img` 1.84 GB — [PDS directory](https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/) — **High**
- **Licence.** NASA content is "generally ... not subject to copyright in the United States"; credit NASA — [NASA media guidelines](https://www.nasa.gov/nasa-brand-center/images-and-media/) — **High**

### (c) Published horizon or Earth-visibility rasters usable directly

- **Average Earth visibility (Mazarico method, 2016 release).** Fraction of hourly timesteps over 18.6 years with any part of Earth's disc visible, at surface level.
  - `AVGVISIB_85S_060M_201608_EARTH`: 5058², 60 m, 51 MB IMG. **Best for validating our pipeline at our sites.**
  - `AVGVISIB_75S_120M_201608_EARTH`: 116 MB.
  - `AVGVISIB_65S_240M_201608_EARTH`: 82 MB.
  - Formats: IMG/JP2 at [imbrium.mit.edu](http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/); TIF/COG from `https://pgda.gsfc.nasa.gov/data/MoonIllumination/` per [PGDA 69](https://pgda.gsfc.nasa.gov/products/69).
  - Also on PDS (`LRO-L-LOLA-4-GDR-V1.0`; 2014 release under `extras/illumination/release_2014/`) — [ODE GDRVIS help](https://ode.rsl.wustl.edu/moon/pagehelp/Content/Missions_Instruments/LRO/LOLA/GDR/GDRVIS.htm) — **High**
  - Limits: averages only (no windows); optimistic criterion; no antenna height; 60 m pixels are coarse for ridge-crest sites.
- **Sky visibility:** `SKYV_65S_240M` (240 m) — [PGDA 69](https://pgda.gsfc.nasa.gov/products/69) — **High**
- **Horizon-mask rasters.** None found on PGDA products 69, 78, 81 or 90 — **Low** (absence)
  - NASA Ames' Celestial Mapping System offers line-of-sight and viewshed tools for Artemis regions. It is a tool, not a dataset — [NTRS 20250009664](https://ntrs.nasa.gov/citations/20250009664) — **Medium**

## Q5. Relay facts (availability, latency, dates, cost)

- **LCRNS (NASA) and Intuitive Machines.**
  - Contract: a Near Space Network firm-fixed-price IDIQ with a "maximum potential value of $4.82 billion".
  - Ordering period: base 1 Oct 2024 – 30 Sep 2029, option to 30 Sep 2034.
  - Scope: relays for "the Moon's South Pole region"; to support HLS, LTV and CLPS.
  - Source: [NASA release, 17 Sep 2024](https://www.nasa.gov/news-release/nasa-selects-lunar-relay-contractor-for-near-space-network-services) — **High**
- **Reference constellation.**
  - 5 satellites in elliptical lunar frozen orbits (ELFO) with apolune over the south pole.
  - Semi-major axis 11,305–11,326 km, eccentricity 0.692, inclination 52.5–59.4°, argument of perilune 85–92.5°, period about 30 h. Epoch 2027-03-01, GRGM-900c gravity.
  - Intuitive Machines owns the final design.
  - Derived geometry: apolune radius ≈ 19,150 km, perilune ≈ 3,490 km. A surface–relay hop adds ≤ about 0.065 s one-way, which is negligible next to our 5.0 s round trip (2 × 1.3 s + 2.4 s ground). **Relays change availability, not latency.**
  - Sources: [Ryden & Volle, LCRNS Reference Constellation 3.1, NTRS 20250002698](https://ntrs.nasa.gov/citations/20250002698) — **High**; derived values **Computed**
- **Coverage.**
  - Yearly average: DTE 17–43 %; DTE + 1 relay 80–86 %; DTE + 2 relays 100 % ("Increment Alpha" to "Bravo").
  - Early design DRM-0: one satellite covers the south pole 41 % of the time (324 of 784 min per orbit); 3 in one plane give 100 %.
  - Source: [Esper et al. 2025](https://ntrs.nasa.gov/api/citations/20250003321/downloads/LCRNS_Esper_257.pdf) — **High**
- **Schedule.**
  - As of June 2024: IOC-Alpha from Sept 2026 (≥ 1 augmented forward signal over the south pole), IOC-Bravo by mid-2028 (≥ 2), IOC-Charlie by Sept 2029 (≥ 4) — [UNOOSA ICG slides, June 2024](https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_01_02.pdf) — **High** (as a 2024 plan)
  - First relay (Altus-1 / LDN-1) rides IM-3. In September 2026 NASA said IM-3 slipped to "the first part" of 2027 (NET Q1 2027) — [Wikipedia IM-3, edited 15 Oct 2026](https://en.wikipedia.org/wiki/IM-3) — **Medium**
  - A July 2026 trade article said "later this year" and "round-the-clock" south-pole coverage once 5 satellites fly; Artemis IV landing "early 2028" — [Via Satellite, July 2026](https://www.satellitetoday.com/space-economy/2026/07/27/building-the-connectivity-backbone-for-the-next-era-of-lunar-exploration/) — **Medium** (its contract year conflicts with NASA's 2024 release)
- **ESA Lunar Pathfinder (SSTL).**
  - One satellite in a highly elliptical lunar frozen orbit; S-band to the surface, X-band to Earth; 8-year life.
  - About $23.5 M from ESA plus $15.2 M from the UK Space Agency; capacity bartered to NASA for "at least two years" in exchange for the ride on Firefly Blue Ghost M2 — [Via Satellite, July 2026](https://www.satellitetoday.com/space-economy/2026/07/27/building-the-connectivity-backbone-for-the-next-era-of-lunar-exploration/) — **Medium**
  - Launch NET 2027; "in October 2026 ... undergoing final environmental test campaign" — [Wikipedia](https://en.wikipedia.org/wiki/Lunar_Pathfinder) — **Medium**
  - No south-pole hours-per-day figure found — **Low** (absence)
  - An older small-relay design gave about 8 h of service per 12 h orbit and 14.9 h/day of real-time relay for south-pole users — [ResearchGate](https://www.researchgate.net/publication/285589326_Small_Satellite_Implementation_of_a_Lunar_Relay_Satellite) — **Medium** (snippet)
- **ESA Moonlight.**
  - 5 satellites (1 communications, 4 navigation), 3 dedicated ground stations, positioned to "prioritise coverage of the lunar south pole".
  - Initial operations by end 2028, full operations by 2030 — [ESA](https://esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration) — **High**
  - Telespazio is prime; Viasat designs the communications network — [Via Satellite, Mar 2025](https://www.satellitetoday.com/manufacturing/2025/03/25/telespazio-contracts-viasat-to-design-lunar-communication-system-for-esas-moonlight-project) — **Medium**
  - $201.4 M approved at the Nov 2025 ESA Ministerial — [Via Satellite, July 2026](https://www.satellitetoday.com/space-economy/2026/07/27/building-the-connectivity-backbone-for-the-next-era-of-lunar-exploration/) — **Medium**
- **Ground segment for DTE.** Lunar Exploration Ground Sites (LEGS) at White Sands, Matjiesfontein and Canberra, each with an 18 m-class dish — [Scardelletti et al. 2023](https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf) — **High**
- **Costs.**
  - No public price per relay hour or per link was found — **Low** (absence)
  - "Many billions in USD over decades" for full constellations — [Jun et al. 2025](https://www-robotics.jpl.nasa.gov/media/documents/A_Rapid_Low-Cost_Path_to_Lunar_Communication_and_Navigation.pdf) — **High**
  - €0.6–1.2 B for a two-satellite relay — [Satellize](https://satellize.com/space-solutions/science/lunar-infrastructure/lunar-comms-relays/) — **Low** (untraceable)
  - So any break-even should be reported as "the relay price per year at which relay = autonomy upgrade = extra rovers", not as a dollar verdict.

---

## What a new LunarHaul result would be

### Research question (the most defensible form)

> At a real, terrain-masked south-pole base (Connecting Ridge), how much cargo throughput and urgent-delivery delay does a rover fleet lose because direct-to-Earth links come and go along its actual routes? How does that loss depend on the autonomy mix (teleop / supervised / autonomous) and on relay coverage (DTE only → one relay ≈ 80 % → full)? And where are the break-evens between buying relay coverage, upgrading autonomy, adding rovers, or putting a 10 m relay mast at the base?

Hypotheses to test (each can be falsified):
- **H1.** With DTE only, a teleop leg can run only while every point on the route sees Earth. Route availability will be at or below the minimum of its end sites (0.00–0.58 here), so teleop capacity drops by more than half on some routes. Urgent jobs posted at a blackout's onset wait about one blackout (≈ 13–14 d).
- **H2.** Supervised rovers lose time only when an intervention falls in a blackout. The break-even between a relay and an autonomy upgrade is therefore set by interventions per km, which our `driving-v1` tables already provide.
- **H3.** The value of relay coverage saturates: past about 80 % coverage, night, plume stand-downs and operator limits dominate. The knee of the "availability → t/yr" curve is the headline number.
- **H4.** ISRU and SCI_1 (0 % Earth on the PDS map) cannot be served by teleop without a relay. A 10 m base mast (the NASA Glenn LSR concept, about 10 km 3GPP range) may beat an orbital relay for these routes.
- **H5.** Blackouts compress operator demand into link-up windows, so peaks can exceed `n_operators` even when the yearly average does not. This second-order effect has not been seen in prior art.
- **H6 (inference to test).** Earth's elevation cycle (draconic month, 27.21 d) beats against the lunar day (29.53 d) with a period of 1/(1/27.21 − 1/29.53) ≈ 347 d. So under DTE only, the overlap of "Earth up" and "Sun up" (VIPER's "Safe Haven" question) gives a yearly ripple in throughput. Testing it needs a real sun series (B-34) instead of `night_fraction` — **Computed**

### Experiment design in our engine (opt-in; results byte-identical when off)

- **New Scenario field `comms`** (BACKEND, `lunarsim/comms.py`, already listed in the Phase 4 file ownership). Default None. Fields:
  - `mode`: `always` | `dte` | `dte+relay`.
  - `relay`: `{coverage: 0–1, gap_model: "parametric" | "lcrns-ref", mean_gap_h}`.
  - `mast`: `{site: "BASE", height_m: 10, range_km: 10}` or None.
  - `link_series`: path to the precomputed link file.
  - `criterion`: `"centre+0.5deg"` | `"any_part"` | `"centre+2deg"`.
- **Rules by autonomy level.**
  - **Teleop:** may start a leg or load/unload only when the link is up. If the link drops mid-leg, the rover parks and resumes at the next link-up (wait time logged).
  - **Supervised, two variants:**
    - `strict`: no driving without the link. This is the conservative policy Otten et al. criticise.
    - `strategic`: drives pre-planned legs without the link, but each intervention (drawn from `driving-v1` interventions/km) waits for the link.
  - Operator demand counts only when the link is up.
  - **Autonomous:** unaffected; its 0.05 attention demand queues to the next window.
  - Crewed periods with local teleop are left out (see open questions).
- **Relay.**
  - `parametric`: covers a fraction p of DTE-blackout hours, in gaps with a chosen mean length.
  - `lcrns-ref`: propagates the five reference ELFO states (white paper) for visibility, using full-sky coarse masks.
  - Latency stays at our 5.0 s round trip (relay hop ≤ 0.065 s).
  - Mast: a site or route sample is linked if it has line of sight to the mast top within 10 km and the mast itself sees Earth (or a relay).
- **Factors (staged, single process, LEAD-run in the background).**
  - Stage A: comms {always, dte, dte+relay p = 0.5 / 0.8 / 0.9 / 1.0} × autonomy {all-teleop, current phase mix, all-supervised-strict, all-supervised-strategic, all-autonomous} × 20 seeds, phase 6, pads at 1 km, 4 simulated years 2028–2031 (spans the 347 d beat about 4×).
  - Stage B: break-even search over +0…3 rovers and mast {none, BASE 10 m} at the Stage-A knee.
  - Stage C: pads at {0.5, 1, 3 km} and the visibility criterion as sensitivity checks.
- **Outputs.**
  - Existing: delivered t/yr, p50/p90 delay by priority, operator hours, $/kg.
  - New counters: blackout wait hours by vehicle and route, operator-demand peaks.
  - Products: the availability → throughput curve per autonomy level; break-even tables (relay coverage ≡ one autonomy step ≡ N extra rovers ≡ mast).
- **Checks.**
  - `comms=always` reproduces the baseline md5.
  - The site series reproduces the PDS map at BASE: 0.50 any-part (±0.05 allowing for criterion and epoch).
  - Window lengths are about 14 d, matching De Rosa.
  - Smooth-sphere runs match the Horizons `i` flag.

### Minimal data pipeline (`tools/comms/`, light: all intermediate data < 50 MB, outputs < 1 MB)

1. **Ephemeris.** SPICE kernels (about 45 MB total) plus `spiceypy.azlcpo` in MOON_ME at 10-min steps for 2028–2031 (about 210k epochs). Points: the 9 sites, the pads, and route samples every 50–100 m along B-32 polylines. One Horizons month at BASE as a cross-check.
2. **Horizon masks.**
   - Only Earth's wedge: grid bearing about −12°…+12° per point, 0.1° steps.
   - Near field ≤ 8 km from the cached Site01 5 m DEM.
   - 8–300 km from windowed `/vsicurl/` reads of `LDEM_80S_80MPP_ADJ.TIF`.
   - Spherical curvature with R = 1,737.4 km; antenna heights 2.5 m (rover) and 10 m (mast).
   - A 360° coarse mask (1° steps) only for the `lcrns-ref` relay option.
3. **Link state.** Visible fraction of Earth's disc plus the margin per point and time. Run-length-encoded windows per point and per leg; teleop requires all samples on the leg to be linked. Output: `data/comms/connecting_ridge/earth_link-v1.json` with sha256 and provenance (kernel names, DEM files, criterion).
4. **Reuse.** The same file drives Earth's disc in the 3D world (F-33, "hidden when below the terrain") and the "comms: relay only" chip (F-36). One source of truth.

### What would count as new

- **New:** the first quantitative link between comms availability and cargo logistics at a real terrain-masked south-pole site, across autonomy levels:
  - the throughput and delay curve and its knee;
  - break-even relay coverage per autonomy step and per extra rover, expressed as a break-even relay price;
  - the "dead zones" for routes (ISRU, SCI_1);
  - the operator-demand compression effect;
  - and, if confirmed, the yearly ripple.
- **Robustness required:** seeds with CIs; insensitivity to the visibility criterion (any-part vs centre + 2°) and to the DEM release.
- **Not new (cite, do not claim):**
  - "Earth is hidden about half the month" and site visibility percentages (Bryant, De Rosa, Mazarico maps).
  - Timing single-rover traverses around DTE windows (VIPER, Otten, Robust-STP3R).
  - Relay coverage percentages (Esper / LCRNS).
  - Autonomy as the fix for blackouts in principle (Otten 2017).

---

## Open questions

1. **Link criterion.**
   - What Earth elevation margin does an X/Ka-band DTE link need near grazing? De Rosa used 2°.
   - The first Fresnel zone at 10 km is about 19 m at X-band (Computed), so links at 0–2° may be lossy even with optical line of sight.
   - Needs a propagation source (NASA Glenn LunarLiTES or ITU-R P.526).
2. **The LCRNS DTE figures (17–43 %).**
   - Why is Malapert at 43 % when Bryant gives 100 %? Probably ground-station or scheduling constraints.
   - Is "Spudis Ridge Peak" our ridge? Needs Fig. 7's assumptions (full text or NASA SCaN contact).
3. **Relay gap structure.** With one ELFO relay (30 h period), are gaps hours long, versus DTE's two-week gaps? For multi-hour teleop legs the gap structure may matter more than coverage %. Needs propagation of the reference states (GRGM-900c; two-body may drift).
4. **Ground segment.** DTE also needs a LEGS/DSN antenna in view and scheduled (DSN contention). Should availability be multiplied by a ground-station factor?
5. **Crew presence.** During crewed periods, astronauts at the base could teleoperate locally with no Earth link. Should crewed weeks be modelled?
6. **Real sun series.** Replace `night_fraction` with the B-34 sun-visibility series so H6 can be tested.
7. **Lander radio shadow.** Does a large lander in the base's Earth wedge measurably attenuate DTE (diffraction)? This would become a pad-siting rule.
8. **Unread full texts.** IEEE GRSL 2025 (terrain-driven Earth visibility) and Gläser 2018 PSS. ScienceDirect and IEEE full texts were not accessible.

## Method and search log

- About 35 web searches and about 25 page or PDF fetches, including full-text reads of:
  - Bryant 2009 (PDF), De Rosa 2012 (PDF), Scardelletti 2023 (PDF), Esper 2025 (PDF);
  - the LCRNS reference-constellation white paper (docx);
  - the VIPER planning slides, Otten 2017 FSR, Jun 2025 (JPL), Gaines 2016;
  - the HLS update 2024 and the LPSC 2026 Artemis III abstract;
  - the PGDA 69/78/81/90 pages, the PDS directory listings and the AVGVISIB label;
  - the Horizons API doc and manual, NAIF listings and azlcpo docs.
- Live JPL Horizons call: Earth from BASE, Jan 2027.
- HTTP range read of 81 rows (0.8 MB) of the PDS Earth-visibility map; registration checked against our DEM (r = +0.39 vs −0.24 with the x-axis flipped).
- Scratch files are under the session scratchpad only. No repo code was touched.
- Searches that found nothing relevant:
  - discrete-event simulation of lunar surface operations with comms windows;
  - relay economic value versus rover utilisation;
  - lander shadow on arrays;
  - horizon-mask products;
  - LTV comms/relay concepts of operations.
