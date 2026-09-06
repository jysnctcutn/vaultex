"""
Vaultex — Onboarding Wizard

The taxonomy specialist: maps folder roles and workspaces onto whatever your
vault actually looks like. It does not choose the server's mode, run Docker,
or start the server.

Mode moved to install.py deliberately. Mode changes the registered toolset
(31 tools vs 4), which is a top-level product concept; owning it here as well
as there was a split brain, and this script is reached both from the
installer and standalone. With no VAULTEX_MODE set, core/mode.py still
derives the mode from whether taxonomy.json has anything configured, so a
vault that never meets install.py behaves sensibly anyway.

Run:
    python3 setup/onboard.py                  # edit-in-place if taxonomy.json exists
    python3 onboard.py --reconfigure    # start fresh, ignoring any existing file
    python3 onboard.py --advanced       # also offer the author's layout
    python3 onboard.py --add-workspace  # name one more workspace, nothing else

Every step is skippable — an unconfigured role just means the tools that
depend on it report "not configured" instead of working, not an error in
this script.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# This file lives in setup/, so core/ is one level up and isn't on sys.path
# when the script is run directly (`python3 setup/onboard.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv  # noqa: E402

import install_ui as ui  # noqa: E402
from core.presets import (  # noqa: E402
    AUTHOR_TAXONOMY,
    AUTHOR_WORKSPACES,
    PARA_FOLDERS,
    PARA_TAXONOMY,
    POLICY_FILENAME,
    POLICY_TEMPLATE_NAME,
    PRESET_AUTHOR,
    PRESET_MAPPED,
    PRESET_SIMPLE,
    ReservedWorkspaceName,
    SIMPLE_LABEL,
    check_name_allowed as check_workspace_name,
    mkdirs,
    seed_write_policy,
)
from install_ui import Option  # noqa: E402

# The repo root, not setup/ -- .env, taxonomy.json and
# write_policy.example.md all live there.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

TAXONOMY_PATH = Path(os.environ.get("TAXONOMY_JSON_PATH", str(BASE_DIR / "taxonomy.json")))
POLICY_TEMPLATE = BASE_DIR / POLICY_TEMPLATE_NAME

# Project roots are not here: they come from workspaces (see
# _prompt_workspaces), which is why the legacy builder_projects /
# professional_projects keys are never offered to a new user.
ROLES = [
    ("ideas", "Ideas not yet a project"),
    ("decisions", "Decisions not tied to a specific project"),
    ("tech_analysis", "Technical / gap-analysis notes"),
    ("architecture", "Architecture notes"),
    ("inbox", "Default folder for captured brainstorms/conversation conclusions"),
    ("episodic", "Append-only agent session/event log (log_event, start_session, close_session)"),
    ("open_questions", "Durable per-project open questions promoted from agent runs (save_open_question)"),
]


def _vault_path() -> Path:
    raw = os.environ.get("VAULTEX_PATH")
    if not raw:
        raise SystemExit("VAULTEX_PATH isn't set in .env — set that up first (see docs/installation.md).")
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"VAULTEX_PATH does not exist: {path}")
    return path


def _top_level_folders(vault: Path) -> list[str]:
    return sorted(p.name for p in vault.iterdir() if p.is_dir() and not p.name.startswith("."))


_TYPE_PATH = "\x00type"
_SKIP = "\x00skip"


def _prompt_choice(
    folders: list[str], title: str, step: str = "Role", footer: str = ""
) -> str | None:
    """Pick a folder for one role. The vault's own folders are the options;
    typing a path and skipping are the last two, so neither needs a separate
    "or..." line the way the old bare prompt did.

    `title` is the role key, not its description -- the descriptions run past
    the frame width, and the title bar is the one place text can't wrap.
    """
    options = [Option(f, f) for f in folders]
    options.append(Option(_TYPE_PATH, "Type a vault-relative path"))
    options.append(Option(_SKIP, "Skip this one", ["Its tools report 'not configured' until you map it."]))

    choice = ui.select(title, step, options, default=len(options) - 1, footer=footer)
    if choice == _SKIP:
        return None
    if choice == _TYPE_PATH:
        return ui.ask_text("  Vault-relative path").strip() or None
    return choice


def load_taxonomy() -> dict:
    if TAXONOMY_PATH.exists():
        with open(TAXONOMY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"roles": {}, "custom_categories": []}


def write_taxonomy(data: dict) -> None:
    with open(TAXONOMY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _slug_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")


def _mkdirs(vault: Path, relative_paths) -> None:
    for rel in mkdirs(vault, relative_paths):
        print(f"  created {rel}/")


def _scaffold_para(vault: Path) -> None:
    created = mkdirs(vault, PARA_FOLDERS)
    for name in PARA_FOLDERS:
        print(f"  created {name}/" if name in created else f"  {name}/ already exists, skipped")


def _prompt_workspaces(vault: Path) -> dict:
    """Workspaces are named project contexts. One is the common case -- being
    handed a split you didn't ask for is the same imposition the old
    professional/builder flag was."""
    print("\n--- Workspaces ---")
    print("A workspace is a named project context you can switch between, like")
    print("separate spaces for personal work, client work, and experiments.")
    print("Each becomes a folder under Projects/.")
    raw = ui.ask_text('\nName your workspaces, comma-separated (e.g. "Personal, Work, '
                      'Sandbox"),\nor press enter for a single workspace')
    names = []
    for n in (n.strip() for n in raw.split(",")):
        if not n:
            continue
        try:
            names.append(check_workspace_name(n))
        except ReservedWorkspaceName as e:
            print(f"  skipped: {e}")
    # One unnamed workspace lives at Projects/ itself: no extra path layer for
    # someone who never asked for the distinction.
    entries = {name: f"Projects/{name}" for name in names} or {"Projects": "Projects"}
    _mkdirs(vault, entries.values())
    return {"default": next(iter(entries)), "entries": entries}


def _seed_write_policy(vault: Path) -> None:
    if seed_write_policy(vault, POLICY_TEMPLATE):
        print(f"  created {POLICY_FILENAME} (edit it any time; changes apply without a restart)")
    else:
        print(f"  {POLICY_FILENAME} already exists, left alone")


def _configure_layout(vault: Path, data: dict, folders: list[str], advanced: bool) -> str:
    """Returns the preset key applied, for taxonomy.json's `preset` field."""
    # The author's layout scaffolds a specific 01-Professional/02-Builder
    # tree. That is the wrong default to dangle in front of someone who
    # already has folders, so install.py hides it there and points here.
    show_author = advanced or not folders

    options = [
        Option(PRESET_SIMPLE, SIMPLE_LABEL, [
            ", ".join(f"{k}: {v}" for k, v in list(PARA_TAXONOMY.items())[:3]) + ", ...",
            "plus Projects/<Workspace>/ from the next step.",
        ], recommended=not folders),
        Option(PRESET_MAPPED, "Map each role to folders you already have", [
            "Guided. Walks the built-in roles one at a time; nothing is moved "
            "or renamed.",
        ], recommended=bool(folders)),
    ]
    if show_author:
        options.append(Option(PRESET_AUTHOR, "Use the author's layout", [
            "JC's own structure: " + ", ".join(list(AUTHOR_TAXONOMY.values())[:3]) + ", ...",
        ]))
    options.append(Option("skip", "Skip for now", ["Leaves roles unconfigured."]))

    footer = "" if show_author else (
        "The author's layout is hidden because your vault already has folders "
        "— re-run with --advanced to see it."
    )
    choice = ui.select("Layout", "Taxonomy", options,
                       default=1 if folders else 0, footer=footer)
    ui.step_done("Layout", choice)

    if choice == PRESET_SIMPLE:
        _scaffold_para(vault)
        data["roles"].update(PARA_TAXONOMY)
        _mkdirs(vault, PARA_TAXONOMY.values())
        data["workspaces"] = _prompt_workspaces(vault)
        return PRESET_SIMPLE
    if choice == PRESET_AUTHOR:
        data["roles"].update(AUTHOR_TAXONOMY)
        data.setdefault("workspaces", AUTHOR_WORKSPACES)
        _mkdirs(vault, [*AUTHOR_TAXONOMY.values(), *AUTHOR_WORKSPACES["entries"].values()])
        print("Applied the author's layout. Re-run this wizard any time to adjust roles.")
        return PRESET_AUTHOR
    if choice == "skip":
        print("Skipped — roles left as-is.")
        return data.get("preset", PRESET_MAPPED)

    for i, (key, description) in enumerate(ROLES, 1):
        current = data["roles"].get(key)
        footer = description + (f"  (currently mapped to {current})" if current else "")
        selected = _prompt_choice(folders, key, f"Role {i} of {len(ROLES)}", footer)
        if selected is not None:
            data["roles"][key] = selected
            ui.step_done(key, selected)
        elif key not in data["roles"]:
            data["roles"].setdefault(key, None)
    # Project roots come from workspaces, not roles, so the guided path
    # needs this too or it ends with nowhere to file a project note.
    if not data.get("workspaces"):
        data["workspaces"] = _prompt_workspaces(vault)
    return PRESET_MAPPED


