from datetime import datetime

from pydantic import BaseModel


class PinValidateRequest(BaseModel):
    room_id: int
    pin: str


class TokenRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    assignment_id: int
    valid_until: datetime
    revoked_at: datetime | None
    created_at: datetime
