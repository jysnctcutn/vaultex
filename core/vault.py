"""Vault-relative path helpers: the access-control boundary plus safe read/write.

Not a read_file/write_file/list_directory server — every tool goes through
these helpers so a new tool can't forget the excluded-areas/traversal checks.
"""

import re
from collections import Counter
from pathlib import Path

from .config import AUTO_LINK_ON_SAVE, EMBEDDINGS_DB_PATH, EXCLUDED_AREAS, VAULT_PATH, logger
from .embeddings import (
    _SEMANTIC_DEPS_AVAILABLE,
    connect as _embeddings_connect,
    delete_path as _delete_path,
    find_related as _find_related,
    get_model,
    index_note as _index_note,
)
from .policy import POLICY_FILENAME, POLICY_PATH, load as write_policy
from .taxonomy import roles

# Cosine-distance cutoff for find_related(), shared by _auto_link() and
# infer_area(). Lower = stricter match; 0.35 picked empirically.
_RELATED_MAX_DISTANCE = 0.35

# Sourced from taxonomy.json, not hardcoded: Path if the role is configured
# for this vault, else None. require_role() below turns None into a clear
# error instead of a silent no-op or silent folder creation.
PROFESSIONAL_DECISIONS = roles["professional_decisions"]
PROFESSIONAL_TECH_ANALYSIS = roles["professional_tech_analysis"]
PROFESSIONAL_ARCHITECTURE = roles["professional_architecture"]
PROFESSIONAL_PROJECTS = roles["professional_projects"]
BUILDER_IDEAS = roles["builder_ideas"]
BUILDER_PROJECTS = roles["builder_projects"]
INBOX = roles["inbox"]
EPISODIC = roles["episodic"]
OPEN_QUESTIONS = roles["open_questions"]


def top_level_area(relative: Path) -> str:
    return relative.parts[0] if relative.parts else ""


def check_area_allowed(relative: Path | str) -> Path:
    """Resolve `relative` against the vault root and enforce containment
    (inside VAULT_PATH) plus EXCLUDED_AREAS, both against the resolved
    path -- not the input string -- so '<allowed>/../<excluded>/...' can't
    walk around either check."""
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
    """A tool needs a taxonomy.json role that isn't configured for this
    vault -- avoids a read silently returning nothing, or a write silently
    creating a folder shaped for someone else's vault layout."""


def require_role(path: Path | None, role_key: str) -> Path:
    if path is None:
        raise TaxonomyNotConfigured(
            f"'{role_key}' isn't configured for this vault. Run `python3 onboard.py` to set it up."
        )
    return path


def resolve_project_subfolder(project_name: str, subfolder: str | None, allowed: list[str] | None) -> str:
    """`allowed` is taxonomy.py's project_subfolders.get(project_name).
    Unconfigured: subfolder must be omitted, keeping the flat project-root
    behavior. Configured: required, exact match -- no case-folding, so a
    mismatch is a clear error rather than a silent miss."""
    if not allowed:
        if subfolder is not None:
            raise ValueError(f"'{project_name}' has no configured subfolders in taxonomy.json; omit `subfolder`.")
        return ""
    if subfolder not in allowed:
        raise ValueError(
            f"'{project_name}' requires `subfolder` to be one of: {', '.join(allowed)}. Got: {subfolder!r}"
        )
    return subfolder


def safe_path(relative: Path | str) -> Path:
    """Resolve a vault-relative path to an absolute one, enforcing the
    same containment/EXCLUDED_AREAS checks as check_area_allowed()."""
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
    first, capped at `limit` if given -- keeps a large project's response
    within a client's context window."""
    paths = sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)
    if limit is not None:
        paths = paths[:limit]
    return [{"path": str(p.relative_to(VAULT_PATH)), "content": read(p)} for p in paths]


def _refuse_protected_path(path: Path) -> None:
    """No tool may write or move write_policy.md. Not enforced in safe_path()
    because reads go through there too, and read_note must still show it."""
    if path == POLICY_PATH:
        raise PermissionError(
            f"{POLICY_FILENAME} controls write behavior and can't be modified by a tool. "
            "Edit it directly in your vault."
        )


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
    _refuse_protected_path(path)
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
    _refuse_protected_path(old_path)
    _refuse_protected_path(new_path)
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


class PlacementAmbiguous(ValueError):
    """infer_area() found no clear leader among plausible folders. An MCP
    call can't prompt a human mid-call, so the candidates go in the error
    message instead -- caller retries save_brainstorm with an explicit
    area=."""


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
    """Keep the semantic-search index current after move() relocates a
    note -- purges the vacated old path's chunks, then indexes at the new
    path. Same no-op/never-fail-the-move contract as _reindex()."""
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


_PATH_SEPARATORS = re.compile(r"[/\\]+")


def sanitize_stem(title: str) -> str:
    """A title is a filename stem, never a path -- without this,
    create_app_idea("Auth/OAuth notes") would create a subfolder.

    Pure and unconditional: landing a note in an unintended folder is a bug,
    not a preference."""
    cleaned = _PATH_SEPARATORS.sub("-", title.strip()).strip()
    # "", "..", "---" carry no title and would make a junk or directory-like note.
    return cleaned if cleaned.strip(" .-") else "untitled"


def slug(title: str, prefix: str = "", *, strip_prefix: bool | None = None) -> str:
    """Filename stem for a note title, minus a leading `prefix` the call site
    is about to prepend itself (e.g. "Decision - ").

    strip_prefix=None consults write_policy.md; pass a bool to keep the call
    pure -- that read is the only I/O here."""
    if strip_prefix is None:
        strip_prefix = write_policy().strip_title_prefix
    stripped = title.strip()
    if prefix and strip_prefix and stripped.lower().startswith(prefix.lower()):
        stripped = stripped[len(prefix):].strip()
    return sanitize_stem(stripped)


class VerificationError(ValueError):
    """Write content failed its structural check. Message names what to
    fix -- the retry loop lives on the caller's side, not this server."""


def verify_sections(content: str, required: list[str]) -> None:
    missing = [s for s in required if s not in content]
    if missing:
        raise VerificationError(
            f"Missing required section(s): {', '.join(missing)}. "
            "Regenerate the note with all required sections and call this tool again."
        )


MAX_LIMIT = 200


def validate_limit(limit: int) -> None:
    """Every read tool's `limit` param funnels through here. Rejects rather
    than silently clamps, so a single call can't be forced to read the
    whole vault -- rate limiting alone only caps call frequency, not
    per-call cost."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= MAX_LIMIT):
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}, got: {limit!r}")
