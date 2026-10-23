"""E21 analysis (B-43): paired effects, the delay-coverage law, delay-based break-evens, operator compression and the
throughput bound, from the E21 replications (results/E21a_comms_autonomy.csv, E21b_breakeven.csv, and
E21c_pads_criterion.csv when present).

    python experiments/phase4/analyse_e21.py demand [--seeds 20] [--max-seconds 540]   # -> results/E21_demand_by_dest.csv
    python experiments/phase4/analyse_e21.py fit [--boot 400]                          # -> the tables below
    python experiments/phase4/analyse_e21.py fit --round r2 [--boot 2000]              # round 2: reads/writes *_r2
    python experiments/phase4/analyse_e21.py rounds                                    # round-2 rows = round-1 rows

Round 2 (referee round 1) also writes table_E21_cells_r2.csv (cell means, Student-t intervals, medians, completion
next to every p90), table_E21_years_r2.csv (key cells by start year, 2028-style flags) and, in E21_fit_r2.json, the
throughput split (bulk / landed / return), year-blocked intervals for the primary comparisons, the full-relay = always
check per mix and the break-even with every bootstrap draw kept.

Writes results/E21_fit.json, results/table_E21_effects.csv, results/table_E21_breakeven_delay.csv and the figure-ready
results/fig_E21_delay_coverage.csv and results/fig_E21_operator_demand.csv.

Method:
  paired effects   every cell runs the same seeds (common random numbers: demand, landings and operations streams,
                   and the comms start year 2028 + seed mod 4), so an effect is the mean of the per-seed differences
                   cell - reference over the seeds where both are finite, with a Student-t 95 % interval (n - 1 dof).
  law              per autonomy mix, urgent p90 (and mean) delay against relay coverage p on stage A (p = 0 is DTE
                   only), fitted to the cell means in log space (the delay spans a factor ~30) with three forms,
                   hyperbolic a + b / (p + c), exponential a + b exp(-k p) and power b (p + c)^-g; the form with the
                   lower 5-fold cross-validated RMSE of log delay (folds of seeds, the held-out fold's cell means
                   scored) is kept. Parameters, f(1) and the coverage reaching 2x and 1.5x f(1) carry percentile
                   bootstrap intervals over seeds (seeds resampled with replacement); the same coverages are also read
                   model-free off the measured cells (target = ratio x the p = 1 cell).
  break-even       at p = 0.5 (stage B): the coverage on the strict curve whose urgent p90 equals an option's measured
                   p90. The curve is model-free (the measured supervised-strict cells: non-increasing envelope,
                   log-linear between grid points), because no smooth form fits the slow decline between p = 0.2 and 1
                   well enough to invert there; the fitted law's answer is kept as p_equiv_law. The same seed draw for
                   curve and option in each bootstrap resample; "beyond full coverage" (inf) when the option beats the
                   p = 1 cell. One LTV = the engine's capital per year (VEHICLE_CLASSES['LTV'].unit_cost_musd /
                   life_years).
  operators        linked operator demand: peak = operator_peak_demand (largest hourly mean of concurrent linked
                   demand), mean = operator_hours / horizon (operator_hours counts linked demand-hours only); a cell
                   is flagged when its peak exceeds n_operators in any seed. The compression is read against relay
                   coverage 1.0 (operations identical to 'always', but demand booked the linked modes' way).
  throughput       the demand model's cargo by destination (each seed's own demand stream, from the supervised-strict
                   "always" run) against the Earth-link file: destinations that never see Earth under DTE cannot be
                   served by a rover that needs a link, so the cargo ready for them in the year bounds the DTE loss.
"""
from __future__ import annotations

import argparse
import faulthandler
import json
import math
import os
import sys
import time
import warnings
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore", category=RuntimeWarning)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402
from scipy.optimize import least_squares  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
STAGE_FILES = ("E21a_comms_autonomy.csv", "E21b_breakeven.csv", "E21c_pads_criterion.csv", "E21a2_operators.csv")
DEMAND_FILE = "E21_demand_by_dest.csv"
METRICS = ["delivered_t_in_year", "delay_prio1_p90_h", "delay_prio1_mean_h", "sl24_prio1", "blackout_wait_vehicle_h",
           "operator_peak_demand"]
LAW_METRICS = ["delay_prio1_p90_h", "delay_prio1_mean_h"]
HORIZON_H = 8760.0
B_P = 0.5                       # stage B relay coverage
N_BOOT = 400
LINK_FILE = os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1.json")


# ---------------------------------------------------------------------------------------------------------
# loading and selection
# ---------------------------------------------------------------------------------------------------------
def load(results: str = RESULTS) -> pd.DataFrame:
    parts = [pd.read_csv(os.path.join(results, f)) for f in STAGE_FILES if os.path.exists(os.path.join(results, f))]
    if not parts:
        raise SystemExit("no E21 replication files in " + results)
    df = pd.concat(parts, ignore_index=True, sort=False)
    return prepare(df)


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Adds p (relay coverage; 0 = DTE only, NaN = always) and the operator mean demand."""
    df = df.copy()
    df["p"] = np.where(df["comms"] == "dte", 0.0, np.where(df["comms"] == "dte+relay", df["coverage"], np.nan))
    if "operator_hours" in df:
        df["operator_mean_demand"] = df["operator_hours"] / HORIZON_H
    for c, v in (("extra_rovers", 0), ("mast", "none"), ("pad_standoff_km", 1.0), ("criterion", "any_part"),
                 ("defer_wait_h", 24.0)):
        if c not in df:
            df[c] = v
    df["defer_wait_h"] = pd.to_numeric(df["defer_wait_h"].replace({"inf": np.inf}), errors="coerce")
    if "operator_wait_vehicle_h" in df:          # B-45: the lenient rule never makes a vehicle wait for an operator
        lenient = df["stage"] != "A2"
        df.loc[lenient, "operator_wait_vehicle_h"] = df.loc[lenient, "operator_wait_vehicle_h"].fillna(0.0)
    return df


def select(df: pd.DataFrame, **kw) -> pd.DataFrame:
    m = np.ones(len(df), bool)
    for k, v in kw.items():
        col = df[k]
        if isinstance(v, float) and math.isnan(v):
            m &= col.isna().to_numpy()
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            m &= np.isclose(pd.to_numeric(col, errors="coerce").to_numpy(float), float(v), rtol=0, atol=1e-9)
        else:
            m &= (col == v).to_numpy()
    return df[m]


# ---------------------------------------------------------------------------------------------------------
# 1. paired effects
# ---------------------------------------------------------------------------------------------------------
def paired(ref: pd.DataFrame, cell: pd.DataFrame, metric: str) -> Dict[str, float]:
    """Mean per-seed difference cell - ref and its Student-t 95 % interval over the seeds where both are finite."""
    a = ref.drop_duplicates("seed").set_index("seed")[metric]
    b = cell.drop_duplicates("seed").set_index("seed")[metric]
    j = pd.concat([a.rename("ref"), b.rename("cell")], axis=1, join="inner").dropna()
    n = len(j)
    out = {"n": n, "ref_mean": float(j["ref"].mean()) if n else np.nan, "cell_mean": float(j["cell"].mean()) if n else np.nan}
    if n < 2:
        return {**out, "diff": np.nan, "ci_lo": np.nan, "ci_hi": np.nan, "rel_pct": np.nan}
    d = (j["cell"] - j["ref"]).to_numpy(float)
    m, h = float(d.mean()), float(stats.t.ppf(0.975, n - 1) * d.std(ddof=1) / math.sqrt(n))
    rel = 100.0 * m / out["ref_mean"] if out["ref_mean"] else np.nan
    return {**out, "diff": m, "ci_lo": m - h, "ci_hi": m + h, "rel_pct": rel, **robust_stats(j["ref"], j["cell"])}


def robust_stats(ref: pd.Series, cell: pd.Series) -> Dict[str, float]:
    """Medians, the paired log-ratio (geometric-mean ratio cell / ref, t interval on the log scale; only when every
    pair is positive) and the Wilcoxon signed-rank p of the differences (zeros dropped)."""
    r, c = ref.to_numpy(float), cell.to_numpy(float)
    d = c - r
    out = {"ref_median": float(np.median(r)), "cell_median": float(np.median(c)), "median_diff": float(np.median(d)),
           "n_increase": int((d > 0).sum()), "gm_ratio": np.nan, "gm_ratio_lo": np.nan, "gm_ratio_hi": np.nan,
           "wilcoxon_p": np.nan}
    n = len(d)
    if n >= 2 and np.all(r > 0) and np.all(c > 0):
        lr = np.log(c / r)
        h = stats.t.ppf(0.975, n - 1) * lr.std(ddof=1) / math.sqrt(n)
        out.update(gm_ratio=float(np.exp(lr.mean())), gm_ratio_lo=float(np.exp(lr.mean() - h)),
                   gm_ratio_hi=float(np.exp(lr.mean() + h)))
    if n >= 2 and np.any(d != 0):
        try:
            out["wilcoxon_p"] = float(stats.wilcoxon(d, zero_method="wilcox").pvalue)
        except ValueError:
            pass
    return out


def _rows(family: str, ref_label: str, cell_label: str, ctx: Dict[str, Any], ref: pd.DataFrame, cell: pd.DataFrame,
          metrics: Sequence[str]) -> List[Dict[str, Any]]:
    out = []
    if ref.empty or cell.empty:
        return out
    for m in metrics:
        if m not in ref or m not in cell:
            continue
        r = paired(ref, cell, m)
        out.append({"family": family, **ctx, "reference": ref_label, "cell": cell_label, "metric": m, **r,
                    "ci_excludes_0": bool(np.isfinite(r["ci_lo"]) and (r["ci_lo"] > 0 or r["ci_hi"] < 0))})
    return out


def _plabel(p) -> str:
    return "always" if p is None or (isinstance(p, float) and math.isnan(p)) else ("DTE" if p == 0 else f"relay {p:g}")


def effects(df: pd.DataFrame, metrics: Sequence[str] = METRICS) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    a = df[df["stage"] == "A"]
    levels = sorted(a["p"].dropna().unique())
    for mix in sorted(a["mix"].unique()):
        alw = select(a, comms="always", mix=mix)
        for p in levels:
            cell = select(a, p=float(p), mix=mix)
            fam = "dte_vs_always" if p == 0 else "relay_vs_always"
            rows += _rows(fam, "always", _plabel(p), {"stage": "A", "mix": mix, "p": p}, alw, cell, metrics)
    for mix in ("supervised_strategic", "supervised_strategic+avoid"):
        for p in [np.nan] + list(levels):
            ref = select(a, p=float(p), mix="supervised_strict")
            cell = select(a, p=float(p), mix=mix)
            rows += _rows("policy_vs_strict", "supervised strict", mix.replace("_", " "),
                          {"stage": "A", "mix": mix, "p": p}, ref, cell, metrics)
    b = df[df["stage"] == "B"]
    for p in sorted(b["p"].dropna().unique()):
        for pol in sorted(b["policy"].unique()):
            base = select(b, p=float(p), policy=pol, extra_rovers=0, mast="none")
            ctx = {"stage": "B", "mix": "supervised", "policy": pol, "p": p}
            for n in sorted(x for x in b["extra_rovers"].unique() if x > 0):
                cell = select(b, p=float(p), policy=pol, extra_rovers=int(n), mast="none")
                rows += _rows("rovers_vs_0", "+0 rovers", f"+{int(n)} rovers", {**ctx, "extra_rovers": int(n)},
                              base, cell, metrics)
            for mast in sorted(x for x in b["mast"].unique() if x != "none"):
                cell = select(b, p=float(p), policy=pol, extra_rovers=0, mast=mast)
                rows += _rows("mast_vs_none", "no mast", mast, {**ctx, "mast": mast}, base, cell, metrics)
            for pol2 in sorted(x for x in b["policy"].unique() if x != "strict"):      # round 2: the policies in B
                if pol != "strict":
                    continue
                for n in sorted(b["extra_rovers"].unique()):
                    for mast in sorted(b["mast"].unique()):
                        ref = select(b, p=float(p), policy="strict", extra_rovers=int(n), mast=mast)
                        cell = select(b, p=float(p), policy=pol2, extra_rovers=int(n), mast=mast)
                        rows += _rows("b_policy_vs_strict", "strict", pol2,
                                      {"stage": "B", "mix": "supervised", "policy": pol2, "p": p, "extra_rovers": int(n),
                                       "mast": mast}, ref, cell, metrics)
    e = df[df["stage"] == "E"] if "sensitivity" in df else None             # round 2: sensitivity vs the Stage A twin
    for (sens, mix, p), g in (e.groupby(["sensitivity", "mix", e["p"].fillna(-1.0)]) if e is not None and len(e) else ()):
        p = np.nan if p < 0 else p
        comms = g["comms"].iloc[0]
        ref = select(a, comms=comms, mix=mix) if comms == "always" else select(a, p=float(p), mix=mix)
        rows += _rows("sensitivity_vs_stage_a", "Stage A twin", sens, {"stage": "E", "mix": mix, "p": p,
                      "sensitivity": sens}, ref, g, metrics)
    a2 = df[df["stage"] == "A2"]                 # B-45: strict operators vs the Stage A twin (same seeds and years)
    for (mix, p), g in a2.groupby(["mix", a2["p"].fillna(-1.0)]):
        p = np.nan if p < 0 else p
        ref = select(a, p=float(p), mix=mix)
        rows += _rows("strict_vs_lenient", "lenient operators", "strict operators", {"stage": "A2", "mix": mix, "p": p},
                      ref, g, list(metrics) + ["operator_wait_vehicle_h"])
    c = df[df["stage"] == "C"]
    if not c.empty:
        for (comms, mix), g in c.groupby(["comms", "mix"]):
            p = g["p"].iloc[0]
            ctx0 = {"stage": "C", "mix": mix, "p": p}
            dflt = g[np.isclose(g["defer_wait_h"], 24.0)]
            for d in sorted(dflt["pad_standoff_km"].unique()):
                ref = select(dflt, pad_standoff_km=float(d), criterion="any_part")
                for crit in sorted(x for x in dflt["criterion"].unique() if x != "any_part"):
                    rows += _rows("criterion_vs_any_part", "any part of the disc", crit,
                                  {**ctx0, "pad_standoff_km": d, "criterion": crit}, ref,
                                  select(dflt, pad_standoff_km=float(d), criterion=crit), metrics)
            for crit in sorted(dflt["criterion"].unique()):
                ref = select(dflt, pad_standoff_km=1.0, criterion=crit)
                for d in sorted(x for x in dflt["pad_standoff_km"].unique() if x != 1.0):
                    rows += _rows("pads_vs_1km", "pads 1 km", f"pads {d:g} km", {**ctx0, "pad_standoff_km": d, "criterion": crit},
                                  ref, select(dflt, pad_standoff_km=float(d), criterion=crit), metrics)
            ref = select(dflt, pad_standoff_km=1.0, criterion="any_part")
            for dw in sorted(x for x in g["defer_wait_h"].unique() if not np.isclose(x, 24.0)):
                cell = g[np.isclose(g["defer_wait_h"], dw) | (np.isinf(dw) & np.isinf(g["defer_wait_h"]))]
                rows += _rows("defer_vs_24h", "defer after 24 h", "never defer" if np.isinf(dw) else f"defer after {dw:g} h",
                              {**ctx0, "defer_wait_h": dw}, ref, cell, metrics)
    cols = ["family", "stage", "mix", "policy", "p", "extra_rovers", "mast", "pad_standoff_km", "criterion", "defer_wait_h",
            "sensitivity", "reference", "cell", "metric", "n", "ref_mean", "cell_mean", "diff", "ci_lo", "ci_hi", "rel_pct",
            "ci_excludes_0", "ref_median", "cell_median", "median_diff", "n_increase", "gm_ratio", "gm_ratio_lo",
            "gm_ratio_hi", "wilcoxon_p"]
    return pd.DataFrame(rows).reindex(columns=cols)


# ---------------------------------------------------------------------------------------------------------
# 2. the delay-coverage law
# ---------------------------------------------------------------------------------------------------------
def _hyp(p, a, b, c):
    return a + b / (p + c)


def _exp(p, a, b, k):
    return a + b * np.exp(-k * p)


def _pow(p, b, c, g):
    return b * (p + c) ** (-g)


FORMS: Dict[str, Tuple[Callable, Tuple[str, str, str]]] = {"hyperbolic": (_hyp, ("a", "b", "c")),
                                                         "exponential": (_exp, ("a", "b", "k")),
                                                         "power": (_pow, ("b", "c", "g"))}
CV_FOLDS = 5


def fit_form(form: str, p: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Least squares of log y on log f(p), a few starts; a, b >= 0, c, k > 0, power exponent g >= 0."""
    f, _ = FORMS[form]
    ok = np.isfinite(y) & (y > 0)
    p, y = np.asarray(p, float)[ok], np.asarray(y, float)[ok]
    ly = np.log(y)
    lo_y, hi_y = float(y[np.argmax(p)]), float(y[np.argmin(p)])
    best = None
    for s in {"hyperbolic": [0.02, 0.1, 0.5], "exponential": [2.0, 10.0, 40.0], "power": [0.01, 0.05, 0.3]}[form]:
        if form == "hyperbolic":
            x0 = [0.8 * lo_y, max(hi_y - lo_y, 1e-3) * s, s]
            lb, ub = [0.0, 0.0, 1e-4], [np.inf, np.inf, 50.0]
        elif form == "exponential":
            x0 = [0.8 * lo_y, max(hi_y - lo_y, 1e-3), s]
            lb, ub = [0.0, 0.0, 1e-3], [np.inf, np.inf, 500.0]
        else:
            g0 = max(math.log(max(hi_y, 1e-3) / max(lo_y, 1e-3)) / math.log((1 + s) / s), 0.0)
            x0 = [max(lo_y, 1e-3) * (1 + s) ** g0, s, g0]
            lb, ub = [0.0, 1e-4, 0.0], [np.inf, 50.0, 20.0]
        r = least_squares(lambda th: np.log(np.maximum(f(p, *th), 1e-12)) - ly, x0, bounds=(lb, ub))
        if best is None or r.cost < best.cost:
            best = r
    return best.x


