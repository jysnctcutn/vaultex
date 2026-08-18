"""Bearer-token auth, request rate limiting, and baseline security-header
middleware."""

import secrets
import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import AUTH_TOKEN, RATE_LIMIT_MAX_REQUESTS, RATE_LIMIT_WINDOW_SECONDS, logger


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer ") or not secrets.compare_digest(
            header.removeprefix("Bearer ").strip(), AUTH_TOKEN
        ):
            logger.warning("Rejected unauthenticated request from %s: %s %s",
                            _client_ip(request), request.method, request.url.path)
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window request cap per client IP (OWASP AP1). Applied to
    every request, auth included, so a flood of bad bearer tokens and a
    flood of valid-but-excessive tool calls are both capped the same way.

    In-memory and per-process — same tradeoff as the /login attempt
    tracker in core/oauth/login.py: fine for a single-user server, resets
    on restart, doesn't survive multiple worker processes. That's an
    accepted limitation here, not an oversight.
    """

    def __init__(self, app, max_requests: int = RATE_LIMIT_MAX_REQUESTS,
                 window_seconds: int = RATE_LIMIT_WINDOW_SECONDS):
        super().__init__(app)
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        ip = _client_ip(request)
        now = time.time()
        hits = [t for t in self._hits[ip] if now - t < self._window_seconds]
        hits.append(now)
        self._hits[ip] = hits
        if len(hits) > self._max_requests:
            logger.warning("Rate limit exceeded for %s (%d requests in %ds)",
                            ip, len(hits), self._window_seconds)
            return JSONResponse({"error": "rate limited"}, status_code=429)
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Baseline response headers (OWASP A02 / Security Misconfiguration).
    This is a JSON API with no HTML rendering, so no CSP is set here."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
        return response
