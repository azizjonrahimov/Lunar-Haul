# P3 notes: reference list (draft 3 after referee round 2, 30 Oct 2026)

Entries run to the next blank line; a paragraph that starts with `NOTE:` after a blank line is an editorial note the
build does not render (build_p3.py references() matches only lines that start with `[n]`).

Sources: `research_notes/Lunar ATC/vehicles_comms_internals.md` (VCI), `multi_owner_allocation.md` (MOA),
`traffic_and_safety.md` (TAS), `paper/p1/NOTES.md` (P1) and `paper/p2/NOTES.md` (P2) for our own papers and the
entries they already carry, and `paper_writing_guide.md` (PWG). The grade is the research note's (High / Medium /
Low). Entries marked "to check" or "to add" are to be checked against the publisher's record before submission.
The earlier papers are [40, 41, 42] in P2's numbering and [56, 57, 58] here; the companion papers P1 and P2 are
[60, 61].

[1] NASA. News release on Lunar Terrain Vehicle Phase 1 task orders, 26-27 May 2026, https://www.nasa.gov/news-release/nasa-provides-update-on-moon-base-rovers-landers-missions/; progress update 20-21 October 2026, https://www.nasa.gov/missions/moon-base/nasa-provides-progress-update-on-moon-base-rovers/ (VCI, High; also the MoonFall award)
[2] Astrolab. FLEX rover page. https://www.astrolab.space (VCI, High as a company claim)
[3] Lunar Outpost. Rover family page (MAPP, MAPP-Ultra, HL-MAPP). https://lunaroutpost.com/rovers (VCI, High as a company claim)
[4] Payload Space. "Lunar Outpost closes $30M Series B, unveils new rover." 8 May 2026. https://payloadspace.com/lunar-outpost-closes-30m-series-b-unveils-new-rover/ (VCI, Medium)
[5] NASA. *Lunar Mobility Drivers and Needs*. Architecture Concept Review 2024 white paper. https://www.nasa.gov/wp-content/uploads/2024/06/acr24-lunar-mobility-drivers-and-needs.pdf (VCI, High)
[6] NASA. *Lunar Surface Cargo*. Architecture Concept Review 2024 white paper. https://www.nasa.gov/wp-content/uploads/2024/06/acr24-lunar-surface-cargo.pdf (VCI, High)
[7] Satnews, 27 May 2026; Interesting Engineering; DroneXL, 28 May 2026. Press reports on the NASA/JPL MoonFall hopping drones (about 250 kg wet, about 50 km of coverage per drone, 14 days of hops). https://satnews.com/2026/05/27/firefly-aerospace-wins-75-million-nasa-jpl-moonfall-subcontract-to-deliver-drones-to-the-moons-south-pole/ (VCI, Medium; secondary)
[8] Intuitive Machines. Micro-Nova hopper. LPSC 2024 abstract 1931, https://www.hou.usra.edu/meetings/lpsc2024/pdf/1931.pdf; product page https://www.intuitivemachines.com/micro-nova (VCI, High)
[9] W. Bluethmann. VIPER mobility hardware, LSIC 2024 technology infusion panel. NASA, November 2024. NTRS 20240013903. (VCI, High; full title to add)
[10] NASA JPL. CADRE mission page. https://www.jpl.nasa.gov/missions/cadre (VCI, High; band and range not public; the rate is public, see [28])
[11] Gunter's Space Page. Blue Moon MK1, 15 April 2026. https://space.skyrocket.de/doc_sdat/blue-moon.htm; Blue Origin. (VCI, High/Medium)
[12] NASA. "NASA JPL testing readies Voyager Technologies lander for Moon mission." 13 October 2026. https://nasa.gov/missions/moon-base/nasa-jpl-testing-readies-voyager-technologies-lander-for-moon-mission (VCI, High)
[13] Firefly Aerospace. Blue Ghost. https://fireflyspace.com/blue-ghost; NASASpaceflight, January 2025. (VCI, High)
[14] ESA. "Argonaut lunar lander family grows." https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Argonaut_lunar_lander_family_grows; Thales Alenia Space press release, 30 January 2025. (VCI, High/Medium)
[15] NASA. *LunaNet Interoperability Specification*, version 5, 29 January 2025. https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-interoperability-specification-v5-baseline.pdf (VCI, High)
[16] M. C. Scardelletti et al. "Lunar Surface Network Relay Terminal: A Lunar Communications Platform." ICSSC 2023. NTRS 20230013361. https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf (VCI, High; full author list and title to add)
[17] Nokia. "Nokia's cellular network ready for Moon as Intuitive Machines completes final lunar lander installation." 7 January 2025. https://www.nokia.com/about-us/news/releases/2025/01/07/; Converge Digest, 11 March 2025; Fierce Network; Mobile World Live, March 2025 (the outcome on IM-2). (VCI, Medium: press as summarised; the primary page returned HTTP 403)
[18] Astrobotic. *Lunar Landers Payload User's Guide*, 2021. https://science.nasa.gov/wp-content/uploads/2023/11/astrobotic-lunar-landers-pug.pdf (VCI, High)
[19] J. Esper, G. Heckler, J. Verville, G. Ryden. "NASA's Lunar Communications Relay and Navigation Systems (LCRNS)." SpaceOps 2025. NTRS 20250003321. (P1 [38], High)
[20] ITU-R Recommendation P.526. *Propagation by diffraction*. https://www.itu.int/rec/R-REC-P.526/en (VCI, High for the method; the knife-edge values are Computed)
[21] S. U. Hwu, M. Upanavage, C. C. Sham. "Lunar Surface Propagation Modeling and Effects on Communications." NASA Johnson Space Center, 2008. NTRS 20080015374. https://ntrs.nasa.gov/citations/20080015374; Johnson, Eckman, Swank, Zemba. "RF Metrology of Lunar Highlands Regolith Simulant NU-LHT-2M." NASA Glenn Research Center, 2023. NTRS 20230013296. https://ntrs.nasa.gov/citations/20230013296 (VCI, High)

NOTE: [21] titles added on 11 Nov 2026 from the source list of `research_notes/Lunar Rover Interaction Protocol/03_comms_protocol_security.md` (G4, [HWU08] and [GRC23], both opened on that date); the Hwu initials are the VCI note's, the Glenn authors' initials are in neither note. [21] is now also the source cited for the flat-ground two-ray law of Section 4.2 (note 03 Q2 and E1: the JSC model shows the 1/R^4 law and its independence of frequency at long range; it is a model, not a lunar measurement).

