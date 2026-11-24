"""Regression tests for code review security, clustering isolation, limit pagination, and re-entrancy fixes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from signal_miner.db.models import (
    Base,
    OpportunityRow,
    PainPointRow,
    RawFeedbackRow,
    RequirementAssetRow,
    SignalRow,
    ThemeRow,
)
from signal_miner.pipeline import clustering as clustering_mod
from signal_miner.routes import assets as assets_routes
from signal_miner.routes import feedback as feedback_routes
from signal_miner.routes import mediacrawler as mediacrawler_routes
from signal_miner.routes import pipeline as pipeline_routes
from signal_miner.routes import versions as versions_routes
from signal_miner.services import StreamerService


@pytest.mark.asyncio
async def test_cross_origin_mutating_routes_rejected_with_403():
    app = FastAPI()
    app.include_router(versions_routes.router, prefix="/api/v1")
    app.include_router(feedback_routes.router, prefix="/api/v1")
    app.include_router(pipeline_routes.router, prefix="/api/v1")
    app.include_router(mediacrawler_routes.router, prefix="/api/v1")

    evil_headers = {"Origin": "https://evil.example"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:18818") as client:
        for method, path, body in (
            ("POST", "/api/v1/versions", {"name": "hack"}),
            ("DELETE", "/api/v1/versions/ver_1", None),
            ("POST", "/api/v1/pipeline/run", {"profile": "product_feedback"}),
            ("POST", "/api/v1/feedback/ingest", {"source_type": "manual", "text": "hi"}),
            ("POST", "/api/v1/mediacrawler/tasks", {"platform": "xhs", "mode": "search", "query": "test"}),
        ):
            resp = await client.request(method, path, json=body, headers=evil_headers)
            assert resp.status_code == 403, (method, path, resp.status_code, resp.text)


@pytest.mark.asyncio
async def test_clustering_isolates_signals_by_pipeline_profile_within_same_version(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'cluster_iso.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(clustering_mod, "get_session_factory", lambda: factory)
    monkeypatch.setattr(clustering_mod, "log_pipeline_event", AsyncMock())

    now = datetime.now(timezone.utc)
    async with factory() as session:
        session.add(RawFeedbackRow(
            id="fb_prod", source_type="zhihu", source_id="zhihu_api", dedupe_key="k1",
            author={}, content={"text": "安装复杂"}, context={}, pipeline_profile="product_feedback", version_id="ver_shared",
        ))
        session.add(RawFeedbackRow(
            id="fb_vid", source_type="bilibili", source_id="bili_api", dedupe_key="k2",
            author={}, content={"text": "前3秒强钩子"}, context={}, pipeline_profile="aigc_video", version_id="ver_shared",
        ))
        session.add(SignalRow(
            id="sig_prod", raw_feedback_id="fb_prod", signal_type="complaint", summary="安装太复杂",
            evidence=["安装复杂"], embedding=[1.0, 0.0, 0.0], embedding_model="BAAI/bge-small-zh-v1.5",
            version_id="ver_shared", created_at=now, updated_at=now,
        ))
        session.add(SignalRow(
            id="sig_vid", raw_feedback_id="fb_vid", signal_type="viral_hook", summary="前3秒反常识开场",
            evidence=["前3秒强钩子"], embedding=[1.0, 0.0, 0.0], embedding_model="BAAI/bge-small-zh-v1.5",
            version_id="ver_shared", created_at=now, updated_at=now,
        ))
        await session.commit()

    mock_llm = SimpleNamespace(
        call_structured=AsyncMock(return_value=json.dumps({
            "name": "安装体验问题", "description": "用户反馈安装复杂", "representative_quotes": ["安装复杂"],
        }))
    )

    created = await clustering_mod.cluster_signals_into_themes(
        mock_llm, pipeline_profile="product_feedback", version_id="ver_shared",
    )
    assert created == 1

    async with factory() as session:
        themes = (await session.execute(clustering_mod.select(ThemeRow))).scalars().all()
        assert len(themes) == 1
        assert themes[0].signal_ids == ["sig_prod"]
        assert themes[0].pipeline_profile == "product_feedback"

    await engine.dispose()


@pytest.mark.asyncio
async def test_assets_list_does_not_truncate_other_profile_before_limit(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'assets_limit.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(assets_routes, "get_session_factory", lambda: factory)

    base_time = datetime.now(timezone.utc)
    async with factory() as session:
        # Older product_feedback chain
        session.add(ThemeRow(id="thm_p", name="P", description="", signal_ids=[], signal_count=1, pipeline_profile="product_feedback", version_id="default", created_at=base_time, updated_at=base_time))
        session.add(PainPointRow(id="pp_p", theme_ids=["thm_p"], description="PP_P", version_id="default", created_at=base_time, updated_at=base_time))
        session.add(OpportunityRow(id="opp_p", pain_point_ids=["pp_p"], jtbd_statement="JTBD_P", description="OPP_P", version_id="default", created_at=base_time, updated_at=base_time))
        session.add(RequirementAssetRow(id="req_p", opportunity_ids=["opp_p"], title="REQ_P", version_id="default", created_at=base_time, updated_at=base_time))
        # Newer aigc_video chain (would crowd out limit=1 if SQL LIMIT ran before profile filter!)
        newer = base_time + timedelta(minutes=5)
        session.add(ThemeRow(id="thm_v", name="V", description="", signal_ids=[], signal_count=1, pipeline_profile="aigc_video", version_id="default", created_at=newer, updated_at=newer))
        session.add(PainPointRow(id="pp_v", theme_ids=["thm_v"], description="PP_V", version_id="default", created_at=newer, updated_at=newer))
        session.add(OpportunityRow(id="opp_v", pain_point_ids=["pp_v"], jtbd_statement="JTBD_V", description="OPP_V", version_id="default", created_at=newer, updated_at=newer))
        session.add(RequirementAssetRow(id="req_v", opportunity_ids=["opp_v"], title="REQ_V", version_id="default", created_at=newer, updated_at=newer))
        await session.commit()

    app = FastAPI()
    app.include_router(assets_routes.router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:18818") as client:
        pps = (await client.get("/api/v1/pain-points?profile=product_feedback&limit=1")).json()
        opps = (await client.get("/api/v1/opportunities?profile=product_feedback&limit=1")).json()
        reqs = (await client.get("/api/v1/requirements?profile=product_feedback&limit=1")).json()
        assert [p["id"] for p in pps] == ["pp_p"]
        assert [o["id"] for o in opps] == ["opp_p"]
        assert [r["id"] for r in reqs] == ["req_p"]

    await engine.dispose()


@pytest.mark.asyncio
async def test_pipeline_run_claims_pending_feedback_atomically(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'claim.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    monkeypatch.setattr(pipeline_routes, "get_session_factory", lambda: factory)
    from signal_miner.pipeline import runner as runner_mod
    monkeypatch.setattr(runner_mod, "run_mining_pipeline", AsyncMock())

    async with factory() as session:
        session.add(RawFeedbackRow(
            id="fb_1", source_type="manual", source_id="manual_api", dedupe_key="k_claim",
            author={}, content={"text": "test"}, context={}, processing_state="pending",
            pipeline_profile="product_feedback", version_id="default",
        ))
        await session.commit()

    app = FastAPI()
    app.state.runtime = SimpleNamespace(llm=SimpleNamespace(), embedding_llm=None, streamer=StreamerService())
    app.include_router(pipeline_routes.router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:18818") as client:
        first = await client.post("/api/v1/pipeline/run", json={"profile": "product_feedback", "version_id": "default"})
        assert first.status_code == 202
        # Immediate second trigger sees 0 pending items (already claimed as processing)
        second = await client.post("/api/v1/pipeline/run", json={"profile": "product_feedback", "version_id": "default"})
        assert second.status_code == 404

    await engine.dispose()


def test_frontend_src_bundle_is_in_sync():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    src_dir = root / "frontend" / "src"
    bundle = (root / "frontend" / "static" / "app.js").read_text(encoding="utf-8")
    parts = sorted(src_dir.glob("*.js"))
    assert len(parts) >= 5
    assembled = "".join(p.read_text(encoding="utf-8") for p in parts)
    assert bundle == assembled, "frontend/static/app.js is out of sync with frontend/src/*.js; run `node scripts/build_frontend.mjs`"
