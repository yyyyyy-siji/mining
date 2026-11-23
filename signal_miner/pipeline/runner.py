"""Pipeline runner — orchestrates the full mining pipeline.

Design reference: agentic-prd-generation/backend/pipelines/pipeline_runner.py
  - Staged pipeline with immutable state transitions
  - SSE progress streaming
  - Error handling with terminal state persistence

Pipeline stages (end-to-end):
  Phase 1: Quality gate + signal extraction
  Phase 2: Embedding + deduplication + clustering
  Phase 3: Asset generation (PainPoint → Opportunity → Requirement)
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import TYPE_CHECKING

from sqlalchemy import select
import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import PipelineRunRow, RawFeedbackRow
from signal_miner.models import PipelineStep, ProcessingState
from signal_miner.models.feedback import PipelineRun
from signal_miner.pipeline.asset_generator import generate_assets_from_themes
from signal_miner.pipeline.clustering import cluster_signals_into_themes
from signal_miner.pipeline.deduplication import deduplicate_signals
from signal_miner.pipeline.embedding import EmbeddingResult, generate_embeddings_for_signals
from signal_miner.pipeline.extraction import extract_signals
from signal_miner.services.audit import log_pipeline_event

if TYPE_CHECKING:
    from signal_miner.llm import BaseLLMAdapter
    from signal_miner.services import StreamerService

logger = structlog.get_logger(__name__)

MAX_RETRIES = 3


async def run_mining_pipeline(
    *,
    run_id: str,
    feedback_ids: list[str],
    llm: BaseLLMAdapter,
    streamer: StreamerService | None = None,
    embedding_llm: BaseLLMAdapter | None = None,
    max_signals: int = 5,
    confidence_threshold: float = 0.5,
    profile_name: str = "product_feedback",
    version_id: str = "default",
) -> str:
    """Run the full signal mining pipeline on a batch of feedback items.

    Args:
        run_id: Externally-assigned run ID so that the caller (route)
                and background task share the same identifier for SSE.
        feedback_ids: Raw feedback item IDs to process.
        llm: LLM adapter for extraction / summarisation.
        streamer: Optional SSE streamer for progress events.
        max_signals: Cap on signals per feedback item.
        confidence_threshold: Minimum extraction confidence.
        profile_name: Name of the PipelineProfile to use. Defaults to
                ``"product_feedback"`` for full backward compatibility.
                Pass ``"aigc_video"`` to switch the extraction /
                clustering / asset-generation prompts to the AIGC
                video viral-mining mode.

    Returns the run_id (same value that was passed in).
    """
    # Phase 7: resolve profile once at the top of the run.
    from signal_miner.pipeline.pipeline_profile import get_profile

    profile = get_profile(profile_name)
    total = len(feedback_ids)

    async def publish(step: str, status: str, progress: float, message: str, **kwargs):
        state = PipelineRun(
            run_id=run_id,
            step=step,
            status=status,
            progress=progress,
            message=message,
            stats=kwargs.get("stats", {}),
            error=kwargs.get("error"),
        )
        if streamer:
            await streamer.publish(run_id, state.to_event_payload())

    try:
        # --- Persist run record ---
        session_factory = get_session_factory()
        async with session_factory() as session:
            run_row = PipelineRunRow(
                id=run_id,
                status="running",
                feedback_count=total,
                pipeline_profile=profile_name,
                version_id=version_id,
                started_at=datetime.now(timezone.utc),
            )
            session.add(run_row)
            await session.commit()

        # ==================================================================
        # Phase 1 — Signal Extraction
        # ==================================================================
        await publish(
            PipelineStep.QUALITY_GATE, "running", 0.02,
            f"Phase 1: Running quality gate on {total} feedback items (profile={profile_name})",
        )
        await publish(
            PipelineStep.EXTRACTION, "running", 0.04,
            f"Phase 1: Extracting signals from {total} feedback items (profile={profile_name})",
        )

        all_signal_ids: list[str] = []
        completed = 0
        failed = 0

        for idx, fb_id in enumerate(feedback_ids):
            progress = (idx / total) * 0.30  # Phase 1 occupies 0–30%
            await publish(
                PipelineStep.EXTRACTION, "running", progress,
                f"Extracting signals from item {idx + 1}/{total}",
            )

            last_exc: Exception | None = None
            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    sids = await extract_signals(
                        fb_id,
                        llm=llm,
                        max_signals=max_signals,
                        confidence_threshold=confidence_threshold,
                        profile=profile,
                    )
                    all_signal_ids.extend(sids)
                    completed += 1
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < MAX_RETRIES:
                        wait_seconds = attempt  # 1s, 2s
                        logger.warning(
                            "pipeline_extraction_retry",
                            run_id=run_id,
                            raw_feedback_id=fb_id,
                            attempt=attempt,
                            max_retries=MAX_RETRIES,
                            wait_seconds=wait_seconds,
                            error=str(exc),
                        )
                        await asyncio.sleep(wait_seconds)

            if last_exc is not None:
                failed += 1
                logger.warning(
                    "pipeline_extraction_item_failed",
                    run_id=run_id, raw_feedback_id=fb_id,
                    attempts=MAX_RETRIES, error=str(last_exc),
                )

        extraction_stats = {
            "total_feedback": total,
            "extraction_completed": completed,
            "extraction_failed": failed,
            "signals_extracted": len(all_signal_ids),
        }

        if not all_signal_ids:
            await publish(
                PipelineStep.COMPLETE, "completed", 1.0,
                "No actionable signals found in the provided feedback.",
                stats=extraction_stats,
            )
            return run_id

        # ==================================================================
        # Phase 2 — Embedding + Clustering
        # ==================================================================
        await publish(
            PipelineStep.EMBEDDING, "running", 0.35,
            f"Phase 2: Generating embeddings for {len(all_signal_ids)} signals",
        )

        emb_result = EmbeddingResult(
            status="blocked_embedding_exception",
            semantic_ready=False,
            reason="Embedding phase not yet executed",
            requested_count=len(all_signal_ids),
        )
        try:
            emb_result = await generate_embeddings_for_signals(
                all_signal_ids,
                embedding_llm or llm,
            )
        except Exception as exc:
            emb_result = EmbeddingResult(
                status="blocked_embedding_exception",
                semantic_ready=False,
                reason=f"Embedding phase crashed: {exc}",
                requested_count=len(all_signal_ids),
            )
            logger.warning("pipeline_embedding_failed", run_id=run_id, error=str(exc))

        # P13-1 fix-2: Read semantic_ready flag directly from structured result.
        dedup_removed = 0
        themes_created = 0
        asset_stats: dict = {}
        final_run_status = "completed"

        if not emb_result.semantic_ready:
            # --- Circuit breaker ---
            logger.info(
                "pipeline_semantic_skipped",
                run_id=run_id,
                embedding_status=emb_result.status,
                reason=emb_result.reason,
            )
            await publish(
                PipelineStep.COMPLETE, "running", 0.60,
                f"文本提取已完成；语义去重/聚类未执行：{emb_result.reason}",
                stats={
                    "semantic_phase": "skipped",
                    "embedding_status": emb_result.status,
                    "embedding_reason": emb_result.reason,
                    "stored_real_count": emb_result.stored_real_count,
                    "failed_count": emb_result.failed_count,
                },
            )
            final_run_status = "completed_with_skips"
        else:
            # --- Normal path ---
            await publish(
                PipelineStep.DEDUPLICATION, "running", 0.42,
                f"Phase 2: Deduplicating {len(all_signal_ids)} signals",
            )
            try:
                all_signal_ids, dedup_removed = await deduplicate_signals(all_signal_ids)
            except Exception as exc:
                logger.warning("pipeline_dedup_failed", run_id=run_id, error=str(exc))

            await publish(
                PipelineStep.CLUSTERING, "running", 0.50,
                f"Phase 2: Clustering {len(all_signal_ids)} signals into themes (removed {dedup_removed} duplicates)",
            )
            try:
                themes_created = await cluster_signals_into_themes(
                    llm,
                    pipeline_profile=profile_name,
                    version_id=version_id,
                )
            except Exception as exc:
                logger.warning("pipeline_clustering_failed", run_id=run_id, error=str(exc))

            # ==================================================================
            # Phase 3 — Asset Generation (only if themes were created)
            # ==================================================================
            if themes_created > 0:
                await publish(
                    PipelineStep.PAIN_POINT, "running", 0.65,
                    f"Phase 3: Generating requirement assets from {themes_created} themes",
                )
                asset_step_map = {
                    "pain_point": PipelineStep.PAIN_POINT,
                    "opportunity": PipelineStep.OPPORTUNITY,
                    "requirement": PipelineStep.REQUIREMENT,
                }

                async def _on_asset_progress(step_key: str, pct: float, msg: str) -> None:
                    step_enum = asset_step_map.get(step_key)
                    if step_enum is not None:
                        await publish(step_enum, "running", pct, msg)

                try:
                    asset_stats = await generate_assets_from_themes(
                        llm,
                        profile=profile,
                        on_progress=_on_asset_progress,
                        version_id=version_id,
                    )
                except Exception as exc:
                    logger.warning("pipeline_asset_gen_failed", run_id=run_id, error=str(exc))

        # ==================================================================
        # Done
        # ==================================================================
        final_stats = {
            **extraction_stats,
            "dedup_removed": dedup_removed,
            "themes_created": themes_created,
            "embedding_status": emb_result.status,
            "embedding_reason": emb_result.reason,
            "semantic_phase": "skipped" if not emb_result.semantic_ready else "completed",
            "stored_real_count": emb_result.stored_real_count,
            "failed_count": emb_result.failed_count,
            **{f"assets_{k}": v for k, v in asset_stats.items()},
        }

        semantic_note = (
            f"文本提取已完成；语义去重/聚类未执行：{emb_result.reason}"
            if not emb_result.semantic_ready
            else f"{len(all_signal_ids)} signals, {themes_created} themes"
        )

        await publish(
            PipelineStep.COMPLETE, final_run_status, 1.0,
            (
                f"Pipeline complete: {semantic_note}, "
                f"{asset_stats.get('pain_points', 0)} pain points, "
                f"{asset_stats.get('opportunities', 0)} opportunities, "
                f"{asset_stats.get('requirements', 0)} requirements"
            ),
            stats=final_stats,
        )

        await log_pipeline_event(
            event_type="pipeline.completed",
            pipeline_step="pipeline",
            detail={"run_id": run_id, "profile": profile_name, **final_stats},
        )
        logger.info("pipeline_completed", run_id=run_id, profile=profile_name, **final_stats)

        # --- Update run record ---
        async with session_factory() as session:
            run_row = await session.get(PipelineRunRow, run_id)
            if run_row:
                run_row.status = final_run_status
                run_row.stats = final_stats
                run_row.completed_at = datetime.now(timezone.utc)
                await session.commit()

        return run_id

    except Exception as exc:
        await publish(
            PipelineStep.ERROR, "failed", 0.0,
            f"Pipeline failed: {exc}",
            error=str(exc),
        )
        await log_pipeline_event(
            event_type="pipeline.failed",
            pipeline_step="pipeline",
            detail={"run_id": run_id, "error": str(exc)},
        )
        logger.error("pipeline_failed", run_id=run_id, error=str(exc))

        # --- Update run record: failed ---
        try:
            async with session_factory() as session:
                run_row = await session.get(PipelineRunRow, run_id)
                if run_row:
                    run_row.status = "failed"
                    run_row.error = str(exc)
                    run_row.completed_at = datetime.now(timezone.utc)
                    await session.commit()
        except Exception:
            logger.warning("pipeline_run_record_update_failed", run_id=run_id)

        raise


# ---------------------------------------------------------------------------
# Feedback ingestion
# ---------------------------------------------------------------------------

def _stable_dedupe_key(source_id: str, text: str) -> str:
    """Deterministic, cross-process-safe dedupe key (replaces Python hash())."""
    normalized = text.strip().lower()
    digest = hashlib.sha256(f"{source_id}:{normalized}".encode()).hexdigest()[:16]
    return f"api_{digest}"


async def ingest_feedback(
    feedback_data: dict,
    *,
    pipeline_profile: str = "product_feedback",
    version_id: str = "default",
) -> str:
    """Ingest a single raw feedback item into the database.

    Returns the feedback item ID.

    Phase 7: ``pipeline_profile`` tags the row with the active mining mode
    so downstream extraction / front-end filtering can scope by profile.
    Unknown profile names are accepted as-is (the column is just a tag)
    but it's recommended to use one of the names returned by
    ``list_profiles()``.
    """
    result = await ingest_feedback_with_result(
        feedback_data,
        pipeline_profile=pipeline_profile,
        version_id=version_id,
    )
    return result.feedback_id


@dataclass(frozen=True)
class IngestFeedbackResult:
    """Actual outcome of this ingestion transaction; an ID alone is not a count."""

    feedback_id: str
    inserted: bool


async def ingest_feedback_with_result(
    feedback_data: dict,
    *,
    pipeline_profile: str = "product_feedback",
    version_id: str = "default",
) -> IngestFeedbackResult:
    """Return insertion only after commit; report every preserved reuse as such."""
    from sqlalchemy.exc import IntegrityError

    from signal_miner.models.feedback import RawFeedback

    feedback = RawFeedback.model_validate(feedback_data)
    scoped_version = (version_id or "default").strip() or "default"

    session_factory = get_session_factory()
    async with session_factory() as session:
        stmt = select(RawFeedbackRow).where(
            RawFeedbackRow.version_id == scoped_version,
            RawFeedbackRow.source_id == feedback.source_id,
            RawFeedbackRow.dedupe_key == feedback.dedupe_key,
        )
        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing:
            logger.info(
                "feedback_duplicate_skipped",
                id=existing.id, dedupe_key=feedback.dedupe_key, version_id=scoped_version,
            )
            return IngestFeedbackResult(existing.id, inserted=False)

        # New API keys include profile and object identity. A legacy text-only
        # key may be reused only when the exact retained source is provably the
        # same; never migrate, repair or overwrite its old provenance.
        if feedback.dedupe_key.startswith("source_v1_"):
            legacy_stmt = select(RawFeedbackRow).where(
                RawFeedbackRow.version_id == scoped_version,
                RawFeedbackRow.source_id == feedback.source_id,
                RawFeedbackRow.dedupe_key == _stable_dedupe_key(feedback.source_id, feedback.content.text),
                RawFeedbackRow.pipeline_profile == pipeline_profile,
                RawFeedbackRow.source_type == feedback.source_type,
                RawFeedbackRow.external_url == feedback.external_url,
            )
            legacy = (await session.execute(legacy_stmt)).scalar_one_or_none()
            if legacy is not None:
                old_context = legacy.context if isinstance(legacy.context, dict) else {}
                old_raw = old_context.get("raw_payload") or {}
                old_platform = old_context.get("platform") or (old_raw.get("platform") if isinstance(old_raw, dict) else None) or legacy.source_type
                new_platform = feedback.context.get("platform") or feedback.source_type
                entity = feedback.context.get("entity_type", "unknown")
                parents_match = all(
                    old_context.get(key) == feedback.context.get(key)
                    for key in ("parent_id", "parent_url", "parent_comment_id", "parent_comment_url")
                )
                comment_identified = entity != "comment" or bool(feedback.external_id)
                if (
                    (legacy.content or {}).get("text") == feedback.content.text
                    and legacy.external_id == feedback.external_id
                    and old_platform == new_platform
                    and old_context.get("entity_type", "unknown") == entity
                    and old_context.get("locator_level", "unknown") == feedback.context.get("locator_level", "unknown")
                    and parents_match and comment_identified
                ):
                    return IngestFeedbackResult(legacy.id, inserted=False)

        row = RawFeedbackRow(
            id=feedback.id,
            source_type=feedback.source_type,
            source_id=feedback.source_id,
            dedupe_key=feedback.dedupe_key,
            external_id=feedback.external_id,
            external_url=feedback.external_url,
            author=feedback.author.model_dump(),
            content=feedback.content.model_dump(),
            context=feedback.context,
            processing_state=ProcessingState.PENDING,
            source_created_at=feedback.source_created_at,
            pipeline_profile=pipeline_profile,
            version_id=scoped_version,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            # Another same-source import may have committed after our SELECT.
            # Preserve the unique index and reuse the winner after rollback.
            await session.rollback()
            winner = (await session.execute(stmt)).scalar_one_or_none()
            if winner is None or winner.pipeline_profile != pipeline_profile:
                raise
            return IngestFeedbackResult(winner.id, inserted=False)

        logger.info(
            "feedback_ingested",
            id=feedback.id,
            source_type=feedback.source_type,
            pipeline_profile=pipeline_profile,
        )
        return IngestFeedbackResult(feedback.id, inserted=True)
