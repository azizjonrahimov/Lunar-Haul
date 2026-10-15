"""Phase-3 experiment suites E15-E20 (PLAN §6): one raw CSV per suite in results/ plus a summary table each.

Usage:  python experiments/phase3/run_phase3.py [e15 e16 e17 e18 e19 e20] [--seeds N] [--workers K]
        python experiments/phase3/run_phase3.py e17 e18 e19 --seeds 2 --workers 2     # smoke

Same conventions as experiments/run_all.py: a cell is (tag, scenario, mechanism); every cell is replicated over
N_SEEDS seeds with common random numbers (seed s = demand stream s, operations stream s + 100,003); rows are the
engine's per-year summary. Differences: the raw CSV is resumable (rows already present, keyed by `cell` and
`seed`, are skipped and new rows are appended as they finish) and the Pool defaults to WORKERS processes.

Suites
  e15  lander Monte Carlo summary from data/policies/outcomes_*.json (no simulation)   -> table_E15.csv
  e16  driving-table validation from data/driving/driving-v1.json (no simulation)       -> E16_driving_validation.csv, table_E16.csv
  e17  landing dispersion x pad standoff x mechanism x fleet/phase                      -> E17_dispersion_standoff.csv, table_E17.csv
  e18  plume keep-out radius x stand-down x mechanism x night x fleet x standoff        -> E18_plume.csv, table_E18.csv
  e19  vehicle autonomy level (teleop at 4/6/8 s RTT, supervised, autonomous) x fleet   -> E19_autonomy_fleet.csv, table_E19.csv
  e20  the law fit and pad siting from E17/E18 (experiments/phase3/fit_law.py)         -> E20_fit.json, table_E20*.csv
Phase-3 Scenario fields are set exactly as `lunarsim run --terrain connecting_ridge --pad-standoff D
--landing-model classical --sigma-scale s --plume R,T --autonomy driving-v1` sets them (lunarsim/cli.py).
"""
import argparse
import glob
import json
import math
import os
import sys
import time
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
from multiprocessing import Pool  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from lunarsim import run, dispatch  # noqa: E402
from lunarsim.config import library, split_rtt  # noqa: E402
from lunarsim.phases import PHASES, FLEETS  # noqa: E402
from experiments.phase3 import fit_law  # noqa: E402

N_SEEDS = 30
WORKERS = 3                      # 8 GB machine shared with other sessions
RESULTS = os.path.join(ROOT, "results")
POLICIES = os.path.join(ROOT, "data", "policies")
DRIVING = os.path.join(ROOT, "data", "driving", "driving-v1.json")
TERRAIN = "connecting_ridge"
AUTONOMY = "driving-v1"
PAD_RADIUS_M = 50.0

MECHS = {
    "inhouse": (dispatch.inhouse, {}),
    "pooled_greedy": (dispatch.pooled_greedy, {}),
    "central_assign": (dispatch.central_assign, {"batch_h": 1.0}),
    "marketplace": (dispatch.marketplace, {}),
}
LIB = library()                  # "P2-default", "P2-<n>-vehicles" (n_operators = max(2, n // 2)), "P3-default"

SIGMAS = (0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0)
STANDOFFS = (0.5, 1.0, 2.0, 3.0, 5.0)
E17_SCENARIOS = ("P2-default", "P2-4-vehicles", "P2-2-vehicles", "P3-default")
E17_MECHS = ("inhouse", "marketplace")
KEEPOUTS = (0.2, 0.5, 1.0, 2.0, 3.0)
STANDDOWNS = (0.1, 0.5, 2.0, 6.0)
NIGHTS = (0.15, 0.0)
E18_SCENARIOS = ("P2-default", "P2-4-vehicles", "P3-default")
E18_STANDOFFS = (1.0, 3.0)
E19_FLEETS = (2, 4, 6, 8)
E19_SETS = (("teleop", 4.0), ("teleop", 6.0), ("teleop", 8.0), ("supervised", None), ("autonomous", None))
E19_MECHS = ("inhouse", "marketplace")

# validation anchors (E16)
JSC_TELEOP_KMH = {0.0: 3.24, 4.0: 2.56, 6.0: 2.03, 8.0: 1.76}      # Litaker et al. (JSC), speed made good vs RTT
CHEN_PSR_KWH = (0.4, 4.4)                                          # Chen 2026, BASE<->PSR round trip, 500 kg rover
CHEN_MASS_KG = 500.0
MIN_FLAT_LEG_M = 500.0


# ---------------------------------------------------------------------------
# cells and the resumable pool
# ---------------------------------------------------------------------------
def standoff_key(d) -> str:
    """sites.json pad key, as lunarsim.cli writes it: 0.5 -> '0.5', 1.0 -> '1'."""
    return f"{float(d):g}"


