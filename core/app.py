"""Assembles the Starlette ASGI app: tool registration plus auth/security middleware."""

from starlette.applications import Starlette

from . import tools  # noqa: F401  (import registers every @mcp.tool())
from .config import HOST, OAUTH_ISSUER_URL
from .mcp_app import mcp
from .middleware import BearerAuthMiddleware, SecurityHeadersMiddleware


def build_app() -> Starlette:
    app = mcp.streamable_http_app(host=HOST)

    if not OAUTH_ISSUER_URL:
        # No OAuth configured: fall back to the original hand-rolled bearer
        # check. Added first = innermost, so it still sees requests that
        # fail auth and attaches headers to the 401 response too.
        app.add_middleware(BearerAuthMiddleware)
    # With OAuth configured, mcp_app.py already wired auth_server_provider/
    # token_verifier into the MCPServer instance, so the SDK's own
    # RequireAuthMiddleware/BearerAuthBackend guards /mcp instead — the OAuth
    # issuance routes (/authorize, /token, /register, /revoke, /login,
    # /.well-known/oauth-authorization-server) stay public by design.

    app.add_middleware(SecurityHeadersMiddleware)
    return app
