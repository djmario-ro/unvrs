from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

Role = Literal["admin", "frontdesk"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=8, max_length=200)
    role: Role = "frontdesk"


class UserUpdate(BaseModel):
    password: str | None = Field(None, min_length=8, max_length=200)
    role: Role | None = None


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    role: str
    created_at: datetime
