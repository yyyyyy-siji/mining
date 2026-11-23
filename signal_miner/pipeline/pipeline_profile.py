"""Pipeline Profile registry.

Defines `PipelineProfile` dataclass and `PROFILE_REGISTRY` for pluggable
mining pipelines. Each profile bundles its own prompt templates, signal
type enum, and source type whitelist, so that one binary can support
multiple vertical-specific mining modes.

Existing behavior is preserved by `PRODUCT_FEEDBACK_PROFILE`, which
import-references the original prompt constants (no string duplication).
A new `AIGC_VIDEO_PROFILE` adds the AIGC video viral-mining mode
without disturbing the product-feedback mode.

Usage:
    from signal_miner.pipeline.pipeline_profile import get_profile, list_profiles

    profile = get_profile("aigc_video")
    prompt = profile.extraction_prompt_template.format(...)
"""
from __future__ import annotations

from dataclasses import dataclass, field

from signal_miner.pipeline.asset_generator import (
    OPPORTUNITY_PROMPT,
    PAIN_POINT_PROMPT,
    REQUIREMENT_PROMPT,
)
from signal_miner.pipeline.prompts import (
    EXTRACTION_PROMPT,
    QUALITY_GATE_PROMPT,
    VIDEO_EXTRACTION_PROMPT,
    VIDEO_OPPORTUNITY_PROMPT,
    VIDEO_PAIN_POINT_PROMPT,
    VIDEO_QUALITY_GATE_PROMPT,
    VIDEO_REQUIREMENT_PROMPT,
)

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PipelineProfile:
    """Immutable configuration for a single mining pipeline mode.

    All prompt templates are strings; the *build* functions that produce
    the final prompt live next to the templates in `prompts.py` /
    `asset_generator.py`, and are bound at the call site. This dataclass
    only stores the templates themselves, keeping registry lookups cheap.
    """

    name: str
    display_name: str
    display_name_en: str
    signal_types: list[str] = field(default_factory=list)
    extraction_prompt_template: str = ""
    quality_gate_prompt_template: str = ""
    pain_point_prompt_template: str = ""
    opportunity_prompt_template: str = ""
    requirement_prompt_template: str = ""
    source_types: list[str] = field(default_factory=list)
    description: str = ""


# ---------------------------------------------------------------------------
# Pre-registered profiles
# ---------------------------------------------------------------------------

# Original product-feedback mode. Prompt templates are imported (NOT copied)
# from prompts.py / asset_generator.py so that any future prompt edit in the
# source files is reflected immediately. This is the zero-destruction path.
PRODUCT_FEEDBACK_PROFILE = PipelineProfile(
    name="product_feedback",
    display_name="用户反馈挖矿",
    display_name_en="Product Feedback Mining",
    signal_types=[
        "feature_request",
        "bug_report",
        "usability_issue",
        "question",
        "praise",
        "complaint",
        "churn_risk",
    ],
    extraction_prompt_template=EXTRACTION_PROMPT,
    quality_gate_prompt_template=QUALITY_GATE_PROMPT,
    pain_point_prompt_template=PAIN_POINT_PROMPT,
    opportunity_prompt_template=OPPORTUNITY_PROMPT,
    requirement_prompt_template=REQUIREMENT_PROMPT,
    source_types=[
        "manual",
        "support_ticket",
        "app_review",
        "github",
        "weibo",
        "tieba",
        "zhihu",
        "xiaohongshu",
        "csdn",
        "juejin",
        "cnblogs",
        "weixin_mp",
        "baidu_search",
        "sogou_search",
        "so360_search",
        "google_search",
        "bing_search",
        "taobao",
        "tmall",
        "jd",
        "pinduoduo",
        "xianyu",
        "zhuanzhuan",
        "aihuishou",
        "bilibili",
        "csv",
        "json",
        "api",
    ],
    description="多源用户反馈 → 痛点 → 机会 → 需求候选",
)


# AIGC video viral-mining mode. Video-specific signal types replace the
# product-feedback taxonomy. JTBD-style opportunity statements shift
# from "when [user context] I want to [motivation] so I can [outcome]"
# to "当 [创作场景] 时，创作者想 [目标]，以实现 [爆款效果]".
AIGC_VIDEO_PROFILE = PipelineProfile(
    name="aigc_video",
    display_name="AIGC视频爆款挖掘",
    display_name_en="AIGC Video Viral Mining",
    signal_types=[
        "viral_hook",
        "content_pattern",
        "visual_technique",
        "audio_strategy",
        "engagement_trigger",
        "platform_algorithm",
        "topic_trend",
        "monetization_pattern",
    ],
    extraction_prompt_template=VIDEO_EXTRACTION_PROMPT,
    quality_gate_prompt_template=VIDEO_QUALITY_GATE_PROMPT,
    pain_point_prompt_template=VIDEO_PAIN_POINT_PROMPT,
    opportunity_prompt_template=VIDEO_OPPORTUNITY_PROMPT,
    requirement_prompt_template=VIDEO_REQUIREMENT_PROMPT,
    source_types=[
        "video_douyin",
        "video_bilibili",
        "video_xiaohongshu",
        "video_kuaishou",
        "video_youtube",
        "video_youku",
        "video_iqiyi",
        "video_tencent",
        "video_manual",
    ],
    description="AIGC视频数据 → 爆款技巧信号 → 模式聚类 → 创作瓶颈 → 爆款公式 → 创作指南",
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

PROFILE_REGISTRY: dict[str, PipelineProfile] = {
    PRODUCT_FEEDBACK_PROFILE.name: PRODUCT_FEEDBACK_PROFILE,
    AIGC_VIDEO_PROFILE.name: AIGC_VIDEO_PROFILE,
}


def get_profile(name: str) -> PipelineProfile:
    """Look up a profile by name. Raises KeyError if missing.

    Raises:
        KeyError: When `name` is not registered. The error message lists
            all available profiles to aid debugging.
    """
    if name not in PROFILE_REGISTRY:
        available = ", ".join(sorted(PROFILE_REGISTRY.keys()))
        raise KeyError(
            f"Unknown pipeline profile: '{name}'. Available profiles: [{available}]"
        )
    return PROFILE_REGISTRY[name]


def list_profiles() -> list[str]:
    """Return the names of all registered profiles (sorted alphabetically)."""
    return sorted(PROFILE_REGISTRY.keys())


def register_profile(profile: PipelineProfile) -> None:
    """Register a new profile or replace an existing one.

    Useful for tests and third-party extensions. Not frozen because
    registration is an explicit mutation point.
    """
    PROFILE_REGISTRY[profile.name] = profile


__all__ = [
    "AIGC_VIDEO_PROFILE",
    "PROFILE_REGISTRY",
    "PRODUCT_FEEDBACK_PROFILE",
    "PipelineProfile",
    "get_profile",
    "list_profiles",
    "register_profile",
]
