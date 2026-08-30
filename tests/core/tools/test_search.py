import pytest

import core.tools.search as search_mod
from core.embeddings import connect, index_note
from core.tools.search import _semantic_search, grep, read_note, search
from core.vault import VAULT_PATH, safe_path, write
from tests.core.test_embeddings import FakeModel


def _build_index(db_path, rel_paths):
    """Index existing vault notes into a fresh db, keyed by the same
    vault-relative path grep reports."""
    conn = connect(db_path)
    model = FakeModel()
    for rel in rel_paths:
        index_note(conn, model, VAULT_PATH, safe_path(rel))
    conn.commit()
    conn.close()
    return model


def test_read_note_returns_content():
    write(safe_path("search-note-1.md"), "hello world", overwrite=True)
    result = read_note("search-note-1.md")
    assert result["path"] == "search-note-1.md"
    assert result["content"] == "hello world"


def test_read_note_missing_raises():
    with pytest.raises(FileNotFoundError):
        read_note("search-does-not-exist.md")


# --- grep (literal substring) ---


def test_grep_matches_content():
    write(safe_path("search-note-2.md"), "the quick brown fox", overwrite=True)
    results = grep("brown fox")
    assert any(r["path"] == "search-note-2.md" for r in results)


def test_grep_matches_filename():
    write(safe_path("search-uniquename.md"), "irrelevant body", overwrite=True)
    results = grep("uniquename")
    assert any(r["path"] == "search-uniquename.md" for r in results)


def test_grep_respects_limit():
    for i in range(5):
        write(safe_path(f"search-limit-{i}.md"), "shared-limit-keyword", overwrite=True)
    results = grep("shared-limit-keyword", limit=2)
    assert len(results) == 2


def test_grep_validates_limit():
    with pytest.raises(ValueError, match="limit must be an integer"):
        grep("anything", limit=0)


def test_grep_scoped_to_areas():
    write(safe_path("03-Knowledge/scoped-note.md"), "scoped-keyword-xyz", overwrite=True)
    write(safe_path("scoped-keyword-xyz-root.md"), "scoped-keyword-xyz", overwrite=True)
    results = grep("scoped-keyword-xyz", areas=["03-Knowledge"])
    assert all(r["path"].startswith("03-Knowledge/") for r in results)
    assert any(r["path"] == "03-Knowledge/scoped-note.md" for r in results)


def test_grep_skips_unreadable_file(monkeypatch):
    write(safe_path("search-unreadable.md"), "keyword-unreadable", overwrite=True)

    import core.vault as vault_mod

    real_read = vault_mod.read

    def _boom(path):
        if path.name == "search-unreadable.md":
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "bad byte")
        return real_read(path)

    monkeypatch.setattr(search_mod, "read", _boom)
    results = grep("keyword-unreadable")
    assert not any(r["path"] == "search-unreadable.md" for r in results)


# --- _semantic_search (internal helper, not an exposed tool) ---


def test_semantic_search_raises_when_deps_unavailable(monkeypatch):
    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="dependencies aren't installed"):
        _semantic_search("anything", limit=10)


def test_semantic_search_raises_when_no_index(monkeypatch, tmp_path):
    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", tmp_path / "does-not-exist.db")
    with pytest.raises(RuntimeError, match="No embeddings database"):
        _semantic_search("anything", limit=10)


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

    results = _semantic_search("apples fruit basket", limit=5)
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

    results = _semantic_search("apples oranges fruit", limit=2)
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

    results = _semantic_search("classified secret content", limit=5)
    assert results == []


# --- search (RRF fusion of keyword + semantic, the default tool) ---


def test_search_validates_limit():
    with pytest.raises(ValueError, match="limit must be an integer"):
        search("anything", limit=0)


def test_search_combines_sources(monkeypatch, tmp_path):
    write(safe_path("hybrid-fruit.md"), "## Fruit\napples apples oranges fruit basket", overwrite=True)
    model = _build_index(tmp_path / "hybrid.db", ["hybrid-fruit.md"])

    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", tmp_path / "hybrid.db")
    monkeypatch.setattr(search_mod, "get_model", lambda: model)

    # The keyword half is a substring match, so the query has to appear
    # verbatim in the note for it to contribute.
    results = search("fruit basket", limit=5)
    hit = next(r for r in results if r["path"] == "hybrid-fruit.md")
    assert hit["sources"] == ["keyword", "semantic"]
    assert hit["score"] > 0
    # Fused score for a two-retriever hit beats either single 1/(k+rank).
    assert hit["score"] > 1.0 / (search_mod.RRF_K + 1)
    assert hit["heading"] == "Fruit"


def test_search_ranks_two_source_hit_above_one_source_hit(monkeypatch, tmp_path):
    write(safe_path("hybrid-both.md"), "alpha beta gamma delta", overwrite=True)
    write(safe_path("hybrid-kw-only.md"), "alpha only here", overwrite=True)
    # Only index the first note, so the second can be a keyword-only hit.
    model = _build_index(tmp_path / "rank.db", ["hybrid-both.md"])

    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", tmp_path / "rank.db")
    monkeypatch.setattr(search_mod, "get_model", lambda: model)

    results = search("alpha", limit=10)
    paths = [r["path"] for r in results]
    assert paths.index("hybrid-both.md") < paths.index("hybrid-kw-only.md")
    assert next(r for r in results if r["path"] == "hybrid-kw-only.md")["sources"] == ["keyword"]


def test_search_soft_fails_to_keyword_without_index(monkeypatch, tmp_path):
    write(safe_path("hybrid-noindex.md"), "unique-hybrid-token body", overwrite=True)
    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", tmp_path / "missing.db")

    results = search("unique-hybrid-token", limit=5)
    assert any(r["path"] == "hybrid-noindex.md" for r in results)
    assert all(r["sources"] == ["keyword"] for r in results)


def test_search_soft_fails_to_keyword_without_deps(monkeypatch):
    write(safe_path("hybrid-nodeps.md"), "another-hybrid-token body", overwrite=True)
    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", False)

    results = search("another-hybrid-token", limit=5)
    assert any(r["path"] == "hybrid-nodeps.md" for r in results)
    assert all(r["sources"] == ["keyword"] for r in results)


def test_search_respects_limit(monkeypatch):
    for i in range(5):
        write(safe_path(f"hybrid-limit-{i}.md"), "shared-hybrid-limit-kw", overwrite=True)
    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", False)

    results = search("shared-hybrid-limit-kw", limit=2)
    assert len(results) == 2


def test_search_scoped_to_areas(monkeypatch, tmp_path):
    write(safe_path("03-Knowledge/hybrid-scoped.md"), "scoped-hybrid-xyz", overwrite=True)
    write(safe_path("hybrid-scoped-root.md"), "scoped-hybrid-xyz", overwrite=True)
    model = _build_index(
        tmp_path / "scoped.db", ["03-Knowledge/hybrid-scoped.md", "hybrid-scoped-root.md"]
    )

    monkeypatch.setattr(search_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    monkeypatch.setattr(search_mod, "EMBEDDINGS_DB_PATH", tmp_path / "scoped.db")
    monkeypatch.setattr(search_mod, "get_model", lambda: model)

    results = search("scoped-hybrid-xyz", areas=["03-Knowledge"], limit=10)
    assert results
    assert all(r["path"].startswith("03-Knowledge/") for r in results)
