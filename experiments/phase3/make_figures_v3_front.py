"""The three front figures of the v3 paper (paper/v3/part3_methods.html): terrain and sites (Figure 1), the descent
environment (Figure 3) and the driving environment (Figure 4).

    python experiments/phase3/make_figures_v3_front.py                 # all three
    python experiments/phase3/make_figures_v3_front.py --only fig03    # one ('fig01', '1', 'v3_fig03_descent' ...)
    python experiments/phase3/make_figures_v3_front.py --seed 100001   # Figure 3 episode seed (default: the first
                                                                       # evaluation seed on which both controllers landed)

Writes figures/v3_fig01_terrain, v3_fig03_descent, v3_fig04_rover (.png at 200 dpi and .pdf, <= 7 in wide) and
figures/v3_front_captions.json {id: {id, file, caption, status, notes}} with the paper's captions verbatim and
notes on what the data could not support. Style (fonts, palette, sizes, flags) is that of make_figures_phase3.py.
Single process, float32 grids, no multiprocessing (a training run shares the machine); the Terrain pack is loaded
once and the 5 m height grid is block-averaged to 10 m for the shaded relief.
"""
import argparse
import json
import math
import os
import sys
import time
import traceback

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle, Circle  # noqa: E402

from experiments.phase3.make_figures_phase3 import (TOL, BATLOW, GREYS, INK, INK2, MUTED, GRID, Skip, save,  # noqa: E402
                                                    ordered_colors, wilson)

FIG = os.path.join(ROOT, "figures")
POLICIES = os.path.join(ROOT, "data", "policies")
CAPTIONS_FILE = "v3_front_captions.json"
SITE = "connecting_ridge"
BATLOW_CMAP = LinearSegmentedColormap.from_list("batlow10", BATLOW)
KIND_MARKER = {"base": ("o", TOL["blue"]), "depot": ("D", TOL["blue"]), "power": ("^", TOL["green"]), "construction": ("P", TOL["purple"]),
               "isru": ("h", TOL["cyan"]), "science": ("*", TOL["purple"]), "psr": ("X", INK), "pad": ("s", TOL["yellow"])}
FAIL_MARKER = {"velocity": "x", "tilt": "^", "sensor": "s", "timeout": "+", "lost": "d"}

# The captions, verbatim from paper/v3/part3_methods.html (HTML entities resolved).
CAPTIONS = {
    "v3_fig01_terrain": ("The Connecting Ridge tile (LOLA 5 m, NASA/GSFC; Measured) with the nine sites and the five pad sets. Relief is "
                         "shaded for a sun at azimuth 0° and 1.5° elevation with cast shadows; the permanently shadowed site lies in "
                         "shadow at all four reference azimuths. Lines from each pad to the base are drawn solid where the terrain blocks "
                         "the line of sight and dashed where it is clear. Expert routes between sites at the 1 km standoff are overlaid in grey."),
    "v3_fig03_descent": ("The descent environment. A: altitude against downrange distance for the classical law (solid) and the DAgger "
                         "policy (dashed) on the same dispersed CLPS episode, with the SPLICE gate, the 30 m sensor-degradation line and "
                         "the 50 m delivery radius marked. B: the altimeter estimate against true altitude on the same episode, showing the "
                         "bias, noise and held values below 30 m. C: miss-distance scatter for 500 episodes of each controller, with failures "
                         "marked by kind. Numbers in the panels are Modelled; the gate and box are Spec."),
    "v3_fig04_rover": ("The driving environment. A: the expert's route from the base to the shadowed crater on the shaded relief for sun "
                       "azimuth 90°, with the driven trail of a 4 s teleoperated drive and its intervention points. B: the 32 × 32 "
                       "observation patch (relative height channel) at one step. C: speed made good against round-trip delay for the "
                       "environment (line) and the JSC measurements (points; Measured), with the supervised and autonomous caps. D: slip "
                       "against slope for the three friction-angle curves (Modelled) and the Yutu-2 in-situ points (Measured)."),
}
# Yutu-2 in-situ slip, research_notes/Lunar landing and rover autonomy logistics/rover_autonomy_driving.md ("Yutu-2 in situ [DEMO]:
# slip 10.5-19.7% on gentle slopes; sinkage ~10 mm"): a range without slope values, so it is drawn as a band, not as points.
YUTU2_SLIP = (0.105, 0.197)
YUTU2_SLOPE_SHOWN_DEG = (0.0, 10.0)      # "gentle slopes" has no number in the note; the band is drawn over 0-10 deg and says so
YUTU2_SOURCE = "Jilin Univ. paper / Nature Geoscience 2022 ESM / Remote Sensing 2023, via rover_autonomy_driving.md"

_TERRAIN = {}


def save_fixed(fig, name, out):
    """Save at the figure's own canvas (no tight bbox): the margins are set explicitly, so the PNG is exactly <= 7 in wide."""
    with plt.rc_context({"savefig.bbox": "standard"}):
        return save(fig, name, out)


def terrain(site=SITE):
    """One Terrain instance per site for the whole run (the 5 m grid is 80 MB)."""
    if site not in _TERRAIN:
        from lunarsim.terrain import Terrain
        _TERRAIN[site] = Terrain(site)
    return _TERRAIN[site]


def relief(t, sun_az_deg, px_out=10.0):
    """(Lambertian hillshade n.s without cast shadows, cast-shadow mask, pixel size), row 0 = south, float32, on the 5 m
    grid block-averaged to px_out metres."""
    from lunarsim.terrain import hillshade, cast_shadow, block_mean
    k = max(1, int(round(px_out / t.px5)))
    z = block_mean(t.z5, k).astype(np.float32) if k > 1 else t.z5.astype(np.float32)
    px = t.px5 * k
    north = z[::-1]
    hs = hillshade(north, px, sun_az_deg, 1.5, shadows=False)[::-1].astype(np.float32)
    sh = cast_shadow(north, px, sun_az_deg, 1.5)[::-1]
    return hs, sh, px


def km_extent(hs, px):
    return (0.0, hs.shape[1] * px / 1000.0, 0.0, hs.shape[0] * px / 1000.0)


SHADOW_ALPHA = 0.45


