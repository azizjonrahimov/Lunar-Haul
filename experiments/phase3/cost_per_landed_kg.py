"""Cost per landed kilogram (B-16 metric) for the Phase-2 four-vehicle fleet and the Phase-3 default fleet.

    .venv\\Scripts\\python experiments\\phase3\\cost_per_landed_kg.py [--seeds 30]

Cells: (P2, 4 vehicles) = the library scenario P2-4-vehicles with 3 operators, i.e. the E10 base scenario of
experiments/run_all.py; (P3, default) = lunarsim.phases.P3 as in E1. Four mechanisms (run_all.MECHS), seeds 0..29,
single process (a few minutes). Writes results/table_cost_landed_kg.csv with, per (phase, fleet, mechanism):
  n                               seeds
  delivered_nonbulk_kg_mean       mean landed cargo delivered per year (bulk and return flows excluded)
  cost_musd_mean                  mean annual fleet + operator cost (M USD)
  cost_per_landed_kg_usd          exact metric: ratio of means, 1e6 * mean(cost) / mean(delivered_nonbulk_kg)
  ci_lo, ci_hi                    percentile seed-bootstrap 95 % interval of that ratio (N_BOOT resamples of the seeds,
                                  numpy default_rng(0), as in fit_law.py)
  v2_approx_usd                   the v2 paper's approximation, 1e6 * mean(cost) / mean(delivered_kg - bulk_kg)
  per_seed_ratio_mean             mean of the per-year ratios, for the record only (unstable: years with one landing)
"""
import argparse, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import numpy as np
import pandas as pd

from lunarsim import run
from lunarsim.config import library
from lunarsim.phases import PHASES
from experiments.run_all import MECHS
from experiments.phase3.fit_law import N_BOOT

OUT = os.path.join(ROOT, "results", "table_cost_landed_kg.csv")


def cells():
    return [("P2", "4 vehicles", library()["P2-4-vehicles"].with_(n_operators=3)),
            ("P3", "default", PHASES["P3"])]


def ratio_ci(cost, kg, B=N_BOOT, seed=0):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(cost), (B, len(cost)))
    r = 1e6 * cost[idx].mean(axis=1) / kg[idx].mean(axis=1)
    return np.percentile(r, [2.5, 97.5])


def summarise(df):
    rows = []
    for (ph, fl, mn), g in df.groupby(["phase", "fleet", "mechanism"], sort=False):
        g = g.sort_values("seed")
        cost = (g.fleet_cost_musd + g.operator_cost_musd).to_numpy()
        kg = g.delivered_nonbulk_kg.to_numpy()
        lo, hi = ratio_ci(cost, kg)
        rows.append({"phase": ph, "fleet": fl, "mechanism": mn, "n": len(g),
                     "delivered_nonbulk_kg_mean": round(kg.mean(), 1), "cost_musd_mean": round(cost.mean(), 4),
                     "cost_per_landed_kg_usd": round(1e6 * cost.mean() / kg.mean(), 1),
                     "ci_lo": round(lo, 1), "ci_hi": round(hi, 1),
                     "v2_approx_usd": round(1e6 * cost.mean() / (g.delivered_kg - g.bulk_kg).mean(), 1),
                     "per_seed_ratio_mean": round(float(np.mean(1e6 * cost / np.maximum(kg, 1e-9))), 1)})
    return pd.DataFrame(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--seeds", type=int, default=30)
    p.add_argument("--out", default=OUT)
    a = p.parse_args(argv)
    t0, recs = time.time(), []
    for ph, fl, sc in cells():
        for mn, (mf, kw) in MECHS.items():
            for s in range(a.seeds):
                r = run(sc, mf, seed=s, **kw)
                r.update({"phase": ph, "fleet": fl, "mechanism": mn, "seed": s})
                recs.append(r)
            print(f"  {ph} {fl} {mn}: {a.seeds} seeds, {time.time() - t0:.0f} s", flush=True)
    tab = summarise(pd.DataFrame(recs))
    tab.to_csv(a.out, index=False)
    print(tab.to_string(index=False))
    print(f"wrote {a.out} in {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
