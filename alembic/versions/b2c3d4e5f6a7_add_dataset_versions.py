"""add_dataset_versions

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-11-24 10:00:00.000000

Adds the ``dataset_versions`` table and ``version_id`` isolation columns
to all 7 pipeline/asset tables, upgrading ``raw_feedback_dedupe_idx`` to
``(version_id, source_id, dedupe_key)``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VERSIONED_TABLES = (
    "raw_feedback_items",
    "feedback_signals",
    "themes",
    "pain_points",
    "opportunities",
    "requirement_assets",
    "pipeline_runs",
)


def upgrade() -> None:
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.String(length=40), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    for table in _VERSIONED_TABLES:
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(
                sa.Column("version_id", sa.String(length=40), nullable=False, server_default="default")
            )
            batch_op.create_index(f"ix_{table}_version_id", ["version_id"])

    with op.batch_alter_table("raw_feedback_items") as batch_op:
        batch_op.drop_index("raw_feedback_dedupe_idx")
        batch_op.create_index(
            "raw_feedback_dedupe_idx",
            ["version_id", "source_id", "dedupe_key"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("raw_feedback_items") as batch_op:
        batch_op.drop_index("raw_feedback_dedupe_idx")
        batch_op.create_index(
            "raw_feedback_dedupe_idx",
            ["source_id", "dedupe_key"],
            unique=True,
        )

    for table in reversed(_VERSIONED_TABLES):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_index(f"ix_{table}_version_id")
            batch_op.drop_column("version_id")

    op.drop_table("dataset_versions")