def show_relief(ax, hs, sh, px, pct=99.0):
    """Hillshade everywhere, stretched to its pct-th percentile (a 1.5 deg sun lights flat ground at n.s = 0.026), with the
    cast shadow overlaid as a dark layer of alpha SHADOW_ALPHA so the relief stays visible. Returns the stretch value."""
    vmax = float(np.percentile(hs, pct)) or 1.0
    ext = km_extent(hs, px)
    ax.imshow(np.clip(hs / max(vmax, 1e-6), 0.0, 1.0), cmap="gray", vmin=0.0, vmax=1.0, origin="lower", extent=ext, interpolation="bilinear")
    rgba = np.zeros(sh.shape + (4,), np.float32)
    rgba[..., 3] = np.where(sh, SHADOW_ALPHA, 0.0)
    ax.imshow(rgba, origin="lower", extent=ext, interpolation="nearest")
    return vmax


def label(ax, x, y, text, dx=5, dy=5, fontsize=7):
    """Dark text with a white halo, offset from the marker in points."""
    import matplotlib.patheffects as pe
    ax.annotate(text, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=fontsize, color=INK,
                path_effects=[pe.withStroke(linewidth=2.2, foreground="white")], zorder=8)


# ---------------------------------------------------------------------------
# Figure 1: terrain, sites, pads, lines of sight, expert routes
# ---------------------------------------------------------------------------
def plan_routes(t, nodes, sun_az_deg=0.0, log=print):
    """A* route for every ordered pair of nodes {name: (x, y)} on the 20 m cost grid, as rover.tables.legs_from_sites
    orders them. Returns {(a, b): polyline or None}."""
    from lunarsim.rover import expert
    cost = expert.cost_grid(t, sun_az_deg)
    out = {}
    names = list(nodes)
    t0 = time.time()
    n = 0
    for a in names:
        for b in names:
            if a == b:
                continue
            pa, pb = nodes[a], nodes[b]
            ja, ia = t.cell(pa[0], pa[1])
            jb, ib = t.cell(pb[0], pb[1])
            cells = expert.astar(cost, (int(ja), int(ia)), (int(jb), int(ib)), t.px20, sun_az_deg)
            if cells is None:
                out[(a, b)] = None
            else:
                pts = np.array([[(c + 0.5) * t.px20, (r + 0.5) * t.px20] for r, c in cells], dtype=np.float32)
                pts[0], pts[-1] = pa, pb
                out[(a, b)] = pts
            n += 1
            if n % 12 == 0:
                log(f"  routes {n}/{len(names) * (len(names) - 1)} ({time.time() - t0:.0f} s)")
    return out


