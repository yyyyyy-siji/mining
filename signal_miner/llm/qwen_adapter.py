"""Qwen LLM adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import AsyncOpenAI
import structlog

if TYPE_CHECKING:
    from signal_miner.llm.types import MultimodalInput

logger = structlog.get_logger(__name__)


class QwenAdapter:
    """Adapter for the Qwen API (using DashScope's OpenAI-compatible endpoint)."""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen-max",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    @property
    def provider_name(self) -> str:
        return "qwen"

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
        return False

    @property
    def last_usage(self) -> dict[str, int]:
        return self._last_usage

    async def call_text(self, prompt: str, *, temperature: float = 0.3) -> str:
        """Call the LLM and return plain text."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from Qwen")
        logger.debug(
            "qwen_call_text",
            model=self._model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        self._last_usage = {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
        }
        return content

    async def call_structured(
        self, prompt: str, *, temperature: float = 0.1, max_tokens: int = 2000
    ) -> str:
        """Call the LLM with JSON response format."""
        # Qwen-max and qwen-turbo support json_object in compatible mode
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty structured response from Qwen")
        logger.debug(
            "qwen_call_structured",
            model=self._model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        self._last_usage = {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
        }
        return content

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector using DashScope text-embedding model."""
        response = await self._client.embeddings.create(
            model="text-embedding-v2", # Qwen's embedding model
            input=text,
        )
        return response.data[0].embedding

    async def call_multimodal(
        self,
        prompt: str,  # noqa: ARG002
        media: list[MultimodalInput],  # noqa: ARG002
        *,
        temperature: float = 0.1,  # noqa: ARG002
    ) -> str:
        """Require a dedicated Qwen-VL adapter instead of guessing by model name."""
        raise NotImplementedError("The configured Qwen adapter is text-only.")
