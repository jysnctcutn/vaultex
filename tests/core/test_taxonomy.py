from pathlib import Path

import core.taxonomy as taxonomy_mod


def test_load_returns_empty_defaults_when_no_file(monkeypatch):
    monkeypatch.setattr(taxonomy_mod, "TAXONOMY_PATH", Path("/no/such/taxonomy.json"))
    assert taxonomy_mod._load() == {"roles": {}, "custom_categories": [], "project_subfolders": {}}


def test_agent_memory_role_keys_registered():
    for key in ("episodic", "open_questions"):
        assert key in taxonomy_mod.ROLE_KEYS
        # present in the resolved map (None when the vault hasn't configured it)
        assert key in taxonomy_mod.roles
