"""Static scenario gallery for the 3D world (B-36): 12 curated cells, each a seed-3 scene package (lunarsim-scene v1)
plus headline numbers (mean and 95 % CI over 20 seeds) in data/scenes/gallery.json, so the site needs no server.

    python experiments/phase4/gallery.py scenes   [--only ID,ID] [--force] [--max-seconds 540]  # missing packages
    python experiments/phase4/gallery.py headline [--seeds 20] [--max-seconds 540]   # resumable -> results/gallery_runs.csv
    python experiments/phase4/gallery.py index                                       # -> data/scenes/gallery.json

Every cell runs with the settings of the committed sample packages, as `lunarsim.scene` was called for them:
--terrain connecting_ridge --landing-model classical --plume 1,0.5 --autonomy driving-v1, seed 3 for the replay.
Packages that already exist under data/scenes (P1, P2, P3, P2-comms-dte, P2V2) are reused as they are; `scenes`
rebuilds one only with --force. The replay seed is one of the headline seeds, so the replay is a member of the
sample its numbers describe. Headline: the delivered tonnes inside the year (delivered_kg_in_horizon when the Earth
link is modelled, else delivered_kg, which then are the same), the urgent mean and p90 delay, the share of urgent items
within 24 h, the cost per landed kg and the rover-hours waiting for Earth; mean over seeds and 1.96 sd / sqrt(n), as
experiments/phase3/fit_law.cell_means.
"""
from __future__ import annotations

import argparse
import faulthandler
import hashlib
import json
import math
import os
import sys
import time
import warnings
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore", category=RuntimeWarning)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

SCENES = os.path.join(ROOT, "data", "scenes")
RUNS = os.path.join(ROOT, "results", "gallery_runs.csv")
GALLERY = os.path.join(SCENES, "gallery.json")
REPLAY_SEED = 3
N_SEEDS = 20
BUDGET_GZ_BYTES = 4 * 2**20
COMMON_ARGS = ["--terrain", "connecting_ridge", "--landing-model", "classical", "--plume", "1,0.5",
               "--autonomy", "driving-v1"]
RELAY_08 = {"mode": "dte+relay", "relay": {"coverage": 0.8, "gap_model": "parametric"}}

GROUPS = [
    {"id": "phases", "title": "Three phases, two job rules",
     "description": "The base as it grows, with each company running its own rovers or every rover taking any job."},
    {"id": "pads", "title": "How far the pads are",
     "description": "The second phase with the shared job rule and the landing pads nearer or farther than the usual distance."},
    {"id": "earth", "title": "Earth below the horizon",
     "description": "The second phase when supervised rovers need Earth in view, with and without a relay or autonomy."},
    {"id": "fleet", "title": "A small fleet",
     "description": "The second phase with fewer rovers."},
]

