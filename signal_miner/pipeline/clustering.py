"""Theme clustering service.

Groups semantically similar signals into Themes.
Uses Agglomerative Clustering and LLM summarization.

P13-1 safety: pseudo-embedding records are excluded from clustering.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING

import numpy as np
from sklearn.cluster import AgglomerativeClustering
from sqlalchemy import or_, select
import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import RawFeedbackRow, SignalRow, ThemeRow
from signal_miner.models import new_id
from signal_miner.services.audit import log_pipeline_event

if TYPE_CHECKING:
    from signal_miner.llm import BaseLLMAdapter

logger = structlog.get_logger(__name__)


def _is_pseudo_embedding_model(model: str | None) -> bool:
    """Check if the embedding_model column indicates a pseudo/test-only embedding."""
    if not model:
        return True
    return "pseudo" in model.lower()

THEME_GENERATION_PROMPT = """You are a product manager analyzing a group of similar user feedback signals.
Your task is to define a unifying 'Theme' that encapsulates these signals.

Signals:
{signals}

Return strict JSON only:
{{
  "name": "Short, clear name for the theme (e.g. 'PDF Export Issues')",
  "description": "A 1-2 sentence description summarizing the core issue or request across these signals.",
  "representative_quotes": ["quote 1", "quote 2"] // Select 1-3 best direct user quotes from the evidence provided
}}
"""

async def cluster_signals_into_themes(
    llm: BaseLLMAdapter,
    distance_threshold: float = 0.45,  # Equivalent to cosine similarity ~0.55
    pipeline_profile: str = "product_feedback",
    version_id: str | None = None,
) -> int:
    """Cluster all un-themed signals and generate new themes or update existing ones.

    Returns the number of new themes created.

    Phase 7: ``pipeline_profile`` tags each created ThemeRow so that
    downstream asset generation and front-end filtering can scope by
    profile. Defaults to ``"product_feedback"`` for full backward compat.
    """
    session_factory = get_session_factory()

    async with session_factory() as session:
        # 1. Fetch signals that have embeddings, scoped to pipeline_profile and version_id
        stmt = (
            select(SignalRow)
            .outerjoin(RawFeedbackRow, RawFeedbackRow.id == SignalRow.raw_feedback_id)
            .where(
                SignalRow.embedding.is_not(None),
                SignalRow.processing_state != "dismissed",
                or_(
                    RawFeedbackRow.id.is_(None),
                    RawFeedbackRow.pipeline_profile == pipeline_profile,
                ),
            )
        )
        if version_id:
            stmt = stmt.where(SignalRow.version_id == version_id)
        result = await session.execute(stmt)
        all_signals = result.scalars().all()

        # P13-1: Exclude pseudo-embedding records from clustering.
        real_signals = [s for s in all_signals if not _is_pseudo_embedding_model(s.embedding_model)]
        if len(real_signals) < len(all_signals):
            logger.info(
                "clustering_filtered_pseudo",
                total_with_embeddings=len(all_signals),
                real_embeddings=len(real_signals),
                pseudo_excluded=len(all_signals) - len(real_signals),
            )

        # 2. Exclude signals already assigned to a theme (idempotency)
        existing_themes_stmt = select(ThemeRow).where(ThemeRow.pipeline_profile == pipeline_profile)
        if version_id:
            existing_themes_stmt = existing_themes_stmt.where(ThemeRow.version_id == version_id)
        existing_result = await session.execute(existing_themes_stmt)
        existing_themes = existing_result.scalars().all()

        already_themed_ids: set[str] = set()
        for t in existing_themes:
            for sid in (t.signal_ids or []):
                already_themed_ids.add(sid)

        signals = [s for s in real_signals if s.id not in already_themed_ids]

        if len(signals) < 1:
            return 0

        # Extract embeddings and IDs
        embeddings = np.array([sig.embedding for sig in signals])
        [sig.id for sig in signals]

        # 2. Run clustering (Agglomerative with cosine distance)
        # Using cosine distance: 1 - cosine_similarity
        if len(signals) == 1:
            labels = [0]
        else:
            clustering = AgglomerativeClustering(
                n_clusters=None,
                metric="cosine",
                linkage="average",
                distance_threshold=distance_threshold
            )
            labels = clustering.fit_predict(embeddings)

        # 3. Group signals by cluster label
        clusters: dict[int, list[SignalRow]] = {}
        for label, sig in zip(labels, signals, strict=False):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(sig)

        themes_created = 0

        # 4. For each cluster with >= 1 signals, generate a theme
        for _label, cluster_signals in clusters.items():
            if len(cluster_signals) < 1:
                continue

            # Prepare data for LLM
            signal_texts = []
            for sig in cluster_signals:
                ev_text = " | ".join(sig.evidence) if sig.evidence else "No direct quote"
                signal_texts.append(f"- Summary: {sig.summary}\n  Evidence: {ev_text}")

            prompt = THEME_GENERATION_PROMPT.format(signals="\n".join(signal_texts))

            try:
                response_text = await llm.call_structured(prompt, temperature=0.2)
                # Cleanup markdown fences if present
                response_text = response_text.strip()
                if response_text.startswith("```json"):
                    response_text = response_text[7:]
                if response_text.startswith("```"):
                    response_text = response_text[3:]
                if response_text.endswith("```"):
                    response_text = response_text[:-3]

                theme_data = json.loads(response_text)

                theme_id = new_id("thm")
                theme_row = ThemeRow(
                    id=theme_id,
                    name=theme_data.get("name", "Untitled Theme"),
                    description=theme_data.get("description", ""),
                    signal_ids=[sig.id for sig in cluster_signals],
                    signal_count=len(cluster_signals),
                    representative_quotes=theme_data.get("representative_quotes", []),
                    status="draft",
                    pipeline_profile=pipeline_profile,
                    version_id=version_id or getattr(cluster_signals[0], "version_id", None) or "default",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
                session.add(theme_row)
                themes_created += 1

                await log_pipeline_event(
                    event_type="theme.created",
                    pipeline_step="clustering",
                    detail={
                        "theme_id": theme_id,
                        "name": theme_row.name,
                        "signal_count": theme_row.signal_count
                    }
                )

            except Exception as e:
                logger.error("theme_generation_failed", cluster_size=len(cluster_signals), error=str(e))

        if themes_created > 0:
            await session.commit()

        return themes_created
