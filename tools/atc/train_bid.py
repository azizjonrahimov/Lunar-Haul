"""B-74: train the learned bid correction by imitation of O_ORACLE (DAgger) and evaluate it.

    python tools/atc/train_bid.py collect --iter i     # rollouts on the training seeds (and, at i = 0, the tuning seeds)
    python tools/atc/train_bid.py train --iter i       # MLP 12-32-32-1 and linear on every row so far -> .cache/atc/
    python tools/atc/train_bid.py export               # -> data/policies/atc_bid_v1.json (+ .check.json) and the linear
                                                       #    baseline atc_bid_linear_v1.json (+ .check.json)
    python tools/atc/train_bid.py evaluate             # seeds 1-30 at 30 % and 60 % load: O, hand bids, MLP, linear
    python tools/atc/train_bid.py ood                  # out-of-distribution cells, 10 seeds each
    python tools/atc/train_bid.py table                # -> results/ATC_learned_eval.json

DAgger: iteration 0 rolls out the hand-built bids (C_AUCTION); iteration i >= 1 rolls out the MLP of iteration i - 1
(C_LEARNED); every auction round of every rollout is labelled with the oracle's choice for each robot (the full-
information pooled marketplace on the same state, lunarsim.atc.learned.oracle_assignment); rows are aggregated over
iterations. Seeds: training 1000-1009 (loads 30 % and 60 % alternating, start years 2028-2031 by seed), tuning
2000-2004 (early stopping and model choice), evaluation 1-30 (never seen). Message loss 0.10, terrain radio, depth 1.
No cross-entropy-method fine-tune was run (optional in the task; see the report). Single process, --max-seconds 540.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
import warnings
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from lunarsim.atc import learned as LR  # noqa: E402

CACHE = os.path.join(ROOT, ".cache", "atc", "bid")
POL_DIR = os.path.join(ROOT, "data", "policies")
OUT_MLP = os.path.join(POL_DIR, "atc_bid_v1.json")
OUT_LIN = os.path.join(POL_DIR, "atc_bid_linear_v1.json")
RESULT = os.path.join(ROOT, "results", "ATC_learned_eval.json")
SCEN = os.path.join(ROOT, "data", "scenarios", "p5", "p5-{mix}-L{load}-T10.json")
TRAIN_SEEDS = tuple(range(1000, 1010))
TUNE_SEEDS = tuple(range(2000, 2005))
EVAL_SEEDS = tuple(range(1, 31))
ITERS = 5
LOSS = 0.10
HIDDEN = (32, 32)
EPOCHS = 40
LR_ = 3e-3
SEED_TORCH = 74


def _seed_cfg(seed: int) -> Tuple[str, int]:
    return ("30" if seed % 2 == 0 else "60"), 2028 + seed % 4


def _scenario(mix="3eq", load="30", fleet_mult=1, horizon=None):
    from lunarsim.config import load_scenario
    sc = load_scenario(SCEN.format(mix=mix, load=load))
    if fleet_mult > 1:
        sc = sc.with_(fleet=list(sc.fleet) * fleet_mult, n_operators=sc.n_operators * fleet_mult)
    if horizon:
        sc = sc.with_(horizon_h=float(horizon))
    return sc


def _run(regime: str, sc, seed: int, kw: Dict[str, Any]):
    from lunarsim import Simulation
    from lunarsim.atc import regimes as G
    sim = Simulation(sc, G.mechanism(regime), seed=seed, mech_kwargs=dict(kw))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        s = sim.run()
    return sim, s


def _policy_path(it: int, kind: str) -> str:
    return os.path.join(CACHE, f"bid_it{it}_{kind}.json")


def _out_of_time(t0, max_s, last):
    return time.time() - t0 > max_s - max(90.0, 1.5 * last)


# ---------------------------------------------------------------------------------------------------- collect
def cmd_collect(it: int, max_s: float) -> bool:
    os.makedirs(CACHE, exist_ok=True)
    t0, last = time.time(), 40.0
    jobs = [("train", s) for s in TRAIN_SEEDS] + ([("tune", s) for s in TUNE_SEEDS] if it == 0 else [])
    for split, seed in jobs:
        path = os.path.join(CACHE, f"data_it{it}_{split}_{seed}.npz")
        if os.path.isfile(path):
            continue
        if _out_of_time(t0, max_s, last):
            print(f"collect it {it}: time limit; rerun")
            return False
        load, year = _seed_cfg(seed)
        kw = {"loss": LOSS, "collect": True, "start_year": year}
        if it == 0:
            regime = "C_AUCTION"
        else:
            regime, kw["policy"] = "C_LEARNED", _policy_path(it - 1, "mlp")
        t = time.time()
        sim, s = _run(regime, _scenario("3eq", load), seed, kw)
        X, sc, y, g = sim.atc.collector.arrays()
        np.savez_compressed(path, X=X, s=sc, y=y, g=g)
        last = time.time() - t
        print(f"  it {it} {split} {seed} (load {load} %, {year}): {len(np.unique(g))} groups, {len(y)} rows, "
              f"urgent {s['atc_urgent_wait_mean_cens_h']:.1f} h ({last:.0f} s)", flush=True)
    print(f"collect it {it}: done")
    return True


def _load_rows(pattern: str):
    Xs, ss, ys, gs, off = [], [], [], [], 0
    for f in sorted(glob.glob(os.path.join(CACHE, pattern))):
        z = np.load(f)
        if len(z["y"]) == 0:
            continue
        Xs.append(z["X"]); ss.append(z["s"]); ys.append(z["y"]); gs.append(z["g"] + off)
        off += int(z["g"].max()) + 1
    if not Xs:
        raise SystemExit(f"no rows for {pattern}; run collect")
    return np.concatenate(Xs), np.concatenate(ss), np.concatenate(ys), np.concatenate(gs)


# ---------------------------------------------------------------------------------------------------- train
def _groups(s, y, g):
    """Padded group tensors: index matrix (G, K), mask, hand scores, target position."""
    order = np.argsort(g, kind="stable")
    g_sorted = g[order]
    starts = np.r_[0, np.flatnonzero(np.diff(g_sorted)) + 1]
    ends = np.r_[starts[1:], len(g_sorted)]
    K = int((ends - starts).max())
    idx = np.zeros((len(starts), K), int)
    mask = np.zeros((len(starts), K), bool)
    tgt = np.zeros(len(starts), int)
    for k, (a, b) in enumerate(zip(starts, ends)):
        rows = order[a:b]
        idx[k, :b - a] = rows
        mask[k, :b - a] = True
        tgt[k] = int(np.flatnonzero(y[rows] == 1)[0])
    return idx, mask, tgt


def _fit(kind: str, X, s, y, g, Xv, sv, yv, gv, offset, scale):
    import torch
    torch.manual_seed(SEED_TORCH)
    torch.set_num_threads(2)
    Xn = torch.tensor((X - offset) / scale, dtype=torch.float32)
    Xvn = torch.tensor((Xv - offset) / scale, dtype=torch.float32)
    S, Sv = torch.tensor(s, dtype=torch.float32), torch.tensor(sv, dtype=torch.float32)
    if kind == "mlp":
        net = torch.nn.Sequential(torch.nn.Linear(X.shape[1], HIDDEN[0]), torch.nn.Tanh(),
                                  torch.nn.Linear(HIDDEN[0], HIDDEN[1]), torch.nn.Tanh(), torch.nn.Linear(HIDDEN[1], 1))
    else:
        net = torch.nn.Sequential(torch.nn.Linear(X.shape[1], 1))
    with torch.no_grad():                                   # start from g = 0: the hand-built bids
        net[-1].weight.zero_(); net[-1].bias.zero_()
    # a learned temperature on the hand score: ranking by a * hand + g equals ranking by hand + g / a, so the
    # exported correction is g / a (the last layer divided by a) and the deployed bid rule is unchanged
    log_a = torch.zeros(1, requires_grad=True)
    opt = torch.optim.Adam(list(net.parameters()) + [log_a], lr=LR_)
    idx, mask, tgt = (torch.tensor(a) for a in _groups(s, y, g))
    vidx, vmask, vtgt = (torch.tensor(a) for a in _groups(sv, yv, gv))

    def loss_acc(Xt, St, I, M, T, chunk=None):
        if chunk:                                           # evaluation in group chunks (memory)
            out = [loss_acc(Xt, St, I[k:k + chunk], M[k:k + chunk], T[k:k + chunk]) for k in range(0, len(T), chunk)]
            w = torch.tensor([min(chunk, len(T) - k) for k in range(0, len(T), chunk)], dtype=torch.float32)
            return (torch.stack([o[0] for o in out]) * w).sum() / w.sum(), (torch.stack([o[1] for o in out]) * w).sum() / w.sum()
        z = (log_a.exp() * St[I] + net(Xt[I.reshape(-1)])[:, 0].reshape(I.shape)).masked_fill(~M, -1e9)
        loss = torch.nn.functional.cross_entropy(z, T)
        acc = (z.argmax(1) == T).float().mean()
        return loss, acc

    hist = []
    n = len(tgt)
    rng = np.random.default_rng(SEED_TORCH)
    # stage 1: the temperature alone (g = 0), so the network starts from the calibrated hand-built bids
    opt_a = torch.optim.Adam([log_a], lr=0.05)
    for _ in range(3):
        perm = torch.tensor(rng.permutation(n))
        for b in range(0, n, 2048):
            sel = perm[b:b + 2048]
            opt_a.zero_grad()
            loss, _ = loss_acc(Xn, S, idx[sel], mask[sel], tgt[sel])
            loss.backward()
            opt_a.step()
    with torch.no_grad():
        lv, av = loss_acc(Xvn, Sv, vidx, vmask, vtgt, chunk=2048)
    # model choice: the epoch with the best held-out agreement (the bid rule ranks by argmax); epoch -1 = g = 0
    best = ((float(av), -float(lv)), ({k: v.clone() for k, v in net.state_dict().items()}, log_a.detach().clone()), -1)
    hist.append([-1, None, None, round(float(lv), 5), round(float(av), 5), round(float(log_a.exp()), 5)])
    with torch.no_grad():
        z0 = Sv[vidx].masked_fill(~vmask, -1e9)               # the hand-built bids alone (a = 1, g = 0)
        l0, a0 = torch.nn.functional.cross_entropy(z0, vtgt), (z0.argmax(1) == vtgt).float().mean()
    for ep in range(EPOCHS):
        perm = torch.tensor(rng.permutation(n))
        for b in range(0, n, 512):
            sel = perm[b:b + 512]
            opt.zero_grad()
            loss, _ = loss_acc(Xn, S, idx[sel], mask[sel], tgt[sel])
            loss.backward()
            opt.step()
        with torch.no_grad():
            lt, at = loss_acc(Xn, S, idx, mask, tgt, chunk=2048)
            lv, av = loss_acc(Xvn, Sv, vidx, vmask, vtgt, chunk=2048)
        hist.append([ep, round(float(lt), 5), round(float(at), 5), round(float(lv), 5), round(float(av), 5)])
        hist[-1].append(round(float(log_a.exp()), 5))
        if (float(av), -float(lv)) > best[0]:
            best = ((float(av), -float(lv)), ({k: v.clone() for k, v in net.state_dict().items()}, log_a.detach().clone()), ep)
    net.load_state_dict(best[1][0])
    a = float(best[1][1].exp())
    with torch.no_grad():
        net[-1].weight.div_(a)
        net[-1].bias.div_(a)
    layers = []
    lin = [m for m in net if isinstance(m, torch.nn.Linear)]
    for k, m in enumerate(lin):
        layers.append({"w": m.weight.detach().double().numpy().tolist(), "b": m.bias.detach().double().numpy().tolist(),
                       "act": "tanh" if k < len(lin) - 1 else "linear"})
    n_par = sum(p.numel() for p in net.parameters())
    return layers, {"history": hist, "history_columns": ["epoch", "train_loss", "train_agreement", "val_loss",
                                                          "val_agreement", "temperature_a"],
                    "temperature_a": round(a, 6), "best_epoch": best[2], "val_loss_hand": round(float(l0), 5),
                    "val_acc_hand": round(float(a0), 5), "parameters": int(n_par)}


def cmd_train(it: int) -> None:
    t0 = time.time()
    X, s, y, g = _load_rows("data_it[0-%d]_train_*.npz" % it)
    Xv, sv, yv, gv = _load_rows("data_it0_tune_*.npz")
    offset = X.mean(0)
    scale = np.where(X.std(0) > 1e-6, X.std(0), 1.0)
    for kind in ("mlp", "linear"):
        layers, rec = _fit(kind, X, s, y, g, Xv, sv, yv, gv, offset, scale)
        doc = _policy_doc(kind, layers, offset, scale, {
            "algo": "imitation of O_ORACLE, DAgger", "iteration": it, "rows": int(len(y)),
            "groups": int(len(np.unique(g))), "val_groups": int(len(np.unique(gv))),
            "epochs": EPOCHS, "lr": LR_, "batch_groups": 512, "seed": SEED_TORCH, **rec,
            "wall_s": round(time.time() - t0, 1)})
        with open(_policy_path(it, kind), "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f)
        h = rec["history"][rec["best_epoch"] + 1]
        print(f"train it {it} {kind}: {len(y)} rows / {len(np.unique(g))} groups; best epoch {rec['best_epoch']}: "
              f"val loss {h[3]} (hand {rec['val_loss_hand']}), val agreement {h[4]} (hand {rec['val_acc_hand']}); "
              f"{rec['parameters']} parameters")


def _policy_doc(kind, layers, offset, scale, training) -> Dict[str, Any]:
    return {"format": "lunarsim-policy", "version": 1, "kind": kind, "id": "atc_bid_v1" if kind == "mlp" else "atc_bid_linear_v1",
            "env": "lunar/ATC-bid-v1",
            "obs": {"names": list(LR.FEATURES), "offset": [float(x) for x in offset], "scale": [float(x) for x in scale],
                    "note": "x_norm = (x - offset) / scale; features as lunarsim/atc/learned.py"},
            "act": {"names": ["bid_correction_h"],
                    "note": "the robot bids bid - urgency_usd_per_h * output (score = -bid / urgency_usd_per_h + output)"},
            "layers": layers, "training": training,
            "card": {"what": "learned correction to the on-Moon auction's hand-built bids (B-74)",
                     "honest_size": "a small MLP (12-32-32-1) or a linear model; the papers call it a learned bidding policy",
                     "teacher": "O_ORACLE (the full-information pooled marketplace) on the same auction state"}}


# ---------------------------------------------------------------------------------------------------- CEM
CEM_FIT_SEEDS = (1000, 1002, 1004, 1006)    # common random numbers: every candidate of every generation runs these
CEM_TUNE_SEEDS = (2000, 2002, 2004)          # selection; all at 30 % load (a 60 % year costs ~70 s; 60 % is tested
                                             # once, on seeds 1-30, as transfer)
CEM = {"linear": {"n": 10, "elite": 3, "gens": 6, "sigma0": 1.5},
       "mlp": {"n": 12, "elite": 3, "gens": 5, "sigma0": 0.5}}
CEM_SMOOTH = 0.7                             # new mean/std = 0.7 elite + 0.3 old
CEM_SIGMA_MIN = 0.05


def _hidden():
    """The MLP's fixed hidden layers (13-32-32, tanh), seeded: CEM fits the 32 output weights on top of them."""
    rng = np.random.default_rng(SEED_TORCH)
    n = len(LR.FEATURES)
    return [(rng.normal(0, 1 / np.sqrt(n), (HIDDEN[0], n)), np.zeros(HIDDEN[0])),
            (rng.normal(0, 1 / np.sqrt(HIDDEN[0]), (HIDDEN[1], HIDDEN[0])), np.zeros(HIDDEN[1]))]


