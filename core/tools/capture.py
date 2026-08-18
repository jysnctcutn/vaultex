"""General note-capture tool (brainstorm/conversation conclusions)."""

from pathlib import Path

from ..mcp_app import write_tool
from ..vault import INBOX, infer_area, safe_path, slug, write


@write_tool
def save_brainstorm(title: str, content: str, area: str | None = None, overwrite: bool = False) -> str:
    """Save a brainstorm/conversation conclusion as a note. Without `area`,
    placement is inferred from related notes, falling back to the inbox if
    semantic search isn't set up or nothing matches closely; pass an
    explicit area like '03-Knowledge/AI' to skip inference. Raises an
    error naming the candidates if placement is genuinely ambiguous. Pass
    overwrite=True to update an existing note in place instead of
    erroring."""
    default_root = INBOX or Path("00-Inbox")
    root = Path(area) if area else infer_area(title, content, default_root)
    path = safe_path(root / f"{slug(title)}.md")
    return write(path, content, overwrite=overwrite)
