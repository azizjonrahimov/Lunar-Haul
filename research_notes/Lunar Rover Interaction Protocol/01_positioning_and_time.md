# Lunar Rover Interaction Protocol, part 1: positioning ("Where am I?") and time

Status date: 11 November 2026. Scope: research questions 1 to 7 (sections 1 Positioning and 3 Time).
Maps, communications, security and the job market are in the other parts.

How to read this note:

- A source key in square brackets, for example [LUGRE26], points to the source list in section G. Every key
  in that list was opened and read in this session. Anything not opened is marked UNVERIFIED.
- Each number carries a tag that says what it was measured on:
  MOON = measured on or at the Moon; MARS = measured on Mars; EARTH = field or lab test on Earth;
  SIM = simulation; REQ = requirement or target; CALC = our own arithmetic (shown in section E).
- "Existing notes" means `research_notes/Lunar ATC/vehicles_comms_internals.md` and
  `research_notes/Lunar landing and rover autonomy logistics/rover_autonomy_driving.md`. Radio range, relay
  coverage, VIPER lighting and slip-versus-slope are already there and are not repeated.

---

## A. Summary in plain language

**1. GPS does not work on the Moon. What replaces it?**
Nothing replaces it one-for-one. A rover counts wheel turns, measures turning with gyros, takes its heading
from the stars or the Sun, and tracks the ground with cameras (visual odometry). That gives position relative
to the start, with an error of about 2 % of the distance driven. Earth's GPS and Galileo signals were received
on the lunar surface in March 2025 (LuGRE on Blue Ghost), but the point fixes were wrong by 0.1 to 100 km, so
they help with time and orbits, not with driving.

**2. What lunar navigation systems are in development?**
Three agencies are building one shared service, the LunaNet Lunar Augmented Navigation Service (LANS). All
satellites send the same signal (AFS, 2492.028 MHz). NASA's part is LCRNS (built by Intuitive Machines; first
satellite now due early 2027). ESA's is Moonlight (first service end of 2028, full service 2030). JAXA's is
LNSS (demonstration satellite 2029). All three aim at the south pole first. The stated user accuracy is about
10 m, and at first only for part of each day.

**3. How accurate is each method and how fast does the error grow?**
Wheel odometry alone: 10 % of distance or worse on loose or sloped ground; the Apollo rover, on firm level
ground with a good gyro, ended its drives within 0.3 to 4 % of the distance.
Visual odometry: 1 to 2.5 %. A good gyro alone drifts less than 3 degrees per hour; a star tracker removes
that drift. Short-range radio ranging (UWB): 0.1 to 0.7 m. LANS: about 10 m when four satellites are in view.

**4. How does a rover get its absolute position?**
By matching what it sees to maps made from orbit. Matching camera panoramas to orbital images gave 0.36 m
average error on Mars (Perseverance, in operation since February 2026). Matching craters on the Moon is
designed for under 5 m. Matching the horizon line gives about 50 m. Star sighting gives about 100 m. A lander
or base beacons with known coordinates give metre-level fixes close to the base. LANS will give about 10 m.

**5. How do you operate in shadow, in permanently shadowed craters, and without contact with Earth?**
With headlights and stereo cameras (VIPER carries eight LED arrays), or with LiDAR, which needs no light. JPL's
ShadowNav finds crater edges in the dark and corrected position to under 5 m in most test runs. Between fixes
the rover dead-reckons and ranges to beacons. Time in the cold is limited (VIPER: 9 hours in a permanently
shadowed region, 50 hours of survival without sun). Earth is below the horizon about two weeks a month, so
position and time must be kept on the Moon, not sent from Earth.

**6. How do rovers synchronise clocks?**
They agree on one lunar time scale and exchange timing messages in both directions so that the signal delay
cancels. LunaNet defines LunaNet Reference Time; the White House asked NASA in April 2024 for a Coordinated
Lunar Time plan by 31 December 2026. A clock on the Moon runs 56.02 microseconds a day faster than the same
clock on Earth, so lunar time cannot simply copy UTC. Between synchronisations each rover relies on its own
oscillator: a crystal (drifts tens of milliseconds a day) or a chip-scale atomic clock (tens of microseconds).

**7. What timing accuracy is needed?**
It depends on the use. One-way radio ranging needs nanoseconds (1 ns is 0.3 m), so it needs atomic clocks in
the beacons. Two-way ranging needs no synchronisation at all. Shared radio slots need 1.5 to 100 microseconds.
Time-stamped position reports need about 10 ms. Road-segment reservations with seconds of margin need 0.1 s.
A crystal oscillator meets the last two for hours to a day; a chip-scale atomic clock meets them for months.

---

## B. Evidence per question

### B1. What replaces GPS

**Direct answer.** A stack of sensors, not one system. No rover has ever had onboard absolute positioning on
the Moon; all flown rovers used relative navigation plus position updates worked out by people on Earth
[DAF23, MCKEE25].

| Method | What it gives | Flight heritage | Limits |
|---|---|---|---|
| Wheel odometry | distance | Apollo LRV 1971-72; every Mars rover; planned on VIPER [MCKEE25] | wheel slip |
| IMU (gyros, accelerometers) | heading change, tilt | LRV directional gyro; MER LN-200 [MAIM07] | gyro drift |
| Sun sensor / Sun image | absolute heading | LRV sun-shadow device; MER sun finding [LRV73, MCKEE25] | Sun at 1-10 deg elevation at the pole; none in shadow |
| Star tracker | absolute 3-axis attitude | VIPER: "first use of a star tracker on a planetary rover" [BLUE24] | glare, dust on optics |
| Visual odometry (VO) | 6-DOF motion | MER, MSL, Perseverance [MAIM07, JPL26] | needs texture and light |
| SLAM (visual or LiDAR) | drift-reduced path, map | field tests only [DAI26, ZHANG24] | loop closures are rare on a one-way haul |
| LiDAR | range images in the dark | none on a lunar rover yet | power, mass |
| Radio ranging (UWB, two-way) | distance to a known node | CADRE (not yet flown) [KNOW24] | line of sight |
| Earth GNSS, weak signal | time, coarse position | LuGRE on Blue Ghost, 2025 [LUGRE26] | geometry; Earth must be in view |
| LANS (AFS) | GNSS-like fixes | none; first satellite 2027 | partial coverage until about 2030 |

**LuGRE facts (MOON).** The Lunar GNSS Receiver Experiment (NASA and the Italian Space Agency, receiver by
Qascom, science team at Politecnico di Torino) flew on Firefly's Blue Ghost Mission 1: launch 15 January
2025, landing 2 March 2025, end of mission 16 March 2025 [LUGRE26].

- First GNSS fix on the lunar surface: 3 March 2025, 06:51:35 UTC [LUGRE26].
- More than 95 hours of operation on the surface, nearly 93 hours in real-time mode [LUGRE26].
- Signals: GPS L1 C/A and L5, Galileo E1 and E5a, received through a steerable high-gain antenna pointed at
  Earth to better than 0.21 deg (median 0.05 deg) on the surface [LUGRE26].
- Geometry is the limit. Geometric dilution of precision (GDOP) on the surface averaged 1,000 to 1,000,000,
  against below 50 in the mission's lowest operation at 15 Earth radii [LUGRE26].
- Least-squares point fixes on the surface: errors of 0.1 to 1 km in position in a stable-geometry window;
  1 to 100 km along the Earth-Moon line and under 1 km across it in a changing-geometry window [LUGRE26].
  NASA's 2026 slides give "range error ~10 km, lateral error ~100 m" for the steady-state case [LUGRE-MGA].
- With GPS and Galileo together, two or more signals were available nearly 70 % of a 24-hour surface period,
  against 25 % for dual-frequency GPS alone [LUGRE26].
- The authors' conclusion: point fixes are feasible but geometry-limited; operational use "should instead
  focus on sequential navigation solutions" (a filter over time), and "high-stability clocks" are needed for
  precise real-time navigation [LUGRE26]. The filter results were still "future work" in early 2026
  [LUGRE-MGA].

