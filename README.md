<div align="center">

```
██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗███████╗██╗  ██╗
██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝██╔════╝╚██╗██╔╝
██║   ██║███████║██║   ██║██║     ██║   █████╗   ╚███╔╝ 
╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║   ██╔══╝   ██╔██╗ 
 ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║   ███████╗██╔╝ ██╗
  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚══════╝╚═╝  ╚═╝
```

*Your Obsidian vault in any MCP client. No Cloud. No Subscriptions. Local First.*

</div>

---
## VAULTEX
Exposes an Obsidian vault to AI clients (Claude, GPT, other MCP-speaking
agents) as a set of *meaningful* operations — search, read a note, save a
decision, gather everything about a project — rather than raw filesystem
access. It is deliberately **not** a `read_file` / `write_file` /
`list_directory` server: every tool goes through a shared path-safety layer
that blocks traversal outside the vault and can hide entire top-level areas
(e.g. client/employer work) from a given server instance.

## Quick start

Four stages, in order: **prerequisites → configure → (optional) taxonomy →
pick a path**. Stages 1-3 are identical either way; stage 4 forks into
Path A (local only) or Path B (self-hosted, reachable remotely).

**Best-fit scenario for each:**
- **Path A** — you only ever want Claude Code (or another local MCP client)
  on *this* computer talking to your vault. Quickest setup, nothing exposed
  to the internet, no extra accounts.
- **Path B** — you want to ask Claude about your notes from your phone or
  claude.ai in a browser too, not just this machine. More setup (Docker, a
  Tailscale account), but your vault isn't tied to one computer anymore.

### 1. Prerequisites

