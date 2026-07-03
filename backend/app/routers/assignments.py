from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.guest_room import GuestRoom
from app.schemas.guest_room import GuestRoomCreate, GuestRoomRead
from app.utils import audit as audit_log
from app.utils.pin import generate_pin

router = APIRouter(prefix="/assignments", tags=["assignments"])


async def _load_assignment(db: AsyncSession, assignment_id: int) -> GuestRoom:
    result = await db.execute(
        select(GuestRoom)
        .where(GuestRoom.id == assignment_id)
        .options(selectinload(GuestRoom.guest), selectinload(GuestRoom.room))
    )
    obj = result.scalar_one_or_none()
    if not obj:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return obj


@router.get("", response_model=list[GuestRoomRead])
async def list_assignments(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(GuestRoom)
        .options(selectinload(GuestRoom.guest), selectinload(GuestRoom.room))
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.post("", response_model=GuestRoomRead, status_code=status.HTTP_201_CREATED)
async def create_assignment(body: GuestRoomCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(GuestRoom).where(
            GuestRoom.guest_id == body.guest_id, GuestRoom.room_id == body.room_id
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409, detail="This guest is already assigned to this room"
        )
    pin = generate_pin()
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
    assignment.pin = generate_pin()
    await audit_log.log(
        db, "assignment.pin_regenerated", f"PIN regenerated for assignment id={assignment_id}"
    )
    return await _load_assignment(db, assignment_id)
