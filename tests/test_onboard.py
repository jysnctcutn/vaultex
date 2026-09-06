"""Onboarding wizard: the shipped layout maps and the flows that write them.

Mode is no longer this script's business -- it moved to install.py, where the
30-tools-vs-4 choice is visible as a product decision rather than buried in
the taxonomy specialist. The .env writer moved with it; its tests now live in
tests/test_install.py. What's left here is the mapping work onboard.py still
owns.
"""

import json

import pytest

import onboard
from core import taxonomy
from onboard import AUTHOR_TAXONOMY, PARA_TAXONOMY, ROLES

# --- shipped layout maps ----------------------------------------------------

_PROMPTED = {key for key, _ in ROLES}          # what onboarding asks about
_VALID = set(taxonomy.ROLE_KEYS)                # what taxonomy.json accepts


@pytest.mark.parametrize("layout", [PARA_TAXONOMY, AUTHOR_TAXONOMY])
def test_layouts_only_reference_known_roles(layout):
    assert set(layout) <= _VALID


def test_prompts_never_offer_the_legacy_project_roles():
    """Project roots come from workspaces now, so a new user is never asked
    to map builder_projects / professional_projects."""
    assert "builder_projects" not in _PROMPTED
    assert "professional_projects" not in _PROMPTED


def test_prompts_carry_no_retired_vocabulary():
    blob = " ".join(f"{k} {d}" for k, d in ROLES).lower()
    assert "professional" not in blob
    assert "builder" not in blob


def test_para_layout_omits_the_project_roles():
    """Project roots come from workspaces in a fresh PARA vault, so a new
    user never meets builder_projects / professional_projects."""
    assert "builder_projects" not in PARA_TAXONOMY
    assert "professional_projects" not in PARA_TAXONOMY


def test_para_layout_puts_episodic_under_resources():
    """PARA's Archive means "inactive", which misdescribes an append-only
    agent log."""
    assert PARA_TAXONOMY["episodic"].startswith("Resources/")


def test_author_layout_covers_every_prompted_role():
    assert set(AUTHOR_TAXONOMY) == _PROMPTED


def test_author_layout_emits_no_retired_keys():
    """Choosing the author layout must not write retired vocabulary into a
    brand-new taxonomy.json — its two project roots go in as workspaces."""
    retired = {"builder_projects", "professional_projects", *taxonomy.ROLE_ALIASES}
    assert set(AUTHOR_TAXONOMY) & retired == set()


def test_author_layout_supplies_its_project_roots_as_workspaces():
    entries = onboard.AUTHOR_WORKSPACES["entries"]
    assert entries["Projects"] == "02-Builder/Projects"
    assert entries["Work"] == "01-Professional/Solution-Architecture/Projects"
    assert onboard.AUTHOR_WORKSPACES["default"] in entries


# --- flows ------------------------------------------------------------------

@pytest.fixture
def wizard(monkeypatch, tmp_path):
    """A vault and a taxonomy.json of our own, never the developer's."""
    vault = tmp_path / "vault"
    vault.mkdir()
    taxonomy_path = tmp_path / "taxonomy.json"
    monkeypatch.setattr(onboard, "BASE_DIR", tmp_path)
    monkeypatch.setattr(onboard, "TAXONOMY_PATH", taxonomy_path)
    monkeypatch.setenv("VAULTEX_PATH", str(vault))
    monkeypatch.setattr("sys.argv", ["onboard.py"])
    return vault, taxonomy_path


def _answers(monkeypatch, *values):
    it = iter(values)
    monkeypatch.setattr("builtins.input", lambda *_: next(it))


def test_the_wizard_no_longer_writes_a_mode(monkeypatch, wizard):
    """Mode belongs to install.py (§9.1). Running the taxonomy specialist
    must not reach into .env at all."""
    vault, _ = wizard
    _answers(monkeypatch, "1", "", "n")  # layout: simple; one workspace; no custom categories
    onboard.main()
    assert not (onboard.BASE_DIR / ".env").exists()


def test_simple_layout_writes_workspaces(monkeypatch, wizard):
    vault, taxonomy_path = wizard
    _answers(monkeypatch, "1", "Personal, Work", "n")

    onboard.main()

    data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    assert data["workspaces"]["default"] == "Personal"
    assert data["workspaces"]["entries"] == {
        "Personal": "Projects/Personal",
        "Work": "Projects/Work",
    }
    assert "builder_projects" not in data["roles"]
    assert (vault / "Projects" / "Work").is_dir()
    assert (vault / onboard.POLICY_FILENAME).is_file()


def test_simple_layout_records_the_preset_key(monkeypatch, wizard):
    _, taxonomy_path = wizard
    _answers(monkeypatch, "1", "", "n")
    onboard.main()
    assert json.loads(taxonomy_path.read_text(encoding="utf-8"))["preset"] == "simple"


def test_a_single_workspace_adds_no_extra_layer(monkeypatch, wizard):
    _, taxonomy_path = wizard
    _answers(monkeypatch, "1", "", "n")  # empty workspace answer

    onboard.main()

    data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    assert data["workspaces"]["entries"] == {"Projects": "Projects"}


def test_a_reserved_workspace_name_is_skipped_not_written(monkeypatch, wizard):
    _, taxonomy_path = wizard
    _answers(monkeypatch, "1", "Builder, Personal", "n")

    onboard.main()

    entries = json.loads(taxonomy_path.read_text(encoding="utf-8"))["workspaces"]["entries"]
    assert "Builder" not in entries
    assert "Personal" in entries


def test_the_author_layout_is_hidden_on_a_populated_vault(monkeypatch, wizard, capsys):
    """§9.4: pre-selecting a scaffold that creates four new top-level folders
    is wrong for someone who already has 400 notes."""
    vault, _ = wizard
    (vault / "Existing").mkdir()
    _answers(monkeypatch, "1", "", "n")

    onboard.main()

    assert "--advanced" in capsys.readouterr().out


def test_advanced_shows_the_author_layout_on_a_populated_vault(monkeypatch, wizard):
    vault, taxonomy_path = wizard
    (vault / "Existing").mkdir()
    monkeypatch.setattr("sys.argv", ["onboard.py", "--advanced"])
    _answers(monkeypatch, "3", "n")  # author's layout; no custom categories

    onboard.main()

    data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    assert data["preset"] == "author"
    assert data["roles"]["ideas"] == "02-Builder/Ideas"


def test_add_workspace_appends_without_touching_roles(monkeypatch, wizard):
    """The single-purpose command install.py's "Later" block points at."""
    vault, taxonomy_path = wizard
    taxonomy_path.write_text(json.dumps({
        "roles": {"inbox": "0-Inbox"},
        "custom_categories": [],
        "workspaces": {"default": "Projects", "entries": {"Projects": "Projects"}},
    }), encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["onboard.py", "--add-workspace"])
    _answers(monkeypatch, "Client", "")  # name, then accept the default folder

    onboard.main()

    data = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    assert data["workspaces"]["entries"]["Client"] == "Projects/Client"
    assert data["workspaces"]["default"] == "Projects"
    assert data["roles"] == {"inbox": "0-Inbox"}
    assert (vault / "Projects" / "Client").is_dir()


def test_add_workspace_refuses_a_reserved_name(monkeypatch, wizard):
    _, taxonomy_path = wizard
    monkeypatch.setattr("sys.argv", ["onboard.py", "--add-workspace"])
    _answers(monkeypatch, "Professional", "Personal", "")

    onboard.main()

    entries = json.loads(taxonomy_path.read_text(encoding="utf-8"))["workspaces"]["entries"]
    assert "Professional" not in entries
    assert "Personal" in entries
