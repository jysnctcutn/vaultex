"""Solution Architecture tools (professional area): decisions, gap analysis, full project context."""

from datetime import date

from ..frontmatter import join, split
from ..mcp_app import mcp, write_tool
from ..taxonomy import project_subfolders
from ..vault import (
    PROFESSIONAL_ARCHITECTURE,
    PROFESSIONAL_DECISIONS,
    PROFESSIONAL_TECH_ANALYSIS,
    check_area_allowed,
    iter_markdown,
    read_capped,
    require_role,
    resolve_project_subfolder,
    safe_path,
    slug,
    validate_limit,
    verify_sections,
    write,
)
from ..workspaces import resolve as resolve_workspace


@mcp.tool()
def get_architecture_decisions(project_name: str | None = None, professional: bool = True,
                                limit: int = 10) -> list[dict]:
    """List decision notes, most-recently modified first, capped at `limit`.

    With project_name, reads that project in the resolved workspace; without
    one, the professional-decisions folder. `professional` is the deprecated
    workspace selector — see list_workspaces."""
    validate_limit(limit)
    if project_name:
        _, base = resolve_workspace(professional=professional)
        root_rel = base / project_name
    else:
        if not professional:
            raise ValueError("project_name is required when professional=False")
        root_rel = require_role(PROFESSIONAL_DECISIONS, "professional_decisions")
    check_area_allowed(root_rel)
    paths = [p for p in iter_markdown(root_rel) if professional or "decision" in p.name.lower()]
    return read_capped(paths, limit=limit)


def _apply_provenance(content: str, source_episodic: str | None, agents: list[str] | None) -> str:
    """Stamp `source_episodic`/`agents`/`decided` into frontmatter. No-op
    when neither is given."""
    if not source_episodic and not agents:
        return content
    if source_episodic and not safe_path(source_episodic).is_file():
        raise ValueError(
            f"source_episodic points at a note that doesn't exist: {source_episodic!r}."
        )
    fm, body = split(content)
    fm.setdefault("type", "decision")
    if source_episodic:
        fm["source_episodic"] = source_episodic
    if agents:
        fm["agents"] = agents
    fm.setdefault("decided", date.today().isoformat())
    return join(fm, body)


@write_tool
def save_decision(title: str, content: str, professional: bool = False,
                   project_name: str | None = None, subfolder: str | None = None,
                   overwrite: bool = False, source_episodic: str | None = None,
                   agents: list[str] | None = None) -> str:
    """Save an architecture/product decision note.

    professional=True writes to the professional-decisions folder;
    professional=False into a project (project_name required), resolved
    through the default workspace. overwrite=True updates in place.

    subfolder: required, and must match one of taxonomy.json's
    project_subfolders, for a project that has any configured.

    source_episodic / agents stamp provenance frontmatter plus a `decided`
    date; omit both and the note is written as-is.

    Content must include `**Decided:**` and `**What it means:**`.
    """
    verify_sections(content, ["**Decided:**", "**What it means:**"])
    content = _apply_provenance(content, source_episodic, agents)
    if professional:
        if subfolder is not None:
            raise ValueError("`subfolder` only applies to project decisions (professional=False)")
        root = require_role(PROFESSIONAL_DECISIONS, "professional_decisions")
        path = safe_path(root / f"{slug(title)}.md")
    else:
        if not project_name:
            raise ValueError("project_name is required when professional=False")
        _, root = resolve_workspace(professional=False)
        resolved = resolve_project_subfolder(project_name, subfolder, project_subfolders.get(project_name))
        path = safe_path(root / project_name / resolved / f"Decision - {slug(title, 'Decision - ')}.md")
    return write(path, content, overwrite=overwrite)


@mcp.tool()
def get_tech_analysis_history(project_name: str | None = None, limit: int = 10) -> list[dict]:
    """List tech-analysis notes, most-recently modified first, capped at
    `limit`. project_name filters to filenames mentioning it."""
    validate_limit(limit)
    root = require_role(PROFESSIONAL_TECH_ANALYSIS, "professional_tech_analysis")
    check_area_allowed(root)
    needle = project_name.lower() if project_name else None
    paths = [p for p in iter_markdown(root) if not needle or needle in p.name.lower()]
    return read_capped(paths, limit=limit)


@mcp.tool()
def get_solution_architecture_context(project_name: str, limit: int = 10) -> dict:
    """A project's own notes plus any tech-analysis and architecture notes
    whose filename mentions it, each capped at `limit`."""
    validate_limit(limit)
    _, projects_root = resolve_workspace(professional=True)
    root_rel = projects_root / project_name
    check_area_allowed(root_rel)
    project_notes = read_capped(iter_markdown(root_rel), limit=limit)
    needle = project_name.lower()
    tech_analysis_root = require_role(PROFESSIONAL_TECH_ANALYSIS, "professional_tech_analysis")
    architecture_root = require_role(PROFESSIONAL_ARCHITECTURE, "professional_architecture")
    tech_analysis_notes = read_capped(
        [p for p in iter_markdown(tech_analysis_root) if needle in p.name.lower()], limit=limit
    )
    arch_notes = read_capped(
        [p for p in iter_markdown(architecture_root) if needle in p.name.lower()], limit=limit
    )
    return {"project": project_notes, "tech_analysis": tech_analysis_notes, "architecture": arch_notes}
