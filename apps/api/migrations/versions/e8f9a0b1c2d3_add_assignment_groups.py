"""Add assignment groups for group/team submission

Adds ``assignment.allow_group_submission`` / ``group_min_size`` /
``group_max_size``, and the ``assignment_group`` / ``assignment_group_member``
tables backing team-based assignment submission.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'e8f9a0b1c2d3'
down_revision: Union[str, None] = 'd7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'allow_group_submission' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column(
                    'allow_group_submission', sa.Boolean(),
                    nullable=True, server_default=sa.false(),
                ),
            )
        if 'group_min_size' not in existing_columns:
            op.add_column('assignment', sa.Column('group_min_size', sa.Integer(), nullable=True))
        if 'group_max_size' not in existing_columns:
            op.add_column('assignment', sa.Column('group_max_size', sa.Integer(), nullable=True))

    if 'assignment_group' not in inspector.get_table_names():
        op.create_table(
            'assignment_group',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(), nullable=False),
            sa.Column('group_uuid', sa.String(), nullable=False, server_default=''),
            sa.Column(
                'assignment_id', sa.Integer(),
                sa.ForeignKey('assignment.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'org_id', sa.Integer(),
                sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'course_id', sa.Integer(),
                sa.ForeignKey('course.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column('creation_date', sa.String(), nullable=False, server_default=''),
        )
        op.create_index(
            'ix_assignment_group_assignment_id', 'assignment_group', ['assignment_id'],
        )
        op.create_index(
            'ix_assignment_group_group_uuid', 'assignment_group', ['group_uuid'],
        )

    if 'assignment_group_member' not in inspector.get_table_names():
        op.create_table(
            'assignment_group_member',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column(
                'group_id', sa.Integer(),
                sa.ForeignKey('assignment_group.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'assignment_id', sa.Integer(),
                sa.ForeignKey('assignment.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'user_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column('creation_date', sa.String(), nullable=False, server_default=''),
            sa.UniqueConstraint(
                'assignment_id', 'user_id',
                name='uq_assignment_group_member_assignment_user',
            ),
        )
        op.create_index(
            'ix_assignment_group_member_group_id', 'assignment_group_member', ['group_id'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment_group_member' in inspector.get_table_names():
        op.drop_index('ix_assignment_group_member_group_id', table_name='assignment_group_member')
        op.drop_table('assignment_group_member')

    if 'assignment_group' in inspector.get_table_names():
        op.drop_index('ix_assignment_group_group_uuid', table_name='assignment_group')
        op.drop_index('ix_assignment_group_assignment_id', table_name='assignment_group')
        op.drop_table('assignment_group')

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        for col in ('group_max_size', 'group_min_size', 'allow_group_submission'):
            if col in existing_columns:
                op.drop_column('assignment', col)
