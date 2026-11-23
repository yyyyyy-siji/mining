"""Quality gate — cheap LLM pre-classifier to filter non-actionable feedback.

Design reference: Quackback's quality-gate.service.ts + shouldExtract() pattern.
The gate runs before the more expensive extraction step to save tokens.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import structlog

from signal_miner.pipeline.prompts import build_quality_gate_prompt
from signal_miner.pipeline.utils import strip_code_fences
from signal_miner.services.audit import log_pipeline_event

if TYPE_CHECKING:
    from signal_miner.llm import BaseLLMAdapter

logger = structlog.get_logger(__name__)


class QualityGateResult:
    """Result of the quality gate evaluation."""

    def __init__(self, extract: bool, reason: str, tier: str) -> None:
        self.extract = extract
        self.reason = reason
        self.tier = tier


async def should_extract(
    *,
    source_type: str,
    text: str,
    raw_feedback_id: str,
    llm: BaseLLMAdapter,
    bypass_gate: bool = False,
) -> QualityGateResult:
    """Run the quality gate to decide if feedback contains actionable signal.

    Returns a QualityGateResult. On LLM failure, defaults to extract=True
    (fail-open) to avoid dropping real feedback.
    """
    if bypass_gate:
        return QualityGateResult(extract=True, reason="Gate bypassed", tier="bypassed")

    # Skip gate for very short texts
    if len(text.strip()) < 10:
        return QualityGateResult(
            extract=False, reason="Text too short to contain actionable feedback", tier="noise"
        )

    prompt = build_quality_gate_prompt(source_type=source_type, text=text)

    try:
        response_text = await llm.call_structured(prompt, temperature=0.1, max_tokens=200)
        response_text = strip_code_fences(response_text)
        result = json.loads(response_text)

        gate = QualityGateResult(
            extract=bool(result.get("extract", True)),
            reason=result.get("reason", ""),
            tier=result.get("tier", "unclear"),
        )

        event_type = "quality_gate.passed" if gate.extract else "quality_gate.rejected"
        await log_pipeline_event(
            event_type=event_type,
            pipeline_step="quality_gate",
            raw_feedback_id=raw_feedback_id,
            detail={
                "tier": gate.tier,
                "reason": gate.reason,
                "source_type": source_type,
            },
        )

        logger.info(
            "quality_gate_result",
            raw_feedback_id=raw_feedback_id,
            extract=gate.extract,
            tier=gate.tier,
        )
        return gate

    except Exception as exc:
        # Fail open — if the gate fails, let extraction proceed
        logger.warning(
            "quality_gate_failed",
            raw_feedback_id=raw_feedback_id,
            error=str(exc),
        )
        await log_pipeline_event(
            event_type="quality_gate.error",
            pipeline_step="quality_gate",
            raw_feedback_id=raw_feedback_id,
            detail={"error": str(exc)},
        )
        return QualityGateResult(extract=True, reason="Gate failed, defaulting to extract", tier="unclear")



