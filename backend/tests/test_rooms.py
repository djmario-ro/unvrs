"""Rooms: images and deletion with the blob column deferred."""
import io

from PIL import Image

from tests.conftest import book, days


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    return buf.getvalue()


async def test_image_upload_list_serve_and_cache(admin, room):
    r = await admin.post(
        f"/api/v1/rooms/{room['id']}/images", files={"file": ("a.png", _png(), "image/png")}
    )
    assert r.status_code == 201, r.text
    img = r.json()
    assert img["is_cover"] is True and img["content_type"] == "image/png"
    listed = (await admin.get(f"/api/v1/rooms/{room['id']}")).json()
    assert [i["id"] for i in listed["images"]] == [img["id"]]
    served = await admin.get(f"/api/v1/rooms/{room['id']}/images/{img['id']}")
    assert served.status_code == 200
    assert served.content[:4] == b"\x89PNG"
    etag = served.headers["etag"]
    cached = await admin.get(
        f"/api/v1/rooms/{room['id']}/images/{img['id']}", headers={"If-None-Match": etag}
    )
    assert cached.status_code == 304
    other = await admin.get(f"/api/v1/rooms/999999/images/{img['id']}")
    assert other.status_code == 404


async def test_non_image_upload_is_400(admin, room):
    r = await admin.post(
        f"/api/v1/rooms/{room['id']}/images", files={"file": ("a.png", b"not an image", "image/png")}
    )
    assert r.status_code == 400


async def test_delete_room_cascades_bookings_and_images(admin, guest, room):
    await admin.post(f"/api/v1/rooms/{room['id']}/images", files={"file": ("a.png", _png(), "image/png")})
    a = (await book(admin, guest, room, days(1), days(2))).json()
    assert (await admin.delete(f"/api/v1/rooms/{room['id']}")).status_code == 204
    assert (await admin.get(f"/api/v1/rooms/{room['id']}")).status_code == 404
    assert (await admin.get(f"/api/v1/assignments/{a['id']}")).status_code == 404


async def test_delete_guest_cascades_bookings(admin, guest, room):
    a = (await book(admin, guest, room, days(1), days(2))).json()
    assert (await admin.delete(f"/api/v1/guests/{guest['id']}")).status_code == 204
    assert (await admin.get(f"/api/v1/assignments/{a['id']}")).status_code == 404


async def test_thumbnail_query_downscales(admin, room):
    import io

    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (1200, 900), "blue").save(buf, format="PNG")
    r = await admin.post(
        f"/api/v1/rooms/{room['id']}/images", files={"file": ("big.png", buf.getvalue(), "image/png")}
    )
    img = r.json()
    full = await admin.get(f"/api/v1/rooms/{room['id']}/images/{img['id']}")
    thumb = await admin.get(f"/api/v1/rooms/{room['id']}/images/{img['id']}", params={"w": 200})
    assert thumb.status_code == 200
    assert len(thumb.content) < len(full.content)
    assert PILImage.open(io.BytesIO(thumb.content)).width == 200
    # Separate ETag per width, so sizes cache independently.
    assert full.headers["etag"] != thumb.headers["etag"]
    cached = await admin.get(
        f"/api/v1/rooms/{room['id']}/images/{img['id']}",
        params={"w": 200},
        headers={"If-None-Match": thumb.headers["etag"]},
    )
    assert cached.status_code == 304


async def test_room_homeassistant_entity_is_admin_only_and_validated(admin, frontdesk, room):
    url = f"/api/v1/rooms/{room['id']}"
    assert (await frontdesk.patch(url, json={"homeassistant_entity_id": "lock.other_door"})).status_code == 403
    for invalid in ["switch.anything", "../script/open_door", "lock.one,lock.two", "lock.", "script.turn_on", "script.reload"]:
        assert (await admin.patch(url, json={"homeassistant_entity_id": invalid})).status_code == 422
    for entity in ["lock.room_101", "script.open_door", None]:
        response = await admin.patch(url, json={"homeassistant_entity_id": entity})
        assert response.status_code == 200
        assert response.json()["homeassistant_entity_id"] == entity
