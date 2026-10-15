"""One exception type for every API error: HTTP status, a message and a stable machine code.
Rendered by app.py as JSON ``{"error": message, "code": code}``."""
from __future__ import annotations

from typing import Dict, Optional

_CODES = {400: "bad_request", 401: "unauthorized", 403: "forbidden", 404: "not_found", 405: "method_not_allowed",
          409: "conflict", 413: "payload_too_large", 422: "invalid_request", 429: "rate_limited",
          500: "internal", 503: "unavailable"}


class ServiceError(Exception):
    def __init__(self, status: int, message: str, code: Optional[str] = None,
                 headers: Optional[Dict[str, str]] = None):
        super().__init__(message)
        self.status = status
        self.message = message
        self.code = code or _CODES.get(status, "error")
        self.headers = headers or {}

    def body(self) -> Dict[str, str]:
        return {"error": self.message, "code": self.code}
