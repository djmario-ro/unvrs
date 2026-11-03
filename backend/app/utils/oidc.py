"""OIDC identity verification and encrypted, revocable backend sessions."""
import base64
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import hmac
import secrets

from authlib.common.errors import AuthlibBaseError
from authlib.integrations.starlette_client import OAuth
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
import httpx
from joserfc.errors import JoseError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.oidc_session import OIDCSession
from app.models.user import User

SESSION_PREFIX = "oidc."
VALIDATION_ERRORS = (AuthlibBaseError, JoseError, ValueError, KeyError, InvalidToken)


@lru_cache(maxsize=8)
def _client(issuer: str, client_id: str, client_secret: str):
    registry = OAuth()
    return registry.register(
        "keycloak",
        client_id=client_id,
        client_secret=client_secret,
        server_metadata_url=issuer + "/.well-known/openid-configuration",
        client_kwargs={
            "scope": "openid profile email",
            "code_challenge_method": "S256",
            "token_endpoint_auth_method": "client_secret_basic",
            "timeout": 10,
        },
    )


def client():
    return _client(settings.oidc_issuer.rstrip("/"), settings.oidc_client_id, settings.oidc_client_secret)


def claims_options():
    return {"iss": {"essential": True, "values": [settings.oidc_issuer.rstrip("/")]}}


def cipher() -> Fernet:
    key = hmac.digest(settings.secret_key.encode(), b"unvrs-oidc-token-encryption-v1", "sha256")
    return Fernet(base64.urlsafe_b64encode(key))


def token_hash(cookie: str) -> str:
    return hashlib.sha256(cookie.encode()).hexdigest()


def provider_expiry(token: dict) -> datetime:
    # Check the central identity at least every five minutes, regardless of an
    # accidentally long provider access-token lifetime.
    seconds = max(1, min(int(token["expires_in"]), 300))
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


async def create_session(db: AsyncSession, user: User, token: dict) -> str:
    now = datetime.now(timezone.utc)
    await db.execute(delete(OIDCSession).where(OIDCSession.expires_at <= now))
    cookie = SESSION_PREFIX + secrets.token_urlsafe(32)
    encryption = cipher()
    db.add(OIDCSession(
        token_hash=token_hash(cookie), user_id=user.id, token_version=user.token_version,
        refresh_token=encryption.encrypt(token["refresh_token"].encode()).decode(),
        id_token=encryption.encrypt(token["id_token"].encode()).decode(),
        issuer=user.oidc_issuer, subject=user.oidc_subject,
        provider_expires_at=provider_expiry(token),
        expires_at=now + timedelta(hours=settings.access_token_expire_hours),
    ))
    return cookie


async def invalid_session(db: AsyncSession, session: OIDCSession):
    await db.delete(session)
    # Persist revocation even though the authentication exception rolls back
    # the request transaction. No application operation has run at this point.
    await db.commit()
    raise HTTPException(status_code=401, detail="Session expired; sign in again")


async def current_user(db: AsyncSession, cookie: str) -> User:
    # Serialize concurrent refresh attempts for the same rotating refresh token.
    session = (await db.execute(select(OIDCSession).where(
        OIDCSession.token_hash == token_hash(cookie)
    ).with_for_update())).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = await db.get(User, session.user_id)
    if (user is None or session.expires_at <= datetime.now(timezone.utc)
            or session.token_version != user.token_version
            or session.issuer != settings.oidc_issuer.rstrip("/")
            or session.issuer != user.oidc_issuer or session.subject != user.oidc_subject):
        await invalid_session(db, session)
    if session.provider_expires_at <= datetime.now(timezone.utc):
        try:
            encryption = cipher()
            oauth = client()
            token = await oauth.fetch_access_token(
                grant_type="refresh_token",
                refresh_token=encryption.decrypt(session.refresh_token.encode()).decode(),
            )
            # Refresh is an authenticated server-to-server exchange; unlike the
            # browser callback, there is no new browser nonce to verify here.
            identity = await oauth.parse_id_token(token, nonce=None, claims_options=claims_options(), leeway=30)
            if not identity or identity["iss"] != session.issuer or identity["sub"] != session.subject:
                raise ValueError("Provider identity changed")
            session.refresh_token = encryption.encrypt(token["refresh_token"].encode()).decode()
            session.id_token = encryption.encrypt(token["id_token"].encode()).decode()
            session.provider_expires_at = provider_expiry(token)
        except httpx.HTTPError:
            # An IdP outage must not silently authenticate expired identities or
            # destroy their session; retry when the provider becomes available.
            raise HTTPException(status_code=503, detail="Sign-in service unavailable; try again")
        except VALIDATION_ERRORS:
            await invalid_session(db, session)
    # Persist rotating refresh tokens before a downstream authorization or
    # business validation error can roll back its separate transaction. Release
    # the session lock here as well, rather than holding it through app work.
    await db.commit()
    return user
