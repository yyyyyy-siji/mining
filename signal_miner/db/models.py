"""SQLAlchemy ORM models for the SignalMiner database.

Schema design references:
  - Quackback: packages/db/src/schema/feedback.ts
  - Cycle: Feedback → Quote → Request layered model
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — required at runtime by SQLAlchemy Mapped[]

from sqlalchemy import JSON, DateTime, Float, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Conditional pgvector support
try:
    from pgvector.sqlalchemy import Vector  # noqa: F401

    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


def _embedding_column():
    """Return the appropriate column type for embeddings."""
    if HAS_PGVECTOR:
        return mapped_column(Vector(1536), nullable=True)
    return mapped_column(JSON)


class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


DEFAULT_VERSION_ID = "default"


class DatasetVersionRow(Base):
    """Dataset version / batch container isolating imports and downstream assets."""

    __tablename__ = "dataset_versions"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RawFeedbackRow(Base):
    """Raw feedback items table — mirrors Quackback's raw_feedback_items."""

    __tablename__ = "raw_feedback_items"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(200), nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text)
    external_url: Mapped[str | None] = mapped_column(Text)
    author: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    processing_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    source_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    extraction_input_tokens: Mapped[int | None] = mapped_column(Integer)
    extraction_output_tokens: Mapped[int | None] = mapped_column(Integer)
    # Phase 7: which mining profile this row belongs to. Defaults to
    # "product_feedback" so existing data is unaffected after migration.
    pipeline_profile: Mapped[str] = mapped_column(
        String(40), nullable=False, default="product_feedback", index=True
    )
    version_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DEFAULT_VERSION_ID, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("raw_feedback_dedupe_idx", "version_id", "source_id", "dedupe_key", unique=True),
        Index("raw_feedback_created_idx", "created_at"),
    )


class SignalRow(Base):
    """Feedback signals table — mirrors Quackback's feedback_signals."""

    __tablename__ = "feedback_signals"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    raw_feedback_id: Mapped[str] = mapped_column(
        String(40), nullable=False, index=True
    )
    signal_type: Mapped[str] = mapped_column(String(30), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    implicit_need: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    # P13-1: Confidence trust baseline — structured semantics for honest display.
    # ``confidence`` is preserved as legacy float for backward compatibility.
    model_self_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    calibrated_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    confidence_method: Mapped[str | None] = mapped_column(String(60), nullable=True)
    confidence_model_version: Mapped[str | None] = mapped_column(String(200), nullable=True)
    evidence_validation_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    embedding: Mapped[list | None] = _embedding_column()
    embedding_model: Mapped[str | None] = mapped_column(String(100))
    extraction_model: Mapped[str | None] = mapped_column(String(100))
    extraction_prompt_version: Mapped[str | None] = mapped_column(String(20))
    processing_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", index=True
    )
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    version_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DEFAULT_VERSION_ID, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ThemeRow(Base):
    """Themes table — semantic clusters of signals."""

    __tablename__ = "themes"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    signal_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    signal_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    representative_quotes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # Phase 7: which mining profile produced this theme.
    pipeline_profile: Mapped[str] = mapped_column(
        String(40), nullable=False, default="product_feedback", index=True
    )
    version_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DEFAULT_VERSION_ID, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class PainPointRow(Base):
    """Pain points table."""

    __tablename__ = "pain_points"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    theme_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    user_segment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="occasional")
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    business_impact: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_signal_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    evidence_quotes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    version_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DEFAULT_VERSION_ID, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class OpportunityRow(Base):
    """Opportunity cards table."""

    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    pain_point_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    jtbd_statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    supporting_evidence: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    assumptions: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    priority: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    version_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DEFAULT_VERSION_ID, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class RequirementAssetRow(Base):
    """Requirement assets table."""

    __tablename__ = "requirement_assets"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    opportunity_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    user_stories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    acceptance_criteria: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    impact: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    priority: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    decision_reasoning: Mapped[str] = mapped_column(Text, nullable=False, default="")
    evidence_trail: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    prd_content: Mapped[str | None] = mapped_column(Text, nullable=True, comment="LLM生成的Markdown格式PRD内容")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    version_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DEFAULT_VERSION_ID, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class AuditLogRow(Base):
    """Pipeline audit log — every AI action is recorded."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    pipeline_step: Mapped[str | None] = mapped_column(String(40))
    raw_feedback_id: Mapped[str | None] = mapped_column(String(40), index=True)
    signal_id: Mapped[str | None] = mapped_column(String(40))
    model: Mapped[str | None] = mapped_column(String(100))
    prompt_version: Mapped[str | None] = mapped_column(String(20))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PipelineRunRow(Base):
    """Pipeline run history — tracks every pipeline execution."""

    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    feedback_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    stats: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    # Phase 7: which profile this run was executed under.
    pipeline_profile: Mapped[str] = mapped_column(
        String(40), nullable=False, default="product_feedback", index=True
    )
    version_id: Mapped[str] = mapped_column(
        String(40), nullable=False, default=DEFAULT_VERSION_ID, index=True
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
