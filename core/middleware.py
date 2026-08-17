"""Bearer-token auth and baseline security-header middleware."""

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .config import AUTH_TOKEN


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer ") or not secrets.compare_digest(
            header.removeprefix("Bearer ").strip(), AUTH_TOKEN
        ):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
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
