"""Importing this package registers every MCP tool (the decorators run on import).

Which modules get imported is the mode boundary: in Basic mode the structured
tools are never imported, so they never register and can't appear in
tools/list at all. Not importing them *is* the mutual exclusion -- there's no
soft-failing and no second write surface stacked on the first.
"""

from ..mode import MODE, PROFESSIONAL
from . import basic, search  # noqa: F401  (search, grep, read_note, write_note)

if MODE == PROFESSIONAL:
    from . import (  # noqa: F401
        architecture,
        builder,
        capture,
        coordination,
        custom,
        distill,
        episodic,
        move,
        open_questions,
        projects,
        tags,
    )
