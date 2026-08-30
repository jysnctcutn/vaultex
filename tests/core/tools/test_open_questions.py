import uuid
from pathlib import Path

import pytest

import core.tools.open_questions as oq_mod
from core.vault import read, safe_path, write


@pytest.fixture
def oq_root(monkeypatch):
    root = Path(f"02-Builder/OpenQuestions-{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(oq_mod, "OPEN_QUESTIONS", root)
    yield root


def test_save_open_question_requires_configured_role():
    with pytest.raises(Exception, match="not configured|isn't configured"):
        oq_mod.save_open_question("SomeProject", "why is the sky blue?")


def test_save_open_question_requires_project_and_question(oq_root):
    with pytest.raises(ValueError, match="project is required"):
        oq_mod.save_open_question("", "q")
    with pytest.raises(ValueError, match="question is required"):
        oq_mod.save_open_question("P", "")


def test_save_open_question_rejects_bad_status(oq_root):
    with pytest.raises(ValueError, match="status must be one of"):
        oq_mod.save_open_question("P", "q", status="maybe")


def test_save_open_question_writes_structured_note(oq_root):
    path = oq_mod.save_open_question("ProjA", "should we shard the DB?",
                                     context="load is climbing", owner="dev")
    content = read(safe_path(path))
    assert "type: open-question" in content
    assert "project: ProjA" in content
    assert "status: open" in content
    assert "owner: dev" in content
    assert "raised:" in content
    assert "## Question\nshould we shard the DB?" in content
    assert "## Context\nload is climbing" in content
    assert "## Resolution\n(unresolved)" in content
    assert path.startswith(str(oq_root))
    assert "Open Question - " in path


def test_save_open_question_rejects_dangling_source_episodic(oq_root):
    with pytest.raises(ValueError, match="doesn't exist"):
        oq_mod.save_open_question("ProjA", "q", source_episodic="02-Builder/Episodic/nope.md")


def test_save_open_question_accepts_real_source_episodic(oq_root):
    src = "02-Builder/Episodic/2026-08/session.md"
    write(safe_path(src), "session", overwrite=True)
    path = oq_mod.save_open_question("ProjA", "linked question", source_episodic=src)
    assert f"source_episodic: {src}" in read(safe_path(path))


def test_get_open_questions_lists_and_filters_by_status(oq_root):
    oq_mod.save_open_question("ProjA", "first q")
    answered = oq_mod.save_open_question("ProjA", "second q", status="answered")
    oq_mod.save_open_question("ProjB", "other project q")

    all_a = oq_mod.get_open_questions("ProjA")
    assert len(all_a) == 2

    only_answered = oq_mod.get_open_questions("ProjA", status="answered")
    assert len(only_answered) == 1
    assert only_answered[0]["path"] in answered


def test_get_open_questions_empty_for_unknown_project(oq_root):
    assert oq_mod.get_open_questions("NoSuchProject") == []
