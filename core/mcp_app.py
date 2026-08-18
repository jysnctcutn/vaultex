"""The shared MCPServer instance and the write-tool registration gate."""

from mcp.server import MCPServer
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions, RevocationOptions

from .config import OAUTH_ISSUER_URL, READ_ONLY

_auth_kwargs = {}
if OAUTH_ISSUER_URL:
    # auth_server_provider/auth are constructor-only on this SDK's
    # high-level MCPServer, unlike the lowlevel server it wraps (which
    # takes them on streamable_http_app() itself). So the OAuth wiring has
    # to happen here, at instance construction, not in core/app.py.
    # Passing only auth_server_provider, not token_verifier too, is
    # deliberate: the SDK derives a ProviderTokenVerifier from it
    # automatically and raises if both are given.
    from .oauth import VaultexOAuthProvider

    _auth_kwargs["auth_server_provider"] = VaultexOAuthProvider()
    _auth_kwargs["auth"] = AuthSettings(
        issuer_url=OAUTH_ISSUER_URL,
        resource_server_url=f"{OAUTH_ISSUER_URL}/mcp",
        client_registration_options=ClientRegistrationOptions(
            enabled=True, valid_scopes=["mcp"], default_scopes=["mcp"]
        ),
        revocation_options=RevocationOptions(enabled=True),
    )

mcp = MCPServer(name="vaultex", version="0.2.0", **_auth_kwargs)

if OAUTH_ISSUER_URL:
    # custom_route() routes are deliberately excluded from the auth
    # requirement (see its docstring). That's exactly what the
    # password-gate consent screen needs, since it's a public entry point
    # by design.
    from .oauth import login_handler

    mcp.custom_route("/login", methods=["GET", "POST"])(login_handler)


def write_tool(func):
    """Register a tool only when READ_ONLY is false. In READ_ONLY mode the
    tool is skipped entirely, so it doesn't appear in tools/list at all —
    not just blocked when called."""
    if READ_ONLY:
        return func
    return mcp.tool()(func)


def register_tool(func, *, name: str, description: str, write: bool = False):
    """Dynamically-named counterpart to write_tool/@mcp.tool(), for the
    per-category tools core/tools/custom.py generates from taxonomy.json
    at import time. The tool name isn't known until then, so it can't
    just be the decorated function's own name."""
    if write and READ_ONLY:
        return func
    return mcp.tool(name=name, description=description)(func)
