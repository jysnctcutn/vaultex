import uuid
from pathlib import Path

import pytest

import core.tools.builder as builder_mod
from core.vault import read, safe_path, write


@pytest.fixture
def builder_ideas_root(monkeypatch):
    root = Path(f"02-Builder/Ideas-{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(builder_mod, "BUILDER_IDEAS", root)
    yield root


def test_get_app_ideas_requires_configured_role():
    with pytest.raises(Exception, match="not configured|isn't configured"):
        builder_mod.get_app_ideas()


def test_create_app_idea_requires_configured_role():
    with pytest.raises(Exception, match="not configured|isn't configured"):
        builder_mod.create_app_idea("Some Idea", "content")


def test_create_app_idea_writes_note(builder_ideas_root):
    path = builder_mod.create_app_idea("My Cool Idea", "some content")
    assert path == f"{builder_ideas_root}/My Cool Idea.md"
    assert read(safe_path(path)) == "some content"


def test_create_app_idea_rejects_duplicate(builder_ideas_root):
    builder_mod.create_app_idea("Dup Idea", "first")
    with pytest.raises(FileExistsError):
        builder_mod.create_app_idea("Dup Idea", "second")


def test_get_app_ideas_lists_with_excerpt(builder_ideas_root):
    write(safe_path(builder_ideas_root / "manual-idea.md"), "x" * 300, overwrite=True)
    ideas = builder_mod.get_app_ideas(limit=5)
    assert len(ideas) == 1
    assert ideas[0]["path"] == f"{builder_ideas_root}/manual-idea.md"
    assert len(ideas[0]["excerpt"]) <= 200
