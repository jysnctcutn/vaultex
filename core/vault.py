"""Vault helpers, re-exported for the tool layer.

The implementation lives in four focused modules -- paths (the access-control
boundary), notes (read/write plus the semantic hooks), naming, and validation.
This module keeps them behind one import so a tool author has a single door to
walk through, which is what stops a new tool forgetting the safety checks.

Import from here in tools; import the specific module when writing core code.
"""

from .config import VAULT_PATH
from .naming import sanitize_stem, slug
from .notes import (
    PlacementAmbiguous,
    _auto_link,
    _ensure_parent,
    _reindex,
    _reindex_move,
    infer_area,
    move,
    read,
    read_capped,
    write,
)
from .paths import (
    check_area_allowed,
    iter_markdown,
    refuse_protected_path,
    safe_path,
    top_level_area,
)
from .taxonomy import roles
from .validation import (
    MAX_LIMIT,
    TaxonomyNotConfigured,
    VerificationError,
    require_role,
    resolve_project_subfolder,
    validate_limit,
    verify_sections,
)

# Sourced from taxonomy.json, not hardcoded: Path if the role is configured
# for this vault, else None. require_role() turns None into a clear error
# instead of a silent no-op or silent folder creation.
PROFESSIONAL_DECISIONS = roles["professional_decisions"]
PROFESSIONAL_TECH_ANALYSIS = roles["professional_tech_analysis"]
PROFESSIONAL_ARCHITECTURE = roles["professional_architecture"]
PROFESSIONAL_PROJECTS = roles["professional_projects"]
BUILDER_IDEAS = roles["builder_ideas"]
BUILDER_PROJECTS = roles["builder_projects"]
INBOX = roles["inbox"]
EPISODIC = roles["episodic"]
OPEN_QUESTIONS = roles["open_questions"]

__all__ = [
    "BUILDER_IDEAS", "BUILDER_PROJECTS", "EPISODIC", "INBOX", "MAX_LIMIT",
    "OPEN_QUESTIONS", "PROFESSIONAL_ARCHITECTURE", "PROFESSIONAL_DECISIONS",
    "PROFESSIONAL_PROJECTS", "PROFESSIONAL_TECH_ANALYSIS", "PlacementAmbiguous",
    "TaxonomyNotConfigured", "VAULT_PATH", "VerificationError", "_auto_link",
    "_ensure_parent", "_reindex", "_reindex_move", "check_area_allowed",
    "infer_area", "iter_markdown", "move", "read", "read_capped",
    "refuse_protected_path", "require_role", "resolve_project_subfolder",
    "safe_path", "sanitize_stem", "slug", "top_level_area", "validate_limit",
    "verify_sections", "write",
]