def v3_fig01_terrain(out=FIG, site=SITE, sun_az_deg=0.0, route_standoff="1", margin_m=700.0, log=print, **_):
    t = terrain(site)
    S = t.sites()
    if not S:
        raise Skip(f"no sites.json in the {site} pack")
    sites = S["sites"]
    pads = S.get("pads") or {}
    base = tuple(S["base_xy_m"])
    standoffs = sorted(pads, key=float)
    hs, sh, px = relief(t, sun_az_deg)
    ext = km_extent(hs, px)
    # crop to the sites and pads
    xs = [s["xy_m"][0] for s in sites] + [xy[0] for D in pads.values() for xy in D.values()]
    ys = [s["xy_m"][1] for s in sites] + [xy[1] for D in pads.values() for xy in D.values()]
    x0, x1 = max(0.0, min(xs) - margin_m), min(t.size_m[0], max(xs) + margin_m)
    y0, y1 = max(0.0, min(ys) - margin_m), min(t.size_m[1], max(ys) + margin_m)
    # lines of sight pad -> base, computed here and compared with sites.json
    los = {}
    mismatch = []
    for D in standoffs:
        for pid, xy in pads[D].items():
            computed = bool(t.line_of_sight(xy, base))
            det = (S.get("pad_details") or {}).get(D, {}).get(pid, {})
            rec = det.get("los_to_base")
            clear = (rec == "clear") if rec in ("clear", "blocked") else computed     # the siting tables use sites.json
            los[(D, pid)] = clear
            if rec is not None and (rec == "clear") != computed:
                mismatch.append(f"{pid}@{D} km: sites.json {rec} (clearance {det.get('los_clearance_m')} m), Terrain.line_of_sight "
                                 f"{'clear' if computed else 'blocked'} (clearance {t.los_clearance_m(xy, base):.2f} m); drawn as sites.json")
    # routes between the sites and the pads of the chosen standoff
    nodes = {s["id"]: tuple(s["xy_m"]) for s in sites}
    for pid, xy in (pads.get(route_standoff) or {}).items():
        nodes[f"{pid}@{route_standoff}"] = tuple(xy)
    log(f"  planning {len(nodes) * (len(nodes) - 1)} expert routes (sun azimuth {sun_az_deg:g} deg) ...")
    routes = plan_routes(t, nodes, sun_az_deg, log=log)
    n_routes = sum(r is not None for r in routes.values())
    # PSR shadow status at the four reference azimuths (20 m ray-march, as the sites rule computes it)
    psr = [s for s in sites if s.get("kind") == "psr"]
    psr_status = {}
    for s in psr:
        psr_status[s["id"]] = {az: bool(t.shadowed(s["xy_m"][0], s["xy_m"][1], az)[0]) for az in (0, 90, 180, 270)}
    # draw
    import matplotlib.patheffects as pe
    fig, ax = plt.subplots(figsize=(7.0, 4.85))
    fig.subplots_adjust(left=0.08, right=0.665, top=0.975, bottom=0.1)     # legend and note live in the right third of the canvas
    ax.grid(False)
    stretch = show_relief(ax, hs, sh, px)
    for (a, b), r in routes.items():
        if r is not None:
            ax.plot(r[:, 0] / 1000, r[:, 1] / 1000, color="#d9d9d9", lw=0.55, alpha=0.75, zorder=2)
    pcol = dict(zip(standoffs, ordered_colors(len(standoffs), hi=7)))
    CLEAR = "white"
    for D in standoffs:
        for pid, xy in pads[D].items():
            clear = los[(D, pid)]
            if clear:       # white dashes on top of everything: distinct from the solid pad-coloured blocked lines
                ax.plot([xy[0] / 1000, base[0] / 1000], [xy[1] / 1000, base[1] / 1000], ls=(0, (4, 3)), color=CLEAR, lw=1.8, zorder=9,
                        path_effects=[pe.withStroke(linewidth=2.6, foreground=INK)])
            else:
                ax.plot([xy[0] / 1000, base[0] / 1000], [xy[1] / 1000, base[1] / 1000], ls="-", color=pcol[D], lw=0.9, zorder=3)
            ax.scatter(xy[0] / 1000, xy[1] / 1000, marker="s", s=34, color=pcol[D], edgecolor="white", linewidth=0.6, zorder=5)
            label(ax, xy[0] / 1000, xy[1] / 1000, f"{pid[-1]} {D}", 5, -9 if float(D) <= 1 else 3, fontsize=6)
    offsets = {"BASE": (9, -13), "CONSTR": (8, -10), "POWER": (-44, 2), "DEPOT": (-38, -13), "ISRU": (8, -11), "SCI_1": (8, 3), "PSR": (-30, 7)}
    for s in sites:
        m, col = KIND_MARKER.get(s.get("kind"), ("o", INK))
        ax.scatter(s["xy_m"][0] / 1000, s["xy_m"][1] / 1000, marker=m, s=60, color=col, edgecolor="white", linewidth=0.7, zorder=6)
        dx, dy = offsets.get(s["id"], (8, 3))
        label(ax, s["xy_m"][0] / 1000, s["xy_m"][1] / 1000, s["id"], dx, dy)
    ax.set_xlim(x0 / 1000, x1 / 1000)
    ax.set_ylim(y0 / 1000, y1 / 1000)
    ax.set_aspect("equal")
    ax.set_xlabel("local x (km), tile frame")
    ax.set_ylabel("local y (km)")
    # inset: whole tile with the crop box
    ins = ax.inset_axes([0.012, 0.012, 0.25, 0.25])
    hs20, sh20, _ = relief(t, sun_az_deg, px_out=40.0)
    show_relief(ins, hs20, sh20, 40.0)
    ins.add_patch(Rectangle((x0 / 1000, y0 / 1000), (x1 - x0) / 1000, (y1 - y0) / 1000, fill=False, ec=TOL["yellow"], lw=0.9))
    ins.set_xticks([])
    ins.set_yticks([])
    ins.grid(False)
    ins.set_title(f"{t.size_m[0] / 1000:g} km tile", fontsize=6, pad=2, color=INK2)
    # legend
    handles = [Line2D([0], [0], marker=KIND_MARKER[k][0], color=KIND_MARKER[k][1], ls="none", ms=6, mec="white", label=lab)
               for k, lab in (("base", "base"), ("depot", "depot"), ("power", "power"), ("construction", "construction"), ("isru", "ISRU"),
                              ("science", "science"), ("psr", "permanently shadowed site")) if any(s.get("kind") == k for s in sites)]
    handles += [Line2D([0], [0], marker="s", color=pcol[D], ls="none", ms=5, label=f"pads A/B at {D} km") for D in standoffs]
    handles += [Line2D([0], [0], color=INK2, lw=0.9, ls="-", label="pad to base, sight line blocked (solid)"),
                Line2D([0], [0], color=CLEAR, lw=1.8, ls=(0, (4, 3)), path_effects=[pe.withStroke(linewidth=2.6, foreground=INK)],
                       label="pad to base, sight line clear (dashed white)"),
                Line2D([0], [0], color="#bdbdbd", lw=0.8, label=f"expert routes, {route_standoff} km pads ({n_routes})")]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=6.5, frameon=False, handletextpad=0.6, borderaxespad=0.0)
    import textwrap
    txt = [f"Sun azimuth {sun_az_deg:g}°, elevation 1.5°; relief stretched to its 99th percentile (n·s = {stretch:.3f}); "
           f"cast shadows darkened (black, alpha {SHADOW_ALPHA:g})."]
    for sid, st in psr_status.items():
        txt.append(f"{sid} in cast shadow at azimuth 0/90/180/270°: " + "/".join("yes" if v else "no" for v in st.values()) + ".")
    txt.append("Sites and pads: Assumed layout on Measured terrain.")
    ax.text(1.01, 0.02, "\n".join(textwrap.fill(s, 34) for s in txt), transform=ax.transAxes, fontsize=6, color=INK2, va="bottom", ha="left")
    paths = save_fixed(fig, "v3_fig01_terrain", out)
    del hs, sh, hs20, sh20
    notes = [f"sites.json lists {len(sites)} sites (" + ", ".join(s["id"] for s in sites) + f") plus 2 pads per set; the caption's "
             f"'nine sites' holds only if the two pads of a set are counted as sites",
             f"routes planned with the sun at azimuth {sun_az_deg:g} deg (the relief's sun); {n_routes} of {len(routes)} ordered pairs routed",
             "PSR cast-shadow status computed with Terrain.shadowed (20 m ray-march, el 1.5 deg): " +
             "; ".join(f"{k}: {v}" for k, v in psr_status.items())]
    if mismatch:
        notes.append("line-of-sight disagreements with sites.json pad_details: " + "; ".join(mismatch))
    else:
        notes.append("line-of-sight status agrees with sites.json pad_details for every pad")
    return {"caption": CAPTIONS["v3_fig01_terrain"], "files": paths, "notes": notes, "psr_shadow": psr_status,
            "los_clear": {f"{pid}@{D}": v for (D, pid), v in los.items()}}


# ---------------------------------------------------------------------------
# Figure 3: the descent environment
# ---------------------------------------------------------------------------
def _rollout(env, controller, seed):
    """One episode; per step the true position, the altimeter estimate and the thrust. Returns dict of arrays + outcome."""
    from lunarsim.lander import physics as LP
    obs, _ = env.reset(seed=seed)
    rec = {"t": [0.0], "x": [env.state[LP.X]], "y": [env.state[LP.Y]], "z": [env.state[LP.Z]], "h_est": [env.last_est[0][2]],
           "thrust_n": [env.thrust_n]}
    done, info = False, {}
    while not done:
        obs, _, term, trunc, info = env.step(controller(obs, env))
        done = term or trunc
        rec["t"].append(env.steps * env.dt)
        rec["x"].append(env.state[LP.X])
        rec["y"].append(env.state[LP.Y])
        rec["z"].append(env.state[LP.Z])
        rec["h_est"].append(env.last_est[0][2])
        rec["thrust_n"].append(env.thrust_n)
    out = {k: np.asarray(v, np.float32) for k, v in rec.items()}
    out["outcome"] = info.get("outcome", {})
    out["alt_bias_low_m"] = float(env.alt_bias)
    out["noise_scale"] = float(env.noise)
    return out


