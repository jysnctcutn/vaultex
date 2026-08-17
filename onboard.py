"""
Vaultex — Taxonomy Onboarding Wizard

Interactive setup for taxonomy.json: maps the server's 7 built-in folder
roles (Ideas, Projects, Decisions, Tech Analysis, Architecture, Professional
Projects, Inbox) onto whatever your vault actually looks like, and lets you
define custom categories (e.g. your own "Meeting Notes") with their own
get/create tools.

Run:
    python3 onboard.py                # edit-in-place if taxonomy.json exists
    python3 onboard.py --reconfigure  # start fresh, ignoring any existing file

Every step is skippable — an unconfigured role just means the tools that
depend on it report "not configured" instead of working, not an error in
this script.
"""

import argparse
import json
import re
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

TAXONOMY_PATH = BASE_DIR / "taxonomy.json"

ROLES = [
    ("builder_ideas", "App/project ideas not yet a project"),
    ("builder_projects", "Personal/builder project work (decisions, features, brainstorms)"),
    ("professional_decisions", "Professional decisions not tied to a specific project"),
    ("professional_tech_analysis", "Technical/gap analysis notes"),
    ("professional_architecture", "Professional architecture notes"),
    ("professional_projects", "Professional/client project work"),
    ("inbox", "Default folder for captured brainstorms/conversation conclusions"),
]

PARA_FOLDERS = ["Projects", "Areas", "Resources", "Archive"]


def _vault_path() -> Path:
    import os

    raw = os.environ.get("VAULTEX_PATH")
    if not raw:
        raise SystemExit("VAULTEX_PATH isn't set in .env — set that up first (see README Quick start).")
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"VAULTEX_PATH does not exist: {path}")
    return path


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


def _load_existing() -> dict:
    if TAXONOMY_PATH.exists():
        with open(TAXONOMY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"roles": {}, "custom_categories": []}


def _write(data: dict) -> None:
    with open(TAXONOMY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def _slug_key(raw: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", raw.strip().lower()).strip("_")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reconfigure", action="store_true", help="Ignore any existing taxonomy.json and start fresh")
    args = parser.parse_args()

    vault = _vault_path()
    data = {"roles": {}, "custom_categories": []} if args.reconfigure else _load_existing()

    if not args.reconfigure and (data["roles"] or data["custom_categories"]):
        print(f"taxonomy.json already has {len(data['roles'])} role(s) and "
              f"{len(data['custom_categories'])} custom categor(y/ies) configured.")
        print("Continuing will let you edit/add to it. Pass --reconfigure to start over instead.\n")

    folders = _top_level_folders(vault)
    print(f"Vault: {vault}")
    print(f"Existing top-level folders: {folders or '(none found)'}")

    if input("\nScaffold the 4 PARA folders (Projects/Areas/Resources/Archive) for any that "
             "don't already exist? (y/N) ").strip().lower() == "y":
        for name in PARA_FOLDERS:
            p = vault / name
            if not p.exists():
                p.mkdir(parents=True)
                print(f"  created {name}/")
            else:
                print(f"  {name}/ already exists, skipped")
        folders = _top_level_folders(vault)

    print("\n--- Built-in roles ---")
    for key, description in ROLES:
        current = data["roles"].get(key)
        label = f" (currently: {current})" if current else ""
        choice = _prompt_choice(folders, f"{description}{label}")
        if choice is not None:
            data["roles"][key] = choice
        elif key not in data["roles"]:
            data["roles"].setdefault(key, None)

    # Drop explicit nulls so the file matches core/taxonomy.py's "missing key = unconfigured" contract.
    data["roles"] = {k: v for k, v in data["roles"].items() if v}

    print("\n--- Custom categories ---")
    print("Add a role beyond the 7 built-in ones (e.g. \"Meeting Notes\"), with its own get/create tools.")
    while input("Add a custom category? (y/N) ").strip().lower() == "y":
        raw_key = input("  Short key (e.g. 'meeting_notes'): ").strip()
        key = _slug_key(raw_key)
        folder = input("  Vault-relative folder (e.g. 'Meetings'): ").strip()
        label = input("  Human label (e.g. 'Meeting Note'): ").strip() or key.replace("_", " ").title()
        get_tool_name = input(f"  Tool name for listing [get_{key}]: ").strip() or f"get_{key}"
        create_tool_name = input(f"  Tool name for creating [create_{key}_note]: ").strip() or f"create_{key}_note"
        sections_raw = input("  Required sections, comma-separated (optional, e.g. **Decided:**,**What it means:**): ").strip()
        required_sections = [s.strip() for s in sections_raw.split(",") if s.strip()]
        prefix = input("  Filename prefix (optional, e.g. 'Meeting - '): ").strip()

        data["custom_categories"] = [c for c in data["custom_categories"] if c["key"] != key]
        data["custom_categories"].append({
            "key": key,
            "folder": folder,
            "label": label,
            "get_tool_name": get_tool_name,
            "create_tool_name": create_tool_name,
            "required_sections": required_sections,
            "prefix": prefix,
        })
        print(f"  Added: {get_tool_name}() / {create_tool_name}(title, content) -> {folder}/")

    _write(data)

    print(f"\nWrote {TAXONOMY_PATH}")
    configured = [k for k, _ in ROLES if k in data["roles"]]
    skipped = [k for k, _ in ROLES if k not in data["roles"]]
    print(f"Configured roles: {configured or '(none)'}")
    if skipped:
        print(f"Skipped roles (their tools will report 'not configured' until you re-run this): {skipped}")
    if data["custom_categories"]:
        print(f"Custom categories: {[c['key'] for c in data['custom_categories']]}")
    print("\nRestart the server (or `docker compose up -d --build`) to pick this up.")


if __name__ == "__main__":
    main()
