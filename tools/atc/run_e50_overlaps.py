"""B-102 (P2 M2; decisions B5): what a reservation overlap is, on E50's runs.

    python tools/atc/run_e50_overlaps.py run --mult 1 --seeds 1-30 [--max-seconds 480]   # resumable, staged
    python tools/atc/run_e50_overlaps.py build              # -> results/E50_overlaps.json, results/E50_overlaps.csv

E50 counts a violation when two conflicting single-lane windows of different vehicles overlap in true time (each
nominal end shifted by the vehicle's along-track error / speed; tools/atc/run_e50.py violations()). Its cells keep
only the count, so each cell's runs are repeated here with E50's own functions and seeds (perfect run; navigation per
layer set; the two margin runs with their navigation), staged so that no stage of a 4x cell exceeds a chunk, and the
counts are checked against E50's cells. E50's cache is only read.

Per overlap (conflicting pair, different vehicles, overlapping true windows; the same set violations() counts):
  - duration: seconds both vehicles' true windows are open at once;
  - nominal gap: the time between the two nominal windows (seconds; 0 = back to back, as a waiting vehicle files);
  - gap at entry: the distance between the two vehicles' true positions at the moment the second truly enters
    (true position = the planned position minus the navigation error e, the convention behind the time shift);
  - R1's required gap at that moment, rss_dmin(v_second, v_first, B_MIN_FLAT) with the segment speeds (the same-
    direction rule used as a yardstick; most conflicting pairs are head-on), and the 5 m static margin D0.
Back-to-back test (the referee's point): every consecutive pair of conflicting windows on a resource, in nominal
order, split by nominal gap (< 1 s = back to back) and the share that overlaps in true time, per layer set.
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
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_e50 as E5  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "e50_ovl")
OUT_JSON = os.path.join(ROOT, "results", "E50_overlaps.json")
OUT_CSV = os.path.join(ROOT, "results", "E50_overlaps.csv")
SETS = {"dr": ("dr", 2028), "dr+ranging": ("dr+ranging", 2028), "dr+ranging+fixes": ("dr+ranging+fixes", 2028),
        "lans@2030": ("dr+ranging+fixes+lans", 2030)}
MARGINS = E5.DESIGN["margin_sets"]                         # {"dr": "dr", "layered": "dr+ranging+fixes+lans"}
SERIES_FROM = {"dr": "dr", "layered": "dr+ranging+fixes"}  # E50: the layered series is the fixes set's (LANS 0 in 2028)
STAGES = ["rec"] + [f"nav_{s}" for s in SETS] + [f"{x}_{lab}" for lab in MARGINS for x in ("mrec", "mnav")]


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


def _dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path + ".tmp", "wb") as f:
        pickle.dump(obj, f)
    os.replace(path + ".tmp", path)


def _load(path):
    with gzip.open(path, "rb") as f:
        return pickle.load(f)


def _sp(m, s, st):
    return os.path.join(CACHE, f"m{m}_s{s}", st + ".pkl.gz")


def _cell(m, s):
    return os.path.join(CACHE, f"m{m}_s{s}.json")


def overlaps(rec, tr, res, t0, t1):
    """Every overlap violations() counts, with duration, nominal gap and gap at entry; and the back-to-back test."""
    from lunarsim.atc.safety import r3_pair_conflict, rss_dmin, B_MIN_FLAT, D0_M
    g = E5._geo()
    vid_col = {int(v): n for n, v in enumerate(tr.ids)}
    by_res = defaultdict(list)
    for res_id, a, b, mh, d, vid, key, f_in, f_out in rec["res_log"]:
        if b <= t0 or a >= t1:
            continue
        ids = g["legs"].get(key) or []
        if len(ids) < 2 or b <= a:
            continue
        P = g["xy"][ids]
        L = float(np.hypot(*np.diff(P, axis=0).T).sum())
        v_ms = (f_out - f_in) * L / ((b - a) * 3600.0)
        if v_ms <= 0:
            continue
        n = vid_col[int(vid)]
        sh = []
        for tt in (a, b):
            k = int(np.clip(round((tt - tr.t_h[0]) * 3600.0 / tr.dt_s), 0, len(tr.t_h) - 1))
            e_al = float(res.e[k, n] @ tr.head[k, n]) if res.e is not None else 0.0
            sh.append(e_al / v_ms / 3600.0)
        by_res[res_id].append((a + sh[0], b + sh[1], d, int(vid), a, b, v_ms))
    out, b2b = [], []
    for res_id, w in by_res.items():
        br = bool(rec["branched"].get(res_id, False))
        w.sort()
        for i in range(len(w)):
            for j in range(i + 1, len(w)):
                if w[j][0] >= w[i][1]:
                    break
                if w[i][3] == w[j][3] or not r3_pair_conflict(w[i][2], w[j][2], br):
                    continue
                A_, B_ = sorted((w[i], w[j]), key=lambda x: x[4])        # nominal order
                k = int(np.clip(round((w[j][0] - tr.t_h[0]) * 3600.0 / tr.dt_s), 0, len(tr.t_h) - 1))
                ni, nj = vid_col[w[i][3]], vid_col[w[j][3]]
                pi = tr.xy[k, ni] - (res.e[k, ni] if res.e is not None else 0.0)
                pj = tr.xy[k, nj] - (res.e[k, nj] if res.e is not None else 0.0)
                out.append({"dur_s": (min(w[i][1], w[j][1]) - w[j][0]) * 3600.0,
                            "nominal_gap_s": (B_[4] - A_[5]) * 3600.0,
                            "gap_m": float(np.hypot(*(pi - pj))),
                            "r1_dmin_m": float(rss_dmin(w[j][6], w[i][6], B_MIN_FLAT)), "d0_m": D0_M,
                            "head_on": bool(w[i][2] != w[j][2]), "branched": br})
        # back-to-back test: consecutive conflicting pairs in nominal order
        wn = sorted(w, key=lambda x: x[4])
        for i in range(len(wn) - 1):
            x, y = wn[i], wn[i + 1]
            if x[3] == y[3] or not r3_pair_conflict(x[2], y[2], br):
                continue
            ov = min(x[1], y[1]) - max(x[0], y[0])
            b2b.append((round((y[4] - x[5]) * 3600.0, 3), bool(ov > 0), max(0.0, ov * 3600.0)))
    return out, b2b


def _traj_nav(rec, ls, year, seed, t0, t1):
    from lunarsim.atc import pnt as PN
    tr = E5.trajectories(rec, t0, t1)
    bi, bxy = E5.beacons(rec)
    res = PN.simulate(tr, PN.LAYER_SETS[ls], seed, params={"year": year}, los=E5._geo()["los"], beacon_idx=bi,
                      beacon_xy=bxy, mast_idx=E5._geo()["ids"]["BASE"], store_errors=True)
    return tr, res


def run_stage(m, s, st):
    """One stage; B-120 D: its output carries E50's code fingerprint taken when it starts ("_code")."""
    code = E5.code_fingerprint()
    out = _run_stage(m, s, st)
    out["_code"] = code
    return out


