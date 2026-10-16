"""Phase-3 figures of the LunarHaul paper (fig20-fig27) from results/ (E15-E20) and data/policies/.

    python experiments/phase3/make_figures_phase3.py                   # every figure
    python experiments/phase3/make_figures_phase3.py --only fig22      # one ('fig22', '22' or 'fig22_dispersion_standoff')
    python experiments/phase3/make_figures_phase3.py --results DIR --out DIR --policies DIR

Each figure is written as <out>/<id>.png (200 dpi) and <id>.pdf, no wider than 7 in; <out>/phase3_captions.json maps
every figure id to its caption (n per cell, the CI convention, the Measured / Spec / Modelled / Assumed flags) and
its build status. A figure whose suite, table or columns are missing is skipped with a printed reason and the
others are still built, so the script runs unchanged on partial (smoke) and on final results.

Data: the fig2x functions read the summary tables fit_law writes (table_E17/E18/E19.csv, E20_fit.json,
table_E20_siting*.csv) and fall back to computing a table from the raw suite CSV when only that exists; fig20
reads data/policies/outcomes_*.json through run_phase3.e15_rows; fig21 reads table_E16.csv.

Conventions: Paul Tol's Bright palette for categories (mechanisms keep the paper's assignment: marketplace blue,
in-house red, pooled greedy yellow, batched assignment purple); samples of Crameri's batlow for ordered sequences;
a red-blue diverging map for paired differences. 95 % CIs: 1.96 SE over seeds for cell means (fit_law.cell_means),
percentile seed-bootstrap intervals for paired differences (fit_law.paired, fit_law.fit_ols), Wilson intervals
for pass rates. Style (fonts, sizes) follows experiments/make_figures.py.
"""
import argparse
import glob
import json
import math
import os
import sys
import traceback
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

from experiments.phase3 import fit_law as fl  # noqa: E402

RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
POLICIES = os.path.join(ROOT, "data", "policies")
CAPTIONS_FILE = "phase3_captions.json"
MAX_WIDTH_IN = 7.0

# Paul Tol, Bright (qualitative)
TOL = {"blue": "#4477AA", "red": "#EE6677", "green": "#228833", "yellow": "#CCBB44", "cyan": "#66CCEE",
       "purple": "#AA3377", "grey": "#BBBBBB"}
# Crameri batlow, 10 samples (dark to light); ordered sequences take evenly spaced samples of the first nine
BATLOW = ["#011959", "#103F60", "#1C5A62", "#3C6D56", "#687B3E", "#9D892B", "#D29343", "#F8A17B", "#FDB7BC", "#FACCFA"]
GREYS = ["#2b2b2b", "#555555", "#808080", "#aaaaaa", "#cccccc"]
MECH_COLOR = {"inhouse": TOL["red"], "pooled_greedy": TOL["yellow"], "central_assign": TOL["purple"], "marketplace": TOL["blue"]}
MECH_LABEL = {"inhouse": "In-house fleets", "pooled_greedy": "Pooled greedy", "central_assign": "Batched assignment",
              "marketplace": "Marketplace"}
MECH_ORDER = ["inhouse", "pooled_greedy", "central_assign", "marketplace"]
MECH_LS = {"inhouse": "--", "pooled_greedy": ":", "central_assign": "-.", "marketplace": "-"}
SCEN_COLOR = [TOL["blue"], TOL["yellow"], TOL["purple"], TOL["cyan"], TOL["red"], TOL["green"], TOL["grey"]]
OUTCOME_COLOR = {"ok": TOL["blue"], "velocity": TOL["red"], "tilt": TOL["purple"], "sensor": TOL["yellow"],
                 "timeout": TOL["cyan"], "lost": TOL["grey"]}
FAIL_KINDS = ("velocity", "tilt", "sensor", "timeout", "lost")
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
DIVERGING = "RdBu_r"

plt.rcParams.update({
    "font.family": "Times New Roman", "mathtext.fontset": "stix", "font.size": 10, "axes.titlesize": 10.5, "axes.labelsize": 10,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 8,
    "figure.dpi": 150, "savefig.dpi": 200, "savefig.bbox": "tight", "savefig.facecolor": "white",
})


class Skip(Exception):
    """Raised by a figure function when its data are absent; build() prints the reason and goes on."""


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def ordered_colors(k, palette=BATLOW, lo=0, hi=6):
    """k colours evenly spaced along an ordered palette (batlow by default, light end excluded)."""
    if k <= 0:
        return []
    if k == 1:
        return [palette[lo]]
    idx = np.round(np.linspace(lo, hi, k)).astype(int)
    return [palette[i] for i in idx]


def wilson(k, n, z=1.96):
    """Wilson score interval for k successes in n trials."""
    if n <= 0:
        return np.nan, np.nan
    p = k / n
    d = 1.0 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def ci95(x):
    return fl.ci95(x)


def fmt_g(x, nd=3):
    return f"{x:.{nd}g}"


def n_text(series, what="seeds per cell"):
    """'n = 30 seeds per cell' or 'n = 2-30 seeds per cell (median 30)' from a per-cell count column."""
    s = pd.Series(series).dropna().astype(int)
    if s.empty:
        return "n unknown"
    if s.min() == s.max():
        return f"n = {int(s.min())} {what}"
    return f"n = {int(s.min())}-{int(s.max())} {what} (median {int(s.median())})"


def scen_label(scenario, n_vehicles=None):
    ph = str(scenario).split("-")[0]
    if n_vehicles is None or (isinstance(n_vehicles, float) and np.isnan(n_vehicles)):
        return str(scenario)
    n = int(n_vehicles)
    return f"{ph}, {n} vehicle{'s' if n != 1 else ''}"


def scenario_order(df):
    """Scenarios sorted by phase then fleet size: [(scenario, n_vehicles), ...]."""
    cols = ["scenario"] + (["n_vehicles"] if "n_vehicles" in df.columns else [])
    g = df[cols].drop_duplicates()
    if "n_vehicles" not in g.columns:
        g = g.assign(n_vehicles=np.nan)
    g = g.assign(ph=g["scenario"].astype(str).str.split("-").str[0]).sort_values(["ph", "n_vehicles", "scenario"])
    return list(zip(g["scenario"], g["n_vehicles"]))


def mechs_present(df):
    have = set(df["mechanism"].astype(str).unique())
    return [m for m in MECH_ORDER if m in have] + sorted(have - set(MECH_ORDER))


def mech_label(m):
    return MECH_LABEL.get(m, str(m))


def mech_color(m, i=0):
    return MECH_COLOR.get(m, SCEN_COLOR[i % len(SCEN_COLOR)])


def load_csv(res, name, required=()):
    path = os.path.join(res, name)
    if not os.path.exists(path):
        raise Skip(f"{name} not found in {res}")
    df = pd.read_csv(path)
    if df.empty:
        raise Skip(f"{name} has no rows")
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise Skip(f"{name} lacks columns {missing}")
    return df


def table_or_raw(res, table, raw, maker, required=(), boot=200):
    """The summary table if present, else the table computed by fit_law from the raw suite CSV."""
    tpath, rpath = os.path.join(res, table), os.path.join(res, raw)
    if os.path.exists(tpath):
        df = load_csv(res, table)
        src = table
    elif os.path.exists(rpath):
        rawdf = load_csv(res, raw)
        try:
            df = maker(rawdf, B=boot)
        except (KeyError, ValueError) as e:
            raise Skip(f"{raw} present but the table could not be computed: {e!r}")
        src = f"{raw} (table computed here, {boot} bootstrap resamples)"
        print(f"  {table} absent; computed from {raw}")
    else:
        raise Skip(f"neither {table} nor {raw} in {res}")
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise Skip(f"{src} lacks columns {missing}")
    df.attrs["source"] = src
    return df


def save(fig, name, out):
    os.makedirs(out, exist_ok=True)
    w = fig.get_size_inches()[0]
    if w > MAX_WIDTH_IN + 1e-6:
        fig.set_size_inches(MAX_WIDTH_IN, fig.get_size_inches()[1] * MAX_WIDTH_IN / w)
    paths = []
    for ext in ("png", "pdf"):
        p = os.path.join(out, f"{name}.{ext}")
        fig.savefig(p)
        paths.append(p)
    plt.close(fig)
    try:
        import matplotlib.image as mimage
        px_w = mimage.imread(paths[0]).shape[1]
        w_in = px_w / plt.rcParams["savefig.dpi"]
        if w_in > MAX_WIDTH_IN * 1.01:
            print(f"  WARNING {name}.png is {w_in:.2f} in wide (> {MAX_WIDTH_IN} in): labels stick out of the figure box")
    except Exception:  # noqa: BLE001
        w_in = float("nan")
    print(f"saved {name} ({w_in:.2f} in wide)")
    return paths


def end_labels(ax, items, x, min_gap=0.055, fontsize=7, pad_pt=4):
    """Direct labels at the right end of lines: items = [(y_data, text, colour)], spread vertically (axes units)."""
    if not items:
        return
    to_ax = lambda y: ax.transAxes.inverted().transform(ax.transData.transform((x, y)))[1]
    pts = []
    for y, text, col in items:
        if y is None or not np.isfinite(y):
            continue
        pts.append([to_ax(y), text, col])
    if not pts:
        return
    pts.sort(key=lambda p: p[0])
    for k in range(1, len(pts)):
        if pts[k][0] - pts[k - 1][0] < min_gap:
            pts[k][0] = pts[k - 1][0] + min_gap
    over = pts[-1][0] - 0.98
    if over > 0:
        for p in pts:
            p[0] -= over
    tr = blended_transform_factory(ax.transData, ax.transAxes)
    for yf, text, col in pts:
        ax.annotate(text, (x, yf), xycoords=tr, xytext=(pad_pt, 0), textcoords="offset points", fontsize=fontsize,
                    color=col, ha="left", va="center", annotation_clip=False)


