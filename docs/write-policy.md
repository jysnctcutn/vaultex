# Write policy and failure modes

In Professional mode the structured write tools shape notes on your behalf.
That is useful until it isn't — if you already have strong folder
conventions, it can feel like the tool is fighting you.

Four behaviors are switchable from a single note at your vault root,
**`write_policy.md`**.

## The four toggles

```yaml
---
auto_link_on_save: true      # append a "## Related notes" footer to new notes
placement_inference: true    # let save_brainstorm pick the folder
strip_title_prefix: true     # avoid "Decision - Decision - …"
create_missing_folders: true # create a write's target folder if absent
---
```

Edit the frontmatter and save — **the next write picks it up, no restart**.
The file ships as `write_policy.example.md`, and `setup/onboard.py` seeds a copy
into your vault on the Professional path. With no file at all, every toggle
defaults to `true`, which is exactly the pre-existing behavior. A malformed
file also falls back to the defaults rather than breaking writes.

| Toggle | `false` means |
|---|---|
| `auto_link_on_save` | Nothing is ever appended. Notes are written exactly as produced. |
| `placement_inference` | `save_brainstorm` never infers a folder, and **never raises `PlacementAmbiguous`** — turning inference off removes the failure mode too. Uses the explicit `area=` if given, otherwise the inbox. |
| `strip_title_prefix` | A leading prefix in the title is preserved verbatim instead of being stripped before the tool prepends its own. |
| `create_missing_folders` | A write to a folder that doesn't exist fails, naming it. Nothing is created. Notes only land in folders you made yourself. |

The example file's body documents each toggle in full, including what it
does *not* affect.

**Quieter Professional** — keep routing and required sections, stop the
shaping:

```yaml
auto_link_on_save: false
placement_inference: false
strip_title_prefix: true      # keep — prevents "Decision - Decision - …"
create_missing_folders: false
```

Want none of it? Use `write_note`, or [Basic mode](modes.md).

## Not configurable

**Path separators in titles** are always replaced. `create_app_idea("Auth/OAuth
notes")` writes `Auth-OAuth notes.md`, never an `Auth/` subfolder. Landing a
note in an unintended folder is a bug, not a preference.

**Required sections** stay required — they are what make the vault
queryable later. `write_note` and Basic mode are the ways out of the
contract.

## The policy file is a control surface

Vaultex refuses to write or move `write_policy.md` through any tool, and the
semantic indexer skips it, so it never turns up as a search hit. `read_note`
can still read it — an agent should be able to explain why a write behaved
the way it did.

## Who reads it

| | Reads `write_policy.md`? |
|---|---|
| Basic mode, anything | **Never** — zero-inference is hard-coded by the mode |
| Professional, structured tools | **Yes** — all four toggles |
| Professional, `write_note` | **Never** — being zero-inference is the point of it |

> `AUTO_LINK_ON_SAVE` in `.env` is the deprecated predecessor of
> `auto_link_on_save`. The two are ANDed, so an install already setting it
> `false` keeps that behavior; otherwise the policy file decides.

## Failure modes

These are normal, expected outcomes rather than bugs — worth recognising
when a tool returns one.

**`TaxonomyNotConfigured`** — a Professional-mode tool needs a
`taxonomy.json` role your vault hasn't mapped. Run `python3 setup/onboard.py`, or
switch to [Basic mode](modes.md), where no taxonomy is needed and these
tools aren't registered in the first place.

**`PlacementAmbiguous`** — `save_brainstorm` found several plausible folders
with no clear winner (under 80% agreement among the closest matches). An MCP
call can't ask you mid-run, so the candidates come back in the error message.
Retry with an explicit `area=`, or set `placement_inference: false`.

**`VerificationError`** — the content is missing a required section (e.g.
`save_decision` needs `**Decided:**` and `**What it means:**`). The message
names what to add.

**`WorkspaceNotConfigured`** — no workspace by that name. The message lists
the valid ones; `list_workspaces` shows them too. Deliberately an error
rather than a silent fallback, so a typo can't file notes into the wrong
project tree.

**`FileExistsError`** — the note already exists and `overwrite` wasn't set.

**`FileNotFoundError` naming a folder** — only when
`create_missing_folders: false`.

**`PermissionError`** — either the path is in `EXCLUDED_AREAS` for this
server instance, or it's `write_policy.md`, which no tool may modify.

**Auto-link silently did nothing** — expected when any of these hold: the
note already existed (footers are only added on creation), no embeddings
index has been built, nothing matched within the distance threshold, or the
toggle is off.
