# Contributing to Vaultex

Thanks for your interest in contributing. Vaultex is a local-first MCP server that exposes a markdown/Obsidian vault to AI clients as meaningful operations (search, read, decisions, project context) with a hard path-safety and access-control boundary.

## How to contribute

1. **Issues** — Bug reports and feature ideas go in [GitHub Issues](https://github.com/jysnctcutn/vaultex/issues). Search existing issues first.
2. **Security** — Do **not** file public issues for vulnerabilities. See [SECURITY.md](SECURITY.md).
3. **Pull requests** — Fork, branch from `main`, open a PR against `main`. Keep PRs focused (one concern per PR when practical).

### Pull request checklist

- [ ] Code follows existing style and patterns in the tree
- [ ] New behavior is covered by tests when practical (see below)
- [ ] `ruff` / lint is clean (or CI would pass)
- [ ] No secrets, tokens, or personal vault data in the diff
- [ ] README / docs updated if user-facing behavior changed

## Development setup

```bash
# Clone and enter the repo
git clone https://github.com/jysnctcutn/vaultex.git
cd vaultex

# Virtualenv (recommended)
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# torch is a transitive dep of sentence-transformers; on Linux pip defaults
# to the CUDA build (~3.5GB of unused nvidia/triton packages). Install the
# CPU wheel first, same as the Dockerfile:
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install runtime + dev deps
pip install -r requirements.txt -r requirements-dev.txt

# Optional: pre-commit (gitleaks + hooks)
pip install pre-commit && pre-commit install
```

Copy `.env.example` to `.env` if you need a local server run. Use a **throwaway test vault**, never a real personal/professional vault, when developing.

## Running tests

```bash
pytest
# or
python -m pytest
```

Useful variants:

```bash
pytest -q                  # quiet
pytest tests/path/to/file  # single file
pytest -k "safe_path"      # name filter
```

`tests/conftest.py` points the server at an isolated temp vault before any test imports `core/config.py` (which validates its env vars at import time) — tests never touch your real `.env` or vault.

### Test policy

- **Major new functionality** should include automated tests in the suite (or a clear justification in the PR if testing is impractical).
- Security-sensitive paths (path resolution, auth middleware, area exclusion) **must** have regression tests when changed.
- Prefer fast unit tests; reserve integration tests for boundaries that need a temporary vault fixture.

There is also a reproducible benchmark script under `benchmarks/` (context handover). It is not a substitute for the unit test suite but is useful for documenting performance claims.

## Linting

```bash
ruff check .
```

Base style guide is [PEP 8](https://peps.python.org/pep-0008/); `ruff.toml`
enforces the subset that catches real mistakes and common vulnerability
classes rather than bikeshedding style — pyflakes/pycodestyle (`E`, `F`,
`W`), bugbear (`B`), bandit-equivalent security rules (`S`), pyupgrade
(`UP`), and comprehension/simplification rules (`C4`, `SIM`). CI runs lint
and tests on pushes and pull requests to `main`. Please keep the branch
green.

## Coding guidelines

- Match the existing package layout under `core/` (`vault.py`, `middleware.py`, `tools/`, `oauth/`, etc.).
- Prefer explicit, small functions over clever abstractions.
- Never log or print secrets (tokens, passwords, full `.env` values).
- Path handling must go through the shared safety helpers (`safe_path` / `check_area_allowed`); do not reimplement ad-hoc path joins for vault access.
- New MCP tools should respect `READ_ONLY` and `EXCLUDED_AREAS` consistently with existing tools.

## Commit messages

Clear, imperative summaries are enough, e.g.:

- `Fix EXCLUDED_AREAS bypass via path resolution`
- `Add rate limiting middleware for search tools`
- `Document vulnerability reporting in SECURITY.md`

## Developer Certificate of Origin (DCO)

By contributing, you certify that you wrote the contribution yourself, or
otherwise have the right to submit it under the project's license, per the
[Developer Certificate of Origin](https://developercertificate.org/).
Sign your commits with `git commit -s` (adds a `Signed-off-by:` trailer
with your name and email) to certify this.

## License

By contributing, you agree that your contributions are licensed under the same **MIT** license as the project (see [LICENSE](LICENSE)).
