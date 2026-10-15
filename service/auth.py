"""Sign-in: ORCID and GitHub OAuth (Authlib), e-mail magic links, server-side sessions.

Sessions   opaque 256-bit tokens; the database keeps sha256(token) with the user id and an absolute
           expiry. The token travels either as the HttpOnly; Secure; SameSite=Lax cookie (same-site
           deployments: app.<domain> + api.<domain>) or as ``Authorization: Bearer <token>`` (the
           github.io fallback, where cookies would be third-party and blocked).
Magic link POST /v2/auth/magic {email} stores sha256(token) with a 15 minute expiry and mails
           BASE_URL/v2/auth/magic/<token>; GET consumes it once (single use), creates/finds the user by
           e-mail and finishes the login. The response is the same whether or not the address exists.
OAuth      GET /v2/auth/{orcid|github}/start -> provider; GET .../callback?code&state. The state is
           stored server-side (single use, 10 minutes) so no cookie is needed during the dance. ORCID
           returns the iD and name in the token response (scope /authenticate); GitHub needs a
           /user call and /user/emails for the primary verified address.
Bearer     a login in ``mode=bearer`` ends with a redirect to APP_URL#login_code=<one-time code>; the
           page exchanges it at POST /v2/auth/token for the session token and keeps it in memory.
CSRF       state-changing requests must carry ``X-Requested-With: lunarsim`` (forces a CORS preflight)
           and, when authenticated by cookie, an Origin header on the allow-list (OWASP: a missing
           Origin is not evidence of a same-origin request). Bearer requests are not CSRF-able.
"""
from __future__ import annotations

import logging
import re
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote, urlsplit

from starlette.requests import Request
from starlette.responses import RedirectResponse, Response

from .db import Database
from .errors import ServiceError
from .settings import Settings
from .util import new_token, now, sha256_text, ulid

log = logging.getLogger("service.auth")

EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]+$")
MODES = ("cookie", "bearer")


