from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import COOKIE_NAME, resolve_access
from app.models.user import User
from app.models.property import PropertyMembership
from app.utils import audit as audit_log
from app.utils import oidc, ratelimit, request_context

router = APIRouter(prefix="/auth/oidc", tags=["auth"])
NO_CACHE = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"}


def enabled():
    if settings.auth_provider != "keycloak":
        raise HTTPException(status_code=404, detail="OIDC sign-in is not enabled")


def redirect_login(error: str | None = None):
    target = settings.frontend_origin.rstrip("/") + "/login"
    if error:
        target += "?error=" + error
    return RedirectResponse(target, status_code=303, headers=NO_CACHE)


@router.get("/login")
async def login(request: Request, switch_account: bool = False):
    enabled()
    ratelimit.enforce(
        f"oidc:ip:{ratelimit.client_ip(request)}", max_attempts=20, window_seconds=60
    )
    callback = settings.frontend_origin.rstrip("/") + "/api/v1/auth/oidc/callback"
    try:
        response = await oidc.client().authorize_redirect(
            request, callback, **({"prompt": "login"} if switch_account else {})
        )
    except httpx.HTTPError:
        raise HTTPException(
            status_code=503, detail="Sign-in service unavailable; try again"
        )
    response.headers.update(NO_CACHE)
    return response


@router.get("/callback")
async def callback(request: Request, db: AsyncSession = Depends(get_db)):
    enabled()
    try:
        token = await oidc.client().authorize_access_token(
            request, claims_options=oidc.claims_options(), leeway=30
        )
        identity = token.get("userinfo")
        if not identity or identity["iss"] != settings.oidc_issuer.rstrip("/"):
            raise ValueError("Missing verified OIDC identity")
        user = (
            await db.execute(
                select(User).where(
                    User.oidc_issuer == identity["iss"],
                    User.oidc_subject == identity["sub"],
                )
            )
        ).scalar_one_or_none()
        if user is None or not await db.scalar(
            select(PropertyMembership.user_id)
            .where(PropertyMembership.user_id == user.id)
            .limit(1)
        ):
            request.session.clear()
            await audit_log.log(
                db, "auth.oidc_denied", "Verified identity has no application access"
            )
            return redirect_login("access_denied")
        await resolve_access(user, request, db)
        cookie = await oidc.create_session(db, user, token)
    except (httpx.HTTPError, *oidc.VALIDATION_ERRORS):
        request.session.clear()
        await audit_log.log(db, "auth.oidc_failed", "OIDC callback validation failed")
        return redirect_login("oidc_failed")
    request.session.clear()
    request_context.actor.set((user.id, user.username))
    await audit_log.log(db, "auth.login", f"{user.username} signed in with Keycloak")
    response = RedirectResponse(
        settings.frontend_origin.rstrip("/") + "/app", status_code=303, headers=NO_CACHE
    )
    response.set_cookie(
        COOKIE_NAME,
        cookie,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_hours * 3600,
        path="/",
    )
    return response


@router.get("/logged-out")
async def logged_out(request: Request):
    enabled()
    try:
        await oidc.client().validate_logout_response(request)
    except oidc.VALIDATION_ERRORS:
        request.session.clear()
        return redirect_login("logout_failed")
    request.session.clear()
    return redirect_login()
