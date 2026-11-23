"""Semantic deduplication of signals based on vector embeddings.

Design reference: Quackback's interpretation.service.ts
Finds similar signals and deduplicates before clustering.

P13-1 safety: dedup is blocked when only pseudo-embeddings are available.
The confidence-based "keep higher confidence, dismiss lower" logic is also
disabled — uncalibrated LLM self-reported scores must not make destructive
dismiss decisions.
"""

from __future__ import annotations

import numpy as np
from sqlalchemy import select
import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import SignalRow

logger = structlog.get_logger(__name__)


def _is_pseudo_embedding_model(model: str | None) -> bool:
    """Check if the embedding_model column indicates a pseudo/test-only embedding."""
    if not model:
        return True
    return "pseudo" in model.lower()


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a = np.array(v1)
    b = np.array(v2)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


async def deduplicate_signals(
    signal_ids: list[str],
    threshold: float = 0.92,
) -> tuple[list[str], int]:
    """Deduplicate signals by cosine similarity on their embeddings.

    P13-1: This function now refuses to make destructive dismiss decisions
    based on uncalibrated LLM self-reported confidence.  When a pair of
    signals has similarity >= threshold, they are *flagged* as potential
    duplicates but neither is dismissed.  True dedup will return in P13-3
    once real embeddings + calibrated confidence are available.

    Returns:
        (surviving_signal_ids, removed_count)  — removed_count is always 0
        in P13-1 since no destructive dismiss is performed.
    """
    if len(signal_ids) < 2:
        return signal_ids, 0

    session_factory = get_session_factory()

    async with session_factory() as session:
        # Load all signals with their embeddings
        stmt = select(SignalRow).where(
            SignalRow.id.in_(signal_ids),
            SignalRow.embedding.is_not(None),
        )
        result = await session.execute(stmt)
        signals = result.scalars().all()

        if len(signals) < 2:
            return signal_ids, 0

        # P13-1: Filter out pseudo-embedding records from dedup.
        real_signals = [s for s in signals if not _is_pseudo_embedding_model(s.embedding_model)]
        if len(real_signals) < 2:
            logger.info(
                "dedup_skipped_no_real_embeddings",
                reason="All candidate signals have pseudo or missing embedding_model",
                total_candidates=len(signals),
                real_count=len(real_signals),
            )
            return signal_ids, 0

        # Pairwise comparison — log potential duplicates but do NOT dismiss
        sigs_list = list(real_signals)
        potential_dup_count = 0
        for i in range(len(sigs_list)):
            for j in range(i + 1, len(sigs_list)):
                sim = cosine_similarity(sigs_list[i].embedding, sigs_list[j].embedding)
                if sim >= threshold:
                    potential_dup_count += 1
                    logger.debug(
                        "potential_duplicate_detected",
                        signal_a=sigs_list[i].id,
                        signal_b=sigs_list[j].id,
                        similarity=round(sim, 4),
                        note="P13-1: no destructive dismiss — deferred to P13-3",
                    )

        if potential_dup_count > 0:
            logger.info(
                "dedup_potential_duplicates_logged",
                potential_duplicates=potential_dup_count,
                note="No dismiss performed — uncalibrated confidence cannot make destructive decisions",
            )

    # All signals survive — no destructive dismiss in P13-1
    return signal_ids, 0


async def find_similar_signals(
    target_signal_id: str,
    threshold: float = 0.55,
    limit: int = 5,
) -> list[dict]:
    """Find signals similar to the target signal based on embedding cosine similarity.

    P13-1: Pseudo-embedding records are excluded from results so that
    similarity search never returns matches based on fake vectors.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        target = await session.get(SignalRow, target_signal_id)
        if not target or not target.embedding:
            return []

        # P13-1: Skip search entirely if target has a pseudo embedding
        if _is_pseudo_embedding_model(target.embedding_model):
            logger.info(
                "similar_search_skipped_pseudo",
                target=target_signal_id,
                embedding_model=target.embedding_model,
            )
            return []

        stmt = select(SignalRow).where(
            SignalRow.id != target_signal_id,
            SignalRow.embedding.is_not(None),
        )
        result = await session.execute(stmt)
        candidates_all = result.scalars().all()

    # P13-1: Filter out pseudo-embedding candidates
    candidates = [c for c in candidates_all if not _is_pseudo_embedding_model(c.embedding_model)]

    similarities = []
    for cand in candidates:
        sim = cosine_similarity(target.embedding, cand.embedding)
        if sim >= threshold:
            similarities.append({
                "signal_id": cand.id,
                "summary": cand.summary,
                "similarity": sim,
                "signal_type": cand.signal_type,
            })

    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    return similarities[:limit]