def _dim(kind):
    return len(LR.FEATURES) if kind == "linear" else HIDDEN[1]


def _cem_doc(kind, theta, training=None) -> Dict[str, Any]:
    theta = [float(x) for x in theta]
    if kind == "linear":
        layers = [{"w": [theta], "b": [0.0], "act": "linear"}]
    else:
        layers = [{"w": w.tolist(), "b": b.tolist(), "act": "tanh"} for w, b in _hidden()]
        layers.append({"w": [theta], "b": [0.0], "act": "linear"})
    return _policy_doc(kind, layers, np.zeros(len(LR.FEATURES)), np.array(LR.SCALE), training or {})


def _fitness(kind, tag, theta, seeds, max_s, t0, runs) -> Optional[float]:
    """Mean urgent wait (censored, h) of C_LEARNED with policy theta on seeds (cached by tag and seed)."""
    vals = []
    for seed in seeds:
        key = f"{kind}|{tag}|{seed}"
        if key not in runs:
            if _out_of_time(t0, max_s, runs.get("_last", 40.0)):
                return None
            pth = os.path.join(CACHE, f"cem_{kind}_{tag}.json")
            with open(pth, "w", encoding="utf-8") as f:
                json.dump(_cem_doc(kind, theta), f)
            load, year = _seed_cfg(seed)
            t = time.time()
            if np.allclose(theta, 0):
                _, s = _run("C_AUCTION", _scenario("3eq", load), seed, {"loss": LOSS, "start_year": year})
            else:
                _, s = _run("C_LEARNED", _scenario("3eq", load), seed, {"loss": LOSS, "policy": pth, "start_year": year})
            runs[key] = s["atc_urgent_wait_mean_cens_h"]
            runs["_last"] = time.time() - t
            _save_json(os.path.join(CACHE, f"cem_{kind}_runs.json"), runs)
        vals.append(runs[key])
    return float(np.mean(vals))