def invert(form: str, th: Sequence[float], y: float) -> float:
    """The coverage p with f(p) = y (inf when y is at or below the asymptote, or unreachable)."""
    if form == "power":
        b, c, g = th
        if b <= 0 or g <= 0 or y <= 0:
            return math.inf
        return (y / b) ** (-1.0 / g) - c
    a, b, c = th
    if y <= a or b <= 0:
        return math.inf
    if form == "hyperbolic":
        return b / (y - a) - c
    return -math.log((y - a) / b) / c


def mono_inverse(P: Sequence[float], m: Sequence[float], y: float) -> float:
    """Model-free: the coverage where the non-increasing envelope of the cell means (log-linear between the grid
    points) equals y; 0 when the lowest coverage already meets it, inf when even the highest does not."""
    P, m = np.asarray(P, float), np.asarray(m, float)
    o = np.argsort(P)
    P, m = P[o], m[o]
    ok = np.isfinite(m) & (m > 0)
    P, env = P[ok], np.minimum.accumulate(m[ok])
    if not len(P) or not np.isfinite(y) or y <= 0:
        return math.nan
    if y >= env[0]:
        return float(P[0])
    if y < env[-1]:
        return math.inf
    for i in range(len(P) - 1):
        if env[i] >= y >= env[i + 1]:
            if env[i] == env[i + 1]:
                return float(P[i])
            w = (math.log(env[i]) - math.log(y)) / (math.log(env[i]) - math.log(env[i + 1]))
            return float(P[i] + w * (P[i + 1] - P[i]))
    return float(P[-1])


def coverage_for(form: str, th: Sequence[float], ratio: float) -> float:
    """The coverage at which the delay falls to `ratio` x the full-coverage delay f(1); 0 when DTE already meets it."""
    f, _ = FORMS[form]
    target = ratio * float(f(1.0, *th))
    if float(f(0.0, *th)) <= target:
        return 0.0
    return float(min(max(invert(form, th, target), 0.0), 1.0))


def _pivot(df: pd.DataFrame, metric: str) -> pd.DataFrame:
    """seeds x p of a metric (stage A, DTE and relay cells of one mix)."""
    return df.pivot_table(index="seed", columns="p", values=metric, aggfunc="first").sort_index(axis=1)


def _means(Y: np.ndarray) -> np.ndarray:
    return np.nanmean(Y, axis=0)


def cv_rmse(form: str, P: np.ndarray, Y: np.ndarray, folds: int = CV_FOLDS) -> float:
    """K-fold over seeds: fit on the other folds' cell means, score the held-out fold's cell means (RMSE of log
    delay). Scoring fold means rather than single seeds keeps the seed-to-seed spread (about 1.2 in log p90) from
    swamping the difference between forms."""
    f, _ = FORMS[form]
    err = []
    for idx in np.array_split(np.arange(Y.shape[0]), min(folds, Y.shape[0])):
        th = fit_form(form, P, _means(np.delete(Y, idx, axis=0)))
        yi = _means(Y[idx])
        ok = np.isfinite(yi) & (yi > 0)
        err += list(np.log(yi[ok]) - np.log(np.maximum(f(P[ok], *th), 1e-12)))
    return float(np.sqrt(np.mean(np.square(err)))) if err else np.nan


def insample_rmse(form: str, P: np.ndarray, Y: np.ndarray) -> float:
    f, _ = FORMS[form]
    m = _means(Y)
    th = fit_form(form, P, m)
    ok = np.isfinite(m) & (m > 0)
    return float(np.sqrt(np.mean(np.square(np.log(m[ok]) - np.log(np.maximum(f(P[ok], *th), 1e-12))))))


def _ci(x: Sequence[float]) -> List[Optional[float]]:
    x = np.asarray([v for v in x if np.isfinite(v)], float)
    return [float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5))] if len(x) >= 10 else [None, None]


def law(P: np.ndarray, Y: np.ndarray, boot: int = N_BOOT, seed: int = 0) -> Dict[str, Any]:
    """Every form with its CV and in-sample error; the chosen form's parameters, f(0), f(1) and the 2x / 1.5x
    coverages, plus the same coverages read model-free off the measured cells (target = ratio x the p = 1 cell mean),
    all with bootstrap intervals over seeds."""
    cv = {k: cv_rmse(k, P, Y) for k in FORMS}
    fit_in = {k: insample_rmse(k, P, Y) for k in FORMS}
    form = min(cv, key=lambda k: (np.inf if not np.isfinite(cv[k]) else cv[k]))
    f, names = FORMS[form]
    j1 = int(np.argmax(P))

    def summary(Ys):
        m = _means(Ys)
        th = fit_form(form, P, m)
        return {**dict(zip(names, map(float, th))), "f0": float(f(0.0, *th)), "f1": float(f(1.0, *th)),
                "p_2x": coverage_for(form, th, 2.0), "p_1.5x": coverage_for(form, th, 1.5),
                "cell_full": float(m[j1]), "p_2x_cells": mono_inverse(P, m, 2.0 * m[j1]),
                "p_1.5x_cells": mono_inverse(P, m, 1.5 * m[j1])}

    point = summary(Y)
    rng = np.random.default_rng(seed)
    draws = [summary(Y[rng.integers(0, Y.shape[0], Y.shape[0])]) for _ in range(boot)]
    ci = {k: _ci([d[k] for d in draws]) for k in point}
    return {"form": form, "cv_rmse_log": cv, "insample_rmse_log": fit_in, "point": point, "ci95": ci,
            "n_seeds": int(Y.shape[0]),
            "p": [float(x) for x in P], "cell_mean": [float(x) for x in _means(Y)],
            "cell_ci95": [float(stats.t.ppf(0.975, max(np.isfinite(Y[:, j]).sum() - 1, 1)) * np.nanstd(Y[:, j], ddof=1)
                                / math.sqrt(max(np.isfinite(Y[:, j]).sum(), 1))) for j in range(Y.shape[1])],
            "boot": boot}


def laws(df: pd.DataFrame, boot: int = N_BOOT) -> Dict[str, Dict[str, Any]]:
    a = df[(df["stage"] == "A") & df["p"].notna()]
    out: Dict[str, Dict[str, Any]] = {}
    for mix in sorted(a["mix"].unique()):
        g = a[a["mix"] == mix]
        out[mix] = {}
        for m in LAW_METRICS:
            Y = _pivot(g, m)
            out[mix][m] = law(Y.columns.to_numpy(float), Y.to_numpy(float), boot)
    return out


# ---------------------------------------------------------------------------------------------------------
# 3. delay-based break-even at p = 0.5
# ---------------------------------------------------------------------------------------------------------
def ltv_musd_per_year() -> float:
    from lunarsim.entities import VEHICLE_CLASSES
    c = VEHICLE_CLASSES["LTV"]
    return c.unit_cost_musd / c.life_years


BREAKEVEN_OPTIONS = [("+1 rover", "strict", 1), ("+2 rovers", "strict", 2), ("+3 rovers", "strict", 3),
                     ("strategic step", "strategic", 0), ("strategic step + 1 rover", "strategic", 1)]


def breakeven(df: pd.DataFrame, form: str, metric: str = "delay_prio1_p90_h", boot: int = N_BOOT, seed: int = 1,
              p_b: float = B_P) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    a = df[(df["stage"] == "A") & df["p"].notna() & (df["mix"] == "supervised_strict")]
    b = df[(df["stage"] == "B")]
    Yc = _pivot(a, metric)
    P = Yc.columns.to_numpy(float)
    base_b = select(b, p=p_b, policy="strict", extra_rovers=0, mast="none").drop_duplicates("seed").set_index("seed")[metric]
    opts = {lab: select(b, p=p_b, policy=pol, extra_rovers=n, mast="none").drop_duplicates("seed").set_index("seed")[metric]
            for lab, pol, n in BREAKEVEN_OPTIONS}
    seeds = sorted(set(Yc.index) & set(base_b.index).intersection(*[set(s.index) for s in opts.values()]))
    Y = Yc.loc[seeds].to_numpy(float)
    f, _ = FORMS[form]
    ltv = ltv_musd_per_year()

    def one(rows: np.ndarray) -> Dict[str, Dict[str, float]]:
        m = _means(Y[rows])
        th = fit_form(form, P, m)
        sd = [seeds[i] for i in rows]
        res = {"_base": {"p90": float(np.nanmean(base_b.loc[sd])), "f_pb": float(f(p_b, *th)), "f1": float(f(1.0, *th)),
                         "cell_pb": float(m[np.argmin(np.abs(P - p_b))]), "cell_full": float(m[np.argmax(P)])}}
        for lab in opts:
            v = float(np.nanmean(opts[lab].loc[sd]))
            pe = mono_inverse(P, m, v)                        # model-free: the measured strict cells
            pl = invert(form, th, v)                          # the fitted law
            res[lab] = {"p90": v, "p_equiv": pe, "p_equiv_law": pl if pl <= 1.0 else math.inf}
        return res

    pt = one(np.arange(len(seeds)))
    rng = np.random.default_rng(seed)
    draws = [one(rng.integers(0, len(seeds), len(seeds))) for _ in range(boot)]
    rows = []
    for lab, pol, n in BREAKEVEN_OPTIONS:
        pe, pl = pt[lab]["p_equiv"], pt[lab]["p_equiv_law"]
        bpe = np.array([d[lab]["p_equiv"] for d in draws])
        bpl = np.array([d[lab]["p_equiv_law"] for d in draws])
        rows.append({"option": lab, "policy": pol, "extra_rovers": n, "metric": metric, "n_seeds": len(seeds),
                     "value": pt[lab]["p90"], "value_ci95": _ci([d[lab]["p90"] for d in draws]),
                     "base_value": pt["_base"]["p90"], "p_equiv": pe, "p_equiv_ci95": _ci(bpe),
                     "share_beyond_full_coverage": float(np.mean(~np.isfinite(bpe))),
                     "delta_p": pe - p_b if np.isfinite(pe) else math.inf, "delta_p_ci95": _ci(bpe - p_b),
                     "p_equiv_law": pl, "p_equiv_law_ci95": _ci(bpl),
                     "share_beyond_full_coverage_law": float(np.mean(~np.isfinite(bpl)))})
    t = pd.DataFrame(rows)
    for c in ("value_ci95", "p_equiv_ci95", "delta_p_ci95", "p_equiv_law_ci95"):
        t[c + "_lo"] = [x[0] for x in t[c]]
        t[c + "_hi"] = [x[1] for x in t[c]]
        del t[c]
    one_ltv = t.loc[t["option"] == "+1 rover"].iloc[0]
    dp1 = float(one_ltv["delta_p"])
    b_dp1 = np.array([d["+1 rover"]["p_equiv"] - p_b for d in draws])
    per01 = [0.1 * ltv / x for x in b_dp1 if np.isfinite(x) and x > 0]
    worth = {"ltv_musd_per_year": ltv, "delta_p_one_ltv": dp1,
             "delta_p_one_ltv_ci95": [one_ltv["delta_p_ci95_lo"], one_ltv["delta_p_ci95_hi"]],
             "musd_per_year_per_0.1_coverage": 0.1 * ltv / dp1 if np.isfinite(dp1) and dp1 > 0 else None,
             "musd_per_year_per_0.1_coverage_ci95": _ci(per01),
             "share_draws_one_ltv_not_positive": float(np.mean(~(np.isfinite(b_dp1) & (b_dp1 > 0)))),
             "base": pt["_base"], "p_b": p_b, "form": form,
             "curve": "model-free: the measured supervised-strict stage A cell means, their non-increasing envelope, "
                      "log-linear between grid points (p_equiv); the fitted law gives p_equiv_law",
             "base_check": "stage B strict +0 rovers at p = 0.5 must equal the stage A strict cell at p = 0.5 "
                           "(same scenario and seeds): base.p90 vs base.cell_pb"}
    return t, worth


