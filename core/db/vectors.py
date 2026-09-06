"""The semantic-search store: schema, indexing, and vector queries.

Every SQL statement against vault_embeddings.db lives here.
"""

import asyncio
import logging
import sqlite3
from pathlib import Path

from ..embeddings import chunk_note, get_model

try:
    import sqlite_vec
    _VEC_AVAILABLE = True
except ImportError:
    _VEC_AVAILABLE = False

logger = logging.getLogger(__name__)

EMBEDDING_DIM = 384

# Here rather than core/policy.py because is_indexable() needs it and this
# package stays config-free. policy.py re-exports it.
POLICY_FILENAME = "write_policy.md"


def connect(db_path: Path) -> sqlite3.Connection:
    """Every caller goes through this rather than sqlite3.connect, so no
    connection can miss the vector-extension load."""
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS files (
            path TEXT PRIMARY KEY,
            mtime REAL NOT NULL
        )"""
    )
    conn.execute(
        """CREATE TABLE IF NOT EXISTS chunks (
            id INTEGER PRIMARY KEY,
            path TEXT NOT NULL,
            heading TEXT,
            chunk_text TEXT NOT NULL
        )"""
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_path ON chunks(path)")
    conn.execute(
        f"CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(embedding float[{EMBEDDING_DIM}])"
    )
    return conn


def _encode_query(model, text: str):
    """The bge prefix the index was built with -- queries must use the same
    one or distances are meaningless."""
    return model.encode(
        f"Represent this sentence for searching relevant passages: {text}",
        normalize_embeddings=True,
    )


def find_related(conn: sqlite3.Connection, model, vault_path: Path,
                  note_path: Path | None, text: str, limit: int = 3,
                  max_distance: float = 0.35) -> list[dict]:
    """Notes semantically related to `text`, nearest first. note_path, if
    given, is excluded from its own results (pass None for a not-yet-saved
    note). Returns at most `limit` within `max_distance` cosine distance."""
    query_embedding = _encode_query(model, text[:2000])
    exclude_rel = str(note_path.relative_to(vault_path)) if note_path else None
    rows = conn.execute(
        """
        SELECT c.path, vec_distance_cosine(v.embedding, ?) AS distance
        FROM vec_chunks v JOIN chunks c ON c.id = v.rowid
        ORDER BY distance ASC
        LIMIT ?
        """,
        (sqlite_vec.serialize_float32(query_embedding.tolist()), limit * 5),
    ).fetchall()
    results: list[dict] = []
    seen: set[str] = set()
    for path, distance in rows:
        if path == exclude_rel or path in seen or distance > max_distance:
            continue
        seen.add(path)
        results.append({"path": path, "distance": distance})
        if len(results) >= limit:
            break
    return results


def semantic_query(db_path: Path, query: str, limit: int) -> list[dict]:
    """Ranked chunk hits for `query`, nearest first, one row per chunk.

    Over-fetches so the caller can drop excluded areas and de-duplicate
    without running short -- this layer knows nothing about EXCLUDED_AREAS.
    """
    query_embedding = _encode_query(get_model(), query)
    conn = connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT c.path, c.heading, c.chunk_text,
                   vec_distance_cosine(v.embedding, ?) AS distance
            FROM vec_chunks v JOIN chunks c ON c.id = v.rowid
            ORDER BY distance ASC
            LIMIT ?
            """,
            (sqlite_vec.serialize_float32(query_embedding.tolist()), limit * 3),
        ).fetchall()
    finally:
        conn.close()
    return [
        {"path": path, "heading": heading, "chunk_text": chunk_text, "distance": distance}
        for path, heading, chunk_text, distance in rows
    ]


def delete_path(conn: sqlite3.Connection, path: str) -> None:
    ids = [r[0] for r in conn.execute("SELECT id FROM chunks WHERE path = ?", (path,))]
    if ids:
        conn.executemany("DELETE FROM vec_chunks WHERE rowid = ?", [(i,) for i in ids])
        conn.execute("DELETE FROM chunks WHERE path = ?", (path,))
    conn.execute("DELETE FROM files WHERE path = ?", (path,))


