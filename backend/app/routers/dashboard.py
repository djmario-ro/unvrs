from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.dependencies import get_current_user
from app.models.guest_room import GuestRoom
from app.models.room import Room

router = APIRouter(
    prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(get_current_user)]
)


def _guest_name(a) -> str | None:
    guest = a.guest
    return f"{guest.firstname} {guest.lastname}" if guest else None


def _room_status(room: Room, now: datetime) -> tuple[str, str | None]:
    """Return (status, guest_name), driven by check-in events (not the clock).

    status is available | booked | checked_in | checked_out.
    booked      = reservation exists, guest hasn't entered their PIN yet.
    checked_in  = guest entered the PIN (checked_in_at set) and hasn't checked out.
    checked_out = a checked-in stay has ended, room not yet cleaned.
    A reservation whose window lapsed without a PIN entry is a no-show (ignored).
    """
    staying = None
    pending = None
    last_stay_checkout: datetime | None = None
    for a in room.assignments:
        ended = a.check_out is not None and a.check_out < now
        if a.checked_in_at is not None:
            # Guest physically checked in at some point.
            if not ended:
                staying = a
            elif last_stay_checkout is None or a.check_out > last_stay_checkout:
                last_stay_checkout = a.check_out
        elif not ended:
            # Reservation awaiting arrival — keep the earliest by check-in time.
            if pending is None or (
                a.check_in is not None
                and (pending.check_in is None or a.check_in < pending.check_in)
            ):
                pending = a

    if staying is not None:
        return "checked_in", _guest_name(staying)
    if last_stay_checkout is not None and (
        room.cleaned_at is None or room.cleaned_at < last_stay_checkout
    ):
        return "checked_out", None
    if pending is not None:
        return "booked", _guest_name(pending)
    return "available", None


@router.get("/floors")
async def floors(db: AsyncSession = Depends(get_db)):
    """Rooms grouped by floor with live housekeeping status (highest floor first)."""
    now = datetime.now(tz=timezone.utc)
    result = await db.execute(
        select(Room).options(
            selectinload(Room.assignments).selectinload(GuestRoom.guest)
        )
    )
    rooms = result.scalars().all()

    grouped: dict[int, list[dict]] = {}
    for room in rooms:
        status, guest_name = _room_status(room, now)
        floor = room.floor if room.floor is not None else 0
        grouped.setdefault(floor, []).append(
            {
                "id": room.id,
                "name": room.name,
                "room_type": room.room_type,
                "status": status,
                "occupied": status == "checked_in",
                "guest": guest_name,
            }
        )

    floors = []
    for floor in sorted(grouped, reverse=True):
        rms = sorted(grouped[floor], key=lambda r: r["name"])
        available = sum(1 for r in rms if r["status"] == "available")
        floors.append(
            {
                "floor": floor,
                "total": len(rms),
                "available": available,
                "rooms": rms,
            }
        )

    all_rooms = [r for f in floors for r in f["rooms"]]
    total = len(all_rooms)
    counts = {"available": 0, "booked": 0, "checked_in": 0, "checked_out": 0}
    for r in all_rooms:
        counts[r["status"]] += 1
    return {
        "floors": floors,
        "totals": {
            "total": total,
            "available": counts["available"],
            "booked": counts["booked"],
            "occupied": counts["checked_in"],
            "cleaning": counts["checked_out"],
        },
    }
