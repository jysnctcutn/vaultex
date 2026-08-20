import pytest

from core.vault import VerificationError, slug, verify_sections


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
