"""Assembles the Starlette ASGI app: tool registration plus auth/security middleware."""

import asyncio
import contextlib

from starlette.applications import Starlette

from . import tools  # noqa: F401  (import registers every @mcp.tool())
from .config import EMBEDDINGS_DB_PATH, HOST, OAUTH_ISSUER_URL, REINDEX_INTERVAL_SECONDS, VAULT_PATH
from .embeddings import _SEMANTIC_DEPS_AVAILABLE, periodic_reindex
from .mcp_app import mcp
from .middleware import BearerAuthMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware


def build_app() -> Starlette:
    app = mcp.streamable_http_app(host=HOST)

    if not OAUTH_ISSUER_URL:
        # No OAuth configured, so fall back to the original hand-rolled
        # bearer check. Added first, making it the innermost middleware --
        # SecurityHeadersMiddleware (added below) wraps around it, so
        # failed-auth responses still get security headers attached.
        app.add_middleware(BearerAuthMiddleware)
    # With OAuth configured, mcp_app.py already wired auth_server_provider/
    # token_verifier into the MCPServer instance, so the SDK's own
    # RequireAuthMiddleware/BearerAuthBackend guards /mcp instead. The
    # OAuth issuance routes (/authorize, /token, /register, /revoke,
    # /login, /.well-known/oauth-authorization-server) stay public by design.

    app.add_middleware(SecurityHeadersMiddleware)

    # Added last, making it the outermost middleware, so a flood is capped
    # before it reaches auth or route handling at all. This covers both a
    # guessing attack against BearerAuthMiddleware and a leaked/over-shared
    # token hammering the expensive search tools once past auth.
    app.add_middleware(RateLimitMiddleware)

    # Only start the periodic reindex sweep if semantic search has already
    # been opted into (index built at least once) — same no-op-until-opted-in
    # gate the write-hook in core/vault.py already uses. Checked once at
    # startup, not re-polled.
    if _SEMANTIC_DEPS_AVAILABLE and EMBEDDINGS_DB_PATH.exists():
        # mcp.streamable_http_app() already built this app with its own
        # lifespan (the StreamableHTTP session manager's startup/shutdown).
        # This Starlette version only accepts `lifespan=` at construction,
        # with no public method to add another handler afterward. So the
        # supported way to layer one on is replacing the router's
        # lifespan_context with a wrapper that still enters/exits the
        # original.
        original_lifespan = app.router.lifespan_context

        @contextlib.asynccontextmanager
        async def lifespan_with_reindex(app):
            async with original_lifespan(app) as state:
                task = asyncio.create_task(
                    periodic_reindex(VAULT_PATH, EMBEDDINGS_DB_PATH, REINDEX_INTERVAL_SECONDS)
                )
                try:
                    yield state
                finally:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task

        app.router.lifespan_context = lifespan_with_reindex

    return app