def phase3(sc, standoff, sigma_scale=1.0, plume=None, landing="classical", autonomy=AUTONOMY):
    """The Phase-3 fields exactly as cli._with_phase3 builds them."""
    kw = {"terrain": TERRAIN, "pad_standoff_km": standoff_key(standoff), "autonomy_model": autonomy}
    if landing:
        kw["landing_model"] = {"policy": landing, "sigma_scale": float(sigma_scale), "pad_radius_m": PAD_RADIUS_M,
                               "failure_policy": "lose"}
    if plume:
        r, t = plume
        kw["plume"] = {"keepout_km": float(r), "standdown_h": float(t), "shelter": "auto"}
    return sc.with_(**kw)


def cell_key(tag, mech_name) -> str:
    return ";".join(f"{k}={v}" for k, v in tag.items() if k != "exp") + f";mechanism={mech_name}"


def _job(args):
    tag, sc, mech_name, mech, kw, seed = args
    out = run(sc, mech, seed=seed, **kw)
    out.update(tag)
    out["mechanism"] = mech_name
    out["cell"] = cell_key(tag, mech_name)
    return out


def pending_jobs(path, cells, seeds):
    """(jobs still to run, rows already in the CSV)."""
    done = set()
    if os.path.exists(path):
        old = pd.read_csv(path, usecols=["cell", "seed"])
        done = set(zip(old["cell"].astype(str), old["seed"].astype(int)))
    jobs = [(tag, sc, mn, mf, kw, s) for (tag, sc, mn, mf, kw) in cells for s in range(seeds)
            if (cell_key(tag, mn), s) not in done]
    return jobs, len(done)


def append_rows(path, rows):
    """Append rows to the CSV keeping the file's column order; rewrite if a new column appears."""
    df = pd.DataFrame(rows)
    if not os.path.exists(path):
        df.to_csv(path, index=False)
        return
    cols = list(pd.read_csv(path, nrows=0).columns)
    if set(df.columns) - set(cols):
        pd.concat([pd.read_csv(path), df], ignore_index=True, sort=False).to_csv(path, index=False)
    else:
        df.reindex(columns=cols).to_csv(path, mode="a", header=False, index=False)


def run_cells(name, cells, seeds=N_SEEDS, workers=WORKERS):
    """cells: list of (tag_dict, scenario, mech_name, mech_fn, mech_kwargs). Resumable; returns the full CSV."""
    path = os.path.join(RESULTS, f"{name}.csv")
    os.makedirs(RESULTS, exist_ok=True)
    jobs, n_done = pending_jobs(path, cells, seeds)
    print(f"[{name}] {len(cells)} cells x {seeds} seeds: {n_done} rows present, {len(jobs)} to run on {workers} workers")
    if jobs:
        t0 = time.time()
        buf = []
        with Pool(workers) as pool:
            for i, row in enumerate(pool.imap_unordered(_job, jobs, chunksize=1), 1):
                buf.append(row)
                if len(buf) >= 50 or i == len(jobs):
                    append_rows(path, buf)
                    buf = []
                if i % 200 == 0 or i == len(jobs):
                    el = time.time() - t0
                    print(f"[{name}] {i}/{len(jobs)} rows, {el:.0f}s elapsed, ETA {el / i * (len(jobs) - i):.0f}s", flush=True)
        print(f"[{name}] {len(jobs)} runs in {time.time() - t0:.0f}s -> {path}")
    return pd.read_csv(path)


def write_table(name, df):
    path = os.path.join(RESULTS, name)
    df.to_csv(path, index=False)
    print(f"[{name}] {len(df)} rows -> {path}")
    return df


def _tag(exp, scen_name, **kw):
    sc = LIB[scen_name]
    tag = {"exp": exp, "scenario": scen_name, "phase": scen_name.split("-")[0], "n_vehicles": len(sc.fleet)}
    tag.update(kw)
    return tag


# ---------------------------------------------------------------------------
# E15: lander Monte Carlo summary from the committed outcome tables
# ---------------------------------------------------------------------------
FAIL_KINDS = ("velocity", "tilt", "sensor", "timeout", "lost")


