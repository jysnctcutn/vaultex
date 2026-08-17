"""General note-capture tool (brainstorm/conversation conclusions)."""

from pathlib import Path

from ..mcp_app import write_tool
from ..vault import INBOX, safe_path, slug, write


@write_tool
def save_brainstorm(title: str, content: str, area: str | None = None, overwrite: bool = False) -> str:
    """Save a brainstorm/conversation conclusion as a note. Defaults to the
    configured inbox folder (or "00-Inbox" if none is configured); pass a
    specific area like '03-Knowledge/AI' to file it directly. Pass
    overwrite=True to update an existing note in place instead of erroring."""
    root = Path(area) if area else (INBOX or Path("00-Inbox"))
    path = safe_path(root / f"{slug(title)}.md")
    return write(path, content, overwrite=overwrite)
