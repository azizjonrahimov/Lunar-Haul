"""Scene packages (``lunarsim-scene`` v1, B-31): what a 3D replay of one simulated year needs.

    python -m lunarsim.scene --trace run_v2.json --out site/public/scenes/P2V2
    python -m lunarsim.scene --scenario P2-4-vehicles --seed 3 --terrain connecting_ridge --pad-standoff 1 \\
        --landing-model classical --plume 1,0.5 --autonomy driving-v1 [--comms dte] --out scenes/P2V2

A package is a folder: scene.json (the index, documented in schemas/scene-v1.schema.json), routes.bin and one
chunk_NNN.bin per 30 days (CHUNK_H). Binaries are little-endian float32 matrices at the offsets the index gives.

Vehicles are a timeline of segments covering [0, horizon] (SEG_COLS): stationary segments sit at (x0, y0, z0);
a driving segment follows route `route` (routes.bin, the B-32 planned route for that leg and the lighting at its start,
vertices (x, y, z, f) with f the cumulative time fraction) from route fraction f0 to f1, with f linear in time inside
the segment: position(t) = route point at f0 + (f1 - f0) (t - t0) / (t1 - t0). route = -1 means a straight line
from (x0, y0, z0) to (x1, y1, z1) (a pad <-> pad leg without a planned route). Segments are split at chunk boundaries
and at every Earth-link wait inside a drive.
States: idle, driving, loading (load/unload, team coupling), team_lift (a loaded team drive), parked_night (a vehicle
that cannot work in the dark, idle or hibernating at night), standdown (a plume keep-out hold), waiting_for_earth
(trace comms_waits), failed (fault recovery).
Mapping from the trace (stated because the trace does not label stationary segments): a job's first segment when it
is stationary and lasts > 0 is a keep-out hold (or an Earth-link wait if comms_waits has it); a second stationary
segment at the job's last site after the unloading is the job's tail extension (night hibernation if it overlaps a
night of a vehicle without night operations, else fault recovery); other stationary segments and gaps inside a job are
loading. A team job's trace records the lead vehicle's segments; the other members are given the same timeline, with
their own approach leg.
Hourly series per chunk (HOURLY_COLS + per site waiting items and kg): sun azimuth (the scenario's sun model,
360 (t mod synodic month) / synodic month, as lunarsim.phase3), night flag, Earth's elevation / apparent radius / grid
bearing at BASE from earth_track-v1 (the comms start year when comms is on, else 2028), items waiting at each site.
Deterministic: the same trace gives byte-identical files.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import math
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

SCENE_FORMAT = "lunarsim-scene"
SCENE_VERSION = 1
CHUNK_H = 720.0
STATES = ("idle", "driving", "loading", "team_lift", "parked_night", "standdown", "waiting_for_earth", "failed")
S = {name: i for i, name in enumerate(STATES)}
SEG_COLS = ("veh", "job", "t0", "t1", "x0", "y0", "z0", "x1", "y1", "z1", "route", "f0", "f1", "load_kg", "state",
            "heading_deg")
HOURLY_COLS = ("sun_az_deg", "night", "earth_el_deg", "earth_radius_deg", "earth_bearing_deg")
ROUTE_COLS = ("x", "y", "z", "f")
ROUTES = os.path.join("data", "driving", "routes-v1.json")
TRAJECTORIES = os.path.join("data", "policies", "trajectories-v1.json")
EARTH_TRACK = os.path.join("data", "comms", "connecting_ridge", "earth_track-v1.json.gz")
RDP_TOL_M = 0.5            # route vertices dropped when within this distance of the simplified line (x, y, z)
LUNAR_CYCLE_H = 29.53 * 24.0
_EPS = 1e-9


def _find(path: str) -> str:
    if os.path.exists(path):
        return path
    alt = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)
    return alt if os.path.exists(alt) else path


def _load_json(path: str):
    p = _find(path)
    with open(p, "rb") as f:
        raw = f.read()
    return json.loads(gzip.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw)


def sun_az_deg(t_h) -> np.ndarray:
    return 360.0 * (np.asarray(t_h, float) % LUNAR_CYCLE_H) / LUNAR_CYCLE_H


def light_key(t_h: float, nights: List[List[float]]) -> str:
    """The driving tables' lighting case at time t (lunarsim.phase3.DrivingModel.light_bin)."""
    if any(a <= t_h < b for a, b in nights):
        return "night"
    az = float(sun_az_deg(t_h))
    best = min((0.0, 90.0, 180.0, 270.0), key=lambda b: abs((az - b + 180.0) % 360.0 - 180.0))
    return f"{best:g}"


