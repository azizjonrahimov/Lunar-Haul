"""Run inputs and the run executor.

`prepare()` turns a POST /v2/runs body into RunInputs: the effective full-form Scenario (request scenario
plus the Phase-3 options applied through Scenario.with_, exactly as lunarsim.cli does), its canonical
sha, the mechanism and its kwargs (lunarsim.server's lookup, so the service and `lunarsim serve` agree),
the seeds and the shas of every data file the engine will read. The API stores these; the worker
rebuilds the engine call from the stored JSON with `materialise()` so a replicate uses nothing but the
record.

The Worker polls the runs table, claims one queued run at a time (single UPDATE, so several workers can
share the database), executes lunarsim.engine.Simulation per seed in-process with a progress event per
seed, stores every trace as a content-addressed blob, writes the output document (rows + trace shas)
as a blob whose sha256 is the run's output_sha, aggregates the summary, settles the CPU-second quota
(estimate reserved at enqueue -> actual) and, for a replicate, compares output_sha with the parent.
"""
from __future__ import annotations

import json
import logging
import math
import os
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .db import Database
from .errors import ServiceError
from .settings import Settings
from .util import canonical_json, day_key, iso, sha256_bytes

log = logging.getLogger("service.worker")

PHASE3_OPTIONS = ("terrain", "pad_standoff_km", "landing_model", "plume", "autonomy_model")
OUTPUT_FORMAT = "lunarsim-run-output"
# Mappings whose key order the engine depends on (see util.canonical_json): the landing schedule is drawn by
# iterating landings_per_year, so {"CLPS":4,"MK1":3,"LARGE":1} and its sorted spelling are different scenarios.
SCENARIO_ORDERED_KEYS = ("landings_per_year",)


def scenario_text(sc_dict: Dict[str, Any]) -> str:
    """The canonical scenario JSON that is both hashed (scenario_sha) and stored (scenario_json)."""
    return canonical_json(sc_dict, ordered_keys=SCENARIO_ORDERED_KEYS).decode("utf-8")


@dataclass
class RunInputs:
    scenario: Any                              # lunarsim.scenario.Scenario (effective)
    scenario_dict: Dict[str, Any]              # full form v1 with Phase-3 fields, header first
    scenario_text: str                         # canonical JSON (what is stored and hashed)
    scenario_sha: str
    mechanism: str
    fn: Callable
    kwargs: Dict[str, Any]                     # mechanism kwargs (no trace flag)
    seeds: List[int]
    options: Dict[str, Any]                    # normalised request options (stored as options_json)
    policy_shas: Dict[str, str] = field(default_factory=dict)


def _wrap(e: Exception) -> ServiceError:
    """lunarsim.server.ApiError -> ServiceError (same status and message)."""
    status = getattr(e, "status", 400)
    return ServiceError(int(status), str(e))


