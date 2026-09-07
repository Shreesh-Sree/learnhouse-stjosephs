"""add prerequisite_course_id and prerequisite_chapter_id

Revision ID: 231566e5217e
Revises: 0fc98ab429b5
Create Date: 2026-09-07 00:00:00.000000

"""
from typing import Union, Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '231566e5217e'
down_revision: Union[str, None] = '0fc98ab429b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    course_columns = {c["name"] for c in inspector.get_columns("course")}
    if "prerequisite_course_id" not in course_columns:
        op.add_column(
            "course",
            sa.Column(
                "prerequisite_course_id",
                sa.Integer(),
                sa.ForeignKey("course.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )

    chapter_columns = {c["name"] for c in inspector.get_columns("chapter")}
    if "prerequisite_chapter_id" not in chapter_columns:
        op.add_column(
            "chapter",
            sa.Column(
                "prerequisite_chapter_id",
                sa.Integer(),
                sa.ForeignKey("chapter.id", ondelete="SET NULL"),
                nullable=True,
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    chapter_columns = {c["name"] for c in inspector.get_columns("chapter")}
    if "prerequisite_chapter_id" in chapter_columns:
        op.drop_column("chapter", "prerequisite_chapter_id")

    course_columns = {c["name"] for c in inspector.get_columns("course")}
    if "prerequisite_course_id" in course_columns:
        op.drop_column("course", "prerequisite_course_id")