# ---------------------------------------------------------------------------------------------------------
# mail
# ---------------------------------------------------------------------------------------------------------
class Mailer:
    def send(self, to: str, subject: str, text: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class LogMailer(Mailer):
    """Development default: the message (with the link) goes to the log, nothing is sent."""

    def send(self, to: str, subject: str, text: str) -> None:
        log.info("MAIL to=%s subject=%r\n%s", to, subject, text)


class ListMailer(Mailer):
    """Collects messages in memory (tests)."""

    def __init__(self):
        self.sent: List[Dict[str, str]] = []

    def send(self, to: str, subject: str, text: str) -> None:
        self.sent.append({"to": to, "subject": subject, "text": text})


class SmtpMailer(Mailer):
    def __init__(self, s: Settings):
        self.s = s

    def send(self, to: str, subject: str, text: str) -> None:
        msg = EmailMessage()
        msg["From"] = self.s.mail_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(text)
        with smtplib.SMTP(self.s.smtp_host, self.s.smtp_port, timeout=20) as smtp:
            if self.s.smtp_starttls:
                smtp.starttls()
            if self.s.smtp_user:
                smtp.login(self.s.smtp_user, self.s.smtp_password or "")
            smtp.send_message(msg)


def make_mailer(s: Settings) -> Mailer:
    return SmtpMailer(s) if s.mail_mode == "smtp" else LogMailer()


# ---------------------------------------------------------------------------------------------------------
# identity
# ---------------------------------------------------------------------------------------------------------
@dataclass
class Identity:
    user_id: str
    user: Dict[str, Any]
    via: str              # "cookie" | "bearer"
    sid_sha: str
    expires: float


class Auth:
    def __init__(self, settings: Settings, db: Database, mailer: Optional[Mailer] = None):
        self.s = settings
        self.db = db
        self.mailer = mailer or make_mailer(settings)

    # ------------------------------------------------------------------ sessions
    def new_session(self, user_id: str) -> Tuple[str, float]:
        token = new_token(32)
        expires = now() + self.s.session_ttl_h * 3600.0
        self.db.create_session(sha256_text(token), user_id, expires)
        return token, expires

    def resolve(self, request: Request) -> Optional[Identity]:
        """The signed-in identity of a request (bearer header first, then the cookie), or None."""
        via, token = None, None
        authz = request.headers.get("authorization", "")
        if authz.lower().startswith("bearer "):
            via, token = "bearer", authz[7:].strip()
        elif self.s.cookie_name in request.cookies:
            via, token = "cookie", request.cookies[self.s.cookie_name]
        if not token or len(token) > 256:
            return None
        sid_sha = sha256_text(token)
        sess = self.db.get_session(sid_sha)
        if sess is None:
            return None
        user = self.db.get_user(sess["user_id"])
        if user is None:
            self.db.delete_session(sid_sha)
            return None
        return Identity(user_id=user["id"], user=dict(user), via=via or "cookie", sid_sha=sid_sha,
                        expires=float(sess["expires"]))

    def set_cookie(self, response: Response, token: str, expires: float) -> None:
        response.set_cookie(self.s.cookie_name, token, max_age=int(max(1, expires - now())), path="/",
                            secure=self.s.cookie_secure, httponly=True, samesite="lax")

    def clear_cookie(self, response: Response) -> None:
        response.delete_cookie(self.s.cookie_name, path="/", secure=self.s.cookie_secure, httponly=True,
                               samesite="lax")

    def logout(self, ident: Identity) -> None:
        self.db.delete_session(ident.sid_sha)

    # ------------------------------------------------------------------ users
    def user_for_email(self, email: str, name: Optional[str] = None) -> Dict[str, Any]:
        row = self.db.find_user(email=email)
        if row is None:
            row = self.db.create_user(ulid(), email=email, name=name)
        return dict(row)

    def user_for_provider(self, provider: str, pid: str, *, email: Optional[str], name: Optional[str],
                          email_verified: bool) -> Dict[str, Any]:
        col = {"orcid": "orcid", "github": "github_id"}[provider]
        row = self.db.find_user(**{col: pid})
        if row is None and email and email_verified:
            row = self.db.find_user(email=email)      # link a verified provider e-mail to an existing account
            if row is not None:
                self.db.update_user(row["id"], **{col: pid})
                row = self.db.get_user(row["id"])
        if row is None:
            kw: Dict[str, Any] = {col: pid, "name": name}
            if email and email_verified and self.db.find_user(email=email) is None:
                kw["email"] = email
            row = self.db.create_user(ulid(), **kw)
        elif name and not row["name"]:
            self.db.update_user(row["id"], name=name)
            row = self.db.get_user(row["id"])
        return dict(row)

    # ------------------------------------------------------------------ magic links
    @staticmethod
    def normalise_email(email: Any) -> str:
        if not isinstance(email, str):
            raise ServiceError(400, "'email' must be a string", "invalid_email")
        e = email.strip().lower()
        if len(e) > 254 or not EMAIL_RE.match(e):
            raise ServiceError(400, "'email' is not a valid address", "invalid_email")
        return e

    def request_magic(self, email: str, mode: str = "cookie", next_path: Optional[str] = None) -> str:
        """Create and mail a single-use link. Returns the link (callers must not expose it)."""
        email = self.normalise_email(email)
        mode = self.check_mode(mode)
        token = new_token(32)
        self.db.put_magic(sha256_text(token), email, mode, self.safe_next(next_path), self.s.magic_ttl_min * 60.0)
        link = f"{self.s.base_url}/v2/auth/magic/{token}"
        minutes = int(self.s.magic_ttl_min)
        text = (f"Sign in to LunarSim with this link (valid for {minutes} minutes, usable once):\n\n{link}\n\n"
                "If you did not request it, ignore this message; nothing happens without the link.\n")
        self.mailer.send(email, "Your LunarSim sign-in link", text)
        return link

    def consume_magic(self, token: str) -> Tuple[Dict[str, Any], str, Optional[str]]:
        if not token or len(token) > 256:
            raise ServiceError(400, "invalid or expired sign-in link", "invalid_token")
        row = self.db.consume_magic(sha256_text(token))
        if row is None:
            raise ServiceError(400, "invalid or expired sign-in link", "invalid_token")
        user = self.user_for_email(row["email"])
        return user, row["mode"], row["next"]

    # ------------------------------------------------------------------ one-time login codes (bearer mode)
    def issue_login_code(self, user_id: str) -> str:
        code = new_token(32)
        self.db.put_login_code(sha256_text(code), user_id, self.s.login_code_ttl_s)
        return code

    def redeem_login_code(self, code: Any) -> Tuple[str, float, Dict[str, Any]]:
        if not isinstance(code, str) or not code or len(code) > 256:
            raise ServiceError(400, "invalid or expired login code", "invalid_code")
        row = self.db.consume_login_code(sha256_text(code))
        if row is None:
            raise ServiceError(400, "invalid or expired login code", "invalid_code")
        user = self.db.get_user(row["user_id"])
        if user is None:
            raise ServiceError(400, "invalid or expired login code", "invalid_code")
        token, expires = self.new_session(user["id"])
        return token, expires, dict(user)

    # ------------------------------------------------------------------ OAuth (Authlib)
    def provider_config(self, provider: str) -> Dict[str, Any]:
        if provider not in ("orcid", "github"):
            raise ServiceError(404, f"unknown sign-in provider '{provider}'", "unknown_provider")
        cfg = self.s.provider(provider)
        if cfg is None:
            raise ServiceError(503, f"sign-in with {provider} is not configured on this server", "provider_unconfigured")
        return cfg

    def _client(self, provider: str, cfg: Dict[str, Any]):
        try:
            from authlib.integrations.httpx_client import OAuth2Client
        except ImportError as e:  # pragma: no cover
            raise ServiceError(503, "authlib is not installed", "provider_unconfigured") from e
        return OAuth2Client(cfg["client_id"], cfg["client_secret"], scope=cfg["scope"],
                            redirect_uri=f"{self.s.base_url}/v2/auth/{provider}/callback", timeout=20.0)

    def oauth_start_url(self, provider: str, mode: str = "cookie", next_path: Optional[str] = None) -> str:
        cfg = self.provider_config(provider)
        mode = self.check_mode(mode)
        state = new_token(24)
        self.db.put_state(state, provider, mode, self.safe_next(next_path), self.s.oauth_state_ttl_s)
        client = self._client(provider, cfg)
        try:
            url, _ = client.create_authorization_url(cfg["authorize_url"], state=state)
        finally:
            client.close()
        return url

    def oauth_callback(self, provider: str, code: Optional[str], state: Optional[str],
                       error: Optional[str] = None) -> Tuple[Dict[str, Any], str, Optional[str]]:
        cfg = self.provider_config(provider)
        if error:
            raise ServiceError(400, f"{provider} refused the sign-in: {error}", "oauth_denied")
        if not state or not code:
            raise ServiceError(400, "missing code or state", "oauth_state")
        st = self.db.consume_state(state, provider)
        if st is None:
            raise ServiceError(400, "unknown or expired OAuth state; start the sign-in again", "oauth_state")
        client = self._client(provider, cfg)
        try:
            token = client.fetch_token(cfg["token_url"], code=code, state=state, grant_type="authorization_code",
                                       headers={"Accept": "application/json"})
            if provider == "orcid":
                pid = str(token.get("orcid") or "")
                if not pid:
                    raise ServiceError(502, "ORCID did not return an iD", "oauth_provider")
                user = self.user_for_provider("orcid", pid, email=None, name=token.get("name"), email_verified=False)
            else:
                r = client.get(f"{cfg['api']}/user", headers={"Accept": "application/vnd.github+json"})
                r.raise_for_status()
                gh = r.json()
                pid = str(gh.get("id") or "")
                if not pid:
                    raise ServiceError(502, "GitHub did not return a user id", "oauth_provider")
                email, verified = gh.get("email"), False
                try:
                    r2 = client.get(f"{cfg['api']}/user/emails", headers={"Accept": "application/vnd.github+json"})
                    if r2.status_code == 200:
                        for e in r2.json():
                            if e.get("primary") and e.get("verified"):
                                email, verified = e.get("email"), True
                                break
                except Exception:  # the e-mail scope may be missing; sign-in still works
                    pass
                user = self.user_for_provider("github", pid, email=(email or "").lower() or None,
                                              name=gh.get("name") or gh.get("login"), email_verified=verified)
        except ServiceError:
            raise
        except Exception as e:
            log.warning("oauth %s callback failed: %s", provider, e)
            raise ServiceError(502, f"{provider} sign-in failed: {type(e).__name__}", "oauth_provider")
        finally:
            client.close()
        return user, st["mode"], st["next"]

    # ------------------------------------------------------------------ finishing a login
    def finish_login(self, user: Dict[str, Any], mode: str, next_path: Optional[str]) -> Response:
        """Cookie mode: set the session cookie and redirect to the app. Bearer mode: redirect to the app
        with a one-time code in the URL fragment (never sent to any server) for POST /v2/auth/token."""
        target = self.s.app_url + (self.safe_next(next_path) or "")
        if mode == "bearer":
            code = self.issue_login_code(user["id"])
            resp = RedirectResponse(f"{target}#login_code={quote(code)}", status_code=303)
        else:
            token, expires = self.new_session(user["id"])
            resp = RedirectResponse(target, status_code=303)
            self.set_cookie(resp, token, expires)
        resp.headers["Cache-Control"] = "no-store"
        resp.headers["Referrer-Policy"] = "no-referrer"
        return resp

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def check_mode(mode: Any) -> str:
        mode = mode or "cookie"
        if mode not in MODES:
            raise ServiceError(400, "mode must be 'cookie' or 'bearer'", "invalid_mode")
        return mode

    @staticmethod
    def safe_next(next_path: Any) -> Optional[str]:
        """Only a same-site path ('/account', '/world?run=...'); anything else is dropped."""
        if not isinstance(next_path, str) or not next_path:
            return None
        if not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path or len(next_path) > 512:
            return None
        if urlsplit(next_path).netloc:
            return None
        return next_path

    # ------------------------------------------------------------------ CSRF
    def csrf_check(self, request: Request, ident: Optional[Identity]) -> None:
        """For state-changing requests: custom header always; Origin on the allow-list whenever one is present,
        and required when the request is authenticated by cookie."""
        hdr = request.headers.get("x-requested-with", "")
        if hdr != self.s.csrf_header_value:
            raise ServiceError(403, f"state-changing requests need the header X-Requested-With: {self.s.csrf_header_value}",
                               "csrf")
        origin = request.headers.get("origin")
        if origin is not None:
            o = origin.rstrip("/")
            if o == "null" or (o not in self.s.allowed_origins and o != self.s.api_origin):
                raise ServiceError(403, f"origin {origin} is not allowed", "csrf")
        elif ident is not None and ident.via == "cookie":
            raise ServiceError(403, "cookie-authenticated requests need an Origin header", "csrf")
