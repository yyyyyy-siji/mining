"""Platform URL validation and DOM-to-feedback adaptation for ExistingChromeCollector."""
from __future__ import annotations

from datetime import datetime, timezone
import re
from urllib.parse import quote, urlsplit

CAPTURE_VERSION = "mining-existing-chrome-dom/v1"
SELECTOR_VERSION = "xhs-public-note-dom/v1"
HOSTS = {"xiaohongshu.com", "www.xiaohongshu.com"}
NOTE_PATH = re.compile(r"/(?:explore|discovery/item)/([a-fA-F0-9]{24})/?$")
SUPPORTED_PLATFORMS = ("xiaohongshu", "bilibili", "weibo", "zhihu", "douyin")
TERMINAL = {"completed", "failed", "cancelled"}
MAX_TEXT = 100_000
MAX_POSTS = 20
MAX_COMMENTS = 50
DEFAULT_TASK_TIMEOUT = 300

PLATFORM_CONFIGS = {
    "xiaohongshu": {
        "label": "小红书",
        "hosts": {"xiaohongshu.com", "www.xiaohongshu.com"},
        "detail_pattern": NOTE_PATH,
        "non_detail_paths": {"", "/explore", "/search_result", "/search_result_ai"},
        "selector_version": "xhs-public-note-dom/v1",
        "search_url": lambda q: "https://www.xiaohongshu.com/search_result?keyword=" + quote(q, safe="") + "&type=51",
        "search_query_keys": ("keyword", "type"),
        "comment_id_pattern": re.compile(r"[a-fA-F0-9]{24}"),
    },
    "bilibili": {
        "label": "B站",
        "hosts": {"bilibili.com", "www.bilibili.com", "search.bilibili.com"},
        "detail_pattern": re.compile(r"/video/(BV[A-Za-z0-9]+|av[0-9]+)/?"),
        "non_detail_paths": {"", "/all"},
        "selector_version": "bili-public-video-dom/v1",
        "search_url": lambda q: "https://search.bilibili.com/all?keyword=" + quote(q, safe=""),
        "search_query_keys": ("keyword",),
        "comment_id_pattern": re.compile(r"[0-9A-Za-z_-]{1,64}"),
    },
    "weibo": {
        "label": "微博",
        "hosts": {"weibo.com", "www.weibo.com", "s.weibo.com"},
        "detail_pattern": re.compile(r"/(?:[0-9]+/([A-Za-z0-9]+)|detail/([0-9]+))/?"),
        "non_detail_paths": {"", "/weibo", "/hot", "/hot/search", "/newlogin", "/mygroups", "/top/summary", "/realtime"},
        "non_detail_prefix": ("/hot/", "/u/"),
        "selector_version": "wb-public-post-dom/v1",
        "search_url": lambda q: "https://s.weibo.com/weibo?q=" + quote(q, safe=""),
        "search_query_keys": ("q",),
        "comment_id_pattern": re.compile(r"[0-9A-Za-z_-]{1,64}"),
    },
    "zhihu": {
        "label": "知乎",
        "hosts": {"zhihu.com", "www.zhihu.com", "zhuanlan.zhihu.com"},
        "detail_pattern": re.compile(r"/(?:question/[0-9]+/answer/([0-9]+)|question/([0-9]+)|p/([0-9]+))/?"),
        "non_detail_paths": {"", "/search", "/hot", "/follow", "/explore", "/waiting", "/knowledge-plan"},
        "non_detail_prefix": ("/topic/", "/column/", "/people/"),
        "selector_version": "zhihu-public-content-dom/v1",
        "search_url": lambda q: "https://www.zhihu.com/search?type=content&q=" + quote(q, safe=""),
        "search_query_keys": ("q",),
        "comment_id_pattern": re.compile(r"[0-9A-Za-z_-]{1,64}"),
    },
    "douyin": {
        "label": "抖音",
        "hosts": {"douyin.com", "www.douyin.com"},
        "detail_pattern": re.compile(r"/(?:video|note)/([0-9]{10,25})/?"),
        "non_detail_paths": {"", "/discover", "/jingxuan", "/follow", "/friend", "/hot", "/channel"},
        "non_detail_prefix": ("/search/", "/user/", "/channel/", "/jingxuan/"),
        "selector_version": "douyin-public-video-dom/v1",
        "search_url": lambda q: "https://www.douyin.com/search/" + quote(q, safe="") + "?type=video",
        "search_query_keys": (),
        "comment_id_pattern": re.compile(r"[0-9A-Za-z_-]{1,64}"),
    },
}


