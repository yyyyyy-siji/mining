"""Bounded official Zhihu search leads, deliberately not full-text evidence.

The caller supplies the O2 streamed HTTP client and owns its concurrency lock.
No credentials, request headers, database writes or LLM calls enter the output.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from urllib.parse import parse_qsl, urlsplit

import httpx

ZHIHU_SEARCH_URL = "https://developer.zhihu.com/api/v1/content/zhihu_search"
ZHIHU_SETUP_URL = "https://developer.zhihu.com/profile"
_AUTH_KEYS = {
    "authorization", "proxyauthorization", "accesssecret", "zhihuaccesssecret",
    "accesstoken", "bearertoken", "auth", "token", "secret", "apikey", "password",
}


class ZhihuSearchError(ValueError):
    """Safe public error; never stores the original upstream body or headers."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


def _invalid_response() -> ZhihuSearchError:
    return ZhihuSearchError(502, "知乎搜索响应结构或来源校验失败，未生成线索。")


def _check_no_auth(value: object, secret: str) -> None:
    """Refuse echoed credentials rather than silently altering the raw item."""
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = re.sub(r"[^a-z]", "", str(key).lower())
            if normalized in _AUTH_KEYS:
                raise _invalid_response()
            _check_no_auth(nested, secret)
    elif isinstance(value, list):
        for nested in value:
            _check_no_auth(nested, secret)
    elif isinstance(value, str) and secret and secret in value:
        raise _invalid_response()


def _string(item: dict, key: str, *, nonempty: bool = False) -> str:
    value = item.get(key)
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise _invalid_response()
    return value


def _source_time(item: dict, key: str) -> str | None:
    value = item.get(key)
    if value is None or (value == 0 and not isinstance(value, bool)):
        return None
    if type(value) is not int or value < 0:
        raise _invalid_response()
    try:
        return datetime.fromtimestamp(value, timezone.utc).isoformat()
    except (ValueError, OverflowError, OSError) as exc:
        raise _invalid_response() from exc


def _validate_source_url(value: str, entity_type: str, external_id: str) -> None:
    try:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https" or parsed.username or parsed.password
            or parsed.port is not None or any(ord(c) < 33 for c in value)
        ):
            raise _invalid_response()
        host = parsed.hostname
    except ValueError as exc:
        raise _invalid_response() from exc
    paths = {
        "question": (r"/question/(\d+)/?", {"www.zhihu.com", "zhihu.com"}),
        "answer": (r"/(?:question/\d+/)?answer/(\d+)/?", {"www.zhihu.com", "zhihu.com"}),
        "article": (r"/p/(\d+)/?", {"zhuanlan.zhihu.com"}),
    }
    pattern, hosts = paths[entity_type]
    match = re.fullmatch(pattern, parsed.path)
    if host not in hosts or match is None or match.group(1) != external_id:
        raise _invalid_response()
    for key, _ in parse_qsl(parsed.query):
        if re.sub(r"[^a-z]", "", key.lower()) in _AUTH_KEYS:
            raise _invalid_response()


def _lead(item: object, *, search_hash_id: str, params: dict, captured_at: str) -> dict:
    if not isinstance(item, dict):
        raise _invalid_response()
    title = _string(item, "Title")
    excerpt = _string(item, "ContentText")
    external_id = _string(item, "ContentID", nonempty=True)
    if not re.fullmatch(r"\d+", external_id):
        raise _invalid_response()
    entity_type = _string(item, "ContentType", nonempty=True).lower()
    if entity_type not in {"question", "answer", "article"}:
        raise _invalid_response()
    source_url = _string(item, "Url", nonempty=True)
    _validate_source_url(source_url, entity_type, external_id)
    comments = item.get("CommentInfoList", [])
    if not isinstance(comments, list) or any(not isinstance(comment, dict) for comment in comments):
        raise _invalid_response()
    curated_comments = [_string(comment, "Content") for comment in comments]
    author_name = item.get("AuthorName")
    if author_name is not None and not isinstance(author_name, str):
        raise _invalid_response()
    for key in ("CommentCount", "VoteUpCount"):
        if key in item and (type(item[key]) is not int or item[key] < 0):
            raise _invalid_response()
    for key in ("AuthorAvatar", "AuthorBadge", "AuthorBadgeText", "AuthorityLevel"):
        if key in item and not isinstance(item[key], str):
            raise _invalid_response()
    if "RankingScore" in item and type(item["RankingScore"]) not in {int, float}:
        raise _invalid_response()
    created = _source_time(item, "CreateTime")
    updated = _source_time(item, "EditTime")
    provenance = {
        "platform": "zhihu", "capture_method": "official_api",
        "acquisition_version": "zhihu-search-v1", "content_nature": "api_excerpt",
        "coverage": "search_excerpt", "source_url": source_url,
        "external_id": external_id, "entity_type": entity_type,
        "source_captured_at": captured_at,
        "excerpt_sha256": hashlib.sha256(excerpt.encode("utf-8")).hexdigest(),
        "curated_comments_nature": "curated_comment",
        "curated_comments_limitation": "仅精选内容；未提供独立评论ID、作者、时间或直达链接。",
        "raw_payload": {
            "original": item, "search_hash_id": search_hash_id,
            "request": dict(params), "captured_at": captured_at,
        },
    }
    result = {
        "title": title, "excerpt": excerpt, "curated_comments": curated_comments,
        "source_url": source_url, "external_id": external_id,
        "entity_type": entity_type, "content_nature": "api_excerpt",
        "source_captured_at": captured_at, "author_name": author_name or None,
        "provenance": provenance,
    }
    for key, value in (("source_created_at", created), ("source_updated_at", updated)):
        if value is not None:
            result[key] = value
            provenance[key] = value
    return result


