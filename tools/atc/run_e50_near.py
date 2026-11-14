"""B-101 (P3 M5; decisions B4): H9' clause 2, "near the base", under several readings, on E50's runs.

    python tools/atc/run_e50_near.py run --mult 1 --seeds 1-30 [--max-seconds 480]   # resumable, one file per cell
    python tools/atc/run_e50_near.py run --mult 4 --seeds 1-10
    python tools/atc/run_e50_near.py build                       # -> results/E50_near_base.json, E50_near_base.csv

E50's cells keep only the error summary under one reading (two or more beacons in line of sight), so each cell's
perfect run and navigation runs are repeated here (E50's own functions, same seeds; the perfect run's delay and the
reading-(a) p95 are checked against E50's cell; E50's cache is only read). Readings, over driving vehicle-steps:
  a  2+ beacons in radio line of sight (the reading used so far: run_e50 DESIGN region_rule)
  b  1+ beacon in radio line of sight
  c  within 1 km of the BASE mast
  d  within radio range (5 km, pnt radio_range_m) of the BASE mast
  e  within radio range (5 km) of any base beacon: PREREG6's words "within radio range of the base beacons"
     taken literally (distance only, terrain ignored)
Per layer set (dr; dr + ranging; dr + ranging + fixes; + LANS as in 2030; in 2028 LANS gives no fix) and reading:
the share of driving steps covered, the p95 error inside (and outside), per seed. Ranging-error sweep (referee M5)
on seeds 1-6 at 1x for dr + ranging: UWB sigma 0.1 / 0.3 / 0.7 m with long-range 3 m, and long-range 1 / 3 / 10 m
with UWB 0.3 m (one at a time; 0.3 / 3 is the default).
"""
from __future__ import annotations

import argparse
import csv
import glob
import gzip
import json
import os
import pickle
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_e50 as E5  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "e50_near")
OUT_JSON = os.path.join(ROOT, "results", "E50_near_base.json")
OUT_CSV = os.path.join(ROOT, "results", "E50_near_base.csv")
BUDGET = 5.0
READINGS = {"a": "2+ beacons in radio line of sight (used so far)", "b": "1+ beacon in radio line of sight",
            "c": "within 1 km of the BASE mast", "d": "within radio range (5 km) of the BASE mast",
            "e": "within radio range (5 km) of any base beacon (PREREG6's words, distance only)"}
SETS = {"dr": ("dr", 2028), "dr+ranging": ("dr+ranging", 2028), "dr+ranging+fixes": ("dr+ranging+fixes", 2028),
        "lans@2030": ("dr+ranging+fixes+lans", 2030)}
SWEEP = [("uwb_sigma_m", 0.1), ("uwb_sigma_m", 0.3), ("uwb_sigma_m", 0.7),
         ("radio_sigma_m", 1.0), ("radio_sigma_m", 3.0), ("radio_sigma_m", 10.0)]
SWEEP_SEEDS = range(1, 7)