def _run_stage(m, s, st):
    month, t0, t1, share = E5._window()
    if st == "rec":
        return E5.record(m, s, t0, t1)
    if st.startswith("nav_"):
        name = st[4:]
        ls, year = SETS[name]
        rec = _load(_sp(m, s, "rec"))
        tr, res = _traj_nav(rec, ls, year, s, t0, t1)
        ov, b2b = overlaps(rec, tr, res, t0, t1)
        o = {"overlaps": ov, "b2b": b2b, "violations": E5.violations(rec, tr, res, t0, t1)["violations"]}
        if name in SERIES_FROM.values():
            o["series"] = E5.bound_series(tr, res, t0)
        return o
    lab = st.split("_", 1)[1]
    if st.startswith("mrec_"):
        series = _load(_sp(m, s, f"nav_{SERIES_FROM[lab]}"))["series"]
        r = E5.record(m, s, t0, t1, pos_margin={"k": E5.DESIGN["k_pos"], "bound_m": series})
        return r
    recm = _load(_sp(m, s, f"mrec_{lab}"))
    tr, res = _traj_nav(recm, MARGINS[lab], 2028, s, t0, t1)
    ov, b2b = overlaps(recm, tr, res, t0, t1)
    return {"overlaps": ov, "b2b": b2b, "violations": E5.violations(recm, tr, res, t0, t1)["violations"],
            "margin_h_mean": float(np.mean([r[3] for r in recm["res_log"]])) if recm["res_log"] else 0.0}