def detect_platform(value: str | None) -> str | None:
    """Return supported platform key for an HTTPS URL, or None."""
    if not isinstance(value, str):
        return None
    try:
        parsed = urlsplit(value)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    host = parsed.hostname.lower()
    for platform, cfg in PLATFORM_CONFIGS.items():
        if host in cfg["hosts"]:
            return platform
    return None


def _extract_detail_id(platform: str, path: str) -> str | None:
    match = PLATFORM_CONFIGS[platform]["detail_pattern"].fullmatch(path)
    if not match:
        return None
    for group in match.groups():
        if group:
            return group
    return None


class ChromeError(ValueError):
    """Safe, deterministic error suitable for the UI; never carries CDP data."""

    def __init__(self, code: str, message: str, status_code: int = 409):
        super().__init__(code)
        self.code, self.message, self.status_code = code, message, status_code


def validate_url(value: str, *, note: bool = False, platform: str | None = None) -> str:
    """Only exact domestic HTTPS supported platform public pages, without authority tricks."""
    try:
        if not isinstance(value, str) or len(value) > 4000 or any(
            ord(char) < 33 or char in "\\,#" for char in value
        ):
            raise ValueError
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or parsed.username or parsed.password or parsed.port is not None
            or parsed.fragment
        ):
            raise ValueError
        resolved_platform = platform or detect_platform(value)
        if resolved_platform not in PLATFORM_CONFIGS:
            raise ValueError
        cfg = PLATFORM_CONFIGS[resolved_platform]
        if (parsed.hostname or "").lower() not in cfg["hosts"]:
            raise ValueError
        is_note = bool(cfg["detail_pattern"].fullmatch(parsed.path))
        normalized_path = parsed.path.rstrip("/")
        is_entry = normalized_path in cfg["non_detail_paths"] or any(
            parsed.path.startswith(prefix) for prefix in cfg.get("non_detail_prefix", ())
        )
        if not is_note and (note or not is_entry):
            raise ValueError
        return value
    except (TypeError, ValueError) as exc:
        raise ChromeError("invalid_target_url", "仅支持国内小红书、B站、微博、知乎或抖音 HTTPS 首页、搜索页或详情链接。", 422) from exc



