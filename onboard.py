"""
Vaultex — Onboarding Wizard

Picks the server's mode, then (in Professional mode) maps folder roles and
workspaces onto whatever your vault actually looks like.

Run:
    python3 onboard.py                # edit-in-place if taxonomy.json exists
    python3 onboard.py --reconfigure  # start fresh, ignoring any existing file

Every step is skippable — an unconfigured role just means the tools that
depend on it report "not configured" instead of working, not an error in
this script.
"""

import argparse
import json
import os
import re
import shutil
from pathlib import Path

from dotenv import load_dotenv

from core.workspaces import ReservedWorkspaceName, check_name_allowed as check_workspace_name

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TAXONOMY_PATH = Path(os.environ.get("TAXONOMY_JSON_PATH", str(BASE_DIR / "taxonomy.json")))
POLICY_TEMPLATE = BASE_DIR / "write_policy.example.md"
POLICY_FILENAME = "write_policy.md"

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

PARA_FOLDERS = ["Projects", "Areas", "Resources", "Archive"]

# Project roots come from workspaces, not roles, so builder_projects and
# professional_projects are deliberately absent -- a fresh vault never meets
# that vocabulary. Episodic sits under Resources rather than Archive: PARA's
# Archive means "inactive", which misdescribes an append-only agent log.
PARA_TAXONOMY = {
    "inbox": "0-Inbox",
    "ideas": "Resources/Ideas",
    "episodic": "Resources/Episodic",
    "decisions": "Areas/Decisions",
    "architecture": "Areas/Architecture",
    "tech_analysis": "Areas/Tech-Analysis",
    "open_questions": "Areas/Open-Questions",
}

# The author's own vault layout. Not a default -- core/taxonomy.py ships with
# every role unconfigured -- but offered as an opt-in starting point.
AUTHOR_TAXONOMY = {
    "ideas": "02-Builder/Ideas",
    "decisions": "01-Professional/Solution-Architecture/Decisions",
    "tech_analysis": "01-Professional/Solution-Architecture/Gap-Analysis",
    "architecture": "01-Professional/Solution-Architecture/Architecture",
    "inbox": "00-Inbox",
    "episodic": "02-Builder/Episodic",
    "open_questions": "02-Builder/Open-Questions",
}

# The two project roots this layout used to map to builder_projects /
# professional_projects. Emitted as workspaces so choosing this option can't
# write the retired keys into a brand-new taxonomy.json.
AUTHOR_WORKSPACES = {
    "default": "Projects",
    "entries": {
        "Projects": "02-Builder/Projects",
        "Work": "01-Professional/Solution-Architecture/Projects",
    },
}

MODE_EXPLAINER = """
--- Mode ---
Vaultex runs in one of two modes.

  1. Basic
       4 tools: search, grep, read_note, write_note.
       No taxonomy, no folder roles, no imposed structure. write_note takes
       an explicit path and does nothing clever with it -- no auto-naming,
       no auto-placement, no required sections, no link footers.
       Best if you already have your own folder conventions.

  2. Professional
       The full structured toolset: save_decision, save_brainstorm, the
       episodic session log, distillation, per-category get/create, and
       multi-agent coordination.
       Notes are routed, named, section-checked and cross-linked for you.
       Needs a folder layout, which the next step sets up.
       You can dial the automatic behavior down later in write_policy.md.
"""


def _vault_path() -> Path:
    raw = os.environ.get("VAULTEX_PATH")
    if not raw:
        raise SystemExit("VAULTEX_PATH isn't set in .env — set that up first (see docs/installation.md).")
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"VAULTEX_PATH does not exist: {path}")
    return path


def _upsert_env(key: str, value: str) -> None:
    """Replace-or-append one key in .env, preserving every other line.

    This rewrites a file holding MCP_AUTH_TOKEN and AUTHORIZE_PASSWORD, so it
    must never print, log, or diff what it reads -- only the one line it owns.
    """
    env_path = BASE_DIR / ".env"
    new_line = f"{key}={value}\n"
    if not env_path.exists():
        env_path.write_text(new_line, encoding="utf-8")
        return
    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.split("=", 1)[0].strip() == key:
            lines[i] = new_line
            break
    else:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(new_line)
    env_path.write_text("".join(lines), encoding="utf-8")


def _top_level_folders(vault: Path) -> list[str]:
    return sorted(p.name for p in vault.iterdir() if p.is_dir() and not p.name.startswith("."))


def _prompt_choice(folders: list[str], prompt: str) -> str | None:
    print(f"\n{prompt}")
    for i, f in enumerate(folders, 1):
        print(f"  {i}. {f}")
    print("  (or type a custom vault-relative path, or press enter to skip)")
    raw = input("> ").strip()
    if not raw:
        return None
    if raw.isdigit() and 1 <= int(raw) <= len(folders):
        return folders[int(raw) - 1]
    return raw


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
    for rel in relative_paths:
        target = vault / rel
        if not target.exists():
            target.mkdir(parents=True)
            print(f"  created {rel}/")


