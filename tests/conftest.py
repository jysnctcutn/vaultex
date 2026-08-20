"""Pytest bootstrap.

core/config.py validates and locks in its env vars the moment it's first
imported (see its module-level SystemExit checks) — so those vars have to
be set here, before any test module imports anything under core/, or tests
would run against the developer's real .env and real vault instead of an
isolated fixture.
"""

import os
import tempfile
from pathlib import Path

_TEST_VAULT = Path(tempfile.mkdtemp(prefix="vaultex-test-vault-"))
(_TEST_VAULT / "01-Excluded").mkdir()

os.environ["VAULTEX_PATH"] = str(_TEST_VAULT)
os.environ["MCP_AUTH_TOKEN"] = "test-token-not-a-real-secret"
os.environ["EXCLUDED_AREAS"] = "01-Excluded"
# Points at a path that doesn't exist, so vault.py's semantic-search hooks
# (_auto_link, _reindex) stay no-ops during tests instead of touching the
# developer's real vault_embeddings.db or downloading the embedding model.
os.environ["VAULT_EMBEDDINGS_DB"] = str(_TEST_VAULT / "unused_embeddings.db")
