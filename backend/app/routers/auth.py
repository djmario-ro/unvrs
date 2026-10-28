from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import COOKIE_NAME, get_current_user
from app.models.user import User
from app.schemas.user import LoginRequest, UserRead
from app.utils import audit as audit_log
from app.utils import ratelimit, request_context
from app.utils.auth import create_access_token, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserRead)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
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
async def logout(response: Response):
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"message": "Logged out"}


@router.get("/me", response_model=UserRead)
async def me(user: User = Depends(get_current_user)):
    return user
