"""Phase-5 experiments for paper P1 (Lunar ATC): E40 main, E41 radio and messages, E42 team lifts (B-75).

Usage:  python experiments/phase5/run_phase5.py time                       # one seed of every E40 regime x load
        python experiments/phase5/run_phase5.py list --exp E40             # the cells, numbered
        python experiments/phase5/run_phase5.py run --exp E40 [--cells 0-11] [--max-seconds 540]
        (E41, E42 likewise)

Conventions as experiments/phase4/run_phase4.py: a cell is (tag, scenario, regime, settings) replicated over seeds
with common random numbers (same seed = same landings, manifests and mass draws across regimes); rows go to
results/<exp>_runs.csv at once, keyed by `cell` and `seed`, so a chunk can stop anywhere and the next resumes;
single process; --max-seconds stops starting runs that would end past the budget.

Common settings: p5 family (lunarsim/atc/p5.py, data/scenarios/p5/), 3 equal owners, team-lift share 0.10, radio
B-70 (5 km, 0 m margin, provisional), message loss 0.10 for the on-Moon regimes, A regimes with own_teams (an
owner's own robot pairs; LEAD, B-73), lost-link rally on (Assumed; LEAD, B-72).
Seeds and start years (PREREG): block v1 = seeds 1-30, start year 2028 + seed mod 4 (earth_link-v1); block v3 =
start years 2032, 2035, 2038, 2041, 2044 (earth_link-v3) x seeds 1-10.

E40  regime {A_EARTH strict, A_EARTH plan_ahead, A_MOON, B_EARTH strict, B_EARTH plan_ahead, B_EARTH_RELAY 0.8,
     B_EARTH_RELAY 1.0, C_LEADER, C_AUCTION, C_LEARNED_MLP, C_LEARNED_LIN, O_ORACLE} x load {10, 30, 60 %} x both
     blocks; sensitivity at 30 %, block v1: hopper_refuel for O_ORACLE and C_AUCTION (LEAD, B-71).
E41  at 30 % load, block v1, one factor at a time around C_* at loss 0.10, depth 1, range 5 km:
     loss {0, 0.10, 0.25, 0.40, burst 0.25} x {C_LEADER, C_AUCTION, C_LEARNED_MLP, C_LEARNED_LIN};
     depth {1, 2, 5} x loss {0.25, 0.40} x {C_AUCTION, C_LEARNED_MLP, C_LEARNED_LIN} (H3b);
     range {2, 5, 10 km, perfect} x the four regimes; rally off and a second 10 m mast at PAD_B (network design,
     LEAD, B-72) x the four regimes.
E42  at 30 % load, block v1, C_AUCTION: team-lift share {0, 0.10, 0.25} x cross-owner pairs {no, yes} x loss {0,
     0.10, 0.25, 0.40} with commit and a 1 h timeout; timeout {0.5, 2 h} and no-commit at share 0.25, cross-owner,
     loss {0.10, 0.25, 0.40}; exploratory: base-arbitrated meetings at the same three losses; A_EARTH strict with own
     teams at each share for the capacity split of H1.
"""
from __future__ import annotations

import argparse
import faulthandler
import math
import os
import sys
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
SCEN = os.path.join(ROOT, "data", "scenarios", "p5", "p5-{mix}-L{load}-T{team}.json")
V1_SEEDS = tuple(range(1, 31))
V3_YEARS = (2032, 2035, 2038, 2041, 2044)
V3_SEEDS = tuple(range(1, 11))
LOSS = 0.10
A_KW = {"own_teams": True, "team_lift": True}
REGIMES_E40 = [("A_EARTH strict", "A_EARTH", dict(A_KW, fallback="strict")),
               ("A_EARTH plan_ahead", "A_EARTH", dict(A_KW, fallback="plan_ahead")),
               ("A_MOON", "A_MOON", dict(A_KW)),
               ("B_EARTH strict", "B_EARTH", {"fallback": "strict"}),
               ("B_EARTH plan_ahead", "B_EARTH", {"fallback": "plan_ahead"}),
               ("B_EARTH_RELAY 0.8", "B_EARTH_RELAY", {"coverage": 0.8}),
               ("B_EARTH_RELAY 1.0", "B_EARTH_RELAY", {"coverage": 1.0}),
               ("C_LEADER", "C_LEADER", {"loss": LOSS}),
               ("C_AUCTION", "C_AUCTION", {"loss": LOSS}),
               ("C_LEARNED_MLP", "C_LEARNED_MLP", {"loss": LOSS}),
               ("C_LEARNED_LIN", "C_LEARNED_LIN", {"loss": LOSS}),
               ("O_ORACLE", "O_ORACLE", {})]
