"""add weekly_digest_send and email_preference.weekly_digest_opt_out

Revision ID: 0fc98ab429b5
Revises: 652a19e0a9b1
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0fc98ab429b5'
down_revision: Union[str, None] = '652a19e0a9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "weekly_digest_send" not in existing_tables:
        op.create_table(
            "weekly_digest_send",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("dedupe_key", sa.String(length=100), nullable=False),
            sa.Column(
                "org_id",
                sa.BigInteger(),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="claimed"),
            sa.Column("claimed_at", sa.String(), nullable=True),
            sa.Column("sent_at", sa.String(), nullable=True),
            sa.Column("error", sa.String(length=500), nullable=True),
            sa.Column("provider_id", sa.String(), nullable=True),
            sa.UniqueConstraint("dedupe_key", name="uq_weekly_digest_send_dedupe"),
        )
        op.create_index("ix_weekly_digest_send_user_org", "weekly_digest_send", ["user_id", "org_id"])

    if "email_preference" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("email_preference")}
        if "weekly_digest_opt_out" not in existing_columns:
            op.add_column(
                "email_preference",
                sa.Column(
                    "weekly_digest_opt_out",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "email_preference" in existing_tables:
        existing_columns = {c["name"] for c in inspector.get_columns("email_preference")}
        if "weekly_digest_opt_out" in existing_columns:
            op.drop_column("email_preference", "weekly_digest_opt_out")

    if "weekly_digest_send" in existing_tables:
        op.drop_table("weekly_digest_send")
