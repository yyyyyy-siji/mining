"""add_pipeline_profile_indexes

Revision ID: 3c2d6afdc851
Revises: 7a1c2d3e4f56
Create Date: 2026-06-03 16:05:25.456644

Adds indexes on ``themes.pipeline_profile`` and
``pipeline_runs.pipeline_profile`` so that lookups by profile
are fast even as data grows (complements the index already on
``raw_feedback_items.pipeline_profile`` from migration 7a1c2d3e4f56).
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '3c2d6afdc851'
down_revision: Union[str, Sequence[str], None] = '7a1c2d3e4f56'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create indexes on themes and pipeline_runs pipeline_profile columns."""
    op.create_index(
        "ix_themes_pipeline_profile",
        "themes",
        ["pipeline_profile"],
    )
    op.create_index(
        "ix_pipeline_runs_pipeline_profile",
        "pipeline_runs",
        ["pipeline_profile"],
    )


def downgrade() -> None:
    """Drop the indexes created in this migration."""
    op.drop_index("ix_themes_pipeline_profile", table_name="themes")
    op.drop_index("ix_pipeline_runs_pipeline_profile", table_name="pipeline_runs")
