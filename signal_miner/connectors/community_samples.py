"""Export a bounded community sample without importing it or calling an LLM.

Example (the output file must not already exist)::

    python scripts/collect_community_opportunity_samples.py --source hn \
        --query "workflow" --days 30 --limit 20 --output /tmp/hn-workflow.json

    python scripts/collect_community_opportunity_samples.py --source v2ex \
        --v2ex-node qna --days 30 --limit 20 --output /tmp/v2ex-qna.json

The JSON array is accepted by POST /api/v1/feedback/batch. Sources use
``custom`` because there is no dedicated platform ingestion policy; the actual
platform and API provenance remain explicit. Public accessibility is not a
goldset authorization. HN has an English-speaking technical bias. V2EX reads
one public Atom feed with only its latest posts, not historical coverage or
comments. V2EX query filtering is local; HN uses server-side search.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode, urlparse
import xml.etree.ElementTree as ET

import httpx

API_URL = "https://hn.algolia.com/api/v1/search_by_date"
MAX_LIMIT = 100
MAX_REQUESTS = 20
PAGE_SIZE = 25
V2EX_FEEDS = {node: f"https://www.v2ex.com/feed/{node}.xml" for node in ("qna", "ideas")}
ATOM = "{http://www.w3.org/2005/Atom}"


class _TextParser(HTMLParser):
    """Keep literal text and paragraph boundaries, discarding HTML markup."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style"}:
            self.hidden_depth += 1
        if tag in {"p", "br", "div", "li", "pre", "blockquote", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self.hidden_depth:
            self.hidden_depth -= 1
        if tag in {"p", "div", "li", "pre", "blockquote", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden_depth:
            self.parts.append(data)


def clean_html(value: object) -> str:
    """Decode entities once, retaining escaped angle brackets as literal text."""
    if not isinstance(value, str):
        return ""
    parser = _TextParser()
    parser.feed(value)
    parser.close()
    lines = [re.sub(r"[\t\r\f\v \xa0]+", " ", line).strip()
             for line in "".join(parser.parts).split("\n")]
    return "\n".join(line for line in lines if line)


def _item_id(value: object) -> str | None:
    candidate = str(value) if isinstance(value, (str, int)) else ""
    return candidate if candidate.isascii() and candidate.isdigit() and int(candidate) > 0 else None


def _item_url(item_id: str | None) -> str | None:
    return f"https://news.ycombinator.com/item?id={item_id}" if item_id else None


def _published_at(hit: dict) -> datetime | None:
    try:
        if isinstance(hit.get("created_at_i"), (float, int)) and not isinstance(hit["created_at_i"], bool):
            return datetime.fromtimestamp(hit["created_at_i"], tz=timezone.utc)
        raw = hit.get("created_at")
        if isinstance(raw, str):
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
    return None


def normalize_hit(
    hit: object,
    *,
    kind: str,
    api_request_url: str,
    collected_at: datetime,
    cutoff: datetime,
) -> tuple[dict | None, str | None]:
    """Return an ingest payload or an explicit reason that this hit was skipped."""
    if not isinstance(hit, dict):
        return None, "invalid_hit"
    item_id = _item_id(hit.get("objectID"))
    if not item_id:
        return None, "invalid_id"
    if hit.get("deleted") or hit.get("dead"):
        return None, "deleted_or_dead"
    published = _published_at(hit)
    if published is None:
        return None, "invalid_timestamp"
    if published < cutoff or published > collected_at:
        return None, "outside_time_window"
    title = clean_html(hit.get("title") if kind == "ask_hn" else hit.get("story_title"))
    body = clean_html(hit.get("story_text") if kind == "ask_hn" else hit.get("comment_text"))
    # A title-only Ask HN is original source text, not an invented summary.
    text = body or (title if kind == "ask_hn" else "")
    if not text:
        return None, "empty_text"
    story_id = _item_id(hit.get("story_id"))
    parent_id = _item_id(hit.get("parent_id"))
    captured = collected_at.isoformat()
    return {
        "source_type": "custom",
        "capture_method": "official_api",
        "pipeline_profile": "product_feedback",
        "subject": title or f"HN comment {item_id}",
        "text": text,
        "author_name": hit.get("author") if isinstance(hit.get("author"), str) else None,
        "external_url": _item_url(item_id),
        "platform": "hacker_news", "external_id": item_id,
        "entity_type": "post" if kind == "ask_hn" else "comment",
        "parent_id": story_id if kind == "comment" else None,
        "parent_url": _item_url(story_id) if kind == "comment" else None,
        "parent_comment_id": parent_id if kind == "comment" and parent_id != story_id else None,
        "parent_comment_url": _item_url(parent_id) if kind == "comment" and parent_id != story_id else None,
        "locator_level": "item", "content_nature": "original_text",
        "text_origin": "body" if body else "title",
        "coverage_scope": "api_item_body" if body else "actual_title_only",
        "capture_version": "hn-algolia/v1", "source_created_at": published.isoformat(),
        "source_captured_at": captured,
        "source_note": (
            f"Hacker News {kind}; HN Algolia search API; public read, "
            "goldset authorization not assessed; technical/English-speaking sample bias."
        ),
        "raw_payload": {
            "platform": "hacker_news",
            "platform_id": item_id,
            "item_type": kind,
            "published_at": published.isoformat(),
            "collected_at": captured,
            "api_provider": "HN Search powered by Algolia",
            "api_request_url": api_request_url,
            "story": {
                "id": story_id,
                "title": title if kind == "comment" else clean_html(hit.get("title")),
                "url": _item_url(story_id),
                "external_url": hit.get("story_url") if kind == "comment" else hit.get("url"),
            },
            "parent": {"id": parent_id, "url": _item_url(parent_id)},
            "goldset_authorization": "not_assessed",
            "original": hit,
        },
    }, None


@dataclass
class CollectionSummary:
    query: str
    days: int
    limit: int
    kinds: list[str]
    source: str = "hn"
    coverage_note: str = "Bounded HN search; technical/English-speaking population bias."
    requests: int = 0
    fetched: int = 0
    collected: int = 0
    skipped: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    stop_reason: str = ""
    written: int = 0
    output: str | None = None
    status: str = "pending"


class CollectionError(RuntimeError):
    """A failed collection, including accurate counters for partial reads."""

    def __init__(self, message: str, summary: CollectionSummary) -> None:
        super().__init__(message)
        self.summary = summary


def collect_samples(
    client: httpx.Client,
    *,
    query: str = "",
    days: int = 30,
    limit: int = 20,
    max_requests: int = 12,
    kind: str = "both",
    now: datetime | None = None,
) -> tuple[list[dict], CollectionSummary]:
    """Read alternating, bounded pages of Ask HN posts and/or HN comments.

    Comments search all HN discussions, not only Ask HN threads. There is no
    follow-up parent fetching, retry loop, database access or implicit LLM call.
    Reaching the request bound is reported even if fewer samples were found.
    """
    if not 1 <= days <= 3650 or not 1 <= limit <= MAX_LIMIT or not 1 <= max_requests <= MAX_REQUESTS:
        raise ValueError("days must be 1..3650, limit 1..100 and max_requests 1..20")
    if kind not in {"both", "ask", "comments"}:
        raise ValueError("kind must be both, ask or comments")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include a timezone")
    current = current.astimezone(timezone.utc)
    cutoff = current - timedelta(days=days)
    kinds = ["ask_hn", "comment"] if kind == "both" else ["ask_hn" if kind == "ask" else "comment"]
    summary = CollectionSummary(query=query, days=days, limit=limit, kinds=kinds)
    pages = dict.fromkeys(kinds, 0)
    active = list(kinds)
    seen: set[str] = set()
    items: list[dict] = []
    reasons: Counter[str] = Counter()
    turn = 0
    try:
        while active and len(items) < limit and summary.requests < max_requests:
            stream = active[turn % len(active)]
            page_size = min(PAGE_SIZE, max(1, (limit + len(kinds) - 1) // len(kinds)), limit - len(items))
            params = {
                "query": query,
                "tags": stream,
                "numericFilters": f"created_at_i>={int(cutoff.timestamp())}",
                "hitsPerPage": page_size,
                "page": pages[stream],
            }
            api_request_url = f"{API_URL}?{urlencode(params)}"
            summary.requests += 1
            response = client.get(API_URL, params=params)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict) or not isinstance(payload.get("hits"), list):
                raise ValueError("HN API response has no hits array")
            hits = payload["hits"]
            summary.fetched += len(hits)
            page_count = payload.get("nbPages")
            if type(page_count) is not int or page_count < 0 or len(hits) > page_size:
                raise ValueError("HN API returned invalid pagination")
            for hit in hits:
                item, reason = normalize_hit(
                    hit, kind=stream, api_request_url=api_request_url,
                    collected_at=current, cutoff=cutoff,
                )
                if item is not None:
                    item_id = item["raw_payload"]["platform_id"]
                    if item_id in seen:
                        reason = "duplicate_id"
                    else:
                        seen.add(item_id)
                        items.append(item)
                        summary.collected += 1
                if reason:
                    summary.skipped += 1
                    reasons[reason] += 1
            summary.skip_reasons = dict(reasons)
            pages[stream] += 1
            if not hits or pages[stream] >= page_count:
                active.remove(stream)
                # The next stream has moved into the current position.
                if active:
                    turn %= len(active)
            else:
                turn += 1
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        message = f"{type(exc).__name__}: {exc}"
        summary.errors.append(message)
        summary.status = "error"
        summary.stop_reason = "request_or_response_error"
        raise CollectionError(message, summary) from exc
    if len(items) >= limit:
        summary.stop_reason = "sample_limit"
        summary.status = "collected"
    elif active:
        summary.stop_reason = "request_limit"
        summary.status = "bounded"
    else:
        summary.stop_reason = "sources_exhausted"
        summary.status = "collected" if items else "empty"
    return items, summary


def _bounded_integer(lower: int, upper: int):
    def parse(value: str) -> int:
        try:
            result = int(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be an integer") from exc
        if not lower <= result <= upper:
            raise argparse.ArgumentTypeError(f"must be between {lower} and {upper}")
        return result
    return parse


def collect_v2ex_samples(
    client: httpx.Client,
    *,
    query: str = "",
    days: int = 30,
    limit: int = 20,
    node: str = "qna",
    now: datetime | None = None,
) -> tuple[list[dict], CollectionSummary]:
    """Read one allowlisted public Atom feed, never fetch histories or replies."""
    if not 1 <= days <= 3650 or not 1 <= limit <= MAX_LIMIT or node not in V2EX_FEEDS:
        raise ValueError("days must be 1..3650, limit 1..100 and node qna or ideas")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now must include a timezone")
    current = current.astimezone(timezone.utc)
    cutoff = current - timedelta(days=days)
    feed_url = V2EX_FEEDS[node]
    summary = CollectionSummary(
        query=query, days=days, limit=limit, kinds=[node], source="v2ex",
        coverage_note=(
            "One public Atom feed, typically latest 50 posts; no complete days/history "
            "coverage or comments. Query is a local text filter. Technical community bias."
        ),
    )
    items = []
    reasons: Counter[str] = Counter()
    seen = set()
    try:
        summary.requests = 1
        response = client.get(feed_url)
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("Public feed exceeds the 2 MB response limit")
        root = ET.fromstring(response.content)
        if root.tag != f"{ATOM}feed":
            raise ValueError("V2EX response is not an Atom feed")
        entries = root.findall(f"{ATOM}entry")
        summary.fetched = len(entries)
        for entry in entries:
            if len(items) >= limit:
                reasons["beyond_sample_limit"] += 1
                continue
            url = next((link.get("href", "") for link in entry.findall(f"{ATOM}link")
                        if link.get("rel", "alternate") == "alternate"), "")
            parsed = urlparse(url)
            match = re.fullmatch(r"/t/(\d+)/?", parsed.path)
            if parsed.scheme != "https" or parsed.hostname not in {"www.v2ex.com", "v2ex.com"} or not match:
                reasons["invalid_source_url"] += 1
                continue
            platform_id = match.group(1)
            if platform_id in seen:
                reasons["duplicate_id"] += 1
                continue
            published_raw = entry.findtext(f"{ATOM}published")
            updated_raw = entry.findtext(f"{ATOM}updated")
            # Atom updated is a modification time, never a publication fallback.
            # Without published we cannot apply the requested publication window.
            if not published_raw or not published_raw.strip():
                reasons["missing_published_at"] += 1
                continue
            published = _published_at({"created_at": published_raw})
            if published is None:
                reasons["invalid_published_at"] += 1
                continue
            if published < cutoff or published > current:
                reasons["outside_time_window"] += 1
                continue
            title = clean_html(entry.findtext(f"{ATOM}title"))
            content_html = entry.findtext(f"{ATOM}content") or ""
            summary_html = entry.findtext(f"{ATOM}summary") or ""
            # Atom summary is an excerpt, not a full original body. Keep this
            # sampler's output importable; report the exclusion rather than
            # silently relabeling excerpts as source text.
            if not clean_html(content_html) and clean_html(summary_html):
                reasons["api_excerpt_not_original"] += 1
                continue
            text = clean_html(content_html) or title
            if not text:
                reasons["empty_text"] += 1
                continue
            if query and query.casefold() not in f"{title}\n{text}".casefold():
                reasons["query_mismatch"] += 1
                continue
            seen.add(platform_id)
            items.append({
                "source_type": "custom",
                "capture_method": "crawler",
                "pipeline_profile": "product_feedback",
                "subject": title or f"V2EX topic {platform_id}",
                "text": text,
                "author_name": entry.findtext(f"{ATOM}author/{ATOM}name"),
                "external_url": url,
                "platform": "v2ex", "external_id": platform_id, "entity_type": "post",
                "locator_level": "item", "content_nature": "original_text",
                "text_origin": "body" if clean_html(content_html) else "title",
                "coverage_scope": "atom_content" if clean_html(content_html) else "actual_title_only",
                "capture_version": "v2ex-atom/v1", "source_created_at": published.isoformat(),
                "source_updated_at": utc_updated.isoformat() if (utc_updated := _published_at({"created_at": updated_raw})) is not None else None,
                "source_captured_at": current.isoformat(),
                "source_note": (
                    f"V2EX {node} public Atom feed; latest posts only, no replies/history; "
                    "goldset authorization not assessed; technical community bias."
                ),
                "raw_payload": {
                    "platform": "v2ex", "platform_id": platform_id,
                    "acquisition_kind": "public_feed", "feed_url": feed_url,
                    "node": node, "published_at": published.isoformat(),
                    "updated_at": updated_raw, "collected_at": current.isoformat(),
                    "local_query": query, "goldset_authorization": "not_assessed",
                    "original": {
                        "id": entry.findtext(f"{ATOM}id"), "title": entry.findtext(f"{ATOM}title"),
                        "content_html": content_html, "summary_html": summary_html, "published": published_raw,
                        "updated": updated_raw, "entry_xml": ET.tostring(entry, encoding="unicode"),
                    },
                },
            })
        summary.collected = len(items)
        summary.skip_reasons = dict(reasons)
        summary.skipped = sum(reasons.values())
        summary.stop_reason = "sample_limit" if len(items) >= limit else "single_feed_exhausted"
        summary.status = "collected" if items else "empty"
    except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
        summary.errors.append(f"{type(exc).__name__}: {exc}")
        summary.status = "error"
        summary.stop_reason = "request_or_response_error"
        raise CollectionError(summary.errors[0], summary) from exc
    return items, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["hn", "v2ex"], default="hn")
    parser.add_argument("--v2ex-node", choices=list(V2EX_FEEDS), default="qna")
    parser.add_argument("--query", default="", help="Optional search terms; no industry is hard-coded")
    parser.add_argument("--days", type=_bounded_integer(1, 3650), default=30)
    parser.add_argument("--limit", type=_bounded_integer(1, MAX_LIMIT), default=20)
    parser.add_argument("--max-requests", type=_bounded_integer(1, MAX_REQUESTS), default=12)
    parser.add_argument("--timeout", type=_bounded_integer(1, 30), default=10, help="Per-request timeout in seconds")
    parser.add_argument("--kind", choices=["both", "ask", "comments"], default="both")
    parser.add_argument("--output", required=True, type=Path, help="Explicit new JSON file; parent directory must exist")
    args = parser.parse_args(argv)
    summary = CollectionSummary(query=args.query, days=args.days, limit=args.limit, kinds=[], source=args.source)
    try:
        if args.output.exists():
            raise FileExistsError("Output already exists; choose a new path")
        if not args.output.parent.is_dir():
            raise FileNotFoundError("Output parent directory does not exist")
        with httpx.Client(
            timeout=args.timeout,
            follow_redirects=False,
            headers={"User-Agent": "SignalMiner-HN-sample/1.0", "Accept": "application/json"},
        ) as client:
            if args.source == "v2ex":
                items, summary = collect_v2ex_samples(
                    client, query=args.query, days=args.days, limit=args.limit, node=args.v2ex_node,
                )
            else:
                items, summary = collect_samples(
                    client, query=args.query, days=args.days, limit=args.limit,
                    max_requests=args.max_requests, kind=args.kind,
                )
        encoded = json.dumps(items, ensure_ascii=False, indent=2) + "\n"
        with args.output.open("x", encoding="utf-8") as output:
            output.write(encoded)
        summary.written = len(items)
    except CollectionError as exc:
        summary = exc.summary
    except (OSError, ValueError) as exc:
        summary.status = "error"
        summary.stop_reason = "output_or_configuration_error"
        summary.errors.append(f"{type(exc).__name__}: {exc}")
    summary.output = str(args.output.absolute())
    print(json.dumps(asdict(summary), ensure_ascii=False))
    return 1 if summary.errors else 0


if __name__ == "__main__":
    sys.exit(main())
