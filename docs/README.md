# Vaultex documentation

Reference material split out of the top-level [README](../README.md). Start
there for the pitch, install, and quick start; come here for the details.

| Page | What's in it |
|---|---|
| [Configuration reference](configuration.md) | Every `.env` variable, what "Running" serves, and how the optional semantic-search index behaves |
| [Available tools](tools.md) | The full tool table (29 built-in) and the episodic-memory / distillation / coordination lifecycle prose |
| [Folder taxonomy](taxonomy.md) | `onboard.py`, the 9 built-in roles, custom categories, per-project subfolders, the example mapping |
| [Architecture](architecture.md) | How the repo is laid out — `server.py`, `core/`, `tools/` |
| [Security model](security-model.md) | Path safety, auth, the OWASP Top 10 (2025) self-review, CI and pre-commit gates |
| [Remote access](remote-access.md) | The self-hosted OAuth 2.1 server, the Tailscale sidecar, and Path B troubleshooting |
| [Benchmarks](benchmarks.md) | The manual-context-handover measurement and how to reproduce it |
| [Memory curator](memory-curator.md) | The curator role that turns a distilled session into durable notes |
