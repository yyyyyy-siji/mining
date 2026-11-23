"""Offline tests for decoupled Embedding adapters and Model Settings API."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from signal_miner.llm.embedding_adapter import (
    LocalFastEmbedAdapter,
    OpenAICompatibleEmbeddingAdapter,
)
from signal_miner.routes import llm as llm_routes
from signal_miner.runtime import build_runtime
from signal_miner.settings import AppSettings


@pytest.mark.asyncio
async def test_local_fastembed_adapter_embeds_offline(tmp_path):
    adapter = LocalFastEmbedAdapter(model="BAAI/bge-small-zh-v1.5")
    assert adapter.provider_name == "local_fastembed"
    assert adapter.supports_embedding is True
    assert adapter.supports_multimodal is False
    # Verify real local fastembed inference (model already cached locally).
    vec = await adapter.embed("记账时备注弹出会员页")
    assert isinstance(vec, list) and len(vec) == 512 and all(isinstance(v, float) for v in vec)


@pytest.mark.asyncio
async def test_cloud_embedding_adapter_calls_openai_compatible_embeddings():
    adapter = OpenAICompatibleEmbeddingAdapter(
        provider="siliconflow",
        api_key="sf-test-key",
        model="BAAI/bge-m3",
        base_url="https://api.siliconflow.cn/v1",
    )
    assert adapter.provider_name == "siliconflow"
    assert adapter.model_name == "BAAI/bge-m3"
    assert adapter.supports_embedding is True
    fake_resp = SimpleNamespace(
        data=[SimpleNamespace(embedding=[0.1, 0.2, 0.3])],
        usage=SimpleNamespace(prompt_tokens=9),
    )
    create_mock = AsyncMock(return_value=fake_resp)
    adapter._client = SimpleNamespace(embeddings=SimpleNamespace(create=create_mock))
    vec = await adapter.embed("测试")
    assert vec == [0.1, 0.2, 0.3]
    assert adapter.last_usage == {"input_tokens": 9, "output_tokens": 0}
    assert create_mock.call_args.kwargs == {"model": "BAAI/bge-m3", "input": "测试"}


@pytest.mark.asyncio
async def test_runtime_selects_local_or_cloud_embedding_independently_of_deepseek(tmp_path):
    s_auto = AppSettings(
        deepseek_api_key="sk-test-primary",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'auto.sqlite'}",
        state_backend="memory",
        debug=False,
    )
    rt = await build_runtime(s_auto)
    assert rt.llm.provider_name == "deepseek"
    assert rt.embedding_llm is not None
    assert rt.embedding_llm.provider_name == "local_fastembed"
    assert rt.embedding_llm.model_name == "BAAI/bge-small-zh-v1.5"
    await rt.state_store.close()

    s_cloud = AppSettings(
        deepseek_api_key="sk-test-primary",
        embedding_provider="dashscope",
        embedding_api_key="sk-dash-test",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'cloud.sqlite'}",
        state_backend="memory",
        debug=False,
    )
    rt_cloud = await build_runtime(s_cloud)
    assert rt_cloud.llm.provider_name == "deepseek"
    assert rt_cloud.embedding_llm.provider_name == "dashscope"
    assert rt_cloud.embedding_llm.model_name == "text-embedding-v4"
    await rt_cloud.state_store.close()


@pytest.mark.asyncio
async def test_model_settings_api_masks_secrets_persists_env_and_hot_reloads(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DATABASE_URL=sqlite+aiosqlite:///keep.db\nDEEPSEEK_API_KEY=sk-secret-12345678\n", encoding="utf-8")
    monkeypatch.setattr(llm_routes, "_env_path", lambda: env_file)

    settings = AppSettings(
        deepseek_api_key="sk-secret-12345678",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 's.sqlite'}",
        state_backend="memory",
        debug=False,
    )
    runtime = await build_runtime(settings)
    app = FastAPI()
    app.state.runtime = runtime
    app.include_router(llm_routes.router, prefix="/api/v1")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://127.0.0.1:18818") as client:
        # Cross-origin blocked
        forbid = await client.get("/api/v1/llm/settings", headers={"Origin": "https://evil.test"})
        assert forbid.status_code == 403

        # Read never exposes plaintext key
        read_res = await client.get("/api/v1/llm/settings")
        assert read_res.status_code == 200
        body = read_res.json()
        assert "sk-secret-12345678" not in read_res.text
        assert body["primary"]["providers"]["deepseek"]["api_key_configured"] is True
        assert body["primary"]["providers"]["deepseek"]["api_key_masked"] == "sk-s****5678"
        assert body["capabilities"]["embedding"]["enabled"] is True

        # Rejects control characters / insecure base_url
        bad_nl = await client.post("/api/v1/llm/settings", json={
            "default_llm_provider": "deepseek",
            "primary_model": "deepseek-flash\nEVIL=1",
        })
        assert bad_nl.status_code == 422

        bad_url = await client.post("/api/v1/llm/settings", json={
            "default_llm_provider": "deepseek",
            "embedding_provider": "custom",
            "embedding_base_url": "http://remote.invalid/v1",
            "embedding_api_key": "k",
            "embedding_model": "m",
        })
        assert bad_url.status_code == 422

        # Save cloud embedding (SiliconFlow) while keeping primary DeepSeek key intact
        save_res = await client.post("/api/v1/llm/settings", json={
            "default_llm_provider": "deepseek",
            "primary_model": "deepseek-flash",
            "primary_api_key": "",
            "embedding_provider": "siliconflow",
            "embedding_model": "BAAI/bge-m3",
            "embedding_base_url": "https://api.siliconflow.cn/v1",
            "embedding_api_key": "sf-new-key-9999",
        })
        assert save_res.status_code == 200
        saved = save_res.json()
        assert "sf-new-key-9999" not in save_res.text
        assert saved["capabilities"]["embedding"]["provider"] == "siliconflow"
        assert saved["capabilities"]["embedding"]["model"] == "BAAI/bge-m3"

        # Switch back to local free embedding and test live local embedding endpoint
        local_res = await client.post("/api/v1/llm/settings", json={
            "default_llm_provider": "deepseek",
            "primary_model": "deepseek-flash",
            "embedding_provider": "local",
            "embedding_model": "BAAI/bge-small-zh-v1.5",
        })
        assert local_res.status_code == 200
        assert local_res.json()["capabilities"]["embedding"]["provider"] == "local_fastembed"

        test_emb = await client.post("/api/v1/llm/test", json={"target": "embedding"})
        assert test_emb.status_code == 200 and test_emb.json()["ok"] is True
        assert test_emb.json()["dimensions"] == 512

    env_text = Path(env_file).read_text(encoding="utf-8")
    assert "DATABASE_URL=sqlite+aiosqlite:///keep.db" in env_text
    assert "DEEPSEEK_API_KEY=sk-secret-12345678" in env_text
    assert "EMBEDDING_PROVIDER=local" in env_text
    await runtime.state_store.close()
