import pytest

from core.vault import MAX_LIMIT, VerificationError, slug, validate_limit, verify_sections


def test_slug_strips_whitespace():
    assert slug("  My Note Title  ") == "My Note Title"


def test_slug_strips_matching_prefix():
    assert slug("Decision - My Note", prefix="Decision - ") == "My Note"


def test_slug_leaves_title_without_prefix_untouched():
    assert slug("My Note", prefix="Decision - ") == "My Note"


def test_slug_prefix_match_is_case_insensitive():
    assert slug("decision - My Note", prefix="Decision - ") == "My Note"


def test_verify_sections_passes_when_all_present():
    verify_sections(
        "**Decided:** yes\n**What it means:** stuff",
        ["**Decided:**", "**What it means:**"],
    )


def test_verify_sections_raises_on_missing_section():
    with pytest.raises(VerificationError, match="What it means"):
        verify_sections("**Decided:** yes", ["**Decided:**", "**What it means:**"])


def test_validate_limit_accepts_in_range_values():
    validate_limit(1)
    validate_limit(MAX_LIMIT)
    validate_limit(10)


def test_validate_limit_rejects_zero_and_negative():
    with pytest.raises(ValueError, match="between 1"):
        validate_limit(0)
    with pytest.raises(ValueError, match="between 1"):
        validate_limit(-5)


def test_validate_limit_rejects_over_max():
    with pytest.raises(ValueError, match="between 1"):
        validate_limit(MAX_LIMIT + 1)


def test_validate_limit_rejects_non_integers():
    with pytest.raises(ValueError, match="between 1"):
        validate_limit(10.5)
    with pytest.raises(ValueError, match="between 1"):
        validate_limit("10")
    with pytest.raises(ValueError, match="between 1"):
        validate_limit(True)
