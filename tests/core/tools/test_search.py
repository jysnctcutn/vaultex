import pytest

import core.tools.search as search_mod
from core.embeddings import connect, index_note
from core.tools.search import read_note, search_vaultex, semantic_search_vaultex
from core.vault import safe_path, write
from tests.core.test_embeddings import FakeModel


def test_read_note_returns_content():
    write(safe_path("search-note-1.md"), "hello world", overwrite=True)
    result = read_note("search-note-1.md")
    assert result["path"] == "search-note-1.md"
    assert result["content"] == "hello world"


def test_read_note_missing_raises():
    with pytest.raises(FileNotFoundError):
        read_note("search-does-not-exist.md")


def test_search_vaultex_matches_content():
    write(safe_path("search-note-2.md"), "the quick brown fox", overwrite=True)
    results = search_vaultex("brown fox")
    assert any(r["path"] == "search-note-2.md" for r in results)


def test_search_vaultex_matches_filename():
    write(safe_path("search-uniquename.md"), "irrelevant body", overwrite=True)
    results = search_vaultex("uniquename")
    assert any(r["path"] == "search-uniquename.md" for r in results)


def test_search_vaultex_respects_limit():
    for i in range(5):
        write(safe_path(f"search-limit-{i}.md"), "shared-limit-keyword", overwrite=True)
    results = search_vaultex("shared-limit-keyword", limit=2)
    assert len(results) == 2


def test_search_vaultex_scoped_to_areas():
    write(safe_path("03-Knowledge/scoped-note.md"), "scoped-keyword-xyz", overwrite=True)
    write(safe_path("scoped-keyword-xyz-root.md"), "scoped-keyword-xyz", overwrite=True)
    results = search_vaultex("scoped-keyword-xyz", areas=["03-Knowledge"])
    assert all(r["path"].startswith("03-Knowledge/") for r in results)
    assert any(r["path"] == "03-Knowledge/scoped-note.md" for r in results)


def test_search_vaultex_skips_unreadable_file(monkeypatch):
    write(safe_path("search-unreadable.md"), "keyword-unreadable", overwrite=True)

    import core.vault as vault_mod

    real_read = vault_mod.read

    def _boom(path):
        if path.name == "search-unreadable.md":
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad byte")
        return real_read(path)

    monkeypatch.setattr(search_mod, "read", _boom)
    results = search_vaultex("keyword-unreadable")
    assert not any(r["path"] == "search-unreadable.md" for r in results)


def test_semantic_search_raises_when_deps_unavailable(monkeypatch):
    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="dependencies aren't installed"):
        semantic_search_vaultex("anything")


def test_semantic_search_raises_when_no_index(monkeypatch, tmp_path):
    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", tmp_path / "does-not-exist.db")
    with pytest.raises(RuntimeError, match="No embeddings database"):
        semantic_search_vaultex("anything")


def test_semantic_search_returns_ranked_results(monkeypatch, tmp_path):
    db_path = tmp_path / "semantic.db"
    conn = connect(db_path)
    model = FakeModel()
    note = tmp_path / "apples.md"
    note.write_text("## Fruit\napples apples oranges fruit basket", encoding="utf-8")
    index_note(conn, model, tmp_path, note)
    conn.commit()
    conn.close()

    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", db_path)
    monkeypatch.setattr(search_mod, "get_model", lambda: model)

    results = semantic_search_vaultex("apples fruit basket", limit=5)
    assert len(results) == 1
    assert results[0]["path"] == "apples.md"
    assert results[0]["heading"] == "Fruit"
    assert "apples" in results[0]["snippet"]


def test_semantic_search_stops_once_limit_reached(monkeypatch, tmp_path):
    db_path = tmp_path / "semantic3.db"
    conn = connect(db_path)
    model = FakeModel()
    for i in range(5):
        note = tmp_path / f"note{i}.md"
        note.write_text(f"apples oranges fruit note number {i}", encoding="utf-8")
        index_note(conn, model, tmp_path, note)
    conn.commit()
    conn.close()

    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", db_path)
    monkeypatch.setattr(search_mod, "get_model", lambda: model)

    results = semantic_search_vaultex("apples oranges fruit", limit=2)
    assert len(results) == 2


def test_semantic_search_filters_excluded_area(monkeypatch, tmp_path):
    db_path = tmp_path / "semantic2.db"
    conn = connect(db_path)
    model = FakeModel()
    note_dir = tmp_path / "01-Excluded"
    note_dir.mkdir()
    note = note_dir / "secret.md"
    note.write_text("classified secret content", encoding="utf-8")
    index_note(conn, model, tmp_path, note)
    conn.commit()
    conn.close()

    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", db_path)
    monkeypatch.setattr(search_mod, "get_model", lambda: model)

    results = semantic_search_vaultex("classified secret content", limit=5)
    assert results == []
