# Lunar ATC: vehicles, surface radio network, and vehicle internals

Research note for LunarHaul ("Lunar ATC" direction). Compiled 27 October 2026 from primary sources where they could be reached (NASA, ESA, company pages, NTRS papers). Every number carries a source and a confidence:

- **High**: a primary source states it directly.
- **Medium**: a secondary source, or a primary source that is old or self-inconsistent.
- **Low**: an inference, or a single weak source.
- **Computed**: derived here by arithmetic from cited inputs. The formula is given.

**Repo baseline read first:** `data/vehicle_classes.csv`, `data/lander_types.csv`, `data/parameters.csv`, `lunarsim/rover/physics.py`, `lunarsim/lander/classes.py` and `lunarsim/comms.py`. Where a finding differs from the repo, it is marked **DIFF**.

The 3D cutaway parts (section 3 and the second table) are schematic, not to engineering scale, unless a row says otherwise. No company has published a full internal general-arrangement drawing for any of these vehicles. VIPER, Apollo LRV, Griffin (2021 payload guide) and Starship (tank order) are the best documented.

---

## 1. Vehicles likely at the 2028-2032 south-pole base

### Takeaway

The LTV that NASA actually bought in May 2026 is much smaller than the LTV in the repo.

- **Two Phase 1 LTVs:**
  - Astrolab CLV-1, derived from FLEX.
  - Lunar Outpost Pegasus, a lighter Eagle.
- **NASA's stated capability (20 October 2026):**
  - up to 80 kg of samples and tools;
  - up to 10 km on one charge;
  - up to 6 km a day when remotely operated.
- **Delivery:** both arrive by Blue Origin Blue Moon MK1 in 2028.
- **Intuitive Machines Moon RACER was not selected.**
- **Cargo-class mobility (about 1,500-2,000 kg)** exists only as Astrolab FLEX (2,000 kg on two top-deck interfaces) and Lunar Outpost Eagle. Neither is under NASA contract.
- **Hoppers enter in 2028:** NASA/JPL MoonFall puts four ~250 kg hopping drones near the south pole, carried by Firefly.
- **Landers in the period:**
  - CLPS: Blue Ghost 150 kg, Nova-C ~100-130 kg, Griffin 455-625 kg.
  - Blue Moon MK1: 3 t.
  - ESA Argonaut: 1.5 t, from 2030-2031.
  - Large landers: Blue Moon MK2 and Starship HLS, 2027 or later.

### 1.1 NASA Lunar Terrain Vehicle (LTV): status after May and October 2026

**Award (26 May 2026).** NASA gave Phase 1 "High Achievability Mission" task orders under the LTV Services contract:

- Astrolab $219 M;
- Lunar Outpost $220 M.

