"""Mode resolution and the registration boundary it draws.

Both are import-time behavior driven by env + taxonomy.json, so these run in
subprocesses for the same reason test_config.py does: reload()ing in-process
would corrupt the env every other test module already imported against.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_LIST_TOOLS = """
import core.tools
from core.mcp_app import mcp
from core.mode import MODE
print(MODE)
print(",".join(sorted(t.name for t in mcp._tool_manager.list_tools())))
"""

BASIC_TOOLS = {"grep", "read_note", "search", "write_note"}


def _run_in_subprocess(code: str, *, taxonomy: dict | None, **extra_env) -> subprocess.CompletedProcess:
    tmp = Path(tempfile.mkdtemp(prefix="vaultex-mode-test-"))
    taxonomy_path = tmp / "taxonomy.json"
    taxonomy_path.write_text(json.dumps(taxonomy or {"roles": {}, "custom_categories": []}))
    env = {
        **os.environ,
        "VAULTEX_PATH": str(tmp),
        "MCP_AUTH_TOKEN": "test-token",
        "TAXONOMY_JSON_PATH": str(taxonomy_path),
        "VAULT_EMBEDDINGS_DB": str(tmp / "unused.db"),
        # Neutralize anything inherited from the developer's real .env.
        "READ_ONLY": "false",
        "ENABLE_NOTE_MOVE": "false",
        "ENABLE_DISTILL_APPLY": "false",
    }
    # Empty, not popped: load_dotenv() would supply the developer's real
    # value for anything absent. An explicit empty wins and reads as unset.
    env["VAULTEX_MODE"] = ""
    env.update({k: str(v) for k, v in extra_env.items()})
    return subprocess.run(  # noqa: S603 — `code` is a module-level literal in this file, not input
        [sys.executable, "-c", code],
        cwd=_REPO_ROOT, env=env, capture_output=True, text=True, timeout=90,
    )


def _mode_and_tools(result: subprocess.CompletedProcess) -> tuple[str, set[str]]:
    assert result.returncode == 0, result.stderr
    mode, names = result.stdout.strip().splitlines()[-2:]
    return mode, set(names.split(","))


# --- resolution -------------------------------------------------------------

def test_no_taxonomy_derives_basic():
    mode, _ = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy=None))
    assert mode == "basic"


def test_configured_role_derives_professional():
    mode, _ = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy={"roles": {"inbox": "00-Inbox"}, "custom_categories": []}))
    assert mode == "professional"


def test_custom_category_alone_derives_professional():
    taxonomy = {
        "roles": {},
        "custom_categories": [{"key": "meetings", "folder": "Meetings", "label": "Meeting"}],
    }
    mode, _ = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy=taxonomy))
    assert mode == "professional"


def test_env_override_forces_basic_despite_taxonomy():
    result = _run_in_subprocess(_LIST_TOOLS, taxonomy={"roles": {"inbox": "00-Inbox"}}, VAULTEX_MODE="basic")
    mode, names = _mode_and_tools(result)
    assert mode == "basic"
    assert names == BASIC_TOOLS


def test_env_override_forces_professional_despite_no_taxonomy():
    mode, names = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy=None, VAULTEX_MODE="professional"))
    assert mode == "professional"
    assert names > BASIC_TOOLS


def test_env_override_is_case_insensitive():
    mode, _ = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy=None, VAULTEX_MODE="  BASIC  "))
    assert mode == "basic"


def test_invalid_mode_exits():
    result = _run_in_subprocess("import core.mode", taxonomy=None, VAULTEX_MODE="nonsense")
    assert result.returncode != 0
    assert "VAULTEX_MODE must be" in result.stderr


def test_professional_without_taxonomy_warns():
    result = _run_in_subprocess("import core.mode", taxonomy=None, VAULTEX_MODE="professional")
    assert result.returncode == 0
    assert "no taxonomy configured" in result.stderr


# --- registration boundary --------------------------------------------------

def test_basic_registers_exactly_four_tools():
    _, names = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy=None))
    assert names == BASIC_TOOLS


def test_basic_read_only_drops_the_write_tool():
    _, names = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy=None, READ_ONLY="true"))
    assert names == BASIC_TOOLS - {"write_note"}


@pytest.mark.parametrize("structured", ["save_decision", "save_brainstorm", "log_event", "get_tags"])
def test_structured_tools_absent_in_basic(structured):
    """Absent, not registered-and-failing: nothing to call, nothing to error."""
    _, names = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy=None))
    assert structured not in names


def test_professional_keeps_the_full_surface_plus_write_note():
    taxonomy = {"roles": {"inbox": "00-Inbox", "builder_projects": "02-Builder/Projects"}}
    _, names = _mode_and_tools(_run_in_subprocess(_LIST_TOOLS, taxonomy=taxonomy))
    assert {"save_decision", "save_brainstorm", "log_event", "get_tags"} <= names
    assert "write_note" in names
    assert names >= BASIC_TOOLS
