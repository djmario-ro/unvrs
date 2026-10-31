from unittest.mock import AsyncMock

import pytest

from app.utils.homeassistant import DoorUnavailable
from tests.conftest import book, days, make_room


@pytest.fixture(autouse=True)
def opener(monkeypatch):
    action = AsyncMock()
    monkeypatch.setattr("app.routers.door.open_door", action)
    return action


async def validate(anon, room, pin, **kw):
    return await anon.post(
        f"/api/v1/door/{room['public_id']}/session",
        json={"pin": pin},
        **kw,
    )


async def test_pin_only_activates_and_slide_checks_in(admin, anon, guest, room, opener):
    a = (await book(admin, guest, room, days(-0.1), days(1))).json()
    r = await validate(anon, room, a["pin"])
    assert r.status_code == 200, r.text
    assert r.json()["guest"] == "Ana Pop"
    assert "HttpOnly" in r.headers["set-cookie"]
    assert "SameSite=strict" in r.headers["set-cookie"]
    assert f"Path=/api/v1/door/{room['public_id']}" in r.headers["set-cookie"]
    opener.assert_not_awaited()
    assert (await admin.get(f"/api/v1/assignments/{a['id']}")).json()["checked_in_at"] is None
    assert (await anon.get(f"/api/v1/door/{room['public_id']}/session")).status_code == 200
    r = await anon.post(f"/api/v1/door/{room['public_id']}/unlock", json={})
    assert r.status_code == 200, r.text
    assert r.json()["message"] == "Door unlock triggered"
    opener.assert_awaited_once_with("lock.test_room")
    assert (await admin.get(f"/api/v1/assignments/{a['id']}")).json()["checked_in_at"] is not None


async def test_pin_outside_stay_window_is_indistinguishable_from_wrong_pin(
    admin, anon, guest, room, opener
):
    past = (await book(admin, guest, room, days(-10), days(-8))).json()
    future = (await book(admin, guest, room, days(5), days(7))).json()
    wrong = await validate(anon, room, "000000")
    for pin in (past["pin"], future["pin"]):
        r = await validate(anon, room, pin)
        assert r.status_code == 401
        assert r.json() == wrong.json()
    opener.assert_not_awaited()


async def test_failed_door_action_does_not_check_in(admin, anon, guest, room, opener):
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    opener.side_effect = DoorUnavailable("Unable to confirm door opening. Please contact reception.")
    assert (await validate(anon, room, booking["pin"])).status_code == 200
    response = await anon.post(f"/api/v1/door/{room['public_id']}/unlock", json={})
    assert response.status_code == 503
    after = (await admin.get(f"/api/v1/assignments/{booking['id']}")).json()
    assert after["checked_in_at"] is None
    events = (await admin.get("/api/v1/audit")).json()
    assert any(e["operation"] == "door.open_failed" and f"room id={room['id']}" in e["message"] for e in events)


async def test_unknown_room_and_malformed_pin(anon, room):
    r = await anon.post(
        "/api/v1/door/validate-pin", json={"room_public_id": "nope", "pin": "123456"}
    )
    assert r.status_code == 401
    assert (await validate(anon, room, "12345")).status_code == 422
    assert (await validate(anon, room, "12345a")).status_code == 422


async def test_per_room_rate_limit(anon, room):
    codes = [(await validate(anon, room, "000000")).status_code for _ in range(11)]
    assert codes[:10] == [401] * 10
    assert codes[10] == 429


async def test_per_ip_limit_ignores_forged_forwarded_for(admin, anon):
    rooms = [await make_room(admin) for _ in range(5)]
    codes = []
    for i in range(21):
        # client-forged entry, real client, Cloudflare edge, nginx — as prod sees it
        xff = f"203.0.113.{i}, 198.51.100.7, 188.114.96.8, 10.0.0.1"
        r = await validate(anon, rooms[i % 5], "000000", headers={"X-Forwarded-For": xff})
        codes.append(r.status_code)
    assert 429 not in codes[:20]
    assert codes[20] == 429


