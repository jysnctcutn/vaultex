"""All database access for Vaultex's semantic index.

The rule: nothing outside core/db/ opens a connection or writes SQL.

Config-free -- paths are arguments, never read from core.config -- so
index_vault.py stays runnable standalone with only VAULTEX_PATH set.
"""

from .events import SEARCH_EVENTS_SCHEMA, log_search_event
from .vectors import (
    EMBEDDING_DIM,
    POLICY_FILENAME,
    connect,
    delete_path,
    find_related,
    incremental_sweep,
    index_note,
    is_indexable,
    periodic_reindex,
    semantic_query,
)

__all__ = [
    "EMBEDDING_DIM",
    "POLICY_FILENAME",
    "SEARCH_EVENTS_SCHEMA",
    "connect",
    "delete_path",
    "find_related",
    "incremental_sweep",
    "index_note",
    "is_indexable",
    "log_search_event",
    "periodic_reindex",
    "semantic_query",
]
