"""Workspace resolution: the taxonomy.json block, the legacy alias, and the
hot-reload contract that separates workspaces from roles.

The conftest taxonomy configures builder_projects only, so the legacy
fallback derives exactly one workspace ("Builder") unless a test writes a
workspaces block.
"""

import json
from pathlib import Path

import pytest

from core import workspaces
from core.config import TAXONOMY_JSON_PATH
from core.workspaces import WorkspaceNotConfigured


@pytest.fixture(autouse=True)
def restore_taxonomy():
    """taxonomy.json is shared with every other test module, so each test
    here puts the original bytes back."""
    original = TAXONOMY_JSON_PATH.read_bytes()
    workspaces._cache = None
    yield
    TAXONOMY_JSON_PATH.write_bytes(original)
    workspaces._cache = None


def _set_block(block: dict | None) -> None:
    data = json.loads(TAXONOMY_JSON_PATH.read_text(encoding="utf-8"))
    if block is None:
        data.pop("workspaces", None)
    else:
        data["workspaces"] = block
    TAXONOMY_JSON_PATH.write_text(json.dumps(data), encoding="utf-8")
    workspaces._cache = None


# --- legacy fallback (no workspaces block) ----------------------------------

def test_falls_back_to_roles_when_no_block():
    _set_block(None)
    assert workspaces.available() == {"Projects": Path("02-Builder/Projects")}


def test_legacy_default_is_the_first_entry():
    _set_block(None)
    assert workspaces.default_name() == "Projects"





# --- explicit workspaces block ----------------------------------------------

def test_block_replaces_the_legacy_entries():
    _set_block({"default": "Work", "entries": {"Personal": "Projects/Personal", "Work": "Projects/Work"}})
    assert set(workspaces.available()) == {"Personal", "Work"}
    assert workspaces.default_name() == "Work"


def test_resolve_uses_the_default_when_workspace_omitted():
    _set_block({"default": "Work", "entries": {"Personal": "Projects/Personal", "Work": "Projects/Work"}})
    name, folder = workspaces.resolve()
    assert (name, str(folder)) == ("Work", "Projects/Work")


def test_resolve_by_name():
    _set_block({"default": "Work", "entries": {"Personal": "Projects/Personal", "Work": "Projects/Work"}})
    name, folder = workspaces.resolve(workspace="Personal")
    assert (name, str(folder)) == ("Personal", "Projects/Personal")


def test_default_falls_back_to_first_entry_when_unset():
    _set_block({"entries": {"Alpha": "Projects/Alpha", "Beta": "Projects/Beta"}})
    assert workspaces.default_name() == "Alpha"


def test_default_falls_back_when_it_names_a_missing_entry():
    _set_block({"default": "Ghost", "entries": {"Alpha": "Projects/Alpha"}})
    assert workspaces.default_name() == "Alpha"


def test_unknown_name_lists_the_valid_ones():
    _set_block({"entries": {"Alpha": "Projects/Alpha", "Beta": "Projects/Beta"}})
    with pytest.raises(WorkspaceNotConfigured) as exc:
        workspaces.resolve(workspace="Gamma")
    assert "Alpha, Beta" in str(exc.value)




# --- reload contract ---------------------------------------------------------

def test_added_workspace_is_visible_without_restart():
    _set_block({"entries": {"Alpha": "Projects/Alpha"}})
    assert set(workspaces.available()) == {"Alpha"}

    data = json.loads(TAXONOMY_JSON_PATH.read_text(encoding="utf-8"))
    data["workspaces"]["entries"]["Beta"] = "Projects/Beta"
    TAXONOMY_JSON_PATH.write_text(json.dumps(data), encoding="utf-8")

    assert set(workspaces.available()) == {"Alpha", "Beta"}


def test_unparseable_taxonomy_keeps_the_last_known_workspaces():
    """Someone mid-save shouldn't break every write."""
    _set_block({"entries": {"Alpha": "Projects/Alpha"}})
    assert set(workspaces.available()) == {"Alpha"}

    TAXONOMY_JSON_PATH.write_text('{"workspaces": {"entries": {', encoding="utf-8")
    assert set(workspaces.available()) == {"Alpha"}


# --- reserved legacy names ---------------------------------------------------

@pytest.mark.parametrize("name", ["Builder", "builder", "Professional", "PROFESSIONAL", " professional "])
def test_reserved_names_are_rejected(name):
    with pytest.raises(workspaces.ReservedWorkspaceName, match="reserved legacy name"):
        workspaces.check_name_allowed(name)


@pytest.mark.parametrize("name", ["Personal", "Work", "Sandbox", "Builders", "Professionally"])
def test_non_reserved_names_pass(name):
    assert workspaces.check_name_allowed(name) == name


def test_resolving_a_reserved_name_gives_the_clearer_error():
    """A hand-edited taxonomy.json can't reintroduce the retired vocabulary."""
    _set_block({"entries": {"Alpha": "Projects/Alpha"}})
    with pytest.raises(workspaces.ReservedWorkspaceName):
        workspaces.resolve(workspace="Professional")


def test_grandfathered_explicit_block_still_resolves():
    """Vaults that already named a workspace Builder keep working -- the
    block applies to new additions, not existing config."""
    _set_block({"default": "Builder", "entries": {"Builder": "02-Builder/Projects"}})
    assert workspaces.resolve(workspace="Builder") == ("Builder", Path("02-Builder/Projects"))
