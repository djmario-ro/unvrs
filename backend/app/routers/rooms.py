from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.room import Room
from app.schemas.room import RoomCreate, RoomRead, RoomUpdate
from app.utils import audit as audit_log
from app.utils.qr import generate_qr_png

router = APIRouter(prefix="/rooms", tags=["rooms"])


@router.get("", response_model=list[RoomRead])
async def list_rooms(
    skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Room).offset(skip).limit(limit))
    return result.scalars().all()


@router.post("", response_model=RoomRead, status_code=status.HTTP_201_CREATED)
async def create_room(body: RoomCreate, db: AsyncSession = Depends(get_db)):
    room = Room(**body.model_dump())
    db.add(room)
    await db.flush()
    await audit_log.log(db, "room.create", f"Created room '{room.name}' (id={room.id})")
    await db.refresh(room)
    return room


@router.get("/{room_id}", response_model=RoomRead)
async def get_room(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.patch("/{room_id}", response_model=RoomRead)
async def update_room(
    room_id: int, body: RoomUpdate, db: AsyncSession = Depends(get_db)
):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(room, field, value)
    await audit_log.log(db, "room.update", f"Updated room id={room_id}")
    await db.refresh(room)
    return room


@router.delete("/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    await audit_log.log(db, "room.delete", f"Deleted room '{room.name}' (id={room_id})")
    await db.delete(room)


@router.get("/{room_id}/qr", summary="Get QR code PNG for door access")
async def get_room_qr(room_id: int, db: AsyncSession = Depends(get_db)):
    room = await db.get(Room, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    door_url = f"{settings.frontend_origin}/door/{room_id}"
    png_bytes = generate_qr_png(door_url)
    return Response(content=png_bytes, media_type="image/png")
