"""Environment configuration and startup validation.

Put the vars below in a `.env` file next to server.py (see .env.example) so
you don't have to export them by hand on every restart — they're loaded
automatically via python-dotenv. Real exported env vars still take
precedence over `.env`, so a one-off `FOO=bar python3 server.py` still works.

    VAULTEX_PATH=/path/to/vaultex
    MCP_AUTH_TOKEN=<long-random-secret>
    EXCLUDED_AREAS=          # e.g. "01-Professional" to hide client/employer work
    READ_ONLY=false          # true = only read-style tools are registered at all
    ENABLE_NOTE_MOVE=false   # true = registers move_note (move/rename within the vault);
                              # off by default even when READ_ONLY=false
    LOG_LEVEL=info           # set to "debug" for verbose output
    RATE_LIMIT_MAX_REQUESTS=120   # requests allowed per IP per RATE_LIMIT_WINDOW_SECONDS
    RATE_LIMIT_WINDOW_SECONDS=60  # sliding window size, in seconds
    AUTO_LINK_ON_SAVE=true        # append related-notes links to brand-new notes
                                    # (no-op unless semantic search is set up)
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
HOST = os.environ.get("MCP_HOST", "0.0.0.0")  # noqa: S104 — intentional: Docker/Path B needs 0.0.0.0 to be reachable through the Tailscale sidecar's network namespace

_PORT_RAW = os.environ.get("MCP_PORT", "8000")
try:
    PORT = int(_PORT_RAW)
except ValueError:
    raise SystemExit(f"MCP_PORT must be an integer, got: {_PORT_RAW!r}") from None

EMBEDDINGS_DB_PATH = Path(
    os.environ.get("VAULT_EMBEDDINGS_DB", str(BASE_DIR / "vault_embeddings.db"))
).expanduser().resolve()

# How often (seconds) the background sweep in core/app.py re-syncs
# vault_embeddings.db with what's actually on disk — catches edits/deletes
# made outside the MCP tools (e.g. directly in Obsidian), which the
# write-hook in core/vault.py can't see. Only starts at all if
# EMBEDDINGS_DB_PATH already exists at server startup.
_REINDEX_INTERVAL_RAW = os.environ.get("REINDEX_INTERVAL_SECONDS", "300")
try:
    REINDEX_INTERVAL_SECONDS = int(_REINDEX_INTERVAL_RAW)
except ValueError:
    raise SystemExit(f"REINDEX_INTERVAL_SECONDS must be an integer, got: {_REINDEX_INTERVAL_RAW!r}") from None

# OWASP AP1 (Unrestricted Resource Consumption): every request is capped
# per source IP on a sliding window, regardless of which tool it targets.
# This gives a leaked or over-shared MCP_AUTH_TOKEN (or a valid OAuth
# session) a hard ceiling on how much it can hit the
# embedding-cost-bearing search tools or anything else.
_RATE_LIMIT_MAX_RAW = os.environ.get("RATE_LIMIT_MAX_REQUESTS", "120")
try:
    RATE_LIMIT_MAX_REQUESTS = int(_RATE_LIMIT_MAX_RAW)
except ValueError:
    raise SystemExit(f"RATE_LIMIT_MAX_REQUESTS must be an integer, got: {_RATE_LIMIT_MAX_RAW!r}") from None

_RATE_LIMIT_WINDOW_RAW = os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "60")
try:
    RATE_LIMIT_WINDOW_SECONDS = int(_RATE_LIMIT_WINDOW_RAW)
except ValueError:
    raise SystemExit(f"RATE_LIMIT_WINDOW_SECONDS must be an integer, got: {_RATE_LIMIT_WINDOW_RAW!r}") from None

# Top-level folder names this server instance refuses to touch at all.
# Use this to run a second, restricted instance for non-Claude / personal
# AI accounts that should never see 01-Professional (client/employer work).
EXCLUDED_AREAS = {
    a.strip() for a in os.environ.get("EXCLUDED_AREAS", "").split(",") if a.strip()
}

# Auto-link gate for core/vault.py's write() hook, which appends a
# "## Related notes" section to brand-new notes once a semantic index
# exists for this vault. The false-positive risk is already small (new
# notes only, conservative distance threshold), but this is a full off
# switch that needs no change to any write tool's signature.
AUTO_LINK_ON_SAVE = os.environ.get("AUTO_LINK_ON_SAVE", "true").strip().lower() in {"1", "true", "yes"}

# Phase 2 of the security progression: when true, write-capable tools are
# never registered at all (they won't even appear in tools/list), not just
# blocked at call time. Flip to false only once you trust the tunnel/clients
# with writes (Phase 3).
READ_ONLY = os.environ.get("READ_ONLY", "false").strip().lower() in {"1", "true", "yes"}

# move_note (core/tools/move.py) is gated separately from -- on top of, not
# instead of -- READ_ONLY: relocate-and-possibly-overwrite anywhere in the
# vault is a qualitatively riskier capability than an additive write, so it
# defaults off even in read/write mode and needs an explicit opt-in.
ENABLE_NOTE_MOVE = os.environ.get("ENABLE_NOTE_MOVE", "false").strip().lower() in {"1", "true", "yes"}

# Self-hosted OAuth 2.1, opt-in. Unset OAUTH_ISSUER_URL = today's
# bearer-token-only behavior (no OAuth routes registered at all). Set it
# (Docker/Tailscale deployments) to also require AUTHORIZE_PASSWORD, which
# gates the /login consent screen.
OAUTH_ISSUER_URL = os.environ.get("OAUTH_ISSUER_URL") or None
AUTHORIZE_PASSWORD = os.environ.get("AUTHORIZE_PASSWORD") or None
OAUTH_STORE_DB = Path(
    os.environ.get("OAUTH_STORE_DB", str(BASE_DIR / "oauth_store.db"))
).expanduser().resolve()

# Override for tests/multi-instance setups so they don't read or clobber a
# real, personal taxonomy.json. Default matches every prior release's
# behavior (BASE_DIR/taxonomy.json).
TAXONOMY_JSON_PATH = Path(
    os.environ.get("TAXONOMY_JSON_PATH", str(BASE_DIR / "taxonomy.json"))
).expanduser().resolve()

# Dynamic client registration (RFC 7591) is open by design — anyone can hit
# /register — but nothing says the server has to accept just any client.
# core/oauth/provider.py rejects registrations whose redirect_uri host isn't
# in this list, so a random internet client can never complete a full OAuth
# flow (it can't receive the redirect) even though the endpoint is public.
ALLOWED_REDIRECT_HOSTS = {
    h.strip().lower() for h in os.environ.get("ALLOWED_REDIRECT_HOSTS", "claude.ai").split(",") if h.strip()
}

if OAUTH_ISSUER_URL and not AUTHORIZE_PASSWORD:
    raise SystemExit("Set AUTHORIZE_PASSWORD when OAUTH_ISSUER_URL is set — it gates the /login consent screen.")

if not VAULT_PATH.exists():
    raise SystemExit(f"Vaultex path does not exist: {VAULT_PATH}")

if not AUTH_TOKEN:
    raise SystemExit(
        "Set MCP_AUTH_TOKEN to a long random secret before running this server.\n"
        f"Example: MCP_AUTH_TOKEN={secrets.token_urlsafe(32)}"
    )