What this means for us: Earth GNSS at the Moon is a time source and an orbit-determination aid for relay
satellites (JAXA's LNSS is built on it [MUR26]). It is not a rover positioning method. At the south pole Earth
is also below the horizon about half of each month (existing notes).

### B2. Lunar navigation systems in development

**Direct answer.** One interoperable service (LANS) fed by three providers, plus precursors. As of 11 November
2026 no LANS satellite is in lunar orbit.

**The common standard.**

- LunaNet Interoperability Specification version 5 (LNIS v5), dated 29 January 2025 and published 7 February
  2025, is still the current version on NASA's page on 11 November 2026 [LNIS5, LNPAGE].
- The navigation signal is the Augmented Forward Signal (AFS), defined in "LunaNet Signal-In-Space Recommended
  Standard - Augmented Forward Signal, Volume A, version 1", 29 January 2025 [AFS1]:
  - band 2483.5 to 2500 MHz, carrier 2492.028 MHz, right-hand circular polarisation;
  - two components: AFS-I at 1.023 Mchip/s carrying data at 500 symbols/s, and AFS-Q at 5.115 Mchip/s as a
    pilot with no data;
  - received power on the surface between -160 and -147 dBW (both values still "TBC" in the document);
  - signal-in-space error (SISE, the part of the range error that the provider controls: orbit, clock, group
    delay): position at most 40 m (95 %) and velocity at most 1 cm/s (95 %), both "TBC"; "different providers
    may have tighter requirements".
- All providers must refer their signals to LunaNet Reference Time (LRT) or broadcast their offset from it
  [LNIS5]. The time and reference-frame standard (applicable document AD5) is still listed as "LNIS-TBD"
  [LNIS5].
- LNIS v5 states the aim of "a minimum of four simultaneous LANS nodes in view" as beyond LunaNet 1.0
  (existing notes, same document).

**Providers.**

| System | Owner / builder | Design | Dates stated by the owner | South-pole coverage | Accuracy target |
|---|---|---|---|---|---|
| LCRNS / Lunar Data Network | NASA Goddard (SCaN); Intuitive Machines under Near Space Network Services, selected 2024 [GSFC-LCRNS] | five satellites in elliptical lunar frozen orbits [LDN25] | 2024 plan: IOC-Alpha Sept 2026 (1 AFS), IOC-Bravo mid-2028 (2 AFS), IOC-Charlie Sept 2029 (4 AFS) [GRAM24]. 2025 wording: three phases "over approx. 5 years", no dates [GRAM25] | service volume 90 deg S to 75 deg S, up to 200 km altitude [GRAM24] | SISE 13.43 m (3-sigma) per satellite [INTEROP25]; at IOC-C at least 4 AFS with GDOP < 6 for 40 % of an Earth day [GRAM24]; "position uncertainty around 10 meters" at GDOP 6 [LDN25] |
| Moonlight LCNS | ESA; Telespazio consortium [MUR26] | five satellites: four navigation, one communications; three ground stations [ESA24] | Lunar Pathfinder first; initial operations end of 2028; full operations 2030 [ESA24] | "prioritise coverage of the lunar south pole" [ESA24]; at least 15 hours of continuous navigation service per 24 hours at the pole [ML24] | SISE 20 m (95 %) at IOC, 10 m at FOC; user 10 m on the surface, 50 m landing, 100 m orbit (95 %); timing "sub microsecond" [ML24] |
| LNSS | JAXA; ArkEdge Space [MUR26] | baseline eight satellites in two elliptical frozen orbits [INTEROP25] | demonstration satellite 2029 [MUR26]; then service for the south-pole region, later the whole Moon [MUR26] | south pole first [MUR26] | SISE 20 m (2-sigma) at IOC, 10 m at FOC [MUR26] |
| Lunar Pathfinder | ESA service bought from SSTL [ESA24] | one relay satellite; no AFS (link details in the existing notes) | "set to begin operations in 2026" [ESA24] | highly elliptical lunar frozen orbit [VIASAT26] | communications relay; also "testing existing Earth-orbiting navigation satellites for lunar use" [ESA24] |

**Where the sources disagree.**

- SISE: the common standard allows 40 m (95 %) [AFS1]; NASA requires 13.43 m at 3-sigma (about 4.5 m at
  1-sigma) [INTEROP25]; ESA and JAXA quote 20 m then 10 m at 95 % or 2-sigma [ML24, MUR26]. They are different
  confidence levels and different service phases, so they are not directly comparable.
- LCRNS dates: the June 2024 slide gives September 2026, mid-2028 and September 2029 [GRAM24]. The March 2025
  slide drops the dates [GRAM25]. JAXA's February 2026 slide still labels LCRNS "(2026~)" [MUR26].

**Status on 11 November 2026.**

- LCRNS: the first relay satellite (named Altus-1) rides with the IM-3 lander. IM-3 slipped from the second
  half of 2026 to the first quarter of 2027; NASA delivered a NavCube3-mini navigation receiver for Altus-1 in
  summer 2026 [WIKI-IM3, secondary source; it cites Aerospace America, 15 September 2026, which we did not open].
  A trade article of 27 July 2026 still said the first satellite was "slated for launch later this year" and
  gave the contract ceiling as 4.82 billion US dollars [VIASAT26]. So the 2024 date for IOC-Alpha (September
  2026) has not been met.
- Lunar Pathfinder: it flies on Firefly's Blue Ghost Mission 2. The launch moved from "no earlier than
  December 2026" to 2027 [WIKI-BGM2, WIKI-LPF, secondary sources].
- Joint demonstration: NASA, ESA and JAXA plan a LANS interoperability demonstration in 2029, with a lander
  near the south pole carrying at least two LANS receivers, launched on a JAXA H3. The expected constellation
  is one Moonlight satellite, one LNSS satellite and three LCRNS satellites [INTEROP25, MUR26].

**Predicted user performance in that 2029 configuration (SIM).** Lander at 87 deg S, 20 deg E, five satellites,
receiver with an oven-controlled crystal oscillator (OCXO) [INTEROP25]:

| Case | Mean | 68 % | 95 % | 99.7 % |
|---|---|---|---|---|
| 2D, no height constraint | 35.7 m | 25.0 m | 121.6 m | 362.0 m |
| 2D, height from a digital elevation model (DEM) | 5.7 m | 5.6 m | 17.2 m | 19.5 m |
| 3D, DEM height, miniature rubidium clock in the receiver | 5.4 m | 5.9 m | 8.2 m | 8.9 m |

Notes: one simulation run with notional orbits. At least three satellites were in view all day. The paper's
text quotes a mean of 13.5 m for the first row while its table says 35.7 m; we give the table. The lesson is
firm either way: a known terrain height turns a 100-metre-class service into a 10-metre-class one. ESA's own
study reports 3 to 5 m (3-sigma) for a rover that combines Moonlight ranging with a 5 m/pixel DEM [ML24].

**Coverage in time (SIM).** For the five-satellite LCRNS design, every point in the service volume has at
least two satellites in view for 90 % of an Earth day; GDOP < 6 comes in two or three windows of 5 to 7 hours
per Earth day; the worst points, at the edge of the volume, get about 34 % of the day instead of 40 % [LDN25].
Relay coverage for communications: direct-to-Earth alone 17 to 43 % of a year at south-pole sites, 80 to 86 %
with one relay, 100 % with two [GRAM25].

### B3. Accuracy and drift of each method

**Direct answer.** See the table. Relative methods grow with distance or time; absolute methods do not.

| Method | Number | Tag | Measured on | Source |
|---|---|---|---|---|
| Wheel odometry + gyro, lunar | end-of-traverse error < 200 m after 10.3, 12.5 and 5.1 km (under 1.9 %, 1.6 % and 3.9 %) | MOON | Apollo 15 LRV, three traverses | [LRV73] |
| Same | end-of-traverse error 0 m after 4.2 km and 0 m after 11.1 km; largest error during any traverse 100 m (11.3 km) | MOON | Apollo 16 LRV | [LRV73] |
| Same | end-of-traverse error 0 m, about 50 m and about 50 m after 2.5, 20.1 and 12.0 km (0.25 % and 0.4 %); "100 m or less during all three traverses" | MOON | Apollo 17 LRV | [LRV73] |
| LRV requirement | vehicle level: range to the lander within 600 m at 5 km, bearing within 6 deg, distance within 2 %; navigation system (3-sigma): 420 m at 5 km, heading 4.5 deg, distance 1 % | REQ | LRV specification | [LRV73] |
| Wheel slip assumed before flight | 1.85 % | REQ | LRV pre-flight error analysis | [LRV73] |
| Wheel odometry alone | "not better than 10 % of the distance traveled", worse in high slip | EARTH | JPL Mars Yard tests | [HELM06] |
| Wheel slip, extreme | up to 125 % on a slope above 25 deg | MARS | Spirit, sol 206 | [MAIM07] |
| Wheel slip, sand trap | commanded 50 m, moved 2 m | MARS | Opportunity, sol 446 | [MCKEE25] |
| MER position design goal | drift of at most 10 % over a 100 m drive | REQ | MER | [MAIM07] |
| Visual odometry | under 2.5 % over 24 m; under 1.5 % over 29 m | EARTH | Mars Yard; Johnson Valley | [MAIM07] |
| Visual odometry | under 1 % over a 2.45 m rock course with up to 85 % slip; wheel odometry + IMU passed 10 % after 1.4 m | EARTH | MER engineering model, indoor sandbox | [MAIM07] |
| VO convergence rate | 97 % (Spirit), 95 % (Opportunity) of attempts | MARS | first two years | [MAIM07] |
| VO + IMU + star camera | "typically < 2 % of distance traveled" | REQ | design assumption for lunar rovers | [DAF23, ATHA24] |
| VO on a long drive | position "off by more than 100 feet (up to 35 meters)" | MARS | Perseverance, long drives | [JPL26] |
| Stereo VO, no map | 78.0 m absolute error over 1.19 km (6.6 %) | SIM | simulated lunar traverse | [DAI26] |
| Stereo SLAM, no map | 94.01 m RMS over a 1.03 km loop (9 %) | EARTH | Mt Etna analogue data (S3LI) | [DAI26] |
| Same with DEM anchoring | 7.71 m (SIM); 21.43 m (EARTH) | SIM / EARTH | same two traverses | [DAI26] |
| LiDAR-inertial SLAM + DEM | about 0.6 m average absolute error | SIM | simulated planetary scene | [ZHANG24] |
| Gyro drift | "usually less than 3 degrees per hour of operation" | MARS | MER, Litton LN-200 | [MAIM07] |
| Gyro drift | requirement under 5 deg/h in the laboratory; in flight "little or none" | MOON | LRV directional gyro | [LRV73] |
| Gyro classes (in-run bias stability) | industrial < 10 deg/h; tactical < 1 deg/h; navigation < 0.1 deg/h | vendor classes | "no agreed-upon definitions" | [VN] |
| Star tracker | "3-axis attitude knowledge to a small fraction of a degree"; "far better than our orientation requirements" | REQ | design statements, lunar rovers | [DAF23, BLUE24] |
| Sun sensor / sun tracker | "well within a degree" in roll, pitch and yaw, no drift | EARTH | CMU analogue rovers | [DEANS05] |
| Sun-shadow device | 2 deg (root-sum-square, 3-sigma) | REQ | LRV | [LRV73] |
| UWB two-way ranging | error 14 cm, standard deviation 11 cm | EARTH | DW1000 boards, rover demo | [PLANS18] |
| UWB two-way ranging | "about 40 to 70 centimeter" | EARTH | DWM1000, indoor, for an analogue-mission rover | [NUCH24] |
| Cheap crystal in UWB radios | clock skew up to 20 parts per million | spec | IEEE 802.15.4z devices | [SHAL22] |
| LANS, user position | about 10 m; table in B2 | REQ / SIM | LCRNS, Moonlight | [LDN25, ML24, INTEROP25] |
| Earth GNSS on the lunar surface | 0.1 to 100 km point fixes | MOON | LuGRE | [LUGRE26] |

How fast the error grows (formulas in E1):

- Distance error grows in proportion to distance: 2 % means 20 m after 1 km and 200 m after 10 km.
- Heading error grows in proportion to time if only a gyro is used. At 3 deg/h the sideways error after one
  hour of straight driving is 2.6 % of the distance (CALC, E1). With a star tracker it stays near 0.1 to 0.2 %.
- Apollo's team expected "range error due to wheel slip would likely contribute much less to overall position
  error than bearing error due to gyroscope misalignment" [MCKEE25]. Heading is the first thing to get right.

Slip on regolith: the existing autonomy note gives Yutu-2 slip of 10.45 to 19.70 % at three sites and the
slip-versus-slope curve from NASA Glenn tests. We reuse those values and did not re-open those sources.

### B4. Absolute position

**Direct answer.** Compare what the rover senses with a georeferenced product made from orbit, or measure
range to something whose coordinates are known.

**The orbital reference.**

- LOLA (laser altimeter on Lunar Reconnaissance Orbiter) south-pole elevation models at 5 m/pixel: track
  geolocation uncertainty about 10 to 20 cm horizontally and 2 to 4 cm vertically after reprocessing; height
  uncertainty of a pixel typically 0.30 to 0.50 m RMS; slope uncertainty 1.5 to 2.5 deg; about 1 % of pixels
  have height errors above 1 m, and the largest is 5.65 m [BARK21, PGDA78].
- LROC NAC images: about 0.5 m/pixel over sunlit areas, enough to map craters of 5 to 10 m diameter.
  ShadowCam on the Korean orbiter: about 1.7 m/pixel inside permanently shadowed regions, craters of 10 to
  20 m [DAF23].
- Photoclinometry (shape from shading) by NASA Ames raises terrain models to 1 m/pixel for VIPER [FONG24].

| Method | Reported accuracy | Tag | Notes | Source |
|---|---|---|---|---|
| Panorama to orbital image (Censible / Mars Global Localization) | mean 0.36 m, maximum 1.07 m, 99 % within 0.93 m over 264 panoramas; orbital map 0.25 m/pixel | MARS | runs on board Perseverance; first operational use 2 February 2026; about once per sol after driving; search radius 30 m | [NASH24, NASH26, JPL26] |
| Crater matching, sunlit (LunarNav) | goal: position < 5 m and heading < 3 deg, 3-sigma; one test 0.75 m (particle filter) and 1.6 m (parametric) | REQ / SIM | craters of 5 m and more detected at 15 m range or more; needs a crater map | [DAF23] |
| Crater-edge matching in the dark (ShadowNav) | "less than 5 m in most cases", centred on 2 to 3 m; field test: average under 5 m and maximum under 9 m in all but one trajectory; target: correct 10 m down to under 5 m | SIM / EARTH | stereo camera plus a lamp; Cinder Lakes, Arizona; straight drive-by of a single crater often fails | [ATHA24, CAU23, SNPOSTER] |
| Stereo point cloud to orbital DEM (VIPER "terrain registration") | no accuracy figure published in what we opened | - | done on the ground, people in the loop, needs the Earth link | [FONG24, VIPER-TI, MCKEE25] |
| Terrain registration using shadows as features | average 0.15 m, maximum 0.71 m (plain ICP: 0.5 m and 3.10 m), from starts up to 10 m off | SIM | polar lighting, six stereo pairs | [FANG19] |
| Horizon (skyline) matching | 50 m or better after filtering; one example goes from 400 m to 73 m | SIM | works when lost; needs relief on the horizon | [DRIES24] |
| Horizon matching, older estimate | "errors < 50 m" in favourable terrain | cited | | [DAF23] |
| Star tracker + gravity direction ("stellar positioning") | 421 m in a one-hour Earth test; about 125 m expected on the Moon; simulations about 100 m (1-sigma) | EARTH / SIM | needs a gravity model and a calibrated tracker-to-IMU angle | [MCKEE25, DAF23] |
| LANS pseudoranges + DEM height | 3 to 5 m (3-sigma); 17.2 m (95 %) in the 2029 configuration | SIM | see B2 | [ML24, INTEROP25] |
| UWB ranging to surveyed anchors | 0.1 to 0.7 m per range | EARTH | position accuracy then depends on geometry (E3) | [PLANS18, NUCH24] |
| Lander as anchor | bearing and range to the lander were the whole navigation display on the LRV | MOON | the lander position itself must be fixed first | [LRV73, MCKEE25] |

**Who does what.**

- VIPER (now manifested on Blue Moon MK1, existing notes): on board, relative pose from wheel encoders, IMU and
  a zenith-facing star tracker; on the ground, visual odometry and terrain registration, merged by a "pose
  corrector" [VIPER-TI, FONG24]. It needs a continuous Earth link and enters a contingency mode without it
  [MCKEE25].
- CADRE (three small JPL rovers and a base station on the IM-3 lander): cameras for visual odometry plus UWB
  radios to measure distances between rovers; a decentralised planner can steer the rovers to keep good
  ranging geometry [KNOW24]. Flight results do not exist yet: IM-3 is now early 2027 [WIKI-IM3].
- Perseverance is the first rover with onboard absolute localisation in routine use. The JPL team says it
  has "already turned their sights to the Moon" [JPL26].
- Base infrastructure: NASA's Lunar Surface Relay concept carries two rubidium clocks and two retroreflectors
  "to provide positioning and ranging sources" [LSR23]. JAXA plans "LANS reference and monitoring stations"
  and considers two-way ranging between LNSS satellites and surface beacons [MUR26].

**Why absolute fixes are needed at all.** Without them, autonomous drives are limited to "a few hundred
meters" before people must re-localise the rover [DAF23]. Perseverance's longest drive without human review
was 699.9 m over three sols [NASH26].

### B5. Shadow, permanently shadowed regions, and no Earth contact

**Direct answer.** Bring your own light or use a sensor that needs none; keep dead reckoning tight with a
star tracker; fix position against crater edges or beacons; plan around thermal limits; keep time and
position services on the Moon.

- **Lighting.** VIPER's lights are LED arrays: two on the mast with a narrow long beam, up to six around the
  body. Lit and shadowed ground are "in such high contrast that any contours in the landscape are effectively
  invisible in the darkness"; dust backscatter "blinds" the cameras, which drove lamp placement
  [VIPER-LIGHTS]. Details of wavelengths are in the existing autonomy note.
- **Localisation in the dark.** ShadowNav uses a stereo camera and a lamp, detects the leading edge of
  craters and matches them to an orbital crater map with a particle filter. Its requirement comes from the
  Endurance-A rover concept: about 70 % of a 2,000 km traverse at night, absolute error kept under 10 m
  [ATHA24, CAU23]. It needs craters near the route and fails on a straight pass by a single crater
  [ATHA24].
- **Maps in the dark.** Orbital images of permanently shadowed regions are coarser (about 1.7 m/pixel against
  0.5 m/pixel), so only craters of 10 to 20 m can serve as landmarks there [DAF23]. LOLA elevation models
  do not depend on sunlight [BARK21].
- **LiDAR.** It gives geometry without sunlight. LunarNav has a LiDAR crater detector, and ShadowNav notes
  that LiDAR "could potentially replace or augment the stereo cameras" [DAF23, ATHA24]. LiDAR matched to a
  DEM gave about 0.6 m in simulation [ZHANG24]. We found no flown lunar rover with LiDAR in the sources
  opened; one of the 2028 crew rovers lists one (existing notes).
- **Heading.** A star tracker works in shadow; a sun sensor does not. VIPER's tracker faces the zenith to
  stay away from the low Sun [MCKEE25].
- **Thermal limits.** VIPER: 9 hours of operations in a permanently shadowed region and 50 hours of survival
  in low-power mode [BLUE24]. The original LTV requirement was 2 hours in such regions (existing notes).
- **No Earth.** At the pole Earth is hidden about two weeks a month and VIPER hibernates through it
  [VIPER-OPS]. Ground-in-the-loop localisation therefore stops for two weeks unless a relay is in view; relay
  coverage figures are in B2.
- **Inertial plus ranging.** In a crater with no landmarks in view, the remaining information is dead
  reckoning and range to nodes with known positions (a mast on the rim, a parked rover, a lander). Section E2
  shows how even sparse ranges bound the drift.

### B6. How rovers synchronise clocks

**Direct answer.** A common reference time scale, a rate correction for relativity, two-way exchange of time
stamps over the radio link, and a local oscillator good enough to hold time between exchanges.

**The reference scale.**

- OSTP memorandum, 2 April 2024, "Policy on Celestial Time Standardization in Support of the National Cislunar
  Science and Technology Strategy" [OSTP24]:
  - NASA, with the Departments of Commerce, Defense, State and Transportation, is to "provide a finalized
    strategy ... to implement lunar timing standardization no later than December 31, 2026";
  - four required features: traceability to UTC, accuracy for precision navigation and science, resilience to
    loss of contact with Earth, scalability beyond the Earth-Moon system;
  - "to an observer on the Moon, an Earth-based clock will appear to lose on average 58.7 microseconds per
    Earth-day with additional periodic variations".
- NASA, 12 September 2024: lunar time "will be determined by a weighted average of atomic clocks at the Moon";
  where those clocks will be is "still to be determined"; NASA's text uses 56 microseconds a day [NASA-LTC24].
- International Astronomical Union, 2024 General Assembly: Resolution II recommends a Lunar Celestial
  Reference System with Lunar Coordinate Time (TCL); Resolution III asks that the relation between a lunar
  reference time scale and UTC be settled by international agreement [DEF25, which quotes both; the IAU's own
  PDF links returned "404" on 11 November 2026].
- Metrology proposals: Bourgoin, Defraigne and Meynadier (Paris Observatory, Royal Observatory of Belgium,
  BIPM) review the options and how to keep traceability to UTC (accepted by Metrologia; preprint version of
  6 January 2026) [BOU26]. Their companion paper concludes that TCL itself "is the best option to be used as
  practical time reference on the Moon", with the offset from UTC predicted to the microsecond level [DEF25].
- China's Purple Mountain Observatory published a lunar time ephemeris, LTE440, built on the same IAU
  definition (June 2025) [LTE440].
- LunaNet: every provider keeps its own system time and must relate it to LunaNet Reference Time; the
  defining document is not yet released [LNIS5].
- As of 11 November 2026 we found no public statement that NASA's strategy has been delivered. The deadline
  is seven weeks away.

**The relativistic rate (derivation in E4).**

| Source | Mean rate, Moon surface clock minus Earth geoid clock | Periodic part |
|---|---|---|
| Ashby and Patla, NIST [ASH24] | +56.0199(12) microseconds/day | -0.1084 cos(f) microseconds/day, f = orbital anomaly |
| Kopeikin and Kaplan [KK24] | +56.025 microseconds/day (60.2147 - 2.7128 - 1.4769) | largest term about 0.5 microsecond, period 27.55 days |
| Turyshev, Williams, Boggs, Park, JPL [TUR25] | +56.0256 microseconds/day | largest about 0.470 microsecond at the anomalistic period |
| OSTP memo [OSTP24] | 58.7 microseconds/day | "additional periodic variations" |

The three papers agree to 0.006 microseconds/day. The memo's 58.7 matches the intermediate value 58.721 in
[ASH24] that is computed "not including any effect from the gravitational potential of the Moon" (which is
2.71 microseconds/day). Use 56.02.

**Time transfer.**

- Two-way time transfer: both ends send and time-stamp, and the path delay cancels because it is the same in
  both directions. Over geostationary satellites its stability over 24 hours is "better than 1 ns", and it
  can be calibrated "to the 1 ns level" with a travelling station; the equipment delays at each end do not
  cancel and are the main error [NIST-TT]. The uncorrected rotation (Sagnac) term between two example sites is
  181 ns [ITU-TF1153].
- LunaNet offers the same idea as point-to-point two-way ranging and Doppler between relay and user
  [GRAM25], and one-way time from AFS (time-of-transmission message, offsets to LRT and UTC) [LNIS5, AFS1].
- A chip-scale atomic clock can be set from a one-pulse-per-second input "with +/-100 ns accuracy" [CSAC].
- Cellular practice: LTE-TDD small cells and 5G NR TDD need a time error within 1.5 microseconds of the
  reference (class 4); large LTE-TDD cells 5 microseconds (class 3) [G8271].

**Oscillator classes.**

| Class | Stability | Tag / measured on | Source |
|---|---|---|---|
| Uncompensated crystal (in UWB chips) | up to 20 parts per million offset | spec | [SHAL22] |
| Temperature-compensated crystal (VCTCXO) | drift between about 0 and 8 x 10^-7 s/s as the receiver warmed from 25 to 45 deg C; a 10 to 15 minute transient at power-on | MOON, LuGRE on the surface (read from the figure axis) | [LUGRE26] |
| Oven-controlled crystal (OCXO) | Allan deviation 1 x 10^-10 at 1 s; 3 x 10^-10 at 10 to 100 s; 2 x 10^-10 at 1,000 s; 1 x 10^-12 at one day | receiver assumption for LANS | [INTEROP25] |
| Chip-scale atomic clock (Microchip SA65) | Allan deviation 3 x 10^-10 at 1 s, 1 x 10^-10 at 10 s, 3 x 10^-11 at 100 s, 1 x 10^-11 at 1,000 s; ageing < 9 x 10^-10 per month; +/-3 x 10^-10 over -40 to +80 deg C; < 120 mW; < 35 g. The data sheet says this model is "not tested, qualified, or rated for space" | data sheet | [CSAC] |
| Miniature rubidium (MiniRAFS) | Allan deviation 1 x 10^-11 at 1 s; 1 x 10^-12 at 100 s; 1 x 10^-13 at 10,000 s | receiver assumption for LANS | [INTEROP25] |
| Rubidium on a surface relay | two units, running continuously | concept | [LSR23] |
| Reference: UTC(NIST) steering | up to 250 ps/day | EARTH | [ASH24] |

### B7. Timing accuracy needed, derived

**Direct answer.** From nanoseconds to tenths of a second, depending on the use. Derivations are in E5 and E6.

| Use | Relation | Needed clock agreement | Clock that holds it, and for how long without resync (CALC) |
|---|---|---|---|
| One-way ranging to beacons or LANS, 1 m budget | range error = c x clock error; 1 ns = 0.30 m | about 3 ns between beacons; the user solves its own offset | rubidium class in beacons, steered continuously; a chip-scale atomic clock holds 3 ns for only about 10 s |
| Two-way ranging (UWB) | clock offset cancels; residual = c x (rate error) x (reply delay) / 2 | none; rate error 1 ppm and 1 ms reply give 0.15 m | any crystal, with double-sided ranging |
| Carrying an absolute fix forward by ranging to a base clock (one-way, 10 m budget) | as row 1 | 33 ns | chip-scale atomic clock: about 2 minutes; rubidium (10^-12): about 9 hours |
| Shared radio slots (TDMA), 5G NR TDD style | guard time >= 2 x clock error + path delay; 10 km of path = 33 microseconds | 1.5 microseconds [G8271] | chip-scale atomic clock: about 80 minutes; crystal at 2 x 10^-7: 7.5 s |
| Shared radio slots, relaxed mesh (10 ms slots, 1 % guard) | same | about 30 microseconds | chip-scale atomic clock: about 1 day; crystal at 2 x 10^-7: 150 s |
| Time-stamped position report, 0.1 m budget | position error = speed x time error | 25 ms at 4 m/s; 1 s at 0.1 m/s; use 10 ms | crystal at 10^-6: 2.8 hours; at 2 x 10^-7: 14 hours; chip-scale atomic clock: about 2 to 3 months |
| Road-segment reservation, margin of seconds | clock error must be small against the margin; 1 s at 4 m/s is 4 m | 0.1 s | crystal at 10^-6: 28 hours; at 2 x 10^-7: 5.8 days; chip-scale atomic clock: more than 6 months |
| Logging and auction time stamps | ordering of messages | 1 ms | crystal at 10^-6: 17 minutes; chip-scale atomic clock: about 3 weeks |

Two warnings:

1. The relativistic offset (56.02 microseconds a day, a rate of 6.48 x 10^-10) is twice the temperature term
   of a chip-scale atomic clock (3 x 10^-10) [CSAC]. If two nodes disagree on whether time stamps are "Earth
   seconds" or "Moon seconds", they diverge by 16.8 km of light-time per day (CALC). The protocol must name
   the scale in every time stamp.
2. A crystal that looks adequate on paper is not adequate through a thermal swing. LuGRE's crystal moved by
   several parts in 10^7 within a day on the surface because of temperature alone [LUGRE26].

---

## C. Our design choice

**Setting.** A south-pole base in about 2028 to 2032 with rovers from several companies: crew rovers, cargo
rovers, small scouts, hoppers that land and park. Speeds 0.1 to 4 m/s. Roads between a landing zone, a power
site and work sites, some in shadow.

**Proposal: five layers, each one bounding the error of the layer below.** A vehicle must have layers 0 and 1
to enter the shared roads. Layers 2 to 4 are services of the base.

| Layer | What | Who provides it | Error it leaves (design value) | Available |
|---|---|---|---|---|
| 0. Common frame and time | one lunar frame (the frame of the LOLA-based base map) and one named time scale | protocol; base time server | - | always |
| 1. Dead reckoning | wheel odometry + IMU + star tracker (sun sensor as backup) + visual odometry with lamps | every vehicle | 2 % of distance since the last fix; 10 % if vision is lost on loose ground | always |
| 2. Cooperative ranging | two-way ranging between vehicles and to surveyed beacons (masts, landers, parked relays); each message carries the sender's position, covariance and time | every vehicle + base beacons | 0.3 m per range; position 0.3 to 5 m depending on geometry (E3) | line of sight to at least two nodes |
| 3. Absolute terrain fix | on-board matching of camera or LiDAR data to the orbital map (craters, DEM, orthoimage); horizon matching to recover a lost vehicle; surveyed markers at road junctions | vehicle, with maps from the base | 1.7 m (1-sigma) sunlit; 3 m in the dark; 50 m for horizon recovery | at stops, where landmarks exist |
| 4. LANS | AFS pseudoranges with height taken from the map; also time | NASA, ESA, JAXA providers | 10 m (95 %) when 3 or more satellites are in view | none in 2026-27; part of each day from about 2029 |

Earth-based localisation stays as an audit of the whole network, not as part of the control loop, because
Earth is out of view for about two weeks a month.

**Why this combination.**

1. Nothing in layer 4 exists yet, and the first full-constellation phase is planned to give four satellites
   with good geometry for only 40 % of an Earth day [GRAM24, LDN25]. One schedule milestone has already
   slipped by at least six months (B2). A base that depends on LANS cannot open in 2028.
2. Layer 1 uses sensors that VIPER and the crew rovers already carry [BLUE24, existing notes].
3. Traffic rules need relative position more than absolute position: two rovers meeting on a road must agree
   on the gap between them. Direct ranging (layer 2) gives that at 0.1 to 0.7 m [PLANS18, NUCH24] even if
   both are 5 m off on the map.
4. Layer 3 ties the network to the map. Without it a ranging network can drift or rotate as a whole.
5. LANS brings what the surface layers lack: an independent check, coverage far from the base, and time.
   With the map height as an extra measurement it is a 10-metre-class fix with only three satellites
   [INTEROP25].
6. The method with flight proof today is layer 3: Perseverance has run it on board since February 2026
   [JPL26]. The lunar versions are tested in simulation and in the field, not in flight [DAF23, ATHA24].

**What each layer's failure looks like, and how the protocol should notice it.**

| Layer | Failure | What it looks like | Detection / response |
|---|---|---|---|
| 0 | two vehicles use different time scales or frames | time stamps that diverge by 56 microseconds a day, or a fixed shift between two maps | every message names its frame and time scale; reject unknown ones |
| 1 | wheel slip in loose regolith or on slopes | odometry runs ahead of true motion (Spirit: 125 % [MAIM07]) | compare wheel distance with visual odometry and with ranges; raise drift to 10 % |
| 1 | vision loss: glare, shadow, dust on lenses, no texture | visual odometry stops converging (MER: 3 to 5 % of attempts [MAIM07]) | fall back to wheel + IMU; slow down; request a ranging fix |
| 1 | star tracker blinded (low Sun, lamps, dust) | heading error grows at the gyro rate, up to 3 deg/h [MAIM07] | sideways error grows as time squared (E1); cap drive time without a heading fix |
| 2 | no line of sight (terrain, another vehicle) | range missing | treat as outage, not as error |
| 2 | reflected path instead of direct path | range too long, always positive | reject ranges that disagree with the prior by more than 3-sigma; never accept a single range as a fix |
| 2 | poor geometry far from the base | good along the line to the base, poor across it (E3) | report the full covariance, not a single number |
| 2 | wrong beacon coordinates | everyone agrees with each other and is wrong on the map | check beacons against layer 3 and layer 4 |
| 2 | a vehicle reports a wrong position (fault or deceit) | neighbours' residuals point at one node | covariance intersection plus residual voting; see the security part |
| 3 | false match (repeating craters, moving shadows) | sudden jump of metres to tens of metres | gate on the prior; require two independent matches before a large correction |
| 3 | no landmarks (smooth mare-like floor, deep shadow, coarse map) | no fix for a long stretch | plan routes past known landmarks or place markers |
| 4 | fewer than three satellites, or a geometry spike | error grows from 10 m to over 100 m [INTEROP25] | use the broadcast SISE and computed DOP as an integrity flag |
| 4 | terrain masks the sky (crater floor) | satellites low on the horizon are lost | same as layer 2 outage |
| 4 | interference from surface radios | AFS is weak (-160 to -147 dBW [AFS1]) and its band (2483.5 to 2500 MHz) starts where the 2.4 GHz Wi-Fi band ends | open question; needs a filter and a spectrum rule at the base |

**Protocol consequences (for the other parts of this work).**

- A position report must contain: frame identifier, time-scale identifier, time stamp, position, a 3 x 3
  covariance (or at least along-track and cross-track sigmas), which layers contributed, and an integrity
  flag.
- A ranging exchange must be two-way and must carry both vehicles' current position and covariance.
- Base beacons broadcast their surveyed coordinates, their clock offset from base time and its uncertainty.
- The base runs a time server (the NASA relay concept has two rubidium clocks [LSR23]) and every contact with
  it is also a two-way time transfer.
- Road reservations must use a margin that covers position error divided by speed (E6), not only clock error.

---

## D. Simulation parameters for the backend engineer

"Value" is the default. "Range" is for parameter sweeps. Tags as in the note header. A = our assumption,
anchored on the cited sources but not measured.

| Parameter | Value | Range for sweep | Unit | Source |
|---|---|---|---|---|
| Dead-reckoning drift, firm level ground, VO + star tracker | 2 | 1 to 2.5 | % of distance (1-sigma) | [MAIM07] EARTH; [DAF23, ATHA24] REQ |
| Dead-reckoning drift, wheel odometry + gyro only, level | 2 | 0.3 to 4 | % of distance | [LRV73] MOON (Apollo 15 to 17 end-of-traverse errors) |
| Dead-reckoning drift, loose soil or slope above 10 deg, no VO | 10 | 5 to 30 | % of distance | [HELM06] EARTH; slip from existing notes |
| Dead-reckoning drift in shadow, VO with lamps | 3 | 2 to 7 | % of distance | A; upper end from [DAI26] SIM (6.6 %) |
| Probability that one VO update fails | 0.04 | 0.01 to 0.15 | per update | [MAIM07] MARS (3 to 5 %); upper end A for shadow |
| Wheel slip, level firm regolith | 2 | 1 to 5 | % | [LRV73] REQ (1.85 % assumed) |
| Wheel slip, slopes and loose soil | 15 | 10 to 125 | % | existing notes (Yutu-2 10 to 20 %); [MAIM07] MARS maximum |
| Heading drift, gyro only | 3 | 1 to 5 | deg/hour | [MAIM07] MARS; [LRV73] REQ |
| Heading error with star tracker | 0.1 | 0.01 to 0.5 | deg, bounded | A; "small fraction of a degree" [DAF23] |
| Heading error with sun sensor (sunlit only) | 1 | 0.5 to 3 | deg, bounded | [DEANS05] EARTH; [LRV73] REQ; LunarNav heading goal 3 deg [DAF23] |
| Absolute fix accuracy, terrain matching, sunlit | 1.7 | 0.4 to 3 | m (1-sigma, horizontal) | [DAF23] REQ (5 m at 3-sigma); lower end [NASH24] MARS |
| Absolute fix accuracy, crater matching in the dark | 3 | 2 to 5 | m | [ATHA24] SIM/EARTH |
| Probability that a dark crater fix fails or exceeds 5 m | 0.3 | 0.1 to 0.5 | per attempt | [ATHA24] (60 % within 5 m on the hardest trajectory); A |
| Absolute fix accuracy, horizon matching (lost rover) | 50 | 30 to 100 | m | [DRIES24] SIM |
| Absolute fix accuracy, star tracker + gravity | 125 | 100 to 400 | m | [MCKEE25] EARTH test scaled to the Moon |
| Distance between terrain-fix opportunities, sunlit highlands | 100 | 50 to 500 | m | A; craters of 5 m and more detected at 15 to 40 m [DAF23] |
| Distance between terrain-fix opportunities, shadowed region | 500 | 200 to 2,000 | m | A; only 10 to 20 m craters are mapped there [DAF23] |
| Time stopped for one terrain fix | 120 | 30 to 600 | s | A; Perseverance runs it once per sol after driving [NASH26] |
| Map (DEM) height error | 0.4 | 0.3 to 0.5; 1 % of pixels above 1 | m RMS | [BARK21] |
| Map horizontal geolocation error | 0.15 | 0.1 to 0.2 | m | [BARK21] (LOLA tracks after adjustment) |
| UWB two-way range error, line of sight | 0.3 | 0.1 to 0.7 | m (1-sigma) | [PLANS18, NUCH24] EARTH |
| UWB maximum range | 100 | 50 to 300 | m | A; no lunar value is public; vendor claim of 290 m UNVERIFIED |
| Range bias when the direct path is blocked | +1 | 0 to +5 | m | A |
| Long-range two-way ranging over the base radio (S-band or cellular) | 3 | 1 to 10 | m | A; range limit = radio line of sight from existing notes |
| Number of base beacons | 4 | 2 to 8 | - | A; see E3 for the effect |
| LANS horizontal accuracy with map height, 3 or more satellites | 10 | 5 to 20 | m (95 %) | [INTEROP25] SIM (17.2 m); [LDN25, ML24] REQ |
| LANS horizontal accuracy without height constraint | 120 | 40 to 360 | m (95 %) | [INTEROP25] SIM |
| LANS per-satellite range error (SISE) | 4.5 | 4.5 to 20 | m (1-sigma) | [INTEROP25] (13.43 m 3-sigma); [AFS1] ceiling of 40 m at 95 % |
| LANS availability of a fix, 2026 | 0 | 0 | fraction of time | no satellite in orbit on 11 Nov 2026 (B2) |
| LANS availability, 2027 | 0 | 0 | fraction | one AFS at most: time and one range, no fix [GRAM24] |
| LANS availability, 2028 | 0 | 0 to 0.2 | fraction | two AFS planned by mid-2028 [GRAM24]; Moonlight initial operations end of 2028 [ESA24]; A |
| LANS availability, 2029 | 0.4 | 0.2 to 0.9 | fraction | IOC-C target 40 % with GDOP < 6 [GRAM24]; five-node demo had 3 or more in view all day [INTEROP25]; A |
| LANS availability, 2030 | 0.6 | 0.4 to 0.9 | fraction | Moonlight full operations: at least 15 of 24 hours [ML24, ESA24]; A |
| LANS availability, 2031-32 | 0.8 | 0.6 to 1.0 | fraction | adds LNSS service [MUR26]; A |
| LANS schedule slip | 1 | 0 to 3 | years | A; one milestone slipped at least 6 months in 2026 (B2) |
| Clock drift, crystal class (TCXO) | 4 x 10^-7 = 35 | 2 x 10^-7 to 1 x 10^-6 = 17 to 86 | fraction; ms/day | [LUGRE26] MOON (0 to 8 x 10^-7 with temperature); 1 x 10^-6 from existing notes |
| Clock drift, chip-scale atomic clock | 3 x 10^-10 = 26 | 1 x 10^-11 to 1 x 10^-9 = 0.9 to 86 | fraction; microseconds/day | [CSAC] (temperature term; Allan floor; monthly ageing) |
| Clock drift, rubidium at the base | 1 x 10^-12 = 0.09 | 1 x 10^-13 to 1 x 10^-11 | fraction; microseconds/day | [INTEROP25] (MiniRAFS Allan deviation); A for long term |
| Relativistic rate, Moon surface minus Earth | +56.02 | fixed; +/-0.11 periodic | microseconds/day | [ASH24, KK24, TUR25] |
| Time-transfer accuracy, two-way over a surface link | 100 | 10 to 1,500 | ns | A; bounded by [NIST-TT] (1 ns, calibrated), [CSAC] (100 ns) and [G8271] (1.5 microseconds) |
| Time accuracy from LANS | 500 | 100 to 1,000 | ns | [ML24] REQ ("sub microsecond") |
| Interval between time resynchronisations | 600 | 10 to 86,400 | s | A; sweep against the table in B7 |
| Time-stamp error allowed on a position report | 10 | 1 to 100 | ms | CALC (E6) |
| Earth link available for ground-in-the-loop fixes | 0.5 | 0.17 to 0.86 | fraction of time | [GRAM25] (17 to 43 % direct; 80 to 86 % with one relay) |

Consistency with the existing notes: speeds, radio line-of-sight ranges, relay coverage and the 56.02
microseconds/day rate are the same values. The crystal drift now has a measured lunar range.

---

## E. Proof sketches we can put in a paper

All derivations are first-order and state their assumptions. Numbers marked CALC were checked with a short
script.

### E1. Error growth of dead reckoning (random walk plus bias)

Assumptions: flat ground, straight path, speed v, small heading error, independent error sources.

Along the track, the odometer has a scale error eps (unmodelled slip) and white noise:

    e_along(d) = eps * d + w(d),      Var[w(d)] = s^2 * d        (s in m per sqrt(m))

Across the track, the error is the integral of the heading error dpsi:

    d(e_cross)/dt = v * dpsi(t)

Case (a), gyro only, initial error dpsi0, constant bias b (rad/s), angle random walk N (rad/sqrt(s)):

    e_cross(t)  = v*dpsi0*t + (1/2)*v*b*t^2
    Var_rw(t)   = v^2 * N^2 * t^3 / 3

Case (b), star tracker with a fixed misalignment beta and white noise sig_psi sampled every Delta seconds:

    e_cross(d)  = beta * d,       Var_rw(t) = v^2 * sig_psi^2 * Delta * t

Total (1-sigma), case (a):

    sigma_p^2 = (eps*d)^2 + s^2*d + (v*dpsi0*t)^2 + (v*b*t^2/2)^2 + v^2*N^2*t^3/3,    d = v*t

Consequences:

- The bias terms grow in proportion to distance (a constant "percent of distance"). The random terms grow as
  the square root, so their percentage falls with distance. A quoted "2 %" is therefore a bias-dominated
  number over tens to hundreds of metres.
- Gyro-only sideways error as a fraction of distance is b*t/2: half the accumulated heading error.
  With b = 3 deg/h [MAIM07] = 1.45 x 10^-5 rad/s and t = 1 h: 2.6 % of distance, that is 18.8 m after 720 m
  at 0.2 m/s and 94 m after 3.6 km at 1 m/s (CALC). After 2 h: 5.2 %.
- With a star tracker and beta = 0.1 deg = 1.75 x 10^-3 rad: 0.17 % of distance, at any time (CALC).
- So the heading reference, not the odometer, decides whether a rover holds 2 %.

### E2. How fixes and a ranging network bound the drift

**Scalar steady state.** Let the variance grow by Q between fixes and let each fix have variance R. With
P- the variance before a fix and P+ after it:

    P-  = P+ + Q
    P+  = P- * R / (P- + R)
    =>  (P+)^2 + Q*P+ - Q*R = 0
    =>  P+ = ( -Q + sqrt(Q^2 + 4*Q*R) ) / 2

Limits: if Q << R then P+ is about sqrt(Q*R); if Q >> R then P+ is about R. The error is bounded for any
Q and R, and the worst error between fixes is sqrt(P+ + Q).

Numbers (CALC), with Q = (k*L)^2 for drift k over a fix spacing L:

| Drift k | Fix spacing L | Fix sigma | Sigma after fix | Sigma just before next fix |
|---|---|---|---|---|
| 2 % | 100 m | 5 m | 2.9 m | 3.5 m |
| 2 % | 500 m | 5 m | 4.6 m | 11.0 m |
| 5 % | 500 m | 5 m | 4.9 m | 25.5 m |
| 2 % | 1,000 m | 10 m (LANS class) | 9.1 m | 22.0 m |
| 2 % | 100 m | 0.3 m (UWB class) | 0.30 m | 2.0 m |

Assumption: the drift between fixes is treated as independent from one interval to the next. A constant
scale error is correlated across intervals; a filter that estimates it does better than this table.

**Cramer-Rao bound for ranging.** A vehicle at position p measures ranges to nodes at known positions a_i:

    r_i = |p - a_i| + n_i,     n_i ~ N(0, sig_i^2),      u_i = (p - a_i) / |p - a_i|

The Fisher information matrix and the bound on any unbiased estimate are

    J = sum_i  u_i * u_i^T / sig_i^2
    Cov(p_hat) >= ( J0 + J )^-1,          J0 = (P-)^-1   (prior from dead reckoning)

Two facts follow. Each range adds information only along its own line of sight u_i. And one range never
gives a fix: J has rank 1, so the bound stays at the prior across the line of sight.

If node i is itself uncertain with covariance P_i and independent of the vehicle, replace sig_i^2 by
sig_i^2 + u_i^T P_i u_i.

**Covariance intersection for vehicle-to-vehicle fusion.** Two vehicles that range to each other repeatedly
share errors, and the correlation is not known. Given two estimates (x_a, P_a) and (x_b, P_b) of the same
position with unknown correlation:

    P^-1     = w * P_a^-1 + (1 - w) * P_b^-1,          0 <= w <= 1
    P^-1 * x = w * P_a^-1 * x_a + (1 - w) * P_b^-1 * x_b

The result is consistent (never over-confident) for any correlation; w is chosen to minimise trace(P). The
price is a larger P than a Kalman update would claim. We propose it as the default rule for mixed fleets
because no company's filter then has to be trusted by the others.

### E3. Geometric dilution of precision for beacons at a polar base

Two-way ranging, so there is no clock unknown. Work in the horizontal plane; beacon i is seen at azimuth
th_i. Each row of H is [cos th_i, sin th_i], all ranges have the same sigma_r, and

    G = H^T H,      Cov = sigma_r^2 * G^-1,      HDOP = sqrt( trace(G^-1) )

**N beacons spread evenly around the vehicle (N >= 3).** Then sum cos^2 = sum sin^2 = N/2 and
sum sin*cos = 0, so G = (N/2)*I and

    HDOP = 2 / sqrt(N)          (N = 4: 1.0;  N = 8: 0.71)

**Vehicle outside the base: two beacons seen at +alpha and -alpha about the line to the base.**

    G = diag( 2*cos^2(alpha), 2*sin^2(alpha) )
    sigma_along = sigma_r / ( sqrt(2) * cos(alpha) )
    sigma_cross = sigma_r / ( sqrt(2) * sin(alpha) )
    HDOP        = sqrt(2) / sin(2*alpha)

With beacon baseline b and distance d from its midpoint, tan(alpha) = b / (2d). Far away (d >> b):
sigma_cross is about sqrt(2) * sigma_r * d / b.

| d / b | HDOP | sigma_cross / sigma_r | sigma_along / sigma_r |
|---|---|---|---|
| 0.5 | 1.41 | 1.00 | 1.00 |
| 1 | 1.77 | 1.58 | 0.79 |
| 2 | 3.01 | 2.92 | 0.73 |
| 5 | 7.14 | 7.11 | 0.71 |
| 10 | 14.2 | 14.2 | 0.71 |

Example (CALC): sigma_r = 0.3 m, b = 500 m, d = 5 km gives 0.21 m along the line to the base and 4.2 m
across it. Beacons at a base give a good distance to the base and a poor bearing. The cure is a long
baseline (a mast on a distant rim) or a second cluster.

**Vertical.** Beacons and vehicle differ in height by dh over a horizontal distance d. The vertical component
of u_i is about dh/d, small, so the vertical bound is about d/dh times worse than the horizontal one. Take the
height from the map instead (0.3 to 0.5 m RMS [BARK21]).

**What is special at the pole.**

- Radio line of sight is set by rims and peaks (existing notes). A vehicle on a crater floor sees only
  beacons on the rim. Beacons on one side of the rim give the two-beacon case above; beacons spread around
  the rim give the evenly-spread case.
- For LANS the receiver clock is a fourth unknown and the rows of H become [u_i, 1]. Satellites in elliptical
  frozen orbits dwell high over the south pole, so the u_i share a large vertical part and the vertical and
  clock columns are nearly parallel (our reading of the geometry). It is consistent with the predicted error
  falling from 121.6 m (95 %) to 17.2 m when the height is fixed from the map [INTEROP25].
- The Sun is low and circles the horizon; that affects cameras and sun sensors, not ranging.

### E4. Relativistic clock-rate offset between the lunar surface and Earth

Assumptions: Earth and Moon as point masses on a circular mutual orbit; work in the frame of their common
centre of mass; ignore the Sun (it acts only through tides, which the full treatments show to be far
smaller); first order in 1/c^2. A clock's rate relative to coordinate time is

    d(tau)/dt = 1 - ( U + v^2/2 ) / c^2

with U the Newtonian potential (positive) and v the speed at the clock.

Constants [ASH24, Table I]: GM_E = 3.986004418 x 10^14 m^3/s^2; GM_M = 4.90280031 x 10^12 m^3/s^2;
a = 3.84399 x 10^8 m; c = 299,792,458 m/s. Lunar radius R_M = 1,737.4 km.

Term 1, Earth clock on the geoid (own potential plus rotation), the IAU defining constant:

    L_G = 6.969290134 x 10^-10                       = 60.2147 microseconds/day

Term 2, Moon clock on the surface, own potential (rotation is negligible: 4.6 m/s):

    L_L = GM_M / (R_M c^2) = 3.1398 x 10^-11         =  2.7128 microseconds/day

Term 3, orbital motion and the other body's potential. With mu = GM_M / (GM_E + GM_M) = 0.012151 and
relative orbital speed squared v_rel^2 = (GM_E + GM_M)/a = 1.049698 x 10^6 m^2/s^2:

    Moon:   U = GM_E/a = 1.036944 x 10^6;   v^2/2 = (1-mu)^2 * v_rel^2 / 2 = 5.12172 x 10^5
    Earth:  U = GM_M/a = 1.27545 x 10^4;    v^2/2 = mu^2 * v_rel^2 / 2     = 77.5
    L_orb = ( 1.036944e6 + 5.12172e5 - 1.27545e4 - 77.5 ) / c^2
          = 1.7093 x 10^-11                          =  1.4769 microseconds/day

Result, Moon clock minus Earth clock:

    rate = L_G - L_L - L_orb = 6.4844 x 10^-10       = +56.025 microseconds/day   (CALC)

The lunar clock runs fast. Published values: 56.0199(12) [ASH24], 56.025 with the same three terms
(60.2147 - 2.7128 - 1.4769) [KK24], 56.0256 [TUR25]. Leaving out term 2 gives 58.7, the figure in [OSTP24].

Periodic part: the orbit is eccentric (e = 0.0549), so term 3 varies as -0.1084 cos(f) microseconds/day
[ASH24]. Integrated over the anomalistic month (27.55 days) the clock offset swings by
0.1084 x 27.55 / (2 pi) = 0.475 microsecond, which matches the 0.470 and 0.5 microsecond amplitudes in
[TUR25] and [KK24].

In distance: 56.02 microseconds x c = 16.8 km per day (CALC). That is about 1,250 times the 13.43 m
signal-in-space allowance of one LCRNS satellite [INTEROP25], reached in a single day without correction.

### E5. Timing-to-ranging conversion

One-way ranging. Transmitter clock error d_t, receiver clock error d_r:

    rho = c * (t_receive - t_transmit) = r + c * (d_r - d_t)
    1 ns  <->  0.2998 m

The receiver removes its own d_r by solving for it with a fourth measurement. The transmitters' d_t cannot be
removed by the user; it is part of SISE. A 13.43 m (3-sigma) SISE [INTEROP25] allows at most 45 ns
(3-sigma) of clock error even with a perfect orbit.

Two-way ranging, single-sided. A sends, B replies after T_reply, A measures T_round:

    ToF = ( T_round - T_reply ) / 2
    error = (1/2) * T_reply * (e_A - e_B)          (e = fractional rate error of each clock)
    range error = c * T_reply * (e_A - e_B) / 2

With T_reply = 1 ms: 3.0 m for 20 ppm crystals; 0.15 m for 1 ppm; 0.05 mm for chip-scale atomic clocks
(CALC). Double-sided two-way ranging adds a third message so that the T_reply term cancels; it is the
"widely adopted" method [SHAL22]. The residual is of order c * ToF * e: 6 mm at 300 m with 20 ppm (CALC).
Conclusion: two-way ranging needs no synchronisation and no good clock. It needs a calibrated antenna delay.

### E6. Timing needed for coordination

**Shared slots.** Two nodes whose clocks differ by up to D, at most d_max apart, with radio turn-around
T_sw:

    T_guard >= 2*D + d_max / c + T_sw

d_max = 10 km costs 33.4 microseconds; 5 km costs 16.7 (CALC). The fraction of air time lost is
T_guard / T_slot. With 10 ms slots and 1 % allowed loss, T_guard = 100 microseconds, so D is about 30
microseconds. Cellular TDD asks for 1.5 microseconds [G8271].

**Time-stamped position.** A report "I was at x at time t" from a vehicle at speed v, read by a node whose
clock differs by D, is wrong by

    dx = v * D

For dx = 0.1 m: D = 25 ms at 4 m/s, 100 ms at 1 m/s, 1 s at 0.1 m/s. We specify 10 ms.

**Reservation of a road segment.** Vehicle A holds a segment until t1; vehicle B may enter at t1 + m. A is
late or early by its clock error D_A plus its along-track position error divided by its speed; the same for
B. No overlap is guaranteed if

    m >= D_A + D_B + sigma_A / v_A + sigma_B / v_B

With sigma = 5 m and v = 1 m/s the position terms are 5 s each; with v = 0.1 m/s they are 50 s each. Clock
errors of 0.1 s are negligible against that. The margin on a lunar road is set by positioning, not by
timekeeping. This links the two halves of this note.

**Holdover.** After a synchronisation with residual x0, a free-running clock with fractional offset y0 and
linear ageing A (per second) has time error

    x(t) = x0 + y0 * t + (1/2) * A * t^2  (+ random part, about sigma_y(tau) * tau)

Time to reach a given error with y0 alone (CALC):

| Error | Crystal 10^-6 | Crystal 2 x 10^-7 | Chip-scale atomic 3 x 10^-10 | Rubidium 10^-12 |
|---|---|---|---|---|
| 10 ns | 0.01 s | 0.05 s | 33 s | 2.8 hours |
| 1 microsecond | 1 s | 5 s | 56 minutes | 11.6 days |
| 100 microseconds | 100 s | 500 s | 3.9 days | years |
| 10 ms | 2.8 hours | 13.9 hours | about 78 days with ageing | years |
| 0.1 s | 27.8 hours | 5.8 days | more than 6 months with ageing | years |

For the chip-scale atomic clock the ageing term (9 x 10^-10 per month [CSAC]) takes over after some weeks;
the last two rows include it.

---

## F. Who to partner with

"Realistic" means: a team of a few researchers can get a useful answer or data without a contract.

| Piece | Owner | What we would ask for | Public page (opened unless noted) | Realistic? |
|---|---|---|---|---|
| LNIS, AFS signal definition, LunaNet Reference Time | NASA SCaN with ESA and JAXA (LNIS working group) | status of the time and frame standard (AD5); whether surface-to-surface PNT will be standardised; a channel for comments on rover use cases. The page says the effort "will continue to seek input" from the community | https://www.nasa.gov/directorates/somd/space-communications-navigation-program/lunanet-interoperability-specification/ | Yes, as commenters |
| LCRNS service and requirements | NASA Goddard, LCRNS project | the service requirements document (we could not find it), coverage and DOP products for the south-pole volume, current dates | https://www.nasa.gov/goddard/esc/lcrns and https://etd.gsfc.nasa.gov/our-work/lcrns/ | Partly: public products yes, programme time no |
| Lunar Data Network satellites (Altus-1 and later) | Intuitive Machines | orbit files after launch; AFS test signal plans | company site not opened (the IM-3 page we tried returned 404) | Low until after launch |
| Moonlight navigation service | ESA; Telespazio-led industry team | the rover performance study (ENC 2023) and its assumptions; user-terminal specifications | https://www.esa.int/Applications/Connectivity_and_Secure_Communications/Moonlight | Medium |
| LNSS and surface beacons | JAXA (M. Murata, address printed in [INTEROP25]); ArkEdge Space | their plan for two-way ranging to surface beacons and for monitoring stations | [MUR26] slides at ioag.org | Medium, by e-mail |
| Lunar PNT coordination | UN ICG Working Group on Lunar PNT; IOAG cislunar workshops | attend, present the mixed-fleet use case | workshop files at ioag.org and unoosa.org [GRAM24, MUR26] | Yes |
| Weak-signal GNSS data from the Moon | NASA Goddard, ASI, Politecnico di Torino, Qascom (LuGRE) | nothing to ask: the data set is public | https://doi.org/10.5281/zenodo.16411686 (DOI printed in [LUGRE26]; record not opened) | Yes, today |
| South-pole elevation models and their error maps | NASA Goddard Planetary Geodesy (PGDA) | nothing to ask: public; possibly newer products for our site | https://pgda.gsfc.nasa.gov/products/78 | Yes, today |
| Crater and dark-crater localisation (LunarNav, ShadowNav) | JPL Robotics (authors' addresses are printed in [DAF23, ATHA24]) | test data from Cinder Lakes; failure statistics by terrain type; whether code can be shared | https://arxiv.org/pdf/2405.01673 | Medium, academic contact |
| On-board map matching in flight (Mars Global Localization) | JPL (J. Nash, V. Verma) | time and compute cost per fix; plans for the Moon | https://www.jpl.nasa.gov/news/nasas-perseverance-now-autonomously-pinpoints-its-location-on-mars/ | Medium |
| Multi-rover ranging in flight hardware | JPL CADRE project | flight ranging accuracy and range after IM-3; the mesh-ranging code is listed as public at github.com/nasa/UWB-mesh-ranging (cited in [KNOW24]; repository not opened) | https://robotics.jpl.nasa.gov/what-we-do/flight-projects/cooperative-autonomous-distributed-robotic-exploration-cadre/ | Medium; code yes |
| Ranging-aware planning, DEM-anchored SLAM | Stanford University NAV Lab (G. Gao) | joint simulation study on mixed fleets; their open simulator | https://arxiv.org/pdf/2406.16679 and https://arxiv.org/pdf/2603.17229 | Yes |
| VIPER localisation and lighting | NASA Ames Intelligent Robotics Group | accuracy of terrain registration; the rover simulator | https://ntrs.nasa.gov/api/citations/20240013292/downloads/PESTO-VIPER-T_Fong.pdf | Medium |
| Analogue field data with ground truth | University of Toronto ASRL (Devon Island set: stereo, sun sensor, inclinometer, DGPS, 10 km) | nothing to ask: public | https://asrl.utias.utoronto.ca/datasets/devon-island-rover-navigation/ | Yes, today |
| UWB anchors on analogue missions | University of Wuerzburg (A. Nuechter) with the Austrian Space Forum; University of Trento with Thales Alenia Space (PLaNS) | range and accuracy outdoors beyond 100 m | https://arxiv.org/pdf/2504.07658 | Yes |
| Lunar time scale: theory | NIST Time and Frequency Division (Ashby, Patla); JPL (Turyshev et al.) | review of our E4 text; advice on naming the scale in messages | https://www.nist.gov/pml/time-and-frequency-division/time-services/time-transfer | Yes, by e-mail |
| Lunar time scale: metrology and UTC traceability | BIPM Time Department; Royal Observatory of Belgium; Paris Observatory (addresses printed in [BOU26]) | which realisation they expect a surface network to use | https://arxiv.org/pdf/2507.21597 | Yes, by e-mail |
| Lunar time policy | NASA SCaN (lead for Coordinated Lunar Time) | whether the strategy due 31 December 2026 will be public | https://www.nasa.gov/solar-system/moon/nasa-to-develop-lunar-time-standard-for-exploration-initiatives | Low |
| Clocks | Microchip (chip-scale atomic clocks; a separate space version exists, data sheet not opened) | radiation and thermal data; price | data sheet copy: https://gps-world.biz/wp-content/uploads/2023/10/microchip-csac-sa65-1.pdf | Yes, as a customer |
| Base time and beacon mast | NASA Glenn (Lunar Surface Relay concept) | clock and retroreflector plans; mast survey accuracy | https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf | Medium |

---

## G. Open questions, risks, what we could not verify, and sources

### G1. Open questions and risks

1. **LANS schedule.** IOC-Alpha was planned for September 2026 and no satellite has launched. Each later
   phase may slip too. Our design must work with layer 4 switched off for the whole study period.
2. **No surface-to-surface PNT standard.** LNIS v5 defines the satellite signal. Ranging between vehicles and
   to surface beacons is not standardised (existing notes reach the same finding for the radio link). This is
   the gap our protocol fills; it is also a risk, because every company may pick a different ranging radio.
3. **UWB on the Moon is unproven.** All accuracy figures are from Earth, indoors or over tens of metres.
   Range, multipath over regolith, thermal behaviour and radiation tolerance are unknown. CADRE would be the
   first data point and has not flown.
4. **AFS next to Wi-Fi.** The AFS band begins at 2483.5 MHz [AFS1]. The 2.4 GHz band used by lander Wi-Fi
   (existing notes) ends at the same frequency on Earth (standard allocation; not re-checked in this
   session). AFS arrives at -160 to -147 dBW. We found no public interference analysis.
5. **Terrain fixes in permanently shadowed regions.** Maps are coarser there and the only tested method needs
   craters with a clear leading edge. Failure rates by terrain type are not published.
6. **Whose map?** Absolute fixes are only as consistent as the maps. Two companies using different DEM
   versions will disagree by the map offset. The LOLA products are good to 0.1 to 0.2 m horizontally, but
   image-based products registered to them may not be.
7. **Lunar time is not yet defined in practice.** LunaNet Reference Time has no released standard; the US
   strategy is due on 31 December 2026; the IAU defined the coordinate time (TCL) only. Papers in 2025-26
   disagree on whether the working scale should be TCL itself or a rescaled version. Our messages must carry
   a time-scale identifier so that the choice can change.
8. **Thermal swings and crystals.** LuGRE's crystal moved by several parts in 10^7 with temperature. Rovers
   crossing in and out of shadow will see larger swings. Holdover numbers in B7 are for constant rates.
9. **Dust.** Star trackers, cameras and lamps are optical. The existing notes record Apollo's experience with
   dust on lenses. No source gives a degradation rate for a star tracker on a rover.
10. **Speed.** All drift figures come from rovers at 0.01 to 0.2 m/s (Mars, VIPER) or from a crewed vehicle
    (LRV). Visual odometry at 2 to 4 m/s on regolith with lamps has no published accuracy.
11. **Integrity.** None of the cited rover methods publishes a probability of a wrong fix that is declared
    good. Traffic rules need that number more than the mean error.
12. **Height.** Most of the methods above are horizontal. Slopes and crater walls need the map height, with
    0.3 to 0.5 m RMS error and rare errors above 1 m [BARK21].

### G2. What we could not verify (and what we tried)

- **LCRNS service requirements document.** Not found by search. The 13.43 m figure and the IOC-C numbers come
  from papers and slides that quote it [INTEROP25, LDN25, GRAM24].
- **IAU 2024 Resolutions II and III.** The links `iau.org/static/resolutions/IAU2024_Resol2_English.pdf` and
  `..._Resol3_English.pdf` returned an error page. We rely on the quotation in [DEF25].
- **IM-3 and Blue Ghost Mission 2 dates.** From Wikipedia pages read on 11 November 2026, which cite Aerospace
  America (15 September 2026) and a company financial report. We did not open those. UNVERIFIED at primary
  level.
- **Whether NASA has delivered the lunar time strategy.** No public statement found in either direction.
- **UWB maximum range.** The vendor's page (qorvo.com) blocked automated access; data-sheet mirrors returned
  "not found". The often-quoted 290 m is UNVERIFIED.
- **Sun-sensor heading accuracy on rovers.** "Within a few degrees" (Furgale, Enright, Barfoot 2011) and
  "+/-3 deg" (JPL FIDO rover) appeared only in search summaries; the pages did not load. UNVERIFIED. The
  error reduction in Lambert et al. 2012 (Devon Island, 10 km) could not be read: the paper is behind a
  paywall and no preprint was found. Only the data-set page was opened [DEVON].
- **Star tracker accuracy in arcseconds.** A vendor page was opened but shows no figures. We use the
  qualitative statements in [DAF23] and [BLUE24].
- **VIPER terrain-registration accuracy.** Not in the three NASA documents opened.
- **Yutu-2 localisation accuracy.** Search results only; nothing opened. Not used.
- **Perseverance visual-odometry drift as a percentage.** The 2023 Science Robotics paper was not opened. We
  use the "up to 35 meters" statement in [JPL26].
- **JAXA's earlier "40 m at any time" requirement** (2022 ICG slides) appeared only in a search summary.
  UNVERIFIED and not used.
- **3GPP specifications.** Not opened; the 1.5 microsecond figure is from ITU-T G.8271, which lists it for
  LTE-TDD and NR TDD.
- **ESA's ALPER absolute-localisation paper** (ASTRA 2023): the server's certificate did not validate.
- **LNSS milestone years.** The slide lists FY2029, FY2031, FY2033 and "FY2040~" next to four milestones;
  the text extraction does not show which year belongs to which. Only "demonstration in 2029" is used.
- **One internal inconsistency in a source.** [INTEROP25] quotes a 13.5 m mean in its text and 35.7 m in its
  table for the same case.

### G3. Findings that differ from the existing notes

1. `vehicles_comms_internals.md`, section 2.1, describes the AFS as "spreading bandwidth 6.16 MHz, about
   3 Mcps". In LNIS v5 that sentence is about spread-spectrum S-band proximity links. The AFS document gives
   1.023 Mchip/s for the data component and 5.115 Mchip/s for the pilot [AFS1].
2. Same note, section 1.4: CADRE on IM-3 "planned for 2026". Now the first quarter of 2027 [WIKI-IM3].
3. Same note, section 1.5: Blue Ghost Mission 2 with Lunar Pathfinder "late 2026 or 2027". Now 2027
   [WIKI-BGM2].
4. Same note, section 2.7: the crystal drift of "about 1 ppm, roughly 86 ms a day" was an assumption. LuGRE
   measured 0 to 8 x 10^-7 on the lunar surface [LUGRE26]: same order, somewhat lower, and strongly
   temperature-dependent.
5. Same section gives 56.02 microseconds/day only. The OSTP memo itself says 58.7; the difference is the
   Moon's own potential (B6). No change to the value we use.
6. Same section: "Whether the plan has been delivered was not checked." Checked on 11 November 2026: no
   public evidence of delivery; the deadline is 31 December 2026.

### G4. Sources (all opened in this session unless marked)

Format: key, author or organisation, title, year, URL. "NTRS" is the NASA Technical Reports Server.

Positioning systems and standards

- [LNIS5] NASA, ESA, JAXA. LunaNet Interoperability Specification, Version 5. 2025.
  https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-interoperability-specification-v5-baseline.pdf
- [AFS1] NASA, ESA, JAXA. LunaNet Signal-In-Space Recommended Standard - Augmented Forward Signal, Vol. A,
  Version 1. 2025.
  https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-signal-in-space-recommended-standard-augmented-forward-signal-vol-a.pdf
- [LNPAGE] NASA. LunaNet Interoperability Specification (web page, read 11 Nov 2026).
  https://www.nasa.gov/directorates/somd/space-communications-navigation-program/lunanet-interoperability-specification/
- [GRAM24] Gramling and Crenshaw (NASA). NASA's LunaNet: Lunar Communications and PNT. ICG, 25 Jun 2024.
  https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_01_02.pdf
- [GRAM25] Gramling (NASA). LunaNet, Interoperability, and NASA's Lunar Relay PNT Services. 5 Mar 2025.
  https://ntrs.nasa.gov/api/citations/20250002120/downloads/LunaNet%20%20and%20NASA%20LCRNS%20-MGAconf%205Mar2025.pdf
- [INTEROP25] Gramling, Crenshaw, Murata, Swinden, Melman, Stallo, Ventura-Traveset. Towards LunaNet Lunar
  Augmented Navigation Service (LANS) Interoperability Demonstration and Monitoring. SpaceOps 2025.
  https://ntrs.nasa.gov/api/citations/20250003163/downloads/LANS%20Interop%20Demo-SpOps2025%20ID429%20v4Final.pdf
- [LDN25] Brack et al. Preliminary Design of the Lunar Data Network Constellation under Operational
  Considerations. AAS 25-758, 2025. https://ntrs.nasa.gov/api/citations/20250006883/downloads/AAS_25_758_LDN_design_v7.pdf
- [ML24] Ventura-Traveset (ESA). Moonlight Navigation Services (slides). 2024.
  https://bsgn.esa.int/wp-content/uploads/2024/02/07-Moonlight_LCNS_S4I_2024_Javier-Ventura-Traveset.pdf
- [ESA24] ESA. ESA's Moonlight programme: Pioneering the path for lunar exploration. 15 Oct 2024.
  https://www.esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration
- [MUR26] Murata (JAXA). Japan LNSS and Towards LunaNet LANS Interoperability Demonstration. ICG-IOAG
  Cislunar PNT Workshop, 10 Feb 2026.
  https://ioag.org/Cislunar2026/Tuesday/02%20Lunar/1125%20LNSS_LANS_demo_Cislunar_PNT_Workshop.pdf
- [GSFC-LCRNS] NASA Goddard. Exploration and Space Communications: LCRNS (web page, read 11 Nov 2026).
  https://www.nasa.gov/goddard/esc/lcrns
- [VIASAT26] Via Satellite. Building the Connectivity Backbone for the Next Era of Lunar Exploration.
  27 Jul 2026.
  https://www.satellitetoday.com/space-economy/2026/07/27/building-the-connectivity-backbone-for-the-next-era-of-lunar-exploration/
- [WIKI-IM3] Wikipedia. IM-3 (secondary; read 11 Nov 2026). https://en.wikipedia.org/wiki/IM-3
- [WIKI-BGM2] Wikipedia. Blue Ghost Mission 2 (secondary; read 11 Nov 2026).
  https://en.wikipedia.org/wiki/Blue_Ghost_Mission_2
- [WIKI-LPF] Wikipedia. Lunar Pathfinder (secondary; read 11 Nov 2026).
  https://en.wikipedia.org/wiki/Lunar_Pathfinder
- [LUGRE26] Parker et al. GNSS Reception at the Moon: First Results of the Lunar GNSS Receiver Experiment
  (LuGRE). NAVIGATION 73(1), 2026, DOI 10.33012/navi.756. Open-access copy read:
  https://iris.polito.it/retrieve/1383355f-0c92-43cd-b505-a11b56b5d792/navi.756.full.pdf
- [LUGRE-MGA] NASA. LuGRE presentation, Multi-GNSS Asia 2026.
  https://ntrs.nasa.gov/api/citations/20260002034/downloads/MGA2026_LuGRE_v2.pdf

Rover navigation

- [LRV73] Smith and Mastin (NASA MSFC). Lunar Roving Vehicle Navigation System Performance Review. NASA
  TN D-7469, 1973. https://ntrs.nasa.gov/api/citations/19740003321/downloads/19740003321.pdf
- [MCKEE25] McKee (NASA). A Survey of Autonomous Navigation Techniques Applicable to Lunar Surface
  Exploration. AAS 25-173, 2025. https://ntrs.nasa.gov/api/citations/20250000720/downloads/Lunar_Surface_Nav_Survey_AAS_GNC_011825.pdf
- [MAIM07] Maimone, Cheng, Matthies (JPL). Two Years of Visual Odometry on the Mars Exploration Rovers.
  Journal of Field Robotics, 2007. https://robotics.jpl.nasa.gov/media/documents/rob-06-0081.R4.pdf
- [HELM06] Helmick et al. (JPL). Slip-Compensated Path Following for Planetary Exploration Rovers. Advanced
  Robotics, 2006. https://robotics.jpl.nasa.gov/media/documents/advanced_robotics_2006.pdf
- [DAF23] Daftry et al. (JPL, NASA Ames). LunarNav: Crater-based Localization for Long-range Autonomous Lunar
  Rover Navigation. IEEE Aerospace 2023. https://arxiv.org/pdf/2301.01350
- [CAU23] Cauligi, Swan et al. (JPL). ShadowNav: Crater-Based Localization for Nighttime and Permanently
  Shadowed Region Lunar Navigation. IEEE Aerospace 2023. https://arxiv.org/pdf/2301.04630
- [ATHA24] Atha et al. (JPL). ShadowNav: Autonomous Global Localization for Lunar Navigation in Darkness.
  2024. https://arxiv.org/pdf/2405.01673
- [SNPOSTER] Atha et al. (JPL). ShadowNav: Lunar Absolute Localization in Darkness using Craters as
  Landmarks (poster). 2023. https://www.jpl.nasa.gov/site/research/media/posters/2023/R21009p.pdf
- [NASH24] Nash et al. (JPL). Censible: A Robust and Practical Global Localization Framework for Planetary
  Surface Missions. ICRA 2024.
  https://www-robotics.jpl.nasa.gov/media/documents/2024_Global_Localization_ICRA.pdf
- [NASH26] Nash, Verma et al. (JPL). A Software-Based Approach to Radiation Mitigation for Planetary
  Missions. IEEE Aerospace 2026.
  https://www-robotics.jpl.nasa.gov/media/documents/2026_Global_Localization_Memory_Workaround_IEEE_Aero__final.pdf
- [JPL26] JPL. NASA's Perseverance Now Autonomously Pinpoints Its Location on Mars. 18 Feb 2026.
  https://www.jpl.nasa.gov/news/nasas-perseverance-now-autonomously-pinpoints-its-location-on-mars/
- [DAI26] Dai, Casadesus Vila, Gao (Stanford). Visual SLAM with DEM Anchoring for Lunar Surface Navigation.
  2026. https://arxiv.org/pdf/2603.17229
- [KNOW24] Knowles, Dai, Gao (Stanford). Multi-Robot Collaborative Localization and Planning with
  Inter-Ranging. 2024. https://arxiv.org/pdf/2406.16679
- [ZHANG24] Zhang et al. LiDAR-Inertial SLAM with DEM-driven Global Constraints for Planetary Rover
  Exploration. ISPRS Archives, 2024.
  https://isprs-archives.copernicus.org/articles/XLVIII-3-2024/615/2024/isprs-archives-XLVIII-3-2024-615-2024.pdf
- [DRIES24] Driessen et al. (NASA Goddard and others). Monocular Horizon Navigation. 2024.
  https://ntrs.nasa.gov/api/citations/20240011910/downloads/Lunar_Horizon_Navigation_SIW_Paper.pdf
- [FANG19] Fang and Whittaker (CMU). Ray Tracing and Use of Shadows as Features for Determining Location in
  Lunar Polar Terrain. FSR 2019.
  https://www.ri.cmu.edu/app/uploads/2020/05/FSR2019__Ray_Tracing_and_Use_of_Shadows_as_Features_for_Determining_Location_in_Lunar_Polar_Terrain__Camera_Ready.pdf
- [BARK21] Barker et al. (NASA Goddard). Improved LOLA Elevation Maps for South Pole Landing Sites: Error
  Estimates and Their Impact on Illumination Conditions. Planetary and Space Science, 2021.
  https://ntrs.nasa.gov/api/citations/20205009660/downloads/Mike%20Barker_%20Paper_%20Improved%20Lola.pdf
- [PGDA78] NASA Goddard PGDA. High-Resolution LOLA Topography for Lunar South Pole Sites (web page).
  https://pgda.gsfc.nasa.gov/products/78
- [FONG24] Fong (NASA Ames). VIPER Software: Rover, Planning, and Ops. 2024.
  https://ntrs.nasa.gov/api/citations/20240013292/downloads/PESTO-VIPER-T_Fong.pdf
- [VIPER-TI] NASA Ames. VIPER Technologies. 8 May 2023. https://ntrs.nasa.gov/api/citations/20230008814/downloads/TI-VIPER-Tech.pdf
- [BLUE24] Bluethmann (NASA JSC). VIPER Rover Overview and Mobility and Hardware. 14 Nov 2024.
  https://ntrs.nasa.gov/api/citations/20240013903/downloads/LSIC_2024-Tech%20Infusion_Panel-VIPER_Mob-HW.pdf
- [VIPER-OPS] NASA. VIPER Lunar Operations (web page). https://science.nasa.gov/mission/viper/lunar-operations/
- [VIPER-LIGHTS] NASA. VIPER Rover Will Get Driving Headlights (web page).
  https://www.nasa.gov/humans-in-space/viper-rover-will-get-driving-headlights/
- [DEANS05] Deans, Wettergreen, Villa (CMU). A Sun Tracker for Planetary Analog Rovers. 2005 (abstract page
  only). https://www.ri.cmu.edu/publications/a-sun-tracker-for-planetary-analog-rovers
- [DEVON] University of Toronto ASRL. Devon Island Rover Navigation Dataset (web page).
  https://asrl.utias.utoronto.ca/datasets/devon-island-rover-navigation/
- [VN] VectorNav. Inertial Navigation Primer: introduction to inertial sensors (web page).
  https://www.vectornav.com/resources/inertial-navigation-primer/theory-of-operation/theory-inertial
- [LSR23] Scardelletti et al. (NASA Glenn). Lunar Surface Network Relay Terminal: A Lunar Communications
  Platform. ICSSC 2023. https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf

Radio ranging

- [PLANS18] Janicijevic et al. (Trento, Thales Alenia Space). Demo: Small PLaNS Towards Mars: Exploiting
  Ultra-wideband for Self-localizing Rover Navigation. EWSN 2018.
  https://www.ewsn.org/file-repository/ewsn-2018/199_200_janicijevic.pdf
- [NUCH24] Nuechter et al. UWB Anchor Based Localization of a Planetary Rover. i-SAIRAS 2024.
  https://arxiv.org/pdf/2504.07658
- [SHAL22] Shalaby et al. Reducing Two-Way Ranging Variance by Signal-Timing Optimization. 2022.
  https://arxiv.org/pdf/2211.00538

Time

- [OSTP24] White House OSTP. Policy on Celestial Time Standardization in Support of the National Cislunar
  Science and Technology Strategy. 2 Apr 2024.
  https://bidenwhitehouse.archives.gov/wp-content/uploads/2024/04/Celestial-Time-Standardization-Policy.pdf
- [NASA-LTC24] NASA. NASA to Develop Lunar Time Standard for Exploration Initiatives. 12 Sep 2024.
  https://www.nasa.gov/solar-system/moon/nasa-to-develop-lunar-time-standard-for-exploration-initiatives
- [ASH24] Ashby and Patla (NIST). A Relativistic Framework to Establish Coordinate Time on the Moon and
  Beyond. 2024. https://arxiv.org/pdf/2402.11150
- [KK24] Kopeikin and Kaplan. Lunar Time in General Relativity. 2024. https://arxiv.org/pdf/2407.04862
- [TUR25] Turyshev, Williams, Boggs, Park (JPL). Relativistic Time Transformations Between the Solar System
  Barycenter, Earth, and Moon. Dec 2024. https://arxiv.org/pdf/2406.16147
- [BOU26] Bourgoin, Defraigne, Meynadier. Lunar Reference Timescale. Accepted by Metrologia; preprint of
  6 Jan 2026. https://arxiv.org/pdf/2507.21597
- [DEF25] Defraigne, Meynadier, Bourgoin. Lunar Time. 4 Nov 2025. https://arxiv.org/pdf/2511.02709
- [LTE440] Lu, Yang, Xie (Purple Mountain Observatory). Lunar Time Ephemeris LTE440: User Manual. 2025.
  https://arxiv.org/pdf/2506.19213
- [NIST-TT] NIST. Two-Way Satellite Time and Frequency Transfer (web page).
  https://www.nist.gov/pml/time-and-frequency-division/time-services/time-transfer
- [ITU-TF1153] ITU-R. Recommendation TF.1153-1: The operational use of two-way satellite time and frequency
  transfer employing PN codes. 1997.
  https://www.itu.int/dms_pubrec/itu-r/rec/tf/R-REC-TF.1153-1-199706-S!!PDF-E.pdf
- [G8271] ITU-T. Recommendation G.8271/Y.1366: Time and phase synchronization aspects of telecommunication
  networks. 2020.
  https://www.itu.int/rec/dologin_pub.asp?lang=e&id=T-REC-G.8271-202003-I!!PDF-E&type=items
- [CSAC] Microchip. CSAC SA65 Chip-Scale Atomic Clock data sheet (copy).
  https://gps-world.biz/wp-content/uploads/2023/10/microchip-csac-sa65-1.pdf

Downloaded files and extracted text are in the session scratchpad, not in the repository:
`D:\Temp\claude\9f85daca063d7b9d\847c6723-50fc-46d9-813f-2a3b803da8fa\scratchpad\research_pnt\dl`