def preview_zhihu_search(
    client: httpx.Client, *, access_secret: str, query: str,
    count: int = 5, days: int = 30, now: datetime | None = None,
) -> dict:
    """One fixed-endpoint request; search excerpts stay separate from evidence."""
    if not access_secret or not access_secret.strip():
        raise ZhihuSearchError(503, "知乎官方搜索未配置：请在本机服务端设置 ZHIHU_ACCESS_SECRET 后重启。")
    if not isinstance(query, str) or not query.strip() or len(query) > 200:
        raise ZhihuSearchError(400, "知乎搜索关键词须为 1 至 200 个字符。")
    if type(count) is not int or not 1 <= count <= 10 or type(days) is not int or not 1 <= days <= 365:
        raise ZhihuSearchError(400, "知乎搜索数量或创建时间范围不合法。")
    captured = now or datetime.now(timezone.utc)
    if captured.tzinfo is None or captured.utcoffset() is None:
        raise ValueError("Search capture time must be timezone aware")
    captured = captured.astimezone(timezone.utc)
    lower = int((captured - timedelta(days=days)).timestamp())
    upper = int(captured.timestamp())
    params = {"Query": query.strip(), "Count": count, "SortBy": f"CreateTime:desc:({lower},{upper})"}
    try:
        response = client.get(
            ZHIHU_SEARCH_URL, params=params,
            headers={
                "Authorization": f"Bearer {access_secret}",
                "X-Request-Timestamp": str(upper), "Content-Type": "application/json",
            },
            follow_redirects=False,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        if code in {401, 403}:
            raise ZhihuSearchError(502, "知乎官方搜索鉴权失败，请检查本机 Access Secret 和系统时间。") from None
        if code == 429:
            raise ZhihuSearchError(429, "知乎搜索频率或额度受限，请稍后重试。") from None
        if code == 400:
            raise ZhihuSearchError(400, "知乎官方搜索拒绝请求参数，未生成线索。") from None
        raise ZhihuSearchError(502, "知乎官方搜索请求失败，未生成线索。") from None
    try:
        payload = response.json()
    except (ValueError, UnicodeDecodeError):
        raise _invalid_response() from None
    if not isinstance(payload, dict) or type(payload.get("Code")) is not int:
        raise _invalid_response()
    errors = {
        10001: (400, "知乎官方搜索拒绝请求参数，未生成线索。"),
        20001: (502, "知乎官方搜索鉴权失败，请检查本机 Access Secret 和系统时间。"),
        30001: (429, "知乎搜索频率或额度受限，请稍后重试。"),
        90001: (502, "知乎官方搜索服务异常，未生成线索。"),
    }
    code = payload["Code"]
    if code != 0:
        status_code, detail = errors.get(code, (502, "知乎官方搜索返回未知错误，未生成线索。"))
        raise ZhihuSearchError(status_code, detail)
    data = payload.get("Data")
    if not isinstance(data, dict):
        raise _invalid_response()
    _check_no_auth(data, access_secret)
    items = data.get("Items")
    search_hash_id = _string(data, "SearchHashId", nonempty=True)
    if not isinstance(items, list) or len(items) > count or type(data.get("HasMore")) is not bool:
        raise _invalid_response()
    if "EmptyReason" in data and not isinstance(data["EmptyReason"], str):
        raise _invalid_response()
    captured_at = captured.isoformat()
    leads = [_lead(item, search_hash_id=search_hash_id, params=params, captured_at=captured_at) for item in items]
    result = {
        "leads": leads,
        "summary": {
            "source": "zhihu", "capture_method": "official_api",
            "status": "ok" if leads else "empty", "requests": 1,
            "query": params["Query"], "count": count, "days": days,
            "sort_by": params["SortBy"], "time_filter": "source_created_at",
            "created_from": (captured - timedelta(days=days)).isoformat(),
            "created_to": captured_at, "source_captured_at": captured_at,
            "search_hash_id": search_hash_id, "has_more": data["HasMore"],
            "collected": len(leads), "written": 0,
            "content_nature": "api_excerpt", "opportunity_analysis_allowed": False,
            "limitation": "检索摘要及精选评论仅作线索；补充原文材料后才能用于机会分析。",
        },
    }
    if data.get("EmptyReason"):
        result["summary"]["empty_reason"] = data["EmptyReason"]
    # Validate the exportable structure as JSON without serializing any request.
    json.dumps(result, ensure_ascii=False, allow_nan=False)
    _check_no_auth(result, access_secret)
    return result
