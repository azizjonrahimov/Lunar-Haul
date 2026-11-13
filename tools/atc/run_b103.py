"""B-103 (P3 M2; decisions B9): hops and reach for vehicles that are driving, against parked ones.

    python tools/atc/run_b103.py        # -> results/E53_bitrate.json key "driving_split", rows added to E53_table.csv

1. The E40 month (E48 step month_links: the B-80 'with' run, seed 1, July 2028, mesh line of sight, default link
   rule): at each decision epoch with the base up, every robot's hop count to BASE (BFS over the mesh links of that
   epoch), split by whether the robot is driving at that epoch (its route sample one minute later differs).
   This is where the papers' 1.024 hops comes from.
2. E53's draws (20 rovers, 30 draws, and every N) with positions drawn from the driving vehicle-steps only, and
   from the parked ones only, of the same pool (the 1x July trace, seed 1, every 7th step): busiest-link load,
   hops, reach, and the airtime on a scheduled channel (eta 0.8) and slotted random access (eta 1/e).
3. The source load if STATUS and INTENT went at 1 Hz like POSITION (the referee's 19.5 kbit/s for 20 robots).
E53's existing rows and keys are not changed; the new rows carry geometry "fleet_driving" / "fleet_parked".
"""
from __future__ import annotations

import csv
import gzip
import json
import os
import pickle
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_e53 as E3  # noqa: E402

KEY = "driving_split"


def e40_month():
    import export_trace as XT
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    (month, t0, t1, share), _ = XT.dark_month()
    spec = XT.RUNS["with"]
    sc = XT._scenario("with", t1)
    mech = G.mechanism(spec["regime"])
    epochs = []

    def wrapped(sim, waiting, free, **k):
        jobs = mech(sim, waiting, free, **k)
        st, t = sim.atc, sim.t
        if st is not None and t0 <= t <= t1 and st.base_up(t):
            alive = [v for v in sorted(sim.vehicles, key=lambda v: v.id) if getattr(v, "alive", True)]
            nodes = [(v.id, int(st.position(v, t)), G.antenna_m(v), int(st.position(v, t + 1.0 / 60.0)) != int(st.position(v, t)))
                     for v in alive]
            epochs.append((t, nodes, dict(st.radio_kw), st.site_index("BASE")))
        return jobs
    for a in ("anticipates", "supports_team", "regime", "__name__"):
        if hasattr(mech, a):
            setattr(wrapped, a, getattr(mech, a))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        Simulation(sc, wrapped, seed=1, mech_kwargs=dict(spec["kw"], start_year=XT.YEAR)).run()
    rm = G._mesh()
    out = {s: {"robot_epochs": 0, "hops": [], "cut": 0} for s in ("driving", "parked", "all")}
    for t, nodes, rk, base_idx in epochs:
        allnodes = nodes + [("BASE", base_idx, G.ANT_MAST_M, False)]
        adj = {n[0]: [] for n in allnodes}
        for i in range(len(allnodes)):
            for j in range(i + 1, len(allnodes)):
                a, b = allnodes[i], allnodes[j]
                if rm.link(a[1], b[1], a[2], b[2], **rk):
                    adj[a[0]].append(b[0])
                    adj[b[0]].append(a[0])
        hp, q = {"BASE": 0}, ["BASE"]
        for u in q:
            for w in adj[u]:
                if w not in hp:
                    hp[w] = hp[u] + 1
                    q.append(w)
        for vid, _, _, drv in nodes:
            for s in ("driving" if drv else "parked", "all"):
                out[s]["robot_epochs"] += 1
                if vid in hp:
                    out[s]["hops"].append(hp[vid])
                else:
                    out[s]["cut"] += 1
    res = {"epochs": len(epochs), "month": month, "note": "default link rule (mesh line of sight within 5 km), as "
           "E48 month_links 'default'; driving = the robot's route sample one minute after the epoch differs"}
    for s, r in out.items():
        h = np.array(r["hops"], float)
        res[s] = {"robot_epochs": r["robot_epochs"], "path_share": round(1 - r["cut"] / max(1, r["robot_epochs"]), 4),
                  "mean_hops_connected": round(float(h.mean()), 3) if len(h) else None,
                  "hop_histogram": {str(int(k)): int((h == k).sum()) for k in np.unique(h)}}
    ref = json.load(open(os.path.join(ROOT, "results", "E48_sizing.json")))["revision"]["two_ray_in_the_mesh"]["e40_month"]["variants"]["default"]
    res["check_against_E48"] = {"all_mean_hops": res["all"]["mean_hops_connected"], "E48_mean_hops": ref["mean_hops_to_base_connected"],
                                "all_robot_epochs": res["all"]["robot_epochs"], "E48_robot_epochs": ref["robot_epochs_with_base_up"]}
    return res


