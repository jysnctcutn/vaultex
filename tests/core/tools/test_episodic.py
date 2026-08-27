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


# --- Phase 2: update_session ---

def test_update_session_replaces_one_section_leaves_others(episodic_root):
    path = episodic_mod.start_session("SomeProject", "ship the feature")
    episodic_mod.update_session(path, what_happened="wired up the endpoint")
    content = read(safe_path(path))
    assert "## What happened\nwired up the endpoint" in content
    assert "## Goal\nship the feature" in content
    # untouched sections keep their placeholder
    assert "## Decisions made (raw)\n(in progress)" in content


def test_update_session_updates_multiple_sections(episodic_root):
    path = episodic_mod.start_session("SomeProject", "ship the feature")
    episodic_mod.update_session(path, what_happened="did X", decisions="chose Y",
                                open_questions="what about Z", artifacts="PR #12")
    content = read(safe_path(path))
    assert "## What happened\ndid X" in content
    assert "## Decisions made (raw)\nchose Y" in content
    assert "## Open questions left\nwhat about Z" in content
    assert "## Artifacts / links\nPR #12" in content
    assert "(in progress)" not in content


def test_update_session_requires_at_least_one_field(episodic_root):
    path = episodic_mod.start_session("SomeProject", "ship the feature")
    with pytest.raises(ValueError, match="at least one of"):
        episodic_mod.update_session(path)


def test_update_session_rejects_closed_session(episodic_root):
    path = episodic_mod.start_session("SomeProject", "ship the feature")
    episodic_mod.close_session(path, "shipped")
    with pytest.raises(ValueError, match="not open"):
        episodic_mod.update_session(path, what_happened="too late")


def test_update_session_rejects_non_session_note(episodic_root):
    event_path = episodic_mod.log_event("SomeProject", "event", "did a thing")
    with pytest.raises(ValueError, match="not a session note"):
        episodic_mod.update_session(event_path, what_happened="nope")


def test_update_session_content_survives_close(episodic_root):
    path = episodic_mod.start_session("SomeProject", "ship the feature")
    episodic_mod.update_session(path, what_happened="built the thing", decisions="went with A")
    episodic_mod.close_session(path, "done")
    content = read(safe_path(path))
    assert "## What happened\nbuilt the thing" in content
    assert "## Decisions made (raw)\nwent with A" in content
    assert "## Outcome\ndone" in content


# --- Phase 2: get_episodic_context / recent_episodic_paths ---

def test_get_episodic_context_requires_configured_role():
    with pytest.raises(Exception, match="not configured|isn't configured"):
        episodic_mod.get_episodic_context("SomeProject")


def test_get_episodic_context_filters_by_project(episodic_root):
    episodic_mod.log_event("ProjA", "event", "a thing")
    episodic_mod.log_event("ProjB", "event", "b thing")
    results = episodic_mod.get_episodic_context("ProjA")
    assert len(results) == 1
    assert "project: ProjA" in results[0]["content"]


def test_get_episodic_context_filters_by_kind_and_status(episodic_root):
    episodic_mod.log_event("ProjA", "event", "an event")
    episodic_mod.log_event("ProjA", "outcome", "an outcome")
    open_session = episodic_mod.start_session("ProjA", "a session")

    events = episodic_mod.get_episodic_context("ProjA", kind="event")
    assert len(events) == 1 and "kind: event" in events[0]["content"]

    open_notes = episodic_mod.get_episodic_context("ProjA", status="open")
    assert len(open_notes) == 1 and open_notes[0]["path"] in open_session


def test_get_episodic_context_rejects_bad_kind(episodic_root):
    with pytest.raises(ValueError, match="kind must be"):
        episodic_mod.get_episodic_context("ProjA", kind="bogus")


def test_get_episodic_context_respects_limit(episodic_root):
    for i in range(3):
        episodic_mod.log_event("ProjA", "event", f"thing {i}")
    assert len(episodic_mod.get_episodic_context("ProjA", limit=2)) == 2


def test_get_episodic_context_time_window_excludes_old_notes(episodic_root):
    from core.frontmatter import join
    from core.vault import write

    episodic_mod.log_event("ProjA", "event", "recent thing")
    old = safe_path(episodic_root / "1999-01" / "1999-01-01-T0000-event-ancient.md")
    body = ("## Goal\n(none)\n\n## What happened\nancient\n\n## Decisions made (raw)\n(none)\n\n"
            "## Open questions left\n(none)\n\n## Artifacts / links\n(none)\n")
    write(old, join({"type": "episodic", "kind": "event", "project": "ProjA",
                     "status": "closed", "started": "1999-01-01T00:00:00",
                     "ended": "1999-01-01T00:00:00"}, body), overwrite=True)

    assert len(episodic_mod.get_episodic_context("ProjA", days=7)) == 1
    assert len(episodic_mod.get_episodic_context("ProjA", days=0)) == 2


def test_get_episodic_context_promoted_filter(episodic_root):
    from core.frontmatter import join, split
    from core.vault import read, write

    plain = episodic_mod.log_event("ProjA", "event", "not yet distilled")
    done = episodic_mod.log_event("ProjA", "event", "already distilled")
    fm, body = split(read(safe_path(done)))
    fm["promoted"] = True
    write(safe_path(done), join(fm, body), overwrite=True)

    not_promoted = episodic_mod.get_episodic_context("ProjA", promoted=False)
    assert [n["path"] for n in not_promoted] == [plain]

    promoted = episodic_mod.get_episodic_context("ProjA", promoted=True)
    assert [n["path"] for n in promoted] == [done]
