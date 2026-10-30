"""E46 (B-76 REVISED + PREREG change 7): the market for P3, H5.

    python tools/atc/run_e46.py design                      # -> data/scenarios/E46-design.json (before any row)
    python tools/atc/run_e46.py calibrate [--max-seconds]   # the posted price, from calibration seeds 101-110
    python tools/atc/run_e46.py run [--max-seconds 480]     # physical runs -> results/E46_parts/ (resumable)
    python tools/atc/run_e46.py analyse                     # -> results/E46_cells.csv, E46_pairs.csv, E46_fit.json

Physical runs per split and seed: the pooled market (C_AUCTION, every owner truthful), twelve deviations (one owner
scales its asks by k in {0.8, 0.9, 1.1, 1.25}), the three two-owner coalitions (only their vehicles and cargo, pooled),
owners alone (A_MOON: each owner's own fleet, decided on the Moon) and the marketplace benchmark (O_ORACLE). Payments
are computed afterwards from each run's job log, so first price, per-item second price, posted price with Shapley
sharing and no payment are compared on the same allocation; only the deviations change the allocation.

Money (USD a year): a carrier's true cost of a job is the engine's variable cost (lunarsim.engine job_cost_usd: wear
share + operator time) times its owner's private-cost multiplier; a shipper's cost is its cargo's value of delivery
time (Scenario.vot_usd_per_h by priority) times the completion time (censored at the horizon for undelivered items).
An owner's profit = payments received as carrier - true carrier costs - tariffs paid as shipper - delay cost of its
cargo. Shippers pay the posted tariff per tonne-km under every paying rule; carriers are paid their ask (first
price), the lowest competing ask for the same job (per-item second price; the posted tariff as reserve when nobody
else could carry it) or the posted tariff (posted price); the operator's budget is tariffs in minus payouts. Posted
price with Shapley sharing gives each owner its Shapley value of the coalition game v(S) = -(delay costs + true
carrier costs) of S's members in S's own run. Audits: Earth audits a random share q of jobs afterwards; an ask that
differs from the true cost is fined m x the difference.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import itertools
import json
import math
import os
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "experiments", "phase5")):
    if p not in sys.path:
        sys.path.insert(0, p)

DESIGN = os.path.join(ROOT, "data", "scenarios", "E46-design.json")
PARTS = os.path.join(ROOT, "results", "E46_parts")
OWNERS = ("A", "B", "C")

DESIGN_DOC = {
    "experiment": "E46 (B-76 REVISED with PREREG change 7), P3, H5",
    "H5": "first-price asks let at least one owner gain by shading; per-item second price reduces that gain; posted "
          "price with Shapley sharing leaves no owner worse off than working alone (decision rules: PREREG change 7)",
    "owners": list(OWNERS), "splits": {"3eq": "equal cargo shares", "3uneq": "50/35/15 cargo shares"},
    "fleet": "the p5 owner mix (A: CLV-1 + FLEX; B: Pegasus + Eagle; C: two HL-MAPP + two MoonFall), 30 % load, "
             "team-lift share 0.10, one year",
    "rules": ["none", "first", "second", "posted"],
    "rule_definitions": {
        "none": "cooperative: no payments",
        "first": "carriers are paid their ask; shippers pay the posted tariff per tonne-km",
        "second": "carriers are paid the lowest competing ask for the same job (team jobs: the two lowest competing "
                  "asks); the posted tariff is the reserve when no other free robot could carry it; shippers pay the "
                  "posted tariff",
        "posted": "carriers are paid the posted tariff per tonne-km, shippers pay it; the coalition's value is then "
                  "shared by Shapley values (budget-neutral transfers)"},
    "k_levels": [0.8, 0.9, 1.1, 1.25], "k_note": "one owner at a time scales its asks by k (the others truthful); "
                                                 "under first and second price; posted price has no ask",
    "q_levels": [0.0, 0.05, 0.20], "audit_penalty_multiple": {"value": 3.0, "flag": "Assumed", "range": [2.0, 5.0]},
    "seeds": list(range(1, 31)), "calibration_seeds": list(range(101, 111)),
    "message_loss": {"value": 0.0, "flag": "design choice: perfect radio, so paired differences show incentives, not "
                                           "message-loss noise (P1 covers loss)"},
    "private_costs": {
        "true_cost": "the engine's job_cost_usd (wear share 0.5 of unit cost per life hour + operator demand x "
                     "operator_cost_per_h 1,000 USD/h) times the owner's multiplier eps_o",
        "eps_distribution": "lognormal: eps_o = exp(N(0, sigma)), one draw per owner per seed (rng seeded by (46, "
                            "seed)), the same in every run of that seed",
        "sigma": {"value": 0.2, "flag": "Assumed", "sweep_range": [0.1, 0.3],
                  "sweep_note": "declared range; the main run uses 0.2 (a sigma sweep needs new physical runs and is "
                                "not part of E46)"},
        "in_the_auction": "an owner's bid = the marketplace bid + (eps_o x k_o - 1) x the carrier-cost part of it "
                          "(dispatch._bid): the ask scales the cost the carrier names, not the shippers' value of time"},
    "shipper_value": {"what": "value of delivery time by priority, Scenario.vot_usd_per_h (1: 5,000, 2: 1,000, "
                              "3: 100 USD/h) x completion time; undelivered items censored at the horizon",
                      "flag": "Spec of the scenario (R-1 economics)"},
    "posted_price": {"how_earth_sets_it": "cost recovery: Earth sets the tariff per tonne-km to the mean true carrier "
                                          "cost per tonne-km of the pooled market in the calibration seeds 101-110 "
                                          "(not the test seeds), per split, published before the year",
                     "markup": 0.0, "flag": "Assumed (rule)", "values_usd_per_tkm": None},
    "coalitions": "all non-empty subsets of {A, B, C}: singletons from the owners-alone run (A_MOON), pairs from "
                  "pair-only runs (their vehicles and cargo, pooled C_AUCTION), the grand coalition from the pooled "
                  "market",
    "benchmark": "O_ORACLE (the marketplace with full information) for the efficiency loss",
    "outputs": ["results/E46_cells.csv", "results/E46_pairs.csv", "results/E46_fit.json", "results/E46_parts/"],
}


def cmd_design():
    doc = dict(DESIGN_DOC)
    if os.path.isfile(DESIGN):
        old = json.load(open(DESIGN, encoding="utf-8"))
        doc["posted_price"] = dict(doc["posted_price"], values_usd_per_tkm=old.get("posted_price", {}).get("values_usd_per_tkm"))
    os.makedirs(os.path.dirname(DESIGN), exist_ok=True)
    with open(DESIGN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print("design:", os.path.relpath(DESIGN, ROOT))


def eps_of(seed: int) -> dict:
    rng = np.random.default_rng([46, int(seed)])
    s = DESIGN_DOC["private_costs"]["sigma"]["value"]
    return {o: float(math.exp(rng.normal(0.0, s))) for o in OWNERS}


def scenario(split: str, members=None):
    import run_phase5 as R
    from lunarsim.atc import p5 as P5
    sc = P5.build(split, k=R.E43_K30, team_lift_share=0.10)
    if members is not None:     # cargo of non-members is dropped at its READY / BULK event (run_one), so the demand
        sc = sc.with_(fleet=[f for f in sc.fleet if f[0] in members])   # stream draws exactly as in the full runs
    return sc.with_(p5=dict(sc.p5, dispatch_fixpoint=True))


def run_one(split: str, seed: int, kind: str, owner=None, k: float = 1.0, members=None) -> dict:
    """One physical run with its job log. kind: pooled | dev | pair | alone | oracle."""
    import run_phase5 as R
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    from lunarsim.engine import WEAR_SHARE
    eps = eps_of(seed)
    sc = scenario(split, members)
    if kind in ("pooled", "dev", "pair"):
        mult = {o: eps[o] * (k if o == owner else 1.0) for o in OWNERS}
        mech, kw = G.mechanism("C_AUCTION"), {"loss": float(DESIGN_DOC["message_loss"]["value"]), "bid_mult": mult}
    elif kind == "alone":
        mech, kw = G.mechanism("A_MOON"), dict(R.A_KW)
    else:
        mech, kw = G.mechanism("O_ORACLE"), {}
    kw["start_year"] = 2028
    free_now = {"t": -1.0, "free": []}

    def wrapped(sim, waiting, free, **kws):
        free_now["t"], free_now["free"] = sim.t, list(free)
        return mech(sim, waiting, free, **kws)
    for a in ("anticipates", "supports_team", "regime", "__name__"):
        if hasattr(mech, a):
            setattr(wrapped, a, getattr(mech, a))
    sim = Simulation(sc, wrapped, seed=seed, mech_kwargs=kw)
    world = sim.world
    if members is not None:                       # coalition runs: the other owners' cargo never exists
        real_push = sim._push

        def push(t, kind_, payload, _rp=real_push):
            if kind_ in ("READY", "BULK") and getattr(payload, "owner", None) not in members:
                for lst in (sim.pending, sim.all_cargo):
                    if payload in lst:
                        lst.remove(payload)
                return
            return _rp(t, kind_, payload)
        sim._push = push
    rate = lambda v: (WEAR_SHARE * v.cls.unit_cost_musd * 1e6 / v.cls.life_hours
                      + sim.operator_demand(v) * sim.sc.operator_cost_per_h)
    jobs = []
    real_start = sim._start_job

    def start(job, _rs=real_start):
        rev0 = {v.id: v.revenue_musd for v in job.vehicles}
        n0 = len(sim.waiting)
        _rs(job)
        if len(sim.waiting) >= n0 and not any(v.revenue_musd != rev0[v.id] for v in job.vehicles):
            return
        price = sum(v.revenue_musd - rev0[v.id] for v in job.vehicles) * 1e6
        items = job.items + job.backhaul
        mass = sum(c.mass_kg for c in job.items)
        org = job.items[0].origin if job.items else (job.vehicles[0].location)
        route = [org] + list(job.route)
        loaded = sum(world.distance_km(a, b) for a, b in zip(route[:-1], route[1:]) if a != b)
        team = len(job.vehicles) > 1
        alts = []
        if items and free_now["t"] == sim.t:
            for u in free_now["free"]:
                if u in job.vehicles or u.busy_until > sim.t + 1e-9 or not u.alive:
                    continue
                need = mass / 2.0 if team else mass
                if u.cls.capacity_kg + 1e-9 < need or any(c.standard not in u.standards for c in job.items):
                    continue
                if team and not getattr(u.cls, "can_team_lift", False):
                    continue
                emp = world.distance_km(u.location, org) if u.location != org else 0.0
                hours = (emp / (u.cls.speed_kmh * u.cls.empty_speed_mult) + loaded / u.cls.speed_kmh
                         + u.cls.load_h + u.cls.unload_h * max(1, len(set(job.route))))
                alts.append([u.owner, round(rate(u) * hours, 2)])
        jobs.append({"t": round(sim.t, 4), "t_end": round(max(v.busy_until for v in job.vehicles), 4),
                     "carriers": [v.owner for v in job.vehicles], "cost": round(price, 2), "team": team,
                     "items": [[c.owner, round(c.mass_kg, 2),
                                round(c.mass_kg / 1000.0 * (world.distance_km(c.origin, c.dest) if c.origin != c.dest
                                                           else 0.0), 5)] for c in items],
                     "alts": alts})
    sim._start_job = start
    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        s = sim.run()
    H = sc.horizon_h
    vot = sim.sc.vot_usd_per_h
    own = {o: {"delay_usd": 0.0, "delay_h": 0.0, "items": 0, "delivered": 0, "delivered_kg": 0.0} for o in OWNERS}
    for c in sim.all_cargo:
        if c.t_ready > H or c.owner not in own or (members is not None and c.owner not in members):
            continue
        end = c.t_delivered if c.t_delivered is not None and c.t_delivered <= H else H
        d = max(0.0, end - c.t_ready)
        own[c.owner]["delay_usd"] += vot.get(c.priority, 100.0) * d
        own[c.owner]["delay_h"] += d
        own[c.owner]["items"] += 1
        if c.t_delivered is not None and c.t_delivered <= H:
            own[c.owner]["delivered"] += 1
            own[c.owner]["delivered_kg"] += c.mass_kg
    return {"split": split, "seed": seed, "kind": kind, "owner": owner, "k": k,
            "members": list(members) if members is not None else list(OWNERS), "eps": eps,
            "run_s": round(time.time() - t0, 2), "horizon_h": H, "owners": own, "jobs": jobs,
            "delivered_share": float(s.get("delivered_share", float("nan")))}


def plan(seeds=None):
    out = []
    for split in DESIGN_DOC["splits"]:
        for seed in (seeds or DESIGN_DOC["seeds"]):
            out.append((split, seed, "pooled", None, 1.0, None))
            for o in OWNERS:
                for k in DESIGN_DOC["k_levels"]:
                    out.append((split, seed, "dev", o, k, None))
            for pair in itertools.combinations(OWNERS, 2):
                out.append((split, seed, "pair", None, 1.0, pair))
            out.append((split, seed, "alone", None, 1.0, None))
            out.append((split, seed, "oracle", None, 1.0, None))
    return out


def _name(split, seed, kind, owner, k, members):
    tag = {"pooled": "pooled", "dev": f"dev_{owner}_{k:g}", "pair": "pair_" + "".join(members or ()),
           "alone": "alone", "oracle": "oracle"}[kind]
    return os.path.join(PARTS, f"{split}_s{seed:03d}_{tag}.json.gz")


def _write(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(tmp, path)


def cmd_run(max_s, seeds=None):
    t0 = time.time()
    est = 15.0
    n_new = 0
    for item in plan(seeds):
        path = _name(*item)
        if os.path.isfile(path):
            continue
        if time.time() - t0 + 2.0 * est > max_s:
            print(f"E46: time limit after {n_new} new runs; rerun", flush=True)
            return False
        r = run_one(*item)
        _write(path, r)
        est = max(est * 0.5, r["run_s"]) if n_new else r["run_s"]
        n_new += 1
    print(f"E46: done ({n_new} new runs)")
    return True


def cmd_calibrate(max_s):
    """Posted tariff per tonne-km = mean true carrier cost per tonne-km of the pooled market, calibration seeds."""
    t0 = time.time()
    cal = os.path.join(ROOT, ".cache", "atc", "e46_calibration")
    os.makedirs(cal, exist_ok=True)
    for split in DESIGN_DOC["splits"]:
        for seed in DESIGN_DOC["calibration_seeds"]:
            p = os.path.join(cal, f"{split}_s{seed}.json.gz")
            if os.path.isfile(p):
                continue
            if time.time() - t0 > max_s - 60:
                print("calibrate: time limit; rerun")
                return
            _write(p, run_one(split, seed, "pooled"))
    vals = {}
    for split in DESIGN_DOC["splits"]:
        cost = tkm = 0.0
        for seed in DESIGN_DOC["calibration_seeds"]:
            r = json.load(gzip.open(os.path.join(cal, f"{split}_s{seed}.json.gz"), "rt"))
            for j in r["jobs"]:
                cost += j["cost"] / len(j["carriers"]) * sum(r["eps"][o] for o in j["carriers"])
                tkm += sum(it[2] for it in j["items"])
        vals[split] = round(cost / tkm, 2)
    doc = json.load(open(DESIGN, encoding="utf-8"))
    doc["posted_price"]["values_usd_per_tkm"] = vals
    with open(DESIGN, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, indent=1)
        f.write("\n")
    print("posted tariff (USD per tonne-km):", vals)


# ------------------------------------------------------------------------------------------------ analysis
def _boot(x, n=20000, seed=46):
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return {"mean": None, "lo": None, "hi": None, "n": 0}
    rng = np.random.default_rng(seed)
    m = rng.choice(x, (n, len(x))).mean(1)
    return {"mean": float(x.mean()), "lo": float(np.quantile(m, 0.025)), "hi": float(np.quantile(m, 0.975)),
            "n": int(len(x))}


def money(run: dict, rule: str, tariff: float, dev_owner=None, k: float = 1.0, q: float = 0.0, m: float = 3.0) -> dict:
    """Per-owner cash and profit for one run under one payment rule (asks scaled by k for dev_owner)."""
    eps = run["eps"]
    kk = {o: (k if o == dev_owner else 1.0) for o in OWNERS}
    recv = {o: 0.0 for o in OWNERS}
    cost = {o: 0.0 for o in OWNERS}
    paid = {o: 0.0 for o in OWNERS}
    fines = {o: 0.0 for o in OWNERS}
    open_end = 0.0
    H = run["horizon_h"]
    sp = {"jobs": 0, "with_alternative": 0, "reserve": 0, "floor_at_ask": 0}   # second price, as implemented
    for j in run["jobs"]:
        n = len(j["carriers"])
        share = j["cost"] / n
        tkm = sum(it[2] for it in j["items"])
        asks = [share * eps[o] * kk[o] for o in j["carriers"]]
        if rule == "first":
            pay = asks
        elif rule == "second":
            alt = sorted(c * eps[o] * kk[o] for o, c in j["alts"])
            need = 2 if j["team"] else 1
            total = sum(alt[:need]) if len(alt) >= need else tariff * tkm
            pay = [max(a, total / n) for a in asks]
            sp["jobs"] += 1
            sp["with_alternative"] += len(alt) >= 1
            sp["reserve"] += len(alt) < need
            sp["floor_at_ask"] += all(a >= total / n for a in asks)
        elif rule == "posted":
            pay = [tariff * tkm / n] * n
        else:
            pay = [0.0] * n
        for o, a, p in zip(j["carriers"], asks, pay):
            recv[o] += p
            cost[o] += share * eps[o]
            if rule in ("first", "second") and q > 0:
                fines[o] += q * m * abs(a - share * eps[o])
            if j["t_end"] > H:
                open_end += p
        if rule != "none":
            for it in j["items"]:
                paid[it[0]] += tariff * it[2]
    out = {}
    for o in OWNERS:
        d = run["owners"][o]["delay_usd"] if o in run["members"] else 0.0
        out[o] = recv[o] - cost[o] - paid[o] - d - fines[o]
    cash = {o: recv[o] - paid[o] - fines[o] for o in OWNERS}
    return {"profit": out, "budget": sum(paid.values()) - sum(recv.values()) + sum(fines.values()),
            "settled_earth": sum(abs(v) for v in cash.values()) / 2.0, "open_end": open_end,
            "system_cost": sum(cost.values()) + sum(run["owners"][o]["delay_usd"] for o in run["members"]),
            "delay_h": sum(run["owners"][o]["delay_h"] for o in run["members"]),
            "delivered": sum(run["owners"][o]["delivered"] for o in run["members"]), "fines": fines,
            "true_cost": cost, "receipts": sum(paid.values()), "payouts": sum(recv.values()),
            "fines_total": sum(fines.values()), "cash": cash, "second_price_jobs": sp}


def coalition_value(run: dict, members) -> float:
    eps = run["eps"]
    c = 0.0
    for j in run["jobs"]:
        c += j["cost"] / len(j["carriers"]) * sum(eps[o] for o in j["carriers"])
    return -(c + sum(run["owners"][o]["delay_usd"] for o in members))


def owner_value(run: dict, o: str) -> float:
    """An owner's value in a run where it works alone (A_MOON): -(its carrier costs + its cargo's delay cost)."""
    eps = run["eps"]
    c = sum(j["cost"] / len(j["carriers"]) * eps[o] for j in run["jobs"] for x in j["carriers"] if x == o)
    return -(c + run["owners"][o]["delay_usd"])


def shapley(v: dict, players) -> dict:
    players = list(players)
    n = len(players)
    phi = {p: 0.0 for p in players}
    for p in players:
        others = [x for x in players if x != p]
        for r in range(len(others) + 1):
            for S in itertools.combinations(others, r):
                w = math.factorial(len(S)) * math.factorial(n - len(S) - 1) / math.factorial(n)
                phi[p] += w * (v[frozenset(S) | {p}] - v[frozenset(S)])
    return phi


def cmd_analyse():
    import pandas as pd
    design = json.load(open(DESIGN, encoding="utf-8"))
    tariffs = design["posted_price"]["values_usd_per_tkm"]
    mpen = design["audit_penalty_multiple"]["value"]
    runs = {}
    run_s = []
    for f in sorted(glob.glob(os.path.join(PARTS, "*.json.gz"))):
        r = json.load(gzip.open(f, "rt"))
        tag = os.path.basename(f).split("_", 2)[2].replace(".json.gz", "")
        runs[(r["split"], r["seed"], tag)] = r
        run_s.append(r["run_s"])
    cells, pairs = [], []
    fit = {"n_rows": len(runs), "run_s_mean": round(float(np.mean(run_s)), 2) if run_s else None,
           "cpu_h": round(sum(run_s) / 3600.0, 3), "design": {k: design[k] for k in ("owners", "splits", "rules", "k_levels",
                                                                                   "q_levels", "seeds")},
           "tariff_usd_per_tkm": tariffs, "audit_penalty_multiple": mpen, "H5": {}, "max_gain": {}, "audits": {},
           "short_cells": [], "exploratory": {"note": "made after the runs, not pre-registered (LEAD, B-76 Q1)", "allocation_fixed_gain": {}, "reallocation_term": {}}}
    for split in design["splits"]:
        seeds = sorted({s for (sp, s, t) in runs if sp == split and t == "pooled"})
        T = tariffs[split]
        base = {s: runs[(split, s, "pooled")] for s in seeds}
        orc = {s: runs.get((split, s, "oracle")) for s in seeds}
        alone = {s: runs.get((split, s, "alone")) for s in seeds}
        alone_v = {s: {o: owner_value(alone[s], o) for o in OWNERS} for s in seeds if alone[s]}

        def cell_row(label, rule, k, q, dev_owner, per_seed):
            prof = {o: [x["profit"][o] for x in per_seed] for o in OWNERS}
            eff = [100.0 * (x["system_cost"] - x["oracle_cost"]) / abs(x["oracle_cost"]) for x in per_seed
                   if x.get("oracle_cost")]
            irv = sum(1 for o in OWNERS if prof[o] and alone_v and
                      np.mean(prof[o]) < np.mean([alone_v[s][o] for s in alone_v]))
            row = {"label": label, "rule": rule, "split": split, "k": k, "q": q, "owner": dev_owner or "",
                   "n": len(per_seed), **{f"profit_{o}_musd": round(float(np.mean(prof[o])) / 1e6, 4) for o in OWNERS},
                   "operator_budget_musd": round(float(np.mean([x["budget"] for x in per_seed])) / 1e6, 4),
                   "efficiency_loss_pct": round(float(np.mean(eff)), 3) if eff else None,
                   "settled_earth_musd": round(float(np.mean([x["settled_earth"] for x in per_seed])) / 1e6, 4),
                   "open_end_musd": round(float(np.mean([x["open_end"] for x in per_seed])) / 1e6, 5),
                   "ir_violations": irv}
            if len(per_seed) < len(design["seeds"]):
                fit["short_cells"].append({"label": label, "have": len(per_seed), "n": len(design["seeds"])})
            cells.append(row)

        truth = {}
        for rule in design["rules"]:
            per = []
            for s in seeds:
                x = money(base[s], rule, T)
                x["oracle_cost"] = money(orc[s], "none", T)["system_cost"] if orc[s] else None
                per.append(x)
            truth[rule] = {s: x for s, x in zip(seeds, per)}
            if rule == "posted":                   # Shapley sharing of the grand coalition's value
                for s, x in zip(seeds, per):
                    v = {frozenset(): 0.0}
                    if s not in alone_v:
                        continue
                    for o in OWNERS:
                        v[frozenset([o])] = alone_v[s][o]
                    ok = True
                    for pr in itertools.combinations(OWNERS, 2):
                        pr_run = runs.get((split, s, "pair_" + "".join(pr)))
                        if pr_run is None:
                            ok = False
                            break
                        v[frozenset(pr)] = coalition_value(pr_run, pr)
                    if not ok:
                        continue
                    v[frozenset(OWNERS)] = coalition_value(base[s], OWNERS)
                    phi = shapley(v, OWNERS)
                    x["cash_profit"] = dict(x["profit"])    # money() before the Shapley payoff replaces it
                    x["profit"] = phi
                    x["v"] = v
            cell_row(f"{rule} {split} truthful", rule, 1.0, 0.0, None, per)
        # P3 referee round 1 (LEAD, 30 Oct): budget with honest asks, Shapley transfers, the second price as
        # implemented, and every rule against no payments (USD a year; bootstrap over seeds, 20,000 resamples)
        bud = fit.setdefault("budget", {})
        for rule in design["rules"]:
            b = _boot([truth[rule][s]["budget"] for s in seeds])
            bud.setdefault(rule, {})[split] = {"mean": b["mean"], "lo": b["lo"], "hi": b["hi"], "n": b["n"],
                "receipts_mean": float(np.mean([truth[rule][s]["receipts"] for s in seeds])),
                "payouts_mean": float(np.mean([truth[rule][s]["payouts"] for s in seeds])),
                "fines_mean": float(np.mean([truth[rule][s]["fines_total"] for s in seeds]))}
        sh = [s for s in seeds if "cash_profit" in truth["posted"][s]]
        tr = fit.setdefault("transfers", {}).setdefault(split, {})
        for o in OWNERS:
            b = _boot([truth["posted"][s]["profit"][o] - truth["posted"][s]["cash_profit"][o] for s in sh])
            tr[o] = {"mean": b["mean"], "lo": b["lo"], "hi": b["hi"], "n": b["n"]}
        st = []
        for s in sh:
            x = truth["posted"][s]
            net = {o: x["cash"][o] + x["profit"][o] - x["cash_profit"][o] for o in OWNERS}
            st.append(sum(abs(v) for v in net.values()) / 2.0)
        b = _boot(st)
        fit.setdefault("settled_with_transfers", {})[split] = {"mean": b["mean"], "lo": b["lo"], "hi": b["hi"],
                                                               "n": b["n"]}
        tot = {k: sum(truth["second"][s]["second_price_jobs"][k] for s in seeds) for k in
               ("jobs", "with_alternative", "reserve", "floor_at_ask")}
        fit.setdefault("second_price", {})[split] = {
            "jobs": tot["jobs"], "with_alternative_share": tot["with_alternative"] / tot["jobs"],
            "reserve_share": tot["reserve"] / tot["jobs"], "floor_at_ask_share": tot["floor_at_ask"] / tot["jobs"],
            "note": "honest asks, all seeds pooled; with_alternative: at least one other free robot could carry the "
                    "job; reserve: fewer alternatives than carriers needed, so total = tariff x tkm; floor_at_ask: "
                    "every carrier of the job is paid its own ask (max(ask, total / n) = ask)"}
        vn = fit.setdefault("vs_none", {})
        for rule in ("first", "second", "posted"):
            vn.setdefault(rule, {})[split] = {}
            for o in OWNERS:
                ss = sh if rule == "posted" else seeds
                b = _boot([truth[rule][s]["profit"][o] - truth["none"][s]["profit"][o] for s in ss])
                vn[rule][split][o] = {"mean": b["mean"], "lo": b["lo"], "hi": b["hi"], "n": b["n"]}
        # rule - rule on delay and delivered (truthful: the same allocation, so identical by construction)
        for r1, r2 in (("second", "first"), ("posted", "first"), ("posted", "second")):
            for met in ("delay_h", "delivered"):
                d = [truth[r1][s][met] - truth[r2][s][met] for s in seeds]
                b = _boot(d)
                pairs.append({"comparison": f"{r1} - {r2} ({split}, truthful)", "metric": met, "n": b["n"],
                              "mean": b["mean"], "lo": b["lo"], "hi": b["hi"],
                              "b_mean": float(np.mean([truth[r2][s][met] for s in seeds])), "share_of_b": 0.0})
        # coalition - alone (posted price with Shapley sharing), every owner in every coalition
        cl3 = []
        for coal in [c for r in (2, 3) for c in itertools.combinations(OWNERS, r)]:
            for o in coal:
                d = []
                for s in seeds:
                    x = truth["posted"][s]
                    if "v" not in x:
                        continue
                    v = x["v"]
                    sub = {frozenset(S): v[frozenset(S)] for r in range(len(coal) + 1) for S in itertools.combinations(coal, r)}
                    d.append(shapley(sub, coal)[o] - v[frozenset([o])])
                b = _boot(d)
                alone_mean = float(np.mean([alone_v[s][o] for s in alone_v])) if alone_v else None
                pairs.append({"comparison": f"coalition {''.join(coal)} - alone, owner {o} ({split})",
                              "metric": "profit_usd", "n": b["n"], "mean": b["mean"], "lo": b["lo"], "hi": b["hi"],
                              "b_mean": alone_mean, "share_of_b": (b["mean"] / abs(alone_mean)) if b["mean"] is not None
                              and alone_mean else None})
                cl3.append({"coalition": "".join(coal), "owner": o, **b})
        # deviations: gain over truthful per rule, k, owner; audits
        gains = {}
        for rule in ("first", "second"):
            for o in OWNERS:
                for k in design["k_levels"]:
                    tag = f"dev_{o}_{k:g}"
                    for q in design["q_levels"]:
                        per, g, sysd, sysh, ss = [], [], [], [], []
                        for s in seeds:
                            rr = runs.get((split, s, tag))
                            if rr is None:
                                continue
                            x = money(rr, rule, T, dev_owner=o, k=k, q=q, m=mpen)
                            x["oracle_cost"] = money(orc[s], "none", T)["system_cost"] if orc[s] else None
                            per.append(x)
                            ss.append(s)
                            g.append(x["profit"][o] - truth[rule][s]["profit"][o])
                            sysd.append(x["system_cost"] - truth[rule][s]["system_cost"])
                            sysh.append(x["delay_h"] - truth[rule][s]["delay_h"])
                        if not per:
                            continue
                        cell_row(f"{rule} {split} owner {o} k={k:g} q={q:g}", rule, k, q, o, per)
                        b = _boot(g)
                        pairs.append({"comparison": f"gain {rule} owner {o} k={k:g} q={q:g} ({split})",
                                      "metric": "profit_usd", "n": b["n"], "mean": b["mean"], "lo": b["lo"],
                                      "hi": b["hi"], "b_mean": float(np.mean([truth[rule][s]["profit"][o] for s in seeds])),
                                      "share_of_b": None})
                        gains[(rule, o, k, q)] = {"gain": g, "sys": sysd, "sysh": sysh, "seeds": ss}
        # H5 clauses (q = 0)
        best = {}
        for rule in ("first", "second"):
            cand = [(np.mean(v["gain"]), key) for key, v in gains.items() if key[0] == rule and key[3] == 0.0 and v["gain"]]
            if not cand:
                continue
            mg, key = max(cand)
            b = _boot(gains[key]["gain"])
            bs = _boot(gains[key]["sys"])
            bh = _boot(gains[key]["sysh"])
            best[rule] = key
            fit["max_gain"].setdefault(rule, {})[split] = {"owner": key[1], "k": key[2], "gain": b["mean"], "lo": b["lo"],
                                                           "hi": b["hi"], "system_cost_usd": bs["mean"],
                                                           "system_cost_h": bh["mean"], "lo_cost": bh["lo"],
                                                           "hi_cost": bh["hi"]}
            fit["audits"].setdefault(rule, {})[split] = {}
            for q in design["q_levels"]:
                gq = gains.get((rule, key[1], key[2], q))
                if gq is None:
                    continue
                g0 = float(np.mean(gains[key]["gain"]))
                gq_m = float(np.mean(gq["gain"]))
                fit["audits"][rule][split][f"{q * 100:g}"] = {"recovered_share": (g0 - gq_m) / g0 if g0 > 0 else None,
                                                              "net_gain": gq_m}
        # H5 by PREREG change 7 (USD a year; P3's build recomputes the verdicts from these intervals)
        c1 = fit["max_gain"].get("first", {}).get(split)
        h5 = {"clause1": {"tested": c1 is not None, "supported": bool(c1 and c1["lo"] > 0),
                          "gain": c1["gain"] if c1 else None, "lo": c1["lo"] if c1 else None,
                          "hi": c1["hi"] if c1 else None, "owner": c1["owner"] if c1 else None,
                          "k": c1["k"] if c1 else None,
                          "rule": "largest gain over truthful across the tested k under first price; supported iff "
                                  "lo > 0"}}
        h5["clause2"] = {"tested": False, "supported": False, "diff_mean": None, "diff_lo": None, "diff_hi": None}
        if "first" in best and "second" in best:
            f_by = dict(zip(gains[best["first"]]["seeds"], gains[best["first"]]["gain"]))
            s_by = dict(zip(gains[best["second"]]["seeds"], gains[best["second"]]["gain"]))
            both = sorted(set(f_by) & set(s_by))
            bd = _boot([s_by[s] - f_by[s] for s in both])
            h5["clause2"] = {"tested": bd["n"] > 0,
                             "supported": bool(bd["n"] > 0 and bd["mean"] < 0 and bd["hi"] < 0),
                             "diff_mean": bd["mean"], "diff_lo": bd["lo"], "diff_hi": bd["hi"], "n": bd["n"],
                             "rule": "paired by seed: second-price largest gain minus first-price largest gain; "
                                     "supported iff diff_mean < 0 and diff_hi < 0"}
        ups = [c["hi"] for c in cl3 if c["hi"] is not None]
        los = [c["lo"] for c in cl3 if c["lo"] is not None]
        h5["clause3"] = {"tested": bool(ups), "supported": bool(ups) and min(ups) >= 0,
                         "min_upper": min(ups) if ups else None, "min_lower": min(los) if los else None,
                         "rule": "over every owner in every tested coalition, (Shapley payoff in the coalition - "
                                 "profit alone); supported iff the smallest upper bound >= 0", "rows": cl3}
        fit["H5"][split] = h5
        # post hoc (not pre-registered): the largest cell's gain with the allocation held fixed (the truthful run
        # re-priced with the scaled asks), and the rest of the paired gain (the deviator's own-delay term)
        ex = fit["exploratory"]
        for rule in ("first", "second"):
            if rule not in best:
                continue
            _, o, k, _ = best[rule]
            fixed = {s: money(base[s], rule, T, dev_owner=o, k=k)["profit"][o] - truth[rule][s]["profit"][o]
                     for s in seeds}
            b = _boot(list(fixed.values()))
            ex["allocation_fixed_gain"].setdefault(rule, {})[split] = {"gain": b["mean"], "lo": b["lo"], "hi": b["hi"],
                                                                       "n": b["n"], "owner": o, "k": k}
            if rule == "first":
                g = dict(zip(gains[best[rule]]["seeds"], gains[best[rule]]["gain"]))
                term = np.array([g[s] - fixed[s] for s in seeds if s in g])
                ex["reallocation_term"][split] = {"mean": float(term.mean()), "sd": float(term.std(ddof=1)),
                                                  "n": int(len(term)), "owner": o, "k": k}
    fit["n_cells"] = len(cells)
    pd.DataFrame(cells).to_csv(os.path.join(ROOT, "results", "E46_cells.csv"), index=False, lineterminator="\n")
    pd.DataFrame(pairs).to_csv(os.path.join(ROOT, "results", "E46_pairs.csv"), index=False, lineterminator="\n")
    with open(os.path.join(ROOT, "results", "E46_fit.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(fit, f, indent=1, default=float)
        f.write("\n")
    print(json.dumps({sp: {c: (v["tested"], v["supported"]) for c, v in h.items()} for sp, h in fit["H5"].items()}),
          json.dumps(fit["max_gain"], default=float)[:600])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["design", "calibrate", "run", "analyse"])
    ap.add_argument("--max-seconds", type=float, default=480.0)
    a = ap.parse_args()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 100, exit=True)
    if a.cmd == "design":
        cmd_design()
    elif a.cmd == "calibrate":
        cmd_calibrate(a.max_seconds)
    elif a.cmd == "run":
        cmd_run(a.max_seconds)
    else:
        cmd_analyse()
