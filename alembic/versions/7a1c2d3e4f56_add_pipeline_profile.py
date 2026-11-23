"""add pipeline_profile column to feedback / themes / runs

Revision ID: 7a1c2d3e4f56
Revises: 4e8f1a2b3c0d
Create Date: 2026-06-02 22:00:00.000000

Phase 7 — PipelineProfile refactor: each row carries the name of the
profile that produced it (default 'product_feedback'). Existing rows
are back-filled with the default by the database; this migration adds
the column and the supporting index without rewriting data.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7a1c2d3e4f56'
down_revision: Union[str, Sequence[str], None] = '4e8f1a2b3c0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add pipeline_profile column to three tables.

    Uses ``batch_alter_table`` for SQLite compatibility (which does not
    support ``ALTER TABLE ... ADD CONSTRAINT`` directly). Each column
    defaults to 'product_feedback' so existing rows auto-back-fill.
    """
    # --- raw_feedback_items ---
    with op.batch_alter_table('raw_feedback_items') as batch_op:
        batch_op.add_column(
            sa.Column(
                'pipeline_profile',
                sa.String(length=40),
                nullable=False,
                server_default='product_feedback',
            )
        )
        batch_op.create_index(
            'ix_raw_feedback_items_pipeline_profile',
            ['pipeline_profile'],
            unique=False,
        )

    # --- themes ---
    with op.batch_alter_table('themes') as batch_op:
        batch_op.add_column(
            sa.Column(
                'pipeline_profile',
                sa.String(length=40),
                nullable=False,
                server_default='product_feedback',
            )
        )

    # --- pipeline_runs ---
    with op.batch_alter_table('pipeline_runs') as batch_op:
        batch_op.add_column(
            sa.Column(
                'pipeline_profile',
                sa.String(length=40),
                nullable=False,
                server_default='product_feedback',
            )
        )


def downgrade() -> None:
    """Reverse the column additions."""
    with op.batch_alter_table('pipeline_runs') as batch_op:
        batch_op.drop_column('pipeline_profile')

    with op.batch_alter_table('themes') as batch_op:
        batch_op.drop_column('pipeline_profile')

    with op.batch_alter_table('raw_feedback_items') as batch_op:
        batch_op.drop_index('ix_raw_feedback_items_pipeline_profile')
        batch_op.drop_column('pipeline_profile')