| Need | Path A | Path B |
|---|---|---|
| A vault — a folder of markdown notes. [Obsidian](https://obsidian.md) is the common way to manage one, but the server itself just needs the folder, not Obsidian running. | required | required |
| Python 3 | required | not required (only if you want `onboard.py` to run outside the container — see stage 3) |
| Docker Desktop | — | required |
| A free [Tailscale](https://tailscale.com) account | — | required |

### 2. Configure `.env`

```bash
cp .env.example .env
```

Fill in `VAULTEX_PATH` (path to your vault folder) and `MCP_AUTH_TOKEN`
(generate one: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`).
Leave `OAUTH_ISSUER_URL`, `AUTHORIZE_PASSWORD`, and `TS_AUTHKEY` blank — those
only get filled in during Path B, later.

### 3. (Optional) Set up your folder taxonomy

8 of the 13 tools — the ones that read/write ideas, projects, decisions,
etc. rather than doing free-form search — need to know which folders in
*your* vault to use. Skip this stage entirely and the server still runs
fine: those 8 tools just report "not configured" until you come back to
this. `search_vaultex`, `semantic_search_vaultex`, `read_note`, and
`save_brainstorm` never need this — they work on any vault immediately.

```bash
python3 onboard.py
```

Walks your vault's existing folders, lets you map each of the 7 built-in
roles (or skip it), optionally scaffolds PARA folders, and lets you define
your own categories beyond the built-in 7. Full detail in "Folder taxonomy"
further down. Safe to run later instead — nothing here blocks stage 4.

### 4. Pick a path and run it

**In plain terms**: Path A just runs Vaultex as a normal program on your
computer — only things running on that *same* computer (like Claude Code)
can reach it, nothing is exposed to the internet, and there's nothing extra
to install beyond Python. Path B wraps it in Docker and uses Tailscale so
you can *also* reach it from Claude's website or phone app, from anywhere —
more moving parts (Docker, a Tailscale account, a login password), but your
vault stops being tied to one machine. If you only ever plan to use Claude
Code on this computer, pick A. If you want to ask Claude about your notes
from your phone or claude.ai in a browser, pick B.

#### Path A — local only, this machine only

No Docker, no Tailscale, no OAuth. Fastest way to get Claude Code talking to
your vault.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python3 index_vault.py   # optional — enables semantic_search_vaultex
.venv/bin/python3 server.py
```

Point Claude Code (or any local MCP client) at `http://localhost:8000/mcp`
with `Authorization: Bearer <your MCP_AUTH_TOKEN>`. Done.

#### Path B — self-hosted, reachable from Claude web/mobile too

Docker + a bundled Tailscale sidecar.

```bash
# 1. Bring the stack up (server starts in bearer-token-only mode for now)
docker compose up -d --build

# 2. One-time: enable Funnel so the container is reachable over the public
#    internet. Prints your URL, e.g. https://vaultex.<your-tailnet>.ts.net
docker compose exec tailscale tailscale funnel 8000

# 3. Didn't run stage 3 (onboard.py) locally? Do it here instead — same
#    effect, writes to the same taxonomy.json:
docker compose exec -it vaultex python3 onboard.py

# 4. Build the semantic-search index (optional, same as Path A)
docker compose exec vaultex python3 index_vault.py
```

Then edit `.env` to turn OAuth on:
- `OAUTH_ISSUER_URL` — the `https://...ts.net` URL step 2 printed
- `AUTHORIZE_PASSWORD` — a password you choose; you'll type it into the
  browser each time you authorize a new OAuth client (e.g. Claude.ai)
- `TS_AUTHKEY` — from [Tailscale admin console → Keys](https://login.tailscale.com/admin/settings/keys)
  (uncheck "Reusable" — `docker-compose.yml` sets `TS_AUTH_ONCE=true`, so
  the key is only ever used once, to log the sidecar in)

```bash
docker compose up -d --build   # restart to pick up OAUTH_ISSUER_URL etc.
```

Now:
- **Claude web/mobile**: add a custom connector pointing at
  `https://<your-tailnet-url>/mcp`. Claude does the OAuth 2.1 handshake;
  you'll see the password screen once per client authorization.
- **Claude Code / CLI tools / this machine**: same URL,
  `Authorization: Bearer <your MCP_AUTH_TOKEN>` — works identically to Path
  A, just going out through the tunnel instead of raw localhost (no port is
  published to the host, since `vaultex` shares the sidecar's network
  namespace — `localhost:8000` on the host won't reach it in this path).

Restarting later is just `docker compose up -d` (no `--build` unless you
changed the code) — the vault mount, the search index, the OAuth store, the
taxonomy config, and the Funnel config all persist across restarts. See
"Remote access" below for what to do if something looks stuck.

## Where this fits

There are two ways in:

```
                        VAULTEX
                     (Obsidian vault)
                            │
                       MCP server
                   (server.py + core/)
                            │
             ┌──────────────┴──────────────┐
             │                             │
        Claude Code               Tailscale Funnel
      (local, direct —              (sidecar, in
       no tunnel needed)             docker-compose)
                                            │
                                  Claude (web / mobile)
```

Local access (this machine) talks to `server.py` directly over localhost —
no tunnel, no OAuth, just the bearer token. Remote access (Claude's web or
mobile Connectors) reaches the server through a Tailscale Funnel — bundled as
a sidecar container in `docker-compose.yml`, so nothing needs installing on
the host — and authenticates via OAuth 2.1, which `server.py` implements
itself (`core/oauth/`). No third-party gateway sits in front of it.

## How it's laid out

```
server.py              Entrypoint — env validation happens on import, then uvicorn.run()
onboard.py              Interactive taxonomy.json setup wizard — see "Folder taxonomy" below
core/
  config.py            Env vars, startup validation, logging setup
  taxonomy.py          Loads taxonomy.json: role paths + custom category definitions
  vault.py             Path-safety boundary: safe_path, iter_markdown, read/write, area roots
  mcp_app.py           The MCPServer instance, OAuth wiring, write_tool/register_tool gates
  middleware.py        Bearer-token auth (non-OAuth fallback) + baseline security headers
  app.py               Wires tools + middleware into the Starlette ASGI app
  oauth/               Self-hosted OAuth 2.1 authorization server — see "Remote access" below
    store.py           SQLite persistence: clients, authorization codes, access/refresh tokens
    provider.py        VaultexOAuthProvider — implements OAuthAuthorizationServerProvider
    login.py           The single-user password-gate consent screen (/login)
  tools/
    search.py          read_note, search_vaultex, semantic_search_vaultex
    builder.py         get_app_ideas, create_app_idea
    projects.py        get_project_context, get_feature_context, update_feature
    architecture.py    get_architecture_decisions, save_decision,
                       get_tech_analysis_history, get_solution_architecture_context
    capture.py         save_brainstorm
    custom.py          Dynamically registers a get/create pair per taxonomy.json custom category
index_vault.py         Standalone script: builds/refreshes the local semantic-search index
Dockerfile              Image for the vaultex service
docker-compose.yml      vaultex + a bundled Tailscale sidecar — see "Remote access" below
```

Each `core/` module owns one concern; `tools/` is grouped by the part of the
vault a tool touches, not by read vs. write.

## Configuration reference

See "Quick start" above for setup commands. Full list of `.env` variables
(all loaded automatically via python-dotenv; real exported env vars still
take precedence, so `FOO=bar python3 server.py` works for one-offs):

| Variable | Default | Purpose |
|---|---|---|
| `VAULTEX_PATH` | `./vaultex` | Path to the Obsidian vault this server reads/writes |
| `MCP_AUTH_TOKEN` | *(required)* | Long random secret; clients send it as `Authorization: Bearer <token>` |
| `MCP_HOST` | `0.0.0.0` | Bind address |
| `MCP_PORT` | `8000` | Bind port |
| `EXCLUDED_AREAS` | *(none)* | Comma-separated top-level folders this instance refuses to touch at all, e.g. `01-Professional` |
| `READ_ONLY` | `false` | `true` = write tools aren't even registered (not just blocked at call time) |
| `LOG_LEVEL` | `info` | Set to `debug` for verbose output (e.g. which files search skips and why) |
| `VAULT_EMBEDDINGS_DB` | `./vault_embeddings.db` | Override the semantic-search index location |
| `OAUTH_ISSUER_URL` | *(unset)* | Set only for remote deployments, e.g. `https://<host>.<tailnet>.ts.net` — enables the self-hosted OAuth 2.1 flow. Unset = today's bearer-token-only behavior, no OAuth routes registered at all |
| `AUTHORIZE_PASSWORD` | *(required if `OAUTH_ISSUER_URL` is set)* | Gates the `/login` consent screen — the single password that authorizes an OAuth client |
| `OAUTH_STORE_DB` | `./oauth_store.db` | Override where registered clients, authorization codes, and tokens are persisted |

## Running

Serves MCP over streamable HTTP at `http://<host>:<port>/mcp`, gated by the
bearer token (and OAuth too, if configured — see "Remote access" below).
Every response also carries a small set of baseline security headers
(`X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`,
`Permissions-Policy`).

### Semantic search (optional)

Keyword search (`search_vaultex`) works out of the box. For meaning-based
search (`semantic_search_vaultex`), `index_vault.py` builds the local
embeddings index — see "Quick start" above for the exact command in each
path (`--full` forces a complete re-index instead of the incremental
default). Produces `vault_embeddings.db`, which stores raw vault text and is
git-ignored on purpose — never commit it.

## Available tools

| Tool | Read/Write | What it does |
|---|---|---|
| `read_note` | read | Full verbatim content of one note by path |
| `search_vaultex` | read | Keyword search across titles and content |
| `semantic_search_vaultex` | read | Meaning-based search via local embeddings |
| `get_app_ideas` | read | List app ideas under the configured `builder_ideas` folder |
| `create_app_idea` | write | Create a new app idea note |
| `get_project_context` | read | All notes for a Builder or Solution-Architecture project |
| `get_feature_context` | read | One feature note plus sibling Architecture/Decisions notes |
| `update_feature` | write | Create or update a project's feature note |
| `get_architecture_decisions` | read | List decision notes, professional or per-project |
| `save_decision` | write | Save an architecture/product decision note |
| `get_tech_analysis_history` | read | List tech-analysis notes, optionally filtered by project |
| `get_solution_architecture_context` | read | A project's notes + matching tech-analysis + architecture notes |
| `save_brainstorm` | write | Save a brainstorm/conversation conclusion, default the configured `inbox` folder |

8 of these tools (everything except `read_note`, `search_vaultex`,
`semantic_search_vaultex`, and `save_brainstorm`) resolve through
`taxonomy.json` — see "Folder taxonomy" below. Any custom categories from
`taxonomy.json` add their own `get_<key>`/`create_<key>_note` tools to this
list at server startup.

## Folder taxonomy

Fresh clone, no `taxonomy.json` yet = a taxonomy-free server. Reads among
the 8 role-gated tools raise a clear `TaxonomyNotConfigured` error instead
of silently returning nothing; writes raise instead of silently creating a
folder in your vault. Run `python3 onboard.py` to fix that — it:

- Scans your vault's existing top-level folders and lets you assign each of
  the 7 built-in roles (ideas, builder projects, professional decisions,
  professional tech analysis, professional architecture, professional
  projects, inbox) to one of them, a custom path you type, or skip it.
- Optionally scaffolds the 4 [PARA](https://fortelabs.com/blog/para/)
  folders (`Projects/`, `Areas/`, `Resources/`, `Archive/`) if you want a
  starting structure rather than mapping onto something that already
  exists.
- Lets you define **custom categories** beyond the 7 built-in roles — e.g.
  your own "Meeting Notes" — each becoming a real `get_<key>`/
  `create_<key>_note` tool pair, registered dynamically at server startup.
  Optional per-category required sections (same mechanism `save_decision`
  uses for its `**Decided:**`/`**What it means:**` check) and filename
  prefix.
- Writes everything to `taxonomy.json` (gitignored — personal, same
  treatment as `.env`). Re-running edits it in place; `--reconfigure`
  starts fresh.

For Path B (Docker), run it inside the container so it writes to the same
bind-mounted `taxonomy.json` the server reads:
```bash
docker compose exec -it vaultex python3 onboard.py   # -it: needs a real terminal for prompts
```
Restart afterward (`docker compose up -d --build`, or just `python3
server.py` again for Path A) to pick up changes — same as any other `.env`
edit.

## Security model

- **Path safety**: every tool resolves through `safe_path`/`iter_markdown` in
  `core/vault.py`, which blocks `..` traversal outside the vault and enforces
  `EXCLUDED_AREAS` — a new tool can't accidentally bypass either check.
- **Auth**: without `OAUTH_ISSUER_URL` set, a single shared bearer token,
  compared with `secrets.compare_digest` (timing-safe) — wrong or missing
  token → `401` before any tool runs. With `OAUTH_ISSUER_URL` set, OAuth 2.1
  access tokens are accepted too (see "Remote access" below); the bearer
  token keeps working either way as a fallback for clients that can't do a
  browser OAuth flow.
- **Read-only mode**: `READ_ONLY=true` removes write tools from the tool list
  entirely, not just from what they're allowed to do.

Deployment is meant to progress in phases: local-only, then tunneled
read-only, then tunneled read/write once trusted, then agent automation on
top. See the docstring in `server.py` for the exact phase breakdown.

## Remote access (optional)

`server.py` is its own single-user OAuth 2.1 authorization server
(`core/oauth/`) — no third-party gateway required. `docker-compose.yml`
bundles it with a Tailscale sidecar so remote (web/mobile) access needs
nothing installed on the host beyond Docker and your own Tailscale account.
See "Quick start" → Path B above for the actual setup commands.

```
Claude (web/iPhone) --OAuth 2.1--> Tailscale Funnel (sidecar) --> server.py (core/oauth/)
```

Since this is single-user, the OAuth `/authorize` step is a shared-password
gate (`AUTHORIZE_PASSWORD`, see `core/oauth/login.py`) rather than a real
login system — the same shape the previous Cloudflare Worker used, just
in-process now. It's your own tailnet and your own `TS_AUTHKEY` throughout;
nothing routes through anyone else's infrastructure. A technical user can
strip the `tailscale` sidecar out of `docker-compose.yml` entirely and front
the `vaultex` service with their own reverse proxy/VPN instead.

`vault_embeddings.db` and `oauth_store.db` are bind-mounted straight from
the repo root into the container (not a Docker-managed volume), so they're
the exact same files `python3 server.py` uses when run locally per Path A —
reindex from either place and both see it. Don't run Path A and the Docker
stack at the same time against the same vault: SQLite expects one writer.

### Troubleshooting

- **`docker compose up` fails to recreate the `vaultex` container** with
  something like `container ... is zombie and can not be killed`: plain
  `python3 server.py` as PID 1 inside a container can't reap zombie
  processes on its own. `docker-compose.yml` already sets `init: true` on
  the `vaultex` service to fix this; if you rewrite the compose file from
  scratch, keep that line.
- **A few seconds of `curl: (35) SSL_ERROR_SYSCALL` right after
  `docker compose up`**: expected — Tailscale's Funnel edge needs ~15-20s to
  reconnect after the sidecar restarts. `tailscale funnel status` inside the
  container will already say "on"; the public URL just needs a moment to
  catch up. No action needed, just retry.
