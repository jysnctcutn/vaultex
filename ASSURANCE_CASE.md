# Security Assurance Case

A documented argument for why Vaultex's security requirements are met, for
its actual deployment environment: a self-hosted, single-operator MCP
server, reachable either only from `localhost` (Path A) or from the public
internet via a Tailscale Funnel (Path B). Each claim below states a
requirement; the argument explains why it holds; the evidence is something
anyone can independently re-check, not just an assertion — most of it was
verified directly against the running code and repository during the
[[OpenSSF Best Practices Passing Badge — Compliance Record]] review, not
assumed from documentation.

This is a self-authored assurance case, not a third-party audit — see
[SECURITY.md](SECURITY.md) for the same caveat. It should be revisited
whenever a security-relevant claim below stops being true, not just on a
schedule.

## Claim 1: An unauthenticated request cannot execute any tool

**Argument**: Every request to `/mcp` passes through the bearer-token or
OAuth 2.1 access-token check before any tool handler runs, using a
timing-safe comparison so a wrong token can't be distinguished from a
missing one by response latency.

**Evidence**:
- `core/middleware.py` rejects with `401` before dispatch; `secrets.compare_digest` used, not `==`
- `core/oauth/provider.py:load_access_token` — same timing-safe check for OAuth tokens
- Direct test, this session: `docker exec vaultex-tailscale-1 wget http://127.0.0.1:8000/mcp` with no token → `401 Unauthorized`, confirming the server actually enforces this rather than only claiming to

## Claim 2: A tool call cannot read or write outside the configured vault, or inside an excluded area

**Argument**: Every path-accepting tool resolves the path against the vault
root and checks containment against the *resolved* path, not the literal
input string — closing the classic `<allowed>/../<excluded>/...` bypass
where an unresolved check would pass.

**Evidence**:
- `core/vault.py:check_area_allowed` — `candidate = (VAULT_PATH / relative).resolve()`, then containment and `EXCLUDED_AREAS` checked against `candidate`
- `tests/core/test_vault_safe_path.py` — regression tests for `../` traversal, absolute-path escape (`/etc/passwd`), and excluded-area access, all passing
- No tool in `core/tools/*.py` builds a filesystem path without going through `safe_path`/`check_area_allowed` (verified by reading every tool module)
- `move_note` (opt-in, `ENABLE_NOTE_MOVE`) resolves *both* its source and destination through `safe_path` before touching the filesystem — a restricted server instance can neither read a source nor write a destination that falls inside an excluded area. Covered by `tests/core/test_vault_move.py`'s traversal/excluded-area tests on both paths independently.

## Claim 3: No secret (token, password, private key) is committed to the repository, past or present

**Argument**: `.env`, `taxonomy.json`, and the local `*.db` stores are
gitignored, and the full commit history has been scanned for accidentally
committed secrets, not just the current working tree.

**Evidence**:
- `.gitignore` covers `.env`, `taxonomy.json`, `vault_embeddings.db`, `oauth_store.db`
- Direct scan, this session: `gitleaks detect --source . --log-opts="--all"` across the complete git history (9 commits) → "no leaks found"
- `gitleaks` also runs on every push/PR (`.github/workflows/security.yml`) and as a local pre-commit hook, so this stays true going forward, not just at the time of this scan

## Claim 4: No dependency with a known vulnerability is shipped

**Argument**: `requirements.txt` is checked against vulnerability databases
before every merge, not just at release time.

**Evidence**:
- Direct run, this session: `pip-audit -r requirements.txt` → "No known vulnerabilities found"
- `pip-audit` also gated in CI (`security.yml`) on every push/PR — a vulnerable dependency can't merge to `main` even if introduced later

## Claim 5: A single client (malicious or buggy) cannot exhaust server resources through one request or a burst of requests

**Argument**: Two independent limits apply, ahead of auth: a per-source-IP
sliding-window rate limit on request *count*, and a hard upper bound on
per-request result size for every tool that reads multiple notes — closing
the gap where rate limiting alone caps how *often* a client can call a
tool but says nothing about how expensive one call can be.

**Evidence**:
- `core/middleware.py:RateLimitMiddleware` — sliding window, applied before auth, default 120 req/60s
- `core/vault.py:validate_limit` (`MAX_LIMIT = 200`) — every tool with a `limit` parameter (`search`, `grep`, `get_app_ideas`, `get_project_context`, `get_architecture_decisions`, `get_tech_analysis_history`, `get_architecture_context`) rejects an out-of-range value instead of silently accepting it
- `tests/core/test_vault_helpers.py` — regression tests for zero, negative, over-max, and non-integer `limit` values

## Claim 6: OAuth 2.1 remote access cannot be completed by an unauthorized party, even though dynamic client registration is unauthenticated by spec

**Argument**: Registration alone can't complete a flow — the redirect must
land on an allowlisted host, and the `/login` consent step is password-
gated with both per-attempt and per-IP lockout, so the password can't be
brute-forced at meaningful scale.

**Evidence**:
- `core/oauth/provider.py:register_client` — rejects any `redirect_uri` whose host isn't in `ALLOWED_REDIRECT_HOSTS` (default `claude.ai`)
- `core/oauth/login.py` — 5 failed attempts kills that `login_id`; 10 failed attempts from one IP within 15 minutes locks out that IP regardless of `login_id`; `secrets.compare_digest` for the password check
- PKCE and `state` handled by the MCP SDK's authorization layer (not reimplemented)

## Claim 7: All cryptographic operations use vetted primitives, never a broken algorithm or a hand-rolled implementation

**Argument**: The project performs no custom cryptography — every random
value comes from the OS CSPRNG via Python's `secrets` module, and PKCE is
delegated entirely to the `mcp` SDK.

**Evidence**:
- Direct grep, this session: zero uses of the insecure `random` module anywhere in the codebase; zero occurrences of MD4/MD5/DES/RC4/Dual-EC-DRBG
- 6 confirmed call sites of `secrets.token_urlsafe`/`secrets.compare_digest` across `core/config.py`, `core/oauth/store.py`, `core/oauth/provider.py`, `core/oauth/login.py`

## What this assurance case does not cover

- **Availability under sustained distributed attack** (e.g. many IPs each under the rate limit) — out of scope for a single-operator self-hosted tool; Tailscale Funnel's own edge infrastructure is the actual line of defense here, not this codebase.
- **Confidentiality of vault content in transit for Path A** — Path A is `localhost`-only by design (no port published to the host in the Docker case), so there is no network segment to secure.
- **Indirect prompt injection via note content flowing back into a calling LLM's context** — a known, documented risk of any tool that hands file content to an LLM. Vaultex doesn't sanitize note *content* for this (it would break legitimate use of the vault), and no mitigation currently exists. Flagged as an open risk here rather than silently omitted — see the 2026-08-18 security audit note in the vault for the original flag.

## Related

- [SECURITY.md](SECURITY.md) — vulnerability reporting process and the security-model summary this assurance case expands on
- [[OpenSSF Best Practices Passing Badge — Compliance Record]] — the vault note this assurance case's evidence was gathered during
