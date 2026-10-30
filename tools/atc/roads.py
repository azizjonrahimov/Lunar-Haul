"""B-77: corridor widths along the Connecting Ridge route network -> data/atc/connecting_ridge/roads-v1.json.

    python tools/atc/roads.py build      # ~10 s, single process
    python tools/atc/roads.py rings      # single-lane rings per share -> results/ATC_roads_rings.json (B-78)

For every route sample of the engine's samples file (earth_link-v1-samples, 2,421 samples, 100 m apart along the
legs), the drivable corridor across the route: the contiguous band through the sample, perpendicular to the route
direction, where the 5 m DEM slope is below a slope limit, sampled every 1 m out to +-50 m (bilinear on the 5 m slope
grid; a width of 101 m means the whole span is drivable). Widths are stored at several limits: 20 deg (the LTV
requirement, lunarsim.rover.physics ROVER["slope_hard_deg"]), 15 deg (nominal design slope), 12, 10 and 8 deg. A
sample is single-lane at a limit when its corridor is narrower than WIDTH_SINGLE_M = 2 vehicle widths + 2 lateral
margins (2 x 2.3 m CLV-1 width + 2 x 2.7 m = 10 m; traffic_and_safety.md R3, "about 10 m for LTV class").
Finding (B-77): at 20 deg no route sample is single-lane, at 15 deg 0.17 %; the engine's road layer
(lunarsim/atc/roads.py) therefore takes the single-lane share as an ASSUMED scenario factor and marks the narrowest
places first, ranked by their width at 10 deg (then 8 deg). Sites and pads are junctions, never single-lane.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from typing import Any, Dict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p_ in (ROOT, os.path.join(ROOT, "tools", "comms")):
    if p_ not in sys.path:
        sys.path.insert(0, p_)
import earth_link as EL  # noqa: E402

OUT = os.path.join(ROOT, "data", "atc", "connecting_ridge", "roads-v1.json")
CORRIDOR = os.path.join(ROOT, "results", "ATC_roads_corridor.json")
NARROW = os.path.join(ROOT, "results", "ATC_roads_narrow.json")
ASSUMED_REASON = ("ASSUMED: the 5 m DEM cannot see boulders, crater rims, shadows or graded one-lane roads, so the "
                  "single-lane share is a scenario factor; the narrowest places (corridor width at 10 deg) are marked "
                  "first")
SLOPE_LIMITS_DEG = (20.0, 15.0, 12.0, 10.0, 8.0)   # 20: Spec (LTV requirement); 15: Spec (nominal); others: sweep
VEHICLE_WIDTH_M = 2.3           # Spec: Astrolab CLV-1 deployed width (catalogue LTV entry)
LATERAL_MARGIN_M = 2.7          # Assumed: so that 2 widths + 2 margins = 10 m (traffic_and_safety.md R3, ~10 m)
WIDTH_SINGLE_M = 2 * VEHICLE_WIDTH_M + 2 * LATERAL_MARGIN_M
HALF_SPAN_M = 50.0
STEP_M = 1.0


def slope_grid(terrain) -> np.ndarray:
    gy, gx = np.gradient(terrain.z5, terrain.px5)
    return np.degrees(np.arctan(np.hypot(gx, gy)))


def corridor_widths(slope, px, xy: np.ndarray, dirs: np.ndarray, limit_deg: float) -> np.ndarray:
    """Width (m) of the band through each point, across its route direction, where slope < limit_deg."""
    from lunarsim.terrain import _bilinear
    offs = np.arange(-HALF_SPAN_M, HALF_SPAN_M + 1e-9, STEP_M)
    nrm = np.stack([-dirs[:, 1], dirs[:, 0]], axis=1)
    X = xy[:, 0:1] + offs[None, :] * nrm[:, 0:1]
    Y = xy[:, 1:2] + offs[None, :] * nrm[:, 1:2]
    ok = _bilinear(slope, px, X, Y) < limit_deg
    c = len(offs) // 2
    w = np.zeros(len(xy))
    for i in range(len(xy)):
        if not ok[i, c]:
            continue
        row = ok[i]
        lo = c - (np.flatnonzero(~row[:c][::-1])[0] if (~row[:c]).any() else c)
        hi = c + (np.flatnonzero(~row[c + 1:])[0] if (~row[c + 1:]).any() else len(offs) - 1 - c)
        w[i] = (hi - lo + 1) * STEP_M
    return w


def route_dirs(sdoc, xy) -> np.ndarray:
    dirs = np.zeros((len(xy), 2))
    for ids in sdoc["legs"].values():
        for k, i in enumerate(ids):
            if np.any(dirs[i]):
                continue
            a, b = ids[max(0, k - 1)], ids[min(len(ids) - 1, k + 1)]
            d = xy[b] - xy[a]
            L = float(np.hypot(*d))
            if L > 0:
                dirs[i] = d / L
    dirs[~np.any(dirs, axis=1)] = [1.0, 0.0]
    return dirs


def build(log=print) -> Dict[str, Any]:
    from lunarsim.terrain import Terrain
    t0 = time.time()
    with open(EL.SAMPLES_V1, "rb") as f:
        sdoc = json.loads(gzip.decompress(f.read()))
    xy = np.array([s["xy_m"] for s in sdoc["samples"]], float)
    named = [k for k, s in enumerate(sdoc["samples"]) if s.get("id")]
    terrain = Terrain(EL.PACK)
    sl = slope_grid(terrain)
    dirs = route_dirs(sdoc, xy)
    widths, summ = {}, {}
    for lim in SLOPE_LIMITS_DEG:
        w = corridor_widths(sl, terrain.px5, xy, dirs, lim)
        single = w < WIDTH_SINGLE_M
        single[named] = False
        widths[f"{lim:g}"] = [round(float(x), 1) for x in w]
        summ[f"{lim:g}"] = {"single_lane_share": round(float(single.mean()), 4),
                            "single_lane_km_unique": round(float(single.sum()) * 0.1, 1),
                            "width_lt_20m_share": round(float((w < 20).mean()), 4),
                            "median_width_m": float(np.median(w))}
    from lunarsim.terrain import _bilinear
    s_at = _bilinear(sl, terrain.px5, xy[:, 0], xy[:, 1])
    doc = {"format": "lunarsim-roads", "version": 1, "terrain": sdoc["terrain"],
           "description": __doc__.split("\n\n")[1].strip(),
           "samples_file": {"file": EL._rel(EL.SAMPLES_V1), "sha256": EL.sha256(EL.SAMPLES_V1), "n_samples": len(xy)},
           "rules": {"slope_limits_deg": list(SLOPE_LIMITS_DEG), "vehicle_width_m": VEHICLE_WIDTH_M,
                     "lateral_margin_m": LATERAL_MARGIN_M, "width_single_m": WIDTH_SINGLE_M,
                     "half_span_m": HALF_SPAN_M, "step_m": STEP_M, "sample_spacing_m": 100.0,
                     "flags": {"slope_limit 20": "Spec (LTV requirement)", "slope_limit 15": "Spec (nominal design)",
                               "vehicle_width_m": "Spec", "lateral_margin_m": "Assumed"}},
           "junctions": named,
           "width_m": widths,
           "slope_at_sample_deg": [round(float(x), 2) for x in s_at],
           "summary": {"by_slope_limit": summ, "route_km_unique": round(len(xy) * 0.1, 1),
                       "slope_at_sample_quantiles_deg": {q: round(float(np.quantile(s_at, q)), 1) for q in (0.5, 0.9, 0.99, 1.0)}},
           "generated": {"tool": "tools/atc/roads.py", "commit": EL._git_sha(),
                         "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, separators=(",", ":"))
    # results for P2: the terrain finding and the ranked narrow places
    lims = [f"{x:g}" for x in SLOPE_LIMITS_DEG]
    corridor = {"task": "B-77", "criterion": {
        "rule": "corridor narrower than 2 vehicle widths + 2 lateral margins at the slope limit",
        "width_single_m": WIDTH_SINGLE_M, "vehicle_width_m": VEHICLE_WIDTH_M, "lateral_margin_m": LATERAL_MARGIN_M,
        "profile": f"+-{HALF_SPAN_M:g} m across the route direction every {STEP_M:g} m, bilinear on the 5 m DEM slope grid",
        "dem": "LOLA 5 m Connecting Ridge tile (data/terrain/connecting_ridge)"},
        "samples": len(xy), "route_km_unique": round(len(xy) * 0.1, 1), "junctions_excluded": len(named),
        "slope_at_sample_percentiles_deg": doc["summary"]["slope_at_sample_quantiles_deg"],
        "by_slope_limit_deg": summ,
        "single_lane_km_at_20deg": summ["20"]["single_lane_km_unique"],
        "single_lane_km_at_15deg": summ["15"]["single_lane_km_unique"],
        "e43_choice": ASSUMED_REASON}
    with open(CORRIDOR, "w", encoding="utf-8", newline="\n") as f:
        json.dump(corridor, f, indent=1)
        f.write("\n")
    w10, w8 = np.array(widths["10"]), np.array(widths["8"])
    junc = set(named)
    order = sorted((i for i in range(len(xy)) if i not in junc), key=lambda i: (w10[i], w8[i], i))
    legs_of: Dict[int, list] = {}
    for leg, ids in sdoc["legs"].items():
        for i in ids:
            legs_of.setdefault(i, []).append(leg)
    narrow = {"task": "B-77", "note": ASSUMED_REASON + "; a single-lane share x marks the first round(x * samples) "
                                                      "entries of this list (lunarsim/atc/roads.py)",
              "samples": len(xy), "ranked": [
                  {"rank": r, "sample": int(i), "xy_m": [float(xy[i][0]), float(xy[i][1])],
                   "width_10deg_m": float(w10[i]), "width_8deg_m": float(w8[i]),
                   "width_20deg_m": float(widths["20"][i]), "slope_deg": round(float(s_at[i]), 2),
                   "legs": sorted(legs_of.get(i, []))[:6]} for r, i in enumerate(order)]}
    with open(NARROW, "w", encoding="utf-8", newline="\n") as f:
        json.dump(narrow, f, separators=(",", ":"))
        f.write("\n")
    log(f"roads: single-lane share by slope limit {json.dumps({k: v['single_lane_share'] for k, v in summ.items()})} "
        f"({time.time() - t0:.0f} s) -> {EL._rel(OUT)}")
    return doc


RINGS = os.path.join(ROOT, "results", "ATC_roads_rings.json")


def rings(shares=(0.05, 0.15, 0.40), log=print) -> Dict[str, Any]:
    """Rings made only of single-lane road (B-78 / LEAD): cycles of the graph of single-lane route samples (edges between
    consecutive samples of any leg; sites and pads are junctions, never single-lane, so a cycle through a site has an
    unbounded waiting place and is not counted). The exit-bay rule (R3) can deadlock only on such a ring (E44 type 5,
    E45 ring note); per share: number of independent cycles (cycle basis) and their lengths. For context, the same for
    the whole route graph (all samples) and how many of its cycles avoid every site."""
    import networkx as nx
    sys.path.insert(0, ROOT)
    from lunarsim.atc import roads as RD
    roads, sdoc = RD._load()
    xy = np.array([s_["xy_m"] for s_ in sdoc["samples"]], float)
    junc = set(roads["junctions"])

    def graph(mask):
        G = nx.Graph()
        for ids in sdoc["legs"].values():
            for a, b in zip(ids[:-1], ids[1:]):
                if a != b and mask[a] and mask[b]:
                    G.add_edge(a, b, w=float(np.hypot(*(xy[a] - xy[b]))))
        return G

    pairs = {lg: set(zip(ids[:-1], ids[1:])) for lg, ids in sdoc["legs"].items()}

    def cyc_info(G):
        out = []
        for c in nx.cycle_basis(G):
            ln = sum(float(np.hypot(*(xy[c[k]] - xy[c[(k + 1) % len(c)]]))) for k in range(len(c)))
            edges = [(c[k], c[(k + 1) % len(c)]) for k in range(len(c))]
            legs = sorted({lg for lg, pr in pairs.items() for a, b in edges if (a, b) in pr or (b, a) in pr})
            out.append({"samples": len(c), "length_m": round(ln, 1), "through_site": any(u in junc for u in c),
                        "sample_ids": [int(u) for u in c], "legs": legs})
        return sorted(out, key=lambda d: d["length_m"])

    # Legs sample shared roads at their own 100 m offsets, so raw sample cycles include 'diamonds' of one road sampled
    # twice. Merge samples closer than MERGE_M into one road node (union-find) and count cycles on the merged graph.
    MERGE_M = 40.0
    parent = list(range(len(xy)))

    def find(u):
        while parent[u] != u:
            parent[u] = parent[parent[u]]
            u = parent[u]
        return u
    from scipy.spatial import cKDTree
    for a, b in cKDTree(xy).query_pairs(MERGE_M):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    root = np.array([find(u) for u in range(len(xy))])

    def merged_graph(mask):
        G = nx.Graph()
        for ids in sdoc["legs"].values():
            for a, b in zip(ids[:-1], ids[1:]):
                if mask[a] and mask[b] and root[a] != root[b]:
                    G.add_edge(int(root[a]), int(root[b]))
        return G

    def merged_cycles(mask):
        G = merged_graph(mask)
        out = []
        for c in nx.cycle_basis(G):
            ln = sum(float(np.hypot(*(xy[c[k]] - xy[c[(k + 1) % len(c)]]))) for k in range(len(c)))
            out.append({"nodes": len(c), "length_m": round(ln, 1),
                        "through_site": any(root[j] == u for u in c for j in junc)})
        return sorted(out, key=lambda d: d["length_m"])

    doc = {"task": "B-78", "note": " ".join(rings.__doc__.split()), "merge_m": MERGE_M, "by_share": {},
           "raw_sample_cycles_note": "cycles of the raw sample graph (before merging) are mostly one road sampled twice "
                                     "by different legs; the merged counts are the physical answer"}
    full = merged_cycles(np.ones(len(xy), bool))
    doc["whole_route_graph"] = {"independent_cycles_merged": len(full),
                                "cycles_avoiding_sites": sum(not c["through_site"] for c in full),
                                "cycle_lengths_m": [c["length_m"] for c in full]}
    for sh in shares:
        G = graph(RD.single_lane_set(sh))
        cs = cyc_info(G)
        mc = merged_cycles(RD.single_lane_set(sh))
        doc["by_share"][f"{sh:g}"] = {"single_lane_samples": int(RD.single_lane_set(sh).sum()),
                                      "rings": len(mc), "ring_lengths_m": [c["length_m"] for c in mc],
                                      "raw_sample_cycles": len(cs), "raw_cycle_lengths_m": [c["length_m"] for c in cs]}
        log(f"rings: share {sh:g}: {len(mc)} single-lane rings after merging {[c['length_m'] for c in mc]} "
            f"(raw sample cycles {len(cs)})")
    log(f"rings: whole route graph: {len(full)} independent cycles, {doc['whole_route_graph']['cycles_avoiding_sites']} "
        f"avoid every site")
    with open(RINGS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    return doc


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python tools/atc/roads.py")
    ap.add_argument("cmd", choices=["build", "rings"])
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(540, exit=True)
    if a.cmd == "rings":
        rings()
        raise SystemExit(0)
    build()
    rss = EL.peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")
