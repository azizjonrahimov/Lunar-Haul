"""FastAPI application factory: `create_app(settings)`.

Middleware (outermost first): CORS allow-list with credentials; Private-Network-Access preflight header
and baseline security headers. Errors of every kind render as {"error", "code"}.
"""
from __future__ import annotations

import contextlib
import inspect
import logging
from typing import Optional

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from .api import Context, router
from .auth import Auth, Mailer
from .db import Database
from .errors import ServiceError
from .ratelimit import RateLimiter
from .settings import Settings

log = logging.getLogger("service")


class HeadersMiddleware:
    """Pure ASGI: Access-Control-Allow-Private-Network on PNA preflights (Chrome, an https page calling a
    local http API, as lunarsim/server.py does) and nosniff / referrer headers on every response."""

    def __init__(self, app, pna: bool = True):
        self.app = app
        self.pna = pna

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
        pna = (self.pna and scope.get("method") == "OPTIONS"
               and headers.get("access-control-request-private-network", "").lower() == "true")

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                hdrs = list(message.get("headers", []))
                hdrs.append((b"x-content-type-options", b"nosniff"))
                hdrs.append((b"referrer-policy", b"no-referrer"))
                if pna:
                    hdrs.append((b"access-control-allow-private-network", b"true"))
                message = dict(message, headers=hdrs)
            await send(message)

        await self.app(scope, receive, send_wrapper)


def create_app(settings: Optional[Settings] = None, mailer: Optional[Mailer] = None) -> FastAPI:
    s = settings or Settings.from_env()
    logging.basicConfig(level=getattr(logging, str(s.log_level).upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    db = Database(s.db_path)
    auth = Auth(s, db, mailer)
    limiter = RateLimiter(s.rate_limits)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        db.purge_expired()
        log.info("service %s on %s; db %s; origins %s", __version__, s.base_url, s.db_path, ", ".join(s.allowed_origins))
        yield
        db.close()

    app = FastAPI(title="LunarSim service", version=__version__, lifespan=lifespan, docs_url="/v2/docs",
                  openapi_url="/v2/openapi.json", redoc_url=None)
    app.state.ctx = Context(settings=s, db=db, auth=auth, limiter=limiter)
    app.include_router(router)

    # middleware: the last added runs first, so CORS is outermost (error responses get CORS headers too)
    cors_kw = dict(allow_origins=s.allowed_origins, allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"],
                   allow_headers=["Content-Type", "Authorization", "X-Requested-With", "Last-Event-ID", "Cache-Control"],
                   expose_headers=["Retry-After", "ETag", "Location", "X-Content-SHA256", "Content-Disposition"],
                   max_age=600)
    # Starlette >= 0.47 answers Chrome's Private Network Access preflight itself; older versions reject the
    # Access-Control-Request-Private-Network header, so our HeadersMiddleware adds the response header then.
    native_pna = "allow_private_network" in inspect.signature(CORSMiddleware.__init__).parameters
    if native_pna:
        cors_kw["allow_private_network"] = True
    app.add_middleware(HeadersMiddleware, pna=not native_pna)
    app.add_middleware(CORSMiddleware, **cors_kw)

    @app.exception_handler(ServiceError)
    async def _service_error(request: Request, e: ServiceError):
        return JSONResponse(e.body(), status_code=e.status, headers=e.headers)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, e: StarletteHTTPException):
        detail = e.detail if isinstance(e.detail, str) else str(e.detail)
        if e.status_code == 404 and detail == "Not Found":
            detail = f"no endpoint {request.method} {request.url.path}"
        return JSONResponse(ServiceError(e.status_code, detail).body(), status_code=e.status_code,
                            headers=dict(e.headers or {}))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, e: RequestValidationError):
        msgs = []
        for err in e.errors()[:5]:
            loc = ".".join(str(x) for x in err.get("loc", []) if x not in ("query", "path", "body"))
            msgs.append(f"{loc}: {err.get('msg')}")
        return JSONResponse({"error": "invalid request: " + "; ".join(msgs), "code": "invalid_request"}, status_code=400)

    @app.exception_handler(Exception)
    async def _any_error(request: Request, e: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse({"error": f"{type(e).__name__}: {e}", "code": "internal"}, status_code=500)

    return app
