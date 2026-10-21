"""Allow chat sessions without authenticated users."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c2e4f6a8b0d1"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "chat_sessions",
        "user_id",
        existing_type=sa.String(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO users (id, email, is_google_login, is_admin, created_at)
        SELECT 'anonymous', 'anonymous@local.invalid', false, false, now()
        WHERE EXISTS (SELECT 1 FROM chat_sessions WHERE user_id IS NULL)
          AND NOT EXISTS (SELECT 1 FROM users WHERE id = 'anonymous')
        """
    )
    op.execute(
        "UPDATE chat_sessions SET user_id = 'anonymous' WHERE user_id IS NULL"
    )
    op.alter_column(
        "chat_sessions",
        "user_id",
        existing_type=sa.String(),
        nullable=False,
    )
