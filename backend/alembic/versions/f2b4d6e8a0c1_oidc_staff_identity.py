"""Federated staff identities and encrypted provider sessions."""
from alembic import op
import sqlalchemy as sa

revision = "f2b4d6e8a0c1"
down_revision = "e2a4b6c8d0f1"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("users", "password_hash", nullable=True)
    op.add_column("users", sa.Column("oidc_issuer", sa.String(512), nullable=True))
    op.add_column("users", sa.Column("oidc_subject", sa.String(255), nullable=True))
    op.create_unique_constraint("uq_users_oidc_identity", "users", ["oidc_issuer", "oidc_subject"])
    op.create_check_constraint("ck_users_oidc_identity_pair", "users", "(oidc_issuer IS NULL) = (oidc_subject IS NULL)")
    op.create_table(
        "oidc_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_version", sa.Integer(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=False),
        sa.Column("id_token", sa.Text(), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("provider_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_oidc_sessions_user_id", "oidc_sessions", ["user_id"])
    op.create_index("ix_oidc_sessions_expires_at", "oidc_sessions", ["expires_at"])


def downgrade():
    # External-only users deliberately have no password. Never invent credentials
    # or silently delete users to force a rollback to a password-only schema.
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM users WHERE password_hash IS NULL LIMIT 1")).first():
        raise RuntimeError("External-only users exist; choose a deliberate identity rollback before downgrading")
    op.drop_table("oidc_sessions")
    op.drop_constraint("ck_users_oidc_identity_pair", "users", type_="check")
    op.drop_constraint("uq_users_oidc_identity", "users", type_="unique")
    op.drop_column("users", "oidc_subject")
    op.drop_column("users", "oidc_issuer")
    op.alter_column("users", "password_hash", nullable=False)
