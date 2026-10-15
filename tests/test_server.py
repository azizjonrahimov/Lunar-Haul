"""`lunarsim serve`: every endpoint of the local JSON API (PLAN §4.5), against a live server on a free port."""
import json, os, sys, threading
import urllib.error, urllib.request
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import pytest

from lunarsim import dispatch, run, Simulation
from lunarsim.config import library
from lunarsim.formats import validate_trace, validate_scenario
from lunarsim.server import make_server


def _no_nan(s):
    raise AssertionError(f"non-standard JSON constant {s}")


@pytest.fixture(scope="module")
def base():
    os.chdir(ROOT)                      # the scenario library lives in experiments/
    srv = make_server(0)
    th = threading.Thread(target=srv.serve_forever, daemon=True)
    th.start()
    host, port = srv.server_address[:2]
    yield f"http://{host}:{port}"
    srv.shutdown()
    srv.server_close()


def call(base, method, path, body=None, raw=None):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    req = urllib.request.Request(base + path, data=data, method=method,
                                 headers={"Content-Type": "application/json"} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            status, headers, text = r.status, r.headers, r.read().decode()
    except urllib.error.HTTPError as e:
        status, headers, text = e.code, e.headers, e.read().decode()
    assert headers["Access-Control-Allow-Origin"] == "*"
    payload = json.loads(text, parse_constant=_no_nan) if text else None
    if text:
        assert headers["Content-Type"] == "application/json"
    return status, payload


SHORT = {"form": "full", "name": "short", "horizon_h": 2000.0,
         "fleet": [["NASA", "LTV", "supervised", "A"], ["CoA", "HAUL", "supervised", "A"]]}


def test_binds_localhost_only(base):
    assert base.startswith("http://127.0.0.1:")


def test_health(base):
    from lunarsim import __version__
    assert call(base, "GET", "/api/health") == (200, {"ok": True, "version": __version__, "engine": "python"})


def test_scenarios(base):
    st, d = call(base, "GET", "/api/scenarios")
    assert st == 200
    names = {s["name"]: s for s in d["scenarios"]}
    assert set(names) == set(library())
    assert names["P2-default"]["fleet_size"] == 6
    assert names["P2-default"]["landings_per_year"] == {"CLPS": 4, "MK1": 3, "LARGE": 1}


def test_scenario_by_name(base):
    st, d = call(base, "GET", "/api/scenarios/P2-4-vehicles")
    assert st == 200 and (d["format"], d["version"], d["form"], d["name"]) == ("lunarsim-scenario", 1, "full", "P2-4-vehicles")
    assert validate_scenario(d) == []
    st, d = call(base, "GET", "/api/scenarios/P9")
    assert st == 404 and "P2-default" in d["error"]


def test_run_named_matches_engine(base):
    st, d = call(base, "POST", "/api/run", {"scenario": "P2-default", "mechanism": "marketplace", "seeds": [1]})
    assert st == 200 and isinstance(d["ms"], int) and len(d["runs"]) == 1
    row = d["runs"][0]
    ref = run(library()["P2-default"], dispatch.marketplace, seed=1)
    assert row["seed"] == 1 and set(row) == set(ref)
    for k, v in ref.items():
        assert row[k] == (None if v != v else v), k        # identical numbers, NaN -> null


def test_run_scenario_object_opts_and_nan(base):
    body = {"scenario": SHORT, "mechanism": "marketplace", "seeds": [0, 2], "opts": {"bundling": False, "team": False}}
    st, d = call(base, "POST", "/api/run", body)
    assert st == 200 and [r["seed"] for r in d["runs"]] == [0, 2]
    from lunarsim.config import scenario_from_dict
    ref = run(scenario_from_dict(SHORT), dispatch.marketplace, seed=2, bundling=False, team_lift=False)
    assert d["runs"][1]["jobs"] == ref["jobs"]
    assert any(v is None for v in d["runs"][0].values())    # short run: some class means are NaN -> null


def test_run_compact_scenario_flags(base):
    compact = {"form": "compact", "phase": "P1", "bulk_t_per_year": 0, "rtt_s": 7.0,
               "fleet": [{"owner": "NASA", "cls": "LTV", "autonomy": "teleop", "std": "A"}],
               "marketplace": {"bundling": False}}
    st, d = call(base, "POST", "/api/run", {"scenario": compact, "seeds": [0]})
    assert st == 200
    from lunarsim.config import scenario_from_dict
    ref = run(scenario_from_dict(compact), dispatch.marketplace, seed=0, bundling=False)
    assert d["runs"][0]["jobs"] == ref["jobs"]
    # opts override the file's flags
    st, d2 = call(base, "POST", "/api/run", {"scenario": compact, "seeds": [0], "opts": {"bundling": True}})
    ref2 = run(scenario_from_dict(compact), dispatch.marketplace, seed=0)
    assert st == 200 and d2["runs"][0]["jobs"] == ref2["jobs"]


def test_compare(base):
    st, d = call(base, "POST", "/api/compare", {"scenario": SHORT, "seeds": [4]})
    assert st == 200 and list(d["runs"]) == ["inhouse", "pooled_greedy", "central_assign", "marketplace"]
    from lunarsim.config import scenario_from_dict
    ref = run(scenario_from_dict(SHORT), dispatch.central_assign, seed=4, batch_h=1.0)
    assert d["runs"]["central_assign"][0]["jobs"] == ref["jobs"]


def test_trace(base):
    st, d = call(base, "POST", "/api/trace", {"scenario": "P2-4-vehicles", "mechanism": "pooled_greedy", "seed": 2})
    assert st == 200 and validate_trace(d) == []
    assert (d["format"], d["engine"], d["scenario"], d["mechanism"], d["seed"]) == ("lunarsim-trace", "python", "P2-4-vehicles", "pooled_greedy", 2)
    sim = Simulation(library()["P2-4-vehicles"], dispatch.pooled_greedy, seed=2, mech_kwargs={"trace": True})
    sim.run()
    assert len(d["jobs"]) == len(sim.trace) and len(d["cargo"]) == len(sim.all_cargo)


def test_verify(base):
    st, d = call(base, "GET", "/api/verify")
    assert st == 200 and d["total"] == len(d["checks"]) and d["passed"] == d["total"]
    for c in d["checks"]:
        assert {"name", "reference", "simulated", "rel_error", "passed"} <= set(c)


def test_options_preflight(base):
    req = urllib.request.Request(base + "/api/run", method="OPTIONS",
                                 headers={"Origin": "https://example.org", "Access-Control-Request-Method": "POST"})
    with urllib.request.urlopen(req, timeout=10) as r:
        assert r.status == 204
        assert r.headers["Access-Control-Allow-Origin"] == "*"
        assert "POST" in r.headers["Access-Control-Allow-Methods"]
        assert "Content-Type" in r.headers["Access-Control-Allow-Headers"]


@pytest.mark.parametrize("method,path,body,status,needle", [
    ("POST", "/api/run", {"scenario": "nope", "seeds": [0]}, 400, "P2-default"),
    ("POST", "/api/run", {"mechanism": "nope", "seeds": [0]}, 400, "marketplace"),
    ("POST", "/api/run", {"seeds": list(range(101))}, 400, "at most 100"),
    ("POST", "/api/run", {"seeds": [-1]}, 400, "non-negative"),
    ("POST", "/api/run", {"seeds": []}, 400, "non-empty"),
    ("POST", "/api/run", {"seeds": [0], "opts": {"telepathy": True}}, 400, "unknown opts"),
    ("POST", "/api/run", {"scenario": {"name": "x", "nigth_fraction": 0.1}, "seeds": [0]}, 400, "unknown scenario fields"),
    ("POST", "/api/compare", {"seeds": list(range(101))}, 400, "at most 100"),
    ("POST", "/api/trace", {"mechanism": "nope"}, 400, "Known"),
    ("POST", "/api/trace", {"seed": "3"}, 400, "seed"),
    ("GET", "/api/run", None, 405, "POST"),
    ("POST", "/api/health", {}, 405, "GET"),
    ("GET", "/api/nothing", None, 404, "no endpoint"),
])
def test_errors(base, method, path, body, status, needle):
    st, d = call(base, method, path, body)
    assert st == status and needle in d["error"]


def test_bad_json(base):
    st, d = call(base, "POST", "/api/run", raw=b"{not json")
    assert st == 400 and "not valid JSON" in d["error"]
    st, d = call(base, "POST", "/api/run", raw=b"[1, 2]")
    assert st == 400 and "JSON object" in d["error"]
