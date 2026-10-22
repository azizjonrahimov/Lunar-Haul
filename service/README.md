# LunarSim service v2

The hosted, multi-user API behind the site (PLAN §5.6): sign-in, saved runs with full provenance, a
job queue executing the Python engine, live progress over Server-Sent Events, machine-checkable
replication, a public gallery. `lunarsim serve` (the stdlib local API) is unchanged and stays for
local, single-user use; this package is what runs on the VPS.

Stack, following `research_notes/.../backend_database_hosting.md`: FastAPI (ASGI) · SQLite in WAL mode
through the standard-library `sqlite3` · a DB-polling worker process · `sse-starlette` for SSE ·
Authlib for ORCID and GitHub OAuth plus e-mail magic links · opaque server-side sessions in
`HttpOnly; Secure; SameSite=Lax` cookies (bearer-token fallback) · in-memory token-bucket rate limits ·
per-account CPU-seconds-per-day quota · Caddy (automatic HTTPS) · Litestream replication of the
database to an S3-compatible bucket · one Hetzner CX23.

```
service/
  app.py          create_app(settings, mailer)  FastAPI factory, middleware, JSON error rendering
  api.py          every /v2 endpoint
  auth.py         sessions, cookies, CSRF rules, magic links, OAuth (Authlib), bearer login codes
  worker.py       prepare() a run request; Worker: claim -> execute per seed -> blobs -> output sha -> quota
  sse.py          /v2/runs/{id}/events stream
  db.py           schema and every SQL statement (sqlite3, WAL)
  provenance.py   engine version, git sha/dirty/patch, environment lock, policy-file shas; data discovery
  ratelimit.py    token buckets
  settings.py     every LUNARSIM_* variable with its default
  util.py         ULID, canonical JSON, hashing
  __main__.py     python -m service [serve|worker|version]
  Dockerfile  Caddyfile  litestream.yml  deploy/{lunarsim-api,lunarsim-worker,litestream}.service  deploy/env.example
tests/test_service.py   17 tests, in-process, no network (skipped when fastapi is missing)
```

## Run it locally

```
.venv\Scripts\python -m pip install -e .[service]      # or: pip install fastapi "uvicorn[standard]" authlib sse-starlette httpx python-multipart argon2-cffi
set LUNARSIM_COOKIE_SECURE=0                           # plain http on localhost; everything else has a safe default
.venv\Scripts\python -m service --port 8800            # API: http://127.0.0.1:8800/v2/health, docs at /v2/docs
.venv\Scripts\python -m service worker                 # second terminal: executes queued runs (same DB file)
```

Default data folder: `<repo>/service_data/` (`lunarsim.db` + `blobs/`), override with `LUNARSIM_DATA_DIR`.
Magic links are logged (`LUNARSIM_MAIL_MODE=log`), so sign in by copying the link from the API log.
`python -m service version` prints the provenance the API would record and the settings without secrets.
Tests: `.venv\Scripts\python -m pytest tests/test_service.py -q`.

A first run from the command line (the custom header is the CSRF defence, see below):

```
curl -s -X POST http://127.0.0.1:8800/v2/runs -H "Content-Type: application/json" -H "X-Requested-With: lunarsim" ^
  -d "{\"scenario\":\"P2-default\",\"mechanism\":\"marketplace\",\"seeds\":[0,1]}"
curl -s http://127.0.0.1:8800/v2/runs/<run_id>                 # status, provenance, summary once done
curl -N http://127.0.0.1:8800/v2/runs/<run_id>/events           # SSE: queued, running, progress x n, done
curl -s "http://127.0.0.1:8800/v2/runs/<run_id>/trace?seed=1"   # lunarsim-trace JSON, content-addressed
```

## API (base `/v2`)

Errors are always `{"error": "...", "code": "..."}`; 429 responses carry `Retry-After` (seconds).

