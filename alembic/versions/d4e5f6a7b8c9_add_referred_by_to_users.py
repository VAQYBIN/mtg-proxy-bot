"""add referred_by to users

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-03-20 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'users',
        sa.Column('referred_by_id', sa.Integer(), nullable=True),
    )
    op.create_index(
        'ix_users_referred_by_id', 'users', ['referred_by_id']
    )
    op.create_foreign_key(
        'fk_users_referred_by_id',
        'users', 'users',
        ['referred_by_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_users_referred_by_id', 'users', type_='foreignkey')
    op.drop_index('ix_users_referred_by_id', table_name='users')
    op.drop_column('users', 'referred_by_id')
