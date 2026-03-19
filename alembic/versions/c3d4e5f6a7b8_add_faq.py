"""add faq

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-03-20 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'proxy_settings',
        sa.Column(
            'faq_enabled',
            sa.Boolean(),
            nullable=False,
            server_default='false',
        ),
    )
    op.create_table(
        'faq_items',
        sa.Column('id', sa.Integer(), nullable=False, autoincrement=True),
        sa.Column('question', sa.String(length=512), nullable=False),
        sa.Column('answer', sa.Text(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('faq_items')
    op.drop_column('proxy_settings', 'faq_enabled')
