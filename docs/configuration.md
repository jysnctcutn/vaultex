# Configuration reference

[← Back to README](../README.md) · [Docs index](README.md)

See [Installation](installation.md) for setup commands. Full list of
`.env` variables (all loaded automatically via python-dotenv; real exported
env vars still take precedence, so `FOO=bar python3 server.py` works for
one-offs):

| Variable | Default | Purpose |
|---|---|---|
| `VAULTEX_PATH` | `./vaultex` | Path to the Obsidian vault this server reads/writes |
| `MCP_AUTH_TOKEN` | *(required)* | Long random secret; clients send it as `Authorization: Bearer <token>` |
| `MCP_HOST` | `0.0.0.0` | Bind address |
| `MCP_PORT` | `8000` | Bind port |
| `EXCLUDED_AREAS` | *(none)* | Comma-separated top-level folders this instance refuses to touch at all, e.g. `01-Professional` |
| `VAULTEX_MODE` | *(derived)* | `basic` or `professional`. Unset = derived from `taxonomy.json` (configured → professional, else basic). Set by `setup/onboard.py`. See [Modes](modes.md) |
| `READ_ONLY` | `false` | `true` = write tools aren't even registered (not just blocked at call time) |
| `ENABLE_NOTE_MOVE` | `false` | `true` = registers `move_note`. Gated separately from, on top of, `READ_ONLY` — off by default even in read/write mode |
| `ENABLE_DISTILL_APPLY` | `false` | `true` = registers `apply_distillation` (distillation's durable write-back). Same gating pattern as `ENABLE_NOTE_MOVE`; `distill_session` stays available regardless |
| `LOG_LEVEL` | `info` | Set to `debug` for verbose output (e.g. which files search skips and why) |
| `VAULT_EMBEDDINGS_DB` | `./vault_embeddings.db` | Override the semantic-search index location |
| `AUTO_LINK_ON_SAVE` | `true` | **Deprecated** — superseded by `auto_link_on_save` in `write_policy.md`, which applies without a restart. ANDed with it, so an install already setting this `false` keeps that behavior; otherwise the policy file decides. See [Write policy](write-policy.md) |
| `SEARCH_LOG` | `false` | `true` = log every `search` call (query, params, fused top results) to a `search_events` table in `vault_embeddings.db`. Best-effort; raw material for a future Learning-to-Rank ranker, nothing reads it yet |
| `RATE_LIMIT_MAX_REQUESTS` | `120` | Requests allowed per source IP per `RATE_LIMIT_WINDOW_SECONDS` |
| `RATE_LIMIT_WINDOW_SECONDS` | `60` | Sliding window size, in seconds, for the request-rate cap |
| `OAUTH_ISSUER_URL` | *(unset)* | Set only for remote deployments, e.g. `https://<host>.<tailnet>.ts.net` — enables the self-hosted OAuth 2.1 flow. Unset = today's bearer-token-only behavior, no OAuth routes registered at all |
| `AUTHORIZE_PASSWORD` | *(required if `OAUTH_ISSUER_URL` is set)* | Gates the `/login` consent screen — the single password that authorizes an OAuth client |
| `OAUTH_STORE_DB` | `./oauth_store.db` | Override where registered clients, authorization codes, and tokens are persisted |
| `TAXONOMY_JSON_PATH` | `./taxonomy.json` | Override where `taxonomy.json` is read from/written to — mainly for running multiple instances against different taxonomies, or test isolation |
| `ALLOWED_REDIRECT_HOSTS` | `claude.ai` | Comma-separated hosts an OAuth client's `redirect_uri` must match to complete registration — dynamic client registration is unauthenticated by spec, so this is what stops a random internet client from registering at all |

## Running

Serves MCP over streamable HTTP at `http://<host>:<port>/mcp`, gated by the
bearer token (and OAuth too, if configured — see [Remote
access](remote-access.md)). Every response also carries a small set of
baseline security headers (`X-Content-Type-Options`, `X-Frame-Options`,
`Referrer-Policy`, `Permissions-Policy`).

## Semantic search (optional)

`search` and `grep` work out of the box on keyword alone. To add
the semantic half of `search`'s ranking, `index_vault.py` builds the local
embeddings index — see [Installation](installation.md) for the exact
command in each path (`--full` forces a complete re-index instead of the
incremental default). Produces `vault_embeddings.db`, which stores raw vault
text and is git-ignored on purpose — never commit it.

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
