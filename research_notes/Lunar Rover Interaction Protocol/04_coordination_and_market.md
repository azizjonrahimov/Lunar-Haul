# Lunar Rover Interaction Protocol, note 04: coordination as a team, market and reality (current to 2026-11-11)

Scope. Sections 6 (coordination as a team) and 8 (market and reality) of the owner's question list: task
allocation, central or decentral control, collision avoidance and narrow passages, failure hand-over, autonomy
under Earth latency; who is doing this already, who would pay, and how to test on Earth. Positioning and time,
maps, and communications / protocol / security are in the other notes of this folder and are not repeated.

This note builds on, and does not repeat, `research_notes/Lunar ATC/multi_owner_allocation.md` (cited as [MOA]),
`research_notes/Lunar ATC/traffic_and_safety.md` ([TS]), `.team/PLAN-phase5.md` (H1 to H8) and the three papers
`paper/p1`, `paper/p2`, `paper/p3` ([P1], [P2], [P3]; numbers taken from their `values.json`).

How to read the evidence tags.
- **Opened** = the page or PDF was fetched and read in this session (list in section I.3, with URL).
- **Snippet** = seen only in a search-result summary; the page was not opened. Every such claim carries the word
  UNVERIFIED and says what was tried.
- **Repo** = a number from this repository's notes or papers; its grade is given there.
- **Computed** = arithmetic done for this note (script kept in the session scratchpad, formulas in section E).

Method. About 50 web searches and 55 page reads; 15 PDFs downloaded and read as text with `pymupdf` (CADRE:
AAMAS 2025 paper, ASTRA 2025 abstract, MASSpace 2024 slides, the leader-election and MoonDB papers, a JPL
hardware talk; NASA/TM-20240001217 on LTV teleoperation; NASA's VIPER slides of April 2026; ORCA; CBBA with
partial replanning; Whitten et al. 2011; Olsen and Wood 2004; OmniLRS; ispace's March 2026 release; the IDA
lunar-demand report). MIT DSpace (the CBBA journal paper), CORE, The Engineer, GovConWire and the LSIC site were
not reachable (403, 429 or time-out); what rests on them is marked.

---

## A. One-page summary: the eight answers

1. **How to allocate tasks.** Use an auction that the robots run themselves, one job per robot at a time, with a
   leader's central plan as the normal mode when the mesh is whole. The published guarantees are loose (auction
   cost at most 2 times optimal; CBBA score at least 50 % of optimal under diminishing marginal gain) and real
   results are far better; our own runs put the robots' auction within 0.8 h of a full-information marketplace
   at 10 % message loss [P1]. The only system built for flight, NASA's CADRE, does not use an auction: one
   elected rover plans for all three.
2. **Central or decentral.** Neither alone. A planner on the Moon (base computer or elected rover) with an
   auction as fallback gave the same urgent wait as a full-information marketplace in our runs (14.9 h against
   14.9 h) and lost only 1.0 h at 40 % message loss, where the pure auction lost 3.9 h [P1]. What must not be
   central is Earth: a dispatcher on Earth that stops when Earth sets cost 89.9 h of extra wait [P1], and
   referring road conflicts to Earth raised delay 5.1 times [P2].
3. **Collisions and narrow passages.** Two layers. Road segments are reserved in time, and a vehicle never
   enters a segment whose reservation it has not had confirmed; on board, speed is capped so that the vehicle
   can stop inside what it can see. Reservation gives a proof (section E.2); reactive methods such as ORCA
   guarantee only the next few seconds and can deadlock. Our rules gave no violation in 11 of 12 encounter types
   and cost 0.1 % delay at today's fleet [P2]; the open hole is a vehicle that stops dead in a one-lane segment.
4. **A rover breaks down.** Neighbours detect silence by missed heartbeats, the job goes back to auction with a
   higher epoch number, and the dead rover's road reservation stays held until someone sees it or tows it.
   Detection costs seconds to minutes on the Moon; if the decision waits for Earth the expected extra delay is
   about 54 h at our base (section E.5). CADRE handles loss of a rover the same way in outline: a new leader
   within 10 s, all tasks stopped and replanned.
5. **How much autonomy.** Everything that must be decided in less than about 10 s (stopping, giving way), and
   everything that cannot wait up to 11 days for Earth to rise (who takes which job, who passes first), must be
   decided on the Moon. Measured teleoperation from Earth falls from 3.24 km/h with no delay to 1.76 km/h at 8 s
   delay (NASA, 2024); VIPER plans 0.8 cm/s made good. One person can watch about five vehicles that need
   attention often, and tens of vehicles only when they rarely ask.
6. **Who is doing this.** Nobody has flown cooperating rovers on the Moon. CADRE (three rovers, one owner) is
   built and waiting; its lander IM-3 slipped to the first quarter of 2027. None of the US commercial landers
   planned for 2026 had launched by early November. NASA ordered two crew rovers from two companies in May 2026
   and added a nuclear rover and four hopping drones for 2028; China's Chang'e 8 (2028 to 2029) is planned to
   carry robots built by at least four organisations in three countries. Nobody found sells a coordination layer
   for vehicles of different makers.
7. **Customers.** In practice one: NASA's Moon Base programme and its contractors (CLPS 1 ceiling raised to
   4.2 billion USD, CLPS 2 awarded on 7 November 2026 with a 10 billion USD ceiling, two LTV task orders of
   about 220 million USD each). Published market sizes range from 94 to 566 billion USD summed to 2050 and
   differ by a factor of six; none sizes a coordination layer. The real need starts when three or more owners
   work one site, which the current plans put at 2028 to 2029.
8. **Testing on Earth.** Yes, in four stages: simulation (our engine plus an open lunar simulator), radio
   hardware in the loop with a channel emulator, three or more small rovers of two "owners" in a sand yard, then
   an analogue site. Each stage proves a different thing (section H). Facilities exist and can be requested, but
   ESA and DLR's LUNA hall is fully booked to June 2027.

---

## B. Evidence, question by question

### B.1 How should tasks be allocated among rovers?

**What the project has shown.**

| Result | Number | Where |
|---|---|---|
| Robots' auction against full-information marketplace, 30 % load, loss 0.10 | -0.84 h (90 % CI -2.6 to 0.7 h); equivalence within 10 % not shown | [P1] H3a |
| Elected leader against the same marketplace | +0.26 h (CI -1.8 to 1.2 h) | [P1] 5.4 |
| Message loss 0 to 0.40: extra urgent wait | leader +1.0 h (ns); auction +3.9 h (2.0 to 5.9) | [P1] E41 |
| Bundle depth 5 against depth 1 | +6.0 h at loss 0.25; +10.0 h at loss 0.40; stale claims 0 to 314 a year | [P1] E41 |
| Learned linear bid correction (13 weights) | urgent wait -16.5 % against hand-built bids; the 1,537-parameter network gave no gain | [P1] H4 |
| Cross-owner two-robot lifts | share of team items delivered 12 % to 93 % | [P1] H6 |
| Pooling across owners | urgent wait cut by 1,232 h (CI 1,076 to 1,401); 99.5 % of the gap is cargo owners alone never deliver | [P1] H1 |
| One auction round in a hundred, scaled to the flight processor | 1.12 s, above the 1 s target | [P3] |

So for this base the choice of allocator matters less than whether vehicles are shared at all and whether the
decision is taken on the Moon. Deep bundles (CBBA style) were worse than single jobs under loss.

**What the outside literature says.**

- *Taxonomy.* Gerkey and Mataric classify by single- or multi-task robots, single- or multi-robot tasks, and
  instantaneous or time-extended assignment; Korsah, Stentz and Dias add the dependency classes. Our single
  hauls are ST-SR and the two-rover lifts are ST-MR with cross-schedule dependencies (XD). Details and sources
  in [MOA] sections 1 and 2 (Repo, graded High and Medium there). Gerkey and Mataric's own advice for fewer than
  about 200 robots is a broadcast-based central assignment [MOA].
- *Sequential single-item auctions.* Total path cost at most 2 times optimal, lower-bound example 1.5 (Koenig
  et al. 2006; Repo [MOA], High). Greedy assignment is 2-competitive.
- *CBBA and CBAA (Choi, Brunet, How, IEEE T-RO 25(4), 2009).* Two phases: each robot builds a bundle greedily,
  then neighbours agree on winners. Statements read this session: CBBA "converges in O(n_t D) rounds of
  communication, where D is the network diameter", it "arrives at the same result as" the sequential greedy
  algorithm, "the sequential greedy solution achieves 50% of the optimal score", and "CBBA requires that the
  score function has diminishing marginal gains (DMG)" (Buckman, Choi, How 2019, section II.C; Opened [L1]).
  Whitten et al. 2011 say the same: with DMG "a provably good feasible solution is guaranteed (50% minimum
  performance bound)" (Opened [L2]). The journal paper's abstract page was opened; its PDF was blocked
  (HTTP 429), so the proof text itself is UNVERIFIED and section E.1 gives our own derivation, which reproduces
  1/2 in two cases and only 1/3 when the bundle limit binds.
- *Adding tasks after convergence.* CBBA with partial replanning resets only the last tasks of each bundle so
  that a new task is absorbed without a full re-auction and convergence is kept; a full reset takes O(n_t D)
  rounds again (Opened [L1]). This is the published basis for re-auctioning a single orphaned job.
- *Message loss.* Best decentralised allocators lose 11 to 13 % of makespan between perfect links and 40 %
  loss; deep bundles lose up to 65 % of travel at 25 % loss (Lott and Honary 2026; Repo [MOA], High). Our E41
  depth result agrees in sign.
- *What CADRE actually uses.* Not an auction. A central planner (JPL's MEXEC, task networks) runs on an
  elected leader and schedules "greedily ... in priority order", each task as close as possible to its preferred
  start, rejecting tasks that would break a constraint. For exploration the unknown region is cut into as many
  sub-regions as there are rovers and each rover explores its own by frontier search; for the radar experiment
  the leader plans one joint trajectory by sampling-based motion planning and hands each rover a time-stamped
  corridor. The authors state why: on the lunar surface "communication failures can result in complex and
  hard-to-diagnose miscoordination" in shared-world designs, and their design gives "reduced inter-agent
  communications compared to shared-world and auction-based approaches" (Rabideau et al., AAMAS 2025; Opened
  [C1]). Section D has the rest.
- *Lunar construction and excavation.*
  - ESA and ESRIC Space Resources Challenge, second edition (excavation and beneficiation; field test at the
    LUNA hall, October 2025 by Snippet): eight teams from six countries; winner Team BREMEN (DLR, DFKI) with a
    mobile excavation rover, Coyote III, and a stationary size-sorting unit; prize a 500,000 EUR ESA development
    contract (ESA BSGN page, 2026; Opened [L13]). The systems could work autonomously or by remote
    control; no allocation method is reported.
  - CoRob-X (EU Horizon 2020, led by DFKI), Lanzarote, 21 January to 11 February 2023: three rovers (SherpaTT,
    over 200 kg; Coyote; LUVMI) mapped the ground around a lava tube and merged the maps, one placed a sensor
    cube that also gave radio coverage inside, and SherpaTT's arm lowered Coyote into the tube (GMV,
    28 Feb 2023; Opened [L12]). Heterogeneous robots of three makers, one project, one plan.
  - DLR ARCHES, Mount Etna, demonstration week ending 1 July 2022: rovers LRU1 ("scientist") and LRU2
    ("assistant", about 30 kg, also the Wi-Fi provider for LRU1), the drone ARDEA ("scout"), a lander mock-up,
    and in a second scenario ESA's Interact rover driven by an astronaut from 23 km away with a Scout rover
    as Wi-Fi repeater. In the first scenario the robots "completed their tasks independently"; wind kept the
    drone and the LIBS instrument out of some runs (DLR, 1 July 2022; Opened [L11]).
  - NASA LuSTR projects (Colorado School of Mines with Lunar Outpost, Michigan Tech and Bechtel on autonomous
    landing-site preparation; a University of Pennsylvania multi-robot mobility project): UNVERIFIED, search
    snippets only; no page opened, and no result on allocation was seen.
  - JAXA with Kajima, autonomous construction machines (two backhoes and a crawler dump, 2023): UNVERIFIED,
    search snippets only.
  - An IAC 2024 improved CBAA for lunar robots and a 2024 ISRU auction hierarchy are in [MOA] section 5 (Repo).

**What is still missing.** (a) No published comparison of auction against leader on lunar terrain with real
Earth windows other than ours. (b) The CBBA bound with a binding bundle limit (E.1). (c) Time-extended
guarantees: every bound above is for one allocation round, and the time-extended problem is NP-hard [MOA]. (d)
Any flight result at all.

### B.2 Centralised control from the base, or decentralised?

**What the project has shown.**
- Deciding on Earth is the expensive choice. A pooled dispatcher on Earth that stops when Earth sets kept
  urgent cargo waiting 89.9 h longer than a full-information marketplace (95 % CI 81.8 to 98.7 h; 7.0 times);
  planning ahead before each blackout left 7.3 h; a relay that is up 80 % of the time left 2.6 h and still
  missed its 10 % margin ([P1] H2).
- On the Moon, a leader and an auction are close. At loss 0.10 the leader (the marketplace run on the base
  computer, losing messages on the way) was 0.26 h from the marketplace and the auction 0.84 h below it; neither
  differs from zero. With no loss: leader 14.6 h, auction 14.3 h, marketplace 14.9 h. At loss 0.40 the leader
  gained 1.0 h (not distinguishable from zero) and the auction 3.9 h ([P1] 5.4, 5.5).
- Radio range mattered less than loss (2, 5, 10 km and unlimited range gave differences within noise), but the
  lost-link rule mattered enormously: with it off the wait rose by 3,267.5 h and the share of robot-time out of
  reach of every mast went from 5.1 % to 83.1 % ([P1] E41).
- Roads (E43): one shared reservation table added 0.1 % to delay per delivery at today's fleet, 3.7 % at twice,
  7.9 % at four times and 41.7 % at eight times the fleet. Each owner keeping its own table and referring
  cross-owner conflicts to Earth multiplied delay by 5.1 (2028 windows) and 6.3 (2038), and by 20.2 at eight
  times the fleet ([P2] 5.2 to 5.4).

**Outside evidence.**
- CADRE chose "centralized-planning, distributed-execution" with a leader election that "ensures robustness to
  failures of individual agents". Every agent carries an inactive copy of the planner; the leader is the agent
  farthest from its thermal and power limits; an appointer is chosen "every ten seconds" by a distributed
  minimum-spanning-tree algorithm (GHS) and "loss of the leader results in at most ten seconds of idle time
  before planning recommences on a new leader"; a "designated survivor" keeps a copy of the leader's data
  (Opened [C1]). The design assumes "a low-bandwidth, potentially high-latency, bidirectional communication
  channel is continuously available between agents and the elected leader"; without that, the authors note, no
  coordination is possible in general (the coordinated-attack problem).
- The leader-election paper adds the assumptions: ordered, eventually delivered messages (TCP underneath), and
  re-election on a timer as the time-out for lost messages (Albee et al. 2024; Opened [C4], read in part).