def panel_note(ax, text, fontsize=7.5):
    ax.text(0.5, 0.5, text, transform=ax.transAxes, ha="center", va="center", fontsize=fontsize, color=MUTED, wrap=True)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)


def nearest(values, target):
    vals = sorted(set(float(v) for v in values))
    return min(vals, key=lambda v: abs(v - target))


# ---------------------------------------------------------------------------
# fig20: lander Monte Carlo
# ---------------------------------------------------------------------------
def _load_outcomes(policy_dir):
    """[(policy, cls, controller, episodes)] from the committed outcome tables."""
    docs = []
    for path in sorted(glob.glob(os.path.join(policy_dir, "outcomes_*.json"))):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
        eps = doc.get("episodes", [])
        if doc.get("format") != "lunarsim-landing-outcomes" or not eps:
            continue
        pol = doc.get("policy") or os.path.basename(path)[len("outcomes_"):-len(".json")]
        docs.append((pol, doc.get("cls") or eps[0].get("cls"), doc.get("controller"), eps))
    return docs


def _policy_label(row):
    if row["kind"] == "classical":
        return "classical law"
    v = row.get("variant")
    if isinstance(v, str) and v:
        return f"learned ({v.replace('_', ' ')})"
    pid = str(row["policy"])
    parts = pid.split("_")
    short = "_".join(p for p in parts if p not in ("lander", str(row["cls"])) and not (p.startswith("s") and p[1:].isdigit()))
    return f"learned ({short or pid})"


def _e15_summary_local(docs, policy_dir):
    """Pass rate, failure counts and variant per outcome table (the subset of run_phase3.e15_rows fig20 needs)."""
    rows = []
    for pol, cls, ctrl, eps in docs:
        learned = ctrl == "policy" or not str(pol).startswith("classical")
        card = os.path.join(policy_dir, f"{pol}.json")
        tr = {}
        if learned and os.path.exists(card):
            with open(card, encoding="utf-8") as f:
                tr = json.load(f).get("training", {}) or {}
        ok = np.array([bool(e.get("ok")) for e in eps])
        kinds = [e.get("failure_kind") for e in eps]
        row = {"policy": pol, "cls": cls, "kind": "learned" if learned else "classical", "variant": tr.get("reward_variant", None if learned else "classical"),
               "n": len(eps), "pass_rate": float(ok.mean()), "sensor": None}
        for k in FAIL_KINDS:
            row[f"fail_{k}"] = int(sum(1 for x in kinds if x == k))
        rows.append(row)
    return pd.DataFrame(rows)


def fig20_lander_mc(res=RES, out=FIG, policies=POLICIES, **_):
    if not os.path.isdir(policies):
        raise Skip(f"policy directory {policies} not found")
    docs_list = _load_outcomes(policies)
    docs = {pol: (cls, ctrl, eps) for pol, cls, ctrl, eps in docs_list}
    try:
        from experiments.phase3.run_phase3 import e15_rows, PAD_RADIUS_M
        summ = e15_rows(policies)
    except Exception as e:  # noqa: BLE001  run_phase3 not importable (lunarsim data) or its relpath failing across drives
        print(f"  fig20: run_phase3.e15_rows unavailable ({e!r}); summarising the outcome tables locally")
        PAD_RADIUS_M = 50.0
        summ = _e15_summary_local(docs_list, policies)
    if summ is None or summ.empty or not docs:
        raise Skip(f"no outcomes_*.json with episodes in {policies}")
    cls_order = ["CLPS", "MK1", "LARGE"]
    summ = summ.copy()
    summ["cls_rank"] = summ["cls"].map(lambda c: cls_order.index(c) if c in cls_order else len(cls_order))
    summ["kind_rank"] = (summ["kind"] != "classical").astype(int)
    summ = summ.sort_values(["cls_rank", "kind_rank", "pass_rate"], ascending=[True, True, False]).reset_index(drop=True)
    summ["label"] = summ.apply(_policy_label, axis=1)
    n_pol = len(summ)
    ncols = min(5, n_pol)
    nrows_sc = int(math.ceil(n_pol / ncols))
    fig = plt.figure(figsize=(7.0, 1.42 * nrows_sc + 2.5))
    gs = fig.add_gridspec(nrows_sc + 1, ncols, height_ratios=[1.0] * nrows_sc + [1.75], hspace=0.7, wspace=0.12)
    lim = 120.0
    for _, (cls, ctrl, eps) in docs.items():
        m = np.array([math.hypot(*e["miss_m"]) for e in eps])
        lim = max(lim, 1.15 * float(m.max()))
    th = np.linspace(0, 2 * np.pi, 200)
    for i, row in summ.iterrows():
        r, c = divmod(i, ncols)
        ax = fig.add_subplot(gs[r, c])
        cls, ctrl, eps = docs[row["policy"]]
        xy = np.array([e["miss_m"] for e in eps], float)
        ok = np.array([bool(e.get("ok")) for e in eps])
        ax.grid(False)
        ax.set_xscale("symlog", linthresh=5.0, linscale=0.7)
        ax.set_yscale("symlog", linthresh=5.0, linscale=0.7)
        ax.plot(PAD_RADIUS_M * np.cos(th), PAD_RADIUS_M * np.sin(th), "--", lw=0.8, color=INK2)
        ax.scatter(xy[ok, 0], xy[ok, 1], s=6, color=TOL["blue"], alpha=0.55, edgecolor="none", label="passed")
        ax.scatter(xy[~ok, 0], xy[~ok, 1], s=11, marker="x", color=TOL["red"], lw=0.7, label="failed")
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        ticks = [-100, -10, 0, 10, 100]
        ax.set_xticks(ticks)
        ax.set_yticks(ticks)
        ax.set_xticklabels([f"{t:g}" for t in ticks] if r == nrows_sc - 1 or i + ncols >= n_pol else [], fontsize=6)
        ax.set_yticklabels([f"{t:g}" for t in ticks] if c == 0 else [], fontsize=6)
        ax.tick_params(length=2, pad=1.5)
        ax.set_title(f"{row['cls']}\n{row['label']}", fontsize=6.8, pad=3)
        if i == 0:
            ax.text(PAD_RADIUS_M * 0.72, PAD_RADIUS_M * 0.72, f"{PAD_RADIUS_M:g} m pad", fontsize=6, color=INK2, ha="left", va="bottom")
            ax.set_ylabel("north miss (m)", fontsize=7)
        if r == nrows_sc - 1 and c == 0:
            ax.set_xlabel("east miss (m)", fontsize=7)
    # pass-rate panel
    ax = fig.add_subplot(gs[nrows_sc, :])
    x = np.arange(n_pol)
    bottom = np.zeros(n_pol)
    n = summ["n"].to_numpy(float)
    shares = {"ok": summ["pass_rate"].to_numpy(float)}
    for k in FAIL_KINDS:
        col = f"fail_{k}"
        shares[k] = summ[col].to_numpy(float) / n if col in summ.columns else np.zeros(n_pol)
    for k, s in shares.items():
        if np.nansum(s) <= 0:
            continue
        ax.bar(x, s, 0.62, bottom=bottom, color=OUTCOME_COLOR[k], edgecolor="white", linewidth=0.5,
               label="passed" if k == "ok" else f"failed: {k}")
        bottom = bottom + np.nan_to_num(s)
    lo_hi = np.array([wilson(int(round(p * nn)), int(nn)) for p, nn in zip(summ["pass_rate"], n)])
    ax.errorbar(x, summ["pass_rate"], yerr=[summ["pass_rate"] - lo_hi[:, 0], lo_hi[:, 1] - summ["pass_rate"]], fmt="o", color=INK,
                ms=4, lw=1.0, capsize=2.5, zorder=5)
    for xi, p in zip(x, summ["pass_rate"]):
        ax.text(xi + 0.36, p, f"{100 * p:.1f} %", fontsize=6.5, color=INK, va="center", ha="left")
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['cls']}\n{r['label']}\nn = {int(r['n'])}" for _, r in summ.iterrows()], fontsize=6.5)
    ax.set_ylim(0, 1.0)
    ax.set_xlim(-0.6, n_pol - 0.2)
    ax.set_ylabel("share of episodes")
    ax.set_title("Pass rate (dot, Wilson 95 % CI) over the outcome mix", fontsize=8.5)
    ax.legend(fontsize=6.5, ncol=3, loc="upper left", bbox_to_anchor=(0.0, -0.42))
    paths = save(fig, "fig20_lander_mc", out)
    n_str = ", ".join(f"{r['cls']} {r['label']} n = {int(r['n'])}" for _, r in summ.iterrows())
    sensor = summ["sensor"].dropna().unique().tolist() if "sensor" in summ.columns else []
    sensor_txt = "; sensor noise " + ("on" if sensor == [True] else "off" if sensor == [False] else "mixed") if sensor else ""
    caption = (f"Terminal-descent Monte Carlo per lander class: the classical ZEM/ZEV law against the learned policies. Top: horizontal "
               f"miss at touchdown in plan view (symlog axes, linear within ±5 m), passed episodes as filled points and failed ones as "
               f"crosses; dashed circle = the {PAD_RADIUS_M:g} m pad radius. Bottom: pass rate (dot) with its Wilson 95 % CI (whisker) "
               f"over the stacked outcome mix. Episodes: {n_str}{sensor_txt}" +
               ". Flags: environment Modelled (3-DoF descent parameterised from flown landers, Spec); failure limits Spec; "
               "learned policies trained in-house (Modelled).")
    return {"caption": caption, "n": n_str, "ci": "Wilson 95 % interval on the pass rate", "flags": "Modelled / Spec", "files": paths}


