"""Resolves workspace names to project-root folders.

A workspace is a user-named project context -- "Personal", "Work",
"Sandbox" -- mapped to any folder in taxonomy.json. It replaces the binary
`professional: bool`, which leaked one particular vault's builder/work split
into five tool signatures.

Entries point at arbitrary folders rather than a fixed `Projects/<name>/`
root, so an existing vault attaches names to folders it already has instead
of moving anything.

Re-read per call, so a workspace added to taxonomy.json works without a
restart: unlike roles and custom categories, workspaces register no tools,
so nothing needs rebuilding.
"""

from pathlib import Path

from .config import TAXONOMY_JSON_PATH, logger
from .taxonomy import load_raw, roles

# Fallback for a vault with no `workspaces` block: it already has up to two
# workspaces, just spelled `professional: true/false`. Ordered so the first
# entry is the default, matching today's `professional: bool = False`.
_LEGACY_WORKSPACES = (("Builder", "builder_projects"), ("Professional", "professional_projects"))

_cache: tuple[int, dict[str, Path], str | None] | None = None


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


def resolve(workspace: str | None = None, professional: bool | None = None) -> tuple[str, Path]:
    """(name, folder) for the workspace a call should write into.

    `professional` is the deprecated alias. Passing both it and `workspace`
    is an error rather than a precedence rule: guessing which the caller
    meant would put notes somewhere they didn't ask for.
    """
    if workspace is not None and professional is not None:
        raise ValueError("Pass either `workspace` or `professional`, not both.")

    entries = available()
    if not entries:
        raise WorkspaceNotConfigured(
            "No workspaces are configured for this vault. Run `python3 onboard.py` to name one."
        )

    if professional is not None:
        # Resolves through the role, not a workspace name, so it keeps working
        # for a vault that has since named its workspaces something else.
        friendly, role_key = _LEGACY_WORKSPACES[professional]
        folder = roles.get(role_key)
        if folder is None:
            # A vault onboarded to PARA never configures these roles -- project
            # roots come from workspaces. The alias has no specific meaning
            # there, so honor the default rather than erroring about a role the
            # user was never shown.
            return resolve()
        named = next((n for n, p in entries.items() if p == folder), friendly)
        return named, folder

    name = workspace if workspace is not None else default_name()
    if name not in entries:
        raise WorkspaceNotConfigured(
            f"No workspace named {name!r}. Configured: {', '.join(sorted(entries))}."
        )
    return name, entries[name]
