"""E56 step 3: the model search, on validation data only. One iteration per call, every one logged.

    python experiments/phase6/nn/run_search.py --iter K [--max-seconds 520]     # rerun the same K if it stops early

ITERATIONS is the search exactly as it was run, in order: each entry changes one thing against the best so far and
says why. Each run appends a row to results/E56_runs.csv (configuration, seed, validation metrics, wall time).
Rule, fixed before the first run: the score of a configuration is its macro event recall on validation faults at
1 false alarm per pair-day (thresholds from validation fault-free blocks); a change is a GAIN if it raises the best
score so far by more than 0.005; the search stops after three changes in a row without a gain. The chosen
configuration is the best one seen; among configurations within 0.005 of the best, the one with fewer parameters.
The test sets are never opened here.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lunarsim.nn import train as T  # noqa: E402

SEARCH_SEED = 100          # not one of the five final seeds
BASE = {"arch": "tcn", "channels": 24, "kernel": 3, "dilations": [1, 2, 4, 8, 16, 32], "residual": True,
        "lr": 3e-3, "wd": 0.0, "epochs": 8, "batch": 32, "crop": 728}
BEST2 = {**BASE, "epochs": 16}
ITERATIONS = [
    (1, BASE, "start: 6 dilated layers, 24 channels, window 127 s"),
    (2, {**BASE, "epochs": 16}, "train twice as long (16 epochs)"),
    # 2 gained (0.887 -> 0.901): BEST2 is the reference for the next three changes, launched together
    (3, {**BEST2, "channels": 32}, "wider: 32 channels (against iteration 2)"),
    (4, {**BEST2, "dilations": [1, 2, 4, 8, 16, 32, 64]}, "longer window: 255 s (against iteration 2)"),
    (5, {**BEST2, "lr": 1e-3}, "lower learning rate 0.001 (against iteration 2)"),
]
# Outcome: scores 0.887, 0.901, 0.906, 0.899, 0.863. Iteration 2 gained; 3, 4 and 5 did not gain more than 0.005
# over 0.901 (iteration 3 came closest, +0.0049, with 74 % more parameters): three changes in a row without a gain,
# so the search stopped. Chosen: iteration 2, the smallest configuration within 0.005 of the best score.
FINAL = BEST2
FINAL_FROM_ITER = 2


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--iter", type=int, required=True)
    ap.add_argument("--max-seconds", type=float, default=520.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 15.0, exit=True)
    it, cfg, note = [x for x in ITERATIONS if x[0] == a.iter][0]
    out = T.fit(f"search_{it:02d}", cfg, SEARCH_SEED, a.max_seconds, stage="search", it=it, note=note)
    sys.exit(0 if out else 3)
