"""Project and feature context tools (Builder projects + Solution-Architecture projects)."""

from pathlib import Path

from ..config import VAULT_PATH
from ..mcp_app import mcp, write_tool
from ..vault import (
    BUILDER_PROJECTS,
    PROFESSIONAL_PROJECTS,
    check_area_allowed,
    iter_markdown,
    read,
    require_role,
    safe_path,
    write,
)


def project_root(project_name: str, professional: bool) -> Path:
    base = require_role(PROFESSIONAL_PROJECTS, "professional_projects") if professional \
        else require_role(BUILDER_PROJECTS, "builder_projects")
    return base / project_name


@mcp.tool()
def get_project_context(project_name: str, professional: bool = False) -> list[dict]:
    """Gather all notes for a project (Builder project by default, or a
    Solution-Architecture project when professional=True)."""
    root_rel = project_root(project_name, professional)
    check_area_allowed(root_rel)
    notes = []
    for p in iter_markdown(root_rel):
        notes.append({"path": str(p.relative_to(VAULT_PATH)), "content": read(p)})
    return notes


@mcp.tool()
def get_feature_context(project_name: str, feature_name: str, professional: bool = False) -> dict:
    """Read a specific feature note (`Feature - <feature_name>.md`) from a
    project, plus sibling Architecture.md and Decisions.md if present."""
    root_rel = project_root(project_name, professional)
    check_area_allowed(root_rel)
    feature_path = safe_path(root_rel / f"Feature - {feature_name}.md")
    result: dict = {}
    if feature_path.exists():
        result["feature"] = read(feature_path)
    else:
        result["feature"] = None
    for sibling in ("Architecture.md", "Decisions.md"):
        sp = safe_path(root_rel / sibling)
        if sp.exists():
            result[sibling] = read(sp)
    return result


@write_tool
def update_feature(project_name: str, feature_name: str, content: str,
                    professional: bool = False, overwrite: bool = True) -> str:
    """Create or update a project's feature note (`Feature - <feature_name>.md`)."""
    root_rel = project_root(project_name, professional)
    path = safe_path(root_rel / f"Feature - {feature_name}.md")
    return write(path, content, overwrite=overwrite)
