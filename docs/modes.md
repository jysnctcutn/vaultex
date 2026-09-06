# Modes

Vaultex runs in one of two modes. `python3 onboard.py` asks which on its
first prompt and records the answer as `VAULTEX_MODE` in `.env`.

| | **Basic** | **Professional** |
|---|---|---|
| Tools registered | 4 | 31 |
| | `search`, `grep`, `read_note`, `write_note` | the above plus `save_decision`, `save_brainstorm`, episodic session log, distillation, coordination, per-category `get`/`create`, `list_workspaces` |
| Taxonomy | none | `taxonomy.json` (roles, workspaces, custom categories) |
| Folder layout | yours, untouched | PARA for a fresh vault, or mapped onto folders you already have |
| Writes | explicit path only | routed, named, section-checked, cross-linked |

**Basic** is the "point it at any Markdown folder" path. `write_note(path,
content)` takes the path literally: no placement inference, no auto-naming,
no required sections, no link footer. Nothing to configure, nothing to learn.

**Professional** is the structured surface. It needs a folder layout, and it
will shape notes on your behalf — which you can dial down in
[`write_policy.md`](write-policy.md) without leaving the mode.

## Mutually exclusive, not stacked

In Basic mode the structured tools are *not registered at all* — they never
appear in `tools/list`, so there is nothing to call and nothing to fail.
That is the whole point: a taxonomy-free vault is a supported
configuration, not an error state.

Mechanically, `core/tools/__init__.py` only imports the structured tool
modules in Professional mode. The `@mcp.tool()` decorators run at import
time, so *not importing a module is the exclusion* — there is no
soft-failing path and no second write surface competing with the first.

`READ_ONLY=true` still applies on top of either mode. Basic plus `READ_ONLY`
leaves three tools: `search`, `grep`, `read_note`.

## Choosing and switching

Re-run `python3 onboard.py` and pick the other mode, or set
`VAULTEX_MODE=basic|professional` in `.env` by hand. Restart the server to
pick it up.

Choosing Basic leaves any existing `taxonomy.json` untouched, so switching
back restores your Professional mapping exactly as it was.

If `VAULTEX_MODE` is unset the mode is **derived**: a configured
`taxonomy.json` (any role or custom category) means Professional, otherwise
Basic. Every existing install therefore keeps its current behavior with no
`.env` change.

Starting the server in Professional mode with no taxonomy configured logs a
warning — that combination registers every structured tool and then fails
each one at call time with `TaxonomyNotConfigured`, which is almost never
what you want. Either run `onboard.py` or switch to Basic.

## Workspaces

A workspace is a named project context — "Personal", "Work", "Sandbox" —
mapped to a folder in `taxonomy.json`:

```json
"workspaces": {
  "default": "Personal",
  "entries": {
    "Personal": "Projects/Personal",
    "Work":     "Projects/Work"
  }
}
```

Pass `workspace="Work"` to `get_project_context`, `get_feature_context`, or
`update_feature`; omit it and `default` is used. `list_workspaces` returns
what is configured.

Entries point at **arbitrary folders**, not a fixed `Projects/<name>/` root.
That is what makes adoption free for an existing vault — you attach names to
folders you already have instead of moving anything:

```json
"workspaces": {
  "default": "Builder",
  "entries": {
    "Builder":      "02-Builder/Projects",
    "Professional": "01-Professional/Solution-Architecture/Projects"
  }
}
```

Adding a third workspace is one more entry, pointing anywhere you like.

### Reload behavior

Workspaces are re-read per call, so one added to `taxonomy.json` works
immediately — **no restart**. Roles and custom categories are not: they are
read once at import because they drive which tools get registered, and
changing those needs a server restart.

A half-saved, unparseable `taxonomy.json` keeps serving the last known-good
workspaces rather than failing every write.

### The deprecated `professional` flag

`professional: bool` used to select between two hard-coded project roots.
It still works, as an alias:

```
workspace="Sandbox"   → that workspace
professional=True     → the workspace whose folder is professional_projects
professional=False    → the workspace whose folder is builder_projects
neither               → the configured default
both                  → error, never a guess
```

It resolves through the *role folder*, not a workspace name, so it keeps
working in a vault that has since renamed its contexts. A vault with no
`workspaces` block gets two derived workspaces, `Builder` and
`Professional`, from those same two roles — which is why no migration is
required.

`professional` also still appears on `save_decision` and
`get_architecture_decisions`, where it means something different — *is this
a standalone decision or a project decision* — and is not a workspace
selector. That naming is tracked for a later cut.