def _save_json(path, doc):
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(doc, f)
    os.replace(path + ".tmp", path)


def cmd_cem(kind: str, max_s: float) -> bool:
    t0 = t_acc = time.time()          # t0: this chunk's time budget; t_acc: wall time not yet added to the record
    cfg = CEM[kind]
    sp = os.path.join(CACHE, f"cem_{kind}.json")
    rp = os.path.join(CACHE, f"cem_{kind}_runs.json")
    st = json.load(open(sp)) if os.path.isfile(sp) else {
        "gen": 0, "mu": [0.0] * _dim(kind), "sigma": [cfg["sigma0"]] * _dim(kind), "history": [], "wall_s": 0.0}
    runs = json.load(open(rp)) if os.path.isfile(rp) else {}
    hand_tune = _fitness(kind, "hand", np.zeros(_dim(kind)), CEM_TUNE_SEEDS, max_s, t0, runs)
    if hand_tune is None:
        print(f"cem {kind}: time limit (hand bids on the tuning seeds); rerun")
        return False
    st["hand_tune"] = hand_tune
    while st["gen"] < cfg["gens"]:
        g = st["gen"]
        if "cands" not in st:
            rng = np.random.default_rng([SEED_TORCH, g, 0 if kind == "linear" else 1])
            mu, sig = np.array(st["mu"]), np.array(st["sigma"])
            st["cands"] = [mu.tolist()] + [(mu + sig * rng.normal(size=len(mu))).tolist() for _ in range(cfg["n"] - 1)]
            st["gen_t0"] = time.time()
            _save_json(sp, st)
        fit = []
        for k, th in enumerate(st["cands"]):
            f = _fitness(kind, f"g{g}c{k}", np.array(th), CEM_FIT_SEEDS, max_s, t0, runs)
            if f is None:
                st["wall_s"] += time.time() - t_acc
                _save_json(sp, st)
                print(f"cem {kind}: time limit in generation {g}; rerun")
                return False
            fit.append(f)
        order = np.argsort(fit, kind="stable")
        elite = np.array([st["cands"][i] for i in order[:cfg["elite"]]])
        mu = CEM_SMOOTH * elite.mean(0) + (1 - CEM_SMOOTH) * np.array(st["mu"])
        sig = np.maximum(CEM_SMOOTH * elite.std(0) + (1 - CEM_SMOOTH) * np.array(st["sigma"]), CEM_SIGMA_MIN)
        tune = _fitness(kind, f"g{g}mu", mu, CEM_TUNE_SEEDS, max_s, t0, runs)
        if tune is None:
            st["wall_s"] += time.time() - t_acc
            _save_json(sp, st)
            print(f"cem {kind}: time limit (tuning seeds, generation {g}); rerun")
            return False
        st["history"].append({"gen": g, "fitness": [round(x, 4) for x in fit], "best_fitness": round(min(fit), 4),
                              "elite": [int(i) for i in order[:cfg["elite"]]], "mu": mu.tolist(), "sigma": sig.tolist(),
                              "tune_mu": round(tune, 4), "hand_tune": round(hand_tune, 4)})
        st["mu"], st["sigma"], st["gen"] = mu.tolist(), sig.tolist(), g + 1
        del st["cands"]
        st["wall_s"] += time.time() - t_acc
        t_acc = time.time()
        _save_json(sp, st)
        print(f"cem {kind} generation {g}: training fitness best {min(fit):.3f} h (current mean {fit[0]:.3f}); "
              f"new mean on tuning seeds {tune:.3f} h vs hand {hand_tune:.3f} h", flush=True)
    best = min(st["history"], key=lambda h: h["tune_mu"])
    print(f"cem {kind}: done; best tuning mean {best['tune_mu']} h (generation {best['gen']}) vs hand {hand_tune:.4f} h")
    return True


