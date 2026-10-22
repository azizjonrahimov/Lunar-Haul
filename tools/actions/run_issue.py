"""The run queue on GitHub Actions (B-37): parse a run-request issue form strictly, run lunarsim, write the outputs.

    python tools/actions/run_issue.py --body-file tools/actions/sample_issue.md --issue 0 --out out   # dry run
    python tools/actions/run_issue.py --body-env ISSUE_BODY --issue "$ISSUE_NUMBER" --out out          # the workflow

The issue form is .github/ISSUE_TEMPLATE/run-scenario.yml; GitHub renders it as "### <label>" sections. Parsing is
strict: every heading must be a known label, appear once and carry an allowed value (choices from fixed lists, numbers
inside fixed ranges); anything else (an edited body, an extra section, a path, code, a value out of range) rejects the
request with a message and exit code 2. The free-text purpose is never interpreted: it is truncated, escaped and only
echoed in the comment. Nothing from the issue reaches a shell (the workflow passes the body through an environment
variable).

Outputs in --out:
    assets/summary.json        request, effective scenario (full form) and its sha256, per-seed engine summaries,
                               mean and 95 % CI of the headline metrics, provenance (the service's block: engine
                               version, git sha, dirty flag, lock sha, python, platform; data file shas)
    assets/trace_seed0.json.gz the seed-0 trace (v2 with terrain on, else v1)
    assets/scene.tar.gz        the seed-0 scene package (lunarsim-scene v1; terrain on only)
    comment.md                 the issue comment (summary table, links)
    release_notes.md           the release text
    error.md                   only when the request is rejected
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import math
import os
import re
import sys
import tarfile
import time
from typing import Any, Dict, List, Optional, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

# label in the form -> field id; the order is the form's
LABELS = {
    "Phase": "phase",
    "Fleet preset": "fleet",
    "Job rule": "mechanism",
    "Terrain and Phase-3 models": "terrain",
    "Pad standoff (km)": "pad_standoff_km",
    "Plume keep-out radius (km)": "keepout_km",
    "Night share of each lunar day": "night_fraction",
    "Round-trip delay (s)": "rtt_s",
    "Operators on console": "n_operators",
    "Earth link": "comms",
    "Supervised driving policy": "supervised_policy",
    "Seeds": "seeds",
    "Purpose": "purpose",
}
CHOICES = {
    "phase": ("P1", "P2", "P3"),
    "fleet": ("phase default", "P2: 2 vehicles", "P2: 4 vehicles", "P2: 6 vehicles", "P2: 8 vehicles"),
    "mechanism": ("marketplace", "pooled_greedy", "inhouse", "central_assign"),
    "terrain": ("on", "off"),
    "pad_standoff_km": ("0.5", "1", "2", "3", "5"),
    "keepout_km": ("none", "0.5", "1", "2"),
    "comms": ("off", "always", "dte", "dte+relay 0.5", "dte+relay 0.8", "dte+relay 0.9", "dte + BASE mast"),
    "supervised_policy": ("strict", "strategic", "strategic+avoid"),
}
RANGES = {"night_fraction": (0.0, 0.5, float), "rtt_s": (0.0, 30.0, float), "n_operators": (1, 20, int),
          "seeds": (1, 30, int)}
OPTIONAL = {"purpose"}
NO_RESPONSE = "_No response_"
PURPOSE_MAX = 500
STANDDOWN_H = 0.5                 # plume stand-down per landing (as the committed samples)
HEADLINE = ("delivered_kg", "delay_prio1_p90_h", "delay_prio1_mean_h", "sl24_prio1", "cost_per_landed_kg_usd",
            "utilisation", "jobs", "blackout_wait_vehicle_h", "operator_peak_demand")
_NUM = re.compile(r"^[0-9]+(\.[0-9]+)?$")


class Rejected(ValueError):
    pass


def parse_body(body: str) -> Dict[str, Any]:
    """The request from an issue-form body; raises Rejected with a reason."""
    if not isinstance(body, str) or len(body) > 20000:
        raise Rejected("the issue body is missing or too long")
    sections: Dict[str, List[str]] = {}
    current = None
    for line in body.replace("\r\n", "\n").split("\n"):
        if line.startswith("### "):
            label = line[4:].strip()
            if label not in LABELS:
                raise Rejected(f"unknown section {label[:60]!r}: only the form's fields are accepted")
            if LABELS[label] in sections:
                raise Rejected(f"section {label!r} appears twice")
            current = LABELS[label]
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
        elif line.strip():
            raise Rejected("text before the first form section")
    req: Dict[str, Any] = {}
    for label, fid in LABELS.items():
        if fid not in sections:
            if fid in OPTIONAL:
                req[fid] = ""
                continue
            raise Rejected(f"missing field {label!r}")
        text = "\n".join(sections[fid]).strip()
        if fid == "purpose":
            req[fid] = "" if text == NO_RESPONSE else text[:PURPOSE_MAX]
            continue
        if "\n" in text:
            raise Rejected(f"field {label!r} must be a single value")
        if fid in CHOICES:
            if text not in CHOICES[fid]:
                raise Rejected(f"field {label!r}: {text[:40]!r} is not one of {', '.join(CHOICES[fid])}")
            req[fid] = text
        else:
            lo, hi, typ = RANGES[fid]
            if not _NUM.match(text) or (typ is int and "." in text):
                raise Rejected(f"field {label!r}: {text[:40]!r} is not a {'whole ' if typ is int else ''}number")
            v = typ(text)
            if not lo <= v <= hi:
                raise Rejected(f"field {label!r}: {v} is outside {lo}-{hi}")
            req[fid] = v
    if req["fleet"] != "phase default" and req["phase"] != "P2":
        raise Rejected("fleet presets other than 'phase default' exist for P2 only")
    if req["terrain"] == "off" and (req["keepout_km"] != "none"):
        raise Rejected("a plume keep-out needs the terrain models on")
    return req


def scenario_from_request(req: Dict[str, Any], horizon_h: Optional[float] = None):
    """(effective Scenario, mechanism name, mechanism kwargs)."""
    from lunarsim.config import library, split_rtt
    lib = library()
    name = f"{req['phase']}-default" if req["fleet"] == "phase default" else f"P2-{req['fleet'].split()[1]}-vehicles"
    sc = lib[name]
    ow, gd = split_rtt(float(req["rtt_s"]), sc.ground_delay_s)
    kw: Dict[str, Any] = {"night_fraction": float(req["night_fraction"]), "one_way_latency_s": ow, "ground_delay_s": gd,
                          "n_operators": int(req["n_operators"]), "name": f"issue-{name}"}
    if horizon_h is not None:
        kw["horizon_h"] = float(horizon_h)
    if req["terrain"] == "on":
        kw.update({"terrain": "connecting_ridge", "pad_standoff_km": req["pad_standoff_km"],
                   "autonomy_model": "driving-v1",
                   "landing_model": {"policy": "classical", "sigma_scale": 1.0, "pad_radius_m": 50.0, "failure_policy": "lose"}})
        if req["keepout_km"] != "none":
            kw["plume"] = {"keepout_km": float(req["keepout_km"]), "standdown_h": STANDDOWN_H, "shelter": "auto"}
    c = req["comms"]
    if c != "off":
        comms: Dict[str, Any] = {"supervised_policy": req["supervised_policy"]}
        if c == "always":
            comms["mode"] = "always"
        elif c.startswith("dte+relay"):
            comms.update(mode="dte+relay", relay={"coverage": float(c.split()[1]), "gap_model": "parametric"})
        elif c == "dte + BASE mast":
            comms.update(mode="dte", mast={"site": "BASE", "height_m": 10.0, "range_km": 10.0})
        else:
            comms["mode"] = "dte"
        kw["comms"] = comms
    return sc.with_(**kw), req["mechanism"]


def _mech(name):
    from lunarsim.cli import _mechanism
    return _mechanism(name)


def provenance(sc) -> Dict[str, Any]:
    """The service's provenance block (service/provenance.py) plus the data files this scenario reads."""
    from service import provenance as SP
    from service.util import sha256_file
    p = SP.as_dict(SP.collect(ROOT))
    p["data_shas"] = SP.policy_shas(sc, ROOT)
    if sc.comms and sc.comms.get("mode") != "always":
        for rel in ("data/comms/connecting_ridge/earth_link-v1.json", "data/comms/connecting_ridge/earth_link-v1-samples.json.gz"):
            p["data_shas"][rel] = sha256_file(os.path.join(ROOT, rel))
    p["runner"] = {"github_run_id": os.environ.get("GITHUB_RUN_ID"), "github_sha": os.environ.get("GITHUB_SHA")}
    return p


