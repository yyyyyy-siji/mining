"""P12-2 通用证据包适配器（manual / csv / json）。

对人工录入、CSV、JSON 来源的数据做预检，确保每条都有真实 URL 和采集方法。
不做平台特定解析，但保证字段契约完整性。
"""

from __future__ import annotations

from typing import Any

from signal_miner.connectors.source_acquisition import AcquisitionEvidence, EvidencePackageError


class GenericEvidenceAdapter:
    """通用证据包构造器，用于 manual / csv / json / custom 等来源。

    不做内容解析，只确保字段契约完整和 URL 必填。
    """

    @staticmethod
    def from_dict(
        item: dict[str, Any],
        *,
        default_source_type: str = "manual",
        default_capture_method: str = "manual_browser",
    ) -> AcquisitionEvidence:
        """从任意字典构造证据包。

        按优先级尝试以下字段获取 external_url:
        external_url → source_url → url → video_url → link

        source_type 和 capture_method 若 item 中缺失则取默认值。

        Raises:
            EvidencePackageError: 若所有 URL 字段均为空。
        """
        external_url = (
            item.get("external_url")
            or item.get("source_url")
            or item.get("url")
            or item.get("video_url")
            or item.get("link")
            or ""
        )
        if not external_url:
            raise EvidencePackageError(
                "通用证据包缺少 external_url / source_url / url / video_url / link 字段。"
            )

        source_type = str(item.get("source_type") or default_source_type)
        capture_method = str(item.get("capture_method") or default_capture_method)

        return AcquisitionEvidence(
            source_type=source_type,
            external_url=str(external_url),
            capture_method=capture_method,
            text=str(item.get("text") or item.get("body") or item.get("content") or ""),
            subject=item.get("subject") if item.get("subject") else None,
            author_name=item.get("author_name") if item.get("author_name") else None,
            author_email=item.get("author_email") if item.get("author_email") else None,
            source_note=item.get("source_note") if item.get("source_note") else None,
            screenshot_path=item.get("screenshot_path") if item.get("screenshot_path") else None,
            ocr_text=item.get("ocr_text") if item.get("ocr_text") else None,
            raw_payload=item,
            video_url=item.get("video_url") if item.get("video_url") else None,
            views=item.get("views") if item.get("views") else None,
            likes=item.get("likes") if item.get("likes") else None,
            platform=item.get("platform") if item.get("platform") else None,
        )

    @staticmethod
    def from_dicts_batch(
        items: list[dict[str, Any]],
        *,
        default_source_type: str = "manual",
        default_capture_method: str = "manual_browser",
    ) -> list[AcquisitionEvidence]:
        """批量构造证据包。

        Raises:
            EvidencePackageError: 任一条目缺 URL 或不合规时抛出，含 1-based index。
        """
        evidence_list: list[AcquisitionEvidence] = []
        for idx, item in enumerate(items, 1):
            try:
                evidence_list.append(
                    GenericEvidenceAdapter.from_dict(
                        item,
                        default_source_type=default_source_type,
                        default_capture_method=default_capture_method,
                    )
                )
            except EvidencePackageError as exc:
                raise EvidencePackageError(
                    f"第 {idx} 条数据不合格：{exc}"
                ) from exc
        return evidence_list
