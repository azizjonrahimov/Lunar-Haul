"""B-63: later years. Does the 2028 dark spell recur? Earth links 2032-2050 with the B-40 setup (R-1 follow-up).

    python tools/comms/later_years.py ephem3                  # SPICE: Earth seen from BASE, 2032-2050, 10 min
    python tools/comms/later_years.py link3 --part 0 --parts 4  # link windows of every point of points.json (chunks)
    python tools/comms/later_years.py assemble3               # -> data/comms/connecting_ridge/earth_link-v3.json and
                                                              #    earth_link-v3-samples.json.gz (2032-2050)
    python tools/comms/later_years.py parking3                # -> parking-v3.json: parking-v1's points, v3 windows
    python tools/comms/later_years.py back188                 # #188 alone, 2025-2027: when did the 2028 spell begin?
    python tools/comms/later_years.py predict                 # -> results/E21_later_years.json (+ _samples.csv)
    python tools/comms/later_years.py join                    # B-64: v1 then v3 as one cached link file (not committed)

Same geometry, kernels, masks and arithmetic as earth_link.py (the v1 files, 2028-2031, are unchanged); only the
epochs differ: 2032-01-01 00:00 UTC to 2050-12-31 23:50 UTC (LEAD: 2032-2050 plus four years, so that
the spell from November 2043 ends inside the file). Every step is single process with --max-seconds 540.
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p_ in (ROOT, HERE):
    if p_ not in sys.path:
        sys.path.insert(0, p_)

import earth_link as EL  # noqa: E402
from lunarsim import comms as C  # noqa: E402

CACHE = EL.CACHE
START3_UTC = "2032-01-01 00:00"
END3_UTC = "2051-01-01 00:00"      # exclusive
YEARS3 = tuple(range(2032, 2051))
EPHEM3 = os.path.join(CACHE, "ephem3.npz")
EPHEM3_INFO = os.path.join(CACHE, "ephem3.json")
DATA = os.path.join(ROOT, "data", "comms", "connecting_ridge")
OUT3 = os.path.join(DATA, "earth_link-v3.json")
SAMPLES3 = os.path.join(DATA, "earth_link-v3-samples.json.gz")


def n_epochs3() -> int:
    import datetime as dt
    days = (dt.date(2051, 1, 1) - dt.date(2032, 1, 1)).days
    return days * 24 * 60 // EL.STEP_MIN


# ---------------------------------------------------------------------------------------------------------
def step_ephem3(log=print) -> Dict[str, Any]:
    """Earth from BASE (the v1 observer, ephem.npz), SPICE spkcpo LT+S in MOON_ME, every 10 min; the azlcpo check;
    Earth's grid bearing against the masks' wedge."""
    t0 = time.time()
    kern = EL.fetch_kernels()
    sp = EL.furnsh_all()
    e1 = np.load(EL.ephem_path())
    P_base = e1["P_base_km"]
    lat, lon = (float(v) for v in e1["base_latlon"])
    n = n_epochs3()
    et0 = sp.str2et(START3_UTC + " UTC")
    ets = et0 + 60.0 * EL.STEP_MIN * np.arange(n)
    E = np.empty((n, 3))
    for i, et in enumerate(ets):
        st, _ = sp.spkcpo("EARTH", float(et), "MOON_ME", "OBSERVER", "LT+S", P_base, "MOON", "MOON_ME")
        E[i] = st[:3]
    az, el, brg, rad = EL.earth_topo(E, P_base, P_base, lat, lon)
    idx = np.arange(0, n, 97)
    d_az, d_el = [], []
    for i in idx:
        st, _ = sp.azlcpo("ELLIPSOID", "EARTH", float(ets[i]), "LT+S", False, True, P_base, "MOON", "MOON_ME")
        d_az.append(abs(EL.wrap180(math.degrees(st[1]) - az[i])))
        d_el.append(abs(math.degrees(st[2]) - el[i]))
    bearings, b0 = EL.wedge_bearings()
    np.savez(EPHEM3, et=ets, E_base_km=E, P_base_km=P_base)
    info = {"n": int(n), "start_utc": START3_UTC, "end_utc_exclusive": END3_UTC,
            "bearing_range_deg": [float(brg.min()), float(brg.max())],
            "el_range_deg": [float(el.min()), float(el.max())],
            "mask_wedge_deg": [float(bearings[0]), float(bearings[-1])],
            "inside_wedge": bool(brg.min() >= bearings[0] and brg.max() <= bearings[-1]),
            "azlcpo_check": {"epochs": int(len(idx)), "max_abs_az_deg": float(max(d_az)), "max_abs_el_deg": float(max(d_el))},
            "kernels": kern, "seconds": round(time.time() - t0, 1)}
    with open(EPHEM3_INFO, "w") as f:
        json.dump(info, f, indent=1)
    log(f"ephem3: {n} epochs; Earth grid bearing {info['bearing_range_deg'][0]:.2f} to {info['bearing_range_deg'][1]:.2f} "
        f"deg (wedge {bearings[0]:.1f} to {bearings[-1]:.1f}: {'inside' if info['inside_wedge'] else 'OUTSIDE'}), "
        f"elevation {el.min():.2f} to {el.max():.2f} deg; azlcpo max |d az| {max(d_az):.1e}, |d el| {max(d_el):.1e} "
        f"({time.time() - t0:.0f} s)")
    return info


def step_link3(part: int = 0, parts: int = 1, log=print) -> None:
    """10-min and hourly window codes (every criterion) of one chunk of the points of points.json, 2032-2050."""
    t0 = time.time()
    meta, _ = EL.load_pack()
    pts = json.load(open(os.path.join(CACHE, "points.json")))["points"]
    M, bearings = EL.load_masks()
    e = np.load(EPHEM3)
    E, P_base = e["E_base_km"], e["P_base_km"]
    n, k_h = len(E), EL.SAMPLE_STEP_MIN // EL.STEP_MIN
    x0, y0 = meta["origin_xy_m"]
    sel = np.array_split(np.arange(len(pts)), parts)[part]
    out: Dict[str, Any] = {}
    for j, i in enumerate(sel.tolist()):
        s = EL.point_link(pts[i], M[i], E, P_base, x0, y0, bearings, i)
        out[str(i)] = {"w10": [C.encode_windows(C.runs(s[c])) for c in C.CRITERIA],
                       "w60": [C.encode_windows(C.runs(s[c][: n - n % k_h].reshape(-1, k_h).all(axis=1)))
                               for c in C.CRITERIA]}
        if (j + 1) % 200 == 0:
            log(f"link3 part {part}/{parts}: {j + 1}/{len(sel)} points ({time.time() - t0:.0f} s)")
    with open(os.path.join(CACHE, f"link3_{part:02d}of{parts:02d}.json"), "w") as f:
        json.dump(out, f)
    log(f"link3 part {part}/{parts}: {len(sel)} points in {time.time() - t0:.0f} s")


def load_link3(n_points: int) -> Dict[str, Any]:
    files = sorted(f for f in os.listdir(CACHE) if f.startswith("link3_") and f.endswith(".json"))
    if len({int(f.split("of")[1][:2]) for f in files}) > 1:
        raise SystemExit(f"link3 files from different --parts runs: {files}; delete the stale ones")
    got: Dict[str, Any] = {}
    for f in files:
        got.update(json.load(open(os.path.join(CACHE, f))))
    if len(got) != n_points:
        raise SystemExit(f"{n_points - len(got)} points have no windows; run the missing `link3 --part` chunks")
    return got


def step_assemble3(recheck: int = 12, log=print) -> Dict[str, Any]:
    """earth_link-v3.json (points, legs, mast; 10 min) and earth_link-v3-samples.json.gz (hourly), the v1 formats
    over 2032-2050. Sample order, legs and mast line of sight are those of the v1 samples file."""
    t0 = time.time()
    meta, _ = EL.load_pack()
    pdoc = json.load(open(os.path.join(CACHE, "points.json")))
    pts, leg_pts = pdoc["points"], pdoc["legs"]
    got = load_link3(len(pts))
    v1 = json.load(open(EL.OUT))
    v1s = json.loads(gzip.decompress(open(EL.SAMPLES_V1, "rb").read()))
    info = json.load(open(EPHEM3_INFO))
    if not info["inside_wedge"]:
        raise SystemExit("Earth leaves the masks' wedge in 2032-2050; extend the masks first")
    n = int(info["n"])
    k_h = EL.SAMPLE_STEP_MIN // EL.STEP_MIN
    step_h = EL.STEP_MIN / 60.0
    mast_i = next(i for i, p in enumerate(pts) if p["id"] == "BASE_MAST")
    dec = lambda code: C.windows_to_mask(C.decode_windows(code), n)
    mast = {c: dec(got[str(mast_i)]["w10"][k]) for k, c in enumerate(C.CRITERIA)}
    used = sorted({k for ids in leg_pts.values() for k in ids})
    if len(used) != len(v1s["samples"]):
        raise SystemExit("points.json does not match the v1 samples file")
    los = {i: bool(v1s["samples"][j]["mast_los"]) for j, i in enumerate(used)}

    def pack(direct, with_mast):
        enc = lambda m: C.encode_windows(C.runs(m))
        return ({"dte": {c: enc(direct[c]) for c in C.CRITERIA}, "dte+mast": {c: enc(with_mast[c]) for c in C.CRITERIA}},
                {"dte": {c: C.summarize(C.runs(direct[c]), n, step_h) for c in C.CRITERIA},
                 "dte+mast": {c: C.summarize(C.runs(with_mast[c]), n, step_h) for c in C.CRITERIA}})

    points_out = {}
    for name, e1 in v1["points"].items():
        i = next(k for k, p in enumerate(pts) if p["id"] == name)
        d = {c: dec(got[str(i)]["w10"][k]) for k, c in enumerate(C.CRITERIA)}
        w, summ = pack(d, {c: d[c] | (e1["mast_los"] & mast[c]) for c in C.CRITERIA})
        points_out[name] = dict(e1, windows=w, summary=summ)
    legs_out = {}
    for name, ids in leg_pts.items():
        if not ids:
            legs_out[name] = {"route": None}
            continue
        acc = {c: np.ones(n, dtype=bool) for c in C.CRITERIA}
        accm = {c: np.ones(n, dtype=bool) for c in C.CRITERIA}
        for i in ids:
            for k, c in enumerate(C.CRITERIA):
                m_ = dec(got[str(i)]["w10"][k])
                acc[c] &= m_
                accm[c] &= m_ | ((los.get(i) if pts[i]["kind"] == "route" else _site_los(v1, pts[i])) & mast[c])
        w, summ = pack(acc, accm)
        legs_out[name] = dict(v1["legs"][name], windows=w, summary=summ)
    series_ix: Dict[tuple, int] = {}
    series_list: List[List[int]] = []

    def sid(code):
        key = tuple(code)
        if key not in series_ix:
            series_ix[key] = len(series_list)
            series_list.append(list(code))
        return series_ix[key]

    sdoc = {"format": C.EARTH_LINK_SAMPLES_FORMAT, "version": 1, "terrain": meta["site_id"],
            "time": {"start_utc": START3_UTC, "step_min": EL.SAMPLE_STEP_MIN, "n": int(n // k_h)},
            "criteria": list(C.CRITERIA),
            "samples": [{"xy_m": s["xy_m"], "id": s["id"], "mast_los": s["mast_los"],
                         "w": [sid(c) for c in got[str(used[j])]["w60"]]} for j, s in enumerate(v1s["samples"])],
            "series": series_list, "legs": v1s["legs"],
            "note": "B-63: the v1 samples file's samples, order and legs over 2032-01-01 .. 2050-12-31 (hourly; an hour "
                    "is linked only when all six 10-min epochs are); the engine reads it only through link_series "
                    "earth_link-v3.json"}
    # determinism: a few v1-span recomputations would need the v1 ephemeris; instead recheck v3 hourly = all(10-min)
    rng = np.random.default_rng(63)
    for j in rng.choice(len(used), size=recheck, replace=False).tolist():
        i = used[j]
        for k in range(len(C.CRITERIA)):
            m10 = dec(got[str(i)]["w10"][k])
            if C.encode_windows(C.runs(m10[: n - n % k_h].reshape(-1, k_h).all(axis=1))) != got[str(i)]["w60"][k]:
                raise SystemExit(f"point {i}: hourly windows do not match its 10-min windows")
    os.makedirs(DATA, exist_ok=True)
    with open(SAMPLES3, "wb") as f:
        f.write(gzip.compress(json.dumps(sdoc, separators=(",", ":")).encode("utf-8"), 9, mtime=0))
    doc = {k: v for k, v in v1.items() if k not in ("points", "legs", "mast", "time", "samples_file", "generated", "earth")}
    doc.update({
        "time": {"start_utc": START3_UTC, "step_min": EL.STEP_MIN, "n": n, "scale": "UTC", "end_utc_exclusive": END3_UTC},
        "earth": {"grid_bearing_range_deg_at_BASE": info["bearing_range_deg"], "elevation_range_deg_at_BASE": info["el_range_deg"],
                  "mask_wedge_deg": v1["earth"]["mask_wedge_deg"]},
        "mast": dict(v1["mast"], windows={c: C.encode_windows(C.runs(mast[c])) for c in C.CRITERIA},
                     summary={c: C.summarize(C.runs(mast[c]), n, step_h) for c in C.CRITERIA}),
        "points": points_out, "legs": legs_out,
        "samples_file": {"file": os.path.basename(SAMPLES3), "sha256": EL.sha256(SAMPLES3),
                         "n_samples": len(sdoc["samples"]), "n_series": len(series_list)},
        "span": "B-63: 2032-01-01 .. 2050-12-31 (v1: 2028-2031); same masks, sites, routes and arithmetic",
        "generated": {"tool": "tools/comms/later_years.py ephem3 / link3 / assemble3"},
    })
    doc["provenance"] = dict(v1["provenance"], kernels=info["kernels"], spice_conversion_check=info["azlcpo_check"])
    errs = C.validate(doc) + C.validate_samples(sdoc)
    if errs:
        raise SystemExit(f"v3 files fail validation: {errs[:3]}")
    with open(OUT3, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    with open(OUT3 + ".sha256", "w") as f:
        f.write(f"{EL.sha256(OUT3)}  {os.path.basename(OUT3)}\n")
    log(f"assemble3: {len(points_out)} points, {len(legs_out)} legs, {len(sdoc['samples'])} samples, {len(series_list)} "
        f"series -> {EL._rel(OUT3)} ({os.path.getsize(OUT3) // 1024} KB), {EL._rel(SAMPLES3)} "
        f"({os.path.getsize(SAMPLES3) // 1024} KB) ({time.time() - t0:.0f} s)")
    return doc


def _site_los(v1: Dict[str, Any], p: Dict[str, Any]) -> bool:
    return bool(v1["points"][p["id"]]["mast_los"])


JOINED_DIR = os.path.join(CACHE, "joined")
JOINED = os.path.join(JOINED_DIR, "earth_link-joined.json")
JOINED_SAMPLES = os.path.join(JOINED_DIR, "earth_link-joined-samples.json.gz")
JOINED_PARKING = os.path.join(JOINED_DIR, "parking-joined.json")


def join_windows(w1: np.ndarray, n1: int, w3: np.ndarray) -> np.ndarray:
    """Windows of a series that runs on: v1's (inside [0, n1)) then v3's shifted by n1; a window ending at n1 and one
    starting at 0 of v3 become one."""
    w1 = np.asarray(w1, dtype=np.int64).reshape(-1, 2)
    w3 = np.asarray(w3, dtype=np.int64).reshape(-1, 2) + n1
    if len(w1) and len(w3) and w1[-1, 1] == n1 and w3[0, 0] == n1:
        w1 = w1.copy()
        w1[-1, 1] = w3[0, 1]
        w3 = w3[1:]
    return np.concatenate([w1, w3]) if len(w3) else w1


def step_join(log=print) -> Dict[str, Any]:
    """B-64: a cached (not committed) link file, samples file and parking file that run 2028-01-01 .. 2050-12-31: the
    v1 windows, then the v3 windows. Inside 2028-2031 every window is v1's; only look-ups past 2031 differ."""
    sys.path.insert(0, HERE)
    import parking as PK
    t0 = time.time()
    v1, v3 = json.load(open(EL.OUT)), json.load(open(OUT3))
    s1 = json.loads(gzip.decompress(open(EL.SAMPLES_V1, "rb").read()))
    s3 = json.loads(gzip.decompress(open(SAMPLES3, "rb").read()))
    n1, n3 = int(v1["time"]["n"]), int(v3["time"]["n"])
    h1, h3 = int(s1["time"]["n"]), int(s3["time"]["n"])
    step_h = EL.STEP_MIN / 60.0
    enc = C.encode_windows
    dec = C.decode_windows

    def jn(c1, c3, n):
        w = join_windows(dec(c1), n, dec(c3))
        return enc(w), w

    def entry(e1, e3):
        e = dict(e1)
        if "windows" not in e1:
            return e
        e["windows"], e["summary"] = {}, {}
        for mode in e1["windows"]:
            e["windows"][mode], e["summary"][mode] = {}, {}
            for c in C.CRITERIA:
                code, w = jn(e1["windows"][mode][c], e3["windows"][mode][c], n1)
                e["windows"][mode][c] = code
                e["summary"][mode][c] = C.summarize(w, n1 + n3, step_h)
        return e

    series_ix: Dict[tuple, int] = {}
    series_list: List[List[int]] = []

    def sid(code):
        key = tuple(code)
        if key not in series_ix:
            series_ix[key] = len(series_list)
            series_list.append(list(code))
        return series_ix[key]

    samples = []
    for a, b in zip(s1["samples"], s3["samples"]):
        if a["xy_m"] != b["xy_m"]:
            raise SystemExit("v1 and v3 samples differ")
        samples.append(dict(a, w=[sid(jn(s1["series"][i], s3["series"][j], h1)[0]) for i, j in zip(a["w"], b["w"])]))
    sdoc = dict(s1, time={"start_utc": s1["time"]["start_utc"], "step_min": s1["time"]["step_min"], "n": h1 + h3},
                samples=samples, series=series_list,
                note="B-64 (cache only, not committed): earth_link-v1-samples then earth_link-v3-samples, 2028-01-01 .. "
                     "2050-12-31; windows that meet at 2032-01-01 are joined")
    os.makedirs(JOINED_DIR, exist_ok=True)
    with open(JOINED_SAMPLES, "wb") as f:
        f.write(gzip.compress(json.dumps(sdoc, separators=(",", ":")).encode("utf-8"), 9, mtime=0))
    doc = dict(v1, time=dict(v1["time"], n=n1 + n3, end_utc_exclusive=v3["time"]["end_utc_exclusive"]),
               points={k: entry(e, v3["points"][k]) for k, e in v1["points"].items()},
               legs={k: entry(e, v3["legs"][k]) for k, e in v1["legs"].items()},
               samples_file={"file": os.path.basename(JOINED_SAMPLES), "sha256": EL.sha256(JOINED_SAMPLES),
                             "n_samples": len(samples), "n_series": len(series_list)},
               span="B-64 (cache only): earth_link-v1 then earth_link-v3, 2028-01-01 .. 2050-12-31",
               generated={"tool": "tools/comms/later_years.py join"})
    mast = dict(v1["mast"])
    mast["windows"], mast["summary"] = {}, {}
    for c in C.CRITERIA:
        code, w = jn(v1["mast"]["windows"][c], v3["mast"]["windows"][c], n1)
        mast["windows"][c], mast["summary"][c] = code, C.summarize(w, n1 + n3, step_h)
    doc["mast"] = mast
    errs = C.validate(doc) + C.validate_samples(sdoc)
    if errs:
        raise SystemExit(f"joined files fail validation: {errs[:3]}")
    with open(JOINED, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    p1, p3 = json.load(open(PK.OUT, encoding="utf-8")), json.load(open(PARKING3, encoding="utf-8"))
    pts = []
    for a, b in zip(p1["points"], p3["points"]):
        q = dict(a)
        if a["kind"] == "grid":
            q["windows"] = enc(join_windows(dec(a["windows"]), h1, dec(b["windows"])))
        pts.append(q)
    pdoc = dict(p1, points=pts, time={"start_utc": s1["time"]["start_utc"], "step_h": 1, "n": h1 + h3, "wrap": True},
                samples_file={"file": os.path.basename(JOINED_SAMPLES), "sha256": doc["samples_file"]["sha256"],
                              "n_samples": len(samples)},
                generated={"tool": "tools/comms/later_years.py join (B-64, cache only)"})
    with open(JOINED_PARKING, "w", encoding="utf-8") as f:
        json.dump(pdoc, f, separators=(",", ":"))
    out = {"link": {"file": EL._rel(JOINED), "sha256": EL.sha256(JOINED)},
           "samples": {"file": EL._rel(JOINED_SAMPLES), "sha256": doc["samples_file"]["sha256"]},
           "parking": {"file": EL._rel(JOINED_PARKING), "sha256": EL.sha256(JOINED_PARKING)},
           "inputs": {EL._rel(p): EL.sha256(p) for p in (EL.OUT, EL.SAMPLES_V1, OUT3, SAMPLES3, PK.OUT, PARKING3)}}
    log(f"join: {len(samples)} samples, {len(series_list)} series, n {n1 + n3} (10 min) / {h1 + h3} (h) -> "
        f"{EL._rel(JOINED_DIR)} ({time.time() - t0:.0f} s)")
    return out


BACK188 = os.path.join(CACHE, "back188.json")


def step_back188(log=print) -> Dict[str, Any]:
    """#188 alone, 2025-01-01 .. 2027-12-31 (the same observer, kernels, mask and arithmetic): when did the dark spell
    that ends 2029-07-02 begin? Its last link-up before 2028 (hourly, all six 10-min epochs)."""
    t0 = time.time()
    sp = EL.furnsh_all()
    meta, _ = EL.load_pack()
    x0, y0 = meta["origin_xy_m"]
    e1 = np.load(EL.ephem_path())
    P_base = e1["P_base_km"]
    pdoc = json.load(open(os.path.join(CACHE, "points.json")))
    used = sorted({k for ids in pdoc["legs"].values() for k in ids})
    i = used[EL.DARK_SAMPLE]
    M, bearings = EL.load_masks()
    import datetime as dt
    n = (dt.date(2028, 1, 1) - dt.date(2025, 1, 1)).days * 24 * 60 // EL.STEP_MIN
    et0 = sp.str2et("2025-01-01 00:00 UTC")
    E = np.empty((n, 3))
    for k in range(n):
        st, _ = sp.spkcpo("EARTH", float(et0 + 60.0 * EL.STEP_MIN * k), "MOON_ME", "OBSERVER", "LT+S", P_base, "MOON", "MOON_ME")
        E[k] = st[:3]
    k_h = EL.SAMPLE_STEP_MIN // EL.STEP_MIN
    s = EL.point_link(pdoc["points"][i], M[i], E, P_base, x0, y0, bearings, i)["any_part"]
    hourly = s[: n - n % k_h].reshape(-1, k_h).all(axis=1)
    on = np.flatnonzero(hourly)
    last = int(on[-1]) + 1 if len(on) else 0                  # first dark hour after the last link-up
    start = np.datetime64("2025-01-01T00", "h") + np.timedelta64(last, "h")
    out = {"sample": EL.DARK_SAMPLE, "span": "2025-01-01 .. 2027-12-31", "linked_h_by_year":
           {str(2025 + k): int(hourly[sum((365, 366, 365)[:k]) * 24: sum((365, 366, 365)[:k + 1]) * 24].sum()) for k in range(3)},
           "spell_start": str(start)[:13], "dark_at_2028_01_01": bool(not hourly[-1]),
           "seconds": round(time.time() - t0, 1)}
    with open(BACK188, "w") as f:
        json.dump(out, f, indent=1)
    log(f"back188: #188 linked h 2025-2027 {list(out['linked_h_by_year'].values())}; the spell ending 2029-07-02 began "
        f"{out['spell_start']} ({time.time() - t0:.0f} s)")
    return out


PARKING3 = os.path.join(DATA, "parking-v3.json")


def step_parking3(log=print) -> Dict[str, Any]:
    """parking-v3.json for Stage J's helper: parking-v1's points and ranking (from the 2028-2031 tallies), the grid
    points' hourly DTE windows recomputed for 2032-2050 (their B-61 masks), link fractions over 2032-2050."""
    sys.path.insert(0, HERE)
    import parking as PK
    t0 = time.time()
    meta, _ = EL.load_pack()
    x0, y0 = meta["origin_xy_m"]
    with open(PK.OUT, encoding="utf-8") as f:
        doc = json.load(f)
    v3s = json.loads(gzip.decompress(open(SAMPLES3, "rb").read()))
    n3 = int(v3s["time"]["n"])
    gp = np.load(PK.GRID_PRE)
    Mg, bearings = PK.load_grid_masks(len(gp["gxy"]))
    key = {(round(float(x), 2), round(float(y), 2)): g for g, (x, y) in enumerate(gp["gxy"])}
    e = np.load(EPHEM3)
    E, P_base = e["E_base_km"], e["P_base_km"]
    k_h = EL.SAMPLE_STEP_MIN // EL.STEP_MIN
    n = len(E)
    frac = lambda code: (lambda w: float((w[:, 1] - w[:, 0]).sum()) / n3 if len(w) else 0.0)(C.decode_windows(code))
    pts = []
    for p in doc["points"]:
        q = dict(p)
        if p["kind"] == "grid":
            g = key[(round(p["xy_m"][0], 2), round(p["xy_m"][1], 2))]
            s = EL.point_link({"x": p["xy_m"][0], "y": p["xy_m"][1], "z": p["z_m"], "h_ant": PK.ANT_M}, Mg[g], E, P_base,
                              x0, y0, bearings, g)["any_part"]
            q["windows"] = C.encode_windows(C.runs(s[: n - n % k_h].reshape(-1, k_h).all(axis=1)))
            q["link_fraction"] = round(frac(q["windows"]), 5)
        else:
            q["link_fraction"] = round(frac(v3s["series"][v3s["samples"][p["sample"]]["w"][0]]), 5)
        pts.append(q)
    out = dict(doc, points=pts,
               time={"start_utc": START3_UTC, "step_h": 1, "n": n3, "wrap": True},
               samples_file={"file": os.path.basename(SAMPLES3), "sha256": EL.sha256(SAMPLES3), "n_samples": len(v3s["samples"])},
               description="B-63: parking-v1.json for the 2032-2050 link files: the same points and ranking (top[], "
                           "shares and coverage are parking-v1's, from the 2028-2031 tallies and dark hours); the "
                           "points' link_fraction and the grid points' hourly DTE windows are 2032-2050 (earth_link-v3). "
                           + doc["description"],
               derived_from={"file": os.path.basename(PK.OUT), "sha256": EL.sha256(PK.OUT)},
               generated={"tool": "tools/comms/later_years.py parking3"})
    with open(PARKING3, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"))
    log(f"parking3: {sum(p['kind'] == 'grid' for p in pts)} grid points recomputed for 2032-2050 -> {EL._rel(PARKING3)} "
        f"({os.path.getsize(PARKING3) // 1024} KB) ({time.time() - t0:.0f} s)")
    return out


# ---------------------------------------------------------------------------------------------------------
# the prediction: does a 2028-like year come back, and with which period?
# ---------------------------------------------------------------------------------------------------------
PREDICT_OUT = os.path.join(ROOT, "results", "E21_later_years.json")
PREDICT_CSV = os.path.join(ROOT, "results", "E21_later_years_samples.csv")
ALL_YEARS = tuple(range(2028, 2051))
MAIN_PADS = ("PAD_A@1", "PAD_B@1")            # the E21 pad standoff (run_phase4.STANDOFF = 1 km)
BEAT_YR = 5.997                               # the task's ~6-year beat of the anomalistic and draconic months
REGOLITH_LEGS = ("CONSTR->ISRU", "ISRU->CONSTR")


def year_edges_h() -> List[int]:
    """Hour index of 1 January 2028 .. 2051 in the joined hourly series (2028-01-01 00:00 = 0)."""
    import datetime as dt
    return [int((dt.date(y, 1, 1) - dt.date(2028, 1, 1)).days * 24) for y in ALL_YEARS + (2051,)]


def jul1_h(y: int) -> int:
    import datetime as dt
    return int((dt.date(y, 7, 1) - dt.date(2028, 1, 1)).days * 24)


def runs_dark(m: np.ndarray) -> np.ndarray:
    return C.runs(~m)


def sinusoid_fit(t: np.ndarray, y: np.ndarray, periods: np.ndarray) -> Dict[str, Any]:
    """Least-squares y = a + b cos(2 pi t / P) + c sin(2 pi t / P) over a grid of periods: RSS per period, the best."""
    rss = np.empty(len(periods))
    coef = []
    for k, P in enumerate(periods):
        X = np.stack([np.ones_like(t), np.cos(2 * np.pi * t / P), np.sin(2 * np.pi * t / P)], axis=1)
        c, *_ = np.linalg.lstsq(X, y, rcond=None)
        r = y - X @ c
        rss[k] = float(r @ r)
        coef.append(c)
    k = int(np.argmin(rss))
    return {"period": float(periods[k]), "rss": rss, "coef": coef[k], "k": k}


def step_predict(boot: int = 2000, log=print) -> Dict[str, Any]:
    import calendar
    import pandas as pd
    from scipy import stats
    t0 = time.time()
    v1s = json.loads(gzip.decompress(open(EL.SAMPLES_V1, "rb").read()))
    v3s = json.loads(gzip.decompress(open(SAMPLES3, "rb").read()))
    n1, n3 = int(v1s["time"]["n"]), int(v3s["time"]["n"])
    E = year_edges_h()
    if E[4] != n1 or E[-1] != n1 + n3:
        raise SystemExit("the v1 / v3 hourly series do not tile 2028-2050")
    mask = lambda doc, s, n: C.windows_to_mask(C.decode_windows(doc["series"][doc["samples"][s]["w"][0]]), n)
    ny = len(ALL_YEARS)
    N = len(v1s["samples"])
    hours = np.zeros((N, ny), dtype=np.int64)
    dark_jan = np.zeros((N, ny), dtype=np.int64)       # hours from 1 January until the first link of the year
    longest = np.zeros((N, ny), dtype=np.int64)        # longest dark spell inside the year
    span = []                                          # longest dark spell 2028-2050 (start h, length h)
    cont_same = 0
    for s in range(N):
        a, b = mask(v1s, s, n1), mask(v3s, s, n3)
        cont_same += int(a[-1] == b[0])
        m = np.concatenate([a, b])
        for k in range(ny):
            seg = m[E[k]:E[k + 1]]
            hours[s, k] = int(seg.sum())
            f = np.flatnonzero(seg)
            dark_jan[s, k] = int(f[0]) if len(f) else len(seg)
            r = runs_dark(seg)
            longest[s, k] = int((r[:, 1] - r[:, 0]).max()) if len(r) else 0
        r = runs_dark(m)
        j = int(np.argmax(r[:, 1] - r[:, 0])) if len(r) else -1
        span.append((int(r[j, 0]), int(r[j, 1] - r[j, 0])) if j >= 0 else (0, 0))
    never_v1 = hours[:, :4].sum(axis=1) == 0
    never_v3 = hours[:, 4:].sum(axis=1) == 0
    never_all = never_v1 & never_v3
    # main-network legs: between the seven sites and the two 1 km pads
    named = {smp["id"] for smp in v1s["samples"] if smp["id"]}
    nodes = {x for x in named if "@" not in x} | set(MAIN_PADS)
    legs = {k: v for k, v in v1s["legs"].items() if all(p in nodes for p in k.split("->"))}
    on_leg = sorted({i for ids in legs.values() for i in ids if not never_all[i]})
    leg_of = {}
    for k, ids in legs.items():
        for i in ids:
            leg_of.setdefault(i, []).append(k)
    like = {}
    longest_leg = {}
    for k, y in enumerate(ALL_YEARS):
        need = jul1_h(y) - E[k]
        hit = [i for i in on_leg if dark_jan[i, k] >= need]
        like[str(y)] = {"samples": hit, "n": len(hit), "dark_from_jan_h_max": int(max((dark_jan[i, k] for i in on_leg), default=0))}
        j = max(on_leg, key=lambda i: longest[i, k])
        longest_leg[str(y)] = {"sample": int(j), "longest_dark_h": int(longest[j, k]), "legs": sorted(leg_of[j])[:4]}
    like_years = [y for y in ALL_YEARS if like[str(y)]["n"]]
    # the legs where 2028's strandings sat: the regolith flow CONSTR <-> ISRU (87 % of the stranded rover-hours,
    # results/E21_strategic_years.json stranding_2028_top_legs)
    reg = sorted({i for k in REGOLITH_LEGS for i in v1s["legs"][k] if not never_all[i]})
    like_reg, whole_reg = {}, {}
    for k, y in enumerate(ALL_YEARS):
        need, full = jul1_h(y) - E[k], E[k + 1] - E[k]
        like_reg[str(y)] = [int(i) for i in reg if dark_jan[i, k] >= need]
        whole_reg[str(y)] = [int(i) for i in reg if dark_jan[i, k] >= full]
    yrs_half = [y for y in ALL_YEARS if like_reg[str(y)]]
    yrs_whole = [y for y in ALL_YEARS if whole_reg[str(y)]]
    # #188 and the period of its annual linked hours
    s188 = EL.DARK_SAMPLE
    y188 = hours[s188].astype(float)
    t = np.array(ALL_YEARS, dtype=float)
    periods = np.round(np.arange(2.0, 19.0001, 0.01), 2)
    fit = sinusoid_fit(t, y188, periods)
    X = np.stack([np.ones_like(t), np.cos(2 * np.pi * t / fit["period"]), np.sin(2 * np.pi * t / fit["period"])], axis=1)
    yhat = X @ fit["coef"]
    res = y188 - yhat
    rss0 = float(((y188 - y188.mean()) ** 2).sum())
    F = ((rss0 - fit["rss"][fit["k"]]) / 3) / (fit["rss"][fit["k"]] / (len(t) - 4))   # period free: 3 extra parameters
    rng = np.random.default_rng(63)
    draws = np.array([sinusoid_fit(t, yhat + rng.choice(res, len(res)), periods)["period"] for _ in range(boot)])
    beat = sinusoid_fit(t, y188, np.array([BEAT_YR]))
    k46 = t <= 2046                                          # the fit on 2028-2046 only (the task's span), for comparison
    fit46 = sinusoid_fit(t[k46], y188[k46], periods)
    X46 = np.stack([np.ones(k46.sum()), np.cos(2 * np.pi * t[k46] / fit46["period"]), np.sin(2 * np.pi * t[k46] / fit46["period"])], axis=1)
    r46 = y188[k46] - X46 @ fit46["coef"]
    d46 = np.array([sinusoid_fit(t[k46], X46 @ fit46["coef"] + rng.choice(r46, len(r46)), periods)["period"] for _ in range(boot)])
    # the same on the monthly linked fraction (228 points) as a finer check
    me = []
    for y in ALL_YEARS:
        for mth in range(1, 13):
            me.append(int(np.datetime64(f"{y}-{mth:02d}-01", "h").astype(int) - np.datetime64("2028-01-01", "h").astype(int)))
    me.append(E[-1])
    m188 = np.concatenate([mask(v1s, s188, n1), mask(v3s, s188, n3)])
    monthly = np.array([m188[me[i]:me[i + 1]].mean() for i in range(len(me) - 1)])
    tm = 2028 + (np.arange(len(monthly)) + 0.5) / 12.0
    fit_m = sinusoid_fit(tm, monthly, periods)
    dates = lambda h: str(np.datetime64("2028-01-01T00", "h") + np.timedelta64(int(h), "h"))[:13]
    r = runs_dark(m188)
    long_ = [(int(a_), int(b_)) for a_, b_ in r if b_ - a_ >= 180 * 24]
    spells = [{"start": dates(a_), "end": dates(b_), "days": round((b_ - a_) / 24.0, 1),
               "censored": bool(a_ == 0 or b_ == len(m188))} for a_, b_ in long_]
    if os.path.isfile(BACK188) and spells and spells[0]["censored"] and spells[0]["start"].startswith("2028-01-01"):
        bk = json.load(open(BACK188))                        # the first spell's true start (step back188)
        t_b = int((np.datetime64(bk["spell_start"], "h") - np.datetime64("2028-01-01T00", "h")).astype(int))
        spells[0].update(start=bk["spell_start"], days=round((long_[0][1] - t_b) / 24.0, 1), censored=False,
                         start_from="back188 (2025-2027 ephemeris, #188 alone)")
        long_[0] = (t_b, long_[0][1])
    starts = [a_ / 8766.0 for a_, b_ in long_ if a_ != 0]
    ends = [b_ / 8766.0 for a_, b_ in long_ if b_ < len(m188)]
    # Earth at BASE per year (the cause): upper-limb elevation from the ephemerides
    e1, e3 = np.load(EL.ephem_path()), np.load(EPHEM3)
    lat, lon = (float(v) for v in e1["base_latlon"])
    sky = {}
    for e, years in ((e1, range(2028, 2032)), (e3, YEARS3)):
        _, el, _, rad = EL.earth_topo(e["E_base_km"], e["P_base_km"], e["P_base_km"], lat, lon)
        up = el + rad
        i0 = 0
        for y in years:
            n_e = (366 if calendar.isleap(y) else 365) * 24 * 60 // EL.STEP_MIN
            u = up[i0:i0 + n_e]
            sky[str(y)] = {"max_upper_limb_deg": round(float(u.max()), 3), "share_above_level": round(float((u > 0).mean()), 5)}
            i0 += n_e
    out = {
        "description": "B-63: Earth links 2032-2050 (earth_link-v3) joined to 2028-2031 (v1): per year, DTE any_part hourly. "
                       "2028-like year: a main-network-leg sample (legs between the seven sites and the two 1 km pads; "
                       "samples linked at some hour of 2028-2050) dark from 1 January until 1 July or later.",
        "continuity_2031_2032": {"samples_same_state": cont_same, "of": N},
        "never_linked": {"v1_2028_2031": int(never_v1.sum()), "v3_2032_2050": int(never_v3.sum()),
                         "all_2028_2050": int(never_all.sum()),
                         "v1_never_that_link_2032_2050": [int(i) for i in np.flatnonzero(never_v1 & ~never_v3)],
                         "v1_never_link_hours_2032_2050": {str(int(i)): int(hours[i, 4:].sum()) for i in np.flatnonzero(never_v1 & ~never_v3)}},
        "dark_sample_188": {"linked_h_by_year": {str(y): int(hours[s188, k]) for k, y in enumerate(ALL_YEARS)},
                            "longest_dark_h_by_year": {str(y): int(longest[s188, k]) for k, y in enumerate(ALL_YEARS)},
                            "dark_from_jan_h_by_year": {str(y): int(dark_jan[s188, k]) for k, y in enumerate(ALL_YEARS)},
                            "longest_dark_spell_2028_2050": {"start": dates(span[s188][0]), "hours": span[s188][1],
                                                             "end": dates(span[s188][0] + span[s188][1])},
                            "monthly_linked_fraction": [round(float(v), 4) for v in monthly]},
        "period_188": {"annual": {"best_period_yr": fit["period"], "ci95_yr": [float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))],
                                  "boot_draws": int(boot), "draws_within_5.5_6.5_yr": float(np.mean((draws >= 5.5) & (draws <= 6.5))),
                                  "amplitude_h": float(math.hypot(*fit["coef"][1:])), "mean_h": float(fit["coef"][0]),
                                  "F_vs_constant": float(F), "p_vs_constant": float(stats.f.sf(F, 3, len(t) - 4)),
                                  "rss_best": float(fit["rss"][fit["k"]]), "rss_at_5.997_yr": float(beat["rss"][0]),
                                  "rss_constant": rss0, "method": "least-squares sinusoid, period on a 0.01-yr grid 2-19 yr; "
                                  "residual bootstrap for the period's interval"},
                       "annual_2028_2046": {"best_period_yr": fit46["period"],
                                            "ci95_yr": [float(np.quantile(d46, 0.025)), float(np.quantile(d46, 0.975))],
                                            "points": int(k46.sum())},
                       "monthly": {"best_period_yr": fit_m["period"], "amplitude": float(math.hypot(*fit_m["coef"][1:]))}},
        "like_2028": {"definition": "main network: any sample of the legs between the sites and the 1 km pads",
                      "years": like_years, "by_year": like,
                      "note": "not discriminating: some rarely linked pad-leg samples are dark half the year in most years"},
        "like_2028_regolith_legs": {"legs": list(REGOLITH_LEGS), "samples": len(reg),
                                    "dark_from_jan_6_months_years": yrs_half, "dark_whole_year_years": yrs_whole,
                                    "by_year_6_months": like_reg, "by_year_whole": whole_reg,
                                    "whole_year_spacing_yr": [b_ - a_ for a_, b_ in zip(yrs_whole, yrs_whole[1:])]},
        "dark_spells_188_over_180_days": {"spells": spells,
                                          "start_spacing_yr": [round(b_ - a_, 2) for a_, b_ in zip(starts, starts[1:])],
                                          "end_spacing_yr": [round(b_ - a_, 2) for a_, b_ in zip(ends, ends[1:])]},
        "main_network_longest_dark_by_year": longest_leg,
        "earth_at_base_by_year": sky,
        "main_network": {"legs": len(legs), "samples": len(on_leg), "nodes": sorted(nodes)},
    }
    with open(PREDICT_OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    tab = pd.DataFrame(hours, columns=[f"linked_h_{y}" for y in ALL_YEARS])
    tab.insert(0, "sample", np.arange(N))
    tab.insert(1, "id", [smp["id"] or "" for smp in v1s["samples"]])
    tab.insert(2, "never_linked_2028_2031", never_v1)
    tab.insert(3, "never_linked_2032_2050", never_v3)
    tab["longest_dark_h_2028_2050"] = [sp_[1] for sp_ in span]
    tab.to_csv(PREDICT_CSV, index=False, lineterminator="\n")
    log(f"predict: #188 linked h by year {[int(v) for v in hours[s188]]}; best period {fit['period']} yr "
        f"(95 % {out['period_188']['annual']['ci95_yr'][0]:.2f}-{out['period_188']['annual']['ci95_yr'][1]:.2f}); "
        f"regolith legs dark from January >= 6 months {yrs_half}, whole year {yrs_whole}; never-linked v1 {int(never_v1.sum())}, v3 {int(never_v3.sum())}, both "
        f"{int(never_all.sum())} ({time.time() - t0:.0f} s)")
    return out


# ---------------------------------------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/comms/later_years.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ephem3")
    p = sub.add_parser("link3")
    p.add_argument("--part", type=int, default=0)
    p.add_argument("--parts", type=int, default=1)
    sub.add_parser("assemble3")
    sub.add_parser("parking3")
    sub.add_parser("back188")
    sub.add_parser("join")
    p = sub.add_parser("predict")
    p.add_argument("--boot", type=int, default=2000)
    for sp_ in sub.choices.values():
        sp_.add_argument("--max-seconds", type=float, default=540.0,
                         help="stop this process after so many seconds (Windows: `timeout` only kills the venv launcher)")
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    {"ephem3": lambda: step_ephem3(), "link3": lambda: step_link3(a.part, a.parts),
     "assemble3": lambda: step_assemble3(), "parking3": lambda: step_parking3(), "back188": lambda: step_back188(), "join": lambda: step_join(),
     "predict": lambda: step_predict(a.boot)}[a.cmd]()
    rss = EL.peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
