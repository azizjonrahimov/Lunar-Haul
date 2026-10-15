"""service v2 (PLAN §5.6): FastAPI app + SQLite + worker + SSE + auth, in-process, no network.

Skips cleanly when fastapi is not installed (`pip install -e .[service]`).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from service.app import create_app  # noqa: E402
from service.auth import ListMailer  # noqa: E402
from service.settings import Settings  # noqa: E402
from service.worker import Worker  # noqa: E402
from lunarsim.formats import validate_trace  # noqa: E402

API = "https://api.test"
APP = "https://app.test"
HDR = {"X-Requested-With": "lunarsim", "Origin": APP}        # what the site sends on every POST
HIGH = {k: "100000/minute" for k in ("default", "auth_start", "auth_magic", "auth_consume", "runs_create",
                                     "runs_read", "public_list", "data_read")}
SHA = re.compile(r"^[0-9a-f]{64}$")


def make(tmp_path, **over):
    kw = dict(data_dir=str(tmp_path / "data"), base_url=API, app_url=APP, allowed_origins=[APP], cookie_secure=True,
              rate_limits=dict(HIGH), quota_cpu_s_per_day=1e6, quota_anon_cpu_s_per_day=1e6, log_level="WARNING")
    kw.update(over)
    settings = Settings(**kw)
    mailer = ListMailer()
    app = create_app(settings, mailer)
    client = TestClient(app, base_url=API)      # https base URL so the Secure cookie is stored and sent
    worker = Worker(settings, db=app.state.ctx.db)
    return {"settings": settings, "mailer": mailer, "app": app, "client": client, "worker": worker,
            "db": app.state.ctx.db}


def sign_in(env, email, client=None):
    """Magic-link flow end to end against the stubbed mailer; returns the client holding the session cookie."""
    c = client or env["client"]
    r = c.post("/v2/auth/magic", json={"email": email}, headers=HDR)
    assert r.status_code == 202, r.text
    link = re.search(r"https://\S+/v2/auth/magic/\S+", env["mailer"].sent[-1]["text"]).group(0)
    r = c.get(link, follow_redirects=False)
    assert r.status_code == 303, r.text
    return c, r


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    e = make(tmp_path_factory.mktemp("svc"))
    with e["client"]:
        yield e


# ---------------------------------------------------------------------------------------------------------
def test_health_and_version(env):
    c = env["client"]
    r = c.get("/v2/health")
    assert r.status_code == 200
    d = r.json()
    from lunarsim import __version__
    assert d["ok"] is True and d["engine"] == __version__ and d["db"] == "ok" and "queued" in d["queue"]
    r = c.get("/v2/version")
    assert r.status_code == 200
    v = r.json()
    assert v["engine_version"].startswith(__version__)
    assert v["git_sha"] is None or re.match(r"^[0-9a-f]{40}$", v["git_sha"])
    assert SHA.match(v["lock_sha"]) and v["python"] and v["platform"]
    assert "limits" in v and v["limits"]["max_seeds"] == 100 and "rate_limits" in v
    assert isinstance(v["policies"], list) and isinstance(v["terrain"], list)
    assert v["auth"] == {"orcid": False, "github": False, "magic_link": True, "csrf_header": "X-Requested-With: lunarsim"}


def test_create_run_worker_summary_trace(env):
    c, w = env["client"], env["worker"]
    r = c.post("/v2/runs", json={"scenario": "P2-default", "mechanism": "marketplace", "seeds": [0, 1]}, headers=HDR)
    assert r.status_code == 202, r.text
    d = r.json()
    rid = d["run_id"]
    assert d["status"] == "queued" and len(rid) == 26 and SHA.match(d["scenario_sha"])
    r = c.get(f"/v2/runs/{rid}")
    assert r.status_code == 200
    g = r.json()
    assert g["status"] == "queued" and g["seeds"] == [0, 1] and g["mechanism"] == "marketplace"
    assert g["scenario"]["format"] == "lunarsim-scenario" and g["scenario"]["name"] == "P2-default"
    assert g["provenance"]["lock_sha"] and g["summary"] is None
    assert c.get(f"/v2/runs/{rid}/summary").status_code == 409        # not ready

    assert w.run_once() is True
    assert w.run_once() is False                                       # queue empty
    g = c.get(f"/v2/runs/{rid}").json()
    assert g["status"] == "done", g
    assert SHA.match(g["output_sha"]) and g["cpu_s"] >= 0 and g["finished"]
    s = g["summary"]
    assert s["n_seeds"] == 2 and set(s["traces"]) == {"0", "1"} and all(SHA.match(x) for x in s["traces"].values())
    assert s["metrics"]["delay_prio1_mean_h"]["n"] == 2 and len(s["rows"]) == 2 and s["rows"][1]["seed"] == 1

    # the per-seed rows equal a direct engine run (the service adds nothing to the physics)
    from lunarsim import dispatch, run
    from lunarsim.config import library
    direct = run(library()["P2-default"].with_(name="P2-default"), dispatch.MECHANISMS["marketplace"], seed=0)
    assert s["rows"][0]["delay_prio1_mean_h"] == pytest.approx(direct["delay_prio1_mean_h"])
    assert s["rows"][0]["cost_per_kg_usd"] == pytest.approx(direct["cost_per_kg_usd"])
    # the stored scenario keeps landings_per_year in the order the engine iterates it (the sorted spelling would
    # change the random draws), while every other mapping is sorted
    sj = env["db"].get_run(rid)["scenario_json"]
    assert '"landings_per_year":{"CLPS":4,"MK1":3,"LARGE":1}' in sj and sj.startswith('{"bulk_flows":[{"dest"')

    r = c.get(f"/v2/runs/{rid}/summary")
    assert r.status_code == 200 and r.json()["output_sha"] == g["output_sha"]

    r = c.get(f"/v2/runs/{rid}/trace", params={"seed": 1})
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    tr = r.json()
    assert validate_trace(tr) == [] and tr["seed"] == 1 and tr["scenario"] == "P2-default"
    sha = s["traces"]["1"]
    assert r.headers["etag"] == f'"{sha}"' and r.headers["x-content-sha256"] == sha
    assert os.path.isfile(os.path.join(env["settings"].data_dir, "blobs", sha[:2], sha))   # content-addressed path
    assert c.get(f"/v2/runs/{rid}/trace", params={"seed": 7}).status_code == 404
    env["run_id"] = rid


def test_replicate_identical_sha_and_badge(env):
    c, w = env["client"], env["worker"]
    rid = env["run_id"]
    r = c.post(f"/v2/runs/{rid}/replicate", headers=HDR)
    assert r.status_code == 202, r.text
    child = r.json()["run_id"]
    assert r.json()["parent_run_id"] == rid
    assert w.run_once() is True
    ch = c.get(f"/v2/runs/{child}").json()
    pa = c.get(f"/v2/runs/{rid}").json()
    assert ch["status"] == "done" and ch["parent_run_id"] == rid
    assert ch["output_sha"] == pa["output_sha"]
    assert ch["replicated"] is True and pa["replicated"] is True
    ev = c.get(f"/v2/runs/{rid}/events").text
    assert "event: replicated" in ev and '"replicated":true' in ev
    env["child_id"] = child


def test_trace_blob_is_deduplicated(env):
    c, db = env["client"], env["db"]
    pa = c.get(f"/v2/runs/{env['run_id']}").json()["summary"]["traces"]
    ch = c.get(f"/v2/runs/{env['child_id']}").json()["summary"]["traces"]
    assert pa == ch                                                     # identical inputs -> identical trace shas
    sha = pa["0"]
    n = db.one("SELECT COUNT(*) AS n FROM blobs WHERE sha=?", (sha,))["n"]
    assert n == 1
    folder = os.path.join(env["settings"].data_dir, "blobs", sha[:2])
    assert sorted(f for f in os.listdir(folder) if f == sha) == [sha]
    row = db.get_blob(sha)
    assert row["path"] == f"blobs/{sha[:2]}/{sha}" and row["media"] == "application/json" and row["bytes"] > 1000


def test_sse_yields_done_event(env):
    c = env["client"]
    r = c.get(f"/v2/runs/{env['run_id']}/events")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    body = r.text
    assert "event: queued" in body and "event: progress" in body and "event: done" in body
    # ids are the run_events seq, so Last-Event-ID resumes after the given one
    first_done_id = int(re.search(r"id: (\d+)\r?\nevent: done", body).group(1))     # sse-starlette uses CRLF
    r2 = c.get(f"/v2/runs/{env['run_id']}/events", headers={"Last-Event-ID": str(first_done_id)})
    assert "event: queued" not in r2.text and "event: replicated" in r2.text
    assert c.get("/v2/runs/01ARZ3NDEKTSV4RRFFQ69G5FAV/events").status_code == 404


def test_magic_link_flow_cookie_attributes_logout(env):
    c = env["client"]
    r = c.post("/v2/auth/magic", json={"email": "not-an-address"}, headers=HDR)
    assert r.status_code == 400 and r.json()["code"] == "invalid_email"
    assert c.get("/v2/me").status_code == 401

    _, r = sign_in(env, "Ada@Example.org")
    assert r.headers["location"] == APP
    cookie = r.headers["set-cookie"]
    low = cookie.lower()
    assert cookie.startswith("lunarsim_session=") and "httponly" in low and "secure" in low and "samesite=lax" in low
    assert "path=/" in low and "max-age=" in low and "domain=" not in low
    link = re.search(r"https://\S+/v2/auth/magic/\S+", env["mailer"].sent[-1]["text"]).group(0)
    r = c.get(link, follow_redirects=False)                              # single use
    assert r.status_code == 400 and r.json()["code"] == "invalid_token"
    r = c.get("/v2/me")
    assert r.status_code == 200
    me = r.json()
    assert me["user"]["email"] == "ada@example.org" and me["session"]["via"] == "cookie" and "quota" in me

    # cookie-authenticated POST without an Origin header is refused (CSRF), with the header it works
    r = c.post("/v2/logout", headers={"X-Requested-With": "lunarsim"})
    assert r.status_code == 403 and r.json()["code"] == "csrf"
    r = c.post("/v2/logout", headers=HDR)
    assert r.status_code == 200
    assert c.get("/v2/me").status_code == 401


def test_bearer_mode_for_github_io_origin(env):
    c = env["client"]
    r = c.post("/v2/auth/magic", json={"email": "grace@example.org", "mode": "bearer", "next": "/account"}, headers=HDR)
    assert r.status_code == 202
    link = re.search(r"https://\S+/v2/auth/magic/\S+", env["mailer"].sent[-1]["text"]).group(0)
    r = c.get(link, follow_redirects=False)
    assert r.status_code == 303 and "set-cookie" not in r.headers
    loc = r.headers["location"]
    assert loc.startswith(APP + "/account#login_code=")
    code = loc.split("#login_code=", 1)[1]
    r = c.post("/v2/auth/token", json={"code": code}, headers=HDR)
    assert r.status_code == 200
    tok = r.json()["token"]
    assert len(tok) >= 32
    assert c.post("/v2/auth/token", json={"code": code}, headers=HDR).status_code == 400      # single use
    auth = {"Authorization": f"Bearer {tok}", "X-Requested-With": "lunarsim"}
    r = c.get("/v2/me", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json()["session"]["via"] == "bearer"
    r = c.post("/v2/runs", json={"scenario": "P2-default", "seeds": [0]}, headers=auth)        # no Origin needed
    assert r.status_code == 202, r.text
    r = c.post("/v2/logout", headers=auth)
    assert r.status_code == 200
    assert c.get("/v2/me", headers={"Authorization": f"Bearer {tok}"}).status_code == 401


def test_csrf_header_required_on_post(env):
    c = env["client"]
    r = c.post("/v2/runs", json={"scenario": "P2-default", "seeds": [0]})
    assert r.status_code == 403 and r.json()["code"] == "csrf"
    r = c.post("/v2/runs", json={"scenario": "P2-default", "seeds": [0]},
               headers={"X-Requested-With": "lunarsim", "Origin": "https://evil.example"})
    assert r.status_code == 403 and r.json()["code"] == "csrf"
    r = c.post("/v2/runs", json={"scenario": "P2-default", "seeds": [0]},
               headers={"X-Requested-With": "wrong", "Origin": APP})
    assert r.status_code == 403
    r = c.post("/v2/auth/magic", json={"email": "x@example.org"}, headers={"X-Requested-With": "lunarsim"})
    assert r.status_code == 202                                         # anonymous + header + no Origin (curl) is fine


def test_errors_are_json(env):
    c = env["client"]
    r = c.post("/v2/runs", json={"scenario": "nope"}, headers=HDR)
    assert r.status_code == 400 and r.json()["code"] == "bad_request" and "unknown scenario" in r.json()["error"]
    r = c.post("/v2/runs", json={"scenario": "P2-default", "seeds": list(range(101))}, headers=HDR)
    assert r.status_code == 400 and "100" in r.json()["error"]
    r = c.post("/v2/runs", json={"scenario": "P2-default", "mechanism": "magic"}, headers=HDR)
    assert r.status_code == 400 and "unknown mechanism" in r.json()["error"]
    r = c.post("/v2/runs", json={"scenario": {"format": "lunarsim-scenario", "version": 1, "form": "full", "fleet": 3}},
               headers=HDR)
    assert r.status_code == 400 and "invalid scenario" in r.json()["error"]
    r = c.post("/v2/runs", json={"scenario": "P2-default", "options": {"bogus": 1}}, headers=HDR)
    assert r.status_code == 400 and "unknown options" in r.json()["error"]
    r = c.post("/v2/runs", content=b"{not json", headers={**HDR, "Content-Type": "application/json"})
    assert r.status_code == 400
    r = c.get("/v2/nothing")
    assert r.status_code == 404 and r.json() == {"error": "no endpoint GET /v2/nothing", "code": "not_found"}
    r = c.get("/v2/runs/not-a-ulid")
    assert r.status_code == 404 and r.json()["code"] == "not_found"
    r = c.get("/v2/runs")
    assert r.status_code == 401


def test_rate_limit_returns_429(tmp_path):
    e = make(tmp_path, rate_limits={**HIGH, "auth_magic": "2/minute"})
    with e["client"] as c:
        for _ in range(2):
            assert c.post("/v2/auth/magic", json={"email": "r@example.org"}, headers=HDR).status_code == 202
        r = c.post("/v2/auth/magic", json={"email": "r@example.org"}, headers=HDR)
        assert r.status_code == 429
        assert r.json()["code"] == "rate_limited" and int(r.headers["retry-after"]) >= 1
        assert c.get("/v2/health").status_code == 200                   # other groups unaffected


def test_quota_exceeded_returns_429_and_settles_to_actual_cpu(tmp_path):
    e = make(tmp_path, quota_anon_cpu_s_per_day=2.9, cpu_s_per_seed_estimate=1.0)
    with e["client"] as c:
        body = {"scenario": "P2-default", "seeds": [0]}
        r1 = c.post("/v2/runs", json=body, headers=HDR)
        r2 = c.post("/v2/runs", json=body, headers=HDR)
        assert r1.status_code == 202 and r2.status_code == 202
        assert r2.json()["quota"] == {"key": "ip", "used_cpu_s": 2.0, "limit_cpu_s": 2.9, "day": r2.json()["quota"]["day"]}
        r3 = c.post("/v2/runs", json=body, headers=HDR)
        assert r3.status_code == 429, r3.text
        assert r3.json()["code"] == "quota_exceeded" and "CPU" in r3.json()["error"] and "00:00 UTC" in r3.json()["error"]
        assert int(r3.headers["retry-after"]) >= 1
        assert e["worker"].run_once() and e["worker"].run_once()
        g = c.get(f"/v2/runs/{r1.json()['run_id']}").json()
        assert g["status"] == "done" and 0 <= g["cpu_s"] < 1.0           # the reservation became the measured CPU time
        r4 = c.post("/v2/runs", json=body, headers=HDR)                  # budget freed by the correction
        assert r4.status_code == 202, r4.text
        assert r4.json()["quota"]["used_cpu_s"] < 2.9


def test_queue_depth_cap(tmp_path):
    e = make(tmp_path, max_queued_per_user=2)
    with e["client"] as c:
        body = {"scenario": "P2-default", "seeds": [0]}
        assert c.post("/v2/runs", json=body, headers=HDR).status_code == 202
        assert c.post("/v2/runs", json=body, headers=HDR).status_code == 202
        r = c.post("/v2/runs", json=body, headers=HDR)
        assert r.status_code == 429 and r.json()["code"] == "queue_full"


def test_public_listing_hides_private_runs(tmp_path):
    e = make(tmp_path)
    with e["client"] as a:
        sign_in(e, "owner@example.org", a)
        r = a.post("/v2/runs", json={"scenario": "P2-default", "seeds": [0]}, headers=HDR)
        assert r.status_code == 202
        rid = r.json()["run_id"]
        assert e["worker"].run_once()
        anon = TestClient(e["app"], base_url=API)
        assert anon.get(f"/v2/runs/{rid}").status_code == 404               # private: invisible to others
        assert anon.get("/v2/runs", params={"public": 1}).json()["runs"] == []
        mine = a.get("/v2/runs").json()
        assert [x["run_id"] for x in mine["runs"]] == [rid] and mine["runs"][0]["owner"] is True
        assert "rows" not in (mine["runs"][0]["summary"] or {})           # list view is compact

        other = TestClient(e["app"], base_url=API)
        sign_in(e, "other@example.org", other)
        assert other.get(f"/v2/runs/{rid}").status_code == 404
        assert other.get("/v2/runs").json()["runs"] == []
        assert other.post(f"/v2/runs/{rid}/publish", headers=HDR).status_code == 404

        r = a.post(f"/v2/runs/{rid}/publish", headers=HDR)
        assert r.status_code == 200 and r.json()["public"] is True
        assert other.post(f"/v2/runs/{rid}/publish", headers=HDR).status_code == 403   # readable now, not owned
        pub = anon.get("/v2/runs", params={"public": 1, "metric": "delay_prio1_mean_h"}).json()
        assert [x["run_id"] for x in pub["runs"]] == [rid]
        assert pub["runs"][0]["metric"]["name"] == "delay_prio1_mean_h" and pub["runs"][0]["owner"] is False
        assert "ranked" in pub["runs"][0] and "ranked_rule" in pub
        assert anon.get(f"/v2/runs/{rid}").status_code == 200
        assert anon.get("/v2/runs", params={"public": 1, "scenario": "P1-default"}).json()["runs"] == []
        assert anon.get("/v2/runs", params={"public": 1, "metric": "bad metric"}).status_code == 400
        r = a.post(f"/v2/runs/{rid}/publish", json={"public": False}, headers=HDR)
        assert r.status_code == 200 and r.json()["public"] is False
        assert anon.get(f"/v2/runs/{rid}").status_code == 404
        # another user replicates a public run: the child belongs to them and the badge lands on both
        a.post(f"/v2/runs/{rid}/publish", headers=HDR)
        r = other.post(f"/v2/runs/{rid}/replicate", headers=HDR)
        assert r.status_code == 202
        assert e["worker"].run_once()
        assert other.get(f"/v2/runs/{r.json()['run_id']}").json()["replicated"] is True
        assert anon.get(f"/v2/runs/{rid}").json()["replicated"] is True


def test_oauth_start_redirect_and_bad_state(tmp_path):
    e = make(tmp_path, github_client_id="cid", github_client_secret="sec")
    with e["client"] as c:
        r = c.get("/v2/auth/github/start", params={"mode": "bearer", "next": "/account"}, follow_redirects=False)
        assert r.status_code == 302, r.text
        loc = r.headers["location"]
        assert loc.startswith("https://github.com/login/oauth/authorize?")
        assert "client_id=cid" in loc and "state=" in loc and "redirect_uri=https%3A%2F%2Fapi.test%2Fv2%2Fauth%2Fgithub%2Fcallback" in loc
        assert "scope=read%3Auser+user%3Aemail" in loc
        r = c.get("/v2/auth/github/callback", params={"code": "x", "state": "bogus"})
        assert r.status_code == 400 and r.json()["code"] == "oauth_state"
        r = c.get("/v2/auth/github/callback", params={"error": "access_denied"})
        assert r.status_code == 400 and r.json()["code"] == "oauth_denied"
        r = c.get("/v2/auth/orcid/start", follow_redirects=False)
        assert r.status_code == 503 and r.json()["code"] == "provider_unconfigured"
        r = c.get("/v2/auth/twitter/start", follow_redirects=False)
        assert r.status_code == 404
        assert c.get("/v2/version").json()["auth"]["github"] is True


def test_cors_and_private_network_preflight(env):
    c = env["client"]
    r = c.options("/v2/runs", headers={"Origin": APP, "Access-Control-Request-Method": "POST",
                                       "Access-Control-Request-Headers": "x-requested-with,content-type",
                                       "Access-Control-Request-Private-Network": "true"})
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == APP
    assert r.headers["access-control-allow-credentials"] == "true"
    assert r.headers["access-control-allow-private-network"] == "true"
    r = c.get("/v2/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    assert r.headers["x-content-type-options"] == "nosniff"


def test_policies_and_terrain(env):
    c = env["client"]
    r = c.get("/v2/policies")
    assert r.status_code == 200
    pol = r.json()["policies"]
    if pol:
        p = pol[0]
        assert SHA.match(p["sha256"]) and "layers" not in p and p["format"] in ("lunarsim-policy", "lunarsim-landing-outcomes")
        r = c.get(f"/v2/policies/{p['id']}")
        assert r.status_code == 200 and r.headers["x-content-sha256"] == p["sha256"] and r.json()["format"] == p["format"]
    assert c.get("/v2/policies/../../pyproject").status_code == 404
    assert c.get("/v2/policies/nope").status_code == 404
    r = c.get("/v2/terrain")
    assert r.status_code == 200
    ter = r.json()["terrain"]
    if ter:
        t = ter[0]
        r = c.get(f"/v2/terrain/{t['id']}")
        assert r.status_code == 200 and r.json()["meta"]["format"] == "lunarsim-terrain" and "meta.json" in r.json()["files"]
        r = c.get(f"/v2/terrain/{t['id']}/files/meta.json")
        assert r.status_code == 200 and r.json()["format"] == "lunarsim-terrain"
        assert c.get(f"/v2/terrain/{t['id']}/files/..%2Fmeta.json").status_code == 404
    assert c.get("/v2/terrain/nope").status_code == 404


def test_phase3_options_run(env):
    c, w = env["client"], env["worker"]
    sites = os.path.join(ROOT, "data", "terrain", "connecting_ridge", "sites.json")
    if not os.path.isfile(sites):
        pytest.skip("terrain pack not present")
    body = {"scenario": "P2-4-vehicles", "mechanism": "marketplace", "seeds": [3],
            "options": {"terrain": "connecting_ridge", "pad_standoff_km": "1",
                        "plume": {"keepout_km": 1.0, "standdown_h": 0.5}, "opts": {"backhaul": False}}}
    r = c.post("/v2/runs", json=body, headers=HDR)
    assert r.status_code == 202, r.text
    rid = r.json()["run_id"]
    g = c.get(f"/v2/runs/{rid}").json()
    assert g["scenario"]["terrain"] == "connecting_ridge" and g["scenario"]["plume"]["keepout_km"] == 1.0
    assert g["options"] == {"terrain": "connecting_ridge", "pad_standoff_km": "1",
                            "plume": {"keepout_km": 1.0, "standdown_h": 0.5}, "opts": {"backhaul": False}}
    assert set(g["provenance"]["policy_shas"]) == {"data/terrain/connecting_ridge/meta.json",
                                                  "data/terrain/connecting_ridge/sites.json"}
    while w.run_once():            # drain the queue (earlier tests may have left runs queued)
        pass
    g = c.get(f"/v2/runs/{rid}").json()
    assert g["status"] == "done", g["error"]
    tr = c.get(f"/v2/runs/{rid}/trace").json()
    assert tr["version"] == 2 and validate_trace(tr) == [] and "plume_windows" in tr
    assert g["summary"]["metrics"].get("plume_standdowns") is not None
    r = c.post("/v2/runs", json={**body, "options": {"landing_model": {"policy": "does_not_exist"}}}, headers=HDR)
    assert r.status_code == 400 and r.json()["code"] == "missing_data"
