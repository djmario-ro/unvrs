"""Property-scoped staff roles and operational data.

Revision ID: a3c5e7f901b2
Revises: f2b4d6e8a0c1
"""

from alembic import op
import sqlalchemy as sa

revision = "a3c5e7f901b2"
down_revision = "f2b4d6e8a0c1"
branch_labels = None
depends_on = None
TABLES = (
    "guests",
    "rooms",
    "guest_rooms",
    "room_images",
    "message_logs",
    "guest_devices",
    "audit",
)


def upgrade():
    op.create_table(
        "properties",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
    )
    op.execute(
        "INSERT INTO properties (id,name,slug) VALUES (1,'Retreat 480','retreat-480')"
    )
    op.execute("SELECT setval(pg_get_serial_sequence('properties','id'),1)")
    op.create_table(
        "property_memberships",
        sa.Column(
            "user_id",
            sa.Integer,
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "property_id",
            sa.Integer,
            sa.ForeignKey("properties.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("roles", sa.JSON, nullable=False),
        sa.CheckConstraint(
            'jsonb_array_length(roles::jsonb)>0 AND roles::jsonb <@ \'["owner","administrator","frontdesk","housekeeping","maintenance"]\'::jsonb',
            name="ck_membership_roles",
        ),
    )
    op.execute("""INSERT INTO property_memberships(user_id,property_id,roles)
                  SELECT id,1,json_build_array(CASE WHEN role='admin' THEN 'administrator' ELSE role END) FROM users""")
    for table in TABLES:
        op.add_column(table, sa.Column("property_id", sa.Integer, nullable=True))
        op.execute(f"UPDATE {table} SET property_id=1")
        if table != "audit":
            op.alter_column(
                table, "property_id", nullable=False, server_default=sa.text("1")
            )
        op.create_foreign_key(
            f"fk_{table}_property", table, "properties", ["property_id"], ["id"]
        )
        op.create_index(f"ix_{table}_property_id", table, ["property_id"])
    op.drop_constraint("guests_email_key", "guests", type_="unique")
    op.create_unique_constraint(
        "uq_guests_property_email", "guests", ["property_id", "email"]
    )
    op.drop_constraint("rooms_name_key", "rooms", type_="unique")
    op.create_unique_constraint(
        "uq_rooms_property_name", "rooms", ["property_id", "name"]
    )
    op.create_table(
        "maintenance_tickets",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "property_id", sa.Integer, sa.ForeignKey("properties.id"), nullable=False
        ),
        sa.Column(
            "room_id",
            sa.Integer,
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_maintenance_tickets_property_id", "maintenance_tickets", ["property_id"]
    )
    # Enforce tenant consistency even for non-HTTP database writers. Existing
    # ORM relationships keep their simple foreign keys for loading.
    for parent in ("rooms", "guests", "guest_rooms"):
        op.create_unique_constraint(
            f"uq_{parent}_property_id", parent, ["property_id", "id"]
        )
    for table, column, parent in (
        ("guest_rooms", "guest_id", "guests"),
        ("guest_rooms", "room_id", "rooms"),
        ("room_images", "room_id", "rooms"),
        ("message_logs", "assignment_id", "guest_rooms"),
        ("guest_devices", "assignment_id", "guest_rooms"),
        ("guest_devices", "room_id", "rooms"),
        ("maintenance_tickets", "room_id", "rooms"),
    ):
        op.create_foreign_key(
            f"fk_{table}_{column}_tenant",
            table,
            parent,
            ["property_id", column],
            ["property_id", "id"],
            ondelete="CASCADE",
        )


def downgrade():
    raise RuntimeError(
        "Property isolation cannot be safely downgraded; roll back application images without dropping tenant data"
    )
