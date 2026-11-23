"""Bounded adapters for MediaCrawler's pinned, normalized export records.

These are not platform HTTP responses. No network, database or model calls occur here.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
import re
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from pathlib import Path

PIN = "54a3d92412f4b20c06b45f1d542b78dd92049d6d"
PLATFORMS = {"xhs": "xiaohongshu", "bili": "bilibili", "wb": "weibo"}
MAX_FILE_BYTES = 2_000_000
MAX_TOTAL_BYTES = 8_000_000
MAX_EXPORT_ROWS = 200


class ExportError(ValueError):
    """Unsafe, oversized or invalid task export."""


def validate_item_url(platform: str, value: str) -> str:
    """Accept item pages only; retain content access parameters verbatim."""
    try:
        if not isinstance(value, str) or len(value) > 2000 or "," in value or any(ord(char) < 32 for char in value):
            raise ValueError
        parsed = urlsplit(value)
        if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port:
            raise ValueError
        host, path = (parsed.hostname or "").lower(), parsed.path
        valid = (
            platform == "xhs" and host in {"www.xiaohongshu.com", "xiaohongshu.com"}
            and re.fullmatch(r"/(?:explore|discovery/item)/[a-fA-F0-9]{24}/?", path)
        ) or (
            platform == "bili" and host in {"www.bilibili.com", "bilibili.com"}
            and re.fullmatch(r"/video/(?:BV[A-Za-z0-9]{10}|av[0-9]+)/?", path)
        ) or (
            platform == "wb" and (
                host == "m.weibo.cn" and re.fullmatch(r"/(?:detail|status)/[0-9A-Za-z]+/?", path)
                or host in {"www.weibo.com", "weibo.com"}
                and re.fullmatch(r"/[0-9]+/[0-9A-Za-z]+/?", path)
            )
        )
        if not valid:
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("请提供所选平台的单个正文链接（https）。") from exc
    return value


def source_time(value, *, milliseconds: bool) -> str | None:
    if value in (None, "", 0, "0") or isinstance(value, bool):
        return None
    try:
        stamp = float(value) / (1000 if milliseconds else 1)
        result = datetime.fromtimestamp(stamp, timezone.utc)
        if result.year < 2000 or result.year > 2100:
            return None
        return result.isoformat()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _identifier(value) -> str | None:
    if value in (None, "", 0, "0") or isinstance(value, (dict, list, bool)):
        return None
    return str(value)


def _has_credentials(value) -> bool:
    if isinstance(value, dict):
        return any(
            re.sub(r"[-_]", "", str(k).lower()) in {
                "cookie", "cookies", "setcookie", "authorization", "proxyauthorization",
                "accesstoken", "refreshtoken", "apikey", "accesssecret", "token",
                "headers", "session", "sessionid", "password", "secret", "storagestate",
                "localstorage", "sessionstorage",
            } or _has_credentials(v) for k, v in value.items()
        )
    return isinstance(value, list) and any(_has_credentials(v) for v in value)


def read_task_exports(task_dir: Path, *, platform: str, mode: str, started_at: str):
    """Read only this task's exact export layout, never shared historical data."""
    root = task_dir.resolve()
    data = task_dir / "data"
    rows = {"contents": [], "comments": []}
    total = count = 0
    started = datetime.fromisoformat(started_at).timestamp()
    if data.is_symlink():
        raise ExportError("invalid_output_path")
    if not data.exists():
        return rows
    files = list(data.rglob("*"))
    if len(files) > 24:
        raise ExportError("too_many_output_files")
    for path in files:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ExportError("invalid_output_path")
        if path.is_dir():
            continue
        relative = path.relative_to(data)
        match = re.fullmatch(rf"{re.escape(mode)}_(contents|comments)_\d{{4}}-\d{{2}}-\d{{2}}\.(jsonl|json)", path.name)
        if len(relative.parts) != 3 or relative.parts[0] != platform or relative.parts[1] not in {"json", "jsonl"} or not match or relative.parts[1] != match[2]:
            raise ExportError("unexpected_output_file")
        size = path.stat().st_size
        total += size
        if size > MAX_FILE_BYTES or total > MAX_TOTAL_BYTES:
            raise ExportError("output_size_limit")
        if path.stat().st_mtime < started - 1:
            raise ExportError("stale_output")
        try:
            with path.open(encoding="utf-8") as stream:
                records = json.load(stream) if match[2] == "json" else [json.loads(line) for line in stream if line.strip()]
            if not isinstance(records, list) or not all(isinstance(row, dict) for row in records):
                raise ValueError
            json.dumps(records, allow_nan=False)  # reject NaN/Infinity, including overflowed floats
        except (ValueError, UnicodeError) as exc:
            raise ExportError("invalid_export") from exc
        count += len(records)
        if count > MAX_EXPORT_ROWS:
            raise ExportError("export_row_limit")
        rows[match[1]].extend(records)
    return rows


