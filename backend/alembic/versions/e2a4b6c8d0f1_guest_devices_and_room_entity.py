"""Room actuators and revocable guest device sessions."""
from alembic import op
import sqlalchemy as sa

revision = "e2a4b6c8d0f1"
down_revision = "d1f3a5c7e9b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("rooms", sa.Column("homeassistant_entity_id", sa.String(255), nullable=True))
    op.add_column("guest_rooms", sa.Column("key_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("guest_rooms", sa.Column("access_revoked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "guest_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("guest_rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("room_id", sa.Integer(), sa.ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("device_name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_guest_devices_assignment_id", "guest_devices", ["assignment_id"])
    # Carry the existing deployment mapping into the editable room field once.
    from app.config import settings
    for public_id, entity in settings.ha_door_scripts.items():
        op.get_bind().execute(sa.text("UPDATE rooms SET homeassistant_entity_id=:entity WHERE public_id=:pid"), {"entity": entity, "pid": public_id})


def downgrade():
    op.drop_table("guest_devices")
    op.drop_column("guest_rooms", "access_revoked_at")
    op.drop_column("guest_rooms", "key_version")
    op.drop_column("rooms", "homeassistant_entity_id")
