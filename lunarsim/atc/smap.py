"""The shared map (B-92, problem 2, experiment E52): a base-held authoritative map of versioned tiles, per-vehicle
copies, hazard contributions accepted under a stated rule, and synchronisation on contact (research note 02 sections
B5, C3-C7, D, E4, E5; source tags as in the note).

Layers and wire sizes (note 02 C3, D): hazard (1 m cells, 256 m tiles, 2,048 B a tile: 0.25 bit a cell, ASSUMED);
traversability cost (1 m, 256 m, 11,796 B: 1.44 bit a cell, MEAS on slope classes); level-1 elevation (rover-made,
1 m, 256 m, 32,768 B: 4 bits a cell, ASSUMED); radio coverage (20 m, 1,280 m tiles, ~2 kB per tile and node,
ASSUMED); road network (vector, ~40 B a changed edge, ASSUMED); keep-out zones (vector, ~300 B a zone, "hundreds of
bytes"). The site is 16 km square: 63 x 63 tiles of 256 m (note 02 counts 62.5^2 = 3,906), 13 x 13 of 1,280 m.

Versions and hashes (C4): each tile has a version; a layer's tiles form a quadtree whose node hash covers its four
children; digests carry 8 bytes of the hash. Sync (B5): root hash per layer both ways (8 B a layer), a walk down the
quadtrees to the changed tiles (each opened node costs its 4 child hashes: E4's bound h (1 + 4 n D)), then the
payloads, in the order "hazards_first" (keep-outs, hazard tiles on the rover's route, the other hazard tiles, roads,
traversability, radio, elevation: note 02 B5) or "oldest_first" (every changed item in the order it changed, the
alternative H12 compares against).

Contribution rule (C6): accepted only with the current frame and datum, position sigma <= 2 m and a median height
difference to the authoritative elevation <= 1 m (both ASSUMED); a hazard is provisional at once, grown by 3 sigma of
the reporter's position error (E5), and confirmed when a second owner (or the same owner on another pass) reports it.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Tuple

SITE_M = 16000.0
LAYERS: Dict[str, Dict[str, float]] = {
    "hazard": {"tile_m": 256.0, "bytes": 2048.0},
    "traversability": {"tile_m": 256.0, "bytes": 11796.0},
    "elevation1": {"tile_m": 256.0, "bytes": 32768.0},
    "radio": {"tile_m": 1280.0, "bytes": 2000.0},
}
VECTOR_BYTES = {"road_edge": 40.0, "keepout": 300.0}
HASH_B, VERSION_B, TILE_HEADER_B = 8, 2, 16           # note 02 E4 (h, v); header per tile payload (ASSUMED)
ORDER_HAZARDS_FIRST = ["keepout", "hazard_route", "hazard", "road_edge", "traversability", "radio", "elevation1"]
POS_SIGMA_LIMIT_M = 2.0                                 # note 02 C6 (ASSUMED)
HEIGHT_DIFF_LIMIT_M = 1.0                               # note 02 C6 (ASSUMED)
HAZARD_GROWTH_SIGMA = 3.0                               # note 02 E5 / D


def tiles_per_side(layer: str) -> int:
    return int(math.ceil(SITE_M / LAYERS[layer]["tile_m"]))


def tile_of(layer: str, x: float, y: float) -> Tuple[int, int]:
    s = LAYERS[layer]["tile_m"]
    return int(x // s), int(y // s)


def quadtree_depth(n_side: int) -> int:
    return int(math.ceil(math.log2(max(1, n_side))))


class TileMap:
    """Tile versions of every layer (dict (ix, iy) -> version; absent = version 0) plus vector items."""

    def __init__(self):
        self.v: Dict[str, Dict[Tuple[int, int], int]] = {k: {} for k in LAYERS}
        self.vec: Dict[str, Dict[int, int]] = {k: {} for k in VECTOR_BYTES}
        self.changed_at: Dict[Tuple[str, object], float] = {}

    def copy(self) -> "TileMap":
        m = TileMap()
        m.v = {k: dict(d) for k, d in self.v.items()}
        m.vec = {k: dict(d) for k, d in self.vec.items()}
        m.changed_at = dict(self.changed_at)
        return m

    def bump(self, layer: str, tile, t: float):
        d = self.v[layer] if layer in self.v else self.vec[layer]
        d[tile] = d.get(tile, 0) + 1
        self.changed_at[(layer, tile)] = t

    def tile_hash(self, layer: str, tile) -> bytes:
        return hashlib.sha256(f"{layer}/{tile}/{self.v[layer].get(tile, 0)}".encode()).digest()[:HASH_B]

    def root_hash(self, layer: str) -> bytes:
        return self._node(layer, 0, 0, quadtree_depth(tiles_per_side(layer)))

    def _node(self, layer, ix, iy, depth) -> bytes:
        """Hash of the quadtree node covering tiles [ix * 2^depth, ...) x [iy * 2^depth, ...)."""
        if depth == 0:
            return self.tile_hash(layer, (ix, iy))
        h = hashlib.sha256()
        for dx in (0, 1):
            for dy in (0, 1):
                h.update(self._node(layer, 2 * ix + dx, 2 * iy + dy, depth - 1))
        return h.digest()[:HASH_B]


def tree_walk_bytes(base: TileMap, copy: TileMap, layer: str) -> Tuple[int, List[Tuple[int, int]]]:
    """Bytes of the hash-tree walk that finds the changed tiles (1 root hash, then 4 child hashes per opened node;
    a node is opened only when its hash differs), and the changed tiles found (note 02 E4)."""
    D = quadtree_depth(tiles_per_side(layer))
    changed = {t for t in set(base.v[layer]) | set(copy.v[layer]) if base.v[layer].get(t, 0) != copy.v[layer].get(t, 0)}
    if not changed:
        return HASH_B, []
    nbytes = HASH_B
    frontier = {(0, 0)}
    for depth in range(D, 0, -1):                       # open the differing nodes level by level
        nxt = set()
        for (ix, iy) in frontier:
            nbytes += 4 * HASH_B
            for dx in (0, 1):
                for dy in (0, 1):
                    c = (2 * ix + dx, 2 * iy + dy)
                    span = 2 ** (depth - 1)
                    if any(c[0] * span <= t[0] < (c[0] + 1) * span and c[1] * span <= t[1] < (c[1] + 1) * span
                           for t in changed):
                        nxt.add(c)
        frontier = nxt
    return nbytes, sorted(changed)


def flat_manifest_bytes(layer: str) -> int:
    n = tiles_per_side(layer) ** 2
    return n * (VERSION_B + HASH_B)


def full_resend_bytes() -> float:
    """Every tile of every raster layer (vector layers excluded: they are small)."""
    return float(sum(tiles_per_side(k) ** 2 * (LAYERS[k]["bytes"] + TILE_HEADER_B) for k in LAYERS))


def sync_plan(base: TileMap, copy: TileMap, route_tiles: Iterable[Tuple[int, int]], order: str = "hazards_first"):
    """The items sent to bring `copy` up to `base`: list of (kind, key, bytes, changed_at), in sending order, after
    the root hashes and the tree walks (returned separately as overhead bytes)."""
    route = set(route_tiles)
    overhead = HASH_B * (len(LAYERS) + len(VECTOR_BYTES))          # root hashes / vector digests
    items = []
    for layer in LAYERS:
        b, ch = tree_walk_bytes(base, copy, layer)
        overhead += b
        for t in ch:
            kind = "hazard_route" if (layer == "hazard" and t in route) else layer
            items.append((kind, (layer, t), LAYERS[layer]["bytes"] + TILE_HEADER_B,
                          base.changed_at.get((layer, t), 0.0)))
    for kind in VECTOR_BYTES:
        for k, ver in base.vec[kind].items():
            if copy.vec[kind].get(k, 0) != ver:
                items.append((kind, (kind, k), VECTOR_BYTES[kind], base.changed_at.get((kind, k), 0.0)))
    if order == "hazards_first":
        rank = {k: i for i, k in enumerate(ORDER_HAZARDS_FIRST)}
        items.sort(key=lambda it: (rank[it[0]], it[3]))
    elif order == "oldest_first":
        items.sort(key=lambda it: it[3])
    else:
        raise ValueError("order must be hazards_first or oldest_first")
    return overhead, items


def time_hazards_current(overhead: float, items, rate_bps: float, loss: float = 0.0) -> Tuple[float, float]:
    """(seconds until the last hazard tile arrives, seconds until everything arrives) at a link rate with a share of
    packets lost and resent (goodput = rate x (1 - loss))."""
    good = rate_bps * (1.0 - loss) / 8.0
    t, t_h = overhead / good, overhead / good
    for kind, key, nb, _ in items:
        t += nb / good
        if kind in ("hazard", "hazard_route"):
            t_h = t
    return t_h, t


# ------------------------------------------------------------------------------------------------ contributions
@dataclass
class Contribution:
    owner: str
    tile: Tuple[int, int]
    pos_sigma_m: float
    height_diff_median_m: float
    frame_ok: bool = True
    hazard: bool = True
    pass_id: int = 0


@dataclass
class Authority:
    """The base map authority (note 02 C5, C6): accepts or rejects contributions and confirms hazards."""
    map: TileMap = field(default_factory=TileMap)
    provisional: Dict[Tuple[int, int], List[Tuple[str, int]]] = field(default_factory=dict)
    confirmed: set = field(default_factory=set)
    log: List[Tuple[str, Tuple[int, int], str]] = field(default_factory=list)

    def submit(self, c: Contribution, t: float) -> str:
        if not c.frame_ok:
            verdict = "rejected: frame or datum"
        elif c.pos_sigma_m > POS_SIGMA_LIMIT_M:
            verdict = "rejected: position sigma"
        elif c.height_diff_median_m > HEIGHT_DIFF_LIMIT_M:
            verdict = "rejected: height disagreement (misaligned)"
        else:
            rep = self.provisional.setdefault(c.tile, [])
            if c.tile in self.confirmed:                     # B-119 C10: a report on a confirmed tile says so
                verdict = "accepted: already confirmed"
            elif any(o != c.owner or p != c.pass_id for o, p in rep):
                self.confirmed.add(c.tile)
                verdict = "accepted: confirmed"
            else:
                verdict = "accepted: provisional"
            rep.append((c.owner, c.pass_id))
            self.map.bump("hazard", c.tile, t)
        self.log.append((c.owner, c.tile, verdict))
        return verdict

    @staticmethod
    def growth_radius_m(pos_sigma_m: float) -> float:
        return HAZARD_GROWTH_SIGMA * pos_sigma_m
