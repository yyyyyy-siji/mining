"""Offline tests for DeepSeek multimodal support and persistent pipeline run state."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from signal_miner.db.models import Base, PipelineRunRow
from signal_miner.llm.deepseek_adapter import DeepSeekAdapter
from signal_miner.llm.types import MultimodalInput
from signal_miner.routes import llm as llm_routes
from signal_miner.routes import pipeline as pipeline_routes
from signal_miner.runtime import _build_multimodal_llm_adapter, build_runtime
from signal_miner.services import StreamerService
from signal_miner.settings import AppSettings


def test_deepseek_adapter_capabilities_by_model_and_overrides():
    flash = DeepSeekAdapter(api_key="test-key")
    assert flash.model_name == "deepseek-flash"
    assert flash.input_modalities == ("text", "image")
    assert flash.supports_multimodal is True
    assert flash.supports_embedding is False

    pro = DeepSeekAdapter(api_key="test-key", model="deepseek-v4-pro")
    assert pro.input_modalities == ("text",)
    assert pro.supports_multimodal is False

    override = DeepSeekAdapter(api_key="test-key", model="deepseek-flash", input_modalities=("text",))
    assert override.supports_multimodal is False


@pytest.mark.asyncio
async def test_deepseek_call_multimodal_builds_image_url_and_tracks_usage():
    adapter = DeepSeekAdapter(api_key="test-key", model="deepseek-flash")
    fake_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"summary": "button blocked"}'))],
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=18),
    )
    create_mock = AsyncMock(return_value=fake_response)
    adapter._client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create_mock)))

    result = await adapter.call_multimodal(
        "Describe screenshot issue",
        [
            MultimodalInput(mime_type="image/png", data_base64="AAAA"),
            MultimodalInput(mime_type="image/jpeg", url="https://example.test/ui.jpg"),
        ],
        temperature=0.2,
    )
    assert result == '{"summary": "button blocked"}'
    assert adapter.last_usage == {"input_tokens": 120, "output_tokens": 18}
    call_kwargs = create_mock.call_args.kwargs
    assert call_kwargs["model"] == "deepseek-flash"
    content = call_kwargs["messages"][0]["content"]
    assert content == [
        {"type": "text", "text": "Describe screenshot issue"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAAA"}},
        {"type": "image_url", "image_url": {"url": "https://example.test/ui.jpg"}},
    ]


@pytest.mark.asyncio
async def test_deepseek_call_multimodal_rejects_text_only_and_unsupported_modalities():
    pro = DeepSeekAdapter(api_key="test-key", model="deepseek-v4-pro")
    with pytest.raises(NotImplementedError, match="text-only"):
        await pro.call_multimodal("hi", [MultimodalInput(mime_type="image/png", data_base64="AAAA")])

    flash = DeepSeekAdapter(api_key="test-key", model="deepseek-flash")
    with pytest.raises(ValueError, match="At least one"):
        await flash.call_multimodal("hi", [])
    with pytest.raises(ValueError, match="Unsupported DeepSeek input modality"):
        await flash.call_multimodal("hi", [MultimodalInput(mime_type="video/mp4", url="https://example.test/a.mp4")])


@pytest.mark.asyncio
async def test_runtime_enables_deepseek_multimodal_and_respects_disabled_and_split_configs(tmp_path):
    settings = AppSettings(
        deepseek_api_key="test-key",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'rt.sqlite'}",
        state_backend="memory",
        debug=False,
    )
    runtime = await build_runtime(settings)
    assert runtime.llm.provider_name == "deepseek"
    assert runtime.llm.model_name == "deepseek-flash"
    assert runtime.llm.supports_multimodal is True
    assert runtime.multimodal_llm is runtime.llm

    app = FastAPI()
    app.state.runtime = runtime
    app.include_router(llm_routes.router, prefix="/api/v1")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        caps = (await client.get("/api/v1/llm/capabilities")).json()
    assert caps["primary"]["model"] == "deepseek-flash"
    assert caps["primary"]["supports_multimodal"] is True
    assert caps["multimodal"]["enabled"] is True
    assert caps["multimodal"]["provider"] == "deepseek"
    assert caps["multimodal"]["input_modalities"] == ["text", "image"]
    await runtime.state_store.close()

    pro_settings = AppSettings(
        deepseek_api_key="test-key",
        deepseek_model="deepseek-v4-pro",
        multimodal_llm_provider="deepseek",
    )
    pro_primary = DeepSeekAdapter(api_key="test-key", model="deepseek-v4-pro")
    split_media = _build_multimodal_llm_adapter(pro_settings, primary_llm=pro_primary)
    assert split_media is not None
    assert split_media.model_name == "deepseek-flash"
    assert split_media.supports_multimodal is True

    disabled = AppSettings(deepseek_api_key="test-key", multimodal_llm_provider="disabled")
    assert _build_multimodal_llm_adapter(disabled, primary_llm=runtime.llm) is None


@pytest.mark.asyncio
async def test_streamer_replays_step_history_on_reconnect_and_pipeline_runs_endpoint_merges_live(tmp_path, monkeypatch):
    streamer = StreamerService()
    await streamer.publish("run_1", {"run_id": "run_1", "profile": "product_feedback", "step": "queued", "status": "running", "progress": 0.0, "message": "queued"})
    await streamer.publish("run_1", {"run_id": "run_1", "profile": "product_feedback", "step": "extraction", "status": "completed", "progress": 0.3, "message": "done"})
    await streamer.publish("run_1", {"run_id": "run_1", "profile": "product_feedback", "step": "pain_point", "status": "running", "progress": 0.65, "message": "analyzing"})

    reconnected = await streamer.add_subscriber("run_1")
    replayed = [reconnected.get_nowait(), reconnected.get_nowait(), reconnected.get_nowait()]
    assert [ev["step"] for ev in replayed] == ["queued", "extraction", "pain_point"]
    assert replayed[-1]["progress"] == 0.65

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'runs.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(PipelineRunRow(id="run_old", status="completed", feedback_count=3, pipeline_profile="product_feedback", stats={"signals": 5}))
        await session.commit()

    monkeypatch.setattr(pipeline_routes, "get_session_factory", lambda: factory)
    app = FastAPI()
    app.state.runtime = SimpleNamespace(streamer=streamer)
    app.include_router(pipeline_routes.router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        runs = (await client.get("/api/v1/pipeline/runs?limit=5")).json()["runs"]
        assert [r["id"] for r in runs] == ["run_1", "run_old"]
        assert runs[0]["status"] == "running"
        assert runs[0]["live"]["latest"]["progress"] == 0.65
        assert set(runs[0]["live"]["steps"]) == {"queued", "extraction", "pain_point"}

        run_detail = (await client.get("/api/v1/pipeline/runs/run_1")).json()
        assert run_detail["status"] == "running"
        assert run_detail["live"]["latest"]["step"] == "pain_point"

        async with client.stream("GET", "/api/v1/pipeline/stream/run_1") as _:
            pass  # endpoint accepts subscription cleanly

    # Bounded cache keeps at most 50 runs
    for idx in range(60):
        await streamer.publish(f"run_bulk_{idx}", {"run_id": f"run_bulk_{idx}", "step": "queued", "status": "running", "progress": 0.1})
    assert len(streamer.recent_runs()) == 50
    await engine.dispose()
    _ = json.dumps(runs)


@pytest.mark.asyncio
async def test_asset_generator_emits_granular_phase3_progress(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from unittest.mock import AsyncMock

    from signal_miner.db.models import ThemeRow
    from signal_miner.pipeline import asset_generator

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'assets.sqlite'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as session:
        session.add(ThemeRow(
            id="thm_1",
            name="Test Theme",
            description="Theme desc",
            signal_ids=[],
            representative_quotes=["quote 1"],
            status="draft",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        await session.commit()

    monkeypatch.setattr(asset_generator, "get_session_factory", lambda: factory)
    monkeypatch.setattr(asset_generator, "build_supporting_evidence_for_opportunity", AsyncMock(return_value=[]))
    monkeypatch.setattr(asset_generator, "build_evidence_trail_for_requirement", AsyncMock(return_value=[]))
    monkeypatch.setattr(asset_generator, "log_pipeline_event", AsyncMock())

    mock_llm = SimpleNamespace(
        call_structured=AsyncMock(side_effect=[
            json.dumps({"user_segment": "devs", "description": "pain", "frequency": "frequent", "severity": "high", "business_impact": "churn"}),
            json.dumps({"jtbd_statement": "When X, I want Y", "description": "opp", "assumptions": []}),
            json.dumps({"title": "Req 1", "user_stories": [], "acceptance_criteria": [], "impact": {}, "decision_reasoning": "good"}),
        ])
    )

    events: list[tuple[str, float, str]] = []

    async def on_progress(step: str, pct: float, msg: str) -> None:
        events.append((step, pct, msg))

    stats = await asset_generator.generate_assets_from_themes(mock_llm, on_progress=on_progress)
    assert stats == {"pain_points": 1, "opportunities": 1, "requirements": 1}
    assert [e[0] for e in events] == ["pain_point", "opportunity", "requirement"]
    assert 0.65 <= events[0][1] < events[1][1] < events[2][1] < 0.95
    await engine.dispose()
