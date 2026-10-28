from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Audit(Base):
    __tablename__ = "audit"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    operation: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(Text)
    # Who did it: the staff user, if any (door and system events have none).
    # The username is denormalized so rows stay readable after a user is deleted.
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
