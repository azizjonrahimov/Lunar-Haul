# Phase 6 plan: the Lunar Rover Interaction Protocol (11 Nov 2026, LEAD)

## 1. What the owner asked for (11 Nov)
1. Finish the open Phase 5 work and commit it.
2. Deeper and more accurate research, with public NASA data used wherever it honestly applies (the PDS Artemis II
   archive included), and better research method.
3. Solve, with sourced and checkable answers, the eight problem groups of the **Lunar Rover Interaction
   Protocol** (owner's list, kept verbatim in §3): positioning, shared map, time, communication, the protocol
   itself, coordination, reliability and security, market and reality. For each: the solution, the method and
   technology, how we use it, who we would partner with, and the evidence.
4. Our own neural network, trained on related data until it is accurate, with its loss landscape and the path
   gradient descent takes through it, shown in 3D together with how the software and hardware work.
5. Better backend architecture and code; better UI/UX, 3D and 2D illustration (anatomy-style cutaways;
   Higgsfield imagery once the owner signs in).
6. All of it carried into the three papers (P1, P2, P3) with proofs and methods, written professionally.

## 2. Rules for this phase (in addition to PLAN-phase5 §2)
- **Baseline first.** Every learned or new method is compared with the simple method it replaces (a chi-square
  test, dead reckoning alone, a fixed-rate report). No baseline, no claim.
- **Split by what we generalise to**: seeds, sites and fleet sizes never appear in both training and test.
- **Honest metrics**: event-level precision and recall for rare faults; never accuracy on rare events.
- **Proved / tested / assumed table** in every paper: each claim is marked as proved (maths, with the
  assumption), tested (which experiment, how many runs), or assumed (with the sweep). Things we have not tested
  are listed as untested.
- **Sources**: every number has a source that was opened. No Sci-Hub. Paywalled papers are cited from the
  abstract, a preprint or an NTRS copy, and the paper says so.
- **Real data is named for what it is.** Artemis II is a crewed flyby: its OpNav images and SPICE kernels test
  position-from-image and geometry code; it is not rover data. SMAP and MSL telemetry test the anomaly-detection
  method; they are not lunar rover telemetry. Simulated data is called simulated.
- **AI-generated images** (Higgsfield) are illustrations only, labelled as such, never evidence, never in a
  paper figure that shows a result.
- Engine results stay byte-identical with every new option off.

## 3. The eight problems (owner's list) and where each is answered
Research notes: `research_notes/Lunar Rover Interaction Protocol/` (00 inputs, 01 positioning and time, 02 map
and coordinates, 03 comms, protocol and security, 04 coordination and market).

| # | Problem group | Research note | Engine work | Experiment | Paper |
|---|---|---|---|---|---|
| 1 | Positioning: "Where am I?" | 01 | B-90 | E50 | P3 (stack), P2 (margin) |
| 2 | Shared map and coordinate system | 02 | B-92 | E52 | P3 |
| 3 | Time | 01 | B-91 | E51 | P3, P2 (reservations) |
| 4 | Communication (physical and network) | 03 | B-94 | E54 | P3 |
| 5 | The protocol itself ("MCP for rovers") | 03 | B-93 | E53 | P1 |
| 6 | Coordination as a team | 04 | (Phase 5 engine) + B-94 lost link | E40-E43, E54 | P1, P2 |
| 7 | Reliability and security | 03 | B-95, B-96 | E55, E56 | P2 (integrity), P3 (security) |
| 8 | Market and reality | 04 | none | none | P3 |

## 4. Pre-registered hypotheses for Phase 6 (written before the runs; `paper/atc/PREREG6.md` holds the exact tests)
H9 positioning: dead reckoning alone breaks the safety separation within a working shift; adding rover-to-rover
and beacon ranging bounds the error near the base; absolute fixes bound it away from the base.
H10 margin: the delay cost of the rules of the road rises with position error roughly in proportion to the
added separation; with the layered scheme it stays within a small multiple of the perfect-position cost.
H11 time: clock error matters for ranging long before it matters for road reservations; a cheap oscillator
with a resync at every base contact is enough for reservations.
H12 map: syncing changed tiles with hazards first keeps a returning rover's hazard map current at a small
fraction of the bytes of a full resend.
H13 protocol: the full message set fits the earlier bit-rate budget at 1 Hz position reports for 20 rovers with
authentication on; it does not at 10 Hz without a wider link.
H14 lost link: store-and-forward with a lost-link rule loses fewer jobs than drop-and-retry at the same radio.
H15 integrity: a learned detector finds wrong position reports earlier than a chi-square innovation test at the
same false-alarm rate for slow drifts, and no better for jumps. It may fail out of distribution.
H16 consensus: with f faulty rovers, the trimmed-mean rule stays within the honest range when the mesh meets
its robustness condition and fails when it does not.
Failed hypotheses are reported as failed.

## 5. Work packages
BACKEND (order): B-90 positioning layer -> B-91 clocks and time -> B-93 protocol messages and codec ->
B-94 store-and-forward and lost link -> B-92 shared map -> B-95 integrity, authentication and consensus ->
B-97 real-data checks (Artemis II OpNav + SPICE; SMAP/MSL) -> B-98 verification rows -> B-99 site data.
B-96 (the neural network and its loss landscape) is run by LEAD's agent in `lunarsim/nn/` and
`experiments/phase6/nn/`; BACKEND does not edit those two folders.
FRONTEND (order): F-60 /protocol/ page (eight problems, one interactive figure each) -> F-61 /network/ page
(loss landscape in 3D with the descent path; what runs where in the vehicle) -> F-62 anatomy-style cutaways of
the navigation, radio and clock hardware -> F-64 UI/UX review and fixes on every page -> F-63 Higgsfield
stills and clips (blocked until the owner signs in) -> F-65 paper pages and results -> F-57 quality pass.
LEAD: the four research notes, PREREG6, B-96 through an agent, the papers (new sections, proofs, the proved /
tested / assumed tables), an internal referee round, PDFs, commits.

## 6. Milestones (owner sees each)
M7 research notes 01-04 and this plan committed.
M8 positioning, time and protocol in the engine (B-90, B-91, B-93) with E50, E51, E53; /protocol/ page frame.
M9 the network trained, baseline beaten or the failure reported, loss landscape exported (B-96); /network/ page.
M10 lost link, map, integrity and consensus (B-94, B-92, B-95), E52, E54, E55, E56; real-data checks (B-97).
M11 papers P1-P3 revised with proofs and the new results; referee round; PDFs.
M12 verification rows, site pages, quality pass, deploy.

## 7. Tools added on 11 Nov (installed for the user, all projects)
anatomy skill (isometric interactive figures), Higgsfield CLI and skills (sign-in pending), REA (MCP + skill),
agency-agents (283 agent definitions), ECC plugin (automatic hooks left off: its standard hook profile can edit
source files and send transcript text to an external model; the owner can turn it on).

## 8. Machine
8 GB shared. The project venv was repaired on 11 Nov (`.venv/pyvenv.cfg` pointed at a Python that no longer
exists; it now points at D:\DevTools\Python\Python312). Console scripts in `.venv/Scripts/*.exe` still carry
the old path: use `.venv\Scripts\python -m <tool>`. torch is the CPU build. Rules of PLAN-phase5 §8 hold.
