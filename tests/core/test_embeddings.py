"""core/embeddings.py tests: chunking and the model singleton.

The DB half moved to test_db.py alongside the code, when storage was
extracted into core/db/.
"""


import core.embeddings as embeddings_mod
from core.embeddings import chunk_note, get_model, strip_frontmatter


# --- get_model caching (SentenceTransformer itself faked; never touches
# the network or loads a real model) ---


def test_get_model_loads_once_and_caches(monkeypatch):
    monkeypatch.setattr(embeddings_mod, "_model", None)
    created = []

    class _FakeSentenceTransformer:
        def __init__(self, name):
            created.append(name)

    monkeypatch.setattr(embeddings_mod, "SentenceTransformer", _FakeSentenceTransformer)

    first = get_model()
    second = get_model()

    assert first is second
    assert created == [embeddings_mod.MODEL_NAME]


# --- pure text helpers ---


def test_strip_frontmatter_removes_block():
    text = "---\ntitle: x\n---\nbody here"
    assert strip_frontmatter(text) == "body here"


def test_strip_frontmatter_noop_without_block():
    assert strip_frontmatter("just body") == "just body"


def test_chunk_note_no_headings_uses_paragraph_chunking():
    chunks = chunk_note("---\ntitle: x\n---\nSome short body text.")
    assert chunks == [(None, "Some short body text.")]


def test_chunk_note_splits_by_heading():
    text = "preamble text\n\n## First\nfirst body\n\n## Second\nsecond body"
    chunks = chunk_note(text)
    headings = [h for h, _ in chunks]
    assert "First" in headings
    assert "Second" in headings
    first_chunk = next(body for h, body in chunks if h == "First")
    assert "first body" in first_chunk


def test_chunk_note_large_section_splits_by_word_count():
    big_body = " ".join(f"word{i}" for i in range(1200))
    text = f"## Big\n{big_body}"
    chunks = chunk_note(text)
    big_chunks = [c for h, c in chunks if h == "Big"]
    assert len(big_chunks) > 1


def test_chunk_note_empty_text_returns_no_chunks():
    assert chunk_note("---\ntitle: x\n---\n   \n") == []


