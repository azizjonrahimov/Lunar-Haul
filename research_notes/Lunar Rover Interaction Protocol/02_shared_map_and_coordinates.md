# Lunar Rover Interaction Protocol, part 2: shared map and coordinate system

Status date: 11 November 2026. Scope: research questions 1 to 5 of section 2 (frame, existing maps, map
merging, who holds the map, synchronisation) and the public-data inventory that supports them.
Positioning and time are in part 1 (`01_positioning_and_time.md`); radio, security and the job market are in
the other parts and are not repeated here.

How to read this note:

- A key in square brackets, for example [NAIF-FK], points to the source list in section G. Every key in that
  list was opened and read in this session (PDFs were downloaded and their text extracted; web pages were
  fetched). Anything not opened is marked UNVERIFIED with what was tried.
- Tags on numbers: MOON = measured at the Moon; EARTH = field or lab test on Earth; SIM = simulation;
  SPEC = a standard or a specification; CALC = our own arithmetic or a computation we ran (shown in section E);
  MEAS = measured by us on this project's own files; ASSUMED = our modelling choice.
- "Existing note" means `research_notes/Lunar landing and rover autonomy logistics/terrain_data_3d_assets.md`.
  File names, sizes and download recipes that are already there are not repeated; this note adds frames,
  accuracy, merging and synchronisation.

---

## A. Summary in plain language

**1. Which coordinate system should describe position on the Moon?**
Use the Mean Earth / Polar Axis system (SPICE name `MOON_ME`, DE421 realisation) with latitude, east
longitude and height above a 1737.4 km sphere: every LOLA, LROC and ShadowCam map is in it, and NASA's 2024
working group endorsed it "as the standard for initial surface operations" [ACR24]. The other system,
Principal Axis (`MOON_PA`), is used for orbits and gravity and is the basis of the new International Lunar
Reference Frame (ILuRF2026) and of the coming LunaNet standard. The same numbers read in the wrong system put
a south-pole base about 660 m from where it is [NAIF-FK, CALC E1], so every coordinate in our protocol
carries a frame name.

**2. What maps already exist?**
The reference terrain model is from the LOLA laser altimeter: 5 m grids for 27 named sites and for everything
south of 87 degrees, with a height error of 0.3 to 0.5 m RMS and position good to about 1 m; but about 90 %
of the 5 m cells are interpolated and the real detail is nearer 20 m [PGDA78, BARKER23]. Cameras add 0.5 m
images (LROC NAC), 1.7 m images inside permanent shadow (ShadowCam), 2 to 5 m stereo models and, since 2025,
5 m shape-from-shading models of the 13 Artemis III regions [PGDA104]. Nothing public resolves the 0.3 to 1 m
rocks and craters that stop a rover: that layer has to be made by the rovers.

**3. How do several rovers merge their local maps into one?**
Each rover keeps a chain of its own poses with a small local map attached to each pose; shared measurements
(the same place seen by two rovers, a radio range between them, the same surveyed marker) tie the chains
together, a least-squares solve puts them in one frame, and the local maps move with their poses. Tested
systems reach about 2 m over 2 km underground with lidar [LAMP2] and 4 to 12 m over 6 to 8 km outdoors with
cameras [KM23], exchange about 12 to 31 kB per keyframe, and must reject 15 to 80 % of candidate cross-rover
matches as wrong [KM22, SWARM, LAMP2]. NASA's CADRE rovers use radio ranges instead of visual matches and
merge traversability grids on an elected leader [MOONDB], but have not flown: IM-3 is now planned for the
first quarter of 2027 at the earliest [IM3-WIKI].

**4. Who holds the "ground truth" map?**
The base should hold one authoritative map of versioned tiles, and every rover should carry a full copy that
it can drive on alone. The surveyed systems that serve one operator merge at one node (a base station, a
server or an elected leader), and none of them has rules for two owners [LAMP2, COVINS, MOONDB]. For a
mixed-company fleet, owners send signed derived products only (hazard cells, traversability, height
corrections with an error estimate), never raw images, and the base checks them against surveyed markers and
a second owner's data before the map changes.

**5. How do you synchronise after a long time out of contact?**
Compare tile versions, not maps: rover and base exchange a short digest (a tree of hashes, about 8 kB for 42
changed tiles out of 3,906) and then the changed tiles in a fixed order, keep-out zones and hazards on the
rover's route first and height refinements last. A day's hazard changes for a 16 km site are about 0.09 MB
(69 s at 10 kbit/s, under 1 s at 1 Mbit/s); height refinements are about 1.4 MB (18 minutes at 10 kbit/s)
and can wait [CALC E4]. The rover's own offline map is first moved back into the shared frame by measuring to
surveyed markers, and only then offered to the base.

**Public data.** Terrain, shadow and illumination products are free at NASA Goddard's PGDA and at the PDS,
images at the LROC and ShadowCam archives, frames at NAIF. The Artemis II archive (released 7 October 2026,
2.6 TB) is from a flyby that came no closer than 6,545 km: it has no rover-scale data, and its 404 OpNav
images show the Moon only 70 to 328 pixels wide, with none taken on the flyby day (B6).

---

## B. Evidence

### B1. Coordinate system

#### The two systems, and a third that SPICE uses by default

| Name (SPICE) | Definition | Used for | Source |
|---|---|---|---|
| Mean Earth / Polar Axis (`MOON_ME`) | z = mean rotation pole; prime meridian = mean Earth direction | all cartographic products; PDS archives | [LROWP08, NAIF-FK] |
| Principal Axis (`MOON_PA`) | axes = principal axes of inertia of the Moon | gravity field, lunar laser ranging, orbit dynamics | [LROWP08, NAIF-FK] |
| `IAU_MOON` | ME computed from a truncated series in the IAU report | SPICE default body frame; kept for backward compatibility | [NAIF-FK] |

Both ME and PA have their origin at the Moon's centre of mass. They differ by a constant small rotation.

