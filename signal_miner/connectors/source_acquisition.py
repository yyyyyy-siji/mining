"""P12-2 统一证据包模型与契约。

每个采集适配器产出 AcquisitionEvidence 实例，该实例可转换为
``/feedback/ingest`` 或 ``/feedback/batch`` 可接受的 IngestRequest payload，
且在转换前强制通过 P12-1 的 ``validate_required_source_url`` 校验。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from datetime import datetime

from signal_miner.utils.source_platforms import (
    SourceUrlValidationError,
    validate_required_source_url,
)

# ── 证据包允许的采集方法 ────────────────────────────────────────────────
_VALID_CAPTURE_METHODS = frozenset({
    "official_api",
    "crawler",
    "browser_screenshot",
    "manual_browser",
    "webhook",
})


class EvidencePackageError(ValueError):
    """证据包自身不合规时抛出（字段缺失、逻辑冲突等）。"""


# ── 证据包数据类 ─────────────────────────────────────────────────────────


@dataclass
class AcquisitionEvidence:
    """站点级采集适配器的统一输出契约。

    所有字段含义与指令中定义一致。
    """

    source_type: str
    """平台策略键（如 ``github``、``cnblogs``）。"""

    external_url: str
    """原始页面／资源 URL（必填，可点击）。"""

    capture_method: str
    """采集方法（official_api / crawler / browser_screenshot / manual_browser / webhook）。"""

    text: str
    """反馈正文／提取的文本内容。"""

    subject: str | None = None
    author_name: str | None = None
    source_note: str | None = None
    source_captured_at: datetime | None = None
    raw_payload: dict[str, Any] | None = None
    screenshot_path: str | None = None
    ocr_text: str | None = None
    # ── 以下用于 ingest payload 映射 ──
    author_email: str | None = None
    company: str | None = None
    segment: str | None = None

    # 保留映射到 IngestRequest 时的输入来源 ID
    source_id: str = field(default="")
    external_id: str | None = None
    source_created_at: datetime | None = None
    source_updated_at: datetime | None = None
    entity_type: str = "unknown"
    parent_id: str | None = None
    parent_url: str | None = None
    parent_comment_id: str | None = None
    parent_comment_url: str | None = None
    locator_level: str = "unknown"
    content_nature: str = "manual_text"
    coverage_scope: str | None = None
    capture_version: str | None = None
    text_origin: str = "user_provided"

    # ── 视频相关（aigc_video profile） ──
    video_url: str | None = None
    views: int | None = None
    likes: int | None = None
    platform: str | None = None

    def __post_init__(self) -> None:
        """构造时做最小自检。"""
        if not self.source_type or not isinstance(self.source_type, str):
            raise EvidencePackageError("source_type 必须是非空字符串。")
        if not self.external_url or not isinstance(self.external_url, str):
            raise EvidencePackageError("external_url 必须是非空字符串。")
        if not self.text:
            raise EvidencePackageError("text 必须是非空字符串。")
        if self.capture_method not in _VALID_CAPTURE_METHODS:
            raise EvidencePackageError(
                f"capture_method 不合法: {self.capture_method!r}，"
                f"可选: {sorted(_VALID_CAPTURE_METHODS)}"
            )

    # ── 校验 ──────────────────────────────────────────────────────────────

    def validate(self) -> None:
        """业务规则校验。

        Raises:
            EvidencePackageError: 若证据包不合规。
        """
        # browser_screenshot 必须提供截图路径或来源备注
        if self.capture_method == "browser_screenshot" and not self.screenshot_path and not self.source_note:
            raise EvidencePackageError(
                "capture_method=browser_screenshot 时必须提供 "
                "screenshot_path 或 source_note，否则无法追溯。"
            )

    # ── 转换为 IngestRequest payload ─────────────────────────────────────

    def to_ingest_payload(
        self,
        *,
        pipeline_profile: str = "product_feedback",
    ) -> dict[str, Any]:
        """将证据包转换为 ``POST /feedback/ingest`` 可接受的 dict。

        转换前：
        1. 运行 self.validate() 做业务规则校验。
        2. 调用 P12-1 的 validate_required_source_url 做域名/方法/搜索页校验。

        Returns:
            dict: 可直接传给 IngestRequest(**payload).
        """
        # 1. 业务规则
        self.validate()

        # 2. P12-1 URL 校验
        try:
            validated_url = validate_required_source_url(
                self.source_type,
                self.external_url,
                source_id=self.source_id or None,
                capture_method=self.capture_method,
            )
        except SourceUrlValidationError as exc:
            raise EvidencePackageError(
                f"来源 URL 校验失败 (P12-1): {exc}"
            ) from exc

        payload: dict[str, Any] = {
            "source_type": self.source_type,
            "text": self.text,
            "external_url": validated_url,
            "capture_method": self.capture_method,
            "pipeline_profile": pipeline_profile,
        }

        if self.subject is not None:
            payload["subject"] = self.subject
        if self.author_name is not None:
            payload["author_name"] = self.author_name
        if self.author_email is not None:
            payload["author_email"] = self.author_email
        if self.company is not None:
            payload["company"] = self.company
        if self.segment is not None:
            payload["segment"] = self.segment
        if self.source_note is not None:
            payload["source_note"] = self.source_note

        # 视频字段
        if self.video_url is not None:
            payload["video_url"] = self.video_url
        if self.views is not None:
            payload["views"] = self.views
        if self.likes is not None:
            payload["likes"] = self.likes
        if self.platform is not None:
            payload["platform"] = self.platform
        for key in (
            "external_id", "entity_type", "parent_id", "parent_url", "parent_comment_id",
            "parent_comment_url", "locator_level", "content_nature", "coverage_scope",
            "capture_version", "text_origin", "raw_payload", "screenshot_path", "ocr_text",
        ):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value
        for key in ("source_created_at", "source_updated_at", "source_captured_at"):
            value = getattr(self, key)
            if value is not None:
                payload[key] = value.isoformat()

        # 证据包特有字段存入 source_note（若未单独指定）
        evidence_meta_parts: list[str] = []
        if self.screenshot_path:
            evidence_meta_parts.append(f"screenshot_path={self.screenshot_path}")
        if self.ocr_text:
            evidence_meta_parts.append(f"ocr_text={self.ocr_text[:200]}")
        if self.source_captured_at:
            evidence_meta_parts.append(f"captured_at={self.source_captured_at.isoformat()}")
        if evidence_meta_parts:
            meta = "; ".join(evidence_meta_parts)
            if payload.get("source_note"):
                payload["source_note"] = f"{payload['source_note']}; {meta}"
            else:
                payload["source_note"] = meta

        return payload

    def to_ingest_payloads(
        self,
        *,
        pipeline_profile: str = "product_feedback",
    ) -> list[dict[str, Any]]:
        """便捷包装 — 返回单项列表，方便批量接口直接使用。"""
        return [self.to_ingest_payload(pipeline_profile=pipeline_profile)]


# ── 辅助：批量转换 ───────────────────────────────────────────────────────


def batch_to_ingest_payloads(
    evidence_list: list[AcquisitionEvidence],
    *,
    pipeline_profile: str = "product_feedback",
) -> list[dict[str, Any]]:
    """将一批证据包转换为发送给 ``POST /feedback/batch`` 的 payload 列表。

    任一项转换失败都会立即抛出 EvidencePackageError。
    """
    return [
        ev.to_ingest_payload(pipeline_profile=pipeline_profile)
        for ev in evidence_list
    ]


__all__ = [
    "AcquisitionEvidence",
    "EvidencePackageError",
    "batch_to_ingest_payloads",
]
