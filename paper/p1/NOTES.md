# P1 notes: reference list (draft 1, 28 Oct 2026)

Sources: `research_notes/Lunar ATC/multi_owner_allocation.md` (MOA), `vehicles_comms_internals.md` (VCI),
`paper_writing_guide.md` (PWG), and `paper/r1/NOTES.md` (R1) for our own papers and LCRNS. The grade is the
research note's (High / Medium / Low). Numbers in brackets are the ones used in `part1`-`part4`.

[1] B. P. Gerkey, M. J. Matarić. "A formal analysis and taxonomy of task allocation in multi-robot systems." *IJRR* 23(9):939-954, 2004. (MOA, High)
[2] S. Koenig, C. Tovey, M. Lagoudakis, V. Markakis, D. Kempe, P. Keskinocak, A. Kleywegt, A. Meyerson, S. Jain. "The Power of Sequential Single-Item Auctions for Agent Coordination." AAAI 2006, pp. 1625-1629. (MOA, High)
[3] M. G. Lagoudakis et al. "Auction-based multi-robot routing." RSS 2005. https://roboticsproceedings.org/rss01/p45.html (MOA, Medium)
[4] H.-L. Choi, L. Brunet, J. P. How. "Consensus-Based Decentralized Auctions for Robust Task Allocation." *IEEE T-RO* 25(4):912-926, 2009. (MOA, Medium; the 50 % bound is quoted via [5])
[5] A. K. Whitten, H.-L. Choi, L. B. Johnson, J. P. How. "Decentralized Task Allocation with Coupled Constraints in Complex Missions." ACC 2011. (MOA, High)
[6] L. B. Johnson, S. Ponda, H.-L. Choi, J. P. How. "Asynchronous Decentralized Task Allocation for Dynamic Environments." Infotech@Aerospace 2011. (MOA, Medium)
[7] M. B. Dias, R. Zlot, N. Kalra, A. Stentz. "Market-Based Multirobot Coordination: A Survey and Analysis." *Proc. IEEE* 94(7):1257-1270, 2006. (MOA, High)
[8] M. Otte, M. J. Kuhlman, D. Sofge. "Auctions for multi-robot task allocation in communication limited environments." *Autonomous Robots* 44(3-4):547-584, 2020. (MOA, High)
[9] S. Nayak et al. "Experimental Comparison of Decentralized Task Allocation Algorithms Under Imperfect Communication." *IEEE RA-L* 5(2):572-579, 2020. (MOA, High)
[10] J. Lott, B. Honary. "Bundle Length Tradeoffs in Decentralized Multi-Robot Task Allocation Under Degraded Communications." arXiv:2609.06273, 2026. (MOA, High)
[11] J. Lott, B. Honary. "Decentralized Multi-Robot Task Allocation Under Degraded Communication: A Benchmark of Performance, Reliability, and Computation." arXiv:2609.13711, 2026. (MOA, High)
[12] S. Bapat, R. Bora, J. Herrmann, S. Azarm, H. Xu, M. Otte. "Distributed task allocation algorithms for multi-agent systems with very low communication." *IEEE Access* 10:124083-124102, 2022. (MOA, Medium)
[13] G. A. Korsah, A. Stentz, M. B. Dias. "A comprehensive taxonomy for multi-robot task allocation." *IJRR* 32(12):1495-1512, 2013. (MOA, Medium)
[14] O. Shehory, S. Kraus. "Methods for task allocation via agent coalition formation." *Artificial Intelligence* 101(1-2):165-200, 1998. (MOA, Medium)
[15] T. Service, J. Adams. "Coalition formation for task allocation: theory and algorithms." *JAAMAS* 22(2):225-248, 2011. (MOA, Medium)
[16] R. Zlot, A. Stentz. "Market-based multirobot coordination for complex tasks." *IJRR* 25(1):73-101, 2006. (MOA, Medium)
[17] A. Krawciw et al. "Sharing the Load: Autonomous Multi-Rover Cargo Transport." arXiv:2510.18766v2, 2026. (MOA, High)
[18] J. Rodriguez, Tarawneh, Koenig, Dong, Lu. "Auction-Consensus Algorithm with Learned Bidding Scheme for Multi-Robot Systems." 23rd Int. Conf. on Ubiquitous Robots, arXiv:2605.21932, 2026. (MOA, Medium; abstract only)
[19] Chekakta, Aouf, Govindaraj, Polisano, De Cubber. "Towards Learning-Based Distributed Task Allocation Approach for Multi-Robot System." ICARA 2024. doi:10.1109/ICARA60736.2024.10553196 (MOA, Medium)
[20] S. Paul, Maurer, S. Chowdhury. "Bigraph Matching Weighted with Learnt Incentive Function for Multi-Robot Task Allocation." arXiv:2403.07131, 2024. (MOA, High)
[21] S. Paul, P. Ghassemi, S. Chowdhury. "Learning Scalable Policies over Graphs for Multi-Robot Task Allocation using Capsule Attention Networks." ICRA 2022, pp. 8815-8822. (MOA, High)
[22] Z. Wang, M. Gombolay. "Heterogeneous Graph Attention Networks for Scalable Multi-Robot Scheduling with Temporospatial Constraints." RSS 2020. (MOA, High, abstract)
[23] Eshkevari et al. "Reinforcement Learning in the Wild: Scalable RL Dispatching Algorithm Deployed in Ridehailing Marketplace." arXiv:2202.05118, 2022. (MOA, High, abstract)
[24] S. Ross, G. Gordon, D. Bagnell. "A Reduction of Imitation Learning and Structured Prediction to No-Regret Online Learning." AISTATS 2011, PMLR 15:627-635. (MOA, Medium; title to confirm)
[25] C. K. Joshi, Q. Cappart, L.-M. Rousseau, T. Laurent. "Learning the travelling salesperson problem requires rethinking generalization." *Constraints* 27(1-2):70-98, 2022. (MOA, Medium)
[26] L. Accorsi, A. Lodi, D. Vigo. "Guidelines for the computational testing of machine learning approaches to vehicle routing problems." *Operations Research Letters* 50(2):229-234, 2022. (MOA, Medium)
[27] T. Séjourné, S. Samaranayake, S. Banerjee. "The Price of Fragmentation in Mobility-on-Demand Services." *Proc. ACM Meas. Anal. Comput. Syst.* 2(2), 2018. (MOA, High)
[28] D. Kondor, I. Bojic, G. Resta, F. Duarte, P. Santi, C. Ratti. "The cost of non-coordination in urban on-demand mobility." *Scientific Reports* 12:4669, 2022. (MOA, High)
[29] F. Cruijssen, M. Cools, W. Dullaert. "Horizontal cooperation in logistics: opportunities and impediments." *Transportation Research Part E* 43(2):129-142, 2007. (MOA via notes/03, Medium-High; title to confirm)
[30] Open-RMF. "The State of Open-RMF." ROSCon 2024. https://roscon.ros.org/2024/talks/The_State_of_Open-RMF.pdf (MOA, Medium)
[31] G. Rabideau et al. "Multi-Robot Cooperative Autonomy on the Moon: The CADRE Technology Demonstration Mission." ASTRA 2025. (MOA, High)
[32] J.-P. de la Croix et al. "Multi-Agent Autonomy for Space Exploration on the CADRE Lunar Technology Demonstration." IEEE Aerospace 2024. doi:10.1109/AERO58975.2024.10521425 (MOA, Medium)
[33] Zhang, Li, Zheng, Ouyang, Sun, Guo, Li, Jing. "Research on task allocation method for multi-agent systems on the Moon with a distributed architecture." IAC-24, A3, IP, paper 86984. (MOA, High, abstract)
[34] Kashid, Kumat. "Hierarchically Decentralized Heterogeneous Multi-Robot Task Allocation System." arXiv:2405.02484, 2024. (MOA, Medium)
[35] M. Saboia et al. "ACHORD: Communication-Aware Multi-Robot Coordination With Intermittent Connectivity." *IEEE RA-L* 7(4):10184-10191, 2022. (MOA, High)
[36] M. Tranzatto et al. "Team CERBERUS Wins the DARPA Subterranean Challenge: Technical Overview and Lessons Learned." *Field Robotics* 2, 2022. (MOA, High)
[37] NASA. News release on Lunar Terrain Vehicle Phase 1 task orders, 26-27 May 2026, https://www.nasa.gov/news-release/nasa-provides-update-on-moon-base-rovers-landers-missions/ ; progress update 20-21 October 2026, https://www.nasa.gov/missions/moon-base/nasa-provides-progress-update-on-moon-base-rovers/ (VCI, High)
[38] J. Esper, G. Heckler, J. Verville, G. Ryden. "NASA's Lunar Communications Relay and Navigation Systems (LCRNS)." SpaceOps 2025. NTRS 20250003321. (R1 [10], High)
[39] NASA. *LunaNet Interoperability Specification*, version 5, 29 January 2025. https://www.nasa.gov/wp-content/uploads/2025/02/lunanet-interoperability-specification-v5-baseline.pdf (VCI, High)
[40] A. Rahimov. *Who Hauls the Habitat? A Verified Simulation Testbed, a Pooled Dispatch Marketplace and a Reference Design for Lunar Surface Logistics*. Preprint, version 2, October 2026. (R1 [33])
[41] A. Rahimov. *Where the Lander Lands: Landing Precision, Pad Standoff, Plume Keep-Out and Rover Autonomy Priced in Lunar Surface Logistics*. Preprint, version 3, October 2026. (R1 [14])
[42] A. Rahimov. *What Earth's Horizon Costs a Lunar Base: Terrain-Masked Communication Windows in South-Pole Cargo Logistics*. Preprint, October 2026.
[43] Pre-registration: `paper/atc/PREREG.md` in the repository, https://github.com/azizjonrahimov/Lunar-Haul, written 27 October 2026. Changes 1 to 5 and 10 apply to this paper and the others to the companion papers; each is dated in the file.
[44] A. Rahimov. "The Vehicles, the Network and the Market: What Lunar ATC Puts Inside Each Lunar Vehicle and How Its Marketplace Works." Companion paper P3, in preparation, 2026.
[45] A. Rahimov. "Rules of the Road on the Moon and Mars: Traffic Rules for Surface Robots of Different Owners, Checked and Priced." Companion paper P2, in preparation, 2026.
[46] D. J. Schuirmann. "A comparison of the two one-sided tests procedure and the power approach for assessing the equivalence of average bioavailability." *Journal of Pharmacokinetics and Biopharmaceutics* 15(6):657-680, 1987. (PWG; journal details confirmed by LEAD 28 Oct; title to check against the journal page)
[47] D. Lakens. "Equivalence tests: a practical primer for t tests, correlations, and meta-analyses." *Social Psychological and Personality Science* 8(4):355-362, 2017. (PWG; title to confirm)
[48] B. A. Nosek et al. "The preregistration revolution." *PNAS* 115(11):2600-2606, 2018. (PWG)
[49] NASA. Delay/Disruption Tolerant Networking page, https://www.nasa.gov/communicating-with-missions/delay-disruption-tolerant-networking/ (VCI, High)
[50] Kim, Li, Wang. "Lunar Surface Space Traffic Management: Considerations for Future Regulations." GLEX-2025, 11, IP, 15, x93808. (MOA, Medium)
[51] F. Cruijssen, O. Bräysy, W. Dullaert, H. Fleuren, M. Salomon. "Joint route planning under varying market conditions." *International Journal of Physical Distribution and Logistics Management* 37(4):287-304, 2007. (MOA via notes/03, Medium-High; title to confirm)
[52] S. Holm. "A simple sequentially rejective multiple test procedure." *Scandinavian Journal of Statistics* 6(2):65-70, 1979. (added by LEAD, 28 Oct)
[53] B. Efron, R. J. Tibshirani. *An Introduction to the Bootstrap*. Chapman & Hall, 1993. (added by LEAD, 28 Oct)
[54] Pre-registration of the protocol experiments: `paper/atc/PREREG6.md` in the repository, written 11 November 2026 before any of its results existed; hypotheses H13 (protocol load) and H14 (lost link) apply to this paper, and its dated changes are listed in the file. Its H9 and H10 are not the H9 and H10 of [43] and are written H9' and H10' in the papers. (N03, project file)
[55] Consultative Committee for Space Data Systems. *Space Packet Protocol*. CCSDS 133.0-B-2, Blue Book, June 2020. https://public.ccsds.org/Pubs/133x0b2e2.pdf (N03, opened)
[56] Consultative Committee for Space Data Systems. *Space Data Link Security Protocol*. CCSDS 355.0-B-2, Blue Book, July 2022. https://public.ccsds.org/Pubs/355x0b2.pdf (N03, opened)
[57] Consultative Committee for Space Data Systems. *High Data Rate Wireless Proximity Network Communications*. CCSDS 883.0-B-2, Blue Book, May 2024. https://public.ccsds.org/Pubs/883x0b2.pdf (N03, opened)
[58] Consultative Committee for Space Data Systems. *Proximity-1 Space Link Protocol: Data Link Layer*. CCSDS 211.0-B-6, Blue Book, July 2020. https://public.ccsds.org/Pubs/211x0b6e1.pdf (N03, opened)
[59] Consultative Committee for Space Data Systems. *Unified Space Data Link Protocol*. CCSDS 732.1-B-3, Blue Book, June 2024. https://public.ccsds.org/Pubs/732x1b3e1.pdf (N03, opened)
[60] Internet Engineering Task Force. *Bundle Protocol Version 7*. RFC 9171, January 2022. https://www.rfc-editor.org/rfc/rfc9171.txt (N03, opened)
[61] Internet Engineering Task Force. *Concise Binary Object Representation (CBOR)*. RFC 8949, December 2020. https://www.rfc-editor.org/rfc/rfc8949.txt (N03, opened; month and year to confirm against the RFC index)
[62] Internet Engineering Task Force. *Edwards-Curve Digital Signature Algorithm (EdDSA)*. RFC 8032, January 2017. https://www.rfc-editor.org/rfc/rfc8032.txt (N03, opened; month and year to confirm against the RFC index)
[63] National Institute of Standards and Technology. *Recommendation for Block Cipher Modes of Operation: The CMAC Mode for Authentication*. NIST Special Publication 800-38B. https://doi.org/10.6028/NIST.SP.800-38B (N03, opened)
[64] Verband der Automobilindustrie (VDA) and VDMA. *VDA 5050*, version 3.0.0, 19 March 2026. https://github.com/VDA5050/VDA5050 (N03, opened)
[65] MassRobotics. *AMR Interoperability Standard*. https://github.com/MassRobotics-AMR/AMR_Interop_Standard (N03, opened)
[66] MAVLink project. *MAVLink Developer Guide*: Packet Serialization; Message Signing. https://github.com/mavlink/mavlink-devguide/tree/master/en/guide (N03, opened)
[67] *Model Context Protocol specification*, revision 2025-11-25, section Tools. https://github.com/modelcontextprotocol/modelcontextprotocol (N03, opened)
[68] Object Management Group. *DDS Interoperability Wire Protocol (DDSI-RTPS)*, version 2.5. https://www.omg.org/spec/DDSI-RTPS/2.5/PDF (N03, opened)
[69] Liang, Yuan, Lin. "A Performance Study on the Throughput and Latency of Zenoh, MQTT, Kafka, and DDS." arXiv:2303.09419, 2023. https://arxiv.org/abs/2303.09419 (N03, opened; written by Zenoh's vendor team and a university group)
[70] *MQTT-SN Protocol Specification*, version 1.2. https://www.oasis-open.org/committees/download.php/66091/MQTT-SN_spec_v1.2.pdf (N03, opened)
[71] Rabideau, Russino, Branch, Dhamani, Stegun Vaquero, Chien, de la Croix, Rossi. "Planning, Scheduling, and Execution on the Moon: The CADRE Technology Demonstration Mission." AAMAS 2025, pp. 1727-1735. https://www.ifaamas.org/Proceedings/aamas2025/pdfs/p1727.pdf (N04, opened)
[72] Saboia, Rossi, Nguyen, Lim, Aguilar, de la Croix. "CADRE MoonDB: Distributed Database for Multi-Robot Information-Sharing and Map-Merging for Lunar Exploration." MASSpace 2024. https://ai.jpl.nasa.gov/public/documents/papers/MoonDB-MASSpace-paper.pdf (N04, read in part)
[73] Brinkmann. "NASA expects one lunar launch this year, Moon Base manager says." *Aerospace America* (AIAA), 15 September 2026. https://aerospaceamerica.aiaa.org/nasa-expects-one-lunar-launch-this-year-moon-base-manager-says/ (N04, opened)
[74] Buckman, Choi, How. "Partial Replanning for Decentralized Dynamic Task Allocation." AIAA SciTech 2019, arXiv:1806.04836. https://arxiv.org/abs/1806.04836 (N04, opened)
[75] Litaker, Li, Beaton, Lewis. *Lunar Terrain Vehicle (LTV) Remote Teleoperation Studies Under Four Lunar Communication Latencies*. NASA/TM-20240001217, 2024. https://ntrs.nasa.gov/api/citations/20240001217/downloads/LTV%20Teleops%20Study.pdf (N04, opened)
[76] Fong. "Volatiles Investigating Polar Exploration Rover." Slides, NASA Ames, 29 April 2026. NTRS 20260002876. https://ntrs.nasa.gov/api/citations/20260002876/downloads/viper-2026-04-29_v2.pdf (N04, opened)
[77] Olsen, Wood. "Fan-out: Measuring Human Control of Multiple Robots." CHI 2004, pp. 231-238. https://hci.rwth-aachen.de/materials/conferences/CHI2004/1p231.pdf (N04, opened)
[78] IoT M2M Council. "How many self-driving vehicles can one person monitor?" 2 September 2025. A report of a Coventry University simulator study; the journal article was not opened. https://iotm2mcouncil.org/iot-library/news/connected-transportation-news/how-many-self-driving-vehicles-can-one-person-monitor/ (N04, opened; secondary)
[79] HumanProgress. Item on Waymo's remote-assistance staffing, 3 March 2026. It quotes a newsletter; the primary letter was not opened. https://humanprogress.org/waymo-achieves-industry-leading-143-remote-operator-ratio/ (N04, opened; secondary)
[80] Yates et al. "Age of Information: An Introduction and Survey." arXiv:2007.08564, 2020. https://arxiv.org/abs/2007.08564 (N03, opened)
[81] Bedewy, Sun, Shroff. "The Age of Information in Multihop Networks." arXiv:1712.10061, 2017. https://arxiv.org/abs/1712.10061 (N03, opened)

