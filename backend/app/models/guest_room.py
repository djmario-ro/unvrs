from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.guest import Guest
    from app.models.room import Room
    from app.models.token import Token


class GuestRoom(Base):
    """Links a guest to a room with a unique PIN per assignment."""

    __tablename__ = "guest_rooms"
    __table_args__ = (UniqueConstraint("guest_id", "room_id", name="uq_guest_room"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    guest_id: Mapped[int] = mapped_column(ForeignKey("guests.id", ondelete="CASCADE"))
    room_id: Mapped[int] = mapped_column(ForeignKey("rooms.id", ondelete="CASCADE"))
    pin: Mapped[str] = mapped_column(String(10))
    check_in: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    check_out: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    guest: Mapped["Guest"] = relationship("Guest", back_populates="assignments")
    room: Mapped["Room"] = relationship("Room", back_populates="assignments")
    tokens: Mapped[list["Token"]] = relationship(
        "Token", back_populates="assignment", cascade="all, delete-orphan"
    )
