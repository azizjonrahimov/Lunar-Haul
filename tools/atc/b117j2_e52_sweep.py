"""B-117 (j2), P3 S17: E52's map change rates swept, one at a time around the defaults.

    python tools/atc/b117j2_e52_sweep.py      # -> results/E52_sweep.json (a new file; seconds per setting)

E52 (tools/atc/run_e52.py) has one setting of its assumed change rates: 42 route tiles a day get new versions (note 02
D, ASSUMED there), 2 new hazards a day, 0.3 keep-outs a day and 5 road edges a day (ASSUMED). Here each rate is varied
alone, the others at their defaults, on E52's seeds (1-30) and code (run_e52.run_seed with the module's rates set):
tiles a day {10, 21, 42, 84}, hazards a day {0.5, 1, 2, 5, 10}, keep-outs a day {0, 0.3, 1, 3}, road edges a day
{0, 5, 20, 50}. Per setting: H12's two clauses (hazards-first bytes after 24 h against a full resend, at 100 kbit/s;
the hazard layer current sooner than oldest-first at every link rate, 24 h) and the stale-map hits after 24 h and 7 d
at 16 kbit/s. The default setting must reproduce results/E52_map.json's h12 and rows (a check; refused otherwise).
Pre-declared in the B-117 estimate (13 Nov) as the change rates; the grids are fixed here before any row.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for _p in (ROOT, HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import run_e52 as E  # noqa: E402

OUT = os.path.join(ROOT, "results", "E52_sweep.json")
GRID = {"TILES_PER_DAY": [10, 21, 42, 84], "HAZARD_PER_DAY": [0.5, 1.0, 2.0, 5.0, 10.0],
        "KEEPOUT_PER_DAY": [0.0, 0.3, 1.0, 3.0], "ROAD_EDGES_PER_DAY": [0.0, 5.0, 20.0, 50.0]}
DEFAULT = {k: getattr(E, k) for k in GRID}


def summarise(rows):
    from lunarsim.atc import smap as S
    get = lambda D, o, r, f: float(np.mean([x[f] for x in rows if x["out_h"] == D and x["order"] == o and x["rate_kbps"] == r]))
    share24 = round(get(24, "hazards_first", 100, "bytes") / S.full_resend_bytes(), 5)
    sooner = {str(r): get(24, "hazards_first", r, "t_hazards_current_s") < get(24, "oldest_first", r, "t_hazards_current_s")
              for r in E.RATES_KBPS}
    return {"share_of_full_resend_24h": share24, "sooner_at_every_rate": sooner,
            "h12_supported": bool(share24 < 0.10 and all(sooner.values())),
            "t_hazards_current_24h_s": {o: {str(r): round(get(24, o, r, "t_hazards_current_s"), 2) for r in E.RATES_KBPS}
                                        for o in ("hazards_first", "oldest_first")},
            "tiles_changed_24h": round(get(24, "hazards_first", 100, "tiles_changed"), 1),
            "hits_during_outage": {f"{D} h": round(get(D, "hazards_first", 16, "hits_during_outage"), 3) for D in (24, 168)},
            "hits_after_contact_16kbps": {f"{D} h": {o: round(get(D, o, 16, "hits_after_contact"), 4)
                                                      for o in ("hazards_first", "oldest_first")} for D in (24, 168)}}


def run(setting):
    for k, v in DEFAULT.items():
        setattr(E, k, setting.get(k, v))
    tour, length = E.route_tiles()
    route_set = {t for t, _ in tour}
    rows = []
    for s in range(1, E.SEEDS + 1):
        rows += E.run_seed(s, tour, length, route_set)
    for k, v in DEFAULT.items():
        setattr(E, k, v)
    return rows


def main():
    t0 = time.time()
    stored = json.load(open(E.OUT_JSON, encoding="utf-8"))
    base = summarise(run({}))
    h = stored["h12"]
    if not (base["share_of_full_resend_24h"] == h["share_of_full_resend_24h"]
            and base["sooner_at_every_rate"] == {k: v for k, v in h["sooner_at_every_rate"].items()}
            and base["h12_supported"] == h["supported"]):
        raise SystemExit(f"the default setting does not reproduce results/E52_map.json h12: {base} vs {h}")
    out = {"task": "B-117 (j2), P3 S17: E52 change rates swept one at a time",
           "note": __doc__.split("\n\n")[1].strip() + " " + __doc__.split("\n\n")[2].strip(),
           "defaults": DEFAULT, "default_reproduces_E52_map_h12": True, "seeds": E.SEEDS, "sweeps": {}}
    for k, vals in GRID.items():
        out["sweeps"][k] = {str(v): (base if v == DEFAULT[k] else summarise(run({k: v}))) for v in vals}
        print(k, {v: (s["share_of_full_resend_24h"], s["h12_supported"]) for v, s in out["sweeps"][k].items()}, flush=True)
    out["h12_supported_in_every_setting"] = all(s["h12_supported"] for sw in out["sweeps"].values() for s in sw.values())
    out["run_s"] = round(time.time() - t0, 1)
    text = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with open(OUT + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(OUT + ".tmp", OUT)
    print("->", OUT, out["run_s"], "s; H12 supported in every setting:", out["h12_supported_in_every_setting"])


if __name__ == "__main__":
    import faulthandler
    faulthandler.dump_traceback_later(540, exit=True)
    main()
