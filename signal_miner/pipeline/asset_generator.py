"""Requirement Asset Generator.

Transforms Themes into Pain Points, Opportunities, and Requirement Assets.
Follows PM-Skills methodologies.

Key feature: every generated asset carries a full evidence trail back to
the original user feedback, making requirements traceable and auditable.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import TYPE_CHECKING

from sqlalchemy import select
import structlog

from signal_miner.db import get_session_factory
from signal_miner.db.models import OpportunityRow, PainPointRow, RequirementAssetRow, ThemeRow
from signal_miner.models import new_id
from signal_miner.pipeline.evidence import (
    build_evidence_trail_for_requirement,
    build_supporting_evidence_for_opportunity,
)
from signal_miner.pipeline.utils import strip_code_fences
from signal_miner.services.audit import log_pipeline_event

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from signal_miner.llm import BaseLLMAdapter
    from signal_miner.pipeline.pipeline_profile import PipelineProfile

logger = structlog.get_logger(__name__)

# --- Prompts ---

PAIN_POINT_PROMPT = """You are an expert Product Manager analyzing a recurring Theme in user feedback.
Extract a core "Pain Point" based on the PM-Skills framework.

Theme: {theme_name}
Description: {theme_description}
Representative Quotes: {quotes}

Rules:
- All text fields ("user_segment", "description", "business_impact") MUST be generated in Simplified Chinese (简体中文) only.

Return strict JSON only:
{{
  "user_segment": "Target user segment experiencing this (e.g. '企业管理员', '移动端用户')",
  "description": "Clear, concise description of the pain point",
  "business_impact": "How this pain affects the business (e.g. 导致用户流失, 增加客服反馈压力)",
  "frequency": "rare|occasional|frequent|constant",
  "severity": "low|medium|high|critical"
}}
"""

OPPORTUNITY_PROMPT = """You are an expert Product Manager defining an Opportunity based on a validated Pain Point.
Follow the Jobs-to-be-Done (JTBD) framework.

Pain Point: {pain_description}
Target Segment: {segment}
Business Impact: {impact}

Rules:
- All text fields ("jtbd_statement", "description", "assumptions") MUST be generated in Simplified Chinese (简体中文) only.
- The "jtbd_statement" MUST strictly follow this Chinese JTBD format: "当 [情境] 时，我想 [动机]，以便于 [预期结果]".

Return strict JSON only:
{{
  "jtbd_statement": "当 [情境] 时，我想 [动机]，以便于 [预期结果]",
  "description": "A detailed description of the opportunity",
  "assumptions": ["assumption 1 to test", "assumption 2 to test"]
}}
"""

REQUIREMENT_PROMPT = """You are an expert Product Manager writing a requirement spec based on an Opportunity.

Opportunity: {opportunity_desc}
JTBD: {jtbd}
Pain Point to Solve: {pain_desc}

Rules:
- All text fields ("title", "role", "action", "benefit", "acceptance_criteria", "user_impact", "business_impact", "estimated_reach", "decision_reasoning") MUST be generated in Simplified Chinese (简体中文) only.
- In "user_stories", translate "role", "action", and "benefit" fully to Chinese.
- Write the "acceptance_criteria" using Given/When/Then logic, but fully translate them to Chinese (e.g. "假设... 当... 那么...").

