"""E56: the result tables of results/E56_integrity.json as Markdown.

    python experiments/phase6/nn/make_tables.py            # print
    python experiments/phase6/nn/make_tables.py --write    # replace the generated block of results/E56_README.md
"""
from __future__ import annotations

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lunarsim.nn import evaluate as E  # noqa: E402
from lunarsim.nn import faults as F  # noqa: E402

DETS = ("chi2_step", "chi2_window", "cusum", "logreg", "net")
NAME = {"chi2_step": "chi-square per step", "chi2_window": "chi-square windowed", "cusum": "CUSUM",
        "logreg": "logistic regression", "net": "network (5 seeds)"}


def cell(e) -> str:
    d = e["delay_median_s"]["mean"]
    return f"{e['recall']['mean']:.2f} / {d:.0f} s" if d == d else f"{e['recall']['mean']:.2f} / -"


def headline(res, sname: str, rate: str, events: str = "events", cls: str = "") -> None:
    print(f"| Detector | false alarms per pair-day | " + " | ".join(F.FAULT_TYPES) + " | all |")
    print("|---|---|" + "---|" * (len(F.FAULT_TYPES) + 1))
    for det in DETS:
        b = res[sname][det][rate]
        ev = b[events] if not cls else b[events][cls]
        fa = b["fa_per_pair_day"]["mean"] if not cls else b["fa_per_pair_day_by_class"].get(cls, float("nan"))
        print(f"| {NAME[det]} | {fa:.2f} | " + " | ".join(cell(ev[t]) for t in E.TYPES) + " |")
    print()


def detail(res, sname: str, rate: str) -> None:
    print("| Detector | fault | n | recall (95 % interval) | sd over seeds | precision at 1 fault per pair-day | "
          "delay median (95 %) | delay p90 | window ROC AUC | PR AUC |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for det in DETS:
        b = res[sname][det][rate]["events"]
        for t in E.TYPES:
            e = b[t]
            a = res[sname][det]["window_auc"][t]
            r, dm = e["recall"], e["delay_median_s"]
            print(f"| {NAME[det]} | {t} | {e['n_events']} | {r['mean']:.3f} ({r['ci95'][0]:.3f} to {r['ci95'][1]:.3f}) "
                  f"| {r['sd_seeds']:.3f} | {e['precision_at_1_fault_per_pair_day']:.2f} | {dm['mean']:.0f} s "
                  f"({dm['ci95'][0]:.0f} to {dm['ci95'][1]:.0f}) | {e['delay_p90_s']['mean']:.0f} s | "
                  f"{a['roc_auc']:.3f} | {a['pr_auc']:.3f} |")
    print()


def fa_table(res) -> None:
    print("| Detector | set | target | false alarms per pair-day (95 %) | per hour, blocks with driving | per hour, "
          "blocks without | UWB blocks, per pair-day | long-range blocks, per pair-day |")
    print("|---|---|---|---|---|---|---|---|")
    for det in DETS:
        for sname in ("test", "ood"):
            for rate, tgt in (("day", 1), ("hour", 24)):
                b = res[sname][det][rate]
                fa = b["fa_per_pair_day"]
                bc = b["fa_per_pair_day_by_class"]
                print(f"| {NAME[det]} | {sname} | {tgt} | {fa['mean']:.2f} ({fa['ci95'][0]:.2f} to {fa['ci95'][1]:.2f}) "
                      f"| {b['fa_per_hour_in_blocks_with_driving']:.3f} | "
                      f"{b['fa_per_hour_in_blocks_without_driving']:.4f} | {bc.get('uwb', float('nan')):.2f} | "
                      f"{bc.get('long', float('nan')):.2f} |")
    print()


def paired(res, sname: str, rate: str) -> None:
    print("| Network minus | " + " | ".join(E.TYPES) + " |")
    print("|---|" + "---|" * len(E.TYPES))
    for base in ("chi2_step", "cusum", "logreg"):
        p = res[sname]["paired_delay_net_minus"][base][rate]
        print(f"| {NAME[base]} | " + " | ".join(
            f"{p[t]['median_diff_s']['mean']:+.1f} s ({p[t]['median_diff_s']['ci95'][0]:+.1f} to "
            f"{p[t]['median_diff_s']['ci95'][1]:+.1f}; n {p[t]['n_both_mean']:.0f})" for t in E.TYPES) + " |")
    print()


def runs() -> None:
    print("| # | change | parameters | window | epochs | val loss | val recall at 1/pair-day | at 1/pair-hour | "
          "drift | jump | wall |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in csv.DictReader(open(os.path.join(ROOT, "results", "E56_runs.csv"), encoding="utf-8")):
        bt = json.loads(r["val_recall_day_by_type"])
        print(f"| {r['iter']} (seed {r['seed']}) | {r['note']} | {r['n_params']} | {r['window_s']} s | {r['epochs']} "
              f"| {float(r['val_loss']):.4f} | {float(r['val_recall_day_macro']):.3f} | "
              f"{float(r['val_recall_hour_macro']):.3f} | {bt['drift']:.3f} | {bt['jump']:.3f} | "
              f"{float(r['wall_s']):.0f} s |")
    print()


def main_tables(res) -> None:
    for sname in ("test", "ood", "ood_recalibrated"):
        for rate in ("day", "hour"):
            print(f"### {sname}, threshold for 1 false alarm per pair-{rate}: recall / median delay\n")
            headline(res, sname, rate)
    for sname in ("test", "ood"):
        for cls in ("uwb", "long"):
            print(f"### {sname}, ranging class {cls}, 1 false alarm per pair-day: recall / median delay\n")
            headline(res, sname, "day", "events_by_class", cls)
    print("### test, details at 1 false alarm per pair-day\n")
    detail(res, "test", "day")
    print("### out of distribution, details at 1 false alarm per pair-day (thresholds as deployed)\n")
    detail(res, "ood", "day")
    print("### false alarms on fault-free blocks\n")
    fa_table(res)
    for sname in ("test", "ood"):
        print(f"### {sname}: paired delay difference on events both found, 1 false alarm per pair-day\n")
        paired(res, sname, "day")
    print("### runs\n")
    runs()


README = os.path.join(ROOT, "results", "E56_README.md")
BEGIN, END = "<!-- BEGIN GENERATED TABLES -->", "<!-- END GENERATED TABLES -->"


def write_into_readme(text: str) -> None:
    s = open(README, encoding="utf-8").read()
    i, j = s.index(BEGIN) + len(BEGIN), s.index(END)
    with open(README, "w", encoding="utf-8", newline="\n") as f:
        f.write(s[:i] + "\n\n" + text.strip() + "\n\n" + s[j:])


if __name__ == "__main__":
    import contextlib
    import io
    buf = io.StringIO()
    res = json.load(open(E.RESULT, encoding="utf-8"))
    with contextlib.redirect_stdout(buf):
        main_tables(res)
    if "--write" in sys.argv:
        write_into_readme(buf.getvalue())
        print("tables written into", README)
    else:
        print(buf.getvalue())


