import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db
from app.models.guest_device import GuestDevice
from app.models.guest import Guest
from app.models.guest_room import GuestRoom
from app.models.message_log import MessageLog
from app.models.room import Room
from app.schemas.guest_room import GuestRoomCreate, GuestRoomRead, GuestRoomUpdate
from app.schemas.message import SendPinRequest, SendPinResult
from app.utils import audit as audit_log
from app.utils import messaging
from app.utils.pin import generate_pin

from app.utils.qr import generate_qr_png

router = APIRouter(prefix="/assignments", tags=["assignments"])


async def _unique_pin(db: AsyncSession, room_id: int) -> str:
    """A PIN not already used by another assignment of the same room.

    Collisions are astronomically unlikely but the (room_id, pin) unique
    constraint would turn one into a 500, so draw again if needed.
    """
    for _ in range(10):
        pin = generate_pin()
        exists = await db.scalar(
            select(GuestRoom.id).where(
                GuestRoom.room_id == room_id, GuestRoom.pin == pin
            )
        )
        if not exists:
            return pin
    raise HTTPException(status_code=500, detail="Could not allocate a unique PIN")



_LOCAL_TZ = ZoneInfo(settings.timezone)


def _format_dt(value: datetime | None) -> str:
    if not value:
        return "—"
    if value.tzinfo is not None:
        value = value.astimezone(_LOCAL_TZ)
    return value.strftime("%d.%m.%Y %H:%M")


def _build_pin_message(assignment: GuestRoom) -> str:
    """Bilingual (Romanian + English) PIN message with the stay details."""
    guest = assignment.guest
    room = assignment.room
    name = settings.guesthouse_name

    stay_ro = stay_en = ""
    if assignment.check_in and assignment.check_out:
        check_in = _format_dt(assignment.check_in)
        check_out = _format_dt(assignment.check_out)
        stay_ro = f"📅 Cazarea ta este în perioada {check_in} – {check_out}.\n"
        stay_en = f"📅 Your accommodation is from {check_in} to {check_out}.\n"

    ro = (
        f"🏡 Mesaj de la {name}\n\n"
        f"Bună, {guest.firstname}! 👋\n"
        f"{stay_ro}"
        f"🔑 Folosește acest cod PIN pentru a accesa {room.name}: {assignment.pin}\n"
        f"Te așteptăm cu drag!"
    )
    en = (
        f"🏡 Message from {name}\n\n"
        f"Hi, {guest.firstname}! 👋\n"
        f"{stay_en}"
        f"🔑 Use this PIN to access {room.name}: {assignment.pin}\n"
        f"See you soon!"
    )
    return f"{ro}\n\n———\n\n{en}"


