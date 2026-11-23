"""Add pgvector support for PostgreSQL backend.

Revision ID: 4e8f1a2b3c0d
Revises: 3fa2b1c8e0d5
Create Date: 2026-05-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e8f1a2b3c0d'
down_revision: Union[str, Sequence[str], None] = '3fa2b1c8e0d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema — enable pgvector on PostgreSQL."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
        op.execute(
            "ALTER TABLE feedback_signals "
            "ALTER COLUMN embedding TYPE vector(1536) "
            "USING embedding::vector(1536)"
        )


def downgrade() -> None:
    """Downgrade schema — revert embedding to JSON."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE feedback_signals "
            "ALTER COLUMN embedding TYPE json "
            "USING embedding::text::json"
        )