def e15_rows(policy_dir=POLICIES):
    rows = []
    for path in sorted(glob.glob(os.path.join(policy_dir, "outcomes_*.json"))):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        eps = doc.get("episodes", [])
        if doc.get("format") != "lunarsim-landing-outcomes" or not eps:
            continue
        pol = doc.get("policy") or os.path.basename(path)[len("outcomes_"):-len(".json")]
        cls = doc.get("cls") or eps[0].get("cls")
        learned = doc.get("controller") == "policy" or not str(pol).startswith("classical")
        card = os.path.join(policy_dir, f"{pol}.json")
        tr = {}
        if learned and os.path.exists(card):
            with open(card, encoding="utf-8") as f:
                tr = json.load(f).get("training", {})
        miss = np.array([math.hypot(*e["miss_m"]) for e in eps])
        ok = np.array([bool(e.get("ok")) for e in eps])
        td = np.array([bool(e.get("touchdown_ok", e.get("ok"))) for e in eps])
        kinds = [e.get("failure_kind") for e in eps]
        prop = np.array([e.get("prop_used_kg") for e in eps], float)
        t30 = np.array([e.get("t_below_30m_s") for e in eps], float)
        vz = np.array([e["v_td"][2] for e in eps if e.get("v_td")], float)
        row = {"policy": pol, "cls": cls, "kind": "learned" if learned else "classical",
               "variant": tr.get("reward_variant", "classical" if not learned else None),
               "controller": doc.get("controller"), "n": len(eps), "pass_rate": float(ok.mean()),
               "touchdown_box_rate": float(td.mean())}
        for k in FAIL_KINDS:
            row[f"fail_{k}"] = int(sum(1 for x in kinds if x == k))
        row.update({"miss_mean_m": float(miss.mean()), "miss_p50_m": float(np.percentile(miss, 50)),
                    "miss_p90_m": float(np.percentile(miss, 90)), "miss_max_m": float(miss.max()),
                    "offpad_50m_share": float((miss > PAD_RADIUS_M).mean()),
                    "prop_used_mean_kg": float(np.nanmean(prop)), "t_below_30m_mean_s": float(np.nanmean(t30)),
                    "vz_td_mean_mps": float(vz.mean()) if len(vz) else np.nan,
                    "sensor": doc.get("sensor"), "seed0": doc.get("seed0"), "training_steps": tr.get("steps"),
                    "policy_sha256": doc.get("policy_sha256"), "file": os.path.relpath(path, ROOT).replace("\\", "/")})
        rows.append(row)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    classical = df[df["kind"] == "classical"].set_index("cls")
    diff_cols = ("pass_rate", "miss_mean_m", "miss_p90_m", "prop_used_mean_kg", "t_below_30m_mean_s", "offpad_50m_share")
    for i, r in df.iterrows():
        if r["kind"] == "learned" and r["cls"] in classical.index:
            c = classical.loc[r["cls"]]
            df.loc[i, "vs"] = c["policy"]
            for m in diff_cols:
                df.loc[i, f"d_{m}"] = r[m] - c[m]
            p1, p2, n1, n2 = r["pass_rate"], c["pass_rate"], r["n"], c["n"]
            df.loc[i, "d_pass_rate_ci95"] = 1.96 * math.sqrt(p1 * (1 - p1) / n1 + p2 * (1 - p2) / n2)
    return df.sort_values(["cls", "kind", "policy"]).reset_index(drop=True)


def e15(**_):
    return write_table("table_E15.csv", e15_rows())


# ---------------------------------------------------------------------------
# E16: driving-table validation against the JSC speed curve and the Chen energy band
# ---------------------------------------------------------------------------
def _lognormal_mean(d):
    return float(d["mean"]) if "mean" in d else math.exp(d["mu"] + 0.5 * d["sigma"] ** 2)


def e16_rows(path=DRIVING):
    """Every leg x autonomy x RTT x lighting of the table: length, time, speed made good, energy, intervention rate."""
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
    rows = []
    for leg, L in doc["legs"].items():
        for aut, A in L["autonomy"].items():
            for rtt, R in A["rtt_s"].items():
                for light, e in R["lighting"].items():
                    route = L["route"].get(light) or next(iter(L["route"].values()))
                    t_h = _lognormal_mean(e["time_h"])
                    rows.append({"leg": leg, "autonomy": aut, "rtt_s": float(rtt), "lighting": light,
                                 "length_m": route.get("length_m"), "climb_m": route.get("climb_m"),
                                 "max_slope_deg": route.get("max_slope_deg"), "shadow_fraction": route.get("shadow_fraction"),
                                 "time_h_mean": t_h, "speed_made_good_kmh": route["length_m"] / 1000.0 / t_h if t_h > 0 else np.nan,
                                 "energy_kwh_mean": _lognormal_mean(e["energy_kwh"]),
                                 "interventions_lambda": e["interventions"]["lambda"], "stops": e.get("stops")})
    return doc, pd.DataFrame(rows)


