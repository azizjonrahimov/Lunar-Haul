# E44 parts from the first main run (archived, not results)

Archived on 29 Oct 2026 under PREREG change 8. These are the batch files of the first E44 main run: types 1-10
complete, plus 9 of the 25 type-11 batches. The run was stopped when an interim summary showed violations in
four types:

| type | violations |
|---|---|
| T4 | 37 |
| T5 | 3 |
| T6 | 82 |
| T9 | 58 |
| all others | 0 |

Two simulator defects caused the T4/T5 and T6 violations:
- the vehicle body swung off the path at corners;
- the type-6 builder made road crossings with no junction tile.

Both are fixed, and the final run repeats all 12 types at the same n in results/E44_parts/. The T9 dead-stop
violations are genuine (R1 assumes a leader brakes at most 0.8 m/s²; a fault stops instantly). They are reported
in results/E44_bounds.json.

Details and re-run counts: results/E44_defects.json.
