"""Dynamically registers a get/create tool pair for every category in
taxonomy.json's custom_categories list — the way a first-time user adds a
role that doesn't correspond to any of the 6 built-in ones (e.g. their own
"Meeting Notes"), via `python3 onboard.py`.

Deliberately the simple pattern (list a folder, create a note in it) —
mirrors get_app_ideas/create_app_idea in builder.py, not the richer
professional/builder-split behavior the built-in roles have. Every
generated tool goes through the same iter_markdown/safe_path/write helpers
as the static tools, so EXCLUDED_AREAS and path-traversal protection apply
automatically.
"""

from pathlib import Path

from ..config import VAULT_PATH
from ..mcp_app import register_tool
from ..taxonomy import CustomCategory, custom_categories
from ..vault import iter_markdown, read, safe_path, slug, verify_sections, write


def _make_get_fn(category: CustomCategory):
    folder = Path(category.folder)

    def _get() -> list[dict]:
        out = []
        for p in iter_markdown(folder):
            text = read(p)
            out.append({"path": str(p.relative_to(VAULT_PATH)), "excerpt": text[:200].strip()})
        return out

    return _get


def _make_create_fn(category: CustomCategory):
    folder = Path(category.folder)

    def _create(title: str, content: str, overwrite: bool = False) -> str:
        if category.required_sections:
            verify_sections(content, category.required_sections)
        name = f"{category.prefix}{slug(title, category.prefix)}" if category.prefix else slug(title)
        path = safe_path(folder / f"{name}.md")
        return write(path, content, overwrite=overwrite)

    return _create


for _category in custom_categories:
    register_tool(
        _make_get_fn(_category),
        name=_category.get_tool_name,
        description=f"List {_category.label} notes under {_category.folder}.",
    )
    register_tool(
        _make_create_fn(_category),
        name=_category.create_tool_name,
        description=f"Create a new {_category.label} note under {_category.folder}.",
        write=True,
    )