def _configure_custom_categories(data: dict) -> None:
    print("\n--- Custom categories ---")
    print("Add a role beyond the built-in ones (e.g. \"Meeting Notes\"), with its own get/create tools.")
    while ui.ask_yes_no("Add a custom category?", default=False):
        key = _slug_key(input("  Short key (e.g. 'meeting_notes'): ").strip())
        folder = input("  Vault-relative folder (e.g. 'Meetings'): ").strip()
        label = input("  Human label (e.g. 'Meeting Note'): ").strip() or key.replace("_", " ").title()
        get_tool_name = input(f"  Tool name for listing [get_{key}]: ").strip() or f"get_{key}"
        create_tool_name = input(f"  Tool name for creating [create_{key}_note]: ").strip() or f"create_{key}_note"
        sections_raw = input("  Required sections, comma-separated (optional, e.g. **Decided:**,**What it means:**): ").strip()
        prefix = input("  Filename prefix (optional, e.g. 'Meeting - '): ").strip()

        data["custom_categories"] = [c for c in data["custom_categories"] if c["key"] != key]
        data["custom_categories"].append({
            "key": key,
            "folder": folder,
            "label": label,
            "get_tool_name": get_tool_name,
            "create_tool_name": create_tool_name,
            "required_sections": [s.strip() for s in sections_raw.split(",") if s.strip()],
            "prefix": prefix,
        })
        print(f"  Added: {get_tool_name}() / {create_tool_name}(title, content) -> {folder}/")


