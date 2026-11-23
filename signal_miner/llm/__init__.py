"""LLM adapter abstractions and factory.

Design reference: agentic-prd-generation/backend/agents/ adapter pattern.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

from signal_miner.llm.deepseek_adapter import DeepSeekAdapter
from signal_miner.llm.google_adapter import GoogleAdapter
from signal_miner.llm.minimax_adapter import MinimaxAdapter
from signal_miner.llm.openai_adapter import OpenAIAdapter
from signal_miner.llm.qwen_adapter import QwenAdapter
from signal_miner.llm.types import MultimodalInput

T = TypeVar("T", bound=BaseModel)


class BaseLLMAdapter(Protocol):
    """Protocol for LLM provider adapters."""

    @property
    def provider_name(self) -> str:
        """Human-readable provider identifier."""
        ...

    @property
    def model_name(self) -> str:
        """Configured model identifier."""
        ...

    @property
    def input_modalities(self) -> tuple[str, ...]:
        """Input modalities accepted by this configured adapter."""
        ...

    @property
    def supports_multimodal(self) -> bool:
        """Whether at least one non-text input modality is supported."""
        ...

    @property
    def supports_embedding(self) -> bool:
        """Whether this adapter supports generating embeddings."""
        ...

    async def call_text(self, prompt: str, *, temperature: float = 0.3) -> str:
        """Call the LLM and return raw text response."""
        ...

    async def call_structured(
        self, prompt: str, *, temperature: float = 0.1, max_tokens: int = 2000
    ) -> str:
        """Call the LLM with JSON response format and return raw JSON string."""
        ...

    async def call_multimodal(
        self,
        prompt: str,
        media: list[MultimodalInput],
        *,
        temperature: float = 0.1,
    ) -> str:
        """Call a model with text plus image/audio/video inputs."""
        ...

    @property
    def last_usage(self) -> dict[str, int]:
        """Token usage from the most recent call. Keys: input_tokens, output_tokens."""
        ...

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text."""
        ...

__all__ = [
    "BaseLLMAdapter",
    "OpenAIAdapter",
    "GoogleAdapter",
    "DeepSeekAdapter",
    "QwenAdapter",
    "MinimaxAdapter",
    "MultimodalInput",
]
