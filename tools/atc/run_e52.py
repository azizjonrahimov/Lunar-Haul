"""E52 (B-92, Phase 6, H12): syncing a returning rover's map.

    python tools/atc/run_e52.py        # -> results/E52_map.json, results/E52_table.csv (30 seeds, seconds)

Site and routes: the Connecting Ridge pack (16 km, lunarsim/atc/smap.py layers), route tiles = the 256 m tiles crossed
by the engine's legs between the sites and the pads at the 1 km stand-off (earth_link-v1-samples legs, 100 m samples).
The base map changes (note 02 D): every day 42 route tiles get new hazard, traversability and level-1 elevation
versions at random times ("Tiles changed per day" 42, ASSUMED there: half of the route tiles); new hazards appear at
HAZARD_PER_DAY on random route tiles (ASSUMED, swept 0.5-10); keep-out zones at 0.3 a day and road edges at 5 a day
(ASSUMED). A rover synced at t = 0 drives the route tiles as a loop at 1 m/s (ASSUMED; LTV-class) and is out of contact
for D in {1 h, 6 h, 1 d, 3 d, 7 d, 14 d}; at D it syncs over one link (10, 16, 100, 1,000 kbit/s; packet loss 0.2,
note 02 D) in the order "hazards_first" (note 02 B5) or "oldest_first".
Outcomes: bytes to sync (hash-tree walk + changed items) against a flat manifest and against a full resend; time until
its hazard layer is current, and until everything is; hazards hit because of a stale map: a hazard the rover's copy
lacks, on a tile it crosses (during the outage, and after contact until that tile arrives), counted with the share
HIDDEN of hazards its own sensors would not see (ASSUMED 0.5; expected counts).
H12 (PREREG6): hazards-first sync of changed tiles needs under 10 % of the bytes of a full resend after 24 h out of
contact, and brings the hazard layer current sooner than oldest-first at every link rate.
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

OUT_JSON = os.path.join(ROOT, "results", "E52_map.json")
OUT_CSV = os.path.join(ROOT, "results", "E52_table.csv")
DURATIONS_H = [1, 6, 24, 72, 168, 336]
RATES_KBPS = [10, 16, 100, 1000]
LOSS = 0.2                     # note 02 D "Packet loss on the mesh" 0.2 [KM23]
TILES_PER_DAY = 42             # note 02 D (ASSUMED there)
HAZARD_PER_DAY = 2.0           # ASSUMED (sweep 0.5-10)
KEEPOUT_PER_DAY = 0.3          # ASSUMED
ROAD_EDGES_PER_DAY = 5.0       # ASSUMED
SPEED_MS = 1.0                 # ASSUMED (LTV class)
HIDDEN = 0.5                   # ASSUMED: share of map hazards the rover's own sensors would miss
SEEDS = 30


def route_tiles():
    """Route tiles in tour order (each unique undirected leg once) and the tour length (m)."""
    from lunarsim.atc import smap as S
    with gzip.open(os.path.join(ROOT, "data", "comms", "connecting_ridge", "earth_link-v1-samples.json.gz")) as f:
        doc = json.load(f)
    xy = np.array([s["xy_m"] for s in doc["samples"]], float)
    sites = {"BASE", "DEPOT", "POWER", "CONSTR", "ISRU", "SCI_1", "PSR", "PAD_A@1", "PAD_B@1"}
    seen, tour, length = set(), [], 0.0
    for key in sorted(doc["legs"]):
        a, b = key.split("->")
        if a not in sites or b not in sites or (b, a) in seen:
            continue
        seen.add((a, b))
        pts = xy[doc["legs"][key]]
        length += float(np.hypot(*np.diff(pts, axis=0).T).sum())
        for p in pts:
            t = S.tile_of("hazard", p[0], p[1])
            if not tour or tour[-1][0] != t:
                tour.append((t, length))
    return tour, length


def crossings(tour, length, t_from, t_to, tile):
    """Times (h) in [t_from, t_to) at which the rover (looping the tour from t = 0 at SPEED_MS) is on `tile`."""
    period = length / SPEED_MS / 3600.0
    offs = [s / SPEED_MS / 3600.0 for (t, s) in tour if t == tile]
    out = []
    k0 = int(t_from // period)
    for k in range(k0, int(t_to // period) + 2):
        for o in offs:
            tt = k * period + o
            if t_from <= tt < t_to:
                out.append(tt)
    return sorted(out)


def run_seed(seed, tour, length, route_set):
    from lunarsim.atc import smap as S
    rng = np.random.default_rng([52, seed])
    Hmax = max(DURATIONS_H)
    base = S.TileMap()
    events = []                                                    # (t_h, layer, key)
    route_list = sorted(route_set)
    for day in range(int(math.ceil(Hmax / 24.0)) + 1):
        pick = rng.choice(len(route_list), size=min(TILES_PER_DAY, len(route_list)), replace=False)
        for i in pick:
            for layer in ("hazard", "traversability", "elevation1"):
                events.append((day * 24.0 + rng.uniform(0, 24.0), layer, route_list[i]))
    hazards = []
    for _ in range(rng.poisson(HAZARD_PER_DAY * Hmax / 24.0)):
        th, tile = rng.uniform(0, Hmax), route_list[rng.integers(len(route_list))]
        hazards.append((th, tile))
        events.append((th, "hazard", tile))
    for _ in range(rng.poisson(KEEPOUT_PER_DAY * Hmax / 24.0)):
        events.append((rng.uniform(0, Hmax), "keepout", int(rng.integers(0, 10 ** 6))))
    for _ in range(rng.poisson(ROAD_EDGES_PER_DAY * Hmax / 24.0)):
        events.append((rng.uniform(0, Hmax), "road_edge", int(rng.integers(0, 400))))
    events.sort(key=lambda e: e[0])
    rows = []
    copy = S.TileMap()                                             # synced at t = 0 (empty = version 0 everywhere)
    ei = 0
    for D in DURATIONS_H:
        while ei < len(events) and events[ei][0] < D:
            t, layer, key = events[ei]
            base.bump(layer, key, t)
            ei += 1
        hz = [(th, tile) for th, tile in hazards if th < D]
        # hits during the outage: the next crossing of the hazard's tile after it appeared
        out_hits = sum(HIDDEN for th, tile in hz if crossings(tour, length, th, D, tile))
        for order in ("hazards_first", "oldest_first"):
            overhead, items = S.sync_plan(base, copy, route_set, order)
            nbytes = overhead + sum(it[2] for it in items)
            n_changed = sum(1 for it in items if it[0] in S.LAYERS or it[0] == "hazard_route")
            for rate in RATES_KBPS:
                t_h, t_all = S.time_hazards_current(overhead, items, rate * 1000.0, LOSS)
                # hits after contact: a hazard on a tile the rover crosses before that tile's item arrives
                good = rate * 1000.0 * (1.0 - LOSS) / 8.0
                arrive, tcum = {}, overhead / good
                for kind, key, nb, _ in items:
                    tcum += nb / good
                    if kind in ("hazard", "hazard_route"):
                        arrive[key[1]] = tcum / 3600.0
                after = 0.0
                for th, tile in hz:
                    ta = arrive.get(tile, 0.0)
                    if crossings(tour, length, D, D + ta, tile):
                        after += HIDDEN
                rows.append({"seed": seed, "out_h": D, "order": order, "rate_kbps": rate, "bytes": nbytes,
                             "overhead_bytes": overhead, "items": len(items), "tiles_changed": n_changed,
                             "full_resend_bytes": S.full_resend_bytes(),
                             "flat_manifest_bytes": sum(S.flat_manifest_bytes(k) for k in S.LAYERS),
                             "t_hazards_current_s": t_h, "t_all_s": t_all, "hazards_present": len(hz),
                             "hits_during_outage": out_hits, "hits_after_contact": after})
    return rows


def main():
    from lunarsim.atc import smap as S
    t0 = time.time()
    tour, length = route_tiles()
    route_set = {t for t, _ in tour}
    rows = []
    for s in range(1, SEEDS + 1):
        rows += run_seed(s, tour, length, route_set)
    keys = ["out_h", "order", "rate_kbps"]
    agg = {}
    for r in rows:
        k = tuple(r[x] for x in keys)
        agg.setdefault(k, []).append(r)
    table = []
    for k, rs in sorted(agg.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        m = lambda f: float(np.mean([r[f] for r in rs]))
        table.append({"out_h": k[0], "order": k[1], "rate_kbps": k[2], "seeds": len(rs),
                      "bytes_mean": round(m("bytes")), "share_of_full_resend": round(m("bytes") / S.full_resend_bytes(), 5),
                      "tree_overhead_bytes": round(m("overhead_bytes")),
                      "flat_manifest_bytes": rs[0]["flat_manifest_bytes"], "tiles_changed_mean": round(m("tiles_changed"), 1),
                      "t_hazards_current_s": round(m("t_hazards_current_s"), 2), "t_all_s": round(m("t_all_s"), 1),
                      "hazards_present_mean": round(m("hazards_present"), 2),
                      "hits_during_outage_mean": round(m("hits_during_outage"), 3),
                      "hits_after_contact_mean": round(m("hits_after_contact"), 4)})
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(table[0]))
        w.writeheader()
        w.writerows(table)
    get = lambda D, o, r: next(x for x in table if x["out_h"] == D and x["order"] == o and x["rate_kbps"] == r)
    share24 = get(24, "hazards_first", 100)["share_of_full_resend"]
    sooner = {r: get(24, "hazards_first", r)["t_hazards_current_s"] < get(24, "oldest_first", r)["t_hazards_current_s"]
              for r in RATES_KBPS}
    paired = {}
    for r in RATES_KBPS:                                            # per seed, hazards-first minus oldest-first
        a = {x["seed"]: x["t_hazards_current_s"] for x in rows if x["out_h"] == 24 and x["order"] == "hazards_first" and x["rate_kbps"] == r}
        b = {x["seed"]: x["t_hazards_current_s"] for x in rows if x["out_h"] == 24 and x["order"] == "oldest_first" and x["rate_kbps"] == r}
        d = np.array([a[s] - b[s] for s in a])
        paired[str(r)] = {"mean_s": float(d.mean()), "seeds_hazards_first_sooner": int((d < 0).sum()), "n": len(d)}
    h12 = {"rule": "after 24 h out of contact: hazards-first sync bytes < 10 % of a full resend, and the hazard layer "
                   "current sooner than oldest-first at every link rate",
           "share_of_full_resend_24h": share24, "sooner_at_every_rate": sooner, "paired_24h": paired,
           "supported": bool(share24 < 0.10 and all(sooner.values()))}
    doc = {"experiment": "E52 (B-92), Phase 6, H12 (paper/atc/PREREG6.md)", "note": __doc__.split("\n\n")[1].strip(),
           "route_tiles": len(route_set), "tour_km": round(length / 1000.0, 2),
           "layers": S.LAYERS, "vector_bytes": S.VECTOR_BYTES, "full_resend_bytes": S.full_resend_bytes(),
           "parameters": {"tiles_per_day": TILES_PER_DAY, "hazards_per_day": HAZARD_PER_DAY, "keepouts_per_day":
                          KEEPOUT_PER_DAY, "road_edges_per_day": ROAD_EDGES_PER_DAY, "speed_ms": SPEED_MS,
                          "hidden_share": HIDDEN, "loss": LOSS},
           "rows": table, "h12": h12, "seeds": SEEDS, "run_s": round(time.time() - t0, 1)}
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print(json.dumps(h12, indent=1), "route tiles", len(route_set), "tour km", round(length / 1000, 1),
          round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(540, exit=True)
    main()
