```
██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗███████╗██╗  ██╗ 
██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝██╔════╝╚██╗██╔╝
██║   ██║███████║██║   ██║██║     ██║   █████╗   ╚███╔╝ 
╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║   ██╔══╝   ██╔██╗ 
 ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║   ███████╗██╔╝ ██╗
  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚══════╝╚═╝  ╚═╝ MCP
Local-first and free for individuals.
No Cloud. No Subscriptions. 
Your Obsidian/MD vault in any MCP client.
```
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14169/badge)](https://www.bestpractices.dev/projects/14169)&nbsp;
[![CI](https://github.com/jysnctcutn/vaultex/actions/workflows/ci.yml/badge.svg)](https://github.com/jysnctcutn/vaultex/actions/workflows/ci.yml)&nbsp;
[![Security](https://github.com/jysnctcutn/vaultex/actions/workflows/security.yml/badge.svg)](https://github.com/jysnctcutn/vaultex/actions/workflows/security.yml)&nbsp;
[![Lint](https://github.com/jysnctcutn/vaultex/actions/workflows/lint.yml/badge.svg)](https://github.com/jysnctcutn/vaultex/actions/workflows/lint.yml)&nbsp;
[![License](https://img.shields.io/github/license/jysnctcutn/vaultex)](LICENSE)&nbsp;
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue?logo=python&logoColor=white)](https://www.python.org/) 
---

## VAULTEX MCP

Exposes an Obsidian vault to AI clients (Claude, GPT, other MCP-speaking
agents) as a set of *meaningful* operations — search, read a note, save a
decision, gather everything about a project — rather than raw filesystem
access. It is deliberately **not** a `read_file` / `write_file` /
`list_directory` server: every tool goes through a shared path-safety layer
that blocks traversal outside the vault and can hide entire top-level areas
(e.g. client/employer work) from a given server instance.

![Vaultex demo](./vaultex.gif)

**Contents:** [Features](#features) · [Easy install](#easy-install) ·
[Quick start](#quick-start) ·
[Connecting AI clients](#connecting-ai-clients-claude-chatgpt-grok) ·
[Where this fits](#where-this-fits) ·
[Manual context handover vs. one tool call](#manual-context-handover-vs-one-tool-call) ·
[How it's laid out](#how-its-laid-out) ·
[Configuration reference](#configuration-reference) ·
[Available tools](#available-tools) ·
[Folder taxonomy](#folder-taxonomy) ·
[Security model](#security-model) ·
[Remote access](#remote-access-optional) ·
[Upgrading and uninstalling](#upgrading-and-uninstalling) ·
[Contributing](#contributing)

## Features

- **Meaningful operations, not raw filesystem access** — search, read a note,
  save a decision, gather everything about a project; no generic
  `read_file`/`write_file`/`list_directory` tools.
- **Path-safety by construction** — every tool routes through a shared
  boundary that blocks `..` traversal and can hide entire top-level folders
  (e.g. client/employer work) per server instance.
- **16 built-in tools** spanning search, app ideas, project context,
  architecture decisions, tagging, and brainstorm capture — see "Available
  tools" below.
- **Folder taxonomy** — map your vault's own folders (or scaffold PARA) once
  via `onboard.py`; define custom categories that become their own
  `get`/`create` tools automatically at startup.
- **Local semantic search** — optional embeddings index (`index_vault.py`),
  runs entirely on your machine, no cloud calls.
- **Two deployment paths** — fully local with no Docker/Tailscale (Path A),
  or self-hosted with a bundled Tailscale sidecar for remote access from
  Claude web/mobile (Path B).
- **Self-hosted OAuth 2.1** — `server.py` is its own single-user
  authorization server; no third-party gateway needed for remote clients.
- **Read-only mode** — `READ_ONLY=true` removes write tools from the tool
  list entirely, not just blocks them at call time.
- **No cloud, no subscriptions** — your vault stays on your machine or your
  own tailnet.

## Easy install

Don't want to work through the manual steps below? Run one command and
answer a few prompts — it does the rest for you:

```bash
git clone https://github.com/jysnctcutn/vaultex.git
python3 install.py   # macOS/Linux
python install.py    # Windows
```

It walks through everything "Quick start" covers by hand:
- Points at an existing vault, or creates one
- Choose Path A (this machine only) or Path B (also reachable from Claude
  web/mobile)
- Installs dependencies — venv + pip for Path A, Docker + Tailscale for
  Path B
- Sets up your folder taxonomy: guided, a sensible default, or skip for now
- Builds the semantic-search index automatically
- Prints your access token and, on Path A, offers to start the server
  right away

Once it's running, connect your client — see [Connecting AI clients (Claude,
ChatGPT, Grok)](#connecting-ai-clients-claude-chatgpt-grok) below.

> **Important:** Custom connectors on ChatGPT requires a paid plan (Plus or
> above) — the free tier doesn't support them.

Prefer doing it by hand, or want to see exactly what it automates? The
stages below are what it runs under the hood.

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

#### Hardware requirements

Vaultex is deliberately light — it's a small Python server plus a local
keyword/embeddings index, not a model host. No GPU is used or needed;
semantic search runs on CPU via a small (~130MB) embedding model
(`BAAI/bge-small-en-v1.5`, 384 dimensions).

| | Minimum | Recommended |
|---|---|---|
| CPU | Any x86_64/ARM64, 2 cores | 2+ cores (faster = quicker `index_vault.py` runs) |
| RAM | 2GB free | 4GB free |
| Disk (Path A, bare `venv`) | ~1-2GB (deps + model + SQLite indexes), plus your vault's own size | Same, with headroom for vault growth |
| Disk (Path B, Docker image) | ~1.4-2GB | Same, with headroom for vault growth |
| GPU | None required | None required |
| Network | None for Path A (fully local) | Path B adds Docker + a Tailscale tunnel — any always-on machine (a spare laptop, mini PC, or NAS capable of running Docker) works |

In practice this runs comfortably on something as modest as a Raspberry Pi
4 (4GB) or an old laptop repurposed as a home server — indexing a large
vault will just take longer on weaker CPUs. RAM is the main constraint: the
embedding model plus `sentence-transformers`/`torch` overhead is the bulk
of the footprint, not the vault itself.

The Dockerfile pins the CPU-only `torch` wheel (`--index-url
https://download.pytorch.org/whl/cpu`) before installing the rest of
`requirements.txt`. Without that, `pip` defaults to the CUDA-enabled build
on Linux and drags in ~3.5GB of unused `nvidia`/`triton` packages — this
app is CPU-only and never touches a GPU, so that build brings no benefit.

### 2. Configure `.env`

```bash
cp .env.example .env
```

Fill in `VAULTEX_PATH` (path to your vault folder) and `MCP_AUTH_TOKEN`
(generate one: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`).
Leave `OAUTH_ISSUER_URL`, `AUTHORIZE_PASSWORD`, and `TS_AUTHKEY` blank — those
only get filled in during Path B, later.

### 3. (Optional) Set up your folder taxonomy

9 of the 16 tools — the ones that read/write ideas, projects, decisions,
etc. rather than doing free-form search — need to know which folders in
*your* vault to use. Skip this stage entirely and the server still runs
fine: those 9 tools just report "not configured" until you come back to
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
#    --bg is required — without it, Funnel turns off as soon as this
#    command's session ends instead of persisting in the background.
docker compose exec tailscale tailscale funnel --bg 8000

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

### Connecting AI clients (Claude, ChatGPT, Grok)

Any MCP-compatible client works the same way once the server is running:
point it at your `/mcp` URL and either complete the OAuth 2.1 handshake
(Path B) or supply `Authorization: Bearer <your MCP_AUTH_TOKEN>` (Path A).

- **Claude** (web, mobile, desktop): Settings → Connectors → Add custom
  connector → paste your `/mcp` URL.
- **ChatGPT**: Settings → Connectors → Add connector → paste your `/mcp`
  URL; ChatGPT runs through the same OAuth 2.1 flow.
- **Grok**: Settings → Connectors (or Tools) → Add MCP connector → same URL.

Menu names shift as these products update — if a step doesn't match what
you see, look for "Connectors," "Custom connector," or "MCP" in that
client's settings.

## Where this fits

There are two ways in:

```
                        VAULTEX
                     (Obsidian vault)
                            │
                       MCP server
                   (server.py + core/)
                            │
             ┌──────────────┴──────────────────────────┐
             │                                         │
  (Path A - 1 Machine)                        (Path B - Cross device)
(local, direct — no tunnel needed)                Tailscale Funnel
          │                                   (sidecar, in docker-compose)
          │                                            │                    
Claude Code + Desktop GUI                              │
                                         Claude (cli /web / mobile) + Obsidian
```

Local access (this machine) talks to `server.py` directly over localhost —
no tunnel, no OAuth, just the bearer token. Remote access (Claude's web or
mobile Connectors) reaches the server through a Tailscale Funnel — bundled as
a sidecar container in `docker-compose.yml`, so nothing needs installing on
the host — and authenticates via OAuth 2.1, which `server.py` implements
itself (`core/oauth/`). No third-party gateway sits in front of it.

## Manual context handover vs. one tool call

Easy to *claim* this beats copy-pasting between AI clients; here's a
measurement instead of a marketing number.

**The scenario**: you close a chat in one AI client and open a different
one — Claude Desktop today, Claude Code tomorrow, ChatGPT or Claude on your
phone next week. None of them share memory with each other. Without
Vaultex, reconstructing "what were we doing on this project" means manually
finding and pasting in the relevant notes, every time you switch.

[`benchmarks/context_handover_benchmark.py`](benchmarks/context_handover_benchmark.py)
measures this directly instead of guessing a percentage. It builds a
synthetic vault (fake "Acme-Redesign" project, not real data) with notes
spread across three folders the way a real Solution-Architecture project
actually accumulates them — project notes, tech-analysis notes, architecture
notes — plus two unrelated notes sitting in those same folders, to check
that filtering by project actually works rather than just counting files.
It then runs the real `get_solution_architecture_context()` tool code
against that fixture — not a simulation of it. Reproduce it yourself:

```bash
python3 benchmarks/context_handover_benchmark.py
```

Measured result for that fixture, one handover:

| | Manual (open + copy each note) | Vaultex |
|---|---|---|
| Folders you need to know about | 3 | 0 — resolved from `taxonomy.json` |
| Files to individually open and paste | 6 | 0 |
| Unrelated notes you must notice and skip | 2 | 0 — filtered automatically by project name |
| Round-trips to reassemble context | — | 1 |

That gap repeats every time you switch clients without shared memory:

| Clients used across a week | Manual file-copies | Vaultex tool calls |
|---|---|---|
| 1 | 6 | 1 |
| 2 | 12 | 2 |
| 3 | 18 | 3 |
| 5 | 30 | 5 |

This is not a token or speed benchmark — the AI reads the same content
either way. What it removes is the manual labor of finding and re-pasting
that content, and the chance of missing or misfiling a note, not the
reading itself. The ratio (files-per-project vs. 1 tool call) will vary
with how many notes your own projects accumulate; rerun the script against
your own taxonomy shape to get your own numbers.

## How it's laid out

```
server.py              Entrypoint — env validation happens on import, then uvicorn.run()
onboard.py              Interactive taxonomy.json setup wizard — see "Folder taxonomy" below
core/
  config.py            Env vars, startup validation, logging setup
  taxonomy.py          Loads taxonomy.json: role paths + custom category definitions
  vault.py             Path-safety boundary: safe_path, iter_markdown, read/write, move, area roots;
                       also auto-linking (_auto_link), placement inference (infer_area),
                       and per-project subfolder validation (resolve_project_subfolder)
  frontmatter.py       Minimal YAML frontmatter split/join, used by tools/tags.py
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
    tags.py            get_tags, update_frontmatter
    move.py            move_note — opt-in via ENABLE_NOTE_MOVE, gated separately from write_tool
    custom.py          Dynamically registers a get/create pair per taxonomy.json custom category
index_vault.py         Standalone script: builds/refreshes the local semantic-search index
tests/                  pytest suite — see "CI and pre-commit gates" below
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
| `ENABLE_NOTE_MOVE` | `false` | `true` = registers `move_note`. Gated separately from, on top of, `READ_ONLY` — off by default even in read/write mode |
| `LOG_LEVEL` | `info` | Set to `debug` for verbose output (e.g. which files search skips and why) |
| `VAULT_EMBEDDINGS_DB` | `./vault_embeddings.db` | Override the semantic-search index location |
| `AUTO_LINK_ON_SAVE` | `true` | `false` disables the automatic "## Related notes" section on brand-new notes (no-op either way until a semantic index exists) |
| `RATE_LIMIT_MAX_REQUESTS` | `120` | Requests allowed per source IP per `RATE_LIMIT_WINDOW_SECONDS` |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window size, in seconds, for the request-rate cap |
| `OAUTH_ISSUER_URL` | *(unset)* | Set only for remote deployments, e.g. `https://<host>.<tailnet>.ts.net` — enables the self-hosted OAuth 2.1 flow. Unset = today's bearer-token-only behavior, no OAuth routes registered at all |
| `AUTHORIZE_PASSWORD` | *(required if `OAUTH_ISSUER_URL` is set)* | Gates the `/login` consent screen — the single password that authorizes an OAuth client |
| `OAUTH_STORE_DB` | `./oauth_store.db` | Override where registered clients, authorization codes, and tokens are persisted |
| `TAXONOMY_JSON_PATH` | `./taxonomy.json` | Override where `taxonomy.json` is read from/written to — mainly for running multiple instances against different taxonomies, or test isolation |
| `ALLOWED_REDIRECT_HOSTS` | `claude.ai` | Comma-separated hosts an OAuth client's `redirect_uri` must match to complete registration — dynamic client registration is unauthenticated by spec, so this is what stops a random internet client from registering at all |

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

Once that index exists, every write tool (`save_decision`,
`save_brainstorm`, `create_app_idea`, `update_feature`, and any custom
category's `create_<key>_note`) re-embeds the note it just wrote, so the
index stays current automatically — you only need to rerun `index_vault.py`
by hand for edits made outside these tools (e.g. editing directly in
Obsidian) or for the very first build.

It also unlocks two more behaviors, both on brand-new notes only (never on
an edit to an existing one): a "## Related notes" section gets appended
linking to close semantic matches (`AUTO_LINK_ON_SAVE=false` to disable),
and `save_brainstorm` routes near related notes instead of always landing
in the inbox when no explicit `area` is given — raising a clear error
naming the candidates if existing notes disagree on where it belongs
rather than guessing.

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
| `save_brainstorm` | write | Save a brainstorm/conversation conclusion; auto-routed near related notes if a semantic index exists, else the configured `inbox` folder |
| `get_tags` | read | A note's frontmatter `tags:` array plus inline `#tag` mentions in the body |
| `update_frontmatter` | write | Create or update a note's YAML frontmatter (any property, not just tags); never touches the body |
| `move_note` | write, opt-in | Move/rename a note within the vault — requires `ENABLE_NOTE_MOVE=true` (off by default even in read/write mode); not registered otherwise |

9 of the 16 tools (everything except `read_note`, `search_vaultex`,
`semantic_search_vaultex`, `save_brainstorm`, `get_tags`,
`update_frontmatter`, and `move_note`) resolve through
`taxonomy.json` — see "Folder taxonomy" below. Any custom categories from
`taxonomy.json` add their own `get_<key>`/`create_<key>_note` tools to this
list at server startup. `get_tags`/`update_frontmatter` work on any note by
path and don't go through `taxonomy.json` at all. `move_note` also works on
any note by path, and — unlike every other write tool — is gated by its own
`ENABLE_NOTE_MOVE` flag on top of `READ_ONLY`, since relocate-and-possibly-
overwrite is a riskier capability than an additive write. There's still no
delete tool: a moved note still exists, just at a different path.

`save_decision` and `update_feature` also accept a `subfolder` parameter for
Builder projects with subfolders configured in `taxonomy.json`'s
`project_subfolders` (see "Folder taxonomy" below) — required when the
project has any configured, omitted otherwise.

New notes created by any write tool above get an automatic "## Related
notes" section linking to close semantic matches, and `save_brainstorm`
auto-routes to sit next to related notes rather than always landing in the
inbox — both no-ops until a semantic index exists (`index_vault.py`), and
both configurable/disableable (see "Configuration reference").

## Folder taxonomy

Fresh clone, no `taxonomy.json` yet = a taxonomy-free server. Reads among
the 9 role-gated tools raise a clear `TaxonomyNotConfigured` error instead
of silently returning nothing; writes raise instead of silently creating a
folder in your vault. Run `python3 onboard.py` to fix that — it:

- Scans your vault's existing top-level folders and lets you assign each of
  the 7 built-in roles (ideas, builder projects, professional decisions,
  professional tech analysis, professional architecture, professional
  projects, inbox) to one of them, a custom path you type, or skip it.
  Offers three modes: map each role yourself (guided), skip for now, or
  apply a working example taxonomy as a starting point — see below.
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

### Example taxonomy

A real, working mapping — one option in `onboard.py`'s menu applies this
directly as a starting point instead of mapping each role by hand:

| Role | Folder |
|---|---|
| `builder_ideas` | `02-Builder/Ideas` |
| `builder_projects` | `02-Builder/Projects` |
| `professional_decisions` | `01-Professional/Solution-Architecture/Decisions` |
| `professional_tech_analysis` | `01-Professional/Solution-Architecture/Gap-Analysis` |
| `professional_architecture` | `01-Professional/Solution-Architecture/Architecture` |
| `professional_projects` | `01-Professional/Solution-Architecture/Projects` |
| `inbox` | `00-Inbox` |

This is one example shape, not a default — a fresh clone still ships with
every role unconfigured until `onboard.py` runs. Picking this option
creates any of these folders that don't already exist in your vault, then
you can re-run the wizard (without `--reconfigure`) any time to adjust
individual roles.

### Per-project subfolders (optional)

Separate from the 7 built-in roles: a Builder project (`builder_projects`
role, `save_decision`/`update_feature` with `professional=False`) can opt
into a fixed set of subfolders via `taxonomy.json`'s `project_subfolders`:

```json
"project_subfolders": {
  "MyProject": ["architecture", "general", "archives"]
}
```

Once a project has an entry, `save_decision`/`update_feature` **require** a
`subfolder` argument for that project and reject anything not in the list —
no guessing, no silent default. A project with no entry (the default for
every project, including in a fresh clone) keeps the flat project-root
behavior every project has always had; this is opt-in, not a breaking
change. `onboard.py` doesn't configure this yet — edit `taxonomy.json`
directly.

Subfolder names are up to you; `architecture`/`legal`/`general` are just a
convention (a legal-sensitive product wants `legal`, most don't). One name
worth adopting everywhere: `archives`, for notes that are discarded/shelved/
no-longer-applicable — an alternative to deleting them (there's still no
delete tool) that keeps them fully readable by every tool, just out of the
way. `move_note` (below) is how a note actually gets there.

For Path B (Docker), run it inside the container so it writes to the same
bind-mounted `taxonomy.json` the server reads:
```bash
docker compose exec -it vaultex python3 onboard.py   # -it: needs a real terminal for prompts
```
Restart afterward (`docker compose up -d --build`, or just `python3
server.py` again for Path A) to pick up changes — same as any other `.env`
edit.

## Security model

Found a vulnerability? See [SECURITY.md](SECURITY.md) for how to report it
privately rather than filing a public issue.

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
- **Move gated separately from writes**: `move_note` needs `ENABLE_NOTE_MOVE=true`
  on top of `READ_ONLY=false` — off by default even in read/write mode, since
  relocate-and-possibly-overwrite is riskier than an additive write. Both of
  its paths still go through the same `safe_path`/`EXCLUDED_AREAS` checks as
  every other tool. There is still no delete tool.
- **Rate limiting**: every request is capped per source IP on a sliding
  window (`RATE_LIMIT_MAX_REQUESTS` per `RATE_LIMIT_WINDOW_SECONDS`, default
  120/60s) — applied ahead of auth, so both a bearer-token guessing attempt
  and a leaked/over-shared token hammering the embedding-cost-bearing search
  tools hit a hard ceiling. See `RateLimitMiddleware` in `core/middleware.py`.
- **Failed-auth logging**: rejected bearer-token requests are logged
  (source IP + method/path, never the token itself) so a guessing attempt
  against a Path B deployment leaves a trace.

### Self-reviewed against OWASP Top 10 (2025)

A pass against the OWASP Top 10 (2025) checklist, verified against the
actual source rather than assumed — items below are things anyone can
re-check themselves, not just asserted:

- **No SQL/NoSQL injection surface** — all SQLite access (`core/oauth/store.py`,
  `core/embeddings.py`) uses parameterized `?` placeholders, no string-built
  queries.
- **No command injection** — no `shell=True`, no `eval`/`exec` anywhere in the
  codebase; `install.py`'s `subprocess` calls use list-form arguments against
  fixed commands, never attacker-controlled input.
- **Vault-root escape is blocked** — `safe_path()`'s containment check
  (`VAULT_PATH not in candidate.parents`) rejects any resolved path landing
  outside the vault, regardless of how it was constructed.
- **No secrets in source or git history** — `.env`, `taxonomy.json`, and the
  local `*.db` stores are gitignored and confirmed untracked
  (`git ls-files | grep -E '\.env$|\.db$|taxonomy\.json$'` returns nothing).
- **No raw stack traces or internal errors returned to clients** — tool
  errors surface through the MCP protocol's own error path, never an HTTP
  response body.
- **Baseline security headers set globally** —
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, and a restrictive
  `Permissions-Policy`, applied to every response via
  `SecurityHeadersMiddleware`.
- **No permissive CORS** — no CORS middleware is configured at all, which is
  the safe default (browsers block cross-origin requests with none
  configured); nothing here uses a wildcard origin with credentials.
- **OAuth hardening** — timing-safe comparisons throughout
  (`secrets.compare_digest`), PKCE and `state` handled by the MCP SDK's
  authorization layer, per-login-attempt and per-IP lockout on `/login`
  (`core/oauth/login.py`), and refresh-token rotation on every use.
- **No unrestricted resource consumption** — every request is rate-limited
  per source IP (`RateLimitMiddleware`, see "Security model" above), closing
  off unthrottled abuse of the embedding-cost-bearing search tools.
- **No known-vulnerable dependencies** — `pip-audit` runs against
  `requirements.txt` on every push/PR; zero known vulnerabilities as of the
  last run.

This is a self-review, not an independent third-party audit — treat it as a
starting point for your own risk assessment, not a certification.

### CI and pre-commit gates

- **`pip-audit`** runs on every push/PR (`.github/workflows/security.yml`),
  checking `requirements.txt` against known-vulnerability databases.
- **`gitleaks`** scans for committed secrets both in CI (same workflow) and
  locally: run `pip install pre-commit && pre-commit install` once to catch a
  secret before it's committed at all, not just after it's pushed.
- **`ruff`** lints on every push/PR (`.github/workflows/lint.yml`) and
  locally via the same pre-commit hook — pyflakes + pycodestyle-errors only
  (`ruff.toml`), so it catches real mistakes (unused imports, undefined
  names) rather than bikeshedding style.
- **`pytest`** runs on every push/PR (`.github/workflows/ci.yml`) — see
  `tests/` for what's covered so far: vault path-safety
  (`safe_path`/`check_area_allowed` — traversal and excluded-area blocking)
  and the frontmatter split/join round-trip. Run locally with `pytest` from
  the repo root (needs `requirements.txt` installed, or at minimum
  `pyyaml` + `python-dotenv` for just these two modules).

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

## Upgrading and uninstalling

**Upgrading** (either path): `git pull`, then re-run the install step for
your path — `.venv/bin/pip install -r requirements.txt` (Path A) or
`docker compose up -d --build` (Path B). Re-run `python3 index_vault.py`
only if a release notes a search-index format change; otherwise your
existing `vault_embeddings.db`/`oauth_store.db`/`taxonomy.json` carry over
untouched. Only the latest tagged release and `main` are supported — see
[SECURITY.md](SECURITY.md#supported-versions).

**Uninstalling**:
- **Path A**: delete the cloned repo folder (removes the `.venv`, the
  local `vault_embeddings.db`/`oauth_store.db`, everything). Your actual
  vault (`VAULTEX_PATH`) is a separate folder and is never touched.
- **Path B**: `docker compose down` stops and removes the containers.
  Add `-v` to also delete the `tailscale-state` volume (you'll need to
  re-run `tailscale funnel --bg 8000` and re-auth the sidecar if you ever
  bring it back up). Then delete the cloned repo folder as in Path A.
  Your vault is bind-mounted from `VAULTEX_PATH`, outside the repo, and is
  never touched by either step.

## Contributing

Bug reports, feature ideas, and PRs are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md)
for the dev setup, test policy, and PR checklist. Security issues go through
[SECURITY.md](SECURITY.md) instead of a public issue. Participation is
governed by the [Code of Conduct](CODE_OF_CONDUCT.md). See
[GOVERNANCE.md](GOVERNANCE.md) for how decisions get made, and
[ROADMAP.md](ROADMAP.md) for what's planned (and explicitly not planned)
over the next year.

## License

[MIT](LICENSE) — do what you want with it.
