"""The vault's access-control boundary.

Containment, excluded areas, and the paths no tool may write. Every tool
resolves through here so a new one can't forget the checks -- this is the
reason Vaultex isn't a read_file/write_file/list_directory server.
"""

from pathlib import Path

from .config import EXCLUDED_AREAS, VAULT_PATH
from .policy import POLICY_FILENAME, POLICY_PATH


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


def safe_path(relative: Path | str) -> Path:
    """Resolve a vault-relative path to an absolute one, enforcing the
    same containment/EXCLUDED_AREAS checks as check_area_allowed()."""
    return check_area_allowed(relative)


def refuse_protected_path(path: Path) -> None:
    """No tool may write or move write_policy.md. Not enforced in safe_path()
    because reads go through there too, and read_note must still show it."""
    if path == POLICY_PATH:
        raise PermissionError(
            f"{POLICY_FILENAME} controls write behavior and can't be modified by a tool. "
            "Edit it directly in your vault."
        )


def iter_markdown(root_relative: Path):
    root = check_area_allowed(root_relative)
    if not root.exists():
        return
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(VAULT_PATH)
        if top_level_area(rel) in EXCLUDED_AREAS:
            continue
        yield p
