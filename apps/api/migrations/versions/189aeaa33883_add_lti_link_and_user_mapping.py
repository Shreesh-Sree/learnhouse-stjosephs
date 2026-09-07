"""add lti_link and lti_user_mapping

Revision ID: 189aeaa33883
Revises: 3ecefad8feb9
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '189aeaa33883'
down_revision: Union[str, None] = '3ecefad8feb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "lti_link" not in existing_tables:
        op.create_table(
            "lti_link",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("link_uuid", sa.String(length=100), nullable=False, server_default=""),
            sa.Column(
                "org_id",
                sa.Integer(),
                sa.ForeignKey("organization.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "course_id",
                sa.Integer(),
                sa.ForeignKey("course.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("consumer_key", sa.String(length=100), nullable=False, unique=True),
            sa.Column("consumer_secret_encrypted", sa.Text(), nullable=False, server_default=""),
            sa.Column("label", sa.String(length=200), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                sa.ForeignKey("user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("creation_date", sa.String(), nullable=False, server_default=""),
            sa.Column("update_date", sa.String(), nullable=False, server_default=""),
        )
        op.create_index("ix_lti_link_link_uuid", "lti_link", ["link_uuid"])
        op.create_index("ix_lti_link_course_id", "lti_link", ["course_id"])
        op.create_index("ix_lti_link_consumer_key", "lti_link", ["consumer_key"])

    if "lti_user_mapping" not in existing_tables:
        op.create_table(
            "lti_user_mapping",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("consumer_key", sa.String(length=100), nullable=False),
            sa.Column("lti_user_id", sa.String(length=255), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("creation_date", sa.String(), nullable=False, server_default=""),
            sa.UniqueConstraint("consumer_key", "lti_user_id", name="uq_lti_user_mapping_key_user"),
        )
        op.create_index("ix_lti_user_mapping_consumer_key", "lti_user_mapping", ["consumer_key"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "lti_user_mapping" in existing_tables:
        op.drop_table("lti_user_mapping")
    if "lti_link" in existing_tables:
        op.drop_table("lti_link")