# ---------------------------------------------------------------------------
# fig21: driving-table validation
# ---------------------------------------------------------------------------
AUT_ORDER = ["teleop", "supervised", "autonomous"]
AUT_LABEL = {"teleop": "teleoperated", "supervised": "supervised autonomy", "autonomous": "autonomous"}
AUT_COLOR = {"teleop": TOL["red"], "supervised": TOL["yellow"], "autonomous": TOL["blue"]}


def fig21_driving_validation(res=RES, out=FIG, **_):
    t16 = load_csv(res, "table_E16.csv", required=["check"])
    flat = t16[t16["check"] == "speed_made_good_vs_rtt_flat"].dropna(subset=["sim_kmh"]) if "sim_kmh" in t16.columns else pd.DataFrame()
    if flat.empty:
        raise Skip("table_E16.csv has no speed_made_good_vs_rtt_flat rows with sim_kmh")
    real = t16[t16["check"] == "speed_made_good_vs_rtt_real_leg"] if "sim_kmh" in t16.columns else pd.DataFrame()
    psr = t16[t16["check"] == "psr_round_trip_energy"]
    psr = psr.dropna(subset=["sim_kwh"]) if "sim_kwh" in psr.columns else pd.DataFrame()
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 3.0), gridspec_kw={"width_ratios": [1.25, 1.0]})
    fig.subplots_adjust(wspace=0.38)
    ax = axes[0]
    items = []
    for aut in [a for a in AUT_ORDER if a in set(flat["autonomy"])]:
        g = flat[flat["autonomy"] == aut].sort_values("rtt_s")
        ax.plot(g["rtt_s"], g["sim_kmh"], "-o", color=AUT_COLOR[aut], ms=3.5, lw=1.6)
        items.append((float(g["sim_kmh"].iloc[-1]), f"{AUT_LABEL[aut]} (sim)", AUT_COLOR[aut]))
    jsc = flat[(flat["autonomy"] == "teleop") & flat["ref_kmh"].notna()].sort_values("rtt_s") if "ref_kmh" in flat.columns else pd.DataFrame()
    if not jsc.empty:
        ax.scatter(jsc["rtt_s"], jsc["ref_kmh"], marker="D", s=26, color=INK, zorder=5, label="JSC teleop (Measured)")
        for _, r in jsc.iterrows():
            ax.annotate(f"{r['ref_kmh']:.2f}", (r["rtt_s"], r["ref_kmh"]), xytext=(-5, -9), textcoords="offset points", ha="right",
                        fontsize=6.5, color=INK)
        if "rel_err" in jsc.columns and jsc["rel_err"].notna().any():
            errs = ", ".join(f"{100 * e:+.1f} %" for e in jsc["rel_err"])
            ax.text(0.02, 0.04, f"sim − JSC: {errs}", transform=ax.transAxes, fontsize=6.5, color=INK2)
    leg_note = ""
    if not real.empty and "ref_kmh" in real.columns:
        rt = real[real["autonomy"] == "teleop"].dropna(subset=["sim_kmh"]).sort_values("rtt_s")
        if not rt.empty:
            ax.plot(rt["rtt_s"], rt["sim_kmh"], "--", color=GREYS[2], lw=1.0, marker="s", ms=2.5)
            items.append((float(rt["sim_kmh"].iloc[-1]), f"teleop, real leg ({rt['max_slope_deg'].iloc[0]:.1f}°)", GREYS[1]))
            leg_note = f" The dashed grey line is the flattest real leg of the table ({rt['leg'].iloc[0]}, max slope {rt['max_slope_deg'].iloc[0]:.1f}°), shown for context."
    ax.set_xlabel("round-trip control latency (s)")
    ax.set_ylabel("speed made good (km/h)")
    ax.set_xticks(sorted(flat["rtt_s"].unique()))
    ax.set_ylim(0, max(ax.get_ylim()[1], 10.0))
    ax.set_xlim(min(flat["rtt_s"]) - 0.5, max(flat["rtt_s"]) + 4.2)
    leg_desc = flat["leg"].iloc[0] if "leg" in flat.columns else "synthetic flat leg"
    ax.set_title(f"A. {leg_desc}: speed made good vs latency", fontsize=8.5)
    if not jsc.empty:
        ax.legend(fontsize=7, loc="upper right")
    end_labels(ax, items, x=max(flat["rtt_s"]), fontsize=6.5)
    # panel B
    ax = axes[1]
    psr_note = ""
    if psr.empty:
        panel_note(ax, "no psr_round_trip_energy rows\nin table_E16.csv")
        psr_note = " Panel B: the PSR round-trip check is absent from the table."
    else:
        lo, hi = float(psr["ref_kwh_lo"].iloc[0]), float(psr["ref_kwh_hi"].iloc[0])
        mass = float(psr["rover_mass_kg"].iloc[0]) if "rover_mass_kg" in psr.columns else np.nan
        ax.axhspan(lo, hi, color="#dfe8f3", lw=0, zorder=0)
        ax.text(0.02, hi * 0.97, f"Chen 2026 band {lo:.2f}-{hi:.2f} kWh\n(0.4-4.4 kWh at 500 kg, scaled ×{mass / 500:g} by mass)" if np.isfinite(mass)
                else f"Chen 2026 band {lo:.2f}-{hi:.2f} kWh", transform=blended_transform_factory(ax.transAxes, ax.transData),
                fontsize=6.5, color=INK2, va="top")
        auts = [a for a in AUT_ORDER if a in set(psr["autonomy"])] + sorted(set(psr["autonomy"]) - set(AUT_ORDER))
        xs = np.arange(len(auts))
        periods = list(dict.fromkeys(psr["lighting"]))
        mk = {"day": ("o", "full"), "night": ("o", "none")}
        for j, per in enumerate(periods):
            sub = psr[psr["lighting"] == per].set_index("autonomy").reindex(auts)
            m, fs = mk.get(per, ("s", "full"))
            off = (j - (len(periods) - 1) / 2) * 0.16
            ax.plot(xs + off, sub["sim_kwh"], m, color=TOL["blue"], ms=6, fillstyle=fs, mew=1.2, ls="none", label=f"{per} (sim)")
            for xi, v in zip(xs + off, sub["sim_kwh"]):
                if np.isfinite(v):
                    ax.annotate(f"{v:.2f}", (xi, v), xytext=(0, 7 if j == 0 else -12), textcoords="offset points", ha="center", fontsize=6, color=INK2)
        ax.set_xticks(xs)
        ax.set_xticklabels([AUT_LABEL.get(a, a) for a in auts], fontsize=7.5)
        ax.set_ylabel("energy, BASE↔PSR round trip (kWh)")
        ax.set_ylim(0, hi * 1.15)
        km = float(psr["length_m"].iloc[0]) / 1000 if "length_m" in psr.columns else np.nan
        ax.set_title(f"B. PSR round trip ({km:.1f} km) vs the mass-scaled Chen band" if np.isfinite(km) else "B. PSR round trip vs the Chen band", fontsize=8.5)
        ax.legend(fontsize=7, loc="center right")
        rtt_bin = psr["rtt_s"].iloc[0]
        psr_note = (f" Panel B: traction energy of the BASE→PSR and PSR→BASE legs at the {rtt_bin:g} s latency bin, day and night, per "
                    f"autonomy level, against the Chen (2026) 0.4-4.4 kWh band for a 500 kg rover scaled linearly to the table's "
                    f"{mass:g} kg rover (Assumed).")
    paths = save(fig, "fig21_driving_validation", out)
    n_runs = ""
    if "note" in flat.columns:
        import re
        m = re.search(r"mean over (\d+) runs", str(flat["note"].iloc[0]))
        if m:
            n_runs = f"; the stochastic mean over {m.group(1)} integrator runs differs by < 1 %"
    caption = (f"Driving-table validation. Panel A: speed made good on the {leg_desc} through the table's own leg integrator (deterministic "
               f"made-good with whole stops{n_runs}) per autonomy level against the JSC teleoperation points (Litaker et al., Measured; "
               f"values printed)." + leg_note + psr_note +
               " n = deterministic integrator means, no replication (the table has no seeds). Flags: JSC points Measured; Chen band Modelled; mass "
               "scaling Assumed; table legs Modelled on LOLA 5 m terrain (Measured).")
    return {"caption": caption, "n": "deterministic integrator means (no replication)", "ci": "none (point checks)",
            "flags": "Measured anchors, Modelled table, Assumed mass scaling", "files": paths}


# ---------------------------------------------------------------------------
# fig22: dispersion x pad radius (paired vs the classical level)
# ---------------------------------------------------------------------------
MISS_SHORT = {"SLIM pre-divert": "SLIM", "ADD Rev C target": "ADD Rev C", "NASA 50-100 m / HLS 100 m 3-sigma": "NASA/HLS",
              "Blue Ghost M1": "Blue Ghost", "IM-2": "IM-2", "IM-1": "IM-1"}


