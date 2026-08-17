"""SQLite persistence for OAuth clients, authorization codes, and tokens.

Same directness as index_vault.py's own sqlite handling — no ORM. A fresh
connection per call is fine at this (single-user, low-QPS) scale. Gitignored,
mounted as a Docker volume so restarts don't force re-authorization.
"""

import secrets
import sqlite3
import time
from pathlib import Path

from mcp.server.auth.provider import AccessToken, AuthorizationCode, AuthorizationParams, RefreshToken
from mcp.shared.auth import OAuthClientInformationFull

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    client_id TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS auth_codes (
    code TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS access_tokens (
    token TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refresh_tokens (
    token TEXT PRIMARY KEY,
    data TEXT NOT NULL
);
"""


def init_db(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.executescript(_SCHEMA)


def save_client(db_path: Path, client_info: OAuthClientInformationFull) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO clients (client_id, data) VALUES (?, ?)",
            (client_info.client_id, client_info.model_dump_json()),
        )


def get_client(db_path: Path, client_id: str) -> OAuthClientInformationFull | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT data FROM clients WHERE client_id = ?", (client_id,)).fetchone()
    return OAuthClientInformationFull.model_validate_json(row[0]) if row else None


def new_authorization_code(
    db_path: Path,
    client: OAuthClientInformationFull,
    params: AuthorizationParams,
    subject: str,
) -> str:
    """Build, persist, and return a fresh single-use authorization code."""
    code_str = secrets.token_urlsafe(32)
    auth_code = AuthorizationCode(
        code=code_str,
        scopes=params.scopes or [],
        expires_at=time.time() + 600,
        client_id=client.client_id,
        code_challenge=params.code_challenge,
        redirect_uri=params.redirect_uri,
        redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
        resource=params.resource,
        subject=subject,
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO auth_codes (code, data, expires_at) VALUES (?, ?, ?)",
            (code_str, auth_code.model_dump_json(), auth_code.expires_at),
        )
    return code_str


def load_auth_code(db_path: Path, code: str) -> AuthorizationCode | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT data FROM auth_codes WHERE code = ?", (code,)).fetchone()
    return AuthorizationCode.model_validate_json(row[0]) if row else None


def delete_auth_code(db_path: Path, code: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM auth_codes WHERE code = ?", (code,))


def save_access_token(db_path: Path, token: AccessToken) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO access_tokens (token, data) VALUES (?, ?)",
            (token.token, token.model_dump_json()),
        )


def load_access_token(db_path: Path, token: str) -> AccessToken | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT data FROM access_tokens WHERE token = ?", (token,)).fetchone()
    return AccessToken.model_validate_json(row[0]) if row else None


def delete_access_token(db_path: Path, token: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM access_tokens WHERE token = ?", (token,))


def save_refresh_token(db_path: Path, token: RefreshToken) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO refresh_tokens (token, data) VALUES (?, ?)",
            (token.token, token.model_dump_json()),
        )


def load_refresh_token(db_path: Path, token: str) -> RefreshToken | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT data FROM refresh_tokens WHERE token = ?", (token,)).fetchone()
    return RefreshToken.model_validate_json(row[0]) if row else None


def delete_refresh_token(db_path: Path, token: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM refresh_tokens WHERE token = ?", (token,))
