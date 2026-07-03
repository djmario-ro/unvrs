from datetime import datetime

from pydantic import BaseModel

from app.schemas.guest import GuestRead
from app.schemas.room import RoomRead


class GuestRoomCreate(BaseModel):
    guest_id: int
    room_id: int
    check_in: datetime | None = None
    check_out: datetime | None = None


class GuestRoomRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    guest_id: int
    room_id: int
    pin: str
    check_in: datetime | None
    check_out: datetime | None
    created_at: datetime
    guest: GuestRead | None = None
    room: RoomRead | None = None
