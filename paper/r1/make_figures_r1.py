"""Figures for the R-1 paper ("What Earth's Horizon Costs a Lunar Base"), round 2 (referee W11), from the E21 results
and the Earth-link data.

    python paper/r1/make_figures_r1.py [--results results] [--out figures]   -> r1_fig1_map.png ... r1_fig6_years.png

Inputs: data/terrain/connecting_ridge/{height_20m.png, meta.json, sites.json}, data/driving/routes-v1.json,
data/comms/connecting_ridge/earth_link-v1.json, and from --results the round-2 replications results/E21{a,b,a2}_*_r2.csv
with results/table_E21_breakeven_delay_r2.csv and results/fig_E21_operator_demand_r2.csv (experiments/phase4/
analyse_e21.py fit --round r2). While a round-2 file is missing the round-1 file is used, with a printed warning and a
small "round-1 data" note on the figure. Style as experiments/phase3/make_figures_phase3.py.

Changes for round 2 (referee W11, S5, E12, O6, M3):
  Fig. 1  elevation shading instead of the hillshade (its cast shadows hid half the map); a thin dark outline under each
          route; the title says which direction of a leg is drawn.
  Fig. 2  throughput split into lander cargo and bulk regolith (two panels), Earth-always reference lines.
  Fig. 3  censored urgent p90 (hollow where under 90 % of urgent items were delivered: a lower bound), geometric means
          with t intervals computed on log values, markers offset per fleet, no fitted laws.
  Fig. 4  paired differences against the strict fleet at relay coverage 0.5, with t intervals, and the equivalent
          coverage of each option with its bootstrap interval.
  Fig. 5  absolute peak of linked operator demand against coverage, the staffing line, the hard-limit (A2) cells, the
          seeds over staff; no "always" point.
  Fig. 6  new: the two primary comparisons per start year (the 2028 calendar effect).
"""
import argparse
import json
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from PIL import Image  # noqa: E402
from scipy import stats  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from lunarsim.comms import EarthLink  # noqa: E402
from lunarsim.rover.routes import decode_geom  # noqa: E402
from experiments.phase4 import analyse_e21 as AN  # noqa: E402

RES, FIG = os.path.join(ROOT, "results"), os.path.join(ROOT, "figures")
TOL = {"blue": "#4477AA", "cyan": "#66CCEE", "green": "#228833", "yellow": "#CCBB44", "red": "#EE6677",
       "purple": "#AA3377", "grey": "#BBBBBB"}
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "STIXGeneral", "DejaVu Serif"], "mathtext.fontset": "stix",
    "font.size": 10, "axes.titlesize": 10.5, "axes.labelsize": 10, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False, "legend.fontsize": 8,
    "figure.dpi": 150, "savefig.dpi": 200, "savefig.bbox": "tight", "savefig.facecolor": "white",
})
MIXES = [("teleop_4s", "Teleoperated (4 s)", TOL["red"], "o"), ("default", "Reference mix", TOL["yellow"], "s"),
         ("supervised_strict", "Supervised, strict", TOL["blue"], "D"),
         ("supervised_strategic", "Supervised, strategic", TOL["cyan"], "^"),
         ("supervised_strategic+avoid", "Supervised, strategic with look-ahead", TOL["purple"], "v"),
         ("autonomous", "Autonomous", TOL["green"], "P")]
STAGE_FILES = {"A": "E21a_comms_autonomy", "B": "E21b_breakeven", "A2": "E21a2_operators"}
USED = {}                                     # what each figure read: "r2", or "r1" (round 2 not there yet)


def _read(results, base):
    p2, p1 = os.path.join(results, f"{base}_r2.csv"), os.path.join(results, f"{base}.csv")
    if os.path.exists(p2):
        return pd.read_csv(p2), "r2"
    if os.path.exists(p1):
        print(f"WARNING: {base}_r2.csv missing in {results}; using round 1 ({base}.csv)")
        return pd.read_csv(p1), "r1"
    return None, None


def stage(results, name):
    """Rows of one E21 stage (round 2 if present), prepared as analyse_e21 does, with the derived tonnage columns."""
    df, rnd = _read(results, STAGE_FILES[name])
    if df is None:
        return None, None
    df = AN.prepare(df)
    for k in ("bulk", "landed"):
        if f"delivered_{k}_kg_in_horizon" in df:
            df[f"delivered_{k}_t"] = df[f"delivered_{k}_kg_in_horizon"] / 1000.0
    return df, rnd


def _note(fig, rnd):
    if rnd != "r2":
        fig.text(0.995, 0.995, "round-1 data (round 2 incomplete)", ha="right", va="top", fontsize=7, color=TOL["red"])


