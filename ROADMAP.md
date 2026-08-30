# Roadmap

What Vaultex intends to do, and explicitly not do, over the next year. This
reflects the project's actual working TODO list, not aspirational planning —
see [CONTRIBUTING.md](CONTRIBUTING.md) if you want to help with any of it.

## Shipped

- **Agent memory system (episodic + distillation layer)** — delivered in
  phases: the episodic write path (`log_event` / `start_session` /
  `update_session` / `close_session`), time-scoped retrieval and provenance
  (`get_episodic_context`, `include_episodic`, `source_episodic` on
  `save_decision`, `save_open_question`), distillation (`distill_session`
  bundles a finished session; `apply_distillation` promotes an approved
  proposal into durable notes with provenance and marks the session
  `promoted`), and lightweight multi-agent coordination (`claim_note` /
  `release_note` / `flag_conflict` / `check_note_status` over note
  frontmatter). Follow-ups still open: provenance params on
  `update_feature`, and an agent-identity registry for the `agents:` field.
- **Blended search (`search` + `grep`)** — `search` is now the
  default tool: keyword and local-embedding semantic retrieval merged with
  Reciprocal Rank Fusion (k=60), de-duplicated by path, `score` and
  `sources` on every result, soft-failing to keyword-only when no semantic
  index exists. `grep` keeps literal substring lookup as its own
  tool. This revised the original "keep both retrievers as separate
  unchanged tools" decision — the standalone `semantic_search_vaultex`
  tool was folded into `search` as an internal helper, and the `_vaultex`
  suffix dropped to match the rest of the toolset. Full Learning-to-Rank
  is still a later upgrade (see Planned).

## Planned
- **Section-aware editing** — patch a note by heading or block reference
  instead of rewriting the whole file, matching the PATCH-style editing
  other Obsidian MCP servers get for free from Obsidian's Local REST API
  plugin. Vaultex has no such dependency (reads/writes raw `.md` directly),
  so this means building an in-house heading/block-boundary parser. Rough
  shape: a heading-boundary scanner (respecting nesting), a block-reference
  scanner, splice operations (replace/append/prepend) on the identified
  range, and `createTargetIfMissing` to append a new heading when the
  target isn't found. Not started.
- **Learning-to-Rank for `search`** — `search` ships with Reciprocal Rank
  Fusion as its blend method (see Shipped). Replacing the final ranking
  step with a learned model (linear or gradient-boosted tree over features
  from both retrievers) is the later upgrade; candidate generation stays
  the same, so it's a near drop-in with RRF kept as fallback. Gated on
  real query volume and a relevance signal — not started.
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
