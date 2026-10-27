# Multi-owner task allocation, coalitions and learned dispatch for Lunar ATC: literature review and experiment design (current to 2026-10-27)

Scope. Task allocation and coordination among robots that belong to different, self-interested owners; tasks that need more than one robot; payment and gain-sharing rules; learned ("neural") allocation; and the space-specific record (CADRE, lunar multi-robot concepts, surface traffic management, DARPA SubT). The goal is to decide what LunarHaul should compare, how, and what would be new.

Grades. **High** = primary source read in this session (full text or the relevant sections of it). **Medium** = abstract, official page, search snippet, or a secondary source that quotes the primary. **Low** = not re-checked in this session (standard result recalled, or untraceable). **Computed** = arithmetic done for this note. **Repo** = a fact taken from this repository's own code, README or notes.

Method. About 45 web searches and 30 page/PDF reads. Fourteen PDFs were downloaded to the session scratchpad and read as text (pdftotext): Lott & Honary (two 2026 papers), Otte et al. 2020, Nayak et al. 2020, Whitten et al. 2011, Koenig et al. 2006, Gerkey & Matarić 2004, Dias et al. 2005/2006, Krawciw et al. 2026, the CADRE ASTRA 2025 abstract and AAMAS slides, ACHORD, CERBERUS, Ausubel & Milgrom, and the IAC 2024 lunar CBAA abstract. ACM, IEEE Xplore and ScienceDirect full texts were not reachable (403/paywall); items resting on those are graded Medium or Low. This note builds on `notes/03_marketplace_mechanisms_and_sim_design.md`, which already covers SSI bounds, gain-sharing methods and the horizontal-collaboration savings band; those numbers are referenced, not repeated in full.

---

## Summary

1. **Decentralized auctions lose a little when communication is good and lose much more, in ways that depend on the algorithm and its settings, when messages drop.** The best decentralized allocators lose about 11–13 % on makespan between perfect delivery and 40 % Bernoulli loss (DGA 21.93 → 24.36 steps; DMCHBA 22.10 → 24.90; Lott & Honary 2026b). ACBBA with deep bundles loses up to 65 % on total travel at 25 % loss, and the bundle length that is best with perfect links is the wrong one under loss (Lott & Honary 2026a). No paper found measures decentralized vs *centralized-optimal* allocation under terrain-masked, range-limited radio links like ours.
2. **Worst-case bounds exist and are loose; measured performance is much better.** SSI: total cost ≤ 2× optimal (Koenig et al. 2006). CBBA: ≥ 50 % of optimal score under diminishing marginal gain, "over 90 % in simulations" (Whitten et al. 2011). Greedy assignment is 2-competitive, and online greedy is 3-competitive (Gerkey & Matarić 2004). For fewer than about 200 robots, Gerkey & Matarić judge broadcast-centralized assignment "likely the better choice".
3. **Tasks needing two robots are formally hard but tiny at our scale.** ST-MR allocation is set partitioning (strongly NP-hard), and inapproximable within O(m^(1−ε)) in general. With ≤ 12 rovers and two-rover lifts, there are ≤ 66 pairs, so exact enumeration is cheap. The hard part is *timing* (both rovers must meet), which CBBA handles only through its coupled-constraint extension (CCBBA).
4. **Two-rover cargo carrying is field-demonstrated.** Two 800 kg rovers carried a 475 kg, 5.5 m cargo. They kept a 9.2 cm mean and 33.4 cm maximum separation error over 13.8 KB/s of inter-rover traffic (Krawciw et al. 2026). The cooperation is control-level and between rovers of one owner.
5. **Mechanism design forces a choice.** No bilateral-trade mechanism is efficient, incentive compatible, individually rational and budget-balanced at once (Myerson & Satterthwaite 1983). VCG is truthful and efficient but runs a deficit and is open to collusion by losing bidders and to shill bids (Ausubel & Milgrom 2006). McAfee's trade reduction is truthful and budget-safe, but it loses up to 1/q of the gains from trade with q trades. In a thin lunar market (q = 2–4 per round) that is 25–50 % worst case (Computed).
6. **Fragmentation has a published law in ride-hailing.** Splitting demand across m non-coordinating operators raises the total fleet by (m−1)·D. D runs from 2.5 % (Manhattan) to 67 % (Curitiba) and falls with trip density. The smallest operator pays most: in Singapore with 50/35/15 % shares, its fleet grows 48 % against 8.5 % for the largest (Kondor et al. 2022). This is a direct external check for LunarHaul's own fragmentation law.
7. **Learned allocators are evaluated on small, cooperative, perfect-comms problems.** Examples: CapAM (Paul et al. 2022), BiG-CAM (Paul et al. 2024), ScheduleNet (Wang & Gombolay 2020), and a 2026 PPO-trained neural bidder inside CBBA (Rodriguez et al. 2026). Generalisation beyond training size is a documented weak point (Joshi et al. 2022). Training budgets are 15–21 h for the graph-RL models. Industrial RL dispatch (DiDi) reports gains of about +1.3 % driver income in A/B tests and up to 5.3 % after deployment (Eshkevari et al. 2022). Learning is an increment, not a step change.
8. **Space practice is conservative.** CADRE runs a *centralized planner on an elected leader* with decentralized execution. Its leader is re-elected every 30 min wake cycle; election uses a GHS minimum spanning tree, then a health convergecast (Rabideau et al. 2025; JPL slides). The SubT winner deployed only single-robot autonomy despite having multi-robot coordination code (Tranzatto et al. 2022).
9. **Recommended design: separate *sharing* from *where decisions are made*.**
   - Compare owners alone vs pooled, crossed with Earth-only dispatch (works only in Earth-link windows) vs on-Moon dispatch.
   - On-Moon dispatch has three variants: elected-leader central (CADRE-style), decentralized hand-crafted bids, and decentralized learned bids.
   - Add a full-information oracle.
   - Run at loads where the fleet is busy (target 20–60 % utilisation). At today's 4.6 % typical utilisation, allocation quality hardly matters (Repo).
10. **A credible "neural bidding policy" is small.** A 2-layer MLP (about 1–2k parameters) scores (rover, item) pairs from about 12 local features. It adds a learned correction to the hand-crafted marginal-cost bid, inside the unchanged auction. It is trained on CPU by imitation (DAgger) of a full-information oracle, optionally fine-tuned by cross-entropy search. It is tested out of distribution and against a linear model with the same features.
11. **Novelty.** Learned bidding in auctions and comm-loss studies of auctions are already published. Not found: allocation among *self-interested owners* with payments and gain sharing, under *terrain-masked Earth-link windows and lunar line-of-sight mesh*, with *cross-owner two-rover lifts*, measured at logistics level (delay, $/kg, per-owner profit, manipulability).

---

## 1. Market-based multi-robot coordination

### Takeaway

Auctions are the standard decentralized allocator because each robot prices tasks from its own cost model and the clearing rule is simple. With perfect communication, sequential single-item (SSI) auctions and CBBA come close to optimal in practice: worst-case factors of 2 and 1/2, but "over 90 %" or "empirically close to optimal" in experiments. Under message loss, performance degrades *differently* for each algorithm. Parameters tuned with perfect links (bundle length) can become dominated under loss, and single-round auctions suffer most because a robot that misses the only round sits idle. Measured degradation for the best methods is about 10–15 % at 25–40 % packet loss. Poorly matched settings lose 15–80 %. Every study found uses abstract grids or Euclidean worlds with i.i.d. or bursty loss, cooperative robots, and makespan or total travel as the metric. None uses terrain line-of-sight, long scheduled blackouts, or logistics metrics.

### Findings

**Bounds and baselines**
- **Sequential single-item auctions (SSI).**
  - Each round, every robot bids its cheapest-insertion cost for each unallocated task, and the lowest bid wins one task.
  - The MiniSum total path cost is at most 2× optimal (known terrain, triangle inequality); a lower-bound example shows 1.5×.
  - Parallel single-item auctions have an unbounded ratio.
  - "Empirically close to optimal (and thus almost as good as … combinatorial auctions)".
  - Source: Koenig, Tovey, Lagoudakis, Markakis, Kempe, Keskinocak, Kleywegt, Meyerson, Jain, "The Power of Sequential Single-Item Auctions for Agent Coordination", AAAI 2006, pp. 1625–1629, https://cdn.aaai.org/AAAI/2006/AAAI06-266.pdf — **High** (text read; bound numbers also in notes/03).
  - Proofs: Lagoudakis et al., "Auction-based multi-robot routing", RSS 2005, https://roboticsproceedings.org/rss01/p45.html — **Medium**.