# id, package folder, group, title, description (plain words), scenario, job rule, pad standoff (km), comms, fleet autonomy
CELLS: List[Dict[str, Any]] = [
    dict(id="p1-inhouse", package="P1-inhouse", group="phases", title="First phase, own rovers",
         description="A small outpost; each company drives only its own rovers.",
         scenario="P1-default", mechanism="inhouse", standoff="1"),
    dict(id="p1-marketplace", package="P1", group="phases", title="First phase, shared rovers",
         description="A small outpost; every rover can take any company's job, offered in an auction.",
         scenario="P1-default", mechanism="marketplace", standoff="1"),
    dict(id="p2-inhouse", package="P2-inhouse", group="phases", title="Second phase, own rovers",
         description="A busier base; each company drives only its own rovers.",
         scenario="P2-default", mechanism="inhouse", standoff="1"),
    dict(id="p2-marketplace", package="P2", group="phases", title="Second phase, shared rovers",
         description="A busier base; every rover can take any job. The reference for the other second-phase scenes.",
         scenario="P2-default", mechanism="marketplace", standoff="1"),
    dict(id="p3-inhouse", package="P3-inhouse", group="phases", title="Third phase, own rovers",
         description="The full base with bulk cargo; each company drives only its own rovers.",
         scenario="P3-default", mechanism="inhouse", standoff="1"),
    dict(id="p3-marketplace", package="P3", group="phases", title="Third phase, shared rovers",
         description="The full base with bulk cargo; every rover can take any job.",
         scenario="P3-default", mechanism="marketplace", standoff="1"),
    dict(id="p2-pads-near", package="P2-pads-0.5km", group="pads", title="Pads close to the base",
         description="The landing pads half the usual distance from the base: shorter drives, more ejecta.",
         scenario="P2-default", mechanism="marketplace", standoff="0.5"),
    dict(id="p2-pads-far", package="P2-pads-3km", group="pads", title="Pads far from the base",
         description="The landing pads three times the usual distance: longer drives, the base out of the spray.",
         scenario="P2-default", mechanism="marketplace", standoff="3"),
    dict(id="p2-earth-direct", package="P2-comms-dte", group="earth", title="Direct links to Earth only",
         description="Supervised rovers drive only while Earth is in view of their whole route.",
         scenario="P2-default", mechanism="marketplace", standoff="1", comms="dte"),
    dict(id="p2-earth-relay", package="P2-comms-relay-0.8", group="earth", title="A relay most of the time",
         description="As with direct links, plus a relay satellite in view most of the time.",
         scenario="P2-default", mechanism="marketplace", standoff="1", comms=RELAY_08),
    dict(id="p2-earth-autonomous", package="P2-comms-dte-autonomous", group="earth", title="Autonomous rovers, direct links",
         description="Direct links only, but every rover drives itself and needs no link.",
         scenario="P2-default", mechanism="marketplace", standoff="1", comms="dte", fleet_autonomy="autonomous"),
    dict(id="p2-small-fleet", package="P2V2", group="fleet", title="Second phase, four rovers",
         description="The second phase with four rovers instead of the usual fleet, shared.",
         scenario="P2-4-vehicles", mechanism="marketplace", standoff="1"),
]

METRICS = [  # key, column, label, unit, scale, digits
    ("delivered_t", None, "Cargo delivered in the year", "t", 1.0, 0),
    ("delay_prio1_mean_h", "delay_prio1_mean_h", "Mean wait of urgent cargo", "h", 1.0, 1),
    ("delay_prio1_p90_h", "delay_prio1_p90_h", "One in ten urgent items waits longer than", "h", 1.0, 0),
    ("sl24_prio1", "sl24_prio1", "Urgent items delivered within a day", "%", 100.0, 0),
    ("cost_per_landed_kg_usd", "cost_per_landed_kg_usd", "Surface cost per landed kg", "$/kg", 1.0, 0),
    ("blackout_wait_vehicle_h", "blackout_wait_vehicle_h", "Rover-hours waiting for Earth", "h", 1.0, 0),
]


def scenario_of(cell: Dict[str, Any]):
    """(Scenario, job-rule function, kwargs) exactly as `python -m lunarsim.scene --scenario ...` builds them."""
    from lunarsim.cli import _add_phase3_args, _mechanism, _scenario_ex, _with_file_opts, _with_phase3
    ap = argparse.ArgumentParser()
    _add_phase3_args(ap)
    args = COMMON_ARGS + ["--pad-standoff", cell["standoff"]]
    if cell.get("comms"):
        c = cell["comms"]
        args += ["--comms", json.dumps(c) if isinstance(c, dict) else c]
    sc, file_kw = _scenario_ex(cell["scenario"])
    sc = _with_phase3(sc, ap.parse_args(args))
    if cell.get("fleet_autonomy"):
        sc = sc.with_(fleet=[(o, c, cell["fleet_autonomy"], s) for (o, c, _, s) in sc.fleet])
    fn, kw = _mechanism(cell["mechanism"])
    return sc, fn, _with_file_opts(cell["mechanism"], kw, file_kw)


def flags_of(cell: Dict[str, Any]) -> Dict[str, Any]:
    sc, _, _ = scenario_of(cell)
    c = cell.get("comms")
    comms = "always" if not c else (c if isinstance(c, str) else f"{c['mode']} {c['relay']['coverage']:g}")
    return {"scenario": cell["scenario"], "phase": cell["scenario"].split("-")[0], "job_rule": cell["mechanism"],
            "pad_standoff_km": float(cell["standoff"]), "earth_link": comms,
            "fleet": "all autonomous" if cell.get("fleet_autonomy") else "default",
            "n_vehicles": len(sc.fleet), "landing_model": "classical", "plume": {"keepout_km": 1.0, "standdown_h": 0.5},
            "autonomy_model": "driving-v1", "terrain": "connecting_ridge"}


