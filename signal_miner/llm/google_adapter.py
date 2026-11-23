"""Google Gemini LLM adapter."""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING

from google import genai
from google.genai import types
import structlog

if TYPE_CHECKING:
    from signal_miner.llm.types import MultimodalInput

logger = structlog.get_logger(__name__)


class GoogleAdapter:
    """Adapter for the Google Gemini API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-lite",
        input_modalities: tuple[str, ...] = ("text", "image", "audio", "video"),
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model
        self._input_modalities = input_modalities
        self._last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    @property
    def provider_name(self) -> str:
        return "google"

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
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
            ),
        )
        text = response.text
        if not text:
            raise ValueError("Empty response from Google Gemini")
        logger.debug("google_call_text", model=self._model)
        usage = getattr(response, "usage_metadata", None)
        self._last_usage = {
            "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
            "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
        }
        return text

    async def call_structured(
        self, prompt: str, *, temperature: float = 0.1, max_tokens: int = 2000
    ) -> str:
        """Call the LLM with JSON response format."""
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
            ),
        )
        text = response.text
        if not text:
            raise ValueError("Empty structured response from Google Gemini")
        logger.debug("google_call_structured", model=self._model)
        usage = getattr(response, "usage_metadata", None)
        self._last_usage = {
            "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
            "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
        }
        return text

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector using Gemini embedding model."""
        response = await self._client.aio.models.embed_content(
            model="text-embedding-004",
            contents=text,
        )
        return list(response.embeddings[0].values)

    async def call_multimodal(
        self,
        prompt: str,
        media: list[MultimodalInput],
        *,
        temperature: float = 0.1,
    ) -> str:
        """Call Gemini with text plus inline bytes or provider-readable URIs."""
        parts: list[types.Part | str] = [prompt]
        for item in media:
            if item.modality not in self._input_modalities:
                raise ValueError(f"Unsupported Google input modality: {item.modality}")
            if item.data_base64:
                parts.append(
                    types.Part.from_bytes(
                        data=base64.b64decode(item.data_base64, validate=True),
                        mime_type=item.mime_type,
                    )
                )
            else:
                parts.append(types.Part.from_uri(file_uri=item.url or "", mime_type=item.mime_type))

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=parts,
            config=types.GenerateContentConfig(temperature=temperature),
        )
        result = response.text
        if not result:
            raise ValueError("Empty multimodal response from Google Gemini")
        usage = getattr(response, "usage_metadata", None)
        self._last_usage = {
            "input_tokens": getattr(usage, "prompt_token_count", 0) or 0,
            "output_tokens": getattr(usage, "candidates_token_count", 0) or 0,
        }
        return result
