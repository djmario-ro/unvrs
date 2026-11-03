"""Property membership is the source of staff authorization."""

from sqlalchemy import ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

ROLES = ("owner", "administrator", "frontdesk", "housekeeping", "maintenance")
MANAGERS = {"owner", "administrator"}
RECEPTION = MANAGERS | {"frontdesk"}


class Property(Base):
    __tablename__ = "properties"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(100), unique=True)


class PropertyMembership(Base):
    __tablename__ = "property_memberships"
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id", ondelete="CASCADE"), primary_key=True
    )
    roles: Mapped[list[str]] = mapped_column(JSON)


class PropertyScoped:
    property_id: Mapped[int] = mapped_column(
        ForeignKey("properties.id"), index=True, default=1
    )