Blue Origin received $188 M for two CLPS 1.0 (CX-2) task orders to deliver both rovers to the south-pole region, with an option worth $280.4 M. Source: [NASA release, 26-27 May 2026](https://www.nasa.gov/news-release/nasa-provides-update-on-moon-base-rovers-landers-missions/). **High**.

**The two vehicles (May 2026 release).** **High**.

| Vehicle | Basis | Mass | Speed | Other stated capability |
|---|---|---|---|---|
| Astrolab CLV-1 | Adapted from FLEX | about 2,000 lb (~907 kg) | more than 6 mph (>9.7 km/h) on level terrain | compact stowed configuration |
| Lunar Outpost Pegasus | Lighter evolution of Eagle | not stated | more than 9 mph (>14.5 km/h) | operational up to a year; manual, autonomous or teleoperated driving |

**LTV capability stated by NASA ([progress update, 20-21 October 2026](https://www.nasa.gov/missions/moon-base/nasa-provides-progress-update-on-moon-base-rovers/)).** **High**.

- up to 3.7 miles (6 km) a day when remotely operated;
- up to 176 lb (80 kg) of lunar samples and tools;
- up to 6 miles (10 km) on a single battery charge;
- up to three moonwalks per Artemis mission;
- design reviews: Lunar Outpost PDR in October 2026, Astrolab PDR by end of December 2026;
- flight hardware delivered to NASA by end of 2027.

**FLIP, Astrolab's robotic precursor.**

- FLIP shares tires, batteries, radios and cameras with CLV-1.
- It flies on Griffin Mission One, launching late 2026 to Nobile Crater.
- Mass is about 500 kg ("nearly half a metric ton").
- Payload is 30 kg (Astrolab release) or 30-50 kg (SpaceNews 2024).

Sources: NASA October 2026 update (**High**); [Astrobotic/Astrolab FLIP page](https://www.astrobotic.com/astrolabs-flip-rover-joins-astrobotics-griffin-1-to-the-moon/) (**Medium** for mass).

**Lunar Outpost MAPP (robotic precursor).** NASA's October 2026 text says MAPP "operated at the Moon's South Pole" in 2025 and that a second MAPP launches in early 2027. Other sources disagree: IM-2 Athena landed on its side on 6 March 2025, MAPP was not deployed, and Athena stopped operating less than 13 hours after landing ([IM-2, Wikipedia, citing NASA and Intuitive Machines](https://en.wikipedia.org/wiki/IM-2)). MAPP was probably powered while still stowed on the lander. Treat "operated" as "powered on, did not drive". **Medium**.

**Original LTV requirement, for comparison (as summarised in press from the 2023 RFP):**

- at least 1,765 lb (800 kg) total payload;
- 12 miles (19 km) a day and 800 miles (1,287 km) a year on one charge;
- two suited crew driving up to 20 km on an 8-hour round trip without recharge.

Sources: [Lunar Outpost press and NatGeo coverage](https://www.nationalgeographic.com/science/article/moon-rover-space-innovation-nasa-artemis) (**Medium**). The NASA ACR24 Mobility white paper also limits the LTV to 800 kg of uncrewed cargo mass ([PDF](https://www.nasa.gov/wp-content/uploads/2024/06/acr24-lunar-mobility-drivers-and-needs.pdf), **High**).

**Astrolab FLEX, the cargo-class parent design.** Source: [astrolab.space](https://www.astrolab.space). **High** as company claims.

- "Total payload capacity of 2000 kg comprised of the two top-deck payload interfaces";
- an underslung payload interface that "can mobilize up to 3 m³";
- a six-degree-of-freedom robotic arm with modular end effectors;
- a gimbaling antenna for high-bandwidth communication with Earth;
- sensors for semi-autonomous payload alignment, pick-up and obstacle avoidance.

**DIFF:** the repo cites FLEX at 1,500-1,600 kg. The company page now says 2,000 kg.

**Lunar Outpost Eagle and Pegasus.**

- Eagle has a reconfigurable cargo bed and a robotic arm. It was built with GM, Goodyear, MDA Space and Leidos, and is designed to operate through two-week nights at about -280 °F ([Lunar Outpost](https://www.lunaroutpost.com/post/lunar-outpost-to-unveil-latest-lunar-terrain-vehicle-at-space-symposium-2025), **Medium**).
- Pegasus is "less than half the size of Eagle", has a "greatly reduced logistics payload capacity", and comes "without Eagle's robotic arm" ([Payload Space, 8 May 2026](https://payloadspace.com/lunar-outpost-closes-30m-series-b-unveils-new-rover/), **Medium**).
- Pegasus carries two astronauts, two solar arrays and spring-mesh tires (NASA October 2026 image captions, **High**).
- One report says Pegasus has four in-wheel electric motors and GM high-nickel Li-ion packs with heaters and insulation for night operation (**Medium/Low**).

**Intuitive Machines Moon RACER (not selected).** **Medium**. It is still useful as a design reference.

- about 1.5 t vehicle mass;
- top speed 15 km/h;
- crosses 30 cm obstacles;
- about 1,800 kg total payload, including a towed trailer.

Sources: [IM LTV page](https://intuitivemachines.com/ltv) and [PDR post](https://www.intuitivemachines.com/post/moon-racer-evolves-how-feedback-from-nasa-is-driving-a-new-era-of-lunar-mobility).

**No public battery size (kWh) for any LTV.** Two reference points:

- VIPER: 5,420 Wh at start of life at 0 °C ([NASA, Bluethmann, November 2024](https://ntrs.nasa.gov/api/citations/20240013903/downloads/LSIC_2024-Tech%20Infusion_Panel-VIPER_Mob-HW.pdf), **High**).
- Apollo LRV: two 36 V, 121 Ah silver-zinc batteries, about 8.7 kWh (computed: 2 × 36 V × 121 Ah). Source: [NSSDC](https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html), **High**.

**DIFF (repo `vehicle_classes.csv`, `LTV` row):** the repo has 1,500 kg capacity, 6 km/h, 40,000 Wh battery and 350 Wh/km.

- The battery and energy figures imply 114 km per charge. NASA states 10 km per charge.
- **Suggestion:**
  - keep the 1,500-2,000 kg vehicle as a separate "cargo LTV (FLEX/Eagle-class)" class, flagged as not yet contracted;
  - add a "Phase 1 LTV" class: 80 kg tools and samples, 10 km per charge, 6 km a day uncrewed, ~907 kg vehicle, 2 seats, no arm on Pegasus.
- The speed caps in the repo (9 km/h autonomous) fit inside CLV-1's >9.7 km/h and Pegasus's >14.5 km/h top speeds.

### 1.2 VIPER (returns to the manifest)

**Status.** VIPER will fly to the south-pole region in 2027 on a Blue Moon MK1. It is fully built and in final test at JSC (NASA October 2026 update). **High**.

**Specifications** (Bluethmann, NASA, November 2024). **High**.

- Mass 490 kg at launch, 447 kg roving.
- Size 1.7 × 1.7 × 2.5 m.
- Solar arrays 320 W per panel (450 W with sun on a corner).
- Battery 5,420 Wh.
- Comms: X-band direct to Earth, no relay. Transmit 250 sps to 8 Msps; receive 250 sps to 75 ksps.
- 50 hours survival in low-power mode; 9 hours of operations in permanently shadowed regions.
- Top speed 20 cm/s, nominal 10 cm/s.
- Slopes 15° and obstacles 15 cm (requirements).
- Mobility qualified for 2 × 20 km.
- Travel goal more than 30 km (NASA October 2026).
- Older figure: 256 kbps high-gain downlink, up to 4 Mbps ([2020 overview](https://ntrs.nasa.gov/api/citations/20205000864/downloads/2020-04-14%2C%20VIPER%20Mission%20Overview%20(Andrews).pdf)). **Medium**.

### 1.3 Hoppers

**NASA/JPL MoonFall (Firefly delivery, 2028).** Source: NASA May 2026 release. **High**.

- Four drones fly short hops to survey landing sites.
- Firefly builds the transport spacecraft (Elytra) for $75 M.
- Launch target is 2028.
- Payloads keep working "several months" after each drone's final flight.

Further figures from secondary sources ([Satnews](https://satnews.com/2026/05/27/firefly-aerospace-wins-75-million-nasa-jpl-moonfall-subcontract-to-deliver-drones-to-the-moons-south-pole/), [Interesting Engineering](https://interestingengineering.com/space/nasa-four-moon-drones-spacecraft-design-review), [DroneXL](https://dronexl.co/2026/05/28/nasa-first-moon-drones-fly-hop/)). **Medium**.

- each drone ~550 lb (~250 kg) including propellant;
- about 7 ft wide × 4 ft tall (2.1 × 1.2 m);
- 10 cameras plus instruments each;
- 14 days of hopping;
- about 30 miles (~50 km) of coverage per drone (JPL project lead Ray Baker);
- deployed during descent, about 50 km above the pole;
- Elytra stays in orbit.

**Intuitive Machines Micro-Nova ("Grace").** Sources: [LPSC 2024 abstract 1931](https://www.hou.usra.edu/meetings/lpsc2024/pdf/1931.pdf) and the [IM page](https://www.intuitivemachines.com/micro-nova). **High**.

- Approximately 1 m tall.
- Up to 8 kg of payload over more than 25 km (LPSC 2024). The IM page says up to 10 kg, range-dependent, with up to 25 km ballistic transfer on the current tanks.
- Flight profiles include parabolas and constant-altitude flight.
- Sensors: IMU, star tracker, optical navigation camera, lidar, situational-awareness camera.
- Deployed from the lander on a rail.

On IM-2 it was not deployed because the lander tipped over. **High**.

**DIFF:** the repo has no hopper class. Suggested parameters are in the final table.

### 1.4 Small rovers

**CADRE (JPL).** Sources: [JPL mission page](https://www.jpl.nasa.gov/missions/cadre), [Tech Briefs](https://www.techbriefs.com/component/content/article/50715-nasas-network-of-small-moon-bound-rovers-is-ready-to-roll). **High** unless marked.

- Three four-wheeled, solar-powered rovers, each "about the size of a carry-on suitcase".
- Each has stereo cameras and multistatic ground-penetrating radar.
- They talk to each other and to a base station on the lander through mesh network radios.
- The telecom board also does ultra-wideband (UWB) ranging between rovers and the base station.
- Mission length is one lunar day (about 14 Earth days) at Reiner Gamma on IM-3, planned for 2026. It is not at the south pole.
- The rovers shut down about every half hour to cool, then wake, share health over the mesh and elect a leader (search summary of JPL material, **Medium**).
- **Gap:** CADRE's radio band, data rate and rover-to-rover range are not public in anything reached here.

**Lunar Outpost rover family** ([lunaroutpost.com/rovers](https://lunaroutpost.com/rovers), **High** as company claims).

| Rover | Mass | Payload | Size | Top speed | Night survival |
|---|---|---|---|---|---|
| MAPP | 5-10 kg | 15 kg | 45 × 38 × 40 cm | 10 cm/s | optional |
| MAPP-Ultra | 30 kg | 30 kg | 1 × 2 × 1 m | 1 m/s | optional |
| HL-MAPP | 250 kg | 200 kg | 1 × 2 × 2 m | 3 m/s | yes |

**ispace Tenacious.** About 5 kg. Lost with the Resilience lander on 6 June 2025 after a hard landing ([Spaceflight Now](https://spaceflightnow.com/2025/06/06/ispaces-resilience-lander-crash-lands-on-the-moon/)). **High**. ispace plans a larger lander around 2027 (**Medium**). No ispace rover is confirmed for the south pole in 2028-2032.

### 1.5 Landers

**Blue Moon MK1** ([Gunter's Space Page, 15 April 2026](https://space.skyrocket.de/doc_sdat/blue-moon.htm), Blue Origin). **High/Medium**.

- Height 8.05 m, primary outer diameter 3.08 m.
- Wet mass under 21,350 kg.
- Payload 3 t to the surface (Blue Origin). The cargo variant is cited at 3.6 t.
- One BE-7 engine burning LOX and LH2, about 40 kN (10,000 lbf, about 44.5 kN).
- Power from solar cells, batteries and fuel cells. IMU, star tracker, hot and cold gas thrusters.
- Pathfinder demonstrates "continuous downlink communications" and precision landing within 100 m.

**Status.** Moon Base I (pathfinder "Endurance", to Shackleton connecting ridge) is NET fall 2026. Launch trackers last updated April 2026 show slips. **Medium** on the date.

**Repo check:** `lander_types.csv` MK1 has 2,000-3,000 kg payload. That matches.

**Griffin (Griffin Mission One).** NASA now calls the builder **Voyager Technologies / Voyager Lunar Systems (Pittsburgh)** ([NASA, 13 October 2026](https://nasa.gov/missions/moon-base/nasa-jpl-testing-readies-voyager-technologies-lander-for-moon-mission)). **High**.

- Spacecraft mass 2,789 lb (1,265 kg) as tested, probably without propellant.
- More than 1,100 lb (455 kg) of cargo, including FLIP.
- Falcon Heavy, "later this year" (2026), to Nobile Crater.

Older figures (**High** as company data, older design): the Astrobotic page and the 2021 payload user's guide give 625 kg payload, 100 m landing accuracy and a 15 cm hazard threshold.

**Firefly Blue Ghost** ([Firefly](https://fireflyspace.com/blue-ghost), [NSF](https://www.nasaspaceflight.com/2025/01/blue-ghost-hakuto-r-launch/)). **High**.

- 2 m tall, 3.5 m diameter.
- 150 kg to the surface.
- Mission 1 landed at Mare Crisium on 2 March 2025. It operated about 14 days plus about 5 hours into night (ended 16 March 2025) and returned about 119 GB, of which 51 GB was science and technology data.
- Mission 2 (far side) carries the Lunar Pathfinder relay commissioning payload. It is scheduled for late 2026 or 2027.

**Intuitive Machines Nova-C** ([Wikipedia](https://en.wikipedia.org/wiki/Intuitive_Machines_Nova-C), [LPSC 2024](https://www.hou.usra.edu/meetings/lpsc2024/pdf/1931.pdf)). **High/Medium**.

- Hexagonal body, six legs.
- 3.94 m (Wikipedia) or 4.3 m (IM) tall, about 1.57-2 m wide.
- 1,908 kg at launch, of which 845 kg LOX and 422 kg CH4.
- One VR900 methalox engine, 3,100 N.
- 100-130 kg payload, 200 W of solar on the surface, 25 Ah battery, 28 V bus.
- Variants: Nova-D up to 2,500 kg (LPSC 2024); Nova-M about 5,000 kg (reports).

**ESA Argonaut** ([ESA](https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Argonaut_lunar_lander_family_grows), [Thales Alenia Space](https://www.thalesgroup.com/en/worldwide/space/press_release/thales-alenia-space-signs-contract-esa-develop-argonaut-lunar-lander)). **High/Medium**.

- Up to 1.5 t of cargo per lander, launched on Ariane 6.
- Thales Alenia Space prime contract for the Lunar Descent Element worth €862 M, signed 30 January 2025.
- First mission 2030 per ESA; 2031 per other reports.
- About 9,900 kg launch mass, about 6 m long, 4.5 m diameter (Wikipedia only, **Medium**).

**Starship HLS** ([Wikipedia](https://en.wikipedia.org/wiki/Starship_HLS), citing NASA). **Medium**.

- 52 m tall, 9 m diameter.
- High-thrust methalox landing engines in the mid-body.
- A band of solar panels around the circumference.
- A crew and cargo elevator, tested with astronauts in December 2023.
- The infobox lists "100,000 kg payload to lunar surface". This is a SpaceX aspiration, not a NASA requirement.
- An October 2026 NASA schedule puts the propellant-transfer demonstration in early 2027 and the uncrewed lunar landing demonstration in late 2027.

**Large cargo landers (NASA ACR24 Lunar Surface Cargo white paper).** **High**.

- Recurring logistics need is 2,500-10,000 kg a year.
- Occasional large deliveries reach 12,000-15,000 kg ([PDF](https://www.nasa.gov/wp-content/uploads/2024/06/acr24-lunar-surface-cargo.pdf)).

The repo's LARGE class (12-30 t) already covers this.

**Moon Base Architecture User's Guide (April 2026, NP-2026-04-6806-HQ).** No public URL for the PDF was found in this session. The repo already cites it (phase landed masses, LTV 10 km/h design target). Not re-verified here.

---

## 2. Surface communications

### Takeaway

**LunaNet does not standardise the radio link between surface vehicles.**

- The LunaNet Interoperability Specification v5 (29 January 2025) lists:
  - "IP over Wi-Fi" and "IP over 3GPP" on lunar surface wireless as **not part of LunaNet 1.0**;
  - the 3GPP lunar bands as still "under investigation".
- Interoperability across vehicles is defined only at the network layer: IPv4/IPv6 and DTN Bundle Protocol v7. Physical links are bilateral.
- This is exactly the gap a "Lunar ATC" layer would fill.

**Practical surface radios in the period:**

- 2.4 GHz 802.11n WLAN (Griffin, Peregrine): about 300 m range in NASA's relay concept.
- 4G/LTE (Nokia on IM-2):
  - targets of a few hundred metres to 2-5 km, with antennas 3-5 m high;
  - powered for about 25 minutes on the tipped-over Athena;
  - sent telemetry, but the first call never happened.
- A 10 m-mast LTE/5G "Lunar Surface Relay": about 10 km coverage, terrain permitting.

**Range is set by geometry, not by radio power.**

- Smooth-Moon horizon for a 1-3 m antenna is 1.9-3.2 km.
- Between two such antennas it is 3.7-6.5 km.
- Real south-pole terrain cuts coverage further: a 4 m tower saw only 10.6-23.7% of a 20 × 20 km Malapert region.
- Outages are therefore terrain-driven and binary-like. DTN store-and-forward (BPv7) is the mandated way to carry data across them.

### 2.1 LunaNet Interoperability Specification v5 (LNIS v5)

Source: [NASA PDF, LNIS V005, 29 January 2025](https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-interoperability-specification-v5-baseline.pdf). **High** for all quotes below.

**Interfaces.** LunaNet 1.0 standardises:

- proximity links (orbiting provider to user);
- direct-with-Earth (DWE) links;
- contingency links;
- terrestrial interfaces.

"Lunar surface interfaces are interfaces between an LNSP lunar surface node and a user surface node". Table 3, however, marks "IP over Wi-Fi" and "IP over 3GPP" (lunar surface wireless) as **LunaNet 1.0: No**.

**Network layer (§4.5).** LunaNet providers may route IPv4, IPv6 or BPv7 bundles from "surface users connected via UHF, Wi-Fi, or 3GPP links" and wired Ethernet. Sub-IP details "are out of scope of LNIS and must be bilaterally defined."

**DTN (§3.1.2).** "The Bundle Protocol version 7 (BPv7) shall be used."

- Over space links, bundles ride in CCSDS Encapsulation Packets over AOS/USLP, or over LTP for long-haul or periodically disrupted links.
- Over IP networks, including lunar surface networks, they ride over the TCP or UDP convergence layers.
- Routing is initially "based on pre-scheduled links" (contact plans).

**Spectrum.**

- S-band is restricted to lunar proximity links:
  - forward 2025-2110 MHz;
  - return 2200-2290 MHz.
- X-band is used direct with Earth:
  - 7190-7235 MHz up;
  - 8450-8500 MHz down.
- K-band proximity:
  - forward 23.15-23.55 GHz;
  - return 27.0-27.5 GHz.
- Lunar 3GPP bands are "under investigation" (not yet ITU-approved).
- A June 2024 ICG draft also lists a 390-405 MHz lunar-orbit-to-surface UHF band and 406-406.1 MHz for search and rescue ([UNOOSA ICG slides](https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_02_01.pdf)). **Medium**: draft.

**S-band proximity rates (Table 7).**

- BPSK: 2 ksps to 2.048 Msps.
- PCM/PM with ranging: 48 ksps to 1.024 Msps.
- Low rate: 0.5-48 ksps.
- High rate (OQPSK or GMSK): 1-5 Msps.
- K-band: from 1 Msps up to "TBD".

**PNT (§3.2).** The Lunar Augmented Navigation Service (LANS) broadcasts the Augmented Forward Signal (AFS):

- CDMA in 2483.5-2500 MHz, Fc = 2492.028 MHz;
- spreading bandwidth 6.16 MHz, about 3 Mcps.

It is time-synchronised to LunaNet Reference Time (LRT), aiming at "a minimum of four simultaneous LANS nodes in view", which is noted as beyond LunaNet 1.0.

### 2.2 NASA Lunar Surface Relay (LSR) concept: 3GPP, Wi-Fi, mast height, terrain viewsheds

Source: [Scardelletti et al., ICSSC 2023, NTRS 20230013361](https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf). **High** for everything in this subsection.

**Coverage and links.**

- 10 m deployable boom carrying the 3GPP sector antennas: "coverage out to 10 km, depending on local terrain effects".
- Wi-Fi: "range of approximately 300 m", at 2.4 or 5 GHz. 802.11n has ISS heritage.
- Legacy UHF Space-to-Space Communication System is also supported.
- Trunk links to Gateway and LCRNS use S-band (voice, TT&C) and Ka-band (high-rate data and video). Direct to Earth uses X and Ka.
- Earth is not visible from the south pole "nominally for 14 days every month".

**PNT and mobility.**

- Two rubidium clocks, running continuously, provide lunar timing to surface elements. Two retroreflectors.
- Mobile LSR on a scaled VIPER chassis: 0.8 km/h nominal, 100 km per lunar day, more than 1,000 km over life, 20° slopes.

**Power.**

- The RTG-powered stationary version needs 131 W for communications.
- It runs 118 h over one lunar day and 177 h over one lunar night.

**Terrain viewshed study (Malapert Massif, 20 × 20 km, receivers 2 m above the surface).**

| Case | Location | 20 m tower | 4 m tower |
|---|---|---|---|
| Best unconstrained site | 8.3 km from the habitat, no line of sight to it | 29.2% of the area | 23.7% |
| Best site with line of sight to the habitat and slope <20° | 9.5 km from the habitat | 12.1% | 10.6% |

- Only 7 of 400 candidate tower sites met both constraints.
- "Movement of a tower ~1 km could have severe impacts to tower LOS coverage."
- Taller towers gave only modest gains for this terrain.

### 2.3 Nokia 4G/LTE on IM-2 (2025)

**Design.** **Medium**: Nokia press as summarised, primary page returned HTTP 403.

- LTE base station with integrated core (EPC) on the Nova-C lander.
- User equipment on Lunar Outpost MAPP and on the Micro-Nova hopper.
- Supports HD video, command and control, and telemetry.
- Planned to run up to 12 days in daylight.
- Range targets:
  - "very close proximity … up to a couple of hundred meters" and "two to three kilometres" (Nokia newsroom);
  - "300 to 400 meters" and "up to 5 kilometers" (Fierce Network).
- Antennas "3 to 5 meters off the ground", which Nokia says "has a major impact on range".

Sources: [Nokia, 7 January 2025](https://www.nokia.com/about-us/news/releases/2025/01/07/nokias-cellular-network-ready-for-moon-as-intuitive-machines-completes-final-lunar-lander-installation/), [Nokia "aims for the Moon"](https://nokia.com/about-us/newsroom/articles/nokia-aims-for-the-moon-with-lte4g), [Fierce](https://fierce-network.com/tech/how-nokia-plans-to-establish-a-4g-network-moon).

**Result.** **High** for the outcome, **Medium** on the cause.

- Athena landed on its side on 6 March 2025.
- The Nokia system "briefly operated within a narrow 25-minute power window", activated and sent telemetry to Earth.
- The planned first cellular call "could not be established". Reported causes: "severe temperature drops" in the hopper ([Converge Digest, 11 March 2025](https://convergedigest.com/despite-tipped-lander-nokia-validates-cellular-tech-on-moon/)) or no power to recharge ([Fierce](https://www.fierce-network.com/wireless/nokias-not-getting-hung-missed-lunar-phone-call)).
- No measured lunar LTE range or data rate exists yet.

### 2.4 Other proximity links in service or planned

**Griffin and Peregrine lander WLAN.**

- "a 2.4 GHz IEEE 802.11n compliant WLAN modem enables wireless communication between the lander and deployed payloads on the lunar surface".
- Wired links: RS-422 or SpaceWire.
- Lander to Earth: X-band; low-gain antennas in cruise, an actuated medium or high gain antenna after touchdown.

Source: [Astrobotic Lunar Landers Payload User's Guide 2021](https://science.nasa.gov/wp-content/uploads/2023/11/astrobotic-lunar-landers-pug.pdf). **High**.

**Blue Ghost.** One X-band and three S-band antennas ([Wikipedia](https://en.wikipedia.org/wiki/Firefly_Aerospace_Blue_Ghost)). **Medium**.

**CADRE.** Mesh radios plus UWB ranging between rovers and the base station on the lander ([JPL](https://robotics.jpl.nasa.gov/gallery/cadre-telecom-board-prototype-testing/)). **High**. Band, rate and range are not public.

**ESA/SSTL Lunar Pathfinder (relay).** **Medium**.

- One S-band and one UHF channel to lunar assets, used simultaneously.
- Moon link "2 × 2.7 Mbps S-band"; Earth link 5 Mbps X-band ([SSTL, 2024](https://bsgn.esa.int/wp-content/uploads/2024/12/Ben-Hooper_-Lunar-Comm-Nav-Session.pdf)). A 2022 slide said 8 Mbps S-band and 4 Mbps UHF.
- Elliptical lunar frozen orbit (ELFO), 8-year life.

**LCRNS (NASA commercial relay; Intuitive Machines first provider).**

- Up to $4.82 B over 5 + 5 years.
- First satellite tied to IM-3 per trade press (**Medium**).
- Coverage figures at the south pole are already in the repo note `research_notes/Lunar communications and visibility/earth_visibility_prior_art.md`: DTE alone 17-43% a year, one relay 80-86%, DTE plus two relays 100% ([Esper et al., SpaceOps 2025](https://ntrs.nasa.gov/api/citations/20250003321/downloads/LCRNS_Esper_257.pdf)). **High**.

**VIPER.** X-band direct to Earth, no relay. High-gain antenna on the mast at 2.3 m height. Transmit up to 8 Msps (NASA 2024). **High**.

### 2.5 Line-of-sight range over lunar terrain (numbers for a radio model)

**Smooth-sphere horizon (Computed).**

- Formula: d = √(2·R·h), with R = 1,737.4 km.
- The Moon has no atmosphere, so there is no refraction: use k = 1, not Earth's 4/3.
- Mutual range between antennas at heights h₁ and h₂ is d₁ + d₂.

| Antenna height h | Horizon (one antenna) | Mutual range (both at h) |
|---|---|---|
| 0.5 m | 1.32 km | 2.64 km |
| 1.0 m | 1.86 km | 3.73 km |
| 1.5 m | 2.28 km | 4.57 km |
| 2.0 m | 2.64 km | 5.27 km |
| 2.5 m | 2.95 km | 5.89 km |
| 3.0 m | 3.23 km | 6.46 km |
| 5.0 m | 4.17 km | 8.34 km |
| 10 m | 5.89 km | 11.8 km |

- Rover at 2 m to a 10 m mast: 8.5 km.
- Rover at 2.5 m to a 20 m mast: 11.3 km.
- The 10 m / 10 km pair in the repo (`comms.py` mast) agrees with this geometry and with the LSR paper.

The horizon formula is standard ([NASA Space Math](https://spacemath.gsfc.nasa.gov/Geometry/3Page19.pdf)). A smooth-sphere treatment of lunar ground-wave loss is in [NBS Monograph 85](https://nvlpubs.nist.gov/nistpubs/Legacy/MONO/nbsmonograph85.pdf). **High**.

**Real terrain at the south pole is the dominant limit.**

- The LSR viewsheds in 2.2 show 10-30% area coverage from a single 4-20 m tower.
- Hwu, Upanavage & Sham (NASA JSC, 2008) conclude "path loss can be much more severe than the free space propagation" and depends on antenna height, frequency and surface material ([NTRS 20080015374](https://ntrs.nasa.gov/citations/20080015374)). That work used 2 m and 6 m two-ray cases ([Glasgow re-analysis](https://eprints.gla.ac.uk/323348/1/323348.pdf)).
- Regolith permittivity at the south pole is unmeasured ([NASA GRC](https://ntrs.nasa.gov/api/citations/20230013296/downloads/20230013296.pdf)). **High** as stated limitations.

**Fresnel clearance and ground reflection (Computed).** Rover antennas of 1-3 m cannot clear the first Fresnel zone at km ranges, so links sit near grazing even when in line of sight.

First Fresnel radius at mid-path, r₁ = √(λ·d/4):

| Frequency | d = 1 km | d = 3 km |
|---|---|---|
| 0.4 GHz | 13.7 m | 23.7 m |
| 0.9 GHz | 9.1 m | 15.8 m |
| 2.4 GHz | 5.6 m | 9.7 m |
| 5.8 GHz | 3.6 m | 6.2 m |
| 26 GHz | 1.7 m | 2.9 m |

Two-ray breakpoint distance, 4·h₁·h₂/λ:

| Frequency | h = 1 m | h = 2 m | h = 3 m |
|---|---|---|---|
| 0.4 GHz | 5 m | 21 m | 48 m |
| 2.4 GHz | 32 m | 128 m | 288 m |
| 5.8 GHz | 77 m | 310 m | 696 m |

Beyond the breakpoint, flat-ground path loss grows about 40·log₁₀(d) instead of 20·log₁₀(d).

**Free-space loss (Computed).**

| Frequency | 1 km | 10 km |
|---|---|---|
| 0.4 GHz | 84.5 dB | 104.5 dB |
| 2.4 GHz | 100.1 dB | 120.1 dB |
| 5.8 GHz | 107.7 dB | 127.7 dB |
| 26 GHz | 120.7 dB | 140.7 dB |

**Diffraction model for a simulator** (standard practice; [ITU-R P.526](https://www.itu.int/rec/R-REC-P.526/en)).

- Compute line of sight on the DEM between antenna tips.
- If blocked, compute single knife-edge loss J(v) with Fresnel parameter v = h·√(2(d₁+d₂)/(λ·d₁·d₂)):
  - about 6 dB at grazing (v = 0);
  - about 13.9 dB at v = 1;
  - about 20.5 dB at v = 2.4.
- Declare the link down when margin is negative.
- At UHF (0.4 GHz) diffraction over low ridges is much kinder than at 2.4-5.8 GHz. That is the main physical argument for a UHF fallback channel.

**High** for the method; the numbers above are Computed.

### 2.6 Latency, outage behaviour, DTN

**Earth link.** Earth-Moon light time is about 1.28 s one way. The repo uses 2.6 s round trip plus 2.4 s processing (`parameters.csv`; NTRS 20250000703). **High**.

**Surface link latency.** Milliseconds per hop for Wi-Fi and LTE. **Assumed** (terrestrial practice; no lunar measurement).

**Outage pattern.** Surface outages are terrain occlusion: binary, position-dependent, and changing in steps over about 1 km of travel (LSR paper). Long DTE outages follow Earth's elevation, about 14 days a month at the pole (LSR paper).

**DTN status.**

- BPv7 is mandatory for LunaNet DTN (LNIS v5).
- NASA's DTN Project completed in January 2026. DTN is now "an operational service in both NASA's Near Space Network and the Deep Space Network" ([NASA DTN page](https://www.nasa.gov/communicating-with-missions/delay-disruption-tolerant-networking/)). **High**.
- DTN has flown at lunar distance on Korea's Danuri/KPLO ETRI payload ([IAC-23](https://iafastro.directory/iac/archive/browse/IAC-23/B2/8-GTS.3/79093/)). **Medium**.
- No lunar-surface DTN demonstration was found as of October 2026.

### 2.7 Time synchronisation and PNT

**Policy.** On 2 April 2024 the White House OSTP directed NASA to deliver a plan for Coordinated Lunar Time (LTC) by end of 2026 ([Reuters via The Weather Network](https://www.theweathernetwork.com/en/news/science/space/nasa-to-create-time-standard-for-the-moon)). **High** on the directive. Whether the plan has been delivered was not checked.

**Clock rate.** A clock on the Moon gains about 56.02 µs a day relative to Earth (Ashby & Patla, Astronomical Journal 168:3, 2024, [APS summary](https://physics.aps.org/articles/v17/140)). Kopeikin & Kaplan agree on the average and add periodic terms. **High**.

**Implementation.**

- LunaNet provider time (LST) is steered to LunaNet Reference Time (LRT).
- LANS AFS at 2492.028 MHz (LNIS v5) provides it.
- The surface relay carries two rubidium clocks (LSR paper).

**Sim implication.** Vehicles of different companies should share one time base (LRT/LTC). Model clock drift only if the vehicle lacks relay or AFS access. A free-running TCXO drifts about 1 ppm, roughly 86 ms a day (**Assumed**). That is large enough to matter for cooperative manoeuvres.

---

## 3. Vehicle internals for 3D cutaways

### Takeaway

Honest cutaways are possible for four reference vehicles whose layouts are published:

- **VIPER** (rover): NASA 2024 slide set.
- **Apollo LRV** (unpressurised rover): NSSDC.
- **Griffin** (lander): Astrobotic 2021 payload user's guide.
- **Starship** (tank order): public descriptions.

The rest need a "schematic, not to engineering scale" label:

- the LTVs: Astrolab gives only the payload-interface layout;
- Blue Moon MK1: only the outer envelope is public;
- the hoppers: envelope and sensor list only.

Propellant tank sizes below are Computed from published propellant masses and densities so that the volumes are physically honest even when positions are schematic.

Densities used: LOX 1,141 kg/m³; LH2 70.8 kg/m³; liquid CH4 422 kg/m³; MON-3/MMH-class storables about 1,400 / 880 kg/m³.

### 3.1 Landers

**Griffin (2021 payload user's guide; GM1 updates).** Source: [Astrobotic PUG 2021](https://science.nasa.gov/wp-content/uploads/2023/11/astrobotic-lunar-landers-pug.pdf). **High** for the 2021 design.

- **Structure.** Aluminium bus of three parts:
  - launch-vehicle adapter cone;
  - solid deck panels;
  - four radiator panels "for directly mounting payloads or avionics".
- **Avionics.** "Lander avionics are mounted on the underside of radiators that form the decks of the lander." There are also side radiators.
- **Propulsion.**
  - Five 700 lbf (3.1 kN) pulsed main engines "located within the cone".
  - Twelve 25 lbf (111 N) attitude-control engines in clusters of three.
  - Pressure-fed MMH-derivative (M20) and MON-3.
  - "Two tanks each of the fuel and oxidizer are spaced evenly about the craft."
- **Power.** Side-mounted solar panels for polar sites; Li-ion battery.
- **Legs.** Four.
- **Payload decks.** About 0.5 m² of mounting area per side. M5 inserts on a 75 mm grid. Payloads can mount above deck (sky view) or below deck (close to the surface). Optional egress ramps for rovers.
- **GM1 update.** The current flight design uses seven main engines and four COPV propellant tanks ([Astrobotic Griffin page](https://www.astrobotic.com/lunar-delivery/landers/griffin-lander/); [GM1 update](https://www.astrobotic.com/griffin-1-mission-update/)). **High**. Use 4 tanks around the central engine cone. The engine count differs by version.
- **Overall dimensions.** Not found in the sources reached. Size the envelope from the deck and adapter cone, and label it schematic.

**Nova-C** ([Wikipedia](https://en.wikipedia.org/wiki/Intuitive_Machines_Nova-C); Design News summary). **Medium**.

- Hexagonal body. "Six spines for the core structure that are attached to the top deck and the engine deck at the bottom". All six faces open for plumbing and harness access.
- Six legs.
- One gimballed VR900 engine at the bottom centre.
- Composite, linerless cryogenic tanks:
  - 845 kg LOX → 0.74 m³ (a sphere about 1.12 m in diameter, Computed);
  - 422 kg CH4 → 1.0 m³ (a sphere about 1.24 m, Computed).
- 17 kg helium in a separate COPV (position not published).
- Solar: one top-deck panel plus two body panels.
- Height 3.94-4.3 m, width about 1.57-2 m.
- Tank positions inside the hexagon are **not published**. Show the two tanks side by side above the engine deck, labelled schematic (**Low**).

**Blue Ghost** ([NSF](https://www.nasaspaceflight.com/2025/01/blue-ghost-hakuto-r-launch/), Firefly). **High/Medium**.

- Box-shaped composite body with 49 struts, 2 m tall × 3.5 m wide.
- Three decks:
  - top deck with sky view;
  - middle deck with rover mounts;
  - bottom deck with surface access.
- Four composite legs with honeycomb crush cores.
- Main engine: LEROS 4-ET, >1,000 N, MON/hydrazine.
- Eight Spectre RCS thrusters and twelve cold-gas thrusters.
- About 400 W of solar from three panels.
- One X-band and three S-band antennas.
- Tank count and positions not published (**Low** if drawn).

**Blue Moon MK1** (Gunter's Space Page; Blue Origin). Envelope **High**; internals **Low**.

- Roughly cylindrical, 8.05 m tall, 3.08 m outer diameter.
- One BE-7 at the bottom.
- Payload on the top deck (3 t), unpressurised.
- A 2019 Space.com description mentions a davit crane to lower payloads ([Space.com](https://www.space.com/blue-origin-blue-moon-lander-explained.html)). **Medium**: old design.
- No tank layout is published.

Computed sizing with the repo's assumption (about 5 t dry plus 3 t payload, so about 13.4 t propellant at launch; mixture ratio 5.5):

- LH2 about 2.05 t → 29 m³, about 4.4 m of a 2.9 m inner-diameter cylinder;
- LOX about 11.3 t → 9.9 m³, about 1.5 m of the same cylinder.

LH2 dominates the volume. Show a tall LH2 tank and a short LOX tank stacked or nested, label "schematic", confidence **Low**.

**Starship HLS** (Wikipedia, Starship spacecraft and HLS pages). **Medium**.

From bottom to top:

- engine bay with Raptors in a shielded compartment;
- **LOX tank (aft)**;
- common dome;
- **CH4 tank (forward)**;
- payload / crew section;
- header tanks in the nose: LOX header at the tip, CH4 header just below.

Tank sizes:

- Propellant 1,500 t: 1,170 t LOX → about 1,025 m³ (about 16 m of 9 m-diameter barrel, Computed); 330 t CH4 → about 780 m³ (about 12 m, Computed).
- HLS: crew cabin and airlock near the top; elevator down the outside of the hull; landing thrusters in the mid-body; a band of solar panels around the hull.
- Height 52 m, diameter 9 m.
- The cargo variant's internal bay layout is not published.

**ESA Argonaut** (ESA). **Medium**.

Three elements:

- Lunar Descent Element (the lander);
- Cargo Platform Element;
- payload.

About 4.5 m diameter, about 6 m long (Wikipedia). Internals are not published.

### 3.2 Unpressurised rover / LTV

**VIPER: the best-published internal layout of a modern lunar rover.** Source: [NASA, Bluethmann, November 2024](https://ntrs.nasa.gov/api/citations/20240013903/downloads/LSIC_2024-Tech%20Infusion_Panel-VIPER_Mob-HW.pdf). **High**.

- Envelope 1.7 × 1.7 × 2.5 m. Four wheel modules.
- **Mast:**
  - high-gain antenna on a pan-tilt at **2.3 m** height (pan 400°, tilt +25/-29°);
  - navigation cameras and lights on a pan-tilt at **2.0 m**;
  - low-gain antenna.
- **Power:**
  - solar arrays on three sides;
  - "2x Batteries (internal)", 5,420 Wh in total.
- **Thermal:** "Radiators (on top)", with loop heat pipes as transport.
- **Avionics:** flight avionics, IMU and motor controllers in a "warm box". Each motor-controller box drives 6 brushless DC actuators, which serve two wheel modules.
- **Navigation:** star tracker, 4 hazard cameras, 6 hazard lights, aft stereo pair.
- **Wheels:** 50 cm diameter with 2.5 cm grousers. Steering ±50°. Active suspension gives 7-43 cm ground clearance.
- **Payload:** 1 m TRIDENT drill.

**Apollo LRV: published dimensions of a crewed, unpressurised rover.** Source: [NSSDC](https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html). **High**.

- 210 kg vehicle, 490 kg payload.
- 3.1 m long, 2.3 m wheelbase, 1.14 m tall, 36 cm clearance.
- Wheels 81.8 cm × 23 cm.
- Each wheel has its own 0.25 hp DC motor with an 80:1 harmonic drive (hub motors). Front and rear steering motors.
- Two 36 V, 121 Ah silver-zinc batteries.
- Mesh dish antenna on a mast at the front centre.
- T-handle controller between the two seats.
- Three-part folding chassis.
- Battery and electronics placement in the forward chassis, behind dust covers and radiators, is from the LRV Operations Handbook. It was not re-read here. **Medium**.

**Phase 1 LTVs (CLV-1, Pegasus) and FLEX: what is public.** **High** as company or NASA statements.

- **FLEX / CLV-1:**
  - two top-deck payload interfaces;
  - an underslung payload bay between the wheels (3 m³);
  - six-degree-of-freedom arm;
  - gimbaling antenna.
- **FLIP** shares tires, batteries, radios and cameras with CLV-1.
- **Pegasus:**
  - two seats, two solar arrays, spring-mesh tires, no arm;
  - one report says four in-wheel motors (**Medium**);
  - GM batteries with heaters and insulation (**Medium**).

**Schematic recipe for an LTV cutaway** (VIPER plus LRV pattern applied to an LTV envelope). **Low**: schematic.

- Battery pack and avionics in an insulated warm box low in the centre chassis, to keep the centre of gravity low and for thermal reasons.
- Radiators on top of the warm box, facing the sky.
- In-hub motors and steering actuators at each wheel.
- Mast at the front or a corner, with cameras at about 2 m and the high-gain antenna at about 2.3 m.
- Solar on the vertical sides (polar sun is low).
- Payload deck at the rear (crewed LTV) or full top deck plus underslung bay (FLEX).
- Arm on a deck corner.

### 3.3 Hopper drone

**Published facts.**

- MoonFall: about 2.1 m wide × 1.2 m tall, about 250 kg wet, 10 cameras (**Medium**).
- Micro-Nova: about 1 m tall, 8-10 kg payload, IMU, star tracker, navigation camera, lidar and situational-awareness camera, rail-deployed from the lander (**High**).

**Not published:** tank count, engine count and propellant for either. Micro-Nova is reported as hydrazine by Wikipedia only (**Low**).

**Schematic recipe.** **Low**: label "schematic, not to engineering scale".

- Low, wide body with a central propellant tank or tanks and a small COPV pressurant tank.
- Downward thrusters under the centre of mass.
- Four short legs.
- Sun-facing solar panel and avionics on the top deck.
- Cameras and lidar on the lower rim, looking down and forward.

### 3.4 Rocket upper stage

**Centaur V** ([Wikipedia](https://en.wikipedia.org/wiki/Centaur_(rocket_stage)), ULA). **High** for dimensions and propellant.

- 5.4 m diameter; 12.6 m tall (CV-HE) or 10.66 m (CV-L).
- 54,000 kg or 39,000 kg of LH2/LOX.
- Two RL10 engines, each about 2.46 × 1.57 m (RL10C-1-1).
- Stainless-steel pressure-stabilised "balloon" tanks, 0.51 mm walls.
- A common bulkhead (two steel skins around a fibreglass honeycomb core) separates LOX and LH2.

LH2 forward / LOX aft is the standard Centaur arrangement shown in ULA cutaways. Not re-verified in this session: **Medium**.

Computed tank volumes for CV-HE (mixture ratio about 5.9):

- LH2 about 7.9 t → about 111 m³, about 4.9 m of barrel;
- LOX about 46 t → about 40 m³, about 1.8 m.

Avionics sit on the forward adapter (**Medium**).

**Alternative reference: Starship's ship** (3.1), for a methalox upper stage.

---

## 4. Cooperative lifting and transport by two rovers

### Takeaway

NASA names multi-robot cooperation as a likely enabling feature and a reason to standardise robot interfaces.

**What does not exist:** a NASA or LTV-provider design for two LTVs carrying one load.

**Closest real work:**

- JPL Tri-ATHLETE: two half-vehicles docking to one cargo pallet.
- Canadian Space Agency-context Lunar Utility Vehicle (LUV) work: two 800 kg rovers carrying a shared 475 kg load under distributed model-predictive control (MPC), with 9.2 cm mean separation error.
- ESA TRAILER: a two-rover tandem.

**Crane capacities on record:**

- NASA LSMS family: 35 kg to 1,000 kg in lunar gravity; a 2010 heavy-lift study at 12 t.
- FLEX: 6-DOF arm.
- Eagle: arm.
- Blue Moon: davit crane, as a 2019 concept.

### Findings

**NASA ACR24 "Lunar Mobility Drivers and Needs".** Source: [PDF](https://www.nasa.gov/wp-content/uploads/2024/06/acr24-lunar-mobility-drivers-and-needs.pdf). **High**.

- "The ability of multiple robotic mobility systems to work together may also be an enabling feature for future systems. This type of behavior would be additional motivation for standardization among robotic interfaces."
- Demand is 500-15,000 kg elements over distances up to 5,000 m.
- "Current demand and mobility capacity are mismatched on the order of 1,000 to 15,000 kg per asset for ranges of 50 to 5,000 m."
- "Wheel and soil interactions for large mobility systems do not scale linearly." This argues for several smaller vehicles over one giant vehicle.

**Krawciw et al., "Sharing the Load: Autonomous Multi-Rover Cargo Transport"** ([arXiv 2510.18766](https://arxiv.org/abs/2510.18766), v2 May 2026; Toronto with industry co-authors). **High** as a paper.

- Two 800 kg "path-to-flight" Lunar Utility Vehicles share 475 kg of cargo.
- A custom coupling decouples each vehicle's kinematics while carrying the full load.
- Control is distributed MPC on top of each rover's lidar teach-and-repeat.
- Field test: 9.2 cm mean and 33.4 cm maximum relative separation error.
- Motivating case: cargo moved up to 5 km from landing site to habitat.
- **The inter-rover link is not described in the abstract.** This is the "Lunar ATC" opening: the cooperative controller needs a low-latency vehicle-to-vehicle link.

**JPL ATHLETE / Tri-ATHLETE** ([JPL](https://robotics.jpl.nasa.gov/how-we-do-it/systems/the-athlete-rover/); [Heverly 2010](https://www-robotics.jpl.nasa.gov/media/documents/Heverly_2010_AMS_Tri-ATHLETE.pdf)). **High**.

- "Two Tri-ATHLETEs dock to opposite sides of a cargo pallet to form a six-limbed symmetrical vehicle, work together to move and emplace the cargo, then undock and depart."
- Generation 1: about 850 kg, 300 kg payload in Earth gravity, 2.75 m wide.
- Generation 2: 450 kg payload in Earth gravity, just over 4 m tall.

**ESA TRAILER.** Tested "a novel architecture of robotic cooperation based on a tandem of two rovers" ([ESA](https://www.esa.int/Enabling_Support/Space_Engineering_Technology/Shaping_the_Future/Twin_rovers_could_lead_search_for_life_supporting_elements)). **Medium**: no numbers reached.

**NASA LSMS cranes** ([NTRS 20240001448](https://ntrs.nasa.gov/citations/20240001448)). **High**.

- The family runs from LSMS-L35 (35 kg lift in lunar gravity) to LSMS-1000 (1,000 kg lift in lunar gravity).
- Tension-stiffened, cable-actuated hybrid crane/manipulator.
- A 2010 NASA study sized a heavy-lift LSMS for a 12 t payload ([NTRS 20100033143](https://ntrs.nasa.gov/citations/20100033143)). **Medium**.
- No reach figure was found.

**On-vehicle arms and cranes.**

- FLEX: 6-DOF arm; picks up and aligns payloads semi-autonomously (**High**).
- Eagle: arm that swaps its own tools (**Medium**).
- Pegasus: no arm (**Medium**).
- Blue Moon: davit crane, 2019 concept (**Medium**).
- Starship HLS: crew and cargo elevator (**High**).

No lift ratings were published for the FLEX or Eagle arms.

### What this means for the simulation

The repo marks `can_team_lift = True` for LTV and HAUL. The best real numbers for a team-lift model are:

- two vehicles carry about 0.3 of their combined mass (475 kg on 2 × 800 kg);
- formation error about 0.1 m mean, 0.35 m maximum;
- formation speed = the slower vehicle's loaded speed.

The cooperative-lift time-sync requirement is **Assumed**: under 10 ms between the two controllers, and a vehicle-to-vehicle link of at least 10 Hz state exchange. No source gives it.

---

## Table A. Simulation parameters (value, range, source)

| Parameter | Value for sim | Range / notes | Source | Conf. |
|---|---|---|---|---|
| Phase 1 LTV payload (samples + tools) | 80 kg | crewed-sortie load; not cargo | NASA 20 Oct 2026 | High |
| Phase 1 LTV range per charge | 10 km | **DIFF**: repo implies 114 km (40 kWh / 350 Wh/km) | NASA 20 Oct 2026 | High |
| Phase 1 LTV uncrewed daily traverse | 6 km/day | remote operation | NASA 20 Oct 2026 | High |
| CLV-1 mass; top speed | ~907 kg; >9.7 km/h | "about 2,000 lb"; ">6 mph" | NASA 26 May 2026 | High |
| Pegasus top speed; life | >14.5 km/h; up to 1 yr | ">9 mph"; no arm | NASA 26 May 2026; Payload Space | High / Med |
| Original LTV requirement | 800 kg; 20 km per 8 h; 1,287 km/yr | for a cargo-capable LTV | ACR24 Mobility; LTV RFP via press | High / Med |
| Cargo LTV (FLEX-class) capacity | 1,500-2,000 kg | **DIFF**: repo 1,500; company page now 2,000 kg on two top decks plus 3 m³ underslung | astrolab.space | High (claim) |
| Moon RACER (reference) | 1.5 t vehicle; 15 km/h; ~1,800 kg with trailer | not selected | Intuitive Machines | Med |
| VIPER | 447 kg roving; 0.1-0.2 m/s; 5.42 kWh; 15° slope | 2027 on MK1 | NASA Nov 2024; Oct 2026 | High |
| HL-MAPP (small cargo rover) | 250 kg; 200 kg payload; 3 m/s | repo MICRO 300 kg / 3 km/h is conservative | lunaroutpost.com | High (claim) |
| MoonFall hopper | 4 units; ~250 kg wet; ~50 km per drone; 14 days of hops | 2028; then months as fixed payloads | NASA May 2026; press | High / Med |
| Micro-Nova hopper | 8-10 kg payload; >25 km total; ~1 m tall | 1 kg on IM-2 manifest | LPSC 2024; IM page | High |
| Griffin GM1 payload | 455 kg | 625 kg (2021 design) | NASA 13 Oct 2026; Astrobotic | High |
| Blue Ghost payload; surface life | 150 kg; ~14 d + 5 h night | 119 GB returned | Firefly; NASA | High |
| Blue Moon MK1 payload; size | 3,000 kg; 8.05 m × 3.08 m | cargo variant 3.6 t; BE-7 ~40-44.5 kN | Gunter; Blue Origin | High / Med |
| Argonaut payload | 1,500 kg | first flight 2030-2031 | ESA | High |
| Large cargo lander | 12-15 t occasional | repo 12-30 t; Starship claim 100 t | ACR24 Cargo; Wikipedia | High / Med |
| Horizon distance (one antenna) | √(2Rh), R = 1,737.4 km | 1.86 km at 1 m; 2.64 km at 2 m; 3.23 km at 3 m; 5.89 km at 10 m | geometry | Computed |
| Mutual line-of-sight range, rover to rover (both 2 m) | 5.3 km (smooth) | 3.7 km at 1 m; 6.5 km at 3 m; real terrain much less | geometry | Computed |
| Rover (2 m) to 10 m mast | 8.5 km (smooth) | repo mast 10 m / 10 km consistent | geometry; LSR paper | Computed / High |
| 3GPP (LTE/5G) cell from a 10 m mast | 10 km | "depending on local terrain" | Scardelletti 2023 | High |
| LTE on a 3-5 m antenna | 0.3-5 km | targets only; never measured on the Moon | Nokia; Fierce | Med |
| Wi-Fi 802.11n (2.4/5 GHz) range | 300 m | Griffin lander WLAN is 2.4 GHz 802.11n | Scardelletti 2023; Astrobotic | High |
| Single-tower area coverage, 20 × 20 km | 10.6-23.7% (4 m); 12.1-29.2% (20 m) | moving a tower ~1 km changes it severely | Scardelletti 2023 | High |
| Knife-edge diffraction loss | 6.0 dB at v = 0; 13.9 dB at v = 1; 20.5 dB at v = 2.4 | apply on DEM line-of-sight blockage | ITU-R P.526 | High (method) |
| Low-antenna ground-reflection breakpoint | 128 m at 2.4 GHz, h = 2 m; 21 m at 0.4 GHz | beyond it, loss grows ~40 log d | two-ray model | Computed |
| S-band proximity (LunaNet) symbol rate | 1-5 Msps high rate; 0.5-48 ksps low | 2025-2110 / 2200-2290 MHz | LNIS v5 Table 7 | High |
| Relay Moon link (Lunar Pathfinder) | 2 × 2.7 Mbps S-band | 2022 slide: 8 Mbps S, 4 Mbps UHF | SSTL 2024 | Med |
| VIPER direct-to-Earth X-band | up to 8 Msps transmit; up to 75 ksps receive | 256 kbps nominal (2020) | NASA 2024; 2020 | High / Med |
| DTE availability at the pole | 17-43% a year; 80-86% with one relay; 100% DTE + 2 relays | Earth hidden ~14 days a month | Esper 2025; Scardelletti 2023 | High |
| Earth round trip | 2.6 s light + 2.4 s processing | as in repo | NTRS 20250000703 | High / Med |
| Surface hop latency | ~10 ms | Wi-Fi/LTE typical | terrestrial practice | Assumed |
| CADRE sleep cycle | wake about every 30 min after a cooling shutdown; leader election on wake | not at south pole | JPL (search summary) | Med |
| Lunar clock rate vs Earth | +56.02 µs/day | LTC plan due end of 2026 | Ashby & Patla 2024; OSTP | High |
| Team-lift payload fraction | ~0.3 of combined vehicle mass | 475 kg on 2 × 800 kg | Krawciw et al. 2025/26 | Med (one test) |
| Team formation error | 0.09 m mean; 0.33 m max | distributed MPC | Krawciw et al. | High (paper) |
| Crane capacity (lunar g) | 35-1,000 kg (LSMS family) | 12 t heavy-lift study (2010) | NTRS 20240001448; 20100033143 | High / Med |

## Table B. Cutaway part lists per vehicle (part, position, size, source)

All entries are schematic, not to engineering scale, unless the confidence is High and a size is given.

### Griffin (2021 design)

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Launch-vehicle adapter cone | Centre bottom; main engines inside it | not published | Astrobotic PUG 2021 | High (position) |
| Main engines | Inside the cone, bottom | 5 × 3.1 kN in 2021; 7 in GM1 | PUG 2021; Astrobotic page | High |
| ACS thrusters | 4 clusters of 3 around the bus | 12 × 111 N | PUG 2021 | High |
| Propellant tanks | Spaced evenly around the cone | 2 fuel + 2 oxidiser (MMH-type / MON-3); 4 COPV in GM1 | PUG 2021; GM1 update | High |
| Avionics | Underside of the radiator panels that form the decks | — | PUG 2021 | High |
| Payload decks | Top and below-deck mounting | ~0.5 m² per side; M5 inserts on a 75 mm grid | PUG 2021 | High |
| Solar panels | Side-mounted (polar configuration) | — | PUG 2021 | High |
| Antennas | Low-gain antennas plus actuated medium/high gain; 2.4 GHz WLAN | — | PUG 2021 | High |
| Legs | 4 | — | Astrobotic | High |
| Rover egress ramps | Payload adapter; optional | — | Astrobotic | High |

### Nova-C

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Hexagonal frame | 6 spines from top deck to engine deck | 3.94-4.3 m tall; 1.57-2 m wide | Wikipedia; IM | Med |
| VR900 engine | Bottom centre, gimballed | 3.1 kN | Wikipedia | Med |
| LOX tank | Inside the hexagon, above the engine deck | 0.74 m³ (sphere ~1.12 m) | Computed from 845 kg | Computed / Low (position) |
| CH4 tank | Beside the LOX tank | 1.0 m³ (sphere ~1.24 m) | Computed from 422 kg | Computed / Low (position) |
| Helium COPV | Not published | 17 kg He | Wikipedia | Low (position) |
| Solar | 1 top-deck panel + 2 body panels | 200 W on the surface | Wikipedia | Med |
| Legs | 6 | — | Wikipedia | High |

### Blue Ghost

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Body | Box frame with 3 decks (top sky view; middle rover mounts; bottom surface access) | 2 m tall × 3.5 m wide | NSF; Firefly | High |
| Main engine | Bottom centre | LEROS 4-ET, >1 kN | NSF; Wikipedia | High |
| RCS | Around the body | 8 Spectre + 12 cold-gas | NSF | High |
| Antennas | On the body | 1 X-band + 3 S-band | Wikipedia | Med |
| Legs | 4 composite, honeycomb crush cores | — | NSF | High |

### Blue Moon MK1

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Body | Vertical cylinder | 8.05 m × 3.08 m | Gunter | High |
| Payload deck | Top, unpressurised | 3 t | Blue Origin | High |
| BE-7 engine | Bottom centre | ~40-44.5 kN | Gunter; Blue Origin | High |
| LH2 tank | Main volume of the cylinder | ~29 m³ (≈4.4 m of length) | Computed, assumed 13.4 t propellant | Low |
| LOX tank | Below or nested with LH2 | ~9.9 m³ (≈1.5 m) | Computed | Low |
| Power | Solar cells, batteries, fuel cells | — | Gunter | High (type) |
| Davit crane | Deck edge | — | Space.com 2019 | Low |

### Starship HLS

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Raptor engines | Aft, shielded compartment | 3 sea-level + 3 RVac | Wikipedia | Med |
| LOX tank | Aft | 1,170 t, ~1,025 m³, ~16 m of 9 m barrel | Wikipedia; Computed | Med |
| CH4 tank | Forward of LOX, common dome | 330 t, ~780 m³, ~12 m | Wikipedia; Computed | Med |
| Header tanks | Nose: LOX at the tip, CH4 below | — | Wikipedia | Med |
| Crew cabin and airlock | Near the top | — | NASA (elevator test) | High |
| Landing thrusters | Mid-body ring | — | Wikipedia | Med |
| Solar band | Around the hull | — | Wikipedia | Med |
| Elevator | External track down the hull | — | NASA | High |

### VIPER (rover reference)

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Body | Four-wheel chassis | 1.7 × 1.7 × 2.5 m | NASA 2024 | High |
| High-gain antenna | Mast top, pan-tilt | 2.3 m height | NASA 2024 | High |
| NavCams and NavLights | Mast, pan-tilt | 2.0 m height | NASA 2024 | High |
| Batteries | Internal, 2 units | 5.42 kWh total | NASA 2024 | High |
| Avionics, IMU, motor controllers | Warm box, internal | — | NASA 2024 | High |
| Radiators | Top | — | NASA 2024 | High |
| Solar arrays | 3 sides | 320-450 W | NASA 2024 | High |
| Wheels | 4 modules with steering and active suspension | 50 cm diameter; clearance 7-43 cm | NASA 2024 | High |
| Drill | Body | 1 m TRIDENT | NASA 2024 | High |

### Apollo LRV (rover reference)

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Chassis | 3 folding sections | 3.1 m long; 2.3 m wheelbase; 1.14 m tall | NSSDC | High |
| Hub motors | In each wheel | 0.25 hp, 80:1 harmonic drive | NSSDC | High |
| Wheels | 4 | 81.8 × 23 cm | NSSDC | High |
| Batteries | Forward chassis | 2 × 36 V, 121 Ah (~8.7 kWh) | NSSDC; LRV handbook | High (size) / Med (position) |
| Dish antenna | Mast, front centre | — | NSSDC | High |
| Seats and T-handle | Centre | 2 seats | NSSDC | High |
| Payload area | Aft | 490 kg total payload | NSSDC | High / Med |

### Phase 1 LTV / FLEX (schematic)

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Payload | FLEX: 2 top-deck interfaces plus underslung bay between the wheels | 2,000 kg; 3 m³ underslung | astrolab.space | High (claim) |
| Arm | Deck corner | 6-DOF (FLEX); none on Pegasus | Astrolab; Payload Space | High / Med |
| Battery and avionics | Warm box, low and centre | kWh unpublished; 10 km per charge | NASA; VIPER/LRV pattern | Low |
| Motors | In-hub (4) | — | Pegasus report; LRV | Med |
| Mast: cameras and antenna | Front or corner | ~2-2.3 m (VIPER pattern); gimbaled antenna (FLEX) | Astrolab; NASA | Low / High |
| Solar | Sides (Pegasus: 2 arrays) | — | NASA Oct 2026 caption | High |
| Tires | 4, spring mesh (Pegasus) or flexible airless (FLEX) | — | NASA Oct 2026 | High |
| Seats | 2 | — | NASA | High |

### MoonFall hopper (schematic)

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Envelope | Low, wide | 2.1 m wide × 1.2 m tall; ~250 kg wet | press | Med |
| Propellant tank(s) and COPV | Central | not published | — | Low |
| Thrusters | Underside, at the centre of mass | not published | — | Low |
| Cameras | Rim | 10 cameras | press | Med |
| Legs | 4 (schematic) | — | — | Low |

### Micro-Nova hopper

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Envelope | — | ~1 m tall | LPSC 2024 | High |
| Sensors | Body | IMU, star tracker, navigation camera, lidar, situational-awareness camera | IM | High |
| Payload | Body | 8-10 kg | LPSC; IM | High |
| Deployment | Rail on the lander | — | IM | High |

### Centaur V upper stage

| Part | Position | Size | Source | Conf. |
|---|---|---|---|---|
| Stage | Vertical cylinder | 5.4 m diameter; 12.6 m (CV-HE) or 10.66 m (CV-L) | Wikipedia; ULA | High |
| LH2 tank | Forward | ~111 m³ (~4.9 m) | Computed; ULA cutaway | Med |
| Common bulkhead | Between the tanks | steel skins around a fibreglass honeycomb core | Wikipedia | High |
| LOX tank | Aft | ~40 m³ (~1.8 m) | Computed | Med |
| RL10 engines | Aft | 2 × (2.46 × 1.57 m) | Wikipedia | High |
| Avionics | Forward adapter | — | ULA (not re-checked) | Med |

---

## Gaps and recommended follow-ups

1. **CADRE mesh radio.** Band, data rate and rover-to-rover range are not public. Ask JPL or read the CADRE IEEE Aerospace papers. This would be the only flight-qualified rover-mesh data point.
2. **Phase 1 LTV battery, mass and communications.** These should appear at or after the PDRs (Lunar Outpost October 2026, Astrolab December 2026). Re-check NASA and company pages in early 2027.
3. **Lunar LTE or 5G measured performance.** None exists. IM-2 gave about 25 minutes of telemetry only.
4. **Moon Base Architecture User's Guide (April 2026).** The PDF was not found by search. The repo citation stands but was not re-verified.
5. **Blue Moon MK1 internal layout.** Unpublished. Keep it "schematic", or wait for the Moon Base I mission media kit.
6. **LunaNet surface-to-surface standard.** LNIS v5 leaves it bilateral. Check the forthcoming LNIS applicable documents (AD6, "LunaNet Data Services") and SFCG work on the lunar 3GPP band.
