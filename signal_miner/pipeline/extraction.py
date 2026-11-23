"""Signal extraction service — the core AI processing step.

Design reference: Quackback's extraction.service.ts
  - Quality gate → LLM structured extraction → confidence filter → cap → persist → audit

This is Pass 1 of the pipeline. Pass 2 (embedding + interpretation) is Phase 2.

Phase 7 update: ``extract_signals`` accepts an optional ``profile`` argument.
When provided, the profile's ``extraction_prompt_template`` is used instead
of the hard-coded ``EXTRACTION_PROMPT``. When ``None`` (default), behavior
is byte-for-byte identical to the pre-Phase-7 implementation.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING

import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import RawFeedbackRow, SignalRow
from signal_miner.models import ProcessingState, new_id
from signal_miner.models.feedback import ExtractionResult
from signal_miner.pipeline.evidence_validation import check_evidence_in_source
from signal_miner.pipeline.prompts import EXTRACTION_PROMPT
from signal_miner.pipeline.quality_gate import should_extract
from signal_miner.pipeline.utils import strip_code_fences
from signal_miner.services.audit import log_pipeline_event
from signal_miner.settings import AppSettings

if TYPE_CHECKING:
    from signal_miner.llm import BaseLLMAdapter
    from signal_miner.pipeline.pipeline_profile import PipelineProfile

logger = structlog.get_logger(__name__)

EXTRACTION_PROMPT_VERSION = "v1"
VIDEO_EXTRACTION_PROMPT_VERSION = "v1-video"


async def extract_signals(
    raw_feedback_id: str,
    *,
    llm: BaseLLMAdapter,
    max_signals: int = 5,
    confidence_threshold: float = 0.5,  # DEPRECATED P13-1: ignored for trust decisions  # noqa: ARG001
    bypass_quality_gate: bool = False,
    profile: PipelineProfile | None = None,
) -> list[str]:
    """Extract product signals from a raw feedback item.

    Returns the list of created signal IDs.

    P13-1 fix-1: ``confidence_threshold`` is accepted for backward
    compatibility but NO LONGER filters signals for persistence.
    All white-listed signal types are stored regardless of confidence.
    ``max_signals``, SignalType whitelist, evidence validation, and
    quality-gate logic still apply.
    1. Load raw feedback item
    2. Check processing state
    3. Run quality gate
    4. LLM structured extraction
    5. Filter by confidence threshold
    6. Cap at max_signals
    7. Persist signals + audit log

    When ``profile`` is provided, the extraction prompt and signal-type
    whitelist are taken from the profile; the prompt-version tag recorded
    on each signal reflects the active mode. When ``profile`` is ``None``
    the original product-feedback path is used unchanged.
    """
    session_factory = get_session_factory()
    # P13-1 fix-1: prompt version tied to profile name, not mere existence
    prompt_version = (
        VIDEO_EXTRACTION_PROMPT_VERSION
        if profile is not None and profile.name == "aigc_video"
        else EXTRACTION_PROMPT_VERSION
    )

    async with session_factory() as session:
        # 1. Load raw feedback
        row = await session.get(RawFeedbackRow, raw_feedback_id)
        if not row:
            raise ValueError(f"Raw feedback {raw_feedback_id} not found")

        # 2. Check state — only process items in correct state
        if row.processing_state not in (
            ProcessingState.PENDING,
            ProcessingState.READY_FOR_EXTRACTION,
        ):
            logger.info(
                "extraction_skipped",
                raw_feedback_id=raw_feedback_id,
                state=row.processing_state,
            )
            return []

        # Mark as extracting
        row.processing_state = ProcessingState.EXTRACTING
        row.attempt_count += 1
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()

    try:
        content = row.content or {}
        text = content.get("text", "")
        subject = content.get("subject", "")
        source_type = row.source_type

        # 3. Quality gate
        settings = AppSettings()
        should_bypass = bypass_quality_gate or source_type in settings.quality_gate_bypass_sources
        gate = await should_extract(
            source_type=source_type,
            text=text,
            raw_feedback_id=raw_feedback_id,
            llm=llm,
            bypass_gate=should_bypass,
        )

        if not gate.extract:
            async with session_factory() as session:
                row = await session.get(RawFeedbackRow, raw_feedback_id)
                row.processing_state = ProcessingState.COMPLETED
                row.processed_at = datetime.now(timezone.utc)
                row.updated_at = datetime.now(timezone.utc)
                await session.commit()
            return []

        # 4. LLM structured extraction
        # Phase 7: select the prompt template from the active profile.
        # When profile is None (backward-compat path) the original
        # EXTRACTION_PROMPT constant is used byte-for-byte unchanged.
        template = (
            profile.extraction_prompt_template
            if profile is not None
            else EXTRACTION_PROMPT
        )
        prompt = template.format(
            source_type=source_type,
            subject=subject or "",
            text=text[:4000],  # Cap input to avoid token limits
            context=json.dumps(row.context or {}, default=str)[:1000],
            max_signals=max_signals,
        )

        response_text = await llm.call_structured(prompt, temperature=0.1, max_tokens=2000)
        usage = llm.last_usage
        response_text = strip_code_fences(response_text)

        try:
            result = ExtractionResult.model_validate_json(response_text)
        except Exception:
            # Try parsing as raw dict
            raw = json.loads(response_text)
            result = ExtractionResult.model_validate(raw)

        # 5. P13-1 fix-1: NO confidence filtering.
        # All LLM-returned signals pass through; confidence_threshold is
        # deprecated and retained only for backward-compatible call signatures.
        # White-listed signal types are still validated, evidence is still
        # checked, and max_signals still caps the result.
        _filtered = list(result.signals)  # No confidence gate

        # 5b. P13-1: SignalType whitelist — reject types not in active profile.
        allowed_types: set[str] | None = None
        if profile is not None:
            allowed_types = set(profile.signal_types)
        rejected_types: list[dict] = []
        if allowed_types is not None:
            kept: list = []
            for s in _filtered:
                if s.signalType in allowed_types:
                    kept.append(s)
                else:
                    rejected_types.append({
                        "rejected_type": s.signalType,
                        "summary": s.summary[:200],
                        "reason": "signalType not in profile whitelist",
                    })
            _filtered = kept
            if rejected_types:
                logger.info(
                    "signal_type_whitelist_rejected",
                    raw_feedback_id=raw_feedback_id,
                    rejected_count=len(rejected_types),
                    kept_count=len(_filtered),
                )

        # 5c. P13-1: Evidence validation — deterministic source-text matching.
        for s in _filtered:
            s.evidence_validation_status = check_evidence_in_source(
                s.evidence, text,
            )

        # 6. Cap at max_signals
        capped = _filtered[:max_signals]

        # 7. Persist signals
        # P13-1: populate confidence contract fields on every persisted signal.
        confidence_model_version = (
            f"provider={llm.provider_name}/model={llm.model_name}/prompt={prompt_version}"
        )

        signal_ids: list[str] = []
        async with session_factory() as session:
            row = await session.get(RawFeedbackRow, raw_feedback_id)
            row_version_id = getattr(row, "version_id", None) or "default"
            for extracted in capped:
                sig_id = new_id("sig")
                raw_score = max(0.0, min(1.0, extracted.confidence))
                signal_row = SignalRow(
                    id=sig_id,
                    raw_feedback_id=raw_feedback_id,
                    signal_type=extracted.signalType,
                    summary=extracted.summary,
                    evidence=extracted.evidence,
                    implicit_need=extracted.implicitNeed,
                    confidence=raw_score,
                    model_self_score=raw_score,
                    calibrated_confidence=None,  # P13-1: always null
                    confidence_method="llm_self_reported",
                    confidence_model_version=confidence_model_version,
                    evidence_validation_status=extracted.evidence_validation_status,
                    processing_state=ProcessingState.PENDING,
                    extraction_model=llm.provider_name,
                    extraction_prompt_version=prompt_version,
                    version_id=row_version_id,
                )
                session.add(signal_row)
                signal_ids.append(sig_id)

            # Update raw feedback state
            row.processing_state = ProcessingState.COMPLETED
            row.processed_at = datetime.now(timezone.utc)
            row.updated_at = datetime.now(timezone.utc)
            row.extraction_input_tokens = usage.get("input_tokens", 0)
            row.extraction_output_tokens = usage.get("output_tokens", 0)
            await session.commit()

        # Audit log
        await log_pipeline_event(
            event_type="extraction.completed",
            pipeline_step="extraction",
            raw_feedback_id=raw_feedback_id,
            model=llm.provider_name,
            prompt_version=prompt_version,
            detail={
                "signals_extracted": len(signal_ids),
                "signals_filtered": len(result.signals) - len(_filtered),
                "signals_capped": len(_filtered) - len(capped),
                "signal_types": [s.signalType for s in capped],
                "confidences": [s.confidence for s in capped],
                "evidence_validation_statuses": [s.evidence_validation_status for s in capped],
                "rejected_types": rejected_types,
            },
        )

        logger.info(
            "extraction_completed",
            raw_feedback_id=raw_feedback_id,
            signals_extracted=len(signal_ids),
        )
        return signal_ids

    except Exception as exc:
        # Mark as failed
        async with session_factory() as session:
            row = await session.get(RawFeedbackRow, raw_feedback_id)
            if row:
                row.processing_state = ProcessingState.FAILED
                row.last_error = str(exc)
                row.updated_at = datetime.now(timezone.utc)
                await session.commit()

        await log_pipeline_event(
            event_type="extraction.failed",
            pipeline_step="extraction",
            raw_feedback_id=raw_feedback_id,
            detail={"error": str(exc), "attempt_count": row.attempt_count if row else 0},
        )

        logger.error(
            "extraction_failed",
            raw_feedback_id=raw_feedback_id,
            error=str(exc),
        )
        raise



