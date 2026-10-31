from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.utils.pin import generate_public_id

if TYPE_CHECKING:
    from app.models.guest_room import GuestRoom
    from app.models.room_image import RoomImage


class Room(Base):
    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # Unguessable id for public/guest-facing links (QR, door page)
    public_id: Mapped[str] = mapped_column(
        String(22), unique=True, index=True, default=generate_public_id
    )
    name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    homeassistant_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Booking.com-style details
    room_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    size_sqm: Mapped[int | None] = mapped_column(nullable=True)
    max_occupancy: Mapped[int | None] = mapped_column(nullable=True)
    beds: Mapped[str | None] = mapped_column(String(200), nullable=True)
    price_per_night: Mapped[int | None] = mapped_column(nullable=True)
    floor: Mapped[int | None] = mapped_column(nullable=True)
    view: Mapped[str | None] = mapped_column(String(100), nullable=True)
    amenities: Mapped[list[str]] = mapped_column(JSON, default=list)
    smoking: Mapped[bool] = mapped_column(default=False)
    # Housekeeping: last time the room was marked cleaned (after a checkout)
    cleaned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # passive_deletes: the FKs are ON DELETE CASCADE, so deleting a room must
    # not load every booking and image blob just to delete them row by row.
    assignments: Mapped[list["GuestRoom"]] = relationship(
        "GuestRoom",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="GuestRoom.check_in",
    )
    images: Mapped[list["RoomImage"]] = relationship(
        "RoomImage",
        back_populates="room",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RoomImage.id",
    )
