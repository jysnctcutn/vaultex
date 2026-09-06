---
auto_link_on_save: true
placement_inference: true
strip_title_prefix: true
create_missing_folders: true
---

# Write Policy

Controls how much Vaultex's **Professional** structured write tools
(`save_decision`, `save_brainstorm`, `create_app_idea`, `save_open_question`,
and any custom-category create tools) shape a note on your behalf.

Edit the frontmatter above and save. The next write picks it up — no server
restart, no redeploy.

**This file does not apply to:**

- **Basic mode** — always writes with zero inference, and never reads this file.
- **`write_note`** — the low-level explicit-path tool, in either mode. Being
  zero-inference is the entire point of it.

Vaultex refuses to write or move this file through any tool. Edit it directly.

---

## `auto_link_on_save`  (default: `true`)

**What it does.** After a **brand-new** note is created, runs a semantic lookup
on the note's title + content and appends a footer:

```
## Related notes
- [[Some Closely Related Note]]
```

**`true`** — the footer is appended when all of these hold: the note is new
(never on an edit), semantic dependencies are installed, `vault_embeddings.db`
exists, and a match falls within cosine distance 0.35.

**`false`** — nothing is ever appended. Notes are written exactly as produced.

**Turn it off if** you maintain links by hand, use a different link convention,
or don't want anything editing note bodies.

**It does not** touch existing notes, rewrite prose, or insert inline
`[[links]]` — only ever an appended footer, only on creation.

---

## `placement_inference`  (default: `true`)

**What it does.** When `save_brainstorm` is called **without** an explicit
`area`, semantic-searches for similar notes and files the new note beside its
closest match instead of defaulting to the inbox.

**`true`** — infer the folder. If the closest matches disagree with no clear
leader (under 80% agreement), the call fails with `PlacementAmbiguous`, listing
candidate folders so the caller can retry with an explicit `area`.

**`false`** — never infer, and **never raise `PlacementAmbiguous`**. The note
goes to the explicit `area` if given, otherwise straight to your inbox.

**Turn it off if** you prefer to triage from an inbox yourself, or
`PlacementAmbiguous` keeps interrupting agents mid-run.

**It does not** affect tools with fixed destinations from `taxonomy.json`
(`save_decision`, `create_app_idea`, `save_open_question`, custom categories) —
those never infer.

---

## `strip_title_prefix`  (default: `true`)

**What it does.** Tools that prepend a filename prefix strip that prefix from
the title first, so a title copied from an existing note doesn't double up.

`save_decision(title="Decision - Use Postgres")`

- `true`  → `Decision - Use Postgres.md`
- `false` → `Decision - Decision - Use Postgres.md`

**Turn it off if** your titles legitimately begin with the same words as a
prefix and you want them preserved verbatim.

**It does not** change the prefixes themselves, or affect the episodic log,
which uses its own dash-separated filename convention.

---

## `create_missing_folders`  (default: `true`)

**What it does.** Decides what happens when a write targets a folder that
doesn't exist.

**`true`** — the folder and any missing parents are created silently. A typo'd
`area="03-Knowlege/AI"` quietly creates `03-Knowlege/`.

**`false`** — the write fails, naming the folder that doesn't exist. Nothing is
created. Notes only land in folders you made yourself.

**Turn it off if** you have established folder conventions and would rather a
mistake be loud than tidy itself into a new directory.

**It does not** affect folders declared in `taxonomy.json` — those are created
during onboarding, not by writes.

---

## Not configurable here

**Path separators in titles** are always replaced. `create_app_idea("Auth/OAuth
notes")` writes `Auth-OAuth notes.md`, never an `Auth/` subfolder. Landing a
note in an unintended folder is a bug, not a preference.

**Required sections.** `save_decision` requires `**Decided:**` and
`**What it means:**`; the episodic and open-question tools have their own. A
write missing them fails with `VerificationError`. This is the structured
tools' content contract, not a preference — it is what makes the vault
queryable later. To write without a contract, use `write_note`, or run in
Basic mode.

---

## Quieter Professional

Keep the routing and required sections, stop the shaping:

```yaml
auto_link_on_save: false
placement_inference: false
strip_title_prefix: true      # keep — prevents "Decision - Decision - …"
create_missing_folders: false
```
