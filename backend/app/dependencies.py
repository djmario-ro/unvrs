from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from app.models.property import Property, PropertyMembership, MANAGERS, RECEPTION
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.config import settings
from app.models.user import User
from app.utils import request_context
from app.utils.auth import decode_token

COOKIE_NAME = "gh_session"


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> User:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    if settings.auth_provider == "keycloak":
        from app.utils import oidc

        if not token.startswith(oidc.SESSION_PREFIX):
            raise HTTPException(status_code=401, detail="Sign in with Keycloak")
        user = await oidc.current_user(db, token)
        request_context.actor.set((user.id, user.username))
        return await resolve_access(user, request, db)
    payload = decode_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session"
        )
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid session")
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    # A token minted before the last password change is no longer valid.
    if payload.get("tv") != user.token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired"
        )
    request_context.actor.set((user.id, user.username))
    return await resolve_access(user, request, db)


async def resolve_access(user: User, request: Request, db: AsyncSession) -> User:
    rows = (
        await db.execute(
            select(PropertyMembership, Property)
            .join(Property, Property.id == PropertyMembership.property_id)
            .where(PropertyMembership.user_id == user.id)
            .order_by(Property.id)
        )
    ).all()
    if not rows:
        raise HTTPException(403, "No property access assigned; contact an owner")
    requested = request.headers.get("X-Property-ID")
    try:
        property_id = int(requested) if requested else rows[0][1].id
    except ValueError:
        raise HTTPException(400, "Invalid property ID")
    active = next((m for m, p in rows if p.id == property_id), None)
    if active is None:
        raise HTTPException(403, "No access to this property")
    user._active_roles = active.roles
    user._active_property_id = property_id
    user._properties = [
        {"id": p.id, "name": p.name, "slug": p.slug, "roles": m.roles} for m, p in rows
    ]
    db.info["property_id"] = property_id
    request_context.property_id.set(property_id)
    return user


def require_roles(*allowed: str):
    async def check(user: User = Depends(get_current_user)) -> User:
        if not set(user.roles).intersection(allowed):
            raise HTTPException(403, "This role does not allow this operation")
        return user

    return check


require_admin = require_roles(*MANAGERS)
require_reception = require_roles(*RECEPTION)
require_housekeeping = require_roles(*MANAGERS, "housekeeping")
require_maintenance = require_roles(*MANAGERS, "maintenance")