- **Optimal-assignment baseline (ST-SR-IA).**
  - Kuhn's Hungarian method solves it in O(mn²).
  - Greedy is 2-competitive for the optimal assignment problem (Avis 1983). Online greedy is 3-competitive (Kalyanasundaram & Pruhs 1993).
  - The time-extended version (ST-SR-TA) is R||Cmax, which is strongly NP-hard.
  - "For small- to medium-scale systems, say n < 200, a broadcast-based centralized assignment solution is likely the better choice."
  - Source: Gerkey & Matarić, "A formal analysis and taxonomy of task allocation in multi-robot systems", IJRR 23(9):939–954, 2004, https://cse-robotics.engr.tamu.edu/dshell/cs689/papers/gerkey04formal.pdf — **High**.
- **Distributed equivalent of the Hungarian method.**
  - Bertsekas's auction algorithm reaches an assignment within nε of optimal.
  - Source: Bertsekas, "The auction algorithm: a distributed relaxation method for the assignment problem", Annals of OR 14:105–123, 1988 — **Low** (standard result, not re-read).
- **CBBA (consensus-based bundle algorithm).**
  - Two phases: greedy bundle building, then consensus on winning bids with neighbours only.
  - The result is conflict-free and robust to inconsistent situational awareness and changing topology.
  - Convergence and the worst-case guarantee need the score to have *diminishing marginal gain* (DMG). With DMG it gives a "50 % minimum performance bound; over 90 % in simulations".
  - Sources: Choi, Brunet, How, "Consensus-Based Decentralized Auctions for Robust Task Allocation", IEEE T-RO 25(4):912–926, 2009, https://dspace.mit.edu/handle/1721.1/52330 — **Medium** (abstract). The 50 %/90 % figures are as stated in Whitten et al. 2011 (below) — **High**.
- **ACBBA.**
  - Removes CBBA's global synchronisation; consensus uses timestamps and selective rebroadcast. The 2011 paper adds an "asynchronous replan" and a UDP real-time implementation.
  - Source: Johnson, Ponda, Choi, How, "Asynchronous Decentralized Task Allocation for Dynamic Environments", Infotech@Aerospace 2011, https://dspace.mit.edu/handle/1721.1/81434 — **Medium**.
  - A later evaluation in a realistic lossy network found duplicated and unassigned tasks as agents and tasks grew (Rantanen et al. 2018) — **Medium** (search snippet; also cited for "duplicate assignments and unassigned tasks" by Lott & Honary 2026b).
- **TraderBots (Dias & Stentz).**
  - A free-market architecture: robots trade tasks to raise individual profit, with "opportunistically centralized" planning by local leaders.
  - The survey calls it "most flexible" in using local planning inside bids.
  - The 2003 IROS comparison (centralized vs market vs behavioural) reports, qualitatively, that markets "compare favorably" to the centralized optimum on cost and to behavioural methods on computation.
  - Sources:
    - Dias, Zlot, Kalra, Stentz, "Market-Based Multirobot Coordination: A Survey and Analysis", Proc. IEEE 94(7):1257–1270, 2006 (TR CMU-RI-TR-05-13 text read), https://www.ri.cmu.edu/publications/market-based-multirobot-coordination-a-survey-and-analysis — **High** (qualitative).
    - Dias & Stentz, IROS 2003, vol. 3, pp. 2279–2284, https://www.ri.cmu.edu/publications/a-comparative-study-between-centralized-market-based-and-behavioral-multirobot-coordination-approaches — **Medium** (abstract; no numbers).
    - TraderBots thesis: Dias, CMU-RI-TR-04-24, 2004 — **Low** (not read).

**Communication loss: measured effects**
- **Otte, Kuhlman, Sofge 2020** (NRL/UMD). Six auctions (sequential, parallel, combinatorial, G-Prim, two repeated-parallel variants), Bernoulli and Gilbert–Elliott loss "from perfect to nonexistent"; simulation plus AscTec Pelican hardware.
  - Rankings change with loss rate. Rank transitions happen at lower drop rates under Bernoulli than under bursty Gilbert–Elliott loss.
  - "Single-round auctions were found to have much worse performance than the multi-round auctions in communication limited scenarios … agents that happen to miss the one and only round of bidding must sit idle."
  - Re-sending previous winners in later rounds "was found to be an easy way to increase the performance of all multi-round auctions".
  - Above about 50 % loss (min-max objective), Repeated G-Prim is best.
  - Mean solve time rises as communication worsens.
  - Source: Otte, Kuhlman, Sofge, "Auctions for multi-robot task allocation in communication limited environments", Autonomous Robots 44(3–4):547–584, 2020, preprint https://ottelab.com/html_stuff/pdf_files/otte.etal.AURO19.pdf — **High**.
- **Nayak et al. 2020.** CBAA, ACBBA, DHBA, HIPC and PI under Bernoulli, Gilbert–Elliott and Rayleigh fading; collaborative visit and search-and-visit; 50 instances per cell.
  - At high communication, ACBBA gives the lowest max distance, but CBAA sends fewer messages.
  - At zero communication (Bernoulli), CBAA and PI do best.
  - "The performance of both groups of algorithms degrades under imperfect communication."
  - Source: Nayak, Yeotikar, Carrillo, Rudnick-Cohen, Jaffar, Patel, Azarm, Herrmann, Xu, Otte, "Experimental Comparison of Decentralized Task Allocation Algorithms Under Imperfect Communication", IEEE RA-L 5(2):572–579, 2020, https://user.eng.umd.edu/~mumu/files/nyc_RAL2020.pdf — **High** (text read; numbers are in figures, not tables).
- **Lott & Honary 2026a, bundle length under loss.** ACBBA, PI and HIPC; 4 robots on a 19×19 grid, 10 targets; 300 paired scenarios; B ∈ {1, 2, 3, 5, 8, 12}; perfect delivery vs 25 % independent per-receiver loss; 12,600 runs.
  - Perfect links: B 1 → 12 cuts total travel by 19.0 % (ACBBA), 23.0 % (PI) and 31.8 % (HIPC). It raises makespan by 45.6 %, 94.3 % and 67.6 %.
  - At 25 % loss, ACBBA's total-travel penalty versus perfect links grows from 19.7 % at B = 1 to 64.7 % at B = 12; PI's from 32.7 % to 78.1 %.
  - Under loss, the best B for total travel moves from 12 to 2. Keeping the perfect-link setting costs 14.4 % (ACBBA, 95 % CI 11.2–17.7) and 7.2 % (PI) in held-out tests, and raises makespan by 30.0 % and 41.8 %.
  - HIPC (local team prediction plus plan consensus) keeps deep bundles under loss.
  - Method lesson: select parameters on separate scenarios from those used to evaluate them (repeated paired cross-fitting).
  - Source: Lott & Honary, "Bundle Length Tradeoffs in Decentralized Multi-Robot Task Allocation Under Degraded Communications", arXiv 2609.06273, Sept 2026, https://arxiv.org/abs/2609.06273; code https://github.com/jlott22/multi-task-plan-depth-study — **High**.
- **Lott & Honary 2026b, six-allocator benchmark.** CBAA, ACBBA, PI, HIPC, DMCHBA, DGA; 500 paired 10-target instances; 25 conditions (Bernoulli, Gilbert–Elliott, Rayleigh); 112,500 core runs.
  - Mean makespan over the 24 impaired conditions: DGA 24.49, DMCHBA 24.78, HIPC 25.12, CBAA 26.02, ACBBA 26.91, PI 29.05 steps.
  - From perfect delivery to 40 % Bernoulli loss: DGA 21.93 → 24.36 steps (+11 %, Computed); DMCHBA 22.10 → 24.90 (+12.7 %).
  - Total travel under impairment: HIPC 66.95, DGA 67.22, DMCHBA 89.99, ACBBA 95.73, CBAA 96.42, PI 105.92 steps.
  - Message intensity: DMCHBA lowest at about 2.08 publications per team step.
  - Median computation from 4.88 ms (DMCHBA) to 1.346 s (DGA).
  - Within-algorithm degradation is about 0.3 % of makespan per percentage point of loss for most methods (0.17 for HIPC).
  - Source: Lott & Honary, "Decentralized Multi-Robot Task Allocation Under Degraded Communication: A Benchmark of Performance, Reliability, and Computation", arXiv 2609.13711, Sept 2026, https://arxiv.org/abs/2609.13711 — **High**.
- **Very-low-communication allocators.** Two new algorithms are compared with ACBBA, DHBA and PI; they do better on time-to-visit-all-targets when communication is very low.
  - Source: Bapat, Bora, Herrmann, Azarm, Xu, Otte, "Distributed task allocation algorithms for multi-agent systems with very low communication", IEEE Access 10:124083–124102, 2022, https://user.eng.umd.edu/~mumu/files/bbh_Access2022.pdf — **Medium** (downloaded; abstract-level use).
