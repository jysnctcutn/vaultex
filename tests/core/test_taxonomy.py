from pathlib import Path

import core.taxonomy as taxonomy_mod


def test_load_returns_empty_defaults_when_no_file(monkeypatch):
    monkeypatch.setattr(taxonomy_mod, "TAXONOMY_PATH", Path("/no/such/taxonomy.json"))
    assert taxonomy_mod._load() == {"roles": {}, "custom_categories": [], "project_subfolders": {}}
