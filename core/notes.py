"""Reading and writing notes, plus the semantic hooks every save triggers.

All writes funnel through write()/move() so the auto-link, folder-creation,
protected-path, and reindex behavior can't be bypassed by a new tool.
"""

from collections import Counter
from pathlib import Path

from .config import AUTO_LINK_ON_SAVE, EMBEDDINGS_DB_PATH, EXCLUDED_AREAS, VAULT_PATH, logger
from .db import (
    connect as _embeddings_connect,
    delete_path as _delete_path,
    find_related as _find_related,
    index_note as _index_note,
)
from .embeddings import _SEMANTIC_DEPS_AVAILABLE, get_model
from .paths import refuse_protected_path, top_level_area
from .policy import POLICY_FILENAME, load as write_policy

# Cosine-distance cutoff for find_related(), shared by _auto_link() and
# infer_area(). Lower = stricter match; 0.35 picked empirically.
_RELATED_MAX_DISTANCE = 0.35


class PlacementAmbiguous(ValueError):
    """infer_area() found no clear leader among plausible folders. An MCP
    call can't prompt a human mid-call, so the candidates go in the error
    message instead -- caller retries save_brainstorm with an explicit
    area=."""


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_capped(paths, limit: int | None = None) -> list[dict]:
    """Read (path, content) for each markdown path, most-recently-modified
    first, capped at `limit` if given -- keeps a large project's response
    within a client's context window."""
    paths = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    if limit is not None:
        paths = paths[:limit]
    return [{"path": str(p.relative_to(VAULT_PATH)), "content": read(p)} for p in paths]


def _ensure_parent(path: Path) -> None:
    """Silent folder creation is the surprise this toggle exists for: a
    typo'd area= otherwise grows a new tree in someone else's vault."""
    if path.parent.exists():
        return
    if not write_policy().create_missing_folders:
        raise FileNotFoundError(
            f"{path.parent.relative_to(VAULT_PATH)} doesn't exist, and create_missing_folders "
            f"is off in {POLICY_FILENAME}. Create the folder first, or turn that toggle back on."
        )
    path.parent.mkdir(parents=True, exist_ok=True)


def write(path: Path, content: str, overwrite: bool, auto_link: bool = True) -> str:
    """auto_link=False is the zero-inference path (write_note); it skips the
    footer regardless of policy."""
    refuse_protected_path(path)
    is_new = not path.exists()
    if not is_new and not overwrite:
        raise FileExistsError(f"{path.relative_to(VAULT_PATH)} already exists; pass overwrite=True")
    if is_new and auto_link:
        content = _auto_link(path, content)
    _ensure_parent(path)
    path.write_text(content, encoding="utf-8")
    _reindex(path)
    return str(path.relative_to(VAULT_PATH))


def move(old_path: Path, new_path: Path, overwrite: bool) -> str:
    """Move/rename a note. Both paths must already be resolved through
    safe_path by the caller -- this function only handles the filesystem
    move and reindex, not path-safety validation."""
    refuse_protected_path(old_path)
    refuse_protected_path(new_path)
    if not old_path.is_file():
        raise FileNotFoundError(f"No such note: {old_path.relative_to(VAULT_PATH)}")
    if new_path.exists() and not overwrite:
        raise FileExistsError(f"{new_path.relative_to(VAULT_PATH)} already exists; pass overwrite=True")
    _ensure_parent(new_path)
    old_path.rename(new_path)
    _reindex_move(old_path, new_path)
    return str(new_path.relative_to(VAULT_PATH))