def is_indexable(vault_path: Path, note_path: Path) -> bool:
    """Keep write_policy.md out of the index -- control surface, not content.
    Case-folded (a case-insensitive filesystem would otherwise index it under
    an alias) and matched against the passed vault_path, since the CLI can
    target a different vault than the server's."""
    return not (
        note_path.name.casefold() == POLICY_FILENAME.casefold()
        and note_path.parent == vault_path
    )


def index_note(conn: sqlite3.Connection, model, vault_path: Path, note_path: Path) -> int:
    if not is_indexable(vault_path, note_path):
        return 0
    rel = str(note_path.relative_to(vault_path))
    try:
        text = note_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        print(f"  skipping {rel}: unreadable ({e})")
        return 0
    delete_path(conn, rel)
    chunks = chunk_note(text)
    if not chunks:
        conn.execute(
            "INSERT INTO files (path, mtime) VALUES (?, ?)",
            (rel, note_path.stat().st_mtime),
        )
        return 0

    embeddings = model.encode(
        [c[1] for c in chunks], normalize_embeddings=True, show_progress_bar=False
    )
    # Batched: chunks and vec_chunks must share rowids to stay joined, but
    # executemany() doesn't report a lastrowid per row. IDs are reserved up
    # front instead, rather than inserting one row at a time just to read
    # each one back.
    start_id = conn.execute("SELECT COALESCE(MAX(id), 0) + 1 FROM chunks").fetchone()[0]
    conn.executemany(
        "INSERT INTO chunks (id, path, heading, chunk_text) VALUES (?, ?, ?, ?)",
        [(start_id + i, rel, heading, chunk_text)
         for i, (heading, chunk_text) in enumerate(chunks)],
    )
    conn.executemany(
        "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
        [(start_id + i, sqlite_vec.serialize_float32(embedding.tolist()))
         for i, embedding in enumerate(embeddings)],
    )
    conn.execute(
        "INSERT INTO files (path, mtime) VALUES (?, ?)",
        (rel, note_path.stat().st_mtime),
    )
    return len(chunks)


def incremental_sweep(vault_path: Path, db_path: Path, on_note=None) -> dict:
    """One pass over the vault: re-embed notes whose mtime changed, drop
    entries for notes no longer on disk (e.g. deleted in Obsidian, which the
    write-hook can't see). Shared by the CLI and the periodic sweep.

    on_note(rel, chunks) fires per (re)index, on_note(rel, None) per removal.
    """
    conn = connect(db_path)
    try:
        stored_mtimes = dict(conn.execute("SELECT path, mtime FROM files"))
        seen_paths: set[str] = set()
        indexed = 0
        indexed_chunks = 0
        for note_path in sorted(vault_path.rglob("*.md")):
            if not is_indexable(vault_path, note_path):
                continue  # not in seen_paths, so an already-indexed copy is purged as stale
            rel = str(note_path.relative_to(vault_path))
            seen_paths.add(rel)
            if stored_mtimes.get(rel) == note_path.stat().st_mtime:
                continue
            n = index_note(conn, get_model(), vault_path, note_path)
            indexed += 1
            indexed_chunks += n
            if on_note:
                on_note(rel, n)
        stale_paths = set(stored_mtimes) - seen_paths
        for rel in stale_paths:
            delete_path(conn, rel)
            if on_note:
                on_note(rel, None)
        conn.commit()
        return {"indexed": indexed, "indexed_chunks": indexed_chunks, "removed": len(stale_paths)}
    finally:
        conn.close()


async def periodic_reindex(vault_path: Path, db_path: Path, interval_seconds: int) -> None:
    """Sweep on a timer so edits made outside the MCP tools don't leave the
    index stale. Runs in a thread -- the sweep is blocking and CPU-bound."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            result = await asyncio.to_thread(incremental_sweep, vault_path, db_path)
            if result["indexed"] or result["removed"]:
                logger.info("Periodic reindex: %s", result)
        except Exception:
            logger.warning("Periodic reindex sweep failed", exc_info=True)
