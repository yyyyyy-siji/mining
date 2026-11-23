"""P12-2 搜索引擎证据包适配器。

接受搜索 API 返回的结果数组或手工导出的 JSON，输出统一证据包。
每条结果必须使用落地页 URL（不是搜索页 URL）。
"""

from __future__ import annotations

from typing import Any

from signal_miner.connectors.source_acquisition import AcquisitionEvidence, EvidencePackageError

# ── 搜索引擎 → source_type 映射 ──────────────────────────────────────────
_SEARCH_SOURCE_TYPES: dict[str, str] = {
    "baidu": "baidu_search",
    "google": "google_search",
    "bing": "bing_search",
    "sogou": "sogou_search",
    "so360": "so360_search",
}


class SearchEvidenceAdapter:
    """将搜索结果 JSON 转换为证据包。

    每条结果的 external_url 必须是搜索结果的**落地页 URL**，
    不能是搜索列表页 URL（由 P12-1 validate_required_source_url 兜底拒绝）。
    """

    source_type: str = "google_search"

    @staticmethod
    def from_search_result(
        result: dict[str, Any],
        *,
        engine: str = "google",
        capture_method: str = "official_api",
        source_note: str | None = None,
    ) -> AcquisitionEvidence:
        """从单条搜索结果构造证据包。

        Args:
            result: 搜索 API 返回的单条结果。
            engine: 搜索引擎标识 (google/baidu/bing/sogou/so360)。
            capture_method: 采集方法。
            source_note: 来源备注。

        Raises:
            EvidencePackageError: 若缺少落地页 URL。
        """
        source_type = _SEARCH_SOURCE_TYPES.get(engine, "google_search")

        # 尝试多种常见字段获取落地页 URL
        landing_url = (
            result.get("link")
            or result.get("url")
            or result.get("landing_page_url")
            or ""
        )
        if not landing_url:
            raise EvidencePackageError(
                "搜索结果缺少落地页 URL（link/url/landing_page_url 字段均为空）。"
            )

        title = result.get("title") or result.get("name") or ""
        snippet = result.get("snippet") or result.get("description") or result.get("summary") or ""

        return AcquisitionEvidence(
            source_type=source_type,
            external_url=str(landing_url),
            capture_method=capture_method,
            text=snippet or title,
            subject=str(title) if title else None,
            source_note=source_note,
            raw_payload=result,
        )

    @staticmethod
    def from_search_results_batch(
        results: list[dict[str, Any]],
        *,
        engine: str = "google",
        capture_method: str = "official_api",
        source_note: str | None = None,
    ) -> list[AcquisitionEvidence]:
        """从搜索结果数组批量构造证据包。

        跳过缺少落地页 URL 的无效条目并警告，不会整体失败。

        Returns:
            list[AcquisitionEvidence]

        Raises:
            EvidencePackageError: 任一条目缺 URL 或不合规时抛出，含 1-based index。
        """
        evidence_list: list[AcquisitionEvidence] = []
        for idx, item in enumerate(results, 1):
            try:
                evidence_list.append(
                    SearchEvidenceAdapter.from_search_result(
                        item,
                        engine=engine,
                        capture_method=capture_method,
                        source_note=source_note,
                    )
                )
            except EvidencePackageError as exc:
                raise EvidencePackageError(
                    f"第 {idx} 条搜索结果不合格：{exc}"
                ) from exc
        return evidence_list
