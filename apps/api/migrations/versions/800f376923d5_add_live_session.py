"""add live_session

Revision ID: 800f376923d5
Revises: 231566e5217e
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '800f376923d5'
down_revision: Union[str, None] = '231566e5217e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "live_session" not in existing_tables:
        op.create_table(
            "live_session",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("session_uuid", sa.String(length=100), nullable=False, server_default=""),
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
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("meeting_url", sa.String(length=2048), nullable=False),
            sa.Column("start_time", sa.String(length=40), nullable=False),
            sa.Column("end_time", sa.String(length=40), nullable=True),
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                sa.ForeignKey("user.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("creation_date", sa.String(), nullable=False, server_default=""),
            sa.Column("update_date", sa.String(), nullable=False, server_default=""),
        )
        op.create_index("ix_live_session_session_uuid", "live_session", ["session_uuid"])
        op.create_index("ix_live_session_course_start", "live_session", ["course_id", "start_time"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "live_session" in existing_tables:
        op.drop_table("live_session")