| Method, path | Purpose | Notes |
|---|---|---|
| `GET /health` | liveness | service + engine versions, queue depth |
| `GET /version` | identity of the running code | engine_version (`2.0.0` on the tag, else `2.0.0+g<sha7>[.dirty]`), git sha, dirty, patch/lock shas, python, platform, policy and terrain ids, limits, rate limits, which sign-in providers are on |
| `GET /auth/{orcid\|github}/start?mode=cookie\|bearer&next=/path` | 302 to the provider | 503 `provider_unconfigured` when the client id/secret are unset |
| `GET /auth/{p}/callback?code&state` | provider returns here | state is server-side, single use, 10 min |
| `POST /auth/magic {email, mode?, next?}` | mail a sign-in link | 202 with the same message whether or not the address exists; 5/min per IP |
| `GET /auth/magic/{token}` | consume the link | single use, 15 min; cookie mode: sets the cookie and 303s to `APP_URL+next`; bearer mode: 303 to `APP_URL+next#login_code=...` |
| `POST /auth/token {code}` | bearer mode: exchange the one-time code | `{token, expires, user}`; the page keeps the token in memory and sends `Authorization: Bearer` |
| `POST /logout` | end the session | clears the cookie |
| `GET /me` | who am I | user, session (via cookie/bearer, expiry), today's quota |
| `POST /runs {scenario, mechanism, seeds[], options{terrain, pad_standoff_km, landing_model, plume, autonomy_model, opts}, public}` | enqueue | 202 `{run_id, status:"queued", estimate_cpu_s, quota, scenario_sha}`; `scenario` is a library name or a lunarsim-scenario v1 object (either form); `opts` are the marketplace flags as in `lunarsim serve` |
| `GET /runs/{id}` | the run record | status, provenance, options, seeds, summary (metrics + per-seed rows + trace shas), `replicated`, `ranked`, links |
| `GET /runs/{id}/events` | SSE | events `queued`, `running`, `progress` (per seed), `done`, `failed`, `replicated`, `published`; ids = seq, `Last-Event-ID` resumes; pings every 15 s |
| `GET /runs/{id}/trace?seed=N` | one lunarsim-trace document | blob by sha; `ETag`, `X-Content-SHA256`, immutable caching; default: first seed |
| `GET /runs/{id}/summary` | aggregated metrics + rows | 409 `not_ready` before the run is done |
| `POST /runs/{id}/replicate` | re-run with identical inputs | new run (owned by the caller) with `parent_run_id`; when it finishes the worker compares `output_sha` with the parent and writes `replicated` true/false on both |
| `POST /runs/{id}/publish {public?: bool}` | gallery visibility | owner only, finished runs only; `false` unpublishes |
| `GET /runs?public=1&metric=&scenario=&mechanism=&ranked=1&order=asc\|desc&limit=&offset=` | gallery / leaderboard | without `public=1` lists the caller's own runs (401 when anonymous); `metric` sorts by `summary.metrics.<name>.mean`; `ranked` = `git_dirty=false` on a tagged release |
| `GET /policies`, `GET /policies/{id}` | model cards and weights | every `lunarsim-policy` and `lunarsim-landing-outcomes` file under `data/policies/`, with sha256 |
| `GET /terrain`, `GET /terrain/{id}`, `GET /terrain/{id}/files/{name}` | terrain packs | meta, sites, per-file shas; the PNG layers are served from `/files/` |

Run statuses: `queued -> running -> done | failed`. Visibility: a run is readable by its owner, by anyone
when `public`, and by anyone holding the id when it was submitted anonymously (no owner to protect it;
ids are ULIDs with 80 random bits). Anonymous runs cannot be published.

### Provenance stored per run

`engine_version`, `git_sha`, `git_dirty`, `patch_sha` (sha256 of `git diff HEAD` when dirty; the patch is a
blob), `lock_sha` (sha256 of pyproject.toml + every installed distribution `name==version`; stored as a blob,
because the repository has no lockfile), `python`, `platform`, `scenario_sha`, `scenario_json`, `mechanism`,
`options_json`, `seeds_json`, `policy_shas_json` (sha256 of every data file the engine reads: landing-outcome
tables per lander class, driving table, terrain meta and sites), `output_sha`, `summary_json`, `cpu_s`.
The API records provisional provenance at enqueue; the worker overwrites the code/environment columns
with what it measured at execution time (that is the code that actually ran).

**Canonical JSON.** `scenario_sha` is the sha256 of the effective full-form scenario (request scenario with
the Phase-3 options applied) serialised with sorted keys, no whitespace, UTF-8, Python float repr, with one
exception that matters: the engine iterates `landings_per_year` in dict order when it draws the landing
schedule, so `{"CLPS":4,"MK1":3,"LARGE":1}` and its sorted spelling are different scenarios. That mapping
keeps the order it was written in, and the stored `scenario_json` is exactly the hashed text, so the worker
runs what was hashed. (This bit us in the first test: sorting it moved the P2-default seed-0 priority-1 delay
from 2.55 h to 3.08 h.)

