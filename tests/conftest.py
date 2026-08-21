"""Pytest bootstrap.

core/config.py validates and locks in its env vars the moment it's first
imported (see its module-level SystemExit checks) — so those vars have to
be set here, before any test module imports anything under core/, or tests
would run against the developer's real .env and real vault instead of an
isolated fixture.
"""

import json
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

# core/taxonomy.py reads a fixed file path by default (BASE_DIR/taxonomy.json)
# with no env override until TAXONOMY_JSON_PATH was added specifically for
# this: tests must never read (or, worse, depend on the presence/absence of)
# the developer's real, gitignored taxonomy.json -- CI has no such file at
# all, so any test relying on it passes locally and fails in CI. This writes
# a throwaway one with just enough configured for tests that need a real
# Builder-project root to resolve against the isolated _TEST_VAULT above.
_TEST_TAXONOMY = _TEST_VAULT / "test_taxonomy.json"
_TEST_TAXONOMY.write_text(json.dumps({
    "roles": {"builder_projects": "02-Builder/Projects"},
    "custom_categories": [],
    "project_subfolders": {},
}), encoding="utf-8")
os.environ["TAXONOMY_JSON_PATH"] = str(_TEST_TAXONOMY)