[22] NASA. Delay/Disruption Tolerant Networking page. https://www.nasa.gov/communicating-with-missions/delay-disruption-tolerant-networking/ (VCI, High)
[23] N. Ashby, B. Patla. "A Relativistic Framework to Establish Coordinate Time on the Moon and Beyond." *Astronomical Journal* 168:3, 2024. arXiv:2402.11150, https://arxiv.org/pdf/2402.11150; APS Physics summary https://physics.aps.org/articles/v17/140 (VCI, High; title from LRIP note 01, where the preprint was opened)
[24] UNOOSA ICG Working Group B, Lunar PNT, June 2024 slides (draft lunar UHF band 390-405 MHz). https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_02_01.pdf (VCI, Medium; draft)
[25] A. Krawciw et al. "Sharing the Load: Autonomous Multi-Rover Cargo Transport." arXiv:2510.18766v2, 2026. (VCI/MOA, High; the 13.8 kB/s convoy figure is quoted in MOA section 5)
[26] G. Rabideau, J. Russino, A. Branch, N. Dhamani, T. Stegun Vaquero, J.-P. de la Croix, F. Rossi. "Multi-Robot Cooperative Autonomy on the Moon: The CADRE Technology Demonstration Mission." ASTRA 2025. https://ai.jpl.nasa.gov/public/documents/papers/CADRE-ASTRA-2025-Extended-Abstract.pdf (MOA, High)
[27] K. Albee et al. "Lunar Leader: Persistent, Optimal Leader Election for Multi-Agent Exploration Teams." MASSpace 2024; JPL CADRE AAMAS slides, https://ai.jpl.nasa.gov/public/documents/presentations/CADRE-AAMAS-Slides.pdf (MOA, Medium / High)
[28] M. Saboia, Rossi, Nguyen, Lim, Aguilar, de la Croix. "CADRE MoonDB: Distributed Database for Multi-Robot Information-Sharing and Map-Merging for Lunar Exploration." MASSpace 2024. https://ai.jpl.nasa.gov/public/documents/papers/MoonDB-MASSpace-paper.pdf (MOA, Medium; title, authors and URL from the source list of the LRIP note 04, entry C5, read in part; the co-authors' initials are not in the note; source of "a minimum of 1Mbps of aggregate bandwidth" in Sections 1 and 2.2)
[29] R. B. Myerson, M. A. Satterthwaite. "Efficient mechanisms for bilateral trading." *Journal of Economic Theory* 29(2):265-281, 1983. (MOA, Medium)
[30] W. Vickrey. "Counterspeculation, auctions, and competitive sealed tenders." *Journal of Finance* 16(1):8-37, 1961. (MOA, Low; standard result, not re-read; title to check)
[31] L. M. Ausubel, P. Milgrom. "The Lovely but Lonely Vickrey Auction." In P. Cramton, Y. Shoham, R. Steinberg (eds.), *Combinatorial Auctions*, MIT Press, 2006, pp. 17-40. (MOA, High)
[32] R. P. McAfee. "A dominant strategy double auction." *Journal of Economic Theory* 56(2):434-450, 1992. doi:10.1016/0022-0531(92)90091-U (MOA, Medium)
[33] N. Nisan, A. Ronen. "Algorithmic mechanism design." *Games and Economic Behavior* 35(1-2):166-196, 2001. (MOA, Low; not re-read)
[34] P. Friedrich, Y. Zhang, M. Curry, L. Dierks, S. McAleer, J. Li, T. Sandholm, S. Seuken. "Scalable Mechanism Design for Multi-Agent Path Finding." IJCAI 2024. arXiv:2401.17044 (MOA, Medium)
[35] F. Cruijssen, M. Cools, W. Dullaert. "Horizontal cooperation in logistics: opportunities and impediments." *Transportation Research Part E* 43(2):129-142, 2007; joint route planning savings in *IJPDLM* 37(4):287-304, 2007. (MOA via notes/03, Medium-High; titles to confirm)
[36] M. Gansterer, R. F. Hartl. "Collaborative vehicle routing: A survey." *European Journal of Operational Research* 268(1):1-12, 2018. (MOA, Medium-High; title to confirm)
[37] L. S. Shapley. "A value for n-person games." In *Contributions to the Theory of Games II*, Princeton University Press, 1953, pp. 307-317.

NOTE: [37] is not in the research notes; it is the standard reference for the Shapley value and is to be verified against the publisher's record before submission.

