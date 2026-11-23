"""p13_1_confidence_baseline

Revision ID: a1b2c3d4e5f6
Revises: 3c2d6afdc851
Create Date: 2026-07-10 10:30:00.000000

P13-1: Adds confidence trust-baseline columns to ``feedback_signals``.

New columns (all nullable so existing rows are unaffected):
  - ``model_self_score``: LLM raw self-assessment, 0-1.
  - ``calibrated_confidence``: calibrated probability (always NULL at this stage).
  - ``confidence_method``: how the score was produced (e.g. ``llm_self_reported``).
  - ``confidence_model_version``: provider/model/prompt tracking string.
  - ``evidence_validation_status``: verified / partial / invalid / not_checked.

The legacy ``confidence`` column is NOT modified — existing values are
preserved as-is for backward compatibility.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '3c2d6afdc851'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add P13-1 confidence trust-baseline columns to feedback_signals."""
    op.add_column('feedback_signals', sa.Column('model_self_score', sa.Float(), nullable=True))
    op.add_column('feedback_signals', sa.Column('calibrated_confidence', sa.Float(), nullable=True))
    op.add_column('feedback_signals', sa.Column('confidence_method', sa.String(60), nullable=True))
    op.add_column('feedback_signals', sa.Column('confidence_model_version', sa.String(200), nullable=True))
    op.add_column('feedback_signals', sa.Column('evidence_validation_status', sa.String(20), nullable=True))


def downgrade() -> None:
    """Remove P13-1 confidence trust-baseline columns."""
    op.drop_column('feedback_signals', 'evidence_validation_status')
    op.drop_column('feedback_signals', 'confidence_model_version')
    op.drop_column('feedback_signals', 'confidence_method')
    op.drop_column('feedback_signals', 'calibrated_confidence')
    op.drop_column('feedback_signals', 'model_self_score')
