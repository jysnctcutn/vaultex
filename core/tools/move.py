"""Move/rename a note within the vault. Opt-in (ENABLE_NOTE_MOVE) and
gated separately from write_tool -- see core/mcp_app.py's move_tool -- since
relocate-and-possibly-overwrite is a qualitatively riskier capability than
an additive write. Move/rename only, deliberately: no delete tool exists on
this server, and this doesn't add one -- a moved note still exists, just at
a different path.
"""

from ..mcp_app import move_tool
from ..vault import move, safe_path


@move_tool
def move_note(old_path: str, new_path: str, overwrite: bool = False) -> str:
    """Move or rename a note within the vault. Both paths go through
    safe_path (traversal + EXCLUDED_AREAS enforced on both ends -- a
    restricted server instance can neither read the source nor write the
    destination if either falls inside an excluded area). Fails if
    new_path already exists unless overwrite=True, same semantics as every
    other write tool. Reindexes both the vacated old path and the new path
    if a semantic index exists.

    Common use: filing a note into a project's configured subfolder (see
    save_decision/update_feature's `subfolder` param), or moving a
    discarded/shelved note into a project's "archives" subfolder instead
    of leaving it in place or deleting it -- archived notes stay fully
    readable by every other tool, just out of the way.
    """
    src = safe_path(old_path)
    dst = safe_path(new_path)
    return move(src, dst, overwrite=overwrite)
