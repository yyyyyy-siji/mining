"""Helpers for building source URLs and human-readable platform names.

The module centralises all platform-specific URL patterns so that the rest of
the codebase can resolve a ``(source_type, external_id)`` pair into a full URL
without scattering template strings across multiple files.
"""

from __future__ import annotations

from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# URL templates – {external_id} is the single interpolation placeholder
# ---------------------------------------------------------------------------

SOURCE_URL_TEMPLATES: dict[str, str | None] = {
    "bilibili": "https://www.bilibili.com/video/{external_id}",
    "video_bilibili": "https://www.bilibili.com/video/{external_id}",
    "douyin": "https://www.douyin.com/video/{external_id}",
    "video_douyin": "https://www.douyin.com/video/{external_id}",
    "kuaishou": "https://live.kuaishou.com/u/{external_id}",
    "video_kuaishou": "https://live.kuaishou.com/u/{external_id}",
    "xiaohongshu": "https://www.xiaohongshu.com/explore/{external_id}",
    "video_xiaohongshu": "https://www.xiaohongshu.com/explore/{external_id}",
    "video_youtube": "https://www.youtube.com/watch?v={external_id}",
    "weibo": "https://weibo.com/{external_id}",
    "github": "https://github.com/{external_id}",
    "support_ticket": None,
    "manual": None,
    "csv": None,
    "webhook": None,
}

_PLACEHOLDER_HOSTS = {
    "example.com",
    "www.example.com",
    "example.net",
    "www.example.net",
    "example.org",
    "www.example.org",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
}

_SYNTHETIC_SOURCE_IDS = {
    "live_game_import",
}

# ---------------------------------------------------------------------------
# Human-readable display names (Chinese where applicable)
# ---------------------------------------------------------------------------

_PLATFORM_DISPLAY_NAMES: dict[str, str] = {
    "bilibili": "B站",
    "video_bilibili": "B站视频",
    "douyin": "抖音",
    "video_douyin": "抖音视频",
    "kuaishou": "快手",
    "video_kuaishou": "快手视频",
    "xiaohongshu": "小红书",
    "video_xiaohongshu": "小红书视频",
    "video_youtube": "YouTube视频",
    "video_youku": "优酷视频",
    "video_iqiyi": "爱奇艺视频",
    "video_tencent": "腾讯视频",
    "weibo": "微博",
    "zhihu": "知乎",
    "tieba": "百度贴吧",
    "csdn": "CSDN",
    "juejin": "掘金",
    "cnblogs": "博客园",
    "weixin_mp": "微信公众号",
    "baidu_search": "百度搜索结果",
    "sogou_search": "搜狗搜索结果",
    "so360_search": "360搜索结果",
    "google_search": "Google搜索结果",
    "bing_search": "Bing搜索结果",
    "taobao": "淘宝",
    "tmall": "天猫",
    "jd": "京东",
    "pinduoduo": "拼多多",
    "xianyu": "闲鱼",
    "zhuanzhuan": "转转",
    "aihuishou": "爱回收",
    "github": "GitHub",
    "manual": "手动录入",
    "csv": "CSV导入",
    "support_ticket": "客服工单",
    "webhook": "Webhook",
}


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def resolve_source_url(
    source_type: str,
    external_id: str | None = None,
    external_url: str | None = None,
    context: dict | None = None,
) -> str | None:
    """Return the best available URL for a signal source.

    Resolution order:

    1. *external_url* – returned verbatim when provided and non-empty.
    2. ``context["video_url"]`` – used when the context dict carries a
       pre-resolved video URL.
    3. Template interpolation – if *source_type* maps to a known template and
       *external_id* is provided, the template is formatted and returned.
    4. ``None`` – when none of the above yield a result.

    Parameters
    ----------
    source_type:
        Platform key (e.g. ``"bilibili"``, ``"douyin"``).
    external_id:
        Platform-specific identifier to embed in the URL template.
    external_url:
        An explicit URL that takes precedence over template resolution.
    context:
        Optional dict that may contain a ``video_url`` key.

    Returns
    -------
    str | None
        The resolved URL, or ``None`` if it cannot be determined.
    """
    # 1. Explicit URL always wins.
    if external_url:
        return external_url

    # 2. Context-provided video_url.
    if context:
        video_url = context.get("video_url")
        if video_url:
            return video_url

    # 3. Template interpolation.
    if external_id:
        template = SOURCE_URL_TEMPLATES.get(source_type)
        if template is not None:
            return template.format(external_id=external_id)

    return None


def is_clickable_source_url(url: str | None, *, source_id: str | None = None) -> bool:
    """Return whether *url* should be exposed as a user-facing clickthrough.

    ``external_url`` is still preserved as raw provenance data, but UI
    clickthroughs must not send users to placeholder/demo pages. In particular,
    local demo imports can contain syntactically valid but randomly generated
    platform URLs; those should be shown as source metadata, not as "open
    original source" links.
    """
    if not url:
        return False

    source_id = (source_id or "").strip()
    if source_id in _SYNTHETIC_SOURCE_IDS or "_sample_" in source_id:
        return False

    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False

    host = (parsed.hostname or "").lower()
    if host in _PLACEHOLDER_HOSTS:
        return False

    if host.startswith("www.video_"):
        return False

    return not parsed.path.startswith("/mock/")


def resolve_clickable_source_url(
    source_type: str,
    external_id: str | None = None,
    external_url: str | None = None,
    context: dict | None = None,
    source_id: str | None = None,
) -> str | None:
    """Resolve a URL that is safe to render as a clickthrough.

    Unlike :func:`resolve_source_url`, this helper intentionally does not
    synthesize a URL from ``(source_type, external_id)``. A guessed platform URL
    can easily point at a different video, an empty page, or a dead room. The
    UI-facing source link is therefore limited to explicit URLs captured during
    ingestion, after placeholder/demo filtering.
    """
    del external_id, source_type  # kept in the signature for call-site clarity

    candidate = external_url
    if not candidate and context:
        candidate = context.get("video_url")

    if is_clickable_source_url(candidate, source_id=source_id):
        return candidate
    return None


def get_platform_display_name(source_type: str) -> str:
    """Return a human-readable display name for the given *source_type*.

    Falls back to *source_type* itself when no explicit mapping exists.

    Parameters
    ----------
    source_type:
        Platform key (e.g. ``"bilibili"``).

    Returns
    -------
    str
        The display name (e.g. ``"B站"``).
    """
    return _PLATFORM_DISPLAY_NAMES.get(source_type, source_type)
