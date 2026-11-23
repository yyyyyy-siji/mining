"""Feedback ingestion and query routes."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003 (required by Pydantic at runtime)
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select

from signal_miner.db import get_session_factory
from signal_miner.db.models import RawFeedbackRow, SignalRow
from signal_miner.utils.source_evidence import (
    build_source_evidence,
    export_source_snapshot,
    redact_credentials,
    source_dedupe_key,
    utc_iso,
    verify_source_snapshot,
)
from signal_miner.utils.source_platforms import (
    SourceUrlValidationError,
    validate_required_source_url,
)
from signal_miner.utils.url_templates import resolve_clickable_source_url

router = APIRouter()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prepare_ingest_data(request: IngestRequest) -> dict:
    """Build validated runner payload from an API ingest request."""
    source_id = f"{request.source_type}_api"
    resolved_url = request.external_url
    if not resolved_url and request.video_url:
        resolved_url = request.video_url

    try:
        validated_url = validate_required_source_url(
            request.source_type,
            resolved_url,
            source_id=source_id,
            capture_method=request.capture_method,
        )
        for parent_url in (request.parent_url, request.parent_comment_url):
            if parent_url:
                validate_required_source_url(
                    request.source_type, parent_url, source_id=source_id,
                    capture_method=request.capture_method,
                )
    except SourceUrlValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # P12-2: browser_screenshot must provide screenshot_path or source_note
    if request.capture_method == "browser_screenshot" and not request.screenshot_path and not request.source_note:
        raise HTTPException(
            status_code=422,
            detail="capture_method=browser_screenshot 时必须提供 screenshot_path 或 source_note，否则无法追溯。",
        )

    context: dict = {
        "capture_method": request.capture_method,
        "source_url_required": True,
        "source_url_validation": "format_and_platform_domain",
        "source_platform": request.source_type,
    }
    if request.pipeline_profile == "product_feedback" and request.content_nature in {"api_excerpt", "curated_comment"}:
        raise HTTPException(status_code=422, detail="API摘要/精选评论只能作为检索线索；请取得并补充原文后再导入机会材料。")
    for key in (
        "entity_type", "parent_id", "parent_url", "parent_comment_id", "parent_comment_url",
        "locator_level", "content_nature", "coverage_scope", "capture_version", "text_origin",
    ):
        value = getattr(request, key)
        if value is not None:
            context[key] = value
    if request.entity_type == "comment" and request.parent_url == validated_url:
        context["locator_level"] = "parent_page"
    if request.source_updated_at is not None:
        context["source_updated_at"] = utc_iso(request.source_updated_at)
    if request.source_note is not None:
        context["source_note"] = request.source_note
    if request.video_url is not None:
        context["video_url"] = request.video_url
    if request.views is not None:
        context["views"] = request.views
    if request.likes is not None:
        context["likes"] = request.likes
    if request.platform is not None:
        context["platform"] = request.platform
    if request.screenshot_path is not None:
        context["screenshot_path"] = request.screenshot_path
    if request.ocr_text is not None:
        context["ocr_text"] = request.ocr_text
    if request.source_captured_at is not None:
        context["source_captured_at"] = utc_iso(request.source_captured_at)
    if request.raw_payload is not None:
        context["raw_payload"] = redact_credentials(request.raw_payload)

    content = {"subject": request.subject, "text": request.text}
    author = {
        "name": request.author_name, "email": request.author_email,
        "company": request.company, "segment": request.segment,
    }
    context["source_evidence"] = build_source_evidence(
        source_type=request.source_type, external_id=request.external_id,
        external_url=validated_url, source_created_at=request.source_created_at,
        content=content, context=context, author=author,
    )

    return {
        "source_type": request.source_type,
        "source_id": source_id,
        "dedupe_key": source_dedupe_key(
            pipeline_profile=request.pipeline_profile, package=context["source_evidence"], content=content,
        ),
        "external_id": request.external_id,
        "external_url": validated_url,
        "source_created_at": request.source_created_at,
        "author": author,
        "content": content,
        "context": context,
    }


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class IngestRequest(BaseModel):
    """Request body for single feedback ingestion."""
    source_type: str = Field("manual", description="Source type identifier")
    subject: str | None = Field(None, description="Subject/title")
    text: str = Field(..., description="Feedback text content", min_length=1)
    author_name: str | None = None
    author_email: str | None = None
    company: str | None = None
    segment: str | None = None
    external_url: str | None = Field(None, description="Required direct URL to the original source")
    external_id: str | None = Field(None, max_length=300)
    entity_type: Literal["post", "comment", "answer", "article", "video", "unknown"] = "unknown"
    parent_id: str | None = None
    parent_url: str | None = None
    parent_comment_id: str | None = None
    parent_comment_url: str | None = None
    locator_level: Literal["item", "parent_page", "unknown"] = "unknown"
    content_nature: Literal["original_text", "api_excerpt", "curated_comment", "ocr_text", "manual_text", "unknown"] = "manual_text"
    text_origin: Literal["body", "title", "user_provided", "ocr", "unknown"] = "user_provided"
    coverage_scope: str | None = None
    capture_version: str | None = None
    source_created_at: datetime | None = None
    source_updated_at: datetime | None = None
    capture_method: str = Field(
        "manual_browser",
        description=(
            "How this source item was acquired: official_api, crawler, "
            "browser_screenshot, manual_browser, or webhook"
        ),
    )
    source_note: str | None = Field(None, description="Optional provenance note for this source item")
    # P12-2: screenshot/OCR evidence fields for browser_screenshot capture method.
    screenshot_path: str | None = Field(None, description="Path to the screenshot file when capture_method=browser_screenshot")
    ocr_text: str | None = Field(None, description="OCR-extracted text from screenshot when capture_method=browser_screenshot")
    # P12-2 fix-4: evidence metadata fields.
    source_captured_at: datetime | None = Field(None, description="ISO-8601 timestamp when the source item was captured")
    raw_payload: dict | None = Field(None, description="Raw payload from the source adapter (original API response, etc.)")
    # Phase 7: tag the row with the active mining profile.
    pipeline_profile: str = Field(
        "product_feedback",
        description="Pipeline profile for this feedback. Use one of GET /api/v1/profiles.",
    )
    version_id: str = Field(
        "default",
        max_length=40,
        description="Dataset version ID isolating imports and downstream assets.",
    )
    # Phase 7: video-specific metadata (only consumed by aigc_video profile).
    video_url: str | None = Field(None, description="[aigc_video] Original video URL")
    views: int | None = Field(None, description="[aigc_video] View count")
    likes: int | None = Field(None, description="[aigc_video] Like count")
    platform: str | None = Field(
        None,
        description="[aigc_video] Source platform (bilibili / douyin / youtube / xiaohongshu)",
    )

    @field_validator("source_created_at", "source_updated_at", "source_captured_at")
    @classmethod
    def aware_source_time(cls, value):
        return datetime.fromisoformat(utc_iso(value)) if value is not None else None

    @model_validator(mode="before")
    @classmethod
    def reject_claimed_verification(cls, values):
        if isinstance(values, dict) and {"source_evidence", "snapshot_hash", "snapshot_verification", "verified", "verification_status"}.intersection(values):
            raise ValueError("来源快照与完整性状态由服务端计算，不能由调用方指定已核验。")
        return values


class IngestResponse(BaseModel):
    feedback_id: str
    is_duplicate: bool = False
    pipeline_profile: str = "product_feedback"
    version_id: str = "default"


class FeedbackSummary(BaseModel):
    id: str
    source_type: str
    subject: str | None
    text_preview: str
    processing_state: str
    signal_count: int = 0
    external_url: str | None = None
    source_url: str | None = None
    pipeline_profile: str = "product_feedback"
    version_id: str = "default"
    created_at: datetime


class BatchIngestResponse(BaseModel):
    total: int
    ingested: int
    duplicates: int
    feedback_ids: list[str]


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/feedback/ingest",
    response_model=IngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a single feedback item",
)
async def ingest_feedback(request: IngestRequest) -> IngestResponse:
    """Accept a single raw feedback item for processing."""
    from signal_miner.pipeline.runner import ingest_feedback as _ingest

    version_id = "default" if not request.version_id or request.version_id == "all" else request.version_id.strip()
    data = _prepare_ingest_data(request)
    feedback_id = await _ingest(data, pipeline_profile=request.pipeline_profile, version_id=version_id)
    return IngestResponse(
        feedback_id=feedback_id,
        pipeline_profile=request.pipeline_profile,
        version_id=version_id,
    )


@router.post(
    "/feedback/batch",
    response_model=BatchIngestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Batch ingest feedback items",
)
async def batch_ingest(
    items: list[IngestRequest],
    version_id: str | None = None,
) -> BatchIngestResponse:
    """Accept multiple feedback items for processing."""
    from signal_miner.pipeline.runner import ingest_feedback_with_result as _ingest

    prepared_items = []
    for idx, item in enumerate(items, 1):
        try:
            prepared_items.append(_prepare_ingest_data(item))
        except HTTPException as exc:
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"第 {idx} 条数据来源不合格：{exc.detail}",
            ) from exc

    feedback_ids = []
    duplicates = 0

    for item, data in zip(items, prepared_items, strict=True):
        effective_version = (
            version_id
            if version_id and version_id != "all"
            else ("default" if not item.version_id or item.version_id == "all" else item.version_id.strip())
        )
        result = await _ingest(
            data,
            pipeline_profile=item.pipeline_profile,
            version_id=effective_version,
        )
        feedback_ids.append(result.feedback_id)
        duplicates += int(not result.inserted)

    return BatchIngestResponse(
        total=len(items),
        ingested=len(items) - duplicates,
        duplicates=duplicates,
        feedback_ids=feedback_ids,
    )


@router.get(
    "/feedback",
    summary="List feedback items",
)
async def list_feedback(
    state: str | None = None,
    source_type: str | None = None,
    profile: str | None = None,
    version_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[FeedbackSummary]:
    """Query raw feedback items with optional filters.

    Phase 7: ``profile`` filters by ``pipeline_profile``. When omitted,
    all profiles are returned (preserves prior behaviour).
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(RawFeedbackRow).order_by(RawFeedbackRow.created_at.desc())

        if state:
            stmt = stmt.where(RawFeedbackRow.processing_state == state)
        if source_type:
            stmt = stmt.where(RawFeedbackRow.source_type == source_type)
        if profile:
            stmt = stmt.where(RawFeedbackRow.pipeline_profile == profile)
        if version_id and version_id != "all":
            stmt = stmt.where(RawFeedbackRow.version_id == version_id)

        stmt = stmt.limit(limit).offset(offset)
        result = await session.execute(stmt)
        rows = result.scalars().all()

        summaries = []
        for row in rows:
            content = row.content or {}
            sig_stmt = select(func.count()).where(SignalRow.raw_feedback_id == row.id)
            sig_count = (await session.execute(sig_stmt)).scalar() or 0

            summaries.append(FeedbackSummary(
                id=row.id,
                source_type=row.source_type,
                subject=content.get("subject"),
                text_preview=(content.get("text", ""))[:200],
                processing_state=row.processing_state,
                signal_count=sig_count,
                external_url=row.external_url,
                source_url=resolve_clickable_source_url(
                    source_type=row.source_type,
                    external_id=row.external_id,
                    external_url=row.external_url,
                    context=row.context if isinstance(row.context, dict) else {},
                    source_id=row.source_id,
                ),
                pipeline_profile=row.pipeline_profile or "product_feedback",
                version_id=row.version_id or "default",
                created_at=row.created_at,
            ))

        return summaries


