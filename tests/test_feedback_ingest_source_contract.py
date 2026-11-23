"""Trusted source URL contract tests for feedback ingestion routes."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
import pytest

from signal_miner.routes.feedback import IngestRequest, batch_ingest, ingest_feedback
from signal_miner.utils.source_platforms import (
    SourceUrlValidationError,
    validate_required_source_url,
)


@pytest.mark.asyncio
async def test_ingest_accepts_real_platform_url_and_records_provenance_context():
    """A valid platform URL must be passed through as the persisted external_url."""
    request = IngestRequest(
        source_type="video_bilibili",
        pipeline_profile="aigc_video",
        subject="AIGC video sample",
        text="评论说这个开场三秒很抓人",
        external_url="https://www.bilibili.com/video/BV1xx411c7mD",
        video_url="https://www.bilibili.com/video/BV1xx411c7mD",
        capture_method="crawler",
        source_note="公开页面评论区采集",
    )

    mocked_ingest = AsyncMock(return_value="rfb_valid_source")
    with patch("signal_miner.pipeline.runner.ingest_feedback", mocked_ingest):
        response = await ingest_feedback(request)

    assert response.feedback_id == "rfb_valid_source"
    mocked_ingest.assert_awaited_once()

    data = mocked_ingest.await_args.args[0]
    assert data["external_url"] == "https://www.bilibili.com/video/BV1xx411c7mD"
    assert data["context"]["capture_method"] == "crawler"
    assert data["context"]["source_url_required"] is True
    assert data["context"]["source_note"] == "公开页面评论区采集"


@pytest.mark.asyncio
async def test_ingest_rejects_missing_source_url_before_runner_call():
    request = IngestRequest(source_type="manual", text="没有来源的反馈")

    mocked_ingest = AsyncMock(return_value="rfb_should_not_exist")
    with (
        patch("signal_miner.pipeline.runner.ingest_feedback", mocked_ingest),
        pytest.raises(HTTPException) as exc_info,
    ):
        await ingest_feedback(request)

    assert exc_info.value.status_code == 422
    assert "真实来源 URL" in str(exc_info.value.detail)
    mocked_ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_rejects_placeholder_source_url():
    request = IngestRequest(
        source_type="manual",
        text="示例链接不能作为来源",
        external_url="https://example.com/product-feedback-source",
    )

    mocked_ingest = AsyncMock(return_value="rfb_should_not_exist")
    with (
        patch("signal_miner.pipeline.runner.ingest_feedback", mocked_ingest),
        pytest.raises(HTTPException) as exc_info,
    ):
        await ingest_feedback(request)

    assert exc_info.value.status_code == 422
    assert "example" in str(exc_info.value.detail)
    mocked_ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_ingest_rejects_platform_domain_mismatch():
    request = IngestRequest(
        source_type="video_bilibili",
        text="平台和 URL 域名不匹配",
        external_url="https://www.douyin.com/video/123456789",
    )

    mocked_ingest = AsyncMock(return_value="rfb_should_not_exist")
    with (
        patch("signal_miner.pipeline.runner.ingest_feedback", mocked_ingest),
        pytest.raises(HTTPException) as exc_info,
    ):
        await ingest_feedback(request)

    assert exc_info.value.status_code == 422
    assert "哔哩哔哩" in str(exc_info.value.detail)
    mocked_ingest.assert_not_awaited()


@pytest.mark.asyncio
async def test_batch_rejects_invalid_item_before_any_runner_call():
    items = [
        IngestRequest(
            source_type="github",
            text="真实 issue 反馈",
            external_url="https://github.com/openai/codex/issues/1",
        ),
        IngestRequest(source_type="manual", text="第二条没有来源"),
    ]

    mocked_ingest = AsyncMock(return_value="rfb_should_not_exist")
    with (
        patch("signal_miner.pipeline.runner.ingest_feedback", mocked_ingest),
        pytest.raises(HTTPException) as exc_info,
    ):
        await batch_ingest(items)

    assert exc_info.value.status_code == 422
    assert "第 2 条" in str(exc_info.value.detail)
    mocked_ingest.assert_not_awaited()


def test_search_source_requires_result_landing_page_not_search_page():
    with pytest.raises(SourceUrlValidationError, match="落地页"):
        validate_required_source_url(
            "google_search",
            "https://www.google.com/search?q=aigc",
            capture_method="official_api",
        )

    assert validate_required_source_url(
        "google_search",
        "https://github.com/openai/codex/issues/1",
        capture_method="official_api",
    ) == "https://github.com/openai/codex/issues/1"


# =========================================================================
# P12-2 fix-4: source_captured_at / raw_payload 字段入库契约
# =========================================================================


@pytest.mark.asyncio
async def test_ingest_persists_source_captured_at_to_context():
    """source_captured_at 通过 IngestRequest 传入并写入 context。"""
    request = IngestRequest(
        source_type="github",
        text="issue body",
        external_url="https://github.com/a/b/issues/1",
        capture_method="official_api",
        source_captured_at=datetime(2024, 6, 1, 10, 30, 0, tzinfo=timezone.utc),
    )

    mocked_ingest = AsyncMock(return_value="rfb_fix4_captured")
    with patch("signal_miner.pipeline.runner.ingest_feedback", mocked_ingest):
        response = await ingest_feedback(request)

    assert response.feedback_id == "rfb_fix4_captured"
    mocked_ingest.assert_awaited_once()

    data = mocked_ingest.await_args.args[0]
    assert data["context"]["source_captured_at"] == "2024-06-01T10:30:00+00:00"


@pytest.mark.asyncio
async def test_ingest_persists_raw_payload_to_context():
    """raw_payload 通过 IngestRequest 传入并写入 context。"""
    raw = {"html_url": "https://github.com/a/b/issues/1", "title": "test", "user": {"login": "dev"}}
    request = IngestRequest(
        source_type="github",
        text="issue body",
        external_url="https://github.com/a/b/issues/1",
        capture_method="official_api",
        raw_payload=raw,
    )

    mocked_ingest = AsyncMock(return_value="rfb_fix4_raw")
    with patch("signal_miner.pipeline.runner.ingest_feedback", mocked_ingest):
        response = await ingest_feedback(request)

    assert response.feedback_id == "rfb_fix4_raw"
    mocked_ingest.assert_awaited_once()

    data = mocked_ingest.await_args.args[0]
    assert data["context"]["raw_payload"] == raw
    assert data["context"]["raw_payload"]["html_url"] == "https://github.com/a/b/issues/1"


@pytest.mark.asyncio
async def test_ingest_omits_none_source_captured_at_and_raw_payload():
    """不传 source_captured_at / raw_payload 时 context 不含对应键。"""
    request = IngestRequest(
        source_type="github",
        text="normal feedback",
        external_url="https://github.com/a/b/issues/1",
        capture_method="official_api",
    )

    mocked_ingest = AsyncMock(return_value="rfb_fix4_none")
    with patch("signal_miner.pipeline.runner.ingest_feedback", mocked_ingest):
        await ingest_feedback(request)

    data = mocked_ingest.await_args.args[0]
    assert "source_captured_at" not in data["context"]
    assert "raw_payload" not in data["context"]
