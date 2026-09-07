"""Add discussion/comment anonymity

Adds ``discussion.is_anonymous`` and ``discussioncomment.is_anonymous``
(both nullable bool, default false) backing anonymous-to-classmates,
identified-to-instructors discussion posting.

Revision ID: 3ecefad8feb9
Revises: 8773210bebc1
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = '3ecefad8feb9'
down_revision: Union[str, None] = '8773210bebc1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in ('discussion', 'discussioncomment'):
        if table_name in inspector.get_table_names():
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
            if 'is_anonymous' not in existing_columns:
                op.add_column(
                    table_name,
                    sa.Column(
                        'is_anonymous', sa.Boolean(),
                        nullable=True, server_default=sa.false(),
                    ),
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    for table_name in ('discussion', 'discussioncomment'):
        if table_name in inspector.get_table_names():
            existing_columns = {col['name'] for col in inspector.get_columns(table_name)}
            if 'is_anonymous' in existing_columns:
                op.drop_column(table_name, 'is_anonymous')
