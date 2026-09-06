# Remote access (optional)

[← Back to README](../README.md) · [Docs index](README.md)

`server.py` is its own single-user OAuth 2.1 authorization server
(`core/oauth/`) — no third-party gateway required. `docker-compose.yml`
bundles it with a Tailscale sidecar so remote (web/mobile) access needs
nothing installed on the host beyond Docker and your own Tailscale account.
See [Installation → Path B](installation.md#4-pick-a-path-and-run-it) for the actual setup
commands.

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

## Troubleshooting

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
