"""core/config.py runs its validation as module-level code at import time,
so exercising the SystemExit branches means importing it fresh in a
subprocess with deliberately-bad env vars -- reload()ing it in-process would
corrupt the env every other test module already imported against.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run_with_env(extra_env: dict) -> subprocess.CompletedProcess:
    vault = tempfile.mkdtemp(prefix="vaultex-config-test-")
    env = {
        **os.environ,
        "VAULTEX_PATH": vault,
        "MCP_AUTH_TOKEN": "test-token",
        # Empty, not absent: load_dotenv() would otherwise supply the
        # developer's real value, so the "unset" branches under test would
        # only ever run in CI. An explicit empty wins and reads as unset.
        "AUTHORIZE_PASSWORD": "",
        "VAULTEX_MODE": "",
        **extra_env,
    }
    return subprocess.run(
        [sys.executable, "-c", "import core.config"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_invalid_mcp_port_exits():
    result = _run_with_env({"MCP_PORT": "not-a-number"})
    assert result.returncode != 0
    assert "MCP_PORT must be an integer" in result.stderr


def test_invalid_reindex_interval_exits():
    result = _run_with_env({"REINDEX_INTERVAL_SECONDS": "soon"})
    assert result.returncode != 0
    assert "REINDEX_INTERVAL_SECONDS must be an integer" in result.stderr


def test_invalid_rate_limit_max_requests_exits():
    result = _run_with_env({"RATE_LIMIT_MAX_REQUESTS": "lots"})
    assert result.returncode != 0
    assert "RATE_LIMIT_MAX_REQUESTS must be an integer" in result.stderr


def test_invalid_rate_limit_window_exits():
    result = _run_with_env({"RATE_LIMIT_WINDOW_SECONDS": "a-while"})
    assert result.returncode != 0
    assert "RATE_LIMIT_WINDOW_SECONDS must be an integer" in result.stderr


def test_oauth_issuer_without_password_exits():
    result = _run_with_env({"OAUTH_ISSUER_URL": "https://example.ts.net"})
    assert result.returncode != 0
    assert "AUTHORIZE_PASSWORD" in result.stderr


def test_missing_vault_path_exits():
    env = {**os.environ, "VAULTEX_PATH": "/no/such/vaultex/path", "MCP_AUTH_TOKEN": "test-token"}
    result = subprocess.run(
        [sys.executable, "-c", "import core.config"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Vaultex path does not exist" in result.stderr


def test_missing_auth_token_exits():
    vault = tempfile.mkdtemp(prefix="vaultex-config-test-")
    env = {**os.environ, "VAULTEX_PATH": vault, "MCP_AUTH_TOKEN": ""}
    result = subprocess.run(
        [sys.executable, "-c", "import core.config"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "Set MCP_AUTH_TOKEN" in result.stderr
