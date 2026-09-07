"""Add rubric_scores to assignment task submission

Adds ``assignmenttasksubmission.rubric_scores`` (nullable JSON): per-criterion
points a teacher awarded against a task's rubric (stored opaquely in the
task's own ``contents["rubric"]``, no schema change needed there — same
"no migration" pattern as pool_size/shuffle_questions/etc.).

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'a0b1c2d3e4f5'
down_revision: Union[str, None] = 'f9a0b1c2d3e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignmenttasksubmission' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignmenttasksubmission')}
        if 'rubric_scores' not in existing_columns:
            op.add_column(
                'assignmenttasksubmission',
                sa.Column('rubric_scores', sa.JSON(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignmenttasksubmission' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignmenttasksubmission')}
        if 'rubric_scores' in existing_columns:
            op.drop_column('assignmenttasksubmission', 'rubric_scores')
