"""All /v2 endpoints (PLAN 5.6). JSON in and out; errors are {"error", "code"}.

Authentication: cookie or bearer session (auth.Auth.resolve). State-changing routes go through
`mutating()` which applies the CSRF rules. Each route group has a token-bucket limit keyed by the
signed-in user or the client IP (429 + Retry-After).
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Request
from starlette.responses import FileResponse, JSONResponse, RedirectResponse

from . import __version__ as SERVICE_VERSION
from . import provenance
from .auth import Auth, Identity
from .db import Database
from .errors import ServiceError
from .ratelimit import RateLimiter
from .settings import Settings
from .util import canonical_json, day_key, is_ulid, iso, seconds_to_next_utc_day, ulid
from .worker import prepare

METRIC_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
RANKED_SQL = "git_dirty = 0 AND engine_version NOT LIKE '%+%'"
RANKED_RULE = "only runs with git_dirty=false on a tagged engine release (engine_version without a local '+' part) rank"


@dataclass
class Context:
    settings: Settings
    db: Database
    auth: Auth
    limiter: RateLimiter


def ctx(request: Request) -> Context:
    return request.app.state.ctx


# ---------------------------------------------------------------------------------------------------------
# dependencies
# ---------------------------------------------------------------------------------------------------------
def client_ip(request: Request) -> str:
    c = ctx(request)
    if c.settings.trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def identity(request: Request) -> Optional[Identity]:
    if not hasattr(request.state, "ident"):
        request.state.ident = ctx(request).auth.resolve(request)
    return request.state.ident


def require_user(request: Request) -> Identity:
    ident = identity(request)
    if ident is None:
        raise ServiceError(401, "sign in first", "unauthorized")
    return ident


def mutating(request: Request) -> Optional[Identity]:
    """CSRF rules for POST routes; returns the identity (may be None for anonymous-capable routes)."""
    ident = identity(request)
    ctx(request).auth.csrf_check(request, ident)
    return ident


def limited(group: str):
    def dep(request: Request) -> None:
        c = ctx(request)
        ident = identity(request)
        key = f"u:{ident.user_id}" if ident else f"ip:{client_ip(request)}"
        retry = c.limiter.check(group, key)
        if retry is not None:
            n, period = c.limiter.rule(group)
            raise ServiceError(429, f"rate limit for this route is {n} requests per {int(period)} s; retry in {retry} s",
                               "rate_limited", {"Retry-After": str(retry)})
    return dep


async def read_json(request: Request) -> Dict[str, Any]:
    c = ctx(request)
    try:
        n = int(request.headers.get("content-length") or 0)
    except ValueError:
        raise ServiceError(400, "bad Content-Length")
    if n > c.settings.max_body_bytes:
        raise ServiceError(413, f"request body over {c.settings.max_body_bytes} bytes")
    raw = await request.body()
    if len(raw) > c.settings.max_body_bytes:
        raise ServiceError(413, f"request body over {c.settings.max_body_bytes} bytes")
    if not raw:
        return {}
    try:
        body = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as e:
        raise ServiceError(400, f"request body is not valid JSON: {e}")
    if not isinstance(body, dict):
        raise ServiceError(400, "request body must be a JSON object")
    return body


# ---------------------------------------------------------------------------------------------------------
# run views
# ---------------------------------------------------------------------------------------------------------
def _loads(s: Optional[str], default):
    if not s:
        return default
    try:
        return json.loads(s)
    except ValueError:
        return default


def can_read(row, ident: Optional[Identity]) -> bool:
    if row["public"]:
        return True
    if row["user_id"] is None:              # anonymous runs are reachable by their (unguessable) id
        return True
    return ident is not None and ident.user_id == row["user_id"]


def is_owner(row, ident: Optional[Identity]) -> bool:
    return ident is not None and row["user_id"] == ident.user_id


def run_view(row, ident: Optional[Identity], base: str, full: bool = True) -> Dict[str, Any]:
    summary = _loads(row["summary_json"], None)
    if summary is not None and not full:
        summary = {k: v for k, v in summary.items() if k != "rows"}
    sc = _loads(row["scenario_json"], {})
    d = {
        "run_id": row["id"], "status": row["status"], "created": row["created"], "started": row["started"],
        "finished": row["finished"], "public": bool(row["public"]), "doi": row["doi"], "cpu_s": row["cpu_s"],
        "parent_run_id": row["parent_run_id"],
        "replicated": None if row["replicated"] is None else bool(row["replicated"]),
        "owner": is_owner(row, ident), "anonymous": row["user_id"] is None,
        "scenario_name": sc.get("name"), "scenario_sha": row["scenario_sha"], "mechanism": row["mechanism"],
        "seeds": _loads(row["seeds_json"], []), "options": _loads(row["options_json"], {}),
        "provenance": {"engine_version": row["engine_version"], "git_sha": row["git_sha"],
                       "git_dirty": None if row["git_dirty"] is None else bool(row["git_dirty"]),
                       "patch_sha": row["patch_sha"], "lock_sha": row["lock_sha"], "python": row["python"],
                       "platform": row["platform"], "policy_shas": _loads(row["policy_shas_json"], {}),
                       "worker": row["worker"]},
        "ranked": bool(row["git_dirty"] == 0 and row["engine_version"] and "+" not in row["engine_version"]),
        "output_sha": row["output_sha"], "error": row["error"], "summary": summary,
        "links": {"self": f"{base}/v2/runs/{row['id']}", "events": f"{base}/v2/runs/{row['id']}/events",
                  "summary": f"{base}/v2/runs/{row['id']}/summary", "trace": f"{base}/v2/runs/{row['id']}/trace"},
    }
    if full:
        d["scenario"] = sc
    return d


def _get_run(c: Context, run_id: str, ident: Optional[Identity]):
    if not is_ulid(run_id):
        raise ServiceError(404, f"no run {run_id}", "not_found")
    row = c.db.get_run(run_id)
    if row is None or not can_read(row, ident):
        raise ServiceError(404, f"no run {run_id}", "not_found")
    return row


def _enqueue(c: Context, request: Request, ident: Optional[Identity], inputs_row: Dict[str, Any], n_seeds: int) -> Dict[str, Any]:
    """Quota + queue-depth checks, then insert. `inputs_row` carries scenario/mechanism/options/seeds/policy columns."""
    s = c.settings
    if ident is None:
        if not s.allow_anonymous_runs:
            raise ServiceError(401, "sign in to submit runs", "unauthorized")
        key, limit = f"ip:{client_ip(request)}", s.quota_anon_cpu_s_per_day
    else:
        key, limit = ident.user_id, s.quota_cpu_s_per_day
    queued = c.db.count_runs("status IN ('queued','running') AND (user_id=? OR anon_key=?)", (key, key))
    if queued >= s.max_queued_per_user:
        raise ServiceError(429, f"you already have {queued} queued or running run(s); the limit is {s.max_queued_per_user}",
                           "queue_full", {"Retry-After": "30"})
    estimate = n_seeds * s.cpu_s_per_seed_estimate
    today = day_key()
    used = c.db.quota_used(key, today)
    if used + estimate > limit:
        wait = seconds_to_next_utc_day()
        raise ServiceError(429, f"daily CPU budget exceeded: {used:.0f} of {limit:.0f} CPU-seconds used today and this "
                                f"run needs about {estimate:.0f}; the budget resets at 00:00 UTC (in {wait} s)",
                           "quota_exceeded", {"Retry-After": str(wait)})
    c.db.quota_add(key, today, estimate)
    prov = provenance.collect(s.repo_root)
    run_id = ulid()
    row = dict(inputs_row)
    row.update({"id": run_id, "user_id": ident.user_id if ident else None, "anon_key": None if ident else key,
                "created": iso(), "status": "queued", "cpu_s": estimate, **prov.columns()})
    row["public"] = int(bool(row.get("public", 0))) if ident else 0
    c.db.insert_run(row)
    c.db.add_event(run_id, "queued", {"seeds": n_seeds, "estimate_cpu_s": estimate,
                                      "position": c.db.count_runs("status='queued'")})
    return {"run_id": run_id, "status": "queued", "estimate_cpu_s": estimate,
            "quota": {"key": "account" if ident else "ip", "used_cpu_s": used + estimate, "limit_cpu_s": limit, "day": today},
            "links": {"self": f"{s.base_url}/v2/runs/{run_id}", "events": f"{s.base_url}/v2/runs/{run_id}/events"}}


# ---------------------------------------------------------------------------------------------------------
# router
# ---------------------------------------------------------------------------------------------------------
router = APIRouter(prefix="/v2")


@router.get("/health")
def health(request: Request):
    c = ctx(request)
    from lunarsim import __version__ as engine
    queued = c.db.count_runs("status='queued'")
    running = c.db.count_runs("status='running'")
    return {"ok": True, "service": SERVICE_VERSION, "engine": engine, "db": "ok",
            "queue": {"queued": queued, "running": running}, "time": iso()}


@router.get("/version")
def version(request: Request):
    c = ctx(request)
    prov = provenance.collect(c.settings.repo_root)
    s = c.settings
    return {"service": SERVICE_VERSION, **prov.public(),
            "policies": [p["id"] for p in provenance.list_policies(s.repo_root)],
            "terrain": [t["id"] for t in provenance.list_terrain(s.repo_root)],
            "limits": {"max_seeds": s.max_seeds, "max_body_bytes": s.max_body_bytes,
                       "max_queued_per_user": s.max_queued_per_user,
                       "quota_cpu_s_per_day": s.quota_cpu_s_per_day,
                       "quota_anon_cpu_s_per_day": s.quota_anon_cpu_s_per_day,
                       "anonymous_runs": s.allow_anonymous_runs},
            "rate_limits": c.limiter.describe(),
            "auth": {"orcid": s.provider("orcid") is not None, "github": s.provider("github") is not None,
                     "magic_link": True, "csrf_header": f"X-Requested-With: {s.csrf_header_value}"}}


# ------------------------------------------------------------------ auth
@router.get("/auth/{provider}/start", dependencies=[Depends(limited("auth_start"))])
def auth_start(provider: str, request: Request, mode: str = "cookie", next: Optional[str] = None):
    url = ctx(request).auth.oauth_start_url(provider, mode, next)
    resp = RedirectResponse(url, status_code=302)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@router.get("/auth/{provider}/callback", dependencies=[Depends(limited("auth_consume"))])
def auth_callback(provider: str, request: Request, code: Optional[str] = None, state: Optional[str] = None,
                  error: Optional[str] = None):
    user, mode, next_path = ctx(request).auth.oauth_callback(provider, code, state, error)
    return ctx(request).auth.finish_login(user, mode, next_path)


@router.post("/auth/magic", dependencies=[Depends(limited("auth_magic"))])
async def auth_magic(request: Request, _ident: Optional[Identity] = Depends(mutating)):
    body = await read_json(request)
    c = ctx(request)
    c.auth.request_magic(body.get("email"), body.get("mode", "cookie"), body.get("next"))
    return JSONResponse({"ok": True, "message": "If that address can receive mail, a sign-in link is on its way. "
                                                f"It is valid for {int(c.settings.magic_ttl_min)} minutes and works once."},
                        status_code=202)


@router.get("/auth/magic/{token}", dependencies=[Depends(limited("auth_consume"))])
def auth_magic_consume(token: str, request: Request):
    a = ctx(request).auth
    user, mode, next_path = a.consume_magic(token)
    return a.finish_login(user, mode, next_path)


@router.post("/auth/token", dependencies=[Depends(limited("auth_consume"))])
async def auth_token(request: Request, _ident: Optional[Identity] = Depends(mutating)):
    body = await read_json(request)
    token, expires, user = ctx(request).auth.redeem_login_code(body.get("code"))
    return JSONResponse({"token": token, "token_type": "bearer", "expires": iso(expires), "user": _user_view(user)},
                        headers={"Cache-Control": "no-store"})


@router.post("/logout")
def logout(request: Request, ident: Optional[Identity] = Depends(mutating)):
    a = ctx(request).auth
    if ident is not None:
        a.logout(ident)
    resp = JSONResponse({"ok": True})
    a.clear_cookie(resp)
    return resp


def _user_view(u: Dict[str, Any]) -> Dict[str, Any]:
    return {"id": u["id"], "orcid": u["orcid"], "github_id": u["github_id"], "email": u["email"], "name": u["name"],
            "created": u["created"]}


@router.get("/me")
def me(request: Request, ident: Identity = Depends(require_user)):
    c = ctx(request)
    today = day_key()
    used = c.db.quota_used(ident.user_id, today)
    return JSONResponse({"user": _user_view(ident.user), "session": {"via": ident.via, "expires": iso(ident.expires)},
                         "quota": {"day": today, "used_cpu_s": used, "limit_cpu_s": c.settings.quota_cpu_s_per_day}},
                        headers={"Cache-Control": "no-store"})


# ------------------------------------------------------------------ runs
@router.post("/runs", dependencies=[Depends(limited("runs_create"))])
async def runs_create(request: Request, ident: Optional[Identity] = Depends(mutating)):
    c = ctx(request)
    body = await read_json(request)
    inputs = prepare(body.get("scenario", "P2-default"), body.get("mechanism", "marketplace"), body.get("seeds"),
                     body.get("options"), c.settings.repo_root, c.settings.max_seeds)
    public = body.get("public", False)
    if not isinstance(public, bool):
        raise ServiceError(400, "'public' must be true or false")
    row = {"scenario_sha": inputs.scenario_sha, "scenario_json": inputs.scenario_text,
           "mechanism": inputs.mechanism, "options_json": canonical_json(inputs.options).decode("utf-8"),
           "seeds_json": json.dumps(inputs.seeds), "policy_shas_json": json.dumps(inputs.policy_shas, sort_keys=True),
           "parent_run_id": None, "public": int(public)}
    out = _enqueue(c, request, ident, row, len(inputs.seeds))
    out["scenario_sha"] = inputs.scenario_sha
    return JSONResponse(out, status_code=202)


@router.get("/runs", dependencies=[Depends(limited("public_list"))])
def runs_list(request: Request, public: int = 0, metric: Optional[str] = None, scenario: Optional[str] = None,
              mechanism: Optional[str] = None, status: Optional[str] = None, ranked: int = 0, order: str = "asc",
              limit: int = 50, offset: int = 0):
    c = ctx(request)
    ident = identity(request)
    where: List[str] = []
    params: List[Any] = []
    if public:
        where += ["public = 1", "status = 'done'"]
    else:
        if ident is None:
            raise ServiceError(401, "sign in to list your runs, or ask for public=1", "unauthorized")
        where.append("user_id = ?")
        params.append(ident.user_id)
    if scenario:
        where.append("json_extract(scenario_json, '$.name') = ?")
        params.append(scenario)
    if mechanism:
        where.append("mechanism = ?")
        params.append(mechanism)
    if status and not public:
        where.append("status = ?")
        params.append(status)
    if ranked:
        where.append(RANKED_SQL)
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    order_sql = "created DESC, id DESC"
    if metric:
        if not METRIC_RE.match(metric):
            raise ServiceError(400, "metric must be a summary metric name such as delay_prio1_mean_h")
        direction = "DESC" if order.lower() == "desc" else "ASC"
        where.append("json_extract(summary_json, '$.metrics.' || ? || '.mean') IS NOT NULL")
        params.append(metric)
        order_sql = f"json_extract(summary_json, '$.metrics.' || ? || '.mean') {direction}, created DESC"
    sql = f"SELECT * FROM runs WHERE {' AND '.join(where)} ORDER BY {order_sql} LIMIT ? OFFSET ?"
    sql_params = list(params) + ([metric] if metric else []) + [limit, offset]
    rows = c.db.all(sql, tuple(sql_params))
    total = c.db.count_runs(" AND ".join(where), tuple(params))
    base = c.settings.base_url
    views = [run_view(r, ident, base, full=False) for r in rows]
    if metric:
        for v in views:
            m = ((v.get("summary") or {}).get("metrics") or {}).get(metric)
            v["metric"] = {"name": metric, **m} if m else None
    return {"runs": views, "count": len(views), "total": total, "limit": limit, "offset": offset,
            "ranked_rule": RANKED_RULE}


@router.get("/runs/{run_id}", dependencies=[Depends(limited("runs_read"))])
def runs_get(run_id: str, request: Request):
    c = ctx(request)
    ident = identity(request)
    row = _get_run(c, run_id, ident)
    return run_view(row, ident, c.settings.base_url, full=True)


@router.get("/runs/{run_id}/summary", dependencies=[Depends(limited("runs_read"))])
def runs_summary(run_id: str, request: Request):
    c = ctx(request)
    row = _get_run(c, run_id, identity(request))
    if row["status"] != "done":
        raise ServiceError(409, f"run {run_id} is {row['status']}; the summary exists once it is done", "not_ready")
    doc = _loads(row["summary_json"], {})
    doc.update({"run_id": run_id, "status": row["status"], "scenario_sha": row["scenario_sha"]})
    return JSONResponse(doc, headers={"ETag": f'"{row["output_sha"]}"', "Cache-Control": "private, max-age=60"})


@router.get("/runs/{run_id}/trace", dependencies=[Depends(limited("runs_read"))])
def runs_trace(run_id: str, request: Request, seed: Optional[int] = None):
    c = ctx(request)
    row = _get_run(c, run_id, identity(request))
    if row["status"] != "done":
        raise ServiceError(409, f"run {run_id} is {row['status']}; traces exist once it is done", "not_ready")
    summary = _loads(row["summary_json"], {})
    traces: Dict[str, str] = summary.get("traces") or {}
    seeds = _loads(row["seeds_json"], [])
    if seed is None:
        seed = seeds[0] if seeds else 0
    sha = traces.get(str(seed))
    if sha is None:
        raise ServiceError(404, f"run {run_id} has no trace for seed {seed}; seeds: {seeds}", "not_found")
    blob = c.db.get_blob(sha)
    if blob is None:
        raise ServiceError(500, f"trace blob {sha} is missing", "blob_missing")
    path = Database.blob_path(c.settings.data_dir, blob)
    if not os.path.isfile(path):
        raise ServiceError(500, f"trace blob file {blob['path']} is missing", "blob_missing")
    return FileResponse(path, media_type="application/json",
                        headers={"ETag": f'"{sha}"', "X-Content-SHA256": sha,
                                 "Cache-Control": "public, max-age=31536000, immutable",
                                 "Content-Disposition": f'inline; filename="run-{run_id}-seed{seed}.json"'})


@router.get("/runs/{run_id}/events", dependencies=[Depends(limited("runs_read"))])
def runs_events(run_id: str, request: Request, after: Optional[int] = None):
    from .sse import sse_response
    c = ctx(request)
    _get_run(c, run_id, identity(request))
    last = request.headers.get("last-event-id")
    after_seq = int(after) if after is not None else (int(last) if last and last.isdigit() else 0)
    return sse_response(c.db, run_id, after_seq, c.settings.sse_poll_s, c.settings.sse_ping_s)


@router.post("/runs/{run_id}/replicate", dependencies=[Depends(limited("runs_create"))])
def runs_replicate(run_id: str, request: Request, ident: Optional[Identity] = Depends(mutating)):
    c = ctx(request)
    parent = _get_run(c, run_id, ident)
    if parent["status"] != "done":
        raise ServiceError(409, f"run {run_id} is {parent['status']}; only finished runs can be replicated", "not_ready")
    row = {"scenario_sha": parent["scenario_sha"], "scenario_json": parent["scenario_json"],
           "mechanism": parent["mechanism"], "options_json": parent["options_json"], "seeds_json": parent["seeds_json"],
           "policy_shas_json": parent["policy_shas_json"], "parent_run_id": parent["id"], "public": 0}
    out = _enqueue(c, request, ident, row, len(_loads(parent["seeds_json"], [])))
    out["parent_run_id"] = parent["id"]
    out["parent_output_sha"] = parent["output_sha"]
    return JSONResponse(out, status_code=202)


@router.post("/runs/{run_id}/publish", dependencies=[Depends(limited("runs_create"))])
async def runs_publish(run_id: str, request: Request, ident: Optional[Identity] = Depends(mutating)):
    c = ctx(request)
    if ident is None:
        raise ServiceError(401, "sign in to publish runs", "unauthorized")
    row = _get_run(c, run_id, ident)
    if not is_owner(row, ident):
        raise ServiceError(403, "only the owner can publish a run", "forbidden")
    if row["status"] != "done":
        raise ServiceError(409, f"run {run_id} is {row['status']}; only finished runs can be published", "not_ready")
    body = await read_json(request)
    public = body.get("public", True)
    if not isinstance(public, bool):
        raise ServiceError(400, "'public' must be true or false")
    c.db.update_run(run_id, public=int(public))
    c.db.add_event(run_id, "published" if public else "unpublished", {"by": ident.user_id})
    return run_view(c.db.get_run(run_id), ident, c.settings.base_url, full=False)


# ------------------------------------------------------------------ policies and terrain
@router.get("/policies", dependencies=[Depends(limited("data_read"))])
def policies_list(request: Request):
    return {"policies": provenance.list_policies(ctx(request).settings.repo_root)}


@router.get("/policies/{pid}", dependencies=[Depends(limited("data_read"))])
def policies_get(pid: str, request: Request):
    got = provenance.load_policy(ctx(request).settings.repo_root, pid)
    if got is None:
        raise ServiceError(404, f"no policy {pid}", "not_found")
    doc, sha, _ = got
    return JSONResponse(doc, headers={"ETag": f'"{sha}"', "X-Content-SHA256": sha, "Cache-Control": "public, max-age=3600"})


@router.get("/terrain", dependencies=[Depends(limited("data_read"))])
def terrain_list(request: Request):
    return {"terrain": provenance.list_terrain(ctx(request).settings.repo_root)}


@router.get("/terrain/{tid}", dependencies=[Depends(limited("data_read"))])
def terrain_get(tid: str, request: Request):
    doc = provenance.load_terrain(ctx(request).settings.repo_root, tid)
    if doc is None:
        raise ServiceError(404, f"no terrain pack {tid}", "not_found")
    base = ctx(request).settings.base_url
    doc["links"] = {name: f"{base}/v2/terrain/{tid}/files/{name}" for name in doc["files"]}
    return doc


@router.get("/terrain/{tid}/files/{name}", dependencies=[Depends(limited("data_read"))])
def terrain_file(tid: str, name: str, request: Request):
    path = provenance.terrain_file(ctx(request).settings.repo_root, tid, name)
    if path is None:
        raise ServiceError(404, f"no file {name} in terrain pack {tid}", "not_found")
    media = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media, headers={"Cache-Control": "public, max-age=86400"})
