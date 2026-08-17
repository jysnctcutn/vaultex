"""VaultexOAuthProvider — the OAuthAuthorizationServerProvider implementation.

mcp.server.auth's TokenHandler/AuthorizationHandler already do the OAuth 2.1
protocol mechanics (PKCE verification, redirect_uri matching, code/token
expiry, client authentication) before calling into this provider — these
methods only need to handle storage and the single-user consent hand-off.
"""

import secrets
import time

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationParams,
    IdentityAssertionParams,
    RefreshToken,
    TokenError,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from ..config import AUTH_TOKEN, OAUTH_STORE_DB
from . import store
from .login import park_pending_login

_ACCESS_TOKEN_TTL = 3600  # seconds


class VaultexOAuthProvider:
    def __init__(self) -> None:
        store.init_db(OAUTH_STORE_DB)

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return store.get_client(OAUTH_STORE_DB, client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        store.save_client(OAUTH_STORE_DB, client_info)

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        login_id = park_pending_login(client, params)
        return f"/login?login_id={login_id}"

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str):
        code = store.load_auth_code(OAUTH_STORE_DB, authorization_code)
        if code is None or code.client_id != client.client_id:
            return None
        return code

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code) -> OAuthToken:
        # Single-use: consume it before minting tokens.
        store.delete_auth_code(OAUTH_STORE_DB, authorization_code.code)

        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        expires_at = int(time.time() + _ACCESS_TOKEN_TTL)

        store.save_access_token(
            OAUTH_STORE_DB,
            AccessToken(
                token=access_token,
                client_id=client.client_id,
                scopes=authorization_code.scopes,
                expires_at=expires_at,
                resource=authorization_code.resource,
                subject=authorization_code.subject,
            ),
        )
        store.save_refresh_token(
            OAUTH_STORE_DB,
            RefreshToken(
                token=refresh_token,
                client_id=client.client_id,
                scopes=authorization_code.scopes,
                subject=authorization_code.subject,
            ),
        )
        return OAuthToken(
            access_token=access_token,
            expires_in=_ACCESS_TOKEN_TTL,
            refresh_token=refresh_token,
            scope=" ".join(authorization_code.scopes) if authorization_code.scopes else None,
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str):
        token = store.load_refresh_token(OAUTH_STORE_DB, refresh_token)
        if token is None or token.client_id != client.client_id:
            return None
        return token

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token,
        scopes: list[str],
    ) -> OAuthToken:
        # Rotate both tokens on every refresh, per the SDK's SHOULD.
        store.delete_refresh_token(OAUTH_STORE_DB, refresh_token.token)

        new_access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(32)
        expires_at = int(time.time() + _ACCESS_TOKEN_TTL)

        store.save_access_token(
            OAUTH_STORE_DB,
            AccessToken(
                token=new_access,
                client_id=client.client_id,
                scopes=scopes,
                expires_at=expires_at,
                subject=refresh_token.subject,
            ),
        )
        store.save_refresh_token(
            OAUTH_STORE_DB,
            RefreshToken(
                token=new_refresh,
                client_id=client.client_id,
                scopes=scopes,
                subject=refresh_token.subject,
            ),
        )
        return OAuthToken(
            access_token=new_access,
            expires_in=_ACCESS_TOKEN_TTL,
            refresh_token=new_refresh,
            scope=" ".join(scopes) if scopes else None,
        )

    async def load_access_token(self, token: str) -> AccessToken | None:
        # Static MCP_AUTH_TOKEN keeps working as the bearer-token fallback
        # (local Claude Code, CLI tools, anything that can't do the browser
        # OAuth flow) alongside dynamically-issued OAuth access tokens.
        if AUTH_TOKEN and secrets.compare_digest(token, AUTH_TOKEN):
            return AccessToken(token=token, client_id="static", scopes=["mcp"], subject="jayson")

        access_token = store.load_access_token(OAUTH_STORE_DB, token)
        if access_token is None:
            return None
        if access_token.expires_at is not None and access_token.expires_at < time.time():
            store.delete_access_token(OAUTH_STORE_DB, token)
            return None
        return access_token

    async def revoke_token(self, token) -> None:
        store.delete_access_token(OAUTH_STORE_DB, token.token)
        store.delete_refresh_token(OAUTH_STORE_DB, token.token)

    async def exchange_identity_assertion(
        self,
        client: OAuthClientInformationFull,
        params: IdentityAssertionParams,
    ) -> OAuthToken:
        # Not offered — single-user server, no enterprise IdP to assert identity.
        raise TokenError(
            error="unsupported_grant_type",
            error_description="The JWT bearer grant is not supported by this authorization server",
        )
