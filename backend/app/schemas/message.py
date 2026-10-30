from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Channel = Literal["sms", "whatsapp"]


class SendPinRequest(BaseModel):
    channels: list[Channel] = Field(min_length=1, max_length=2)

    @field_validator("channels")
    @classmethod
    def _dedupe(cls, channels: list[str]) -> list[str]:
        # Each channel is a paid/real send; never deliver the same one twice.
        return list(dict.fromkeys(channels))


class MessageLogRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    assignment_id: int
    channel: str
    recipient: str
    status: str  # sent | mocked | failed
    error: str | None
    created_at: datetime


class SendPinResult(BaseModel):
    results: list[MessageLogRead]