# ---------------------------------------------------------------------------------------------------------
# 4. operator-demand compression (H5)
# ---------------------------------------------------------------------------------------------------------
def operator_demand(df: pd.DataFrame, mixes: Sequence[str] = ("teleop_4s", "default")) -> pd.DataFrame:
    """Per mix and coverage. The reference for the compression is relay coverage 1.0, not 'always': with a relay that
    is always up the operations equal 'always' exactly, but the linked modes book demand per driven segment (and admit
    a job while another is between segments), whereas 'always' books it over the whole job, so the peak is only
    comparable within the linked modes."""
    rows = []
    for stage, mix in [(st, m) for st in ("A", "A2") for m in mixes]:
        g = df[(df["stage"] == stage) & (df["mix"] == mix)]
        if g.empty:
            continue
        full = select(g, p=1.0)
        for p, h in g.groupby(g["p"].fillna(-1.0)):
            vs = paired(full, h, "operator_peak_demand") if len(full) and p >= 0 else {}
            ratio = (h["operator_peak_demand"] / h["operator_mean_demand"]).replace([np.inf, -np.inf], np.nan)
            n_ops = int(h["n_operators"].iloc[0])
            n = int(ratio.notna().sum())
            t = stats.t.ppf(0.975, max(n - 1, 1))
            rows.append({"stage": stage, "operators": "strict" if stage == "A2" else "lenient", "mix": mix,
                         "comms": h["comms"].iloc[0], "p": np.nan if p < 0 else p, "n_seeds": int(len(h)),
                         "peak_mean": float(h["operator_peak_demand"].mean()),
                         "peak_ci95": float(t * h["operator_peak_demand"].std(ddof=1) / math.sqrt(len(h))),
                         "peak_max": float(h["operator_peak_demand"].max()),
                         "mean_demand": float(h["operator_mean_demand"].mean()),
                         "peak_to_mean": float(ratio.mean()), "peak_to_mean_ci95": float(t * ratio.std(ddof=1) / math.sqrt(n)) if n > 1 else np.nan,
                         "n_operators": n_ops, "seeds_over_staffing": int((h["operator_peak_demand"] > n_ops + 1e-9).sum()),
                         "over_staffing": bool((h["operator_peak_demand"] > n_ops + 1e-9).any()),
                         "peak_minus_full_relay": vs.get("diff", np.nan), "peak_minus_full_relay_ci_lo": vs.get("ci_lo", np.nan),
                         "peak_minus_full_relay_ci_hi": vs.get("ci_hi", np.nan)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------------------------------------
# 5. throughput: the never-linked bound
# ---------------------------------------------------------------------------------------------------------
def site_link_fractions(path: str = LINK_FILE, criterion: str = "any_part") -> Dict[str, float]:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    return {k: float(v["summary"]["dte"][criterion]["fraction"]) for k, v in doc["points"].items()}


def demand_by_dest(cargo: List[List[Any]], cols: List[str], horizon_h: float = HORIZON_H) -> Dict[str, Dict[str, float]]:
    """kg ready in the year and kg delivered inside it, by destination, from a trace cargo table."""
    ci = {c: i for i, c in enumerate(cols)}
    out: Dict[str, Dict[str, float]] = {}
    for r in cargo:
        d = out.setdefault(r[ci["dest"]], {"ready_kg": 0.0, "delivered_kg": 0.0})
        if r[ci["t_ready"]] is not None and r[ci["t_ready"]] < horizon_h:
            d["ready_kg"] += r[ci["mass_kg"]]
        td = r[ci["t_delivered"]]
        if td is not None and td <= horizon_h + 1e-9:
            d["delivered_kg"] += r[ci["mass_kg"]]
    return out


def throughput_bound(dem: pd.DataFrame, never: Sequence[str]) -> Dict[str, Any]:
    """dem: seed, run (always | dte), dest, ready_kg, delivered_kg. The bound = cargo ready in the year for the never-
    linked destinations; the measured gap = delivered(always) - delivered(DTE), both inside the year; per seed."""
    never = list(never)
    g = dem.groupby(["seed", "run"])
    tot = g["delivered_kg"].sum().unstack("run")
    un = dem[dem["dest"].isin(never)]
    ready_un = un[un["run"] == "always"].groupby("seed")["ready_kg"].sum()
    deliv_un = un.groupby(["seed", "run"])["delivered_kg"].sum().unstack("run").reindex(columns=["always", "dte"]).fillna(0.0)
    gap = (tot["always"] - tot["dte"]) / 1000.0
    lost_un = (deliv_un["always"] - deliv_un["dte"]) / 1000.0
    rest = gap - lost_un
    n = len(gap)
    t = stats.t.ppf(0.975, max(n - 1, 1))
    ms = lambda s: {"mean": float(s.mean()), "ci95": float(t * s.std(ddof=1) / math.sqrt(len(s))) if len(s) > 1 else None}
    by_dest = (dem[dem["run"] == "always"].groupby("dest")["ready_kg"].mean() / 1000.0).round(3).to_dict()
    deliv_dest = {run: (g.groupby("dest")["delivered_kg"].sum() / 1000.0 / n).round(3).to_dict()
                  for run, g in dem.groupby("run")}
    return {"never_linked": never, "n_seeds": n, "bound_ready_t": ms(ready_un / 1000.0), "gap_t": ms(gap),
            "lost_at_never_linked_t": ms(lost_un), "gap_elsewhere_t": ms(rest),
            "dte_delivered_to_never_linked_t": ms(deliv_un["dte"] / 1000.0),
            "gap_minus_bound_t": ms(gap - ready_un / 1000.0), "ready_t_by_dest_always": by_dest,
            "delivered_t_by_dest": deliv_dest}


def cmd_demand(a) -> None:
    """Re-run the supervised-strict stage A cells 'always' and 'dte' with traces (the E21 cells exactly, start year
    by seed) and tabulate cargo by destination; the delivered totals must equal the E21 raw rows."""
    from lunarsim import Simulation
    from experiments.phase4 import run_phase4 as R
    if a.max_seconds and a.max_seconds > 0:
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    raw = load(a.results)
    rows, checks = [], []
    t0 = time.time()
    for run, mode in (("always", "always"), ("dte", "dte")):
        tag, sc = R.scenario(a.mix, mode)
        fn, kw = R.MECHS[R.MECH]
        for s in range(a.seeds):
            sc_s = sc.with_(comms=dict(sc.comms, start_year=R.start_year(s)))
            sim = Simulation(sc_s, fn, seed=s, mech_kwargs=dict(kw, trace=True))
            out = sim.run()
            tr = json.loads(json.dumps(sim.trace_export(mechanism=R.MECH)))
            for dest, v in demand_by_dest(tr["cargo"], tr["cargo_columns"]).items():
                rows.append({"seed": s, "run": run, "mix": a.mix, "dest": dest, **v})
            ref = select(raw, stage="A", comms=mode, mix=a.mix, seed=s)
            checks.append(abs(out["delivered_kg_in_horizon"] - float(ref["delivered_kg_in_horizon"].iloc[0])) if len(ref) else np.nan)
        print(f"[{run}] {a.seeds} seeds done ({time.time() - t0:.0f} s)")
    pd.DataFrame(rows).to_csv(os.path.join(a.results, DEMAND_FILE), index=False, lineterminator="\n")
    print(f"wrote {DEMAND_FILE}: {len(rows)} rows; max |delivered in year - E21 raw| = {np.nanmax(checks):.3g} kg "
          f"over {np.isfinite(checks).sum()} runs")


# ---------------------------------------------------------------------------------------------------------
def _json(x):
    if isinstance(x, dict):
        return {str(k): _json(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_json(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if not math.isfinite(float(x)) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


def cmd_fit(a) -> None:
    df = load(a.results)
    t0 = time.time()
    eff = effects(df)
    eff.to_csv(os.path.join(a.results, "table_E21_effects.csv"), index=False, lineterminator="\n")
    print(f"table_E21_effects.csv: {len(eff)} rows ({time.time() - t0:.0f} s)")
    L = laws(df, a.boot)
    print(f"laws fitted ({time.time() - t0:.0f} s)")
    fig = []
    for mix, d in L.items():
        for m, r in d.items():
            f, _ = FORMS[r["form"]]
            th = [r["point"][k] for k in FORMS[r["form"]][1]]
            for p, y, h in zip(r["p"], r["cell_mean"], r["cell_ci95"]):
                fig.append({"mix": mix, "metric": m, "p": p, "mean": y, "ci95": h, "fit": float(f(p, *th)), "form": r["form"],
                            "kind": "cell"})
            for p in np.linspace(0, 1, 51):
                fig.append({"mix": mix, "metric": m, "p": float(p), "mean": np.nan, "ci95": np.nan, "fit": float(f(p, *th)),
                            "form": r["form"], "kind": "curve"})
    pd.DataFrame(fig).to_csv(os.path.join(a.results, "fig_E21_delay_coverage.csv"), index=False, lineterminator="\n")
    form = L["supervised_strict"]["delay_prio1_p90_h"]["form"]
    be, worth = breakeven(df, form, boot=a.boot)
    sa = select(df, stage="A", p=B_P, mix="supervised_strict")
    worth["stage_A_strict_p90_at_pb"] = float(sa["delay_prio1_p90_h"].mean()) if len(sa) else None
    be.to_csv(os.path.join(a.results, "table_E21_breakeven_delay.csv"), index=False, lineterminator="\n")
    print(f"table_E21_breakeven_delay.csv ({time.time() - t0:.0f} s)")
    ops = operator_demand(df)
    ops.to_csv(os.path.join(a.results, "fig_E21_operator_demand.csv"), index=False, lineterminator="\n")
    fr = site_link_fractions()
    never = [k for k, v in fr.items() if v == 0.0 and "@" not in k]
    tb = None
    dp = os.path.join(a.results, DEMAND_FILE)
    if os.path.exists(dp):
        tb = throughput_bound(pd.read_csv(dp), never)
    doc = {"experiment": "E21", "stages": sorted(df["stage"].unique().tolist()), "n_rows": int(len(df)),
           "method": __doc__.split("Method:", 1)[1].strip(),
           "laws": L, "breakeven_delay": {"options": be.to_dict(orient="records"), **worth},
           "operators": ops.to_dict(orient="records"),
           "throughput": {"site_link_fraction_dte_any_part": fr, **(tb or {"note": f"run `demand` first ({DEMAND_FILE})"})}}
    with open(os.path.join(a.results, "E21_fit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(_json(doc), f, indent=1)
        f.write("\n")
    print(f"E21_fit.json written ({time.time() - t0:.0f} s)")


# ---------------------------------------------------------------------------------------------------------
# round 2 (B-49, referee round 1): reads the *_r2 files, writes *_r2 outputs; the round-1 files stay as they are
# ---------------------------------------------------------------------------------------------------------
R2_FILES = STAGE_FILES + ("E21e_sensitivity.csv",)
R2_METRICS = METRICS + ["delay_prio1_p90_censored_h", "delay_prio1_mean_censored_h", "prio1_completion_share",
                        "delivered_bulk_t", "delivered_landed_t", "completion_share_landed", "completion_share_bulk"]
N_BOOT_R2 = 2000
PRICE_POORLY_DETERMINED_MUSD = 200.0
CELL_KEYS = ["stage", "comms", "p", "mix", "policy", "extra_rovers", "mast", "pad_standoff_km", "criterion", "defer_wait_h",
             "sensitivity"]
YEAR_CELLS = [("always", np.nan), ("dte", 0.0), ("dte+relay", 0.1), ("dte+relay", 0.5), ("dte+relay", 1.0)]
YEAR_MIXES = ("default", "supervised_strict", "supervised_strategic", "supervised_strategic+avoid", "teleop_4s")
# the primary comparisons (referee S16): (family, mix, p, metric, cell label or None); intervals are per comparison
PRIMARY = [("dte_vs_always", "supervised_strict", 0.0, "delivered_t_in_year", None),
           ("dte_vs_always", "supervised_strict", 0.0, "delivered_landed_t", None),
           ("dte_vs_always", "supervised_strict", 0.0, "delay_prio1_p90_censored_h", None),
           ("relay_vs_always", "supervised_strict", 0.5, "delay_prio1_p90_h", None),
           ("policy_vs_strict", "supervised_strategic", 0.1, "delay_prio1_p90_h", None),
           ("rovers_vs_0", "supervised", 0.5, "delay_prio1_p90_h", "+1 rovers")]


def load_round(results: str = RESULTS, rnd: str = "r1") -> pd.DataFrame:
    x = "" if rnd == "r1" else f"_{rnd}"
    files = [f.replace(".csv", f"{x}.csv") for f in (STAGE_FILES if rnd == "r1" else R2_FILES)]
    parts = [pd.read_csv(os.path.join(results, f)) for f in files if os.path.exists(os.path.join(results, f))]
    if not parts:
        raise SystemExit(f"no E21 {rnd} replication files in {results}")
    df = prepare(pd.concat(parts, ignore_index=True, sort=False))
    if "sensitivity" not in df:
        df["sensitivity"] = "none"
    df["sensitivity"] = df["sensitivity"].fillna("none")
    for k in ("bulk", "landed"):
        if f"delivered_{k}_kg_in_horizon" in df:
            df[f"delivered_{k}_t"] = df[f"delivered_{k}_kg_in_horizon"] / 1000.0
    if "delivered_bulk_t" in df and "delivered_landed_t" in df:
        df["delivered_return_t"] = df["delivered_t_in_year"] - df["delivered_bulk_t"] - df["delivered_landed_t"]
    return df


def _tci(v: np.ndarray) -> float:
    v = v[np.isfinite(v)]
    return float(stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else np.nan


def cell_table(df: pd.DataFrame, metrics: Sequence[str]) -> pd.DataFrame:
    """One row per cell: mean, Student-t 95 % half-width (n - 1 dof, referee E20), median and n per metric; the
    share of seeds whose censored p90 is only a bound; the operator peak's maximum and the seeds over the staff."""
    metrics = [m for m in metrics if m in df]
    keys = [k for k in CELL_KEYS if k in df]
    rows = []
    for key, g in df.groupby(keys, dropna=False, sort=True):
        r = dict(zip(keys, key))
        r["n_seeds"] = int(g["seed"].nunique())
        for m in metrics:
            v = g[m].to_numpy(float)
            fin = v[np.isfinite(v)]
            r[m] = float(fin.mean()) if len(fin) else np.nan
            r[m + "_ci95_t"] = _tci(v)
            r[m + "_median"] = float(np.median(fin)) if len(fin) else np.nan
            r[m + "_n"] = int(len(fin))
        if "delay_prio1_p90_censored_is_bound" in g:
            r["p90_censored_bound_share"] = float(g["delay_prio1_p90_censored_is_bound"].mean())
        if "operator_peak_demand" in g:
            r["operator_peak_max"] = float(g["operator_peak_demand"].max())
            r["seeds_over_staff"] = int((g["operator_peak_demand"] > g["n_operators"] + 1e-9).sum())
        rows.append(r)
    return pd.DataFrame(rows)


def split_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Referee M2/O1: the throughput split. The demand model's bulk flows, landed cargo lost under DTE per mix, and
    the landed cargo that moves at 3 km pads under DTE (Stage C)."""
    from lunarsim.phases import PHASES
    flows = [{"origin": b.origin, "dest": b.dest, "t_per_year": b.tonnes_per_year} for b in PHASES["P2"].bulk_flows]
    out: Dict[str, Any] = {"bulk_flows_P2": flows,
                           "note": "bulk = regolith flows (the demand model); landed = lander cargo (not bulk, not "
                                   "return); return = items sent back to the pads"}
    if "delivered_landed_t" not in df:
        out["missing"] = "no delivered_landed_kg_in_horizon column (round-1 files)"
        return out
    a = df[df["stage"] == "A"]
    per = {}
    for mix in sorted(a["mix"].unique()):
        ref, cell = select(a, comms="always", mix=mix), select(a, comms="dte", mix=mix)
        per[mix] = {m: paired(ref, cell, m) for m in ("delivered_bulk_t", "delivered_landed_t", "delivered_return_t")
                    if m in df}
    out["dte_vs_always"] = per
    c = df[(df["stage"] == "C") & np.isclose(df["pad_standoff_km"], 3.0) & (df["comms"] == "dte")]
    out["pads_3km_dte"] = {f"{mix}/{crit}": {"landed_t_mean": float(g["delivered_landed_t"].mean()),
                                             "seeds_with_landed_cargo": int((g["delivered_landed_t"] > 0).sum()),
                                             "n_seeds": int(len(g))}
                           for (mix, crit), g in c.groupby(["mix", "criterion"])}
    return out


def year_table(df: pd.DataFrame, metrics: Sequence[str]) -> pd.DataFrame:
    """Referee M3/S3: key Stage A cells by start year (2028-2031, five seeds each), with a flag where one year's mean
    is less than half or more than twice the other years' mean (e.g. the 2028 stranding)."""
    a = df[df["stage"] == "A"]
    metrics = [m for m in metrics if m in df]
    rows = []
    for comms, p in YEAR_CELLS:
        for mix in YEAR_MIXES:
            g = select(a, comms=comms, mix=mix) if comms == "always" else select(a, p=float(p), mix=mix)
            if g.empty:
                continue
            for m in metrics:
                by = g.groupby("start_year")[m]
                means = by.mean()
                for yr, v in by:
                    others = means.drop(yr).mean()
                    ratio = float(means[yr] / others) if others and np.isfinite(others) and others != 0 else np.nan
                    rows.append({"comms": comms, "p": p, "mix": mix, "metric": m, "start_year": int(yr),
                                 "n": int(v.notna().sum()), "mean": float(v.mean()), "median": float(v.median()),
                                 "ratio_to_other_years": ratio,
                                 "flag": bool(np.isfinite(ratio) and (ratio < 0.5 or ratio > 2.0))})
    return pd.DataFrame(rows)


def year_blocked(ref: pd.DataFrame, cell: pd.DataFrame, metric: str) -> Dict[str, float]:
    """The paired effect with the calendar as the unit: per-year means of the per-seed differences (four years),
    t interval on 3 dof."""
    j = pd.concat([ref.drop_duplicates("seed").set_index("seed")[[metric, "start_year"]].rename(columns={metric: "r"}),
                   cell.drop_duplicates("seed").set_index("seed")[[metric]].rename(columns={metric: "c"})],
                  axis=1, join="inner").dropna()
    ym = (j["c"] - j["r"]).groupby(j["start_year"]).mean()
    n = len(ym)
    if n < 2:
        return {"years": n, "diff": np.nan, "ci_lo": np.nan, "ci_hi": np.nan}
    h = stats.t.ppf(0.975, n - 1) * ym.std(ddof=1) / math.sqrt(n)
    return {"years": n, "diff": float(ym.mean()), "ci_lo": float(ym.mean() - h), "ci_hi": float(ym.mean() + h),
            "by_year": {int(k): float(v) for k, v in ym.items()}}


def _q(x: np.ndarray, q: float) -> float:
    """Order-statistic quantile that keeps +-inf draws (no interpolation across an infinite value)."""
    x = np.sort(np.asarray(x, float))
    x = x[~np.isnan(x)]
    if not len(x):
        return np.nan
    return float(x[int(math.floor(q * (len(x) - 1)))] if q < 0.5 else x[int(math.ceil(q * (len(x) - 1)))])


def breakeven_r2(df: pd.DataFrame, metric: str = "delay_prio1_p90_h", boot: int = N_BOOT_R2, seed: int = 1,
                 p_b: float = B_P) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Referee M5/S4/E2/E15: the model-free break-even with every bootstrap draw kept. A draw where an option beats
    the full-coverage cell has p_equiv = inf (delta_p = inf, price ~ 0); a draw where one rover buys nothing has
    delta_p <= 0 (price unbounded). Intervals are order statistics over all draws. Also the paired difference
    delta_p(strategic step) - delta_p(+1 rover) on the same draws. No law-based column (referee S5)."""
    a = df[(df["stage"] == "A") & df["p"].notna() & (df["mix"] == "supervised_strict")]
    b = df[df["stage"] == "B"]
    Yc = _pivot(a, metric)
    P = Yc.columns.to_numpy(float)
    opts = {lab: select(b, p=p_b, policy=pol, extra_rovers=n, mast="none").drop_duplicates("seed").set_index("seed")[metric]
            for lab, pol, n in BREAKEVEN_OPTIONS}
    base = select(b, p=p_b, policy="strict", extra_rovers=0, mast="none").drop_duplicates("seed").set_index("seed")[metric]
    seeds = sorted(set(Yc.index) & set(base.index).intersection(*[set(s.index) for s in opts.values()]))
    Y = Yc.loc[seeds].to_numpy(float)
    ltv = ltv_musd_per_year()

    def one(rows):
        m = _means(Y[rows])
        sd = [seeds[i] for i in rows]
        return {lab: mono_inverse(P, m, float(np.nanmean(opts[lab].loc[sd]))) for lab in opts}, \
            float(np.nanmean(opts["+1 rover"].loc[sd]))

    pt, _ = one(np.arange(len(seeds)))
    rng = np.random.default_rng(seed)
    draws = [one(rng.integers(0, len(seeds), len(seeds)))[0] for _ in range(boot)]
    rows = []
    for lab, pol, n in BREAKEVEN_OPTIONS:
        pe = np.array([d[lab] for d in draws])
        dp = pe - p_b
        rows.append({"option": lab, "policy": pol, "extra_rovers": n, "metric": metric, "n_seeds": len(seeds), "boot": boot,
                     "value": float(np.nanmean(opts[lab].loc[seeds])), "base_value": float(np.nanmean(base.loc[seeds])),
                     "p_equiv": pt[lab], "p_equiv_ci95_lo": _q(pe, 0.025), "p_equiv_ci95_hi": _q(pe, 0.975),
                     "delta_p": pt[lab] - p_b, "delta_p_ci95_lo": _q(dp, 0.025), "delta_p_ci95_hi": _q(dp, 0.975),
                     "share_beyond_full_coverage": float(np.mean(np.isinf(pe))),
                     "ci95_hi_beyond_full_coverage": bool(np.isinf(_q(pe, 0.975))),     # JSON writes inf as null
                     "share_delta_p_not_positive": float(np.mean(dp <= 0))})
    t = pd.DataFrame(rows)
    dp1 = np.array([d["+1 rover"] for d in draws]) - p_b
    price = np.where(dp1 <= 0, np.inf, np.where(np.isinf(dp1), 0.0, 0.1 * ltv / np.where(dp1 > 0, dp1, 1.0)))
    hi = _q(price, 0.975)
    dps = np.array([d["strategic step"] for d in draws]) - p_b
    with np.errstate(invalid="ignore"):
        diff = dps - dp1                                   # inf - inf = nan: both beyond full coverage
    worth = {"ltv_musd_per_year": ltv, "p_b": p_b, "boot": boot,
             "price_musd_per_0.1_coverage": (0.1 * ltv / (pt["+1 rover"] - p_b)
                                             if np.isfinite(pt["+1 rover"]) and pt["+1 rover"] > p_b else None),
             "price_ci95": [_q(price, 0.025), hi],
             "price_upper_poorly_determined": bool(not np.isfinite(hi) or hi > PRICE_POORLY_DETERMINED_MUSD),
             "share_draws_rover_buys_nothing": float(np.mean(dp1 <= 0)),
             "share_draws_rover_beyond_full_coverage": float(np.mean(np.isinf(dp1))),
             "strategic_minus_rover": {"point": pt["strategic step"] - pt["+1 rover"],
                                       "ci95": [_q(diff, 0.025), _q(diff, 0.975)],
                                       "share_positive": float(np.mean(diff > 0)),
                                       "share_undetermined": float(np.mean(np.isnan(diff)))},
             "curve": "model-free: the measured supervised-strict Stage A cells (non-increasing envelope, log-linear "
                      "between grid points; round 2 has levels 0.05, 0.6 and 0.7)",
             "at": "p = 0.5, supervised-strict fleet, this demand (referee O5)"}
    return t, worth


def full_relay_vs_always(df: pd.DataFrame, metrics: Sequence[str]) -> Dict[str, Dict[str, Any]]:
    """Referee E5: per mix, does relay coverage 1.0 reproduce 'always' seed by seed?"""
    a = df[df["stage"] == "A"]
    out = {}
    for mix in sorted(a["mix"].unique()):
        r = select(a, comms="always", mix=mix).drop_duplicates("seed").set_index("seed")
        c = select(a, p=1.0, mix=mix).drop_duplicates("seed").set_index("seed")
        common = r.index.intersection(c.index)
        res = {}
        for m in [m for m in metrics if m in a] + [m for m in ("unmet_operator_waits",) if m in a]:
            x, y = r.loc[common, m].astype(float), c.loc[common, m].astype(float)
            same = (x == y) | (x.isna() & y.isna())
            res[m] = {"seeds_differing": int((~same).sum()),
                      "max_abs_diff": float(np.nanmax(np.abs(x - y))) if (~same).any() else 0.0}
        out[mix] = {"seeds": int(len(common)), "identical": all(v["seeds_differing"] == 0 for v in res.values()),
                    "metrics": res}
    return out


def mark_primary(eff: pd.DataFrame) -> pd.DataFrame:
    eff = eff.copy()
    eff["primary"] = False
    for fam, mix, p, metric, cell in PRIMARY:
        m = ((eff["family"] == fam) & (eff["mix"] == mix) & np.isclose(eff["p"].astype(float), p, equal_nan=False)
             & (eff["metric"] == metric))
        if fam == "rovers_vs_0":
            m &= (eff["policy"] == "strict") & (eff["cell"] == cell)
        if fam == "policy_vs_strict":
            m &= eff["stage"] == "A"
        eff.loc[m, "primary"] = True
    return eff


def cmd_fit_r2(a) -> None:
    rnd, x = a.round, f"_{a.round}"
    df = load_round(a.results, rnd)
    w = lambda name: os.path.join(a.results, name.replace(".csv", f"{x}.csv").replace(".json", f"{x}.json"))
    t0 = time.time()
    eff = mark_primary(effects(df, R2_METRICS))
    eff.to_csv(w("table_E21_effects.csv"), index=False, lineterminator="\n")
    cells = cell_table(df, R2_METRICS + ["delivered_return_t", "operator_peak_demand", "operator_wait_vehicle_h"])
    cells.to_csv(w("table_E21_cells.csv"), index=False, lineterminator="\n")
    years = year_table(df, ["delivered_t_in_year", "delivered_landed_t", "delay_prio1_p90_h",
                            "delay_prio1_p90_censored_h", "prio1_completion_share"])
    years.to_csv(w("table_E21_years.csv"), index=False, lineterminator="\n")
    print(f"effects {len(eff)}, cells {len(cells)}, year rows {len(years)} ({time.time() - t0:.0f} s)")
    blocked = {}
    a_ = df[df["stage"] == "A"]
    b_ = df[df["stage"] == "B"]
    for fam, mix, p, metric, cell in PRIMARY:
        if metric not in df:
            continue
        if fam == "rovers_vs_0":
            ref, cel = (select(b_, p=p, policy="strict", extra_rovers=0, mast="none"),
                        select(b_, p=p, policy="strict", extra_rovers=1, mast="none"))
        elif fam == "policy_vs_strict":
            ref, cel = select(a_, p=p, mix="supervised_strict"), select(a_, p=p, mix=mix)
        else:
            ref, cel = select(a_, comms="always", mix=mix), select(a_, p=p, mix=mix)
        blocked[f"{fam}|{mix}|{p}|{metric}"] = year_blocked(ref, cel, metric)
    L = laws(df, a.boot_law)
    be, worth = breakeven_r2(df, boot=a.boot)
    be.to_csv(w("table_E21_breakeven_delay.csv"), index=False, lineterminator="\n")
    ops = operator_demand(df)
    ops.to_csv(w("fig_E21_operator_demand.csv"), index=False, lineterminator="\n")
    fr = site_link_fractions()
    never = [k for k, v in fr.items() if v == 0.0 and "@" not in k]
    dp = os.path.join(a.results, DEMAND_FILE)
    doc = {"experiment": "E21", "round": rnd, "stages": sorted(df["stage"].unique().tolist()), "n_rows": int(len(df)),
           "method": __doc__.split("Method:", 1)[1].strip()
           + "\n  round 2: medians, paired log-ratios (geometric-mean ratio, t interval on the log scale) and Wilcoxon"
             " signed-rank p beside every paired effect; cell intervals Student-t; the break-even keeps every bootstrap"
             " draw (2,000); year-blocked intervals for the primary comparisons; intervals are per comparison, not"
             " adjusted for multiplicity.",
           "primary_comparisons": [dict(zip(("family", "mix", "p", "metric", "cell"), p)) for p in PRIMARY],
           "year_blocked": blocked,
           "throughput_split": split_summary(df),
           "full_relay_vs_always": full_relay_vs_always(df, R2_METRICS),
           "laws": {"note": "descriptive only: the three families cannot represent the slow decline between p = 0.2 and 1 "
                            "(referee S5); use the model-free coverages (p_2x_cells, p_1.5x_cells)", **L},
           "breakeven_delay": {"options": be.to_dict(orient="records"), **worth},
           "operators": ops.to_dict(orient="records"),
           "throughput_bound": ({"site_link_fraction_dte_any_part": fr,
                                 **throughput_bound(pd.read_csv(dp), never)} if os.path.exists(dp) else None),
           "rounds_check": check_rounds(a.results)}
    with open(w("E21_fit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(_json(doc), f, indent=1)
        f.write("\n")
    print(f"E21_fit{x}.json and the {x} tables written ({time.time() - t0:.0f} s)")


ROUND_FILES = STAGE_FILES + ("E21d_sun.csv",)


def check_rounds(results: str = RESULTS) -> Dict[str, Any]:
    """Round 2 reruns the round-1 cells with an unchanged engine: every round-2 row that has a round-1 twin (same
    stage file, cell key and seed) must equal it in every round-1 column. Files are read with round-trip float parsing
    (pandas' default parser can be one unit in the last place off)."""
    out: Dict[str, Any] = {}
    for f in ROUND_FILES:
        p1, p2 = os.path.join(results, f), os.path.join(results, f.replace(".csv", "_r2.csv"))
        if not (os.path.exists(p1) and os.path.exists(p2)):
            continue
        a = pd.read_csv(p1, float_precision="round_trip")
        b = pd.read_csv(p2, float_precision="round_trip")
        cols = [c for c in a.columns if c in b.columns and c not in ("cell", "seed", "run_s")]
        m = a.merge(b, on=["cell", "seed"], suffixes=("_1", "_2"))
        diff = {}
        for c in cols:
            x, y = m[c + "_1"], m[c + "_2"]
            same = (x == y) | (x.isna() & y.isna())
            if not same.all():
                diff[c] = int((~same).sum())
        out[f] = {"pairs": int(len(m)), "r1_rows": int(len(a)), "columns": len(cols), "differing": diff}
    return out


def cmd_rounds(a) -> None:
    res = check_rounds(a.results)
    if not res:
        print("no stage has both round-1 and round-2 files yet")
        return
    bad = 0
    for f, r in res.items():
        bad += len(r["differing"])
        print(f"{f}: {r['pairs']} of {r['r1_rows']} round-1 rows have a round-2 twin; {r['columns']} columns; "
              + ("all equal" if not r["differing"] else f"DIFFERING {r['differing']}"))
    if bad:
        raise SystemExit(1)


# ---------------------------------------------------------------------------------------------------------
# Stage F (B-57): the bounded-wait strategic rule and strategic without the re-draw
# ---------------------------------------------------------------------------------------------------------
BOUNDED_METRICS = ["delivered_t_in_year", "delivered_bulk_t", "delivered_landed_t", "prio1_completion_share",
                   "delay_prio1_p90_censored_h", "blackout_wait_vehicle_h", "blackout_jobs_refused"]
STAGE_F_FILE = "E21f_bounded_r2.csv"
YEARS = (2028, 2029, 2030, 2031)


def _f_label(r) -> str:
    if r.get("never_linked") == "strand":
        return "strategic, strand on never-linked"
    return f"bound {r['bound_h']:g} h, never-linked {'refused' if r['bound_never'] == 'refuse' else 'as strategic'}"


def load_stage_f(results: str = RESULTS) -> pd.DataFrame:
    f = prepare(pd.read_csv(os.path.join(results, STAGE_F_FILE)))
    for k in ("bulk", "landed"):
        f[f"delivered_{k}_t"] = f[f"delivered_{k}_kg_in_horizon"] / 1000.0
    f["variant"] = f.apply(_f_label, axis=1)
    return f


def never_linked_legs(path: str = LINK_FILE) -> Dict[str, Any]:
    """Legs with at least one never-linked route sample (direct, any part of the disc): under DTE an intervention there
    can never be cleared. Main network = the seven sites and the two pads at 1 km."""
    from lunarsim import comms as C
    el = C.EarthLink.load(path, samples=True)
    s = el.samples
    dark = {i for i, smp in enumerate(s["samples"]) if not s["series"][smp["w"][0]]}
    legs = sorted(k for k, ids in s["legs"].items() if any(i in dark for i in ids))
    sites = [p for p in el.doc["points"] if p.endswith("@1") or "@" not in p]
    main = [f"{a}->{b}" for a in sites for b in sites if a != b and not (a.startswith("PAD") and b.startswith("PAD"))]
    hit = [k for k in main if k in legs]
    return {"criterion": "any_part, direct", "samples_never_linked": len(dark), "samples": len(s["samples"]),
            "legs_with_never_linked_sample": len(legs), "legs": len(s["legs"]),
            "main_network_legs": len(main), "main_network_legs_with_never_linked_sample": len(hit),
            "main_network_list": hit}


def redraw_counts(df: pd.DataFrame, f: pd.DataFrame) -> List[Dict[str, Any]]:
    """blackout_jobs_refused per run by policy, link regime and start year. strategic: a committed job whose
    intervention fell on a never-linked sample (refused, re-drawn at a later dispatch); look-ahead: its deferrals
    (= blackout_jobs_avoided); strict: deferrals and never-linked legs; Stage F variants: both kinds."""
    a = df[(df["stage"] == "A") & (df["sensitivity"] == "none")]
    groups = [("strategic", a[a["mix"] == "supervised_strategic"]), ("look-ahead", a[a["mix"] == "supervised_strategic+avoid"]),
              ("strict", a[a["mix"] == "supervised_strict"])] + [(v, g) for v, g in f.groupby("variant")]
    out = []
    for name, g in groups:
        for p in (0.0, 0.1, 0.5):
            gp = select(g, p=p)
            if gp.empty:
                continue
            row = {"policy": name, "link": _plabel(p), "runs": int(len(gp)),
                   "refused_per_run": float(gp["blackout_jobs_refused"].mean()),
                   "avoided_per_run": float(gp["blackout_jobs_avoided"].mean()),
                   "refused_not_avoided_per_run": float((gp["blackout_jobs_refused"] - gp["blackout_jobs_avoided"]).mean())}
            for y in YEARS:
                gy = gp[gp["start_year"] == y]
                row[f"refused_per_run_{y}"] = float(gy["blackout_jobs_refused"].mean()) if len(gy) else None
            out.append(row)
    return out


def bounded_tables(df: pd.DataFrame, f: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    a = df[(df["stage"] == "A") & (df["sensitivity"] == "none")]
    rows, summary = [], []
    for p in (0.0, 0.1, 0.5):
        refs = {"strategic": select(a, p=p, mix="supervised_strategic"),
                "look-ahead": select(a, p=p, mix="supervised_strategic+avoid")}
        for var, cell in select(f, p=p).groupby("variant", sort=False):
            ctx = {"p": p, "link": _plabel(p), "start_year": "all"}
            for rl, ref in refs.items():
                rows += _rows("bounded", rl, var, ctx, ref, cell, BOUNDED_METRICS)
                for y in YEARS:
                    rows += _rows("bounded_by_year", rl, var, {**ctx, "start_year": y}, ref[ref["start_year"] == y],
                                  cell[cell["start_year"] == y], BOUNDED_METRICS)
            m = {k: float(cell[k].mean()) for k in BOUNDED_METRICS}
            m["delay_prio1_p90_censored_h_median"] = float(cell["delay_prio1_p90_censored_h"].median())
            by = {str(y): {k: float(cell.loc[cell["start_year"] == y, k].mean()) for k in
                           ("delivered_t_in_year", "delivered_bulk_t", "delivered_landed_t", "prio1_completion_share",
                            "blackout_wait_vehicle_h")} for y in YEARS}
            summary.append({"link": _plabel(p), "variant": var, "n": int(len(cell)), "mean": m, "by_year": by})
        for rl, ref in refs.items():
            summary.append({"link": _plabel(p), "variant": rl + " (Stage A)", "n": int(len(ref)),
                            "mean": {k: float(ref[k].mean()) for k in BOUNDED_METRICS},
                            "by_year": {str(y): {k: float(ref.loc[ref["start_year"] == y, k].mean()) for k in
                                                 ("delivered_t_in_year", "delivered_bulk_t", "delivered_landed_t",
                                                  "prio1_completion_share", "blackout_wait_vehicle_h")} for y in YEARS}})
    return pd.DataFrame(rows), {"cells": summary}


def bounded_verdict(summary: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Under DTE: does a variant keep the ISRU cargo (bulk >= 90 % of strategic's) and avoid the 2028 collapse
    (2028 tonnage >= 90 % of its own 2029-2031 mean)?"""
    dte = {s["variant"]: s for s in summary if s["link"] == "DTE"}
    strat_bulk = dte["strategic (Stage A)"]["mean"]["delivered_bulk_t"]
    out = []
    for v, s in dte.items():
        by = s["by_year"]
        other = float(np.mean([by[str(y)]["delivered_t_in_year"] for y in YEARS[1:]]))
        out.append({"variant": v, "bulk_t": s["mean"]["delivered_bulk_t"], "bulk_share_of_strategic": s["mean"]["delivered_bulk_t"] / strat_bulk,
                    "t_2028": by["2028"]["delivered_t_in_year"], "t_2029_2031": other,
                    "keeps_isru": bool(s["mean"]["delivered_bulk_t"] >= 0.9 * strat_bulk),
                    "avoids_2028_collapse": bool(by["2028"]["delivered_t_in_year"] >= 0.9 * other)})
    return out


def _fresh_plans(sim) -> None:
    """A diagnostic that asks dispatch questions outside a dispatch call must not read the plan memo of the previous
    call (lunarsim.dispatch._plan_hours is keyed by the engine's dispatch serial): give it a serial of its own (a
    half-step; the engine's next call adds 1, so every serial stays unique). Pure memo key; results unchanged."""
    sim._dispatch_serial = getattr(sim, "_dispatch_serial", 0) + 0.5


def pool_blocked_share(mix: str, seed: int, start_year: int, step_h: float = 24.0) -> Dict[str, Any]:
    """Stage A cell (all-supervised `mix`, DTE) run with the given start year: at most once every step_h, the share of
    the marketplace's MAX_POOL auction slots held by items blocked for every free rover (B-59 part 4)."""
    from lunarsim import Simulation, dispatch
    from experiments.phase4 import run_phase4 as R
    tag, sc, mn, mf, kw = next(c for c in R.e21a_cells("r2") if c[0]["mix"] == mix and c[0]["comms"] == "dte")
    sc = sc.with_(comms=dict(sc.comms, start_year=start_year))
    sim = Simulation(sc, mf, seed=seed, mech_kwargs=dict(kw))
    samples, nxt, orig = [], [0.0], sim._dispatch

    def look():
        free = sim.free_vehicles()
        if sim.t >= nxt[0] and free:
            nxt[0] = sim.t + step_h
            _fresh_plans(sim)
            cands = sim.comms.filter_candidates(sim, [c for c in sim.waiting if not c.stranded])
            pool = sorted(cands, key=lambda c: (c.priority, c.t_ready))[:dispatch.MAX_POOL]
            if pool:
                blocked = sum(all(dispatch._comms_blocked(sim, v, c) for v in free) for c in pool)
                samples.append((len(pool), blocked))
        return orig()

    sim._dispatch = look
    out = sim.run()
    n = np.array([s[0] for s in samples], float)
    b = np.array([s[1] for s in samples], float)
    return {"mix": mix, "seed": seed, "start_year": start_year, "samples": int(len(samples)), "step_h": step_h,
            "pool_cap": dispatch.MAX_POOL, "pool_full_share": float(np.mean(n >= dispatch.MAX_POOL)) if len(n) else None,
            "blocked_share_of_slots": float(np.mean(b / dispatch.MAX_POOL)) if len(n) else None,
            "blocked_share_of_pool": float(np.mean(b / n)) if len(n) else None,
            "delivered_t_in_year": out["delivered_kg_in_horizon"] / 1000.0}


POOL_FILTER_NOTE = {
    "rule": "lunarsim.dispatch.marketplace caps its auction at MAX_POOL items after sorting by (priority, t_ready); the "
            "only comms filter before the cap is CommsModel.filter_candidates (engine._dispatch), which runs when every "
            "vehicle is restricted and drops items whose delivery leg can NEVER be served (could_serve); the per-pair "
            "check that a job is blocked now (_comms_blocked: job_plan infinite) runs inside the auction, after the cap",
    "strict": "not filtered: only items whose delivery leg is never linked end to end are dropped; items blocked now "
              "(a planned link wait above the deferral limit) keep their slots",
    "look-ahead": "not filtered: only items whose delivery leg has a never-linked sample are dropped; items deferred "
                  "now (a forecast intervention wait above the limit) keep their slots",
}


def pool_starvation(results: str = RESULTS, seed: int = 0, bound_h: float = 24.0,
                    moments: Sequence[float] = (1000.0, 3000.0, 6000.0)) -> Dict[str, Any]:
    """One Stage F run (DTE, bound_never 'strategic'; seed 0 starts in 2028): what the marketplace's auction pool
    (dispatch.MAX_POOL oldest / most urgent items) holds at a few moments, how many of those items a free rover is
    blocked from by the look-ahead, and how many servable items wait beyond the pool cap."""
    from collections import Counter
    from lunarsim import Simulation, dispatch
    from experiments.phase4 import run_phase4 as R
    cell = next(c for c in R.e21f_cells() if c[0]["comms"] == "dte" and c[0].get("bound_h") == bound_h
                and c[0].get("bound_never") == "strategic")
    tag, sc, mn, mf, kw = cell
    sc = sc.with_(comms=dict(sc.comms, start_year=R.start_year(seed)))
    sim = Simulation(sc, mf, seed=seed, mech_kwargs=dict(kw))
    todo, snaps, orig = list(moments), [], sim._dispatch

    def look():
        while todo and sim.t >= todo[0]:
            todo.pop(0)
            _fresh_plans(sim)
            cands = sim.comms.filter_candidates(sim, [c for c in sim.waiting if not c.stranded])
            order = sorted(cands, key=lambda c: (c.priority, c.t_ready))
            pool, rest = order[:dispatch.MAX_POOL], order[dispatch.MAX_POOL:]
            free = sim.free_vehicles()
            v = free[0] if free else None
            blocked = [c for c in pool if v is not None and dispatch._comms_blocked(sim, v, c)]
            servable = [c for c in rest if v is not None and not dispatch._comms_blocked(sim, v, c)]
            lanes = Counter(f"{c.origin}->{c.dest}" for c in pool)
            snaps.append({"t_h": round(float(sim.t), 1), "waiting": len(cands), "free_rovers": len(free),
                          "pool": len(pool), "pool_blocked": len(blocked), "pool_lanes": dict(lanes.most_common(4)),
                          "beyond_cap": len(rest), "beyond_cap_servable_now": len(servable),
                          "beyond_cap_servable_lanes": dict(Counter(f"{c.origin}->{c.dest}" for c in servable).most_common(3))})
        return orig()

    sim._dispatch = look
    out = sim.run()
    return {"seed": seed, "start_year": R.start_year(seed), "bound_h": bound_h, "pool_cap": dispatch.MAX_POOL,
            "delivered_t_in_year": out["delivered_kg_in_horizon"] / 1000.0, "moments": snaps}


def pool_full_share(seed: int, bound_h: float = 24.0, step_h: float = 24.0) -> Dict[str, Any]:
    """B-60 N7: one Stage F run (DTE, bound_never 'strategic'): at most once a day, is the 40-slot auction pool full,
    and what share of the slots do CONSTR->ISRU items hold (composition only, no plans)."""
    from lunarsim import Simulation, dispatch
    from experiments.phase4 import run_phase4 as R
    tag, sc, mn, mf, kw = next(c for c in R.e21f_cells() if c[0]["comms"] == "dte" and c[0].get("bound_h") == bound_h
                               and c[0].get("bound_never") == "strategic")
    sc = sc.with_(comms=dict(sc.comms, start_year=R.start_year(seed)))
    sim = Simulation(sc, mf, seed=seed, mech_kwargs=dict(kw))
    samples, nxt, orig = [], [0.0], sim._dispatch

    def look():
        if sim.t >= nxt[0]:
            nxt[0] = sim.t + step_h
            cands = sim.comms.filter_candidates(sim, [c for c in sim.waiting if not c.stranded])
            pool = sorted(cands, key=lambda c: (c.priority, c.t_ready))[:dispatch.MAX_POOL]
            samples.append((len(pool), sum(1 for c in pool if (c.origin, c.dest) == ("CONSTR", "ISRU"))))
        return orig()

    sim._dispatch = look
    out = sim.run()
    n = np.array([s[0] for s in samples], float)
    k = np.array([s[1] for s in samples], float)
    return {"seed": seed, "start_year": R.start_year(seed), "samples": int(len(n)),
            "pool_full_share": float(np.mean(n >= dispatch.MAX_POOL)),
            "constr_isru_share_of_slots": float(np.mean(k / dispatch.MAX_POOL)),
            "delivered_t_in_year": out["delivered_kg_in_horizon"] / 1000.0}


def cmd_pool2028(a) -> None:
    """Adds bounded.pool_starvation.all_2028_seeds to E21_fit_r2.json, a few seeds per call (each run ~70 s)."""
    path = os.path.join(a.results, "E21_fit_r2.json")
    for s in (int(x) for x in a.seeds.split(",")):
        r = pool_full_share(s)
        with open(path, encoding="utf-8") as fh:
            fit = json.load(fh)
        blk = fit["bounded"]["pool_starvation"].setdefault("all_2028_seeds", {"runs": {}})
        blk["runs"][str(s)] = _json(r)
        runs = list(blk["runs"].values())
        blk.update({"bound_h": 24.0, "bound_never": "strategic", "n_runs": len(runs),
                    "pool_full_share_mean": float(np.mean([x["pool_full_share"] for x in runs])),
                    "constr_isru_share_of_slots_mean": float(np.mean([x["constr_isru_share_of_slots"] for x in runs])),
                    "note": "daily samples of the auction pool in Stage F runs (bound 24 h, never-linked as strategic, "
                            "DTE) of the 2028 seeds 0, 4, 8, 12, 16; each run must reproduce its Stage F row"})
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(fit, fh, indent=1)
            fh.write("\n")
        print(f"seed {s}: pool full {r['pool_full_share']:.0%} of {r['samples']} days, CONSTR->ISRU "
              f"{r['constr_isru_share_of_slots']:.0%} of slots, {r['delivered_t_in_year']:.1f} t", flush=True)


def cmd_bounded(a) -> None:
    t0 = time.time()
    df = load_round(a.results, "r2")
    f = load_stage_f(a.results)
    table, doc = bounded_tables(df, f)
    table.to_csv(os.path.join(a.results, "table_E21f_bounded_r2.csv"), index=False, lineterminator="\n")
    doc.update({"design": "Stage F (B-57), all-supervised fleet, 20 seeds, E21 year rule, common random numbers with Stage A: "
                          "strategic+bound at bound_h {24, 72, 168, 720} x never-linked samples {refused, left out "
                          "(as strategic)}, and strategic with stranding on never-linked samples, at DTE, relay 0.1 "
                          "and 0.5; paired against Stage A strategic and look-ahead at the same link regime",
                "verdict_dte": bounded_verdict(doc["cells"]),
                "redraws": redraw_counts(df, f),
                "never_linked_legs": never_linked_legs()})
    if a.diagnose:
        doc["pool_starvation"] = pool_starvation(a.results)
        doc["pool_starvation"]["filter_before_cap"] = POOL_FILTER_NOTE
        for key, mix in (("strict", "supervised_strict"), ("look_ahead", "supervised_strategic+avoid")):
            doc["pool_starvation"][key] = [pool_blocked_share(mix, 0, y) for y in YEARS]
    path = os.path.join(a.results, "E21_fit_r2.json")
    with open(path, encoding="utf-8") as fh:
        fit = json.load(fh)
    fit["bounded"] = _json(doc)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fit, fh, indent=1)
        fh.write("\n")
    print(f"table_E21f_bounded_r2.csv ({len(table)} rows) and E21_fit_r2.json 'bounded' written ({time.time() - t0:.0f} s)")
    for v in doc["verdict_dte"]:
        print(f"  DTE {v['variant']:45s} bulk {v['bulk_t']:6.1f} t ({v['bulk_share_of_strategic']:.0%} of strategic)  "
              f"2028 {v['t_2028']:6.1f} t vs {v['t_2029_2031']:6.1f} t  keeps ISRU {v['keeps_isru']}  avoids 2028 {v['avoids_2028_collapse']}")


# ---------------------------------------------------------------------------------------------------------
# Stage G (B-59): how fast must help come where Earth never rises?
# ---------------------------------------------------------------------------------------------------------
STAGE_G_FILE = "E21g_rescue_r2.csv"
RESCUE_METRICS = ["delivered_t_in_year", "delivered_bulk_t", "delivered_landed_t", "prio1_completion_share",
                  "delay_prio1_p90_censored_h", "blackout_wait_vehicle_h"]


STAGE_G2_FILE = "E21g2_rescue_any_r2.csv"
RESCUE_RUNS = {   # --scope: (stage file, fit-file key, table, design)
    "never_linked": (STAGE_G_FILE, "rescue", "table_E21g_rescue_r2.csv",
                     "Stage G (B-59): plain strategic, all-supervised, DTE only, 20 seeds, E21 year rule, common random "
                     "numbers with Stage A; an intervention drawn on a never-linked sample is resolved after rescue_h "
                     "{0, 24, 72, 168, 720} h and the rover drives on. The helper's own time is not modelled (optimistic). "
                     "Bounds: redraw (free second draw, Stage A strategic) and strand (no help, Stage F)."),
    "any": (STAGE_G2_FILE, "rescue_any", "table_E21g2_rescue_any_r2.csv",
            "Stage G2 (B-60): as Stage G, but every strategic intervention wait longer than rescue_h ends after rescue_h "
            "(rescue_scope 'any'), never-linked or not, so the 2028 dark spot (#188) is helped too. Also paired against "
            "the Stage G level of the same rescue_h (help only where Earth never rises). The helper's own time is not "
            "modelled (optimistic)."),
}


def load_stage_g(results: str = RESULTS, file: str = STAGE_G_FILE) -> pd.DataFrame:
    g = prepare(pd.read_csv(os.path.join(results, file)))
    for k in ("bulk", "landed"):
        g[f"delivered_{k}_t"] = g[f"delivered_{k}_kg_in_horizon"] / 1000.0
    return g


def crossing_h(levels: Sequence[float], diffs: Sequence[float]) -> float:
    """The rescue time where the mean difference (variant - reference) first falls to 0 as rescue_h grows, linear in
    log(1 + rescue_h) between levels; -inf when it is <= 0 already at the first level, inf when it stays > 0."""
    x = np.log1p(np.asarray(levels, float))
    d = np.asarray(diffs, float)
    if d[0] <= 0:
        return -math.inf
    for i in range(1, len(d)):
        if d[i] <= 0:
            return float(np.expm1(x[i - 1] + (x[i] - x[i - 1]) * d[i - 1] / (d[i - 1] - d[i])))
    return math.inf


def rescue_breakeven(g: pd.DataFrame, ref: pd.DataFrame, metric: str, boot: int = N_BOOT_R2, seed: int = 3) -> Dict[str, Any]:
    """Break-even rescue time against a reference cell: the crossing of the paired mean differences over the rescue
    levels; seed bootstrap (the same draw of seeds for every level and the reference); every draw kept."""
    levels = sorted(g["rescue_h"].unique().tolist())
    r = ref.drop_duplicates("seed").set_index("seed")[metric]
    D = pd.DataFrame({h: g[g["rescue_h"] == h].drop_duplicates("seed").set_index("seed")[metric] - r for h in levels}).dropna()
    seeds = D.index.to_numpy()
    point = crossing_h(levels, D.mean().to_numpy())
    rng = np.random.default_rng(seed)
    draws = np.array([crossing_h(levels, D.loc[rng.choice(seeds, len(seeds))].mean().to_numpy()) for _ in range(boot)])
    lab = lambda h: "beyond 720 h" if h == math.inf else "below 0 h" if h == -math.inf else round(float(h), 1)
    return {"metric": metric, "levels_h": levels, "mean_diff_by_level": [float(v) for v in D.mean()],
            "n_seeds": int(len(seeds)), "breakeven_h": lab(point),
            "ci95": [lab(_q(draws, 0.025)), lab(_q(draws, 0.975))], "median_draw": lab(_q(draws, 0.5)),
            "share_beyond_range": float(np.mean(draws == math.inf)), "share_below_range": float(np.mean(draws == -math.inf)),
            "draws": int(boot)}


def cmd_rescue(a) -> None:
    t0 = time.time()
    file, key, table_name, design = RESCUE_RUNS[a.scope]
    df = load_round(a.results, "r2")
    g = load_stage_g(a.results, file)
    g59 = load_stage_g(a.results) if a.scope == "any" else None
    A = df[(df["stage"] == "A") & (df["sensitivity"] == "none")]
    refs = {"strategic": select(A, p=0.0, mix="supervised_strategic"), "strict": select(A, p=0.0, mix="supervised_strict"),
            "look-ahead": select(A, p=0.0, mix="supervised_strategic+avoid")}
    rows, levels = [], []
    for h, cell in g.groupby("rescue_h"):
        lab = f"rescue {h:g} h"
        level_refs = dict(refs)
        if g59 is not None:                       # B-60: the same help where Earth never rises only (Stage G)
            level_refs["rescue never-linked only (B-59)"] = g59[g59["rescue_h"] == h]
        for rl, ref in level_refs.items():
            rows += _rows("rescue", rl, lab, {"rescue_h": h, "start_year": "all"}, ref, cell, RESCUE_METRICS)
            for y in YEARS:
                rows += _rows("rescue_by_year", rl, lab, {"rescue_h": h, "start_year": y}, ref[ref["start_year"] == y],
                              cell[cell["start_year"] == y], RESCUE_METRICS)
        levels.append({"rescue_h": float(h), "n": int(len(cell)),
                       "mean": {k: float(cell[k].mean()) for k in RESCUE_METRICS},
                       "censored_p90_median_h": float(cell["delay_prio1_p90_censored_h"].median()),
                       "rescues_per_run": float(cell["blackout_rescues_never_linked"].mean()),
                       "rescue_vehicle_h_per_run": float(cell["blackout_rescue_vehicle_h"].mean()),
                       "by_year": {str(y): {k: float(cell.loc[cell["start_year"] == y, k].mean()) for k in
                                            ("delivered_t_in_year", "delivered_landed_t", "prio1_completion_share")}
                                   for y in YEARS}})
    table = pd.DataFrame(rows)
    table.to_csv(os.path.join(a.results, table_name), index=False, lineterminator="\n")
    doc = {"design": design,
           "levels": levels,
           "references": {k: {"mean": {m: float(v[m].mean()) for m in RESCUE_METRICS}, "n": int(len(v)),
                              "by_year": {str(y): float(v.loc[v["start_year"] == y, "delivered_t_in_year"].mean())
                                          for y in YEARS}} for k, v in refs.items()},
           "breakeven_vs_strict": {m: rescue_breakeven(g, refs["strict"], m, a.boot)
                                   for m in ("delivered_t_in_year", "prio1_completion_share")},
           "breakeven_method": "crossing of the paired mean differences (rescue level - strict) as rescue_h grows, "
                               "linear in log(1 + rescue_h) between levels; seed bootstrap with the same draw for every "
                               "level and the reference; 'beyond 720 h' when it stays above 0, 'below 0 h' when it "
                               "starts at or below 0"}
    path = os.path.join(a.results, "E21_fit_r2.json")
    with open(path, encoding="utf-8") as fh:
        fit = json.load(fh)
    fit[key] = _json(doc)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fit, fh, indent=1)
        fh.write("\n")
    print(f"{table_name} ({len(table)} rows) and E21_fit_r2.json '{key}' written ({time.time() - t0:.0f} s)")
    for m, b in doc["breakeven_vs_strict"].items():
        print(f"  break-even vs strict, {m}: {b['breakeven_h']} (95 % {b['ci95'][0]} .. {b['ci95'][1]}; beyond range "
              f"{b['share_beyond_range']:.2%}, below {b['share_below_range']:.2%}); diffs by level "
              + ", ".join(f"{v:.3g}" for v in b["mean_diff_by_level"]))


STAGE_H_FILE = "E21h_helper_r2.csv"
HELPER_DESIGN = ("Stage H (B-62): Stage G2 with the helper's own time (lunarsim/comms.py 'helpers'). Plain strategic, "
                 "all-supervised, DTE, 20 seeds, E21 year rule, common random numbers with Stage A. A strategic "
                 "intervention wait longer than the call threshold calls a helper at BASE; it drives to the held "
                 "sample's best parking point (parking-v1.json), waits there for that point's DTE link, serves S hours "
                 "and drives home (first-fit booking; sent only when it ends the wait before its natural end). "
                 "Dedicated helpers are extra vehicles; 'from fleet' takes one LTV out of the hauling fleet. References: "
                 "strict (Stage A), strict with one extra rover (Stage B, no mast: the same vehicle count as a dedicated "
                 "helper), Stage G2 at the same threshold (the ideal helper) and always-linked strategic (Stage A).")


def _h_label(r) -> str:
    who = "from fleet" if bool(r["helpers_from_fleet"]) else "dedicated"
    s = f"{who} k={int(r['helpers_n'])}, {r['rescue_h']:g} h"
    return s + (f", S={r['helpers_service_h']:g} h" if float(r["helpers_service_h"]) != 1.0 else "")


def cmd_helper(a) -> None:
    t0 = time.time()
    df = load_round(a.results, "r2")
    h = load_stage_g(a.results, STAGE_H_FILE)
    g2 = load_stage_g(a.results, STAGE_G2_FILE)
    A = df[(df["stage"] == "A") & (df["sensitivity"] == "none")]
    B = df[(df["stage"] == "B") & (df["comms"] == "dte") & (df["policy"] == "strict") & (df["mast"] == "none")]
    always = A[(A["mix"] == "supervised_strategic") & (A["comms"] == "always")]
    refs = {"strict": select(A, p=0.0, mix="supervised_strict"), "strict + 1 rover": select(B, extra_rovers=1),
            "always-linked strategic": always}
    for k, v in refs.items():
        if len(v) != 20:
            raise SystemExit(f"reference {k!r}: {len(v)} rows, expected 20")
    h["label"] = h.apply(_h_label, axis=1)
    rows, cells = [], []
    for lab, cell in h.groupby("label", sort=False):
        th = float(cell["rescue_h"].iloc[0])
        cref = dict(refs, **{"G2 same threshold (ideal helper)": g2[g2["rescue_h"] == th]})
        for rl, ref in cref.items():
            rows += _rows("helper", rl, lab, {"rescue_h": th, "start_year": "all"}, ref, cell, RESCUE_METRICS)
            for y in YEARS:
                rows += _rows("helper_by_year", rl, lab, {"rescue_h": th, "start_year": y}, ref[ref["start_year"] == y],
                              cell[cell["start_year"] == y], RESCUE_METRICS)
        busy = cell["helper_busy_h"]
        al_y = {y: float(always.loc[always["start_year"] == y, "delivered_t_in_year"].mean()) for y in YEARS}
        by_y = {y: float(cell.loc[cell["start_year"] == y, "delivered_t_in_year"].mean()) for y in YEARS}
        ratio = {str(y): by_y[y] / al_y[y] for y in YEARS}
        d = {rl: paired(ref, cell, "delivered_t_in_year") for rl, ref in cref.items()}
        d28 = {rl: paired(ref[ref["start_year"] == 2028], cell[cell["start_year"] == 2028], "delivered_t_in_year")
               for rl, ref in cref.items()}
        cells.append({
            "label": lab, "helpers": int(cell["helpers_n"].iloc[0]), "from_fleet": bool(cell["helpers_from_fleet"].iloc[0]),
            "call_threshold_h": th, "service_h": float(cell["helpers_service_h"].iloc[0]),
            "n_haulers": int(cell["n_haulers"].iloc[0]), "n_vehicles": int(cell["n_vehicles"].iloc[0]), "n": int(len(cell)),
            "mean": {k: float(cell[k].mean()) for k in RESCUE_METRICS},
            "censored_p90_median_h": float(cell["delay_prio1_p90_censored_h"].median()),
            "by_year": {str(y): {k: float(cell.loc[cell["start_year"] == y, k].mean()) for k in
                                 ("delivered_t_in_year", "delivered_landed_t", "prio1_completion_share")} for y in YEARS},
            "share_of_always_linked_by_year": ratio,
            "within_5pct_of_always_linked_every_year": bool(min(ratio.values()) >= 0.95),
            "years_below_95pct_of_always_linked": [y for y, r in ratio.items() if r < 0.95],
            "tonnage_vs": {rl: {k: v[k] for k in ("diff", "ci_lo", "ci_hi", "rel_pct", "wilcoxon_p")} for rl, v in d.items()},
            "tonnage_2028_vs": {rl: {k: v[k] for k in ("diff", "ci_lo", "ci_hi", "rel_pct")} for rl, v in d28.items()},
            "helper": {"calls_per_run": float(cell["helper_calls"].mean()), "helps_per_run": float(cell["helper_helps"].mean()),
                       "unserved_per_run": float(cell["helper_unserved"].mean()),
                       "natural_first_per_run": float(cell["helper_natural_first"].mean()),
                       "strandings_per_run": float(cell["helper_strandings"].mean()),
                       "utilisation": float(cell["helper_utilisation"].mean()),
                       "busy_h_per_run": float(busy.mean()),
                       "busy_split_h_per_run": {"driving": float(cell["helper_drive_h"].mean()),
                                                "parked_waiting_for_earth": float(cell["helper_park_h"].mean()),
                                                "service": float(cell["helper_service_h"].mean())},
                       "busy_split_share": {"driving": float(cell["helper_drive_h"].sum() / busy.sum()),
                                            "parked_waiting_for_earth": float(cell["helper_park_h"].sum() / busy.sum()),
                                            "service": float(cell["helper_service_h"].sum() / busy.sum())},
                       "call_to_release_mean_h": float(cell["helper_call_to_release_mean_h"].mean()),
                       "call_to_release_p90_h_median_of_runs": float(cell["helper_call_to_release_p90_h"].median())},
        })
    table = pd.DataFrame(rows)
    table.to_csv(os.path.join(a.results, "table_E21h_helper_r2.csv"), index=False, lineterminator="\n")
    keep = [c["label"] for c in cells if c["within_5pct_of_always_linked_every_year"]]
    lost = {c["label"]: c["years_below_95pct_of_always_linked"] for c in cells if not c["within_5pct_of_always_linked_every_year"]}
    doc = {"design": HELPER_DESIGN, "cells": cells,
           "references": {k: {"mean": {m: float(v[m].mean()) for m in RESCUE_METRICS if m in v}, "n": int(len(v)),
                              "by_year": {str(y): float(v.loc[v["start_year"] == y, "delivered_t_in_year"].mean())
                                          for y in YEARS}} for k, v in refs.items()},
           "g2_headline_kept_by": keep, "g2_headline_lost_by": lost,
           "g2_headline": "within 5 % of the always-linked strategic tonnage in every start year (Stage G2)"}
    path = os.path.join(a.results, "E21_fit_r2.json")
    with open(path, encoding="utf-8") as fh:
        fit = json.load(fh)
    fit["helper"] = _json(doc)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fit, fh, indent=1)
        fh.write("\n")
    print(f"table_E21h_helper_r2.csv ({len(table)} rows) and E21_fit_r2.json 'helper' written ({time.time() - t0:.0f} s)")
    for c in cells:
        hp = c["helper"]
        print(f"  {c['label']:<32} {c['mean']['delivered_t_in_year']:.1f} t; by year "
              + " / ".join(f"{c['by_year'][str(y)]['delivered_t_in_year']:.1f}" for y in YEARS)
              + f"; min share of always-linked {min(c['share_of_always_linked_by_year'].values()):.2%}; helps "
              f"{hp['helps_per_run']:.1f}/run, utilisation {hp['utilisation']:.2%}, parked {hp['busy_split_share']['parked_waiting_for_earth']:.2%}")


def helper_call_log(seed: int, rescue_h: float = 168.0) -> Dict[str, Any]:
    """One Stage H replication (dedicated k = 1, S = 1 h) with every committed helper call logged: sample, leg, wait
    start, natural wait, the rover's wait with the helper and the outcome (help / natural first / unserved)."""
    from experiments.phase4 import run_phase4 as R
    from lunarsim import Simulation
    tag, sc, _, mech, kw = next(c for c in R.e21h_cells() if c[0]["rescue_h"] == rescue_h and c[0]["helpers_n"] == 1
                                and not c[0]["helpers_from_fleet"] and c[0]["helpers_service_h"] == 1.0)
    yr = R.start_year(seed)
    sim = Simulation(sc.with_(comms=dict(sc.comms, start_year=yr)), mech, seed=seed, mech_kwargs=dict(kw))
    cm = sim.comms
    last: Dict[str, Any] = {}
    log: List[Dict[str, Any]] = []
    o_sw, o_hw, o_ch = cm._sample_wait, cm._helper_wait, cm._commit_helpers

    def sample_wait(a, b, u, t):
        last["leg"] = f"{a}->{b}"
        return o_sw(a, b, u, t)

    def helper_wait(sid, ti, w_nat):
        w = o_hw(sid, ti, w_nat)
        cm._hp_pend[-1].update(sid=sid, w_nat=w_nat, leg=last.get("leg"), held=w)
        return w

    def commit_helpers():
        log.extend(dict(r) for r in cm._hp_pend)
        o_ch()

    cm._sample_wait, cm._helper_wait, cm._commit_helpers = sample_wait, helper_wait, commit_helpers
    out = sim.run()
    return {"seed": seed, "start_year": yr, "horizon_h": float(sc.horizon_h), "calls": log,
            "delivered_t_in_year": out["delivered_kg_in_horizon"] / 1000.0, "start_h": cm.start_h}


def cmd_helper168(a) -> None:
    """B-62 addendum: why the 168 h helper loses more in 2029 than in 2028 (Stage H vs G2 at 168 h, paired by seed)."""
    import gzip
    t0 = time.time()
    h = pd.read_csv(os.path.join(a.results, STAGE_H_FILE), float_precision="round_trip")
    h = h[(h["rescue_h"] == 168.0) & (h["helpers_n"] == 1) & (~h["helpers_from_fleet"].astype(bool)) & (h["helpers_service_h"] == 1.0)]
    g2 = pd.read_csv(os.path.join(a.results, STAGE_G2_FILE), float_precision="round_trip")
    g2 = g2[g2["rescue_h"] == 168.0]
    with open(os.path.join(ROOT, "data", "comms", "connecting_ridge", "parking-v1.json"), encoding="utf-8") as fh:
        park = json.load(fh)
    with open(os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1-samples.json.gz"), "rb") as fh:
        sdoc = json.loads(gzip.decompress(fh.read()))
    n_s = int(sdoc["time"]["n"])
    linked = lambda code: windows_mask(code, n_s)
    for d_ in (h, g2):
        d_["delivered_bulk_t"] = d_["delivered_bulk_kg_in_horizon"] / 1000.0
        d_["delivered_landed_t"] = d_["delivered_landed_kg_in_horizon"] / 1000.0
    paired_y = {}
    for y in YEARS:
        hy, gy = h[h["start_year"] == y], g2[g2["start_year"] == y]
        paired_y[str(y)] = {m: {k: paired(gy, hy, m)[k] for k in ("ref_mean", "cell_mean", "diff", "ci_lo", "ci_hi")}
                            for m in ("delivered_t_in_year", "delivered_bulk_t", "delivered_landed_t",
                                      "blackout_wait_vehicle_h")}
    dd = lambda y: (h[h["start_year"] == y].set_index("seed")["delivered_t_in_year"]
                    - g2[g2["start_year"] == y].set_index("seed")["delivered_t_in_year"]).dropna().to_numpy()
    d28, d29 = dd(2028), dd(2029)
    contrast = {"per_seed_diff_2028": [round(float(v), 1) for v in d28], "per_seed_diff_2029": [round(float(v), 1) for v in d29],
                "mean_diff_2029_minus_2028": float(d29.mean() - d28.mean()),
                "welch_t_p": float(stats.ttest_ind(d29, d28, equal_var=False).pvalue),
                "mann_whitney_p": float(stats.mannwhitneyu(d29, d28, alternative="two-sided").pvalue)}
    rows = []
    for seed in sorted(h["seed"].unique().tolist()):
        r = helper_call_log(int(seed))
        want = float(h.loc[h["seed"] == seed, "delivered_t_in_year"].iloc[0])
        if r["delivered_t_in_year"] != want:
            raise SystemExit(f"helper168: seed {seed} does not reproduce its Stage H row")
        H = r["horizon_h"]
        for c in r["calls"]:
            held = min(c["ti"] + c["held"], H) - c["ti"]                 # inside the year
            excess = max(0.0, held - min(168.0, H - c["ti"]))           # G2 holds every capped wait 168 h
            rows.append({"seed": int(seed), "start_year": r["start_year"], "sample": c["sid"], "leg": c["leg"],
                         "kind": c["kind"], "ti": c["ti"], "excess_h": excess,
                         "month": int(min(11, c["ti"] // (H / 12.0)))})
    df = pd.DataFrame(rows)
    edges = month_edges_hourly_2028()
    out: Dict[str, Any] = {"cell": "dedicated k=1, 168 h (S = 1 h) vs Stage G2 168 h", "paired_by_start_year": paired_y,
                           "excess_definition": "rover-hours held inside the year beyond G2's cap: per call, the wait "
                                                "with the helper minus min(168 h, hours left in the year)",
                           "runs_reproduce_stage_h": True, "year_contrast_tonnage": contrast, "by_year": {}}
    for y in YEARS:
        d = df[df["start_year"] == y]
        runs = d["seed"].nunique()
        tot = float(d["excess_h"].sum()) / runs
        top_s = d.groupby("sample")["excess_h"].sum().sort_values(ascending=False).head(5) / runs
        top_l = d.groupby("leg")["excess_h"].sum().sort_values(ascending=False).head(5) / runs
        lo, hi = edges[12 * (y - 2028)], edges[12 * (y - 2027)]
        samples = []
        for s, ex in top_s.items():
            s = int(s)
            rec = park["samples"].get(str(s))
            own = linked(sdoc["series"][sdoc["samples"][s]["w"][0]])
            dark = np.flatnonzero(~own[lo:hi]) + lo
            entry = {"sample": s, "excess_h_per_run": round(float(ex), 1),
                     "share_of_year_excess": round(float(ex) / tot, 5) if tot else None,
                     "calls_per_run": round(float((d["sample"] == s).sum()) / runs, 2),
                     "own_link_share_in_year": round(float(own[lo:hi].mean()), 5), "dark_hours_in_year": int(len(dark))}
            if rec and rec["top"]:
                p = park["points"][rec["top"][0]["point"]]
                pm = (linked(sdoc["series"][sdoc["samples"][p["sample"]]["w"][0]]) if p["kind"] == "route"
                      else linked(p["windows"]))
                W = _wait_until(pm)
                entry["best_point"] = {"kind": p["kind"], "dist_m": rec["top"][0]["dist_m"],
                                       "link_share_in_year": round(float(pm[lo:hi].mean()), 5),
                                       "share_of_dark_hours_linked_within_0_24_168h":
                                           [round(float((W[dark] <= x).mean()), 5) if len(dark) else None for x in (0, 24, 168)]}
            samples.append(entry)
        by_kind = (d.groupby("kind")["excess_h"].sum() / runs).round(1).to_dict()
        out["by_year"][str(y)] = {"runs": int(runs), "excess_h_per_run": round(tot, 1),
                                  "calls_per_run": round(len(d) / runs, 2), "excess_by_kind_h_per_run": by_kind,
                                  "excess_by_call_month_h_per_run": [round(float(d.loc[d["month"] == m, "excess_h"].sum()) / runs, 1)
                                                                     for m in range(12)],
                                  "top_samples": samples,
                                  "top_legs": [{"leg": k, "excess_h_per_run": round(float(v), 1),
                                                "share_of_year_excess": round(float(v) / tot, 5) if tot else None}
                                               for k, v in top_l.items()]}
    b8, b9, p8, p9 = out["by_year"]["2028"], out["by_year"]["2029"], paired_y["2028"], paired_y["2029"]
    top = lambda b: sum(s_["share_of_year_excess"] for s_ in b["top_samples"])
    s188 = lambda b: next((s_ for s_ in b["top_samples"] if s_["sample"] == 188), None)
    leg = lambda b, k: next((l_["share_of_year_excess"] for l_ in b["top_legs"] if l_["leg"] == k), 0.0)
    pk = lambda b: sorted(range(12), key=lambda m: -b["excess_by_call_month_h_per_run"][m])[:3]
    mon = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    t8, t9 = s188(b8), s188(b9)
    out["summary"] = (
        f"The 168 h helper loses {-p9['delivered_t_in_year']['diff']:.1f} t against G2 168 h in 2029 "
        f"({p9['delivered_t_in_year']['cell_mean']:.1f} vs {p9['delivered_t_in_year']['ref_mean']:.1f}; 95 % "
        f"[{p9['delivered_t_in_year']['ci_lo']:.1f}, {p9['delivered_t_in_year']['ci_hi']:.1f}]) and "
        f"{-p8['delivered_t_in_year']['diff']:.1f} t in 2028 ([{p8['delivered_t_in_year']['ci_lo']:.1f}, "
        f"{p8['delivered_t_in_year']['ci_hi']:.1f}]); the per-seed losses differ between the years (Welch p = "
        f"{contrast['welch_t_p']:.4f}, Mann-Whitney p = {contrast['mann_whitney_p']:.4f}). It is not more held time: the "
        f"rover-hours held beyond G2's cap are {b8['excess_h_per_run']:,.0f} h a run in 2028 and {b9['excess_h_per_run']:,.0f} "
        f"in 2029 (paired extra intervention waiting {p8['blackout_wait_vehicle_h']['diff']:,.0f} and "
        f"{p9['blackout_wait_vehicle_h']['diff']:,.0f} vehicle-hours), at the same five samples (#4 ISRU, #188, #189, #190, "
        f"#230: {top(b8):.0%} and {top(b9):.0%} of it) on the same legs (ISRU->CONSTR {leg(b8, 'ISRU->CONSTR'):.0%} / "
        f"{leg(b9, 'ISRU->CONSTR'):.0%}, CONSTR->ISRU {leg(b8, 'CONSTR->ISRU'):.0%} / {leg(b9, 'CONSTR->ISRU'):.0%}). It is "
        f"not a worse parking point: #188's best point is linked {t8['best_point']['link_share_in_year']:.2%} of 2028 and "
        f"{t9['best_point']['link_share_in_year']:.2%} of 2029, and links "
        f"{t8['best_point']['share_of_dark_hours_linked_within_0_24_168h'][2]:.2%} / "
        f"{t9['best_point']['share_of_dark_hours_linked_within_0_24_168h'][2]:.2%} of #188's dark hours within 168 h; "
        f"the other four best points likewise. #188's dark spell does run on into 2029 (it holds {t9['excess_h_per_run']:,.0f} "
        f"h a run against {t8['excess_h_per_run']:,.0f}), yet the year's total excess is unchanged. The 2029 loss is bulk regolith ({p9['delivered_bulk_t']['diff']:.1f} t "
        f"[{p9['delivered_bulk_t']['ci_lo']:.1f}, {p9['delivered_bulk_t']['ci_hi']:.1f}] of "
        f"{p9['delivered_t_in_year']['diff']:.1f}): the same held hours cost more of the CONSTR->ISRU flow in 2029. The "
        f"tally does not show why; the excess falls at different times (2029 peaks in {', '.join(mon[m] for m in pk(b9))}; "
        f"2028 in {', '.join(mon[m] for m in pk(b8))}), a candidate, not a tested cause.")
    path = os.path.join(a.results, "E21_fit_r2.json")
    with open(path, encoding="utf-8") as fh:
        fit = json.load(fh)
    fit["helper"]["diagnosis_168h"] = _json(out)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(fit, fh, indent=1)
        fh.write("\n")
    print(f"E21_fit_r2.json helper.diagnosis_168h written ({time.time() - t0:.0f} s)")
    for y, b in out["by_year"].items():
        print(f"  {y}: excess {b['excess_h_per_run']} h/run over {b['calls_per_run']} calls; by kind {b['excess_by_kind_h_per_run']}; "
              f"tonnage diff {paired_y[y]['delivered_t_in_year']['diff']:.1f}; top samples "
              + ", ".join(f"#{s['sample']} {s['excess_h_per_run']} h ({s['share_of_year_excess']:.0%})" for s in b["top_samples"]))


def windows_mask(code: Sequence[int], n: int) -> np.ndarray:
    from lunarsim.comms import decode_windows, windows_to_mask
    return windows_to_mask(decode_windows(code), n)


def _wait_until(linked: np.ndarray) -> np.ndarray:
    n = len(linked)
    if not linked.any():
        return np.full(n, np.inf)
    idx = np.where(np.concatenate([linked, linked]), np.arange(2 * n), 4 * n)
    return (np.minimum.accumulate(idx[::-1])[::-1][:n] - np.arange(n)).astype(float)


def month_edges_hourly_2028() -> List[int]:
    """Hour indices of every month start 2028-01 .. 2031-12 (and the end) in the hourly sample series."""
    import calendar
    out, hh = [], 0
    for y in YEARS:
        for m in range(1, 13):
            out.append(hh)
            hh += 24 * calendar.monthrange(y, m)[1]
    return out + [hh]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("rounds", help="round-2 rows equal their round-1 twins in every round-1 column")
    p.add_argument("--results", default=RESULTS)
    p = sub.add_parser("demand")
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--mix", default="supervised_strict")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--max-seconds", type=float, default=540.0)
    p = sub.add_parser("fit")
    p.add_argument("--round", default="r1", choices=("r1", "r2"),
                   help="r2 reads the *_r2 files and writes *_r2 outputs (round-1 outputs are left as they are)")
    p.add_argument("--boot", type=int, default=None, help=f"break-even draws (default {N_BOOT}; round 2 {N_BOOT_R2})")
    p.add_argument("--boot-law", type=int, default=N_BOOT, help="law bootstrap draws (round 2)")
    p.add_argument("--results", default=RESULTS)
    p = sub.add_parser("bounded", help="Stage F (B-57) -> table_E21f_bounded_r2.csv and E21_fit_r2.json 'bounded'")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--diagnose", action="store_true", help="also run one Stage F year to show the auction-pool starvation")
    p = sub.add_parser("rescue", help="Stage G (B-59) -> table_E21g_rescue_r2.csv and E21_fit_r2.json 'rescue'; "
                                      "--scope any: Stage G2 (B-60) -> table_E21g2_rescue_any_r2.csv, 'rescue_any'")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--boot", type=int, default=N_BOOT_R2)
    p.add_argument("--scope", default="never_linked", choices=tuple(RESCUE_RUNS))
    p = sub.add_parser("helper", help="Stage H (B-62) -> table_E21h_helper_r2.csv and E21_fit_r2.json 'helper'")
    p.add_argument("--results", default=RESULTS)
    p = sub.add_parser("helper168", help="B-62 addendum: the 168 h helper's losses by start year (20 tally reruns)")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--max-seconds", type=float, default=540.0)
    p = sub.add_parser("pool2028", help="B-60 N7: pool-full share in the 2028 seeds of the bounded rule (a few per call)")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--seeds", default="0,4,8,12,16")
    p.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    if a.cmd == "fit":
        a.boot = a.boot or (N_BOOT if a.round == "r1" else N_BOOT_R2)
        if a.round != "r1":
            return cmd_fit_r2(a)
    if a.cmd in ("pool2028", "helper168") and a.max_seconds > 0:
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    {"demand": cmd_demand, "fit": cmd_fit, "rounds": cmd_rounds, "bounded": cmd_bounded, "rescue": cmd_rescue,
     "pool2028": cmd_pool2028, "helper": cmd_helper, "helper168": cmd_helper168}[a.cmd](a)


if __name__ == "__main__":
    main()
