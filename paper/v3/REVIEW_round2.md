# Referee review, round 2: "Where the Lander Lands" (v3, paper/v3/paper.html rebuilt after round 1)

Scope: every number changed or added in round 2 (NOTES_back.md "Round 2"), recomputed from the centred table_E20.csv and E20_fit.json, table_E15/E17/E18/E19.csv, table_cost_landed_kg.csv, the siting tables, the raw E19 CSV, the two CLPS outcome JSONs, data/scenarios and v3_front_captions.json; plus a grep of the rebuilt text for the old fit.

## 1. Numbers added or changed in round 2

Confirmed:
- The re-fitted law, everywhere it appears (Abstract, 6.3, 6.5, 6.7, Table 12, 7.1, 8, 9): standoff +0.3003 [+0.2824, +0.3195] = +35.0% [+32.6%, +37.6%]; keep-out −0.0050 [−0.0151, +0.0083]; stand-down −0.0075 [−0.0114, −0.0029]; ln miss +0.0785 [+0.0597, +0.1001] = +8.2% [+6.2%, +10.5%]; the three constants; per-rule standoff +24.5 / +35.6 / +39.5 / +39.6% and keep-out −0.016, −0.033, +0.025, +0.022; the service-level and cost columns; centres 0.046 and 0.048 / 0.046 / 0.048 / 0.042; interactions, dummies, R² and residual SD unchanged.
- Cost per landed kilogram (Section 6): all eight values and intervals match table_cost_landed_kg.csv ($5,525 [4,436, 7,298]; $5,630 [4,892, 6,673]; $10,019 [8,128, 12,904]; $7,199 [6,122, 8,682]; $6,102; $6,707; v2 approximations $5,072 and $5,048; "8–10%" under-read).
- Table 7 memoryless row: box 94.8 (92.5–96.4), failures 11/1/11/3/0, miss 2.82/4.73/80.4, 0.4%, 85.2 kg, 21.6 s, −1.19 m/s match table_E15 and the outcomes JSON (env_version 3, same 500 seeds as the law).
- E19 paired differences (6.6, 7.1, Abstract, 9), recomputed from the raw per-seed CSV: −1.25, +2.15, −6.80, −0.15, +1.15, −5.62 h and −0.036, −0.001, −0.029 of service level, all point estimates exact; my bootstrap endpoints differ by 0.02–0.4 h (e.g. [−3.84, +1.62] against [−3.96, +1.60]), resampling noise between RNG streams, with no sign or zero-inclusion change. The four fleet compositions in 6.6 match data/scenarios.
- E18 counts (6.5): 131 of 600 at 3 km (117 positive, 14 negative), 16 Phase-3 marketplace, 4 with the night on, max |Δ| 1.50 h; 128 of 600 at 1 km. Section 8 "most of the rest exclude it by less than an hour": 241 of 259.
- Abstract: 349 words; 18–160 vehicle-hours; +0.62 to +2.85 h at 1,500 m; "under an hour below 300 m".
- Front captions: Figure 1 (seven sites plus two pads per set, pad A at 1 km clear by 0.4 m, routes for azimuth 0°), Figure 3 (seed 100,001; misses 0.65 and 3.03 m) and Figure 4 (4.74 km, 2.18 h, 0.69 kWh, 48 stops, no intervention, Yutu-2 band disclosed) agree with v3_front_captions.json.

