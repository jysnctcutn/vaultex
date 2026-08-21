import pytest

from core.vault import VAULT_PATH, move, read, safe_path, write


def _make_note(rel_path: str, content: str = "hello") -> None:
    write(safe_path(rel_path), content, overwrite=True)


def test_move_relocates_the_file():
    _make_note("move-src-1.md")
    new_path = move(safe_path("move-src-1.md"), safe_path("moved/move-dst-1.md"), overwrite=False)
    assert new_path == "moved/move-dst-1.md"
    assert not (VAULT_PATH / "move-src-1.md").exists()
    assert read(VAULT_PATH / "moved" / "move-dst-1.md") == "hello"


def test_move_missing_source_raises():
    with pytest.raises(FileNotFoundError):
        move(safe_path("does-not-exist.md"), safe_path("moved/somewhere.md"), overwrite=False)


def test_move_collision_without_overwrite_raises():
    _make_note("move-src-2.md", "src")
    _make_note("move-dst-2.md", "dst")
    with pytest.raises(FileExistsError):
        move(safe_path("move-src-2.md"), safe_path("move-dst-2.md"), overwrite=False)


def test_move_collision_with_overwrite_succeeds():
    _make_note("move-src-3.md", "src content")
    _make_note("move-dst-3.md", "stale content")
    move(safe_path("move-src-3.md"), safe_path("move-dst-3.md"), overwrite=True)
    assert read(VAULT_PATH / "move-dst-3.md") == "src content"


def test_move_rejects_traversal_on_either_path():
    _make_note("move-src-4.md")
    with pytest.raises(ValueError, match="escapes the vault"):
        move(safe_path("move-src-4.md"), safe_path("../outside.md"), overwrite=False)
    with pytest.raises(ValueError, match="escapes the vault"):
        move(safe_path("../outside.md"), safe_path("moved/move-dst-4.md"), overwrite=False)


def test_move_rejects_excluded_area_on_either_side():
    _make_note("move-src-5.md")
    with pytest.raises(PermissionError):
        move(safe_path("move-src-5.md"), safe_path("01-Excluded/move-dst-5.md"), overwrite=False)