def rdp(points: np.ndarray, tol: float) -> List[int]:
    """Indices kept by Ramer-Douglas-Peucker on 3-D points (iterative)."""
    n = len(points)
    if n <= 2:
        return list(range(n))
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    stack = [(0, n - 1)]
    while stack:
        i, j = stack.pop()
        if j <= i + 1:
            continue
        a, b = points[i], points[j]
        ab = b - a
        L2 = float(ab @ ab)
        seg = points[i + 1:j] - a
        if L2 <= 0:
            d = np.linalg.norm(seg, axis=1)
        else:
            u = np.clip(seg @ ab / L2, 0.0, 1.0)
            d = np.linalg.norm(seg - np.outer(u, ab), axis=1)
        k = int(np.argmax(d))
        if d[k] > tol:
            m = i + 1 + k
            keep[m] = True
            stack += [(i, m), (m, j)]
    return list(np.flatnonzero(keep))


class _Routes:
    """Planned routes (routes-v1) used by a package, decoded on demand and simplified."""

    def __init__(self, doc, standoff: str, pads: Sequence[str]):
        from .rover.routes import decode_geom, decode_f
        self.doc, self.standoff, self.pads = doc, standoff, set(pads)
        self._dg, self._df = decode_geom, decode_f
        self.index: Dict[Tuple[str, str], int] = {}
        self.blocks: List[np.ndarray] = []
        self.meta: List[Dict[str, Any]] = []

    def name(self, site: str) -> str:
        return f"{site}@{self.standoff}" if site in self.pads else site

    def get(self, a: str, b: str, light: str) -> int:
        key = f"{self.name(a)}->{self.name(b)}"
        k = (key, light)
        if k in self.index:
            return self.index[k]
        e = (self.doc["legs"].get(key) or {}).get(light)
        if e is None:
            self.index[k] = -1
            return -1
        g = self._dg(self.doc["geoms"][e["geom"]])
        f = self._df(e["df"])
        pts = np.stack([g["x"], g["y"], g["z"]], axis=1)
        keep = rdp(pts, RDP_TOL_M)
        block = np.column_stack([pts[keep], f[keep]]).astype("<f4")
        self.index[k] = len(self.blocks)
        self.blocks.append(block)
        self.meta.append({"leg": key, "lighting": light, "n": int(len(block)), "length_m": e["length_m"]})
        return self.index[k]

    def point(self, ridx: int, f: float) -> Tuple[float, float, float]:
        b = self.blocks[ridx].astype(float)
        return (float(np.interp(f, b[:, 3], b[:, 0])), float(np.interp(f, b[:, 3], b[:, 1])),
                float(np.interp(f, b[:, 3], b[:, 2])))

    def heading(self, ridx: int, f: float) -> float:
        b = self.blocks[ridx].astype(float)
        k = int(np.clip(np.searchsorted(b[:, 3], f, side="right") - 1, 0, len(b) - 2))
        dx, dy = b[k + 1, 0] - b[k, 0], b[k + 1, 1] - b[k, 1]
        return math.degrees(math.atan2(dx, dy)) % 360.0


def _site_z(sites_doc, standoff: str) -> Dict[str, float]:
    z = {s["id"]: float(s.get("z_m", 0.0)) for s in sites_doc["sites"]}
    for pid, d in (sites_doc.get("pad_details", {}).get(standoff) or {}).items():
        z[pid] = float(d.get("z_m", 0.0))
    return z