def _e17_table(res):
    return table_or_raw(res, "table_E17.csv", "E17_dispersion_standoff.csv", fl.table_e17,
                        required=["scenario", "mechanism", "miss_level_m", "pad_radius_m", "pad_standoff_km", "n_seeds"])


def fig22_dispersion_standoff(res=RES, out=FIG, standoff=1.0, metric="delay_prio1_mean_h", **_):
    t = _e17_table(res)
    dcol = f"dCL_{metric}"
    if dcol not in t.columns:
        raise Skip(f"table_E17 has no {dcol}: the paired difference needs the classical miss level and at least one other level in the table")
    D = nearest(t["pad_standoff_km"], standoff)
    sub = t[np.isclose(t["pad_standoff_km"], D)]
    scens = scenario_order(sub)
    mechs = mechs_present(sub)
    radii = sorted(sub["pad_radius_m"].unique())
    rcol = dict(zip(radii, ordered_colors(len(radii))))
    has_offpad = "offpad_share" in sub.columns
    nrows = len(mechs) + (1 if has_offpad else 0)
    ncols = len(scens)
    fig, axes = plt.subplots(nrows, ncols, figsize=(7.0, 1.85 * nrows + 0.7), sharex=True, squeeze=False)
    fig.subplots_adjust(hspace=0.35, wspace=0.3, top=0.9)
    labels = sub.drop_duplicates("miss_level_m").set_index("miss_level_m")["miss_label"] if "miss_label" in sub.columns else {}
    for r, m in enumerate(mechs):
        for c, (sc, nv) in enumerate(scens):
            ax = axes[r, c]
            cell = sub[(sub["mechanism"] == m) & (sub["scenario"] == sc)]
            ax.axhline(0, color=MUTED, lw=0.8)
            items = []
            for pr in radii:
                g = cell[cell["pad_radius_m"] == pr].dropna(subset=[dcol]).sort_values("miss_level_m")
                if g.empty:
                    continue
                lo = g[f"{dcol}_lo"] if f"{dcol}_lo" in g.columns else g[dcol]
                hi = g[f"{dcol}_hi"] if f"{dcol}_hi" in g.columns else g[dcol]
                ax.errorbar(g["miss_level_m"], g[dcol], yerr=[g[dcol] - lo, hi - g[dcol]], fmt="-o", color=rcol[pr], ms=3, lw=1.3,
                            capsize=1.5, elinewidth=0.7)
                items.append((float(g[dcol].iloc[-1]), f"{pr:g} m pad", rcol[pr]))
            ax.set_xscale("log")
            if r == 0:
                ax.set_title(scen_label(sc, nv), fontsize=8.5, pad=30 if len(labels) else 4)
                if len(labels):
                    lv = sorted(x for x in labels.index if x > 0 and labels[x] != fl.CLASSICAL_LABEL)
                    tr = blended_transform_factory(ax.transData, ax.transAxes)
                    for k, x in enumerate(lv):
                        y = 1.03 + 0.09 * (k % 3)
                        ax.plot([x, x], [1.0, y], color=MUTED, lw=0.5, transform=tr, clip_on=False)
                        ax.text(x, y + 0.01, MISS_SHORT.get(labels[x], str(labels[x])), transform=tr, fontsize=5.5, color=INK2,
                                ha="center", va="bottom", clip_on=False)
            if c == 0:
                ax.set_ylabel(f"{mech_label(m)}\nΔ urgent mean delay (h)", fontsize=8)
            if c == ncols - 1:
                end_labels(ax, items, x=float(cell["miss_level_m"].max()) if not cell.empty else 1.0, fontsize=6.5)
            ax.tick_params(labelsize=7)
    if has_offpad:
        for c, (sc, nv) in enumerate(scens):
            ax = axes[nrows - 1, c]
            cell = sub[(sub["scenario"] == sc) & (sub["mechanism"] == mechs[0])] if mechs else sub[sub["scenario"] == sc]
            items = []
            for pr in radii:
                g = cell[cell["pad_radius_m"] == pr].dropna(subset=["offpad_share"]).sort_values("miss_level_m")
                if g.empty:
                    continue
                err = 100 * g["offpad_share_ci95"].fillna(0) if "offpad_share_ci95" in g.columns else None
                ax.errorbar(g["miss_level_m"], 100 * g["offpad_share"], yerr=err, fmt="-o", color=rcol[pr], ms=3, lw=1.3, capsize=1.5, elinewidth=0.7)
                items.append((float(100 * g["offpad_share"].iloc[-1]), f"{pr:g} m pad", rcol[pr]))
            ax.set_xscale("log")
            ax.set_ylim(-3, 103)
            if c == 0:
                ax.set_ylabel("off-pad landings (%)", fontsize=8)
            if c == ncols - 1:
                end_labels(ax, items, x=float(cell["miss_level_m"].max()) if not cell.empty else 1.0, fontsize=6.5)
            ax.set_xlabel("implied mean |miss| (m)", fontsize=8)
            ax.tick_params(labelsize=7)
    else:
        for c in range(ncols):
            axes[nrows - 1, c].set_xlabel("implied mean |miss| (m)", fontsize=8)
    paths = save(fig, "fig22_dispersion_standoff", out)
    ncom = [c for c in sub.columns if c.startswith("n_common")]
    ntxt = n_text(sub["n_seeds"])
    caption = (f"Landing dispersion acts through off-pad landings. Rows 1-{len(mechs)}: paired difference in the mean urgent-item delay "
               f"against the classical miss level (dCL) as a function of the implied mean |miss| (log axis; flown-lander and requirement "
               f"anchors on top), one line per pad radius, pad standoff {D:g} km, small multiples by fleet (columns) and dispatch mechanism "
               f"(rows). Bottom row: share of landings beyond the pad radius. {ntxt}; differences are paired on common seeds and the "
               f"whiskers are percentile seed-bootstrap 95 % CIs ({fl.N_BOOT} resamples, fit_law.paired); off-pad whiskers are 1.96 SE "
               f"over seeds. Flags: miss levels Measured (SLIM, Blue Ghost M1, IM-1, IM-2) and Spec (ADD Rev C 50 m, NASA/HLS 100 m); "
               f"the classical level Modelled ({fl.CLASSICAL_LABEL}); terrain Measured (LOLA 5 m); logistics Modelled."
               + (" PRELIMINARY: fewer than 10 seeds per cell." if sub["n_seeds"].max() < 10 else ""))
    return {"caption": caption, "n": ntxt, "ci": "paired seed-bootstrap 95 % percentile CI; 1.96 SE for shares",
            "flags": "Measured anchors, Spec requirements, Modelled logistics", "files": paths, "standoff_km": D, "n_common_cols": ncom}


# ---------------------------------------------------------------------------
# fig23: pad standoff
# ---------------------------------------------------------------------------
STANDOFF_METRICS = [("delay_prio1_mean_h", "urgent mean delay (h)"), ("km_total", "fleet km per year"), ("energy_kwh", "driving energy (kWh / yr)")]


