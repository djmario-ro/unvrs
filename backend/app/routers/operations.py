"""Limited room operations without guest identities, PINs or lock actuators."""

from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.database import get_db
from app.dependencies import require_housekeeping, require_maintenance, require_roles
from app.models.property import MANAGERS, RECEPTION
from app.models.room import Room
from app.models.guest_room import GuestRoom
from app.models.maintenance import MaintenanceTicket
from app.routers.dashboard import _room_status
from app.utils import audit as audit_log

router = APIRouter(prefix="/operations", tags=["operations"])


async def operational_rooms(db):
    rows = (
        await db.scalars(
            select(Room)
            .options(selectinload(Room.assignments).selectinload(GuestRoom.guest))
            .order_by(Room.name)
        )
    ).all()
    now = datetime.now(timezone.utc)
    return [
        {
            "id": room.id,
            "name": room.name,
            "floor": room.floor,
            "status": _room_status(room, now)[0],
            "cleaned_at": room.cleaned_at,
        }
        for room in rows
    ]


@router.get("/housekeeping", dependencies=[Depends(require_housekeeping)])
async def housekeeping(db: AsyncSession = Depends(get_db)):
    return await operational_rooms(db)


@router.post(
    "/housekeeping/{room_id}/cleaned",
    status_code=204,
    dependencies=[Depends(require_housekeeping)],
)
async def cleaned(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(404, "Room not found")
    room.cleaned_at = datetime.now(timezone.utc)
    await audit_log.log(db, "room.cleaned", f"Marked room id={room_id} cleaned")


@router.get("/maintenance/rooms", dependencies=[Depends(require_maintenance)])
async def maintenance_rooms(db: AsyncSession = Depends(get_db)):
    return await operational_rooms(db)


class TicketCreate(BaseModel):
    room_id: int
    title: str = Field(min_length=1, max_length=160)
    description: str = Field("", max_length=4000)


class TicketUpdate(BaseModel):
    status: Literal["open", "in_progress", "resolved"]


class TicketRead(BaseModel):
    model_config = {"from_attributes": True}
    id: int
    room_id: int
    title: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime


@router.get(
    "/maintenance",
    response_model=list[TicketRead],
    dependencies=[Depends(require_maintenance)],
)
async def tickets(db: AsyncSession = Depends(get_db)):
    return (
        await db.scalars(
            select(MaintenanceTicket)
            .order_by(MaintenanceTicket.created_at.desc())
            .limit(500)
        )
    ).all()


@router.post(
    "/maintenance",
    response_model=TicketRead,
    status_code=201,
    dependencies=[Depends(require_roles(*RECEPTION, "housekeeping", "maintenance"))],
)
async def report(body: TicketCreate, db: AsyncSession = Depends(get_db)):
    if not await db.get(Room, body.room_id):
        raise HTTPException(404, "Room not found")
    ticket = MaintenanceTicket(**body.model_dump())
    db.add(ticket)
    await db.flush()
    await audit_log.log(
        db,
        "maintenance.create",
        f"Reported maintenance ticket id={ticket.id} room id={body.room_id}",
    )
    return ticket


@router.patch(
    "/maintenance/{ticket_id}",
    response_model=TicketRead,
    dependencies=[Depends(require_maintenance)],
)
async def update(
    ticket_id: int, body: TicketUpdate, db: AsyncSession = Depends(get_db)
):
    ticket = await db.get(MaintenanceTicket, ticket_id)
    if not ticket:
        raise HTTPException(404, "Maintenance ticket not found")
    ticket.status = body.status
    await db.flush()
    await db.refresh(ticket)
    await audit_log.log(
        db, "maintenance.update", f"Maintenance ticket id={ticket_id}: {body.status}"
    )
    return ticket