def assemble(m, s):
    codes = {_load(_sp(m, s, st)).get("_code") for st in STAGES}             # B-120 D: one code for all stages
    if len(codes) > 1 or None in codes:
        raise SystemExit(f"overlaps m{m} s{s}: stages made with different or unknown code {sorted(codes, key=str)}; "
                         "rerun them")
    out = {"mult": m, "seed": s, "no_margin": {}, "with_margin": {}}
    for name in SETS:
        o = _load(_sp(m, s, f"nav_{name}"))
        out["no_margin"][name] = {k: o[k] for k in ("overlaps", "b2b", "violations")}
    for lab in MARGINS:
        out["with_margin"][lab] = {k: v for k, v in _load(_sp(m, s, f"mnav_{lab}")).items() if k != "_code"}
    p50 = os.path.join(E5.CACHE, f"m{m}_s{s}.pkl.gz")
    if os.path.isfile(p50):
        c = _load(p50)
        out["e50_reproduced"] = (all(c["nav"][n]["violations_no_margin"]["violations"] == out["no_margin"][n]["violations"]
                                     for n in SETS)
                                 and all(c["margin"][lab]["violations"]["violations"] == out["with_margin"][lab]["violations"]
                                         for lab in MARGINS))
    out["peak_mb"] = _peak_mb()
    out["code"] = codes.pop()
    with open(_cell(m, s) + ".tmp", "w") as f:
        json.dump(out, f)
    os.replace(_cell(m, s) + ".tmp", _cell(m, s))
    for st in STAGES:
        try:
            os.remove(_sp(m, s, st))
        except OSError:
            pass
    try:
        os.rmdir(os.path.dirname(_sp(m, s, "rec")))
    except OSError:
        pass
    return out


def _seeds(x):
    lo, hi = (x.split("-") + [x])[:2]
    return list(range(int(lo), int(hi) + 1))


def cmd_run(m, seeds, max_s):
    t0 = time.time()
    est = {"rec": 6.0, "nav": 15.0}
    scale = {1: 1.0, 4: 12.0, 8: 60.0}.get(m, 10.0 * m)
    for s in seeds:
        if os.path.isfile(_cell(m, s)):
            continue
        for st in STAGES:
            if os.path.isfile(_sp(m, s, st)):
                continue
            kind = "rec" if st in ("rec",) or st.startswith("mrec") else "nav"
            need = est[kind] * scale * 1.3
            if time.time() - t0 + need > max_s:
                print(f"stop before m{m} s{s} {st}: time budget (needs ~{need:.0f} s)", flush=True)
                return
            ts = time.time()
            _dump(_sp(m, s, st), run_stage(m, s, st))
            dt = time.time() - ts
            est[kind] = max(est[kind] * 0.5, dt / scale)
            print(f"m{m} s{s} {st}: {dt:.0f} s", flush=True)
        out = assemble(m, s)
        print(f"m{m} s{s} assembled: overlaps no margin "
              + ", ".join(f"{n} {len(v['overlaps'])}" for n, v in out["no_margin"].items())
              + "; with margin " + ", ".join(f"{n} {len(v['overlaps'])}" for n, v in out["with_margin"].items())
              + f"; repro {out.get('e50_reproduced')}, peak {out['peak_mb']} MB", flush=True)
    print("all requested cells done", flush=True)


def _dist(x):
    x = np.asarray(x, float)
    if not len(x):
        return {"n": 0}
    return {"n": int(len(x)), "median": float(np.median(x)), "p95": float(np.quantile(x, 0.95)), "max": float(x.max())}


