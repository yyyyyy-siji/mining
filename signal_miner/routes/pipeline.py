"""Pipeline trigger and progress streaming routes.

Design reference: agentic-prd-generation/backend/routes/generation.py
  - POST to trigger background pipeline
  - GET SSE stream for progress updates

Fix: run_id is generated HERE and passed into the background pipeline,
so the caller and the pipeline share the same identifier for SSE.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sse_starlette.sse import EventSourceResponse

from signal_miner.db import get_session_factory
from signal_miner.db.models import PipelineRunRow, RawFeedbackRow
from signal_miner.models import ProcessingState, new_id

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class RunPipelineRequest(BaseModel):
    """Request to trigger the mining pipeline."""
    feedback_ids: list[str] | None = Field(
        None,
        description="Specific feedback IDs to process. If empty, processes all pending items.",
    )
    max_signals: int = Field(5, ge=1, le=10)
    confidence_threshold: float = Field(
        0.5, ge=0.0, le=1.0,
        deprecated=True,
        description="DEPRECATED P13-1: 未校准，已忽略，不参与入库或自动决策",
    )
    profile: str = Field(
        "product_feedback",
        description="Pipeline profile name. Use one of GET /api/v1/profiles.",
    )
    version_id: str = Field(
        "default",
        max_length=40,
        description="Dataset version ID to scope pending feedback and generated assets.",
    )


class RunPipelineResponse(BaseModel):
    run_id: str
    feedback_count: int
    profile: str
    version_id: str = "default"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/pipeline/run",
    response_model=RunPipelineResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger the full mining pipeline",
)
async def run_pipeline(
    request: RunPipelineRequest,
    background_tasks: BackgroundTasks,
    http_request: Request,
) -> RunPipelineResponse:
    """Start the mining pipeline on feedback items.

    If feedback_ids is not provided, processes all pending feedback items.
    Returns immediately with a run_id for SSE progress tracking.
    The SAME run_id is used by the background pipeline for SSE events.
    """
    session_factory = get_session_factory()

    effective_version = "default" if not request.version_id or request.version_id == "all" else request.version_id.strip()

    # Resolve feedback IDs
    if request.feedback_ids:
        feedback_ids = request.feedback_ids
    else:
        async with session_factory() as session:
            stmt = (
                select(RawFeedbackRow.id)
                .where(RawFeedbackRow.processing_state == ProcessingState.PENDING)
                .where(RawFeedbackRow.pipeline_profile == request.profile)
                .where(RawFeedbackRow.version_id == effective_version)
                .order_by(RawFeedbackRow.created_at.asc())
            )
            result = await session.execute(stmt)
            feedback_ids = [row[0] for row in result.all()]

    if not feedback_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No pending feedback items found for profile '{request.profile}' in version '{effective_version}'.",
        )

    runtime = http_request.app.state.runtime

    # Generate run_id HERE and pass it into the pipeline
    run_id = new_id("run")

    await runtime.streamer.publish(
        run_id,
        {
            "run_id": run_id,
            "profile": request.profile,
            "version_id": effective_version,
            "step": "queued",
            "status": "running",
            "progress": 0.0,
            "message": f"管线已启动，准备处理 {len(feedback_ids)} 条反馈…",
            "stats": {},
            "error": None,
        },
    )

    from signal_miner.pipeline.runner import run_mining_pipeline

    background_tasks.add_task(
        run_mining_pipeline,
        run_id=run_id,
        feedback_ids=feedback_ids,
        llm=runtime.llm,
        streamer=runtime.streamer,
        embedding_llm=runtime.embedding_llm,
        max_signals=request.max_signals,
        confidence_threshold=request.confidence_threshold,
        profile_name=request.profile,
        version_id=effective_version,
    )

    return RunPipelineResponse(
        run_id=run_id,
        feedback_count=len(feedback_ids),
        profile=request.profile,
        version_id=effective_version,
    )


@router.get(
    "/pipeline/stream/{run_id}",
    summary="Stream pipeline progress via SSE",
)
async def stream_pipeline(run_id: str, http_request: Request) -> EventSourceResponse:
    """Establish an SSE connection for real-time pipeline progress updates."""
    runtime = http_request.app.state.runtime
    queue = await runtime.streamer.add_subscriber(run_id)

    async def event_publisher() -> AsyncIterator[dict[str, str]]:
        try:
            while True:
                payload = await queue.get()
                yield {"event": "message", "data": json.dumps(payload, default=str)}
                if payload.get("status") in ("completed", "completed_with_skips", "failed"):
                    return
        finally:
            await runtime.streamer.remove_subscriber(run_id, queue)

    return EventSourceResponse(event_publisher())


# ---------------------------------------------------------------------------
# Run status lookup (P13-1 fix-2)
# ---------------------------------------------------------------------------

@router.get(
    "/pipeline/runs",
    summary="List recent and active pipeline runs",
)
async def list_pipeline_runs(
    request: Request,
    profile: str | None = None,
    version_id: str | None = None,
    limit: int = Query(5, ge=1, le=20),
) -> dict:
    """Return recent pipeline runs merged with in-memory live step progress."""
    streamer = request.app.state.runtime.streamer
    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(PipelineRunRow).order_by(PipelineRunRow.started_at.desc()).limit(limit)
        if profile:
            stmt = stmt.where(PipelineRunRow.pipeline_profile == profile)
        if version_id and version_id != "all":
            stmt = stmt.where(PipelineRunRow.version_id == version_id)
        rows = list((await session.execute(stmt)).scalars().all())

    items: list[dict] = []
    seen: set[str] = set()
    for cached in streamer.recent_runs():
        rid = cached.get("run_id")
        if not isinstance(rid, str) or rid in seen:
            continue
        if any(row.id == rid for row in rows):
            continue
        if profile and cached.get("profile") and cached.get("profile") != profile:
            continue
        seen.add(rid)
        snap = streamer.get_snapshot(rid)
        items.append({
            "id": rid,
            "status": cached.get("status", "running"),
            "profile": cached.get("profile") or profile,
            "stats": cached.get("stats", {}),
            "error": cached.get("error"),
            "feedback_count": None,
            "started_at": None,
            "completed_at": None,
            "live": snap,
        })

    for row in rows:
        snap = streamer.get_snapshot(row.id)
        items.append({
            "id": row.id,
            "status": row.status,
            "profile": row.pipeline_profile,
            "stats": row.stats,
            "error": row.error,
            "feedback_count": row.feedback_count,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "live": snap,
        })
    return {"runs": items[:limit]}


@router.get(
    "/pipeline/runs/{run_id}",
    summary="Get pipeline run status",
)
async def get_pipeline_run(run_id: str, request: Request) -> dict:
    """Return the current status of a pipeline run."""
    streamer = request.app.state.runtime.streamer
    snap = streamer.get_snapshot(run_id)
    session_factory = get_session_factory()
    async with session_factory() as session:
        row = await session.get(PipelineRunRow, run_id)
        if not row:
            if snap and snap.get("latest"):
                latest = snap["latest"]
                return {
                    "id": run_id,
                    "status": latest.get("status", "running"),
                    "profile": latest.get("profile"),
                    "stats": latest.get("stats", {}),
                    "error": latest.get("error"),
                    "feedback_count": None,
                    "started_at": None,
                    "completed_at": None,
                    "live": snap,
                }
            raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
        return {
            "id": row.id,
            "status": row.status,
            "profile": row.pipeline_profile,
            "stats": row.stats,
            "error": row.error,
            "feedback_count": row.feedback_count,
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "live": snap,
        }


# ---------------------------------------------------------------------------
# Profile discovery (Phase 7)
# ---------------------------------------------------------------------------

class ProfileSummary(BaseModel):
    """Public summary of a single pipeline profile."""
    name: str
    display_name: str
    display_name_en: str
    description: str
    signal_types: list[str]
    source_types: list[str]


@router.get(
    "/profiles",
    response_model=list[ProfileSummary],
    summary="List all available pipeline profiles",
)
async def list_pipeline_profiles() -> list[ProfileSummary]:
    """Return every registered PipelineProfile. Front-end uses this to
    render the profile switcher; the API uses it to validate request.profile.
    """
    from signal_miner.pipeline.pipeline_profile import PROFILE_REGISTRY

    return [
        ProfileSummary(
            name=p.name,
            display_name=p.display_name,
            display_name_en=p.display_name_en,
            description=p.description,
            signal_types=list(p.signal_types),
            source_types=list(p.source_types),
        )
        for p in PROFILE_REGISTRY.values()
    ]