def _pick_seed(cl, bc, seed0):
    both = cl.set_index("seed").join(bc.set_index("seed"), lsuffix="_cl", rsuffix="_bc", how="inner")
    ok = both[(both["ok_cl"] == 1) & (both["ok_bc"] == 1)]
    ok = ok[ok.index >= seed0]
    if ok.empty:
        raise Skip("no evaluation seed on which both controllers landed")
    return int(ok.index.min())


def v3_fig03_descent(out=FIG, policies=POLICIES, seed=None, policy_id="lander_CLPS_bc_v3_s0", cls="CLPS", log=print, **_):
    try:
        from lunarsim.lander.env import DescentEnv, obs_version_of, SENSOR
        from lunarsim.lander.classes import GATE, TOUCHDOWN
        from lunarsim.lander.evaluate import classical_action, EVAL_SEED0
        from lunarsim.lander.policy import MlpPolicy
    except ImportError as e:
        raise Skip(f"lunarsim.lander not importable (gymnasium?): {e!r}")
    cl_csv = os.path.join(policies, f"outcomes_classical_{cls}.csv")
    bc_csv = os.path.join(policies, f"outcomes_{policy_id}.csv")
    card = os.path.join(policies, f"{policy_id}.json")
    for p in (cl_csv, bc_csv, card):
        if not os.path.exists(p):
            raise Skip(f"{p} not found")
    cl, bc = pd.read_csv(cl_csv), pd.read_csv(bc_csv)
    if seed is None:
        seed = _pick_seed(cl, bc, EVAL_SEED0)
    pol = MlpPolicy.from_json(card)
    env_pol = DescentEnv(cls=cls, sensor=True, obs_version=obs_version_of(pol.doc["obs"]["names"]))
    env_cl = DescentEnv(cls=cls, sensor=True, obs_version=2)
    log(f"  rolling out seed {seed}: classical law and {policy_id}")
    r_cl = _rollout(env_cl, lambda o, e: classical_action(e), seed)
    r_bc = _rollout(env_pol, lambda o, e: pol.act(o), seed)
    low = SENSOR["low_alt_m"]
    R50 = TOUCHDOWN["delivery_radius_m"]
    miss = {}
    for name, r in (("classical", r_cl), ("policy", r_bc)):
        o = r["outcome"]
        miss[name] = {"miss_m": float(math.hypot(*o.get("miss_m", (np.nan, np.nan)))), "ok": bool(o.get("ok")), "failure_kind": o.get("failure_kind"),
                      "t_flight_s": float(o.get("t_flight_s", np.nan)), "prop_used_kg": float(o.get("prop_used_kg", np.nan)),
                      "same_as_table": None}
    for name, df in (("classical", cl), ("policy", bc)):
        row = df[df["seed"] == seed]
        if len(row):
            miss[name]["table_miss_m"] = float(row["miss_r_m"].iloc[0])
            miss[name]["same_as_table"] = bool(abs(row["miss_r_m"].iloc[0] - miss[name]["miss_m"]) < 1e-3)
    # figure: A (left) + B (right) on top; C (left) + [legend over D] (right) below
    fig = plt.figure(figsize=(7.0, 6.4))
    fig.subplots_adjust(left=0.09, right=0.975, top=0.92, bottom=0.08)
    gs = fig.add_gridspec(2, 2, width_ratios=[1.45, 1.0], height_ratios=[1.0, 1.2], hspace=0.5, wspace=0.3)
    col = {"classical": TOL["blue"], "policy": TOL["red"]}
    ls = {"classical": "-", "policy": "--"}
    lab = {"classical": "classical law (ZEM/ZEV + terminal phase)", "policy": "DAgger policy (bc v3)"}
    # A: altitude vs downrange
    ax = fig.add_subplot(gs[0, 0])
    for name, r in (("classical", r_cl), ("policy", r_bc)):
        dr = np.hypot(r["x"], r["y"])
        ax.plot(dr, r["z"], ls=ls[name], color=col[name], lw=1.5, label=lab[name])
        ax.plot(dr[-1], max(r["z"][-1], 0), "o", color=col[name], ms=4, mec="white")
    ax.plot(GATE["downrange_m"], GATE["altitude_m"], "D", color=INK, ms=5, zorder=5)
    ax.annotate(f"SPLICE gate (Spec)\n{GATE['downrange_m']:g} m downrange, {GATE['altitude_m']:g} m up,\n{GATE['vh_mps']:g} m/s, {GATE['vz_mps']:g} m/s",
                (GATE["downrange_m"], GATE["altitude_m"]), xytext=(-8, -4), textcoords="offset points", fontsize=6, ha="right", va="top", color=INK2)
    ax.axhline(low, color=MUTED, lw=0.8, ls=":")
    ax.text(5, low + 3, f"{low:g} m: altimeter degrades (Modelled)", fontsize=6, color=INK2, ha="left", va="bottom")
    ax.axvline(R50, color=TOL["yellow"], lw=0.9, ls="-.")
    ax.text(R50 + 3, 466, f"{R50:g} m delivery radius (Spec)", fontsize=6, color=INK2, ha="left", va="top")
    ax.set_xlim(-5, 310)
    ax.set_ylim(-5, 470)
    ax.set_xlabel("horizontal distance to the target (m)")
    ax.set_ylabel("altitude (m)")
    ax.set_title(f"A. Seed {seed}: altitude vs downrange", fontsize=8.5, pad=15)       # second title line below, at 8 pt
    ax.text(0.5, 1.012, "touchdown miss: " + ", ".join(f"{lab[n].split(' (')[0]} {miss[n]['miss_m']:.2f} m" for n in ("classical", "policy")) + " (Modelled)",
            transform=ax.transAxes, fontsize=8, color=INK2, ha="center", va="bottom")
    ax.legend(fontsize=6.2, loc="lower right", bbox_to_anchor=(1.0, 0.1))
    # A inset: the last 60 m (right, between the gate annotation above and the legend below)
    ins = ax.inset_axes([0.53, 0.3, 0.44, 0.33])
    for name, r in (("classical", r_cl), ("policy", r_bc)):
        dr = np.hypot(r["x"], r["y"])
        ins.plot(dr, r["z"], ls=ls[name], color=col[name], lw=1.2)
    ins.axhline(low, color=MUTED, lw=0.7, ls=":")
    ins.axvline(R50, color=TOL["yellow"], lw=0.7, ls="-.")
    ins.set_xlim(-1, 60)
    ins.set_ylim(-1, 45)
    ins.tick_params(labelsize=5.5, length=2)
    ins.set_title("last 60 m", fontsize=6, pad=2, loc="left")
    # B: altimeter estimate vs true altitude
    ax = fig.add_subplot(gs[0, 1])
    lim = 60.0
    ax.plot([0, lim], [0, lim], color=MUTED, lw=0.8)
    ax.axvline(low, color=MUTED, lw=0.8, ls=":")
    n_held = {}
    for name, r in (("classical", r_cl), ("policy", r_bc)):
        z, h = r["z"], r["h_est"]
        held = np.zeros(len(h), bool)
        held[1:] = (h[1:] == h[:-1]) & (z[1:] < low)
        n_held[name] = int(held.sum())
        sel = z <= lim
        ax.plot(z[sel], h[sel], ls=ls[name], color=col[name], lw=0.9, alpha=0.9)
        ax.scatter(z[sel & ~held], h[sel & ~held], s=6, color=col[name], edgecolor="none", alpha=0.7)
        ax.scatter(z[sel & held], h[sel & held], s=22, facecolor="none", edgecolor=col[name], lw=0.9, zorder=5, label=f"held reading ({lab[name].split(' (')[0]})")
    ax.set_xlim(0, lim)
    ax.set_ylim(0, lim)
    ax.set_xlabel("true altitude (m)")
    ax.set_ylabel("altimeter estimate (m)")
    ax.set_title("B. Altimeter estimate vs truth", fontsize=8.5)
    ax.text(0.03, 0.97, f"bias below {low:g} m: {r_cl['alt_bias_low_m']:+.2f} m (both; same seed)\nnoise scale ×{r_cl['noise_scale']:.2f}; "
            f"held values: {n_held['classical']} / {n_held['policy']} steps\n(Modelled sensor, dropout p = {SENSOR['alt_dropout_p']:g} per step)",
            transform=ax.transAxes, fontsize=6, va="top", color=INK2)
    ax.legend(fontsize=6, loc="lower right")
    # C: miss scatter (left); right: the legend over panel D
    sub = gs[1, 1].subgridspec(2, 1, height_ratios=[1.0, 1.0], hspace=0.15)
    ax = fig.add_subplot(gs[1, 0])
    th = np.linspace(0, 2 * np.pi, 200)
    ax.plot(R50 * np.cos(th), R50 * np.sin(th), "--", color=INK2, lw=0.9)
    ax.text(-R50 * 0.9, R50 * 0.9, f"{R50:g} m delivery\nradius (Spec)", fontsize=6.5, color=INK2, ha="left", va="top")
    hand = []
    for name, df in (("classical", cl), ("policy", bc)):
        okm = df["ok"].astype(int) == 1
        ax.scatter(df.loc[okm, "miss_x_m"], df.loc[okm, "miss_y_m"], s=7, color=col[name], alpha=0.55, edgecolor="none")
        hand.append(Line2D([0], [0], marker="o", color=col[name], ls="none", ms=4, label=f"{lab[name].split(' (')[0]}: landed in the box ({int(okm.sum())} of {len(df)})"))
        for kind, mk in FAIL_MARKER.items():
            sel = (~okm) & (df["failure_kind"] == kind)
            if sel.any():
                ax.scatter(df.loc[sel, "miss_x_m"], df.loc[sel, "miss_y_m"], s=22, marker=mk, color=col[name], lw=0.8,
                           facecolor="none" if mk in ("^", "s", "d") else col[name])
                hand.append(Line2D([0], [0], marker=mk, color=col[name], ls="none", ms=5, mfc="none" if mk in ("^", "s", "d") else col[name],
                                   label=f"{lab[name].split(' (')[0]}: {kind} ({int(sel.sum())})"))
    ax.set_xscale("symlog", linthresh=5.0, linscale=0.7)
    ax.set_yscale("symlog", linthresh=5.0, linscale=0.7)
    L = 150.0
    ax.set_xlim(-L, L)
    ax.set_ylim(-L, L)
    ax.set_aspect("equal")
    ticks = [-100, -10, 0, 10, 100]
    ax.set_xticks(ticks)
    ax.set_yticks(ticks)
    ax.set_xticklabels([f"{v:g}" for v in ticks], fontsize=7)
    ax.set_yticklabels([f"{v:g}" for v in ticks], fontsize=7)
    ax.set_xlabel("miss, east (m; symlog, linear within ±5 m)", fontsize=8)
    ax.set_ylabel("miss, north (m)", fontsize=8)
    ax.set_title(f"C. Touchdown miss, {len(cl)} + {len(bc)} episodes\n(evaluation seeds from {int(cl['seed'].min())})", fontsize=8.5)
    axl = fig.add_subplot(sub[0])
    axl.axis("off")
    axl.legend(handles=hand, fontsize=5.8, loc="upper left", bbox_to_anchor=(-0.08, 1.08), frameon=False, handletextpad=0.5, labelspacing=0.3)
    # D: touchdown state against the Spec box
    axd = fig.add_subplot(sub[1])
    for name, df in (("classical", cl), ("policy", bc)):
        axd.scatter(df["vh_td"].abs(), df["vz_td"].abs(), s=6, color=col[name], alpha=0.5, edgecolor="none")
    axd.add_patch(Rectangle((0, 0), TOUCHDOWN["vh_max_mps"], TOUCHDOWN["vz_max_mps"], fill=False, ec=INK, lw=1.1, zorder=5))
    axd.text(TOUCHDOWN["vh_max_mps"] + 0.08, TOUCHDOWN["vz_max_mps"] + 0.1, f"box: |v_h| ≤ {TOUCHDOWN['vh_max_mps']:g}, |v_z| ≤ {TOUCHDOWN['vz_max_mps']:g} m/s,\n"
             f"tilt ≤ {TOUCHDOWN['tilt_max_deg']:g}°, rate ≤ {TOUCHDOWN['rate_max_dps']:g}°/s (Spec)", fontsize=5.8, color=INK2, va="bottom")
    axd.set_xlim(0, 4)
    axd.set_ylim(0, 6)
    axd.set_xlabel("|v_h| at touchdown (m/s); axes clipped", fontsize=7)
    axd.set_ylabel("|v_z| at touchdown (m/s)", fontsize=7)
    axd.tick_params(labelsize=6.5)
    axd.set_title("D. Touchdown state (Spec box)", fontsize=8.5)
    paths = save_fixed(fig, "v3_fig03_descent", out)
    notes = [f"episode seed {seed} = the first evaluation seed (from {EVAL_SEED0}) on which both controllers landed in the box" if seed == _pick_seed(cl, bc, EVAL_SEED0)
             else f"episode seed {seed} (chosen by the caller)",
             "same seed: identical dispersed initial state, domain randomisation and per-episode sensor biases for both controllers; "
             "the per-step noise comes from the same stream and is identical while both are above 30 m, but the dropout (held-value) "
             "draws fall at different steps because the two trajectories enter the low-altitude regime at different times",
             "the 'touchdown box' is a velocity/tilt box, not a region of the miss plane; it is drawn as panel D (touchdown velocities), "
             "which the caption does not mention",
             f"policy evaluated with obs v{obs_version_of(pol.doc['obs']['names'])}, classical law with obs v2 (as in data/policies)",
             "miss on this seed: " + "; ".join(f"{n} {m['miss_m']:.2f} m ({'box' if m['ok'] else m['failure_kind']}; table {m.get('table_miss_m', float('nan')):.2f} m, "
                                               f"{'same' if m['same_as_table'] else 'DIFFERENT'})" for n, m in miss.items())]
    return {"caption": CAPTIONS["v3_fig03_descent"], "files": paths, "notes": notes, "seed": seed, "miss": miss}


