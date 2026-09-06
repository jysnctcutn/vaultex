"""Resolves workspace names to project-root folders.

A workspace is a user-named project context ("Personal", "Work") mapped to
any folder in taxonomy.json. Entries point at arbitrary folders, so an
existing vault attaches names to folders it already has instead of moving
anything.

Re-read per call: workspaces register no tools, so adding one needs no
restart -- unlike roles and custom categories.
"""

from pathlib import Path

from .config import TAXONOMY_JSON_PATH, logger
from .taxonomy import load_raw, roles

# Fallback for a vault with no `workspaces` block, derived from the two
# legacy project roles. First entry is the default. These labels exist only
# for un-migrated vaults and are meant to be renamed.
_LEGACY_WORKSPACES = (("Projects", "builder_projects"), ("Work", "professional_projects"))

# Retired vocabulary, blocked for new workspaces so it can't reappear under
# user control. Vaults already using them in an explicit block keep working.
RESERVED_NAMES = frozenset({"builder", "professional"})

_cache: tuple[int, dict[str, Path], str | None] | None = None


class ReservedWorkspaceName(ValueError):
    """A new workspace tried to use retired vocabulary."""


def check_name_allowed(name: str) -> str:
    """Reject a reserved name. Called by onboarding and by resolution, so a
    hand-edited taxonomy.json can't reintroduce what onboarding refuses."""
    if name.strip().casefold() in RESERVED_NAMES:
        raise ReservedWorkspaceName(
            f"{name!r} is a reserved legacy name. Choose another, e.g. 'Personal' or 'Work'."
        )
    return name


class WorkspaceNotConfigured(ValueError):
    """Named workspace isn't in taxonomy.json. The message lists the valid
    names instead of falling back to a default, so a typo can't silently
    write into the wrong project tree."""


def _legacy_entries() -> dict[str, Path]:
    return {name: roles[key] for name, key in _LEGACY_WORKSPACES if roles.get(key) is not None}


def _read() -> tuple[dict[str, Path], str | None]:
    """(entries, default_name), re-parsed only when taxonomy.json's mtime
    moves. A mid-edit unparseable file keeps serving the last good value --
    someone saving a half-typed workspace shouldn't break every write."""
    global _cache
    try:
        mtime = TAXONOMY_JSON_PATH.stat().st_mtime_ns
    except OSError:
        return _legacy_entries(), None

    if _cache is not None and _cache[0] == mtime:
        return _cache[1], _cache[2]

    try:
        block = load_raw().get("workspaces") or {}
    except (OSError, ValueError):
        logger.warning("Couldn't parse %s; keeping the last known workspaces.", TAXONOMY_JSON_PATH)
        return (_cache[1], _cache[2]) if _cache else (_legacy_entries(), None)

    entries = {name: Path(folder) for name, folder in (block.get("entries") or {}).items()}
    default = block.get("default")
    if not entries:
        entries, default = _legacy_entries(), None
    _cache = (mtime, entries, default)
    return entries, default


def available() -> dict[str, Path]:
    """Configured workspace names mapped to their vault-relative folders."""
    return dict(_read()[0])


def default_name() -> str | None:
    """Explicit `default`, else the first configured entry. None when the
    vault has no workspaces at all."""
    entries, default = _read()
    if default and default in entries:
        return default
    return next(iter(entries), None)


def resolve(workspace: str | None = None) -> tuple[str, Path]:
    """(name, folder) for the workspace a call should write into. Omit
    `workspace` for the vault's default."""
    entries = available()
    if not entries:
        raise WorkspaceNotConfigured(
            "No workspaces are configured for this vault. Run `python3 onboard.py` to name one."
        )

    name = workspace if workspace is not None else default_name()
    if name not in entries:
        # Reserved names get the clearer message; anything else lists what's valid.
        check_name_allowed(name)
        raise WorkspaceNotConfigured(
            f"No workspace named {name!r}. Configured: {', '.join(sorted(entries))}."
        )
    return name, entries[name]
