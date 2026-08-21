from core.tools.projects import get_feature_context, update_feature


def test_get_feature_context_finds_feature_at_project_root():
    update_feature("FCTestRoot", "Widget", "root content")
    result = get_feature_context("FCTestRoot", "Widget")
    assert result["feature"] == "root content"


def test_get_feature_context_finds_feature_in_a_subfolder():
    from core.vault import safe_path, write

    write(safe_path("02-Builder/Projects/FCTestSub/architecture/Feature - Widget.md"),
          "subfolder content", overwrite=True)
    result = get_feature_context("FCTestSub", "Widget")
    assert result["feature"] == "subfolder content"


def test_get_feature_context_returns_none_when_missing():
    result = get_feature_context("FCTestMissing", "NoSuchFeature")
    assert result["feature"] is None
