"""
Vaultex — Vault Embeddings Indexer

Standalone script (kept separate from server.py per the semantic search
architecture decision) that walks the vault, chunks each note, embeds the
chunks with a local sentence-transformers model, and stores the vectors in
a sqlite-vec database for semantic_search_vaultex to query.

Run:
    export VAULTEX_PATH=/path/to/vaultex
    python3 index_vault.py                # incremental: only changed notes
    python3 index_vault.py --full         # re-embed everything from scratch

The resulting vault_embeddings.db is vault-wide (no EXCLUDED_AREAS filtering
here) — area restrictions are applied at query time in server.py, the same
way _iter_markdown() filters keyword search, so one embeddings db can serve
both a full and a restricted server instance.
"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

# Loads VAULTEX_PATH (and friends) from a `.env` file next to this
# script, if present, so it doesn't need exporting by hand — same as server.py.
load_dotenv(Path(__file__).parent / ".env")

from core.embeddings import MODEL_NAME, connect, delete_path, get_model, index_note  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vault", default=os.environ.get("VAULTEX_PATH", "./vaultex"),
        help="Path to the vault (default: $VAULTEX_PATH or ./vaultex)",
    )
    parser.add_argument(
        "--db", default=os.environ.get(
            "VAULT_EMBEDDINGS_DB", str(Path(__file__).parent / "vault_embeddings.db")
        ),
        help="Path to the sqlite-vec database (default: $VAULT_EMBEDDINGS_DB or ./vault_embeddings.db)",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="Force a full re-index, ignoring stored mtimes",
    )
    args = parser.parse_args()

    vault_path = Path(args.vault).expanduser().resolve()
    if not vault_path.exists():
        raise SystemExit(f"Vault path does not exist: {vault_path}")

    db_path = Path(args.db).expanduser().resolve()
    conn = connect(db_path)

    print(f"Loading embedding model ({MODEL_NAME})...")
    model = get_model()

    stored_mtimes = dict(conn.execute("SELECT path, mtime FROM files")) if not args.full else {}
    seen_paths: set[str] = set()
    indexed_notes = 0
    indexed_chunks = 0

    for note_path in sorted(vault_path.rglob("*.md")):
        rel = str(note_path.relative_to(vault_path))
        seen_paths.add(rel)
        current_mtime = note_path.stat().st_mtime
        if not args.full and stored_mtimes.get(rel) == current_mtime:
            continue
        n = index_note(conn, model, vault_path, note_path)
        indexed_notes += 1
        indexed_chunks += n
        print(f"  indexed {rel} ({n} chunks)")

    stale_paths = set(stored_mtimes) - seen_paths
    for rel in stale_paths:
        delete_path(conn, rel)
        print(f"  removed {rel} (no longer in vault)")

    conn.commit()
    total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    conn.close()

    print(
        f"\nDone. {indexed_notes} notes re-indexed ({indexed_chunks} chunks), "
        f"{len(stale_paths)} removed. Database now has {total_files} notes, "
        f"{total_chunks} chunks total. -> {db_path}"
    )


if __name__ == "__main__":
    main()
