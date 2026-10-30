"""drop uq_guest_room so a returning guest can stay in the same room again

Revision ID: a7c1d2e3f4b5
Revises: f1a2b3c4d5e6
Create Date: 2026-10-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a7c1d2e3f4b5'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_guest_room', 'guest_rooms', type_='unique')


def downgrade() -> None:
    # Fails if the same guest has meanwhile been booked twice into one room;
    # those rows must be removed by hand before downgrading.
    op.create_unique_constraint('uq_guest_room', 'guest_rooms', ['guest_id', 'room_id'])
