from datetime import datetime

from pydantic import BaseModel, EmailStr


class GuestBase(BaseModel):
    firstname: str
    lastname: str
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None


class GuestCreate(GuestBase):
    pass


class GuestUpdate(BaseModel):
    firstname: str | None = None
    lastname: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None


class GuestRead(GuestBase):
    model_config = {"from_attributes": True}

    id: int
    created_at: datetime
    updated_at: datetime
