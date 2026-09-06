"""
Vaultex — Vault Embeddings Indexer

Standalone script (kept separate from server.py per the semantic search
architecture decision) that walks the vault, chunks each note, embeds the
chunks with a local sentence-transformers model, and stores the vectors in
a sqlite-vec database for the `search` tool's semantic half to query.

Run:
    export VAULTEX_PATH=/path/to/vaultex
    python3 index_vault.py                # incremental: only changed notes
    python3 index_vault.py --full         # re-embed everything from scratch

The resulting vault_embeddings.db is vault-wide -- no EXCLUDED_AREAS
filtering happens here. Area restrictions are applied at query time
instead (the same way iter_markdown() filters keyword search), so one
embeddings db can serve both a full and a restricted server instance.
"""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

# Loads VAULTEX_PATH (and friends) from a `.env` file next to this
# script, if present, so it doesn't need exporting by hand — same as server.py.
load_dotenv(Path(__file__).parent / ".env")

from core.db import connect, incremental_sweep, index_note, is_indexable  # noqa: E402
from core.embeddings import MODEL_NAME, get_model  # noqa: E402


def _print_progress(rel: str, chunks: int | None) -> None:
    if chunks is None:
        print(f"  removed {rel} (no longer in vault)")
    else:
        print(f"  indexed {rel} ({chunks} chunks)")


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

    print(f"Loading embedding model ({MODEL_NAME})...")
    get_model()  # warm the cache before the loop so it's not attributed to the first file

    if args.full:
        # Bypasses incremental_sweep() deliberately: --full re-embeds every
        # file unconditionally. It doesn't attempt stale-entry cleanup
        # (same as before this refactor), since it never looks at what's
        # currently stored.
        conn = connect(db_path)
        model = get_model()
        indexed_notes = indexed_chunks = 0
        for note_path in sorted(vault_path.rglob("*.md")):
            if not is_indexable(vault_path, note_path):
                continue
            rel = str(note_path.relative_to(vault_path))
            n = index_note(conn, model, vault_path, note_path)
            indexed_notes += 1  # noqa: SIM113 — enumerate() doesn't fit: indexed_chunks below is a running sum of a different quantity, not the loop index
            indexed_chunks += n
            print(f"  indexed {rel} ({n} chunks)")
        removed = 0
        conn.commit()
        total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        conn.close()
    else:
        result = incremental_sweep(vault_path, db_path, on_note=_print_progress)
        indexed_notes, indexed_chunks, removed = result["indexed"], result["indexed_chunks"], result["removed"]
        conn = connect(db_path)
        total_chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
        conn.close()

    print(
        f"\nDone. {indexed_notes} notes re-indexed ({indexed_chunks} chunks), "
        f"{removed} removed. Database now has {total_files} notes, "
        f"{total_chunks} chunks total. -> {db_path}"
    )


if __name__ == "__main__":
    main()
