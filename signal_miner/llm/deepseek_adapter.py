"""DeepSeek LLM adapter (text and DeepSeek-V4.1-Flash vision multimodal)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from openai import AsyncOpenAI
import structlog

if TYPE_CHECKING:
    from signal_miner.llm.types import MultimodalInput

logger = structlog.get_logger(__name__)

# Verified against https://api.deepseek.com/v1/models:
# - deepseek-flash (DeepSeek-V4.1-Flash) and its chat/vision aliases support text + image.
# - deepseek-v4-pro / deepseek-reasoner remain text-only.
DEEPSEEK_IMAGE_MODELS = frozenset({
    "deepseek-flash",
    "deepseek-v4-flash-vision-exp",
    "deepseek-chat",
})


class DeepSeekAdapter:
    """Adapter for the DeepSeek API (using OpenAI-compatible endpoint)."""

    def __init__(
        self,
        api_key: str,
        model: str = "deepseek-flash",
        base_url: str = "https://api.deepseek.com/v1",
        input_modalities: tuple[str, ...] | None = None,
    ) -> None:
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._input_modalities: tuple[str, ...] = (
            tuple(input_modalities)
            if input_modalities is not None
            else (("text", "image") if model in DEEPSEEK_IMAGE_MODELS else ("text",))
        )
        self._last_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    @property
    def provider_name(self) -> str:
        return "deepseek"

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
            raise ValueError("Empty response from DeepSeek")
        logger.debug(
            "deepseek_call_text",
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
        """Call the LLM with JSON response format.
        Note: DeepSeek supports response_format={"type": "json_object"}.
        """
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=temperature,
            max_completion_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Empty structured response from DeepSeek")
        logger.debug(
            "deepseek_call_structured",
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
        Currently DeepSeek doesn't have a public embedding model, but we might use an alternative
        like an OpenAI embedding or a local HuggingFace embedding in a real setup.
        For now, this raises an error to be handled or we can fallback.
        """
        raise NotImplementedError("DeepSeek does not currently provide an embedding endpoint. Please configure a different embedding model.")

    async def call_multimodal(
        self,
        prompt: str,
        media: list[MultimodalInput],
        *,
        temperature: float = 0.1,
    ) -> str:
        """Call DeepSeek vision model with text plus image inputs."""
        if not self.supports_multimodal:
            raise NotImplementedError(
                f"The configured DeepSeek model '{self._model}' is text-only."
            )
        if not media:
            raise ValueError("At least one MultimodalInput item is required")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for item in media:
            if item.modality not in self._input_modalities:
                raise ValueError(f"Unsupported DeepSeek input modality: {item.modality}")
            if item.modality != "image":
                raise ValueError("DeepSeek multimodal currently supports image inputs only")
            image_url = item.url or f"data:{item.mime_type};base64,{item.data_base64}"
            content.append({"type": "image_url", "image_url": {"url": image_url}})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": content}],
            temperature=temperature,
        )
        result = response.choices[0].message.content
        if not result:
            raise ValueError("Empty multimodal response from DeepSeek")
        logger.debug(
            "deepseek_call_multimodal",
            model=self._model,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
        )
        self._last_usage = {
            "input_tokens": response.usage.prompt_tokens if response.usage else 0,
            "output_tokens": response.usage.completion_tokens if response.usage else 0,
        }
        return result
