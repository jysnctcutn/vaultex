"""The installer: its .env writer, and the taxonomy it hands a new user.

_upsert_env is the only code in install.py that rewrites a file holding
secrets (MCP_AUTH_TOKEN, TS_AUTHKEY, AUTHORIZE_PASSWORD), so most of the
first half is about proving it touches exactly one line and leaves the rest
byte-for-byte intact. Every test points ENV_PATH at a tmp_path -- none of
them may go near the developer's real .env.

The second half guards the thing that made this rewrite necessary: the old
step_taxonomy wrote builder_projects / professional_projects into a
brand-new vault, minting retired vocabulary the Role Vocabulary Cut had
already removed from onboard.py.
"""

import json

import pytest

import install
from core import taxonomy
from core.presets import PRESET_AUTHOR, PRESET_SIMPLE
from install import _upsert_env

SECRETS = (
    "MCP_AUTH_TOKEN=pretend-token-value\n"
    "AUTHORIZE_PASSWORD=pretend-password-value\n"
    "VAULTEX_PATH=/somewhere/vault\n"
)


@pytest.fixture
def env_file(tmp_path):
    return tmp_path / ".env"


# --- .env writer -------------------------------------------------------------

def test_creates_env_when_missing(env_file):
    _upsert_env(env_file, "VAULTEX_MODE", "basic")
    assert env_file.read_text(encoding="utf-8") == "VAULTEX_MODE=basic\n"


def test_appends_without_disturbing_existing_lines(env_file):
    env_file.write_text(SECRETS, encoding="utf-8")
    _upsert_env(env_file, "VAULTEX_MODE", "professional")
    assert env_file.read_text(encoding="utf-8") == SECRETS + "VAULTEX_MODE=professional\n"


def test_replaces_in_place_without_duplicating(env_file):
    env_file.write_text(SECRETS + "VAULTEX_MODE=basic\n", encoding="utf-8")
    _upsert_env(env_file, "VAULTEX_MODE", "professional")
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
    _upsert_env(env_file, "VAULTEX_MODE", "professional")
    assert env_file.read_text(encoding="utf-8") == original.replace(
        "VAULTEX_MODE=basic", "VAULTEX_MODE=professional"
    )


def test_handles_a_file_with_no_trailing_newline(env_file):
    env_file.write_text("MCP_AUTH_TOKEN=pretend-token-value", encoding="utf-8")
    _upsert_env(env_file, "VAULTEX_MODE", "basic")
    assert env_file.read_text(encoding="utf-8") == (
        "MCP_AUTH_TOKEN=pretend-token-value\nVAULTEX_MODE=basic\n"
    )


def test_does_not_match_a_key_that_merely_shares_a_prefix(env_file):
    env_file.write_text("VAULTEX_MODE_OVERRIDE=yes\n", encoding="utf-8")
    _upsert_env(env_file, "VAULTEX_MODE", "basic")
    text = env_file.read_text(encoding="utf-8")
    assert "VAULTEX_MODE_OVERRIDE=yes\n" in text
    assert "VAULTEX_MODE=basic\n" in text


def test_tolerates_whitespace_around_an_existing_key(env_file):
    env_file.write_text("  VAULTEX_MODE = basic\n", encoding="utf-8")
    _upsert_env(env_file, "VAULTEX_MODE", "professional")
    assert env_file.read_text(encoding="utf-8") == "VAULTEX_MODE=professional\n"


def test_path_b_three_write_sequence_preserves_every_other_line(env_file):
    """Decision §9.6: a remote install writes three values in one run, so the
    guarantee has to hold across the whole sequence, not just per call."""
    original = (
        "# Vaultex configuration\n"
        "MCP_AUTH_TOKEN=pretend-token-value\n"
        "VAULTEX_PATH=/somewhere/vault\n"
        "\n"
        "EXCLUDED_AREAS=01-Professional\n"
        "# end\n"
    )
    env_file.write_text(original, encoding="utf-8")

    _upsert_env(env_file, "TS_AUTHKEY", "pretend-authkey")
    _upsert_env(env_file, "AUTHORIZE_PASSWORD", "pretend-password")
    _upsert_env(env_file, "VAULTEX_MODE", "professional")

    text = env_file.read_text(encoding="utf-8")
    assert text.startswith(original)
    assert text.endswith(
        "TS_AUTHKEY=pretend-authkey\n"
        "AUTHORIZE_PASSWORD=pretend-password\n"
        "VAULTEX_MODE=professional\n"
    )


def test_crlf_line_endings_are_not_rewritten(env_file):
    """install.py explicitly supports Windows. Splitting without keepends
    silently converted a whole CRLF .env to LF on every Path B run."""
    original = "MCP_AUTH_TOKEN=pretend-token-value\r\nVAULTEX_PATH=C:\\vault\r\n"
    env_file.write_bytes(original.encode("utf-8"))
    _upsert_env(env_file, "VAULTEX_MODE", "basic")
    raw = env_file.read_bytes()
    assert b"MCP_AUTH_TOKEN=pretend-token-value\r\n" in raw
    assert b"VAULTEX_PATH=C:\\vault\r\n" in raw


