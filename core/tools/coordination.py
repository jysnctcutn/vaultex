"""Multi-agent coordination (Phase 4): lightweight claim / release /
conflict primitives on note frontmatter. No distributed consensus -- an
agent is told (via skill / system prompt) to claim a note before a major
edit and to stop on a lock or conflict it doesn't own. All four tools work
on any note by path, like update_frontmatter; they are plain writes/reads,
not taxonomy-role-gated.
"""

from datetime import datetime, timezone
from pathlib import Path

from ..frontmatter import join, split
from ..mcp_app import mcp, write_tool
from ..vault import read, safe_path, write


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def _load(path: str):
    note_path = safe_path(path)
    if not note_path.is_file():
        raise FileNotFoundError(f"No such note: {path}")
    fm, body = split(read(note_path))
    return note_path, fm, body


@write_tool
def claim_note(path: str, agent: str, force: bool = False) -> str:
    """Claim a note for exclusive editing by `agent` -- sets `locked_by` /
    `locked_at` in frontmatter. Re-claiming your own lock just refreshes
    `locked_at`. Raises if another agent holds the lock unless force=True
    (for a stale lock left by a crashed run)."""
    if not agent:
        raise ValueError("agent is required")
    note_path, fm, body = _load(path)
    holder = fm.get("locked_by")
    if holder and holder != agent and not force:
        raise ValueError(
            f"{path} is locked by {holder!r} since {fm.get('locked_at')}. "
            "Stop, or pass force=True to override a stale lock."
        )
    fm["locked_by"] = agent
    fm["locked_at"] = _now()
    return write(note_path, join(fm, body), overwrite=True)


@write_tool
def release_note(path: str, agent: str, force: bool = False) -> str:
    """Release a note claimed with claim_note -- clears `locked_by` /
    `locked_at`. Raises if the lock is held by a different agent unless
    force=True. Succeeds (no-op) if the note isn't locked."""
    if not agent:
        raise ValueError("agent is required")
    note_path, fm, body = _load(path)
    holder = fm.get("locked_by")
    if holder and holder != agent and not force:
        raise ValueError(
            f"{path} is locked by {holder!r}, not {agent!r}. "
            "Pass force=True to release someone else's lock."
        )
    fm.pop("locked_by", None)
    fm.pop("locked_at", None)
    return write(note_path, join(fm, body), overwrite=True)


@write_tool
def flag_conflict(path: str, conflicts_with: list[str] | None = None, note: str = "") -> str:
    """Mark a note as conflicted when two runs reached incompatible
    conclusions about it: sets `status: conflict` + `conflict_flagged_at`
    in frontmatter, records `conflicts_with` (paths of the competing
    episodic/durable notes, each must exist), and appends a
    `## Conflict (<date>)` body section with `note` and links to them."""
    note_path, fm, body = _load(path)
    stamp = _now()
    links = conflicts_with or []
    for ref in links:
        if not safe_path(ref).is_file():
            raise ValueError(f"conflicts_with points at a note that doesn't exist: {ref!r}")
    fm["status"] = "conflict"
    fm["conflict_flagged_at"] = stamp
    if links:
        fm["conflicts_with"] = links
    section = [f"## Conflict ({stamp[:10]})"]
    if note:
        section.append(note)
    section += [f"- [[{Path(ref).stem}]]" for ref in links]
    new_body = f"{body.rstrip()}\n\n" + "\n".join(section) + "\n"
    return write(note_path, join(fm, new_body), overwrite=True)


@mcp.tool()
def check_note_status(path: str) -> dict:
    """Quick pre-edit check for a note -- its lock holder/time and conflict
    state, without reading the whole note. Returns {locked_by, locked_at,
    status, conflicts_with}; unset fields come back null / []."""
    _, fm, _ = _load(path)
    return {
        "locked_by": fm.get("locked_by"),
        "locked_at": fm.get("locked_at"),
        "status": fm.get("status"),
        "conflicts_with": fm.get("conflicts_with", []),
    }
