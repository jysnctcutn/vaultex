import pytest
from mcp.server.auth.provider import AccessToken, AuthorizationParams, RefreshToken
from mcp.shared.auth import OAuthClientInformationFull

from core.oauth import store


@pytest.fixture
def db(tmp_path):
    path = tmp_path / "oauth_store.db"
    store.init_db(path)
    return path


@pytest.fixture
def client():
    return OAuthClientInformationFull(client_id="test-client", redirect_uris=["https://claude.ai/callback"])


def test_save_and_get_client(db, client):
    store.save_client(db, client)
    loaded = store.get_client(db, client.client_id)
    assert loaded is not None
    assert loaded.client_id == "test-client"


def test_get_missing_client_returns_none(db):
    assert store.get_client(db, "no-such-client") is None


def test_save_client_upserts(db, client):
    store.save_client(db, client)
    store.save_client(db, client)  # INSERT OR REPLACE, must not raise
    assert store.get_client(db, client.client_id) is not None


def test_authorization_code_lifecycle(db, client):
    params = AuthorizationParams(
        state="s", scopes=["mcp"], code_challenge="cc",
        redirect_uri="https://claude.ai/callback", redirect_uri_provided_explicitly=True,
    )
    code_str = store.new_authorization_code(db, client, params, subject="user-1")
    assert code_str

    loaded = store.load_auth_code(db, code_str)
    assert loaded is not None
    assert loaded.client_id == client.client_id
    assert loaded.subject == "user-1"

    store.delete_auth_code(db, code_str)
    assert store.load_auth_code(db, code_str) is None


def test_load_missing_auth_code_returns_none(db):
    assert store.load_auth_code(db, "does-not-exist") is None


def test_access_token_lifecycle(db):
    token = AccessToken(token="tok-1", client_id="test-client", scopes=["mcp"], expires_at=9999999999)
    store.save_access_token(db, token)

    loaded = store.load_access_token(db, "tok-1")
    assert loaded is not None
    assert loaded.client_id == "test-client"

    store.delete_access_token(db, "tok-1")
    assert store.load_access_token(db, "tok-1") is None


def test_load_missing_access_token_returns_none(db):
    assert store.load_access_token(db, "no-such-token") is None


def test_refresh_token_lifecycle(db):
    token = RefreshToken(token="rtok-1", client_id="test-client", scopes=["mcp"], expires_at=9999999999)
    store.save_refresh_token(db, token)

    loaded = store.load_refresh_token(db, "rtok-1")
    assert loaded is not None
    assert loaded.client_id == "test-client"

    store.delete_refresh_token(db, "rtok-1")
    assert store.load_refresh_token(db, "rtok-1") is None


def test_load_missing_refresh_token_returns_none(db):
    assert store.load_refresh_token(db, "no-such-refresh") is None