def adapt_exports(records: dict, task: dict) -> dict:
    platform = task["platform"]
    if platform not in PLATFORMS:
        raise ExportError("unsupported_platform")
    post_id_field = "video_id" if platform == "bili" else "note_id"
    url_field = "video_url" if platform == "bili" else "note_url"
    body_field = {"xhs": "desc", "bili": "desc", "wb": "content"}[platform]
    time_field = "time" if platform == "xhs" else "create_time"
    skip = Counter()
    items, parents, seen = [], {}, set()
    emitted_posts = set()
    comment_counts = Counter()
    coverage = {
        "xhs": "笔记描述正文及最多8条一级评论；不含媒体、图片文字或楼中楼。",
        "bili": "视频简介片段（上游最多500字符），不是视频口播；最多8条一级评论。",
        "wb": "微博导出正文；上游尝试展开长文但不保证完整；最多8条一级评论，不含楼中楼。",
    }[platform]

    def parent_metadata(row):
        if _has_credentials(row):
            skip["credential_fields"] += 1
            return None
        external_id = _identifier(row.get(post_id_field))
        url = row.get(url_field)
        try:
            validate_item_url(platform, url)
        except ValueError:
            skip["invalid_source_url"] += 1
            return None
        url_id = urlsplit(url).path.rstrip("/").split("/")[-1]
        if not external_id or url_id != (f"av{external_id}" if platform == "bili" else external_id):
            skip["source_id_url_mismatch"] += 1
            return None
        return {"external_id": external_id, "external_url": url}

    def make(row, *, comment=False, parent=None):
        if comment and _has_credentials(row):
            skip["credential_fields"] += 1
            return None
        text = row.get("content" if comment else body_field)
        if not isinstance(text, str) or not text.strip():
            skip["missing_body"] += 1
            return None
        external_id = _identifier(row.get("comment_id" if comment else post_id_field))
        url = parent["external_url"] if comment else row.get(url_field)
        try:
            validate_item_url(platform, url)
        except ValueError:
            skip["invalid_source_url"] += 1
            return None
        key = ("comment" if comment else "post", external_id, url, text)
        if key in seen:
            skip["duplicate_export"] += 1
            return None
        seen.add(key)
        created = source_time(row.get("create_time" if comment else time_field), milliseconds=platform == "xhs")
        updated = source_time(row.get("last_update_time"), milliseconds=True) if platform == "xhs" and not comment else None
        metadata = {key: task.get(key) for key in ("id", "platform", "mode", "query", "url", "max_posts", "max_comments", "started_at", "ended_at")}
        return {
            "source_type": PLATFORMS[platform], "platform": PLATFORMS[platform],
            "pipeline_profile": "product_feedback", "capture_method": "crawler",
            "subject": (row.get("title") if not comment else None), "text": text,
            "author_name": None, "external_id": external_id, "external_url": url,
            "entity_type": "comment" if comment else "video" if platform == "bili" else "post",
            "parent_id": parent["external_id"] if comment else None,
            "parent_url": parent["external_url"] if comment else None,
            "parent_comment_id": _identifier(row.get("parent_comment_id")) if comment else None,
            "locator_level": "parent_page" if comment else "item",
            "content_nature": "original_text", "text_origin": "body",
            "source_created_at": created, "source_updated_at": updated,
            "source_captured_at": source_time(row.get("last_modify_ts") or row.get("add_ts"), milliseconds=True),
            "capture_version": f"MediaCrawler@{PIN}",
            "coverage_scope": coverage,
            "source_note": "上游规范化导出记录，非平台原始HTTP响应；nickname已遮蔽、creator_hash为匿名化标识，原作者未知；真实性未认证。" + ("评论仅定位父页。" if comment else ""),
            "raw_payload": {"acquisition_kind": "mediacrawler_normalized_export", "upstream_pin": PIN,
                "task": metadata, "record": row,
                "timestamp_semantics": {"source": "milliseconds" if platform == "xhs" else "seconds",
                    "add_ts": "collector_milliseconds_if_present", "last_modify_ts": "collector_milliseconds_if_present"},
                "coverage_scope": coverage, "author_semantics": "masked_nickname_and_anonymized_creator_hash; original_author_unknown"},
        }

    for row in records.get("contents", []):
        metadata = parent_metadata(row)
        if not metadata:
            continue
        parent_id = metadata["external_id"]
        if parent_id not in parents and len(parents) >= task["max_posts"]:
            skip["post_limit"] += 1
            continue
        if parent_id in emitted_posts:
            skip["duplicate_parent_record"] += 1
            continue
        parents.setdefault(parent_id, metadata)
        item = make(row)
        if item:
            items.append(item)
            emitted_posts.add(parent_id)
    for row in records.get("comments", []):
        parent_id = _identifier(row.get(post_id_field))
        parent = parents.get(parent_id)
        if not parent:
            skip["missing_task_parent"] += 1
            continue
        if _identifier(row.get("parent_comment_id")):
            skip["sub_comment_not_covered"] += 1
            continue
        if comment_counts[parent_id] >= task["max_comments"] or len(items) >= 30:
            skip["comment_limit"] += 1
            continue
        item = make(row, comment=True, parent=parent)
        if item:
            items.append(item)
            comment_counts[parent_id] += 1
    return {"items": items, "summary": {"returned": len(items), "posts": sum(item["entity_type"] != "comment" for item in items), "parent_objects": len(parents),
        "comments": sum(comment_counts.values()), "skip_reasons": dict(skip),
        "max_posts": task["max_posts"], "max_comments_per_post": task["max_comments"],
        "coverage_note": coverage, "upstream_pin": PIN,
        "authenticity": "not_verified", "raw_record_kind": "upstream_normalized_export"}}