def build(trace: Dict[str, Any], out_dir: str, routes_doc=None, traj_doc=None, track_doc=None,
          start_h: Optional[float] = None) -> Dict[str, Any]:
    """Write a scene package for a trace v2 (dict); returns the index."""
    if trace.get("format") != "lunarsim-trace" or trace.get("version") != 2:
        raise ValueError("a scene package is built from a lunarsim-trace v2 (terrain legs)")
    H = float(trace["horizon_h"])
    standoff = str(trace.get("pad_standoff_km") or "1")
    pads = [p for p in trace["site_xy_m"] if p.startswith("PAD_")]
    routes_doc = routes_doc or _load_json(ROUTES)
    traj_doc = traj_doc if traj_doc is not None else (_load_json(TRAJECTORIES) if os.path.exists(_find(TRAJECTORIES)) else None)
    track_doc = track_doc if track_doc is not None else (_load_json(EARTH_TRACK) if os.path.exists(_find(EARTH_TRACK)) else None)
    sites_doc = _load_json(os.path.join("data", "terrain", trace["terrain"], "sites.json"))
    zs = _site_z(sites_doc, standoff)
    xy = {k: (float(v[0]), float(v[1])) for k, v in trace["site_xy_m"].items()}
    pos = {k: (xy[k][0], xy[k][1], zs.get(k, 0.0)) for k in xy}
    nights = [list(map(float, n)) for n in trace["nights"]]
    routes = _Routes(routes_doc, standoff, pads)
    vehicles = trace["vehicles"]
    night_ops = {v["id"]: bool(v["night_ops"]) for v in vehicles}
    comms = trace.get("comms")
    waits_by_v: Dict[int, List[list]] = {}
    for w in trace.get("comms_waits", []) or []:
        waits_by_v.setdefault(int(w[0]), []).append(w)
    if start_h is None:
        start_h = float(comms["start_h"]) if comms else 0.0

    # ---- per vehicle raw segments (t0, t1, a, b, load, state, job) -----------------------------------------
    raw: Dict[int, List[list]] = {v["id"]: [] for v in vehicles}
    jobs = sorted(enumerate(trace["jobs"]), key=lambda kv: (kv[1]["t0"], kv[0]))
    last_loc = {v["id"]: "DEPOT" for v in vehicles}
    for jid, rec in jobs:
        segs = rec["segments"]
        team = rec.get("team") or [rec["veh"]]
        is_team = len(team) > 1
        for vid in team:
            own = [list(s) for s in segs]
            if vid != rec["veh"] and own and own[0][0] != own[0][1]:
                own[0][0] = last_loc[vid]                       # the member's own approach leg
            n = len(own)
            mine: List[list] = []
            for k, (a, b, t0, t1, load) in enumerate(own):
                if t1 - t0 <= _EPS and a == b:
                    continue
                if a != b:
                    state = "team_lift" if (is_team and load > 0) else "driving"
                elif k == 0 and rec["kind"] != "reposition":
                    state = "standdown"
                elif k == n - 1 and k >= 1 and own[k - 1][0] == own[k - 1][1] == a and n >= 3:
                    state = "parked_night" if (not night_ops[vid] and any(x < t1 and y > t0 for x, y in nights)) else "failed"
                else:
                    state = "loading"
                if mine and t0 > mine[-1][1] + 1e-7:            # a gap inside the job (team coupling): loading
                    mine.append([mine[-1][1], t0, a, a, float(load), "loading", jid])
                mine.append([t0, t1, a, b, float(load), state, jid])
            raw[vid].extend(mine)
            if own:
                last_loc[vid] = own[-1][1]

    # ---- timeline: idle / night gaps, Earth-link waits, positions on routes ------------------------------
    rows: List[List[float]] = []
    deliveries = []
    for v in vehicles:
        vid = v["id"]
        segs = sorted(raw[vid], key=lambda s: (s[0], s[1]))
        timeline: List[list] = []
        t, loc, heading = 0.0, "DEPOT", 0.0

        def idle(t0, t1, site):
            cuts = sorted({t0, t1, *[c for n in nights for c in n if t0 < c < t1]})
            for x, y in zip(cuts[:-1], cuts[1:]):
                night = any(a <= x < b for a, b in nights)
                st = "parked_night" if (night and not night_ops[vid]) else "idle"
                timeline.append([x, y, site, site, 0.0, st, -1])

        for s in segs:
            if s[0] > t + 1e-7:
                idle(t, s[0], loc)
            timeline.append(s)
            t, loc = max(t, s[1]), s[3]
        if t < H - 1e-7:
            idle(t, H, loc)
        waits = sorted(waits_by_v.get(vid, []), key=lambda w: w[1])
        for t0, t1, a, b, load, state, jid in timeline:
            if t1 - t0 <= _EPS:
                continue
            if a == b:
                st = state
                if any(abs(w[1] - t0) < 1e-3 and abs(w[2] - t1) < 1e-3 for w in waits):
                    st = "waiting_for_earth"
                x, y, z = pos[a]
                rows.append([vid, jid, t0, t1, x, y, z, x, y, z, -1, 0.0, 0.0, load, S[st], heading])
                continue
            light = light_key(t0, nights)
            ridx = routes.get(a, b, light)
            inner = [w for w in waits if t0 - 1e-6 <= w[1] and w[2] <= t1 + 1e-6 and w[4] in ("midway", "intervention")]
            moving = (t1 - t0) - sum(w[2] - w[1] for w in inner)
            pieces, cur, done = [], t0, 0.0
            for w in inner:                                     # split the drive at every wait
                d = w[1] - cur
                pieces.append(("move", cur, w[1], done, done + d))
                done += d
                pieces.append(("wait", w[1], w[2], done, done))
                cur = w[2]
            pieces.append(("move", cur, t1, done, moving))
            for kind, p0, p1, m0, m1 in pieces:
                if p1 - p0 <= _EPS:
                    continue
                fa, fb = (m0 / moving, m1 / moving) if moving > _EPS else (1.0, 1.0)
                if ridx >= 0:
                    x0, y0, z0 = routes.point(ridx, fa)
                    x1, y1, z1 = routes.point(ridx, fb)
                    hd = routes.heading(ridx, fa)
                else:
                    (ax, ay, az), (bx, by, bz) = pos[a], pos[b]
                    x0, y0, z0 = ax + fa * (bx - ax), ay + fa * (by - ay), az + fa * (bz - az)
                    x1, y1, z1 = ax + fb * (bx - ax), ay + fb * (by - ay), az + fb * (bz - az)
                    hd = math.degrees(math.atan2(bx - ax, by - ay)) % 360.0
                st = state if kind == "move" else "waiting_for_earth"
                rows.append([vid, jid, p0, p1, x0, y0, z0, x1, y1, z1, ridx, fa, fb, load, S[st], hd])
                heading = hd
    # deliveries from the cargo table (masses as the trace rounds them)
    cols = trace["cargo_columns"]
    ci = {c: i for i, c in enumerate(cols)}
    for r in trace["cargo"]:
        if r[ci["t_delivered"]] is not None:
            deliveries.append([float(r[ci["t_delivered"]]), r[ci["dest"]], float(r[ci["mass_kg"]]), int(r[ci["id"]])])
    deliveries.sort(key=lambda d: (d[0], d[3]))

    # ---- chunking -------------------------------------------------------------------------------------------
    os.makedirs(out_dir, exist_ok=True)
    n_chunks = int(math.ceil(H / CHUNK_H - 1e-9))
    seg = np.array(rows, dtype=float) if rows else np.zeros((0, len(SEG_COLS)))
    sites = list(xy)
    site_ix = {s: i for i, s in enumerate(sites)}
    waiting = _waiting_hourly(trace, sites, H)
    hourly_cols = list(HOURLY_COLS) + [f"waiting_n_{s}" for s in sites] + [f"waiting_kg_{s}" for s in sites]
    hours = np.arange(int(math.ceil(H)))
    earth = _earth_hourly(track_doc, start_h, hours)
    night_flag = np.array([1.0 if any(a <= h < b for a, b in nights) else 0.0 for h in hours])
    hourly = np.column_stack([sun_az_deg(hours), night_flag, earth, waiting]).astype(float)
    chunks = []
    for c in range(n_chunks):
        c0, c1 = c * CHUNK_H, min(H, (c + 1) * CHUNK_H)
        sel = seg[(seg[:, 2] < c1) & (seg[:, 3] > c0)] if len(seg) else seg
        part = []
        for r in sel:                                         # clip to the chunk; f stays linear in time
            r = r.copy()
            t0, t1 = r[2], r[3]
            n0, n1 = max(t0, c0), min(t1, c1)
            if (n0, n1) != (t0, t1):
                if r[10] >= 0 or r[4:7].tolist() != r[7:10].tolist():
                    g = lambda tt: (tt - t0) / (t1 - t0)
                    f0, f1 = r[11], r[12]
                    p0, p1 = r[4:7].copy(), r[7:10].copy()
                    r[11], r[12] = f0 + (f1 - f0) * g(n0), f0 + (f1 - f0) * g(n1)
                    if r[10] >= 0:
                        r[4:7] = routes.point(int(r[10]), r[11])
                        r[7:10] = routes.point(int(r[10]), r[12])
                    else:
                        r[4:7], r[7:10] = p0 + (p1 - p0) * g(n0), p0 + (p1 - p0) * g(n1)
                r[2], r[3] = n0, n1
            part.append(r)
        segs_c = np.array(part, dtype="<f4").reshape(-1, len(SEG_COLS))
        hr = hourly[int(c0):int(math.ceil(c1))].astype("<f4")
        fname = f"chunk_{c:03d}.bin"
        buf = segs_c.tobytes() + hr.tobytes()
        with open(os.path.join(out_dir, fname), "wb") as f:
            f.write(buf)
        chunks.append({"file": fname, "t0": c0, "t1": c1, "bytes": len(buf), "sha256": hashlib.sha256(buf).hexdigest(),
                       "segments": {"offset": 0, "rows": int(len(segs_c)), "cols": len(SEG_COLS)},
                       "hourly": {"offset": int(segs_c.nbytes), "rows": int(len(hr)), "cols": len(hourly_cols),
                                  "first_hour": int(c0)}})
    rbuf = b"".join(b.tobytes() for b in routes.blocks)
    with open(os.path.join(out_dir, "routes.bin"), "wb") as f:
        f.write(rbuf)
    off, rmeta = 0, []
    for m, b in zip(routes.meta, routes.blocks):
        rmeta.append(dict(m, offset=off))
        off += b.nbytes

    # ---- landings with their nearest B-33 trajectory --------------------------------------------------------
    landings = []
    for L in trace["landings"]:
        miss = float(math.hypot(*L["miss_m"])) if L.get("miss_m") is not None else None
        landings.append({"t_h": float(L["t"]), "cls": L["type"], "pad": L["pad"], "miss_m": miss, "ok": L.get("ok"),
                         "failure_kind": L.get("failure_kind"), "cargo_kg": L.get("cargo_kg"),
                         "trajectory": _nearest_trajectory(traj_doc, L["type"], miss, L.get("ok"))})
    checks = {"delivered_kg_cargo_table": round(sum(d[2] for d in deliveries), 3),
              "delivered_kg_summary": trace["summary"].get("delivered_kg"),
              "trips": sum(1 for j in trace["jobs"] if j.get("kind") != "reposition"),
              "trips_summary": trace["summary"].get("jobs"), "landings": len(trace["landings"])}
    index = {
        "format": SCENE_FORMAT, "version": SCENE_VERSION, "scenario": trace["scenario"], "mechanism": trace["mechanism"],
        "seed": trace["seed"], "terrain": trace["terrain"], "pad_standoff_km": standoff, "horizon_h": H,
        "chunk_h": CHUNK_H, "frame": "terrain pack local frame: x east, y north (m from the tile's south-west corner), "
                                     "z = LOLA height (m); heading: grid azimuth deg, 0 = +y, 90 = +x",
        "sites": {k: [round(v, 3) for v in pos[k]] for k in sites},
        "vehicles": [{"id": v["id"], "owner": v["owner"], "cls": v["cls"], "autonomy": v["autonomy"],
                      "night_ops": v["night_ops"], "capacity_kg": v["capacity"]} for v in vehicles],
        "states": list(STATES), "segment_columns": list(SEG_COLS), "hourly_columns": hourly_cols,
        "route_columns": list(ROUTE_COLS),
        "routes": {"file": "routes.bin", "bytes": len(rbuf), "sha256": hashlib.sha256(rbuf).hexdigest(),
                   "source": "data/driving/routes-v1.json (B-32), simplified (RDP, %.1f m)" % RDP_TOL_M, "items": rmeta},
        "chunks": chunks,
        "landings": landings,
        "keepout_windows": [[float(a), float(b), p, float(r)] for a, b, p, r in trace.get("plume_windows", [])],
        "nights": nights,
        "deliveries": [[round(d[0], 4), site_ix.get(d[1], -1), d[2]] for d in deliveries],
        "jobs": [[jid, rec.get("kind", ""), rec["veh"], len(rec.get("team") or [rec["veh"]]), round(rec["t0"], 4),
                  round(rec["t1"], 4), len(rec.get("items", []))] for jid, rec in enumerate(trace["jobs"])],
        "jobs_columns": ["job", "kind", "lead_vehicle", "team_size", "t0", "t1", "items"],
        "comms": comms, "comms_waits": trace.get("comms_waits") if comms else None,
        "earth": {"source": "data/comms/connecting_ridge/earth_track-v1.json.gz" if track_doc else None,
                  "start_h": start_h},
        "checks": checks,
        "summary": {k: trace["summary"].get(k) for k in ("delivered_kg", "jobs", "delay_prio1_p90_h", "delay_mean_h",
                                                       "plume_standdowns", "offpad_landings", "failed_landings")},
    }
    with open(os.path.join(out_dir, "scene.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, separators=(",", ":"))
    return index


def _waiting_hourly(trace, sites, H) -> np.ndarray:
    """Items and kg waiting (ready, not picked up) at each site at the start of every hour."""
    cols = {c: i for i, c in enumerate(trace["cargo_columns"])}
    n_h = int(math.ceil(H))
    cnt = np.zeros((n_h, len(sites)))
    kg = np.zeros((n_h, len(sites)))
    ix = {s: i for i, s in enumerate(sites)}
    for r in trace["cargo"]:
        o = r[cols["origin"]]
        if o not in ix:
            continue
        t0 = r[cols["t_ready"]]
        t1 = r[cols["t_picked"]] if r[cols["t_picked"]] is not None else H + 1
        h0, h1 = int(math.ceil(t0 - 1e-9)), min(n_h, int(math.ceil(t1 - 1e-9)))
        if h1 > h0:
            cnt[h0:h1, ix[o]] += 1
            kg[h0:h1, ix[o]] += r[cols["mass_kg"]]
    return np.column_stack([cnt, kg])


def _earth_hourly(track, start_h: float, hours: np.ndarray) -> np.ndarray:
    if not track:
        return np.full((len(hours), 3), np.nan)
    n = int(track["time"]["n"])
    i = (int(round(start_h)) + hours) % n
    el = np.asarray(track["elevation_cdeg"])[i] / 100.0
    rad = np.asarray(track["radius_cdeg"])[i] / 100.0
    brg = np.asarray(track["grid_bearing_cdeg"])[i] / 100.0
    return np.column_stack([el, rad, brg])


def _nearest_trajectory(doc, cls: str, miss: Optional[float], ok) -> Optional[Dict[str, Any]]:
    """The B-33 episode of the classical law for this class whose |miss| is nearest (a failed landing prefers the
    first-failure episode)."""
    if not doc or miss is None:
        return None
    for p in doc["pilots"]:
        if p["cls"] == cls and p["pilot"] == "classical":
            eps = p["episodes"]
            if ok is False:
                fails = [e for e in eps if e["pick"] == "first_failure"]
                if fails:
                    e = fails[0]
                    return {"cls": cls, "pilot": "classical", "pick": e["pick"], "seed": e["seed"], "miss_m": e["miss_m"]}
            e = min(eps, key=lambda e: (abs(e["miss_m"] - miss), e["seed"]))
            return {"cls": cls, "pilot": "classical", "pick": e["pick"], "seed": e["seed"], "miss_m": e["miss_m"]}
    return None


# ---------------------------------------------------------------------------------------------------------
# reading (the Python twin of the JS reader; used by the tests)
# ---------------------------------------------------------------------------------------------------------
def read(pkg_dir: str) -> Dict[str, Any]:
    with open(os.path.join(pkg_dir, "scene.json"), encoding="utf-8") as f:
        idx = json.load(f)
    rb = np.fromfile(os.path.join(pkg_dir, "routes.bin"), dtype="<f4")
    routes = []
    for m in idx["routes"]["items"]:
        o = m["offset"] // 4
        routes.append(rb[o:o + 4 * m["n"]].reshape(m["n"], 4).astype(float))
    segs, hourly = [], []
    for c in idx["chunks"]:
        b = open(os.path.join(pkg_dir, c["file"]), "rb").read()
        s = c["segments"]
        segs.append(np.frombuffer(b, dtype="<f4", count=s["rows"] * s["cols"], offset=s["offset"]).reshape(s["rows"], s["cols"]))
        h = c["hourly"]
        hourly.append(np.frombuffer(b, dtype="<f4", count=h["rows"] * h["cols"], offset=h["offset"]).reshape(h["rows"], h["cols"]))
    return {"index": idx, "routes": routes, "segments": np.vstack(segs).astype(float), "hourly": np.vstack(hourly)}


def replay_counts(pkg: Dict[str, Any]) -> Dict[str, Any]:
    """What a viewer replaying the package counts: delivered kg, trips (distinct non-reposition jobs) and landings."""
    idx = pkg["index"]
    seg = pkg["segments"]
    cols = {c: i for i, c in enumerate(idx["segment_columns"])}
    job_ids = {int(j) for j in seg[:, cols["job"]] if j >= 0}
    kinds = {j[0]: j[1] for j in idx["jobs"]}
    trips = sum(1 for j in job_ids if kinds.get(j) != "reposition")
    return {"delivered_kg": round(sum(d[2] for d in idx["deliveries"]), 3), "trips": trips, "job_ids": job_ids,
            "landings": len(idx["landings"])}


def position(pkg: Dict[str, Any], vid: int, t: float) -> Tuple[float, float, float, str]:
    idx, seg = pkg["index"], pkg["segments"]
    c = {k: i for i, k in enumerate(idx["segment_columns"])}
    m = (seg[:, c["veh"]] == vid) & (seg[:, c["t0"]] <= t) & (seg[:, c["t1"]] > t)
    r = seg[np.flatnonzero(m)[0]]
    state = idx["states"][int(r[c["state"]])]
    g = (t - r[c["t0"]]) / max(r[c["t1"]] - r[c["t0"]], 1e-12)
    if r[c["route"]] >= 0:
        b = pkg["routes"][int(r[c["route"]])]
        f = r[c["f0"]] + (r[c["f1"]] - r[c["f0"]]) * g
        return float(np.interp(f, b[:, 3], b[:, 0])), float(np.interp(f, b[:, 3], b[:, 1])), float(np.interp(f, b[:, 3], b[:, 2])), state
    p0, p1 = r[c["x0"]:c["z0"] + 1], r[c["x1"]:c["z1"] + 1]
    p = p0 + (p1 - p0) * g
    return float(p[0]), float(p[1]), float(p[2]), state


def gz_size(pkg_dir: str) -> int:
    return sum(len(gzip.compress(open(os.path.join(pkg_dir, f), "rb").read(), 9, mtime=0)) for f in sorted(os.listdir(pkg_dir)))


def main(argv=None):
    from .cli import _add_phase3_args, _with_phase3, _mechanism
    ap = argparse.ArgumentParser(description="Write a lunarsim-scene v1 package")
    ap.add_argument("--trace", default=None, help="a lunarsim-trace v2 file")
    ap.add_argument("--scenario", default=None, help="or simulate: a library scenario or a scenario file")
    ap.add_argument("--mechanism", default="marketplace")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-seconds", type=float, default=540.0)
    _add_phase3_args(ap)
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    if a.trace:
        trace = _load_json(a.trace)
    else:
        from .cli import _scenario_ex, _with_file_opts
        from .engine import Simulation
        sc, file_kw = _scenario_ex(a.scenario)
        sc = _with_phase3(sc, a)
        fn, kw = _mechanism(a.mechanism)
        sim = Simulation(sc, fn, seed=a.seed, mech_kwargs=dict(_with_file_opts(a.mechanism, kw, file_kw), trace=True))
        sim.run()
        trace = json.loads(json.dumps(sim.trace_export(mechanism=a.mechanism)))
    idx = build(trace, a.out)
    print(f"wrote {a.out}: {len(idx['chunks'])} chunks, {sum(c['segments']['rows'] for c in idx['chunks'])} segments, "
          f"{len(idx['routes']['items'])} routes; gzip {gz_size(a.out) / 2**20:.2f} MB; checks {idx['checks']}")


if __name__ == "__main__":
    main()
