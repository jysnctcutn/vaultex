# Roadmap

What Vaultex intends to do, and explicitly not do, over the next year. This
reflects the project's actual working TODO list, not aspirational planning —
see [CONTRIBUTING.md](CONTRIBUTING.md) if you want to help with any of it.

## Planned

- **Agent memory system (episodic + distillation layer)** — the next major
  release. Vaultex today is a strong *durable* memory substrate (typed
  write tools, project-scoped retrieval, path isolation) but has no
  first-class *episodic* layer for agent session/event logs, and no
  deliberate step that promotes high-signal experience into durable
  project knowledge. Release will be in phases.
- **Section-aware editing** — patch a note by heading or block reference
  instead of rewriting the whole file, matching the PATCH-style editing
  other Obsidian MCP servers get for free from Obsidian's Local REST API
  plugin. Vaultex has no such dependency (reads/writes raw `.md` directly),
  so this means building an in-house heading/block-boundary parser. Rough
  shape: a heading-boundary scanner (respecting nesting), a block-reference
  scanner, splice operations (replace/append/prepend) on the identified
  range, and `createTargetIfMissing` to append a new heading when the
  target isn't found. Not started.
- **`search_vaultex` / `semantic_search_vaultex` merge question** — decide
  whether to blend keyword and semantic search into one tool or keep them
  separate. Still undecided.
- **Richer custom categories** — today's `taxonomy.json` custom categories
  are a simple list+create pattern only, no professional/builder split, no
  per-project subfolders, no sibling-file reads. New scope if richer
  behavior is ever wanted, not a bug fix.
- **Inline `#tag` rewriting** — `get_tags` is currently read-only
  reconciliation of frontmatter `tags:` plus inline `#tag` mentions.
  A write path was deferred over false-positive risk on a destructive
  edit; revisit if a safe rewrite strategy emerges.
- **Auto-routing extended beyond `save_brainstorm`** — placement inference
  (`infer_area()`) currently only applies to `save_brainstorm`, since the
  other write tools already have deterministic taxonomy-role routing.
  Could extend if a real need shows up.
- **OpenSSF Best Practices Gold** — Silver is in progress as of this
  roadmap's writing (governance docs, code of conduct, stricter static
  analysis, and expanded test coverage underway). Gold is the aspiration
  beyond it, but it's not purely a checklist away: it structurally requires
  a second, unaffiliated significant contributor and two-person code
  review on 50%+ of changes — neither of which exist yet for a
  solo-maintained project. Realistically blocked on the project actually
  growing a contributor base, not on more solo effort.

## Explicitly not planned
- **Obsidian plugin** — sync mechanics, push-only vs. in-app panel, and
  retention-on-delete are all open questions with no resolution. Not
  started.

## Out of scope, permanently

- Vaultex will not become a generic filesystem server (`read_file`/
  `write_file`/`list_directory`) — the meaningful-operations design and
  path-safety boundary are the point, not an implementation detail to
  optimize away.
