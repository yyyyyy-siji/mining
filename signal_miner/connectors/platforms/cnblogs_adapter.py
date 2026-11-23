"""P12-2 博客园（cnblogs）证据包适配器。

解析公开文章 URL 和 / 或 cnblogs Open API JSON，输出统一 AcquisitionEvidence。
无 token 时允许只解析传入样例 JSON，不访问网络。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from signal_miner.connectors.source_acquisition import AcquisitionEvidence, EvidencePackageError


class CnblogsEvidenceAdapter:
    """将博客园文章数据转换为证据包。

    capture_method 默认为 ``official_api``（若有 API JSON），
    也可用 ``crawler`` 或 ``manual_browser``。
    """

    source_type: str = "cnblogs"

    @staticmethod
    def from_api_json(
        article: dict[str, Any],
        *,
        capture_method: str = "official_api",
        source_note: str | None = None,
    ) -> AcquisitionEvidence:
        """从博客园 Open API JSON 创建证据包。

        Args:
            article: 博客园 API 返回的文章对象。
            capture_method: 采集方法。
            source_note: 可选来源备注。

        Raises:
            EvidencePackageError: 若 URL 缺失或不来自 cnblogs.com。
        """
        url = article.get("Url") or article.get("url") or ""
        if not url:
            raise EvidencePackageError("博客园文章 JSON 缺少 Url/url 字段。")

        return AcquisitionEvidence(
            source_type="cnblogs",
            external_url=str(url),
            capture_method=capture_method,
            text=str(article.get("Description") or article.get("Summary") or article.get("Body") or ""),
            subject=str(article.get("Title") or article.get("title")) if article.get("Title") or article.get("title") else None,
            author_name=str(article.get("Author") or article.get("author") or article.get("BlogApp", "")) or None,
            source_note=source_note,
            source_captured_at=CnblogsEvidenceAdapter._parse_time(article.get("DateAdded") or article.get("PostDate")),
            raw_payload=article,
        )

    @staticmethod
    def from_url_and_text(
        url: str,
        text: str,
        *,
        subject: str | None = None,
        author_name: str | None = None,
        capture_method: str = "manual_browser",
        source_note: str | None = None,
    ) -> AcquisitionEvidence:
        """从已知 URL 和已提取文本创建证据包（人工浏览场景）。

        URL 必须来自 cnblogs.com 域名。
        """
        return AcquisitionEvidence(
            source_type="cnblogs",
            external_url=url,
            capture_method=capture_method,
            text=text,
            subject=subject,
            author_name=author_name,
            source_note=source_note,
        )

    @staticmethod
    def _parse_time(iso_str: str | None) -> datetime | None:
        if not iso_str:
            return None
        try:
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