- **Learned communication instead of learned bids.** Agents learn when to send or censor CBBA messages from features such as local graph density. Reported: faster convergence and better allocations under constrained communication.
  - Source: Raja, MIT thesis (advisor J. How), https://dspace.mit.edu/handle/1721.1/128998 — **Medium**.

**Answer to "how much worse is decentralized than centralized?"**
- *Perfect links*:
  - Worst-case factors are 2 (SSI, cost) and 0.5 (CBBA, score).
  - Typical measured gaps are under 10 % ("over 90 %"; "empirically close to optimal").
  - No paper found gives a clean decentralized-vs-optimal gap on a logistics problem — **Medium**.
- *Dropped messages*:
  - +11–13 % makespan at 40 % i.i.d. loss for the best methods.
  - +20–78 % total travel at 25 % loss for ACBBA/PI, depending on bundle length.
  - Single-round auctions are the most fragile.
  - These are relative to the *same algorithm with perfect links*, not to a centralized optimum — **High** (Lott & Honary; Otte et al.).
- *Limited range*:
  - Studies exist (Bai, Yan & Ge, IEEE T-SMC: Systems 2022, report that total travel can *increase* with range in some disconnected cases; Verma et al., IEEE Access 13:171818–171830, 2025, cited by Lott & Honary).
  - No range-vs-optimality numbers were read — **Medium/Low**.

---

## 2. Coalition formation and cooperative transport

### Takeaway

Allocating tasks that need several robots at once (ST-MR in Gerkey & Matarić's taxonomy) is a set-partitioning problem: strongly NP-hard and, in general, inapproximable. But the difficulty is in the number of possible coalitions, and two-rover lifts among a dozen rovers are trivially enumerable. What matters for LunarHaul is the *cross-schedule dependency* (iTax "XD"): both rovers must arrive, couple and travel together. Under message loss a rover can wait for a partner that never comes, so the protocol needs a commit step and a timeout. Decentralized solutions exist (CCBBA's pessimistic/optimistic bidding with timing constraints; MURDOCH-style auctions; RACHNA). Two-rover cargo carriage has been demonstrated in the field for a lunar cargo concept. Nothing found studies coalitions of robots from *different owners* with payments or gain sharing.

### Findings

- **Taxonomy.**
  - Gerkey & Matarić: single-task vs multi-task robots (ST/MT), single-robot vs multi-robot tasks (SR/MR), instantaneous vs time-extended assignment (IA/TA).
  - ST-MR-IA "can be cast as an instance of" the set partitioning problem, which "is strongly NP-hard". Shehory & Kraus 1998 showed a parallel SPP-style algorithm for coalition formation.
  - Source: Gerkey & Matarić 2004 (above) — **High**.
- **iTax.** Adds interrelated utilities and constraints: no dependencies (ND), in-schedule (ID), cross-schedule (XD) and complex (CD) dependencies, and maps each class to OR models.
  - A two-rover lift whose timing affects both rovers' schedules is XD.
  - Source: Korsah, Stentz, Dias, "A comprehensive taxonomy for multi-robot task allocation", IJRR 32(12):1495–1512, 2013, https://www.ri.cmu.edu/publications/a-comprehensive-taxonomy-for-multi-robot-task-allocation — **Medium** (abstract and secondary definitions).
- **Coalition formation for task allocation (multi-agent).** Distributed greedy set-partitioning and set-covering algorithms "with low ratio bounds" and low complexity. They cover overlapping coalitions and precedence-ordered tasks and are any-time.
  - Source: Shehory & Kraus, "Methods for task allocation via agent coalition formation", Artificial Intelligence 101(1–2):165–200, 1998, https://www.ri.cmu.edu/publications/methods-for-task-allocation-via-agent-coalition-formation — **Medium** (abstract; exact bound not read).
- **Multi-robot coalition formation.** Adapts Shehory & Kraus to physical robots (sensor/capability constraints, coalition imbalance, fault tolerance). RACHNA is a market-based coalition-formation system.
  - Sources: Vig & Adams, "Multi-robot coalition formation", IEEE T-RO 22(4):637–649, 2006 — **Low** (venue not confirmed by search); Vig's 2006 Vanderbilt dissertation, https://ir.vanderbilt.edu/handle/1803/14147 — **Medium**.
  - Service & Adams state that coalition formation with m tasks is NP-hard to approximate within O(m^(1−ε)): "Coalition formation for task allocation: theory and algorithms", JAAMAS 22(2):225–248, 2011 — **Medium** (via search snippet).
- **Complex tasks with markets.** Task trees let robots bid on decompositions as well as tasks.
  - Source: Zlot & Stentz, "Market-based multirobot coordination for complex tasks", IJRR 25(1):73–101, 2006 — **Medium**.
