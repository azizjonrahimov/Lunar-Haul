"""Service settings from environment variables (prefix LUNARSIM_), with safe local defaults.

Every value is documented in service/README.md. Nothing here reads files; `Settings.from_env()`
is the only constructor the runners use, and tests build `Settings(...)` directly.
"""
from __future__ import annotations

import dataclasses
import json
import os
import socket
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlsplit

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)

# Per-route request limits (token bucket per client; a client is the signed-in user or the IP).
DEFAULT_RATE_LIMITS: Dict[str, str] = {
    "default": "240/minute",        # anything not named below
    "auth_start": "20/minute",      # OAuth redirects
    "auth_magic": "5/minute",       # magic-link e-mails (OWASP: tight, brute-force surface)
    "auth_consume": "20/minute",    # magic-link / login-code consumption
    "runs_create": "10/minute",     # POST /v2/runs and /replicate
    "runs_read": "120/minute",      # GET run, summary, trace, events
    "public_list": "60/minute",     # gallery / leaderboard
    "data_read": "120/minute",      # policies, terrain
}


def _bool(v: Optional[str], default: bool) -> bool:
    if v is None or v == "":
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _int(v: Optional[str], default: int) -> int:
    return default if v in (None, "") else int(v)


def _float(v: Optional[str], default: float) -> float:
    return default if v in (None, "") else float(v)


def _list(v: Optional[str]) -> List[str]:
    return [x.strip().rstrip("/") for x in (v or "").split(",") if x.strip()]


def origin_of(url: str) -> str:
    u = urlsplit(url)
    return f"{u.scheme}://{u.netloc}"