def _peak_mb():
    try:
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + \
                       [(n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "a", "b", "c", "d", "e", "f")]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k32 = ctypes.WinDLL("kernel32")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        f = k32.K32GetProcessMemoryInfo
        f.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD]
        f(k32.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return round(c.PeakWorkingSetSize / 2 ** 20, 1)
    except Exception:
        return None


def masks(tr, rec):
    """Reading masks over (T, N) vehicle-steps (not yet restricted to driving)."""
    from lunarsim.atc import pnt as PN
    g = E5._geo()
    los = g["los"]
    bi, bxy = E5.beacons(rec)
    cnt = np.zeros(tr.idx.shape, np.int8)
    for b in bi:
        for h in np.unique(tr.ant):
            sel = tr.ant == h
            if b == g["ids"]["BASE"]:
                cnt[:, sel] += los.mast[float(h)][tr.idx[:, sel]]
            else:
                cnt[:, sel] += los.mat[(2.5, float(h))][b, tr.idx[:, sel]]
    rr = PN.DEFAULTS["radio_range_m"]
    base_xy = g["xy"][g["ids"]["BASE"]]
    d_base = np.hypot(tr.xy[..., 0] - base_xy[0], tr.xy[..., 1] - base_xy[1])
    d_any = np.min(np.stack([np.hypot(tr.xy[..., 0] - x, tr.xy[..., 1] - y) for x, y in bxy]), axis=0)
    out = {"a": cnt >= 2, "b": cnt >= 1, "c": d_base <= 1000.0, "d": d_base <= rr, "e": d_any <= rr}
    assert np.array_equal(out["a"], E5.near_mask(tr, rec))     # reading a is E50's region rule
    return out


def _p95(err, m):
    return float(np.quantile(err[m], 0.95)) if m.any() else None


def run_cell(mult, seed):
    from lunarsim.atc import pnt as PN
    t_s = time.time()
    month, t0, t1, share = E5._window()
    rec = E5.record(mult, seed, t0, t1)
    tr = E5.trajectories(rec, t0, t1)
    mv = tr.ds > 0
    M = masks(tr, rec)
    out = {"mult": mult, "seed": seed, "window": [t0, t1], "driving_steps": int(mv.sum()),
           "perfect_delay_mean_h": rec["delay_mean_h"],
           "share_of_driving": {r: float((m & mv).sum() / max(1, mv.sum())) for r, m in M.items()}, "sets": {}}
    bi, bxy = E5.beacons(rec)
    kw = dict(los=E5._geo()["los"], beacon_idx=bi, beacon_xy=bxy, mast_idx=E5._geo()["ids"]["BASE"], store_errors=False)
    for name, (ls, year) in SETS.items():
        res = PN.simulate(tr, PN.LAYER_SETS[ls], seed, params={"year": year}, **kw)
        out["sets"][name] = {r: {"in_p95_m": _p95(res.err, m & mv), "out_p95_m": _p95(res.err, ~m & mv)} for r, m in M.items()}
        out["sets"][name]["all_driving_p95_m"] = _p95(res.err, mv)
        del res
    if mult == 1 and seed in SWEEP_SEEDS:
        out["sweep"] = []
        for par, val in SWEEP:
            res = PN.simulate(tr, PN.LAYER_SETS["dr+ranging"], seed, params={"year": 2028, par: val}, **kw)
            out["sweep"].append({"param": par, "value": val,
                                 **{r: _p95(res.err, m & mv) for r, m in M.items()}})
            del res
    p50 = os.path.join(E5.CACHE, f"m{mult}_s{seed}.pkl.gz")
    if os.path.isfile(p50):
        with gzip.open(p50) as f:
            c = pickle.load(f)
        out["e50_reproduced"] = {
            "perfect_delay": c["perfect"]["delay_mean_h"] == rec["delay_mean_h"],
            "ranging_near_p95": abs(c["nav"]["dr+ranging"]["near"]["p95_m"] - out["sets"]["dr+ranging"]["a"]["in_p95_m"]) < 1e-4}
    out["cell_s"] = round(time.time() - t_s, 1)
    out["peak_mb"] = _peak_mb()
    return out


def _seeds(s):
    lo, hi = (s.split("-") + [s])[:2]
    return list(range(int(lo), int(hi) + 1))


def cmd_run(mult, seeds, max_s):
    os.makedirs(CACHE, exist_ok=True)
    t0 = time.time()
    last = 60.0 * mult
    for s in seeds:
        p = os.path.join(CACHE, f"m{mult}_s{s}.json")
        if os.path.isfile(p):
            continue
        if time.time() - t0 + last * 1.25 > max_s:
            print(f"stop before m{mult} s{s}: time budget", flush=True)
            return
        ts = time.time()
        out = run_cell(mult, s)
        with open(p + ".tmp", "w") as f:
            json.dump(out, f)
        os.replace(p + ".tmp", p)
        last = time.time() - ts
        r = out["sets"]["dr+ranging"]
        print(f"m{mult} s{s}: {last:.0f} s, ranging p95 a/b/c/d/e "
              + " / ".join(f"{r[k]['in_p95_m']:.2f}" if r[k]["in_p95_m"] is not None else "-" for k in READINGS)
              + f", repro {all(out.get('e50_reproduced', {}).values())}, peak {out['peak_mb']} MB", flush=True)
    print("all requested cells done", flush=True)


def _ci(x, rng, B=10000):
    x = np.asarray([v for v in x if v is not None], float)
    if not len(x):
        return None
    m = x[rng.integers(0, len(x), (B, len(x)))].mean(axis=1)
    return [float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def cmd_build():
    rng = np.random.default_rng([50, 101])
    cells = [json.load(open(p)) for p in glob.glob(os.path.join(CACHE, "m*_s*.json"))]
    doc = {"task": "B-101 (P3 M5; decisions B4)", "note": __doc__.strip().split("\n\n")[1].replace("\n", " "),
           "readings": READINGS, "budget_m": BUDGET, "multiples": {}, "sweep": None}
    rows = []
    for mult in sorted({c["mult"] for c in cells}):
        C = sorted((c for c in cells if c["mult"] == mult), key=lambda c: c["seed"])
        blk = {"seeds": [c["seed"] for c in C], "e50_reproduced_all": all(all(c.get("e50_reproduced", {}).values())
                                                                          and c.get("e50_reproduced") for c in C),
               "peak_mb_max": max((c["peak_mb"] or 0) for c in C), "cell_s_mean": float(np.mean([c["cell_s"] for c in C])),
               "share_of_driving": {r: {"mean": float(np.mean([c["share_of_driving"][r] for c in C])),
                                        "min": float(min(c["share_of_driving"][r] for c in C)),
                                        "max": float(max(c["share_of_driving"][r] for c in C))} for r in READINGS},
               "sets": {}}
        for name in SETS:
            blk["sets"][name] = {}
            for r in READINGS:
                vin = [c["sets"][name][r]["in_p95_m"] for c in C]
                vout = [c["sets"][name][r]["out_p95_m"] for c in C]
                ok = [v for v in vin if v is not None]
                blk["sets"][name][r] = {
                    "in_p95_m_mean": float(np.mean(ok)) if ok else None, "in_p95_m_ci95_seeds": _ci(vin, rng),
                    "in_p95_m_min_max": [float(min(ok)), float(max(ok))] if ok else None,
                    "seeds_inside_budget": int(sum(v < BUDGET for v in ok)), "seeds_with_steps": len(ok),
                    "out_p95_m_mean": float(np.mean([v for v in vout if v is not None])) if any(v is not None for v in vout) else None}
                for c in C:
                    rows.append({"mult": mult, "seed": c["seed"], "layer_set": name, "reading": r,
                                 "share_of_driving": round(c["share_of_driving"][r], 5),
                                 "in_p95_m": None if c["sets"][name][r]["in_p95_m"] is None else round(c["sets"][name][r]["in_p95_m"], 4),
                                 "out_p95_m": None if c["sets"][name][r]["out_p95_m"] is None else round(c["sets"][name][r]["out_p95_m"], 4),
                                 "inside_budget": None if c["sets"][name][r]["in_p95_m"] is None else c["sets"][name][r]["in_p95_m"] < BUDGET})
        rg = blk["sets"]["dr+ranging"]
        # B-118 N19: a reading with no driving steps in any seed has nothing to judge
        blk["h9_clause2_by_reading"] = {r: ("no driving steps under this reading: not judged" if rg[r]["seeds_with_steps"] == 0
                                            else "on the predicted side in every seed" if rg[r]["seeds_inside_budget"] == rg[r]["seeds_with_steps"]
                                            else "on the predicted side in no seed" if rg[r]["seeds_inside_budget"] == 0
                                            else f"on the predicted side in {rg[r]['seeds_inside_budget']} of {rg[r]['seeds_with_steps']} seeds")
                                        for r in READINGS}
        doc["multiples"][str(mult)] = blk
    sw = [c for c in cells if c.get("sweep")]
    if sw:
        S = {}
        for c in sw:
            for e in c["sweep"]:
                S.setdefault((e["param"], e["value"]), []).append(e)
        doc["sweep"] = {"seeds": sorted(c["seed"] for c in sw), "layer_set": "dr+ranging", "rows": [
            {"param": k[0], "value": k[1], **{r: {"in_p95_m_mean": float(np.mean([e[r] for e in v if e[r] is not None])),
                                                 "seeds_inside_budget": int(sum(e[r] < BUDGET for e in v if e[r] is not None)),
                                                 "seeds": len(v)} for r in READINGS}} for k, v in sorted(S.items())]}
    doc["verdict"] = "depends on the reading (PREREG6 section 6, 11 Nov): see h9_clause2_by_reading per fleet multiple"
    import e50_build as EB
    EB.keep_superseded(OUT_JSON, doc, E5.DESIGN["multiples"], doc["multiples"])
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, allow_nan=False)
        f.write("\n")
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for mult, blk in doc["multiples"].items():
        print(f"x{mult}", {r: round(v["mean"], 3) for r, v in blk["share_of_driving"].items()})
        for name in SETS:
            print("  ", name, {r: (round(v["in_p95_m_mean"], 2) if v["in_p95_m_mean"] is not None else None,
                                   f"{v['seeds_inside_budget']}/{v['seeds_with_steps']}") for r, v in blk["sets"][name].items()})
        print("  ", blk["h9_clause2_by_reading"], "repro", blk["e50_reproduced_all"], "peak", blk["peak_mb_max"])
    if doc["sweep"]:
        for row in doc["sweep"]["rows"]:
            print("  sweep", row["param"], row["value"], {r: (round(row[r]["in_p95_m_mean"], 2), row[r]["seeds_inside_budget"]) for r in READINGS})


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "build"])
    ap.add_argument("--mult", type=int, default=1)
    ap.add_argument("--seeds", default="1-30")
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        cmd_run(a.mult, _seeds(a.seeds), a.max_seconds)
    else:
        cmd_build()


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(560, exit=True)
    main()
