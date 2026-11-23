"""PRD Generator — transforms RequirementAsset into structured Markdown PRD via LLM.

Key feature: full evidence trail is woven into the PRD output so every claim
is traceable back to the original user feedback (signals, quotes, source).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import (
    OpportunityRow,
    PainPointRow,
    RawFeedbackRow,
    RequirementAssetRow,
    SignalRow,
)
from signal_miner.services.audit import log_pipeline_event
from signal_miner.utils.url_templates import resolve_clickable_source_url

if TYPE_CHECKING:
    from signal_miner.llm import BaseLLMAdapter

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# PRD Generation Prompt
# ---------------------------------------------------------------------------

PRD_GENERATION_PROMPT = """你是一位资深产品经理。请基于以下需求资产信息，生成一份专业、排版精美的 Markdown 格式 PRD（产品需求文档）。

## 需求信息

**标题**: {title}
**决策理由**: {decision_reasoning}

### 用户故事
{user_stories}

### 验收标准
{acceptance_criteria}

### 影响分析
- 用户影响: {user_impact}
- 业务影响: {business_impact}
- 预估覆盖: {estimated_reach}

### 关联机会与痛点
{opportunities_context}

### 证据链 (Evidence Trail)
以下是从原始用户反馈中提取的证据，请在 PRD 中引用这些证据来支撑需求分析：
{evidence_trail}

## 输出要求

请生成一份完整的 Markdown PRD，包含以下章节（使用中文）：

1. **# {title}** — 文档标题
2. **## 概述** — 需求背景和核心问题
3. **## 用户故事** — 结构化展示用户故事（表格格式）
4. **## 验收标准** — 编号列表
5. **## 影响分析** — 用户影响、业务影响、预估覆盖
6. **## 关联机会与痛点** — 总结关联 Opportunity 的 JTBD 和描述，以及关联 PainPoint 的描述、严重度和频度
7. **## 证据链** — 列出关键证据，每条证据包含：信号摘要、用户原话（Quote）、来源类型、置信度、来源链接（如有）
8. **## 决策理由** — 为什么这个需求值得优先做
9. **## 风险与假设** — 潜在风险和待验证假设

