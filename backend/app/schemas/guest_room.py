from datetime import datetime

from pydantic import AwareDatetime, BaseModel

from app.schemas.guest import GuestRead
from app.schemas.room import RoomRead


class GuestRoomCreate(BaseModel):
    guest_id: int
    room_id: int
    # Aware only: a naive datetime would be compared against tz-aware DB values.
    check_in: AwareDatetime | None = None
    check_out: AwareDatetime | None = None


class GuestRoomUpdate(BaseModel):
    room_id: int | None = None
    check_in: AwareDatetime | None = None
    check_out: AwareDatetime | None = None


class GuestRoomRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    guest_id: int
    room_id: int
    pin: str
    check_in: datetime | None
    check_out: datetime | None
    checked_in_at: datetime | None = None
    access_revoked_at: datetime | None = None
    created_at: datetime
    guest: GuestRead | None = None
    room: RoomRead | None = None