- **CCBBA (coupled-constraint CBBA).** Extends CBBA to assignment couplings (a task's value depends on whether another is assigned) and temporal couplings (on when it is done relative to another), with pessimistic or optimistic bidding.
  - It outperforms the baseline "particularly for task-rich scenarios".
  - Plain CBBA "only considers homogeneous agents and independent tasks" (as later works note).
  - Source: Whitten, Choi, Johnson, How, "Decentralized Task Allocation with Coupled Constraints in Complex Missions", ACC 2011, https://skoge.folk.ntnu.no/prost/proceedings/acc11/data/papers/0813.pdf — **High**.
- **Cooperative cargo carrying on lunar-analogue terrain.**
  - Hardware: two 800 kg LELR path-to-flight rovers (300 kg payload, 13 km/h max, 12 kWh) carried a 475 kg, 5.475 m cargo. A custom coupling leaves the rovers kinematically independent; the hold-down tolerates about 15 cm alignment error.
  - Results:
    - Relative separation error was 9.2 cm mean and 33.4 cm max.
    - On the CSA Analogue Terrain, runs of 347 m and 1,122 m had path RMSE of 6.6–6.9 cm.
    - Inter-rover convoy traffic was 13.83 KB/s with 33.7 ms mean latency on 2.4 GHz WiFi. Four-robot convoys showed 46–58 ms latency.
  - The sequence is cargo pickup, coupled convoy, then reverse-docking. Pickup maps are shared between the rovers.
  - The paper argues two smaller rovers give capacity plus flexibility: one can work alone while the other follows the LTV.
  - Source: Krawciw, Antonyshyn, Lilge, Olmedo, Rehmatullah, Desjardins-Goulet, Toupin, Barfoot, "Sharing the Load: Autonomous Multi-Rover Cargo Transport", arXiv 2510.18766v2, May 2026, https://arxiv.org/abs/2510.18766 — **High**.
- **Cooperative object transport review.**
  - Source: Tuci, Alkilabi, Akanyeti, "Cooperative object transport in multi-robot systems: a review of the state-of-the-art", Frontiers in Robotics and AI 5:59, 2018 — **Low** (not re-read; notes/03 flags that a "cost of transport jumps 1→2 robots" claim was snippet-only).
- **LunarHaul today (Repo).**
  - The marketplace does team lifts for oversize items with `TEAM_SETUP_H = 1.0` h of rendezvous and coupling (`lunarsim/engine.py`).
  - 1.6 t rovers move 40 % of the Phase-2 manifest; two lifting together move 55 % (README).
  - Team lifts today are drawn from the pooled fleet regardless of owner, with no payment split.

---

## 3. Mechanism design for multi-owner fleets

### Takeaway

When rovers belong to different companies, an allocator is also a market, and four properties cannot all be had at once in general: efficiency, incentive compatibility (truthful bids), individual rationality (no owner worse off than alone), and budget balance (no outside subsidy). VCG gives the first three and runs a deficit. It is also open to collusion by losing bidders and to shill identities, which matters with only 3–6 owners. Trade-reduction double auctions (McAfee) give truthfulness and budget safety by giving up the least valuable trade, which is cheap in thick markets and expensive in thin ones. The practical route in freight is an auction or exchange with ex-post gain sharing (Shapley-type), plus trust-building. Field surveys say finding a fair allocation rule and a trusted coordinator are the main obstacles. Ride-hailing gives a quantified "price of fragmentation": extra fleet grows as (m−1)·D, smaller operators pay disproportionately, and D falls with demand density. On the Moon, two features change the trade-offs:
- Costs are *verifiable*: odometry, energy logs and the shared trace make misreporting auditable, so mechanisms with verification (Nisan & Ronen) become plausible.
- A natural subsidiser exists: NASA as anchor customer could cover a VCG-type deficit.

### Findings

**Impossibility and standard mechanisms**
- **Myerson–Satterthwaite.** For one buyer and one seller with independent private values on overlapping ranges, no Bayesian incentive-compatible, individually rational mechanism is ex-post efficient without an outside subsidy.
  - Source: Myerson & Satterthwaite, "Efficient mechanisms for bilateral trading", J. Economic Theory 29(2):265–281, 1983, https://www.cs.princeton.edu/courses/archive/spr08/cos444/papers/myerson_satterthwaite83.pdf — **Medium** (citation and statement confirmed via secondary sources; PDF located, not read).
- **VCG.** Truthful and efficient; the payment rule is generally not budget-balanced (Green & Laffont 1977).
  - Sources: Vickrey, J. Finance 16(1):8–37, 1961; Clarke, Public Choice 11:17–33, 1971; Groves, Econometrica 41(4):617–631, 1973; Green & Laffont, Econometrica 45(2):427–438, 1977 — **Low** (standard results, not re-read).
- **Weaknesses of VCG in practice.** Ausubel & Milgrom list:
  - "non-monotonicity of the seller's revenues in the set of bidders";
  - "vulnerability to collusion by a coalition of losing bidders";
  - profitable "use of multiple identities" (shill bidding);
  - poor behaviour under budget constraints.
  - "Even losing bidders may possess profitable joint deviations, facilitating collusion."
  - Source: Ausubel & Milgrom, "The Lovely but Lonely Vickrey Auction", in Cramton, Shoham, Steinberg (eds.), Combinatorial Auctions, MIT Press 2006, pp. 17–40, https://ranger.uta.edu/~weems/NOTES6319/PAPERSONE/ausubelMilgrom.pdf — **High**.
- **McAfee double auction (trade reduction).** Dominant-strategy truthful for buyers and sellers and weakly budget-balanced (the auctioneer may keep a surplus). The inefficiency comes from "barring the least valuable profitable trade", so gains from trade are ≥ (1 − 1/q) of optimal with q efficient trades.
  - Computed: q = 2 → ≥ 50 %; q = 4 → ≥ 75 %; q = 10 → ≥ 90 %.
  - Source: McAfee, "A dominant strategy double auction", J. Economic Theory 56(2):434–450, 1992, doi:10.1016/0022-0531(92)90091-U — **Medium** (abstract and secondary statements of the bound).
- **SBBA.** A single price for all trades, so the auctioneer keeps nothing (strong budget balance). The same expected gain from trade as McAfee, but the guarantee holds only in expectation, because of a lottery that excludes at most one seller. It extends to spatially distributed markets with transit costs.
  - Source: Segal-Halevi, Hassidim, Aumann, "SBBA: a Strongly-Budget-Balanced Double-Auction Mechanism", SAGT 2016, arXiv 1607.05139, https://arxiv.org/abs/1607.05139 — **Medium**.
- **Mechanisms with verification.** When the mechanism can observe the agent's actual execution (for example, time taken), truthful mechanisms exist where unverifiable ones fail.
  - Source: Nisan & Ronen, "Algorithmic mechanism design", Games and Economic Behavior 35(1–2):166–196, 2001 — **Low** (not re-read). Relevance: rover telemetry makes reported costs checkable after the fact.
- **Strategyproof mechanisms for multi-agent path finding.**
  - Self-interested agents may misreport goals.
  - VCG needs an optimal outcome; with approximate solvers strategyproofness generally fails, unless the solver is "maximal-in-range" (optimal over a fixed restricted set).
  - Three strategyproof, individually rational mechanisms are tested on dozens to hundreds of agents.
  - Source: Friedrich, Zhang, Curry, Dierks, McAleer, Li, Sandholm, Seuken, "Scalable Mechanism Design for Multi-Agent Path Finding", IJCAI 2024, arXiv 2401.17044, https://arxiv.org/abs/2401.17044 — **Medium**.
  - This is the closest published "traffic + self-interest" robotics work found. It covers paths, not task allocation.
- **Interdependent task allocation with self-interested agents.** If tasks can fail, valuations become interdependent, and strategy-proofness is impossible with a single allocation round.
  - Source: Springer LNCS chapter, doi:10.1007/978-3-642-32729-2_5 — **Medium** (snippet).

**Horizontal collaboration in freight (numbers carried over from notes/03, B1–B4)**
- Joint route planning saves up to about 30 % (cooperative vs non-cooperative "around 20–30 %") (Cruijssen et al. 2007, IJPDLM 37(4):287–304).
- Other figures: courier up to 20 %; city logistics 25.6 % distance; forest transport 5–15 % (Frisk et al. 2010); shipper collaboration 19 % (Ergun, Kuyzu, Savelsbergh 2007).
- Impediments: a reliable party to lead and a fair allocation of benefits rank highest (Cruijssen, Cools, Dullaert 2007, TR-E 43(2):129–142).
- Most gain-sharing uses the Shapley value (Gansterer & Hartl 2018, EJOR 268(1):1–12).
- Grades: **Medium–High** per notes/03.
- **Request exchange between carriers.** Auction-based decentralized exchange is compared with no collaboration and with centralized planning, under the constraint that no carrier's profit falls: "horizontal collaboration pays off even in highly competitive environments".
  - The five-phase auction framework: request selection, bundling, bidding, winner determination, profit sharing.
  - Source: Berger & Bierwirth, "Solutions to the request reassignment problem in collaborative carrier networks", TR-E 46(5):627–638, 2010, https://ideas.repec.org/a/eee/transe/v46y2010i5p627-638.html — **Medium** (abstract; percentages not read).
- **Survey of 120 papers (2007–2017).** Carrier alliances and flow-controller collaboration are most studied. Managerial and technological implementation issues are under-studied.
  - Source: Pan, Trentesaux, Ballot, Huang, "Horizontal collaborative transport: survey of solutions and practical implementation issues", IJPR 57(15–16):5340–5361, 2019, doi:10.1080/00207543.2019.1574040 — **Medium**.

**Shared fleets and fragmentation (ride-hailing)**
- **Price of fragmentation (theory).** Splitting demand between independent mobility-on-demand platforms adds rebalancing cost. Under scaling, the excess either decays exponentially ("fragmentation-resilient") or grows as √θ ("fragmentation-affected"). Unequal market shares can make it grow linearly.
  - NYC data (about 335,000 trips per day) show the affected regime becomes likely at fine spatial resolution.
  - Source: Séjourné, Samaranayake, Banerjee, "The Price of Fragmentation in Mobility-on-Demand Services", Proc. ACM Meas. Anal. Comput. Syst. 2(2), 2018, arXiv 1711.10963, https://arxiv.org/abs/1711.10963 — **High** (full text summarised).
- **Cost of non-coordination (data, five cities).**
  - Model: m non-coordinating operators raise the total fleet by (m − 1)·D, with per-operator factor R(p) = D(1/p − 1) for demand share p. D falls with trip density and roughly linearly with traffic speed.
  - D values: Manhattan 2.52 %, Singapore 8.48 %, San Francisco 37 %, Curitiba 67.14 % per extra operator.
  - Singapore with three operators at 50/35/15 % shares: individual fleet increases of 8.48 %, 15.75 % and 48.05 %, against 16.96 % city-wide.
  - Fleet-sizing criterion: ≥ 95 % of trips served within 5 min.
  - Source: Kondor, Bojic, Resta, Duarte, Santi, Ratti, "The cost of non-coordination in urban on-demand mobility", Scientific Reports 12:4669, 2022, doi:10.1038/s41598-022-08427-2, https://pmc.ncbi.nlm.nih.gov/articles/PMC8933415/ — **High**.
- **Minimum fleet.** Optimal dispatching of 150 million NYC taxi trips needs a fleet about 30 % smaller than the one in use (a model result).
  - Source: Vazifeh, Santi, Resta, Strogatz, Ratti, "Addressing the minimum fleet problem in on-demand urban mobility", Nature 557:534–538, 2018, doi:10.1038/s41586-018-0095-1 — **Medium**.
- **LunarHaul's own law (Repo).** "The in-house penalty follows 20/e hours in effective vehicles per owner"; pooled dispatch stays 46–53 % below in-house fleets on the Phase-3 terrain (README). Kondor's R(p) is an independent functional form to test against.

**Multi-vendor robot traffic in practice**
- **Open-RMF.** Robots of unrelated vendors publish intended trajectories to a shared traffic schedule. Conflicts are resolved by peer-to-peer negotiation "similar to conflict-based search", and tasks are assigned across fleets by bidding. The design goal is that "multiple unrelated proprietary fleet managers cooperate with each other without changing the way those fleet managers are implemented".
  - There is no stable wire protocol yet, and users report high CPU during negotiation.
  - Sources: ROSCon 2024 "The State of Open-RMF", https://roscon.ros.org/2024/talks/The_State_of_Open-RMF.pdf; https://github.com/open-rmf/rmf_traffic — **Medium**.
  - This is the closest working analogue of a "Lunar ATC" for mixed-owner fleets.

---

## 4. Learned ("neural") allocation

### Takeaway

Learned allocators come in three families:
1. Graph-neural policies that output assignments directly, trained by RL or imitation (CapAM, ScheduleNet, RoboGNN).
2. Hybrids where a network learns scores or incentives and a classical solver does the assignment (BiG-CAM with Hungarian matching; GCN-scored CBBA; PPO-trained bidders inside CBBA, 2026).
3. Large-scale value-function RL dispatch in ride-hailing (DiDi), where a learned spatio-temporal value of a driver's position is added to a combinatorial matching.

The hybrids keep the solver's feasibility and conflict-free guarantees and are the right template for us. Evaluations typically:
- train on one size (for example 50–100 tasks, 2–7 robots) and test on larger ones;
- compare with expert heuristics, iterated local search, and sometimes MILP on small cases;
- report task completion rate and runtime with paired t-tests.

They seldom report out-of-distribution failure, communication loss or strategic agents. Documented pitfalls:
- poor generalisation beyond the training distribution (TSP: Joshi et al.);
- evaluation practices that the OR community does not accept (Accorsi et al.);
- reward mis-specification, seen in this repo's own PPO lander, which learned a slow, fuel-costly descent the reward did not penalise.

Gains in production are modest: low single-digit percent.

### Findings

- **CapAM (graph RL for MRTA with deadlines and capacities).**
  - Training: REINFORCE with rollout baseline; 100 epochs; 500,000 training samples of 100 tasks with 2–7 robots; about 10 min per epoch, about 17 h in total (Computed). Hardware not stated.
  - Results: about 85 ms per full task sequence vs 0.30 s (BiG-MRTA) and 1.0–1.3 s (iterated local search).
  - Task completion at 100 tasks: 34.6 / 51.1 / 74.9 / 94.8 % for 2 / 3 / 5 / 7 robots (CapAM P = 3), against 22.7 / 38.0 / 70.2 / 85.6 % for an attention-only RL baseline.
  - At 200 tasks (double the training size): 28.2–77.8 %.
  - Source: Paul, Ghassemi, Chowdhury, "Learning Scalable Policies over Graphs for Multi-Robot Task Allocation using Capsule Attention Networks", ICRA 2022, pp. 8815–8822, doi:10.1109/ICRA46639.2022.9812370, arXiv 2205.03321 — **High**.
- **BiG-CAM (learned incentive plus Hungarian matching).**
  - A graph-RL policy outputs bipartite edge weights; the Hungarian algorithm assigns.
  - Training: PPO (Stable-Baselines3), 5 M steps, about 21 h, on 50 tasks and 6 robots.
  - At the training size it matches the expert-designed incentive (p = 0.188), with much lower variance (SD 0.064–0.21 vs 0.57–0.88).
  - It is better at 250–500 tasks with few robots, slightly worse with many robots.
  - Source: Paul, Maurer, Chowdhury, "Bigraph Matching Weighted with Learnt Incentive Function for Multi-Robot Task Allocation", arXiv 2403.07131, 2024, https://arxiv.org/abs/2403.07131 — **High**.
  - This is the closest template to "learned bid plus classical clearing".
- **Graph attention scheduling by imitation.**
  - RA-L 2020: "high-quality solutions for about 90 % of test problems with 2–5 robots and up to 100 tasks, with up to 100× less computation time than exact solvers" (as summarised from the abstract).
  - ScheduleNet (RSS 2020) adds robot and proximity nodes to a simple temporal network, giving a heterogeneous graph that is "nonparametric in the number of tasks, robots and task resources". It is "end-to-end trainable via imitation learning on small-scale problems, generalizing to large, unseen problems".
  - Sources: Wang & Gombolay, "Learning Scheduling Policies for Multi-Robot Coordination With Graph Attention Networks", IEEE RA-L 5, 2020, doi:10.1109/LRA.2020.3002198 — **Medium**. Wang & Gombolay, "Heterogeneous Graph Attention Networks for Scalable Multi-Robot Scheduling with Temporospatial Constraints", RSS 2020, doi:10.15607/RSS.2020.XVI.094, https://roboticsproceedings.org/rss16/p094.html — **High** (abstract only; no numbers in it).
- **Neural bidding inside CBBA.**
  - Replaces CBBA's hand-crafted greedy score with a neural bidding policy and keeps the auction and consensus phases.
  - Training is centralized, execution decentralized, from partial local observations. PPO is used, with reward based on closeness to MILP-optimal solutions. Neural Additive Model, LSTM and Set Transformer are compared.
  - Reported: better solution quality than classical CBBA across swarm sizes. No numbers in the abstract. Agents are cooperative; message loss is not addressed.
  - Source: Rodriguez, Tarawneh, Koenig, Dong, Lu, "Auction-Consensus Algorithm with Learned Bidding Scheme for Multi-Robot Systems", 23rd Int. Conf. on Ubiquitous Robots, arXiv 2605.21932, May 2026, https://arxiv.org/abs/2605.21932 — **Medium**.
  - **This is the closest prior art to a "learned bidding policy"; it must be cited.**
- **GCN-approximated CBBA score.**
  - Source: Chekakta, Aouf, Govindaraj, Polisano, De Cubber, "Towards Learning-Based Distributed Task Allocation Approach for Multi-Robot System", ICARA 2024, doi:10.1109/ICARA60736.2024.10553196, https://openaccess.city.ac.uk/id/eprint/33240 — **Medium**.
- **Ride-hailing dispatch at scale (DiDi).**
  - Xu et al. 2018: learning (a spatio-temporal value of drivers' states from history) plus planning (combinatorial matching each round), with online A/B tests. "Large-Scale Order Dispatch in On-Demand Ride-Hailing Platforms: A Learning and Planning Approach", KDD 2018, doi:10.1145/3219819.3219824 — **Medium** (method); the size of the A/B gains was **not verified** in this session.
  - Li et al. 2019: mean-field multi-agent RL, with gains in GMV and response rate in simulation on real data. "Efficient Ridesharing Order Dispatching with Mean Field Multi-Agent Reinforcement Learning", WWW 2019, arXiv 1901.11454 — **Medium**.
  - Qin et al. 2020: semi-MDP plus deep RL replacing myopic matching; 2019 INFORMS Wagner Prize. "Ride-Hailing Order Dispatching at DiDi via Reinforcement Learning", INFORMS J. Applied Analytics 50(5), 2020, doi:10.1287/inte.2020.1047 — **Medium**.
  - Eshkevari et al. 2022: TD value updates, a tuned utility, and bandit-based graph pruning gave "over 1.3 %" more total driver income in A/B tests, and "up to 5.3 %" in major metrics by causal analysis after full deployment. "Reinforcement Learning in the Wild: Scalable RL Dispatching Algorithm Deployed in Ridehailing Marketplace", arXiv 2202.05118 — **High** (abstract).
- **Multi-agent RL building blocks.**
  - MAPPO is PPO with a centralized value function and decentralized actors (centralized training, decentralized execution). It is strong on four benchmarks with minimal tuning; "high data reuse is detrimental", so use fewer epochs per batch. Source: Yu, Velu, Vinitsky, Gao, Wang, Bayen, Wu, "The Surprising Effectiveness of PPO in Cooperative Multi-Agent Games", NeurIPS 2022 Datasets & Benchmarks, arXiv 2103.01955 — **Medium**.
  - QMIX: Rashid et al., ICML 2018 — **Low** (not re-read).
- **Imitation of an expert.** DAgger (dataset aggregation) avoids the compounding errors of plain behavioural cloning. Source: Ross, Gordon, Bagnell, AISTATS 2011, PMLR 15:627–635 — **Medium**.
  - Repo precedent: the v3 learned lander is a DAgger clone. It lands inside the touchdown box 89.0 % of the time, against 93.8 % for its teacher and 63.2 % for PPO on the shaped reward (README).
- **Generalisation pitfall.** Neural TSP solvers do well on training sizes but "struggle to generalize" zero-shot to larger instances; the authors call for rethinking evaluation protocols.
  - Source: Joshi, Cappart, Rousseau, Laurent, "Learning the travelling salesperson problem requires rethinking generalization", Constraints 27(1–2):70–98, 2022, doi:10.1007/s10601-022-09327-y — **Medium**.
- **Evaluation pitfall.** ML-for-routing papers are "seldom employed" by OR practitioners, partly because of evaluation practice. The paper proposes a common testing setup: same instances, time limits, hardware reporting, and comparison to strong classical heuristics.
  - Source: Accorsi, Lodi, Vigo, "Guidelines for the computational testing of machine learning approaches to vehicle routing problems", Operations Research Letters 50(2):229–234, 2022, doi:10.1016/j.orl.2022.01.018 — **Medium**.
- **Tuning pitfall in decentralized MRTA.** Configurations selected under one communication condition do not transfer to another; select and evaluate on disjoint scenarios (Lott & Honary 2026a) — **High**.
- **Reward hacking.** A policy optimises the reward as written, not the intent. In-repo example: the PPO lander's slow, fuel-costly descent (Repo). In dispatch, the analogous failures are starving low-priority items, refusing team lifts, or gaming a deadline metric by never accepting hard jobs. Literature: Skalse et al., "Defining and characterizing reward hacking", NeurIPS 2022 — **Low** (not re-read).

**What a credible, small, CPU-trainable "neural dispatch/bidding policy" looks like.** This is design guidance derived from the sources above.
- *Role.* A per-rover scoring network that outputs a correction to the hand-crafted bid:
  - bid = marginal job hours (as in `dispatch._bid`) + g_θ(features);
  - the auction or consensus, feasibility checks and team-lift rules stay unchanged.
  - The network never assigns directly, so conflicts and infeasible plans cannot come from it. This is the BiG-CAM / neural-CBBA pattern at a much smaller scale.
- *Inputs (about 12, all locally observable on a rover or from its mesh neighbours):*
  - approach hours; loaded hours; item priority and age;
  - rover state of charge; hours to the next night; hours until the Earth link changes on that leg (`comms.EarthLink.next_change`);
  - number of waiting items within reach; number of free rovers within radio range;
  - owner-match flag; team-lift flag; message loss seen in the last hour.
- *Size.* Two hidden layers of 32 units: 12·32 + 32·32 + 32 + biases ≈ 1.5k parameters (Computed). It runs in microseconds in Python and in the browser. Export to JSON as the lander and rover policies already are.
- *Training.*
  - Stage 1, imitation with DAgger: label each auction decision with the choice of a full-information teacher. The teacher can be the existing pooled marketplace with perfect links and a 24 h look-ahead of known landings, or `central_assign` with full information. Use a listwise cross-entropy loss over candidate rovers ("learning to rank bids").
  - Stage 2 (optional): fine-tune θ by cross-entropy-method search on the simulator's objective, using a few hundred simulated years. This avoids PPO's sample cost; BiG-CAM needed 5 M steps.
  - Both stages are CPU, single process. The actual sim-year cost should be measured before committing to stage 2.
- *Honesty checks.*
  - A linear model on the same features: if it matches the MLP, say so.
  - The hand-crafted bid alone.
  - The teacher (upper reference).
  - Held-out seeds, demand phases, fleet sizes, loss rates and owner mixes.
  - DMG check if used inside CBBA: a per-task additive term that does not depend on the bundle keeps marginal gains non-increasing (Computed reasoning). A bundle-dependent learned term can break CBBA's convergence guarantee. SSI has no such requirement.
- *Name.* "Learned bid-correction network inside a sequential auction" is accurate. "Neural traffic network" would overstate it.

---

## 5. Space-specific record

### Takeaway

Only one multi-rover autonomy system is being prepared for flight, NASA/JPL's CADRE. It uses a centralized planner on an elected leader, a lightweight distributed database and a mesh radio, and it re-elects the leader on each wake cycle. It is one owner, three rovers plus a base station, and science exploration, not logistics. Lunar multi-robot task-allocation papers exist (an IAC 2024 improved CBAA with payload, priority, lunar night and cooperative tasks; a 2024 ISRU auction hierarchy in a ROS2 simulator; ESA/DLR heterogeneous-team analogue campaigns), but they are single-owner and do not model Earth-link windows. "Lunar surface traffic management" has appeared at GLEX 2025 as a regulatory discussion (ispace), and at COPUOS as operator coordination of landing sites. Neither contains allocation algorithms or numbers. DARPA SubT showed how teams actually cope with denied comms: mesh networks, droppable relays, data mules, time budgets out of contact, and in the winning team, single-robot autonomy only.

### Findings

- **CADRE architecture.**
  - Three rovers plus a base station on the lander. Ground gives a high-level task network.
  - A centralized planner (MEXEC-based) runs on an *elected leader*; every agent executes. On any constraint violation the leader stops all agents and replans.
  - Leader election favours agents furthest from thermal and power limits; on a leader change, in-progress tasks stop and the new leader replans.
  - Source: Rabideau, Russino, Branch, Dhamani, Stegun Vaquero, de la Croix, Rossi, "Multi-Robot Cooperative Autonomy on the Moon: The CADRE Technology Demonstration Mission", ASTRA 2025, https://ai.jpl.nasa.gov/public/documents/papers/CADRE-ASTRA-2025-Extended-Abstract.pdf — **High**.
- **CADRE details.**
  - Election: GHS minimum spanning tree to find a unique "appointer", then a convergecast of health metrics, then a broadcast of the chosen leader, repeated periodically. The design separates "finding a unique agent" from "finding the best leader".
  - The slides describe the coordination choice as "centralized on an elected leader, while execution is distributed", over a mesh protocol.
  - 30-minute wake–sleep cycles handle heat; the leader is re-elected on each wake.
  - Sources: JPL CADRE AAMAS slides, https://ai.jpl.nasa.gov/public/documents/presentations/CADRE-AAMAS-Slides.pdf — **High**; NASA/JPL news, https://www.jpl.nasa.gov/news/nasas-trio-of-mini-rovers-will-team-up-to-explore-the-moon — **Medium**.
  - Papers behind it:
    - de la Croix et al., "Multi-Agent Autonomy for Space Exploration on the CADRE Lunar Technology Demonstration", IEEE Aerospace 2024, doi:10.1109/AERO58975.2024.10521425 — **Medium**.
    - Albee et al., "Lunar Leader: Persistent, Optimal Leader Election for Multi-Agent Exploration Teams", MASSpace 2024 — **Medium**.
    - Rabideau et al., AAMAS 2025, https://www.ifaamas.org/Proceedings/aamas2025/pdfs/p1727.pdf — **Medium**.
    - Saboia et al., "CADRE MoonDB", MASSpace 2024 — **Medium**.
- **CADRE status.** Manifested on Intuitive Machines IM-3 (Reiner Gamma). Older dates (2025, early 2026) have passed. Wikipedia lists NET Q1 2027 — **Medium** (secondary; check before citing).
- **Lunar CBAA (IAC 2024).** An improved Consensus-Based Auction Algorithm for lunar multi-robot systems. It models:
  - payload effects on speed and energy;
  - priority constraints;
  - a load-dependent collision radius;
  - lunar phases and night hibernation;
  - "turn-in" bidding for cooperative tasks.
  - It argues centralized methods "struggled to poor communication conditions".
  - Source: Zhang, Li, Zheng, Ouyang, Sun, Guo, Li, Jing (Northwestern Polytechnical Univ.), "Research on task allocation method for multi-agent systems on the Moon with a distributed architecture", IAC-24, A3, IP, paper 86984, https://iafastro.directory/iac/archive/browse/IAC-24/A3/IP/86984/ — **High** (abstract; no results seen).
- **Lunar ISRU auction hierarchy.** Scouts, excavators and haulers; three policies for multiple simultaneous auctions; a MURDOCH variant; pyrobosim (2D ROS2).
  - Source: Kashid & Kumat, "Hierarchically Decentralized Heterogeneous Multi-Robot Task Allocation System", arXiv 2405.02484, 2024 — **Medium**.
- **Earlier lunar-construction allocation.** PRO-ACT (i-SAIRAS 2020) and an IFAC 2025 MIQP/MPC construction allocator (16.4 % faster build, 16.0 % less energy) are already listed in the novelty note — **Medium**.
- **ESA heterogeneous teams.** Decentralized allocation for walking robots with limited communication. Nodes "continuously synchronize the databases and resolve conflicts … such as when two robots have claimed the same task".
  - Source: Schnell et al., ASTRA 2023, https://robotics.estec.esa.int/ASTRA/Astra2023/2023%20PAPERS/87_Schnell_Autonomous%20cooperation%20of%20intelligent%20heterogeneous%20robots%20in%20realistic%20planetary%20and%20lunar%20exploration%20scenarios.pdf — **Medium** (snippet).
- **DLR ARCHES.** Rovers and a drone on Mt Etna: automated task planning, high-level mission control, collaborative multi-robot SLAM, autonomous sample return.
  - Source: Schuster et al., "The ARCHES Space-Analogue Demonstration Mission", IEEE RA-L 5(4):5315–5322, 2020 — **Medium**.
- **Lunar surface traffic management (ispace, GLEX 2025).** Raises right-of-way, passing and signalling rules for roads; liability; crewed vs uncrewed regimes; and maritime rules as a model. No algorithms or numbers in the abstract.
  - Source: Kim, Li, Wang, "Lunar Surface Space Traffic Management: Considerations for Future Regulations", GLEX-2025, 11, IP, 15, x93808, https://iafastro.directory/iac/archive/browse/GLEX-2025/11/IP/93808/ — **Medium**.
- **Operator coordination at the south pole.** A proposed COPUOS action team would share south-pole landing plans and coordinate site selection; current coordination is manual.
  - Source: UNOOSA STSC 2024 non-paper (Romania), https://www.unoosa.org/documents/pdf/copuos/stsc/2024/np/STSC-2024-Non-Paper-Romania_Action-Team-on-Lunar-ConsultationsE.pdf — **Medium**.
- **DARPA SubT, communications (CoSTAR/JPL ACHORD).**
  - Silvus MIMO mesh radios, droppable relays, and robots acting as relays or data mules.
  - Data stratification and flow control: requiring ordered receipt for all mission-critical topics built large queues and congestion after reconnection.
  - Results by test: 4–6 radios deployed; maximum delay 13 s / 1 s / 6 s / 7 s; effective range 49–1,058 m; up to about 20 Mbps from six exploring robots; comms "over more than 150 meters of exploration".
  - Lesson: a robot stuck out of range had its data recovered by another acting as relay, so "equipping high-level decision-making with inter-robot comms models is key", and high-fidelity network simulation would have helped.
  - Source: Saboia et al., "ACHORD: Communication-Aware Multi-Robot Coordination With Intermittent Connectivity", IEEE RA-L 7(4):10184–10191, 2022, arXiv 2206.02245 — **High**.
- **DARPA SubT, the winning team (CERBERUS).**
  - One human supervisor; an ad-hoc mesh with "breadcrumb" relays ferried by legged robots.
  - Out-of-contact exploration ran on a supervisor-given *time budget*, after which a homing timer brings the robot back.
  - "For our team only single-robot autonomy was deployed despite multi-robot coordination methods being developed … significantly more field testing … necessary."
  - Source: Tranzatto et al., "Team CERBERUS Wins the DARPA Subterranean Challenge: Technical Overview and Lessons Learned", Field Robotics 2, 2022, arXiv 2207.04914 — **High**.
- **Lunar link geometry for our base (Repo / Computed).**
  - Earth is visible from BASE about 50 % of the time (LOLA 18.6-year map), from DEPOT 37 % and from ISRU or SCI_1 never. Windows are about 14 days on and 14 days off.
  - DTE-only yearly coverage is 17–43 %, versus 80–86 % with one relay (LCRNS) (`research_notes/Lunar communications and visibility/earth_visibility_prior_art.md`).
  - Smooth-sphere radio horizon on the Moon (R = 1,737.4 km) is √(2Rh): about 2.6 km for a 2 m rover antenna, so about 5.3 km rover-to-rover, and about 5.9 km for the 10 m BASE mast. Terrain shortens this. Inter-rover coordination traffic is small (13.8 KB/s even for convoy control, Krawciw et al.).

---

## 6. What this means for our simulation

### 6.1 Design principle

The question "does an on-Moon network help?" mixes two effects:
- **sharing**: rovers of all owners can serve all cargo;
- **availability**: decisions can be made when Earth is out of sight.

Cross them, so each effect can be measured on its own. Then add the variants of on-Moon decision-making and a full-information oracle. Keep rover autonomy fixed at "autonomous" in the main experiment. Teleoperation is already handled by the Phase-4 comms rule and would confound the dispatch effect.

### 6.2 Conditions (mapped to existing code)

| Code | Who can serve whom | Where decisions are made | When decisions can be made | Allocator | Existing code |
|---|---|---|---|---|---|
| A-Earth | each owner only | Earth (owner's control room) | only while BASE gateway sees Earth; between windows, rovers run the queue uploaded before loss of signal (LOS) | in-house greedy | `inhouse` + new window gate |
| A-Moon | each owner only | on each owner's lead rover | always (owner's own mesh) | in-house greedy | `inhouse` |
| B-Earth (user's "b") | pooled | shared dispatcher on Earth | only in Earth-link windows; plan-ahead queue between windows | pooled marketplace or batched Hungarian | `marketplace`, `central_assign` + gate |
| B-Earth-relay | pooled | Earth | 80 % or 100 % coverage (relay) | same | same + coverage factor |
| C-Leader | pooled | elected leader on the Moon (CADRE-style) | always, but only rovers in the leader's mesh partition | central marketplace on the leader | `marketplace` restricted to partition |
| C-Auction (user's "c", hand-crafted) | pooled | every rover; decentralized SSI with rebroadcast of winners, or CBBA | always; messages limited by line of sight and loss | marginal-insertion bids | new |
| C-Learned (user's "c") | pooled | every rover | as C-Auction | bids + learned correction g_θ | new |
| O (oracle) | pooled | omniscient | always, perfect links | pooled marketplace with perfect information | `marketplace` |

Two fallback rules for the Earth conditions should both be run; the truth lies between them:
- *strict*: no new assignments during blackouts;
- *plan-ahead*: before LOS, upload a queue covering the expected blackout, built from the known landing schedule.

### 6.3 Factors and levels

| Factor | Levels | Basis |
|---|---|---|
| Load (utilisation) | about 10 %, 30 %, 60 % (via demand phase P2/P3 and fleet 4–8) | Allocation quality is invisible at the current 4.6 % (Repo); Kondor: coordination value depends on density |
| Owners and shares | 2, 3, 5 owners; equal shares and 50/35/15 | Kondor's Singapore split; Repo's fragmentation law |
| Message loss | Bernoulli 0, 0.10, 0.25, 0.40; Gilbert–Elliott burst variant | Lott & Honary; Otte et al.; Nayak et al. |
| Radio links | line of sight on the 5 m DEM with 2 m rover and 10 m mast antennas, multi-hop; plus "perfect" | Computed horizon about 2.6–5.9 km; ACHORD/CERBERUS mesh practice |
| Earth link | DTE at BASE (`earth_link-v1`, `any_part`); DTE + mast; 80 % relay; 100 % | Earth-visibility note |
| Team-lift share | 0, 10, 25 % of items need two rovers (cross-owner allowed or not) | notes/03 C2; Krawciw |
| Bundle depth or look-ahead | 1, 2, 5 items | Lott & Honary: shallow under loss |
| Payment rule (pooled cells) | none (cooperative); first-price; per-item second-price; posted price + Shapley gain sharing | §3 |

The full factorial is too large. Recommended structure:
- **E-A (main).** Coordination condition × load × Earth link, at 3 owners with equal shares, 0.10 loss, 10 % team lifts. 8 × 3 × 4 = 96 cells.
- **E-B (comms robustness).** C-Auction / C-Learned / C-Leader × loss × burst model × bundle depth, at 30 % load.
- **E-C (owners and incentives).** Owners × shares × payment rule, at 30 % load, with the strategic-deviation test below.
- **E-D (team lifts).** Team-lift share × cross-owner allowed × loss, with a two-phase commit and timeout (sweep 0.5, 1, 2 h).

Use 30 seeds per cell with common random numbers across conditions, as the repo does. Report paired-bootstrap 95 % CIs (Lott & Honary use 20,000 resamples) and use `precision.py` to add seeds where CIs are wide.

### 6.4 Metrics

- **Primary:** mean and 95th-percentile delay of urgent cargo (h); delivered-within-deadline rate.
- **Efficiency:** loaded vs empty hours (deadhead share); utilisation; regret vs oracle O (%); "price of fragmentation" = (A − B) / B per owner. Fit Kondor's R(p) = D(1/p − 1) against the Repo's 20/e law.
- **Coordination health:** messages per rover-hour; duplicate assignments; unassigned-task-hours while a feasible rover was free; for team lifts, rendezvous wait (h), failed rendezvous (count) and partner no-shows.
- **Blackout exposure:** share of time each condition could not assign; backlog at end of each blackout.
- **Owners:**
  - per-owner profit and individual rationality (IR) violations, i.e. owners worse off than in A-Moon;
  - smallest-owner penalty;
  - operator budget surplus or deficit per year (payment rules);
  - **manipulability**: the largest profit gain an owner gets by scaling its bids by k ∈ {0.8, 0.9, 1.1, 1.25} while others bid honestly, and the system delay cost of that deviation.
- **Learned policy:** regret vs teacher and vs hand-crafted; the same metrics on out-of-distribution test sets; counts of starved items (age > 7 days), refused team lifts, and deadline-gaming flags (reward-hacking guards).
- **Compute:** decision time per auction call (Python); must stay well under the event time scale.

### 6.5 Hypotheses to pre-register (with the literature anchor for each number)

- **H1 (sharing).** Pooled vs alone at 30–60 % load reproduces the Repo's 46–53 % reduction in urgent delay. With 50/35/15 shares, the smallest owner gains most (Kondor: 48 % vs 8.5 % fleet penalty).
- **H2 (availability).** B-Earth's loss vs O grows with blackout fraction. The strict fallback loses most of the pooling gain during roughly 14-day DTE blackouts at BASE (about 50 % visibility). Plan-ahead recovers part of it. An 80 % relay recovers most. *This is the central new measurement; no prior number exists.*
- **H3 (decentralization cost).**
  - At ≤ 0.10 loss with line-of-sight links, C-Auction is within 10 % of O on urgent delay (CBBA/SSI "over 90 %"; +11–13 % makespan only at 40 % loss for the best methods).
  - At 0.25–0.40 loss, deep bundles lose 15–65 % and shallow bundles less (Lott & Honary 2026a).
  - C-Leader matches C-Auction unless the mesh partitions (Gerkey: centralized is preferable below about 200 robots when links allow; CADRE practice).
- **H4 (learning).** C-Learned beats C-Auction by a few percent at 30–60 % load and by nothing measurable at 10 % load. Out of distribution it may be worse than C-Auction (Joshi et al.; production RL gains of 1–5 %). A linear model may capture most of the gain.
- **H5 (incentives).** Under first-price bids, an owner can gain by shading. Second-price per-item payments reduce but do not remove this, because SSI is not strategyproof across rounds (a reasoned expectation, not a cited result). Posted price + Shapley sharing gives IR for all owners in the coalitions tested (Gansterer & Hartl). Budget deficit or surplus is reported, not assumed away (Myerson–Satterthwaite).
- **H6 (team lifts).** Cross-owner team lifts raise the share of the manifest that can move (Repo: 40 % → 55 % with pairs). Under loss, rendezvous failures rise unless there is a commit-and-timeout protocol (CCBBA timing constraints; Otte: rebroadcast helps).

### 6.6 Parameter values to start from

- Earth link: `data/comms/connecting_ridge/earth_link-v1.json`, criterion `any_part`; BASE about 0.50; relay coverage 0.80–0.86 or 1.0.
- Radio: line of sight on the 5 m DEM; antennas 2 m (rover) and 10 m (mast); smooth-sphere limits 2.6 / 5.3 / 5.9 km (Computed); per-message Bernoulli loss as above; Gilbert–Elliott with mean burst of about 10 messages (assumed; sweep).
- Team-lift setup: `TEAM_SETUP_H = 1.0` h (Repo); rendezvous timeout 1 h (assumed; sweep 0.5–2 h).
- Auction: rebroadcast previous winners every round (Otte et al.); bundle depth 1–2 under loss (Lott & Honary 2026a); `MAX_POOL = 40` (Repo).
- Payments: per-item second price; posted price per tonne-km. Shapley gain sharing by Monte-Carlo permutations over owners (exact for ≤ 5 owners: 2⁵ = 32 coalition runs per seed, Computed).
- Learned policy: MLP 12-32-32-1 (about 1.5k parameters); DAgger 5 iterations; at most a few hundred sim-years of CEM fine-tuning, after timing one sim-year.

### 6.7 Validation of the new pieces (link to `verification_plan.md`)

- **Degenerate checks:**
  - C-Auction with perfect links and bundle depth 1 must equal the existing pooled marketplace on the same seeds.
  - B-Earth with 100 % coverage must equal the same pooled mechanism.
  - A-Earth with 100 % coverage must equal `inhouse`.
- **Literature checks:**
  - Reproduce the qualitative Lott & Honary result on a toy grid: under 25 % loss, the best bundle depth moves from deep to shallow.
  - Reproduce Kondor's direction: the smallest owner bears the largest per-owner penalty.

---

## 7. Novelty check

**Already published (do not claim):**
- Decentralized auction and consensus allocation under message loss, with algorithm rankings and degradation curves: Otte 2020; Nayak 2020; Bapat 2022; Cao 2025; Lott & Honary 2026a, b.
- Coupled-constraint and coalition variants of CBBA: Whitten 2011. Market-based complex tasks: Zlot & Stentz 2006.
- Learned bids or scores inside an auction or a matching: Rodriguez et al. 2026 (PPO-trained neural bids in CBBA); Chekakta 2024 (GCN score in CBBA); BiG-CAM 2024 (learned incentive + Hungarian). Learned communication in CBBA: Raja.
- GNN/attention MRTA policies trained by RL or imitation: CapAM, ScheduleNet, RA-L 2020.
- Industrial RL dispatch: DiDi.
- Quantified price of fragmentation and smallest-operator burden: Séjourné 2018; Kondor 2022.
- Horizontal collaboration savings and gain sharing in freight (notes/03).
- Lunar decentralized auction with payload, night, priority and cooperative tasks: IAC 2024 NPU. Lunar ISRU auctions: Kashid 2024.
- Elected-leader centralized planning with mesh on the Moon: CADRE.
- Multi-vendor robot traffic negotiation in practice: Open-RMF.
- Strategyproof mechanisms for multi-agent path finding: Friedrich et al. 2024.
- Two-rover lunar cargo carrying hardware: Krawciw 2026.
- Lunar surface traffic regulation: ispace GLEX 2025.

**Not found in this search (candidate contributions, in order of defensibility):**
1. **Earth-link geometry → dispatch availability → logistics outcome, for shared vs separate fleets.** No paper compares an Earth-side shared dispatcher limited to real terrain-masked DTE windows against on-Moon allocation, measured in cargo delay and $/kg. This combines the repo's R-1 Earth-visibility data with its marketplace. *Defensibility: high.*
2. **Allocation among self-interested owners with payments, individual rationality and a manipulability test, in a robot fleet.** Freight and ride-hailing study gain sharing and fragmentation; robotics MRTA assumes cooperative robots. The MAPF mechanism-design paper is about paths. A multi-owner rover market with measured IR, budget balance and bid-shading gains appears new. *Defensibility: medium-high.* Grogan & de Weck 2012 (federated space-resource economy) must be read first; it is still unread (novelty note).
3. **Cross-owner two-rover coalitions with rendezvous risk under message loss, at logistics level.** Coalition-allocation and cooperative-carrying papers are single-owner and do not price rendezvous failures. *Defensibility: medium.*
4. **Line-of-sight lunar mesh from a real DEM as the communication model for allocation.** Prior comm-loss studies use i.i.d. or bursty loss on grids. *Defensibility: medium.* It is incremental in method, but new in setting.
5. **A small learned bid-correction network.** Learned bidding is published (Rodriguez et al. 2026). Our version is new only in its inputs (Earth-link timing, night, owner, team lift), in being evaluated under the conditions above, and in being tested against a linear model and out of distribution. *Defensibility: low as a standalone claim.* Present it as a component, not the contribution.

**Phrasing to avoid:** "first neural traffic network on the Moon", "neural ATC". The learned part is a small scorer inside a classical auction. Recommended framing: "an on-Moon, multi-owner allocation layer whose value is measured against an Earth-side dispatcher that works only while Earth is in sight".

---

## 8. Gaps and items to verify

- **Not read in full:**
  - the Choi et al. 2009 proofs (the 50 % bound is quoted via Whitten et al. 2011);
  - McAfee 1992 and Myerson–Satterthwaite 1983 (statements via secondary sources);
  - the Xu et al. 2018 KDD A/B numbers;
  - Korsah 2013 definitions;
  - Shehory & Kraus 1998 ratio bounds;
  - Rodriguez et al. 2026 results (abstract only);
  - Cao et al. 2025 (RA-L) and Verma et al. 2025 (IEEE Access), which are cited by Lott & Honary;
  - the CADRE AAMAS 2025 paper.
- **Venue not confirmed:** Vig & Adams 2006 (IEEE T-RO 22(4):637–649) was not confirmed by search; only the dissertation was.
- **CADRE launch date:** conflicting sources (NET H2 2026 vs Q1 2027).
- **Unread prior art:** Grogan & de Weck 2012 (federated decentralized space-resource economy) is the main item to read before claiming novelty point 2.
- **No source found** for decentralized-vs-centralized-optimal gaps on a pickup-and-delivery problem under range limits. The repo would be generating that number.
- **Search log (main queries):**
  - Otte auctions under communication limits; CBBA 50 % bound; ACBBA; Dias market survey; Nayak comparison; Kalra/Dias comparative study; CCBBA;
  - Shehory & Kraus; Korsah iTax; Vig & Adams; price of fragmentation; Kondor non-coordination; Open-RMF negotiation; McAfee; Myerson–Satterthwaite; Ausubel & Milgrom; SBBA; MAPF mechanism design; Berger & Bierwirth; Pan et al. survey; Vazifeh minimum fleet;
  - DiDi KDD 2018 / WWW 2019 / INFORMS 2020 / RL in the wild / V1D3; CapAM; ScheduleNet; learned bidding in CBBA; BiG-CAM; Joshi TSP generalisation; Accorsi guidelines; MAPPO;
  - CADRE (architecture, status); ispace GLEX 2025; ARCHES; LunA-10; SubT (Annual Review not found; ACHORD; CERBERUS); lunar CBAA (IAC 2024); lunar ISRU auction; mechanism design for self-interested robots.
