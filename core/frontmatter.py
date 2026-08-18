"""Minimal YAML frontmatter split/join — pyyaml directly, not the
python-frontmatter package, so parsing stays consistent with the existing
FRONTMATTER_RE convention in core/embeddings.py and body text is never
touched outside the frontmatter block itself.
"""

import re

import yaml

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?\n)---\s*\n?", re.DOTALL)


def split(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Empty dict if there's no
    frontmatter block, it isn't valid YAML, or it isn't a mapping —
    callers treat that as "no frontmatter" rather than erroring, so a read
    never fails on a malformed/missing block."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        data = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}, text
    if not isinstance(data, dict):
        return {}, text
    return data, text[m.end():]


def join(frontmatter: dict, body: str) -> str:
    """Reconstruct file content. Omits the block entirely if `frontmatter`
    is empty (so update_frontmatter(path, {}, merge=False) can strip a
    note's frontmatter down to nothing)."""
    if not frontmatter:
        return body
    yaml_block = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=True)
    return f"---\n{yaml_block}---\n{body}"
