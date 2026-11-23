"""OpenAI LLM adapter (also supports OpenAI-compatible endpoints like OpenRouter)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI
import structlog

if TYPE_CHECKING:
    from signal_miner.llm.types import MultimodalInput

logger = structlog.get_logger(__name__)


class OpenAIAdapter:
    """Adapter for the OpenAI API (and compatible endpoints)."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
        base_url: str | None = None,
        input_modalities: tuple[str, ...] = ("text", "image"),
    ) -> None:
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)
        self._model = model
        self._embedding_model = embedding_model
        self._input_modalities = input_modalities
        self._last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def input_modalities(self) -> tuple[str, ...]:
        return self._input_modalities

    @property
    def supports_multimodal(self) -> bool:
        return any(modality != "text" for modality in self._input_modalities)

    @property
    def supports_embedding(self) -> bool:
        return True

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
            raise ValueError("Empty response from OpenAI")
        logger.debug(
            "openai_call_text",
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
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty structured response from OpenAI")
        logger.debug(
            "openai_call_structured",
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
        """Generate an embedding vector."""
        response = await self._client.embeddings.create(
            model=self._embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def call_multimodal(
        self,
        prompt: str,
        media: list[MultimodalInput],
        *,
        temperature: float = 0.1,
    ) -> str:
        """Call an OpenAI-compatible vision model with text and images."""
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for item in media:
            if item.modality not in self._input_modalities:
                raise ValueError(f"Unsupported OpenAI input modality: {item.modality}")
            if item.modality != "image":
                raise ValueError("This OpenAI adapter currently supports image inputs only")
            image_url = item.url or f"data:{item.mime_type};base64,{item.data_base64}"
            content.append({"type": "image_url", "image_url": {"url": image_url}})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": content}],
            temperature=temperature,
        )
        result = response.choices[0].message.content
        if not result:
            raise ValueError("Empty multimodal response from OpenAI")
        self._last_usage = {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
        }
        return result

    def get_usage_from_response(self, response) -> dict:
        """Extract token usage from a response object."""
        if response and response.usage:
            return {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
