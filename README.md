```
██╗   ██╗ █████╗ ██╗   ██╗██╗  ████████╗███████╗██╗  ██╗ 
██║   ██║██╔══██╗██║   ██║██║  ╚══██╔══╝██╔════╝╚██╗██╔╝
██║   ██║███████║██║   ██║██║     ██║   █████╗   ╚███╔╝ 
╚██╗ ██╔╝██╔══██║██║   ██║██║     ██║   ██╔══╝   ██╔██╗ 
 ╚████╔╝ ██║  ██║╚██████╔╝███████╗██║   ███████╗██╔╝ ██╗
  ╚═══╝  ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚══════╝╚═╝  ╚═╝ MCP
Local-first context layer for AI agents.
No Cloud. No Subscriptions. One context. Every AI. 
MIT licensed. Free for individuals.
```
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14169/badge)](https://www.bestpractices.dev/projects/14169)&nbsp;
[![Security](https://github.com/jysnctcutn/vaultex/actions/workflows/security.yml/badge.svg)](https://github.com/jysnctcutn/vaultex/actions/workflows/security.yml)&nbsp;
[![MCP Server](https://badge.mcpx.dev?type=server)](https://modelcontextprotocol.io/)&nbsp;
[![CI](https://github.com/jysnctcutn/vaultex/actions/workflows/ci.yml/badge.svg)](https://github.com/jysnctcutn/vaultex/actions/workflows/ci.yml)&nbsp;
[![Lint](https://github.com/jysnctcutn/vaultex/actions/workflows/lint.yml/badge.svg)](https://github.com/jysnctcutn/vaultex/actions/workflows/lint.yml)&nbsp;
[![License](https://img.shields.io/github/license/jysnctcutn/vaultex)](LICENSE)&nbsp;
[![Python 3.14](https://img.shields.io/badge/python-3.14-blue?logo=python&logoColor=white)](https://www.python.org/) 
---

## VAULTEX MCP - local-first context layer for AI agents

Vaultex gives AI agents a persistent, local-first context layer backed by
your Markdown vault. Instead of treating your knowledge base as a raw
filesystem, it exposes *meaningful* context operations — search, read a
note, save a decision, gather everything about a project, and record an
agent's working trail so the next session, in any client, picks up where
the last one left off.

It is deliberately **not** a `read_file` / `write_file` /
`list_directory` server: every operation goes through a shared path-safety
layer that blocks traversal outside the vault and can hide entire
top-level areas (e.g. client or employer work) from a given server
instance. Your context stays on your machine or your own tailnet; any
MCP-compatible client reaches only the context you choose to share.

![Vaultex demo](./vaultex.gif)

**Contents:** [Features](#features) · [Modes](#modes) ·
[Easy install](#easy-install) · [Quick start](#quick-start) ·
[Connecting AI clients](#connecting-ai-clients-claude-chatgpt-grok) ·
[Opinionated writes](#opinionated-writes) ·
[Where this fits](#where-this-fits) ·
[Documentation](#related-documentation) ·
[Upgrading and uninstalling](#upgrading-and-uninstalling) ·
[Contributing](#contributing)

Deeper reference — modes, tools, configuration, taxonomy, security model,
remote access — lives in [`docs/`](docs/), linked from
[Documentation](#related-documentation) below.

## Features

- **A context layer, not raw filesystem access** — search, read a note,
  save a decision, gather everything about a project; no generic
  `read_file`/`write_file`/`list_directory` tools.
- **Agent memory lifecycle** — an agent opens an episodic session, writes a
  structured trail as it works, then distills the high-signal parts into
  durable project notes with provenance back to the session they came from.
  Plain Markdown throughout, no vector-only second store.
- **Built for multiple agents** — `claim_note` / `release_note` /
  `flag_conflict` put advisory locks and conflict markers in a note's
  frontmatter so concurrent agents don't clobber each other.
- **Path-safety by construction** — every tool routes through a shared
  boundary that blocks `..` traversal and can hide entire top-level folders
  (e.g. client/employer work) per server instance.
- **Two modes** — **Basic** points at any Markdown folder and gives you four
  tools with no taxonomy at all; **Professional** adds the full structured
  toolset. See [Modes](#modes) and [docs/modes.md](docs/modes.md).
- **31 built-in tools** in Professional mode, spanning search, project and
  architecture context, episodic memory, distillation, multi-agent
  coordination, tagging, and brainstorm capture — see
  [docs/tools.md](docs/tools.md).
- **Folder taxonomy** — map your vault's own folders (or scaffold PARA) once
  via `onboard.py`; define custom categories that become their own
  `get`/`create` tools automatically at startup.
- **Workspaces** — name your own project contexts ("Personal", "Work",
  "Sandbox") and pass `workspace=` to the project tools. Add one to
  `taxonomy.json` and it works on the next call, no restart.
- **Tunable write behavior** — a `write_policy.md` note at your vault root
  turns off auto-linking, placement inference, prefix stripping, or silent
  folder creation. Edit and save; the next write picks it up. See
  [docs/write-policy.md](docs/write-policy.md).
- **Local semantic search** — optional embeddings index (`index_vault.py`);
  keyword + embeddings merged with Reciprocal Rank Fusion, runs entirely on
  your machine, no cloud calls.
- **Two deployment paths** — fully local with no Docker/Tailscale (Path A),
  or self-hosted with a bundled Tailscale sidecar for remote access from
  Claude web/mobile (Path B).
- **Self-hosted OAuth 2.1** — `server.py` is its own single-user
  authorization server; no third-party gateway needed for remote clients.
- **Read-only mode** — `READ_ONLY=true` removes write tools from the tool
  list entirely, not just blocks them at call time.
- **No cloud, no subscriptions** — your vault stays on your machine or your
  own tailnet.

## Modes

Vaultex runs in one of two modes. `python3 onboard.py` asks which on its
first prompt and writes the answer to `.env` as `VAULTEX_MODE`.

| | **Basic** | **Professional** |
|---|---|---|
| Tools | 4 — `search`, `grep`, `read_note`, `write_note` | 31 — the above plus decisions, brainstorms, episodic memory, distillation, coordination, workspaces |
| Taxonomy | none | `taxonomy.json` |
| Folder layout | yours, untouched | PARA for a fresh vault, or mapped onto folders you already have |
| Writes | explicit path only | routed, named, section-checked, cross-linked |

**Basic** is the "point it at any Markdown folder" path — nothing to
configure, nothing to learn. **Professional** is the structured surface.

The two are mutually exclusive, not stacked: in Basic mode the structured
tools are *not registered at all*, so a taxonomy-free vault is a supported
configuration rather than an error state. With `VAULTEX_MODE` unset the mode
is derived from `taxonomy.json`, so existing installs are unaffected.

Full detail — switching, the derivation rule, **workspaces**, and the
deprecated `professional` flag — in [docs/modes.md](docs/modes.md).

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

### 3. Pick a mode (and, in Professional, a folder layout)

```bash
python3 onboard.py
```

Its first question is [Basic or Professional](#modes), and it explains both
before you answer. The choice is written to `.env` as `VAULTEX_MODE`.

**Basic** finishes here — four tools, no taxonomy, your folders left alone.

**Professional** continues to a layout:

1. **PARA** — scaffolds `Projects/ Areas/ Resources/ Archive/` and maps the
   built-in roles into them (recommended for a fresh vault)
2. **Guided** — map each role onto folders you already have
3. **Author's layout** — the maintainer's own structure, as a starting point
4. **Skip** — leave roles unconfigured for now

Then it asks what to call your workspaces (press enter for a single one),
and seeds a [`write_policy.md`](#opinionated-writes) into your vault.

Skipping this stage entirely still leaves a working server: with no
taxonomy, the mode derives to Basic. Full detail in
[docs/taxonomy.md](docs/taxonomy.md). Safe to run later — nothing here
blocks stage 4.

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
.venv/bin/python3 index_vault.py   # optional — adds semantic ranking to `search`
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
[docs/remote-access.md](docs/remote-access.md) for what to do if something
looks stuck.

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

## Opinionated writes

In Professional mode the structured write tools shape notes for you. Four
behaviors are switchable from a single note at your vault root,
`write_policy.md`:

```yaml
auto_link_on_save: true      # append a "## Related notes" footer to new notes
placement_inference: true    # let save_brainstorm pick the folder
strip_title_prefix: true     # avoid "Decision - Decision - …"
create_missing_folders: true # create a write's target folder if absent
```

Edit and save — the next write picks it up, no restart. With no file, every
toggle defaults to `true`, which is the pre-existing behavior. Want none of
it? Use `write_note`, or Basic mode.

The toggles, what stays deliberately non-configurable, and the **failure
modes** (`PlacementAmbiguous`, `TaxonomyNotConfigured`, `VerificationError`,
`WorkspaceNotConfigured`) are documented in
[docs/write-policy.md](docs/write-policy.md).

## Where this fits

There are two ways in:

```
                        VAULTEX
                  (Your Markdown vault)
                            │
                       MCP server
                   (server.py + core/)
                            │
             ┌──────────────┴──────────────────────────┐
             │                                         │
  (Path A - 1 Machine)                        (Path B - Cross device)
(local, direct — no tunnel needed)                Tailscale Funnel
              │                             (sidecar, in docker-compose)
              │                                        │                    
Claude Code + Desktop GUI                              │
                                      Grok, Claude, GPT and other AI Clients 
                                            (cli/web/ide/mobile/agents) 
                                             Obsidian/Noteable/Logseq
```

Local access (this machine) talks to `server.py` directly over localhost —
no tunnel, no OAuth, just the bearer token. Remote access (Claude's web or
mobile Connectors) reaches the server through a Tailscale Funnel — bundled as
a sidecar container in `docker-compose.yml`, so nothing needs installing on
the host — and authenticates via OAuth 2.1, which `server.py` implements
itself (`core/oauth/`). No third-party gateway sits in front of it.

## Related Documentation

Deeper reference lives in [`docs/`](docs/):

- **[Modes](docs/modes.md)** — Basic vs Professional, how the mode is chosen
  and switched, workspaces, and the deprecated `professional` flag
- **[Write policy](docs/write-policy.md)** — the four `write_policy.md`
  toggles, what stays non-configurable, and every failure mode a tool can
  return
- **[Configuration reference](docs/configuration.md)** — every `.env`
  variable, what "Running" serves, and the optional semantic-search index
- **[Available tools](docs/tools.md)** — the full 31-tool table and the
  episodic-memory / distillation / multi-agent coordination lifecycle
- **[Folder taxonomy](docs/taxonomy.md)** — `onboard.py`, the 9 built-in
  roles, workspaces, custom categories, per-project subfolders
- **[Architecture](docs/architecture.md)** — how the repo is laid out
  (`server.py`, `core/`, `tools/`)
- **[Security model](docs/security-model.md)** — path safety, auth, the
  OWASP Top 10 (2025) self-review, CI and pre-commit gates
- **[Remote access](docs/remote-access.md)** — the self-hosted OAuth 2.1
  server, the Tailscale sidecar, and Path B troubleshooting
- **[Benchmarks](docs/benchmarks.md)** — the manual-context-handover
  measurement and how to reproduce it
- **[Memory curator](docs/memory-curator.md)** — the curator role that turns
  a distilled session into durable notes

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
