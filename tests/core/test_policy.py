"""write_policy.md loading: defaults, coercion, and mtime-based reload."""

import os

import pytest

from core import policy


@pytest.fixture(autouse=True)
def _clean_policy():
    """Each test starts with no policy file and a cold cache, so one test's
    file can't leak into the next through the module-level _cache."""
    policy._cache = None
    policy.POLICY_PATH.unlink(missing_ok=True)
    yield
    policy.POLICY_PATH.unlink(missing_ok=True)
    policy._cache = None


def _write(text: str) -> None:
    policy.POLICY_PATH.write_text(text, encoding="utf-8")


def _bump_mtime() -> None:
    """Force a distinct mtime rather than relying on filesystem timestamp
    resolution, so the reload tests are deterministic."""
    stat = policy.POLICY_PATH.stat()
    os.utime(policy.POLICY_PATH, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))


def test_no_file_returns_defaults():
    result = policy.load()
    assert result == policy.WritePolicy()
    assert result.auto_link_on_save is True
    assert result.placement_inference is True
    assert result.strip_title_prefix is True
    assert result.create_missing_folders is True


def test_all_toggles_false():
    _write(
        "---\n"
        "auto_link_on_save: false\n"
        "placement_inference: false\n"
        "strip_title_prefix: false\n"
        "create_missing_folders: false\n"
        "---\n\n# Write Policy\n"
    )
    result = policy.load()
    assert result.auto_link_on_save is False
    assert result.placement_inference is False
    assert result.strip_title_prefix is False
    assert result.create_missing_folders is False


def test_partial_file_keeps_other_defaults():
    _write("---\nplacement_inference: false\n---\n")
    result = policy.load()
    assert result.placement_inference is False
    assert result.auto_link_on_save is True
    assert result.strip_title_prefix is True
    assert result.create_missing_folders is True


def test_malformed_yaml_returns_defaults():
    _write("---\nauto_link_on_save: [unclosed\n---\n")
    assert policy.load() == policy.WritePolicy()


def test_non_mapping_frontmatter_returns_defaults():
    _write("---\n- a\n- b\n---\n")
    assert policy.load() == policy.WritePolicy()


def test_no_frontmatter_block_returns_defaults():
    _write("# Write Policy\n\nJust prose, no frontmatter.\n")
    assert policy.load() == policy.WritePolicy()


def test_unknown_keys_are_ignored():
    _write("---\nauto_link_on_save: false\nsome_future_toggle: true\n---\n")
    result = policy.load()
    assert result.auto_link_on_save is False
    assert not hasattr(result, "some_future_toggle")


@pytest.mark.parametrize("raw", ["false", '"false"', "no", "off", "0", "FALSE", "No"])
def test_falsey_spellings_coerce(raw):
    _write(f"---\nauto_link_on_save: {raw}\n---\n")
    assert policy.load().auto_link_on_save is False


@pytest.mark.parametrize("raw", ["true", '"true"', "yes", "on", "1", "TRUE", "Yes"])
def test_truthy_spellings_coerce(raw):
    _write(f"---\nplacement_inference: {raw}\n---\n")
    assert policy.load().placement_inference is True


def test_unrecognized_value_falls_back_to_that_fields_default():
    _write("---\nauto_link_on_save: maybe\nplacement_inference: false\n---\n")
    result = policy.load()
    assert result.auto_link_on_save is True   # default, not a crash
    assert result.placement_inference is False  # the valid key still applies


def test_edit_is_picked_up_without_restart():
    _write("---\nauto_link_on_save: true\n---\n")
    assert policy.load().auto_link_on_save is True

    _write("---\nauto_link_on_save: false\n---\n")
    _bump_mtime()
    assert policy.load().auto_link_on_save is False


def test_unchanged_file_is_not_reparsed(monkeypatch):
    _write("---\nauto_link_on_save: false\n---\n")
    policy.load()

    calls = []
    real_split = policy.frontmatter.split

    def counting_split(text):
        calls.append(text)
        return real_split(text)

    monkeypatch.setattr(policy.frontmatter, "split", counting_split)

    assert policy.load().auto_link_on_save is False
    assert policy.load().auto_link_on_save is False
    assert calls == [], "unchanged mtime should serve from cache without re-parsing"


def test_deleted_file_returns_to_defaults():
    _write("---\nauto_link_on_save: false\n---\n")
    assert policy.load().auto_link_on_save is False

    policy.POLICY_PATH.unlink()
    assert policy.load() == policy.WritePolicy()
