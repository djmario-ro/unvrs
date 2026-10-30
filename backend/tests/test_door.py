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
        "/api/v1/door/validate-pin",
        json={"room_public_id": room["public_id"], "pin": pin},
        **kw,
    )


async def test_current_stay_opens_and_checks_in(admin, anon, guest, room, opener):
    a = (await book(admin, guest, room, days(-0.1), days(1))).json()
    assert a["checked_in_at"] is None
    r = await validate(anon, room, a["pin"])
    assert r.status_code == 200, r.text
    assert r.json()["guest"] == "Ana Pop"
    assert r.json()["message"] == "Door unlock triggered"
    opener.assert_awaited_once_with(room["public_id"])
    after = (await admin.get(f"/api/v1/assignments/{a['id']}")).json()
    assert after["checked_in_at"] is not None
    floors = (await admin.get("/api/v1/dashboard/floors")).json()
    statuses = {r_["id"]: r_["status"] for f in floors["floors"] for r_ in f["rooms"]}
    assert statuses[room["id"]] == "checked_in"


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
    response = await validate(anon, room, booking["pin"])
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
