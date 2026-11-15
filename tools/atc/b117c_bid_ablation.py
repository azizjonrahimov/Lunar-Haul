"""B-117 (c), P1 S12: what the learned linear bid's 13 weights do, and the hand rule tuned with the same budget.

    python tools/atc/b117c_bid_ablation.py ablate     # resumable (--max-seconds 500)
    python tools/atc/b117c_bid_ablation.py tune       # resumable: CEM on the hand rule's 4 parameters
    python tools/atc/b117c_bid_ablation.py evaluate   # resumable: the tuned hand rule on seeds 1-30, 30 % and 60 % load
    python tools/atc/b117c_bid_ablation.py table      # -> results/B117c_bid_ablation.json (a new file)

Ablation: the published linear policy (data/policies/atc_bid_linear_v1.json) with one weight set to 0 at a time (13
policies), run as train_bid's evaluation runs them (C_LEARNED, 3eq, 30 % load, loss 0.10, seeds 1-30), with the full
linear policy and the hand bids (C_AUCTION) repeated on the current code as references; the references must equal
train_bid's cached evaluation runs (.cache/atc/bid_rerun/eval_runs.json; checked in the table).
Tuning: the hand rule's four parameters (dispatch._bid: w_p1 = 6 h, w_p2 = 2 h, w_age = 0.08, vot_scale = 1; as
dispatch kwargs) fitted with the linear CEM's own budget and seeds (train_bid.CEM["linear"]: 10 candidates, 3 elite, 6
generations, sigma0 1.5, smoothing 0.7; training seeds CEM_FIT_SEEDS, selection on CEM_TUNE_SEEDS; 30 % load), in log
space around the defaults (parameter = default x exp(theta), so every parameter stays positive). The selected point
(lowest mean on the selection seeds, as cmd_cem picks) is evaluated on seeds 1-30 at 30 % and 60 % load and paired
with the hand and linear runs (60 %: train_bid's cached evaluation runs). Pre-declared in the B-117 estimate (13 Nov).
"""
from __future__ import annotations

import argparse
import copy
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
import train_bid as TB  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "b117c")
RUNS = os.path.join(CACHE, "runs.json")
CEM_STATE = os.path.join(CACHE, "cem_hand.json")
OUT = os.path.join(ROOT, "results", "B117c_bid_ablation.json")
REF_RUNS = os.path.join(ROOT, ".cache", "atc", "bid_rerun", "eval_runs.json")
FIXPOINT = False          # B-122: --fixpoint runs everything on the engine with PREREG change 5 (own cache)
NO_FIX_BLOCK = "no_fixpoint_2026-11-15"
HAND = {"w_p1": 6.0, "w_p2": 2.0, "w_age": 0.08, "vot_scale": 1.0}
NAMES = list(HAND)


def _code():
    import run_e50 as E5
    return E5.code_fingerprint() + ("+fixpoint" if FIXPOINT else "")


def _set_fixpoint():
    """B-122: train_bid's runs with the dispatch fixed point; own cache; references from the fixed-point evaluation."""
    global FIXPOINT, CACHE, RUNS, CEM_STATE, REF_RUNS
    FIXPOINT = TB.FIXPOINT = True
    CACHE = os.path.join(ROOT, ".cache", "atc", "b117c_fixpoint")
    RUNS, CEM_STATE = os.path.join(CACHE, "runs.json"), os.path.join(CACHE, "cem_hand.json")
    REF_RUNS = os.path.join(ROOT, ".cache", "atc", "bid_fixpoint", "eval_runs.json")


def _load(path, default):
    return json.load(open(path, encoding="utf-8")) if os.path.isfile(path) else default


def _save(path, doc):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(doc, f, allow_nan=False)
    os.replace(path + ".tmp", path)


def _ablated_policy(i):
    doc = json.load(open(TB.OUT_LIN, encoding="utf-8"))
    d = copy.deepcopy(doc)
    if i is not None:
        d["layers"][-1]["w"][0][i] = 0.0
    p = os.path.join(CACHE, f"linear_zero_{i}.json" if i is not None else "linear_full.json")
    _save(p, d)
    return p


def hand_kw(theta):
    return {k: HAND[k] * float(np.exp(t)) for k, t in zip(NAMES, theta)}


class Runner:
    def __init__(self, max_s):
        self.t0, self.max_s = time.time(), max_s
        self.runs = _load(RUNS, {})
        fp = _code()
        if self.runs and self.runs.get("_code") != fp:
            raise SystemExit(f"{RUNS} was made with other code; delete it and rerun")
        self.runs["_code"] = fp
        self.last = 10.0

    def out_of_time(self):
        return time.time() - self.t0 > self.max_s - max(60.0, 1.5 * self.last)

    def get(self, key, regime, load, seed, kw):
        """Urgent wait etc. of one run, cached by key; None at the time limit."""
        if key in self.runs:
            return self.runs[key]
        if self.out_of_time():
            return None
        t = time.time()
        _, s = TB._run(regime, TB._scenario("3eq", load), seed, kw)
        self.last = time.time() - t
        self.runs[key] = {k: (float(s[k]) if s.get(k) is not None else None) for k in TB.KEEP if k in s}
        _save(RUNS, self.runs)
        print(f"  {key}: {self.runs[key]['atc_urgent_wait_mean_cens_h']:.3f} h ({self.last:.1f} s)", flush=True)
        return self.runs[key]