def add_workspace(vault: Path) -> None:
    """Single-purpose: name one more workspace and point it at a folder. No
    full wizard, and no restart -- core/workspaces.py re-reads taxonomy.json
    per call, so a new workspace is live as soon as this writes."""
    data = load_taxonomy()
    block = data.get("workspaces") or {"default": None, "entries": {}}
    entries = dict(block.get("entries") or {})
    if entries:
        print(f"Existing workspaces: {', '.join(entries)}")

    while True:
        name = input("Name for the new workspace: ").strip()
        if not name:
            raise SystemExit("No name entered — nothing changed.")
        try:
            name = check_workspace_name(name)
        except ReservedWorkspaceName as e:
            print(f"  {e}")
            continue
        if name in entries:
            print(f"  {name!r} already exists — pick another name.")
            continue
        break

    default_folder = f"Projects/{name}"
    folder = input(f"Vault-relative folder [{default_folder}]: ").strip() or default_folder
    entries[name] = folder
    data["workspaces"] = {"default": block.get("default") or name, "entries": entries}
    _mkdirs(vault, [folder])
    write_taxonomy(data)
    print(f"\nAdded workspace {name!r} -> {folder}/ (no restart needed).")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconfigure", action="store_true", help="Ignore any existing taxonomy.json and start fresh")
    parser.add_argument("--advanced", action="store_true", help="Also offer the author's layout on a populated vault")
    parser.add_argument("--add-workspace", action="store_true", help="Name one more workspace and exit")
    args = parser.parse_args()

    vault = _vault_path()
    if args.add_workspace:
        add_workspace(vault)
        return

    data = {"roles": {}, "custom_categories": []} if args.reconfigure else load_taxonomy()
    data.setdefault("roles", {})
    data.setdefault("custom_categories", [])

    print(f"Vault: {vault}")
    folders = _top_level_folders(vault)
    print(f"Existing top-level folders: {folders or '(none found)'}")

    if not args.reconfigure and (data["roles"] or data["custom_categories"]):
        print(f"\ntaxonomy.json already has {len(data['roles'])} role(s) and "
              f"{len(data['custom_categories'])} custom categor(y/ies) configured.")
        print("Continuing will let you edit/add to it. Pass --reconfigure to start over instead.")

    data["preset"] = _configure_layout(vault, data, folders, args.advanced)

    # Drop explicit nulls so the file matches core/taxonomy.py's
    # "missing key = unconfigured" contract.
    data["roles"] = {k: v for k, v in data["roles"].items() if v}

    _configure_custom_categories(data)
    write_taxonomy(data)

    print(f"\nWrote {TAXONOMY_PATH}")
    _seed_write_policy(vault)

    configured = [k for k, _ in ROLES if k in data["roles"]]
    skipped = [k for k, _ in ROLES if k not in data["roles"]]
    print(f"Configured roles: {configured or '(none)'}")
    if skipped:
        print(f"Skipped roles (their tools report 'not configured' until you re-run this): {skipped}")
    if data.get("workspaces"):
        print(f"Workspaces: {list(data['workspaces']['entries'])} (default: {data['workspaces']['default']})")
    if data["custom_categories"]:
        print(f"Custom categories: {[c['key'] for c in data['custom_categories']]}")
    print("\nRestart the server (or `docker compose up -d --build`) to pick this up.")


if __name__ == "__main__":
    main()
