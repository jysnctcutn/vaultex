"""write_policy.md's toggles wired into core/notes.py and core/naming.py,
plus the two fixes that ride along with them: slug() filename sanitization
and the guard that stops any tool writing the policy file itself.

Follows test_notes_semantic_hooks.py's approach for the semantic-gated
paths -- monkeypatch the embeddings names in core.notes' own namespace so
the real branch logic runs without loading a model.
"""

import shutil
from pathlib import Path

import pytest

import core.policy as policy_mod
import core.notes as notes_mod
from core.embeddings import is_indexable
from core.vault import (
    PlacementAmbiguous,
    VAULT_PATH,
    _auto_link,
    infer_area,
    move,
    safe_path,
    sanitize_stem,
    slug,
    write,
)


@pytest.fixture(autouse=True)
def _clean_policy():
    policy_mod._cache = None
    policy_mod.POLICY_PATH.unlink(missing_ok=True)
    yield
    policy_mod.POLICY_PATH.unlink(missing_ok=True)
    policy_mod._cache = None


def _write_policy_file(**toggles) -> None:
    body = "".join(f"{k}: {str(v).lower()}\n" for k, v in toggles.items())
    policy_mod.POLICY_PATH.write_text(f"---\n{body}---\n", encoding="utf-8")
    policy_mod._cache = None


@pytest.fixture
def semantic_enabled(monkeypatch, tmp_path):
    fake_db = tmp_path / "vault_embeddings.db"
    fake_db.write_text("")
    monkeypatch.setattr(notes_mod, "EMBEDDINGS_DB_PATH", fake_db)
    monkeypatch.setattr(notes_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(notes_mod, "get_model", lambda: "fake-model")
    monkeypatch.setattr(notes_mod, "_embeddings_connect", lambda path: _FakeConn())
    return fake_db


class _FakeConn:
    def close(self):
        pass

    def commit(self):
        pass


@pytest.fixture
def scratch():
    """A throwaway folder inside the test vault, removed afterwards -- these
    tests need real writes to real paths, not tmp_path, because safe_path()
    only resolves inside VAULT_PATH."""
    folder = VAULT_PATH / "05-PolicyScratch"
    folder.mkdir(exist_ok=True)
    yield folder
    shutil.rmtree(folder, ignore_errors=True)


# --- create_missing_folders -------------------------------------------------

def test_missing_folder_is_created_by_default(scratch):
    target = safe_path(Path(f"{scratch.name}/deep/nested/note.md"))
    write(target, "body", overwrite=False)
    assert target.is_file()


def test_missing_folder_refused_when_toggle_off():
    _write_policy_file(create_missing_folders=False)
    target = safe_path(Path("05-PolicyTest-Off/note.md"))
    with pytest.raises(FileNotFoundError) as exc:
        write(target, "body", overwrite=False)
    assert "05-PolicyTest-Off" in str(exc.value)
    assert "create_missing_folders" in str(exc.value)
    assert not target.parent.exists(), "nothing should have been created"


def test_existing_folder_still_writes_when_toggle_off(scratch):
    _write_policy_file(create_missing_folders=False)
    target = scratch / "note.md"
    write(target, "body", overwrite=False)
    assert target.read_text(encoding="utf-8") == "body"


# --- placement_inference ----------------------------------------------------

def test_inference_off_returns_default_without_touching_semantics(semantic_enabled, monkeypatch):
    _write_policy_file(placement_inference=False)

    def _boom(*args, **kwargs):
        raise AssertionError("semantic lookup should not run when inference is off")

    monkeypatch.setattr(notes_mod, "_find_related", _boom)
    default = Path("00-Inbox")
    assert infer_area("title", "content", default) == default


def test_inference_off_never_raises_placement_ambiguous(semantic_enabled, monkeypatch):
    """The ambiguous fixture from test_vault_semantic_hooks, with the toggle
    off: turning inference off has to remove the failure mode, not just the
    guessing."""
    monkeypatch.setattr(
        notes_mod, "_find_related",
        lambda *a, **k: [
            {"path": "02-Builder/one.md"},
            {"path": "03-Knowledge/two.md"},
        ],
    )
    default = Path("00-Inbox")

    with pytest.raises(PlacementAmbiguous):
        infer_area("title", "content", default)

    _write_policy_file(placement_inference=False)
    assert infer_area("title", "content", default) == default


# --- auto_link_on_save ------------------------------------------------------

def test_auto_link_off_by_policy(semantic_enabled, monkeypatch):
    _write_policy_file(auto_link_on_save=False)
    monkeypatch.setattr(
        notes_mod, "_find_related",
        lambda *a, **k: [{"path": "00-Inbox/Related One.md"}],
    )
    assert _auto_link(VAULT_PATH / "new-note.md", "some body") == "some body"


def test_write_auto_link_false_skips_footer_even_when_policy_allows(semantic_enabled, monkeypatch, scratch):
    """The zero-inference path (write_note) bypasses auto-link regardless of
    what the policy says -- it never consults the policy at all."""
    monkeypatch.setattr(
        notes_mod, "_find_related",
        lambda *a, **k: [{"path": "00-Inbox/Related One.md"}],
    )
    linked, raw = scratch / "linked.md", scratch / "raw.md"

    write(linked, "body", overwrite=False)
    assert "## Related notes" in linked.read_text(encoding="utf-8")

    write(raw, "body", overwrite=False, auto_link=False)
    assert raw.read_text(encoding="utf-8") == "body"


# --- strip_title_prefix -----------------------------------------------------

def test_prefix_stripped_by_default():
    assert slug("Decision - My Note", prefix="Decision - ") == "My Note"


def test_prefix_kept_when_toggle_off():
    _write_policy_file(strip_title_prefix=False)
    assert slug("Decision - My Note", prefix="Decision - ") == "Decision - My Note"


# --- sanitize_stem: pure, unconditional, no policy ---------------------------

@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Auth/OAuth notes", "Auth-OAuth notes"),
        ("Auth\\OAuth notes", "Auth-OAuth notes"),
        ("a//b", "a-b"),
        ("v1.0.0 release notes", "v1.0.0 release notes"),
        ("", "untitled"),
        ("   ", "untitled"),
        ("..", "untitled"),
        ("/", "untitled"),
        ("///", "untitled"),
        (". . .", "untitled"),
    ],
)
def test_sanitize_stem(raw, expected):
    assert sanitize_stem(raw) == expected


