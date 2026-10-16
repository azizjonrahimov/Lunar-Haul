"""Behaviour-cloning rover driver (B-13, PLAN §5.4): PilotNet-style CNN on terrain patches, DAgger, ONNX export.

    python -m lunarsim.rover.bc --site connecting_ridge --legs 20 --stride 5 --dagger 3 --epochs 10 --id rover_bc_s0

Pipeline
1. Dataset: the scripted expert (A* route + pure pursuit, expert.py) drives legs between the sites of the terrain
   pack (sites.json; pads at every standoff) under every lighting case (sun azimuth 0/90/180/270, night) in
   lunar/Drive-v0. Every `stride`-th step is recorded: patch (3x32x32, float16), scalars (5, float32) and the
   expert's action (steer-rate command, throttle). Saved as an npz under runs/ (kept well under 2 GB).
2. Model: PilotNet-style CNN (Bojarski et al. 2016, scaled to a 32x32 input): conv 5x5/2 (24) -> conv 5x5/2 (36)
   -> conv 3x3 (48) -> flatten, concatenated with the scalars -> 100 -> 50 -> 10 -> 2, tanh output in [-1, 1].
3. Training: MSE on the expert actions (Adam). DAgger: roll out the current policy, label every recorded state with
   the expert's action for that state, aggregate, retrain (>= 3 rounds).
   Memory bound (B-20): a rollout records every `stride`-th step like the base data, but a policy that does not
   reach its goal drives until the env's step limit (up to 50,000 steps), so one round can record ten times the
   base data. Each round therefore keeps at most `dagger_steps_cap` samples (reservoir sample over the round) and
   stops early once more than half of its runs so far (after the first 5) did not reach the goal; the patches stay
   float16 in RAM and training converts one mini-batch at a time to float32. Every round prints the dataset size
   and the process memory (working set, its peak, private bytes).
4. Export: ONNX (opset 17; inputs "patch" [N,3,32,32] and "scalars" [N,5], output "action" [N,2]) + a
   lunarsim-policy v1 card (kind "cnn") data/policies/<id>.json with the input spec, normalisation, training record
   and check vectors (<id>.check.json, onnxruntime outputs; torch agrees to 1e-5).

Device: CUDA when torch sees a GPU (the cu126 wheel), else CPU; the card records which.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import platform
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np

from . import physics as R
from .env import DT_S, DriveEnv, ENV_ID, ENV_VERSION, PATCH, SCALAR_NAMES
from .expert import PurePursuit, plan

LIGHTING = (0.0, 90.0, 180.0, 270.0, R.NIGHT)
PATCH_CHANNELS = ["height_rel_10m", "slope_20deg", "roughness_1m"]


# ---------------------------------------------------------------------------------------------------------
# drivers with one interface: act(obs) -> np.array([steer_rate_cmd, throttle])
# ---------------------------------------------------------------------------------------------------------
class ExpertDriver:
    """The scripted expert behind the act(obs) interface (it reads the env's state, not the observation)."""

    def __init__(self, env: DriveEnv):
        self.env = env
        self.pp: Optional[PurePursuit] = None

    def reset(self):
        self.pp = PurePursuit(self.env.route)

    def act(self, obs=None) -> np.ndarray:
        s = self.env.state
        cap = self.env._v_cap(s["x"], s["y"], s["psi"])
        return np.array(self.pp.action(s, cap), dtype=np.float32)


class TorchDriver:
    def __init__(self, model, device="cpu"):
        self.model, self.device = model, device

    def reset(self):
        pass

    def act(self, obs) -> np.ndarray:
        import torch
        with torch.no_grad():
            p = torch.as_tensor(np.asarray(obs["patch"], np.float32)[None], device=self.device)
            s = torch.as_tensor(np.asarray(obs["scalars"], np.float32)[None], device=self.device)
            return self.model(p, s).cpu().numpy()[0].astype(np.float32)


# ---------------------------------------------------------------------------------------------------------
# model
# ---------------------------------------------------------------------------------------------------------
def make_model():
    import torch
    import torch.nn as nn

    class PilotNet(nn.Module):
        def __init__(self):
            super().__init__()
            self.conv = nn.Sequential(nn.Conv2d(3, 24, 5, stride=2, padding=2), nn.ELU(),
                                      nn.Conv2d(24, 36, 5, stride=2, padding=2), nn.ELU(),
                                      nn.Conv2d(36, 48, 3, stride=1, padding=1), nn.ELU(), nn.Flatten())
            n = 48 * (PATCH // 4) * (PATCH // 4)
            self.head = nn.Sequential(nn.Linear(n + len(SCALAR_NAMES), 100), nn.ELU(), nn.Linear(100, 50), nn.ELU(),
                                      nn.Linear(50, 10), nn.ELU(), nn.Linear(10, 2), nn.Tanh())

        def forward(self, patch, scalars):
            return self.head(torch.cat([self.conv(patch), scalars], dim=1))

    return PilotNet()


def device_name() -> str:
    import torch
    return "cuda" if torch.cuda.is_available() else "cpu"


# ---------------------------------------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------------------------------------
def leg_list(terrain, n_legs: int, seed: int = 0) -> List[Tuple[str, Tuple[float, float], Tuple[float, float]]]:
    """A reproducible sample of ordered site/pad legs from the pack's sites.json (all legs if n_legs <= 0)."""
    from .tables import legs_from_sites
    with open(os.path.join(terrain.path, "sites.json"), encoding="utf-8") as f:
        legs = [l for l in legs_from_sites(json.load(f)) if np.hypot(l[1][0] - l[2][0], l[1][1] - l[2][1]) >= 1.0]
    if n_legs > 0 and n_legs < len(legs):
        idx = np.random.default_rng(seed).choice(len(legs), n_legs, replace=False)
        legs = [legs[i] for i in sorted(idx)]
    return legs


def drive(env: DriveEnv, route, sun, driver, expert: Optional[ExpertDriver], stride: int, autonomy: str = "autonomous",
          rtt_s: float = 4.0, seed: int = 0, record: bool = True, max_steps: Optional[int] = None,
          sink: Optional[Callable] = None):
    """Drive one leg with `driver`; when `expert` is given, record (obs, expert action) every `stride` steps.
    Returns (records, leg info). With `sink`, each record goes to sink(patch, scalars, action) instead and the
    returned record lists are empty."""
    obs, _ = env.reset(seed=seed, options={"waypoints": route, "autonomy": autonomy, "rtt_s": rtt_s, "sun_az_deg": sun})
    driver.reset()
    if expert is not None and expert is not driver:
        expert.reset()
    P, S, A = [], [], []
    k = 0
    info: Dict[str, Any] = {}
    while True:
        if record and expert is not None and k % stride == 0:
            if sink is not None:
                sink(obs["patch"].astype(np.float16), obs["scalars"], expert.act(obs))
            else:
                P.append(obs["patch"].astype(np.float16))
                S.append(obs["scalars"])
                A.append(expert.act(obs))
        a = driver.act(obs)
        obs, _, term, trunc, info = env.step(a)
        k += 1
        if term or trunc or (max_steps and k >= max_steps):
            break
    leg = info.get("leg") or {"time_s": env.time_s, "energy_wh": env.energy_wh, "interventions": env.interventions,
                               "distance_m": env.dist_m, "stops": env.stops, "reached": False}
    return (P, S, A), leg


class Reservoir:
    """Uniform sample of at most `cap` items from a stream of unknown length (Vitter's algorithm R)."""

    def __init__(self, cap: int, rng: np.random.Generator):
        self.cap, self.rng, self.items, self.seen = int(cap), rng, [], 0

    def add(self, *item) -> None:
        self.seen += 1
        if len(self.items) < self.cap:
            self.items.append(item)
        else:
            j = int(self.rng.integers(0, self.seen))
            if j < self.cap:
                self.items[j] = item


def collect(terrain, legs, driver_factory, stride: int, lighting=LIGHTING, autonomy: str = "autonomous",
            seed: int = 0, max_steps: Optional[int] = None, verbose: bool = False, cap: Optional[int] = None,
            rng: Optional[np.random.Generator] = None, stop_fail_share: Optional[float] = None,
            min_runs: int = 5) -> Dict[str, Any]:
    """Dataset over legs x lighting. driver_factory(env, expert) -> driver (the expert itself for round 0).
    cap: keep at most this many samples (reservoir over the whole call, drawn with `rng`); stop_fail_share: stop
    after a run once more than this share of the runs so far (at least `min_runs`) did not reach the goal. With
    neither, every recorded sample is kept in order. "rollout" in the result says what was seen, kept and skipped."""
    env = DriveEnv(terrain)
    expert = ExpertDriver(env)
    driver = driver_factory(env, expert)
    P, S, A, legs_info = [], [], [], []
    res = Reservoir(cap, rng if rng is not None else np.random.default_rng(seed)) if cap else None
    runs = failed = 0
    stopped = False
    t0 = time.time()
    for li, (name, a, b) in enumerate(legs):
        for sun in lighting:
            route = plan(terrain, a, b, sun)
            if route is None:
                continue
            (p, s, act), leg = drive(env, route, sun, driver, expert, stride, autonomy=autonomy,
                                     seed=seed + li, max_steps=max_steps, sink=res.add if res else None)
            P += p
            S += s
            A += act
            legs_info.append({"leg": name, "sun": "night" if sun == R.NIGHT else sun, **leg})
            runs += 1
            failed += not leg.get("reached")
            if stop_fail_share is not None and runs >= min_runs and failed > stop_fail_share * runs:
                stopped = True
                break
        if verbose and (li + 1) % 5 == 0:
            print(f"    {li + 1}/{len(legs)} legs, {res.seen if res else len(A)} samples ({time.time() - t0:.0f} s)", flush=True)
        if stopped:
            break
    recorded = res.seen if res else len(A)
    if res is not None:
        P, S, A = ([it[i] for it in res.items] for i in range(3))
        res.items = []
    return {"patch": np.asarray(P, np.float16).reshape(-1, 3, PATCH, PATCH),
            "scalars": np.asarray(S, np.float32).reshape(-1, len(SCALAR_NAMES)),
            "act": np.asarray(A, np.float32).reshape(-1, 2), "legs": legs_info,
            "rollout": {"runs": runs, "planned_runs": len(legs) * len(lighting), "failed": failed,
                        "stopped_early": stopped, "recorded": recorded, "kept": len(A)}}


def merge(a, b):
    return {k: np.concatenate([a[k], b[k]]) for k in ("patch", "scalars", "act")} | {"legs": a.get("legs", []) + b.get("legs", [])}


def dataset_mb(data) -> float:
    return sum(data[k].nbytes for k in ("patch", "scalars", "act")) / 2 ** 20


def process_memory_mb() -> Dict[str, Optional[float]]:
    """Working set (RSS), its peak, and private bytes (commit) of this process in MiB; None where unknown."""
    try:
        import psutil
        m = psutil.Process().memory_info()
        return {"rss_mb": m.rss / 2 ** 20,
                "peak_rss_mb": m.peak_wset / 2 ** 20 if hasattr(m, "peak_wset") else None,
                "private_mb": m.private / 2 ** 20 if hasattr(m, "private") else None}
    except ImportError:
        pass
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                               "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
        k32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        if psapi.GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
            return {"rss_mb": c.WorkingSetSize / 2 ** 20, "peak_rss_mb": c.PeakWorkingSetSize / 2 ** 20,
                    "private_mb": c.PagefileUsage / 2 ** 20}
        return {"rss_mb": None, "peak_rss_mb": None, "private_mb": None}
    try:
        with open("/proc/self/statm") as f:
            rss = int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2 ** 20
    except OSError:
        rss = None
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    peak = peak / 2 ** 20 if platform.system() == "Darwin" else peak / 2 ** 10
    return {"rss_mb": rss, "peak_rss_mb": peak, "private_mb": None}


def _round_mem() -> Dict[str, Optional[float]]:
    return {k: (None if v is None else round(v, 1)) for k, v in process_memory_mb().items()}


def _mem_line(data) -> str:
    m = process_memory_mb()
    f = lambda v: "?" if v is None else f"{v:.0f}"
    return (f"dataset {len(data['act'])} samples, {dataset_mb(data):.0f} MB; process working set {f(m['rss_mb'])} MB "
            f"(peak {f(m['peak_rss_mb'])} MB), private {f(m['private_mb'])} MB")


def save_npz(path: str, data) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    np.savez_compressed(path, patch=data["patch"], scalars=data["scalars"], act=data["act"])


# ---------------------------------------------------------------------------------------------------------
# training
# ---------------------------------------------------------------------------------------------------------
def train(model, data, epochs: int = 10, batch: int = 256, lr: float = 1e-3, seed: int = 0, device: str = "cpu",
          max_steps: Optional[int] = None, verbose: bool = False) -> Dict[str, float]:
    import torch
    torch.manual_seed(seed)
    model.to(device).train()
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    P = torch.as_tensor(data["patch"])          # float16, shares the array; each mini-batch goes to float32 below
    S = torch.as_tensor(data["scalars"])
    A = torch.as_tensor(data["act"])
    n = len(A)
    g = torch.Generator().manual_seed(seed)
    steps, loss_v = 0, float("nan")
    for ep in range(epochs):
        perm = torch.randperm(n, generator=g)
        tot = 0.0
        for k in range(0, n, batch):
            idx = perm[k:k + batch]
            out = model(P[idx].to(device=device, dtype=torch.float32), S[idx].to(device))
            loss = torch.nn.functional.mse_loss(out, A[idx].to(device))
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += loss.item() * len(idx)
            steps += 1
            if max_steps and steps >= max_steps:
                break
        loss_v = tot / max(1, min(n, steps * batch) if max_steps else n)
        if verbose:
            print(f"    epoch {ep}: MSE {loss_v:.5f}", flush=True)
        if max_steps and steps >= max_steps:
            break
    model.eval()
    return {"mse": loss_v, "steps": steps}


# ---------------------------------------------------------------------------------------------------------
# evaluation: interventions per km and autonomy %
# ---------------------------------------------------------------------------------------------------------
def evaluate_driver(terrain, legs, make_driver, autonomies=("autonomous",), rtt_s: float = 4.0, lighting=LIGHTING,
                    seed: int = 0, max_steps: Optional[int] = None) -> Dict[str, Any]:
    """interventions/km and autonomy % = 1 - interventions * (RTT + recovery) / elapsed time, per autonomy level."""
    out = {}
    env = DriveEnv(terrain)
    for au in autonomies:
        drv = make_driver(env)
        n_int = km = t = 0.0
        reached = runs = 0
        for li, (name, a, b) in enumerate(legs):
            for sun in lighting:
                route = plan(terrain, a, b, sun)
                if route is None:
                    continue
                _, leg = drive(env, route, sun, drv, None, 1, autonomy=au, rtt_s=rtt_s, seed=seed + li,
                               record=False, max_steps=max_steps)
                n_int += leg["interventions"]
                km += leg["distance_m"] / 1000.0
                t += leg["time_s"]
                reached += bool(leg.get("reached"))
                runs += 1
        cost = n_int * R.intervention_cost_s(rtt_s)
        out[au] = {"runs": runs, "reached": reached, "km": km, "interventions": n_int,
                   "interventions_per_km": n_int / km if km else None,
                   "autonomy_pct": 100.0 * (1.0 - cost / t) if t else None, "time_h": t / 3600.0,
                   "rtt_s": rtt_s}
    return out


# ---------------------------------------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------------------------------------
def export_onnx(model, path: str, opset: int = 17) -> None:
    import torch
    model = model.to("cpu").eval()
    p = torch.zeros(1, 3, PATCH, PATCH)
    s = torch.zeros(1, len(SCALAR_NAMES))
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    kw = dict(input_names=["patch", "scalars"], output_names=["action"], opset_version=opset,
              dynamic_axes={"patch": {0: "n"}, "scalars": {0: "n"}, "action": {0: "n"}})
    import warnings
    try:
        with warnings.catch_warnings():         # the TorchScript exporter is deprecated but stable at opset 17
            warnings.simplefilter("ignore", DeprecationWarning)
            torch.onnx.export(model, (p, s), path, dynamo=False, **kw)
    except TypeError:                                   # older torch without the dynamo switch
        torch.onnx.export(model, (p, s), path, **kw)


def write_card(model, policy_id: str, out_dir: str, training: Dict[str, Any], evaluation: Dict[str, Any],
               n_check: int = 20, seed: int = 0) -> Dict[str, Any]:
    """<id>.onnx + <id>.json card + <id>.check.json (onnxruntime outputs; torch must agree to 1e-5)."""
    import onnxruntime as ort
    import torch
    onnx_path = os.path.join(out_dir, f"{policy_id}.onnx")
    export_onnx(model, onnx_path)
    rng = np.random.default_rng(seed)
    P = rng.uniform(-1, 1, (n_check, 3, PATCH, PATCH)).astype(np.float32)
    S = rng.uniform(-1, 1, (n_check, len(SCALAR_NAMES))).astype(np.float32)
    sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
    ort_out = sess.run(["action"], {"patch": P, "scalars": S})[0]
    with torch.no_grad():
        torch_out = model.to("cpu")(torch.as_tensor(P), torch.as_tensor(S)).numpy()
    err = float(np.max(np.abs(ort_out - torch_out)))
    if err > 1e-5:
        raise AssertionError(f"ONNX and torch disagree by {err:g}")
    with open(onnx_path, "rb") as f:
        sha = hashlib.sha256(f.read()).hexdigest()
    card = {
        "format": "lunarsim-policy", "version": 1, "kind": "cnn", "id": policy_id, "env": ENV_ID, "env_version": ENV_VERSION,
        "onnx": os.path.basename(onnx_path), "onnx_sha256": sha, "opset": 17,
        "input": {"patch": {"shape": [3, PATCH, PATCH], "dtype": "float32", "channels": PATCH_CHANNELS,
                            "layout": "rows = forward (row 0 is 8 cells behind the rover), columns = left..right, 5 m cells",
                            "normalisation": "height - rover height / 10 m; slope / 20 deg; roughness / 1 m; clipped to +-10"},
                  "scalars": {"shape": [len(SCALAR_NAMES)], "names": SCALAR_NAMES, "dtype": "float32",
                              "normalisation": "speed / v_cap; heading error / pi; distance to waypoint / 100 m (<= 10); "
                                               "sun azimuth relative / 180 deg (0 at night); shadow flag"}},
        "output": {"name": "action", "names": ["steer_rate_cmd", "throttle"], "low": [-1.0, -1.0], "high": [1.0, 1.0]},
        "runtime": {"python": "onnxruntime", "browser": "onnxruntime-web", "torch_onnx_max_abs_err": err},
        "training": training, "evaluation": evaluation,
        "card": {"title": "Behaviour-cloned rover driver (PilotNet-style CNN, DAgger against the scripted expert)",
                 "intended_use": "stochastic generator of driving times / interventions for the LunarSim driving tables",
                 "limitations": "trained on one terrain pack; kinematic rover on 5 m LOLA heights (90 % interpolated); "
                                "lighting is a speed/shadow model, not imagery; interventions are rule-based (env.py)"},
    }
    with open(os.path.join(out_dir, f"{policy_id}.json"), "w", encoding="utf-8") as f:
        json.dump(card, f, indent=1)
    with open(os.path.join(out_dir, f"{policy_id}.check.json"), "w", encoding="utf-8") as f:
        json.dump({"format": "lunarsim-policy-check", "version": 1, "policy": policy_id, "tolerance": 1e-5,
                   "patch": P.tolist(), "scalars": S.tolist(), "action": ort_out.astype(float).tolist(),
                   "note": "action = onnxruntime (CPU) on the inputs; torch agrees to 1e-5"}, f)
    return card


# ---------------------------------------------------------------------------------------------------------
def run(site: str, policy_id: str, n_legs: int = 20, stride: int = 5, dagger: int = 3, epochs: int = 10,
        dagger_epochs: int = 5, seed: int = 0, out_dir: str = os.path.join("data", "policies"),
        run_root: str = os.path.join("runs", "rover"), eval_legs: int = 6, max_steps: Optional[int] = None,
        verbose: bool = True, dagger_steps_cap: Optional[int] = 20_000,
        dagger_stop_fail: Optional[float] = 0.5) -> Dict[str, Any]:
    import torch
    from ..terrain import Terrain
    torch.set_num_threads(max(1, (os.cpu_count() or 2) // 2))
    t_all = time.time()
    terrain = Terrain(site)
    legs = leg_list(terrain, n_legs, seed)
    dev = device_name()
    run_dir = os.path.join(run_root, policy_id)
    os.makedirs(run_dir, exist_ok=True)
    if verbose:
        print(f"{len(legs)} legs x {len(LIGHTING)} lighting cases on {site}; device {dev}", flush=True)
    data = collect(terrain, legs, lambda env, ex: ex, stride, seed=seed, max_steps=max_steps, verbose=verbose)
    model = make_model()
    hist = [{"round": 0, "samples": int(len(data["act"])), **train(model, data, epochs, seed=seed, device=dev, verbose=verbose)}]
    hist[-1].update({"dataset_mb": round(dataset_mb(data), 1), **_round_mem()})
    if verbose:
        print(f"  round 0: {_mem_line(data)}", flush=True)
    for k in range(1, dagger + 1):
        new = collect(terrain, legs, lambda env, ex: TorchDriver(model, dev), stride, seed=seed + 1000 * k,
                      max_steps=max_steps, verbose=False, cap=dagger_steps_cap,
                      rng=np.random.default_rng(seed + 1000 * k), stop_fail_share=dagger_stop_fail)
        ro = new["rollout"]
        interventions = float(sum(l["interventions"] for l in new["legs"]))
        data = merge(data, new)
        del new
        hist.append({"round": k, "samples": int(len(data["act"])), "rollout_interventions": interventions,
                     "rollout": ro, **train(model, data, dagger_epochs, seed=seed + k, device=dev)})
        hist[-1].update({"dataset_mb": round(dataset_mb(data), 1), **_round_mem()})
        if verbose:
            print(f"  DAgger round {k}: {ro['runs']}/{ro['planned_runs']} runs, {ro['failed']} did not reach the goal"
                  f"{' (round stopped early)' if ro['stopped_early'] else ''}; recorded {ro['recorded']}, kept "
                  f"{ro['kept']}; rollout interventions {interventions:.0f}, MSE {hist[-1]['mse']:.5f}", flush=True)
            print(f"  round {k}: {_mem_line(data)}", flush=True)
    save_npz(os.path.join(run_dir, "dataset.npz"), data)
    torch.save(model.state_dict(), os.path.join(run_dir, "model.pt"))
    ev_legs = leg_list(terrain, eval_legs, seed + 77)
    evaluation = {
        "learned": evaluate_driver(terrain, ev_legs, lambda env: TorchDriver(model.to("cpu"), "cpu"),
                                   autonomies=("autonomous", "supervised"), max_steps=max_steps),
        "expert": evaluate_driver(terrain, ev_legs, lambda env: ExpertDriver(env), autonomies=("autonomous", "supervised"),
                                  max_steps=max_steps),
        "legs": [l[0] for l in ev_legs], "lighting": ["night" if s == R.NIGHT else s for s in LIGHTING],
    }
    training = {"algo": "BC + DAgger (MSE on expert actions)", "terrain": site, "legs": len(legs), "stride": stride,
                "dagger_rounds": dagger, "epochs": epochs, "dagger_epochs": dagger_epochs, "seed": seed, "device": dev,
                "dagger_steps_cap": dagger_steps_cap, "dagger_stop_fail": dagger_stop_fail,
                "torch_version": torch.__version__, "history": hist, "samples": int(len(data["act"])),
                "dataset": os.path.join(run_dir, "dataset.npz"), "wallclock_s": round(time.time() - t_all, 1),
                "python": platform.python_version(),
                "time": _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat()}
    card = write_card(model, policy_id, out_dir, training, evaluation)
    return {"card": card, "run_dir": run_dir}


def main(argv=None):
    p = argparse.ArgumentParser(description="behaviour-cloned rover driver with DAgger, ONNX export")
    p.add_argument("--site", default="connecting_ridge")
    p.add_argument("--id", default="rover_bc_s0")
    p.add_argument("--legs", type=int, default=20, help="legs sampled from sites.json (0 = all)")
    p.add_argument("--stride", type=int, default=5)
    p.add_argument("--dagger", type=int, default=3)
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--dagger-epochs", type=int, default=5)
    p.add_argument("--dagger-steps-cap", type=int, default=20_000,
                   help="per DAgger round: keep at most N recorded rollout samples (reservoir; 0 = no cap)")
    p.add_argument("--dagger-stop-fail", type=float, default=0.5,
                   help="stop a DAgger round once more than this share of its runs did not reach the goal (< 0: never)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--eval-legs", type=int, default=6)
    p.add_argument("--max-steps", type=int, default=None, help="cap steps per drive (smoke runs)")
    p.add_argument("--out-dir", default=os.path.join("data", "policies"))
    p.add_argument("--run-root", default=os.path.join("runs", "rover"))
    a = p.parse_args(argv)
    r = run(a.site, a.id, a.legs, a.stride, a.dagger, a.epochs, a.dagger_epochs, a.seed, a.out_dir, a.run_root,
            a.eval_legs, a.max_steps, dagger_steps_cap=a.dagger_steps_cap or None,
            dagger_stop_fail=None if a.dagger_stop_fail < 0 else a.dagger_stop_fail)
    ev = r["card"]["evaluation"]
    for who in ("learned", "expert"):
        for au, v in ev[who].items():
            print(f"{who:8s} {au:10s} interventions/km {v['interventions_per_km']:.3f}  autonomy {v['autonomy_pct']:.2f} %  "
                  f"reached {v['reached']}/{v['runs']}")
    print(f"wrote {os.path.join(a.out_dir, a.id)}.{{onnx,json,check.json}}; run dir {r['run_dir']}")


if __name__ == "__main__":
    main()
