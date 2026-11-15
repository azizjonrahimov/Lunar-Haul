"""B-97: real-data checks.

    python tools/atc/run_b97.py telemetry     # SMAP / MSL telemetry: the z-score baseline and B-96's detector family
    python tools/atc/run_b97.py artemis       # Artemis II OpNav limb fits against the SPICE trajectory and attitude
    python tools/atc/run_b97.py geometry      # earth_link.py's topocentric geometry on the Artemis II trajectory
    python tools/atc/run_b97.py manifest      # results/B97_downloads.json (URL, bytes, sha256, mirror flag, licence)
    -> results/B97_realdata.json

Downloads (196 MB in all, under the 200 MB limit) live in .cache/external/ (git-ignored); the manifest is the record.

(1) Telemetry. The labelled SMAP / MSL telemetry of Hundman et al. 2018 (telemanom). Its original S3 bucket answers
    403; the arrays come from a public mirror (the TranAD repository, BSD-3-Clause, files unchanged) verified against
    the original: its labeled_anomalies.csv is byte-identical (sha256) to telemanom's GitHub copy; 82 channels (55
    SMAP, 27 MSL) and 105 labelled anomalies; every downloaded array has the stated number of rows (num_values) and
    25 (SMAP) or 55 (MSL) columns. A subset is used for the size limit: 14 MSL + 14 SMAP channels (the first of each
    spacecraft in the label file), 38 labelled anomalies. Column 0 is the telemetry value.
    Detectors on z = (x - mean_train) / std_train (std floored at 1e-3) and on the first difference: the z-score
    (|z|), and B-96's chi-square per step, chi-square windowed (w = 16) and CUSUM (k = 0.5), called through
    lunarsim.nn.baselines on a feature array in B-96's layout. Thresholds per channel from the TRAINING data only (the
    maximum training score: no training alarm), never from the labelled test events. B-96's logistic regression and
    network take B-96's ten pair features and do not apply to a single telemetry channel. Event level as telemanom: a
    labelled anomaly is found if an alarm falls inside it; a false positive is an alarm run that touches no anomaly.
(2) Artemis II OpNav (limb navigation only, cislunar range, not surface navigation): six raw 8-bit 2,592 x 2,048
    images, one per flight-day session (the 2 April session at about 365,000 km to the 10 April one), the label's
    start time; the lit disc segmented (Otsu), its boundary fitted with a RANSAC circle (the limb; the terminator is
    not a circle), refined by least squares on the inliers. Range = R / sin(alpha), alpha = atan(r / f), f from the
    instrument kernel (FOV half-angles 10.05 and 7.972 deg over 1,296 and 1,024 px). SPICE truth: the Moon's position
    from Orion (-24) in the ART002_OPNAV frame (LT+S), the trajectory SPK and the spacecraft attitude CK; the lunar
    frames kernel is loaded explicitly. Compared: range, the off-boresight angle (independent of the pixel-axis
    convention), and the full direction under the pixel-axis signs that fit best (the instrument kernel does not state
    them: stated as a choice of 2 bits). The labels' target field is not used (it says Moon for every image).
(3) Geometry: the elevation and azimuth of Orion seen from BASE (2-10 April 2026, hourly) by earth_link.py's own
    topocentric conversion (earth_topo on spkcpo vectors in MOON_ME) against SPICE's azlcpo; and how far BASE moves
    between MOON_ME and the IAU_MOON fallback (why the lunar frames kernel must be loaded).
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools", "comms")):
    if p not in sys.path:
        sys.path.insert(0, p)
EXT = os.path.join(ROOT, ".cache", "external")
TM = os.path.join(EXT, "telemanom")
A2 = os.path.join(EXT, "artemis2")
GEN = os.path.join(ROOT, ".cache", "comms", "kernels")
OUT = os.path.join(ROOT, "results", "B97_realdata.json")
MANIFEST = os.path.join(ROOT, "results", "B97_downloads.json")
R_MOON_KM = 1737.4
BODIES = {"MOON": 1737.4, "EARTH": 6371.0}       # mean radii (km); Earth's limb also has an atmosphere and 0.3 % flattening


def _update(key, val):
    doc = json.load(open(OUT)) if os.path.isfile(OUT) else {"task": "B-97 real-data checks", "note": __doc__.split("\n\n")[1].strip()}
    doc[key] = val
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1, default=float)
        f.write("\n")


# ------------------------------------------------------------------------------------------------ (1) telemetry
def _events(alarm):
    """Contiguous alarm runs [(start, end_exclusive)]."""
    a = np.r_[False, alarm, False].astype(int)
    d = np.diff(a)
    return list(zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)))


def cmd_telemetry():
    import ast
    from lunarsim.nn import baselines as B, faults as F
    rows = {r["chan_id"]: r for r in csv.DictReader(open(os.path.join(TM, "labeled_anomalies_official.csv")))}
    chans = sorted(f[:-4] for f in os.listdir(os.path.join(TM, "test")))

    def feats(z):
        X = np.zeros((1, len(z), len(F.FEATURES)), np.float32)
        X[0, :, F.F_Z] = z
        X[0, :, F.F_VALID] = 1.0
        return X
    dets = {"zscore": lambda X: np.abs(X[..., F.F_Z]), "chi2_step": B.chi2_step,
            "chi2_window_16": lambda X: B.chi2_window(X, 16), "cusum_k0.5": lambda X: B.cusum(X, 0.5)}
    tally = {}
    for c in chans:
        tr = np.load(os.path.join(TM, "train", c + ".npy"))[:, 0].astype(np.float64)
        te = np.load(os.path.join(TM, "test", c + ".npy"))[:, 0].astype(np.float64)
        anoms = ast.literal_eval(rows[c]["anomaly_sequences"])
        sc = rows[c]["spacecraft"]
        for res in ("level", "diff"):
            if res == "level":
                mu, sd = tr.mean(), max(tr.std(), 1e-3)
                ztr, zte = (tr - mu) / sd, (te - mu) / sd
            else:
                dtr = np.diff(tr, prepend=tr[0])
                sd = max(dtr.std(), 1e-3)
                ztr, zte = dtr / sd, np.diff(te, prepend=te[0]) / sd
            for dn, fn in dets.items():
                str_, ste = fn(feats(ztr))[0], fn(feats(zte))[0]
                thr = float(np.max(str_))                     # no alarm on the training data
                alarm = ste > thr
                found = sum(bool(alarm[a:b + 1].any()) for a, b in anoms)
                runs = _events(alarm)
                fp = sum(1 for s, e in runs if not any(s <= b and e - 1 >= a for a, b in anoms))
                k = (sc, res, dn)
                t = tally.setdefault(k, {"events": 0, "found": 0, "fp_runs": 0, "channels": 0})
                t["events"] += len(anoms)
                t["found"] += found
                t["fp_runs"] += fp
                t["channels"] += 1
    out = []
    for (sc, res, dn), t in sorted(tally.items()):
        rec = t["found"] / t["events"] if t["events"] else None
        prec = t["found"] / (t["found"] + t["fp_runs"]) if (t["found"] + t["fp_runs"]) else None
        f05 = (1.25 * prec * rec / (0.25 * prec + rec)) if prec and rec else 0.0
        out.append({"spacecraft": sc, "residual": res, "detector": dn, **t, "recall": rec, "precision": prec, "f0.5": f05})
    _update("telemetry", {"channels": chans, "rows": out,
                          "threshold_rule": "per channel, the maximum score on the training data (no training alarm)"})
    for r in out:
        print(r["spacecraft"], r["residual"], r["detector"], r["found"], "/", r["events"], "fp", r["fp_runs"],
              "P %.2f R %.2f" % (r["precision"] or 0, r["recall"] or 0))


# ------------------------------------------------------------------------------------------------ (2) Artemis II
def _otsu(img):
    h = np.bincount(img.ravel(), minlength=256).astype(float)
    p = h / h.sum()
    w = np.cumsum(p)
    mu = np.cumsum(p * np.arange(256))
    with np.errstate(divide="ignore", invalid="ignore"):
        sb = (mu[-1] * w - mu) ** 2 / (w * (1 - w))
    return int(np.nanargmax(sb))


def _largest_component(mask):
    """Largest 4-connected component (iterative flood fill on the bounding box of the mask)."""
    from collections import deque
    H, W = mask.shape
    seen = np.zeros_like(mask, bool)
    best = None
    ys, xs = np.nonzero(mask)
    for y0, x0 in zip(ys[::max(1, len(ys) // 2000)], xs[::max(1, len(xs) // 2000)]):
        if seen[y0, x0]:
            continue
        q = deque([(y0, x0)])
        seen[y0, x0] = True
        pts = []
        while q:
            y, x = q.popleft()
            pts.append((y, x))
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < H and 0 <= xx < W and mask[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    q.append((yy, xx))
        if best is None or len(pts) > len(best):
            best = pts
    out = np.zeros_like(mask, bool)
    if best:
        yy, xx = zip(*best)
        out[list(yy), list(xx)] = True
    return out


def _circle_lsq(x, y):
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    b = x * x + y * y
    (cx, cy, c), *_ = np.linalg.lstsq(A, b, rcond=None)
    return cx, cy, math.sqrt(max(c + cx * cx + cy * cy, 0.0))


def fit_limb(img, rng, iters=3000, tol=1.0):
    """(cx, cy, r, inlier share, n boundary points) of the lit disc's limb (module docstring)."""
    thr = _otsu(img)
    comp = _largest_component(img > thr)
    inner = comp.copy()
    inner[1:-1, 1:-1] = comp[1:-1, 1:-1] & comp[:-2, 1:-1] & comp[2:, 1:-1] & comp[1:-1, :-2] & comp[1:-1, 2:]
    by, bx = np.nonzero(comp & ~inner)
    x, y = bx.astype(float), by.astype(float)
    if len(x) < 10:
        return None
    best = (0, None)
    for _ in range(iters):
        i = rng.choice(len(x), 3, replace=False)
        try:
            cx, cy, r = _circle_lsq(x[i], y[i])
        except Exception:
            continue
        if not (5 < r < 4000):
            continue
        inl = np.abs(np.hypot(x - cx, y - cy) - r) < tol
        if inl.sum() > best[0]:
            best = (int(inl.sum()), inl)
    inl = best[1]
    cx, cy, r = _circle_lsq(x[inl], y[inl])
    inl = np.abs(np.hypot(x - cx, y - cy) - r) < tol
    cx, cy, r = _circle_lsq(x[inl], y[inl])
    return cx, cy, r, float(inl.mean()), int(len(x)), thr


