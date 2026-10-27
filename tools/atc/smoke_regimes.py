"""B-72 / B-73 smoke tables at 30 % load, 5 seeds (CRN across cells).

    python tools/atc/smoke_regimes.py run [--set regimes|auction]     # resumable (cached in .cache/atc/)
    python tools/atc/smoke_regimes.py table [--set regimes|auction]   # -> results/ATC_regimes_smoke.json,
                                                                      #    results/ATC_auction_smoke.json
    python tools/atc/smoke_regimes.py bounds                          # -> results/ATC_auction_bounds.json

regimes (B-72): every decision regime, 2028 and 2038. auction (B-73): C_AUCTION against O_ORACLE at message loss
0 / 0.10 / 0.25 / 0.40 (depth 1), depth 5 at loss 0 and 0.25, and team lifts without the commit step at loss 0.25,
2028.

Scenario: p5 3 equal owners, k for 30 % FLEX + Eagle busy (data/scenarios/p5/p5-3eq-L30-T10.json), team share
0.10. C_LEADER at message loss 0.10 (E40's level). Single process, --max-seconds 540.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import warnings
from typing import Any, Dict, List, Optional

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

CACHE = os.path.join(ROOT, ".cache", "atc", "smoke_regimes.json")
OUT = os.path.join(ROOT, "results", "ATC_regimes_smoke.json")
SCEN = os.path.join(ROOT, "data", "scenarios", "p5", "p5-3eq-L30-T10.json")
SEEDS = (1, 2, 3, 4, 5)
YEARS = (2028, 2038)
CELLS = [("O_ORACLE", {}), ("B_EARTH strict", {"fallback": "strict"}),
         ("B_EARTH plan_ahead", {"fallback": "plan_ahead"}), ("B_EARTH_RELAY 0.8", {"coverage": 0.8}),
         ("B_EARTH_RELAY 1.0", {"coverage": 1.0}), ("A_EARTH strict", {"fallback": "strict"}),
         ("A_EARTH plan_ahead", {"fallback": "plan_ahead"}), ("A_MOON", {}), ("C_LEADER loss 0.10", {"loss": 0.10})]
METRICS = ("atc_urgent_wait_mean_cens_h", "atc_urgent_wait_mean_h", "atc_urgent_wait_p95_cens_h",
           "atc_urgent_within24_share", "delivered_kg", "atc_deadhead_share", "p5_cargo_util", "utilisation",
           "atc_decider_down_share", "atc_backlog_end_blackout_t_mean", "atc_backlog_end_blackout_t_max",
           "atc_msgs_per_robot_h", "atc_robots_out_share", "atc_hand_conflicts", "atc_hand_wait_h", "atc_rallies",
           "atc_queue_jobs", "atc_standing_jobs", "team_lifts", "backlog_kg", "stranded_kg", "atc_blackouts")


AUCTION_CELLS = [("O_ORACLE", {}), ("C_AUCTION loss 0", {"loss": 0.0}), ("C_AUCTION loss 0.10", {"loss": 0.10}),
                 ("C_AUCTION loss 0.25", {"loss": 0.25}), ("C_AUCTION loss 0.40", {"loss": 0.40}),
                 ("C_AUCTION depth 5 loss 0", {"depth": 5}), ("C_AUCTION depth 5 loss 0.25", {"depth": 5, "loss": 0.25}),
                 ("C_AUCTION no commit loss 0.25", {"loss": 0.25, "commit": False})]
AUCTION_METRICS = ("atc_conflicts", "atc_parallel_winners", "atc_wasted_trips", "atc_claims_won", "atc_claims_run",
                   "atc_claims_stale", "atc_failed_meetings", "atc_team_no_agreement", "atc_meeting_wait_h")
SETS = {"regimes": (CELLS, YEARS, CACHE, OUT),
        "auction": (AUCTION_CELLS, (2028,), CACHE.replace("smoke_regimes", "smoke_auction"),
                    OUT.replace("ATC_regimes_smoke", "ATC_auction_smoke"))}
BOUNDS = os.path.join(ROOT, "results", "ATC_auction_bounds.json")


def regime_of(label: str) -> str:
    return label.split()[0]


def run_one(label: str, kw: Dict[str, Any], year: int, seed: int) -> Dict[str, Any]:
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    from lunarsim.config import load_scenario
    sc = load_scenario(SCEN)
    t = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        s = Simulation(sc, G.mechanism(regime_of(label)), seed=seed, mech_kwargs=dict(kw, start_year=year)).run()
    r = {m: (float(s[m]) if s.get(m) is not None else None) for m in METRICS + AUCTION_METRICS if m in s}
    r["wall_s"] = round(time.time() - t, 1)
    return r


def cmd_run(max_s: float, which: str = "regimes") -> bool:
    CELLS, YEARS, CACHE, OUT = SETS[which]
    t0 = time.time()
    done = json.load(open(CACHE)) if os.path.isfile(CACHE) else {}
    last = 10.0
    for year in YEARS:
        for label, kw in CELLS:
            for seed in SEEDS:
                key = f"{label}|{year}|{seed}"
                if key in done:
                    continue
                if time.time() - t0 > max_s - max(30.0, 2.5 * last):
                    print(f"run: time limit, {len(done)} of {len(YEARS) * len(CELLS) * len(SEEDS)} done; rerun")
                    return False
                r = run_one(label, kw, year, seed)
                last = r["wall_s"]
                done[key] = r
                os.makedirs(os.path.dirname(CACHE), exist_ok=True)
                with open(CACHE + ".tmp", "w") as f:
                    json.dump(done, f)
                os.replace(CACHE + ".tmp", CACHE)
                print(f"  {key}: urgent {r['atc_urgent_wait_mean_cens_h']:.1f} h, {r['delivered_kg'] / 1000:.0f} t "
                      f"({r['wall_s']} s)", flush=True)
    print("run: done")
    return True


def cmd_table(which: str = "regimes") -> Dict[str, Any]:
    CELLS, YEARS, CACHE, OUT = SETS[which]
    done = json.load(open(CACHE))
    out: Dict[str, Any] = {"task": "B-72" if which == "regimes" else "B-73", "scenario": os.path.relpath(SCEN, ROOT).replace(os.sep, "/"),
                           "seeds": list(SEEDS), "note": __doc__.split("\n\n")[-1].strip(), "years": {}}
    for year in YEARS:
        cells = {}
        ref = np.array([done[f"O_ORACLE|{year}|{s}"]["atc_urgent_wait_mean_cens_h"] for s in SEEDS])
        for label, kw in CELLS:
            rows = [done[f"{label}|{year}|{s}"] for s in SEEDS]
            c = {}
            for m in METRICS + AUCTION_METRICS:
                if m not in rows[0]:
                    continue
                v = np.array([r[m] if r[m] is not None else np.nan for r in rows], float)
                c[m] = [round(float(np.nanmean(v)), 4), round(float(np.nanstd(v, ddof=1)), 4)]
            d = np.array([r["atc_urgent_wait_mean_cens_h"] for r in rows]) - ref
            c["urgent_minus_oracle_h"] = [round(float(d.mean()), 3), round(float(d.std(ddof=1)), 3)]
            c["wall_s_mean"] = round(float(np.mean([r["wall_s"] for r in rows])), 1)
            cells[label] = c
        out["years"][str(year)] = cells
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    for year in YEARS:
        print(f"-- {year}")
        for label, _ in CELLS:
            c = out["years"][str(year)][label]
            print(f"{label:22s} urgent {c['atc_urgent_wait_mean_cens_h'][0]:8.1f} h (p95 {c['atc_urgent_wait_p95_cens_h'][0]:7.1f}, "
                  f"<=24 h {c['atc_urgent_within24_share'][0]:.3f})  {c['delivered_kg'][0] / 1000:6.0f} t  "
                  f"cargo {c['p5_cargo_util'][0]:.3f} fleet {c['utilisation'][0]:.3f}  down {c['atc_decider_down_share'][0]:.3f}  "
                  f"blackout-end backlog {c['atc_backlog_end_blackout_t_mean'][0]:6.1f} t  msg/rh {c['atc_msgs_per_robot_h'][0]:.2f}")
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/atc/smoke_regimes.py")
    ap.add_argument("cmd", choices=["run", "table", "bounds"])
    ap.add_argument("--set", default="regimes", choices=sorted(SETS))
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 30, exit=True)
    if a.cmd == "bounds":
        from lunarsim.atc.auction import bounds_check
        with open(BOUNDS, "w", encoding="utf-8", newline="\n") as f:
            json.dump(dict(bounds_check(200, 73), task="B-73"), f, indent=1)
            f.write("\n")
        print(f"bounds: {os.path.relpath(BOUNDS, ROOT)}")
    elif a.cmd == "run":
        cmd_run(a.max_seconds, a.set)
    else:
        cmd_table(a.set)
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from terrain_assets import peak_rss_mb
    rss = peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
