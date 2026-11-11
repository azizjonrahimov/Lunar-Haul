"""Robot-to-robot radio links from the terrain visibility file mesh-v1 (B-70; writer tools/atc/mesh.py).

Positions are point indices of the file, which are the sample indices of the engine's samples file
(earth_link-v1-samples; samples 0-16 are the sites and pads, BASE = 0). Antenna heights: 2.5 m (rover) or 1.0 m
(small robot) at any point; 10 m (the base computer's mast) only at BASE.

A link a-b exists when d(a, b) <= d_max_m, the terrain clearance of the ray > margin_m and, when fresnel_min is
given, the first-Fresnel-zone clearance ratio at the worst point >= fresnel_min at freq_hz. margin_m resolves to
0.1 m and fresnel_min to 0.01 (the file's encoding; both exact).

PROVISIONAL defaults (B-70 task; the Phase 5 research note will set them): d_max_m = 5 km, margin_m = 0 m, no
Fresnel requirement, 2.4 GHz.

Opt-in propagation law (B-89; research note 03 "comms, protocol, security", section E1 and the section D row "Range
cap d_max_m = min(horizon, budget range of E1)"): with propagation="two_ray" a link also needs
  (1) d <= the smooth-Moon mutual radio horizon sqrt(2 R h_a) + sqrt(2 R h_b), R = 1,737.4 km, and
  (2) d <= the range at which the flat-ground loss still closes the link budget `budget` (DEFAULT_BUDGET: the E48
      constants, 1 W, 3 dBi each end, 1 MHz, noise figure 5 dB, link margin 10 dB, 16 kbit/s).
Flat-ground loss: free space up to the breakpoint d_b = 4 h_a h_b / lambda, beyond it the two-ray asymptote
40 log10 d - 20 log10(h_a h_b) (reflection coefficient -1 at grazing; [HWU08] NASA JSC 2008, NTRS 20080015374,
finds the 1/R^4 law and frequency independence on lunar ground). Between d_b and 4 pi h_a h_b / lambda the asymptote
lies below free space (by up to 20 log10 pi = 9.9 dB at d_b), so the larger of the two losses is used there: the law
is continuous and never more optimistic than free space. The default (propagation=None) is unchanged, so every
Phase 5 result stays byte-identical.
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

# ---------------------------------------------------------------------------------------------- propagation (B-89)
MOON_RADIUS_M = 1737400.0         # note 03 section D (smooth-Moon horizon), as mesh-v1 rules.radius_m
C_M_S = 299792458.0
PROPAGATIONS = (None, "two_ray")
# E48's link constants (tools/atc/run_e48.py DESIGN_DOC["radio"], Assumed there) = note 03 section D rows "Transmit
# power" (LTV 1 W), "Antenna gain" 3 dBi, "Receiver noise figure" 5 dB, "Noise temperature" 290 K, "Bandwidth:
# broadband" 1,000 kHz, "Link margin" 10 dB; rate = "Narrow-band channel rate" 16 kbit/s (the coordination channel).
DEFAULT_BUDGET: Dict[str, float] = {"freq_hz": 2.4e9, "tx_power_w": 1.0, "gain_dbi": 3.0, "bandwidth_hz": 1.0e6,
                                    "noise_figure_db": 5.0, "margin_db": 10.0, "rate_bps": 16000.0}


def horizon_m(h):
    """Smooth-Moon radio horizon of an antenna h m high: sqrt(2 R h) (note 03 E1; no atmosphere)."""
    return np.sqrt(2.0 * MOON_RADIUS_M * np.asarray(h, dtype=np.float64))


def mutual_horizon_m(h_a, h_b):
    return horizon_m(h_a) + horizon_m(h_b)


def breakpoint_m(h_a, h_b, freq_hz: float = DEFAULT_FREQ_HZ):
    """Last maximum of the two-ray interference term: 4 h_a h_b / lambda (note 03 E1)."""
    return 4.0 * np.asarray(h_a, dtype=np.float64) * np.asarray(h_b, dtype=np.float64) * float(freq_hz) / C_M_S


def free_space_loss_db(d, freq_hz: float = DEFAULT_FREQ_HZ):
    """20 log10(4 pi d f / c)."""
    return 20.0 * np.log10(4.0 * np.pi * np.asarray(d, dtype=np.float64) * float(freq_hz) / C_M_S)


def two_ray_loss_db(d, h_a, h_b):
    """Plane-earth asymptote 40 log10 d - 20 log10(h_a h_b), independent of frequency (note 03 E1; [HWU08])."""
    return 40.0 * np.log10(np.asarray(d, dtype=np.float64)) - 20.0 * np.log10(np.asarray(h_a, dtype=np.float64)
                                                                               * np.asarray(h_b, dtype=np.float64))


def flat_ground_loss_db(d, h_a, h_b, freq_hz: float = DEFAULT_FREQ_HZ):
    """Free space up to the breakpoint, then the larger of free space and the two-ray asymptote (module docstring)."""
    fs = free_space_loss_db(d, freq_hz)
    beyond = np.asarray(d, dtype=np.float64) > breakpoint_m(h_a, h_b, freq_hz)
    return np.where(beyond, np.maximum(fs, two_ray_loss_db(d, h_a, h_b)), fs)


def noise_dbm(bandwidth_hz: float, noise_figure_db: float) -> float:
    """kTB at 290 K plus the noise figure: -174 dBm/Hz + 10 log10 B + F."""
    return -174.0 + 10.0 * np.log10(float(bandwidth_hz)) + float(noise_figure_db)


def snr_db(loss_db, budget: Optional[Dict[str, float]] = None):
    """SNR after the link margin: P_t + 2 G - L - N - M (dB; budget keys as DEFAULT_BUDGET)."""
    b = dict(DEFAULT_BUDGET, **(budget or {}))
    pt = 10.0 * np.log10(b["tx_power_w"] * 1000.0)
    return pt + 2.0 * b["gain_dbi"] - np.asarray(loss_db) - noise_dbm(b["bandwidth_hz"], b["noise_figure_db"]) \
        - b["margin_db"]


def shannon_kbps(loss_db, budget: Optional[Dict[str, float]] = None):
    """B log2(1 + SNR) in kbit/s at the given path loss."""
    b = dict(DEFAULT_BUDGET, **(budget or {}))
    return b["bandwidth_hz"] / 1e3 * np.log2(1.0 + 10.0 ** (snr_db(loss_db, b) / 10.0))


def allowed_loss_db(budget: Optional[Dict[str, float]] = None) -> float:
    """Largest path loss at which Shannon capacity still reaches budget['rate_bps']."""
    b = dict(DEFAULT_BUDGET, **(budget or {}))
    need = 10.0 * np.log10(2.0 ** (b["rate_bps"] / b["bandwidth_hz"]) - 1.0)
    return float(snr_db(0.0, b) - need)


def budget_range_m(h_a, h_b, budget: Optional[Dict[str, float]] = None):
    """Largest d with flat_ground_loss_db(d) <= allowed_loss_db(budget) (the loss rises monotonically with d)."""
    b = dict(DEFAULT_BUDGET, **(budget or {}))
    la = allowed_loss_db(b)
    d_fs = C_M_S / (4.0 * np.pi * b["freq_hz"]) * 10.0 ** (la / 20.0)
    d_pe = np.sqrt(np.asarray(h_a, dtype=np.float64) * np.asarray(h_b, dtype=np.float64)) * 10.0 ** (la / 40.0)
    db = breakpoint_m(h_a, h_b, b["freq_hz"])
    return np.where(d_fs <= db, d_fs, np.maximum(db, np.minimum(d_fs, d_pe)))


def range_cap_m(h_a, h_b, d_max_m, propagation: Optional[str] = None, budget: Optional[Dict[str, float]] = None):
    """The distance limit a link must meet: d_max_m, and under two_ray also the horizon and the budget range."""
    if propagation is None:
        return d_max_m
    if propagation != "two_ray":
        raise ValueError(f"propagation must be one of {PROPAGATIONS}")
    return np.minimum(np.minimum(d_max_m, mutual_horizon_m(h_a, h_b)), budget_range_m(h_a, h_b, budget))


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
             freq_hz: float = DEFAULT_FREQ_HZ, propagation: Optional[str] = None,
             budget: Optional[Dict[str, float]] = None) -> bool:
        """Can an antenna h_a m above point a and one h_b m above point b talk directly? propagation="two_ray" adds
        the horizon and link-budget range caps (module docstring; budget keys as DEFAULT_BUDGET)."""
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
            cap = range_cap_m(h_a, h_b, d_max_m, propagation, budget)
            return bool(self._ok(self.mast_clear_dm[c, k], self.mast_fresnel[c, self._fi(freq_hz), k], self.mast_d[k],
                                 cap, margin_m, fresnel_min))
        if a > b:
            a, b, h_a, h_b = b, a, h_b, h_a
        try:
            k = self._pair(a, b)
        except KeyError:
            return False
        c = self._combo(h_a, h_b)
        cap = range_cap_m(h_a, h_b, d_max_m, propagation, budget)
        return bool(self._ok(self.clear_dm[c, k], self.fresnel[c, self._fi(freq_hz), k], self.d[k], cap, margin_m,
                             fresnel_min))

    def pair_links(self, h: Heights = 2.5, d_max_m: float = DEFAULT_D_MAX_M, margin_m: float = DEFAULT_MARGIN_M,
                   fresnel_min: Optional[float] = None, freq_hz: float = DEFAULT_FREQ_HZ,
                   base_mast: bool = True, propagation: Optional[str] = None,
                   budget: Optional[Dict[str, float]] = None) -> np.ndarray:
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
        cap = range_cap_m(hv[self.I], hv[self.J], d_max_m, propagation, budget)
        ok = self._ok(self.clear_dm[ci, K], fr, self.d, cap, margin_m, fresnel_min)
        if base_mast:
            at = self.I == self.base
            j = self.J[at]
            cm = np.array([self.mast_combos.index((self.mast_h, float(x))) for x in hv[j]], np.int64)
            k = self._mast_pos[j]
            frm = self.mast_fresnel[cm, fi, k] if fresnel_min is not None else None
            capm = range_cap_m(self.mast_h, hv[j], d_max_m, propagation, budget)
            ok[at] = self._ok(self.mast_clear_dm[cm, k], frm, self.mast_d[k], capm, margin_m, fresnel_min)
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
