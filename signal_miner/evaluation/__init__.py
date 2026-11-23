"""P13-2-1 fix: Gold-set contract models and validation helpers.

Authorization MUST be explicit — no auto-derivation from source_type.
All Pydantic models use extra="forbid".
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import re
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0.0"

AUTHORIZED_BASES = frozenset({
    "explicit_user_consent",
    "public_forum_post",
    "internal_feedback_channel",
    "licensed_dataset",
})

PROFILES = frozenset({"product_feedback", "aigc_video"})

SENSITIVE_PATTERNS = [
    re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    re.compile(r"1[3-9]\d{9}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
]


# ── Models ──

class EvidenceSpan(BaseModel):
    model_config = {"extra": "forbid"}
    start: int
    end: int
    text: str


class SignalAnnotation(BaseModel):
    model_config = {"extra": "forbid"}
    signal_type: str = ""
    summary: str = ""
    evidence_spans: list[EvidenceSpan] = Field(default_factory=list)
    implicit_need: str | None = None
    implicit_need_has_basis: bool = False
    hallucination: bool = False
    notes: str | None = None


class HumanAnnotation(BaseModel):
    model_config = {"extra": "forbid"}
    sample_id: str
    annotator_slot: str  # A or B
    has_signals: bool = False
    signal_count: int = 0
    signals: list[SignalAnnotation] = Field(default_factory=list)
    completed_at: str | None = None
    notes: str | None = None


class Suggestion(BaseModel):
    model_config = {"extra": "forbid"}
    suggestion_id: str
    suggestion_model: str
    suggestion_model_version: str
    suggestion_prompt_version: str
    suggested_signals: list[dict[str, Any]] = Field(default_factory=list)
    suggestion_created_at: str = ""
    fixture_only: bool = False


class GoldRecord(BaseModel):
    model_config = {"extra": "forbid"}
    schema_version: str = SCHEMA_VERSION
    sample_id: str
    raw_feedback_id: str | None = None
    profile: str
    source_platform: str = ""
    capture_method: str = ""
    authorization_basis: str = ""
    content_hash: str = ""
    redacted_text: str = ""
    redaction_applied: bool = False
    language: str = "zh"
    hard_case_tags: list[str] = Field(default_factory=list)
    split: str = "development"
    split_seed: int = 42
    annotation_mode: str = "assisted_review"
    annotation_status: str = "pending"
    annotator_slot: str = "none"


class FrozenManifest(BaseModel):
    model_config = {"extra": "forbid"}
    dataset_id: str
    schema_version: str = SCHEMA_VERSION
    created_at: str = ""
    selection_query_fingerprint: str = ""
    seed: int = 42
    splits: dict[str, list[str]] = Field(default_factory=dict)
    double_annotation_ids: list[str] = Field(default_factory=list)
    double_annotation_count: int = 0
    double_annotation_ratio: float = 0.0
    annotation_mode_by_split: dict[str, str] = Field(default_factory=dict)
    sample_count: int = 0
    profile_distribution: dict[str, int] = Field(default_factory=dict)
    source_distribution: dict[str, int] = Field(default_factory=dict)
    capture_method_distribution: dict[str, int] = Field(default_factory=dict)
    blind_pack_hash: str = ""
    blind_pack_leakage_count: int = 0
    content_hash_list: list[str] = Field(default_factory=list)
    ordered_samples_hash: str = ""
    guideline_hash: str = ""
    human_labels_complete: bool = False
    human_verified_count: int = 0
    calibration_allowed: bool = False
    passed: bool = False


# ── Helpers ──

def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def has_sensitive(text: str) -> bool:
    return any(pat.search(text) for pat in SENSITIVE_PATTERNS)


def redact_sensitive(text: str) -> tuple[str, bool]:
    """Replace email/phone/token with stable placeholders. Returns (redacted, changed)."""
    changed = False
    result = text
    if re.search(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", result):
        result = re.sub(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]", result)
        changed = True
    if re.search(r"1[3-9]\d{9}", result):
        result = re.sub(r"1[3-9]\d{9}", "[PHONE_REDACTED]", result)
        changed = True
    if re.search(r"sk-[a-zA-Z0-9]{20,}", result):
        result = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[TOKEN_REDACTED]", result)
        changed = True
    return result, changed


def validate_evidence(redacted: str, spans: list[EvidenceSpan]) -> list[str]:
    mismatches: list[str] = []
    for span in spans:
        actual = ""
        try:
            actual = redacted[span.start: span.end]
        except Exception:
            actual = "<INDEX_ERROR>"
        if actual != span.text:
            mismatches.append(
                f"span [{span.start}:{span.end}] expected={span.text[:50]!r} actual={actual[:50]!r}"
            )
    return mismatches


def check_blind_pack_leakage(data: dict[str, Any]) -> int:
    """Recursively scan for prediction/suggestion/confidence/model/provider/prompt fields.

    Covers both exact key names and normalized variants.
    """
    # Exact and normalized field names to detect
    leak_keys = {
        # prediction / suggestion
        "prediction", "suggestion", "suggested_signals",
        # confidence / score
        "confidence", "score", "self_score", "calibrated_confidence",
        "model_self_score", "confidence_score",
        # model identity — both exact and compound
        "model", "model_name", "model_version", "model_id",
        # provider
        "provider", "llm_provider",
        # prompt
        "prompt", "prompt_version", "prompt_template",
    }

    def _scan(obj: Any, path: str = "$") -> int:
        count = 0
        if isinstance(obj, dict):
            for k, v in obj.items():
                kl = k.lower()
                # Check exact match or substring for compound model_ keys
                if k.lower() in leak_keys or any(w in kl for w in ("prediction", "suggestion", "confidence",
                                             "calibrated", "self_score",
                                             "model_", "prompt_version", "suggested_")) or kl in ("model", "provider", "llm_provider", "prompt", "score"):
                    count += 1
                count += _scan(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                count += _scan(item, f"{path}[{i}]")
        return count
    return _scan(data)


def compute_ordered_hash(samples: list[GoldRecord]) -> str:
    payload = "".join(s.content_hash for s in sorted(samples, key=lambda s: s.sample_id))
    return sha256(payload)


def is_test_or_mock_record(raw_feedback_id: str, text: str = "", source_id: str = "") -> bool:
    rid = raw_feedback_id.lower()
    t = text[:100].lower()
    sid = source_id.lower()
    if any(tag in rid for tag in ("test", "mock", "sample", "fixture", "demo")):
        return True
    if any(phrase in t for phrase in ("test feedback", "mock data", "sample fixt")):
        return True
    return bool(any(tag in sid for tag in ("test", "mock")))