def _scaffold_para(vault: Path) -> None:
    for name in PARA_FOLDERS:
        p = vault / name
        if not p.exists():
            p.mkdir(parents=True)
            print(f"  created {name}/")
        else:
            print(f"  {name}/ already exists, skipped")


def _choose_mode(existing: dict) -> str:
    print(MODE_EXPLAINER)
    suggested = "2" if (existing.get("roles") or existing.get("custom_categories")) else "1"
    raw = input(f"Which mode? [1] Basic  [2] Professional (default: {suggested}) ").strip() or suggested
    return "professional" if raw == "2" else "basic"


def _prompt_workspaces(vault: Path) -> dict:
    """Workspaces are named project contexts. One is the common case -- being
    handed a split you didn't ask for is the same imposition the old
    professional/builder flag was."""
    print("\n--- Workspaces ---")
    print("A workspace is a named project context you can switch between, like")
    print("separate spaces for personal work, client work, and experiments.")
    print("Each becomes a folder under Projects/.")
    raw = input('\nName your workspaces, comma-separated (e.g. "Personal, Work, Sandbox"),\n'
                "or press enter for a single workspace: ").strip()
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
    target = vault / POLICY_FILENAME
    if target.exists():
        print(f"  {POLICY_FILENAME} already exists, left alone")
        return
    if not POLICY_TEMPLATE.exists():
        return
    shutil.copyfile(POLICY_TEMPLATE, target)
    print(f"  created {POLICY_FILENAME} (edit it any time; changes apply without a restart)")


def _configure_layout(vault: Path, data: dict, folders: list[str]) -> None:
    print("\n--- Professional layout ---")
    print("  1. PARA layout (recommended for a fresh vault)")
    for key, path in PARA_TAXONOMY.items():
        print(f"       {key}: {path}")
    print("       plus Projects/<Workspace>/ from the next step")
    print("  2. Map each role to folders you already have (guided)")
    print("  3. Use the author's layout (JC's own structure)")
    for key, path in AUTHOR_TAXONOMY.items():
        print(f"       {key}: {path}")
    print("  4. Skip for now — leave roles unconfigured")
    choice = input("> ").strip() or "1"

    if choice == "1":
        _scaffold_para(vault)
        data["roles"].update(PARA_TAXONOMY)
        _mkdirs(vault, PARA_TAXONOMY.values())
        data["workspaces"] = _prompt_workspaces(vault)
    elif choice == "3":
        data["roles"].update(AUTHOR_TAXONOMY)
        data.setdefault("workspaces", AUTHOR_WORKSPACES)
        _mkdirs(vault, [*AUTHOR_TAXONOMY.values(), *AUTHOR_WORKSPACES["entries"].values()])
        print("Applied the author's layout. Re-run this wizard any time to adjust roles.")
    elif choice == "4":
        print("Skipped — roles left as-is.")
    else:
        for key, description in ROLES:
            current = data["roles"].get(key)
            label = f" (currently: {current})" if current else ""
            selected = _prompt_choice(folders, f"{description}{label}")
            if selected is not None:
                data["roles"][key] = selected
            elif key not in data["roles"]:
                data["roles"].setdefault(key, None)
        # Project roots come from workspaces, not roles, so the guided path
        # needs this too or it ends with nowhere to file a project note.
        if not data.get("workspaces"):
            data["workspaces"] = _prompt_workspaces(vault)


def _configure_custom_categories(data: dict) -> None:
    print("\n--- Custom categories ---")
    print("Add a role beyond the built-in ones (e.g. \"Meeting Notes\"), with its own get/create tools.")
    while input("Add a custom category? (y/N) ").strip().lower() == "y":
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconfigure", action="store_true", help="Ignore any existing taxonomy.json and start fresh")
    args = parser.parse_args()

    vault = _vault_path()
    data = {"roles": {}, "custom_categories": []} if args.reconfigure else load_taxonomy()
    data.setdefault("roles", {})
    data.setdefault("custom_categories", [])

    print(f"Vault: {vault}")
    folders = _top_level_folders(vault)
    print(f"Existing top-level folders: {folders or '(none found)'}")

    mode = _choose_mode(data)
    _upsert_env("VAULTEX_MODE", mode)
    print(f"\nMode set to {mode} (written to .env).")

    if mode == "basic":
        # Deliberately leaves taxonomy.json untouched: trying Basic must not
        # destroy a Professional mapping you can switch back to.
        if input("\nScaffold the 4 PARA folders (Projects/Areas/Resources/Archive)? (y/N) ").strip().lower() == "y":
            _scaffold_para(vault)
        print("\nBasic mode is ready. Tools: search, grep, read_note, write_note.")
        print("Re-run this wizard any time to switch to Professional.")
        print("\nRestart the server (or `docker compose up -d --build`) to pick this up.")
        return

    if not args.reconfigure and (data["roles"] or data["custom_categories"]):
        print(f"\ntaxonomy.json already has {len(data['roles'])} role(s) and "
              f"{len(data['custom_categories'])} custom categor(y/ies) configured.")
        print("Continuing will let you edit/add to it. Pass --reconfigure to start over instead.")

    _configure_layout(vault, data, folders)

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
