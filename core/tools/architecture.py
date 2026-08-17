"""Solution Architecture tools (professional area): decisions, gap analysis, full project context."""

from ..config import VAULT_PATH
from ..mcp_app import mcp, write_tool
from ..vault import (
    BUILDER_PROJECTS,
    PROFESSIONAL_ARCHITECTURE,
    PROFESSIONAL_DECISIONS,
    PROFESSIONAL_PROJECTS,
    PROFESSIONAL_TECH_ANALYSIS,
    check_area_allowed,
    iter_markdown,
    read,
    require_role,
    safe_path,
    slug,
    verify_sections,
    write,
)


@mcp.tool()
def get_architecture_decisions(project_name: str | None = None, professional: bool = True) -> list[dict]:
    """List architecture decision notes. professional=True (default) reads
    the configured professional-decisions folder; professional=False reads
    the equivalent Decisions.md inside a Builder project instead."""
    if professional:
        root_rel = require_role(PROFESSIONAL_DECISIONS, "professional_decisions") if not project_name \
            else require_role(PROFESSIONAL_PROJECTS, "professional_projects") / project_name
    else:
        if not project_name:
            raise ValueError("project_name is required when professional=False")
        root_rel = require_role(BUILDER_PROJECTS, "builder_projects") / project_name
    check_area_allowed(root_rel)
    out = []
    for p in iter_markdown(root_rel):
        if professional or "decision" in p.name.lower():
            out.append({"path": str(p.relative_to(VAULT_PATH)), "content": read(p)})
    return out


@write_tool
def save_decision(title: str, content: str, professional: bool = False,
                   project_name: str | None = None, overwrite: bool = False) -> str:
    """Save an architecture/product decision note.

    professional=True writes to the configured professional-decisions folder.
    professional=False writes into a Builder project's folder (project_name required).
    Pass overwrite=True to update an existing note in place instead of erroring.

    Content must include a `**Decided:**` and a `**What it means:**` section —
    if either is missing, the note is rejected with a message naming what to add.
    """
    verify_sections(content, ["**Decided:**", "**What it means:**"])
    if professional:
        root = require_role(PROFESSIONAL_DECISIONS, "professional_decisions")
        path = safe_path(root / f"{slug(title)}.md")
    else:
        if not project_name:
            raise ValueError("project_name is required when professional=False")
        root = require_role(BUILDER_PROJECTS, "builder_projects")
        path = safe_path(root / project_name / f"Decision - {slug(title)}.md")
    return write(path, content, overwrite=overwrite)


@mcp.tool()
def get_tech_analysis_history(project_name: str | None = None) -> list[dict]:
    """List tech-analysis notes from the configured professional-tech-analysis
    folder, optionally filtered to those whose filename mentions project_name."""
    root = require_role(PROFESSIONAL_TECH_ANALYSIS, "professional_tech_analysis")
    check_area_allowed(root)
    out = []
    needle = project_name.lower() if project_name else None
    for p in iter_markdown(root):
        if needle and needle not in p.name.lower():
            continue
        out.append({"path": str(p.relative_to(VAULT_PATH)), "content": read(p)})
    return out


@mcp.tool()
def get_solution_architecture_context(project_name: str) -> dict:
    """Gather everything relevant to a Solution Architecture project: the
    project's own notes plus any matching tech-analysis and architecture notes."""
    projects_root = require_role(PROFESSIONAL_PROJECTS, "professional_projects")
    root_rel = projects_root / project_name
    check_area_allowed(root_rel)
    project_notes = [{"path": str(p.relative_to(VAULT_PATH)), "content": read(p)}
                      for p in iter_markdown(root_rel)]
    needle = project_name.lower()
    tech_analysis_root = require_role(PROFESSIONAL_TECH_ANALYSIS, "professional_tech_analysis")
    architecture_root = require_role(PROFESSIONAL_ARCHITECTURE, "professional_architecture")
    tech_analysis_notes = [{"path": str(p.relative_to(VAULT_PATH)), "content": read(p)}
                            for p in iter_markdown(tech_analysis_root) if needle in p.name.lower()]
    arch_notes = [{"path": str(p.relative_to(VAULT_PATH)), "content": read(p)}
                  for p in iter_markdown(architecture_root) if needle in p.name.lower()]
    return {"project": project_notes, "tech_analysis": tech_analysis_notes, "architecture": arch_notes}
