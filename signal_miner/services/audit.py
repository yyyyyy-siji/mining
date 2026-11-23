"""Audit logging service for pipeline events.

Every AI action is recorded for transparency and traceability.
Design reference: Quackback's logPipelineEvent pattern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import AuditLogRow

logger = structlog.get_logger(__name__)


async def log_pipeline_event(
    *,
    event_type: str,
    pipeline_step: str | None = None,
    raw_feedback_id: str | None = None,
    signal_id: str | None = None,
    model: str | None = None,
    prompt_version: str | None = None,
    input_tokens: int | None = None,
    output_tokens: int | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    """Record a pipeline event to the audit log.

    This function is designed to be best-effort — it logs but does not
    raise on database errors to avoid disrupting the pipeline.
    """
    try:
        session_factory = get_session_factory()
        async with session_factory() as session:
            row = AuditLogRow(
                event_type=event_type,
                pipeline_step=pipeline_step,
                raw_feedback_id=raw_feedback_id,
                signal_id=signal_id,
                model=model,
                prompt_version=prompt_version,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                detail=detail or {},
                created_at=datetime.now(timezone.utc),
            )
            session.add(row)
            await session.commit()
    except Exception:
        logger.warning(
            "audit_log_failed",
            event_type=event_type,
            raw_feedback_id=raw_feedback_id,
            exc_info=True,
        )
