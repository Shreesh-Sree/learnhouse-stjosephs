"""Add plagiarism check

Adds ``assignment.enable_plagiarism_check`` / ``plagiarism_similarity_threshold``,
and the ``plagiarism_match`` table backing in-house cross-submission
similarity checking.

Revision ID: 3ea5b61eaf0a
Revises: c2d3e4f5a6b7
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '3ea5b61eaf0a'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'enable_plagiarism_check' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column(
                    'enable_plagiarism_check', sa.Boolean(),
                    nullable=True, server_default=sa.false(),
                ),
            )
        if 'plagiarism_similarity_threshold' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column(
                    'plagiarism_similarity_threshold', sa.Integer(),
                    nullable=True, server_default='70',
                ),
            )

    if 'plagiarism_match' not in inspector.get_table_names():
        op.create_table(
            'plagiarism_match',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('match_uuid', sa.String(), nullable=False, server_default=''),
            sa.Column(
                'assignment_id', sa.Integer(),
                sa.ForeignKey('assignment.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'assignment_task_id', sa.Integer(),
                sa.ForeignKey('assignmenttask.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'user_a_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column(
                'user_b_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False,
            ),
            sa.Column('similarity_percent', sa.Integer(), nullable=False),
            sa.Column('creation_date', sa.String(), nullable=False, server_default=''),
            sa.UniqueConstraint(
                'assignment_task_id', 'user_a_id', 'user_b_id',
                name='uq_plagiarism_match_task_pair',
            ),
        )
        op.create_index(
            'ix_plagiarism_match_assignment_id', 'plagiarism_match', ['assignment_id'],
        )
        op.create_index(
            'ix_plagiarism_match_match_uuid', 'plagiarism_match', ['match_uuid'],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'plagiarism_match' in inspector.get_table_names():
        op.drop_index('ix_plagiarism_match_match_uuid', table_name='plagiarism_match')
        op.drop_index('ix_plagiarism_match_assignment_id', table_name='plagiarism_match')
        op.drop_table('plagiarism_match')

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        for col in ('plagiarism_similarity_threshold', 'enable_plagiarism_check'):
            if col in existing_columns:
                op.drop_column('assignment', col)
