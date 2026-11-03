"""Property authorization, role boundaries and cross-tenant IDOR regression tests."""

from uuid import uuid4
from contextlib import aclosing
from fastapi import Depends
from app.database import get_db
import httpx
import pytest
from app.main import app


async def staff(admin, roles):
    username = "staff-" + uuid4().hex[:12]
    result = await admin.post(
        "/api/v1/users",
        json={"username": username, "password": "staff-password-123", "roles": roles},
    )
    assert result.status_code == 201, result.text
    client = httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "staff-password-123"},
    )
    assert login.status_code == 200, login.text
    return client, result.json()


@pytest.mark.parametrize(
    "role,allowed,denied",
    [
        (
            "frontdesk",
            ["/guests", "/assignments", "/dashboard/floors"],
            ["/users", "/operations/housekeeping", "/operations/maintenance"],
        ),
        (
            "housekeeping",
            ["/operations/housekeeping"],
            [
                "/guests",
                "/assignments",
                "/rooms",
                "/users",
                "/audit",
                "/messaging/logs",
                "/dashboard/floors",
                "/operations/maintenance",
            ],
        ),
        (
            "maintenance",
            ["/operations/maintenance", "/operations/maintenance/rooms"],
            [
                "/guests",
                "/assignments",
                "/rooms",
                "/users",
                "/audit",
                "/operations/housekeeping",
            ],
        ),
        (
            "administrator",
            [
                "/users",
                "/guests",
                "/operations/housekeeping",
                "/operations/maintenance",
            ],
            [],
        ),
        (
            "owner",
            [
                "/users",
                "/guests",
                "/operations/housekeeping",
                "/operations/maintenance",
            ],
            [],
        ),
    ],
)
async def test_role_api_boundaries(admin, role, allowed, denied):
    client, _ = await staff(admin, [role])
    async with aclosing(client):
        for path in allowed:
            response = await client.get("/api/v1" + path)
            assert response.status_code == 200, (path, response.text)
        for path in denied:
            assert (await client.get("/api/v1" + path)).status_code == 403, path


async def test_housekeeping_sees_no_guest_identity_or_pin_and_can_report_issue(
    admin, room, guest
):
    from tests.conftest import book, days

    assert (await book(admin, guest, room, days(-1), days(1))).status_code == 201
    client, _ = await staff(admin, ["housekeeping"])
    async with aclosing(client):
        rows = (await client.get("/api/v1/operations/housekeeping")).json()
        row = next(row for row in rows if row["id"] == room["id"])
        assert set(row) == {"id", "name", "floor", "status", "cleaned_at"}
        assert (
            await client.post(f"/api/v1/operations/housekeeping/{room['id']}/cleaned")
        ).status_code == 204
        report = await client.post(
            "/api/v1/operations/maintenance",
            json={"room_id": room["id"], "title": "Tap leaking"},
        )
        assert report.status_code == 201, report.text
        assert (
            await client.patch(
                f"/api/v1/operations/maintenance/{report.json()['id']}",
                json={"status": "resolved"},
            )
        ).status_code == 403


async def test_maintenance_can_track_repairs_but_cannot_clean(admin, room):
    client, _ = await staff(admin, ["maintenance"])
    async with aclosing(client):
        ticket = await client.post(
            "/api/v1/operations/maintenance",
            json={"room_id": room["id"], "title": "Lamp broken"},
        )
        assert ticket.status_code == 201, ticket.text
        changed = await client.patch(
            f"/api/v1/operations/maintenance/{ticket.json()['id']}",
            json={"status": "in_progress"},
        )
        assert changed.status_code == 200 and changed.json()["status"] == "in_progress"
        assert (
            await client.post(f"/api/v1/operations/housekeeping/{room['id']}/cleaned")
        ).status_code == 403


async def test_combined_roles_and_immediate_membership_revocation(admin):
    client, user = await staff(admin, ["housekeeping", "maintenance"])
    async with aclosing(client):
        assert (await client.get("/api/v1/operations/housekeeping")).status_code == 200
        assert (await client.get("/api/v1/operations/maintenance")).status_code == 200
        assert (
            await admin.patch(
                f"/api/v1/users/{user['id']}", json={"roles": ["maintenance"]}
            )
        ).status_code == 200
        assert (await client.get("/api/v1/operations/housekeeping")).status_code == 403
        assert (await client.get("/api/v1/operations/maintenance")).status_code == 200
        assert (await admin.delete(f"/api/v1/users/{user['id']}")).status_code == 204
        assert (await client.get("/api/v1/auth/me")).status_code == 403


async def test_administrator_cannot_grant_or_change_owner_or_admin(admin):
    client, _ = await staff(admin, ["administrator"])
    target_client, target = await staff(admin, ["housekeeping"])
    await target_client.aclose()
    async with aclosing(client):
        for role in ["owner", "administrator"]:
            assert (
                await client.post(
                    "/api/v1/users",
                    json={
                        "username": "escalate-" + uuid4().hex[:8],
                        "password": "password-123",
                        "roles": [role],
                    },
                )
            ).status_code == 403
            assert (
                await client.patch(
                    f"/api/v1/users/{target['id']}", json={"roles": [role]}
                )
            ).status_code == 403
        me = (await admin.get("/api/v1/auth/me")).json()
        assert (await client.delete(f"/api/v1/users/{me['id']}")).status_code in (
            400,
            403,
        )