# ---------------------------------------------------------------------------------------------------- export
IMITATION = {   # DAgger iteration 0 on the 12 original features (B-74; models in .cache/atc/bid/imitation12/)
    "teacher": "O_ORACLE: the full-information pooled marketplace on the same auction state",
    "rows": 624640, "groups": 37941, "val_groups_tuning_seeds": "2000-2004",
    "hand_agreement_val": 0.92881, "best_epoch": -1,
    "finding": ("imitation reproduces the hand-built bids: their top item is the oracle's item for the robot in 92.9 % "
                "of held-out rounds, and every disagreement is an item the oracle gives another robot in the same round "
                "(318 of 318 at 30 % load, 404 of 404 at 60 %, seeds 2000/2001); both the MLP and the linear model reach "
                "their best held-out agreement with no correction (g = 0), so DAgger iterations 1-4 were not run"),
}


def cmd_export(it: int) -> None:
    """The CEM-selected policies (best mean on the tuning seeds) with the full training record."""
    rng = np.random.default_rng(0)
    for kind, out in (("mlp", OUT_MLP), ("linear", OUT_LIN)):
        st = json.load(open(os.path.join(CACHE, f"cem_{kind}.json"), encoding="utf-8"))
        best = min(st["history"], key=lambda h: h["tune_mu"])
        if best["tune_mu"] >= st["hand_tune"]:
            print(f"export {kind}: CEM found nothing on the tuning seeds ({best['tune_mu']} >= {st['hand_tune']}); not exported")
            continue
        training = {"algo": "imitation of O_ORACLE (DAgger), then the cross-entropy method on mean urgent wait",
                    "imitation": IMITATION,
                    "cem": {"parameters_searched": _dim(kind), "population": CEM[kind]["n"], "elite": CEM[kind]["elite"],
                            "generations": CEM[kind]["gens"], "sigma0": CEM[kind]["sigma0"], "smoothing": CEM_SMOOTH,
                            "fitness": ("mean urgent wait (censored, h), C_LEARNED, loss 0.10, 30 % load, common random "
                                        f"numbers: seeds {list(CEM_FIT_SEEDS)} for every candidate"),
                            "selection": f"mean of each generation on tuning seeds {list(CEM_TUNE_SEEDS)}; the best one is exported",
                            "hand_tune_h": round(st["hand_tune"], 4), "selected_generation": best["gen"],
                            "selected_tune_h": best["tune_mu"], "wall_s": round(st["wall_s"], 1),
                            "trace": [{k: h[k] for k in ("gen", "fitness", "best_fitness", "elite", "tune_mu")} for h in st["history"]]},
                    "hidden_layers": "fixed random (seed 74), not trained" if kind == "mlp" else None}
        doc = _cem_doc(kind, best["mu"], training)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            json.dump(doc, f)
        pol = LR.Policy(out)
        X = np.abs(rng.normal(0, 1, (50, len(LR.FEATURES)))) * np.array(LR.SCALE)
        with open(out.replace(".json", ".check.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump({"format": "lunarsim-policy-check", "version": 1, "policy": doc["id"], "tolerance": 1e-9,
                       "obs": X.tolist(), "act": [[float(v)] for v in pol(X)],
                       "note": "act = float64 numpy runtime (lunarsim.atc.learned.Policy) on obs; runtimes must "
                               "match it to 1e-9"}, f)
        print(f"export: {os.path.relpath(out, ROOT)} (generation {best['gen']}, tuning {best['tune_mu']} h vs hand "
              f"{st['hand_tune']:.4f} h)")


