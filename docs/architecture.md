# How it's laid out

[← Back to README](../README.md) · [Docs index](README.md)

```
server.py              Entrypoint — env validation happens on import, then uvicorn.run()
setup/
  install.py           First-run installer: vault, access, deps, mode, layout, index
  onboard.py           Taxonomy specialist: maps roles/workspaces onto an existing vault
  install_ui.py        Stdlib-only wizard UI both share — panels, arrow keys, plain fallback
core/
  config.py            Env vars, startup validation, logging setup
  taxonomy.py          Loads taxonomy.json: role paths + custom category definitions
  vault.py             Path-safety boundary: safe_path, iter_markdown, read/write, move, area roots;
                       also auto-linking (_auto_link), placement inference (infer_area),
                       and per-project subfolder validation (resolve_project_subfolder)
  frontmatter.py       Minimal YAML frontmatter split/join, used by tools/tags.py
  mcp_app.py           The MCPServer instance, OAuth wiring, write_tool/register_tool gates
  middleware.py        Bearer-token auth (non-OAuth fallback) + baseline security headers
  app.py               Wires tools + middleware into the Starlette ASGI app
  oauth/               Self-hosted OAuth 2.1 authorization server — see docs/remote-access.md
    store.py           SQLite persistence: clients, authorization codes, access/refresh tokens
    provider.py        VaultexOAuthProvider — implements OAuthAuthorizationServerProvider
    login.py           The single-user password-gate consent screen (/login)
  tools/
    search.py          read_note, search (RRF hybrid), grep
    builder.py         get_app_ideas, create_app_idea
    projects.py        get_project_context, get_feature_context, update_feature
    architecture.py    get_architecture_decisions, save_decision,
                       get_tech_analysis_history, get_architecture_context
    capture.py         save_brainstorm
    episodic.py        log_event, start_session, update_session, close_session,
                       get_episodic_context
    open_questions.py  save_open_question, get_open_questions
    distill.py         distill_session, apply_distillation — apply is opt-in via ENABLE_DISTILL_APPLY
    coordination.py    claim_note, release_note, flag_conflict, check_note_status
    tags.py            get_tags, update_frontmatter
    move.py            move_note — opt-in via ENABLE_NOTE_MOVE, gated separately from write_tool
    custom.py          Dynamically registers a get/create pair per taxonomy.json custom category
index_vault.py         Standalone script: builds/refreshes the local semantic-search index
tests/                  pytest suite — see docs/security-model.md ("CI and pre-commit gates")
Dockerfile              Image for the vaultex service
docker-compose.yml      vaultex + a bundled Tailscale sidecar — see docs/remote-access.md
```

Each `core/` module owns one concern; `tools/` is grouped by the part of the
vault a tool touches, not by read vs. write.
