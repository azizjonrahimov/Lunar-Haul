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
[10] NASA JPL. CADRE mission page. https://www.jpl.nasa.gov/missions/cadre (VCI, High; band, rate and range not public)
[11] Gunter's Space Page. Blue Moon MK1, 15 April 2026. https://space.skyrocket.de/doc_sdat/blue-moon.htm; Blue Origin. (VCI, High/Medium)
[12] NASA. "NASA JPL testing readies Voyager Technologies lander for Moon mission." 13 October 2026. https://nasa.gov/missions/moon-base/nasa-jpl-testing-readies-voyager-technologies-lander-for-moon-mission (VCI, High)
[13] Firefly Aerospace. Blue Ghost. https://fireflyspace.com/blue-ghost; NASASpaceflight, January 2025. (VCI, High)
[14] ESA. "Argonaut lunar lander family grows." https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Argonaut_lunar_lander_family_grows; Thales Alenia Space press release, 30 January 2025. (VCI, High/Medium)
[15] NASA. *LunaNet Interoperability Specification*, version 5, 29 January 2025. https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-interoperability-specification-v5-baseline.pdf (VCI, High)
[16] M. C. Scardelletti et al. "Lunar Surface Relay." ICSSC 2023. NTRS 20230013361. https://ntrs.nasa.gov/api/citations/20230013361/downloads/ICSSC-2023_LSR_paper%20rev7k.pdf (VCI, High; full author list and title to add)
[17] Nokia. "Nokia's cellular network ready for Moon as Intuitive Machines completes final lunar lander installation." 7 January 2025. https://www.nokia.com/about-us/news/releases/2025/01/07/; Converge Digest, 11 March 2025; Fierce Network; Mobile World Live, March 2025 (the outcome on IM-2). (VCI, Medium: press as summarised; the primary page returned HTTP 403)
[18] Astrobotic. *Lunar Landers Payload User's Guide*, 2021. https://science.nasa.gov/wp-content/uploads/2023/11/astrobotic-lunar-landers-pug.pdf (VCI, High)
[19] J. Esper, G. Heckler, J. Verville, G. Ryden. "NASA's Lunar Communications Relay and Navigation Systems (LCRNS)." SpaceOps 2025. NTRS 20250003321. (P1 [38], High)
[20] ITU-R Recommendation P.526. *Propagation by diffraction*. https://www.itu.int/rec/R-REC-P.526/en (VCI, High for the method; the knife-edge values are Computed)
[21] S. U. Hwu, M. Upanavage, C. C. Sham. Lunar surface propagation study. NASA JSC, 2008. NTRS 20080015374. https://ntrs.nasa.gov/citations/20080015374; NASA GRC on regolith permittivity, NTRS 20230013296. (VCI, High)

NOTE: [21] full title to add from the NTRS record before submission.

[22] NASA. Delay/Disruption Tolerant Networking page. https://www.nasa.gov/communicating-with-missions/delay-disruption-tolerant-networking/ (VCI, High)
[23] N. Ashby, B. Patla. Lunar clock rate relative to Earth. *Astronomical Journal* 168:3, 2024; APS Physics summary https://physics.aps.org/articles/v17/140 (VCI, High; title to add)
[24] UNOOSA ICG Working Group B, Lunar PNT, June 2024 slides (draft lunar UHF band 390-405 MHz). https://www.unoosa.org/documents/pdf/icg/2024/WG-B_Lunar_PNT_Jun24/LunarPNT_Jun24_02_01.pdf (VCI, Medium; draft)
[25] A. Krawciw et al. "Sharing the Load: Autonomous Multi-Rover Cargo Transport." arXiv:2510.18766v2, 2026. (VCI/MOA, High; the 13.8 kB/s convoy figure is quoted in MOA section 5)
[26] G. Rabideau, J. Russino, A. Branch, N. Dhamani, T. Stegun Vaquero, J.-P. de la Croix, F. Rossi. "Multi-Robot Cooperative Autonomy on the Moon: The CADRE Technology Demonstration Mission." ASTRA 2025. https://ai.jpl.nasa.gov/public/documents/papers/CADRE-ASTRA-2025-Extended-Abstract.pdf (MOA, High)
[27] K. Albee et al. "Lunar Leader: Persistent, Optimal Leader Election for Multi-Agent Exploration Teams." MASSpace 2024; JPL CADRE AAMAS slides, https://ai.jpl.nasa.gov/public/documents/presentations/CADRE-AAMAS-Slides.pdf (MOA, Medium / High)
[28] M. Saboia et al. "CADRE MoonDB." MASSpace 2024. (MOA, Medium; full title to add)
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
[60] A. Rahimov. *Working Together Without Earth: Job Sharing, Team Lifts and Learned Bidding Among Lunar Robots of Different Owners*. Preprint, October 2026 (companion paper P1).
[61] A. Rahimov. *Rules of the Road on the Moon and Mars: Traffic Rules for Surface Robots of Different Owners, Checked and Priced*. Preprint, October 2026 (companion paper P2).
[62] B. Efron, R. J. Tibshirani. *An Introduction to the Bootstrap*. Chapman & Hall, 1993. (P2 [55])
[63] NASA Space Math. Horizon distance on a sphere. https://spacemath.gsfc.nasa.gov/Geometry/3Page19.pdf (VCI, High; the lunar values are Computed in the note)
[64] NSSDC. Apollo Lunar Roving Vehicle. https://nssdc.gsfc.nasa.gov/planetary/lunar/apollo_lrv.html (VCI, High)
[65] S. Pan, D. Trentesaux, E. Ballot, G. Q. Huang. "Horizontal collaborative transport: survey of solutions and practical implementation issues." *International Journal of Production Research* 57(15-16):5340-5361, 2019. doi:10.1080/00207543.2019.1574040 (MOA, Medium)

NOTE: [65] is cited in 2.4 since draft 2 (the survey of 120 studies). Draft 2 also cites [22] in 2.2 (DTN operational, no surface demonstration) and [51], [52], [53] in 2.1 (the policy frame); every entry is now cited.

NOTE: draft 3 (referee round 2, finding 28): the spaces before semicolons in [1], [8], [11], [13], [14], [17], [21] are removed; [59] no longer carries backticks or the "cite by tag" remark; [53]'s authors' initials are not in the research notes (MOA section 6 and TAS give "Kim (ispace), Li, Wang (Univ. of Newcastle, Australia)" without initials), so the entry stays as it is until the GLEX record is checked; [7] is three press names and keeps its semicolons.

[66] J. Rios et al. *UAS Service Supplier Network Performance: Results and Analysis from Flight Testing Multiple USS Providers in NASA's TCL4 Demonstration*. NASA/TM-2020-220462, January 2020. https://ntrs.nasa.gov/citations/20200000531 (TAS, High)

## Reference statistics (draft 0)

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
