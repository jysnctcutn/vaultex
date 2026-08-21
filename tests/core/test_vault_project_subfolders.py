import pytest

from core.vault import resolve_project_subfolder


def test_unconfigured_project_with_no_subfolder_passes():
    assert resolve_project_subfolder("KALAM", None, None) == ""


def test_unconfigured_project_with_empty_list_passes():
    assert resolve_project_subfolder("KALAM", None, []) == ""


def test_unconfigured_project_rejects_subfolder():
    with pytest.raises(ValueError, match="no configured subfolders"):
        resolve_project_subfolder("KALAM", "architecture", None)


def test_configured_project_accepts_valid_subfolder():
    allowed = ["architecture", "legal", "general", "archives"]
    assert resolve_project_subfolder("SuriinPH", "legal", allowed) == "legal"


def test_configured_project_rejects_missing_subfolder():
    allowed = ["architecture", "legal", "general", "archives"]
    with pytest.raises(ValueError, match="one of"):
        resolve_project_subfolder("SuriinPH", None, allowed)


def test_configured_project_rejects_invalid_subfolder():
    allowed = ["architecture", "legal", "general", "archives"]
    with pytest.raises(ValueError, match="one of"):
        resolve_project_subfolder("SuriinPH", "finance", allowed)


def test_configured_project_rejects_case_mismatch():
    allowed = ["architecture", "legal", "general", "archives"]
    with pytest.raises(ValueError, match="one of"):
        resolve_project_subfolder("SuriinPH", "Architecture", allowed)