Missing from the research notes and needed:
- The Hungarian method (Kuhn 1955) is named in 2.1 and 3.11 and is cited only through [1].

## Reference statistics (LEAD, 28 Oct 2026; writing guide §7: mostly recent, low self-citation)
53 entries. Dated 2021 or later: 26 by the year in the entry, plus [33] (IAC-24, 2024) and the two companion papers
[44, 45] (2026) = 29 of 53 (55 %). Undated: [49] (NASA web page). Own work: [40]-[45] = 6 of 53 (11 %), of which
Here [43] is the pre-registration file and [44, 45] the companion papers. Entries marked "title to confirm" or "to add"
([24], [29], [46], [47], [51]) must be checked against the publisher's record before submission; the AI-use statement
in part5 says so.

## Phase 6 additions (11 Nov 2026): [54]-[81]
Sources: `research_notes/Lunar Rover Interaction Protocol/03_comms_protocol_security.md` (N03, source list G4) and
`04_coordination_and_market.md` (N04, source list I.4). Only sources those notes mark as opened are listed, with the
author names as the notes give them (surnames only where the notes give no initials; add initials from the
publisher's record before submission). The RFC dates of [61] and [62] are not in the notes and must be confirmed.
Not listed because the notes could not open them, and therefore not cited as support in the text: the FIPA Contract
Net specification (named in Section 3.12 with that flag); the full text of Choi, Brunet and How 2009 ([4], abstract
page only: the 50 % bound is quoted as reported by [5] and [74]); Fisher, Nemhauser and Wolsey 1978 (named in
Appendix B with the flag "not re-read": Proposition 1 is proved without it); de la Croix et al. 2024 ([32], kept from
draft 1, paywalled: the CADRE facts added in Phase 6 rest on [71]-[73]). [78] and [79] are secondary reports and the
text says so. Total 81 entries; own work [40]-[45] and [54] = 7 of 81 (9 %).
