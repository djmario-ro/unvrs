"""add guest_room checked_in_at

Revision ID: f1a2b3c4d5e6
Revises: e99daaa379a1
Create Date: 2026-07-06 15:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e99daaa379a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'guest_rooms',
        sa.Column('checked_in_at', sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('guest_rooms', 'checked_in_at')