@dataclass
class Settings:
    # storage
    data_dir: str = os.path.join(REPO_ROOT, "service_data")
    db_path: Optional[str] = None                      # default <data_dir>/lunarsim.db
    repo_root: str = REPO_ROOT                         # git provenance, data/ folders, scenario library
    # URLs and origins
    base_url: str = "http://127.0.0.1:8800"            # public URL of this API (OAuth callbacks, magic links)
    app_url: str = "http://localhost:5173"             # where sign-in redirects back to (the site)
    allowed_origins: List[str] = field(default_factory=list)   # CORS allow-list; the app_url origin is always added
    trust_proxy: bool = False                          # take the client IP from X-Forwarded-For (behind Caddy)
    # sessions and cookies
    cookie_name: str = "lunarsim_session"
    cookie_secure: bool = True                         # set 0 only for plain-http local development
    session_ttl_h: float = 24.0 * 7                    # absolute session lifetime
    magic_ttl_min: float = 15.0                        # magic-link validity
    login_code_ttl_s: float = 120.0                    # one-time code exchanged for a bearer token
    oauth_state_ttl_s: float = 600.0
    csrf_header_value: str = "lunarsim"                # X-Requested-With on state-changing requests
    # OAuth providers (unset = provider disabled; /start answers 503)
    orcid_client_id: Optional[str] = None
    orcid_client_secret: Optional[str] = None
    orcid_sandbox: bool = False
    github_client_id: Optional[str] = None
    github_client_secret: Optional[str] = None
    # mail for magic links
    mail_mode: str = "log"                             # log | smtp
    mail_from: str = "LunarSim <no-reply@localhost>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_starttls: bool = True
    # limits and quotas
    max_seeds: int = 100
    max_body_bytes: int = 1 << 20
    max_queued_per_user: int = 5
    quota_cpu_s_per_day: float = 1800.0                # signed-in accounts: 30 CPU-minutes/day
    quota_anon_cpu_s_per_day: float = 300.0            # anonymous (per IP): 5 CPU-minutes/day
    cpu_s_per_seed_estimate: float = 1.0               # reserved at enqueue, corrected when the run finishes
    allow_anonymous_runs: bool = True
    rate_limits: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_RATE_LIMITS))
    # worker
    worker_id: str = field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    worker_poll_s: float = 1.0
    worker_stale_s: float = 3600.0                     # a running run older than this is re-queued at worker start
    # SSE
    sse_ping_s: float = 15.0
    sse_poll_s: float = 0.5
    log_level: str = "INFO"

    # ------------------------------------------------------------------ derived
    def __post_init__(self):
        self.data_dir = os.path.abspath(self.data_dir)
        if not self.db_path:
            self.db_path = os.path.join(self.data_dir, "lunarsim.db")
        self.base_url = self.base_url.rstrip("/")
        self.app_url = self.app_url.rstrip("/")
        origins = [o.rstrip("/") for o in self.allowed_origins]
        app_origin = origin_of(self.app_url)
        if app_origin not in origins:
            origins.append(app_origin)
        self.allowed_origins = origins
        merged = dict(DEFAULT_RATE_LIMITS)
        merged.update(self.rate_limits or {})
        self.rate_limits = merged

    @property
    def blob_dir(self) -> str:
        return os.path.join(self.data_dir, "blobs")

    @property
    def api_origin(self) -> str:
        return origin_of(self.base_url)

    def provider(self, name: str) -> Optional[dict]:
        """OAuth provider config or None when not configured."""
        if name == "orcid" and self.orcid_client_id and self.orcid_client_secret:
            host = "https://sandbox.orcid.org" if self.orcid_sandbox else "https://orcid.org"
            return {"client_id": self.orcid_client_id, "client_secret": self.orcid_client_secret,
                    "authorize_url": f"{host}/oauth/authorize", "token_url": f"{host}/oauth/token",
                    "scope": "/authenticate", "api": host}
        if name == "github" and self.github_client_id and self.github_client_secret:
            return {"client_id": self.github_client_id, "client_secret": self.github_client_secret,
                    "authorize_url": "https://github.com/login/oauth/authorize",
                    "token_url": "https://github.com/login/oauth/access_token",
                    "scope": "read:user user:email", "api": "https://api.github.com"}
        return None

    def public_dict(self) -> dict:
        """Settings safe to show (no secrets); used by GET /v2/version."""
        d = dataclasses.asdict(self)
        for k in list(d):
            if "secret" in k or "password" in k:
                d[k] = bool(d[k])
        return d

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "Settings":
        e = os.environ if env is None else env

        def g(k, d=None):
            return e.get("LUNARSIM_" + k, d)

        kw = dict(
            data_dir=g("DATA_DIR", cls.data_dir), db_path=g("DB_PATH") or None, repo_root=g("REPO_ROOT", REPO_ROOT),
            base_url=g("BASE_URL", cls.base_url), app_url=g("APP_URL", cls.app_url),
            allowed_origins=_list(g("ALLOWED_ORIGINS")), trust_proxy=_bool(g("TRUST_PROXY"), False),
            cookie_name=g("COOKIE_NAME", cls.cookie_name), cookie_secure=_bool(g("COOKIE_SECURE"), True),
            session_ttl_h=_float(g("SESSION_TTL_H"), cls.session_ttl_h),
            magic_ttl_min=_float(g("MAGIC_TTL_MIN"), cls.magic_ttl_min),
            orcid_client_id=g("ORCID_CLIENT_ID") or None, orcid_client_secret=g("ORCID_CLIENT_SECRET") or None,
            orcid_sandbox=_bool(g("ORCID_SANDBOX"), False),
            github_client_id=g("GITHUB_CLIENT_ID") or None, github_client_secret=g("GITHUB_CLIENT_SECRET") or None,
            mail_mode=g("MAIL_MODE", "log"), mail_from=g("MAIL_FROM", cls.mail_from),
            smtp_host=g("SMTP_HOST", "localhost"), smtp_port=_int(g("SMTP_PORT"), 587),
            smtp_user=g("SMTP_USER") or None, smtp_password=g("SMTP_PASSWORD") or None,
            smtp_starttls=_bool(g("SMTP_STARTTLS"), True),
            max_seeds=_int(g("MAX_SEEDS"), 100), max_body_bytes=_int(g("MAX_BODY_BYTES"), 1 << 20),
            max_queued_per_user=_int(g("MAX_QUEUED_PER_USER"), 5),
            quota_cpu_s_per_day=_float(g("QUOTA_CPU_S_PER_DAY"), 1800.0),
            quota_anon_cpu_s_per_day=_float(g("QUOTA_ANON_CPU_S_PER_DAY"), 300.0),
            cpu_s_per_seed_estimate=_float(g("CPU_S_PER_SEED_ESTIMATE"), 1.0),
            allow_anonymous_runs=_bool(g("ALLOW_ANON_RUNS"), True),
            rate_limits=json.loads(g("RATE_LIMITS") or "{}"),
            worker_poll_s=_float(g("WORKER_POLL_S"), 1.0), worker_stale_s=_float(g("WORKER_STALE_S"), 3600.0),
            sse_ping_s=_float(g("SSE_PING_S"), 15.0), log_level=g("LOG_LEVEL", "INFO"),
        )
        wid = g("WORKER_ID")
        if wid:
            kw["worker_id"] = wid
        return cls(**kw)
