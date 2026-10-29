"""Paired analysis of E43 for paper P2 (LEAD): the tables build_p2.py reads. BACKEND's analyse_e43.py writes the
report summary (results/E43_summary.json); this script writes the paper's tables and the PREREG H8 decision.

    python experiments/phase5/analyse_e43_pairs.py   # -> results/table_E43_cells.csv, results/table_E43_pairs.csv,
                                                      #    results/E43_fit.json (works on whatever rows exist; prints n)

Design (run_phase5.e43_cells). Pooled dispatch (O_ORACLE) in every cell, so only the road layer differs:
  mode in {none (no road layer, no landing closure), atc (one shared reservation table), uncoordinated (each owner
  sees only its own reservations; a conflict with another owner stops both until Earth settles it by hand)}
  x fleet density m in {1, 2, 4, 8} (fleet and demand both x m at 30 % load) x start year (none and atc never wait
  for Earth, so they run 2028 only; uncoordinated runs 2028 and 2038) x seeds (30 at 1x and 2x over a year; 10 at
  4x over 90 days and 8x over 60 days, see E43-design.json). Sweeps at 1x, 2028: single-lane share (0, 0.05, 0.40;
  ASSUMED factor, default 0.15), passing-bay spacing (0.5, 2 km; default 1 km), and the strict comms-loss rule r7.

Pairs: the same seed in two cells (common random numbers). "none" and "atc" do not depend on the start year, so an
uncoordinated run of 2038 pairs with the none/atc run of the same seed. Paired mean difference with a percentile
bootstrap 95 % CI (20,000 resamples, seed 43), the 90 % CI for one-sided rules, and the ratio to the baseline's
mean with its own bootstrap CI.

Decision rule (PREREG H8): at today's fleet density (1x) the rules add less than 5 % to the delay per delivery:
supported if the one-sided 95 % upper bound of (atc - none) / mean(none) is below 0.05, on the primary outcome
delay_mean_h (mean delay per delivered item). "At 4-8x density the cost rises" is reported per density, exploratory.
Deadlocks are counted (road_deadlocks) and must be zero for the exit-bay construction to be reported as holding.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES = os.path.join(ROOT, "results")
sys.path.insert(0, ROOT)
from experiments.phase5 import run_phase5 as RP  # noqa: E402

PRIMARY = "delay_mean_h"
METRICS = ["delay_mean_h", "delay_p90_h", "delay_mass_weighted_h", "atc_urgent_wait_mean_cens_h", "delivered_items",
           "delivered_kg", "operator_hours", "road_wait_h", "road_apron_wait_h", "road_eva_slow_h", "road_conflicts",
           "road_hand_conflicts", "road_hand_wait_h", "road_other_stop_h", "road_deadlocks", "road_traversals",
           "road_single_km", "road_r7_fallbacks", "road_r7_unlinked_jobs", "road_wait_h_owner_A",
           "road_wait_h_owner_B", "road_wait_h_owner_C", "plume_standdowns", "standdown_vehicle_h", "run_s",
           "horizon_days"]
N_BOOT, SEED, MARGIN_H8 = 20000, 43, 0.05


def load() -> pd.DataFrame:
    files = RP.run_files("E43")
    if not files:
        raise SystemExit("no E43 run files")
    d = pd.concat([pd.read_csv(f, float_precision="round_trip") for f in files], ignore_index=True)
    dup = int(d.duplicated(["cell", "seed", "start_year"]).sum())
    if dup:
        print(f"note: {dup} duplicate keys dropped (a rerun in flight?)")
        d = d.drop_duplicates(["cell", "seed", "start_year"], keep="last")
    if "label" not in d:
        d["label"] = d["cell"].str.extract(r"label=([^;]+)")[0]
    if "horizon_days" not in d:
        d["horizon_days"] = d["horizon_h"] / 24.0
    return d


def paired(a: pd.DataFrame, b: pd.DataFrame, metric: str, rng: np.random.Generator) -> Dict[str, Any]:
    """a - b on the same seeds; b is the baseline."""
    m = a[["seed", metric]].merge(b[["seed", metric]], on="seed", suffixes=("_a", "_b")).dropna()
    n = len(m)
    out: Dict[str, Any] = {"n": n}
    if n == 0:
        return dict(out, mean=np.nan, lo=np.nan, hi=np.nan, lo90=np.nan, hi90=np.nan, p=np.nan, b_mean=np.nan,
                    share_of_b=np.nan, ratio_lo=np.nan, ratio_hi=np.nan, ratio_hi95=np.nan)
    x, y = m[f"{metric}_a"].to_numpy(float), m[f"{metric}_b"].to_numpy(float)
    d = x - y
    idx = rng.integers(0, n, size=(N_BOOT, n))
    bd = d[idx].mean(axis=1)
    by = y[idx].mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        br = np.where(by != 0, bd / by, np.nan)
    q = lambda v, p: float(np.nanpercentile(v, p))
    p = float(2 * min((bd <= 0).mean(), (bd >= 0).mean()))       # two-sided bootstrap p (floor 1/N_BOOT)
    return dict(out, mean=float(d.mean()), lo=q(bd, 2.5), hi=q(bd, 97.5), lo90=q(bd, 5), hi90=q(bd, 95),
                p=max(p, 1.0 / N_BOOT), b_mean=float(y.mean()),
                share_of_b=float(d.mean() / y.mean()) if y.mean() != 0 else np.nan,
                ratio_lo=q(br, 2.5), ratio_hi=q(br, 97.5), ratio_hi95=q(br, 95))


def main() -> None:
    t0 = time.time()
    d = load()
    rng = np.random.default_rng(SEED)
    design = json.load(open(RP.E43_DESIGN, encoding="utf-8")) if os.path.exists(RP.E43_DESIGN) else {}
    print(f"E43: {len(d)} rows, {d['label'].nunique()} labels")

    rows = []
    for (label, year), g in d.groupby(["label", "start_year"], sort=False):
        row = {"label": label, "start_year": int(year), "mode": g["mode"].iloc[0], "density": int(g["density"].iloc[0]),
               "n": len(g), "seeds": ",".join(str(s) for s in sorted(g["seed"].astype(int)))}
        for mtr in METRICS:
            row[mtr] = float(g[mtr].mean()) if mtr in g and g[mtr].notna().any() else np.nan
        row["road_deadlocks_total"] = float(g["road_deadlocks"].sum()) if "road_deadlocks" in g else np.nan
        rows.append(row)
    cells = pd.DataFrame(rows)
    cells.to_csv(os.path.join(RES, "table_E43_cells.csv"), index=False)

    def sub(label, year=None):
        g = d[d["label"] == label]
        return g if year is None else g[g["start_year"] == year]

    pairs: List[Dict[str, Any]] = []

    def add(comparison, a, b, metrics=(PRIMARY,), **tags):
        for mtr in metrics:
            if mtr not in a or mtr not in b:
                continue
            r = paired(a, b, mtr, rng)
            pairs.append(dict(comparison=comparison, metric=mtr, **tags, **r))
            if mtr == PRIMARY:
                print(f"  {comparison:48s} n={r['n']:3d} {r['mean']:+9.3f} [{r['lo']:+.3f}, {r['hi']:+.3f}] "
                      f"ratio {r['share_of_b']:+.3f} (95 % upper {r['ratio_hi95']:+.3f})")

    SEC = (PRIMARY, "delay_p90_h", "delay_mass_weighted_h", "atc_urgent_wait_mean_cens_h", "delivered_items",
           "operator_hours", "road_wait_h", "road_hand_wait_h")
    densities = sorted(int(x) for x in d["density"].unique())
    years = sorted(int(y) for y in d["start_year"].unique())
    H8: Dict[str, Any] = {}
    for m in densities:
        none, atc = sub(f"none x{m}"), sub(f"atc x{m}")
        add(f"H8: atc - none, x{m}", atc, none, SEC, density=m, start_year=2028)
        r = next((p for p in pairs if p["comparison"] == f"H8: atc - none, x{m}" and p["metric"] == PRIMARY), None)
        if r and r["n"] > 0:
            H8[str(m)] = {"test": r, "supported": bool(np.isfinite(r["ratio_hi95"]) and r["ratio_hi95"] < MARGIN_H8),
                          "margin": MARGIN_H8, "confirmatory": m == 1}
        for y in years:
            unc = sub(f"uncoordinated x{m}", y)
            if len(unc):
                add(f"uncoordinated - none, x{m}, {y}", unc, none, SEC, density=m, start_year=y)
                add(f"uncoordinated - atc, x{m}, {y}", unc, atc, SEC, density=m, start_year=y)
    none1, atc1 = sub("none x1"), sub("atc x1")
    for lab in sorted(l for l in d["label"].unique() if " share " in l or " bay " in l or l.endswith(" r7")):
        add(f"{lab} - none x1", sub(lab), none1, SEC, density=1, start_year=2028)
        if lab.startswith("atc"):
            add(f"{lab} - atc x1", sub(lab), atc1, SEC, density=1, start_year=2028)
    pd.DataFrame(pairs).to_csv(os.path.join(RES, "table_E43_pairs.csv"), index=False)

    owners = {}
    for m in densities:
        g = sub(f"atc x{m}")
        if len(g):
            owners[str(m)] = {o: float(g[f"road_wait_h_owner_{o}"].mean()) for o in "ABC"
                              if f"road_wait_h_owner_{o}" in g}
    deadlocks = {str(m): float(d[d["density"] == m]["road_deadlocks"].fillna(0).sum()) for m in densities}
    horizons = {str(m): sorted(float(h) for h in d[d["density"] == m]["horizon_days"].unique()) for m in densities}
    counts = {lab: int(n) for lab, n in d.groupby("label", sort=False).size().items()}
    fit = {"n_rows": int(len(d)), "labels": counts, "densities": densities, "years": years, "horizons_days": horizons,
           "primary": PRIMARY, "n_boot": N_BOOT, "seed": SEED,
           "H8": H8, "deadlocks_total_by_density": deadlocks, "owner_bay_wait_h_atc": owners,
           "run_s_mean_by_label": {lab: float(v) for lab, v in d.groupby("label", sort=False)["run_s"].mean().items()},
           "design": {k: design.get(k) for k in ("load_multiplier_30pct", "plume_R5", "single_share_flag",
                                                   "design_changes")},
           "elapsed_s": round(time.time() - t0, 1)}
    with open(os.path.join(RES, "E43_fit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(fit, f, indent=1)
        f.write("\n")
    print(json.dumps({"H8": {m: {"supported": v["supported"], "ratio": round(v["test"]["share_of_b"], 4),
                                 "upper95": round(v["test"]["ratio_hi95"], 4)} for m, v in H8.items()},
                      "deadlocks": deadlocks}, indent=1))


if __name__ == "__main__":
    main()
