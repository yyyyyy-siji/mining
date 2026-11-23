"""Evidence chain validation module.

Validates that all evidence links in requirement assets are unbroken and trace
correctly back to active Signal and RawFeedback records in the database.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import select
import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import RawFeedbackRow, RequirementAssetRow, SignalRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = structlog.get_logger(__name__)


class BrokenLink(BaseModel):
    """Represents a broken link in the evidence chain."""

    signal_id: str
    raw_feedback_id: str
    reason: str


class ValidationReport(BaseModel):
    """Validation report for a single requirement asset's evidence trail."""

    requirement_id: str
    total_links: int
    valid_links: int
    broken_links: list[BrokenLink]
    is_valid: bool


async def validate_evidence_chain(requirement_id: str, session: AsyncSession | None = None) -> ValidationReport:
    """Validates the evidence chain for a specific requirement asset."""

    async def _do_validate(sess: AsyncSession) -> ValidationReport:
        req = await sess.get(RequirementAssetRow, requirement_id)
        if not req:
            raise ValueError(f"Requirement with ID {requirement_id} not found")

        evidence_trail = req.evidence_trail or []
        total_links = len(evidence_trail)
        broken_links: list[BrokenLink] = []

        for link in evidence_trail:
            # The trail is stored as a list of dicts in the DB.
            sig_id = link.get("signal_id")
            rf_id = link.get("raw_feedback_id")
            quote = link.get("quote")

            # 1. Check quote is not empty
            if not quote:
                broken_links.append(
                    BrokenLink(
                        signal_id=sig_id or "",
                        raw_feedback_id=rf_id or "",
                        reason="Quote is empty or missing",
                    )
                )
                continue

            # 2. Check signal_id exists and is valid
            if not sig_id:
                broken_links.append(
                    BrokenLink(
                        signal_id="",
                        raw_feedback_id=rf_id or "",
                        reason="Signal ID is missing",
                    )
                )
                continue

            sig = await sess.get(SignalRow, sig_id)
            if not sig:
                broken_links.append(
                    BrokenLink(
                        signal_id=sig_id,
                        raw_feedback_id=rf_id or "",
                        reason=f"SignalRow not found for signal_id: {sig_id}",
                    )
                )
                continue

            # 3. Check raw_feedback_id exists and is valid
            if not rf_id:
                broken_links.append(
                    BrokenLink(
                        signal_id=sig_id,
                        raw_feedback_id="",
                        reason="Raw Feedback ID is missing",
                    )
                )
                continue

            rfb = await sess.get(RawFeedbackRow, rf_id)
            if not rfb:
                broken_links.append(
                    BrokenLink(
                        signal_id=sig_id,
                        raw_feedback_id=rf_id,
                        reason=f"RawFeedbackRow not found for raw_feedback_id: {rf_id}",
                    )
                )
                continue

        valid_links = total_links - len(broken_links)
        is_valid = len(broken_links) == 0

        return ValidationReport(
            requirement_id=requirement_id,
            total_links=total_links,
            valid_links=valid_links,
            broken_links=broken_links,
            is_valid=is_valid,
        )

    if session:
        return await _do_validate(session)

    session_factory = get_session_factory()
    async with session_factory() as sess:
        return await _do_validate(sess)


async def validate_all_evidence_chains(session: AsyncSession | None = None) -> list[ValidationReport]:
    """Validates the evidence chains for all requirement assets in the database."""

    async def _do_validate_all(sess: AsyncSession) -> list[ValidationReport]:
        stmt = select(RequirementAssetRow.id)
        result = await sess.execute(stmt)
        req_ids = result.scalars().all()

        reports: list[ValidationReport] = []
        for req_id in req_ids:
            report = await validate_evidence_chain(req_id, session=sess)
            reports.append(report)
        return reports

    if session:
        return await _do_validate_all(session)

    session_factory = get_session_factory()
    async with session_factory() as sess:
        return await _do_validate_all(sess)
