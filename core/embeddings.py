"""Turning note text into chunks and embeddings. No storage — that's core/db/.

Deliberately config-free, like core/db/, so index_vault.py keeps working as a
standalone script needing only VAULTEX_PATH rather than the full server env.
"""

import re

try:
    import sqlite_vec  # noqa: F401 — probed, not used here; see _SEMANTIC_DEPS_AVAILABLE
    from sentence_transformers import SentenceTransformer
    _SEMANTIC_DEPS_AVAILABLE = True
except ImportError:
    _SEMANTIC_DEPS_AVAILABLE = False

# Probes both halves: callers gate on "can we search semantically at all",
# not on either one, so the answer can't depend on which module you ask.

MODEL_NAME = "BAAI/bge-small-en-v1.5"
MAX_CHUNK_WORDS = 500

FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
HEADING_RE = re.compile(r"(?m)^## (.+)$")

_model = None


def get_model() -> "SentenceTransformer":
    """Loaded once, on first use, then cached — shared by the `search` tool
    and the write-time reindex hook so the process only holds one copy."""
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def strip_frontmatter(text: str) -> str:
    return FRONTMATTER_RE.sub("", text, count=1)


def _chunk_by_words(text: str, heading: str | None, max_words: int = MAX_CHUNK_WORDS):
    text = text.strip()
    if not text:
        return []
    words = text.split()
    if len(words) <= max_words:
        return [(heading, text)]
    return [
        (heading, " ".join(words[i:i + max_words]))
        for i in range(0, len(words), max_words)
    ]


def chunk_note(text: str) -> list[tuple[str | None, str]]:
    """Chunk by ## heading first; each heading's body falls back to
    ~500-word blocks if it's still too large. Notes with no ## headings are
    chunked by word blocks directly."""
    text = strip_frontmatter(text)
    headings = list(HEADING_RE.finditer(text))
    if not headings:
        return _chunk_by_words(text, None)

    chunks: list[tuple[str | None, str]] = []
    preamble = text[:headings[0].start()].strip()
    if preamble:
        chunks.extend(_chunk_by_words(preamble, None))

    for i, m in enumerate(headings):
        start = m.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
        heading = m.group(1).strip()
        body = text[start:end].strip()
        chunks.extend(_chunk_by_words(body, heading))
    return chunks
