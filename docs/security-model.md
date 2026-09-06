# Security model

[← Back to README](../README.md) · [Docs index](README.md)

Found a vulnerability? See [SECURITY.md](../SECURITY.md) for how to report it
privately rather than filing a public issue.

- **Path safety**: every tool resolves through `safe_path`/`iter_markdown` in
  `core/vault.py`, which blocks `..` traversal outside the vault and enforces
  `EXCLUDED_AREAS` — a new tool can't accidentally bypass either check.
- **Auth**: without `OAUTH_ISSUER_URL` set, a single shared bearer token,
  compared with `secrets.compare_digest` (timing-safe) — wrong or missing
  token → `401` before any tool runs. With `OAUTH_ISSUER_URL` set, OAuth 2.1
  access tokens are accepted too (see [Remote access](remote-access.md)); the
  bearer token keeps working either way as a fallback for clients that can't
  do a browser OAuth flow.
- **Read-only mode**: `READ_ONLY=true` removes write tools from the tool list
  entirely, not just from what they're allowed to do.
- **Move gated separately from writes**: `move_note` needs `ENABLE_NOTE_MOVE=true`
  on top of `READ_ONLY=false` — off by default even in read/write mode, since
  relocate-and-possibly-overwrite is riskier than an additive write. Both of
  its paths still go through the same `safe_path`/`EXCLUDED_AREAS` checks as
  every other tool. There is still no delete tool.
- **Distillation write-back gated separately**: `apply_distillation` needs
  `ENABLE_DISTILL_APPLY=true` on top of `READ_ONLY=false`, and a per-call
  `confirm=True`, since it promotes episodic content into the durable store.
  `distill_session` (read-only bundling) is always available.
- **Rate limiting**: every request is capped per source IP on a sliding
  window (`RATE_LIMIT_MAX_REQUESTS` per `RATE_LIMIT_WINDOW_SECONDS`, default
  120/60s) — applied ahead of auth, so both a bearer-token guessing attempt
  and a leaked/over-shared token hammering the embedding-cost-bearing search
  tools hit a hard ceiling. See `RateLimitMiddleware` in `core/middleware.py`.
- **Failed-auth logging**: rejected bearer-token requests are logged
  (source IP + method/path, never the token itself) so a guessing attempt
  against a Path B deployment leaves a trace.

## Self-reviewed against OWASP Top 10 (2025)

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
  per source IP (`RateLimitMiddleware`, see "Rate limiting" above), closing
  off unthrottled abuse of the embedding-cost-bearing search tools.
- **No known-vulnerable dependencies** — `pip-audit` runs against
  `requirements.txt` on every push/PR; zero known vulnerabilities as of the
  last run.

This is a self-review, not an independent third-party audit — treat it as a
starting point for your own risk assessment, not a certification.

## CI and pre-commit gates

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
