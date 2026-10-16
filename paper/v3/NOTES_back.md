# Paper v3, back half: notes (Stage 1 on 2026-10-15; Stages 2 and 3 on 2026-10-16)

## Files written or changed

| File | Content |
|---|---|
| `paper/v3/part4_results.html` | Section 6 (intro with the version-2 reference-cell comparison and the cost-per-landed-kg correction; 6.1 lander controllers; 6.2 driving validation; 6.3 dispersion and pad radius; 6.4 standoff; 6.5 keep-out incl. the B-12c/B-12d/B-12e analysis, the hold/drive split and the boundary staging; 6.6 autonomy x fleet; 6.7 the law and siting incl. the VoT dimension). Tables 7-13, Figures 5-12. All numbers final. |
| `paper/v3/part5_back.html` | 7 Discussion, 8 Limitations, 9 Availability, Appendices A-D, References ([1],[2],[3],[5],[14],[15],[16],[18],[29],[41],[43],[59] from v2 plus [60]-[121]; [60] now carries the nasa.gov copy as primary link with the two quoted sentences located; cited alone for the "reduction in distance" sentence). |
| `paper/v3/part1_front.html` | Abstract result sentences filled; "500 dispersed landings"; stand-down range 0.033-6 h; "[60]" alone for the distance sentence; the learned-driver sentence; the roadmap paragraph (Sections 6-9, Appendices A-D); a two-rule `<style>` so `table.wide` may break between rows. |
| `paper/v3/part2_related.html` | one cross-reference (Section 6.1). |
| `paper/v3/part3_methods.html` | E17 and E18 designs as run (840 and 1,248 cells, 63,840 years); the released clone recipe (memoryless expert, observation v3, 800 episodes, 25 epochs, 2 x 300 DAgger, sample counts, label-inconsistency score); observation v3 sentence; learned driver as design only, suites on the expert's tables; T levels incl. 0.033 h; PSR route 8.95 / 8.57 km and the E16 numbers; C_rr,eff 0.178; the identity check's canonical MD5; "Sixteen further tests"; 5.4 compute and wall-clock; Table 4 caption; Table 5 rows; all Section 6.x cross-references; no precision runs. |
| `paper/build.py` | `table_e16()` (Table 6 from `results/table_E16.csv`), `fill_common()` (the tags shared by both builds), `render_pdf()`, `build_v2()` (unchanged behaviour; a dry run reproduces the existing `paper/paper.html` byte for byte), `build_v3()` and `main(--v3)`. |
| `paper/v3/paper.html`, `paper/v3/where_the_lander_lands_v3.pdf` | the assembled version 3 (build products). |

## Final placeholder count

`grep -o '\[\[[^]]*\]\]' paper/v3/*.html` -> **2**, both DOIs: `[[DOI: Zenodo record for version 3, to be minted at submission]]` (Section 9) and `[[DOI: Zenodo record of version 2]]` (reference [113]). No `[[E..]]` remains. Build tags left for `build.py`: `{E3_GAIN}` (abstract), `{{v3-TABLE_E16}}` (Section 5.2), `{MKT_MEAN}` and `{INH_MEAN}` (Section 6 intro), `{{TABLE_VV}}` (Appendix B); all are filled by `build_v3()` (the assembled `paper.html` has none).

## Stage 3: the build

- `python paper/build.py --v3` writes `paper/v3/paper.html` (280,471 bytes, 38,380 words by whitespace) and renders `paper/v3/where_the_lander_lands_v3.pdf` (3,123,267 bytes) with the v2 headless-Chrome command. `python paper/build.py` still builds version 2; a dry run of the refactored v2 path reproduces the existing `paper/paper.html` exactly (146,386 characters), so the v2 build is not broken (it was not re-run to disk).
- **PDF: 69 pages, Letter.** 12 `<img>` tags; the 8 Phase-3 figures (fig20-fig27, rebuilt 2026-10-16 02:36-02:37, all "produced" in `figures/phase3_captions.json`) load; **4 do not exist**: `figures/v3_fig01_terrain.png`, `v3_fig02_dataflow.png`, `v3_fig03_descent.png`, `v3_fig04_rover.png` (Figures 1-4 of the front half; NOTES.md already lists them as not yet produced). Chrome prints a broken-image box with the alt text on pages 11, 16, 18 and 20.
- Checks run with PyMuPDF on the rendered PDF (`scratchpad/check_pdf.py`): no text block past the right margin on any page after Table 7 was moved to `table.wide` (its last column had been clipped at 8.8 pt); no page ends with an h2/h3 heading; the caption of Table 7 was stranded at a page bottom until the `table.wide { break-inside: auto }` rule, after which the table follows its caption. Pages with the wide tables (6, 7, 10-13, A2-A4, B3, B4, C1) were rendered and inspected; they fit.
- Not checked: the four missing front-half figures leave their captions below an empty box; the look of the PDF on a printer other than Chrome's.

