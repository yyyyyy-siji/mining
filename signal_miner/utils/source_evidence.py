"""Versioned source snapshots: local integrity, never platform authentication."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

if TYPE_CHECKING:
    from signal_miner.db.models import RawFeedbackRow

VERSION = "source-evidence/v1"
_SECRET_KEYS = {
    "authorization", "proxyauthorization", "secret", "accesssecret", "zhihuaccesssecret",
    "apikey", "accesstoken", "refreshtoken", "cookie", "setcookie", "password",
}
_SOURCE_FIELDS = (
    "platform", "entity_type", "parent_id", "parent_url", "parent_comment_id",
    "parent_comment_url", "locator_level", "content_nature", "coverage_scope",
    "capture_version", "text_origin", "source_updated_at",
)


def redact_credentials(value: Any) -> Any:
    """Never retain/export request authorization or configuration credential keys."""
    if isinstance(value, dict):
        return {
            key: "[redacted]" if "".join(c for c in str(key).lower() if c.isalnum()) in _SECRET_KEYS
            else redact_credentials(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_credentials(item) for item in value]
    return value


def utc_iso(value: datetime | str | None, *, persisted: bool = False) -> str | None:
    """Normalize aware source time; SQLite persisted UTC values may lose tzinfo."""
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        if not persisted:
            raise ValueError("来源时间必须包含时区。")
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def body_digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def body_text(content: dict) -> tuple[str, str]:
    """One actual body field only; titles are never used as a fallback."""
    for key in ("text", "body", "content"):
        text = content.get(key)
        if isinstance(text, str) and text.strip():
            return text, f"content.{key}"
    return "", "content.text"


def _snapshot_material(package: dict, content: dict) -> dict:
    material = {key: value for key, value in package.items() if key != "snapshot_sha256"}
    text, quote_field = body_text(content)
    material["body_sha256"] = body_digest(text)
    material["quote_field"] = quote_field
    # FeedbackContent adds optional language=None on persistence. Only exact
    # title and the one body field are part of this version's content scope.
    material["content"] = {"subject": content.get("subject"), "body": text}
    return material


def _author_fields(author: dict | None) -> dict:
    author = author if isinstance(author, dict) else {}
    return {key: author.get(key) for key in ("name", "email", "external_id", "company", "segment", "mrr")}


def _context_digest(context: dict) -> str:
    return digest({key: value for key, value in context.items() if key != "source_evidence"})


def build_source_evidence(
    *, source_type: str, external_id: str | None, external_url: str,
    source_created_at: datetime | None, content: dict, context: dict, author: dict | None = None,
) -> dict:
    text, quote_field = body_text(content)
    package = {
        "version": VERSION, "source_type": source_type,
        "platform": context.get("platform") or source_type,
        "entity_type": context.get("entity_type") or "unknown",
        "external_id": external_id, "original_url": external_url,
        "parent_id": context.get("parent_id"), "parent_url": context.get("parent_url"),
        "parent_comment_id": context.get("parent_comment_id"),
        "parent_comment_url": context.get("parent_comment_url"),
        "locator_level": context.get("locator_level") or "unknown",
        "content_nature": context.get("content_nature") or "manual_text",
        "coverage_scope": context.get("coverage_scope") or "user_provided_text",
        "text_origin": context.get("text_origin") or "user_provided",
        "source_created_at": utc_iso(source_created_at),
        "source_updated_at": utc_iso(context.get("source_updated_at")),
        "source_captured_at": utc_iso(context.get("source_captured_at")),
        "retained_at": datetime.now(timezone.utc).isoformat(),
        "capture_method": context.get("capture_method") or "manual_browser",
        "capture_version": context.get("capture_version") or "feedback-api/v1",
        "raw_payload": deepcopy(context.get("raw_payload")),
        "author": _author_fields(author),
        "screenshot_path": context.get("screenshot_path"), "ocr_text": context.get("ocr_text"),
        "source_note": context.get("source_note"), "context_sha256": _context_digest(context),
        "quote_field": quote_field, "body_sha256": body_digest(text),
        "authenticity": "not_verified",
        "authenticity_note": "人工或程序提供的材料，未联网核验；哈希仅核对留存完整性，不认证平台真实性。",
    }
    package["snapshot_sha256"] = digest(_snapshot_material(package, content))
    return package


def source_dedupe_key(*, pipeline_profile: str, package: dict, content: dict) -> str:
    """Stable object+body identity, excluding capture/request/payload churn."""
    identity = {
        "profile": pipeline_profile,
        "platform": package.get("platform"), "source_type": package.get("source_type"),
        "entity_type": package.get("entity_type"),
        "source_url": _stable_source_url(package.get("original_url") or ""),
        "identity": {"id": package["external_id"]} if package.get("external_id")
        else {"url": package.get("original_url")},
        "parent_identity": package.get("parent_id") or package.get("parent_url"),
        "parent_comment_identity": package.get("parent_comment_id") or package.get("parent_comment_url"),
        "body": body_text(content)[0],
        "content_nature": package.get("content_nature"), "text_origin": package.get("text_origin"),
    }
    return f"source_v1_{digest(identity)}"


def _stable_source_url(url: str) -> str:
    """Keep identity queries; omit XHS item access signatures only from identity."""
    parsed = urlsplit(url)
    xhs_item = (parsed.hostname or "").lower() in {"xiaohongshu.com", "www.xiaohongshu.com"} and re.fullmatch(
        r"/(?:explore|discovery/item)/[a-fA-F0-9]{24}/?", parsed.path,
    )
    query = urlencode([
        (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_")
        and not (xhs_item and key.lower() in {"xsec_token", "xsec_source"})
    ])
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, query, parsed.fragment))


def verify_source_snapshot(row: RawFeedbackRow) -> dict:
    context = row.context if isinstance(row.context, dict) else {}
    package = context.get("source_evidence")
    if "source_evidence" not in context:
        if (row.dedupe_key or "").startswith("source_v1_"):
            return {"status": "mismatch", "message": "本记录应有来源快照，但快照已缺失。"}
        return {"status": "not_recorded", "message": "历史文本，未记录来源快照；没有自动补造。"}
    if not isinstance(package, dict):
        return {"status": "mismatch", "message": "来源快照结构损坏。"}
    if package.get("version") != VERSION:
        return {"status": "mismatch", "message": "来源快照版本缺失或不受支持。"}
    current = deepcopy(package)
    content = row.content if isinstance(row.content, dict) else {}
    try:
        current.update({
            "source_type": row.source_type, "external_id": row.external_id,
            "original_url": row.external_url,
            "source_created_at": utc_iso(row.source_created_at, persisted=True),
            "raw_payload": context.get("raw_payload"),
            "capture_method": context.get("capture_method") or "manual_browser",
            "source_captured_at": utc_iso(context.get("source_captured_at")),
            "author": _author_fields(row.author),
            "screenshot_path": context.get("screenshot_path"), "ocr_text": context.get("ocr_text"),
            "source_note": context.get("source_note"), "context_sha256": _context_digest(context),
        })
        for key in _SOURCE_FIELDS:
            if key in context:
                current[key] = utc_iso(context[key]) if key == "source_updated_at" else context[key]
        text, quote_field = body_text(content)
        body_matches = package.get("body_sha256") == body_digest(text) and package.get("quote_field") == quote_field
        hash_matches = current == package and package.get("snapshot_sha256") == digest(_snapshot_material(current, content))
    except (TypeError, ValueError, OverflowError):
        body_matches = hash_matches = False
    return {
        "status": "verified" if body_matches and hash_matches else "mismatch",
        "body_sha256_matches": body_matches, "snapshot_sha256_matches": hash_matches,
        "message": "留存完整性一致，不代表平台真实性或人工审核已通过。" if body_matches and hash_matches
        else "当前正文或来源元数据与留存快照不一致，不可作为候选依据。",
    }


def export_source_snapshot(row: RawFeedbackRow) -> dict:
    context = row.context if isinstance(row.context, dict) else {}
    return redact_credentials({
        "feedback_id": row.id, "pipeline_profile": row.pipeline_profile,
        "source_type": row.source_type, "external_id": row.external_id,
        "external_url": row.external_url, "content": row.content,
        "author": row.author, "screenshot_path": context.get("screenshot_path"),
        "ocr_text": context.get("ocr_text"), "source_note": context.get("source_note"),
        "source_created_at": utc_iso(row.source_created_at, persisted=True),
        "source_captured_at": context.get("source_captured_at"),
        "source_updated_at": context.get("source_updated_at"),
        "raw_payload": context.get("raw_payload"),
        "source_evidence": context.get("source_evidence"),
        "snapshot_verification": verify_source_snapshot(row),
    })
