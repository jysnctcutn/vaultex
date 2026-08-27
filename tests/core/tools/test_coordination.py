import pytest

from core.tools.coordination import (
    check_note_status,
    claim_note,
    flag_conflict,
    release_note,
)
from core.vault import read, safe_path, write


def _note(name: str, body: str = "body") -> str:
    rel = f"02-Builder/Projects/CoordProj/{name}.md"
    write(safe_path(rel), body, overwrite=True)
    return rel


# --- claim_note ---

def test_claim_note_sets_lock(tmp_path):
    path = _note("claim-basic")
    claim_note(path, "agent-a")
    content = read(safe_path(path))
    assert "locked_by: agent-a" in content
    assert "locked_at:" in content


def test_claim_note_requires_agent():
    path = _note("claim-no-agent")
    with pytest.raises(ValueError, match="agent is required"):
        claim_note(path, "")


def test_claim_note_missing_file_raises():
    with pytest.raises(FileNotFoundError):
        claim_note("02-Builder/Projects/CoordProj/nope.md", "agent-a")


def test_claim_note_reclaim_own_lock_refreshes(monkeypatch):
    path = _note("claim-reclaim")
    stamps = iter(["2026-08-28T10:00:00", "2026-08-28T11:00:00"])
    monkeypatch.setattr("core.tools.coordination._now", lambda: next(stamps))
    claim_note(path, "agent-a")
    claim_note(path, "agent-a")  # no error
    assert "locked_at: '2026-08-28T11:00:00'" in read(safe_path(path))


def test_claim_note_foreign_lock_raises():
    path = _note("claim-foreign")
    claim_note(path, "agent-a")
    with pytest.raises(ValueError, match="locked by 'agent-a'"):
        claim_note(path, "agent-b")


def test_claim_note_force_steals_lock():
    path = _note("claim-force")
    claim_note(path, "agent-a")
    claim_note(path, "agent-b", force=True)
    assert "locked_by: agent-b" in read(safe_path(path))


# --- release_note ---

def test_release_note_clears_lock():
    path = _note("release-basic")
    claim_note(path, "agent-a")
    release_note(path, "agent-a")
    content = read(safe_path(path))
    assert "locked_by" not in content
    assert "locked_at" not in content


def test_release_note_unlocked_is_noop():
    path = _note("release-noop")
    release_note(path, "agent-a")  # no error


def test_release_note_foreign_lock_raises_without_force():
    path = _note("release-foreign")
    claim_note(path, "agent-a")
    with pytest.raises(ValueError, match="not 'agent-b'"):
        release_note(path, "agent-b")


def test_release_note_force_releases_foreign_lock():
    path = _note("release-force")
    claim_note(path, "agent-a")
    release_note(path, "agent-b", force=True)
    assert "locked_by" not in read(safe_path(path))


# --- flag_conflict ---

def test_flag_conflict_writes_frontmatter_and_body_section():
    path = _note("conflict-basic")
    competing = _note("competing-session")
    flag_conflict(path, conflicts_with=[competing], note="two runs disagreed on the schema")
    content = read(safe_path(path))
    assert "status: conflict" in content
    assert "conflict_flagged_at:" in content
    assert "conflicts_with:" in content
    assert "## Conflict (" in content
    assert "two runs disagreed on the schema" in content
    assert "[[competing-session]]" in content


def test_flag_conflict_rejects_dangling_reference():
    path = _note("conflict-dangling")
    with pytest.raises(ValueError, match="doesn't exist"):
        flag_conflict(path, conflicts_with=["02-Builder/Projects/CoordProj/ghost.md"])


def test_flag_conflict_without_references_still_flags():
    path = _note("conflict-bare")
    flag_conflict(path, note="needs a human")
    content = read(safe_path(path))
    assert "status: conflict" in content
    assert "## Conflict (" in content


# --- check_note_status ---

def test_check_note_status_reports_lock_and_conflict():
    path = _note("status-full")
    competing = _note("status-competing")
    claim_note(path, "agent-a")
    flag_conflict(path, conflicts_with=[competing])
    status = check_note_status(path)
    assert status["locked_by"] == "agent-a"
    assert status["locked_at"]
    assert status["status"] == "conflict"
    assert status["conflicts_with"] == [competing]


def test_check_note_status_clean_note_returns_nulls():
    path = _note("status-clean")
    status = check_note_status(path)
    assert status == {"locked_by": None, "locked_at": None, "status": None, "conflicts_with": []}
