"""add quiz_question_flag

Revision ID: 652a19e0a9b1
Revises: 189aeaa33883
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '652a19e0a9b1'
down_revision: Union[str, None] = '189aeaa33883'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "quiz_question_flag" not in existing_tables:
        op.create_table(
            "quiz_question_flag",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("flag_uuid", sa.String(length=100), nullable=False, server_default=""),
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
            sa.Column(
                "activity_id",
                sa.Integer(),
                sa.ForeignKey("activity.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("quiz_id", sa.String(length=100), nullable=False),
            sa.Column("question_id", sa.String(length=100), nullable=False),
            sa.Column("question_text_snapshot", sa.Text(), nullable=False, server_default=""),
            sa.Column("reason", sa.String(length=30), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column(
                "flagged_by_user_id",
                sa.Integer(),
                sa.ForeignKey("user.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "resolved_by_user_id",
                sa.Integer(),
                sa.ForeignKey("user.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("resolved_at", sa.String(), nullable=True),
            sa.Column("creation_date", sa.String(), nullable=False, server_default=""),
            sa.Column("update_date", sa.String(), nullable=False, server_default=""),
        )
        op.create_index("ix_quiz_question_flag_flag_uuid", "quiz_question_flag", ["flag_uuid"])
        op.create_index(
            "ix_quiz_question_flag_course_status", "quiz_question_flag", ["course_id", "status"]
        )
        op.create_index(
            "ix_quiz_question_flag_activity_question",
            "quiz_question_flag",
            ["activity_id", "question_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "quiz_question_flag" in existing_tables:
        op.drop_table("quiz_question_flag")