Return strict JSON only:
{{
  "title": "Clear requirement title",
  "user_stories": [
    {{"role": "user role", "action": "what they want to do", "benefit": "why they want it"}}
  ],
  "acceptance_criteria": [
    "AC 1: 假设... 当... 那么...",
    "AC 2: ..."
  ],
  "impact": {{
    "user_impact": "How this improves the user experience",
    "business_impact": "How this helps the business",
    "estimated_reach": "e.g. 所有活跃用户, 仅企业管理员"
  }},
  "decision_reasoning": "Explain WHY this requirement is prioritized based on the original pain point and business impact."
}}
"""

def _clean_json_response(text: str) -> dict:
    """Clean LLM JSON response and parse."""
    return json.loads(strip_code_fences(text))

async def generate_assets_from_themes(
    llm: BaseLLMAdapter,
    profile: PipelineProfile | None = None,
    on_progress: Callable[[str, float, str], Awaitable[None]] | None = None,
    version_id: str | None = None,
) -> dict[str, int]:
    """Generate the full chain of product assets from un-processed Themes.

    Flow: Theme -> PainPoint -> Opportunity -> RequirementAsset

    Each asset is linked to its evidence chain so that any requirement
    can be traced back to the original user feedback.

    Phase 7: when ``profile`` is provided, the profile's pain-point /
    opportunity / requirement prompt templates are used instead of the
    module-level ``PAIN_POINT_PROMPT`` / ``OPPORTUNITY_PROMPT`` /
    ``REQUIREMENT_PROMPT`` constants. When ``profile`` is ``None`` the
    original behavior is preserved.
    """
    # Phase 7: resolve prompt templates from profile (or fall back to
    # module-level constants, which are identical to the product_feedback
    # profile by construction).
    if profile is not None:
        pp_template = profile.pain_point_prompt_template
        opp_template = profile.opportunity_prompt_template
        req_template = profile.requirement_prompt_template
    else:
        pp_template = PAIN_POINT_PROMPT
        opp_template = OPPORTUNITY_PROMPT
        req_template = REQUIREMENT_PROMPT

    session_factory = get_session_factory()
    stats = {"pain_points": 0, "opportunities": 0, "requirements": 0}

    async with session_factory() as session:
        # 1. Fetch draft Themes
        stmt = select(ThemeRow).where(ThemeRow.status == "draft")
        if version_id:
            stmt = stmt.where(ThemeRow.version_id == version_id)
        result = await session.execute(stmt)
        themes = result.scalars().all()

        total_themes = len(themes)
        for idx, theme in enumerate(themes):
            try:
                base_progress = 0.65 + (idx / max(total_themes, 1)) * 0.30
                step_span = 0.30 / max(total_themes, 1)

                # --- Step 1: Pain Point ---
                if on_progress is not None:
                    await on_progress(
                        "pain_point",
                        round(base_progress, 4),
                        f"Theme {idx + 1}/{total_themes} ({theme.name}): 提炼痛点",
                    )
                prompt_pp = pp_template.format(
                    theme_name=theme.name,
                    theme_description=theme.description,
                    quotes=json.dumps(theme.representative_quotes, ensure_ascii=False)
                )
                res_pp = _clean_json_response(await llm.call_structured(prompt_pp))

                theme_version_id = getattr(theme, "version_id", None) or version_id or "default"
                pp_id = new_id("ppn")
                pp_row = PainPointRow(
                    id=pp_id,
                    theme_ids=[theme.id],
                    user_segment=res_pp.get("user_segment", ""),
                    description=res_pp.get("description", ""),
                    frequency=res_pp.get("frequency", "occasional"),
                    severity=res_pp.get("severity", "medium"),
                    business_impact=res_pp.get("business_impact", ""),
                    evidence_signal_ids=theme.signal_ids or [],
                    evidence_quotes=theme.representative_quotes or [],
                    status="draft",
                    version_id=theme_version_id,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                session.add(pp_row)
                await session.flush()  # Ensure pp_row is visible for evidence queries
                stats["pain_points"] += 1

                # --- Step 2: Opportunity (with supporting evidence) ---
                if on_progress is not None:
                    await on_progress(
                        "opportunity",
                        round(base_progress + step_span * 0.35, 4),
                        f"Theme {idx + 1}/{total_themes} ({theme.name}): 生成机会卡片",
                    )
                prompt_opp = opp_template.format(
                    pain_description=pp_row.description,
                    segment=pp_row.user_segment,
                    impact=pp_row.business_impact
                )
                res_opp = _clean_json_response(await llm.call_structured(prompt_opp))

                # Build supporting evidence from the pain point's signals
                supporting_evidence = await build_supporting_evidence_for_opportunity([pp_id], session=session)

                opp_id = new_id("opp")
                opp_row = OpportunityRow(
                    id=opp_id,
                    pain_point_ids=[pp_id],
                    jtbd_statement=res_opp.get("jtbd_statement", ""),
                    description=res_opp.get("description", ""),
                    supporting_evidence=[item.model_dump() for item in supporting_evidence],
                    assumptions=res_opp.get("assumptions", []),
                    priority={"composite": 0.5},
                    status="draft",
                    version_id=theme_version_id,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                session.add(opp_row)
                await session.flush()
                stats["opportunities"] += 1

                # --- Step 3: Requirement Asset (with full evidence trail) ---
                if on_progress is not None:
                    await on_progress(
                        "requirement",
                        round(base_progress + step_span * 0.70, 4),
                        f"Theme {idx + 1}/{total_themes} ({theme.name}): 生成需求资产",
                    )
                prompt_req = req_template.format(
                    opportunity_desc=opp_row.description,
                    jtbd=opp_row.jtbd_statement,
                    pain_desc=pp_row.description
                )
                res_req = _clean_json_response(await llm.call_structured(prompt_req))

                # Build full evidence trail: Requirement → Opportunity → PainPoint → Signal → RawFeedback
                evidence_trail = await build_evidence_trail_for_requirement([opp_id], session=session)

                req_id = new_id("req")
                req_row = RequirementAssetRow(
                    id=req_id,
                    opportunity_ids=[opp_id],
                    title=res_req.get("title", "Untitled Requirement"),
                    user_stories=res_req.get("user_stories", []),
                    acceptance_criteria=res_req.get("acceptance_criteria", []),
                    impact=res_req.get("impact", {}),
                    priority={"composite": 0.5},
                    decision_reasoning=res_req.get("decision_reasoning", ""),
                    evidence_trail=[item.model_dump() for item in evidence_trail],
                    status="draft",
                    version_id=theme_version_id,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
                session.add(req_row)
                stats["requirements"] += 1

                # Update Theme status
                theme.status = "reviewed"
                theme.updated_at = datetime.now(timezone.utc)

                logger.info(
                    "asset_chain_generated",
                    theme_id=theme.id,
                    pain_point_id=pp_id,
                    opportunity_id=opp_id,
                    requirement_id=req_id,
                    evidence_count=len(evidence_trail),
                )

            except Exception as e:
                logger.error("asset_generation_failed", theme_id=theme.id, error=str(e))
                continue

        if sum(stats.values()) > 0:
            await session.commit()
            await log_pipeline_event(
                event_type="assets.generated",
                pipeline_step="asset_generation",
                detail=stats
            )

    return stats