- DARPA SubT: the winning team flew single-robot autonomy only, with time budgets out of contact (Repo [MOA]).
- Multi-operator practice on Earth (UTM, Open-RMF): federated services, filed intents, no single controller;
  measured USS-to-USS exchange 189 ms mean (Repo [TS], [MOA]).

**Reading.** A leader is simpler, uses fewer messages and is what flight engineers trust; an auction survives a
partition. "Leader with fallback" is therefore the design, and the fallback rule has to be written so that two
leaders can never both grant the same road segment (E.2, assumption c).

**Missing.** Our mesh did not partition for long in E40 to E42 (5.1 % of robot-time out of reach of every mast),
so H3's clause "the leader matches the auction unless the mesh partitions" has been tested only on the mild
side. A run that forces partitions of hours is needed.

### B.3 How do rovers avoid collisions and share narrow passages?

**What the project has shown** ([P2]). Rules R1 to R10 of [TS], enforced by a safety program on each vehicle:
- 274,580 driven encounters of 12 types; no hard violation in 11 types (264,580 encounters). Type 9, the
  non-conforming vehicle, had 58 violating encounters in 10,000 (7 contacts), all where a fault stops the leader
  instantly. Deadlocks: 386 of 10,000 in the ring of one-lane segments with finite bays (3.9 %), 4 of 10,000 at
  the landing closure. Near misses in 44 % of driven encounters; smallest clearance without a violation 1.1 m.
- Exhaustive search of the discrete model: 47,085 reachable states, 272,899 transitions, no unsafe or stuck
  state; each of three removed rules (R3 exit slot, R5 entry check, R7 hold) produced its counterexample.
- Cost: see B.2 (0.1 % at today's fleet).

**Outside methods and what each guarantees.**

| Method | Guarantee | Needs | Fails when | Source |
|---|---|---|---|---|
| ORCA (optimal reciprocal collision avoidance) | Robots that all run it are "guaranteed to be collision-free for at least tau time"; each solves a small linear program, no communication | All robots run the same rule; holonomic motion ("we assume that the robot is holonomic"); each observes the others' position, velocity and radius exactly | Dense cases: "the linear program may be infeasible ... choosing a collision-free velocity cannot be guaranteed"; "may also lead to a global deadlock" | van den Berg et al., ISRR 2009 / 2011; Opened [L4] |
| Control barrier function filter | The safe set stays invariant while the quadratic program is feasible; smallest change to the planner's command | Accurate motion model, known braking authority, pairwise state | Model error, actuator limits, the "frozen robot" in crowds | Repo [TS] section 3 |
| Responsibility-sensitive safety distance | Closed-form gap such that the follower can always stop if the leader brakes at up to b_max | Bound on leader's braking; reaction time rho | Leader stops faster than b_max (our type-9 exception) | Repo [TS] section 3 |
| Priority and right-of-way rules (COLREGs style) | No guarantee by themselves; they make the outcome of a conflict predictable | Everyone knows and obeys the ladder | Cyclic waits | Repo [TS] section 5 |
| Space-time reservation of segments (cooperative A*, intersection manager) | No two vehicles in one segment at one time; a lost message can only add delay | A unique authority per segment; a vehicle never assumes an unconfirmed reservation; bounded position error | Vehicle cannot leave on time and the window is not extended; split authority | Dresner and Stone 2008 (Repo [TS], High); proof in E.2 |
| Execution precedence graph (ADG) | Plan order is kept under arbitrary delays; cycles are detected before execution | Completion reports | Report lost: delay only | Hoenig et al. 2019 (Repo [TS], High) |
| UTM / U-space | Filed 4D intents "free of intersection in space and time"; conformance monitoring | Network to a service supplier | No network | Repo [TS] section 2 |
| Airport surface guidance (A-SMGCS) | Routing, guidance and conflict alerting by a tower | Surveillance, a controller | Not opened this session; named as an analogue only (UNVERIFIED) | none |

CADRE's formation drive is a reservation in miniature: the leader hands each rover a "time-stamped corridor";
"if every rover remains within its own time-stamped corridor" the separation limit holds, and "if a rover is
unable to remain within the allocated corridor, all other rovers must stop" (Opened [C1]).

**Missing.** (a) A rule for the dead-stop case (E.2, rule T3 proposes the brick-wall gap). (b) Deadlock in a
ring with finite bays (3.9 %): needs a resource-ordering rule or a bay-count condition. (c) Vehicles that do
not run our rules at all (another bloc's rover): only sensing and R2 protect against them.

### B.4 What if a rover breaks down: who takes over its task?

**What the project has shown.**
- Team lifts under loss: with a commit step and a 1 h time-out, failed meetings were 4.0 a year at loss 0.10,
  12.1 at 0.25 and 25.2 at 0.40; without the commit step 15.2 and 35.4 at the two higher losses. The step cost
  1.8 h of urgent wait at loss 0.25 ([P1] H6). A time-out plus an explicit commit is therefore worth having,
  and it is not free.
- The lost-link ("rally") rule is the single most valuable recovery rule we measured (B.2).
- Road rule R7 (a silent vehicle keeps the reservations it holds, others treat its last reserved volume as
  occupied until it reappears or a time-out extends the hold) could not be removed without the checker finding
  198 unsafe states ([P2] 5.7).
- Not yet simulated: a rover that dies with cargo on board, towing, and re-auction of its job. Section E.5
  gives the expected delay to put into the engine.

**Outside evidence.**
- CADRE. Information needed for planning is kept on two agents (leader and designated survivor) and synchronised
  every 10 s; "information is only lost if both the leader and the designated survivor fail before a new leader
  and survivor can be elected (which happens within 10s)". On a leader change every agent drops tasks not yet
  commanded, issues clean-up commands, waits for running tasks to end and only then acknowledges the new
  leader, which replans from fresh state: "the new leader does not rely on information shared from the previous
  one". Ground operators can mark an agent as not participating; for the formation task there is one task
  hierarchy per subset of the three rovers, larger subsets tried first, so the team carries on with two rovers
  when one is excluded. A task that fails on one rover aborts the coupled tasks of the others through an
  "abort task" message that carries only a task ID, to raise its chance of delivery. The stated limit: if abort
  messages are delayed, "agents may act in an uncoordinated manner for some time" (all Opened [C1]). The
  leader-election paper shows agents dropped one by one with re-election after each (Opened [C4]).
- CBBA family. A new or orphaned task can be absorbed by partial replanning without a full reset [L1]. CBBA is
  described by its authors as robust to changing network topology and inconsistent situational awareness (MIT
  DSpace abstract page, Opened [L3]); measured degradation under loss is in [MOA].
- Auctions under loss. Single-round auctions are the fragile ones, because a robot that misses the only round
  sits idle; re-sending winners in later rounds helps (Otte et al. 2020; Repo [MOA], High).
- Towing and recovery. No published lunar towing demonstration was found. The nearest hardware results are two
  rovers carrying one cargo with a coupling that tolerates about 15 cm misalignment (Krawciw et al. 2026; Repo
  [MOA], High) and CoRob-X's rover lowering another by tether [L12].

**Missing.** Failure rates for lunar rovers (no fleet statistics exist); a towing model; the false-alarm side of
heartbeat detection under bursty loss (E.5 uses independent loss, which is optimistic).

### B.5 How much autonomy is needed, given the latency to Earth?

**The delay.**

| Quantity | Value | Source |
|---|---|---|
| Light time, round trip, at 356,500 / 384,400 / 406,700 km | 2.38 / 2.56 / 2.71 s | Computed (distance / c) |
| Round trip assumed in our papers, with ground processing | 2.6 s + 2.4 s = 5.0 s | [P3] (light time Measured, processing Assumed) |
| Round-trip latency NASA plans for VIPER operations | "Med latency (6-10 s round trip)" | NASA Ames, VIPER slides, 29 Apr 2026; Opened [M26] |
| Delays tested by NASA for LTV teleoperation | 0, 4, 6, 8 s | NASA/TM-20240001217; Opened [L5] |
| Earth in view of our base antenna | 59 % of the time; windows about 16 days, gaps about 11 days; oxygen plant never | [P1] introduction (from R-1) |
| Direct-to-Earth coverage at candidate south-pole sites; with one relay | 17 to 43 %; 80 to 86 % | Repo [MOA] section 5 (LCRNS source) |

**Driving experience.**

| Vehicle | Mode | Speed and distance | Source |
|---|---|---|---|
| Lunokhod 1 (1970 to 1971) | Remote driving from Earth by TV | 10.54 km in 321 Earth days (11 lunar days): 33 m per Earth day on average (Computed) | Wikipedia, Lunokhod 1; Opened [M25]. Crew of five and about 1 km/h: UNVERIFIED (search snippet) |
| Yutu-2 (2019 onward) | Ground-commanded via relay | 1.613 km as of 19 Sep 2024 since 3 Jan 2019; 120 m in its first lunar day | Wikipedia, Yutu-2; Opened [M24] |
| Pragyan (2023) | Ground-commanded via lander | 101.4 m in 12 days; data only through the lander | Wikipedia, Chandrayaan-3; Opened [M14] |
| VIPER (planned) | Near-real-time waypoint driving from NASA Ames | 20 cm/s maximum; 10 cm/s while prospecting; 0.8 cm/s "speed made good"; 20 km design traverse; drive team of driver, co-driver, navigator and real-time science; "1 operator is responsible for 21 HW components + 4 SW modules" | NASA Ames slides, 29 Apr 2026; Opened [M26]. Waypoints of about 4.5 m: UNVERIFIED (snippet of a NASA page) |
| LTV, driven from Earth (simulator) | Direct teleoperation, one mast camera | Mean speed 3.24 km/h at 0 s, 2.56 at 4 s, 2.03 at 6 s, 1.76 at 8 s delay; 6 km takes 1:51, 2:21, 2:57, 3:25 h | NASA/TM-20240001217 (Litaker, Li, Beaton, Lewis, 2024); Opened [L5] |
| LTV requirement | Remote operation | LTV-SYS-071: 6 km (threshold), 8 km (goal) in 24 h when operated remotely; LTV-SYS-029: at least 20 km without recharge | same; Opened [L5] |
| LTV as ordered | Crewed or uncrewed | CLV-1: about 2,000 lb, over 6 mph on level ground; Pegasus: over 9 mph, up to a year of operation | NASA release 26-046, 26 May 2026; Opened [M1]. "Up to 10 km/h, slopes to 20 degrees, range 200 km": SpacePolicyOnline, 26 May 2026; Opened [M2] |
| CADRE (planned) | High-level goals only | Regions of 6 x 6 m to 22 x 13 m and goals 6 to 20 m away in Earth tests; about 400 m2 planned on the Moon | [C1]; NASA/JPL 2023 [C7]; Opened |

The NASA study adds the human side: with delay, workload rose significantly (mental demand, frustration),
operators braked more, and the test operators judged that 20 to 100 hours of training give about 60 %
proficiency and a year gives full proficiency [L5]. Its first sentence is the reason for an on-board safety
layer: teleoperation under a multi-second delay "could result in a dangerous state where the roving vehicle is
either damaged or lost".

**Which decisions must be made on the Moon.** Three tests, each with numbers.

1. *Reaction time.* During the loop delay the vehicle is blind to commands. At 10 km/h (2.78 m/s) it covers
   7.2 m in 2.6 s, 16.7 m in 6 s and 27.8 m in 10 s (Computed), which is more than the 5.3 m it needs to brake
   at a friction coefficient of 0.45 ([TS] table). Section E.3 turns this into a speed cap: with 20 m of
   usable sight and friction 0.45, 16.0 km/h with a 1 s on-board reaction against 8.5 km/h at 6 s and 5.8 km/h
   at 10 s. Stopping, following distance and giving way at a junction are therefore on-board decisions.
2. *Blackouts.* Any decision that cannot wait for the next Earth window has to be on the Moon. With gaps of
   about 11 days in every 27, a decision needed at a random moment waits 54 h on average if only Earth may take
   it (E.5, Computed). Measured in our simulator: 89.9 h more urgent wait for dispatch [P1], 5.1 times the
   delay for road conflicts [P2].
3. *Operator workload.* VIPER needs about four people on console for one rover [M26]. A base with 8 to 20
   vehicles of several owners cannot be driven that way around the clock. Published ratios:

| Setting | Ratio | Source |
|---|---|---|
| Fan-out model: robots per operator = activity time / interaction time (FO = AT / IT) | by definition | Olsen and Wood, CHI 2004; Opened [L6] |
| Remote monitoring of self-driving vehicles, simulator study | best at about 5; steady from 5 to 7; clear drop at 9; mean response 13 s | Coventry University study as reported by IoT M2M Council, 2 Sep 2025; Opened [L7] (secondary; journal article not opened) |
| Robotaxi remote assistance, Waymo | about 70 agents on duty for about 3,000 vehicles (about 1 to 43), as of 17 Feb 2026 | HumanProgress quoting a newsletter, 3 Mar 2026; Opened [L8] (secondary; primary letter not opened) |
| Robotaxi remote assistance, other firms | 1 to 20 (Pony.ai), 1 to 3 (earlier Chinese rule) | UNVERIFIED (search snippets) |
| VIPER | about 4 people per rover per shift | [M26] |
| CADRE | three rovers under one high-level command; staffing not published | [C1] |

So the decision table is:

| Decision | Needed within | Where | Why |
|---|---|---|---|
| Emergency stop, obstacle and vehicle avoidance | 0.1 to 1 s | On each vehicle | Reaction test |
| Following gap, speed on slopes, crew keep-clear | 1 s | On each vehicle | Reaction test; [P2] |
| Right of way, segment reservation, bay use | 1 to 60 s | Vehicles and base computer on the Moon | Reaction and blackout tests; [P2] 5.1 times |
| Re-auction of a failed rover's job | 1 to 10 min | Vehicles and base computer on the Moon | Blackout test; E.5 |
| Job allocation, team-lift meetings, charger slots | minutes to an hour | On the Moon; Earth may upload plans ahead | [P1] 89.9 h against 7.3 h |
| Recovery of a broken vehicle, towing, unusual hazards | hours | People on Earth when in view; hold safely otherwise | Rare, high judgment |
| Prices, rules, audits, settlement | days | Earth | [P3] |

**Missing.** A measured intervention rate (requests for help per vehicle-hour) for any lunar rover; without it
the workload model of E.4 is a formula with assumed inputs.

### B.6 Who is already doing this? (status as of 11 November 2026)

The short answer: several organisations have flown or will fly more than one mobile robot on one mission, all
under one mission plan. None has shown robots of different owners negotiating jobs or right of way.

**NASA CADRE** (Cooperative Autonomous Distributed Robotic Exploration). Section D gives the design.
- Hardware finished February 2024; three rovers and the base station arrived at Intuitive Machines in Houston
  on 9 February 2025 (JPL, 11 Feb 2025; Opened [C8]).
- Flight: payload of IM-3 (lander Nova-C "Trinity", Reiner Gamma), which NASA now also calls "Moon Base III"
  (NASA release 26-046, 26 May 2026; Opened [M1]). The launch slipped to "the first quarter of 2027" according
  to Intuitive Machines' chief executive on the August 2026 earnings call, reported by Aerospace America on
  15 September 2026, which also quotes NASA's Moon Base manager that the lander is "basically in final assembly"
  (Opened [M3]). NASA's and JPL's CADRE pages still say "in 2026" (Opened [C9], [C10], the latter last updated
  9 July 2025). **CADRE has not flown.**
- Earlier targets, for the record: 2024 [C7], 2025/2026 [C1], "early 2026" [C8], second half of 2026
  (Wikipedia IM-3, citing January 2026 reporting; Opened [M6]).

**Astrobotic** (being bought by Voyager Technologies; agreement announced 2 June 2026, close expected "by early
July 2026"; Opened [M21]. NASA's 7 November 2026 release lists Voyager Technologies, not Astrobotic, among CLPS 2
awardees; Opened [M4]).
- Peregrine Mission One (January 2024) did not reach the Moon (not re-checked this session).
- Griffin Mission One ("Moon Base II"): not launched. "No earlier than January 2027" (Wikipedia, citing Next
  Spaceflight, retrieved 5 Nov 2026, and a NASA statement of 20 Oct 2026 giving "before the end of 2026" or
  "in January 2027"; page last edited 9 Nov 2026; Opened [M7]). In September NASA's manager still said
  "no earlier than November" [M3]. Environmental tests ended at JPL on 13 October 2026 [M7].
- Cargo: Astrolab's FLIP rover (about 500 kg), an Astrobotic CubeRover, ESA's LandCam-X; site near Nobile
  crater and Mons Mouton [M7]. Two rovers of two companies on one lander, with no stated cooperation.
- LunaGrid-Lite (a CubeRover unreeling 1 km of power cable) and the VSAT solar tower: UNVERIFIED (search
  snippets and a product mention in [M21]); no flight date found.

**Intuitive Machines.**
- IM-1 (2024) and IM-2 (6 March 2025) both landed and tipped over [M2]. IM-2 "Athena" came down about
  250 m from its target in a crater on Mons Mouton, on its side; the mission ended the next day. The drill could
  not reach the surface; Lunar Outpost's MAPP rover could not deploy (Spaceflight Now, 7 Mar 2025; Opened
  [M19]). Nokia's 4G unit ran about 25 minutes without a call (Repo [TS]).
- Near Space Network contract, 17 September 2024: firm-fixed-price IDIQ, maximum 4.82 billion USD, five-year
  base (1 Oct 2024 to 30 Sep 2029) plus a five-year option, for lunar relay and navigation services (SatNews,
  17 Sep 2024; Opened [M22]). The first relay satellite, Altus-1, first of five in the company's Lunar Data
  Network, is to ride with IM-3 (Wikipedia IM-3; Opened [M6]). Not yet in orbit.
- LTV: not selected for the May 2026 Phase 1 task orders [M1], [M2]. Selected for CLPS 2 on 7 Nov 2026 [M4].

**ispace.**
- HAKUTO-R Mission 1: launched December 2022, hard landing 2023. Mission 2 "Resilience": hard landing on
  6 June 2025 (JST) after the laser rangefinder was late in giving valid ranges; the Tenacious micro rover of
  ispace-Europe was lost with it (Spaceflight Now, 6 Jun 2025; Opened [M18]).
- 27 March 2026: the Series 3 and APEX 1.0 landers were merged into one design, ULTRA, with a new engine;
  "ispace's next lunar landing mission is planned to launch in 2028"; the first ispace-U.S. mission (CLPS task
  order CP-12 with Draper) is "now expected in 2030", pending NASA's approval (ispace press release; Opened
  [M17]). ispace-U.S. is a CLPS 2 awardee [M4]. No rover of ispace has operated on the Moon.