def _label_time(xml_path):
    s = open(xml_path, encoding="utf-8", errors="replace").read()
    m = re.search(r"<start_date_time>([^<]+)</start_date_time>", s)
    return m.group(1).strip() if m else None


def _furnsh_artemis(sp):
    sp.kclear()
    for k in ("naif0012.tls", "pck00011.tpc", "moon_pa_de440_200625.bpc", "moon_de440_250416.tf", "de440s.bsp"):
        sp.furnsh(os.path.join(GEN, k))
    for k in ("moon_assoc_me.tf", "art002_v0.tf", "art002_fixedcam_v0.ti", "art002_met_v0.tsc", "art002_nom_v0.tsc",
              "art002_struct_v1.bsp", "art002_rec_260402_260410_jsc_bet_revf_gapfill.bsp",
              "art002_rec_260402_260410_jsc_bet_revf.bsp", "art002_sc_rec_260402_260410_betv0_v1.bc"):
        sp.furnsh(os.path.join(A2, "spice", k))


def cmd_artemis():
    import spiceypy as sp
    from PIL import Image
    _furnsh_artemis(sp)
    W, H = 2592, 2048
    fx = (W / 2) / math.tan(math.radians(10.05))
    fy = (H / 2) / math.tan(math.radians(7.972))
    f = 0.5 * (fx + fy)
    rng = np.random.default_rng(97)
    rows = []
    for name in sorted(n for n in os.listdir(os.path.join(A2, "opnav")) if n.endswith(".tif")):
        img = np.asarray(Image.open(os.path.join(A2, "opnav", name)))
        if img.ndim == 3:
            img = img[..., 0]
        t_utc = _label_time(os.path.join(A2, "opnav", name.replace(".tif", ".xml")))
        et = sp.str2et(t_utc.rstrip("Z").replace("T", " ") + " UTC")
        row = {"image": name, "utc": t_utc, "otsu": None,
               "pixel_stats": {"min": int(img.min()), "max": int(img.max()), "mean": float(img.mean())}}
        if img.min() == img.max():
            row["fit"] = f"unusable: every pixel is {int(img.min())} (saturated or blank frame)"
            rows.append(row)
            print(name, t_utc, row["fit"])
            continue
        fit = fit_limb(img.astype(np.uint8), rng)
        if fit is None:
            row["fit"] = "no disc found"
            rows.append(row)
            continue
        cx, cy, r, share, nb, thr = fit
        alpha = math.atan(r / f)
        u = (cx - (W - 1) / 2) / f
        v = (cy - (H - 1) / 2) / f
        off_img = math.degrees(math.atan(math.hypot(u, v)))
        row.update({"otsu": thr, "limb_px": {"cx": cx, "cy": cy, "r": r}, "limb_inlier_share": share, "boundary_px": nb,
                    "off_boresight_deg_image": off_img})
        # which body is it? The labels' target field says Moon for every image; decide from the geometry
        geo = {}
        for body, R in BODIES.items():
            pos, _ = sp.spkpos(body, et, "J2000", "LT+S", "ART002")
            d_km = float(np.linalg.norm(pos))
            g = {"range_km_spice": d_km, "r_px_predicted": f * math.tan(math.asin(R / d_km))}
            try:
                pc, _ = sp.spkpos(body, et, "ART002_OPNAV", "LT+S", "ART002")
                dd = np.asarray(pc) / np.linalg.norm(pc)
                g["dir_cam"] = dd
                g["off_boresight_deg_spice"] = math.degrees(math.acos(max(-1.0, min(1.0, dd[2]))))
                g["in_fov"] = bool(dd[2] > 0 and abs(math.degrees(math.atan2(dd[0], dd[2]))) <= 10.05
                                   and abs(math.degrees(math.atan2(dd[1], dd[2]))) <= 7.972)
            except Exception as e:
                g["attitude"] = f"no attitude ({type(e).__name__})"
            geo[body] = g
        if all("in_fov" in g for g in geo.values()) and any(g["in_fov"] for g in geo.values()):
            target = next(b for b, g in geo.items() if g["in_fov"])
            row["target_basis"] = "SPICE: the body inside the OpNav field of view"
        else:
            target = min(geo, key=lambda b: abs(geo[b]["r_px_predicted"] - r))
            row["target_basis"] = "no attitude: the body whose predicted disc radius matches the fit"
        g = geo[target]
        R = BODIES[target]
        rng_img = R / math.sin(alpha)
        row.update({"target": target, "radius_km_used": R, "range_km_image": rng_img, "range_km_spice": g["range_km_spice"],
                    "range_err_km": rng_img - g["range_km_spice"],
                    "range_err_rel": (rng_img - g["range_km_spice"]) / g["range_km_spice"],
                    "r_px_predicted": g["r_px_predicted"],
                    "other_body_off_boresight_deg": {b: geo[b].get("off_boresight_deg_spice") for b in geo if b != target}})
        if "dir_cam" in g:
            d = g["dir_cam"]
            row["off_boresight_deg_spice"] = g["off_boresight_deg_spice"]
            row["off_boresight_err_deg"] = off_img - g["off_boresight_deg_spice"]
            best = None
            for sx in (1, -1):
                for sy in (1, -1):
                    m = np.array([sx * u, sy * v, 1.0])
                    m /= np.linalg.norm(m)
                    ang = math.degrees(math.acos(max(-1.0, min(1.0, float(m @ d)))))
                    if best is None or ang < best[0]:
                        best = (ang, sx, sy)
            row["direction_err_deg_best_signs"] = best[0]
            row["pixel_axis_signs"] = [best[1], best[2]]
        else:
            row["attitude"] = g.get("attitude", "no attitude") + ": range check only"
        rows.append(row)
        print(name, t_utc, target, "r %.1f px (pred %.1f) share %.2f" % (r, g["r_px_predicted"], share),
              "range img %.0f spice %.0f km (%.2f %%)" % (rng_img, g["range_km_spice"], 100 * row["range_err_rel"]),
              "off-bore img %.3f spice %s" % (off_img, "%.3f" % row["off_boresight_deg_spice"] if "off_boresight_deg_spice" in row else "-"),
              "dir err %s" % ("%.3f" % row["direction_err_deg_best_signs"] if "direction_err_deg_best_signs" in row else "-"))
    signs = [tuple(r["pixel_axis_signs"]) for r in rows if "pixel_axis_signs" in r]
    _update("artemis2", {"camera": {"focal_px": f, "fx": fx, "fy": fy, "urad_per_px": 1e6 / f}, "images": rows,
                         "pixel_axis_signs_consistent": len(set(signs)) <= 1,
                         "scope": "limb navigation only (cislunar range from the disc), not surface navigation"})


