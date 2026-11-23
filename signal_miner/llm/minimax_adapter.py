"""Minimax LLM adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING

from openai import AsyncOpenAI
import structlog

if TYPE_CHECKING:
    from signal_miner.llm.types import MultimodalInput

logger = structlog.get_logger(__name__)


class MinimaxAdapter:
    """Adapter for the Minimax API (using their OpenAI-compatible endpoint)."""

    def __init__(
        self,
        api_key: str,
        group_id: str = "",  # noqa: ARG002 (required by Minimax API contract)
        model: str = "MiniMax-M2.7-highspeed",
        base_url: str = "https://api.minimaxi.com/v1",
    ) -> None:
        # Minimax OpenAI compatible API requires group_id in some contexts,
        # but modern v1 endpoints often just use Bearer token.
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    @property
    def provider_name(self) -> str:
        return "minimax"

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

    async def call_text(self, prompt: str, *, temperature: float = 0.3) -> str:
        """Call the LLM and return plain text."""
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty response from Minimax")
        logger.debug(
            "minimax_call_text",
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
        # Ensure prompt asks for JSON, as some minimax models might not fully support response_format strict json
        modified_prompt = prompt + "\n\nCRITICAL: You MUST output valid JSON format."
        try:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": modified_prompt}],
                response_format={"type": "json_object"},
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
            content = response.choices[0].message.content
        except Exception as e:
            # Fallback to standard request without response_format if it errors out
            logger.warning("minimax_json_format_failed", error=str(e))
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=[{"role": "user", "content": modified_prompt}],
                temperature=temperature,
                max_completion_tokens=max_tokens,
            )
            content = response.choices[0].message.content

        if not content:
            raise ValueError("Empty structured response from Minimax")
        logger.debug(
            "minimax_call_structured",
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
        """Generate an embedding vector.
        Minimax provides embo-01 embedding model.
        """
        try:
            response = await self._client.embeddings.create(
                model="embo-01",
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("minimax_embedding_failed", error=str(e))
            raise NotImplementedError(f"Minimax embedding failed or not fully supported: {e}") from e

    async def call_multimodal(
        self,
        prompt: str,  # noqa: ARG002
        media: list[MultimodalInput],  # noqa: ARG002
        *,
        temperature: float = 0.1,  # noqa: ARG002
    ) -> str:
        """Reject media for the configured text-only MiniMax model."""
        raise NotImplementedError("The configured MiniMax adapter is text-only.")
