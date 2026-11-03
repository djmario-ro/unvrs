from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    """A global staff identity; property memberships authorize access.

    The legacy role column is retained for compatibility with old images only.
    """

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("oidc_issuer", "oidc_subject", name="uq_users_oidc_identity"),
        CheckConstraint(
            "(oidc_issuer IS NULL) = (oidc_subject IS NULL)",
            name="ck_users_oidc_identity_pair",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    oidc_issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    oidc_subject: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="frontdesk")
    # Bumped when the password changes; a JWT carrying an older value is
    # rejected, so changing a password signs that user's sessions out.
    token_version: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    @property
    def roles(self) -> list[str]:
        return getattr(self, "_active_roles", [])

    @property
    def effective_role(self) -> str:
        from app.models.property import ROLES

        return next((role for role in ROLES if role in self.roles), "frontdesk")

    @property
    def active_property_id(self) -> int | None:
        return getattr(self, "_active_property_id", None)

    @property
    def properties(self) -> list[dict]:
        return getattr(self, "_properties", [])
