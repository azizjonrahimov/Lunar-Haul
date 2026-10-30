# E44 variant 6_request_rule (dropped, not reported)

Exploratory variant of type 6 under PREREG change 9: a vehicle requests a resource only when no closed or closing zone
lies before it. It gave 203 deadlocks and 0 violations, against 202 in the registered cell. Tracing showed the type-6
'deadlocks' were a stall-classification defect (vehicles held by a closure counted only within ~1 m of the zone line),
not reservations held behind a hold point, so the variant had no mechanism to test. Dropped per the change-9 correction;
details in results/E44_defects.json, change_9.variant_dropped.
