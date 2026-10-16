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
not the minimum-cost standoff; the siting table shows the scale of the terms side by side.
Plume damage (Modelled): expected impacts per landing I(D) from Wittal et al. (NASA OTPS 2022): 8 at 1 km,
0.37 at 5 km, 0.10 at 10 km, ln I linear in D between the anchors and extrapolated to 0.5 km with the 1-5 km
slope; x shielding 0.1 (Assumed) when sites.json says PAD_A's line of sight to BASE is blocked at that standoff;
x damage cost per impact in DAMAGE_MUSD_PER_IMPACT (Assumed); x the scenario's landings per year.
Dispersion in E17 is tagged by the implied mean |miss| (`miss_level_m`); `sigma_scale` = level / the classical
CLPS table's mean |miss| (classical_mean_miss_m).
"""
import argparse
import json
import os
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RESULTS = os.path.join(ROOT, "results")
POLICIES = os.path.join(ROOT, "data", "policies")
SITES_JSON = os.path.join(ROOT, "data", "terrain", "connecting_ridge", "sites.json")
ENERGY_PRICES = (0, 500, 2000, 5000)          # $/kWh, Assumed (swept)
PAD_COST_MUSD = {"10K": 130.0, "100K": 229.0, "300K": 548.0}   # Metzger & Autry 2022, by $/kg transport (Spec)
PAD_LIFE_YEARS = 10.0
WITTAL_IMPACTS = {1.0: 8.0, 5.0: 0.37, 10.0: 0.10}   # expected impacts per landing vs distance km (Wittal et al., OTPS 2022; Modelled)
DAMAGE_MUSD_PER_IMPACT = (0.1, 1.0, 10.0)            # Assumed (swept)
SHIELD_LOS_BLOCKED = 0.1                             # Assumed: damage factor when terrain blocks the pad-BASE line of sight
VOT_USD_PER_ITEM_H = (0, 100, 1000)                  # Assumed (swept): blended value of delivery time per item-hour; the engine prices
                                                     # urgency per priority class (vot_usd_per_h 5000 / 1000 / 100), this is a stand-in
SITING_FLAGS = ("hauling Modelled; energy price Assumed; pad cost Spec (Metzger & Autry 2022), independent of standoff; impacts/landing "
                "Modelled from Wittal et al. (OTPS 2022) anchors, shield 0.1 Assumed when PAD_A LOS to BASE is blocked; damage cost per "
                "impact Assumed; delay valuation Assumed (blended $/item-hour stand-in for the engine's per-priority vot_usd_per_h)")
MISS_REF_CLS = "CLPS"
MISS_REF_FALLBACK_M = 2.9
CLASSICAL_LABEL = "classical (as flown in the env)"   # the E17 miss level that leaves the classical table unscaled
N_BOOT = 1000


def classical_mean_miss_m(cls=MISS_REF_CLS, policy_dir=POLICIES):
    """Mean |miss| (m) of the classical outcome table for `cls`; the reference that turns a miss level into sigma_scale."""
    path = os.path.join(policy_dir, f"outcomes_classical_{cls}.json")
    if not os.path.exists(path):
        return MISS_REF_FALLBACK_M
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    comp = doc.get("summary", {}).get("components", {}).get("miss_r_m")
    if comp and comp.get("mean") is not None:
        return float(comp["mean"])
    return float(np.mean([np.hypot(*e["miss_m"]) for e in doc["episodes"]]))


def impacts_per_landing(d_km):
    """Expected plume impacts per landing at distance d_km: ln I piecewise-linear in D through WITTAL_IMPACTS,
    extrapolated below the first anchor with the first segment's slope and above the last with the last's."""
    xs = np.array(sorted(WITTAL_IMPACTS))
    ys = np.log([WITTAL_IMPACTS[x] for x in xs])
    d = np.asarray(d_km, float)
    lo_slope = (ys[1] - ys[0]) / (xs[1] - xs[0])
    hi_slope = (ys[-1] - ys[-2]) / (xs[-1] - xs[-2])
    out = np.interp(d, xs, ys)
    out = np.where(d < xs[0], ys[0] + lo_slope * (d - xs[0]), out)
    out = np.where(d > xs[-1], ys[-1] + hi_slope * (d - xs[-1]), out)
    return np.exp(out) if out.ndim else float(np.exp(out))


def pad_los_blocked(standoff_km, pad="PAD_A", sites_path=SITES_JSON):
    """True when sites.json pad_details[D][pad].los_to_base == 'blocked'; None when unknown."""
    if not os.path.exists(sites_path):
        return None
    with open(sites_path, encoding="utf-8") as f:
        det = json.load(f).get("pad_details", {})
    key = f"{float(standoff_km):g}"
    try:
        return det[key][pad]["los_to_base"] == "blocked"
    except KeyError:
        return None

MEAN_METRICS = ["delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "delivered_share", "delay_mean_h",
                "cost_per_kg_usd", "energy_kwh", "km_total", "utilisation", "jobs", "repositions", "km_reposition",
                "operator_hours", "plume_standdowns", "standdown_vehicle_h", "landing_miss_m_mean", "offpad_landings",
                "failed_landings", "cargo_lost_kg", "km_offpad_extra", "interventions", "intervention_h"]
PAIRED_METRICS = ["delay_prio1_mean_h", "delay_prio1_p90_h", "sl24_prio1", "cost_per_kg_usd", "energy_kwh", "km_total"]
E17_FACTORS = ["scenario", "phase", "n_vehicles", "mechanism", "miss_level_m", "miss_label", "pad_radius_m", "pad_standoff_km"]
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
    """One row per cell: <m> (mean over the seeds with a finite value), <m>_ci95, n_seeds, n_valid (seeds with a finite
    delay_prio1_mean_h; a year without an urgent delivery has NaN there) and n_valid_min (the smallest finite count over
    the metrics)."""
    metrics = [m for m in metrics if m in df.columns]
    rows = []
    for key, sub in df.groupby(factors, sort=True):
        row = dict(zip(factors, key))
        row["n_seeds"] = int(sub["seed"].nunique())
        row["n_valid"] = _n_valid(sub["delay_prio1_mean_h"]) if "delay_prio1_mean_h" in sub.columns else row["n_seeds"]
        n_min = row["n_seeds"]
        for m in metrics:
            v = sub[m].to_numpy(float)
            n_min = min(n_min, _n_valid(v))
            row[m] = float(np.nanmean(v)) if np.isfinite(v).any() else np.nan
            row[m + "_ci95"] = ci95(v)
        row["n_valid_min"] = n_min
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
        D = a.loc[common].to_numpy(float) - b.loc[common].to_numpy(float)       # (n, m); NaN where either year lacks the metric
        n = len(common)
        idx = rng.integers(0, n, (B, n))
        with warnings.catch_warnings():                                        # all-NaN resamples are expected, not errors
            warnings.simplefilter("ignore", RuntimeWarning)
            boot = np.nanmean(D[idx], axis=1)                                  # (B, m)
            lo, hi = np.nanpercentile(boot, [2.5, 97.5], axis=0)
        row = dict(zip(factors, key))
        row["n_common"] = n
        row[f"{prefix}_n_valid"] = int(np.isfinite(D).all(axis=1).sum())       # seeds with every paired metric finite
        for j, m in enumerate(metrics):
            col = D[:, j]
            row[f"{prefix}_{m}"] = float(np.nanmean(col)) if np.isfinite(col).any() else np.nan
            row[f"{prefix}_{m}_lo"] = float(lo[j])
            row[f"{prefix}_{m}_hi"] = float(hi[j])
        rows.append(row)
    return pd.DataFrame(rows)


def _merge(base, extra, factors):
    return base if extra.empty else base.merge(extra, on=factors, how="left")


def table_e17(df, B=N_BOOT):
    df = add_energy_cost(df)
    if "landings" in df.columns:
        df["offpad_share"] = df["offpad_landings"] / df["landings"].clip(lower=1)
    metrics = MEAN_METRICS + ["sigma_scale", "offpad_share", "landings"] + energy_cols()
    pm = PAIRED_METRICS + ["cost_per_kg_with_energy_usd_2000", "offpad_landings", "km_offpad_extra"]
    t = cell_means(df, E17_FACTORS, metrics)
    t = _merge(t, paired(df, E17_FACTORS, pm, {"pad_standoff_km": 1.0}, B=B, prefix="dD1"), E17_FACTORS)    # vs standoff 1 km, same miss level and pad
    cl = df[df["miss_label"] == CLASSICAL_LABEL]
    if len(cl):
        ref = {"miss_label": CLASSICAL_LABEL, "miss_level_m": float(cl["miss_level_m"].iloc[0])}
        t = _merge(t, paired(df, E17_FACTORS, pm, ref, B=B, prefix="dCL"), E17_FACTORS)                    # vs the classical miss, same standoff and pad
    t = _merge(t, paired(df, E17_FACTORS, pm, {"pad_radius_m": 50.0}, B=B, prefix="dR50"), E17_FACTORS)     # vs the 50 m pad, same miss level and standoff
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
TERMS = ["const", "log_miss", "standoff", "keepout", "standdown", "util", "night_fraction", "offpad_share", "pad_radius_m",
         "log_miss:standoff", "keepout:standdown", "keepout:util", "standdown:util", "standoff:util", "log_miss:util"]
DESIGN_NOTE = {
    "rows": "one simulated year (one seed of one cell) pooled from E17 (dispersion x standoff x pad radius) and E18 (keep-out), "
            "classical landings, driving-v1 legs, Connecting ridge terrain",
    "responses": {"log_delay_prio1_mean_h": "ln of the mean urgent-item delay (h); 100*(exp(b)-1) = % per unit",
                  "sl24_prio1": "share of urgent items delivered within 24 h (linear)",
                  "cost_per_kg_usd": "fleet + operator cost per delivered kg (linear)",
                  "cost_per_kg_with_energy_usd_<p>": "the same plus p $/kWh x energy_kwh / delivered_kg (p Assumed, swept)"},
    "regressors": TERMS + [f"mech_{m}" for m in MECH_DUMMIES],
    "log_miss": "ln(miss_level_m), the implied mean |miss| in metres (= sigma_scale x the classical CLPS mean |miss|; "
                "E18 rows and rows without miss_level_m use sigma_scale x that mean)",
    "offpad_share": "offpad_landings / landings of the year (rows without a landings count: 0 when offpad_landings is 0, else dropped); "
                    "lets the fit separate dispersion acting through off-pad events from any smooth effect",
    "pad_radius_m": "landing_model.pad_radius_m (rows without it: 50)",
    "standoff": "pad_standoff_km", "keepout": "plume keepout_km (E17 and no-plume rows: 0)", "standdown": "plume standdown_h (0 likewise)",
    "util": "mean utilisation of the reference cell (sigma 1, standoff 1 km, 50 m pad, no keep-out) of the same scenario, mechanism and "
            "night fraction: a group-level covariate for fleet load, not the row's own utilisation",
    "controls": "mechanism dummies (inhouse is the base) and night_fraction; the per-mechanism fits drop the dummies",
    "estimator": "ordinary least squares, numpy lstsq; columns constant in the data are dropped and listed",
    "ci": "percentile bootstrap over seeds, N_BOOT resamples: seeds drawn with replacement, every row of a drawn seed enters "
          "with that seed's multiplicity (weighted normal equations), so the CI respects the common-random-number pairing",
}


def _util_reference(df):
    """Reference-cell mean utilisation per (scenario, mechanism, night_fraction); the group mean if that cell is absent."""
    g = ["scenario", "mechanism", "night_fraction"]
    ref = df[(df["sigma_scale"] == 1.0) & (df["pad_standoff_km"] == 1.0) & (df["keepout_km"] == 0.0) & (df["standdown_h"] == 0.0)
             & (df["pad_radius_m"] == 50.0)]
    u = ref.groupby(g)["utilisation"].mean()
    fallback = df.groupby(g)["utilisation"].mean()
    u = fallback.to_frame("u_fb").join(u.rename("u_ref"), how="left")
    u["util"] = u["u_ref"].fillna(u["u_fb"])
    return df.merge(u[["util"]].reset_index(), on=g, how="left")["util"].to_numpy(float)


def design(df, mech_dummies=True, miss_ref_m=None):
    """(X, names) for the law. df needs pad_standoff_km, scenario, mechanism, utilisation and either miss_level_m or
    sigma_scale; keepout_km, standdown_h, night_fraction, pad_radius_m, offpad_landings, landings are filled when absent."""
    d = df.copy()
    for c, v in (("keepout_km", 0.0), ("standdown_h", 0.0), ("sigma_scale", 1.0), ("night_fraction", 0.15),
                 ("pad_radius_m", 50.0), ("offpad_landings", 0.0), ("landings", np.nan)):
        if c not in d.columns:
            d[c] = v
        d[c] = d[c].fillna(v)
    ref = classical_mean_miss_m() if miss_ref_m is None else float(miss_ref_m)
    if "miss_level_m" not in d.columns:
        d["miss_level_m"] = np.nan
    miss = d["miss_level_m"].fillna(d["sigma_scale"] * ref).to_numpy(float)
    lm = np.log(np.clip(miss, 1e-6, None))
    D = d["pad_standoff_km"].to_numpy(float)
    R = d["keepout_km"].to_numpy(float)
    T = d["standdown_h"].to_numpy(float)
    u = _util_reference(d)
    nf = d["night_fraction"].to_numpy(float)
    offpad = d["offpad_landings"].to_numpy(float)
    nl = d["landings"].to_numpy(float)
    share = np.where(offpad == 0, 0.0, offpad / nl)          # NaN when off-pad landings exist but the count is unknown
    pr = d["pad_radius_m"].to_numpy(float)
    cols = [np.ones(len(d)), lm, D, R, T, u, nf, share, pr, lm * D, R * T, R * u, T * u, D * u, lm * u]
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
SITING_CELL = ["scenario", "phase", "n_vehicles", "mechanism", "miss_level_m", "miss_label", "sigma_scale", "pad_radius_m", "pad_standoff_km"]
SITING_SWEEP = ["energy_price_usd_per_kwh", "pad_case_usd_per_kg_transport", "damage_musd_per_impact", "vot_usd_per_item_h"]


def _n_valid(x):
    return int(np.isfinite(np.asarray(x, float)).sum())


def _landings_per_year():
    from lunarsim.config import library
    return {k: float(sum(sc.landings_per_year.values())) for k, sc in library().items()}


def siting_table(e17, prices=ENERGY_PRICES, pad_costs=PAD_COST_MUSD, life=PAD_LIFE_YEARS, damage_costs=DAMAGE_MUSD_PER_IMPACT,
                 vots=VOT_USD_PER_ITEM_H, sites_path=SITES_JSON, landings_per_year=None):
    """Per E17 cell (means over seeds) x energy price x pad case x damage cost x value of time: hauling cost per year
    (operator + priced energy, M$), amortised pad cost (M$/yr), expected plume damage (landings/yr x I(D) x shield x cost),
    delay valuation (delivered items x mean delay h x VoT), their total, the fleet capital for context, and min_cost marking
    the minimum-cost standoff within each cost assumption. Means skip NaN years; n_valid counts years with an urgent delay."""
    g = [c for c in SITING_CELL if c in e17.columns]
    agg = e17.groupby(g).agg(n_seeds=("seed", "nunique"), n_valid=("delay_prio1_mean_h", _n_valid),
                             operator_cost_musd=("operator_cost_musd", "mean"),
                             energy_kwh=("energy_kwh", "mean"), delivered_kg=("delivered_kg", "mean"),
                             delivered_items=("delivered_items", "mean"), delay_mean_h=("delay_mean_h", "mean"),
                             fleet_cost_musd=("fleet_cost_musd", "mean"), cargo_lost_kg=("cargo_lost_kg", "mean"),
                             offpad_landings=("offpad_landings", "mean"), km_total=("km_total", "mean"),
                             delay_prio1_mean_h=("delay_prio1_mean_h", "mean")).reset_index()
    lpy = _landings_per_year() if landings_per_year is None else landings_per_year
    agg["landings_per_year"] = agg["scenario"].map(lpy).astype(float)
    D = agg["pad_standoff_km"].astype(float)
    agg["impacts_per_landing"] = impacts_per_landing(D.to_numpy())
    los = {d: pad_los_blocked(d, sites_path=sites_path) for d in D.unique()}
    agg["pad_a_los_blocked"] = D.map(los)
    agg["shield"] = np.where(agg["pad_a_los_blocked"].fillna(False).astype(bool), SHIELD_LOS_BLOCKED, 1.0)
    rows = []
    for p in prices:
        for case, pad in pad_costs.items():
            for dc in damage_costs:
                for vot in vots:
                    t = agg.copy()
                    t["energy_price_usd_per_kwh"] = p
                    t["pad_case_usd_per_kg_transport"] = case
                    t["damage_musd_per_impact"] = dc
                    t["vot_usd_per_item_h"] = vot
                    t["pad_cost_musd"] = pad
                    t["pad_musd_per_year"] = pad / life
                    t["energy_cost_musd"] = p * t["energy_kwh"] / 1e6
                    t["hauling_musd"] = t["operator_cost_musd"] + t["energy_cost_musd"]
                    t["damage_musd"] = t["landings_per_year"] * t["impacts_per_landing"] * t["shield"] * dc
                    t["delay_cost_musd"] = t["delivered_items"] * t["delay_mean_h"] * vot / 1e6
                    t["total_musd"] = t["hauling_musd"] + t["pad_musd_per_year"] + t["damage_musd"] + t["delay_cost_musd"]
                    t["total_usd_per_kg"] = 1e6 * t["total_musd"] / t["delivered_kg"].clip(lower=1e-9)
                    t["system_usd_per_kg"] = 1e6 * (t["total_musd"] + t["fleet_cost_musd"]) / t["delivered_kg"].clip(lower=1e-9)
                    rows.append(t)
    out = pd.concat(rows, ignore_index=True)
    grp = [c for c in g if c != "pad_standoff_km"] + SITING_SWEEP
    out["min_cost"] = out["total_musd"] == out.groupby(grp)["total_musd"].transform("min")
    return out.sort_values(grp + ["pad_standoff_km"]).reset_index(drop=True)


def siting_minimum(sit):
    """The minimum-cost standoff per cell and cost assumption (one row per group; ties keep the smallest standoff)."""
    grp = [c for c in SITING_CELL if c in sit.columns and c != "pad_standoff_km"] + SITING_SWEEP
    cols = grp + ["pad_standoff_km", "hauling_musd", "pad_musd_per_year", "damage_musd", "delay_cost_musd", "total_musd", "total_usd_per_kg"]
    m = sit[sit["min_cost"]].sort_values(grp + ["pad_standoff_km"])
    return m[cols].drop_duplicates(grp).reset_index(drop=True)


SUMMARY_KEYS = ["energy_price_usd_per_kwh", "damage_musd_per_impact", "vot_usd_per_item_h"]


def siting_summary(mins, standoffs=None):
    """Share of (cell, pad case) groups whose minimum-cost standoff is each D, by energy price x damage cost x VoT."""
    t = mins.groupby(SUMMARY_KEYS + ["pad_standoff_km"]).size().unstack("pad_standoff_km", fill_value=0)
    if standoffs is not None:
        t = t.reindex(columns=sorted(set(standoffs) | set(t.columns)), fill_value=0)
    t = t.div(t.sum(axis=1), axis=0)
    t.columns = [f"share_min_at_{c:g}km" for c in t.columns]
    return t.reset_index()


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
        sit.to_csv(os.path.join(res, "table_E20_siting.csv.gz"), index=False, float_format="%.6g")   # ~90k rows: gzipped like E14
        mins = siting_minimum(sit)
        mins.to_csv(os.path.join(res, "table_E20_siting_min.csv"), index=False, float_format="%.6g")
        summ = siting_summary(mins, standoffs=sit["pad_standoff_km"].unique())
        summ.to_csv(os.path.join(res, "table_E20_siting_shares.csv"), index=False)
        fit["siting"] = {"energy_prices_usd_per_kwh": list(ENERGY_PRICES), "pad_cost_musd": PAD_COST_MUSD,
                         "pad_life_years": PAD_LIFE_YEARS, "damage_musd_per_impact": list(DAMAGE_MUSD_PER_IMPACT),
                         "vot_usd_per_item_h": list(VOT_USD_PER_ITEM_H),
                         "impacts_per_landing_anchors": {f"{k:g}": v for k, v in WITTAL_IMPACTS.items()},
                         "impacts_per_landing_at_standoffs": {f"{d:g}": float(impacts_per_landing(d)) for d in (0.5, 1, 2, 3, 5)},
                         "shield_los_blocked": SHIELD_LOS_BLOCKED,
                         "pad_a_los_blocked": {f"{d:g}": pad_los_blocked(d) for d in (0.5, 1, 2, 3, 5)},
                         "flags": SITING_FLAGS,
                         "note": "total = hauling (operator + priced energy) + amortised pad cost (independent of standoff) + expected "
                                 "plume damage (landings/yr x I(D) x shield x cost per impact) + delay valuation (delivered items x mean "
                                 "delay h x VoT, a blended stand-in for the engine's per-priority vot_usd_per_h 5000/1000/100); min_cost "
                                 "marks the argmin standoff per cell and cost assumption; table_E20_siting_min.csv lists the minima, "
                                 "table_E20_siting_shares.csv the share of minima at each standoff per (energy price, damage cost, VoT)",
                         "share_of_minima_by_standoff": summ.to_dict("records")}
        print(f"[E20] table_E20_siting.csv.gz: {len(sit)} rows, {len(mins)} minima")
        print(summ.round(2).to_string(index=False))
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
