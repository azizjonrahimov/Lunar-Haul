"""Robot-to-robot radio links from the terrain visibility file mesh-v1 (B-70; writer tools/atc/mesh.py).

Positions are point indices of the file, which are the sample indices of the engine's samples file
(earth_link-v1-samples; samples 0-16 are the sites and pads, BASE = 0). Antenna heights: 2.5 m (rover) or 1.0 m
(small robot) at any point; 10 m (the base computer's mast) only at BASE.

A link a-b exists when d(a, b) <= d_max_m, the terrain clearance of the ray > margin_m and, when fresnel_min is
given, the first-Fresnel-zone clearance ratio at the worst point >= fresnel_min at freq_hz. margin_m resolves to
0.1 m and fresnel_min to 0.01 (the file's encoding; both exact).

PROVISIONAL defaults (B-70 task; the Phase 5 research note will set them): d_max_m = 5 km, margin_m = 0 m, no
Fresnel requirement, 2.4 GHz.
"""
from __future__ import annotations

import base64
import gzip
import json
import os
from typing import Any, Dict, Optional, Sequence, Union

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_MESH = os.path.join(ROOT, "data", "atc", "connecting_ridge", "mesh-v1.json.gz")
DEFAULT_D_MAX_M = 5000.0          # Provisional (B-70 task): radio range, until the research note
DEFAULT_MARGIN_M = 0.0            # Provisional (B-70 task): clearance margin, until the research note
DEFAULT_FREQ_HZ = 2.4e9           # Provisional (B-70 task): only used with fresnel_min

Heights = Union[float, Sequence[float], np.ndarray]


def unb64(d: Dict[str, Any]) -> np.ndarray:
    """A mesh-v1 array: little-endian base64, optionally byte-shuffled (byte planes)."""
    dt = np.dtype(d["dtype"])
    raw = np.frombuffer(base64.b64decode(d["b64"]), dtype=np.uint8)
    if d.get("shuffle"):
        raw = np.ascontiguousarray(raw.reshape(dt.itemsize, -1).T)
    return raw.view(dt).reshape(d["shape"])


def _units(x: float, unit: float, what: str) -> int:
    k = round(x / unit)
    if abs(k * unit - x) > 1e-9:
        raise ValueError(f"{what} {x} is not a multiple of {unit} (the file's resolution)")
    return int(k)