def _tmean(v):
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if not len(v):
        return np.nan, np.nan
    h = stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / math.sqrt(len(v)) if len(v) > 1 else np.nan
    return float(v.mean()), float(h)


def _gmean(v):
    """Geometric mean and its t interval computed on log values (referee W11: no bars below zero on a log axis)."""
    v = np.asarray(v, float)
    v = np.log(np.maximum(v[np.isfinite(v)], 1e-3))
    if not len(v):
        return np.nan, np.nan, np.nan
    h = stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / math.sqrt(len(v)) if len(v) > 1 else 0.0
    return float(np.exp(v.mean())), float(np.exp(v.mean() - h)), float(np.exp(v.mean() + h))


def _save(fig, out, name, rnd="r2"):
    _note(fig, rnd)
    p = os.path.join(out, name)
    fig.savefig(p)
    plt.close(fig)
    USED[name] = rnd
    return p


# ---------------------------------------------------------------------------------------------------------
def fig1_map(results, out):
    """Earth-link fraction of every route at 1 km pad standoff (DTE, any part of the disc), on LOLA elevation."""
    meta = json.load(open(os.path.join(ROOT, "data/terrain/connecting_ridge/meta.json"), encoding="utf-8"))
    sites = json.load(open(os.path.join(ROOT, "data/terrain/connecting_ridge/sites.json"), encoding="utf-8"))
    routes = json.load(open(os.path.join(ROOT, "data/driving/routes-v1.json"), encoding="utf-8"))
    el = EarthLink.load(os.path.join(ROOT, "data/comms/connecting_ridge/earth_link-v1.json"))
    pts = {s["id"]: s["xy_m"] for s in sites["sites"]}
    pts.update({k: v for k, v in sites["pads"]["1"].items()})
    enc = meta["z_encoding"]
    z = enc["offset_m"] + enc["scale_m_per_unit"] * np.asarray(Image.open(
        os.path.join(ROOT, "data/terrain/connecting_ridge", meta["layers"]["height_20m"]["file"])), dtype=np.float64)
    W, H = meta["size_m"]
    xs = [p[0] for p in pts.values()]; ys = [p[1] for p in pts.values()]
    x0, x1, y0, y1 = min(xs) - 700, max(xs) + 700, min(ys) - 700, max(ys) + 700
    # elevation range of the shown window, so the shading uses the full light-grey ramp there
    r0, r1 = int((H - y1) / 20), int((H - y0) / 20)
    c0, c1 = int(x0 / 20), int(x1 / 20)
    win = z[max(r0, 0):r1, max(c0, 0):c1]
    fig, ax = plt.subplots(figsize=(6.6, 5.6))
    im = ax.imshow(z, cmap="Greys_r", extent=(0, W, 0, H), origin="upper",
                   vmin=np.percentile(win, 1) - 0.3 * np.ptp(win), vmax=np.percentile(win, 99.5))
    segs, vals = [], []
    for key, by_light in routes["legs"].items():
        a, b = key.split("->")
        if ("@" in a and not a.endswith("@1")) or ("@" in b and not b.endswith("@1")):
            continue
        if a > b and f"{b}->{a}" in routes["legs"]:
            continue                                                          # draw each pair once (A->B)
        g = decode_geom(routes["geoms"][by_light["night"]["geom"]])
        try:
            frac = el.summary(key)["fraction"]
        except KeyError:
            continue
        segs.append(np.column_stack([g["x"], g["y"]])); vals.append(frac)
    ax.add_collection(LineCollection(segs, colors=INK, linewidths=2.9, alpha=0.8, zorder=3))       # thin dark outline
    lc = LineCollection(segs, array=np.asarray(vals), cmap="viridis", norm=plt.Normalize(0, 0.6), linewidths=1.9, zorder=4)
    ax.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("share of 2028–2031 with Earth in view along the whole route")
    for sid, (x, y) in pts.items():
        key = sid if sid in el.points() else f"{sid}@1"
        f = el.summary(key)["fraction"] if key in el.points() else np.nan
        ax.plot(x, y, "o", ms=6, mec="white", mfc=INK, mew=1.0, zorder=5)
        off = {"POWER": (8, -13), "BASE": (8, -13)}.get(sid, (6, 5))           # keep neighbouring labels apart
        ax.annotate(f"{sid}  {f:.0%}", (x, y), xytext=off, textcoords="offset points", fontsize=8, color="white",
                    bbox=dict(boxstyle="round,pad=0.15", fc="#000000aa", ec="none"), zorder=6)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.grid(False)
    ax.set_xlabel("x east (m, tile frame)"); ax.set_ylabel("y north (m, grid)")
    ax.set_title("Earth in view at the sites and along the routes (direct links, pads at 1 km)\n"
                 "each leg drawn once (its night route, from the alphabetically first end)", fontsize=9.5)
    cbz = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.12, location="bottom", aspect=40)
    cbz.set_label("elevation (m, LOLA 5 m, shown at 20 m)")
    return _save(fig, out, "r1_fig1_map.png")


