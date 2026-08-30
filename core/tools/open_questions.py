"""Open-question tools (Phase 2): promote an unknown raised during an agent
run into a durable per-project store -- distinct from the raw episodic trail
and from decisions (which record answers, not open questions).
"""

from datetime import date

from ..frontmatter import join, split
from ..mcp_app import mcp, write_tool
from ..vault import (
    OPEN_QUESTIONS,
    iter_markdown,
    read,
    read_capped,
    require_role,
    safe_path,
    slug,
    validate_limit,
    verify_sections,
    write,
)

REQUIRED_SECTIONS = ["## Question", "## Context", "## Resolution"]

_STATUSES = ("open", "answered", "deferred")


@write_tool
def save_open_question(project: str, question: str, context: str = "",
                        source_episodic: str | None = None, owner: str = "human",
                        status: str = "open") -> str:
    """Record an open question for `project` in the durable Open-Questions store.

    question also becomes the filename. source_episodic links the session it
    was raised in (must resolve to a real note). owner is who chases it (e.g.
    "ba"/"dev"/"human"). status: open / answered / deferred."""
    if not project:
        raise ValueError("project is required")
    if not question:
        raise ValueError("question is required")
    if status not in _STATUSES:
        raise ValueError(f"status must be one of {', '.join(_STATUSES)}, got: {status!r}")
    if source_episodic and not safe_path(source_episodic).is_file():
        raise ValueError(
            f"source_episodic points at a note that doesn't exist: {source_episodic!r}."
        )
    root = require_role(OPEN_QUESTIONS, "open_questions")
    fm = {
        "type": "open-question",
        "project": project,
        "status": status,
        "raised": date.today().isoformat(),
        "owner": owner,
    }
    if source_episodic:
        fm["source_episodic"] = source_episodic
    body = (
        f"## Question\n{question}\n\n"
        f"## Context\n{context or '(none)'}\n\n"
        f"## Resolution\n{'(unresolved)' if status == 'open' else ''}\n"
    )
    verify_sections(body, REQUIRED_SECTIONS)
    path = safe_path(root / project / f"Open Question - {slug(question, 'Open Question - ')}.md")
    return write(path, join(fm, body), overwrite=False)


@mcp.tool()
def get_open_questions(project: str, status: str | None = None, limit: int = 20) -> list[dict]:
    """List `project`'s open-question notes as {path, content} dicts, newest
    first. status: open / answered / deferred; omit for all."""
    validate_limit(limit)
    if status is not None and status not in _STATUSES:
        raise ValueError(f"status must be one of {', '.join(_STATUSES)}, got: {status!r}")
    root = require_role(OPEN_QUESTIONS, "open_questions")
    paths = []
    for path in iter_markdown(root / project):
        if status is None:
            paths.append(path)
            continue
        fm, _ = split(read(path))
        if fm.get("status") == status:
            paths.append(path)
    return read_capped(paths, limit=limit)
