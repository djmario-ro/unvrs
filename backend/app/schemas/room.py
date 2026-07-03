from datetime import datetime

from pydantic import BaseModel


class RoomBase(BaseModel):
    name: str
    description: str | None = None


class RoomCreate(RoomBase):
    pass


class RoomUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class RoomRead(RoomBase):
    model_config = {"from_attributes": True}

    id: int
    created_at: datetime
