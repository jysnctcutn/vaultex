# Upgrading

How to move between Vaultex versions, and what changed along the way. See
[ROADMAP.md](ROADMAP.md) for what's planned next, and the [releases
page](https://github.com/jysnctcutn/vaultex/releases) / `git tag -n99` for
the full list of tagged versions.

## General upgrade steps

Vaultex has no database migrations and no persistent server-side state
beyond your vault, `.env`, `taxonomy.json`, and the local SQLite index/OAuth
stores — upgrading is a code update, not a data migration, unless a
specific version below says otherwise.

**Path A (local venv):**

```bash
git pull
pip install -r requirements.txt -r requirements-dev.txt
```

**Path B (Docker / Tailscale sidecar):**

```bash
git pull
docker compose build
docker compose up -d
```

Re-run `pytest` after upgrading if you maintain a fork or local changes, to
confirm nothing you rely on regressed.

## Version-specific notes

### v0.1.0 → v0.2.0

No breaking changes. Every addition in v0.2.0 is opt-in and defaults to the
v0.1.0 behavior if you don't touch your `.env`/`taxonomy.json`:

- **Per-project subfolders** (`architecture`/`legal`/`general`/`archives` on
  `save_decision`/`update_feature`) only activate if you add
  `project_subfolders` to `taxonomy.json`. Existing flat-layout vaults are
  unaffected.
- **`move_note` tool** only appears if you set `ENABLE_NOTE_MOVE=true` in
  `.env`. Unset (the v0.1.0 default) means the tool isn't registered at
  all.
- **`validate_limit` input validation** on every tool's `limit` parameter is
  always-on and not configurable — a call that previously sent an
  out-of-range or non-integer `limit` will now be rejected instead of
  silently accepted. This is the one behavior change worth testing for if
  you have a client that constructs `limit` programmatically.
- **`get_feature_context` bug fix** — it previously only found feature notes
  living directly at a project's root; it now also finds them in
  subfolders. No action needed; this only fixes cases that were previously
  silently returning nothing.

No config keys were renamed or removed, and no MCP tool signatures changed
in a way that breaks existing calls.

## Upgrade policy going forward

- Breaking changes (renamed/removed config keys, changed tool signatures,
  altered on-disk formats) will get their own dated entry in this file
  under "Version-specific notes," with the specific interfaces that changed
  and the steps to migrate — not just a changelog one-liner.
- Purely additive, opt-in changes (new tools, new optional config) are
  noted here for completeness but don't require any action to stay on the
  new version.
- Once the project has enough of a user base that pinning to an older
  tagged release is common, this document will also start tracking which
  older versions remain security-supported (today: only `main` /latest tag,
  per [SECURITY.md](../SECURITY.md)).