def fig23_standoff(res=RES, out=FIG, miss_label=fl.CLASSICAL_LABEL, pad_radius=50.0, **_):
    t = _e17_table(res)
    if "miss_label" in t.columns and (t["miss_label"] == miss_label).any():
        sub = t[t["miss_label"] == miss_label]
        miss_desc = miss_label
    else:
        lvl = float(t["miss_level_m"].min())
        sub = t[t["miss_level_m"] == lvl]
        miss_desc = f"mean |miss| {lvl:g} m"
    pr = nearest(sub["pad_radius_m"], pad_radius)
    sub = sub[np.isclose(sub["pad_radius_m"], pr)]
    metrics = [(m, lab) for m, lab in STANDOFF_METRICS if m in sub.columns]
    if not metrics:
        raise Skip("table_E17 has none of " + ", ".join(m for m, _ in STANDOFF_METRICS))
    has_d = any(f"dD1_{m}" in sub.columns for m, _ in metrics)
    scens = scenario_order(sub)
    mechs = mechs_present(sub)
    scol = {sc: SCEN_COLOR[i % len(SCEN_COLOR)] for i, (sc, _) in enumerate(scens)}
    nrows = 2 if has_d else 1
    fig, axes = plt.subplots(nrows, len(metrics), figsize=(7.0, 2.6 * nrows + 0.4), squeeze=False)
    fig.subplots_adjust(wspace=0.38, hspace=0.42)
    standoffs = sorted(sub["pad_standoff_km"].unique())
    for j, (m, lab) in enumerate(metrics):
        ax = axes[0, j]
        for (sc, nv) in scens:
            for mech in mechs:
                g = sub[(sub["scenario"] == sc) & (sub["mechanism"] == mech)].sort_values("pad_standoff_km")
                if g.empty:
                    continue
                err = g[f"{m}_ci95"].fillna(0) if f"{m}_ci95" in g.columns else None
                ax.errorbar(g["pad_standoff_km"], g[m], yerr=err, fmt="o", ls=MECH_LS.get(mech, "-"), color=scol[sc], ms=3, lw=1.4,
                            capsize=1.5, elinewidth=0.7)
        ax.set_xticks(standoffs)
        ax.set_title(lab, fontsize=8.5)
        ax.tick_params(labelsize=7.5)
        if not has_d:
            ax.set_xlabel("pad standoff from BASE (km)", fontsize=8)
        if has_d:
            ax = axes[1, j]
            dcol = f"dD1_{m}"
            ax.axhline(0, color=MUTED, lw=0.8)
            if dcol not in sub.columns:
                panel_note(ax, f"no {dcol}")
            else:
                for (sc, nv) in scens:
                    for mech in mechs:
                        g = sub[(sub["scenario"] == sc) & (sub["mechanism"] == mech)].sort_values("pad_standoff_km")
                        g = g.assign(**{dcol: g[dcol].where(~np.isclose(g["pad_standoff_km"], 1.0), 0.0)})
                        lo = g[f"{dcol}_lo"].where(~np.isclose(g["pad_standoff_km"], 1.0), 0.0) if f"{dcol}_lo" in g.columns else g[dcol]
                        hi = g[f"{dcol}_hi"].where(~np.isclose(g["pad_standoff_km"], 1.0), 0.0) if f"{dcol}_hi" in g.columns else g[dcol]
                        g = g.dropna(subset=[dcol])
                        if g.empty:
                            continue
                        lo, hi = lo.loc[g.index].fillna(g[dcol]), hi.loc[g.index].fillna(g[dcol])
                        ax.errorbar(g["pad_standoff_km"], g[dcol], yerr=[g[dcol] - lo, hi - g[dcol]], fmt="o", ls=MECH_LS.get(mech, "-"),
                                    color=scol[sc], ms=3, lw=1.4, capsize=1.5, elinewidth=0.7)
                ax.set_xticks(standoffs)
                ax.set_title(f"Δ vs 1 km: {lab}", fontsize=8.5)
                ax.set_xlabel("pad standoff from BASE (km)", fontsize=8)
                ax.tick_params(labelsize=7.5)
    handles = [Line2D([0], [0], color=scol[sc], lw=1.6, label=scen_label(sc, nv)) for sc, nv in scens]
    handles += [Line2D([0], [0], color=INK2, lw=1.4, ls=MECH_LS.get(mech, "-"), label=mech_label(mech)) for mech in mechs]
    fig.legend(handles=handles, loc="upper center", ncol=min(len(handles), 6), fontsize=7, bbox_to_anchor=(0.5, 1.02 if has_d else 1.06))
    paths = save(fig, "fig23_standoff", out)
    ntxt = n_text(sub["n_seeds"])
    caption = (f"Pad standoff from BASE. Top: cell means of {', '.join(lab for _, lab in metrics)} against standoff for each fleet (colour) "
               f"and dispatch mechanism (line style), {miss_desc}, {pr:g} m pad radius; whiskers are 95 % CIs (1.96 SE over seeds)." +
               (" Bottom: paired differences against the 1 km standoff (dD1) on common seeds, whiskers = percentile seed-bootstrap 95 % CIs "
                f"({fl.N_BOOT} resamples); the 1 km point is the reference (0)." if has_d else "") +
               f" {ntxt}. Flags: terrain Measured (LOLA 5 m, Connecting ridge); driving legs and landings Modelled; standoff set Assumed (swept)."
               + (" PRELIMINARY: fewer than 10 seeds per cell." if sub["n_seeds"].max() < 10 else ""))
    return {"caption": caption, "n": ntxt, "ci": "95 % CI = 1.96 SE over seeds (means); paired seed-bootstrap 95 % percentile CI (differences)",
            "flags": "Measured terrain, Modelled logistics, Assumed sweep", "files": paths}


# ---------------------------------------------------------------------------
# fig24: plume keep-out heatmaps
# ---------------------------------------------------------------------------
def fig24_plume(res=RES, out=FIG, standoff=1.0, metric="delay_prio1_mean_h", **_):
    t = table_or_raw(res, "table_E18.csv", "E18_plume.csv", fl.table_e18,
                     required=["scenario", "mechanism", "night_fraction", "pad_standoff_km", "keepout_km", "standdown_h", "n_seeds"])
    dcol = f"dNP_{metric}"
    if dcol not in t.columns:
        raise Skip(f"table_E18 has no {dcol} (no-plume reference cells missing)")
    D = nearest(t["pad_standoff_km"], standoff)
    sub = t[np.isclose(t["pad_standoff_km"], D) & (t["keepout_km"] > 0)].dropna(subset=[dcol])
    if sub.empty:
        raise Skip(f"table_E18 has no plume cells with {dcol} at standoff {D:g} km")
    scens = scenario_order(sub)
    nights = sorted(sub["night_fraction"].unique(), reverse=True)
    rows = [(sc, nv, nf) for (sc, nv) in scens for nf in nights if ((sub["scenario"] == sc) & (sub["night_fraction"] == nf)).any()]
    mechs = mechs_present(sub)
    keepouts = sorted(sub["keepout_km"].unique())
    standdowns = sorted(sub["standdown_h"].unique())
    vmax = float(np.nanpercentile(np.abs(sub[dcol]), 98)) or 1.0
    nr, nc = len(rows), len(mechs)
    has_sd = "standdown_vehicle_h" in sub.columns
    fig = plt.figure(figsize=(7.0, 1.2 * nr + (2.1 if has_sd else 0) + 0.9))
    gs = fig.add_gridspec(nr + (1 if has_sd else 0), nc + 1, width_ratios=[1.0] * nc + [0.06],
                          height_ratios=[1.0] * nr + ([1.9] if has_sd else []), hspace=0.42, wspace=0.12)
    norm = TwoSlopeNorm(vmin=-vmax, vcenter=0.0, vmax=vmax)
    im = None
    for r, (sc, nv, nf) in enumerate(rows):
        for c, mech in enumerate(mechs):
            ax = fig.add_subplot(gs[r, c])
            ax.grid(False)
            cell = sub[(sub["scenario"] == sc) & (sub["night_fraction"] == nf) & (sub["mechanism"] == mech)]
            if cell.empty:
                panel_note(ax, "no cells", fontsize=6.5)
                continue
            piv = cell.pivot_table(index="standdown_h", columns="keepout_km", values=dcol, aggfunc="mean").reindex(index=standdowns, columns=keepouts)
            im = ax.imshow(piv.to_numpy(float), cmap=DIVERGING, norm=norm, aspect="auto", origin="lower")
            if f"{dcol}_lo" in cell.columns and f"{dcol}_hi" in cell.columns:
                lo = cell.pivot_table(index="standdown_h", columns="keepout_km", values=f"{dcol}_lo", aggfunc="mean").reindex(index=standdowns, columns=keepouts).to_numpy(float)
                hi = cell.pivot_table(index="standdown_h", columns="keepout_km", values=f"{dcol}_hi", aggfunc="mean").reindex(index=standdowns, columns=keepouts).to_numpy(float)
                sig = (lo > 0) | (hi < 0)
                for (yi, xi) in zip(*np.where(sig)):
                    ax.add_patch(Rectangle((xi - 0.5, yi - 0.5), 1, 1, fill=False, ec=INK, lw=0.9))
            vals = piv.to_numpy(float)
            for yi in range(vals.shape[0]):
                for xi in range(vals.shape[1]):
                    v = vals[yi, xi]
                    if np.isfinite(v):
                        ax.text(xi, yi, f"{v:+.1f}", ha="center", va="center", fontsize=5.2, color="white" if abs(v) > 0.6 * vmax else INK)
            ax.set_xticks(range(len(keepouts)))
            ax.set_yticks(range(len(standdowns)))
            ax.set_xticklabels([f"{k:g}" for k in keepouts] if r == nr - 1 else [], fontsize=6)
            ax.set_yticklabels([f"{s:g}" for s in standdowns] if c == 0 else [], fontsize=6)
            ax.tick_params(length=2, pad=1.5)
            if r == 0:
                ax.set_title(mech_label(mech), fontsize=8, color=mech_color(mech, c))
            if c == 0:
                ax.set_ylabel(f"{scen_label(sc, nv)}\n{'night ' + format(100 * nf, 'g') + ' %' if nf > 0 else 'no night'}\nstand-down (h)", fontsize=6.5)
            if r == nr - 1:
                ax.set_xlabel("keep-out radius (km)", fontsize=7)
    if im is not None:
        cax = fig.add_subplot(gs[:nr, nc])
        cb = fig.colorbar(im, cax=cax)
        cb.set_label("Δ urgent mean delay vs no plume (h)", fontsize=7)
        cb.ax.tick_params(labelsize=6)
    sd_note = ""
    if has_sd:
        sc0, nv0, nf0 = rows[0]
        scol = dict(zip(standdowns, ordered_colors(len(standdowns))))
        kpos = {k: i for i, k in enumerate(keepouts)}
        for c, mech in enumerate(mechs):
            ax = fig.add_subplot(gs[nr, c])
            cell = sub[(sub["scenario"] == sc0) & (sub["night_fraction"] == nf0) & (sub["mechanism"] == mech)]
            items = []
            for sd in standdowns:
                g = cell[cell["standdown_h"] == sd].sort_values("keepout_km")
                if g.empty:
                    continue
                err = g["standdown_vehicle_h_ci95"].fillna(0) if "standdown_vehicle_h_ci95" in g.columns else None
                xk = g["keepout_km"].map(kpos)
                ax.errorbar(xk, g["standdown_vehicle_h"], yerr=err, fmt="-o", color=scol[sd], ms=2.8, lw=1.3, capsize=1.5, elinewidth=0.7)
                items.append((float(g["standdown_vehicle_h"].iloc[-1]), f"stand-down {sd:g} h", scol[sd]))
            ax.set_xticks(range(len(keepouts)))
            ax.set_xticklabels([f"{k:g}" for k in keepouts], fontsize=6)
            ax.tick_params(labelsize=6.5)
            ax.set_xlabel("keep-out radius (km)", fontsize=7)
            if c == 0:
                ax.set_ylabel(f"stand-down vehicle-h / yr\n({scen_label(sc0, nv0)}, {'night ' + format(100 * nf0, 'g') + ' %' if nf0 > 0 else 'no night'})", fontsize=6.5)
            else:
                ax.tick_params(labelleft=False)
            if c == nc - 1:
                end_labels(ax, items, x=len(keepouts) - 1, fontsize=6)
            ax.text(0.03, 0.93, mech_label(mech), transform=ax.transAxes, fontsize=7, color=mech_color(mech, c), va="top")
        sd_note = (f" Bottom row: vehicle-hours lost to keep-out holds and evacuations per year against keep-out radius, one line per "
                   f"stand-down time ({scen_label(sc0, nv0)}, {'night ' + format(100 * nf0, 'g') + ' %' if nf0 > 0 else 'no night'}; whiskers 1.96 SE).")
    paths = save(fig, "fig24_plume", out)
    ntxt = n_text(sub["n_seeds"])
    per_scen = "; ".join(f"{scen_label(sc, nv)}: {n_text(sub[sub['scenario'] == sc]['n_seeds'], 'seeds')}" for sc, nv in scens)
    caption = (f"Plume keep-out. Heatmaps of the paired difference in the mean urgent-item delay against the matching no-plume cell (dNP, "
               f"hours, printed in each cell) over keep-out radius × stand-down time, pad standoff {D:g} km, small multiples by fleet and "
               f"night share (rows) and dispatch mechanism (columns); cells whose percentile seed-bootstrap 95 % CI ({fl.N_BOOT} resamples) "
               f"excludes 0 are outlined. Colour scale clipped at the 98th percentile of |dNP| ({vmax:.2f} h).{sd_note} {ntxt} ({per_scen}). "
               f"Flags: keep-out radius and stand-down Assumed (swept, not predicted; NASA calls PSI predictions qualitative); impacts-vs-distance "
               f"ordering Modelled (Wittal et al.); logistics Modelled."
               + (" PRELIMINARY: some cells have fewer than 10 seeds." if sub["n_seeds"].min() < 10 else ""))
    return {"caption": caption, "n": ntxt, "ci": "paired seed-bootstrap 95 % CI (outlined cells exclude 0); 1.96 SE for stand-down hours",
            "flags": "Assumed sweep, Modelled logistics", "files": paths}


