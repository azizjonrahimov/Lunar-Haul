# Phase 5 plan: Lunar ATC (27 Oct 2026, LEAD)

## 1. What the owner asked for (27 Oct)
LunarHaul becomes the test bed for **Lunar ATC**: an on-Moon network that lets rovers, hopper drones and robots of
different companies talk to each other directly, team up on heavy and complex jobs, share jobs, roads and chargers,
and keep working when Earth is out of sight ("the AI suggests, the safety program decides"). Owner's list:
1. Deep research (done 27 Oct: `research_notes/Lunar ATC/`, five notes, read them before your task).
2. Simulate how it works, and how fleets struggle without it, long enough for specific, defensible results.
3. Improve every part of the 3D site; clear "inside" and "on its own" views of every vehicle, rocket and rover.
4. Slower motion so each vehicle can be followed (F-50, running).
5. Many more verification checks than the current 13.
6. Three professional papers, human in tone, each on a different piece of work.
7. Push and deploy.

## 2. Honesty rules for this phase
- The learned part is a small network (MLP about 1.5k parameters) that corrects auction bids. Papers call it a
  "learned bidding policy". "Neural traffic network" is the product's name, never a claim about the method.
- Every number in a paper comes from a results file through a build script that asserts the wording's facts
  (the R-1 pattern, `paper/r1/build_r1.py`).
- Pre-register the hypotheses (§4) in `paper/atc/PREREG.md` before the main runs; report the ones that fail.
- Results of hand-built rules (no published lunar standard exists) are labelled as assumptions with sweeps.
- Vehicle internals: published layouts where they exist; everything else labelled "schematic".

## 3. The three papers (LEAD writes; build scripts like R-1's; style: `paper_writing_guide.md`)
- **P-A "Without Earth in the loop"**: does the pooling gain survive when decisions move onto the robots?
  Fleets without the network (owners alone, coordinated from Earth; one pooled dispatcher on Earth that acts only
  while Earth is in view, strict or plan-ahead) against fleets with it (elected leader on the Moon; decentralised
  auction with hand-built bids; the same with learned bids), plus a full-information oracle. Real Earth-link
  windows 2028-2046 (R-1 files), terrain-limited robot radio (B-70), message loss, cross-owner team lifts.
  Experiments E40-E42.
- **P-B "Rules of the road"**: a runtime-assured safety layer for robots of many owners near landing zones, crew and
  single-lane roads. Exhaustive check of a discrete model (with mutation tests), 1.2 million simulated encounters
  in 12 types (rule-of-three bounds), and the delay the rules cost inside the logistics model. E43-E45.
- **P-C "Owners who cheat"**: payment rules and audits for a market of self-interested owners: fairness to each
  owner against working alone, the operator's budget, how much an owner gains by shading bids or hogging chargers,
  and what audits recover. E46.
All three cite v2, v3 and R-1 as prior work and share one methods appendix (engine, V&V).

## 4. Pre-registered hypotheses (from `multi_owner_allocation.md` §6.5, `traffic_and_safety.md`)
H1 sharing: pooled beats alone by roughly the v2 margins at 30-60 % load; the smallest owner gains most.
H2 availability: an Earth-only dispatcher (strict) loses most of the pooling gain during ~14-day blackouts at
BASE; plan-ahead recovers part; an 80 % relay recovers most. (Central new measurement.)
H3 decentralisation: at <= 0.10 message loss the on-Moon auction is within 10 % of the oracle; at 0.25-0.40
deep bundles lose more than shallow; the leader matches the auction unless the mesh partitions.
H4 learning: learned bids beat hand-built bids by a few percent at 30-60 % load, nothing at 10 %; may lose out of
distribution; a linear model may capture most of the gain.
H5 incentives: first-price invites shading; second-price per item reduces it; posted price + Shapley sharing
keeps every owner at least as well off as alone; the operator's budget balance is reported, not assumed.
H6 team lifts: cross-owner pairs raise the movable share (v2: 40 % -> 55 %); under loss, failed meetings rise
unless a commit-and-timeout step is used.
H7 safety: zero violations in every encounter type; each rule removed in turn produces a counterexample.
H8 cost of safety: the rules cost little delay at today's traffic and more at 4-8x fleet density.

## 5. Load
v2's typical utilisation is 4.6 %, where allocation quality barely matters. Run at about 10, 30 and 60 % (demand
phase and fleet size), and say plainly that today's planned base sits at the low end.

## 6. Work packages (detail in the inboxes)
BACKEND (critical path, in order): B-70 radio mesh (running) -> B-71 real vehicle classes and hoppers -> B-72
decision places, messages and Earth gating -> B-73 decentralised auction and cross-owner team lifts -> B-74 learned
bidding policy -> B-75 P-A experiments -> B-77 roads and rules in the engine -> B-78 encounter simulator, safety
layer and exhaustive check -> B-76 owners and payments -> B-79 verification batches (batch 1 can start any time
after B-71) -> B-80 site data.
FRONTEND: F-50 slower motion (running) -> F-51 every vehicle "on its own" and "inside" -> F-52 3D audit of every
page -> F-53 Lunar ATC on /world/ (needs B-80) -> F-54 /atc/ page with an encounter sandbox (needs B-78 fixtures)
-> F-55 verification page phase 5 -> F-56 the three paper pages, results and a new story -> F-57 quality pass.
LEAD: plan, PREREG, commits, runs heavy jobs when asked, writes P-A/P-B/P-C, internal referee round, PDFs, deploy.

## 7. Milestones (owner sees each)
M1 radio mesh + vehicle classes + slower motion (B-70, B-71, F-50).
M2 with/without engine working, degenerate checks pass (B-72, B-73), cutaway viewer (F-51).
M3 learned policy + P-A runs + verification batch 1-2; P-A draft.
M4 safety layer, encounters, exhaustive check, roads; P-B draft; /atc/ page.
M5 payments and cheating; P-C draft; verification batch 3.
M6 internal referee round for all three, PDFs, site pages, deploy.

## 8. Memory
8 GB shared by three sessions. Heavy jobs: single process, foreground, `--max-seconds 540` chunks, cached and
resumable; check free RAM >= 0.4 GB before builds/browsers; one browser page at a time.