[38] S. Berger, C. Bierwirth. "Solutions to the request reassignment problem in collaborative carrier networks." *Transportation Research Part E* 46(5):627-638, 2010. (MOA, Medium)
[39] D. Kondor, I. Bojic, G. Resta, F. Duarte, P. Santi, C. Ratti. "The cost of non-coordination in urban on-demand mobility." *Scientific Reports* 12:4669, 2022. doi:10.1038/s41598-022-08427-2 (MOA, High)
[40] T. Séjourné, S. Samaranayake, S. Banerjee. "The Price of Fragmentation in Mobility-on-Demand Services." *Proc. ACM Meas. Anal. Comput. Syst.* 2(2), 2018. arXiv:1711.10963 (MOA, High)
[41] Open-RMF. "The State of Open-RMF." ROSCon 2024. https://roscon.ros.org/2024/talks/The_State_of_Open-RMF.pdf ; https://github.com/open-rmf/rmf_traffic (MOA, Medium)
[42] S. Koenig, C. Tovey, M. Lagoudakis, V. Markakis, D. Kempe, P. Keskinocak, A. Kleywegt, A. Meyerson, S. Jain. "The Power of Sequential Single-Item Auctions for Agent Coordination." AAAI 2006, pp. 1625-1629. (P1 [2], High)
[43] H.-L. Choi, L. Brunet, J. P. How. "Consensus-Based Decentralized Auctions for Robust Task Allocation." *IEEE Transactions on Robotics* 25(4):912-926, 2009. (P1 [4], Medium)
[44] M. Otte, M. J. Kuhlman, D. Sofge. "Auctions for multi-robot task allocation in communication limited environments." *Autonomous Robots* 44(3-4):547-584, 2020. (P1 [8], High)
[45] K. Dunlap, M. Hibbard, M. Mote, K. Hobbs. "Comparing run time assurance approaches for safe spacecraft docking." arXiv:2110.00447, 2021. (TAS, High; venue to check)
[46] K. L. Hobbs, M. L. Mote, M. C. L. Abate, S. D. Coogan, E. M. Feron. "Runtime assurance for safety-critical systems: An introduction to safety filtering approaches for complex control systems." *IEEE Control Systems Magazine* 43(2):28-65, 2023. doi:10.1109/MCS.2023.3234380 (TAS, High for the abstract)
[47] L. Sha. "Using simplicity to control complexity." *IEEE Software* 18(4):20-28, 2001. doi:10.1109/MS.2001.936213 (TAS, Medium)
[48] M. Alshiekh, R. Bloem, R. Ehlers, B. Könighofer, S. Niekum, U. Topcu. "Safe reinforcement learning via shielding." AAAI 2018, 32(1). arXiv:1708.08611 (TAS, High)
[49] K. Dresner, P. Stone. "A multiagent approach to autonomous intersection management." *Journal of Artificial Intelligence Research* 31:591-656, 2008. doi:10.1613/jair.2502 (TAS, High)
[50] P. Kopardekar, J. Rios, T. Prevot, M. Johnson, J. Jung, J. E. Robinson. "Unmanned Aircraft System Traffic Management (UTM) Concept of Operations." AIAA 2016-3292. NTRS 20190000370. (TAS, High; DOI to check)
[51] G. Swiney, A. Hernandez. *Lunar Landing and Operations Policy Analysis*. NASA Office of Technology, Policy, and Strategy, report 20220015973, 30 September 2022. (TAS, High)
[52] *The Artemis Accords: Principles for Cooperation in the Civil Exploration and Use of the Moon, Mars, Comets, and Asteroids*. Signed 13 October 2020. https://www.nasa.gov/wp-content/uploads/2022/11/Artemis-Accords-signed-13Oct2020.pdf (TAS, High)
[53] Kim, Li, Wang. "Lunar Surface Space Traffic Management: Considerations for Future Regulations." GLEX-2025, 11, IP, 15, x93808. https://iafastro.directory/iac/archive/browse/GLEX-2025/11/IP/93808/ (TAS/MOA, Medium)
[54] M. Saboia et al. "ACHORD: Communication-Aware Multi-Robot Coordination With Intermittent Connectivity." *IEEE Robotics and Automation Letters* 7(4):10184-10191, 2022. arXiv:2206.02245 (MOA, High)
[55] M. Tranzatto et al. "Team CERBERUS Wins the DARPA Subterranean Challenge: Technical Overview and Lessons Learned." *Field Robotics* 2, 2022. arXiv:2207.04914 (MOA, High)
[56] A. Rahimov. *Who Hauls the Habitat? A Verified Simulation Testbed, a Pooled Dispatch Marketplace and a Reference Design for Lunar Surface Logistics*. Preprint, version 2, October 2026. (P2 [40])
[57] A. Rahimov. *Where the Lander Lands: Landing Precision, Pad Standoff, Plume Keep-Out and Rover Autonomy Priced in Lunar Surface Logistics*. Preprint, version 3, October 2026. (P2 [41])
[58] A. Rahimov. *What Earth's Horizon Costs a Lunar Base: Terrain-Masked Communication Windows in South-Pole Cargo Logistics*. Preprint, October 2026. (P2 [42])
[59] Pre-registration, paper/atc/PREREG.md in the repository, written 27 October 2026, with dated changes. (P2 [43])
[60] A. Rahimov. *Working Together Without Earth: Job Sharing, Team Lifts and Learned Bidding Among Lunar Robots of Different Owners*. Preprint, October 2026; revised November 2026 (companion paper P1).
[61] A. Rahimov. *Rules of the Road on the Moon and Mars: Traffic Rules for Surface Robots of Different Owners, Checked and Priced*. Preprint, October 2026; revised November 2026 (companion paper P2).
[62] B. Efron, R. J. Tibshirani. *An Introduction to the Bootstrap*. Chapman & Hall, 1993. (P2 [55])
[63] NASA Space Math. Horizon distance on a sphere. https://spacemath.gsfc.nasa.gov/Geometry/3Page19.pdf (VCI, High; the lunar values are Computed in the note)
[64] NSSDC. Apollo Lunar Roving Vehicle. https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html (VCI, High)
[65] S. Pan, D. Trentesaux, E. Ballot, G. Q. Huang. "Horizontal collaborative transport: survey of solutions and practical implementation issues." *International Journal of Production Research* 57(15-16):5340-5361, 2019. doi:10.1080/00207543.2019.1574040 (MOA, Medium)

NOTE: [65] is cited in 2.4 since draft 2 (the survey of 120 studies). Draft 2 also cites [22] in 2.2 (DTN operational, no surface demonstration) and [51], [52], [53] in 2.1 (the policy frame); every entry is now cited.

NOTE: draft 3 (referee round 2, finding 28): the spaces before semicolons in [1], [8], [11], [13], [14], [17], [21] are removed; [59] no longer carries backticks or the "cite by tag" remark; [53]'s authors' initials are not in the research notes (MOA section 6 and TAS give "Kim (ispace), Li, Wang (Univ. of Newcastle, Australia)" without initials), so the entry stays as it is until the GLEX record is checked; [7] is three press names and keeps its semicolons.

[66] J. Rios et al. *UAS Service Supplier Network Performance: Results and Analysis from Flight Testing Multiple USS Providers in NASA's TCL4 Demonstration*. NASA/TM-2020-220462, January 2020. https://ntrs.nasa.gov/citations/20200000531 (TAS, High)

