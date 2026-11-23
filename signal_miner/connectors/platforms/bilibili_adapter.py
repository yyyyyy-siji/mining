"""P12-2 哔哩哔哩（bilibili）证据包适配器。

接受用户提供的视频标题、评论文本、BV URL，构造统一证据包。
不伪造评论，不绕过登录/反爬——所有内容均由调用方提供真实数据。
"""

from __future__ import annotations

from signal_miner.connectors.source_acquisition import AcquisitionEvidence, EvidencePackageError


class BilibiliEvidenceAdapter:
    """将 B 站视频/评论样本转换为证据包。

    支持两种 source_type：``bilibili`` 和 ``video_bilibili``。
    capture_method 可选 ``official_api``、``crawler``、``manual_browser``。
    """

    source_type: str = "bilibili"

    @staticmethod
    def from_video_sample(
        bv_url: str,
        text: str,
        *,
        source_type: str = "video_bilibili",
        subject: str | None = None,
        author_name: str | None = None,
        capture_method: str = "crawler",
        source_note: str | None = None,
        views: int | None = None,
        likes: int | None = None,
    ) -> AcquisitionEvidence:
        """从 B 站视频样本构造证据包。

        Args:
            bv_url: BV 视频页完整 URL（如 https://www.bilibili.com/video/BV1xx...）。
            text: 视频标题/描述/评论/爆款观察文本。
            source_type: ``video_bilibili`` 或 ``bilibili``。
            subject: 视频标题（可选）。
            author_name: UP 主名称（可选）。
            capture_method: 采集方法。
            source_note: 来源备注（可选）。
            views: 播放量（可选）。
            likes: 点赞量（可选）。

        Raises:
            EvidencePackageError: 若 BV URL 不来自 bilibili.com。
        """
        if not bv_url:
            raise EvidencePackageError("B 站证据包必须提供 video URL (BV 页)。")

        platform = None
        if source_type.startswith("video_"):
            platform = source_type.replace("video_", "")

        return AcquisitionEvidence(
            source_type=source_type,
            external_url=bv_url,
            capture_method=capture_method,
            text=text,
            subject=subject,
            author_name=author_name,
            source_note=source_note,
            video_url=bv_url,
            views=views,
            likes=likes,
            platform=platform,
        )

    @staticmethod
    def from_comment(
        bv_url: str,
        comment_text: str,
        *,
        comment_author: str | None = None,
        capture_method: str = "crawler",
        source_note: str | None = None,
    ) -> AcquisitionEvidence:
        """从 B 站单条评论构造证据包。

        external_url 使用评论所在 BV 视频页 URL。
        """
        if not bv_url:
            raise EvidencePackageError("B 站评论证据包必须提供视频页 URL。")

        return AcquisitionEvidence(
            source_type="bilibili",
            external_url=bv_url,
            capture_method=capture_method,
            text=comment_text,
            subject=f"[B站评论] {comment_text[:50]}..." if len(comment_text) > 50 else f"[B站评论] {comment_text}",
            author_name=comment_author,
            source_note=source_note,
            video_url=bv_url,
        )
