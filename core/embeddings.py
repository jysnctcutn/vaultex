"""Chunking/embedding logic shared by index_vault.py (standalone bulk
re-index) and vault.write() (incremental, on every save).

Deliberately config-free — takes vault_path/db_path as explicit arguments
rather than importing core.config — so index_vault.py keeps working as a
standalone script that only needs VAULTEX_PATH, not the full server env
(MCP_AUTH_TOKEN etc.) that importing core.config would pull in.
"""

import asyncio
import logging
import re
import sqlite3
from pathlib import Path

try:
    import sqlite_vec
    from sentence_transformers import SentenceTransformer
    _SEMANTIC_DEPS_AVAILABLE = True
except ImportError:
    _SEMANTIC_DEPS_AVAILABLE = False

logger = logging.getLogger(__name__)

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
MAX_CHUNK_WORDS = 500

FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"(?m)^## (.+)$")

_model = None


def get_model() -> "SentenceTransformer":
    """Loaded once, on first use, then cached — shared by the `search` tool
    and the write-time reindex hook so the process only ever holds one copy."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def _chunk_by_words(text: str, heading: str | None, max_words: int = MAX_CHUNK_WORDS):
    text = text.strip()
    if not text:
        return []
    words = text.split()
    if len(words) <= max_words:
        return [(heading, text)]
    return [
        (heading, " ".join(words[i:i + max_words]))
        for i in range(0, len(words), max_words)
    ]


def chunk_note(text: str) -> list[tuple[str | None, str]]:
    """Chunk by ## heading first; each heading's body falls back to
    ~500-word paragraph blocks if it's still too large. Notes with no ##
    headings are chunked by paragraph blocks directly."""
    text = strip_frontmatter(text)
    headings = list(HEADING_RE.finditer(text))
    if not headings:
        return _chunk_by_words(text, None)

    chunks: list[tuple[str | None, str]] = []
    preamble = text[:headings[0].start()].strip()
    if preamble:
        chunks.extend(_chunk_by_words(preamble, None))

    for i, m in enumerate(headings):
        start = m.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        heading = m.group(1).strip()
        body = text[start:end].strip()
        chunks.extend(_chunk_by_words(body, heading))
    return chunks


def connect(db_path: Path) -> sqlite3.Connection:
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


def find_related(conn: sqlite3.Connection, model: "SentenceTransformer", vault_path: Path,
                  note_path: Path | None, text: str, limit: int = 3,
                  max_distance: float = 0.35) -> list[dict]:
    """Semantic-search the existing index for notes related to `text`.
    note_path, if given, is excluded from its own results (pass None for a
    not-yet-saved note). Returns at most `limit` notes within
    `max_distance` cosine distance (lower = more similar); mirrors
    _semantic_search's query shape in core/tools/search.py, just factored
    out for reuse from core/vault.py.
    """
    query_embedding = model.encode(
        f"Represent this sentence for searching relevant passages: {text[:2000]}",
        normalize_embeddings=True,
    )
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


def delete_path(conn: sqlite3.Connection, path: str) -> None:
    ids = [r[0] for r in conn.execute("SELECT id FROM chunks WHERE path = ?", (path,))]
    if ids:
        conn.executemany("DELETE FROM vec_chunks WHERE rowid = ?", [(i,) for i in ids])
        conn.execute("DELETE FROM chunks WHERE path = ?", (path,))
    conn.execute("DELETE FROM files WHERE path = ?", (path,))


def index_note(conn: sqlite3.Connection, model: "SentenceTransformer", vault_path: Path, note_path: Path) -> int:
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
    """One incremental pass over the whole vault: re-embed any note whose
    mtime has changed since it was last indexed, and drop entries for notes
    no longer on disk (e.g. deleted directly in Obsidian, outside any MCP
    tool the write-hook in core/vault.py could see). Shared by
    index_vault.py's CLI and the periodic background sweep below, so
    there's one tested implementation instead of two.

    on_note, if given, is called on_note(rel_path, chunks) after each note
    is (re)indexed, and on_note(rel_path, None) for each removed stale path
    — lets a caller (the CLI) report progress without duplicating the
    walk/diff loop.
    """
    conn = connect(db_path)
    try:
        stored_mtimes = dict(conn.execute("SELECT path, mtime FROM files"))
        seen_paths: set[str] = set()
        indexed = 0
        indexed_chunks = 0
        for note_path in sorted(vault_path.rglob("*.md")):
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
    """Background task: run incremental_sweep() on a timer for as long as
    the server is up, so notes edited or deleted outside the MCP tools
    don't leave the semantic index stale indefinitely. Runs the sweep in a
    thread (it's blocking and CPU-bound) so it never stalls concurrent
    request handling on the same event loop."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            result = await asyncio.to_thread(incremental_sweep, vault_path, db_path)
            if result["indexed"] or result["removed"]:
                logger.info("Periodic reindex: %s", result)
        except Exception:
            logger.warning("Periodic reindex sweep failed", exc_info=True)
