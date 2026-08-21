"""Exercises core/vault.py's semantic-search integration points
(_auto_link, infer_area, _reindex, _reindex_move) without loading a real
sentence-transformers model: they're gated behind
_SEMANTIC_DEPS_AVAILABLE/EMBEDDINGS_DB_PATH.exists(), then call the
embeddings-module functions core.vault imported by name -- monkeypatching
those names in core.vault's own namespace exercises the real
try/except/branch logic in vault.py without needing torch inference.
"""

from pathlib import Path

import pytest

import core.vault as vault_mod
from core.vault import (
    PlacementAmbiguous,
    VAULT_PATH,
    _auto_link,
    _reindex,
    _reindex_move,
    infer_area,
    iter_markdown,
    safe_path,
)


@pytest.fixture
def semantic_enabled(monkeypatch, tmp_path):
    fake_db = tmp_path / "vault_embeddings.db"
    fake_db.write_text("")
    monkeypatch.setattr(vault_mod, "EMBEDDINGS_DB_PATH", fake_db)
    monkeypatch.setattr(vault_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(vault_mod, "get_model", lambda: "fake-model")
    monkeypatch.setattr(vault_mod, "_embeddings_connect", lambda path: _FakeConn())
    return fake_db


class _FakeConn:
    def close(self):
        pass

    def commit(self):
        pass


def test_auto_link_appends_related_notes(semantic_enabled, monkeypatch):
    monkeypatch.setattr(
        vault_mod, "_find_related",
        lambda conn, model, vault, area, text, limit, max_distance: [{"path": "00-Inbox/Related One.md"}],
    )
    result = _auto_link(VAULT_PATH / "new-note.md", "some body")
    assert "## Related notes" in result
    assert "[[Related One]]" in result


def test_auto_link_no_matches_returns_unchanged(semantic_enabled, monkeypatch):
    monkeypatch.setattr(
        vault_mod, "_find_related",
        lambda conn, model, vault, area, text, limit, max_distance: [],
    )
    result = _auto_link(VAULT_PATH / "new-note.md", "some body")
    assert result == "some body"


def test_auto_link_filters_excluded_area_matches(semantic_enabled, monkeypatch):
    monkeypatch.setattr(
        vault_mod, "_find_related",
        lambda conn, model, vault, area, text, limit, max_distance: [{"path": "01-Excluded/Secret.md"}],
    )
    result = _auto_link(VAULT_PATH / "new-note.md", "some body")
    assert result == "some body"


def test_auto_link_swallows_lookup_failure(semantic_enabled, monkeypatch):
    def _boom(path):
        raise RuntimeError("connection failed")

    monkeypatch.setattr(vault_mod, "_embeddings_connect", _boom)
    result = _auto_link(VAULT_PATH / "new-note.md", "some body")
    assert result == "some body"


def test_infer_area_returns_default_when_deps_unavailable(monkeypatch):
    monkeypatch.setattr(vault_mod, "_SEMANTIC_DEPS_AVAILABLE", False)
    default = Path("00-Inbox")
    assert infer_area("title", "content", default) == default


def test_infer_area_swallows_lookup_failure(semantic_enabled, monkeypatch):
    def _boom(path):
        raise RuntimeError("boom")

    monkeypatch.setattr(vault_mod, "_embeddings_connect", _boom)
    default = Path("00-Inbox")
    assert infer_area("title", "content", default) == default


def test_infer_area_returns_default_when_no_matches(semantic_enabled, monkeypatch):
    monkeypatch.setattr(
        vault_mod, "_find_related",
        lambda conn, model, vault, area, text, limit, max_distance: [],
    )
    default = Path("00-Inbox")
    assert infer_area("title", "content", default) == default


def test_infer_area_returns_clear_leader_folder(semantic_enabled, monkeypatch):
    monkeypatch.setattr(
        vault_mod, "_find_related",
        lambda conn, model, vault, area, text, limit, max_distance: [
            {"path": "03-Knowledge/AI/one.md"},
            {"path": "03-Knowledge/AI/two.md"},
            {"path": "03-Knowledge/AI/three.md"},
        ],
    )
    result = infer_area("title", "content", Path("00-Inbox"))
    assert result == Path("03-Knowledge/AI")


def test_infer_area_raises_when_ambiguous(semantic_enabled, monkeypatch):
    monkeypatch.setattr(
        vault_mod, "_find_related",
        lambda conn, model, vault, area, text, limit, max_distance: [
            {"path": "03-Knowledge/AI/one.md"},
            {"path": "04-Writing/two.md"},
        ],
    )
    with pytest.raises(PlacementAmbiguous):
        infer_area("title", "content", Path("00-Inbox"))


def test_reindex_calls_index_note(semantic_enabled, monkeypatch):
    calls = []
    monkeypatch.setattr(
        vault_mod, "_index_note",
        lambda conn, model, vault, path: calls.append(path),
    )
    _reindex(VAULT_PATH / "some-note.md")
    assert calls == [VAULT_PATH / "some-note.md"]


def test_reindex_swallows_failure(semantic_enabled, monkeypatch):
    def _boom(conn, model, vault, path):
        raise RuntimeError("index failed")

    monkeypatch.setattr(vault_mod, "_index_note", _boom)
    _reindex(VAULT_PATH / "some-note.md")  # must not raise


def test_reindex_move_deletes_old_and_indexes_new(semantic_enabled, monkeypatch):
    deleted = []
    indexed = []
    monkeypatch.setattr(vault_mod, "_delete_path", lambda conn, rel: deleted.append(rel))
    monkeypatch.setattr(
        vault_mod, "_index_note",
        lambda conn, model, vault, path: indexed.append(path),
    )
    old_path = VAULT_PATH / "old.md"
    new_path = VAULT_PATH / "new.md"
    _reindex_move(old_path, new_path)
    assert deleted == ["old.md"]
    assert indexed == [new_path]


def test_reindex_move_swallows_failure(semantic_enabled, monkeypatch):
    def _boom(conn, rel):
        raise RuntimeError("delete failed")

    monkeypatch.setattr(vault_mod, "_delete_path", _boom)
    _reindex_move(VAULT_PATH / "old.md", VAULT_PATH / "new.md")  # must not raise


def test_iter_markdown_skips_excluded_area_files_under_broad_root():
    excluded_note = VAULT_PATH / "01-Excluded" / "secret.md"
    excluded_note.parent.mkdir(parents=True, exist_ok=True)
    excluded_note.write_text("secret content", encoding="utf-8")
    from core.vault import write

    write(safe_path("iter-markdown-visible.md"), "visible", overwrite=True)

    results = list(iter_markdown(Path(".")))
    assert not any(p.name == "secret.md" for p in results)
    assert any(p.name == "iter-markdown-visible.md" for p in results)