def fig2_throughput(results, out):
    a, rnd = stage(results, "A")
    a = a[a["stage"] == "A"]
    split = "delivered_landed_t" in a
    if not split:
        print("WARNING: no bulk / landed columns (round-1 data); landed cargo shown as delivered_nonbulk_kg (booked at "
              "pickup), bulk as the rest of the year's deliveries")
        a = a.assign(delivered_landed_t=a["delivered_nonbulk_kg"] / 1000.0)
        a = a.assign(delivered_bulk_t=a["delivered_t_in_year"] - a["delivered_landed_t"])
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.4))
    for ax, col_name, title in ((axes[0], "delivered_landed_t", "Lander cargo"),
                                (axes[1], "delivered_bulk_t", "Bulk regolith (incl. 200 t/yr to ISRU)")):
        for i, (mix, label, col, mk) in enumerate(MIXES):
            g = a[(a["mix"] == mix) & a["p"].notna()]
            ps = sorted(g["p"].unique())
            m = [_tmean(g[np.isclose(g["p"], p)][col_name]) for p in ps]
            eb = ax.errorbar(np.array(ps) + (i - 2.5) * 0.008, [x[0] for x in m], yerr=[x[1] for x in m], color=col,
                             marker=mk, ms=3.5, lw=1.0, elinewidth=0.7, capsize=0, label=label)
            for part in eb[2]:
                part.set_alpha(0.3)                                        # intervals faint: the seed spread is wide
        ref = a[(a["comms"] == "always") & (a["mix"] == "supervised_strict")][col_name].mean()
        ax.axhline(ref, color=MUTED, lw=0.8, ls="--")
        ax.text(0.98, ref, "Earth always in view", ha="right", va="bottom", fontsize=7.5, color=MUTED,
                transform=ax.get_yaxis_transform())
        ax.set_title(title); ax.set_xlabel("relay coverage (0 = direct links only)")
    axes[0].set_ylabel("delivered inside the year (t), mean ± 95 % t interval")
    axes[0].legend(fontsize=7, loc="lower right")
    fig.suptitle("Throughput by cargo class: what direct links lose, and what any relay or autonomy restores", fontsize=10.5)
    return _save(fig, out, "r1_fig2_throughput.png", rnd if split else "r1")


