"""write_note -- the zero-inference write path, registered in both modes."""

from ..mcp_app import write_tool
from ..vault import safe_path, write


@write_tool
def write_note(path: str, content: str, overwrite: bool = False) -> str:
    """Create a note at an explicit vault-relative path, e.g.
    "03-Knowledge/AI/Some Note.md". Pass overwrite=True to replace an
    existing one instead of erroring.

    Low-level and deliberately literal: no placement inference, no
    auto-naming, no required sections, no related-notes footer. Prefer
    save_decision / save_brainstorm when they fit -- they route and
    structure the note for you. Use this when you need an exact path.
    """
    return write(safe_path(path), content, overwrite=overwrite, auto_link=False)
