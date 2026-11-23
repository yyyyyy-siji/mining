"""P12-2 站点级真实采集适配器合约测试。

覆盖：
- GitHub issue/comment 转证据包（保留 html_url）
- 博客园文章 JSON/URL 转证据包（保留 cnblogs.com URL）
- B 站手工视频样本转证据包（保留 bilibili.com/video/...）
- Google/Baidu 搜索结果使用落地页 URL，拒绝搜索结果列表页
- browser_screenshot 无 screenshot_path 且无 source_note 时拒绝
- 证据包转 ingest payload 时调用 P12-1 URL 校验，错域名失败
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from signal_miner.connectors.platforms.bilibili_adapter import BilibiliEvidenceAdapter
from signal_miner.connectors.platforms.cnblogs_adapter import CnblogsEvidenceAdapter
from signal_miner.connectors.platforms.generic_adapter import GenericEvidenceAdapter
from signal_miner.connectors.platforms.github_adapter import GitHubEvidenceAdapter
from signal_miner.connectors.platforms.search_adapter import SearchEvidenceAdapter
from signal_miner.connectors.source_acquisition import (
    AcquisitionEvidence,
    EvidencePackageError,
    batch_to_ingest_payloads,
)

# =========================================================================
# GitHub 适配器
# =========================================================================


def test_github_issue_to_evidence_preserves_html_url():
    """GitHub issue JSON 转证据包，external_url 保留 html_url。"""
    issue = {
        "html_url": "https://github.com/openai/codex/issues/1",
        "title": "Support streaming responses",
        "body": "The API should support streaming for long responses.",
        "user": {"login": "dev_user"},
        "created_at": "2024-01-15T10:30:00Z",
    }

    ev = GitHubEvidenceAdapter.from_issue(issue, source_note="API 拉取")

    assert ev.source_type == "github"
    assert ev.external_url == "https://github.com/openai/codex/issues/1"
    assert ev.capture_method == "official_api"
    assert ev.text == "The API should support streaming for long responses."
    assert ev.subject == "Support streaming responses"
    assert ev.author_name == "dev_user"
    assert ev.source_note == "API 拉取"
    assert ev.source_captured_at is not None
    assert ev.raw_payload is issue


def test_github_comment_to_evidence_preserves_html_url():
    """GitHub comment JSON 转证据包，保留 comment 的 html_url。"""
    issue = {
        "html_url": "https://github.com/openai/codex/issues/1",
        "title": "Support streaming",
    }
    comment = {
        "html_url": "https://github.com/openai/codex/issues/1#issuecomment-123456",
        "body": "I agree, this is critical for UX.",
        "user": {"login": "reviewer"},
        "created_at": "2024-01-16T08:00:00Z",
    }

    ev = GitHubEvidenceAdapter.from_comment(issue, comment)

    assert ev.source_type == "github"
    assert ev.external_url == "https://github.com/openai/codex/issues/1#issuecomment-123456"
    assert ev.capture_method == "official_api"
    assert "I agree" in ev.text
    assert ev.author_name == "reviewer"


def test_github_issue_missing_html_url_raises():
    """缺少 html_url 的 issue 抛出 EvidencePackageError。"""
    issue = {"title": "No URL", "body": "missing html_url"}
    with pytest.raises(EvidencePackageError, match="html_url"):
        GitHubEvidenceAdapter.from_issue(issue)


# =========================================================================
# 博客园适配器
# =========================================================================


def test_cnblogs_from_api_json_preserves_url():
    """博客园 API JSON 转证据包，保留 cnblogs.com URL。"""
    article = {
        "Url": "https://www.cnblogs.com/someone/p/12345.html",
        "Title": "Python 异步编程最佳实践",
        "Description": "详细介绍 asyncio 的使用方法和注意事项。",
        "Author": "tech_blogger",
        "DateAdded": "2024-03-01T12:00:00",
    }

    ev = CnblogsEvidenceAdapter.from_api_json(article)

    assert ev.source_type == "cnblogs"
    assert ev.external_url == "https://www.cnblogs.com/someone/p/12345.html"
    assert ev.capture_method == "official_api"
    assert ev.subject == "Python 异步编程最佳实践"
    assert "asyncio" in ev.text
    assert ev.author_name == "tech_blogger"


def test_cnblogs_from_url_and_text():
    """博客园 URL + 文本直接构造证据包。"""
    ev = CnblogsEvidenceAdapter.from_url_and_text(
        url="https://www.cnblogs.com/author/p/999.html",
        text="这篇文章讲得很清楚",
        subject="好文章",
        author_name="reader",
        capture_method="manual_browser",
    )

    assert ev.source_type == "cnblogs"
    assert ev.external_url == "https://www.cnblogs.com/author/p/999.html"
    assert ev.text == "这篇文章讲得很清楚"


# =========================================================================
# B 站适配器
# =========================================================================


def test_bilibili_video_sample_preserves_bv_url():
    """B 站视频样本转证据包，保留 bilibili.com/video/ URL。"""
    bv_url = "https://www.bilibili.com/video/BV1xx411c7mD"

    ev = BilibiliEvidenceAdapter.from_video_sample(
        bv_url=bv_url,
        text="开场三秒反转抓眼球，评论区都说一集封神",
        subject="【年度最佳】三秒封神的神反转短片",
        author_name="UP主小王",
        capture_method="crawler",
        source_note="公开页面评论区采集",
        views=120000,
        likes=8500,
    )

    assert ev.source_type == "video_bilibili"
    assert ev.external_url == bv_url
    assert ev.video_url == bv_url
    assert ev.capture_method == "crawler"
    assert ev.subject == "【年度最佳】三秒封神的神反转短片"
    assert ev.author_name == "UP主小王"
    assert ev.views == 120000
    assert ev.likes == 8500
    assert ev.platform == "bilibili"


def test_bilibili_comment_preserves_video_page_url():
    """B 站评论证据包，external_url 使用视频页 URL。"""
    bv_url = "https://www.bilibili.com/video/BV1xx411c7mD"

    ev = BilibiliEvidenceAdapter.from_comment(
        bv_url=bv_url,
        comment_text="这个转场太丝滑了！！求教程！",
        comment_author="热心网友A",
    )

    assert ev.source_type == "bilibili"
    assert ev.external_url == bv_url
    assert "转场" in ev.text
    assert ev.author_name == "热心网友A"


# =========================================================================
# 搜索引擎适配器
# =========================================================================


def test_google_search_result_uses_landing_page_url():
    """Google 搜索结果使用落地页 URL，不用搜索列表页。"""
    result = {
        "link": "https://github.com/openai/codex/issues/1",
        "title": "Support streaming responses",
        "snippet": "The API should support streaming for long-running operations.",
    }

    ev = SearchEvidenceAdapter.from_search_result(result, engine="google")

    assert ev.source_type == "google_search"
    assert ev.external_url == "https://github.com/openai/codex/issues/1"
    assert "streaming" in ev.text


def test_baidu_search_result_uses_landing_page_url():
    """百度搜索结果使用落地页 URL。"""
    result = {
        "url": "https://www.cnblogs.com/author/p/12345.html",
        "title": "Python 异步编程",
        "description": "深入理解 asyncio",
    }

    ev = SearchEvidenceAdapter.from_search_result(result, engine="baidu")

    assert ev.source_type == "baidu_search"
    assert ev.external_url == "https://www.cnblogs.com/author/p/12345.html"


def test_search_result_landing_page_url_passes_p12_1_validation():
    """落地页 URL 通过 validate_required_source_url。"""
    ev = AcquisitionEvidence(
        source_type="google_search",
        external_url="https://github.com/openai/codex/issues/1",
        capture_method="official_api",
        text="test",
    )

    # 转换为 ingest payload 应成功（不抛异常）
    payload = ev.to_ingest_payload()
    assert payload["external_url"] == "https://github.com/openai/codex/issues/1"


def test_search_result_rejects_search_list_page_url():
    """搜索结果列表页 URL 被 P12-1 拦截。"""
    ev = AcquisitionEvidence(
        source_type="google_search",
        external_url="https://www.google.com/search?q=aigc",
        capture_method="official_api",
        text="test",
    )

    with pytest.raises(EvidencePackageError, match="落地页"):
        ev.to_ingest_payload()


def test_search_result_missing_landing_page_url_raises():
    """搜索结果缺少落地页 URL 时抛出 EvidencePackageError。"""
    result = {"title": "No URL", "snippet": "nothing"}
    with pytest.raises(EvidencePackageError, match="落地页"):
        SearchEvidenceAdapter.from_search_result(result, engine="google")


def test_search_result_batch_rejects_invalid_item():
    """批量搜索结果遇到缺 URL 条目时抛出 EvidencePackageError。"""
    results = [
        {"link": "https://github.com/a/b", "title": "Valid", "snippet": "ok"},
        {"title": "No URL", "snippet": "bad"},  # 没有 link
        {"link": "https://github.com/c/d", "title": "Also valid", "snippet": "yes"},
    ]
    with pytest.raises(EvidencePackageError, match="第 2 条"):
        SearchEvidenceAdapter.from_search_results_batch(results, engine="google")


# =========================================================================
# browser_screenshot 防御
# =========================================================================


def test_browser_screenshot_without_path_or_note_rejected():
    """browser_screenshot 无 screenshot_path 且无 source_note 时，validate() 拒绝。"""
    ev = AcquisitionEvidence(
        source_type="manual",
        external_url="https://www.douyin.com/video/123",
        capture_method="browser_screenshot",
        text="test",
        # 既没有 screenshot_path 也没有 source_note
    )
    with pytest.raises(EvidencePackageError, match="screenshot_path"):
        ev.validate()


def test_browser_screenshot_with_screenshot_path_accepted():
    """browser_screenshot 有 screenshot_path 时通过构造，可通过 validate。"""
    ev = AcquisitionEvidence(
        source_type="douyin",
        external_url="https://www.douyin.com/video/123456",
        capture_method="browser_screenshot",
        text="test content",
        screenshot_path="/tmp/screenshots/douyin_123456.png",
    )
    # 不应抛异常
    ev.validate()


def test_browser_screenshot_with_source_note_accepted():
    """browser_screenshot 有 source_note 时通过校验。"""
    ev = AcquisitionEvidence(
        source_type="douyin",
        external_url="https://www.douyin.com/video/123456",
        capture_method="browser_screenshot",
        text="test content",
        source_note="截图取自 2024-06-01 抖音评论区",
    )
    ev.validate()


def test_browser_screenshot_validate_rejects_missing_both():
    """validate() 方法在 browser_screenshot 缺少截图路径和备注时抛出。"""
    ev = AcquisitionEvidence(
        source_type="douyin",
        external_url="https://www.douyin.com/video/123456",
        capture_method="browser_screenshot",
        text="test content",
    )
    with pytest.raises(EvidencePackageError, match="screenshot_path"):
        ev.validate()


# =========================================================================
# P12-1 URL 校验集成
# =========================================================================


def test_evidence_to_ingest_payload_calls_p12_1_validation():
    """证据包转 ingest payload 时调用 P12-1 validate_required_source_url。"""
    ev = AcquisitionEvidence(
        source_type="github",
        external_url="https://github.com/openai/codex/issues/1",
        capture_method="official_api",
        text="test",
    )
    payload = ev.to_ingest_payload()
    assert payload["source_type"] == "github"
    assert payload["external_url"] == "https://github.com/openai/codex/issues/1"
    assert payload["capture_method"] == "official_api"
    assert payload["text"] == "test"


def test_evidence_wrong_domain_fails_p12_1():
    """平台域名不匹配时转换失败。"""
    ev = AcquisitionEvidence(
        source_type="video_bilibili",
        external_url="https://www.douyin.com/video/123456",
        capture_method="crawler",
        text="test",
    )
    with pytest.raises(EvidencePackageError, match="哔哩哔哩"):
        ev.to_ingest_payload()


def test_evidence_placeholder_url_fails_p12_1():
    """example.com 占位 URL 被 P12-1 拦截。"""
    ev = AcquisitionEvidence(
        source_type="manual",
        external_url="https://example.com/test",
        capture_method="manual_browser",
        text="test",
    )
    with pytest.raises(EvidencePackageError, match="example"):
        ev.to_ingest_payload()


def test_evidence_missing_url_fails_p12_1():
    """空 URL 被 P12-1 拦截。"""
    with pytest.raises(EvidencePackageError):
        AcquisitionEvidence(
            source_type="manual",
            external_url="",
            capture_method="manual_browser",
            text="test",
        )


# =========================================================================
# batch_to_ingest_payloads
# =========================================================================


def test_batch_to_ingest_payloads_converts_all():
    """批量证据包全部转换为 ingest payload。"""
    evidence_list = [
        AcquisitionEvidence(
            source_type="github",
            external_url="https://github.com/a/b/issues/1",
            capture_method="official_api",
            text="First item",
        ),
        AcquisitionEvidence(
            source_type="cnblogs",
            external_url="https://www.cnblogs.com/x/p/1.html",
            capture_method="manual_browser",
            text="Second item",
        ),
    ]
    payloads = batch_to_ingest_payloads(evidence_list)
    assert len(payloads) == 2
    assert payloads[0]["source_type"] == "github"
    assert payloads[1]["source_type"] == "cnblogs"


def test_batch_fails_if_any_item_invalid():
    """批量转换中任一项不合法立即抛出。"""
    evidence_list = [
        AcquisitionEvidence(
            source_type="github",
            external_url="https://github.com/a/b/issues/1",
            capture_method="official_api",
            text="Valid",
        ),
        AcquisitionEvidence(
            source_type="video_bilibili",
            external_url="https://www.douyin.com/video/123",
            capture_method="crawler",
            text="Wrong domain",
        ),
    ]
    with pytest.raises(EvidencePackageError, match="哔哩哔哩"):
        batch_to_ingest_payloads(evidence_list)


# =========================================================================
# 通用适配器
# =========================================================================


def test_generic_adapter_from_dict_maps_fields():
    """GenericEvidenceAdapter 正确映射字段。"""
    item = {
        "external_url": "https://www.zhihu.com/question/123",
        "source_type": "zhihu",
        "capture_method": "crawler",
        "text": "这个问题很有价值",
        "subject": "How to optimize?",
        "author_name": "知乎用户A",
    }
    ev = GenericEvidenceAdapter.from_dict(item)
    assert ev.source_type == "zhihu"
    assert ev.external_url == "https://www.zhihu.com/question/123"
    assert ev.text == "这个问题很有价值"
    assert ev.subject == "How to optimize?"


def test_generic_adapter_fallback_url_fields():
    """当 external_url 缺失时，回退到 source_url / url / video_url / link。"""
    item = {"url": "https://example.org/post", "source_type": "manual", "text": "test"}
    ev = GenericEvidenceAdapter.from_dict(item)
    assert ev.external_url == "https://example.org/post"


def test_generic_adapter_missing_all_urls_raises():
    """所有 URL 字段为空时抛出。"""
    item = {"source_type": "manual", "text": "no url"}
    with pytest.raises(EvidencePackageError, match="external_url"):
        GenericEvidenceAdapter.from_dict(item)


def test_generic_adapter_batch_rejects_invalid_item():
    """批量通用适配器遇到缺 URL 条目时抛出 EvidencePackageError。"""
    items = [
        {"external_url": "https://a.com/1", "source_type": "manual", "text": "ok1"},
        {"source_type": "manual", "text": "no url"},
        {"external_url": "https://a.com/2", "source_type": "manual", "text": "ok2"},
    ]
    with pytest.raises(EvidencePackageError, match="第 2 条"):
        GenericEvidenceAdapter.from_dicts_batch(items)


# =========================================================================
# P12-2 返修3：路由级 browser_screenshot 约束 + 证据字段入库
# =========================================================================


def _make_feedback_test_app() -> TestClient:
    """Build minimal FastAPI app with feedback router for route-level tests."""
    from signal_miner.routes.feedback import router as feedback_router

    app = FastAPI()
    app.include_router(feedback_router, prefix="/api/v1")
    return TestClient(app)


@pytest.fixture
def mock_runner():
    """Mock pipeline.runner.ingest_feedback to return a fake ID."""
    return AsyncMock(return_value="rfb_test")


# ── 路由级 browser_screenshot 拒绝 ──────────────────────────────────────


def test_ingest_rejects_browser_screenshot_without_evidence(mock_runner):
    """POST /feedback/ingest browser_screenshot 缺 screenshot_path + source_note → 422."""
    client = _make_feedback_test_app()
    payload = {
        "source_type": "douyin",
        "text": "test content",
        "external_url": "https://www.douyin.com/video/123456",
        "capture_method": "browser_screenshot",
    }

    with patch("signal_miner.pipeline.runner.ingest_feedback", mock_runner):
        response = client.post("/api/v1/feedback/ingest", json=payload)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "screenshot_path" in detail.lower() or "source_note" in detail.lower()
    mock_runner.assert_not_awaited()


def test_batch_rejects_browser_screenshot_without_evidence(mock_runner):
    """POST /feedback/batch browser_screenshot 缺截图证据 → 422，含 index。"""
    client = _make_feedback_test_app()
    items = [
        {
            "source_type": "github",
            "text": "valid item",
            "external_url": "https://github.com/a/b/issues/1",
            "capture_method": "official_api",
        },
        {
            "source_type": "douyin",
            "text": "bad item — no screenshot evidence",
            "external_url": "https://www.douyin.com/video/123456",
            "capture_method": "browser_screenshot",
        },
    ]

    with patch("signal_miner.pipeline.runner.ingest_feedback", mock_runner):
        response = client.post("/api/v1/feedback/batch", json=items)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "第 2 条" in detail
    mock_runner.assert_not_awaited()


def test_ingest_accepts_browser_screenshot_with_screenshot_path(mock_runner):
    """POST /feedback/ingest browser_screenshot 有 screenshot_path → 201。"""
    client = _make_feedback_test_app()
    payload = {
        "source_type": "douyin",
        "text": "test content",
        "external_url": "https://www.douyin.com/video/123456",
        "capture_method": "browser_screenshot",
        "screenshot_path": "/tmp/screenshots/douyin_123.png",
    }

    with patch("signal_miner.pipeline.runner.ingest_feedback", mock_runner):
        response = client.post("/api/v1/feedback/ingest", json=payload)

    assert response.status_code == 201
    mock_runner.assert_awaited_once()

    data = mock_runner.await_args.args[0]
    assert data["context"]["screenshot_path"] == "/tmp/screenshots/douyin_123.png"


def test_ingest_accepts_browser_screenshot_with_source_note(mock_runner):
    """POST /feedback/ingest browser_screenshot 有 source_note → 201。"""
    client = _make_feedback_test_app()
    payload = {
        "source_type": "douyin",
        "text": "test content",
        "external_url": "https://www.douyin.com/video/123456",
        "capture_method": "browser_screenshot",
        "source_note": "截图取自 2024-06-01 抖音评论区",
    }

    with patch("signal_miner.pipeline.runner.ingest_feedback", mock_runner):
        response = client.post("/api/v1/feedback/ingest", json=payload)

    assert response.status_code == 201
    mock_runner.assert_awaited_once()

    data = mock_runner.await_args.args[0]
    assert data["context"]["source_note"] == "截图取自 2024-06-01 抖音评论区"


def test_ingest_persists_screenshot_path_to_context(mock_runner):
    """screenshot_path 被写入 context 并传递给 pipeline。"""
    client = _make_feedback_test_app()
    payload = {
        "source_type": "github",
        "text": "issue body",
        "external_url": "https://github.com/a/b/issues/1",
        "capture_method": "official_api",
        "screenshot_path": "/tmp/gh-screen.png",
    }

    with patch("signal_miner.pipeline.runner.ingest_feedback", mock_runner):
        response = client.post("/api/v1/feedback/ingest", json=payload)

    assert response.status_code == 201
    data = mock_runner.await_args.args[0]
    assert data["context"]["screenshot_path"] == "/tmp/gh-screen.png"


def test_ingest_persists_ocr_text_to_context(mock_runner):
    """ocr_text 被写入 context 并传递给 pipeline。"""
    client = _make_feedback_test_app()
    payload = {
        "source_type": "douyin",
        "text": "text from screenshot",
        "external_url": "https://www.douyin.com/video/123456",
        "capture_method": "browser_screenshot",
        "screenshot_path": "/tmp/dy.png",
        "ocr_text": "OCR: 这个产品不错，推荐购买",
    }

    with patch("signal_miner.pipeline.runner.ingest_feedback", mock_runner):
        response = client.post("/api/v1/feedback/ingest", json=payload)

    assert response.status_code == 201
    data = mock_runner.await_args.args[0]
    assert data["context"]["ocr_text"] == "OCR: 这个产品不错，推荐购买"
    assert data["context"]["screenshot_path"] == "/tmp/dy.png"


def test_ingest_omits_none_screenshot_and_ocr_from_context(mock_runner):
    """不传 screenshot_path/ocr_text 时 context 不含对应键。"""
    client = _make_feedback_test_app()
    payload = {
        "source_type": "github",
        "text": "normal feedback",
        "external_url": "https://github.com/a/b/issues/1",
        "capture_method": "official_api",
    }

    with patch("signal_miner.pipeline.runner.ingest_feedback", mock_runner):
        response = client.post("/api/v1/feedback/ingest", json=payload)

    assert response.status_code == 201
    data = mock_runner.await_args.args[0]
    assert "screenshot_path" not in data["context"]
    assert "ocr_text" not in data["context"]
