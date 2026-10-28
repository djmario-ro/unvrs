from pydantic import BaseModel, Field


class PinValidateRequest(BaseModel):
    # Bounded so these values are safe to use as rate-limit keys.
    room_public_id: str = Field(min_length=1, max_length=64)
    pin: str = Field(pattern=r"^\d{6}$")
