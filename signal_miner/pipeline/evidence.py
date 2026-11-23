"""Evidence trail builder — constructs traceable evidence chains.

This is the key differentiator: every requirement asset can trace back
through Opportunity → PainPoint → Theme → Signal → RawFeedback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import (
    OpportunityRow,
    PainPointRow,
    RawFeedbackRow,
    SignalRow,
)
from signal_miner.models.assets import EvidenceLink

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


async def build_evidence_links(signal_ids: list[str], session: AsyncSession | None = None) -> list[EvidenceLink]:
    """Given a list of signal IDs, build standardized evidence links."""
    if not signal_ids:
        return []

    async def _do_build(sess: AsyncSession) -> list[EvidenceLink]:
        links: list[EvidenceLink] = []
        for sig_id in signal_ids:
            sig = await sess.get(SignalRow, sig_id)
            if not sig:
                continue

            rfb = await sess.get(RawFeedbackRow, sig.raw_feedback_id) if sig.raw_feedback_id else None
            best_quote = sig.evidence[0] if sig.evidence else sig.summary

            author_info = rfb.author if rfb and rfb.author else {}
            author_segment = ""
            if isinstance(author_info, dict):
                author_segment = author_info.get("segment", "") or author_info.get("company", "") or ""

            links.append(EvidenceLink(
                signal_id=sig.id,
                signal_summary=sig.summary,
                signal_type=sig.signal_type,
                quote=best_quote,
                confidence=sig.confidence,
                source_type=rfb.source_type if rfb else "",
                author_segment=author_segment,
                raw_feedback_id=sig.raw_feedback_id or "",
                external_url=rfb.external_url if rfb else None,
            ))
        return links

    if session:
        return await _do_build(session)

    session_factory = get_session_factory()
    async with session_factory() as sess:
        return await _do_build(sess)


async def build_evidence_trail_for_requirement(
    opportunity_ids: list[str],
    session: AsyncSession | None = None,
) -> list[EvidenceLink]:
    """Build a full evidence trail for a requirement asset."""
    if not opportunity_ids:
        return []

    async def _do_build(sess: AsyncSession) -> list[EvidenceLink]:
        all_signal_ids: set[str] = set()
        for opp_id in opportunity_ids:
            opp = await sess.get(OpportunityRow, opp_id)
            if not opp or not opp.pain_point_ids:
                continue

            for pp_id in opp.pain_point_ids:
                pp = await sess.get(PainPointRow, pp_id)
                if not pp:
                    continue
                for sid in (pp.evidence_signal_ids or []):
                    all_signal_ids.add(sid)
        return await build_evidence_links(list(all_signal_ids), session=sess)

    if session:
        return await _do_build(session)

    session_factory = get_session_factory()
    async with session_factory() as sess:
        return await _do_build(sess)


async def build_supporting_evidence_for_opportunity(
    pain_point_ids: list[str],
    session: AsyncSession | None = None,
) -> list[EvidenceLink]:
    """Build supporting evidence for an opportunity from its pain points."""
    if not pain_point_ids:
        return []

    async def _do_build(sess: AsyncSession) -> list[EvidenceLink]:
        all_signal_ids: set[str] = set()
        for pp_id in pain_point_ids:
            pp = await sess.get(PainPointRow, pp_id)
            if not pp:
                continue
            for sid in (pp.evidence_signal_ids or []):
                all_signal_ids.add(sid)
        return await build_evidence_links(list(all_signal_ids), session=sess)

    if session:
        return await _do_build(session)

    session_factory = get_session_factory()
    async with session_factory() as sess:
        return await _do_build(sess)

