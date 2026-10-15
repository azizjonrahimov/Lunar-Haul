"""The dispersion / standoff / keep-out law (E20) from the E17 and E18 raw CSVs.

    python experiments/phase3/fit_law.py                 # results/E17_dispersion_standoff.csv, E18_plume.csv
    python experiments/phase3/fit_law.py --results DIR --boot 1000

Writes results/table_E17.csv and table_E18.csv (cell means with 95% CIs, paired differences on common seeds
against the reference cell with seed-bootstrap CIs), results/E20_fit.json and table_E20.csv (the OLS fit with
bootstrap CIs; the design is stated in the JSON) and table_E20_siting.csv (hauling cost plus amortised pad
construction cost against standoff, with the minimum-cost standoff per cost assumption).

Costs added here, not in the engine (B-15 addendum):
    cost_per_kg_with_energy_usd_<p> = cost_per_kg_usd + p * energy_kwh / delivered_kg
for an energy price p in ENERGY_PRICES ($/kWh delivered on the surface; Assumed, swept, no source).
Pad construction cost: Metzger & Autry 2022, $130 M / $229 M / $548 M at $10K / $100K / $300K per kg of
transport (Spec), amortised over PAD_LIFE_YEARS. It does not depend on standoff, so it shifts the total and
not the minimum-cost standoff; the siting table shows the scale of the two terms side by side.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(ROOT, "results")
ENERGY_PRICES = (0, 500, 2000, 5000)          # $/kWh, Assumed (swept)
PAD_COST_MUSD = {"10K": 130.0, "100K": 229.0, "300K": 548.0}   # Metzger & Autry 2022, by $/kg transport (Spec)
PAD_LIFE_YEARS = 10.0
N_BOOT = 1000

MEAN_METRICS = ["delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "delivered_share", "delay_mean_h",
                "cost_per_kg_usd", "energy_kwh", "km_total", "utilisation", "jobs", "repositions", "km_reposition",
                "operator_hours", "plume_standdowns", "standdown_vehicle_h", "landing_miss_m_mean", "offpad_landings",
                "failed_landings", "cargo_lost_kg", "km_offpad_extra", "interventions", "intervention_h"]
PAIRED_METRICS = ["delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "cost_per_kg_usd", "energy_kwh", "km_total"]
E17_FACTORS = ["scenario", "phase", "n_vehicles", "mechanism", "sigma_scale", "pad_standoff_km"]
E18_FACTORS = ["scenario", "phase", "n_vehicles", "mechanism", "night_fraction", "pad_standoff_km", "keepout_km", "standdown_h"]
E19_FACTORS = ["scenario", "n_vehicles", "mechanism", "autonomy", "rtt_s"]


def energy_cols(prices=ENERGY_PRICES):
    return [f"cost_per_kg_with_energy_usd_{p}" for p in prices]


def add_energy_cost(df, prices=ENERGY_PRICES):
    """cost_per_kg_usd plus priced driving energy per delivered kg (same denominator as the engine's cost_per_kg_usd)."""
    df = df.copy()
    kg = df["delivered_kg"].clip(lower=1e-9)
    for p in prices:
        df[f"cost_per_kg_with_energy_usd_{p}"] = df["cost_per_kg_usd"] + p * df["energy_kwh"] / kg
    return df


def ci95(x):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return 1.96 * x.std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan


def cell_means(df, factors, metrics):
    """One row per cell: <m> (mean over seeds), <m>_ci95, n_seeds."""
    metrics = [m for m in metrics if m in df.columns]
    rows = []
    for key, sub in df.groupby(factors, sort=True):
        row = dict(zip(factors, key))
        row["n_seeds"] = int(sub["seed"].nunique())
        for m in metrics:
            v = sub[m].to_numpy(float)
            row[m] = float(np.nanmean(v)) if np.isfinite(v).any() else np.nan
            row[m + "_ci95"] = ci95(v)
        rows.append(row)
    return pd.DataFrame(rows)


def paired(df, factors, metrics, ref, B=N_BOOT, seed=0, prefix="d"):
    """Per cell: mean difference to the reference cell on common seeds and a percentile bootstrap 95% CI over
    seeds (B resamples). The reference cell has the factor values of the cell with `ref` substituted."""
    metrics = [m for m in metrics if m in df.columns]
    rng = np.random.default_rng(seed)
    by_key = {key if isinstance(key, tuple) else (key,): sub.set_index("seed")[metrics]
              for key, sub in df.groupby(factors, sort=True)}
    rows = []
    for key, a in by_key.items():
        rkey = tuple(ref.get(f, v) for f, v in zip(factors, key))
        if rkey == key or rkey not in by_key:
            continue
        b = by_key[rkey]
        common = a.index.intersection(b.index)
        if len(common) == 0:
            continue
        D = a.loc[common].to_numpy(float) - b.loc[common].to_numpy(float)       # (n, m)
        n = len(common)
        idx = rng.integers(0, n, (B, n))
        boot = np.nanmean(D[idx], axis=1)                                      # (B, m)
        lo, hi = np.nanpercentile(boot, [2.5, 97.5], axis=0)
        row = dict(zip(factors, key))
        row["n_common"] = n
        for j, m in enumerate(metrics):
            row[f"{prefix}_{m}"] = float(np.nanmean(D[:, j]))
            row[f"{prefix}_{m}_lo"] = float(lo[j])
            row[f"{prefix}_{m}_hi"] = float(hi[j])
        rows.append(row)
    return pd.DataFrame(rows)


def _merge(base, extra, factors):
    return base if extra.empty else base.merge(extra, on=factors, how="left")


def table_e17(df, B=N_BOOT):
    df = add_energy_cost(df)
    metrics = MEAN_METRICS + energy_cols()
    pm = PAIRED_METRICS + ["cost_per_kg_with_energy_usd_2000"]
    t = cell_means(df, E17_FACTORS, metrics)
    t = _merge(t, paired(df, E17_FACTORS, pm, {"pad_standoff_km": 1.0}, B=B, prefix="dD1"), E17_FACTORS)    # vs standoff 1 km, same sigma
    t = _merge(t, paired(df, E17_FACTORS, pm, {"sigma_scale": 1.0}, B=B, prefix="dS1"), E17_FACTORS)        # vs sigma 1, same standoff
    return t


def table_e18(df, B=N_BOOT):
    df = add_energy_cost(df)
    metrics = MEAN_METRICS + energy_cols()
    pm = PAIRED_METRICS + ["cost_per_kg_with_energy_usd_2000", "plume_standdowns", "standdown_vehicle_h", "repositions"]
    t = cell_means(df, E18_FACTORS, metrics)
    t = _merge(t, paired(df, E18_FACTORS, pm, {"keepout_km": 0.0, "standdown_h": 0.0}, B=B, prefix="dNP"), E18_FACTORS)  # vs no plume
    return t


def table_e19(df, B=N_BOOT):
    df = add_energy_cost(df)
    metrics = MEAN_METRICS + energy_cols() + ["unmet_operator_waits", "operator_cost_musd"]
    pm = PAIRED_METRICS + ["cost_per_kg_with_energy_usd_2000", "interventions", "operator_hours"]
    t = cell_means(df, E19_FACTORS, metrics)
    sup = df[df["autonomy"] == "supervised"]
    if len(sup):
        rtt = float(sup["rtt_s"].iloc[0])
        t = _merge(t, paired(df, E19_FACTORS, pm, {"autonomy": "supervised", "rtt_s": rtt}, B=B, prefix="dSUP"), E19_FACTORS)
    return t


# ---------------------------------------------------------------------------
# The law: OLS with seed-bootstrap CIs
# ---------------------------------------------------------------------------
MECH_BASE = "inhouse"
MECH_DUMMIES = ("marketplace", "pooled_greedy", "central_assign")
TERMS = ["const", "log_sigma", "standoff", "keepout", "standdown", "util", "night_fraction",
         "log_sigma:standoff", "keepout:standdown", "keepout:util", "standdown:util", "standoff:util", "log_sigma:util"]
DESIGN_NOTE = {
    "rows": "one simulated year (one seed of one cell) pooled from E17 (dispersion x standoff) and E18 (keep-out), "
            "classical landings, driving-v1 legs, Connecting ridge terrain",
    "responses": {"log_delay_prio1_mean_h": "ln of the mean urgent-item delay (h); 100*(exp(b)-1) = % per unit",
                  "sl24_prio1": "share of urgent items delivered within 24 h (linear)",
                  "cost_per_kg_usd": "fleet + operator cost per delivered kg (linear)",
                  "cost_per_kg_with_energy_usd_<p>": "the same plus p $/kWh x energy_kwh / delivered_kg (p Assumed, swept)"},
    "regressors": TERMS + [f"mech_{m}" for m in MECH_DUMMIES],
    "log_sigma": "ln(sigma_scale) of the landing-miss vector (E18 rows: 0)",
    "standoff": "pad_standoff_km", "keepout": "plume keepout_km (E17 and no-plume rows: 0)", "standdown": "plume standdown_h (0 likewise)",
    "util": "mean utilisation of the reference cell (sigma 1, standoff 1 km, no keep-out) of the same scenario, mechanism and "
            "night fraction: a group-level covariate for fleet load, not the row's own utilisation",
    "controls": "mechanism dummies (inhouse is the base) and night_fraction; the per-mechanism fits drop the dummies",
    "estimator": "ordinary least squares, numpy lstsq; columns constant in the data are dropped and listed",
    "ci": "percentile bootstrap over seeds, N_BOOT resamples: seeds drawn with replacement, every row of a drawn seed enters "
          "with that seed's multiplicity (weighted normal equations), so the CI respects the common-random-number pairing",
}


def _util_reference(df):
    """Reference-cell mean utilisation per (scenario, mechanism, night_fraction); the group mean if that cell is absent."""
    g = ["scenario", "mechanism", "night_fraction"]
    ref = df[(df["sigma_scale"] == 1.0) & (df["pad_standoff_km"] == 1.0) & (df["keepout_km"] == 0.0) & (df["standdown_h"] == 0.0)]
    u = ref.groupby(g)["utilisation"].mean()
    fallback = df.groupby(g)["utilisation"].mean()
    u = fallback.to_frame("u_fb").join(u.rename("u_ref"), how="left")
    u["util"] = u["u_ref"].fillna(u["u_fb"])
    return df.merge(u[["util"]].reset_index(), on=g, how="left")["util"].to_numpy(float)


def design(df, mech_dummies=True):
    """(X, names) for the law. df needs sigma_scale, pad_standoff_km, keepout_km, standdown_h, night_fraction,
    scenario, mechanism, utilisation."""
    d = df.copy()
    for c, v in (("keepout_km", 0.0), ("standdown_h", 0.0), ("sigma_scale", 1.0), ("night_fraction", 0.15)):
        if c not in d.columns:
            d[c] = v
        d[c] = d[c].fillna(v)
    ls = np.log(d["sigma_scale"].to_numpy(float))
    D = d["pad_standoff_km"].to_numpy(float)
    R = d["keepout_km"].to_numpy(float)
    T = d["standdown_h"].to_numpy(float)
    u = _util_reference(d)
    nf = d["night_fraction"].to_numpy(float)
    cols = [np.ones(len(d)), ls, D, R, T, u, nf, ls * D, R * T, R * u, T * u, D * u, ls * u]
    names = list(TERMS)
    if mech_dummies:
        for m in MECH_DUMMIES:
            cols.append((d["mechanism"] == m).to_numpy(float))
            names.append(f"mech_{m}")
    return np.column_stack(cols), names


def fit_ols(X, y, seeds, B=N_BOOT, rng_seed=0):
    """OLS of y on X; percentile bootstrap CIs over seeds via per-seed normal equations.
    Returns dict(coef, lo, hi, n, r2, sigma, dropped) with constant columns removed (their index in `dropped`)."""
    ok = np.isfinite(y) & np.isfinite(X).all(axis=1)
    X, y, seeds = X[ok], y[ok], np.asarray(seeds)[ok]
    n, K = X.shape
    keep = [j for j in range(K) if j == 0 or X[:, j].std() > 1e-12]
    dropped = [j for j in range(K) if j not in keep]
    X = X[:, keep]
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ beta
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((res ** 2).sum()) / ss_tot if ss_tot > 0 else np.nan
    sigma = float(np.sqrt((res ** 2).sum() / max(n - X.shape[1], 1)))
    uniq, inv = np.unique(seeds, return_inverse=True)
    S = len(uniq)
    Kk = X.shape[1]
    G = np.zeros((S, Kk, Kk))
    g = np.zeros((S, Kk))
    for s in range(S):
        Xs, ys = X[inv == s], y[inv == s]
        G[s] = Xs.T @ Xs
        g[s] = Xs.T @ ys
    rng = np.random.default_rng(rng_seed)
    draws = rng.integers(0, S, (B, S))
    W = np.zeros((B, S))
    for b in range(B):
        W[b] = np.bincount(draws[b], minlength=S)
    Gb = np.einsum("bs,skl->bkl", W, G)
    gb = np.einsum("bs,sk->bk", W, g)
    try:
        betas = np.linalg.solve(Gb, gb[..., None])[..., 0]
    except np.linalg.LinAlgError:
        betas = np.stack([np.linalg.lstsq(Gb[b], gb[b], rcond=None)[0] for b in range(B)])
    lo, hi = np.percentile(betas, [2.5, 97.5], axis=0)
    return {"coef": beta, "lo": lo, "hi": hi, "n": int(n), "r2": r2, "sigma": sigma, "dropped": dropped, "keep": keep,
            "n_seeds": int(S), "boot": int(B)}


def _responses(df):
    out = {"log_delay_prio1_mean_h": np.log(np.clip(df["delay_prio1_mean_h"].to_numpy(float), 1e-6, None)),
           "sl24_prio1": df["sl24_prio1"].to_numpy(float), "cost_per_kg_usd": df["cost_per_kg_usd"].to_numpy(float)}
    for c in energy_cols():
        if c in df.columns and not c.endswith("_0"):
            out[c] = df[c].to_numpy(float)
    return out


def fit_law(df, B=N_BOOT):
    """Pooled and per-mechanism fits of every response. Returns (json-able dict, long table)."""
    df = add_energy_cost(df)
    seeds = df["seed"].to_numpy(int)
    out = {"design": dict(DESIGN_NOTE, n_boot=B), "pooled": {}, "by_mechanism": {}}
    rows = []

    def record(store, subset, X, names, sub_df, sub_seeds):
        for resp, y in _responses(sub_df).items():
            f = fit_ols(X, y, sub_seeds, B=B)
            kept = [names[j] for j in f["keep"]]
            store[resp] = {"n": f["n"], "n_seeds": f["n_seeds"], "r2": f["r2"], "residual_sd": f["sigma"],
                           "dropped_constant": [names[j] for j in f["dropped"]],
                           "coef": {t: {"coef": float(c), "ci95": [float(l), float(h)]} for t, c, l, h in zip(kept, f["coef"], f["lo"], f["hi"])}}
            for t, c, l, h in zip(kept, f["coef"], f["lo"], f["hi"]):
                r = {"response": resp, "subset": subset, "term": t, "coef": float(c), "ci_lo": float(l), "ci_hi": float(h),
                     "n": f["n"], "n_seeds": f["n_seeds"], "r2": f["r2"]}
                if resp.startswith("log_"):
                    r["pct_per_unit"] = 100.0 * (np.exp(c) - 1.0)
                rows.append(r)

    X, names = design(df, mech_dummies=True)
    record(out["pooled"], "pooled", X, names, df, seeds)
    for m, sub in df.groupby("mechanism"):
        Xm, nm = design(sub, mech_dummies=False)
        out["by_mechanism"][m] = {}
        record(out["by_mechanism"][m], m, Xm, nm, sub, sub["seed"].to_numpy(int))
    return out, pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Pad siting: hauling cost + amortised pad cost against standoff
# ---------------------------------------------------------------------------
def siting_table(e17, prices=ENERGY_PRICES, pad_costs=PAD_COST_MUSD, life=PAD_LIFE_YEARS):
    """Per (scenario, mechanism, sigma_scale, energy price, pad case, standoff): hauling cost per year (operator +
    priced energy, M$), amortised pad cost (M$/yr), their total, the fleet capital for context, and min_cost marking
    the minimum-cost standoff within the group. Means over seeds of the E17 cells."""
    g = ["scenario", "phase", "n_vehicles", "mechanism", "sigma_scale", "pad_standoff_km"]
    agg = e17.groupby(g).agg(n_seeds=("seed", "nunique"), operator_cost_musd=("operator_cost_musd", "mean"),
                             energy_kwh=("energy_kwh", "mean"), delivered_kg=("delivered_kg", "mean"),
                             fleet_cost_musd=("fleet_cost_musd", "mean"), cargo_lost_kg=("cargo_lost_kg", "mean"),
                             offpad_landings=("offpad_landings", "mean"), km_total=("km_total", "mean"),
                             delay_prio1_mean_h=("delay_prio1_mean_h", "mean")).reset_index()
    rows = []
    for p in prices:
        for case, pad in pad_costs.items():
            t = agg.copy()
            t["energy_price_usd_per_kwh"] = p
            t["pad_case_usd_per_kg_transport"] = case
            t["pad_cost_musd"] = pad
            t["pad_musd_per_year"] = pad / life
            t["energy_cost_musd"] = p * t["energy_kwh"] / 1e6
            t["hauling_musd"] = t["operator_cost_musd"] + t["energy_cost_musd"]
            t["total_musd"] = t["hauling_musd"] + t["pad_musd_per_year"]
            t["total_usd_per_kg"] = 1e6 * t["total_musd"] / t["delivered_kg"].clip(lower=1e-9)
            t["system_usd_per_kg"] = 1e6 * (t["total_musd"] + t["fleet_cost_musd"]) / t["delivered_kg"].clip(lower=1e-9)
            rows.append(t)
    out = pd.concat(rows, ignore_index=True)
    grp = ["scenario", "mechanism", "sigma_scale", "energy_price_usd_per_kwh", "pad_case_usd_per_kg_transport"]
    out["min_cost"] = out["total_musd"] == out.groupby(grp)["total_musd"].transform("min")
    out["flag"] = "hauling Modelled; energy price Assumed; pad cost Spec (Metzger & Autry 2022), independent of standoff"
    return out.sort_values(grp + ["pad_standoff_km"]).reset_index(drop=True)


def siting_minimum(sit):
    """The minimum-cost standoff per (scenario, mechanism, sigma_scale, energy price, pad case)."""
    cols = ["scenario", "mechanism", "sigma_scale", "energy_price_usd_per_kwh", "pad_case_usd_per_kg_transport",
            "pad_standoff_km", "hauling_musd", "pad_musd_per_year", "total_musd", "total_usd_per_kg"]
    return sit[sit["min_cost"]][cols].drop_duplicates(cols[:5]).reset_index(drop=True)


# ---------------------------------------------------------------------------
def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--results", default=RESULTS)
    p.add_argument("--boot", type=int, default=N_BOOT)
    a = p.parse_args(argv)
    res = a.results
    e17p, e18p = os.path.join(res, "E17_dispersion_standoff.csv"), os.path.join(res, "E18_plume.csv")
    frames = []
    e17 = e18 = None
    if os.path.exists(e17p):
        e17 = pd.read_csv(e17p)
        table_e17(e17, B=a.boot).to_csv(os.path.join(res, "table_E17.csv"), index=False)
        frames.append(e17)
        print(f"[E20] table_E17.csv from {len(e17)} rows")
    if os.path.exists(e18p):
        e18 = pd.read_csv(e18p)
        table_e18(e18, B=a.boot).to_csv(os.path.join(res, "table_E18.csv"), index=False)
        frames.append(e18)
        print(f"[E20] table_E18.csv from {len(e18)} rows")
    if not frames:
        raise SystemExit(f"neither {e17p} nor {e18p} exists; run e17 / e18 first")
    both = pd.concat(frames, ignore_index=True, sort=False)
    fit, table = fit_law(both, B=a.boot)
    fit["inputs"] = {"E17": e17p if e17 is not None else None, "E18": e18p if e18 is not None else None,
                     "rows": int(len(both)), "seeds": int(both["seed"].nunique())}
    if e17 is not None:
        sit = siting_table(e17)
        sit.to_csv(os.path.join(res, "table_E20_siting.csv"), index=False)
        mins = siting_minimum(sit)
        fit["siting"] = {"energy_prices_usd_per_kwh": list(ENERGY_PRICES), "pad_cost_musd": PAD_COST_MUSD,
                         "pad_life_years": PAD_LIFE_YEARS,
                         "note": "pad cost is independent of standoff, so the minimum-cost standoff is set by hauling "
                                 "(operator + priced energy); the table shows both terms",
                         "min_cost_standoff_km": {f"{r.scenario}|{r.mechanism}|sigma{r.sigma_scale:g}|{r.energy_price_usd_per_kwh}$/kWh|{r.pad_case_usd_per_kg_transport}":
                                                  float(r.pad_standoff_km) for r in mins.itertuples()}}
        print(f"[E20] table_E20_siting.csv: {len(sit)} rows, {len(mins)} minima")
    table.to_csv(os.path.join(res, "table_E20.csv"), index=False)
    with open(os.path.join(res, "E20_fit.json"), "w", encoding="utf-8") as f:
        json.dump(fit, f, indent=1)
    pooled = fit["pooled"].get("log_delay_prio1_mean_h", {})
    print(f"[E20] fit on {fit['inputs']['rows']} rows, {fit['inputs']['seeds']} seeds; log-delay R2 {pooled.get('r2', float('nan')):.3f}")
    for t in ("standoff", "log_sigma", "keepout", "standdown", "util"):
        c = pooled.get("coef", {}).get(t)
        if c:
            print(f"       {t:10s} {c['coef']:+.4f}  [{c['ci95'][0]:+.4f}, {c['ci95'][1]:+.4f}]")
    return fit


if __name__ == "__main__":
    main()
