"""Batch receipt counts from real temporary transactions; no platform or live DB."""
from __future__ import annotations

import asyncio
from copy import deepcopy

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from signal_miner.db.models import Base, RawFeedbackRow
from signal_miner.models import feedback as feedback_models
from signal_miner.pipeline import runner
from signal_miner.routes import feedback

POST_ID = "64abcdef0123456789abcdef"
POST_URL = f"https://www.xiaohongshu.com/explore/{POST_ID}"


def material(index):
    return {
        "source_type": "xiaohongshu", "platform": "xiaohongshu",
        "pipeline_profile": "product_feedback", "capture_method": "manual_browser",
        "external_url": POST_URL, "external_id": POST_ID if index == 0 else f"comment-{index}",
        "entity_type": "post" if index == 0 else "comment",
        "parent_id": None if index == 0 else POST_ID,
        "parent_url": None if index == 0 else POST_URL,
        "locator_level": "item" if index == 0 else "parent_page",
        "text": "OFFLINE正文材料" if index == 0 else "OFFLINE不同评论的相同正文",
        "subject": "OFFLINE测试标题", "author_name": None,
        "content_nature": "manual_text", "text_origin": "user_provided",
        "source_captured_at": "2026-11-10T08:00:00Z",
        "raw_payload": {"kind": "OFFLINE-fixture", "index": index},
    }


@pytest.fixture
async def isolated_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'counts.sqlite'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(runner, "get_session_factory", lambda: factory)
    monkeypatch.setattr(feedback, "get_session_factory", lambda: factory)
    app = FastAPI()
    app.include_router(feedback.router, prefix="/api/v1")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, factory, engine
    finally:
        await engine.dispose()


async def batch(client, items):
    response = await client.post("/api/v1/feedback/batch", json=items)
    assert response.status_code == 201, response.text
    return response.json()


async def rows(factory):
    async with factory() as session:
        records = (await session.execute(select(RawFeedbackRow))).scalars().all()
        return {row.id: deepcopy({
            "content": row.content, "context": row.context, "author": row.author,
            "url": row.external_url, "external_id": row.external_id,
            "source_id": row.source_id, "dedupe_key": row.dedupe_key,
            "created_at": row.created_at, "updated_at": row.updated_at,
        }) for row in records}


async def snapshot(client, row_id):
    response = await client.get(f"/api/v1/feedback/{row_id}/source-snapshot")
    assert response.status_code == 200, response.text
    return response.json()


async def test_new_four_then_repeat_four_counts_ids_rows_and_snapshots(isolated_db):
    client, factory, _ = isolated_db
    items = [material(index) for index in range(4)]
    first = await batch(client, items)
    assert (first["total"], first["ingested"], first["duplicates"]) == (4, 4, 0)
    assert len(set(first["feedback_ids"])) == 4
    before = await rows(factory)
    snapshots = {row_id: await snapshot(client, row_id) for row_id in first["feedback_ids"]}
    assert len(before) == 4 and all(saved["snapshot_verification"]["status"] == "verified" for saved in snapshots.values())
    repeated = await batch(client, items)
    assert (repeated["total"], repeated["ingested"], repeated["duplicates"]) == (4, 0, 4)
    assert repeated["feedback_ids"] == first["feedback_ids"]
    assert await rows(factory) == before
    for row_id in first["feedback_ids"]:
        assert await snapshot(client, row_id) == snapshots[row_id]
    changed_capture = deepcopy(items)
    for item in changed_capture:
        item["source_captured_at"] = "2026-11-10T09:00:00Z"
        item["raw_payload"]["new_capture"] = True
    third = await batch(client, changed_capture)
    assert (third["ingested"], third["duplicates"]) == (0, 4)
    assert third["feedback_ids"] == first["feedback_ids"] and await rows(factory) == before


async def test_mixed_existing_new_and_repeated_inputs_count_in_order(isolated_db):
    client, factory, _ = isolated_db
    old = await batch(client, [material(0), material(1)])
    mixed = await batch(client, [material(index) for index in (1, 4, 4, 0, 5, 1)])
    assert (mixed["total"], mixed["ingested"], mixed["duplicates"]) == (6, 2, 4)
    ids = mixed["feedback_ids"]
    assert ids[0] == ids[5] == old["feedback_ids"][1]
    assert ids[3] == old["feedback_ids"][0] and ids[1] == ids[2]
    assert len(set(ids)) == 4 and len(await rows(factory)) == 4
    for row_id, index in zip(ids, (1, 4, 4, 0, 5, 1), strict=True):
        saved = await snapshot(client, row_id)
        assert saved["raw_payload"]["index"] == index
        assert saved["snapshot_verification"]["status"] == "verified"