# Regimes that never wait for Earth: with no engine Earth-link rule in the p5 scenarios, their run for a seed is the
# same whatever the start year, so block v3 would repeat v1 seeds 1-10 (PREREG change 4). The unrun 60 % cells of these
# regimes run block v1 only; the 10 % and 30 % cells keep their keys (block "both") and rows.
EARTH_INDEPENDENT = {"O_ORACLE", "B_EARTH_RELAY 1.0", "A_EARTH full coverage", "C_LEADER", "C_AUCTION",
                     "C_LEARNED_MLP", "C_LEARNED_LIN", "O_ORACLE hopper_refuel", "C_AUCTION hopper_refuel"}
C_FOUR = [("C_LEADER", "C_LEADER"), ("C_AUCTION", "C_AUCTION"), ("C_LEARNED_MLP", "C_LEARNED_MLP"),
          ("C_LEARNED_LIN", "C_LEARNED_LIN")]


def start_year(seed: int) -> int:
    return 2028 + seed % 4


def blocks(which: str = "both") -> List[Tuple[str, int, Optional[int]]]:
    """(block, seed, start year or None = 2028 + seed mod 4)."""
    out = []
    if which in ("both", "v1"):
        out += [("v1", s, None) for s in V1_SEEDS]
    if which in ("both", "v3"):
        out += [("v3", s, y) for y in V3_YEARS for s in V3_SEEDS]
    if which.startswith("y"):                      # E43: "y2038:10" = start year 2038, seeds 1-10
        y, _, n = which[1:].partition(":")
        out += [(which, s, int(y)) for s in range(1, int(n or 30) + 1)]
    return out


def cell(exp, label, regime, kw, load="30", team="10", mix="3eq", block="both", **extra):
    tag = {"exp": exp, "label": label, "regime": regime, "load": int(load), "team_share": int(team) / 100.0,
           "owners": mix, "block": block}
    tag.update({k: v for k, v in kw.items() if k not in ("team_lift",)})
    tag.update(extra)
    return {"tag": tag, "regime": regime, "kw": dict(kw), "scen": SCEN.format(mix=mix, load=load, team=team),
            "block": block, "key": ";".join(f"{k}={tag[k]}" for k in sorted(tag) if k != "exp")}


def e40_cells() -> List[Dict[str, Any]]:
    cells = [cell("E40", lab, reg, kw, load=load,
                  block="v1" if load == "60" and lab in EARTH_INDEPENDENT else "both")
             for load in ("10", "30", "60") for lab, reg, kw in REGIMES_E40]
    for lab, reg, kw in REGIMES_E40:
        if lab in ("O_ORACLE", "C_AUCTION"):
            cells.append(cell("E40", lab + " hopper_refuel", reg, dict(kw), block="v1", hopper_refuel=True))
    for load in ("30", "60"):                  # H1's "A regimes with full coverage" (appended: indices 38-39)
        cells.append(cell("E40", "A_EARTH full coverage", "A_EARTH", dict(A_KW, fallback="strict", coverage=1.0), load=load,
                          block="v1" if load == "60" else "both"))
    return cells


