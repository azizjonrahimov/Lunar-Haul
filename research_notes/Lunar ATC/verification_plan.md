# Verification and validation plan for Lunar ATC: from 13 checks to about 70 (current to 2026-10-27)

This plan proposes 60 new checks for the simulator's existing engine and for the Lunar ATC components still to be built:

- decentralized learned bidding;
- cross-owner team lifts;
- the surface radio network;
- the safety layer;
- the traffic model;
- the energy and battery model;
- the 3D replay.

Each check has an analytic or independent reference, a pass tolerance and a source. The plan changes no code. It is a specification for `lunarsim/vv.py` and the site's Verification page.

## 1. What exists today

### 1.1 The thirteen checks

`lunarsim/vv.py`, `run_all_checks()`, tested in `tests/test_verification.py` and shown on the site as "Simulation engine (13 checks, as in the paper)" in `site/src/verify/main.js`.

| # | Check | Reference | Tolerance | Sargent technique | Status in v2 paper |
|---|---|---|---|---|---|
| 1 | Travel time on a flat two-edge path (PAD_A–DEPOT–BASE) | distance / speed | 1e-9 rel | analytic identity (verification) | pass |
| 2 | Steep-edge travel time doubles (SCI_1–PSR) | distance / (0.5 × speed) | 1e-9 rel | analytic identity | pass |
| 3–6 | Teleoperated speed at 0, 4, 6, 8 s RTT | JSC LTV trial averages 3.24, 2.56, 2.03, 1.76 km/h (Litaker et al., TM-20240001217) | 1% rel | historical data | pass |
| 7 | Dark share of time | night_fraction = 0.15, sampled over 10 cycles | 0.5% rel | parameter identity | pass |
| 8–9 | Mass conservation, under the marketplace and under pooled greedy | ready = delivered + stranded + backlog | 1e-9 rel | conservation law | pass |
| 10 | Items above team capacity (2 × 1,500 kg) never delivered | 0 items, six large landings | exact | extreme condition | pass |
| 11 | Same landed manifest for four mechanisms (seed 11) | identical manifest | exact | internal validity (CRN) | pass |
| 12 | Annual fleet amortisation | Σ unit cost / life | 1e-9 rel | identity | pass |
| 13 | M/G/1 mean wait in queue | Pollaczek–Khinchine W_q = λE[S²] / (2(1 − ρ)) | 5% rel | analytic queueing model | pass at 0.5% over about 18,000 items |

The v2 paper reports a maximum relative error of 0.5%, with all but the M/G/1 check at or below 0.03%.

### 1.2 Checks added since v2

- **Phase 4** (`run_phase4_checks()`, `tests/test_verification_phase4.py`): 8 rows.
  - Catalogue values equal the engine's constants.
  - The scene package reproduces the trace's trips, landings and delivered kg (3 rows).
  - A stored descent trajectory replays to < 1e-6 m.
  - Earth elevation and azimuth at BASE agree with JPL Horizons over January 2028 to ≤ 0.01° (2 rows).
  - Earth-link mode "always" reproduces the baseline canonical MD5.
- **v3 paper:**
  - an identity check that the v2 columns are unchanged;
  - sixteen engine tests of the terrain, lander and plume models;
  - model-level checks;
  - Python–browser parity.

  The browser Verification page runs 37 checks in all.

### 1.3 Gaps a referee will find

1. **Four of the thirteen are calibration, not validation.** The teleoperation model interpolates the JSC table, so reproducing that table verifies the interpolation. It does not validate the model (Kleijnen 1995). The night-fraction check confirms that a parameter is honoured. Label both kinds accordingly.
2. **One queueing reference, at one load, with one server.** There is nothing for multiple servers, priority classes, Little's law, overload, or the sensitivity of wait to load.
3. **No metamorphic tests.** Nothing checks that relabelling, rescaling or permuting inputs changes outputs only as theory says it should (Chen et al., ACM Computing Surveys 51(1):4, 2018).
4. **No trace-level assertions.** Nothing checks clock order, state-transition order, or that no vehicle is in two jobs at once, across whole runs.
5. **No input-distribution tests.** Nothing checks that the generated landings and masses follow the specified distributions.
6. **Nothing for the new components.** The auction, radio mesh, safety layer, traffic, battery and learned policy have no checks yet. Each makes claims that have closed-form or exhaustive references.

## 2. Framework

### 2.1 Classes of check

Every new check carries three labels:

1. **Sargent technique** (Sargent 2013): analytic, degenerate, extreme condition, event validity, face validity, historical data, internal validity, parameter variability, traces, comparison to other models.
2. **NASA-STD-7009A credibility factor** it supports: code verification, solution verification, conceptual validation, referent validation, input pedigree, results uncertainty or results robustness. Confirm the factor list against NTRS 20160011121.
3. **Kind:**
   - V (verification: the code does what the model says);
   - Val (validation against something outside the model);
   - Cal (calibration reproduction).

