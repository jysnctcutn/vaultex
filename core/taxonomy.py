"""Loads taxonomy.json — the vault's folder-role mapping and any
user-defined custom categories. core/vault.py and core/tools/custom.py both
read from this module; nothing else should touch taxonomy.json directly.

No file at all (fresh clone, before `python3 onboard.py` has run) means a
fully taxonomy-free server: every role is None, custom_categories is empty.
That's deliberate — see the "Naming change"/onboarding decision notes for
why nothing here defaults to JC's own folder layout.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

from .config import TAXONOMY_JSON_PATH

TAXONOMY_PATH = TAXONOMY_JSON_PATH

# Every built-in role key this server understands. onboard.py walks this
# list; core/vault.py exposes one Path|None constant per entry.
ROLE_KEYS = [
    "builder_ideas",
    "builder_projects",
    "professional_decisions",
    "professional_tech_analysis",
    "professional_architecture",
    "professional_projects",
    "inbox",
    "episodic",
]


@dataclass
class CustomCategory:
    key: str
    folder: str
    label: str
    get_tool_name: str
    create_tool_name: str
    required_sections: list[str] = field(default_factory=list)
    prefix: str = ""


def _load() -> dict:
    if not TAXONOMY_PATH.exists():
        return {"roles": {}, "custom_categories": [], "project_subfolders": {}}
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return json.load(f)


_data = _load()

roles: dict[str, Path | None] = {
    key: (Path(value) if value else None) for key, value in {**dict.fromkeys(ROLE_KEYS), **_data.get("roles", {})}.items()
}

custom_categories: list[CustomCategory] = [
    CustomCategory(
        key=c["key"],
        folder=c["folder"],
        label=c["label"],
        get_tool_name=c.get("get_tool_name") or f"get_{c['key']}",
        create_tool_name=c.get("create_tool_name") or f"create_{c['key']}_note",
        required_sections=c.get("required_sections", []),
        prefix=c.get("prefix", ""),
    )
    for c in _data.get("custom_categories", [])
]

# Opt-in per Builder project: which subfolder names save_decision/
# update_feature will accept (and require) for that project_name. A
# project with no entry here keeps the flat project-root behavior every
# project has always had -- this is additive, not a default.
project_subfolders: dict[str, list[str]] = _data.get("project_subfolders", {})
