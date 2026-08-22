"""Episodic memory tools (Phase 1): append-only session/event notes under
the `episodic` role, separate from a project's durable folder until a
future distillation step promotes them.
"""

import re
from datetime import datetime, timezone

from ..frontmatter import join, split
from ..mcp_app import write_tool
from ..vault import EPISODIC, read, require_role, safe_path, verify_sections, write

# Hard-validated on every episodic write; "## Outcome" is required in
# addition once a session closes.
REQUIRED_SECTIONS = [
    "## Goal",
    "## What happened",
    "## Decisions made (raw)",
    "## Open questions left",
    "## Artifacts / links",
]

_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


def _file_slug(text: str) -> str:
    """Dash-separated slug, distinct from vault.slug()'s case/space-
    preserving style -- matches the locked filename convention."""
    return _SLUG_RE.sub("-", text.strip()).strip("-").lower()[:60] or "untitled"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _episodic_path(kind: str, slug_source: str):
    root = require_role(EPISODIC, "episodic")
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    stamp = now.strftime("%Y-%m-%d-T%H%M")
    filename = f"{stamp}-{kind}-{_file_slug(slug_source)}.md"
    return safe_path(root / month / filename)


def _build_body(goal: str, what_happened: str, decisions: str, open_questions: str, artifacts: str) -> str:
    return (
        f"## Goal\n{goal}\n\n"
        f"## What happened\n{what_happened}\n\n"
        f"## Decisions made (raw)\n{decisions}\n\n"
        f"## Open questions left\n{open_questions}\n\n"
        f"## Artifacts / links\n{artifacts}\n"
    )


def _clean(fm: dict) -> dict:
    """Drop None values instead of serializing them as YAML `null`."""
    return {k: v for k, v in fm.items() if v is not None}


@write_tool
def log_event(project: str, kind: str, summary: str, details: str = "",
              agents: list[str] | None = None, tags: list[str] | None = None) -> str:
    """Append a one-shot episodic event or outcome note for `project`,
    without bracketing a full start_session/close_session run.

    kind: "event" or "outcome". summary is the main record; details is
    optional free text alongside it. Written under the configured
    `episodic` role, dated in UTC."""
    if kind not in ("event", "outcome"):
        raise ValueError(f"kind must be 'event' or 'outcome', got: {kind!r}")
    if not project:
        raise ValueError("project is required")
    now = _now()
    fm = _clean({
        "type": "episodic",
        "kind": kind,
        "project": project,
        "agents": agents or [],
        "status": "closed",
        "started": now,
        "ended": now,
        "tags": tags or [],
        "promoted": False,
    })
    body = _build_body("(none -- quick event)", summary, details or "(none)", "(none)", "(none)")
    verify_sections(body, REQUIRED_SECTIONS)
    path = _episodic_path(kind, summary)
    return write(path, join(fm, body), overwrite=False)


@write_tool
def start_session(project: str, goal: str, task_id: str | None = None,
                   agents: list[str] | None = None, tags: list[str] | None = None) -> str:
    """Open an episodic session note bracketing a multi-turn agent run.

    Returns the note's path; pass it to close_session when the run ends."""
    if not project:
        raise ValueError("project is required")
    fm = _clean({
        "type": "episodic",
        "kind": "session",
        "project": project,
        "task_id": task_id,
        "agents": agents or [],
        "status": "open",
        "started": _now(),
        "tags": tags or [],
        "promoted": False,
    })
    body = _build_body(goal, "(in progress)", "(in progress)", "(in progress)", "(in progress)")
    verify_sections(body, REQUIRED_SECTIONS)
    path = _episodic_path("session", goal)
    return write(path, join(fm, body), overwrite=False)


@write_tool
def close_session(session_path: str, outcome: str) -> str:
    """Close a session opened by start_session: sets status="closed",
    stamps `ended`, and appends the required ## Outcome section."""
    note_path = safe_path(session_path)
    if not note_path.is_file():
        raise FileNotFoundError(f"No such episodic note: {session_path}")
    fm, body = split(read(note_path))
    if fm.get("kind") != "session":
        raise ValueError(f"{session_path} is not a session note (kind={fm.get('kind')!r})")
    if fm.get("status") != "open":
        raise ValueError(f"{session_path} is not open (status={fm.get('status')!r})")
    fm["status"] = "closed"
    fm["ended"] = _now()
    new_body = f"{body.rstrip()}\n\n## Outcome\n{outcome}\n"
    verify_sections(new_body, [*REQUIRED_SECTIONS, "## Outcome"])
    return write(note_path, join(fm, new_body), overwrite=True)
