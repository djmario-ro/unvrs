"""Bad input must come back as 4xx with a usable message, never as a 500."""
from tests.conftest import book, days


async def test_duplicate_guest_email_is_409(admin):
    body = {"firstname": "A", "lastname": "B", "email": "dup@example.com"}
    assert (await admin.post("/api/v1/guests", json=body)).status_code == 201
    r = await admin.post("/api/v1/guests", json=body)
    assert r.status_code == 409
    assert "email" in r.json()["detail"]


async def test_duplicate_room_name_is_409(admin, room):
    r = await admin.post("/api/v1/rooms", json={"name": room["name"]})
    assert r.status_code == 409
    assert "name" in r.json()["detail"]


async def test_overlong_fields_are_422(admin):
    r = await admin.post("/api/v1/guests", json={"firstname": "x" * 101, "lastname": "B"})
    assert r.status_code == 422
    r = await admin.post("/api/v1/rooms", json={"name": "x" * 101})
    assert r.status_code == 422
    r = await admin.post("/api/v1/guests", json={"firstname": "", "lastname": "B"})
    assert r.status_code == 422


async def test_booking_unknown_guest_or_room_is_404(admin, guest, room):
    r = await admin.post(
        "/api/v1/assignments", json={"guest_id": 999999, "room_id": room["id"]}
    )
    assert r.status_code == 404
    r = await admin.post(
        "/api/v1/assignments", json={"guest_id": guest["id"], "room_id": 999999}
    )
    assert r.status_code == 404
    a = (await book(admin, guest, room, days(1), days(2))).json()
    r = await admin.patch(f"/api/v1/assignments/{a['id']}", json={"room_id": 999999})
    assert r.status_code == 404


async def test_negative_or_huge_paging_is_422(admin):
    for path in ("/api/v1/guests", "/api/v1/rooms", "/api/v1/assignments", "/api/v1/audit"):
        assert (await admin.get(path, params={"limit": -1})).status_code == 422
        assert (await admin.get(path, params={"skip": -1})).status_code == 422
        assert (await admin.get(path, params={"limit": 501})).status_code == 422
        assert (await admin.get(path, params={"limit": 500})).status_code == 200


async def test_user_password_rules(admin):
    r = await admin.post("/api/v1/users", json={"username": "", "password": "longenough"})
    assert r.status_code == 422
    r = await admin.post("/api/v1/users", json={"username": "shortpw", "password": "short"})
    assert r.status_code == 422


async def test_send_pin_channels_validated_and_deduped(admin, guest, room):
    a = (await book(admin, guest, room, days(1), days(2))).json()
    url = f"/api/v1/assignments/{a['id']}/send-pin"
    assert (await admin.post(url, json={"channels": []})).status_code == 422
    assert (await admin.post(url, json={"channels": ["fax"]})).status_code == 422
    r = await admin.post(url, json={"channels": ["sms", "sms"]})
    assert r.status_code == 200
    assert len(r.json()["results"]) == 1


async def test_send_pin_without_gateway_is_reported_as_mocked(admin, guest, room):
    a = (await book(admin, guest, room, days(1), days(2))).json()
    r = await admin.post(f"/api/v1/assignments/{a['id']}/send-pin", json={"channels": ["sms", "whatsapp"]})
    assert r.status_code == 200
    assert {e["status"] for e in r.json()["results"]} == {"mocked"}


async def test_naive_datetime_is_rejected(admin, guest, room):
    # A naive timestamp (no offset) must not be silently stored as server-local.
    r = await admin.post(
        "/api/v1/assignments",
        json={"guest_id": guest["id"], "room_id": room["id"], "check_in": "2026-12-01T14:00:00"},
    )
    assert r.status_code == 422
    # The same instant with an offset is fine.
    r = await admin.post(
        "/api/v1/assignments",
        json={
            "guest_id": guest["id"],
            "room_id": room["id"],
            "check_in": "2026-12-01T14:00:00+02:00",
            "check_out": "2026-12-03T10:00:00+02:00",
        },
    )
    assert r.status_code == 201, r.text
