"""Episodic memory tools: append-only session/event notes under the
`episodic` role, kept out of a project's durable folder until distillation.

Phase 1: log_event, start_session, close_session.
Phase 2: update_session, get_episodic_context, and recent_episodic_paths()
(shared with get_project_context's include_episodic flag).
"""

import re
from datetime import datetime, timedelta, timezone

from ..frontmatter import join, split
from ..mcp_app import mcp, write_tool
from ..vault import (
    EPISODIC,
    iter_markdown,
    read,
    read_capped,
    require_role,
    safe_path,
    validate_limit,
    verify_sections,
    write,
)

# Hard-validated on every episodic write; "## Outcome" is required in
# addition once a session closes.
REQUIRED_SECTIONS = [
    "## Goal",
    "## What happened",
    "## Decisions made (raw)",
    "## Open questions left",
    "## Artifacts / links",
]

# Sections update_session can rewrite; "## Goal"/"## Outcome" are not editable here.
_UPDATABLE_SECTIONS = {
    "what_happened": "## What happened",
    "decisions": "## Decisions made (raw)",
    "open_questions": "## Open questions left",
    "artifacts": "## Artifacts / links",
}

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


def _replace_section(body: str, heading: str, new_text: str) -> str:
    """Swap the content under `heading` (to the next `## ` or EOF) for `new_text`."""
    pattern = re.compile(
        rf"(^{re.escape(heading)}[ \t]*\n)(.*?)(?=^## |\Z)",
        re.DOTALL | re.MULTILINE,
    )
    if not pattern.search(body):
        raise ValueError(f"Session note is missing the {heading!r} section; cannot update it.")
    return pattern.sub(lambda m: f"{m.group(1)}{new_text.rstrip()}\n\n", body, count=1).rstrip() + "\n"


def _parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def recent_episodic_paths(project: str, days: int) -> list:
    """Episodic-note paths for `project`, newest first. `days <= 0` = no time
    filter; else keep notes whose `ended`/`started`/mtime is within the window.
    Raises TaxonomyNotConfigured if the `episodic` role isn't set."""
    root = require_role(EPISODIC, "episodic")
    cutoff = None if days <= 0 else datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
    matches = []
    for path in iter_markdown(root):
        fm, _ = split(read(path))
        if fm.get("project") != project:
            continue
        if cutoff is not None:
            stamp = _parse_ts(fm.get("ended")) or _parse_ts(fm.get("started"))
            if stamp is None:
                stamp = datetime.utcfromtimestamp(path.stat().st_mtime)
            if stamp < cutoff:
                continue
        matches.append(path)
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)


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

    Returns the note's path; fill it in with update_session, then
    close_session when the run ends."""
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
def update_session(session_path: str, what_happened: str | None = None,
                    decisions: str | None = None, open_questions: str | None = None,
                    artifacts: str | None = None) -> str:
    """Rewrite one or more body sections of an OPEN session note in place,
    so detail lands before close_session instead of leaving "(in progress)".

    Only the sections you pass are touched ("## Goal"/"## Outcome" aren't
    editable here). Each call replaces a section wholesale -- pass the full
    current text, not a delta."""
    updates = {k: v for k, v in {
        "what_happened": what_happened, "decisions": decisions,
        "open_questions": open_questions, "artifacts": artifacts,
    }.items() if v is not None}
    if not updates:
        raise ValueError("Pass at least one of: what_happened, decisions, open_questions, artifacts.")
    note_path = safe_path(session_path)
    if not note_path.is_file():
        raise FileNotFoundError(f"No such episodic note: {session_path}")
    fm, body = split(read(note_path))
    if fm.get("kind") != "session":
        raise ValueError(f"{session_path} is not a session note (kind={fm.get('kind')!r})")
    if fm.get("status") != "open":
        raise ValueError(f"{session_path} is not open (status={fm.get('status')!r}); reopen is not supported.")
    for key, text in updates.items():
        body = _replace_section(body, _UPDATABLE_SECTIONS[key], text)
    verify_sections(body, REQUIRED_SECTIONS)
    return write(note_path, join(fm, body), overwrite=True)


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


@mcp.tool()
def get_episodic_context(project: str, days: int = 7, limit: int = 20,
                          kind: str | None = None, status: str | None = None,
                          promoted: bool | None = None) -> list[dict]:
    """Recent episodic notes for `project` as {path, content} dicts, newest
    first -- the time-scoped counterpart to get_project_context.

    days: look-back window (<=0 for none). kind: "session"/"event"/"outcome".
    status: "open"/"closed". promoted: True/False to filter by whether
    distillation has already promoted the note (e.g. promoted=False,
    status="closed" finds sessions still waiting to be distilled)."""
    validate_limit(limit)
    if kind is not None and kind not in ("session", "event", "outcome"):
        raise ValueError(f"kind must be 'session', 'event', or 'outcome', got: {kind!r}")
    if status is not None and status not in ("open", "closed"):
        raise ValueError(f"status must be 'open' or 'closed', got: {status!r}")
    paths = recent_episodic_paths(project, days)
    if kind is not None or status is not None or promoted is not None:
        kept = []
        for path in paths:
            fm, _ = split(read(path))
            if kind is not None and fm.get("kind") != kind:
                continue
            if status is not None and fm.get("status") != status:
                continue
            if promoted is not None and bool(fm.get("promoted", False)) != promoted:
                continue
            kept.append(path)
        paths = kept
    return read_capped(paths, limit=limit)
