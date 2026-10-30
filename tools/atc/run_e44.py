"""E44 (B-78): the 12 encounter types, randomised, every vehicle through the one safety_check (lunarsim/atc/safety.py).

    python tools/atc/run_e44.py run [--types 1-12] [--n 100000] [--max-seconds 480]   # resumable, batch files
    python tools/atc/run_e44.py summarize        # -> results/E44_encounters.csv, results/E44_bounds.json
    python tools/atc/run_e44.py fixtures         # -> data/atc/encounter_fixtures/ (20 replays + index with tolerance)

Per batch: results/E44_parts/T<k>_b<j>.csv.gz, one row per encounter (seeded by (44, k, j): reproducible). Bounds per
type (traffic_and_safety.md §E): zero hard violations in n encounters -> one-sided 95 % upper bound 1 - 0.05^(1/n);
with importance sampling (types 6, 7, 9) n is the effective sample size (sum w)^2 / sum w^2 and the weights are reported;
with x > 0 violations the Clopper-Pearson upper bound (unweighted). Joint statement over the 12 types: Bonferroni,
alpha_k = 0.05 / 12. Deadlocks are counted only where no vehicle runs the random fuzzer (a fuzzer may idle on purpose);
type 1 encounters on slopes that friction cannot hold (v_max = 0) are not driven and are counted apart.
"""
from __future__ import annotations

import argparse
import faulthandler
import glob
import gzip
import io
import json
import math
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from lunarsim.atc import encounter as E, encounter_types as ET  # noqa: E402

PARTS = os.path.join(ROOT, "results", "E44_parts")
OUT_CSV = os.path.join(ROOT, "results", "E44_encounters.csv")
OUT_BOUNDS = os.path.join(ROOT, "results", "E44_bounds.json")
FIX_DIR = os.path.join(ROOT, "data", "atc", "encounter_fixtures")
BATCH = {1: 4000, 2: 2000, 3: 2000, 4: 2000, 5: 1000, 6: 1000, 7: 4000, 8: 2000, 9: 2000, 10: 1000, 11: 250, 12: 2000}
N_TARGET = {k: 10_000 for k in range(1, 13)}          # PREREG change 6: 10^4 per type, 10^5 for the cheap types 1 and 7
N_TARGET.update({1: 100_000, 7: 100_000})
OUT_BINS = os.path.join(ROOT, "results", "E44_bins.csv")
OUTCOMES = ("not_driven", "violation", "blocked_by_fault", "deadlock", "finished", "incomplete")
VIOL = ("viol_contact", "viol_gap", "viol_zone", "viol_crew", "viol_r3", "viol_slots")
NEAR = ("near_gap", "near_ttc", "near_crew", "near_zone")
PARAM_BINS = {1: ["theta", "mu"], 2: ["bay", "queued"], 3: ["oncoming"], 4: ["tiles", "n"], 5: ["K", "keep_free"],
              6: ["R", "kind", "inside_cls"], 7: ["variant"], 8: ["loss_bin"], 9: ["kind"], 10: ["haul"], 11: ["mult"],
              12: ["base_type"]}


