"""Add webcam proctoring fields

Adds ``assignment.require_webcam_proctoring`` (nullable bool, default false)
and the ``proctoring_snapshot`` table backing opportunistic webcam capture
during a proctored attempt.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'c6d7e8f9a0b1'
down_revision: Union[str, None] = 'b5c6d7e8f9a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'require_webcam_proctoring' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column(
                    'require_webcam_proctoring', sa.Boolean(),
                    nullable=True, server_default=sa.false(),
                ),
            )

    if 'proctoring_snapshot' not in inspector.get_table_names():
        op.create_table(
            'proctoring_snapshot',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('snapshot_uuid', sa.String(), nullable=False, server_default=''),
            sa.Column(
                'org_id', sa.Integer(),
                sa.ForeignKey('organization.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'course_id', sa.Integer(),
                sa.ForeignKey('course.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'activity_id', sa.Integer(),
                sa.ForeignKey('activity.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'assignment_id', sa.Integer(),
                sa.ForeignKey('assignment.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'user_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column('filename', sa.String(), nullable=False),
            sa.Column('captured_at', sa.String(), nullable=False, server_default=''),
            sa.Column('creation_date', sa.String(), nullable=False, server_default=''),
        )
        op.create_index(
            'ix_proctoring_snapshot_assignment_user',
            'proctoring_snapshot', ['assignment_id', 'user_id'],
        )
        op.create_index(
            'ix_proctoring_snapshot_snapshot_uuid',
            'proctoring_snapshot', ['snapshot_uuid'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'proctoring_snapshot' in inspector.get_table_names():
        op.drop_index('ix_proctoring_snapshot_snapshot_uuid', table_name='proctoring_snapshot')
        op.drop_index('ix_proctoring_snapshot_assignment_user', table_name='proctoring_snapshot')
        op.drop_table('proctoring_snapshot')

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'require_webcam_proctoring' in existing_columns:
            op.drop_column('assignment', 'require_webcam_proctoring')
