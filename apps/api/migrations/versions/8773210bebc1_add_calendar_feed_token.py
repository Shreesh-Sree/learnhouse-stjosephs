"""Add calendar feed token

Adds the ``calendarfeedtoken`` table backing a per-user, opaque-secret ICS
feed of assignment due dates.

Revision ID: 8773210bebc1
Revises: 3ea5b61eaf0a
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '8773210bebc1'
down_revision: Union[str, None] = '3ea5b61eaf0a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'calendarfeedtoken' not in inspector.get_table_names():
        op.create_table(
            'calendarfeedtoken',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('token', sa.String(), nullable=False, server_default=''),
            sa.Column(
                'user_id', sa.Integer(),
                sa.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, unique=True,
            ),
            sa.Column('creation_date', sa.String(), nullable=False, server_default=''),
        )
        op.create_index('ix_calendarfeedtoken_token', 'calendarfeedtoken', ['token'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'calendarfeedtoken' in inspector.get_table_names():
        op.drop_index('ix_calendarfeedtoken_token', table_name='calendarfeedtoken')
        op.drop_table('calendarfeedtoken')