def _auto_link(path: Path, content: str) -> str:
    """Append a '## Related notes' footer of close semantic matches.

    New notes only (write()'s is_new gate), so it can't duplicate on edits
    or break update_frontmatter's "never touches the body" promise. Lookup
    failures are logged and swallowed -- never block the save.

    AUTO_LINK_ON_SAVE is the deprecated env predecessor, ANDed so an install
    already setting it false keeps that behavior."""
    if not AUTO_LINK_ON_SAVE or not write_policy().auto_link_on_save:
        return content
    if not _SEMANTIC_DEPS_AVAILABLE or not EMBEDDINGS_DB_PATH.exists():
        return content
    try:
        conn = _embeddings_connect(EMBEDDINGS_DB_PATH)
        try:
            related = _find_related(conn, get_model(), VAULT_PATH, None, f"{path.stem}\n\n{content}",
                                     limit=3, max_distance=_RELATED_MAX_DISTANCE)
        finally:
            conn.close()
    except Exception:
        logger.warning("Auto-link lookup failed for %s", path, exc_info=True)
        return content
    related = [r for r in related if top_level_area(Path(r["path"])) not in EXCLUDED_AREAS]
    if not related:
        return content
    links = "\n".join(f"- [[{Path(r['path']).stem}]]" for r in related)
    return f"{content.rstrip()}\n\n## Related notes\n{links}\n"


def infer_area(title: str, content: str, default: Path) -> Path:
    """Infer where a free-form note (save_brainstorm) belongs, from the
    folders its closest semantic matches live in.

    Falls back to `default` rather than fabricating a folder: no index, no
    close match, or placement_inference off. Raises PlacementAmbiguous when
    the matches disagree with no clear leader instead of guessing -- but
    never when the toggle is off, since turning inference off has to remove
    the failure mode too."""
    if not write_policy().placement_inference:
        return default
    if not _SEMANTIC_DEPS_AVAILABLE or not EMBEDDINGS_DB_PATH.exists():
        return default
    try:
        conn = _embeddings_connect(EMBEDDINGS_DB_PATH)
        try:
            matches = _find_related(conn, get_model(), VAULT_PATH, None, f"{title}\n\n{content}",
                                     limit=5, max_distance=_RELATED_MAX_DISTANCE)
        finally:
            conn.close()
    except Exception:
        logger.warning("Placement inference failed; defaulting to %s", default, exc_info=True)
        return default
    matches = [m for m in matches if top_level_area(Path(m["path"])) not in EXCLUDED_AREAS]
    if not matches:
        return default
    areas = [top_level_area(Path(m["path"])) for m in matches]
    _, leader_count = Counter(areas).most_common(1)[0]
    if leader_count / len(areas) < 0.8:
        candidates = sorted(set(areas))
        raise PlacementAmbiguous(
            f"This note could plausibly belong under any of: {', '.join(candidates)}. "
            f"Pass area=<one of these paths> to save_brainstorm to disambiguate, or "
            f"area='{default}' to use the default inbox."
        )
    # Closest match's own parent folder, not just its top-level area --
    # lands in the right project subfolder, not just the right bucket.
    return Path(matches[0]["path"]).parent


def _reindex(path: Path) -> None:
    """Keep the semantic-search index current on every save -- every write
    tool funnels through write(), so this one hook covers all of them.
    No-op until `python3 index_vault.py` has been run once; a failure
    here must never fail the save itself."""
    if not _SEMANTIC_DEPS_AVAILABLE or not EMBEDDINGS_DB_PATH.exists():
        return
    try:
        conn = _embeddings_connect(EMBEDDINGS_DB_PATH)
        try:
            _index_note(conn, get_model(), VAULT_PATH, path)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.warning("Semantic reindex failed for %s", path, exc_info=True)


def _reindex_move(old_path: Path, new_path: Path) -> None:
    """Purge the vacated path's chunks, then index at the new one. Same
    no-op/never-fail-the-move contract as _reindex()."""
    if not _SEMANTIC_DEPS_AVAILABLE or not EMBEDDINGS_DB_PATH.exists():
        return
    try:
        conn = _embeddings_connect(EMBEDDINGS_DB_PATH)
        try:
            _delete_path(conn, str(old_path.relative_to(VAULT_PATH)))
            _index_note(conn, get_model(), VAULT_PATH, new_path)
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.warning("Semantic reindex failed for move %s -> %s", old_path, new_path, exc_info=True)
