"""
Vaultex — Vault Embeddings Indexer

Standalone script (kept separate from server.py per the semantic search
architecture decision) that walks the vault, chunks each note, embeds the
chunks with a local sentence-transformers model, and stores the vectors in
a sqlite-vec database for semantic_search_vaultex to query.

Run:
    export VAULTEX_PATH=/path/to/vaultex
    python3 index_vault.py                # incremental: only changed notes
    python3 index_vault.py --full         # re-embed everything from scratch

The resulting vault_embeddings.db is vault-wide (no EXCLUDED_AREAS filtering
here) — area restrictions are applied at query time in server.py, the same
way _iter_markdown() filters keyword search, so one embeddings db can serve
both a full and a restricted server instance.
"""

import argparse
import os
import re
import sqlite3
from pathlib import Path

import sqlite_vec
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

# Loads VAULTEX_PATH (and friends) from a `.env` file next to this
# script, if present, so it doesn't need exporting by hand — same as server.py.
load_dotenv(Path(__file__).parent / ".env")

MODEL_NAME = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIM = 384
MAX_CHUNK_WORDS = 500

FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"(?m)^## (.+)$")


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


def delete_path(conn: sqlite3.Connection, path: str) -> None:
    ids = [r[0] for r in conn.execute("SELECT id FROM chunks WHERE path = ?", (path,))]
    if ids:
        conn.executemany("DELETE FROM vec_chunks WHERE rowid = ?", [(i,) for i in ids])
        conn.execute("DELETE FROM chunks WHERE path = ?", (path,))
    conn.execute("DELETE FROM files WHERE path = ?", (path,))


def index_note(conn: sqlite3.Connection, model: SentenceTransformer, vault_path: Path, note_path: Path) -> int:
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
    # Batched: chunks and vec_chunks must share rowids to stay joined, and
    # executemany() doesn't report a lastrowid per row, so ids are reserved
    # up front instead of inserting one row at a time to read each one back.
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault", default=os.environ.get("VAULTEX_PATH", "./vaultex"),
        help="Path to the vault (default: $VAULTEX_PATH or ./vaultex)",
    )
    parser.add_argument(
        "--db", default=os.environ.get(
            "VAULT_EMBEDDINGS_DB", str(Path(__file__).parent / "vault_embeddings.db")
        ),
        help="Path to the sqlite-vec database (default: $VAULT_EMBEDDINGS_DB or ./vault_embeddings.db)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Force a full re-index, ignoring stored mtimes",
    )
    args = parser.parse_args()

    vault_path = Path(args.vault).expanduser().resolve()
    if not vault_path.exists():
        raise SystemExit(f"Vault path does not exist: {vault_path}")

    db_path = Path(args.db).expanduser().resolve()
    conn = connect(db_path)

    print(f"Loading embedding model ({MODEL_NAME})...")
    model = SentenceTransformer(MODEL_NAME)

    stored_mtimes = dict(conn.execute("SELECT path, mtime FROM files")) if not args.full else {}
    seen_paths: set[str] = set()
    indexed_notes = 0
    indexed_chunks = 0

    for note_path in sorted(vault_path.rglob("*.md")):
        rel = str(note_path.relative_to(vault_path))
        seen_paths.add(rel)
        current_mtime = note_path.stat().st_mtime
        if not args.full and stored_mtimes.get(rel) == current_mtime:
            continue
        n = index_note(conn, model, vault_path, note_path)
        indexed_notes += 1
        indexed_chunks += n
        print(f"  indexed {rel} ({n} chunks)")

    stale_paths = set(stored_mtimes) - seen_paths
    for rel in stale_paths:
        delete_path(conn, rel)
        print(f"  removed {rel} (no longer in vault)")

    conn.commit()
    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    conn.close()

    print(
        f"\nDone. {indexed_notes} notes re-indexed ({indexed_chunks} chunks), "
        f"{len(stale_paths)} removed. Database now has {total_files} notes, "
        f"{total_chunks} chunks total. -> {db_path}"
    )


if __name__ == "__main__":
    main()
