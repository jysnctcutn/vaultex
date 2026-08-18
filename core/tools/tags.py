"""Frontmatter (YAML properties) and tag tools. Deliberately general
(update_frontmatter works on any YAML property, not just `tags`) rather
than tag-only, since the underlying mechanism and risk profile are
identical — see core/frontmatter.py for the split/join contract. Inline
`#tag` text in the body is reported by get_tags for visibility but is
never modified by update_frontmatter, which only ever rewrites the
frontmatter block.
"""

import re

from ..frontmatter import join, split
from ..mcp_app import mcp, write_tool
from ..vault import read, safe_path, write

# Excludes a leading '#' immediately preceded by another non-space char
# (so "issue#123" or a URL fragment doesn't match) and requires the tag to
# start with a letter (so ATX headings like "# Title" and bare numeric
# refs like "#123" don't match either).
_INLINE_TAG_RE = re.compile(r"(?<!\S)#([A-Za-z][\w/-]*)")
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _normalize_tags(value) -> list[str]:
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [t.strip() for t in value.split(",") if t.strip()]
    return []


def _scan_inline_tags(body: str) -> list[str]:
    text = _CODE_FENCE_RE.sub("", body)
    return sorted({m.group(1) for m in _INLINE_TAG_RE.finditer(text)})


@mcp.tool()
def get_tags(path: str) -> dict:
    """List a note's tags: the YAML frontmatter `tags:` array plus any
    inline `#tag` mentions in the body (informational only — inline tags
    are never modified by this server). Returns the note's full
    frontmatter dict plus frontmatter_tags, inline_tags, and all_tags (the
    deduplicated union)."""
    note_path = safe_path(path)
    if not note_path.is_file():
        raise FileNotFoundError(f"No such note: {path}")
    fm, body = split(read(note_path))
    fm_tags = _normalize_tags(fm.get("tags"))
    inline_tags = _scan_inline_tags(body)
    return {
        "frontmatter": fm,
        "frontmatter_tags": fm_tags,
        "inline_tags": inline_tags,
        "all_tags": sorted(set(fm_tags) | set(inline_tags)),
    }


@write_tool
def update_frontmatter(path: str, updates: dict, merge: bool = True) -> str:
    """Create or update a note's YAML frontmatter (the `---`-delimited
    properties block Obsidian shows in its Properties panel) — status,
    tags, aliases, or any other property. Never touches the note's body.

    merge=True (default) upserts each key in `updates` into the note's
    existing frontmatter, leaving every other existing key untouched — to
    change a list-typed property like `tags`, pass the complete new list,
    not just the values to add or remove (read the current value first
    with get_tags or read_note).
    merge=False replaces the frontmatter block with exactly `updates`,
    dropping any existing key not present in it.
    """
    note_path = safe_path(path)
    if not note_path.is_file():
        raise FileNotFoundError(f"No such note: {path}")
    fm, body = split(read(note_path))
    new_fm = {**fm, **updates} if merge else dict(updates)
    return write(note_path, join(new_fm, body), overwrite=True)