def _peak_rss_mb():
    """Peak working set of this process (tracemalloc would slow the numpy loop many times over)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from terrain_assets import peak_rss_mb
    return peak_rss_mb()


VARIANTS = {"6_request_rule": {"type": 6, "prefix": "V06",
                                "rule": "a vehicle requests a resource only when no hold point it cannot pass (a closed "
                                        "or closing landing zone) lies before that resource"}}


def _batch_path(k, j, variant=None):
    pre = VARIANTS[variant]["prefix"] if variant else f"T{k:02d}"
    return os.path.join(PARTS, f"{pre}_b{j:04d}.csv.gz")


def run_batch(k: int, j: int, size: int, variant=None) -> dict:
    rng = np.random.default_rng([44, k, j])            # a variant re-uses its type's encounters, seed for seed
    specs = [ET.build(k, rng) for _ in range(size)]
    if variant == "6_request_rule":
        for sp in specs:
            sp.request_rule = True
    drive = [i for i, s in enumerate(specs) if s.params.get("drivable", True)]
    rows = []
    t0 = time.time()
    if drive:
        b = E.Batch([specs[i] for i in drive])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            oc, _ = E.run_batch(b, np.random.default_rng([4400, k, j]))
    peak = _peak_rss_mb()
    pos = {i: q for q, i in enumerate(drive)}
    for i, sp in enumerate(specs):
        r = {"type": k, "batch": j, "idx": i, "weight": sp.weight, "drivable": int(i in pos),
             "n_nominal": sum(p == 0 for p in sp.planner), "n_random": sum(p == 1 for p in sp.planner),
             "n_adversarial": sum(p == 2 for p in sp.planner), "n_vehicles": len(sp.paths),
             "params": json.dumps({a: (round(v, 4) if isinstance(v, float) else (bool(v) if isinstance(v, (bool, np.bool_)) else (int(v) if isinstance(v, (np.integer,)) else v)))
                                   for a, v in sp.params.items()}, sort_keys=True)}
        if i in pos:
            q = pos[i]
            for f in VIOL + NEAR + ("r1_breach", "no_safe"):
                r[f] = int(getattr(oc, f)[q] > 0)
            for f in ("min_sep", "min_gap_same", "min_crew", "delay_s", "t_end"):
                x = float(getattr(oc, f)[q])
                r[f] = round(x, 4) if math.isfinite(x) else None
            r["interventions"] = int(oc.interventions[q])
            r["proposals"] = int(oc.proposals[q])
            r["deadlock"] = int(oc.deadlock[q])
            r["blocked_by_fault"] = int(oc.blocked_by_fault[q])
            r["finished"] = int(oc.finished[q])
            r["steps"] = int(oc.steps[q])
        rows.append(r)
    df = pd.DataFrame(rows)
    os.makedirs(PARTS, exist_ok=True)
    tmp = _batch_path(k, j, variant) + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8", newline="\n") as f:
        df.to_csv(f, index=False, lineterminator="\n")
    os.replace(tmp, _batch_path(k, j, variant))
    return {"seconds": time.time() - t0, "peak_mb": peak or 0.0, "n": size}


def cmd_run(types, n_target, max_s, variant=None):
    t0 = time.time()
    log = os.path.join(PARTS, "timing.json")
    tim = json.load(open(log)) if os.path.isfile(log) else {}
    for k in types:
        size = BATCH[k]
        nb = math.ceil((n_target or N_TARGET[k]) / size)
        for j in range(nb):
            if os.path.isfile(_batch_path(k, j, variant)):
                continue
            tk = variant or str(k)                          # timing key (a variant keeps its own)
            est = tim.get(tk, tim.get(str(k), {})).get("seconds", 60.0)
            if time.time() - t0 + 1.3 * est > max_s:
                print(f"E44: time limit before T{k} batch {j}; rerun", flush=True)
                return False
            r = run_batch(k, j, size, variant)
            old = tim.get(tk, {})
            tim[tk] = {"seconds": round(r["seconds"], 2), "batch": size,
                           "seconds_total": round(old.get("seconds_total", 0.0) + r["seconds"], 1),
                           "batches_run": old.get("batches_run", 0) + 1,
                           "peak_rss_mb": round(max(old.get("peak_rss_mb", 0.0), r["peak_mb"]), 1)}
            os.makedirs(PARTS, exist_ok=True)
            json.dump(tim, open(log, "w"), indent=1)
            print(f"  E44 T{k} batch {j + 1}/{nb}: {r['seconds']:.1f} s, process peak {r['peak_mb']:.0f} MB", flush=True)
    print("E44: done")
    return True


def load_parts(types=None):
    fs = sorted(glob.glob(os.path.join(PARTS, "T*_b*.csv.gz")))
    parts = [pd.read_csv(f) for f in fs if types is None or int(os.path.basename(f)[1:3]) in types]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _cp_upper(x, n, alpha=0.05):
    from scipy.stats import beta
    return 1.0 if x >= n else float(beta.ppf(1 - alpha, x + 1, n - x))


def classify(df: pd.DataFrame) -> pd.Series:
    """Exactly one outcome per encounter, by precedence: not_driven > violation > blocked_by_fault > deadlock (only
    where no random fuzzer runs) > finished > incomplete (time limit, or quiet by design: a fuzzer idling, a robot told
    to stay stopped, vehicles held at a closed zone)."""
    viol = df[list(VIOL)].fillna(0).max(axis=1) > 0
    out = np.select([df["drivable"] == 0, viol, df["blocked_by_fault"].fillna(0) > 0,
                     (df["deadlock"].fillna(0) > 0) & (df["n_random"] == 0), df["finished"].fillna(0) > 0],
                    ["not_driven", "violation", "blocked_by_fault", "deadlock", "finished"], "incomplete")
    return pd.Series(out, index=df.index)


def planner_label(df: pd.DataFrame) -> pd.Series:
    n = df["n_vehicles"]
    return pd.Series(np.select([df["n_nominal"] == n, df["n_random"] == n, df["n_adversarial"] == n],
                               ["nominal", "random", "adversarial"], "mixed"), index=df.index)


NEAR_MISS_DEF = {"gap": "same-lane bumper gap below 2 x RSS d_min (speed-dependent, so not a fixed number of metres)",
                 "ttc_s": 10.0, "crew": "clearance below 2 x R_crew,stop (stopping distance + 10 m)",
                 "zone_exit_margin_s": 300.0}


def cmd_summarize():
    df = load_parts()
    if df.empty:
        raise SystemExit("no E44 parts")
    df["outcome"] = classify(df)
    df["planner"] = planner_label(df)
    df["min_margin_m"] = df[["min_sep", "min_crew"]].min(axis=1)
    df["near_miss"] = df[list(NEAR)].fillna(0).max(axis=1) > 0
    slim = df[["type", "batch", "idx", "planner", "weight", "outcome", "min_margin_m"]].copy()
    slim["weight"] = slim["weight"].round(6)
    slim["min_margin_m"] = slim["min_margin_m"].round(3)
    slim.to_csv(OUT_CSV, index=False, lineterminator="\n")
    P = df["params"].map(json.loads)
    for cols in PARAM_BINS.values():
        for c in cols:
            if c not in df:
                df[c] = [p.get(c) for p in P]
    df["loss_bin"] = [round(p["loss"], 1) if "loss" in p else None for p in P]
    tim = json.load(open(os.path.join(PARTS, "timing.json"))) if os.path.isfile(os.path.join(PARTS, "timing.json")) else {}
    nt = len(ET.BUILDERS)
    alpha_k = 0.05 / nt
    bounds = {"note": __doc__.split("\n\n")[1].strip(), "outcome_classes": list(OUTCOMES),
              "outcome_rule": " ".join(classify.__doc__.split()), "near_miss_margin_m": NEAR_MISS_DEF["gap"],
              "near_miss_definition": NEAR_MISS_DEF,
              "min_margin_m_definition": "smallest clearance to another vehicle (two-disc footprint) or crew member, m",
              "emergency_brake_definition": "share of encounters with at least one step where no candidate satisfied "
                                            "every rule and the shield applied full braking (an event, not an outcome)",
              "alpha_per_type": alpha_k, "types": {}}
    rows = []

    def _blk(d, k, tkey):
        dd = d[d["drivable"] == 1]
        nd = len(dd)
        w = dd["weight"].to_numpy(float)
        n_eff = float(w.sum() ** 2 / (w * w).sum()) if nd else 0.0
        x = int((dd["outcome"] == "violation").sum())
        sampled = bool(np.any(np.abs(w - 1) > 1e-12))
        counts = {c: int((d["outcome"] == c).sum()) for c in OUTCOMES}
        blk = {"title": E.TYPES[int(k)], "n": int(len(d)), "n_driven": nd, "n_eff": round(n_eff, 1),
               "violations": x, "violations_by_kind": {f: int(dd[f].sum()) for f in VIOL},
               "bound": (1 - 0.05 ** (1 / n_eff)) if x == 0 and n_eff > 0 else _cp_upper(x, nd),
               "bonferroni_bound": (1 - alpha_k ** (1 / n_eff)) if x == 0 and n_eff > 0 else _cp_upper(x, nd, alpha_k),
               "bound_rule": ("zero violations: 1 - 0.05^(1/n_eff)" if x == 0 else "Clopper-Pearson upper (unweighted)"),
               "near_misses": int(dd["near_miss"].sum()),
               "near_misses_by_kind": {f: int(dd[f].sum()) for f in NEAR},
               "min_margin_m": float(dd["min_margin_m"].min()) if nd else None,
               "min_margin_m_p01": float(dd["min_margin_m"].quantile(0.01)) if nd else None,
               "outcomes": counts, "outcomes_sum_equals_n": sum(counts.values()) == len(d),
               "emergency_brake_rate": float(dd["no_safe"].mean()) if nd else None,
               "intervention_rate": float(dd["interventions"].sum() / max(1, dd["proposals"].sum())),
               "r1_breach_rate": float(dd["r1_breach"].mean()) if nd else None,
               "delay_s_nominal_mean": float(dd[dd["planner"] == "nominal"]["delay_s"].mean()),
               "run_time_s": tim.get(tkey, {}).get("seconds_total"),
               "peak_rss_mb": tim.get(tkey, {}).get("peak_rss_mb")}
        if sampled:
            blk["weights"] = {"min": float(w.min()), "max": float(w.max()), "mean": float(w.mean())}
            blk["outcome_shares_weighted"] = {c: float(w[(dd["outcome"] == c).to_numpy()].sum() / w.sum())
                                              for c in OUTCOMES if c != "not_driven"}
        if x:
            ex = dd[dd["outcome"] == "violation"].head(20)
            blk["violating_examples"] = [{"batch": int(r.batch), "idx": int(r.idx), "params": json.loads(r.params),
                                          "kinds": [f for f in VIOL if r[f]]} for _, r in ex.iterrows()]
        return blk

    for k in sorted(df["type"].unique()):
        d = df[df["type"] == k]
        dd = d[d["drivable"] == 1]
        bounds["types"][int(k)] = _blk(d, k, str(int(k)))
        for keys, g in dd.groupby(PARAM_BINS[int(k)], dropna=False):
            keys = keys if isinstance(keys, tuple) else (keys,)
            rows.append({"type": int(k), "bin": "; ".join(f"{c}={v}" for c, v in zip(PARAM_BINS[int(k)], keys)),
                         "n_driven": len(g), **{c: int((g["outcome"] == c).sum()) for c in OUTCOMES[1:]},
                         "near_misses": int(g["near_miss"].sum()), "min_margin_m": g["min_margin_m"].min(),
                         "emergency_brake_rate": round(float(g["no_safe"].mean()), 5),
                         "intervention_rate": round(float(g["interventions"].sum() / max(1, g["proposals"].sum())), 4),
                         "delay_s_nominal": g[g["planner"] == "nominal"]["delay_s"].mean()})
    ts = bounds["types"]
    bounds["joint"] = {"types": len(ts), "max_bonferroni_bound": float(max(t["bonferroni_bound"] for t in ts.values())),
                       "equal_weight_mix_bonferroni_bound": float(np.mean([t["bonferroni_bound"] for t in ts.values()])),
                       "statement": "95 % jointly (Bonferroni over the 12 types): for each type, the per-encounter "
                                    "probability of a hard violation is below its bonferroni_bound, for that type's "
                                    "randomised parameter distribution (results/E44_bins.csv)"}
    dfile = os.path.join(ROOT, "results", "E44_defects.json")
    if os.path.isfile(dfile):                         # PREREG change 8: defects found in the first main run
        bounds["defects_found_in_main_run"] = json.load(open(dfile, encoding="utf-8"))["defects_found_in_main_run"]
    # exploratory variants (PREREG change 9): outside the twelve types and outside the Bonferroni family
    for name, vdef in VARIANTS.items():
        fs = sorted(glob.glob(os.path.join(PARTS, f"{vdef['prefix']}_b*.csv.gz")))
        if not fs:
            continue
        dv = pd.concat([pd.read_csv(f) for f in fs], ignore_index=True)
        dv["outcome"] = classify(dv)
        dv["planner"] = planner_label(dv)
        dv["min_margin_m"] = dv[["min_sep", "min_crew"]].min(axis=1)
        dv["near_miss"] = dv[list(NEAR)].fillna(0).max(axis=1) > 0
        vb = _blk(dv, vdef["type"], name)
        vb.pop("bonferroni_bound", None)
        vb["title"] = f"{E.TYPES[vdef['type']]} - variant"
        vb["rule"] = vdef["rule"]
        vb["bound_note"] = "uncorrected one-sided 95 % limit (exploratory, not in the Bonferroni family)"
        bounds.setdefault("variants", {})[name] = vb
    pd.DataFrame(rows).to_csv(OUT_BINS, index=False, lineterminator="\n")
    with open(OUT_BOUNDS, "w", encoding="utf-8", newline="\n") as f:
        json.dump(bounds, f, indent=1, default=float)
        f.write("\n")
    for k, t in ts.items():
        print(f"T{k:2d} n {t['n']:6d} n_eff {t['n_eff']:9.0f} viol {t['violations']:4d} bound {t['bound']:.2e} "
              f"bonf {t['bonferroni_bound']:.2e} {t['outcomes']}")


def _clean(x):
    if isinstance(x, float):
        return None if not math.isfinite(x) else round(x, 6)
    if isinstance(x, list):
        return [_clean(y) for y in x]
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    return x


def cmd_fixtures(max_steps=600):
    """20 replays: two per type for types 1-8 and 10, one each for 9, 11, 12 (nominal and adversarial planners)."""
    os.makedirs(FIX_DIR, exist_ok=True)
    plan = [(k, p) for k in (1, 2, 3, 4, 5, 6, 7, 8, 10) for p in (0, 2)] + [(9, 0), (11, 0)]
    index = []
    for q, (k, planner) in enumerate(plan):
        rng = np.random.default_rng([4499, k, planner])
        for _ in range(50):
            sp = ET.build(k, rng)
            if sp.params.get("drivable", True):
                break
        sp.planner = [planner] * len(sp.paths)
        b = E.Batch([sp])
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            oc, tr = E.run_batch(b, np.random.default_rng([4498, k, planner]), record=[0])
        steps = [{"t": st["t"], "move": st["move"], "a": st["a"], "modified": st["modified"], "s": st["s"],
                  "v": st["v"], "xy": st["xy"], "crew": st["crew"]} for st in tr[0][:max_steps]]
        doc = {"type": k, "title": E.TYPES[k], "planner": ["nominal", "random", "adversarial"][planner],
               "dt": E.DT, "vehicle": {"length": E.VEH_L, "width": E.VEH_W},
               "spec": {"paths": [np.asarray(p).round(4).tolist() for p in sp.paths], "v_class": sp.v_class,
                        "s0": sp.s0, "v0": sp.v0, "theta": sp.theta, "mu": sp.mu, "params": json.loads(json.dumps(sp.params, default=str)),
                        "zone": sp.zone, "crew": sp.crew, "occluders": sp.occluders},
               "constants": {k_: getattr(E.S, k_) for k_ in ("G_MOON", "RHO_S", "A_ACC", "B_MIN_FLAT", "B_MAX", "D0_M",
                                                             "STEEP_DEG", "STEEP_STOP_M", "R_CREW_SLOW_M",
                                                             "R_CREW_MARGIN_M", "V_CREW_MS", "MOVING_MS")},
               "steps": steps, "truncated": len(tr[0]) > max_steps}
        name = f"E44_fixture_{q:02d}_T{k:02d}_{doc['planner']}.json.gz"
        # fixed gzip timestamp (mtime=0): a regeneration with unchanged content is byte-identical
        with io.TextIOWrapper(gzip.GzipFile(os.path.join(FIX_DIR, name), "wb", mtime=0), encoding="utf-8") as f:
            json.dump(_clean(doc), f, separators=(",", ":"))
        index.append({"file": name, "type": k, "planner": doc["planner"], "steps": len(steps)})
    meta = {"note": "Replays for the site's encounter sandbox (F-54). Each step holds the safety_check inputs per "
                    "vehicle ('move', the Move fields of lunarsim/atc/safety.py) and its output acceleration 'a', "
                    "all stored to 6 decimals. Parity: a JS port of safety_check given 'move' must return 'a' within "
                    "1e-6 m/s2 per vehicle; one step of the kinematics of lunarsim/atc/encounter.py (no reversing, "
                    "0.1 s) from the stored 's', 'v' with the stored 'a' must give the next step's 's', 'v' within "
                    "1e-5. Infinite distances are stored as null.",
            "tolerance": {"a": 1e-6, "s": 1e-5, "v": 1e-5}, "fixtures": index}
    with open(os.path.join(FIX_DIR, "index.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=1)
        f.write("\n")
    print(f"fixtures: {len(index)} in {os.path.relpath(FIX_DIR, ROOT)}")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "summarize", "fixtures"])
    ap.add_argument("--types", default="1-12")
    ap.add_argument("--variant", default=None, choices=sorted(VARIANTS))
    ap.add_argument("--n", type=int, default=None, help="override the per-type targets (N_TARGET)")
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args(argv)
    faulthandler.dump_traceback_later(a.max_seconds + 120, exit=True)
    types = []
    for part in a.types.split(","):
        x, _, y = part.partition("-")
        types += list(range(int(x), int(y or x) + 1))
    if a.cmd == "run":
        if a.variant:
            cmd_run([VARIANTS[a.variant]["type"]], a.n, a.max_seconds, a.variant)
        else:
            cmd_run(types, a.n, a.max_seconds)
    elif a.cmd == "summarize":
        cmd_summarize()
    else:
        cmd_fixtures()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