# ---------------------------------------------------------------------------
# fig25: autonomy level x fleet size
# ---------------------------------------------------------------------------
def _aut_levels(df):
    """Ordered autonomy levels present: teleop by descending RTT, then supervised, autonomous. [(key, label, mask_fn)]."""
    levels = []
    tele = sorted(df[df["autonomy"] == "teleop"]["rtt_s"].dropna().unique(), reverse=True)
    for rtt in tele:
        levels.append(((f"teleop", rtt), f"teleop, {rtt:g} s RTT"))
    for a in ("supervised", "autonomous"):
        if (df["autonomy"] == a).any():
            levels.append(((a, None), AUT_LABEL[a]))
    others = sorted(set(df["autonomy"].unique()) - {"teleop", "supervised", "autonomous"})
    for a in others:
        levels.append(((a, None), str(a)))
    return levels


def _aut_mask(df, key):
    a, rtt = key
    m = df["autonomy"] == a
    if rtt is not None:
        m &= np.isclose(df["rtt_s"].astype(float), rtt)
    return m


def fig25_autonomy_fleet(res=RES, out=FIG, **_):
    t = table_or_raw(res, "table_E19.csv", "E19_autonomy_fleet.csv", fl.table_e19,
                     required=["n_vehicles", "mechanism", "autonomy", "rtt_s", "n_seeds"])
    metrics = [(m, lab) for m, lab in (("delay_prio1_mean_h", "urgent mean delay (h)"), ("operator_hours", "operator console hours / yr"))
               if m in t.columns]
    if not metrics:
        raise Skip("table_E19 has neither delay_prio1_mean_h nor operator_hours")
    mechs = mechs_present(t)
    levels = _aut_levels(t)
    lcol = dict(zip([k for k, _ in levels], ordered_colors(len(levels))))
    fleets = sorted(t["n_vehicles"].unique())
    fig, axes = plt.subplots(len(metrics), len(mechs), figsize=(7.0, 2.5 * len(metrics) + 0.3), squeeze=False, sharey="row")
    fig.subplots_adjust(wspace=0.12, hspace=0.38, right=0.84)
    for i, (m, lab) in enumerate(metrics):
        for j, mech in enumerate(mechs):
            ax = axes[i, j]
            items = []
            for key, label in levels:
                g = t[_aut_mask(t, key) & (t["mechanism"] == mech)].sort_values("n_vehicles")
                if g.empty:
                    continue
                ax.plot(g["n_vehicles"], g[m], "-o", color=lcol[key], ms=3.5, lw=1.6)
                if f"{m}_ci95" in g.columns:
                    ci = g[f"{m}_ci95"].fillna(0)
                    ax.fill_between(g["n_vehicles"], g[m] - ci, g[m] + ci, color=lcol[key], alpha=0.15, lw=0)
                items.append((float(g[m].iloc[-1]), label, lcol[key]))
            ax.set_xticks(fleets)
            ax.tick_params(labelsize=8)
            if i == 0:
                ax.set_title(mech_label(mech), fontsize=9, color=mech_color(mech, j))
            if i == len(metrics) - 1:
                ax.set_xlabel("vehicles in the fleet", fontsize=8.5)
            if j == 0:
                ax.set_ylabel(lab, fontsize=8.5)
            if j == len(mechs) - 1:
                end_labels(ax, items, x=max(fleets), fontsize=6.5)
    paths = save(fig, "fig25_autonomy_fleet", out)
    ntxt = n_text(t["n_seeds"])
    scen = t["scenario"].iloc[0].split("-")[0] if "scenario" in t.columns else "P2"
    caption = (f"Vehicle autonomy level and fleet size ({scen} demand, every vehicle at the same level): "
               f"{' and '.join(lab for _, lab in metrics)} against fleet size for teleoperation at 4, 6 and 8 s round-trip latency, "
               f"supervised autonomy and full autonomy (ordered colours), in-house fleets vs the marketplace (columns). Bands are 95 % CIs "
               f"(±1.96 SE over seeds). {ntxt}. Flags: speed-vs-latency and stop cadence Modelled on JSC teleoperation (Measured); intervention rates Assumed "
               f"by autonomy level; operators per fleet = max(2, n/2) (Assumed); latencies Spec (Moon direct 4 s) and Assumed (6, 8 s relayed).")
    return {"caption": caption, "n": ntxt, "ci": "95 % CI bands (±1.96 SE over seeds)", "flags": "Modelled on Measured JSC curve; Assumed interventions",
            "files": paths}


