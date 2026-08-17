"""Keyword and semantic search tools."""

import sqlite3
from pathlib import Path

from ..config import EMBEDDINGS_DB_PATH, EXCLUDED_AREAS, VAULT_PATH, logger
from ..mcp_app import mcp
from ..vault import iter_markdown, read, safe_path, top_level_area

try:
    import sqlite_vec
    from sentence_transformers import SentenceTransformer
    _SEMANTIC_DEPS_AVAILABLE = True
except ImportError:
    _SEMANTIC_DEPS_AVAILABLE = False

EMBEDDING_MODEL_NAME = "BAAI/bge-small-en-v1.5"
# Loaded once on first semantic_search_vaultex call, then cached — kept
# lazy (rather than at import time) so a server without semantic search set
# up yet still starts cleanly.
_embed_model = None


@mcp.tool()
def read_note(path: str) -> dict:
    """Read the full, verbatim content of a single note by its vault-relative
    path (as returned by search_vaultex, e.g. "03-Knowledge/AI/Some Note.md").

    Use this instead of relying on search_vaultex's snippets whenever you
    need a note's actual content rather than a keyword-match excerpt.
    """
    note_path = safe_path(path)
    if not note_path.is_file():
        raise FileNotFoundError(f"No such note: {path}")
    return {"path": str(note_path.relative_to(VAULT_PATH)), "content": read(note_path)}


@mcp.tool()
def search_vaultex(query: str, areas: list[str] | None = None, limit: int = 20) -> list[dict]:
    """Search note titles and content across the vault.

    areas optionally restricts the search to top-level folders, e.g.
    ["02-Builder", "03-Knowledge"]. Notes under excluded areas for this
    server instance are never returned regardless of `areas`.
    """
    query_lower = query.lower()
    results: list[dict] = []
    roots = [Path(a) for a in areas] if areas else [Path(".")]
    for root in roots:
        for p in iter_markdown(root):
            try:
                text = read(p)
            except (UnicodeDecodeError, OSError) as e:
                logger.debug("Skipping unreadable file %s: %s", p, e)
                continue
            idx = text.lower().find(query_lower)
            name_hit = query_lower in p.name.lower()
            if name_hit or idx != -1:
                snippet = text[max(0, idx - 60): idx + 60].strip() if idx != -1 else text[:120].strip()
                results.append({"path": str(p.relative_to(VAULT_PATH)), "snippet": snippet})
            if len(results) >= limit:
                return results
    return results


@mcp.tool()
def semantic_search_vaultex(query: str, limit: int = 10) -> list[dict]:
    """Search vault notes by meaning rather than exact keyword match, using
    local embeddings. Same result shape as search_vaultex (path +
    snippet) — use this alongside keyword search for queries where the
    right note might not share any wording with the query.

    Requires vault_embeddings.db to exist; run `python3 index_vault.py`
    first (and after significant vault edits) to build/refresh it.
    """
    if not _SEMANTIC_DEPS_AVAILABLE:
        raise RuntimeError(
            "Semantic search dependencies aren't installed. "
            "Run: pip install sentence-transformers sqlite-vec"
        )
    if not EMBEDDINGS_DB_PATH.exists():
        raise RuntimeError(
            f"No embeddings database at {EMBEDDINGS_DB_PATH}. "
            "Run `python3 index_vault.py` first to build it."
        )

    global _embed_model
    if _embed_model is None:
        _embed_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    query_embedding = _embed_model.encode(
        f"Represent this sentence for searching relevant passages: {query}",
        normalize_embeddings=True,
    )

    conn = sqlite3.connect(EMBEDDINGS_DB_PATH)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
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

    results: list[dict] = []
    seen_paths: set[str] = set()
    for path, heading, chunk_text, distance in rows:
        if top_level_area(Path(path)) in EXCLUDED_AREAS or path in seen_paths:
            continue
        seen_paths.add(path)
        results.append({
            "path": path,
            "heading": heading,
            "snippet": chunk_text[:180].strip(),
            "distance": distance,
        })
        if len(results) >= limit:
            break
    return results
