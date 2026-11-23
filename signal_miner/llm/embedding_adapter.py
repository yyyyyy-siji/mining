"""Decoupled embedding adapters: local free Chinese ONNX (fastembed) and cloud APIs."""

from __future__ import annotations

import asyncio
import importlib.util
from typing import TYPE_CHECKING

from openai import AsyncOpenAI
import structlog

if TYPE_CHECKING:
    from signal_miner.llm.types import MultimodalInput

logger = structlog.get_logger(__name__)

EMBEDDING_PRESETS: dict[str, dict[str, str]] = {
    "local": {
        "label": "本机免费中文向量 (fastembed · 离线零费用)",
        "default_model": "BAAI/bge-small-zh-v1.5",
        "base_url": "",
    },
    "siliconflow": {
        "label": "硅基流动 SiliconFlow (BAAI/bge-m3)",
        "default_model": "BAAI/bge-m3",
        "base_url": "https://api.siliconflow.cn/v1",
    },
    "dashscope": {
        "label": "阿里云百炼 DashScope (text-embedding-v4)",
        "default_model": "text-embedding-v4",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    },
    "zhipu": {
        "label": "智谱 AI BigModel (embedding-3)",
        "default_model": "embedding-3",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    "openai": {
        "label": "OpenAI (text-embedding-3-small)",
        "default_model": "text-embedding-3-small",
        "base_url": "",
    },
    "custom": {
        "label": "自定义 OpenAI 兼容 Embedding API",
        "default_model": "",
        "base_url": "",
    },
}


class LocalFastEmbedAdapter:
    """Offline local embedding adapter backed by fastembed (ONNX Runtime)."""

    def __init__(self, model: str = "BAAI/bge-small-zh-v1.5") -> None:
        self._model_name = model or "BAAI/bge-small-zh-v1.5"
        self._embedder = None
        self._last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    @property
    def provider_name(self) -> str:
        return "local_fastembed"

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def input_modalities(self) -> tuple[str, ...]:
        return ("text",)

    @property
    def supports_multimodal(self) -> bool:
        return False

    @property
    def supports_embedding(self) -> bool:
        return importlib.util.find_spec("fastembed") is not None

    @property
    def last_usage(self) -> dict[str, int]:
        return self._last_usage

    def _embed_sync(self, text: str) -> list[float]:
        if self._embedder is None:
            from fastembed import TextEmbedding

            self._embedder = TextEmbedding(model_name=self._model_name)
        vectors = list(self._embedder.embed([text]))
        return [float(x) for x in vectors[0]]

    async def embed(self, text: str) -> list[float]:
        """Generate a local semantic embedding vector."""
        if not self.supports_embedding:
            raise RuntimeError("fastembed is not installed in this Python environment.")
        return await asyncio.to_thread(self._embed_sync, text)

    async def call_text(self, prompt: str, *, temperature: float = 0.3) -> str:  # noqa: ARG002
        raise NotImplementedError("LocalFastEmbedAdapter only supports embed().")

    async def call_structured(
        self, prompt: str, *, temperature: float = 0.1, max_tokens: int = 2000  # noqa: ARG002
    ) -> str:
        raise NotImplementedError("LocalFastEmbedAdapter only supports embed().")

    async def call_multimodal(
        self,
        prompt: str,  # noqa: ARG002
        media: list[MultimodalInput],  # noqa: ARG002
        *,
        temperature: float = 0.1,  # noqa: ARG002
    ) -> str:
        raise NotImplementedError("LocalFastEmbedAdapter only supports embed().")


class OpenAICompatibleEmbeddingAdapter:
    """Cloud embedding adapter for SiliconFlow, DashScope, Zhipu, OpenAI, or custom endpoints."""

    def __init__(
        self,
        *,
        provider: str,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    @property
    def provider_name(self) -> str:
        return self._provider

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def input_modalities(self) -> tuple[str, ...]:
        return ("text",)

    @property
    def supports_multimodal(self) -> bool:
        return False

    @property
    def supports_embedding(self) -> bool:
        return True

    @property
    def last_usage(self) -> dict[str, int]:
        return self._last_usage

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector via OpenAI-compatible /embeddings endpoint."""
        response = await self._client.embeddings.create(model=self._model, input=text)
        usage = getattr(response, "usage", None)
        if usage:
            self._last_usage = {
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": 0,
            }
        return [float(x) for x in response.data[0].embedding]

    async def call_text(self, prompt: str, *, temperature: float = 0.3) -> str:  # noqa: ARG002
        raise NotImplementedError("OpenAICompatibleEmbeddingAdapter only supports embed().")

    async def call_structured(
        self, prompt: str, *, temperature: float = 0.1, max_tokens: int = 2000  # noqa: ARG002
    ) -> str:
        raise NotImplementedError("OpenAICompatibleEmbeddingAdapter only supports embed().")

    async def call_multimodal(
        self,
        prompt: str,  # noqa: ARG002
        media: list[MultimodalInput],  # noqa: ARG002
        *,
        temperature: float = 0.1,  # noqa: ARG002
    ) -> str:
        raise NotImplementedError("OpenAICompatibleEmbeddingAdapter only supports embed().")


__all__ = [
    "EMBEDDING_PRESETS",
    "LocalFastEmbedAdapter",
    "OpenAICompatibleEmbeddingAdapter",
]