# ---------------------------------------------------------------------------
# Figure 4: the driving environment
# ---------------------------------------------------------------------------
def _drive_teleop(t, route, rtt_s=4.0, sun_az_deg=90.0, phi=42.0, seed=0):
    """Drive the route with the pure-pursuit expert in lunar/Drive-v0 (teleop); trail, interventions, one observation."""
    from lunarsim.rover.env import DriveEnv
    from lunarsim.rover.expert import PurePursuit
    env = DriveEnv(t)
    obs, _ = env.reset(seed=seed, options={"waypoints": route, "autonomy": "teleop", "rtt_s": rtt_s, "sun_az_deg": sun_az_deg, "phi": phi})
    pp = PurePursuit(env.route)
    trail = [(env.state["x"], env.state["y"])]
    interventions = []
    best = (-1.0, None, None)        # (relief spread, patch, position) of the most informative step
    n_int = 0
    while True:
        cap = env._v_cap(env.state["x"], env.state["y"], env.state["psi"])
        prev = (env.state["x"], env.state["y"])
        obs, _, term, trunc, info = env.step(np.array(pp.action(env.state, cap), dtype=np.float32))
        trail.append((env.state["x"], env.state["y"]))
        if env.interventions > n_int:
            n_int = env.interventions
            interventions.append(prev)
        spread = float(np.std(obs["patch"][0]))
        if spread > best[0]:
            best = (spread, obs["patch"][0].copy(), (env.state["x"], env.state["y"], env.state["psi"]))
        if term or trunc:
            return np.asarray(trail, np.float32), np.asarray(interventions, np.float32), best, info["leg"]


