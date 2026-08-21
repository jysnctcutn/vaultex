import pytest

from core.tools.tags import get_tags, update_frontmatter
from core.vault import read, safe_path, write


def test_get_tags_missing_note_raises():
    with pytest.raises(FileNotFoundError):
        get_tags("tags-does-not-exist.md")


def test_get_tags_combines_frontmatter_and_inline():
    write(
        safe_path("tags-note-1.md"),
        "---\ntags: [alpha, beta]\n---\nBody mentions #gamma and issue#123 and a ```code #notatag``` block.\n",
        overwrite=True,
    )
    result = get_tags("tags-note-1.md")
    assert result["frontmatter_tags"] == ["alpha", "beta"]
    assert result["inline_tags"] == ["gamma"]
    assert result["all_tags"] == ["alpha", "beta", "gamma"]


def test_get_tags_handles_string_tags_and_no_inline():
    write(safe_path("tags-note-2.md"), "---\ntags: alpha, beta\n---\nNo inline tags here.\n", overwrite=True)
    result = get_tags("tags-note-2.md")
    assert result["frontmatter_tags"] == ["alpha", "beta"]
    assert result["inline_tags"] == []


def test_get_tags_no_frontmatter_tags():
    write(safe_path("tags-note-3.md"), "---\nstatus: draft\n---\nBody with no tags.\n", overwrite=True)
    result = get_tags("tags-note-3.md")
    assert result["frontmatter_tags"] == []
    assert result["all_tags"] == []


def test_update_frontmatter_missing_note_raises():
    with pytest.raises(FileNotFoundError):
        update_frontmatter("tags-missing.md", {"status": "done"})


def test_update_frontmatter_merges_by_default():
    write(safe_path("tags-note-4.md"), "---\nstatus: draft\ntags: [a]\n---\nBody.\n", overwrite=True)
    update_frontmatter("tags-note-4.md", {"status": "done"})
    fm = get_tags("tags-note-4.md")["frontmatter"]
    assert fm["status"] == "done"
    assert fm["tags"] == ["a"]


def test_update_frontmatter_replaces_when_merge_false():
    write(safe_path("tags-note-5.md"), "---\nstatus: draft\ntags: [a]\n---\nBody.\n", overwrite=True)
    update_frontmatter("tags-note-5.md", {"status": "done"}, merge=False)
    fm = get_tags("tags-note-5.md")["frontmatter"]
    assert fm == {"status": "done"}


def test_update_frontmatter_preserves_body():
    write(safe_path("tags-note-6.md"), "---\nstatus: draft\n---\nOriginal body text.\n", overwrite=True)
    update_frontmatter("tags-note-6.md", {"status": "done"})
    assert "Original body text." in read(safe_path("tags-note-6.md"))
