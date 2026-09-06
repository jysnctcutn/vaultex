import pytest

from core.taxonomy import project_subfolders as _global_project_subfolders
from core.tools.architecture import save_decision
from core.tools.projects import update_feature


@pytest.fixture
def configured_project():
    name = "WTSTestProj"
    _global_project_subfolders[name] = ["architecture", "general"]
    yield name
    del _global_project_subfolders[name]


def test_save_decision_rejects_missing_subfolder_when_configured(configured_project):
    with pytest.raises(ValueError, match="one of"):
        save_decision("Title", "**Decided:** x\n**What it means:** y", project_name=configured_project)


def test_save_decision_writes_into_configured_subfolder(configured_project):
    path = save_decision("Widget Choice", "**Decided:** x\n**What it means:** y",
                          project_name=configured_project, subfolder="architecture")
    assert path.startswith(f"02-Builder/Projects/{configured_project}/architecture/")


def test_save_decision_unconfigured_project_ignores_subfolder_param_by_rejecting_it():
    with pytest.raises(ValueError, match="no configured subfolders"):
        save_decision("Title", "**Decided:** x\n**What it means:** y",
                       project_name="WTSTestUnconfigured", subfolder="architecture")


def test_update_feature_writes_into_configured_subfolder(configured_project):
    path = update_feature(configured_project, "Widget", "content", subfolder="general")
    assert path == f"02-Builder/Projects/{configured_project}/general/Feature - Widget.md"


def test_save_decision_rejects_subfolder_when_professional():
    with pytest.raises(ValueError, match="only applies to project decisions"):
        save_decision("Title", "**Decided:** x\n**What it means:** y",
                       subfolder="architecture")