def _smg_kmh(autonomy, rtt_s):
    """Flat-ground speed made good incl. stops, as the driving tables compute it (tests/test_rover.py)."""
    from lunarsim.rover import physics as R
    every, stop_s = R.stop_plan(autonomy, rtt_s)
    ground = R.speed_cap_mps(autonomy, rtt_s) * (1.0 - R.slip(0.0))
    t = 1000.0 / ground + (1000.0 / every * stop_s if np.isfinite(every) else 0.0)
    return 3.6 * 1000.0 / t


def v3_fig04_rover(out=FIG, site=SITE, sun_az_deg=90.0, rtt_s=4.0, phi=42.0, seed=0, log=print, **_):
    try:
        from lunarsim.rover import physics as R, expert
        from lunarsim.rover.env import PATCH, PATCH_BEHIND, PATCH_RES_M
    except ImportError as e:
        raise Skip(f"lunarsim.rover not importable: {e!r}")
    seed = 0 if seed is None else int(seed)          # the drive's env seed (build() passes the Figure 3 seed, None by default)
    t = terrain(site)
    S = t.sites()
    if not S:
        raise Skip(f"no sites.json in the {site} pack")
    pts = {s["id"]: tuple(s["xy_m"]) for s in S["sites"]}
    psr = [s["id"] for s in S["sites"] if s.get("kind") == "psr"]
    if "BASE" not in pts or not psr:
        raise Skip("sites.json has no BASE or no psr site")
    a, b = pts["BASE"], pts[psr[0]]
    log(f"  planning BASE -> {psr[0]} at sun azimuth {sun_az_deg:g} deg ...")
    route = expert.plan(t, a, b, sun_az_deg=sun_az_deg)
    if route is None:
        raise Skip(f"no expert route BASE -> {psr[0]} under the slope limit")
    log(f"  driving it (teleop {rtt_s:g} s, phi {phi:g}, seed {seed}) ...")
    trail, inter, (spread, patch, where), leg = _drive_teleop(t, route, rtt_s, sun_az_deg, phi, seed)
    hs, sh, px = relief(t, sun_az_deg)
    mx, my = 350.0, 1000.0
    x0, x1 = min(route[:, 0].min(), trail[:, 0].min()) - mx, max(route[:, 0].max(), trail[:, 0].max()) + mx
    y0, y1 = min(route[:, 1].min(), trail[:, 1].min()) - my, max(route[:, 1].max(), trail[:, 1].max()) + my
    fig = plt.figure(figsize=(7.0, 7.2))
    fig.subplots_adjust(left=0.09, right=0.925, top=0.95, bottom=0.12)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 1.0], width_ratios=[1.25, 1.0, 1.0], hspace=0.35, wspace=0.42)
    # A: route, trail, interventions
    ax = fig.add_subplot(gs[0, :2])
    ax.grid(False)
    show_relief(ax, hs, sh, px)
    ax.plot(route[:, 0] / 1000, route[:, 1] / 1000, color=TOL["cyan"], lw=1.6, label="expert route (A* on the 20 m cost grid)")
    ax.plot(trail[:, 0] / 1000, trail[:, 1] / 1000, color=TOL["red"], lw=0.8, ls="--", label=f"driven trail, teleop {rtt_s:g} s RTT")
    if len(inter):
        ax.scatter(inter[:, 0] / 1000, inter[:, 1] / 1000, marker="x", s=30, color=TOL["yellow"], lw=1.2, zorder=6, label=f"interventions ({len(inter)})")
    ax.scatter([a[0] / 1000, b[0] / 1000], [a[1] / 1000, b[1] / 1000], marker="o", s=40, color=[TOL["blue"], INK], edgecolor="white", zorder=7)
    label(ax, a[0] / 1000, a[1] / 1000, "BASE", 6, 4)
    label(ax, b[0] / 1000, b[1] / 1000, psr[0], 6, 4)
    if where is not None:
        ax.scatter(where[0] / 1000, where[1] / 1000, marker="s", s=70, facecolor="none", edgecolor=TOL["yellow"], lw=1.2, zorder=6, label="observation of panel B")
    ax.set_xlim(x0 / 1000, x1 / 1000)
    ax.set_ylim(y0 / 1000, y1 / 1000)
    ax.set_aspect("equal")
    ax.set_xlabel("local x (km)")
    ax.set_ylabel("local y (km)")
    ax.set_title(f"A. BASE → {psr[0]}, sun azimuth {sun_az_deg:g}°: {leg['distance_m'] / 1000:.2f} km driven in {leg['time_s'] / 3600:.2f} h, "
                 f"{leg['energy_wh'] / 1000:.2f} kWh, {leg['stops']} stops (Modelled)", fontsize=7.5)
    ax.legend(fontsize=6, loc="lower right", framealpha=0.85, frameon=True)
    # B: observation patch
    ax = fig.add_subplot(gs[0, 2])
    ax.grid(False)
    if patch is None:
        ax.text(0.5, 0.5, "no observation recorded", transform=ax.transAxes, ha="center", fontsize=7)
    else:
        fwd = (np.arange(PATCH + 1) - PATCH_BEHIND - 0.5) * PATCH_RES_M
        lat = (np.arange(PATCH + 1) - PATCH / 2) * PATCH_RES_M
        im = ax.pcolormesh(lat, fwd, patch * 10.0, cmap=BATLOW_CMAP, shading="flat")
        ax.plot(0, 0, marker=(3, 0, 0), color="white", ms=7, mec=INK)
        cb = fig.colorbar(im, ax=ax, fraction=0.05, pad=0.03)
        cb.set_label("height relative to the rover (m)", fontsize=6.5)
        cb.ax.tick_params(labelsize=6)
        ax.set_aspect("equal")
        ax.set_xlabel("lateral (m), left → right", fontsize=7)
        ax.set_ylabel("forward along the heading (m)", fontsize=7)
        ax.tick_params(labelsize=6.5)
    ax.set_title(f"B. {PATCH} × {PATCH} patch at {PATCH_RES_M:g} m,\nrelative-height channel", fontsize=7.5)
    # C: speed made good vs RTT
    ax = fig.add_subplot(gs[1, 0])
    rtts = np.linspace(0.0, 8.0, 81)
    ax.plot(rtts, [_smg_kmh("teleop", r) for r in rtts], color=TOL["red"], lw=1.6, label="environment, teleoperated (flat ground)")
    jsc = R.LITAKER_SMG_KMH
    ax.scatter(list(jsc), list(jsc.values()), marker="D", s=26, color=INK, zorder=5, label="JSC teleoperation (Litaker et al.; Measured)")
    for r, v in jsc.items():
        ax.annotate(f"{v:.2f}", (r, v), xytext=(5, 4), textcoords="offset points", fontsize=6, color=INK)
    xr = 10.4
    for aut, c in (("supervised", TOL["yellow"]), ("autonomous", TOL["blue"])):
        v = _smg_kmh(aut, 0.0)
        ax.axhline(v, color=c, lw=1.2, ls="--")
        if aut == "autonomous":
            ax.text(xr - 0.15, v + 0.12, f"autonomous cap {v:.1f} km/h\n(LRV moving average; Spec)", fontsize=8, color=INK2, ha="right", va="bottom")
        else:   # above the line at its right end: the stretch the teleop curve and its value labels leave free
            ax.text(xr - 0.15, v + 0.5, f"supervised cap\n{v:.2f} km/h (Assumed)", fontsize=7.5, color=INK2, ha="right", va="bottom")
    ax.set_xlim(-0.2, xr)
    ax.set_ylim(0, 10.8)
    ax.set_xlabel("round-trip control delay (s)")
    ax.set_ylabel("speed made good (km/h)")
    ax.set_title("C. Speed made good vs delay", fontsize=8.5)
    ax.legend(fontsize=6, loc="upper left", bbox_to_anchor=(-0.12, -0.17), ncol=1, frameon=False)
    # D: slip vs slope
    ax = fig.add_subplot(gs[1, 1:])
    cols = ordered_colors(len(R.SLIP_PHI_DEG))
    g = np.linspace(0, 30, 121)
    soil = {37.8: "loose", 42.0: "medium", 47.8: "dense"}
    for ph, c in zip(R.SLIP_PHI_DEG, cols):
        ax.plot(g, [R.slip(x, ph) for x in g], color=c, lw=1.5, label=f"φ = {ph:g}° ({soil.get(float(ph), '')} GRC-3)")
        ax.scatter(R.SLIP_TABLE_DEG, R.SLIP_CURVES[list(R.SLIP_PHI_DEG).index(ph)], s=14, color=c, zorder=4)
    ax.axhline(R.DIG_IN_SLIP, color=MUTED, lw=0.8, ls=":")
    ax.text(0.3, R.DIG_IN_SLIP + 0.012, f"dig-in > {100 * R.DIG_IN_SLIP:.0f} % slip", fontsize=8, color=INK2, ha="left", va="bottom")
    ax.add_patch(Rectangle((YUTU2_SLOPE_SHOWN_DEG[0], YUTU2_SLIP[0]), YUTU2_SLOPE_SHOWN_DEG[1] - YUTU2_SLOPE_SHOWN_DEG[0], YUTU2_SLIP[1] - YUTU2_SLIP[0],
                           facecolor=TOL["grey"], alpha=0.45, edgecolor=INK2, lw=0.6, hatch="////",
                           label=f"Yutu-2 in situ {100 * YUTU2_SLIP[0]:.1f}-{100 * YUTU2_SLIP[1]:.1f} % on 'gentle slopes'\n(range only, slope unstated; "
                                 f"drawn {YUTU2_SLOPE_SHOWN_DEG[0]:g}-{YUTU2_SLOPE_SHOWN_DEG[1]:g}°; Measured)"))
    ax.set_xlim(0, 30)
    ax.set_ylim(0, 1.0)
    ax.set_xlabel("slope along the heading, uphill (°)")
    ax.set_ylabel("longitudinal slip (fraction)")
    ax.set_title("D. Slip vs slope", fontsize=8.5)
    lg = ax.legend(fontsize=6, loc="lower right", frameon=True, framealpha=0.9, title="Hu et al. 2024, 440 kg in lunar gravity (Modelled)",
                   borderaxespad=0.3)
    lg.get_title().set_fontsize(6)
    paths = save_fixed(fig, "v3_fig04_rover", out)
    del hs
    notes = [f"route BASE -> {psr[0]}: {np.hypot(*np.diff(route, axis=0).T).sum() / 1000:.2f} km planned, {leg['distance_m'] / 1000:.2f} km driven, "
             f"{leg['time_s'] / 3600:.2f} h, {leg['energy_wh'] / 1000:.2f} kWh, {leg['interventions']} interventions, {leg['stops']} stops, "
             f"reached = {leg['reached']} (teleop {rtt_s:g} s, phi {phi:g}, seed {seed}, sun azimuth {sun_az_deg:g} deg)",
             ("intervention markers are the rover's position at the step before the env reset it to the route (<= 2.5 m off the trigger point)"
              if len(inter) else f"NO intervention occurred on this drive (teleop {rtt_s:g} s, phi {phi:g}, seed {seed}), so the caption's "
                                 "'intervention points' has nothing to show; the legend omits the entry"),
             "panel B shows the step whose relative-height channel has the largest spread (most relief in view); its position is the yellow square in A",
             "panel C: the environment line is the flat-ground speed made good with stops, which reproduces the four JSC values by construction "
             "(the stop cadence is solved from them); caps drawn as speed made good incl. the supervised approval stops",
             "panel D: the research note gives the Yutu-2 slip as a range (10.5-19.7 %) without slope values, so it is drawn as a band and the "
             "caption's 'Yutu-2 in-situ points' is not supported by the data at hand; source: " + YUTU2_SOURCE]
    return {"caption": CAPTIONS["v3_fig04_rover"], "files": paths, "notes": notes, "leg": {k: (float(v) if isinstance(v, (int, float, np.floating)) else v) for k, v in leg.items()}}


