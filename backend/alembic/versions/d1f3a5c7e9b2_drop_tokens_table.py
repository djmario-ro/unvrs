"""drop the unused tokens table

The door flow is a one-shot PIN check; it never issued session tokens, so
the table was dead. See CQ-3 / B-15.

Revision ID: d1f3a5c7e9b2
Revises: c9e3f5a7b2d4
Create Date: 2026-10-28 20:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1f3a5c7e9b2'
down_revision: Union[str, None] = 'c9e3f5a7b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table('tokens')


def downgrade() -> None:
    op.create_table(
        'tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('valid_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['assignment_id'], ['guest_rooms.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_tokens_token', 'tokens', ['token'], unique=True)
    op.create_index('ix_tokens_assignment_id', 'tokens', ['assignment_id'])
    op.create_index('ix_tokens_id', 'tokens', ['id'])
