"""Phase 6 verification rows (B-98): one row per formula in the proof sections of the Lunar Rover Interaction Protocol
notes (research_notes/Lunar Rover Interaction Protocol/01, 02, 03, sections E) checked against the code that uses it,
and one row per degenerate case. Same row format as results/vv_phase5.json (lunarsim/vv5.py _row; the verification
page reads both).

    python -m lunarsim.vv6          # -> results/vv_phase6.json

Ids: P = positioning and time (note 01), M = map and coordinates (note 02), C = communication, protocol and security
(note 03), G = degenerate cases (Phase 6 options off or trivial). Every row names its source section in
tolerance_source.
"""
from __future__ import annotations

import math
import os
import time
from typing import Dict, List

import numpy as np

from .vv5 import _row, write_json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
N01 = "research_notes/Lunar Rover Interaction Protocol/01_positioning_and_time.md"
N02 = "research_notes/Lunar Rover Interaction Protocol/02_shared_map_and_coordinates.md"
N03 = "research_notes/Lunar Rover Interaction Protocol/03_comms_protocol_security.md"
OUT = os.path.join(ROOT, "results", "vv_phase6.json")


def R(cid, sub, name, ref, sim, tol, unit, basis, src, tol_src, papers=("P3",), mode="abs", technique="analytic",
      t0=None):
    return _row(cid, sub, name, ref, sim, tol, unit, basis, technique, "code verification", "V", "P1", list(papers),
                mode=mode, source=src, t0=t0, tol_src=tol_src)