def _deadline(max_s: float):
    if max_s and max_s > 0:
        faulthandler.dump_traceback_later(max_s, exit=True)
    return time.time() + (max_s - 60 if max_s and max_s > 120 else float("inf"))


# ---------------------------------------------------------------------------------------------------------
def cmd_scenes(a) -> None:
    from lunarsim import scene as SCN
    from lunarsim.engine import Simulation
    stop = _deadline(a.max_seconds)
    only = set(a.only.split(",")) if a.only else None
    for cell in CELLS:
        if only and cell["id"] not in only:
            continue
        out = os.path.join(SCENES, cell["package"])
        if os.path.isfile(os.path.join(out, "scene.json")) and not a.force:
            print(f"[{cell['id']}] {cell['package']} exists, kept")
            continue
        if time.time() > stop:
            print("time budget reached; run again to continue")
            return
        t0 = time.time()
        sc, fn, kw = scenario_of(cell)
        sim = Simulation(sc, fn, seed=REPLAY_SEED, mech_kwargs=dict(kw, trace=True))
        sim.run()
        trace = json.loads(json.dumps(sim.trace_export(mechanism=cell["mechanism"])))
        idx = SCN.build(trace, out)
        print(f"[{cell['id']}] wrote {cell['package']}: {len(idx['chunks'])} chunks, "
              f"{sum(c['segments']['rows'] for c in idx['chunks'])} segments, gzip {SCN.gz_size(out) / 2**20:.2f} MB, "
              f"checks {idx['checks']}, {time.time() - t0:.1f} s")


def _done(path: str) -> set:
    if not os.path.exists(path):
        return set()
    d = pd.read_csv(path, usecols=["cell", "seed"])
    return set(zip(d["cell"], d["seed"].astype(int)))


def _append(path: str, row: Dict[str, Any]) -> None:
    df = pd.DataFrame([row])
    if not os.path.exists(path):
        df.to_csv(path, index=False, lineterminator="\n")
        return
    cols = list(pd.read_csv(path, nrows=0).columns)
    if set(df.columns) - set(cols):
        pd.concat([pd.read_csv(path), df], ignore_index=True, sort=False).to_csv(path, index=False, lineterminator="\n")
    else:
        df.reindex(columns=cols).to_csv(path, mode="a", header=False, index=False, lineterminator="\n")


def cmd_headline(a) -> None:
    from lunarsim.engine import run
    stop = _deadline(a.max_seconds)
    done = _done(a.runs)
    todo = [(c, s) for c in CELLS for s in range(a.seeds) if (c["id"], s) not in done]
    print(f"[headline] {len(CELLS)} cells x {a.seeds} seeds: {len(done)} rows in {os.path.relpath(a.runs, ROOT)}, "
          f"{len(todo)} to run")
    t_all = time.time()
    for i, (cell, s) in enumerate(todo):
        if time.time() > stop:
            print(f"time budget reached after {i} runs; run again to continue")
            return
        sc, fn, kw = scenario_of(cell)
        t0 = time.time()
        r = run(sc, fn, seed=s, **kw)
        r = {"cell": cell["id"], **{k: v for k, v in r.items() if k != "seed"}, "seed": s, "run_s": round(time.time() - t0, 2)}
        _append(a.runs, r)
        if (i + 1) % 20 == 0 or i + 1 == len(todo):
            print(f"  {i + 1}/{len(todo)} ({time.time() - t_all:.0f} s)")


def _r(x: float) -> float:
    """12 significant digits: numpy's reductions differ in the last bit between machines (SIMD width)."""
    return float(f"{float(x):.12g}")


