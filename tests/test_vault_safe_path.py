import pytest

from core.config import VAULT_PATH
from core.vault import safe_path


def test_allows_path_inside_vault():
    assert safe_path("some-note.md") == VAULT_PATH / "some-note.md"


def test_allows_nested_path_inside_vault():
    assert safe_path("02-Builder/Projects/note.md") == VAULT_PATH / "02-Builder/Projects/note.md"


def test_blocks_dotdot_traversal_outside_vault():
    with pytest.raises(ValueError, match="escapes the vault"):
        safe_path("../outside.md")


def test_blocks_deeper_dotdot_traversal_outside_vault():
    with pytest.raises(ValueError, match="escapes the vault"):
        safe_path("02-Builder/../../outside.md")


def test_blocks_absolute_path_escape():
    with pytest.raises(ValueError, match="escapes the vault"):
        safe_path("/etc/passwd")


def test_blocks_excluded_area():
    with pytest.raises(PermissionError):
        safe_path("01-Excluded/secret.md")


def test_allows_non_excluded_area():
    assert safe_path("02-Allowed/note.md") == VAULT_PATH / "02-Allowed/note.md"