def fig3_delay(results, out):
    a, rnd = stage(results, "A")
    a = a[(a["stage"] == "A") & a["p"].notna()]
    cens = "delay_prio1_p90_censored_h" in a
    metric = "delay_prio1_p90_censored_h" if cens else "delay_prio1_p90_h"
    if not cens:
        print("WARNING: no censored p90 (round-1 data); plotting the uncensored urgent p90")
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    for i, (mix, label, col, mk) in enumerate(MIXES):
        g = a[a["mix"] == mix]
        if g.empty:
            continue
        ps = sorted(g["p"].unique())
        gm = [_gmean(g[np.isclose(g["p"], p)][metric]) for p in ps]
        comp = [g[np.isclose(g["p"], p)]["prio1_completion_share"].mean() if "prio1_completion_share" in g else 1.0
                for p in ps]
        x = np.array(ps) + (i - 2.5) * 0.009
        y = np.array([v[0] for v in gm])
        ax.errorbar(x, y, yerr=[y - np.array([v[1] for v in gm]), np.array([v[2] for v in gm]) - y], color=col, lw=0,
                    elinewidth=0.8, capsize=1.5, alpha=0.6)
        full = np.array([c >= 0.9 for c in comp])
        ax.plot(x[full], y[full], mk, color=col, ms=4.5, label=label)
        ax.plot(x[~full], y[~full], mk, mfc="white", mec=col, ms=4.5)
    ax.plot([], [], "o", mfc="white", mec=INK2, ms=4.5, label="under 90 % delivered: lower bound")
    ax.set_yscale("log"); ax.set_xlabel("relay coverage (0 = direct links only)")
    ax.set_ylabel("urgent cargo: 90 % delivered within (h)" + ("\n(undelivered items censored at the year's end)" if cens else ""))
    ax.set_title("Urgent delay against relay coverage (geometric mean over seeds, 95 % t interval on log values)")
    ax.legend(ncol=3, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    return _save(fig, out, "r1_fig3_delay.png", rnd if cens else "r1")


def fig4_breakeven(results, out):
    a, rnd = stage(results, "A")
    b = a[a["stage"] == "B"] if "B" in set(a["stage"]) else None
    bdf, rnd_b = stage(results, "B")
    b = bdf
    be, rnd_be = _read(results, "table_E21_breakeven_delay")
    opts = [("+1 rover", "strict", 1), ("+2 rovers", "strict", 2), ("+3 rovers", "strict", 3),
            ("strategic step", "strategic", 0), ("strategic with look-ahead", "strategic+avoid", 0),
            ("strategic step + 1 rover", "strategic", 1)]
    base = AN.select(b, p=0.5, policy="strict", extra_rovers=0, mast="none")
    strict_curve = a[(a["stage"] == "A") & a["p"].notna() & (a["mix"] == "supervised_strict")]
    P = sorted(strict_curve["p"].unique())
    M = [strict_curve[np.isclose(strict_curve["p"], p)]["delay_prio1_p90_h"].mean() for p in P]
    fig, ax = plt.subplots(figsize=(6.6, 3.3))
    rows = []
    for lab, pol, n in opts:
        cell = AN.select(b, p=0.5, policy=pol, extra_rovers=n, mast="none")
        if cell.empty:
            continue
        r = AN.paired(base, cell, "delay_prio1_p90_h")
        pe = None
        if be is not None and lab in set(be["option"]):
            row = be[be["option"] == lab].iloc[0]
            pe = (row["p_equiv"], row.get("p_equiv_ci95_lo"), row.get("p_equiv_ci95_hi"))
        elif lab == "strategic with look-ahead":
            pe = (AN.mono_inverse(P, M, float(cell["delay_prio1_p90_h"].mean())), None, None)
        rows.append((lab, r, pe))
    y = np.arange(len(rows))[::-1]
    for yi, (lab, r, pe) in zip(y, rows):
        col = TOL["purple"] if "look-ahead" in lab else (TOL["cyan"] if "strategic" in lab else TOL["blue"])
        ax.errorbar(r["diff"], yi, xerr=[[r["diff"] - r["ci_lo"]], [r["ci_hi"] - r["diff"]]], fmt="o", color=col,
                    capsize=2.5, ms=5)
        fmtp = lambda v: "beyond 1" if v is None or (isinstance(v, float) and (math.isinf(v) or math.isnan(v))) else f"{v:.2f}"
        if pe is not None:
            txt = f"≈ coverage {fmtp(pe[0])}" + (f" [{fmtp(pe[1])}, {fmtp(pe[2])}]" if pe[1] is not None else " (point)")
            ax.text(1.02, yi, txt, va="center", fontsize=7.5, color=INK2, transform=ax.get_yaxis_transform())
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows])
    ax.set_xlabel(f"change in urgent p90 vs the strict fleet at relay 0.5 (h; base {base['delay_prio1_p90_h'].mean():.0f} h), "
                  "paired, 95 % t interval")
    ax.set_title("What an extra rover and an autonomy step buy at relay coverage 0.5, and the coverage each equals",
                 fontsize=9.5)
    return _save(fig, out, "r1_fig4_breakeven.png", "r2" if (rnd_b == "r2" and rnd_be == "r2") else "r1")


