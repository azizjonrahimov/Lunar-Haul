"""B-61: can a helper park where it sees both Earth and the held rover? (R-1 follow-up; data only, no engine change)

    python tools/comms/parking.py tally         # Stage G2's 0 h and 168 h cells rerun with a per-sample tally of the
                                                # capped intervention waits (cached; nothing written to results CSVs)
    python tools/comms/parking.py candidates    # every set-H sample: route samples within 3 km (line of sight, link,
                                                # network drive)
    python tools/comms/parking.py gridpre       # 40 m grid points within 1.5 km of every set-H sample: line of sight
                                                # to each, reachability (A* component of BASE)
    python tools/comms/parking.py grid --part i --parts 6   # their horizon masks and hourly series (i = 0..5, ~5 min each)
    python tools/comms/parking.py astar         # A* route length from each grid point's nearest route sample
    python tools/comms/parking.py parking       # -> data/comms/connecting_ridge/parking-v1.json, results/E21_parking.json
                                                # (resumable: rerun until it writes the files)

Each step is single process with --max-seconds 540 (default); every step caches in .cache/comms/parking_*.

Set H (the samples where help is needed): every route sample of the engine's samples file (earth_link-v1-samples,
2,421 samples) where a capped wait was tallied, plus the never-linked samples and the 2028 dark sample #188.
Candidates for every sample of H: the route samples within 3 km and the 40 m grid points within 1.5 km (all of H,
no trigger).

A parking point p works for a held sample s when
- terrain line of sight from p to s, both antennas 2.5 m above the ground: Terrain.los_clearance_m > 0 (also
  reported with a 1 m clearance margin);
- it is reachable: a route sample (on the route network), or an off-route point to which the expert A* route
  (lunarsim.rover.expert.plan, no lighting term) from its nearest route sample exists;
- it sees Earth when s does not: DTE-linked (any_part, hourly) in at least one hour 2028-2031 in which s is unlinked
  (the task's question is a point that sees both Earth and the held rover).
Drive distances: on the route network, the engine's leg routes (consecutive samples, each leg scaled to its A*
route length); off-route points add the A* leg from their nearest route sample. Ranking of the working points (LEAD,
B-61): the share of s's calls (tallied capped waits at their call hour = wait start + rescue_h; untallied samples:
s's dark hours 2028-2031) linked within 24 h, then within 168 h, then the share of s's dark hours linked within
168 h, then the shortest drive from s; the first is the best parking point, the file keeps the top 5 and the union
coverage of all working points.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p_ in (ROOT, HERE):
    if p_ not in sys.path:
        sys.path.insert(0, p_)

import earth_link as EL  # noqa: E402
from lunarsim import comms as C  # noqa: E402

CACHE = EL.CACHE
SAMPLES_V1 = EL.SAMPLES_V1
LINK_V1 = EL.OUT
G2_CSV = os.path.join(ROOT, "results", "E21g2_rescue_any_r2.csv")
TALLY = os.path.join(CACHE, "parking_tally.json")
TALLY_H = (0.0, 168.0)            # Stage G2 cells rerun (B-61 step 1)
N_SEEDS = 20


def _load_samples() -> Dict[str, Any]:
    import gzip
    with open(SAMPLES_V1, "rb") as f:
        return json.loads(gzip.decompress(f.read()))


# ---------------------------------------------------------------------------------------------------------
# step 1: where help is needed
# ---------------------------------------------------------------------------------------------------------
def g2_cell(rescue_h: float):
    from experiments.phase4 import run_phase4 as R
    return next(c for c in R.e21g2_cells() if float(c[0]["rescue_h"]) == float(rescue_h))


def tally_run(rescue_h: float, seed: int) -> Dict[str, Any]:
    """One Stage G2 replication with every committed intervention wait logged at its route sample. Returns the
    capped waits (natural wait > rescue_h) as [sample, engine hour, series hour, natural wait h or None (never)]."""
    from experiments.phase4 import run_phase4 as R
    from lunarsim import Simulation
    tag, sc, _, mech, kw = g2_cell(rescue_h)
    yr = R.start_year(seed)
    sc = sc.with_(comms=dict(sc.comms, start_year=yr))
    sim = Simulation(sc, mech, seed=seed, mech_kwargs=dict(kw))
    cm = sim.comms
    cur: List[Tuple[Optional[int], float, float]] = []
    pend: Dict[Any, list] = {}
    events: List[Tuple[Optional[int], float, float]] = []
    o_sw, o_ap, o_cm = cm._sample_wait, cm._apply, cm.commit

    def sample_wait(a, b, u, t):                              # the engine's draw, plus the sample it sits at
        w = o_sw(a, b, u, t)
        try:
            ids = cm.el.leg_samples(f"{cm.name(a)}->{cm.name(b)}")
            sid = ids[min(len(ids) - 1, int(u * len(ids)))]
        except KeyError:
            sid = None
        cur.append((sid, float(t), float(w)))
        return w

    def apply(v, segs, ks, realize):
        del cur[:]
        r = o_ap(v, segs, ks, realize)
        if realize:
            pend[v.id] = list(cur)
        return r

    def commit(sim_, job, t0, t_end):                        # only the committed job's waits count
        for v in job.vehicles:
            events.extend(pend.pop(v.id, []))
        return o_cm(sim_, job, t0, t_end)

    cm._sample_wait, cm._apply, cm.commit = sample_wait, apply, commit
    out = sim.run()
    H = float(sc.horizon_h)
    capped = [[sid, round(t, 4), round((cm.start_h + t) % cm.el.horizon_h, 4), w if math.isfinite(w) else None]
              for sid, t, w in events if w > rescue_h]
    return {"rescue_h": float(rescue_h), "seed": int(seed), "start_year": yr, "horizon_h": H,
            "delivered_t_in_year": out.get("delivered_kg_in_horizon", float("nan")) / 1000.0,
            "rescues": int(out.get("blackout_rescues_never_linked", -1)),
            "interventions_logged": len(events), "capped": capped}


def step_tally(max_seconds: float = 540.0, log=print) -> Dict[str, Any]:
    """Stage G2's 0 h and 168 h cells, 20 seeds each (CRN with Stage A), single process; resumable cache. Each run
    must reproduce its row of results/E21g2_rescue_any_r2.csv exactly, and its tally its rescue count."""
    import pandas as pd
    t0 = time.time()
    doc = json.load(open(TALLY)) if os.path.isfile(TALLY) else {"runs": {}}
    g2 = pd.read_csv(G2_CSV, float_precision="round_trip").set_index(["rescue_h", "seed"])
    todo = [(h, s) for h in TALLY_H for s in range(N_SEEDS) if f"{h:g}/{s}" not in doc["runs"]]
    for h, s in todo:
        if time.time() - t0 > max_seconds - 30:
            log(f"tally: stopping for the time limit; {len(doc['runs'])} of {len(TALLY_H) * N_SEEDS} runs done, rerun")
            break
        r = tally_run(h, s)
        row = g2.loc[(h, s)]
        if r["delivered_t_in_year"] != float(row["delivered_t_in_year"]) or r["rescues"] != int(row["blackout_rescues_never_linked"]):
            raise SystemExit(f"tally run {h:g} h seed {s} does not reproduce its Stage G2 row")
        if len(r["capped"]) != r["rescues"]:
            raise SystemExit(f"tally run {h:g} h seed {s}: {len(r['capped'])} capped waits logged, {r['rescues']} rescues")
        doc["runs"][f"{h:g}/{s}"] = r
        with open(TALLY, "w") as f:
            json.dump(doc, f)
        log(f"tally {h:g} h seed {s}: {r['rescues']} capped waits ({time.time() - t0:.0f} s)")
    log(f"tally: {len(doc['runs'])}/{len(TALLY_H) * N_SEEDS} runs in the cache ({time.time() - t0:.0f} s this call)")
    return doc


def load_tally() -> Dict[str, Any]:
    doc = json.load(open(TALLY)) if os.path.isfile(TALLY) else {"runs": {}}
    if len(doc["runs"]) != len(TALLY_H) * N_SEEDS:
        raise SystemExit("the tally is incomplete; run `tally` again")
    return doc


def set_h(tally: Dict[str, Any], sdoc: Dict[str, Any]) -> Tuple[List[int], List[int]]:
    """(set H sorted, the never-linked samples): tallied samples + never-linked + DARK_SAMPLE."""
    never = [i for i, s in enumerate(sdoc["samples"]) if not sdoc["series"][s["w"][0]]]
    got = {e[0] for r in tally["runs"].values() for e in r["capped"] if e[0] is not None}
    return sorted(got | set(never) | {EL.DARK_SAMPLE}), never


# ---------------------------------------------------------------------------------------------------------
# geometry, links and the route network
# ---------------------------------------------------------------------------------------------------------
ANT_M = EL.ANT_ROVER_M            # Assumed (B-40): 2.5 m antenna on the held rover and on the parked helper
ROUTE_R_M = 3000.0                # Spec (B-61 task): route-sample candidates within 3 km straight line
GRID_R_M = 1500.0                 # Spec (B-61 task): off-route candidates within 1.5 km, 40 m grid
GRID_STEP_M = 40.0
MARGIN_M = 1.0                    # Spec (B-61 task): line of sight also reported with a 1 m clearance margin
DELAYS_H = (0.0, 24.0, 168.0)
CAND = os.path.join(CACHE, "parking_candidates.npz")


def los_batch(terrain, A: np.ndarray, B: np.ndarray, h_a: float = ANT_M, h_b: float = ANT_M,
              step_m: float = 5.0) -> np.ndarray:
    """Terrain.los_clearance_m(A[k], B[k], h_a, h_b, step_m) for many pairs at once, with the same arithmetic
    (profile: np.linspace stations, f = s / L, bilinear 5 m heights; chord bulge s (L - s) / 2R)."""
    from lunarsim.terrain import MOON_RADIUS_M
    A, B = np.asarray(A, float).reshape(-1, 2), np.asarray(B, float).reshape(-1, 2)
    out = np.empty(len(A))
    S, X, Y, cut, Ls = [], [], [], [0], []
    for k, (a, b) in enumerate(zip(A, B)):
        L = float(np.hypot(*(b - a)))
        n = max(1, int(math.ceil(L / step_m)))
        s = np.linspace(0.0, L, n + 1)
        f = s / L if L > 0 else np.zeros_like(s)
        S.append(s)
        X.append(a[0] + f * (b[0] - a[0]))
        Y.append(a[1] + f * (b[1] - a[1]))
        cut.append(cut[-1] + len(s))
        Ls.append(L)
    if not len(A):
        return out
    s, z = np.concatenate(S), terrain.height(np.concatenate(X), np.concatenate(Y))
    for k, L in enumerate(Ls):
        sk, zk = s[cut[k]:cut[k + 1]], z[cut[k]:cut[k + 1]]
        if L <= 0:
            out[k] = float(h_a)
            continue
        if len(sk) <= 2:
            out[k] = float(min(h_a, h_b))
            continue
        za, zb = zk[0] + h_a, zk[-1] + h_b
        line = za + (zb - za) * sk / L
        bulge = sk * (L - sk) / (2 * MOON_RADIUS_M)
        out[k] = float(np.min(line[1:-1] - (zk[1:-1] + bulge[1:-1])))
    return out


def hourly_linked(sdoc: Dict[str, Any]) -> np.ndarray:
    """(samples, hours) DTE any_part hourly link of every sample, 2028-2031."""
    n = int(sdoc["time"]["n"])
    out = np.zeros((len(sdoc["samples"]), n), dtype=bool)
    for i, s in enumerate(sdoc["samples"]):
        out[i] = C.windows_to_mask(C.decode_windows(sdoc["series"][s["w"][0]]), n)
    return out


def wait_until_linked(linked: np.ndarray) -> np.ndarray:
    """Hours from each hour until the series is linked (0 when linked), the series repeated after its end as the
    engine does (wrap); inf when it is never linked."""
    n = len(linked)
    if not linked.any():
        return np.full(n, np.inf)
    idx = np.where(np.concatenate([linked, linked]), np.arange(2 * n), 4 * n)
    nxt = np.minimum.accumulate(idx[::-1])[::-1][:n]
    return (nxt - np.arange(n)).astype(float)


def network(sdoc: Dict[str, Any], link: Dict[str, Any]):
    """Undirected graph of the engine's route network: consecutive samples of every leg, each leg's chords scaled
    to its A* route length (earth_link-v1.json legs[leg].length_m). Returns (csr matrix, xy)."""
    from scipy.sparse import csr_matrix
    xy = np.array([s["xy_m"] for s in sdoc["samples"]], dtype=float)
    best: Dict[Tuple[int, int], float] = {}
    for leg, ids in sdoc["legs"].items():
        if len(ids) < 2:
            continue
        seg = np.hypot(*np.diff(xy[ids], axis=0).T)
        k = float(link["legs"][leg]["length_m"]) / float(seg.sum())
        for a, b, w in zip(ids[:-1], ids[1:], seg * k):
            key = (min(a, b), max(a, b))
            if a != b and w < best.get(key, math.inf):
                best[key] = float(w)
    ij = np.array(list(best), dtype=int).reshape(-1, 2)
    n = len(xy)
    return csr_matrix((list(best.values()), (ij[:, 0], ij[:, 1])), shape=(n, n)), xy


def step_candidates(log=print) -> Dict[str, Any]:
    """Every set-H sample against the route samples within 3 km: clearance, whether the candidate is linked in an hour
    when s is not, network drive from s. Cached in .cache/comms/parking_candidates.npz."""
    from scipy.sparse.csgraph import connected_components, dijkstra
    from lunarsim.terrain import Terrain
    t0 = time.time()
    sdoc = _load_samples()
    link = json.load(open(LINK_V1))
    H, never = set_h(load_tally(), sdoc)
    G, xy = network(sdoc, link)
    ncomp, lab = connected_components(G, directed=False)
    if ncomp != 1:
        raise SystemExit(f"the route network has {ncomp} components")
    D = dijkstra(G, directed=False, indices=H)
    D_base = dijkstra(G, directed=False, indices=[0])[0]
    Lk = np.packbits(hourly_linked(sdoc), axis=1)
    terrain = Terrain(EL.PACK)
    rows = {k: [] for k in ("s", "p", "dist_m", "clear_m", "helps", "drive_m")}
    for j, s in enumerate(H):
        d = np.hypot(*(xy - xy[s]).T)
        cand = np.flatnonzero((d <= ROUTE_R_M) & (np.arange(len(xy)) != s))
        clear = los_batch(terrain, xy[cand], np.repeat(xy[s][None], len(cand), axis=0))
        helps = (Lk[cand] & ~Lk[s]).any(axis=1)
        rows["s"].append(np.full(len(cand), s))
        rows["p"].append(cand)
        rows["dist_m"].append(d[cand])
        rows["clear_m"].append(clear)
        rows["helps"].append(helps)
        rows["drive_m"].append(D[j, cand])
        if (j + 1) % 100 == 0:
            log(f"candidates: {j + 1}/{len(H)} samples ({time.time() - t0:.0f} s)")
    out = {k: np.concatenate(v) for k, v in rows.items()}
    # the batch clearance must equal Terrain.los_clearance_m exactly
    rng = np.random.default_rng(61)
    chk = rng.choice(len(out["p"]), size=300, replace=False)
    for k in chk:
        a, b = xy[out["p"][k]], xy[out["s"][k]]
        if terrain.los_clearance_m(tuple(a), tuple(b), h_a=ANT_M, h_b=ANT_M) != out["clear_m"][k]:
            raise SystemExit("los_batch differs from Terrain.los_clearance_m")
    np.savez(CAND, H=np.array(H), never=np.array(never), D_base=D_base, **out)
    work = (out["clear_m"] > 0) & out["helps"]
    no_sol = sorted(set(H) - set(out["s"][work].tolist()))
    log(f"candidates: {len(H)} samples, {len(out['p'])} pairs within {ROUTE_R_M / 1000:g} km, {int(work.sum())} working; "
        f"{len(no_sol)} samples without a route-sample solution; 300 clearances equal los_clearance_m "
        f"({time.time() - t0:.0f} s)")
    return out


# ---------------------------------------------------------------------------------------------------------
# step 2b: off-route points on a 40 m grid within 1.5 km
# ---------------------------------------------------------------------------------------------------------
GRID_PRE = os.path.join(CACHE, "parking_gridpre.npz")
EDGE_M = 100.0                    # grid points kept this far inside the 16 km tile (the masks' 5 m near DEM)


def reach_labels(terrain) -> Tuple[np.ndarray, int]:
    """8-connected components of the passable 20 m cells of the expert A* cost grid (no lighting term) and the label
    of BASE's cell: A* (lunarsim.rover.expert.plan, whose last try searches the whole grid) finds a route between two
    passable cells exactly when they share a label."""
    from scipy import ndimage
    from lunarsim.rover.expert import cost_grid
    lab, _ = ndimage.label(np.isfinite(cost_grid(terrain, None)), structure=np.ones((3, 3), dtype=int))
    bx, by = terrain.sites()["base_xy_m"]
    j, i = terrain.cell(bx, by)
    return lab, int(lab[int(j), int(i)])


def step_gridpre(max_seconds: float = 540.0, log=print) -> Dict[str, Any]:
    """Grid points (40 m lattice, cell centres) within 1.5 km of every set-H sample, inside the tile; line of sight to
    each such sample; reachability. Keeps the points that see at least one set-H sample and are reachable."""
    from scipy.spatial import cKDTree
    from lunarsim.terrain import Terrain
    t0 = time.time()
    sdoc = _load_samples()
    H, _ = set_h(load_tally(), sdoc)
    xy = np.array([s["xy_m"] for s in sdoc["samples"]], dtype=float)
    terrain = Terrain(EL.PACK)
    lab, base_lab = reach_labels(terrain)
    j, i = terrain.cell(xy[:, 0], xy[:, 1])
    off = lab[j, i] != base_lab
    if off.any():
        raise SystemExit(f"{int(off.sum())} route samples lie outside BASE's passable component")
    W, Hm = terrain.size_m
    g = np.arange(GRID_STEP_M / 2, max(W, Hm), GRID_STEP_M)
    keep = {"s": [], "g": [], "clear_m": []}
    ids: Dict[Tuple[int, int], int] = {}
    gxy: List[Tuple[float, float]] = []
    for k, s in enumerate(H):
        if time.time() - t0 > max_seconds - 30:
            raise SystemExit("gridpre: out of time before finishing; raise --max-seconds (one pass is ~5 min)")
        sx, sy = xy[s]
        cx = g[(g >= max(EDGE_M, sx - GRID_R_M)) & (g <= min(W - EDGE_M, sx + GRID_R_M))]
        cy = g[(g >= max(EDGE_M, sy - GRID_R_M)) & (g <= min(Hm - EDGE_M, sy + GRID_R_M))]
        X, Y = np.meshgrid(cx, cy)
        X, Y = X.ravel(), Y.ravel()
        m = (X - sx) ** 2 + (Y - sy) ** 2 <= GRID_R_M ** 2
        X, Y = X[m], Y[m]
        jj, ii = terrain.cell(X, Y)
        r = lab[jj, ii] == base_lab
        X, Y = X[r], Y[r]
        clear = los_batch(terrain, np.stack([X, Y], axis=1), np.repeat(xy[s][None], len(X), axis=0))
        vis = clear > 0
        for x_, y_, c_ in zip(X[vis], Y[vis], clear[vis]):
            key = (int(round(x_ / GRID_STEP_M - 0.5)), int(round(y_ / GRID_STEP_M - 0.5)))
            if key not in ids:
                ids[key] = len(gxy)
                gxy.append((float(x_), float(y_)))
            keep["s"].append(s)
            keep["g"].append(ids[key])
            keep["clear_m"].append(float(c_))
        if (k + 1) % 50 == 0:
            log(f"gridpre: {k + 1}/{len(H)} samples, {len(gxy)} grid points so far ({time.time() - t0:.0f} s)")
    G = np.array(gxy, dtype=float)
    q_d, q = cKDTree(xy).query(G)
    np.savez(GRID_PRE, H=np.array(H), gxy=G, near_sample=q, near_dist_m=q_d,
             s=np.array(keep["s"]), g=np.array(keep["g"]), clear_m=np.array(keep["clear_m"]))
    log(f"gridpre: {len(G)} reachable grid points see at least one of {len(H)} samples ({len(keep['s'])} pairs) "
        f"({time.time() - t0:.0f} s)")
    return {"n_points": len(G), "n_pairs": len(keep["s"])}


def link_series(P: List[Dict[str, Any]], near, far, bearings, E, P_base, x0, y0) -> Tuple[np.ndarray, List[List[int]]]:
    """Horizon masks and hourly DTE any_part windows (encoded) of observation points {x, y, z, h_ant} (local metres),
    with the arithmetic of earth_link.py masks / series2."""
    n, k_h = len(E), EL.SAMPLE_STEP_MIN // EL.STEP_MIN
    M = EL.horizon_wedge(np.array([p["x"] + x0 for p in P]), np.array([p["y"] + y0 for p in P]),
                         np.array([p["z"] for p in P]), np.array([p["h_ant"] for p in P]), bearings, near, far)
    codes = []
    for i, (p, row) in enumerate(zip(P, M)):
        s = EL.point_link(p, row, E, P_base, x0, y0, bearings, i)["any_part"]
        codes.append(C.encode_windows(C.runs(s[: n - n % k_h].reshape(-1, k_h).all(axis=1))))
    return M, codes


def step_grid(part: int = 0, parts: int = 1, log=print) -> None:
    """Horizon masks (2.5 m antenna, 5 m tile to 8 km + 80 m LDEM to 300 km, the B-40 way) and hourly DTE windows
    (any_part: an hour linked only when all six 10-min epochs are) of one chunk of the grid points (cached)."""
    t0 = time.time()
    meta, _ = EL.load_pack()
    d = np.load(GRID_PRE)
    G = d["gxy"]
    sel = np.array_split(np.arange(len(G)), parts)[part]
    bearings, _ = EL.wedge_bearings()
    near, _ = EL.near_sampler(meta)
    far = EL.far_sampler()
    x0, y0 = meta["origin_xy_m"]
    e = np.load(EL.ephem_path())
    E, P_base = e["E_base_km"], e["P_base_km"]
    pts = [{"x": round(float(x), 2), "y": round(float(y), 2), "h_ant": ANT_M} for x, y in G[sel]]
    z = near(np.array([p["x"] + x0 for p in pts]), np.array([p["y"] + y0 for p in pts]))
    for p, z_ in zip(pts, z):
        p["z"] = round(float(z_), 3)
    out: Dict[str, Any] = {}
    masks = np.full((len(sel), len(bearings)), np.nan, dtype=np.float32)
    batch = 250
    for k in range(0, len(sel), batch):
        P = pts[k:k + batch]
        masks[k:k + len(P)], codes = link_series(P, near, far, bearings, E, P_base, x0, y0)
        for p, i, code in zip(P, sel[k:k + batch].tolist(), codes):
            out[str(i)] = {"z": p["z"], "w": code}
        log(f"grid part {part}/{parts}: {min(k + batch, len(sel))}/{len(sel)} points ({time.time() - t0:.0f} s)")
    np.savez(os.path.join(CACHE, f"parking_gridmask_{part:02d}of{parts:02d}.npz"), idx=sel, mask=masks, bearings=bearings)
    with open(os.path.join(CACHE, f"parking_grid_{part:02d}of{parts:02d}.json"), "w") as f:
        json.dump(out, f)
    log(f"grid part {part}/{parts}: {len(sel)} points in {time.time() - t0:.0f} s")


ASTAR = os.path.join(CACHE, "parking_astar.npz")


def step_astar(max_seconds: float = 540.0, log=print) -> None:
    """Length (m) of the expert A* route (lunarsim.rover.expert.plan, no lighting term) from each grid point's nearest
    route sample to the point; NaN = no route. Resumable cache."""
    from lunarsim.rover.expert import plan
    from lunarsim.terrain import Terrain
    t0 = time.time()
    d = np.load(GRID_PRE)
    xy = np.array([s["xy_m"] for s in _load_samples()["samples"]], dtype=float)
    G, q = d["gxy"], d["near_sample"]
    L = np.load(ASTAR)["astar_m"] if os.path.isfile(ASTAR) else np.full(len(G), -1.0)
    terrain = Terrain(EL.PACK)
    todo = np.flatnonzero(L < 0)
    for k, g in enumerate(todo):
        if time.time() - t0 > max_seconds - 30:
            break
        poly = plan(terrain, tuple(xy[q[g]]), tuple(G[g]), None)
        L[g] = np.nan if poly is None else float(np.hypot(*np.diff(poly, axis=0).T).sum())
        if (k + 1) % 2000 == 0:
            np.savez(ASTAR, astar_m=L)
            log(f"astar: {int((L >= 0).sum() + np.isnan(L).sum())}/{len(G)} ({time.time() - t0:.0f} s)")
    np.savez(ASTAR, astar_m=L)
    left = int((L < 0).sum())
    log(f"astar: {len(G) - left}/{len(G)} grid points done, {int(np.isnan(L).sum())} without a route"
        + (f"; {left} left, rerun" if left else "") + f" ({time.time() - t0:.0f} s)")


def load_grid() -> Tuple[Dict[str, np.ndarray], Dict[str, Any]]:
    d = dict(np.load(GRID_PRE))
    files = sorted(f for f in os.listdir(CACHE) if f.startswith("parking_grid_") and f.endswith(".json"))
    if len({int(f.split("of")[1][:2]) for f in files}) > 1:
        raise SystemExit(f"grid files from different --parts runs: {files}; delete the stale ones")
    got: Dict[str, Any] = {}
    for f in files:
        got.update(json.load(open(os.path.join(CACHE, f))))
    miss = len(d["gxy"]) - len(got)
    if miss:
        raise SystemExit(f"{miss} grid points have no series; run the missing `grid --part` chunks")
    return d, got


def load_grid_masks(n_points: int) -> Tuple[np.ndarray, np.ndarray]:
    M, bearings = None, None
    for f in sorted(f for f in os.listdir(CACHE) if f.startswith("parking_gridmask_") and f.endswith(".npz")):
        d = np.load(os.path.join(CACHE, f))
        if M is None:
            bearings = d["bearings"]
            M = np.full((n_points, len(bearings)), np.nan, dtype=np.float32)
        M[d["idx"]] = d["mask"]
    if M is None or not np.isfinite(M).any(axis=1).all():
        raise SystemExit("grid masks incomplete; run the `grid --part` chunks")
    return M, bearings


# ---------------------------------------------------------------------------------------------------------
# steps 3-5: working points, the best parking point, help delays, diagnostics
# ---------------------------------------------------------------------------------------------------------
OUT = os.path.join(ROOT, "data", "comms", "connecting_ridge", "parking-v1.json")
SUMMARY = os.path.join(ROOT, "results", "E21_parking.json")
WORK = os.path.join(CACHE, "parking_work.pkl")
PARKING_FORMAT, PARKING_VERSION = "lunarsim-parking", 1
TOP_K = 5                         # LEAD (B-61): the parking file keeps each sample's five best working points
RECHECK = 12                      # v1 route samples recomputed with the grid code; must reproduce their series
MEASURES = ("best", "route", "grid", "all", "all_1500m", "all_margin_1m")
BLOCK = 64


def waits_at(win: np.ndarray, hours: np.ndarray, n: int) -> np.ndarray:
    """wait_until_linked(windows_to_mask(win, n))[hours], from the windows directly."""
    hours = np.asarray(hours, dtype=np.int64)
    if len(win) == 0:
        return np.full(len(hours), np.inf)
    st, en = win[:, 0], win[:, 1]
    j = np.searchsorted(en, hours, side="right")
    jj = np.minimum(j, len(win) - 1)
    inside = (j < len(win)) & (st[jj] <= hours)
    nxt = np.where(j < len(win), st[jj], st[0] + n)
    return np.where(inside, 0, nxt - hours).astype(float)


def _counts(W: np.ndarray) -> List[int]:
    return [int((W <= x).sum()) for x in DELAYS_H]


def _share(c: Sequence[int], n: int) -> Optional[List[float]]:
    return [round(v / n, 5) for v in c] if n else None


def _hourly_all(m10: np.ndarray, n: int) -> np.ndarray:
    k_h = EL.SAMPLE_STEP_MIN // EL.STEP_MIN
    return m10[: n * k_h].reshape(n, k_h).all(axis=1)


def _inputs() -> Dict[str, str]:
    meta, _ = EL.load_pack()
    files = [SAMPLES_V1, LINK_V1, G2_CSV, os.path.join(EL.PACK, "meta.json"), os.path.join(EL.PACK, "sites.json"),
             os.path.join(EL.PACK, meta["layers"]["height_5m"]["file"]), os.path.join(EL.PACK, meta["layers"]["slope_20m"]["file"]),
             EL.ephem_path(), EL.far_window_path()]
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import terrain_assets as ta
    dem = ta.default_dem(meta)
    if dem:
        files.append(dem)
    return {EL._rel(p): EL.sha256(p) for p in files}


def _calls(tally: Dict[str, Any], n: int) -> Dict[int, Dict[str, np.ndarray]]:
    """Per tallied sample: call hour (series hour of the wait start + rescue_h), cell, start year, natural wait hours
    inside the simulated year (the hours the rover would be held without help), series hour of the wait start."""
    rows: Dict[int, List[Tuple[int, float, int, float, float]]] = {}
    for r in tally["runs"].values():
        for sid, t, sh, w in r["capped"]:
            nat = min(w if w is not None else math.inf, r["horizon_h"] - t)
            rows.setdefault(sid, []).append((int(math.floor(sh + r["rescue_h"] + 1e-9)) % n, r["rescue_h"],
                                             r["start_year"], nat, sh))
    return {s: {k: np.array([e[j] for e in v]) for j, k in enumerate(("hour", "cell", "year", "nat_h", "start_h"))}
            for s, v in rows.items()}


def _sample_point(pdoc: Dict[str, Any], used: List[int], s: int) -> Dict[str, Any]:
    return pdoc["points"][used[s]]


def _earth_at(p: Dict[str, Any], E, P_base, x0, y0):
    X, Y = p["x"] + x0, p["y"] + y0
    lat, lon = EL.latlon_deg(X, Y)
    P = EL.stereo_unit(X, Y) * (EL.R_MOON_M + p["z"] + p["h_ant"]) / 1000.0
    _, el, brg, rad = EL.earth_topo(E, P_base, P, float(lat), float(lon))
    return el, brg, rad


def _interp_rows(M: np.ndarray, bearings: np.ndarray, brg: np.ndarray) -> np.ndarray:
    """Horizons (k, m) of mask rows M (k, bearings; NaN = open sky = -90 deg) at grid bearings brg (m)."""
    Mf = np.where(np.isnan(M), -90.0, M)
    step = float(bearings[1] - bearings[0])
    u = np.clip((brg - bearings[0]) / step, 0, len(bearings) - 1 - 1e-9)
    i0 = np.floor(u).astype(int)
    f = u - i0
    return Mf[:, i0] * (1 - f) + Mf[:, i0 + 1] * f


def work_sample(s: int, ctx: Dict[str, Any]) -> Dict[str, Any]:
    """All B-61 quantities of one set-H sample (pure function of the caches; see the module docstring)."""
    n, Lk, xy, D, D_base = ctx["n"], ctx["Lk"], ctx["xy"], ctx["D"], ctx["D_base"]
    rc, gp, astar, win_r, win_g = ctx["rc"], ctx["gp"], ctx["astar"], ctx["win_r"], ctx["win_g"]
    k = ctx["Hix"][s]
    dark = ~Lk[s]
    cd = np.concatenate([[0], np.cumsum(dark)])
    rm = ctx["rows_r"][s]
    r_p, r_clear, r_help, r_dist = rc["p"][rm], rc["clear_m"][rm], rc["helps"][rm], rc["dist_m"][rm]
    gm = ctx["rows_g"][s]
    g_g, g_clear = gp["g"][gm], gp["clear_m"][gm]
    g_help = np.array([len(w) > 0 and bool(np.any(cd[w[:, 1]] - cd[w[:, 0]] > 0)) for w in (win_g[g] for g in g_g)],
                      dtype=bool)
    rw, gw = (r_clear > 0) & r_help, (g_clear > 0) & g_help
    gq = gp["near_sample"][g_g[gw]]
    kind = np.concatenate([np.zeros(int(rw.sum()), dtype=int), np.ones(int(gw.sum()), dtype=int)])
    ids = np.concatenate([r_p[rw], g_g[gw]]).astype(int)
    clear = np.concatenate([r_clear[rw], g_clear[gw]])
    dist = np.concatenate([r_dist[rw], np.hypot(*(gp["gxy"][g_g[gw]] - xy[s]).T)])
    drive = np.concatenate([D[k, r_p[rw]], D[k, gq] + astar[g_g[gw]]])
    bdrive = np.concatenate([D_base[r_p[rw]], D_base[gq] + astar[g_g[gw]]])
    nw = len(ids)
    Mk = np.zeros((nw, n), dtype=bool)
    Mk[: int(rw.sum())] = Lk[r_p[rw]]
    for j, g in enumerate(g_g[gw], start=int(rw.sum())):
        for a_, b_ in win_g[g]:
            Mk[j, a_:b_] = True
    ev = ctx["calls"].get(s)
    hours = ev["hour"] if ev is not None else np.flatnonzero(dark)
    cnt = np.zeros((nw, 3), dtype=np.int64)
    cnt_d = np.zeros((nw, 3), dtype=np.int64)                # the same over s's dark hours
    dh = np.flatnonzero(dark)
    ar = np.arange(2 * n, dtype=np.int32)
    for b0 in range(0, nw, BLOCK):                           # hours until linked, a block of candidates at a time
        blk = np.concatenate([Mk[b0:b0 + BLOCK], Mk[b0:b0 + BLOCK]], axis=1)
        idx = np.where(blk, ar, 4 * n)
        nxt = np.minimum.accumulate(idx[:, ::-1], axis=1)[:, ::-1]
        for c_, hh in ((cnt, hours), (cnt_d, dh)):
            W = nxt[:, hh] - hh
            c_[b0:b0 + BLOCK] = np.stack([(W <= x).sum(axis=1) for x in DELAYS_H], axis=1)
    # LEAD (B-61): calls within 24 h, then 168 h, then dark hours within 168 h, then the shortest drive
    order = np.lexsort((drive, -cnt_d[:, 2], -cnt[:, 2], -cnt[:, 1])) if nw else np.zeros(0, dtype=int)
    U = {"route": kind == 0, "grid": kind == 1, "all": np.ones(nw, dtype=bool), "all_1500m": dist <= GRID_R_M,
         "all_margin_1m": clear > MARGIN_M}
    Wu = {m: wait_until_linked(Mk[sel].any(axis=0)) for m, sel in U.items()}
    Wu["best"] = wait_until_linked(Mk[order[0]]) if nw else np.full(n, np.inf)
    out: Dict[str, Any] = {
        "s": s, "never": s in ctx["never"], "basis": "calls" if ev is not None else "dark_hours",
        "n_basis": int(len(hours)), "n_route": int(len(rm)), "n_route_los": int((r_clear > 0).sum()),
        "n_grid_los": int(len(gm)), "n_work_route": int(rw.sum()), "n_work_grid": int(gw.sum()),
        "n_work_margin": int((clear > MARGIN_M).sum()),
        "top": [{"kind": int(kind[j]), "id": int(ids[j]), "counts": cnt[j].tolist(), "dark_counts": cnt_d[j].tolist(),
                 "drive_m": float(drive[j]),
                 "base_drive_m": float(bdrive[j]), "dist_m": float(dist[j]), "clear_m": float(clear[j]),
                 "near_sample": int(gp["near_sample"][ids[j]]) if kind[j] == 1 else None,
                 "access_m": float(astar[ids[j]]) if kind[j] == 1 else None} for j in order[:TOP_K]],
        "coverage": {m: _counts(Wu[m][hours]) for m in MEASURES},
        "dark": {"n": int(dark.sum()), "best": _counts(Wu["best"][dark]), "all": _counts(Wu["all"][dark])},
        "nearest_working": None,
    }
    if nw:
        j = int(np.argmin(dist))
        out["nearest_working"] = {"kind": int(kind[j]), "id": int(ids[j]), "dist_m": float(dist[j]),
                                  "drive_m": float(drive[j]), "link_fraction": float(Mk[j].mean())}
    if s in ctx["keep_w"]:
        out["W"] = {m: Wu[m].astype(np.float32) for m in ("best", "all")}
    if ev is None:
        return out
    # per call and per held hour, by cell and start year
    acc: Dict[str, List[int]] = {}
    for basis in ("call", "held_hour"):
        for cell in TALLY_H:
            for yr in sorted(set(ev["year"].tolist())):
                sel = (ev["cell"] == cell) & (ev["year"] == yr)
                if not sel.any():
                    continue
                if basis == "call":
                    hh = ev["hour"][sel]
                else:
                    hh = np.concatenate([(int(math.floor(st)) + np.arange(int(math.ceil(L)))) % n
                                         for st, L in zip(ev["start_h"][sel], ev["nat_h"][sel])])
                for m in MEASURES:
                    acc[f"{basis}|{cell:g}|{yr}|{m}"] = [int(len(hh))] + _counts(Wu[m][hh])
    out["acc"] = acc
    # B-61 (3): calls no working point links within 168 h: Earth against the lowest horizon among s's candidates
    el, brg, rad = _earth_at(_sample_point(ctx["pdoc"], ctx["used"], s), ctx["E"], ctx["P_base"], ctx["x0"], ctx["y0"])
    el_up = el + rad
    Mc = np.concatenate([ctx["Mr"][[ctx["used"][p] for p in r_p[r_clear > 0]]], ctx["Mg"][g_g]], axis=0)
    Mc = np.where(np.isnan(Mc), -90.0, Mc)                   # NaN = no terrain sampled = open sky
    env = Mc.min(axis=0)
    hz_env = _interp_rows(env[None, :], ctx["bearings"], brg)[0]
    W_env = wait_until_linked(_hourly_all(el_up > hz_env, n))
    W_lvl = wait_until_linked(_hourly_all(el_up > 0.0, n))
    k_h = EL.SAMPLE_STEP_MIN // EL.STEP_MIN
    e6 = (ev["hour"].astype(np.int64)[:, None] * k_h + np.arange(k_h)).ravel()     # the six epochs of every call
    hz = np.concatenate([_interp_rows(Mc, ctx["bearings"], brg[e6[i:i + 600]]).min(axis=0)
                         for i in range(0, len(e6), 600)]).reshape(-1, k_h)
    own = _interp_rows(ctx["Mr"][[ctx["used"][s]]], ctx["bearings"], brg[e6])[0].reshape(-1, k_h)
    up = el_up[e6].reshape(-1, k_h)
    jm = np.argmax(up - hz, axis=1)                          # the epoch of the call hour where Earth is highest above it
    rr = np.arange(len(jm))
    out["diag"] = [[float(cell), int(yr), round(float(a), 3), round(float(b), 3), round(float(o), 3), float(W_env[c]),
                    float(W_lvl[c]), float(Wu["all"][c]), float(ctx["W_mast"][c])]
                   for cell, yr, a, b, o, c in zip(ev["cell"], ev["year"], up[rr, jm], hz[rr, jm], own[rr, jm], ev["hour"])]
    # two hops through the BASE mast: a candidate (line of sight to s, reachable) that also sees the 10 m mast;
    # only needed where some call gets no direct help within 168 h
    two = None
    if (Wu["all"][ev["hour"]] > 168).any():
        two = bool(ctx["mast_los_r"][r_p[r_clear > 0]].any()) or any(ctx["mast_los_g"](int(g)) for g in g_g)
    out["two_hop_candidate"] = two
    return out


def step_parking(max_seconds: float = 540.0, log=print) -> Optional[Dict[str, Any]]:
    """Per set-H sample (resumable, cached in parking_work.pkl), then the data file and the results summary."""
    import pickle
    from scipy.sparse.csgraph import dijkstra
    from lunarsim.terrain import Terrain
    t0 = time.time()
    sdoc = _load_samples()
    link = json.load(open(LINK_V1))
    tally = load_tally()
    H, never = set_h(tally, sdoc)
    n = int(sdoc["time"]["n"])
    G, xy = network(sdoc, link)
    rc = dict(np.load(CAND))
    gp, gser = load_grid()
    if not (np.array_equal(rc["H"], H) and np.array_equal(gp["H"], H)):
        raise SystemExit("set H changed since `candidates` / `gridpre`; rerun them")
    astar = np.load(ASTAR)["astar_m"]
    if (astar < 0).any() or np.isnan(astar).any():
        raise SystemExit("A* lengths missing; run `astar`")
    meta, sites = EL.load_pack()
    x0, y0 = meta["origin_xy_m"]
    pdoc = json.load(open(os.path.join(CACHE, "points.json")))
    used = sorted({k for ids in pdoc["legs"].values() for k in ids})
    if len(used) != len(sdoc["samples"]):
        raise SystemExit("points.json does not match the v1 samples file")
    Mr, bearings = EL.load_masks()
    Mg, bg = load_grid_masks(len(gp["gxy"]))
    if not np.array_equal(bearings, bg):
        raise SystemExit("grid mask bearings differ from the v1 masks")
    e = np.load(EL.ephem_path())
    E, P_base = e["E_base_km"], e["P_base_km"]
    terrain = Terrain(EL.PACK)
    bx, by = sites["base_xy_m"]
    mast_g: Dict[int, bool] = {}

    def mast_los_g(g: int) -> bool:
        if g not in mast_g:
            x, y = gp["gxy"][g]
            mast_g[g] = EL.sees_mast(terrain, {"x": float(x), "y": float(y)}, bx, by)
        return mast_g[g]

    m10 = C.windows_to_mask(C.decode_windows(link["mast"]["windows"]["any_part"]), len(E))
    ctx = {"n": n, "Lk": hourly_linked(sdoc), "xy": xy, "D": dijkstra(G, directed=False, indices=H),
           "D_base": dijkstra(G, directed=False, indices=[0])[0], "rc": rc, "gp": gp, "astar": astar,
           "win_r": [C.decode_windows(sdoc["series"][s_["w"][0]]) for s_ in sdoc["samples"]],
           "win_g": [C.decode_windows(gser[str(g)]["w"]) for g in range(len(gp["gxy"]))],
           "Hix": {s: k for k, s in enumerate(H)}, "never": set(never), "calls": _calls(tally, n),
           "keep_w": {EL.DARK_SAMPLE, 4}, "pdoc": pdoc, "used": used, "Mr": Mr, "Mg": Mg, "bearings": bearings,
           "E": E, "P_base": P_base, "x0": x0, "y0": y0, "W_mast": wait_until_linked(_hourly_all(m10, n)),
           "mast_los_r": np.array([bool(s_["mast_los"]) for s_ in sdoc["samples"]]), "mast_los_g": mast_los_g}
    o_r, o_g = np.argsort(rc["s"], kind="stable"), np.argsort(gp["s"], kind="stable")
    ctx["rows_r"] = {int(s): o_r[a:b] for s, a, b in _runs_of(rc["s"][o_r])}
    ctx["rows_g"] = {int(s): o_g[a:b] for s, a, b in _runs_of(gp["s"][o_g])}
    for s in H:
        ctx["rows_r"].setdefault(s, np.zeros(0, dtype=int))
        ctx["rows_g"].setdefault(s, np.zeros(0, dtype=int))
    done: Dict[int, Any] = pickle.load(open(WORK, "rb")) if os.path.isfile(WORK) else {}
    if done.get("_H") != H:
        done = {"_H": H}
    for s in H:
        if s in done:
            continue
        if time.time() - t0 > max_seconds - 60:
            pickle.dump(done, open(WORK, "wb"))
            log(f"parking: {len(done) - 1}/{len(H)} samples done; out of time, rerun to continue")
            return None
        done[s] = work_sample(s, ctx)
        if len(done) % 50 == 0:
            pickle.dump(done, open(WORK, "wb"))
            log(f"parking: {len(done) - 1}/{len(H)} samples ({time.time() - t0:.0f} s)")
    pickle.dump(done, open(WORK, "wb"))
    # determinism: v1 route samples recomputed with the grid code reproduce their v1 hourly series
    near, _ = EL.near_sampler(meta)
    far = EL.far_sampler()
    rng = np.random.default_rng(61)
    chk = sorted(rng.choice(np.arange(17, len(used)), size=RECHECK, replace=False).tolist())
    P = []
    for s in chk:
        p = dict(pdoc["points"][used[s]])
        z = round(float(near(np.array([p["x"] + x0]), np.array([p["y"] + y0]))[0]), 3)
        if z != p["z"]:
            raise SystemExit(f"sample {s}: height {z} differs from points.json {p['z']}")
        P.append(p)
    _, codes = link_series(P, near, far, bearings, E, P_base, x0, y0)
    for s, code in zip(chk, codes):
        if code != sdoc["series"][sdoc["samples"][s]["w"][0]]:
            raise SystemExit(f"sample {s}: the grid code does not reproduce its v1 series")
    log(f"parking: {RECHECK} v1 route samples recomputed with the grid code, identical")
    res = {s: done[s] for s in H}
    doc = _parking_doc(res, sdoc, gp, gser, astar, ctx, meta)
    summ = _summary(res, sdoc, tally, H, never, ctx, doc)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(doc, f, separators=(",", ":"))
    rss = EL.peak_rss_mb()
    summ["peak_rss_mb"] = round(rss) if rss else None
    summ["parking_file"] = {"file": EL._rel(OUT), "sha256": EL.sha256(OUT)}
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump(summ, f, indent=1)
    log(f"parking: -> {EL._rel(OUT)} ({os.path.getsize(OUT) / 1024:.0f} KB), {EL._rel(SUMMARY)} ({time.time() - t0:.0f} s)")
    return summ


def _parking_doc(res: Dict[int, Any], sdoc, gp, gser, astar, ctx, meta) -> Dict[str, Any]:
    n, Lk = ctx["n"], ctx["Lk"]
    points: List[Dict[str, Any]] = []
    pix: Dict[Tuple[int, int], int] = {}

    def point(t: Dict[str, Any]) -> int:
        key = (t["kind"], t["id"])
        if key not in pix:
            pix[key] = len(points)
            if t["kind"] == 0:
                points.append({"kind": "route", "sample": t["id"], "xy_m": sdoc["samples"][t["id"]]["xy_m"],
                               "base_drive_km": round(t["base_drive_m"] / 1000, 3),
                               "link_fraction": round(float(Lk[t["id"]].mean()), 5)})
            else:
                w = ctx["win_g"][t["id"]]
                points.append({"kind": "grid", "xy_m": [round(float(v), 2) for v in gp["gxy"][t["id"]]],
                               "z_m": gser[str(t["id"])]["z"], "near_sample": t["near_sample"],
                               "access_m": round(t["access_m"], 1), "base_drive_km": round(t["base_drive_m"] / 1000, 3),
                               "link_fraction": round(float((w[:, 1] - w[:, 0]).sum()) / n if len(w) else 0.0, 5),
                               "windows": gser[str(t["id"])]["w"]})
        return pix[key]

    samples = {}
    for s, r in res.items():
        nb = r["n_basis"]
        samples[str(s)] = {
            "id": sdoc["samples"][s]["id"], "xy_m": sdoc["samples"][s]["xy_m"], "never_linked": r["never"],
            "link_fraction": round(float(Lk[s].mean()), 5), "basis": r["basis"], "n_basis": nb,
            "candidates": {"route_3km": r["n_route"], "route_los": r["n_route_los"], "grid_los": r["n_grid_los"]},
            "working": {"route": r["n_work_route"], "grid": r["n_work_grid"], "margin_1m": r["n_work_margin"]},
            "top": [{"point": point(t), "share": _share(t["counts"], nb),
                     "dark_share": _share(t["dark_counts"], r["dark"]["n"]), "drive_km": round(t["drive_m"] / 1000, 3),
                     "dist_m": round(t["dist_m"], 1), "clear_m": round(t["clear_m"], 3)} for t in r["top"]],
            "coverage": {m: _share(r["coverage"][m], nb) for m in MEASURES},
            "dark_hours": {"n": r["dark"]["n"], "best": _share(r["dark"]["best"], r["dark"]["n"]),
                           "all": _share(r["dark"]["all"], r["dark"]["n"])},
        }
    H = sorted(res)
    return {
        "format": PARKING_FORMAT, "version": PARKING_VERSION, "terrain": meta["site_id"],
        "description": "B-61: parking points for a helper that must see both Earth (direct, any_part, hourly) and a "
                       "rover held at a route sample, for every sample of set H (Stage G2's capped waits, the "
                       "never-linked samples, the 2028 dark sample). A point works for sample s when it has terrain "
                       "line of sight to s (2.5 m to 2.5 m, Terrain.los_clearance_m > 0), is reachable (a route "
                       "sample, or a 40 m grid point within 1.5 km that the expert A* route reaches from its nearest "
                       "route sample) and is linked in at least one hour 2028-2031 in which s is not. top[] ranks the "
                       "working points by the share of s's basis hours (its tallied calls, else its dark hours) linked "
                       "within 24 h, then within 168 h, then the share of s's dark hours linked within 168 h "
                       "(dark_share), then the shortest drive from s; top[0] is the best parking point. "
                       "share/dark_share/coverage = [within 0 h, 24 h, 168 h]; coverage.all = any working point.",
        "time": {"start_utc": sdoc["time"]["start_utc"], "step_h": 1, "n": n, "wrap": True},
        "criterion": "any_part", "mode": "dte", "antenna_m": ANT_M, "delays_h": list(DELAYS_H),
        "rules": {"route_radius_m": ROUTE_R_M, "grid_radius_m": GRID_R_M, "grid_step_m": GRID_STEP_M,
                  "margin_m": MARGIN_M, "top_k": TOP_K, "call_hour": "series hour of the wait start + rescue_h",
                  "drive": "route network: consecutive samples of the engine's legs, each leg scaled to its A* route "
                           "length; grid points add the A* route (lunarsim.rover.expert.plan, no lighting term) "
                           "from their nearest route sample (access_m)",
                  "measures": {"best": "top[0]", "route": "any working route sample", "grid": "any working grid point",
                               "all": "any working point", "all_1500m": "any working point within 1.5 km",
                               "all_margin_1m": "any working point with clearance > 1 m"}},
        "samples_file": {"file": os.path.basename(SAMPLES_V1), "sha256": EL.sha256(SAMPLES_V1),
                         "n_samples": len(sdoc["samples"])},
        "inputs": ctx.get("inputs") or _inputs(),
        "set_h": {"n": len(H), "never_linked": sum(r["never"] for r in res.values()),
                  "tallied": sum(r["basis"] == "calls" for r in res.values()), "dark_sample": EL.DARK_SAMPLE},
        "points": points, "samples": samples,
        "no_working_point": [s for s, r in res.items() if not r["top"]],
        "generated": {"tool": "tools/comms/parking.py tally / candidates / gridpre / grid / astar / parking"},
    }


def _q(v: Sequence[float], qs=(0.1, 0.5, 0.9)) -> Optional[List[float]]:
    v = np.asarray(v, dtype=float)
    return [round(float(x), 2) for x in np.quantile(v, qs)] if len(v) else None


def _summary(res: Dict[int, Any], sdoc, tally, H, never, ctx, doc) -> Dict[str, Any]:
    n = ctx["n"]
    # step 1
    tb: Dict[str, Any] = {}
    for cell in TALLY_H:
        runs = [r for r in tally["runs"].values() if r["rescue_h"] == cell]
        per_s: Dict[int, List[float]] = {}
        by_year: Dict[str, int] = {}
        for r in runs:
            by_year[str(r["start_year"])] = by_year.get(str(r["start_year"]), 0) + len(r["capped"])
            for sid, t, sh, w in r["capped"]:
                nat = min(w if w is not None else math.inf, r["horizon_h"] - t)
                a = per_s.setdefault(sid, [0, 0.0, 0.0])
                a[0] += 1
                a[1] += min(cell, r["horizon_h"] - t)
                a[2] += nat
        top = sorted(per_s.items(), key=lambda kv: -kv[1][0])[:10]
        tb[f"{cell:g}"] = {"runs": len(runs), "capped_waits": sum(v[0] for v in per_s.values()),
                           "per_run": round(sum(v[0] for v in per_s.values()) / len(runs), 2), "samples": len(per_s),
                           "by_start_year": by_year,
                           "held_h_before_cap": round(sum(v[1] for v in per_s.values()), 1),
                           "natural_held_h": round(sum(v[2] for v in per_s.values()), 1),
                           "top_samples": [{"sample": s, "calls": v[0], "natural_held_h": round(v[2], 1),
                                            "never_linked": s in ctx["never"]} for s, v in top]}
    # step 4
    acc: Dict[str, List[int]] = {}
    for r in res.values():
        for k, v in r.get("acc", {}).items():
            a = acc.setdefault(k, [0, 0, 0, 0])
            for i in range(4):
                a[i] += v[i]
            basis, cell, yr, m = k.split("|")
            a = acc.setdefault(f"{basis}|{cell}|all|{m}", [0, 0, 0, 0])
            for i in range(4):
                a[i] += v[i]
    hd: Dict[str, Any] = {}
    for k, v in sorted(acc.items()):
        basis, cell, yr, m = k.split("|")
        hd.setdefault(basis, {}).setdefault(cell, {}).setdefault(yr, {"n": v[0]})[m] = _share(v[1:], v[0])
    adds = {b: {c: {"route": hd[b][c]["all"]["route"], "all": hd[b][c]["all"]["all"],
                    "gain_pp": [round(100 * (x - y), 2) for x, y in zip(hd[b][c]["all"]["all"], hd[b][c]["all"]["route"])]}
                for c in hd[b]} for b in hd}
    # (3) uncovered calls
    unc: Dict[str, Any] = {}
    rows = [(s, d) for s, r in res.items() for d in r.get("diag", [])]
    two = {s: r.get("two_hop_candidate", False) for s, r in res.items()}
    for cell in [f"{c:g}" for c in TALLY_H] + ["all"]:
        for yr in ("all", "2028", "2029-2031"):
            R_ = [(s, d) for s, d in rows if (cell == "all" or d[0] == float(cell))
                  and (yr == "all" or (d[1] == 2028) == (yr == "2028"))]
            F = [(s, d) for s, d in R_ if d[7] > 168]
            cov = [d for _, d in R_ if d[7] <= 168]
            el = np.array([d[2] for _, d in F])
            hz = np.array([d[3] for _, d in F])
            blk = {"calls": len(R_), "uncovered": len(F), "uncovered_share": round(len(F) / len(R_), 5) if R_ else None}
            if F:
                blk.update({
                    "earth_below_level_share": round(float((el < 0).mean()), 5),
                    "earth_below_lowest_candidate_horizon_share": round(float((el < hz).mean()), 5),
                    "earth_upper_limb_deg_q10_50_90": _q(el), "lowest_candidate_horizon_deg_q10_50_90": _q(hz),
                    "own_horizon_deg_q10_50_90": _q([d[4] for _, d in F]),
                    "gap_deg_q10_50_90": _q(hz - el),
                    "h_until_earth_clears_lowest_horizon_q10_50_90": _q([d[5] for _, d in F]),
                    "h_until_earth_above_level_q10_50_90": _q([d[6] for _, d in F]),
                    "earth_below_level_whole_week_share": round(float(np.mean([d[6] > 168 for _, d in F])), 5),
                    "covered_calls_earth_below_level_share": round(float(np.mean([d[2] < 0 for d in cov])), 5) if cov else None,
                    "two_hop_candidate_share": round(float(np.mean([two[s] for s, _ in F])), 5),
                    "two_hop_mast_linked_within_0_24_168h_share": [round(float(np.mean([two[s] and d[8] <= x for s, d in F])), 5)
                                                                   for x in DELAYS_H],
                })
            unc[f"{cell}|{yr}"] = blk
    # spotlights
    edges = EL.month_edges_hourly()
    r188 = res[EL.DARK_SAMPLE]
    spell = np.flatnonzero(~ctx["Lk"][EL.DARK_SAMPLE][: edges[18]])            # its dark hours Jan 2028 - Jun 2029
    W = r188["W"]
    c188 = {m: [0, 0, 0, 0] for m in MEASURES}
    for k, v in r188.get("acc", {}).items():
        b, c, y, m = k.split("|")
        if b == "call" and y == "2028":
            for i in range(4):
                c188[m][i] += v[i]
    pts = doc["points"]

    def best_of(s):
        t = doc["samples"][str(s)]["top"]
        if not t:
            return None
        p = pts[t[0]["point"]]
        return {"point": t[0]["point"], "kind": p["kind"], "dist_m": t[0]["dist_m"], "drive_km": t[0]["drive_km"],
                "base_drive_km": p["base_drive_km"], "link_fraction": p["link_fraction"], "share": t[0]["share"],
                "clear_m": t[0]["clear_m"]}

    legs = []
    nl = set(never)
    for leg, ids in sorted(sdoc["legs"].items()):
        bad = [i for i in ids if i in nl]
        if not bad:
            continue
        cov = [doc["samples"][str(i)]["coverage"]["all"][2] for i in bad]
        bcov = [doc["samples"][str(i)]["coverage"]["best"][2] for i in bad if doc["samples"][str(i)]["top"]]
        legs.append({"leg": leg, "never_linked_samples": len(bad), "interior": sum(i not in (ids[0], ids[-1]) for i in bad),
                     "worst_any_point_within_168h": min(cov), "worst_best_point_within_168h": min(bcov) if bcov else None,
                     "max_best_drive_km": max((doc["samples"][str(i)]["top"][0]["drive_km"] for i in bad
                                               if doc["samples"][str(i)]["top"]), default=None)})
    isru = doc["samples"]["4"]
    nw = res[4]["nearest_working"]
    spot = {
        "dark_sample_188": {"best": best_of(EL.DARK_SAMPLE),
                            "calls_2028": {m: _share(v[1:], v[0]) for m, v in c188.items()} | {"n": c188["all"][0]},
                            "dark_spell_jan2028_jun2029": {"hours": int(len(spell)),
                                                           "best": _share(_counts(W["best"][spell]), len(spell)),
                                                           "all": _share(_counts(W["all"][spell]), len(spell))}},
        "isru": {"never_linked": isru["never_linked"], "best": best_of(4), "nearest_working": nw,
                 "working": isru["working"], "coverage": isru["coverage"], "basis": isru["basis"]},
        "never_linked_legs": legs,
    }
    tot = lambda k: int(sum(r[k] for r in res.values()))
    return {
        "description": "B-61 (R-1 follow-up): can a helper park where it sees both Earth and the held rover? Set H, "
                       "working parking points, the best point per sample and the effective help delay (hours until a "
                       "working point is linked), shares within [0, 24, 168] h. Bases: 'call' = each tallied capped wait "
                       "at its call hour (wait start + rescue_h); 'held_hour' = every hour the rover would be held "
                       "without help (natural wait, inside the simulated year). See data/comms/connecting_ridge/"
                       "parking-v1.json for the per-sample records and the definitions.",
        "inputs": doc["inputs"],
        "tally": {"cells_rescue_h": list(TALLY_H), "seeds": N_SEEDS, "runs_reproduce_stage_g2": True,
                  "capped_logged_equals_rescues": True, "cells": tb},
        "set_h": doc["set_h"] | {"tallied_never_linked": sum(r["never"] and r["basis"] == "calls" for r in res.values())},
        "candidates": {"route_pairs_3km": tot("n_route"), "route_los": tot("n_route_los"), "route_working": tot("n_work_route"),
                       "grid_points": int(len(ctx["gp"]["gxy"])), "grid_los_pairs": tot("n_grid_los"),
                       "grid_working": tot("n_work_grid"), "working_margin_1m": tot("n_work_margin"),
                       "samples_without_working_route_point": sum(r["n_work_route"] == 0 for r in res.values()),
                       "samples_without_working_grid_point": sum(r["n_work_grid"] == 0 for r in res.values())},
        "no_working_point": doc["no_working_point"],
        "help_delay": hd, "grid_adds": adds, "uncovered_calls": unc, "spotlights": spot,
    }


def _runs_of(a: np.ndarray):
    """(value, start, end) of the runs of equal values of a sorted array."""
    if not len(a):
        return []
    cut = np.flatnonzero(np.diff(a)) + 1
    st = np.concatenate([[0], cut])
    en = np.concatenate([cut, [len(a)]])
    return [(a[i], i, j) for i, j in zip(st, en)]


# ---------------------------------------------------------------------------------------------------------
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/comms/parking.py", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("tally")
    sub.add_parser("candidates")
    sub.add_parser("gridpre")
    p = sub.add_parser("grid")
    p.add_argument("--part", type=int, default=0)
    p.add_argument("--parts", type=int, default=1)
    sub.add_parser("astar")
    sub.add_parser("parking")
    for sp_ in sub.choices.values():
        sp_.add_argument("--max-seconds", type=float, default=540.0,
                         help="stop this process after so many seconds (Windows: `timeout` only kills the venv launcher)")
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    if a.cmd == "tally":
        step_tally(a.max_seconds)
    elif a.cmd == "candidates":
        step_candidates()
    elif a.cmd == "gridpre":
        step_gridpre(a.max_seconds)
    elif a.cmd == "grid":
        step_grid(a.part, a.parts)
    elif a.cmd == "astar":
        step_astar(a.max_seconds)
    elif a.cmd == "parking":
        step_parking(a.max_seconds)
    rss = EL.peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
