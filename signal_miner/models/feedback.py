"""Pydantic models for the feedback ingestion and signal extraction domain.

Design references:
  - Quackback: packages/db/src/schema/feedback.ts (RawFeedback, Signal, Suggestion)
  - Cycle: Feedback → Quote → Request layered model
  - HyperOrbit: raw signal → theme → need → requirement chain
"""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 — required at runtime by Pydantic

from pydantic import BaseModel, Field

from signal_miner.models import (
    Confidence,
    ProcessingState,
    SignalType,
    UTCTimestamp,
    new_id,
)

# ---------------------------------------------------------------------------
# Supporting types
# ---------------------------------------------------------------------------

class FeedbackContent(BaseModel):
    """Normalized content payload of a raw feedback item."""

    subject: str | None = Field(None, description="Title, subject line, or ticket summary")
    text: str = Field(..., description="Main body text of the feedback")
    language: str | None = Field(None, description="ISO 639-1 language code if detected")


class FeedbackAuthor(BaseModel):
    """Author/submitter metadata (kept denormalized for source fidelity)."""

    name: str | None = None
    email: str | None = None
    external_id: str | None = None
    company: str | None = None
    segment: str | None = None  # e.g. "enterprise", "smb", "free"
    mrr: float | None = Field(None, description="Monthly recurring revenue for revenue-weighted scoring")


# ---------------------------------------------------------------------------
# Core entities
# ---------------------------------------------------------------------------

class RawFeedback(BaseModel):
    """Raw feedback item — unprocessed input from any data source.

    Design: mirrors Quackback's rawFeedbackItems table with idempotent
    deduplication via (source_id, dedupe_key).
    """

    id: str = Field(default_factory=lambda: new_id("rfb"))
    source_type: str = Field(..., description="csv, manual, github, slack, zendesk, ...")
    source_id: str = Field(..., description="Identifier of the source configuration")
    dedupe_key: str = Field(..., description="Idempotent dedup key within source")
    external_id: str | None = Field(None, description="Original ID in external system")
    external_url: str | None = Field(None, description="Link back to original item")
    author: FeedbackAuthor = Field(default_factory=FeedbackAuthor)
    content: FeedbackContent
    context: dict = Field(default_factory=dict, description="Arbitrary source-specific metadata")
    processing_state: ProcessingState = ProcessingState.PENDING
    attempt_count: int = 0
    last_error: str | None = None
    source_created_at: datetime | None = None
    processed_at: datetime | None = None
    created_at: UTCTimestamp
    updated_at: UTCTimestamp


class Signal(BaseModel):
    """Atomic signal — the smallest unit of product signal extracted from feedback.

    Design: mirrors Quackback's feedbackSignals table.  Each raw feedback
    item can yield up to MAX_SIGNALS_PER_FEEDBACK signals.
    """

    id: str = Field(default_factory=lambda: new_id("sig"))
    raw_feedback_id: str = Field(..., description="FK → RawFeedback.id")
    signal_type: SignalType
    summary: str = Field(..., description="Short neutral summary of the signal")
    evidence: list[str] = Field(default_factory=list, description="Direct quotes from source")
    implicit_need: str | None = Field(None, description="What the user actually needs")
    confidence: Confidence = 0.5

    # P13-1: Confidence trust baseline — structured semantics.
    model_self_score: float | None = Field(None, description="LLM raw self-assessment 0-1")
    calibrated_confidence: float | None = Field(None, description="Calibrated probability; always null until P13-2")
    confidence_method: str | None = Field(None, description="e.g. llm_self_reported")
    confidence_model_version: str | None = Field(None, description="provider/model/prompt tracking")
    evidence_validation_status: str | None = Field(None, description="verified/partial/invalid/not_checked")

    # Embedding (populated in Phase 2)
    embedding: list[float] | None = Field(None, exclude=True)
    embedding_model: str | None = None

    # Audit trail
    extraction_model: str | None = None
    extraction_prompt_version: str | None = None
    processing_state: ProcessingState = ProcessingState.PENDING
    input_tokens: int | None = None
    output_tokens: int | None = None

    created_at: UTCTimestamp
    updated_at: UTCTimestamp


# ---------------------------------------------------------------------------
# Pipeline state
# ---------------------------------------------------------------------------

class PipelineRun(BaseModel, frozen=True):
    """Immutable snapshot of a pipeline run's state.

    Design: mirrors agentic-prd-generation's PRDState — every mutation
    creates a new instance for clean SSE streaming.
    """

    run_id: str = Field(default_factory=lambda: new_id("run"))
    step: str = Field(..., description="Current pipeline step name")
    status: str = Field("running", description="running | completed | failed")
    progress: float = Field(0.0, ge=0.0, le=1.0, description="0.0–1.0 progress fraction")
    message: str = ""
    stats: dict = Field(default_factory=dict, description="Step-level statistics")
    error: str | None = None
    created_at: UTCTimestamp

    def to_event_payload(self) -> dict:
        """Serialize to SSE event payload."""
        return self.model_dump(
            mode="json",
            include={"run_id", "step", "status", "progress", "message", "stats", "error", "created_at"},
        )


# ---------------------------------------------------------------------------
# Extraction result (LLM response schema)
# ---------------------------------------------------------------------------

class ExtractedSignal(BaseModel):
    """Schema for a single signal within the LLM extraction response."""

    signalType: str = Field(..., description="One of the SignalType enum values")
    summary: str
    evidence: list[str] = Field(default_factory=list)
    implicitNeed: str | None = None
    confidence: float = 0.5
    # P13-1: evidence validation status is set programmatically after extraction
    # based on deterministic matching of evidence quotes against source text.
    # It is NOT provided by the LLM.
    evidence_validation_status: str = "not_checked"


class ExtractionResult(BaseModel):
    """Schema for the complete LLM extraction response."""

    signals: list[ExtractedSignal] = Field(default_factory=list)
