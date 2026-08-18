"""The single-user password-gate consent screen — replaces the Cloudflare
Worker's /authorize HTML form. VaultexOAuthProvider.authorize() parks the
validated OAuth request here (keyed by login_id) instead of rendering
anything itself; this is the SDK's documented pattern for a provider that
redirects to a second handler to complete authorization.
"""

import secrets
import time

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import AuthorizationParams, construct_redirect_uri
from mcp.shared.auth import OAuthClientInformationFull

from ..config import AUTHORIZE_PASSWORD, OAUTH_STORE_DB
from . import store

_LOGIN_TTL = 600  # seconds

# login_id -> (client, params, expires_at). In-memory and short-lived on
# purpose: losing this on a restart mid-flow just means the user retries.
_pending_logins: dict[str, tuple[OAuthClientInformationFull, AuthorizationParams, float]] = {}


def park_pending_login(client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
    login_id = secrets.token_urlsafe(16)
    _pending_logins[login_id] = (client, params, time.time() + _LOGIN_TTL)
    return login_id


# DCR is unauthenticated by spec, so nothing stops a stranger from parking
# their own login and hammering this password field. The
# ALLOWED_REDIRECT_HOSTS check in provider.py stops them from ever
# *completing* a flow, but not from guessing. Two independent caps below,
# in-memory like _pending_logins above (same "lost on restart is fine"
# reasoning, since this is a single-user server):
_MAX_ATTEMPTS_PER_LOGIN = 5
_MAX_ATTEMPTS_PER_IP = 10
_IP_LOCKOUT_WINDOW = 900  # seconds

_login_attempts: dict[str, int] = {}
_ip_failures: dict[str, list[float]] = {}


def _record_ip_failure(ip: str) -> None:
    now = time.time()
    fails = [t for t in _ip_failures.get(ip, []) if now - t < _IP_LOCKOUT_WINDOW]
    fails.append(now)
    _ip_failures[ip] = fails


def _ip_locked_out(ip: str) -> bool:
    now = time.time()
    fails = [t for t in _ip_failures.get(ip, []) if now - t < _IP_LOCKOUT_WINDOW]
    _ip_failures[ip] = fails
    return len(fails) >= _MAX_ATTEMPTS_PER_IP


def _password_form(login_id: str, error: str | None = None) -> str:
    error_html = f'<p style="color:#c00">{error}</p>' if error else ""
    return f"""<!doctype html>
<html><head><title>Vaultex — Sign in</title></head>
<body style="font-family: system-ui, sans-serif; max-width: 360px; margin: 4rem auto; padding: 0 1rem;">
  <h1>Vaultex</h1>
  <p>Enter the access password to authorize this client.</p>
  {error_html}
  <form method="post" action="/login?login_id={login_id}">
    <input type="password" name="password" autofocus autocomplete="current-password"
           style="width:100%; padding:.5rem; font-size:1rem; box-sizing:border-box;">
    <button type="submit" style="margin-top:.75rem; padding:.5rem 1rem;">Authorize</button>
  </form>
</body></html>"""


async def login_handler(request: Request) -> Response:
    login_id = request.query_params.get("login_id", "")
    pending = _pending_logins.get(login_id)
    if pending is None or pending[2] < time.time():
        _pending_logins.pop(login_id, None)
        _login_attempts.pop(login_id, None)
        return HTMLResponse(
            "This login link has expired or is invalid. Go back to the client and try again.",
            status_code=400,
        )
    client, params, _expires_at = pending

    if request.method == "GET":
        return HTMLResponse(_password_form(login_id))

    ip = request.client.host if request.client else "unknown"
    if _ip_locked_out(ip):
        return HTMLResponse(
            "Too many failed attempts from this address. Try again later.", status_code=429,
        )

    form = await request.form()
    password = form.get("password")
    if (
        not AUTHORIZE_PASSWORD
        or not isinstance(password, str)
        or not secrets.compare_digest(password, AUTHORIZE_PASSWORD)
    ):
        _record_ip_failure(ip)
        attempts = _login_attempts.get(login_id, 0) + 1
        if attempts >= _MAX_ATTEMPTS_PER_LOGIN:
            _pending_logins.pop(login_id, None)
            _login_attempts.pop(login_id, None)
            return HTMLResponse(
                "Too many failed attempts. Go back to the client and try again.", status_code=429,
            )
        _login_attempts[login_id] = attempts
        return HTMLResponse(_password_form(login_id, error="Wrong password — try again."), status_code=401)

    code = store.new_authorization_code(OAUTH_STORE_DB, client, params, subject="jayson")
    del _pending_logins[login_id]
    _login_attempts.pop(login_id, None)
    return RedirectResponse(
        construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state),
        status_code=302,
        headers={"Cache-Control": "no-store"},
    )
