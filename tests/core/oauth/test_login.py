import pytest
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.testclient import TestClient

import core.oauth.login as login_mod
from core.oauth import store
from core.oauth.login import login_handler, park_pending_login
from mcp.server.auth.provider import AuthorizationParams
from mcp.shared.auth import OAuthClientInformationFull


@pytest.fixture
def oauth_env(monkeypatch, tmp_path):
    db_path = tmp_path / "oauth_store.db"
    store.init_db(db_path)
    monkeypatch.setattr(login_mod, "OAUTH_STORE_DB", db_path)
    monkeypatch.setattr(login_mod, "AUTHORIZE_PASSWORD", "correct-horse")
    # These are module-level mutable dicts shared across the whole test
    # session; clear them before and after so tests don't leak state into
    # each other via a shared login_id/IP.
    login_mod._pending_logins.clear()
    login_mod._login_attempts.clear()
    login_mod._ip_failures.clear()
    yield db_path
    login_mod._pending_logins.clear()
    login_mod._login_attempts.clear()
    login_mod._ip_failures.clear()


@pytest.fixture
def client_app():
    app = Starlette(routes=[Route("/login", login_handler, methods=["GET", "POST"])])
    return TestClient(app)


def _client_info():
    return OAuthClientInformationFull(client_id="test-client", redirect_uris=["https://claude.ai/callback"])


def _params():
    return AuthorizationParams(
        state="s1", scopes=["mcp"], code_challenge="cc",
        redirect_uri="https://claude.ai/callback", redirect_uri_provided_explicitly=True,
    )


def test_park_pending_login_returns_id():
    login_id = park_pending_login(_client_info(), _params())
    assert login_id
    assert login_id in login_mod._pending_logins


def test_login_get_unknown_id_returns_400(oauth_env, client_app):
    resp = client_app.get("/login", params={"login_id": "no-such-id"})
    assert resp.status_code == 400


def test_login_get_expired_returns_400(oauth_env, client_app):
    login_id = park_pending_login(_client_info(), _params())
    client, params, _ = login_mod._pending_logins[login_id]
    login_mod._pending_logins[login_id] = (client, params, 0)  # already expired
    resp = client_app.get("/login", params={"login_id": login_id})
    assert resp.status_code == 400
    assert login_id not in login_mod._pending_logins


def test_login_get_valid_id_renders_form(oauth_env, client_app):
    login_id = park_pending_login(_client_info(), _params())
    resp = client_app.get("/login", params={"login_id": login_id})
    assert resp.status_code == 200
    assert "Enter the access password" in resp.text


def test_login_post_wrong_password_returns_401(oauth_env, client_app):
    login_id = park_pending_login(_client_info(), _params())
    resp = client_app.post("/login", params={"login_id": login_id}, data={"password": "nope"})
    assert resp.status_code == 401
    assert "Wrong password" in resp.text
    assert login_id in login_mod._pending_logins  # still parked, one attempt used


def test_login_post_correct_password_redirects_with_code(oauth_env, client_app):
    login_id = park_pending_login(_client_info(), _params())
    resp = client_app.post(
        "/login", params={"login_id": login_id}, data={"password": "correct-horse"}, follow_redirects=False
    )
    assert resp.status_code == 302
    assert "code=" in resp.headers["location"]
    assert login_id not in login_mod._pending_logins


def test_login_post_lockout_after_max_attempts_per_login(oauth_env, client_app):
    login_id = park_pending_login(_client_info(), _params())
    for _ in range(login_mod._MAX_ATTEMPTS_PER_LOGIN - 1):
        resp = client_app.post("/login", params={"login_id": login_id}, data={"password": "nope"})
        assert resp.status_code == 401
    # Final attempt trips the per-login cap and discards the pending login.
    resp = client_app.post("/login", params={"login_id": login_id}, data={"password": "nope"})
    assert resp.status_code == 429
    assert login_id not in login_mod._pending_logins


def test_login_post_ip_lockout_across_logins(oauth_env, client_app):
    # Different login_ids, same client IP (TestClient's default) -- the IP
    # cap is independent of and lower-friction to trip than the per-login one.
    for _ in range(login_mod._MAX_ATTEMPTS_PER_IP):
        login_id = park_pending_login(_client_info(), _params())
        client_app.post("/login", params={"login_id": login_id}, data={"password": "nope"})

    another_id = park_pending_login(_client_info(), _params())
    resp = client_app.post("/login", params={"login_id": another_id}, data={"password": "correct-horse"})
    assert resp.status_code == 429
    assert "Too many failed attempts from this address" in resp.text


def test_login_post_missing_password_field_treated_as_failure(oauth_env, client_app):
    login_id = park_pending_login(_client_info(), _params())
    resp = client_app.post("/login", params={"login_id": login_id}, data={})
    assert resp.status_code == 401
