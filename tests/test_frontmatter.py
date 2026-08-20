from core.frontmatter import join, split


def test_split_with_valid_frontmatter():
    text = "---\ntitle: Hello\ntags:\n  - a\n  - b\n---\nBody text here.\n"
    data, body = split(text)
    assert data == {"title": "Hello", "tags": ["a", "b"]}
    assert body == "Body text here.\n"


def test_split_with_no_frontmatter_block():
    text = "Just a plain note, no frontmatter.\n"
    data, body = split(text)
    assert data == {}
    assert body == text


def test_split_with_malformed_yaml_does_not_raise():
    text = "---\nfoo: [1, 2\n---\nBody.\n"
    data, body = split(text)
    assert data == {}
    assert body == text


def test_split_with_non_mapping_frontmatter():
    text = "---\n- just\n- a\n- list\n---\nBody.\n"
    data, body = split(text)
    assert data == {}
    assert body == text


def test_join_round_trips_with_split():
    original = {"title": "Hello", "tags": ["a", "b"]}
    body = "Body text here.\n"
    data, round_tripped_body = split(join(original, body))
    assert data == original
    assert round_tripped_body == body


def test_join_with_empty_frontmatter_returns_body_unchanged():
    assert join({}, "Just body.\n") == "Just body.\n"