def e41_cells() -> List[Dict[str, Any]]:
    cells = []
    for loss in (0.0, 0.10, 0.25, 0.40):
        for lab, reg in C_FOUR:
            cells.append(cell("E41", f"{lab} loss {loss:g}", reg, {"loss": loss}, block="v1"))
    for lab, reg in C_FOUR:
        cells.append(cell("E41", f"{lab} burst 0.25", reg, {"loss": 0.25, "loss_model": "burst"}, block="v1"))
    for depth in (2, 5):
        for loss in (0.25, 0.40):
            for lab, reg in C_FOUR[1:]:
                cells.append(cell("E41", f"{lab} depth {depth} loss {loss:g}", reg, {"loss": loss, "depth": depth}, block="v1"))
    for rng in (2000.0, 10000.0, "perfect"):
        for lab, reg in C_FOUR:
            kw = {"loss": LOSS, "radio": "perfect"} if rng == "perfect" else {"loss": LOSS, "d_max_m": rng}
            cells.append(cell("E41", f"{lab} range {rng if rng == 'perfect' else f'{rng / 1000:g} km'}", reg, kw, block="v1"))
    for lab, reg in C_FOUR:
        cells.append(cell("E41", f"{lab} rally off", reg, {"loss": LOSS, "rally": False}, block="v1"))
        cells.append(cell("E41", f"{lab} mast2 PAD_B", reg, {"loss": LOSS, "mast2": "PAD_B"}, block="v1"))
    return cells


def e42_cells() -> List[Dict[str, Any]]:
    cells = []
    for team in ("00", "10", "25"):
        for scope in ("same_owner", "any"):
            for loss in (0.0, 0.10, 0.25, 0.40):
                cells.append(cell("E42", f"C_AUCTION team {team} {scope} loss {loss:g}", "C_AUCTION",
                                  {"loss": loss, "team_scope": scope, "commit": True, "timeout_h": 1.0}, team=team, block="v1"))
        cells.append(cell("E42", f"A_EARTH strict own teams team {team}", "A_EARTH", dict(A_KW, fallback="strict"),
                          team=team, block="v1"))
    for loss in (0.10, 0.25, 0.40):
        for to in (0.5, 2.0):
            cells.append(cell("E42", f"C_AUCTION team 25 any loss {loss:g} timeout {to:g}", "C_AUCTION",
                              {"loss": loss, "team_scope": "any", "commit": True, "timeout_h": to}, team="25", block="v1"))
        cells.append(cell("E42", f"C_AUCTION team 25 any loss {loss:g} no commit", "C_AUCTION",
                          {"loss": loss, "team_scope": "any", "commit": False, "timeout_h": 1.0}, team="25", block="v1"))
        cells.append(cell("E42", f"C_AUCTION team 25 any loss {loss:g} arbitrated (exploratory)", "C_AUCTION",
                          {"loss": loss, "team_scope": "any", "commit": True, "timeout_h": 1.0, "arbitrate": True},
                          team="25", block="v1"))
    return cells


E43_K30 = 2.806                   # the 30 % load multiplier of data/scenarios/p5 (B-71 calibration)
E43_DENSITY = {1: (None, 30), 2: (None, 30), 4: (2160.0, 10), 8: (720.0, 10)}    # horizon h (None = a year), seeds
# 8x was 60 days (1440 h) in the design sent to LEAD; cut to 30 days after the first 8x run took 310 s at 60 days (over
# the 5 min per-run limit); seeds kept at 10, so the cut is in horizon only (rows carry horizon_days)
E43_DESIGN = os.path.join(ROOT, "data", "scenarios", "E43-design.json")   # not in p5/: that folder holds scenarios only
E43_PLUME = {"keepout_km": 1.0, "standdown_h": 0.75, "shelter": "auto"}           # R5: R 1 km, 30 + 15 min
SINGLE_SHARE = 0.15
SINGLE_SHARE_FLAG = ("ASSUMED: the 5 m DEM cannot see boulders, crater rims, shadows or graded one-lane roads; the "
                     "narrowest places at a 10 deg slope limit are marked first")