# ---------------------------------------------------------------------------
FIGURES = [("v3_fig01_terrain", v3_fig01_terrain), ("v3_fig03_descent", v3_fig03_descent), ("v3_fig04_rover", v3_fig04_rover)]
FIG_IDS = [f for f, _ in FIGURES]


def select(only):
    if not only:
        return list(FIG_IDS)
    chosen = []
    for o in only:
        o = str(o).strip().lower()
        hits = [f for f in FIG_IDS if f == o or f.split("_")[1] == o or (o.isdigit() and f.split("_")[1] == f"fig{int(o):02d}")
                or f"v3_{o}" == f]
        if not hits:
            raise SystemExit(f"unknown figure {o!r}; choose from {FIG_IDS}")
        chosen += [h for h in hits if h not in chosen]
    return chosen


def build(only=None, out=FIG, policies=POLICIES, seed=None, captions_name=CAPTIONS_FILE):
    os.makedirs(out, exist_ok=True)
    cpath = os.path.join(out, captions_name)
    caps = {}
    if os.path.exists(cpath):
        try:
            with open(cpath, encoding="utf-8") as f:
                caps = json.load(f)
        except (OSError, ValueError):
            caps = {}
    for fid, fn in FIGURES:
        if fid not in select(only):
            caps.setdefault(fid, {"id": fid, "file": f"figures/{fid}.png", "caption": CAPTIONS[fid], "status": "not built in this run"})
            continue
        t0 = time.time()
        print(f"[{fid}]")
        try:
            info = fn(out=out, policies=policies, seed=seed)
            caps[fid] = {"id": fid, "file": f"figures/{fid}.png", "caption": info["caption"], "status": "produced",
                         "files": [os.path.basename(p) for p in info["files"]], "notes": info.get("notes", []),
                         **{k: v for k, v in info.items() if k not in ("caption", "files", "notes")}, "seconds": round(time.time() - t0, 1)}
        except Skip as e:
            print(f"skip {fid}: {e}")
            caps[fid] = {"id": fid, "file": f"figures/{fid}.png", "caption": CAPTIONS[fid], "status": "skipped", "reason": str(e)}
        except Exception as e:  # noqa: BLE001
            print(f"FAILED {fid}: {e!r}")
            traceback.print_exc()
            plt.close("all")
            caps[fid] = {"id": fid, "file": f"figures/{fid}.png", "caption": CAPTIONS[fid], "status": "failed", "error": repr(e)}
    caps = {fid: caps[fid] for fid in FIG_IDS if fid in caps}
    with open(cpath, "w", encoding="utf-8") as f:
        json.dump(caps, f, indent=1, ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o))
    print(f"captions -> {cpath}")
    return caps


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--only", nargs="*", default=None)
    p.add_argument("--out", default=FIG)
    p.add_argument("--policies", default=POLICIES)
    p.add_argument("--seed", type=int, default=None, help="Figure 3 episode seed")
    a = p.parse_args(argv)
    caps = build(a.only, out=a.out, policies=a.policies, seed=a.seed)
    bad = [k for k, v in caps.items() if v["status"] == "failed"]
    print("status:", {k: v["status"] for k, v in caps.items()})
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
