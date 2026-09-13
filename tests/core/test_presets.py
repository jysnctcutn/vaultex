"""core/presets.py is the one core module install.py may import.

install.py runs on the bare system interpreter before `pip install` has
created the venv, and on Path B it runs on the host while the third-party
deps live inside the container. So the shared presets have to stay
dependency-free -- a single `from dotenv import ...` added here would break
the installer for every new user, and only on a machine that hasn't
installed Vaultex yet, which is the one case a developer never re-tests.
"""

from pathlib import Path

import pytest

from core import presets, workspaces

REPO = Path(__file__).resolve().parents[2]


def test_presets_imports_nothing_outside_the_standard_library():
    assert presets.is_stdlib_only(REPO / "core" / "presets.py")


def test_the_installer_ui_imports_nothing_outside_the_standard_library():
    assert presets.is_stdlib_only(REPO / "setup" / "install_ui.py")


def test_the_installer_reaches_only_stdlib_presets_and_its_own_ui():
    """Anything else under core/ pulls in dotenv through core/config.py."""
    allowed = {"core", "install_ui"}
    assert presets.imports_of(REPO / "setup" / "install.py") - allowed <= set(__import__("sys").stdlib_module_names)


def test_workspaces_re_exports_the_same_rules_it_used_to_own():
    """core/workspaces.py stayed the import site for everything else in the
    project; only the definition moved."""
    assert workspaces.RESERVED_NAMES is presets.RESERVED_NAMES
    assert workspaces.check_name_allowed is presets.check_name_allowed
    assert workspaces.ReservedWorkspaceName is presets.ReservedWorkspaceName


@pytest.mark.parametrize("name", ["Builder", "builder", "Professional", "PROFESSIONAL", "  builder  "])
def test_retired_vocabulary_is_refused(name):
    with pytest.raises(presets.ReservedWorkspaceName, match="reserved legacy name"):
        presets.check_name_allowed(name)


@pytest.mark.parametrize("name", ["Personal", "Work", "Projects", "Builders"])
def test_ordinary_names_pass_through_unchanged(name):
    assert presets.check_name_allowed(name) == name


def test_the_simple_preset_key_matches_its_on_screen_label():
    """§9.4 requires the preset key, the README, and the screen label to be
    the same word."""
    assert presets.PRESET_SIMPLE == "simple"
    assert presets.SIMPLE_LABEL.lower().startswith(presets.PRESET_SIMPLE)


def test_mkdirs_reports_only_what_it_created(tmp_path):
    (tmp_path / "Areas").mkdir()
    created = presets.mkdirs(tmp_path, ["Areas", "Projects"])
    assert created == ["Projects"]
    assert (tmp_path / "Projects").is_dir()


def test_an_existing_write_policy_is_never_overwritten(tmp_path):
    """It may carry hand-tuned toggles."""
    template = tmp_path / "write_policy.example.md"
    template.write_text("template", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "write_policy.md").write_text("mine", encoding="utf-8")

    assert presets.seed_write_policy(vault, template) is False
    assert (vault / "write_policy.md").read_text(encoding="utf-8") == "mine"


def test_a_missing_policy_is_seeded_from_the_template(tmp_path):
    template = tmp_path / "write_policy.example.md"
    template.write_text("template", encoding="utf-8")
    vault = tmp_path / "vault"
    vault.mkdir()

    assert presets.seed_write_policy(vault, template) is True
    assert (vault / "write_policy.md").read_text(encoding="utf-8") == "template"