def test_get_env_reads_back_what_upsert_wrote(env_file):
    _upsert_env(env_file, "OAUTH_ISSUER_URL", "https://example.ts.net")
    assert install._get_env(env_file, "OAUTH_ISSUER_URL") == "https://example.ts.net"
    assert install._get_env(env_file, "NOT_SET") is None


# --- the taxonomy a new user is handed ---------------------------------------

_RETIRED = {"builder_projects", "professional_projects", *taxonomy.ROLE_ALIASES}


@pytest.fixture
def vault(tmp_path, monkeypatch):
    v = tmp_path / "vault"
    v.mkdir()
    monkeypatch.setattr(install, "TAXONOMY_PATH", tmp_path / "taxonomy.json")
    return v


def _written(monkeypatched_path):
    return json.loads(monkeypatched_path.read_text(encoding="utf-8"))


def test_simple_preset_writes_no_retired_vocabulary(vault):
    """The regression this rewrite exists to fix: the old step_taxonomy wrote
    builder_projects and professional_projects into every new vault."""
    install._apply_simple(vault)
    data = _written(install.TAXONOMY_PATH)
    assert set(data["roles"]) & _RETIRED == set()


def test_simple_preset_records_the_agreed_key(vault):
    """§9.4: one string shared by the preset key, the README, and the screen."""
    install._apply_simple(vault)
    assert _written(install.TAXONOMY_PATH)["preset"] == PRESET_SIMPLE == "simple"


def test_simple_preset_supplies_a_workspace_and_a_write_policy(vault):
    """Both were missing from the old default path, so a user who took the
    recommended option ended up with nowhere to file a project note."""
    install._apply_simple(vault)
    data = _written(install.TAXONOMY_PATH)
    assert data["workspaces"]["entries"] == {"Projects": "Projects"}
    assert data["workspaces"]["default"] == "Projects"
    assert (vault / "write_policy.md").is_file()


def test_simple_preset_scaffolds_the_folders_it_maps(vault):
    install._apply_simple(vault)
    for name in ("Projects", "Areas", "Resources", "Archive"):
        assert (vault / name).is_dir()
    assert (vault / "Resources" / "Episodic").is_dir()


def test_author_preset_emits_its_project_roots_as_workspaces(vault):
    install._apply_author(vault)
    data = _written(install.TAXONOMY_PATH)
    assert set(data["roles"]) & _RETIRED == set()
    assert data["preset"] == PRESET_AUTHOR
    assert data["workspaces"]["entries"]["Work"] == "01-Professional/Solution-Architecture/Projects"


def test_every_written_role_is_one_taxonomy_understands(vault):
    install._apply_simple(vault)
    assert set(_written(install.TAXONOMY_PATH)["roles"]) <= set(taxonomy.ROLE_KEYS)


def test_rerunning_preserves_custom_categories_and_subfolders(vault):
    """Re-running the installer over a configured vault must not silently drop
    work done through onboard.py."""
    install.TAXONOMY_PATH.write_text(json.dumps({
        "roles": {"inbox": "00-Inbox"},
        "custom_categories": [{"key": "meetings", "folder": "Meetings", "label": "Meeting"}],
        "project_subfolders": {"Vaultex": ["architecture"]},
    }), encoding="utf-8")

    install._apply_simple(vault)
    data = _written(install.TAXONOMY_PATH)
    assert data["custom_categories"][0]["key"] == "meetings"
    assert data["project_subfolders"] == {"Vaultex": ["architecture"]}


def test_reserved_workspace_names_are_refused(vault):
    """§10.1's install.py enforcement point: a reserved name never reaches
    taxonomy.json, even via a hand-edited preset."""
    from core.presets import ReservedWorkspaceName

    reserved = {"default": "Builder", "entries": {"Builder": "Projects"}}
    with pytest.raises(ReservedWorkspaceName, match="reserved legacy name"):
        install._write_taxonomy({"inbox": "0-Inbox"}, reserved, PRESET_SIMPLE)
    assert not install.TAXONOMY_PATH.exists()


def test_a_populated_vault_is_detected(vault):
    assert not install._vault_is_populated(vault)
    (vault / "Areas").mkdir()
    assert install._vault_is_populated(vault)


def test_an_empty_vault_with_only_hidden_folders_is_not_populated(vault):
    (vault / ".obsidian").mkdir()
    assert not install._vault_is_populated(vault)


def test_a_vault_with_notes_but_no_folders_is_populated(vault):
    (vault / "note.md").write_text("hello", encoding="utf-8")
    assert install._vault_is_populated(vault)


# --- the interpreter guard ---------------------------------------------------

def test_the_version_guard_runs_before_any_non_stdlib_import():
    """A stock macOS python3 is 3.9. install_ui and core.presets both use
    `X | None` in annotations evaluated at def time, so importing them first
    turns an old interpreter into a bare TypeError naming a module the user
    has never heard of, instead of a sentence telling them what to do."""
    import ast

    tree = ast.parse((install.BASE_DIR / "setup" / "install.py").read_text(encoding="utf-8"))
    guard_line = next(
        node.lineno
        for node in tree.body
        if isinstance(node, ast.If) and "version_info" in ast.dump(node.test)
    )
    first_local_import = min(
        node.lineno
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and any(
            name.split(".")[0] in {"install_ui", "core"}
            for name in (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
        )
    )
    assert guard_line < first_local_import
