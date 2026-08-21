from pathlib import Path

import pytest

import core.tools.architecture as arch_mod
from core.tools.architecture import (
    get_architecture_decisions,
    get_solution_architecture_context,
    get_tech_analysis_history,
    save_decision,
)
from core.vault import safe_path, write


@pytest.fixture
def professional_roots(monkeypatch):
    decisions = Path("01-Professional/Decisions")
    projects = Path("01-Professional/Projects")
    tech_analysis = Path("01-Professional/TechAnalysis")
    architecture = Path("01-Professional/Architecture")
    monkeypatch.setattr(arch_mod, "PROFESSIONAL_DECISIONS", decisions)
    monkeypatch.setattr(arch_mod, "PROFESSIONAL_PROJECTS", projects)
    monkeypatch.setattr(arch_mod, "PROFESSIONAL_TECH_ANALYSIS", tech_analysis)
    monkeypatch.setattr(arch_mod, "PROFESSIONAL_ARCHITECTURE", architecture)
    return {
        "decisions": decisions,
        "projects": projects,
        "tech_analysis": tech_analysis,
        "architecture": architecture,
    }


def test_save_decision_professional_writes_into_decisions_root(professional_roots):
    path = save_decision(
        "Widget Choice", "**Decided:** x\n**What it means:** y", professional=True
    )
    assert path.startswith("01-Professional/Decisions/")


def test_save_decision_builder_requires_project_name():
    with pytest.raises(ValueError, match="project_name is required"):
        save_decision("Title", "**Decided:** x\n**What it means:** y", professional=False)


def test_get_architecture_decisions_professional_default_root(professional_roots):
    write(
        safe_path(professional_roots["decisions"] / "some-decision.md"),
        "**Decided:** x\n**What it means:** y",
        overwrite=True,
    )
    results = get_architecture_decisions(professional=True)
    assert any(r["path"].endswith("some-decision.md") for r in results)


def test_get_architecture_decisions_professional_with_project(professional_roots):
    proj_dir = professional_roots["projects"] / "ProjA"
    write(safe_path(proj_dir / "Decision - foo.md"), "content", overwrite=True)
    results = get_architecture_decisions(project_name="ProjA", professional=True)
    assert any("Decision - foo.md" in r["path"] for r in results)


def test_get_architecture_decisions_builder_requires_project_name():
    with pytest.raises(ValueError, match="project_name is required"):
        get_architecture_decisions(professional=False)


def test_get_architecture_decisions_builder_filters_to_decision_files():
    # BUILDER_PROJECTS (02-Builder/Projects) is already configured by the
    # test taxonomy fixture in conftest.py -- no monkeypatch needed.
    write(safe_path("02-Builder/Projects/ArchTestProj/Decision - one.md"), "d", overwrite=True)
    write(safe_path("02-Builder/Projects/ArchTestProj/Notes.md"), "n", overwrite=True)
    results = get_architecture_decisions(project_name="ArchTestProj", professional=False)
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


def test_get_solution_architecture_context_gathers_everything(professional_roots):
    write(safe_path(professional_roots["projects"] / "CtxProj" / "note.md"), "n", overwrite=True)
    write(safe_path(professional_roots["tech_analysis"] / "CtxProj - ta.md"), "t", overwrite=True)
    write(safe_path(professional_roots["architecture"] / "CtxProj - arch.md"), "a", overwrite=True)

    result = get_solution_architecture_context("CtxProj")

    assert len(result["project"]) == 1
    assert len(result["tech_analysis"]) == 1
    assert len(result["architecture"]) == 1