# ---------------------------------------------------------------------------
# fig26: pad siting
# ---------------------------------------------------------------------------
def fig26_siting(res=RES, out=FIG, scenario="P2-default", mechanism="marketplace", pad_radius=50.0, miss_label=fl.CLASSICAL_LABEL, **_):
    sit = load_csv(res, "table_E20_siting.csv", required=["pad_standoff_km", "total_musd", "energy_price_usd_per_kwh",
                                                           "pad_case_usd_per_kg_transport", "damage_musd_per_impact", "min_cost"])
    mpath = os.path.join(res, "table_E20_siting_min.csv")
    mins = pd.read_csv(mpath) if os.path.exists(mpath) else fl.siting_minimum(sit)
    # reference cell
    ref = sit
    for col, want in (("miss_label", miss_label), ("scenario", scenario), ("mechanism", mechanism)):
        if col in ref.columns and (ref[col] == want).any():
            ref = ref[ref[col] == want]
        elif col in ref.columns:
            ref = ref[ref[col] == ref[col].iloc[0]]
    if "pad_radius_m" in ref.columns:
        ref = ref[np.isclose(ref["pad_radius_m"], nearest(ref["pad_radius_m"], pad_radius))]
    desc = ", ".join(str(ref[c].iloc[0]) for c in ("scenario", "mechanism", "miss_label") if c in ref.columns)
    if "pad_radius_m" in ref.columns:
        desc += f", {ref['pad_radius_m'].iloc[0]:g} m pad"
    prices = sorted(sit["energy_price_usd_per_kwh"].unique())
    cases = sit.drop_duplicates("pad_case_usd_per_kg_transport")
    if "pad_cost_musd" in cases.columns:
        cases = cases.sort_values("pad_cost_musd")
    cases = list(cases["pad_case_usd_per_kg_transport"])
    case_ls = dict(zip(cases, [":", "--", "-", "-."][:len(cases)]))
    dmg = sorted(sit["damage_musd_per_impact"].unique())
    dcol = dict(zip(dmg, ordered_colors(len(dmg))))
    standoffs = sorted(sit["pad_standoff_km"].unique())
    fig, axes = plt.subplots(2, max(len(prices), 1), figsize=(7.0, 5.4), squeeze=False, gridspec_kw={"height_ratios": [1.0, 1.15]})
    fig.subplots_adjust(hspace=0.5, wspace=0.08)
    ymin = max(float(ref["total_musd"].min()) * 0.7, 1e-3) if not ref.empty else 0.1
    ymax = float(ref["total_musd"].max()) * 1.5 if not ref.empty else 1.0
    for j, p in enumerate(prices):
        ax = axes[0, j]
        g0 = ref[ref["energy_price_usd_per_kwh"] == p]
        for case in cases:
            for d in dmg:
                g = g0[(g0["pad_case_usd_per_kg_transport"] == case) & (g0["damage_musd_per_impact"] == d)].sort_values("pad_standoff_km")
                if g.empty:
                    continue
                ax.plot(g["pad_standoff_km"], g["total_musd"], ls=case_ls[case], color=dcol[d], lw=1.3)
                mn = g[g["min_cost"].astype(bool)]
                ax.plot(mn["pad_standoff_km"], mn["total_musd"], "o", color=dcol[d], ms=4.5, mec="white", mew=0.6, zorder=5)
        ax.set_xticks(standoffs)
        ax.set_xticklabels([f"{s:g}" for s in standoffs], fontsize=7)
        ax.set_yscale("log")
        ax.set_ylim(ymin, ymax)
        ax.set_title(f"energy {p:g} \\$/kWh", fontsize=8.5)
        ax.set_xlabel("pad standoff (km)", fontsize=8)
        ax.tick_params(labelsize=7.5)
        if j == 0:
            ax.set_ylabel("cost per year (M\\$, log)\nhauling + pad + plume damage", fontsize=8)
        else:
            ax.tick_params(labelleft=False)
    handles = [Line2D([0], [0], color=dcol[d], lw=1.6, label=f"damage {d:g} M\\$/impact") for d in dmg]
    handles += [Line2D([0], [0], color=INK2, lw=1.3, ls=case_ls[c], label=f"pad at {c} \\$/kg transport") for c in cases]
    handles += [Line2D([0], [0], marker="o", color=INK2, ls="none", ms=4.5, label="minimum-cost standoff")]
    fig.legend(handles=handles, loc="upper center", ncol=min(len(handles), 4), fontsize=6.8, bbox_to_anchor=(0.5, 1.01))
    # dot plot of the share of minima
    gs = axes[1, 0].get_gridspec()
    for ax in axes[1, :]:
        ax.remove()
    ax = fig.add_subplot(gs[1, :])
    summ = fl.siting_summary(mins, standoffs=standoffs)
    share_cols = [c for c in summ.columns if c.startswith("share_min_at_")]
    xs = [float(c[len("share_min_at_"):-2]) for c in share_cols]
    summ = summ.sort_values(["energy_price_usd_per_kwh", "damage_musd_per_impact"]).reset_index(drop=True)
    grp = [c for c in fl.SITING_CELL if c in mins.columns and c != "pad_standoff_km"] + ["pad_case_usd_per_kg_transport"]
    n_groups = int(mins.groupby(grp).ngroups / max(summ.shape[0], 1) * summ.shape[0] / max(summ.shape[0], 1)) if len(mins) else 0
    n_per_row = int(len(mins) / max(len(summ), 1))
    for i, r in summ.iterrows():
        for x, c in zip(xs, share_cols):
            s = float(r[c])
            if s <= 0:
                ax.plot(x, i, ".", color=GRID, ms=3)
                continue
            ax.scatter(x, i, s=25 + 170 * s, color=TOL["blue"], alpha=0.25 + 0.7 * s, edgecolor="none", zorder=3)
            ax.text(x, i, f"{100 * s:.0f}", ha="center", va="center", fontsize=6, color="white" if s > 0.5 else INK, zorder=4)
    ax.set_yticks(range(len(summ)))
    ax.set_yticklabels([f"{r['energy_price_usd_per_kwh']:g} \\$/kWh, {r['damage_musd_per_impact']:g} M\\$/impact" for _, r in summ.iterrows()], fontsize=7)
    ax.invert_yaxis()
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x:g}" for x in xs], fontsize=7.5)
    ax.set_xlabel("minimum-cost pad standoff (km)", fontsize=8)
    ax.set_title(f"Share of cell × pad-cost groups ({n_per_row} per row) whose cost minimum lies at each standoff (%)", fontsize=8)
    ax.grid(axis="x")
    paths = save(fig, "fig26_siting", out)
    ntxt = n_text(ref["n_seeds"]) if "n_seeds" in ref.columns else n_text(sit["n_seeds"]) if "n_seeds" in sit.columns else "n unknown"
    flag = str(sit["flag"].iloc[0]) if "flag" in sit.columns else ("hauling Modelled; energy price Assumed; pad cost Spec (Metzger & Autry 2022); "
                                                                   "plume impacts Modelled (Wittal et al.); damage cost Assumed")
    caption = (f"Pad siting. Top: total cost per year (operator cost of hauling + priced driving energy + amortised pad construction over "
               f"{fl.PAD_LIFE_YEARS:g} yr + expected plume damage = landings/yr × impacts per landing × line-of-sight shield × cost per impact) "
               f"against pad standoff for the reference cell ({desc}; cell means, {ntxt}), one line per damage cost (colour) and pad-cost case "
               f"(line style), small multiples by energy price; the filled marker is the minimum-cost standoff. Bottom: share of all cells and "
               f"pad-cost cases whose minimum lies at each standoff, by energy price and damage cost ({n_per_row} groups per row). "
               f"Flags: {flag}. The pad cost does not depend on standoff and shifts totals, not minima.")
    return {"caption": caption, "n": ntxt, "ci": "none shown (cell means; the siting terms are deterministic given the means)", "flags": flag,
            "files": paths}


# ---------------------------------------------------------------------------
# fig27: the law (forest plot)
# ---------------------------------------------------------------------------
TERM_DISPLAY = [  # (term, label, unit multiplier applied to the coefficient before exp())
    ("log_miss", "mean |miss| × 2.72 (ln miss + 1)", 1.0),
    ("offpad_share", "off-pad share + 0.1", 0.1),
    ("pad_radius_m", "pad radius + 10 m", 10.0),
    ("standoff", "pad standoff + 1 km", 1.0),
    ("keepout", "keep-out radius + 1 km", 1.0),
    ("standdown", "stand-down + 1 h", 1.0),
    ("night_fraction", "night share + 0.15", 0.15),
    ("util", "reference utilisation + 0.01", 0.01),
    ("log_miss:standoff", "ln miss × standoff (+1 × +1 km)", 1.0),
    ("log_miss:util", "ln miss × utilisation (+1 × +0.01)", 0.01),
    ("keepout:standdown", "keep-out × stand-down (+1 km × +1 h)", 1.0),
    ("keepout:util", "keep-out × utilisation (+1 km × +0.01)", 0.01),
    ("standdown:util", "stand-down × utilisation (+1 h × +0.01)", 0.01),
    ("standoff:util", "standoff × utilisation (+1 km × +0.01)", 0.01),
    ("mech_pooled_greedy", "pooled greedy vs in-house", 1.0),
    ("mech_central_assign", "batched assignment vs in-house", 1.0),
    ("mech_marketplace", "marketplace vs in-house", 1.0),
]


def _load_fit(res, response="log_delay_prio1_mean_h"):
    """{subset: {'coef': {term: (c, lo, hi)}, 'n', 'n_seeds', 'r2', 'dropped'}} from E20_fit.json, else table_E20.csv."""
    jpath, tpath = os.path.join(res, "E20_fit.json"), os.path.join(res, "table_E20.csv")
    fits, meta = {}, {}
    if os.path.exists(jpath):
        with open(jpath, encoding="utf-8") as f:
            doc = json.load(f)
        meta = {"inputs": doc.get("inputs", {}), "n_boot": doc.get("design", {}).get("n_boot", fl.N_BOOT)}
        pooled = doc.get("pooled", {}).get(response)
        if pooled:
            fits["pooled"] = {"coef": {t: (v["coef"], v["ci95"][0], v["ci95"][1]) for t, v in pooled["coef"].items()},
                              "n": pooled.get("n"), "n_seeds": pooled.get("n_seeds"), "r2": pooled.get("r2"), "dropped": pooled.get("dropped_constant", [])}
        for m, d in doc.get("by_mechanism", {}).items():
            r = d.get(response)
            if r:
                fits[m] = {"coef": {t: (v["coef"], v["ci95"][0], v["ci95"][1]) for t, v in r["coef"].items()},
                           "n": r.get("n"), "n_seeds": r.get("n_seeds"), "r2": r.get("r2"), "dropped": r.get("dropped_constant", [])}
    elif os.path.exists(tpath):
        t = pd.read_csv(tpath)
        t = t[t["response"] == response]
        for subset, g in t.groupby("subset"):
            fits[subset] = {"coef": {r.term: (r.coef, r.ci_lo, r.ci_hi) for r in g.itertuples()}, "n": int(g["n"].iloc[0]),
                            "n_seeds": int(g["n_seeds"].iloc[0]), "r2": float(g["r2"].iloc[0]),
                            "dropped": [tm for tm, *_ in TERM_DISPLAY if tm not in set(g["term"]) and not tm.startswith("mech_")]}
        meta = {"inputs": {}, "n_boot": fl.N_BOOT}
    else:
        raise Skip(f"neither E20_fit.json nor table_E20.csv in {res}")
    if "pooled" not in fits:
        raise Skip(f"no pooled fit of {response} in the E20 outputs")
    return fits, meta


def _pct(c, scale):
    return 100.0 * (math.exp(scale * c) - 1.0)


