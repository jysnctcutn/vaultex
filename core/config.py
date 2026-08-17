"""Environment configuration and startup validation.

Put the vars below in a `.env` file next to server.py (see .env.example) so
you don't have to export them by hand on every restart — they're loaded
automatically via python-dotenv. Real exported env vars still take
precedence over `.env`, so a one-off `FOO=bar python3 server.py` still works.

    VAULTEX_PATH=/path/to/vaultex
    MCP_AUTH_TOKEN=<long-random-secret>
    EXCLUDED_AREAS=          # e.g. "01-Professional" to hide client/employer work
    READ_ONLY=false          # true = only read-style tools are registered at all
    LOG_LEVEL=info           # set to "debug" for verbose output
    OAUTH_ISSUER_URL=        # set only for Docker/Tailscale remote deployments —
                              # e.g. https://<host>.<tailnet>.ts.net — enables the
                              # self-hosted OAuth 2.1 flow; unset = today's
                              # bearer-token-only behavior, no OAuth routes at all
    AUTHORIZE_PASSWORD=      # required alongside OAUTH_ISSUER_URL — gates /login
"""

import logging
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(), format="%(levelname)-8s %(message)s")
logger = logging.getLogger("vaultex")

VAULT_PATH = Path(os.environ.get("VAULTEX_PATH", "./vaultex")).expanduser().resolve()
AUTH_TOKEN = os.environ.get("MCP_AUTH_TOKEN")
HOST = os.environ.get("MCP_HOST", "0.0.0.0")

_PORT_RAW = os.environ.get("MCP_PORT", "8000")
try:
    PORT = int(_PORT_RAW)
except ValueError:
    raise SystemExit(f"MCP_PORT must be an integer, got: {_PORT_RAW!r}")

EMBEDDINGS_DB_PATH = Path(
    os.environ.get("VAULT_EMBEDDINGS_DB", str(BASE_DIR / "vault_embeddings.db"))
).expanduser().resolve()

# Top-level folder names this server instance refuses to touch at all.
# Use this to run a second, restricted instance for non-Claude / personal
# AI accounts that should never see 01-Professional (client/employer work).
EXCLUDED_AREAS = {
    a.strip() for a in os.environ.get("EXCLUDED_AREAS", "").split(",") if a.strip()
}

# Phase 2 of the security progression: when true, write-capable tools are
# never registered at all (they won't even appear in tools/list), not just
# blocked at call time. Flip to false only once you trust the tunnel/clients
# with writes (Phase 3).
READ_ONLY = os.environ.get("READ_ONLY", "false").strip().lower() in {"1", "true", "yes"}

# Self-hosted OAuth 2.1, opt-in. Unset OAUTH_ISSUER_URL = today's
# bearer-token-only behavior (no OAuth routes registered at all). Set it
# (Docker/Tailscale deployments) to also require AUTHORIZE_PASSWORD, which
# gates the /login consent screen.
OAUTH_ISSUER_URL = os.environ.get("OAUTH_ISSUER_URL") or None
AUTHORIZE_PASSWORD = os.environ.get("AUTHORIZE_PASSWORD") or None
OAUTH_STORE_DB = Path(
    os.environ.get("OAUTH_STORE_DB", str(BASE_DIR / "oauth_store.db"))
).expanduser().resolve()

if OAUTH_ISSUER_URL and not AUTHORIZE_PASSWORD:
    raise SystemExit("Set AUTHORIZE_PASSWORD when OAUTH_ISSUER_URL is set — it gates the /login consent screen.")

if not VAULT_PATH.exists():
    raise SystemExit(f"Vaultex path does not exist: {VAULT_PATH}")

if not AUTH_TOKEN:
    raise SystemExit(
        "Set MCP_AUTH_TOKEN to a long random secret before running this server.\n"
        f"Example: MCP_AUTH_TOKEN={secrets.token_urlsafe(32)}"
    )