def e43_cells() -> List[Dict[str, Any]]:
    """E43 (B-77): road coordination mode x fleet density (fleet and demand both x m, 30 % load) x start year.
    Modes: "none" (no road layer and no landing closures), "atc", "uncoordinated" (R3-R6, R10 and the plume closure
    R5). Pooled dispatch (O_ORACLE) in every cell, so only road coordination differs. "none" and "atc" never wait for
    Earth, so their runs do not depend on the start year (one year per seed, PREREG change 4); "uncoordinated" runs
    2028 and 2038. 4x and 8x run 90 and 60 days, 10 seeds (a year at 4x takes ~6 min)."""
    cells = []

    def mk(mode, m, block, label_extra="", **roads):
        horizon, _ = E43_DENSITY[m]
        rd = None if mode == "none" else dict({"mode": mode, "single_share": SINGLE_SHARE,
                                               "single_share_flag": SINGLE_SHARE_FLAG, "bay_km": 1.0}, **roads)
        c = cell("E43", f"{mode} x{m}{label_extra}", "O_ORACLE", {}, block=block, mode=mode, density=m,
                 horizon_h=horizon or 8760.0, single_share=(rd or {}).get("single_share", 0.0),
                 bay_km=(rd or {}).get("bay_km", 0.0), r7=bool((rd or {}).get("r7", False)))
        c["build"] = {"m": m, "horizon": horizon, "roads": rd}
        cells.append(c)

    for m, (horizon, n) in E43_DENSITY.items():
        mk("none", m, f"y2028:{n}")
        mk("atc", m, f"y2028:{n}")
        for y in (2028, 2038):
            mk("uncoordinated", m, f"y{y}:{n}")
    for share in (0.0, 0.05, 0.40):                          # sweeps at 1x, 2028
        mk("atc", 1, "y2028:30", f" share {share:g}", single_share=share)
        mk("uncoordinated", 1, "y2028:30", f" share {share:g}", single_share=share)
    for bay in (0.5, 2.0):
        mk("atc", 1, "y2028:30", f" bay {bay:g}", bay_km=bay)
        mk("uncoordinated", 1, "y2028:30", f" bay {bay:g}", bay_km=bay)
    mk("atc", 1, "y2028:30", " r7", r7=True)
    return cells


