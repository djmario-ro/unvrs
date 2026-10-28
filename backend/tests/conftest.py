"""Integration tests against a real Postgres.

Point TEST_DATABASE_URL at an empty, disposable database (default below
matches a local `postgres:16-alpine` on port 5433). The schema is rebuilt
from the Alembic migrations once per session — never run this against a
database you care about.
"""
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://guesthouse:guesthouse@localhost:5433/guesthouse_test",
)

# Settings are read at import time, so configure the environment before the
# app is imported anywhere.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL
os.environ["DEBUG"] = "false"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production-0123456789"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD"] = "test-admin-password"
os.environ["TRUSTED_PROXIES"] = "private,cloudflare"
os.environ.setdefault("WHATSAPP_SERVICE_URL", "")
os.environ.setdefault("SMS_GATEWAY_URL", "")

import httpx  # noqa: E402

from app.main import _ensure_admin, app  # noqa: E402
from app.utils import ratelimit  # noqa: E402


def _alembic(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        check=True,
        capture_output=True,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
    )


async def _drop_schema() -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    """Rebuild the schema from migrations so tests see exactly what prod gets.

    Drop everything rather than `alembic downgrade base`: downgrades may
    legitimately refuse data left by a previous run.
    """
    import asyncio

    asyncio.run(_drop_schema())
    _alembic("upgrade", "head")


@pytest.fixture(scope="session", autouse=True)
async def seeded_admin(migrated_database):
    await _ensure_admin()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    ratelimit._windows.clear()
    yield
    ratelimit._windows.clear()


@pytest.fixture
async def anon():
    """Unauthenticated client (door, login)."""
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest.fixture
async def admin(anon):
    """Client logged in as the env master admin."""
    r = await anon.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    assert r.status_code == 200, r.text
    yield anon


@pytest.fixture
async def frontdesk(admin):
    """A fresh front-desk user, logged in on its own client."""
    name = f"desk-{datetime.now().timestamp()}"
    r = await admin.post(
        "/api/v1/users",
        json={"username": name, "password": "desk-password", "role": "frontdesk"},
    )
    assert r.status_code == 201, r.text
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/api/v1/auth/login", json={"username": name, "password": "desk-password"}
        )
        assert r.status_code == 200, r.text
        yield c


# --- data helpers -----------------------------------------------------------

NOW = lambda: datetime.now(tz=timezone.utc)  # noqa: E731


def days(n: float) -> str:
    """ISO timestamp n days from now (negative = past)."""
    return (NOW() + timedelta(days=n)).isoformat()


@pytest.fixture
async def guest(admin):
    r = await admin.post(
        "/api/v1/guests",
        json={"firstname": "Ana", "lastname": "Pop", "phone": "0743000000"},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
async def room(admin):
    return await make_room(admin)


async def make_room(client):
    r = await client.post(
        "/api/v1/rooms", json={"name": f"Room {datetime.now().timestamp()}"}
    )
    assert r.status_code == 201, r.text
    return r.json()


async def book(client, guest, room, check_in: str | None, check_out: str | None):
    return await client.post(
        "/api/v1/assignments",
        json={
            "guest_id": guest["id"],
            "room_id": room["id"],
            "check_in": check_in,
            "check_out": check_out,
        },
    )