**Output sha.** Each per-seed trace (`Simulation.trace_export`, NaN -> null, canonical JSON) is a
content-addressed blob under `<data_dir>/blobs/<sha[:2]>/<sha>`; identical traces are stored once. The
output document `{format:"lunarsim-run-output", version:1, scenario_sha, mechanism, seeds, rows, traces:{seed: sha}}`
is itself a blob and its sha256 is `output_sha`. It contains no timestamps, run ids or version strings, so
two runs with identical inputs on the same engine give the same `output_sha` and a replicate can be
checked by hash alone. A diverging child says both shas in its `replicated` event, with the engine
versions of both runs in the records.

### Limits and quotas

| Limit | Default | Setting |
|---|---|---|
| seeds per run | 100 | `LUNARSIM_MAX_SEEDS` |
| request body | 1 MiB | `LUNARSIM_MAX_BODY_BYTES` |
| queued + running runs per account (or IP) | 5 | `LUNARSIM_MAX_QUEUED_PER_USER` (429 `queue_full`) |
| CPU-seconds per day, signed in | 1800 (30 min) | `LUNARSIM_QUOTA_CPU_S_PER_DAY` |
| CPU-seconds per day, anonymous, per IP | 300 | `LUNARSIM_QUOTA_ANON_CPU_S_PER_DAY` (set `LUNARSIM_ALLOW_ANON_RUNS=0` to require sign-in) |
| reservation per seed at enqueue | 1.0 s | `LUNARSIM_CPU_S_PER_SEED_ESTIMATE` |

The quota is enforced at enqueue: today's used CPU-seconds (UTC day) plus the reservation for the new run
must stay under the budget, else 429 `quota_exceeded` with `Retry-After` = seconds to midnight UTC. When the
run finishes the worker replaces the reservation with the measured `time.process_time()`, so cheap runs
give the budget back. A v2 P2-default year takes about 0.3 CPU-s per seed on a laptop; Phase-3 runs with
terrain legs take longer.

Rate limits (token bucket per signed-in user, else per IP; override with `LUNARSIM_RATE_LIMITS` JSON):
`auth_magic` 5/min, `auth_start` 20/min, `auth_consume` 20/min, `runs_create` 10/min (also replicate and
publish), `runs_read` 120/min, `public_list` 60/min, `data_read` 120/min, `default` 240/min.

### Cookies, origins, CSRF (why the custom domain is required)

The session cookie is `lunarsim_session=<256-bit token>; HttpOnly; Secure; SameSite=Lax; Path=/` with no
`Domain` attribute. `github.io` is on the Public Suffix List, so a page on `<user>.github.io` and an API on
any other host are different *sites*: the cookie would be a third-party cookie, blocked by Safari, Firefox
and Brave. Put the site on `app.<domain>` (GitHub Pages custom domain, CNAME) and the API on `api.<domain>`:
same registrable domain, so the cookie is same-site for `fetch(..., {credentials: "include"})`.

CORS: explicit allow-list (`LUNARSIM_ALLOWED_ORIGINS`; the `LUNARSIM_APP_URL` origin is always included) with
`Access-Control-Allow-Credentials: true`, never `*`. Chrome's Private Network Access preflight
(`Access-Control-Request-Private-Network`) is answered with `Access-Control-Allow-Private-Network: true`, as
`lunarsim/server.py` does, so an https page can talk to a local API.

CSRF: every state-changing request (all POSTs) must carry `X-Requested-With: lunarsim`; a request that has
an `Origin` header must have one on the allow-list; a cookie-authenticated request must have an `Origin`
header at all (OWASP: a missing Origin is not evidence of a same-origin request). Bearer-authenticated and
anonymous requests may omit `Origin` (curl, scripts); the custom header still forces a CORS preflight.

Bearer fallback for `github.io`: start the login with `mode=bearer`; the login ends with a redirect to
`APP_URL#login_code=...`; the page POSTs the code to `/v2/auth/token` within 2 minutes and keeps the returned
session token in memory (not localStorage), sending `Authorization: Bearer <token>`.

### Sign-in providers

- ORCID: register a Public API client at orcid.org (Developer tools), redirect URI
  `https://api.<domain>/v2/auth/orcid/callback` (exact match, https only); set `LUNARSIM_ORCID_CLIENT_ID/SECRET`,
  `LUNARSIM_ORCID_SANDBOX=1` while testing against sandbox.orcid.org. Scope `/authenticate`; the token response
  carries the iD and name, which are stored on the user (ORCID gives no e-mail with this scope).
