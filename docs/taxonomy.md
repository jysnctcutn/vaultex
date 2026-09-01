# Folder taxonomy

[← Back to README](../README.md) · [Docs index](README.md)

Fresh clone, no `taxonomy.json` yet = a taxonomy-free server. Reads among
the 18 role-gated tools raise a clear `TaxonomyNotConfigured` error instead
of silently returning nothing; writes raise instead of silently creating a
folder in your vault. Run `python3 onboard.py` to fix that — it:

- Scans your vault's existing top-level folders and lets you assign each of
  the 9 built-in roles (ideas, builder projects, professional decisions,
  professional tech analysis, professional architecture, professional
  projects, inbox, episodic, open questions) to one of them, a custom path
  you type, or skip it. Offers three modes: map each role yourself (guided),
  skip for now, or apply a working example taxonomy as a starting point —
  see below.
- Optionally scaffolds the 4 [PARA](https://fortelabs.com/blog/para/)
  folders (`Projects/`, `Areas/`, `Resources/`, `Archive/`) if you want a
  starting structure rather than mapping onto something that already
  exists.
- Lets you define **custom categories** beyond the 9 built-in roles — e.g.
  your own "Meeting Notes" — each becoming a real `get_<key>`/
  `create_<key>_note` tool pair, registered dynamically at server startup.
  Optional per-category required sections (same mechanism `save_decision`
  uses for its `**Decided:**`/`**What it means:**` check) and filename
  prefix.
- Writes everything to `taxonomy.json` (gitignored — personal, same
  treatment as `.env`). Re-running edits it in place; `--reconfigure`
  starts fresh.

## Example taxonomy

A real, working mapping — one option in `onboard.py`'s menu applies this
directly as a starting point instead of mapping each role by hand:

| Role | Folder |
|---|---|
| `builder_ideas` | `02-Builder/Ideas` |
| `builder_projects` | `02-Builder/Projects` |
| `professional_decisions` | `01-Professional/Solution-Architecture/Decisions` |
| `professional_tech_analysis` | `01-Professional/Solution-Architecture/Gap-Analysis` |
| `professional_architecture` | `01-Professional/Solution-Architecture/Architecture` |
| `professional_projects` | `01-Professional/Solution-Architecture/Projects` |
| `inbox` | `00-Inbox` |
| `episodic` | `02-Builder/Episodic` |
| `open_questions` | `02-Builder/Open-Questions` |

This is one example shape, not a default — a fresh clone still ships with
every role unconfigured until `onboard.py` runs. Picking this option
creates any of these folders that don't already exist in your vault, then
you can re-run the wizard (without `--reconfigure`) any time to adjust
individual roles.

## Per-project subfolders (optional)

Separate from the 9 built-in roles: a Builder project (`builder_projects`
role, `save_decision`/`update_feature` with `professional=False`) can opt
into a fixed set of subfolders via `taxonomy.json`'s `project_subfolders`:

```json
"project_subfolders": {
  "MyProject": ["architecture", "general", "archives"]
}
```

Once a project has an entry, `save_decision`/`update_feature` **require** a
`subfolder` argument for that project and reject anything not in the list —
no guessing, no silent default. A project with no entry (the default for
every project, including in a fresh clone) keeps the flat project-root
behavior every project has always had; this is opt-in, not a breaking
change. `onboard.py` doesn't configure this yet — edit `taxonomy.json`
directly.

Subfolder names are up to you; `architecture`/`legal`/`general` are just a
convention (a legal-sensitive product wants `legal`, most don't). One name
worth adopting everywhere: `archives`, for notes that are discarded/shelved/
no-longer-applicable — an alternative to deleting them (there's still no
delete tool) that keeps them fully readable by every tool, just out of the
way. [`move_note`](tools.md) is how a note actually gets there.

For Path B (Docker), run it inside the container so it writes to the same
bind-mounted `taxonomy.json` the server reads:
```bash
docker compose exec -it vaultex python3 onboard.py   # -it: needs a real terminal for prompts
```
Restart afterward (`docker compose up -d --build`, or just `python3
server.py` again for Path A) to pick up changes — same as any other `.env`
edit.
