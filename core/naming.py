"""Turning a note title into a filename stem."""

import re

from .policy import load as write_policy

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
