"""write_note -- the zero-inference write path.

Registration per mode is covered in tests/core/test_mode.py; this covers
behavior, which is identical in both modes.
"""

import shutil

import pytest

import core.policy as policy_mod
import core.vault as vault_mod
from core.tools.basic import write_note
from core.vault import VAULT_PATH


@pytest.fixture(autouse=True)
def _clean_policy():
    policy_mod._cache = None
    policy_mod.POLICY_PATH.unlink(missing_ok=True)
    yield
    policy_mod.POLICY_PATH.unlink(missing_ok=True)
    policy_mod._cache = None


@pytest.fixture
def scratch():
    folder = VAULT_PATH / "05-BasicScratch"
    folder.mkdir(exist_ok=True)
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


def test_writes_at_the_exact_path_given(scratch):
    rel = f"{scratch.name}/Some Note.md"
    assert write_note(rel, "body") == rel
    assert (scratch / "Some Note.md").read_text(encoding="utf-8") == "body"


def test_title_is_never_reinterpreted_as_a_name(scratch):
    """No auto-naming: the path is taken literally, punctuation and all."""
    rel = f"{scratch.name}/Decision - Weird: Name.md"
    write_note(rel, "body")
    assert (scratch / "Decision - Weird: Name.md").is_file()


def test_refuses_to_clobber_without_overwrite(scratch):
    rel = f"{scratch.name}/note.md"
    write_note(rel, "first")
    with pytest.raises(FileExistsError):
        write_note(rel, "second")
    assert (scratch / "note.md").read_text(encoding="utf-8") == "first"


def test_overwrite_replaces_in_place(scratch):
    rel = f"{scratch.name}/note.md"
    write_note(rel, "first")
    write_note(rel, "second", overwrite=True)
    assert (scratch / "note.md").read_text(encoding="utf-8") == "second"


@pytest.mark.parametrize("bad", ["../outside.md", "05-BasicScratch/../../outside.md"])
def test_rejects_paths_escaping_the_vault(bad):
    with pytest.raises(ValueError):
        write_note(bad, "body")


def test_rejects_excluded_areas():
    with pytest.raises(PermissionError):
        write_note("01-Excluded/note.md", "body")


def test_refuses_the_policy_file():
    with pytest.raises(PermissionError):
        write_note(policy_mod.POLICY_FILENAME, "auto_link_on_save: false")
    assert not policy_mod.POLICY_PATH.exists()


def test_never_appends_related_notes(monkeypatch, tmp_path, scratch):
    """Zero-inference means zero-inference: no footer even with an index
    available and the policy toggle left on."""
    fake_db = tmp_path / "vault_embeddings.db"
    fake_db.write_text("")
    monkeypatch.setattr(vault_mod, "EMBEDDINGS_DB_PATH", fake_db)
    monkeypatch.setattr(vault_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(vault_mod, "get_model", lambda: "fake-model")
    monkeypatch.setattr(vault_mod, "_embeddings_connect", lambda path: _FakeConn())
    monkeypatch.setattr(vault_mod, "_find_related", lambda *a, **k: [{"path": "00-Inbox/Related.md"}])

    write_note(f"{scratch.name}/note.md", "body")
    assert (scratch / "note.md").read_text(encoding="utf-8") == "body"


class _FakeConn:
    def close(self):
        pass

    def commit(self):
        pass
