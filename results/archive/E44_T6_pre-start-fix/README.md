# E44 type-6 parts, first pass after change 8 (archived, not results)

Archived under PREREG change 9 on 29-30 Oct 2026. These are the 10 batch files of type 6 (landing closure, n =
10,000) from the E44 rerun, made with the R10 junction tiles of change 8. That pass showed three things.

| what | count | class | what was done |
|---|---|---|---|
| R3 "inside without grant" | 10 | builder start-state defect | Vehicles started within stopping distance of a crossing tile, so they could not stop before it. Fixed in the type-6 builder: no start within stopping distance + 20 m of a tile. |
| same-lane gap below D0 | 10 | metric artefact | No contact; minimum clearance 2.2 m. Vehicles on two roads crossing at under 30 deg counted as one lane. Fixed: the D0 violation and the near-miss gap count only same-road, same-direction pairs (road identity). |
| deadlocks | 201 | genuine finding | All at R = 1 km. A vehicle held at a closing zone's boundary held a crossing tile that the vehicle inside needed to exit. Kept in the registered cell; the request-rule variant is run separately. |

The final type-6 run is in results/E44_parts/T06_*.csv.gz. Details: results/E44_defects.json, block "change_9".
