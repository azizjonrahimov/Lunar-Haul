"""Before/after table for a rerun (PREREG change 5, the dispatch fixed-point fix): the rows now in an experiment's run
files against the archived rows of the same (cell, seed, start_year), for the papers' "choices after looking" sections.

    python experiments/phase5/compare_rerun.py --exp E43          # -> results/E43_fixpoint_before_after.csv / .json
    python experiments/phase5/compare_rerun.py --exp E40 --archive results/archive/E40_runs.pre-fixpoint-2026-10-28.csv

Per label and start year: n matched, the old and new cell means, the mean and the largest absolute per-run change,
for the primary outcome (delay_mean_h), the censored urgent wait and the run time. The JSON holds the overall figures
the build scripts quote (rows matched, mean |change| and largest |change| of the primary outcome, the share of rows
whose primary outcome moved by more than 0.1 h, the old and new mean run time). Works on partial reruns (prints n).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "results")
sys.path.insert(0, ROOT)
from experiments.phase5 import run_phase5 as RP  # noqa: E402

KEY = ["cell", "seed", "start_year"]
METRICS = ["delay_mean_h", "atc_urgent_wait_mean_cens_h", "run_s"]
MOVED_H = 0.1


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--archive", nargs="*", help="archived run files (default: results/archive/{EXP}_runs*.pre-fixpoint-*.csv)")
    ap.add_argument("--tag", default="fixpoint", help="name of the change, used in the output file names")
    a = ap.parse_args()
    arch = a.archive or sorted(glob.glob(os.path.join(RES, "archive", f"{a.exp}_runs*.pre-fixpoint-*.csv")))
    files = RP.run_files(a.exp)
    if not arch or not files:
        raise SystemExit(f"{a.exp}: {len(arch)} archived file(s), {len(files)} current file(s)")
    old = pd.concat([pd.read_csv(f, float_precision="round_trip") for f in arch], ignore_index=True)
    new = pd.concat([pd.read_csv(f, float_precision="round_trip") for f in files], ignore_index=True)
    new = new.drop_duplicates(KEY, keep="last")
    old = old.drop_duplicates(KEY, keep="last")
    if "dispatch_fixpoint" in new and not (new["dispatch_fixpoint"].fillna(0) == 1).all():
        raise SystemExit("current rows are not all flagged dispatch_fixpoint=1")
    if "dispatch_fixpoint" in old and (old["dispatch_fixpoint"].fillna(0) == 1).any():
        raise SystemExit("archived rows carry the flag")
    for d in (old, new):
        if "label" not in d:
            d["label"] = d["cell"].str.extract(r"label=([^;]+)")[0]
    m = new.merge(old, on=KEY, suffixes=("_new", "_old"))
    rows = []
    for (lab, y), g in m.groupby(["label_new", "start_year"], sort=False):
        r = {"label": lab, "start_year": int(y), "n": len(g)}
        for mt in METRICS:
            if f"{mt}_new" not in g:
                continue
            d = g[f"{mt}_new"] - g[f"{mt}_old"]
            r[f"{mt}_old"] = float(g[f"{mt}_old"].mean())
            r[f"{mt}_new"] = float(g[f"{mt}_new"].mean())
            r[f"{mt}_change"] = float(d.mean())
            r[f"{mt}_max_abs"] = float(d.abs().max())
        rows.append(r)
    t = pd.DataFrame(rows)
    out = os.path.join(RES, f"{a.exp}_{a.tag}_before_after")
    t.to_csv(out + ".csv", index=False)
    dp = m["delay_mean_h_new"] - m["delay_mean_h_old"]
    summary = {
        "exp": a.exp, "archived_files": [os.path.relpath(f, ROOT).replace(os.sep, "/") for f in arch],
        "current_files": [os.path.relpath(f, ROOT).replace(os.sep, "/") for f in files],
        "n_old": int(len(old)), "n_new": int(len(new)), "n_matched": int(len(m)),
        "primary": "delay_mean_h",
        "primary_mean_change_h": float(dp.mean()), "primary_mean_abs_change_h": float(dp.abs().mean()),
        "primary_max_abs_change_h": float(dp.abs().max()),
        "primary_max_abs_label": str(m.loc[dp.abs().idxmax(), "label_new"]),
        "share_rows_moved_over_0.1h": float((dp.abs() > MOVED_H).mean()),
        "share_rows_identical": float((dp == 0).mean()),
        "run_s_old_mean": float(m["run_s_old"].mean()), "run_s_new_mean": float(m["run_s_new"].mean()),
        "run_s_old_max": float(m["run_s_old"].max()), "run_s_new_max": float(m["run_s_new"].max()),
        "labels_only_new": sorted(set(new["label"]) - set(old["label"])),
        "labels_only_old": sorted(set(old["label"]) - set(new["label"])),
    }
    with open(out + ".json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(summary, f, indent=1)
        f.write("\n")
    pd.set_option("display.width", 200)
    print(t.round(2).to_string(index=False))
    print(json.dumps({k: (round(v, 3) if isinstance(v, float) else v) for k, v in summary.items()
                      if k not in ("archived_files", "current_files")}, indent=1))
    print(f"wrote {out}.csv and .json")


if __name__ == "__main__":
    main()
