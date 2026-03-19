"""add proxy_settings table

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-19 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'proxy_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('max_devices', sa.Integer(), nullable=True),
        sa.Column('traffic_limit_gb', sa.Double(), nullable=True),
        sa.Column('expires_days', sa.Integer(), nullable=True),
        sa.Column('traffic_reset_interval', sa.String(length=16), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.execute("INSERT INTO proxy_settings (id) VALUES (1)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('proxy_settings')
