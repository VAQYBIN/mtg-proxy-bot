"""add web auth fields

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-03-22 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # --- Изменения таблицы users ---

    # telegram_id: NOT NULL → nullable
    op.alter_column('users', 'telegram_id', nullable=True)

    # first_name: NOT NULL → nullable
    op.alter_column('users', 'first_name', nullable=True)

    # Новые поля для email-авторизации
    op.add_column('users', sa.Column('email', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=False,
                                     server_default=sa.text('false')))
    op.add_column('users', sa.Column('display_name', sa.String(128), nullable=True))

    op.create_unique_constraint('uq_users_email', 'users', ['email'])
    op.create_index('ix_users_email', 'users', ['email'])

    # --- Новая таблица email_verifications ---
    op.create_table(
        'email_verifications',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('code', sa.String(8), nullable=False),
        sa.Column('token', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_email_verifications_email', 'email_verifications', ['email'])
    op.create_unique_constraint(
        'uq_email_verifications_token', 'email_verifications', ['token']
    )
    op.create_index(
        'ix_email_verifications_token', 'email_verifications', ['token']
    )
    op.create_index(
        'ix_email_verifications_user_id', 'email_verifications', ['user_id']
    )

    # --- Новая таблица account_link_tokens ---
    op.create_table(
        'account_link_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(16), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_account_link_tokens_user_id', 'account_link_tokens', ['user_id'])
    op.create_unique_constraint(
        'uq_account_link_tokens_code', 'account_link_tokens', ['code']
    )
    op.create_index('ix_account_link_tokens_code', 'account_link_tokens', ['code'])


def downgrade() -> None:
    """Downgrade schema."""
    # Удаляем account_link_tokens
    op.drop_index('ix_account_link_tokens_code', table_name='account_link_tokens')
    op.drop_constraint('uq_account_link_tokens_code', 'account_link_tokens',
                       type_='unique')
    op.drop_index('ix_account_link_tokens_user_id', table_name='account_link_tokens')
    op.drop_table('account_link_tokens')

    # Удаляем email_verifications
    op.drop_index('ix_email_verifications_user_id', table_name='email_verifications')
    op.drop_index('ix_email_verifications_token', table_name='email_verifications')
    op.drop_constraint('uq_email_verifications_token', 'email_verifications',
                       type_='unique')
    op.drop_index('ix_email_verifications_email', table_name='email_verifications')
    op.drop_table('email_verifications')

    # Откатываем изменения users
    op.drop_index('ix_users_email', table_name='users')
    op.drop_constraint('uq_users_email', 'users', type_='unique')
    op.drop_column('users', 'display_name')
    op.drop_column('users', 'email_verified')
    op.drop_column('users', 'email')
    op.alter_column('users', 'first_name', nullable=False)
    op.alter_column('users', 'telegram_id', nullable=False)