def e16_table(doc, raw):
    """The two validation checks. Fields missing from the table are reported, not guessed."""
    rows = []
    mass = doc.get("model", {}).get("mass_kg")
    day = raw[raw["lighting"] != "night"]
    # (a) flattest leg (smallest max slope over its daylight routes, at least MIN_FLAT_LEG_M long): teleop speed vs RTT
    legs = day.groupby("leg").agg(max_slope_deg=("max_slope_deg", "max"), length_m=("length_m", "min"), climb_m=("climb_m", "max")).reset_index()
    cand = legs[legs["length_m"] >= MIN_FLAT_LEG_M]
    if cand.empty:
        cand = legs
    flat = cand.sort_values(["max_slope_deg", "climb_m", "length_m"]).iloc[0]["leg"]
    sub = day[day["leg"] == flat]
    light = sub.sort_values("shadow_fraction").iloc[0]["lighting"]        # least-shadowed daylight bin
    sub = sub[sub["lighting"] == light]
    base = {}
    for aut in ("teleop", "supervised", "autonomous"):
        s0 = sub[(sub["autonomy"] == aut) & (sub["rtt_s"] == 0.0)]
        base[aut] = float(s0["speed_made_good_kmh"].iloc[0]) if len(s0) else np.nan
    for r in sub.sort_values(["autonomy", "rtt_s"]).itertuples():
        jsc = JSC_TELEOP_KMH.get(r.rtt_s) if r.autonomy == "teleop" else None
        rows.append({"check": "speed_made_good_vs_rtt", "leg": flat, "lighting": light, "autonomy": r.autonomy, "rtt_s": r.rtt_s,
                     "length_m": r.length_m, "max_slope_deg": r.max_slope_deg, "sim_kmh": r.speed_made_good_kmh,
                     "sim_ratio_to_rtt0": r.speed_made_good_kmh / base[r.autonomy] if base[r.autonomy] else np.nan,
                     "ref_kmh": jsc, "ref_ratio_to_rtt0": (jsc / JSC_TELEOP_KMH[0.0]) if jsc else np.nan,
                     "rel_err": (r.speed_made_good_kmh / jsc - 1.0) if jsc else np.nan,
                     "interventions_lambda": r.interventions_lambda,
                     "note": "JSC/Litaker teleop course (Measured); table time excludes interventions; flattest leg >= %g m" % MIN_FLAT_LEG_M})
    # (b) BASE<->PSR round trip energy per autonomy level vs the Chen band scaled by rover mass
    out_leg, back_leg = "BASE->PSR", "PSR->BASE"
    have = set(raw["leg"])
    if out_leg not in have or back_leg not in have:
        rows.append({"check": "psr_round_trip_energy", "note": f"legs {out_leg} / {back_leg} absent from the table"})
    elif mass is None:
        rows.append({"check": "psr_round_trip_energy", "note": "model.mass_kg absent from the table; cannot scale the Chen band"})
    else:
        scale = mass / CHEN_MASS_KG
        lo, hi = CHEN_PSR_KWH[0] * scale, CHEN_PSR_KWH[1] * scale
        rt = raw[raw["leg"].isin((out_leg, back_leg))].copy()
        rtts = sorted(rt["rtt_s"].unique())
        rtt_bin = 4.0 if 4.0 in rtts else rtts[0]            # the bin the engine uses at the scenario default RTT (5 s)
        rt = rt[rt["rtt_s"] == rtt_bin]
        rt["period"] = np.where(rt["lighting"] == "night", "night", "day")
        g = rt.groupby(["autonomy", "rtt_s", "period", "leg"])["energy_kwh_mean"].mean().unstack("leg")
        km = rt.groupby("leg")["length_m"].first()
        for (aut, rtt, period), e in g.iterrows():
            tot = float(e[out_leg] + e[back_leg])
            rows.append({"check": "psr_round_trip_energy", "leg": f"{out_leg} + {back_leg}", "lighting": period, "autonomy": aut, "rtt_s": rtt,
                         "length_m": float(km[out_leg] + km[back_leg]), "sim_kwh": tot, "ref_kwh_lo": lo, "ref_kwh_hi": hi,
                         "in_band": bool(lo <= tot <= hi), "rover_mass_kg": mass,
                         "note": f"Chen 2026 band {CHEN_PSR_KWH[0]}-{CHEN_PSR_KWH[1]} kWh at {CHEN_MASS_KG:g} kg scaled x{scale:g} "
                                 f"(rolling + grade losses scale with m*g: Assumed linear); table energy is traction only"})
    return pd.DataFrame(rows)


def e16(**_):
    doc, raw = e16_rows()
    write_table("E16_driving_validation.csv", raw)
    return write_table("table_E16.csv", e16_table(doc, raw))


