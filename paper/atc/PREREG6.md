# Pre-registration: Phase 6 experiments (the Lunar Rover Interaction Protocol)

Written 11 November 2026 by LEAD, before any Phase 6 result exists (git history dates this file). The E56
pipeline (B-96) was being built when this was written; no E56 number had been seen. Changes made after the
first result row exists are listed at the end with the date and the reason; the original text stays. The
general rules of `PREREG.md` (common random numbers, percentile bootstrap 95 % CI with 20,000 resamples, TOST
for "no practical difference") apply unless stated.

## 1. Questions
- **Q-P (positioning).** How large does a rover's position error get at a south-pole base without GPS, and how
  much of it does each layer remove: dead reckoning, ranging between rovers and to base beacons, absolute fixes
  against the map, a lunar navigation service?
- **Q-M (margin).** What does position error cost the rules of the road in delay, once the separation margin
  is widened to cover it?
- **Q-T (time).** How good must the clocks be, for ranging and for road reservations?
- **Q-S (map).** How many bytes does it take to bring a rover's map up to date after it was out of contact?
- **Q-R (protocol).** Does the full message set fit the radio we assumed, with authentication on?
- **Q-L (lost link).** Does store-and-forward with a lost-link rule lose fewer jobs than drop-and-retry?
- **Q-I (integrity).** Can a rover tell that another rover's reported position is wrong, how fast, and does a
  small learned detector do better than the classical tests?
- **Q-C (consensus).** How many faulty rovers can a shared estimate tolerate on our mesh?

## 2. Conditions and data
- Fleet and month: the Phase 5 scenario "p5 3eq, 30 % load" and its July 2028 window, at 1x, 4x and 8x fleet;
  30 seeds per cell for engine experiments unless a run-time limit forces fewer (then the number is stated).
- Parameters: from the "Simulation parameters" tables of research notes 01 to 04, each with its source. A
  parameter without an opened source is ASSUMED and swept.
- E56 data: true motion from the simulator's traces; faults injected into reports (jump, slow drift, frozen
  report, frame error, noise inflation); honest disturbances kept in the fault-free class. Split by seed/month
  and by vehicle pair into train, validation and test, plus an out-of-distribution set (noisier sensors, fault
  sizes outside the training range).

## 3. Outcomes
- E50: position error (median, p95, max, m) per layer set; share of time the 95 % bound exceeds the separation
  budget; safety violations with and without the widened margin; delay per delivery against perfect position.
- E51: ranging error added by clock error (m); reservation conflicts caused by clock error alone; longest time
  without a resync that keeps each use inside its budget.
- E52: bytes to sync after 1 h to 14 days out of contact, against a full resend; time until the hazard layer
  is current; hazards hit because of a stale map.
- E53: bits per second per rover and per busiest mesh link at 0.1, 1 and 10 Hz for 5 to 80 rovers.
- E54: jobs lost, urgent wait, age of information at the base, reservations left stuck.
- E55 and E56 (primary for Q-I): event-level recall and median detection delay per fault type at a fixed
  false-alarm rate of one per rover-pair-day on fault-free data (thresholds set on validation data only).
  Secondary: precision, recall at one false alarm per pair-hour, p90 delay, window-level ROC and PR AUC,
  inference time and model size.
- E55 (Q-C): error of the agreed estimate against the honest rovers' range, by number of faulty rovers f and
  by whether the mesh meets the robustness condition.

## 4. Hypotheses and decision rules
- **H9 (positioning).** With dead reckoning alone the p95 position error exceeds the separation budget within
  one 8-hour shift of driving. With ranging added it stays inside the budget within radio range of the base
  beacons. With absolute fixes it stays inside the budget away from the base. Supported per layer if the p95
  error over seeds is on the predicted side of the budget.
- **H10 (margin).** Delay per delivery with the widened margin and the layered scheme is within 1.5 times the
  delay with perfect position at 1x fleet (TOST margin 50 % of the perfect-position delay), and the gap grows
  at 4x and 8x. With dead reckoning alone and the widened margin the delay is larger by a CI that excludes
  zero.
- **H11 (time).** A resync interval exists for the cheaper oscillator class at which reservation conflicts due
  to clock error are zero while its clock error still adds more than the ranging radio's own noise to ranging.
  Supported if such an interval is found in the sweep; otherwise reported as not supported.
- **H12 (map).** Hazards-first sync of changed tiles needs under 10 % of the bytes of a full resend after 24 h
  out of contact, and brings the hazard layer current sooner than oldest-first at every link rate.
- **H13 (protocol).** At 1 Hz position reports, 20 rovers and authentication on, the busiest link carries no
  more than the 16 kbit/s assumed in Phase 5; at 10 Hz it carries more. Reported with the byte counts whichever
  way it comes out.
- **H14 (lost link).** At message loss 0.25 and with a 14-day Earth blackout, store-and-forward with the
  lost-link rule loses fewer jobs than drop-and-retry (paired CI excludes zero) and leaves no reservation
  stuck past its timeout.
- **H15 (integrity).** At one false alarm per pair-day: (a) on slow drifts the network's median detection
  delay is shorter than the per-step chi-square test's (bootstrap CI over events excludes zero); (b) on jumps
  the two are within one second (TOST margin 1 s); (c) against CUSUM the comparison is reported without a
  predicted direction (exploratory); (d) on the out-of-distribution set the network's recall may fall below
  CUSUM's: reported whichever way it comes out. The test set is scored once, with the configuration chosen on
  validation data.
- **H16 (consensus).** With f faulty rovers the trimmed-mean rule keeps the agreed value inside the range of
  the honest rovers' values whenever the mesh graph is (2f+1)-robust, in every run; when it is not, at least
  one run leaves the range.

Family for multiplicity: {H9, H10, H13, H14, H15a} are confirmatory (Holm). The rest are exploratory.

## 5. What would count against us
- H15a failing means the learned detector has no measured advantage over a 1960s test; the papers then
  recommend the classical test and say so.
- H13 failing at 1 Hz means the Phase 5 radio budget was too small; P3's sizing table is corrected.
- H10 failing means position error, not the rules, sets traffic capacity; P2 says so.

## 6. Changes after first results
- **11 Nov 2026, E50 seeds and the budget (decided after one timing cell: 1x and 4x, seed 1).** Run time per
  cell is 1.5 min at 1x, about 11 min at 4x and about 42 min at 8x, so E50 runs 30 seeds at 1x, 10 at 4x and 5
  at 8x (section 2 allows fewer seeds when run time forces it, with the number stated). The seed-1 numbers were
  seen when this was decided; they did not enter the choice, which follows run time only. The "separation
  budget" of H9 is R1's static margin D0 = 5 m (`lunarsim/atc/safety.py`), the distance the rules already
  keep free for position uncertainty.
