"""Add peer review

Adds ``assignment.enable_peer_review`` / ``peer_reviews_per_submission``,
and the ``peer_review`` table backing student-to-student review assignment
and tracking.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'f9a0b1c2d3e4'
down_revision: Union[str, None] = 'e8f9a0b1c2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'enable_peer_review' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column(
                    'enable_peer_review', sa.Boolean(),
                    nullable=True, server_default=sa.false(),
                ),
            )
        if 'peer_reviews_per_submission' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column(
                    'peer_reviews_per_submission', sa.Integer(),
                    nullable=True, server_default='2',
                ),
            )

    if 'peer_review' not in inspector.get_table_names():
        op.create_table(
            'peer_review',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('review_uuid', sa.String(), nullable=False, server_default=''),
            sa.Column(
                'assignment_id', sa.Integer(),
                sa.ForeignKey('assignment.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'reviewer_user_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'target_user_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column('score', sa.Integer(), nullable=True),
            sa.Column('feedback', sa.Text(), nullable=True),
            sa.Column('status', sa.String(), nullable=False, server_default='PENDING'),
            sa.Column('creation_date', sa.String(), nullable=False, server_default=''),
            sa.Column('update_date', sa.String(), nullable=False, server_default=''),
            sa.Column('submitted_at', sa.String(), nullable=True),
            sa.UniqueConstraint(
                'assignment_id', 'reviewer_user_id', 'target_user_id',
                name='uq_peer_review_reviewer_target',
            ),
        )
        op.create_index(
            'ix_peer_review_assignment_target', 'peer_review', ['assignment_id', 'target_user_id'],
        )
        op.create_index(
            'ix_peer_review_assignment_reviewer', 'peer_review', ['assignment_id', 'reviewer_user_id'],
        )
        op.create_index('ix_peer_review_review_uuid', 'peer_review', ['review_uuid'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'peer_review' in inspector.get_table_names():
        op.drop_index('ix_peer_review_review_uuid', table_name='peer_review')
        op.drop_index('ix_peer_review_assignment_reviewer', table_name='peer_review')
        op.drop_index('ix_peer_review_assignment_target', table_name='peer_review')
        op.drop_table('peer_review')

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        for col in ('peer_reviews_per_submission', 'enable_peer_review'):
            if col in existing_columns:
                op.drop_column('assignment', col)
