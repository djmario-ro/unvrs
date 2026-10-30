import logging
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.dependencies import get_current_user, require_admin
from app.models.user import User
from app.routers import (
    assignments,
    audit,
    auth,
    dashboard,
    door,
    guests,
    messaging,
    rooms,
    users,
)
from app.utils import ratelimit, request_context
from app.utils.auth import hash_password, verify_password

# Surface the app's own INFO logs (e.g. messaging mocks) on stdout, scoped so
# it doesn't duplicate SQLAlchemy's echo output.
_app_logger = logging.getLogger("app")
if not _app_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s - %(message)s"))
    _app_logger.addHandler(_handler)
    _app_logger.setLevel(logging.INFO)
    _app_logger.propagate = False


_DEFAULT_SECRET = "change-me-in-production-please"


def _check_production_secrets() -> None:
    """Refuse to boot in production with default/placeholder secrets."""
    if settings.debug:
        return
    problems = []
    if settings.secret_key == _DEFAULT_SECRET:
        problems.append("SECRET_KEY is still the default placeholder")
    if settings.admin_password == "admin":
        problems.append("ADMIN_PASSWORD is still the default 'admin'")
    if problems:
        raise RuntimeError(
            "Refusing to start: "
            + "; ".join(problems)
            + ". Set these via environment variables (or set DEBUG=true for local dev)."
        )


async def _ensure_admin() -> None:
    """Keep the env-defined admin account in sync on every startup.

    The master admin is controlled entirely by ADMIN_USERNAME / ADMIN_PASSWORD:
    it is created if missing and its password/role are reset to match the env.
    Other users are managed in-app by admins.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == settings.admin_username)
        )
        user = result.scalar_one_or_none()
        if user is None:
            db.add(
                User(
                    username=settings.admin_username,
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                )
            )
            _app_logger.info("Created admin user '%s'", settings.admin_username)
        else:
            if not verify_password(settings.admin_password, user.password_hash):
                user.token_version += 1
                user.password_hash = hash_password(settings.admin_password)
            user.role = "admin"
            _app_logger.info("Synced admin user '%s' from env", settings.admin_username)
        await db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by the Kubernetes migration Job before rollout.
    # For local development, run `alembic upgrade head` before starting the API.
    _check_production_secrets()
    await _ensure_admin()
    yield
    await engine.dispose()


app = FastAPI(
    title="Guesthouse Management API",
    version="1.0.0",
    lifespan=lifespan,
)


# Unique-constraint names (Postgres defaults) → messages staff can act on.
_UNIQUE_MESSAGES = {
    "guests_email_key": "A guest with this email already exists",
    "rooms_name_key": "A room with this name already exists",
    "ix_users_username": "Username already exists",
}


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Turn constraint violations into 409s instead of 500s.

    The session is rolled back by get_db; this only shapes the response.
    """
    # SQLAlchemy wraps the asyncpg error (which carries constraint_name) in
    # its DBAPI adapter; look through both, then fall back to the message.
    orig = getattr(exc, "orig", None)
    constraint = ""
    for err in (orig, getattr(orig, "__cause__", None)):
        constraint = getattr(err, "constraint_name", None) or constraint
    if not constraint:
        m = re.search(r'constraint "([^"]+)"', str(orig))
        constraint = m.group(1) if m else ""
    if constraint in _UNIQUE_MESSAGES:
        detail = _UNIQUE_MESSAGES[constraint]
    elif "foreign key" in str(orig).lower():
        detail = "A referenced record does not exist"
    else:
        detail = "Conflicts with an existing record"
    return JSONResponse(status_code=409, content={"detail": detail})

@app.middleware("http")
async def remember_client_ip(request: Request, call_next):
    """Expose the client IP to the audit log for the duration of the request."""
    token = request_context.client_ip.set(ratelimit.client_ip(request))
    try:
        return await call_next(request)
    finally:
        request_context.client_ip.reset(token)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Public: authentication and the guest-facing door client.
app.include_router(auth.router, prefix="/api/v1")
app.include_router(door.router, prefix="/api/v1")

# Any signed-in staff member (admin or front desk).
_staff = [Depends(get_current_user)]
app.include_router(dashboard.router, prefix="/api/v1", dependencies=_staff)
app.include_router(guests.router, prefix="/api/v1", dependencies=_staff)
app.include_router(assignments.router, prefix="/api/v1", dependencies=_staff)
app.include_router(rooms.router, prefix="/api/v1", dependencies=_staff)

# Property management — admin only.
_admin = [Depends(require_admin)]
app.include_router(users.router, prefix="/api/v1")  # router already requires admin
app.include_router(audit.router, prefix="/api/v1", dependencies=_admin)
app.include_router(messaging.router, prefix="/api/v1", dependencies=_admin)


@app.get("/health")
async def health():
    return {"status": "ok"}
