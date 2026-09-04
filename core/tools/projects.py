"""Project and feature context tools (Builder projects + Solution-Architecture projects)."""

from pathlib import Path

from ..mcp_app import mcp, write_tool
from ..taxonomy import project_subfolders
from ..vault import (
    check_area_allowed,
    iter_markdown,
    read,
    read_capped,
    resolve_project_subfolder,
    safe_path,
    validate_limit,
    write,
)
from ..workspaces import available as available_workspaces, default_name, resolve as resolve_workspace
from .episodic import recent_episodic_paths


def project_root(project_name: str, workspace: str | None = None) -> Path:
    """Project folder inside the named workspace, or the vault's default."""
    _, base = resolve_workspace(workspace)
    return base / project_name


@mcp.tool()
def list_workspaces() -> dict:
    """Workspaces configured for this vault: named project contexts you can
    pass as `workspace=` to the project and decision tools.

    Returns {"default": name, "workspaces": {name: folder}}. The default is
    used whenever `workspace` is omitted.
    """
    return {
        "default": default_name(),
        "workspaces": {name: str(folder) for name, folder in available_workspaces().items()},
    }


@mcp.tool()
def get_project_context(project_name: str, workspace: str | None = None, limit: int = 10,
                        include_episodic: bool = False, episodic_days: int = 7) -> list[dict]:
    """Gather notes for a project, most-recently modified first, capped at
    `limit` notes. Pass a bigger `limit` for older notes, or use read_note
    for a specific known path.

    workspace picks which project context to read; omit it for the vault's
    default (see list_workspaces).

    include_episodic=True also appends recent episodic notes for this project
    (see get_episodic_context), same {path, content} shape; episodic_days is
    their look-back window (<=0 for none). Requires the `episodic` role."""
    validate_limit(limit)
    root_rel = project_root(project_name, workspace)
    check_area_allowed(root_rel)
    notes = read_capped(iter_markdown(root_rel), limit=limit)
    if include_episodic:
        notes += read_capped(recent_episodic_paths(project_name, episodic_days), limit=limit)
    return notes


@mcp.tool()
def get_feature_context(project_name: str, feature_name: str,
                        workspace: str | None = None) -> dict:
    """Read a specific feature note (`Feature - <feature_name>.md`) from a
    project -- found regardless of which subfolder it's in -- plus sibling
    Architecture.md and Decisions.md at the project root if present.

    workspace picks which project context to read; omit it for the vault's
    default."""
    root_rel = project_root(project_name, workspace)
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
                    workspace: str | None = None, subfolder: str | None = None,
                    overwrite: bool = True) -> str:
    """Create or update a project's feature note (`Feature - <feature_name>.md`).

    workspace picks which project context to write into; omit it for the
    vault's default.

    subfolder: for a project with subfolders configured in taxonomy.json's
    project_subfolders, required and must be one of the configured values;
    omit for a project with none configured. Subfolders are keyed by project
    name, so they apply the same way in every workspace."""
    root_rel = project_root(project_name, workspace)
    resolved = resolve_project_subfolder(
        project_name, subfolder, project_subfolders.get(project_name)
    )
    path = safe_path(root_rel / resolved / f"Feature - {feature_name}.md")
    return write(path, content, overwrite=overwrite)