def cmd_ablate(max_s):
    R = Runner(max_s)
    plan = [("hand", "C_AUCTION", {"loss": TB.LOSS})]
    plan.append(("linear", "C_LEARNED", {"loss": TB.LOSS, "policy": _ablated_policy(None)}))
    plan += [(f"zero {TB.LR.FEATURES[i]}", "C_LEARNED", {"loss": TB.LOSS, "policy": _ablated_policy(i)})
             for i in range(len(TB.LR.FEATURES))]
    for lab, reg, kw in plan:
        for seed in TB.EVAL_SEEDS:
            if R.get(f"{lab}|30|{seed}", reg, "30", seed, kw) is None:
                print("ablate: time limit; rerun", flush=True)
                return False
    if FIXPOINT:                                          # B-122: the 60 % references repeated, not from a cache
        for lab, reg, kw in plan[:2]:
            for seed in TB.EVAL_SEEDS:
                if R.get(f"{lab}|60|{seed}", reg, "60", seed, kw) is None:
                    print("ablate: time limit; rerun", flush=True)
                    return False
    print("ablate: done", flush=True)
    return True


def _fit(R, tag, theta, seeds):
    vals = []
    for seed in seeds:
        load, year = TB._seed_cfg(seed)
        r = R.get(f"cem|{tag}|{seed}", "C_AUCTION", load, seed, dict({"loss": TB.LOSS, "start_year": year}, **hand_kw(theta)))
        if r is None:
            return None
        vals.append(r["atc_urgent_wait_mean_cens_h"])
    return float(np.mean(vals))


def cmd_tune(max_s):
    R = Runner(max_s)
    cfg = TB.CEM["linear"]
    st = _load(CEM_STATE, {"gen": 0, "mu": [0.0] * 4, "sigma": [cfg["sigma0"]] * 4, "history": []})
    base = _fit(R, "default", np.zeros(4), TB.CEM_TUNE_SEEDS)
    if base is None:
        print("tune: time limit; rerun")
        return False
    st["default_tune"] = base
    while st["gen"] < cfg["gens"]:
        g = st["gen"]
        if "cands" not in st:
            rng = np.random.default_rng([TB.SEED_TORCH, g, 117])
            mu, sig = np.array(st["mu"]), np.array(st["sigma"])
            st["cands"] = [mu.tolist()] + [(mu + sig * rng.normal(size=4)).tolist() for _ in range(cfg["n"] - 1)]
            _save(CEM_STATE, st)
        fit = []
        for k, th in enumerate(st["cands"]):
            f = _fit(R, f"g{g}c{k}", np.array(th), TB.CEM_FIT_SEEDS)
            if f is None:
                print(f"tune: time limit in generation {g}; rerun", flush=True)
                return False
            fit.append(f)
        order = np.argsort(fit, kind="stable")
        elite = np.array([st["cands"][i] for i in order[:cfg["elite"]]])
        mu = TB.CEM_SMOOTH * elite.mean(0) + (1 - TB.CEM_SMOOTH) * np.array(st["mu"])
        sig = np.maximum(TB.CEM_SMOOTH * elite.std(0) + (1 - TB.CEM_SMOOTH) * np.array(st["sigma"]), TB.CEM_SIGMA_MIN)
        tune = _fit(R, f"g{g}mu", mu, TB.CEM_TUNE_SEEDS)
        if tune is None:
            print(f"tune: time limit (selection seeds, generation {g}); rerun", flush=True)
            return False
        st["history"].append({"gen": g, "fitness": [round(x, 4) for x in fit], "mu": mu.tolist(),
                              "params": hand_kw(mu), "sigma": sig.tolist(), "tune_mu": round(tune, 4)})
        st["mu"], st["sigma"], st["gen"] = mu.tolist(), sig.tolist(), g + 1
        del st["cands"]
        _save(CEM_STATE, st)
        print(f"tune generation {g}: best training {min(fit):.3f} h; mean on selection seeds {tune:.3f} h "
              f"(default {base:.3f} h); {hand_kw(mu)}", flush=True)
    print("tune: done", flush=True)
    return True


def _selected():
    st = _load(CEM_STATE, None)
    if not st or st["gen"] < TB.CEM["linear"]["gens"]:
        raise SystemExit("run tune first")
    best = min(st["history"], key=lambda h: h["tune_mu"])
    return best, st


def cmd_evaluate(max_s):
    R = Runner(max_s)
    best, _ = _selected()
    kw = dict({"loss": TB.LOSS}, **hand_kw(best["mu"]))
    for load in ("30", "60"):
        for seed in TB.EVAL_SEEDS:
            if R.get(f"hand tuned|{load}|{seed}", "C_AUCTION", load, seed, kw) is None:
                print("evaluate: time limit; rerun", flush=True)
                return False
    print("evaluate: done", flush=True)
    return True


