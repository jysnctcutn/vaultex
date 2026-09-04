"""core/db/ tests. connect()/find_related()/index_note()/etc all use the
real sqlite_vec extension (lightweight, no network) -- only the ML model is
faked, with a deterministic bag-of-words vector so cosine distance behaves
predictably without downloading a real sentence-transformers model.
"""

import re

import numpy as np
import pytest

from core.db import (
    EMBEDDING_DIM,
    connect,
    delete_path,
    find_related,
    incremental_sweep,
    index_note,
    log_search_event,
    periodic_reindex,
)

class FakeModel:
    """Deterministic bag-of-words embedding: texts sharing words end up
    close in cosine distance, texts with disjoint vocab end up near-
    orthogonal -- enough to make find_related's ordering/cutoff testable
    without a real model."""

    def encode(self, inputs, normalize_embeddings=True, show_progress_bar=False):
        if isinstance(inputs, str):
            return self._vector(inputs)
        return np.array([self._vector(t) for t in inputs])

    @staticmethod
    def _vector(text: str) -> np.ndarray:
        v = np.zeros(EMBEDDING_DIM, dtype="float32")
        for word in re.findall(r"\w+", text.lower()):
            v[hash(word) % EMBEDDING_DIM] += 1.0
        norm = np.linalg.norm(v)
        return v / norm if norm else v


@pytest.fixture
def conn(tmp_path):
    c = connect(tmp_path / "test_embeddings.db")
    yield c
    c.close()

# --- connect/index_note/find_related/delete_path ---


def test_index_note_and_delete_path(conn, tmp_path):
    note = tmp_path / "note.md"
    note.write_text("## Topic\nsome content about apples and oranges", encoding="utf-8")
    n_chunks = index_note(conn, FakeModel(), tmp_path, note)
    assert n_chunks == 1

    rows = conn.execute("SELECT COUNT(*) FROM chunks WHERE path = ?", ("note.md",)).fetchone()
    assert rows[0] == 1

    delete_path(conn, "note.md")
    rows = conn.execute("SELECT COUNT(*) FROM chunks WHERE path = ?", ("note.md",)).fetchone()
    assert rows[0] == 0


def test_index_note_unreadable_file_returns_zero(conn, tmp_path):
    note = tmp_path / "missing.md"  # never created -> OSError on read_text
    result = index_note(conn, FakeModel(), tmp_path, note)
    assert result == 0


def test_index_note_empty_note_records_file_with_zero_chunks(conn, tmp_path):
    note = tmp_path / "empty.md"
    note.write_text("   \n", encoding="utf-8")
    result = index_note(conn, FakeModel(), tmp_path, note)
    assert result == 0
    row = conn.execute("SELECT mtime FROM files WHERE path = ?", ("empty.md",)).fetchone()
    assert row is not None


def test_find_related_orders_by_distance_and_respects_limit(conn, tmp_path):
    apples = tmp_path / "apples.md"
    apples.write_text("apples apples apples fruit orchard", encoding="utf-8")
    oranges = tmp_path / "oranges.md"
    oranges.write_text("oranges citrus fruit juice", encoding="utf-8")
    cars = tmp_path / "cars.md"
    cars.write_text("cars engines wheels road", encoding="utf-8")

    model = FakeModel()
    for note in (apples, oranges, cars):
        index_note(conn, model, tmp_path, note)

    results = find_related(conn, model, tmp_path, None, "apples fruit orchard", limit=2, max_distance=1.0)
    assert results[0]["path"] == "apples.md"
    assert len(results) <= 2


def test_find_related_excludes_self_path(conn, tmp_path):
    note = tmp_path / "self.md"
    note.write_text("unique vocabulary tokens here", encoding="utf-8")
    model = FakeModel()
    index_note(conn, model, tmp_path, note)

    results = find_related(conn, model, tmp_path, note, "unique vocabulary tokens here", limit=5, max_distance=1.0)
    assert not any(r["path"] == "self.md" for r in results)


def test_find_related_respects_max_distance_cutoff(conn, tmp_path):
    note = tmp_path / "completely-unrelated.md"
    note.write_text("zzz qqq xxx yyy", encoding="utf-8")
    model = FakeModel()
    index_note(conn, model, tmp_path, note)

    results = find_related(conn, model, tmp_path, None, "apples oranges bananas", limit=5, max_distance=0.01)
    assert results == []


# --- incremental_sweep / periodic_reindex ---


def test_incremental_sweep_indexes_new_and_removes_stale(monkeypatch, tmp_path):
    import core.db.vectors as emb_mod

    monkeypatch.setattr(emb_mod, "get_model", lambda: FakeModel())

    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = tmp_path / "sweep.db"
    (vault / "keep.md").write_text("keep this content", encoding="utf-8")

    seen = []
    result = incremental_sweep(vault, db_path, on_note=lambda rel, n: seen.append((rel, n)))
    assert result["indexed"] == 1
    assert result["removed"] == 0
    assert seen == [("keep.md", 1)]

    # Second sweep with unchanged mtime should skip re-indexing entirely.
    result2 = incremental_sweep(vault, db_path)
    assert result2["indexed"] == 0

    # Delete the note on disk; next sweep should report it removed.
    (vault / "keep.md").unlink()
    result3 = incremental_sweep(vault, db_path, on_note=lambda rel, n: seen.append((rel, n)))
    assert result3["removed"] == 1
    assert ("keep.md", None) in seen


@pytest.mark.anyio
async def test_periodic_reindex_runs_sweep_on_timer_and_swallows_errors(monkeypatch):
    import asyncio

    import core.db.vectors as emb_mod

    calls = []

    def _fake_sweep(vault_path, db_path):
        calls.append((vault_path, db_path))
        if len(calls) == 2:
            raise RuntimeError("simulated sweep failure")
        return {"indexed": 1, "removed": 0}

    monkeypatch.setattr(emb_mod, "incremental_sweep", _fake_sweep)

    task = asyncio.create_task(periodic_reindex("vault", "db", interval_seconds=0.01))
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert len(calls) >= 2  # at least one success and the simulated failure, without crashing the loop


@pytest.fixture
def anyio_backend():
    return "asyncio"


# --- log_search_event (search_events table for future LTR) ---


def test_log_search_event_creates_table_and_row(tmp_path):
    import json
    import sqlite3

    db_path = tmp_path / "events.db"
    results = [
        {"path": "a.md", "score": 0.5, "sources": ["keyword", "semantic"]},
        {"path": "b.md", "score": 0.2, "sources": ["semantic"]},
    ]
    log_search_event(db_path, "my query", 10, ["02-Builder"], soft_fail=False, results=results)

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT query, limit_n, areas, soft_fail, result_count, results_json FROM search_events"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "my query"
    assert row[1] == 10
    assert json.loads(row[2]) == ["02-Builder"]
    assert row[3] == 0
    assert row[4] == 2
    logged = json.loads(row[5])
    assert [r["rank"] for r in logged] == [1, 2]
    assert logged[0]["path"] == "a.md"


def test_log_search_event_appends(tmp_path):
    import sqlite3

    db_path = tmp_path / "events.db"
    log_search_event(db_path, "q1", 5, None, soft_fail=True, results=[])
    log_search_event(db_path, "q2", 5, None, soft_fail=False, results=[])

    conn = sqlite3.connect(db_path)
    try:
        count = conn.execute("SELECT COUNT(*) FROM search_events").fetchone()[0]
    finally:
        conn.close()
    assert count == 2
