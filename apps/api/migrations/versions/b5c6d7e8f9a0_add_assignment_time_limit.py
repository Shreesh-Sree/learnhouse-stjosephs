"""Add assignment time limit and attempt start tracking

Adds two nullable columns:

- ``assignment.time_limit_minutes`` — per-attempt duration, independent of
  due_date (an absolute deadline). NULL means no time limit.
- ``assignmentusersubmission.started_at`` — when the learner's current
  attempt clock started, set once by start_assignment_attempt and never
  client-settable.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'b5c6d7e8f9a0'
down_revision: Union[str, None] = 'a4b5c6d7e8f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'time_limit_minutes' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column('time_limit_minutes', sa.Integer(), nullable=True),
            )

    if 'assignmentusersubmission' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignmentusersubmission')}
        if 'started_at' not in existing_columns:
            op.add_column(
                'assignmentusersubmission',
                sa.Column('started_at', sa.String(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignmentusersubmission' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignmentusersubmission')}
        if 'started_at' in existing_columns:
            op.drop_column('assignmentusersubmission', 'started_at')

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'time_limit_minutes' in existing_columns:
            op.drop_column('assignment', 'time_limit_minutes')
