"""Interchange formats: lunarsim-trace v1 (and, from B-2, lunarsim-scenario v1)."""
import copy, glob, json, os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pytest

from lunarsim import dispatch, Scenario, Simulation
from lunarsim.formats import validate_trace, load_schema, TRACE_CARGO_COLUMNS


@pytest.fixture(scope="module")
def trace():
    sc = Scenario(name="fmt-test",
                  fleet=[("NASA", "LTV", "supervised", "A"), ("CoA", "HAUL", "supervised", "A")])
    sim = Simulation(sc, dispatch.marketplace, seed=2, mech_kwargs={"trace": True})
    sim.run()
    # round-trip through JSON exactly as `lunarsim trace` writes it
    return json.loads(json.dumps(sim.trace_export()))


def test_trace_header(trace):
    assert trace["format"] == "lunarsim-trace" and trace["version"] == 1
    assert trace["engine"] == "python"
    assert trace["scenario"] == "fmt-test" and trace["mechanism"] == "marketplace" and trace["seed"] == 2
    assert trace["cargo_columns"] == TRACE_CARGO_COLUMNS
    assert all(len(r) == len(TRACE_CARGO_COLUMNS) for r in trace["cargo"])


def test_trace_validates(trace):
    assert trace["jobs"] and trace["cargo"]
    assert validate_trace(trace) == []


def test_mechanism_override():
    sc = Scenario(horizon_h=200.0, fleet=[("NASA", "LTV", "supervised", "A")])
    sim = Simulation(sc, dispatch.central_assign, seed=1, mech_kwargs={"trace": True, "batch_h": 1.0})
    sim.run()
    assert sim.trace_export()["mechanism"] == "central_assign"
    assert sim.trace_export(mechanism="my-name")["mechanism"] == "my-name"


@pytest.mark.parametrize("breakage", [
    lambda d: d.pop("jobs"),
    lambda d: d.update(format="something-else"),
    lambda d: d.update(version=2),
    lambda d: d.update(horizon_h="8760"),
    lambda d: d["cargo"][0].pop(),                         # row shorter than cargo_columns
    lambda d: d["cargo"][0].__setitem__(10, 2),            # stranded must be 0/1
    lambda d: d["jobs"][0]["segments"][0].pop(),           # segment of 4
    lambda d: d["jobs"][0]["segments"][0].__setitem__(2, "t"),
    lambda d: d["jobs"][0].pop("t1"),
    lambda d: d["vehicles"][0].pop("capacity"),
    lambda d: d.update(cargo_columns=list(reversed(TRACE_CARGO_COLUMNS))),
    lambda d: d["summary"].update(bad="x"),
])
def test_broken_trace_rejected(trace, breakage):
    d = copy.deepcopy(trace)
    breakage(d)
    assert validate_trace(d), "expected at least one error"


def test_extra_appended_column_ok(trace):
    d = copy.deepcopy(trace)
    d["cargo_columns"] = d["cargo_columns"] + ["t_landed"]
    for r in d["cargo"]:
        r.append(None)
    assert validate_trace(d) == []


SAMPLES = sorted(glob.glob(os.path.join(ROOT, "data", "sample_traces", "*.json")))


def _trace_version(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f).get("version", 1)


SAMPLES_V1 = [p for p in SAMPLES if _trace_version(p) == 1]
SAMPLES_V2 = [p for p in SAMPLES if _trace_version(p) == 2]


TRACE_HEADER = ("format", "version", "engine", "scenario", "mechanism", "seed", "cargo_columns")
SCENARIO_HEADER = ("format", "version", "form")


def _strip(d, keys):
    """A pre-v1 (legacy) copy of a v1 document: the same content without the header keys."""
    return {k: v for k, v in d.items() if k not in keys}