async def test_cross_property_data_and_write_isolation(admin, room, guest):
    created = await admin.post(
        "/api/v1/properties",
        json={"name": "Second property", "slug": "second-" + uuid4().hex[:12]},
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    headers = {"X-Property-ID": str(pid)}
    me = (await admin.get("/api/v1/auth/me", headers=headers)).json()
    assert me["roles"] == ["owner"] and me["property_id"] == pid
    assert len(me["properties"]) >= 2
    assert (await admin.get("/api/v1/rooms", headers=headers)).json() == []
    assert (
        await admin.get(f"/api/v1/rooms/{room['id']}", headers=headers)
    ).status_code == 404
    assert (
        await admin.get(f"/api/v1/guests/{guest['id']}", headers=headers)
    ).status_code == 404
    other = await admin.post(
        "/api/v1/rooms", headers=headers, json={"name": room["name"]}
    )
    assert other.status_code == 201, other.text  # room names are unique per property
    assert (await admin.get(f"/api/v1/rooms/{other.json()['id']}")).status_code == 404
    # A body cannot smuggle IDs from another tenant.
    assignment = await admin.post(
        "/api/v1/assignments",
        headers=headers,
        json={"room_id": other.json()["id"], "guest_id": guest["id"]},
    )
    assert assignment.status_code == 404, assignment.text
    other_guest = await admin.post(
        "/api/v1/guests",
        headers=headers,
        json={"firstname": "Other", "lastname": "Tenant"},
    )
    assert other_guest.status_code == 201
    assert all(
        g["id"] != other_guest.json()["id"]
        for g in (await admin.get("/api/v1/guests")).json()
    )
    # IDs and audit rows from the original property cannot leak into this one.
    audit = (await admin.get("/api/v1/audit", headers=headers)).json()
    assert not any(
        row["operation"] == "guest.create" and f"id={guest['id']}" in row["message"]
        for row in audit
    )
    assert (
        await admin.get("/api/v1/messaging/whatsapp/status", headers=headers)
    ).status_code == 409
    # A user with a valid session but no membership in the target is denied.
    client, _ = await staff(admin, ["administrator"])
    async with aclosing(client):
        assert (await client.get("/api/v1/rooms", headers=headers)).status_code == 403
        assert (await client.get("/api/v1/users", headers=headers)).status_code == 403


async def test_identity_is_shared_but_memberships_and_roles_are_separate(
    admin, monkeypatch
):
    from app.config import settings
    from app.database import AsyncSessionLocal
    from app.models.property import PropertyMembership
    from app.models.user import User
    from sqlalchemy import select

    # One immutable Keycloak identity belongs to two properties, without a
    # second user row, email matching, or a global role grant.
    issuer = "https://identity.example.test/realms/staging"
    subject = str(uuid4())
    async with AsyncSessionLocal() as db:
        person = User(
            username="shared-" + uuid4().hex[:12],
            password_hash=None,
            oidc_issuer=issuer,
            oidc_subject=subject,
            role="frontdesk",
        )
        db.add(person)
        await db.flush()
        uid = person.id
        db.add(PropertyMembership(user_id=uid, property_id=1, roles=["housekeeping"]))
        await db.commit()
    prop = await admin.post(
        "/api/v1/properties",
        json={"name": "Shared property", "slug": "shared-" + uuid4().hex[:10]},
    )
    pid = prop.json()["id"]
    # admin is a local session; switch provider only for endpoint behavior,
    # replace the auth dependency with the already validated local owner.
    from app.dependencies import get_current_user
    from app.models.property import Property

    async def owner_context(db=Depends(get_db)):
        user = await db.get(User, 1)
        user._active_roles = ["owner"]
        user._active_property_id = pid
        db.info["property_id"] = pid
        return user

    app.dependency_overrides[get_current_user] = owner_context
    try:
        monkeypatch.setattr(settings, "auth_provider", "keycloak")
        monkeypatch.setattr(settings, "oidc_issuer", issuer)
        result = await admin.post(
            "/api/v1/users",
            json={
                "username": "ignored-display-name",
                "oidc_subject": subject,
                "roles": ["maintenance"],
            },
        )
        assert result.status_code == 201, result.text
        assert result.json()["id"] == uid and result.json()["roles"] == ["maintenance"]
    finally:
        app.dependency_overrides.clear()
    async with AsyncSessionLocal() as db:
        assert (await db.get(PropertyMembership, (uid, 1))).roles == ["housekeeping"]
        assert (await db.get(PropertyMembership, (uid, pid))).roles == ["maintenance"]
        assert (
            len(
                (
                    await db.scalars(select(User).where(User.oidc_subject == subject))
                ).all()
            )
            == 1
        )


async def test_database_rejects_cross_property_foreign_keys(admin, guest):
    from sqlalchemy.exc import IntegrityError
    from app.database import AsyncSessionLocal
    from app.models.property import Property
    from app.models.room import Room
    from app.models.guest_room import GuestRoom

    async with AsyncSessionLocal() as db:
        prop = Property(name="Database boundary", slug="db-" + uuid4().hex[:12])
        db.add(prop)
        await db.flush()
        room = Room(property_id=prop.id, name="Foreign room")
        db.add(room)
        await db.flush()
        db.add(
            GuestRoom(
                property_id=1, room_id=room.id, guest_id=guest["id"], pin="654321"
            )
        )
        with pytest.raises(IntegrityError):
            await db.flush()
        await db.rollback()
