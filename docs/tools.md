# Available tools

[← Back to README](../README.md) · [Docs index](README.md)

| Tool | Read/Write | What it does |
|---|---|---|
| `read_note` | read | Full verbatim content of one note by path |
| `search` | read | Default search — keyword + local-embedding semantic, merged with Reciprocal Rank Fusion (k=60); each hit carries `score` and `sources`; soft-fails to keyword-only with no embeddings index |
| `grep` | read | Literal substring search across titles and content — no ranking, no embeddings; for exact strings |
| `get_app_ideas` | read | List app ideas under the configured `builder_ideas` folder |
| `create_app_idea` | write | Create a new app idea note |
| `get_project_context` | read | All notes for a Builder or Solution-Architecture project; `include_episodic=True` also appends recent episodic notes for it |
| `get_feature_context` | read | One feature note plus sibling Architecture/Decisions notes |
| `update_feature` | write | Create or update a project's feature note |
| `get_architecture_decisions` | read | List decision notes, professional or per-project |
| `save_decision` | write | Save an architecture/product decision note; optional `source_episodic` + `agents` stamp provenance frontmatter for agent-originated decisions |
| `get_tech_analysis_history` | read | List tech-analysis notes, optionally filtered by project |
| `get_solution_architecture_context` | read | A project's notes + matching tech-analysis + architecture notes |
| `save_brainstorm` | write | Save a brainstorm/conversation conclusion; auto-routed near related notes if a semantic index exists, else the configured `inbox` folder |
| `get_tags` | read | A note's frontmatter `tags:` array plus inline `#tag` mentions in the body |
| `update_frontmatter` | write | Create or update a note's YAML frontmatter (any property, not just tags); never touches the body |
| `move_note` | write, opt-in | Move/rename a note within the vault — requires `ENABLE_NOTE_MOVE=true` (off by default even in read/write mode); not registered otherwise |
| `log_event` | write | Append a one-shot episodic event/outcome note under the configured `episodic` folder |
| `start_session` | write | Open an episodic session note bracketing a multi-turn agent run; returns its path |
| `update_session` | write | Rewrite an open session's body sections (`What happened` / `Decisions` / `Open questions` / `Artifacts`) in place, so detail lands before close |
| `close_session` | write | Close a session opened by `start_session` — sets `status: closed`, stamps `ended`, appends `## Outcome` |
| `get_episodic_context` | read | Recent episodic notes for a project + time window; filter by `kind`/`status` |
| `save_open_question` | write | Promote a question raised in an agent run into the durable per-project `open_questions` store |
| `get_open_questions` | read | List a project's open-question notes, optionally filtered by `status` |
| `distill_session` | read | Bundle a closed session + its project context + the proposal schema for a curator to turn into durable notes |
| `apply_distillation` | write, opt-in | Write a filled distillation proposal (decisions + open questions, with provenance) and mark the session `promoted` — requires `ENABLE_DISTILL_APPLY=true` and `confirm=True`; not registered otherwise |
| `claim_note` | write | Claim a note for exclusive editing by an agent — sets `locked_by` / `locked_at`; refuses a foreign lock unless `force=True` |
| `release_note` | write | Clear a note's `locked_by` / `locked_at` — refuses to release another agent's lock unless `force=True` |
| `flag_conflict` | write | Mark a note `status: conflict`, record `conflicts_with`, and append a `## Conflict (<date>)` body section |
| `check_note_status` | read | A note's `locked_by` / `locked_at` / `status` / `conflicts_with` without reading the whole note — the pre-edit check |

18 of the 29 tools (everything except `read_note`, `search`, `grep`,
`save_brainstorm`, `get_tags`, `update_frontmatter`, `move_note`,
`claim_note`, `release_note`, `flag_conflict`, and `check_note_status`)
resolve through
`taxonomy.json` — see [Folder taxonomy](taxonomy.md). Any custom categories
from `taxonomy.json` add their own `get_<key>`/`create_<key>_note` tools to
this list at server startup. `get_tags`/`update_frontmatter` work on any
note by path and don't go through `taxonomy.json` at all. `move_note` also
works on any note by path, and — unlike every other write tool — is gated by
its own `ENABLE_NOTE_MOVE` flag on top of `READ_ONLY`, since
relocate-and-possibly-overwrite is a riskier capability than an additive
write. There's still no delete tool: a moved note still exists, just at a
different path. `apply_distillation` is gated the same way, by
`ENABLE_DISTILL_APPLY`, since it promotes episodic content into the durable
store.

`save_decision` and `update_feature` also accept a `subfolder` parameter for
Builder projects with subfolders configured in `taxonomy.json`'s
`project_subfolders` (see [Folder taxonomy](taxonomy.md)) — required when the
project has any configured, omitted otherwise.

New notes created by any write tool above get an automatic "## Related
notes" section linking to close semantic matches, and `save_brainstorm`
auto-routes to sit next to related notes rather than always landing in the
inbox — both no-ops until a semantic index exists (`index_vault.py`), and
both configurable/disableable (see [Configuration
reference](configuration.md)).

`log_event`/`start_session`/`update_session`/`close_session` are append-only
and hard-validate the body on every write: `## Goal`, `## What happened`,
`## Decisions made (raw)`, `## Open questions left`, and
`## Artifacts / links` must all be present (`close_session` additionally
requires `## Outcome`), or the write is rejected naming what's missing.
They write into the `episodic` folder, never into a project's durable
folder directly.

`get_episodic_context` reads that trail back for a project over a time
window, and `get_project_context(..., include_episodic=True)` folds it into
a normal project read. `save_decision`'s optional `source_episodic` +
`agents` record which session a durable decision came from, and
`save_open_question` promotes a still-open unknown into the per-project
`open_questions` store.

`distill_session` closes the loop: it bundles a finished session with the
project's current durable context and the proposal schema, a curator
(see [memory-curator.md](memory-curator.md)) turns that into a proposal of new
decisions / open questions / discards, and `apply_distillation` writes the
approved proposal back — each note stamped with `source_episodic` + the
session's `agents`, and the session marked `promoted: true`. Nothing is
promoted silently: `apply_distillation` needs `ENABLE_DISTILL_APPLY` and an
explicit `confirm=True`, and edits to existing notes are returned as
advice, not auto-applied.

The full lifecycle: **an agent works → writes a structured episodic trail
→ later distills the high-signal parts → durable project knowledge grows,
with provenance back to the session it came from.** All plain Markdown,
Obsidian-editable, local-first — no vector-only second store.

For concurrent agents, `claim_note` / `release_note` put a `locked_by` /
`locked_at` marker in a note's frontmatter, `flag_conflict` marks a note
`status: conflict` with links to the competing notes, and
`check_note_status` is the cheap pre-edit lookup. There's no distributed
consensus — agents are told (via skill / system prompt) to claim before a
major edit and to stop on a lock or conflict they don't own; `force=True`
overrides a stale lock. All four work on any note by path.