| Quantity | Value | Tag | Source |
|---|---|---|---|
| ME to PA rotation, DE421 | P = Rz(67.92") Ry(78.56") Rx(0.30") M | SPEC | [LROWP08] section 6.2; [PGDA95] |
| ME to PA rotation, DE440 (frame `MOON_ME_DE440_ME421`) | angles 67.8526", 78.6944", 0.2785" about axes 3, 2, 1 | SPEC | [NAIF-FK] |
| Total rotation angle, DE440 | 0.02886 deg = about 875 m on a great circle | SPEC | [NAIF-FK] |
| The same, as NASA states it | "up to 875 m (572 m in longitude)" | SPEC | [PAC24] slide 3; [ACR24] |
| Displacement at the south pole itself | 662.9 m horizontal, 0.13 m vertical | CALC | E1, from [NAIF-FK] with SPICE |
| Displacement at the Connecting Ridge tile centre (89.46 S, 222.5 E) | 659 m (444 m west, 487 m north when ME numbers are read as PA; the reverse for the opposite mistake) | CALC | E1 |
| `MOON_ME_DE440_ME421` against `MOON_ME_DE421`, 2000 to 2040 | at most 3.07e-7 rad = 53.4 cm | SPEC | [NAIF-FK] |
| `IAU_MOON` against the DE440-based ME frame, 2000 to 2040 | up to about 155 m, mean about 72 m | SPEC | [NAIF-FK] |
| "MOON_ME of DE421 ... overall uncertainty of a few meters relative to the principal axis frame" | a few m | MOON | [BARKER23] section 2 |
| Reference sphere | 1737.4 km; heights are distances above or below it | SPEC | [LROWP08] section 5.1; [LROC-SIS] |
| Longitude convention | planetocentric, east positive, 0 to 360 deg | SPEC | [LROWP08] section 5 |

Three practical consequences:

1. A SPICE program that does not load a lunar frames kernel gets `IAU_MOON`, which is wrong by up to 155 m.
   Load `moon_de440_250416.tf` with `moon_pa_de440_200625.bpc` and ask for `MOON_ME` by name [NAIF-FK].
2. `MOON_ME` in the current kernel is an alias for `MOON_ME_DE440_ME421`, a frame built to stay aligned with
   the DE421 Mean Earth frame of the LOLA and LROC products (within 53 cm until 2040). Old DE421 maps and new
   DE440 geometry can therefore be used together [NAIF-FK].
3. The PA frame of each new ephemeris moves a little; NASA's cartographers call PA frames "NOT suitable as a
   highest accuracy cartographic (mapping) reference frame" for that reason, and note that ME frames are
   "kept locked to the lunar surface" by a no-net-rotation step [PAC24] slide 4.

#### Who uses and recommends what (dated)

| Date | Body | Statement | Source |
|---|---|---|---|
| 1 Oct 2008 | LRO Project and LGCWG | LRO teams "shall deliver data to the PDS with planetocentric coordinates in the ME reference system only"; PA may be used internally | [LROWP08] |
| 22 Aug 2020 | LROC team (ASU) | products use "the mean Earth/polar axis system", de421, radius 1737.4 km | [LROC-SIS] section 5.5 |
| 2021 to 2023 | LOLA team (GSFC) | polar products: "south polar stereographic X/Y ... MOON_ME reference frame, DE421 ephemeris" | [PGDA78, PGDA81, PGDA90, PGDA-README] |
| Nov 2023 | NASA Planetary Science Advisory Committee | endorses "use of ME over PA lunar reference frame for mapping" | [PAC24] slide 2 |
| May 2024 | LOLA team | also publishes a `MOON_PA` global grid (64 and 128 pixels per degree) for geophysics | [PGDA95] |
| Aug 2024 | IAU General Assembly, Cape Town | Lunar Celestial Reference System (LCRS) and Lunar Coordinate Time (TCL) established | [ICG26-IAU] slide 5 |
| Dec 2024 | NASA Moon to Mars Architecture (ACR24) | architecture must support more than one frame; working group "endorsed the Mean Earth lunar reference frame as the standard for initial surface operations, including planning and user location data exchange"; no orbital standard endorsed | [ACR24] |
| 29 Jan 2025 | LunaNet Interoperability Specification v5 | names no frame itself: providers "shall adhere to the Lunar Reference System and Lunar Time System Standard [AD5]", document number "LNIS-TBD-AD0005"; message MSG-G32 carries frame transformations | [LNIS5] sections 2, 3.2.3.1 |
| Mar 2025 | USGS | Lunar Grid Reference System (LGRS) and Artemis Condensed Coordinates, built on the DE421 ME frame | [USGS-TM] |
| Oct 2025 | IAG/IAU Joint Working Group 1.1.3 | first International Lunar Reference Frame: PA system, combination of INPOP21a, DE430 and EPM2021; mean error 17.6 cm for 2010 to 2030; transformation to the DE421 ME frame good to 5 cm | [ILRF25] abstract |
| 11 Feb 2026 | LunaNet working group (NASA, ESA, JAXA) at the ICG workshop | AD5 will point to the ILuRF (PA) and define LunaNet messages for a "time varying transformation from ILuRF_PA to ME"; schedule: vendor draft May 2026, "Nov 2026: v1 publicly available" | [ICG26-RF] slides 6 and 9 |
| 30 Jul 2026 | IAG JWG 1.1.3 | "ILuRS adopts the PA frame as its natural choice"; ILuRF2026 delivered with 7-parameter transformations; PA to ME DE421 errors "reach 10 cm (7-parameter) and 14 cm (3-parameter)" | [ILURS26] |
| 11 Nov 2026 | NASA LNIS web page | still lists version 5 (published 7 Feb 2025) as current, with AD1 Volume A; AD5 is not listed | [LNIS-PAGE] |

So, as of 11 November 2026: maps and surface operations are in ME; the navigation service will be defined in
PA (ILuRF) and will broadcast the transformation; AD5 was promised for this month but we could not find it
published. NGA's own "Lunar Reference System" work is UNVERIFIED here (the NGA news page returned HTTP 403);
[PAC24] slide 10 lists NGA only as a consulted stakeholder. The IAU working group report itself
(Archinal et al. 2018) is UNVERIFIED in full text: only the Springer landing page and reference list were
read [WGCCRE15]; its ME recommendation is quoted second-hand from [LROWP08], [NAIF-FK] and [PAC24] slide 5.

#### Map projection used for south-pole products

LOLA and LROC polar products use a polar stereographic projection of the 1737.4 km sphere, centred on the
pole [PGDA69, LROC-SIS]. Two conventions are in use and they are not interchangeable:

| Convention | Scale at the pole | False origin | Grid north at the south pole | Source |
|---|---|---|---|---|
| LOLA / PGDA GeoTIFFs (what `lunarsim/terrain.py` reads) | 1 (true scale at the pole) | none: the pole is (0, 0) | +Y along longitude 0 | [PGDA69]; pack `meta.json` proj4 |
| USGS Lunar Polar Stereographic (LPS), for LGRS | 0.994 exactly ("true scale" at 81 deg) | 500 km east and north | "oriented in the direction of the 0 deg meridian", so it faces Earth | [USGS-TM] |

An LPS easting or northing is therefore not our X or Y: it is 0.6 % shorter and shifted by 500 km. LGRS adds a
25 km lettered grid and the Artemis Condensed Coordinates give a six-character position with 10 m precision
for voice use [USGS-TM]. The scale error of the PGDA convention near the pole is small (CALC, E2):

| Distance from the pole | Latitude | Scale error (k - 1) | Radial length error |
|---|---|---|---|
| 10 km | 89.67 S | 8 ppm | 0.03 m |
| 27.6 km (far corner of our tile) | 89.09 S | 63 ppm | 0.6 m |
| 50 km | 88.35 S | 207 ppm (0.21 m per km) | 3.5 m |
| 91 km | 87.0 S | 686 ppm | 20.8 m |
| 303 km | 80.0 S | 7,653 ppm | 772 m |

Height matters more than the projection at our site: the Connecting Ridge pack spans heights of -523 m to
+1,959 m about the sphere (MEAS, `meta.json` stats), which changes horizontal lengths by -301 to +1,128 ppm
(CALC, E2). USGS reports the same effect for the whole Moon as a "height factor" of 0.994 to 1.005 [USGS-TM].

### B2. Maps that already exist

Accuracy words: "geolocation" is where a product is on the Moon (absolute); "RMS Z" is the height error of a
grid cell against the true mean height of that cell; "effective resolution" is the size of the largest
feature that can hide between measurements.

| Product | Grid | Coverage | Accuracy (as stated by the source) | Format | Where | Licence or terms seen |
|---|---|---|---|---|---|---|
| LOLA site DEMs, "High-Resolution LOLA Topography for Lunar South Pole Sites" | 5 m | 27 named sites (Site01 Connecting ridge, Site04, 06, 07, 11, 20, 20v2, 23, 42, Haworth, Shoemaker, DM1-2, SL2-3, NPA-D, LM1-8) | track geolocation about 10 to 20 cm horizontal, 2 to 4 cm vertical after adjustment; median RMS Z about 0.30 to 0.50 m; RMS slope 1.5 to 2.5 deg; about 90 % of cells interpolated | GeoTIFF; per-cell error rasters; 100 "clones"; XYZI point clouds | https://pgda.gsfc.nasa.gov/products/78 | citation requested (Barker et al. 2021); no licence text on the page [PGDA78, PGDA-README] |
| South Pole LOLA DEM Mosaic | 5 m | 87 to 90 S (97 fields of 20 km, 2 km overlap) | "typical RMS residual of 30-55 cm" against the fields | GeoTIFF, 3.3 GB | https://pgda.gsfc.nasa.gov/products/81 | as above [PGDA81] |
| "A New View of the Lunar South Pole from LOLA" | 10 m (83 S), 20/40/80 m (80 S), 30 m (75 S), 60/120/240 m (60 S) | 60 to 90 S | raw tracks: "a few meters horizontally and <1 m vertically"; offsets applied RMS 8.7 / 9.5 / 0.64 m (along / cross / radial); final track geolocation "1.00/1.00/0.15 m as a conservative estimate"; fill factor 15 to 75 % at 20 m; effective resolution about 20 m poleward of 84 S | cloud-optimised GeoTIFF; error, slope, roughness, PSR rasters and shapefiles | https://pgda.gsfc.nasa.gov/products/90 ; DOI 10.60903/gsfcpgda-lola-spole | paper is CC BY 4.0 [PGDA90, BARKER23] |
| SLDEM2015 (LOLA + Kaguya Terrain Camera) | 512 px/deg (about 60 m) | **60 S to 60 N only** | LOLA: "vertical precision of ~10 cm and an accuracy of ~1 m"; merged product median RMS residual 2.6 m, 90th percentile 3.4 m | float IMG, JPEG2000, tiles | https://pgda.gsfc.nasa.gov/products/54 ; https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/sldem2015/ | citation requested [PGDA54] |
| Shape-from-shading DEMs, 13 Artemis III regions (Bertone et al.) | 5 m | the 13 regions announced in 2022 | NAC images sharpen the LOLA 5 m grid in lit areas; tied to LOLA; difference maps included; no single number on the page | GeoTIFF sets | https://pgda.gsfc.nasa.gov/products/104 ; Zenodo DOI 10.5281/zenodo.17954508 | citation requested; Zenodo licence UNVERIFIED (record not opened) [PGDA104] |
| LROC NAC images | 0.5 m per pixel from 50 km; swath 2.5 x 26 km | global, repeated | uncontrolled map products displaced "less than 20 m in the NAC" | PDS IMG; GeoTIFF for derived products | https://data.lroc.im-ldi.com/ ; https://pds.lroc.im-ldi.com/ | credit line not re-read here (see existing note) [LROC-SPEC, LROC-SIS] |
| LROC NAC stereo terrain models (`NAC_DTM`) | 2 to 5 m ("minimum of 3 times the native pixel scale") | selected sites; always geodetically controlled | per-product README; the Shackleton-rim ESA model's "RMS 0.5 m against LOLA" is in the existing note and was not re-read | PDS IMG, GeoTIFF; about 6.5 GB with sub-products | https://data.lroc.im-ldi.com/lroc/rdr_product_select | [LROC-SIS] |
| ShadowCam (on KPLO / Danuri) | 1.7 m per pixel from 100 km; footprint 5.2 x 144 km | permanently shadowed regions | "over 200 times more sensitive" than LROC NAC; no geolocation number on the pages read | PDS raw and calibrated; cloud-optimised GeoTIFF maps; "new data released quarterly" | https://pds.shadowcam.im-ldi.com/ ; https://data.im-ldi.com/lunaserv.html | footer "(c) ShadowCam 2026"; no licence text [SHADOWCAM] |
| LOLA illumination, Earth visibility, sky visibility, PSR | 240 m (65 to 90 deg), 120 m (75 to 90), 60 m (85 to 90) | both poles | hourly steps over 18.6 years; Sun as a finite disc; no error number | IMG, JP2, GeoTIFF, COG | https://pgda.gsfc.nasa.gov/products/69 ; https://pgda.gsfc.nasa.gov/data/MoonIllumination/ | citation requested (Mazarico et al. 2011) [PGDA69] |
| PSR outlines from the 20 m DEM | 20 m | 80 to 90 S | 506,349 PSRs; 1,531 larger than 1 km2; false positives and negatives studied | GeoTIFF, shapefile, CSV | https://pgda.gsfc.nasa.gov/products/90 | [PGDA90, BARKER23] |
| Diviner temperatures | page gives no cell size ("500-meter horizontal scales" overall) | global; polar cumulative products 5 Jul 2009 to 15 Mar 2020; polar resource products | no number on the page; solar channels 1 and 2 missing from most RDR since 17 Apr 2019 | PDS4 | https://pds-geosciences.wustl.edu/missions/lro/diviner.htm | PDS archive [DIVINER-PDS] |
| Chandrayaan-2 OHRC | about 0.25 m from 100 km, 3 km swath | selected strips | UNVERIFIED: the PRADAN site did not resolve and the USGS page returned 403; figures are from search snippets only | PDS4, login needed | https://pradan.issdc.gov.in/ch2/ | UNVERIFIED |

Also available, in one paragraph: the PDS holds the same LOLA grids in PDS3 form (cylindrical 4 to 512 pixels
per degree; polar stereographic 240 m down to 5 m) [LOLA-GDR]; LROC publishes 1 m `NAC_POLE` mosaics of
85.5 to 90 degrees and 20 m long-exposure mosaics of permanent shadow, both uncontrolled [LROC-SIS]; PGDA has
a 30 m shape-from-shading model of the approach corridor (1.1 GB) [PGDA92], a `MOON_PA` copy of the global
LOLA grid [PGDA95], and a machine-learning method that sharpens a 320 m model to 20 m with 5 to 6 m RMS
height error, which its authors call "a methodological demonstration" [PGDA106]. KPLO's LUTI camera is
UNVERIFIED: the KARI data page could not be read.

What the table means for a rover:

- Height at a point: LOLA is the reference; expect 0.3 to 0.5 m RMS where tracks are dense and worse where a
  5 m cell lies between tracks (each site has a per-cell error raster, `*_toterr.tif`) [PGDA-README].
- Position of the map on the Moon: about 1 m after track adjustment [BARKER23]; images that are not
  controlled can sit up to 20 m away from it [LROC-SIS].
- Detail: about 20 m over most of the Artemis zone [BARKER23]. A 5 m grid drawn from 20 m sampling shows
  smooth ground where there may be a 3 m crater. Shape-from-shading adds real detail at 5 m but only where the
  Sun reaches [PGDA104]; ShadowCam sees into shadow at 1.7 m but gives pictures, not heights [SHADOWCAM].
- LRO is still delivering: PDS Release 67 (15 September 2026) added LOLA data acquired from 24 March to
  13 June 2026 [LOLA-PDS].
- SLDEM2015 is often listed with the polar products but stops at 60 S; it is of no use for the base [PGDA54].

### B3. How several rovers merge their local maps

#### The method in four steps

1. Each rover builds a pose graph: a node for its pose every metre or so, an edge for the measured motion
   between two nodes (wheels, inertial unit, cameras). A small local map (a height or traversability patch)
   is stored with a node, in that node's own frame.
2. Rovers add edges between graphs: a place both have seen (an "inter-robot loop closure"), a radio range
   between two rovers at a known time, or a sighting of the same surveyed marker.
3. A least-squares solve (pose-graph optimisation, section E3) finds the node poses that best fit all edges.
   Wrong edges are removed first or down-weighted during the solve.
4. The local maps are redrawn at the corrected node poses and overlaid with a merging rule.

#### What the surveyed systems do

| System (year) | Who solves | Sensors | Tested where | Data exchanged | Wrong-match handling | Reported accuracy | Source |
|---|---|---|---|---|---|---|---|
| CADRE MoonDB + pose-graph module (2024) | elected leader; a "designated survivor" holds a full copy; the base station is the gateway to Earth | camera (stereo reconstruction), inertial, UWB ranging between rovers | JPL clean room (flight rovers) and Mars Yard (development models); **not flown** | pose-graph nodes and edges and local traversability maps (policy "all"); rover state (policy "latest"); mesh radio "minimum of 1Mbps of aggregate bandwidth"; no sharing while driving (motor interference) | no visual matches: UWB ranges tie the graphs; merge rule by resolution and time | no accuracy number published | [MOONDB] |
| LAMP 2.0 (2022), JPL-led team CoSTAR | central base station | lidar | DARPA Subterranean Challenge sites: 4 robots over 6 km (Kentucky), 2 robots 2.5 km (tunnel) | odometry and "keyed scans" to the base | GNC robust solve; "able to perform well with more than 80% outlier loop closures" | "errors (below 2 m) with trajectory lengths of up to 2.2 km"; map errors below 4 m | [LAMP2] |
| Kimera-Multi (2022) | distributed; all robots | stereo camera + inertial | simulation, EuRoC, outdoor ground-robot data | 65.9 MB for 2,918 poses (place recognition 22.6, geometric check 41.5, optimisation 1.8); sending images instead: 2,113 MB | distributed GNC; reported better than PCM | (see next row) | [KM22] Table II |
| Kimera-Multi field tests (2023) | distributed, compared with a central solver | as above | MIT campus: 6 robots, 6,044 m outdoor; 8 robots, 7,785 m indoor-outdoor; tunnels | link use 0.01 to 0.55 MB/s average, 2.1 MB/s peak; 20 to 46 % of packets dropped; delays up to 7.7 s | only 20.8 to 36.5 % of detected loop closures are inliers | trajectory error (RMS) 4.48 / 7.71 / 12.4 m distributed and 4.38 / 5.83 / 9.38 m central (tunnels / hybrid / outdoor); map error 1.9 to 4.8 m | [KM23] Tables I, II |
| Swarm-SLAM (2023) | one robot elected at each meeting | lidar, stereo or RGB-D | public datasets; 3 robots in an indoor car park | 94.95 MB for 3,103 keyframes over 475 m | GNC; 10 of 67 inter-robot loop closures rejected | 2.17 m on KITTI 00 with 2 robots and 280 kB of back-end traffic | [SWARM] Tables II, III |
| DOOR-SLAM (2020) | distributed (DGS) | stereo camera | KITTI 00; two drones on a football field | 1.00 kB descriptor per keyframe; 34.5 + 25.0 kB of keypoints per candidate match; 0.34 kB per loop closure | PCM | "dramatic distortion" without rejection (no single number extracted) | [DOOR] Table II |
| COVINS (2021) | central server | camera + inertial | EuRoC; 12 agents in a photo-realistic simulator | full keyframe 97 kB, keyframe update 273 B, landmark 162 B; 400 to 600 kB/s per agent up, 2.3 kB/s down | server-side place recognition | 0.036 m (EuRoC, 1,681 keyframes) | [COVINS] Tables 2, 3 |
| D2SLAM (2024) | distributed | stereo or omnidirectional camera + inertial | datasets and real drone flights | compact keyframe 1.2 kB (stereo) or 4.8 kB (omni); complete 20.1 or 56.3 kB; pose-graph update about 81 kB | distributed optimisation | 2.5 cm relative position at close range | [D2SLAM] |

Derived figures (CALC): Kimera-Multi 12 to 23 kB per pose across its five datasets (59.4 MB for 5,088 poses
to 65.9 MB for 2,918); Swarm-SLAM 30.6 kB per keyframe and 200 kB per metre driven. The lowest published
total is "only around 2MB in total" for ten simulated robots on KITTI 00 [CIES18].

#### Pose-graph optimisation, distributed versions and outlier rejection

- Central solve: all graphs at one node; standard and most accurate. In [KM23] the distributed solver is
  "comparable but less accurate ... due to the fact that the distributed solver only solves GNC
  approximately".
- Distributed solve: each robot optimises its own poses and exchanges only the poses that touch another
  robot's graph. In DGS a robot "only sends an estimate of its rendezvous poses", which its authors call a
  "privacy constraint" [DGS]. DPGO adds a certificate of global optimality and claims "privacy protection"
  by the same mechanism [DPGO].
- Pairwise consistency maximisation (PCM): two inter-robot edges are consistent if, combined with the two
  robots' own odometry, they close a loop within a statistical threshold; the largest set of mutually
  consistent edges (a maximum clique of the consistency graph) is kept [PCM]. Graduated non-convexity (GNC)
  instead solves with a robust cost that is tightened step by step; [KM22] and [LAMP2] report it as more
  robust than PCM.
- Rejection is not optional: 15 % (Swarm-SLAM car park), 63 to 79 % (Kimera-Multi field tests) and more
  than 80 % (LAMP 2.0) of candidate matches were wrong.

#### What changes on the Moon

- Low Sun and long shadows change how a place looks between two passes. NASA Ames built the POLAR datasets
  for stereo vision under this lighting [POLAR, POLARTRAV]. Visual place recognition between rovers is
  therefore the weak step; radio ranges and surveyed markers are the robust ones. CADRE made the same choice
  [MOONDB].
- A common frame can be fixed at the start: LAMP 2.0 puts the robots in front of a gate with "three
  reflective plates (fiducial markers) with known 3D coordinates" [LAMP2]. A base can do this permanently.
- Planetary-analogue data for testing: the Erfoud set has two robots with centimetre RTK truth and names
  "multi-robot SLAM approaches" as a use [ERFOUD]; S3LI (Mt. Etna) has 7 sequences with D-GNSS truth [S3LI].
  The DLR ARCHES demonstration on Etna ("collaborative multi-robot 6D SLAM") is UNVERIFIED: the paper is
  closed access and only its abstract was seen in search results.

### B4. Who holds the "ground truth" map

| Property | Base-held authoritative map, versioned tiles | Fully distributed map (CRDT-like merging) |
|---|---|---|
| One answer to "is this cell safe?" | yes, by construction | only after all copies have exchanged all updates |
| Works out of contact | rover drives on its copy; changes queue until contact | yes |
| Failure of one node | the base is a single point; needs a standby copy (CADRE's "designated survivor") | none |
| Wrong or hostile contribution | checked once, at the base, before it spreads | spreads first; every rover must check |
| Mixed owners | one registry, one rule book, one audit log | every pair of owners needs a trust rule |
| Radio cost | star: every rover to the base | mesh: shorter links, more total traffic |
| Global re-alignment (a new solve moves many tiles) | one new version of the affected tiles | every copy must reach the same solve result |
| Field evidence | LAMP 2.0, COVINS, CADRE (leader) | Kimera-Multi, Swarm-SLAM, DOOR-SLAM, D2SLAM (single-owner teams) |

What the systems actually do: the three that serve an operator who needs one map (a rescue team, a mission
control) centralise the merge. CADRE elects the leader, replicates everything to one backup, and shares
"localization and mapping information ... only when the leader requires information for replanning"
[MOONDB]. The distributed systems were built to work without infrastructure; they agree on poses, and each
robot then builds its own dense map. None of the ten systems in B3 has a rule for two owners who disagree,
and none signs data.

A conflict-free replicated data type (CRDT) is a data structure whose copies can be updated independently and
always converge once they have seen the same updates; hashes linked in a tree or graph (a Merkle structure)
let two copies find what the other is missing [MERKLE]. The original CRDT report by Shapiro et al. (INRIA,
2011) is UNVERIFIED here: the HAL server refused automated download. CADRE's merge rule is in effect such a
type for one cell: the newer value wins "if v_t' has the same or higher resolution than v_t", the older wins
"if v_t has higher resolution", and "the footprint of all rovers' past poses" is marked free [MOONDB] eq. 1.

Recommendation for a mixed-company fleet: a base-held authoritative map, with CRDT rules only for the layers
where they are safe. Reasons:

1. Owners can keep raw sensor data. The base needs derived cells and an error estimate, not images. DGS shows
   the same idea at the pose level: a robot reveals only the poses where it met another robot [DGS].
2. A hazard that one rover reports must reach all rovers through one checked path, not through gossip.
3. A logistics base has a base. The single-point risk is handled by a standby copy and by every rover
   carrying the last full map.
4. Hazard and keep-out layers can still merge without the base when two rovers meet, because a safe rule
   exists for them (the more cautious value wins until the base decides). Height cannot: averaging two
   misaligned height patches makes a false ridge.

### B5. Synchronising after a long time out of contact

What is exchanged, in order (our proposal, built on [MOONDB] and [MERKLE]):

| Step | Content | Size (CALC or ASSUMED, see E4) |
|---|---|---|
| 1 | Root hash of each layer, both ways | 8 bytes per layer |
| 2 | Hash-tree walk down to the changed tiles | at most 4 x 8 x 6 = 192 bytes per changed tile (3,906 tiles) |
| 3 | Keep-out zones and moving obstacles (vector, short-lived) | hundreds of bytes |
| 4 | Hazard tiles on the rover's planned route, then the rest | about 2 kB per 256 m tile |
| 5 | Road network changes (vector) | about 40 bytes per changed edge (ASSUMED) |
| 6 | Traversability cost tiles | about 12 kB per tile |
| 7 | Radio coverage tiles | about 2 kB per 1.28 km tile and radio node (ASSUMED) |
| 8 | Height refinements | 17 kB (orbital 5 m, MEAS) to 33 kB (rover 1 m, ASSUMED) per tile |
| 9 | The rover's own offline observations, after re-anchoring, up to the base | same sizes |

Bandwidth cost for one example (16 km site, 3,906 tiles of 256 m, 42 tiles changed in a day; assumptions
in E4):

| Item | Bytes | 10 kbit/s | 100 kbit/s | 1 Mbit/s |
|---|---|---|---|---|
| Hash-tree walk (upper bound) | 8.1 kB | 6.5 s | 0.6 s | 0.06 s |
| Flat list of all tile versions instead (10 bytes each) | 39 kB | 31 s | 3.1 s | 0.3 s |
| Hazard tiles (42) | 86 kB | 69 s | 6.9 s | 0.7 s |
| Traversability tiles (42) | 495 kB | 6.6 min | 40 s | 4.0 s |
| Height refinements (42) | 1.38 MB | 18.3 min | 1.8 min | 11 s |
| First load of the whole 5 m height layer | 2.87 MB (MEAS) | 38 min | 3.8 min | 23 s |
| First load of the whole hazard layer | 8.0 MB | 107 min | 10.7 min | 64 s |

So: load the full map before deployment or at the charger; on the mesh send only changes, hazards first.
CADRE's flight design has the same shape: it logs per destination which records were sent and acknowledged,
resends the unacknowledged ones, and for state data sends only the latest value [MOONDB] section 4.

Re-anchoring a drifted local map, step by step:

1. The rover's local tiles are attached to pose-graph nodes, not to map coordinates [MOONDB] section 5.2.
   Correcting the poses therefore corrects the map without touching the tiles.
2. On return the rover measures to surveyed markers (ranges to three or more radio anchors from two poses,
   or range and bearing to one marker plus a star-tracker heading). These become edges to fixed nodes (E3).
3. The pose graph is solved again. Drift that grew with distance is spread back along the path; with a fix
   at both ends the largest remaining error is about half the open-loop end error (E3).
4. Check before submitting: compare the rover's height patch with the authoritative tile under it. If the
   median difference is larger than the stated error of both, the alignment is wrong; do not submit.
5. Submit derived cells with the node covariance, the map version they were built against, and a signature.

### B6. NASA and other public data we can use, in full

#### (a) LOLA, LROC, ShadowCam and Diviner south-pole products

Product pages are in the table of B2 and in the source list. The data directories and nodes behind them:

| What | Exact URL |
|---|---|
| PGDA product list | https://pgda.gsfc.nasa.gov/products |
| LOLA 5 m site files and readme | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/SiteXX/ ; https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/README |
| LOLA 87 S mosaic files | https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/87S/ |
| LOLA 10 to 240 m files, PSRs, roughness | https://pgda.gsfc.nasa.gov/data/LOLA_20mpp/ |
| Illumination and Earth-visibility files | https://pgda.gsfc.nasa.gov/data/MoonIllumination/ ; http://imbrium.mit.edu/EXTRAS/ILLUMINATION/ |
| LOLA `MOON_PA` files | https://pgda.gsfc.nasa.gov/data/LOLA_PA/ |
| Approach-path DEM | https://pgda.gsfc.nasa.gov/data/LargeDEM/share_hls_v2_mar.tar (1.1 GB) |
| LOLA at the PDS (tracks and grids) | https://pds-geosciences.wustl.edu/missions/lro/lola.htm ; https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/ |
| LOLA Data Node (newer than the PDS); SLDEM2015 | http://imbrium.mit.edu/ ; http://imbrium.mit.edu/DATA/SLDEM2015/ |
| Lunar Orbital Data Explorer | https://ode.rsl.wustl.edu/moon/ |
| LROC search, PDS volume, specification | https://data.lroc.im-ldi.com/lroc/rdr_product_select ; https://pds.lroc.im-ldi.com/ (redirects to pds.mcp.nasa.gov) ; https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DOCUMENT/RDRSIS.PDF |
| ShadowCam | https://pds.shadowcam.im-ldi.com/ ; https://data.im-ldi.com/lunaserv.html |
| Diviner polar products | https://pds-geosciences.wustl.edu/lro/urn-nasa-pds-lro_diviner_derived1/data_derived_pcp/ ; same path with /data_derived_prp/ |

#### (b) The NASA PDS Artemis II archive: what is actually there (checked 11 November 2026)

Mission facts from the archive: launch 1 April 2026 22:35:12 UTC; closest approach 6 April 2026 23:00 UTC,
"approximately 6,543 km above the lunar farside" [A2-GUIDE] (the node page says 6,545 km [A2-PDS]; the
archived trajectory gives 6,545.0 km at 23:00:50 UTC over 2.6 S, 179.6 E, CALC from [A2-SPICE]); splashdown
11 April 2026 00:07 UTC. First archive release: 7 October 2026 [A2-PDS].

| Bundle (node) | Products counted | Bytes | Formats | Time range |
|---|---|---|---|---|
| Crew camera (Imaging) | 10,329 Nikon images in each of four collections | source NEF 223.1 GB; raw TIFF 567.9 GB; processed TIFF 1,692.9 GB; browse PNG 46.0 GB; total 2,531.9 GB | .nef, 16-bit .tif, .png, PDS4 .xml | 2 to 9 April 2026 (guide Table 4) |
| Orion camera (Imaging) | 1,012 still images: OpNav 404, DCAM 249, SAW Cam 3 189, Cab Cam 2 148, SAW Cam 4 12, SAW Cam 2 10; 22 videos | raw TIFF 15.75 GB (OpNav 2.15 GB); video 26.27 GB; browse 1.41 GB; total 43.4 GB | 8-bit .tif, .png or .jpg browse, .mp4 | OpNav: 2 to 10 April 2026 |
| Mission audio (Imaging) | 54 crew recordings, 3 voice-loop files, transcripts, 5 annotation PDFs | 0.85 GB | .m4a, .csv, .srt, .pdf | not tabulated here |
| Mission (Geosciences, lead node) | 6 documents; 2 data-logger tables | user guide 8.3 MB; targeting package 172 MB and 196 MB (extended); loggers 1.7 MB each | .pdf, .json, .html, .csv | loggers 26 March to 21 April 2026, every 60 s |
| SPICE (NAIF) | 32 kernels and 1 meta-kernel | about 0.59 GB (attitude files 357 MB and 92 MB; de430 114 MB; trajectory 5.4 MB) | SPICE kernels | trajectory 2 April 01:58:21 to 10 April 23:53:25 UTC, six segments |

Counts and bytes are from the Imaging Node's Atlas search index, queried on 11 November 2026 and summed by
bundle, collection and file type (87,102 files in total, labels included) [A2-ATLAS]; the SPICE and Mission
figures are from the directory listings [A2-SPICE, A2-PDS]. Three things differ from the documents:

- The guide speaks of 10,339 Nikon images; the index holds 10,329 per collection. The iPhone collection is
  "still being prepared" [A2-GUIDE].
- The lead node page still says "The SPICE bundle at the NAIF node is delayed" [A2-PDS], but the NAIF
  directory is populated (kernels dated 5 and 6 October 2026, directories touched 6 November 2026) and its
  trajectory kernel loads and gives the numbers above [A2-SPICE].
- All 397 OpNav labels we could read give the target as "Moon", including the first session, when Orion was
  76,000 km from Earth and 364,000 km from the Moon (CALC). Do not trust the target field.

OpNav camera, as archived: 2,592 x 2,048 pixels, 8-bit monochrome, 5.3 MB per TIFF, "No calibration was
applied" [A2-GUIDE]; field-of-view half-extents 10.05 x 7.972 degrees [A2-SPICE, instrument kernel], which
is 135 microradians per pixel (CALC). The 404 images were taken in six short sessions (times from the PDS4
labels [A2-ATLAS]; distances CALC from [A2-SPICE]):

| Session (UTC, 2026) | Labels read | Distance to Moon centre | Moon diameter in the image | Ground sample |
|---|---|---|---|---|
| 2 Apr 12:49 to 13:19 | 163 | 364,000 to 366,000 km | 70 px | 49 km per pixel |
| 3 Apr 19:54 to 20:24 | 45 | about 250,000 km | 103 px | 34 km |
| 4 Apr 21:13 to 21:24 | 48 | about 165,000 km | 155 px | 22 km |
| 6 Apr 00:08 to 00:37 | 44 | 79,000 to 81,000 km | 318 to 325 px | 10.7 to 10.9 km |
| 6 Apr 23:00, closest approach | none | 8,283 km | (3,123 px: wider than the frame) | (1.1 km) |
| 7 Apr 21:08 to 21:37 | 45 | 78,000 to 80,000 km | 322 to 328 px | 10.6 to 10.8 km |
| 10 Apr 00:18 to 16:27 | 52 | 241,000 to 314,000 km | 82 to 107 px | 33 to 42 km |

Seven of the 404 labels failed to download; the session counts are of the 397 read.

Usable for a surface-rover project:

1. SPICE bundle: a complete, small, citable example of the frame set we recommend. Its meta-kernel loads
   `moon_pa_de440_200625.bpc`, `moon_de440_250416.tf` and `moon_assoc_me.tf`, the same lunar kernels as
   `tools/comms/earth_link.py`, so it works in `MOON_ME` [A2-SPICE]. Earth, Moon and Sun geometry for
   2 to 10 April 2026 with a real trajectory is a ready test case for our geometry code.
2. OpNav images with the trajectory: a real test set for "where is the camera, from the Moon's disc and
   limb" at 78,000 to 366,000 km. That is cislunar navigation, not surface or landing navigation. The
   spacecraft attitude file "contains several gaps" [A2-SPICE].
3. Crew Nikon images: 3,687 carry control points and corner coordinates on the 1737.4 km sphere [A2-GUIDE]
   section 5.2.7 (its Figure 7 caption says 3,101 of 10,339 were georeferenced). With the 400 mm lens a
   pixel is 16 microradians (half-extent 2.564 degrees over 5,568 pixels [A2-SPICE]), so about 105 m under
   the spacecraft and 130 m at the limb at closest approach (CALC). At every time we sampled (the six OpNav
   sessions and closest approach) Orion was between 2.6 S and 4.2 N of the lunar equator (CALC), so the
   south pole was on the limb, seen edge-on. Use: a coarse, dated (6 April 2026) check of large shadows; not
   a check of site-scale illumination.
4. The geolocation method (find basemap tiles by image embedding, match features, fit with RANSAC)
   [A2-GUIDE] section 5.2.7 is the same idea as fixing a rover or lander against an orbital map.

Not usable: anything at rover scale (no surface images, no terrain model, no rover telemetry, no radio
measurements); the audio and transcripts; the locker temperature loggers; the solar-array camera video.

#### (c) NAIF generic kernels for the Moon

| Kernel | Purpose | URL |
|---|---|---|
| `moon_de440_250416.tf` (19 kB, 16 Apr 2025) | defines `MOON_ME`, `MOON_PA`, `MOON_PA_DE440`, `MOON_ME_DE440_ME421` | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf |
| `moon_assoc_me.tf`, `moon_assoc_pa.tf` (8 kB each) | make ME or PA the Moon's default body-fixed frame for older SPICE routines | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/ |
| `moon_pa_de440_200625.bpc` (12 MB) | lunar orientation from DE440 [NAIF-PCK] | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/ |
| `pck00011.tpc`, `naif0012.tls` | constants; leap seconds | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/ and https://naif.jpl.nasa.gov/pub/naif/generic_kernels/lsk/ |
| `de440s.bsp` (in the project cache) or `de440.bsp` | planetary ephemeris | https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/ |

#### (d) JPL CADRE and other rover datasets

No public CADRE dataset was found. Public CADRE material is papers: MoonDB (CC BY 4.0) [MOONDB] and the
ASTRA 2025 abstract [CADRE25]. Flight data cannot exist before the IM-3 landing (no earlier than the first
quarter of 2027; the schedule is from a secondary source [IM3-WIKI]). The LAMP 2.0 authors "release our
multi-robot back-end datasets (and the corresponding ground truth)" from the DARPA challenge [LAMP2];
Kimera-Multi releases its campus datasets with reference trajectories and point-cloud maps [KM23]. Their
download locations and licences were not checked.

#### (e) AI4Mars, analogue-terrain and simulated lunar datasets

| Dataset | What | Size | Licence seen | URL | Use for us |
|---|---|---|---|---|---|
| AI4Mars v0.6 (JPL, 2022) | about 50,000 Mars rover images, about 425,000 crowd labels, about 1,500 expert labels; soil, bedrock, sand, big rock | 17.8 GB (16.2 + 1.6) | CC BY 4.0 | https://zenodo.org/records/15995036 | terrain-class method; Mars, not Moon [AI4MARS] |
| POLAR Stereo (NASA Ames, 2017) | "over 2500 HDR stereo pairs", 13 terrains, oblique light, lidar truth "sub-2mm" | 11.5 GB | none stated | https://ti.arc.nasa.gov/dataset/IRG_PolarDB/ | stereo under polar lighting [POLAR] |
| POLAR Traverse (NASA Ames, 2023) | four views: 20 and 150 degree lighting, forward and reverse cameras | 13.4 GB (views 3.1 to 3.3 GB) | none stated | https://ti.arc.nasa.gov/dataset/PolarTrav/downloads.html | visual odometry under polar lighting [POLARTRAV] |
| S3LI Etna (DLR, 2022) | stereo, solid-state lidar, inertial; 7 sequences; D-GNSS truth | not stated | CC BY-NC-SA 4.0 | https://datasets.arches-projekt.de/s3li_dataset/ | SLAM on Moon-like ground [S3LI] |
| S3LI Vulcano (DLR, 2026) | camera and lidar; place recognition | about 500 GB | not stated | https://my.hidrive.com/share/5iodmhym4m | larger sequel [S3LI] |
| MADMAX (DLR, 2021) | 36 runs, 9.2 km, 8 sites in Morocco; stereo, colour, omnidirectional, inertial; RTK truth | not stated | not stated | https://datasets.arches-projekt.de/morocco2018/ | visual-inertial navigation [MADMAX] |
| Erfoud (LAAS, 2020) | two robots, three sites, 9 routes; about 110,000 georeferenced stereo pairs; lidar; cm RTK | not stated | not stated | https://sites.laas.fr/projects/erfoud-dataset (index) | **two-robot** map merging [ERFOUD] |
| Devon Island (Univ. of Toronto, 2012) | 10 km traverse, stereo every 20 cm, Sun sensor, DGPS, lidar at 37 places, orbital DEM | not stated | not stated | https://asrl.utias.utoronto.ca/datasets/devon-island-rover-navigation/ | long traverse; matching to an orbital DEM [DEVON] |
| LuSNAR (2024) | simulated Moon, 9 scenes; stereo, depth, lidar, semantic labels | 108 GB | MIT (repository badge) | https://github.com/zqyu9/LuSNAR-dataset | perception and SLAM in simulation [LUSNAR] |

---

## C. Our design choice

### C1. Frame

- Canonical frame: `MOON_ME`, DE421 realisation (in today's SPICE kernel the name `MOON_ME` resolves to
  `MOON_ME_DE440_ME421`, within 53 cm of it [NAIF-FK]). Coordinates: planetocentric latitude, east longitude
  0 to 360 degrees, height above the 1737.4 km sphere. Reason: it is the frame of every terrain and image
  product in B2 and NASA's endorsed standard for surface location exchange [ACR24].
- Map grid: south polar stereographic of the 1737.4 km sphere, true scale at the pole, +Y along longitude 0,
  metres, no false origin. This is the LOLA convention and what `lunarsim/terrain.py` already reads.
- Every position in every message carries a `frame_id` and a `datum_id`. A receiver rejects a position
  without them. Ids we define now: `MOON_ME`, `MOON_PA_DE440`, `ILuRF2026` (PA), `LPS-S` (the USGS grid),
  `SITE-<name>-v<n>`.
- A position from a navigation service in a PA frame is converted once, in the receiver, with the published
  transformation (three angles from [NAIF-FK], or the seven-parameter transformation of [ILURS26], good to
  10 cm). It is never mixed into the map unconverted.
- For people: the LGRS / Artemis Condensed Coordinates label [USGS-TM] is shown next to a position. It is
  computed for display and never stored as the primary value.

### C2. Datum for a base

- One surveyed point O (a marker on the first lander or on a mast) with declared `MOON_ME` coordinates and
  declared map-grid coordinates (X0, Y0) and height h0. It is declared once as version 1 and is never moved
  silently.
- Site grid frame `SITE-<name>-v1`: x = X - X0, y = Y - Y0, z = h - h0. It is grid-aligned, as in
  `terrain.py`. Bearings are grid bearings (0 = +y). An east-north-up frame at O is derived from it for
  antenna and Sun pointing only (E1).
- At least three surveyed markers (radio-ranging anchors or optical targets) more than 100 m apart, with site
  coordinates known to 0.1 m. They are the frame as far as a rover is concerned: a rover that measures to
  them is in the frame.
- The datum's absolute position in `MOON_ME` comes from registering the site survey to the LOLA model and to
  controlled images; expect 1 to 10 m (B2). This error is the same for every user of the datum, so it does
  not affect driving. It is published as a `SITE-to-MOON_ME` transformation with its own version; improving
  it changes the transformation, not the site coordinates.
- Heights stay relative to the sphere, not to a tangent plane at O: a plane drops below the sphere by
  d^2 / 2R, which is 0.29 m at 1 km and 18 m at 8 km (CALC).

### C3. Layers

| Layer | Form | Cell | Tile | Made from | Who may change it | Lifetime of a value |
|---|---|---|---|---|---|---|
| Elevation, level 0 | raster, 16-bit, 0.5 m steps | 5 m | 1,280 m (256 cells) | LOLA 5 m site DEM, shape-from-shading where lit | base only | until a new orbital product |
| Elevation, level 1 | raster, 16-bit, 0.05 m steps, with per-cell error | 1 m | 256 m | rover stereo or lidar, fused by the base | base only (rovers submit patches) | permanent |
| Hazard | raster, 2 bits: unknown, free, hazard, hazard-confirmed | 1 m | 256 m | rover observations | any rover (provisional); base (confirmed) | permanent until cleared |
| Traversability cost | raster, 8 bits (255 = impassable), one base value plus a multiplier per vehicle class | 1 m | 256 m | slope, roughness, hazard, measured slip | base | permanent |
| Road network | graph: nodes, edges with centre line, width, speed limit, direction, surface state, last-driven time | n/a | per edge | planner and drive logs | base | permanent; state fields 30 days |
| Keep-out zones | polygons with reason, issuer, start and end time | n/a | per zone | landing schedule, work sites, cables | issuing authority only | until end time |
| Radio coverage | raster, 8 bits (link margin in dB), one per fixed radio node | 20 m | 1,280 m | computed from elevation; corrected by rover measurements | base | until a node moves |
| Illumination | not stored as a map: computed from elevation and ephemeris; the base publishes "lit until / dark until" per 20 m cell for the next 30 days | 20 m | 1,280 m | elevation level 0 + SPICE | base | 30 days |

Pads and work sites may add a level 2 (0.25 m cells, 64 m tiles).

### C4. Tiles and versions

- A tile is named (layer, level, ix, iy), counted from the site grid origin.
- Each tile has a version number (32 bits), a content hash (SHA-256; 8 bytes of it in sync digests), the list
  of contributions it contains, and the elevation version it was built against.
- Tiles of one layer form a quadtree; each parent stores the hash of its four children's hashes.
- Size of a tile on the wire: see D.

### C5. Who is authoritative

The base map authority: a service at the base, run by the base operator or by a registry that all owners
accept, with a standby copy on a second node (CADRE's "designated survivor" pattern [MOONDB]). Rovers carry a
full copy and may drive on it without contact. Only the authority issues new tile versions for elevation,
confirmed hazards, cost, roads and coverage.

### C6. How a contribution from one owner is accepted

1. Form: a contribution is a set of derived cells (hazard, free, height with error, measured slip, measured
   link margin), each with time, sensor class, cell size, the pose covariance of the observing node, and the
   map version it was built against. No raw images. It is signed with the owner's key (signature scheme: see
   the security part).
2. Frame check: `frame_id` and `datum_id` match the current datum version.
3. Anchoring check: the contribution states how long ago and how far back the rover last measured to a
   surveyed marker. Position sigma above 2 m (ASSUMED limit) is not accepted for 1 m layers.
4. Consistency check: the contribution's heights are compared with the authoritative elevation; a median
   difference above 1 m (ASSUMED; about twice the LOLA RMS) means misalignment and rejection.
5. Hazards are accepted at once as provisional and are grown by three sigma of the reported position error
   (E5). They become confirmed when a second owner reports the same hazard or the same owner sees it again
   from a different pass.
6. Clearing a hazard needs a newer observation at the same or finer cell size [MOONDB] eq. 1 from two
   independent passes, or a recorded drive-through of the cell.
7. Heights are fused by the base (inverse-variance weights) and issued as a new tile version.
8. Every accepted or rejected contribution is logged with owner, time and reason. Between companies the log
   is what settles a dispute about who reported what.

### C7. Conflicts and stale data

| Case | Rule |
|---|---|
| Two rovers meet out of contact with different hazard tiles | merge cell by cell: hazard beats free, newer beats older at equal cell size, finer beats coarser; result is provisional |
| Rover's copy is older than the base's | rover takes the base's tiles; its own queued contributions are re-checked against the new version |
| Rover's offline contribution was built against an old elevation version | accepted only if the tile's elevation did not change, otherwise re-registered first |
| Two owners disagree (one says free, one says hazard) | hazard stands as provisional; the authority asks for a third pass |
| Keep-out zone past its end time | expires on every copy without contact with the base |
| The base and its standby disagree after a split | higher version wins; equal versions with different hashes are both withdrawn and rebuilt from the log |

---

## D. Simulation parameters

| Parameter | Value | Sweep range | Unit | Source |
|---|---|---|---|---|
| Reference sphere radius | 1,737,400 | fixed | m | [LROWP08] |
| Frame mix-up fault (PA read as ME) at the site | 660 | 0 or 660 | m | CALC E1 from [NAIF-FK] |
| Site datum absolute error in `MOON_ME` (common to all rovers) | 5 | 1 to 20 | m | [BARKER23]; [LROC-SIS]; ASSUMED mid value |
| Orbital DEM height error, RMS per 5 m cell | 0.4 | 0.3 to 0.5; 1 to 2 where tracks are sparse | m | [PGDA78]; [BARKER23] |
| Orbital DEM slope error, RMS | 2.0 | 1.5 to 2.5 | deg | [PGDA78] |
| Orbital DEM effective resolution | 20 | 5 to 80 | m | [BARKER23] |
| Share of 5 m cells that are interpolated | 0.9 | 0.25 to 0.9 | fraction | [PGDA78]; fill factor 15 to 75 % at 20 m [BARKER23] |
| Projection scale error inside the 16 km tile | 63 | 2 to 63 | ppm | CALC E2 |
| Height factor at the site (z = -523 to +1,959 m) | +575 at 1 km height | -301 to +1,128 | ppm | CALC E2; pack `meta.json` (MEAS) |
| Elevation tile, level 0 (256 x 256 cells of 5 m, 0.5 m steps, PNG) | 17.4 | 15.3 to 25.1 | kB | MEAS on `data/terrain/connecting_ridge/height_5m.png` (144 tiles) |
| Binary hazard layer, compressed | 0.12 | 0.01 to 1.0 | bit per cell | MEAS: slope > 20 deg mask, 64 x 64 tiles: median 61 B, 90th percentile 347 B, max 487 B |
| Five-class traversability, compressed | 1.44 | 1 to 2 | bit per cell | MEAS: slope classes, median 736 B per 4,096 cells |
| Hazard tile, level 1 (256 x 256 cells of 1 m) | 2.0 | 0.1 to 8 | kB | CALC at 0.25 bit per cell (ASSUMED) |
| Traversability tile, level 1 | 11.8 | 8 to 16 | kB | CALC at 1.44 bit per cell |
| Rover-made elevation, compressed | 4 | 2 to 8 | bit per cell | ASSUMED (orbital data measured 2.1; real sensor noise compresses worse) |
| Elevation tile, level 1 (rover-made) | 32.8 | 16 to 66 | kB | CALC |
| Keyframe sent between rovers, by content | 1 / 20 / 97 | 1 to 100 | kB | descriptor only [DOOR]; features [D2SLAM, KM22]; full keyframe [COVINS] |
| Pose-graph node on the wire | 100 | 50 to 300 | B | ASSUMED (a pose is 48 B in [CIES18]; plus covariance and ids) |
| Share of candidate cross-rover matches that are wrong | 0.5 | 0.15 to 0.8 | fraction | [SWARM] 10 of 67; [KM23] 63 to 79 %; [LAMP2] more than 80 % |
| Map merge error after loop closure (position, RMS) | 2 | 0.5 to 12 | m | [LAMP2] below 2 m over 2.2 km; [KM23] 4.5 to 12.4 m over 6 to 8 km |
| Dead-reckoning drift between anchor fixes | 2 | 0.5 to 5 | % of distance | part 1 of this series |
| Surveyed marker position error in the site frame | 0.1 | 0.05 to 0.7 | m | ASSUMED; ranging accuracy from part 1 |
| Hazard growth radius | 3 x position sigma | 2 to 4 sigma | m | E5 |
| Contribution limits: position sigma / height disagreement | 2 / 1 | 1 to 5 / 0.5 to 2 | m | ASSUMED (C6) |
| Mesh data rate available for map traffic | 100 | 10 to 1,000 | kbit/s | task brief; CADRE mesh 1,000 aggregate [MOONDB] |
| Map exchange while driving | off | off, on | flag | CADRE shares only when stopped [MOONDB] |
| Packet loss on the mesh | 0.2 | 0 to 0.46 | fraction | [KM23] 20 to 46 % (2.4 GHz radio, Earth) |
| Tiles per layer, 16 km site, level 1 | 3,906 | fixed for this site | count | CALC (16,000 / 256)^2 |
| Tiles changed per day (hazard, cost, level-1 height) | 42 | 5 to 250 | count | ASSUMED: half of the 84 tiles crossed by the 21.4 km of legs in `data/site_graph.json` |
| Sync volume after N hours out of contact, hazards only | 3.6 x N | 0.4 to 21 x N | kB | CALC E4 (86 kB per 24 h) |
| Sync volume after N hours, all raster layers | 82 x N | 10 to 490 x N | kB | CALC E4 (1.96 MB per 24 h), capped by the route tiles |
| First full load, level-0 elevation / level-1 hazard | 2.87 / 8.0 | fixed for this site | MB | MEAS / CALC |

---

## E. Proof sketches we can put in a paper

### E1. From `MOON_ME` to a local east-north-up frame at a polar site, and the cost of the wrong frame

A point with planetocentric latitude phi, east longitude lambda and height h has Cartesian coordinates

    r = (R + h) (cos phi cos lambda, cos phi sin lambda, sin phi),   R = 1,737,400 m.

At a datum r0 with (phi0, lambda0) define the unit vectors

    e = (-sin lambda0, cos lambda0, 0)
    n = (-sin phi0 cos lambda0, -sin phi0 sin lambda0, cos phi0)
    u = ( cos phi0 cos lambda0,  cos phi0 sin lambda0, sin phi0)

and the matrix Q with rows e, n, u. Then p = Q (r - r0) is the east-north-up position. Q is orthonormal
(e.n = e.u = n.u = 0 and each has length 1), so r = r0 + Q^T p. For our tile centre (89.4632 S, 222.5104 E):
e = (0.6757, -0.7372, 0), n = (-0.7371, -0.6757, 0.0094), u = (-0.0069, -0.0063, -1.0000).

Link to the map grid. With X = rho sin lambda, Y = rho cos lambda and rho = 2R tan(c/2), where c is the
angle from the south pole, a small step (dX, dY) at longitude lambda0 is

    east  = (cos lambda0 dX - sin lambda0 dY) / k
    north = (sin lambda0 dX + cos lambda0 dY) / k,      k = sec^2(c/2)   (E2).

Check: at lambda0 = 0 the point is on the +Y axis; east is +X and north (away from the south pole) is +Y.
So the site grid is the local east-north frame turned by lambda0 and stretched by k. Because lambda0 changes
by tens of degrees across a polar site, we keep grid axes and convert only at the datum.

Wrong frame. Let M be the rotation with v_PA = M v_ME. If a position computed in PA is read as ME, the point
moves by delta = (M - I) r. For a small rotation vector theta, delta = theta x r to first order, so

    |delta| <= |theta| |r|,   with equality when r is perpendicular to theta.

The rotation vector of the matrix SPICE builds from the [NAIF-FK] angles is theta = (0.2914", 78.6944",
67.8526") = (1.413e-6, 3.8152e-4, 3.2896e-4) rad. Its length is |theta| = 5.0376e-4 rad = 0.02886 deg,
and |theta| R = 875.2 m, the published maximum. At the south pole
r = (0, 0, -R), so |delta| = R sqrt(theta_x^2 + theta_y^2) = 1,737,400 x 3.8152e-4 = 662.9 m: the rotation
about z does nothing at the pole. The vertical part is zero to first order (theta x r is perpendicular to r)
and -|delta|^2 / 2R = -0.126 m to second order. A direct evaluation with SPICE (`pxform` from `MOON_ME` to
`MOON_PA`, kernels of B6c) gives 662.86 m at the pole, 659.22 m at our tile centre and 875.23 m at latitude 0,
longitude 0. At the tile centre the shift is east -444.3 m, north +487.0 m, up -0.125 m when ME numbers are
read as PA, and the opposite when PA numbers are read as ME. The matrix is constant in time (checked at 2000,
2030 and 2040).

Two consequences. A whole fleet that uses PA consistently has no internal error, because the map is only
turned as a rigid body; the 660 m appears only when PA positions meet ME maps. And heading is hardly affected:
the turn about the local vertical is theta.u, which is 68" (0.019 deg) at the pole.

### E2. Scale distortion of the polar stereographic map within 50 km of the pole

Sphere of radius R, angle c from the pole, map radius rho(c) = 2 R k0 tan(c/2).

    radial scale     = d rho / (R dc)   = k0 sec^2(c/2)
    tangential scale = rho / (R sin c)  = 2 k0 tan(c/2) / (2 sin(c/2) cos(c/2)) = k0 sec^2(c/2)

The two are equal, so the map is conformal and the scale is k = k0 sec^2(c/2) = k0 (1 + tan^2(c/2)). With
k0 = 1 and surface distance d = R c from the pole,

    k - 1 = tan^2(d / 2R)  ~  (d / 2R)^2,        rho - d  ~  d^3 / (12 R^2).

At d = 50 km: (50 / 3,474.8)^2 = 2.07e-4, that is 207 ppm or 0.21 m per km, and rho - d = 3.45 m. Inside
50 km of the pole the map is true to better than 0.021 %. A leg of length L at mean distance d from the pole
is drawn too long by L (d / 2R)^2. The USGS grid uses k0 = 0.994, so it is 0.6 % short at the pole and true
near 81 degrees (0.994 x sec^2(4.5 deg) = 1.0002) [USGS-TM]. If its axes are oriented as stated in B1, then
X_LPS = 0.994 X + 500,000 m and Y_LPS = 0.994 Y + 500,000 m; check this against the USGS software before use.

Height. The map is drawn on the sphere. A length measured on ground at height h is longer than its map
length by the factor (R + h) / (R k). At our site h runs from -523 to +1,959 m, so h/R runs from -301 to
+1,128 ppm: up to 1.1 m per km, five times the projection term at 50 km. The simulator should compute leg
lengths from 3-D positions, not from map distances, if it needs better than 0.1 %.

### E3. Map merging as least squares, and why one anchor (or two) fixes the gauge

Unknowns: poses T_i in SE(2) (or SE(3)) of all nodes of all rovers. Measurements: relative poses Z_ij with
information matrices Omega_ij (odometry within a rover, loop closures within or between rovers). The merged
map is the minimiser of

    F(T) = sum over edges (i,j) of  || Log( Z_ij^-1 T_i^-1 T_j ) ||^2 weighted by Omega_ij.

Gauge freedom. For any rigid motion G, T_i^-1 T_j = (G T_i)^-1 (G T_j). So F(G T) = F(T): the cost cannot
tell where the whole graph sits. The Hessian at a minimum has a null space of dimension 3 in the plane (two
shifts and one turn) and 6 in space. If two rovers' graphs share no edge, each has its own freedom (6 in the
plane in total).

Fixing it.

- One edge between the two graphs that measures a full relative pose (a verified loop closure) leaves one
  common freedom: the rovers are in one frame, but the frame floats.
- One anchor with a known full pose in the site frame (position and heading, for example a marker seen with
  a camera plus a star-tracker heading) adds a term || Log(A^-1 T_a) ||^2 that changes under every G except
  the identity. The null space is empty and the solution is unique: the gauge is fixed.
- An anchor that gives position only (a ranging beacon at a surveyed point) fixes the shifts but leaves the
  turn about the anchor. A second position anchor at distance b removes it, with heading error about
  sqrt(2) sigma_p / b (0.08 deg for sigma_p = 0.1 m and b = 100 m). In space, gravity sensed by the rover
  already fixes roll and pitch, so the count is the same: one full-pose anchor, or two position anchors.
- Range-only edges between rovers (CADRE's choice) give one scalar each. Tying two planar graphs needs three
  independent ranges (three unknowns), and a fourth to remove the mirror solution.

How much error is left. Model drift as a random walk with variance q s after distance s (sigma = sqrt(q s)).
With an anchor only at the start, the error at distance L is sqrt(q L). With anchors at both ends (sigma_a
small) the corrected error at distance s is that of a pinned random walk, variance q s (L - s) / L, largest
at the middle: sigma_max = sqrt(q L) / 2. Closing the loop at the base halves the worst error and brings it
to zero at both ends. For drift that is a constant heading or scale bias, the two-ended fix removes it
almost completely, because one rotation and one scale explain all of it.

Outliers. One wrong inter-rover edge with a tight covariance drags the minimum by metres, which is why the
systems in B3 use robust costs (GNC) or select a consistent subset (PCM) before solving.

### E4. Bytes needed to synchronise, as a function of changed tiles

N tiles in a layer, n of them changed, mean compressed size s, per-tile header t, hash length h, version
length v, quadtree depth D = ceil(log4 N).

    Flat manifest:   B = N (v + h) + n (s + t)
    Hash tree:       B <= h (1 + 4 n D) + n (s + t)

Proof of the bound: start at the root (1 hash). A node is opened only if its hash differs, which happens
only if a changed tile lies below it; at each of the D levels at most n nodes are opened, and opening a node
costs its 4 child hashes. The tree wins when 4 n D h < N (v + h), that is n < N (v + h) / (4 D h).

Numbers for the 16 km site: N = (16,000 / 256)^2 = 3,906, D = 6, h = 8, v = 2. Flat: 39,060 B. Tree with
n = 42: 8 (1 + 4 x 42 x 6) = 8,072 B. The tree wins for n < 203. Time = 8 B / rate.

Payload sizes (s): hazard 256^2 x 0.25 / 8 = 2,048 B; traversability 256^2 x 1.44 / 8 = 11,796 B; rover
elevation 256^2 x 4 / 8 = 32,768 B. For n = 42: 86 kB, 495 kB, 1.38 MB; all three together 1.96 MB per day.
At 10 kbit/s these take 69 s, 6.6 min and 18.3 min. The 5 m elevation layer of the whole site is the
measured 2,874,671 B (38 min at 10 kbit/s, 23 s at 1 Mbit/s).

The change count n is the weak input. On a haul network it is bounded: rovers drive the same legs, so the
tiles that can change are those the legs cross. The nine-site graph in `data/site_graph.json` has 12 legs
and 21.4 km; 21,370 / 256 = 84 tiles (about 250 with one neighbour each side). We take half of the 84 as
changed in a day (ASSUMED). Exploration off the network is not bounded this way: a rover mapping a 20 m
swath at 3 km/h (the small-rover speed in `data/parameters.csv`) touches about 12 new tiles per hour.

### E5. An upper bound on map disagreement between two rovers

Rover A at true position x_A sees a feature at true position p, at range r_A = |p - x_A|. It records it at

    p_A = p + eps_A + dtheta_A J (p - x_A) + eta_A

where eps_A is its position error, dtheta_A its heading error (J turns a vector by 90 degrees) and eta_A the
sensor error. The same holds for rover B. Subtracting and using the triangle inequality:

    |p_A - p_B| <= |eps_A| + |eps_B| + |dtheta_A| r_A + |dtheta_B| r_B + |eta_A| + |eta_B|.

For independent zero-mean errors the RMS disagreement is

    sigma_AB = sqrt( sigma_A^2 + sigma_B^2 + (sigma_thA r_A)^2 + (sigma_thB r_B)^2 + sigma_etaA^2 + sigma_etaB^2 ).

Two additions: a raster adds at most half a cell diagonal per map (0.71 m for 1 m cells, worst case); and an
error that both rovers share (the datum's absolute error, C2) cancels in the difference.

Example: both rovers 1 m (1 sigma) after anchoring, heading 0.5 deg at 10 m range (0.087 m), sensor 0.05 m:
sigma_AB = sqrt(2 (1 + 0.0076 + 0.0025)) = 1.42 m; three sigma is 4.3 m. If instead each has driven 500 m
since its last anchor fix at 2 % drift (10 m each), sigma_AB = 14 m and the two maps cannot be merged at
1 m cells: the rover must re-anchor first (B5). This sets the hazard growth radius in C6 and the 2 m limit.

---

## F. Who to partner with

| Piece | Owner | What we would ask for | Public URL | Realistic for a small team? |
|---|---|---|---|---|
| LOLA terrain, error rasters, illumination | Planetary Geodesy Data Archive, NASA Goddard (M. Barker, E. Mazarico, G. Neumann, S. Bertone) | which site DEM version to cite; per-cell error use; whether the shape-from-shading DEMs are tied to the same grid; advice on a `MOON_ME` to ILuRF path for their products | https://pgda.gsfc.nasa.gov/ | yes: data are open; a short, specific e-mail is normal |
| NAC images, mosaics, stereo DTMs; ShadowCam | LROC and ShadowCam teams, Arizona State University | which controlled products cover our site; geolocation of ShadowCam frames against LOLA | https://lroc.im-ldi.com/ ; https://shadowcam.im-ldi.com/ | yes for questions; no for custom products |
| Map standards, LGRS grid, software (ISIS) | USGS Astrogeology Science Center | LGRS reference code and test vectors; review of our grid and datum definition | https://www.usgs.gov/centers/astrogeology-science-center ; https://doi.org/10.3133/tm11E1 | yes: they publish and answer; the grid is meant for outside use |
| Frames and ephemerides | NAIF, JPL | nothing to ask; use the kernels and give credit | https://naif.jpl.nasa.gov/ | yes (self-service) |
| International Lunar Reference Frame | IAG/IAU Joint Working Group 1.1.3 (chair A. Fienga); ILuRS product centre | transformation parameters and their software; how surface users should cite a frame version | https://ilurs-6e772d.gitlab.io/ [ILURS-WEB] | yes: products and software are public |
| LunaNet reference system (AD5) | NASA SCaN with ESA and JAXA | when AD5 is public; whether a surface-map message is planned | https://www.nasa.gov/directorates/somd/space-communications-navigation-program/lunanet-interoperability-specification/ | partly: comments are taken from vendors; we can only read |
| Multi-rover map database in flight hardware | JPL CADRE team (J.-P. de la Croix, F. Rossi, M. Saboia) | whether the MoonDB merge policy and test maps can be shared; flight results after IM-3 | https://www.jpl.nasa.gov/missions/cadre/ | possible after the flight; papers are open now |
| Multi-robot SLAM software | MIT (Kimera-Multi), MISTLab at Polytechnique Montreal (Swarm-SLAM), Vision for Robotics Lab at ETH Zurich (COVINS), HKUST (D2SLAM) | open code and datasets; a joint test on analogue data | https://github.com/MISTLab/Swarm-SLAM (others: see the papers) | yes: code is open; a student project is the usual form |
| Two-robot analogue data | LAAS-CNRS (Erfoud); DLR Robotics and Mechatronics (S3LI, MADMAX) | licence terms for the Erfoud and MADMAX sets; ground-truth files | https://sites.laas.fr/projects/erfoud-dataset ; https://www.dlr.de/en/rm/research/publications-and-downloads/datasets | yes |

---

## G. Open questions, risks, differences from existing notes, and sources

### Open questions and risks

1. AD5 is not public (11 November 2026). If it fixes ILuRF (PA) for navigation messages, every surface
   receiver must convert to ME, and the conversion version becomes part of our protocol. Risk: a 660 m error
   from one unconverted position. Mitigation: mandatory `frame_id`, and a plausibility test against the map.
2. Two polar grids exist (LOLA, scale 1; USGS LPS, scale 0.994 with a 500 km false origin). A partner who
   sends "polar stereographic metres" without saying which is off by 0.6 % plus the offset.
3. The orbital model's detail is about 20 m. Slopes computed on the 5 m grid are slopes of an interpolated
   surface. Rover-scale hazards are not in any public product; our hazard layer is entirely rover-made.
4. No field result exists for multi-rover mapping on the Moon. CADRE has not flown. All accuracy numbers in
   B3 are from Earth, most with lidar or in good light.
5. Visual matching between rovers under polar light is untested at scale; our design leans on markers and
   ranges. If a base cannot place three surveyed markers early, the datum is weak.
6. The acceptance limits in C6 (2 m, 1 m, two passes) are our choices, not measured optima. They need a
   sweep in the simulator.
7. Owners may refuse even derived cells for commercial reasons (a hazard map shows where a competitor
   drives). The market part should say whether contributing is paid or required.
8. Licence gaps: no licence text on the PGDA pages, the POLAR pages, MADMAX or Erfoud. For a paper this is
   fine with citation; for redistribution on our web site ask first.
9. Compression figures for rover-made rasters are assumed; the measured ones are for smooth orbital data.

### Differences from existing notes and from the simulator's terrain code

- `lunarsim/terrain.py` and `tools/comms/earth_link.py` are consistent with this note on the frame
  (`MOON_ME`, 1737.4 km, polar stereographic with scale 1, grid bearings). No change needed there.
- `terrain.py` lists six site names; the PGDA page has 27 site DEMs, among them "SL3: Connecting ridge
  extension" next to our tile [PGDA78].
- The flag "Measured" on the 5 m DEM is right for height but can mislead for detail: about 90 % of cells are
  interpolated and the effective resolution is about 20 m [PGDA78, BARKER23]. Slope statistics from the 5 m
  grid understate short slopes.
- Not in the existing note: 5 m shape-from-shading DEMs of the 13 Artemis III regions [PGDA104], the LOLA
  `MOON_PA` grid [PGDA95], the deep-learning product [PGDA106], the USGS LGRS grid [USGS-TM], the ILuRF.
- SLDEM2015 ends at 60 S [PGDA54]; it should not appear in a list of polar products.
- `00_inputs_from_owner.md` gives AI4Mars as about 35,000 images and 326,000 labels (the 2021 paper); the
  current release (v0.6) has about 50,000 images and 425,000 labels, with Perseverance, under CC BY 4.0
  [AI4MARS].
- `00_inputs_from_owner.md` expects OpNav images to test "horizon and landmark navigation". The archive
  supports horizon (limb) work only: the Moon is 70 to 328 pixels wide and there are no OpNav images within
  22 hours of closest approach. It also expects crew images of "the south polar region under known lighting"
  to check the illumination model: the pole was on the limb at 105 to 130 m per pixel, so only very large
  shadows can be checked.
- The Artemis II lead-node page says the SPICE bundle is delayed; it is in fact online at NAIF.

### Could not verify (what was tried)

- IAU working group report, full text (Springer returned the landing page only).
- NGA lunar reference system page (HTTP 403). LNIS AD5 (not found on the NASA page).
- Chandrayaan-2 OHRC at PRADAN (host did not resolve); USGS Chandrayaan-2 page (HTTP 403).
- KPLO LUTI at KARI KPDS (page text not readable). Katwijk beach rover dataset of ESA
  (https://robotics.estec.esa.int/datasets/katwijk-beach-11-2015/): the certificate did not match the host.
- Diviner polar product cell size; NAC DTM accuracy figures (Henriksen et al. 2017 not opened).
- Shapiro et al. CRDT report (bot wall at HAL). DLR ARCHES paper (closed access).
- Zenodo record of the shape-from-shading DEMs (licence and sizes). Park et al. 2021 (DE440 paper) and
  Mazarico et al. 2011, Barker et al. 2021 as papers: read only through the PGDA pages and the kernel.
- IM-3 schedule: from Wikipedia (edited 9 November 2026), not from NASA or Intuitive Machines directly.

### Sources (all opened in this session, 11 November 2026)

Frames and standards

- [NAIF-FK] NAIF/JPL (N. Bachman), "SPICE Lunar Reference Frame Specification Kernel", `moon_de440_250416.tf`,
  16 April 2025. https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf
- [NAIF-PCK] NAIF, generic PCK readme (binary lunar PCKs). https://naif.jpl.nasa.gov/pub/naif/generic_kernels/pck/aareadme.txt
- [LROWP08] LRO Project and LGCWG, "A Standardized Lunar Coordinate System for the Lunar Reconnaissance
  Orbiter and Lunar Datasets", White Paper, Version 5, 1 October 2008.
  https://science.nasa.gov/wp-content/uploads/2024/01/luncoordwhitepaper-10-08.pdf
- [PAC24] R. Fergason, B. Archinal, "Lunar Reference Frame Update to the PAC", 10 July 2024.
  https://science.nasa.gov/wp-content/uploads/2024/08/22-lunar-reference-frame-update-pac-july2024.pdf
- [ACR24] NASA, "Lunar Reference Frames", 2024 Moon to Mars Architecture Concept Review white paper.
  https://www.nasa.gov/wp-content/uploads/2024/12/acr24-lunar-reference-frames.pdf
- [LNIS5] NASA, "LunaNet Interoperability Specification Document", Version 5, 29 January 2025.
  https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-interoperability-specification-v5-baseline.pdf
- [LNIS-PAGE] NASA SCaN, LunaNet Interoperability Specification page.
  https://www.nasa.gov/directorates/somd/space-communications-navigation-program/lunanet-interoperability-specification/
- [ICG26-RF] C. Gramling and others, "Reference Frames for Interoperability within LunaNet", ICG Cislunar PNT
  Workshop, Vienna, 11 February 2026. https://ioag.org/Cislunar2026/Wednesday/04a%20Lunar%20Reference%20Frame/0930%20ICG%202026%20Workshop-%20Day2%200930-0950-Reference%20Frames%20v1.pdf
- [ICG26-IAU] S. Stewart (IAU Commission A3), "Lunar Reference Frame Standards", 11 February 2026.
  https://ioag.org/Cislunar2026/Wednesday/04a%20Lunar%20Reference%20Frame/0900%20ICG-IOAG%202026%20IAU%20Update%20Lunar%20Standards.pdf
- [ILRF25] K. Sosnica, A. Fienga, D. Pavlov, N. Rambaux, R. Zajdel, "Definition and Realization of the
  International Lunar Reference Frame", arXiv:2510.15484, October 2025. https://arxiv.org/abs/2510.15484
- [ILURS26] A. Fienga on behalf of IAG JWG 1.1.3, "The International Lunar Reference System",
  arXiv:2607.27762, 30 July 2026. https://arxiv.org/abs/2607.27762
- [ILURS-WEB] ILuRS product centre (temporary site). https://ilurs-6e772d.gitlab.io/
- [USGS-TM] M. McClernan and others, "Lunar grid systems, coordinate systems, and map projections for the
  Artemis missions and lunar surface navigation", USGS Techniques and Methods 11-E1, 2025.
  https://pubs.usgs.gov/tm/11/e1/tm11E1.pdf (doi:10.3133/tm11E1)
- [WGCCRE15] B. Archinal and others, "Report of the IAU Working Group on Cartographic Coordinates and
  Rotational Elements: 2015", Celest. Mech. Dyn. Astron. 130:22, 2018 (landing page and references only).
  https://doi.org/10.1007/s10569-017-9805-5

Terrain and image products

- [PGDA54], [PGDA69], [PGDA78], [PGDA81], [PGDA90], [PGDA92], [PGDA95], [PGDA104], [PGDA106]: NASA Goddard
  Planetary Geodesy Data Archive, product pages of those numbers (54 SLDEM2015, M. Barker; 69 Lunar Polar
  Illumination, E. Mazarico; 78 High-Resolution LOLA Topography for Lunar South Pole Sites, M. Barker;
  81 South Pole LOLA DEM Mosaic, M. Barker; 90 A New View of the Lunar South Pole from LOLA, M. Barker;
  92 Large-scale Lunar Elevation Models to Support Optical Navigation, S. Bertone; 95 LOLA MOON_PA gridded
  dataset, G. Neumann, 2024; 104 Enhanced Topography Models for Selected Lunar South Pole Regions with
  Shape-from-Shading, S. Bertone; 106 Improving Lunar Topography with Deep Learning Schrodinger Bridges,
  M. Repasky and others). https://pgda.gsfc.nasa.gov/products/NN with NN the number.
- [PGDA-README] LOLA 5 m site data readme. https://pgda.gsfc.nasa.gov/data/LOLA_5mpp/README
- [BARKER23] M. Barker and others, "A New View of the Lunar South Pole from the Lunar Orbiter Laser Altimeter
  (LOLA)", Planet. Sci. J. 4:183, 2023, CC BY 4.0. https://doi.org/10.3847/PSJ/acf3e1
- [LOLA-PDS] PDS Geosciences Node, LRO LOLA page (Release 67, 15 September 2026).
  https://pds-geosciences.wustl.edu/missions/lro/lola.htm
- [LOLA-GDR] G. Neumann, LOLA GDR data set catalogue file.
  https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/catalog/gdr_ds.cat
- [LROC-SIS] LROC team, "LROC RDR Data Products Software Interface Specification", Version 1.6,
  22 August 2020. https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DOCUMENT/RDRSIS.PDF
- [LROC-SPEC] LROC, instrument specifications. https://lroc.im-ldi.com/about/specs
- [SHADOWCAM] ShadowCam, "About" and "Archive" pages. https://shadowcam.im-ldi.com/about ; https://shadowcam.im-ldi.com/archive
- [DIVINER-PDS] PDS Geosciences Node, LRO Diviner page. https://pds-geosciences.wustl.edu/missions/lro/diviner.htm

Artemis II

- [A2-GUIDE] Artemis II Lunar Science Team, "Artemis II Lunar Science Data User Guide", Version 1.0,
  7 October 2026, doi:10.17189/dtpt-2857 (local copy in `sources/artemis2_data_user_guide.txt`).
  https://pds-geosciences.wustl.edu/artemis2/urn-nasa-pds-artemis2_mission/document/artemis2_data_user_guide.pdf
- [A2-PDS] PDS Geosciences Node, Artemis II page and Mission bundle directories.
  https://pds-geosciences.wustl.edu/missions/artemis2/index.htm
- [A2-ATLAS] PDS Imaging Node, Atlas search index and archive (bundles `artemis2_crew_camera`,
  `artemis2_orion_camera`, `artemis2_mission_audio`), queried 11 November 2026; 397 OpNav PDS4 labels read.
  https://pds-imaging.jpl.nasa.gov/tools/atlas/archive-explorer?mission=artemis2
- [A2-SPICE] A. Bailey, B. Semenov, "Artemis II Mission SPICE Bundle", NAIF, doi:10.17189/7ezn-0294
  (`spiceds_v001.html`, meta-kernel, instrument kernels, trajectory kernel read).
  https://naif.jpl.nasa.gov/pub/naif/pds/pds4/artemis2/artemis2_spice/

Multi-robot mapping and data structures

- [MOONDB] M. Saboia and others, "CADRE MoonDB: Distributed Database for Multi-Robot Information-Sharing and
  Map-Merging for Lunar Exploration", MASSpace workshop at AAMAS 2024, CC BY 4.0.
  https://mas-space.github.io/aamas2024ws/pdfs/masspace2024-5.pdf
- [CADRE25] G. Rabideau and others, "Multi-Robot Cooperative Autonomy on the Moon: the CADRE Technology
  Demonstration Mission", ASTRA 2025. https://ai.jpl.nasa.gov/public/documents/papers/CADRE-ASTRA-2025-Extended-Abstract.pdf
- [IM3-WIKI] Wikipedia, "IM-3" (edited 9 November 2026; secondary source). https://en.wikipedia.org/wiki/IM-3
- [LAMP2] Y. Chang, K. Ebadi and others, "LAMP 2.0", IEEE RA-L 2022. https://arxiv.org/abs/2205.13135
- [KM22] Y. Tian and others, "Kimera-Multi", IEEE T-RO 2022. https://arxiv.org/abs/2106.14386
- [KM23] Y. Tian and others, "Resilient and Distributed Multi-Robot Visual SLAM: Datasets, Experiments, and
  Lessons Learned", 2023. https://arxiv.org/abs/2304.04362
- [SWARM] P.-Y. Lajoie, G. Beltrame, "Swarm-SLAM", 2023. https://arxiv.org/abs/2301.06230
- [DOOR] P.-Y. Lajoie and others, "DOOR-SLAM", IEEE RA-L 2020. https://arxiv.org/abs/1909.12198
- [COVINS] P. Schmuck and others, "COVINS", 2021. https://arxiv.org/abs/2108.05756
- [D2SLAM] H. Xu and others, "D2SLAM", 2024. https://arxiv.org/abs/2211.01538
- [CIES18] T. Cieslewski, S. Choudhary, D. Scaramuzza, "Data-Efficient Decentralized Visual SLAM", ICRA 2018.
  https://arxiv.org/abs/1710.05772
- [DGS] S. Choudhary and others, "Distributed Mapping with Privacy and Communication Constraints", IJRR 2017.
  https://arxiv.org/abs/1702.03435
- [DPGO] Y. Tian and others, "Distributed Certifiably Correct Pose-Graph Optimization", 2021.
  https://arxiv.org/abs/1911.03721
- [PCM] J. Mangelson and others, "Pairwise Consistent Measurement Set Maximization for Robust Multi-robot Map
  Merging", ICRA 2018. https://robots.engin.umich.edu/publications/jmangelson-2018a.pdf
- [MERKLE] H. Sanjuan and others, "Merkle-CRDTs: Merkle-DAGs meet CRDTs", 2020. https://arxiv.org/abs/2004.00107

Datasets

- [AI4MARS] R. Swan, M. Ono, D. Atha, "AI4Mars", v0.6, Zenodo, 2022. https://zenodo.org/records/15995036
- [POLAR] U. Wong and others, "POLAR Stereo Dataset", NASA Ames, 2017. https://ti.arc.nasa.gov/dataset/IRG_PolarDB/
- [POLARTRAV] NASA Ames, "POLAR Traverse Dataset", downloads page. https://ti.arc.nasa.gov/dataset/PolarTrav/downloads.html
- [S3LI] DLR, S3LI datasets page and Etna download page.
  https://www.dlr.de/en/rm/research/publications-and-downloads/datasets/s3li-datasets ; https://datasets.arches-projekt.de/s3li_dataset/
- [MADMAX] DLR, MADMAX page and download page.
  https://www.dlr.de/en/rm/research/publications-and-downloads/datasets/marokko-navigations-tests ; https://datasets.arches-projekt.de/morocco2018/
- [ERFOUD] S. Lacroix and others, "The Erfoud dataset", LAAS-CNRS (ASTRA paper listed on the page).
  https://sites.laas.fr/projects/erfoud-dataset/sites.laas.fr/projects/erfoud-dataset/index.html
- [DEVON] P. Furgale and others, "The Devon Island Rover Navigation Dataset", IJRR 2012.
  https://asrl.utias.utoronto.ca/datasets/devon-island-rover-navigation/
- [LUSNAR] J. Liu and others, "LuSNAR", arXiv:2407.06512, and repository readme.
  https://arxiv.org/abs/2407.06512 ; https://github.com/zqyu9/LuSNAR-dataset

Our own computations (scripts and downloaded files are in the session scratchpad, not in the repository):
the `MOON_ME` to `MOON_PA` displacements and the Artemis II ranges were computed with `spiceypy` and the
kernels in `.cache/comms/kernels` plus the archived Orion trajectory; tile sizes were measured on
`data/terrain/connecting_ridge/*.png` with PNG and zlib compression.