def headline_numbers(runs: pd.DataFrame, cell_id: str, seeds: int) -> Dict[str, Any]:
    sub = runs[(runs["cell"] == cell_id) & (runs["seed"] < seeds)]
    if sub["seed"].nunique() < seeds:
        return None
    out: Dict[str, Any] = {"n_seeds": int(sub["seed"].nunique())}
    for key, col, _, _, scale, _ in METRICS:
        if key == "delivered_t":
            v = (sub["delivered_kg_in_horizon"] if "delivered_kg_in_horizon" in sub and sub["delivered_kg_in_horizon"].notna().all()
                 else sub["delivered_kg"]).to_numpy(float) / 1000.0
        elif col in sub:
            v = sub[col].to_numpy(float)
        else:
            continue
        v = v[np.isfinite(v)] * scale
        if not len(v):
            continue
        out[key] = {"mean": _r(v.mean()), "ci95": _r(1.96 * v.std(ddof=1) / math.sqrt(len(v))) if len(v) > 1 else None,
                    "n": int(len(v))}
    return out


def build_index(root: str = ROOT, runs_path: str = None, seeds: int = N_SEEDS) -> Dict[str, Any]:
    from lunarsim import scene as SCN
    runs_path = runs_path or os.path.join(root, "results", "gallery_runs.csv")
    runs = pd.read_csv(runs_path) if os.path.exists(runs_path) else None
    scenes, total = [], 0
    for cell in CELLS:
        pkg = os.path.join(root, "data", "scenes", cell["package"])
        with open(os.path.join(pkg, "scene.json"), encoding="utf-8") as f:
            idx = json.load(f)
        gz = SCN.gz_size(pkg)
        total += gz
        head = headline_numbers(runs, cell["id"], seeds) if runs is not None else None
        scenes.append({"id": cell["id"], "package": cell["package"], "group": cell["group"], "title": cell["title"],
                       "description": cell["description"], "flags": flags_of(cell),
                       "replay": {"seed": idx["seed"], "summary": idx.get("summary", {}), "gz_bytes": gz,
                                  "files": 2 + len(idx["chunks"])},
                       "headline": head,
                       "source": (f"results/gallery_runs.csv, cell {cell['id']}, seeds 0-{seeds - 1} "
                                  "(experiments/phase4/gallery.py headline)") if head else None})
    return {"format": "lunarsim-scene-gallery", "version": 1,
            "description": "Curated years of the base for the 3D world: each scene is a replay of one simulated year "
                           "(a lunarsim-scene v1 package under data/scenes/<package>) with headline numbers over "
                           f"{seeds} seeds of the same settings.",
            "common": {"terrain": "connecting_ridge", "landing_model": "classical", "plume": {"keepout_km": 1.0, "standdown_h": 0.5},
                       "autonomy_model": "driving-v1", "replay_seed": REPLAY_SEED, "seeds": seeds},
            "metrics": [{"key": k, "label": lab, "unit": u, "digits": d, "flag": "Modelled"} for k, _, lab, u, _, d in METRICS],
            "groups": GROUPS, "scenes": scenes, "total_gz_bytes": total, "budget_gz_bytes": BUDGET_GZ_BYTES}


def cmd_index(a) -> None:
    doc = build_index(seeds=a.seeds)
    missing = [s["id"] for s in doc["scenes"] if not s["headline"]]
    b = (json.dumps(doc, indent=1, ensure_ascii=False) + "\n").encode("utf-8")
    with open(GALLERY, "wb") as f:
        f.write(b)
    print(f"wrote {os.path.relpath(GALLERY, ROOT)} ({len(b) / 1024:.0f} kB): {len(doc['scenes'])} scenes, "
          f"packages {doc['total_gz_bytes'] / 2**20:.2f} MB gzip of {BUDGET_GZ_BYTES / 2**20:.0f} MB"
          + (f"; headline pending for {', '.join(missing)}" if missing else ""))
    if doc["total_gz_bytes"] > BUDGET_GZ_BYTES:
        raise SystemExit("over the gallery budget")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("scenes")
    p.add_argument("--only", default=None)
    p.add_argument("--force", action="store_true")
    p.add_argument("--max-seconds", type=float, default=540.0)
    p = sub.add_parser("headline")
    p.add_argument("--seeds", type=int, default=N_SEEDS)
    p.add_argument("--runs", default=RUNS)
    p.add_argument("--max-seconds", type=float, default=540.0)
    p = sub.add_parser("index")
    p.add_argument("--seeds", type=int, default=N_SEEDS)
    a = ap.parse_args(argv)
    {"scenes": cmd_scenes, "headline": cmd_headline, "index": cmd_index}[a.cmd](a)


if __name__ == "__main__":
    main()
