"""Tests for the evidence chain validation and structured models."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from pydantic import ValidationError
import pytest

from signal_miner.models.assets import EvidenceLink
from signal_miner.pipeline.evidence_validator import (
    validate_all_evidence_chains,
    validate_evidence_chain,
)


def test_evidence_link_model_validation():
    """Verify that EvidenceLink Pydantic model validates required and optional fields correctly."""
    # 1. Valid construction
    link = EvidenceLink(
        signal_id="sig_001",
        raw_feedback_id="rfb_001",
        quote="This is an awesome tool!",
        source_type="manual",
        author_segment="Enterprise",
        signal_summary="User likes the tool",
        signal_type="praise",
        confidence=0.9,
        external_url="http://example.com",
    )
    assert link.signal_id == "sig_001"
    assert link.raw_feedback_id == "rfb_001"
    assert link.quote == "This is an awesome tool!"
    assert link.source_type == "manual"
    assert link.author_segment == "Enterprise"
    assert link.signal_summary == "User likes the tool"
    assert link.signal_type == "praise"
    assert link.confidence == 0.9
    assert link.external_url == "http://example.com"

    # 2. Allow empty string for author_segment
    link_empty_author = EvidenceLink(
        signal_id="sig_001",
        raw_feedback_id="rfb_001",
        quote="This is an awesome tool!",
        source_type="manual",
        author_segment="",
        signal_summary="User likes the tool",
        signal_type="praise",
        confidence=0.9,
        external_url=None,
    )
    assert link_empty_author.author_segment == ""

    # 3. Missing required field (e.g. quote) throws ValidationError
    with pytest.raises(ValidationError):
        EvidenceLink(
            signal_id="sig_001",
            raw_feedback_id="rfb_001",
            source_type="manual",
            author_segment="Enterprise",
            signal_summary="User likes the tool",
            signal_type="praise",
            confidence=0.9,
        )

    # 4. Missing required field (e.g. raw_feedback_id) throws ValidationError
    with pytest.raises(ValidationError):
        EvidenceLink(
            signal_id="sig_001",
            quote="Quote only",
            source_type="manual",
            author_segment="Enterprise",
            signal_summary="User likes the tool",
            signal_type="praise",
            confidence=0.9,
        )


@pytest.mark.asyncio
async def test_validation_report_with_valid_chain():
    """Verify validate_evidence_chain returns is_valid=True for a fully valid chain."""
    mock_session = AsyncMock()

    class MockRequirementRow:
        id = "req_1"
        title = "Test Requirement"
        evidence_trail = [
            {
                "signal_id": "sig_1",
                "raw_feedback_id": "rfb_1",
                "quote": "Valid quote",
                "source_type": "manual",
                "author_segment": "Enterprise",
                "signal_summary": "Summary",
                "signal_type": "feature",
                "confidence": 0.8,
            }
        ]

    class MockSignalRow:
        id = "sig_1"
        raw_feedback_id = "rfb_1"
        summary = "Summary"
        signal_type = "feature"
        evidence = ["Valid quote"]
        confidence = 0.8

    class MockRawFeedbackRow:
        id = "rfb_1"
        source_type = "manual"
        author = {"segment": "Enterprise"}
        content = {"text": "Valid quote"}
        external_url = None

    async def mock_get(model, id_val):
        if model.__name__ == "RequirementAssetRow" and id_val == "req_1":
            return MockRequirementRow()
        if model.__name__ == "SignalRow" and id_val == "sig_1":
            return MockSignalRow()
        if model.__name__ == "RawFeedbackRow" and id_val == "rfb_1":
            return MockRawFeedbackRow()
        return None

    mock_session.get.side_effect = mock_get

    report = await validate_evidence_chain("req_1", session=mock_session)

    assert report.requirement_id == "req_1"
    assert report.total_links == 1
    assert report.valid_links == 1
    assert report.is_valid is True
    assert len(report.broken_links) == 0


@pytest.mark.asyncio
async def test_validation_report_detects_missing_signal():
    """Verify validate_evidence_chain flags broken links when signal_id is missing/invalid."""
    mock_session = AsyncMock()

    class MockRequirementRow:
        id = "req_1"
        title = "Test Requirement"
        evidence_trail = [
            {
                "signal_id": "sig_missing",
                "raw_feedback_id": "rfb_1",
                "quote": "Valid quote",
                "source_type": "manual",
                "author_segment": "Enterprise",
                "signal_summary": "Summary",
                "signal_type": "feature",
                "confidence": 0.8,
            }
        ]

    async def mock_get(model, id_val):
        if model.__name__ == "RequirementAssetRow" and id_val == "req_1":
            return MockRequirementRow()
        # SignalRow returns None for sig_missing
        return None

    mock_session.get.side_effect = mock_get

    report = await validate_evidence_chain("req_1", session=mock_session)

    assert report.requirement_id == "req_1"
    assert report.total_links == 1
    assert report.valid_links == 0
    assert report.is_valid is False
    assert len(report.broken_links) == 1
    assert report.broken_links[0].signal_id == "sig_missing"
    assert "SignalRow not found" in report.broken_links[0].reason


@pytest.mark.asyncio
async def test_validation_report_detects_missing_feedback():
    """Verify validate_evidence_chain flags broken links when raw_feedback_id is invalid."""
    mock_session = AsyncMock()

    class MockRequirementRow:
        id = "req_1"
        title = "Test Requirement"
        evidence_trail = [
            {
                "signal_id": "sig_1",
                "raw_feedback_id": "rfb_missing",
                "quote": "Valid quote",
                "source_type": "manual",
                "author_segment": "Enterprise",
                "signal_summary": "Summary",
                "signal_type": "feature",
                "confidence": 0.8,
            }
        ]

    class MockSignalRow:
        id = "sig_1"
        raw_feedback_id = "rfb_missing"
        summary = "Summary"
        signal_type = "feature"
        evidence = ["Valid quote"]
        confidence = 0.8

    async def mock_get(model, id_val):
        if model.__name__ == "RequirementAssetRow" and id_val == "req_1":
            return MockRequirementRow()
        if model.__name__ == "SignalRow" and id_val == "sig_1":
            return MockSignalRow()
        # RawFeedbackRow returns None for rfb_missing
        return None

    mock_session.get.side_effect = mock_get

    report = await validate_evidence_chain("req_1", session=mock_session)

    assert report.requirement_id == "req_1"
    assert report.total_links == 1
    assert report.valid_links == 0
    assert report.is_valid is False
    assert len(report.broken_links) == 1
    assert report.broken_links[0].raw_feedback_id == "rfb_missing"
    assert "RawFeedbackRow not found" in report.broken_links[0].reason


@pytest.mark.asyncio
async def test_empty_evidence_trail():
    """Verify validate_evidence_chain handles empty evidence trail smoothly."""
    mock_session = AsyncMock()

    class MockRequirementRow:
        id = "req_empty"
        title = "Empty Requirement"
        evidence_trail = []

    async def mock_get(model, id_val):
        if model.__name__ == "RequirementAssetRow" and id_val == "req_empty":
            return MockRequirementRow()
        return None

    mock_session.get.side_effect = mock_get

    report = await validate_evidence_chain("req_empty", session=mock_session)

    assert report.requirement_id == "req_empty"
    assert report.total_links == 0
    assert report.valid_links == 0
    assert report.is_valid is True
    assert len(report.broken_links) == 0


@pytest.mark.asyncio
async def test_validate_all_evidence_chains():
    """Verify validate_all_evidence_chains validates all requirements and compiles reports."""
    mock_session = AsyncMock()

    class MockRequirementRow:
        def __init__(self, req_id):
            self.id = req_id
            self.title = "Empty Requirement"
            self.evidence_trail = []

    async def mock_get(model, id_val):
        if model.__name__ == "RequirementAssetRow":
            return MockRequirementRow(id_val)
        return None

    mock_session.get.side_effect = mock_get

    # Mock the query returned by execute
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = ["req_empty_1", "req_empty_2"]
    mock_session.execute = AsyncMock(return_value=mock_result)

    reports = await validate_all_evidence_chains(session=mock_session)

    assert len(reports) == 2
    assert reports[0].requirement_id == "req_empty_1"
    assert reports[0].total_links == 0
    assert reports[0].is_valid is True
    assert reports[1].requirement_id == "req_empty_2"
    assert reports[1].total_links == 0
    assert reports[1].is_valid is True