@pytest.mark.parametrize("path", SAMPLES_V1, ids=os.path.basename)
def test_sample_traces_are_v1(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    assert (d["format"], d["version"]) == ("lunarsim-trace", 1)
    assert validate_trace(d) == []


@pytest.mark.parametrize("path", SAMPLES_V2, ids=os.path.basename)
def test_sample_traces_v2_validate(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    assert (d["format"], d["version"]) == ("lunarsim-trace", 2)
    assert validate_trace(d) == []


@pytest.mark.parametrize("path", SAMPLES_V1, ids=os.path.basename)
def test_legacy_traces_accepted(path):
    with open(path, encoding="utf-8") as f:
        legacy = _strip(json.load(f), TRACE_HEADER)
    assert "format" not in legacy and "cargo_columns" not in legacy
    assert validate_trace(legacy) == []      # no header: read as v1 with the default cargo columns


def test_trace_schema_is_valid_json_and_lists_required_keys():
    s = load_schema("trace-v1")
    assert s["$schema"].endswith("2020-12/schema")
    assert set(s["required"]) == {"horizon_h", "nights", "landings", "vehicles", "jobs", "cargo"}


def test_trace_matches_schema_if_jsonschema_installed(trace):
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator(load_schema("trace-v1")).validate(trace)


# ---------------------------------------------------------------------------
# lunarsim-scenario v1
# ---------------------------------------------------------------------------
from lunarsim import BulkFlow
from lunarsim.config import (scenario_to_dict, scenario_from_dict, scenario_from_dict_ex, load_scenario_ex,
                             save_scenario, load_scenario, split_rtt, marketplace_kwargs)
from lunarsim.formats import validate_scenario

SCENARIO_FILES = sorted(glob.glob(os.path.join(ROOT, "data", "scenarios", "*.json")))
OWNERS = ["NASA", "NASA", "NASA", "NASA", "CoA", "CoA", "CoB", "CoC"]


@pytest.fixture
def in_root(monkeypatch):
    monkeypatch.chdir(ROOT)          # (historical: compact form used to need the repo root)
    monkeypatch.syspath_prepend(ROOT)


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=os.path.basename)
def test_data_scenarios_load_and_validate(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    assert validate_scenario(d) == []
    sc, kw = load_scenario_ex(path)
    assert kw == {} and sc.name == os.path.basename(path)[:-5]


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=os.path.basename)
def test_full_round_trip(path, tmp_path):
    sc = load_scenario(path)
    d = scenario_to_dict(sc)
    assert (d["format"], d["version"], d["form"]) == ("lunarsim-scenario", 1, "full")
    assert scenario_from_dict(json.loads(json.dumps(d))) == sc
    save_scenario(sc, str(tmp_path / "x.json"))
    assert load_scenario(str(tmp_path / "x.json")) == sc


def test_unknown_full_field_raises():
    with pytest.raises(ValueError, match="unknown scenario fields"):
        scenario_from_dict({"name": "x", "nigth_fraction": 0.1})
    with pytest.raises(ValueError, match="unsupported scenario version"):
        scenario_from_dict({"format": "lunarsim-scenario", "version": 2, "name": "x"})
    with pytest.raises(ValueError, match="not a scenario file"):
        scenario_from_dict({"format": "lunarsim-trace", "name": "x"})
    assert validate_scenario({"name": "x", "nigth_fraction": 0.1})


COMPACT = {"format": "lunarsim-scenario", "version": 1, "form": "compact", "name": "lunarsim-live",
           "phase": "P2", "bulk_t_per_year": 500,
           "fleet": [{"owner": "NASA", "cls": "LTV", "autonomy": "supervised", "std": "A"},
                     {"owner": "CoA", "cls": "LTV", "autonomy": "supervised", "std": "A"},
                     {"owner": "CoA", "cls": "HAUL", "autonomy": "supervised", "std": "A"},
                     {"owner": "CoB", "cls": "MICRO", "autonomy": "teleop", "std": "A"}],
           "night_fraction": 0.15, "rtt_s": 5.0, "n_operators": 3, "other_duty_share": 0.3,
           "mtbf_mult": 1.0, "common_standard_share": 1.0,
           "marketplace": {"bundling": True, "consolidate": True, "team_lift": True, "night_aware": True,
                           "anticipate": True, "backhaul": True, "priority": True}}


def test_compact_matches_makeScenario(in_root):
    """Expected values written out by hand from web/sim.js makeScenario({phase: P2, bulkT: 500, rtt: 5, ...})."""
    assert validate_scenario(COMPACT) == []
    sc, kw = scenario_from_dict_ex(COMPACT)
    expected = Scenario(
        name="lunarsim-live", horizon_h=8760.0,
        landings_per_year={"CLPS": 4, "MK1": 3, "LARGE": 1}, cargo_owners=OWNERS,
        bulk_flows=[BulkFlow("CONSTR", "BASE", 300.0, 1000, "NASA", 3), BulkFlow("CONSTR", "ISRU", 200.0, 1000, "NASA", 3)],
        fleet=[("NASA", "LTV", "supervised", "A"), ("CoA", "LTV", "supervised", "A"),
               ("CoA", "HAUL", "supervised", "A"), ("CoB", "MICRO", "teleop", "A")],
        night_fraction=0.15, night_speed_mult=0.6, one_way_latency_s=1.3, ground_delay_s=2.4,
        n_operators=3, supervised_fanout=4, failures=True, mtbf_mult=1.0,
        other_duty_share=0.3, other_duty_block_h=48.0, common_standard_share=1.0,
        operator_cost_per_h=1000.0, urgency_usd_per_h=2000.0, vot_usd_per_h={1: 5000.0, 2: 1000.0, 3: 100.0})
    assert sc == expected
    assert 2 * sc.one_way_latency_s + sc.ground_delay_s == 5.0
    assert kw == {"bundling": True, "consolidate": True, "team_lift": True, "night_aware": True,
                  "anticipate": True, "backhaul": True, "priority": True}


def test_compact_bulk_scaling_and_variants(in_root):
    # P3 has three flows (800/600/100, PSR at priority 2, lot 500); 750 t => scale 0.5
    d = {"phase": "P3", "bulk_t_per_year": 750, "fleet": [["NASA", "LTV", "autonomous", "A"]], "rtt_s": 2.0}
    sc, kw = scenario_from_dict_ex(d)          # no `form`: detected from `phase`
    assert [(b.origin, b.dest, b.tonnes_per_year, b.lot_kg, b.owner, b.priority) for b in sc.bulk_flows] == [
        ("CONSTR", "BASE", 400.0, 1000, "NASA", 3), ("CONSTR", "ISRU", 300.0, 1000, "NASA", 3),
        ("PSR", "ISRU", 50.0, 500, "NASA", 2)]
    assert sc.landings_per_year == {"CLPS": 4, "MK1": 4, "LARGE": 3} and sc.n_operators == 4   # phase defaults
    assert (sc.one_way_latency_s, sc.ground_delay_s) == (1.0, 0.0)                          # rtt below 2.4 s
    assert sc.name == "P3" and kw == {}
    assert scenario_from_dict(dict(d, bulk_t_per_year=0)).bulk_flows == []
    # short PLAN spellings map to the Python kwargs
    assert marketplace_kwargs({"team": False, "night": False}) == {"team_lift": False, "night_aware": False}
    with pytest.warns(UserWarning, match="no Python equivalent"):
        assert marketplace_kwargs({"telepathy": True}) == {}


def test_compact_unknown_field_raises(in_root):
    with pytest.raises(ValueError, match="unknown scenario fields"):
        scenario_from_dict(dict(COMPACT, horizon_days=10))
    with pytest.raises(ValueError, match="unknown phase"):
        scenario_from_dict(dict(COMPACT, phase="P9"))
    assert validate_scenario(dict(COMPACT, horizon_days=10))
    assert validate_scenario(dict(COMPACT, marketplace={"bundling": "yes"}))


def test_compact_equals_library_phase(in_root):
    """A compact file that restates the P2 defaults expands to exactly P2-default."""
    from lunarsim.config import library
    p2 = library()["P2-default"]
    d = {"form": "compact", "name": p2.name, "phase": "P2", "bulk_t_per_year": 500, "fleet": [list(v) for v in p2.fleet],
         "night_fraction": 0.15, "rtt_s": 5.0, "n_operators": 3, "other_duty_share": 0.3, "mtbf_mult": 1.0,
         "common_standard_share": 1.0}
    assert scenario_from_dict(d) == p2


def test_split_rtt_exact_over_slider_range():
    for i in range(0, 6001):
        rtt = round(i * 0.01, 10)
        ow, gd = split_rtt(rtt)
        assert 2 * ow + gd == rtt and ow >= 0 and gd >= 0
        assert gd == 0.0 if rtt < 2.4 else abs(gd - 2.4) < 1e-15


def test_cli_run_with_compact_file(in_root, tmp_path):
    from lunarsim.cli import main
    p = tmp_path / "web.json"
    p.write_text(json.dumps(dict(COMPACT, marketplace={"bundling": False})), encoding="utf-8")
    out = tmp_path / "runs.csv"
    main(["run", "--scenario", str(p), "--mechanism", "marketplace", "--seeds", "2", "--out", str(out)])
    import pandas as pd
    df = pd.read_csv(out)
    assert list(df["scenario"]) == ["lunarsim-live"] * 2
    # the file's flag reached the mechanism: identical to calling marketplace(bundling=False) directly
    from lunarsim import run
    sc, kw = load_scenario_ex(str(p))
    assert kw == {"bundling": False}
    assert df.loc[1, "jobs"] == run(sc, dispatch.marketplace, seed=1, bundling=False)["jobs"]


def test_scenario_schema_if_jsonschema_installed(in_root):
    jsonschema = pytest.importorskip("jsonschema")
    v = jsonschema.Draft202012Validator(load_schema("scenario-v1"))
    for path in SCENARIO_FILES:
        with open(path, encoding="utf-8") as f:
            v.validate(json.load(f))
    v.validate(COMPACT)
    v.validate(scenario_to_dict(scenario_from_dict(COMPACT)))
    assert list(v.iter_errors(dict(COMPACT, horizon_days=1)))


# ---------------------------------------------------------------------------
# lunarsim validate
# ---------------------------------------------------------------------------
from lunarsim.formats import detect_kind, validate_file


def _validate_cli(capsys, *files):
    from lunarsim.cli import main
    with pytest.raises(SystemExit) as e:
        main(["validate", *map(str, files)])
    return e.value.code, capsys.readouterr().out


def test_validate_cli_bundled_files(in_root, capsys):
    files = SCENARIO_FILES + SAMPLES
    code, out = _validate_cli(capsys, *files)
    assert code == 0
    oks = [l for l in out.splitlines() if l.startswith("OK")]
    assert len(oks) == len(files)
    assert sum(l.endswith("trace v1") for l in oks) == len(SAMPLES_V1)
    assert sum(l.endswith("trace v2") for l in oks) == len(SAMPLES_V2)
    assert sum(l.endswith("scenario v1") for l in oks) == len(SCENARIO_FILES)
    assert not any("legacy" in l for l in oks)


def test_validate_cli_legacy_copies(in_root, tmp_path, capsys):
    """The committed files with their v1 headers stripped still validate, reported as legacy."""
    files = []
    for src, keys in [(p, SCENARIO_HEADER) for p in SCENARIO_FILES] + [(p, TRACE_HEADER) for p in SAMPLES_V1]:
        with open(src, encoding="utf-8") as f:
            legacy = _strip(json.load(f), keys)
        assert "format" not in legacy
        dst = tmp_path / os.path.basename(src)
        dst.write_text(json.dumps(legacy), encoding="utf-8")
        files.append(dst)
    code, out = _validate_cli(capsys, *files)
    assert code == 0
    oks = [l for l in out.splitlines() if l.startswith("OK")]
    assert len(oks) == len(SCENARIO_FILES) + len(SAMPLES_V1)              # v2 traces have no legacy form
    assert sum(l.endswith("trace v1 legacy") for l in oks) == len(SAMPLES_V1)
    assert sum(l.endswith("scenario v1 legacy") for l in oks) == len(SCENARIO_FILES)


@pytest.mark.parametrize("path", SCENARIO_FILES, ids=os.path.basename)
def test_legacy_scenarios_load_like_v1(path):
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    assert (d["format"], d["version"], d["form"]) == ("lunarsim-scenario", 1, "full")
    legacy = _strip(d, SCENARIO_HEADER)
    assert validate_scenario(legacy) == []
    assert scenario_from_dict(legacy) == scenario_from_dict(d)


def test_validate_cli_reports_failures(in_root, tmp_path, capsys, trace):
    good = tmp_path / "trace.json"
    good.write_text(json.dumps(trace), encoding="utf-8")
    broken = copy.deepcopy(trace)
    broken["cargo"][0].pop()
    bad_trace = tmp_path / "bad_trace.json"
    bad_trace.write_text(json.dumps(broken), encoding="utf-8")
    bad_phase = tmp_path / "bad_phase.json"
    bad_phase.write_text(json.dumps(dict(COMPACT, phase="P9")), encoding="utf-8")
    bad_field = tmp_path / "bad_field.json"
    bad_field.write_text(json.dumps({"name": "x", "nigth_fraction": 0.1}), encoding="utf-8")
    not_json = tmp_path / "not.json"
    not_json.write_text("{oops", encoding="utf-8")
    other = tmp_path / "other.json"
    other.write_text(json.dumps({"format": "something-else"}), encoding="utf-8")
    code, out = _validate_cli(capsys, good, bad_trace, bad_phase, bad_field, not_json, other)
    assert code == 1
    assert f"OK   {good}  trace v1" in out and "legacy" not in out.splitlines()[0]
    for p in (bad_trace, bad_phase, bad_field, not_json, other):
        assert f"FAIL {p}" in out
    assert "cargo[0]: expected a list of 11" in out
    assert "phase: expected P1, P2 or P3" in out
    assert "unknown scenario fields: ['nigth_fraction']" in out
    assert "cannot read JSON" in out and "unknown format 'something-else'" in out
    assert "1 of 6 files valid" in out


def test_detect_kind():
    assert detect_kind({"format": "lunarsim-trace"}) == "trace"
    assert detect_kind({"format": "lunarsim-scenario", "phase": "P2"}) == "scenario"
    assert detect_kind({"jobs": [], "cargo": []}) == "trace"
    assert detect_kind({"name": "x"}) == "scenario"
    with pytest.raises(ValueError):
        detect_kind({"format": "csv"})


def test_validate_file_semantic_scenario_error(in_root, tmp_path):
    # structurally fine, but the loader refuses it: the bulk flow names a field BulkFlow lacks
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"name": "x", "bulk_flows": [{"origin": "A", "dest": "B", "tonnes_per_year": 1, "colour": "red"}]}),
                 encoding="utf-8")
    kind, legacy, errs = validate_file(str(p))
    assert (kind, legacy) == ("scenario", True) and errs and "does not load" in errs[0]


