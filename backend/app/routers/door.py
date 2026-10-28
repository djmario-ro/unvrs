import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.guest_room import GuestRoom
from app.models.room import Room
from app.schemas.door import PinValidateRequest
from app.utils import audit as audit_log
from app.utils import ratelimit

router = APIRouter(prefix="/door", tags=["door"])
logger = logging.getLogger("app.door")


@router.post("/validate-pin")
async def validate_pin(
    body: PinValidateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Validate a guest PIN for a room. Public, one-shot check, rate-limited."""
    now = datetime.now(tz=timezone.utc)
    ip = ratelimit.client_ip(request)
    # Per-room cap blunts distributed brute force; per-IP cap stops one client
    # from hammering many rooms.
    ratelimit.enforce(f"door:room:{body.room_public_id}", max_attempts=10, window_seconds=60)
    ratelimit.enforce(f"door:ip:{ip}", max_attempts=20, window_seconds=60)

    room_result = await db.execute(
        select(Room).where(Room.public_id == body.room_public_id)
    )
    room = room_result.scalar_one_or_none()
    if not room:
        # Don't reveal whether the room link is valid.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN"
        )

    # The stay window is part of the match and every failure is the same 401,
    # so the response never reveals that a PIN belongs to a past or future stay.
    result = await db.execute(
        select(GuestRoom)
        .where(
            GuestRoom.room_id == room.id,
            GuestRoom.pin == body.pin,
            or_(GuestRoom.check_in.is_(None), GuestRoom.check_in <= now),
            or_(GuestRoom.check_out.is_(None), GuestRoom.check_out >= now),
        )
        .options(selectinload(GuestRoom.room), selectinload(GuestRoom.guest))
        .limit(1)
    )
    assignment = result.scalar_one_or_none()

    if not assignment:
        logger.info(
            "Door PIN rejected: room id=%s ip=%s xff=%r",
            room.id,
            ip,
            request.headers.get("x-forwarded-for", "")[:200],
        )
        # Own transaction: the 401 rolls the request's session back.
        await audit_log.log_detached("door.pin_rejected", f"Wrong PIN at room id={room.id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid PIN"
        )

    # First valid PIN entry checks the guest in (booked -> checked in).
    first_entry = assignment.checked_in_at is None
    if first_entry:
        assignment.checked_in_at = now
        await audit_log.log(
            db,
            "door.checkin",
            f"Guest checked in: guest id={assignment.guest_id} room id={room.id}",
        )

    await audit_log.log(
        db,
        "door.access",
        f"Door access granted: guest id={assignment.guest_id} room id={room.id}",
    )

    return {
        "message": "Access granted",
        "guest": f"{assignment.guest.firstname} {assignment.guest.lastname}",
        "room": assignment.room.name,
    }
