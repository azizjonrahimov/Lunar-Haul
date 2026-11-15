"""B-99: site data for /protocol/ and /network/ (one small JSON per figure, sizes and sha256 in an index, as B-80).

    python tools/atc/export_protocol.py          # -> data/atc/protocol/*.json + index.json

Files (format "lunarsim-protocol-data" v1):
  e50_layers.json     positioning error and 95 % bound per layer set, the busiest 24 h of the most-driving vehicle of
                      E50's 1x seed 1 at 2 min steps, with the month's p95 per layer (results/E50_summary.json)
  e53_bitrate.json    bit rates: per rover and on the busiest link, auth on / off, 0.1 / 1 / 10 Hz, 5-80 rovers,
                      fleet and spread geometry (results/E53_table.csv), with the 16 kbit/s and 1 Mbit/s lines
  e54_timeline.json   one month (seed 1, loss 0.25, 14-day blackout) message by message: awards, grants and task
                      states with creation and delivery hour under drop_retry / sf / sf_ll, and each vehicle's hourly
                      link to the base with and without the lost-link return
  e55_detectors.json  detector curves on B-96's test streams: event recall against false alarms per pair-day as the
                      threshold sweeps, for the LRIP 3-of-5 rule and the single chi-square test, with E56's operating
                      points (chi-square, CUSUM, network at 1 per pair-day) and the W-MSR consensus table
  b96_landscape.json  B-96's loss landscape (PCA plane of the training path, the path, a random slice, the
                      interpolation line), copied unchanged from data/atc/integrity/landscape.json (LEAD's agent)
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import os
import pickle
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, HERE, os.path.join(ROOT, "experiments", "phase5")):
    if p not in sys.path:
        sys.path.insert(0, p)
OUT = os.path.join(ROOT, "data", "atc", "protocol")
FORMAT = "lunarsim-protocol-data"


def _write(name, doc):
    os.makedirs(OUT, exist_ok=True)
    raw = json.dumps(dict({"format": FORMAT, "version": 1}, **doc), separators=(",", ":"), allow_nan=False).encode()
    with open(os.path.join(OUT, name), "wb") as f:
        f.write(raw + b"\n")
    return name


def e50():
    tr = pickle.load(gzip.open(os.path.join(ROOT, ".cache", "atc", "e50", "trace_m1_s1.pkl.gz")))
    ds = np.asarray(tr["ds"])
    n = int(np.argmax((ds > 0).sum(axis=0)))
    drive = (ds[:, n] > 0).astype(float)
    win = 24 * 60
    c = np.convolve(drive, np.ones(win), "valid")
    k0 = int(np.argmax(c))
    step = 2
    sl = slice(k0, k0 + win, step)
    t_h = np.asarray(tr["t_h"])[sl]
    xy = np.asarray(tr["xy"])[sl, n]
    sets = {}
    for ls, (err, b95) in tr["sets"].items():
        if ls == "dr+ranging+fixes+lans":
            continue                                          # identical to dr+ranging+fixes in 2028 (no LANS)
        sets[ls] = {"err_m": [round(float(x), 2) for x in np.asarray(err)[sl, n]],
                    "b95_m": [round(float(x), 2) for x in np.asarray(b95)[sl, n]]}
    summ = json.load(open(os.path.join(ROOT, "results", "E50_summary.json")))
    month = {ls: {"p95_m": v["all"]["p95_m"]["mean"], "median_m": v["all"]["median_m"]["mean"],
                  "share_b95_over_budget": v["all"]["share_b95_over_budget"]["mean"]}
             for ls, v in summ["errors"]["1"].items() if ls != "dr+ranging+fixes+lans"}
    return _write("e50_layers.json", {
        "experiment": "E50 (B-90), 1x, seed 1", "vehicle": int(tr["ids"][n]), "budget_m": 5.0,
        "t0_h": round(float(t_h[0]), 4), "step_min": step, "t_h": [round(float(x - t_h[0]), 4) for x in t_h],
        "moving": [int(x) for x in (ds[sl, n] > 0)], "xy_m": [[int(round(a)), int(round(b))] for a, b in xy],
        "sets": sets, "set_labels": {"dr": "dead reckoning", "dr+ranging": "+ ranging", "dr+ranging+fixes":
                                     "+ terrain fixes (LANS has no fix in 2028)", "lans@2030": "+ LANS as in 2030"},
        "month_1x_30_seeds": month})


def e53():
    rows = list(csv.DictReader(open(os.path.join(ROOT, "results", "E53_table.csv"))))
    cols = ["geometry", "auth", "position_hz", "rovers", "per_rover_kbps", "busiest_link_kbps_mean",
            "busiest_link_kbps_p95", "mean_hops_to_base", "reachable_share"]
    data = []
    for r in rows:
        data.append([r["geometry"], r["auth"], float(r["position_hz"]), int(r["rovers"]), float(r["per_rover_kbps"]),
                     float(r["busiest_link_kbps_mean"]), float(r["busiest_link_kbps_p95"]),
                     float(r["mean_hops_to_base"]), float(r["reachable_share"])])
    j = json.load(open(os.path.join(ROOT, "results", "E53_bitrate.json")))
    return _write("e53_bitrate.json", {"experiment": "E53 (B-93)", "columns": cols, "rows": data,
                                       "lines_kbps": {"narrow-band (Phase 5 target)": 16.0, "broadband": 1000.0},
                                       "eta": j["eta"], "h13": j["h13"],
                                       "sizes_bytes": {k: v["default"] for k, v in j["sizes"].items()}})


def e54():
    import run_e50 as E5
    import run_e54 as E4
    from lunarsim.atc import dtn as DT
    month, t0h, t1h, share = E5._window()
    rec = E4.record(1, t0h, t1h)
    tr = E5.trajectories(rec, t0h, t1h)
    g = E5._geo()
    A = DT.contact_plan(tr, g["los"], g["ids"]["BASE"])
    A_ll, _ = DT.lost_link_plan(A, tr)
    N = A.shape[1] - 1
    vid_col = {int(v): n for n, v in enumerate(tr.ids)}
    eu = E4.earth_up_fn(t0h, t1h, tr.dt_s)
    msgs = [m for m in E4.messages(rec, t0h, t1h, N, vid_col) if m.kind != "ledger_earth"]
    out = {}
    for proto in ("drop_retry", "sf", "sf_ll"):
        res = DT.simulate(A_ll if proto == "sf_ll" else A, msgs, "drop_retry" if proto == "drop_retry" else "sf", 0.25,
                          np.random.default_rng([1, 94, 25, ("drop_retry", "sf", "sf_ll").index(proto)]), tr.dt_s,
                          earth_up=lambda k: bool(eu[min(k, len(eu) - 1)]))
        out[proto] = [None if m.t_done is None else round(m.t_done / 3600.0, 3) for m in res]
    per_h = int(round(3600.0 / tr.dt_s))
    hb, hb_ll = DT.base_hops(A), DT.base_hops(A_ll)
    T = (len(hb) // per_h) * per_h
    link = (hb[:T] >= 0).reshape(-1, per_h, N).mean(axis=1)
    link_ll = (hb_ll[:T] >= 0).reshape(-1, per_h, N).mean(axis=1)
    return _write("e54_timeline.json", {
        "experiment": "E54 (B-94), seed 1, loss 0.25, 14-day Earth blackout (days 8-22)", "t0_h": t0h,
        "messages": {"kind": [m.kind for m in msgs], "dst": [m.dst for m in msgs], "src": [m.src for m in msgs],
                     "t_created_h": [round(m.t0 / 3600.0, 3) for m in msgs], "life_h": [round(m.life_s / 3600.0, 4) for m in msgs],
                     "delivered_h": out, "note": "dst / src: vehicle column, -1 = base; delivered_h null = lost (expired)"},
        "vehicles": [int(v) for v in tr.ids],
        "link_share_per_hour": {"plain": [[round(float(x), 3) for x in row] for row in link],
                                "lost_link_return": [[round(float(x), 3) for x in row] for row in link_ll]},
        "earth_up_per_hour": [round(float(x), 3) for x in eu[:T].reshape(-1, per_h).mean(axis=1)]})


def e55():
    from lunarsim.atc import integrity as I
    from lunarsim.nn import baselines as B, dataset as D
    d = D.load("test")
    w = d["mn"][:, D.META.index("weight")]
    kinds = d["mf"][:, D.META.index("kind")].astype(int)
    curves = {}
    for rule in ("3of5", "single"):
        pts = []
        for gamma in (4.0, 6.63, 8.0, 10.83, 13.0, 15.14, 19.5, 25.0, 35.0, 50.0):
            if rule == "3of5":
                sf, sn, thr = I.lrip_rule_score(d["Xf"], gamma), I.lrip_rule_score(d["Xn"], gamma), 2.5
            else:
                sf, sn, thr = B.chi2_step(d["Xf"]), B.chi2_step(d["Xn"]), gamma
            fa = B.fa_per_day(B.bin_max(sn), w, thr)
            found, delay, _ = B.detect(sf, d["mf"], thr)
            sel = kinds > 0
            pts.append([gamma, round(fa, 4), round(float(found[sel].mean()), 4),
                        round(float(np.nanmedian(delay[sel & found])), 1) if (sel & found).any() else None])
            del sf, sn
        curves[rule] = pts
    del d
    e56 = json.load(open(os.path.join(ROOT, "results", "E56_integrity.json")))
    ops = {det: {"fa_per_pair_day": e56["test"][det]["day"]["fa_per_pair_day"]["mean"],
                 "recall": e56["test"][det]["day"]["events"]["all"]["recall"]["mean"]
                 if isinstance(e56["test"][det]["day"]["events"]["all"]["recall"], dict)
                 else e56["test"][det]["day"]["events"]["all"]["recall"]} for det in ("chi2_step", "cusum", "net")}
    e55 = json.load(open(os.path.join(ROOT, "results", "E55_integrity.json")))
    cons = [{k: c[k] for k in ("geometry", "N", "f", "F", "safe_share", "agreement_share", "degree_condition_share")}
            for c in e55["consensus"]["cells"]]
    return _write("e55_detectors.json", {
        "experiment": "E55 (B-95) on B-96's test streams; E56 operating points",
        "curve_columns": ["gamma", "false_alarms_per_pair_day", "event_recall_all", "median_delay_s"],
        "curves": curves, "e56_at_1_per_pair_day": ops, "consensus": cons,
        "auth": {"forgery_8bit": e55["auth"]["forgery"]["8"], "forgery_16bit": e55["auth"]["forgery"]["16"]}})


def b96():
    src = os.path.join(ROOT, "data", "atc", "integrity", "landscape.json")
    doc = json.load(open(src))
    return _write("b96_landscape.json", {"source": "data/atc/integrity/landscape.json (B-96, LEAD's agent), unchanged",
                                         "source_sha256": hashlib.sha256(open(src, "rb").read()).hexdigest(),
                                         "landscape": doc})


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return None


def main():
    t0 = time.time()
    names = [e50(), e53(), e54(), e55(), b96()]
    idx = {"format": FORMAT + "-index", "version": 1, "commit": _commit(), "files": {}}
    for n in names:
        p = os.path.join(OUT, n)
        b = open(p, "rb").read()
        idx["files"][n] = {"bytes": len(b), "bytes_gzip": len(gzip.compress(b, 9, mtime=0)),
                           "sha256": hashlib.sha256(b).hexdigest()}
    with open(os.path.join(OUT, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(idx, f, indent=1)
        f.write("\n")
    print(json.dumps({k: (v["bytes"], v["bytes_gzip"]) for k, v in idx["files"].items()}), round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(560, exit=True)
    main()
