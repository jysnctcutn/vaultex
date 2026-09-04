"""Onboarding wizard: the .env writer and the shipped layout maps.

_upsert_env is the only code in the project that rewrites a file holding
secrets (MCP_AUTH_TOKEN, AUTHORIZE_PASSWORD), so most of this module is
about proving it touches exactly one line and leaves the rest byte-for-byte
intact. Every test points BASE_DIR at a tmp_path -- none of them may go near
the developer's real .env.
"""

import pytest

import onboard
from core import taxonomy
from onboard import AUTHOR_TAXONOMY, PARA_TAXONOMY, ROLES, _upsert_env

SECRETS = (
    "MCP_AUTH_TOKEN=pretend-token-value\n"
    "AUTHORIZE_PASSWORD=pretend-password-value\n"
    "VAULTEX_PATH=/somewhere/vault\n"
)


@pytest.fixture
def env_file(monkeypatch, tmp_path):
    monkeypatch.setattr(onboard, "BASE_DIR", tmp_path)
    return tmp_path / ".env"


def test_creates_env_when_missing(env_file):
    _upsert_env("VAULTEX_MODE", "basic")
    assert env_file.read_text(encoding="utf-8") == "VAULTEX_MODE=basic\n"


def test_appends_without_disturbing_existing_lines(env_file):
    env_file.write_text(SECRETS, encoding="utf-8")
    _upsert_env("VAULTEX_MODE", "professional")
    assert env_file.read_text(encoding="utf-8") == SECRETS + "VAULTEX_MODE=professional\n"


def test_replaces_in_place_without_duplicating(env_file):
    env_file.write_text(SECRETS + "VAULTEX_MODE=basic\n", encoding="utf-8")
    _upsert_env("VAULTEX_MODE", "professional")
    text = env_file.read_text(encoding="utf-8")
    assert text.count("VAULTEX_MODE=") == 1
    assert text == SECRETS + "VAULTEX_MODE=professional\n"


def test_every_other_line_survives_byte_for_byte(env_file):
    """The one that matters: a rewrite must not reformat, reorder, drop, or
    re-quote anything it doesn't own."""
    original = (
        "# a comment\n"
        "MCP_AUTH_TOKEN=pretend-token-value\n"
        "\n"
        'AUTHORIZE_PASSWORD="quoted value with spaces"\n'
        "EXCLUDED_AREAS=01-Professional\n"
        "VAULTEX_MODE=basic\n"
        "# trailing comment\n"
    )
    env_file.write_text(original, encoding="utf-8")
    _upsert_env("VAULTEX_MODE", "professional")

    before = original.splitlines()
    after = env_file.read_text(encoding="utf-8").splitlines()
    assert len(before) == len(after)
    for b, a in zip(before, after, strict=True):
        if b.startswith("VAULTEX_MODE="):
            assert a == "VAULTEX_MODE=professional"
        else:
            assert a == b


def test_handles_a_file_with_no_trailing_newline(env_file):
    env_file.write_text("MCP_AUTH_TOKEN=pretend-token-value", encoding="utf-8")
    _upsert_env("VAULTEX_MODE", "basic")
    assert env_file.read_text(encoding="utf-8") == (
        "MCP_AUTH_TOKEN=pretend-token-value\nVAULTEX_MODE=basic\n"
    )


def test_does_not_match_a_key_that_merely_shares_a_prefix(env_file):
    env_file.write_text("VAULTEX_MODE_OVERRIDE=something\n", encoding="utf-8")
    _upsert_env("VAULTEX_MODE", "basic")
    text = env_file.read_text(encoding="utf-8")
    assert "VAULTEX_MODE_OVERRIDE=something\n" in text
    assert "VAULTEX_MODE=basic\n" in text


def test_tolerates_whitespace_around_an_existing_key(env_file):
    env_file.write_text("  VAULTEX_MODE = basic\n", encoding="utf-8")
    _upsert_env("VAULTEX_MODE", "professional")
    assert env_file.read_text(encoding="utf-8") == "VAULTEX_MODE=professional\n"


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


# --- the Basic flow, end to end ---------------------------------------------

def test_basic_flow_writes_mode_and_leaves_taxonomy_alone(monkeypatch, tmp_path):
    """Trying Basic must not destroy a Professional mapping you can switch
    back to, so taxonomy.json is left byte-for-byte untouched."""
    vault = tmp_path / "vault"
    vault.mkdir()
    taxonomy = tmp_path / "taxonomy.json"
    existing = '{"roles": {"inbox": "00-Inbox"}, "custom_categories": []}'
    taxonomy.write_text(existing, encoding="utf-8")

    monkeypatch.setattr(onboard, "BASE_DIR", tmp_path)
    monkeypatch.setattr(onboard, "TAXONOMY_PATH", taxonomy)
    monkeypatch.setenv("VAULTEX_PATH", str(vault))
    monkeypatch.setattr("sys.argv", ["onboard.py"])

    answers = iter(["1", "n"])  # mode: Basic; scaffold PARA: no
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    onboard.main()

    assert (tmp_path / ".env").read_text(encoding="utf-8") == "VAULTEX_MODE=basic\n"
    assert taxonomy.read_text(encoding="utf-8") == existing


def test_basic_flow_can_scaffold_para(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(onboard, "BASE_DIR", tmp_path)
    monkeypatch.setattr(onboard, "TAXONOMY_PATH", tmp_path / "taxonomy.json")
    monkeypatch.setenv("VAULTEX_PATH", str(vault))
    monkeypatch.setattr("sys.argv", ["onboard.py"])

    answers = iter(["1", "y"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    onboard.main()

    for name in onboard.PARA_FOLDERS:
        assert (vault / name).is_dir()


def test_professional_para_flow_writes_workspaces(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    taxonomy = tmp_path / "taxonomy.json"
    monkeypatch.setattr(onboard, "BASE_DIR", tmp_path)
    monkeypatch.setattr(onboard, "TAXONOMY_PATH", taxonomy)
    monkeypatch.setenv("VAULTEX_PATH", str(vault))
    monkeypatch.setattr("sys.argv", ["onboard.py"])

    # mode: Professional; layout: PARA; workspaces: two named; no custom categories
    answers = iter(["2", "1", "Personal, Work", "n"])
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    onboard.main()

    import json
    data = json.loads(taxonomy.read_text(encoding="utf-8"))
    assert data["workspaces"]["default"] == "Personal"
    assert data["workspaces"]["entries"] == {
        "Personal": "Projects/Personal",
        "Work": "Projects/Work",
    }
    assert "builder_projects" not in data["roles"]
    assert (vault / "Projects" / "Work").is_dir()
    assert (vault / onboard.POLICY_FILENAME).is_file()


def test_professional_single_workspace_adds_no_extra_layer(monkeypatch, tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    taxonomy = tmp_path / "taxonomy.json"
    monkeypatch.setattr(onboard, "BASE_DIR", tmp_path)
    monkeypatch.setattr(onboard, "TAXONOMY_PATH", taxonomy)
    monkeypatch.setenv("VAULTEX_PATH", str(vault))
    monkeypatch.setattr("sys.argv", ["onboard.py"])

    answers = iter(["2", "1", "", "n"])  # empty workspace answer
    monkeypatch.setattr("builtins.input", lambda *_: next(answers))

    onboard.main()

    import json
    data = json.loads(taxonomy.read_text(encoding="utf-8"))
    assert data["workspaces"]["entries"] == {"Projects": "Projects"}
