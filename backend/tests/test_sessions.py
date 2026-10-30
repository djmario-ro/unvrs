"""Password changes revoke existing sessions (B-10)."""
import httpx

from app.main import app


async def _client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t")


async def test_password_change_invalidates_existing_session(admin):
    # Create a user and sign them in on their own client.
    await admin.post("/api/v1/users", json={"username": "rev", "password": "password-123"})
    async with await _client() as c:
        assert (await c.post("/api/v1/auth/login", json={"username": "rev", "password": "password-123"})).status_code == 200
        assert (await c.get("/api/v1/guests")).status_code == 200  # session works
        # Admin resets their password elsewhere.
        uid = next(u["id"] for u in (await admin.get("/api/v1/users")).json() if u["username"] == "rev")
        await admin.patch(f"/api/v1/users/{uid}", json={"password": "password-456"})
        # The old cookie is now rejected.
        assert (await c.get("/api/v1/guests")).status_code == 401


async def test_role_change_does_not_log_other_sessions_out(admin):
    await admin.post("/api/v1/users", json={"username": "rolechg", "password": "password-123"})
    async with await _client() as c:
        await c.post("/api/v1/auth/login", json={"username": "rolechg", "password": "password-123"})
        uid = next(u["id"] for u in (await admin.get("/api/v1/users")).json() if u["username"] == "rolechg")
        await admin.patch(f"/api/v1/users/{uid}", json={"role": "admin"})
        # No password change → session still valid.
        assert (await c.get("/api/v1/guests")).status_code == 200


async def test_admin_restart_preserves_session_with_unchanged_password(admin):
    from app.main import _ensure_admin

    await _ensure_admin()
    assert (await admin.get("/api/v1/auth/me")).status_code == 200


async def test_admin_password_rotation_revokes_session(admin, monkeypatch):
    from app.config import settings
    from app.main import _ensure_admin

    with monkeypatch.context() as patch:
        patch.setattr(settings, "admin_password", "rotated-admin-password")
        await _ensure_admin()
        assert (await admin.get("/api/v1/auth/me")).status_code == 401
    await _ensure_admin()
