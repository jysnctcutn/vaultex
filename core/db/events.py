"""Search-event capture: raw material for a future Learning-to-Rank ranker.

Reuses vault_embeddings.db rather than adding a second store; stdlib sqlite3
only, so it works without the vector extension.
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SEARCH_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS search_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts            TEXT    NOT NULL,
    query         TEXT    NOT NULL,
    limit_n       INTEGER NOT NULL,
    areas         TEXT,
    soft_fail     INTEGER NOT NULL DEFAULT 0,
    result_count  INTEGER NOT NULL,
    results_json  TEXT    NOT NULL
)
"""


def log_search_event(db_path: Path, query: str, limit_n: int, areas: list[str] | None,
                     soft_fail: bool, results: list[dict]) -> None:
    """Append one `search` call to the search_events table, creating the DB
    file if absent.

    Callers gate this on the SEARCH_LOG env flag and swallow exceptions --
    search must never fail because logging did.
    """
    rows = [
        {"path": r["path"], "score": r["score"], "sources": r["sources"], "rank": i}
        for i, r in enumerate(results, start=1)
    ]
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(SEARCH_EVENTS_SCHEMA)
        conn.execute(
            "INSERT INTO search_events "
            "(ts, query, limit_n, areas, soft_fail, result_count, results_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                query,
                limit_n,
                json.dumps(areas) if areas else None,
                int(soft_fail),
                len(results),
                json.dumps(rows, separators=(",", ":")),
            ),
        )
        conn.commit()
    finally:
        conn.close()
