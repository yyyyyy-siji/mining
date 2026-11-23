"""Common types, enums, and ID helpers used across the SignalMiner domain."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated
import uuid

from pydantic import Field

# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------

def new_id(prefix: str = "") -> str:
    """Generate a prefixed UUID-based identifier."""
    uid = uuid.uuid4().hex[:20]
    return f"{prefix}_{uid}" if prefix else uid


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SignalType(str, Enum):
    """Types of product signals that can be extracted from raw feedback.

    Original product-feedback taxonomy is preserved. AIGC-video viral-mining
    mode adds 8 new signal types (see ``aigc_video`` profile).
    """

    # --- Product feedback taxonomy (preserved) ---
    FEATURE_REQUEST = "feature_request"
    BUG_REPORT = "bug_report"
    USABILITY_ISSUE = "usability_issue"
    QUESTION = "question"
    PRAISE = "praise"
    COMPLAINT = "complaint"
    CHURN_RISK = "churn_risk"

    # --- AIGC video viral-mining taxonomy (Phase 7, additive only) ---
    VIRAL_HOOK = "viral_hook"                    # 开头钩子
    CONTENT_PATTERN = "content_pattern"          # 内容模式
    VISUAL_TECHNIQUE = "visual_technique"        # 视觉技巧
    AUDIO_STRATEGY = "audio_strategy"            # 音频策略
    ENGAGEMENT_TRIGGER = "engagement_trigger"    # 互动触发
    PLATFORM_ALGORITHM = "platform_algorithm"    # 平台算法适配
    TOPIC_TREND = "topic_trend"                  # 话题趋势
    MONETIZATION_PATTERN = "monetization_pattern"  # 变现模式


class ProcessingState(str, Enum):
    """Processing state machine for feedback items and signals."""

    PENDING = "pending"
    READY_FOR_EXTRACTION = "ready_for_extraction"
    EXTRACTING = "extracting"
    INTERPRETING = "interpreting"
    COMPLETED = "completed"
    FAILED = "failed"
    DISMISSED = "dismissed"


class AssetStatus(str, Enum):
    """Lifecycle status for generated requirement assets."""

    DRAFT = "draft"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    DEFERRED = "deferred"
    REJECTED = "rejected"


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Frequency(str, Enum):
    RARE = "rare"
    OCCASIONAL = "occasional"
    FREQUENT = "frequent"
    CONSTANT = "constant"


class PipelineStep(str, Enum):
    """Named steps within the mining pipeline."""

    QUALITY_GATE = "quality_gate"
    EXTRACTION = "extraction"
    EMBEDDING = "embedding"
    DEDUPLICATION = "deduplication"
    CLUSTERING = "clustering"
    PAIN_POINT = "pain_point"
    OPPORTUNITY = "opportunity"
    REQUIREMENT = "requirement"
    PRD = "prd"
    COMPLETE = "complete"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Annotated field shortcuts
# ---------------------------------------------------------------------------

Confidence = Annotated[float, Field(ge=0.0, le=1.0, description="Confidence score 0.0–1.0")]

UTCTimestamp = Annotated[
    datetime,
    Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp"),
]