# ---------------------------------------------------------------------------
# E17: landing dispersion x pad standoff
# ---------------------------------------------------------------------------
def e17_cells():
    cells = []
    for name in E17_SCENARIOS:
        base = LIB[name]
        for sig in SIGMAS:
            for D in STANDOFFS:
                sc = phase3(base, D, sigma_scale=sig)
                for mn in E17_MECHS:
                    tag = _tag("E17", name, sigma_scale=float(sig), pad_standoff_km=float(D), keepout_km=0.0, standdown_h=0.0,
                               night_fraction=float(base.night_fraction))
                    cells.append((tag, sc, mn, *MECHS[mn]))
    return cells


def e17(seeds=N_SEEDS, workers=WORKERS):
    df = run_cells("E17_dispersion_standoff", e17_cells(), seeds, workers)
    return write_table("table_E17.csv", fit_law.table_e17(df))


# ---------------------------------------------------------------------------
# E18: plume keep-out radius x stand-down time (plus the matching no-plume cells)
# ---------------------------------------------------------------------------
def e18_cells():
    cells = []
    for name in E18_SCENARIOS:
        for nf in NIGHTS:
            for D in E18_STANDOFFS:
                base = LIB[name].with_(night_fraction=nf)
                for mn in MECHS:
                    tag = _tag("E18", name, night_fraction=float(nf), pad_standoff_km=float(D), sigma_scale=1.0, keepout_km=0.0, standdown_h=0.0)
                    cells.append((tag, phase3(base, D), mn, *MECHS[mn]))
                    for R in KEEPOUTS:
                        for T in STANDDOWNS:
                            tag = _tag("E18", name, night_fraction=float(nf), pad_standoff_km=float(D), sigma_scale=1.0,
                                       keepout_km=float(R), standdown_h=float(T))
                            cells.append((tag, phase3(base, D, plume=(R, T)), mn, *MECHS[mn]))
    return cells


def e18(seeds=N_SEEDS, workers=WORKERS):
    df = run_cells("E18_plume", e18_cells(), seeds, workers)
    return write_table("table_E18.csv", fit_law.table_e18(df))


# ---------------------------------------------------------------------------
# E19: vehicle autonomy level x fleet size (Phase-2 fleet variants)
# ---------------------------------------------------------------------------
def e19_cells():
    base = PHASES["P2"]
    cells = []
    for n in E19_FLEETS:
        for aut, rtt in E19_SETS:
            fleet = [(o, c, aut, s) for (o, c, _, s) in FLEETS[n]]
            kw = {"fleet": fleet, "n_operators": max(2, n // 2)}
            if rtt is not None:
                kw["one_way_latency_s"], kw["ground_delay_s"] = split_rtt(rtt, base.ground_delay_s)
            sc = phase3(base.with_(**kw), 1.0)
            rtt_s = 2 * sc.one_way_latency_s + sc.ground_delay_s
            for mn in E19_MECHS:
                tag = {"exp": "E19", "scenario": f"P2-{n}-vehicles", "phase": "P2", "n_vehicles": n, "autonomy": aut,
                       "rtt_s": float(rtt_s), "pad_standoff_km": 1.0, "sigma_scale": 1.0}
                cells.append((tag, sc, mn, *MECHS[mn]))
    return cells


def e19(seeds=N_SEEDS, workers=WORKERS):
    df = run_cells("E19_autonomy_fleet", e19_cells(), seeds, workers)
    return write_table("table_E19.csv", fit_law.table_e19(df))


# ---------------------------------------------------------------------------
# E20: the law fit and pad siting (fit_law.py), from the E17 / E18 CSVs
# ---------------------------------------------------------------------------
def e20(**_):
    return fit_law.main(["--results", RESULTS])


SUITES = {"e15": e15, "e16": e16, "e17": e17, "e18": e18, "e19": e19, "e20": e20}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("suites", nargs="*", help="any of " + " ".join(SUITES) + " (default: all)")
    p.add_argument("--seeds", type=int, default=N_SEEDS, help="replications per cell (smoke: 2)")
    p.add_argument("--workers", type=int, default=WORKERS, help="Pool processes (default %d)" % WORKERS)
    a = p.parse_args(argv)
    names = [s.lower() for s in a.suites] or list(SUITES)
    unknown = [s for s in names if s not in SUITES]
    if unknown:
        raise SystemExit(f"unknown suite(s) {unknown}; choose from {list(SUITES)}")
    t0 = time.time()
    for n in names:
        SUITES[n](seeds=a.seeds, workers=a.workers)
    print(f"done {names} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
