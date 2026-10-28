from app.dependencies import COOKIE_NAME


async def test_login_sets_httponly_cookie(anon):
    r = await anon.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "test-admin-password"},
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    cookie = r.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    assert "HttpOnly" in cookie


async def test_wrong_password_is_401_without_hint(anon):
    bad_user = await anon.post(
        "/api/v1/auth/login", json={"username": "nobody", "password": "x"}
    )
    bad_pass = await anon.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "x"}
    )
    assert bad_user.status_code == bad_pass.status_code == 401
    assert bad_user.json() == bad_pass.json()


async def test_staff_routes_require_login(anon):
    assert (await anon.get("/api/v1/guests")).status_code == 401
    assert (await anon.get("/api/v1/dashboard/floors")).status_code == 401


async def test_admin_routes_reject_frontdesk(frontdesk):
    assert (await frontdesk.get("/api/v1/guests")).status_code == 200
    assert (await frontdesk.get("/api/v1/audit")).status_code == 403
    assert (await frontdesk.get("/api/v1/users")).status_code == 403
    assert (await frontdesk.post("/api/v1/rooms", json={"name": "x"})).status_code == 403


async def test_login_rate_limited_per_ip(anon):
    codes = []
    for i in range(11):
        r = await anon.post(
            "/api/v1/auth/login", json={"username": f"u{i}", "password": "x"}
        )
        codes.append(r.status_code)
    assert codes[:10] == [401] * 10
    assert codes[10] == 429