# ------------------------------------------------------------------------------------------------ (3) geometry
def cmd_geometry():
    import spiceypy as sp
    import earth_link as EL
    _furnsh_artemis(sp)
    from lunarsim.atc import geo
    meta, sites = EL.load_pack()
    bx, by = sites["base_xy_m"]
    X, Y = bx + meta["origin_xy_m"][0], by + meta["origin_xy_m"][1]
    P = EL.stereo_unit(X, Y) * (EL.R_MOON_M) / 1000.0                     # BASE on the sphere (km)
    lat, lon = EL.latlon_deg(X, Y)
    et0, et1 = sp.str2et("2026-04-02 03:00 UTC"), sp.str2et("2026-04-10 23:00 UTC")
    ets = np.arange(et0, et1, 3600.0)
    E, ok = [], []
    for et in ets:
        try:
            st, _ = sp.spkcpo("ART002", float(et), "MOON_ME", "OBSERVER", "LT+S", P, "MOON", "MOON_ME")
            E.append(st[:3])
            ok.append(et)
        except Exception:
            pass
    E = np.array(E)
    az, el, brg, rad = EL.earth_topo(E, P, P, float(lat), float(lon))
    d_az, d_el = [], []
    for i, et in enumerate(ok):
        st, _ = sp.azlcpo("ELLIPSOID", "ART002", float(et), "LT+S", False, True, P, "MOON", "MOON_ME")
        d_az.append(abs(EL.wrap180(math.degrees(st[1]) - az[i])))
        d_el.append(abs(math.degrees(st[2]) - el[i]))
    M = sp.pxform("MOON_ME", "IAU_MOON", float(ets[len(ets) // 2]))
    shift_m = float(np.linalg.norm(np.asarray(M) @ P - P) * 1000.0)
    res = {"epochs": len(ok), "base_lat_lon": [float(lat), float(lon)],
           "orion_elevation_range_deg": [float(el.min()), float(el.max())],
           "orion_visible_share": float((el > 0).mean()),
           "max_abs_az_diff_deg": float(max(d_az)), "max_abs_el_diff_deg": float(max(d_el)),
           "moon_me_vs_iau_moon_shift_at_base_m": shift_m,
           "note": "earth_topo (earth_link.py) against SPICE azlcpo for Orion seen from BASE; the frame shift is BASE's "
                   "position moved by the MOON_ME -> IAU_MOON rotation at mid-period (the fallback without the lunar "
                   "frames kernel)"}
    _update("geometry", res)
    print(json.dumps(res, indent=1))


def cmd_manifest():
    SP = sys.argv[2] if len(sys.argv) > 2 else None
    import hashlib
    files = []
    for dirpath, _, names in os.walk(EXT):
        for n in sorted(names):
            p = os.path.join(dirpath, n)
            b = open(p, "rb").read()
            files.append({"file": os.path.relpath(p, ROOT).replace("\\", "/"), "bytes": len(b),
                          "sha256": hashlib.sha256(b).hexdigest()})
    urls = {}
    for src in ("b97_tele_manifest.json", "b97_a2_manifest.json"):
        if SP and os.path.isfile(os.path.join(SP, src)):
            d = json.load(open(os.path.join(SP, src)))
            for m in (d if isinstance(d, list) else d["manifest"]):
                urls[m["file"].replace("\\", "/")] = (m["url"], m.get("mirror", False))
    urls[".cache/external/telemanom/labeled_anomalies_official.csv"] = (
        "https://raw.githubusercontent.com/khundman/telemanom/master/labeled_anomalies.csv", False)
    urls[".cache/external/telemanom/labeled_anomalies_mirror.csv"] = (
        "https://raw.githubusercontent.com/imperial-qore/TranAD/main/data/SMAP_MSL/labeled_anomalies.csv", True)
    for f in files:
        u, mir = urls.get(f["file"], (None, None))
        f["url"], f["mirror"] = u, mir
    doc = {"task": "B-97", "location": ".cache/external/ (git-ignored)", "total_bytes": sum(f["bytes"] for f in files),
           "limit_bytes": 200_000_000,
           "sources": {
               "telemanom (SMAP / MSL)": {
                   "original": "https://github.com/khundman/telemanom (data bucket https://s3-us-west-2.amazonaws.com/telemanom/data.zip answers 403)",
                   "mirror": "https://github.com/imperial-qore/TranAD/tree/main/data/SMAP_MSL",
                   "mirror_licence": "BSD-3-Clause (GitHub licence API for imperial-qore/TranAD)",
                   "original_licence": "NOASSERTION per the GitHub licence API (see the repository's LICENSE file)",
                   "is_mirror": True,
                   "checks_passed": ["labeled_anomalies.csv byte-identical to the original (sha256 057ce2d6...)",
                                     "82 channels: 55 SMAP, 27 MSL", "105 labelled anomalies",
                                     "every downloaded test array has num_values rows; 25 (SMAP) / 55 (MSL) columns"]},
               "Artemis II SPICE": "https://naif.jpl.nasa.gov/pub/naif/pds/pds4/artemis2/artemis2_spice/ (doi:10.17189/7ezn-0294)",
               "Artemis II OpNav images": "PDS Imaging Node Atlas, https://pds-imaging.jpl.nasa.gov/api/data/atlas:pds4:artemis2:artemis2:/artemis2_orion_camera/data_raw_image/",
               "generic NAIF kernels": "already in .cache/comms/kernels (tools/comms/earth_link.py), not counted here"},
           "files": files}
    with open(MANIFEST, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(len(files), "files", round(doc["total_bytes"] / 1e6, 2), "MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["telemetry", "artemis", "geometry", "manifest"])
    ap.add_argument("scratch", nargs="?")
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(540, exit=True)
    {"telemetry": cmd_telemetry, "artemis": cmd_artemis, "geometry": cmd_geometry, "manifest": cmd_manifest}[a.cmd]()


if __name__ == "__main__":
    main()