# ---------------------------------------------------------------------------------------------------- evaluate
EVAL_CELLS = [("O_ORACLE", "O_ORACLE", {}), ("hand", "C_AUCTION", {"loss": LOSS}),
              ("mlp", "C_LEARNED", {"loss": LOSS, "policy": OUT_MLP}),
              ("linear", "C_LEARNED", {"loss": LOSS, "policy": OUT_LIN})]
OOD_CELLS = [("2eq", dict(mix="2eq")), ("5eq", dict(mix="5eq")), 
             ("loss 0.25", dict(loss=0.25)), ("loss 0.40", dict(loss=0.40)), ("load 10 %", dict(load="10")),
             ("year 2038", dict(year=2038))]
OOD_SEEDS = tuple(range(1, 11))
KEEP = ("atc_urgent_wait_mean_cens_h", "atc_urgent_wait_p95_cens_h", "atc_urgent_within24_share", "delivered_kg",
        "atc_deadhead_share", "p5_cargo_util", "utilisation", "atc_starved_items", "p5_team_items",
        "p5_team_items_delivered", "atc_msgs_per_robot_h", "delay_prio2_mean_h", "delay_mean_bulk", "delay_mean_h",
        "tonne_days_waiting")
GUARD_SEEDS = tuple(range(1, 11))


