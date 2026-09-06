"""Add scorm_tracking_data table

Adds the scorm_tracking_data table backing the SCORM 1.2 player's cmi.core
tracking: one row per (activity, user) holding lesson_status, score, resume
location/suspend_data, and accumulated time.

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-09-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'a4b5c6d7e8f9'
down_revision: Union[str, None] = 'f3a4b5c6d7e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'scorm_tracking_data' in inspector.get_table_names():
        return

    op.create_table(
        'scorm_tracking_data',
        sa.Column('id', sa.Integer(), primary_key=True),
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
            'user_id', sa.Integer(),
            sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
        ),
        sa.Column('lesson_status', sa.String(length=32), nullable=False, server_default='not_attempted'),
        sa.Column('score_raw', sa.Float(), nullable=True),
        sa.Column('score_min', sa.Float(), nullable=True),
        sa.Column('score_max', sa.Float(), nullable=True),
        sa.Column('lesson_location', sa.String(), nullable=True),
        sa.Column('suspend_data', sa.Text(), nullable=True),
        sa.Column('session_time_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_time_seconds', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('creation_date', sa.String(), nullable=False, server_default=''),
        sa.Column('update_date', sa.String(), nullable=False, server_default=''),
        sa.UniqueConstraint('activity_id', 'user_id', name='uq_scorm_tracking_activity_user'),
    )
    op.create_index('ix_scorm_tracking_activity_id', 'scorm_tracking_data', ['activity_id'])
    op.create_index('ix_scorm_tracking_user_id', 'scorm_tracking_data', ['user_id'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'scorm_tracking_data' not in inspector.get_table_names():
        return

    op.drop_index('ix_scorm_tracking_user_id', table_name='scorm_tracking_data')
    op.drop_index('ix_scorm_tracking_activity_id', table_name='scorm_tracking_data')
    op.drop_table('scorm_tracking_data')