async def test_same_request_duplicates_and_empty_batch(isolated_db):
    client, factory, _ = isolated_db
    receipt = await batch(client, [material(2)] * 4)
    assert (receipt["total"], receipt["ingested"], receipt["duplicates"]) == (4, 1, 3)
    assert len(set(receipt["feedback_ids"])) == 1 and len(await rows(factory)) == 1
    assert await batch(client, []) == {"total": 0, "ingested": 0, "duplicates": 0, "feedback_ids": []}


async def test_legacy_reuse_counts_duplicate_without_fabricating_snapshot(isolated_db):
    client, factory, _ = isolated_db
    text = "OFFLINE legacy正文"
    url = "https://www.v2ex.com/t/123"
    async with factory() as session:
        session.add(RawFeedbackRow(id="legacy-counts", source_type="manual", source_id="manual_api",
            dedupe_key=runner._stable_dedupe_key("manual_api", text), external_url=url,
            content={"text": text}, author={}, context={}, pipeline_profile="product_feedback"))
        await session.commit()
    before = await rows(factory)
    receipt = await batch(client, [{"source_type": "manual", "external_url": url, "text": text}] * 2)
    assert receipt == {"total": 2, "ingested": 0, "duplicates": 2, "feedback_ids": ["legacy-counts", "legacy-counts"]}
    assert await rows(factory) == before
    saved = await snapshot(client, "legacy-counts")
    assert saved["source_evidence"] is None and saved["snapshot_verification"]["status"] == "not_recorded"


async def test_actual_unique_index_race_reports_only_the_transaction_winner_new(isolated_db, monkeypatch):
    client, factory, engine = isolated_db
    both_selected = asyncio.Event()
    counters = {"selects": 0, "rollbacks": 0}

    class RaceSession(AsyncSession):
        async def execute(self, statement, *args, **kwargs):
            result = await super().execute(statement, *args, **kwargs)
            if not self.info.get("first_select_done"):
                self.info["first_select_done"] = True
                counters["selects"] += 1
                if counters["selects"] == 2:
                    both_selected.set()
                await asyncio.wait_for(both_selected.wait(), 3)
            return result

        async def rollback(self):
            counters["rollbacks"] += 1
            await super().rollback()

    racing_factory = async_sessionmaker(engine, class_=RaceSession, expire_on_commit=False)
    monkeypatch.setattr(runner, "get_session_factory", lambda: racing_factory)
    first, second = await asyncio.gather(batch(client, [material(1)]), batch(client, [material(1)]))
    assert counters == {"selects": 2, "rollbacks": 1}  # both SELECTs missed; real loser rolled back
    assert first["feedback_ids"] == second["feedback_ids"]
    assert first["ingested"] + second["ingested"] == 1
    assert first["duplicates"] + second["duplicates"] == 1
    assert len(await rows(factory)) == 1
    assert (await snapshot(client, first["feedback_ids"][0]))["snapshot_verification"]["status"] == "verified"


async def test_database_integrity_error_without_same_key_winner_is_not_counted_or_swallowed(isolated_db, monkeypatch):
    client, factory, _ = isolated_db
    existing = await batch(client, [material(0)])
    existing_id = existing["feedback_ids"][0]
    # Real primary-key collision on a different source key; the unique-index
    # recovery must not mistake that unrelated record for a duplicate winner.
    monkeypatch.setattr(feedback_models, "new_id", lambda _prefix: existing_id)
    before = await rows(factory)
    with pytest.raises(IntegrityError):
        await client.post("/api/v1/feedback/batch", json=[material(99)])
    assert await rows(factory) == before


async def test_batch_validates_all_sources_before_any_transaction(isolated_db):
    client, factory, _ = isolated_db
    invalid = dict(material(1), external_url="https://evil.invalid/not-xhs")
    response = await client.post("/api/v1/feedback/batch", json=[material(0), invalid])
    assert response.status_code == 422 and "第 2 条" in response.text
    async with factory() as session:
        assert await session.scalar(select(func.count()).select_from(RawFeedbackRow)) == 0


async def test_legacy_string_call_and_single_api_stay_compatible(isolated_db):
    client, factory, _ = isolated_db
    data = feedback._prepare_ingest_data(feedback.IngestRequest(**material(1)))
    row_id = await runner.ingest_feedback(data)
    assert type(row_id) is str
    result = await runner.ingest_feedback_with_result(data)
    assert result.feedback_id == row_id and result.inserted is False
    response = await client.post("/api/v1/feedback/ingest", json=material(1))
    assert response.status_code == 201 and response.json()["feedback_id"] == row_id
    assert response.json()["pipeline_profile"] == "product_feedback"
    assert len(await rows(factory)) == 1