def cmd_table():
    from experiments.phase5.analyse_e40 import boot
    runs = _load(RUNS, {})
    if runs.get("_code") != _code():
        raise SystemExit("runs made with other code; rerun")
    ref = _load(REF_RUNS, {})
    m = "atc_urgent_wait_mean_cens_h"
    ser = lambda lab, load="30": np.array([runs[f"{lab}|{load}|{s}"][m] for s in TB.EVAL_SEEDS])
    refser = lambda lab, load: np.array([ref[f"{lab}|{load}|{s}"][m] for s in TB.EVAL_SEEDS])
    check = {lab: float(np.max(np.abs(ser(lab) - refser(lab, "30")))) for lab in ("hand", "linear")}
    if FIXPOINT:
        check.update({f"{lab} 60": float(np.max(np.abs(ser(lab, "60") - refser(lab, "60")))) for lab in ("hand", "linear")})
    if any(v != 0.0 for v in check.values()):
        raise SystemExit(f"the repeated references differ from train_bid's cached evaluation runs: {check}")
    best, st = _selected()
    full = ser("linear")
    out = {"task": "B-117 (c), P1 S12: ablation of the linear bid's 13 weights, and a tuned hand rule",
           "note": __doc__.split("\n\n")[1].strip() + " " + __doc__.split("\n\n")[2].strip(), "code": runs["_code"],
           "seeds": list(TB.EVAL_SEEDS), "references_reproduce_cached_eval_runs": True,
           "weights": dict(zip(TB.LR.FEATURES, json.load(open(TB.OUT_LIN))["layers"][-1]["w"][0])),
           "urgent_wait_h_30": {"hand": round(float(ser("hand").mean()), 4), "linear": round(float(full.mean()), 4)},
           "ablation_30": {}, "tuned_hand": {}}
    for f in TB.LR.FEATURES:
        z = ser(f"zero {f}")
        out["ablation_30"][f] = {"urgent_wait_h": round(float(z.mean()), 4), "minus_linear": boot(z - full),
                                 "minus_hand": boot(z - ser("hand"))}
    out["tuned_hand"] = {"selected_generation": best["gen"], "params": best["params"], "theta_log": best["mu"],
                         "selection_seeds_mean_h": best["tune_mu"], "default_selection_seeds_mean_h": st["default_tune"],
                         "history": st["history"]}
    for load in ("30", "60"):
        th = ser("hand tuned", load)
        hand = ser("hand", load) if FIXPOINT else (ser("hand") if load == "30" else refser("hand", "60"))
        lin = full if load == "30" else (ser("linear", "60") if FIXPOINT else refser("linear", "60"))
        out["tuned_hand"][f"load_{load}"] = {"urgent_wait_h": round(float(th.mean()), 4),
                                             "hand_h": round(float(hand.mean()), 4), "linear_h": round(float(lin.mean()), 4),
                                             "tuned_minus_hand": boot(th - hand), "linear_minus_tuned": boot(lin - th)}
    out["tuned_hand"]["note_60"] = ("hand and linear at 60 % load: repeated here, and equal to the fixed-point "
                                    "evaluation's runs (.cache/atc/bid_fixpoint/eval_runs.json)" if FIXPOINT else
                                    "hand and linear at 60 % load: train_bid's cached evaluation runs "
                                    "(.cache/atc/bid_rerun/eval_runs.json), not repeated; the 30 % references equal "
                                    "their cached runs exactly")
    if FIXPOINT:
        out["engine"] = ("PREREG change 5 on (Scenario.p5 dispatch_fixpoint: fixed point and wake dedupe), as E40 and "
                         "results/ATC_learned_eval_fixpoint.json; the linear policy was trained without it and not "
                         "retrained; the tuned hand rule was selected again by the CEM on this engine (same budget, "
                         "seeds and random streams)")
        if os.path.isfile(OUT):
            prev = json.load(open(OUT, encoding="utf-8"))
            if NO_FIX_BLOCK in prev:
                out[NO_FIX_BLOCK] = prev[NO_FIX_BLOCK]
            elif not str(prev.get("code", "")).endswith("+fixpoint"):
                out[NO_FIX_BLOCK] = dict({"reason": "B-122 (15 Nov 2026): the first run of (c) used train_bid's "
                                                    "engine without PREREG change 5 (no dispatch fixed point), as "
                                                    "results/ATC_learned_eval_rerun.json did; kept as it was. The "
                                                    "main content of this file is on the engine with change 5."},
                                         **prev)
    text = json.dumps(out, indent=1, allow_nan=False) + "\n"
    with open(OUT + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(OUT + ".tmp", OUT)
    print(text[:6000])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["ablate", "tune", "evaluate", "table"])
    ap.add_argument("--max-seconds", type=float, default=500.0)
    ap.add_argument("--fixpoint", action="store_true", help="B-122: the engine with PREREG change 5 (own cache)")
    a = ap.parse_args()
    if a.fixpoint:
        _set_fixpoint()
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 120, exit=True)
    {"ablate": cmd_ablate, "tune": cmd_tune, "evaluate": cmd_evaluate}.get(a.cmd, lambda _: cmd_table())(a.max_seconds)
