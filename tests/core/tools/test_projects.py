import uuid
from pathlib import Path

import pytest

import core.tools.episodic as episodic_mod
from core.tools.projects import get_feature_context, get_project_context, update_feature
from core.vault import safe_path, write


@pytest.fixture
def episodic_root(monkeypatch):
    root = Path(f"02-Builder/Episodic-{uuid.uuid4().hex[:8]}")
    monkeypatch.setattr(episodic_mod, "EPISODIC", root)
    yield root


def test_get_project_context_lists_project_notes():
    write(safe_path("02-Builder/Projects/PCTestProj/Notes.md"), "notes content", overwrite=True)
    results = get_project_context("PCTestProj")
    assert any(r["path"].endswith("Notes.md") for r in results)


def test_get_project_context_respects_limit():
    for i in range(3):
        write(safe_path(f"02-Builder/Projects/PCTestLimit/Note{i}.md"), "x", overwrite=True)
    results = get_project_context("PCTestLimit", limit=2)
    assert len(results) == 2


def test_get_feature_context_finds_feature_at_project_root():
    update_feature("FCTestRoot", "Widget", "root content")
    result = get_feature_context("FCTestRoot", "Widget")
    assert result["feature"] == "root content"


def test_get_feature_context_finds_feature_in_a_subfolder():
    write(safe_path("02-Builder/Projects/FCTestSub/architecture/Feature - Widget.md"),
          "subfolder content", overwrite=True)
    result = get_feature_context("FCTestSub", "Widget")
    assert result["feature"] == "subfolder content"


def test_get_feature_context_returns_none_when_missing():
    result = get_feature_context("FCTestMissing", "NoSuchFeature")
    assert result["feature"] is None


def test_get_feature_context_includes_sibling_architecture_and_decisions():
    write(safe_path("02-Builder/Projects/PCTestSiblings/Architecture.md"), "arch content", overwrite=True)
    write(safe_path("02-Builder/Projects/PCTestSiblings/Decisions.md"), "decisions content", overwrite=True)
    update_feature("PCTestSiblings", "Widget", "feature content")

    result = get_feature_context("PCTestSiblings", "Widget")
    assert result["feature"] == "feature content"
    assert result["Architecture.md"] == "arch content"
    assert result["Decisions.md"] == "decisions content"


def test_update_feature_rejects_subfolder_when_professional():
    with pytest.raises(ValueError, match="only applies to Builder projects"):
        update_feature("PCTestProf", "Widget", "content", professional=True, subfolder="architecture")


def test_get_project_context_default_excludes_episodic(episodic_root):
    write(safe_path("02-Builder/Projects/EpiExcl/Notes.md"), "durable note", overwrite=True)
    episodic_mod.log_event("EpiExcl", "event", "a session event")
    results = get_project_context("EpiExcl")
    assert all("Episodic" not in r["path"] for r in results)


def test_get_project_context_include_episodic_appends_episodic_notes(episodic_root):
    write(safe_path("02-Builder/Projects/EpiInc/Notes.md"), "durable note", overwrite=True)
    episodic_mod.log_event("EpiInc", "event", "a session event")
    results = get_project_context("EpiInc", include_episodic=True)
    paths = [r["path"] for r in results]
    assert any("EpiInc/Notes.md" in p for p in paths)
    assert any(str(episodic_root) in p for p in paths)


def test_get_project_context_include_episodic_requires_configured_role(monkeypatch):
    monkeypatch.setattr(episodic_mod, "EPISODIC", None)
    with pytest.raises(Exception, match="not configured|isn't configured"):
        get_project_context("AnyProj", include_episodic=True)