@pytest.mark.parametrize("toggle", [True, False])
def test_slug_sanitizes_regardless_of_policy(toggle):
    _write_policy_file(strip_title_prefix=toggle)
    assert slug("Auth/OAuth notes") == "Auth-OAuth notes"


def test_slug_is_pure_when_strip_prefix_is_explicit():
    """No policy file is read on this path, so callers that already know
    don't inherit slug()'s only I/O."""
    _write_policy_file(strip_title_prefix=True)
    assert slug("Decision - X", prefix="Decision - ", strip_prefix=False) == "Decision - X"
    assert slug("Decision - X", prefix="Decision - ", strip_prefix=True) == "X"


# --- policy file is a control surface, not content --------------------------

def test_write_refuses_the_policy_file():
    policy_mod.POLICY_PATH.write_text("---\nauto_link_on_save: true\n---\n", encoding="utf-8")
    original = policy_mod.POLICY_PATH.read_text(encoding="utf-8")
    with pytest.raises(PermissionError) as exc:
        write(policy_mod.POLICY_PATH, "rewritten by an agent", overwrite=True)
    assert policy_mod.POLICY_FILENAME in str(exc.value)
    assert policy_mod.POLICY_PATH.read_text(encoding="utf-8") == original


def test_move_refuses_the_policy_file_as_source():
    policy_mod.POLICY_PATH.write_text("---\n---\n", encoding="utf-8")
    with pytest.raises(PermissionError):
        move(policy_mod.POLICY_PATH, VAULT_PATH / "00-Inbox" / "stolen.md", overwrite=False)
    assert policy_mod.POLICY_PATH.is_file()


def test_move_refuses_the_policy_file_as_destination(scratch):
    decoy = scratch / "decoy.md"
    decoy.write_text("payload", encoding="utf-8")
    with pytest.raises(PermissionError):
        move(decoy, policy_mod.POLICY_PATH, overwrite=True)
    assert not policy_mod.POLICY_PATH.exists()


def test_policy_file_is_still_readable():
    """Refused for writes, but read_note has to keep working -- an agent
    should be able to explain why a write behaved the way it did."""
    policy_mod.POLICY_PATH.write_text("---\nauto_link_on_save: false\n---\nprose\n", encoding="utf-8")
    from core.tools.search import read_note

    result = read_note(policy_mod.POLICY_FILENAME)
    assert "auto_link_on_save: false" in result["content"]


# --- indexer skips it -------------------------------------------------------

def test_policy_file_is_not_indexable():
    assert is_indexable(VAULT_PATH, VAULT_PATH / "00-Inbox" / "note.md") is True
    assert is_indexable(VAULT_PATH, policy_mod.POLICY_PATH) is False


def test_same_filename_deeper_in_the_vault_is_still_indexed():
    """Only the vault-root file is the control surface; a note that happens
    to share the name elsewhere is ordinary content."""
    nested = VAULT_PATH / "03-Knowledge" / policy_mod.POLICY_FILENAME
    assert is_indexable(VAULT_PATH, nested) is True
