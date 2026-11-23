"""Tests for the PRD generation API routes.

These tests use httpx.AsyncClient with ASGI transport to test the FastAPI
endpoints directly, validating request/response behaviour and error handling.

NOTE: These tests require pydantic_core to be loadable. If the environment
has code-signing restrictions on pydantic_core, they will not be importable.
In that case, the logic is validated through test_prd_generator.py instead.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

MOCK_PRD_CONTENT = """# 测试 PRD

## 概述
这是一份测试 PRD。

## 用户故事
| 角色 | 行为 | 价值 |
|------|------|------|
| 用户 | 测试 | 验证 |

## 证据链
**证据 1**: PDF 导出功能不可用
"""


def _make_mock_app():
    """Create a minimal FastAPI app with mocked runtime for testing."""
    from fastapi import FastAPI

    from signal_miner.routes.assets import router
    from signal_miner.runtime import AppRuntime

    mock_llm = MagicMock()
    mock_llm.call_text = AsyncMock(return_value=MOCK_PRD_CONTENT)
    mock_llm.provider_name = "test_provider"
    mock_llm.last_usage = {"input_tokens": 100, "output_tokens": 50}

    mock_state_store = MagicMock()
    mock_streamer = MagicMock()

    app = FastAPI()
    app.state.runtime = AppRuntime(
        settings=MagicMock(),
        llm=mock_llm,
        state_store=mock_state_store,
        streamer=mock_streamer,
    )
    app.include_router(router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_FROZEN_NOW = datetime(2026, 6, 25, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def mock_session():
    """Create a mock database session with a valid requirement asset."""
    from unittest.mock import AsyncMock, MagicMock

    session = AsyncMock()

    # Mock requirement row
    mock_req = MagicMock()
    mock_req.id = "req_test_001"
    mock_req.title = "测试需求"
    mock_req.user_stories = [
        {"role": "测试者", "action": "生成 PRD", "benefit": "验证流程"}
    ]
    mock_req.acceptance_criteria = ["Given 系统就绪, When 调用生成, Then 返回 PRD"]
    mock_req.impact = {"user_impact": "方便", "business_impact": "高效", "estimated_reach": "全部"}
    mock_req.priority = {"composite": 0.8}
    mock_req.decision_reasoning = "测试用"
    mock_req.evidence_trail = [
        {
            "signal_id": "sig_1",
            "raw_feedback_id": "rfb_1",
            "quote": "需要 PRD 功能",
            "source_type": "manual",
            "author_segment": "internal",
            "signal_summary": "PRD 生成需求",
            "signal_type": "feature_request",
            "confidence": 0.9,
        }
    ]
    mock_req.opportunity_ids = ["opp_1"]
    mock_req.status = "draft"
    mock_req.prd_content = None
    mock_req.created_at = _FROZEN_NOW
    mock_req.updated_at = _FROZEN_NOW

    session.get = AsyncMock(return_value=mock_req)

    return session


@pytest.fixture
def mock_session_factory(mock_session):
    """Mock the get_session_factory to return a session with mock_req."""
    factory = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=mock_session)
    ctx.__aexit__ = AsyncMock(return_value=None)
    factory.return_value = ctx
    return factory


# ---------------------------------------------------------------------------
# POST /requirements/{req_id}/generate-prd
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_generate_prd_success(mock_session_factory):
    """POST /generate-prd returns 200 with GeneratePRDResponse on success.

    The route handler's own ``get_session_factory`` (for requirement
    validation) is patched via *mock_session_factory*.  The nested call to
    ``generate_prd_for_requirement`` is mocked entirely so we don't need to
    mock its internal ``get_session_factory`` / audit-log DB calls.
    """
    with (
        patch("signal_miner.routes.assets.get_session_factory", return_value=mock_session_factory),
        patch(
            "signal_miner.pipeline.prd_generator.generate_prd_for_requirement",
            new_callable=AsyncMock,
            return_value=MOCK_PRD_CONTENT,
        ),
    ):
        app = _make_mock_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/requirements/req_test_001/generate-prd")

    assert response.status_code == 200
    data = response.json()

    # Required fields with correct types
    assert isinstance(data["requirement_id"], str)
    assert data["requirement_id"] == "req_test_001"
    assert isinstance(data["title"], str)
    assert data["title"] == "测试需求"
    assert isinstance(data["status"], str)
    assert data["status"] == "generated"
    assert isinstance(data["prd_length"], int)
    assert data["prd_length"] == len(MOCK_PRD_CONTENT)
    assert isinstance(data["message"], str)
    assert "generated" in data["message"].lower()


@pytest.mark.asyncio
async def test_post_generate_prd_value_error_returns_404(mock_session_factory):
    """Generator raises ValueError → route returns 404."""
    with (
        patch("signal_miner.routes.assets.get_session_factory", return_value=mock_session_factory),
        patch(
            "signal_miner.pipeline.prd_generator.generate_prd_for_requirement",
            new_callable=AsyncMock,
            side_effect=ValueError("Requirement asset 'bad_id' not found"),
        ),
    ):
        app = _make_mock_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/requirements/req_test_001/generate-prd")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "not found" in detail.lower()


@pytest.mark.asyncio
async def test_post_generate_prd_runtime_error_returns_500(mock_session_factory):
    """Generator raises RuntimeError → route returns 500 with expected phrase."""
    with (
        patch("signal_miner.routes.assets.get_session_factory", return_value=mock_session_factory),
        patch(
            "signal_miner.pipeline.prd_generator.generate_prd_for_requirement",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM PRD generation failed: simulated"),
        ),
    ):
        app = _make_mock_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/requirements/req_test_001/generate-prd")

    assert response.status_code == 500
    detail = response.json()["detail"]
    assert "PRD generation failed" in detail


@pytest.mark.asyncio
async def test_post_generate_prd_not_found(mock_session_factory):
    """POST /generate-prd returns 404 when requirement does not exist."""
    # Override session to return None for the requirement
    not_found_session = AsyncMock()
    not_found_session.get = AsyncMock(return_value=None)
    nf_factory = MagicMock()
    nf_ctx = MagicMock()
    nf_ctx.__aenter__ = AsyncMock(return_value=not_found_session)
    nf_ctx.__aexit__ = AsyncMock(return_value=None)
    nf_factory.return_value = nf_ctx

    with patch(
        "signal_miner.routes.assets.get_session_factory",
        return_value=nf_factory,
    ):
        app = _make_mock_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post("/api/v1/requirements/nonexistent/generate-prd")

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "not found" in detail.lower()


# ---------------------------------------------------------------------------
# GET /requirements/{req_id}/prd
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_prd_markdown_format(mock_session_factory):
    """GET /prd?format=markdown returns Markdown content."""
    # Set prd_content on the mock
    mock_req = mock_session_factory.return_value.__aenter__.return_value.get.return_value
    mock_req.prd_content = MOCK_PRD_CONTENT

    with patch(
        "signal_miner.routes.assets.get_session_factory",
        return_value=mock_session_factory,
    ):
        app = _make_mock_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/requirements/req_test_001/prd",
                params={"format": "markdown"},
            )

    assert response.status_code == 200
    data = response.json()
    # Top-level required fields
    assert isinstance(data["requirement_id"], str)
    assert data["requirement_id"] == "req_test_001"
    assert isinstance(data["title"], str)
    assert data["title"] == "测试需求"
    # Format-specific
    assert data["format"] == "markdown"
    assert isinstance(data["content"], str)
    assert "测试 PRD" in data["content"]


@pytest.mark.asyncio
async def test_get_prd_json_format(mock_session_factory):
    """GET /prd?format=json returns structured JSON with all required fields."""
    mock_req = mock_session_factory.return_value.__aenter__.return_value.get.return_value
    mock_req.prd_content = MOCK_PRD_CONTENT

    with patch(
        "signal_miner.routes.assets.get_session_factory",
        return_value=mock_session_factory,
    ):
        app = _make_mock_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/requirements/req_test_001/prd",
                params={"format": "json"},
            )

    assert response.status_code == 200
    data = response.json()
    # Top-level required fields
    assert isinstance(data["requirement_id"], str)
    assert data["requirement_id"] == "req_test_001"
    assert isinstance(data["title"], str)
    assert data["title"] == "测试需求"
    assert data["format"] == "json"

    content = data["content"]
    assert isinstance(content, dict)

    # All required content keys per instruction
    required_content_keys = {
        "title", "user_stories", "acceptance_criteria",
        "impact", "priority", "decision_reasoning", "evidence_trail",
        "prd_content", "opportunity_ids", "status", "created_at", "updated_at",
    }
    missing = required_content_keys - set(content.keys())
    assert not missing, f"Missing content keys: {missing}"
    assert content["title"] == "测试需求"
    assert isinstance(content["user_stories"], list)
    assert len(content["user_stories"]) == 1
    assert isinstance(content["acceptance_criteria"], list)
    assert len(content["acceptance_criteria"]) == 1
    assert isinstance(content["impact"], dict)
    assert "user_impact" in content["impact"]
    assert isinstance(content["priority"], dict)
    assert isinstance(content["decision_reasoning"], str)
    assert isinstance(content["evidence_trail"], list)
    assert isinstance(content["opportunity_ids"], list)
    assert content["status"] == "draft"
    assert content["prd_content"] == MOCK_PRD_CONTENT
    assert content["created_at"] is not None
    assert content["updated_at"] is not None


@pytest.mark.asyncio
async def test_get_prd_invalid_format(mock_session_factory):
    """GET /prd?format=invalid returns 400 Bad Request."""
    with patch(
        "signal_miner.routes.assets.get_session_factory",
        return_value=mock_session_factory,
    ):
        app = _make_mock_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/requirements/req_test_001/prd",
                params={"format": "pdf"},
            )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "Unsupported format" in detail


@pytest.mark.asyncio
async def test_get_prd_requirement_not_found():
    """GET /prd returns 404 when requirement does not exist."""
    not_found_session = AsyncMock()
    not_found_session.get = AsyncMock(return_value=None)
    nf_factory = MagicMock()
    nf_ctx = MagicMock()
    nf_ctx.__aenter__ = AsyncMock(return_value=not_found_session)
    nf_ctx.__aexit__ = AsyncMock(return_value=None)
    nf_factory.return_value = nf_ctx

    with patch(
        "signal_miner.routes.assets.get_session_factory",
        return_value=nf_factory,
    ):
        app = _make_mock_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/requirements/nonexistent/prd")

    assert response.status_code == 404
