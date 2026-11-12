"""E51 (B-91, Phase 6, H11): how good the clocks must be, for ranging and for road reservations.

    python tools/atc/run_e51.py run --seeds 1-30 [--max-seconds 480]    # resumable, one cache file per seed
    python tools/atc/run_e51.py build                                   # -> results/E51_clocks.json, E51_table.csv

Per seed (fleet x 1, the E50 scenario and July 2028 window; tools/atc/run_e50.py record / trajectories): the perfect-
position run's single-lane reservations and trajectories on a 60 s grid; a vehicle can take a two-way time transfer
when it has a radio path to the BASE mast (directly or through other vehicles; B-70 mesh, lunarsim.atc.pnt.LOS).
Sweep: oscillator class (crystal, CSAC) x resync interval (10 s, 1 min, 10 min, 1 h, 6 h, 1 day, never) x time scale
(lunar, and "earth_scale": the vehicles' clocks count Earth seconds against the base's lunar seconds). Baseline row:
perfect clocks (all effects zero). Clock model and effects: lunarsim/atc/clocks.py.

Outcomes per cell: one-way ranging error added (m; at the vehicle's driving steps, against the base clock); two-way
single-sided ranging error between vehicle pairs (m); time-stamped position error at 1 m/s between driving vehicles
(m); reservation conflicts caused by clock error alone, with the 0.1 s guard (note 01 B7) and with none; the largest
clock error (s); the share of sync attempts that failed for lack of contact. Holdover: the longest time without a
resync for each use of note 01 B7, for 95 % of vehicles (from the drawn clocks) and analytically.
H11 (PREREG6 section 4): supported if, for the crystal class, some resync interval gives zero clock-caused reservation
conflicts (guard 0.1 s) in every seed while the one-way ranging error it adds (p95) exceeds the ranging radio's own
noise (UWB 0.3 m, note 01 D).
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import math
import os
import sys
import time
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

CACHE = os.path.join(ROOT, ".cache", "atc", "e51")
OUT_JSON = os.path.join(ROOT, "results", "E51_clocks.json")
OUT_CSV = os.path.join(ROOT, "results", "E51_table.csv")
DESIGN = {
    "experiment": "E51 (B-91), Phase 6, H11 (paper/atc/PREREG6.md)",
    "scenario": "E50's (tools/atc/run_e50.py): p5 3eq, 30 % load, C_AUCTION, loss 0.10, roads atc, fleet x 1, July 2028",
    "classes": ["crystal", "csac"],
    "intervals_s": [10, 60, 600, 3600, 21600, 86400, None],
    "scales": ["lunar", "earth_scale"],
    "guards_s": [0.01, 0.1, 1.0, 0.0],
    # B-91b (post-hoc, LEAD 11 Nov): a daily thermal cycle on the frequency (amplitude: crystal half of LuGRE's 0 to
    # 8e-7 swing [LUGRE26]; CSAC its temperature term [CSAC]; period 24 h: Assumed), offset-only transfer vs a transfer
    # that also steers frequency; and a mixed fleet (every other vehicle counts Earth seconds) with and without the
    # 56.02 us/day correction (the second vehicle of every class on Earth seconds)
    "b91b": {"thermal_amp": {"crystal": 4e-7, "csac": 3e-10}, "thermal_period_s": 86400.0,
             "intervals_s": [60, 600, 3600, 21600, 86400], "mixed_intervals_s": [600, 3600, 86400, None]},
    "v_stamp_ms": 1.0,
    "uwb_sigma_m": 0.3,
    "seeds": list(range(1, 31)),
}


def contact_matrix(tr, rec):
    """(T, N) bool: a radio path to the BASE mast at each grid step (BFS over vehicles in DEM line of sight)."""
    import run_e50 as E5
    g = E5._geo()
    los = g["los"]
    T, N = tr.idx.shape
    ant = tr.ant
    C = np.zeros((T, N), bool)
    pairs = [(i, j) for i in range(N) for j in range(i + 1, N)]
    for k in range(T):
        ix = tr.idx[k]
        reach = np.array([los.mast[float(ant[i])][ix[i]] for i in range(N)])
        if reach.all():
            C[k] = True
            continue
        adj = np.zeros((N, N), bool)
        for i, j in pairs:
            if los.mat[(float(ant[i]), float(ant[j]))][ix[i], ix[j]]:
                adj[i, j] = adj[j, i] = True
        for _ in range(N):
            new = reach | adj[reach].any(axis=0)
            if (new == reach).all():
                break
            reach = new
        C[k] = reach
    return C


def conflicts(rec, clk, t0_s, guard_s, pair_ok=None):
    """Clock-only conflicts: conflicting (R3) pairs of single-lane reservations, nominal gap + 2 x guard < x_B - x_A
    (B the later one; module docstring)."""
    from lunarsim.atc.safety import r3_pair_conflict
    vid_col = {int(v): n for n, v in enumerate(sorted(rec["ant"]))}
    by = defaultdict(list)
    for res_id, a, b, mh, d, vid, key, f_in, f_out in rec["res_log"]:
        by[res_id].append((a, b, d, int(vid)))
    n_c, worst, n_pairs = 0, -math.inf, 0
    for res_id, w in by.items():
        w.sort()
        br = bool(rec["branched"].get(res_id, False))
        for i in range(len(w)):
            for j in range(i + 1, len(w)):
                A_, B_ = w[i], w[j]
                if B_[0] - A_[1] > 1.0:                     # nominal gap over an hour: clocks cannot close it
                    break
                if A_[3] == B_[3] or not r3_pair_conflict(A_[2], B_[2], br):
                    continue
                if pair_ok is not None and not pair_ok(vid_col[A_[3]], vid_col[B_[3]]):
                    continue
                n_pairs += 1
                xa = float(clk.x(vid_col[A_[3]], t0_s + (A_[1] - rec["_t0_h"]) * 3600.0)[0])
                xb = float(clk.x(vid_col[B_[3]], t0_s + (B_[0] - rec["_t0_h"]) * 3600.0)[0])
                gap_s = (B_[0] - A_[1]) * 3600.0
                close = (xb - xa) - gap_s                   # how far the clocks close the nominal gap
                worst = max(worst, close)
                n_c += int(close > 2.0 * guard_s)
    return n_c, (worst if n_pairs else 0.0), n_pairs


def run_seed(seed):
    import run_e50 as E5
    from lunarsim.atc import clocks as CK
    month, t0h, t1h, share = E5._window()
    t = time.time()
    rec = E5.record(1, seed, t0h, t1h)
    rec["_t0_h"] = t0h
    tr = E5.trajectories(rec, t0h, t1h)
    C = contact_matrix(tr, rec)
    T, N = C.shape
    dt = tr.dt_s
    mv = tr.ds > 0
    step_s = np.arange(T) * dt
    out = {"seed": seed, "n_vehicles": N, "contact_share": float(C.mean()), "reservations": len(rec["res_log"]),
           "cells": [], "holdover_draws": {}}
    for cls in DESIGN["classes"]:
        for scale in DESIGN["scales"]:
            rng = np.random.default_rng([seed, 91, DESIGN["classes"].index(cls), DESIGN["scales"].index(scale)])
            y, A = CK.draw(N, cls, rng, earth_scale=(scale == "earth_scale"))
            if scale == "lunar":
                out["holdover_draws"][cls] = {"y": y.tolist(), "A": A.tolist()}
            # two-way single-sided ranging: depends on the frequency errors only
            tw = [C_ * CK.T_REPLY_S * abs(y[i] - y[j]) / 2.0 for i in range(N) for j in range(i + 1, N)
                  for C_ in (CK.C_M_S,)]
            for I in DESIGN["intervals_s"]:
                if I is None:
                    n_att, fail = 0, float("nan")
                    contact = None
                else:
                    n_att = int((t1h - t0h) * 3600.0 // I)
                    att_step = np.minimum(((np.arange(n_att) + 1) * I // dt).astype(int), T - 1)
                    contact = lambda i, _s=att_step: C[_s, i]
                    fail = float(1.0 - C[att_step].mean()) if n_att else float("nan")
                clk = CK.Clocks(y, A, 0.0, I, contact, n_att, np.random.default_rng([seed, 91, 7]))
                X = np.stack([clk.x(i, step_s) for i in range(N)], axis=1)          # (T, N) seconds
                one = CK.C_M_S * np.abs(X[mv])
                # time-stamp error between pairs of driving vehicles at 1 m/s
                st = []
                for k in np.nonzero(mv.sum(axis=1) >= 2)[0][::5]:
                    xs = X[k, mv[k]]
                    st.append(np.abs(xs[:, None] - xs[None, :]).max())
                row = {"class": cls, "scale": scale, "interval_s": I, "sync_fail_share": fail,
                       "one_way_m": {"median": float(np.median(one)), "p95": float(np.quantile(one, 0.95)),
                                     "max": float(one.max())},
                       "two_way_single_sided_m_p95": float(np.quantile(tw, 0.95)),
                       "stamp_m_at_1ms_p95": float(np.quantile(st, 0.95)) * DESIGN["v_stamp_ms"] if st else 0.0,
                       "max_abs_clock_s": float(np.abs(X).max())}
                for g in DESIGN["guards_s"]:
                    n_c, worst, n_pairs = conflicts(rec, clk, 0.0, g)
                    row[f"conflicts_guard_{g:g}"] = n_c
                    row["worst_close_s"] = worst
                    row["conflict_pairs_checked"] = n_pairs
                out["cells"].append(row)
    out["cells_b"] = run_b91b(seed, rec, C, mv, step_s, t0h, t1h, dt)
    out["run_s"] = round(time.time() - t, 1)
    return out


def _contact_fn(C, I, t0h, t1h, dt):
    T = C.shape[0]
    if I is None:
        return None, 0
    n_att = int((t1h - t0h) * 3600.0 // I)
    att_step = np.minimum(((np.arange(n_att) + 1) * I // dt).astype(int), T - 1)
    return (lambda i, _s=att_step: C[_s, i]), n_att


def run_b91b(seed, rec, C, mv, step_s, t0h, t1h, dt):
    """B-91b cells: steering under a thermal cycle, and the mixed-scale fleet (DESIGN["b91b"])."""
    from lunarsim.atc import clocks as CK
    B = DESIGN["b91b"]
    T, N = C.shape
    out = []
    for cls in DESIGN["classes"]:
        rng = np.random.default_rng([seed, 91, 20 + DESIGN["classes"].index(cls)])
        y, A = CK.draw(N, cls, rng)
        phase = rng.uniform(0.0, 2.0 * math.pi, N)
        for I in B["intervals_s"]:
            contact, n_att = _contact_fn(C, I, t0h, t1h, dt)
            for steer in (False, True):
                clk = CK.Clocks(y, A, 0.0, I, contact, n_att, np.random.default_rng([seed, 91, 8]), steer=steer,
                                thermal_amp=B["thermal_amp"][cls], thermal_period_s=B["thermal_period_s"], phase=phase)
                X = np.stack([clk.x(i, step_s) for i in range(N)], axis=1)
                one = CK.C_M_S * np.abs(X[mv])
                row = {"part": "steering", "class": cls, "interval_s": I, "transfer": "steer" if steer else "offset",
                       "one_way_m_p95": float(np.quantile(one, 0.95)), "max_abs_clock_s": float(np.abs(X).max()),
                       "estimator_err_p95": float(np.quantile(np.abs(clk.est_err), 0.95)) if clk.est_err else None}
                for g in (0.01, 0.1):
                    row[f"conflicts_guard_{g:g}"] = conflicts(rec, clk, 0.0, g)[0]
                out.append(row)
        # mixed fleet: every other vehicle counts Earth seconds (y + 6.4844e-10) unless the correction is applied
        rng = np.random.default_rng([seed, 91, 30 + DESIGN["classes"].index(cls)])
        y, A = CK.draw(N, cls, rng)
        # Earth seconds for the second vehicle of every class (owner A lunar, owner B Earth, owner C split): single-lane
        # traffic is mostly the two cargo rovers, so the split must separate them
        import run_e50 as E5
        fleet = E5._scenario(1, t1h).fleet
        seen, earth = {}, np.zeros(N, bool)
        for i, f in enumerate(fleet[:N]):
            c = str(f[1]).split("_")[0]          # class family: LTV1, CARGO, MAPP, HOPPER
            seen[c] = seen.get(c, 0) + 1
            earth[i] = seen[c] % 2 == 0
        cross = lambda a, b: bool(earth[a] != earth[b])
        for I in B["mixed_intervals_s"]:
            contact, n_att = _contact_fn(C, I, t0h, t1h, dt)
            for corrected in (False, True):
                yy = y + (0.0 if corrected else CK.RATE_MOON_MINUS_EARTH) * earth
                clk = CK.Clocks(yy, A, 0.0, I, contact, n_att, np.random.default_rng([seed, 91, 9]))
                X = np.stack([clk.x(i, step_s) for i in range(N)], axis=1)
                d = []
                for k in np.nonzero(mv.any(axis=1))[0][::3]:
                    xe, xl = X[k, earth], X[k, ~earth]
                    if len(xe) and len(xl):
                        d.append(np.abs(xe[:, None] - xl[None, :]).max())
                row = {"part": "mixed", "class": cls, "interval_s": I,
                       "scales": "lunar for all (corrected)" if corrected else "half Earth seconds, no conversion",
                       "cross_scale_one_way_m_p95": float(CK.C_M_S * np.quantile(d, 0.95)) if d else 0.0,
                       "cross_scale_one_way_m_max": float(CK.C_M_S * np.max(d)) if d else 0.0}
                for g in (0.01, 0.1):
                    n_c, worst, n_pairs = conflicts(rec, clk, 0.0, g, pair_ok=cross)
                    row[f"cross_scale_conflicts_guard_{g:g}"] = n_c
                    row["cross_scale_pairs_checked"] = n_pairs
                out.append(row)
    return out


def cmd_run(seeds, max_s):
    t0 = time.time()
    os.makedirs(CACHE, exist_ok=True)
    for s in seeds:
        p = os.path.join(CACHE, f"s{s}.json")
        if os.path.isfile(p):
            continue
        if time.time() - t0 > max_s * 0.6:
            print(f"stop before seed {s}: time budget", flush=True)
            return
        o = run_seed(s)
        json.dump(o, open(p + ".tmp", "w"), allow_nan=True)
        os.replace(p + ".tmp", p)
        print(f"s{s} done in {o['run_s']} s", flush=True)
    print("all requested seeds done", flush=True)


def build():
    from lunarsim.atc import clocks as CK
    files = sorted(glob.glob(os.path.join(CACHE, "s*.json")), key=lambda p: int(os.path.basename(p)[1:-5]))
    S = [json.load(open(p)) for p in files]
    if not S:
        raise SystemExit("no E51 seeds")
    key = lambda r: (r["class"], r["scale"], r["interval_s"])
    cells = defaultdict(list)
    for s in S:
        for r in s["cells"]:
            cells[key(r)].append(r)
    rows = [{"class": "perfect", "scale": "-", "interval_s": "-", "seeds": len(S), "sync_fail_share": 0.0,
             "one_way_m_median": 0.0, "one_way_m_p95": 0.0, "one_way_m_max": 0.0, "two_way_single_sided_m_p95": 0.0,
             "stamp_m_at_1ms_p95": 0.0, "max_abs_clock_s": 0.0, "conflicts_guard_0.01": 0, "conflicts_guard_0.1": 0,
             "conflicts_guard_1": 0, "conflicts_guard_0": 0,
             "seeds_with_conflict_guard_0.1": 0, "conflict_pairs_checked": "", "worst_close_s": 0.0}]
    for (cls, scale, I), rs in cells.items():
        rows.append({"class": cls, "scale": scale, "interval_s": "never" if I is None else I, "seeds": len(rs),
                     "sync_fail_share": float(np.nanmean([r["sync_fail_share"] for r in rs])) if I is not None else "",
                     "one_way_m_median": float(np.mean([r["one_way_m"]["median"] for r in rs])),
                     "one_way_m_p95": float(np.mean([r["one_way_m"]["p95"] for r in rs])),
                     "one_way_m_max": float(np.max([r["one_way_m"]["max"] for r in rs])),
                     "two_way_single_sided_m_p95": float(np.mean([r["two_way_single_sided_m_p95"] for r in rs])),
                     "stamp_m_at_1ms_p95": float(np.mean([r["stamp_m_at_1ms_p95"] for r in rs])),
                     "max_abs_clock_s": float(np.max([r["max_abs_clock_s"] for r in rs])),
                     "conflicts_guard_0.01": int(sum(r["conflicts_guard_0.01"] for r in rs)),
                     "conflicts_guard_0.1": int(sum(r["conflicts_guard_0.1"] for r in rs)),
                     "conflicts_guard_1": int(sum(r["conflicts_guard_1"] for r in rs)),
                     "conflicts_guard_0": int(sum(r["conflicts_guard_0"] for r in rs)),
                     "seeds_with_conflict_guard_0.1": int(sum(r["conflicts_guard_0.1"] > 0 for r in rs)),
                     "conflict_pairs_checked": int(sum(r["conflict_pairs_checked"] for r in rs)),
                     "worst_close_s": float(np.max([r["worst_close_s"] for r in rs]))})
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{v:.6g}" if isinstance(v, float) else v) for k, v in r.items()})
    # holdover: 95 % of drawn vehicles hold at least this long (r = 0), and analytic at the class's 95th percentile y
    hold = {}
    for cls in DESIGN["classes"]:
        ys = np.concatenate([np.abs(s["holdover_draws"][cls]["y"]) for s in S])
        As = np.concatenate([np.abs(s["holdover_draws"][cls]["A"]) for s in S])
        c = CK.CLASSES[cls]
        y95 = 0.95 * c["y_hi"] if "y_hi" in c else 1.959964 * c["y_sigma"]
        hold[cls] = {}
        for use, b in CK.USES.items():
            hs = np.array([CK.holdover_s(b, y, A) for y, A in zip(ys, As)])
            hold[cls][use] = {"budget_s": b, "p5_over_vehicles_s": float(np.quantile(hs, 0.05)),
                              "analytic_y95_s": CK.holdover_s(b, y95, CK.ageing_rate(cls)), "n_vehicles": int(len(hs))}
    # H11
    cr = [r for r in rows if r["class"] == "crystal" and r["scale"] == "lunar" and r["interval_s"] != "never"]
    ok = [r["interval_s"] for r in cr if r["seeds_with_conflict_guard_0.1"] == 0 and r["one_way_m_p95"] > DESIGN["uwb_sigma_m"]]
    h11 = {"supported": bool(ok), "intervals_meeting_both": ok,
           "rule": "crystal, lunar scale: zero clock-caused reservation conflicts (guard 0.1 s) in every seed AND one-way "
                   "ranging error added (p95) above the UWB noise 0.3 m"}
    doc = {"experiment": DESIGN["experiment"], "design": {k: v for k, v in DESIGN.items() if k != "experiment"},
           "seeds": [s["seed"] for s in S], "contact_share_mean": float(np.mean([s["contact_share"] for s in S])),
           "reservations_per_seed_mean": float(np.mean([s["reservations"] for s in S])),
           "rows": rows, "holdover": hold, "h11": h11,
           "constants": {"rate_moon_minus_earth": CK.RATE_MOON_MINUS_EARTH, "tt_sigma_s": CK.TT_SIGMA_S,
                         "t_reply_s": CK.T_REPLY_S, "guard_s": CK.GUARD_S, "classes": CK.CLASSES}}
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, allow_nan=False, default=lambda x: None)
        f.write("\n")
    build_b(S)
    print(json.dumps({"seeds": len(S), "h11": h11}, indent=1))


OUT_JSON_B = os.path.join(ROOT, "results", "E51b_clocks.json")
OUT_CSV_B = os.path.join(ROOT, "results", "E51b_table.csv")


def build_b(S):
    """B-91b: steering vs offset-only under the thermal cycle; the mixed-scale fleet (sums / means over seeds)."""
    groups = defaultdict(list)
    for s in S:
        for r in s.get("cells_b", []):
            k = (r["part"], r["class"], r["interval_s"], r.get("transfer") or r.get("scales"))
            groups[k].append(r)
    rows = []
    for (part, cls, I, var), rs in groups.items():
        row = {"part": part, "class": cls, "interval_s": "never" if I is None else I, "variant": var, "seeds": len(rs)}
        for k in rs[0]:
            if k in ("part", "class", "interval_s", "transfer", "scales"):
                continue
            vals = [r[k] for r in rs if r[k] is not None]
            if not vals:
                row[k] = ""
            elif "conflicts" in k or k.endswith("pairs_checked"):
                row[k] = int(sum(vals))
            elif k.endswith("_max") or k.startswith("max_"):
                row[k] = float(max(vals))
            else:
                row[k] = float(np.mean(vals))
        rows.append(row)
    keys = []
    for r in rows:
        keys += [k for k in r if k not in keys]
    with open(OUT_CSV_B, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({k: (f"{r[k]:.6g}" if isinstance(r.get(k), float) else r.get(k, "")) for k in keys})
    doc = {"experiment": "E51b (B-91b): post-hoc variants of E51", "design": DESIGN["b91b"],
           "estimator": "steering: yhat_k = mean frequency over the previous transfer interval, measured from the two "
                        "transfer offsets; its error is sqrt(2) x 100 ns / interval plus the change of the frequency over "
                        "the interval (thermal cycle, ageing); applied from t_k (lunarsim/atc/clocks.py Clocks)",
           "seeds": [s["seed"] for s in S], "rows": rows}
    with open(OUT_JSON_B, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, allow_nan=False, default=lambda x: None)
        f.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "build"])
    ap.add_argument("--seeds", default="1-30")
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    if a.cmd == "run":
        lo, hi = (a.seeds.split("-") + [a.seeds])[:2]
        cmd_run(list(range(int(lo), int(hi) + 1)), a.max_seconds)
    else:
        build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
