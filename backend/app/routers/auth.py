from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import COOKIE_NAME, get_current_user, resolve_access
from app.models.user import User
from app.schemas.user import LoginRequest, UserRead
from app.utils import audit as audit_log
from app.utils import ratelimit, request_context
from app.utils.auth import create_access_token, verify_password
from app.utils import oidc
from app.models.oidc_session import OIDCSession

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/config")
async def config():
    return {
        "provider": settings.auth_provider,
        "login_url": "/api/v1/auth/oidc/login"
        if settings.auth_provider == "keycloak"
        else None,
    }


@router.post("/login", response_model=UserRead)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    if settings.auth_provider != "local":
        raise HTTPException(
            status_code=409,
            detail="Passwords are managed by Keycloak; use single sign-on",
        )
    ip = ratelimit.client_ip(request)
    ratelimit.enforce(f"login:ip:{ip}", max_attempts=10, window_seconds=60)
    ratelimit.enforce(f"login:user:{body.username}", max_attempts=5, window_seconds=60)
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        # Written in its own transaction: the 401 below rolls this request back.
        await audit_log.log_detached("auth.login_failed", f"username={body.username!r}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    await resolve_access(user, request, db)
    request_context.actor.set((user.id, user.username))
    await audit_log.log(db, "auth.login", f"{user.username} signed in")
    token = create_access_token(user.id, user.token_version)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_hours * 3600,
        path="/",
    )
    return user


@router.post("/logout")
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
):
    origin = request.headers.get("origin")
    if origin and origin != settings.frontend_origin.rstrip("/"):
        raise HTTPException(status_code=403, detail="Invalid request origin")
    logout_url = None
    if settings.auth_provider == "keycloak":
        cookie = request.cookies.get(COOKIE_NAME, "")
        session = (
            await db.get(OIDCSession, oidc.token_hash(cookie))
            if cookie.startswith(oidc.SESSION_PREFIX)
            else None
        )
        hint = None
        if session:
            try:
                hint = oidc.cipher().decrypt(session.id_token.encode()).decode()
            except oidc.VALIDATION_ERRORS:
                pass
            await db.delete(session)
        request.session.clear()
        try:
            redirect = await oidc.client().logout_redirect(
                request,
                post_logout_redirect_uri=settings.frontend_origin.rstrip("/")
                + "/api/v1/auth/oidc/logged-out",
                id_token_hint=hint,
                client_id=settings.oidc_client_id,
            )
            logout_url = redirect.headers["location"]
        except (httpx.HTTPError, *oidc.VALIDATION_ERRORS):
            # Local logout must still work during an identity-provider outage.
            request.session.clear()
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    response.headers["Cache-Control"] = "no-store"
    return {"message": "Logged out", "logout_url": logout_url}


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)):
    return user