def ci95(x) -> float:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    return float(1.96 * x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else float("nan")


def _clean(v):
    if isinstance(v, (np.floating, float)):
        return None if not math.isfinite(float(v)) else float(v)
    if isinstance(v, np.integer):
        return int(v)
    return v


def run_request(req: Dict[str, Any], issue: int, out: str, horizon_h: Optional[float] = None, log=print) -> Dict:
    from lunarsim.config import scenario_to_dict
    from lunarsim.engine import Simulation
    from service.util import canonical_json, sha256_bytes
    t0 = time.time()
    sc, mech_name = scenario_from_request(req, horizon_h)
    fn, mkw = _mech(mech_name)
    sc_dict = scenario_to_dict(sc)
    sc_text = canonical_json(sc_dict, ordered_keys=("landings_per_year",))
    os.makedirs(os.path.join(out, "assets"), exist_ok=True)
    rows, trace = [], None
    for seed in range(int(req["seeds"])):
        sim = Simulation(sc, fn, seed=seed, mech_kwargs=dict(mkw, trace=(seed == 0)))
        r = sim.run()
        rows.append({"seed": seed, **{k: _clean(v) for k, v in r.items()}})
        if seed == 0:
            trace = json.loads(json.dumps(sim.trace_export(mechanism=mech_name)))
        log(f"seed {seed}: delivered {r['delivered_kg'] / 1000:.1f} t, urgent p90 {r['delay_prio1_p90_h']:.1f} h")
    agg = {}
    for k in HEADLINE:
        vals = [r[k] for r in rows if r.get(k) is not None]
        if vals:
            agg[k] = {"mean": float(np.mean(vals)), "ci95": _clean(ci95(vals)), "n": len(vals)}
    files = ["summary.json", "trace_seed0.json.gz"]
    with open(os.path.join(out, "assets", "trace_seed0.json.gz"), "wb") as f:
        f.write(gzip.compress(json.dumps(trace, separators=(",", ":")).encode("utf-8"), 9, mtime=0))
    scene_note = "no scene package (terrain models off)"
    if trace.get("version") == 2:
        from lunarsim import scene as SCN
        sdir = os.path.join(out, "scene")
        SCN.build(trace, sdir)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz", format=tarfile.PAX_FORMAT) as tar:
            for name in sorted(os.listdir(sdir)):
                ti = tarfile.TarInfo(f"scene/{name}")
                data = open(os.path.join(sdir, name), "rb").read()
                ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
                tar.addfile(ti, io.BytesIO(data))
        with open(os.path.join(out, "assets", "scene.tar.gz"), "wb") as f:
            f.write(buf.getvalue())
        files.append("scene.tar.gz")
        scene_note = "scene package for the 3D world included"
    summary = {"format": "lunarsim-run", "version": 1, "issue": issue, "request": req,
               "scenario": sc_dict, "scenario_sha": sha256_bytes(sc_text), "mechanism": mech_name,
               "seeds": list(range(int(req["seeds"]))), "aggregate": agg, "rows": rows,
               "provenance": provenance(sc), "files": files, "wall_s": round(time.time() - t0, 1)}
    with open(os.path.join(out, "assets", "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=1)
    write_texts(summary, out, scene_note)
    return summary


def _escape(text: str) -> str:
    """Purpose text for the comment: no mentions, no HTML, no markdown structure; quoted line by line."""
    t = text.replace("@", "@​").replace("<", "&lt;").replace(">", "&gt;")
    t = re.sub(r"([\\`*_\[\]#|~])", r"\\\1", t)
    return "\n".join("> " + line for line in t.split("\n")) if t.strip() else "> (none given)"


def site_url(issue: int) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "azizjonrahimov/Lunar-Haul")
    owner, name = repo.split("/", 1)
    return f"https://{owner.lower()}.github.io/{name}/world/?run={issue}"


def release_url(issue: int) -> str:
    repo = os.environ.get("GITHUB_REPOSITORY", "azizjonrahimov/Lunar-Haul")
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    return f"{server}/{repo}/releases/tag/run-{issue}"


def write_texts(summary: Dict[str, Any], out: str, scene_note: str) -> None:
    req, agg, issue = summary["request"], summary["aggregate"], summary["issue"]
    fmt = {"delivered_kg": ("Delivered cargo (t / year)", 1e-3, 1), "delay_prio1_p90_h": ("Urgent delay, 90th percentile (h)", 1, 1),
           "delay_prio1_mean_h": ("Urgent delay, mean (h)", 1, 1), "sl24_prio1": ("Urgent items within 24 h (%)", 100, 1),
           "cost_per_landed_kg_usd": ("Cost per landed kg (USD)", 1, 0), "utilisation": ("Fleet utilisation (%)", 100, 1),
           "jobs": ("Trips per year", 1, 0), "blackout_wait_vehicle_h": ("Waiting for an Earth link (vehicle-h)", 1, 0),
           "operator_peak_demand": ("Peak operator demand (consoles)", 1, 2)}
    lines = [f"**Run for #{issue}** · {req['phase']} · {req['fleet']} · {req['mechanism']} · terrain {req['terrain']}"
             f" · Earth link {req['comms']} · {len(summary['seeds'])} seeds", "",
             "| Metric | Mean | 95 % CI (±) |", "|---|---|---|"]
    for k, (label, scale, d) in fmt.items():
        if k in agg:
            m, c = agg[k]["mean"] * scale, agg[k]["ci95"]
            lines.append(f"| {label} | {m:,.{d}f} | {'' if c is None else f'{c * scale:,.{d}f}'} |")
    prov = summary["provenance"]
    lines += ["", f"Purpose given:", _escape(req.get("purpose", "")), "",
              f"- Files: {release_url(issue)} ({', '.join(summary['files'])}); {scene_note}.",
              f"- Watch it in 3D: {site_url(issue)} (available after the site's next deploy, a few minutes).",
              f"- Provenance: lunarsim {prov.get('engine_version')} at {str(prov.get('git_sha'))[:12]}, scenario sha256 "
              f"{summary['scenario_sha'][:12]}, {len(prov.get('data_shas', {}))} data files hashed (summary.json).",
              f"- Wall time {summary['wall_s']} s."]
    with open(os.path.join(out, "comment.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(out, "release_notes.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(f"Outputs of the run requested in issue #{issue} (LunarHaul run queue). summary.json holds the request, the "
                f"effective scenario, every seed's summary and the provenance; trace_seed0.json.gz the seed-0 trace; "
                f"scene.tar.gz (when present) the 3D scene package.\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Run queue: parse an issue form, run lunarsim, write the outputs")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--body-file")
    src.add_argument("--body-env", help="name of the environment variable holding the issue body")
    ap.add_argument("--issue", type=int, required=True)
    ap.add_argument("--out", default="out")
    ap.add_argument("--parse-only", action="store_true")
    ap.add_argument("--max-seconds", type=float, default=3300.0, help="stop before the job's 60 min limit")
    a = ap.parse_args(argv)
    if a.max_seconds and a.max_seconds > 0:
        import faulthandler
        faulthandler.dump_traceback_later(a.max_seconds, exit=True)
    body = open(a.body_file, encoding="utf-8").read() if a.body_file else os.environ.get(a.body_env, "")
    os.makedirs(a.out, exist_ok=True)
    try:
        req = parse_body(body)
    except Rejected as e:
        with open(os.path.join(a.out, "error.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(f"The run request could not be accepted: {e}.\n\nPlease open a new issue with the "
                    f"'Run a scenario' form and leave its section headings unchanged.\n")
        print(f"rejected: {e}", file=sys.stderr)
        return 2
    print("request:", json.dumps(req))
    if a.parse_only:
        return 0
    s = run_request(req, a.issue, a.out)
    print(f"done: {len(s['rows'])} seeds in {s['wall_s']} s; files {s['files']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
