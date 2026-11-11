"""E56 step 4: train the chosen configuration with five seeds (rerun a seed if it stops at the time limit).

    python experiments/phase6/nn/run_final.py --seed 0      # seeds 0 to 4; seed 0 also saves its weight trajectory

FINAL is the configuration the search chose (experiments/phase6/nn/run_search.py, results/E56_runs.csv). Each run
appends a row with stage "final" to results/E56_runs.csv. The test sets are not opened here.
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lunarsim.nn import evaluate as E  # noqa: E402
from lunarsim.nn import train as T  # noqa: E402

from run_search import FINAL, FINAL_FROM_ITER  # noqa: E402

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, required=True, choices=E.FINAL_SEEDS)
    ap.add_argument("--max-seconds", type=float, default=520.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 15.0, exit=True)
    out = T.fit(E.final_name(a.seed), FINAL, a.seed, a.max_seconds, trajectory=(a.seed == 0), stage="final",
                it=f"final(from {FINAL_FROM_ITER})", note="the chosen configuration, final seed")
    sys.exit(0 if out else 3)
