"""Add is_admin column and migrate to timezone-aware datetimes

Revision ID: a1b2c3d4e5f6
Revises: 0148268d651c
Create Date: 2026-08-08 00:00:00.000000

Changes:
  - users.is_admin (Boolean, default=False, NOT NULL)
  - Migrate all DateTime columns to TIMESTAMPTZ (timezone-aware)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '0148268d651c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Add is_admin column to users ──────────────────────────────────────
    op.add_column(
        'users',
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='false')
    )

    # ── 2. Migrate DateTime → TIMESTAMPTZ on users ───────────────────────────
    op.alter_column(
        'users', 'created_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using='created_at AT TIME ZONE \'UTC\''
    )

    # ── 3. Migrate DateTime → TIMESTAMPTZ on chat_sessions ───────────────────
    op.alter_column(
        'chat_sessions', 'created_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using='created_at AT TIME ZONE \'UTC\''
    )
    op.alter_column(
        'chat_sessions', 'updated_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using='updated_at AT TIME ZONE \'UTC\''
    )

    # ── 4. Migrate DateTime → TIMESTAMPTZ on chat_messages ───────────────────
    op.alter_column(
        'chat_messages', 'created_at',
        type_=sa.DateTime(timezone=True),
        existing_type=sa.DateTime(),
        existing_nullable=True,
        postgresql_using='created_at AT TIME ZONE \'UTC\''
    )


def downgrade() -> None:
    # Revert chat_messages
    op.alter_column(
        'chat_messages', 'created_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )

    # Revert chat_sessions
    op.alter_column(
        'chat_sessions', 'updated_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )
    op.alter_column(
        'chat_sessions', 'created_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )

    # Revert users
    op.alter_column(
        'users', 'created_at',
        type_=sa.DateTime(),
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=True,
    )

    # Drop is_admin column
    op.drop_column('users', 'is_admin')