### 2.2 Tolerance policy

1. **Deterministic identities** (conservation, exact formulas evaluated by the engine on crafted inputs): 1e-9 relative, or exact for counts and booleans.
2. **Float32 paths** (browser, ONNX, WebGL): state the tolerance from the precision. Float32 has a unit roundoff of about 6e-8, which is about 1e-3 m at 10 km.
3. **Stochastic checks against analytic references.** Choose the sample size n so that the 99% batch-means half-width is at most one-third of the tolerance. The check passes when |relative error| ≤ tolerance. With that margin, a correct implementation fails only if the estimate is more than about 7.7 standard errors from the reference, so no multiplicity correction is needed across the family. Also report whether the 99% interval covers the reference. A tolerance met with the interval excluding the reference is a "bias flag", recorded but not a failure. Use batch means (10–30 batches, Schmeiser 1982, Operations Research 30(3):556–568) because waits within a run are autocorrelated.
4. **Goodness-of-fit tests** (input distributions): α = 0.01 per test, with Holm correction across the family.
5. **Zero-event safety checks.** Pass means zero events. Also report the exposure and the 95% upper bound: 1 − 0.05^(1/n), about 3/n (Hanley and Lippman-Hand 1983). The independence unit is the run unless a finer unit is justified.
6. **Approximations** (formulas that are themselves approximate, such as Kingman or Allen–Cunneen): do not use them as pass criteria. Use exact references (Erlang C, Franx's M/D/c, Cobham) and report the approximations only for interest.

### 2.3 Budget

The checks share a machine with 8 GB of RAM and two other sessions. Rules for every check:

- one process;
- under 300 MB;
- under 60 s, except the long-horizon queueing checks, which may take up to 3 min each;
- the whole new suite under 20 min.

Tests that need a model change that the production engine does not have (exponential service, Markov routing) use a test-only hook, named as such and excluded from production configurations.

### 2.4 Priorities and papers

- **P1:** needed before any submission.
- **P2:** needed before the paper whose claim it supports.
- **P3:** strengthens the case.

Paper tags:
- **C:** coordination paper (decentralized learned bidding, team lifts).
- **S:** safety and Earth-independent operation paper.
- **O:** operations paper.

---

## 3. Proposed checks

Notation:
- λ: arrival rate.
- S: service time.
- ρ: utilisation.
- c: number of servers.
- τ: deterministic traversal time.
- R: lunar mean radius, 1737.4 km (Archinal et al. 2018, Celestial Mechanics and Dynamical Astronomy 130:22).
- g: lunar surface gravity, 1.62 m/s².
- μ_Moon: lunar gravitational parameter, 4902.80 km³/s² (GRAIL gravity models; Konopliv et al. 2013, JGR Planets 118:1415–1434).

### 3.1 Dispatch engine (D1–D11)

| ID | What it checks (technique, kind) | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| D1 | Little's law, sample-path form, on the queue of waiting cargo in any run (traces, V) | ∫₀ᵀ N_q(t) dt = Σᵢ [min(pickupᵢ, T) − max(readyᵢ, 0)], computed from the trace. The asymptotic form L_q = λ W_q is also reported. | sample-path: 1e-9 rel; asymptotic form: 2% in a 20-year M/G/1 run | Little, Operations Research 9(3):383–387, 1961; Little, Operations Research 59(3):536–549, 2011 | P1 / all |
| D2 | P-K wait and utilisation across load: the existing M/G/1 check repeated at ρ = 0.3, 0.6, 0.85, plus a one-pad variant with deterministic service (M/D/1) (analytic, V) | W_q = λE[S²]/(2(1 − ρ)); M/D/1: W_q = ρS/(2(1 − ρ)); busy fraction = λE[S] | W_q: 3%, 5%, 10% at the three loads; busy fraction: 1% | Pollaczek 1930; Khinchine 1932; Kleinrock, *Queueing Systems* Vol. 1, Wiley, 1975 | P1 / O |
| D3 | Multiple vehicles, two sub-cases (analytic, V). (a) c = 2, 3, 4 vehicles with exponential service through a test hook. (b) Real deterministic service with one pad. | (a) Erlang C: P_wait = [aᶜ/c! · c/(c − a)] / [Σₖ₌₀ᶜ⁻¹ aᵏ/k! + aᶜ/c! · c/(c − a)], with a = λE[S], and W_q = P_wait / (cμ − λ). (b) Exact M/D/c mean wait. | 5% | Erlang 1917; Franx, Operations Research Letters 29(5):221–229, 2001; Tijms, *A First Course in Stochastic Models*, Wiley, 2003 | P1 / O, C |
| D4 | Priority classes: urgent items ahead of routine, non-preemptive, one vehicle (analytic, V) | Cobham: W_q,k = W₀ / ((1 − σₖ₋₁)(1 − σₖ)), with W₀ = Σᵢ λᵢE[Sᵢ²]/2 and σₖ = Σᵢ≤ₖ ρᵢ | 5% per class | Cobham, Operations Research 2(1):70–76, 1954; Kleinrock Vol. 2, 1976 | P2 / O. Valid only if dispatch is strict-priority FCFS within class; if not, record the rule. |
| D5 | Extreme conditions, three cases (extreme condition, V): (a) zero landings, (b) zero vehicles, (c) overload ρ = 1.5 | (a) delivered = 0, km = 0, energy = 0, fleet cost unchanged; (b) backlog = ready mass, no crash; (c) backlog grows at λ − 1/E[S] items per hour | (a, b) exact; (c) 2% on the fitted slope | Sargent 2013 | P1 / all |
| D6 | One owner: in-house dispatch equals pooled greedy (degenerate, V) | identical trace (MD5) | exact; any difference must be explained in the text | Sargent 2013 | P1 / O, C |
| D7 | Time-scale invariance: multiply every duration (speeds⁻¹, load and unload times, landing gaps, night cycle, horizon) by k = 2 (metamorphic, V) | all delays × k; counts and kg unchanged | 1e-9 rel. A failure locates hard-coded time constants, which is itself a finding. | Chen et al. 2018; Segura et al., IEEE TSE 42(9):805–824, 2016 | P2 / all |
| D8 | Trace invariants over every run of every suite (traces, assertion checking, V) | clock non-decreasing; t_ready ≤ t_picked ≤ t_delivered; no vehicle in two overlapping jobs; team members share the job interval; carried mass ≤ capacity (team sum); no event scheduled in the past | zero violations | Balci 1998 (assertion checking); Sargent 2013 (traces) | P1 / all |
| D9 | Central assignment is optimal (comparison with another model, V) | brute force over all n! assignments on 1,000 random cost matrices, n ≤ 8 | equal cost to 1e-9 | Kuhn, Naval Research Logistics Quarterly 2:83–97, 1955; Munkres, J. SIAM 5(1):32–38, 1957; `lunarsim/assign.py` | P1 / C |
| D10 | CRN extended to every new mechanism, and CRN effectiveness (internal validity, V) | identical landed manifest for each ATC mechanism; correlation of paired outputs > 0; variance-reduction factor Var(X − Y)/(Var X + Var Y) < 1 | manifest exact; correlation's 95% CI excludes 0 | Law 2015, ch. 11; extends existing check 11 | P1 / all |
| D11 | Input distributions: landing counts per year Poisson with the scenario rate; item masses per class follow the specified distributions; destination shares (historical data / input pedigree, Val) | χ² on yearly counts; Kolmogorov–Smirnov on gaps (exponential) and masses; χ² on destination shares | p ≥ 0.01 after Holm across the family | Law 2015, ch. 6 | P2 / O |

### 3.2 Decentralized auction and team lifts (A1–A9)

| ID | What it checks | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| A1 | Single-item ε-auction against the optimum (comparison with another model, V) | total cost J_auction − J* ≤ nε, with J* from the Hungarian method (D9); with integer costs and ε < 1/n, J_auction = J* | bound holds on 1,000 random instances; zero exceedances | Bertsekas, Annals of OR 14:105–123, 1988 | P1 / C |
| A2 | Decentralized equals centralized when communication is perfect: zero latency, full connectivity, no loss, same bids (degenerate, V) | the decentralized protocol's awards equal the centralized implementation of the same auction | identical award list and identical trace (MD5) on 30 seeds of the reference scenarios | design identity | P1 / C |
| A3 | CBBA convergence and agreement (analytic, V) | under synchronous rounds, a static connected network and DMG scores: rounds ≤ N_t · D (N_t tasks, D network diameter); at convergence each task has exactly one winner and all agents hold identical winner lists | zero bound exceedances and zero conflicts on 1,000 random instances (2–12 agents, 2–30 tasks, random geometric graphs) | Choi, Brunet and How, IEEE T-RO 25(4):912–926, 2009 | P1 / C |
| A4 | Optimality ratio on small instances (comparison with another model, V) | CBBA score ≥ 0.5 × optimum (exhaustive search or MILP) under DMG; report the distribution of the ratio | minimum ratio ≥ 0.5; any instance below is saved and reported | Choi et al. 2009. A 2025 paper (doi 10.3233/FAIA251222) reports that the 50% guarantee can fail even with DMG and proposes GCBBA; treat a failure as a finding. | P2 / C |
| A5 | The learned scoring function satisfies diminishing marginal gain (property test, V). If it does not, A3 and A4's guarantees do not apply, and the paper must say so. | for random bundles b ⊂ b′ and task j ∉ b′: Δ(j \| b) ≥ Δ(j \| b′) | zero violations in 10⁵ samples, or report the rate and use a DMG-enforcing wrapper (bid warping) | Choi et al. 2009; Johnson, Ponda, Choi and How, "Asynchronous decentralized task allocation for dynamic environments", AIAA Infotech@Aerospace 2011 | P1 / C |
| A6 | Metamorphic invariances (metamorphic, V). (a) Relabel agents and owners (permute IDs). (b) Multiply all scores by k > 0. (c) Add a constant to every bid on one task. (d) One agent: awards equal that agent's greedy sequence. (e) One task: winner = argmax score. | (a) same total score, and the same assignment up to the permutation when ties break on a stable key; (b, c) same assignment, the assignment problem's optimum being invariant to these transforms; (d, e) exact | exact | Burkard, Dell'Amico and Martello, *Assignment Problems*, SIAM, 2009; Chen et al. 2018 | P1 / C |
| A7 | Partition and merge of the radio network (event validity, V) | while partitioned: no task held by two agents in the same component; after the merge: conflicts resolved within D_merged rounds (synchronous) and all duplicates released | zero intra-component duplicates; resolution within the bound | Johnson et al. 2011 (ACBBA); Choi et al. 2009 | P1 / C, S |
| A8 | Payments and incentives (analytic, V). (a) Transfers between owners sum to zero (or to the stated fee). (b) If the mechanism is VCG or second-price, no unilateral misreport (bids scaled by 0.5–2.0 on a grid) raises the deviator's utility. | (a) Σ payments = 0; (b) gain ≤ 0 | (a) 1e-9; (b) ≤ 1e-9 for exact VCG; for a heuristic mechanism, report the maximum gain without a pass threshold | Vickrey, J. Finance 16(1):8–37, 1961; Clarke, Public Choice 11:17–33, 1971; Groves, Econometrica 41(4):617–631, 1973 | P2 / C |
| A9 | Cross-owner team lift feasibility (traces, V) | a team forms only when Σ capacity ≥ item mass; members reach the pickup within the synchronisation tolerance; no member is released before drop-off; the item's owner pays the agreed split, which sums to the price | zero violations; synchronisation ≤ the model's stated tolerance (e.g. 60 s) | Gerkey and Matarić, IJRR 23(9):939–954, 2004 (single-task, multi-robot tasks) | P1 / C |

### 3.3 Radio and visibility (R1–R8)

| ID | What it checks | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| R1 | Smooth-sphere horizon, with the line-of-sight routine run on a synthetic bald-Moon DEM (analytic, V) | single antenna: d_h = √(2Rh + h²). A 2.5 m antenna gives 2,947 m; a 10 m mast gives 5,895 m. Two antennas are in sight iff d ≤ √(2Rh₁) + √(2Rh₂); 2.5 m to 10 m gives 8,842 m. | classification exact for points more than one grid cell (5 m) from the boundary; transition located within one cell | spherical geometry; Archinal et al. 2018 for R | P1 / S, C |
| R2 | Reciprocity: A sees B iff B sees A, at equal antenna heights, over all node pairs and route points (metamorphic, V) | symmetric visibility | zero asymmetries | geometry | P1 / S |
| R3 | Single knife-edge obstruction: a synthetic ridge of known height between two antennas (analytic, V) | blocked iff the ridge top is above the chord. Diffraction loss J(ν) = 6.9 + 20 log₁₀(√((ν − 0.1)² + 1) + ν − 0.1) dB for ν > −0.78, with ν = h√(2(d₁ + d₂)/(λd₁d₂)). First Fresnel radius r₁ = √(λd₁d₂/(d₁ + d₂)). | blocking exact; J(ν) within 0.5 dB if the model computes diffraction loss | ITU-R P.526 (single knife-edge) | P2 / S |
| R4 | Link budget arithmetic and capacity bound (analytic, V) | FSPL = 20 log₁₀(4πd/λ) dB; Eb/N0 = EIRP − L + G/T − k − 10 log₁₀ R_b, with k = −228.6 dBW/K/Hz; no link carries more than C = B log₂(1 + SNR) | 1e-9 dB on the arithmetic; zero capacity violations | Friis, Proc. IRE 34(5):254–256, 1946; Shannon, BSTJ 27, 1948 | P2 / S, C |
| R5 | Earth geometry against JPL Horizons at a second site and in a second month with different libration (for example the PSR site, July 2029); one-way light time (comparison with another model, Val) | elevation and azimuth from Horizons; light time = range / c (range 356,000–407,000 km gives 1.19–1.36 s); Earth's centre elevation stays within (90° − \|φ\|) ± (6.7° latitude libration + 0.26° topocentric parallax) at site latitude φ | elevation and azimuth ≤ 0.01° (as B-40); light time ≤ 1 ms; extremes inside the band ± 0.1° | JPL Horizons API; the existing check `check_ephemeris_horizons()`; `research_notes/Lunar communications and visibility/earth_visibility_prior_art.md` | P1 / S, O |
| R6 | Relay orbit (analytic and comparison, V) | Kepler period T = 2π√(a³/μ_Moon): a = 6,142 km gives 12.0 h. Relay-visible fraction from the model against a SPICE-propagated orbit for one month. | period 1e-6 rel; visible fraction within 1 percentage point | Kepler; SPICE (NAIF) | P2 / O, S |
| R7 | Network graph and broadcast latency (comparison with another model, V) | network diameter from BFS equals Floyd–Warshall; component count equals union-find; with all links up and no loss, a broadcast reaches every node within D × (per-hop latency + processing time) | exact; zero latency-bound violations | standard graph algorithms; D feeds A3 | P1 / C, S |
| R8 | Face validity against published coverage (face validity, Val) | DTE fraction at the Connecting Ridge site against published values for the same criterion and antenna height (Bryant et al. ~51–58%; NASA/LCRNS 17–43% yearly across candidate sites); surface relay range against NASA Glenn's lunar surface relay ("out to 10 km, depending on local terrain", 10 m boom), compared with R1's 8.8 km smooth-sphere limit to a 2.5 m rover | within ±5 percentage points for the same criterion, or the difference explained | the repo's prior-art note; Scardelletti et al., ICSSC 2023 | P2 / O, S |

### 3.4 Safety layer (S1–S7)

| ID | What it checks | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| S1 | Zero separation violations, evaluated in continuous time, over every run (traces, V). Between events, the closest approach of two piecewise-linear trajectories is computed analytically, not sampled. | for each segment pair: t* = clip(−(Δp · Δv)/\|Δv\|², 0, Δt) and d_min = \|Δp + Δv t*\|; require d_min ≥ d_safe. Report the exposure (encounters within 50 m, vehicle-pair-hours, runs) and the 95% upper bound 1 − 0.05^(1/n). With n = 1,000 runs the bound is 2.99 × 10⁻³ per run. | zero violations | Hanley and Lippman-Hand 1983; closest-point-of-approach geometry | P1 / S |
| S2 | Fault injection (mutation testing): inject unsafe proposals into the layer's input. Examples: conflicting route reservations, bids that overload a vehicle, team lifts below the required capacity, entry into a landing keep-out, a dispatch that leaves the battery below reserve. | 100% of injected violations rejected | N ≥ 1,000 injections per class; zero misses (miss-rate bound 3/N) | DeMillo, Lipton and Sayward, IEEE Computer 11(4):34–41, 1978; Jia and Harman, IEEE TSE 37(5):649–678, 2011 | P1 / S |
| S3 | Minimal interference: a proposal that is already safe passes unchanged (V) | output = input for safe proposals; report the intervention rate | 100% identity on safe proposals | Alshiekh et al., "Safe reinforcement learning via shielding", AAAI 2018; Ames et al., "Control barrier functions: theory and applications", ECC 2019 | P1 / S |
| S4 | One-step forward invariance (formal, V): from every safe state in an exhaustive grid of small instances (2–4 vehicles, 1–2 lanes, discretised positions and speeds), the layer's chosen action leads to a safe state. Where feasible, model-check the rule set (TLA+ or UPPAAL). | inductive invariant: Safe(x) ∧ a = shield(x, u) ⇒ Safe(f(x, a)) | zero counterexamples; the model checker reports the property holds for the bounded instance | Ames et al. 2019; Lamport, *Specifying Systems*, 2002; Behrmann et al., UPPAAL tutorial, 2004 | P2 / S |
| S5 | Deadlock freedom and liveness (traces, V) | the wait-for graph is acyclic at every event; every reservation request is granted within T_max (stated), or the maximum wait is reported | zero cycles; zero requests above T_max | Coffman, Elphick and Shoshani, ACM Computing Surveys 3(2):67–78, 1971 | P1 / S |
| S6 | Independence from Earth (metamorphic, V). The same proposals are run with Earth-link modes "never" and "always". | the layer's decisions are identical (its inputs exclude Earth state); in ATC mode, actions awaiting Earth approval = 0 | exact | design identity | P1 / S |
| S7 | Landing keep-out along the whole path (traces, V). This extends v3's "no job starts or ends at a pad inside a window" to every point of every route. | no vehicle position (continuous-time, as in S1) lies within the keep-out radius during a landing window | zero violations | v3 engine tests | P1 / S, O |

### 3.5 Traffic model (T1–T5)

| ID | What it checks | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| T1 | Single-lane segment, single occupancy in either direction, Poisson arrivals, deterministic traversal τ (analytic, V) | M/D/1: W_q = λτ²/(2(1 − λτ)). For example τ = 0.1 h and λ = 6 per h give ρ = 0.6 and W_q = 0.075 h. Run ρ = 0.3, 0.6, 0.85 with ≥ 20,000 traversals. | 3%, 5%, 10% | Kleinrock 1975 | P1 / S, O |
| T2 | Deterministic inputs (analytic, V). (a) n vehicles arrive at once: mean wait (n − 1)τ/2, total n(n − 1)τ/2. (b) Strictly alternating directions with a clearance s: throughput 1/(τ + s). | exact formulas | 1e-9 rel | elementary queueing | P1 / S |
| T3 | Saturation capacity of a following lane (analytic, V) | q_max = v / (L_veh + d_min) vehicles per hour at the stated speed v, vehicle length and gap; a saturated run matches it | 1% | Daganzo, *Fundamentals of Transportation and Traffic Operations*, Pergamon, 1997 | P2 / S |
| T4 | Network of single-lane segments, Poisson external arrivals, exponential traversal and Markov routing through a test hook (analytic, V) | Jackson product form: segment i has mean occupancy ρᵢ/(1 − ρᵢ), with ρᵢ from the traffic equations λᵢ = γᵢ + Σⱼ λⱼ pⱼᵢ | 5% per segment | Jackson, Operations Research 5(4):518–521, 1957 | P3 / S |
| T5 | Free-flow travel and node conservation (traces, V) | one vehicle on the lane network: time = Σ Lᵢ/vᵢ; at every node and event, vehicles in = vehicles out + vehicles present; no two reservations of one segment overlap in time | 1e-9 rel; zero violations | extends existing checks 1–2 | P1 / S |

### 3.6 Energy and battery (E1–E5)

| ID | What it checks | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| E1 | Energy identity (V) | summary `energy_kwh` = Σ over legs of (Wh/km × km × factors), recomputed from the trace | 1e-9 rel | conservation | P1 / O |
| E2 | Battery balance and bounds, per vehicle at every event (traces, V) | SOC_end = SOC_0 + charged − traction − hotel − heater; 0 ≤ SOC ≤ capacity; no dispatched job leaves SOC below the stated reserve | balance 1e-9 rel; zero bound violations | conservation | P1 / O, S |
| E3 | Traction physics by hand calculation on synthetic legs (analytic, V) | flat: E = C_rr m g d / (1 − s), with C_rr = 0.178. 700 kg at slip 0.04 gives 58.4 Wh/km, matching the Apollo LRV's measured 57–60 Wh/km; 1,600 kg gives 133.5 Wh/km (v3 quotes 134). Grade: add m g Δz / η with η = 0.7; downhill not recovered. | 0.5% against the formula; flat 700 kg case inside the LRV's measured 57–60 Wh/km | v3 Section 3.4 energy model; Apollo LRV data as cited in v3 [41] | P1 / O |
| E4 | Charging and solar input (analytic, V) | charge time Δt = ΔE / (P_charge η_charge); solar power P = η A S cos i, with S = 1361 W/m², integrated over the illumination file for one lunar day | 1e-9 on the charge time; 1% on the daily energy | Kopp and Lean, GRL 38:L01706, 2011 | P2 / O |
| E5 | Extremes (extreme condition, V). (a) A vehicle survives a dark period T iff reserve ≥ P_survival × T; the engine strands exactly those that fail. (b) No job longer than the range B/e is accepted. (c) Infinite battery and zero charge time reproduce the energy-free baseline digest (see X1). | exact sets and counts | exact | Sargent 2013 | P1 / O |

### 3.7 Learned bidding policy (L1–L6)

| ID | What it checks | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| L1 | Agreement with the teacher on held-out cases (comparison with another model, Val). Held-out cases are ≥ 2,000 decision points from seeds and scenarios disjoint from training. Disjointness is checked by set intersection of seed and scenario hashes. | top-1 award agreement, and the mean absolute bid error relative to the teacher | agreement at or above the preregistered threshold (e.g. 95%), judged on the Wilson 95% lower bound; seed sets disjoint (exact) | Ross, Gordon and Bagnell, "DAgger", AISTATS 2011; Wilson, JASA 22:209–212, 1927 | P1 / C |
| L2 | Outcome equivalence with the teacher: paired across ≥ 30 CRN seeds on the primary metric (internal validity, Val) | TOST with a preregistered margin (e.g. ±5% of the teacher mean) | both one-sided tests reject at α = 0.05 | Schuirmann 1987; Lakens 2017 | P1 / C |
| L3 | Calibration of predicted cost or ETA bids against realised values (Val) | regression of realised on predicted: slope and intercept | slope in [0.95, 1.05] and intercept CI covering 0, or report miscalibration | standard calibration practice | P2 / C |
| L4 | Export parity (comparison with another implementation, V): PyTorch against ONNX, and ONNX in Python against onnxruntime-web in the browser, on 1,000 fixed inputs | max absolute output difference | ≤ 1e-5 (PyTorch–ONNX, float32); ≤ 1e-4 (Python–browser) | the existing pattern in `lunarsim/rover/onnx_driver.py` and the policy check vectors | P1 / C |
| L5 | Monotonicity (metamorphic, Val): holding all else fixed, the cost bid does not decrease with distance to pickup or with item mass, and does not increase with state of charge | sign of the finite difference on probe pairs | violations ≤ 1% of 10⁴ probes; all violations listed | Chen et al. 2018 | P2 / C |
| L6 | Teacher substitution (degenerate, V): replacing the learned bids with the teacher's in the decentralized engine reproduces the teacher run | identical trace (MD5) | exact | design identity; separates policy error from protocol error | P1 / C |

Out-of-distribution behaviour (fleet sizes, owner counts or demand outside the training range) is a reported result, not a pass/fail check. The paper reports the performance relative to the teacher. It also reports, from S1, that the safety layer still gives zero violations.

### 3.8 3D scene and replay (V1–V4)

| ID | What it checks | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| V1 | Trace replay equals engine output, extended to the ATC fields: trips, landings, delivered kg, bids, award messages, safety interventions, team lifts and link-state changes. Seeking directly to time t gives the same state as playing from 0 to t, at 1× and 10× speed. | counts and sums from the engine's trace | exact; state identical | extends B-31 (`check_scene_reproduces_trace`) | P1 / all |
| V2 | Vehicle positions at event times (V) | scene position equals the engine's node or route position at each event | ≤ 0.05 m (float32 at 10 km is about 1e-3 m; margin for transforms) | engine trace | P1 / all |
| V3 | Between events: on route and on the ground (V) | the position at time t equals the route arclength at the engine's speed profile; distance to the route polyline ≤ 0.5 m; wheel height above the DEM within [−0.05, +0.3] m on every sampled frame | as stated; zero violations | LOLA tile; `data/driving/routes-v1.json` | P2 / all |
| V4 | Sun, Earth and link lines (V) | the Sun and Earth directions drawn in the scene equal the SPICE tracks at the same time; the link lines drawn equal the trace's link state on sampled frames | ≤ 0.1° on directions; zero mismatches on links | `earth_track-v1.json.gz`; illumination data | P2 / S, O |

### 3.9 Cross-cutting (X1–X5)

| ID | What it checks | Reference or formula | Pass tolerance | Source | Pri / paper |
|---|---|---|---|---|---|
| X1 | Regression identity (V): with every ATC feature off (and the infinite battery of E5c), the engine reproduces the v2 and v3 canonical digests | `BASELINE_V2_CANONICAL_MD5` and the v3 digest | exact | B-41 (`check_comms_always_baseline`) | P1 / all |
| X2 | Python against browser engine on the ATC cells (comparison with another implementation, V) | paired equivalence on ≥ 24 metric cells | TOST within the cell's preregistered margin, or within the 95% CI as in v2. Divergences documented as in v3 Table B4. | v2 and v3 parity method | P2 / all |
| X3 | Replication adequacy and warm-up (results uncertainty) | for each headline cell, 95% half-width ≤ γ × mean (γ preregistered, e.g. 5%); MSER-5 truncation point ≤ 5% of the horizon, or the headline unchanged by more than half its CI when the warm-up is removed | as stated | Law 2015, ch. 9; White, Simulation 69(6):323–334, 1997 (MSER); Hoad, Robinson and Davies, JORS 61(9):1389–1403, 2010 | P1 / all |
| X4 | Sensitivity screening (parameter variability, results robustness): Morris elementary effects on the ~20 Assumed parameters, with r = 10 trajectories (about 210 runs, a few minutes) | μ* and σ of the elementary effects per parameter | not pass/fail. Any Assumed parameter in the top five by μ* for a headline metric gets a dedicated sweep in the paper. | Morris, Technometrics 33(2):161–174, 1991; Campolongo, Cariboni and Saltelli, Environmental Modelling & Software 22(10):1509–1518, 2007 | P1 / all |
| X5 | Face validity and Turing-style review (face validity, Val): two or more reviewers outside the team with lunar surface operations or multi-robot experience watch replays of chosen traces and judge whether behaviours are plausible; optionally, they try to tell engine traces from hand-made operations plans | written findings, each closed or carried to Limitations | review held and recorded | Sargent 2013 (face validity, Turing tests) | P2 / all |

Total: 11 + 9 + 8 + 7 + 5 + 5 + 6 + 4 + 5 = **60 checks**. Counting sub-cases and loads as separate rows, as the current page does for the four teleoperation speeds, the Verification page would show roughly 110 rows.

---

## 4. Order of work

1. **First tranche (P1, current engine only):** D1, D2, D5, D6, D8, D9, D10, E1, E2, E3, E5, X1, X3, X4. These need no new model code. Most reuse runs the test suite already makes. Together they answer gaps 2–5 of Section 1.3. Estimated run time under 10 minutes in total.
2. **Second tranche (with the ATC code):** A1–A3, A5, A6, A7, A9; R1, R2, R5, R7; S1–S3, S5–S7; T1, T2, T5; L1, L2, L4, L6; V1, V2. Write each test alongside the component it checks. A component is not done until its checks pass.
3. **Third tranche (before the relevant paper):** D3, D4, D7, D11, A4, A8, R3, R4, R6, R8, S4, T3, E4, L3, L5, V3, V4, X2, X5, then T4.

## 5. How to report it in the papers

1. **Section 4 of each paper:** a summary table by component (checks, passed, maximum error), the two or three hardest checks in prose, and the calibration/validation distinction stated plainly.
2. **Appendix:** the full table (check, technique, reference, tolerance, n, result).
3. **Safety paper:** the exposure, the zero count and the upper bound in the Abstract or the Introduction. Formal checks (S4, A3) belong beside the theorems they test.
4. **Credibility statement:** one paragraph in each paper. It says which claims rest on which factor (code verification, referent validation, and so on). It names what is not validated because no referent exists, for example decentralized lunar operations as a whole, and says what evidence would change that.

## Sources

Main references (others are cited inline in the tables):
- R. G. Sargent, "Verification and validation of simulation models", Journal of Simulation 7(1):12–24, 2013.
- O. Balci, "Verification, validation, and testing", in J. Banks (ed.), *Handbook of Simulation*, Wiley, 1998.
- J. P. C. Kleijnen, EJOR 82(1):145–162, 1995.
- A. M. Law, *Simulation Modeling and Analysis*, 5th ed., 2015.
- W. L. Oberkampf and C. J. Roy, *Verification and Validation in Scientific Computing*, 2010.
- NASA-STD-7009A (2016), NTRS 20160011121; superseded by 7009B (2024).
- ASME V&V 40-2018.
- T. Y. Chen et al., "Metamorphic testing: a review of challenges and opportunities", ACM Computing Surveys 51(1):4, 2018.
- H.-L. Choi, L. Brunet and J. P. How, "Consensus-based decentralized auctions for robust task allocation", IEEE T-RO 25(4):912–926, 2009.
- D. P. Bertsekas, Annals of Operations Research 14:105–123, 1988.
- J. A. Hanley and A. Lippman-Hand, JAMA 249(13):1743–1745, 1983.
- G. J. Franx, Operations Research Letters 29(5):221–229, 2001.
- A. Cobham, Operations Research 2(1):70–76, 1954.
- J. R. Jackson, Operations Research 5(4):518–521, 1957.
- ITU-R Recommendation P.526.

Web sources consulted for this plan:
- [MIT DSpace, Choi/Brunet/How CBBA thesis record](https://dspace.mit.edu/handle/1721.1/44926)
- [Event-driven CBBA (bound N·D under DMG)](https://arxiv.org/pdf/2509.06481)
- [GCBBA, 50% guarantee caveat](https://journals.sagepub.com/doi/10.3233/FAIA251222)
- [NASA-STD-7009A, NTRS](https://ntrs.nasa.gov/api/citations/20160011121/downloads/20160011121.pdf)
- [NASA application of 7009A credibility factors](https://ntrs.nasa.gov/citations/20230000585)

Internal:
- `lunarsim/vv.py`
- `tests/test_verification.py`
- `tests/test_verification_phase4.py`
- `site/src/verify/main.js`
- `paper/part2_methods.html` (Section 5)
- `paper/v3/part3_methods.html` (Section 5)
- `research_notes/Lunar communications and visibility/earth_visibility_prior_art.md`