Off:
- [should] N1. Table 7 and 6.1 "+1.0 ± 2.4 points" (memoryless law vs filtered law): the per-episode flags give 10 wins and 5 losses in 500, so a paired normal interval is ±1.5 points; the unpaired normal used for the other rows gives ±2.9. Neither is 2.4.
- [should] N2. Table 7 caption "the paired difference … is on identical episodes (95% CI, normal)": the intervals in table_E15 are unpaired (bc_v3 ±3.5 unpaired against ±2.7 paired; baseline ±4.7 vs ±4.4; bcml ±4.0 vs ±3.2; bc_s0 ±4.8 vs ±4.4). Conservative, but say "unpaired normal" or recompute from the flags.
- [should] N3. 6.7 "only a cost of the order of $10,000 per impact could move a minimum to 1 km" (and Section 8's floor paragraph by implication): in the reference cell with free energy and no value of time, 1 km becomes the minimum only below about $900 per impact against 2 km, $1,400 against 3 km and $2,300 against 5 km; at $10,000 the 1 km damage ($0.64 M/yr) still exceeds the hauling increment to 5 km ($0.15 M/yr) four times over. Write "below about $1,000–2,000 per impact". (My round-1 "about $10 k" was the same loose estimate; this arithmetic supersedes it.)
- [may] N4. 6.7 marketplace keep-out "−3.3% [−5.0%, −1.5%]": e^−0.0497 − 1 = −4.8%.
- [may] N5. Figure 4 caption "the supervised level makes good 2.73 km/h" against Table 6 and 6.2 "2.711 km/h" (analytic cadence 500 m per 660 s versus the integrator's four whole stops). Quote one.

Not checkable: Figure 3's held-reading counts (3 and 6); the Figure 4 drive statistics beyond the notes.

## 2. Survivors of the uncentred fit

None. 0.334 / 39.7%, 0.114 / 12.1%, 0.023 / 2.3%, 0.015 / 1.6%, "no smooth effect", "only through off-pad landings", "hypothesis test", "at the fit's origin" and "indistinguishable from zero" do not occur in the body (the two numeric hits are unrelated service-level values).
- [should] S1. One sentence of the old framing remains, 6.7 first paragraph: "the year's off-pad share (so that the fit can separate dispersion acting through off-pad events from any smooth effect)". The same section now says the law "cannot separate what the engine does not". Rewrite the parenthesis as "(entered to check that it adds nothing once the miss is in the model)".

## 3. Abstract, Limitations, Conclusions

- [must] A1. Abstract "The keep-out radius and stand-down time add no measurable delay at the 2–8% utilisations simulated" contradicts 6.5 (240 cells positive with intervals excluding zero; 2 and 3 km radii cost up to +1.86 h in the Phase-2 in-house night cells, at exactly those utilisations) and the Conclusions ("the radius matters where the duration does not"). The law's main effect at the typical load is near zero; the cells are not. Write: "A 1 km keep-out adds no measurable delay (… −0.10 h [−0.41, +0.20]); 2–3 km radii cost up to +1.9 h in the lightest night cells; stand-down time does not matter; the cost is 18–160 vehicle-hours a year of evacuation driving."
- [must] A2. Section 8 "The expert … its outcome table is not among the released files" is now false: memoryless_CLPS is released and cited in 6.1, Table 7 and table_E15. Delete the clause.
- Otherwise the three agree with Section 6: "about a third" per kilometre, concave; four to eighteen hours; +8.2% per e-fold as "a quarter of a kilometre of standoff" (8.2/35); 100 m pad absorbs the 50 m target, 25 m does not; two autonomous ≈ six teleoperated as pooled-dispatch only; within five points / trailing by thirty. Section 8 now names the typical-load reading, the by-construction channel, the staging rule, the $0.1 M floor, Wittal's 10 t curve and classical-tables-only.
- Voice: the Abstract, Section 8 and Section 9 contain none of the listed tells (one ", not " each, one "is what" in 9); the counted openers are down to three; 7.1 no longer repeats Table 10's intervals. Section 9 reads as a researcher's summary.
- [may] A3. v3_front_captions.json records that Terrain.line_of_sight calls the 1 km pad A blocked (−2.56 m) while sites.json calls it clear (+0.4 m); the siting shield of 1 at 1 km rests on the sites.json call. The Figure 1 caption says so; Section 8's "siting sweep's floor" paragraph should too.

## 4. Round-1 [must] items

All seven closed: N1 corrected; C1/C2 reframed in RQ6, contribution 1, 6.3, 7.2 and 8 (one residual parenthesis, S1 above); C3 closed by centring u; Figure 2 now points to v3_fig02_pipeline.png, which exists; Figure 10's caption matches its panels; no "[[" placeholder remains. Nothing from round 1 is open at [must]; A1 and A2 above are new to the round-2 text.

## Counts

[must] 2 · [should] 4 · [may] 3
