"""Embedding generation for signals.

P13-1 fix-2: Returns structured ``EmbeddingResult`` with ``semantic_ready``
flag.  Runner reads ``semantic_ready`` directly — no string-matching on status.
Five negative scenarios are caught: no capability, all-failed, partial failure,
exception, and pseudo-only.  In every one, ``semantic_ready=False``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from typing import TYPE_CHECKING

import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import SignalRow
from signal_miner.services.audit import log_pipeline_event

if TYPE_CHECKING:
    from signal_miner.llm import BaseLLMAdapter

logger = structlog.get_logger(__name__)


@dataclass
class EmbeddingResult:
    """Structured result of an embedding generation run.

    ``semantic_ready`` is True ONLY when ALL of:
      - at least one requested signal was found
      - every signal needing embedding got a real (non-pseudo) vector
      - no embedding failures are unhandled
      - zero pseudo-embeddings were generated
    """

    status: str  # ready_real_embeddings | skipped_no_real_embedding_capability | ...
    semantic_ready: bool
    reason: str = ""

    requested_count: int = 0
    found_count: int = 0
    preexisting_real_count: int = 0
    stored_real_count: int = 0
    failed_count: int = 0
    pseudo_count: int = 0


async def generate_embeddings_for_signals(
    signal_ids: list[str],
    llm: BaseLLMAdapter,
) -> EmbeddingResult:
    """Generate embeddings. Returns structured result; caller decides next step."""
    req = len(signal_ids)

    # --- No embedding capability at all ---
    if not llm.supports_embedding:
        env = os.environ.get("APP_ENVIRONMENT", os.environ.get("ENVIRONMENT", "development"))
        allow_test_pseudo = os.environ.get("ALLOW_TEST_PSEUDO_EMBEDDING", "").lower() in (
            "1", "true", "yes",
        )
        if not (allow_test_pseudo and env == "test"):
            logger.warning(
                "embedding_blocked_no_capability",
                provider=llm.provider_name,
                signal_count=req,
            )
            await log_pipeline_event(
                event_type="embedding.blocked",
                pipeline_step="embedding",
                detail={"status": "skipped_no_real_embedding_capability", "provider": llm.provider_name},
            )
            return EmbeddingResult(
                status="skipped_no_real_embedding_capability",
                semantic_ready=False,
                reason=f"Adapter {llm.provider_name} does not support embeddings",
                requested_count=req,
            )

        # test-only pseudo path
        logger.warning("embedding_test_only_pseudo", provider=llm.provider_name)
        return await _generate_test_only_pseudo(signal_ids, llm)

    # --- Real embedding path ---
    session_factory = get_session_factory()
    stored = 0
    failed = 0
    preexisting = 0
    found = 0

    try:
        async with session_factory() as session:
            for sig_id in signal_ids:
                row = await session.get(SignalRow, sig_id)
                if not row:
                    continue
                found += 1

                if row.embedding is not None:
                    preexisting += 1
                    continue

                try:
                    evidence_text = " ".join(row.evidence) if row.evidence else ""
                    implicit_need = row.implicit_need or ""
                    text_to_embed = (
                        f"Summary: {row.summary}\nEvidence: {evidence_text}\nImplicit Need: {implicit_need}"
                    )
                    vector = await llm.embed(text_to_embed)
                    row.embedding = vector
                    row.embedding_model = f"{llm.provider_name}_embedding"
                    row.updated_at = datetime.now(timezone.utc)
                    await session.commit()
                    stored += 1
                    await asyncio.sleep(0.1)
                except Exception as e:
                    logger.error("embedding_generation_failed", signal_id=sig_id, error=str(e))
                    failed += 1

    except Exception as e:
        logger.error("embedding_phase_failed", error=str(e))
        return EmbeddingResult(
            status="blocked_embedding_exception",
            semantic_ready=False,
            reason=f"Embedding phase crashed: {e}",
            requested_count=req,
            found_count=found,
            preexisting_real_count=preexisting,
            stored_real_count=stored,
            failed_count=failed,
        )

    # --- Determine status ---
    if found == 0:
        return EmbeddingResult(
            status="blocked_no_signals_found",
            semantic_ready=False,
            reason="None of the requested signal IDs exist in the database",
            requested_count=req,
        )

    # semantic_ready: found >= 1, all found signals have real vectors, no failures, no pseudo
    needs_embedding = found - preexisting
    all_covered = (stored == needs_embedding) and (failed == 0)

    if all_covered:
        await log_pipeline_event(
            event_type="embedding.generated",
            pipeline_step="embedding",
            detail={"stored": stored, "failed": 0, "preexisting": preexisting},
        )
        logger.info("embeddings_ready", stored=stored, preexisting=preexisting)
        return EmbeddingResult(
            status="ready_real_embeddings",
            semantic_ready=True,
            reason=f"{stored} new + {preexisting} preexisting real embeddings",
            requested_count=req,
            found_count=found,
            preexisting_real_count=preexisting,
            stored_real_count=stored,
        )

    # Not fully covered
    result = EmbeddingResult(
        status="blocked_incomplete_real_embeddings",
        semantic_ready=False,
        reason=f"stored={stored} / needs={needs_embedding}, failed={failed}",
        requested_count=req,
        found_count=found,
        preexisting_real_count=preexisting,
        stored_real_count=stored,
        failed_count=failed,
    )
    await log_pipeline_event(
        event_type="embedding.incomplete",
        pipeline_step="embedding",
        detail={"stored": stored, "failed": failed, "needed": needs_embedding},
    )
    return result


async def _generate_test_only_pseudo(
    signal_ids: list[str],
    llm: BaseLLMAdapter,
) -> EmbeddingResult:
    import hashlib
    import random

    session_factory = get_session_factory()
    pseudo = 0

    async with session_factory() as session:
        for sig_id in signal_ids:
            row = await session.get(SignalRow, sig_id)
            if not row:
                continue
            if row.embedding is not None:
                continue

            evidence_text = " ".join(row.evidence) if row.evidence else ""
            implicit_need = row.implicit_need or ""
            text_to_embed = f"Summary: {row.summary}\nEvidence: {evidence_text}\nImplicit Need: {implicit_need}"
            sig_type = getattr(row, "signal_type", "") or ""
            type_seed = int(hashlib.md5(sig_type.encode("utf-8")).hexdigest(), 16) % 2**32
            rng_type = random.Random(type_seed)
            vector_type = [rng_type.gauss(0, 1) for _ in range(1536)]
            text_seed = int(hashlib.md5(text_to_embed.encode("utf-8")).hexdigest(), 16) % 2**32
            rng_text = random.Random(text_seed)
            vector_text = [rng_text.gauss(0, 1) for _ in range(1536)]
            vector_raw = [0.8 * t + 0.2 * u for t, u in zip(vector_type, vector_text, strict=False)]
            norm = sum(x**2 for x in vector_raw) ** 0.5
            vector = [x / norm for x in vector_raw]
            row.embedding = vector
            row.embedding_model = f"{llm.provider_name}_test_only_pseudo"
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            pseudo += 1

    await log_pipeline_event(
        event_type="embedding.test_only_pseudo",
        pipeline_step="embedding",
        detail={"pseudo_count": pseudo},
    )
    return EmbeddingResult(
        status="test_only_pseudo_embedding",
        semantic_ready=False,
        reason=f"Test-only pseudo-embeddings generated ({pseudo})",
        requested_count=len(signal_ids),
        pseudo_count=pseudo,
    )