- GitHub: an OAuth App with callback `https://api.<domain>/v2/auth/github/callback`; scope `read:user user:email`.
  The primary *verified* e-mail links the GitHub identity to an existing magic-link account with that address.
- Magic links: `LUNARSIM_MAIL_MODE=smtp` with `LUNARSIM_SMTP_*` and `LUNARSIM_MAIL_FROM`. Tokens are 256-bit,
  stored as sha256, single use, 15 minutes.

Sessions last `LUNARSIM_SESSION_TTL_H` (default 7 days, absolute); the DB keeps only sha256(token).

## Deploy on one Hetzner CX23 (Caddy + systemd + Litestream)

Owner decisions first (PLAN §8): the domain, the ORCID/GitHub registrations, an SMTP sender, an S3-compatible
bucket for backups.

1. **Server.** CX23 (2 vCPU, 4 GB, Ubuntu 24.04). `apt install git python3.12-venv caddy` (Caddy from its apt
   repo: https://caddyserver.com/docs/install), Litestream from its .deb release. Create the user and folders:
   ```
   useradd -r -m -d /srv/lunarsim lunarsim
   mkdir -p /var/lib/lunarsim /etc/lunarsim && chown lunarsim:lunarsim /var/lib/lunarsim
   sudo -u lunarsim git clone https://github.com/azizjonrahimov/Lunar-Haul /srv/lunarsim/repo
   sudo -u lunarsim python3.12 -m venv /srv/lunarsim/venv
   sudo -u lunarsim /srv/lunarsim/venv/bin/pip install -e "/srv/lunarsim/repo[service]"
   ```
   Check out a tagged release (`git checkout v2.x.y`) and keep the tree clean: only `git_dirty=false` runs on a
   tag rank in the leaderboard. (The terrain pack `data/terrain/connecting_ridge/` must exist in the checkout
   for terrain runs; the policies and driving tables are committed.)
2. **DNS.** `api.<domain>` A/AAAA -> the VPS. `app.<domain>` CNAME -> `<user>.github.io`, and set the custom
   domain in the Pages settings (verify the domain to prevent takeover). The site must call
   `https://api.<domain>`.
3. **Environment.** `cp service/deploy/env.example /etc/lunarsim/env`, fill it in, `chmod 600`. At least
   `LUNARSIM_BASE_URL`, `LUNARSIM_APP_URL`, `LUNARSIM_ALLOWED_ORIGINS`, `LUNARSIM_TRUST_PROXY=1`, the mail
   settings, and whichever providers are registered.
4. **Caddy.** `cp service/Caddyfile /etc/caddy/Caddyfile`, set `DOMAIN=<domain>` in `/etc/caddy/environment`
   (or replace `{$DOMAIN}`), `systemctl reload caddy`. Caddy obtains and renews the certificate; the Caddyfile
   disables buffering on the SSE path and forwards `X-Forwarded-For`.
5. **Services.** `cp service/deploy/*.service /etc/systemd/system/`, `systemctl daemon-reload`,
   `systemctl enable --now lunarsim-api lunarsim-worker litestream`. The API binds 127.0.0.1:8800 behind Caddy;
   the worker runs under a CPU quota so it cannot starve the API on two vCPUs. `journalctl -u lunarsim-worker -f`
   shows run progress. One worker is the sane default on a CX23; a second one is just another unit with a
   different `LUNARSIM_WORKER_ID` (claims are atomic).
6. **Backups.** Litestream replicates `lunarsim.db` continuously (config `service/litestream.yml`, credentials
   from the env file). The `blobs/` folder is not in the database: add a cron job such as
   `rclone sync /var/lib/lunarsim/blobs s3bucket:lunarsim/blobs` (hourly). Restore:
   `litestream restore -config service/litestream.yml -o /var/lib/lunarsim/lunarsim.db /var/lib/lunarsim/lunarsim.db`
   then `rclone sync` the blobs back.
7. **Upgrade.** `git fetch && git checkout vX.Y.Z && pip install -e ".[service]"`, `systemctl restart lunarsim-api
   lunarsim-worker`. The schema is created with `CREATE TABLE IF NOT EXISTS`; there are no migrations yet
   (see below).
8. **Check.** `curl https://api.<domain>/v2/health`, `.../v2/version` (expect `git_dirty: false` and an
   engine_version without `+`), then a run from the site's Account page.

Docker is an alternative to steps 1 and 5 (`service/Dockerfile`; one image, `python -m service` for the API and
`python -m service worker` for the executor, sharing a volume at `/var/lib/lunarsim`); Caddy and Litestream
stay on the host or in sidecars.

## How /replicate works

`POST /v2/runs/{id}/replicate` copies the parent's `scenario_json`, `mechanism`, `options_json`, `seeds_json`
and `policy_shas_json` into a new queued run owned by the caller with `parent_run_id` set; the caller pays
the quota. The worker executes it exactly like any run (it rebuilds the engine call from the stored record,
never from the request), and when the child is done it compares the two `output_sha` values and writes
`replicated = true|false` on **both** rows plus a `replicated` event on both event streams carrying both
shas. A parent therefore shows the verdict of its most recent replication. Because every trace is
content-addressed, an identical replicate costs no extra blob storage.

## Departures from PLAN §5.6, and why

1. **sqlite3 instead of SQLAlchemy.** The note's primary stack says "FastAPI + SQLAlchemy on SQLite"; with
   nine fixed tables and plain SQL the ORM buys nothing, and the stdlib driver keeps the service dependency-light.
   All SQL is in `db.py`.
2. **Extra columns on `runs`:** `started`, `finished`, `error`, `replicated`, `worker`, `anon_key`. The PLAN row
   has no place for the replication verdict it asks for, the failure text, or the anonymous quota key.
3. **Extra tables:** `magic_links`, `oauth_states`, `login_codes` (auth bookkeeping the PLAN schema omits).
   `sessions.id` holds sha256(token), not the token.
4. **Canonical JSON is not fully sorted:** `landings_per_year` keeps its order (explained above). Without this
   the service would silently run a different scenario from `lunarsim run`.
5. **Anonymous runs are allowed** (per-IP quota, cannot be published, readable by link). PLAN mentions
   Turnstile on sign-up as an owner decision; nothing in it forbids anonymous runs, and the Lab pages are
   usable without an account. Set `LUNARSIM_ALLOW_ANON_RUNS=0` to require sign-in.
6. **`POST /v2/auth/token`** and the `mode=bearer` query parameter were added for the github.io fallback the
   PLAN asks for ("fallback bearer token for the github.io origin") - a login has to hand the token to the
   page somehow, and a one-time code in the URL fragment is the way that never puts the token in a server log.
7. **`GET /v2/terrain/{id}/files/{name}`** was added so the viewer can load the PNG layers from the API.
8. **Trace per seed:** `GET /runs/{id}/trace?seed=N` returns one lunarsim-trace document (the viewer replays
   one), the run's output blob holds the per-seed trace shas. PLAN says "trace (blob)" without saying how a
   multi-seed run maps to it.
9. **`engine_version`** carries the PEP 440 local part (`+g<sha7>[.dirty]`) when not on a clean tag; the
   leaderboard filter `ranked` is derived from it and `git_dirty`.
10. **Rate limits are per process, in memory** (no Redis), which is what the note recommends to start; with
    `uvicorn --workers > 1` each process has its own buckets.

## What is NOT done

- **Turnstile** on sign-up / anonymous submission (owner decision in PLAN; the hook is `POST /v2/runs` and
  `POST /v2/auth/magic`).
- **Zenodo deposit** of a run bundle; `runs.doi` exists but nothing writes it.
- **Passkeys**, passwords (hence `argon2-cffi` is installed but unused), account deletion, e-mail change.
- **Schema migrations**: the schema is created if missing; a future column needs an `ALTER TABLE` step.
- **Blob replication** is a cron job, not Litestream (which only handles the SQLite file); no storage quota
  or TTL for private runs yet.
- **Cancel** for queued runs; the worker executes runs strictly in order.
- **Live OAuth** against ORCID/GitHub was not exercised (no credentials in this environment); tests cover the
  redirect, the state check and the error paths. The ORCID token-response field names (`orcid`, `name`) and
  the GitHub `/user`, `/user/emails` calls follow the providers' documentation.
- `uvicorn --workers > 1` and multiple API processes: fine for the DB (WAL), but the rate-limit buckets are
  per process.
- Add `service_data/` to `.gitignore` (LEAD-owned file) so a local run does not show up in `git status`.