def _summ(s) -> Dict[str, Any]:
    return {k: (float(s[k]) if s.get(k) is not None else None) for k in KEEP if k in s}


def _agreement(sim, pol_kind):
    """Held-out agreement with the teacher: share of a robot's auction rounds whose top score is the oracle's item."""
    X, sc, y, g = sim.atc.collector.arrays()
    if not len(y):
        return None
    if pol_kind == "hand":
        score = sc
    else:
        score = sc + LR.Policy(OUT_MLP if pol_kind == "mlp" else OUT_LIN)(X)
    hits = [y[g == k][np.argmax(score[g == k])] == 1 for k in np.unique(g)]
    return [float(np.mean(hits)), len(hits)]


def cmd_evaluate(max_s: float, which: str) -> bool:
    path = os.path.join(CACHE, f"{which}_runs.json")
    done = json.load(open(path)) if os.path.isfile(path) else {}
    t0, last = time.time(), 30.0
    if which == "guard":                          # the guards: what the urgent gain costs the other cargo
        plan = [(f"{lab}|{load}|{seed}", reg, kw, dict(load=load), seed, lab)
                for load in ("30", "60") for seed in GUARD_SEEDS for lab, reg, kw in EVAL_CELLS if lab in ("hand", "linear")]
    elif which == "eval":
        plan = [(f"{lab}|{load}|{seed}", reg, kw, dict(load=load), seed, lab)
                for load in ("30", "60") for seed in EVAL_SEEDS for lab, reg, kw in EVAL_CELLS]
    else:
        plan = [(f"{name}|{lab}|{seed}", reg, dict(kw, loss=o.get("loss", kw["loss"])), o, seed, lab)
                for name, o in OOD_CELLS for seed in OOD_SEEDS[:o.get("seeds", len(OOD_SEEDS))]
                for lab, reg, kw in EVAL_CELLS if lab in ("hand", "linear")]
    for key, reg, kw, o, seed, lab in plan:
        if key in done:
            continue
        if _out_of_time(t0, max_s, max(last, 330.0 / 1.5 if o.get("fleet_mult", 1) > 1 else 0.0)):
            print(f"{which}: time limit, {len(done)}/{len(plan)} done; rerun")
            return False
        kw = dict(kw)
        if "year" in o:
            kw["start_year"] = o["year"]
        if which == "eval" and o.get("load") == "30" and reg != "O_ORACLE":
            kw["collect"] = True                         # held-out agreement on the 30 % runs
        t = time.time()
        sim, s = _run(reg, _scenario(o.get("mix", "3eq"), o.get("load", "30"), o.get("fleet_mult", 1), o.get("horizon")),
                      seed, kw)
        r = _summ(s)
        if kw.get("collect"):
            r["agreement"] = _agreement(sim, lab)
        last = r["wall_s"] = round(time.time() - t, 1)
        done[key] = r
        with open(path + ".tmp", "w") as f:
            json.dump(done, f)
        os.replace(path + ".tmp", path)
        print(f"  {key}: urgent {r['atc_urgent_wait_mean_cens_h']:.2f} h ({r['wall_s']} s)", flush=True)
    print(f"{which}: done")
    return True


