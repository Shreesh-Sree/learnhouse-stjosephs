"""Add Safe Exam Browser fields to assignment

Adds three nullable columns to ``assignment``:

- ``require_safe_exam_browser`` (bool, default false) — gates submission on a
  verified Safe Exam Browser session when true.
- ``seb_config_key`` (text) — per-assignment secret used to compute/verify the
  SEB Config Key hash. Generated server-side on first enable.
- ``seb_quit_password`` (text) — proctor break-glass password for SEB's own
  quit UI. Unused by the primary submit-then-auto-exit flow.

Revision ID: f3a4b5c6d7e8
Revises: b1c2d3e4f5a6
Create Date: 2026-09-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'f3a4b5c6d7e8'
down_revision: Union[str, None] = 'b1c2d3e4f5a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('assignment')}

    if 'require_safe_exam_browser' not in existing_columns:
        op.add_column(
            'assignment',
            sa.Column(
                'require_safe_exam_browser',
                sa.Boolean(),
                nullable=True,
                server_default=sa.false(),
            ),
        )

    if 'seb_config_key' not in existing_columns:
        op.add_column(
            'assignment',
            sa.Column('seb_config_key', sa.Text(), nullable=True),
        )

    if 'seb_quit_password' not in existing_columns:
        op.add_column(
            'assignment',
            sa.Column('seb_quit_password', sa.Text(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' not in inspector.get_table_names():
        return

    existing_columns = {col['name'] for col in inspector.get_columns('assignment')}

    if 'seb_quit_password' in existing_columns:
        op.drop_column('assignment', 'seb_quit_password')

    if 'seb_config_key' in existing_columns:
        op.drop_column('assignment', 'seb_config_key')

    if 'require_safe_exam_browser' in existing_columns:
        op.drop_column('assignment', 'require_safe_exam_browser')