NOTE: entries [67] to [114] were added in the revision of 11 Nov 2026 (Phase 6). Each is a source that one of the four research notes of `research_notes/Lunar Rover Interaction Protocol/` lists as opened on that date; the tag at the end of an entry (LRIP-01 to LRIP-04 and the note's own key) is not rendered. Sources the notes mark UNVERIFIED are not cited. Secondary sources are named as such in the entry and in the text. Authors' initials are given only where the notes have them.

[67] Pre-registration of the Phase 6 experiments, paper/atc/PREREG6.md in the repository, written 11 November 2026, with dated changes. (LRIP, own work)
[68] Lunar Rover Interaction Protocol, research notes 01 to 04 (positioning and time; shared map and coordinates; communication, protocol and security; coordination and market), research_notes/Lunar Rover Interaction Protocol/ in the repository, 11 November 2026: the design, its parameters with their sources, and what could not be verified. (LRIP, own work)
[69] Maimone, Cheng, Matthies. "Two Years of Visual Odometry on the Mars Exploration Rovers." *Journal of Field Robotics*, 2007. https://robotics.jpl.nasa.gov/media/documents/rob-06-0081.R4.pdf (LRIP-01 MAIM07)
[70] Daftry et al. "LunarNav: Crater-based Localization for Long-range Autonomous Lunar Rover Navigation." IEEE Aerospace Conference 2023. https://arxiv.org/pdf/2301.01350 (LRIP-01 DAF23)
[71] Atha et al. "ShadowNav: Autonomous Global Localization for Lunar Navigation in Darkness." 2024. https://arxiv.org/pdf/2405.01673 (LRIP-01 ATHA24)
[72] Helmick et al. "Slip-Compensated Path Following for Planetary Exploration Rovers." *Advanced Robotics*, 2006. https://robotics.jpl.nasa.gov/media/documents/advanced_robotics_2006.pdf (LRIP-01 HELM06)
[73] NASA JPL. "NASA's Perseverance Now Autonomously Pinpoints Its Location on Mars." 18 February 2026. https://www.jpl.nasa.gov/news/nasas-perseverance-now-autonomously-pinpoints-its-location-on-mars/; J. Nash et al. "Censible: A Robust and Practical Global Localization Framework for Planetary Surface Missions." ICRA 2024. https://www-robotics.jpl.nasa.gov/media/documents/2024_Global_Localization_ICRA.pdf; J. Nash, V. Verma et al. "A Software-Based Approach to Radiation Mitigation for Planetary Missions." IEEE Aerospace Conference 2026. https://www-robotics.jpl.nasa.gov/media/documents/2026_Global_Localization_Memory_Workaround_IEEE_Aero__final.pdf (LRIP-01 JPL26, NASH24, NASH26)
[74] Dai, Casadesus Vila, Gao. "Visual SLAM with DEM Anchoring for Lunar Surface Navigation." 2026. https://arxiv.org/pdf/2603.17229 (LRIP-01 DAI26)
[75] Janicijevic et al. "Demo: Small PLaNS Towards Mars: Exploiting Ultra-wideband for Self-localizing Rover Navigation." EWSN 2018. https://www.ewsn.org/file-repository/ewsn-2018/199_200_janicijevic.pdf; A. Nuechter et al. "UWB Anchor Based Localization of a Planetary Rover." i-SAIRAS 2024. https://arxiv.org/pdf/2504.07658 (LRIP-01 PLANS18, NUCH24)
[76] M. Barker et al. "Improved LOLA Elevation Maps for South Pole Landing Sites: Error Estimates and Their Impact on Illumination Conditions." *Planetary and Space Science*, 2021. https://ntrs.nasa.gov/api/citations/20205009660/downloads/Mike%20Barker_%20Paper_%20Improved%20Lola.pdf (LRIP-01 BARK21)
[77] C. Gramling, Crenshaw, Murata, Swinden, Melman, Stallo, Ventura-Traveset. "Towards LunaNet Lunar Augmented Navigation Service (LANS) Interoperability Demonstration and Monitoring." SpaceOps 2025. https://ntrs.nasa.gov/api/citations/20250003163/downloads/LANS%20Interop%20Demo-SpOps2025%20ID429%20v4Final.pdf (LRIP-01 INTEROP25)
[78] C. Gramling, Crenshaw. "NASA's LunaNet: Lunar Communications and PNT." UN ICG Working Group B, 25 June 2024. https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_01_02.pdf (LRIP-01 GRAM24)
[79] ESA. "ESA's Moonlight programme: Pioneering the path for lunar exploration." 15 October 2024. https://www.esa.int/Applications/Connectivity_and_Secure_Communications/ESA_s_Moonlight_programme_Pioneering_the_path_for_lunar_exploration; J. Ventura-Traveset. "Moonlight Navigation Services" (slides), 2024. https://bsgn.esa.int/wp-content/uploads/2024/02/07-Moonlight_LCNS_S4I_2024_Javier-Ventura-Traveset.pdf (LRIP-01 ESA24, ML24)
[80] M. Murata. "Japan LNSS and Towards LunaNet LANS Interoperability Demonstration." ICG-IOAG Cislunar PNT Workshop, 10 February 2026. https://ioag.org/Cislunar2026/Tuesday/02%20Lunar/1125%20LNSS_LANS_demo_Cislunar_PNT_Workshop.pdf (LRIP-01 MUR26)
[81] Brinkmann. "NASA expects one lunar launch this year, Moon Base manager says." *Aerospace America* (AIAA), 15 September 2026. https://aerospaceamerica.aiaa.org/nasa-expects-one-lunar-launch-this-year-moon-base-manager-says/ (LRIP-04 M3)
[82] Parker et al. "GNSS Reception at the Moon: First Results of the Lunar GNSS Receiver Experiment (LuGRE)." *NAVIGATION* 73(1), 2026. doi:10.33012/navi.756 (LRIP-01 LUGRE26; an open-access copy was read)
[83] Kopeikin, Kaplan. "Lunar Time in General Relativity." 2024. https://arxiv.org/pdf/2407.04862 (LRIP-01 KK24)
[84] Turyshev, Williams, Boggs, Park. "Relativistic Time Transformations Between the Solar System Barycenter, Earth, and Moon." 2024. https://arxiv.org/pdf/2406.16147 (LRIP-01 TUR25)
[85] White House Office of Science and Technology Policy. "Policy on Celestial Time Standardization in Support of the National Cislunar Science and Technology Strategy." 2 April 2024. https://bidenwhitehouse.archives.gov/wp-content/uploads/2024/04/Celestial-Time-Standardization-Policy.pdf (LRIP-01 OSTP24)
[86] Microchip. CSAC SA65 chip-scale atomic clock, data sheet (a copy was read). https://gps-world.biz/wp-content/uploads/2023/10/microchip-csac-sa65-1.pdf (LRIP-01 CSAC)
[87] ITU-T Recommendation G.8271/Y.1366. *Time and phase synchronization aspects of telecommunication networks*. 2020. (LRIP-01 G8271)
[88] NAIF, NASA JPL (N. Bachman). "SPICE Lunar Reference Frame Specification Kernel", moon_de440_250416.tf, 16 April 2025. https://naif.jpl.nasa.gov/pub/naif/generic_kernels/fk/satellites/moon_de440_250416.tf (LRIP-02 NAIF-FK)
[89] NASA. "Lunar Reference Frames." 2024 Moon to Mars Architecture Concept Review white paper. https://www.nasa.gov/wp-content/uploads/2024/12/acr24-lunar-reference-frames.pdf (LRIP-02 ACR24)
[90] M. Barker et al. "A New View of the Lunar South Pole from the Lunar Orbiter Laser Altimeter (LOLA)." *Planetary Science Journal* 4:183, 2023. https://doi.org/10.3847/PSJ/acf3e1; NASA Goddard Planetary Geodesy Data Archive, "High-Resolution LOLA Topography for Lunar South Pole Sites", https://pgda.gsfc.nasa.gov/products/78 (LRIP-02 BARKER23, PGDA78)
[91] A. Fienga on behalf of IAG Joint Working Group 1.1.3. "The International Lunar Reference System." arXiv:2607.27762, 30 July 2026. https://arxiv.org/abs/2607.27762; C. Gramling et al. "Reference Frames for Interoperability within LunaNet." ICG Cislunar PNT Workshop, Vienna, 11 February 2026. https://ioag.org/Cislunar2026/Wednesday/04a%20Lunar%20Reference%20Frame/0930%20ICG%202026%20Workshop-%20Day2%200930-0950-Reference%20Frames%20v1.pdf (LRIP-02 ILURS26, ICG26-RF)
[92] LROC team. "LROC RDR Data Products Software Interface Specification", version 1.6, 22 August 2020. https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DOCUMENT/RDRSIS.PDF; ShadowCam, "About" page, https://shadowcam.im-ldi.com/about; NASA Goddard Planetary Geodesy Data Archive, "Enhanced Topography Models for Selected Lunar South Pole Regions with Shape-from-Shading", https://pgda.gsfc.nasa.gov/products/104 (LRIP-02 LROC-SIS, SHADOWCAM, PGDA104)
[93] H. Sanjuan et al. "Merkle-CRDTs: Merkle-DAGs meet CRDTs." 2020. https://arxiv.org/abs/2004.00107 (LRIP-02 MERKLE)
[94] CCSDS. *Proximity-1 Physical Layer*, CCSDS 211.1-B-4, December 2013; *Proximity-1 Data Link Layer*, CCSDS 211.0-B-6, July 2020; *Proximity-1 Coding and Synchronization*, CCSDS 211.2-B-3, October 2019. https://public.ccsds.org/Pubs/211x1b4e1.pdf (LRIP-03 P1-PHY, P1-DLL, P1-CS)
[95] CCSDS. *Space Packet Protocol*, CCSDS 133.0-B-2, June 2020; *AOS Space Data Link Protocol*, CCSDS 732.0-B-4, October 2021; *Unified Space Data Link Protocol*, CCSDS 732.1-B-3, June 2024. https://public.ccsds.org/Pubs/133x0b2e2.pdf (LRIP-03 SPP, AOS, USLP)
[96] CCSDS. *Space Data Link Security*, CCSDS 355.0-B-2, July 2022; *SDLS Extended Procedures*, CCSDS 355.1-B-1, February 2020; *Cryptographic Algorithms*, CCSDS 352.0-B-2, August 2019. https://public.ccsds.org/Pubs/355x0b2.pdf (LRIP-03 SDLS, SDLS-EP, CRYPTO)
[97] CCSDS. *High Data Rate Wireless Proximity Network Communications*, CCSDS 883.0-B-2, May 2024. https://public.ccsds.org/Pubs/883x0b2.pdf (LRIP-03 WPN)
[98] IETF. RFC 9171, *Bundle Protocol Version 7*; RFC 9172 (BPSec); RFC 9173 (default security contexts); January 2022. https://www.rfc-editor.org/rfc/rfc9171.txt; CCSDS 734.2-B-1, the Bundle Protocol book for version 6, September 2015; CCSDS 734.3-B-1, *Schedule-Aware Bundle Routing*, July 2019. (LRIP-03 RFC9171, RFC9172, RFC9173, BP6, SABR)
[99] NIST Special Publication 800-38B (CMAC). https://doi.org/10.6028/NIST.SP.800-38B; NIST Special Publication 800-38D (GCM). https://nvlpubs.nist.gov/nistpubs/Legacy/SP/nistspecialpublication800-38d.pdf (LRIP-03 NIST38B, NIST38D)
[100] IETF. RFC 8032 (EdDSA); RFC 8949 (CBOR). https://www.rfc-editor.org/rfc/rfc8032.txt (LRIP-03 RFC8032, RFC8949)
[101] Nokia. Press release of 10 March 2025 on its cellular network on the IM-2 lander. https://www.nokia.com/newsroom/nokia-and-intuitive-machines-deliver-first-cellular-network-to-the-moon-achieve-some-key-mission-objectives/ (LRIP-03 NOKIA25)
[102] NASA. Release on the completion of CAPSTONE's extended mission, 6 July 2026. https://nasa.gov/technology/space-comms/nasas-capstone-completes-extended-mission-testing-lunar-technologies (LRIP-03 NASA-CAP)
[103] Santorelli, Wyglinski. "LunarRF: A Terrain-Aware Propagation Engine and Pole-Wide 3GPP Surface Coverage Atlas of the Lunar South Pole." Preprint, 19 October 2026, not peer reviewed. https://arxiv.org/abs/2610.34554 (LRIP-03 LUNARRF)
[104] LeBlanc, Zhang, Sundaram, Koutsoukos. "Consensus of Multi-Agent Networks in the Presence of Adversaries Using Only Local Information." 2012. https://arxiv.org/abs/1205.3676 (LRIP-03 LEBLANC12; the authors' open report, the journal paper being paywalled)
[105] FAA Notice N JO 7110.724, "UAS Lost Link", 11 October 2016. https://www.faa.gov/documentLibrary/media/Notice/N_JO_7110.724_5-2-9_UAS_Lost_Link.pdf; United States Code of Federal Regulations, 14 CFR 91.185. (LRIP-03 FAA16, CFR91185)
[106] G. Rabideau, J. Russino, A. Branch, N. Dhamani, T. Stegun Vaquero, Chien, J.-P. de la Croix, F. Rossi. "Planning, Scheduling, and Execution on the Moon: The CADRE Technology Demonstration Mission." AAMAS 2025, pp. 1727-1735. https://www.ifaamas.org/Proceedings/aamas2025/pdfs/p1727.pdf; NASA JPL, "NASA's Mini Rover Team Is Packed for Lunar Journey", 11 February 2025. https://www.jpl.nasa.gov/news/nasas-mini-rover-team-is-packed-for-lunar-journey/ (LRIP-04 C1, C8)
[107] NASA. News release 26-095, "NASA Awards Moon Base Transportation, Technology, Science Projects", 7 November 2026. https://www.nasa.gov/news-release/nasa-awards-moon-base-transportation-technology-science-projects/ (LRIP-04 M4)
[108] Wikipedia. "Chang'e 8" (a secondary source, read 11 November 2026; it cites SpaceNews of 27 January and 25 April 2025, which were not opened). https://en.wikipedia.org/wiki/Chang%27e_8 (LRIP-04 M11)
[109] Press reports of consultancy forecasts, the reports themselves not opened: SpaceQ, "PwC report: lunar economy projected to generate up to US$127 billion by 2050", 15 May 2026. https://spaceq.ca/pwc-report-lunar-economy-projected-to-generate-up-to-us127-billion-by-2050/; Fortune, on Deloitte's "Building the Lunar Economy", 26 August 2026. https://fortune.com/2026/08/26/spacex-moon-musk-lunar-economy-566-billion-deloitte/; ESA Space Economy, "PwC's Lunar market assessment", November 2021. https://space-economy.esa.int/article/119/pwcs-lunar-market-assessment-market-trends-and-challenges-in-the-development-of-a-lunar-economy (LRIP-04 K1, K3, K2)
[110] Colvin, Crane, Lindbergh, Lal. *Demand Drivers of the Lunar and Cislunar Economy*. IDA Science and Technology Policy Institute, Document D-13219, April 2020 (the executive summary was read). https://www.ida.org/-/media/feature/publications/d/de/demand-drivers-of-the-lunar-and-cislunar-economy/d-13219.pdf (LRIP-04 K4)
[111] Richard, Kamohara, Uno, Santra, van der Meer, Olivares-Mendez, Yoshida. "OmniLRS: A Photorealistic Simulator for Lunar Robotics." arXiv:2309.08997. https://arxiv.org/abs/2309.08997; NASA Glenn, "NASA Tests Lunar Communications Network in Lava Field", 8 December 2022. https://www.nasa.gov/centers-and-facilities/glenn/nasa-tests-lunar-communications-network-in-lava-field/; LUNA Analog Facility (DLR and ESA), "Working and testing in LUNA". https://luna-analog-facility.de/en/for-users/working-and-testing-in-luna/; NASA SSERVI, Lunar Lab and Regolith Testbed. https://sservi.nasa.gov/testbed/ (LRIP-04 L9, L16, L14, L15)
[112] DLR. "Robotics team practises lunar exploration on Mount Etna." 1 July 2022. https://www.dlr.de/en/latest/news/2022/03/20220701_robotics-team-practises-lunar-exploration-on-mount-etna; GMV, "Final field testing completed for CoRob-X", 28 February 2023. https://www.gmv.com/en-es/communication/news/final-field-testing-completed-corob-x (LRIP-04 L11, L12)
[113] Johns Hopkins Applied Physics Laboratory. Press release on the Lunar Operating Guidelines for Infrastructure Consortium (LOGIC), 11 October 2023. https://www.jhuapl.edu/news/news-releases/231011b-lunar-technology-development; Space ROS, site and demonstrations repository. https://space.ros.org/ (LRIP-04 L17, L18)
[114] NASA, ESA, JAXA. *LunaNet Signal-In-Space Recommended Standard: Augmented Forward Signal*, Volume A, version 1, 29 January 2025. https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-signal-in-space-recommended-standard-augmented-forward-signal-vol-a.pdf (LRIP-01 AFS1)

NOTE: [16] title corrected on 12 Nov 2026 to the one in the source list of LRIP note 01 ([LSR23]). [117] to [121] were added in the referee round: [117] and [118] are opened sources of LRIP note 03 (G4); [119], [120] are secondary sources that LRIP notes 01 and 04 record as read and that the text names as secondary; [121] is the source string of the E48 design file, which no research note records as opened, and the text says so.

[115] Artemis II Lunar Science Team. *Artemis II Lunar Science Data User Guide*, version 1.0, 7 October 2026. NASA Planetary Data System, Geosciences Node. doi:10.17189/dtpt-2857; the optical-navigation frames are in the bundle artemis2_orion_camera at the PDS Imaging Node. (LRIP-02 A2-GUIDE, A2-ATLAS)
[116] A. Bailey, B. Semenov. "Artemis II Mission SPICE Bundle." NAIF, NASA JPL. doi:10.17189/7ezn-0294 (LRIP-02 A2-SPICE)
[117] VDA and VDMA. *VDA 5050*, version 3.0.0, 19 March 2026. https://github.com/VDA5050/VDA5050 (LRIP-03 VDA5050)
[118] MassRobotics. *AMR Interoperability Standard*. https://github.com/MassRobotics-AMR/AMR_Interop_Standard (LRIP-03 MASSROB)
[119] Wikipedia. "IM-3" (a secondary source, read 11 November 2026). https://en.wikipedia.org/wiki/IM-3 (LRIP-01 WIKI-IM3)
[120] Wikipedia. "Griffin Mission One" (a secondary source, last edited 9 November 2026). https://en.wikipedia.org/wiki/Griffin_Mission_One (LRIP-04 M7)
[121] Cobham Gaisler. GR740 benchmark results, ESA DSP Day 2016 (as cited in the design file of experiment E48; not recorded as opened in the research notes). https://indico.esa.int/event/102/contributions/62/ (LRIP none)

## Reference statistics (draft 0; the revision of 11 Nov 2026 brings the list to 116 entries, of which 67 and 68 are own work)


66 entries. Own work: [56]-[61] = 6 of 66 (9 %), of which [59] is the pre-registration file and [60, 61] the
companion papers. Dated 2021 or later: to be counted once the text is stable (the vehicle and network sources
[1]-[19], [23]-[28], [34], [41], [45], [46], [54], [55] and the own work are 2021 or later; the mechanism-design
foundations [29]-[33], [37] are older and reported as such). Entries needing publisher checks: [9], [16], [21],
[23], [28], [30], [35], [36], [37], [45], [50].

## What is typed and what is a placeholder

- **Placeholders read from files (not results):** everything in Table 2 and the capacity plateau (the catalogue and
  the scenario's fleet), every mesh number in 3.3 (`results/ATC_mesh.json`), the Assumed defaults of the code (hop
  latency, burst length, radio range, MTBF, repair, re-election delay, rendezvous timeout), the learned policies'
  sizes, the load factor, and the dated changes of PREREG.md.
- **Typed with a citation and flag:** every literature number in Sections 1, 2, 3.2 (lander payloads, ACR24
  demand), 3.3 (horizon, Fresnel, diffraction, free-space loss, Earth round trip, DTE availability, LSR coverage and
  power, Nokia outcome, LunaNet scope) and 6.2 (Dunlap's ladder, UTM latency, CADRE's wake cycle, Kondor's shares,
  Krawciw's 13.8 kB/s). The three design targets of 3.4 (100 B/s per robot, 16 kbit/s for 20 robots, < 1 MB/day)
  are typed as Assumed from H10 and B-81.
- **Placeholders that are results (all pending at draft 0):** every E46 and E48 key, the H5 and H10 verdicts, the
  four E46 and four E48 results paragraphs, Tables 5-8, the B-79 check sentences.
- **Marked [[CHECK]] instead of typed:** (1) the frequencies and transmit power per class of B-81's link budget;
  (2) the source for the radio unit's power per class; (3) whether the lander carries a Lunar ATC unit (the site's
  table says yes, B-81 does not); (4) whether B-76 step 1's private-cost distributions are kept, and their sweep
  ranges; (5) the posted price per tonne-km, or how Earth sets it; (6) which owners-alone regime is the
  individual-rationality baseline (A_MOON per the research note's metric, or A_EARTH); (7) the audit penalty
  multiple m; (8) whether E46 gains a first-price cell or H5's first two clauses are reported as not tested, to be
  recorded as a dated change in PREREG.md before E46 runs; (9) the reference flight processor and benchmark B-81
  chooses; (10) the MTBF levels of the failover sweep.

## Correction of 11 Nov 2026 (B-89, PREREG change 11)

- **What changed in the text.** E48's link budget (5.3, Table 6, 4.2, 3.3's last sentence) is read under the flat-ground two-ray law
  with the smooth-Moon horizon check, free space kept as an upper bound; the traffic (5.2, 3.4, 4.2) gains the authenticated sizes and
  the airtime on a shared channel; every sentence that said the 20-robot traffic is within the 16 kbit/s target (abstract,
  introduction, H10 verdict in 5.1, 5.2, discussion 6.1, conclusion) now carries the condition; 4.1, 4.6, 5.8 and Section 7 disclose the
  correction; CADRE's radio rate is stated as public (1, 2.2) from [28].
- **Typed with a citation:** the law's lunar confirmation [21] and the horizon rule [63] in the composed 4.2 sentence; CADRE's
  "a minimum of 1Mbps of aggregate bandwidth" [28]. **Typed and checked against strings of the file:** the 16 kbit/s and 10 dB margin of
  the mast-reach share, the 20 % guard time and 1/e, the month's trace (regime, load, loss, seed), the report rates of the authenticated
  layout. **Typed, no file holds it:** "an internal check against the literature" (the event; its date is the file's `revision.date`).
- **Word limits.** The abstract builds at exactly 300 words and the conclusion at exactly 250 after cutting 10 and 4 typed words; the
  conclusion therefore states the link condition without the three rates, which Sections 5.1 and 5.2 hold.
- **Not changed, for the lead** (the correction's report lists them): 3.3's "about 8.5 km" for a rover and the mast (2.95 + 5.89 = 8.84);
  6.3's sentence that a UHF band would change the link budget more than any software choice (the two-ray loss is independent of
  frequency beyond the breakpoint); "floods" in 3.4 and 6.3 against the one-hop condition; "known by name" in the introduction.

## Open questions for the lead

1. **H5 against B-76 REVISED.** H5 as registered (and unchanged by change 1) tests first-price shading and says the
   second price "reduces the largest gain", which is a comparison with first price. B-76 REVISED keeps none / second
   price / posted price and drops first price. Either E46 gains a first-price cell (one more rule x two splits x the
   k levels, 30 seeds) or H5's first two clauses are reported "not tested". Both need a dated entry in PREREG.md
   before the first E46 row. The draft states the rule we would apply (Section 4.1) so that it can be registered.
2. **H5 has no numeric decision rule** in PREREG.md. Section 4.1 proposes one (one-sided CI rules per clause); it must
   be registered before E46 runs or the H5 verdict is exploratory.
3. **E46 file names.** B-76 REVISED names none. The build reads `results/E46_cells.csv`, `E46_pairs.csv` and
   `E46_fit.json` with the fields in PLACEHOLDERS.md; BACKEND should confirm or the build's readers change.
4. **E48 schema.** B-81 names `results/E48_sizing.json` and the measurements, not the fields. PLACEHOLDERS.md states
   the schema the build expects (per class: `cpu_safety_check_us`, `cpu_auction_round_ms`, `peak_memory_mb`,
   `power_w`, `link`; `messages`, `ledger_mb_per_year`, `failover`, `flight`, `laptop`, `targets`, `runs`). Fields
   the build needs that B-81 does not promise: `power_w` per class (B-81 says "power estimate"), `flight.memory_mb`
   (the reference processor's memory, needed for the memory part of H10), `laptop.processor`, `runs` (count,
   multiples, run time, processor hours), `failover.by_mtbf.*.merges` and `jobs_assigned_twice` (B-81 promises the
   check, not the count), and `targets` (the three design targets, so that they live in the file and not in the text).
5. **Which "alone" is the IR baseline** (A_MOON or A_EARTH), and whether the alone runs reuse E40's rows.
6. **The lander.** The site's "inside each vehicle" table (F-54) has a lander column; B-81 does not. Table 3 says
   the lander is a closure, not a participant, and flags it.
7. **Shapley coalition runs.** Three owners need 2^3 = 8 coalition runs per seed (the build computes the count from
   the fleet's owners); the research note's 32 is for five owners. B-76 should confirm the runs are made on the same
   seed.
8. **E48 vehicle classes.** The text uses crew rover / cargo rover / small rover / hopper / base computer. If B-81
   measures per catalogue class (seven) instead, the build's CLASSES and CLASS_NAME change.
9. **The abstract and conclusion word counts** are checked only once nothing is pending; with the markers the build
   prints a note instead of failing. Both will need a pass when the clauses fill.

## What in the research notes contradicts the plan

- PLAN-phase5 section 3 says P3 covers "B-71's capacity plateau"; the research note gives the inputs (80 kg crew
  rovers, 2,000 / 800 kg uncontracted cargo rovers) but no plateau number; the draft computes it from the catalogue
  (largest single payload, largest team-lift pair, fleet sum) and states it as a fact about the fleet.
- The research note (MOA section 6.4) names the IR baseline as A-Moon; B-76 says "working alone" without a regime.
- The research note (MOA section 6.6) gives 2^5 = 32 coalition runs per seed for five owners; E46 has three owners.
- B-81 step 2 quotes "the proposal's estimates (20 zones x robots at 10 Hz; 16 kbit/s for 20 robots at 100 B/s;
  < 1 MB/day)"; none of these appears in the research notes, so they are typed as Assumed design targets from H10
  and the task, not as sourced numbers.
- The site's F-54 table gives the lander a Lunar ATC unit; the plan and B-81 do not.

## Revision of 11 Nov 2026 (Phase 6: the Lunar Rover Interaction Protocol in P3)

- **What was added.** Sections 3.5 to 3.8 (position without GPS with Table 4; time; the shared map and its frame; the communication stack and
  its security with Table 5), a Phase 6 paragraph in 4.1, the experiments E50, E51, E52, E53, E54, E55 (authentication) and the real-data checks
  of B-97 in 4.2, their choices-after-results in 4.6, Sections 5.8 to 5.13 with Tables 10 to 15, a fourth-part paragraph in 6.1, three rules
  in 6.3, Section 6.5 (market and reality; Tables 16 and 17), eight new limitation paragraphs in 7, Section 8 (Table 18: proved, tested,
  assumed, not yet tested), Appendix A (Propositions 1 to 8), references [67] to [116].
- **What was renumbered.** The marketplace 3.5 to 3.9; checks 3.6 to 3.10; "What did not work" 5.8 to 5.14; Future work 6.5 to 6.6; the
  Conclusion 8 to 9; Tables 5, 6, 7, 8 to 6, 7, 8, 9 (so that tables are numbered in the order they appear).
- **Typed, with a citation and a flag:** every literature number of 3.5 to 3.8 and 6.5 (the navigation service's dates and simulated accuracy,
  the sensors' Earth and Mars figures, the three published clock rates and the memorandum's 58.7, the frame statements and the LOLA
  products' accuracy and resolution, the standards of Table 5 with issue and date, what has flown, contract ceilings and market totals).
  **Typed and covered by a build check:** the byte layout of an authenticated message (6 + 8 or 16, or a 64-byte signature), the map's
  acceptance limits and site size, E51's guards and intervals, E50's scenario. **Typed design values with no file behind them:** the 10 s
  freshness window, the daily site key, the hop limit, the ladder's order of steps (research note 03, section C). **Placeholders:** every
  result, every model input that `pnt.py`, `clocks.py` constants (through E51), `smap.py` (through E52), the E53 size table and the E54
  parameters hold, and every number of a worked example in Appendix A.
- **Word limits.** The abstract builds at 300 words and the conclusion at 250. To make room, the post hoc clauses
  P3-H5-POWER-ABSTRACT-CLAUSE and P3-H5-POWER-CONCLUSION-CLAUSE left both (they remain in 5.7 and 6.1), the abstract's sentence on the
  companion papers was folded into the question, and the impact sentence was shortened. The E48 link clause of the correction of this
  morning is unchanged in both. The build now enforces both limits even when a key elsewhere is pending.
- **The eleven items left open by the correction of this morning, as fixed:** (1) 3.3's "about 8.5 km" is now computed, 8.84 km, with the
  1.0 m antenna's horizon beside it (P3-HORIZON-SENTENCE); (2) 6.3's UHF sentence now says that a lower band does not lengthen a flat-ground
  hop and changes diffraction around terrain; (3) "floods ... hop by hop" in 3.4, 3.9 and 6.3 is replaced by the two kinds of traffic,
  reports one hop on the scheduled channel and events relayed, with the first version's wording named; (4) a new paragraph in 3.3 sets the
  two-hop median over all route points beside the month's 1.024 hops and adds E53's spread geometry; (5) 3.3 states that the terrain mesh
  keeps 1.0 m pairs beyond the 3.73 km smooth-Moon horizon and quotes `revision.two_ray_in_the_mesh` (6.9 % of 1.0 m links removed with the
  horizon check on; all links close 16 kbit/s at 3 and 10 dB; 94.2 % and 99.1 % at 15 dB); (6) Section 7 no longer says the link budget uses
  a diffraction model; (7) CADRE's election is stated as an appointer every 10 s, at most 10 s without a planner, 25 minutes awake in every
  30, in 2.3 and 3.4 and in the comment of 6.2, with [106]; (8) the introduction says the vehicles are planned and have names, and the
  conclusion "planned"; (9) PROMISE (late 2028, NASA release of 7 Nov 2026 [107]) is named in 1, 3.2, 6.5 and 7 as not in the catalogue;
  (10) the front matter says "revised November 2026"; (11) `references()` keeps trailing punctuation outside a URL's link.
- **Differences found between the notes, the reports and the files** (the paper follows the files): the two-ray asymptote differs from the
  exact two-ray factor by 0.36 dB at the meeting point, not 0.37 (a typed value the build's check caught); note 02 E4 counts 3,906 tiles and
  a 2-byte version while its C4 defines 32-bit versions, and E52 uses 63 x 63 = 3,969 tiles and 10 B per tile in the flat list, which the
  paper follows (the tree's bound does not contain the version length); `lunarsim/atc/geo.py` labels 0.2914 arcseconds as the frame
  kernel's third angle, but the kernel has 0.2785 (0.2914 is the first component of the composed matrix's rotation vector); the shifts
  agree to 0.05 m and the paper uses the kernel's angles; the B-91b report says steering helps the crystal "3 to 7 times", the E51b rows
  give 1.5 to 7.1 (1.5 at a 6 h interval); the B-97 report and the lead's message give "400 to 800 m" of range error at 80,000 km, the
  file gives 408 and 661 km (0.5 to 0.8 % of 79,000 km), and the fitted radius is 0.8 to 1.3 pixels small, not 1.0 to 1.4; the B-92
  report gives the flat manifest as 159 kB, the E52 rows hold 120,760 B; E52's stale-map hits after contact reach 1.65 at 10 kbit/s with
  oldest-first (1.2 at 16 kbit/s).
- **Holm (follow-up of the same day).** `results/phase6_family.json` now holds the confirmatory family with Holm over the three hypotheses that
  have a sampling test (H10, H14, H15a); the paper states it in 4.1, 4.6, 5.8, 5.11, 5.12, 7 and Table 18 through P3-FAMILY-* keys, and the build
  recomputes the adjusted p-values and H14's sign test. The Phase 6 verification rows (`results/vv_phase6.json`, 35 tagged P3) are cited in
  3.10 and 5.14. The E55 variant with the base mast as a node is composed from `consensus_with_base_mast.cells`; over the fleet cells with f at
  most F the graph is connected in 58 to 96 % of runs, and the lowest cell overall, 44 %, has two faulty rovers against a rule set for one.
- **Pending in this build:** E50 at eight times the fleet (`errors."8"` of the E50 file) and E50b. The 8x sentence composes itself when the
  cells land; E50b's composing function only raises the pending and has to be written against the file's real schema.

## Referee round of 11-12 Nov 2026 (reports/referee_phase6_p3.md, decisions in reports/referee_phase6_decisions.md)

- **What changed.** Per finding: `reports/referee_phase6_p3_response.md`. No number that a results file holds changed; what several are called did.
  New composed keys and the awaited keys are in PLACEHOLDERS.md. E50b (B-90b) and E50's eight-times cells landed during the revision and are reported.
- **Referee's own numbers.** The four readings of H9' clause 2, three sensitivity values and the spherical-ground loss and rates are read by the
  build from the referee report and attributed to the referee wherever they print; tasks B-101 and B-104 replace them.
- **References.** [16] title corrected; [60], [61] dated "revised November 2026"; [117] VDA 5050 and [118] MassRobotics added (opened, note 03);
  [119], [120] secondary pages named as such; [121] the GR740 benchmark as the E48 design file cites it (not opened in any note).
  Still without a date, initials or a full title, because the notes do not hold them: [2], [3], [10], [13], [14], [20], [22], [63], [64], [86],
  [99], [100], [116] (dates); [24], [41], [53], [69] to [72], [74], [81] to [84], [103], [104] (authors or initials); [7], [11], [17], [21], [35]
  (composite entries). The arXiv identifier of [103] is as note 03 gives it and was not re-checked on the web.
- **Not done.** O3 (199 jobs against 200.9 awards a seed, unexplained), O6 (CoreMark on the laptop), the split of the paper (the lead's decision:
  a roadmap paragraph and explicit halves instead).
