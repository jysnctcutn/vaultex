"""The vault's access-control boundary: containment, excluded areas, and
the paths no tool may write.

Every tool resolves through here so a new one can't forget the checks.
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


def _is_policy_path(path: Path) -> bool:
    """`path == POLICY_PATH` isn't enough: on a case-insensitive filesystem
    resolve() keeps the case you typed, so "Write_Policy.md" compares unequal
    yet opens the real file. samefile() also catches link aliases."""
    if path.name.casefold() == POLICY_FILENAME.casefold() and path.parent == POLICY_PATH.parent:
        return True
    try:
        return path.exists() and POLICY_PATH.exists() and path.samefile(POLICY_PATH)
    except OSError:
        return False


def refuse_protected_path(path: Path) -> None:
    """No tool may write or move write_policy.md. Not enforced in safe_path()
    because reads go through there too, and read_note must still show it."""
    if _is_policy_path(path):
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
