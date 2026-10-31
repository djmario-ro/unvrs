from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, Field


def specific_entity(value: str) -> str:
    if value in {"script.turn_on", "script.turn_off", "script.toggle", "script.reload"}:
        raise ValueError("Choose a specific lock or script entity, not a script management action")
    return value


HomeAssistantEntityId = Annotated[str, Field(max_length=255, pattern=r"^(lock|script)\.[a-z0-9_]+$"), AfterValidator(specific_entity)]

# Lengths mirror the String(n) columns in models/room.py, so the API returns
# 422 instead of letting the database fail with a 500.


class RoomImageRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    is_cover: bool
    content_type: str
    created_at: datetime


class RoomBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    homeassistant_entity_id: HomeAssistantEntityId | None = None
    room_type: str | None = Field(None, max_length=50)
    size_sqm: int | None = Field(None, ge=0)
    max_occupancy: int | None = Field(None, ge=0)
    beds: str | None = Field(None, max_length=200)
    price_per_night: int | None = Field(None, ge=0)
    floor: int | None = None
    view: str | None = Field(None, max_length=100)
    amenities: list[str] = []
    smoking: bool = False


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = Field(None, max_length=1000)
    homeassistant_entity_id: HomeAssistantEntityId | None = None
    room_type: str | None = Field(None, max_length=50)
    size_sqm: int | None = Field(None, ge=0)
    max_occupancy: int | None = Field(None, ge=0)
    beds: str | None = Field(None, max_length=200)
    price_per_night: int | None = Field(None, ge=0)
    floor: int | None = None
    view: str | None = Field(None, max_length=100)
    amenities: list[str] | None = None
    smoking: bool | None = None


class RoomRead(RoomBase):
    model_config = {"from_attributes": True}

    id: int
    public_id: str
    created_at: datetime
    images: list[RoomImageRead] = []
