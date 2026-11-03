import logging
import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from starlette.middleware.sessions import SessionMiddleware
from urllib.parse import urlsplit

from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.dependencies import get_current_user, require_admin, require_reception
from app.models.user import User
from app.models.property import PropertyMembership
from app.routers import (
    assignments,
    audit,
    auth,
    dashboard,
    door,
    guests,
    messaging,
    oidc,
    properties,
    operations,
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
    _handler.setFormatter(
        logging.Formatter("%(levelname)s:     %(name)s - %(message)s")
    )
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
    if settings.auth_provider == "local" and settings.admin_password == "admin":
        problems.append("ADMIN_PASSWORD is still the default 'admin'")
    if settings.auth_provider == "keycloak":
        issuer = urlsplit(settings.oidc_issuer)
        if (
            issuer.scheme != "https"
            or not issuer.netloc
            or issuer.query
            or issuer.fragment
            or issuer.username
        ):
            problems.append("OIDC_ISSUER must be a fixed HTTPS realm URL")
        if (
            not settings.oidc_client_id
            or not settings.oidc_client_secret
            or not settings.oidc_bootstrap_subject
        ):
            problems.append(
                "OIDC_CLIENT_ID, OIDC_CLIENT_SECRET and OIDC_BOOTSTRAP_SUBJECT are required"
            )
    if problems:
        raise RuntimeError(
            "Refusing to start: "
            + "; ".join(problems)
            + ". Set these via environment variables (or set DEBUG=true for local dev)."
        )


async def _ensure_admin() -> None:
    """Keep the env-defined admin account in sync on every startup.

    Identity binding stays explicit. Initial property access is granted only
    when creating the account: a restart never restores a revoked membership.
    Local-mode passwords remain controlled by ADMIN_PASSWORD.
    """
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(User).where(User.username == settings.admin_username)
        )
        user = result.scalar_one_or_none()
        created = user is None
        if settings.auth_provider == "keycloak":
            expected = (
                settings.oidc_issuer.rstrip("/"),
                settings.oidc_bootstrap_subject,
            )
            if user is None:
                user = User(
                    username=settings.admin_username, password_hash=None, role="admin"
                )
                db.add(user)
            if (
                user.oidc_issuer is not None
                and (user.oidc_issuer, user.oidc_subject) != expected
            ):
                raise RuntimeError(
                    "Refusing to rebind the bootstrap administrator to a different identity"
                )
            if user.oidc_subject is None:
                user.oidc_issuer, user.oidc_subject = expected
                user.token_version = (user.token_version or 0) + 1
            user.role = "admin"
            await db.flush()
            if created:
                db.add(
                    PropertyMembership(
                        user_id=user.id, property_id=1, roles=["administrator"]
                    )
                )
            await db.commit()
            _app_logger.info(
                "Verified explicit Keycloak mapping for administrator '%s'",
                settings.admin_username,
            )
            return
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
        await db.flush()
        seeded = (
            await db.execute(
                select(User).where(User.username == settings.admin_username)
            )
        ).scalar_one()
        if created:
            db.add(
                PropertyMembership(
                    user_id=seeded.id, property_id=1, roles=["administrator"]
                )
            )
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

# Only a short-lived signed state/nonce/PKCE cookie is stored here. OAuth access
# and refresh tokens are kept encrypted in the backend database, not this cookie.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="gh_oidc_flow",
    max_age=300,
    path="/api/v1/auth/oidc",
    same_site="lax",
    https_only=settings.cookie_secure,
)


# Unique-constraint names (Postgres defaults) → messages staff can act on.
_UNIQUE_MESSAGES = {
    "uq_guests_property_email": "A guest with this email already exists",
    "uq_rooms_property_name": "A room with this name already exists",
    "ix_users_username": "Username already exists",
    "uq_users_oidc_identity": "This Keycloak identity already has application access",
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
    tenant_token = request_context.property_id.set(None)
    token = request_context.client_ip.set(ratelimit.client_ip(request))
    try:
        return await call_next(request)
    finally:
        request_context.client_ip.reset(token)
        request_context.property_id.reset(tenant_token)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Property-ID"],
)

# Public: authentication and the guest-facing door client.
app.include_router(auth.router, prefix="/api/v1")
app.include_router(oidc.router, prefix="/api/v1")
app.include_router(door.router, prefix="/api/v1")

app.include_router(properties.router, prefix="/api/v1")
app.include_router(operations.router, prefix="/api/v1")

# Any signed-in staff member (admin or front desk).
_staff = [Depends(require_reception)]
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
