from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Role = Literal["owner", "administrator", "frontdesk", "housekeeping", "maintenance"]


class RoleInput(BaseModel):
    role: Role | Literal["admin"] | None = None
    roles: list[Role] | None = Field(None, min_length=1, max_length=5)

    @model_validator(mode="after")
    def normalize_roles(self):
        if self.roles is not None and self.role is not None:
            raise ValueError("Specify roles or role, not both")
        return self

    def assigned_roles(self):
        return (
            sorted(set(self.roles))
            if self.roles
            else ["administrator" if self.role == "admin" else self.role or "frontdesk"]
        )


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=200)


class UserCreate(RoleInput):
    username: str = Field(min_length=1, max_length=50)
    password: str | None = Field(None, min_length=8, max_length=200)
    oidc_subject: str | None = Field(None, pattern=r"^[!-~]{1,255}$")


class UserUpdate(RoleInput):
    password: str | None = Field(None, min_length=8, max_length=200)
    oidc_subject: str | None = Field(None, pattern=r"^[!-~]{1,255}$")


class UserRead(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    username: str
    role: str = Field(validation_alias="effective_role")
    roles: list[Role]
    property_id: int | None = Field(None, validation_alias="active_property_id")
    properties: list[dict] = Field(default_factory=list)
    oidc_subject: str | None = None
    created_at: datetime
