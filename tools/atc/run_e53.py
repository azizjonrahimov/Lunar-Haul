"""E53 (B-93, Phase 6, H13): does the LRIP message set fit the radio?

    python tools/atc/run_e53.py            # -> results/E53_bitrate.json, results/E53_table.csv,
                                           #    data/atc/lrip/conformance-v0.1.json (hex vectors for FRONTEND)

Per rover (bytes from the codec, lunarsim/atc/lrip; authentication on = profile N with an 8-byte AES-CMAC, awards and
grants signed with Ed25519; off = no security header or trailer): POSITION at f in {0.1, 1, 10} Hz, STATUS and INTENT
at 0.1 Hz (note 03 C2 default rates), HELLO filling up to 1 Hz of messages when nothing else is sent, and the event
messages at E48's measured rates per robot-hour at 1x (results/E48_sizing.json: reservation request / grant /
release per road traversal, the auction's bid / award / claim, landing announcements as ALERT sent once + 3 repeats).
On the mesh: N rovers in {5, 10, 20, 40, 80} at positions drawn from the 1x fleet's July 2028 trajectories (E50,
.cache/atc/e50/trace_m1_s1.pkl.gz; every vehicle-step equally likely), 2.5 m antennas, the 10 m mast at BASE, links
by DEM line of sight within 5 km (B-70 mesh). Beacons (POSITION, STATUS, INTENT, HELLO) go one hop and are never
relayed; event messages travel to BASE along shortest paths and every relay hop is another transmission (note 03 E3).
The load of the busiest link = the largest shared-channel load at any node: every transmission by a node in its
closed neighbourhood (itself and the nodes it hears), the base mast included. 30 draws per N; mean and p95.
Geometry "fleet" (pre-registered, H13): positions drawn from the fleet's own trajectories (it works near the base);
"spread" (LEAD, 11 Nov): positions uniform over all route samples, where relaying shows.
Compared with the 16 kbit/s narrow-band channel (Phase 5 / note 03 D), the 1 Mbit/s broadband channel, and as
airtime on a scheduled channel (eta 0.8) and slotted random access (eta 1/e).
"""
from __future__ import annotations

import csv
import gzip
import json
import math
import os
import pickle
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_JSON = os.path.join(ROOT, "results", "E53_bitrate.json")
OUT_CSV = os.path.join(ROOT, "results", "E53_table.csv")
OUT_VEC = os.path.join(ROOT, "data", "atc", "lrip", "conformance-v0.1.json")
RATES_HZ = [0.1, 1.0, 10.0]
N_ROVERS = [5, 10, 20, 40, 80]
DRAWS = 30
CHANNELS_KBPS = {"narrow-band (Phase 5 target)": 16.0, "broadband": 1000.0}
ETA = {"scheduled": 0.8, "slotted_aloha": 1.0 / math.e}
BEACONS = ("POSITION", "STATUS", "INTENT", "HELLO")


def per_rover(f_hz, auth):
    """Messages per second and bytes per second per rover, by type (module docstring)."""
    from lunarsim.atc.lrip import codec as C
    e48 = json.load(open(os.path.join(ROOT, "results", "E48_sizing.json")))
    ev = e48["messages"]["per_robot_hour_by_type"]["1"]
    size = {nm: (C.packet_bytes(nm, C.default_auth(nm)) if auth else C.packet_bytes(nm, None))
            for nm in ("POSITION", "STATUS", "INTENT", "HELLO", "RESERVE_REQ", "RESERVE_GRANT", "RESERVE_RELEASE",
                       "TASK_BID", "TASK_AWARD", "TASK_STATE", "ALERT")}
    auc = ev["auction (bid, award, claim)"] / 3600.0 / 3.0
    rate = {"POSITION": f_hz, "STATUS": 0.1, "INTENT": 0.1,
            "RESERVE_REQ": ev["reservation_request"] / 3600.0, "RESERVE_GRANT": ev["grant"] / 3600.0,
            "RESERVE_RELEASE": ev["release"] / 3600.0, "TASK_BID": auc, "TASK_AWARD": auc, "TASK_STATE": auc,
            "ALERT": ev["landing_announcement"] / 3600.0 * 4}
    rate["HELLO"] = max(0.0, 1.0 - sum(rate.values()))
    bps = {k: rate[k] * size[k] for k in rate}
    return rate, size, bps


def positions():
    """Pooled vehicle-steps of the 1x July trajectories, as route-sample indices."""
    import run_e50 as E5
    g = E5._geo()
    tr = pickle.load(gzip.open(os.path.join(ROOT, ".cache", "atc", "e50", "trace_m1_s1.pkl.gz")))
    xy = np.asarray(tr["xy"], float).reshape(-1, 2)[::7]
    sxy = g["xy"]
    idx = np.empty(len(xy), int)
    for k in range(0, len(xy), 4096):
        d = ((xy[k:k + 4096, None, :] - sxy[None, :, :]) ** 2).sum(axis=2)
        idx[k:k + 4096] = d.argmin(axis=1)
    return idx, g


