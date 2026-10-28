"""B-75: per-owner columns for the E40 rows that ran before they existed (own_<O>_urgent_wait_cens_h, own_<O>_delivered_t).

    python tools/atc/backfill_owner.py run      # resumable; -> results/E40_owner_backfill.csv
    python tools/atc/backfill_owner.py check    # every row of the run files has its per-owner columns somewhere

Each row lacking them (own_A_delivered_t empty) is rerun with the same cell, seed and start year; every column the row
already has must equal the rerun bit for bit (read with float round-trip; run_s, the wall time, excepted), otherwise
the tool stops and reports the row (LEAD's condition). Only the new columns are written, to a separate file keyed by
cell, seed and start year; the run files are never modified. experiments/phase5/analyse_e40.py merges it.
Single process, --max-seconds 480.
"""
from __future__ import annotations

import argparse
import math
import os
import sys
import time
import warnings

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from experiments.phase5 import run_phase5 as R  # noqa: E402

OUT = os.path.join(ROOT, "results", "E40_owner_backfill.csv")
KEY = ["cell", "seed", "start_year"]


def todo() -> pd.DataFrame:
    parts = []
    for f in R.run_files("E40"):
        d = pd.read_csv(f, float_precision="round_trip")
        if "own_A_delivered_t" in d:
            d = d[d["own_A_delivered_t"].isna()]
        parts.append(d)
    d = pd.concat(parts, ignore_index=True)
    if os.path.isfile(OUT):
        done = pd.read_csv(OUT)[KEY]
        d = d.merge(done, on=KEY, how="left", indicator=True)
        d = d[d["_merge"] == "left_only"].drop(columns="_merge")
    return d


def same(a, b) -> bool:
    if isinstance(a, float) and math.isnan(a):
        return isinstance(b, float) and math.isnan(b)
    try:
        return float(a) == float(b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def cmd_run(max_s: float) -> None:
    t0, last = time.time(), 20.0
    cells = {c["key"]: c for c in R.e40_cells()}
    rows = todo()
    print(f"run: {len(rows)} rows to backfill")
    for _, row in rows.iterrows():
        if time.time() - t0 > max_s - max(60.0, 1.5 * last):
            print("run: time limit; rerun")
            return
        c = cells[row["cell"]]
        year = None if int(row["start_year"]) == R.start_year(int(row["seed"])) else int(row["start_year"])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            new = R.run_one(c, int(row["seed"]), year)
        last = new["run_s"]
        bad = [k for k in row.index if k not in ("run_s",) and not pd.isna(row[k]) and k in new
               and not same(row[k], new[k])]
        bad += [k for k in row.index if k in new and pd.isna(row[k]) and not pd.isna(new[k]) and not k.startswith("own_")]
        if bad:
            raise SystemExit(f"MISMATCH, stopping: {row['label']} L{row['load']} seed {row['seed']} {row['start_year']}: "
                             + ", ".join(f"{k}: {row[k]!r} vs {new[k]!r}" for k in bad[:5]))
        rec = {k: row[k] for k in KEY}
        rec.update({k: v for k, v in new.items() if k.startswith("own_") and k != "own_teams"})
        pd.DataFrame([rec]).to_csv(OUT, mode="a", header=not os.path.isfile(OUT), index=False, lineterminator="\n")
        print(f"  {row['label']} L{row['load']} seed {row['seed']} {row['start_year']}: matches; {len(rec) - 3} columns "
              f"added ({last} s)", flush=True)
    print("run: done")


def cmd_check() -> None:
    left = todo()
    print(f"check: {len(left)} rows still without per-owner columns")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "check"])
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    cmd_run(a.max_seconds) if a.cmd == "run" else cmd_check()
