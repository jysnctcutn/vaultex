"""App-idea capture tools."""

from ..config import VAULT_PATH
from ..mcp_app import mcp, write_tool
from ..vault import BUILDER_IDEAS, iter_markdown, read, require_role, safe_path, slug, write


@mcp.tool()
def get_app_ideas() -> list[dict]:
    """List app ideas from the configured builder-ideas folder with a short excerpt of each."""
    root = require_role(BUILDER_IDEAS, "builder_ideas")
    out = []
    for p in iter_markdown(root):
        text = read(p)
        out.append({"path": str(p.relative_to(VAULT_PATH)), "excerpt": text[:200].strip()})
    return out


@write_tool
def create_app_idea(title: str, content: str) -> str:
    """Create a new app idea note in the configured builder-ideas folder."""
    root = require_role(BUILDER_IDEAS, "builder_ideas")
    path = safe_path(root / f"{slug(title)}.md")
    return write(path, content, overwrite=False)
