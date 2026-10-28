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
[43] Pre-registration: `paper/atc/PREREG.md` in the repository, written 27 October 2026, changes 1-3 dated (commits 4bb0b0b, 0deb61d, 31c8ceb, c90676f). Cite by repository tag when tagged.
[44] Companion paper P3 (vehicles, network, what Lunar ATC puts inside each vehicle, and the market). Title to be fixed.
[45] Companion paper P2 (rules of the road and the safety layer on the Moon and Mars). Title to be fixed.
[46] D. J. Schuirmann. "A comparison of the two one-sided tests procedure and the power approach for assessing the equivalence of average bioavailability." *Journal of Pharmacokinetics and Biopharmaceutics* 15(6):657-680, 1987. (PWG; journal details confirmed by LEAD 28 Oct; title to check against the journal page)
[47] D. Lakens. *Social Psychological and Personality Science* 8(4):355-362, 2017 (equivalence testing). (PWG; title to add)
[48] B. A. Nosek et al. "The preregistration revolution." *PNAS* 115(11):2600-2606, 2018. (PWG) Not cited in the text yet; cite in 4.1 if kept.
[49] NASA. Delay/Disruption Tolerant Networking page, https://www.nasa.gov/communicating-with-missions/delay-disruption-tolerant-networking/ (VCI, High)
[50] Kim, Li, Wang. "Lunar Surface Space Traffic Management: Considerations for Future Regulations." GLEX-2025, 11, IP, 15, x93808. (MOA, Medium)
[51] F. Cruijssen et al. Joint route planning savings, *IJPDLM* 37(4):287-304, 2007. (MOA via notes/03, Medium-High; full title to add)
[52] S. Holm. "A simple sequentially rejective multiple test procedure." *Scandinavian Journal of Statistics* 6(2):65-70, 1979. (added by LEAD, 28 Oct)
[53] B. Efron, R. J. Tibshirani. *An Introduction to the Bootstrap*. Chapman & Hall, 1993. (added by LEAD, 28 Oct)

Missing from the research notes and needed:
- The Hungarian method (Kuhn 1955) is named in 2.1 and 3.11 and is cited only through [1].
