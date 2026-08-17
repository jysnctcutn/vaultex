"""Self-hosted OAuth 2.1 authorization server for remote (Tailscale-reachable) access.

Replaces the previous Cloudflare Worker gateway — `mcp`'s own auth toolkit
(`mcp.server.auth`) does the OAuth 2.1 protocol mechanics (PKCE, expiry,
client auth, redirect_uri matching); this package only supplies storage
(`store.py`), the provider hooks (`provider.py`), and the single-user
password-gate consent screen (`login.py`).

Entirely opt-in: `core.app.build_app()` only wires this in when
`OAUTH_ISSUER_URL` is set. Plain local/dev runs are unaffected.
"""

from .login import login_handler
from .provider import VaultexOAuthProvider

__all__ = ["VaultexOAuthProvider", "login_handler"]
