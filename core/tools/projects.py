"""Project and feature context tools (Builder projects + Solution-Architecture projects)."""

from pathlib import Path

from ..mcp_app import mcp, write_tool
from ..taxonomy import project_subfolders
from ..vault import (
    BUILDER_PROJECTS,
    PROFESSIONAL_PROJECTS,
    check_area_allowed,
    iter_markdown,
    read,
    read_capped,
    require_role,
    resolve_project_subfolder,
    safe_path,
    validate_limit,
    write,
)


def project_root(project_name: str, professional: bool) -> Path:
    base = require_role(PROFESSIONAL_PROJECTS, "professional_projects") if professional \
        else require_role(BUILDER_PROJECTS, "builder_projects")
    return base / project_name


@mcp.tool()
def get_project_context(project_name: str, professional: bool = False, limit: int = 10) -> list[dict]:
    """Gather notes for a project (Builder project by default, or a
    Solution-Architecture project when professional=True), most-recently
    modified first, capped at `limit` notes. Pass a bigger `limit` for
    older notes, or use read_note for a specific known path."""
    validate_limit(limit)
    root_rel = project_root(project_name, professional)
    check_area_allowed(root_rel)
    return read_capped(iter_markdown(root_rel), limit=limit)


@mcp.tool()
def get_feature_context(project_name: str, feature_name: str, professional: bool = False) -> dict:
    """Read a specific feature note (`Feature - <feature_name>.md`) from a
    project -- found regardless of which subfolder it's in -- plus sibling
    Architecture.md and Decisions.md at the project root if present."""
    root_rel = project_root(project_name, professional)
    check_area_allowed(root_rel)
    target = f"Feature - {feature_name}.md"
    match = next((p for p in iter_markdown(root_rel) if p.name == target), None)
    result: dict = {"feature": read(match) if match else None}
    for sibling in ("Architecture.md", "Decisions.md"):
        sp = safe_path(root_rel / sibling)
        if sp.exists():
            result[sibling] = read(sp)
    return result


@write_tool
def update_feature(project_name: str, feature_name: str, content: str,
                    professional: bool = False, subfolder: str | None = None,
                    overwrite: bool = True) -> str:
    """Create or update a project's feature note (`Feature - <feature_name>.md`).

    subfolder: for a Builder project with subfolders configured in
    taxonomy.json's project_subfolders, required and must be one of the
    configured values; omit for a project with none configured, or when
    professional=True."""
    if professional and subfolder is not None:
        raise ValueError("`subfolder` only applies to Builder projects (professional=False)")
    root_rel = project_root(project_name, professional)
    resolved = "" if professional else resolve_project_subfolder(
        project_name, subfolder, project_subfolders.get(project_name)
    )
    path = safe_path(root_rel / resolved / f"Feature - {feature_name}.md")
    return write(path, content, overwrite=overwrite)
