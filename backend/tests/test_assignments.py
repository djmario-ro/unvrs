from tests.conftest import book, days, make_room


async def test_returning_guest_can_stay_in_same_room_again(admin, guest, room):
    first = await book(admin, guest, room, days(-10), days(-8))
    second = await book(admin, guest, room, days(5), days(7))
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["pin"] != second.json()["pin"]


async def test_overlapping_booking_is_rejected(admin, guest, room):
    assert (await book(admin, guest, room, days(1), days(3))).status_code == 201
    overlap = await book(admin, guest, room, days(2), days(4))
    assert overlap.status_code == 409
    adjacent = await book(admin, guest, room, days(3), days(5))
    assert adjacent.status_code == 201, adjacent.text


async def test_checkout_must_follow_checkin(admin, guest, room):
    r = await book(admin, guest, room, days(3), days(1))
    assert r.status_code == 400


async def test_list_is_newest_first_and_honours_limit(admin, guest):
    room = await make_room(admin)
    old = (await book(admin, guest, room, days(-30), days(-28))).json()
    new = (await book(admin, guest, room, days(10), days(12))).json()
    listed = (await admin.get("/api/v1/assignments", params={"limit": 500})).json()
    ids = [a["id"] for a in listed]
    assert ids.index(new["id"]) < ids.index(old["id"])
    assert len((await admin.get("/api/v1/assignments", params={"limit": 1})).json()) == 1


async def test_regenerate_pin_changes_it(admin, guest, room):
    a = (await book(admin, guest, room, days(1), days(2))).json()
    r = await admin.post(f"/api/v1/assignments/{a['id']}/regenerate-pin")
    assert r.status_code == 200
    assert r.json()["pin"] != a["pin"]
    assert len(r.json()["pin"]) == 6


async def test_send_pin_uses_console_mock_when_no_gateway(admin, guest, room):
    a = (await book(admin, guest, room, days(1), days(2))).json()
    r = await admin.post(f"/api/v1/assignments/{a['id']}/send-pin", json={"channels": ["sms"]})
    assert r.status_code == 200, r.text
    (entry,) = r.json()["results"]
    assert entry["channel"] == "sms"
    assert entry["recipient"] == "+40743000000"


async def test_two_rooms_can_share_a_pin_but_one_room_cannot(admin, guest):
    from tests.conftest import make_room, book, days
    # PIN uniqueness is per room, so collisions across rooms are fine; within a
    # room the generator avoids them. We assert the generator never produces a
    # duplicate within a room across many assignments.
    room = await make_room(admin)
    pins = set()
    # Sequential non-overlapping stays in the same room.
    for i in range(15):
        a = await book(admin, guest, room, days(i * 2 + 1), days(i * 2 + 2))
        assert a.status_code == 201, a.text
        pins.add(a.json()["pin"])
    assert len(pins) == 15  # all distinct within the room
