"""P12-2 GitHub 证据包适配器。

包装 GitHub connector 的 issue/comment 数据，输出统一 AcquisitionEvidence，
保留 html_url 作为 external_url。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from signal_miner.connectors.source_acquisition import AcquisitionEvidence, EvidencePackageError


class GitHubEvidenceAdapter:
    """将 GitHub issue / comment 数据转换为证据包。

    输入可以是 GitHub REST API v3 返回的原始 JSON，也可以手动构造。
    capture_method 固定为 ``official_api``。
    """

    source_type: str = "github"

    @staticmethod
    def from_issue(
        issue: dict[str, Any],
        *,
        source_note: str | None = None,
    ) -> AcquisitionEvidence:
        """从 GitHub issue 原始 JSON 创建证据包。

        Args:
            issue: GitHub API 返回的 issue object（至少含 html_url, title, body）。
            source_note: 可选来源备注。

        Returns:
            AcquisitionEvidence

        Raises:
            EvidencePackageError: 若缺少必填字段。
        """
        html_url = issue.get("html_url", "")
        if not html_url:
            raise EvidencePackageError("GitHub issue 缺少 html_url 字段。")

        return AcquisitionEvidence(
            source_type="github",
            external_url=str(html_url),
            capture_method="official_api",
            text=str(issue.get("body") or issue.get("title", "")),
            subject=str(issue.get("title")) if issue.get("title") else None,
            author_name=str(issue["user"]["login"]) if issue.get("user", {}).get("login") else None,
            source_note=source_note,
            source_captured_at=GitHubEvidenceAdapter._parse_time(issue.get("created_at")),
            raw_payload=issue,
        )

    @staticmethod
    def from_comment(
        issue: dict[str, Any],
        comment: dict[str, Any],
        *,
        source_note: str | None = None,
    ) -> AcquisitionEvidence:
        """从 GitHub issue + comment 原始 JSON 创建证据包。

        external_url 使用 comment 自身的 html_url，若无则回退到 issue 的 html_url。
        """
        comment_url = comment.get("html_url") or issue.get("html_url", "")
        if not comment_url:
            raise EvidencePackageError("GitHub comment 缺少 html_url 字段。")

        # 构造有意义的 subject
        issue_title = issue.get("title", "")
        subject = f"[Comment] {issue_title}" if issue_title else None

        return AcquisitionEvidence(
            source_type="github",
            external_url=str(comment_url),
            capture_method="official_api",
            text=str(comment.get("body", "")),
            subject=subject,
            author_name=str(comment["user"]["login"]) if comment.get("user", {}).get("login") else None,
            source_note=source_note,
            source_captured_at=GitHubEvidenceAdapter._parse_time(comment.get("created_at")),
            raw_payload={"issue": issue, "comment": comment},
        )

    @staticmethod
    def _parse_time(iso_str: str | None) -> datetime | None:
        if not iso_str:
            return None
        try:
            return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
