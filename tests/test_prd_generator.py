"""Tests for the PRD generator module."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from signal_miner.pipeline.prd_generator import (
    _format_acceptance_criteria,
    _format_evidence_trail,
    _format_user_stories_table,
    generate_prd_for_requirement,
)

# ---------------------------------------------------------------------------
# Unit tests for formatting helpers
# ---------------------------------------------------------------------------

def test_format_user_stories_table_with_stories():
    """Format user stories as a Markdown table."""
    stories = [
        {"role": "管理员", "action": "导出报告", "benefit": "分享给团队"},
        {"role": "普通用户", "action": "切换暗色模式", "benefit": "保护眼睛"},
    ]
    result = _format_user_stories_table(stories)
    assert "| 角色 | 行为 | 价值 |" in result
    assert "| 管理员 | 导出报告 | 分享给团队 |" in result
    assert "| 普通用户 | 切换暗色模式 | 保护眼睛 |" in result


def test_format_user_stories_table_empty():
    """Format empty user stories returns placeholder."""
    result = _format_user_stories_table([])
    assert "无用户故事" in result


def test_format_acceptance_criteria_with_items():
    """Format acceptance criteria as a numbered list."""
    criteria = [
        "Given 用户已登录, When 点击导出按钮, Then PDF 下载开始",
        "Given 导出进行中, When 网络断开, Then 显示错误提示",
    ]
    result = _format_acceptance_criteria(criteria)
    assert "1. Given 用户已登录" in result
    assert "2. Given 导出进行中" in result


def test_format_acceptance_criteria_empty():
    """Format empty acceptance criteria returns placeholder."""
    result = _format_acceptance_criteria([])
    assert "无验收标准" in result


def test_format_evidence_trail_with_entries():
    """Format evidence trail as structured Markdown."""
    trail = [
        {
            "signal_summary": "PDF 导出按钮不工作",
            "quote": "按钮根本点不了，已经试了很多次",
            "source_type": "support_ticket",
            "confidence": 0.92,
            "source_url": "https://github.com/acme/support/issues/123",
        },
        {
            "signal_summary": "需要暗色模式",
            "quote": "晚上用太刺眼了",
            "source_type": "feature_request",
            "confidence": 0.75,
        },
    ]
    result = _format_evidence_trail(trail)
    assert "**证据 1**:" in result
    assert "PDF 导出按钮不工作" in result
    assert "按钮根本点不了" in result
    assert "support_ticket" in result
    assert "**证据 2**:" in result
    assert "需要暗色模式" in result
    # Verify source_url → Markdown link, and no misleading output for entries without link
    assert "[打开原始来源](https://github.com/acme/support/issues/123)" in result
    # Evidence 2 has no source_url → no "来源链接" line and no "None" leakage
    evidence_2_start = result.find("**证据 2**:")
    evidence_2_block = result[evidence_2_start:]
    assert "来源链接" not in evidence_2_block
    assert "None" not in evidence_2_block


def test_format_evidence_trail_empty():
    """Format empty evidence trail returns placeholder."""
    result = _format_evidence_trail([])
    assert "无证据链记录" in result


# ---------------------------------------------------------------------------
# Integration tests for generate_prd_for_requirement
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_prd_requirement_not_found():
    """Verify ValueError is raised when requirement is not found."""
    mock_session = AsyncMock()
    mock_session.get = AsyncMock(return_value=None)

    mock_session_factory = MagicMock()
    mock_session_factory_context = MagicMock()
    mock_session_factory_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory_context.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_session_factory_context

    mock_llm = MagicMock()

    with patch(
        "signal_miner.pipeline.prd_generator.get_session_factory",
        return_value=mock_session_factory,
    ), pytest.raises(ValueError, match="not found"):
        await generate_prd_for_requirement("nonexistent_id", mock_llm)


@pytest.mark.asyncio
async def test_generate_prd_success():
    """Verify successful PRD generation with a mock LLM."""
    expected_prd = """# 测试需求

## 概述
这是一份测试 PRD。

## 用户故事
测试用户故事。