**Lunar Outpost.** MAPP reached the Moon inside IM-2 and stayed inside; the company said its data show the rover
survived the landing [M19]. LTV Phase 1 task order of 220 million USD for Pegasus (team: General Motors,
Goodyear, Leidos) [M1], [M2]. No multi-robot or cross-maker capability shown.

**Venturi Astrolab.** FLIP is built and waits on Griffin-1 [M7]. LTV Phase 1 task order of 219 million USD for
CLV-1, adapted from FLEX (team: Axiom Space, Interlune, Odyssey Space Research) [M1], [M2]. Nothing flown.

**LTV Services: the down-select.** The 2024 contract named three teams (maximum value 4.6 billion USD:
UNVERIFIED, search snippet). On 26 May 2026 NASA issued "Phase 1 High Achievability Mission" task orders to
two of them, Astrolab (219 million USD) and Lunar Outpost (220 million USD); the vehicles are to be on the Moon
by 2028, delivered through CLPS; over the following 18 months the providers finish designs, run crewed
evaluations and qualify flight units; NASA will hold on-ramp competitions to add LTV vendors. Blue Origin
received 188 million USD, with an option worth 280.4 million USD, to deliver both rovers on Blue Moon Mark 1
landers (NASA release 26-046; Opened [M1]). So the outcome is two makers, not one, which is exactly the
mixed-fleet case; Intuitive Machines is out for now.

