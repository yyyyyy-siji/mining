"""Source platform policies for trusted feedback ingestion.

The import API must only accept feedback that can be traced back to a real,
clickable origin. This module keeps platform-specific source URL rules and
collection guidance in one place so that domestic video/blog/search/shopping
sites are not treated as a single generic crawler bucket.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from signal_miner.utils.url_templates import is_clickable_source_url


class SourceUrlValidationError(ValueError):
    """Raised when an imported item does not have a trustworthy source URL."""


@dataclass(frozen=True)
class SourcePlatformPolicy:
    """Per-platform source acquisition and URL validation policy."""

    key: str
    label: str
    category: str
    allowed_domains: tuple[str, ...] = ()
    acquisition_methods: tuple[str, ...] = ("manual_browser",)
    allow_any_domain: bool = False
    source_url_rule: str = "original_page_url"
    notes: str = ""


CAPTURE_METHOD_LABELS: dict[str, str] = {
    "official_api": "官方 API / 开放平台",
    "crawler": "合规公开页面爬取",
    "browser_screenshot": "浏览器截图 / OCR / 人工识别",
    "manual_browser": "人工浏览记录",
    "webhook": "Webhook / 外部系统推送",
}


def _policy(
    key: str,
    label: str,
    category: str,
    *,
    allowed_domains: tuple[str, ...] = (),
    acquisition_methods: tuple[str, ...] = ("manual_browser",),
    allow_any_domain: bool = False,
    source_url_rule: str = "original_page_url",
    notes: str = "",
) -> SourcePlatformPolicy:
    return SourcePlatformPolicy(
        key=key,
        label=label,
        category=category,
        allowed_domains=allowed_domains,
        acquisition_methods=acquisition_methods,
        allow_any_domain=allow_any_domain,
        source_url_rule=source_url_rule,
        notes=notes,
    )


_COMMON_MANUAL_METHODS = ("manual_browser", "browser_screenshot")
_API_AND_MANUAL_METHODS = ("official_api", "manual_browser")
_API_SCREENSHOT_METHODS = ("official_api", "manual_browser", "browser_screenshot")
_PUBLIC_PAGE_METHODS = ("crawler", "manual_browser", "browser_screenshot")
_SEARCH_METHODS = ("official_api", "manual_browser", "browser_screenshot")


SOURCE_PLATFORM_POLICIES: dict[str, SourcePlatformPolicy] = {
    # Domestic video / short-video platforms.
    "video_douyin": _policy(
        "video_douyin",
        "抖音视频",
        "video",
        allowed_domains=("douyin.com", "iesdouyin.com"),
        acquisition_methods=_API_SCREENSHOT_METHODS,
        notes="优先使用抖音开放平台授权接口；页面受限时记录视频页 URL，并用浏览器截图/OCR 提取可见评论。",
    ),
    "douyin": _policy(
        "douyin",
        "抖音",
        "video",
        allowed_domains=("douyin.com", "iesdouyin.com"),
        acquisition_methods=_API_SCREENSHOT_METHODS,
        notes="优先使用抖音开放平台授权接口；页面受限时记录原始视频页 URL。",
    ),
    "video_bilibili": _policy(
        "video_bilibili",
        "哔哩哔哩视频",
        "video",
        allowed_domains=("bilibili.com", "b23.tv"),
        acquisition_methods=("official_api", "crawler", "manual_browser", "browser_screenshot"),
        notes="可用开放平台/公开页面采集；每条评论或视频样本保留 BV 视频页或评论所在页 URL。",
    ),
    "bilibili": _policy(
        "bilibili",
        "哔哩哔哩",
        "video",
        allowed_domains=("bilibili.com", "b23.tv"),
        acquisition_methods=("official_api", "crawler", "manual_browser", "browser_screenshot"),
        notes="可用开放平台/公开页面采集；必须保留可打开的 B 站原始页面。",
    ),
    "video_kuaishou": _policy(
        "video_kuaishou",
        "快手视频",
        "video",
        allowed_domains=("kuaishou.com", "gifshow.com"),
        acquisition_methods=_API_SCREENSHOT_METHODS,
        notes="优先开放平台授权；页面受限时用浏览器可见内容截图/OCR，并保留视频页 URL。",
    ),
    "kuaishou": _policy(
        "kuaishou",
        "快手",
        "video",
        allowed_domains=("kuaishou.com", "gifshow.com"),
        acquisition_methods=_API_SCREENSHOT_METHODS,
        notes="优先开放平台授权；页面受限时保留原始视频页 URL。",
    ),
    "video_xiaohongshu": _policy(
        "video_xiaohongshu",
        "小红书视频/笔记",
        "video",
        allowed_domains=("xiaohongshu.com", "xhslink.com"),
        acquisition_methods=_API_SCREENSHOT_METHODS,
        notes="优先蒲公英/开放平台授权；页面受限时用浏览器截图/OCR，并保留笔记页 URL。",
    ),
    "xiaohongshu": _policy(
        "xiaohongshu",
        "小红书",
        "community",
        allowed_domains=("xiaohongshu.com", "xhslink.com"),
        acquisition_methods=("official_api", "crawler", "manual_browser", "browser_screenshot"),
        notes="优先开放平台授权；页面受限时保留笔记页 URL 和截图/OCR 记录。",
    ),
    "video_youtube": _policy(
        "video_youtube",
        "YouTube 视频",
        "video",
        allowed_domains=("youtube.com", "youtu.be"),
        acquisition_methods=_API_AND_MANUAL_METHODS,
        notes="可用 YouTube Data API 或人工浏览记录；必须保留视频页 URL。",
    ),
    "video_youku": _policy(
        "video_youku",
        "优酷视频",
        "video",
        allowed_domains=("youku.com",),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="页面/账号限制较多，采用人工浏览或截图/OCR，保留视频页 URL。",
    ),
    "video_iqiyi": _policy(
        "video_iqiyi",
        "爱奇艺视频",
        "video",
        allowed_domains=("iqiyi.com",),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="页面/账号限制较多，采用人工浏览或截图/OCR，保留视频页 URL。",
    ),
    "video_tencent": _policy(
        "video_tencent",
        "腾讯视频",
        "video",
        allowed_domains=("v.qq.com", "video.qq.com"),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="页面/账号限制较多，采用人工浏览或截图/OCR，保留视频页 URL。",
    ),
    "video_manual": _policy(
        "video_manual",
        "视频手动录入",
        "video",
        acquisition_methods=_COMMON_MANUAL_METHODS,
        allow_any_domain=True,
        notes="用于未单独建模的视频网站；仍必须保留真实视频页 URL。",
    ),
    # Domestic blog/community platforms.
    "weibo": _policy(
        "weibo",
        "微博",
        "community",
        allowed_domains=("weibo.com", "m.weibo.cn"),
        acquisition_methods=_PUBLIC_PAGE_METHODS,
        notes="公开微博可用页面采集；登录/反爬限制时用浏览器截图/OCR，保留微博详情页 URL。",
    ),
    "zhihu": _policy(
        "zhihu",
        "知乎",
        "community",
        allowed_domains=("zhihu.com",),
        acquisition_methods=("official_api", *_PUBLIC_PAGE_METHODS),
        notes="公开回答/文章/评论可页面采集；受限内容用浏览器截图/OCR，保留原页面 URL。",
    ),
    "csdn": _policy(
        "csdn",
        "CSDN",
        "blog",
        allowed_domains=("csdn.net",),
        acquisition_methods=_PUBLIC_PAGE_METHODS,
        notes="公开博客页可抓取；保留文章或评论页 URL。",
    ),
    "juejin": _policy(
        "juejin",
        "掘金",
        "blog",
        allowed_domains=("juejin.cn",),
        acquisition_methods=_PUBLIC_PAGE_METHODS,
        notes="公开文章/沸点可页面采集；保留原始内容页 URL。",
    ),
    "cnblogs": _policy(
        "cnblogs",
        "博客园",
        "blog",
        allowed_domains=("cnblogs.com",),
        acquisition_methods=_API_AND_MANUAL_METHODS,
        notes="优先使用博客园 Open API；也可人工浏览公开文章并保留文章 URL。",
    ),
    "weixin_mp": _policy(
        "weixin_mp",
        "微信公众号文章",
        "blog",
        allowed_domains=("mp.weixin.qq.com",),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="公众号页面限制较多，采用浏览器打开文章、截图/OCR 或人工摘录，保留文章 URL。",
    ),
    "tieba": _policy(
        "tieba",
        "百度贴吧",
        "community",
        allowed_domains=("tieba.baidu.com",),
        acquisition_methods=_PUBLIC_PAGE_METHODS,
        notes="公开帖子可页面采集；保留帖子或楼层所在 URL。",
    ),
    # Search engines: source_type records the engine, external_url must be the result page.
    "baidu_search": _policy(
        "baidu_search",
        "百度搜索结果",
        "search",
        acquisition_methods=_SEARCH_METHODS,
        allow_any_domain=True,
        source_url_rule="search_result_target_url",
        notes="采集结果时保存搜索结果的落地页 URL，不保存泛化搜索页作为证据。",
    ),
    "sogou_search": _policy(
        "sogou_search",
        "搜狗搜索结果",
        "search",
        acquisition_methods=_SEARCH_METHODS,
        allow_any_domain=True,
        source_url_rule="search_result_target_url",
        notes="采集结果时保存搜索结果的落地页 URL，不保存泛化搜索页作为证据。",
    ),
    "so360_search": _policy(
        "so360_search",
        "360 搜索结果",
        "search",
        acquisition_methods=_SEARCH_METHODS,
        allow_any_domain=True,
        source_url_rule="search_result_target_url",
        notes="采集结果时保存搜索结果的落地页 URL，不保存泛化搜索页作为证据。",
    ),
    "google_search": _policy(
        "google_search",
        "Google 搜索结果",
        "search",
        acquisition_methods=_SEARCH_METHODS,
        allow_any_domain=True,
        source_url_rule="search_result_target_url",
        notes="可用 Google Custom Search/Programmable Search；证据 URL 必须是结果落地页。",
    ),
    "bing_search": _policy(
        "bing_search",
        "Bing 搜索结果",
        "search",
        acquisition_methods=_SEARCH_METHODS,
        allow_any_domain=True,
        source_url_rule="search_result_target_url",
        notes="证据 URL 必须是搜索结果落地页，不是搜索结果列表页。",
    ),
    # Shopping engines / marketplaces.
    "taobao": _policy(
        "taobao",
        "淘宝",
        "shopping",
        allowed_domains=("taobao.com", "m.tb.cn"),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="商品/评价页面限制较多，采用浏览器打开、截图/OCR 或人工记录，保留商品/评价页 URL。",
    ),
    "tmall": _policy(
        "tmall",
        "天猫",
        "shopping",
        allowed_domains=("tmall.com", "taobao.com", "m.tb.cn"),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="商品/评价页面限制较多，采用浏览器打开、截图/OCR 或人工记录，保留商品/评价页 URL。",
    ),
    "jd": _policy(
        "jd",
        "京东",
        "shopping",
        allowed_domains=("jd.com", "3.cn"),
        acquisition_methods=_API_SCREENSHOT_METHODS,
        notes="优先京东开放平台授权接口；页面受限时用截图/OCR，保留商品或评价页 URL。",
    ),
    "pinduoduo": _policy(
        "pinduoduo",
        "拼多多",
        "shopping",
        allowed_domains=("pinduoduo.com", "yangkeduo.com"),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="页面/账号限制较多，采用浏览器打开、截图/OCR 或人工记录，保留商品页 URL。",
    ),
    # Second-hand platforms.
    "xianyu": _policy(
        "xianyu",
        "闲鱼",
        "second_hand",
        allowed_domains=("goofish.com", "2.taobao.com", "m.tb.cn"),
        acquisition_methods=_API_SCREENSHOT_METHODS,
        notes="优先闲鱼开放平台/TOP 权限接口；页面受限时截图/OCR，保留商品页 URL。",
    ),
    "zhuanzhuan": _policy(
        "zhuanzhuan",
        "转转",
        "second_hand",
        allowed_domains=("zhuanzhuan.com",),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="页面限制较多，采用浏览器打开、截图/OCR 或人工记录，保留商品页 URL。",
    ),
    "aihuishou": _policy(
        "aihuishou",
        "爱回收",
        "second_hand",
        allowed_domains=("aihuishou.com",),
        acquisition_methods=_COMMON_MANUAL_METHODS,
        notes="采用浏览器打开、截图/OCR 或人工记录，保留商品/报价页 URL。",
    ),
    # Foreign/dev and system sources.
    "github": _policy(
        "github",
        "GitHub",
        "developer",
        allowed_domains=("github.com",),
        acquisition_methods=_API_AND_MANUAL_METHODS,
        notes="优先 GitHub REST API；保留 issue、discussion、PR 或 comment 的 html_url。",
    ),
    "manual": _policy(
        "manual",
        "手动录入",
        "custom",
        acquisition_methods=_COMMON_MANUAL_METHODS,
        allow_any_domain=True,
        notes="手动录入也必须填写真实原始页面 URL，不能用示例页或空 URL。",
    ),
    "support_ticket": _policy(
        "support_ticket",
        "客服工单",
        "internal",
        acquisition_methods=("webhook", "manual_browser"),
        allow_any_domain=True,
        notes="填写可点击的工单系统 URL 或客户原始反馈页 URL。",
    ),
    "app_review": _policy(
        "app_review",
        "应用商店评价",
        "review",
        acquisition_methods=_COMMON_MANUAL_METHODS,
        allow_any_domain=True,
        notes="填写 App Store、应用商店或评价详情可打开页面 URL。",
    ),
    "app_store_review": _policy(
        "app_store_review",
        "应用商店评价",
        "review",
        acquisition_methods=_COMMON_MANUAL_METHODS,
        allow_any_domain=True,
        notes="填写 App Store、应用商店或评价详情可打开页面 URL。",
    ),
    "csv": _policy(
        "csv",
        "CSV 导入",
        "file",
        acquisition_methods=("manual_browser", "webhook"),
        allow_any_domain=True,
        notes="CSV 每一行必须带 external_url/source_url/url/link 字段。",
    ),
    "json": _policy(
        "json",
        "JSON 导入",
        "file",
        acquisition_methods=("manual_browser", "webhook"),
        allow_any_domain=True,
        notes="JSON 每一项必须带 external_url/source_url/url/link 字段。",
    ),
    "api": _policy(
        "api",
        "外部 API",
        "custom",
        acquisition_methods=("official_api", "webhook", "manual_browser"),
        allow_any_domain=True,
        notes="外部 API 数据必须提供原始页面 URL 或源系统可点击 URL。",
    ),
    "webhook": _policy(
        "webhook",
        "Webhook",
        "custom",
        acquisition_methods=("webhook", "manual_browser"),
        allow_any_domain=True,
        notes="Webhook payload 必须携带原始页面 URL 或源系统可点击 URL。",
    ),
    "custom": _policy(
        "custom",
        "自定义来源",
        "custom",
        acquisition_methods=("official_api", "crawler", "manual_browser", "browser_screenshot", "webhook"),
        allow_any_domain=True,
        notes="自定义来源仍必须提供真实可点击原始 URL。",
    ),
}


def get_source_platform_policy(source_type: str) -> SourcePlatformPolicy:
    """Return the policy for *source_type*, falling back to the custom policy."""
    key = (source_type or "").strip()
    return SOURCE_PLATFORM_POLICIES.get(key) or SOURCE_PLATFORM_POLICIES["custom"]


def is_supported_source_type(source_type: str) -> bool:
    """Return whether *source_type* has a first-class platform policy."""
    return (source_type or "").strip() in SOURCE_PLATFORM_POLICIES


def validate_required_source_url(
    source_type: str,
    url: str | None,
    *,
    source_id: str | None = None,
    capture_method: str | None = None,
) -> str:
    """Validate and normalize an import source URL.

    The validation is intentionally deterministic and does not fetch the URL.
    Many target sites reject HEAD/GET probes, require login, or vary by IP.
    Runtime verification is therefore handled by requiring an explicit URL,
    rejecting placeholders, checking the URL host against the selected platform
    policy, and preserving the capture method for audit.
    """
    policy = get_source_platform_policy(source_type)
    candidate = (url or "").strip()
    if not candidate:
        raise SourceUrlValidationError("导入数据必须提供真实来源 URL，不能为空。")

    if not is_clickable_source_url(candidate, source_id=source_id):
        raise SourceUrlValidationError(
            "来源 URL 不是可点击的真实原始页面，请不要使用 example、mock、"
            "本地地址或演示链接。"
        )

    parsed = urlparse(candidate)
    host = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not host:
        raise SourceUrlValidationError("来源 URL 必须是 http(s) 开头的完整地址。")

    method = (capture_method or "manual_browser").strip()
    if method not in CAPTURE_METHOD_LABELS:
        raise SourceUrlValidationError(f"未知数据获得方法：{method}")
    if method not in policy.acquisition_methods:
        allowed = "、".join(CAPTURE_METHOD_LABELS[m] for m in policy.acquisition_methods)
        raise SourceUrlValidationError(f"{policy.label} 不支持该数据获得方法，可选：{allowed}。")

    if not policy.allow_any_domain and not _host_matches_any(host, policy.allowed_domains):
        domains = "、".join(policy.allowed_domains)
        raise SourceUrlValidationError(
            f"{policy.label} 的来源 URL 必须来自对应站点域名：{domains}。"
        )

    if policy.source_url_rule == "search_result_target_url" and _looks_like_search_results_page(
        source_type,
        host,
        parsed.path,
    ):
        raise SourceUrlValidationError(
            f"{policy.label} 的证据 URL 必须是搜索结果落地页，不能是搜索结果列表页。"
        )

    return candidate


def _host_matches_any(host: str, allowed_domains: tuple[str, ...]) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def _looks_like_search_results_page(source_type: str, host: str, path: str) -> bool:
    key = (source_type or "").strip()
    normalized_path = path.rstrip("/") or "/"
    if key == "baidu_search":
        return host in {"www.baidu.com", "m.baidu.com"} and normalized_path in {"/s", "/ssid"}
    if key == "google_search":
        return host.endswith("google.com") and normalized_path == "/search"
    if key == "sogou_search":
        return host in {"www.sogou.com", "m.sogou.com"} and normalized_path in {"/web", "/sogou"}
    if key == "so360_search":
        return host in {"www.so.com", "m.so.com"} and normalized_path == "/s"
    if key == "bing_search":
        return host.endswith("bing.com") and normalized_path == "/search"
    return False


__all__ = [
    "CAPTURE_METHOD_LABELS",
    "SOURCE_PLATFORM_POLICIES",
    "SourcePlatformPolicy",
    "SourceUrlValidationError",
    "get_source_platform_policy",
    "is_supported_source_type",
    "validate_required_source_url",
]
