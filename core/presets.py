"""Layout presets and workspace-name rules, shared by both entry points.

Deliberately dependency-free. `install.py` imports this while running on the
bare system interpreter, before `pip install` has created the venv -- and on
Path B it runs on the *host*, where the third-party deps live inside the
container rather than alongside it. So nothing here may import dotenv, or any
core module that reaches it (which is every other one, via core/config.py).

tests/core/test_presets.py asserts that property, so it can't quietly regress
the next time one of these constants needs a friend.
"""

import ast
import shutil
import sys
from pathlib import Path

# --- Preset identity ---------------------------------------------------------

# The Easy Install & Onboarding UX decision (§9.4) requires one string to be
# shared by the taxonomy.json preset key, the README, and the on-screen label.
# Everything that needs it reads it from here rather than spelling it again.
PRESET_SIMPLE = "simple"
PRESET_AUTHOR = "author"
PRESET_MAPPED = "mapped"

# Label stem for PRESET_SIMPLE. "Standard structure" was considered and
# rejected (§9.4): it implies the alternatives are non-standard, which is
# unfair to someone mapping folders they have used for years. "Recommended"
# already does that work on screen.
SIMPLE_LABEL = "Simple structure"

PARA_FOLDERS = ["Projects", "Areas", "Resources", "Archive"]

# Project roots come from workspaces, not roles, so builder_projects and
# professional_projects are deliberately absent -- a fresh vault never meets
# that vocabulary. Episodic sits under Resources rather than Archive: PARA's
# Archive means "inactive", which misdescribes an append-only agent log.
PARA_TAXONOMY = {
    "inbox": "0-Inbox",
    "ideas": "Resources/Ideas",
    "episodic": "Resources/Episodic",
    "decisions": "Areas/Decisions",
    "architecture": "Areas/Architecture",
    "tech_analysis": "Areas/Tech-Analysis",
    "open_questions": "Areas/Open-Questions",
}

# The author's own vault layout. Not a default -- core/taxonomy.py ships with
# every role unconfigured -- but offered as an opt-in starting point.
AUTHOR_TAXONOMY = {
    "ideas": "02-Builder/Ideas",
    "decisions": "01-Professional/Solution-Architecture/Decisions",
    "tech_analysis": "01-Professional/Solution-Architecture/Gap-Analysis",
    "architecture": "01-Professional/Solution-Architecture/Architecture",
    "inbox": "00-Inbox",
    "episodic": "02-Builder/Episodic",
    "open_questions": "02-Builder/Open-Questions",
}

# The two project roots this layout used to map to builder_projects /
# professional_projects. Emitted as workspaces so choosing this option can't
# write the retired keys into a brand-new taxonomy.json.
AUTHOR_WORKSPACES = {
    "default": "Projects",
    "entries": {
        "Projects": "02-Builder/Projects",
        "Work": "01-Professional/Solution-Architecture/Projects",
    },
}

# A single unnamed workspace lives at Projects/ itself: no extra path layer
# for someone who never asked for the distinction.
DEFAULT_WORKSPACE_NAME = "Projects"
DEFAULT_WORKSPACES = {
    "default": DEFAULT_WORKSPACE_NAME,
    "entries": {DEFAULT_WORKSPACE_NAME: "Projects"},
}

POLICY_FILENAME = "write_policy.md"
POLICY_TEMPLATE_NAME = "write_policy.example.md"


# --- Reserved workspace names ------------------------------------------------

# Retired vocabulary, blocked for new workspaces so it can't reappear under
# user control. Vaults already using them in an explicit block keep working.
# This lives here rather than in core/workspaces.py (which re-exports it) so
# install.py can enforce it too without importing dotenv -- see the module
# docstring.
RESERVED_NAMES = frozenset({"builder", "professional"})


class ReservedWorkspaceName(ValueError):
    """A new workspace tried to use retired vocabulary."""


def check_name_allowed(name: str) -> str:
    """Reject a reserved name. Called by both onboarding entry points and by
    workspace resolution, so a hand-edited taxonomy.json can't reintroduce
    what onboarding refuses."""
    if name.strip().casefold() in RESERVED_NAMES:
        raise ReservedWorkspaceName(
            f"{name!r} is a reserved legacy name. Choose another, e.g. 'Personal' or 'Work'."
        )
    return name


# --- Shared scaffolding ------------------------------------------------------

def mkdirs(vault: Path, relative_paths) -> list[str]:
    """Create each vault-relative folder that doesn't exist yet. Returns the
    ones actually created, so callers can report them in their own voice --
    install.py collapses steps to one line, onboard.py prints each."""
    created = []
    for rel in relative_paths:
        target = vault / rel
        if not target.exists():
            target.mkdir(parents=True)
            created.append(str(rel))
    return created


def seed_write_policy(vault: Path, template: Path) -> bool:
    """Copy write_policy.example.md into the vault. Returns False when the
    vault already has one -- an existing policy is never overwritten, since
    it may carry hand-tuned toggles."""
    target = vault / POLICY_FILENAME
    if target.exists() or not template.exists():
        return False
    shutil.copyfile(template, target)
    return True


def imports_of(module_path: Path) -> set[str]:
    """Top-level module names imported by a source file. Used by the test that
    keeps this module dependency-free."""
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def is_stdlib_only(module_path: Path) -> bool:
    return imports_of(module_path) <= sys.stdlib_module_names
