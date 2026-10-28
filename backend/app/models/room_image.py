from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, LargeBinary, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.room import Room


class RoomImage(Base):
    """A room photo, stored inline in the database and served as an image."""

    __tablename__ = "room_images"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    room_id: Mapped[int] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    # Deferred: the blob is only needed when serving the image itself, never
    # when listing rooms or bookings. Load it with undefer(RoomImage.content).
    content: Mapped[bytes] = mapped_column(LargeBinary, deferred=True)
    is_cover: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    room: Mapped["Room"] = relationship("Room", back_populates="images")
