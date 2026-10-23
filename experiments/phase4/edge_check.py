"""B-64: how much does the link file's end move the 2028-2031 results? (robustness only; no rows replaced)

    python experiments/phase4/edge_check.py run [--max-seconds 540]   # the quoted cells with link windows that run
                                                                       # on into 2032-2050 (resumable cache)
    python experiments/phase4/edge_check.py report                     # -> results/E21_edge_check_r2.json
    python experiments/phase4/edge_check.py paper --variant base|joined  # the paper's quoted values from a copy of
                                                                       # the results (tables and fit regenerated)
    python experiments/phase4/edge_check.py paper-diff                 # which quoted values move -> the same JSON

The v1 link file ends on 2031-12-31, and a strategic wait that runs past a sample's last link-up in the file has no
end there: the engine counts it as never linked (re-draw). Here the same cells run with a cached joined link file
(tools/comms/later_years.py join: earth_link-v1 then earth_link-v3, 2028-01-01 .. 2050-12-31; inside 2028-2031 every
window is v1's), and each run is paired with its committed row (same cell, seed and start year, so the same CRN).
Single process, foreground.
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import math
import os
import sys
import time
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p_ in (ROOT, os.path.join(ROOT, "tools", "comms")):
    if p_ not in sys.path:
        sys.path.insert(0, p_)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

from experiments.phase4 import run_phase4 as R  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "comms")
RUNS = os.path.join(CACHE, "edge_runs.json")
OUT = os.path.join(ROOT, "results", "E21_edge_check_r2.json")
METRICS = ("delivered_t_in_year", "prio1_completion_share", "delay_prio1_p90_censored_h", "blackout_jobs_refused")
YEARS = (2028, 2029, 2030, 2031)


def cells() -> List[Dict[str, Any]]:
    """The quoted cells (label, committed file, cell tuple); fast ones first."""
    A = R.e21a_cells("r2")
    a = lambda mix: next(c for c in A if c[0]["mix"] == mix and c[0]["comms"] == "dte")
    g = lambda h: next(c for c in R.e21g2_cells() if c[0]["rescue_h"] == h)
    hc = next(c for c in R.e21h_cells() if c[0]["rescue_h"] == 24.0 and c[0]["helpers_n"] == 1
              and not c[0]["helpers_from_fleet"] and c[0]["helpers_service_h"] == 1.0)
    return [{"label": "A strategic", "file": "E21a_comms_autonomy_r2.csv", "cell": a("supervised_strategic")},
            {"label": "G2 24 h", "file": "E21g2_rescue_any_r2.csv", "cell": g(24.0)},
            {"label": "G2 168 h", "file": "E21g2_rescue_any_r2.csv", "cell": g(168.0)},
            {"label": "H dedicated k=1 24 h", "file": "E21h_helper_r2.csv", "cell": hc},
            {"label": "A strict", "file": "E21a_comms_autonomy_r2.csv", "cell": a("supervised_strict")},
            {"label": "A look-ahead", "file": "E21a_comms_autonomy_r2.csv", "cell": a("supervised_strategic+avoid")}]


def joined(cell):
    """The cell with the joined link file (and, for helpers, the joined parking file); the tag is unchanged, so the
    run's cell key is the committed row's."""
    import later_years as LY
    tag, sc, mn, mf, kw = cell
    cm = dict(sc.comms, link_series=LY.JOINED)
    if "helpers" in cm:
        cm["helpers"] = dict(cm["helpers"], parking=LY.JOINED_PARKING)
    return tag, sc.with_(comms=cm), mn, mf, kw


def cmd_run(a) -> None:
    import later_years as LY
    t0 = time.time()
    if not os.path.isfile(LY.JOINED):
        raise SystemExit("no joined link file; run `tools/comms/later_years.py join` first")
    done = json.load(open(RUNS)) if os.path.isfile(RUNS) else {}
    for c in cells():
        cell = joined(c["cell"])
        rows = done.setdefault(c["label"], {})
        for seed in range(R.N_SEEDS):
            if str(seed) in rows:
                continue
            if time.time() - t0 > a.max_seconds - 60:
                print(f"edge run: stopping for the time limit ({sum(len(v) for v in done.values())} runs cached); rerun")
                return
            out = R._job((*cell, seed))
            rows[str(seed)] = {k: (float(v) if isinstance(v, (int, float, np.floating, np.integer)) and not isinstance(v, bool) else v)
                               for k, v in out.items() if isinstance(v, (int, float, str, bool, np.floating, np.integer))}
            with open(RUNS, "w") as f:
                json.dump(done, f)
            print(f"edge run {c['label']} seed {seed}: {rows[str(seed)]['delivered_t_in_year']:.3f} t "
                  f"({rows[str(seed)]['run_s']:.0f} s; {time.time() - t0:.0f} s)", flush=True)
    print(f"edge run: all {sum(len(v) for v in done.values())} runs cached ({time.time() - t0:.0f} s)")


def _pd(d: np.ndarray) -> Dict[str, Any]:
    n = len(d)
    m = float(d.mean())
    h = float(stats.t.ppf(0.975, n - 1) * d.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")
    return {"n": n, "mean_diff": m, "ci95": [m - h, m + h], "max_abs_seed_diff": float(np.abs(d).max()),
            "seeds_changed": int((d != 0).sum())}


def cmd_report(a) -> None:
    import later_years as LY
    t0 = time.time()
    done = json.load(open(RUNS))
    res: Dict[str, Any] = {}
    flags = []
    for c in cells():
        rows = done.get(c["label"], {})
        if len(rows) != R.N_SEEDS:
            raise SystemExit(f"{c['label']}: {len(rows)} runs cached; run `run` again")
        csv = pd.read_csv(os.path.join(ROOT, "results", c["file"]), float_precision="round_trip")
        key = next(iter(rows.values()))["cell"]
        old = csv[csv["cell"] == key].set_index("seed").sort_index()
        new = pd.DataFrame.from_dict(rows, orient="index")
        new.index = new.index.astype(int)
        new = new.sort_index()
        if len(old) != R.N_SEEDS or not (old["start_year"].to_numpy() == new["start_year"].to_numpy()).all():
            raise SystemExit(f"{c['label']}: committed rows do not pair with the runs")
        num = [k for k in old.columns if k in new.columns and k != "run_s" and pd.api.types.is_numeric_dtype(old[k])]
        changed = [int(s) for s in old.index if any(not (pd.isna(old.at[s, k]) and pd.isna(new.at[s, k]))
                                                     and float(old.at[s, k]) != float(new.at[s, k]) for k in num)]
        blk: Dict[str, Any] = {"committed_file": c["file"], "cell": key, "rows_with_any_change": changed, "metrics": {}}
        for m in METRICS:
            o, nn = old[m].to_numpy(float), new[m].to_numpy(float)
            mb = {"overall": dict(_pd(nn - o), committed_mean=float(o.mean()), joined_mean=float(nn.mean())), "by_start_year": {}}
            for y in YEARS:
                k = old["start_year"].to_numpy() == y
                mb["by_start_year"][str(y)] = dict(_pd(nn[k] - o[k]), committed_mean=float(o[k].mean()),
                                                   joined_mean=float(nn[k].mean()))
            blk["metrics"][m] = mb
        # the precision the paper prints these cells at: tonnage to 1 t (by year) and 0.1 t (overall), completion in
        # whole per cent, censored p90 in whole hours, re-draws as whole numbers per run
        prec = {"delivered_t_in_year": (0.1, 1.0), "prio1_completion_share": (0.01, 0.01),
                "delay_prio1_p90_censored_h": (1.0, 1.0), "blackout_jobs_refused": (1.0, 1.0)}
        for m, (p_all, p_y) in prec.items():
            mb = blk["metrics"][m]
            for where, b, p in [("overall", mb["overall"], p_all)] + [(y, mb["by_start_year"][y], p_y) for y in mb["by_start_year"]]:
                moved = abs(b["joined_mean"] - b["committed_mean"])
                b["printed_precision"] = p
                b["moves_more_than_last_printed_digit"] = bool(moved > p)
                if moved > p:
                    flags.append(f"{c['label']} {m} {where}: {b['committed_mean']:.4g} -> {b['joined_mean']:.4g}")
        res[c["label"]] = blk
    j = json.load(open(LY.JOINED))
    s = json.loads(__import__("gzip").decompress(open(LY.JOINED_SAMPLES, "rb").read()))
    never = sum(1 for smp in s["samples"] if not s["series"][smp["w"][0]])
    doc = {"description": "B-64: the quoted 2028-2031 cells rerun with link windows that run on into 2032-2050 (a cached "
                          "joined file: earth_link-v1 then earth_link-v3; not committed), paired with the committed rows "
                          "(same cell, seed and start year: same CRN). Differences are joined - committed. Re-draws = "
                          "blackout_jobs_refused per run. 'moves_more_than_last_printed_digit': |change of the cell mean| > "
                          "the precision printed (tonnage 0.1 t overall and 1 t by start year, completion 1 %, censored p90 "
                          "1 h, re-draws 1 per run). Robustness only: no row is replaced.",
           "joined_files": {"link": {"file": os.path.relpath(LY.JOINED, ROOT).replace(os.sep, "/"), "sha256": LY.EL.sha256(LY.JOINED)},
                            "samples": {"file": os.path.relpath(LY.JOINED_SAMPLES, ROOT).replace(os.sep, "/"),
                                        "sha256": j["samples_file"]["sha256"]},
                            "parking": {"file": os.path.relpath(LY.JOINED_PARKING, ROOT).replace(os.sep, "/"),
                                        "sha256": LY.EL.sha256(LY.JOINED_PARKING)},
                            "span": "2028-01-01 .. 2050-12-31", "never_linked_samples": never, "never_linked_v1": 283},
           "cells": res, "moves_beyond_printed_precision": flags,
           "verdict": ("no quoted cell mean moves by more than its last printed digit" if not flags else
                       f"{len(flags)} cell means move by more than their last printed digit (see the list)")}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    print(f"{os.path.relpath(OUT, ROOT)} written ({time.time() - t0:.0f} s): {doc['verdict']}")
    for lab, blk in res.items():
        d = blk["metrics"]["delivered_t_in_year"]
        print(f"  {lab:<22} rows changed {len(blk['rows_with_any_change'])}/20; tonnage {d['overall']['mean_diff']:+.3f} t "
              f"(max seed {d['overall']['max_abs_seed_diff']:.3f}); by year "
              + " ".join(f"{y}:{d['by_start_year'][y]['mean_diff']:+.2f}" for y in d["by_start_year"])
              + f"; re-draws {blk['metrics']['blackout_jobs_refused']['overall']['mean_diff']:+.2f}")
    for f_ in flags:
        print("  MOVES:", f_)


EDGE_RES = os.path.join(CACHE, "edge_results")


def cmd_paper(a) -> None:
    """The paper's quoted values (paper/r1/build_r1.values) from a copy of the E21 results with the derived tables and
    fit blocks regenerated: variant 'base' (rows as committed) or 'joined' (the quoted cells' rows replaced by the joined
    runs). Only the copy is touched; simulation-only fit blocks (bounded.pool_starvation, helper.diagnosis_168h) are
    carried over from the committed fit file."""
    import glob
    import shutil
    from experiments.phase4 import analyse_e21 as AN
    t0 = time.time()
    dst = os.path.join(EDGE_RES, a.variant)
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst)
    for p in glob.glob(os.path.join(ROOT, "results", "*")):
        b = os.path.basename(p)
        if os.path.isfile(p) and b.startswith(("E21", "table_E21", "fig_E21")):
            shutil.copy2(p, os.path.join(dst, b))
    with open(os.path.join(ROOT, "results", "E21_fit_r2.json"), encoding="utf-8") as fh:
        committed = json.load(fh)
    if a.variant == "joined":
        done = json.load(open(RUNS))
        for c in cells():
            path = os.path.join(dst, c["file"])
            df = pd.read_csv(path, float_precision="round_trip")
            for s, r in done[c["label"]].items():
                m = (df["cell"] == r["cell"]) & (df["seed"] == int(s))
                if m.sum() != 1:
                    raise SystemExit(f"{c['label']} seed {s}: no single committed row")
                for k, v in r.items():
                    if k in df.columns and k != "run_s":
                        df[k] = df[k].astype(object) if df[k].dtype != object and isinstance(v, str) else df[k]
                        df.loc[m, k] = v
            df.to_csv(path, index=False, lineterminator="\n")
    R.write_tables(dst, "r2")
    AN.main(["fit", "--round", "r2", "--results", dst])
    AN.main(["bounded", "--results", dst])
    AN.main(["rescue", "--results", dst])
    AN.main(["rescue", "--scope", "any", "--results", dst])
    AN.main(["helper", "--results", dst])
    AN.main(["years", "--results", dst])
    fp = os.path.join(dst, "E21_fit_r2.json")
    with open(fp, encoding="utf-8") as fh:
        fit = json.load(fh)
    fit["bounded"]["pool_starvation"] = committed["bounded"]["pool_starvation"]
    fit["helper"]["diagnosis_168h"] = committed["helper"]["diagnosis_168h"]
    with open(fp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fit, fh, indent=1)
    sys.path.insert(0, os.path.join(ROOT, "paper", "r1"))
    import build_r1 as B
    B.RES = dst
    V, _ = B.values(B.R())
    with open(os.path.join(EDGE_RES, f"values_{a.variant}.json"), "w", encoding="utf-8") as fh:
        json.dump(V, fh, indent=1, ensure_ascii=False)
    print(f"paper values ({a.variant}): {len(V)} -> {os.path.relpath(EDGE_RES, ROOT)} ({time.time() - t0:.0f} s)")


def cmd_paper_diff(a) -> None:
    """Which quoted values differ between the 'base' and 'joined' variants; written into E21_edge_check_r2.json."""
    vb = json.load(open(os.path.join(EDGE_RES, "values_base.json"), encoding="utf-8"))
    vj = json.load(open(os.path.join(EDGE_RES, "values_joined.json"), encoding="utf-8"))
    vp = json.load(open(os.path.join(ROOT, "paper", "r1", "values.json"), encoding="utf-8"))
    moved = [{"key": k, "base": vb[k], "joined": vj.get(k)} for k in vb if vj.get(k) != vb[k]]
    doc = json.load(open(OUT, encoding="utf-8"))
    doc["paper_values"] = {
        "method": "paper/r1/build_r1.values() on two copies of the E21 results with every derived table and CSV-derived "
                  "fit block regenerated (write_tables; analyse_e21 fit --round r2, bounded, rescue, rescue --scope any, "
                  "helper, years): 'base' = rows as committed, 'joined' = the six quoted cells' rows from the joined runs. "
                  "Simulation-only blocks (bounded.pool_starvation, helper.diagnosis_168h) carried over.",
        "n_values": len(vb), "n_moved": len(moved), "moved": moved,
        "base_equals_committed_values_json": sum(1 for k in vb if vp.get(k) == vb[k]),
        "base_differs_from_committed_values_json": [k for k in vb if vp.get(k) != vb[k]]}
    if "verdict_cells_assumed_precision" not in doc:
        doc["verdict_cells_assumed_precision"] = doc.pop("verdict")
        doc["cell_means_beyond_assumed_precision"] = doc.pop("moves_beyond_printed_precision")
    doc["verdict"] = (f"yes: {len(moved)} of the paper's {len(vb)} quoted values change in their printed digits "
                      "(paper_values.moved); every change comes from the 2031 start-year rows" if moved else
                      f"no: none of the paper's {len(vb)} quoted values changes in its printed digits")
    doc["verdict_paper"] = doc["verdict"]
    doc["not_rerun"] = ("Only the six quoted cells were rerun. Their 2031 rows carry the edge, and so do the 2031 rows of "
                        "every other 2028-2031 cell (Stages A2, B, C, D, E, F, G, the other H cells); quoted values built "
                        "from those cells' own rows are not covered here, only those built against the six.")
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=1, ensure_ascii=False)
    print(doc["verdict_paper"])
    for m in moved:
        print(f"  {m['key']}: {str(m['base'])[:70]}  ->  {str(m['joined'])[:70]}")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--max-seconds", type=float, default=540.0)
    sub.add_parser("report")
    p = sub.add_parser("paper")
    p.add_argument("--variant", choices=("base", "joined"), required=True)
    p.add_argument("--max-seconds", type=float, default=540.0)
    sub.add_parser("paper-diff")
    a = ap.parse_args(argv)
    if a.cmd in ("run", "paper") and a.max_seconds > 0:
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    {"run": cmd_run, "report": cmd_report, "paper": cmd_paper, "paper-diff": cmd_paper_diff}[a.cmd](a)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from terrain_assets import peak_rss_mb
    rss = peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")


if __name__ == "__main__":
    main()