def busiest(idx_nodes, g, beacon_Bps, event_Bps):
    """Shared-channel load (B/s) at the busiest node, and the mean hop count to BASE (module docstring)."""
    los = g["los"]
    base = g["ids"]["BASE"]
    n = len(idx_nodes)
    A = np.zeros((n + 1, n + 1), bool)                 # node n = the base mast
    for i in range(n):
        A[i, n] = A[n, i] = bool(los.mast[2.5][idx_nodes[i]]) or idx_nodes[i] == base
        for j in range(i + 1, n):
            if los.mat[(2.5, 2.5)][idx_nodes[i], idx_nodes[j]]:
                A[i, j] = A[j, i] = True
    # shortest paths to the base (BFS)
    hop = np.full(n + 1, -1)
    hop[n] = 0
    frontier = [n]
    while frontier:
        nxt = []
        for u in frontier:
            for w in np.nonzero(A[u])[0]:
                if hop[w] < 0:
                    hop[w] = hop[u] + 1
                    nxt.append(w)
        frontier = nxt
    tx = np.zeros(n + 1)                                # bytes per second transmitted by each node
    tx[:n] += beacon_Bps
    # events: up to the base and the reply back (grants / awards are the base's or the winner's; symmetric hops)
    parent = np.full(n + 1, -1)
    for w in range(n):
        if hop[w] > 0:
            cand = [u for u in np.nonzero(A[w])[0] if hop[u] == hop[w] - 1]
            parent[w] = min(cand)
    for i in range(n):
        if hop[i] < 0:
            continue
        u = i
        while u != n:                                   # every hop on the way up transmits the event traffic once
            tx[u] += event_Bps
            u = parent[u]
        tx[n] += 0.0                                    # the base's replies are inside event_Bps (both directions)
    load = np.array([tx[np.nonzero(A[j] | (np.arange(n + 1) == j))[0]].sum() for j in range(n + 1)])
    reach = hop[:n] >= 0
    return float(load.max()), float(hop[:n][reach].mean()) if reach.any() else float("nan"), float(reach.mean())


