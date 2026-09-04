# Installation

[← Back to README](../README.md) · [Docs index](README.md)

The [README](../README.md#30-second-installation) covers the one-command
installer. This page is everything else: what that installer does under the
hood, the manual four-stage setup, the two deployment paths, and how to
upgrade or uninstall.

## The one-command installer

```bash
git clone https://github.com/jysnctcutn/vaultex.git
python3 install.py   # macOS/Linux
python install.py    # Windows
```

It walks through everything the manual stages below cover by hand:
- Points at an existing vault, or creates one
- Choose Path A (this machine only) or Path B (also reachable from Claude
  web/mobile)
- Installs dependencies — venv + pip for Path A, Docker + Tailscale for
  Path B
- Sets up your folder taxonomy: guided, a sensible default, or skip for now
- Builds the semantic-search index automatically
- Prints your access token and, on Path A, offers to start the server
  right away

Once it's running, connect your client — see
[Connect your AI](../README.md#connect-your-ai).

## Manual setup

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

Every variable is listed in the
[configuration reference](configuration.md).

### 3. Pick a mode (and, in Professional, a folder layout)

```bash
python3 onboard.py
```

Its first question is [Basic or Professional](modes.md), and it explains
both before you answer. The choice is written to `.env` as `VAULTEX_MODE`.

**Basic** finishes here — four tools, no taxonomy, your folders left alone.

**Professional** continues to a layout:

1. **PARA** — scaffolds `Projects/ Areas/ Resources/ Archive/` and maps the
   built-in roles into them (recommended for a fresh vault)
2. **Guided** — map each role onto folders you already have
3. **Author's layout** — the maintainer's own structure, as a starting point
4. **Skip** — leave roles unconfigured for now

Then it asks what to call your workspaces (press enter for a single one),
and seeds a [`write_policy.md`](write-policy.md) into your vault.

Skipping this stage entirely still leaves a working server: with no
taxonomy, the mode derives to Basic. Full detail in
[Folder taxonomy](taxonomy.md). Safe to run later — nothing here blocks
stage 4.

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
[Remote access](remote-access.md) for what to do if something looks stuck.

## Upgrading and uninstalling

**Upgrading** (either path): `git pull`, then re-run the install step for
your path — `.venv/bin/pip install -r requirements.txt` (Path A) or
`docker compose up -d --build` (Path B). Re-run `python3 index_vault.py`
only if a release notes a search-index format change; otherwise your
existing `vault_embeddings.db`/`oauth_store.db`/`taxonomy.json` carry over
untouched. Only the latest tagged release and `main` are supported — see
[SECURITY.md](../SECURITY.md#supported-versions).

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
