import asyncio

import pytest
from mcp.server.auth.provider import AuthorizationParams, RegistrationError, TokenError
from mcp.shared.auth import OAuthClientInformationFull

import core.oauth.provider as provider_mod
from core.config import AUTH_TOKEN
from core.oauth.provider import VaultexOAuthProvider


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture
def provider(monkeypatch, tmp_path):
    db_path = tmp_path / "oauth_store.db"
    monkeypatch.setattr(provider_mod, "OAUTH_STORE_DB", db_path)
    return VaultexOAuthProvider()


def _client(client_id="test-client", redirect_uri="https://claude.ai/callback"):
    return OAuthClientInformationFull(client_id=client_id, redirect_uris=[redirect_uri])


def _params(redirect_uri="https://claude.ai/callback"):
    return AuthorizationParams(
        state="s1", scopes=["mcp"], code_challenge="cc",
        redirect_uri=redirect_uri, redirect_uri_provided_explicitly=True,
    )


def test_register_client_allows_allowed_host(provider):
    client = _client(redirect_uri="https://claude.ai/callback")
    _run(provider.register_client(client))
    loaded = _run(provider.get_client(client.client_id))
    assert loaded is not None


def test_register_client_rejects_disallowed_host(provider):
    client = _client(redirect_uri="https://evil.example.com/callback")
    with pytest.raises(RegistrationError):
        _run(provider.register_client(client))


def test_get_client_missing_returns_none(provider):
    assert _run(provider.get_client("nope")) is None


def test_authorize_returns_login_redirect_path(provider):
    client = _client()
    path = _run(provider.authorize(client, _params()))
    assert path.startswith("/login?login_id=")


def test_load_authorization_code_round_trip(provider):
    client = _client()
    _run(provider.register_client(client))
    from core.oauth import store as store_mod

    code_str = store_mod.new_authorization_code(provider_mod.OAUTH_STORE_DB, client, _params(), subject="jayson")
    loaded = _run(provider.load_authorization_code(client, code_str))
    assert loaded is not None
    assert loaded.code == code_str


def test_load_authorization_code_wrong_client_returns_none(provider):
    client = _client("client-a")
    other_client = _client("client-b")
    from core.oauth import store as store_mod

    code_str = store_mod.new_authorization_code(provider_mod.OAUTH_STORE_DB, client, _params(), subject="jayson")
    assert _run(provider.load_authorization_code(other_client, code_str)) is None


def test_load_authorization_code_missing_returns_none(provider):
    assert _run(provider.load_authorization_code(_client(), "no-such-code")) is None


def test_exchange_authorization_code_issues_tokens_and_consumes_code(provider):
    client = _client()
    from core.oauth import store as store_mod

    code_str = store_mod.new_authorization_code(provider_mod.OAUTH_STORE_DB, client, _params(), subject="jayson")
    auth_code = store_mod.load_auth_code(provider_mod.OAUTH_STORE_DB, code_str)

    token = _run(provider.exchange_authorization_code(client, auth_code))

    assert token.access_token
    assert token.refresh_token
    assert token.scope == "mcp"
    assert store_mod.load_auth_code(provider_mod.OAUTH_STORE_DB, code_str) is None


def test_load_refresh_token_round_trip_and_wrong_client(provider):
    client = _client("client-a")
    other = _client("client-b")
    from mcp.server.auth.provider import RefreshToken

    from core.oauth import store as store_mod

    rt = RefreshToken(token="rtok", client_id="client-a", scopes=["mcp"], expires_at=9999999999)
    store_mod.save_refresh_token(provider_mod.OAUTH_STORE_DB, rt)

    assert _run(provider.load_refresh_token(client, "rtok")) is not None
    assert _run(provider.load_refresh_token(other, "rtok")) is None
    assert _run(provider.load_refresh_token(client, "no-such")) is None


def test_exchange_refresh_token_rotates_tokens(provider):
    client = _client()
    from mcp.server.auth.provider import RefreshToken

    from core.oauth import store as store_mod

    rt = RefreshToken(token="rtok-old", client_id=client.client_id, scopes=["mcp"], expires_at=9999999999)
    store_mod.save_refresh_token(provider_mod.OAUTH_STORE_DB, rt)

    new_token = _run(provider.exchange_refresh_token(client, rt, ["mcp"]))

    assert new_token.access_token
    assert new_token.refresh_token != "rtok-old"
    assert store_mod.load_refresh_token(provider_mod.OAUTH_STORE_DB, "rtok-old") is None


def test_load_access_token_static_bearer_fallback(provider):
    token = _run(provider.load_access_token(AUTH_TOKEN))
    assert token is not None
    assert token.client_id == "static"


def test_load_access_token_wrong_static_and_missing_dynamic(provider):
    assert _run(provider.load_access_token("totally-wrong-token")) is None


def test_load_access_token_dynamic_valid(provider):
    from mcp.server.auth.provider import AccessToken

    from core.oauth import store as store_mod

    at = AccessToken(token="dyn-tok", client_id="c1", scopes=["mcp"], expires_at=int(9999999999))
    store_mod.save_access_token(provider_mod.OAUTH_STORE_DB, at)
    loaded = _run(provider.load_access_token("dyn-tok"))
    assert loaded is not None
    assert loaded.client_id == "c1"


def test_load_access_token_expired_dynamic_returns_none_and_deletes(provider):
    import time

    from mcp.server.auth.provider import AccessToken

    from core.oauth import store as store_mod

    at = AccessToken(token="expired-tok", client_id="c1", scopes=["mcp"], expires_at=int(time.time() - 10))
    store_mod.save_access_token(provider_mod.OAUTH_STORE_DB, at)
    assert _run(provider.load_access_token("expired-tok")) is None
    assert store_mod.load_access_token(provider_mod.OAUTH_STORE_DB, "expired-tok") is None


def test_revoke_token_deletes_access_and_refresh(provider):
    from mcp.server.auth.provider import AccessToken

    from core.oauth import store as store_mod

    at = AccessToken(token="shared-tok", client_id="c1", scopes=["mcp"], expires_at=9999999999)
    store_mod.save_access_token(provider_mod.OAUTH_STORE_DB, at)

    _run(provider.revoke_token(at))

    assert store_mod.load_access_token(provider_mod.OAUTH_STORE_DB, "shared-tok") is None


def test_exchange_identity_assertion_unsupported(provider):
    with pytest.raises(TokenError):
        _run(provider.exchange_identity_assertion(_client(), params=None))
