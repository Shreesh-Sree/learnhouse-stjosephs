"""Add assignment extensions

Adds the ``assignment_extension`` table backing per-student assignment
deadline overrides.

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = 'a0b1c2d3e4f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment_extension' not in inspector.get_table_names():
        op.create_table(
            'assignment_extension',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('extension_uuid', sa.String(), nullable=False, server_default=''),
            sa.Column(
                'assignment_id', sa.Integer(),
                sa.ForeignKey('assignment.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'user_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'granted_by_user_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column('extended_due_date', sa.String(), nullable=False),
            sa.Column('reason', sa.Text(), nullable=True),
            sa.Column('creation_date', sa.String(), nullable=False, server_default=''),
            sa.Column('update_date', sa.String(), nullable=False, server_default=''),
            sa.UniqueConstraint(
                'assignment_id', 'user_id',
                name='uq_assignment_extension_assignment_user',
            ),
        )
        op.create_index(
            'ix_assignment_extension_assignment_id', 'assignment_extension', ['assignment_id'],
        )
        op.create_index(
            'ix_assignment_extension_extension_uuid', 'assignment_extension', ['extension_uuid'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment_extension' in inspector.get_table_names():
        op.drop_index('ix_assignment_extension_extension_uuid', table_name='assignment_extension')
        op.drop_index('ix_assignment_extension_assignment_id', table_name='assignment_extension')
        op.drop_table('assignment_extension')