def conformance():
    """Golden packets (hex) with their decoded values: every message, profile N MAC 8 B (signed for awards and
    grants), unsecured, and profile B; the two example manifests in compact CBOR. Test keys only."""
    from lunarsim.atc import lrip as L
    from lunarsim.atc.lrip import codec as C, manifest as M
    rng = np.random.default_rng(93)
    sk, pk = C.ed25519_keys(bytes(range(32)))
    keys = C.Keys(mac_key=bytes(range(16)), sign_key=sk, verify_key=pk, epoch=5)
    vec = []
    for m in C.schema()["messages"]:
        nm = m["name"]
        vals = {}
        for f in m["fields"]:
            name, typ, bits, scale = f[0], f[1], f[2], f[3]
            if typ == "spare":
                continue
            if typ == "flag":
                vals[name] = bool(rng.integers(0, 2))
            elif typ == "flags":
                vals[name] = int(rng.integers(0, 1 << bits))
            elif typ.startswith("enum"):
                codes = [int(k) for k in C.schema()["enums"][typ.split(":", 1)[1]] if k.isdigit()]
                vals[name] = int(rng.choice(codes))
            elif typ == "int":
                q = int(rng.integers(-(1 << (bits - 1)), 1 << (bits - 1)))
                vals[name] = q * scale if not float(scale).is_integer() else int(q * scale)
            else:
                q = int(rng.integers(0, 1 << bits))
                vals[name] = round(q * scale, 10) if not float(scale).is_integer() else int(q * scale)
        body = M.encode(M.example("small_rover")) if nm == "CAP_MANIFEST" else None
        for profile, auth in (("N", C.default_auth(nm)), ("N", None), ("B", C.default_auth(nm))):
            pkt = L.encode(nm, vals, sender=291, t_valid_s=4321.0, seq=42, auth=auth, keys=keys, profile=profile,
                           body=body)
            d = L.decode(pkt, auth="auto" if auth else None, keys=keys, profile=profile)
            vec.append({"message": nm, "profile": profile, "auth": auth, "bytes": len(pkt), "hex": pkt.hex(),
                        "sender": 291, "t_valid_s": 4321.0, "seq": 42 if auth else None,
                        "fields": d.fields if body is None else {"manifest_cbor_hex": body.hex()}})
    doc = {"format": "lrip-conformance", "version": "0.1", "schema": "lunarsim/schemas/lrip-v0.1.json",
           "keys": {"note": "TEST KEYS ONLY", "aes_cmac_key_hex": keys.mac_key.hex(), "key_epoch": 5,
                    "ed25519_seed_hex": bytes(range(32)).hex(),
                    "ed25519_public_hex": pk.public_bytes_raw().hex()},
           "manifests": {nm: {"json_bytes": len(M.minified_json(M.example(nm))),
                              "compact_cbor_hex": M.encode(M.example(nm)).hex()} for nm in ("small_rover", "hopper")},
           "vectors": vec}
    with open(OUT_VEC, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    return len(vec)


def main():
    from lunarsim.atc.lrip import codec as C, manifest as M
    t0 = time.time()
    idx_fleet, g = positions()
    pools = {"fleet": idx_fleet, "spread": np.arange(len(g["xy"]))}
    rows, cells = [], {}
    for geo, idx_pool in pools.items():
      for auth in (True, False):
        for f in RATES_HZ:
            rate, size, bps = per_rover(f, auth)
            beacon = sum(bps[k] for k in BEACONS)
            event = sum(v for k, v in bps.items() if k not in BEACONS)
            per = beacon + event
            for N in N_ROVERS:
                rng = np.random.default_rng([53, N])
                res = [busiest(idx_pool[rng.integers(0, len(idx_pool), N)], g, beacon, event) for _ in range(DRAWS)]
                L_ = np.array([r[0] for r in res]) * 8 / 1000.0          # kbit/s
                row = {"geometry": geo, "auth": "on" if auth else "off", "position_hz": f, "rovers": N,
                       "per_rover_kbps": round(per * 8 / 1000.0, 4),
                       "one_hop_sum_kbps": round(N * per * 8 / 1000.0, 3),
                       "busiest_link_kbps_mean": round(float(L_.mean()), 3),
                       "busiest_link_kbps_p95": round(float(np.quantile(L_, 0.95)), 3),
                       "mean_hops_to_base": round(float(np.nanmean([r[1] for r in res])), 3),
                       "reachable_share": round(float(np.mean([r[2] for r in res])), 4)}
                for cn, ck in CHANNELS_KBPS.items():
                    key = "nb" if ck == 16.0 else "bb"
                    row[f"fits_{key}_raw_p95"] = bool(row["busiest_link_kbps_p95"] <= ck)
                    for en, ev in ETA.items():
                        row[f"fits_{key}_{en}_p95"] = bool(row["busiest_link_kbps_p95"] / ev <= ck)
                rows.append(row)
                cells[(geo, auth, f, N)] = row
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    r20_1, r20_10 = cells[("fleet", True, 1.0, 20)], cells[("fleet", True, 10.0, 20)]
    h13 = {"rule": "auth on, 20 rovers: the busiest link's load (p95 over draws) <= 16 kbit/s at 1 Hz position reports, "
                   "and > 16 kbit/s at 10 Hz",
           "at_1hz_kbps_p95": r20_1["busiest_link_kbps_p95"], "at_10hz_kbps_p95": r20_10["busiest_link_kbps_p95"],
           "supported": bool(r20_1["busiest_link_kbps_p95"] <= 16.0 and r20_10["busiest_link_kbps_p95"] > 16.0),
           "airtime_1hz_scheduled_kbps": round(r20_1["busiest_link_kbps_p95"] / ETA["scheduled"], 3),
           "airtime_1hz_slotted_aloha_kbps": round(r20_1["busiest_link_kbps_p95"] / ETA["slotted_aloha"], 3)}
    per_type = {}
    for auth in (True, False):
        rate, size, bps = per_rover(1.0, auth)
        per_type["on" if auth else "off"] = {k: {"rate_hz": round(rate[k], 5), "bytes": size[k],
                                                 "bps": round(8 * bps[k], 2)} for k in rate}
    n_vec = conformance()
    doc = {"experiment": "E53 (B-93), Phase 6, H13 (paper/atc/PREREG6.md)", "note": __doc__.split("\n\n")[1].strip(),
           "sizes": C.size_table(len(M.encode(M.example("small_rover")))),
           "manifest_bytes": {nm: {"json": len(M.minified_json(M.example(nm))), "compact_cbor": len(M.encode(M.example(nm))),
                                   "note03_compact": {"small_rover": 247, "hopper": 251}[nm]}
                              for nm in ("small_rover", "hopper")},
           "per_rover_at_1hz": per_type, "rows": rows, "h13": h13, "draws": DRAWS,
           "spread_auth_1hz_20": cells[("spread", True, 1.0, 20)], "spread_auth_10hz_20": cells[("spread", True, 10.0, 20)],
           "channels_kbps": CHANNELS_KBPS, "eta": ETA, "conformance_vectors": n_vec,
           "run_s": round(time.time() - t0, 1)}
    with open(OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(json.dumps(h13, indent=1), n_vec, "vectors", round(time.time() - t0, 1), "s")


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(540, exit=True)
    main()