要求：
- 排版专业、层次清晰、适合产品评审会使用
- 证据链部分必须完整列出所有证据，体现需求的可追溯性
- 直接输出 Markdown，不要包裹在代码块中
"""


def _format_user_stories_table(stories: list[dict]) -> str:
    """Format user stories as a Markdown table."""
    if not stories:
        return "_无用户故事_"

    lines = ["| 角色 | 行为 | 价值 |", "|------|------|------|"]
    for s in stories:
        role = s.get("role", "用户")
        action = s.get("action", "")
        benefit = s.get("benefit", "")
        lines.append(f"| {role} | {action} | {benefit} |")
    return "\n".join(lines)


def _format_acceptance_criteria(criteria: list) -> str:
    """Format acceptance criteria as a numbered list."""
    if not criteria:
        return "_无验收标准_"
    return "\n".join(f"{i+1}. {c}" for i, c in enumerate(criteria))


def _format_evidence_trail(evidence_trail: list[dict]) -> str:
    """Format evidence trail as structured Markdown."""
    if not evidence_trail:
        return "_无证据链记录_"

    lines = []
    for i, entry in enumerate(evidence_trail, 1):
        summary = entry.get("signal_summary", "未知信号")
        quote = entry.get("quote", "无引用")
        source_type = entry.get("source_type", "未知来源")
        confidence = entry.get("confidence", 0.0)
        source_url = entry.get("source_url")

        block = (
            f"**证据 {i}**:\n"
            f"- 信号摘要: {summary}\n"
            f"- 用户原话: 「{quote}」\n"
            f"- 来源: {source_type}\n"
            f"- 置信度: {confidence:.0%}"
        )
        if source_url:
            block += f"\n- 来源链接: [打开原始来源]({source_url})"
        block += "\n"
        lines.append(block)
    return "\n".join(lines)


async def generate_prd_for_requirement(
    requirement_id: str,
    llm: BaseLLMAdapter,
    *,
    temperature: float = 0.3,
) -> str:
    """Generate a structured Markdown PRD for a given RequirementAsset.

    The PRD weaves in the full evidence trail so that every requirement
    claim is traceable back to original user feedback signals.

    Args:
        requirement_id: The ID of the RequirementAssetRow to generate PRD for.
        llm: An LLM adapter instance used for text generation.
        temperature: LLM temperature parameter (default 0.3).

    Returns:
        The generated Markdown PRD string.

    Raises:
        ValueError: If the requirement is not found.
        RuntimeError: If LLM generation fails.
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        # 1. Load the requirement asset
        req_row = await session.get(RequirementAssetRow, requirement_id)
        if not req_row:
            raise ValueError(f"Requirement asset '{requirement_id}' not found")

        # 2. Fetch linked opportunities and their pain points for richer context
        opportunities_context: list[str] = []
        for opp_id in (req_row.opportunity_ids or []):
            opp = await session.get(OpportunityRow, opp_id)
            if opp:
                opp_text = f"- JTBD: {opp.jtbd_statement}\n- 描述: {opp.description}"
                opportunities_context.append(opp_text)

                # Fetch pain points linked to this opportunity
                for pp_id in (opp.pain_point_ids or []):
                    pp = await session.get(PainPointRow, pp_id)
                    if pp:
                        opportunities_context.append(
                            f"  - 痛点: {pp.description} (严重度: {pp.severity}, 频度: {pp.frequency})"
                        )

        # 3. Enrich evidence trail with signal details
        enriched_evidence = []
        for link in (req_row.evidence_trail or []):
            sig_id = link.get("signal_id")
            rfb_id = link.get("raw_feedback_id")
            sig = await session.get(SignalRow, sig_id) if sig_id else None
            rfb = await session.get(RawFeedbackRow, rfb_id) if rfb_id else None
            if rfb:
                source_url = resolve_clickable_source_url(
                    source_type=rfb.source_type,
                    external_id=rfb.external_id,
                    external_url=rfb.external_url,
                    context=rfb.context if isinstance(rfb.context, dict) else {},
                    source_id=rfb.source_id,
                )
            else:
                source_url = resolve_clickable_source_url(
                    source_type=link.get("source_type", ""),
                    external_id=None,
                    external_url=link.get("source_url") or link.get("external_url"),
                    context={},
                )
            enriched_evidence.append({
                "signal_summary": sig.summary if sig else link.get("signal_summary", ""),
                "quote": link.get("quote", ""),
                "source_type": link.get("source_type", ""),
                "confidence": sig.confidence if sig else link.get("confidence", 0.0),
                "signal_type": sig.signal_type if sig else link.get("signal_type", ""),
                "author_segment": link.get("author_segment", ""),
                "source_url": source_url,
            })

        # 4. Build the LLM prompt
        impact = req_row.impact or {}
        opportunities_text = (
            "\n".join(opportunities_context)
            if opportunities_context
            else "_无关联机会与痛点_"
        )
        prompt = PRD_GENERATION_PROMPT.format(
            title=req_row.title,
            decision_reasoning=req_row.decision_reasoning or "无",
            user_stories=_format_user_stories_table(req_row.user_stories or []),
            acceptance_criteria=_format_acceptance_criteria(req_row.acceptance_criteria or []),
            user_impact=impact.get("user_impact", "未指定"),
            business_impact=impact.get("business_impact", "未指定"),
            estimated_reach=impact.get("estimated_reach", "未指定"),
            evidence_trail=_format_evidence_trail(enriched_evidence),
            opportunities_context=opportunities_text,
        )

        # 5. Call LLM to generate PRD
        try:
            prd_markdown = await llm.call_text(prompt, temperature=temperature)
        except Exception as exc:
            logger.error("prd_generation_llm_failed", requirement_id=requirement_id, error=str(exc))
            raise RuntimeError(f"LLM PRD generation failed: {exc}") from exc

        # 6. Persist PRD content and update status
        req_row.prd_content = prd_markdown
        req_row.status = "reviewed"
        req_row.updated_at = datetime.now(timezone.utc)
        await session.commit()

        # 7. Audit log
        try:
            usage = getattr(llm, "last_usage", {})
        except Exception:
            usage = {}
        await log_pipeline_event(
            event_type="prd.generated",
            pipeline_step="prd_generation",
            signal_id=requirement_id,
            model=getattr(llm, "provider_name", "unknown"),
            input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"),
            detail={
                "requirement_id": requirement_id,
                "title": req_row.title,
                "prd_length": len(prd_markdown),
                "evidence_count": len(enriched_evidence),
            },
        )

        logger.info(
            "prd_generated",
            requirement_id=requirement_id,
            title=req_row.title,
            prd_length=len(prd_markdown),
        )

        return prd_markdown
