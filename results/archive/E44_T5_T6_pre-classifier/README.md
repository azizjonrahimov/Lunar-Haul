# E44 types 5 and 6 before the stall-classifier fix (archived, not results)

Archived on 30 Oct 2026 under the change-9 correction. The stall check counted a vehicle held by a closed zone only
within ~1 m of the zone line, and called any stalled vehicle with an ungranted group 'waiting for a grant'. Type 6 had
202 deadlocks, all such closure holds at R = 1 km. Type 5 had 386, which are re-checked. Only deadlock flags can change.
Both types are rerun under the fixed classifier in results/E44_parts/. Details: results/E44_defects.json,
change_9.classification_defect.