def _normalise_options(options: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """(phase3 fields for Scenario.with_, request-level options to store). Validates shapes the engine
    would otherwise reject deep inside a run."""
    from lunarsim.server import _opts
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ServiceError(400, "'options' must be an object")
    known = set(PHASE3_OPTIONS) | {"opts"}
    bad = sorted(set(options) - known)
    if bad:
        raise ServiceError(400, f"unknown options {bad}. Known: {sorted(known)}")
    p3: Dict[str, Any] = {}
    for k in PHASE3_OPTIONS:
        v = options.get(k)
        if v is None:
            continue
        if k in ("terrain", "autonomy_model"):
            if not isinstance(v, str) or not v:
                raise ServiceError(400, f"options.{k} must be a non-empty string")
            if k == "autonomy_model" and v != "driving-v1" and (os.path.isabs(v) or ".." in v.replace("\\", "/").split("/")):
                raise ServiceError(400, "options.autonomy_model must be 'driving-v1' or a repo-relative table path")
        elif k == "pad_standoff_km":
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                v = (str(v).rstrip("0").rstrip(".") if "." in str(v) else str(v))
            if not isinstance(v, str) or not v:
                raise ServiceError(400, "options.pad_standoff_km must be a string key such as '2'")
        elif k == "landing_model":
            if not isinstance(v, dict):
                raise ServiceError(400, "options.landing_model must be an object {policy, sigma_scale, pad_radius_m, failure_policy}")
            d = v.get("dir")
            if d is not None and (not isinstance(d, str) or os.path.isabs(d) or ".." in d.replace("\\", "/").split("/")):
                raise ServiceError(400, "options.landing_model.dir must be a repo-relative folder")
        elif k == "plume":
            if not isinstance(v, dict) or not all(isinstance(v.get(x), (int, float)) for x in ("keepout_km", "standdown_h")):
                raise ServiceError(400, "options.plume must be {keepout_km, standdown_h[, shelter]}")
        p3[k] = v
    try:
        _opts(options.get("opts"))          # validates the marketplace flags (unknown keys, non-booleans)
    except Exception as e:  # ApiError
        raise _wrap(e)
    stored = {k: v for k, v in options.items() if v is not None}
    return p3, stored


def prepare(scenario: Any, mechanism: Any, seeds: Any, options: Any, repo_root: str, max_seeds: int) -> RunInputs:
    """Validate and normalise a run request (raises ServiceError with status 400 on any problem)."""
    from lunarsim.config import scenario_to_dict
    from lunarsim.server import _mechanism, _mech_kwargs, _scenario, _seeds, _opts
    from . import provenance
    try:
        sc, file_kw = _scenario(scenario)
        if not isinstance(mechanism, str):
            raise ServiceError(400, "'mechanism' must be a string")
        fn, base_kw = _mechanism(mechanism)
        seeds_list = _seeds(seeds)
    except ServiceError:
        raise
    except Exception as e:
        raise _wrap(e)
    if len(seeds_list) > max_seeds:
        raise ServiceError(400, f"at most {max_seeds} seeds per run (got {len(seeds_list)})")
    if len(set(seeds_list)) != len(seeds_list):
        raise ServiceError(400, "'seeds' must not repeat")
    p3, stored = _normalise_options(options)
    if p3:
        try:
            sc = sc.with_(**p3)
        except TypeError as e:
            raise ServiceError(400, f"invalid options: {e}")
    if isinstance(scenario, str):
        sc = sc.with_(name=scenario)
    try:
        mkw = _opts(stored.get("opts"))
    except Exception as e:
        raise _wrap(e)
    # A compact-form scenario carries marketplace flags (file_kw) that the full form loses; fold them into the
    # stored options so materialise() rebuilds the identical mechanism call from the record alone.
    effective = {**file_kw, **mkw} if mechanism.startswith("marketplace") else mkw
    if effective:
        stored["opts"] = effective
    else:
        stored.pop("opts", None)
    kwargs = _mech_kwargs(mechanism, base_kw, file_kw, mkw)
    sc_dict = scenario_to_dict(sc)
    text = scenario_text(sc_dict)
    sc_sha = sha256_bytes(text.encode("utf-8"))
    try:
        shas = provenance.policy_shas(sc, repo_root)
    except FileNotFoundError as e:
        raise ServiceError(400, f"the run needs a data file that is not on this server: {e}", "missing_data")
    return RunInputs(scenario=sc, scenario_dict=sc_dict, scenario_text=text, scenario_sha=sc_sha, mechanism=mechanism,
                     fn=fn, kwargs=kwargs, seeds=seeds_list, options=stored, policy_shas=shas)


def materialise(row: Dict[str, Any]) -> Tuple[Any, str, Callable, Dict[str, Any], List[int]]:
    """(Scenario, mechanism name, fn, kwargs, seeds) from a stored runs row."""
    from lunarsim.config import scenario_from_dict_ex
    from lunarsim.server import _mechanism, _mech_kwargs, _opts
    sc, _ = scenario_from_dict_ex(json.loads(row["scenario_json"]))
    name = row["mechanism"]
    fn, base_kw = _mechanism(name)
    options = json.loads(row["options_json"] or "{}")
    kwargs = _mech_kwargs(name, base_kw, {}, _opts(options.get("opts")))
    seeds = [int(s) for s in json.loads(row["seeds_json"])]
    return sc, name, fn, kwargs, seeds


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Per-metric mean/std/min/max/n over the per-seed rows (None and non-numbers skipped)."""
    keys: List[str] = []
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    out: Dict[str, Dict[str, Any]] = {}
    for k in keys:
        if k == "seed":
            continue
        xs = [float(r[k]) for r in rows if isinstance(r.get(k), (int, float)) and not isinstance(r.get(k), bool)
              and math.isfinite(float(r[k]))]
        if not xs:
            continue
        n = len(xs)
        mean = sum(xs) / n
        std = math.sqrt(sum((x - mean) ** 2 for x in xs) / (n - 1)) if n > 1 else 0.0
        out[k] = {"mean": mean, "std": std, "min": min(xs), "max": max(xs), "n": n}
    return out


class Worker:
    def __init__(self, settings: Settings, db: Optional[Database] = None):
        self.s = settings
        self.db = db or Database(settings.db_path)
        self.id = settings.worker_id
        self._stop = False

    # ------------------------------------------------------------------ loop
    def run_forever(self) -> None:
        requeued = self.db.requeue_stale(self.s.worker_stale_s)
        if requeued:
            log.warning("re-queued %d stale running run(s): %s", len(requeued), ", ".join(requeued))
        log.info("worker %s polling %s every %.1fs", self.id, self.db.path, self.s.worker_poll_s)
        while not self._stop:
            try:
                if not self.run_once():
                    time.sleep(self.s.worker_poll_s)
            except KeyboardInterrupt:
                break
            except Exception:  # keep the loop alive; the run itself is marked failed inside execute()
                log.exception("worker loop error")
                time.sleep(self.s.worker_poll_s)

    def stop(self) -> None:
        self._stop = True

    def run_once(self) -> bool:
        """Claim and execute one queued run; False when the queue is empty."""
        row = self.db.claim_run(self.id)
        if row is None:
            return False
        self.execute(dict(row))
        return True

    # ------------------------------------------------------------------ one run
    def execute(self, row: Dict[str, Any]) -> None:
        from lunarsim.server import clean
        from . import provenance
        run_id = row["id"]
        t_wall0 = time.perf_counter()
        t_cpu0 = time.process_time()
        quota_key = row["user_id"] or row["anon_key"]
        estimate = float(row["cpu_s"] or 0.0)
        day = row["created"][:10] if row["created"] else day_key()
        try:
            prov = provenance.collect(self.s.repo_root, refresh=True)
            if prov.patch:
                self.db.put_blob(self.s.data_dir, prov.patch, "text/x-diff", prov.patch_sha)  # type: ignore[arg-type]
            self.db.put_blob(self.s.data_dir, prov.lock, "text/plain", prov.lock_sha)
            self.db.update_run(run_id, **prov.columns())
            sc, name, fn, kwargs, seeds = materialise(row)
            self.db.add_event(run_id, "running", {"worker": self.id, "seeds": len(seeds),
                                                  "engine_version": prov.engine_version, "git_sha": prov.git_sha,
                                                  "git_dirty": prov.git_dirty})
            cwd = os.getcwd()
            rows: List[Dict[str, Any]] = []
            traces: Dict[str, str] = {}
            try:
                os.chdir(self.s.repo_root)          # data/ paths inside lunarsim.phase3 are repo-relative
                from lunarsim.engine import Simulation
                t_cpu0 = time.process_time()        # charge the engine, not the provenance/import work above
                for i, seed in enumerate(seeds):
                    t0 = time.perf_counter()
                    sim = Simulation(sc, fn, seed=seed, mech_kwargs=dict(kwargs, trace=True))
                    sim.run()
                    trace = clean(sim.trace_export(mechanism=name))
                    tb = canonical_json(trace)
                    tsha = sha256_bytes(tb)
                    self.db.put_blob(self.s.data_dir, tb, "application/json", tsha)
                    traces[str(seed)] = tsha
                    summary = dict(trace.get("summary") or {})
                    summary["seed"] = seed
                    rows.append(summary)
                    self.db.add_event(run_id, "progress", {"done": i + 1, "total": len(seeds), "seed": seed,
                                                           "trace_sha": tsha,
                                                           "ms": round(1000 * (time.perf_counter() - t0))})
            finally:
                os.chdir(cwd)
            output = {"format": OUTPUT_FORMAT, "version": 1, "scenario_sha": row["scenario_sha"],
                      "mechanism": name, "seeds": seeds, "rows": rows, "traces": traces}
            ob = canonical_json(output)
            osha = sha256_bytes(ob)
            self.db.put_blob(self.s.data_dir, ob, "application/json", osha)
            cpu_s = max(0.0, time.process_time() - t_cpu0)
            wall_s = time.perf_counter() - t_wall0
            summary_doc = {"format": "lunarsim-run-summary", "version": 1, "scenario": sc.name, "mechanism": name,
                           "n_seeds": len(seeds), "seeds": seeds, "metrics": aggregate(rows), "rows": rows,
                           "traces": traces, "output_sha": osha, "cpu_s": round(cpu_s, 3), "wall_s": round(wall_s, 3),
                           "engine_version": prov.engine_version}
            self.db.update_run(run_id, status="done", finished=iso(), output_sha=osha, cpu_s=round(cpu_s, 3),
                               summary_json=json.dumps(clean(summary_doc), allow_nan=False, separators=(",", ":")))
            if quota_key:
                self.db.quota_add(quota_key, day, cpu_s - estimate)
            payload = {"output_sha": osha, "cpu_s": round(cpu_s, 3), "wall_s": round(wall_s, 3), "n_seeds": len(seeds),
                       "metrics": {k: v["mean"] for k, v in summary_doc["metrics"].items()}}
            replicated = self._settle_replication(row, osha)
            if replicated is not None:
                payload["replicated"] = replicated
            self.db.add_event(run_id, "done", clean(payload))
            log.info("run %s done: %d seed(s), %.2f cpu-s, output %s", run_id, len(seeds), cpu_s, osha[:12])
        except Exception as e:
            cpu_s = max(0.0, time.process_time() - t_cpu0)
            err = f"{type(e).__name__}: {e}"
            log.error("run %s failed: %s\n%s", run_id, err, traceback.format_exc())
            self.db.update_run(run_id, status="failed", finished=iso(), error=err[:2000], cpu_s=round(cpu_s, 3))
            if quota_key:
                self.db.quota_add(quota_key, day, cpu_s - estimate)
            self.db.add_event(run_id, "failed", {"error": err[:2000], "code": "engine_error", "cpu_s": round(cpu_s, 3)})

    def _settle_replication(self, row: Dict[str, Any], output_sha: str) -> Optional[bool]:
        """For a replicate: compare with the parent's output sha and record the verdict on both runs."""
        parent_id = row.get("parent_run_id")
        if not parent_id:
            return None
        parent = self.db.get_run(parent_id)
        if parent is None or parent["status"] != "done" or not parent["output_sha"]:
            self.db.add_event(row["id"], "replicated", {"replicated": None, "parent_run_id": parent_id,
                                                        "reason": "parent has no finished output"})
            return None
        same = bool(parent["output_sha"] == output_sha)
        payload = {"replicated": same, "parent_run_id": parent_id, "child_run_id": row["id"],
                   "output_sha": output_sha, "parent_output_sha": parent["output_sha"]}
        self.db.update_run(row["id"], replicated=int(same))
        self.db.update_run(parent_id, replicated=int(same))
        self.db.add_event(row["id"], "replicated", payload)
        self.db.add_event(parent_id, "replicated", payload)
        return same
