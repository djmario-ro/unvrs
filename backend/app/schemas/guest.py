from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

# Lengths mirror the String(n) columns in models/guest.py, so the API returns
# 422 instead of letting the database fail with a 500.


class GuestBase(BaseModel):
    firstname: str = Field(min_length=1, max_length=100)
    lastname: str = Field(min_length=1, max_length=100)
    email: EmailStr | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=1000)


class GuestCreate(GuestBase):
    pass


class GuestUpdate(BaseModel):
    firstname: str | None = Field(None, min_length=1, max_length=100)
    lastname: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=50)
    address: str | None = Field(None, max_length=500)
    notes: str | None = Field(None, max_length=1000)


class GuestRead(GuestBase):
    model_config = {"from_attributes": True}

    id: int
    created_at: datetime
    updated_at: datetime
