"""Vault-relative path helpers: the access-control boundary plus safe read/write.

Deliberately not a read_file/write_file/list_directory server — every tool
goes through these helpers so the excluded-areas and path-traversal checks
can't be bypassed by a new tool forgetting to call them.
"""

from collections import Counter
from pathlib import Path

from .config import AUTO_LINK_ON_SAVE, EMBEDDINGS_DB_PATH, EXCLUDED_AREAS, VAULT_PATH, logger
from .embeddings import (
    _SEMANTIC_DEPS_AVAILABLE,
    connect as _embeddings_connect,
    find_related as _find_related,
    get_model,
    index_note as _index_note,
)
from .taxonomy import roles

# Cosine-distance cutoff for find_related() lookups, shared by _auto_link()
# and infer_area() below. Lower means more similar; 0.35 was picked
# empirically to admit clearly-on-topic matches while rejecting
# merely-plausible ones. Tune it down for stricter auto-linking/placement,
# up for looser.
_RELATED_MAX_DISTANCE = 0.35

# Area roots — sourced from taxonomy.json (see core/taxonomy.py), not
# hardcoded: each is a Path if that role is configured for this vault, or
# None if it isn't. Use require_role() below to turn an unconfigured role
# into a clear error instead of a silent no-op / silent folder creation.
PROFESSIONAL_DECISIONS = roles["professional_decisions"]
PROFESSIONAL_TECH_ANALYSIS = roles["professional_tech_analysis"]
PROFESSIONAL_ARCHITECTURE = roles["professional_architecture"]
PROFESSIONAL_PROJECTS = roles["professional_projects"]
BUILDER_IDEAS = roles["builder_ideas"]
BUILDER_PROJECTS = roles["builder_projects"]
INBOX = roles["inbox"]


def top_level_area(relative: Path) -> str:
    return relative.parts[0] if relative.parts else ""


def check_area_allowed(relative: Path | str) -> Path:
    """Resolve `relative` against the vault root and enforce both
    boundaries: the result must stay inside VAULT_PATH, and its top-level
    folder must not be in EXCLUDED_AREAS. Both checks run against the
    resolved path, not the literal input string, so an
    '<allowed>/../<excluded>/...' path can't walk around either rule."""
    candidate = (VAULT_PATH / relative).resolve()
    if candidate != VAULT_PATH and VAULT_PATH not in candidate.parents:
        raise ValueError(f"Path escapes the vault: {relative}")
    area = top_level_area(candidate.relative_to(VAULT_PATH))
    if area in EXCLUDED_AREAS:
        raise PermissionError(
            f"This server instance is configured without access to '{area}'."
        )
    return candidate


class TaxonomyNotConfigured(ValueError):
    """Raised when a tool needs a taxonomy.json role that isn't configured
    for this vault. Prevents a read tool from silently returning nothing,
    or a write tool from silently creating a folder shaped for someone
    else's own vault layout."""


def require_role(path: Path | None, role_key: str) -> Path:
    if path is None:
        raise TaxonomyNotConfigured(
            f"'{role_key}' isn't configured for this vault. Run `python3 onboard.py` to set it up."
        )
    return path


def safe_path(relative: Path | str) -> Path:
    """Resolve a vault-relative path to an absolute one. Blocks paths that
    escape the vault root entirely and paths landing inside an
    EXCLUDED_AREAS folder -- see check_area_allowed() for how both checks
    are enforced against the resolved path rather than the input string."""
    return check_area_allowed(relative)


def iter_markdown(root_relative: Path):
    root = check_area_allowed(root_relative)
    if not root.exists():
        return
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(VAULT_PATH)
        if top_level_area(rel) in EXCLUDED_AREAS:
            continue
        yield p


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def read_capped(paths, limit: int | None = None) -> list[dict]:
    """Read (path, content) for each markdown path, most-recently-modified
    first. Caps at `limit` notes if given, so a project with many
    accumulated notes doesn't blow a single tool response past what a
    client's context window can hold."""
    paths = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    if limit is not None:
        paths = paths[:limit]
    return [{"path": str(p.relative_to(VAULT_PATH)), "content": read(p)} for p in paths]


def write(path: Path, content: str, overwrite: bool) -> str:
    is_new = not path.exists()
    if not is_new and not overwrite:
        raise FileExistsError(f"{path.relative_to(VAULT_PATH)} already exists; pass overwrite=True")
    if is_new:
        content = _auto_link(path, content)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _reindex(path)
    return str(path.relative_to(VAULT_PATH))


def _auto_link(path: Path, content: str) -> str:
    """Append a '## Related notes' section linking to close semantic
    matches. Only fires for brand-new notes -- write()'s is_new gate above
    means an overwrite never re-triggers this, so it can't duplicate
    across repeated edits and can't break update_frontmatter's "never
    touches the body" promise. No-op unless AUTO_LINK_ON_SAVE is enabled
    and a semantic index already exists for this vault; any lookup
    failure is logged and swallowed, never blocks the save.
    """
    if not AUTO_LINK_ON_SAVE or not _SEMANTIC_DEPS_AVAILABLE or not EMBEDDINGS_DB_PATH.exists():
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


class PlacementAmbiguous(ValueError):
    """Raised by infer_area() when existing notes split across more than
    one plausible folder with no clear leader. An MCP tool call has no
    mid-call prompt to a human, so this surfaces the candidates in the
    error message instead of guessing. The caller is expected to re-ask
    the user or retry save_brainstorm with an explicit area=."""


def infer_area(title: str, content: str, default: Path) -> Path:
    """Infer where a free-form note (save_brainstorm) belongs, by
    semantic-searching existing notes for title+content and looking at
    what folder(s) the closest matches already live in.

    Returns `default` unchanged -- no inference -- when semantic search
    isn't opted into for this vault, or when no existing note is a close
    enough match: never fabricates a new or ambiguously-named folder.
    Raises PlacementAmbiguous when the closest matches disagree across
    multiple existing top-level areas with no clear leader, instead of
    guessing.
    """
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
    # Route to the single closest match's own parent folder, not just its
    # top-level area. This puts the note in the right subfolder (e.g.
    # inside the specific project it relates to), not just the right
    # top-level bucket.
    return Path(matches[0]["path"]).parent


def _reindex(path: Path) -> None:
    """Keep the semantic-search index current on every save. Every write
    tool funnels through write() above, so this one hook covers all of
    them. It's a no-op if semantic search hasn't been set up yet (run
    `python3 index_vault.py` once to opt in), and a failure here must
    never fail the save itself.
    """
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


def slug(title: str, prefix: str = "") -> str:
    """Normalize a note title for use as a filename stem. If `prefix` is
    the exact string the call site is about to prepend (e.g. "Decision - ",
    or a taxonomy.json category's configured prefix), any leading
    occurrence of it already in `title` is stripped first. This stops a
    caller-supplied title that already includes the type prefix (e.g.
    copied from an existing note) from ending up doubled once the call
    site prepends its own copy."""
    stripped = title.strip()
    if prefix and stripped.lower().startswith(prefix.lower()):
        stripped = stripped[len(prefix):].strip()
    return stripped


class VerificationError(ValueError):
    """Raised when write content fails its structural check. The message
    tells the calling agent exactly what to fix — the retry loop lives on
    the caller's side (re-prompt, regenerate, call the tool again), not in
    this server."""


def verify_sections(content: str, required: list[str]) -> None:
    missing = [s for s in required if s not in content]
    if missing:
        raise VerificationError(
            f"Missing required section(s): {', '.join(missing)}. "
            "Regenerate the note with all required sections and call this tool again."
        )
