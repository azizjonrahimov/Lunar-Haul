"""E21 analysis (B-43): paired effects, the delay-coverage law, delay-based break-evens, operator compression and the
throughput bound, from the E21 replications (results/E21a_comms_autonomy.csv, E21b_breakeven.csv, and
E21c_pads_criterion.csv when present).

    python experiments/phase4/analyse_e21.py demand [--seeds 20] [--max-seconds 540]   # -> results/E21_demand_by_dest.csv
    python experiments/phase4/analyse_e21.py fit [--boot 400]                          # -> the tables below

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
STAGE_FILES = ("E21a_comms_autonomy.csv", "E21b_breakeven.csv", "E21c_pads_criterion.csv")
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
    return {**out, "diff": m, "ci_lo": m - h, "ci_hi": m + h, "rel_pct": rel}


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
            "reference", "cell", "metric", "n", "ref_mean", "cell_mean", "diff", "ci_lo", "ci_hi", "rel_pct", "ci_excludes_0"]
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
    a = df[df["stage"] == "A"]
    rows = []
    for mix in mixes:
        g = a[a["mix"] == mix]
        full = select(g, p=1.0)
        for p, h in g.groupby(g["p"].fillna(-1.0)):
            vs = paired(full, h, "operator_peak_demand") if len(full) and p >= 0 else {}
            ratio = (h["operator_peak_demand"] / h["operator_mean_demand"]).replace([np.inf, -np.inf], np.nan)
            n_ops = int(h["n_operators"].iloc[0])
            n = int(ratio.notna().sum())
            t = stats.t.ppf(0.975, max(n - 1, 1))
            rows.append({"mix": mix, "comms": h["comms"].iloc[0], "p": np.nan if p < 0 else p, "n_seeds": int(len(h)),
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


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("demand")
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--mix", default="supervised_strict")
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--max-seconds", type=float, default=540.0)
    p = sub.add_parser("fit")
    p.add_argument("--boot", type=int, default=N_BOOT)
    p.add_argument("--results", default=RESULTS)
    a = ap.parse_args(argv)
    {"demand": cmd_demand, "fit": cmd_fit}[a.cmd](a)


if __name__ == "__main__":
    main()
