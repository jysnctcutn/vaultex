import pytest

from core.tools.move import move_note
from core.vault import VAULT_PATH, read, safe_path, write


def test_move_note_relocates_the_file():
    write(safe_path("tool-move-src.md"), "hello", overwrite=True)
    new_path = move_note("tool-move-src.md", "moved/tool-move-dst.md")
    assert new_path == "moved/tool-move-dst.md"
    assert not (VAULT_PATH / "tool-move-src.md").exists()
    assert read(VAULT_PATH / "moved" / "tool-move-dst.md") == "hello"


def test_move_note_rejects_traversal():
    write(safe_path("tool-move-src-2.md"), "hello", overwrite=True)
    with pytest.raises(ValueError, match="escapes the vault"):
        move_note("tool-move-src-2.md", "../outside.md")