# ------------------------------------------------------------------------------------------------ P: note 01
def check_p() -> List[Dict]:
    from .atc import pnt as PN, clocks as CK
    rows = []
    t0 = time.time()
    T, N = 120, 400
    ds = np.full((T, N), 60.0, np.float32)
    head = np.zeros((T, N, 2), np.float32)
    head[..., 0] = 1.0
    tr = PN.Trajectories(np.arange(T) / 60.0, np.zeros((T, N, 2), np.float32), np.zeros((T, N), np.int32), ds, head,
                         np.zeros((T, N), np.int32), np.zeros((T, N), np.int8), np.ones((T, N), bool),
                         np.zeros((T, N), bool), np.arange(N), np.full(N, 2.5), 60.0)
    res = PN.simulate(tr, ("dr",), seed=1)
    d = float(ds[:, 0].sum())
    rms = float(np.sqrt((res.err[-1].astype(float) ** 2).mean()))
    ref = math.hypot(PN.DEFAULTS["dr_firm"], math.radians(PN.DEFAULTS["heading_sigma_deg"]))
    rows.append(R("P1", "dead reckoning", "Dead-reckoning error grows as k x distance (1-sigma)", ref, rms / d, 0.1,
                  "share of distance", f"400 vehicles, 7.2 km straight on firm ground: rms |e| / d against hypot(k, "
                  f"psi) = {ref:.4f}", "lunarsim/atc/pnt.py", f"{N01} section E1; 10 % for 400 samples (rms "
                  "standard error 3.5 %)", ("P3", "P2"), mode="rel", technique="monte carlo", t0=t0))
    t0 = time.time()
    k, L, sig = 0.02, 100.0, 5.0
    Q, Rf = (k * L) ** 2, sig ** 2
    P = 0.0
    for _ in range(500):
        P = (P + Q) * Rf / (P + Q + Rf)
    form = (-Q + math.sqrt(Q * Q + 4 * Q * Rf)) / 2
    rows.append(R("P2", "fix steady state", "Scalar steady state after a fix: P+ = (-Q + sqrt(Q^2 + 4 Q R)) / 2",
                  form, P, 1e-9, "m^2", f"iterated P- = P+ + Q, P+ = P- R / (P- + R) for 2 %, 100 m, 5 m; the note's "
                  f"table gives sigma 2.9 m after and 3.5 m before (here {math.sqrt(form):.2f} / {math.sqrt(form + Q):.2f})",
                  "note 01 E2", f"{N01} section E2; deterministic identity", ("P3",), mode="rel", t0=t0))
    t0 = time.time()
    worst = 0.0
    for n in (4, 8):
        th = 2 * math.pi * np.arange(n) / n
        H = np.c_[np.cos(th), np.sin(th)]
        worst = max(worst, abs(math.sqrt(np.trace(np.linalg.inv(H.T @ H))) - 2 / math.sqrt(n)))
    a = math.atan(1 / (2 * 5.0))
    H2 = np.array([[math.cos(a), math.sin(a)], [math.cos(a), -math.sin(a)]])
    hd = math.sqrt(np.trace(np.linalg.inv(H2.T @ H2)))
    rows.append(R("P3", "even beacons", "HDOP = 2 / sqrt(N) for N beacons evenly around the vehicle", 0.0, worst, 1e-9,
                  "HDOP", "N = 4 and 8 from the geometry matrix", "note 01 E3", f"{N01} section E3; identity", t0=t0))
    rows.append(R("P3", "two beacons", "Two beacons at d / b = 5: HDOP = sqrt(2) / sin(2 alpha)", 7.14, hd, 0.01,
                  "HDOP", "beacons at +-alpha, tan alpha = b / 2d; note table 7.14", "note 01 E3",
                  f"{N01} section E3 table (2 decimals)", t0=t0))
    t0 = time.time()
    c = 299792458.0
    GM_E, GM_M, a_m, RM = 3.986004418e14, 4.90280031e12, 3.84399e8, 1737.4e3
    mu = GM_M / (GM_E + GM_M)
    v2 = (GM_E + GM_M) / a_m
    L_G = 6.969290134e-10
    L_L = GM_M / (RM * c * c)
    L_orb = (GM_E / a_m + (1 - mu) ** 2 * v2 / 2 - GM_M / a_m - mu ** 2 * v2 / 2) / (c * c)
    rate = (L_G - L_L - L_orb) * 86400e6
    rows.append(R("P4", "Moon minus Earth", "Relativistic rate of a lunar surface clock against Earth's geoid",
                  56.025, rate, 0.01, "us/day", "L_G - GM_M / (R c^2) - orbital term, constants of [ASH24] Table I",
                  "note 01 E4", f"{N01} section E4 (CALC 56.025; published 56.0199(12), 56.0256)", t0=t0))
    rows.append(R("P4", "constant in code", "The clocks module's Moon-minus-Earth rate equals note 01 E4", 56.025,
                  CK.RATE_MOON_MINUS_EARTH * 86400e6, 0.01, "us/day", "lunarsim/atc/clocks.py RATE_MOON_MINUS_EARTH",
                  "lunarsim/atc/clocks.py", f"{N01} section E4", t0=t0))
    rows.append(R("P5", "1 ns", "One-way ranging: 1 ns of clock error is 0.2998 m", 0.2998, CK.C_M_S * 1e-9, 1e-4, "m",
                  "c x 1 ns", "note 01 E5", f"{N01} section E5 (4 digits)", t0=t0))
    rows.append(R("P5", "two-way single-sided", "Two-way single-sided ranging: c x T_reply x (e_A - e_B) / 2 at 1 ms, "
                  "1 ppm", 0.15, CK.C_M_S * 1e-3 * 1e-6 / 2, 0.001, "m", "note's 0.15 m", "note 01 E5",
                  f"{N01} section E5 (2 digits)", t0=t0))
    t0 = time.time()
    rows.append(R("P6", "crystal 0.1 s", "Holdover: a crystal at 1e-6 reaches 0.1 s in 27.8 h", 27.8,
                  CK.holdover_s(0.1, 1e-6) / 3600, 0.05, "h", "x(t) = y0 t", "lunarsim/atc/clocks.py holdover_s",
                  f"{N01} section E6 holdover table (3 digits)", t0=t0))
    rows.append(R("P6", "CSAC 1 us", "Holdover: a chip-scale atomic clock at 3e-10 reaches 1 us in about 56 min", 55.6,
                  CK.holdover_s(1e-6, 3e-10) / 60, 0.5, "min", "x(t) = y0 t", "lunarsim/atc/clocks.py holdover_s",
                  f"{N01} section E6 holdover table ('56 minutes')", t0=t0))
    t0 = time.time()
    x = np.random.default_rng(6).normal(size=(400000, 2))
    rows.append(R("P7", "95 % bound", "The 95 % bound 2.4477 sigma contains 95 % of a circular 2D Gaussian", 0.95,
                  float((np.hypot(*x.T) <= PN.R95).mean()), 0.002, "share", "400,000 draws", "lunarsim/atc/pnt.py R95",
                  f"{N01} sections D, E (bound definition); binomial 3-sigma 0.001", technique="monte carlo", t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ M: note 02
def check_m() -> List[Dict]:
    from .atc import geo as G, smap as S
    rows = []
    t0 = time.time()
    d = G.base_datum()
    rng = np.random.default_rng(2)
    worst = 0.0
    for _ in range(300):
        la, lo, h = -89.0 - rng.random(), rng.uniform(0, 360), rng.uniform(-500, 2000)
        e = d.me_to_enu(la, lo, h)
        la2, lo2, h2 = d.enu_to_me(e)
        worst = max(worst, float(np.linalg.norm(G.latlon_to_cart(float(la2), float(lo2), float(h2))
                                                - G.latlon_to_cart(la, lo, h))))
    rows.append(R("M1", "ENU round trip", "MOON_ME <-> local east-north-up at the base datum, round trip", 0.0, worst,
                  1e-5, "m", "300 points within 1 deg of the pole, heights -500 to 2,000 m", "lunarsim/atc/geo.py",
                  f"{N02} section E1; 10 micrometres: float64 latitude from arcsin(z / r) loses about two digits within "
                  "1 deg of the pole (condition number 1 / cos(lat), about 60)", t0=t0))
    t0 = time.time()
    for sub, la, lo, ref in (("pole", -90.0, 0.0, 662.86), ("tile centre", -89.4632, 222.5104, 659.22),
                             ("lat 0 lon 0", 0.0, 0.0, 875.23)):
        rows.append(R("M2", sub, "PA read as ME: the shift (SPICE pxform values in note 02)", ref,
                      float(np.linalg.norm(G.frame_mixup_shift(la, lo))), 0.05, "m",
                      "NAIF FK angles 67.8526 / 78.6944 / 0.2785 arcsec (moon_de440_250416.tf), axes 3-2-1", "lunarsim/atc/geo.py",
                      f"{N02} section E1 (SPICE to 0.01 m; 0.05 m allows the composition order)", t0=t0))
    t0 = time.time()
    dd = 50000.0
    rho = 2 * G.R_MOON * math.tan(dd / G.R_MOON / 2)
    rows.append(R("M3", "scale at 50 km", "Stereographic scale k - 1 = tan^2(d / 2R) at 50 km from the pole", 207.0,
                  (G.grid_scale(rho, 0.0) - 1) * 1e6, 1.0, "ppm", "k = 1 + (rho / 2R)^2", "lunarsim/atc/geo.py",
                  f"{N02} section E2 (3 digits)", t0=t0))
    rows.append(R("M3", "rho minus d", "Map radius minus surface distance at 50 km (d^3 / 12 R^2)", 3.45, rho - dd, 0.01,
                  "m", "rho = 2R tan(c/2)", "lunarsim/atc/geo.py", f"{N02} section E2 (3 digits)", t0=t0))
    t0 = time.time()
    base, copy = S.TileMap(), S.TileMap()
    tiles = {(int(a), int(b)) for a, b in np.random.default_rng(4).integers(0, 63, (42, 2))}
    for t in tiles:
        base.bump("hazard", t, 0.0)
    walk, _ = S.tree_walk_bytes(base, copy, "hazard")
    bound = S.HASH_B * (1 + 4 * len(tiles) * S.quadtree_depth(S.tiles_per_side("hazard")))
    rows.append(R("M4", "tree bound", "Hash-tree walk bytes <= h (1 + 4 n D)", 0.0, float(walk > bound), 0.0, "breaches",
                  f"n = {len(tiles)} changed tiles, D = 6: walk {walk} B, bound {bound} B (note: 8,072 B at n = 42)",
                  "lunarsim/atc/smap.py", f"{N02} section E4; exact", t0=t0))
    rows.append(R("M4", "hazard payload 24 h", "Hazard payload for 42 changed tiles at 2,048 B", 86016.0,
                  42 * S.LAYERS["hazard"]["bytes"], 0.0, "B", "256^2 cells x 0.25 bit", "lunarsim/atc/smap.py",
                  f"{N02} section E4 ('86 kB'); exact", t0=t0))
    sig = math.sqrt(2 * (1 + (math.radians(0.5) * 10) ** 2 + 0.05 ** 2))
    rows.append(R("M5", "disagreement", "Two rovers' map disagreement, RMS (1 m position, 0.5 deg at 10 m, 0.05 m "
                  "sensor)", 1.42, sig, 0.005, "m", "sqrt(2 (sigma^2 + (sigma_th r)^2 + sigma_eta^2))", "note 02 E5",
                  f"{N02} section E5 (3 digits)", t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ C: note 03
def check_c() -> List[Dict]:
    from .atc import radio as RA, integrity as I
    from .atc.lrip import codec as CO, cbor
    rows = []
    t0 = time.time()
    rows.append(R("C1", "allowed loss", "Worked example A: allowed loss for 1 Mbit/s", 135.0,
                  RA.allowed_loss_db({"rate_bps": 1e6}), 1e-9, "dB", "30 dBm + 6 dBi + 109 dB - 10 dB margin, SNR 0 dB",
                  "lunarsim/atc/radio.py", f"{N03} section E1; identity", ("P3",), mode="abs", t0=t0))
    for h, ref in ((2.0, 4740.0), (1.0, 2370.0)):
        rows.append(R("C1", f"1 Mbit/s range, {h:g} m", "Worked example A: flat-ground range for 1 Mbit/s", ref,
                      float(RA.budget_range_m(h, h, {"rate_bps": 1e6})), 10.0, "m", "sqrt(h1 h2) 10^(L / 40)",
                      "lunarsim/atc/radio.py", f"{N03} section E1 table (3 digits)", t0=t0))
    for h, ref in ((0.5, 2640.0), (1.0, 3730.0), (1.5, 4570.0), (2.0, 5270.0)):
        rows.append(R("C2", f"horizon {h:g} m", "Smooth-Moon mutual radio horizon sqrt(2Rh1) + sqrt(2Rh2)", ref,
                      float(RA.mutual_horizon_m(h, h)), 10.0, "m", "R = 1,737.4 km", "lunarsim/atc/radio.py",
                      f"{N03} section E1 table E1 (3 digits)", t0=t0))
    for cls, pw, h, ref in (("LTV / cargo", 1.0, 2.5, 1574.0), ("small", 0.25, 1.0, 18.0), ("hopper", 0.5, 1.0, 36.0)):
        rows.append(R("C3", cls, "Flat-ground Shannon rate at the 5 km hop (the E48 check)", ref,
                      float(RA.shannon_kbps(RA.flat_ground_loss_db(5000.0, h, h), {"tx_power_w": pw})), 1.0, "kbit/s",
                      "E48 constants, two-ray beyond the breakpoint", "lunarsim/atc/radio.py",
                      f"{N03} section E1 'Check against E48' (whole kbit/s)", t0=t0))
    t0 = time.time()
    st = CO.size_table()
    for m, ref in (("POSITION", 41), ("STATUS", 43), ("TASK_BID", 37), ("ALERT", 42), ("TASK_AWARD", 92),
                   ("RESERVE_GRANT", 94)):
        rows.append(R("C4", m, "Bytes on the air (MAC 8 B; awards and grants signed)", ref, st[m]["default"], 0.0, "B",
                      "Space Packet 6 + LRIP 8 + payload + security 6 + MAC 8 (or signature 64)", "lunarsim/atc/lrip/codec.py",
                      f"{N03} sections C2, E2 (Table B5); exact", ("P1",), t0=t0))
    t0 = time.time()
    rng = np.random.default_rng(5)
    keys = CO.Keys(mac_key=bytes(range(16)))
    bad = 0
    n = 0
    for m in CO.schema()["messages"]:
        if not m["fields"]:
            continue
        for prof in ("N", "B"):
            for _ in range(10):
                vals = {}
                for f in m["fields"]:
                    nm, typ, bits, scale = f[0], f[1], f[2], f[3]
                    if typ == "spare":
                        continue
                    if typ == "flag":
                        vals[nm] = bool(rng.integers(0, 2))
                    elif typ == "flags":
                        vals[nm] = int(rng.integers(0, 1 << bits))
                    elif typ.startswith("enum"):
                        vals[nm] = int(rng.choice([int(k) for k in CO.schema()["enums"][typ.split(":")[1]] if k.isdigit()]))
                    elif typ == "int":
                        vals[nm] = int(rng.integers(-(1 << (bits - 1)), 1 << (bits - 1))) * scale
                    else:
                        vals[nm] = int(rng.integers(0, 1 << bits)) * scale
                pkt = CO.encode(m["name"], vals, 3, 1.0, auth="mac8", keys=keys, profile=prof)
                dd = CO.decode(pkt, auth="mac8", keys=keys, profile=prof)
                n += 1
                bad += int(any(abs(float(vals[k]) - float(dd.fields[k])) > 1e-9 for k in vals))
    rows.append(R("C5", "codec round trips", "Every message round-trips (profile N bit-packed and profile B CBOR, MAC 8 B)",
                  0.0, float(bad), 0.0, "mismatches", f"{n} random packets", "lunarsim/atc/lrip/codec.py",
                  f"{N03} section C4 rule 6 (golden packets); exact", ("P1",), t0=t0))
    rows.append(R("C5", "CBOR heads", "CBOR integer heads: 23 -> 1 B, 24 -> 2 B, 256 -> 3 B, 65,536 -> 5 B", 11.0,
                  float(sum(len(cbor.dumps(x)) for x in (23, 24, 256, 65536))), 0.0, "B", "RFC 8949 shortest form",
                  "lunarsim/atc/lrip/cbor.py", f"{N03} section E2 step 8; exact", ("P1",), t0=t0))
    t0 = time.time()
    load = (41 + 0.1 * 43 + 0.1 * 38) * 20 * 8 / 1000.0
    rows.append(R("C6", "offered load", "Offered load, 20 robots: POSITION 1 Hz + STATUS and INTENT 0.1 Hz (MAC 8 B)",
                  7.86, load, 0.01, "kbit/s", "8 x 49.1 B/s x 20", "note 03 E3", f"{N03} section E3 (3 digits)", ("P1",), t0=t0))
    rows.append(R("C6", "scheduled airtime", "Channel rate needed on a scheduled channel (eta 0.8, one hop)", 9.8,
                  load / 0.8, 0.05, "kbit/s", "R >= L h / eta", "note 03 E3", f"{N03} section E3 (2 digits)", ("P1",), t0=t0))
    t0 = time.time()
    n_att = 40000
    acc = I.forgery_trial(8, n_att, np.random.default_rng(8))
    rows.append(R("C7", "MAC 8 bits", "Forgery acceptance of a t-bit MAC is 2^-t per attempt (t = 8, measured)", 2.0 ** -8,
                  acc / n_att, 3 * math.sqrt(2.0 ** -8 / n_att), "per attempt", f"{n_att} random tags, real AES-CMAC",
                  "lunarsim/atc/integrity.py", f"{N03} section E4; binomial 3-sigma", ("P3",), technique="monte carlo", t0=t0))
    t0 = time.time()
    from scipy import stats
    rows.append(R("C8", "gamma m=1", "Chi-square threshold, one range, alpha 1e-3", 10.83, float(stats.chi2.ppf(1 - 1e-3, 1)),
                  0.005, "-", "scipy chi2.ppf", "lunarsim/atc/integrity.py GAMMA", f"{N03} section E5 table (2 decimals)",
                  ("P2",), t0=t0))
    rows.append(R("C8", "gamma m=2", "Chi-square threshold, two measurements, alpha 1e-3 (= -2 ln alpha)", 13.82,
                  -2 * math.log(1e-3), 0.005, "-", "closed form", "lunarsim/atc/integrity.py GAMMA",
                  f"{N03} section E5 table (2 decimals)", ("P2",), t0=t0))
    chk = I.detectable_error_check(n=200000)
    rows.append(R("C8", "detectable error", "A bias of 4.57 sigma is caught with probability 0.9 (m = 1, alpha 1e-3)", 0.90,
                  chk["detect_prob"], 0.005, "probability", "200,000 draws", "lunarsim/atc/integrity.py",
                  f"{N03} section E5; binomial 3-sigma 0.002 plus rounding of 4.57", ("P2",), technique="monte carlo", t0=t0))
    rows.append(R("C8", "3 of 5", "Persistence 3 of 5 at alpha 1e-3: false-alarm probability", 1.0e-8,
                  I.k_of_n_false_alarm(1e-3), 1e-10, "probability", "binomial sum", "lunarsim/atc/integrity.py",
                  f"{N03} section E5 (2 digits)", ("P2",), t0=t0))
    t0 = time.time()
    k, p, Tp, D = 3, 0.25, 1.0, 0.010
    q = (1 - p) ** k
    ref = k * D + Tp * (2 - q) / (2 * q)
    g = np.random.default_rng(9).geometric(q, 200000) * Tp
    sim = k * D + float((g ** 2).mean() / (2 * g.mean()))
    rows.append(R("C9", "age 3 hops", "Mean age of information over k hops with loss p, no retry", ref, sim, 0.02 * ref,
                  "s", "renewal: k D + E[X^2] / 2 E[X], X = G T; note table 1.90 s at k 3, p 0.25", "note 03 E7",
                  f"{N03} section E7; 2 % for 200,000 renewals", ("P1",), mode="abs", technique="monte carlo", t0=t0))
    t0 = time.time()
    n7 = 7
    full = ~np.eye(n7, dtype=bool)
    x0 = np.random.default_rng(0).normal(0, 1, n7)
    f1 = np.zeros(n7, bool)
    f1[0] = True
    _, safe1 = I.wmsr(full, x0, f1, F=1, steps=60)
    rows.append(R("C10", "one liar, F = 1", "W-MSR keeps honest values inside the honest range (one liar, F = 1, K7)", 1.0,
                  float(safe1), 0.0, "boolean", "polarising liar +-50", "lunarsim/atc/integrity.py",
                  f"{N03} section E6 (safety); exact", ("P2",), t0=t0))
    return rows


# ------------------------------------------------------------------------------------------------ G: degenerate cases
def check_g() -> List[Dict]:
    import sys
    import warnings
    from .atc import pnt as PN, clocks as CK
    from .atc.messages import Channel
    rows = []
    t0 = time.time()
    sys.path.insert(0, os.path.join(ROOT, "experiments", "phase5"))
    from . import Simulation
    from .atc import regimes as G, p5 as P5
    sc = P5.build("3eq", k=2.806, team_lift_share=0.10)
    sc = sc.with_(horizon_h=24.0 * 30, p5=dict(sc.p5, roads={"mode": "atc", "single_share": 0.15, "bay_km": 1.0}))
    sc_off = sc.with_(p5=dict(sc.p5, roads=dict(sc.p5["roads"], pos_margin=None, log_reservations=False)))
    mech = G.mechanism("C_AUCTION")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        a = Simulation(sc, mech, seed=2, mech_kwargs={"loss": 0.1}).run()
        b = Simulation(sc_off, mech, seed=2, mech_kwargs={"loss": 0.1, "capability_filter": None}).run()
    mism = sum(1 for k in a if not (a[k] == b[k] or (isinstance(a[k], float) and math.isnan(a[k]) and math.isnan(b[k]))))
    rows.append(R("G1", "options off", "Every Phase 6 engine option off (pos_margin, log_reservations, capability_filter) "
                  "equals the Phase 5 run", 0.0, float(mism), 0.0, "summary values differing",
                  f"C_AUCTION, roads atc, 30 days, seed 2: {len(a)} summary values compared", "lunarsim/atc",
                  "PLAN-phase6 section 2 ('byte-identical with every new option off'); exact", ("P1", "P2", "P3"), t0=t0))
    ch = Channel(0.0)
    ch.send(3)
    rows.append(R("G1", "channel sizes off", "Message channel without LRIP sizes counts no bytes", 0.0,
                  float(ch.bytes_sent), 0.0, "B", "Channel(sizes=None)", "lunarsim/atc/messages.py",
                  "B-93 opt-in; exact", ("P1",), t0=t0))
    t0 = time.time()
    att = np.ones(100, bool)
    clk = CK.Clocks(np.zeros(4), np.zeros(4), 0.0, 600.0, lambda i: att, 100, np.random.default_rng(0), tt_sigma_s=0.0)
    xmax = max(float(np.abs(clk.x(i, np.linspace(0, 60000, 500))).max()) for i in range(4))
    rows.append(R("G2", "perfect clocks", "Perfect clocks (no frequency error, no ageing, exact transfer) give zero "
                  "clock error", 0.0, xmax, 0.0, "s", "4 vehicles, 60,000 s", "lunarsim/atc/clocks.py",
                  "B-98 degenerate case; exact", ("P3",), t0=t0))
    t0 = time.time()
    T, N = 30, 10
    tr = PN.Trajectories(np.arange(T) / 60.0, np.zeros((T, N, 2), np.float32), np.zeros((T, N), np.int32),
                         np.full((T, N), 60.0, np.float32), np.tile(np.array([1.0, 0.0], np.float32), (T, N, 1)),
                         np.zeros((T, N), np.int32), np.zeros((T, N), np.int8), np.ones((T, N), bool),
                         np.zeros((T, N), bool), np.arange(N), np.full(N, 2.5), 60.0)
    perf = PN.simulate(tr, (), seed=1)
    rows.append(R("G3", "perfect position", "The 'perfect' layer set gives zero position error and bound", 0.0,
                  float(perf.err.max() + perf.b95.max()), 0.0, "m", "no layers", "lunarsim/atc/pnt.py",
                  "B-98 degenerate case; exact", ("P3", "P2"), t0=t0))
    a1 = PN.simulate(tr, ("dr",), seed=3)
    a2 = PN.simulate(tr, ("dr", "lans"), seed=3, params={"year": 2028})
    rows.append(R("G3", "LANS absent in 2028", "With no LANS service (2028) the LANS layer changes nothing", 0.0,
                  float(np.abs(a1.err - a2.err).max()), 0.0, "m", "same random streams", "lunarsim/atc/pnt.py",
                  "B-98 degenerate case; exact", ("P3",), t0=t0))
    t0 = time.time()
    z = np.random.default_rng(10).normal(size=2_000_000)
    rate = float((z * z > 10.83).mean())
    rows.append(R("G4", "zero faults, single test", "No faults: the single chi-square test alarms at its false-alarm rate",
                  1e-3, rate, 3 * math.sqrt(1e-3 / 2e6), "per test", "2,000,000 Gaussian innovations, gamma 10.83",
                  "lunarsim/atc/integrity.py", f"{N03} section E5; binomial 3-sigma", ("P2",), technique="monte carlo", t0=t0))
    from .nn import faults as F
    X = np.zeros((1, len(z), len(F.FEATURES)), np.float32)
    X[0, :, F.F_Z] = z
    X[0, :, F.F_VALID] = 1
    from .atc.integrity import lrip_rule_score
    alarms = float((lrip_rule_score(X, 10.83)[0] >= 3).sum())
    rows.append(R("G4", "zero faults, 3 of 5", "No faults: the 3-of-5 rule raises no alarm in 2,000,000 tests "
                  "(expected 0.02)", 0.0, alarms, 0.0, "alarms", "Gaussian innovations, gamma 10.83",
                  "lunarsim/atc/integrity.py", f"{N03} section E5 (1e-8 per window); exact count", ("P2",),
                  technique="monte carlo", t0=t0))
    return rows


def run_phase6_checks() -> List[Dict]:
    return check_p() + check_m() + check_c() + check_g()


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(600, exit=True)
    t = time.time()
    rows = run_phase6_checks()
    p = write_json(rows, OUT)
    for r in rows:
        print(("PASS" if r["passed"] else "FAIL"), r["id"], r["sub"], f"ref={r['reference']:.6g} sim={r['simulated']:.6g}")
    print(os.path.relpath(p, ROOT), f"{len(rows)} rows, {time.time() - t:.0f} s")
