"""Vault search tools: `search` (RRF hybrid, the default) and `grep` (substring)."""

from pathlib import Path

from ..config import EMBEDDINGS_DB_PATH, EXCLUDED_AREAS, SEARCH_LOG, VAULT_PATH, logger
from ..db import log_search_event, semantic_query
from ..embeddings import _SEMANTIC_DEPS_AVAILABLE
from ..mcp_app import mcp
from ..vault import iter_markdown, read, safe_path, top_level_area, validate_limit

# RRF rank-bias constant; 60 is the value from the original RRF paper.
RRF_K = 60


@mcp.tool()
def read_note(path: str) -> dict:
    """Read the full, verbatim content of a single note by its vault-relative
    path (as returned by `search`, e.g. "03-Knowledge/AI/Some Note.md").

    Use this instead of relying on `search`'s snippets whenever you need a
    note's actual content rather than a match excerpt.
    """
    note_path = safe_path(path)
    if not note_path.is_file():
        raise FileNotFoundError(f"No such note: {path}")
    return {"path": str(note_path.relative_to(VAULT_PATH)), "content": read(note_path)}


@mcp.tool()
def grep(query: str, areas: list[str] | None = None, limit: int = 20) -> list[dict]:
    """Literal substring search over note titles and content — no ranking,
    no embeddings. Use it for exact strings (error messages, config keys,
    identifiers); use `search` for everything else.

    areas optionally restricts to top-level folders, e.g. ["02-Builder",
    "03-Knowledge"]. Excluded areas are never returned regardless of `areas`.
    """
    validate_limit(limit)
    return _grep(query, areas, limit)


def _grep(query: str, areas: list[str] | None, limit: int) -> list[dict]:
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


def _semantic_search(query: str, limit: int) -> list[dict]:
    """Meaning-based retrieval against vault_embeddings.db. Internal helper
    for `search` and core/vault.py's auto-linking, not its own tool.
    Requires the index (`python3 index_vault.py`).
    """
    validate_limit(limit)
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

    rows = semantic_query(EMBEDDINGS_DB_PATH, query, limit)

    results: list[dict] = []
    seen_paths: set[str] = set()
    for row in rows:
        path = row["path"]
        if top_level_area(Path(path)) in EXCLUDED_AREAS or path in seen_paths:
            continue
        seen_paths.add(path)
        results.append({
            "path": path,
            "heading": row["heading"],
            "snippet": row["chunk_text"][:180].strip(),
            "distance": row["distance"],
        })
        if len(results) >= limit:
            break
    return results


@mcp.tool()
def search(query: str, areas: list[str] | None = None, limit: int = 10) -> list[dict]:
    """Default search tool. Runs keyword and semantic retrieval, merges
    them with Reciprocal Rank Fusion (k=60), de-duplicates by path. Each
    result carries `score` (higher = better) and `sources` (["keyword"],
    ["semantic"], or both). `areas` restricts to top-level folders.

    Soft-fails to keyword-only when the embeddings index isn't built. Use
    `grep` for exact-string lookups.
    """
    validate_limit(limit)

    # Fuse deeper lists than `limit` so ranks past the top-N still count.
    pool = min(200, max(limit * 5, 50))

    keyword_results = _grep(query, areas, pool)

    semantic_ran = _SEMANTIC_DEPS_AVAILABLE and EMBEDDINGS_DB_PATH.exists()
    semantic_results: list[dict] = []
    if semantic_ran:
        semantic_results = _semantic_search(query, pool)
        if areas:
            prefixes = tuple(f"{a.rstrip('/')}/" for a in areas)
            semantic_results = [r for r in semantic_results if r["path"].startswith(prefixes)]

    scores: dict[str, float] = {}
    snippets: dict[str, str] = {}
    headings: dict[str, str | None] = {}
    sources: dict[str, set[str]] = {}

    def _fuse(rows: list[dict], label: str) -> None:
        for rank, row in enumerate(rows, start=1):
            path = row["path"]
            scores[path] = scores.get(path, 0.0) + 1.0 / (RRF_K + rank)
            sources.setdefault(path, set()).add(label)
            if row.get("snippet"):
                snippets.setdefault(path, row["snippet"])
            if row.get("heading") is not None:
                headings.setdefault(path, row["heading"])

    # Keyword first, so its query-anchored snippet wins the setdefault.
    _fuse(keyword_results, "keyword")
    _fuse(semantic_results, "semantic")

    ranked = sorted(scores, key=lambda p: (-scores[p], p))
    results = [
        {
            "path": path,
            "heading": headings.get(path),
            "snippet": snippets.get(path, ""),
            "score": round(scores[path], 6),
            "sources": sorted(sources[path]),
        }
        for path in ranked[:limit]
    ]

    if SEARCH_LOG:
        try:
            log_search_event(EMBEDDINGS_DB_PATH, query, limit, areas, not semantic_ran, results)
        except Exception:
            logger.debug("search_events logging failed", exc_info=True)

    return results