def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _absolute_time(value) -> str | None:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d\d-\d\dT\d\d:\d\d(?::\d\d(?:\.\d+)?)?(?:Z|[+-]\d\d:\d\d)", value
    ):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def adapt_dom(record: dict, task: dict) -> dict:
    """Whitelist public DOM values and retain unknown IDs/times as null."""
    platform = task.get("platform") or detect_platform(record.get("url")) or "xiaohongshu"
    pipeline_profile = task.get("pipeline_profile") or "product_feedback"
    cfg = PLATFORM_CONFIGS[platform]
    source_url = validate_url(record.get("url"), note=True, platform=platform)
    post_id = _extract_detail_id(platform, urlsplit(source_url).path)
    body = record.get("body")
    if not isinstance(body, str) or not body.strip():
        raise ChromeError("body_missing", "未找到已加载的正文内容；标题不能代替正文。")
    captured = _now()
    has_subtitles = bool(record.get("has_subtitles"))
    subtitle_lang = record.get("subtitle_language") or "CC/AI"
    incomplete = [
        f"已包含视频字幕逐字稿（{subtitle_lang}）；不包含无字幕画面文字。"
        if has_subtitles
        else "只覆盖本次已加载的 DOM；不包含图片文字、视频口播或未加载评论。"
    ]
    if record.get("body_clipped"):
        incomplete.append("正文容器存在折叠或裁剪，当前材料为片段。")
    if record.get("body_limit") or len(body) > MAX_TEXT:
        incomplete.append("正文超过 100000 字符安全上限，当前材料为片段。")
    if not record.get("comment_container_present") and task["max_comments"]:
        incomplete.append("未找到已加载评论容器，本次未覆盖评论。")
    elif task["max_comments"] and not record.get("comments") and not record.get("comment_empty_explicit"):
        incomplete.append("等待已加载评论达到上限，未见评论或明确空状态；本次评论覆盖未知，不能认定真实零评论。")
    coverage = f"1 篇已加载正文内容，最多 {task['max_comments']} 条已加载顶层评论；不遍历或加载更多。"
    cid_pattern = cfg["comment_id_pattern"]

    def make(text, *, comment=None):
        is_comment = comment is not None
        stamp = comment if is_comment else record
        cid = stamp.get("comment_id") if is_comment else post_id
        if is_comment and not (isinstance(cid, str) and cid_pattern.fullmatch(cid)):
            cid = None
        parent_cid = stamp.get("parent_comment_id") if is_comment else None
        if not isinstance(parent_cid, str) or not cid_pattern.fullmatch(parent_cid):
            parent_cid = None
        return {
            "source_type": platform, "platform": platform,
            "pipeline_profile": pipeline_profile, "capture_method": "manual_browser" if platform == "douyin" else "crawler",
            "capture_version": CAPTURE_VERSION, "text": text[:MAX_TEXT],
            "subject": None if is_comment or not isinstance(record.get("title"), str) else record["title"][:5000],
            "external_url": source_url, "external_id": cid,
            "entity_type": "comment" if is_comment else "post",
            "parent_id": post_id if is_comment else None,
            "parent_url": source_url if is_comment else None,
            "parent_comment_id": parent_cid, "parent_comment_url": None,
            "locator_level": "parent_page" if is_comment else "item",
            "content_nature": "original_text", "text_origin": "body",
            "source_created_at": _absolute_time(stamp.get("source_created_at")),
            "source_updated_at": None, "source_captured_at": captured,
            "coverage_scope": coverage,
            "source_note": "项目自有固定选择器读取当前 Chrome 已加载公开 DOM；非 MediaCrawler 导出。作者未知；来源真实性未认证。" + ("评论仅定位父页，未知评论ID和楼层保持空值。" if is_comment else "") + " ".join(incomplete),
            "raw_payload": {
                "acquisition_kind": "existing_chrome_loaded_dom",
                "capture_version": CAPTURE_VERSION, "selector_version": cfg["selector_version"],
                "source_url": source_url, "object_id": cid,
                "source_time_display": stamp.get("source_time_display"),
                "body_fragment": bool(record.get("body_clipped") or record.get("body_limit") or len(body) > MAX_TEXT),
                "has_subtitles": has_subtitles,
                "subtitle_language": record.get("subtitle_language"),
                "coverage_scope": coverage, "incomplete_reasons": list(incomplete),
                "task": {key: task[key] for key in ("id", "mode", "max_posts", "max_comments")},
            },
        }

    items = [make(body)]
    comments = record.get("comments") if isinstance(record.get("comments"), list) else []
    for comment in comments:
        if len(items) > task["max_comments"]:
            break
        if not isinstance(comment, dict) or not isinstance(comment.get("text"), str) or not comment["text"].strip():
            continue
        # A directly evidenced reply is outside the first version's top-level scope.
        if comment.get("parent_comment_id"):
            continue
        item = make(comment["text"], comment=comment)
        if comment.get("text_truncated") or len(comment["text"]) > MAX_TEXT:
            item["raw_payload"]["incomplete_reasons"].append("该评论超过 100000 字符安全上限，当前为片段。")
        items.append(item)
    return {"items": items, "summary": {
        "post_count": 1, "comment_count": len(items) - 1, "item_count": len(items),
        "comment_coverage": "not_requested" if not task["max_comments"] else "loaded_comments" if len(items) > 1 else "explicit_empty" if record.get("comment_empty_explicit") else "unknown",
        "coverage": coverage, "incomplete_reasons": incomplete,
        "capture_version": CAPTURE_VERSION, "source_captured_at": captured,
    }}