## Numbers in the text that are not read from a results table (all sourced; listed for the record)

1. Cost per landed kilogram: $5,525 [4,460, 7,281], $5,630 [4,883, 6,655], $10,019 [8,067, 12,756], $7,199 [6,182, 8,612], "$5,048-5,072" and "$306-314 / $264-267 per kg moved" - from `.team/reports.md` LEAD 20:36 (B-16 accepted), not from a committed table. Section 6 intro.
2. The keep-out component analysis (filter and holds +0.000 to +0.021 h; sign flips; T 0.5 h +0.67 [+0.01, +1.80]; etc.) and the shelter-staging artefact (+0.92 [+0.16, +2.16]) - B-12c and B-12d in `.team/reports.md`; the 10-seed post-change check (-0.47 [-1.38, +0.06]) is B-12e's; the hold/drive split for marketplace cells is from the raw `results/E18_plume.csv` (9,000 re-run rows carry `standdown_hold_h` / `standdown_drive_h`; the summary table does not). Section 6.5.
3. The return-drive comparison 72.9 vs 67.3 (with return) and 32.6 vs 33.7 (without), P2-4 pooled greedy, 3 km - B-12d's table (30 paired seeds, single-process runs). Section 6.5.
4. The memoryless law's 94.8% (92.5-96.4) and the round-0 clone's 87.2% (84.0-89.8) on 500 episodes - the LEAD ladder (19:16) and B-10d; no outcome table is released for either. Table 7 marks them "development evaluation, table not released".
5. The reward-v1 PPO row of Table 7 (43.6%, failures 87/13/182, miss 5.73/7.55/99.9 m, 59.8 kg, 8.5 s, -2.18 m/s, paired -50.2 +/- 4.8) - from the first `results/table_E15.csv`, overwritten on 2026-10-15; the box rate and failure counts are also in `.team/reports.md` (LEAD 13:49). Marked "superseded; development evaluation".
6. Label-inconsistency scores 0.41 / 0.33 (filtered / memoryless expert) and the per-component values - B-10d; per-round values 0.28-0.35 are in the policy cards.
7. Per-friction-angle PSR energies 1.49 / 1.70 / 2.56 / 1.76 kWh and the per-metre energies 197.5-201.0 Wh/km and route lengths 8,949 / 8,567 / 8,578 / 9,247 m - B-11b and B-12c development runs (Section 6.2 says "development runs").
8. Wall-clock of the suites, "about three to four hours with three workers at 0.2-0.33 s per simulated year per process" - an estimate from B-12e's "about 9,000 runs, ~30 min at 3 workers" and Section 3.6's 0.326 s per year; no log was available. Sections 5.4 and 9.
9. Pad-A route lengths by standoff (0.52-5.47 km) - `data/driving/driving-v1.json` `route.length_m`, not a results table. Section 6.4.
10. The flown-record anchors, NASA quotations and all Spec/Measured values - unchanged from the front half's sources.

## Numbering

Sections 6 (6.1-6.7), 7 (7.1-7.5), 8, 9; Appendices A (Tables A1-A4), B ({{TABLE_VV}} as B1, B2-B4), C (C1), D (D1); Tables 6-13; Figures 5-12 (fig20->5, fig21->6, fig22->7, fig23->8, fig24->9, fig25->10, fig27->11, fig26->12). Reference [110] is listed but uncited (NOTES.md called it optional); [60]'s primary link is now the nasa.gov copy.

## Things the owner should still decide or check

1. Produce Figures 1-4 (`figures/v3_fig01_terrain.png` ... `v3_fig04_rover.png`); until then the PDF shows empty boxes on pages 11, 16, 18 and 20.
2. The two DOI placeholders.
3. The site's headline "40 % per km" (F-18) is the pooled fit's slope at the origin; Section 6.7 and 7.1 say the cells show 10-19% per km beyond 2 km and 52% per km below 1 km. The site may want the same caveat.
4. A committed table for the cost-per-landed-kg numbers (B-16) so that Section 6's correction paragraph can be read at build time.
5. Whether to release the memoryless law's and the round-0 clone's outcome tables (Table 7 rows marked "not released").
6. NOTES.md's contradictions 7, 8, 9, 17 and 18 are now resolved in the text (stand-down levels, E17 levels, E15 design, name, PPO env version); the remaining open items of Appendix C stand.
