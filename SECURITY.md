# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| `main` (latest) | ✅ |
| Latest tagged release | ✅ |
| Older tags | ❌ (please upgrade) |

Vaultex is a single-user, self-hosted MCP server. Security fixes land on `main` first and are included in the next tagged release.

## Verifying releases

Starting with `v0.3.0`, tagged releases are signed with the maintainer's
GPG key.

**Get the public key:**
- GitHub: [github.com/jysnctcutn.gpg](https://github.com/jysnctcutn.gpg)
  (also attached to the maintainer's [GitHub profile](https://github.com/jysnctcutn),
  so signed tags show a "Verified" badge on the repo's tags/releases pages)

**Verify a tag:**

```bash
git verify-tag v0.3.0
# or, after fetching the tag into a local clone:
git tag -v v0.3.0
```

Tags before `v0.3.0` predate this process and are not signed; if you need
integrity assurance for those, use `main` or upgrade to a signed release
per [UPGRADING.md](UPGRADING.md).

The private signing key lives only on the maintainer's local machine — it
is never stored in this repository or on any site used to distribute the
software.

## Reporting a Vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Please report security issues through one of these private channels:

1. **Preferred:** [GitHub Security Advisories](https://github.com/jysnctcutn/vaultex/security/advisories/new) (private, coordinated disclosure)
2. **Alternative:** Email the maintainer at the address listed on the [GitHub profile](https://github.com/jysnctcutn)

Include as much detail as you can:

- Description of the issue and impact
- Steps to reproduce (or a minimal proof-of-concept)
- Affected version / commit if known
- Whether you plan to disclose publicly and on what timeline

### What to expect

| Stage | Target |
|-------|--------|
| Acknowledgement | Within **14 days** |
| Initial assessment | Within **14 days** of acknowledgement |
| Fix or mitigation for confirmed issues | Aim for **60 days** when the issue is (or will become) public |

We may request more information, offer a draft advisory for review, or coordinate a disclosure date. Credit will be given in the advisory and release notes unless you prefer to remain anonymous.

### Scope notes

In scope (examples):

- Path traversal or `EXCLUDED_AREAS` bypass
- Authentication / authorization flaws (bearer token, OAuth)
- Rate-limit bypass that enables abuse
- Secrets leakage or unsafe defaults in the published tree
- Dependency vulnerabilities with a realistic exploit path in Vaultex's deployment model

Out of scope (examples):

- Issues that require the operator to deliberately weaken their own config (e.g. publishing `AUTHORIZE_PASSWORD` or turning off auth)
- Vulnerabilities solely in upstream dependencies with no practical impact on Vaultex (report those upstream; we track them via `pip-audit` in CI)
- Social engineering of the operator's machine or vault contents outside the server boundary

## Security model (summary)

Vaultex is designed as a **local-first, single-operator** tool. See the README's ["Security model"](README.md#security-model) section for the full breakdown, and [ASSURANCE_CASE.md](ASSURANCE_CASE.md) for the claim-by-claim argument and evidence behind each security requirement below. In short:

- Path safety blocks `..` traversal and respects `EXCLUDED_AREAS`, enforced against the resolved path rather than the input string
- Bearer-token auth uses timing-safe comparison (`secrets.compare_digest`); optional OAuth 2.1 with redirect-host allowlisting, PKCE, and per-login/per-IP lockout on `/login`
- `READ_ONLY=true` removes write tools from the tool list entirely, not only at call time
- Every request is rate-limited per source IP on a sliding window, ahead of auth
- No secrets committed to the repository (enforced by gitleaks in CI and pre-commit)
- Dependency vulnerabilities gated by `pip-audit` in CI

Operators remain responsible for:

- Protecting `.env`, tokens, and vault data on disk
- Using HTTPS / Tailscale Funnel (or equivalent) for any remote exposure
- Keeping the deployment and dependencies updated

## Preference for coordinated disclosure

We prefer coordinated disclosure so users can update before details are public. Thank you for helping keep Vaultex and its operators safe.