def write_e43_design() -> None:
    """data/scenarios/E43-design.json: every E43 cell as built (density, horizon, roads incl. the ASSUMED flag)."""
    import json
    doc = {"experiment": "E43", "builder": "experiments/phase5/run_phase5.py e43_cells",
           "load_multiplier_30pct": E43_K30, "plume_R5": E43_PLUME,
           "single_share_flag": SINGLE_SHARE_FLAG,
           "design_changes": [{"what": "8x horizon 60 d -> 30 d (1440 h -> 720 h), 10 seeds kept",
                               "why": "the first 8x run took 310.2 s at 60 days (none x8, seed 1), over the 5 min "
                                      "per-run limit; the 60-day row is archived in results/archive/E43_runs.x8_60d.csv"},
                              {"what": "8x cells (indices 12-15) not run; the 30-day cut was never used for results",
                               "why": "a 30-day 8x run went past 470 s (none x8 seed 1: 7 d 1.8 s, 14 d 8.6 s, 21 d "
                                      "141 s); cause: duplicate consolidation WAKEs (lunarsim/dispatch.py:299, 2.37 M "
                                      "WAKEs and 1.6 M dispatch calls in 21 d); the opt-in dedupe failed the "
                                      "bit-identity gate (results/ATC_wake_check.json), so 8x is reported as not run"}],
           "not_run_cells": [12, 13, 14, 15],
           "cells": [{"index": i, "label": c["tag"]["label"], "key": c["key"], "block": c["block"],
                      "density": c["build"]["m"], "horizon_days": (c["build"]["horizon"] or 8760.0) / 24.0,
                      "roads": c["build"]["roads"]} for i, c in enumerate(e43_cells())]}
    os.makedirs(os.path.dirname(E43_DESIGN), exist_ok=True)
    with open(E43_DESIGN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")


EXPS = {"E40": e40_cells, "E41": e41_cells, "E42": e42_cells, "E43": e43_cells}


def run_one(c: Dict[str, Any], seed: int, year: Optional[int]) -> Dict[str, Any]:
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    from lunarsim.config import load_scenario
    if c.get("build"):                              # E43: fleet and demand x m, horizon, roads and closures
        from lunarsim.atc import p5 as P5
        b = c["build"]
        m = int(b["m"])
        sc = P5.build("3eq", k=E43_K30 * m, team_lift_share=0.10)
        sc = sc.with_(fleet=list(sc.fleet) * m, n_operators=sc.n_operators * m)
        if b["horizon"]:
            sc = sc.with_(horizon_h=float(b["horizon"]))
        if b["roads"]:
            sc = sc.with_(p5=dict(sc.p5, roads=dict(b["roads"])), plume=dict(E43_PLUME))
    else:
        sc = load_scenario(c["scen"])
    kw = dict(c["kw"])
    if c["tag"].get("hopper_refuel"):
        sc = sc.with_(p5=dict(sc.p5, hopper_refuel=True))
    y = year if year is not None else start_year(seed)
    kw["start_year"] = y
    t0 = time.time()
    sim = Simulation(sc, G.mechanism(c["regime"]), seed=seed, mech_kwargs=kw)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        out = sim.run()
    out = {k: v for k, v in out.items() if np.isscalar(v)}
    out.update(c["tag"])
    out.update({"seed": seed, "start_year": y, "cell": c["key"], "run_s": round(time.time() - t0, 2),
                "landings": len(sim.landing_schedule)})
    if c.get("build"):
        out["horizon_days"] = float(sc.horizon_h) / 24.0
    return out


def _csv(exp: str, part: str = "") -> str:
    """results/<exp>_runs.csv, or results/<exp>_runs.<part>.csv for another process (one writer per file)."""
    return os.path.join(RESULTS, f"{exp}_runs{'.' + part if part else ''}.csv")


def run_files(exp: str) -> List[str]:
    import glob
    return sorted(glob.glob(os.path.join(RESULTS, f"{exp}_runs.csv")) + glob.glob(os.path.join(RESULTS, f"{exp}_runs.*.csv")))


def load_runs(exp: str) -> pd.DataFrame:
    """The union of results/<exp>_runs*.csv; a cell + seed + start year present twice is an error."""
    fs = run_files(exp)
    if not fs:
        return pd.DataFrame()
    parts = []
    for f in fs:
        d = pd.read_csv(f, float_precision="round_trip")
        d["_file"] = os.path.basename(f)
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    dup = df.duplicated(["cell", "seed", "start_year"], keep=False)
    if dup.any():
        ex = df.loc[dup, ["cell", "seed", "start_year", "_file"]].head(6).to_dict("records")
        raise ValueError(f"{exp}: {int(dup.sum())} rows share a cell + seed + start year across run files, e.g. {ex}")
    return df.drop(columns="_file")


def _done(exp: str) -> set:
    """Keys already run in any of the run files (a duplicate across files is an error)."""
    out: set = set()
    for p in run_files(exp):
        d = pd.read_csv(p, usecols=["cell", "seed", "start_year"])
        keys = set(zip(d["cell"].astype(str), d["seed"].astype(int), d["start_year"].astype(int)))
        if out & keys:
            raise ValueError(f"{exp}: {len(out & keys)} keys appear in more than one run file ({os.path.basename(p)})")
        out |= keys
    return out


def _append(exp: str, row: Dict[str, Any], part: str = "") -> None:
    p = _csv(exp, part)
    new = pd.DataFrame([row])
    if os.path.isfile(p):
        cols = list(pd.read_csv(p, nrows=0).columns)
        if set(new.columns) - set(cols):                    # a new column: rewrite with the union, old order first
            old = pd.read_csv(p, float_precision="round_trip")
            pd.concat([old, new], ignore_index=True)[cols + [c for c in new.columns if c not in cols]].to_csv(
                p, index=False, lineterminator="\n")
            return
        new.reindex(columns=cols).to_csv(p, mode="a", header=False, index=False, lineterminator="\n")
    else:
        new.to_csv(p, index=False, lineterminator="\n")


def parse_cells(spec: Optional[str], n: int) -> List[int]:
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1))
    return [i for i in out if i < n]


