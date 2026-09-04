"""Loads write_policy.md -- the vault's opinionated-write toggles.

A vault-root Markdown note, so it edits in Obsidian. Cached on mtime, so a
change applies to the next write with no restart. Only Professional-mode
structured write tools consult it; Basic mode and write_note never do.
"""

from dataclasses import dataclass, fields

from . import frontmatter
from .config import VAULT_PATH, logger
# Defined in core/db/, which must stay config-free; re-exported here.
from .db import POLICY_FILENAME

__all__ = ["DEFAULTS", "POLICY_FILENAME", "POLICY_PATH", "WritePolicy", "load"]

POLICY_PATH = VAULT_PATH / POLICY_FILENAME


@dataclass(frozen=True)
class WritePolicy:
    """Defaults live on the fields, so a missing file and a missing key
    resolve the same way."""

    auto_link_on_save: bool = True
    placement_inference: bool = True
    strip_title_prefix: bool = True
    create_missing_folders: bool = True


DEFAULTS = WritePolicy()

# The spellings core/config.py already accepts for env vars.
_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off"}

# st_mtime_ns, not st_mtime: second resolution can miss two edits in one tick.
_cache: tuple[int, WritePolicy] | None = None


def _coerce(key: str, value: object, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    token = str(value).strip().lower()
    if token in _TRUE:
        return True
    if token in _FALSE:
        return False
    logger.warning(
        "%s: %r isn't a yes/no value for '%s'; using %s.", POLICY_FILENAME, value, key, default
    )
    return default


def _parse(text: str) -> WritePolicy:
    """Unknown keys are ignored, so the file can carry notes-to-self."""
    data, _ = frontmatter.split(text)
    return WritePolicy(**{
        f.name: _coerce(f.name, data[f.name], f.default)
        for f in fields(WritePolicy)
        if f.name in data
    })


def load() -> WritePolicy:
    """Never raises -- a mistake in the policy file must not break writes."""
    global _cache
    try:
        mtime = POLICY_PATH.stat().st_mtime_ns
    except OSError:
        _cache = None
        return DEFAULTS

    cached = _cache
    if cached is not None and cached[0] == mtime:
        return cached[1]

    try:
        text = POLICY_PATH.read_text(encoding="utf-8")
    except OSError:
        logger.warning("Couldn't read %s; using defaults.", POLICY_FILENAME, exc_info=True)
        _cache = None
        return DEFAULTS

    policy = _parse(text)
    # Single tuple assignment: a race costs a redundant parse, never a torn read.
    _cache = (mtime, policy)
    return policy
