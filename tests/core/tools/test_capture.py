import pytest

from core.tools.capture import save_brainstorm
from core.vault import read, safe_path


def test_save_brainstorm_explicit_area():
    path = save_brainstorm("Explicit Area Idea", "some content", area="03-Knowledge/AI")
    assert path == "03-Knowledge/AI/Explicit Area Idea.md"
    assert read(safe_path(path)) == "some content"


def test_save_brainstorm_defaults_to_inbox_when_no_area_and_no_match():
    path = save_brainstorm("No Area Idea", "some other content")
    assert path.startswith("00-Inbox/")


def test_save_brainstorm_overwrite():
    save_brainstorm("Overwrite Me", "first", area="00-Inbox")
    path = save_brainstorm("Overwrite Me", "second", area="00-Inbox", overwrite=True)
    assert read(safe_path(path)) == "second"


def test_save_brainstorm_rejects_duplicate_without_overwrite():
    save_brainstorm("No Overwrite", "first", area="00-Inbox")
    with pytest.raises(FileExistsError):
        save_brainstorm("No Overwrite", "second", area="00-Inbox")
