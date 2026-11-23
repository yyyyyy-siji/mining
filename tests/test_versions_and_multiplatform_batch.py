"""Tests for dataset version management and multi-platform concurrent Chrome batch collection."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from signal_miner.connectors.existing_chrome import ExistingChromeCollector
from signal_miner.db import _ensure_version_schema
from signal_miner.db.models import (
    Base,
    OpportunityRow,
    PainPointRow,
    RequirementAssetRow,
    SignalRow,
    ThemeRow,
)
from signal_miner.pipeline import runner as runner_mod
from signal_miner.routes import assets as assets_routes
from signal_miner.routes import feedback as feedback_routes
from signal_miner.routes import signals as signals_routes
from signal_miner.routes import versions as versions_routes


@pytest.mark.asyncio
async def test_version_crud_isolation_dedupe_and_cascade_delete(tmp_path, monkeypatch):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'versions.sqlite'}"
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _ensure_version_schema(conn, db_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    for mod in (versions_routes, feedback_routes, signals_routes, assets_routes, runner_mod):
        monkeypatch.setattr(mod, "get_session_factory", lambda: factory)

    app = FastAPI()
    app.include_router(versions_routes.router, prefix="/api/v1")
    app.include_router(feedback_routes.router, prefix="/api/v1")
    app.include_router(signals_routes.router, prefix="/api/v1")
    app.include_router(assets_routes.router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Default version exists automatically
        res = await client.get("/api/v1/versions")
        assert res.status_code == 200
        versions = res.json()["versions"]
        assert any(v["id"] == "default" for v in versions)

        # 2. Create two custom versions
        v1 = (await client.post("/api/v1/versions", json={"name": "v1-调研", "description": "第一轮"})).json()
        v2 = (await client.post("/api/v1/versions", json={"name": "v2-复盘", "description": "第二轮"})).json()
        assert v1["id"].startswith("ver_")
        assert v2["id"].startswith("ver_")

        # 3. Same item imported into v1 and v2 should NOT collide (version-scoped dedupe)
        item = {
            "source_type": "zhihu",
            "text": "这个插件安装流程太复杂了",
            "external_url": "https://www.zhihu.com/question/123456/answer/987654",
            "external_id": "987654",
            "capture_method": "crawler",
            "pipeline_profile": "product_feedback",
        }
        r1 = await client.post(f"/api/v1/feedback/batch?version_id={v1['id']}", json=[item])
        assert r1.status_code == 201 and r1.json()["ingested"] == 1
        # Duplicate inside same version v1 is deduplicated
        r1_dup = await client.post(f"/api/v1/feedback/batch?version_id={v1['id']}", json=[item])
        assert r1_dup.status_code == 201 and r1_dup.json()["duplicates"] == 1
        # Same item into v2 inserts freshly!
        r2 = await client.post(f"/api/v1/feedback/batch?version_id={v2['id']}", json=[item])
        assert r2.status_code == 201 and r2.json()["ingested"] == 1
        assert r1.json()["feedback_ids"][0] != r2.json()["feedback_ids"][0]

        # 4. List endpoints strictly isolate by version_id, and 'all' returns both
        fb_v1 = (await client.get(f"/api/v1/feedback?version_id={v1['id']}")).json()
        fb_v2 = (await client.get(f"/api/v1/feedback?version_id={v2['id']}")).json()
        fb_all = (await client.get("/api/v1/feedback?version_id=all")).json()
        assert len(fb_v1) == 1 and fb_v1[0]["version_id"] == v1["id"]
        assert len(fb_v2) == 1 and fb_v2[0]["version_id"] == v2["id"]
        assert len(fb_all) == 2

        # 5. Seed downstream signal/theme/pain_point/opportunity/requirement in v1 & v2
        now = datetime.now(timezone.utc)
        async with factory() as session:
            for idx, (ver_id, fb_id) in enumerate(((v1["id"], fb_v1[0]["id"]), (v2["id"], fb_v2[0]["id"])), 1):
                sig_id = f"sig_test_{idx}"
                thm_id = f"thm_test_{idx}"
                pp_id = f"pp_test_{idx}"
                opp_id = f"opp_test_{idx}"
                req_id = f"req_test_{idx}"
                session.add(SignalRow(id=sig_id, raw_feedback_id=fb_id, signal_type="complaint", summary=f"S{idx}", evidence=[], version_id=ver_id))
                session.add(ThemeRow(id=thm_id, name=f"T{idx}", description="D", signal_ids=[sig_id], signal_count=1, pipeline_profile="product_feedback", version_id=ver_id, created_at=now, updated_at=now))
                session.add(PainPointRow(id=pp_id, theme_ids=[thm_id], description=f"PP{idx}", version_id=ver_id, created_at=now, updated_at=now))
                session.add(OpportunityRow(id=opp_id, pain_point_ids=[pp_id], jtbd_statement=f"JTBD{idx}", description=f"OPP{idx}", version_id=ver_id, created_at=now, updated_at=now))
                session.add(RequirementAssetRow(id=req_id, opportunity_ids=[opp_id], title=f"REQ{idx}", version_id=ver_id, created_at=now, updated_at=now))
            await session.commit()

        assert len((await client.get(f"/api/v1/signals?version_id={v1['id']}")).json()) == 1
        assert len((await client.get(f"/api/v1/themes?profile=product_feedback&version_id={v1['id']}")).json()) == 1
        assert len((await client.get(f"/api/v1/pain-points?profile=product_feedback&version_id={v1['id']}")).json()) == 1
        assert len((await client.get(f"/api/v1/opportunities?profile=product_feedback&version_id={v1['id']}")).json()) == 1
        assert len((await client.get(f"/api/v1/requirements?profile=product_feedback&version_id={v1['id']}")).json()) == 1

        # 6. Rename + archive + cannot delete default
        upd = await client.patch(f"/api/v1/versions/{v1['id']}", json={"name": "v1-已重命名", "status": "archived"})
        assert upd.status_code == 200 and upd.json()["name"] == "v1-已重命名" and upd.json()["status"] == "archived"
        assert (await client.delete("/api/v1/versions/default")).status_code == 400

        # 7. Deleting v1 removes v1 records while leaving v2 completely intact
        del_res = await client.delete(f"/api/v1/versions/{v1['id']}")
        assert del_res.status_code == 200 and del_res.json()["deleted"] is True
        assert len((await client.get(f"/api/v1/feedback?version_id={v1['id']}")).json()) == 0
        assert len((await client.get(f"/api/v1/feedback?version_id={v2['id']}")).json()) == 1
        assert len((await client.get(f"/api/v1/requirements?version_id={v2['id']}")).json()) == 1

    await engine.dispose()


@pytest.mark.asyncio
async def test_sqlite_legacy_schema_migration_adds_version_id_and_upgrades_index(tmp_path):
    db_url = f"sqlite+aiosqlite:///{tmp_path / 'legacy.sqlite'}"
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.execute(text(
            "CREATE TABLE raw_feedback_items ("
            "id VARCHAR(40) PRIMARY KEY, source_type VARCHAR(40) NOT NULL, source_id VARCHAR(100) NOT NULL, "
            "dedupe_key VARCHAR(200) NOT NULL)"
        ))
        await conn.execute(text("CREATE UNIQUE INDEX raw_feedback_dedupe_idx ON raw_feedback_items (source_id, dedupe_key)"))
        for tbl in ("feedback_signals", "themes", "pain_points", "opportunities", "requirement_assets", "pipeline_runs"):
            await conn.execute(text(f"CREATE TABLE {tbl} (id VARCHAR(40) PRIMARY KEY)"))
        await conn.execute(text(
            "CREATE TABLE dataset_versions ("
            "id VARCHAR(40) PRIMARY KEY, name VARCHAR(120) NOT NULL, description TEXT NOT NULL DEFAULT '', "
            "status VARCHAR(20) NOT NULL DEFAULT 'active')"
        ))
        await _ensure_version_schema(conn, db_url)
        cols = {row[1] for row in (await conn.execute(text("PRAGMA table_info(raw_feedback_items)"))).fetchall()}
        idx_cols = [row[2] for row in (await conn.execute(text("PRAGMA index_info('raw_feedback_dedupe_idx')"))).fetchall()]
        default_row = (await conn.execute(text("SELECT id FROM dataset_versions WHERE id='default'"))).fetchone()

    assert "version_id" in cols
    assert idx_cols == ["version_id", "source_id", "dedupe_key"]
    assert default_row is not None
    await engine.dispose()


@pytest.mark.asyncio
async def test_existing_chrome_batch_partial_failure_and_single_tab_retry():
    collector = ExistingChromeCollector()
    collector._status = "connected"
    collector._transport = type("FakeTransport", (), {"closed": False})()
    collector._tabs = {"t_bili": "target_bili", "t_dy": "target_dy"}
    collector._tab_meta = {
        "t_bili": {"target_id": "target_bili", "platform": "bilibili", "url": "https://www.bilibili.com/", "title": "B站"},
        "t_dy": {"target_id": "target_dy", "platform": "douyin", "url": "https://www.douyin.com/", "title": "抖音"},
    }

    dy_attempts = 0

    async def fake_collect(task, target_id):
        nonlocal dy_attempts
        if target_id == "target_bili":
            return {
                "items": [{"entity_type": "post", "source_type": "bilibili", "text": "B站正文", "external_url": "https://www.bilibili.com/video/BV1xx411c7mD", "capture_version": "mining-existing-chrome-dom/v1"}],
                "summary": {"post_count": 1, "comment_count": 0, "item_count": 1},
            }
        dy_attempts += 1
        if dy_attempts == 1:
            from signal_miner.connectors.existing_chrome import ChromeError
            raise ChromeError("access_gate", "抖音出现登录或验证遮罩。")
        return {
            "items": [{"entity_type": "post", "source_type": "douyin", "text": "抖音正文", "external_url": "https://www.douyin.com/video/7412345678901234567", "capture_version": "mining-existing-chrome-dom/v1"}],
            "summary": {"post_count": 1, "comment_count": 0, "item_count": 1},
        }

    collector._collect = fake_collect

    started = await collector.start_batch({
        "tab_ids": ["t_bili", "t_dy"],
        "mode": "search",
        "query": "DeepSeek",
        "max_posts": 2,
        "max_comments": 5,
        "concurrency": 2,
    })
    assert started["status"] == "running"
    await asyncio.sleep(0.05)

    done = collector.public_batch(collector.get_batch(started["id"]))
    assert done["status"] == "completed"
    assert done["summary"]["completed_tabs"] == 1
    assert done["summary"]["failed_tabs"] == 1
    assert len(collector.batch_results(started["id"])["items"]) == 1

    # Retry only the failed Douyin tab while preserving Bilibili results
    retried = await collector.retry_batch_tab(started["id"], "t_dy")
    assert retried["status"] == "running"
    await asyncio.sleep(0.05)

    final = collector.public_batch(collector.get_batch(started["id"]))
    assert final["status"] == "completed"
    assert final["summary"]["completed_tabs"] == 2
    assert final["summary"]["failed_tabs"] == 0
    items = collector.batch_results(started["id"])["items"]
    assert {it["source_type"] for it in items} == {"bilibili", "douyin"}
