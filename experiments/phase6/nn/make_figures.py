"""E56 figures -> figures/phase6/ (matplotlib; run after evaluate and landscape).

    python experiments/phase6/nn/make_figures.py

Reads results/E56_integrity.json, .cache/nn/eval_arrays.npz, .cache/nn/landscape_final_s0/all.npz and the training
histories in .cache/nn/final_s*/done.json. Colours: one fixed colour per detector (a palette checked for the common
colour-vision deficiencies, with a line style as the second cue); surfaces use one blue ramp, light = low loss.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402

from lunarsim.nn import baselines as B  # noqa: E402
from lunarsim.nn import dataset as D  # noqa: E402
from lunarsim.nn import evaluate as E  # noqa: E402
from lunarsim.nn import faults as F  # noqa: E402
from lunarsim.nn import train as T  # noqa: E402

OUT = os.path.join(ROOT, "figures", "phase6")
COL = {"net": "#2a78d6", "chi2_step": "#eb6834", "cusum": "#1baf7a", "logreg": "#eda100", "chi2_window": "#e87ba4"}
STYLE = {"net": "-", "chi2_step": "--", "cusum": "-.", "logreg": ":", "chi2_window": (0, (5, 1, 1, 1, 1, 1))}
INK, MUTED, GRID, PATH = "#0b0b0b", "#52514e", "#e1e0d9", "#eb6834"
RAMP = LinearSegmentedColormap.from_list("blue", ["#eef4fd", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
TITLE = {"jump": "jump (5 to 50 m)", "drift": "slow drift (0.01 to 0.5 m/s)", "frozen": "frozen report",
         "frame": "frame error (300 to 1,000 m)", "noise": "noise inflation (x3 to x10)"}
plt.rcParams.update({"font.size": 9, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK, "xtick.color": MUTED,
                     "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6, "figure.dpi": 150,
                     "savefig.bbox": "tight", "legend.frameon": False, "axes.titlesize": 9.5,
                     "axes.titleweight": "bold", "axes.titlelocation": "left"})


def save(fig, name: str) -> None:
    os.makedirs(OUT, exist_ok=True)
    fig.savefig(os.path.join(OUT, name + ".png"), dpi=200)
    fig.savefig(os.path.join(OUT, name + ".pdf"))
    plt.close(fig)
    print("wrote", name)


def landscape(L) -> None:
    xs, ys, Zv, Zt, xy, ep = L["xs"], L["ys"], L["Zv"], L["Zt"], L["xy"], L["ep"]
    ev = L["explained"]
    whole = np.flatnonzero((ep == np.round(ep)) & (ep > 0))
    lab = [f"PCA direction 1 ({100 * ev[0]:.1f} % of the path's variance)",
           f"PCA direction 2 ({100 * ev[1]:.1f} %)"]
    # 3D surface with the path on it
    fig = plt.figure(figsize=(7.2, 5.6))
    ax = fig.add_subplot(111, projection="3d", computed_zorder=False)
    Xg, Yg = np.meshgrid(xs, ys)
    lz = np.log10(Zv)
    ax.plot_surface(Xg, Yg, lz, cmap=RAMP, linewidth=0, antialiased=True, alpha=0.92, rstride=1, cstride=1,
                    zorder=1)
    pz = np.log10(L["pv"])
    ax.plot(xy[:, 0], xy[:, 1], pz + 0.02, color=PATH, lw=2.0, zorder=10)
    ax.scatter(xy[whole, 0], xy[whole, 1], pz[whole] + 0.02, color=PATH, s=16, depthshade=False, zorder=11,
               edgecolor="#ffffff", linewidth=0.5)
    ax.scatter([xy[0, 0]], [xy[0, 1]], [pz[0] + 0.02], color=INK, s=26, depthshade=False, zorder=12)
    ax.text(xy[0, 0], xy[0, 1], pz[0] + 0.1, "start", color=INK, zorder=20)
    ax.text(0.3, 0, pz[-1] + 0.1, "final model", color=INK, zorder=20)
    ax.set_xlabel(lab[0], labelpad=8)
    ax.set_ylabel(lab[1], labelpad=8)
    ax.set_zlabel("log10 of the validation loss", labelpad=6)
    ax.set_title("Validation loss in the PCA plane, with the training path (dots: epochs)")
    ax.view_init(elev=38, azim=-64)
    save(fig, "fig_E56_landscape_3d")
    # contours: validation and training
    fig, axes = plt.subplots(1, 2, figsize=(10.4, 4.5), sharey=True)
    for ax, Z, name, rec in ((axes[0], Zv, "validation", L["rec_v"]), (axes[1], Zt, "training", L["rec_t"])):
        lev = np.geomspace(max(Z.min(), 1e-3), Z.max(), 16)
        cf = ax.contourf(xs, ys, Z, levels=lev, cmap=RAMP, norm=LogNorm(lev[0], lev[-1]))
        ax.contour(xs, ys, Z, levels=lev, colors="#ffffff", linewidths=0.35, alpha=0.7)
        ax.plot(xy[:, 0], xy[:, 1], color=PATH, lw=1.8)
        ax.scatter(xy[whole, 0], xy[whole, 1], color=PATH, s=16, zorder=5, edgecolor="#ffffff", linewidth=0.6)
        for k in whole:
            if int(ep[k]) in (1, 2, 4, 8, int(ep[-1])):
                ax.annotate(f"{int(ep[k])}", (xy[k, 0], xy[k, 1]), textcoords="offset points", xytext=(4, 5),
                            color=INK, fontsize=8)
        ax.scatter([xy[0, 0]], [xy[0, 1]], color=INK, s=22, zorder=6)
        ax.annotate("start", (xy[0, 0], xy[0, 1]), textcoords="offset points", xytext=(5, -11), color=INK)
        ax.set_title(f"{name} loss ({rec[0]:.2f} at the start, {rec[-1]:.3f} at the final model)")
        ax.set_xlabel(lab[0])
        ax.grid(False)
        cb = fig.colorbar(cf, ax=ax, shrink=0.9, pad=0.02)
        cb.set_label("class-balanced cross-entropy")
        cb.set_ticks([t for t in (0.05, 0.1, 0.2, 0.3, 0.5, 0.7, 1, 2, 3, 5, 10) if lev[0] <= t <= lev[-1]])
        cb.ax.set_yticklabels([f"{t:g}" for t in cb.get_ticks()])
    axes[0].set_ylabel(lab[1])
    fig.suptitle("Loss in the PCA plane of the training path; numbers on the path are epochs", x=0.01, ha="left",
                 fontsize=10, fontweight="bold")
    save(fig, "fig_E56_landscape_contour")
    # random filter-normalised slice
    fig, ax = plt.subplots(figsize=(5.2, 4.4))
    Zr, rs = L["Zr"], L["rs"]
    lev = np.geomspace(Zr.min(), Zr.max(), 16)
    cf = ax.contourf(rs, rs, Zr, levels=lev, cmap=RAMP, norm=LogNorm(lev[0], lev[-1]))
    ax.contour(rs, rs, Zr, levels=lev, colors="#ffffff", linewidths=0.35, alpha=0.7)
    ax.scatter([0], [0], color=PATH, s=24, zorder=5)
    ax.annotate("final model", (0, 0), textcoords="offset points", xytext=(6, 6), color=INK)
    ax.set_xlabel("random direction 1 (filter-normalised; 1 = the size of the weights)")
    ax.set_ylabel("random direction 2 (filter-normalised)")
    ax.set_title("Validation loss on a random slice through the final weights")
    ax.grid(False)
    cb = fig.colorbar(cf, ax=ax, shrink=0.9, pad=0.02)
    cb.set_label("class-balanced cross-entropy")
    cb.set_ticks([t for t in (0.1, 0.2, 0.3, 0.5, 0.7, 1, 2, 3, 5, 10, 20, 50) if lev[0] <= t <= lev[-1]])
    cb.ax.set_yticklabels([f"{t:g}" for t in cb.get_ticks()])
    save(fig, "fig_E56_landscape_random")
    # 1D interpolation
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    ax.plot(L["alpha"], L["iv"], color=COL["net"], lw=2, label="validation subset")
    ax.plot(L["alpha"], L["it"], color=COL["chi2_step"], lw=2, ls="--", label="training subset")
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.axvline(1, color=MUTED, lw=0.8)
    ax.text(0.01, ax.get_ylim()[1], " initial weights", va="top", color=MUTED, fontsize=8)
    ax.text(1.01, ax.get_ylim()[1], " final weights", va="top", color=MUTED, fontsize=8)
    ax.set_yscale("log")
    ax.set_xlabel("position on the straight line from the initial (0) to the final (1) weights")
    ax.set_ylabel("class-balanced cross-entropy")
    ax.set_title("Loss along the straight line from start to finish")
    ax.legend()
    save(fig, "fig_E56_interpolation")


def curves() -> None:
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    for s in E.FINAL_SEEDS:
        h = json.load(open(os.path.join(T.STATE, E.final_name(s), "done.json"), encoding="utf-8"))["hist"]
        e = [q["epoch"] for q in h]
        ax.plot(e, [q["train_loss"] for q in h], color=COL["chi2_step"], lw=1.2, ls="--", alpha=0.8,
                label="training (mean over the epoch's batches)" if s == 0 else None)
        ax.plot(e, [q["val_loss"] for q in h], color=COL["net"], lw=1.4, alpha=0.8,
                label="validation (all fault streams, after the epoch)" if s == 0 else None)
    ax.set_xlabel("epoch")
    ax.set_ylabel("class-balanced cross-entropy")
    ax.set_title("Training and validation loss, five seeds")
    ax.legend()
    save(fig, "fig_E56_curves")


def delays(A, res, sname: str, rate: str = "day") -> None:
    kinds = A[f"{sname}__kinds"]
    dets = ("chi2_step", "cusum", "logreg", "net")
    fig, axes = plt.subplots(1, 5, figsize=(13.5, 3.2), sharey=True)
    t = np.arange(0, 601)
    for ax, (k, name) in zip(axes, enumerate(F.FAULT_TYPES, 1)):
        sel = kinds == k
        for det in dets:
            d = A[f"{sname}__delay__{det}__{rate}"][:, sel]                  # [S, n], nan = missed
            share = np.mean([(np.nan_to_num(d[s], nan=1e9)[None, :] <= t[:, None]).mean(1) for s in range(len(d))],
                            axis=0)
            ax.plot(t, share, color=COL[det], ls=STYLE[det], lw=2, label=E.LABEL[det])
        ax.set_title(TITLE[name] if sname == "test" else name)
        ax.set_xscale("symlog", linthresh=10)
        ax.set_xlim(0, 600)
        ax.set_xticks([0, 5, 10, 30, 100, 400])
        ax.set_xticklabels(["0", "5", "10", "30", "100", "400"])
        ax.set_ylim(0, 1.02)
        ax.set_xlabel("seconds since the fault began")
    axes[0].set_ylabel("share of faults found by then")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="upper right", ncol=4, fontsize=8, bbox_to_anchor=(0.99, 1.07))
    fas = [res[sname][d][rate]["fa_per_pair_day"]["mean"] for d in dets]
    what = "Test set" if sname == "test" else "Out-of-distribution set, same thresholds"
    fig.suptitle(f"{what}: share of faults found against time, thresholds set for 1 false alarm per pair-{rate} on "
                 f"validation" + chr(10) + f"(realised false alarms {min(fas):.1f} to {max(fas):.0f} per pair-day; a curve ends at "
                 f"the detector's recall)", x=0.01, y=1.1, ha="left", fontsize=10, fontweight="bold")
    save(fig, f"fig_E56_delay_{sname}")


def roc(A, res) -> None:
    fig, ax = plt.subplots(figsize=(5.4, 4.0))
    for det in E.DETECTORS:
        auc = res["test"][det]["window_auc"]["all"]["roc_auc"]
        ax.plot(A[f"test__roc_fpr__{det}"], A[f"test__roc_tpr__{det}"], color=COL[det], ls=STYLE[det], lw=2,
                label=f"{E.LABEL[det]} (AUC {auc:.3f})")
    ax.set_xscale("log")
    ax.set_xlim(1e-4, 1)
    ax.set_ylim(0, 1.01)
    ax.set_xlabel("false-positive rate per scored step (log scale)")
    ax.set_ylabel("true-positive rate per scored step")
    ax.set_title("Window-level ROC on the test fault streams")
    ax.legend(loc="upper left", fontsize=7.5)
    save(fig, "fig_E56_roc")


def recall_bars(res) -> None:
    """Recall per fault type at the validation thresholds for 1 false alarm per pair-day, test and OOD."""
    dets = ("chi2_step", "cusum", "logreg", "net")
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), sharey=True)
    for ax, sname, ttl in ((axes[0], "test", "Test set"), (axes[1], "ood", "Out of distribution, same thresholds")):
        names = list(F.FAULT_TYPES)
        fas = []
        for j, det in enumerate(dets):
            e = res[sname][det]["day"]["events"]
            fas.append(res[sname][det]["day"]["fa_per_pair_day"]["mean"])
            m = np.array([e[n]["recall"]["mean"] for n in names])
            lo = np.array([e[n]["recall"]["ci95"][0] for n in names])
            hi = np.array([e[n]["recall"]["ci95"][1] for n in names])
            x = np.arange(len(names)) + (j - 1.5) * 0.2
            ax.bar(x, m, width=0.17, color=COL[det], label=E.LABEL[det] if sname == "test" else None,
                   edgecolor="#fcfcfb", linewidth=0.8)
            ax.errorbar(x, m, yerr=[m - lo, hi - m], fmt="none", ecolor=INK, elinewidth=0.8, capsize=1.5)
        ax.set_xticks(np.arange(len(names)))
        ax.set_xticklabels(names)
        ax.set_ylim(0, 1.05)
        ax.set_title(f"{ttl} (realised false alarms: {min(fas):.1f} to {max(fas):.0f} per pair-day)")
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("share of faults found")
    fig.legend(loc="upper center", ncol=4, fontsize=8, bbox_to_anchor=(0.5, 1.0))
    fig.suptitle("Event recall at the thresholds set for 1 false alarm per pair-day on validation "
                 "(bars: 95 % interval over events)", x=0.01, y=1.08, ha="left", fontsize=10, fontweight="bold")
    save(fig, "fig_E56_recall")


if __name__ == "__main__":
    res = json.load(open(E.RESULT, encoding="utf-8"))
    with np.load(E.EVAL_CACHE) as z:
        A = {k: z[k] for k in z.files}
    lpath = os.path.join(T.STATE, "landscape_final_s0", "all.npz")
    if os.path.isfile(lpath):
        with np.load(lpath) as z:
            landscape({k: z[k] for k in z.files})
    curves()
    delays(A, res, "test")
    delays(A, res, "ood")
    roc(A, res)
    recall_bars(res)
