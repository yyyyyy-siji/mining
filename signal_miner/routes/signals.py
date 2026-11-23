"""Signal query routes."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 (required by Pydantic at runtime)

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from signal_miner.db import get_session_factory
from signal_miner.db.models import RawFeedbackRow, SignalRow, ThemeRow
from signal_miner.utils.url_templates import resolve_clickable_source_url

router = APIRouter()


class SignalSummary(BaseModel):
    id: str
    raw_feedback_id: str
    signal_type: str
    summary: str
    evidence: list[str]
    implicit_need: str | None
    # P13-1: deprecated legacy alias for model_self_score (uncalibrated)
    confidence: float = Field(
        ...,
        deprecated=True,
        description="DEPRECATED: legacy uncalibrated alias. Use model_self_score.",
    )
    extraction_model: str | None
    # P13-1: confidence trust baseline fields
    model_self_score: float | None = None
    calibrated_confidence: float | None = None
    confidence_method: str | None = None
    confidence_model_version: str | None = None
    evidence_validation_status: str | None = None
    external_url: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    created_at: datetime | None


@router.get(
    "/signals",
    response_model=list[SignalSummary],
    summary="List extracted signals",
    description="P13-1: ``min_confidence`` is deprecated; use ``min_model_self_score`` for filtering (uncalibrated, view-only).",
)
async def list_signals(
    signal_type: str | None = None,
    min_confidence: float = Query(
        0.0,
        deprecated=True,
        description="DEPRECATED: use min_model_self_score instead (uncalibrated, view-only).",
    ),
    profile: str | None = None,
    version_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
    min_model_self_score: float | None = None,  # P13-1: preferred filter param
) -> list[SignalSummary]:
    """Query extracted signals with optional filters.

    Phase 7: ``profile`` joins through ``RawFeedbackRow.pipeline_profile``
    so that callers can scope the result to a specific mining mode.
    When omitted, all profiles are returned.

    P13-1: ``min_confidence`` is deprecated (uncalibrated value).
    Use ``min_model_self_score`` instead for view-only filtering.
    """
    # Resolve filter value: prefer min_model_self_score, fall back to legacy min_confidence
    effective_min_score = min_model_self_score if min_model_self_score is not None else min_confidence

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(SignalRow).order_by(SignalRow.confidence.desc())

        if signal_type:
            stmt = stmt.where(SignalRow.signal_type == signal_type)
        if effective_min_score > 0:
            # P13-1: filter against model_self_score (preferred) or legacy confidence
            stmt = stmt.where(SignalRow.model_self_score >= effective_min_score)
        if version_id and version_id != "all":
            stmt = stmt.where(SignalRow.version_id == version_id)
        if profile:
            stmt = stmt.join(
                RawFeedbackRow, RawFeedbackRow.id == SignalRow.raw_feedback_id
            ).where(RawFeedbackRow.pipeline_profile == profile)

        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        summaries = []
        for r in rows:
            # Look up parent feedback for source URL
            rfb = await session.get(RawFeedbackRow, r.raw_feedback_id) if r.raw_feedback_id else None
            source_url = None
            fb_source_type = None
            fb_external_url = None
            if rfb:
                fb_source_type = rfb.source_type
                fb_external_url = rfb.external_url
                source_url = resolve_clickable_source_url(
                    source_type=rfb.source_type,
                    external_id=rfb.external_id,
                    external_url=rfb.external_url,
                    context=rfb.context if isinstance(rfb.context, dict) else {},
                    source_id=rfb.source_id,
                )
            summaries.append(SignalSummary(
                id=r.id,
                raw_feedback_id=r.raw_feedback_id,
                signal_type=r.signal_type,
                summary=r.summary,
                evidence=r.evidence or [],
                implicit_need=r.implicit_need,
                confidence=r.confidence,
                extraction_model=r.extraction_model,
                model_self_score=r.model_self_score,
                calibrated_confidence=r.calibrated_confidence,
                confidence_method=r.confidence_method,
                confidence_model_version=r.confidence_model_version,
                evidence_validation_status=r.evidence_validation_status,
                external_url=fb_external_url,
                source_url=source_url,
                source_type=fb_source_type,
                created_at=r.created_at,
            ))
        return summaries


@router.get(
    "/signals/{signal_id}",
    summary="Get signal details",
)
async def get_signal(signal_id: str) -> dict:
    """Get full details of an extracted signal."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = await session.get(SignalRow, signal_id)
        if not row:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

        return {
            "id": row.id,
            "raw_feedback_id": row.raw_feedback_id,
            "signal_type": row.signal_type,
            "summary": row.summary,
            "evidence": row.evidence,
            "implicit_need": row.implicit_need,
            "confidence": row.confidence,
            # P13-1: confidence trust baseline fields
            "model_self_score": row.model_self_score,
            "calibrated_confidence": row.calibrated_confidence,
            "confidence_method": row.confidence_method,
            "confidence_model_version": row.confidence_model_version,
            "evidence_validation_status": row.evidence_validation_status,
            "extraction_model": row.extraction_model,
            "extraction_prompt_version": row.extraction_prompt_version,
            "processing_state": row.processing_state,
            "input_tokens": row.input_tokens,
            "output_tokens": row.output_tokens,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }


@router.get(
    "/signals/{signal_id}/themes",
    summary="Get themes linked to a signal",
)
async def get_signal_themes(signal_id: str) -> list[dict]:
    """Get all themes that contain this signal ID."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        sig = await session.get(SignalRow, signal_id)
        if not sig:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

        stmt = select(ThemeRow)
        result = await session.execute(stmt)
        themes = result.scalars().all()

        linked_themes = []
        for theme in themes:
            if theme.signal_ids and signal_id in theme.signal_ids:
                linked_themes.append({
                    "id": theme.id,
                    "name": theme.name,
                    "description": theme.description,
                    "signal_count": theme.signal_count,
                    "representative_quotes": theme.representative_quotes,
                    "status": theme.status,
                    "created_at": theme.created_at.isoformat() if theme.created_at else None,
                })

        return linked_themes
