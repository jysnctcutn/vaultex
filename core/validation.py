"""Input and content checks shared by the tool layer, with the errors they
raise. Each rejects with a message naming the fix -- the retry loop lives on
the caller's side, not this server.
"""

from pathlib import Path

MAX_LIMIT = 200


class TaxonomyNotConfigured(ValueError):
    """A tool needs a taxonomy.json role that isn't configured for this
    vault -- avoids a read silently returning nothing, or a write silently
    creating a folder shaped for someone else's vault layout."""


class VerificationError(ValueError):
    """Write content failed its structural check."""


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


def verify_sections(content: str, required: list[str]) -> None:
    missing = [s for s in required if s not in content]
    if missing:
        raise VerificationError(
            f"Missing required section(s): {', '.join(missing)}. "
            "Regenerate the note with all required sections and call this tool again."
        )


def validate_limit(limit: int) -> None:
    """Every read tool's `limit` funnels through here. Rejects rather than
    silently clamps, so a single call can't be forced to read the whole
    vault -- rate limiting alone caps call frequency, not per-call cost."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not (1 <= limit <= MAX_LIMIT):
        raise ValueError(f"limit must be an integer between 1 and {MAX_LIMIT}, got: {limit!r}")