async def test_three_phones_reuse_pin_and_single_device_revocation(admin, guest, room, opener):
    import httpx
    from app.main import app
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    phones = [httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") for _ in range(3)]
    try:
        tokens = []
        for i, phone in enumerate(phones):
            response = await validate(phone, room, booking["pin"], headers={"User-Agent": f"Test phone {i}"})
            assert response.status_code == 200
            tokens.append(phone.cookies.get("gh_guest"))
            assert (await phone.get("/api/v1/rooms")).status_code == 401
        assert len(set(tokens)) == 3
        devices = (await admin.get(f"/api/v1/assignments/{booking['id']}/devices")).json()
        assert len(devices) == 3 and all(d["active"] for d in devices)
        assert all("token_hash" not in d and "token" not in d for d in devices)
        first = next(d for d in devices if d["device_name"] == "Test phone 0")
        assert (await admin.post(f"/api/v1/assignments/{booking['id']}/devices/{first['id']}/revoke")).status_code == 204
        assert (await phones[0].post(f"/api/v1/door/{room['public_id']}/unlock", json={})).status_code == 401
        for phone in phones[1:]:
            assert (await phone.post(f"/api/v1/door/{room['public_id']}/unlock", json={})).status_code == 200
        assert opener.await_count == 2
    finally:
        for phone in phones:
            await phone.aclose()


async def test_revoke_stay_blocks_pin_and_sessions_until_pin_replaced(admin, anon, guest, room, opener):
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    assert (await validate(anon, room, booking["pin"])).status_code == 200
    assert (await admin.post(f"/api/v1/assignments/{booking['id']}/revoke-access")).status_code == 204
    assert (await anon.post(f"/api/v1/door/{room['public_id']}/unlock", json={})).status_code == 401
    assert (await validate(anon, room, booking["pin"])).status_code == 401
    updated = (await admin.post(f"/api/v1/assignments/{booking['id']}/regenerate-pin")).json()
    assert updated["access_revoked_at"] is None
    assert (await validate(anon, room, booking["pin"])).status_code == 401
    assert (await validate(anon, room, updated["pin"])).status_code == 200
    assert (await anon.post(f"/api/v1/door/{room['public_id']}/unlock", json={})).status_code == 200


async def test_pin_regeneration_invalidates_already_activated_phone(admin, anon, guest, room, opener):
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    await validate(anon, room, booking["pin"])
    await admin.post(f"/api/v1/assignments/{booking['id']}/regenerate-pin")
    assert (await anon.post(f"/api/v1/door/{room['public_id']}/unlock", json={})).status_code == 401
    opener.assert_not_awaited()


@pytest.mark.parametrize("change", ["past", "future", "room", "delete"])
async def test_booking_changes_are_checked_on_every_unlock(admin, anon, guest, room, opener, change):
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    await validate(anon, room, booking["pin"])
    if change == "past":
        result = await admin.patch(f"/api/v1/assignments/{booking['id']}", json={"check_in": days(-2), "check_out": days(-1)})
    elif change == "future":
        result = await admin.patch(f"/api/v1/assignments/{booking['id']}", json={"check_in": days(2), "check_out": days(3)})
    elif change == "room":
        other = await make_room(admin)
        result = await admin.patch(f"/api/v1/assignments/{booking['id']}", json={"room_id": other["id"]})
    else:
        result = await admin.delete(f"/api/v1/assignments/{booking['id']}")
    assert result.status_code in (200, 204), result.text
    assert (await anon.get(f"/api/v1/door/{room['public_id']}/session")).status_code == 401
    assert (await anon.post(f"/api/v1/door/{room['public_id']}/unlock", json={})).status_code == 401
    opener.assert_not_awaited()


async def test_room_binding_origin_and_json_guards(admin, anon, guest, room, opener):
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    await validate(anon, room, booking["pin"])
    token = anon.cookies.get("gh_guest")
    other = await make_room(admin)
    assert (await anon.post(f"/api/v1/door/{other['public_id']}/unlock", json={}, headers={"Cookie": f"gh_guest={token}"})).status_code == 401
    url = f"/api/v1/door/{room['public_id']}/unlock"
    assert (await anon.post(url, json={}, headers={"Origin": "https://attacker.example"})).status_code == 403
    assert (await anon.post(url, content="x=1", headers={"Content-Type": "application/x-www-form-urlencoded"})).status_code == 415
    assert (await anon.get(url)).status_code == 405
    opener.assert_not_awaited()


async def test_forgetting_phone_revokes_its_cookie_on_server(admin, anon, guest, room, opener):
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    await validate(anon, room, booking["pin"])
    token = anon.cookies.get("gh_guest")
    assert (await anon.post(f"/api/v1/door/{room['public_id']}/logout", json={})).status_code == 204
    assert (await anon.post(f"/api/v1/door/{room['public_id']}/unlock", json={}, headers={"Cookie": f"gh_guest={token}"})).status_code == 401
    opener.assert_not_awaited()


async def test_guest_cannot_manage_other_devices(anon):
    assert (await anon.get("/api/v1/assignments/1/devices")).status_code == 401
    assert (await anon.post("/api/v1/assignments/1/revoke-access")).status_code == 401


async def test_guest_cookie_is_secure_hashed_and_expiry_is_enforced(admin, anon, guest, room, opener, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import select
    from app.config import settings
    from app.database import AsyncSessionLocal
    from app.models.guest_device import GuestDevice
    from app.routers.door import token_hash
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    monkeypatch.setattr(settings, "cookie_secure", True)
    response = await validate(anon, room, booking["pin"])
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]
    token = response.cookies.get("gh_guest")
    assert token not in response.text
    async with AsyncSessionLocal() as db:
        device = (await db.execute(select(GuestDevice).where(GuestDevice.token_hash == token_hash(token)))).scalar_one()
        assert device.token_hash != token and len(device.token_hash) == 64
        device.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
    response = await anon.post(f"/api/v1/door/{room['public_id']}/unlock", json={}, headers={"Cookie": f"gh_guest={token}"})
    assert response.status_code == 401
    opener.assert_not_awaited()


@pytest.mark.parametrize("checkout", [45, None])
async def test_guest_cookie_lasts_until_checkout_or_bounded_open_ended_stay(admin, anon, guest, room, checkout):
    from datetime import datetime, timezone
    booking = (await book(admin, guest, room, days(-0.1), days(checkout) if checkout else None)).json()
    response = await validate(anon, room, booking["pin"])
    assert response.status_code == 200
    expires = datetime.fromisoformat(response.json()["expires_at"])
    if checkout:
        assert expires == datetime.fromisoformat(booking["check_out"])
    else:
        assert 29 < (expires - datetime.now(timezone.utc)).total_seconds() / 86400 <= 30


async def test_legacy_pin_endpoint_is_also_activation_only(admin, anon, guest, room, opener):
    booking = (await book(admin, guest, room, days(-0.1), days(1))).json()
    response = await anon.post("/api/v1/door/validate-pin", json={"room_public_id": room["public_id"], "pin": booking["pin"]})
    assert response.status_code == 200
    assert "gh_guest=" in response.headers["set-cookie"]
    opener.assert_not_awaited()
