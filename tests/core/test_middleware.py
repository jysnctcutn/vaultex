import time

from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from core.config import AUTH_TOKEN
from core.middleware import BearerAuthMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware


async def _ok(request):
    return PlainTextResponse("ok")


def _make_app(*middlewares):
    app = Starlette(routes=[Route("/x", _ok)])
    for mw, kwargs in middlewares:
        app.add_middleware(mw, **kwargs)
    return app


def test_bearer_auth_rejects_missing_header():
    client = TestClient(_make_app((BearerAuthMiddleware, {})))
    resp = client.get("/x")
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


def test_bearer_auth_rejects_wrong_token():
    client = TestClient(_make_app((BearerAuthMiddleware, {})))
    resp = client.get("/x", headers={"Authorization": "Bearer wrong-token"})
    assert resp.status_code == 401


def test_bearer_auth_accepts_correct_token():
    client = TestClient(_make_app((BearerAuthMiddleware, {})))
    resp = client.get("/x", headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
    assert resp.status_code == 200
    assert resp.text == "ok"


def test_rate_limit_allows_under_the_cap():
    client = TestClient(_make_app((RateLimitMiddleware, {"max_requests": 3, "window_seconds": 60})))
    for _ in range(3):
        assert client.get("/x").status_code == 200


def test_rate_limit_blocks_over_the_cap():
    client = TestClient(_make_app((RateLimitMiddleware, {"max_requests": 2, "window_seconds": 60})))
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 200
    resp = client.get("/x")
    assert resp.status_code == 429
    assert resp.json() == {"error": "rate limited"}


def test_rate_limit_window_resets_old_hits():
    client = TestClient(_make_app((RateLimitMiddleware, {"max_requests": 1, "window_seconds": 0.05})))
    assert client.get("/x").status_code == 200
    time.sleep(0.1)
    assert client.get("/x").status_code == 200


def test_security_headers_present():
    client = TestClient(_make_app((SecurityHeadersMiddleware, {})))
    resp = client.get("/x")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "camera=()" in resp.headers["Permissions-Policy"]
