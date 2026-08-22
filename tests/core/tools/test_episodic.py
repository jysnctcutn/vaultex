import uuid
from pathlib import Path

import pytest

import core.tools.episodic as episodic_mod
from core.vault import VerificationError, read, safe_path


@pytest.fixture
def episodic_root(monkeypatch):
    root = Path(f"02-Builder/Episodic-{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(episodic_mod, "EPISODIC", root)
    yield root


def test_log_event_requires_configured_role():
    with pytest.raises(Exception, match="not configured|isn't configured"):
        episodic_mod.log_event("SomeProject", "event", "did a thing")


def test_start_session_requires_configured_role():
    with pytest.raises(Exception, match="not configured|isn't configured"):
        episodic_mod.start_session("SomeProject", "get the thing done")


def test_log_event_rejects_bad_kind(episodic_root):
    with pytest.raises(ValueError, match="kind must be"):
        episodic_mod.log_event("SomeProject", "session", "nope")


def test_log_event_rejects_missing_project(episodic_root):
    with pytest.raises(ValueError, match="project is required"):
        episodic_mod.log_event("", "event", "nope")


def test_log_event_writes_structured_note(episodic_root):
    path = episodic_mod.log_event("SomeProject", "event", "did a thing", details="extra context",
                                   agents=["dev"], tags=["auth"])
    content = read(safe_path(path))
    assert "kind: event" in content
    assert "project: SomeProject" in content
    assert "## What happened\ndid a thing" in content
    assert "## Decisions made (raw)\nextra context" in content
    assert path.startswith(str(episodic_root))
    assert "-event-" in path


def test_log_event_defaults_details_when_omitted(episodic_root):
    path = episodic_mod.log_event("SomeProject", "outcome", "shipped it")
    content = read(safe_path(path))
    assert "## Decisions made (raw)\n(none)" in content
    assert "-outcome-" in path


def test_start_session_opens_note_with_status_open(episodic_root):
    path = episodic_mod.start_session("SomeProject", "ship the feature", task_id="task-1", agents=["ba"])
    content = read(safe_path(path))
    assert "kind: session" in content
    assert "status: open" in content
    assert "task_id: task-1" in content
    assert "## Goal\nship the feature" in content
    assert "-session-" in path


def test_close_session_requires_existing_note(episodic_root):
    with pytest.raises(FileNotFoundError):
        episodic_mod.close_session(f"{episodic_root}/2026-08/nope.md", "done")


def test_close_session_rejects_non_session_note(episodic_root):
    event_path = episodic_mod.log_event("SomeProject", "event", "did a thing")
    with pytest.raises(ValueError, match="not a session note"):
        episodic_mod.close_session(event_path, "done")


def test_close_session_sets_status_closed_and_appends_outcome(episodic_root):
    session_path = episodic_mod.start_session("SomeProject", "ship the feature")
    closed_path = episodic_mod.close_session(session_path, "shipped and verified")
    assert closed_path == session_path
    content = read(safe_path(closed_path))
    assert "status: closed" in content
    assert "## Outcome\nshipped and verified" in content


def test_close_session_rejects_already_closed(episodic_root):
    session_path = episodic_mod.start_session("SomeProject", "ship the feature")
    episodic_mod.close_session(session_path, "shipped")
    with pytest.raises(ValueError, match="not open"):
        episodic_mod.close_session(session_path, "shipped again")


def test_required_sections_are_hard_validated(episodic_root):
    # Sanity check that the shared constant matches the locked-defaults schema.
    assert episodic_mod.REQUIRED_SECTIONS == [
        "## Goal",
        "## What happened",
        "## Decisions made (raw)",
        "## Open questions left",
        "## Artifacts / links",
    ]


def test_verify_sections_still_raises_verification_error_shape():
    with pytest.raises(VerificationError):
        from core.vault import verify_sections
        verify_sections("no headings here", episodic_mod.REQUIRED_SECTIONS)