def _paired(a, b):
    d = np.array(a) - np.array(b)
    m, sd = float(d.mean()), float(d.std(ddof=1)) if len(d) > 1 else 0.0
    half = 2.045 * sd / np.sqrt(len(d)) if len(d) > 1 else 0.0          # t(0.975, 29); approximate for other n
    return {"mean": round(m, 3), "ci95": [round(m - half, 3), round(m + half, 3)], "n": int(len(d))}


def cmd_table() -> Dict[str, Any]:
    ev = json.load(open(os.path.join(CACHE, "eval_runs.json")))
    oo = json.load(open(os.path.join(CACHE, "ood_runs.json"))) if os.path.isfile(os.path.join(CACHE, "ood_runs.json")) else {}
    m = "atc_urgent_wait_mean_cens_h"
    out: Dict[str, Any] = {"task": "B-74", "note": __doc__.split("\n\n")[-1].strip(), "eval": {}, "ood": {},
                           "policies": {}}
    for kind, p in (("mlp", OUT_MLP), ("linear", OUT_LIN)):
        d = json.load(open(p, encoding="utf-8"))
        out["policies"][kind] = {"file": os.path.relpath(p, ROOT).replace(os.sep, "/"),
                                 "cem": {k: v for k, v in d["training"]["cem"].items() if k != "trace"}}
    out["imitation"] = IMITATION
    for load in ("30", "60"):
        v = {lab: [ev[f"{lab}|{load}|{s}"][m] for s in EVAL_SEEDS] for lab, _, _ in EVAL_CELLS}
        blk = {lab: {"urgent_mean_h": round(float(np.mean(x)), 3)} for lab, x in v.items()}
        for lab in ("hand", "mlp", "linear"):
            blk[lab]["regret_vs_teacher_h"] = _paired(v[lab], v["O_ORACLE"])
        for lab in ("mlp", "linear"):
            blk[lab]["vs_hand_h"] = _paired(v[lab], v["hand"])
            blk[lab]["vs_hand_share"] = round(float(np.mean(v[lab]) / np.mean(v["hand"]) - 1), 4)
        for k in ("p5_cargo_util", "utilisation", "delivered_kg", "atc_starved_items", "atc_urgent_within24_share",
                  "atc_urgent_wait_p95_cens_h"):
            for lab, _, _ in EVAL_CELLS:
                blk[lab][k] = round(float(np.mean([ev[f"{lab}|{load}|{s}"].get(k, np.nan) for s in EVAL_SEEDS])), 4)
        if load == "30":
            for lab in ("hand", "mlp", "linear"):
                a = [ev[f"{lab}|30|{s}"]["agreement"] for s in EVAL_SEEDS]
                hits = sum(x[0] * x[1] for x in a)
                n = sum(x[1] for x in a)
                blk[lab]["heldout_agreement"] = round(hits / n, 4)
                blk[lab]["heldout_groups"] = int(n)
        out["eval"][load] = blk
    for name, o in OOD_CELLS:
        seeds = OOD_SEEDS[:o.get("seeds", len(OOD_SEEDS))]
        if not all(f"{name}|{lab}|{s}" in oo for s in seeds for lab in ("hand", "linear")):
            continue
        v = {lab: [oo[f"{name}|{lab}|{s}"][m] for s in seeds] for lab in ("hand", "linear")}
        out["ood"][name] = {lab: {"urgent_mean_h": round(float(np.mean(x)), 3),
                                  "starved_items": round(float(np.mean([oo[f"{name}|{lab}|{s}"].get("atc_starved_items", np.nan) for s in seeds])), 2)}
                            for lab, x in v.items()}
        for lab in ("linear",):
            out["ood"][name][lab]["vs_hand_h"] = _paired(v[lab], v["hand"])
    gp = os.path.join(CACHE, "guard_runs.json")
    if os.path.isfile(gp):
        gr = json.load(open(gp))
        out["guards"] = {}
        for load in ("30", "60"):
            if not all(f"{lab}|{load}|{sd}" in gr for sd in GUARD_SEEDS for lab in ("hand", "linear")):
                continue
            blk = {}
            for k in ("atc_urgent_wait_mean_cens_h", "delay_prio2_mean_h", "delay_mean_bulk", "delay_mean_h",
                      "tonne_days_waiting", "atc_starved_items", "delivered_kg"):
                h = [gr[f"hand|{load}|{sd}"][k] for sd in GUARD_SEEDS]
                l = [gr[f"linear|{load}|{sd}"][k] for sd in GUARD_SEEDS]
                blk[k] = {"hand": round(float(np.mean(h)), 3), "linear": round(float(np.mean(l)), 3),
                          "linear_minus_hand": _paired(l, h)}
            out["guards"][load] = blk
    with open(RESULT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(json.dumps(out["eval"], indent=1)[:3000])
    return out


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python tools/atc/train_bid.py")
    ap.add_argument("cmd", choices=["collect", "train", "cem", "export", "evaluate", "ood", "guard", "table"])
    ap.add_argument("--kind", default="linear", choices=["linear", "mlp"])
    ap.add_argument("--iter", type=int, default=0)
    ap.add_argument("--max-seconds", type=float, default=540.0)
    a = ap.parse_args(argv)
    import faulthandler
    faulthandler.dump_traceback_later(a.max_seconds + 30, exit=True)
    if a.cmd == "collect":
        cmd_collect(a.iter, a.max_seconds)
    elif a.cmd == "train":
        cmd_train(a.iter)
    elif a.cmd == "cem":
        cmd_cem(a.kind, a.max_seconds)
    elif a.cmd == "export":
        cmd_export(a.iter)
    elif a.cmd == "evaluate":
        cmd_evaluate(a.max_seconds, "eval")
    elif a.cmd == "ood":
        cmd_evaluate(a.max_seconds, "ood")
    elif a.cmd == "guard":
        cmd_evaluate(a.max_seconds, "guard")
    else:
        cmd_table()
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from terrain_assets import peak_rss_mb
    rss = peak_rss_mb()
    if rss:
        print(f"peak RSS {rss:.0f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
