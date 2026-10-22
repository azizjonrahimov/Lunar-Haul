"""Figures for the R-1 paper ("What Earth's Horizon Costs a Lunar Base"), from the E21 results and the Earth-link data.

    python paper/r1/make_figures_r1.py          -> figures/r1_fig1_map.png ... r1_fig5_operators.png

Inputs (all committed): data/terrain/connecting_ridge/{hillshade_20m.png, sites.json}, data/driving/routes-v1.json,
data/comms/connecting_ridge/earth_link-v1.json, results/table_E21.csv, results/fig_E21_delay_coverage.csv,
results/table_E21_breakeven_delay.csv, results/fig_E21_operator_demand.csv. Style as experiments/phase3/make_figures_phase3.py.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import LineCollection  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from lunarsim.comms import EarthLink  # noqa: E402
from lunarsim.rover.routes import decode_geom  # noqa: E402

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
MIXES = [("teleop_4s", "Teleoperated (4 s)", TOL["red"], "o"), ("default", "Phase-2 mix", TOL["yellow"], "s"),
         ("supervised_strict", "Supervised, strict", TOL["blue"], "D"),
         ("supervised_strategic", "Supervised, strategic", TOL["cyan"], "^"),
         ("supervised_strategic+avoid", "Supervised, strategic + avoid", TOL["purple"], "v"),
         ("autonomous", "Autonomous", TOL["green"], "P")]


def coverage(df):
    return np.where(df["comms"] == "dte", 0.0, np.where(df["comms"] == "always", np.nan, df["coverage"]))


def fig1_map():
    """Earth-link fraction of every route at 1 km pad standoff (DTE, any part of the disc), on the LOLA hillshade."""
    sites = json.load(open(os.path.join(ROOT, "data/terrain/connecting_ridge/sites.json"), encoding="utf-8"))
    routes = json.load(open(os.path.join(ROOT, "data/driving/routes-v1.json"), encoding="utf-8"))
    el = EarthLink.load(os.path.join(ROOT, "data/comms/connecting_ridge/earth_link-v1.json"))
    pts = {s["id"]: s["xy_m"] for s in sites["sites"]}
    pts.update({k: v for k, v in sites["pads"]["1"].items()})
    shade = np.asarray(Image.open(os.path.join(ROOT, "data/terrain/connecting_ridge/hillshade_20m.png")).convert("L"))
    xs = [p[0] for p in pts.values()]; ys = [p[1] for p in pts.values()]
    x0, x1, y0, y1 = min(xs) - 700, max(xs) + 700, min(ys) - 700, max(ys) + 700
    fig, ax = plt.subplots(figsize=(6.6, 5.6))
    ax.imshow(shade, cmap="gray", extent=(0, 16000, 0, 16000), origin="upper", vmin=0, vmax=255, alpha=0.9)
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
        xy = np.column_stack([g["x"], g["y"]])
        segs.append(xy); vals.append(frac)
    lc = LineCollection(segs, array=np.asarray(vals), cmap="viridis", norm=plt.Normalize(0, 0.6), linewidths=2.2)
    ax.add_collection(lc)
    cb = fig.colorbar(lc, ax=ax, fraction=0.04, pad=0.02)
    cb.set_label("share of 2028–2031 with Earth in view along the whole route")
    for sid, (x, y) in pts.items():
        key = sid if sid in el.points() else f"{sid}@1"
        f = el.summary(key)["fraction"] if key in el.points() else np.nan
        ax.plot(x, y, "o", ms=6, mec="white", mfc=INK, mew=1.0, zorder=5)
        ax.annotate(f"{sid}  {f:.0%}", (x, y), xytext=(6, 5), textcoords="offset points", fontsize=8, color="white",
                    bbox=dict(boxstyle="round,pad=0.15", fc="#000000aa", ec="none"), zorder=6)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.set_aspect("equal"); ax.grid(False)
    ax.set_xlabel("x east (m, tile frame)"); ax.set_ylabel("y north (m, grid)")
    ax.set_title("Earth in view at the sites and along the routes (direct links, pads at 1 km)")
    out = os.path.join(FIG, "r1_fig1_map.png"); fig.savefig(out); plt.close(fig); return out


def fig2_throughput():
    t = pd.read_csv(os.path.join(RES, "table_E21.csv")); a = t[t["stage"] == "A"].copy(); a["p"] = coverage(a)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for mix, label, col, mk in MIXES:
        s = a[(a["mix"] == mix) & a["p"].notna()].sort_values("p")
        ax.errorbar(s["p"], s["delivered_t_in_year"], yerr=s["delivered_t_in_year_ci95"], color=col, marker=mk, ms=4,
                    lw=1.2, capsize=2, label=label)
    al = a[(a["comms"] == "always") & (a["mix"] == "supervised_strict")]["delivered_t_in_year"].mean()
    ax.axhline(al, color=MUTED, lw=0.8, ls="--"); ax.text(0.62, al - 16, "Earth always in view", ha="center", fontsize=8, color=MUTED)
    ax.set_xlabel("relay coverage (0 = direct-to-Earth links only)"); ax.set_ylabel("cargo delivered in the year (t)")
    ax.set_title("Throughput: lost without a relay, restored by any relay or by autonomy")
    ax.legend(ncol=2, loc="lower right")
    out = os.path.join(FIG, "r1_fig2_throughput.png"); fig.savefig(out); plt.close(fig); return out


def fig3_delay():
    d = pd.read_csv(os.path.join(RES, "fig_E21_delay_coverage.csv"))
    d = d[d["metric"] == "delay_prio1_p90_h"]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for mix, label, col, mk in MIXES:
        c = d[(d["mix"] == mix) & (d["kind"] == "cell")].sort_values("p")
        if c.empty:
            continue
        lo = np.maximum(c["mean"] - c["ci95"], 1.0)
        eb = ax.errorbar(c["p"], c["mean"], yerr=[c["mean"] - lo, c["ci95"]], color=col, marker=mk, ms=4, lw=0,
                         elinewidth=0.8, capsize=1.5, label=label)
        for part in eb[1:]:
            for artist in (part if isinstance(part, tuple) else [part]):
                artist.set_alpha(0.35)
        f = d[(d["mix"] == mix) & (d["kind"] != "cell")].sort_values("p")
        if not f.empty:
            ax.plot(f["p"], f["fit"], color=col, lw=1.0, alpha=0.8)
    ax.set_yscale("log"); ax.set_xlabel("relay coverage (0 = direct-to-Earth links only)")
    ax.set_ylabel("urgent cargo: 90 % delivered within (h)")
    ax.set_title("Urgent delay against relay coverage (points: cells ± 95 % CI; lines: fitted laws)")
    ax.legend(ncol=3, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.2))
    out = os.path.join(FIG, "r1_fig3_delay.png"); fig.savefig(out); plt.close(fig); return out


def fig4_breakeven():
    b = pd.read_csv(os.path.join(RES, "table_E21_breakeven_delay.csv"))
    rows = [("strict, as is", b["base_value"].iloc[0], np.nan, np.nan, None)]
    for _, r in b.iterrows():
        rows.append((r["option"], r["value"], r["value_ci95_lo"], r["value_ci95_hi"], r["p_equiv"]))
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    y = np.arange(len(rows))[::-1]
    for yi, (lab, v, lo, hi, pe) in zip(y, rows):
        col = TOL["cyan"] if "strategic" in lab else (TOL["blue"] if "rover" in lab else MUTED)
        ax.barh(yi, v, color=col, height=0.6)
        if np.isfinite(lo):
            ax.errorbar(v, yi, xerr=[[v - lo], [hi - v]], color=INK2, capsize=2, lw=0.9)
        txt = f"{v:.0f} h" + (f"  ≈ coverage {pe:.2f}" if pe is not None and np.isfinite(pe) else "")
        ax.text(max(v, hi if np.isfinite(hi) else v) + 1, yi, txt, va="center", fontsize=8, color=INK2)
    ax.set_yticks(y); ax.set_yticklabels([r[0] for r in rows]); ax.set_xlabel("urgent cargo: 90 % delivered within (h), relay coverage 0.5")
    ax.set_title("What an extra rover and an autonomy step are worth, in relay coverage")
    ax.set_xlim(0, max(r[1] for r in rows) * 1.6)
    out = os.path.join(FIG, "r1_fig4_breakeven.png"); fig.savefig(out); plt.close(fig); return out


def fig5_operators():
    o = pd.read_csv(os.path.join(RES, "fig_E21_operator_demand.csv"))
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    for mix, label, col, mk in MIXES[:2]:
        s = o[o["mix"] == mix].copy()
        s["x"] = np.where(s["comms"] == "always", 1.1, np.where(s["comms"] == "dte", 0.0, s["p"]))
        s = s.sort_values("x")
        ax.errorbar(s["x"], s["peak_to_mean"], yerr=s["peak_to_mean_ci95"], color=col, marker=mk, ms=4, lw=1.2, capsize=2, label=label)
    ax.set_xticks([0, 0.2, 0.4, 0.6, 0.8, 1.0, 1.1]); ax.set_xticklabels(["DTE", "0.2", "0.4", "0.6", "0.8", "1.0", "always"])
    ax.set_xlabel("relay coverage"); ax.set_ylabel("peak / mean operator demand")
    ax.set_title("Weak links bunch operator demand into the link-up windows")
    ax.legend()
    out = os.path.join(FIG, "r1_fig5_operators.png"); fig.savefig(out); plt.close(fig); return out


if __name__ == "__main__":
    os.makedirs(FIG, exist_ok=True)
    for f in (fig1_map, fig2_throughput, fig3_delay, fig4_breakeven, fig5_operators):
        try:
            print("wrote", f())
        except Exception as e:  # report and go on, so one broken input does not hide the others
            print("FAILED", f.__name__, type(e).__name__, e)
