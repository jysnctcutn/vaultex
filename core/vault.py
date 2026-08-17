"""Vault-relative path helpers: the access-control boundary plus safe read/write.

Deliberately not a read_file/write_file/list_directory server — every tool
goes through these helpers so the excluded-areas and path-traversal checks
can't be bypassed by a new tool forgetting to call them.
"""

from pathlib import Path

from .config import EXCLUDED_AREAS, VAULT_PATH
from .taxonomy import roles

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


def check_area_allowed(relative: Path) -> None:
    area = top_level_area(relative)
    if area in EXCLUDED_AREAS:
        raise PermissionError(
            f"This server instance is configured without access to '{area}'."
        )


class TaxonomyNotConfigured(ValueError):
    """Raised when a tool needs a taxonomy.json role that isn't set up for
    this vault — instead of the tool silently returning nothing (for reads)
    or silently creating a JC-shaped folder in someone else's vault (for
    writes)."""


def require_role(path: Path | None, role_key: str) -> Path:
    if path is None:
        raise TaxonomyNotConfigured(
            f"'{role_key}' isn't configured for this vault. Run `python3 onboard.py` to set it up."
        )
    return path


def safe_path(relative: Path | str) -> Path:
    """Resolve a vault-relative path, blocking traversal and excluded areas."""
    relative = Path(relative)
    check_area_allowed(relative)
    candidate = (VAULT_PATH / relative).resolve()
    if candidate != VAULT_PATH and VAULT_PATH not in candidate.parents:
        raise ValueError(f"Path escapes the vault: {relative}")
    return candidate


def iter_markdown(root_relative: Path):
    check_area_allowed(root_relative)
    root = VAULT_PATH / root_relative
    if not root.exists():
        return
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(VAULT_PATH)
        if top_level_area(rel) in EXCLUDED_AREAS:
            continue
        yield p


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write(path: Path, content: str, overwrite: bool) -> str:
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path.relative_to(VAULT_PATH)} already exists; pass overwrite=True")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path.relative_to(VAULT_PATH))


def slug(title: str) -> str:
    return title.strip()


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