## 证据链
测试证据。
"""

    # Build mock requirement row
    mock_req = MagicMock()
    mock_req.id = "req_test_1"
    mock_req.title = "测试需求"
    mock_req.user_stories = [
        {"role": "测试者", "action": "生成 PRD", "benefit": "验证流程"}
    ]
    mock_req.acceptance_criteria = ["Given 系统就绪, When 调用生成, Then 返回 PRD"]
    mock_req.impact = {
        "user_impact": "方便用户",
        "business_impact": "提升效率",
        "estimated_reach": "所有用户",
    }
    mock_req.priority = {"composite": 0.8}
    mock_req.decision_reasoning = "测试需求，用于验证 PRD 生成流程"
    mock_req.evidence_trail = [
        {
            "signal_id": "sig_1",
            "raw_feedback_id": "rfb_1",
            "quote": "需要 PRD 生成功能",
            "source_type": "manual",
            "author_segment": "internal",
            "signal_summary": "PRD 生成需求",
            "signal_type": "feature_request",
            "confidence": 0.9,
            "source_url": "https://github.com/acme/app/issues/1",
        },
        {
            "signal_id": "sig_2",
            "quote": "界面按钮不好找",
            "source_type": "app_store_review",
            "external_url": "https://github.com/acme/app/issues/2",
        },
    ]
    mock_req.opportunity_ids = ["opp_1"]
    mock_req.status = "draft"

    # Mock opportunity
    mock_opp = MagicMock()
    mock_opp.jtbd_statement = "当测试时，我想要生成 PRD，以便验证系统"
    mock_opp.description = "测试机会"
    mock_opp.pain_point_ids = ["pp_1"]

    # Mock LLM
    mock_llm = MagicMock()
    mock_llm.call_text = AsyncMock(return_value=expected_prd)
    mock_llm.provider_name = "mock_provider"
    mock_llm.last_usage = {"input_tokens": 500, "output_tokens": 200}

    mock_session = AsyncMock()

    async def mock_get(model, id_val):
        if model.__name__ == "RequirementAssetRow" and id_val == "req_test_1":
            return mock_req
        if model.__name__ == "OpportunityRow" and id_val == "opp_1":
            return mock_opp
        if model.__name__ == "SignalRow" and id_val == "sig_1":
            mock_sig = MagicMock()
            mock_sig.summary = "PRD 生成需求"
            mock_sig.signal_type = "feature_request"
            mock_sig.confidence = 0.9
            return mock_sig
        if model.__name__ == "SignalRow" and id_val == "sig_2":
            mock_sig2 = MagicMock()
            mock_sig2.summary = "界面按钮不好找"
            mock_sig2.signal_type = "usability_issue"
            mock_sig2.confidence = 0.85
            return mock_sig2
        if model.__name__ == "PainPointRow" and id_val == "pp_1":
            mock_pp = MagicMock()
            mock_pp.description = "用户在晚上使用时界面太刺眼"
            mock_pp.severity = "high"
            mock_pp.frequency = "daily"
            return mock_pp
        return None

    mock_session.get.side_effect = mock_get

    mock_session_factory = MagicMock()
    mock_session_factory_context = MagicMock()
    mock_session_factory_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory_context.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_session_factory_context

    with patch(
        "signal_miner.pipeline.prd_generator.get_session_factory",
        return_value=mock_session_factory,
    ), patch(
        "signal_miner.pipeline.prd_generator.log_pipeline_event",
        new_callable=AsyncMock,
    ) as mock_log:
        result = await generate_prd_for_requirement("req_test_1", mock_llm)

    # Verify result
    assert result == expected_prd

    # Verify prd_content was saved
    assert mock_req.prd_content == expected_prd
    assert mock_req.status == "reviewed"

    # Verify LLM was called with temperature=0.3
    mock_llm.call_text.assert_awaited_once()
    call_prompt = mock_llm.call_text.call_args[0][0]
    llm_call_kwargs = mock_llm.call_text.call_args[1]
    assert llm_call_kwargs["temperature"] == 0.3
    # Prompt: title, user stories, acceptance criteria, evidence (quote / source / confidence)
    assert "测试需求" in call_prompt
    assert "测试者" in call_prompt
    assert "生成 PRD" in call_prompt
    assert "验证流程" in call_prompt
    assert "Given 系统就绪" in call_prompt
    assert "PRD 生成需求" in call_prompt
    assert "需要 PRD 生成功能" in call_prompt
    assert "manual" in call_prompt
    assert "90%" in call_prompt

    # Verify opportunity and pain point enrichment in prompt
    assert "当测试时，我想要生成 PRD，以便验证系统" in call_prompt
    assert "测试机会" in call_prompt
    assert "用户在晚上使用时界面太刺眼" in call_prompt
    assert "high" in call_prompt
    assert "daily" in call_prompt

    # Verify output structure requirements in prompt
    assert "## 关联机会与痛点" in call_prompt
    assert "## 证据链" in call_prompt
    assert "## 决策理由" in call_prompt
    assert "## 风险与假设" in call_prompt

    # Verify source_url and external_url fallback appear in prompt
    assert "[打开原始来源](https://github.com/acme/app/issues/1)" in call_prompt
    assert "[打开原始来源](https://github.com/acme/app/issues/2)" in call_prompt

    # Verify persistence: prd_content, status, updated_at
    assert mock_req.prd_content == expected_prd
    assert mock_req.status == "reviewed"
    assert mock_req.updated_at is not None

    # Verify session.commit was called once
    mock_session.commit.assert_awaited_once()

    # Verify audit log with all required parameters
    mock_log.assert_awaited_once()
    log_kwargs = mock_log.call_args[1]
    assert log_kwargs["event_type"] == "prd.generated"
    assert log_kwargs["pipeline_step"] == "prd_generation"
    assert log_kwargs["signal_id"] == "req_test_1"
    assert log_kwargs["model"] == "mock_provider"
    assert log_kwargs["input_tokens"] == 500
    assert log_kwargs["output_tokens"] == 200
    assert log_kwargs["detail"]["requirement_id"] == "req_test_1"
    assert log_kwargs["detail"]["prd_length"] == len(expected_prd)
    assert log_kwargs["detail"]["evidence_count"] == 2


@pytest.mark.asyncio
async def test_generate_prd_empty_evidence():
    """Verify PRD generation works with empty evidence trail."""
    expected_prd = "# 空证据需求\n\n## 概述\n测试无证据场景。"

    mock_req = MagicMock()
    mock_req.id = "req_no_evidence"
    mock_req.title = "空证据需求"
    mock_req.user_stories = []
    mock_req.acceptance_criteria = []
    mock_req.impact = {}
    mock_req.priority = {}
    mock_req.decision_reasoning = ""
    mock_req.evidence_trail = []
    mock_req.opportunity_ids = []
    mock_req.status = "draft"

    mock_llm = MagicMock()
    mock_llm.call_text = AsyncMock(return_value=expected_prd)
    mock_llm.provider_name = "mock"
    mock_llm.last_usage = {}

    mock_session = AsyncMock()

    async def mock_get(model, id_val):
        if model.__name__ == "RequirementAssetRow" and id_val == "req_no_evidence":
            return mock_req
        return None

    mock_session.get.side_effect = mock_get

    mock_session_factory = MagicMock()
    mock_session_factory_context = MagicMock()
    mock_session_factory_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory_context.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_session_factory_context

    with patch(
        "signal_miner.pipeline.prd_generator.get_session_factory",
        return_value=mock_session_factory,
    ), patch(
        "signal_miner.pipeline.prd_generator.log_pipeline_event",
        new_callable=AsyncMock,
    ):
        result = await generate_prd_for_requirement("req_no_evidence", mock_llm)

    assert result == expected_prd
    assert mock_req.prd_content == expected_prd

    # Verify fallback text for empty opportunities_context
    call_prompt = mock_llm.call_text.call_args[0][0]
    assert "_无关联机会与痛点_" in call_prompt


@pytest.mark.asyncio
async def test_generate_prd_llm_failure_no_commit():
    """Verify LLM exception is converted to RuntimeError and no commit occurs."""
    mock_req = MagicMock()
    mock_req.id = "req_fail_1"
    mock_req.title = "失败测试需求"
    mock_req.user_stories = [
        {"role": "用户", "action": "测试失败", "benefit": "验证错误处理"}
    ]
    mock_req.acceptance_criteria = []
    mock_req.impact = {}
    mock_req.decision_reasoning = "测试 LLM 失败场景"
    mock_req.evidence_trail = []
    mock_req.opportunity_ids = []
    mock_req.status = "draft"

    mock_llm = MagicMock()
    mock_llm.call_text = AsyncMock(side_effect=Exception("LLM service error"))
    mock_llm.provider_name = "mock_provider"

    mock_session = AsyncMock()

    async def mock_get(model, id_val):
        if model.__name__ == "RequirementAssetRow" and id_val == "req_fail_1":
            return mock_req
        return None

    mock_session.get.side_effect = mock_get

    mock_session_factory = MagicMock()
    mock_session_factory_context = MagicMock()
    mock_session_factory_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory_context.__aexit__ = AsyncMock(return_value=None)
    mock_session_factory.return_value = mock_session_factory_context

    with patch(
        "signal_miner.pipeline.prd_generator.get_session_factory",
        return_value=mock_session_factory,
    ), pytest.raises(RuntimeError, match="LLM PRD generation failed"):
        await generate_prd_for_requirement("req_fail_1", mock_llm)

    # Verify no commit was performed
    mock_session.commit.assert_not_awaited()
    # Verify status was NOT updated
    assert mock_req.status == "draft"