def cmd_run(exp: str, cells_spec: Optional[str], max_s: float, part: str = "") -> bool:
    t0 = time.time()
    cells = EXPS[exp]()
    if exp == "E43":
        write_e43_design()
    done = _done(exp)
    last: Dict[str, float] = {}
    n_new = 0
    for i in parse_cells(cells_spec, len(cells)):
        c = cells[i]
        for blk, seed, year in blocks(c["block"]):
            y = year if year is not None else start_year(seed)
            if (c["key"], seed, y) in done:
                continue
            est = last.get(c["regime"] + c["tag"]["label"], 30.0)
            if time.time() - t0 > max_s - max(60.0, 1.5 * est):
                print(f"{exp}: time limit after {n_new} new runs; rerun")
                return False
            row = run_one(c, seed, year)
            last[c["regime"] + c["tag"]["label"]] = row["run_s"]
            _append(exp, row, part)
            done.add((c["key"], seed, y))
            n_new += 1
            print(f"  {exp} [{i}] {c['tag']['label']} L{c['tag']['load']} seed {seed} {y}: urgent "
                  f"{row.get('atc_urgent_wait_mean_cens_h', float('nan')):.1f} h ({row['run_s']} s)", flush=True)
    print(f"{exp}: cells {cells_spec or 'all'} done ({n_new} new runs)")
    return True


def cmd_time(max_s: float) -> None:
    """One v1 seed (seed 1, 2029) and one v3 seed (seed 1, 2038) of every E40 regime x load: run time per year."""
    import json
    t0 = time.time()
    path = os.path.join(ROOT, ".cache", "atc", "e40_timing.json")
    res = json.load(open(path)) if os.path.isfile(path) else {}
    for c in e40_cells():
        if c["block"] != "both":
            continue
        for seed, year in ((1, None), (1, 2038)):
            k = f"{c['key']}|{seed}|{year}"
            if k in res:
                continue
            if time.time() - t0 > max_s - 90:
                print("time: time limit; rerun")
                return
            r = run_one(c, seed, year)
            res[k] = {"label": c["tag"]["label"], "load": c["tag"]["load"], "year": r["start_year"], "run_s": r["run_s"]}
            os.makedirs(os.path.dirname(path), exist_ok=True)
            json.dump(res, open(path, "w"), indent=1)
            print(f"  {c['tag']['label']} L{c['tag']['load']} {r['start_year']}: {r['run_s']} s", flush=True)
    print("time: done")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python experiments/phase5/run_phase5.py")
    ap.add_argument("cmd", choices=["time", "list", "run"])
    ap.add_argument("--exp", default="E40", choices=sorted(EXPS))
    ap.add_argument("--cells", default=None)
    ap.add_argument("--part", default="", help="write results/<exp>_runs.<part>.csv (a second process uses its own file)")
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    faulthandler.dump_traceback_later(a.max_seconds + 60, exit=True)
    if a.cmd == "time":
        cmd_time(a.max_seconds)
    elif a.cmd == "list":
        for i, c in enumerate(EXPS[a.exp]()):
            n = len(blocks(c["block"]))
            print(f"{i:3d} {c['tag']['label']:48s} L{c['tag']['load']:<3d} team {c['tag']['team_share']:.2f} "
                  f"block {c['block']} ({n} runs)")
    else:
        cmd_run(a.exp, a.cells, a.max_seconds, a.part)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
