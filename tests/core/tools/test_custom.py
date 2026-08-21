import pytest

from core.taxonomy import CustomCategory
from core.tools.custom import _make_create_fn, _make_get_fn
from core.vault import VerificationError, read, safe_path, write

_CATEGORY = CustomCategory(
    key="meeting_notes",
    folder="03-Knowledge/MeetingNotes",
    label="Meeting Notes",
    get_tool_name="get_meeting_notes",
    create_tool_name="create_meeting_notes_note",
)

_CATEGORY_WITH_PREFIX_AND_SECTIONS = CustomCategory(
    key="reviews",
    folder="03-Knowledge/Reviews",
    label="Reviews",
    get_tool_name="get_reviews",
    create_tool_name="create_reviews_note",
    required_sections=["**Summary:**"],
    prefix="Review - ",
)


def test_create_fn_writes_note_and_get_fn_lists_it():
    create = _make_create_fn(_CATEGORY)
    get = _make_get_fn(_CATEGORY)

    path = create("Standup", "notes from standup")
    assert path == "03-Knowledge/MeetingNotes/Standup.md"
    assert read(safe_path(path)) == "notes from standup"

    listed = get()
    assert any(n["path"] == path for n in listed)


def test_create_fn_rejects_duplicate_without_overwrite():
    create = _make_create_fn(_CATEGORY)
    create("Dup Meeting", "first")
    with pytest.raises(FileExistsError):
        create("Dup Meeting", "second")


def test_create_fn_with_prefix_and_required_sections():
    create = _make_create_fn(_CATEGORY_WITH_PREFIX_AND_SECTIONS)
    path = create("Review - Q1 Planning", "**Summary:** went well")
    assert path == "03-Knowledge/Reviews/Review - Q1 Planning.md"


def test_create_fn_missing_required_section_raises():
    create = _make_create_fn(_CATEGORY_WITH_PREFIX_AND_SECTIONS)
    with pytest.raises(VerificationError):
        create("Review - Missing Section", "no summary here")


def test_get_fn_excerpt_is_capped_and_stripped():
    create = _make_create_fn(_CATEGORY)
    get = _make_get_fn(_CATEGORY)
    write(safe_path("03-Knowledge/MeetingNotes/manual.md"), "  " + ("y" * 300), overwrite=True)
    listed = get()
    entry = next(n for n in listed if n["path"] == "03-Knowledge/MeetingNotes/manual.md")
    assert len(entry["excerpt"]) <= 200
    assert not entry["excerpt"].startswith(" ")
