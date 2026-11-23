"""D1 provenance semantics with real temporary SQLite; all external data OFFLINE."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
import httpx
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from signal_miner.connectors.community_samples import collect_v2ex_samples, normalize_hit
from signal_miner.connectors.source_acquisition import AcquisitionEvidence
from signal_miner.db.models import Base, RawFeedbackRow
from signal_miner.pipeline import runner
from signal_miner.routes import assets, feedback
from signal_miner.routes.feedback import IngestRequest, _prepare_ingest_data

TEXT = "每周手动导出报表耗时两小时。"
CAPTURED = "2026-11-05T08:30:00+00:00"


def payload(**overrides):
    result = {
        "source_type": "custom", "platform": "v2ex", "external_id": "123",
        "entity_type": "post", "external_url": "https://www.v2ex.com/t/123",
        "capture_method": "crawler", "content_nature": "original_text", "text_origin": "body",
        "locator_level": "item", "text": TEXT, "subject": "父标题不是正文",
        "source_created_at": "2026-11-01T16:00:00+08:00",
        "source_captured_at": CAPTURED, "source_updated_at": "2026-11-02T08:00:00Z",
        "source_note": "OFFLINE fixture", "capture_version": "fixture/v1",
        "raw_payload": {"platform": "v2ex", "original": {"id": "123", "body": TEXT}},
    }
    result.update(overrides)
    return result


def model(quote=TEXT, row_id="f1"):
    return SimpleNamespace(supports_embedding=False, call_structured=AsyncMock(return_value=json.dumps({
        "candidates": [{"title": "导出辅助", "user_segment": "报表用户", "scenario": "每周导出", "pain_point": "手工耗时",
                        "minimum_idea": "定时导出（推断）", "reasoning": "可能节约时间（推断）",
                        "validation_questions": ["现有替代方案？", "是否愿意付费？"],
                        "evidence": [{"feedback_id": row_id, "quote": quote}]}], "insufficiency_reason": "",
    })))


@pytest.fixture
async def app_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'source.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    for module in (feedback, assets, runner):
        monkeypatch.setattr(module, "get_session_factory", lambda: factory)
    app = FastAPI()
    app.state.runtime = SimpleNamespace(llm=model())
    app.include_router(feedback.router, prefix="/api/v1")
    app.include_router(assets.router, prefix="/api/v1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, app, factory
    await engine.dispose()


async def ingest(client, item):
    response = await client.post("/api/v1/feedback/ingest", json=item)
    assert response.status_code == 201, response.text
    return response.json()["feedback_id"]


async def read_snapshot(client, row_id):
    response = await client.get(f"/api/v1/feedback/{row_id}/source-snapshot")
    assert response.status_code == 200
    return response.json()


async def test_preview_ingest_detail_snapshot_keeps_source_fields_and_utc(app_db):
    client, _, _ = app_db
    original = payload(author_name=None, screenshot_path="/tmp/source.png", ocr_text="OCR片段")
    row_id = await ingest(client, original)
    detail = (await client.get(f"/api/v1/feedback/{row_id}")).json()
    snapshot = await read_snapshot(client, row_id)
    assert detail["external_id"] == "123"
    assert detail["source_created_at"] == "2026-11-01T08:00:00+00:00"
    assert detail["snapshot_verification"]["status"] == "verified"  # SQLite has dropped tzinfo
    assert snapshot["raw_payload"] == original["raw_payload"]
    assert snapshot["source_captured_at"] == CAPTURED
    assert snapshot["author"]["name"] is None
    assert snapshot["screenshot_path"] == "/tmp/source.png" and snapshot["ocr_text"] == "OCR片段"
    assert snapshot["source_note"] == "OFFLINE fixture"
    package = snapshot["source_evidence"]
    assert package["body_sha256"] and package["snapshot_sha256"]
    assert package["quote_field"] == "content.text"
    assert package["authenticity"] == "not_verified"
    assert package["source_created_at"] != package["source_captured_at"]
    assert package["author"]["name"] is None
    assert "不代表" in snapshot["snapshot_verification"]["message"]


async def test_same_text_different_platforms_and_comments_keep_distinct_records(app_db):
    client, _, factory = app_db
    first = await ingest(client, payload())
    second = await ingest(client, payload(platform="hacker_news", external_url="https://news.ycombinator.com/item?id=123"))
    common = payload(source_type="bilibili", platform="bilibili", entity_type="comment", external_url="https://www.bilibili.com/video/BV1xx411c7mD", parent_url="https://www.bilibili.com/video/BV1xx411c7mD", locator_level="item", capture_method="manual_browser", source_created_at=None)
    third = await ingest(client, dict(common, external_id="comment1"))
    fourth = await ingest(client, dict(common, external_id="comment2"))
    assert len({first, second, third, fourth}) == 4
    for row_id, expected in ((first, "v2ex.com"), (second, "ycombinator.com"), (third, "bilibili.com")):
        saved = await read_snapshot(client, row_id)
        assert expected in saved["external_url"]
        assert saved["snapshot_verification"]["status"] == "verified"
    saved = await read_snapshot(client, third)
    assert saved["source_evidence"]["locator_level"] == "parent_page"
    assert saved["source_created_at"] is None  # never borrow a parent's time
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(RawFeedbackRow)) == 4


async def test_same_object_capture_or_request_churn_reuses_first_snapshot(app_db):
    client, _, _ = app_db
    first = await ingest(client, payload())
    initial = await read_snapshot(client, first)
    repeated = payload(source_captured_at="2026-11-05T09:30:00+00:00", raw_payload={"platform": "v2ex", "request_id": "new-request-each-capture"})
    assert await ingest(client, repeated) == first
    assert await read_snapshot(client, first) == initial
    changed = await ingest(client, payload(text=TEXT + "我想简化它。"))
    assert changed != first
    assert await read_snapshot(client, first) == initial
    assert (await read_snapshot(client, changed))["content"]["text"].endswith("简化它。")


async def test_different_urls_without_ids_and_profiles_cannot_merge(app_db):
    client, _, _ = app_db
    first = await ingest(client, payload(external_id=None))
    second = await ingest(client, payload(external_id=None, external_url="https://www.v2ex.com/t/456"))
    third = await ingest(client, payload(external_id=None, pipeline_profile="aigc_video"))
    assert len({first, second, third}) == 3


@pytest.mark.parametrize("source_type", ["manual", "custom"])
async def test_same_claimed_comment_id_without_platform_never_merges_other_pages_or_hosts(app_db, source_type):
    client, _, _ = app_db
    urls = ["https://www.v2ex.com/t/123", "https://www.v2ex.com/t/456", "https://www.zhihu.com/question/123/answer/456"]
    ids = [await ingest(client, payload(
        source_type=source_type, platform=None, entity_type="comment", external_id="comment-1",
        capture_method="manual_browser", external_url=url,
    )) for url in urls]
    assert len(set(ids)) == 3
    for row_id, url in zip(ids, urls, strict=True):
        assert (await read_snapshot(client, row_id))["external_url"] == url


async def test_tracking_churn_is_idempotent_but_hn_identity_query_is_not_removed(app_db):
    client, _, _ = app_db
    first_url = "https://news.ycombinator.com/item?id=100&utm_source=first"
    first = await ingest(client, payload(external_url=first_url))
    repeated = await ingest(client, payload(external_url="https://news.ycombinator.com/item?id=100&utm_source=second&utm_campaign=third"))
    another_object = await ingest(client, payload(external_url="https://news.ycombinator.com/item?id=200&utm_source=first"))
    assert repeated == first and another_object != first
    assert (await read_snapshot(client, first))["external_url"] == first_url


async def test_concurrent_same_object_import_handles_unique_index_race(app_db):
    client, _, factory = app_db
    ids = await asyncio.gather(*(ingest(client, payload()) for _ in range(4)))
    assert len(set(ids)) == 1
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(RawFeedbackRow)) == 1


@pytest.mark.parametrize("tamper", ["body", "url", "raw_payload", "author", "delete_metadata", "delete_package", "package_metadata"])
async def test_tampered_sources_fail_snapshot_and_never_reach_model(app_db, tamper):
    client, app, factory = app_db
    row_id = await ingest(client, payload())
    async with factory() as session:
        row = await session.get(RawFeedbackRow, row_id)
        if tamper == "body":
            row.content = dict(row.content, text="changed body")
        elif tamper == "url":
            row.external_url = "https://www.v2ex.com/t/999"
        elif tamper == "author":
            row.author = dict(row.author, name="Changed author")
        else:
            context = deepcopy(row.context)
            if tamper == "raw_payload":
                context["raw_payload"]["original"]["body"] = "changed original"
            elif tamper == "delete_metadata":
                del context["source_note"]
            elif tamper == "delete_package":
                del context["source_evidence"]
            else:
                context["source_evidence"]["locator_level"] = "parent_page"
            row.context = context
        await session.commit()
    assert (await read_snapshot(client, row_id))["snapshot_verification"]["status"] == "mismatch"
    app.state.runtime.llm = model(row_id=row_id)
    response = await client.post("/api/v1/opportunities/discover", json={"feedback_ids": [row_id]})
    assert response.status_code == 200
    assert response.json()["candidates"] == []
    assert "完整性" in response.json()["excluded"][0]["reason"]
    app.state.runtime.llm.call_structured.assert_not_called()


@pytest.mark.parametrize("quote", ["父标题不是正文", "不是正文每周手动", "父标题不是正文\n\n每周手动"])
async def test_title_or_cross_field_quotes_are_rejected(app_db, quote):
    client, app, _ = app_db
    row_id = await ingest(client, payload())
    app.state.runtime.llm = model(quote=quote, row_id=row_id)
    result = (await client.post("/api/v1/opportunities/discover", json={"feedback_ids": [row_id]})).json()
    assert result["candidates"] == []
    assert "父标题不是正文" not in app.state.runtime.llm.call_structured.call_args.args[0]


async def test_valid_candidate_contains_body_field_and_source_snapshot_metadata(app_db):
    client, app, _ = app_db
    row_id = await ingest(client, payload())
    app.state.runtime.llm = model(row_id=row_id)
    result = (await client.post("/api/v1/opportunities/discover", json={"feedback_ids": [row_id]})).json()
    evidence = result["candidates"][0]["evidence"][0]
    assert evidence["feedback_id"] == row_id and evidence["quote_field"] == "content.text"
    assert evidence["snapshot_status"] == "verified" and len(evidence["snapshot_hash"]) == 64
    assert evidence["platform"] == "v2ex" and evidence["external_id"] == "123"
    assert evidence["source_captured_at"] == CAPTURED


@pytest.mark.parametrize("nature", ["api_excerpt", "curated_comment"])
async def test_excerpt_import_rejected_and_persisted_defensive_gate_stops_model(app_db, nature):
    client, app, factory = app_db
    response = await client.post("/api/v1/feedback/ingest", json=payload(content_nature=nature))
    assert response.status_code == 422 and "补充原文" in response.text
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(RawFeedbackRow)) == 0
        session.add(RawFeedbackRow(id="legacy-excerpt", source_type="custom", source_id="old", dedupe_key="old", external_url="https://www.v2ex.com/t/123", content={"text": TEXT}, context={"content_nature": nature}, author={}, pipeline_profile="product_feedback"))
        await session.commit()
    result = (await client.post("/api/v1/opportunities/discover", json={"feedback_ids": ["legacy-excerpt"]})).json()
    assert not result["candidates"] and "检索线索" in result["excluded"][0]["reason"]
    app.state.runtime.llm.call_structured.assert_not_called()


async def test_missing_body_never_uses_title_and_legacy_snapshot_is_not_fabricated(app_db):
    client, app, factory = app_db
    async with factory() as session:
        session.add(RawFeedbackRow(id="old-title", source_type="custom", source_id="old", dedupe_key="old", external_url="https://www.v2ex.com/t/123", content={"subject": TEXT, "text": ""}, context={}, author={}, pipeline_profile="product_feedback"))
        await session.commit()
    saved = await read_snapshot(client, "old-title")
    assert saved["source_evidence"] is None and saved["snapshot_verification"]["status"] == "not_recorded"
    result = (await client.post("/api/v1/opportunities/discover", json={"feedback_ids": ["old-title"]})).json()
    assert not result["candidates"]
    app.state.runtime.llm.call_structured.assert_not_called()


@pytest.mark.parametrize("field", ["source_created_at", "source_updated_at", "source_captured_at"])
def test_input_source_times_require_timezone(field):
    with pytest.raises(ValidationError, match="时区"):
        IngestRequest.model_validate(payload(**{field: "2026-11-05T08:30:00"}))


async def test_request_cannot_claim_verification_or_export_credentials(app_db):
    client, _, _ = app_db
    rejected = await client.post("/api/v1/feedback/ingest", json=payload(verified=True))
    assert rejected.status_code == 422
    row_id = await ingest(client, payload(raw_payload={"Authorization": "Bearer NEVER-EXPORT", "nested": {"ZHIHU_ACCESS_SECRET": "NEVER-EXPORT"}, "original": {"id": "123"}}))
    for path in (f"/api/v1/feedback/{row_id}", f"/api/v1/feedback/{row_id}/source-snapshot"):
        response = await client.get(path)
        assert "NEVER-EXPORT" not in response.text
    saved = await read_snapshot(client, row_id)
    assert saved["snapshot_verification"]["status"] == "verified"
    assert saved["source_evidence"]["authenticity"] == "not_verified"


def test_acquisition_conversion_preserves_structured_source_values():
    captured = datetime(2026, 11, 5, 8, tzinfo=timezone.utc)
    evidence = AcquisitionEvidence(source_type="bilibili", external_url="https://www.bilibili.com/video/BV1xx411c7mD", capture_method="browser_screenshot", text=TEXT, source_captured_at=captured, raw_payload={"original": "visible text"}, screenshot_path="/tmp/source.png", ocr_text=TEXT, external_id="comment7", entity_type="comment", parent_url="https://www.bilibili.com/video/BV1xx411c7mD", locator_level="parent_page", content_nature="ocr_text", text_origin="ocr")
    result = evidence.to_ingest_payload()
    request = IngestRequest.model_validate(result)
    assert request.external_id == "comment7" and request.source_captured_at == captured
    assert request.raw_payload == {"original": "visible text"}
    assert request.ocr_text == TEXT and request.screenshot_path == "/tmp/source.png"
    assert request.locator_level == "parent_page"


def test_hn_preview_has_own_comment_id_time_and_title_origin():
    now = datetime.now(timezone.utc)
    original = {"objectID": "123", "created_at": (now - timedelta(hours=1)).isoformat(), "comment_text": "my comment", "story_id": 100, "parent_id": 110, "story_title": "parent title"}
    item, reason = normalize_hit(original, kind="comment", api_request_url="https://hn.algolia.com/api/v1/search_by_date", collected_at=now, cutoff=now-timedelta(days=30))
    assert reason is None
    request = IngestRequest.model_validate(item)
    assert request.external_id == "123" and request.parent_id == "100" and request.parent_comment_id == "110"
    assert request.entity_type == "comment" and request.author_name is None
    assert request.source_created_at != request.source_captured_at
    assert request.text_origin == "body" and request.content_nature == "original_text"


def test_capture_churn_changes_integrity_hash_but_not_source_identity():
    first = _prepare_ingest_data(IngestRequest.model_validate(payload()))
    second = _prepare_ingest_data(IngestRequest.model_validate(payload(
        source_captured_at="2026-11-05T09:00:00Z", raw_payload={"request_id": "different"},
    )))
    assert first["dedupe_key"] == second["dedupe_key"]
    assert first["context"]["source_evidence"]["snapshot_sha256"] != second["context"]["source_evidence"]["snapshot_sha256"]


def test_v2ex_atom_summary_is_not_silently_imported_as_original_content():
    now = datetime.now(timezone.utc)
    feed = f'''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>topic/123</id>
      <title>真实标题</title><link href="https://www.v2ex.com/t/123"/>
      <published>{(now-timedelta(hours=1)).isoformat()}</published>
      <summary type="html">这只是摘要</summary></entry></feed>'''
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, text=feed))) as client:
        items, summary = collect_v2ex_samples(client, now=now)
    assert items == [] and summary.status == "empty"
    assert summary.skip_reasons == {"api_excerpt_not_original": 1}


async def test_hn_actual_title_only_text_is_explicit_and_can_be_quoted(app_db):
    client, app, _ = app_db
    now = datetime.now(timezone.utc)
    actual = "Ask HN: How can weekly report exports be automated?"
    item, reason = normalize_hit(
        {"objectID": "777", "title": actual, "created_at": (now-timedelta(hours=1)).isoformat()},
        kind="ask_hn", api_request_url="https://hn.algolia.com/api/v1/search_by_date",
        collected_at=now, cutoff=now-timedelta(days=30),
    )
    assert reason is None and item["text_origin"] == "title"
    row_id = await ingest(client, item)
    app.state.runtime.llm = model(quote=actual, row_id=row_id)
    result = (await client.post("/api/v1/opportunities/discover", json={"feedback_ids": [row_id]})).json()
    assert result["candidates"][0]["evidence"][0]["text_origin"] == "title"


async def test_legacy_exact_source_compatibility_never_merges_other_url(app_db):
    client, _, factory = app_db
    old = {"source_type": "manual", "external_url": "https://www.v2ex.com/t/123", "text": TEXT}
    async with factory() as session:
        session.add(RawFeedbackRow(id="legacy-exact", source_type="manual", source_id="manual_api", dedupe_key=runner._stable_dedupe_key("manual_api", TEXT), external_url=old["external_url"], content={"text": TEXT}, context={}, author={}, pipeline_profile="product_feedback"))
        await session.commit()
    assert await ingest(client, old) == "legacy-exact"
    assert (await read_snapshot(client, "legacy-exact"))["snapshot_verification"]["status"] == "not_recorded"
    other = await ingest(client, dict(old, external_url="https://www.v2ex.com/t/456"))
    assert other != "legacy-exact"


@pytest.mark.parametrize("own_id,parent_comment", [(None, "102"), (None, "101"), ("comment-7", "102")])
async def test_legacy_comment_requires_own_identity_and_matching_parents(app_db, own_id, parent_comment):
    client, _, factory = app_db
    url = "https://www.bilibili.com/video/BV1xx411c7mD"
    context = {"entity_type": "comment", "locator_level": "parent_page", "parent_url": url, "parent_comment_id": "101"}
    async with factory() as session:
        session.add(RawFeedbackRow(
            id="legacy-comment", source_type="bilibili", source_id="bilibili_api",
            dedupe_key=runner._stable_dedupe_key("bilibili_api", TEXT),
            external_id=own_id, external_url=url, content={"text": TEXT}, context=context,
            author={}, pipeline_profile="product_feedback",
        ))
        await session.commit()
    new_id = await ingest(client, {
        "source_type": "bilibili", "external_id": own_id, "external_url": url, "text": TEXT,
        "entity_type": "comment", "locator_level": "parent_page", "parent_url": url,
        "parent_comment_id": parent_comment,
    })
    assert new_id != "legacy-comment"
    assert (await read_snapshot(client, new_id))["source_evidence"]["parent_comment_id"] == parent_comment
    async with factory() as session:
        assert (await session.get(RawFeedbackRow, "legacy-comment")).context["parent_comment_id"] == "101"
