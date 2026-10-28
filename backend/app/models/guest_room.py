from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.guest import Guest
    from app.models.message_log import MessageLog
    from app.models.room import Room


class GuestRoom(Base):
    """One stay of a guest in a room, with its own PIN.

    The same guest may have several rows for the same room (repeat visits);
    the router rejects overlapping dates for a room.
    """

    __tablename__ = "guest_rooms"
    __table_args__ = (
        # Unique so the door lookup can never match two rows; also the index
        # for the hot lookup: WHERE room_id = ? AND pin = ?
        UniqueConstraint("room_id", "pin", name="uq_guest_rooms_room_pin"),
    )

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
    # First time the guest entered their PIN at the door — marks actual check-in.
    # Null means the reservation is still "booked" (guest hasn't arrived).
    checked_in_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    guest: Mapped["Guest"] = relationship("Guest", back_populates="assignments")
    room: Mapped["Room"] = relationship("Room", back_populates="assignments")
    messages: Mapped[list["MessageLog"]] = relationship(
        "MessageLog", back_populates="assignment", cascade="all, delete-orphan", passive_deletes=True
    )
