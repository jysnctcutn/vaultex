# Vaultex documentation

Reference material split out of the top-level [README](../README.md). Start
there for the pitch and the one-command install; come here for the details.

| Page | What's in it |
|---|---|
| [Installation](installation.md) | The manual four-stage setup, hardware requirements, Path A vs Path B, upgrading and uninstalling |
| [Modes](modes.md) | Basic vs Professional, how the mode is chosen and switched, workspaces, and the deprecated `professional` flag |
| [Write policy](write-policy.md) | The four `write_policy.md` toggles, what stays non-configurable, and every failure mode a tool can return |
| [Configuration reference](configuration.md) | Every `.env` variable, what "Running" serves, and how the optional semantic-search index behaves |
| [Available tools](tools.md) | The full tool table (31 in Professional mode, 4 in Basic) and the episodic-memory / distillation / coordination lifecycle prose |
| [Folder taxonomy](taxonomy.md) | `setup/onboard.py`, the 9 built-in roles, custom categories, per-project subfolders, the example mapping |
| [Architecture](architecture.md) | How the repo is laid out — `server.py`, `core/`, `tools/` |
| [Security model](security-model.md) | Path safety, auth, the OWASP Top 10 (2025) self-review, CI and pre-commit gates |
| [Remote access](remote-access.md) | The self-hosted OAuth 2.1 server, the Tailscale sidecar, and Path B troubleshooting |
| [Benchmarks](benchmarks.md) | The manual-context-handover measurement and how to reproduce it |
| [Memory curator](memory-curator.md) | The curator role that turns a distilled session into durable notes |
| [Roadmap](ROADMAP.md) | What's planned, and what's explicitly not |
| [Upgrading](UPGRADING.md) | Version-to-version upgrade notes |
| [Governance](GOVERNANCE.md) | How decisions get made |
| [Assurance case](ASSURANCE_CASE.md) | Claim-by-claim security argument and its evidence |