async def _load_assignment(db: AsyncSession, assignment_id: int) -> GuestRoom:
    result = await db.execute(
        select(GuestRoom)
        .where(GuestRoom.id == assignment_id)
        .options(
            selectinload(GuestRoom.guest),
            selectinload(GuestRoom.room).selectinload(Room.images),
        )
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return obj


@router.get("", response_model=list[GuestRoomRead])
async def list_assignments(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    # Newest stays first so a truncated page drops old history, not current bookings.
    result = await db.execute(
        select(GuestRoom)
        .options(
            selectinload(GuestRoom.guest),
            selectinload(GuestRoom.room).selectinload(Room.images),
        )
        .order_by(GuestRoom.check_in.desc().nulls_last(), GuestRoom.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("", response_model=GuestRoomRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(body: GuestRoomCreate, db: AsyncSession = Depends(get_db)):
    if not await db.get(Guest, body.guest_id):
        raise HTTPException(status_code=404, detail="Guest not found")
    if not await db.get(Room, body.room_id):
        raise HTTPException(status_code=404, detail="Room not found")

    # A guest may stay in the same room more than once; only overlapping dates
    # are rejected.
    if body.check_in and body.check_out:
        if body.check_in >= body.check_out:
            raise HTTPException(
                status_code=400, detail="Check-out must be after check-in"
            )
        # Reject a stay that overlaps an existing booking for the same room.
        overlap = await db.execute(
            select(GuestRoom)
            .where(
                GuestRoom.room_id == body.room_id,
                GuestRoom.check_in.is_not(None),
                GuestRoom.check_out.is_not(None),
                GuestRoom.check_in < body.check_out,
                GuestRoom.check_out > body.check_in,
            )
            .limit(1)
        )
        if overlap.scalar_one_or_none():
            raise HTTPException(
                status_code=409,
                detail="Room is already booked for those dates",
            )

    pin = await _unique_pin(db, body.room_id)
    assignment = GuestRoom(**body.model_dump(), pin=pin)
    db.add(assignment)
    await db.flush()
    await audit_log.log(
        db,
        "assignment.create",
        f"Assigned guest id={body.guest_id} to room id={body.room_id} (assignment id={assignment.id})",
    )
    return await _load_assignment(db, assignment.id)


@router.get("/{assignment_id}", response_model=GuestRoomRead)
async def get_assignment(assignment_id: int, db: AsyncSession = Depends(get_db)):
    return await _load_assignment(db, assignment_id)


@router.patch("/{assignment_id}", response_model=GuestRoomRead)
async def update_assignment(
    assignment_id: int, body: GuestRoomUpdate, db: AsyncSession = Depends(get_db)
):
    """Edit a booking's room and/or dates, re-validating for double-booking."""
    assignment = await db.get(GuestRoom, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    data = body.model_dump(exclude_unset=True)
    room_id = data.get("room_id", assignment.room_id)
    check_in = data.get("check_in", assignment.check_in)
    check_out = data.get("check_out", assignment.check_out)

    if check_in and check_out and check_in >= check_out:
        raise HTTPException(status_code=400, detail="Check-out must be after check-in")

    if room_id != assignment.room_id and not await db.get(Room, room_id):
        raise HTTPException(status_code=404, detail="Room not found")

    if check_in and check_out:
        overlap = await db.execute(
            select(GuestRoom)
            .where(
                GuestRoom.id != assignment_id,
                GuestRoom.room_id == room_id,
                GuestRoom.check_in.is_not(None),
                GuestRoom.check_out.is_not(None),
                GuestRoom.check_in < check_out,
                GuestRoom.check_out > check_in,
            )
            .limit(1)
        )
        if overlap.scalar_one_or_none():
            raise HTTPException(
                status_code=409, detail="Room is already booked for those dates"
            )

    if room_id != assignment.room_id:
        assignment.key_version += 1
        assignment.pin = await _unique_pin(db, room_id)
    for field, value in data.items():
        setattr(assignment, field, value)
    await audit_log.log(db, "assignment.update", f"Updated booking id={assignment_id}")
    await db.flush()
    return await _load_assignment(db, assignment_id)


@router.delete("/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assignment(assignment_id: int, db: AsyncSession = Depends(get_db)):
    assignment = await db.get(GuestRoom, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await audit_log.log(db, "assignment.delete", f"Removed assignment id={assignment_id}")
    await db.delete(assignment)


@router.post("/{assignment_id}/regenerate-pin", response_model=GuestRoomRead)
async def regenerate_pin(assignment_id: int, db: AsyncSession = Depends(get_db)):
    """Generate a new PIN for an existing guest-room assignment."""
    assignment = await db.get(GuestRoom, assignment_id)
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")
    assignment.pin = await _unique_pin(db, assignment.room_id)
    assignment.key_version += 1
    assignment.access_revoked_at = None
    await audit_log.log(
        db, "assignment.pin_regenerated", f"PIN regenerated for assignment id={assignment_id}"
    )
    return await _load_assignment(db, assignment_id)


@router.post("/{assignment_id}/send-pin", response_model=SendPinResult)
async def send_pin(
    assignment_id: int, body: SendPinRequest, db: AsyncSession = Depends(get_db)
):
    """Send the assignment PIN to the guest over the requested channel(s)."""
    if not body.channels:
        raise HTTPException(status_code=400, detail="No channels selected")

    assignment = await _load_assignment(db, assignment_id)
    if not assignment.guest.phone:
        raise HTTPException(
            status_code=400, detail="Guest has no phone number on file"
        )

    phone = messaging.normalize_phone(assignment.guest.phone)
    text = _build_pin_message(assignment)

    # WhatsApp also carries the room's door QR code as an image.
    qr_png = None
    if "whatsapp" in body.channels:
        door_url = f"{settings.frontend_origin}/door/{assignment.room.public_id}"
        qr_png = generate_qr_png(door_url)

    async def _send(channel: str) -> tuple[str, str | None]:
        """Return (status, error) for one channel. Never raises."""
        try:
            if channel == "whatsapp":
                return await messaging.send_whatsapp(phone, text, image=qr_png), None
            return await messaging.send_sms(phone, text), None
        except messaging.MessagingError as exc:
            return "failed", str(exc)

    # Do the network I/O up front and concurrently, so the DB transaction is
    # not held open across (possibly slow) provider calls.
    outcomes = await asyncio.gather(*(_send(c) for c in body.channels))

    logs: list[MessageLog] = []
    for channel, (status_, error) in zip(body.channels, outcomes):
        entry = MessageLog(
            assignment_id=assignment.id,
            channel=channel,
            recipient=phone,
            status=status_,
            error=error,
        )
        db.add(entry)
        logs.append(entry)

    await audit_log.log(
        db,
        "assignment.pin_sent",
        f"PIN sent for assignment id={assignment_id} via {', '.join(body.channels)}",
    )
    await db.flush()
    for entry in logs:
        await db.refresh(entry)
    return SendPinResult(results=logs)


@router.get("/{assignment_id}/devices")
async def list_devices(assignment_id: int, db: AsyncSession = Depends(get_db)):
    stay = await db.get(GuestRoom, assignment_id)
    if not stay:
        raise HTTPException(404, "Assignment not found")
    result = await db.execute(select(GuestDevice).where(GuestDevice.assignment_id == assignment_id).order_by(GuestDevice.created_at.desc()))
    now = datetime.now(timezone.utc)
    return [{"id": d.id, "device_name": d.device_name, "created_at": d.created_at,
             "last_used_at": d.last_used_at, "expires_at": d.expires_at,
             "active": not d.revoked_at and not stay.access_revoked_at and d.key_version == stay.key_version
             and d.room_id == stay.room_id and now < d.expires_at
             and (stay.check_in is None or stay.check_in <= now) and (stay.check_out is None or now < stay.check_out)}
            for d in result.scalars()]


@router.post("/{assignment_id}/devices/{device_id}/revoke", status_code=204)
async def revoke_device(assignment_id: int, device_id: int, db: AsyncSession = Depends(get_db)):
    device = await db.get(GuestDevice, device_id)
    if not device or device.assignment_id != assignment_id:
        raise HTTPException(404, "Device not found")
    device.revoked_at = datetime.now(timezone.utc)
    await audit_log.log(db, "door.device_revoked", f"Device id={device_id} revoked for booking id={assignment_id}")


@router.post("/{assignment_id}/revoke-access", status_code=204)
async def revoke_access(assignment_id: int, db: AsyncSession = Depends(get_db)):
    stay = await db.get(GuestRoom, assignment_id)
    if not stay:
        raise HTTPException(404, "Assignment not found")
    stay.access_revoked_at = datetime.now(timezone.utc)
    stay.key_version += 1
    await audit_log.log(db, "door.stay_revoked", f"Guest access disabled for booking id={assignment_id}")