@router.get(
    "/feedback/{feedback_id}",
    summary="Get feedback details",
)
async def get_feedback(feedback_id: str) -> dict:
    """Get full details of a feedback item including its extracted signals."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = await session.get(RawFeedbackRow, feedback_id)
        if not row:
            raise HTTPException(status_code=404, detail=f"Feedback {feedback_id} not found")

        sig_stmt = select(SignalRow).where(SignalRow.raw_feedback_id == feedback_id)
        sig_result = await session.execute(sig_stmt)
        signals = sig_result.scalars().all()

        return {
            "id": row.id,
            "source_type": row.source_type,
            "source_id": row.source_id,
            "version_id": row.version_id or "default",
            "external_id": row.external_id,
            "external_url": row.external_url,
            "author": row.author,
            "content": row.content,
            "context": redact_credentials(row.context),
            "processing_state": row.processing_state,
            "attempt_count": row.attempt_count,
            "last_error": row.last_error,
            "pipeline_profile": row.pipeline_profile or "product_feedback",
            "source_created_at": utc_iso(row.source_created_at, persisted=True),
            "source_evidence": redact_credentials((row.context or {}).get("source_evidence")),
            "snapshot_verification": verify_source_snapshot(row),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "processed_at": row.processed_at.isoformat() if row.processed_at else None,
            "signals": [
                {
                    "id": s.id,
                    "signal_type": s.signal_type,
                    "summary": s.summary,
                    "evidence": s.evidence,
                    "implicit_need": s.implicit_need,
                    "confidence": s.confidence,
                    "extraction_model": s.extraction_model,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                }
                for s in signals
            ],
        }


@router.get("/feedback/{feedback_id}/source-snapshot", summary="View the retained source snapshot and current integrity")
async def get_source_snapshot(feedback_id: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        row = await session.get(RawFeedbackRow, feedback_id)
        if row is None:
            raise HTTPException(status_code=404, detail="材料不存在。")
        return export_source_snapshot(row)