def fig27_law(res=RES, out=FIG, response="log_delay_prio1_mean_h", **_):
    fits, meta = _load_fit(res, response)
    pooled = fits["pooled"]
    mechs = [m for m in MECH_ORDER if m in fits] + sorted(set(fits) - set(MECH_ORDER) - {"pooled"})
    terms_a = [(t, lab, s) for t, lab, s in TERM_DISPLAY if t in pooled["coef"] or t in pooled.get("dropped", [])]
    terms_b = [(t, lab, s) for t, lab, s in terms_a if not t.startswith("mech_")]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 0.27 * len(terms_a) + 1.9), gridspec_kw={"width_ratios": [1.0, 1.0]}, sharey=False)
    fig.subplots_adjust(wspace=0.08, bottom=0.2, left=0.27, right=0.99)
    # panel A: pooled
    ax = axes[0]
    ya = np.arange(len(terms_a))
    xa = []
    for i, (t, lab, s) in enumerate(terms_a):
        if t not in pooled["coef"]:
            ax.text(0, i, "constant in the data", fontsize=6.5, color=MUTED, va="center", ha="left")
            continue
        c, lo, hi = pooled["coef"][t]
        pc, plo, phi = _pct(c, s), _pct(lo, s), _pct(hi, s)
        xa += [plo, phi]
        sig = plo > 0 or phi < 0
        ax.errorbar(pc, i, xerr=[[pc - plo], [phi - pc]], fmt="o", color=TOL["blue"], ms=4.5, mfc=TOL["blue"] if sig else "white", mew=1.1,
                    lw=1.1, capsize=2)
        ax.text(phi, i, f"  {pc:+.1f} % [{plo:+.1f}, {phi:+.1f}]", fontsize=5.8, color=INK2, va="center", ha="left")
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_yticks(ya)
    ax.set_yticklabels([lab for _, lab, _ in terms_a], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("change in mean urgent delay (%)", fontsize=8)
    if xa:
        lo_, hi_ = min(xa), max(xa)
        ax.set_xlim(lo_ - 0.08 * (hi_ - lo_), hi_ + 1.0 * (hi_ - lo_))
    ax.tick_params(labelsize=7)
    r2 = pooled.get("r2")
    ax.set_title(f"A. Pooled fit (n = {pooled.get('n'):,} years, {pooled.get('n_seeds')} seeds, R² = {r2:.2f})" if r2 is not None
                 else "A. Pooled fit", fontsize=8.5)
    # panel B: per mechanism
    ax = axes[1]
    yb = np.arange(len(terms_b))
    k = max(len(mechs), 1)
    xb = []
    for j, m in enumerate(mechs):
        f = fits[m]
        off = (j - (k - 1) / 2) * (0.7 / k)
        for i, (t, lab, s) in enumerate(terms_b):
            if t not in f["coef"]:
                ax.plot(0, i + off, "x", color=mech_color(m, j), ms=3.5, mew=0.8, alpha=0.6)
                continue
            c, lo, hi = f["coef"][t]
            pc, plo, phi = _pct(c, s), _pct(lo, s), _pct(hi, s)
            xb += [plo, phi]
            sig = plo > 0 or phi < 0
            ax.errorbar(pc, i + off, xerr=[[pc - plo], [phi - pc]], fmt="o", color=mech_color(m, j), ms=3.3, mfc=mech_color(m, j) if sig else "white",
                        mew=0.9, lw=0.9, capsize=1.5)
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_yticks(yb)
    ax.set_yticklabels([])
    ax.set_ylim(len(terms_b) - 0.5, -0.5)
    ax.set_xlabel("change in mean urgent delay (%)", fontsize=8)
    ax.tick_params(labelsize=7)
    if xb:
        lo_, hi_ = np.nanpercentile(xb, 1), np.nanpercentile(xb, 99)
        pad = 0.1 * (hi_ - lo_) if hi_ > lo_ else 1.0
        ax.set_xlim(lo_ - pad, hi_ + pad)
    handles = [Line2D([0], [0], marker="o", color=mech_color(m, j), ls="none", ms=4,
                      label=f"{mech_label(m)} (n = {fits[m].get('n'):,}, R² = {fits[m].get('r2'):.2f})" if fits[m].get("r2") is not None else mech_label(m))
               for j, m in enumerate(mechs)]
    handles.append(Line2D([0], [0], marker="x", color=INK2, ls="none", ms=3.5, label="term constant in that subset (dropped)"))
    ax.legend(handles=handles, fontsize=6.3, loc="lower right")
    ax.set_title("B. Per-mechanism fits (no mechanism dummies)", fontsize=8.5)
    paths = save(fig, "fig27_law", out)
    inputs = meta.get("inputs", {})
    ntxt = f"n = {pooled.get('n'):,} simulated years from {pooled.get('n_seeds')} seeds" if pooled.get("n") else "n unknown"
    caption = (f"The dispersion / standoff / keep-out law: OLS of ln(mean urgent-item delay) on ln(mean |miss|), pad standoff, keep-out "
               f"radius, stand-down time, the reference-cell utilisation, night share, off-pad share, pad radius, their interactions and "
               f"mechanism dummies (in-house is the base), pooled over the E17 and E18 years ({ntxt}; "
               f"pooled R² = {r2:.2f}). Coefficients are shown as the % change in mean urgent delay per the stated unit "
               f"(100·(exp(b·unit) − 1)); whiskers are percentile seed-bootstrap 95 % CIs ({meta.get('n_boot', fl.N_BOOT)} resamples, "
               f"seeds drawn with replacement, every year of a drawn seed weighted by its multiplicity); filled markers exclude 0, "
               f"open ones do not. Panel B repeats the fit within each mechanism (crosses: term constant in that subset). Flags: the fit is "
               f"Modelled on simulated years; regressor levels Measured / Spec (miss anchors) and Assumed (standoff, keep-out, stand-down sweeps). "
               f"Suites with fewer seeds enter fewer bootstrap resamples; a CI is only as good as the seeds behind the term.")
    return {"caption": caption, "n": ntxt, "ci": "percentile seed-bootstrap 95 % CI (fit_law.fit_ols)", "flags": "Modelled fit; Measured/Spec/Assumed levels",
            "files": paths, "inputs": {k: (os.path.basename(v) if isinstance(v, str) else v) for k, v in inputs.items()}}


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
FIGURES = [("fig20_lander_mc", fig20_lander_mc), ("fig21_driving_validation", fig21_driving_validation),
           ("fig22_dispersion_standoff", fig22_dispersion_standoff), ("fig23_standoff", fig23_standoff), ("fig24_plume", fig24_plume),
           ("fig25_autonomy_fleet", fig25_autonomy_fleet), ("fig26_siting", fig26_siting), ("fig27_law", fig27_law)]
FIG_IDS = [fid for fid, _ in FIGURES]


def select(only):
    """Figure ids matching 'fig22', '22' or the full id; None / empty -> all."""
    if not only:
        return list(FIG_IDS)
    chosen = []
    for o in only:
        o = str(o).strip().lower()
        hits = [fid for fid in FIG_IDS if fid == o or fid.split("_")[0] == o or fid.split("_")[0] == f"fig{o}"]
        if not hits:
            raise SystemExit(f"unknown figure {o!r}; choose from {FIG_IDS}")
        chosen += [h for h in hits if h not in chosen]
    return chosen


def build(only=None, res=RES, out=FIG, policies=POLICIES, captions_name=CAPTIONS_FILE):
    """Build the selected figures; write <out>/<captions_name> with every figure id (entries of unselected figures are kept)."""
    os.makedirs(out, exist_ok=True)
    cpath = os.path.join(out, captions_name)
    caps = {}
    if os.path.exists(cpath):
        try:
            with open(cpath, encoding="utf-8") as f:
                caps = json.load(f)
        except (OSError, ValueError):
            caps = {}
    chosen = select(only)
    for fid, fn in FIGURES:
        if fid not in chosen:
            caps.setdefault(fid, {"status": "not built in this run", "caption": ""})
            continue
        try:
            info = fn(res=res, out=out, policies=policies)
            info = dict(info)
            info["status"] = "produced"
            info["files"] = [os.path.basename(p) for p in info.get("files", [])]
            caps[fid] = info
        except Skip as e:
            print(f"skip {fid}: {e}")
            caps[fid] = {"status": "skipped", "reason": str(e), "caption": f"Not built: {e}"}
            stale = [f"{fid}.{ext}" for ext in ("png", "pdf") if os.path.exists(os.path.join(out, f"{fid}.{ext}"))]
            if stale:
                print(f"  note: {', '.join(stale)} on disk are from an earlier build and were left untouched")
                caps[fid]["stale_files"] = stale
        except Exception as e:  # noqa: BLE001  one broken figure must not stop the others
            print(f"FAILED {fid}: {e!r}")
            traceback.print_exc()
            plt.close("all")
            caps[fid] = {"status": "failed", "error": repr(e), "caption": f"Build failed: {e!r}"}
    caps = {fid: caps[fid] for fid in FIG_IDS if fid in caps} | {k: v for k, v in caps.items() if k not in FIG_IDS}
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump(caps, f, indent=1, ensure_ascii=False)
    print(f"captions -> {cpath}")
    return caps


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--only", nargs="*", default=None, help="figure ids to build, e.g. fig22 fig27 (default: all)")
    p.add_argument("--results", default=RES)
    p.add_argument("--out", default=FIG)
    p.add_argument("--policies", default=POLICIES)
    a = p.parse_args(argv)
    caps = build(a.only, res=a.results, out=a.out, policies=a.policies)
    produced = [k for k, v in caps.items() if v.get("status") == "produced"]
    skipped = [k for k, v in caps.items() if v.get("status") == "skipped"]
    failed = [k for k, v in caps.items() if v.get("status") == "failed"]
    print(f"produced {len(produced)}: {produced}")
    if skipped:
        print(f"skipped {len(skipped)}: {skipped}")
    if failed:
        print(f"failed {len(failed)}: {failed}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
