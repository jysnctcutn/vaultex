"""
Remote MCP Server

Exposes an Obsidian vault ("YOUR VAULT") to AI clients (Claude, GPT,
agents, etc.) as *meaningful* operations rather than raw filesystem
access — per the architecture doc, this is deliberately NOT a
read_file/write_file/list_directory server.

Expected vault layout (create folders that don't exist yet as needed):

    vaultex/
    ├── 00-Inbox/
    ├── 01-Professional/
    │   └── Solution-Architecture/
    │       ├── Projects/
    │       ├── Analysis/
    │       ├── Architecture/
    │       ├── Decisions/s
    │       └── Knowledge/
    ├── 02-Builder/
    │   ├── Ideas/
    │   ├── Products/
    │   └── Projects/<ProjectName>/
    ├── 03-Knowledge/
    │   ├── AI/ Software/ Architecture/ Research/
    └── 04-Writing/

Run:
    Put the vars below in a `.env` file next to this script (see .env.example)
    so you don't have to export them by hand on every restart — they're loaded
    automatically via python-dotenv. Real exported env vars still take
    precedence over `.env`, so a one-off `FOO=bar python3 server.py` still works.

    VAULTEX_PATH=/path/to/vaultex
    MCP_AUTH_TOKEN=<long-random-secret>
    EXCLUDED_AREAS=          # e.g. "01-Professional" to hide client/employer work
    READ_ONLY=false          # true = only read-style tools are registered at all

    python3 server.py

Security progression this server is built for (local vault stays on
this machine; a tunnel exposes only this process, never the filesystem
directly):
    Phase 1: local, READ_ONLY=false               (Claude Code on this machine)
    Phase 2: tunneled, READ_ONLY=true              (first remote access, read-only)
    Phase 3: tunneled, READ_ONLY=false             (remote writes, once trusted)
    Phase 4: agent automation on top of this server

See README.md for tunnel setup and for running a second, restricted
instance for personal/non-Claude AI accounts (the 01-Professional
boundary).

Implementation lives in core/ (config, vault access, middleware, tools/) —
this file is just the entrypoint.
"""

import uvicorn

from core.app import build_app
from core.config import EXCLUDED_AREAS, HOST, PORT, READ_ONLY, VAULT_PATH, logger

if __name__ == "__main__":
    logger.info("Vaultex vault: %s", VAULT_PATH)
    if EXCLUDED_AREAS:
        logger.info("Excluded areas (hidden from this instance): %s", ", ".join(sorted(EXCLUDED_AREAS)))
    logger.info("Mode: %s", "READ-ONLY (write tools not registered)" if READ_ONLY else "read/write")
    logger.info("Listening on http://%s:%s/mcp (requires Bearer auth)", HOST, PORT)
    uvicorn.run(build_app(), host=HOST, port=PORT)
