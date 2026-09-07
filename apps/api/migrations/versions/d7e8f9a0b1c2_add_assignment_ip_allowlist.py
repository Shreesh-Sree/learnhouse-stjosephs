"""Add assignment IP allowlist fields

Adds ``assignment.require_ip_allowlist`` (nullable bool, default false) and
``assignment.ip_allowlist`` (nullable text: newline/comma-separated IPs and
CIDR ranges), backing campus-network-restricted assignment submission.

Revision ID: d7e8f9a0b1c2
Revises: c6d7e8f9a0b1
Create Date: 2026-09-07

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401


# revision identifiers, used by Alembic.
revision: str = 'd7e8f9a0b1c2'
down_revision: Union[str, None] = 'c6d7e8f9a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'require_ip_allowlist' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column(
                    'require_ip_allowlist', sa.Boolean(),
                    nullable=True, server_default=sa.false(),
                ),
            )
        if 'ip_allowlist' not in existing_columns:
            op.add_column(
                'assignment',
                sa.Column('ip_allowlist', sa.Text(), nullable=True),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if 'assignment' in inspector.get_table_names():
        existing_columns = {col['name'] for col in inspector.get_columns('assignment')}
        if 'ip_allowlist' in existing_columns:
            op.drop_column('assignment', 'ip_allowlist')
        if 'require_ip_allowlist' in existing_columns:
            op.drop_column('assignment', 'require_ip_allowlist')
