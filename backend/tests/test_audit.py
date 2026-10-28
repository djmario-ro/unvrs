"""The audit log answers who, from where, and includes auth failures."""
from tests.conftest import book, days


async def _latest(admin, operation):
    rows = (await admin.get("/api/v1/audit", params={"limit": 50})).json()
    return next(r for r in rows if r["operation"] == operation)


async def test_staff_actions_record_actor_and_ip(admin, guest, room):
    a = (await book(admin, guest, room, days(1), days(2))).json()
    await admin.post(f"/api/v1/assignments/{a['id']}/regenerate-pin")
    row = await _latest(admin, "assignment.pin_regenerated")
    assert row["actor"] == "admin"
    assert row["ip"]  # ASGI test client peer address


async def test_failed_login_is_audited_without_actor(admin, anon):
    await anon.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
    row = await _latest(admin, "auth.login_failed")
    assert "ghost" in row["message"]
    assert row["actor"] is None
    login = await _latest(admin, "auth.login")
    assert login["actor"] == "admin"


async def test_rejected_door_pin_is_audited(admin, anon, room):
    await anon.post(
        "/api/v1/door/validate-pin", json={"room_public_id": room["public_id"], "pin": "000000"}
    )
    row = await _latest(admin, "door.pin_rejected")
    assert f"room id={room['id']}" in row["message"]
    assert row["actor"] is None


async def test_guest_deletion_logs_id_not_name(admin, guest):
    await admin.delete(f"/api/v1/guests/{guest['id']}")
    row = await _latest(admin, "guest.delete")
    assert "Ana" not in row["message"] and str(guest["id"]) in row["message"]
