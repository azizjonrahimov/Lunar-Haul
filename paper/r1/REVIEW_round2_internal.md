# Internal round-2 referee check (22 Oct 2026, a fresh reviewer agent; not the journal's referee)

Recommendation: **minor revision**. Every Must item of round 1 is addressed and every number spot-checked matches the
result files. The remaining problems are in the material added late (Stages F and G) and in how the abstract,
Discussion and Conclusions repeat it.

## Round-1 requests
Addressed: 1-13, 15, 16, 18, 19, 21. Partly: 14 (antenna basis given, no second height run), 17 (abstract about 300
words although the response says ~240; file paths in prose in 5.4 and 7; "Phase 2 mix" still in the captions of
Figures 2, 3 and 6), 20 (busy fleet and plant relay bound not run). Not addressed: 22 (link budget; stated as a
limitation).

## New problems, most serious first
- **N1.** Stage G helps only at samples dark in all of 2028-2031; the 2028 sample is dark for 18 months and is waited
  out, so "help does not change 2028" describes the rescue rule, not help. "Never" also means only "not in
  2028-2031". Rerun Stage G with rescue for any wait longer than the rescue time, or restate the 2028 claims (5.4, 6,
  8) as a limit of the rule. -> B-60.
- **N2.** "The helper's own time is not modelled" is missing from the abstract, the third finding of 8 and Table 5's
  Stage G row. 57-81 rescues a run at <= 168 h would keep a helper rover busy; no check that parking points in line of
  sight exist. "A crew" (4.2) contradicts "crewed periods are not modelled" (7).
- **N3.** "Three of four start years" is a tonnage split (113 t in 2028) but is attached to urgent deliveries; urgent
  completion in 2028 is 75 % (re-draw) and 70-79 % (rescue <= 168 h) against 52 % for strict. Also explain how 75 % of
  urgent items arrive while 89 % of the fleet is stranded May-December 2028. -> B-60 diagnostic b.
- **N4.** The one-month result is stated at three strengths (abstract "keeps most", 5.4 "survives", 6 "keeps").
  Against the re-draw, 720 h lengthens the censored p90 2.36x [1.33, 4.19] (p = 0.016) and lowers completion 7.7
  points [-15.3, -0.2]; report them.
- **N5.** "Indistinguishable" / "as good as" for a non-significant difference (-21 t [-48, 5]; censored 1.43
  [0.71, 2.86] at 168 h): write "not significantly different" with the intervals.
- **N6.** The tonnage break-even sits at the edge of the range (+3 t [-37, 44] at 720 h; 58 % of draws beyond; 1.05 %
  below 0 h, unreported); the interpolation method is not in 4.4. Write "about 720 h or more (95 %: from 310 h)".
- **N7.** The auction-pool cause rests on three snapshots of one seed: count pool-full hours in all five 2028 seeds,
  or write "in the run we traced". -> B-60 diagnostic a.
- **N8.** The abstract's price leaves out that the rover's effect is not significant by the paired test (-9.1 h
  [-19.6, 1.4], p = 0.23) and holds for the fixed night share only; "exceeds the staff in 18 of 20 seeds" needs "with
  a soft operator pool".
- **N9.** Stages F and G were added during the revision and are not primary comparisons; label them exploratory where
  they carry the abstract and 8.
- **N10.** "The relay results do not depend on the free second chance" holds because the relay is assumed to see every
  route point; say so.
- **N11.** 2,404 route cells (1, 3.1) vs 283 of 2,421 route samples (5.4); the swap test fixes landings but redraws
  manifests (say so); "such a year recurs" is inferred, not shown; 2028 tonnage is not monotone in rescue time (86,
  135, 195, 143, 208 t); "0-10 %" for later years where 2029 is 10.5 %.

## Spot checks (all match)
Strict DTE tonnage and completion; censored p90 medians; Table 7 strict targets (2x target 0.583 recomputed); LCRNS
ratio; teleoperated peaks; price 38 M$ [11, 370] and its draw shares; strategic minus rover +0.05 [-0.26, 0.34];
Stage F (stranding, re-draws, never-linked legs, bounded rule); Stage G (week, month, break-even, rescues, 2028);
E21_strategic_years.json (tonnage by year, waits, 79 %, stranded share, swap test, sky hours, first link). The
"-265 t [-277, -253] against strict" pairing is computed in build_r1.py from raw runs and was not checked
independently.
