"""users.token_version; unique (room_id, pin)

Revision ID: c9e3f5a7b2d4
Revises: b8d2e4f6a1c3
Create Date: 2026-10-28 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9e3f5a7b2d4'
down_revision: Union[str, None] = 'b8d2e4f6a1c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('token_version', sa.Integer(), server_default='0', nullable=False),
    )
    # Replace the plain index with a unique constraint on (room_id, pin).
    op.drop_index('ix_guest_rooms_room_pin', table_name='guest_rooms')
    op.create_unique_constraint(
        'uq_guest_rooms_room_pin', 'guest_rooms', ['room_id', 'pin']
    )


def downgrade() -> None:
    op.drop_constraint('uq_guest_rooms_room_pin', 'guest_rooms', type_='unique')
    op.create_index('ix_guest_rooms_room_pin', 'guest_rooms', ['room_id', 'pin'])
    op.drop_column('users', 'token_version')