**VIPER.** Cancelled in July 2024, then revived: NASA now expects VIPER to fly on Blue Origin's second Mark 1
mission in 2027 (SpacePolicyOnline, 26 May 2026; Opened [M2]). The first Mark 1, "Endurance" ("Moon
Base I"), was due in 2026 and is now "the first part of 2027" after a New Glenn rocket exploded on its pad on
28 May 2026 ([M3]; date of the explosion from SpacePolicyOnline, 9 Jun 2026; Opened [M8]). A 2027 VIPER landing
therefore depends on a lander that has not flown and a pad being rebuilt; no newer official date was found.
NASA's April 2026 slides still plan four or more lunar days near Nobile crater [M26].

**Other NASA south-pole robots announced in 2026.** MoonFall: four hopping drones, designed by JPL, carried
by a Firefly spacecraft, launch target 2028 [M1]; the count is "not yet decided" according to the programme
manager [M2]. PROMISE: a six-wheeled, nuclear-powered rover built at JPL largely from spare Curiosity and
Perseverance hardware, launch target late 2028, 18-month mission, delivered by Blue Origin (94 million USD plus
a 140 million USD option) (NASA release 26-095, 7 Nov 2026; Opened [M4]).

**Firefly Blue Ghost Mission 1.** Landed 2 March 2025 in Mare Crisium, worked 346 hours over the lunar day
with ten NASA payloads, ended 16 March 2025; the longest commercial surface operation so far (Spaceflight
Now, 18 Mar 2025; Opened [M20]). No rover. Mission 2 is "scheduled to launch later in 2027" [M3]; Mission
Control of Canada says it will provide the surface link between the UAE's Rashid Rover 2 and Firefly's lander
(company site, 2026; Opened [M23]), a rover of one organisation talking through a lander of another.

**China.**
- Chang'e 6: launched 3 May 2024, landed 1 June 2024 in the Apollo basin on the far side, returned 1,935.3 g
  on 25 June 2024, relayed by Queqiao-2. A mini rover of about 5 kg, Jinchan, detached on its own and
  photographed the lander (Wikipedia, Chang'e 6; Opened [M12]).
- Chang'e 7 (orbiter, lander, rover, six-legged hopper for shadowed craters; target Shackleton rim): the launch
  window opened on 24 August 2026 and was not used; a statement posted 23 August moved the launch to 2027
  (Scientific American, 20 Aug 2026, updated 24 Aug; Opened [M10]). A new date was not found.
- Chang'e 8: planned 2028 to 2029, site Leibnitz Beta (Mons Mouton). Besides the lander and rover it is to
  carry a multi-functional operation robot of about 100 kg with a mobile charging station (Hong Kong
  University of Science and Technology with partners), a Pakistani rover of about 35 kg, and two 5 kg
  micro-robots (Middle East Technical University, Zhejiang University, STAR.VISION) (Wikipedia, Chang'e 8,
  citing SpaceNews of 27 Jan and 25 Apr 2025; Opened [M11]). This is the first planned mission on which robots
  of several makers and countries share a site. No coordination method is published.
- ILRS: 13 member countries listed; construction missions ILRS-1 to ILRS-5 planned 2031 to 2035; ILRS-1 covers
  "basic energy, and telecommunication facilities" (Wikipedia, ILRS; Opened [M13]). Its communication-network
  element is not described in the source read (UNVERIFIED beyond that).
- Yutu-2: still the longest-lived rover; 1.613 km as of 19 September 2024 [M24].

**India.** Chandrayaan-3 landed on 23 August 2023 at 69 degrees south; the 26 kg Pragyan rover drove 101.4 m and
spoke only through the lander; both failed to wake after the first night [M14]. Chandrayaan-5 / LUPEX with
JAXA: approved by India's cabinet on 14 March 2025; planned 2028 to 2029 on an H3-24L; ISRO lander, JAXA rover
of 350 kg built by Mitsubishi Heavy Industries; over 100 days of operation (Wikipedia, LUPEX; Opened [M15]).
Chandrayaan-4 (sample return): 2027 or 2028 depending on the source, UNVERIFIED (search snippets).

**ESA.** Argonaut: Thales Alenia Space Italy leads the descent element, due in 2030; first mission "ArgoNET"
expected in 2031 (ESA, 30 Jan 2025; Opened [M16]); an October 2026 article gives the end of 2030 (UNVERIFIED,
snippet). ESA's robotics work on the ground is in B.1 and B.8.

**South Korea.** A lander is planned for 2032 and the KPLO orbiter's mission was extended (UNVERIFIED, search
snippets). A Korean instrument, LUSEM, flies on IM-3 [M1], [M6].

**Software players.** Mission Control (Canada): Spacefarer operations software and the rover-to-lander link
above [M23]. Open-RMF: multi-vendor robot traffic on Earth, the closest working analogue (Repo [MOA]). Space
ROS: an open framework "for developing flight-quality robotic and autonomous space systems", with demos for
Canadarm2, the Curiosity rover and navigation, Apache-2.0 (site and demos repository; Opened [L18]). DARPA's
LOGIC consortium at APL writes interface guidelines for power, communications, navigation and "cislunar space
traffic control" (APL, 11 Oct 2023; Opened [L17]). A search for a company selling a coordination layer for
lunar vehicles of different makers found none (11 Nov 2026); that is an absence of evidence, not proof.

### B.7 Who would the customers be?

**Who buys today.** Almost only NASA, through three vehicles of procurement.

| Contract | What it is | Money | Date and source |
|---|---|---|---|
| CLPS 1.0 | Task orders for delivery of payloads; NASA buys a service, the company owns the lander | Ceiling raised from 2.6 to 4.2 billion USD; orders through November 2028, deliveries to November 2033 | NASA release 26-095, 7 Nov 2026; Opened [M4] |
| CLPS 2 | Ten-year multiple-award IDIQ; eight companies may bid for task orders: Blue Origin, Firefly, Intuitive Machines, ispace-U.S., Lockheed Martin, Northrop Grumman, SpaceX, Voyager Technologies | Combined maximum 10 billion USD (a ceiling, not an award) | same [M4]; list also in NewSpaceEconomy, 9 Nov 2026; Opened [M5] |
| LTV Services, Phase 1 | Two task orders for crew rovers as a service | 219 and 220 million USD; delivery 188 million USD plus 280.4 million USD option | NASA release 26-046, 26 May 2026; Opened [M1] |
| Launch and transport (VADR) | Six task orders to Arrow, Blue Origin, Impulse | about 1.3 billion USD together | [M4] |
| Near Space Network, lunar relay | Relay and navigation services | maximum 4.82 billion USD over up to ten years | [M22] |
| PROMISE rover delivery | Blue Origin Mark 1 | 94 million USD plus 140 million USD option | [M4] |

NASA's stated tempo: more than a dozen Moon Base missions to be announced in 2026 [M1]; the administrator
wants 10 CLPS missions a year for three years from 2027 [M2]; Phase One of Moon Base
runs through 2029 [M3]. Against that, the record of 2026 so far is no launch of a US commercial lunar lander: NASA
"expects one lunar launch this year" (September) [M3], and that one has since moved to January 2027 [M7].

**The Artemis schedule as it stands.** Artemis II flew around the Moon in April 2026 (launch 1 April, splashdown
10 April: search snippets and a headline only, UNVERIFIED in detail; the project holds the mission's PDS archive
guide of 7 Oct 2026). Artemis III is no longer a landing: on 27 February 2026 NASA made it a low-Earth-orbit
test of docking with the two landers in 2027 (Spectrum News 13; Opened [M9]); the crew was named on 9 June 2026
and "no launch date was set", readiness "no earlier than this time next year" (SpacePolicyOnline; Opened [M8]).
Artemis IV is the first landing: "NASA is striving to do that by 2028" [M8]; NASA's May release speaks of
"future crewed Artemis landing missions in 2028" [M1]. Dependencies named in [M8]: Starship has not reached
orbit, propellant transfer has slipped repeatedly, New Glenn's pad is being rebuilt.

**Market size: three independent estimates and how far apart they are.**

| Estimate | Number | Horizon and kind | Assumptions stated | Source |
|---|---|---|---|---|
| PwC, "Lunar market assessment", Sept 2021 | over 142 billion EUR (footnoted as 170 billion USD) | to 2040; transport, lunar data, resource use | public and private cooperation "the key variable" | ESA Space Economy page, Nov 2021; Opened [K2] (PwC PDF not opened) |
| PwC, "Building the Lunar Economy", Jan 2026 | revenue 93.9 to 127.3 billion USD; infrastructure investment 72.7 to 88.5 billion USD | cumulative 2026 to 2050; mobility, communication, habitation, energy, water | scenario-based; transport is 70 to 80 % of infrastructure cost to 2035 | SpaceQ, 15 May 2026; Opened [K1] (report not opened) |
| Deloitte, "Building the Lunar Economy", Aug 2026 | 343 to 566 billion USD; a further 541 billion USD of "spillover" left out | "through 2050" (cumulative by wording); core 282 billion USD of which transport 206 and power 44; the rest covers communications, surface mobility, construction, life support | high case needs lunar propellant, helium-3, orbital data centres; over 400 model inputs | Fortune, 26 Aug 2026; Opened [K3] (report not opened; Fortune notes Deloitte has a space investment) |
| IDA Science and Technology Policy Institute, for NASA, April 2020 | about 63 billion USD of government money for human lunar missions | 2024 to 2040; demand side | most firms' business cases "tied to space-oriented agencies, especially NASA"; of a dozen household markets examined only a few looked viable | IDA Document D-13219; Opened [K4] (executive summary read) |

How uncertain: the same firm's two reports give 170 billion USD by 2040 and at most 127 billion USD by 2050;
the two 2026 reports differ by a factor of 3.7 to 6 over the same horizon (94 against 343, 127 against 566);
the only demand-side study says the money is government money. All are forecasts of activity that has not
started; none has been tested against a single year of revenue. None sizes surface mobility alone: in
Deloitte's breakdown everything except transport and power is 32 billion USD over 25 years for four categories
(Computed: 282 - 206 - 44), so mobility is of the order of ten billion USD at the high end, and a coordination
layer is a small part of that. **We should not quote a market size for the protocol.** What can be said is the
number of vehicles and owners (next paragraph).

**Who has an actual need for a mixed-fleet layer, and when.**

| When (planned) | Vehicles at or near the south pole | Owners or makers | Need |
|---|---|---|---|
| 2027 | FLIP and a CubeRover from Griffin-1 (Nobile / Mons Mouton); Chang'e 7 rover and hopper (Shackleton rim); possibly VIPER | Astrolab, Voyager / Astrobotic, CNSA, NASA | Low: sites are apart; deconfliction is by notification under the Artemis Accords [TS] |
| 2028 to 2029 | Two LTVs (CLV-1, Pegasus), PROMISE, MoonFall drones, VIPER if it flies, CLPS 2 payload rovers; Chang'e 8 with four or more robots at Mons Mouton | Astrolab, Lunar Outpost, JPL, NASA Ames, Firefly; CNSA, HKUST, SUPARCO, METU and partners | First real case: three or more owners near one site, crew arriving with Artemis IV. NASA's own policy study expected central coordination to "become necessary" at three or more actors [TS] |
| 2030 on | ISRU plants, power and communication towers (miniCAST [M4]), Argonaut and LUPEX payloads | plus ESA, JAXA, ISRO | Routine shared roads, chargers and pads: the case our papers simulate |

Likely first buyers, in order: NASA's Moon Base programme office (it holds the LTV and CLPS task orders and can
write an interface into them); the two LTV makers (each must already let NASA and commercial users command its
rover between crews); CLPS 2 lander companies that will carry third-party rovers; relay operators (Intuitive
Machines' network, later ESA Moonlight) that want traffic on their links. Agencies of the ILRS group are a
separate bloc with its own standards.

**Missing.** Any statement from NASA that mixed-fleet coordination will be required in an LTV or CLPS 2 task
order; none was found in the two releases read.

### B.8 Can the protocol be tested on Earth?

Yes, and the published record shows how. The inventory, with what each item can and cannot show:

**Simulators.**

| Tool | What it gives | Limits | Source |
|---|---|---|---|
| Our engine (`lunarsim`) | Logistics, mesh on 5 m terrain, Earth windows, auction, rules of the road; 5,480 simulated years [P1], 650 runs [P2] and 1,080 simulated years [P3] already run | No wheel-soil physics, no perception | [P1], [P2], [P3] |
| OmniLRS (University of Luxembourg, Tohoku University) | Photorealistic lunar scenes on NVIDIA Isaac Sim, "multi-robot capabilities", ROS 1 and ROS 2 bindings, procedural terrain; sim-to-real rock segmentation within 5 % of a model trained on real data | Perception-centred; terramechanics simplified | Richard et al., arXiv 2309.08997; Opened [L9] |
| NASA Lunar Autonomy Challenge (2024 to 2025) | CARLA with a digital twin of NASA's IPEx excavator; agents had to map the surface, find obstacles and manage power; 31 US university teams; winners Stanford, MIT, Carnegie Mellon; run for NASA by Johns Hopkins APL with Caterpillar and Embodied AI | Single agent; no multi-robot or radio element | NASA, 15 May 2025; Opened [L10] |
| Space ROS demos | Flight-style ROS 2 stack; Curiosity and Canadarm2 demos, a navigation demo | No lunar multi-rover demo yet | [L18] |
| VIPER's simulator (RSIM) | Lighting, camera and slip models tuned against the Ames Lunar Lab and Glenn SLOPE tests; 1 m and 4 cm terrain | NASA-internal | [M26] |
| DUST (Digital Lunar Exploration Sites Unreal Simulation Tool, NASA JSC) | South-pole terrain visualisation in Unreal Engine 5; in NASA's software catalogue as MSC-27522-1 | Release conditions not read: UNVERIFIED beyond the catalogue entry existing | catalogue URL checked reachable, content from snippet |

**Hardware-in-the-loop radio.** NASA Glenn's Lunar LTE Studies project (LunarLiTES) combined two weeks of 4G
field measurements at Black Point Lava Flow, Arizona, in 2022 with an emulated radio environment at Glenn;
"the data collected during field testing will be used to improve future emulation models" (NASA Glenn,
8 Dec 2022; Opened [L16]). The emulation bench (MATRICS) is known only from a search snippet (UNVERIFIED). The
method carries over: real radios, cabled through a channel emulator that plays path loss and blockage computed
from our terrain mesh model. CADRE's own lesson is that motor noise matters: electromagnetic interference from
the motors causes "degraded signal quality and packet loss ... especially during rover movement" [C5].

**Facilities and analogue sites.**

| Place | What is there | Access | Source |
|---|---|---|---|
| LUNA, Cologne (ESA and DLR) | Regolith hall for astronauts and robots (700 m2 and 900 t of simulant: UNVERIFIED, snippets; pages returned 403) | "LUNA Utilization Request Form" by e-mail; reviewed by a technical team; decided by a joint ESA/DLR board; "fully booked with activities through June 2027" | LUNA site, read 11 Nov 2026; Opened [L14] |
| NASA Ames Lunar Lab and SSERVI Regolith Testbed | 4 x 4 m bed with about 8 t of JSC-1A; 19 x 4 m bed with over 15 t of LHS-1 highland simulant; a deep bed for drills; sun simulators | "available for use"; contact for "availability and pricing" | SSERVI page; Opened [L15]; also [M26] |
| NASA Glenn SLOPE lab | Slip, slope, crater and entrapment tests of rover mobility (used for VIPER, 30 degree slope tests) | Not read | [M26] (pictures and captions only) |
| NASA KSC Swamp Works | Regolith bin with 120 t of BP-1 simulant | UNVERIFIED (snippet) | none opened |
| NASA JSC Rock Yard; Ames Roverscape | Outdoor rover yards | UNVERIFIED (not found or not opened) | none opened |
| JPL Mars Yard | Where CADRE's development rovers drove outdoors, including at night with spotlights | NASA-internal | [C1], [C6] |
| Mount Etna | ARCHES 2022 (B.1) | Campaign-based | [L11] |
| Lanzarote, La Corona lava tubes | CoRob-X 2023 (B.1) | Campaign-based | [L12] |
| Devon Island, Haughton-Mars Project | Arctic impact-crater base run by the SETI Institute and Mars Institute since the late 1990s; summer field seasons | By arrangement with the project | Wikipedia; Opened [L19] |
| Iceland | Rover field campaigns | UNVERIFIED (nothing opened) | none |
| ESA / ESRIC Space Resources Challenge | Competition with a field test (second edition at LUNA) | Open call per edition; the second closed in February 2025 (snippet) | [L13] |

What the record implies for us: every multi-robot field campaign above was one project with one plan. A test
with two or three "owners" whose robots run independent software and meet only through a protocol would be
new, and it can be small. Section H lays out the stages.

**Missing.** Lunar gravity for braking tests (no facility gives 1.62 m/s2 to a driving vehicle; low-friction
surfaces or scaled speeds are the substitute and must be stated as such); a public multi-rover lunar benchmark.

---

## C. Comparison table

"Cooperating robots" counts mobile robots meant to work on one site in one mission. "Interop" = interoperability
with vehicles of other makers: yes (shown), claimed (announced, not shown), no (not designed or not stated).

| Project or company | Country | What flew, and when | Cooperating robots | Coordination method | Comms between robots | Interop | Source |
|---|---|---|---|---|---|---|---|
| NASA / JPL CADRE | USA | Nothing yet; built Feb 2024, at the lander maker since Feb 2025; IM-3 now Q1 2027 | 3 rovers + base station | Central planner on an elected leader; distributed execution | Microhard mesh radio, at least 1 Mbit/s shared; UWB for ranging | no (one owner, identical rovers) | [C1], [C5], [C6], [M3] |
| Intuitive Machines | USA | IM-1 2024 and IM-2 (6 Mar 2025) landed and tipped; IM-3 Q1 2027 | IM-2 carried a hopper and third-party rovers; none deployed | Each payload on its own | Nokia 4G flown, about 25 min, no call; relay satellite Altus-1 planned with IM-3 | claimed (relay service for others) | [M19], [M6], [M22], [TS] |
| Astrobotic / Voyager | USA | Peregrine 2024 failed in transit (not re-checked); Griffin-1 NET Jan 2027 | FLIP + CubeRover on one lander | None stated | Lander Wi-Fi to payloads [P3] | no | [M7], [M21] |
| Venturi Astrolab | USA | Nothing; FLIP awaiting Griffin-1; CLV-1 ordered May 2026 for 2028 | 1 | Remote and crewed driving | Via lander or relay | no | [M1], [M7] |
| Lunar Outpost | USA | MAPP reached the surface inside IM-2 (Mar 2025), not deployed; Pegasus ordered May 2026 | 1 | Remote driving | Was to use Nokia 4G | no | [M19], [M1] |
| NASA LTV Services | USA | Nothing; two Phase 1 task orders 26 May 2026; on the Moon by 2028 | 2 rovers of 2 makers, one customer | Not published | Not published | not stated | [M1], [M2] |
| NASA VIPER | USA | Nothing; cancelled 2024, revived; second Blue Moon Mark 1, 2027 at the earliest | 1 | Waypoint driving from Earth | Direct to Earth | no | [M2], [M26] |
| NASA MoonFall, PROMISE | USA | Nothing; 2028 targets | about 4 drones; 1 rover | Not published | Not published | not stated | [M1], [M4] |
| Firefly | USA | Blue Ghost M1 landed 2 Mar 2025, 346 h; M2 in 2027 | 0 (M2 to carry Rashid Rover 2) | n/a | Rover-to-lander link by Mission Control (planned) | claimed | [M20], [M3], [M23] |
| ispace | Japan / USA / Europe | M1 (2023) and M2 (6 Jun 2025) hard landings; next 2028; US mission 2030 | 1 micro rover per mission (lost) | Remote driving | Via lander | no | [M17], [M18] |
| CNSA Chang'e 6 | China | Far-side sample return, May to June 2024 | lander + 5 kg mini rover | Rover moved and imaged the lander on its own | Queqiao-2 relay | no | [M12] |
| CNSA Chang'e 7 | China | Nothing; launch moved from Aug 2026 to 2027 | lander, rover, hopper | Not published | Not read | no | [M10] |
| CNSA Chang'e 8 / ILRS | China + partners | Nothing; 2028 to 2029 | lander, rover, a 100 kg robot, a 35 kg Pakistani rover, two 5 kg micro-robots | Not published | Not published | claimed (multi-country robots on one mission) | [M11], [M13] |
| ISRO Chandrayaan-3 | India | Landed 23 Aug 2023; rover 101.4 m | lander + 1 rover | Ground-commanded | Rover only through lander | no | [M14] |
| ISRO / JAXA LUPEX | India / Japan | Nothing; 2028 to 2029 | lander + 350 kg rover | Not published | Not read | two-agency mission | [M15] |
| ESA Argonaut | Europe | Nothing; first mission 2031 | cargo lander | n/a | n/a | n/a | [M16] |
| DLR ARCHES (Earth) | Germany | Mount Etna, June to July 2022 | 2 rovers + drone + lander mock-up; plus ESA rover with relay rover | Automated task planning, shared mapping; teleoperation in one scenario | Wi-Fi, one robot as relay | partly (DLR and ESA / KIT robots) | [L11] |
| CoRob-X (Earth) | EU, led by DFKI | Lanzarote, Jan to Feb 2023 | 3 rovers of 3 makers | One mission plan; map merging; tethered descent | Sensor cube as relay | yes, inside one project | [L12] |
| ESA Space Resources Challenge 2 (Earth) | Europe | LUNA hall, 2025 | per team; winner: rover + fixed sorter | Autonomous or remote | Not read | no | [L13] |
| LunarHaul / Lunar ATC (simulation) | this project | Simulated only | 8 vehicles of 3 owners (up to 8 times that) | Auction among owners' robots, leader as normal mode, rules of the road | Mesh on 5 m terrain, loss 0 to 0.40 | yes, by design | [P1], [P2], [P3] |

---

## D. What CADRE teaches us

CADRE is the only multi-robot autonomy system built and tested for flight on the Moon, and its team publishes
openly (CC-BY). Everything below is from the team's own papers and slides, read this session.

### D.1 Architecture

- **Agents.** Three rovers and a static base station on the lander; the base station is the gateway to Earth
  and does computing for the team [C1], [C2].
- **Four modules** [C1]: leader election; a shared state database; a strategic planner (active on the leader
  only, a dormant copy on every agent); an agent controller on every agent that executes tasks and checks its
  own constraints.
- **Ground input.** A task network and the boundary of a region; then "go explore this region" level commands
  [C1], [C7].
- **Planner.** MEXEC task networks; tasks carry a flight-software command, an expected duration, constraints
  and expected impacts; replanning is evaluated at 1 Hz; tasks are handed to an agent when their start falls
  within 5 s; scheduling is greedy by priority [C1].
- **Safety split.** Each agent checks constraints it can see itself and may refuse or fail a task; constraints
  that need another agent's state are checked on the leader, which sends "abort task". A stale plan cannot make
  an agent break its own limits: "the agent controller will refuse to execute the task based on its local
  information, ensuring safety" [C1]. This is the same split as our "the AI suggests, the safety program
  decides".
- **Database.** SQLite with a custom synchronisation layer; availability is preferred over consistency (agents
  may hold different data); because only the leader plans, "such lack of consistency will not result in
  uncoordinated action", only in plans made on stale data [C1].
- **Software.** Flight software in F Prime; autonomy in C++ on a ModalAI VOXL running non-real-time Linux [C3].

### D.2 Numbers

| Item | Value | Source |
|---|---|---|
| Rovers | 3 (4 were planned at first) plus base station | [C1], [C6] |
| Rover size and mass | about 0.75 x 0.5 x 0.2 m with panels deployed; "less than 10 kg each" | [C5] |
| Computer | ModalAI VOXL, Qualcomm Snapdragon 821, 4 GB RAM, 32 GB flash | [C5] |
| Radio between agents | Microhard mesh network radios, "a minimum of 1Mbps of aggregate bandwidth shared between all participating stations"; TCP/IP interface | [C5], [C3], [C6] |
| Ranging | Ultra-wideband radios for formation keeping | [C7], [C6] |
| Radio problem found | Motor interference causes packet loss while driving; the database sends key data only in set windows | [C5] |
| Leader election | GHS spanning tree picks an appointer every 10 s; appointer picks the agent farthest from thermal and power limits; hysteresis | [C1] |
| Loss of leader | at most 10 s idle before a new leader plans | [C1] |
| State synchronisation to leader and designated survivor | every 10 s | [C1] |
| Wake and sleep | An FPGA outside autonomy's control shuts agents down at 25 and 55 minutes past the hour and restarts them at 0 and 30: 25-minute work cycles | [C1] |
| Thermal limit that drives planning | CPU 65 degrees C; near lunar noon rovers "can only drive for a few minutes" | [C1] |
| Battery floor used in planning | for example 20 % state of charge | [C1] |
| Exploration area | about 400 m2 on the Moon (planned); 6 x 6 m to 22 x 13 m in tests | [C7], [C1] |
| Formation goals in tests | 6 to 20 m away | [C1] |
| Radar | Multistatic ground-penetrating radar, imaging to about 10 m depth | [C7], [C2] |
| Mapping | Stereo cameras; robot-centred multi-resolution traversability maps in four layers, merged on the leader | [C5], [C1] |
| Lander | Intuitive Machines Nova-C, about 4 m tall; rovers lowered by tether about 1 m | [C6], [C7] |
| Surface time | one lunar day ("about 14 Earth days" [C7]; "about 10 Earth days" [C3]) | [C7], [C3] |
| Test record | ROS simulation with a fault matrix; flight-software farm on VOXL boards; development rovers in the JPL Mars Yard, day and night; flight rovers in the clean room, wake and sleep cycles "for over 9 hours"; full four-agent test on flight hardware on 22 Dec 2023; thermal-vacuum tests Oct to Dec 2023 | [C1], [C6] |
| Radio band and range | not found in any source read | n/a |

### D.3 What CADRE does not cover

1. **One owner.** No payments, no private information, no question of whose job comes first.
2. **Identical rovers.** No classes with different speed, payload or braking; no crew vehicles.
3. **No auction and no negotiation.** The authors chose a leader precisely to avoid the message load and the
   failure modes of auctions and shared-world planning on lossy surface links [C1].
4. **No roads and no traffic.** Tens of metres, open ground, three robots; collision avoidance is a corridor
   per rover and "all stop" on violation.
5. **No Earth blackout.** Reiner Gamma is on the near side, Earth is always in view through the lander, and the
   mission is one lunar day.
6. **A link is assumed.** The design needs a continuous, if slow, two-way channel between every agent and the
   leader [C1]. It has no mode for a partition lasting hours.
7. **No cargo.** Tasks are exploring and driving in formation, not hauling.

### D.4 How our work differs, and how to validate against CADRE

| Aspect | CADRE | Lunar ATC (our papers) |
|---|---|---|
| Owners | 1 | 3 in the main runs, 2 and 5 out of distribution [P1] |
| Vehicles | 3 identical, under 10 kg | 8 in six classes, 250 kg to tonnes, up to 8 times the fleet [P1], [P2] |
| Decision place | elected leader | Earth (strict, plan-ahead, relay), leader, auction, learned bids, oracle: 13 regimes [P1] |
| Links | mesh, at least 1 Mbit/s, always up by assumption | mesh on 5 m terrain, 5 km range, loss 0 to 0.40; Earth hidden 41 % of the time [P1] |
| Safety | per-agent constraint checks, abort messages | rules R1 to R10, exhaustive check, 274,580 encounters [P2] |
| Evidence | hardware and flight software tests | simulation only |

Validation steps we can take without anyone's permission:
1. **Reproduce CADRE as a degenerate case of our engine.** One owner, three identical rovers, base station,
   25-minute wake cycles, leader elected by "farthest from limits", 10 s synchronisation, a 400 m2 region. Our
   leader regime should then finish exploration and formation tasks, and our fault injections should reproduce
   the published behaviours: at most 10 s without a planner after the leader dies; all rovers stop when one
   leaves its corridor; two-rover operation when one is excluded.
2. **Run our auction on the CADRE case** and report the message count and bytes against the leader design. The
   CADRE authors claim the leader needs fewer messages [C1]; we can measure by how much in our model, and at
   what loss rate the ranking changes.
3. **Run CADRE's design on our case**: a leader with CADRE's rules, no fallback, under our partitions. This
   shows what the fallback buys.
4. **Compare predictions with flight data when IM-3 flies** (Q1 2027 at the earliest): leader changes per
   cycle, time lost per abort, packet loss while driving. Ask the team for logs (section G, item 1); if they
   decline, the published post-flight papers will still give aggregate numbers.
5. **Borrow their test ladder**: fault matrix per task (nominal, starts late, runs late, ends early, fails),
   then hardware-equivalent compute, then outdoor rovers, then flight hardware [C1], Table 1 and 2.

---

## E. Our design choice for coordination and failure handling

Stated as rules. Each rule has the guarantee it gives (G) and the assumption it needs (A). Proof sketches
follow. Rules R1 to R10 of [TS] stay as they are; the rules here sit above them (who decides) and beside them
(what happens when a robot fails).

### E.0 The rules

| # | Rule | Guarantee (G) | Assumption (A) |
|---|---|---|---|
| A1 | **Allocation is an auction of single jobs.** Each free robot bids its marginal job-hours for each open job it can reach by radio; the best bid wins one job; repeat. Bundle depth 1 by default, depth 2 at most. | Per round, at least 1/2 of the best total score (E.1, case L = 1); no robot holds two jobs; no job has two holders once messages settle. | Bids are comparable (one cost model, audited [P3]); the round's messages reach all bidders within the round time, or the job stays open (delay, not conflict). |
| A2 | **A leader plans when the mesh is whole.** The base computer, or an elected robot if the base is silent, runs the same auction centrally over the state it has and sends awards. | Same allocation as A1 with fewer messages; in [P1] 0.26 h from the full-information marketplace. | Leader reachable by every robot within the round time. |
| A3 | **Fallback is automatic and one-way per epoch.** A robot that has not heard a leader award or heartbeat for T_lead falls back to A1 with the robots it can hear. A leader's awards carry an epoch; a robot ignores awards from an older epoch. | Two leaders never both command one robot; allocation continues in every connected group. | Clocks agree within the time-out; epochs only increase (kept in non-volatile memory). |
| A4 | **Learned bids only as a bounded correction** to the hand-built bid, per job, not depending on the bundle. | The auction's conflict-freedom is unchanged; DMG is kept (E.1). | The correction is the linear model of [P1] (13 weights) or an audited successor. |
| T1 | **Reserve before entering.** A vehicle enters a road segment, junction tile, pad apron or charger slot only with a confirmed reservation, and treats an unconfirmed one as refused. | No two complying vehicles in one exclusive segment at one time (E.2). A lost message adds delay only. | One reservation authority per segment at any time (A3 epochs); position error within the margin. |
| T2 | **Hold until clear.** A reservation ends when its holder reports, or is seen, clear of the segment, not when its planned window ends. | Lateness cannot cause a collision. | Reports or sightings eventually arrive; otherwise the segment stays closed (R7). |
| T3 | **Brick-wall gap in one-lane segments.** A follower keeps a gap of at least its own full stopping distance plus margin (as if the leader could stop instantly). | Closes the dead-stop exception of [P2] type 9. | Own braking at least a_min; sight or radio range covers the gap. |
| T4 | **Speed is capped by what the vehicle can see** (E.3), with the reaction delay of whoever is in the loop. | The vehicle can stop inside its clear distance. | Perception range and friction bound are honest. |
| F1 | **Heartbeats.** Every vehicle sends a heartbeat every T_hb; a neighbour that misses k in a row marks it "silent"; the leader (or, in fallback, the group) marks it "failed" after a second, longer time-out or a sighting. | Detection within (k + 1) T_hb; false alarms below a chosen rate (E.5). | Loss is not total; k is set for the measured loss. |
| F2 | **Re-auction with epochs.** A failed vehicle's job is reopened with its epoch raised by one. The old holder, if it returns, drops the job unless it already carries the cargo, in which case it says so and the new award is cancelled. | At most one robot holds the cargo; at most one wasted approach. | Epoch numbers reach both robots before the hand-over point. |
| F3 | **A silent vehicle keeps its road.** Its last reserved volume stays closed until it is seen or towed (R7). Jobs that need that segment are re-routed or wait. | Safety does not depend on the failure detector being right. | Alternative routes or bays exist (well-formed layout). |
| F4 | **Cargo on a dead vehicle is a team job.** It is posted as a two-robot task with a commit step and a time-out. | The cargo is not lost to the schedule; meeting failures are bounded (measured in [P1] H6). | A second robot with a lifting or towing interface is in range. |
| F5 | **Lost link: go to coverage.** A robot out of contact for T_rally finishes its current leg and drives to the nearest point with known coverage. | Share of robot-time out of contact stays low (5.1 % against 83.1 % without the rule [P1]). | Coverage map on board. |
| H1 | **People on Earth are asked, not waited for.** Any request to Earth has a default action taken on time-out (hold at a safe point, or the conservative option). | No decision blocks longer than its time-out. | Defaults are safe by construction (they only stop or wait). |

### E.1 Proof sketch: the CBBA / greedy 50 % bound and its assumption

Setting. Robots i, jobs j. An assignment A is a set of pairs (i, j) with each job in at most one pair and at
most L jobs per robot. Robot i scores its set of jobs A_i by S_i(A_i) (computed with its best visiting order);
the team score is F(A) = sum of S_i(A_i). The marginal score of j for i, given the jobs b it already holds,
is c_ij(b) = S_i(b + j) - S_i(b).

Assumption (DMG, diminishing marginal gain): c_ij(b) >= c_ij(b + k) for every job k. In words: a job is never
worth more to a robot that already holds more. Scores are also non-negative at the margin, because a robot
only adds jobs that raise its score.

Step 1 (CBBA equals sequential greedy). The sequential greedy algorithm (SGA) repeatedly takes the pair (i, j)
with the largest marginal score among the pairs still allowed, and fixes it. Under DMG the largest bid
anywhere in the network can never be beaten later, because every other bid can only fall as bundles grow. So
after at most D communication rounds (D = network diameter) every robot agrees on that pair. Repeat for the
next pair: n pairs are agreed after at most n D rounds. This is the published convergence statement, O(n_t D)
rounds, and the published claim that CBBA reaches the SGA solution ([L1], Opened). Without DMG a later bid can
overtake an earlier winner and the consensus can cycle.

Step 2 (greedy is at least half of optimal when the limit L does not bind). Let G be the greedy assignment,
built in the order g_1, g_2, ..., with G_k the first k picks, and let O be an optimal assignment.
- Monotone: F(O) <= F(O union G). (Give each robot the union of its jobs; marginals are non-negative.)
- DMG means F is submodular on pairs, so F(O union G) - F(G) <= sum over o in O not in G of [F(G + o) - F(G)].
- Take such an o = (i', j). If greedy gave job j to some robot at step k, then at that moment o was still
  allowed (job j was free and robot i' had room, since L does not bind), so greedy's gain at step k was at
  least o's marginal then, which by DMG is at least o's marginal at the end. Charge o to g_k. If greedy never
  assigned j, then o was allowed to the end and greedy did not take it, so its marginal is not positive.
- Each greedy pick is charged at most once, because O contains each job once. The greedy gains sum to F(G).
- Hence F(O) <= F(G) + F(G), that is F(G) >= F(O) / 2.

Step 3 (L = 1). With one job per robot the score is a plain sum of pair values and the problem is a maximum
weight matching. Greedy matching is at least half of optimal: each greedy pair (i, j) blocks at most two pairs
of O (the one using i and the one using j), each worth no more than (i, j) when it was picked. No DMG needed.
This is the case of rule A1.

Step 4 (1 < L, limit binding): only 1/3 follows from this argument. If robot i' is already full when job j is
awarded elsewhere, o = (i', j) was not allowed at that step and must be charged instead to one of the L earlier
picks of robot i' (each of which beat o when it was made). A greedy pick can then be charged twice, once by
job and once by robot, giving F(O) <= 3 F(G). This matches the general theorem for greedy on a submodular
score under two matroid constraints (Fisher, Nemhauser, Wolsey 1978; standard result, not re-read). The
truncated score "best L jobs out of a set" is not submodular in general (we built a four-job coverage
counterexample: marginal 0 given {a, b} but 2 given {a, b, d}), so the simpler argument does not rescue 1/2.
**Flag:** the CBBA papers we could read state 50 % without separating these cases; the journal proof was not
readable. Until checked, quote "50 % when the bundle limit does not bind or bundles hold one job; 1/3 proven
by us otherwise".

What the bound does not cover. It is for one allocation round with truthful, comparable bids, a connected
network and perfect information about jobs. It says nothing about the time-extended schedule, about message
loss (measured instead: [MOA], [P1] E41), or about owners who shade bids ([P3] H5). A learned correction that
depends only on (robot, job) features keeps DMG; one that depends on the bundle can break it [MOA].

### E.2 Proof sketch: a reservation table with non-overlapping entries and a stopping margin gives no collisions

Model. The road network is cut into segments (one-lane stretches, junction tiles, aprons). A reservation is a
triple (vehicle, segment, window). The table is held by one authority per segment at any time. Each vehicle
has length l, position error at most e, guaranteed braking a_min, and a margin m >= e + l/2.

Rules used: T1 (enter only with a confirmed reservation), T2 (hold until clear), and:
- I2: the authority confirms a reservation for an exclusive segment only if its window does not overlap, with
  a buffer, any other confirmed and unreleased reservation for that segment.
- I3: a vehicle's speed is such that it can stop before the end of the last segment it holds:
  v^2 / (2 a_min) + v t_r + m <= distance to that boundary.

Claim. Two vehicles that both obey the rules never occupy the same exclusive segment at the same time; so
they cannot collide inside one.

Sketch.
1. A vehicle's body, widened by m, is always inside segments it holds: it starts so, T1 forbids crossing into
   a segment it does not hold, and I3 guarantees it can stop before the boundary if the next reservation has
   not arrived. A lost or late confirmation therefore leaves it stopped inside its own segments.
2. Suppose A and B are both in exclusive segment s at time t. By step 1 both hold confirmed, unreleased
   reservations on s at t. The authority confirmed one of them second; at that moment the other was confirmed
   and unreleased, so by I2 their windows do not overlap, and by T2 the first is released only when its
   holder is clear of s. So the second holder cannot be inside s before the first has left. Contradiction.
3. Junction tiles and aprons are exclusive segments, so the same argument covers crossing and merging.
4. Same-direction following inside a long shared segment is not covered by exclusivity; there T3 applies: with
   gap >= v t_r + v^2 / (2 a_min) + m the follower stops short of the leader's present position even if the
   leader stops instantly.

Assumptions, each of which is a way the proof can fail in reality:
- (a) position error really is below e (covered by the positioning note);
- (b) braking really is at least a_min on the slope and soil at hand (R2; friction is poorly known [TS]);
- (c) one authority per segment: two leaders after a partition must not both grant s. Rule A3's epochs give
  this if a new leader may grant a segment only after the old leader's grants have expired or been handed
  over, and a robot in a minority group gets no new grants and stops at a safe point;
- (d) clocks agree within the buffer;
- (e) every vehicle complies. A vehicle that does not (another bloc's rover, a fault) is outside the proof and
  is handled by sensing and T4.
Liveness is separate: exclusivity alone allows deadlock (a ring of one-lane segments deadlocked in 3.9 % of
encounters in [P2]). R3's exit-slot rule removes it on well-formed layouts; the ring needs a fixed acquisition
order or one more bay than vehicles.

### E.3 Maximum safe speed against perception range, lunar braking and reaction delay

A vehicle that sees clear ground for d_p metres, reacts after t_r seconds and then brakes at a must stop
within d_p less a margin d_0:

    v t_r + v^2 / (2 a) <= d_p - d_0,   so   v_max = -a t_r + sqrt( a^2 t_r^2 + 2 a (d_p - d_0) ).

On level ground a = mu g with g = 1.62 m/s2; on a downhill slope theta, a = g (mu cos theta - sin theta), and
no stop is possible when mu <= tan theta ([TS] table).

Reaction delay t_r: on board, 0.5 to 1 s (sensing, decision, actuation). With a person on Earth in the loop,
at least 2.56 s of light time plus ground processing and human reaction: 5.0 s in our papers [P3], 6 to 10 s
in NASA's plan for VIPER [M26], 4 to 8 s in NASA's LTV study [L5].

Computed with d_0 = 2 m, level ground (speeds in km/h):

| mu | d_p (m) | t_r = 0.5 s | 1 s | 3 s | 6 s | 10 s |
|---|---|---|---|---|---|---|
| 0.30 | 10 | 9.2 | 8.4 | 6.1 | 4.0 | 2.7 |
| 0.30 | 20 | 14.2 | 13.4 | 10.7 | 7.9 | 5.6 |
| 0.30 | 40 | 21.0 | 20.2 | 17.3 | 13.8 | 10.5 |
| 0.45 | 10 | 11.1 | 9.9 | 6.7 | 4.2 | 2.7 |
| 0.45 | 20 | 17.2 | 16.0 | 12.2 | 8.5 | 5.8 |
| 0.45 | 40 | 25.5 | 24.3 | 20.1 | 15.3 | 11.3 |
| 0.60 | 10 | 12.6 | 11.1 | 7.2 | 4.3 | 2.8 |
| 0.60 | 20 | 19.6 | 18.1 | 13.2 | 8.9 | 6.0 |
| 0.60 | 40 | 29.2 | 27.6 | 22.2 | 16.4 | 11.7 |

Check of one cell: mu = 0.45, a = 0.729 m/s2, d_p = 20 m, t_r = 6 s: -4.374 + sqrt(19.13 + 26.24) = 2.36 m/s
= 8.5 km/h.

Reading. (1) With on-board reaction the LTV speeds NASA ordered (10 to 15 km/h) need about 20 m of trustworthy
sight; with 10 m they must slow to about 10 km/h. (2) With Earth in the loop at 6 to 10 s the cap is 3 to 9
km/h for 10 to 20 m of sight, before any allowance for the operator reading the scene; NASA measured 2.03 and
1.76 km/h average at 6 and 8 s [L5], inside these caps. (3) At long delay the friction coefficient hardly
matters (the delay term dominates), at short delay it does. (4) The low-sun lighting of the pole shortens d_p;
that belongs to the maps and perception notes.

### E.4 Operator workload against fleet size and autonomy level

Fan-out (Olsen and Wood [L6]): FO = AT / IT, the time a robot works usefully after a command divided by the
time the operator spends on it. In rate form, for N vehicles each asking for help lambda times per hour, each
request taking h hours of one person, and operators loaded to at most rho_max:

    operators needed M = ceil( N lambda h / rho_max ),   fan-out per operator = rho_max / (lambda h).

With Earth delay each request takes longer: h = h_0 + n_rt T_rt for n_rt command-response exchanges of
round-trip time T_rt. In a blackout Earth cannot serve at all, and the vehicle waits (E.5).

Computed for rho_max = 0.7:

| Autonomy level | lambda (per vehicle-hour) | h (min) | Fan-out | Operators for 8 / 20 / 50 vehicles | Anchor |
|---|---|---|---|---|---|
| 0 Waypoint teleoperation | continuous | continuous | about 0.25 | 32 / 80 / 200 | VIPER: about four roles per rover [M26] |
| 1 Supervised drive segments | 6 | 2 | 3.5 | 3 / 6 / 15 | LTV remote driving with assists [L5] (Assumed rate) |
| 2 Task-level autonomy | 1 | 5 | 8.4 | 1 / 3 / 6 | Coventry: 5 to 7 vehicles watched well [L7] |
| 3 Fleet-level autonomy, exceptions only | 0.2 | 10 | 21 | 1 / 1 / 3 | CADRE-style high-level commands [C1] (Assumed rate) |
| 4 On-Moon dispatch and traffic, people audit | 0.05 | 15 | 56 | 1 / 1 / 1 | Waymo: about 43 vehicles per agent [L8] |

The rates lambda and h are assumptions chosen to bracket the published anchors; the formula is the result.
Per shift, multiply by three to five for round-the-clock cover. The step that matters is from level 1 to
level 2: below it the staff grows with the fleet, above it one console per owner is enough. Our own runs put
the rules' effect on operator hours at +7.4 h a year, with an interval that includes zero ([P2] 5.2).

### E.5 Expected task-completion delay after a rover failure, under re-auction with a heartbeat time-out

Detection. Heartbeat period T_hb; declare silence after k consecutive misses. A failure at a random phase is
detected between k T_hb and (k + 1) T_hb later, mean (k + 1/2) T_hb. With independent loss probability p per
heartbeat, a live robot is wrongly marked silent at any given heartbeat with probability p^k, so the
false-alarm rate is (86,400 / T_hb) p^k per robot-pair per day.

| T_hb | k | Mean detection | False alarms per day at p = 0.10 | at p = 0.40 |
|---|---|---|---|---|
| 10 s | 3 | 35 s | 8.6 | 553 |
| 10 s | 5 | 55 s | 0.09 | 88 |
| 10 s | 8 | 85 s | 0.0001 | 5.7 |
| 10 s | 12 | 125 s | below 1e-6 | 0.15 |

So k must follow the measured loss: 5 at 10 % loss, about 12 at 40 %. Bursty loss needs more (the i.i.d.
assumption is optimistic), which is why F1 uses a second confirmation and F3 never lets safety depend on it.
CADRE's figures for comparison: state sent every 10 s, a new leader within 10 s [C1].

Expected extra delay of the job, decided on the Moon:

    E[dT] = (k + 1/2) T_hb            detection
          + R T_round                  re-auction, R rounds of T_round (one round is about D hop-times)
          + E[d_new] / v               approach of the new winner from where it is
          + q T_xfer                   if the cargo is on the dead rover (probability q): team-lift setup
          - T_saved                    work the failed rover had left that the new one does not repeat

Worked example (inputs Assumed, to be replaced by engine values): T_hb = 10 s, k = 5, R = 2, T_round = 10 s,
new winner 1.5 km away at 4 km/h (hauler class), q = 0.5, T_xfer = 1.0 h (`TEAM_SETUP_H` in the engine):
55 s + 20 s + 22.5 min + 30 min = about 54 min, of which detection and auction are 75 s. Travel and transfer
dominate; shaving the heartbeat below 10 s buys nothing.

If the decision must wait for Earth. Let Earth be hidden in gaps of length G separated by windows of length W.
A failure at a random time falls in a gap with probability G / (G + W) and then waits G / 2 on average:

    E[wait for Earth] = ( G / (G + W) ) ( G / 2 ).

For our base, G about 11 days = 264 h and W about 16 days [P1]: 0.407 x 132 h = 54 h. With an 80 % relay and
outages of a few hours the same formula gives well under an hour, but the relay does not reach sites that
never see it (the oxygen plant) [P1]. This 54 h is the number to set against 54 minutes: the reason failure
handling belongs on the Moon.

---

## F. Simulation parameters for the backend engineer

Tags: [S] sourced, [D] derived here, [A] assumed and to be swept. Existing engine values are kept where they
exist; new ones are for the failure and CADRE-replica experiments.

| Parameter | Value | Sweep range | Unit | Source |
|---|---|---|---|---|
| Lunar gravity | 1.62 | fixed | m/s2 | [TS] [S] |
| Braking friction coefficient mu | 0.45 | 0.30, 0.45, 0.60 | none | [TS] [A] |
| On-board reaction delay t_r | 1.0 | 0.5 to 3 | s | [TS] R1 [A] |
| Earth-in-loop reaction delay | 5.0 | 2.6, 5, 6, 8, 10 | s | [P3]; [M26] 6 to 10 s; [L5] 4 to 8 s [S] |
| Light time, round trip | 2.56 | 2.38 to 2.71 | s | E-M distance / c [D] |
| Perception range d_p for speed cap | 20 | 10, 20, 40 | m | [A] (needs the perception note) |
| Stop margin d_0 | 2 | 1 to 5 | m | [A] |
| Speed cap | formula E.3 | n/a | m/s | [D] |
| Teleoperated mean speed against delay | 3.24, 2.56, 2.03, 1.76 at 0, 4, 6, 8 s | use as a lookup | km/h | NASA/TM-20240001217 [L5] [S] |
| LTV remote-drive requirement | 6 (threshold), 8 (goal) | check only | km per 24 h | [L5] [S] |
| LTV top speeds as ordered | CLV-1 over 9.7; Pegasus over 14.5 | 10 to 15 | km/h | [M1] (6 and 9 mph) [S] |
| VIPER speeds | 0.20 max; 0.10 prospecting; 0.008 made good | fixed | m/s | [M26] [S] |
| Heartbeat period T_hb | 10 | 1, 10, 60 | s | CADRE sync 10 s [C1] [S]; sweep [A] |
| Misses before "silent", k | 5 | 3, 5, 8, 12 | count | E.5 [D] |
| Confirmation time-out before "failed" | 120 | 60 to 600 | s | [A] |
| Leader time-out T_lead (fallback to auction) | 30 | 10 to 300 | s | CADRE: 10 s to a new leader [C1] [S]; value [A] |
| Leader election period | 10 | 10 to 1,800 | s | [C1] [S] |
| Auction round time T_round | 10 | 1 to 60 | s | [A]; [P3] measured 1.12 s for 1 round in 100 on flight-class compute |
| Auction rounds per orphaned job R | 2 | 1 to 5 | count | [A] |
| Bundle depth L | 1 | 1, 2, 5 | jobs | [P1] E41 [S] |
| Message loss p | 0.10 | 0, 0.10, 0.25, 0.40; add bursty (Gilbert-Elliott) | probability | [P1], [MOA] [S] |
| Extra loss while driving | 0 | 0, 0.1, 0.3 added to p | probability | CADRE motor interference [C5], size [A] |
| Mesh rate available for coordination | 1,000 | 100 to 1,000 | kbit/s shared | CADRE at least 1 Mbit/s [C5] [S]; our need 7.68 kbit/s for 20 robots [P3] |
| Radio range | 5 | 2, 5, 10 | km | [P1] [A] |
| Lost-link rally time-out T_rally | engine default | 0.5 to 6 | h | [P1] E41 [S] |
| Hold of a silent vehicle's reservation (R7) | 10 | 1 to 60 | min | [TS] [A] |
| Team-lift setup / cargo transfer T_xfer | 1.0 | 0.5 to 3 | h | engine `TEAM_SETUP_H` [S] |
| Commit time-out for meetings | 1.0 | 0.25 to 2 | h | [P1] H6 [S] |
| Probability cargo is aboard at failure q | 0.5 | from the engine's duty cycle | probability | [A] |
| Rover failure rate (hard, mission-ending) | 1 per 2 vehicle-years | 0.1 to 5 per vehicle-year | 1/year | [A]; no fleet statistics exist. Sanity: the two commercial rovers of 2025 whose fate we read (Tenacious, MAPP) never drove, both because the lander failed [M18], [M19] |
| Soft failure (stuck, safe mode; recovers) | 12 per vehicle-year | 1 to 50 | 1/year | [A] |
| Soft-failure recovery time | 6 | 1 to 48 | h | [A] |
| Earth window W and gap G at base | 16 and 11 | R-1 files, 2028 to 2046 | days | [P1] [S] |
| Relay availability | 0 | 0, 0.8, 1.0 | fraction | [P1] [S] |
| Operator handling time h and request rate lambda | table in E.4 | as in table | min, 1/h | [A], anchored on [M26], [L7], [L8] |
| Operator load cap rho_max | 0.7 | 0.5 to 0.9 | fraction | [A] |
| CADRE replica: agents | 3 rovers + base | fixed | count | [C1] [S] |
| CADRE replica: rover mass, size | under 10; 0.75 x 0.5 x 0.2 | fixed | kg; m | [C5] [S] |
| CADRE replica: duty cycle | 25 on, 5 off | fixed | min | [C1] [S] |
| CADRE replica: region and goal distance | 400; 6 to 20 | 36 to 400; 6 to 20 | m2; m | [C7], [C1] [S] |
| CADRE replica: planner tick and commit window | 1 Hz; 5 s | fixed | Hz; s | [C1] [S] |
| South-pole fleet scenario 2028 to 2029 | 2 LTVs, 1 PROMISE, 4 drones, 1 VIPER, 2 to 4 small rovers; 3 to 6 owners | as listed | vehicles | [M1], [M4] [S]; small rovers [A] |

New experiments these parameters call for: (1) hard and soft failures with re-auction (E.5), on-Moon against
Earth-decided; (2) forced mesh partitions of 1 to 24 h for the leader-with-fallback rule; (3) the CADRE replica
(D.4); (4) the brick-wall gap T3 in encounter type 9; (5) k against bursty loss.

---

## G. Who to partner with, and for what

Ranked inside each group by (what they have that we lack) times (chance a three-person research team gets a
reply). "URL checked" means the address answered on 11 Nov 2026; content was read only where a source tag is
given.

### G.1 Realistic in the next 12 months

| # | Organisation | What they have that we need | What we can offer | How to approach | URL |
|---|---|---|---|---|---|
| 1 | JPL CADRE autonomy team (F. Rossi, J.-P. de la Croix, G. Rabideau and colleagues) | The only flight-qualified multi-rover autonomy; test logs; after IM-3, flight data | An open simulation replica of CADRE (D.4), a measured leader-against-auction comparison under partitions, and the multi-owner extension they do not cover | Submit the replica study to the MASSpace workshop at AAMAS (where they publish) and to ASTRA; write to the corresponding author named on the ASTRA abstract with the replica results and one precise data request | https://ai.jpl.nasa.gov/public/projects/cadre/ (Opened [C11]) |
| 2 | Lunar Surface Innovation Consortium (APL for NASA) | The US community's forum; focus groups on excavation and construction, power, and (by snippet) interoperability | A talk: "what a mixed-fleet traffic and job layer costs and saves", with our three papers | Join as an organisation and ask for a focus-group slot. Membership terms UNVERIFIED (site timed out); more than 3,500 members by snippet | https://lsic.jhuapl.edu/ (URL checked) |
| 3 | LOGIC, the Lunar Operating Guidelines for Infrastructure Consortium (DARPA, run by APL) | The place where interface guidelines are written, including "cislunar space traffic control" and surface surveying | A draft "surface traffic and job-exchange" guideline with a reference simulator and test vectors | Ask to join the relevant working group; the 2023 release gives the address | https://logic.jhuapl.edu (URL checked; described in [L17]) |
| 4 | University of Luxembourg SnT SpaceR and Tohoku University Space Robotics Lab (OmniLRS authors) | An open photorealistic multi-robot lunar simulator; lab rovers and a lunar sand room (lab facilities not verified) | Our dispatch, mesh and rules layer as a plug-in scenario; a co-authored benchmark paper | E-mail the OmniLRS authors with a concrete scenario pull request | https://github.com/OmniLRS/OmniLRS (URL checked); paper [L9] |
| 5 | Space ROS / Open Robotics, and the Open-RMF project | Flight-style ROS 2 stack with demos; a working multi-vendor traffic and bidding framework for Earth robots | A lunar multi-rover demo for Space ROS; a study of what Open-RMF's traffic negotiation needs to survive loss and blackouts | Open an issue and a pull request in the demos repository; present at ROSCon | https://space.ros.org/ and https://github.com/space-ros/demos (Opened [L18]); https://www.open-rmf.org/ (URL checked) |
| 6 | DFKI Robotics Innovation Center, Bremen (CoRob-X lead; Team BREMEN, winner of the Space Resources Challenge) | Heterogeneous rovers that have worked as a team in the field; a rover that fits a two-owner test | Protocol and safety layer to run on their rovers; analysis of their field logs | Propose a joint paper; ask about the next ESA or EU call | https://robotik.dfki-bremen.de/en/startpage (URL checked; project facts [L12], [L13]) |
| 7 | DLR Institute of Robotics and Mechatronics (ARCHES; LRU rovers) | Field-proven rover team, Etna experience, a seat in LUNA | Same as 6; our Earth-window and blackout model for their mission-control concept | Contact through the ARCHES authors; meet at ASTRA or IAC | https://www.dlr.de/en/rm (URL checked); [L11] |
| 8 | University of Toronto ASRL (two-rover cargo carrying, with the Canadian Space Agency's analogue terrain) | Hardware proof of cooperative transport; convoy radio measurements | Allocation and commit protocol for cross-owner lifts ([P1] H6) to pair with their control layer | Cite and write; propose a joint simulation-plus-hardware paper | https://utiasasrl.github.io/ (URL checked); paper in [MOA] |
| 9 | LUNA analog facility (ESA and DLR) | A regolith hall with lighting for robots and crew | A compact multi-owner rover test campaign | Send the LUNA Utilization Request Form now; the hall is booked through June 2027, so aim at the second half of 2027 | https://luna-analog-facility.de/en/for-users/working-and-testing-in-luna/ (Opened [L14]) |
| 10 | NASA Ames Lunar Lab and SSERVI Regolith Testbed | Simulant beds with polar lighting | A small-rover test with perception under low sun | Write to the contact on the page for availability and pricing; as a non-US team expect to need a US partner | https://sservi.nasa.gov/testbed/ (Opened [L15]) |
| 11 | ESRIC (Luxembourg) and the ESA Space Resources Challenge | Competition with field tests, prize contracts, a start-up programme (programme details not read) | A team or a sub-team for the coordination part of a multi-robot entry | Watch for the third edition's call; contact ESRIC | https://www.esric.lu/ (URL checked); [L13] |
| 12 | Mission Control (Canada) | Operations software flown or contracted on rover missions; the Rashid 2 to Firefly lander link | Multi-owner dispatch and traffic logic to sit on top of their operations software | Direct contact; they are small enough to answer | https://missioncontrolspace.com/ (Opened [M23]) |
| 13 | Conferences as the venue ladder | Reviewers and the people above in one room | The three papers | IAC (IAF), ASTRA (ESA), i-SAIRAS, IEEE Aerospace, the MASSpace workshop | https://www.iafastro.org/events/iac/ (URL checked) |
| 14 | NASA challenges (Lunar Autonomy Challenge format; Lunabotics) | A ready simulator and an audience | If a multi-agent edition is announced, enter; otherwise propose one to APL | The 2025 edition was for US university teams only [L10]; a US university partner would be needed | https://lunar-autonomy-challenge.jhuapl.edu/ (URL checked) |

### G.2 Long shots

| # | Organisation | What they have | What would have to be true | URL |
|---|---|---|---|---|
| 15 | NASA Moon Base programme office and the LTV Services office | The power to write an interface into task orders | They decide mixed-fleet coordination is a requirement; we would enter through LSIC, LOGIC or a US prime, not directly | https://www.nasa.gov/commercial-lunar-payload-services/ (URL checked) |
| 16 | Venturi Astrolab and Lunar Outpost | The two crew rovers of 2028 and their operations software | One of them wants a neutral traffic layer rather than its own; our offer is the simulator as a shared test bench | https://www.astrolab.space/ ; https://www.lunaroutpost.com/ (URLs checked) |
| 17 | Intuitive Machines (Lunar Data Network), later ESA Moonlight | The relay that our Earth link and "80 % relay" cases depend on | They share coverage and outage models | https://www.intuitivemachines.com/ (URL answered with a redirect) |
| 18 | Blue Origin, Firefly, Voyager / Astrobotic (CLPS 2 landers that carry other people's rovers) | Lander-side radios and deployment sequences | They want payload rovers to deconflict on their own | https://voyagertechnologies.com/ ; https://fireflyspace.com/missions/blue-ghost-mission-2/ (URLs checked) |
| 19 | CCSDS and IOAG (space data standards; the agencies' interoperability group) | Formal standards for links below our layer | Membership is by agency; a research team contributes through its national agency or as an invited expert | https://ccsds.org/ ; https://ioag.org/ (URLs checked) |
| 20 | LunaNet Interoperability Specification team (NASA SCaN) | The network specification our messages must ride on | They take comments on surface-to-surface services, which [P2] notes are left to bilateral agreement | https://www.nasa.gov/directorates/somd/space-communications-navigation-program/lunanet-interoperability-specification/ (URL checked) |
| 21 | UN COPUOS Action Team on Lunar Activities Consultation (ATLAC) | The inter-governmental track on consultation for lunar activities; work plan 2025 to 2027 (snippets) | Access is through a national delegation or an observer organisation such as the Moon Village Association | https://www.unoosa.org/oosa/en/ourwork/copuos/atlac/index.html (URL checked, content not read); https://moonvillageassociation.org/ (URL checked) |
| 22 | Chang'e 8 / ILRS participants (HKUST, METU, SUPARCO and others) | The first planned multi-maker robot team on the Moon | Open publication of their coordination scheme; partnership is constrained by export-control and bloc politics on both sides | see [M11] |
| 23 | KSC Swamp Works, JSC Rock Yard, Glenn SLOPE | Large regolith bins and mobility rigs | A NASA-funded partner brings us in | not opened |

What we can offer everyone, stated plainly: three papers with pre-registered results, an open engine that
runs a year of base logistics in minutes, a rule set with an exhaustive check, and no stake in any vehicle.
What we lack: hardware, flight heritage, and a US or ESA contract vehicle. The first three rows of G.1 cost
only writing time and should be done first.

---

## H. A staged validation plan on Earth

Each stage has one question, a setup, and pass criteria written before the stage is run (the pre-registration
habit of phase 5). A stage that fails sends work back, not forward.

| Stage | Question it answers | Setup | Pass criteria | What it cannot show |
|---|---|---|---|---|
| S0 Protocol model | Are the rules free of unsafe and stuck states, including failure and leader change? | Extend the [P2] checker with rules A3, T2, T3, F1 to F3: two leaders, epochs, a vehicle that dies in a segment | No unsafe state, no deadlock on well-formed layouts; each new rule, when removed, yields a counterexample; state count and traces stored | Anything continuous: braking, radio |
| S1 Simulation | Does failure handling work at fleet scale, and what does it cost? | `lunarsim` with section F parameters: hard and soft failures, partitions of 1 to 24 h, CADRE replica, T3 in type 9; optionally OmniLRS for perception-limited speed | (a) Zero hard violations in type 9 with T3 over 10,000 encounters (rule of three bound 3e-4); (b) on-Moon re-auction delay within 20 % of E.5's formula; (c) leader-with-fallback within 10 % of the oracle with partitions up to 24 h; (d) CADRE replica reproduces: planner back within 10 s of leader loss, all-stop on corridor exit, two-rover operation; (e) deadlock rate in the ring layout below 0.1 % with the new ordering rule | Real radios, real robots |
| S2 Radio hardware in the loop | Do the messages get through real radios at the loss and rate we assumed, and do the time-outs hold? | 3 to 6 mesh radios of the kind small rovers carry, cabled through a channel emulator (or programmable attenuators) driven by path loss from our terrain mesh model; protocol stack on flight-class single-board computers; injected motor noise | (a) Coordination traffic for 20 emulated robots at or below 10 kbit/s (target from [P3]: 7.68); (b) 99 % of auction rounds under 1 s at loss 0.10 on the target processor, or the round time is re-set and S1 re-run; (c) false "silent" alarms below 1 per robot-day at the chosen k under recorded bursty loss; (d) no reservation granted twice in 10^5 emulated partitions and merges | Antenna patterns on real terrain; multipath from real regolith |
| S3 Small-rover field test | Do robots of two "owners", running separately built software, share a yard through the protocol alone? | Three to five small rovers (10 to 50 kg class), two software teams that see only the protocol document; a sand or gravel yard of at least 30 x 30 m with a one-lane passage, two bays, a "pad" that closes, a person as "crew"; scaled speeds so that stopping distances match lunar ones | (a) 200 head-on, crossing and following encounters with zero contacts and zero entries without reservation; (b) a killed rover is detected and its job re-awarded within the predicted time plus or minus 30 %; (c) leader killed: fallback within T_lead, no double grant; (d) crew keep-clear never broken; (e) all logs replay in the simulator and match within stated tolerances | Lunar lighting, dust, thermal cycles, gravity |
| S4 Analogue campaign | Does it hold over kilometres, hours, terrain masking and a delayed, interrupted "Earth"? | A week at an analogue site (lava field or quarry; LUNA from mid-2027 for lighting and regolith) with three or more rovers of at least two institutions, a relay mast, mission control behind a 5 to 10 s delay and scheduled blackouts of hours | (a) A scripted day of 20 or more jobs completed with Earth blacked out for half of it, within 15 % of the completion time with Earth always up; (b) the same day with decisions referred to Earth shows the predicted loss (direction and rough size); (c) zero safety violations; (d) terrain-masked link loss within the error band of the mesh model; (e) one unscripted failure handled without operator driving | Flight environment; that is IM-3's and the LTVs' job |

Order and cost. S0 and S1 need only our time and can finish in the current phase. S2 needs radios and an
emulator: buy or borrow (a university wireless lab is enough). S3 needs rovers: partner rows 4, 6, 7 or 8 of
G.1, or low-cost platforms. S4 needs a partner and a site: plan it for late 2027, in step with CADRE's flight
data, so that S1's CADRE replica can be checked against the Moon at the same time.

---

## I. Open questions, risks, contradictions and sources

### I.1 Open questions

1. Does the 50 % bound hold for CBBA when the bundle limit binds (E.1, step 4)? Needs the journal proof.
2. What breaks first under long partitions: the allocation (duplicated work) or the reservation authority
   (blocked roads)? Needs experiment S1(c) and the S0 model with two leaders.
3. What is a defensible failure rate for a lunar rover? No fleet data; the commercial rovers sent in 2025
   (Tenacious, MAPP) were lost with or inside their landers before driving.
4. How should a vehicle that follows our rules treat one that follows none (another bloc, or a legacy rover)?
   Only sensing-based rules apply; is that enough on one-lane roads?
5. Is a leader acceptable to competing owners? CADRE's leader is trusted because there is one owner. With three
   owners the leader sees every bid; [P3] audits help, but the political question is open.
6. What will NASA require of the two LTV makers for uncrewed operation between crews, and will it include
   deconfliction with other vehicles? Not found in the releases read.
7. Braking on real regolith at 10 to 15 km/h in lunar gravity: no test data found; mu remains a sweep.
8. How much of the perception range survives low sun and long shadows (feeds E.3)?
9. Will Chang'e 8's robots of several makers use a published coordination scheme? Nothing found.

### I.2 Risks

- **Schedule.** Every date in B.6 has slipped at least once in 2026; no US commercial lunar lander had launched
  this year by early November; the 2028 fleet depends on Blue Moon Mark 1, which has not flown, and on New
  Glenn's rebuilt pad. A paper that says "2028" should say "planned".
- **Single customer.** The need for a mixed-fleet layer rests on NASA keeping two LTV makers and many CLPS
  rovers at one site. A change of policy (the programme was reshaped twice in 2026) removes it.
- **CADRE flies and works.** Then a leader-only design has flight heritage and ours has not. Mitigation: the
  replica and the partition experiment, done before the flight.
- **CADRE fails for reasons unrelated to autonomy** (both earlier Nova-C landers tipped). Then there is still
  no flight evidence for any multi-robot scheme; ground tests gain weight.
- **Over-claiming the market.** The published totals disagree by a factor of six and none isolates our layer.
- **Proof scope.** E.2 is a proof about complying vehicles on exclusive segments; type 9 and the ring layout
  show where reality leaves the model.
- **Secondary sources.** Several statuses rest on Wikipedia or trade press read this session (marked in I.3).
  Before any of them goes into a paper, the primary document should be opened.

### I.3 Findings that differ from the existing notes or the three papers

1. **CADRE's leader election runs all the time (an appointer every 10 s), not only once per wake cycle.**
   [MOA] summary point 8 and section 5 say the leader "is re-elected every 30 min wake cycle" / "on each
   wake". That is true as far as it goes (NASA's 2023 article says the same [C7]), but the AAMAS 2025 paper
   adds that an appointer is selected "every ten seconds", with hysteresis, and that leader loss costs at
   most 10 s [C1]. Also the work cycle is 25 minutes awake in every 30 (shutdown at :25 and :55).
2. **CADRE's radio rate is public.** [P3] says CADRE's "radio band, rate and range are not public". The MoonDB
   paper gives Microhard mesh radios with "a minimum of 1Mbps of aggregate bandwidth", rovers under 10 kg and
   0.75 x 0.5 x 0.2 m, a Snapdragon 821 with 4 GB RAM, and motor interference causing packet loss while
   driving [C5]. Band and range were still not found. P3's sentence should be narrowed to "band and range".
3. **CADRE's surface time.** [TS] uses "one lunar day (about 14 Earth days)" (NASA's wording [C7]); the team's
   own slides say "about 10 Earth days" [C3]. Minor; quote both or neither.
4. **The CBBA bound.** [MOA] quotes "at least 50 % under DMG" without qualification. Our derivation gives 1/2
   only when the bundle limit does not bind or bundles hold one job, and 1/3 otherwise (E.1). Not a
   contradiction of a paper (P1 runs depth 1 by default), but P1's related-work sentence should not state 50 %
   for deep bundles without the caveat.
5. **Contract ceilings moved on 7 November 2026**, after the papers were built (30 October): CLPS 1 from 2.6 to
   4.2 billion USD, CLPS 2 awarded to eight companies with a 10 billion USD ceiling, a nuclear rover (PROMISE)
   added for late 2028 [M4]. No sentence in the three papers was found to conflict, but P3's vehicle list for
   2028 to 2032 can now add PROMISE.
6. **Confirmed, not contradicted:** "NASA's Lunar Terrain Vehicle task orders of May 2026 went to two
   companies" ([P1], [P2]) matches NASA release 26-046 [M1]; "IM-3 NET Q1 2027" in [TS] matches [M3]; VIPER's
   10 to 20 cm/s in [TS] matches [M26]; the teleoperation speeds in [TS] match [L5].
7. **Schedule context for P3's "2028 to 2032".** Blue Moon Mark 1's first flight moved to early 2027, Chang'e 7
   to 2027, Griffin-1 to January 2027 at the earliest, ispace's US mission to 2030. Nothing in P3 depends on a
   2026 landing, but the phrase "known by name" should stay "planned".

### I.4 Sources

Opened this session (page or PDF read). Dates are publication dates; all were read on 11 Nov 2026.

CADRE
- [C1] Rabideau, Russino, Branch, Dhamani, Stegun Vaquero, Chien, de la Croix, Rossi, "Planning, Scheduling,
  and Execution on the Moon: The CADRE Technology Demonstration Mission", AAMAS 2025, pp. 1727-1735.
  https://www.ifaamas.org/Proceedings/aamas2025/pdfs/p1727.pdf
- [C2] Rabideau et al., "Multi-Robot Cooperative Autonomy on the Moon: The CADRE Technology Demonstration
  Mission", ASTRA 2025 (extended abstract).
  https://ai.jpl.nasa.gov/public/documents/papers/CADRE-ASTRA-2025-Extended-Abstract.pdf
- [C3] Rossi and de la Croix, "CADRE: Multi-Agent Autonomy for Space Exploration", MASSpace '24 slides,
  7 May 2024. https://ai.jpl.nasa.gov/public/documents/presentations/CADRE-AAMAS-Slides.pdf
- [C4] Albee, Bhamidipati, Rossi, Vander Hook, de la Croix, "Lunar Leader: Persistent, Optimal Leader Election
  for Multi-Agent Exploration Teams", MASSpace 2024 (read in part).
  https://ai.jpl.nasa.gov/public/documents/papers/leader-election-MASSpace-paper.pdf
- [C5] Saboia, Rossi, Nguyen, Lim, Aguilar, de la Croix, "CADRE MoonDB: Distributed Database for Multi-Robot
  Information-Sharing and Map-Merging for Lunar Exploration", MASSpace 2024 (read in part).
  https://ai.jpl.nasa.gov/public/documents/papers/MoonDB-MASSpace-paper.pdf
- [C6] Shelton (JPL), "Maintaining Reliability in a Harsh Environment: The Design and Delivery of the CADRE
  Lunar Rovers and Base Station", Space Power Workshop 2025 slides.
  https://spw.aerospace.org/files/2025/07/2_MPE_M.-Shelton_Presentation.pdf
- [C7] NASA / JPL, "NASA's Trio of Mini Rovers Will Team Up to Explore the Moon", 2 Aug 2023 (page updated
  22 Jun 2026). https://www.nasa.gov/technology/robotics/nasas-trio-of-mini-rovers-will-team-up-to-explore-the-moon/
- [C8] JPL, "NASA's Mini Rover Team Is Packed for Lunar Journey", 11 Feb 2025.
  https://www.jpl.nasa.gov/news/nasas-mini-rover-team-is-packed-for-lunar-journey/
- [C9] JPL, CADRE mission page. https://www.jpl.nasa.gov/missions/cadre
- [C10] NASA, CADRE page, last updated 9 Jul 2025.
  https://www.nasa.gov/cooperative-autonomous-distributed-robotic-exploration-cadre/
- [C11] JPL AI group, CADRE project page. https://ai.jpl.nasa.gov/public/projects/cadre/
- Not opened (paywall or not found): de la Croix et al., "Multi-Agent Autonomy for Space Exploration on the
  CADRE Lunar Technology Demonstration", IEEE Aerospace 2024, doi:10.1109/AERO58975.2024.10521425; Nayak et
  al., "Multi-Robot Exploration for the CADRE Mission", Autonomous Robots, 2025. Both are cited by [C2].

Missions, contracts, schedule
- [M1] NASA release 26-046, "NASA Provides Update on Moon Base Rovers, Landers, Missions", 26 May 2026.
  https://www.nasa.gov/news-release/nasa-provides-update-on-moon-base-rovers-landers-missions
- [M2] SpacePolicyOnline, "NASA Awards Initial Moon Base Rover and Lander Contracts", 26 May 2026.
  https://spacepolicyonline.com/news/nasa-awards-initial-moon-base-rover-and-lander-contracts/
- [M3] Brinkmann, "NASA expects one lunar launch this year, Moon Base manager says", Aerospace America (AIAA),
  15 Sep 2026. https://aerospaceamerica.aiaa.org/nasa-expects-one-lunar-launch-this-year-moon-base-manager-says/
- [M4] NASA release 26-095, "NASA Awards Moon Base Transportation, Technology, Science Projects", 7 Nov 2026.
  https://www.nasa.gov/news-release/nasa-awards-moon-base-transportation-technology-science-projects/
- [M5] NewSpaceEconomy, "NASA selects eight companies for CLPS 2 lunar deliveries", 9 Nov 2026.
  https://newspaceeconomy.ca/2026/11/09/nasa-selects-eight-companies-for-clps-2-lunar-deliveries/
- [M6] Wikipedia, "IM-3". https://en.wikipedia.org/wiki/IM-3
- [M7] Wikipedia, "Griffin Mission One" (last edited 9 Nov 2026). https://en.wikipedia.org/wiki/Griffin_Mission_One
- [M8] SpacePolicyOnline, "Three Americans and a European Named Crew of Artemis III", 9 Jun 2026.
  https://spacepolicyonline.com/news/three-americans-and-a-european-named-crew-of-artemis-iii/
- [M9] Spectrum News 13 (A. Leone), report of NASA's 27 Feb 2026 briefing that Artemis III will not land.
  https://mynews13.com/fl/orlando/space/2026/02/27/nasa-artemis-iii-no-moon-landing
- [M10] Scientific American, "China's Chang'e 7 moonshot will seek water ice at the lunar south pole",
  20 Aug 2026, updated 24 Aug 2026.
  https://www.scientificamerican.com/article/chinas-change-7-moonshot-will-seek-water-ice-at-the-lunar-south-pole/
- [M11] Wikipedia, "Chang'e 8". https://en.wikipedia.org/wiki/Chang%27e_8
- [M12] Wikipedia, "Chang'e 6". https://en.wikipedia.org/wiki/Chang%27e_6
- [M13] Wikipedia, "International Lunar Research Station".
  https://en.wikipedia.org/wiki/International_Lunar_Research_Station
- [M14] Wikipedia, "Chandrayaan-3". https://en.wikipedia.org/wiki/Chandrayaan-3
- [M15] Wikipedia, "Lunar Polar Exploration Mission". https://en.wikipedia.org/wiki/Lunar_Polar_Exploration_Mission
- [M16] ESA, "Argonaut: a first European lunar lander", 30 Jan 2025.
  https://www.esa.int/Science_Exploration/Human_and_Robotic_Exploration/Argonaut_a_first_European_lunar_lander
- [M17] ispace, "ispace Announces New 'ULTRA' Lunar Lander Integrating Japanese and U.S. Lander Models",
  press release, 27 Mar 2026. https://ispace-inc.com/wp-content/uploads/2026/03/20260327-ULTRA.pdf
- [M18] Spaceflight Now, "ispace's Resilience lander crash lands on the Moon", 6 Jun 2025.
  https://spaceflightnow.com/2025/06/06/ispaces-resilience-lander-crash-lands-on-the-moon/
- [M19] Spaceflight Now, "Intuitive Machines' IM-2 Moon mission ends with lander on its side", 7 Mar 2025,
  https://spaceflightnow.com/2025/03/07/intuitive-machines-im-2-mission-ends-with-lander-on-its-side-on-the-moon/
  and "Intuitive Machines lunar lander healthy, but apparently on its side", 7 Mar 2025,
  https://spaceflightnow.com/2025/03/07/intuitive-machines-lunar-lander-healthy-but-apparently-on-its-side/
- [M20] Spaceflight Now, "Firefly Aerospace's Blue Ghost Mission 1 concludes successful 14-day mission on the
  Moon", 18 Mar 2025.
  https://spaceflightnow.com/2025/03/18/firefly-aerospaces-blue-ghost-mission-1-concludes-successful-14-day-mission-on-the-moon/
- [M21] Astrobotic, "Astrobotic to Join Voyager Technologies", 2 Jun 2026.
  https://www.astrobotic.com/astrobotic-to-join-voyager-technologies-accelerating-americas-moon-base/
- [M22] SatNews, "NASA awards Intuitive Machines the Near Space Network contract", 17 Sep 2024.
  https://satnews.com/2024/09/17/nasa-awards-intuitive-machines-the-near-space-network-contract/
- [M23] Mission Control, company site (news items of 2026). https://missioncontrolspace.com/
- [M24] Wikipedia, "Yutu-2". https://en.wikipedia.org/wiki/Yutu-2
- [M25] Wikipedia, "Lunokhod 1". https://en.wikipedia.org/wiki/Lunokhod_1
- [M26] Fong (NASA Ames), "Volatiles Investigating Polar Exploration Rover", slides, 29 Apr 2026, NTRS
  20260002876. https://ntrs.nasa.gov/api/citations/20260002876/downloads/viper-2026-04-29_v2.pdf

Methods, autonomy, test facilities
- [L1] Buckman, Choi, How, "Partial Replanning for Decentralized Dynamic Task Allocation", arXiv 1806.04836
  (AIAA SciTech 2019). https://arxiv.org/abs/1806.04836
- [L2] Whitten, Choi, Johnson, How, "Decentralized Task Allocation with Coupled Constraints in Complex
  Missions", ACC 2011. https://skoge.folk.ntnu.no/prost/proceedings/acc11/data/papers/0813.pdf
- [L3] Choi, Brunet, How, "Consensus-Based Decentralized Auctions for Robust Task Allocation", IEEE T-RO
  25(4):912-926, 2009; abstract page opened, PDF blocked. https://dspace.mit.edu/handle/1721.1/52330
- [L4] van den Berg, Guy, Lin, Manocha, "Reciprocal n-body Collision Avoidance", ISRR 2009 (Springer 2011).
  https://gamma.cs.unc.edu/ORCA/publications/ORCA.pdf
- [L5] Litaker, Li, Beaton, Lewis, "Lunar Terrain Vehicle (LTV) Remote Teleoperation Studies Under Four Lunar
  Communication Latencies", NASA/TM-20240001217, 2024.
  https://ntrs.nasa.gov/api/citations/20240001217/downloads/LTV%20Teleops%20Study.pdf
- [L6] Olsen and Wood, "Fan-out: Measuring Human Control of Multiple Robots", CHI 2004, pp. 231-238.
  https://hci.rwth-aachen.de/materials/conferences/CHI2004/1p231.pdf
- [L7] IoT M2M Council, "How many self-driving vehicles can one person monitor?", 2 Sep 2025 (report of a
  Coventry University study).
  https://iotm2mcouncil.org/iot-library/news/connected-transportation-news/how-many-self-driving-vehicles-can-one-person-monitor/
- [L8] HumanProgress, item on Waymo's remote-assistance staffing, 3 Mar 2026 (quotes a newsletter).
  https://humanprogress.org/waymo-achieves-industry-leading-143-remote-operator-ratio/
- [L9] Richard, Kamohara, Uno, Santra, van der Meer, Olivares-Mendez, Yoshida, "OmniLRS: A Photorealistic
  Simulator for Lunar Robotics", arXiv 2309.08997. https://arxiv.org/abs/2309.08997
- [L10] NASA, "Top Prize Awarded in Lunar Autonomy Challenge to Virtually Map Moon's Surface", 15 May 2025.
  https://www.nasa.gov/directorates/stmd/top-prize-awarded-in-lunar-autonomy-challenge-to-virtually-map-moons-surface
- [L11] DLR, "Robotics team practises lunar exploration on Mount Etna", 1 Jul 2022.
  https://www.dlr.de/en/latest/news/2022/03/20220701_robotics-team-practises-lunar-exploration-on-mount-etna
- [L12] GMV, "Final field testing completed for CoRob-X", 28 Feb 2023.
  https://www.gmv.com/en-es/communication/news/final-field-testing-completed-corob-x
- [L13] ESA Business in Space Growth Network, page on the second Space Resources Challenge (2026).
  https://bsgn.esa.int/?p=102564
- [L14] LUNA Analog Facility (DLR and ESA), "Working and testing in LUNA".
  https://luna-analog-facility.de/en/for-users/working-and-testing-in-luna/
- [L15] NASA SSERVI, Lunar Lab and Regolith Testbed. https://sservi.nasa.gov/testbed/
- [L16] NASA Glenn, "NASA Tests Lunar Communications Network in Lava Field", 8 Dec 2022.
  https://www.nasa.gov/centers-and-facilities/glenn/nasa-tests-lunar-communications-network-in-lava-field/
- [L17] Johns Hopkins APL, press release on LOGIC, 11 Oct 2023.
  https://www.jhuapl.edu/news/news-releases/231011b-lunar-technology-development
- [L18] Space ROS site and demos repository. https://space.ros.org/ ; https://github.com/space-ros/demos
- [L19] Wikipedia, "Haughton-Mars Project". https://en.wikipedia.org/wiki/Haughton%E2%80%93Mars_Project

Market
- [K1] SpaceQ, "PwC report: lunar economy projected to generate up to US$127 billion by 2050", 15 May 2026.
  https://spaceq.ca/pwc-report-lunar-economy-projected-to-generate-up-to-us127-billion-by-2050/
- [K2] ESA Space Economy, "PwC's Lunar market assessment: market trends and challenges in the development of
  a lunar economy", Nov 2021.
  https://space-economy.esa.int/article/119/pwcs-lunar-market-assessment-market-trends-and-challenges-in-the-development-of-a-lunar-economy
- [K3] Fortune, article on Deloitte's "Building the Lunar Economy", 26 Aug 2026.
  https://fortune.com/2026/08/26/spacex-moon-musk-lunar-economy-566-billion-deloitte/
- [K4] Colvin, Crane, Lindbergh, Lal, "Demand Drivers of the Lunar and Cislunar Economy", IDA Document
  D-13219, April 2020 (executive summary read).
  https://www.ida.org/-/media/feature/publications/d/de/demand-drivers-of-the-lunar-and-cislunar-economy/d-13219.pdf

Repository sources
- [P1], [P2], [P3]: `paper/p1`, `paper/p2`, `paper/p3` (`paper.html`, `values.json`), built 30 Oct 2026.
- [MOA]: `research_notes/Lunar ATC/multi_owner_allocation.md` (27 Oct 2026).
- [TS]: `research_notes/Lunar ATC/traffic_and_safety.md` (27 Oct 2026).

Could not be opened, and what rests on them
- MIT DSpace PDF of Choi, Brunet, How 2009 (HTTP 429) and Brunet's thesis on CORE (403): the text of the 50 %
  proof.
- The Engineer and DLR pages on LUNA's size (403): 700 m2, 900 t.
- GovConWire (403): the 4.6 billion USD LTV Services maximum and the 4.2 billion USD CLPS notice of April 2026
  (the latter is confirmed by [M4]).
- LSIC site (time-out): membership terms and the current list of focus groups.
- NSSDCA Lunokhod page (error): Lunokhod's driving crew, speed and TV frame rate.
- Space.com on Artemis II (page body not returned): launch and splashdown dates.
- Not searched to a primary source: Chandrayaan-4 date, South Korea's lander, LunaGrid-Lite and VSAT status,
  LuSTR construction projects, JAXA and Kajima, Pony.ai's ratio, Swamp Works, JSC Rock Yard, Roverscape,
  Iceland campaigns, A-SMGCS, the MATRICS bench, DUST's release terms. Each is marked UNVERIFIED in the text.
