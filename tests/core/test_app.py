from starlette.testclient import TestClient

import core.app as app_mod
from core.app import build_app
from core.config import AUTH_TOKEN


def test_build_app_rejects_unauthenticated_request_with_security_headers():
    app = build_app()
    client = TestClient(app)
    resp = client.get("/mcp")
    # No bearer token: BearerAuthMiddleware (innermost) rejects before
    # routing resolves, and SecurityHeadersMiddleware (wraps it) still
    # attaches headers to that 401.
    assert resp.status_code == 401
    assert resp.headers["X-Content-Type-Options"] == "nosniff"


def test_build_app_accepts_valid_bearer_token():
    app = build_app()
    with TestClient(app) as client:
        resp = client.get("/mcp", headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    assert resp.status_code != 401


def test_build_app_skips_reindex_lifespan_when_no_embeddings_index_exists():
    app = build_app()
    default_lifespan = app.router.lifespan_context
    # EMBEDDINGS_DB_PATH doesn't exist in the test env (see conftest.py), so
    # build_app() must not have swapped in the reindex-wrapping lifespan.
    assert default_lifespan.__name__ != "lifespan_with_reindex"


def test_build_app_wraps_lifespan_when_embeddings_index_exists(monkeypatch, tmp_path):
    fake_db = tmp_path / "vault_embeddings.db"
    fake_db.write_text("")
    monkeypatch.setattr(app_mod, "EMBEDDINGS_DB_PATH", fake_db)
    monkeypatch.setattr(app_mod, "_SEMANTIC_DEPS_AVAILABLE", True)

    app = build_app()

    assert app.router.lifespan_context.__name__ == "lifespan_with_reindex"


def test_build_app_reindex_lifespan_starts_and_cancels_task_cleanly(monkeypatch, tmp_path):
    fake_db = tmp_path / "vault_embeddings.db"
    fake_db.write_text("")
    monkeypatch.setattr(app_mod, "EMBEDDINGS_DB_PATH", fake_db)
    monkeypatch.setattr(app_mod, "_SEMANTIC_DEPS_AVAILABLE", True)
    # Long interval: the periodic task should sit sleeping for the whole
    # test, so this only exercises task creation + the finally-cancel path
    # on lifespan exit, never an actual sweep.
    monkeypatch.setattr(app_mod, "REINDEX_INTERVAL_SECONDS", 300)

    app = build_app()
    with TestClient(app):
        pass  # lifespan startup/shutdown both fire around this block