def pools():
    """E53's pool (1x July trace, seed 1, every 7th vehicle-step) split by driving (ds > 0) and parked."""
    idx, g = E3.positions()
    tr = pickle.load(gzip.open(os.path.join(ROOT, ".cache", "atc", "e50", "trace_m1_s1.pkl.gz")))
    ds = np.asarray(tr["ds"]).reshape(-1)[::7]
    assert len(ds) == len(idx)
    return {"fleet_driving": idx[ds > 0], "fleet_parked": idx[ds == 0]}, g, float((ds > 0).mean())


def main():
    t_s = time.time()
    P, g, drv_share = pools()
    rows, cells = [], {}
    for geo, pool in P.items():
        for auth in (True, False):
            for f in E3.RATES_HZ:
                rate, size, bps = E3.per_rover(f, auth)
                beacon = sum(bps[k] for k in E3.BEACONS)
                event = sum(v for k, v in bps.items() if k not in E3.BEACONS)
                per = beacon + event
                for N in E3.N_ROVERS:
                    rng = np.random.default_rng([53, N])        # E53's draw streams
                    res = [E3.busiest(pool[rng.integers(0, len(pool), N)], g, beacon, event) for _ in range(E3.DRAWS)]
                    L_ = np.array([r[0] for r in res]) * 8 / 1000.0
                    row = {"geometry": geo, "auth": "on" if auth else "off", "position_hz": f, "rovers": N,
                           "per_rover_kbps": round(per * 8 / 1000.0, 4), "one_hop_sum_kbps": round(N * per * 8 / 1000.0, 3),
                           "busiest_link_kbps_mean": round(float(L_.mean()), 3),
                           "busiest_link_kbps_p95": round(float(np.quantile(L_, 0.95)), 3),
                           "mean_hops_to_base": round(float(np.nanmean([r[1] for r in res])), 3),
                           "reachable_share": round(float(np.mean([r[2] for r in res])), 4)}
                    for cn, ck in E3.CHANNELS_KBPS.items():
                        key = "nb" if ck == 16.0 else "bb"
                        row[f"fits_{key}_raw_p95"] = bool(row["busiest_link_kbps_p95"] <= ck)
                        for en, ev in E3.ETA.items():
                            row[f"fits_{key}_{en}_p95"] = bool(row["busiest_link_kbps_p95"] / ev <= ck)
                    rows.append(row)
                    cells[(geo, auth, f, N)] = row
    # (3) STATUS and INTENT at 1 Hz
    rate, size, bps = E3.per_rover(1.0, True)
    three = sum(size[k] for k in ("POSITION", "STATUS", "INTENT"))
    rate1 = dict(rate, STATUS=1.0, INTENT=1.0)
    rate1["HELLO"] = max(0.0, 1.0 - sum(v for k, v in rate1.items() if k != "HELLO"))   # HELLO only fills up to 1 Hz
    per1 = sum(rate1[k] * size[k] for k in rate1)
    beacon1 = sum(rate1[k] * size[k] for k in E3.BEACONS)
    event1 = per1 - beacon1
    load1 = {}
    for geo in ("fleet", "fleet_driving"):
        pool = P.get(geo) if geo != "fleet" else E3.positions()[0]
        rng = np.random.default_rng([53, 20])
        L_ = np.array([E3.busiest(pool[rng.integers(0, len(pool), 20)], g, beacon1, event1)[0] for _ in range(E3.DRAWS)]) * 8 / 1000
        load1[geo] = {"busiest_link_kbps_mean": round(float(L_.mean()), 3), "busiest_link_kbps_p95": round(float(np.quantile(L_, 0.95)), 3)}
    status_intent_1hz = {
        "bytes_position_status_intent_auth": {k: size[k] for k in ("POSITION", "STATUS", "INTENT")},
        "three_beacons_per_rover_Bps": three, "three_beacons_20_rovers_kbps": round(20 * three * 8 / 1000.0, 3),
        "per_rover_all_messages_kbps": round(per1 * 8 / 1000.0, 4), "sources_20_rovers_kbps": round(20 * per1 * 8 / 1000.0, 3),
        "busiest_link_20_rovers": load1,
        "scheduled_airtime_p95_kbps": {k: round(v["busiest_link_kbps_p95"] / E3.ETA["scheduled"], 3) for k, v in load1.items()},
        "note": "POSITION, STATUS and INTENT each at 1 Hz, authenticated; HELLO then not sent (it only fills up to 1 Hz); "
                "event messages as E53"}
    e40 = e40_month()
    eta = E3.ETA
    a20 = {geo: {f"{f:g} Hz": {k: cells[(geo, True, f, 20)][k] for k in ("busiest_link_kbps_mean", "busiest_link_kbps_p95",
                                                                        "mean_hops_to_base", "reachable_share")}
                 | {"scheduled_airtime_p95_kbps": round(cells[(geo, True, f, 20)]["busiest_link_kbps_p95"] / eta["scheduled"], 3),
                    "slotted_aloha_airtime_p95_kbps": round(cells[(geo, True, f, 20)]["busiest_link_kbps_p95"] / eta["slotted_aloha"], 3)}
                 for f in (1.0, 10.0)} for geo in P}
    E54 = json.load(open(os.path.join(ROOT, "results", "E54_dtn.json")))["link_shares"]
    blk = {"task": "B-103 (P3 M2; decisions B9)", "note": __doc__.strip().split("\n\n")[1].replace("\n", " "),
           "pool_driving_share": round(drv_share, 4), "e40_month": e40, "e53_auth_20_rovers": a20,
           "status_intent_at_1hz": status_intent_1hz,
           "e54_link_shares_30_seeds": {"linked_share_all_time": E54["linked_share_all_time"],
                                        "linked_share_driving_time": E54["linked_share_driving_time"]},
           "run_s": round(time.time() - t_s, 1)}
    doc = json.load(open(E3.OUT_JSON))
    doc[KEY] = blk
    with open(E3.OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    with open(E3.OUT_CSV, newline="", encoding="utf-8") as fh:
        old = [r for r in csv.DictReader(fh) if r["geometry"] not in P]
        fields = list(old[0])
    with open(E3.OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(old)
        w.writerows(rows)
    print(json.dumps({"pool_driving_share": blk["pool_driving_share"], "e40": {s: e40[s] for s in ("driving", "parked", "all")},
                      "check": e40["check_against_E48"], "e53": a20, "si1hz": status_intent_1hz}, indent=1))


def main_v02():
    """B-110: the driving split and the status-and-intent load with LRIP v0.2 sizes (HELLO at least every 10 s), without
    and with Proximity-1 framing (+12 B per packet) -> E53_bitrate.json lrip_v02.driving_split (other keys unchanged)."""
    from lunarsim.atc.lrip import codec as C
    t_s = time.time()
    P, g, drv_share = pools()
    hello_min = 1.0 / C.message("HELLO")["declaration_interval_s"]
    frame_b = C.schema()["framing"]["proximity1_frame_bytes"]
    blk = {"task": "B-110", "note": "as B-103 (driving_split) with v0.2 packet sizes and HELLO >= 0.1 Hz; 'proximity1' adds "
                                    f"{frame_b} B per packet; authenticated, 20 rovers, E53's draw streams",
           "pool_driving_share": round(drv_share, 4), "e53_auth_20_rovers": {}, "status_intent_at_1hz": {}}
    for framing in ("lrip", "proximity1"):
        fb = frame_b if framing == "proximity1" else 0
        blk["e53_auth_20_rovers"][framing] = {}
        for geo, pool in list(P.items()) + [("fleet", E3.positions()[0])]:
            key = geo if geo != "fleet" else "fleet_all"
            blk["e53_auth_20_rovers"][framing][key] = {}
            for f in (1.0, 10.0):
                rate, size, bps = E3.per_rover(f, True, minor=2, hello_min_hz=hello_min, frame_b=fb)
                beacon = sum(bps[k] for k in E3.BEACONS)
                event = sum(v for k, v in bps.items() if k not in E3.BEACONS)
                rng = np.random.default_rng([53, 20])
                res = [E3.busiest(pool[rng.integers(0, len(pool), 20)], g, beacon, event) for _ in range(E3.DRAWS)]
                L_ = np.array([r[0] for r in res]) * 8 / 1000.0
                p95 = float(np.quantile(L_, 0.95))
                blk["e53_auth_20_rovers"][framing][key][f"{f:g} Hz"] = {
                    "busiest_link_kbps_mean": round(float(L_.mean()), 3), "busiest_link_kbps_p95": round(p95, 3),
                    "mean_hops_to_base": round(float(np.nanmean([r[1] for r in res])), 3),
                    "reachable_share": round(float(np.mean([r[2] for r in res])), 4),
                    "scheduled_airtime_p95_kbps": round(p95 / E3.ETA["scheduled"], 3),
                    "slotted_aloha_airtime_p95_kbps": round(p95 / E3.ETA["slotted_aloha"], 3)}
        # STATUS and INTENT at 1 Hz like POSITION
        rate, size, bps = E3.per_rover(1.0, True, minor=2, hello_min_hz=hello_min, frame_b=fb)
        rate1 = dict(rate, STATUS=1.0, INTENT=1.0)
        rate1["HELLO"] = max(hello_min, 1.0 - sum(v for k, v in rate1.items() if k != "HELLO"))
        per1 = sum(rate1[k] * size[k] for k in rate1)
        beacon1 = sum(rate1[k] * size[k] for k in E3.BEACONS)
        load = {}
        for geo, pool in (("fleet", E3.positions()[0]), ("fleet_driving", P["fleet_driving"])):
            rng = np.random.default_rng([53, 20])
            L_ = np.array([E3.busiest(pool[rng.integers(0, len(pool), 20)], g, beacon1, per1 - beacon1)[0]
                           for _ in range(E3.DRAWS)]) * 8 / 1000
            load[geo] = {"busiest_link_kbps_p95": round(float(np.quantile(L_, 0.95)), 3),
                         "scheduled_airtime_p95_kbps": round(float(np.quantile(L_, 0.95)) / E3.ETA["scheduled"], 3)}
        blk["status_intent_at_1hz"][framing] = {
            "bytes": {k: size[k] for k in ("POSITION", "STATUS", "INTENT", "HELLO")},
            "three_beacons_20_rovers_kbps": round(20 * sum(size[k] for k in ("POSITION", "STATUS", "INTENT")) * 8 / 1000, 3),
            "sources_20_rovers_kbps": round(20 * per1 * 8 / 1000, 3), "busiest_link_20_rovers": load}
    blk["run_s"] = round(time.time() - t_s, 1)
    doc = json.load(open(E3.OUT_JSON))
    doc["lrip_v02"]["driving_split"] = blk
    with open(E3.OUT_JSON, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, indent=1)
        fh.write("\n")
    print(json.dumps(blk, indent=1)[:3500])


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(540, exit=True)
    if len(sys.argv) > 1 and sys.argv[1] == "v02":
        main_v02()
    else:
        main()
