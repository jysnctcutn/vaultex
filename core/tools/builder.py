"""App-idea capture tools."""

from ..config import VAULT_PATH
from ..mcp_app import mcp, write_tool
from ..vault import IDEAS, iter_markdown, read, require_role, safe_path, slug, validate_limit, write


@mcp.tool()
def get_app_ideas(limit: int = 10) -> list[dict]:
    """List app ideas from the configured ideas folder with a short
    excerpt of each, most-recently modified first, capped at `limit`."""
    validate_limit(limit)
    root = require_role(IDEAS, "ideas")
    paths = sorted(iter_markdown(root), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    return [{"path": str(p.relative_to(VAULT_PATH)), "excerpt": read(p)[:200].strip()} for p in paths]


@write_tool
def create_app_idea(title: str, content: str) -> str:
    """Create a new app idea note in the configured ideas folder."""
    root = require_role(IDEAS, "ideas")
    path = safe_path(root / f"{slug(title)}.md")
    return write(path, content, overwrite=False)