def fig5_operators(results, out):
    o, rnd = _read(results, "fig_E21_operator_demand")
    has_a2 = "operators" in o and (o["operators"] == "strict").any()
    if "operators" not in o:
        o = o.assign(operators="lenient")
    if not has_a2:
        print("WARNING: operator table without the strict (A2) cells")
        rnd = "r1"
    o = o[o["comms"] != "always"].copy()                                  # referee E12: not comparable
    o["x"] = np.where(o["comms"] == "dte", 0.0, o["p"])
    fig, ax = plt.subplots(figsize=(6.6, 3.4))
    for mix, label, col, mk in MIXES[:2]:
        for rule, mfc, ls in (("lenient", col, "-"), ("strict", "white", ":")):
            s = o[(o["mix"] == mix) & (o["operators"] == rule)].sort_values("x")
            if s.empty:
                continue
            ax.errorbar(s["x"], s["peak_mean"], yerr=s["peak_ci95"], color=col, marker=mk, mfc=mfc, ms=4.5, lw=1.1, ls=ls,
                        capsize=2, label=f"{label}, {'hard operator limit' if rule == 'strict' else 'soft pool'}")
            if rule == "lenient":
                for _, r in s.iterrows():
                    if r["seeds_over_staffing"] > 0:
                        ax.annotate(f"{int(r['seeds_over_staffing'])}/{int(r['n_seeds'])}", (r["x"], r["peak_mean"] + r["peak_ci95"]),
                                    xytext=(0, 3), textcoords="offset points", ha="center", fontsize=6.5, color=col)
    staff = float(o["n_operators"].iloc[0]) if len(o) else 3.0
    ax.axhline(staff, color=INK2, lw=0.9, ls="--")
    ax.text(1.0, staff, f"  {staff:.0f} operators on duty", va="bottom", ha="right", fontsize=7.5, color=INK2,
            transform=ax.get_yaxis_transform())
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0]); ax.set_xticklabels(["DTE", "0.2", "0.4", "0.6", "0.8", "1.0"])
    ax.set_xlabel("relay coverage"); ax.set_ylabel("peak linked operator demand\n(largest hourly mean; mean ± 95 % t)")
    ax.set_title("Operator demand peaks in the link windows (numbers: seeds above the staff)", fontsize=10)
    ax.legend(fontsize=7, ncol=2, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    return _save(fig, out, "r1_fig5_operators.png", rnd)


def fig6_years(results, out):
    a, rnd = stage(results, "A")
    a = a[a["stage"] == "A"]
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.2))
    years = sorted(a["start_year"].unique())
    for k, (mix, label, col, mk) in enumerate([MIXES[2], MIXES[3]]):
        ref = AN.select(a, comms="always", mix=mix).set_index("seed")
        cel = AN.select(a, p=0.0, mix=mix).set_index("seed")
        d = (cel["delivered_t_in_year"] - ref["delivered_t_in_year"]).dropna()
        yr = ref.loc[d.index, "start_year"]
        m = [_tmean(d[yr == y]) for y in years]
        axes[0].errorbar(np.array(years) + (k - 0.5) * 0.12, [x[0] for x in m], yerr=[x[1] for x in m], fmt=mk, color=col,
                         capsize=2.5, ms=5, label=label)
    axes[0].axhline(0, color=MUTED, lw=0.8)
    axes[0].set_title("Direct links vs Earth always: cargo (t)", fontsize=9.5)
    axes[0].set_ylabel("paired difference per start year\n(mean of 5 seeds ± 95 % t)")
    axes[0].legend(fontsize=7, loc="lower right")
    ref = AN.select(a, p=0.1, mix="supervised_strict").set_index("seed")
    cel = AN.select(a, p=0.1, mix="supervised_strategic").set_index("seed")
    metric = "delay_prio1_p90_censored_h" if "delay_prio1_p90_censored_h" in a else "delay_prio1_p90_h"
    lr = np.log(np.maximum(cel[metric], 1e-3) / np.maximum(ref[metric], 1e-3)).dropna()
    yr = ref.loc[lr.index, "start_year"]
    for y in years:
        v = lr[yr == y].to_numpy()
        h = stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / math.sqrt(len(v)) if len(v) > 1 else 0.0
        axes[1].errorbar([y], [math.exp(v.mean())], yerr=[[math.exp(v.mean()) - math.exp(v.mean() - h)],
                                                          [math.exp(v.mean() + h) - math.exp(v.mean())]],
                         fmt="^", color=TOL["cyan"], capsize=2.5, ms=5)
    axes[1].axhline(1, color=MUTED, lw=0.8)
    axes[1].set_yscale("log")
    axes[1].set_title("Strategic vs strict at relay 0.1: urgent p90 ratio", fontsize=9.5)
    axes[1].set_ylabel("geometric-mean ratio (log scale)")
    for ax in axes:
        ax.set_xticks(years); ax.set_xlabel("start year")
    fig.suptitle("The calendar matters: the primary comparisons by start year (strategic fleet under direct links, 2028)",
                 fontsize=10)
    return _save(fig, out, "r1_fig6_years.png", rnd)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--results", default=RES)
    ap.add_argument("--out", default=FIG)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    for f in (fig1_map, fig2_throughput, fig3_delay, fig4_breakeven, fig5_operators, fig6_years):
        try:
            print("wrote", f(a.results, a.out))
        except Exception as e:  # report and go on, so one broken input does not hide the others
            print("FAILED", f.__name__, type(e).__name__, e)
    stale = sorted(k for k, v in USED.items() if v != "r2")
    if stale:
        print("NOTE: round-1 data in", ", ".join(stale))


if __name__ == "__main__":
    main()
