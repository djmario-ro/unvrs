async def test_admin_creates_and_lists_users(admin):
    r = await admin.post(
        "/api/v1/users", json={"username": "desk1", "password": "password-123", "role": "frontdesk"}
    )
    assert r.status_code == 201
    assert r.json()["role"] == "frontdesk"
    names = [u["username"] for u in (await admin.get("/api/v1/users")).json()]
    assert "admin" in names and "desk1" in names


async def test_duplicate_username_is_409(admin):
    body = {"username": "desk2", "password": "password-123"}
    assert (await admin.post("/api/v1/users", json=body)).status_code == 201
    assert (await admin.post("/api/v1/users", json=body)).status_code == 409


async def test_invalid_role_is_422(admin):
    r = await admin.post(
        "/api/v1/users", json={"username": "desk3", "password": "password-123", "role": "owner"}
    )
    assert r.status_code == 422


async def _create(admin, username, role="frontdesk"):
    r = await admin.post(
        "/api/v1/users", json={"username": username, "password": "password-123", "role": role}
    )
    assert r.status_code == 201, r.text
    return r.json()


async def test_master_admin_cannot_be_edited_or_deleted_in_app(admin):
    me = (await admin.get("/api/v1/auth/me")).json()
    r = await admin.patch(f"/api/v1/users/{me['id']}", json={"password": "new-password-1"})
    assert r.status_code == 400
    assert "ADMIN_" in r.json()["detail"]
    assert (await admin.delete(f"/api/v1/users/{me['id']}")).status_code == 400


async def test_admin_cannot_change_own_role_and_last_admin_is_protected(admin):
    import httpx

    from app.main import app

    second = await _create(admin, "second-admin", role="admin")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
        r = await c.post("/api/v1/auth/login", json={"username": "second-admin", "password": "password-123"})
        assert r.status_code == 200
        r = await c.patch(f"/api/v1/users/{second['id']}", json={"role": "frontdesk"})
        assert r.status_code == 400
        assert "own role" in r.json()["detail"]
    # The master admin may demote and delete the second admin (master still counts).
    r = await admin.patch(f"/api/v1/users/{second['id']}", json={"role": "frontdesk"})
    assert r.status_code == 200
    assert (await admin.delete(f"/api/v1/users/{second['id']}")).status_code == 204