class RadioMesh:
    """Link queries on a mesh-v1 file (path, or an already loaded doc)."""

    def __init__(self, path: Optional[str] = None, doc: Optional[Dict[str, Any]] = None):
        if doc is None:
            with open(path or DEFAULT_MESH, "rb") as f:
                doc = json.loads(gzip.decompress(f.read()))
        if doc.get("format") != "lunarsim-mesh" or doc.get("version") != 1:
            raise ValueError("not a lunarsim-mesh v1 file")
        self.doc_meta = {k: v for k, v in doc.items() if k not in ("pairs", "mast", "points")}
        self.xy = np.array(doc["points"]["xy_m"], dtype=np.float64)
        self.n = len(self.xy)
        self.base = int(doc["points"]["base"])
        self.ids = dict(doc["points"].get("ids", {}))
        pr, ms = doc["pairs"], doc["mast"]
        self.I, self.J = unb64(pr["i"]).astype(np.int64), unb64(pr["j"]).astype(np.int64)
        self.d = np.hypot(*(self.xy[self.J] - self.xy[self.I]).T)
        self.combos = [tuple(map(float, c)) for c in pr["combos"]]
        c0 = unb64(pr["clear_dm0"]).astype(np.int16)
        self.clear_dm = np.concatenate([c0[None], (c0[None] + unb64(pr["clear_dm_delta"])).astype(np.int16)])
        self.fresnel = unb64(pr["fresnel"])
        self.mast_h = float(doc["antenna_m"]["mast"])
        self.mast_j = unb64(ms["j"]).astype(np.int64)
        self.mast_d = np.hypot(*(self.xy[self.mast_j] - self.xy[self.base]).T)
        self.mast_combos = [tuple(map(float, c)) for c in ms["combos"]]
        self.mast_clear_dm, self.mast_fresnel = unb64(ms["clear_dm"]), unb64(ms["fresnel"])
        self.freqs = [float(f) for f in doc["rules"]["freqs_hz"]]
        self.heights = sorted({h for c in self.combos for h in c})
        self._full = len(self.I) == self.n * (self.n - 1) // 2
        self._key = self.I * self.n + self.J
        self._mast_pos = np.full(self.n, -1, np.int64)
        self._mast_pos[self.mast_j] = np.arange(len(self.mast_j))

    # ------------------------------------------------------------------------------------------------------
    def _pair(self, i: int, j: int) -> int:
        """Index of the pair (i < j); KeyError when the file has no such pair (beyond its max_d_m)."""
        if self._full:
            return i * self.n - i * (i + 1) // 2 + (j - i - 1)
        k = int(np.searchsorted(self._key, i * self.n + j))
        if k >= len(self._key) or self._key[k] != i * self.n + j:
            raise KeyError((i, j))
        return k

    def _combo(self, h_i: float, h_j: float) -> int:
        try:
            return self.combos.index((float(h_i), float(h_j)))
        except ValueError:
            raise ValueError(f"no antenna combination ({h_i}, {h_j}) m; heights {self.heights}, "
                             f"{self.mast_h} m only at BASE") from None

    def _fi(self, freq_hz: float) -> int:
        try:
            return self.freqs.index(float(freq_hz))
        except ValueError:
            raise ValueError(f"no Fresnel data at {freq_hz} Hz; the file has {self.freqs}") from None

    def _ok(self, clear_dm, fres, d, d_max_m, margin_m, fresnel_min):
        """fres: the encoded ratio at the chosen frequency (ignored without fresnel_min)."""
        ok = (d <= d_max_m) & (clear_dm >= _units(margin_m, 0.1, "margin_m"))
        if fresnel_min is not None:
            k = _units(fresnel_min, 0.01, "fresnel_min")
            if not 0 <= k <= 254:
                raise ValueError("fresnel_min must lie in 0..2.54")
            ok = ok & (fres >= k + 1)
        return ok

    # ------------------------------------------------------------------------------------------------------
    def link(self, a: int, b: int, h_a: float = 2.5, h_b: float = 2.5, d_max_m: float = DEFAULT_D_MAX_M,
             margin_m: float = DEFAULT_MARGIN_M, fresnel_min: Optional[float] = None,
             freq_hz: float = DEFAULT_FREQ_HZ) -> bool:
        """Can an antenna h_a m above point a and one h_b m above point b talk directly?"""
        a, b = int(a), int(b)
        if a == b:
            return True
        if float(h_b) == self.mast_h:
            a, b, h_a, h_b = b, a, h_b, h_a
        if float(h_a) == self.mast_h:
            if a != self.base:
                raise ValueError(f"the {self.mast_h} m mast stands only at BASE (point {self.base})")
            if float(h_b) == self.mast_h:
                raise ValueError("only one mast")
            k = int(self._mast_pos[b])
            c = self.mast_combos.index((self.mast_h, float(h_b)))
            return bool(self._ok(self.mast_clear_dm[c, k], self.mast_fresnel[c, self._fi(freq_hz), k], self.mast_d[k],
                                 d_max_m, margin_m, fresnel_min))
        if a > b:
            a, b, h_a, h_b = b, a, h_b, h_a
        try:
            k = self._pair(a, b)
        except KeyError:
            return False
        c = self._combo(h_a, h_b)
        return bool(self._ok(self.clear_dm[c, k], self.fresnel[c, self._fi(freq_hz), k], self.d[k], d_max_m, margin_m,
                             fresnel_min))

    def pair_links(self, h: Heights = 2.5, d_max_m: float = DEFAULT_D_MAX_M, margin_m: float = DEFAULT_MARGIN_M,
                   fresnel_min: Optional[float] = None, freq_hz: float = DEFAULT_FREQ_HZ,
                   base_mast: bool = True) -> np.ndarray:
        """Bool per pair of the file: does the pair link with antenna h (a height, or one per point)? With
        base_mast, pairs that touch BASE use the mast at BASE instead (and its height there)."""
        hv = np.broadcast_to(np.asarray(h, dtype=np.float64), (self.n,))
        ci = np.empty(len(self.I), np.int64)
        for c, (hi, hj) in enumerate(self.combos):
            ci[(hv[self.I] == hi) & (hv[self.J] == hj)] = c
        known = np.isin(hv, self.heights)
        if not known.all():
            raise ValueError(f"antenna heights must be in {self.heights} at every point")
        K = np.arange(len(self.I))
        fi = self._fi(freq_hz)
        fr = self.fresnel[ci, fi, K] if fresnel_min is not None else None
        ok = self._ok(self.clear_dm[ci, K], fr, self.d, d_max_m, margin_m, fresnel_min)
        if base_mast:
            at = self.I == self.base
            j = self.J[at]
            cm = np.array([self.mast_combos.index((self.mast_h, float(x))) for x in hv[j]], np.int64)
            k = self._mast_pos[j]
            frm = self.mast_fresnel[cm, fi, k] if fresnel_min is not None else None
            ok[at] = self._ok(self.mast_clear_dm[cm, k], frm, self.mast_d[k], d_max_m, margin_m, fresnel_min)
        return ok

    def graph(self, h: Heights = 2.5, **kw):
        """Symmetric scipy CSR adjacency (n x n) of the links (pair_links keywords)."""
        from scipy.sparse import csr_matrix
        ok = self.pair_links(h, **kw)
        i, j = self.I[ok], self.J[ok]
        return csr_matrix((np.ones(2 * len(i), np.int8), (np.concatenate([i, j]), np.concatenate([j, i]))),
                          shape=(self.n, self.n))

    def neighbours(self, a: int, h: Heights = 2.5, **kw) -> np.ndarray:
        """Points that point a links to directly (pair_links keywords; coincident points included)."""
        G = self.graph(h, **kw)
        return np.sort(G.indices[G.indptr[a]:G.indptr[a + 1]])

    def neighbour_counts(self, h: Heights = 2.5, exclude_coincident: bool = True, **kw) -> np.ndarray:
        """Number of direct links of every point (pairs at d = 0 left out by default)."""
        ok = self.pair_links(h, **kw)
        if exclude_coincident:
            ok &= self.d > 0
        return (np.bincount(self.I[ok], minlength=self.n) + np.bincount(self.J[ok], minlength=self.n)).astype(int)

    def hops(self, src: int, h: Heights = 2.5, **kw) -> np.ndarray:
        """Fewest links from src to every point (0 at src, -1 where unreachable; pair_links keywords)."""
        from scipy.sparse.csgraph import shortest_path
        dist = shortest_path(self.graph(h, **kw), directed=False, unweighted=True, indices=int(src))
        return np.where(np.isfinite(dist), dist, -1).astype(int)