def cmd_build():
    cells = [json.load(open(p)) for p in glob.glob(os.path.join(CACHE, "m*_s*.json"))]
    if not cells:
        raise SystemExit("no overlaps cells")
    import e50_build as EB
    code = EB.require_code((c.get("code") for c in cells), "overlaps")       # B-120 D
    doc = {"task": "B-102 (P2 M2; decisions B5)", "note": __doc__.strip().split("\n\n")[1].replace("\n", " "),
           "code": code, "multiples": {}}
    rows = []
    for m in sorted({c["mult"] for c in cells}):
        C = sorted((c for c in cells if c["mult"] == m), key=lambda c: c["seed"])
        blk = {"seeds": [c["seed"] for c in C], "e50_reproduced_all": all(c.get("e50_reproduced") for c in C),
               "peak_mb_max": max((c["peak_mb"] or 0) for c in C), "runs": {}}
        for cond, sets in (("no_margin", list(SETS)), ("with_margin", list(MARGINS))):
            for name in sets:
                O = [o for c in C for o in c[cond][name]["overlaps"]]
                B = [b for c in C for b in c[cond][name]["b2b"]]
                dur = [o["dur_s"] for o in O]
                gap = [o["gap_m"] for o in O]
                abut = [b for b in B if abs(b[0]) < 1.0]
                sep = [b for b in B if b[0] >= 1.0]
                nom_ov = [b for b in B if b[0] <= -1.0]  # B-118 N20: nominal windows overlapping by >= 1 s (in neither group)
                if nom_ov:
                    print(f"m{m} {cond}:{name}: {len(nom_ov)} consecutive pairs overlap nominally by >= 1 s", flush=True)
                r = {"overlaps_per_seed": len(O) / len(C), "violations_per_seed_e50": float(np.mean([c[cond][name]["violations"] for c in C])),
                     "duration_s": _dist(dur), "gap_at_entry_m": _dist(gap),
                     "nominal_gap_s": _dist([o["nominal_gap_s"] for o in O]),
                     "counts_per_seed": {"dur_over_1s": sum(d > 1 for d in dur) / len(C), "dur_over_10s": sum(d > 10 for d in dur) / len(C),
                                         "dur_over_60s": sum(d > 60 for d in dur) / len(C),
                                         "gap_under_d0_5m": sum(o["gap_m"] < o["d0_m"] for o in O) / len(C),
                                         "gap_under_r1_dmin": sum(o["gap_m"] < o["r1_dmin_m"] for o in O) / len(C)},
                     "r1_dmin_m": _dist([o["r1_dmin_m"] for o in O]), "head_on_share": float(np.mean([o["head_on"] for o in O])) if O else None,
                     "back_to_back": {"consecutive_conflicting_pairs_per_seed": len(B) / len(C),
                                      "abutting_pairs_per_seed": len(abut) / len(C),
                                      "abutting_share_overlapping": float(np.mean([b[1] for b in abut])) if abut else None,
                                      "separated_pairs_per_seed": len(sep) / len(C),
                                      "separated_share_overlapping": float(np.mean([b[1] for b in sep])) if sep else None,
                                      "separated_nominal_gap_s": _dist([b[0] for b in sep]),
                                      "nominally_overlapping_pairs": len(nom_ov)}}
                blk["runs"][f"{cond}:{name}"] = r
                rows.append({"mult": m, "condition": cond, "layer_set": name, "overlaps_per_seed": round(r["overlaps_per_seed"], 3),
                             "dur_median_s": r["duration_s"].get("median"), "dur_p95_s": r["duration_s"].get("p95"),
                             "dur_max_s": r["duration_s"].get("max"), "gap_median_m": r["gap_at_entry_m"].get("median"),
                             "gap_p95_m": r["gap_at_entry_m"].get("p95"), "gap_max_m": r["gap_at_entry_m"].get("max"),
                             **{k: round(v, 3) for k, v in r["counts_per_seed"].items()},
                             "abutting_share_overlapping": r["back_to_back"]["abutting_share_overlapping"],
                             "separated_share_overlapping": r["back_to_back"]["separated_share_overlapping"]})
        doc["multiples"][str(m)] = blk
    import e50_build as EB
    EB.keep_superseded(OUT_JSON, doc, E5.DESIGN["multiples"], doc["multiples"])
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, allow_nan=False)
        f.write("\n")
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for r in rows:
        print(r)


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
