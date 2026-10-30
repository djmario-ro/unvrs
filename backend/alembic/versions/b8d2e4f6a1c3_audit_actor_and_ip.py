"""audit: record the acting user and client ip

Revision ID: b8d2e4f6a1c3
Revises: a7c1d2e3f4b5
Create Date: 2026-10-28 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d2e4f6a1c3'
down_revision: Union[str, None] = 'a7c1d2e3f4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('audit', sa.Column('actor_id', sa.Integer(), nullable=True))
    op.add_column('audit', sa.Column('actor', sa.String(length=50), nullable=True))
    op.add_column('audit', sa.Column('ip', sa.String(length=64), nullable=True))
    op.create_foreign_key(
        'fk_audit_actor_id_users', 'audit', 'users', ['actor_id'], ['id'], ondelete='SET NULL'
    )


def downgrade() -> None:
    op.drop_constraint('fk_audit_actor_id_users', 'audit', type_='foreignkey')
    op.drop_column('audit', 'ip')
    op.drop_column('audit', 'actor')
    op.drop_column('audit', 'actor_id')