# ---------------------------------------------------------------------------
# B-6: phase table inside the package
# ---------------------------------------------------------------------------
import shutil, subprocess


def test_phases_module_matches_experiments():
    import experiments.scenarios as old
    import experiments.run_all as ra
    from lunarsim import phases
    assert old.PHASES is phases.PHASES and old.OWNERS is phases.OWNERS
    assert ra.FLEETS == phases.FLEETS          # run_all keeps its own copy of the fleet table


def test_compact_outside_repo_checkout(tmp_path):
    """Only the lunarsim package (no experiments/), run from an unrelated working directory."""
    pkg = tmp_path / "site"
    shutil.copytree(os.path.join(ROOT, "lunarsim"), pkg / "lunarsim", ignore=shutil.ignore_patterns("__pycache__"))
    work = tmp_path / "work"
    work.mkdir()
    (work / "web.json").write_text(json.dumps(dict(COMPACT, phase="P1", bulk_t_per_year=0)), encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(pkg), PYTHONWARNINGS="ignore")
    def lunarsim(*args):
        return subprocess.run([sys.executable, "-m", "lunarsim", *args], cwd=work, env=env,
                              capture_output=True, text=True, timeout=300)
    r = subprocess.run([sys.executable, "-c", "import experiments"], cwd=work, env=env, capture_output=True, text=True)
    assert r.returncode != 0                     # really no repository on the path
    r = lunarsim("validate", "web.json")
    assert r.returncode == 0 and "OK   web.json  scenario v1" in r.stdout, r.stdout + r.stderr
    r = lunarsim("run", "--scenario", "web.json", "--seeds", "2", "--out", "runs.csv")
    assert r.returncode == 0, r.stderr
    assert "marketplace on lunarsim-live: 2 seeds" in r.stdout
    r = lunarsim("scenarios", "list")
    assert r.returncode == 0 and "P2-8-vehicles" in r.stdout


def test_landing_order_does_not_depend_on_dict_key_order():
    """B-12b: reversed landings_per_year keys give the same year, seed for seed."""
    from lunarsim import run, dispatch
    from lunarsim.config import library
    sc = library()["P2-default"]
    rev = sc.with_(landings_per_year=dict(reversed(list(sc.landings_per_year.items()))))
    assert list(rev.landings_per_year) != list(sc.landings_per_year)
    for seed in (0, 1):
        a, b = run(sc, dispatch.marketplace, seed=seed), run(rev, dispatch.marketplace, seed=seed)
        assert all((x == y) or (x != x and y != y) for x, y in zip(a.values(), b.values()))
    d = scenario_to_dict(rev)
    assert scenario_from_dict(json.loads(json.dumps(d))).landings_per_year == rev.landings_per_year
    with pytest.raises(ValueError, match="unknown lander types"):
        run(sc.with_(landings_per_year={"CLPS": 1, "XL": 1}), dispatch.marketplace, seed=0)
