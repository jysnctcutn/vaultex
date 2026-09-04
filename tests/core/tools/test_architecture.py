from pathlib import Path

import pytest

import core.tools.architecture as arch_mod
from core.tools.architecture import (
    get_architecture_decisions,
    get_architecture_context,
    get_tech_analysis_history,
    save_decision,
)
from core.vault import read, safe_path, write


@pytest.fixture
def professional_roots(monkeypatch):
    decisions = Path("01-Professional/Decisions")
    projects = Path("01-Professional/Projects")
    tech_analysis = Path("01-Professional/TechAnalysis")
    architecture = Path("01-Professional/Architecture")
    monkeypatch.setattr(arch_mod, "DECISIONS", decisions)
    monkeypatch.setattr(arch_mod, "TECH_ANALYSIS", tech_analysis)
    monkeypatch.setattr(arch_mod, "ARCHITECTURE", architecture)

    # Project roots resolve through workspaces. Stubbing the resolver keeps
    # the two contexts these tests rely on: workspace="Work" lands in the
    # fixture's own tree, the default in the project root conftest configures.
    def _resolve(workspace=None):
        if workspace == "Work":
            return "Work", projects
        return "Projects", Path("02-Builder/Projects")

    monkeypatch.setattr(arch_mod, "resolve_workspace", _resolve)
    return {
        "decisions": decisions,
        "projects": projects,
        "tech_analysis": tech_analysis,
        "architecture": architecture,
    }


def test_save_decision_professional_writes_into_decisions_root(professional_roots):
    path = save_decision(
        "Widget Choice", "**Decided:** x\n**What it means:** y"
    )
    assert path.startswith("01-Professional/Decisions/")


def test_save_decision_without_project_name_writes_a_standalone_decision(professional_roots):
    """Behavior change in the role-vocabulary cut: this used to raise
    "project_name is required". Omitting project_name is now how you ask for
    a standalone decision."""
    path = save_decision("Standalone Thing", "**Decided:** x\n**What it means:** y")
    assert path.startswith("01-Professional/Decisions/")


def test_save_decision_without_provenance_writes_content_verbatim(professional_roots):
    body = "**Decided:** x\n**What it means:** y"
    path = save_decision("No Prov", body)
    assert read(safe_path(path)) == body


def test_save_decision_stamps_provenance_frontmatter(professional_roots):
    src = "02-Builder/Episodic/2026-08/2026-08-27-T1200-session-thing.md"
    write(safe_path(src), "session note", overwrite=True)
    path = save_decision(
        "With Prov", "**Decided:** x\n**What it means:** y",
        source_episodic=src, agents=["dev", "ba"],
    )
    content = read(safe_path(path))
    assert content.startswith("---\n")
    assert f"source_episodic: {src}" in content
    assert "type: decision" in content
    assert "- dev" in content and "- ba" in content
    assert "decided:" in content
    assert "**Decided:** x" in content


def test_save_decision_rejects_dangling_source_episodic(professional_roots):
    with pytest.raises(ValueError, match="doesn't exist"):
        save_decision(
            "Bad Prov", "**Decided:** x\n**What it means:** y",
            source_episodic="02-Builder/Episodic/nope.md",
        )


def test_get_architecture_decisions_professional_default_root(professional_roots):
    write(
        safe_path(professional_roots["decisions"] / "some-decision.md"),
        "**Decided:** x\n**What it means:** y",
        overwrite=True,
    )
    results = get_architecture_decisions()
    assert any(r["path"].endswith("some-decision.md") for r in results)


def test_get_architecture_decisions_professional_with_project(professional_roots):
    proj_dir = professional_roots["projects"] / "ProjA"
    write(safe_path(proj_dir / "Decision - foo.md"), "content", overwrite=True)
    results = get_architecture_decisions(project_name="ProjA", workspace="Work")
    assert any("Decision - foo.md" in r["path"] for r in results)


def test_save_decision_rejects_workspace_without_project_name():
    with pytest.raises(ValueError, match="only applies to project decisions"):
        save_decision("T", "**Decided:** x\n**What it means:** y", workspace="Work")


def test_get_architecture_decisions_builder_filters_to_decision_files():
    # BUILDER_PROJECTS (02-Builder/Projects) is already configured by the
    # test taxonomy fixture in conftest.py -- no monkeypatch needed.
    write(safe_path("02-Builder/Projects/ArchTestProj/Decision - one.md"), "d", overwrite=True)
    write(safe_path("02-Builder/Projects/ArchTestProj/Notes.md"), "n", overwrite=True)
    results = get_architecture_decisions(project_name="ArchTestProj")
    paths = [r["path"] for r in results]
    assert any("Decision - one.md" in p for p in paths)
    assert not any(p.endswith("Notes.md") for p in paths)


def test_get_tech_analysis_history_filters_by_project(professional_roots):
    root = professional_roots["tech_analysis"]
    write(safe_path(root / "ProjA - analysis.md"), "content", overwrite=True)
    write(safe_path(root / "ProjB - analysis.md"), "content", overwrite=True)
    results = get_tech_analysis_history(project_name="ProjA")
    assert len(results) == 1
    assert "ProjA" in results[0]["path"]


def test_get_tech_analysis_history_no_filter_returns_all(professional_roots):
    root = professional_roots["tech_analysis"]
    write(safe_path(root / "AllOne.md"), "content", overwrite=True)
    write(safe_path(root / "AllTwo.md"), "content", overwrite=True)
    results = get_tech_analysis_history()
    assert len(results) >= 2


def test_get_architecture_context_gathers_everything(professional_roots):
    write(safe_path(professional_roots["projects"] / "CtxProj" / "note.md"), "n", overwrite=True)
    write(safe_path(professional_roots["tech_analysis"] / "CtxProj - ta.md"), "t", overwrite=True)
    write(safe_path(professional_roots["architecture"] / "CtxProj - arch.md"), "a", overwrite=True)

    result = get_architecture_context("CtxProj", workspace="Work")

    assert len(result["project"]) == 1
    assert len(result["tech_analysis"]) == 1
    assert len(result["architecture"]) == 1
